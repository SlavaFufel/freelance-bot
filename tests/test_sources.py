import json
from pathlib import Path

import pytest

import bot.net as net
from bot.sources.hh import HHSource
from bot.sources.telegram_channels import TelegramChannelsSource

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResp:
    def __init__(self, *, json_data=None, text=""):
        self._json = json_data
        self.text = text

    def json(self):
        return self._json


@pytest.fixture
def patch_net(monkeypatch):
    """Подменяет net.get на возврат фикстуры."""

    def _install(resp: FakeResp):
        monkeypatch.setattr(net, "get", lambda *a, **k: resp)

    return _install


def test_hh_parses_json(patch_net):
    data = json.loads((FIXTURES / "hh_vacancies.json").read_text(encoding="utf-8"))
    patch_net(FakeResp(json_data=data))

    src = HHSource({"queries": ["сайт"]}, user_agent="Test/1.0")
    orders = src.fetch()

    assert len(orders) == 2
    o = orders[0]
    assert o.external_id == "1001"
    assert "лендинг" in o.title.lower()
    assert o.url == "https://hh.ru/vacancy/1001"
    assert "50000" in (o.budget or "")
    # <highlighttext> вычищен, employer добавлен
    assert "<" not in o.description
    assert "Ромашка" in o.description


def test_telegram_parses_html(patch_net):
    html = (FIXTURES / "telegram_channel.html").read_text(encoding="utf-8")
    patch_net(FakeResp(text=html))

    src = TelegramChannelsSource({"channels": ["testchan"], "limit_per_channel": 50})
    orders = src.fetch()

    # пустой пост (testchan/12) пропущен
    assert len(orders) == 2
    ids = {o.external_id for o in orders}
    assert "testchan/10" in ids
    o = next(o for o in orders if o.external_id == "testchan/10")
    assert o.url == "https://t.me/testchan/10"
    assert o.source == "tg:testchan"
    assert "Tilda" in o.description
    # zero-width префикс вычищен — заголовок начинается с реального текста
    assert o.title.startswith("Нужен")
