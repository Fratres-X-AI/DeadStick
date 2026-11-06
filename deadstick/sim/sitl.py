from __future__ import annotations

import signal
import subprocess
from pathlib import Path
from typing import IO


class SitlProcess:
    """Runs `arducopter` SITL with an isolated working directory."""

    def __init__(
        self,
        *,
        arducopter_bin: Path,
        workdir: Path,
        model: str = "quad",
        speedup: float = 1.0,
        tcp_port: int = 5760,
        instance: int = 0,
        defaults_parm: Path,
        home: str = "-35.363261,149.165230,584,353",
    ) -> None:
        self.arducopter_bin = arducopter_bin
        self.workdir = workdir
        self.model = model
        self.speedup = speedup
        self.tcp_port = tcp_port
        self.instance = int(instance)
        self.defaults_parm = defaults_parm
        self.home = home
        self._proc: subprocess.Popen[str] | None = None
        self._log_f: IO[str] | None = None

    def start(self) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        log_path = self.workdir / "sitl.log"
        self._log_f = log_path.open("w", encoding="utf-8")
        log_f = self._log_f
        for stale in ("eeprom.bin", "terrain"):
            p = self.workdir / stale
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                pass
        cmd: list[str] = [
            str(self.arducopter_bin),
            "--model",
            self.model,
            "--home",
            self.home,
            f"-I{self.instance}",
            "--speedup",
            str(self.speedup),
        ]
        cmd.extend(["--defaults", str(self.defaults_parm)])
        # SITL SERIAL0 is tcp:5760 + instance*10 (see ArduPilot SITL).
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(self.workdir),
            stdout=log_f,
            stderr=subprocess.STDOUT,
            text=True,
        )
        # Do not open a raw TCP probe here: SITL treats that as a connect+hangup and
        # breaks the real MAVLink client's first connection. The harness connects via
        # ``connect_with_retry`` in link.py.

    def stop(self) -> None:
        if self._proc is None:
            return
        self._proc.send_signal(signal.SIGTERM)
        try:
            self._proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None
        if self._log_f is not None:
            try:
                self._log_f.close()
            except Exception:
                pass
            self._log_f = None
