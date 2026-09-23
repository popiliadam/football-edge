"""Jev taklidi: ağa çıkmaz, senaryoyu test yazar."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from football_edge.jev import COST_REPORTED, BatteryAnswer, ChoiceAnswer, Question


@dataclass
class FakeJev:
    answer: ChoiceAnswer
    seen: list[dict[str, Any]] = field(default_factory=list)

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        self.seen = [*self.seen, {"state": state, "criteria": criteria}]
        return self.answer

    def ask_battery(self, state: Mapping[str, Any], questions: Sequence[Question]) -> BatteryAnswer:
        raise AssertionError("FakeJev yalnız ask_choice içindir; batarya için FakeBatteryJev")


@dataclass
class FakeBatteryJev:
    """Her soruya `choices`taki seçimi, yoksa İLK kriterini verir.

    `missing`teki soru cevapsız döner (kısmi başarısızlık); `error` verilirse çağrı patlar.
    `seen` her çağrının durumunu ve soru kimliklerini sırasıyla tutar.
    """

    choices: Mapping[str, str] = field(default_factory=dict)
    confidence: float = 0.9
    jev_model: str = "jev-fake"
    cost_usd: float = 0.002
    cost_basis: str = COST_REPORTED
    missing: frozenset[str] = frozenset()
    error: Exception | None = None
    seen: list[dict[str, Any]] = field(default_factory=list)

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        raise AssertionError("FakeBatteryJev yalnız ask_battery içindir")

    def ask_battery(self, state: Mapping[str, Any], questions: Sequence[Question]) -> BatteryAnswer:
        ids = tuple(question.question_id for question in questions)
        self.seen = [*self.seen, {"state": dict(state), "question_ids": ids}]
        if self.error is not None:
            raise self.error
        return BatteryAnswer(
            answers={
                question.question_id: self._answer(question)
                for question in questions
                if question.question_id not in self.missing
            },
            jev_model=self.jev_model,
            cost_usd=self.cost_usd,
            cost_basis=self.cost_basis,
        )

    def _answer(self, question: Question) -> ChoiceAnswer:
        choice = self.choices.get(question.question_id, next(iter(question.criteria)))
        rest = [label for label in question.criteria if label != choice]
        top = self.confidence if rest else 1.0
        share = (1.0 - top) / len(rest) if rest else 0.0
        return ChoiceAnswer(
            choice=choice,
            confidence=self.confidence,
            probabilities={choice: top, **{label: share for label in rest}},
        )
