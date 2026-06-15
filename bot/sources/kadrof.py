"""kadrof.ru — лента заказов/вакансий (Tier 1, статический HTML).

Страница /work отдаёт карточки со ссылками /work/<id>. Парсится статикой,
как freelance.ru. Обновляется ежедневно, есть заказы на сайты/боты/Python.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://www.kadrof.ru"
_WORK = re.compile(r"/work/(\d+)")


class KadrofSource(Source):
    name = "kadrof.ru"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", f"{BASE}/work")

    def fetch(self) -> list[Order]:
        try:
            resp = net.get(self.url)
        except Exception as exc:  # noqa: BLE001
            log.warning("kadrof.ru не загрузился: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            m = _WORK.search(a["href"])
            if not m:
                continue
            wid = m.group(1)
            title = a.get_text(strip=True)
            if not title or wid in seen:
                continue
            seen.add(wid)

            card = a.find_parent(["article", "li", "div", "tr"])
            description = ""
            budget = None
            if card is not None:
                txt = card.get_text(" ", strip=True)
                description = re.sub(r"\s+", " ", txt.replace(title, " ")).strip()
                mb = re.search(r"(до|от)?\s*\d[\d\s]*(₽|руб)", txt)
                if mb:
                    budget = mb.group(0).strip()

            href = a["href"]
            url = href if href.startswith("http") else f"{BASE}{href}"
            out.append(
                Order(
                    source=self.name,
                    external_id=wid,
                    title=title,
                    description=description[:800],
                    url=url,
                    budget=budget,
                )
            )

        log.info("kadrof.ru: получено %d заказов", len(out))
        return out


if __name__ == "__main__":  # ручная проверка
    logging.basicConfig(level=logging.INFO)
    for o in KadrofSource({}).fetch()[:10]:
        print(f"- {o.title[:70]}\n  {o.url} | {o.budget}")
