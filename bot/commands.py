"""Обработка входящих сообщений бота: /start и доступ по ключу.

Работает в polling-модели: читаем новые сообщения через getUpdates, регистрируем
подписчиков, отвечаем. Важно для надёжности:
- offset продвигаем ТОЛЬКО за апдейт, ответ на который реально доставлен
  (иначе при сетевом сбое ответ другу терялся бы навсегда);
- API-вызовы с ретраями; 409 (параллельный потребитель) логируем, а не глотаем.
"""
from __future__ import annotations

import html
import logging
import time

import httpx

from .storage import Storage

log = logging.getLogger(__name__)

OFFSET_KEY = "tg_offset"
_TRANSIENT = (429, 500, 502, 503, 504)
_PERMANENT = (400, 401, 403)  # bad request / unauthorized / бот заблокирован — не повторять


def _api(token: str, method: str, *, retries: int = 3, **params) -> dict:
    """Telegram API с ретраями. Возвращает распарсенный JSON или {'ok': False}."""
    last: dict = {"ok": False, "error_code": 0}
    for attempt in range(1, retries + 1):
        try:
            r = httpx.post(
                f"https://api.telegram.org/bot{token}/{method}", data=params, timeout=20
            )
            data = r.json()
            if data.get("ok") or data.get("error_code", 0) not in _TRANSIENT:
                return data            # успех или постоянная ошибка — отдаём сразу
            last = data                # временная ошибка — пробуем ещё
        except Exception as exc:  # noqa: BLE001
            last = {"ok": False, "error_code": 0, "error": str(exc)}
        if attempt < retries:
            time.sleep(1.5 * attempt)
    return last


def _send(token: str, chat_id: str, text: str) -> bool:
    """Отправить сообщение. True — доставлено ИЛИ постоянная ошибка (повторять
    бессмысленно: бот заблокирован и т.п.); False — временный сбой (повторить позже)."""
    resp = _api(token, "sendMessage", chat_id=chat_id, text=text,
                parse_mode="HTML", disable_web_page_preview="true")
    if resp.get("ok"):
        return True
    code = resp.get("error_code", 0)
    if code in _PERMANENT:
        log.warning("sendMessage %s: постоянная ошибка %s — пропускаю", chat_id, code)
        return True
    log.warning("sendMessage %s: временный сбой (%s) — повторю позже", chat_id, resp)
    return False


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


def _handle(token, storage, access_key, owner_chat_id, interval, msg) -> tuple[bool, bool]:
    """Обработать одно сообщение. Возвращает (ok, is_new_sub).

    ok=False только при ВРЕМЕННОМ сбое отправки — тогда апдейт не подтверждаем и
    повторим в следующий раз (чтобы пользователь точно получил ответ).
    """
    chat = msg.get("chat") or {}
    cid = str(chat.get("id") or "")
    if not cid:
        return True, False
    username = chat.get("username") or chat.get("first_name") or "?"
    text = (msg.get("text") or "").strip()

    if text in ("/start", "/help"):
        ok = _send(token, cid, _already(interval) if storage.is_subscriber(cid) else WELCOME)
        return ok, False

    if text in ("/stop", "стоп"):
        ok = _send(token, cid, STOPPED)
        if ok:
            storage.deactivate_subscriber(cid)
        return ok, False

    if access_key and text == access_key:
        already = storage.is_subscriber(cid)
        ok = _send(token, cid, _access_ok(interval))
        if not ok:
            return False, False        # не регистрируем, пока не подтвердили доступ
        storage.add_subscriber(cid, username)
        is_new = not already
        if is_new and owner_chat_id and cid != str(owner_chat_id):
            _send(token, owner_chat_id,
                  f"👤 Новый пользователь: @{html.escape(username)} ({cid})")
        return True, is_new

    return _send(token, cid, ACCESS_HINT), False


def process_updates(
    token: str,
    storage: Storage,
    access_key: str,
    owner_chat_id: str | None,
    interval_minutes: int = 15,
) -> int:
    """Обработать новые сообщения. Возвращает число новых подписчиков."""
    if owner_chat_id:
        storage.add_subscriber(owner_chat_id, "owner")

    offset = int(storage.get_meta(OFFSET_KEY, "0") or "0")
    resp = _api(token, "getUpdates", offset=offset, timeout=0, allowed_updates='["message"]')
    if not resp.get("ok"):
        if resp.get("error_code") == 409:
            log.warning("getUpdates 409 Conflict — параллельный потребитель getUpdates "
                        "(одновременный запуск или вебхук). Пропускаю цикл.")
        else:
            log.warning("getUpdates не ok: %s", resp)
        return 0

    new_subs = 0
    for upd in resp.get("result", []):
        uid = upd.get("update_id", 0)
        ok, is_new = _handle(token, storage, access_key, owner_chat_id,
                             interval_minutes, upd.get("message") or {})
        if not ok:
            # временный сбой отправки — НЕ продвигаем offset, повторим этот апдейт позже
            log.warning("Апдейт %s не обработан (временный сбой) — остаётся в очереди", uid)
            break
        storage.set_meta(OFFSET_KEY, str(uid + 1))   # подтверждаем только доведённый до конца
        if is_new:
            new_subs += 1

    if new_subs:
        log.info("Новых подписчиков: %d", new_subs)
    return new_subs
