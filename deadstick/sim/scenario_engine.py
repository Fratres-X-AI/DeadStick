from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pymavlink import mavutil

from deadstick.evaluate.runner import evaluate_rule
from deadstick.metadata import assert_not_fake_metadata, load_metadata
from deadstick.param_file import load_param_file
from deadstick.provenance import build_provenance, sha256_file
from deadstick.report.json_report import write_result_json
from deadstick.report.md_report import write_report_md
from deadstick.rules.loader import load_rule
from deadstick.rules.schema import RuleFile
from deadstick.sim.dataflash_log import find_latest_dataflash_bin
from deadstick.sim.faults import FaultInjector
from deadstick.sim.link import (
    apply_param_file,
    connect,
    drain_ack_results,
    reboot_and_reconnect,
    send_arm_command,
    set_mode_apm,
    set_param,
    vehicle_time_boot_ms,
    wait_heartbeat,
)
from deadstick.sim.sitl import SitlProcess
from deadstick.timeline.dataflash import bin_to_timeline
from deadstick.timeline.jsonl import load_jsonl
from deadstick.timeline.model import Timeline, TimelineEvent
from deadstick.timeline.recorder import append_events, poll_mavlink_to_timeline
from deadstick.verdict import Result, Verdict


@dataclass
class SitlRunResult:
    verdict: Verdict
    reason: str
    results: list[Result]
    timeline_jsonl: Path | None
    dataflash_bin: Path | None
    run_dir: Path
    harness_error: str | None = None
    not_applied: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


def _worst(rows: list[Result]) -> Verdict:
    order = [Verdict.PASS, Verdict.CANNOT_JUDGE, Verdict.FAIL, Verdict.ERROR]
    worst = Verdict.PASS
    for r in rows:
        if order.index(r.verdict) > order.index(worst):
            worst = r.verdict
    return worst


def _prelude_for_inject_kind(kind: str) -> list[tuple[str, dict[str, Any]]]:
    k = kind.lower()
    if "rc_loss_while_disarmed" in k:
        return []
    if "rc_loss_in_air" in k or "battery" in k:
        return [
            ("wait_ready", {"timeout_s": 180.0}),
            ("set_mode", {"mode": "GUIDED"}),
            ("arm", {}),
            ("takeoff", {"alt_m": 20.0}),
            ("move_north", {"m": 100.0}),
            ("set_mode", {"mode": "LOITER"}),
            ("hold", {"seconds": 5.0}),
        ]
    return []


def _post_inject_for_kind(
    kind: str, observe_after_inject_s: float
) -> list[tuple[str, dict[str, Any]]]:
    k = kind.lower()
    if "rc_loss_while_disarmed" in k:
        return [
            ("attempt_arm", {}),
            ("observe", {"seconds": 8.0}),
        ]
    return [
        ("observe", {"seconds": observe_after_inject_s}),
    ]


def _expand_scenario_steps(
    rule: RuleFile, observe_after_inject_s: float
) -> list[tuple[str, dict[str, Any]]]:
    """Flat sequence: prelude (from inject kind), YAML steps, post-inject observe/arm."""
    out: list[tuple[str, dict[str, Any]]] = []
    for st in rule.scenario:
        if st.step == "inject_fault":
            kind = str(st.args.get("kind", ""))
            out.extend(_prelude_for_inject_kind(kind))
            out.append((st.step, st.args))
            out.extend(_post_inject_for_kind(kind, observe_after_inject_s))
        else:
            out.append((st.step, st.args))
    return out


def run_rule_on_sitl(
    *,
    rule_path: Path,
    param_path: Path,
    metadata_path: Path,
    arducopter_bin: Path,
    defaults_parm: Path | None,
    results_dir: Path,
    speedup: float = 1.0,
    tcp_base_port: int = 5760,
    instance: int = 0,
    observe_after_inject_s: float = 45.0,
    allow_fake_metadata: bool = False,
    seed: int | None = None,
) -> SitlRunResult:
    """
    Full harness: isolated SITL dir, MAVLink JSONL, optional dataflash .BIN,
    then evaluate_rule (prefers .BIN timeline when non-empty).
    """
    run_id = str(uuid.uuid4())[:12]
    run_dir = results_dir / f"sitl_{run_id}"
    if run_dir.exists():
        raise RuntimeError(f"Run directory already exists (refusing overwrite): {run_dir}")
    sitl_work = run_dir / "sitl_work"
    timeline_path = run_dir / "timeline.jsonl"
    rule = load_rule(rule_path)
    meta = load_metadata(metadata_path)
    if not allow_fake_metadata:
        assert_not_fake_metadata(metadata_path, meta)

    tcp_port = tcp_base_port + int(instance) * 10
    mavlink_url = f"tcp:127.0.0.1:{tcp_port}"

    sitl = SitlProcess(
        arducopter_bin=arducopter_bin,
        workdir=sitl_work,
        speedup=speedup,
        tcp_port=tcp_port,
        instance=int(instance),
        defaults_parm=defaults_parm,
    )

    harness_error: str | None = None
    timeline_jsonl_written = False
    dataflash: Path | None = None
    not_applied: list[str] = []
    rejected: list[str] = []
    reported: dict[str, float] = {}

    try:
        if timeline_path.exists():
            timeline_path.unlink()
        sitl.start()
        mav = connect(mavlink_url)
        wait_heartbeat(mav)

        reported, missing, rej = apply_param_file(mav, param_path)
        not_applied = missing
        rejected = rej

        for _harness_p, _harness_v in (("LOG_DISARMED", 1.0),):
            if _harness_p in reported:
                set_param(mav, _harness_p, _harness_v)

        mav = reboot_and_reconnect(mavlink_url)

        reported, missing, rej = apply_param_file(mav, param_path)
        not_applied = missing
        rejected = rej
        for _harness_p, _harness_v in (("LOG_DISARMED", 1.0),):
            if _harness_p in reported:
                set_param(mav, _harness_p, _harness_v)

        t_params = vehicle_time_boot_ms(mav)
        append_events(
            timeline_path,
            append_param_digest_events(missing, rej, t_params),
        )

        fi = FaultInjector(mav)
        fi.refresh_param_names(reported)

        def t_now() -> float:
            return vehicle_time_boot_ms(mav)

        for step_name, step_args in _expand_scenario_steps(rule, observe_after_inject_s):
            _exec_step(
                step_name,
                step_args,
                mav=mav,
                fi=fi,
                timeline_path=timeline_path,
                t_now=t_now,
                observe_after_inject_s=observe_after_inject_s,
            )

        poll_mavlink_to_timeline(
            mav,
            out_path=timeline_path,
            duration_s=2.0,
            append=True,
        )
        timeline_jsonl_written = True
    except Exception as exc:  # noqa: BLE001
        harness_error = str(exc)
    finally:
        try:
            sitl.stop()
        except Exception:
            pass

    dataflash = find_latest_dataflash_bin(sitl_work)

    params_from_file = load_param_file(param_path)
    eval_params = reported if reported else params_from_file

    tl_json: Timeline | None = None
    if timeline_jsonl_written and timeline_path.exists():
        tl_json = load_jsonl(timeline_path)
    tl_bin: Timeline | None = None
    if dataflash is not None:
        tl_bin = bin_to_timeline(dataflash, params=eval_params)

    if harness_error:
        rows = [
            Result(
                rule_id=rule.id,
                verdict=Verdict.ERROR,
                reason=f"Harness error: {harness_error}",
            )
        ]
        verdict = Verdict.ERROR
    elif tl_bin is not None and tl_bin.events:
        rows = evaluate_rule(rule=rule, params=eval_params, metadata=meta, timeline=tl_bin)
        verdict = _worst(rows)
    elif tl_json is not None and tl_json.events:
        rows = evaluate_rule(rule=rule, params=eval_params, metadata=meta, timeline=tl_json)
        verdict = _worst(rows)
    else:
        rows = [
            Result(
                rule_id=rule.id,
                verdict=Verdict.ERROR,
                reason="No timeline from SITL (empty or missing JSONL and dataflash).",
            )
        ]
        verdict = Verdict.ERROR

    prov = build_provenance(
        param_path=param_path,
        rule_path=rule_path,
        simulator_speedup=speedup,
        random_seed=seed,
        extra={
            "sitl_instance": instance,
            "mavlink": mavlink_url,
            "not_applied": not_applied,
            "rejected": rejected,
            "file_params_not_applied": not_applied,
            "file_params_rejected": rejected,
            "file_params_sha256": sha256_file(param_path),
        },
    )
    write_result_json(
        run_dir / "result.json",
        rule_id=rule.id,
        results=rows,
        provenance=prov,
        timeline_path=timeline_path if timeline_jsonl_written else None,
        dataflash_path=dataflash,
    )
    write_report_md(
        run_dir / "report.md",
        rule_id=rule.id,
        rule_say=rule.say,
        results=rows,
        provenance=dict(prov),
    )

    return SitlRunResult(
        verdict=verdict,
        reason=rows[-1].reason if rows else "",
        results=rows,
        timeline_jsonl=timeline_path if timeline_jsonl_written else None,
        dataflash_bin=dataflash,
        run_dir=run_dir,
        harness_error=harness_error,
        not_applied=not_applied,
        rejected=rejected,
    )


def append_param_digest_events(
    missing: list[str], rejected: list[str], t_ms: float
) -> list[TimelineEvent]:
    return [
        TimelineEvent(
            t_boot_ms=t_ms,
            type="param_digest",
            payload={"not_applied": missing, "rejected": rejected},
        )
    ]


def _exec_step(
    name: str,
    args: dict[str, Any],
    *,
    mav: mavutil.mavlink_connection,
    fi: FaultInjector,
    timeline_path: Path,
    t_now: Callable[[], float],
    observe_after_inject_s: float,
) -> None:
    if name == "wait_ready":
        deadline = time.monotonic() + float(args.get("timeout_s", 180.0))
        have_gps_fix = False
        have_pos = False
        while time.monotonic() < deadline:
            m = mav.recv_match(
                type=["GPS_RAW_INT", "GLOBAL_POSITION_INT", "EKF_STATUS_REPORT"],
                blocking=False,
            )
            if m is None:
                time.sleep(0.04)
                continue
            if m.get_type() == "GPS_RAW_INT" and int(getattr(m, "fix_type", 0)) >= 3:
                have_gps_fix = True
            if m.get_type() == "GLOBAL_POSITION_INT":
                have_pos = True
            if have_gps_fix and have_pos:
                return
            time.sleep(0.02)
        raise TimeoutError("wait_ready: no GPS fix (3D+) and position estimate in time")

    if name == "set_mode":
        mode = str(args["mode"])
        if not set_mode_apm(mav, mode):
            raise RuntimeError(f"set_mode failed for {mode}")
        poll_mavlink_to_timeline(mav, out_path=timeline_path, duration_s=2.0, append=True)
        return

    if name == "arm":
        ok, code = send_arm_command(mav, arm=True)
        if not ok:
            raise RuntimeError(f"arm not accepted (MAV_RESULT={code})")
        poll_mavlink_to_timeline(mav, out_path=timeline_path, duration_s=3.0, append=True)
        return

    if name == "takeoff":
        alt_m = float(args["alt_m"])
        mav.mav.command_long_send(
            mav.target_system,
            mav.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            alt_m,
        )
        poll_mavlink_to_timeline(mav, out_path=timeline_path, duration_s=25.0, append=True)
        return

    if name == "move_north":
        dist_m = float(args["m"])
        deadline = time.monotonic() + 45.0
        lat_deg: float | None = None
        lon_deg: float | None = None
        alt_m = 0.0
        while time.monotonic() < deadline:
            m = mav.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
            if m is not None:
                lat_deg = float(m.lat) / 1.0e7
                lon_deg = float(m.lon) / 1.0e7
                alt_m = float(m.relative_alt) / 1000.0
                break
            time.sleep(0.05)
        if lat_deg is None or lon_deg is None:
            raise RuntimeError("move_north: no GLOBAL_POSITION_INT")
        dlat = dist_m / 111_320.0
        tgt_lat = lat_deg + dlat
        mav.mav.command_long_send(
            mav.target_system,
            mav.target_component,
            mavutil.mavlink.MAV_CMD_DO_REPOSITION,
            0,
            -1.0,
            0,
            0,
            float(tgt_lat),
            float(lon_deg),
            float(alt_m),
        )
        poll_mavlink_to_timeline(mav, out_path=timeline_path, duration_s=20.0, append=True)
        return

    if name == "hold":
        time.sleep(float(args["seconds"]))
        return

    if name in ("inject", "inject_fault"):
        kind = str(args.get("kind", ""))
        t0 = t_now()
        if "rc_loss" in kind:
            fi.inject_rc_loss()
        elif "battery" in kind:
            fi.inject_battery_low(float(args.get("voltage", 10.0)))
        else:
            raise ValueError(f"unknown inject kind {kind!r}")
        append_events(
            timeline_path,
            [TimelineEvent(t_boot_ms=t0, type="fault_injected", payload={"kind": kind})],
        )
        return

    if name == "observe":
        poll_mavlink_to_timeline(
            mav,
            out_path=timeline_path,
            duration_s=float(args.get("seconds", 1.0)),
            append=True,
        )
        return

    if name == "attempt_arm":
        t0 = t_now()
        mav.mav.command_long_send(
            mav.target_system,
            mav.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1.0,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        poll_mavlink_to_timeline(mav, out_path=timeline_path, duration_s=2.0, append=True)
        for res in drain_ack_results(
            mav, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, timeout_s=1.0
        ):
            append_events(
                timeline_path,
                [
                    TimelineEvent(
                        t_boot_ms=t0,
                        type="command_ack",
                        payload={"command": "ARM_DISARM", "result": res},
                    )
                ],
            )
        poll_mavlink_to_timeline(mav, out_path=timeline_path, duration_s=3.0, append=True)
        return

    raise ValueError(f"unsupported scenario step {name!r}")
