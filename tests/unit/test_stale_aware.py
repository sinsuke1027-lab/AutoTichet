"""stale-tasks の datetime aware 正規化テスト（issue #19）

SQLite は timezone 情報を落として naive な datetime を返すことがあり、
aware な now との減算で TypeError → 500 になる。_ensure_aware で吸収する。
"""

from datetime import UTC, datetime

from src.api.routers.dashboard import _ensure_aware


def test_naive_datetime_becomes_aware_utc() -> None:
    naive = datetime(2026, 6, 1, 12, 0, 0)
    result = _ensure_aware(naive)
    assert result.tzinfo is not None
    assert result.utcoffset().total_seconds() == 0


def test_aware_datetime_is_unchanged() -> None:
    aware = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    assert _ensure_aware(aware) == aware


def test_subtraction_with_naive_does_not_raise() -> None:
    now = datetime.now(UTC)
    naive_past = datetime(2026, 1, 1, 0, 0, 0)
    # 正規化すれば aware - aware で例外なく days を計算できる
    days = (now - _ensure_aware(naive_past)).days
    assert days >= 0
