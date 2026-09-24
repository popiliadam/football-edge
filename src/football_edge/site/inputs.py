"""Türetim girdi dökümü (Faz 6 İz B tasarımı §5.1/4–5).

Dışa aktarım işleminde okunan HER türetim girdisi — `site.*` ve `site_input.*` satırları, çıpa,
yapılandırma — tek bir kanonik JSON metnine (`ledger._canonical`) yazılır; iki türetim de bu
metinden çözülen tiplerle çalışır, DB'nin ham tipleri (`Decimal`, `datetime`) türetime girmez.
Sayılar metin olarak taşınır, tip dökümün şemasıyla açıktır. `site_audit` satırları dökümde
YOKTUR: zincir doğrulaması türetimden önce biter. Döküm kitap bazında fiyat taşır: diske ve loga
yazılmaz.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from football_edge.ledger import _canonical, canonical_timestamp

DUMP_VERSION = 1


class DeriveError(ValueError):
    """Döküm yayımlanabilir bir gövdeye dönüşmüyor (slug çakışması, kimlik biçimi, bozuk zaman, …).

    Burada tanımlanır, çünkü bozuk zaman dökümü çözerken görülür ve `derive` bu modülü import
    eder; `football_edge.site.derive.DeriveError` aynı sınıftır.
    """


@dataclass(frozen=True)
class DumpConfig:
    devig_method: str
    min_books: int
    min_team_matches: int
    move_min_matches: int
    path_id_length: int


@dataclass(frozen=True)
class LedgerCut:
    rows: int
    last_id: int
    head: str  # kesimin son satırının YENİDEN HESAPLANMIŞ hash'i


@dataclass(frozen=True)
class AnchorValue:
    file: str
    rows: int
    last_id: int
    head: str


@dataclass(frozen=True)
class LeagueRow:
    id: str
    name: str
    country: str
    slug: str  # `config/site_leagues.yaml`dan (DB değil); addan türetilmez


@dataclass(frozen=True)
class MatchRow:
    id: str
    league_id: str
    commence_time: datetime
    home: str
    away: str


@dataclass(frozen=True)
class QuoteRow:
    ledger_id: int
    match_id: str
    observed_at: datetime
    is_closing: bool
    outcome: str
    price: float
    book_key: int


@dataclass(frozen=True)
class RecordRow:
    publication_id: int
    match_id: str
    market: str
    outcome: str
    published_at: datetime
    published_price: float
    publication_ledger_id: int
    closing_fair_price: float
    clv: float
    publication_hash: str


@dataclass(frozen=True)
class ExportInputs:
    config: DumpConfig
    floor: datetime
    ledger: LedgerCut
    anchor: AnchorValue
    leagues: tuple[LeagueRow, ...]
    matches: tuple[MatchRow, ...]
    quotes: tuple[QuoteRow, ...]
    record: tuple[RecordRow, ...]


def encode(value: object) -> object:
    """DB değeri → döküm değeri: sayı metin, zaman kanonik UTC metni; bool, None, metin aynen."""
    if value is None or isinstance(value, bool | str):
        return value
    if isinstance(value, int | Decimal):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, datetime):
        return canonical_timestamp(value)
    raise TypeError(f"dökümde desteklenmeyen tip: {type(value).__name__}")


def dump_text(
    *,
    config: DumpConfig,
    floor: datetime,
    ledger: LedgerCut,
    anchor: AnchorValue,
    leagues: Sequence[Sequence[object]],
    matches: Sequence[Sequence[object]],
    quotes: Sequence[Sequence[object]],
    record: Sequence[Sequence[object]],
) -> str:
    """Satırları (DB'nin döndürdüğü kolon sırasıyla) kanonik döküm metnine çevirir."""
    return _canonical(
        {
            "version": DUMP_VERSION,
            "config": {name: encode(value) for name, value in vars(config).items()},
            "floor": encode(floor),
            "ledger": {name: encode(value) for name, value in vars(ledger).items()},
            "anchor": {name: encode(value) for name, value in vars(anchor).items()},
            "leagues": [[encode(value) for value in row] for row in leagues],
            "matches": [[encode(value) for value in row] for row in matches],
            "quotes": [[encode(value) for value in row] for row in quotes],
            "record": [[encode(value) for value in row] for row in record],
        }
    )


def load_inputs(text: str) -> ExportInputs:
    """Döküm metnini tiplerine çözer; biçim bozuksa `ValueError`."""
    raw = json.loads(text)
    if raw.get("version") != DUMP_VERSION:
        raise ValueError("döküm sürümü tanınmıyor")
    config = raw["config"]
    return ExportInputs(
        config=DumpConfig(
            devig_method=str(config["devig_method"]),
            min_books=int(config["min_books"]),
            min_team_matches=int(config["min_team_matches"]),
            move_min_matches=int(config["move_min_matches"]),
            path_id_length=int(config["path_id_length"]),
        ),
        floor=_time(raw["floor"]),
        ledger=LedgerCut(
            int(raw["ledger"]["rows"]), int(raw["ledger"]["last_id"]), raw["ledger"]["head"]
        ),
        anchor=_anchor(raw["anchor"]),
        leagues=tuple(LeagueRow(str(a), str(b), str(c), str(d)) for a, b, c, d in raw["leagues"]),
        matches=tuple(_match(row) for row in raw["matches"]),
        quotes=tuple(_quote(row) for row in raw["quotes"]),
        record=tuple(_record(row) for row in raw["record"]),
    )


def _time(text: object) -> datetime:
    """Döküm zamanı: `encode` onu `canonical_timestamp`le yazdı; başka her biçim bozuk dökümdür.

    Saat dilimsiz metin UTC SAYILMAZ (`canonical_timestamp` öyle yapardı): döküm hep `+00:00`
    taşır. Naive an türetimin ortasında düz `ValueError` (`iso_z`) ya da `TypeError` (başlama
    karşılaştırması) olurdu; dışa aktarıcı yalnız `DeriveError`ı çıkış koduna eşler.
    """
    if not isinstance(text, str):
        raise DeriveError(f"dökümde zaman metin değil: {type(text).__name__}")
    try:
        canonical = canonical_timestamp(text)
    except ValueError:
        raise DeriveError(f"dökümde zaman biçim dışı: {text!r}") from None
    if canonical != text:
        raise DeriveError(f"dökümde zaman kanonik UTC metni değil: {text!r}")
    return datetime.fromisoformat(canonical)


def _anchor(raw: Mapping[str, Any]) -> AnchorValue:
    return AnchorValue(str(raw["file"]), int(raw["rows"]), int(raw["last_id"]), str(raw["head"]))


def _match(row: Sequence[Any]) -> MatchRow:
    match_id, league_id, commence_time, home, away = row
    return MatchRow(str(match_id), str(league_id), _time(commence_time), str(home), str(away))


def _quote(row: Sequence[Any]) -> QuoteRow:
    ledger_id, match_id, observed_at, is_closing, outcome, price, book_key = row
    if not isinstance(is_closing, bool):
        raise ValueError("is_closing bool değil")
    return QuoteRow(
        int(ledger_id),
        str(match_id),
        _time(observed_at),
        is_closing,
        str(outcome),
        float(price),
        int(book_key),
    )


def _record(row: Sequence[Any]) -> RecordRow:
    (
        publication_id,
        match_id,
        market,
        outcome,
        published_at,
        published_price,
        publication_ledger_id,
        closing_fair_price,
        clv,
        publication_hash,
    ) = row
    return RecordRow(
        int(publication_id),
        str(match_id),
        str(market),
        str(outcome),
        _time(published_at),
        float(published_price),
        int(publication_ledger_id),
        float(closing_fair_price),
        float(clv),
        str(publication_hash),
    )
