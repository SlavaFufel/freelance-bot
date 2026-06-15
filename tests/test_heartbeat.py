import run
from bot.config import Config, Secrets
from bot.storage import Storage


class StubNotifier:
    def __init__(self):
        self.sent: list[tuple[str, list | None]] = []

    def send_text(self, text, chat_ids=None):
        self.sent.append((text, chat_ids))
        return True


class StubPipeline:
    def __init__(self, storage, notifier):
        self.storage = storage
        self.notifier = notifier


def make_cfg() -> Config:
    cfg = Config()
    cfg.secrets = Secrets(telegram_chat_id="999")
    cfg.heartbeat_idle = True
    cfg.heartbeat_interval_minutes = 60
    return cfg


def test_heartbeat_sends_to_owner_when_idle(tmp_path):
    storage = Storage(tmp_path / "t.db")
    notifier = StubNotifier()
    run.heartbeat(make_cfg(), StubPipeline(storage, notifier), sent=0)
    assert len(notifier.sent) == 1
    assert notifier.sent[0][1] == ["999"]   # только владельцу


def test_heartbeat_skipped_when_orders_sent(tmp_path):
    storage = Storage(tmp_path / "t.db")
    notifier = StubNotifier()
    run.heartbeat(make_cfg(), StubPipeline(storage, notifier), sent=3)
    assert notifier.sent == []
    assert storage.get_meta("last_notify") is not None   # таймер сброшен


def test_heartbeat_throttled_within_interval(tmp_path):
    storage = Storage(tmp_path / "t.db")
    notifier = StubNotifier()
    cfg = make_cfg()
    run.heartbeat(cfg, StubPipeline(storage, notifier), sent=0)  # шлёт
    run.heartbeat(cfg, StubPipeline(storage, notifier), sent=0)  # рано — молчит
    assert len(notifier.sent) == 1


def test_heartbeat_disabled(tmp_path):
    storage = Storage(tmp_path / "t.db")
    notifier = StubNotifier()
    cfg = make_cfg()
    cfg.heartbeat_idle = False
    run.heartbeat(cfg, StubPipeline(storage, notifier), sent=0)
    assert notifier.sent == []
