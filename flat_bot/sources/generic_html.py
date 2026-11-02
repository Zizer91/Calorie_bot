"""Общий парсер для сайтов без открытого API (Этажи, N1).

1. Пытаемся найти объявления во встроенном JSON (Next.js / Nuxt state).
2. Иначе — берём ссылки на объявления по шаблону URL и парсим текст карточек.
Подробности (кухня, тип дома, год) добираются со страницы объявления.
"""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..extract import clean, listing_from_text
from ..models import Listing
from .base import Source


def cards_from_links(html: str, base_url: str, source: str, link_re: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, Listing] = {}
    rx = re.compile(link_re)
    for a in soup.find_all("a", href=True):
        m = rx.search(a["href"])
        if not m:
            continue
        oid = m.group(1)
        if oid in out:
            continue
        # поднимаемся до контейнера карточки: в нём должны быть цена и площадь
        node, text = a, ""
        for _ in range(8):
            node = node.parent
            if node is None:
                break
            text = clean(node.get_text(" "))
            if "₽" in text and "м²" in text:
                break
            if len(text) > 3000:
                break
        if not text or len(text) > 3000:
            text = clean(a.get_text(" "))
        url = urljoin(base_url, a["href"].split("?")[0])
        out[oid] = listing_from_text(source, oid, url, text)
    return list(out.values())


class GenericHtml(Source):
    needs_details = True
    base_url = ""
    link_re = ""

    def search_url(self) -> str:
        raise NotImplementedError

    def page_params(self, page: int) -> dict:
        return {"page": page}

    def search(self) -> Iterable[Listing]:
        seen: set[str] = set()
        for page in range(1, self.s.pages_per_source + 1):
            r = self.http.get(self.search_url(), params=self.page_params(page),
                              dump=f"{self.name}_p{page}.html")
            items = [l for l in cards_from_links(r.text, self.base_url, self.name, self.link_re)
                     if l.external_id not in seen]
            if not items:
                break
            for l in items:
                seen.add(l.external_id)
                yield l
