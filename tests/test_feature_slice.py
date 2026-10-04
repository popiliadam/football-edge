"""Seçim dilimi sayacı (Plan 2 R181): küme başına sayım, haftalık hız, 900'e varış; mühür."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.slice import (
    RATE_WINDOW,
    SLICE_SQL,
    TARGET,
    eta_for,
    select_slice_rows,
    slice_lines,
)
from football_edge.features.tier2 import ASKED, NO_NEWS, status_question
from football_edge.features.types import HOME
from tests.fake_tier2_db import FakeTier2Db

NOW = datetime(2026, 10, 9, 13, 0, tzinfo=UTC)
D = NOW - timedelta(days=3)
A, B, C = "a" * 64, "b" * 64, "c" * 64


def _answer(
    match_id: str, decided_at: datetime, variant: str = "real", outcome: str = ASKED
) -> dict[str, Any]:
    """Yalnız bir tarafın durum işareti: sayaç cevap İÇERİĞİNE bakmaz (R181, I5)."""
    question_id = status_question(HOME, outcome)
    return {
        "match_id": match_id,
        "decided_at": decided_at,
        "prompt_version": A,
        "variant": variant,
        "question_id": question_id,
    }


@pytest.mark.leakage
def test_the_slice_query_reads_no_answer_content_probability_or_result() -> None:
    """R181: sayaç sonuç, kapanış, olasılık ya da cevap içeriği OKUMAZ — yalnız var olma."""
    text = SLICE_SQL.lower()
    forbidden = ("probabilities", "choice", "confidence", "p_home", "p_draw", "p_away", "pre_")
    for word in (*forbidden, "odds_snapshots", "closing", "result"):
        assert word not in text, word
    assert "exists (" in text and "from model_predictions" in text
    assert "a.question_id = any(%s)" in text, "yalnız `asked` işareti sayılır (haberli karar)"
    assert "p.match_id = a.match_id and p.decided_at = a.decided_at" in text, "aynı karar anı"
    assert "a.variant = %s" in text, "yalnız gerçek varyant (kanarya arşivi sayılmaz)"
    assert "p.strategy = any(%s)" in text, "yalnız baz gölge stratejileri"


@pytest.mark.leakage
def test_only_asked_decisions_with_a_base_shadow_row_are_counted() -> None:
    db = FakeTier2Db()
    db.match_answers = [
        _answer("m1", D),
        _answer("m1", D),
        _answer("m2", D),
        _answer("m3", D),
        _answer("m4", D, variant="blank"),
        _answer("m5", D, outcome=NO_NEWS),
    ]
    db.predictions = [
        ("m1", "market", D),
        ("m3", "harman_jev", D),
        ("m4", "market", D),
        ("m5", "market", D),
    ]

    assert select_slice_rows(db) == ((A, "m1", D),)  # type: ignore[arg-type]


def test_sets_are_counted_separately_and_the_current_set_shows_at_zero() -> None:
    rows = [(A, f"m{n}", NOW - timedelta(days=n)) for n in range(1, 9)]
    rows.append((B, "x", NOW - timedelta(days=60)))

    lines = slice_lines(rows, now=NOW, current=C)

    assert [(x.prompt_version, x.count, x.current) for x in lines] == [
        (A, 8, False),
        (B, 1, False),
        (C, 0, True),
    ]
    assert lines[0].weekly_rate == pytest.approx(2.0)  # 8 karar / 4 hafta
    assert (lines[1].weekly_rate, lines[1].eta) == (0.0, None)


def test_the_eta_is_the_weeks_left_at_the_current_rate() -> None:
    today = date(2026, 10, 9)

    assert eta_for(300, 30.0, today=today) == today + timedelta(days=140)
    assert eta_for(0, 0.0, today=today) is None
    assert eta_for(TARGET, 0.0, today=today) == today
    # Kesirli gün yukarı yuvarlanır: 1 karar ÷ haftada 3 = 2,33 gün → 3 gün (inceleme M5).
    assert eta_for(TARGET - 1, 3.0, today=today) == today + timedelta(days=3)


def test_the_rate_window_starts_just_after_its_edge() -> None:
    """Hız penceresi `(now − 28 gün, now]`: tam kenardaki karar hıza girmez, bir saniye sonraki
    girer; ikisi de sayılır (inceleme M4)."""
    edge = NOW - RATE_WINDOW
    rows = [(A, "m1", edge), (A, "m2", edge + timedelta(seconds=1))]

    (line,) = slice_lines(rows, now=NOW, current=None)

    assert (line.count, line.weekly_rate) == (2, pytest.approx(0.25))


def test_slice_status_appends_to_the_summary_inside_a_read_only_transaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = FakeTier2Db()
    db.match_answers = [_answer("m1", D)]
    db.predictions = [("m1", "market", D)]
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    out = tmp_path / "summary.md"
    out.write_text("önceki\n", encoding="utf-8")

    assert cli.main(["slice-status", "--out", str(out)]) == 0

    text = out.read_text(encoding="utf-8")
    assert text.startswith("önceki\n") and f"1 / {TARGET}" in text and "(geçerli küme)" in text
    assert db.statements[0] == "SET TRANSACTION READ ONLY"


def test_slice_status_without_the_set_file_still_counts_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Küme dosyası okunamazsa sayaç KOŞAR (exit 0), geçerli küme işaretsizdir; log "koşulmadı"
    demez (inceleme 6)."""
    db = FakeTier2Db()
    db.match_answers = [_answer("m1", D)]
    db.predictions = [("m1", "market", D)]
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: NOW)

    with caplog.at_level(logging.INFO):
        code = cli.main(["slice-status", "--live-config", str(tmp_path / "yok.yaml")])

    out = capsys.readouterr().out
    assert code == 0 and f"1 / {TARGET}" in out and "(geçerli küme)" not in out
    assert "koşulmadı" not in caplog.text and "geçerli küme işaretsiz" in caplog.text
