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
