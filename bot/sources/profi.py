"""Profi.ru — заказы (Tier 3, best-effort через Playwright).

ОГРАНИЧЕНИЕ: у Profi.ru тяжёлый анти-бот, а заказы видны в основном
авторизованному специалисту. Без сохранённой сессии (storage_state) парсер,
скорее всего, вернёт пусто. По умолчанию источник ВЫКЛЮЧЕН в config.yaml.

Как включить позже:
  1) pip install playwright && python -m playwright install chromium
  2) один раз войти в аккаунт и сохранить сессию в profi_state.json
  3) добавить "profi" в enabled_sources и указать storage_state в sources.profi
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..models import Order
from . import _playwright
from .base import Source

log = logging.getLogger(__name__)

DEFAULT_URL = "https://profi.ru/backoffice/n.php"  # лента заказов (под логином)
_ORDER_HREF = re.compile(r"/order/(\w+)")


class ProfiSource(Source):
    name = "profi"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", DEFAULT_URL)
        self.storage_state = cfg.get("storage_state")  # путь к profi_state.json
        self.wait_selector = cfg.get("wait_selector")

    def fetch(self) -> list[Order]:
        html = _playwright.render_html(
            self.url,
            wait_selector=self.wait_selector,
            storage_state=self.storage_state,
        )
        if not html:
            log.info("profi: пропущено (нет Playwright/сессии или страница пуста)")
            return []

        soup = BeautifulSoup(html, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()
        for a in soup.select('a[href*="/order/"]'):
            m = _ORDER_HREF.search(a.get("href", ""))
            if not m:
                continue
            oid = m.group(1)
            title = a.get_text(strip=True)
            if not title or oid in seen:
                continue
            seen.add(oid)
            href = a.get("href", "")
            url = href if href.startswith("http") else f"https://profi.ru{href}"
            out.append(
                Order(source=self.name, external_id=oid, title=title,
                      description="", url=url)
            )
        log.info("profi: получено %d заказов", len(out))
        return out
