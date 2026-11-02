"""ДомКлик — JSON API сервиса объявлений."""
from __future__ import annotations

from typing import Iterable

from ..extract import first, material_from_word, to_float, to_int
from ..models import Listing
from .base import Source

API = "https://offers-service.domclick.ru/research/v5/offers/"
LIMIT = 30


def parse_offer(o: dict) -> Listing | None:
    oid = o.get("id")
    if not oid:
        return None
    path = first(o, "path", "url", default="")
    url = path if str(path).startswith("http") else f"https://domclick.ru/card/sale__flat__{oid}"
    metros = first(o, "address.subways", "location.subways", "subways", "metro", default=[]) or []
    if isinstance(metros, dict):
        metros = [metros]
    best_name, best_walk = None, None
    for m in metros:
        t = to_int(first(m, "time_on_foot", "timeOnFoot", "time", "duration"))
        if t is not None and (best_walk is None or t < best_walk):
            best_name, best_walk = first(m, "name", "title"), t
    rooms = to_int(first(o, "object_info.rooms", "objectInfo.rooms", "rooms"))
    is_studio = bool(first(o, "object_info.is_studio", "objectInfo.isStudio", default=False))
    return Listing(
        source="domclick",
        external_id=str(oid),
        url=url,
        price=to_int(first(o, "price_info.price", "priceInfo.price", "price")),
        rooms=0 if is_studio else rooms,
        total_area=to_float(first(o, "object_info.area", "objectInfo.area", "area")),
        kitchen_area=to_float(first(o, "object_info.kitchen_area", "objectInfo.kitchenArea", "kitchen_area")),
        floor=to_int(first(o, "object_info.floor", "objectInfo.floor", "floor")),
        floors_total=to_int(first(o, "house.floors", "house_info.floors", "floors")),
        material=material_from_word(first(o, "house.wall_type", "house_info.wall_type", "house.material", "wall_type")),
        build_year=to_int(first(o, "house.build_year", "house_info.build_year", "house.buildYear")),
        address=first(o, "address.display_name", "address.short_display_name", "address.name", default=""),
        metro=best_name,
        metro_walk_min=best_walk,
        description=first(o, "description", default=""),
    )


class Domclick(Source):
    name = "domclick"

    def search(self) -> Iterable[Listing]:
        headers = {"Origin": "https://domclick.ru", "Referer": "https://domclick.ru/"}
        rooms = [r for r in self.s.rooms if r >= 1]
        for page in range(self.s.pages_per_source):
            params = [
                ("address", self.s.domclick_address_guid),
                ("offer_type", "flat"),
                ("deal_type", "sale"),
                ("category", "living"),
                ("sale_price__lte", self.s.max_price),
                ("time_on_foot__lte", self.s.max_metro_walk_min),
                ("sort", "published"),
                ("sort_dir", "desc"),
                ("offset", page * LIMIT),
                ("limit", LIMIT),
                *[("rooms", r) for r in rooms],
            ]
            r = self.http.get(API, params=params, headers=headers, dump=f"domclick_p{page}.json")
            items = first(r.json(), "result.items", "items", default=[])
            if not items:
                break
            for o in items:
                l = parse_offer(o)
                if l:
                    yield l
