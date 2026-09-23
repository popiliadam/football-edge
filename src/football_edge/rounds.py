from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

import httpx
import psycopg

from football_edge.db import insert_snapshots, upsert_leagues, upsert_matches
from football_edge.leagues import League
from football_edge.ledger import canonical_timestamp
from football_edge.odds_api import (
    PriceRow,
    Quota,
    QuotaExhausted,
    fetch_event_times,
    fetch_odds,
    guard_quota,
)

LOGGER = logging.getLogger("football_edge.rounds")

# R53: `collect.py` 799/800 satırda ikinci sınıra ulaştı (ilk ikisi anchors.py ve R50/
# fetch.py'yi doğuran bölünmelerdi). Faz 0'ın tur orkestrasyonu — `_collect` ve onu saran
# `run_snapshot`/`run_seal`, mühür adayı/damga yardımcıları, lig aynası tazeleme,
# `CollectResult`/`SealCandidates` ve `MIN_PRICE` — DOMAIN mantığıdır, CLI değildir;
# buraya taşınması `collect.py`yi CLI dispatch'ine, defter/zincir komutlarına, kaynak
# denetimine ve varlık eşlemesine bırakır.
#
# Bağımlılık TEK YÖNLÜDÜR ve fetch.py'nin aksine GECİKMELİ import GEREKMEZ: bu modül
# `football_edge.collect`tan HİÇBİR ŞEY içe aktarmaz — aşağıdaki fonksiyonların hiçbiri
# EXIT_*, yol sabitleri ya da `_require_env`e dokunmaz. `collect.py` ise `main()`in
# ihtiyaç duyduğu `CollectResult`, `_mirror_leagues`, `_mirror_failed`, `run_snapshot`,
# `run_seal`i BU modülden üst düzeyde (modül seviyesinde) içe aktarır — döngü yok, çünkü
# bu yön tek yönlü: `rounds.py` `collect.py`yi hiç bilmez.

# db/migrations/0001_init.sql → check (price > 1.0). Şema kısıtının kod tarafındaki karşılığı.
MIN_PRICE = 1.0


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
    # Boş tur bekçisi: HİÇBİR lig satır yazmadığı hâlde ufukta fikstürü olan ligler. Yalnız
    # snapshot turu doldurur; bkz. `_leagues_with_fixtures`.
    fixtures_without_odds: tuple[str, ...] = ()


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
    horizon = horizon_iso(now, horizon_days)
    result = _collect(
        conn,
        client,
        api_key,
        leagues,
        now,
        commence_time_to=horizon,
        is_closing=False,
        min_remaining=min_remaining,
    )
    if not _silently_empty(result):
        return result
    flagged = _leagues_with_fixtures(client, api_key, leagues, horizon)
    return replace(result, fixtures_without_odds=flagged)


def _silently_empty(result: CollectResult) -> bool:
    """Tur arızasız bitti ama HİÇBİR lig satır yazmadı: milli ara mı, sessiz arıza mı?

    Kredi bitişi ya da düşen lig turu zaten kırmızıya çevirir ve boşluğu açıklayabilir —
    bekçi onlara karışmaz. Kısmi boşluk (bir lig yazdı, öteki boş) KASITLI olarak soru
    değildir: bazı liglerin eu-bölge oranı fikstürden günler sonra açılır.
    """
    return result.written == 0 and not result.failed_leagues and not result.quota_exhausted


def _leagues_with_fixtures(
    client: httpx.Client, api_key: str, leagues: tuple[League, ...], horizon: str
) -> tuple[str, ...]:
    """Oranı boş dönen ligler arasında ufukta fikstürü olanlar — ücretsiz `/events` ucundan.

    Ufuk, `/odds`a giden `commenceTimeTo` ile AYNI metindir ve istemci tarafında da
    uygulanır: API parametreyi yok sayarsa milli aradaki 16 gün sonraki fikstür arızaya
    dönmesin. Bekçinin kendi arızası turu KIRMIZIYA ÇEVİRMEZ (bir ağ hıçkırığı toplayıcıyı
    düşürmemeli) — ama o lig için boşluğun doğrulanamadığı logda adıyla yazılır.
    """
    limit = datetime.fromisoformat(canonical_timestamp(horizon))
    flagged: tuple[str, ...] = ()
    for league in leagues:
        try:
            times = fetch_event_times(
                client, api_key, league.odds_api_key, commence_time_to=horizon
            )
            # Ayrıştırma da bekçinin işidir: bozuk saat turu çökertmez (son inceleme M-1).
            upcoming = sum(
                1 for time in times if datetime.fromisoformat(canonical_timestamp(time)) <= limit
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            LOGGER.warning(
                "lig=%s fikstür kontrolü yapılamadı (%s) — boş tur doğrulanamadı, "
                "tur bu yüzden kırmızıya çevrilmiyor",
                league.id,
                _describe(error),
            )
            continue
        LOGGER.info("lig=%s oran yok, ufuktaki fikstür=%d", league.id, upcoming)
        if upcoming:
            flagged = (*flagged, league.id)
    return flagged


def _describe(error: Exception) -> str:
    """URL'siz tanım: `HTTPStatusError` metni tam URL'yi, yani anahtarı taşır."""
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code}"
    return type(error).__name__


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
