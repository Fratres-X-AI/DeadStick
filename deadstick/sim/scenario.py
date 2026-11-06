from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pymavlink import mavutil

from deadstick.rules.schema import RuleFile
from deadstick.timeline.model import TimelineEvent
from deadstick.timeline.recorder import append_events, record_mavlink_to_jsonl
from deadstick.sim.faults import FaultInjector
from deadstick.sim.link import apply_param_file, connect, fetch_all_params, wait_heartbeat


@dataclass
class ScenarioResult:
    timeline_path: Path
    dataflash_path: Path | None
    verdict_phase: str
    error: str | None = None
    params_reported: dict[str, float] = field(default_factory=dict)
    not_applied: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


def _find_inject_step(rule: RuleFile) -> tuple[str, dict[str, Any]] | None:
    for st in rule.scenario:
        if st.step in ("inject", "inject_fault"):
            return st.step, st.args
    return None


def run_rule_scenario_stub(
    *,
    rule: RuleFile,
    param_path: Path,
    results_dir: Path,
    arducopter_bin: Path,
    defaults_parm: Path | None = None,
    speedup: float = 1.0,
    observe_s: float = 8.0,
) -> ScenarioResult:
    """
    Minimal harness: start SITL, connect, apply params, inject fault from rule,
    record MAVLink JSONL. Full flight script (takeoff/GUIDED) is phase-3 extended.
    """
    from deadstick.sim.sitl import SitlProcess

    run_id = f"{rule.id}_stub"
    sitl_dir = results_dir / run_id / "sitl"
    timeline_path = results_dir / run_id / "timeline.jsonl"
    sitl_dir.mkdir(parents=True, exist_ok=True)
    if timeline_path.exists():
        timeline_path.unlink()

    sitl = SitlProcess(
        arducopter_bin=arducopter_bin,
        workdir=sitl_dir,
        speedup=speedup,
        defaults_parm=defaults_parm,
    )
    inj = _find_inject_step(rule)
    try:
        sitl.start()
        mav = connect()
        wait_heartbeat(mav)
        reported, missing, rejected = apply_param_file(mav, param_path)
        fi = FaultInjector(mav)
        fi.refresh_param_names(reported)
        if inj:
            kind = inj[1].get("kind", "")
            t_boot = 0.0
            m = mav.recv_match(blocking=False)
            if m is not None and getattr(m, "time_boot_ms", None) is not None:
                t_boot = float(m.time_boot_ms)
            try:
                if "rc_loss" in kind:
                    fi.inject_rc_loss()
                elif "battery" in kind:
                    fi.inject_battery_low()
                else:
                    raise ValueError(f"Unknown inject kind {kind!r}")
            except Exception as exc:  # noqa: BLE001
                return ScenarioResult(
                    timeline_path=timeline_path,
                    dataflash_path=None,
                    verdict_phase="ERROR",
                    error=str(exc),
                    params_reported=reported,
                    not_applied=missing,
                    rejected=rejected,
                )
            append_events(
                timeline_path,
                [
                    TimelineEvent(
                        t_boot_ms=t_boot,
                        type="fault_injected",
                        payload={"kind": kind},
                    )
                ],
            )
        record_mavlink_to_jsonl(
            mav, out_path=timeline_path, duration_s=observe_s, append=timeline_path.exists()
        )
        return ScenarioResult(
            timeline_path=timeline_path,
            dataflash_path=None,
            verdict_phase="OK",
            params_reported=reported,
            not_applied=missing,
            rejected=rejected,
        )
    finally:
        sitl.stop()
