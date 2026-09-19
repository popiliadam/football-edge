from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import psycopg

from football_edge.anchors import (
    ANCHOR_DIR,
    Anchor,
    _scan_anchors,
    archived_anchors,
    expected_anchor_names,
    missing_anchors,
)
from football_edge.collectors.footystats import collect_footystats
from football_edge.collectors.news import NewsCollectResult, collect_news
from football_edge.collectors.results import ResultsCollectResult, collect_results
from football_edge.collectors.tff import collect_tff
from football_edge.collectors.venues import VenuesResult, collect_venues
from football_edge.db import (
    chain_head,
    connect,
    insert_snapshots,
    upsert_leagues,
    upsert_matches,
)
from football_edge.leagues import League, active_leagues, load_leagues
from football_edge.ledger import (
    ChainResult,
    canonical_timestamp,
    payload_of,
    row_hash,
    verify_chain,
)
from football_edge.odds_api import PriceRow, Quota, QuotaExhausted, fetch_odds, guard_quota
from football_edge.sources import audit_offline, load_sources

LOGGER = logging.getLogger("football_edge.collect")
LEAGUES_PATH = Path("config/leagues.yaml")
SOURCES_PATH = Path("config/sources.yaml")
ROBOTS_DIR = Path("config/robots")

# db/migrations/0001_init.sql → check (price > 1.0). Şema kısıtının kod tarafındaki karşılığı.
MIN_PRICE = 1.0

# ── ÇIKIŞ KODLARI ───────────────────────────────────────────────────────────
# Her kodun `.github/workflows/*.yml` içinde ADLANDIRILMIŞ bir `case` arm'ı vardır;
# adı olmayan kod `*)` dalına düşer ve operatör arızayı ayırt edemez. Kod eklenince
# workflow da güncellenir — `tests/test_workflows.py` bu bağı kapıda tutar.
#
# 0 ve 1 ayrılmıştır: 0 yalnız arızasız tur, 1 ise zincir kırığı (`verify-chain`)
# ve Python'ın kendi beklenmedik arızaları.
EXIT_QUOTA_EXHAUSTED = 2
EXIT_LEAGUE_FAILED = 3
EXIT_MIRROR_FAILED = 4
# Kaçan mühür GERİ ALINAMAZ: maçın kapanış fiyatı bir daha oluşmaz. Bu yüzden 0
# olamaz — 0, seal.yml'de "mühür turu tamam" diye okunur ve Faz 0'ın önlemek için
# var olduğu TEK sonuç başarı olarak raporlanır.
EXIT_MISSED_SEAL = 5
# BİLİNÇLİ İSTİSNA: yukarıdaki "her kodun ADLANDIRILMIŞ case arm'ı vardır" kuralı buna
# UYGULANMAZ. `sources-audit` `seal.yml`/`snapshot.yml`ce HİÇ çağrılmaz (case listesi
# taşıyan tek yerler), o yüzden oraya bir arm eklemek var olmayan bir çağrıyı adlandırırdı.
# Bunu gerçekten tüketen `verify.sh`/`sources-audit.yml` case arm'ı taşımaz — adımın çıkışını
# ham "başarılı/başarısız" diye okurlar. `tests/test_workflows.py`'nin parametrize listesi
# YALNIZ seal.yml'in case'lerini tutar ve bunu KASITLI dışarıda bırakır (o dosyadaki yorum).
EXIT_SOURCE_POLICY = 6
# M7 (2026-09-19 merge) — AYNI İSTİSNA, AYNI GEREKÇE, EXIT_SOURCE_POLICY emsalini izler:
# `fetch-tff`/`fetch-venues`/`fetch-news`nin arıza kodu. `EXIT_LEAGUE_FAILED` KASITLI
# yeniden kullanılmadı: o kod "lig" kavramına bağlı (run_snapshot/run_seal/fetch-footystats/
# fetch-results'ın döngülediği şey) — TFF ulusal TEK sayfa, haber KAYNAK'a (adaptöre) göre,
# stadyum/hava VARLIK'a (stadyum QID'si) göre döngüleniyor; "lig" onların hiçbirini
# adlandırmaz. Var olan bir kodu yanlış kavrama yeniden bağlamak, bu kod tabanının
# tekrarlayan dersiyle (bkz. footystats.py, tff.py: "isimle bul, konumla değil") aynı
# sınıf arızadır — yalnız isimlendirme yüzeyinde.
# `fetch-results` bu kodu ALMAZ: o gerçekten LİG döngüler (aynı `League.odds_api_key`
# kümesi, aynı per-lig izolasyon deseni) ve `EXIT_LEAGUE_FAILED`ı DOĞRU biçimde yeniden
# kullanır — bkz. `collectors.results.collect_results` docstring'i.
# Bu kod da (EXIT_SOURCE_POLICY gibi) `seal.yml`nin case listesinde YOKTUR: M8 bu görevde
# hiçbir yeni workflow/cron eklenmesini yasaklıyor, dört yeni alt komuttan hiçbiri
# `seal.yml`/`snapshot.yml` tarafından hiç çağrılmıyor — `tests/test_workflows.py`deki
# "BU LİSTE ELLE TUTULUR" yorumu bu kararı da adıyla taşır.
EXIT_SOURCE_FAILED = 7

_LEDGER_COLUMNS = """
    SELECT match_id, observed_at, bookmaker, market, outcome, point, price,
           bookmaker_last_update, is_closing, prev_hash, row_hash
    FROM odds_snapshots
"""
_LEDGER_ALL = _LEDGER_COLUMNS + " ORDER BY id"
_LEDGER_AFTER = _LEDGER_COLUMNS + " WHERE id > %s ORDER BY id"
_LEDGER_AT = _LEDGER_COLUMNS + " WHERE id = %s"


@dataclass(frozen=True)
class CollectResult:
    written: int
    quota: Quota | None
    failed_leagues: tuple[str, ...]
    # Hakkında GERÇEKTEN satır yazılan maçlar. Mühür bu kümeye basılır; "ligi
    # toplayabildik" mühür için yeterli değildir (F1).
    written_matches: tuple[str, ...] = ()
    missed_seals: tuple[str, ...] = ()
    quota_exhausted: bool = False
    leagues_mirrored: bool = True


@dataclass(frozen=True)
class SealCandidates:
    due: tuple[League, ...]
    missed: tuple[str, ...]


def horizon_iso(now: datetime, days: int) -> str:
    return (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def seal_window(commence_time: datetime, now: datetime, minutes: int) -> bool:
    delta = commence_time - now
    return timedelta(0) <= delta <= timedelta(minutes=minutes)


def _commence_at(row: PriceRow) -> datetime:
    """API'den gelen metni tek kanonik yoldan datetime'a çevirir."""
    return datetime.fromisoformat(canonical_timestamp(row.commence_time))


def _seal_row_filter(now: datetime, window_minutes: int) -> Callable[[PriceRow], bool]:
    """Mühür turu 24 saatlik ufuk çeker; kapanış damgasını YALNIZ penceredeki maç hak eder."""

    def in_window(row: PriceRow) -> bool:
        return seal_window(_commence_at(row), now, window_minutes)

    return in_window


def _priced_rows(rows: tuple[PriceRow, ...], league_id: str) -> tuple[PriceRow, ...]:
    """Şema kısıtını ihlal eden satırları ayıklar — ama adıyla loglayarak."""
    valid: tuple[PriceRow, ...] = ()
    for row in rows:
        if row.price > MIN_PRICE:
            valid = (*valid, row)
        else:
            LOGGER.warning(
                "lig=%s maç=%s bahisçi=%s piyasa=%s sonuç=%s geçersiz fiyat=%s — satır atlandı",
                league_id,
                row.event_id,
                row.bookmaker,
                row.market,
                row.outcome,
                row.price,
            )
    return valid


def _usable_rows(
    rows: tuple[PriceRow, ...], league_id: str, row_filter: Callable[[PriceRow], bool] | None
) -> tuple[PriceRow, ...]:
    windowed = rows if row_filter is None else tuple(row for row in rows if row_filter(row))
    return _priced_rows(windowed, league_id)


def _quota_spent(quota: Quota, min_remaining: int) -> bool:
    """guard_quota'nın eşiği tek kaynaktır; tur erken kapanır ama toplanan iş kaybolmaz."""
    try:
        guard_quota(quota, min_remaining)
    except QuotaExhausted:
        LOGGER.warning(
            "kalan kredi %d < eşik %d — tur erken kapatıldı", quota.remaining, min_remaining
        )
        return True
    return False


def _write_league(
    conn: psycopg.Connection[Any],
    rows: tuple[PriceRow, ...],
    league_id: str,
    now: datetime,
    *,
    is_closing: bool,
) -> tuple[str, ...]:
    """Yazılan satırların match_id'lerini döner — mühür bu listeden basılır."""
    if not rows:
        LOGGER.info("lig=%s yazılacak satır yok", league_id)
        return ()
    upsert_matches(conn, rows, league_id)
    return insert_snapshots(conn, rows, now, is_closing=is_closing)


def _collect(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    commence_time_to: str,
    is_closing: bool,
    min_remaining: int,
    row_filter: Callable[[PriceRow], bool] | None = None,
) -> CollectResult:
    written: tuple[str, ...] = ()
    quota: Quota | None = None
    failed: tuple[str, ...] = ()
    spent = False
    for league in leagues:
        if quota is not None and _quota_spent(quota, min_remaining):
            spent = True
            break
        try:
            rows, quota = fetch_odds(
                client, api_key, league.odds_api_key, commence_time_to=commence_time_to
            )
            usable = _usable_rows(rows, league.id, row_filter)
            recorded = _write_league(conn, usable, league.id, now, is_closing=is_closing)
            conn.commit()
        except Exception:
            # Tek bir ligin arızası diğer liglerin kapanış oranını kaçırmasına yol açmamalı.
            # Kapanış oranı kaçarsa geri gelmez; bozuk bir lig ise sonraki turda tekrar denenir.
            conn.rollback()
            LOGGER.exception("lig=%s toplanamadı, diğer liglere devam ediliyor", league.id)
            failed = (*failed, league.id)
            continue
        # MÜHRÜ SÜREN LİSTE COMMIT'TEN SONRA BİRİKİR — `try` İÇİNE ALMAYIN (G1).
        # `commit()` bağlantı AYAKTAYKEN de düşer: statement timeout, serialization
        # abort, sunucu tarafı transaction abort. O hâlde `rollback()` başarılı olur,
        # lig doğru biçimde arızalı sayılır, ama commit'ten ÖNCE biriktirilmiş
        # match_id'ler `written_matches`e akıp geri alınmış maça `sealed_at` bastırır.
        # Mühürlenen maç bir daha denenmez; kapanış fiyatı kalıcı olarak kaybolur.
        written = (*written, *recorded)
        LOGGER.info("lig=%s satır=%d kalan_kredi=%d", league.id, len(usable), quota.remaining)
    return CollectResult(
        written=len(written),
        quota=quota,
        failed_leagues=failed,
        written_matches=tuple(dict.fromkeys(written)),
        quota_exhausted=spent,
    )


def run_snapshot(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    horizon_days: int = 7,
    min_remaining: int = 10,
) -> CollectResult:
    return _collect(
        conn,
        client,
        api_key,
        leagues,
        now,
        commence_time_to=horizon_iso(now, horizon_days),
        is_closing=False,
        min_remaining=min_remaining,
    )


def _seal_candidates(
    conn: psycopg.Connection[Any], leagues: tuple[League, ...], now: datetime, window_minutes: int
) -> SealCandidates:
    """Mühürlenecek ligleri ve mührü KAÇMIŞ maçları aynı sorgudan çıkarır."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, league_id, commence_time FROM matches
            WHERE sealed_at IS NULL AND commence_time > %s - interval '1 day'
            """,
            (now,),
        )
        candidates = tuple((str(record[0]), str(record[1]), record[2]) for record in cur.fetchall())
    due = {
        league_id
        for _, league_id, commence_time in candidates
        if seal_window(commence_time, now, window_minutes)
    }
    # Başlama saati geçmiş ve hâlâ mühürsüz: cron kaydı, bir daha da gelmeyecek.
    missed = tuple(match_id for match_id, _, commence_time in candidates if commence_time < now)
    return SealCandidates(
        due=tuple(league for league in leagues if league.id in due), missed=missed
    )


def run_seal(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    window_minutes: int = 20,
    min_remaining: int = 5,
) -> CollectResult:
    candidates = _seal_candidates(conn, leagues, now, window_minutes)
    if not candidates.due:
        LOGGER.info("mühürlenecek maç yok")
        return CollectResult(
            written=0, quota=None, failed_leagues=(), missed_seals=candidates.missed
        )
    result = _collect(
        conn,
        client,
        api_key,
        candidates.due,
        now,
        commence_time_to=horizon_iso(now, 1),
        is_closing=True,
        min_remaining=min_remaining,
        # 24 saatlik çekimin tamamı "kapanış" değildir: pencere dışı satır yazılmaz.
        row_filter=_seal_row_filter(now, window_minutes),
    )
    _stamp_sealed(conn, result.written_matches, now)
    return replace(result, missed_seals=candidates.missed)


def _stamp_sealed(conn: psycopg.Connection[Any], match_ids: tuple[str, ...], now: datetime) -> None:
    """Mühür MAÇ bazındadır: yalnız kapanış satırı gerçekten yazılan maç damgalanır.

    Lig bazında damgalamak, ligin HTTP çekimi başarılı olduğu için o ligin penceredeki
    her maçını mühürlüyordu — fiyatı kayda geçmemiş maçlar dâhil. Mühürlenen maç bir
    daha denenmez; kapanış fiyatı geri gelmez.
    """
    if not match_ids:
        LOGGER.info("mühürlenecek maç yok: bu turda kapanış satırı yazılmadı")
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE matches SET sealed_at = %s WHERE sealed_at IS NULL AND id = ANY(%s)",
            (now, list(match_ids)),
        )
    conn.commit()


def _mirror_leagues(conn: psycopg.Connection[Any], configured: tuple[League, ...]) -> bool:
    """Lig aynasını tazeler; BAŞARISIZLIĞINI traceback'le değil, dönüş değeriyle bildirir.

    Bu çağrı `try` dışındaydı: `leagues.odds_api_key` UNIQUE ihlali ya da geçici bir
    veritabanı arızası `main()`den dışarı düşüp turu traceback'le bitiriyordu (F3).
    Arıza artık yakalanır, adıyla raporlanır ve çıkış kodu 4 olur — ama tur SÜRMEZ:
    ücretli çağrıya girmenin bedeli `_mirror_failed()`te yazılı (G3).
    """
    try:
        upsert_leagues(conn, configured)
        conn.commit()
    except Exception:
        conn.rollback()
        LOGGER.exception("lig aynası tazelenemedi, tur başlatılmıyor (ücretli çağrı yapılmaz)")
        return False
    return True


def _mirror_failed() -> CollectResult:
    """Ayna düşmüşse tur BAŞLAMADAN durur: `fetch_odds` ücretlidir (G3).

    Turu sürdürmek her ligi ücretli çağrıya sokuyor, satır yazılınca da yabancı anahtar
    zaten patlıyordu: lig başına 1 kredi × 6 lig × 15 dakikalık mühür cron'u, 500
    kredilik aylık ücretsiz katmanı iki günde bitirir. Önce kredi harcayıp sonra
    yazamamak, hiç denememekten kötüdür.

    ÖDÜNLEŞME AÇIKÇA KAYITLIDIR: ayna yalnız GEÇİCİ bir arızadan tazelenemediyse
    (tablo bir önceki turun aynasını hâlâ taşıyor olabilir) bu tur mühürlenebilirdi.
    O turun mührü artık kaçar ve kapanış fiyatı geri gelmez — kredi güvenliği bu
    riskin üstünde tutuldu. Bkz. HANDOFF §3.5.
    """
    return CollectResult(written=0, quota=None, failed_leagues=(), leagues_mirrored=False)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} tanımlı değil")
    return value


def _normalised(record: dict[str, Any]) -> dict[str, Any]:
    # ── BU NORMALİZASYON LOAD-BEARING'DİR, SADELEŞTİRMEYİN ──────────────────
    # Zincir hash'i satırın kanonik JSON METNİNİ kapsıyor. Postgres aynı değeri
    # farklı Python tipiyle geri veriyor ve metin hâli değişiyor:
    #   numeric  → Decimal: json.dumps(Decimal) TypeError fırlatır; ayrıca
    #              yazarken float 2.40 → "2.4", okurken Decimal("2.40") → "2.40"
    #   timestamptz → datetime: yazma tarafı (db.snapshot_payload) ile okuma tarafı
    #              AYNI `canonical_timestamp` fonksiyonunu çağırır. Burada ikinci bir
    #              biçimlendirme yazılırsa iki taraf sessizce ayrışır — yasak.
    # Bu dönüşümler kaldırılırsa KURCALANMAMIŞ HER SATIR "KIRIK" der —
    # yanlış alarm, kaçırılan kurcalama kadar zararlıdır çünkü alarma güven biter.
    return {
        **record,
        "observed_at": canonical_timestamp(record["observed_at"]),
        "bookmaker_last_update": (
            None
            if record["bookmaker_last_update"] is None
            else canonical_timestamp(record["bookmaker_last_update"])
        ),
        "point": None if record["point"] is None else float(record["point"]),
        "price": float(record["price"]),
    }


def _ledger_rows(conn: psycopg.Connection[Any], after_id: int | None) -> tuple[dict[str, Any], ...]:
    """Defteri okur. `after_id` verilince yalnız çıpadan SONRAKİ kuyruk çekilir."""
    with conn.cursor() as cur:
        if after_id is None:
            cur.execute(_LEDGER_ALL)
        else:
            cur.execute(_LEDGER_AFTER, (after_id,))
        columns = [desc[0] for desc in cur.description or ()]
        records = tuple(dict(zip(columns, record, strict=True)) for record in cur.fetchall())
    return tuple(_normalised(record) for record in records)


def _ledger_row(conn: psycopg.Connection[Any], row_id: int) -> dict[str, Any] | None:
    """Tek satırı yükü ve prev_hash'iyle birlikte okur — hash yeniden hesaplanabilsin diye."""
    with conn.cursor() as cur:
        cur.execute(_LEDGER_AT, (row_id,))
        columns = [desc[0] for desc in cur.description or ()]
        found = cur.fetchone()
    return None if found is None else _normalised(dict(zip(columns, found, strict=True)))


def _anchor_break(conn: psycopg.Connection[Any], anchor: Anchor) -> str | None:
    """Çıpanın işaret ettiği satırın İÇERİĞİ hâlâ çıpadaki hash'i üretiyor mu?

    TRUNCATE satır-seviyesi append-only tetikleyicisini ATEŞLEMEZ. Kuyruk kesilip aynı
    sayıda sahte satır eklenirse kalan zincir kendi içinde tutarlıdır ve satır sayısı da
    tutar — çıplak zincir doğrulaması bunu göremez. Arızayı yalnız dışarıda yayınlanmış
    hash gösterir.

    SAKLANAN `row_hash` HÜCRESİ DELİL DEĞİLDİR: yayınlanan head herkese açıktır ve
    veritabanına yazabilen biri o açık değeri last_id satırının hücresine yazıp sahte
    kuyruğunu oradan zincirleyebilir. Bu yüzden hash, satırın yükünden ve `prev_hash`
    değerinden YENİDEN HESAPLANIR; hücrenin kendisine bakılmaz.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM odds_snapshots")
        total = int((cur.fetchone() or (0,))[0])
    row = _ledger_row(conn, anchor.last_id)
    if row is None:
        return f"çıpanın işaret ettiği satır (id={anchor.last_id}) defterde yok"
    if row_hash(str(row["prev_hash"]), payload_of(row)) != anchor.head:
        return f"id={anchor.last_id} satırının içeriği çıpadaki hash'i üretmiyor"
    if total < anchor.rows:
        return f"defterde {total} satır var, çıpa {anchor.rows} diyordu"
    return None


def _first_anchor_break(conn: psycopg.Connection[Any], anchors: tuple[Anchor, ...]) -> str | None:
    """Verilen çıpaları SIRAYLA sorar, ilk uyuşmazlığı dosya adıyla döner.

    Hangi çıpaların sorulacağına KENDİSİ karar vermez — çağıran (`_verify_chain_command`)
    belirler: varsayılan modda yalnız en eski+en yeni, `--full` altında HER çıpa.
    """
    for anchor in anchors:
        if anchor.last_id <= 0:
            continue  # Boş defterin çıpası: kesilecek kuyruk yok.
        breakage = _anchor_break(conn, anchor)
        if breakage is not None:
            return f"{breakage} ({anchor.path.name})"
    return None


def _sources_audit_command(*, today: date) -> int:
    """`config/sources.yaml`'ı commit'lenmiş robots anlık görüntülerine karşı sorar — ağsız."""
    violations = audit_offline(load_sources(SOURCES_PATH), ROBOTS_DIR, today)
    if not violations:
        sys.stdout.write("kaynak politikası: TEMİZ\n")
        return 0
    for text in violations:
        sys.stdout.write(f"KAYNAK POLİTİKASI İHLALİ: {text}\n")
    return EXIT_SOURCE_POLICY


def _report_chain(result: ChainResult) -> int:
    sys.stdout.write(
        f"zincir: {'SAĞLAM' if result.ok else 'KIRIK'} "
        f"kontrol={result.checked} baş={result.head[:16]} hata={result.error}\n"
    )
    return 0 if result.ok else 1


def _verify_chain_command(
    conn: psycopg.Connection[Any], *, anchor_dir: Path = ANCHOR_DIR, full: bool = False
) -> int:
    scan = _scan_anchors(anchor_dir)
    anchors = scan.readable
    if scan.downgraded is not None and anchors:
        # Düşürülen kontrol de geçmek değildir: en yeni çıpanın kanıtı kullanılamadı,
        # kuyruk yalnız daha ESKİ bir çıpadan doğrulandı. Tek iz bir log uyarısı olursa
        # `zincir: SAĞLAM` satırını okuyan operatör hangi çıpaya bakıldığını bilemez (G4).
        sys.stdout.write(
            f"en yeni çıpa okunamadı ({scan.downgraded.name}) — kuyruk kesme kontrolü "
            "bir önceki çıpaya düşürüldü, EN YENİ ÇIPA ATLANDI\n"
        )
    expected = expected_anchor_names(anchor_dir)
    if expected is None:
        # Atlanan kontrol geçmek değildir: sessiz kalınmaz, adıyla yazılır.
        sys.stdout.write("git geçmişi okunamadı — ÇIPA EKSİKLİĞİ KONTROLÜ ATLANDI\n")
    else:
        archived = archived_anchors(anchor_dir, recorded=expected)
        if archived:
            # RUNBOOK §1.4: arşivleme (TAŞIMA) meşrudur ama kanıtı GÖTÜRÜR. Bu satır o
            # kaybı sessiz bırakmaz — ama meşru bir prosedür kapıyı kalıcı kırmızı da
            # yapmaz: yalnız SİLİNEN (hiçbir yerde bulunamayan) çıpa aşağıda exit 1 verir.
            sys.stdout.write(
                "ÇIPA ARŞİVLENDİ (kanıt kapsamı daraldı): " + ", ".join(archived) + "\n"
            )
        gone = missing_anchors(anchor_dir, recorded=expected)
        if gone:
            sys.stdout.write(
                "ÇIPA EKSİK (git geçmişinde var, diskte yok): " + ", ".join(gone) + "\n"
            )
            return 1
    if not anchors:
        # Atlanan kontrol geçmek değildir: sessiz kalınmaz, adıyla yazılır.
        sys.stdout.write("çıpa yok ya da okunamadı — kuyruk kesme kontrolü ATLANDI\n")
        return _report_chain(verify_chain(_ledger_rows(conn, None)))
    # En eski çıpa da sorulur: yalnız en yeniye bakmak, `ledger/`deki dosyayı da değiştiren
    # bir saldırganın yeniden yazdığı öneki göremez (F2). --full altında HER çıpa sorulur ve
    # defter GENESIS'ten yeniden hash'lenir; varsayılan mod yalnız (en eski, en yeni) çiftini
    # sorar ve yalnız kuyruğu tarar — aradaki satırlar hiç yeniden hash'lenmez (DEFERRED
    # §1.1, §1.2).
    asked = anchors if (full or len(anchors) == 1) else (anchors[0], anchors[-1])
    breakage = _first_anchor_break(conn, asked)
    if breakage is not None:
        sys.stdout.write(f"ÇIPA UYUŞMAZLIĞI: {breakage}\n")
        return 1
    newest = anchors[-1]
    if full:
        sys.stdout.write(f"tam tarama: {len(asked)} çıpa soruldu, defter GENESIS'ten taranıyor\n")
        return _report_chain(verify_chain(_ledger_rows(conn, None)))
    if newest.last_id <= 0:
        # Boş defterin çıpası: kesilecek kuyruk yok, defter GENESIS'ten doğrulanır.
        return _report_chain(verify_chain(_ledger_rows(conn, None)))
    return _report_chain(verify_chain(_ledger_rows(conn, newest.last_id), start_hash=newest.head))


def _publish_head_command(
    conn: psycopg.Connection[Any], now: datetime, *, directory: Path = ANCHOR_DIR
) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*), coalesce(max(id), 0) FROM odds_snapshots")
        found = cur.fetchone() or (0, 0)
    count, last_id = int(found[0]), int(found[1])
    head = chain_head(conn)
    target = directory / f"head-{now:%Y-%m-%d}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    # last_id olmadan kuyruk kesme kontrolü kurulamaz: doğrulama nereden devam edeceğini bilemez.
    target.write_text(
        f"{now.isoformat()}\nrows={count}\nlast_id={last_id}\nhead={head}\n", encoding="utf-8"
    )
    sys.stdout.write(f"zincir başı yazıldı: {target}\n")
    return 0


def _report(result: CollectResult) -> int:
    remaining = "bilinmiyor" if result.quota is None else str(result.quota.remaining)
    sys.stdout.write(f"yazılan satır: {result.written}, kalan kredi: {remaining}\n")
    if result.missed_seals:
        # Kaçan mühür kalıcıdır; sessiz exit 0 arızayı gizler.
        sys.stdout.write("kaçan mühür: " + ", ".join(result.missed_seals) + "\n")
    if not result.leagues_mirrored:
        sys.stdout.write("lig aynası tazelenemedi — tur hiç başlatılmadı, kredi harcanmadı\n")
    if result.quota_exhausted:
        sys.stdout.write("kredi tükendi — tur erken kapandı\n")
    if result.failed_leagues:
        # Diğer ligler toplandı ama bu sessizce geçilmemeli: CI kırmızı olmalı.
        sys.stdout.write("başarısız ligler: " + ", ".join(result.failed_leagues) + "\n")
    return _exit_code(result)


def _exit_code(result: CollectResult) -> int:
    """Çıkış kodu, rapor TAMAMEN yazıldıktan SONRA seçilir.

    Kod, dalların arasından erken dönüldüğünde aynı turdaki ikinci arıza hiç
    yazılmıyordu: kredi bittiğinde operatör hangi ligin de düştüğünü öğrenemiyordu.

    SIRA yalnız TEK bir sayıya indirgeme sırasıdır, önem sırası değil: aynı turun
    her arızası `_report` tarafından zaten adıyla yazılır. Yerleşik üç basamak
    dokunulmadan bırakıldı (kredi bitişi en üstte — incelenmiş davranış);
    `missed_seals` en alta eklendi, çünkü yukarıdaki üçünün her biri zaten kırmızı
    veriyor ve mührün kaçtığı satır raporda duruyor. Değişen tek şey: BAŞKA hiçbir
    arıza yokken kaçan mühür artık 0 DEĞİL.
    """
    if result.quota_exhausted:
        return EXIT_QUOTA_EXHAUSTED
    if result.failed_leagues:
        return EXIT_LEAGUE_FAILED
    if not result.leagues_mirrored:
        return EXIT_MIRROR_FAILED
    if result.missed_seals:
        return EXIT_MISSED_SEAL
    return 0


def _fetch_tff_command(conn: psycopg.Connection[Any], client: httpx.Client, now: datetime) -> int:
    """`collect_tff` TEK bir ulusal sayfa fetch eder — footystats'ın aksine lig döngüsü
    yok, izole edilecek bir "parça" yok, bu yüzden arıza TÜM komuta aittir.

    `collect_tff` kendi `conn.commit()`ini zaten çağırıyor (başarı yolunda); burada
    `rollback()` yalnız `commit()`in KENDİSİ düşüp bağlantı ayaktayken KALIRSA devreye
    girer (G1 ile aynı sınıf arıza — bkz. `db.py:LEDGER_LOCK_KEY` yorumu) — traceback'i
    yutmuyor, `LOGGER.exception` onu adıyla yazıyor, yalnız bağlantıyı temiz kapatıyor.
    """
    try:
        written = collect_tff(
            conn, client, sources_path=SOURCES_PATH, robots_dir=ROBOTS_DIR, now=now
        )
    except Exception:
        conn.rollback()
        LOGGER.exception("tff toplanamadı")
        sys.stdout.write("tff: toplama başarısız — günlüğe bakın\n")
        return EXIT_SOURCE_FAILED
    sys.stdout.write(f"tff: {written} yeni gözlem\n")
    return 0


def _fetch_venues_command(
    conn: psycopg.Connection[Any], client: httpx.Client, now: datetime
) -> int:
    result: VenuesResult = collect_venues(
        conn, client, sources_path=SOURCES_PATH, robots_dir=ROBOTS_DIR, now=now
    )
    sys.stdout.write(f"venues: {result.written} yeni gözlem\n")
    if result.failed_venues:
        sys.stdout.write("venues başarısız stadyumlar: " + ", ".join(result.failed_venues) + "\n")
    if result.failed_matches:
        sys.stdout.write(
            "venues başarısız maçlar (hava): " + ", ".join(result.failed_matches) + "\n"
        )
    if result.failed_venues or result.failed_matches:
        return EXIT_SOURCE_FAILED
    return 0


def _fetch_news_command(conn: psycopg.Connection[Any], client: httpx.Client, now: datetime) -> int:
    result: NewsCollectResult = collect_news(
        conn, client, sources_path=SOURCES_PATH, robots_dir=ROBOTS_DIR, now=now
    )
    sys.stdout.write(f"news: {result.written} yeni gözlem\n")
    if result.self_stamped:
        # M6: kaynak tarih vermediği için `now`a düşmüş öğeler — yazıldı ama tazelik
        # iddiasının DIŞINDA tutuldu (bkz. collectors.news.collect_news docstring'i).
        # Sessizce yutulmaz: bu sayı burada raporlanmazsa bayrak hiçbir yerde okunmamış olur.
        sys.stdout.write(f"news kendi-damgalı (tazelik denetlenmedi): {result.self_stamped}\n")
    if result.failed_sources:
        sys.stdout.write("news başarısız kaynaklar: " + ", ".join(result.failed_sources) + "\n")
        return EXIT_SOURCE_FAILED
    return 0


def _fetch_results_command(
    conn: psycopg.Connection[Any], client: httpx.Client, now: datetime
) -> int:
    api_key = _require_env("ODDS_API_KEY")
    configured = active_leagues(load_leagues(LEAGUES_PATH))
    result: ResultsCollectResult = collect_results(conn, client, api_key, configured, now)
    sys.stdout.write(f"results: {result.written} yeni sonuç\n")
    if result.scoreless_completed:
        # R34: tamamlanmış ama skorsuz — uydurma 0-0 yazılmadı, adıyla raporlanır.
        sys.stdout.write(
            "results tamamlanmış ama skorsuz: " + ", ".join(result.scoreless_completed) + "\n"
        )
    if result.failed_leagues:
        # `EXIT_LEAGUE_FAILED`ın BİLİNÇLİ yeniden kullanımı — bkz. o sabitin yorumu.
        sys.stdout.write("results başarısız ligler: " + ", ".join(result.failed_leagues) + "\n")
        return EXIT_LEAGUE_FAILED
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="football-edge")
    parser.add_argument(
        "command",
        choices=(
            "snapshot",
            "seal",
            "verify-chain",
            "publish-head",
            "sources-audit",
            "fetch-footystats",
            "fetch-tff",
            "fetch-venues",
            "fetch-news",
            "fetch-results",
        ),
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="verify-chain: defteri GENESIS'ten yeniden hash'le ve HER çıpayı sor",
    )
    args = parser.parse_args(argv)

    now = datetime.now(UTC)

    # `connect()` AÇILMADAN ÖNCE: veritabanına DOKUNMAZ — DATABASE_URL yokken de kırılmaz,
    # `verify.sh`nin ağsız/secret'sız koşma sözleşmesiyle tutarlı.
    if args.command == "sources-audit":
        return _sources_audit_command(today=now.date())

    with connect() as conn:
        if args.command == "verify-chain":
            return _verify_chain_command(conn, full=args.full)
        if args.command == "publish-head":
            return _publish_head_command(conn, now)
        if args.command == "fetch-footystats":
            # Ayrı değişken adı BİLİNÇLİ: `result` aşağıda `CollectResult` için yeniden
            # kullanılıyor; Python fonksiyon kapsamı blok değil, aynı adı iki farklı tipe
            # atamak mypy --strict'i düşürür.
            with httpx.Client() as client:
                footystats_result = collect_footystats(
                    conn,
                    client,
                    active_leagues(load_leagues(LEAGUES_PATH)),
                    sources_path=SOURCES_PATH,
                    robots_dir=ROBOTS_DIR,
                    now=now,
                )
            sys.stdout.write(f"footystats: {footystats_result.written} yeni gözlem\n")
            if footystats_result.failed_leagues:
                # Diğer ligler toplandı ama bu sessizce geçilmemeli: CI kırmızı olmalı
                # (aynı gerekçe collect.py:_report — F4). Sessiz kalırsa "footystats: 0
                # yeni gözlem" hem başarılı ikinci turun hem ALTI LİGİN DE kırıldığı bir
                # turun çıktısı olur (review #3).
                sys.stdout.write(
                    "footystats başarısız ligler: "
                    + ", ".join(footystats_result.failed_leagues)
                    + "\n"
                )
                return EXIT_LEAGUE_FAILED
            return 0
        if args.command == "fetch-tff":
            with httpx.Client() as client:
                return _fetch_tff_command(conn, client, now)
        if args.command == "fetch-venues":
            with httpx.Client() as client:
                return _fetch_venues_command(conn, client, now)
        if args.command == "fetch-news":
            with httpx.Client() as client:
                return _fetch_news_command(conn, client, now)
        if args.command == "fetch-results":
            with httpx.Client() as client:
                return _fetch_results_command(conn, client, now)

        api_key = _require_env("ODDS_API_KEY")
        configured = load_leagues(LEAGUES_PATH)
        # matches.league_id'nin yabancı anahtarı her turdan ÖNCE konfigürasyondan tazelenir.
        if not _mirror_leagues(conn, configured):
            return _report(_mirror_failed())
        with httpx.Client() as client:
            # Ayrı if/else: run_snapshot ve run_seal farklı keyword argümanlara
            # sahip, tek değişkene atanınca mypy --strict uyumsuzluk bildirir.
            if args.command == "snapshot":
                result = run_snapshot(conn, client, api_key, active_leagues(configured), now)
            else:
                result = run_seal(conn, client, api_key, active_leagues(configured), now)
        return _report(result)


if __name__ == "__main__":
    raise SystemExit(main())
