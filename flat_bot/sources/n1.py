"""N1 (n1.ru)."""
from .generic_html import GenericHtml


class N1(GenericHtml):
    name = "n1"
    base_url = "https://spb.n1.ru"
    link_re = r"/view/(\d{5,})/?"

    def search_url(self) -> str:
        return self.s.n1_url

    def page_params(self, page: int) -> dict:
        return {"page": page, "price_max": self.s.max_price}
