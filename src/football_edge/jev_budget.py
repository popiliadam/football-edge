"""Jev harcama tavanı (spec §9, R159): her çağrıdan ÖNCE ayın toplamı + tahmin ≤ tavan.

Odds API kota deseninin (`odds_api.guard_quota` → `EXIT_QUOTA_EXHAUSTED`) karşılığı: tavan
aşılacaksa çağrı YAPILMAZ, `BudgetExceeded` adıyla çıkar, CLI onu `EXIT_BUDGET`e çevirir.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol

import psycopg

from football_edge.jev import (
    COST_ESTIMATED,
    COST_REPORTED,
    COST_UNPRICED,
    BatteryAnswer,
    ChoiceAnswer,
    JevClient,
    Question,
    battery_question_ids,
)

MONTHLY_CAP_USD = 25.0
EXIT_BUDGET = 16
# ÖLÇÜLMEDİ: SDK maliyet bildirmez; ilk 100 gerçek çağrıdan sonra Plan 2 ölçümle değiştirir.
# Yüksek tutulur: fazla tahmin tavanı erken kapatır (görünür), düşük tahmin aşırtır (görünmez).
ESTIMATE_USD_UNMEASURED = 0.01
KIND_CHOICE = "choice"
KIND_BATTERY = "battery"
FAILED_SUFFIX = "_failed"
LEDGER_BASES = frozenset({COST_REPORTED, COST_ESTIMATED})


class BudgetExceeded(RuntimeError):
    """Bu çağrı ayın tavanını aşardı; çağrı yapılmadı."""


def month_bounds(now: datetime) -> tuple[datetime, datetime]:
    """UTC takvim ayının [başı, sonraki ayın başı). Saat dilimsiz an reddedilir: ay belirsizdir."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(f"saat dilimsiz an: {now.isoformat()}")
    start = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        return start, start.replace(year=start.year + 1, month=1)
    return start, start.replace(month=start.month + 1)


@dataclass(frozen=True)
class SpendEntry:
    at: datetime
    kind: str
    cost_usd: float
    cost_basis: str
    input_tokens: int | None
    output_tokens: int | None

    def __post_init__(self) -> None:
        month_bounds(self.at)
        if not self.kind:
            raise ValueError("kind boş")
        # NaN girerse ay toplamı NaN olur ve `toplam + tahmin > tavan` hep False: tavan kapanır.
        if not (math.isfinite(self.cost_usd) and self.cost_usd >= 0):
            raise ValueError(f"cost_usd sonlu ve ≥ 0 olmalı: {self.cost_usd}")
        if self.cost_basis not in LEDGER_BASES:
            raise ValueError(f"deftere yalnız reported/estimated girer: {self.cost_basis}")
        for tokens in (self.input_tokens, self.output_tokens):
            if tokens is not None and tokens < 0:
                raise ValueError(f"token sayısı negatif: {tokens}")


class SpendLedger(Protocol):
    def month_total(self, now: datetime) -> float: ...

    def record(
        self,
        *,
        at: datetime,
        kind: str,
        cost_usd: float,
        cost_basis: str = COST_REPORTED,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None: ...


class MemorySpendLedger:
    """Testler için: kayıtlar değişmez bir demette birikir."""

    def __init__(self, entries: Sequence[SpendEntry] = ()) -> None:
        self._entries: tuple[SpendEntry, ...] = tuple(entries)

    @property
    def entries(self) -> tuple[SpendEntry, ...]:
        return self._entries

    def month_total(self, now: datetime) -> float:
        start, end = month_bounds(now)
        return sum(entry.cost_usd for entry in self._entries if start <= entry.at < end)

    def record(
        self,
        *,
        at: datetime,
        kind: str,
        cost_usd: float,
        cost_basis: str = COST_REPORTED,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        entry = SpendEntry(at, kind, cost_usd, cost_basis, input_tokens, output_tokens)
        self._entries = (*self._entries, entry)


MONTH_TOTAL_SQL = """
    SELECT coalesce(sum(cost_usd), 0) FROM jev_spend WHERE spent_at >= %s AND spent_at < %s
"""
INSERT_SPEND_SQL = """
    INSERT INTO jev_spend (spent_at, kind, cost_usd, cost_basis, input_tokens, output_tokens)
    VALUES (%s, %s, %s, %s, %s, %s)
"""


class PostgresSpendLedger:
    """`jev_spend` (0012). Bağlantı autocommit OLMALI: çağıranın rollback'i harcamayı silmesin."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        if not conn.autocommit:
            raise ValueError(
                "PostgresSpendLedger autocommit bağlantı ister — geri alınan bir işlem "
                "yapılmış çağrının kaydını da siler ve tavan eksik sayar"
            )
        self._conn = conn

    def month_total(self, now: datetime) -> float:
        with self._conn.cursor() as cur:
            cur.execute(MONTH_TOTAL_SQL, month_bounds(now))
            found = cur.fetchone()
        return 0.0 if found is None else float(found[0])

    def record(
        self,
        *,
        at: datetime,
        kind: str,
        cost_usd: float,
        cost_basis: str = COST_REPORTED,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        entry = SpendEntry(at, kind, cost_usd, cost_basis, input_tokens, output_tokens)
        with self._conn.cursor() as cur:
            cur.execute(
                INSERT_SPEND_SQL,
                (
                    entry.at,
                    entry.kind,
                    entry.cost_usd,
                    entry.cost_basis,
                    entry.input_tokens,
                    entry.output_tokens,
                ),
            )


def _positive(name: str, value: float) -> float:
    if not (math.isfinite(value) and value > 0):
        raise ValueError(f"{name} sonlu ve > 0 olmalı: {value}")
    return value


class BudgetedJev:
    """`JevClient`ı sarar: tavan kontrolü çağrıdan ÖNCE, kayıt çağrıdan SONRA.

    Başarısız çağrı da tahminle kaydedilir (`<tür>_failed`): SDK yeniden denemeleri
    faturalanmış olabilir; fazla saymak tavanı erken kapatır, eksik saymak aşırtır.
    """

    def __init__(
        self,
        client: JevClient,
        ledger: SpendLedger,
        *,
        cap_usd: float,
        estimate_usd: float,
        clock: Callable[[], datetime],
    ) -> None:
        self._client = client
        self._ledger = ledger
        self._cap = _positive("cap_usd", cap_usd)
        # Sıfır tahmin, tavana tam oturmuş bir ayda bir çağrı daha geçirir.
        self._estimate = _positive("estimate_usd", estimate_usd)
        self._clock = clock

    def _guard(self) -> datetime:
        at = self._clock()
        spent = self._ledger.month_total(at)
        if spent + self._estimate > self._cap:
            raise BudgetExceeded(
                f"jev: ay toplamı ${spent:.4f} + tahmin ${self._estimate:.4f} > "
                f"tavan ${self._cap:.2f} — çağrı yapılmadı"
            )
        return at

    def _record_failure(self, at: datetime, kind: str) -> None:
        self._ledger.record(
            at=at, kind=kind + FAILED_SUFFIX, cost_usd=self._estimate, cost_basis=COST_ESTIMATED
        )

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        at = self._guard()
        try:
            answer = self._client.ask_choice(state, instructions, criteria)
        except Exception:
            self._record_failure(at, KIND_CHOICE)
            raise
        self._ledger.record(
            at=at, kind=KIND_CHOICE, cost_usd=self._estimate, cost_basis=COST_ESTIMATED
        )
        return answer

    def ask_battery(self, state: Mapping[str, Any], questions: Sequence[Question]) -> BatteryAnswer:
        # Geçersiz batarya çağrı sayılmaz: ne tavanı yoklar ne deftere başarısız çağrı yazar.
        battery_question_ids(questions)
        at = self._guard()
        try:
            answer = self._client.ask_battery(state, questions)
        except Exception:
            self._record_failure(at, KIND_BATTERY)
            raise
        if answer.cost_basis == COST_UNPRICED:
            answer = replace(answer, cost_usd=self._estimate, cost_basis=COST_ESTIMATED)
        self._ledger.record(
            at=at,
            kind=KIND_BATTERY,
            cost_usd=answer.cost_usd,
            cost_basis=answer.cost_basis,
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
        )
        return answer
