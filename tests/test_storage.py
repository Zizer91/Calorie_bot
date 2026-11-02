from flat_bot.models import Listing
from flat_bot.storage import Storage, house_key, metro_key


def mk(source, eid, **kw):
    base = dict(source=source, external_id=eid, url=f"https://{source}/{eid}", price=10_500_000,
                rooms=2, total_area=54.3, floor=5, floors_total=9,
                address="Санкт-Петербург, Московский пр., 200", metro="Московская")
    base.update(kw)
    return Listing(**base)


def test_house_key():
    assert house_key("Санкт-Петербург, Московский пр., 200") == "200"
    assert house_key("СПб, 7-я линия В.О., д. 34") == "34"
    assert house_key("ул. Ленина, 5к2") == "5"
    assert metro_key("м. Московская") == metro_key("Московская")


def test_exact_and_cross_site_duplicates():
    db = Storage(":memory:")
    a = mk("cian", "1")
    assert not db.was_sent(a) and db.find_cross_duplicate(a) is None
    db.mark_sent(a)
    assert db.was_sent(a)
    # та же квартира на Авито: площадь 54, цена чуть другая, адрес в другом формате
    b = mk("avito", "x", total_area=54.0, price=10_300_000, address="Московский проспект, 200", metro="м. Московская")
    assert db.find_cross_duplicate(b) == a.url
    # другой дом — не дубль
    assert db.find_cross_duplicate(mk("avito", "y", address="Московский пр., 198")) is None
    # другой этаж — не дубль
    assert db.find_cross_duplicate(mk("avito", "z", floor=6)) is None


def test_seen_price():
    db = Storage(":memory:")
    l = mk("cian", "1")
    assert db.seen_price(l) == (False, None)
    db.mark_seen(l)
    assert db.seen_price(l) == (True, 10_500_000)
