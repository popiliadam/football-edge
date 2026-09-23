"""Haber gözlemleri → `news_items` (spec §4; R166, R172).

`news_items` kademe 1 ve 2'nin TEK okuma yoludur. `source_observations.observed_at` ajansspor için
bizim toplama anımız DEĞİL, yayıncının iddia ettiği `news:publication_date`dir
(`collectors/news.py:news_observation`). Bu yüzden canlı haberin `available_at`i Python'da
kurulmaz: INSERT anında VERİTABANI saatiyle `greatest(now(), published_at_claimed)` olur ve
`first_seen_at` (varsayılan `now()`) aynı anı taşır. Geç senkronlanan haber senkron anından,
ileri tarihli iddia iddiadan önce kullanılamaz. Yeniden gözlem ilk satırı değiştirmez.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any

import psycopg

from football_edge.collector import ContractViolation
from football_edge.features.types import (
    ARCHIVE_CLAIMED,
    AVAILABILITY_BASES,
    OBSERVED,
    StoredNews,
)

# Kaynak → haber dili. EN kaynağı (Plan 2, T2) buraya eklenir; dilsiz kaynak okunmaz.
NEWS_SOURCE_LANGS: Mapping[str, str] = MappingProxyType({"ajansspor": "tr"})
NEWS_KIND = "news"
# `sync-news`in varsayılan geriye bakışı: haber sitemap'i son iki günü taşır; pay bir haftadır.
SYNC_LOOKBACK = timedelta(days=7)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class NewsDraft:
    """Yazılmamış haber. Canlıda `available_at` YOKTUR: veritabanı saatiyle INSERT'te kurulur."""

    source_id: str
    lang: str
    title: str
    body: str | None
    url: str
    published_at_claimed: datetime | None
    availability_basis: str
    content_hash: str
    available_at: datetime | None = None  # yalnız ARCHIVE_CLAIMED: `archive_available_at`

    def __post_init__(self) -> None:
        if self.availability_basis not in AVAILABILITY_BASES:
            raise ValueError(f"{self.url}: bilinmeyen availability_basis {self.availability_basis}")
        if self.availability_basis == OBSERVED and self.available_at is not None:
            raise ValueError(f"{self.url}: canlı haberin available_at'ini veritabanı kurar")
        if self.availability_basis == ARCHIVE_CLAIMED and (
            self.available_at is None
            or self.published_at_claimed is None
            or self.available_at < self.published_at_claimed
        ):
            raise ValueError(f"{self.url}: arşiv haberi iddia + pay ister (available ≥ iddia)")


_SELECT_OBSERVATIONS = """
    SELECT source_id, observed_at, payload
    FROM source_observations
    WHERE entity_kind = %s AND source_id = ANY(%s) AND observed_at >= %s
    ORDER BY observed_at, id
"""

_NEWS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_id", "text"),
    ("lang", "text"),
    ("title", "text"),
    ("body", "text"),
    ("url", "text"),
    ("published_at_claimed", "timestamptz"),
    ("available_at", "timestamptz"),
    ("availability_basis", "text"),
    ("content_hash", "text"),
)
_NEWS_NAMES = ", ".join(name for name, _ in _NEWS_COLUMNS)
_NEWS_ARRAYS = ", ".join(f"%({name})s::{kind}[]" for name, kind in _NEWS_COLUMNS)

# `now()` işlem başlangıcıdır: `first_seen_at` varsayılanıyla AYNI an (0012 kısıtı: canlı satırda
# available_at ≥ first_seen_at ve ≥ published_at_claimed). `greatest` NULL iddiayı yok sayar.
# İlk yazılan kalır: aynı içerik yeniden gözlenince `available_at` ileri kaymaz.
INSERT_NEWS = f"""
    INSERT INTO news_items ({_NEWS_NAMES})
    SELECT source_id, lang, title, body, url, published_at_claimed,
           CASE WHEN availability_basis = '{OBSERVED}'
                THEN greatest(now(), published_at_claimed)
                ELSE available_at END,
           availability_basis, content_hash
    FROM unnest({_NEWS_ARRAYS}) AS t({_NEWS_NAMES})
    ON CONFLICT (source_id, content_hash) DO NOTHING
    RETURNING id
"""

_SELECT_NEWS = f"""
    SELECT id, {_NEWS_NAMES}, first_seen_at
    FROM news_items
    WHERE available_at >= %s
    ORDER BY available_at, id
"""


def news_hash(source_id: str, url: str, title: str, body: str | None) -> str:
    """İçerik kimliği: yayın zamanı HARİÇ — aynı haberin yeniden damgalanması yeni haber değil."""
    canonical = json.dumps(
        {"b": body, "s": source_id, "t": title, "u": url},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _text(payload: Mapping[str, Any], key: str, source_id: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{source_id}: haber payload'ında '{key}' yok")
    return value.strip()


def _claimed(value: object, source_id: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ContractViolation(f"{source_id}: observed_at saat dilimli bir an değil ({value!r})")
    return value


def _draft(row: Mapping[str, Any]) -> NewsDraft:
    source_id = str(row["source_id"])
    lang = NEWS_SOURCE_LANGS.get(source_id)
    if lang is None:
        raise ContractViolation(f"{source_id}: haber dili tanımlı değil (NEWS_SOURCE_LANGS)")
    payload = row["payload"]
    if not isinstance(payload, Mapping):
        raise ContractViolation(f"{source_id}: haber payload'ı bir nesne değil")
    title = _text(payload, "title", source_id)
    url = _text(payload, "url", source_id)
    return NewsDraft(
        source_id=source_id,
        lang=lang,
        title=title,
        body=None,  # gövde saklanmaz (spec §3.2/4); T0c gövdeyi açarsa burası değişir
        url=url,
        # Toplayıcı `observed_at`e yayıncının `news:publication_date`ini yazar (R172).
        published_at_claimed=_claimed(row["observed_at"], source_id),
        availability_basis=OBSERVED,
        content_hash=news_hash(source_id, url, title, None),
    )


def _claim_order(draft: NewsDraft) -> tuple[datetime, str]:
    return draft.published_at_claimed or _EPOCH, draft.content_hash


def news_from_observations(rows: Sequence[Mapping[str, Any]]) -> tuple[NewsDraft, ...]:
    """`source_observations` haber satırları → taslak; aynı içerikten EN ERKEN iddia kalır.

    `available_at` burada KURULMAZ (R172): veritabanı INSERT anında kendi saatiyle kurar.
    """
    earliest: dict[tuple[str, str], NewsDraft] = {}
    for row in rows:
        draft = _draft(row)
        key = (draft.source_id, draft.content_hash)
        current = earliest.get(key)
        if current is None or _claim_order(draft) < _claim_order(current):
            earliest[key] = draft
    return tuple(sorted(earliest.values(), key=_claim_order))


def archive_available_at(published: datetime, lag: timedelta) -> datetime:
    """Arşiv haberinin kullanılabilir anı: iddia edilen yayın + ölçülmüş güvenlik payı (§3/2)."""
    if published.tzinfo is None:
        raise ValueError("arşiv yayın zamanı saat dilimsiz")
    if lag < timedelta(0):
        raise ValueError(f"güvenlik payı negatif olamaz ({lag})")
    return published + lag


def write_news(conn: psycopg.Connection[Any], drafts: Sequence[NewsDraft]) -> int:
    """YENİ yazılan haber sayısı (yinelenenler sayılmaz)."""
    if not drafts:
        return 0
    columns = {name: [getattr(draft, name) for draft in drafts] for name, _ in _NEWS_COLUMNS}
    with conn.cursor() as cur:
        cur.execute(INSERT_NEWS, columns)
        return len(cur.fetchall())


def sync_news(conn: psycopg.Connection[Any], *, since: datetime | None = None) -> int:
    """`source_observations` → `news_items`; `since` verilmezse bütün geçmiş taranır."""
    with conn.cursor() as cur:
        cur.execute(_SELECT_OBSERVATIONS, (NEWS_KIND, list(NEWS_SOURCE_LANGS), since or _EPOCH))
        rows = cur.fetchall()
    observed = tuple(
        {"source_id": row[0], "observed_at": row[1], "payload": row[2]} for row in rows
    )
    return write_news(conn, news_from_observations(observed))


def load_news(conn: psycopg.Connection[Any], *, since: datetime) -> tuple[StoredNews, ...]:
    with conn.cursor() as cur:
        cur.execute(_SELECT_NEWS, (since,))
        rows = cur.fetchall()
    return tuple(
        StoredNews(
            item_id=int(row[0]),
            source_id=str(row[1]),
            lang=str(row[2]),
            title=str(row[3]),
            body=None if row[4] is None else str(row[4]),
            url=str(row[5]),
            published_at_claimed=row[6],
            available_at=row[7],
            availability_basis=str(row[8]),
            content_hash=str(row[9]),
            first_seen_at=row[10],
        )
        for row in rows
    )
