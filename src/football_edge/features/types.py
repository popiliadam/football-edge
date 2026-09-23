"""Özellik deposunun satır tipleri (spec §4; R166 — tek zaman alanı `available_at`, R172)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

OBSERVED = "observed"
ARCHIVE_CLAIMED = "archive_claimed"
AVAILABILITY_BASES = frozenset({OBSERVED, ARCHIVE_CLAIMED})

HOME = "home"
AWAY = "away"
BOTH = "both"
SIDES = frozenset({HOME, AWAY, BOTH})


@dataclass(frozen=True)
class StoredNews:
    item_id: int | None  # `news_items.id`; yazılmadan önce None
    source_id: str
    lang: str
    title: str
    body: str | None
    url: str
    published_at_claimed: datetime | None
    available_at: datetime
    availability_basis: str
    content_hash: str
    # Veritabanı saatiyle ilk görüldüğü an (R172); okuma yolunda doludur.
    first_seen_at: datetime | None = None

    def __post_init__(self) -> None:
        # Saat dilimsiz an karar anıyla sessizce yanlış karşılaştırılamaz; burada durur.
        if self.available_at.tzinfo is None:
            raise ValueError(f"{self.url}: available_at saat dilimsiz")
        if self.first_seen_at is not None and self.first_seen_at.tzinfo is None:
            raise ValueError(f"{self.url}: first_seen_at saat dilimsiz")
        if self.availability_basis not in AVAILABILITY_BASES:
            raise ValueError(f"{self.url}: bilinmeyen availability_basis {self.availability_basis}")


@dataclass(frozen=True)
class ItemGate:
    """Kademe 1 cevabının özeti: haber hangi maça, hangi tarafa ait, ne kadar güvenilir."""

    item_id: int
    match_id: str | None
    side: str | None  # HOME | AWAY | BOTH | None
    belongs: float
    reliability: float
    cluster_id: str
    asked_at: datetime

    def __post_init__(self) -> None:
        if self.asked_at.tzinfo is None:
            raise ValueError(f"haber {self.item_id}: asked_at saat dilimsiz")
        if self.side is not None and self.side not in SIDES:
            raise ValueError(f"haber {self.item_id}: bilinmeyen taraf {self.side!r}")
