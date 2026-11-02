"""Этажи (spb.etagi.com)."""
from .generic_html import GenericHtml


class Etagi(GenericHtml):
    name = "etagi"
    base_url = "https://spb.etagi.com"
    link_re = r"/realty/(\d{4,})/?"

    def search_url(self) -> str:
        return self.s.etagi_url

    def page_params(self, page: int) -> dict:
        return {"page": page, "price_max": self.s.max_price}
