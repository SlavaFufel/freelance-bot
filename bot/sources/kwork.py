"""Kwork — биржа проектов kwork.ru/projects (Tier 2, best-effort).

Страница рендерится через JS, статический HTML может не содержать заказов.
Если этот парсер вернёт пусто — данные подгружаются динамически: тогда нужен
Playwright (см. requirements.txt) или внутренний JSON-эндпоинт Kwork.
ПОДЛЕЖИТ ЖИВОЙ СВЕРКЕ.
"""
from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://kwork.ru"
_PROJ_HREF = re.compile(r"/projects/(\d+)")


class KworkSource(Source):
    name = "kwork"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", f"{BASE}/projects")

    def fetch(self) -> list[Order]:
        try:
            resp = net.get(self.url)
        except Exception as exc:  # noqa: BLE001
            log.warning("kwork не загрузился: %s", exc)
            return []

        html = resp.text
        orders = self._from_embedded_json(html) or self._from_html(html)

        # Контент Kwork грузится через JS — если статикой пусто, пробуем headless-браузер.
        if not orders:
            from . import _playwright

            rendered = _playwright.render_html(self.url, wait_selector='a[href*="/projects/"]')
            if rendered:
                orders = self._from_embedded_json(rendered) or self._from_html(rendered)
            else:
                log.warning(
                    "kwork: заказов не найдено — контент грузится через JS. "
                    "Установи Playwright (см. requirements.txt), чтобы парсить Kwork."
                )

        log.info("kwork: получено %d заказов", len(orders))
        return orders

    def _from_embedded_json(self, html: str) -> list[Order]:
        """Kwork часто кладёт state в inline-JSON. Пытаемся вытащить wantsListData."""
        out: list[Order] = []
        m = re.search(r'"wantsListData"\s*:\s*(\[.*?\])\s*[,}]', html, re.DOTALL)
        if not m:
            return out
        try:
            items = json.loads(m.group(1))
        except json.JSONDecodeError:
            return out
        for it in items:
            pid = str(it.get("id") or it.get("want_id") or "")
            if not pid:
                continue
            out.append(
                Order(
                    source=self.name,
                    external_id=pid,
                    title=it.get("name") or it.get("title") or "(проект Kwork)",
                    description=it.get("description") or it.get("desc") or "",
                    url=f"{BASE}/projects/{pid}",
                    budget=str(it.get("priceLimit") or it.get("price") or "") or None,
                )
            )
        return out

    def _from_html(self, html: str) -> list[Order]:
        out: list[Order] = []
        seen: set[str] = set()
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select('a[href*="/projects/"]'):
            m = _PROJ_HREF.search(a.get("href", ""))
            if not m:
                continue
            pid = m.group(1)
            title = a.get_text(strip=True)
            if not title or pid in seen:
                continue
            seen.add(pid)
            out.append(
                Order(
                    source=self.name,
                    external_id=pid,
                    title=title,
                    description="",
                    url=f"{BASE}/projects/{pid}",
                )
            )
        return out
