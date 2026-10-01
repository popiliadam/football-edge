"""Bağlantı dizesinin (DSN) hata yollarında yankılanmaması (DEFERRED 18g b).

libpq ve psycopg bozuk bir DSN'i reddederken değerin kendisini tırnak içinde basar: ayrıştırma
hatası (`invalid percent-encoded token: "<parola>%zz"`), ad çözme (`failed to resolve host
'<parola>@…'`), seçenek değeri (`invalid sslmode value: "password=<parola>"`). Zamanlanmış işlerin
logları herkese açıktır; GitHub yalnız secret'ın TAMAMINI maskeler ve kök logger'ın redaksiyonu
parolayı libpq'dan aldığı için bu biçimlerde onu bilemez. İki katman:

(A) `dsn_well_formed`: bağlanmadan ÖNCE dar, biçim düzeyinde denetim — ad çözme ve soket yok.
(B) `masked`: bağlanırken yükselen her psycopg hatasında libpq'nun ayrıştırdığı değerlerin ve ham
    DSN'in alt dizesi olan her tırnaklı yankı maskelenir; tırnaksız tanı okunur kalır. (A) bir
    biçimi kaçırırsa (B) tırnaklı yankıyı yine yakalar; (B) bozulursa (A) bilinen biçimleri düşürür.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Mapping
from urllib.parse import unquote

import psycopg
from psycopg.conninfo import conninfo_to_dict

MASK = "<gizli>"

_HOST_NAME = re.compile(r"[A-Za-z0-9_.-]+")
# libpq `parse_int_param`: `strtol` öncesi/sonrası ASCII boşluk ve işaret serbest, int32 aralığı
# (ölçüldü: t2-r3-int-probe.out — ` 1`, `1\n`, `+1`, `01` kabul; `1.0`, `0x1`, `１`, `1 1` red).
_LIBPQ_INTEGER = re.compile(r"[ \t\n\x0b\x0c\r]*[+-]?[0-9]+[ \t\n\x0b\x0c\r]*")
_INT32 = range(-(2**31), 2**31)
_PORTS = range(1, 65536)
_QUOTES = ("'", '"')
_URL_PREFIXES = ("postgresql://", "postgres://")

# libpq 18'in belgelenmiş değer kümeleri (ölçüldü: review-t2-r2/r3-enum-sets.out). Küme dışı değer
# libpq'da `invalid <seçenek> value: "<değer>"` ile yankılanır. Sürüm kayması güvenli tarafa düşer:
# yeni bir libpq değeri burada genel mesajla reddedilir, sızmaz.
# TLS sürümlerini libpq büyük/küçük harf duyarsız karşılaştırır (ölçüldü: `tlsv1.2` kabul).
_TLS_VERSIONS = frozenset({"tlsv1", "tlsv1.1", "tlsv1.2", "tlsv1.3"})
_PROTOCOL_VERSIONS = frozenset({"3.0", "3.2", "latest"})
_ENUMS: Mapping[str, frozenset[str]] = {
    "sslmode": frozenset({"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}),
    "gssencmode": frozenset({"disable", "prefer", "require"}),
    "channel_binding": frozenset({"disable", "prefer", "require"}),
    "target_session_attrs": frozenset(
        {"any", "read-write", "read-only", "primary", "standby", "prefer-standby"}
    ),
    "load_balance_hosts": frozenset({"disable", "random"}),
    "sslnegotiation": frozenset({"postgres", "direct"}),
    "sslcertmode": frozenset({"disable", "allow", "require"}),
    "min_protocol_version": _PROTOCOL_VERSIONS,
    "max_protocol_version": _PROTOCOL_VERSIONS,
}
_CASELESS_ENUMS: Mapping[str, frozenset[str]] = {
    "ssl_min_protocol_version": _TLS_VERSIONS,
    "ssl_max_protocol_version": _TLS_VERSIONS,
}
_AUTH_METHODS = frozenset({"password", "md5", "gss", "sspi", "scram-sha-256", "oauth", "none"})
_INTEGERS = frozenset(
    {
        "keepalives",
        "keepalives_idle",
        "keepalives_interval",
        "keepalives_count",
        "tcp_user_timeout",
    }
)


def _ip_ok(address: str) -> bool:
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return False
    return True


def _host_ok(host: str) -> bool:
    """Boş (varsayılan), `/` ile başlayan unix soket dizini, ad ya da IP; başka hiçbir şey."""
    if not host or host.startswith("/") or _HOST_NAME.fullmatch(host):
        return True
    return _ip_ok(host)


def _libpq_integer(value: str) -> int | None:
    """libpq'nun tamsayı olarak kabul ettiği değer (int32), değilse `None`."""
    if _LIBPQ_INTEGER.fullmatch(value) is None:
        return None
    number = int(value)
    return number if number in _INT32 else None


def _port_ok(port: str) -> bool:
    return not port or _libpq_integer(port) in _PORTS


def _psycopg_timeout_ok(value: str) -> bool:
    """`connect_timeout`u libpq değil psycopg okur: `int(float(değer))` (ör. `2.5` kabul)."""
    try:
        int(float(value))
    except (ValueError, OverflowError):
        return False
    return True


def _auth_ok(value: str) -> bool:
    return all(method.removeprefix("!") in _AUTH_METHODS for method in value.split(","))


def _option_ok(key: str, value: str) -> bool:
    """Değer kümesi/tamsayı denetimi; `service` her zaman red (tanımsız ad aynen yankılanır)."""
    if not value:
        return True
    if key == "service":
        return False  # projede servis dosyası yok: `definition of service "<değer>" not found`
    if key in _ENUMS:
        return value in _ENUMS[key]
    if key in _CASELESS_ENUMS:
        return value.lower() in _CASELESS_ENUMS[key]
    if key == "require_auth":
        return _auth_ok(value)
    if key == "connect_timeout":
        return _psycopg_timeout_ok(value)
    if key in _INTEGERS:
        return _libpq_integer(value) is not None
    return True


_ENTRY_CHECKS: Mapping[str, Callable[[str], bool]] = {
    "host": _host_ok,
    "hostaddr": lambda address: not address or _ip_ok(address),
    "port": _port_ok,
}


def dsn_well_formed(dsn: str) -> bool:
    """(A) DSN ayrışır; host/hostaddr/port girdilerinin HER BİRİ ve seçenek değerleri mümkündür.

    URL biçiminde tek gerçek `@` userinfo ayırıcısıdır (parolada `%40`); ikinci bir `@`, parolanın
    bir parçasını host'a ya da veritabanı adına taşır (`postgresql://u:ab@<parola>/x@h/db` →
    host `<parola>`). Bu yüzden URL'de birden fazla kodlanmamış `@` bozuk sayılır.
    """
    if dsn.startswith(_URL_PREFIXES) and dsn.count("@") > 1:
        return False
    try:
        params = conninfo_to_dict(dsn)
    except (psycopg.ProgrammingError, UnicodeError):  # vekil karakter: `repr`i DSN'i taşır
        return False
    for key, raw in params.items():
        value = "" if raw is None else str(raw)
        check = _ENTRY_CHECKS.get(key)
        if check is not None and not all(check(entry) for entry in value.split(",")):
            return False
        if not _option_ok(key, value):
            return False
    return True


def _parsed_values(dsn: str) -> list[str]:
    """libpq'nun ayrıştırdığı değerler, en uzundan; ayrıştırılamazsa boş (aralık kuralı kalır)."""
    try:
        params = conninfo_to_dict(dsn)
    except (psycopg.Error, UnicodeError):
        return []
    return sorted({str(value) for value in params.values() if value}, key=len, reverse=True)


def _span_end(message: str, start: int, sources: tuple[str, ...]) -> int | None:
    """`start`taki tırnağın, aradaki metni DSN'in alt dizesi yapan EN UZAK eşi; yoksa `None`."""
    quote = message[start]
    for end in range(len(message) - 1, start + 1, -1):
        if message[end] == quote and any(message[start + 1 : end] in src for src in sources):
            return end
    return None


def masked(message: str, dsn: str) -> str:
    """(B) DSN'den gelen her tırnaklı yankı `MASK` olur; tırnaklar kalır, tırnaksız tanı aynen.

    İki adım (tur 3 I4): (1) libpq ayrıştırdığı değeri AYNEN yankılar — anahtar=değer kaçışı
    çözülmüş, iç tırnak dâhil (`"password=ab"<parola>"`): `conninfo_to_dict` değerleri tırnaklı
    hâlleriyle maskelenir. (2) Kalan her tırnak, aradaki metni ham ya da yüzde-çözülmüş DSN'in alt
    dizesi yapan EN UZAK eşiyle maskelenir — ilk eş, değerin içindeki tırnakta keserdi.
    """
    text = message
    for value in _parsed_values(dsn):
        for quote in _QUOTES:
            text = text.replace(f"{quote}{value}{quote}", f"{quote}{MASK}{quote}")
    sources = (dsn, unquote(dsn))
    pieces: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        end = _span_end(text, index, sources) if char in _QUOTES else None
        if end is None:
            pieces.append(char)
            index += 1
        else:
            pieces.append(f"{char}{MASK}{char}")
            index = end + 1
    return "".join(pieces)
