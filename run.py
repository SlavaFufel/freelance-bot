"""Точка входа: собирает компоненты и крутит polling-цикл.

Примеры:
    python run.py --once --dry-run     # один прогон, вывод в консоль (без Telegram)
    python run.py --once               # один прогон с отправкой в Telegram
    python run.py                      # бесконечный цикл (Ctrl+C для остановки)
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from bot.config import load_config
from bot.matcher import Matcher
from bot.notifier import ConsoleNotifier, TelegramNotifier
from bot.pipeline import Pipeline
from bot.responder import Responder
from bot.sources import build_sources
from bot.storage import Storage

ROOT = Path(__file__).resolve().parent


def build_pipeline(cfg, dry_run: bool) -> Pipeline:
    sources = build_sources(cfg)
    if not sources:
        logging.warning("Нет активных источников — проверь enabled_sources в config.yaml")

    matcher = Matcher(cfg.match)
    responder = Responder(cfg.responder)
    storage = Storage(ROOT / "freelance_bot.db")

    if dry_run:
        notifier = ConsoleNotifier(is_prompt=responder.is_prompt)
        return Pipeline(sources, matcher, responder, notifier, storage)

    token = cfg.secrets.telegram_bot_token
    owner = cfg.secrets.telegram_chat_id

    # Получатели заказов. В multi_user — все активные подписчики + владелец.
    # Регистрацией подписчиков занимается отдельный путь `--commands` (раз в минуту),
    # поэтому здесь getUpdates НЕ дёргаем (иначе два потребителя → 409). Список
    # получателей НЕ зависит от наличия ACCESS_KEY (ключ нужен лишь для регистрации).
    if cfg.multi_user:
        recipients = storage.active_subscribers()
        if owner and owner not in recipients:
            recipients.insert(0, owner)
    else:
        recipients = [owner] if owner else []

    if not recipients:
        logging.warning("Нет получателей (ни владельца, ни подписчиков) — карточки не отправляются")
        return Pipeline(sources, matcher, responder,
                        ConsoleNotifier(is_prompt=responder.is_prompt), storage)

    logging.info("Получателей: %d", len(recipients))
    notifier = TelegramNotifier(token, recipients, is_prompt=responder.is_prompt)
    return Pipeline(sources, matcher, responder, notifier, storage)


def heartbeat(cfg, pipeline, sent: int) -> None:
    """Раз в N минут слать владельцу 'новых заказов нет', если была тишина.

    Любая реальная отправка сбрасывает таймер. Метка времени хранится в БД,
    поэтому работает и при запуске раз в N минут отдельными процессами (cron).
    """
    if not cfg.heartbeat_idle:
        return
    owner = cfg.secrets.telegram_chat_id
    if not owner:
        return
    storage = pipeline.storage
    now = datetime.now(timezone.utc)

    if sent > 0:                       # были новые заказы — таймер сбрасываем
        storage.set_meta("last_notify", now.isoformat())
        return

    last = storage.get_meta("last_notify")
    due = True
    if last:
        try:
            elapsed = (now - datetime.fromisoformat(last)).total_seconds()
            due = elapsed >= cfg.heartbeat_interval_minutes * 60
        except ValueError:
            due = True
    if due:
        pipeline.notifier.send_text(
            "ℹ️ Пока новых заказов нет — бот работает, проверяю каждые "
            f"{cfg.update_interval_minutes} мин. Сообщу, как появится.",
            chat_ids=[owner],
        )
        storage.set_meta("last_notify", now.isoformat())


def main() -> None:
    parser = argparse.ArgumentParser(description="Парсер фриланс-бирж с откликами")
    parser.add_argument("--once", action="store_true", help="один прогон и выход")
    parser.add_argument(
        "--commands", action="store_true",
        help="только обработать входящие сообщения (/start, ключ) — быстро, без поиска заказов",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="печатать карточки в консоль вместо отправки в Telegram",
    )
    parser.add_argument("--config", default=None, help="путь к config.yaml")
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = load_config(args.config)

    # Быстрый режим: только ответить на входящие сообщения (/start, ключ).
    # Используется в цикле часто (раз в минуту), чтобы друзья получали ответ
    # почти сразу, не дожидаясь полного поиска заказов (раз в 15 мин).
    if args.commands:
        token = cfg.secrets.telegram_bot_token
        if cfg.multi_user and cfg.secrets.access_key and token:
            from bot.commands import process_updates

            storage = Storage(ROOT / "freelance_bot.db")
            process_updates(token, storage, cfg.secrets.access_key,
                            cfg.secrets.telegram_chat_id,
                            interval_minutes=cfg.update_interval_minutes)
        else:
            logging.info("--commands: multi_user/ACCESS_KEY не заданы — нечего обрабатывать")
        return

    pipeline = build_pipeline(cfg, dry_run=args.dry_run)

    if args.once:
        stats = pipeline.run_once()
        if not args.dry_run:
            heartbeat(cfg, pipeline, stats.sent)
        return

    logging.info("Старт. Опрос каждые %d сек. Ctrl+C для остановки.", cfg.poll_interval_sec)
    try:
        while True:
            stats = pipeline.run_once()
            if not args.dry_run:
                heartbeat(cfg, pipeline, stats.sent)
            time.sleep(cfg.poll_interval_sec)
    except KeyboardInterrupt:
        logging.info("Остановлено пользователем.")


if __name__ == "__main__":
    main()
