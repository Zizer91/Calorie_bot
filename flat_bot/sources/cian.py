"""ЦИАН — внутренний JSON API поиска (тот же, что использует сайт)."""
from __future__ import annotations

import logging
from typing import Iterable

from ..extract import first, material_from_word, to_float, to_int
from ..models import Listing
from .base import Source

log = logging.getLogger(__name__)

API = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"
SPB_REGION = 2


def build_query(s, page: int) -> dict:
    rooms = [r for r in s.rooms if 1 <= r <= 5]
    q = {
        "_type": "flatsale",
        "engine_version": {"type": "term", "value": 2},
        "region": {"type": "terms", "value": [SPB_REGION]},
        "room": {"type": "terms", "value": rooms},
        "price": {"type": "range", "value": {"lte": s.max_price}},
        "foot_min": {"type": "range", "value": {"lte": s.max_metro_walk_min}},
        "only_foot": {"type": "term", "value": "2"},
        "sort": {"type": "term", "value": "creation_date_desc"},
        "page": {"type": "term", "value": page},
    }
    return {"jsonQuery": q}


def parse_offer(o: dict) -> Listing | None:
    oid = o.get("cianId") or o.get("id")
    url = o.get("fullUrl")
    if not oid or not url:
        return None
    undergrounds = (o.get("geo") or {}).get("undergrounds") or []
    walk = [u for u in undergrounds if (u.get("transportType") or "walk") == "walk" and u.get("time") is not None]
    best = min(walk, key=lambda u: u["time"]) if walk else None
    building = o.get("building") or {}
    geo = o.get("geo") or {}
    parts = geo.get("address") or []
    street = [a for a in parts if a.get("type") in ("street", "house")]
    address = ", ".join(a.get("fullName") or a.get("name") or "" for a in (street or parts)) or geo.get("userInput", "")
    rooms = o.get("roomsCount")
    flat_type = (o.get("flatType") or "").lower()
    if flat_type == "studio":
        rooms = 0
    return Listing(
        source="cian",
        external_id=str(oid),
        url=url,
        price=to_int(first(o, "bargainTerms.priceRur", "bargainTerms.price")),
        rooms=rooms,
        is_euro=bool(o.get("isEuroFlat")) or "euro" in flat_type,
        total_area=to_float(o.get("totalArea")),
        kitchen_area=to_float(o.get("kitchenArea")),
        floor=to_int(o.get("floorNumber")),
        floors_total=to_int(building.get("floorsCount")),
        material=material_from_word(building.get("materialType")),
        build_year=to_int(building.get("buildYear")),
        address=address,
        metro=best.get("name") if best else None,
        metro_walk_min=to_int(best.get("time")) if best else None,
        description=o.get("description") or "",
    )


class Cian(Source):
    name = "cian"

    def search(self) -> Iterable[Listing]:
        headers = {"Origin": "https://spb.cian.ru", "Referer": "https://spb.cian.ru/"}
        for page in range(1, self.s.pages_per_source + 1):
            r = self.http.post_json(API, build_query(self.s, page), headers=headers,
                                    dump=f"cian_p{page}.json")
            offers = first(r.json(), "data.offersSerialized", default=[])
            if not offers:
                break
            for o in offers:
                l = parse_offer(o)
                if l:
                    yield l
