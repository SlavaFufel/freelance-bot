"""Freelancehunt.com — биржа фриланс-проектов (RU/UA, статический HTML).

Публичный листинг без логина: https://freelancehunt.com/projects/
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://freelancehunt.com"
_ID = re.compile(r"/project/(?:view/)?(\d+)")


class FreelancehuntSource(Source):
    name = "freelancehunt"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", f"{BASE}/projects/")

    def fetch(self) -> list[Order]:
        try:
            resp = net.get(self.url, headers={"Accept-Language": "ru-RU,ru;q=0.9"})
        except Exception as exc:  # noqa: BLE001
            log.warning("freelancehunt: не загрузился: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()

        # Ищем все ссылки на проекты (формат /project/view/<id>/ или /project/<id>/)
        for a in soup.find_all("a", href=_ID):
            href = a.get("href", "")
            m = _ID.search(href)
            if not m:
                continue
            pid = m.group(1)
            if pid in seen:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            seen.add(pid)

            card = a.find_parent(["div", "article", "li", "tr"])
            description = ""
            budget = None
            if card is not None:
                full = card.get_text(" ", strip=True)
                description = re.sub(r"\s+", " ", full.replace(title, " ")).strip()[:800]
                mb = re.search(r"\d[\d\s]*(₽|грн|usd|\$|€)", full, re.IGNORECASE)
                if mb:
                    budget = mb.group(0).strip()

            url = href if href.startswith("http") else f"{BASE}{href}"
            out.append(
                Order(source=self.name, external_id=pid, title=title,
                      description=description, url=url, budget=budget)
            )

        log.info("freelancehunt: получено %d заказов", len(out))
        return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for o in FreelancehuntSource({}).fetch()[:10]:
        print(f"- {o.title[:70]}\n  {o.url} | {o.budget}\n  {o.description[:100]}\n")
