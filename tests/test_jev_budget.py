"""Jev harcama tavanı (spec §9, R159): çağrıdan ÖNCE yoklanır, aşılacaksa çağrı YAPILMAZ.

Ağa çıkmaz: istemci `FakeBatteryJev`, defter `MemorySpendLedger` ya da sahte bağlantılı
`PostgresSpendLedger`. Gerçek `jev_spend` tablosu `tests/test_jev_tables_db.py`de okunur.
"""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from football_edge.jev import COST_ESTIMATED, COST_REPORTED, COST_UNPRICED, ChoiceAnswer, Question
from football_edge.jev_budget import (
    EXIT_BUDGET,
    MONTHLY_CAP_USD,
    BudgetedJev,
    BudgetExceeded,
    MemorySpendLedger,
    PostgresSpendLedger,
    SpendEntry,
    month_bounds,
)
from tests.fake_jev import FakeBatteryJev, FakeJev

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
QUESTIONS = (
    Question(question_id="ait", instructions="ait mi?", criteria={"evet": "e", "hayır": "h"}),
    Question(question_id="taraf", instructions="kim?", criteria={"ev": "e", "deplasman": "d"}),
)


def _entry(at: datetime, cost: float, kind: str = "battery") -> SpendEntry:
    return SpendEntry(at, kind, cost, COST_REPORTED, None, None)


def _budgeted(
    client: Any,
    ledger: MemorySpendLedger,
    *,
    cap: float = 1.0,
    estimate: float = 0.02,
    now: datetime = NOW,
) -> BudgetedJev:
    return BudgetedJev(client, ledger, cap_usd=cap, estimate_usd=estimate, clock=lambda: now)


def test_the_cap_and_exit_codes_are_the_registered_values() -> None:
    assert MONTHLY_CAP_USD == 25.0
    assert EXIT_BUDGET == 16


def test_every_exit_code_name_owns_exactly_one_value_across_commands() -> None:
    """16/17 mevcut kodlarla çakışmaz (collect 2–8, backtest 9–14, live 15)."""
    modules = (
        "football_edge.collect",
        "football_edge.backtest.__main__",
        "football_edge.market.__main__",
        "football_edge.live.__main__",
        "football_edge.jev",
        "football_edge.jev_budget",
    )
    owners: dict[int, set[str]] = {}
    for name in modules:
        module = importlib.import_module(name)
        for attr, value in vars(module).items():
            if attr.startswith("EXIT_") and isinstance(value, int):
                owners.setdefault(value, set()).add(attr)

    assert {code: names for code, names in owners.items() if len(names) > 1} == {}
    assert owners[16] == {"EXIT_BUDGET"}
    assert owners[17] == {"EXIT_NO_JEV_KEY"}


def test_month_bounds_is_the_utc_calendar_month_and_rolls_over_december() -> None:
    assert month_bounds(NOW) == (
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 10, 1, tzinfo=UTC),
    )
    assert month_bounds(datetime(2026, 12, 31, 23, 59, tzinfo=UTC)) == (
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2027, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="saat dilimsiz"):
        month_bounds(datetime(2026, 9, 23, 12, 0))


def test_memory_ledger_sums_only_the_current_utc_month() -> None:
    ledger = MemorySpendLedger(
        (
            _entry(datetime(2026, 8, 31, 23, 59, tzinfo=UTC), 5.0),
            _entry(datetime(2026, 9, 1, 0, 0, tzinfo=UTC), 0.25),
            _entry(datetime(2026, 9, 30, 23, 59, tzinfo=UTC), 0.5),
            _entry(datetime(2026, 10, 1, 0, 0, tzinfo=UTC), 7.0),
        )
    )

    assert ledger.month_total(NOW) == pytest.approx(0.75)


def test_spend_entry_rejects_what_the_database_would_reject() -> None:
    with pytest.raises(ValueError, match="kind"):
        SpendEntry(NOW, "", 0.1, COST_REPORTED, None, None)
    with pytest.raises(ValueError, match="reported/estimated"):
        SpendEntry(NOW, "battery", 0.1, COST_UNPRICED, None, None)
    with pytest.raises(ValueError, match="token"):
        SpendEntry(NOW, "battery", 0.1, COST_REPORTED, -1, None)
    with pytest.raises(ValueError, match="saat dilimsiz"):
        SpendEntry(datetime(2026, 9, 23), "battery", 0.1, COST_REPORTED, None, None)


def test_a_call_under_the_cap_is_made_and_its_reported_cost_is_recorded() -> None:
    client = FakeBatteryJev(cost_usd=0.003, choices={"taraf": "deplasman"})
    ledger = MemorySpendLedger()

    answer = _budgeted(client, ledger).ask_battery({"haber": "x"}, QUESTIONS)

    assert answer.answers["taraf"].choice == "deplasman"
    assert len(client.seen) == 1
    assert ledger.entries == (SpendEntry(NOW, "battery", 0.003, COST_REPORTED, None, None),)


def test_an_unpriced_answer_is_recorded_and_returned_at_the_estimate_by_name() -> None:
    """SDK maliyet bildirmez: tahmin yazılır ve kayıt "estimated" diye adlandırılır."""
    client = FakeBatteryJev(cost_usd=0.0, cost_basis=COST_UNPRICED)
    ledger = MemorySpendLedger()

    answer = _budgeted(client, ledger, estimate=0.02).ask_battery({}, QUESTIONS)

    assert (answer.cost_usd, answer.cost_basis) == (0.02, COST_ESTIMATED)
    assert ledger.entries == (SpendEntry(NOW, "battery", 0.02, COST_ESTIMATED, None, None),)


def test_a_call_that_would_cross_the_cap_is_not_made_and_not_recorded() -> None:
    client = FakeBatteryJev()
    ledger = MemorySpendLedger((_entry(NOW - timedelta(days=1), 0.99),))

    with pytest.raises(BudgetExceeded, match="çağrı yapılmadı"):
        _budgeted(client, ledger, cap=1.0, estimate=0.02).ask_battery({}, QUESTIONS)

    assert client.seen == []
    assert len(ledger.entries) == 1


def test_landing_exactly_on_the_cap_is_allowed() -> None:
    """Spec §9: "ayın toplamı + tahmini maliyet ≤ $25" — eşitlik geçer."""
    client = FakeBatteryJev(cost_usd=0.25)
    ledger = MemorySpendLedger((_entry(NOW, 0.75),))

    _budgeted(client, ledger, cap=1.0, estimate=0.25).ask_battery({}, QUESTIONS)

    assert len(client.seen) == 1


def test_repeated_calls_stop_at_the_first_call_that_would_cross_the_cap() -> None:
    client = FakeBatteryJev(cost_usd=0.02)
    ledger = MemorySpendLedger()
    budgeted = _budgeted(client, ledger, cap=0.05, estimate=0.02)

    budgeted.ask_battery({}, QUESTIONS)
    budgeted.ask_battery({}, QUESTIONS)
    with pytest.raises(BudgetExceeded):
        budgeted.ask_battery({}, QUESTIONS)

    assert len(client.seen) == 2
    assert ledger.month_total(NOW) == pytest.approx(0.04)


def test_last_months_spend_does_not_count_against_this_month() -> None:
    client = FakeBatteryJev()
    ledger = MemorySpendLedger((_entry(datetime(2026, 8, 31, 23, 0, tzinfo=UTC), 25.0),))

    _budgeted(client, ledger, cap=MONTHLY_CAP_USD).ask_battery({}, QUESTIONS)

    assert len(client.seen) == 1


def test_a_failed_call_is_recorded_at_the_estimate_and_the_error_propagates() -> None:
    client = FakeBatteryJev(error=TimeoutError("jev zaman aşımı"))
    ledger = MemorySpendLedger()

    with pytest.raises(TimeoutError, match="zaman aşımı"):
        _budgeted(client, ledger, estimate=0.02).ask_battery({}, QUESTIONS)

    assert ledger.entries == (SpendEntry(NOW, "battery_failed", 0.02, COST_ESTIMATED, None, None),)


def test_an_invalid_battery_is_rejected_before_the_guard_and_is_not_recorded() -> None:
    client = FakeBatteryJev()
    ledger = MemorySpendLedger()

    with pytest.raises(ValueError, match="boş batarya"):
        _budgeted(client, ledger).ask_battery({}, ())

    assert client.seen == []
    assert ledger.entries == ()


def test_ask_choice_is_budgeted_too_and_recorded_at_the_estimate() -> None:
    """`map-entities`/`calibrate` da aynı sarmalayıcıdan geçebilir; ask_choice maliyet taşımaz."""
    client = FakeJev(answer=ChoiceAnswer("GS", 0.9, {"GS": 0.9}))
    ledger = MemorySpendLedger()

    answer = _budgeted(client, ledger, estimate=0.01).ask_choice({}, "hangisi?", {"GS": "GS"})

    assert answer.choice == "GS"
    assert ledger.entries == (SpendEntry(NOW, "choice", 0.01, COST_ESTIMATED, None, None),)


@pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, math.inf])
def test_budgeted_jev_rejects_a_cap_or_estimate_that_would_disable_the_guard(bad: float) -> None:
    with pytest.raises(ValueError, match="estimate_usd"):
        BudgetedJev(
            FakeBatteryJev(), MemorySpendLedger(), cap_usd=1.0, estimate_usd=bad, clock=lambda: NOW
        )
    with pytest.raises(ValueError, match="cap_usd"):
        BudgetedJev(
            FakeBatteryJev(), MemorySpendLedger(), cap_usd=bad, estimate_usd=0.01, clock=lambda: NOW
        )


# ── PostgresSpendLedger: sahte bağlantı ─────────────────────────────────────


@dataclass
class _Cursor:
    conn: _Conn

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.conn.executed = [*self.conn.executed, (" ".join(sql.split()), params)]

    def fetchone(self) -> tuple[Any, ...] | None:
        return (self.conn.total,)


@dataclass
class _Conn:
    autocommit: bool = True
    total: Decimal = Decimal("0")
    executed: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def cursor(self) -> _Cursor:
        return _Cursor(self)


def test_postgres_ledger_sums_the_utc_month_and_returns_a_float() -> None:
    conn = _Conn(total=Decimal("3.1400"))

    total = PostgresSpendLedger(conn).month_total(NOW)  # type: ignore[arg-type]

    assert total == 3.14 and isinstance(total, float)
    sql, params = conn.executed[0]
    assert sql == (
        "SELECT coalesce(sum(cost_usd), 0) FROM jev_spend WHERE spent_at >= %s AND spent_at < %s"
    )
    assert params == (datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 10, 1, tzinfo=UTC))


def test_postgres_ledger_inserts_one_row_per_record() -> None:
    conn = _Conn()

    PostgresSpendLedger(conn).record(  # type: ignore[arg-type]
        at=NOW,
        kind="battery",
        cost_usd=0.02,
        cost_basis=COST_ESTIMATED,
        input_tokens=120,
        output_tokens=7,
    )

    sql, params = conn.executed[0]
    assert sql.startswith("INSERT INTO jev_spend (spent_at, kind, cost_usd, cost_basis,")
    assert params == (NOW, "battery", 0.02, COST_ESTIMATED, 120, 7)


# ── Review Focus ─────────────────────────────────────────────────────────────


def test_review_focus_postgres_ledger_refuses_a_transactional_connection() -> None:
    """Harcama kaydı çağıranın işlemine binerse, sonraki bir rollback yapılmış çağrıyı siler."""
    with pytest.raises(ValueError, match="autocommit"):
        PostgresSpendLedger(_Conn(autocommit=False))  # type: ignore[arg-type]


def test_review_focus_a_non_utc_clock_is_bucketed_by_the_utc_month() -> None:
    """İstanbul 1 Ekim 01:30 = UTC 30 Eylül 22:30: eylül harcaması o çağrıyı durdurmalı."""
    istanbul = timezone(timedelta(hours=3))
    late_night = datetime(2026, 10, 1, 1, 30, tzinfo=istanbul)
    ledger = MemorySpendLedger((_entry(datetime(2026, 9, 15, tzinfo=UTC), 24.99),))

    with pytest.raises(BudgetExceeded):
        _budgeted(FakeBatteryJev(), ledger, cap=MONTHLY_CAP_USD, now=late_night).ask_battery(
            {}, QUESTIONS
        )


def test_review_focus_nan_cost_never_reaches_the_ledger() -> None:
    """NaN toplamda kalırsa `NaN + tahmin > tavan` hep False: tavan sessizce kalkar."""
    ledger = MemorySpendLedger()

    for bad in (math.nan, math.inf, -0.01):
        with pytest.raises(ValueError, match="cost_usd"):
            ledger.record(at=NOW, kind="battery", cost_usd=bad)

    assert ledger.entries == ()
