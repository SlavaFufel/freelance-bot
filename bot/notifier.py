"""Доставка найденных заказов: Telegram-бот (и консоль для dry-run)."""
from __future__ import annotations

import html
import logging

import httpx

from .matcher import MatchResult
from .models import Order

log = logging.getLogger(__name__)

TG_LIMIT = 4096          # лимит длины сообщения Telegram
DESC_LIMIT = 600         # сколько символов описания показывать


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_card(order: Order, result: MatchResult, response: str, is_prompt: bool = False) -> str:
    """Карточка заказа для Telegram (HTML parse_mode)."""
    e = html.escape
    budget = order.budget or "не указан"
    desc = _truncate(order.description, DESC_LIMIT)

    parts = [
        f"🔔 <b>{e(order.title)}</b>",
        f"🏷 {e(order.source)}  ·  💰 {e(budget)}  ·  ⭐ {result.score}",
        f"🔗 {e(order.url)}",
    ]
    if desc:
        parts.append(f"\n{e(desc)}")
    if is_prompt:
        parts.append("\n🤖 <b>Промпт для Gemini</b> (скопируй и вставь в Gemini — он напишет отклик):")
    else:
        parts.append("\n📝 <b>Черновик отклика</b> (скопируй и проверь перед отправкой):")
    parts.append(f"<pre>{e(response)}</pre>")

    text = "\n".join(parts)
    return _truncate(text, TG_LIMIT)


class TelegramNotifier:
    def __init__(self, token: str, chat_ids: str | list[str], is_prompt: bool = False):
        if isinstance(chat_ids, str):
            chat_ids = [chat_ids]
        chat_ids = [str(c) for c in chat_ids if c]
        if not token or not chat_ids:
            raise ValueError(
                "Не задан TELEGRAM_BOT_TOKEN или нет получателей (chat_id/подписчиков)"
            )
        self.token = token
        self.chat_ids = chat_ids
        self.is_prompt = is_prompt
        self.api = f"https://api.telegram.org/bot{token}/sendMessage"

    def _send_one(self, chat_id: str, text: str) -> bool:
        try:
            resp = httpx.post(
                self.api,
                data={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "false",
                },
                timeout=20.0,
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                return True
            log.error("Telegram sendMessage %s failed: %s %s", chat_id, resp.status_code, resp.text)
            return False
        except Exception as exc:  # noqa: BLE001
            log.error("Telegram sendMessage %s error: %s", chat_id, exc)
            return False

    def send(self, order: Order, result: MatchResult, response: str) -> bool:
        """Отправить карточку всем получателям. True, если дошло хотя бы одному."""
        text = format_card(order, result, response, self.is_prompt)
        ok_any = False
        for chat_id in self.chat_ids:
            if self._send_one(chat_id, text):
                ok_any = True
        return ok_any


class ConsoleNotifier:
    """Для --dry-run: печатает карточку в stdout, ничего не отправляет."""

    def __init__(self, is_prompt: bool = False):
        self.is_prompt = is_prompt

    def send(self, order: Order, result: MatchResult, response: str) -> bool:
        print("=" * 70)
        print(f"[{order.source}] {order.title}  (score={result.score})")
        print(f"URL: {order.url}")
        print(f"Бюджет: {order.budget or 'не указан'}")
        if order.description:
            print(f"\n{_truncate(order.description, DESC_LIMIT)}")
        print("\n--- промпт для Gemini ---" if self.is_prompt else "\n--- черновик отклика ---")
        print(response)
        print("=" * 70)
        return True
