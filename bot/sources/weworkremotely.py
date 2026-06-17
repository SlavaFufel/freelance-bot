"""We Work Remotely — RSS-лента удалённых вакансий (programming + devops).

Публичный RSS без авторизации: https://weworkremotely.com/categories/remote-programming-jobs.rss
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]

_ID_RE = re.compile(r"/listings/(\d+)")


def _parse_rss(xml_text: str, source_name: str) -> list[Order]:
    out: list[Order] = []
    seen: set[str] = set()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.warning("weworkremotely: ошибка парсинга RSS: %s", exc)
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    for item in channel.findall("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        region_el = item.find("region") or item.find("{https://weworkremotely.com}region")

        title = (title_el.text or "").strip() if title_el is not None else ""
        # link в WWR хранится в CDATA после пустого <link/>
        url = ""
        for el in item:
            if el.tag == "link" and el.text:
                url = el.text.strip()
                break
            if el.tag == "link" and el.tail:
                url = el.tail.strip()
                break
        # запасной вариант — берём из guid
        if not url:
            guid = item.find("guid")
            if guid is not None and guid.text:
                url = guid.text.strip()

        if not title or not url:
            continue

        m = _ID_RE.search(url)
        pid = m.group(1) if m else re.sub(r"[^a-z0-9]", "", url[-20:])
        if pid in seen:
            continue
        seen.add(pid)

        raw_desc = (desc_el.text or "") if desc_el is not None else ""
        desc = re.sub(r"<[^>]+>", " ", raw_desc)
        desc = re.sub(r"\s+", " ", desc).strip()[:800]

        out.append(
            Order(source=source_name, external_id=pid, title=title,
                  description=desc, url=url, budget=None)
        )
    return out


class WeWorkRemotelySource(Source):
    name = "weworkremotely"

    def __init__(self, cfg: dict):
        self.feeds: list[str] = cfg.get("feeds", FEEDS)

    def fetch(self) -> list[Order]:
        all_orders: list[Order] = []
        seen_ids: set[str] = set()

        for feed_url in self.feeds:
            try:
                resp = net.get(feed_url, headers={"Accept": "application/rss+xml"})
            except Exception as exc:  # noqa: BLE001
                log.warning("weworkremotely [%s]: ошибка: %s", feed_url, exc)
                continue
            for o in _parse_rss(resp.text, self.name):
                if o.external_id not in seen_ids:
                    seen_ids.add(o.external_id)
                    all_orders.append(o)

        log.info("weworkremotely: получено %d заказов", len(all_orders))
        return all_orders


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for o in WeWorkRemotelySource({}).fetch()[:10]:
        print(f"- {o.title[:70]}\n  {o.url}\n  {o.description[:100]}\n")
