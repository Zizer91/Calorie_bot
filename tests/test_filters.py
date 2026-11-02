from flat_bot.config import Settings
from flat_bot.filters import Verdict, evaluate
from flat_bot.models import Listing, Material

S = Settings()


def mk(**kw):
    base = dict(source="t", external_id="1", url="u", price=10_000_000, rooms=2, total_area=50,
                material=Material.BRICK, metro_walk_min=10, floor=3, floors_total=9)
    base.update(kw)
    return Listing(**base)


def v(l, final=False):
    return evaluate(l, S, final).verdict


def test_basic_pass_and_price():
    assert v(mk()) == Verdict.PASS
    assert v(mk(price=11_800_000)) == Verdict.PASS
    assert v(mk(price=11_800_001)) == Verdict.REJECT


def test_rooms():
    assert v(mk(rooms=3)) == Verdict.PASS
    assert v(mk(rooms=4)) == Verdict.REJECT
    assert v(mk(rooms=0)) == Verdict.REJECT


def test_one_room_needs_big_kitchen():
    assert v(mk(rooms=1, total_area=40, kitchen_area=14)) == Verdict.PASS
    assert v(mk(rooms=1, total_area=40, kitchen_area=9)) == Verdict.REJECT
    assert v(mk(rooms=1, total_area=40)) == Verdict.NEED_MORE
    assert v(mk(rooms=1, total_area=40), final=True) == Verdict.REJECT
    assert v(mk(rooms=1, total_area=30, kitchen_area=14)) == Verdict.REJECT
    assert v(mk(rooms=1, is_euro=True, total_area=40)) == Verdict.PASS


def test_building():
    assert v(mk(material=Material.PANEL, build_year=1975)) == Verdict.PASS
    assert v(mk(material=Material.PANEL, build_year=1965)) == Verdict.REJECT
    assert v(mk(material=Material.PANEL)) == Verdict.NEED_MORE
    assert v(mk(material=Material.MONOLITH)) == Verdict.REJECT
    assert v(mk(material=Material.MONOLITH_BRICK)) == Verdict.PASS
    assert v(mk(material=Material.UNKNOWN)) == Verdict.NEED_MORE
    r = evaluate(mk(material=Material.UNKNOWN), S, final=True)
    assert r.verdict == Verdict.PASS and r.warnings


def test_metro():
    assert v(mk(metro_walk_min=15)) == Verdict.PASS
    assert v(mk(metro_walk_min=16)) == Verdict.REJECT
    assert v(mk(metro_walk_min=None), final=True) == Verdict.REJECT
