from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from typesafe_sdk import ChoiceAnswer as SdkChoiceAnswer
    from typesafe_sdk import SystemOneResponse

NO_MATCH = "none of the above"

# Anahtarsız Jev komutu adıyla çıkar (spec §9); collect 2–8, backtest 9–14, live 15, bütçe 16.
EXIT_NO_JEV_KEY = 17

# Maliyetin kaynağı. typesafe-sdk 0.7.0 yanıtı maliyet TAŞIMAZ (yalnız `model` ve token sayısı):
# gerçek istemci "unpriced" döner, `BudgetedJev` tahmini yazar ve kaydı "estimated" diye adlandırır.
COST_REPORTED = "reported"
COST_ESTIMATED = "estimated"
COST_UNPRICED = "unpriced"
COST_BASES = frozenset({COST_REPORTED, COST_ESTIMATED, COST_UNPRICED})


class MissingJevKey(RuntimeError):
    """`TYPESAFE_API_KEY` yok. RuntimeError'dan türer: mevcut `map-entities` yolu aynen patlar."""


@dataclass(frozen=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]


@dataclass(frozen=True)
class Question:
    """Bataryadaki tek Choice sorusu. `question_id` modele GİTMEZ; anlam `instructions`tadır."""

    question_id: str
    instructions: str
    criteria: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.question_id:
            raise ValueError("question_id boş")
        if not self.criteria:
            raise ValueError(f"{self.question_id}: criteria boş — seçeneksiz soru cevaplanamaz")
        object.__setattr__(self, "criteria", MappingProxyType(dict(self.criteria)))


@dataclass(frozen=True)
class BatteryAnswer:
    """Tek çağrının cevapları. Cevabı gelmeyen soru `answers`ta YOKTUR — sıfır sayılmaz."""

    answers: Mapping[str, ChoiceAnswer]
    jev_model: str
    cost_usd: float
    cost_basis: str = COST_REPORTED
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        # NaN tavan karşılaştırmasını her zaman False yapar: bir kez girerse tavan kapanır.
        if not (math.isfinite(self.cost_usd) and self.cost_usd >= 0):
            raise ValueError(f"cost_usd sonlu ve ≥ 0 olmalı: {self.cost_usd}")
        if self.cost_basis not in COST_BASES:
            raise ValueError(f"bilinmeyen cost_basis: {self.cost_basis}")
        object.__setattr__(self, "answers", MappingProxyType(dict(self.answers)))


class JevClient(Protocol):
    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer: ...

    def ask_battery(
        self, state: Mapping[str, Any], questions: Sequence[Question]
    ) -> BatteryAnswer: ...


def battery_question_ids(questions: Sequence[Question]) -> tuple[str, ...]:
    """Boş ya da yinelenen kimlikli batarya reddedilir: yanıtta iki soru tek anahtara düşer."""
    ids = tuple(question.question_id for question in questions)
    if not ids:
        raise ValueError("boş batarya: en az bir soru gerekir")
    duplicates = sorted({qid for qid in ids if ids.count(qid) > 1})
    if duplicates:
        raise ValueError(f"yinelenen question_id: {', '.join(duplicates)}")
    return ids


def _choice_answer(answer: SdkChoiceAnswer) -> ChoiceAnswer:
    return ChoiceAnswer(
        choice=str(answer.choice),
        confidence=float(answer.confidence),
        probabilities={str(k): float(v) for k, v in dict(answer.probabilities).items()},
    )


def battery_from_response(
    response: SystemOneResponse, question_ids: Sequence[str]
) -> BatteryAnswer:
    """Yalnız istenen ve Choice olan cevaplar alınır; gelmeyen soru eksik kalır (spec §9)."""
    choices = response.choices
    return BatteryAnswer(
        answers={qid: _choice_answer(choices[qid]) for qid in question_ids if qid in choices},
        jev_model=str(response.model),
        cost_usd=0.0,
        cost_basis=COST_UNPRICED,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


class TypeSafeJev:
    """TypeSafe System One (Jev) sarmalayıcısı.

    `typesafe_sdk` yalnız BURADA import edilir: eşleme mantığı sağlayıcıyı tanımaz ve
    testler ağa çıkmadan `JevClient` protokolünü taklit eder.

    `confidence`, olasılık DAĞILIMININ ne kadar tepeli olduğunu özetler — işin doğru
    yapıldığının garantisi değil (TypeSafe confidence dokümanı). Eşik, sonucun
    bedeline göre seçilir; burada bedel sessiz bir join hatasıdır, o yüzden yüksektir.

    Zaman aşımı ve 5xx'te sınırlı yeniden deneme SDK'nın varsayılan `RetryPolicy`sidir
    (2 yeniden deneme); tükenirse istisna çağırana çıkar, satır yazılmaz (spec §9).
    """

    def __init__(self, api_key: str | None = None) -> None:
        resolved = api_key or os.getenv("TYPESAFE_API_KEY")
        if not resolved:
            raise MissingJevKey("TYPESAFE_API_KEY tanımlı değil")
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
        return _choice_answer(response.choices["match"])

    def ask_battery(self, state: Mapping[str, Any], questions: Sequence[Question]) -> BatteryAnswer:
        """Bütün sorular TEK istekte: aynı durum üstündeki bağımsız sorular birlikte sorulur."""
        question_ids = battery_question_ids(questions)
        from typesafe_sdk import Choice, TypeSafeClient

        with TypeSafeClient(api_key=self._api_key) as client:
            response = client.system_one(
                state=dict(state),
                questions={
                    question.question_id: Choice(
                        instructions=question.instructions, criteria=dict(question.criteria)
                    )
                    for question in questions
                },
            )
        return battery_from_response(response, question_ids)
