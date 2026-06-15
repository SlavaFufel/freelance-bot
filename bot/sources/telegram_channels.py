"""Публичные Telegram-каналы через веб-превью t.me/s/<канал> (Tier 1).

Без логина и без API: t.me/s/<channel> отдаёт HTML с последними постами.
Для закрытых каналов используйте Telethon (см. requirements.txt) — здесь не нужен.
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

# Невидимые символы, которыми каналы часто начинают пост (ломают заголовок).
_ZW = dict.fromkeys(map(ord, "​‌‍﻿⁠\xad"), None)


def _clean(s: str) -> str:
    return (s or "").translate(_ZW).strip()


def _has_letter(s: str) -> bool:
    return any(c.isalpha() for c in s)


def _pick_title(lines: list[str]) -> str:
    """Первая осмысленная строка: пропускаем хештег-строки и строки без букв (эмодзи)."""
    for ln in lines:
        tokens = ln.split()
        if not tokens or all(t.startswith("#") for t in tokens):
            continue
        if not _has_letter(ln):  # строка из одних эмодзи/знаков
            continue
        return ln[:120]
    return lines[0][:120] if lines else "(пост из Telegram)"


class TelegramChannelsSource(Source):
    name = "telegram"

    def __init__(self, cfg: dict):
        self.channels: list[str] = [
            c.lstrip("@") for c in (cfg.get("channels") or [])
        ]
        self.limit = int(cfg.get("limit_per_channel", 20))

    def fetch(self) -> list[Order]:
        orders: list[Order] = []
        for channel in self.channels:
            try:
                orders.extend(self._fetch_channel(channel))
            except Exception as exc:  # noqa: BLE001
                log.warning("telegram канал %r не загрузился: %s", channel, exc)
        log.info("telegram: получено %d постов", len(orders))
        return orders

    def _fetch_channel(self, channel: str) -> list[Order]:
        resp = net.get(f"https://t.me/s/{channel}")
        soup = BeautifulSoup(resp.text, "html.parser")
        out: list[Order] = []

        messages = soup.select(".tgme_widget_message")
        for msg in messages[-self.limit:]:
            post = msg.get("data-post")  # формат "channel/123"
            if not post:
                continue
            text_el = msg.select_one(".tgme_widget_message_text")
            raw = text_el.get_text("\n", strip=True) if text_el else ""
            # чистим zero-width мусор и собираем непустые строки
            lines = [ln for ln in (_clean(ln) for ln in raw.split("\n")) if ln]
            text = "\n".join(lines)
            if not text:
                continue

            title = _pick_title(lines)

            out.append(
                Order(
                    source=f"tg:{channel}",
                    external_id=post,
                    title=title,
                    description=text,
                    url=f"https://t.me/{post}",
                )
            )
        return out


if __name__ == "__main__":  # ручная проверка
    logging.basicConfig(level=logging.INFO)
    import sys

    ch = sys.argv[1] if len(sys.argv) > 1 else "freelancetaverna"
    for o in TelegramChannelsSource({"channels": [ch]}).fetch()[:5]:
        print(f"- {o.title}\n  {o.url}\n  {o.description[:150]}\n")
