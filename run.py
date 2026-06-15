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

    if dry_run:
        notifier = ConsoleNotifier()
    else:
        notifier = TelegramNotifier(
            cfg.secrets.telegram_bot_token, cfg.secrets.telegram_chat_id
        )

    storage = Storage(ROOT / "freelance_bot.db")
    return Pipeline(sources, matcher, responder, notifier, storage)


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
        pipeline.run_once()
        return

    logging.info("Старт. Опрос каждые %d сек. Ctrl+C для остановки.", cfg.poll_interval_sec)
    try:
        while True:
            pipeline.run_once()
            time.sleep(cfg.poll_interval_sec)
    except KeyboardInterrupt:
        logging.info("Остановлено пользователем.")


if __name__ == "__main__":
    main()
