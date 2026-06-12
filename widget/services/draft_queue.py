from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "drafts.db"


@dataclass
class DraftEntry:
    id: int
    payload: dict
    created_at: str
    retry_count: int
    last_error: str | None


class DraftQueue:
    """オフライン時のタスクドラフトを SQLite で管理する。"""

    def __init__(self, db_path: Path = _DEFAULT_DB) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload     TEXT    NOT NULL,
                    created_at  TEXT    NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    last_error  TEXT
                )
            """
            )
            conn.commit()

    def add(self, payload: dict) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO drafts (payload, created_at) VALUES (?, ?)",
                (json.dumps(payload, ensure_ascii=False), now),
            )
            conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def get_pending(self) -> list[DraftEntry]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT id, payload, created_at, retry_count, last_error "
                "FROM drafts ORDER BY id ASC"
            ).fetchall()
        return [
            DraftEntry(
                id=r[0],
                payload=json.loads(r[1]),
                created_at=r[2],
                retry_count=r[3],
                last_error=r[4],
            )
            for r in rows
        ]

    def remove(self, draft_id: int) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            conn.commit()

    def increment_retry(self, draft_id: int, error: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE drafts SET retry_count = retry_count + 1, last_error = ? "
                "WHERE id = ?",
                (error, draft_id),
            )
            conn.commit()
