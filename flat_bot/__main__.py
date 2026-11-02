"""Запуск: python -m flat_bot [--once] [--dry-run] [--sources cian,avito]"""
from __future__ import annotations

import argparse
import logging
import random
import time

from .config import Settings
from .notifier import ConsoleNotifier, Telegram
from .runner import Runner
from .storage import Storage


def main() -> None:
    ap = argparse.ArgumentParser(description="Бот поиска квартир в СПб")
    ap.add_argument("--once", action="store_true", help="один проход и выход (для cron)")
    ap.add_argument("--dry-run", action="store_true",
                    help="печатать в консоль вместо Telegram, базу не трогать")
    ap.add_argument("--sources", help="через запятую, напр. cian,avito")
    ap.add_argument("--env", default=None, help="файл настроек (по умолчанию settings.env или .env)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    s = Settings.from_env(args.env)
    if args.sources:
        s.sources = [x.strip().lower() for x in args.sources.split(",") if x.strip()]

    storage = Storage(":memory:" if args.dry_run else s.db_path)
    notifier = ConsoleNotifier() if args.dry_run else Telegram(s.telegram_token, s.telegram_chat_id)
    runner = Runner(s, storage, notifier)

    log = logging.getLogger("flat_bot")
    while True:
        try:
            runner.run_once()
        except Exception:  # noqa: BLE001
            log.exception("проход завершился с ошибкой")
        if args.once or args.dry_run:
            break
        pause = s.interval_min * 60 * random.uniform(0.8, 1.2)
        log.info("следующая проверка через %.0f мин", pause / 60)
        time.sleep(pause)
    storage.close()


if __name__ == "__main__":
    main()
