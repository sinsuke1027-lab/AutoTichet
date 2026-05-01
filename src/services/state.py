from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

DB_PATH = Path("data/processed.db")


async def init_db() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                message_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                processed_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def is_processed(message_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?",
            (message_id,),
        )
        return await cursor.fetchone() is not None


async def mark_processed(message_id: str, source_type: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO processed_messages VALUES (?, ?, ?)",
            (message_id, source_type, datetime.now(UTC).isoformat()),
        )
        await db.commit()


async def unmark_processed(message_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM processed_messages WHERE message_id = ?",
            (message_id,),
        )
        await db.commit()
