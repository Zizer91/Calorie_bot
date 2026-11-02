"""Яндекс Недвижимость — данные выдачи лежат в JSON-состоянии страницы."""
from __future__ import annotations

from typing import Iterable

from ..extract import embedded_json, first, iter_dicts, material_from_word, to_float, to_int
from ..models import Listing
from .base import Source


def parse_offer(o: dict) -> Listing | None:
    oid = o.get("offerId")
    if not oid:
        return None
    loc = o.get("location") or {}
    metros = list(loc.get("metroList") or [])
    if loc.get("metro"):
        metros.append(loc["metro"])
    best_name, best_walk = None, None
    for m in metros:
        if (m.get("metroTransport") or "ON_FOOT") != "ON_FOOT":
            continue
        t = to_int(m.get("timeToMetro"))
        if t is not None and (best_walk is None or t < best_walk):
            best_name, best_walk = m.get("name"), t
    floors = o.get("floorsOffered") or []
    building = o.get("building") or {}
    rooms = to_int(o.get("roomsTotal"))
    if o.get("roomsTotalKey") == "STUDIO" or (o.get("house") or {}).get("studio"):
        rooms = 0
    return Listing(
        source="yandex",
        external_id=str(oid),
        url=f"https://realty.yandex.ru/offer/{oid}/",
        price=to_int(first(o, "price.value", "price.valueForWhole")),
        rooms=rooms,
        total_area=to_float(first(o, "area.value")),
        kitchen_area=to_float(first(o, "kitchenSpace.value")),
        floor=to_int(floors[0]) if floors else None,
        floors_total=to_int(o.get("floorsTotal")),
        material=material_from_word(building.get("buildingType")),
        build_year=to_int(building.get("builtYear")),
        address=loc.get("address") or loc.get("geocoderAddress") or "",
        metro=best_name,
        metro_walk_min=best_walk,
        description=o.get("description") or "",
    )


def parse_search_html(html: str) -> list[Listing]:
    out, ids = [], set()
    for state in embedded_json(html):
        for d in iter_dicts(state):
            if "offerId" in d and "price" in d and ("roomsTotal" in d or "area" in d):
                l = parse_offer(d)
                if l and l.external_id not in ids:
                    ids.add(l.external_id)
                    out.append(l)
    return out


class Yandex(Source):
    name = "yandex"

    def search(self) -> Iterable[Listing]:
        for page in range(self.s.pages_per_source):
            params = [
                ("priceMax", self.s.max_price),
                ("timeToMetro", self.s.max_metro_walk_min),
                ("metroTransport", "ON_FOOT"),
                ("sort", "DATE_DESC"),
                ("page", page),
                *[("roomsTotal", r) for r in self.s.rooms if r >= 1],
            ]
            r = self.http.get(self.s.yandex_url, params=params, dump=f"yandex_p{page}.html")
            items = parse_search_html(r.text)
            if not items:
                break
            yield from items
