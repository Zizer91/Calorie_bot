"""Извлечение характеристик квартиры из русского текста и встроенного JSON.

Регулярки работают по видимому тексту страницы, поэтому меньше зависят
от вёрстки сайта, чем CSS-селекторы.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterator

from .models import Listing, Material

NUM = r"(\d+(?:[.,]\d+)?)"
SEP = r"\s*[:\-—–]?\s*"


def to_float(s: Any) -> float | None:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    try:
        return float(str(s).replace(",", ".").replace(" ", "").strip())
    except ValueError:
        return None


def to_int(s: Any) -> int | None:
    f = to_float(s)
    return int(f) if f is not None else None


def clean(text: str) -> str:
    text = text.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_price(text: str) -> int | None:
    text = clean(text)
    for m in re.finditer(r"(\d{1,3}(?:[ .]\d{3}){1,3}|\d{6,9})\s*(?:₽|руб)", text):
        v = int(re.sub(r"\D", "", m.group(1)))
        if 500_000 <= v <= 1_000_000_000:
            return v
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*млн", text)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1_000_000)
    return None


def parse_rooms(text: str) -> tuple[int | None, bool]:
    """Вернуть (количество комнат, евро-планировка). Студия = 0."""
    t = clean(text).lower()
    euro = bool(re.search(r"евро\s*-?\s*\d|\d\s*-?\s*к\.?\s*евро|евродвушк|евротрёшк|евротрешк", t))
    if re.search(r"студи", t):
        return 0, False
    m = re.search(r"евро\s*-?\s*(\d)", t)
    if m:
        # «Евро-2» = кухня-гостиная + 1 спальня, считаем как 1 спальню
        return int(m.group(1)) - 1, True
    m = re.search(r"(\d)\s*-?\s*(?:к\b|к\.|комн|комнатн|х\s*комн)", t)
    if m:
        return int(m.group(1)), euro
    words = {"одно": 1, "двух": 2, "трёх": 3, "трех": 3, "четырёх": 4, "четырех": 4}
    for w, n in words.items():
        if re.search(w + r"комнатн", t):
            return n, euro
    return None, euro


def parse_total_area(text: str) -> float | None:
    t = clean(text).lower()
    m = re.search(r"общая(?:\s+площадь)?" + SEP + NUM + r"\s*м", t) or re.search(
        r"площадь(?:\s+общая)?" + SEP + NUM + r"\s*м", t
    )
    if m:
        return to_float(m.group(1))
    m = re.search(NUM + r"\s*м²", t) or re.search(NUM + r"\s*кв\.?\s*м", t)
    return to_float(m.group(1)) if m else None


def parse_kitchen(text: str) -> float | None:
    t = clean(text).lower()
    m = re.search(r"(?:площадь\s+)?кухн[яиеюё]" + SEP + NUM + r"\s*(?:м|кв)", t)
    if m:
        return to_float(m.group(1))
    m = re.search(r"кухня-гостиная" + SEP + NUM, t)
    return to_float(m.group(1)) if m else None


def parse_floor(text: str) -> tuple[int | None, int | None]:
    t = clean(text).lower()
    m = re.search(r"(\d{1,2})\s*(?:/|из)\s*(\d{1,2})\s*эт", t) or re.search(
        r"этаж" + SEP + r"(\d{1,2})\s*(?:/|из)\s*(\d{1,2})", t
    )
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"этаж" + SEP + r"(\d{1,2})\b", t)
    f = int(m.group(1)) if m else None
    m = re.search(r"(?:этажей\s+в\s+доме|этажность(?:\s+дома)?)" + SEP + r"(\d{1,2})", t)
    return f, int(m.group(1)) if m else None


def parse_year(text: str) -> int | None:
    t = clean(text).lower()
    m = re.search(
        r"(?:год\s+постройки|год\s+сдачи|построен[а-я]*(?:\s+в)?|дом\s+\d{4}\s*г)" + SEP + r"(?:в\s+)?((?:18|19|20)\d{2})",
        t,
    )
    return int(m.group(1)) if m else None


def material_from_word(word: str | None) -> Material:
    if not word:
        return Material.UNKNOWN
    w = word.lower()
    if ("кирпич" in w and "монолит" in w) or "monolithbrick" in w or "monolit_brick" in w or "monolith_brick" in w:
        return Material.MONOLITH_BRICK
    if "сталин" in w or w == "stalin":
        return Material.STALIN
    if "кирпич" in w or w in ("brick", "old") or "старый фонд" in w:
        return Material.BRICK
    if "панел" in w or w == "panel":
        return Material.PANEL
    if "блоч" in w or w == "block":
        return Material.BLOCK
    if "монолит" in w or w in ("monolith", "monolit"):
        return Material.MONOLITH
    if "дерев" in w or w in ("wood", "wooden"):
        return Material.WOOD
    return Material.UNKNOWN


def parse_material(text: str) -> Material:
    t = clean(text).lower()
    m = re.search(
        r"(?:тип\s+дома|тип\s+здания|материал\s+(?:стен|дома)|тип\s+постройки|стены)" + SEP
        + r"([а-яё]+(?:\s*-\s*[а-яё]+)?)",
        t,
    )
    if m:
        mat = material_from_word(m.group(1))
        if mat != Material.UNKNOWN:
            return mat
    m = re.search(r"(кирпичн[а-я]*\s*-?\s*монолитн|монолитно\s*-?\s*кирпичн|кирпичн|панельн|блочн|монолитн|сталинк)[а-я]*\s+дом", t)
    return material_from_word(m.group(1)) if m else Material.UNKNOWN


def parse_metro_walk(text: str) -> int | None:
    """Минимальное время пешком до метро, найденное в тексте."""
    t = clean(text).lower()
    found = [int(x) for x in re.findall(r"(\d{1,2})\s*мин(?:ут[аы]?|\.)?\s*пешком", t)]
    found += [int(x) for x in re.findall(r"пешком\s*(?:за\s*)?(\d{1,2})\s*мин", t)]
    return min(found) if found else None


def parse_range_minutes(text: str) -> int | None:
    """Авито пишет «до 5 мин.», «6–10 мин.», «11–15 мин.», «от 31 мин.» — берём верхнюю границу."""
    t = clean(text).lower()
    m = re.search(r"\d{1,2}\s*[–\-—]\s*(\d{1,2})\s*мин", t)
    if m:
        return int(m.group(1))
    m = re.search(r"до\s*(\d{1,2})\s*мин", t)
    if m:
        return int(m.group(1))
    m = re.search(r"от\s*(\d{1,2})\s*мин", t)
    if m:
        return int(m.group(1)) + 15
    m = re.search(r"(\d{1,2})\s*мин", t)
    return int(m.group(1)) if m else None


def listing_from_text(source: str, external_id: str, url: str, text: str) -> Listing:
    """Собрать объявление из произвольного текста карточки/страницы."""
    t = clean(text)
    rooms, euro = parse_rooms(t)
    floor, floors_total = parse_floor(t)
    return Listing(
        source=source,
        external_id=external_id,
        url=url,
        price=parse_price(t),
        rooms=rooms,
        is_euro=euro,
        total_area=parse_total_area(t),
        kitchen_area=parse_kitchen(t),
        floor=floor,
        floors_total=floors_total,
        material=parse_material(t),
        build_year=parse_year(t),
        metro_walk_min=parse_metro_walk(t),
    )


# ---------- встроенный JSON (Next.js / Redux-state и т.п.) ----------

_STATE_PATTERNS = [
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>",
    r"window\.INITIAL_STATE\s*=\s*(\{.*?\})\s*;?\s*</script>",
    r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>",
    r'<script[^>]+type="application/json"[^>]*>(\{.*?\})</script>',
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
]


def embedded_json(html: str) -> list[Any]:
    out = []
    for pat in _STATE_PATTERNS:
        for m in re.finditer(pat, html, re.S):
            raw = m.group(1).strip()
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return out


def iter_dicts(obj: Any, depth: int = 0) -> Iterator[dict]:
    if depth > 40:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_dicts(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_dicts(v, depth + 1)


def dig(d: Any, *path: str, default: Any = None) -> Any:
    """Безопасно достать вложенное поле: dig(x, 'a', 'b', '0', 'c')."""
    cur = d
    for p in path:
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, list) and p.isdigit() and int(p) < len(cur):
            cur = cur[int(p)]
        else:
            return default
        if cur is None:
            return default
    return cur


def first(d: dict, *paths: str, default: Any = None) -> Any:
    """Первое непустое значение среди путей вида 'a.b.c'."""
    for p in paths:
        v = dig(d, *p.split("."))
        if v not in (None, "", [], {}):
            return v
    return default
