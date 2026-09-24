"""`verify-snapshot`: anlık görüntünün DB'siz denetimi (Faz 6 İz B tasarımı §5.1, H1–H5).

Hata metinleri JSON yolunu ve kuralı adlandırır, DEĞERİ basmaz: log public'tir ve reddedilen değer
tam da sızmaması gereken şey olabilir (ör. bir DSN).
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from football_edge.site.contract import (
    FORBIDDEN_KEYS,
    PATH_ID_LENGTH,
    PUBLIC_FLOOR,
    RESERVED_LEAGUE_SLUGS,
    RESERVED_TEAM_SLUGS,
    SITE_MIN_TEAM_MATCHES,
    content_sha256,
    iso_z,
)
from football_edge.site.schema import validate
from football_edge.site.slugs import match_slug, slugify

_DATE = re.compile(r"(?<![0-9])([0-9]{4})-([0-9]{2})-([0-9]{2})(?![0-9])")
_MARKUP = ("http", "<", ">")  # H2c: bağlantı ve işaretleme taşıyan veri dizesi yok
_SECRETS = ("postgres://", "postgresql://", "service_role", "supabase_", "netlify_auth")
_JWT = "eyJ"  # JWT öneki; büyük/küçük harf duyarlı
_ONE_DECIMAL = ("p", "move", "move_distribution")
_TWO_DECIMALS = ("clv", "mean_clv", "ci_low", "ci_high", "published_price", "closing_fair_price")


def snapshot_errors(snapshot: object, schema: Mapping[str, Any]) -> list[str]:
    """Bütün kuralların ihlalleri; boş liste = yayımlanabilir.

    Metin taramaları (H1 tarih, H2, H5, yasak anahtarlar) şekilden bağımsızdır ve HER ZAMAN koşar;
    şekle dayanan kontroller yalnız şema geçerse koşar.
    """
    found = [*validate(snapshot, schema), *_date_errors(snapshot), *_text_errors(snapshot, "$")]
    if found or not isinstance(snapshot, dict):
        return found
    return [
        *_order_errors(snapshot),
        *_floor_errors(snapshot),
        *_precision_errors(snapshot, "$"),
        *_consistency_errors(snapshot),
        *_ledger_errors(snapshot["ledger"]),
        *_hash_errors(snapshot),
    ]


def _strictly_increasing(items: Sequence[Any], key: Any, name: str) -> Iterator[str]:
    keys = [key(item) for item in items]
    for index in range(1, len(keys)):
        if not keys[index - 1] < keys[index]:
            yield f"$.{name}[{index}]: sıra bozuk ya da tekrar (tanımlı anahtar)"


def _order_errors(snapshot: dict[str, Any]) -> Iterator[str]:
    yield from _strictly_increasing(snapshot["leagues"], lambda item: item["id"], "leagues")
    yield from _strictly_increasing(
        snapshot["teams"], lambda item: (item["league_id"], item["slug"]), "teams"
    )
    yield from _strictly_increasing(
        snapshot["matches"], lambda item: (item["commence_time"], item["id"]), "matches"
    )
    yield from _strictly_increasing(
        snapshot["record"]["entries"], lambda item: item["publication_id"], "record.entries"
    )


def _floor_errors(snapshot: dict[str, Any]) -> Iterator[str]:
    floor_text = iso_z(PUBLIC_FLOOR)
    for index, match in enumerate(snapshot["matches"]):
        if match["commence_time"] < floor_text:
            yield f"$.matches[{index}].commence_time: holdout tabanından eski (H1)"


def _date_errors(snapshot: object) -> Iterator[str]:
    """H1e: tabandan eski HİÇBİR tarih — alan adından bağımsız, her dizede."""
    floor_day = iso_z(PUBLIC_FLOOR)[:10]
    for path, text in _strings(snapshot, "$"):
        for found in _DATE.finditer(text):
            if "-".join(found.groups()) < floor_day:
                yield f"{path}: holdout tabanından eski tarih (H1)"


def _strings(node: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _strings(value, f"{path}[{index}]")


def _text_errors(node: Any, path: str) -> Iterator[str]:
    """H2c, H5b ve §4.3'ün yasak anahtarları; anahtar adları da taranır."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_KEYS:
                yield f"{path}.{key}: yayımlanmayan anahtar (§4.3)"
            yield from _secret_errors(key, f"{path}.{key} (anahtar)")
            yield from _text_errors(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _text_errors(value, f"{path}[{index}]")
    elif isinstance(node, str):
        lowered = node.lower()
        for mark in _MARKUP:
            if mark in lowered:
                yield f"{path}: bağlantı ya da işaretleme ({mark!r}) taşıyor (H2)"
        yield from _secret_errors(node, path)


def _secret_errors(text: str, path: str) -> Iterator[str]:
    lowered = text.lower()
    for mark in _SECRETS:
        if mark in lowered:
            yield f"{path}: kimlik bilgisi kalıbı ({mark!r}) taşıyor (H5)"
    if _JWT in text:
        yield f"{path}: JWT öneki taşıyor (H5)"


def _precision_errors(node: Any, path: str, digits: int | None = None) -> Iterator[str]:
    """§5.4: sayılar görüntü hassasiyetinde taşınır; TS yuvarlamaz."""
    if isinstance(node, dict):
        for key, value in node.items():
            inner = 1 if key in _ONE_DECIMAL else 2 if key in _TWO_DECIMALS else digits
            yield from _precision_errors(value, f"{path}.{key}", inner)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _precision_errors(value, f"{path}[{index}]", digits)
    elif isinstance(node, float) and digits is not None and round(node, digits) != node:
        yield f"{path}: {digits} ondalıktan fazla hassasiyet (§5.4)"


def _consistency_errors(snapshot: dict[str, Any]) -> Iterator[str]:
    leagues = {league["id"]: league for league in snapshot["leagues"]}
    matches = snapshot["matches"]
    league_slugs = [league["slug"] for league in snapshot["leagues"]]
    if len(set(league_slugs)) != len(league_slugs):
        yield "$.leagues: slug tekrarı"
    for index, league in enumerate(snapshot["leagues"]):
        # Lig slug'ı yapılandırmadandır (addan türemez); biçimi şema, burası ayrılmış adı sınar.
        if league["slug"] in RESERVED_LEAGUE_SLUGS:
            yield f"$.leagues[{index}].slug: ayrılmış bölüt (§8.1)"
        own = sum(1 for match in matches if match["league_id"] == league["id"])
        if league["matches"] != own:
            yield f"$.leagues[{index}].matches: maç listesiyle uyuşmuyor"
    yield from _team_errors(snapshot, leagues)
    yield from _match_errors(matches, leagues)
    yield from _record_errors(snapshot["record"])


def _team_errors(snapshot: dict[str, Any], leagues: Mapping[str, Any]) -> Iterator[str]:
    names: dict[tuple[str, str], int] = {}
    for match in snapshot["matches"]:
        for name in (match["home"], match["away"]):
            key = (match["league_id"], name)
            names[key] = names.get(key, 0) + 1
    listed = {(team["league_id"], team["name"]) for team in snapshot["teams"]}
    if listed != set(names):
        yield "$.teams: maçlardaki takım kümesiyle uyuşmuyor"
    for index, team in enumerate(snapshot["teams"]):
        at = f"$.teams[{index}]"
        if team["league_id"] not in leagues:
            yield f"{at}.league_id: bilinmeyen lig"
        if team["slug"] != slugify(team["name"]) or team["slug"] in RESERVED_TEAM_SLUGS:
            yield f"{at}.slug: addan türemiyor ya da ayrılmış (§8.1)"
        if team["matches"] != names.get((team["league_id"], team["name"]), 0):
            yield f"{at}.matches: maç listesiyle uyuşmuyor"
        if team["indexable"] != (team["matches"] >= SITE_MIN_TEAM_MATCHES):
            yield f"{at}.indexable: eşikle uyuşmuyor (§8.4)"


def _match_errors(matches: Sequence[Any], leagues: Mapping[str, Any]) -> Iterator[str]:
    path_ids: set[str] = set()
    for index, match in enumerate(matches):
        at = f"$.matches[{index}]"
        if match["league_id"] not in leagues:
            yield f"{at}.league_id: bilinmeyen lig"
        if match["path_id"] != match["id"][:PATH_ID_LENGTH] or match["path_id"] in path_ids:
            yield f"{at}.path_id: kimliğin öneki değil ya da çakışıyor (§8.1)"
        path_ids.add(match["path_id"])
        if match["slug"] != match_slug(match["home"], match["away"]):
            yield f"{at}.slug: takım adlarından türemiyor"
        if match["date"] != match["commence_time"][:10]:
            yield f"{at}.date: başlama anının UTC günü değil"
        if match["rounds"] < 1:
            yield f"{at}.rounds: kesimde satırı olmayan maç"
        if not match["sealed"] and match["h2h"]["closing"] is not None:
            yield f"{at}.h2h.closing: mühürsüz maçta kapanış"


def _record_errors(record: dict[str, Any]) -> Iterator[str]:
    if record["published"] != len(record["entries"]):
        yield "$.record.published: girdi sayısıyla uyuşmuyor"
    summary = record["summary"]
    if (summary is None) != (record["published"] == 0):
        yield "$.record.summary: yalnız boş sicilde null olur"
    if summary is not None and summary["n"] != record["published"]:
        yield "$.record.summary.n: yayın sayısıyla uyuşmuyor"


def _ledger_errors(ledger: dict[str, Any]) -> Iterator[str]:
    anchor = ledger["anchor"]
    if not ledger["rows"] <= ledger["last_id"]:
        yield "$.ledger: satır sayısı son kimliği aşıyor"
    if anchor["rows"] > ledger["rows"] or anchor["last_id"] > ledger["last_id"]:
        yield "$.ledger.anchor: çıpa kesimden ileride"


def _hash_errors(snapshot: dict[str, Any]) -> Iterator[str]:
    if content_sha256(snapshot) != snapshot["content_sha256"]:
        yield "$.content_sha256: gövdenin yeniden hesaplanan hash'iyle uyuşmuyor"
