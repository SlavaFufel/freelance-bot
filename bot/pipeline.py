"""Конвейер: fetch → dedup → match → render → notify."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .matcher import Matcher
from .responder import Responder
from .storage import Storage
from .sources.base import Source

log = logging.getLogger(__name__)


@dataclass
class CycleStats:
    fetched: int = 0
    new: int = 0
    matched: int = 0
    sent: int = 0
    errors: int = 0


class Pipeline:
    def __init__(
        self,
        sources: list[Source],
        matcher: Matcher,
        responder: Responder,
        notifier,            # TelegramNotifier | ConsoleNotifier (есть .send)
        storage: Storage,
    ):
        self.sources = sources
        self.matcher = matcher
        self.responder = responder
        self.notifier = notifier
        self.storage = storage

    def run_once(self) -> CycleStats:
        stats = CycleStats()

        for source in self.sources:
            try:
                orders = source.fetch()
            except Exception as exc:  # noqa: BLE001 — один источник не должен ронять цикл
                log.error("Источник %s упал: %s", getattr(source, "name", source), exc)
                stats.errors += 1
                continue

            stats.fetched += len(orders)
            for order in orders:
                if self.storage.is_seen(order.source, order.external_id):
                    continue
                stats.new += 1

                result = self.matcher.evaluate(order)
                if not result.passed:
                    # запоминаем, чтобы не пересчитывать тот же заказ каждый цикл
                    self.storage.mark_seen(order, result.score, notified=False)
                    continue

                stats.matched += 1
                response = self.responder.render(order)
                ok = self.notifier.send(order, result, response)
                if ok:
                    stats.sent += 1
                    self.storage.mark_seen(order, result.score, notified=True)
                else:
                    # не помечаем seen — повторим отправку в следующем цикле
                    stats.errors += 1

        log.info(
            "Цикл завершён: получено=%d новых=%d подошло=%d отправлено=%d ошибок=%d",
            stats.fetched, stats.new, stats.matched, stats.sent, stats.errors,
        )
        return stats
