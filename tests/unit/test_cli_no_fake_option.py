from __future__ import annotations

from typer.testing import CliRunner

from deadstick.cli import app


def test_run_and_sitl_help_have_no_fake_bypass_flag() -> None:
    runner = CliRunner()
    for args in (["run", "--help"], ["sitl-run", "--help"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        combined = result.output.lower()
        assert "fake" not in combined
