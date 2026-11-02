from __future__ import annotations

import logging
from typing import Iterable

from bs4 import BeautifulSoup

from ..config import Settings
from ..extract import clean, listing_from_text
from ..http import Http
from ..models import Listing

log = logging.getLogger(__name__)


class Source:
    name = "base"
    # True — карточки поиска неполные, полезно открывать страницу объявления
    needs_details = False

    def __init__(self, http: Http, settings: Settings):
        self.http = http
        self.s = settings

    def search(self) -> Iterable[Listing]:
        raise NotImplementedError

    def details(self, l: Listing) -> Listing | None:
        """По умолчанию: скачать страницу объявления и вытащить характеристики из текста."""
        r = self.http.get(l.url, dump=f"{self.name}_detail_{l.external_id}.html")
        return self.parse_detail_html(l, r.text)

    def parse_detail_html(self, l: Listing, html: str) -> Listing:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = clean(soup.get_text(" "))
        info = listing_from_text(self.name, l.external_id, l.url, text)
        og = soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content") and not l.description:
            info.description = og["content"]
        return info
