"""Единая модель заказа, к которой приводятся данные всех источников."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Order:
    """Нормализованный заказ/вакансия с любой биржи."""

    source: str                 # "hh", "habr", "tg:<channel>", "kwork", ...
    external_id: str            # стабильный id внутри источника (для дедупа)
    title: str                  # заголовок заказа
    description: str            # текст/описание (может быть пустым)
    url: str                    # прямая ссылка на заказ (требование п.3)
    budget: str | None = None   # бюджет/зарплата в человекочитаемом виде
    published: datetime | None = None

    @property
    def raw_text(self) -> str:
        """Текст для матчинга и детекции категории (заголовок + описание)."""
        return f"{self.title}\n{self.description}".strip()

    @property
    def dedup_key(self) -> tuple[str, str]:
        return (self.source, self.external_id)
