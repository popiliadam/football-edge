"""Site testlerinin sentetik defteri: turlar → zincirli satırlar, çıpa deposu, döküm girdileri.

Fiyatlar ADİL kitaplardır (Σ 1/o = 1): `devig` onları her yöntemde olduğu gibi döndürür, beklenen
olasılıklar elle yazılır (`2.0/4.0/4.0` → 50/25/25). Kitaplar arası ortalama da aynı fiyatsa adil
kalır; farklı adil kitapların ortalaması Σ < 1 verir ve temizlenemez — bu yüzden bir turdaki
kitaplar aynı üçlüyü taşır.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from football_edge.ledger import GENESIS, canonical_timestamp, chain
from football_edge.site.contract import (
    MOVE_MIN_MATCHES,
    PATH_ID_LENGTH,
    PUBLIC_FLOOR,
    SITE_MIN_BOOKS,
    SITE_MIN_TEAM_MATCHES,
)
from football_edge.site.inputs import (
    AnchorValue,
    DumpConfig,
    ExportInputs,
    LedgerCut,
    dump_text,
    load_inputs,
)
from tests.fake_db import stored_row

# Adil üçlüler (ev, beraberlik, deplasman) ve elle hesaplanmış yüzdeleri.
EVEN = (2.0, 4.0, 4.0)  # 50.0 / 25.0 / 25.0
AWAY_FAVOURED = (4.0, 4.0, 2.0)  # 25.0 / 25.0 / 50.0
DRAWISH = (5.0, 2.5, 2.5)  # 20.0 / 40.0 / 40.0
WIDE = (2.5, 5.0, 2.5)  # 40.0 / 20.0 / 40.0
HOME_HEAVY = (1.25, 10.0, 10.0)  # 80.0 / 10.0 / 10.0
HOME_LEAN = (1.6, 8.0, 4.0)  # 62.5 / 12.5 / 25.0
# Marjlı ama simetrik: üç kitabın ortalaması 2.8/2.8/2.8 → power yöntemi 33.3 / 33.3 / 33.3.
SYMMETRIC = ((2.7, 2.7, 2.7), (2.8, 2.8, 2.8), (2.9, 2.9, 2.9))
BOOKS = ("kitap-a", "kitap-b", "kitap-c", "kitap-d")


@dataclass(frozen=True)
class Round:
    match_id: str
    observed_at: str  # ISO, Z
    home: str
    away: str
    books: Sequence[tuple[float, float, float]]
    is_closing: bool = False
    drop_away_for: int | None = None  # bu sıradaki kitabın deplasman satırı yok (eksik kitap)


def payloads(rounds: Sequence[Round]) -> tuple[dict[str, Any], ...]:
    """Turları defter yüküne çevirir; sıra = defter sırası (kitap, sonra ev, beraberlik, dep.)."""
    found: list[dict[str, Any]] = []
    for item in rounds:
        for index, (home, draw, away) in enumerate(item.books):
            for outcome, price in ((item.home, home), ("Draw", draw), (item.away, away)):
                if outcome == item.away and item.drop_away_for == index:
                    continue
                found.append(
                    {
                        "match_id": item.match_id,
                        "observed_at": canonical_timestamp(item.observed_at),
                        "bookmaker": BOOKS[index],
                        "market": "h2h",
                        "outcome": outcome,
                        "point": None,
                        "price": price,
                        "bookmaker_last_update": canonical_timestamp(item.observed_at),
                        "is_closing": item.is_closing,
                    }
                )
    return tuple(found)


def ledger(rows: Sequence[dict[str, Any]], *, first_id: int = 1) -> tuple[dict[str, Any], ...]:
    """Zincirlenmiş, psycopg tipleriyle saklanmış satırlar (`id` 1'den)."""
    return tuple(
        {**stored_row(row), "id": index + first_id}
        for index, row in enumerate(chain(tuple(rows), prev_hash=GENESIS))
    )


def anchored_repo(root: Path, *, rows: int, last_id: int, head: str, day: str) -> Path:
    """Çıpa dosyasını geçici bir git deposuna commit'ler; `ledger/` dizinini döner.

    Çıpa eksikliği kontrolü git geçmişi ister (`test_verify_chain.py` deseni); geçmişsiz dizinde
    "ATLANDI" satırı dışa aktarımı her koşuda durdururdu.
    """
    directory = root / "ledger"
    directory.mkdir(parents=True)
    (directory / f"head-{day}.txt").write_text(
        f"{day}T12:00:00+00:00\nrows={rows}\nlast_id={last_id}\nhead={head}\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@example.com", "-c", "user.name=t"]
        + ["commit", "-q", "-m", "çıpa"],
        check=True,
    )
    return directory


def at(text: str) -> datetime:
    return datetime.fromisoformat(canonical_timestamp(text))


def quote_rows(rounds: Sequence[Round]) -> list[tuple[Any, ...]]:
    """`site_input.h2h_quotes` kolon sırasıyla satırlar; `book_key` = turdaki kitap sırası."""
    return [
        (
            ledger_id,
            row["match_id"],
            at(row["observed_at"]),
            row["is_closing"],
            row["outcome"],
            Decimal(str(row["price"])),
            BOOKS.index(row["bookmaker"]) + 1,
        )
        for ledger_id, row in enumerate(payloads(rounds), start=1)
    ]


def export_dump(
    *,
    leagues: Sequence[tuple[str, str, str, str]],  # id, ad, ülke, site slug'ı
    matches: Sequence[tuple[str, str, str, str, str]],
    rounds: Sequence[Round],
    record: Sequence[tuple[Any, ...]] = (),
    method: str = "power",
) -> str:
    """Dışa aktarımın üreteceği döküm METNİ (`dump_text`), DB'siz."""
    quotes = quote_rows(rounds)
    last_id = len(quotes)
    return dump_text(
        config=DumpConfig(
            method, SITE_MIN_BOOKS, SITE_MIN_TEAM_MATCHES, MOVE_MIN_MATCHES, PATH_ID_LENGTH
        ),
        floor=PUBLIC_FLOOR,
        ledger=LedgerCut(last_id, last_id, "c" * 64),
        anchor=AnchorValue("head-2026-09-21.txt", last_id, last_id, "c" * 64),
        leagues=leagues,
        matches=[(mid, league, at(when), home, away) for mid, league, when, home, away in matches],
        quotes=quotes,
        record=record,
    )


def export_inputs(**parts: Any) -> ExportInputs:
    """`export_dump`in çözülmüş hâli — iki türetimin de çalıştığı tipler."""
    return load_inputs(export_dump(**parts))
