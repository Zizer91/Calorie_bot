import json

from flat_bot.models import Material
from flat_bot.sources import avito, cian, domclick, yandex
from flat_bot.sources.generic_html import cards_from_links


def test_cian_offer():
    o = {
        "cianId": 301, "fullUrl": "https://spb.cian.ru/sale/flat/301/",
        "bargainTerms": {"price": 11_000_000}, "roomsCount": 1, "totalArea": "41.5",
        "kitchenArea": "14", "floorNumber": 4, "flatType": "rooms",
        "building": {"floorsCount": 9, "materialType": "panel", "buildYear": 1983},
        "geo": {"address": [{"type": "location", "fullName": "Санкт-Петербург"},
                            {"type": "street", "fullName": "улица Ленсовета"},
                            {"type": "house", "fullName": "81"}],
                "undergrounds": [{"name": "Звёздная", "time": 20, "transportType": "transport"},
                                 {"name": "Московская", "time": 12, "transportType": "walk"}]},
        "description": "Хорошая квартира",
    }
    l = cian.parse_offer(o)
    assert (l.external_id, l.price, l.rooms, l.total_area, l.kitchen_area) == ("301", 11_000_000, 1, 41.5, 14)
    assert (l.material, l.build_year, l.floors_total) == (Material.PANEL, 1983, 9)
    assert (l.metro, l.metro_walk_min) == ("Московская", 12)
    assert l.address == "улица Ленсовета, 81"


AVITO_HTML = """
<div data-marker="item" data-item-id="4001">
  <a data-marker="item-title" href="/sankt-peterburg/kvartiry/2-k_kvartira_54m_59et._4001?context=x"
     title="2-к. квартира, 54 м², 5/9 эт.">2-к. квартира, 54 м², 5/9 эт.</a>
  <meta itemprop="price" content="10500000">
  <div data-marker="item-address"><div>
    <p><span>Московский пр-т, 200</span></p>
    <p><span><i></i></span><span>Московская</span><span>6–10 мин.</span></p>
  </div></div>
</div>"""


def test_avito_search():
    [l] = avito.parse_search_html(AVITO_HTML)
    assert l.url == "https://www.avito.ru/sankt-peterburg/kvartiry/2-k_kvartira_54m_59et._4001"
    assert (l.price, l.rooms, l.total_area, l.floor, l.floors_total) == (10_500_000, 2, 54, 5, 9)
    assert (l.metro, l.metro_walk_min, l.address) == ("Московская", 10, "Московский пр-т, 200")


def test_yandex_state():
    state = {"search": {"offers": {"entities": [{
        "offerId": "777", "price": {"value": 9_900_000}, "roomsTotal": 2, "area": {"value": 47},
        "kitchenSpace": {"value": 7}, "floorsOffered": [3], "floorsTotal": 5,
        "building": {"buildingType": "BRICK", "builtYear": 1962},
        "location": {"address": "Санкт-Петербург, ул. Типанова, 10",
                     "metroList": [{"name": "Московская", "timeToMetro": 9, "metroTransport": "ON_FOOT"}]},
    }]}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>'
    [l] = yandex.parse_search_html(html)
    assert (l.url, l.price, l.material, l.metro_walk_min, l.floor) == (
        "https://realty.yandex.ru/offer/777/", 9_900_000, Material.BRICK, 9, 3)


def test_domclick_offer():
    o = {"id": 55, "price_info": {"price": 11_700_000},
         "object_info": {"rooms": 3, "area": 60.2, "kitchen_area": 8, "floor": 2},
         "house": {"floors": 12, "wall_type": "Панельный", "build_year": 1979},
         "address": {"display_name": "Санкт-Петербург, пр. Ветеранов, 100",
                     "subways": [{"name": "Проспект Ветеранов", "time_on_foot": 14}]}}
    l = domclick.parse_offer(o)
    assert (l.rooms, l.material, l.build_year, l.metro_walk_min, l.floors_total) == (3, Material.PANEL, 1979, 14, 12)


def test_generic_cards():
    html = """<ul><li class="card"><a href="/realty/123456/"><img></a>
      <div>2-комн. квартира 52 м² 7/10 эт.</div><div>11 100 000 ₽</div><div>Ладожская 8 мин пешком</div></li>
      <li class="card"><a href="/realty/123457/">x</a><div>3-комн. квартира 70 м²</div><div>13 000 000 ₽</div></li></ul>"""
    a, b = cards_from_links(html, "https://spb.etagi.com", "etagi", r"/realty/(\d{4,})/?")
    assert (a.external_id, a.rooms, a.total_area, a.price, a.metro_walk_min) == ("123456", 2, 52, 11_100_000, 8)
    assert a.url == "https://spb.etagi.com/realty/123456/"
    assert b.price == 13_000_000
