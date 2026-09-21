"""Jev taklidi: ağa çıkmaz, senaryoyu test yazar."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from football_edge.jev import ChoiceAnswer


@dataclass
class FakeJev:
    answer: ChoiceAnswer
    seen: list[dict[str, Any]] = field(default_factory=list)

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        self.seen = [*self.seen, {"state": state, "criteria": criteria}]
        return self.answer
