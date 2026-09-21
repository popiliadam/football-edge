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


def test_fetch_refuses_a_redirect_to_a_disallowed_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """`follow_redirects=True` guard_path'i tamamen atlatıyordu (review #8): robots yalnız
    İLK URL'e soruluyordu. Bir 302'nin `Location`'ı GUARD EDİLMEDEN istenmemeli."""
    write_robots(tmp_path, "redir", "User-agent: *\nDisallow: /disallowed\n")
    source = fake_source(id="redir")
    parser = robots_for(source, tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/disallowed"})
        return httpx.Response(200, text="gelmemeliydi")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(SourceBlocked),
    ):
        fetch_text(client, source, "/start", parser, expect="text/html")

    assert calls == ["https://example.test/start"], "disallowed Location'a ikinci istek atıldı"


def test_fetch_refuses_a_cross_host_redirect(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """`guard_path` yalnız KENDİ kaynağının parser'ına karşı anlamlıdır. base_url ORİJİNİ
    dışına sıçrayan bir `Location`, hiç ilgisi olmayan bir host'un robots'una karşı hiç
    sorulmadan istenmemeli — 'base_url ile başlıyor' bir alt dize testi ile yetinilirse
    `https://example.test.evil.example` gibi bir host da (yanlışlıkla) izinli sayılırdı."""
    write_robots(tmp_path, "cross", "")
    source = fake_source(id="cross")
    parser = robots_for(source, tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.host == "example.test":
            return httpx.Response(302, headers={"location": "https://evil.example/x"})
        return httpx.Response(200, text="gelmemeliydi")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(SourceBlocked),
    ):
        fetch_text(client, source, "/start", parser, expect="text/html")

    assert calls == ["https://example.test/start"], "çapraz-host Location'a istek atıldı"


def test_fetch_follows_a_same_host_redirect_to_an_allowed_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Yönlendirme YASAKLANMIYOR, yalnız her sıçrama guard_path'ten geçiyor — aynı host'ta
    izinli bir hedefe giden 302 hâlâ çalışmalı (redirect'i tamamen kapatmak aşırı olurdu)."""
    write_robots(tmp_path, "redir-ok", "")
    source = fake_source(id="redir-ok")
    parser = robots_for(source, tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/old":
            return httpx.Response(302, headers={"location": "/new"})
        return httpx.Response(200, text="hedef", headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        text = fetch_text(client, source, "/old", parser, expect="text/html")

    assert text == "hedef"
    assert calls == ["https://example.test/old", "https://example.test/new"]


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


def test_missing_field_fails_the_schema_assertion_when_value_is_none_or_empty() -> None:
    """Şema iddiası yalnız ANAHTARIN varlığına bakıyordu (review #4): `{"xg": None}` ya da
    `{"xg": ""}` bir markup değişikliğinden sonra hâlâ eşleşen ama artık hiçbir şey
    taşımayan bir seçiciyle birebir aynı arıza şeklidir — boş liste kadar yaygın, ama
    eski kod bunu YAKALAMIYORDU. `xga` her iki denemede de GERÇEK bir değer taşıyor ve
    `missing` listesine GİRMEMELİ — yalnız `xg` girmeli."""
    none_valued = (Observation("footystats", "team", "gs", NOW, {"xg": None, "xga": 1.1}),)
    with pytest.raises(ContractViolation, match=r"\['xg'\]"):
        assert_schema(
            none_valued, source_id="footystats", required=frozenset({"xg", "xga"}), minimum_rows=1
        )

    empty_string_valued = (Observation("footystats", "team", "gs", NOW, {"xg": "", "xga": 1.1}),)
    with pytest.raises(ContractViolation, match=r"\['xg'\]"):
        assert_schema(
            empty_string_valued,
            source_id="footystats",
            required=frozenset({"xg", "xga"}),
            minimum_rows=1,
        )


def test_stale_data_fails_the_freshness_assertion() -> None:
    old = Observation("footystats", "team", "gs", NOW - timedelta(days=9), {"xg": 1.5})
    with pytest.raises(ContractViolation, match="tazelik"):
        assert_fresh((old,), NOW, max_age=timedelta(days=7), source_id="footystats")


def test_future_dated_data_fails_the_freshness_assertion() -> None:
    """R13'teki `sources._date_violation` ile AYNI arıza sınıfı (review #3): `now - newest`
    negatifken eski kod hiç raise ETMİYORDU. Tasks 5-8 `observed_at`i KAYNAK tarihinden
    türetir (feed pubDate, fikstür tarihi); ileri tarihli TEK satır tüm partiyi süresiz
    taze gösterebilirdi."""
    future = Observation("footystats", "team", "gs", NOW + timedelta(days=400), {"xg": 1.5})
    with pytest.raises(ContractViolation, match="GELECEKTE"):
        assert_fresh((future,), NOW, max_age=timedelta(days=7), source_id="footystats")


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


def test_record_defaults_threshold_to_three() -> None:
    """Brief'in Produces sözleşmesi `threshold: int = 3` diyor (review #5); varsayılansız
    imza Task 6-10'un TAMAMININ paralel worktree'lerde aynı `TypeError`i üretmesi demek —
    beş ajan aynı hatayı aynı anda yapar. `threshold` burada BİLEREK verilmiyor."""
    cooldown = timedelta(hours=1)
    breaker = Breaker(failures=0, opened_at=None)
    for _ in range(3):
        breaker = record(breaker, NOW, ok=False, cooldown=cooldown)

    assert is_open(breaker, NOW, cooldown=cooldown) is True


def test_normalise_team_strips_legal_suffixes_and_punctuation() -> None:
    from football_edge.naming import normalise_team

    assert normalise_team("  Galatasaray A.Ş. ") == normalise_team("GALATASARAY AŞ")
    assert normalise_team("Gaziantep F.K.") == normalise_team("gaziantep fk")


def test_normalise_team_uses_turkish_case_rules() -> None:
    """Review #2: eski hâli `"I".lower()`ı SİLİP düz `.lower()` koysanız bile YEŞİL
    kalıyordu (ölçüldü) — testin adının bahsettiği kural olmadan da geçen bir test.

    Buradaki üç çift ÖLÇÜLEREK seçildi, "makul" diye değil:
    - `FENERBAHÇE`/`Fenerbahçe`: İ/I yok, yalnız sıradan Türkçe harflerin bozulmadığını
      kanıtlar (regresyon emniyeti, bu kuralı sınamaz).
    - `İstanbulspor`/`Istanbulspor` (NOKTALI büyük İ / ASCII büyük I): review #1'in
      düzelttiği TAM arıza — TFF (windows-1254) doğru Türkçe `İstanbulspor` yayınlar,
      FootyStats ASCII `Istanbulspor` yayınlar. Ölçüldü: İ/I değişimi TAMAMEN silinip
      düz `.lower()`a dönülürse bu çift `'i̇stanbulspor'` (İ'nin Python'ın varsayılan
      `.lower()`ında ürettiği "i" + birleştirici nokta, `_NON_WORD` tarafından boşluğa
      çevrilir) vs `'istanbulspor'` verir — FARKLI, yani KIRMIZI. `naming.py`nin SONUNDAKİ
      `ı`→`i` katlaması (review #1 fix'i) kaldırılırsa da `'ıstanbulspor'` vs
      `'istanbulspor'` kalır — yine FARKLI, yine KIRMIZI. Reviewer'ın önerdiği
      `KASIMPAŞA`/`Kasımpaşa` çifti BURADA KULLANILMADI: aynı ölçümle, review #1'in sonda
      eklediği `ı`→`i` katlamasıyla BİRLİKTE o çift artık AYIRT ETMİYOR (regresyonlu VE
      düzeltilmiş kodda EŞİT sonuç veriyor — iki tarafta da nihai `ı` `i`ye katlanıyor);
      yani #2'nin KENDİ standardını ("test cannot cannot fail") o çift bu bağlamda
      karşılamıyor. Aşağıdaki ALL-CAPS çifti de aynı ayrımı büyük harfte tekrar kanıtlar.
    """
    from football_edge.naming import normalise_team

    assert normalise_team("FENERBAHÇE") == normalise_team("Fenerbahçe")
    assert normalise_team("İstanbulspor") == normalise_team("Istanbulspor")
    assert normalise_team("İSTANBULSPOR") == normalise_team("ISTANBULSPOR")
