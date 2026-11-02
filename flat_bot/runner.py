"""Один проход: собрать → уточнить → отфильтровать → убрать повторы → отправить."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import Settings
from .filters import Result, Verdict, evaluate
from .http import BlockedError, Http
from .models import Listing
from .notifier import SOURCE_RU, format_listing
from .sources import REGISTRY
from .storage import Storage

log = logging.getLogger(__name__)

FAILS_BEFORE_ALERT = 3


@dataclass
class Candidate:
    listing: Listing
    result: Result
    price_drop_from: int | None = None


class Runner:
    def __init__(self, settings: Settings, storage: Storage, notifier, http: Http | None = None):
        self.s = settings
        self.db = storage
        self.notifier = notifier
        self.http = http or Http((settings.delay_min, settings.delay_max), settings.debug_dir)

    # ---------- сбор с одного сайта ----------
    def collect(self, name: str) -> list[Candidate]:
        source = REGISTRY[name](self.http, self.s)
        out: list[Candidate] = []
        details_left = self.s.max_details_per_source
        details_blocked = False
        total = 0
        error: Exception | None = None
        try:
            for l in source.search():
                total += 1
                was_seen, old_price = self.db.seen_price(l)

                if self.db.was_sent(l):
                    if (self.s.notify_price_drop and l.price and old_price
                            and l.price < old_price * 0.99):
                        out.append(Candidate(l, Result(Verdict.PASS), price_drop_from=old_price))
                    else:
                        self.db.mark_seen(l)
                    continue
                if was_seen and old_price == l.price:
                    continue  # уже проверяли и отбросили, цена не менялась

                res = evaluate(l, self.s)
                if res.verdict == Verdict.NEED_MORE:
                    if details_blocked or details_left <= 0:
                        continue  # не помечаем — проверим в следующий раз
                    details_left -= 1
                    try:
                        info = source.details(l)
                        if info:
                            l.merge(info)
                    except BlockedError as ex:
                        log.warning("%s: страница объявления заблокирована (%s)", name, ex)
                        details_blocked = True
                        continue
                    except Exception as ex:  # noqa: BLE001
                        log.warning("%s: не удалось открыть %s: %s", name, l.url, ex)
                        continue
                    res = evaluate(l, self.s, final=True)

                if res.verdict == Verdict.REJECT:
                    log.debug("%s %s отклонено: %s", name, l.external_id, res.reason)
                    self.db.mark_seen(l)
                    continue
                out.append(Candidate(l, res))
        except BlockedError as ex:
            error = ex
            log.warning("%s: блокировка/капча: %s", name, ex)
        except Exception as ex:  # noqa: BLE001
            error = ex
            log.exception("%s: ошибка парсинга", name)

        log.info("%s: просмотрено %d, подходит %d", name, total, len(out))
        self._health(name, ok=total > 0, error=error)
        return out

    def _health(self, name: str, ok: bool, error: Exception | None) -> None:
        title = SOURCE_RU.get(name, name)
        if ok:
            if self.db.source_ok(name):
                self.notifier.send(f"✅ {title} снова работает")
            return
        fails, notified = self.db.source_failed(name)
        if fails >= FAILS_BEFORE_ALERT and not notified:
            why = "сайт ограничивает доступ (капча)" if isinstance(error, BlockedError) else \
                f"ошибка: {error}" if error else "в выдаче не найдено объявлений (сменилась вёрстка?)"
            self.notifier.send(f"⚠️ {title}: {fails} проверок подряд без результата — {why}. "
                               f"Источник пропускается; можно убрать его из SOURCES или уменьшить частоту проверок.")
            self.db.source_notified(name)

    # ---------- полный проход ----------
    def run_once(self) -> int:
        candidates: list[Candidate] = []
        for name in self.s.sources:
            if name not in REGISTRY:
                log.error("неизвестный источник %s, доступны: %s", name, ", ".join(REGISTRY))
                continue
            candidates.extend(self.collect(name))

        sent = 0
        for c in candidates:
            if sent >= self.s.max_messages_per_run:
                log.info("лимит сообщений за проход достигнут, остальное — в следующий раз")
                break
            l = c.listing
            if c.price_drop_from:
                text = "📉 <b>Цена снижена</b>\n" + format_listing(l, price_drop_from=c.price_drop_from)
                if self.notifier.send(text):
                    self.db.mark_seen(l)
                    sent += 1
                continue
            if self.db.was_sent(l):
                continue
            dup = self.db.find_cross_duplicate(l)
            if dup:
                log.info("%s %s — та же квартира уже отправлена: %s", l.source, l.external_id, dup)
                self.db.mark_seen(l)
                continue
            if self.notifier.send(format_listing(l, c.result.warnings)):
                self.db.mark_sent(l)
                self.db.mark_seen(l)
                sent += 1
        log.info("отправлено: %d", sent)
        return sent
