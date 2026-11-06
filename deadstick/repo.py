from __future__ import annotations

from pathlib import Path

# DeadStick package lives at <repo>/deadstick/ — repo root is one level up.
REPO_ROOT: Path = Path(__file__).resolve().parents[1]

# ArduPilot autotest default params for SITL Copter (relative to REPO_ROOT).
DEFAULT_COPTER_SITL_DEFAULTS: Path = Path("ardupilot/Tools/autotest/default_params/copter.parm")


def resolve_sitl_defaults_parm(explicit: Path | None) -> Path:
    """Resolve the ``--defaults`` .parm file for SITL.

    When *explicit* is ``None``, use ``ardupilot/Tools/autotest/default_params/copter.parm``
    under the DeadStick repo root. If that file does not exist, raise ``FileNotFoundError``.
    """
    if explicit is not None:
        p = explicit.expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"SITL --defaults not found: {p}")
        return p.resolve()
    p = (REPO_ROOT / DEFAULT_COPTER_SITL_DEFAULTS).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"SITL defaults not found at {p}")
    return p
