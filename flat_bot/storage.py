"""SQLite-хранилище: что уже видели и что уже отправили.

Два уровня защиты от повторов:
1. Точный: (сайт, id объявления) — одно и то же объявление не придёт дважды.
2. Между сайтами: та же квартира на ЦИАН и Авито — совпадают комнаты, этаж,
   этажность, площадь (±0.6 м²), цена (±7%), номер дома и метро (если известны).
"""
from __future__ import annotations

import re
import sqlite3
import time

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    price INTEGER,
    first_seen REAL NOT NULL,
    PRIMARY KEY (source, external_id)
);
CREATE TABLE IF NOT EXISTS sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT,
    rooms INTEGER,
    area REAL,
    floor INTEGER,
    floors_total INTEGER,
    house_key TEXT,
    metro_key TEXT,
    price INTEGER,
    sent_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sent_fp ON sent (rooms, floor, floors_total);
CREATE TABLE IF NOT EXISTS source_health (
    source TEXT PRIMARY KEY,
    fails INTEGER NOT NULL DEFAULT 0,
    notified INTEGER NOT NULL DEFAULT 0
);
"""

_CITY_RE = re.compile(r"(россия|санкт-петербург|г\.\s*санкт-петербург|спб|ленинградская\s+обл[а-я.]*)", re.I)


def house_key(address: str) -> str | None:
    """Номер дома: первое «самостоятельное» число адреса (без порядковых «7-я линия»)."""
    if not address:
        return None
    a = _CITY_RE.sub(" ", address.lower().replace("ё", "е"))
    a = re.sub(r"\b\d{6}\b", " ", a)  # почтовый индекс
    a = re.sub(r"\d+\s*-?\s*(?:я|й|ая|ий|ой)\b", " ", a)  # 7-я линия, 2-й муринский
    nums = re.findall(r"(?<![\d])(\d{1,4})(?![\d])", a)
    return nums[0] if nums else None


def metro_key(metro: str | None) -> str | None:
    if not metro:
        return None
    m = metro.lower().replace("ё", "е")
    m = re.sub(r"\b(м\.|метро|ст\.|станция)\s*", "", m)
    m = re.sub(r"[^a-zа-я0-9]", "", m)
    return m or None


class Storage:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # --- уже видели ---
    def seen_price(self, l: Listing) -> tuple[bool, int | None]:
        row = self.db.execute(
            "SELECT price FROM seen WHERE source=? AND external_id=?", l.key
        ).fetchone()
        return (row is not None, row[0] if row else None)

    def mark_seen(self, l: Listing) -> None:
        self.db.execute(
            "INSERT INTO seen (source, external_id, price, first_seen) VALUES (?,?,?,?) "
            "ON CONFLICT(source, external_id) DO UPDATE SET price=excluded.price",
            (*l.key, l.price, time.time()),
        )
        self.db.commit()

    # --- уже отправили ---
    def was_sent(self, l: Listing) -> bool:
        return self.db.execute(
            "SELECT 1 FROM sent WHERE source=? AND external_id=?", l.key
        ).fetchone() is not None

    def find_cross_duplicate(self, l: Listing) -> str | None:
        """URL ранее отправленного объявления с той же квартирой (с другого сайта)."""
        if l.rooms is None or l.floor is None or l.floors_total is None or l.total_area is None:
            return None
        hk, mk = house_key(l.address), metro_key(l.metro)
        rows = self.db.execute(
            "SELECT url, area, price, house_key, metro_key FROM sent "
            "WHERE rooms=? AND floor=? AND floors_total=? AND NOT (source=? AND external_id=?)",
            (l.rooms, l.floor, l.floors_total, *l.key),
        ).fetchall()
        for url, area, price, h, m in rows:
            if area is None or abs(area - l.total_area) > 0.6:
                continue
            if price and l.price and abs(price - l.price) / max(price, l.price) > 0.07:
                continue
            if hk and h and hk != h:
                continue
            if mk and m and mk != m:
                continue
            return url
        return None

    def mark_sent(self, l: Listing) -> None:
        self.db.execute(
            "INSERT INTO sent (source, external_id, url, rooms, area, floor, floors_total, "
            "house_key, metro_key, price, sent_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (*l.key, l.url, l.rooms, l.total_area, l.floor, l.floors_total,
             house_key(l.address), metro_key(l.metro), l.price, time.time()),
        )
        self.db.commit()

    # --- здоровье источников ---
    def source_failed(self, source: str) -> tuple[int, bool]:
        self.db.execute(
            "INSERT INTO source_health (source, fails) VALUES (?, 1) "
            "ON CONFLICT(source) DO UPDATE SET fails = fails + 1",
            (source,),
        )
        self.db.commit()
        fails, notified = self.db.execute(
            "SELECT fails, notified FROM source_health WHERE source=?", (source,)
        ).fetchone()
        return fails, bool(notified)

    def source_notified(self, source: str) -> None:
        self.db.execute("UPDATE source_health SET notified=1 WHERE source=?", (source,))
        self.db.commit()

    def source_ok(self, source: str) -> bool:
        """Сбросить счётчик ошибок. Вернуть True, если до этого слали предупреждение."""
        row = self.db.execute("SELECT notified FROM source_health WHERE source=?", (source,)).fetchone()
        self.db.execute(
            "INSERT INTO source_health (source, fails, notified) VALUES (?, 0, 0) "
            "ON CONFLICT(source) DO UPDATE SET fails=0, notified=0",
            (source,),
        )
        self.db.commit()
        return bool(row and row[0])
