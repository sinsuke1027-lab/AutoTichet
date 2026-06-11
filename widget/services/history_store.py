from __future__ import annotations

import logging
import pathlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime

_DB_PATH = pathlib.Path(__file__).parent.parent / "data" / "history.db"
_MAX_HISTORY = 10


@dataclass
class HistoryEntry:
    task_id: str
    title: str
    project_name: str | None
    created_at: str


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            title TEXT NOT NULL,
            project_name TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def add_history(task_id: str, title: str, project_name: str | None = None) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO history (task_id, title, project_name, created_at) VALUES (?, ?, ?, ?)",
            (task_id, title, project_name, datetime.now().isoformat()),
        )
        conn.execute(
            "DELETE FROM history WHERE id NOT IN "
            "(SELECT id FROM history ORDER BY id DESC LIMIT ?)",
            (_MAX_HISTORY,),
        )
        conn.commit()
    except Exception as exc:
        logging.error("history_store.add_history error: %s", exc)
    finally:
        conn.close()


def get_history() -> list[HistoryEntry]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT task_id, title, project_name, created_at "
            "FROM history ORDER BY id DESC LIMIT ?",
            (_MAX_HISTORY,),
        ).fetchall()
        return [HistoryEntry(r[0], r[1], r[2], r[3]) for r in rows]
    except Exception as exc:
        logging.error("history_store.get_history error: %s", exc)
        return []
    finally:
        conn.close()
