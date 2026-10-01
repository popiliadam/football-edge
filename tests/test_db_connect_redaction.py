"""Bozuk DSN'de `db.connect` parolayı yankılamaz (DEFERRED 18g b).

libpq ayrıştırma hatası DSN'in parçasını tırnak içinde geri basar (`invalid percent-encoded token:
"<parola>%zz"`, `missing "=" after "<parola>"`, `invalid connection option "<parola>_…"`).
Ayrıştırmayı GEÇEN iki biçim de bağlanırken basar: parolada kodlanmamış `@` hostu `<parola>@…`
yapar (`failed to resolve host '<parola>@…'`), port yerine düşen parola `invalid integer value
"<parola>"` olur. Zamanlanmış işlerin logları herkese açıktır ve GitHub yalnız secret'ın TAMAMINI
maskeler; kök logger'ın redaksiyonu da parolayı libpq'dan aldığı için bu biçimlerde parolayı
bilemez. DSN bağlanmadan önce ayrıştırılıp host/port doğrulanır; hata metinsiz yükselir, zincir
(`__cause__`/`__context__`) boştur.

Ağ yok: süreç içinde bağlanma üreteci ve `socket.getaddrinfo` bekçiyle değiştirilir (ön koşul
testinde `psycopg.connect` de); alt süreçlere aynı bekçi `sitecustomize` ile girer. Geçerli
biçimli DSN'le bağlanılmaz — geçerli biçimler yalnız doğrulamadan geçip sahte `psycopg.connect`e
ulaştıklarıyla ölçülür.
"""

from __future__ import annotations

import socket
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
    pytest.param(f"postgresql://kullanici:ab@{PASSWORD}@{HOST}:5432/db", id="parolada-at"),
    pytest.param(f"host=127.0.0.1 port={PASSWORD}", id="port-parola"),
    pytest.param(f"postgresql://127.0.0.1:{PASSWORD}/db", id="url-port-parola"),
    pytest.param(f"host={HOST} hostaddr={PASSWORD}", id="hostaddr-parola"),
]
# libpq'nun ayrıştırıcısından ve host/port doğrulamasından geçer; psycopg'nin kendi denetimi
# (`bad value for connect_timeout: '<parola>'`) bağlanma ve ad çözmeden önce düşürür.
REJECTED_BY_PSYCOPG = [
    pytest.param(f"host={HOST} connect_timeout={PASSWORD}", id="zaman-asimi-parola"),
]
EVERY_MALFORMED = MALFORMED + REJECTED_BY_PSYCOPG

WELL_FORMED = [
    pytest.param("postgresql://u:p%40ss@aws-0-eu.pooler.supabase.com:5432/postgres", id="url"),
    pytest.param("postgresql://u@h1.example.com:5432,h2.example.com:5433/db", id="coklu-host"),
    pytest.param("host=/var/run/postgresql dbname=db", id="unix-soket"),
    pytest.param("postgresql:///db?host=/tmp", id="url-unix-soket"),
    pytest.param("postgresql://u@[::1]:5432/db", id="ipv6-url"),
    pytest.param("host=fe80::1%en0 port=5432", id="ipv6-zone"),
    pytest.param("host=db_svc hostaddr=10.0.0.1,10.0.0.2 port=6543,6544", id="hostaddr"),
    pytest.param("dbname=db", id="host-yok"),
]

# Alt süreç bekçisi: ad çözme ve bağlanma denenirse düşer (ağa hiçbir paket çıkmaz).
GUARD = """\
import socket


def _no_dns(*_args, **_kwargs):
    raise socket.gaierror(socket.EAI_NONAME, "test bekçisi: ad çözme yok")


socket.getaddrinfo = _no_dns
import psycopg  # noqa: E402


def _no_connect(*_args, **_kwargs):
    raise AssertionError("test bekçisi: bağlanma denendi")


psycopg.Connection._connect_gen = classmethod(_no_connect)
"""


def _no_network(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("bozuk DSN doğrulamada düşmeliydi; bağlanma ya da ad çözme denendi")


@pytest.fixture(autouse=True)
def _guard_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(psycopg.Connection, "_connect_gen", _no_network)
    monkeypatch.setattr(socket, "getaddrinfo", _no_network)


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
def test_a_malformed_dsn_is_rejected_before_psycopg_is_called(
    dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ön koşul: bu biçimler `psycopg.connect`e (ve dolayısıyla ad çözmeye) hiç ulaşmaz.
    monkeypatch.setattr(psycopg, "connect", _no_network)

    with pytest.raises(psycopg.ProgrammingError, match="ayrıştırılamadı") as caught:
        connect(dsn)

    _assert_silent(caught.value)


def test_a_psycopg_programming_error_after_validation_is_silent_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def echo(conninfo: str, **_kwargs: Any) -> Any:
        raise psycopg.ProgrammingError(f"bad value for connect_timeout: {PASSWORD!r}")

    monkeypatch.setattr(psycopg, "connect", echo)

    with pytest.raises(psycopg.ProgrammingError, match="ayrıştırılamadı") as caught:
        connect(f"host={HOST} dbname=db")

    _assert_silent(caught.value)


@pytest.mark.parametrize("dsn", EVERY_MALFORMED)
def test_a_malformed_dsn_raises_without_echoing_the_password(dsn: str) -> None:
    with pytest.raises(psycopg.ProgrammingError, match="ayrıştırılamadı") as caught:
        connect(dsn)

    _assert_silent(caught.value)


@pytest.mark.parametrize("dsn", EVERY_MALFORMED)
def test_a_malformed_database_url_from_the_environment_is_silent_too(
    dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DSN_VAR, dsn)

    with pytest.raises(psycopg.ProgrammingError, match="ayrıştırılamadı") as caught:
        connect()

    _assert_silent(caught.value)


def test_a_dsn_that_cannot_be_encoded_is_silent_too() -> None:
    # Vekil karakter libpq'ya kodlanamaz: `UnicodeEncodeError`ın `repr`i (args) DSN'i taşır.
    with pytest.raises(psycopg.ProgrammingError, match="ayrıştırılamadı") as caught:
        connect(f"host={HOST} password={PASSWORD}\udcff")

    _assert_silent(caught.value)


@pytest.mark.parametrize("dsn", WELL_FORMED)
def test_a_well_formed_dsn_passes_validation_and_reaches_psycopg(
    dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Bağlanılmaz: `psycopg.connect` sahte; yalnız doğrulamanın geçerli biçimi reddetmediği ölçülür.
    calls: list[tuple[str, dict[str, Any]]] = []
    sentinel: Any = object()

    def record(conninfo: str, **kwargs: Any) -> Any:
        calls.append((conninfo, kwargs))
        return sentinel

    monkeypatch.setattr(psycopg, "connect", record)

    assert connect(dsn) is sentinel
    assert calls == [(dsn, {"options": "-c timezone=UTC"})]


def _subprocess_env(dsn: str, guard_dir: Path) -> dict[str, str]:
    guard_dir.mkdir(exist_ok=True)
    (guard_dir / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
    pythonpath = f"{guard_dir}:{REPO / 'src'}"
    return {"PYTHONPATH": pythonpath, "PATH": "/usr/bin:/bin", DSN_VAR: dsn}


@pytest.mark.parametrize("dsn", EVERY_MALFORMED)
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
    env = {**_subprocess_env(dsn, tmp_path / "bekci"), TEST_DSN_VAR: dsn}
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


@pytest.mark.parametrize("dsn", EVERY_MALFORMED)
def test_a_cli_with_a_malformed_database_url_exits_red_without_the_password(
    dsn: str, tmp_path: Path
) -> None:
    # `verify-chain` bağlantıyı yakalamaz: yakalanmamış istisna excepthook'tan geçer, exit 1.
    result = subprocess.run(
        [sys.executable, "-m", "football_edge.collect", "verify-chain"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=_subprocess_env(dsn, tmp_path / "bekci"),
        check=False,
        timeout=120,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0 and "ProgrammingError" in output, output
    assert PASSWORD not in output
