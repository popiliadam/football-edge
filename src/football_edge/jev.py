from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

NO_MATCH = "none of the above"


@dataclass(frozen=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]


class JevClient(Protocol):
    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer: ...


class TypeSafeJev:
    """TypeSafe System One (Jev) sarmalayıcısı.

    `typesafe_sdk` yalnız BURADA import edilir: eşleme mantığı sağlayıcıyı tanımaz ve
    testler ağa çıkmadan `JevClient` protokolünü taklit eder.

    `confidence`, olasılık DAĞILIMININ ne kadar tepeli olduğunu özetler — işin doğru
    yapıldığının garantisi değil (TypeSafe confidence dokümanı). Eşik, sonucun
    bedeline göre seçilir; burada bedel sessiz bir join hatasıdır, o yüzden yüksektir.
    """

    def __init__(self, api_key: str | None = None) -> None:
        resolved = api_key or os.getenv("TYPESAFE_API_KEY")
        if not resolved:
            raise RuntimeError("TYPESAFE_API_KEY tanımlı değil")
        self._api_key = resolved

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        from typesafe_sdk import Choice, TypeSafeClient

        with TypeSafeClient(api_key=self._api_key) as client:
            response = client.system_one(
                state=state,
                questions={"match": Choice(instructions=instructions, criteria=criteria)},
            )
        answer = response.choices["match"]
        return ChoiceAnswer(
            choice=str(answer.choice),
            confidence=float(answer.confidence),
            probabilities={str(k): float(v) for k, v in dict(answer.probabilities).items()},
        )
