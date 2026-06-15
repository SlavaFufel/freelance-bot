"""Weblancer — заказы weblancer.net/jobs (Tier 2, best-effort).

Server-rendered HTML, парсится статически. Возможен анти-бот/Cloudflare —
тогда net.get вернёт не-200 и источник просто пропустится.
ПОДЛЕЖИТ ЖИВОЙ СВЕРКЕ селекторов.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://www.weblancer.net"
_JOB_HREF = re.compile(r"/(?:project|jobs)/(\d+)")


class WeblancerSource(Source):
    name = "weblancer"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", f"{BASE}/jobs/")

    def fetch(self) -> list[Order]:
        try:
            resp = net.get(self.url)
        except Exception as exc:  # noqa: BLE001
            log.warning("weblancer не загрузился (возможен анти-бот): %s", exc)
            return []

        out = self._parse(resp.text)

        # Список заказов Weblancer рендерится через JS — статикой ссылок на заказы нет.
        if not out:
            from . import _playwright

            rendered = _playwright.render_html(self.url, wait_selector='a[href*="/project/"]')
            if rendered:
                out = self._parse(rendered)
            else:
                log.warning(
                    "weblancer: заказов не найдено — список грузится через JS. "
                    "Установи Playwright (см. requirements.txt), чтобы парсить Weblancer."
                )

        log.info("weblancer: получено %d заказов", len(out))
        return out

    def _parse(self, html: str) -> list[Order]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()

        # Карточки заказов Weblancer: заголовок — ссылка на /project/<id> (или /jobs/<id>)
        for a in soup.select('a[href*="/project/"], a[href*="/jobs/"]'):
            href = a.get("href", "")
            m = _JOB_HREF.search(href)
            if not m:
                continue
            jid = m.group(1)
            title = a.get_text(strip=True)
            if not title or jid in seen:
                continue
            seen.add(jid)

            card = a.find_parent(["div", "tr", "li"])
            description = ""
            budget = None
            if card is not None:
                desc_el = card.select_one(".text_field, .description, p")
                if desc_el:
                    description = desc_el.get_text(" ", strip=True)
                price_el = card.select_one(".amount, .price, .text-truncate")
                if price_el and ("$" in price_el.get_text() or "₽" in price_el.get_text()
                                 or "грн" in price_el.get_text()):
                    budget = price_el.get_text(" ", strip=True)

            url = href if href.startswith("http") else f"{BASE}{href}"
            out.append(
                Order(
                    source=self.name,
                    external_id=jid,
                    title=title,
                    description=description,
                    url=url,
                    budget=budget,
                )
            )

        return out
