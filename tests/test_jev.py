"""`jev.py`nin ÇEVRİMDIŞI test edilebilir kısmı: anahtar çözümü ve hata yolu.

`ask_choice` gerçek bir ağ çağrısı yapar (`typesafe_sdk.TypeSafeClient`) ve BURADA
sınanmaz — bu ortamda `TYPESAFE_API_KEY` yok (task-11 brief, "prerequisite gap").
`typesafe_sdk` `ask_choice` içinde GECİKMELİ import edilir, tam bu yüzden: modülün
import edilmesi paketin kurulu olmasını gerektirmez, yalnız GERÇEKTEN çağrılırsa gerekir.
`mapping.py`nin tüm testleri (`tests/test_mapping.py`) `FakeJev` ile ÇEVRİMDIŞI koşar.
"""

from __future__ import annotations

import dataclasses

import pytest

from football_edge.jev import NO_MATCH, ChoiceAnswer, TypeSafeJev


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
