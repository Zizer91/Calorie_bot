"""Отправка сообщений в Telegram через Bot API (без тяжёлых библиотек)."""
from __future__ import annotations

import html
import logging
import time

import requests

from .models import MATERIAL_RU, Listing, Material

log = logging.getLogger(__name__)

SOURCE_RU = {
    "cian": "ЦИАН",
    "avito": "Авито",
    "domclick": "ДомКлик",
    "yandex": "Яндекс Недвижимость",
    "etagi": "Этажи",
    "n1": "N1",
}


def _fmt_money(v: int) -> str:
    return f"{v:,}".replace(",", " ")


def _num(v: float) -> str:
    return f"{v:g}"


def format_listing(l: Listing, warnings: list[str] | None = None, price_drop_from: int | None = None) -> str:
    e = html.escape
    if l.rooms is None:
        rooms = "Квартира"
    elif l.is_euro:
        rooms = f"Евро-{l.rooms + 1}"
    else:
        rooms = f"{l.rooms}-к"
    head = [rooms]
    if l.total_area:
        head.append(f"{_num(l.total_area)} м²")
    if l.floor:
        head.append(f"{l.floor}/{l.floors_total or '?'} эт.")
    lines = [f"🏠 <b>{e(', '.join(head))}</b>"]

    if l.price:
        p = f"💰 <b>{_fmt_money(l.price)} ₽</b>"
        if l.total_area:
            p += f" ({_fmt_money(round(l.price / l.total_area))} ₽/м²)"
        if price_drop_from:
            p += f"  📉 было {_fmt_money(price_drop_from)} ₽"
        lines.append(p)

    details = []
    if l.kitchen_area:
        details.append(f"🍳 кухня {_num(l.kitchen_area)} м²")
    house = MATERIAL_RU[l.material] if l.material != Material.UNKNOWN else "тип дома ?"
    if l.build_year:
        house += f", {l.build_year} г."
    details.append(f"🧱 {house}")
    lines.append(" · ".join(details))

    if l.metro or l.metro_walk_min:
        m = f"🚇 {e(l.metro or 'метро')}"
        if l.metro_walk_min is not None:
            m += f", {l.metro_walk_min} мин пешком"
        lines.append(m)
    if l.address:
        lines.append(f"📍 {e(l.address)}")
    if l.description:
        d = l.description.strip().replace("\n", " ")
        lines.append(f"<i>{e(d[:220] + ('…' if len(d) > 220 else ''))}</i>")
    if warnings:
        lines.append("⚠️ " + e("; ".join(warnings)))
    lines.append(f'🔗 <a href="{e(l.url, quote=True)}">{SOURCE_RU.get(l.source, l.source)}</a>')
    return "\n".join(lines)


class Telegram:
    def __init__(self, token: str, chat_id: str):
        if not token or not chat_id:
            raise ValueError("Нужны TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID (см. README)")
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id

    def send(self, text: str) -> bool:
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                   "disable_web_page_preview": False}
        for attempt in range(5):
            try:
                r = requests.post(self.url, json=payload, timeout=30)
            except requests.RequestException as ex:
                log.warning("telegram: %s", ex)
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 429:
                wait = r.json().get("parameters", {}).get("retry_after", 5)
                time.sleep(wait + 1)
                continue
            if r.ok:
                time.sleep(1.1)  # лимит Telegram — ~1 сообщение в секунду в один чат
                return True
            log.error("telegram %s: %s", r.status_code, r.text[:300])
            return False
        return False


class ConsoleNotifier:
    """Для --dry-run: печатает сообщения вместо отправки."""

    def send(self, text: str) -> bool:
        print("-" * 60)
        print(text)
        return True
