"""Döküm → gövde (§5.2, §5.4, §8.4): beklenen değerler ELLE hesaplandı, türetme kodu çağrılmadan.

Adil kitaplar (`site_builders`): `2.0/4.0/4.0` → 50.0/25.0/25.0 vb.; simetrik marjlı tur → 33.3.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from football_edge.site.contract import content_sha256
from football_edge.site.derive import DeriveError, derive, record_mismatches
from football_edge.site.inputs import load_inputs
from football_edge.site.verify import snapshot_errors
from tests.site_builders import (
    AWAY_FAVOURED,
    DRAWISH,
    EVEN,
    HOME_HEAVY,
    HOME_LEAN,
    SYMMETRIC,
    WIDE,
    Round,
    at,
    export_dump,
    export_inputs,
)

REPO = Path(__file__).resolve().parent.parent
SCHEMA: dict[str, Any] = json.loads(
    (REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8")
)
LEAGUE = ("tst.1", "Deneme Ligi", "Testland", "deneme-ligi")


def mid(number: int) -> str:
    return f"{number:02d}" + "ab" * 15


SEALED = Round(mid(1), "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3)
SEALED_MIDDLE = Round(
    mid(1), "2026-09-21T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3, drop_away_for=0
)
SEALED_CLOSE = Round(
    mid(1), "2026-09-22T13:00:00Z", "Alfa Spor", "Beta FK", SYMMETRIC, is_closing=True
)
OPEN_FIRST = Round(mid(2), "2026-09-20T11:00:00Z", "Gamma United", "Alfa Spor", [AWAY_FAVOURED] * 3)
OPEN_LATEST = Round(mid(2), "2026-09-21T11:00:00Z", "Gamma United", "Alfa Spor", [DRAWISH] * 3)
THIN = Round(mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [HOME_HEAVY] * 2)
MATCHES = [
    (mid(1), "tst.1", "2026-09-22T14:00:00Z", "Alfa Spor", "Beta FK"),
    (mid(2), "tst.1", "2026-09-23T15:00:00Z", "Gamma United", "Alfa Spor"),
    (mid(3), "tst.1", "2026-09-24T16:00:00Z", "Delta Şehir", "Beta FK"),
]


def _body(rounds: list[Round], **extra: Any) -> dict[str, Any]:
    return derive(export_inputs(leagues=[LEAGUE], matches=MATCHES, rounds=rounds, **extra))


def _match(body: dict[str, Any], number: int) -> dict[str, Any]:
    (found,) = [match for match in body["matches"] if match["id"] == mid(number)]
    return found


ROUNDS = [SEALED, SEALED_MIDDLE, SEALED_CLOSE, OPEN_FIRST, OPEN_LATEST, THIN]


def test_a_sealed_match_shows_opening_latest_closing_and_the_move_to_closing() -> None:
    match = _match(_body(ROUNDS), 1)

    assert match["sealed"] is True and match["rounds"] == 3
    assert match["h2h"]["opening"] == {
        "observed_at": "2026-09-20T10:00:00Z",
        "books": 3,
        "p": {"home": 50.0, "draw": 25.0, "away": 25.0},
    }
    closing = {
        "observed_at": "2026-09-22T13:00:00Z",
        "books": 3,
        "p": {"home": 33.3, "draw": 33.3, "away": 33.3},
    }
    assert match["h2h"]["closing"] == closing and match["h2h"]["latest"] == closing
    # Ham farktan yuvarlanır: 33.33 − 50 = −16.67 → −16.7; 33.33 − 25 = 8.33 → 8.3.
    assert match["move"] == {"home": -16.7, "draw": 8.3, "away": 8.3}
    assert match["indexable"] is True


def test_a_round_with_an_incomplete_book_counts_only_full_books() -> None:
    """Orta turda bir kitabın deplasman satırı yok: 2 tam kitap < 3 → tur sayılır, gösterilmez."""
    match = _match(_body([SEALED, SEALED_MIDDLE]), 1)

    assert match["rounds"] == 2
    assert match["h2h"]["latest"] is None
    assert match["move"] is None, "son tur görünmüyorsa hareket de yok"


def test_an_unsealed_match_moves_to_the_latest_round() -> None:
    match = _match(_body(ROUNDS), 2)

    assert match["sealed"] is False and match["h2h"]["closing"] is None
    assert match["h2h"]["latest"]["p"] == {"home": 20.0, "draw": 40.0, "away": 40.0}
    assert match["move"] == {"home": -5.0, "draw": 15.0, "away": -10.0}


def test_a_thin_single_round_match_is_listed_but_not_indexable() -> None:
    match = _match(_body(ROUNDS), 3)

    assert match["rounds"] == 1
    assert match["h2h"] == {"opening": None, "latest": None, "closing": None}
    assert match["move"] is None and match["indexable"] is False


def test_a_single_round_match_moves_by_exactly_zero() -> None:
    lone = Round(mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [EVEN] * 3)

    match = _match(_body([lone]), 3)

    assert match["move"] == {"home": 0.0, "draw": 0.0, "away": 0.0}
    assert match["indexable"] is False, "§8.4: tek tur, üç kitaplı olsa da indekslenmez"


def test_a_tiny_negative_move_is_shown_as_zero_not_minus_zero() -> None:
    """−0.04 pp bir ondalığa −0.0 yuvarlanır; sayfada "-0,0" görünmesin (§5.4)."""
    home, away = 1 / 0.4996, 1 / 0.2504  # adil kitap: 49.96 / 25.0 / 25.04
    first = Round(mid(3), "2026-09-20T10:00:00Z", "Delta Şehir", "Beta FK", [EVEN] * 3)
    later = Round(mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [(home, 4.0, away)] * 3)
    move = _match(_body([first, later]), 3)["move"]

    assert [str(value) for value in move.values()] == ["0.0", "0.0", "0.0"]


def test_a_round_whose_average_cannot_be_devigged_is_not_shown() -> None:
    """Σ 1/o < 1 (negatif marj) hiçbir yöntemde temizlenmez: tur null, türetim düşmez."""
    negative = Round(
        mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [(2.1, 4.2, 4.2)] * 3
    )

    assert _match(_body([negative]), 3)["h2h"]["opening"] is None


def test_the_match_url_parts_and_date() -> None:
    match = _match(_body(ROUNDS), 3)

    assert match["path_id"] == mid(3)[:12]
    assert match["slug"] == "delta-sehir-vs-beta-fk"
    assert (match["date"], match["commence_time"]) == ("2026-09-24", "2026-09-24T16:00:00Z")


def test_teams_count_their_matches_and_cross_the_threshold_at_three() -> None:
    body = _body(ROUNDS)

    assert [(team["slug"], team["matches"], team["indexable"]) for team in body["teams"]] == [
        ("alfa-spor", 2, False),
        ("beta-fk", 2, False),
        ("delta-sehir", 1, False),
        ("gamma-united", 1, False),
    ]


DISTRIBUTION_ENDS = [WIDE, AWAY_FAVOURED, HOME_HEAVY, HOME_LEAN, DRAWISH]


def _sealed_moving(ends: list[tuple[float, float, float]]) -> tuple[list[Any], list[Round]]:
    """`EVEN` açılış → `end` kapanış; maç 10'dan başlar, başlamalar 20., 21., … Eylül 18:00."""
    matches: list[Any] = []
    rounds: list[Round] = []
    for number, end in enumerate(ends, start=10):
        kickoff = f"2026-09-2{number - 10}T18:00:00Z"
        matches.append((mid(number), "tst.1", kickoff, f"Ev {number}", f"Dep {number}"))
        rounds.append(
            Round(mid(number), "2026-09-19T08:00:00Z", f"Ev {number}", f"Dep {number}", [EVEN] * 3)
        )
        rounds.append(
            Round(
                mid(number),
                kickoff.replace("18:", "17:"),
                f"Ev {number}",
                f"Dep {number}",
                [end] * 3,
                is_closing=True,
            )
        )
    return matches, rounds


def test_a_league_distribution_needs_five_sealed_moving_matches() -> None:
    """|hareket| en büyük bileşeni: 15, 25, 30, 12.5, 30 → numpy doğrusal yüzdelik 13.5/25/30."""
    matches, rounds = _sealed_moving(DISTRIBUTION_ENDS)
    five = derive(export_inputs(leagues=[LEAGUE], matches=matches, rounds=rounds))
    four = derive(export_inputs(leagues=[LEAGUE], matches=matches[:4], rounds=rounds[:8]))

    assert five["leagues"][0]["move_distribution"] == {"p10": 13.5, "p50": 25.0, "p90": 30.0}
    assert four["leagues"][0]["move_distribution"] is None


@pytest.mark.parametrize(
    ("leagues", "matches", "needle"),
    [
        ([("tst.1", "Kayıt", "X", "track-record")], MATCHES, "lig tst.1: slug"),
        ([("tst.1", "Veri", "X", "data")], MATCHES, "lig tst.1: slug"),
        ([LEAGUE, ("tst.2", "Başka Lig", "Y", "deneme-ligi")], MATCHES, "lig tst.2: slug"),
        (
            [LEAGUE],
            [*MATCHES[:2], (mid(3), "tst.1", "2026-09-24T16:00:00Z", "Alfa-Spor", "Beta FK")],
            "takım slug",
        ),
        (
            [LEAGUE],
            [*MATCHES[:2], (mid(3), "tst.1", "2026-09-24T16:00:00Z", "Match", "Beta FK")],
            "takım slug",
        ),
    ],
)
def test_slug_collisions_and_reserved_slugs_stop_the_derivation(
    leagues: list[tuple[str, str, str, str]], matches: list[Any], needle: str
) -> None:
    rounds = [Round(m[0], "2026-09-21T09:00:00Z", m[3], m[4], [EVEN] * 3) for m in matches]

    with pytest.raises(DeriveError, match=needle):
        derive(export_inputs(leagues=leagues, matches=matches, rounds=rounds))


def test_two_leagues_with_the_same_name_keep_their_configured_slugs() -> None:
    """I3: `ger.1` ve `aut.1`in ikisi de "Bundesliga"; slug addan türeseydi yayın dururdu."""
    leagues = [
        ("ger.1", "Bundesliga", "Germany", "bundesliga"),
        ("aut.1", "Bundesliga", "Austria", "austrian-bundesliga"),
    ]
    matches = [(mid(1), "ger.1", "2026-09-22T14:00:00Z", "Alfa Spor", "Beta FK")]
    rounds = [Round(mid(1), "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3)]

    body = derive(export_inputs(leagues=leagues, matches=matches, rounds=rounds))

    assert [(league["id"], league["slug"]) for league in body["leagues"]] == [
        ("aut.1", "austrian-bundesliga"),
        ("ger.1", "bundesliga"),
    ]


def test_two_matches_sharing_a_path_prefix_stop_the_derivation() -> None:
    twin = mid(1)[:12] + "cd" * 10
    matches = [MATCHES[0], (twin, "tst.1", "2026-09-25T16:00:00Z", "Eta", "Teta")]
    rounds = [SEALED, Round(twin, "2026-09-21T09:00:00Z", "Eta", "Teta", [EVEN] * 3)]

    with pytest.raises(DeriveError, match="path_id"):
        derive(export_inputs(leagues=[LEAGUE], matches=matches, rounds=rounds))


@pytest.mark.parametrize(
    ("section", "row", "column"),
    [("matches", 0, 2), ("quotes", 0, 2), ("floor", None, None)],
)
@pytest.mark.parametrize(
    "broken", ["2026-09-22T14:00:00", "2026-09-22T17:00:00+03:00", "22.09.2026 14:00", 1758549600]
)
def test_a_dump_time_that_is_not_canonical_utc_stops_the_derivation(
    section: str, row: int | None, column: int | None, broken: object
) -> None:
    """Döküm zamanı `canonical_timestamp` metnidir (`+00:00`). Saat dilimsiz, başka dilimli ya da
    bozuk zaman `DeriveError`dır: dışa aktarıcı yalnız onu çıkış koduna eşler; düz `ValueError`
    (`iso_z`) ya da `TypeError` (naive/aware karşılaştırması) adsız traceback olurdu."""
    raw = json.loads(export_dump(leagues=[LEAGUE], matches=MATCHES, rounds=ROUNDS))
    if row is None:
        raw[section] = broken
    else:
        raw[section][row][column] = broken

    with pytest.raises(DeriveError, match="zaman"):
        derive(load_inputs(json.dumps(raw)))


def test_an_empty_record_has_no_summary() -> None:
    assert _body(ROUNDS)["record"] == {"published": 0, "entries": [], "summary": None}


def _publication(
    number: int, outcome: str, price: float, clv: float, fair: float
) -> tuple[Any, ...]:
    return (
        number,
        mid(1),
        "h2h",
        outcome,
        at("2026-09-21T09:00:00Z"),
        price,
        3,
        1.0 / fair,
        clv,
        str(number) * 64,
    )


def test_a_filled_record_rounds_only_at_display_time() -> None:
    """Kapanış 1/3: 3.12 × 1/3 − 1 = 0.04 → %4.00; 3.06 × 1/3 − 1 = 0.02 → %2.00; ortalama %3.00.

    Güven aralığı da elle: iki örnekten yerine koymalı çekilişin ortalaması 2/3/4'tür, olasılıkları
    1/4, 1/2, 1/4. 2000 tekrarda ~500'er uç değer %2,5 ve %97,5 yüzdeliklerini (50. ve 1950. sıra)
    uçlara oturtur: aralık tam [2.00, 4.00] (tohum sabit; aralık iddiası tahmin değil eşitlik).
    """
    record = [
        _publication(2, "away", 3.06, 3.06 / 3 - 1, 1 / 3),
        _publication(1, "home", 3.12, 3.12 / 3 - 1, 1 / 3),
    ]
    body = _body(ROUNDS, record=record)

    assert [entry["publication_id"] for entry in body["record"]["entries"]] == [1, 2]
    assert [entry["clv"] for entry in body["record"]["entries"]] == [4.0, 2.0]
    assert body["record"]["entries"][0]["closing_fair_price"] == 3.0
    summary = body["record"]["summary"]
    assert summary == {"mean_clv": 3.0, "ci_low": 2.0, "ci_high": 4.0, "n": 2}


def test_record_entries_are_recomputed_from_the_ledger_closing() -> None:
    """§6.4/3d: CLV ve kapanış adil oranı defterin kapanış konsensüsünden yeniden hesaplanır."""
    good = _publication(1, "home", 3.12, 3.12 * 0.3333333333333333 - 1, 0.3333333333333333)
    inputs = export_inputs(leagues=[LEAGUE], matches=MATCHES, rounds=ROUNDS, record=[good])
    assert record_mismatches(inputs) == []

    wrong_clv = (*good[:8], 0.5, good[9])
    unsealed = (good[0], mid(2), *good[2:])
    bad_outcome = (*good[:3], "H", *good[4:])
    late = (*good[:6], 10**6, *good[7:])
    for row, needle in (
        (wrong_clv, "CLV defterden"),
        (unsealed, "kapanış konsensüsü yok"),
        (bad_outcome, "sözleşme dışı"),
        (late, "kesimden sonraki"),
    ):
        broken = export_inputs(leagues=[LEAGUE], matches=MATCHES, rounds=ROUNDS, record=[row])
        assert any(needle in problem for problem in record_mismatches(broken)), needle


def test_the_body_is_the_same_on_every_call() -> None:
    inputs = export_inputs(leagues=[LEAGUE], matches=MATCHES, rounds=ROUNDS)

    assert content_sha256(derive(inputs)) == content_sha256(derive(inputs))


def test_a_derived_snapshot_passes_verify_and_orders_teams_by_slug_not_name() -> None:
    """N3: "Çınar" adda "Delta"dan sonra, slug'da (`cinar`) önce gelir; dizi slug'la sıralıdır."""
    matches = [(mid(1), "tst.1", "2026-09-22T14:00:00Z", "Delta Şehir", "Çınar Spor")]
    rounds = [Round(mid(1), "2026-09-20T10:00:00Z", "Delta Şehir", "Çınar Spor", [EVEN] * 3)]
    body = derive(export_inputs(leagues=[LEAGUE], matches=matches, rounds=rounds))
    snapshot = {**body, "generated_at": "2026-09-24T12:00:00Z", "git_sha": "1" * 40}
    snapshot["content_sha256"] = content_sha256(snapshot)

    assert [team["slug"] for team in body["teams"]] == ["cinar-spor", "delta-sehir"]
    assert snapshot_errors(snapshot, SCHEMA) == []


# ── Review Focus ──────────────────────────────────────────────────────────────────────────────


def test_review_focus_a_sealed_match_with_a_thin_closing_shows_no_closing_and_no_move() -> None:
    """Mühür turu yalnız iki tam kitap gördüyse: mühürlü, ama kapanış ve hareket gösterilmez."""
    opening = Round(mid(3), "2026-09-20T10:00:00Z", "Delta Şehir", "Beta FK", [EVEN] * 3)
    thin_close = Round(
        mid(3), "2026-09-24T15:00:00Z", "Delta Şehir", "Beta FK", [WIDE] * 2, is_closing=True
    )
    body = _body([opening, thin_close])
    match = _match(body, 3)
    snapshot = {**body, "generated_at": "2026-09-24T12:00:00Z", "git_sha": "1" * 40}
    snapshot["content_sha256"] = content_sha256(snapshot)

    assert match["sealed"] is True and match["rounds"] == 2
    assert match["h2h"]["closing"] is None and match["h2h"]["latest"] is None
    assert match["move"] is None and match["indexable"] is True
    assert snapshot_errors(snapshot, SCHEMA) == []


def test_review_focus_a_postponed_match_keeps_its_url_and_moves_its_date() -> None:
    """AK20(b): maç yolu değişmez kimlik taşır; erteleme yalnız görünen tarihi değiştirir."""
    moved = [
        (mid(3), "tst.1", "2026-10-02T19:45:00Z", "Delta Şehir", "Beta FK") if m[0] == mid(3) else m
        for m in MATCHES
    ]
    before = _match(_body(ROUNDS), 3)
    after = _match(derive(export_inputs(leagues=[LEAGUE], matches=moved, rounds=ROUNDS)), 3)

    assert (after["path_id"], after["slug"]) == (before["path_id"], before["slug"])
    assert (after["date"], after["commence_time"]) == ("2026-10-02", "2026-10-02T19:45:00Z")


# ── I1: maç içi (in-play) satırlar türetime girmez (spec §1.3, §3.3/3) ─────────────────────────


def test_a_round_after_the_seal_and_after_kickoff_is_ignored() -> None:
    """Mühürden sonra, başlamadan sonra yazılan tur `latest`i, `rounds`u ve `move`u değiştirmez."""
    in_play = Round(mid(1), "2026-09-22T15:00:00Z", "Alfa Spor", "Beta FK", [HOME_HEAVY] * 3)
    match = _match(_body([SEALED, SEALED_CLOSE, in_play]), 1)
    closing = {
        "observed_at": "2026-09-22T13:00:00Z",
        "books": 3,
        "p": {"home": 33.3, "draw": 33.3, "away": 33.3},
    }

    assert match["sealed"] is True and match["rounds"] == 2
    assert match["h2h"]["latest"] == closing and match["h2h"]["closing"] == closing
    assert match["move"] == {"home": -16.7, "draw": 8.3, "away": 8.3}


def test_an_unsealed_match_ignores_rounds_at_and_after_kickoff() -> None:
    """Kaçan mühürde hareket açılış → maç içi olmaz; başlama anındaki sıradan tur da sayılmaz."""
    at_kickoff = Round(
        mid(2), "2026-09-23T15:00:00Z", "Gamma United", "Alfa Spor", [HOME_HEAVY] * 3
    )
    after = Round(mid(2), "2026-09-23T16:30:00Z", "Gamma United", "Alfa Spor", [WIDE] * 3)
    match = _match(_body([OPEN_FIRST, OPEN_LATEST, at_kickoff, after]), 2)

    assert match["sealed"] is False and match["rounds"] == 2
    assert match["h2h"]["latest"]["p"] == {"home": 20.0, "draw": 40.0, "away": 40.0}
    assert match["move"] == {"home": -5.0, "draw": 15.0, "away": -10.0}
    assert match["indexable"] is True


def test_a_closing_round_written_exactly_at_kickoff_is_kept() -> None:
    """`rounds.seal_window` kapsayıcıdır (`0 <= başlama − an`): mühür başlama anında da yazılır."""
    closing = Round(
        mid(3), "2026-09-24T16:00:00Z", "Delta Şehir", "Beta FK", SYMMETRIC, is_closing=True
    )
    first = Round(mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [EVEN] * 3)
    match = _match(_body([first, closing]), 3)

    assert match["sealed"] is True and match["rounds"] == 2
    assert match["h2h"]["closing"]["p"] == {"home": 33.3, "draw": 33.3, "away": 33.3}


def test_a_closing_row_after_kickoff_marks_the_match_sealed_but_is_not_shown() -> None:
    """Başlama sonradan öne çekilirse (UPSERT) mühür turu başlamadan sonraya düşer. `sealed` spec
    §5.2'nin tanımıdır (kesimde kapanış satırı var mı); fiyatı maç içi sayılır, gösterilmez."""
    late_seal = Round(
        mid(1), "2026-09-22T14:30:00Z", "Alfa Spor", "Beta FK", SYMMETRIC, is_closing=True
    )
    match = _match(_body([SEALED, late_seal]), 1)

    assert match["sealed"] is True and match["rounds"] == 1
    assert match["h2h"]["closing"] is None
    assert match["h2h"]["latest"] == match["h2h"]["opening"]
    assert match["move"] is None, "mühürlü maçın hareketi kapanışa gider; kapanış yoksa hareket yok"


def test_a_match_seen_only_after_kickoff_is_not_listed() -> None:
    late = Round(mid(3), "2026-09-24T17:00:00Z", "Delta Şehir", "Beta FK", [EVEN] * 3)
    body = _body([SEALED, late])

    assert [match["id"] for match in body["matches"]] == [mid(1)]
    assert "delta-sehir" not in {team["slug"] for team in body["teams"]}


# ── İnceleme (düzeltme turu 1): yayımlanan kurallar tek tek sabit ──────────────────────────────


def test_a_match_whose_rounds_all_lack_enough_books_is_not_indexable() -> None:
    """§8.4'ün ikinci koşulu: iki tur var, ama ikisi de 2 tam kitaplı (< 3) → indekslenmez."""
    first = Round(mid(3), "2026-09-20T10:00:00Z", "Delta Şehir", "Beta FK", [EVEN] * 2)
    second = Round(mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [WIDE] * 2)
    match = _match(_body([first, second]), 3)

    assert match["rounds"] == 2
    assert match["h2h"] == {"opening": None, "latest": None, "closing": None}
    assert match["move"] is None and match["indexable"] is False


def test_a_sealed_single_round_match_stays_out_of_the_league_distribution() -> None:
    """Dağılım yalnız en az iki turlu mühürlü maçlardan: tek turlu mühürlü maçın hareketi 0'dır ve
    girseydi yüzdelikleri kaydırırdı ([0, 12.5, 15, 25, 30, 30] → p10 6.2). Beşin değeri kalır."""
    matches, rounds = _sealed_moving(DISTRIBUTION_ENDS)
    matches.append((mid(15), "tst.1", "2026-09-25T18:00:00Z", "Ev 15", "Dep 15"))
    rounds.append(
        Round(mid(15), "2026-09-25T17:00:00Z", "Ev 15", "Dep 15", [EVEN] * 3, is_closing=True)
    )
    body = derive(export_inputs(leagues=[LEAGUE], matches=matches, rounds=rounds))

    assert _match(body, 15)["move"] == {"home": 0.0, "draw": 0.0, "away": 0.0}
    assert body["leagues"][0]["move_distribution"] == {"p10": 13.5, "p50": 25.0, "p90": 30.0}


def test_a_sealed_match_moves_to_its_closing_not_to_a_later_pre_kickoff_round() -> None:
    """Mühür (13:00) ile başlama (14:00) arasına bir snapshot turu düşebilir (06:22 turu, 20 dk
    mühür penceresi). `latest` o turdur (80/10/10); hareket yine açılış → kapanış (spec §5.2):
    33.33 − 50 = −16.7, 33.33 − 25 = 8.3. Son tura gitseydi 30 / −15 / −15 olurdu."""
    after_seal = Round(mid(1), "2026-09-22T13:30:00Z", "Alfa Spor", "Beta FK", [HOME_HEAVY] * 3)
    match = _match(_body([SEALED, SEALED_CLOSE, after_seal]), 1)

    assert match["sealed"] is True and match["rounds"] == 3
    assert match["h2h"]["latest"]["p"] == {"home": 80.0, "draw": 10.0, "away": 10.0}
    assert match["h2h"]["closing"]["p"] == {"home": 33.3, "draw": 33.3, "away": 33.3}
    assert match["move"] == {"home": -16.7, "draw": 8.3, "away": 8.3}


def test_a_team_name_without_latin_letters_or_digits_stops_the_derivation_by_name() -> None:
    """`slugify` harf/rakamsız adda düz `ValueError` atar; dışa aktarıcı yalnız `DeriveError`ı
    çıkış koduna eşler, bu yüzden türetim onu adıyla yeniden fırlatır."""
    matches = [(mid(1), "tst.1", "2026-09-22T14:00:00Z", "北京国安", "Beta FK")]
    rounds = [Round(mid(1), "2026-09-20T10:00:00Z", "北京国安", "Beta FK", [EVEN] * 3)]

    with pytest.raises(DeriveError, match="lig tst.1: takım adından slug üretilemedi"):
        derive(export_inputs(leagues=[LEAGUE], matches=matches, rounds=rounds))


def test_the_record_summary_does_not_depend_on_the_dump_row_order() -> None:
    """`bootstrap_mean` konumla örnekler: özet de girdiler gibi `publication_id` sırasıyla."""
    clvs = [0.04, -0.10, 0.02, 0.15, -0.05]
    rows = [_publication(n, "home", 3.12, value, 1 / 3) for n, value in enumerate(clvs, start=1)]

    forward = _body(ROUNDS, record=rows)["record"]
    backward = _body(ROUNDS, record=rows[::-1])["record"]

    assert forward["summary"]["mean_clv"] == 1.2  # (4 − 10 + 2 + 15 − 5) / 5
    assert backward == forward
