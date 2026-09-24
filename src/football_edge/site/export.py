"""`site export`: tek salt okuma işleminde defteri doğrula, türet, iki kez türet, denetle, yaz.

Faz 6 İz B tasarımı §5.1 (B12). Adımların hepsi `REPEATABLE READ, READ ONLY` TEK işlemdedir:
`matches.commence_time` her snapshot turunda UPDATE edilir, defter kesimi onu dondurmaz — işlem
dondurur. Herhangi bir kontrol kırmızıysa HİÇBİR dosya yazılmaz ve `ExportRefused` adıyla yükselir.
Log yalnız sayı ve hash taşır; girdi dökümü (kitap bazında fiyat) ne diske ne loga gider.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
import yaml

from football_edge.anchors import (
    ANCHOR_DIR,
    Anchor,
    _scan_anchors,
    archived_anchors,
    expected_anchor_names,
    missing_anchors,
)
from football_edge.collect import LEDGER_AUDIT_VIEW, _first_anchor_break, _ledger_rows
from football_edge.ledger import GENESIS, _canonical, verify_chain
from football_edge.market.devig import METHODS
from football_edge.site.contract import (
    EXIT_SITE_CHAIN,
    EXIT_SITE_CONFIG,
    EXIT_SITE_CUT,
    EXIT_SITE_INVALID,
    EXIT_SITE_NONDETERMINISTIC,
    MOVE_MIN_MATCHES,
    PATH_ID_LENGTH,
    PUBLIC_FLOOR,
    RECORD_COLUMNS,
    SITE_MIN_BOOKS,
    SITE_MIN_TEAM_MATCHES,
    content_sha256,
    iso_z,
)
from football_edge.site.derive import DeriveError, derive, record_mismatches
from football_edge.site.inputs import AnchorValue, DumpConfig, LedgerCut, dump_text, load_inputs
from football_edge.site.slugs import load_league_slugs
from football_edge.site.verify import snapshot_errors

LOGGER = logging.getLogger("football_edge.site.export")
SNAPSHOT_FILE = "snapshot.json"
HASH_FILE = "snapshot.sha256"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHILD_ENV_DROPPED = ("SITE_DATABASE_URL", "DATABASE_URL")

_ISOLATION = (
    "SELECT current_setting('transaction_isolation'), current_setting('transaction_read_only')"
)
_FLOOR = "SELECT site.public_floor()"
_AUDIT_LAST_ID = f"SELECT coalesce(max(id), 0) FROM {LEDGER_AUDIT_VIEW}"
_HEAD = "SELECT rows, last_id, head FROM site.ledger_head"
_LEAGUES = "SELECT id, name, country FROM site.leagues ORDER BY id"
_MATCHES = "SELECT id, league_id, commence_time, home_team, away_team FROM site.matches ORDER BY id"
_QUOTES = (
    "SELECT ledger_id, match_id, observed_at, is_closing, outcome, price, book_key "
    "FROM site_input.h2h_quotes WHERE ledger_id <= %s ORDER BY ledger_id"
)
_RECORD = (
    f"SELECT {', '.join(name for name, _ in RECORD_COLUMNS)} FROM site.record "
    "ORDER BY publication_id"
)


class ExportRefused(RuntimeError):
    """Yayın yok: `code` CLI'nin çıkış kodu, mesaj adıyla ne olduğunu söyler (değer taşımaz)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExportSummary:
    matches: int
    leagues: int
    teams: int
    rows: int
    last_id: int
    content_sha256: str
    file_sha256: str


def devig_method(path: Path) -> str:
    """Modelin vig yöntemi (`config/model_faz3.yaml` `method`); `backtest` import edilmez (H1f)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    method = raw.get("method") if isinstance(raw, dict) else None
    if method not in METHODS:
        raise ExportRefused(EXIT_SITE_CONFIG, f"{path}: vig yöntemi okunamadı")
    return str(method)


def site_league_slugs(path: Path) -> Mapping[str, str]:
    """`config/site_leagues.yaml` (Task 4); eksik ya da kural dışıysa adlandırılmış çıkış (N3).

    Mesaj yalnız yolu ve yükleyicinin kuralını taşır (lig kimliği, slug); secret taşımaz.
    """
    try:
        return load_league_slugs(path)
    except (OSError, ValueError, yaml.YAMLError) as error:
        reason = f"{type(error).__name__}: {(str(error).splitlines() or [''])[0]}"
        raise ExportRefused(
            EXIT_SITE_CONFIG, f"{path}: lig slug'ları okunamadı ({reason})"
        ) from None


def derive_in_subprocess(dump: str, *, hash_seed: str) -> str:
    """Aynı dökümden AYRI bir süreçte, verilen `PYTHONHASHSEED`le türetilen `content_sha256`.

    Çocuk DB'ye bağlanamaz (adres ortamından çıkarılır). Çıktısı ve hatası YAKALANIR ve loga
    aktarılmaz: çöken çocuğun traceback'i bir fiyat taşıyabilir.
    """
    env = {key: value for key, value in os.environ.items() if key not in _CHILD_ENV_DROPPED}
    env["PYTHONHASHSEED"] = hash_seed
    try:
        result = subprocess.run(
            [sys.executable, "-m", "football_edge.site", "derive-stdin"],
            input=dump,
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        raise ExportRefused(
            EXIT_SITE_NONDETERMINISTIC, "ikinci türetim alt süreci 300 sn'de bitmedi"
        ) from None
    if result.returncode != 0:
        raise ExportRefused(
            EXIT_SITE_NONDETERMINISTIC,
            f"ikinci türetim alt süreci düştü, çıkış kodu {result.returncode}",
        )
    found = result.stdout.strip()
    if _SHA256.fullmatch(found) is None:
        raise ExportRefused(EXIT_SITE_NONDETERMINISTIC, "ikinci türetim beklenmeyen çıktı verdi")
    return found


def dump_refusal(error: Exception) -> str:
    """Çözülemeyen döküm yalnız istisnanın SINIFIYLA adlandırılır: metni bir fiyat taşıyabilir
    (`float("4.47x")`) ve dışa aktarımın çıktısı public Actions loguna düşer."""
    return f"girdi dökümü çözülemedi ({type(error).__name__})"


def other_hash_seed(environ: Mapping[str, str]) -> str:
    """Bu sürecin tohumundan FARKLI sabit bir tohum (ölçülen tek fark hash tohumudur)."""
    return "2" if environ.get("PYTHONHASHSEED") == "1" else "1"


def run_export(
    conn: psycopg.Connection[Any],
    out_dir: Path,
    *,
    generated_at: datetime,
    git_sha: str,
    method: str,
    schema: Mapping[str, Any],
    league_slugs: Mapping[str, str],
    anchor_dir: Path = ANCHOR_DIR,
    derive_elsewhere: Callable[[str], str] | None = None,
) -> ExportSummary:
    """§5.1'in altı adımı; hepsi geçerse iki dosya yazılır, biri kırmızıysa hiçbiri."""
    _require_empty_out(out_dir)
    conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    conn.read_only = True
    with conn.transaction():
        _require_isolation(conn)
        anchor, verified = _verified_chain(conn, anchor_dir)
        cut = _cut(conn, anchor, verified)
        dump = _dump(conn, cut, anchor, method, league_slugs)
    try:
        inputs = load_inputs(dump)
        body = derive(inputs)
    except DeriveError as error:
        raise ExportRefused(EXIT_SITE_CUT, str(error)) from None
    except (KeyError, TypeError, ValueError) as error:
        raise ExportRefused(EXIT_SITE_CUT, dump_refusal(error)) from None
    local = content_sha256(body)
    elsewhere = derive_elsewhere or (
        lambda text: derive_in_subprocess(text, hash_seed=other_hash_seed(os.environ))
    )
    if elsewhere(dump) != local:
        raise ExportRefused(
            EXIT_SITE_NONDETERMINISTIC, "ikinci türetim farklı content_sha256 üretti"
        )
    problems = record_mismatches(inputs)
    if problems:
        raise ExportRefused(EXIT_SITE_CUT, "; ".join(problems))
    snapshot = {
        **body,
        "generated_at": iso_z(generated_at),
        "git_sha": git_sha,
        "content_sha256": local,
    }
    errors = snapshot_errors(snapshot, schema)
    if errors:
        raise ExportRefused(EXIT_SITE_INVALID, f"verify-snapshot: {len(errors)} ihlal: {errors[0]}")
    return _write(out_dir, snapshot, cut)


def _require_isolation(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(_ISOLATION)
        found = cur.fetchone()
    if found is None or tuple(found) != ("repeatable read", "on"):
        raise ExportRefused(EXIT_SITE_CUT, "işlem REPEATABLE READ, READ ONLY değil")


def _verified_chain(conn: psycopg.Connection[Any], anchor_dir: Path) -> tuple[Anchor, LedgerCut]:
    """HER çıpa sorulur, kesim GENESIS'ten yeniden hash'lenir (§5.1/1); indirgeme kırmızıdır.

    Dönen kesim DOĞRULANAN satırlardandır (sayı, son kimlik, yeniden hesaplanmış baş).
    """
    anchors = _anchors_to_ask(anchor_dir)
    breakage = _first_anchor_break(conn, anchors, relation=LEDGER_AUDIT_VIEW)
    if breakage is not None:
        raise ExportRefused(EXIT_SITE_CHAIN, f"ÇIPA UYUŞMAZLIĞI: {breakage}")
    rows = _ledger_rows(conn, None, relation=LEDGER_AUDIT_VIEW)
    result = verify_chain(rows)
    if not result.ok:
        raise ExportRefused(
            EXIT_SITE_CHAIN, f"zincir KIRIK: {result.failed_index}. satır, {result.error}"
        )
    if rows and anchors[-1].last_id <= 0:
        raise ExportRefused(
            EXIT_SITE_CHAIN, f"en yeni çıpa boş defteri gösteriyor ({anchors[-1].path.name})"
        )
    # Kimlik hash'e girmez (`ledger._CHAIN_KEYS`): son kimlik aynı işlemde aynı görünümden okunur.
    with conn.cursor() as cur:
        cur.execute(_AUDIT_LAST_ID)
        last_id = int((cur.fetchone() or (0,))[0])
    return anchors[-1], LedgerCut(len(rows), last_id, result.head)


def _anchors_to_ask(anchor_dir: Path) -> tuple[Anchor, ...]:
    """Depodaki bütün çıpalar; okunamayan, eksik ya da tutarsız boş çıpa kırmızıdır."""
    try:
        scan = _scan_anchors(anchor_dir)
    except (OSError, UnicodeDecodeError) as error:
        raise ExportRefused(
            EXIT_SITE_CHAIN, f"çıpa dosyası okunamadı ({type(error).__name__})"
        ) from None
    if scan.downgraded is not None:
        raise ExportRefused(
            EXIT_SITE_CHAIN, f"en yeni çıpa okunamadı ({scan.downgraded.name}) — indirgeme yok"
        )
    if not scan.readable:
        raise ExportRefused(EXIT_SITE_CHAIN, "çıpa yok ya da okunamadı — çıpasız yayın yok")
    # `_scan_anchors` okunamayan ESKİ dosyayı sessizce düşürür; sorulmayan çıpa da indirgemedir.
    read = {anchor.path.name for anchor in scan.readable}
    unreadable = sorted(p.name for p in anchor_dir.glob("head-*.txt") if p.name not in read)
    if unreadable:
        raise ExportRefused(EXIT_SITE_CHAIN, "okunamayan çıpa: " + ", ".join(unreadable))
    # `_first_anchor_break` `last_id <= 0`ı boş defterin çıpası sayıp atlar: öyle olduğu sınanır.
    hollow = [
        anchor.path.name
        for anchor in scan.readable
        if anchor.last_id <= 0 and (anchor.rows != 0 or anchor.head != GENESIS)
    ]
    if hollow:
        raise ExportRefused(EXIT_SITE_CHAIN, "boş defter çıpası tutarsız: " + ", ".join(hollow))
    expected = expected_anchor_names(anchor_dir)
    if expected is None:
        raise ExportRefused(
            EXIT_SITE_CHAIN, "git geçmişi okunamadı — ÇIPA EKSİKLİĞİ KONTROLÜ ATLANDI (kırmızı)"
        )
    gone = missing_anchors(anchor_dir, recorded=expected)
    if gone:
        raise ExportRefused(EXIT_SITE_CHAIN, "ÇIPA EKSİK: " + ", ".join(gone))
    archived = archived_anchors(anchor_dir, recorded=expected)
    if archived:
        LOGGER.warning("arşivlenmiş çıpa (kanıt kapsamı daraldı): %d", len(archived))
    return scan.readable


def _cut(conn: psycopg.Connection[Any], anchor: Anchor, verified: LedgerCut) -> LedgerCut:
    with conn.cursor() as cur:
        cur.execute(_FLOOR)
        floor = (cur.fetchone() or (None,))[0]
        cur.execute(_HEAD)
        found = cur.fetchone()
    if floor != PUBLIC_FLOOR:
        raise ExportRefused(EXIT_SITE_CUT, "site.public_floor() Python tabanından farklı (H1)")
    if found is None:
        raise ExportRefused(EXIT_SITE_CUT, "site.ledger_head satır döndürmedi")
    rows, last_id = int(found[0]), int(found[1])
    if anchor.rows > 0 and rows == 0:
        raise ExportRefused(
            EXIT_SITE_CUT, "çıpa satır diyor, görünüm 0 satır döndü (görünüm sahipliği/RLS?)"
        )
    # İki görünüm aynı tabloya aynı RR anlık görüntüsünde bakar: fark sahiplik/süzgeç arızasıdır.
    if (rows, last_id) != (verified.rows, verified.last_id):
        raise ExportRefused(EXIT_SITE_CUT, "site.ledger_head doğrulanan zincirle uyuşmuyor")
    return verified


def _dump(
    conn: psycopg.Connection[Any],
    cut: LedgerCut,
    anchor: Anchor,
    method: str,
    league_slugs: Mapping[str, str],
) -> str:
    with conn.cursor() as cur:
        leagues = _all(cur, _LEAGUES)
        matches = _all(cur, _MATCHES)
        quotes = _all(cur, _QUOTES, (cut.last_id,))
        record = _all(cur, _RECORD)
    quoted = {row[1] for row in quotes}
    shown = [row for row in matches if row[0] in quoted]
    if anchor.rows > 0 and not shown:
        raise ExportRefused(EXIT_SITE_CUT, "defterde satır var ama maç kümesi boş")
    if any(row[2] < PUBLIC_FLOOR for row in matches):
        raise ExportRefused(EXIT_SITE_CUT, "görünüm tabandan eski bir maç döndürdü (H1)")
    unslugged = sorted(str(row[0]) for row in leagues if row[0] not in league_slugs)
    if unslugged:
        raise ExportRefused(
            EXIT_SITE_CONFIG,
            "config/site_leagues.yaml'da slug'ı olmayan lig: " + ", ".join(unslugged),
        )
    return dump_text(
        config=DumpConfig(
            method, SITE_MIN_BOOKS, SITE_MIN_TEAM_MATCHES, MOVE_MIN_MATCHES, PATH_ID_LENGTH
        ),
        floor=PUBLIC_FLOOR,
        ledger=cut,
        anchor=AnchorValue(anchor.path.name, anchor.rows, anchor.last_id, anchor.head),
        leagues=[(*row, league_slugs[str(row[0])]) for row in leagues],
        matches=matches,
        quotes=quotes,
        record=record,
    )


def _all(cur: psycopg.Cursor[Any], sql: str, params: tuple[Any, ...] = ()) -> list[Sequence[Any]]:
    cur.execute(sql, params or None)
    return [tuple(row) for row in cur.fetchall()]


def _require_empty_out(out_dir: Path) -> None:
    """`--out` ya yok ya boş bir dizin: bayat dosyayla yayın yok, dosya yolunun üstüne yazılmaz."""
    try:
        occupied = out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir()))
    except OSError as error:
        raise ExportRefused(
            EXIT_SITE_CONFIG, f"çıktı dizini okunamadı ({type(error).__name__})"
        ) from None
    if occupied:
        raise ExportRefused(
            EXIT_SITE_CONFIG, f"{out_dir} boş değil ya da dizin değil — bayat dosyayla yayın yok"
        )


def _write(out_dir: Path, snapshot: Mapping[str, Any], cut: LedgerCut) -> ExportSummary:
    """İki dosya bir hazırlama dizinine yazılır, dizin TEK `rename`le `--out` olur: yarım yayın yok.

    POSIX'te dizin boş bir dizinin üstüne taşınabilir. Hata metni basılmaz (yol taşır), sınıf adı.
    """
    payload = (_canonical(dict(snapshot)) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    staging: Path | None = None
    try:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}-", dir=out_dir.parent))
        (staging / SNAPSHOT_FILE).write_bytes(payload)
        (staging / HASH_FILE).write_text(f"{digest}  {SNAPSHOT_FILE}\n", encoding="utf-8")
        staging.rename(out_dir)
    except OSError as error:
        _discard(staging)
        raise ExportRefused(
            EXIT_SITE_CONFIG, f"çıktı yazılamadı ({type(error).__name__})"
        ) from None
    return ExportSummary(
        matches=len(snapshot["matches"]),
        leagues=len(snapshot["leagues"]),
        teams=len(snapshot["teams"]),
        rows=cut.rows,
        last_id=cut.last_id,
        content_sha256=str(snapshot["content_sha256"]),
        file_sha256=digest,
    )


def _discard(staging: Path | None) -> None:
    """Başarısız yazımın KENDİ hazırlama dizini: yalnız iki bilinen dosya ve dizinin kendisi."""
    if staging is None:
        return
    for name in (SNAPSHOT_FILE, HASH_FILE):
        with contextlib.suppress(OSError):
            (staging / name).unlink(missing_ok=True)
    with contextlib.suppress(OSError):
        staging.rmdir()
