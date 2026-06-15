from bot.storage import Storage


def test_subscribers(tmp_path):
    db = Storage(tmp_path / "t.db")

    assert db.active_subscribers() == []
    assert not db.is_subscriber("111")

    db.add_subscriber("111", "alice")
    db.add_subscriber("222", "bob")
    assert db.is_subscriber("111")
    assert set(db.active_subscribers()) == {"111", "222"}

    # повторная подписка не дублирует
    db.add_subscriber("111", "alice2")
    assert db.active_subscribers().count("111") == 1

    # отписка
    db.deactivate_subscriber("111")
    assert not db.is_subscriber("111")
    assert db.active_subscribers() == ["222"]

    db.close()


def test_meta(tmp_path):
    db = Storage(tmp_path / "t.db")
    assert db.get_meta("tg_offset") is None
    assert db.get_meta("tg_offset", "0") == "0"
    db.set_meta("tg_offset", "42")
    assert db.get_meta("tg_offset") == "42"
    db.set_meta("tg_offset", "43")
    assert db.get_meta("tg_offset") == "43"
    db.close()
