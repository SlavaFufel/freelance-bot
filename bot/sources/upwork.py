"""Upwork — RSS-лента свежих заказов по нескольким поисковым запросам.

Upwork предоставляет публичный RSS без авторизации:
https://www.upwork.com/ab/feed/jobs/rss?q=<query>&sort=recency
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://www.upwork.com"
RSS_URL = "https://www.upwork.com/ab/feed/jobs/rss"

_DEFAULT_QUERIES = [
    "web developer",
    "python developer",
    "telegram bot",
    "react developer",
    "unity developer",
    "web scraping",
    "automation script",
]

_ID_RE = re.compile(r"~([0-9a-f]+)")
_BUDGET_RE = re.compile(r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?|\$[\d,]+/hr")


def _parse_rss(xml_text: str, source_name: str) -> list[Order]:
    out: list[Order] = []
    seen: set[str] = set()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.warning("upwork: не удалось распарсить RSS: %s", exc)
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    channel = root.find("channel")
    if channel is None:
        return []

    for item in channel.findall("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""
        raw_desc = (desc_el.text or "") if desc_el is not None else ""

        if not title or not url:
            continue

        m = _ID_RE.search(url)
        pid = m.group(1) if m else re.sub(r"[^a-z0-9]", "", url[-30:])
        if pid in seen:
            continue
        seen.add(pid)

        # описание в RSS — HTML, чистим теги
        desc = re.sub(r"<[^>]+>", " ", raw_desc)
        desc = re.sub(r"\s+", " ", desc).strip()[:800]

        budget = None
        mb = _BUDGET_RE.search(raw_desc)
        if mb:
            budget = mb.group(0).strip()

        out.append(
            Order(source=source_name, external_id=pid, title=title,
                  description=desc, url=url, budget=budget)
        )
    return out


class UpworkSource(Source):
    name = "upwork"

    def __init__(self, cfg: dict):
        self.queries: list[str] = cfg.get("queries", _DEFAULT_QUERIES)

    def fetch(self) -> list[Order]:
        all_orders: list[Order] = []
        seen_ids: set[str] = set()

        for query in self.queries:
            try:
                resp = net.get(
                    RSS_URL,
                    params={"q": query, "sort": "recency", "paging": "0;10"},
                    headers={"Accept": "application/rss+xml, application/xml, text/xml"},
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("upwork [%s]: ошибка запроса: %s", query, exc)
                continue

            orders = _parse_rss(resp.text, self.name)
            for o in orders:
                if o.external_id not in seen_ids:
                    seen_ids.add(o.external_id)
                    all_orders.append(o)

        log.info("upwork: получено %d заказов (по %d запросам)", len(all_orders), len(self.queries))
        return all_orders


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for o in UpworkSource({}).fetch()[:10]:
        print(f"- {o.title[:70]}\n  {o.url} | {o.budget}\n  {o.description[:100]}\n")
