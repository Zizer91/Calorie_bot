"""Настройки берутся из переменных окружения / файла .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

ALL_SOURCES = ["cian", "avito", "domclick", "yandex", "etagi", "n1"]


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on", "да")


def _int(name: str, default: int) -> int:
    v = os.getenv(name)
    return int(v) if v and v.strip() else default


def _float(name: str, default: float) -> float:
    v = os.getenv(name)
    return float(v.replace(",", ".")) if v and v.strip() else default


def _list(name: str, default: list[str]) -> list[str]:
    v = os.getenv(name)
    if not v or not v.strip():
        return list(default)
    return [x.strip().lower() for x in v.split(",") if x.strip()]


@dataclass
class Settings:
    telegram_token: str = ""
    telegram_chat_id: str = ""

    # --- критерии поиска ---
    max_price: int = 11_800_000
    rooms: list[int] = field(default_factory=lambda: [1, 2, 3])
    min_kitchen_1k: float = 12.0  # кухня у 1-к, чтобы сделать кухню-гостиную
    min_area_1k: float = 36.0
    max_metro_walk_min: int = 15
    min_panel_year: int = 1970  # для панельных и блочных домов
    allow_monolith: bool = False
    allow_unknown_building: bool = True  # слать, если тип дома не указан (с пометкой)
    allow_unknown_metro: bool = False

    # --- работа бота ---
    sources: list[str] = field(default_factory=lambda: list(ALL_SOURCES))
    pages_per_source: int = 3
    max_details_per_source: int = 20  # сколько карточек за проход открывать для уточнения
    interval_min: int = 20
    max_messages_per_run: int = 30
    notify_price_drop: bool = False
    db_path: str = "flats.db"
    delay_min: float = 2.0
    delay_max: float = 5.0
    debug_dir: str = ""

    # --- адреса поиска (можно поменять, если сайт сменит URL) ---
    avito_url: str = "https://www.avito.ru/sankt-peterburg/kvartiry/prodam-ASgBAgICAUSSA8YQ"
    yandex_url: str = "https://realty.yandex.ru/sankt-peterburg/kupit/kvartira/"
    etagi_url: str = "https://spb.etagi.com/realty/"
    n1_url: str = "https://spb.n1.ru/kupit/kvartiry/"
    domclick_address_guid: str = "c2deb16a-0330-4f05-821f-1d09c93331e6"  # ФИАС: Санкт-Петербург

    @classmethod
    def from_env(cls, env_file: str | None = ".env") -> "Settings":
        if env_file:
            load_dotenv(env_file)
        d = cls()
        return cls(
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            max_price=_int("MAX_PRICE", d.max_price),
            rooms=[int(x) for x in _list("ROOMS", [str(r) for r in d.rooms])],
            min_kitchen_1k=_float("MIN_KITCHEN_1K", d.min_kitchen_1k),
            min_area_1k=_float("MIN_AREA_1K", d.min_area_1k),
            max_metro_walk_min=_int("MAX_METRO_WALK_MIN", d.max_metro_walk_min),
            min_panel_year=_int("MIN_PANEL_YEAR", d.min_panel_year),
            allow_monolith=_bool("ALLOW_MONOLITH", d.allow_monolith),
            allow_unknown_building=_bool("ALLOW_UNKNOWN_BUILDING", d.allow_unknown_building),
            allow_unknown_metro=_bool("ALLOW_UNKNOWN_METRO", d.allow_unknown_metro),
            sources=_list("SOURCES", d.sources),
            pages_per_source=_int("PAGES_PER_SOURCE", d.pages_per_source),
            max_details_per_source=_int("MAX_DETAILS_PER_SOURCE", d.max_details_per_source),
            interval_min=_int("INTERVAL_MIN", d.interval_min),
            max_messages_per_run=_int("MAX_MESSAGES_PER_RUN", d.max_messages_per_run),
            notify_price_drop=_bool("NOTIFY_PRICE_DROP", d.notify_price_drop),
            db_path=os.getenv("DB_PATH", d.db_path),
            delay_min=_float("DELAY_MIN", d.delay_min),
            delay_max=_float("DELAY_MAX", d.delay_max),
            debug_dir=os.getenv("DEBUG_DIR", ""),
            avito_url=os.getenv("AVITO_URL", d.avito_url),
            yandex_url=os.getenv("YANDEX_URL", d.yandex_url),
            etagi_url=os.getenv("ETAGI_URL", d.etagi_url),
            n1_url=os.getenv("N1_URL", d.n1_url),
            domclick_address_guid=os.getenv("DOMCLICK_ADDRESS_GUID", d.domclick_address_guid),
        )
