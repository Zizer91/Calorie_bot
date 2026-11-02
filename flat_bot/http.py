"""Простой HTTP-клиент с паузами между запросами.

Если сайт показывает капчу или блокирует запрос, бот не пытается это обойти:
источник пропускается, а после нескольких неудач приходит уведомление в Telegram.
"""
from __future__ import annotations

import logging
import random
import re
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

BLOCK_MARKERS = (
    "showcaptcha",
    "Подтвердите, что запросы отправляли вы",
    "Доступ ограничен",
    "Вы робот?",
    "Request blocked",
)


class BlockedError(Exception):
    """Сайт показал капчу или ограничил доступ."""


class Http:
    def __init__(self, delay: tuple[float, float] = (2.0, 5.0), debug_dir: str = ""):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "ru-RU,ru;q=0.9",
        })
        self.delay = delay
        self.debug_dir = Path(debug_dir) if debug_dir else None
        self._last = 0.0

    def _pause(self) -> None:
        wait = random.uniform(*self.delay) - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def _check(self, r: requests.Response, url: str) -> None:
        if r.status_code in (401, 403, 429) or re.search(r"captcha|/blocked", r.url):
            raise BlockedError(f"{r.status_code} {r.url}")
        r.raise_for_status()
        if len(r.text) < 200_000 and any(m in r.text[:20000] for m in BLOCK_MARKERS):
            raise BlockedError(f"captcha page at {r.url}")

    def _dump(self, name: str, text: str) -> None:
        if self.debug_dir:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r"[^\w.-]+", "_", name)[:120]
            (self.debug_dir / safe).write_text(text, encoding="utf-8")

    def get(self, url: str, *, params=None, headers=None, dump: str = "") -> requests.Response:
        self._pause()
        r = self.session.get(url, params=params, headers=headers or {}, timeout=30)
        if dump:
            self._dump(dump, r.text)
        self._check(r, url)
        return r

    def post_json(self, url: str, payload: dict, *, headers=None, dump: str = "") -> requests.Response:
        self._pause()
        r = self.session.post(url, json=payload, headers=headers or {}, timeout=30)
        if dump:
            self._dump(dump, r.text)
        self._check(r, url)
        return r
