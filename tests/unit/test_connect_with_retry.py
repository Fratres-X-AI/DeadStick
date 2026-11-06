from __future__ import annotations

from unittest.mock import MagicMock, patch

from deadstick.sim.link import connect_with_retry


def test_connect_with_retry_succeeds_on_third_mavlink_open() -> None:
    """``mavlink_connection`` fails twice; third opens and returns HEARTBEAT immediately."""
    hb = MagicMock()
    hb.get_type.return_value = "HEARTBEAT"
    conn_ok = MagicMock()
    conn_ok.recv_match.return_value = hb

    with patch("socket.create_connection") as raw_tcp:
        with patch(
            "deadstick.sim.link.mavutil.mavlink_connection",
            side_effect=[ConnectionError("fail"), ConnectionError("fail"), conn_ok],
        ) as mc:
            with patch("deadstick.sim.link.time.sleep"):
                out = connect_with_retry("tcp:127.0.0.1:5760", timeout_s=30.0)
    raw_tcp.assert_not_called()
    assert out is conn_ok
    assert mc.call_count == 3
    conn_ok.close.assert_not_called()
