"""Kademe 2'nin dondurulmuş kümesi (Plan 2 R185; I-11): `faz4_live.yaml` + `faz4_ops.yaml`."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path

import pytest

from football_edge.features.live_config import (
    TIER1,
    TIER2,
    LiveConfig,
    LiveConfigError,
    frozen_violations,
    live_prompt_version,
    load_live_config,
)
from football_edge.features.questions import load_questions

REPO = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = REPO / "config" / "jev_questions.yaml"
PV = load_questions(QUESTIONS_PATH).prompt_version
LIVE = (
    f"tier1_prompt_version: {PV}\njev_model: jev-2026-10\nmin_belongs: 0.5\nmin_reliability: 0.5\n"
)
OPS = (
    "estimate_usd:\n  tier1: 0.01\n  tier2: 0.02\n"
    "max_sides_per_run: 80\nmax_decision_age_hours: 6\n"
)


def _load(tmp_path: Path, live: str = LIVE, ops: str = OPS) -> LiveConfig:
    (tmp_path / "live.yaml").write_text(live, encoding="utf-8")
    (tmp_path / "ops.yaml").write_text(ops, encoding="utf-8")
    return load_live_config(
        tmp_path / "live.yaml", ops_path=tmp_path / "ops.yaml", questions_path=QUESTIONS_PATH
    )


def test_the_set_version_is_the_hash_of_questions_and_the_live_file_only(tmp_path: Path) -> None:
    config = _load(tmp_path)

    expected = hashlib.sha256(QUESTIONS_PATH.read_bytes() + LIVE.encode()).hexdigest()
    assert config.prompt_version == expected
    assert expected == live_prompt_version(QUESTIONS_PATH.read_bytes(), LIVE.encode())
    assert _load(tmp_path, live=LIVE + "# yorum\n").prompt_version != expected


def test_an_operational_change_keeps_the_set_and_its_counter(tmp_path: Path) -> None:
    """M4: birim fiyat ya da tavan düzeltmesi yeni küme DEĞİLDİR (sayaç sıfırlanmaz)."""
    config = _load(tmp_path)
    cheaper = _load(tmp_path, ops=OPS.replace("tier2: 0.02", "tier2: 0.015"))

    assert cheaper.prompt_version == config.prompt_version
    assert cheaper.estimate_usd[TIER2] == 0.015
    assert config.estimate_usd[TIER1] == 0.01
    assert config.max_decision_age == timedelta(hours=6)


@pytest.mark.parametrize(
    ("live_old", "live_new", "ops_old", "ops_new", "needle"),
    [
        ("min_reliability: 0.5\n", "", "", "", "alanlar"),
        ("", "", "max_sides_per_run: 80\n", "", "alanlar"),
        (
            f"tier1_prompt_version: {PV}",
            "tier1_prompt_version: abc",
            "",
            "",
            "tier1_prompt_version",
        ),
        ("jev_model: jev-2026-10", 'jev_model: ""', "", "", "jev_model"),
        ("min_belongs: 0.5", "min_belongs: 1.5", "", "", "min_belongs"),
        ("", "", "tier2: 0.02", "tier2: 0", "estimate_usd"),
        ("", "", "max_sides_per_run: 80", "max_sides_per_run: 0", "max_sides_per_run"),
        ("", "", "max_decision_age_hours: 6", "max_decision_age_hours: 7", "max_decision_age"),
    ],
)
def test_a_malformed_set_is_refused_by_name(
    tmp_path: Path, live_old: str, live_new: str, ops_old: str, ops_new: str, needle: str
) -> None:
    live = LIVE.replace(live_old, live_new) if live_old else LIVE
    ops = OPS.replace(ops_old, ops_new) if ops_old else OPS
    with pytest.raises(LiveConfigError, match=needle):
        _load(tmp_path, live=live, ops=ops)


@pytest.mark.parametrize(("model", "needle"), [("null", "sabitlenmedi"), ("jev-latest", "latest")])
def test_an_unpinned_model_is_not_a_frozen_set(tmp_path: Path, model: str, needle: str) -> None:
    config = _load(tmp_path, live=LIVE.replace("jev_model: jev-2026-10", f"jev_model: {model}"))

    (violation,) = frozen_violations(config, questions_prompt_version=PV)
    assert needle in violation


def test_a_changed_question_file_breaks_the_frozen_set(tmp_path: Path) -> None:
    config = _load(tmp_path)

    assert frozen_violations(config, questions_prompt_version=PV) == ()
    assert frozen_violations(config, questions_prompt_version="f" * 64) != ()


def test_the_committed_set_pins_todays_questions_and_the_spec_limits() -> None:
    config = load_live_config(
        REPO / "config" / "faz4_live.yaml",
        ops_path=REPO / "config" / "faz4_ops.yaml",
        questions_path=QUESTIONS_PATH,
    )
    found = frozen_violations(config, questions_prompt_version=PV)

    assert [violation for violation in found if "jev_model" not in violation] == []
    assert config.max_decision_age == timedelta(hours=6)
    assert (config.min_belongs, config.min_reliability, config.max_sides_per_run) == (0.5, 0.5, 80)
