"""Единая модель объявления, к которой приводятся данные со всех сайтов."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Material(str, Enum):
    BRICK = "brick"
    MONOLITH_BRICK = "monolith_brick"
    STALIN = "stalin"
    PANEL = "panel"
    BLOCK = "block"
    MONOLITH = "monolith"
    WOOD = "wood"
    UNKNOWN = "unknown"


MATERIAL_RU = {
    Material.BRICK: "кирпич",
    Material.MONOLITH_BRICK: "монолит-кирпич",
    Material.STALIN: "сталинка (кирпич)",
    Material.PANEL: "панель",
    Material.BLOCK: "блочный",
    Material.MONOLITH: "монолит",
    Material.WOOD: "дерево",
    Material.UNKNOWN: "не указан",
}


@dataclass
class Listing:
    source: str
    external_id: str
    url: str
    price: int | None = None
    rooms: int | None = None  # 0 = студия
    is_euro: bool = False  # «евро-2» и т.п.: кухня-гостиная + спальня
    total_area: float | None = None
    kitchen_area: float | None = None
    floor: int | None = None
    floors_total: int | None = None
    material: Material = Material.UNKNOWN
    build_year: int | None = None
    address: str = ""
    metro: str | None = None
    metro_walk_min: int | None = None
    description: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str]:
        return self.source, str(self.external_id)

    def merge(self, other: "Listing") -> None:
        """Дополнить пустые поля данными со страницы объявления."""
        for name in (
            "price", "rooms", "total_area", "kitchen_area", "floor", "floors_total",
            "build_year", "metro", "metro_walk_min",
        ):
            if getattr(self, name) is None and getattr(other, name) is not None:
                setattr(self, name, getattr(other, name))
        if self.material == Material.UNKNOWN:
            self.material = other.material
        if not self.address and other.address:
            self.address = other.address
        if not self.description and other.description:
            self.description = other.description
        # is_euro намеренно не переносим: по полному тексту объявления его легко угадать неверно
