from __future__ import annotations
import threading
import time
from enum import Enum
from typing import Callable

import httpx


class ConnectionState(Enum):
    CONNECTED    = "connected"
    DEGRADED     = "degraded"
    DISCONNECTED = "disconnected"


class ConnectionMonitor:
    """バックグラウンドスレッドでバックエンドの接続状態を定期チェックする。"""

    def __init__(
        self,
        url: str,
        on_state_change: Callable[[ConnectionState], None],
        check_interval_connected: float = 30.0,
        check_interval_disconnected: float = 10.0,
        degraded_threshold: float = 2.0,
    ) -> None:
        self._url = url
        self._on_state_change = on_state_change
        self._interval_connected = check_interval_connected
        self._interval_disconnected = check_interval_disconnected
        self._degraded_threshold = degraded_threshold
        self._state = ConnectionState.DISCONNECTED
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def state(self) -> ConnectionState:
        return self._state

    def is_connected(self) -> bool:
        return self._state in (ConnectionState.CONNECTED, ConnectionState.DEGRADED)

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _check(self) -> ConnectionState:
        try:
            start = time.monotonic()
            resp = httpx.get(f"{self._url}/health", timeout=5.0)
            elapsed = time.monotonic() - start
            if resp.status_code == 200:
                if elapsed > self._degraded_threshold:
                    return ConnectionState.DEGRADED
                return ConnectionState.CONNECTED
        except Exception:
            pass
        return ConnectionState.DISCONNECTED

    def _check_and_notify(self) -> None:
        new_state = self._check()
        if new_state != self._state:
            self._state = new_state
            self._on_state_change(new_state)

    def _next_interval(self) -> float:
        # DEGRADED も「接続中」扱いとし、接続時の長いポーリング間隔を使う（issue #34）
        if self._state in (ConnectionState.CONNECTED, ConnectionState.DEGRADED):
            return self._interval_connected
        return self._interval_disconnected

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._check_and_notify()
            self._stop_event.wait(self._next_interval())
