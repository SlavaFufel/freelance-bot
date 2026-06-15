"""Подбор подходящих заказов по ключевым словам (без ИИ)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import MatchConfig
from .models import Order

_NON_WORD = re.compile(r"[^0-9a-zа-я]+")


def normalize(text: str) -> str:
    """lower + ё→е + схлопывание небуквенных символов в пробелы."""
    text = (text or "").lower().replace("ё", "е")
    text = _NON_WORD.sub(" ", text)
    return f" {text.strip()} "  # пробелы по краям, чтобы ловить целые слова через ' kw '


@dataclass
class MatchResult:
    passed: bool
    score: float
    matched: list[str]       # совпавшие include-слова
    boosted: list[str]       # совпавшие boost-слова
    excluded: list[str]      # сработавшие exclude-слова
    reason: str = ""


class Matcher:
    def __init__(self, cfg: MatchConfig):
        self.cfg = cfg
        # Нормализуем ключевые слова один раз. Многословные фразы тоже нормализуются
        # (дефисы → пробелы), поэтому ищем их как подстроки.
        self.include = [normalize(k).strip() for k in cfg.include_keywords]
        self.boost = [normalize(k).strip() for k in cfg.boost_keywords]
        self.exclude = [normalize(k).strip() for k in cfg.exclude_keywords]

    @staticmethod
    def _hits(text: str, keywords: list[str]) -> list[str]:
        # text уже с пробелами по краям; ищем " kw " чтобы не цеплять подстроки внутри слов.
        out = []
        for kw in keywords:
            if not kw:
                continue
            if f" {kw} " in text or f" {kw}" in text or f"{kw} " in text:
                out.append(kw)
        return out

    def evaluate(self, order: Order) -> MatchResult:
        text = normalize(order.raw_text)

        excluded = self._hits(text, self.exclude)
        if excluded:
            return MatchResult(False, 0.0, [], [], excluded, reason="exclude")

        matched = self._hits(text, self.include)
        if not matched:
            return MatchResult(False, 0.0, [], [], [], reason="no-include")

        # Сильный фильтр точности: суть заказа должна быть в заголовке, а не
        # случайно упомянута в длинном тексте ("у нас есть сайт, нужен SMM").
        if self.cfg.require_in_title and not self._hits(normalize(order.title), self.include):
            return MatchResult(False, 0.0, matched, [], [], reason="not-in-title")

        boosted = self._hits(text, self.boost)
        score = (
            len(matched) * self.cfg.include_weight
            + len(boosted) * self.cfg.boost_weight
        )
        passed = score >= self.cfg.min_score
        return MatchResult(
            passed=passed,
            score=round(score, 2),
            matched=matched,
            boosted=boosted,
            excluded=[],
            reason="ok" if passed else "below-threshold",
        )
