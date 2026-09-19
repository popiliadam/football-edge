from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, date, datetime
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
from football_edge.calibration import language_config_violations, run_calibration
from football_edge.db import chain_head, connect
from football_edge.jev import TypeSafeJev
from football_edge.leagues import active_leagues, load_leagues
from football_edge.ledger import (
    ChainResult,
    canonical_timestamp,
    payload_of,
    row_hash,
    verify_chain,
)
from football_edge.mapping import MappingReport, canonical_team_names, resolve_source_aliases
from football_edge.rounds import (
    CollectResult,
    _mirror_failed,
    _mirror_leagues,
    run_seal,
    run_snapshot,
)
from football_edge.sources import audit_offline, load_sources

LEAGUES_PATH = Path("config/leagues.yaml")
SOURCES_PATH = Path("config/sources.yaml")
ROBOTS_DIR = Path("config/robots")
LANGUAGES_PATH = Path("config/languages.yaml")
CALIBRATION_DIR = Path("data/calibration")

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
# Task 11 (review fix, Minor #3 promoted) — `map-entities` de BU kodu alır: `mapping.
# resolve_source_aliases`in fırlattığı `RuntimeError` (örn. `_alias_text`in eksik
# `team_name` bulgusu) AYNI İSTİSNA, AYNI GEREKÇE — bir kaynağın veri sözleşmesi ihlali,
# "lig" kavramına bağlı değil. `seal.yml`/`snapshot.yml` `map-entities`i de hiç çağırmaz.
EXIT_SOURCE_FAILED = 7
# Task 12 (spec §5.4): ölçülmemiş dil üretime alınamaz. AYNI İSTİSNA/GEREKÇE (yukarıdaki iki
# yorum) — check-languages/calibrate `seal.yml`/`snapshot.yml`ce hiç çağrılmaz. 7 DEĞİL 8:
# `EXIT_SOURCE_FAILED=7` bu brief YAZILDIKTAN SONRA, Task 11'de eklendi.
EXIT_LANGUAGE_UNCALIBRATED = 8

_LEDGER_COLUMNS = """
    SELECT match_id, observed_at, bookmaker, market, outcome, point, price,
           bookmaker_last_update, is_closing, prev_hash, row_hash
    FROM odds_snapshots
"""
_LEDGER_ALL = _LEDGER_COLUMNS + " ORDER BY id"
_LEDGER_AFTER = _LEDGER_COLUMNS + " WHERE id > %s ORDER BY id"
_LEDGER_AT = _LEDGER_COLUMNS + " WHERE id = %s"


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


# R50 (Task 11): dört `_fetch_*_command` (+ footystats) `src/football_edge/fetch.py`ye
# taşındı — collect.py'yi 774/800'de bölme sınırına getiren tam olarak buydu (#M41).
# `main()` onları GECİKMELİ (yerel) import ile çağırır — bkz. fetch.py'nin üst yorumu.

# Task 11 — footystats bugün `entity_kind="team"` yayınlayan TEK kaynak (TFF şimdilik
# yalnız `fixture_official` gözlemliyor, bkz. collectors/tff.py). `--source` yine de
# parametredir: adı `map-entities` kalır, ikinci bir kaynak takım gözlemi yaymaya
# başlarsa komut DEĞİŞMEZ.
DEFAULT_MAPPING_SOURCE = "footystats"


def _map_entities_command(
    conn: psycopg.Connection[Any], source_id: str, league_id: str, now: datetime
) -> int:
    """Bir kaynağın bir ligdeki takım takma adlarını kanonik (The Odds API) ada eşler.

    Gerçek iş `mapping.resolve_source_aliases`de (KOD aday çıkarır, JEV seçer — spec
    §5.3): eşik altı/'hiçbiri' eşleşme YAZILMAZ ama HER İKİSİ de burada adıyla
    raporlanır — atlanan bir eşleşme, farklı kılıktaki sessiz join hatasıdır. Bu
    fonksiyon yalnız CLI camı: kanonik listeyi sorar, Jev istemcisini kurar, raporlar.

    Lig PARAMETREDİR, taranmaz: aynı ad farklı ligde farklı kulüp olabilir
    (`mapping.resolve` docstring'i) — komut bunu OPERATÖRDEN ister, tahmin etmez.
    """
    canonical = canonical_team_names(conn, league_id)
    if not canonical:
        sys.stdout.write(f"map-entities: {league_id} için matches tablosunda takım yok\n")
        return 0
    client = TypeSafeJev()
    try:
        report: MappingReport | None = resolve_source_aliases(
            conn, client, source_id, league_id, canonical, now
        )
    except RuntimeError as exc:
        # Kardeşleriyle AYNI şekil: adıyla stdout satırı + EXIT_SOURCE_FAILED — çıplak
        # traceback değil (review, Minor #3 promoted). `TypeSafeJev()`in KENDİ
        # RuntimeError'ı (anahtar eksik) buraya GİRMEZ: try bloğu yalnız `resolve_
        # source_aliases`i sarıyor, o kurulum hatası hâlâ adıyla, yukarıda, patlıyor.
        sys.stdout.write(f"map-entities: {source_id}/{league_id} eşlenemedi — {exc}\n")
        return EXIT_SOURCE_FAILED
    if report is None:
        sys.stdout.write(f"map-entities: {source_id}/{league_id} için gözlem yok\n")
        return 0
    unresolved = tuple(entry for entry in report.resolutions if entry.canonical_id is None)
    sys.stdout.write(
        f"map-entities: {report.written} eşleşme yazıldı, {len(unresolved)} çözülmedi\n"
    )
    for entry in unresolved:
        # Atlanan eşleşme raporlanmazsa Task 11'in önlemek için var olduğu tam o
        # sessiz arızadır — bir eşleşmeyi atlamak yanlış eşlemekten iyidir, AMA
        # yalnız GÖRÜNÜRSE.
        sys.stdout.write(f"  çözülmedi: {entry.alias!r} — {entry.reason}\n")
    return 0


def _check_languages_command(*, languages_path: Path = LANGUAGES_PATH) -> int:
    """Rapor OLMADAN production_enabled olan dil var mı? Ağa/parayla dokunmaz (Ruling R4)."""
    violations = language_config_violations(languages_path)
    for text in violations:
        sys.stdout.write(f"DİL KALİBRASYON İHLALİ: {text}\n")
    if violations:
        return EXIT_LANGUAGE_UNCALIBRATED
    sys.stdout.write("dil kalibrasyonu: TEMİZ\n")
    return 0


def _calibrate_command(language: str, *, calibration_dir: Path = CALIBRATION_DIR) -> int:
    """Jev'i ELLE etiketlenmiş kümede koşturur; AĞA ÇIKAR, PARA HARCAR, kapı ÇAĞIRMAZ (R4).

    Etiket yoksa Jev hiç KURULMAZ; anahtarsız `TypeSafeJev()` çıplak patlar (map-entities gibi).
    """
    labels_path = calibration_dir / f"{language}.jsonl"
    if not labels_path.is_file():
        sys.stdout.write(f"calibrate: {labels_path} yok — önce elle etiketlenmeli\n")
        return EXIT_LANGUAGE_UNCALIBRATED
    path, reason = run_calibration(language, calibration_dir, TypeSafeJev())
    sys.stdout.write(f"calibrate: {reason}\n")
    sys.stdout.write(f"rapor yazıldı: {path}\n")
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
            "map-entities",
            "calibrate",
            "check-languages",
        ),
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="verify-chain: defteri GENESIS'ten yeniden hash'le ve HER çıpayı sor",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_MAPPING_SOURCE,
        help="map-entities: eşlenecek kaynağın source_id'si (varsayılan: footystats)",
    )
    parser.add_argument(
        "--league",
        default=None,
        help="map-entities: lig id'si (config/leagues.yaml) — ZORUNLU, tahmin edilmez",
    )
    parser.add_argument("--language", default=None, help="calibrate: ISO dil kodu (örn. tr)")
    args = parser.parse_args(argv)

    now = datetime.now(UTC)

    # `connect()` AÇILMADAN ÖNCE: veritabanına DOKUNMAZ — DATABASE_URL yokken de kırılmaz.
    # `check-languages`/`calibrate` de BURADA dallanır (Ruling R4), aynı gerekçeyle.
    if args.command == "sources-audit":
        return _sources_audit_command(today=now.date())
    if args.command == "check-languages":
        return _check_languages_command()
    if args.command == "calibrate":
        if not args.language:
            parser.error("calibrate için --language zorunlu")
        return _calibrate_command(args.language)
    if args.command == "map-entities" and not args.league:
        parser.error(
            "map-entities için --league zorunlu (aynı ad farklı ligde farklı kulüp olabilir)"
        )

    with connect() as conn:
        if args.command == "verify-chain":
            return _verify_chain_command(conn, full=args.full)
        if args.command == "publish-head":
            return _publish_head_command(conn, now)
        if args.command == "map-entities":
            return _map_entities_command(conn, args.source, args.league, now)
        if args.command in (
            "fetch-footystats",
            "fetch-tff",
            "fetch-venues",
            "fetch-news",
            "fetch-results",
        ):
            # Gecikmeli (yerel) import: `fetch.py` üst düzeyde `collect.py`den sabit/
            # yardımcı içe aktarır (EXIT_*, yol sabitleri, `_require_env`) — modül
            # seviyesinde İKİ YÖNLÜ bir import döngüsel olurdu. Bu satır yalnız `main()`
            # ÇAĞRILDIĞINDA çalışır, o ana kadar iki modül de tam yüklenmiş olur.
            import football_edge.fetch as fetch

            with httpx.Client() as client:
                if args.command == "fetch-footystats":
                    return fetch._fetch_footystats_command(conn, client, now)
                if args.command == "fetch-tff":
                    return fetch._fetch_tff_command(conn, client, now)
                if args.command == "fetch-venues":
                    return fetch._fetch_venues_command(conn, client, now)
                if args.command == "fetch-news":
                    return fetch._fetch_news_command(conn, client, now)
                return fetch._fetch_results_command(conn, client, now)

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
