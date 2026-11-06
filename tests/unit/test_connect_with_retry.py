from __future__ import annotations

from unittest.mock import MagicMock, patch

from deadstick.sim.link import connect_with_retry


def test_connect_with_retry_succeeds_on_third_attempt() -> None:
    """Two connections time out waiting for HEARTBEAT; third succeeds on first recv."""
    sim_time = [0.0]

    def monotonic_mock() -> float:
        return sim_time[0]

    hb = MagicMock()
    hb.get_type.return_value = "HEARTBEAT"

    def recv_until_window_expires(*_a: object, **_kw: object) -> None:
        sim_time[0] += 1.0
        return None

    def recv_heartbeat(*_a: object, **_kw: object) -> MagicMock:
        return hb

    conn_fail = MagicMock()
    conn_fail.recv_match.side_effect = recv_until_window_expires
    conn_ok = MagicMock()
    conn_ok.recv_match.side_effect = recv_heartbeat

    with patch("socket.create_connection") as raw_tcp:
        with patch("deadstick.sim.link.mavutil.mavlink_connection", side_effect=[conn_fail, conn_fail, conn_ok]) as mc:
            with patch("deadstick.sim.link.time.sleep"):
                with patch("deadstick.sim.link.time.monotonic", side_effect=monotonic_mock):
                    out = connect_with_retry("tcp:127.0.0.1:5760", timeout_s=120.0)
    raw_tcp.assert_not_called()
    assert out is conn_ok
    assert mc.call_count == 3
    assert conn_fail.close.call_count == 2
    assert conn_ok.close.call_count == 0
