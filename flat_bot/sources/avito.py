"""Авито — HTML выдачи. Кухня, тип дома и год есть только на странице объявления,
поэтому подходящие по цене/комнатам/метро карточки открываются отдельно."""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..extract import clean, parse_floor, parse_range_minutes, parse_rooms, parse_total_area, to_int
from ..models import Listing
from .base import Source

BASE = "https://www.avito.ru"


def parse_search_html(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for item in soup.select('[data-marker="item"]'):
        iid = item.get("data-item-id") or item.get("id", "").lstrip("i")
        a = item.select_one('a[data-marker="item-title"]') or item.select_one('a[itemprop="url"]')
        if not iid or not a or not a.get("href"):
            continue
        title = clean(a.get("title") or a.get_text(" "))
        price_meta = item.select_one('meta[itemprop="price"]')
        price = to_int(price_meta["content"]) if price_meta and price_meta.get("content") else None
        if price is None:
            pe = item.select_one('[data-marker="item-price"]')
            price = to_int(re.sub(r"\D", "", pe.get_text())) if pe else None
        rooms, euro = parse_rooms(title)
        floor, floors_total = parse_floor(title)

        geo = item.select_one('[data-marker="item-address"]') or item.select_one('[class*="geo-root"]')
        address, metro, walk = "", None, None
        if geo:
            for p in geo.find_all("p") or [geo]:
                t = clean(p.get_text(" "))
                if re.search(r"\d\s*мин", t):
                    walk = parse_range_minutes(t)
                    metro = re.sub(r"(?:до|от)?\s*\d{1,2}(?:\s*[–\-—]\s*\d{1,2})?\s*мин\.?.*$", "", t).strip(" ,") or None
                    break
                if not address:
                    address = t
        desc_el = item.select_one('meta[itemprop="description"]')
        out.append(Listing(
            source="avito",
            external_id=str(iid),
            url=urljoin(BASE, a["href"].split("?")[0]),
            price=price,
            rooms=rooms,
            is_euro=euro,
            total_area=parse_total_area(title),
            floor=floor,
            floors_total=floors_total,
            address=address,
            metro=metro,
            metro_walk_min=walk,
            description=desc_el.get("content", "") if desc_el else "",
        ))
    return out


class Avito(Source):
    name = "avito"
    needs_details = True

    def search(self) -> Iterable[Listing]:
        for page in range(1, self.s.pages_per_source + 1):
            params = {"pmax": self.s.max_price, "s": 104, "p": page}  # s=104 — сначала новые
            r = self.http.get(self.s.avito_url, params=params, dump=f"avito_p{page}.html")
            items = parse_search_html(r.text)
            if not items:
                break
            yield from items
