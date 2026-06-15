"""freelance.ru — заказы со страницы /task (Tier 1, статический HTML).

Замена закрытому Habr Freelance. Карточки заказов: <article class="task-card">,
ссылка на заказ — /task/view/<id>. Премиум-карточки (видны только по платной
подписке) пропускаем — по ним всё равно не откликнуться.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .. import net
from ..models import Order
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://freelance.ru"
_VIEW = re.compile(r"/task/view/(\d+)")
_NOISE = ("Видно всем", "★ Только для Премиум", "Только для Премиум")


class FreelanceRuSource(Source):
    name = "freelance.ru"

    def __init__(self, cfg: dict):
        self.url = cfg.get("url", f"{BASE}/task")
        # премиум-заказы видны, но откликнуться на них можно только с платной
        # подпиской freelance.ru. По умолчанию пропускаем как неоткликабельные.
        self.include_premium = bool(cfg.get("include_premium", False))

    def fetch(self) -> list[Order]:
        try:
            resp = net.get(self.url)
        except Exception as exc:  # noqa: BLE001
            log.warning("freelance.ru не загрузился: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        out: list[Order] = []
        seen: set[str] = set()

        for card in soup.select("article.task-card"):
            classes = card.get("class") or []
            if "task-card--premium" in classes and not self.include_premium:
                continue  # заказ под платной подпиской — пропускаем

            a = card.select_one('a[href*="/task/view/"]')
            if not a:
                continue
            m = _VIEW.search(a.get("href", ""))
            if not m:
                continue
            tid = m.group(1)
            if tid in seen:
                continue
            seen.add(tid)

            title = a.get_text(strip=True)
            if not title:
                continue

            main = card.select_one(".task-card__main") or card
            full = main.get_text(" ", strip=True)
            desc = full
            for noise in (*_NOISE, title):
                desc = desc.replace(noise, " ")
            desc = re.sub(r"\s+", " ", desc).strip()

            budget = None
            mb = re.search(r"\d[\d\s]*₽", full)
            if mb:
                budget = mb.group(0).strip()

            out.append(
                Order(
                    source=self.name,
                    external_id=tid,
                    title=title,
                    description=desc[:1000],
                    url=f"{BASE}{a.get('href')}",
                    budget=budget,
                )
            )

        log.info("freelance.ru: получено %d заказов", len(out))
        return out


if __name__ == "__main__":  # ручная проверка
    logging.basicConfig(level=logging.INFO)
    for o in FreelanceRuSource({}).fetch()[:10]:
        print(f"- {o.title[:70]}\n  {o.url} | {o.budget}\n  {o.description[:120]}\n")
