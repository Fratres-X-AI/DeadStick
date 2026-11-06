from __future__ import annotations

import math
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
from deadstick.repo import resolve_sitl_defaults_parm
from deadstick.report.json_report import write_result_json
from deadstick.report.md_report import write_report_md
from deadstick.rules.loader import load_rule
from deadstick.rules.schema import RuleFile
from deadstick.sim.dataflash_log import find_latest_dataflash_bin
from deadstick.sim.faults import FaultInjector
from deadstick.sim.link import (
    apply_param_file,
    connect_with_retry,
    drain_ack_results,
    reboot_and_reconnect,
    send_arm_command,
    set_mode_apm,
    set_param,
    vehicle_time_boot_ms,
)
from deadstick.sim.sitl import SitlProcess
from deadstick.timeline.dataflash import bin_to_timeline
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


def _haversine_m(lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float) -> float:
    r_earth = 6371000.0
    p1 = math.radians(lat1_deg)
    p2 = math.radians(lat2_deg)
    dlat = math.radians(lat2_deg - lat1_deg)
    dlon = math.radians(lon2_deg - lon1_deg)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return r_earth * c


def _worst(rows: list[Result]) -> Verdict:
    order = [Verdict.PASS, Verdict.CANNOT_JUDGE, Verdict.FAIL, Verdict.ERROR]
    worst = Verdict.PASS
    for r in rows:
        if order.index(r.verdict) > order.index(worst):
            worst = r.verdict
    return worst


def evaluate_run_artifacts(
    *,
    rule: RuleFile,
    metadata: dict[str, Any],
    vehicle_params: dict[str, float],
    file_params: dict[str, float],
    dataflash_path: Path | None,
    timeline_jsonl_path: Path | None,
    harness_error: str | None,
) -> tuple[Verdict, list[Result]]:
    eval_params = vehicle_params if vehicle_params else file_params
    tl_bin: Timeline | None = None
    if dataflash_path is not None:
        tl_bin = bin_to_timeline(dataflash_path, params=eval_params)

    if harness_error:
        rows = [
            Result(
                rule_id=rule.id,
                verdict=Verdict.ERROR,
                reason=f"Harness error: {harness_error}",
            )
        ]
        return Verdict.ERROR, rows

    if dataflash_path is None or tl_bin is None or not tl_bin.events:
        rows = [
            Result(
                rule_id=rule.id,
                verdict=Verdict.ERROR,
                reason="no dataflash log produced",
            )
        ]
        return Verdict.ERROR, rows

    rows = evaluate_rule(rule=rule, params=eval_params, metadata=metadata, timeline=tl_bin)
    return _worst(rows), rows


def _prelude_for_inject_kind(kind: str) -> list[tuple[str, dict[str, Any]]]:
    k = kind.lower()
    if "rc_loss_while_disarmed" in k:
        return [("wait_ready", {"timeout_s": 180.0})]
    if "rc_loss_in_air" in k or "battery" in k:
        return [
            ("wait_ready", {"timeout_s": 180.0}),
            ("set_mode", {"mode": "GUIDED"}),
            ("arm", {}),
            ("takeoff", {"alt_m": 20.0}),
            ("move_north", {"m": 100.0}),
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
    _allow_fake_metadata_for_tests: bool = False,
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
    if not _allow_fake_metadata_for_tests:
        assert_not_fake_metadata(metadata_path, meta)

    tcp_port = tcp_base_port + int(instance) * 10
    mavlink_url = f"tcp:127.0.0.1:{tcp_port}"

    harness_error: str | None = None
    sitl: SitlProcess | None = None
    defaults_resolved: Path | None = None
    timeline_jsonl_written = False
    dataflash: Path | None = None
    not_applied: list[str] = []
    rejected: list[str] = []
    reported: dict[str, float] = {}

    try:
        try:
            defaults_resolved = resolve_sitl_defaults_parm(defaults_parm)
        except FileNotFoundError as exc:
            harness_error = str(exc)
            raise
        sitl = SitlProcess(
            arducopter_bin=arducopter_bin,
            workdir=sitl_work,
            speedup=speedup,
            tcp_port=tcp_port,
            instance=int(instance),
            defaults_parm=defaults_resolved,
        )
        if timeline_path.exists():
            timeline_path.unlink()
        sitl.start()
        mav = connect_with_retry(mavlink_url)

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
        if sitl is not None:
            try:
                sitl.stop()
            except Exception:
                pass

    dataflash = find_latest_dataflash_bin(sitl_work)
    params_from_file = load_param_file(param_path)
    verdict, rows = evaluate_run_artifacts(
        rule=rule,
        metadata=meta,
        vehicle_params=reported,
        file_params=params_from_file,
        dataflash_path=dataflash,
        timeline_jsonl_path=timeline_path if timeline_jsonl_written else None,
        harness_error=harness_error,
    )

    extra_prov: dict[str, Any] = {
        "sitl_instance": instance,
        "mavlink": mavlink_url,
        "not_applied": not_applied,
        "rejected": rejected,
        "file_params_not_applied": not_applied,
        "file_params_rejected": rejected,
        "file_params_sha256": sha256_file(param_path),
    }
    if defaults_resolved is not None:
        extra_prov["sitl_defaults_file"] = str(defaults_resolved)
        extra_prov["sitl_defaults_sha256"] = sha256_file(defaults_resolved)
    prov = build_provenance(
        param_path=param_path,
        rule_path=rule_path,
        simulator_speedup=speedup,
        random_seed=seed,
        extra=extra_prov,
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


def _assert_preflight_in_air_fault(mav: mavutil.mavlink_connection) -> None:
    """Armed, GUIDED, and enough relative altitude before RC/battery inject."""
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        hb = mav.recv_match(type="HEARTBEAT", blocking=False)
        gp = mav.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
        if hb is None or gp is None:
            time.sleep(0.04)
            continue
        armed = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        mapping = mav.mode_mapping()
        mode_name = ""
        if mapping:
            want = hb.custom_mode
            for nm, num in mapping.items():
                if int(num) == int(want):
                    mode_name = str(nm)
                    break
        guided = mode_name.upper() == "GUIDED"
        rel_m = float(gp.relative_alt) / 1000.0
        if armed and guided and rel_m + 1e-6 >= 15.0:
            return
        time.sleep(0.02)
    raise RuntimeError("precondition for in-flight fault not reached (armed/GUIDED/15m not confirmed)")


def _probe_armable_before_r01_fault(mav: mavutil.mavlink_connection) -> None:
    """
    r01 needs the vehicle armable (GPS/EKF ready) before RC loss; otherwise any
    PreArm refusal could be misread as radio-gating.
    """
    ok_arm, _code = send_arm_command(mav, arm=True, timeout_s=10.0)
    if ok_arm:
        send_arm_command(mav, arm=False, timeout_s=10.0)
        return

    lines: list[str] = []
    t_end = time.monotonic() + 4.0
    while time.monotonic() < t_end:
        m = mav.recv_match(type=["STATUSTEXT"], blocking=False)
        if m is not None:
            text = str(getattr(m, "text", "") or "")
            if text.strip():
                lines.append(text)
        else:
            time.sleep(0.05)
    snippet = " | ".join(lines[-12:]) if lines else "no STATUSTEXT"
    raise RuntimeError(
        "vehicle not armable before fault; cannot test r01. "
        f"Recorded statustext: {snippet}"
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
        deadline = time.monotonic() + 15.0
        start_lat: float | None = None
        start_lon: float | None = None
        cur_lat: float | None = None
        cur_lon: float | None = None
        while time.monotonic() < deadline:
            gp = mav.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
            if gp is not None:
                start_lat = float(gp.lat) / 1.0e7
                start_lon = float(gp.lon) / 1.0e7
                break
            time.sleep(0.05)
        if start_lat is None or start_lon is None:
            raise RuntimeError("move_north: no GLOBAL_POSITION_INT for start")
        dlat = dist_m / 111_320.0
        tgt_lat = start_lat + dlat
        tgt_lon = start_lon
        alt_m = 20.0
        mav.mav.command_int_send(
            mav.target_system,
            mav.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            mavutil.mavlink.MAV_CMD_DO_REPOSITION,
            0,
            0,
            -1.0,
            0,
            0,
            int(round(tgt_lat * 1.0e7)),
            int(round(tgt_lon * 1.0e7)),
            alt_m,
        )
        poll_mavlink_to_timeline(mav, out_path=timeline_path, duration_s=3.0, append=True)

        arrive_deadline = time.monotonic() + 60.0
        while time.monotonic() < arrive_deadline:
            gp = mav.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
            if gp is not None:
                cur_lat = float(gp.lat) / 1.0e7
                cur_lon = float(gp.lon) / 1.0e7
                rel_alt = float(gp.relative_alt) / 1000.0
                horiz = _haversine_m(start_lat, start_lon, cur_lat, cur_lon)
                if horiz + 0.5 >= 90.0 and 15.0 - 0.5 <= rel_alt <= 25.0 + 0.5:
                    poll_mavlink_to_timeline(mav, out_path=timeline_path, duration_s=2.0, append=True)
                    return
            time.sleep(0.05)
        raise RuntimeError("reposition not reached")

    if name == "hold":
        time.sleep(float(args["seconds"]))
        return

    if name in ("inject", "inject_fault"):
        kind = str(args.get("kind", ""))
        kl = kind.lower()
        if "rc_loss_while_disarmed" in kl:
            _probe_armable_before_r01_fault(mav)
        elif "rc_loss_in_air" in kl or "battery" in kl:
            _assert_preflight_in_air_fault(mav)
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
