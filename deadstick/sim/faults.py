from __future__ import annotations

from pymavlink import mavutil

from deadstick.sim.link import set_param


class FaultInjector:
    """SITL fault parameters — names verified against live param list when possible."""

    def __init__(self, mav: mavutil.mavlink_connection) -> None:
        self.mav = mav
        self._names: set[str] = set()

    def refresh_param_names(self, params: dict[str, float]) -> None:
        self._names = set(params.keys())

    def _require(self, name: str) -> None:
        if self._names and name not in self._names:
            raise KeyError(f"Simulator has no parameter {name!r} (check SITL build).")

    def inject_rc_loss(self) -> None:
        name = "SIM_RC_FAIL"
        self._require(name)
        if not set_param(self.mav, name, 1.0):
            raise RuntimeError(f"Failed to set {name}")

    def clear_rc_loss(self) -> None:
        name = "SIM_RC_FAIL"
        self._require(name)
        set_param(self.mav, name, 0.0)

    def inject_battery_low(self, voltage: float = 10.0) -> None:
        name = "SIM_BATT_VOLTAGE"
        self._require(name)
        if not set_param(self.mav, name, float(voltage)):
            raise RuntimeError(f"Failed to set {name}")
