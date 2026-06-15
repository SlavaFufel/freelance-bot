"""Обработка входящих сообщений бота: /start и доступ по ключу.

Работает в cron-модели (каждый прогон): читаем новые сообщения через getUpdates,
регистрируем подписчиков, отвечаем. Ответ приходит на следующем прогоне — задержка
до интервала опроса (это нормально для GitHub Actions).
"""
from __future__ import annotations

import html
import logging

import httpx

from .storage import Storage

log = logging.getLogger(__name__)

OFFSET_KEY = "tg_offset"


def _api(token: str, method: str, **params) -> dict:
    r = httpx.post(f"https://api.telegram.org/bot{token}/{method}", data=params, timeout=30)
    return r.json()


def _send(token: str, chat_id: str, text: str) -> None:
    try:
        _api(token, "sendMessage", chat_id=chat_id, text=text,
             parse_mode="HTML", disable_web_page_preview="true")
    except Exception as exc:  # noqa: BLE001
        log.warning("sendMessage %s failed: %s", chat_id, exc)


WELCOME = (
    "👋 <b>Привет!</b>\n\n"
    "Я ищу свежие фриланс-заказы и присылаю их сюда: сайты, доработки, "
    "Telegram-боты, парсеры, автоматизация, Unity.\n\n"
    "🔑 Чтобы начать получать заказы, отправь мне <b>ключ доступа</b> "
    "(его даёт владелец бота)."
)


def _access_ok(interval: int) -> str:
    return (
        "✅ <b>Доступ открыт!</b>\n\n"
        "Теперь буду присылать тебе подходящие заказы.\n"
        f"🔄 Проверяю новые примерно <b>раз в {interval} минут</b> — "
        "первые карточки придут в ближайшее время.\n\n"
        "📦 В каждой карточке: описание заказа, ссылка и готовый <b>промпт для Gemini</b> — "
        "скопируй его, вставь в Gemini, и получишь готовый отклик под заказчика.\n\n"
        "ℹ️ /stop — отписаться."
    )


def _already(interval: int) -> str:
    return (
        "✅ Ты уже подключён — заказы приходят автоматически "
        f"(проверяю раз в ~{interval} минут).\n"
        "ℹ️ /stop — отписаться."
    )


ACCESS_HINT = (
    "🤔 Не узнаю это сообщение.\n"
    "Отправь <b>ключ доступа</b>, который дал владелец бота. "
    "Нет ключа — попроси у того, кто тебя пригласил."
)
STOPPED = (
    "🛑 Окей, больше не присылаю заказы.\n"
    "Чтобы вернуться — отправь ключ доступа снова."
)


def process_updates(
    token: str,
    storage: Storage,
    access_key: str,
    owner_chat_id: str | None,
    interval_minutes: int = 15,
) -> int:
    """Обработать новые сообщения. Возвращает число новых подписчиков."""
    # владелец всегда подписан
    if owner_chat_id:
        storage.add_subscriber(owner_chat_id, "owner")

    offset = int(storage.get_meta(OFFSET_KEY, "0") or "0")
    try:
        resp = _api(token, "getUpdates", offset=offset, timeout=0,
                    allowed_updates='["message"]')
    except Exception as exc:  # noqa: BLE001
        log.warning("getUpdates failed: %s", exc)
        return 0

    if not resp.get("ok"):
        log.warning("getUpdates not ok: %s", resp)
        return 0

    new_subs = 0
    max_update_id = offset
    for upd in resp.get("result", []):
        max_update_id = max(max_update_id, upd.get("update_id", 0))
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        cid = str(chat.get("id") or "")
        if not cid:
            continue
        username = chat.get("username") or chat.get("first_name") or "?"
        text = (msg.get("text") or "").strip()

        if text in ("/start", "/help"):
            _send(token, cid, _already(interval_minutes) if storage.is_subscriber(cid) else WELCOME)
        elif text in ("/stop", "стоп"):
            storage.deactivate_subscriber(cid)
            _send(token, cid, STOPPED)
        elif access_key and text == access_key:
            already = storage.is_subscriber(cid)
            storage.add_subscriber(cid, username)
            _send(token, cid, _access_ok(interval_minutes))
            if not already:
                new_subs += 1
                if owner_chat_id and cid != str(owner_chat_id):
                    _send(token, owner_chat_id,
                          f"👤 Новый пользователь: @{html.escape(username)} ({cid})")
        else:
            _send(token, cid, ACCESS_HINT)

    if max_update_id >= offset:
        storage.set_meta(OFFSET_KEY, str(max_update_id + 1))

    if new_subs:
        log.info("Новых подписчиков: %d", new_subs)
    return new_subs
