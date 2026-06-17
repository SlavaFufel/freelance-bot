"""Freelancer.com — публичный листинг проектов (best-effort, статический HTML).

Страница /jobs/ отдаёт часть проектов без JS.
ОГРАНИЧЕНИЕ: Freelancer.com активно защищается от ботов; с датацентрового IP
(GitHub Actions) может отдавать 403/CAPTCHA. Лучший шанс — запуск локально.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://www.freelancer.com"
_ID_RE = re.compile(r"/projects/[^/]+/([^/?#]+)")


class FreelancerComSource(Source):
    name = "freelancer.com"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", f"{BASE}/jobs/")

    def fetch(self) -> list[Order]:
        try:
            resp = net.get(
                self.url,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("freelancer.com: не загрузился: %s", exc)
            return []

        if resp.status_code != 200:
            log.info("freelancer.com: HTTP %s — пропускаю", resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=re.compile(r"/projects/")):
            href = a.get("href", "")
            m = _ID_RE.search(href)
            if not m:
                continue
            slug = m.group(1)
            if slug in seen:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            seen.add(slug)

            card = a.find_parent(["div", "article", "li"])
            description = ""
            budget = None
            if card is not None:
                full = card.get_text(" ", strip=True)
                description = re.sub(r"\s+", " ", full.replace(title, " ")).strip()[:800]
                mb = re.search(r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?", full)
                if mb:
                    budget = mb.group(0).strip()

            url = href if href.startswith("http") else f"{BASE}{href}"
            out.append(
                Order(source=self.name, external_id=slug, title=title,
                      description=description, url=url, budget=budget)
            )

        log.info("freelancer.com: получено %d заказов", len(out))
        return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for o in FreelancerComSource({}).fetch()[:10]:
        print(f"- {o.title[:70]}\n  {o.url} | {o.budget}\n  {o.description[:100]}\n")
