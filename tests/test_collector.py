from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from football_edge.collector import (
    Breaker,
    ContractViolation,
    Observation,
    assert_fresh,
    assert_schema,
    fetch_text,
    is_open,
    record,
)
from football_edge.sources import SourceBlocked, robots_for
from tests.fake_sources import fake_source, write_robots

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def observation(key: str, **payload: object) -> Observation:
    return Observation(
        source_id="footystats",
        entity_kind="team",
        entity_key=key,
        observed_at=NOW,
        payload={"xg": 1.5, "xga": 1.1, **payload},
    )


def test_fetch_refuses_a_disallowed_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """İstek ATILMAZ: robots kontrolü fetch'in İLK işidir, yanıtı filtrelemek değil."""
    write_robots(tmp_path, "blocked", "User-agent: *\nDisallow: /\n")
    source = fake_source(id="blocked")
    parser = robots_for(source, tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text="gelmemeliydi")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(SourceBlocked),
    ):
        fetch_text(client, source, "/anything", parser, expect="text/html")

    assert calls == [], "robots kapalıyken HTTP isteği atıldı"


def test_fetch_rejects_a_wrong_content_type(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Spec §7: bazı uçlar 200 dönüp YANLIŞ içerik verir. 200 doğruluk değildir."""
    write_robots(tmp_path, "ok", "")
    source = fake_source(id="ok")
    parser = robots_for(source, tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="<html>hata sayfası</html>", headers={"content-type": "text/html"}
        )

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ContractViolation, match="content-type"),
    ):
        fetch_text(client, source, "/feed", parser, expect="application/xml")


def test_fetch_decodes_with_the_declared_encoding(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """TFF windows-1254: charset YALNIZ HTTP başlığında. httpx'in tahminine bırakılmaz."""
    write_robots(tmp_path, "tff", "")
    source = fake_source(id="tff")
    parser = robots_for(source, tmp_path)
    body = "Süper Lig hakem ataması".encode("windows-1254")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        text = fetch_text(client, source, "/x", parser, expect="text/html", encoding="windows-1254")

    assert "Süper Lig" in text


def test_empty_result_fails_the_schema_assertion() -> None:
    """Kırılan ayrıştırıcı BOŞ LİSTE üretir ve sessizce başarılı görünür — asıl arıza budur."""
    with pytest.raises(ContractViolation, match="en az 1 satır"):
        assert_schema((), source_id="footystats", required=frozenset({"xg"}), minimum_rows=1)


def test_missing_field_fails_the_schema_assertion() -> None:
    with pytest.raises(ContractViolation, match="xga"):
        assert_schema(
            (Observation("footystats", "team", "gs", NOW, {"xg": 1.5}),),
            source_id="footystats",
            required=frozenset({"xg", "xga"}),
            minimum_rows=1,
        )


def test_stale_data_fails_the_freshness_assertion() -> None:
    old = Observation("footystats", "team", "gs", NOW - timedelta(days=9), {"xg": 1.5})
    with pytest.raises(ContractViolation, match="tazelik"):
        assert_fresh((old,), NOW, max_age=timedelta(days=7), source_id="footystats")


def test_fresh_data_passes() -> None:
    assert_fresh((observation("gs"),), NOW, max_age=timedelta(days=7), source_id="footystats")


def test_content_hash_is_stable_and_content_sensitive() -> None:
    """Aynı içerik yeniden gözlenirse yeni satır yazılmaz; depo idempotent olmalı."""
    assert observation("gs").content_hash == observation("gs").content_hash
    assert observation("gs").content_hash != observation("gs", xg=1.6).content_hash


def test_breaker_opens_after_the_threshold_and_closes_after_cooldown() -> None:
    """Kaynak başına devre kesici (spec §8): kırılgan kaynak turu her seferinde düşürmesin."""
    cooldown = timedelta(hours=1)
    breaker = Breaker(failures=0, opened_at=None)
    for _ in range(3):
        breaker = record(breaker, NOW, ok=False, threshold=3, cooldown=cooldown)

    assert is_open(breaker, NOW, cooldown=cooldown) is True
    assert is_open(breaker, NOW + timedelta(hours=2), cooldown=cooldown) is False
    assert record(breaker, NOW, ok=True, threshold=3, cooldown=cooldown).failures == 0


def test_normalise_team_strips_legal_suffixes_and_punctuation() -> None:
    from football_edge.naming import normalise_team

    assert normalise_team("  Galatasaray A.Ş. ") == normalise_team("GALATASARAY AŞ")
    assert normalise_team("Gaziantep F.K.") == normalise_team("gaziantep fk")


def test_normalise_team_uses_turkish_case_rules() -> None:
    """`"I".lower()` Python'da `"i"` verir; Türkçe'de `ı` olmalı. Karıştıran join boş kalır."""
    from football_edge.naming import normalise_team

    assert normalise_team("FENERBAHÇE") == normalise_team("Fenerbahçe")
    assert normalise_team("ISTANBULSPOR") == normalise_team("Istanbulspor")
