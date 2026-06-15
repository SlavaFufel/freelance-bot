"""Загрузка конфигурации: секреты из .env + параметры из config.yaml."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class MatchConfig:
    min_score: float = 2.0
    include_weight: float = 1.0
    boost_weight: float = 2.0
    require_in_title: bool = True
    include_keywords: list[str] = field(default_factory=list)
    boost_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)


@dataclass
class ResponderConfig:
    greeting: str = "Здравствуйте!"
    portfolio_link: str = ""
    cta: str = ""
    experience: dict[str, str] = field(default_factory=dict)


@dataclass
class Secrets:
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    hh_user_agent: str = "FreelanceBot/1.0"
    telegram_api_id: str | None = None
    telegram_api_hash: str | None = None


@dataclass
class Config:
    poll_interval_sec: int = 300
    enabled_sources: list[str] = field(default_factory=list)
    sources: dict = field(default_factory=dict)
    match: MatchConfig = field(default_factory=MatchConfig)
    responder: ResponderConfig = field(default_factory=ResponderConfig)
    secrets: Secrets = field(default_factory=Secrets)

    def source_cfg(self, name: str) -> dict:
        """Параметры конкретного источника (или пустой dict)."""
        return self.sources.get(name, {}) or {}


def load_config(path: str | Path | None = None) -> Config:
    """Прочитать .env и config.yaml, собрать объект Config."""
    load_dotenv(ROOT / ".env")

    cfg_path = Path(path) if path else ROOT / "config.yaml"
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    raw_match = data.get("match", {}) or {}
    match = MatchConfig(
        min_score=float(raw_match.get("min_score", 2.0)),
        include_weight=float(raw_match.get("include_weight", 1.0)),
        boost_weight=float(raw_match.get("boost_weight", 2.0)),
        require_in_title=bool(raw_match.get("require_keyword_in_title", True)),
        include_keywords=list(raw_match.get("include_keywords", []) or []),
        boost_keywords=list(raw_match.get("boost_keywords", []) or []),
        exclude_keywords=list(raw_match.get("exclude_keywords", []) or []),
    )

    raw_resp = data.get("responder", {}) or {}
    responder = ResponderConfig(
        greeting=raw_resp.get("greeting", "Здравствуйте!"),
        portfolio_link=raw_resp.get("portfolio_link", ""),
        cta=raw_resp.get("cta", ""),
        experience=dict(raw_resp.get("experience", {}) or {}),
    )

    secrets = Secrets(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        hh_user_agent=os.getenv("HH_USER_AGENT", "FreelanceBot/1.0").strip(),
        telegram_api_id=(os.getenv("TELEGRAM_API_ID") or None),
        telegram_api_hash=(os.getenv("TELEGRAM_API_HASH") or None),
    )

    # Источники можно переопределить переменной окружения (удобно для хостинга:
    # на заграничном IP hh даёт 403, поэтому в GitHub Actions оставляем только то,
    # что работает отовсюду). Формат: ENABLED_SOURCES=telegram_channels,freelance_ru
    enabled = list(data.get("enabled_sources", []) or [])
    env_sources = os.getenv("ENABLED_SOURCES")
    if env_sources:
        enabled = [s.strip() for s in env_sources.split(",") if s.strip()]

    return Config(
        poll_interval_sec=int(data.get("poll_interval_sec", 300)),
        enabled_sources=enabled,
        sources=dict(data.get("sources", {}) or {}),
        match=match,
        responder=responder,
        secrets=secrets,
    )
