from __future__ import annotations

from unittest.mock import MagicMock, patch

from deadstick.sim.link import connect_with_retry


def test_connect_with_retry_retries_only_until_open_then_waits_for_delayed_heartbeat() -> None:
    """Two connection failures (port not up), then open; heartbeat arrives after delay — same socket."""
    hb = MagicMock()
    hb.get_type.return_value = "HEARTBEAT"
    conn = MagicMock()
    recv_calls = {"n": 0}

    def recv_side_effect(*_a: object, **_kw: object):
        recv_calls["n"] += 1
        if recv_calls["n"] < 8:
            return None
        return hb

    conn.recv_match.side_effect = recv_side_effect

    refused = ConnectionRefusedError(111, "Connection refused")

    with patch("socket.create_connection") as raw_tcp:
        with patch(
            "deadstick.sim.link.mavutil.mavlink_connection",
            side_effect=[refused, refused, conn],
        ) as mc:
            with patch("deadstick.sim.link.time.sleep"):
                out = connect_with_retry("tcp:127.0.0.1:5760", timeout_s=90.0)
    raw_tcp.assert_not_called()
    assert out is conn
    assert mc.call_count == 3
    conn.close.assert_not_called()
