from __future__ import annotations

from pathlib import Path


def test_deadstick_sim_has_no_socket_create_connection(repo_root: Path) -> None:
    sim = repo_root / "deadstick" / "sim"
    for path in sorted(sim.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "socket.create_connection" not in text, f"raw TCP probe in {path.relative_to(repo_root)}"
