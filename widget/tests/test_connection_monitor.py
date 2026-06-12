from __future__ import annotations
from unittest.mock import MagicMock, patch
from widget.services.connection_monitor import ConnectionMonitor, ConnectionState


def _make_monitor(callback=None):
    return ConnectionMonitor(
        url="http://localhost:8000",
        on_state_change=callback or (lambda s: None),
    )


def test_check_returns_connected_on_fast_200():
    monitor = _make_monitor()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("widget.services.connection_monitor.httpx.get", return_value=mock_resp):
        with patch("widget.services.connection_monitor.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.5]  # 0.5秒 < 2秒閾値
            result = monitor._check()
    assert result == ConnectionState.CONNECTED


def test_check_returns_degraded_on_slow_200():
    monitor = _make_monitor()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("widget.services.connection_monitor.httpx.get", return_value=mock_resp):
        with patch("widget.services.connection_monitor.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 3.0]  # 3秒 > 2秒閾値
            result = monitor._check()
    assert result == ConnectionState.DEGRADED


def test_check_returns_disconnected_on_exception():
    monitor = _make_monitor()
    with patch(
        "widget.services.connection_monitor.httpx.get",
        side_effect=Exception("connection refused"),
    ):
        result = monitor._check()
    assert result == ConnectionState.DISCONNECTED


def test_callback_fires_on_state_change():
    states: list[ConnectionState] = []
    monitor = _make_monitor(callback=states.append)
    monitor._state = ConnectionState.CONNECTED

    with patch(
        "widget.services.connection_monitor.httpx.get",
        side_effect=Exception("down"),
    ):
        monitor._check_and_notify()

    assert states == [ConnectionState.DISCONNECTED]


def test_callback_not_fired_when_state_unchanged():
    states: list[ConnectionState] = []
    monitor = _make_monitor(callback=states.append)
    monitor._state = ConnectionState.DISCONNECTED  # 既に DISCONNECTED

    with patch(
        "widget.services.connection_monitor.httpx.get",
        side_effect=Exception("still down"),
    ):
        monitor._check_and_notify()

    assert states == []  # 変化なし → コールバックなし


def test_next_interval_degraded_uses_connected_interval():
    # DEGRADED は「接続中」扱いなのでポーリング間隔も接続時の長い方を使う（issue #34）
    monitor = ConnectionMonitor(
        url="http://localhost:8000",
        on_state_change=lambda s: None,
        check_interval_connected=30.0,
        check_interval_disconnected=10.0,
    )
    monitor._state = ConnectionState.CONNECTED
    assert monitor._next_interval() == 30.0
    monitor._state = ConnectionState.DEGRADED
    assert monitor._next_interval() == 30.0
    monitor._state = ConnectionState.DISCONNECTED
    assert monitor._next_interval() == 10.0


def test_is_connected_true_for_connected_and_degraded():
    monitor = _make_monitor()
    monitor._state = ConnectionState.CONNECTED
    assert monitor.is_connected() is True
    monitor._state = ConnectionState.DEGRADED
    assert monitor.is_connected() is True
    monitor._state = ConnectionState.DISCONNECTED
    assert monitor.is_connected() is False
