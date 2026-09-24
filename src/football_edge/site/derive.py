"""Döküm → anlık görüntü gövdesi (Faz 6 İz B tasarımı §5.2, §5.4, §8.4).

Saf fonksiyonlar: DB yok, saat yok, rastgelelik yok. Aynı döküm her süreçte, her `PYTHONHASHSEED`le
aynı gövdeyi üretir (B12); ikinci türetim bunu ölçer. Hesap ham değerle yapılır, yuvarlama yalnız
çıktıda (`_shown`). Konsensüs `market.consensus`, vig temizleme `market.devig`, CLV ve güven
aralığı `market.metrics` — model neyse site o; burada ikinci bir tanım yazılmaz.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from football_edge.market.consensus import LIVE_H2H, Quote, round_consensus
from football_edge.market.devig import InvalidPrices, devig
from football_edge.market.metrics import bootstrap_mean, clv
from football_edge.site.contract import (
    RESERVED_LEAGUE_SLUGS,
    RESERVED_TEAM_SLUGS,
    SCHEMA_VERSION,
    iso_z,
)
from football_edge.site.inputs import DeriveError as DeriveError  # dışa aktarıcının adı
from football_edge.site.inputs import ExportInputs, MatchRow, QuoteRow, RecordRow
from football_edge.site.slugs import match_slug, slugify

OUTCOMES = ("home", "draw", "away")
_MATCH_ID = re.compile(r"[0-9a-z]+")


@dataclass(frozen=True)
class RoundView:
    observed_at: datetime
    books: int
    probs: tuple[float, float, float]  # vig'i temizlenmiş, ham (0–1)


@dataclass(frozen=True)
class MatchView:
    row: MatchRow
    rounds: int
    sealed: bool
    opening: RoundView | None
    latest: RoundView | None
    closing: RoundView | None
    indexable: bool


def derive(inputs: ExportInputs) -> dict[str, Any]:
    """Anlık görüntü gövdesi (`generated_at`, `git_sha`, `content_sha256` HARİÇ)."""
    views = match_views(inputs)
    matches = [_match_json(view, inputs) for view in views]
    path_ids = [match["path_id"] for match in matches]
    if len(set(path_ids)) != len(path_ids):
        raise DeriveError("iki maç aynı path_id önekini taşıyor (§8.1)")
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger": {
            "rows": inputs.ledger.rows,
            "last_id": inputs.ledger.last_id,
            "head": inputs.ledger.head,
            "anchor": {
                "file": inputs.anchor.file,
                "rows": inputs.anchor.rows,
                "last_id": inputs.anchor.last_id,
                "head": inputs.anchor.head,
            },
        },
        "floor": iso_z(inputs.floor),
        "leagues": _leagues(inputs, views),
        "teams": _teams(inputs, views),
        "matches": matches,
        "record": _record(inputs.record),
        "value_badge": None,
        "analysis": None,
    }


def match_views(inputs: ExportInputs) -> tuple[MatchView, ...]:
    """Kesimde en az bir MAÇ ÖNCESİ 1X2 satırı olan maçlar, (başlama, kimlik) sırasıyla.

    Ürün maç öncesidir (spec §1.3, §3.3/3 "in-play yok"): başlama anından sonraki satırlar —
    snapshot turu The Odds API'nin canlı maçlarını da yazar — tura, `rounds`a, `latest`e ve
    `move`a girmez. Süzgeç dökülmüş satır üzerinde uygulanır: `commence_time` UPSERT'le değişir,
    görünüm değil türetim anı sayılır. Yalnız başladıktan sonra görülmüş maç listelenmez.
    """
    kickoffs = {row.id: row.commence_time for row in inputs.matches}
    everything: dict[str, list[QuoteRow]] = {}
    before: dict[str, list[QuoteRow]] = {}
    for quote in inputs.quotes:
        kickoff = kickoffs.get(quote.match_id)
        if kickoff is None:
            continue
        everything.setdefault(quote.match_id, []).append(quote)
        if pre_kickoff(quote, kickoff):
            before.setdefault(quote.match_id, []).append(quote)
    rows = sorted(
        (row for row in inputs.matches if row.id in before),
        key=lambda row: (row.commence_time, row.id),
    )
    return tuple(_view(row, before[row.id], everything[row.id], inputs) for row in rows)


def pre_kickoff(quote: QuoteRow, kickoff: datetime) -> bool:
    """Satır maç öncesi mi. Mühür turu `rounds.seal_window`un KAPSAYICI sınırıyla
    (`0 <= başlama − an`) tam başlama anında da yazılabilir: kapanış satırı eşitlikte kalır,
    sıradan snapshot satırı kalmaz."""
    return quote.observed_at < kickoff or (quote.is_closing and quote.observed_at == kickoff)


def _view(
    row: MatchRow,
    quotes: Sequence[QuoteRow],
    everything: Sequence[QuoteRow],
    inputs: ExportInputs,
) -> MatchView:
    """`quotes` maç öncesi satırlardır; `sealed` spec §5.2'nin tanımıyla kesimdeki HER satırdan."""
    times = sorted({quote.observed_at for quote in quotes})
    closing_times = sorted({quote.observed_at for quote in quotes if quote.is_closing})
    rounds = {moment: _round(row, quotes, moment, inputs) for moment in times}
    shown = [view for view in rounds.values() if view is not None]
    return MatchView(
        row=row,
        rounds=len(times),
        sealed=any(quote.is_closing for quote in everything),
        opening=rounds[times[0]],
        latest=rounds[times[-1]],
        closing=rounds[closing_times[-1]] if closing_times else None,
        indexable=len(times) >= 2 and any(view.books >= inputs.config.min_books for view in shown),
    )


def _round(
    row: MatchRow, quotes: Sequence[QuoteRow], moment: datetime, inputs: ExportInputs
) -> RoundView | None:
    """Turun konsensüsü ve vig'i temizlenmiş olasılığı; tam kitap yoksa, temizlenemezse None."""
    found = round_consensus(
        [
            Quote(q.match_id, q.observed_at, str(q.book_key), LIVE_H2H, q.outcome, q.price)
            for q in quotes
            if q.observed_at == moment
        ],
        moment,
        row.home,
        row.away,
    )
    if found is None:
        return None
    try:
        home, draw, away = devig(found.means, inputs.config.devig_method)
    except InvalidPrices:
        return None
    return RoundView(moment, found.books, (home, draw, away))


def _shown(value: float, digits: int) -> float:
    """Görüntü hassasiyetine yuvarlar; `-0.0` `0.0` olur (sayfada "-0,0" görünmesin)."""
    return round(value, digits) + 0.0


def _percent(probs: tuple[float, float, float]) -> dict[str, float]:
    return {name: _shown(100.0 * value, 1) for name, value in zip(OUTCOMES, probs, strict=True)}


def _visible(view: RoundView | None, inputs: ExportInputs) -> RoundView | None:
    return view if view is not None and view.books >= inputs.config.min_books else None


def _round_json(view: RoundView | None, inputs: ExportInputs) -> dict[str, Any] | None:
    shown = _visible(view, inputs)
    if shown is None:
        return None
    return {
        "observed_at": iso_z(shown.observed_at),
        "books": shown.books,
        "p": _percent(shown.probs),
    }


def _move(view: MatchView, inputs: ExportInputs) -> tuple[float, float, float] | None:
    """Açılış → kapanış (yoksa son) hareketi, ham yüzde puanı; iki uç da görünür değilse None."""
    start = _visible(view.opening, inputs)
    end = _visible(view.closing if view.sealed else view.latest, inputs)
    if start is None or end is None:
        return None
    home, draw, away = (
        100.0 * (after - before) for before, after in zip(start.probs, end.probs, strict=True)
    )
    return home, draw, away


def _match_json(view: MatchView, inputs: ExportInputs) -> dict[str, Any]:
    row = view.row
    length = inputs.config.path_id_length
    if _MATCH_ID.fullmatch(row.id) is None or len(row.id) < length:
        raise DeriveError(f"maç kimliği beklenmeyen biçimde (lig {row.league_id})")
    move = _move(view, inputs)
    return {
        "id": row.id,
        "league_id": row.league_id,
        "path_id": row.id[:length],
        "slug": match_slug(row.home, row.away),
        "date": row.commence_time.astimezone(UTC).date().isoformat(),
        "commence_time": iso_z(row.commence_time),
        "home": row.home,
        "away": row.away,
        "sealed": view.sealed,
        "rounds": view.rounds,
        "h2h": {
            "opening": _round_json(view.opening, inputs),
            "latest": _round_json(view.latest, inputs),
            "closing": _round_json(view.closing, inputs),
        },
        "move": None
        if move is None
        else {name: _shown(value, 1) for name, value in zip(OUTCOMES, move, strict=True)},
        "indexable": view.indexable,
    }


def _leagues(inputs: ExportInputs, views: Sequence[MatchView]) -> list[dict[str, Any]]:
    """Lig slug'ı addan TÜRETİLMEZ (iki lig aynı adı taşır: `ger.1`/`aut.1` "Bundesliga");
    `config/site_leagues.yaml`ın kalıcı değeri dökümle gelir. Çakışma ve ayrılmış ad yine durur."""
    seen: dict[str, str] = {}
    found: list[dict[str, Any]] = []
    for league in sorted(inputs.leagues, key=lambda league: league.id):
        if league.slug in RESERVED_LEAGUE_SLUGS or league.slug in seen:
            raise DeriveError(
                f"lig {league.id}: slug ayrılmış ya da {seen.get(league.slug)} ile çakışıyor"
            )
        seen[league.slug] = league.id
        own = [view for view in views if view.row.league_id == league.id]
        found.append(
            {
                "id": league.id,
                "slug": league.slug,
                "name": league.name,
                "country": league.country,
                "matches": len(own),
                "move_distribution": _distribution(own, inputs),
            }
        )
    return found


def _distribution(views: Sequence[MatchView], inputs: ExportInputs) -> dict[str, float] | None:
    """Mühürlü, en az iki turlu maçlarda |açılış → kapanış| hareketinin en büyük bileşeni."""
    moves = [
        max(abs(value) for value in move)
        for view in views
        if view.sealed and view.rounds >= 2 and (move := _move(view, inputs)) is not None
    ]
    if len(moves) < inputs.config.move_min_matches:
        return None
    p10, p50, p90 = (float(value) for value in np.percentile(np.asarray(moves), [10, 50, 90]))
    return {"p10": _shown(p10, 1), "p50": _shown(p50, 1), "p90": _shown(p90, 1)}


def _teams(inputs: ExportInputs, views: Sequence[MatchView]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = {}
    for view in views:
        for name in (view.row.home, view.row.away):
            key = (view.row.league_id, name)
            counts[key] = counts.get(key, 0) + 1
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for (league_id, name), count in counts.items():
        key = (league_id, slugify(name))
        if key[1] in RESERVED_TEAM_SLUGS or key in entries:
            raise DeriveError(f"lig {league_id}: bir takım slug'ı ayrılmış ya da çakışıyor")
        entries[key] = {
            "league_id": league_id,
            "slug": key[1],
            "name": name,
            "matches": count,
            "indexable": count >= inputs.config.min_team_matches,
        }
    return [entries[key] for key in sorted(entries)]


def _record(rows: Sequence[RecordRow]) -> dict[str, Any]:
    entries = [
        {
            "publication_id": row.publication_id,
            "match_id": row.match_id,
            "market": row.market,
            "outcome": row.outcome,
            "published_at": iso_z(row.published_at),
            "published_price": _shown(row.published_price, 2),
            "publication_ledger_id": row.publication_ledger_id,
            "closing_fair_price": _shown(row.closing_fair_price, 2),
            "clv": _shown(100.0 * row.clv, 2),
            "publication_hash": row.publication_hash,
        }
        for row in sorted(rows, key=lambda row: row.publication_id)
    ]
    summary = None
    if rows:
        interval = bootstrap_mean([row.clv for row in rows])
        summary = {
            "mean_clv": _shown(100.0 * interval.estimate, 2),
            "ci_low": _shown(100.0 * interval.low, 2),
            "ci_high": _shown(100.0 * interval.high, 2),
            "n": len(rows),
        }
    return {"published": len(rows), "entries": entries, "summary": summary}


def record_mismatches(inputs: ExportInputs) -> list[str]:
    """§6.4/3d: her sicil girdisinin CLV'si defterin kapanış konsensüsünden yeniden hesaplanır."""
    views = {view.row.id: view for view in match_views(inputs)}
    problems: list[str] = []
    for row in inputs.record:
        view = views.get(row.match_id)
        closing = None if view is None else view.closing
        if row.market != LIVE_H2H or row.outcome not in OUTCOMES:
            problems.append(f"yayın {row.publication_id}: market/sonuç sözleşme dışı")
        elif row.publication_ledger_id > inputs.ledger.last_id:
            problems.append(f"yayın {row.publication_id}: kesimden sonraki bir satıra bağlı")
        elif closing is None:
            problems.append(f"yayın {row.publication_id}: maçın kesimde kapanış konsensüsü yok")
        else:
            fair = closing.probs[OUTCOMES.index(row.outcome)]
            if not math.isclose(row.clv, clv(row.published_price, fair), abs_tol=1e-9):
                problems.append(f"yayın {row.publication_id}: CLV defterden yeniden hesaplanamıyor")
            if not math.isclose(row.closing_fair_price, 1.0 / fair, rel_tol=1e-9):
                problems.append(
                    f"yayın {row.publication_id}: kapanış adil oranı defterle uyuşmuyor"
                )
    return problems
