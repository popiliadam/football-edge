"""Tarihsel taban kilidi (tasarım §5.2, D8; kanonik satır: Ruling R86).

Kanonik satırın biçimi burada harfiyen sabitlenir: biçim değişirse `CANONICAL_VERSION` artar ve
kilit yeniden üretilir. Holdout özeti anahtarsız hesaplanır ama satırlar dışarı çıkmaz;
`verify_lock` farkların hepsini tek istisnada söyler. Takım adları sentetiktir.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.history.holdout import DEV, DEV_END, HOLDOUT, HOLDOUT_END
from football_edge.history.lock import (
    CANONICAL_VERSION,
    Digest,
    HistoryLock,
    LockViolation,
    build_lock,
    canonical_line,
    digest,
    dump_lock,
    load_lock,
    verify_lock,
)
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, HistMatch, OddsKey

AVGC = {
    OddsKey("Avg", H2H, "H", CLOSING): 1.95,
    OddsKey("Avg", H2H, "D", CLOSING): 3.6,
    OddsKey("Avg", H2H, "A", CLOSING): 4.2,
}
PRE_HOME = {OddsKey("Avg", H2H, "H", PRE_CLOSING): 2.0}
BASE = HistMatch(
    league="E0",
    season="2425",
    date=dt.date(2025, 3, 15),
    kickoff=dt.datetime(2025, 3, 15, 15, 0, tzinfo=dt.UTC),
    home="Ev A",
    away="Deplasman B",
    home_goals=2,
    away_goals=1,
    result="H",
    odds=MappingProxyType({**AVGC, **PRE_HOME}),
    stats=MappingProxyType({"HS": 12, "AS": 7}),
    source_line=4,
)


def _match(**changes: Any) -> HistMatch:
    return replace(BASE, **changes)


def _described(value: Digest) -> str:
    return f"rows={value.rows} sha256={value.sha256} avgc_complete={value.avgc_complete}"


PARTIAL_AVGC = {key: price for key, price in AVGC.items() if key.outcome != "A"}
# İngiltere tarihi 1 Temmuz, başlama UTC'de 30 Haziran 23:30: dönem Date'ten gelir.
LATE_KICKOFF = dt.datetime(2025, 6, 30, 23, 30, tzinfo=dt.UTC)
E0_DEV = _match()
E0_DEV_PARTIAL = _match(
    date=dt.date(2025, 6, 30), home="Ev C", away="Deplasman D", odds=MappingProxyType(PARTIAL_AVGC)
)
E0_HOLDOUT = _match(
    season="2526", date=dt.date(2025, 7, 1), kickoff=LATE_KICKOFF, home="Ev E", away="Deplasman F"
)
E0_POST = _match(
    season="2627", date=dt.date(2026, 7, 1), kickoff=None, home="Ev G", away="Deplasman H"
)
E0 = (E0_DEV, E0_DEV_PARTIAL, E0_HOLDOUT)
SP1 = (_match(league="SP1", home="Ev I", away="Deplasman J"),)
F1 = (_match(league="F1", home="Ev K", away="Deplasman L"),)
LOCKED_AT = dt.date(2026, 10, 6)


# ── Kanonik satır ──────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_canonical_line_is_exactly_the_documented_layout() -> None:
    """Oranlar OddsKey, istatistikler ad sırasıyla — eşlemelerin ekleme sırası değil."""
    assert CANONICAL_VERSION == 1
    assert canonical_line(BASE) == "\t".join(
        [
            "E0",
            "2425",
            "2025-03-15",
            "2025-03-15T15:00:00+00:00",
            "Ev A",
            "Deplasman B",
            "2",
            "1",
            "H",
            "Avg|1x2|A|close=4.2",
            "Avg|1x2|D|close=3.6",
            "Avg|1x2|H|close=1.95",
            "Avg|1x2|H|pre=2.0",
            "AS=7",
            "HS=12",
        ]
    )


@pytest.mark.leakage
def test_canonical_line_writes_the_kickoff_in_utc() -> None:
    plus_one = dt.timezone(dt.timedelta(hours=1))
    shifted = _match(kickoff=dt.datetime(2025, 3, 15, 16, 0, tzinfo=plus_one))

    assert canonical_line(shifted) == canonical_line(BASE)


@pytest.mark.leakage
def test_canonical_line_leaves_an_unknown_kickoff_empty() -> None:
    assert canonical_line(_match(kickoff=None)).split("\t")[3] == ""


@pytest.mark.leakage
@pytest.mark.parametrize(
    "changes",
    [
        {"league": "E1"},
        {"season": "2324"},
        {"date": dt.date(2025, 3, 16)},
        {"kickoff": dt.datetime(2025, 3, 15, 17, 30, tzinfo=dt.UTC)},
        {"home": "Ev Z"},
        {"away": "Deplasman Z"},
        {"home_goals": 3},
        {"away_goals": 0},
        {"result": "D"},
        {"odds": MappingProxyType({**AVGC, **PRE_HOME, OddsKey("Avg", H2H, "H", CLOSING): 1.96})},
        {"odds": MappingProxyType(AVGC)},
        {"stats": MappingProxyType({"HS": 13, "AS": 7})},
        {"stats": MappingProxyType({"HS": 12})},
    ],
    ids=[
        "league",
        "season",
        "date",
        "kickoff",
        "home",
        "away",
        "home_goals",
        "away_goals",
        "result",
        "price",
        "odds-key",
        "stat-value",
        "stat-key",
    ],
)
def test_canonical_line_changes_when_any_locked_value_changes(changes: dict[str, Any]) -> None:
    assert canonical_line(_match(**changes)) != canonical_line(BASE)


@pytest.mark.leakage
def test_canonical_line_ignores_the_source_line() -> None:
    assert canonical_line(_match(source_line=99)) == canonical_line(BASE)


@pytest.mark.leakage
@pytest.mark.parametrize(
    "changes",
    [
        {"kickoff": dt.datetime(2025, 3, 15, 15, 0)},
        {"home": "Ev\tA"},
        {"away": "Deplasman\nB"},
    ],
    ids=["naive-kickoff", "tab", "newline"],
)
def test_canonical_line_rejects_values_that_would_blur_the_digest(changes: dict[str, Any]) -> None:
    """Saat dilimsiz başlama özeti makinenin yerel saatine bağlardı; ayraç içeren bir değer iki
    farklı veriyi aynı metne indirebilirdi."""
    with pytest.raises(ValueError):
        canonical_line(_match(**changes))


# ── Özet ───────────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_digest_is_sha256_of_the_sorted_newline_joined_lines() -> None:
    lines = sorted([canonical_line(E0_DEV), canonical_line(E0_DEV_PARTIAL)])
    expected = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    reverse_sorted = sorted([E0_DEV, E0_DEV_PARTIAL], key=canonical_line, reverse=True)

    assert digest(reverse_sorted).sha256 == expected


@pytest.mark.leakage
def test_digest_ignores_match_order() -> None:
    assert digest([E0_DEV, E0_DEV_PARTIAL, E0_HOLDOUT]) == digest(
        [E0_HOLDOUT, E0_DEV, E0_DEV_PARTIAL]
    )


@pytest.mark.leakage
def test_digest_counts_rows_and_complete_avgc_1x2() -> None:
    """Yalnız AvgC 1X2'si tam satır sayılır: kapanış öncesi Avg, eksik sonuç ya da başka kitap
    sayılmaz."""
    pre_only = _match(
        home="Ev M",
        odds=MappingProxyType({OddsKey("Avg", H2H, side, PRE_CLOSING): 2.9 for side in "HDA"}),
    )
    max_close = _match(
        home="Ev N",
        odds=MappingProxyType({OddsKey("Max", H2H, side, CLOSING): 3.1 for side in "HDA"}),
    )

    result = digest([E0_DEV, E0_HOLDOUT, E0_DEV_PARTIAL, pre_only, max_close])

    assert (result.rows, result.avgc_complete) == (5, 2)


@pytest.mark.leakage
def test_digest_of_no_matches_is_the_empty_sha256() -> None:
    assert digest([]) == Digest(rows=0, sha256=hashlib.sha256(b"").hexdigest(), avgc_complete=0)


# ── Kilit kurma ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_build_lock_splits_by_source_date_and_leaves_post_out() -> None:
    lock = build_lock({"E0": (*E0, E0_POST)}, locked_at=LOCKED_AT)

    assert dict(lock.leagues["E0"]) == {
        DEV: digest([E0_DEV, E0_DEV_PARTIAL]),
        HOLDOUT: digest([E0_HOLDOUT]),
    }


@pytest.mark.leakage
def test_build_lock_records_the_code_constants() -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)

    assert (lock.canonical_version, lock.locked_at, lock.dev_end, lock.holdout_end) == (
        CANONICAL_VERSION,
        LOCKED_AT,
        DEV_END,
        HOLDOUT_END,
    )


@pytest.mark.leakage
def test_lock_cannot_be_modified_after_it_is_built() -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)

    with pytest.raises(TypeError):
        lock.leagues["E0"][DEV] = Digest(0, "0" * 64, 0)  # type: ignore[index]


# ── Dosya ───────────────────────────────────────────────────────────────────────────────────

LOCK = HistoryLock(
    canonical_version=CANONICAL_VERSION,
    locked_at=LOCKED_AT,
    dev_end=DEV_END,
    holdout_end=HOLDOUT_END,
    leagues=MappingProxyType(
        {
            "SP1": MappingProxyType({DEV: Digest(3, "c" * 64, 1), HOLDOUT: Digest(1, "d" * 64, 1)}),
            "E0": MappingProxyType({HOLDOUT: Digest(2, "b" * 64, 2), DEV: Digest(5, "a" * 64, 4)}),
        }
    ),
)


@pytest.mark.leakage
def test_dump_lock_writes_the_documented_text() -> None:
    """Lig kodları sıralı, anahtar sırası sabit; başlık içerik taşımadığını ve değişikliğin
    gerekçeli commit olduğunu söyler."""
    header, body = dump_lock(LOCK).split("canonical_version:", 1)

    assert header.splitlines(), "başlık yorumu yok"
    assert all(line.startswith("# ") for line in header.splitlines())
    assert "İÇERİK TAŞIMAZ" in header and "gerekçeli bir commit" in header
    assert "canonical_version:" + body == "\n".join(
        [
            "canonical_version: 1",
            "locked_at: 2026-10-06",
            "dev_end: 2025-07-01",
            "holdout_end: 2026-07-01",
            "leagues:",
            "  E0:",
            "    dev:",
            "      rows: 5",
            f"      sha256: {'a' * 64}",
            "      avgc_complete: 4",
            "    holdout:",
            "      rows: 2",
            f"      sha256: {'b' * 64}",
            "      avgc_complete: 2",
            "  SP1:",
            "    dev:",
            "      rows: 3",
            f"      sha256: {'c' * 64}",
            "      avgc_complete: 1",
            "    holdout:",
            "      rows: 1",
            f"      sha256: {'d' * 64}",
            "      avgc_complete: 1",
            "",
        ]
    )


@pytest.mark.leakage
def test_dump_then_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "history_lock.yaml"
    path.write_text(dump_lock(LOCK), encoding="utf-8")

    assert load_lock(path) == LOCK


@pytest.mark.leakage
def test_dumped_lock_carries_no_match_content() -> None:
    text = dump_lock(build_lock({"E0": E0, "SP1": SP1}, locked_at=LOCKED_AT))

    assert not [name for match in (*E0, *SP1) for name in (match.home, match.away) if name in text]


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("canonical_version: 1", "canonical_version: 2", "canonical_version"),
        ("canonical_version: 1", "canonical_version: true", "canonical_version"),
        (f"sha256: {'a' * 64}", f"sha256: {'a' * 63}", "sha256"),
        (f"sha256: {'a' * 64}", f"sha256: {'A' * 64}", "sha256"),
        ("rows: 5", "rows: -5", "rows"),
        ("rows: 5", "rows: true", "rows"),
        ("avgc_complete: 4", "avgc_complete: 6", "avgc_complete"),
        ("locked_at: 2026-10-06", "locked_at: 2026-10-06 12:00:00", "locked_at"),
        ("  SP1:\n    dev:", "  SP1:\n    post:", "SP1"),
        ("leagues:\n", "locked_by: x\nleagues:\n", "bilinmeyen"),
        ("holdout_end: 2026-07-01\n", "", "eksik alan ['holdout_end']"),
        ("leagues:\n", "leagues: [\n", "okunamıyor"),
        ("rows: 5", "rows: !!python/object/apply:builtins.int ['5']", "okunamıyor"),
    ],
    ids=[
        "version",
        "version-bool",
        "short-sha",
        "upper-sha",
        "negative-rows",
        "bool-rows",
        "coverage-above-rows",
        "datetime",
        "unknown-period",
        "unknown-key",
        "missing-key",
        "broken-yaml",
        "python-tag",
    ],
)
def test_load_lock_rejects_malformed_files(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    """R99: her yapı ve biçim hatası dosyayı adıyla anan TEK farklı bir LockViolation'dır —
    kilidi okuyan CLI'lar veri farkıyla aynı çıkışı (9) verir, traceback değil. Python etiketi
    de biçim hatasıdır: kilit güvenli yükleyiciyle okunur, dosya nesne kurup kod çalıştıramaz."""
    text = dump_lock(LOCK)
    assert old in text, "değişiklik metne uymuyor — test kurgusu bayatlamış"
    path = tmp_path / "history_lock.yaml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

    with pytest.raises(LockViolation, match=re.escape(message)) as caught:
        load_lock(path)

    (difference,) = caught.value.differences
    assert str(path) in difference


@pytest.mark.leakage
def test_load_lock_reports_an_undecodable_file_as_a_violation(tmp_path: Path) -> None:
    path = tmp_path / "history_lock.yaml"
    path.write_bytes(dump_lock(LOCK).encode("utf-8").replace(b"# ", b"# \xff", 1))

    with pytest.raises(LockViolation, match="okunamıyor"):
        load_lock(path)


# ── Doğrulama ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_verify_lock_accepts_unchanged_data_in_any_order_and_new_post_rows() -> None:
    lock = build_lock({"E0": E0, "SP1": SP1}, locked_at=LOCKED_AT)

    verify_lock(lock, {"SP1": SP1, "E0": (E0_POST, *reversed(E0))})


@pytest.mark.leakage
@pytest.mark.parametrize(("index", "period"), [(0, DEV), (2, HOLDOUT)], ids=["dev", "holdout"])
def test_verify_lock_reports_a_corrected_score_in_each_locked_period(
    index: int, period: str
) -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)
    corrected = tuple(
        replace(match, home_goals=3) if position == index else match
        for position, match in enumerate(E0)
    )
    actual = build_lock({"E0": corrected}, locked_at=LOCKED_AT).leagues["E0"][period]

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": corrected})

    expected = lock.leagues["E0"][period]
    assert caught.value.differences == (
        f"E0/{period}: beklenen {_described(expected)} · gerçek {_described(actual)}",
    )


@pytest.mark.leakage
def test_verify_lock_reports_a_removed_row() -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)

    with pytest.raises(LockViolation, match=r"E0/dev: beklenen rows=2 .* gerçek rows=1 "):
        verify_lock(lock, {"E0": E0[1:]})


@pytest.mark.leakage
def test_verify_lock_reports_a_league_absent_from_the_lock() -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": E0, "F1": F1})

    assert caught.value.differences == ("F1: veride var, kilitte yok",)


@pytest.mark.leakage
def test_verify_lock_reports_a_locked_league_missing_from_the_data() -> None:
    lock = build_lock({"E0": E0, "SP1": SP1}, locked_at=LOCKED_AT)

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": E0})

    assert caught.value.differences == ("SP1: kilitte var, veride yok",)


@pytest.mark.leakage
def test_verify_lock_reports_a_period_missing_from_the_lock() -> None:
    built = build_lock({"E0": E0}, locked_at=LOCKED_AT)
    dev_only = MappingProxyType({DEV: built.leagues["E0"][DEV]})

    with pytest.raises(LockViolation) as caught:
        verify_lock(replace(built, leagues=MappingProxyType({"E0": dev_only})), {"E0": E0})

    actual = _described(built.leagues["E0"][HOLDOUT])
    assert caught.value.differences == (f"E0/holdout: beklenen yok · gerçek {actual}",)


@pytest.mark.leakage
def test_verify_lock_reports_moved_boundaries_and_a_foreign_version() -> None:
    lock = replace(
        build_lock({"E0": E0}, locked_at=LOCKED_AT),
        canonical_version=2,
        dev_end=dt.date(2025, 6, 30),
        holdout_end=dt.date(2026, 7, 2),
    )

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": E0})

    assert caught.value.differences == (
        "canonical_version: kilit 2, kod 1",
        "dev_end: kilit 2025-06-30, kod 2025-07-01",
        "holdout_end: kilit 2026-07-02, kod 2026-07-01",
    )


@pytest.mark.leakage
def test_verify_lock_lists_every_difference_in_one_violation() -> None:
    lock = replace(
        build_lock({"E0": E0, "SP1": SP1}, locked_at=LOCKED_AT), dev_end=dt.date(2025, 6, 30)
    )
    corrected = replace(E0_DEV, away_goals=0)

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": (corrected, *E0[1:]), "F1": F1})

    before = lock.leagues["E0"][DEV]
    after = digest([corrected, E0_DEV_PARTIAL])
    assert caught.value.differences == (
        "dev_end: kilit 2025-06-30, kod 2025-07-01",
        f"E0/dev: beklenen {_described(before)} · gerçek {_described(after)}",
        "F1: veride var, kilitte yok",
        "SP1: kilitte var, veride yok",
    )
    assert str(caught.value).splitlines()[1:] == list(caught.value.differences)
