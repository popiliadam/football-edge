"""`verify-snapshot` (§5.1): DB'siz denetim — H1/H2/H3/H5, §4.3 yasak anahtarlar, sıra, hash.

Her ihlal fixture'ın küçük bir kopyasında kurulur; kopya yeniden hash'lenir ki yalnız sınanan kural
kırmızı versin (hash kuralı kendi testinde).
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from football_edge.site import __main__ as cli
from football_edge.site import verify
from football_edge.site.contract import EXIT_SITE_INVALID, content_sha256
from football_edge.site.slugs import match_slug, slugify
from football_edge.site.verify import snapshot_errors

REPO = Path(__file__).resolve().parent.parent
SCHEMA: dict[str, Any] = json.loads(
    (REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8")
)
BASE = REPO / "web/fixtures/snapshot.fixture.json"
FULL_RECORD = REPO / "web/fixtures/snapshot.fixture-record.json"


def _fixture(path: Path = BASE) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _broken(change: Callable[[dict[str, Any]], None], path: Path = BASE) -> list[str]:
    snapshot = copy.deepcopy(_fixture(path))
    change(snapshot)
    snapshot["content_sha256"] = content_sha256(snapshot)
    return snapshot_errors(snapshot, SCHEMA)


def _set(path: str, value: Any) -> Callable[[dict[str, Any]], None]:
    """`matches.0.home` gibi noktalı yolun hedefine değer yazar."""

    def change(snapshot: dict[str, Any]) -> None:
        node: Any = snapshot
        *parents, last = path.split(".")
        for part in parents:
            node = node[int(part)] if isinstance(node, list) else node[part]
        node[int(last) if isinstance(node, list) else last] = value

    return change


@pytest.mark.parametrize("path", [BASE, FULL_RECORD], ids=lambda path: path.name)
def test_the_fixtures_pass_every_rule(path: Path) -> None:
    assert snapshot_errors(_fixture(path), SCHEMA) == []


@pytest.mark.leakage
def test_a_match_before_the_floor_is_red() -> None:
    """H1e: taban komşusu (2026-07-01) anlık görüntüde olamaz."""

    def before_floor(snapshot: dict[str, Any]) -> None:
        snapshot["matches"][0]["commence_time"] = "2026-07-01T23:59:59Z"
        snapshot["matches"][0]["date"] = "2026-07-01"

    errors = _broken(before_floor)

    assert any("commence_time: holdout tabanından eski" in error for error in errors), errors


@pytest.mark.leakage
def test_an_old_date_in_any_string_is_red_whatever_the_key() -> None:
    errors = _broken(_set("teams.0.name", "Alfa 2026-01-15"))

    assert any("$.teams[0].name: holdout tabanından eski tarih" in e for e in errors), errors


@pytest.mark.parametrize("text", ["http://x.invalid", "HTTPS://X", "a<b", "a>b"])
def test_links_and_markup_in_a_data_string_are_red(text: str) -> None:
    """H2c."""
    errors = _broken(_set("matches.0.home", text))

    assert any("$.matches[0].home: bağlantı ya da işaretleme" in e for e in errors), errors


@pytest.mark.parametrize(
    "text",
    [
        "postgres" + "://u@h/d",
        "postgresql" + "://u@h/d",
        "service" + "_role",
        "eyJ" + "hbGciOi",
        "SUPABASE" + "_ANON",
        "NETLIFY" + "_AUTH_TOKEN",
    ],
)
def test_credential_patterns_are_red_and_the_value_is_not_echoed(text: str) -> None:
    """H5b: hata metni yolu ve kuralı söyler; değeri basmaz (log public)."""
    value = f"önek {text} sonek"
    errors = _broken(_set("leagues.0.country", value))

    assert any("$.leagues[0].country:" in error and "(H5)" in error for error in errors), errors
    assert all(value not in error for error in errors)


def test_a_forbidden_key_is_red_at_any_depth_even_when_the_schema_also_fails() -> None:
    """§4.3: `additionalProperties: false` bilinmeyeni durdurur; yasak anahtar ADIYLA da görünür."""
    errors = _broken(_set("matches.0.h2h.latest.price", 2.1))

    assert any("$.matches[0].h2h.latest.price: yayımlanmayan anahtar" in e for e in errors)


def test_a_value_badge_is_red() -> None:
    """H3/B6."""
    errors = _broken(_set("value_badge", {"match_id": "x"}))

    assert any("$.value_badge" in error for error in errors), errors


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        (lambda s: s["matches"].reverse(), "$.matches[1]: sıra bozuk"),
        (lambda s: s["teams"].reverse(), "$.teams[1]: sıra bozuk"),
        (lambda s: s["leagues"].reverse(), "$.leagues[1]: sıra bozuk"),
    ],
)
def test_every_array_must_follow_its_declared_order(
    change: Callable[[dict[str, Any]], None], needle: str
) -> None:
    """N3: sıralı diziler; `sorted` kaldırılırsa kırmızı bu testten gelir."""
    assert any(needle in error for error in _broken(change)), needle


def test_a_record_entry_out_of_order_is_red() -> None:
    errors = _broken(lambda s: s["record"]["entries"].reverse(), FULL_RECORD)

    assert any("$.record.entries[1]: sıra bozuk" in error for error in errors), errors


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        (_set("matches.0.h2h.opening.p.home", 46.12), "$.matches[0].h2h.opening.p.home: 1 ondalık"),
        (_set("matches.0.move.home", 3.75), "$.matches[0].move.home: 1 ondalık"),
        (_set("leagues.0.move_distribution.p50", 3.14), "move_distribution.p50: 1 ondalık"),
    ],
)
def test_numbers_travel_at_display_precision(
    change: Callable[[dict[str, Any]], None], needle: str
) -> None:
    """§5.4: TS yuvarlamaz; fazla hassasiyet kırmızıdır."""
    assert any(needle in error for error in _broken(change)), needle


def test_a_clv_with_three_decimals_is_red() -> None:
    errors = _broken(_set("record.entries.0.clv", 2.145), FULL_RECORD)

    assert any("$.record.entries[0].clv: 2 ondalıktan fazla" in e for e in errors), errors


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        (_set("record.published", 1), "$.record.published"),
        (_set("leagues.0.matches", 99), "$.leagues[0].matches"),
        (_set("teams.0.matches", 9), "$.teams[0].matches"),
        (_set("teams.1.indexable", True), "$.teams[1].indexable"),
        (_set("matches.0.path_id", "000000000000"), "$.matches[0].path_id"),
        (_set("matches.0.slug", "x-vs-y"), "$.matches[0].slug"),
        (_set("matches.0.date", "2026-09-30"), "$.matches[0].date"),
        (_set("leagues.0.slug", "track-record"), "$.leagues[0].slug"),
        (_set("leagues.0.slug", "data"), "$.leagues[0].slug"),
        (_set("leagues.1.slug", "kuzey-ligi"), "$.leagues: slug tekrarı"),
        (_set("teams.0.slug", "match"), "$.teams[0].slug"),
        (_set("ledger.anchor.last_id", 10**6), "$.ledger.anchor"),
    ],
)
def test_internal_consistency(change: Callable[[dict[str, Any]], None], needle: str) -> None:
    assert any(needle in error for error in _broken(change)), needle


def _before_floor(snapshot: dict[str, Any]) -> None:
    snapshot["matches"][0]["commence_time"] = "2026-07-01T23:59:59Z"
    snapshot["matches"][0]["date"] = "2026-07-01"


@pytest.mark.leakage
def test_the_floor_rule_stands_alone_when_the_date_scan_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H1: kat kuralı, tarama kırılırsa savunmadır; mesajı taramanınkinden ayrıdır (`tarih` yok)."""
    monkeypatch.setattr(verify, "_date_errors", lambda snapshot, known: iter(()))

    errors = _broken(_before_floor)

    assert "$.matches[0].commence_time: holdout tabanından eski (H1)" in errors, errors


def _drop(key: str) -> Callable[[dict[str, Any]], None]:
    """Dizinin SON öğesini atar: `tst.2` ligi ya da `zeta-rovers` takımı."""

    def change(snapshot: dict[str, Any]) -> None:
        snapshot[key].pop()

    return change


def _rename_team(old: str, new: str) -> Callable[[dict[str, Any]], None]:
    """Takımı her yerde tutarlı yeniden adlandırır; yalnız sınanan kural kırmızı kalsın."""

    def change(snapshot: dict[str, Any]) -> None:
        for team in snapshot["teams"]:
            if team["name"] == old:
                team["name"], team["slug"] = new, slugify(new)
        for match in snapshot["matches"]:
            match["home"] = new if match["home"] == old else match["home"]
            match["away"] = new if match["away"] == old else match["away"]
            match["slug"] = match_slug(match["home"], match["away"])

    return change


def _same_cut_other_head(snapshot: dict[str, Any]) -> None:
    anchor, ledger = snapshot["ledger"]["anchor"], snapshot["ledger"]
    anchor["rows"], anchor["last_id"] = ledger["rows"], ledger["last_id"]


@pytest.mark.parametrize(
    ("change", "needle", "path"),
    [
        (_set("ledger.rows", 138), "$.ledger: satır sayısı son kimliği aşıyor", BASE),
        (
            _set("record.summary", None),
            "$.record.summary: yalnız boş sicilde null olur",
            FULL_RECORD,
        ),
        (_set("record.summary.n", 3), "$.record.summary.n: yayın sayısıyla uyuşmuyor", FULL_RECORD),
        (_set("matches.0.rounds", 0), "$.matches[0].rounds: kesimde satırı olmayan maç", BASE),
        (_drop("leagues"), "$.matches[5].league_id: bilinmeyen lig", BASE),
        (_drop("leagues"), "$.teams[4].league_id: bilinmeyen lig", BASE),
        (_drop("teams"), "$.teams: maçlardaki takım kümesiyle uyuşmuyor", BASE),
        (_rename_team("Beta FK", "Match"), "$.teams[1].slug: ayrılmış bölüt (§8.1)", BASE),
        (
            _same_cut_other_head,
            "$.ledger.anchor.head: aynı kesimde farklı baş hash (çatallanmış zincir)",
            BASE,
        ),
        (
            _set("ledger.anchor.file", "head-2026-09-25.txt"),
            "$.ledger.anchor.file: dışa aktarım gününden ileri tarihli çıpa",
            BASE,
        ),
    ],
    ids=[
        "ledger-rows",
        "summary-null",
        "summary-n",
        "rounds",
        "match-league",
        "team-league",
        "team-set",
        "reserved-team",
        "anchor-head",
        "anchor-future",
    ],
)
def test_every_rule_branch_names_its_own_rule(
    change: Callable[[dict[str, Any]], None], needle: str, path: Path
) -> None:
    """Her kural kolu KENDİ mesajıyla kırmızı; kol silinirse bu test kırmızı (inceleme I1, M5)."""
    assert needle in _broken(change, path), needle


def test_a_team_called_match_is_reserved_not_underived() -> None:
    errors = _broken(_rename_team("Beta FK", "Match"))

    assert "$.teams[1].slug: addan türemiyor (§8.2)" not in errors, errors


def test_an_anchor_dated_on_the_export_day_is_fine() -> None:
    assert _broken(_set("ledger.anchor.file", "head-2026-09-24.txt")) == []


def test_a_team_name_without_a_slug_is_a_named_violation() -> None:
    """`ЦСКА` slug üretmez; `slugify`in ValueError'ı istisna olarak kaçmaz (inceleme M1)."""
    errors = _broken(_set("teams.1.name", "ЦСКА"))

    assert "$.teams[1].name: slug üretmiyor, harf ya da rakam yok (§8.2)" in errors, errors


def test_a_match_with_a_slugless_team_name_is_a_named_violation() -> None:
    errors = _broken(_set("matches.0.home", "ЦСКА"))

    assert "$.matches[0].slug: takım adından slug üretilemiyor (§8.2)" in errors, errors


def test_a_lone_surrogate_is_a_named_violation() -> None:
    """Eşleşmemiş vekil UTF-8'e yazılamaz; hash'e ulaşmadan adıyla kırmızı (inceleme M1)."""
    snapshot = _fixture()
    snapshot["leagues"][0]["country"] = "Nord\ud800land"

    errors = snapshot_errors(snapshot, SCHEMA)

    assert "$.leagues[0].country: UTF-8'e kodlanamayan karakter (eşleşmemiş vekil)" in errors


@pytest.mark.parametrize(
    "key", ["postgresql" + "://u:S3CRETPW@h/d", "satır\nsonu http", "Nord\ud800land"]
)
def test_an_unknown_key_is_not_echoed(key: str) -> None:
    """İnceleme M2: saldırgan anahtar adı da değer gibi loga basılmaz; yol sırasını söyler."""
    snapshot = _fixture()
    snapshot["leagues"][0][key] = "http://x.invalid"  # yolu basan bir tarama kuralı da ateşlesin

    errors = snapshot_errors(snapshot, SCHEMA)

    assert "$.leagues[0]: bilinmeyen anahtar (ad basılmaz)" in errors, errors
    assert all(key not in error and "\n" not in error for error in errors), errors
    assert any(error.startswith("$.leagues[0].<bilinmeyen anahtar #6>") for error in errors)


def test_a_league_slug_need_not_follow_the_league_name() -> None:
    """I3: lig slug'ı yapılandırmadandır (`ger.1`/`aut.1` ikisi de "Bundesliga")."""
    assert _broken(_set("leagues.0.slug", "kuzey-bolgesi")) == []


def test_an_unsealed_match_cannot_show_a_closing_round() -> None:
    def closing_on_unsealed(snapshot: dict[str, Any]) -> None:
        unsealed = next(m for m in snapshot["matches"] if not m["sealed"])
        unsealed["h2h"]["closing"] = unsealed["h2h"]["latest"]

    assert any("mühürsüz maçta kapanış" in error for error in _broken(closing_on_unsealed))


def test_a_stale_content_hash_is_red() -> None:
    snapshot = _fixture()
    snapshot["matches"][0]["rounds"] += 1  # hash yeniden hesaplanmadı

    assert any("$.content_sha256" in error for error in snapshot_errors(snapshot, SCHEMA))


def _cli(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "football_edge.site", "verify-snapshot", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"},
        check=False,
    )


def test_the_cli_accepts_a_fixture_and_rejects_a_broken_copy(tmp_path: Path) -> None:
    broken = _fixture()
    broken["matches"][0]["home"] = "http://x.invalid"
    target = tmp_path / "snapshot.json"
    target.write_text(json.dumps(broken), encoding="utf-8")

    good, bad = _cli(str(BASE)), _cli(str(target))

    assert good.returncode == 0, good.stdout + good.stderr
    assert bad.returncode == EXIT_SITE_INVALID
    assert "ANLIK GÖRÜNTÜ İHLALİ: $.matches[0].home" in bad.stdout
    assert "http://x.invalid" not in bad.stdout + bad.stderr


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_the_cli_refuses_non_json_constants_at_load_time(tmp_path: Path, token: str) -> None:
    """RFC 8259'da NaN/Infinity yok; `json.loads` onları kabul eder, B-2'nin `JSON.parse`ı etmez."""
    text = BASE.read_text(encoding="utf-8").replace('"rounds": 1', f'"rounds": {token}', 1)
    assert token in text
    target = tmp_path / "snapshot.json"
    target.write_text(text, encoding="utf-8")

    result = _cli(str(target))

    assert result.returncode == EXIT_SITE_INVALID
    assert "ANLIK GÖRÜNTÜ İHLALİ: snapshot.json: JSON dışı sabit (NaN/Infinity)" in result.stdout


def test_the_cli_refuses_a_file_that_is_not_json(tmp_path: Path) -> None:
    target = tmp_path / "snapshot.json"
    target.write_text(BASE.read_text(encoding="utf-8")[:-20], encoding="utf-8")

    result = _cli(str(target))

    assert result.returncode == EXIT_SITE_INVALID
    assert "ANLIK GÖRÜNTÜ İHLALİ: snapshot.json: geçerli JSON değil" in result.stdout
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ("[" * 2000 + "]" * 2000, "snapshot.json: iç içelik ayrıştırıcının sınırını aşıyor"),
        ("[" * 100_000 + "]" * 100_000, "snapshot.json: iç içelik ayrıştırıcının sınırını aşıyor"),
        ("\ufeff{}", "snapshot.json: geçerli JSON değil"),
    ],
    ids=["depth-2000", "depth-100000", "bom"],
)
def test_the_cli_names_unparseable_input(tmp_path: Path, body: str, needle: str) -> None:
    """İnceleme M1/M6d: traceback + exit 1 yerine adlandırılmış satır + exit 24."""
    target = tmp_path / "snapshot.json"
    target.write_text(body, encoding="utf-8")

    result = _cli(str(target))

    assert result.returncode == EXIT_SITE_INVALID, result.stdout + result.stderr
    assert f"ANLIK GÖRÜNTÜ İHLALİ: {needle}" in result.stdout
    assert "Traceback" not in result.stderr


def test_the_cli_refuses_utf16(tmp_path: Path) -> None:
    """`json.loads(bytes)` UTF-16'yı sezerdi; B-2'nin UTF-8 okuyucusu sezmez."""
    target = tmp_path / "snapshot.json"
    target.write_bytes(BASE.read_text(encoding="utf-8").encode("utf-16"))

    result = _cli(str(target))

    assert result.returncode == EXIT_SITE_INVALID
    assert "ANLIK GÖRÜNTÜ İHLALİ: snapshot.json: geçerli JSON değil" in result.stdout


def test_the_cli_names_a_lone_surrogate(tmp_path: Path) -> None:
    snapshot = _fixture()
    snapshot["leagues"][0]["country"] = "Nord\ud800land"
    target = tmp_path / "snapshot.json"
    target.write_text(json.dumps(snapshot), encoding="utf-8")

    result = _cli(str(target))

    assert result.returncode == EXIT_SITE_INVALID, result.stdout + result.stderr
    assert "ANLIK GÖRÜNTÜ İHLALİ: $.leagues[0].country: UTF-8'e kodlanamayan" in result.stdout


@pytest.mark.parametrize("kind", ["missing", "directory", "missing-sha256"])
def test_the_cli_names_an_unreadable_file(tmp_path: Path, kind: str) -> None:
    target = tmp_path / "snapshot.json"
    if kind == "directory":
        target.mkdir()
    args = [str(target if kind != "missing-sha256" else BASE)]
    if kind == "missing-sha256":
        args += ["--sha256", str(tmp_path / "snapshot.sha256")]
    name = "snapshot.sha256" if kind == "missing-sha256" else "snapshot.json"

    result = _cli(*args)

    assert result.returncode == EXIT_SITE_INVALID, result.stdout + result.stderr
    assert f"ANLIK GÖRÜNTÜ İHLALİ: {name}: okunamadı (" in result.stdout
    assert "Traceback" not in result.stderr


def test_the_cli_outside_the_repo_root_names_the_limit(tmp_path: Path) -> None:
    """Sınır: şema yolu göreli; depo kökü dışından koşu adıyla exit 24 (sessiz yeşil değil)."""
    result = _cli(str(BASE), cwd=tmp_path)

    assert result.returncode == EXIT_SITE_INVALID, result.stdout + result.stderr
    assert "snapshot.schema.json: okunamadı — komut depo kökünden koşulur" in result.stdout


def test_an_unforeseen_error_in_a_rule_stays_a_named_violation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kural kollarının öngörmediği istisna exit 1 + traceback değil, adlandırılmış satırdır."""

    def explode(snapshot: object, schema: object) -> list[str]:
        raise ValueError("gizli değer")

    monkeypatch.chdir(REPO)
    monkeypatch.setattr(cli, "snapshot_errors", explode)

    assert cli._content_errors(BASE, BASE.read_bytes()) == [
        "snapshot.fixture.json: denetlenemedi (ValueError)"
    ]


def test_the_cli_checks_the_file_hash_when_asked(tmp_path: Path) -> None:
    target = tmp_path / "snapshot.json"
    target.write_bytes(BASE.read_bytes())
    digest = tmp_path / "snapshot.sha256"
    digest.write_text("0" * 64 + "  snapshot.json\n", encoding="utf-8")

    result = _cli(str(target), "--sha256", str(digest))

    assert result.returncode == EXIT_SITE_INVALID
    assert "snapshot.sha256: dosya baytlarının sha256'sı değil" in result.stdout
