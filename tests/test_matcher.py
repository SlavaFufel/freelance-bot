from bot.config import MatchConfig
from bot.matcher import Matcher
from bot.models import Order


def make_matcher(**overrides) -> Matcher:
    cfg = MatchConfig(
        min_score=2.0,
        include_weight=1.0,
        boost_weight=2.0,
        include_keywords=["сайт", "разработка", "магазин", "доработка"],
        boost_keywords=["сайт", "лендинг", "react", "интернет-магазин"],
        exclude_keywords=["логотип", "копирайтинг", "ремонт квартир"],
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return Matcher(cfg)


def order(title, desc=""):
    return Order(source="t", external_id="1", title=title, description=desc, url="u")


def test_web_order_passes_and_scores_high():
    m = make_matcher()
    res = m.evaluate(order("Разработка сайта-лендинга на React"))
    assert res.passed
    # include: сайт, разработка (+ boost: сайт, лендинг, react)
    assert res.score >= 4.0
    assert "сайт" in res.boosted


def test_exclude_rejects():
    m = make_matcher()
    res = m.evaluate(order("Нужен логотип и копирайтинг для сайта"))
    assert not res.passed
    assert res.reason == "exclude"


def test_no_include_rejects():
    m = make_matcher()
    res = m.evaluate(order("Ищу бухгалтера на удаленку"))
    assert not res.passed
    assert res.reason == "no-include"


def test_below_threshold():
    # одно include-слово без boost: score=1.0 < min_score=2.0
    m = make_matcher()
    res = m.evaluate(order("Требуется доработка отчёта"))
    assert not res.passed
    assert res.reason == "below-threshold"
    assert res.score == 1.0


def test_yo_normalization():
    m = make_matcher(include_keywords=["вёрстка"], boost_keywords=[], min_score=1.0)
    res = m.evaluate(order("Нужна верстка макета"))  # без ё
    assert res.passed


def test_bot_and_automation_keywords():
    m = make_matcher(
        include_keywords=["бот", "парсер", "автоматизац"],
        boost_keywords=["бот", "парсер"],
        min_score=1.0,
    )
    assert m.evaluate(order("Нужен телеграм бот для записи")).passed
    assert m.evaluate(order("Сделать парсер маркетплейса")).passed
    assert m.evaluate(order("Автоматизация выгрузки данных")).passed
    # "бот" не должно ловиться внутри "работу"
    assert not m.evaluate(order("Ищу работу удалённо")).passed


def test_permanent_job_excluded():
    m = make_matcher(
        include_keywords=["сайт", "python", "unity"],
        boost_keywords=[],
        exclude_keywords=["senior", "в штат", "full-time", "оклад"],
        min_score=1.0,
    )
    # вакансия на постоянную работу — режется
    assert not m.evaluate(order("Senior Python разработчик в штат")).passed
    # разовый заказ — проходит
    assert m.evaluate(order("Нужно доработать сайт на Python")).passed


def test_unity_included():
    m = make_matcher(include_keywords=["unity", "юнити"], boost_keywords=["unity"], min_score=1.0)
    assert m.evaluate(order("Нужен разработчик Unity на проект")).passed


def test_substring_not_matched_inside_word():
    # "сайт" не должно ловиться в "дизайнсайтище"? проверим обратное: целое слово ок
    m = make_matcher(boost_keywords=[], include_keywords=["веб"], min_score=1.0)
    assert m.evaluate(order("нужен веб разработчик")).passed
    assert not m.evaluate(order("требуется человек")).passed
