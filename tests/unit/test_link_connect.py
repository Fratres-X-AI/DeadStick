from __future__ import annotations

from unittest.mock import patch

from deadstick.sim.link import connect


def test_connect_uses_tcp_prefix_by_default() -> None:
    with patch("deadstick.sim.link.mavutil.mavlink_connection") as mock_mc:
        connect()
        mock_mc.assert_called_once()
        assert mock_mc.call_args[0][0].startswith("tcp:")
