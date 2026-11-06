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
        defaults_parm: Path | None = None,
    ) -> None:
        self.arducopter_bin = arducopter_bin
        self.workdir = workdir
        self.model = model
        self.speedup = speedup
        self.tcp_port = tcp_port
        self.defaults_parm = defaults_parm
        self._proc: subprocess.Popen[str] | None = None

    def start(self) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
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
            "0,0,0,0",
            "-I0",
            "--speedup",
            str(self.speedup),
        ]
        if self.defaults_parm is not None:
            cmd.extend(["--defaults", str(self.defaults_parm)])
        # SITL listens on tcp:5760 (+instance offset) for instance 0
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(self.workdir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
