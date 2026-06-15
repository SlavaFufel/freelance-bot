from bot.config import ResponderConfig
from bot.models import Order
from bot.responder import Responder


def make_responder() -> Responder:
    cfg = ResponderConfig(
        greeting="Здравствуйте!",
        portfolio_link="https://port.folio/me",
        cta="Когда удобно созвониться?",
        experience={
            "landing": "Делаю лендинги.",
            "ecommerce": "Делаю магазины.",
            "fix": "Чиню сайты.",
            "webapp": "Делаю веб-приложения.",
            "bot": "Делаю Telegram-ботов.",
            "automation": "Делаю парсеры и автоматизацию.",
            "generic": "Веб-разработка.",
        },
    )
    return Responder(cfg)


def order(title, desc=""):
    return Order(source="t", external_id="1", title=title, description=desc, url="u")


def test_detect_category_landing():
    r = make_responder()
    assert r.detect_category(order("Нужен лендинг для кофейни")) == "landing"


def test_detect_category_ecommerce():
    r = make_responder()
    assert r.detect_category(order("Создать интернет-магазин обуви")) == "ecommerce"


def test_detect_category_fix():
    r = make_responder()
    assert r.detect_category(order("Доработка существующего сайта, правки")) == "fix"


def test_detect_category_bot():
    r = make_responder()
    assert r.detect_category(order("Нужен телеграм-бот для записи клиентов")) == "bot"
    assert r.detect_category(order("Написать бота на aiogram с оплатой")) == "bot"


def test_detect_category_automation():
    r = make_responder()
    assert r.detect_category(order("Нужен парсер сайта с выгрузкой в Excel")) == "automation"
    assert r.detect_category(order("Автоматизация: скрипт на Python")) == "automation"


def test_detect_category_generic():
    r = make_responder()
    assert r.detect_category(order("Нужен специалист")) == "generic"


def test_detect_tech():
    r = make_responder()
    techs = r.detect_tech(order("Сайт на WordPress, нужна адаптивная верстка и React"))
    low = [t.lower() for t in techs]
    assert "wordpress" in low
    assert "react" in low


def test_render_uses_category_experience_and_tech():
    r = make_responder()
    text = r.render(order("Нужен лендинг на Tilda", "адаптив обязателен"))
    assert "Делаю лендинги." in text          # опыт нужной категории
    assert "Tilda" in text or "тильда" in text.lower()  # tech_line подставлен
    assert "https://port.folio/me" in text    # портфолио
    assert "Когда удобно созвониться?" in text # cta


def test_render_bot_category_uses_bot_template():
    r = make_responder()
    text = r.render(order("Нужен телеграм-бот на aiogram", "приём оплаты"))
    assert "Делаю Telegram-ботов." in text   # опыт категории bot
    assert "aiogram" in text.lower()          # tech_line подставлен
    assert "https://port.folio/me" in text


def test_render_without_tech_has_no_dangling_blank_lines():
    r = make_responder()
    text = r.render(order("Нужен сайт", ""))
    assert "\n\n\n" not in text  # пустые строки схлопнуты
