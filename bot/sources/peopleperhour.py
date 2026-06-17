"""PeoplePerHour — биржа фриланса (Великобритания, best-effort HTML).

Страница /freelance-jobs отдаёт часть листинга статикой.
ОГРАНИЧЕНИЕ: сайт использует JS-рендеринг, часть контента может не загрузиться.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://www.peopleperhour.com"
_ID_RE = re.compile(r"/job/[^/?#]+/(\d+)")


class PeoplePerHourSource(Source):
    name = "peopleperhour"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", f"{BASE}/freelance-jobs")

    def fetch(self) -> list[Order]:
        try:
            resp = net.get(self.url, headers={"Accept-Language": "en-GB,en;q=0.9"})
        except Exception as exc:  # noqa: BLE001
            log.warning("peopleperhour: не загрузился: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=_ID_RE):
            href = a.get("href", "")
            m = _ID_RE.search(href)
            if not m:
                continue
            pid = m.group(1)
            if pid in seen:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            seen.add(pid)

            card = a.find_parent(["div", "article", "li"])
            description = ""
            budget = None
            if card is not None:
                full = card.get_text(" ", strip=True)
                description = re.sub(r"\s+", " ", full.replace(title, " ")).strip()[:800]
                mb = re.search(r"£[\d,]+(?:\s*[-–]\s*£[\d,]+)?|\$[\d,]+", full)
                if mb:
                    budget = mb.group(0).strip()

            url = href if href.startswith("http") else f"{BASE}{href}"
            out.append(
                Order(source=self.name, external_id=pid, title=title,
                      description=description, url=url, budget=budget)
            )

        log.info("peopleperhour: получено %d заказов", len(out))
        return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for o in PeoplePerHourSource({}).fetch()[:10]:
        print(f"- {o.title[:70]}\n  {o.url} | {o.budget}\n  {o.description[:100]}\n")
