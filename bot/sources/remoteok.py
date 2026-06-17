"""RemoteOK — публичный JSON API без авторизации.

https://remoteok.com/api — возвращает массив вакансий прямо в JSON.
Самый надёжный зарубежный источник: работает со всех IP без капчи.
"""
from __future__ import annotations

import logging
import re

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"


class RemoteOkSource(Source):
    name = "remoteok"

    def __init__(self, cfg: dict):
        self.limit: int = int(cfg.get("limit", 50))

    def fetch(self) -> list[Order]:
        try:
            resp = net.get(
                API_URL,
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("remoteok: ошибка: %s", exc)
            return []

        out: list[Order] = []
        for item in data:
            if not isinstance(item, dict) or "id" not in item:
                continue  # первый элемент — meta/legal
            pid = str(item.get("id", ""))
            title = (item.get("position") or "").strip()
            if not title or not pid:
                continue

            raw_desc = item.get("description") or ""
            desc = re.sub(r"<[^>]+>", " ", raw_desc)
            desc = re.sub(r"\s+", " ", desc).strip()[:800]

            tags = item.get("tags") or []
            if tags:
                desc = f"[{', '.join(tags)}] {desc}"

            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")
            budget = None
            if salary_min:
                budget = f"${salary_min}–${salary_max}/yr" if salary_max else f"${salary_min}+/yr"

            url = item.get("url") or f"https://remoteok.com/remote-jobs/{pid}"
            out.append(
                Order(source=self.name, external_id=pid, title=title,
                      description=desc, url=url, budget=budget)
            )
            if len(out) >= self.limit:
                break

        log.info("remoteok: получено %d заказов", len(out))
        return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for o in RemoteOkSource({}).fetch()[:10]:
        print(f"- {o.title[:70]}\n  {o.url} | {o.budget}\n  {o.description[:100]}\n")
