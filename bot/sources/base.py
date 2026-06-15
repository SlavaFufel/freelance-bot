"""Абстрактный источник заказов."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Order


class Source(ABC):
    #: короткое имя источника (используется в Order.source и логах)
    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[Order]:
        """Вернуть свежие заказы. Бросать исключение можно — pipeline его поймает."""
        raise NotImplementedError
