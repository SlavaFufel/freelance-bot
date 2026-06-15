"""FL.ru — проекты fl.ru/projects (best-effort через Playwright).

ОГРАНИЧЕНИЕ: у FL.ru тяжёлый анти-бот (DDoS-Guard). Список проектов виден без
логина, но защита может отдавать челлендж/пусто, особенно с датацентр-IP (GitHub).
Лучший шанс — запуск локально с российского IP. Если Playwright не установлен или
страница не отдалась — источник просто пропускается.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..models import Order
from . import _playwright
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://www.fl.ru"
_PROJ = re.compile(r"/projects/(\d+)")


class FlRuSource(Source):
    name = "fl.ru"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", f"{BASE}/projects/")
        self.storage_state = cfg.get("storage_state")
        self.wait_selector = cfg.get("wait_selector", 'a[href*="/projects/"]')

    def fetch(self) -> list[Order]:
        html = _playwright.render_html(
            self.url, wait_selector=self.wait_selector, storage_state=self.storage_state
        )
        if not html:
            log.info("fl.ru: пропущено (нет Playwright/браузера или анти-бот отдал пусто)")
            return []

        soup = BeautifulSoup(html, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()

        for a in soup.select('a[href*="/projects/"]'):
            m = _PROJ.search(a.get("href", ""))
            if not m:
                continue
            pid = m.group(1)
            title = a.get_text(strip=True)
            if not title or pid in seen:
                continue
            seen.add(pid)

            card = a.find_parent(["div", "article", "li"])
            description = ""
            budget = None
            if card is not None:
                txt = card.get_text(" ", strip=True)
                description = re.sub(r"\s+", " ", txt.replace(title, " ")).strip()
                mb = re.search(r"\d[\d\s]*(₽|руб)", txt)
                if mb:
                    budget = mb.group(0).strip()

            href = a.get("href", "")
            url = href if href.startswith("http") else f"{BASE}{href}"
            out.append(
                Order(source=self.name, external_id=pid, title=title,
                      description=description[:800], url=url, budget=budget)
            )

        log.info("fl.ru: получено %d заказов", len(out))
        return out
