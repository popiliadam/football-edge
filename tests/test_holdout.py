"""Dönemler, pencereler ve holdout anahtarı (tasarım §5.1, §5.3; D2, D8).

Holdout'un tek kapısı `select_periods`tir ve anahtarı yalnız `open_holdout` kurar; açılış
`holdout_access_log`a commit'lenmeden anahtar dönmez. Veritabanı sahte bir bağlantıyla taklit
edilir; migration metin üzerinden sınanır (gerçek veritabanı testi yok).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.history.holdout import (
    DEV,
    DEV_END,
    EXTRA_WINDOW,
    HOLDOUT,
    HOLDOUT_END,
    MAIN_WINDOW,
    POST,
    HoldoutKey,
    HoldoutLocked,
    Window,
    in_window,
    open_holdout,
    period_of,
    select_periods,
)
from football_edge.history.types import HistMatch
from tests.workflow_helpers import MIGRATIONS

SHA = "0123456789abcdef0123456789abcdef01234567"
NOW = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.UTC)
PURPOSE = "Faz 3 kapısı: önceden yazılmış karşılaştırma"


class InsertFailed(Exception):
    """INSERT düştü (bağlantı koptu ya da kısıt ihlali)."""


class CommitFailed(Exception):
    """COMMIT düştü, bağlantı ayakta — `tests/fake_db.py:CommitFailed` deseni."""


@dataclass
class FakeAccessLogDb:
    """`holdout_access_log` taklidi: bekleyen satırlar yalnız commit'le kalıcı olur, rollback
    onları atar. INSERT dışındaki her ifade reddedilir — açılış maç verisi okumaz."""

    fail_insert: bool = False
    fail_commit: bool = False
    statements: list[tuple[str, Any]] = field(default_factory=list)
    pending: list[Any] = field(default_factory=list)
    committed: list[Any] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0

    def cursor(self) -> _AccessCursor:
        return _AccessCursor(self)

    def commit(self) -> None:
        if self.fail_commit:
            raise CommitFailed("COMMIT düştü, bağlantı ayakta")
        self.commits += 1
        self.committed = [*self.committed, *self.pending]
        self.pending = []

    def rollback(self) -> None:
        self.rollbacks += 1
        self.pending = []


class _AccessCursor:
    def __init__(self, db: FakeAccessLogDb) -> None:
        self._db = db

    def __enter__(self) -> _AccessCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        self._db.statements = [*self._db.statements, (text, params)]
        if not text.startswith("INSERT INTO holdout_access_log"):
            raise AssertionError(f"taklit veritabanı bu sorguyu tanımıyor: {text}")
        if self._db.fail_insert:
            raise InsertFailed("INSERT düştü")
        self._db.pending = [*self._db.pending, params]


def _match(day: dt.date, *, kickoff: dt.datetime | None = None, home: str = "Ev A") -> HistMatch:
    return HistMatch(
        league="E0",
        season="2425",
        date=day,
        kickoff=kickoff,
        home=home,
        away="Deplasman B",
        home_goals=1,
        away_goals=1,
        result="D",
        odds=MappingProxyType({}),
        stats=MappingProxyType({}),
        source_line=1,
    )


# İngiltere tarihi 1 Temmuz, başlama UTC'de 30 Haziran 23:30 (00:30 BST): dönem Date'ten gelir.
LATE_KICKOFF = dt.datetime(2025, 6, 30, 23, 30, tzinfo=dt.UTC)
DEV_MATCH = _match(dt.date(2025, 6, 30), home="Ev A")
FIRST_HOLDOUT = _match(dt.date(2025, 7, 1), kickoff=LATE_KICKOFF, home="Ev B")
LAST_HOLDOUT = _match(dt.date(2026, 6, 30), home="Ev C")
POST_MATCH = _match(dt.date(2026, 7, 1), home="Ev D")
MATCHES = (POST_MATCH, DEV_MATCH, LAST_HOLDOUT, FIRST_HOLDOUT)  # kasıtlı olarak sırasız


# ── Dönemler ve pencereler ────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_period_constants_are_the_approved_boundaries() -> None:
    assert (dt.date(2025, 7, 1), dt.date(2026, 7, 1)) == (DEV_END, HOLDOUT_END)
    assert (DEV, HOLDOUT, POST) == ("dev", "holdout", "post")


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("day", "period"),
    [
        (dt.date(2012, 3, 1), DEV),
        (dt.date(2025, 6, 30), DEV),
        (dt.date(2025, 7, 1), HOLDOUT),
        (dt.date(2026, 6, 30), HOLDOUT),
        (dt.date(2026, 7, 1), POST),
        (dt.date(2026, 9, 20), POST),
    ],
)
def test_period_follows_the_source_date_at_every_boundary(day: dt.date, period: str) -> None:
    assert period_of(day) == period


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("day", "inside"),
    [
        (dt.date(2019, 6, 30), False),
        (dt.date(2019, 7, 1), True),
        (dt.date(2025, 6, 30), True),
        (dt.date(2025, 7, 1), False),
    ],
)
def test_main_window_is_half_open_from_2019_07_01_to_dev_end(day: dt.date, inside: bool) -> None:
    assert in_window(_match(day), MAIN_WINDOW) is inside


@pytest.mark.leakage
def test_extra_window_has_no_lower_bound_and_stops_at_dev_end() -> None:
    assert in_window(_match(dt.date(2012, 3, 25)), EXTRA_WINDOW)
    assert not in_window(_match(DEV_END), EXTRA_WINDOW)


@pytest.mark.leakage
def test_window_membership_uses_the_source_date_not_the_kickoff() -> None:
    assert not in_window(FIRST_HOLDOUT, MAIN_WINDOW)
    assert not in_window(FIRST_HOLDOUT, EXTRA_WINDOW)


@pytest.mark.leakage
def test_approved_windows_construct_with_their_documented_bounds() -> None:
    assert Window(dt.date(2019, 7, 1), DEV_END) == MAIN_WINDOW
    assert Window(None, DEV_END) == EXTRA_WINDOW


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("start", "end"),
    [
        (None, HOLDOUT_END),
        (dt.date(2025, 1, 1), dt.date(2026, 1, 1)),
        (None, dt.date(2025, 7, 2)),
    ],
    ids=["open-start-to-holdout-end", "across-dev-end", "one-day-past-dev-end"],
)
def test_window_reaching_past_dev_end_is_rejected(start: dt.date | None, end: dt.date) -> None:
    """R89: `in_window` anahtar sormaz; holdout'a uzanan pencere hiç kurulamamalı."""
    with pytest.raises(ValueError, match="holdout'a uzanamaz"):
        Window(start, end)


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("start", "end"),
    [(dt.date(2020, 1, 1), dt.date(2020, 1, 1)), (dt.date(2021, 1, 1), dt.date(2020, 1, 1))],
    ids=["empty", "reversed"],
)
def test_window_with_start_not_before_end_is_rejected(start: dt.date, end: dt.date) -> None:
    with pytest.raises(ValueError, match="boş pencere"):
        Window(start, end)


# Dönem sınırları, çevreleri ve iki uç: kurulabilen ve kurulamayan pencereleri birlikte üretir.
GRID_DAYS = (
    dt.date.min,
    dt.date(2019, 7, 1),
    dt.date(2025, 6, 30),
    DEV_END,
    dt.date(2025, 7, 2),
    dt.date(2026, 1, 1),
    HOLDOUT_END,
    dt.date(2026, 9, 20),
    dt.date.max,
)
MIXED = (*MATCHES, _match(dt.date(2012, 3, 1), home="Ev E"), _match(dt.date(2026, 9, 20)))


def _constructible(start: dt.date | None, end: dt.date) -> Window | None:
    try:
        return Window(start, end)
    except ValueError:
        return None


@pytest.mark.leakage
def test_no_constructible_window_returns_a_holdout_or_later_match() -> None:
    """R89'un özelliği: kurulabilen HER pencere yalnız geliştirme maçı seçer. Izgaranın iki yanı
    da denediği (kurulan ve reddedilen pencere var) ve boşa seçmediği ayrıca ölçülür."""
    candidates = [(start, end) for start in (None, *GRID_DAYS) for end in GRID_DAYS]
    windows = [window for window in (_constructible(*pair) for pair in candidates) if window]
    leaked = [
        (window, match.date)
        for window in windows
        for match in MIXED
        if in_window(match, window) and period_of(match.date) != DEV
    ]

    assert 0 < len(windows) < len(candidates), "ızgara kurulabilirliğin iki yanını denemiyor"
    assert any(in_window(match, window) for window in windows for match in MIXED)
    assert leaked == [], f"holdout'a ya da sonrasına uzanan pencere: {leaked}"


# ── select_periods ve anahtar ─────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_dev_and_post_need_no_key_and_keep_input_order() -> None:
    assert select_periods(MATCHES, periods=frozenset({DEV, POST})) == (POST_MATCH, DEV_MATCH)


@pytest.mark.leakage
def test_dev_selection_uses_the_source_date_not_the_kickoff() -> None:
    assert select_periods(MATCHES, periods=frozenset({DEV})) == (DEV_MATCH,)


@pytest.mark.leakage
@pytest.mark.parametrize(
    "periods",
    [frozenset({HOLDOUT}), frozenset({DEV, HOLDOUT}), frozenset({HOLDOUT, POST})],
    ids=["holdout", "dev+holdout", "holdout+post"],
)
def test_holdout_without_a_key_is_locked(periods: frozenset[str]) -> None:
    with pytest.raises(HoldoutLocked):
        select_periods(MATCHES, periods=periods)


@pytest.mark.leakage
@pytest.mark.parametrize("seal", [{}, {"_seal": object()}], ids=["no-seal", "foreign-seal"])
def test_hand_built_key_does_not_open_the_holdout(seal: dict[str, object]) -> None:
    forged = HoldoutKey(opened_at=NOW, purpose=PURPOSE, git_sha=SHA, **seal)

    with pytest.raises(HoldoutLocked):
        select_periods(MATCHES, periods=frozenset({HOLDOUT}), key=forged)


@pytest.mark.leakage
def test_key_from_open_holdout_opens_the_holdout_by_source_date() -> None:
    key = open_holdout(FakeAccessLogDb(), purpose=PURPOSE, git_sha=SHA, now=NOW)

    selected = select_periods(MATCHES, periods=frozenset({HOLDOUT}), key=key)

    assert selected == (LAST_HOLDOUT, FIRST_HOLDOUT)


@pytest.mark.leakage
def test_select_periods_rejects_unknown_period_names() -> None:
    with pytest.raises(ValueError, match="bilinmeyen dönem"):
        select_periods(MATCHES, periods=frozenset({"holdot"}))


# ── open_holdout ──────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_open_holdout_commits_one_access_row_before_returning_the_key() -> None:
    db = FakeAccessLogDb()

    key = open_holdout(db, purpose=PURPOSE, git_sha=SHA, now=NOW)

    assert (db.committed, db.pending, db.commits) == ([(NOW, SHA, PURPOSE)], [], 1)
    assert (key.opened_at, key.purpose, key.git_sha) == (NOW, PURPOSE, SHA)


@pytest.mark.leakage
def test_open_holdout_passes_values_as_query_parameters() -> None:
    """Amaç serbest metindir: SQL metnine girerse tırnak içeren bir amaç ifadeyi bozar."""
    purpose = "K3'ün son ölçümü; DROP TABLE"
    db = FakeAccessLogDb()

    open_holdout(db, purpose=purpose, git_sha=SHA, now=NOW)

    ((sql, params),) = db.statements
    assert sql == (
        "INSERT INTO holdout_access_log (opened_at, git_sha, purpose) VALUES (%s, %s, %s)"
    )
    assert params == (NOW, SHA, purpose)


@pytest.mark.leakage
def test_open_holdout_returns_no_key_when_the_insert_fails() -> None:
    db = FakeAccessLogDb(fail_insert=True)

    with pytest.raises(InsertFailed):
        open_holdout(db, purpose=PURPOSE, git_sha=SHA, now=NOW)

    assert (db.committed, db.pending, db.commits, db.rollbacks) == ([], [], 0, 1)


@pytest.mark.leakage
def test_open_holdout_returns_no_key_when_the_commit_fails() -> None:
    db = FakeAccessLogDb(fail_commit=True)

    with pytest.raises(CommitFailed):
        open_holdout(db, purpose=PURPOSE, git_sha=SHA, now=NOW)

    assert (db.committed, db.pending, db.rollbacks) == ([], [], 1)


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"purpose": ""}, "amacı"),
        ({"purpose": "   "}, "amacı"),
        ({"git_sha": SHA.upper()}, "git_sha"),
        ({"git_sha": SHA[:-1]}, "git_sha"),
        ({"git_sha": SHA + "0"}, "git_sha"),
        ({"git_sha": SHA + "\n"}, "git_sha"),
        ({"now": NOW.replace(tzinfo=None)}, "saat dilimli"),
    ],
    ids=["empty", "blank", "upper", "short", "long", "newline", "naive-now"],
)
def test_open_holdout_rejects_bad_openings_before_writing(
    changes: dict[str, Any], message: str
) -> None:
    db = FakeAccessLogDb()
    arguments: dict[str, Any] = {"purpose": PURPOSE, "git_sha": SHA, "now": NOW, **changes}

    with pytest.raises(ValueError, match=message):
        open_holdout(db, **arguments)

    assert db.statements == []


@pytest.mark.leakage
def test_key_is_immutable() -> None:
    key = open_holdout(FakeAccessLogDb(), purpose=PURPOSE, git_sha=SHA, now=NOW)

    with pytest.raises(dataclasses.FrozenInstanceError):
        key.purpose = "başka"  # type: ignore[misc]


# ── Migration 0007 (metin) ────────────────────────────────────────────────────────────────


def _migration_sql() -> str:
    """Yorumsuz, tek boşluklu metin: yoruma alınmış bir satır iddiayı karşılamasın."""
    text = (MIGRATIONS / "0007_holdout.sql").read_text(encoding="utf-8")
    return " ".join(re.sub(r"--[^\n]*", "", text).split())


def _table_columns(sql: str) -> tuple[str, ...]:
    body = re.search(r"create table if not exists holdout_access_log \((.*?)\);", sql)
    assert body is not None, "0007 holdout_access_log tablosunu kurmuyor"
    return tuple(column.strip() for column in body.group(1).split(", "))


@pytest.mark.leakage
def test_access_log_migration_defines_checked_columns() -> None:
    assert _table_columns(_migration_sql()) == (
        "id bigserial primary key",
        "opened_at timestamptz not null",
        "git_sha text not null check (git_sha ~ '^[0-9a-f]{40}$')",
        "purpose text not null check (length(purpose) > 0)",
    )


@pytest.mark.leakage
def test_access_log_migration_is_append_only_with_the_ledger_trigger() -> None:
    """Açılış sayısı ancak kayıt silinemiyorsa kanıttır. Tetikleyici fonksiyonu 0001'in; 0007 onu
    yeniden tanımlamaz (yeniden tanım korumayı sessizce gevşetebilirdi)."""
    sql = _migration_sql()

    assert (
        "create trigger holdout_access_log_append_only before update or delete on "
        "holdout_access_log for each row execute function forbid_ledger_mutation();"
    ) in sql
    assert "create or replace function" not in sql


@pytest.mark.leakage
def test_access_log_migration_blocks_truncate() -> None:
    """Satır tetikleyicisi TRUNCATE'i görmez; bu olmasa sayım tek komutla silinirdi."""
    assert (
        "create trigger holdout_access_log_no_truncate before truncate on holdout_access_log "
        "for each statement execute function forbid_ledger_mutation();"
    ) in _migration_sql()


@pytest.mark.leakage
def test_access_log_migration_closes_the_table_to_api_roles() -> None:
    """R90: RLS açık ve politika yok — API rolleri satır okuyamaz, yazamaz. Hat tablonun sahibi
    olarak RLS'yi atlar; FORCE sahibi de politikaya bağlar ve açılış yazımını durdururdu."""
    sql = _migration_sql()

    assert "alter table holdout_access_log enable row level security;" in sql
    assert "create policy" not in sql
    assert "force row level security" not in sql


@pytest.mark.leakage
def test_open_holdout_writes_exactly_the_migration_columns() -> None:
    """Taklit sütun adını denetlemez: yazım hatasını gerçek veritabanına gitmeden bu yakalar.
    `id` dışındaki her sütun NOT NULL ve varsayılansızdır; hepsi yazılmalı."""
    db = FakeAccessLogDb()
    open_holdout(db, purpose=PURPOSE, git_sha=SHA, now=NOW)
    ((sql, _),) = db.statements
    written = re.search(r"INSERT INTO holdout_access_log \(([^)]*)\)", sql)
    assert written is not None, sql

    defined = [column.split()[0] for column in _table_columns(_migration_sql())]

    assert written.group(1).split(", ") == [name for name in defined if name != "id"]
