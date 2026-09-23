"""`jev.py`nin ÇEVRİMDIŞI test edilebilir kısmı: anahtar çözümü ve hata yolu.

`ask_choice` gerçek bir ağ çağrısı yapar (`typesafe_sdk.TypeSafeClient`) ve BURADA
sınanmaz — bu ortamda `TYPESAFE_API_KEY` yok (task-11 brief, "prerequisite gap").
`typesafe_sdk` `ask_choice` içinde GECİKMELİ import edilir, tam bu yüzden: modülün
import edilmesi paketin kurulu olmasını gerektirmez, yalnız GERÇEKTEN çağrılırsa gerekir.
`mapping.py`nin tüm testleri (`tests/test_mapping.py`) `FakeJev` ile ÇEVRİMDIŞI koşar.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any

import pytest
import typesafe_sdk

from football_edge.jev import (
    COST_UNPRICED,
    EXIT_NO_JEV_KEY,
    NO_MATCH,
    BatteryAnswer,
    ChoiceAnswer,
    MissingJevKey,
    Question,
    TypeSafeJev,
    battery_from_response,
    battery_question_ids,
)


def test_typesafe_jev_requires_a_key_and_names_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anahtarsız SESSİZCE bir varsayılana düşmez — adıyla patlar (brief: "clear named error")."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        TypeSafeJev()


def test_typesafe_jev_accepts_an_explicit_key_without_touching_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    client = TypeSafeJev(api_key="explicit-key")

    assert client._api_key == "explicit-key"


def test_typesafe_jev_falls_back_to_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "env-key")

    client = TypeSafeJev()

    assert client._api_key == "env-key"


def test_typesafe_jev_prefers_the_explicit_key_over_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`resolved = api_key or os.getenv(...)`in SIRASI: parametre HER ZAMAN kazanır."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "env-key")

    client = TypeSafeJev(api_key="explicit-key")

    assert client._api_key == "explicit-key"


def test_choice_answer_is_frozen() -> None:
    """Global kural: mutation yok (frozen=True, bkz. coding-style.md)."""
    answer = ChoiceAnswer(choice="Galatasaray", confidence=0.9, probabilities={"Galatasaray": 0.9})

    with pytest.raises(dataclasses.FrozenInstanceError):
        answer.choice = "Fenerbahce"  # type: ignore[misc]


def test_no_match_sentinel_is_a_readable_string_not_a_real_club_name() -> None:
    """Kanonik listeyle ASLA çakışmamalı — çakışırsa `resolve`in NO_MATCH kontrolü belirsizleşir."""
    assert NO_MATCH == "none of the above"


# ── Faz 4 Task 7: batarya çağrısı ────────────────────────────────────────────


def _question(qid: str, *labels: str) -> Question:
    return Question(
        question_id=qid,
        instructions=f"{qid} sorusu",
        criteria={label: f"{label} açıklaması" for label in labels or ("evet", "hayır")},
    )


def _response(
    answers: dict[str, Any], *, model: str = "jev-test"
) -> typesafe_sdk.SystemOneResponse:
    return typesafe_sdk.SystemOneResponse.model_validate(
        {"model": model, "usage": {"input_tokens": 120, "output_tokens": 7}, "answers": answers}
    )


def _choice(choice: str, confidence: float = 0.8) -> dict[str, Any]:
    return {
        "type": "choice",
        "choice": choice,
        "confidence": confidence,
        "probabilities": {choice: confidence, "diğer": round(1 - confidence, 10)},
    }


def test_missing_key_is_a_named_runtime_error_with_its_own_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RuntimeError'dan türer: `map-entities`in mevcut davranışı değişmez; CLI 17'ye çevirir."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(MissingJevKey, match="TYPESAFE_API_KEY"):
        TypeSafeJev()
    assert issubclass(MissingJevKey, RuntimeError)
    assert EXIT_NO_JEV_KEY == 17


def test_question_freezes_its_criteria_and_rejects_an_empty_choice_set() -> None:
    source = {"evet": "haber bu maça ait", "hayır": "değil"}
    question = Question(question_id="t1_ait", instructions="ait mi?", criteria=source)
    source["belki"] = "sonradan eklendi"

    assert list(question.criteria) == ["evet", "hayır"]
    with pytest.raises(TypeError):
        question.criteria["x"] = "y"  # type: ignore[index]
    with pytest.raises(ValueError, match="criteria boş"):
        Question(question_id="t1_bos", instructions="?", criteria={})
    with pytest.raises(ValueError, match="question_id boş"):
        Question(question_id="", instructions="?", criteria={"a": "b"})


def test_battery_question_ids_rejects_empty_and_duplicate_batteries() -> None:
    assert battery_question_ids([_question("a"), _question("b")]) == ("a", "b")
    with pytest.raises(ValueError, match="boş batarya"):
        battery_question_ids([])
    with pytest.raises(ValueError, match="yinelenen question_id: a"):
        battery_question_ids([_question("a"), _question("b"), _question("a")])


def test_battery_answer_is_read_only_and_rejects_an_unknown_cost_basis() -> None:
    answer = BatteryAnswer(
        answers={"a": ChoiceAnswer("evet", 0.9, {"evet": 0.9, "hayır": 0.1})},
        jev_model="jev-test",
        cost_usd=0.01,
    )

    with pytest.raises(TypeError):
        answer.answers["b"] = answer.answers["a"]  # type: ignore[index]
    with pytest.raises(ValueError, match="cost_basis"):
        BatteryAnswer(answers={}, jev_model="jev-test", cost_usd=0.0, cost_basis="guessed")


def test_battery_from_response_keeps_only_requested_choice_answers_and_leaves_gaps() -> None:
    """Gelmeyen soru EKSİK kalır (sıfır sayılmaz); istenmeyen ve Choice olmayan cevap alınmaz."""
    response = _response(
        {
            "a": _choice("evet"),
            "noul": {"type": "noul", "noul": 0.4},
            "istenmedi": _choice("hayır"),
        }
    )

    battery = battery_from_response(response, ("a", "b", "noul"))

    assert set(battery.answers) == {"a"}
    assert battery.answers["a"] == ChoiceAnswer("evet", 0.8, {"evet": 0.8, "diğer": 0.2})
    assert battery.jev_model == "jev-test"
    assert (battery.input_tokens, battery.output_tokens) == (120, 7)
    # SDK maliyet bildirmez: gerçek istemci fiyatsız döner, BudgetedJev tahmini yazar.
    assert (battery.cost_usd, battery.cost_basis) == (0.0, COST_UNPRICED)


@dataclass
class _SdkCalls:
    calls: tuple[dict[str, Any], ...] = ()


def _patch_sdk(
    monkeypatch: pytest.MonkeyPatch, response: typesafe_sdk.SystemOneResponse
) -> _SdkCalls:
    recorder = _SdkCalls()

    class _Client:
        def __init__(self, *, api_key: str) -> None:
            recorder.calls = (*recorder.calls, {"api_key": api_key})

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def system_one(
            self, *, state: dict[str, Any], questions: dict[str, Any]
        ) -> typesafe_sdk.SystemOneResponse:
            recorder.calls = (*recorder.calls, {"state": state, "questions": questions})
            return response

    monkeypatch.setattr(typesafe_sdk, "TypeSafeClient", _Client)
    return recorder


def test_ask_battery_sends_every_question_in_one_request_keyed_by_question_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _patch_sdk(monkeypatch, _response({"a": _choice("evet"), "b": _choice("ev")}))
    questions = [_question("a"), _question("b", "ev", "deplasman", "ikisi")]

    battery = TypeSafeJev(api_key="k" * 16).ask_battery({"haber": "başlık"}, questions)

    assert recorder.calls[0] == {"api_key": "k" * 16}
    sent = recorder.calls[1]
    assert len(recorder.calls) == 2, "batarya tek istek olmalı"
    assert sent["state"] == {"haber": "başlık"}
    assert list(sent["questions"]) == ["a", "b"]
    assert isinstance(sent["questions"]["b"], typesafe_sdk.Choice)
    assert sent["questions"]["b"].instructions == "b sorusu"
    assert dict(sent["questions"]["b"].criteria) == {
        "ev": "ev açıklaması",
        "deplasman": "deplasman açıklaması",
        "ikisi": "ikisi açıklaması",
    }
    assert set(battery.answers) == {"a", "b"}


def test_ask_battery_rejects_a_duplicate_battery_before_opening_a_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _patch_sdk(monkeypatch, _response({}))

    with pytest.raises(ValueError, match="yinelenen"):
        TypeSafeJev(api_key="k" * 16).ask_battery({}, [_question("a"), _question("a")])
    assert recorder.calls == ()


# ── Review Focus ─────────────────────────────────────────────────────────────


def test_battery_answer_rejects_a_non_finite_or_negative_cost() -> None:
    """Review Focus: NaN maliyet deftere girerse `toplam + tahmin > tavan` hep False olur."""
    for bad in (math.nan, math.inf, -0.01):
        with pytest.raises(ValueError, match="cost_usd"):
            BatteryAnswer(answers={}, jev_model="jev-test", cost_usd=bad)
