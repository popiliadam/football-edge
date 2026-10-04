"""`python -m football_edge.features {sync-news,tier1}` — haber deposu ve kademe 1 (spec §4, §6).

`sync-news`: haber gözlemlerini `news_items`a taşır; ağa çıkmaz, para harcamaz. `collect-news` iş
akışında toplamanın hemen ardından koşar (R172): `first_seen_at` bizim saatimizdir ve toplamayla
senkron arasındaki her dakika onu geç damgalar. Varsayılan pencere `SYNC_LOOKBACK`; 2026-09-04'ten
beri biriken geçmiş bir kez `--since 2026-09-04` ile taşınır.
`tier1` yalnız üretim dillerinin (`config/languages.yaml`, rapor geçerli) haberini sorar ve
pencereyi sorgudan hemen sonra dille süzer — kalibre olmayan dilin başlığı küme adayı olarak da
Jev'e gitmez (R178). Tur başına `MAX_CALLS_PER_RUN` çağrı, EN YENİ haber önce (inceleme I6); her
`BATCH_SIZE` haberde commit (I-8).
`tier1`: sorulmamış haberlere kademe 1 bataryasını sorar — AĞA ÇIKAR, PARA HARCAR; kapı onu
çağırmaz (Ruling R4). Anahtar yoksa `EXIT_NO_JEV_KEY`; aylık tavan dolarsa o ana kadarki cevaplar
yazılır ve `EXIT_BUDGET`. Jev kesintisinde (art arda `OUTAGE_STREAK` Jev hatası) koşu durur,
serinin işareti yazılmaz, haberler sonraki koşuda yeniden sorulur ve `EXIT_SOURCE_FAILED`.
Harcama defteri AYRI, autocommit bir bağlantıdadır: cevap işlemi geri alınsa bile harcama
kaydı kalır (`PostgresSpendLedger`).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from football_edge.calibration import production_languages
from football_edge.collect import EXIT_SOURCE_FAILED, LANGUAGES_PATH, configure_logging
from football_edge.collector import ContractViolation
from football_edge.db import connect
from football_edge.features.news import SYNC_LOOKBACK, load_news, sync_news
from football_edge.features.questions import QUESTIONS_PATH, QuestionSet, load_questions
from football_edge.features.tier1 import (
    BATCH_SIZE,
    CLUSTER_WINDOW,
    EMPTY_RUN,
    HORIZON,
    MAX_ATTEMPTS,
    MAX_CALLS_PER_RUN,
    OUTAGE_STREAK,
    Tier1Run,
    asked_item_ids,
    batches,
    failed_attempts,
    load_fixtures,
    merge_runs,
    newest_within_cap,
    run_tier1,
    write_item_answers,
)
from football_edge.features.types import StoredNews
from football_edge.jev import EXIT_NO_JEV_KEY, JevClient, MissingJevKey, TypeSafeJev
from football_edge.jev_budget import (
    EXIT_BUDGET,
    MONTHLY_CAP_USD,
    budgeted_jev,
)
from football_edge.live.context import LiveMatch

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
    tier1.add_argument("--languages", type=Path, default=LANGUAGES_PATH)
    tier1.add_argument("--max-calls", type=int, default=MAX_CALLS_PER_RUN)
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


def _report(run: Tier1Run, items: int, written: int, marked: int) -> None:
    LOGGER.info("jev: soru %d · başarısız %d · çağrı %d", run.asked, run.failed, run.calls)
    LOGGER.info(
        "kademe 1: haber %d · adaysız %d · yazılan cevap %d · ertelenen %d (tur tavanı)",
        items,
        run.no_candidate,
        written,
        run.deferred,
    )
    # Vazgeçilen haber bu `prompt_version` için bir daha sorulmaz: operatör onu buradan görür.
    LOGGER.info(
        "kademe 1: başarısızlık işareti %d · vazgeçilen haber %d (%d başarısız deneme)",
        marked,
        run.given_up,
        MAX_ATTEMPTS,
    )


def _ask_in_batches(
    conn: Any,
    client: JevClient,
    questions: QuestionSet,
    *,
    items: Sequence[StoredNews],
    history: Sequence[StoredNews],
    fixtures: Sequence[LiveMatch],
    attempts: Mapping[int, int],
    max_calls: int,
) -> tuple[Tier1Run, int, int]:
    """Partiler: her partiden sonra yaz + commit (I-8); sonraki partinin küme havuzu öncekileri
    görür. Tavan ya da kesinti kalan partileri durdurur. Dönüş: (birleşik koşu, cevap, işaret)."""
    total, written, marked = EMPTY_RUN, 0, 0
    done: tuple[StoredNews, ...] = ()
    for batch in batches(items, BATCH_SIZE):
        run = run_tier1(
            batch,
            client,
            questions,
            fixtures=fixtures,
            clock=_now,
            history=(*history, *done),
            attempts=attempts,
            max_calls=max_calls - total.calls,
        )
        written += write_item_answers(conn, run.rows)
        marked += write_item_answers(conn, run.failures)
        conn.commit()  # parti başına (I-8): zaman aşımı ödenmiş cevabı yutmaz
        total, done = merge_runs(total, run), (*done, *batch)
        if run.budget_hit or run.outage:
            break
    return total, written, marked


def _tier1_exit(run: Tier1Run) -> int:
    if run.budget_hit:
        LOGGER.error("jev: aylık tavan $%.2f doldu — kalan haberler sorulmadı", MONTHLY_CAP_USD)
        return EXIT_BUDGET
    if run.outage:
        # Kesinti bir bağımlılığın (Jev) arızasıdır, haberlerin değil: `sync-news`in kaynak kodu.
        LOGGER.error(
            "jev: kesinti — art arda %d haber Jev hatasıyla düştü, koşu durdu; serinin işareti "
            "yazılmadı, sonraki koşu yeniden sorar",
            OUTAGE_STREAK,
        )
        return EXIT_SOURCE_FAILED
    return 0


def _tier1(args: argparse.Namespace) -> int:
    try:
        jev = TypeSafeJev()
    except MissingJevKey as error:
        LOGGER.error("kademe 1 koşulmadı: %s", error)
        return EXIT_NO_JEV_KEY
    languages = production_languages(args.languages)
    if not languages:
        LOGGER.info("kademe 1: üretimde dil yok (%s) — Jev'e haber gitmedi", args.languages)
        return 0
    questions = load_questions(args.questions)
    now = _now()
    # Varsayılan pencere: adayı hâlâ başlamamış olabilecek haberler (fikstür ufku kadar geri).
    since = args.since or now - HORIZON
    with connect() as conn, connect() as spend_conn:
        # Üretim dışı dilin haberi ne sorulur ne küme adayı olur: başlığı Jev'e hiç gitmez (R178).
        window = tuple(
            n for n in load_news(conn, since=since - CLUSTER_WINDOW) if n.lang in languages
        )
        ids = [item.item_id for item in window if item.item_id is not None]
        asked = asked_item_ids(conn, questions.prompt_version, ids)
        unasked = tuple(n for n in window if n.item_id not in asked and n.available_at >= since)
        # Başlamış maç için sorulan cevap hiçbir karara yetişmez; yalnız gelecek fikstürler.
        fixtures = load_fixtures(conn, since=now, until=now + HORIZON)
        attempts = failed_attempts(conn, questions.prompt_version, ids)
        # Tavan altında en yeni haber önce (I6); seçilenler partilerde zaman sırasıyla sorulur.
        items, deferred = newest_within_cap(
            unasked, fixtures, attempts=attempts, cap=args.max_calls
        )
        run, written, marked = _ask_in_batches(
            conn,
            budgeted_jev(jev, spend_conn, clock=_now),
            questions,
            items=items,
            # Pencerenin kalanı küme adayıdır: sorulmuşlar ve `since`ten önceki (72 saatlik) kuyruk.
            history=tuple(n for n in window if n.item_id in asked or n.available_at < since),
            fixtures=fixtures,
            attempts=attempts,
            max_calls=args.max_calls,
        )
    run = replace(run, deferred=run.deferred + deferred)
    _report(run, len(unasked), written, marked)
    return _tier1_exit(run)


COMMANDS: Mapping[str, Callable[[argparse.Namespace], int]] = MappingProxyType(
    {"sync-news": _sync_news, "tier1": _tier1}
)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
