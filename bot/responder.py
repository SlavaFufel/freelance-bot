"""Генерация черновика отклика под заказ — шаблоны без ИИ (требования п.2, п.3)."""
from __future__ import annotations

from pathlib import Path
from string import Template

from .config import ResponderConfig
from .matcher import normalize
from .models import Order

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Категория -> подстроки-маркеры в нормализованном тексте. Порядок важен:
# проверяем сверху вниз, берём первую сработавшую.
CATEGORY_MARKERS: list[tuple[str, list[str]]] = [
    ("gamedev", ["unity", "юнити", "unity3d", "gamedev", "геймдев",
                 "разработка игр", "игровой движок", "unreal", "игровую механик"]),
    ("bot", ["телеграм-бот", "телеграм бот", "телеграмм бот", "telegram бот",
             "tg бот", "чат-бот", "чатбот", "aiogram", "discord", "дискорд",
             "бот для", "бота для", "напис бот", "сдела бот"]),
    ("automation", ["парсер", "парсинг", "спарсить", "скрейп", "scraping",
                    "scrapy", "автоматизац", "автоматизир", "скрипт",
                    "selenium", "выгрузк", "сбор данных"]),
    ("fix", ["доработ", "правк", "исправ", "починить", "почини",
             "ошибк", "доделать", "допилить", "переделать сайт"]),
    ("ecommerce", ["интернет магазин", "интернет-магазин", "магазин", "ecommerce",
                   "корзин", "каталог товар", "маркетплейс"]),
    ("webapp", ["веб приложение", "веб-приложение", "web app", "crm", "erp",
                "личный кабинет", "dashboard"]),
    ("landing", ["лендинг", "лэндинг", "landing", "одностраничник",
                 "сайт визитка", "сайт-визитка", "визитк", "промо страниц"]),
]

# Технологии/требования, которые приятно явно упомянуть в отклике.
TECH_TERMS = [
    "wordpress", "tilda", "тильда", "bitrix", "битрикс", "react", "vue",
    "next", "angular", "laravel", "django", "fastapi", "flask", "php",
    "node", "html", "css", "javascript", "typescript", "python",
    "адаптив", "figma", "фигма", "seo", "aiogram", "telethon", "selenium",
    "playwright", "scrapy", "api", "postgresql", "docker",
    "unity", "юнити", "unity3d", "unreal", "gamedev",
]


class Responder:
    def __init__(self, cfg: ResponderConfig, templates_dir: Path = TEMPLATES_DIR):
        self.cfg = cfg
        self.templates_dir = templates_dir
        self._cache: dict[str, Template] = {}

    # --- классификация ---
    @staticmethod
    def detect_category(order: Order) -> str:
        text = normalize(order.raw_text)
        for category, markers in CATEGORY_MARKERS:
            for m in markers:
                if f" {m} " in text or f" {m}" in text or f"{m} " in text:
                    return category
        return "generic"

    @staticmethod
    def detect_tech(order: Order) -> list[str]:
        text = normalize(order.raw_text)
        found: list[str] = []
        for term in TECH_TERMS:
            t = term.replace("ё", "е")
            if f" {t} " in text or f" {t}" in text or f"{t} " in text:
                # показываем оригинальное написание термина
                pretty = term if not term.isascii() else term.capitalize()
                if pretty not in found:
                    found.append(pretty)
        return found

    # --- рендер ---
    def _load_template(self, category: str) -> Template:
        if category in self._cache:
            return self._cache[category]
        path = self.templates_dir / f"{category}.txt"
        if not path.exists():
            path = self.templates_dir / "generic.txt"
        tmpl = Template(path.read_text(encoding="utf-8"))
        self._cache[category] = tmpl
        return tmpl

    @property
    def is_prompt(self) -> bool:
        return (self.cfg.output or "prompt").lower() == "prompt"

    def render(self, order: Order) -> str:
        if self.is_prompt:
            return self.build_prompt(order)
        return self._render_text(order)

    def build_prompt(self, order: Order) -> str:
        """Готовый промпт для Gemini: пользователь копирует его и получает отклик."""
        category = self.detect_category(order)
        techs = self.detect_tech(order)
        experience = self.cfg.experience.get(category) or self.cfg.experience.get(
            "generic", ""
        )
        profile = self.cfg.profile.strip() or experience

        desc = (order.description or "").strip()
        if len(desc) > 900:
            desc = desc[:900].rstrip() + "…"

        lines = [
            "Ты — опытный фрилансер-разработчик. Напиши на русском короткий, цепляющий "
            "отклик на фриланс-заказ ниже — такой, чтобы заказчик захотел ответить именно мне.",
            "",
            "ОБО МНЕ:",
            profile,
        ]
        if experience and experience != profile:
            lines.append(f"Особенно релевантно по этой задаче: {experience}")
        if self.cfg.portfolio_link:
            lines.append(f"Портфолио: {self.cfg.portfolio_link}")
        if techs:
            lines.append("Упомянутые в заказе технологии: " + ", ".join(techs))
        lines += [
            "",
            f"ЗАКАЗ (источник: {order.source}):",
            f"Заголовок: {order.title}",
            f"Описание: {desc or '—'}",
            f"Бюджет: {order.budget or 'не указан'}",
            f"Ссылка: {order.url}",
            "",
            "КАК НАПИСАТЬ ОТКЛИК:",
            "- Обращайся к заказчику на «вы», по делу, без воды и канцелярита.",
            "- Покажи, что понял суть задачи; упомяни 1–2 релевантных пункта моего опыта.",
            "- Предложи следующий шаг (короткий созвон/обсуждение) и задай 1 уточняющий "
            "вопрос, если уместно.",
            "- 4–7 предложений, дружелюбно и профессионально.",
            "- Не выдумывай факты обо мне сверх указанного выше.",
            "- В ответе верни только текст отклика, без пояснений.",
        ]
        return "\n".join(lines).strip()

    def _render_text(self, order: Order) -> str:
        category = self.detect_category(order)
        techs = self.detect_tech(order)

        if techs:
            tech_line = "Вижу в задаче: " + ", ".join(techs) + " — с этим работаю."
        else:
            tech_line = ""

        experience = self.cfg.experience.get(category) or self.cfg.experience.get(
            "generic", ""
        )

        mapping = {
            "greeting": self.cfg.greeting,
            "relevant_experience": experience,
            "tech_line": tech_line,
            "portfolio_link": self.cfg.portfolio_link,
            "cta": self.cfg.cta,
        }
        text = self._load_template(category).safe_substitute(mapping)
        # убираем пустые строки, оставшиеся от незаполненного tech_line
        lines = [ln.rstrip() for ln in text.splitlines()]
        cleaned: list[str] = []
        for ln in lines:
            if ln == "" and cleaned and cleaned[-1] == "":
                continue
            cleaned.append(ln)
        return "\n".join(cleaned).strip()
