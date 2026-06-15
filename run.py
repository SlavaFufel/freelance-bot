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

    if cfg.multi_user and cfg.secrets.access_key:
        # обрабатываем входящие сообщения (/start, ключ доступа) и собираем подписчиков
        from bot.commands import process_updates

        process_updates(token, storage, cfg.secrets.access_key, owner,
                        interval_minutes=cfg.update_interval_minutes)
        recipients = storage.active_subscribers()
        # Владелец получает заказы ВСЕГДА, даже если сам не отправлял ключ боту.
        if owner and owner not in recipients:
            recipients.insert(0, owner)
        logging.info("Многопользовательский режим: получателей %d", len(recipients))
    else:
        if cfg.multi_user and not cfg.secrets.access_key:
            logging.warning("multi_user включён, но ACCESS_KEY не задан — шлю только владельцу")
        recipients = [owner] if owner else []

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
