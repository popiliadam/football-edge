from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from football_edge.collectors import news, tff, venues
from football_edge.collectors.weather import FORECAST_PATH
from football_edge.leagues import active_leagues, load_leagues
from football_edge.sources import (
    ACCESS_BASIS_API_TERMS,
    Source,
    SourceBlocked,
    allows,
    audit_offline,
    enabled_sources,
    guard_path,
    load_sources,
    robots_for,
    snapshot_from_status,
)

REPO = Path(__file__).resolve().parent.parent

UNDERSTAT_ROBOTS = "User-agent: *\nDisallow: /\n"
# footystats' REAL robots.txt (measured 2026-09-19): "Disallow: /api/club*" / "/*.php" /
# "/matches?*" — wildcards `protego` (R10) parses correctly, unlike stdlib's old
# `urllib.robotparser` (which percent-encoded `*`/`?` into unmatchable literals; see
# `test_wildcard_disallow_actually_blocks_a_matching_path` below for a fixture dedicated to
# proving that). What THIS fixture still exists to prove is independent of wildcard support:
# a UA-specific block fully REPLACES the `*` block for that agent (RFC 9309 precedence). The
# real `User-agent: ClaudeBot` stanza here carries only `Crawl-delay`, so ClaudeBot is exempt
# from every `*` rule, wildcard or not — that's real (footystats.org's live robots.txt has
# this exact shape) and it's exactly the exemption R9 says we must not exploit by presenting
# as ClaudeBot. To keep this test meaningful (an allowed path passes, a disallowed path
# raises) despite that exemption, the ClaudeBot block carries its own literal
# `Disallow: /c-dl.php` — the `*` block's rules are restored to the real wildcarded form
# since `guard_path(parser, footystats, "/c-dl.php")` still doesn't depend on them.
FOOTYSTATS_ROBOTS = (
    "User-agent: ClaudeBot\nCrawl-delay: 1\nDisallow: /c-dl.php\n\n"
    "User-agent: *\nDisallow: /api/club*\nDisallow: /*.php\nDisallow: /matches?*\n"
)
AJANSSPOR_ROBOTS = (
    "User-agent: *\n"
    "Content-Signal: ai-train=no, search=yes, ai-input=yes\n"
    "Disallow: /lineup/\nDisallow: /mac/\nDisallow: /oyuncu/\nDisallow: /lig/\n"
)


def source(**overrides: object) -> Source:
    base = {
        "id": "footystats",
        "base_url": "https://footystats.org",
        "user_agent": "ClaudeBot/1.0 (+https://anthropic.com/claudebot)",
        "crawl_delay_seconds": 1.0,
        "robots_verified_at": date(2026, 9, 19),
        "declared_paths": ("/turkey/super-lig/xg",),
        "enabled": True,
        "note": "",
        "access_basis": "robots",
        "terms_url": "",
    }
    return Source(**{**base, **overrides})  # type: ignore[arg-type]


def write_robots(directory: Path, source_id: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{source_id}.txt"
    target.write_text(body, encoding="utf-8")
    return target


def test_site_wide_disallow_blocks_every_path(tmp_path: Path) -> None:
    """Understat: `User-agent: * / Disallow: /`. Spec §3.2/1 — taranmaz."""
    write_robots(tmp_path, "understat", UNDERSTAT_ROBOTS)
    understat = source(id="understat", base_url="https://understat.com")
    parser = robots_for(understat, tmp_path)

    assert allows(parser, understat, "/league/EPL") is False
    assert allows(parser, understat, "/") is False


def test_allowed_path_passes_and_disallowed_path_raises(tmp_path: Path) -> None:
    """Documents the behaviour R9 forbids us from exploiting: `source()`'s ClaudeBot
    user_agent gets its own group with no Disallow rules of its own, exempting it from the
    `*` block entirely (RFC 9309 group precedence — correctly implemented by both stdlib and
    `protego`; this was never the stdlib-specific bug). That exemption is real —
    footystats.org's live robots.txt has this identical shape. `config/sources.yaml` does NOT
    configure footystats with this user_agent: presenting as Anthropic's crawler to receive
    an allowance granted to Anthropic, not to us, would be user-agent spoofing. This test's
    `FOOTYSTATS_ROBOTS` fixture keeps the ClaudeBot exemption on purpose, so the exemption's
    existence stays proven in code, not just asserted in prose.
    """
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    footystats = source()
    parser = robots_for(footystats, tmp_path)

    guard_path(parser, footystats, "/turkey/super-lig/xg")  # patlamamalı
    with pytest.raises(SourceBlocked, match="footystats"):
        guard_path(parser, footystats, "/c-dl.php")


def test_ajansspor_structural_paths_are_closed_but_news_is_open(tmp_path: Path) -> None:
    """robots `/lineup/`, `/mac/`, `/oyuncu/`, `/lig/` kapatıyor — muhtemel 11 ALINMAZ."""
    write_robots(tmp_path, "ajansspor", AJANSSPOR_ROBOTS)
    ajansspor = source(id="ajansspor", base_url="https://ajansspor.com", crawl_delay_seconds=1.0)
    parser = robots_for(ajansspor, tmp_path)

    assert allows(parser, ajansspor, "/lineup/galatasaray") is False
    assert allows(parser, ajansspor, "/mac/12345") is False
    assert allows(parser, ajansspor, "/futbol/galatasaray-haberleri") is True


def test_empty_robots_file_allows_everything(tmp_path: Path) -> None:
    """TFF'de robots.txt YOK (404) ve ClubElo'nunki boş. Boş politika = kısıt yok.

    Ayrım hâlâ iki farklı şeyi karıştırmama meselesi, ama artık farklı bir mekanizmayla:
    "hiç ölçülmedi" (anlık görüntü dosyası hiç yok) `audit_offline`'ın AYRI, dosya
    varlığına bakan kontrolüdür ve `robots_for()` o durumda hiç çağrılmaz. Bu test onun
    yerine "ölçüldü ve boş çıktı" durumunu sınar: `robots_for()` dosyayı okur okumaz
    `Protego.parse(body)` çağırır (stdlib'in "hiç parse edilmemişse False döner" tuzağı
    protego'da YOK — `robots_for` koşulsuz parse eder), ve `Protego.parse("")` her yola
    izin verir. İkisini karıştırmak izinli bir kaynağı sessizce kapatırdı.
    """
    write_robots(tmp_path, "tff", "")
    tff = source(id="tff", base_url="https://www.tff.org")
    parser = robots_for(tff, tmp_path)

    assert allows(parser, tff, "/Default.aspx?pageID=600") is True


def test_missing_snapshot_is_a_violation_not_a_pass(tmp_path: Path) -> None:
    """Anlık görüntü yoksa kapı YEŞİL VERMEZ. Ölçülmemiş politika, izin değildir."""
    violations = audit_offline((source(),), tmp_path, date(2026, 9, 19))
    assert any("anlık görüntü yok" in text for text in violations)


def test_declared_path_that_robots_forbids_is_a_violation(tmp_path: Path) -> None:
    """Toplayıcının beyan ettiği yol robots'a uymuyorsa, kod yazılmadan kapı kırmızı verir."""
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    violations = audit_offline(
        (source(declared_paths=("/turkey/super-lig/xg", "/c-dl.php")),),
        tmp_path,
        date(2026, 9, 19),
    )
    assert any("/c-dl.php" in text for text in violations)


def test_stale_verification_is_a_violation(tmp_path: Path) -> None:
    """robots 30 günden eski ölçüldüyse 'izinli' bir iddia değil, bir hatıradır."""
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    violations = audit_offline((source(),), tmp_path, date(2026, 11, 1))
    assert any("30 günden eski" in text for text in violations)


def test_future_dated_verification_is_a_violation_not_a_year_of_freshness(tmp_path: Path) -> None:
    """`today - verified_at` bir GELECEK tarih için hep negatif kalır, yani hep
    `max_age_days`den küçüktür — düzeltilmezse bu, tazelik kontrolünü sessizce söndürür
    (bir yazım hatasının kapıyı bir yıllığına kapatması gerekmez)."""
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    violations = audit_offline(
        (source(robots_verified_at=date(2027, 9, 19)),), tmp_path, date(2026, 9, 19)
    )
    assert any("gelecekte" in text for text in violations), violations


def test_disabled_sources_are_not_audited(tmp_path: Path) -> None:
    """Kapalı kaynak taranmıyor; anlık görüntüsü eksik diye kapı kırmızı vermez."""
    assert audit_offline((source(enabled=False),), tmp_path, date(2026, 9, 19)) == ()


def test_registry_loads_and_filters(tmp_path: Path) -> None:
    target = tmp_path / "sources.yaml"
    target.write_text(
        "sources:\n"
        "  - id: footystats\n"
        "    base_url: https://footystats.org\n"
        "    user_agent: ClaudeBot/1.0\n"
        "    crawl_delay_seconds: 1.0\n"
        "    robots_verified_at: 2026-09-19\n"
        "    declared_paths: ['/turkey/super-lig/xg']\n"
        "    enabled: true\n"
        "    note: ''\n"
        "    access_basis: robots\n"
        "    terms_url: ''\n"
        "  - id: understat\n"
        "    base_url: https://understat.com\n"
        "    user_agent: ClaudeBot/1.0\n"
        "    crawl_delay_seconds: 1.0\n"
        "    robots_verified_at: 2026-09-19\n"
        "    declared_paths: []\n"
        "    enabled: false\n"
        "    note: 'robots.txt Disallow: / — spec §3.2/1'\n"
        "    access_basis: robots\n"
        "    terms_url: ''\n",
        encoding="utf-8",
    )
    loaded = load_sources(target)

    assert len(loaded) == 2
    assert tuple(entry.id for entry in enabled_sources(loaded)) == ("footystats",)
    assert loaded[0].robots_verified_at == date(2026, 9, 19)


# ── R7 (then R10): a blank line mid-block must not silently drop the rules after it ─────────
# Found while re-verifying wikidata's disable: the real robots.txt has a SINGLE
# "User-agent: *" line (148) and never repeats it again in the whole 446-line file, but has
# blank lines at 422/423/425 while still mid-block. stdlib's old `RobotFileParser.parse()`
# treated ANY blank line while state==2 (at least one Disallow/Allow already seen) as ending
# that group, WITHOUT requiring a fresh "User-agent:" line — RFC 9309 says only a new
# User-agent line (or EOF) ends a group. Rules after such a stray blank line were silently
# dropped, appended to no entry at all. `protego` (R10) never had this bug — this test now
# guards a `protego` property instead of a stdlib workaround, kept because the scenario is
# real (wikidata's own file) and worth pinning regardless of which parser sits underneath.

BLANK_LINE_MID_BLOCK_ROBOTS = "User-agent: *\nDisallow: /a\n\nDisallow: /b\n"


def test_blank_line_mid_block_does_not_drop_the_rule_that_follows(tmp_path: Path) -> None:
    """`Disallow: /b` has no `User-agent:` line of its own — it continues the `*` block above
    the blank line. A parser that treats the blank line as ending the group drops it, and `/b`
    comes back allowed by accident (no rule matches it) rather than by policy."""
    write_robots(tmp_path, "blankmid", BLANK_LINE_MID_BLOCK_ROBOTS)
    blankmid = source(id="blankmid", base_url="https://blankmid.example")
    parser = robots_for(blankmid, tmp_path)

    assert allows(parser, blankmid, "/a") is False
    assert allows(parser, blankmid, "/b") is False


# ── R10: protego must actually implement the two RFC 9309 properties stdlib lacked ──────────
# Without these two tests, a future revert to (or copy of) stdlib's `urllib.robotparser` would
# pass every other test in this file silently — none of the others exercise a wildcard pattern
# or a specificity conflict on their own. These are what keep the guard honest.


def test_wildcard_disallow_actually_blocks_a_matching_path(tmp_path: Path) -> None:
    """`Disallow: /*.php` must block `/anything.php` — this is the exact pattern footystats'
    and ajansspor's real robots.txt use, and the exact pattern stdlib's `RuleLine` silently
    turned into an unmatchable literal (`%2A.php`) by percent-encoding the `*`."""
    write_robots(tmp_path, "wildcard", "User-agent: *\nDisallow: /*.php\n")
    wildcard_source = source(id="wildcard", base_url="https://wildcard.example")
    parser = robots_for(wildcard_source, tmp_path)

    assert allows(parser, wildcard_source, "/anything.php") is False
    assert allows(parser, wildcard_source, "/anything.html") is True


LONGEST_MATCH_ROBOTS = (
    "User-agent: *\nDisallow: /wiki/Special:\nAllow: /wiki/Special:EntityData/*.\n"
)


def test_longest_match_lets_a_narrow_allow_override_a_broad_disallow(tmp_path: Path) -> None:
    """This is wikidata's own robots.txt shape (Disallow: /wiki/Special: precedes, in file
    order, the narrower Allow it's meant to carve an exception out of). stdlib's
    `Entry.allowance()` returned the first matching rule in FILE ORDER, so the broad,
    earlier `Disallow` always won — RFC 9309 requires the LONGEST/most specific matching
    rule to win regardless of order, which is why Wikidata's own robots.txt author could
    write the broad rule first at all."""
    write_robots(tmp_path, "longestmatch", LONGEST_MATCH_ROBOTS)
    longest_source = source(id="longestmatch", base_url="https://longestmatch.example")
    parser = robots_for(longest_source, tmp_path)

    assert allows(parser, longest_source, "/wiki/Special:EntityData/Q170980.json") is True
    assert allows(parser, longest_source, "/wiki/Special:SomethingElse") is False


# ── R8: access_basis=api_terms — robots.txt does not govern a documented API's client ───────


def test_api_terms_source_without_a_terms_url_fails_the_audit(tmp_path: Path) -> None:
    """The exception can never become an unexplained footnote: no terms_url, no pass."""
    api_source = source(
        id="openmeteo",
        base_url="https://api.open-meteo.com",
        declared_paths=("/v1/forecast",),
        access_basis=ACCESS_BASIS_API_TERMS,
        terms_url="",
    )
    violations = audit_offline((api_source,), tmp_path, date(2026, 9, 19))

    assert any("terms_url" in text for text in violations), violations


def test_api_terms_source_with_a_terms_url_skips_the_robots_path_check(tmp_path: Path) -> None:
    """openmeteo's REAL robots.txt is `Disallow: /` for everyone — if `access_basis` didn't
    bypass the robots check, this source could never pass the audit no matter what its terms
    say. It must pass anyway, on the strength of `terms_url` alone."""
    write_robots(tmp_path, "openmeteo", "User-agent: *\nDisallow: /\n")
    api_source = source(
        id="openmeteo",
        base_url="https://api.open-meteo.com",
        declared_paths=("/v1/forecast",),
        access_basis=ACCESS_BASIS_API_TERMS,
        terms_url="https://open-meteo.com/en/terms",
    )
    violations = audit_offline((api_source,), tmp_path, date(2026, 9, 19))

    assert violations == ()
    # And guard_path must not raise either — this is what a real collector calls at fetch time.
    parser = robots_for(api_source, tmp_path)
    guard_path(parser, api_source, "/v1/forecast")  # must not raise


def test_registry_rejects_an_unrecognised_access_basis(tmp_path: Path) -> None:
    """A typo'd `access_basis` (e.g. `robot` for `robots`) must not silently fall through to
    whatever `Source.access_basis` happens to compare against — it must fail to load."""
    target = tmp_path / "sources.yaml"
    target.write_text(
        "sources:\n"
        "  - id: footystats\n"
        "    base_url: https://footystats.org\n"
        "    user_agent: football-edge/0.1\n"
        "    crawl_delay_seconds: 1.0\n"
        "    robots_verified_at: 2026-09-19\n"
        "    declared_paths: []\n"
        "    enabled: true\n"
        "    note: ''\n"
        "    access_basis: robot\n"  # typo: should be 'robots'
        "    terms_url: ''\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="access_basis"):
        load_sources(target)


# ── #M13 (deferred, kapatıldı Faz 1 SON inceleme) — declared_paths TİPİ doğrulanmalı ────────


def test_registry_rejects_a_scalar_declared_paths(tmp_path: Path) -> None:
    """`declared_paths: /turkey/super-lig/xg` (tırnaksız, listesiz) GEÇERLİ YAML'dır — bir
    LİSTE değil, DÜZ BİR DİZEDİR. Doğrulama olmadan `load_sources`teki `tuple(entry[
    "declared_paths"])` bunu karakterlere böler: `('/', 't', 'u', 'r', ...)`. Kapı sonra bu
    "yolları" robots'a karşı harf harf, sessizce ve anlamsızca sorar — kırmızı da vermez,
    doğru da ölçmez."""
    target = tmp_path / "sources.yaml"
    target.write_text(
        "sources:\n"
        "  - id: footystats\n"
        "    base_url: https://footystats.org\n"
        "    user_agent: football-edge/0.1\n"
        "    crawl_delay_seconds: 1.0\n"
        "    robots_verified_at: 2026-09-19\n"
        "    declared_paths: /turkey/super-lig/xg\n"  # skaler, liste DEĞİL
        "    enabled: true\n"
        "    note: ''\n"
        "    access_basis: robots\n"
        "    terms_url: ''\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="declared_paths"):
        load_sources(target)


# ── #M20 (deferred, kapatıldı Faz 1 SON inceleme) — boş declared_paths hiçbir şey ölçmez ────


def test_enabled_robots_source_with_empty_declared_paths_is_a_violation(tmp_path: Path) -> None:
    """`enabled: true` + `declared_paths: []` eskiden bu denetimden HİÇBİR YOL sınanmadan
    TEMİZ çıkıyordu — döngü boş demette no-op. Anlık görüntü VARSA (aşağıda öyle) ve
    tazelikse, TEK eksik sinyal declared_paths'in boşluğuydu; artık bu da adıyla kırmızı."""
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    violations = audit_offline((source(declared_paths=()),), tmp_path, date(2026, 9, 19))
    assert any("declared_paths boş" in text for text in violations), violations


def test_enabled_api_terms_source_with_empty_declared_paths_is_not_flagged(tmp_path: Path) -> None:
    """`access_basis=api_terms` kaynaklarda `declared_paths` zaten robots kararını
    etkilemiyor (`allows()` onu hiç sormuyor) — M20'nin boşluk kontrolü bu kaynak sınıfını
    KAPSAMAZ, yanlış alarm vermez."""
    write_robots(tmp_path, "openmeteo", "User-agent: *\nDisallow: /\n")
    api_source = source(
        id="openmeteo",
        base_url="https://api.open-meteo.com",
        declared_paths=(),
        access_basis=ACCESS_BASIS_API_TERMS,
        terms_url="https://open-meteo.com/en/terms",
    )
    violations = audit_offline((api_source,), tmp_path, date(2026, 9, 19))

    assert not any("declared_paths boş" in text for text in violations), violations


# ── R15: what an HTTP status means for a live robots.txt check — moved here from
# scripts/robots_drift.py because it is source-policy logic, not script plumbing, and
# because it is the newest safety-relevant branch this project has (review Important #1
# fixed it; review R15 moved the decision where the gate can see it). The 404-vs-403 cases
# below are the whole point: a bug that made both return the same thing (either "" or None)
# would pass a test suite that didn't assert them separately — these do.


@pytest.mark.parametrize(
    ("status_code", "body", "expected"),
    [
        (200, "User-agent: *\nDisallow: /x\n", "User-agent: *\nDisallow: /x\n"),
        (404, "this body must never leak through — 404 means no policy file", ""),
        (410, "this body must never leak through — 410 means no policy file", ""),
        (403, "Forbidden", None),
        (429, "Too Many Requests", None),
        (500, "Internal Server Error", None),
    ],
)
def test_snapshot_from_status_distinguishes_no_policy_from_unmeasured(
    status_code: int, body: str, expected: str | None
) -> None:
    """200 carries the real body through untouched (proves the body isn't discarded).
    404/410 collapse to "" — measured, no policy file (tff's real, committed shape).
    403/429/500 must NOT collapse to "" too — they're None (unmeasured, a source that may
    be blocking us), a genuinely different outcome from 404's "" that a caller must treat
    differently (scripts/robots_drift.py fails the run on None; it does not on "")."""
    assert snapshot_from_status(status_code, body) == expected


# ── #M28 / M-1 (deferred, kapatıldı Faz 1 SON inceleme) — declared_paths'i toplayıcının
# GERÇEKTEN fetch ettiği yollara bağlayan hiçbir test yoktu. `sources.audit_offline`
# yalnız `declared_paths`in robots'a UYUP UYMADIĞINI denetler; beyan edilmemiş bir fetch'i
# hiç görmez. Bu test YALNIZ o yönü bağlar: fetch edilen ⊆ declared. Ters yön — declared
# ama hiç fetch edilmeyen; `pageID=246` böyle yaşadı (artık kaldırıldı), ajansspor'un
# `/sitemap`i bilinçli — HİÇBİR testle bağlı DEĞİL; HANDOFF §3 madde 32'de adıyla yazılı
# (Ruling R59).
#
# openmeteo yalnız BAZ yolunu taşır (`FORECAST_PATH`, sorgu dizesiz): `_forecast_path`nin
# ürettiği GERÇEK istek zorunlu `latitude`/`longitude` sorgu parametreleri taşır ve
# `declared_paths` bunu hiç ifade edemez (DEFERRED §9.1d, ayrı ve bilinçli bir boşluk) —
# ama `access_basis=api_terms` olduğu için robots.txt zaten hiç sorulmuyor (R8); burada
# sınanan yalnız kayıt defterinin bu kaynağı BAZ yoluyla tanıdığıdır.


def _collector_fetched_paths() -> tuple[tuple[str, str], ...]:
    leagues = active_leagues(load_leagues(REPO / "config/leagues.yaml"))
    # Yolu olmayan lig footystats'ta HİÇ istenmez (`collect_footystats` atlar) — beyan da gerekmez.
    pairs: tuple[tuple[str, str], ...] = tuple(
        ("footystats", league.footystats_path)
        for league in leagues
        if league.footystats_path is not None
    )
    pairs += (("tff", tff.REFEREE_PATH),)
    pairs += tuple(("wikidata", venues.ENTITY_PATH.format(qid=spec.qid)) for spec in venues.VENUES)
    pairs += (("openmeteo", FORECAST_PATH),)
    pairs += tuple(news._ARTICLE_PATHS.items())  # anahtar = adaptörün kaynak id'si
    return pairs


@pytest.mark.parametrize(
    ("source_id", "path"),
    _collector_fetched_paths(),
    ids=[f"{s}:{p}" for s, p in _collector_fetched_paths()],
)
def test_each_collectors_fetched_path_is_declared(source_id: str, path: str) -> None:
    """Gerçek `config/sources.yaml` + `config/leagues.yaml`e karşı: her toplayıcının
    GERÇEKTEN istediği yol, o kaynağın `declared_paths`inde OLMALI — aksi hâlde
    `kaynak-politikası` adımı o yolu robots'a karşı HİÇ sormaz, sessizce."""
    registry = load_sources(REPO / "config/sources.yaml")
    source_entry = next(entry for entry in registry if entry.id == source_id)

    assert path in source_entry.declared_paths, (
        f"{source_id}: {path!r} fetch ediliyor ama declared_paths'te YOK — "
        "kaynak-politikası kapısı bu yolu hiç denetlemiyor"
    )
