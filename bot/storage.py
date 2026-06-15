"""SQLite-хранилище для дедупа: какие заказы уже обработаны/отправлены."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import sqlite3

from .models import Order


class Storage:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
                source       TEXT NOT NULL,
                external_id  TEXT NOT NULL,
                title        TEXT,
                url          TEXT,
                score        REAL,
                notified     INTEGER NOT NULL DEFAULT 0,
                processed_at TEXT NOT NULL,
                PRIMARY KEY (source, external_id)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id   TEXT PRIMARY KEY,
                username  TEXT,
                joined_at TEXT NOT NULL,
                active    INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        self.conn.commit()

    # --- подписчики (многопользовательский режим) ---
    def add_subscriber(self, chat_id: str, username: str | None) -> None:
        self.conn.execute(
            """
            INSERT INTO subscribers (chat_id, username, joined_at, active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET active = 1, username = excluded.username
            """,
            (str(chat_id), username, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def deactivate_subscriber(self, chat_id: str) -> None:
        self.conn.execute(
            "UPDATE subscribers SET active = 0 WHERE chat_id = ?", (str(chat_id),)
        )
        self.conn.commit()

    def is_subscriber(self, chat_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM subscribers WHERE chat_id = ? AND active = 1", (str(chat_id),)
        )
        return cur.fetchone() is not None

    def active_subscribers(self) -> list[str]:
        cur = self.conn.execute(
            "SELECT chat_id FROM subscribers WHERE active = 1 ORDER BY joined_at"
        )
        return [row["chat_id"] for row in cur.fetchall()]

    # --- произвольные пары ключ/значение (offset getUpdates и т.п.) ---
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        cur = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    def is_seen(self, source: str, external_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM seen WHERE source = ? AND external_id = ?",
            (source, external_id),
        )
        return cur.fetchone() is not None

    def mark_seen(self, order: Order, score: float, notified: bool) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO seen
                (source, external_id, title, url, score, notified, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.source,
                order.external_id,
                order.title,
                order.url,
                score,
                1 if notified else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
