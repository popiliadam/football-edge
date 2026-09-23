"""Soru dosyası (spec §5.2, §6): sürümlü, tekil, taraf başına, "tabloda zaten var mı?" süzgeçli."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from football_edge.features.questions import (
    ALWAYS,
    CLUSTER_QUESTION,
    LEVEL_CRITERIA,
    MATCH_QUESTION,
    NEW_EVENT,
    RELIABLE_CHOICES,
    TEAM_SLOT,
    TIER1_QUESTIONS,
    QuestionsError,
    for_team,
    load_questions,
)
from football_edge.features.types import AWAY, HOME
from football_edge.jev import NO_MATCH, Question

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config" / "jev_questions.yaml"
# Cevabı bir toplayıcının ya da defterin zaten verdiği konular (ana tasarım §5.2 kuralı).
TABLE_ANSWERED = (
    "weather",
    "rain",
    "temperature",
    "wind",
    "distance",
    "kilomet",
    "travel",
    "days of rest",
    "fixture congestion",
    "league position",
    "standings",
    "table position",
    "recent form",
    "goals scored",
    "odds",
    "betting",
    "elo",
    "head-to-head",
    "referee appoint",
    "referee assigned",
)


def _minimal() -> dict[str, Any]:
    return {
        "tier1": [
            {"id": MATCH_QUESTION, "instructions": "Which fixture?"},
            {"id": CLUSTER_QUESTION, "instructions": "Which earlier item?"},
            {
                "id": "t1_guvenilirlik",
                "instructions": "How reliable?",
                "criteria": {"official": "o", "reported": "r", "rumour": "x"},
            },
            {"id": "t1_celiski", "instructions": "Contradiction?", "criteria": {"yes": "y"}},
        ],
        "tier2": [{"id": "t2_a", "instructions": "How much for {team}?"}],
        "tier3": [{"id": "t3_b", "instructions": "How strongly for {team}?"}],
        "tier4": [],
    }


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "questions.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_the_real_file_loads_with_about_thirty_five_questions() -> None:
    questions = load_questions(CONFIG)
    total = sum(
        len(t) for t in (questions.tier1, questions.tier2, questions.tier3, questions.tier4)
    )

    assert 30 <= total <= 40
    assert {q.question_id for q in questions.tier1} == TIER1_QUESTIONS
    assert min(len(questions.tier2), len(questions.tier3), len(questions.tier4)) >= 5


def test_prompt_version_is_the_sha256_of_the_file() -> None:
    assert load_questions(CONFIG).prompt_version == hashlib.sha256(CONFIG.read_bytes()).hexdigest()


def test_one_changed_character_is_a_new_prompt_version(tmp_path: Path) -> None:
    first = load_questions(_write(tmp_path, _minimal())).prompt_version
    changed = _minimal()
    changed["tier2"][0]["instructions"] = "How much for {team}!"

    assert load_questions(_write(tmp_path, changed)).prompt_version != first


def test_dynamic_questions_carry_only_their_always_present_option() -> None:
    tier1 = {q.question_id: q for q in load_questions(CONFIG).tier1}

    assert dict(tier1[MATCH_QUESTION].criteria) == dict(ALWAYS[MATCH_QUESTION])
    assert set(tier1[MATCH_QUESTION].criteria) == {NO_MATCH}
    assert set(tier1[CLUSTER_QUESTION].criteria) == {NEW_EVENT}


def test_instructions_name_the_always_present_options_verbatim() -> None:
    tier1 = {q.question_id: q for q in load_questions(CONFIG).tier1}

    assert f"'{NO_MATCH}'" in tier1[MATCH_QUESTION].instructions
    assert f"'{NEW_EVENT}'" in tier1[CLUSTER_QUESTION].instructions


def test_reliability_offers_the_choices_the_gate_sums() -> None:
    tier1 = {q.question_id: q for q in load_questions(CONFIG).tier1}

    assert set(RELIABLE_CHOICES) <= set(tier1["t1_guvenilirlik"].criteria)


def test_side_questions_have_one_team_slot_and_the_common_scale() -> None:
    questions = load_questions(CONFIG)

    for question in (*questions.tier2, *questions.tier3, *questions.tier4):
        assert question.instructions.count(TEAM_SLOT) == 1, question.question_id
        assert dict(question.criteria) == dict(LEVEL_CRITERIA), question.question_id


def test_no_question_asks_what_a_table_already_answers() -> None:
    questions = load_questions(CONFIG)
    asked = [
        (q.question_id, term)
        for q in (*questions.tier2, *questions.tier3, *questions.tier4)
        for term in TABLE_ANSWERED
        if re.search(rf"\b{term}", q.instructions.lower())
    ]

    assert asked == [], f"cevabı tabloda olan soru: {asked}"


def _drop_criteria(data: dict[str, Any]) -> None:
    del data["tier1"][2]["criteria"]["official"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["tier2"].append({"id": "t2_a", "instructions": "x {team}"}), "kimliği"),
        (lambda d: d["tier3"].append({"id": "t2_c", "instructions": "x {team}"}), "öneki"),
        (lambda d: d["tier1"][0].update(criteria={"a": "b"}), "haberden kurulur"),
        (lambda d: d["tier2"][0].update(criteria={"a": "b"}), "ortak ölçek"),
        (lambda d: d["tier2"][0].update(instructions="How much?"), "yuvası"),
        (lambda d: d["tier2"][0].update(instructions="{team} or {team}"), "yuvası"),
        (lambda d: d["tier2"][0].update(extra="x"), "alanları"),
        (lambda d: d["tier1"].pop(3), "kademe 1"),
        (lambda d: d["tier3"][0].update(instructions="How much for {team}?"), "iki kez"),
        (_drop_criteria, "zorunlu"),
        (lambda d: d.pop("tier4"), "üst düzey"),
        (lambda d: d["tier2"][0].update(id="t2_Buyuk"), "geçersiz"),
    ],
)
def test_a_malformed_file_is_refused_by_name(tmp_path: Path, mutate: Any, message: str) -> None:
    data = _minimal()
    mutate(data)

    with pytest.raises(QuestionsError, match=message):
        load_questions(_write(tmp_path, data))


def test_for_team_binds_a_side_question_to_one_side() -> None:
    question = Question("t2_x", "How much for {team}?", LEVEL_CRITERIA)

    home = for_team(question, side=HOME, team="Galatasaray")

    assert home.question_id == "t2_x:home"
    assert home.instructions == "How much for Galatasaray?"
    assert dict(home.criteria) == dict(LEVEL_CRITERIA)
    assert for_team(question, side=AWAY, team="Göztepe").question_id == "t2_x:away"


def test_for_team_refuses_a_bad_side_or_a_question_without_a_slot() -> None:
    with pytest.raises(ValueError, match="taraf"):
        for_team(Question("t2_x", "for {team}", LEVEL_CRITERIA), side="both", team="A")
    with pytest.raises(ValueError, match="taraf sorusu değil"):
        for_team(Question("t1_x", "no slot", {"a": "b"}), side=HOME, team="A")
