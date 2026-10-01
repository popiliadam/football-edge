"""Bozuk DSN'de `db.connect` parolayı yankılamaz (DEFERRED 18g b).

libpq ve psycopg bozuk DSN'i reddederken değeri tırnak içinde basar: ayrıştırma (`invalid
percent-encoded token: "<parola>%zz"`), ad çözme (parolada kodlanmamış `@`: `failed to resolve host
'<parola>@…'`), seçenek değeri (boş kalan `sslmode=` ardından gelen `password=…`yu yutar: `invalid
sslmode value: "password=<parola>"`). Zamanlanmış işlerin logları herkese açıktır; GitHub yalnız
secret'ın TAMAMINI maskeler, kök logger'ın redaksiyonu da bu biçimlerde parolayı bilemez.

İki katman (`football_edge.dsn_hygiene`): (A) bağlanmadan önce biçim denetimi, (B) bağlanırken
yükselen psycopg hatasında DSN'den gelen tırnaklı parçaların maskelenmesi. Testler her sızıntı
biçimini dört yüzeyde ölçer (istisna zinciri, ortamdan DSN, alt süreçte `pytest --tb=short`, alt
süreçte `collect seal`/`verify-chain`); ön koşul testi (A)'yı, maskeleme testleri (B)'yi ayrı ölçer.

Ağ yok: ad çözme süreç içinde ve alt süreçte (`sitecustomize`) bekçiyle düşer — DNS paketi çıkmaz.
Hostlar `.invalid` (çözülmez), var olmayan bir unix soket dizini ya da loopback `127.0.0.1:1`dir;
gerçek bir hosta biçimce geçerli bir DSN'le bağlanılmaz. Geçerli biçimler yalnız doğrulamadan geçip
sahte `psycopg.connect`e ulaştıklarıyla ölçülür.
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

from football_edge import db as db_module
from football_edge.db import connect
from football_edge.dsn_hygiene import MASK, masked

REPO = Path(__file__).resolve().parent.parent
DSN_VAR = "DATABASE" + "_URL"
TEST_DSN_VAR = "FE_T2_BOZUK" + "_DSN"
PASSWORD = "SahteParola" + "T2x9"  # parçadan kurulur: secret taraması `AD=değer` arar
HOST = "ornek.invalid"  # RFC 2606: hiçbir zaman çözülmez
SOCKET_DIR = "/fe-t2-yok-dizin"  # var olmayan unix soket dizini: TCP yok
LOOPBACK = "hostaddr=127.0.0.1 port=1"  # TCP'ye özgü seçenekler için; dinleyen yok
URL = "postgresql://kullanici"

ENUM_OPTIONS = (
    "sslmode",
    "gssencmode",
    "channel_binding",
    "target_session_attrs",
    "load_balance_hosts",
    "sslnegotiation",
    "sslcertmode",
    "ssl_min_protocol_version",
    "ssl_max_protocol_version",
    "min_protocol_version",
    "max_protocol_version",
)
TCP_INTEGER_OPTIONS = (
    "keepalives",
    "keepalives_idle",
    "keepalives_interval",
    "keepalives_count",
    "tcp_user_timeout",
)

# (A)'nın bağlanmadan önce düşürdüğü, (B) olmadan parolayı yankılayan biçimler.
MALFORMED = [
    # libpq ayrıştırma hataları
    pytest.param(f"{URL}:{PASSWORD}%zz@{HOST}/db", id="yuzde-kodlamasi"),
    pytest.param(f"host={HOST} {PASSWORD}", id="esittir-eksik"),
    pytest.param(f"host={HOST} {PASSWORD}_ayar=1", id="bilinmeyen-secenek"),
    # parolada kodlanmamış '@' (tur 1 C1, tur 2 C2)
    pytest.param(f"{URL}:ab@{PASSWORD}@{HOST}:5432/db", id="parolada-at"),
    pytest.param(f"{URL}:ab@{PASSWORD}/x@{HOST}:5432/db", id="at-slash"),
    pytest.param(f"{URL}:ab@{PASSWORD}:5432/x@{HOST}:5432/db", id="at-port-slash"),
    pytest.param(f"{URL}:ab@{PASSWORD}.x/y@{HOST}:5432/db", id="at-nokta-slash"),
    pytest.param(f"{URL}:{PASSWORD}@{PASSWORD}x/y@{HOST}:5432/db", id="parola-at-parola"),
    # host/hostaddr/port girdileri (her girdi, yalnız ilki değil: m5)
    pytest.param(f"host=127.0.0.1 port={PASSWORD}", id="port-parola"),
    pytest.param(f"postgresql://127.0.0.1:{PASSWORD}/db", id="url-port-parola"),
    pytest.param(f"host={HOST} hostaddr={PASSWORD}", id="hostaddr-parola"),
    pytest.param(f"host={HOST},ab@{PASSWORD}", id="ikinci-host-at"),
    pytest.param(f"host=127.0.0.1,127.0.0.1 port=1,{PASSWORD}", id="ikinci-port-parola"),
    # seçenek değerleri (tur 2 I3): boş slot, servis, değer kümeleri, tamsayılar
    pytest.param(f"host={SOCKET_DIR} sslmode= password={PASSWORD}", id="bos-slot-sslmode"),
    pytest.param(f"host={SOCKET_DIR} service={PASSWORD}", id="service"),
    pytest.param(f"host={SOCKET_DIR} require_auth={PASSWORD}", id="require_auth"),
    pytest.param(f"host={SOCKET_DIR} require_auth=!{PASSWORD}", id="require_auth-olumsuz"),
    *(pytest.param(f"host={SOCKET_DIR} {key}={PASSWORD}", id=key) for key in ENUM_OPTIONS),
    *(pytest.param(f"{LOOPBACK} {key}={PASSWORD}", id=key) for key in TCP_INTEGER_OPTIONS),
    pytest.param(f"host={HOST} connect_timeout={PASSWORD}", id="connect_timeout"),
    # C2'nin `postgres://` öneki (tur 3 m8)
    pytest.param(f"postgres://kullanici:ab@{PASSWORD}/x@{HOST}:5432/db", id="postgres-at-slash"),
    # yankılanan değerde tırnak ya da anahtar=değer kaçışı (tur 3 I4; inceleyicinin 12 + 4 biçimi)
    pytest.param(f'host={SOCKET_DIR} sslmode= password=ab"{PASSWORD}', id="bos-slot-cift-tirnak"),
    pytest.param(f"host={SOCKET_DIR} sslmode= password=ab'{PASSWORD}", id="bos-slot-tek-tirnak"),
    pytest.param(f"host={SOCKET_DIR} sslmode= password=ab\\'{PASSWORD}", id="bos-slot-ters-bolu"),
    pytest.param(f"host={SOCKET_DIR} sslmode= password=a\\b{PASSWORD}", id="bos-slot-ters-bolu-2"),
    pytest.param(f"host={SOCKET_DIR} sslmode='x\\'{PASSWORD}'", id="tirnakli-deger-kacis"),
    pytest.param(f"postgresql:///db?host={SOCKET_DIR}&sslmode=%22{PASSWORD}", id="sorgu-cift"),
    pytest.param(f"postgresql:///db?host={SOCKET_DIR}&sslmode=%27{PASSWORD}", id="sorgu-tek"),
    pytest.param(f"postgresql:///db?host={SOCKET_DIR}&sslmode=ab%22{PASSWORD}", id="sorgu-ortada"),
    pytest.param(f'host={SOCKET_DIR} target_session_attrs=x"{PASSWORD}', id="target-cift-tirnak"),
    pytest.param(f"host={SOCKET_DIR} connect_timeout=x'{PASSWORD}", id="timeout-tek-tirnak"),
    pytest.param(f'host={SOCKET_DIR} service=x"{PASSWORD}', id="service-cift-tirnak"),
    pytest.param(f'{URL}:ab"{PASSWORD}%zz@{HOST}/db', id="yuzde-cift-tirnak"),
    pytest.param(f"{URL}:ab'{PASSWORD}%zz@{HOST}/db", id="yuzde-tek-tirnak"),
    pytest.param(f'host={SOCKET_DIR} password=ab"{PASSWORD} foo', id="esitsiz-cift-tirnak"),
    # psycopg'nin `repr` ile yankıladığı değer (tur 4 I5): `bad value for connect_timeout: {!r}`,
    # `failed to resolve host {!r}`, çoklu deneme listesi `host: %r` (girdi başına). `repr` ters
    # bölüyü ikiler, iki tırnak türünde `\'` yazar, basılamayanı `\xNN` yazar.
    pytest.param(
        f"postgresql:///db?host={SOCKET_DIR}&connect_timeout=ab%5C{PASSWORD}",
        id="repr-timeout-ters-bolu",
    ),
    pytest.param(
        f"host={SOCKET_DIR} connect_timeout= password={PASSWORD}'x\"", id="repr-timeout-iki-tirnak"
    ),
    pytest.param(
        f"host={SOCKET_DIR} connect_timeout='{PASSWORD}\\'x\"'", id="repr-timeout-tirnakli"
    ),
    pytest.param(
        f"postgresql:///db?host={SOCKET_DIR}&connect_timeout={PASSWORD}%01",
        id="repr-timeout-basilamayan",
    ),
    pytest.param(
        f"host={SOCKET_DIR} connect_timeout= password=ab\\\\{PASSWORD}",
        id="repr-timeout-cift-ters-bolu",
    ),
    pytest.param(f"{URL}@ab%5C{PASSWORD}/db", id="repr-host-ters-bolu"),
    pytest.param(f"{URL}@{PASSWORD}%27x%22/db", id="repr-host-iki-tirnak"),
    pytest.param(
        f"{URL}@ab%5C{PASSWORD}:1,ab%5C{PASSWORD}:1/db"
        "?hostaddr=127.0.0.1,127.0.0.1&connect_timeout=3",
        id="repr-coklu-deneme-listesi",
    ),
    # libpq yüzde-kodlu ANAHTARI çözüp yankılar, ayrıştırma düşer (tur 4 m9: `unquote` kaynağı)
    pytest.param(f"postgresql:///db?x%2D{PASSWORD}=1", id="yuzde-kodlu-anahtar"),
]

WELL_FORMED = [
    pytest.param("postgresql://u:p%40ss@aws-0-eu.pooler.supabase.com:5432/postgres", id="url"),
    pytest.param("postgresql://u@h1.example.com:5432,h2.example.com:5433/db", id="coklu-host"),
    pytest.param("host=/var/run/postgresql dbname=db", id="unix-soket"),
    pytest.param("postgresql:///db?host=/tmp", id="url-unix-soket"),
    pytest.param("postgresql://u@[::1]:5432/db", id="ipv6-url"),
    pytest.param("host=fe80::1%en0 port=5432", id="ipv6-zone"),
    pytest.param("host=db_svc hostaddr=10.0.0.1,10.0.0.2 port=6543,6544", id="hostaddr"),
    pytest.param("dbname=db", id="host-yok"),
    pytest.param(
        "postgresql://u:p@aws-0-eu.pooler.supabase.com:5432/postgres?sslmode=require",
        id="url-sslmode",
    ),
    pytest.param(
        "host=db.example.com sslmode=verify-full sslrootcert=/x/ca.pem keepalives=1 "
        "keepalives_idle=30",
        id="verify-full-keepalives",
    ),
    pytest.param(
        "host=h1,h2 target_session_attrs=read-write load_balance_hosts=random", id="hedef-oturum"
    ),
    pytest.param(
        "host=h require_auth=scram-sha-256 channel_binding=require gssencmode=disable",
        id="require-auth",
    ),
    pytest.param(
        "host=h require_auth=!password,!md5 sslnegotiation=direct sslmode=require",
        id="require-auth-olumsuz",
    ),
    pytest.param(
        "host=h ssl_min_protocol_version=TLSv1.2 min_protocol_version=3.0 "
        "max_protocol_version=latest",
        id="protokol",
    ),
    pytest.param(
        "host=h tcp_user_timeout=0 keepalives_count=3 keepalives_interval=10 sslcertmode=allow",
        id="tamsayilar",
    ),
    pytest.param("host=h ssl_max_protocol_version=tlsv1.3 connect_timeout=10", id="tls-kucuk"),
    # libpq/psycopg'nin kabul ettiği tamsayı biçimleri (tur 3 m7; ölçüm t2-r3-int-probe.out)
    pytest.param("postgresql://u:p@h.example.com:5432\n", id="port-satir-sonu"),
    pytest.param("postgresql://u@h.example.com:5432%0A/db", id="url-port-kodlu-satir-sonu"),
    pytest.param("host=h port=' 5432 '", id="port-bosluk"),
    pytest.param("host=h port=+5432,05433", id="port-arti-sifir"),
    pytest.param("postgresql://u@h/db?connect_timeout=10%0A", id="timeout-satir-sonu"),
    pytest.param("host=h connect_timeout=+10", id="timeout-arti"),
    pytest.param("host=h connect_timeout=2.5", id="timeout-ondalik"),
    pytest.param("host=h keepalives_idle='\t30 ' tcp_user_timeout=-5", id="tamsayi-bosluk-eksi"),
]

# Alt süreç bekçisi: ad çözme düşer (DNS paketi çıkmaz). Bağlanma üreteci açık kalır: (A)
# kapatılırsa libpq'nun seçenek doğrulaması gerçekten koşmalı ki (B) ölçülebilsin; hostlar yerel.
GUARD = """\
import socket


def _no_dns(*_args, **_kwargs):
    raise socket.gaierror(socket.EAI_NONAME, "test bekçisi: ad çözme yok")


socket.getaddrinfo = _no_dns
"""


def _no_dns(*_args: Any, **_kwargs: Any) -> Any:
    raise socket.gaierror(socket.EAI_NONAME, "test bekçisi: ad çözme yok")


def _no_psycopg(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("bozuk DSN doğrulamada (A) düşmeliydi; psycopg.connect çağrıldı")


@pytest.fixture(autouse=True)
def _guard_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _no_dns)


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


# ── (A): bağlanmadan önce ─────────────────────────────────────────────────────────────────────


OUT_OF_RANGE = [
    pytest.param(f"host={HOST} port=99999", id="aralik"),
    pytest.param(f"{LOOPBACK} keepalives=2147483648", id="int32-disi"),
]


@pytest.mark.parametrize("dsn", [*MALFORMED, *OUT_OF_RANGE])
def test_layer_a_rejects_a_malformed_dsn_before_psycopg_is_called(
    dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(psycopg, "connect", _no_psycopg)

    with pytest.raises(psycopg.ProgrammingError, match="ayrıştırılamadı ya da bozuk") as caught:
        connect(dsn)

    _assert_silent(caught.value)


def test_layer_a_rejects_a_dsn_that_cannot_be_encoded(monkeypatch: pytest.MonkeyPatch) -> None:
    # Vekil karakter libpq'ya kodlanamaz: `UnicodeEncodeError`ın `repr`i (args) DSN'i taşır.
    monkeypatch.setattr(psycopg, "connect", _no_psycopg)

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


# ── (B): bağlanırken ──────────────────────────────────────────────────────────────────────────


def test_layer_b_masks_every_quoted_fragment_taken_from_the_dsn() -> None:
    dsn = f"host={HOST} port=1 password={PASSWORD} sslmode=require"
    message = (
        f'connection is bad: invalid integer value "{PASSWORD}" for connection option "port"; '
        f'host \'{HOST}\'; yüzde-çözülmüş "{PASSWORD}"; başka "x-sunucu"'
    )

    assert masked(message, dsn) == (
        f'connection is bad: invalid integer value "{MASK}" for connection option "{MASK}"; '
        f'host \'{MASK}\'; yüzde-çözülmüş "{MASK}"; başka "x-sunucu"'
    )
    assert masked(f'"{PASSWORD}@"', f"{URL}:{PASSWORD}%40@{HOST}/db") == f'"{MASK}"', "çözülmüş"


@pytest.mark.parametrize(
    ("dsn", "message"),
    [
        pytest.param(
            f'host=/x sslmode= password=ab"{PASSWORD}',
            f'invalid sslmode value: "password=ab"{PASSWORD}"',
            id="deger-icinde-cift-tirnak",
        ),
        pytest.param(
            f"host=/x sslmode= password=ab\\'{PASSWORD}",
            f'invalid sslmode value: "password=ab\'{PASSWORD}"',
            id="anahtar-deger-kacisi",
        ),
        pytest.param(
            f'{URL}:ab"{PASSWORD}%zz@{HOST}/db',
            f'invalid percent-encoded token: "ab"{PASSWORD}%zz"',
            id="ayristirilamayan-en-uzun-aralik",
        ),
    ],
)
def test_layer_b_masks_an_echo_that_carries_a_quote_or_an_escape(dsn: str, message: str) -> None:
    # libpq ayrıştırdığı değeri AYNEN yankılar (kaçış çözülmüş, iç tırnak dâhil): önce o değerler,
    # sonra DSN'in alt dizesi olan EN UZUN tırnaklı aralık maskelenir.
    assert PASSWORD not in masked(message, dsn)
    assert masked(message, dsn).endswith(f'"{MASK}"')


def _raising(error: psycopg.Error) -> Any:
    def fail(conninfo: str, **_kwargs: Any) -> Any:
        raise error

    return fail


@pytest.mark.parametrize(
    "kind", [psycopg.OperationalError, psycopg.ProgrammingError, psycopg.InterfaceError]
)
def test_layer_b_reraises_the_same_class_with_the_dsn_fragments_masked(
    kind: type[psycopg.Error], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Her `psycopg.Error` (yalnız `OperationalError` değil): ör. psycopg'nin `ProgrammingError`ı
    # (`bad value for connect_timeout`) ayrıştırmadan SONRA, bağlanmadan önce yükselir.
    dsn = f"host={HOST} password={PASSWORD} sslmode=require"
    original = kind(f'invalid sslmode value: "password={PASSWORD}"')
    monkeypatch.setattr(psycopg, "connect", _raising(original))

    with pytest.raises(kind) as caught:
        connect(dsn)

    assert type(caught.value) is kind
    assert str(caught.value) == f'invalid sslmode value: "{MASK}"'
    _assert_silent(caught.value)


@pytest.mark.parametrize("dsn", MALFORMED)
def test_layer_b_alone_keeps_every_malformed_dsn_silent(
    dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # (A) kapalı: libpq/psycopg gerçekten koşar (DNS bekçide; hostlar yerel ya da `.invalid`).
    monkeypatch.setattr(db_module, "dsn_well_formed", lambda _dsn: True)

    with pytest.raises(psycopg.Error) as caught:
        connect(dsn)

    _assert_silent(caught.value)


def test_layer_b_leaves_a_diagnostic_without_dsn_fragments_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = (
        "connection failed: Connection refused\n"
        '\tIs the server running on that host and accepting TCP/IP connections? ("başka-host")'
    )
    monkeypatch.setattr(psycopg, "connect", _raising(psycopg.errors.ConnectionTimeout(text)))

    with pytest.raises(psycopg.errors.ConnectionTimeout) as caught:
        connect(f"host={HOST} dbname=db")

    assert str(caught.value) == text
    assert caught.value.__cause__ is None and caught.value.__context__ is None


# ── dört yüzey: her sızıntı biçimi, (A) ya da (B) hangisi tutarsa ──────────────────────────────


@pytest.mark.parametrize("dsn", MALFORMED)
def test_a_malformed_dsn_raises_without_echoing_the_password(dsn: str) -> None:
    with pytest.raises(psycopg.Error) as caught:
        connect(dsn)

    _assert_silent(caught.value)


@pytest.mark.parametrize("dsn", MALFORMED)
def test_a_malformed_database_url_from_the_environment_is_silent_too(
    dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DSN_VAR, dsn)

    with pytest.raises(psycopg.Error) as caught:
        connect()

    _assert_silent(caught.value)


def _subprocess_env(dsn: str, guard_dir: Path) -> dict[str, str]:
    guard_dir.mkdir(exist_ok=True)
    (guard_dir / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
    pythonpath = f"{guard_dir}:{REPO / 'src'}"
    # Boş HOME: `~/.pgpass` ve servis dosyası okunmaz.
    home = guard_dir / "home"
    home.mkdir(exist_ok=True)
    return {"PYTHONPATH": pythonpath, "PATH": "/usr/bin:/bin", "HOME": str(home), DSN_VAR: dsn}


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
    assert result.returncode == 1 and "psycopg." in output, output
    assert PASSWORD not in output


@pytest.mark.parametrize("command", ["seal", "verify-chain"])
@pytest.mark.parametrize("dsn", MALFORMED)
def test_a_cli_with_a_malformed_database_url_exits_red_without_the_password(
    dsn: str, command: str, tmp_path: Path
) -> None:
    # Bu komutlar bağlantıyı yakalamaz: yakalanmamış istisna excepthook'tan geçer, exit 1.
    result = subprocess.run(
        [sys.executable, "-m", "football_edge.collect", command],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=_subprocess_env(dsn, tmp_path / "bekci"),
        check=False,
        timeout=120,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0 and "psycopg." in output, output
    assert PASSWORD not in output
