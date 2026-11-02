from flat_bot import sources
from flat_bot.config import Settings
from flat_bot.models import Listing, Material
from flat_bot.runner import Runner
from flat_bot.sources.base import Source
from flat_bot.storage import Storage


class Collect:
    def __init__(self):
        self.msgs = []

    def send(self, text):
        self.msgs.append(text)
        return True


def L(src, eid, **kw):
    d = dict(source=src, external_id=eid, url=f"https://{src}/{eid}", price=10_000_000, rooms=2,
             total_area=50, floor=3, floors_total=9, material=Material.BRICK, metro_walk_min=10,
             address="ул. Типанова, 10", metro="Московская")
    d.update(kw)
    return Listing(**d)


class FakeA(Source):
    name = "fake_a"
    detail_calls = 0

    def search(self):
        yield L("fake_a", "1")
        yield L("fake_a", "2", price=20_000_000)  # дорого
        yield L("fake_a", "3", rooms=1, kitchen_area=None, total_area=40, floor=7)  # нужна кухня

    def details(self, l):
        FakeA.detail_calls += 1
        return L(l.source, l.external_id, kitchen_area=15)


class FakeB(Source):
    name = "fake_b"

    def search(self):
        yield L("fake_b", "x", total_area=50.2, price=9_900_000)  # та же квартира, что fake_a/1


def test_full_run_no_repeats(monkeypatch):
    monkeypatch.setitem(sources.REGISTRY, "fake_a", FakeA)
    monkeypatch.setitem(sources.REGISTRY, "fake_b", FakeB)
    import flat_bot.runner as runner_mod
    monkeypatch.setattr(runner_mod, "REGISTRY", sources.REGISTRY)

    s = Settings(sources=["fake_a", "fake_b"])
    db, out = Storage(":memory:"), Collect()
    r = Runner(s, db, out, http=object())

    assert r.run_once() == 2  # fake_a/1 и fake_a/3 (кухня 15 после уточнения); fake_b/x — дубль
    assert FakeA.detail_calls == 1
    assert "Евро" not in out.msgs[0] and "fake_a/1" in out.msgs[0]

    # второй проход — ничего нового, страницы объявлений повторно не открываются
    assert r.run_once() == 0
    assert FakeA.detail_calls == 1
    assert len(out.msgs) == 2
