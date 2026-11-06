from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import IO


def wait_tcp_open(host: str, port: int, timeout_s: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            s = socket.create_connection((host, port), timeout=1.0)
            s.close()
            return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"TCP {host}:{port} did not open within {timeout_s}s")


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
        defaults_parm: Path | None = None,
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
        if self.defaults_parm is not None:
            cmd.extend(["--defaults", str(self.defaults_parm)])
        # SITL SERIAL0 is tcp:5760 + instance*10 (see ArduPilot SITL).
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(self.workdir),
            stdout=log_f,
            stderr=subprocess.STDOUT,
            text=True,
        )
        wait_tcp_open("127.0.0.1", self.tcp_port, timeout_s=90.0)

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
