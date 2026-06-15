import bot.commands as commands
from bot.storage import Storage


def test_process_updates_registers_by_key(tmp_path, monkeypatch):
    sent = []

    updates = {
        "ok": True,
        "result": [
            {"update_id": 10, "message": {"chat": {"id": 555, "username": "frienda"}, "text": "/start"}},
            {"update_id": 11, "message": {"chat": {"id": 555, "username": "frienda"}, "text": "secret-key"}},
            {"update_id": 12, "message": {"chat": {"id": 777, "first_name": "Rand"}, "text": "привет"}},
        ],
    }

    def fake_api(token, method, **params):
        if method == "getUpdates":
            return updates
        if method == "sendMessage":
            sent.append((str(params["chat_id"]), params["text"]))
            return {"ok": True}
        return {"ok": True}

    monkeypatch.setattr(commands, "_api", fake_api)

    db = Storage(tmp_path / "t.db")
    new_subs = commands.process_updates("token", db, access_key="secret-key", owner_chat_id="999")

    # друг по ключу подписан, владелец подписан, случайный — нет
    assert new_subs == 1
    assert set(db.active_subscribers()) == {"999", "555"}
    assert not db.is_subscriber("777")

    # offset продвинут за последний update
    assert db.get_meta("tg_offset") == "13"

    # друг получил приветствие и подтверждение, случайный — подсказку
    recipients = [c for c, _ in sent]
    assert "555" in recipients and "777" in recipients
    db.close()


def test_process_updates_stop(tmp_path, monkeypatch):
    updates = {
        "ok": True,
        "result": [
            {"update_id": 5, "message": {"chat": {"id": 555, "username": "a"}, "text": "secret"}},
            {"update_id": 6, "message": {"chat": {"id": 555, "username": "a"}, "text": "/stop"}},
        ],
    }
    monkeypatch.setattr(commands, "_api",
                        lambda t, m, **p: updates if m == "getUpdates" else {"ok": True})
    db = Storage(tmp_path / "t.db")
    commands.process_updates("token", db, access_key="secret", owner_chat_id=None)
    # подписался ключом, затем отписался /stop
    assert not db.is_subscriber("555")
    db.close()
