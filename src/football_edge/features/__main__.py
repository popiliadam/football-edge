"""`python -m football_edge.features {sync-news,tier1}` — haber deposu ve kademe 1 (spec §4, §6).

`sync-news`: haber gözlemlerini `news_items`a taşır; ağa çıkmaz, para harcamaz. `collect-news` iş
akışında toplamanın hemen ardından koşar (R172): `first_seen_at` bizim saatimizdir ve toplamayla
senkron arasındaki her dakika onu geç damgalar. Varsayılan pencere `SYNC_LOOKBACK`; 2026-09-04'ten
beri biriken geçmiş bir kez `--since 2026-09-04` ile taşınır.
`tier1`: sorulmamış haberlere kademe 1 bataryasını sorar — AĞA ÇIKAR, PARA HARCAR; kapı onu
çağırmaz (Ruling R4). Anahtar yoksa `EXIT_NO_JEV_KEY`; aylık tavan dolarsa o ana kadarki cevaplar
yazılır ve `EXIT_BUDGET`. Harcama defteri AYRI, autocommit bir bağlantıdadır: cevap işlemi geri
alınsa bile harcama kaydı kalır (`PostgresSpendLedger`).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import psycopg

from football_edge.collect import EXIT_SOURCE_FAILED, configure_logging
from football_edge.collector import ContractViolation
from football_edge.db import connect
from football_edge.features.news import SYNC_LOOKBACK, load_news, sync_news
from football_edge.features.questions import QUESTIONS_PATH, load_questions
from football_edge.features.tier1 import (
    CLUSTER_WINDOW,
    HORIZON,
    MAX_ATTEMPTS,
    Tier1Run,
    asked_item_ids,
    failed_attempts,
    load_fixtures,
    run_tier1,
    write_item_answers,
)
from football_edge.jev import EXIT_NO_JEV_KEY, JevClient, MissingJevKey, TypeSafeJev
from football_edge.jev_budget import (
    ESTIMATE_USD_UNMEASURED,
    EXIT_BUDGET,
    MONTHLY_CAP_USD,
    BudgetedJev,
    PostgresSpendLedger,
)

LOGGER = logging.getLogger("football_edge.features")


def _utc(text: str) -> datetime:
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.features")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync-news")
    sync.add_argument("--since", type=_utc, default=None)
    tier1 = commands.add_parser("tier1")
    tier1.add_argument("--questions", type=Path, default=QUESTIONS_PATH)
    tier1.add_argument("--since", type=_utc, default=None)
    return parser


def _sync_news(args: argparse.Namespace) -> int:
    try:
        with connect() as conn:
            written = sync_news(conn, since=args.since or _now() - SYNC_LOOKBACK)
            conn.commit()
    except ContractViolation as error:
        LOGGER.error("haber senkronu durdu: %s", error)
        return EXIT_SOURCE_FAILED
    LOGGER.info("haber: yeni %d", written)
    return 0


def _budgeted(jev: JevClient, spend_conn: psycopg.Connection[Any]) -> JevClient:
    return BudgetedJev(
        jev,
        PostgresSpendLedger(spend_conn),
        cap_usd=MONTHLY_CAP_USD,
        estimate_usd=ESTIMATE_USD_UNMEASURED,
        clock=_now,
    )


def _report(run: Tier1Run, items: int, written: int, marked: int) -> None:
    LOGGER.info("jev: soru %d · başarısız %d", run.asked, run.failed)
    LOGGER.info(
        "kademe 1: haber %d · adaysız %d · yazılan cevap %d", items, run.no_candidate, written
    )
    # Vazgeçilen haber bu `prompt_version` için bir daha sorulmaz: operatör onu buradan görür.
    LOGGER.info(
        "kademe 1: başarısızlık işareti %d · vazgeçilen haber %d (%d başarısız deneme)",
        marked,
        run.given_up,
        MAX_ATTEMPTS,
    )


def _tier1(args: argparse.Namespace) -> int:
    try:
        jev = TypeSafeJev()
    except MissingJevKey as error:
        LOGGER.error("kademe 1 koşulmadı: %s", error)
        return EXIT_NO_JEV_KEY
    questions = load_questions(args.questions)
    now = _now()
    # Varsayılan pencere: adayı hâlâ başlamamış olabilecek haberler (fikstür ufku kadar geri).
    since = args.since or now - HORIZON
    with connect() as conn, connect() as spend_conn:
        spend_conn.autocommit = True
        window = load_news(conn, since=since - CLUSTER_WINDOW)
        ids = [item.item_id for item in window if item.item_id is not None]
        asked = asked_item_ids(conn, questions.prompt_version, ids)
        attempts = failed_attempts(conn, questions.prompt_version, ids)
        items = tuple(n for n in window if n.item_id not in asked and n.available_at >= since)
        run = run_tier1(
            items,
            _budgeted(jev, spend_conn),
            questions,
            # Başlamış maç için sorulan cevap hiçbir karara yetişmez; yalnız gelecek fikstürler.
            fixtures=load_fixtures(conn, since=now, until=now + HORIZON),
            clock=_now,
            # Pencerenin kalanı küme adayıdır: sorulmuşlar ve `since`ten önceki (72 saatlik) kuyruk.
            history=tuple(n for n in window if n.item_id in asked or n.available_at < since),
            attempts=attempts,
        )
        written = write_item_answers(conn, run.rows)
        marked = write_item_answers(conn, run.failures)
        conn.commit()
    _report(run, len(items), written, marked)
    if run.budget_hit:
        LOGGER.error("jev: aylık tavan $%.2f doldu — kalan haberler sorulmadı", MONTHLY_CAP_USD)
        return EXIT_BUDGET
    return 0


COMMANDS: Mapping[str, Callable[[argparse.Namespace], int]] = MappingProxyType(
    {"sync-news": _sync_news, "tier1": _tier1}
)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
