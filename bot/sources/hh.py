"""hh.ru — официальный API api.hh.ru/vacancies (Tier 1, надёжно).

ВАЖНО: hh требует осмысленный заголовок User-Agent, иначе 403.
Док: https://api.hh.ru/openapi/redoc , https://github.com/hhru/api
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

API_URL = "https://api.hh.ru/vacancies"
_TAG = re.compile(r"<[^>]+>")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return _TAG.sub("", text).replace("&quot;", '"').replace("&amp;", "&").strip()


def _salary(item: dict) -> str | None:
    s = item.get("salary")
    if not s:
        return None
    lo, hi, cur = s.get("from"), s.get("to"), s.get("currency") or ""
    if lo and hi:
        return f"{lo}–{hi} {cur}"
    if lo:
        return f"от {lo} {cur}"
    if hi:
        return f"до {hi} {cur}"
    return None


class HHSource(Source):
    name = "hh"

    def __init__(self, cfg: dict, user_agent: str):
        self.queries: list[str] = cfg.get("queries") or ["разработка сайта"]
        self.area = cfg.get("area", 113)
        self.period_days = int(cfg.get("period_days", 1))
        self.per_page = int(cfg.get("per_page", 50))
        self.search_field = cfg.get("search_field", "name")
        self.user_agent = user_agent

    def fetch(self) -> list[Order]:
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        seen_ids: set[str] = set()
        orders: list[Order] = []

        for query in self.queries:
            params = {
                "text": query,
                "area": self.area,
                "period": self.period_days,
                "per_page": self.per_page,
                "order_by": "publication_time",
                "search_field": self.search_field,
            }
            try:
                resp = net.get(API_URL, headers=headers, params=params)
                data = resp.json()
            except Exception as exc:  # noqa: BLE001
                log.warning("hh запрос %r не удался: %s", query, exc)
                continue

            for item in data.get("items", []):
                vid = str(item.get("id"))
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)

                snippet = item.get("snippet") or {}
                desc = " ".join(
                    filter(None, [_clean(snippet.get("requirement")),
                                  _clean(snippet.get("responsibility"))])
                )
                employer = (item.get("employer") or {}).get("name") or ""
                if employer:
                    desc = f"{employer}. {desc}".strip()

                published = None
                if item.get("published_at"):
                    try:
                        published = datetime.fromisoformat(item["published_at"])
                    except ValueError:
                        published = None

                orders.append(
                    Order(
                        source=self.name,
                        external_id=vid,
                        title=item.get("name") or "(без названия)",
                        description=desc,
                        url=item.get("alternate_url") or f"https://hh.ru/vacancy/{vid}",
                        budget=_salary(item),
                        published=published,
                    )
                )

        log.info("hh: получено %d вакансий", len(orders))
        return orders
