"""Anlık görüntü sözleşmesinin Python tarafındaki sabitleri (Faz 6 İz B tasarımı §4–§5, §8).

Sayılar ve adlar TEK yerde: dışa aktarıcı, `verify-snapshot` ve testler buradan okur. Holdout tabanı
`history.holdout`tan import EDİLMEZ (H1f); eşitliği `tests/test_site_contract.py` kanıtlar.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from football_edge.ledger import _canonical

SCHEMA_VERSION = 1
SCHEMA_PATH = Path("web/contract/snapshot.schema.json")
DEVIG_CONFIG_PATH = Path("config/model_faz3.yaml")
# Lig URL bölütleri: KALICI ve elle yazılır (§8.1–8.2, AK20 b); `leagues.yaml`dan ayrı dosya.
SITE_LEAGUES_PATH = Path("config/site_leagues.yaml")

# B4: holdout Londra'da 2026-07-01 00:00'da biter; bir günlük pay saat dilimini ve kaynak
# tarihi belirsizliğini kapatır. `site.public_floor()` aynı anı döner (0014, katalog testi).
PUBLIC_FLOOR = datetime(2026, 7, 2, tzinfo=UTC)

SITE_MIN_BOOKS = 3  # §5.2: bu kadar tam kitabı olmayan tur anlık görüntüde null
SITE_MIN_TEAM_MATCHES = 3  # §8.4: takım sayfasının indekslenebilirlik eşiği
MOVE_MIN_MATCHES = 5  # §5.2: ligin hareket dağılımı bu kadar mühürlü maçla yayımlanır
PATH_ID_LENGTH = 12  # §8.1: maç yolunda The Odds API olay kimliğinin öneki (çakışma kırmızı)

# `track-record`/`legal` sabit bölütlerdir (§8.1); `data` yayın dosyalarının, `_next` Next'in
# derleme çıktısının dizinidir (B-2). `_next` slug biçimine zaten uymaz; liste açık yazılır.
RESERVED_LEAGUE_SLUGS = frozenset({"track-record", "legal", "data", "_next"})
RESERVED_TEAM_SLUGS = frozenset({"match"})

# `site.record` (B5): Faz 5 `publications`a AYNI ad, tip ve sırayla bağlanır. Katalog testi
# görünümün kolonlarını bu tuple'la karşılaştırır; sona eklenen kolon da kırmızıdır.
RECORD_COLUMNS: tuple[tuple[str, str], ...] = (
    ("publication_id", "bigint"),
    ("match_id", "text"),
    ("market", "text"),
    ("outcome", "text"),
    ("published_at", "timestamp with time zone"),
    ("published_price", "numeric"),
    ("publication_ledger_id", "bigint"),
    ("closing_fair_price", "numeric"),
    ("clv", "double precision"),
    ("publication_hash", "text"),
)

# §4.3: yayımlanmayan kolon adları — (site_input ∪ site_audit) − (site ∪ şemanın anahtarları).
# Katalogdan türetilmiş kümeye eşitliği `tests/test_site_views_db.py` sınar.
FORBIDDEN_KEYS = frozenset(
    {
        "bookmaker",
        "book_key",
        "ledger_id",
        "point",
        "price",
        "bookmaker_last_update",
        "prev_hash",
        "row_hash",
        "is_closing",
    }
)

# Çıkış kodları: collect 2–8 ve 19, backtest/market/live/jev 9–18 (tests/test_jev_budget.py).
EXIT_SITE_CONFIG = 20  # SITE_DATABASE_URL yok, --out boş değil, git SHA okunamadı
EXIT_SITE_CHAIN = 21  # çıpa ya da zincir doğrulanamadı; indirgeme de kırmızıdır
EXIT_SITE_CUT = 22  # kesim, görünüm, taban ya da sicil tutarsız
EXIT_SITE_NONDETERMINISTIC = 23  # ikinci türetim farklı content_sha256 üretti ya da düştü
EXIT_SITE_INVALID = 24  # verify-snapshot kırmızı

# İçerik hash'inin dışında kalan alanlar (§5.2): derleme anı ve kaynak sürümü içerik değildir.
OUTSIDE_CONTENT = ("generated_at", "git_sha", "content_sha256")


def iso_z(moment: datetime) -> str:
    """`2026-09-20T14:00:00Z` — anlık görüntünün tek zaman biçimi (mikrosaniye taşınmaz)."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_sha256(snapshot: Mapping[str, Any]) -> str:
    """`OUTSIDE_CONTENT` hariç gövdenin kanonik JSON'unun (`ledger._canonical`) sha256'sı."""
    inner = {key: value for key, value in snapshot.items() if key not in OUTSIDE_CONTENT}
    return hashlib.sha256(_canonical(inner).encode("utf-8")).hexdigest()
