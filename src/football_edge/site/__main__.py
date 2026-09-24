"""`python -m football_edge.site {export,verify-snapshot,derive-stdin}` (Faz 6 İz B §5.1).

`export`: `SITE_DATABASE_URL` (yalnız `site_reader`) ile tek salt okuma işleminde anlık görüntü
üretir; secret'ın varlığını kendisi denetler. `verify-snapshot`: DB'siz denetim; B-2 ve `site.yml`
bu komutu çağırır. `derive-stdin`: dışa aktarımın ikinci türetimi için İÇ komut — girdi dökümünü
stdin'den okur, yalnız `content_sha256` basar, DB'ye bağlanmaz.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import psycopg

from football_edge.collect import configure_logging
from football_edge.db import connect
from football_edge.site.contract import (
    DEVIG_CONFIG_PATH,
    EXIT_SITE_CONFIG,
    EXIT_SITE_CUT,
    EXIT_SITE_INVALID,
    SCHEMA_PATH,
    SITE_LEAGUES_PATH,
    content_sha256,
)
from football_edge.site.derive import DeriveError, derive
from football_edge.site.export import (
    ExportRefused,
    devig_method,
    dump_refusal,
    run_export,
    site_league_slugs,
)
from football_edge.site.inputs import load_inputs
from football_edge.site.schema import check_schema
from football_edge.site.verify import snapshot_errors

LOGGER = logging.getLogger("football_edge.site")
DSN_VAR = "SITE_DATABASE" + "_URL"


def _schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    check_schema(schema)
    return schema


def _git_sha() -> str:
    found = os.environ.get("GITHUB_SHA", "")
    if not found:
        try:
            found = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=30
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            found = ""
    if len(found) != 40:
        raise ExportRefused(EXIT_SITE_CONFIG, "git SHA okunamadı")
    return found


def _export(out_dir: Path) -> int:
    dsn = os.environ.get(DSN_VAR, "")
    if not dsn:
        sys.stdout.write(f"{DSN_VAR} yok — yayın yapılmadı\n")
        return EXIT_SITE_CONFIG
    try:
        method = devig_method(DEVIG_CONFIG_PATH)
        git_sha = _git_sha()
        league_slugs = site_league_slugs(SITE_LEAGUES_PATH)
        with connect(dsn) as conn:
            summary = run_export(
                conn,
                out_dir,
                generated_at=datetime.now(UTC),
                git_sha=git_sha,
                method=method,
                schema=_schema(),
                league_slugs=league_slugs,
            )
    except ExportRefused as refused:
        sys.stdout.write(f"DIŞA AKTARIM REDDEDİLDİ: {refused}\n")
        return refused.code
    except psycopg.Error as error:
        # Metin basılmaz: libpq hatası adresin (parolanın) parçasını taşıyabilir. Yalnız sınıf adı.
        sys.stdout.write(f"DIŞA AKTARIM REDDEDİLDİ: veritabanı hatası ({type(error).__name__})\n")
        return EXIT_SITE_CONFIG
    LOGGER.info(
        "anlık görüntü yazıldı: maç=%d lig=%d takım=%d satır=%d last_id=%d "
        "content_sha256=%s dosya_sha256=%s",
        summary.matches,
        summary.leagues,
        summary.teams,
        summary.rows,
        summary.last_id,
        summary.content_sha256,
        summary.file_sha256,
    )
    return 0


def _derive_stdin() -> int:
    """Çözülemeyen ya da türetilemeyen döküm adlandırılmış çıkıştır (exit 22), traceback değil;
    yalnız istisnanın sınıfı basılır — metni bir fiyat taşıyabilir (dışa aktarımla aynı kural)."""
    try:
        found = content_sha256(derive(load_inputs(sys.stdin.read())))
    except (DeriveError, KeyError, TypeError, ValueError) as error:
        sys.stdout.write(f"İKİNCİ TÜRETİM REDDEDİLDİ: {dump_refusal(error)}\n")
        return EXIT_SITE_CUT
    sys.stdout.write(found + "\n")
    return 0


class _NonJsonConstantError(ValueError):
    """RFC 8259'da NaN/Infinity yok: `json.loads` kabul eder, B-2'nin `JSON.parse`ı etmez."""


def _refuse_constant(_token: str) -> NoReturn:
    raise _NonJsonConstantError


def _load_errors(path: Path, payload: bytes) -> tuple[object, list[str]]:
    """Yükleme hatası da ihlal satırıdır (exit 24); değer ve iz basılmaz (log public).

    Baytlar KATI UTF-8 olarak çözülür: `json.loads(bytes)` UTF-16'yı ve BOM'u sezip kabul ederdi,
    B-2'nin `readFileSync(…, "utf-8")` + `JSON.parse`ı etmez — iki taraf aynı dosyayı görmeli.
    """
    try:
        return json.loads(payload.decode("utf-8"), parse_constant=_refuse_constant), []
    except _NonJsonConstantError:
        return None, [f"{path.name}: JSON dışı sabit (NaN/Infinity)"]
    except RecursionError:
        return None, [f"{path.name}: iç içelik ayrıştırıcının sınırını aşıyor"]
    except ValueError as error:  # JSONDecodeError (BOM dâhil) ve UTF-8 çözme hatası
        where = f" (satır {error.lineno})" if isinstance(error, json.JSONDecodeError) else ""
        return None, [f"{path.name}: geçerli JSON değil{where}"]


def _read(path: Path) -> tuple[bytes | None, list[str]]:
    try:
        return path.read_bytes(), []
    except OSError as error:
        return None, [f"{path.name}: okunamadı ({type(error).__name__})"]


def _content_errors(path: Path, payload: bytes) -> list[str]:
    snapshot, errors = _load_errors(path, payload)
    if errors:
        return errors
    try:
        schema = _schema()
    except OSError:
        # Sınır: şema yolu göreli (`SCHEMA_PATH`); komut depo kökünden koşar.
        return [f"{SCHEMA_PATH}: okunamadı — komut depo kökünden koşulur"]
    try:
        return snapshot_errors(snapshot, schema)
    except (ValueError, RecursionError) as error:  # kural kollarının öngörmediği girdi: kapalı kal
        return [f"{path.name}: denetlenemedi ({type(error).__name__})"]


def _sha256_errors(sha256_file: Path, payload: bytes | None) -> list[str]:
    raw, errors = _read(sha256_file)
    if raw is None:
        return errors
    recorded = raw.decode("utf-8", errors="replace").split()
    if payload is None or not recorded or recorded[0] != hashlib.sha256(payload).hexdigest():
        return [f"{sha256_file.name}: dosya baytlarının sha256'sı değil"]
    return []


def _verify(path: Path, sha256_file: Path | None) -> int:
    payload, errors = _read(path)
    if payload is not None:
        errors = _content_errors(path, payload)
    if sha256_file is not None:
        errors.extend(_sha256_errors(sha256_file, payload))
    for text in errors:
        sys.stdout.write(f"ANLIK GÖRÜNTÜ İHLALİ: {text}\n")
    if errors:
        return EXIT_SITE_INVALID
    sys.stdout.write(f"anlık görüntü geçerli: {path.name}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m football_edge.site")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="DB → snapshot.json + snapshot.sha256")
    export.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify-snapshot", help="anlık görüntünün DB'siz denetimi")
    verify.add_argument("path", type=Path)
    verify.add_argument("--sha256", type=Path, default=None)
    commands.add_parser("derive-stdin", help="İÇ: dışa aktarımın ikinci türetimi")
    args = parser.parse_args(argv)
    if args.command == "derive-stdin":
        return _derive_stdin()
    configure_logging()
    if args.command == "export":
        return _export(args.out)
    return _verify(args.path, args.sha256)


if __name__ == "__main__":
    raise SystemExit(main())
