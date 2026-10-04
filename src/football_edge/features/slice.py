"""Seçim dilimi sayacı (Plan 2 R181; I-10, I-11): `features slice-status`.

Sayılan birim (küme, maç, karar anı): en az bir tarafı `asked` durum işareti taşıyan (haberli, I5)
VE o karar anında baz gölge satırı (`model_predictions`) bulunan karar. Küme = kademe 2
`prompt_version`ı (R185); küme değişirse sayaç sıfırdan. Sonuç, kapanış, olasılık ya da cevap
içeriği OKUNMAZ — yalnız işaretin var olması (testle sabit).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import psycopg

from football_edge.features.tier2 import ASKED_MARKERS, SHADOW_STRATEGIES, VARIANT_REAL

TARGET = 900
RATE_WINDOW = timedelta(days=28)
READ_ONLY = "SET TRANSACTION READ ONLY"
# `jev_match_answers` işaret okuyucusu (`tests/test_jev_match_answers_readers.py` MARKER_READERS):
# yalnız `asked` işaretleri, her çağrıda `ASKED_MARKERS` parametresiyle.
SLICE_SQL = """
    SELECT a.prompt_version, a.match_id, a.decided_at
    FROM jev_match_answers a
    WHERE a.variant = %s AND a.question_id = ANY(%s) AND EXISTS (
        SELECT 1 FROM model_predictions p
        WHERE p.match_id = a.match_id AND p.decided_at = a.decided_at AND p.strategy = ANY(%s)
    )
    GROUP BY a.prompt_version, a.match_id, a.decided_at
"""


@dataclass(frozen=True)
class SliceLine:
    prompt_version: str
    count: int
    weekly_rate: float
    eta: date | None
    current: bool


def eta_for(count: int, weekly_rate: float, *, today: date, target: int = TARGET) -> date | None:
    """Bugünkü haftalık hızla `target`a varış; hız sıfırsa tahmin yok."""
    if count >= target:
        return today
    if weekly_rate <= 0:
        return None
    return today + timedelta(days=math.ceil((target - count) / weekly_rate * 7))


def _line(
    version: str, decided: Sequence[datetime], *, now: datetime, current: str | None, target: int
) -> SliceLine:
    recent = sum(1 for at in decided if at > now - RATE_WINDOW)
    rate = recent / (RATE_WINDOW / timedelta(weeks=1))
    eta = eta_for(len(decided), rate, today=now.date(), target=target)
    return SliceLine(version, len(decided), rate, eta, version == current)


def slice_lines(
    rows: Sequence[tuple[str, str, datetime]],
    *,
    now: datetime,
    current: str | None,
    target: int = TARGET,
) -> tuple[SliceLine, ...]:
    """Küme başına satır; geçerli küme hiç satırı yoksa da 0 ile görünür."""
    by_set: dict[str, list[datetime]] = {} if current is None else {current: []}
    for version, _match_id, decided_at in rows:
        by_set.setdefault(version, []).append(decided_at)
    return tuple(
        _line(version, decided, now=now, current=current, target=target)
        for version, decided in sorted(by_set.items())
    )


def render(lines: Sequence[SliceLine], *, target: int = TARGET) -> str:
    out = ["## Seçim dilimi (Plan 2 R181)", "", f"Hedef: {target} haberli karar, küme başına.", ""]
    for line in lines:
        mark = " (geçerli küme)" if line.current else ""
        eta = "tahmin yok (hız 0)" if line.eta is None else line.eta.isoformat()
        out.append(
            f"- `{line.prompt_version[:12]}`{mark}: {line.count} / {target} · haftalık "
            f"{line.weekly_rate:.1f} · tahmini varış {eta}"
        )
    return "\n".join(out) + "\n"


def read_only(conn: psycopg.Connection[Any]) -> None:
    """İşlemin İLK ifadesi olmalı: veri bağlantısı bu komutlarda yazamaz (M-8)."""
    with conn.cursor() as cur:
        cur.execute(READ_ONLY)


def select_slice_rows(conn: psycopg.Connection[Any]) -> tuple[tuple[str, str, datetime], ...]:
    with conn.cursor() as cur:
        cur.execute(SLICE_SQL, (VARIANT_REAL, list(ASKED_MARKERS), list(SHADOW_STRATEGIES)))
        rows = cur.fetchall()
    return tuple((str(r[0]), str(r[1]), r[2]) for r in rows)
