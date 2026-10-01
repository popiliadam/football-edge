"""Bozuk DSN'de `db.connect` parolayı yankılamaz (DEFERRED 18g b).

libpq ayrıştırma hatası DSN'in parçasını tırnak içinde geri basar (`invalid percent-encoded token:
"<parola>%zz"`, `missing "=" after "<parola>"`, `invalid connection option "<parola>_…"`).
Zamanlanmış işlerin logları herkese açıktır ve GitHub yalnız secret'ın TAMAMINI maskeler; kök
logger'ın redaksiyonu da parolayı libpq'dan aldığı için ayrıştırılamayan `key=value` DSN'de
parolayı bilemez. Hata kaynağında metinsiz yeniden yükseltilir; zincir (`__cause__`/`__context__`)
de boştur.

Ağ yok: bozuk DSN bağlanma denemesinden ÖNCE düşer — süreç içi testlerde bağlanma üreteci bir
bekçiyle değiştirilir; denenirse test kırmızıdır. Geçerli biçimli DSN'le bağlanılmaz.
"""

from __future__ import annotations

import subprocess
import sys
import traceback
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from football_edge.db import connect

REPO = Path(__file__).resolve().parent.parent
DSN_VAR = "DATABASE" + "_URL"
TEST_DSN_VAR = "FE_T2_BOZUK" + "_DSN"
PASSWORD = "SahteParola" + "T2x9"  # parçadan kurulur: secret taraması `AD=değer` arar
HOST = "ornek.invalid"  # RFC 2606: hiçbir zaman çözülmez

MALFORMED = [
    pytest.param(f"postgresql://kullanici:{PASSWORD}%zz@{HOST}/db", id="yuzde-kodlamasi"),
    pytest.param(f"host={HOST} {PASSWORD}", id="esittir-eksik"),
    pytest.param(f"host={HOST} {PASSWORD}_ayar=1", id="bilinmeyen-secenek"),
]


def _no_network(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("bozuk DSN ayrıştırmada düşmeliydi; bağlanma denendi")


@pytest.fixture(autouse=True)
def _guard_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(psycopg.Connection, "_connect_gen", _no_network)


def _chain(error: BaseException) -> Iterator[BaseException]:
    seen: BaseException | None = error
    while seen is not None:
        yield seen
        seen = seen.__cause__ or seen.__context__


def _assert_silent(error: BaseException) -> None:
    for link in _chain(error):
        assert PASSWORD not in str(link), f"{type(link).__name__} metni parolayı taşıyor"
        assert PASSWORD not in repr(link), f"{type(link).__name__} repr'i parolayı taşıyor"
    assert error.__cause__ is None and error.__context__ is None, "zincir libpq metnini taşıyor"
    assert PASSWORD not in "".join(traceback.format_exception(error))


@pytest.mark.parametrize("dsn", MALFORMED)
def test_a_malformed_dsn_raises_without_echoing_the_password(dsn: str) -> None:
    with pytest.raises(psycopg.ProgrammingError, match="ayrıştırılamadı") as caught:
        connect(dsn)

    _assert_silent(caught.value)


@pytest.mark.parametrize("dsn", MALFORMED)
def test_a_malformed_database_url_from_the_environment_is_silent_too(
    dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DSN_VAR, dsn)

    with pytest.raises(psycopg.ProgrammingError, match="ayrıştırılamadı") as caught:
        connect()

    _assert_silent(caught.value)


def _subprocess_env(dsn: str) -> dict[str, str]:
    return {"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin", DSN_VAR: dsn}


@pytest.mark.parametrize("dsn", MALFORMED)
def test_the_short_pytest_traceback_does_not_print_the_password(dsn: str, tmp_path: Path) -> None:
    # Kaynak satırı DSN'i değişken adıyla taşır: `--tb=short` hata satırını ve kaynağı basar.
    # Boş `pytest.ini`: TMPDIR depo içindeyse üstteki `pyproject`in `pythonpath`ı devreye girmez.
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    probe = tmp_path / "test_bozuk_dsn.py"
    probe.write_text(
        "import os\n\nfrom football_edge.db import connect\n\n\n"
        f"def test_bozuk() -> None:\n    connect(os.environ[{TEST_DSN_VAR!r}])\n",
        encoding="utf-8",
    )
    env = {**_subprocess_env(dsn), TEST_DSN_VAR: dsn}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", str(probe)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
        timeout=120,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 1 and "ProgrammingError" in output, output
    assert PASSWORD not in output


@pytest.mark.parametrize("dsn", MALFORMED)
def test_a_cli_with_a_malformed_database_url_exits_red_without_the_password(
    dsn: str, tmp_path: Path
) -> None:
    # `verify-chain` bağlantıyı yakalamaz: yakalanmamış istisna excepthook'tan geçer, exit 1.
    result = subprocess.run(
        [sys.executable, "-m", "football_edge.collect", "verify-chain"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=_subprocess_env(dsn),
        check=False,
        timeout=120,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0 and "ProgrammingError" in output, output
    assert PASSWORD not in output
