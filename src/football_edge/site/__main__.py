"""`python -m football_edge.site verify-snapshot` (Faz 6 İz B §5.1).

`verify-snapshot`: anlık görüntünün DB'siz denetimi; B-2 ve `site.yml` bu komutu çağırır. Dışa
aktarım (`export`) ve ikinci türetimin iç komutu (`derive-stdin`) Task 6'da eklenir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

from football_edge.collect import configure_logging
from football_edge.site.contract import EXIT_SITE_INVALID, SCHEMA_PATH
from football_edge.site.schema import check_schema
from football_edge.site.verify import snapshot_errors


def _schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    check_schema(schema)
    return schema


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
    verify = commands.add_parser("verify-snapshot", help="anlık görüntünün DB'siz denetimi")
    verify.add_argument("path", type=Path)
    verify.add_argument("--sha256", type=Path, default=None)
    args = parser.parse_args(argv)
    configure_logging()
    return _verify(args.path, args.sha256)


if __name__ == "__main__":
    raise SystemExit(main())
