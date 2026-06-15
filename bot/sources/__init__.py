"""Источники заказов. Каждый источник приводит данные к bot.models.Order."""
from __future__ import annotations

from ..config import Config
from .base import Source


def build_sources(cfg: Config) -> list[Source]:
    """Собрать включённые в config источники. Неизвестные/упавшие — пропускаем."""
    import logging

    log = logging.getLogger(__name__)
    built: list[Source] = []

    for name in cfg.enabled_sources:
        try:
            src = _build_one(name, cfg)
        except Exception as exc:  # noqa: BLE001
            log.error("Не удалось создать источник %r: %s", name, exc)
            continue
        if src is not None:
            built.append(src)
    return built


def _build_one(name: str, cfg: Config) -> Source | None:
    sc = cfg.source_cfg(name)

    if name == "hh":
        from .hh import HHSource

        return HHSource(sc, user_agent=cfg.secrets.hh_user_agent)
    if name == "telegram_channels":
        from .telegram_channels import TelegramChannelsSource

        return TelegramChannelsSource(sc)
    if name == "freelance_ru":
        from .freelance_ru import FreelanceRuSource

        return FreelanceRuSource(sc)
    if name == "kadrof":
        from .kadrof import KadrofSource

        return KadrofSource(sc)
    if name == "fl_ru":
        from .fl_ru import FlRuSource

        return FlRuSource(sc)
    if name == "youdo":
        from .youdo import YoudoSource

        return YoudoSource(sc)
    if name == "kwork":
        from .kwork import KworkSource

        return KworkSource(sc)
    if name == "weblancer":
        from .weblancer import WeblancerSource

        return WeblancerSource(sc)
    if name == "profi":
        from .profi import ProfiSource

        return ProfiSource(sc)
    if name == "yandex_uslugi":
        from .yandex_uslugi import YandexUslugiSource

        return YandexUslugiSource(sc)

    raise ValueError(f"неизвестный источник: {name}")
