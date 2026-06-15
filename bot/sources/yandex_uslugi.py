"""Яндекс Услуги — заказы (Tier 3, best-effort через Playwright).

ОГРАНИЧЕНИЕ: анти-бот + заказы видны авторизованному исполнителю.
Без сохранённой сессии парсер, скорее всего, вернёт пусто. По умолчанию
источник ВЫКЛЮЧЕН в config.yaml. Включение — как у Profi (см. profi.py).
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..models import Order
from . import _playwright
from .base import Source

log = logging.getLogger(__name__)

DEFAULT_URL = "https://uslugi.yandex.ru/orders"  # лента заказов (под логином)
_ORDER_HREF = re.compile(r"/orders?/([\w-]+)")


class YandexUslugiSource(Source):
    name = "yandex_uslugi"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", DEFAULT_URL)
        self.storage_state = cfg.get("storage_state")
        self.wait_selector = cfg.get("wait_selector")

    def fetch(self) -> list[Order]:
        html = _playwright.render_html(
            self.url,
            wait_selector=self.wait_selector,
            storage_state=self.storage_state,
        )
        if not html:
            log.info("yandex_uslugi: пропущено (нет Playwright/сессии или пусто)")
            return []

        soup = BeautifulSoup(html, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()
        for a in soup.select('a[href*="/order"]'):
            m = _ORDER_HREF.search(a.get("href", ""))
            if not m:
                continue
            oid = m.group(1)
            title = a.get_text(strip=True)
            if not title or oid in seen:
                continue
            seen.add(oid)
            href = a.get("href", "")
            url = href if href.startswith("http") else f"https://uslugi.yandex.ru{href}"
            out.append(
                Order(source=self.name, external_id=oid, title=title,
                      description="", url=url)
            )
        log.info("yandex_uslugi: получено %d заказов", len(out))
        return out
