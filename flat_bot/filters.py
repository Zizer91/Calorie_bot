"""Проверка объявления на соответствие критериям."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .config import Settings
from .models import Listing, Material


class Verdict(str, Enum):
    PASS = "pass"
    REJECT = "reject"
    NEED_MORE = "need_more"  # не хватает данных — стоит открыть страницу объявления


@dataclass
class Result:
    verdict: Verdict
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


GOOD_MATERIALS = {Material.BRICK, Material.MONOLITH_BRICK, Material.STALIN}
YEAR_MATERIALS = {Material.PANEL, Material.BLOCK}


def evaluate(l: Listing, s: Settings, final: bool = False) -> Result:
    """final=False — данные с карточки поиска, можно попросить уточнение.
    final=True — уточнять больше нечего, решаем с тем, что есть."""
    missing: list[str] = []
    warnings: list[str] = []

    # цена
    if l.price is None:
        missing.append("цена")
    elif l.price > s.max_price:
        return Result(Verdict.REJECT, f"цена {l.price}")

    # комнаты / кухня
    if l.rooms is None:
        missing.append("комнаты")
    elif l.rooms == 0:
        return Result(Verdict.REJECT, "студия")
    elif l.rooms not in s.rooms and not (l.is_euro and l.rooms + 1 in s.rooms):
        return Result(Verdict.REJECT, f"{l.rooms} комн.")
    elif l.rooms == 1 and not l.is_euro:
        if l.total_area is not None and l.total_area < s.min_area_1k:
            return Result(Verdict.REJECT, f"1-к {l.total_area} м²")
        if l.kitchen_area is None:
            missing.append("кухня")
        elif l.kitchen_area < s.min_kitchen_1k:
            return Result(Verdict.REJECT, f"кухня {l.kitchen_area} м²")

    # метро
    if l.metro_walk_min is None:
        if final and s.allow_unknown_metro:
            warnings.append("время до метро не указано")
        else:
            missing.append("метро")
    elif l.metro_walk_min > s.max_metro_walk_min:
        return Result(Verdict.REJECT, f"метро {l.metro_walk_min} мин")

    # дом
    m = l.material
    if m in GOOD_MATERIALS:
        pass
    elif m in YEAR_MATERIALS:
        if l.build_year is None:
            if final and s.allow_unknown_building:
                warnings.append("год постройки не указан")
            else:
                missing.append("год постройки")
        elif l.build_year < s.min_panel_year:
            return Result(Verdict.REJECT, f"{m.value} {l.build_year}")
    elif m == Material.MONOLITH:
        if not s.allow_monolith:
            return Result(Verdict.REJECT, "монолит")
    elif m == Material.WOOD:
        return Result(Verdict.REJECT, "деревянный дом")
    else:  # UNKNOWN
        if final and s.allow_unknown_building:
            warnings.append("тип дома не указан")
        else:
            missing.append("тип дома")

    if missing:
        if final:
            return Result(Verdict.REJECT, "нет данных: " + ", ".join(missing))
        return Result(Verdict.NEED_MORE, ", ".join(missing))
    return Result(Verdict.PASS, warnings=warnings)
