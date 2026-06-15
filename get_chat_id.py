"""Помощник: показывает username бота и твой chat_id.

Как пользоваться:
  1) открой своего бота в Telegram (его @username покажет этот скрипт),
  2) нажми Start и отправь боту любое сообщение,
  3) запусти:  python get_chat_id.py
Скрипт найдёт chat_id и предложит вписать его в .env.
"""
from __future__ import annotations

import re
from pathlib import Path

import httpx

from bot.config import ROOT, load_config

cfg = load_config()
token = cfg.secrets.telegram_bot_token
if not token:
    raise SystemExit("В .env пуст TELEGRAM_BOT_TOKEN — впиши токен от @BotFather.")

base = f"https://api.telegram.org/bot{token}"

me = httpx.get(f"{base}/getMe", timeout=20).json()
if not me.get("ok"):
    raise SystemExit(f"Токен не принят Telegram: {me}")
bot_username = me["result"]["username"]
print(f"✓ Бот найден: @{bot_username}")

upd = httpx.get(f"{base}/getUpdates", timeout=20).json()
chats: dict[int, str] = {}
for u in upd.get("result", []):
    msg = u.get("message") or u.get("edited_message") or u.get("channel_post") or {}
    chat = msg.get("chat") or {}
    cid = chat.get("id")
    if cid is not None:
        who = chat.get("username") or chat.get("first_name") or chat.get("title") or "?"
        chats[cid] = who

if not chats:
    print(
        f"\n⚠ Сообщений не найдено.\n"
        f"  1) Открой в Telegram: https://t.me/{bot_username}\n"
        f"  2) Нажми Start и напиши боту любое сообщение.\n"
        f"  3) Запусти этот скрипт снова: python get_chat_id.py"
    )
    raise SystemExit(0)

print("\nНайденные чаты (id — кто):")
for cid, who in chats.items():
    print(f"  {cid}  —  {who}")

chat_id = next(iter(chats))
env_path = Path(ROOT) / ".env"
text = env_path.read_text(encoding="utf-8")
new = re.sub(r"(?m)^TELEGRAM_CHAT_ID=.*$", f"TELEGRAM_CHAT_ID={chat_id}", text)
env_path.write_text(new, encoding="utf-8")
print(f"\n✓ Записал TELEGRAM_CHAT_ID={chat_id} в .env")
print("Готово! Теперь можно запускать:  python run.py --once")
