"""YouDo — задания youdo.com (best-effort через Playwright).

ОГРАНИЧЕНИЕ: контент рендерится через JS + есть анти-бот; многое — локальные
услуги, а не разработка (фильтр по ключевым словам отсеет лишнее). Лучший шанс —
локальный запуск с российского IP. Без Playwright/браузера источник пропускается.

По умолчанию берём раздел, близкий к IT/разработке (настраивается через url).
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..models import Order
from . import _playwright
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://youdo.com"
# задания YouDo: /t<цифры> (например /t123456) либо /tasks/<...>
_TASK = re.compile(r"/t(\d{5,})")


class YoudoSource(Source):
    name = "youdo"

    def __init__(self, cfg: dict):
        # раздел "Разработка и IT" (можно поменять на нужную категорию)
        self.url = cfg.get("url", f"{BASE}/tasks-internet-it")
        self.storage_state = cfg.get("storage_state")
        self.wait_selector = cfg.get("wait_selector", 'a[href*="/t"]')

    def fetch(self) -> list[Order]:
        html = _playwright.render_html(
            self.url, wait_selector=self.wait_selector, storage_state=self.storage_state
        )
        if not html:
            log.info("youdo: пропущено (нет Playwright/браузера или анти-бот)")
            return []

        soup = BeautifulSoup(html, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            m = _TASK.search(a["href"])
            if not m:
                continue
            tid = m.group(1)
            title = a.get_text(strip=True)
            if not title or tid in seen:
                continue
            seen.add(tid)

            card = a.find_parent(["div", "article", "li"])
            description = ""
            budget = None
            if card is not None:
                txt = card.get_text(" ", strip=True)
                description = re.sub(r"\s+", " ", txt.replace(title, " ")).strip()
                mb = re.search(r"\d[\d\s]*(₽|руб)", txt)
                if mb:
                    budget = mb.group(0).strip()

            href = a["href"]
            url = href if href.startswith("http") else f"{BASE}{href}"
            out.append(
                Order(source=self.name, external_id=tid, title=title,
                      description=description[:800], url=url, budget=budget)
            )

        log.info("youdo: получено %d заданий", len(out))
        return out
