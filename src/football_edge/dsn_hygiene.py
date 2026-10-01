"""Bağlantı dizesinin (DSN) hata yollarında yankılanmaması (DEFERRED 18g b).

libpq ve psycopg bozuk bir DSN'i reddederken değerin kendisini tırnak içinde basar: ayrıştırma
hatası (`invalid percent-encoded token: "<parola>%zz"`), ad çözme (`failed to resolve host
'<parola>@…'`), seçenek değeri (`invalid sslmode value: "password=<parola>"`). Zamanlanmış işlerin
logları herkese açıktır; GitHub yalnız secret'ın TAMAMINI maskeler ve kök logger'ın redaksiyonu
parolayı libpq'dan aldığı için bu biçimlerde onu bilemez. İki katman:

(A) `dsn_well_formed`: bağlanmadan ÖNCE dar, biçim düzeyinde denetim — ad çözme ve soket yok.
(B) `masked`: bağlanırken yükselen her psycopg hatasında, ham DSN'in alt dizesi olan her tırnaklı
    parça maskelenir. Tırnaksız tanı ("Connection refused") okunur kalır. (A) bir biçimi kaçırırsa
    (B) tırnaklı yankıyı yine yakalar; (B) bozulursa (A) bilinen biçimlerin hepsini zaten düşürür.
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
_PORT = re.compile(r"[0-9]{1,5}")
_INTEGER = re.compile(r"-?[0-9]{1,9}")
_QUOTED = re.compile(r"'([^']*)'|\"([^\"]*)\"")
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
        "connect_timeout",
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


def _port_ok(port: str) -> bool:
    return not port or (_PORT.fullmatch(port) is not None and 1 <= int(port) <= 65535)


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
    if key in _INTEGERS:
        return _INTEGER.fullmatch(value) is not None
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


def masked(message: str, dsn: str) -> str:
    """(B) Ham (ya da yüzde-çözülmüş) DSN'in alt dizesi olan her tırnaklı parça `MASK` olur.

    Tırnaksız tanı ("Connection refused", "timeout expired") olduğu gibi kalır. Ölçülen her libpq
    ve psycopg değer yankısı tırnaklıdır; tırnaksız bir yankı (B)'yi geçer ve (A)'ya kalır.
    """
    sources = (dsn, unquote(dsn))

    def hide(found: re.Match[str]) -> str:
        fragment = found.group(1) if found.group(1) is not None else found.group(2)
        if fragment and any(fragment in source for source in sources):
            return MASK
        return found.group(0)

    return _QUOTED.sub(hide, message)
