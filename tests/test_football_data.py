from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime

import pytest

from football_edge.collector import ContractViolation
from football_edge.history.football_data import (
    ODDS_COLUMNS,
    REASON_DATE,
    REASON_DUPLICATE,
    REASON_GOALS,
    REASON_RESULT,
    REASON_SEASON,
    REASON_TEAM,
    REASON_TIME,
    ParseResult,
    Rejected,
    check_quality,
    parse_file,
)
from football_edge.history.types import (
    CLOSING,
    H2H,
    PRE_CLOSING,
    TOTALS_25,
    HistMatch,
    OddsKey,
)
from tests.history_csv import (
    BRA,
    E0,
    EXTRA_NEW,
    EXTRA_RUS,
    MAIN_2526,
    MAIN_2627,
    MAIN_OLD,
    csv_bytes,
    extra_row,
    main_row,
    unique_prices,
)

# (kitap, evre) → sütunlar, sırayla H, D, A, Ü2.5, A2.5 — ölçülen 2025/26 başlığından elle yazıldı.
EXPECTED_2526 = {
    ("Avg", PRE_CLOSING): ("AvgH", "AvgD", "AvgA", "Avg>2.5", "Avg<2.5"),
    ("Avg", CLOSING): ("AvgCH", "AvgCD", "AvgCA", "AvgC>2.5", "AvgC<2.5"),
    ("Max", PRE_CLOSING): ("MaxH", "MaxD", "MaxA", "Max>2.5", "Max<2.5"),
    ("Max", CLOSING): ("MaxCH", "MaxCD", "MaxCA", "MaxC>2.5", "MaxC<2.5"),
    ("B365", PRE_CLOSING): ("B365H", "B365D", "B365A", "B365>2.5", "B365<2.5"),
    ("B365", CLOSING): ("B365CH", "B365CD", "B365CA", "B365C>2.5", "B365C<2.5"),
    ("PS", PRE_CLOSING): ("PSH", "PSD", "PSA", "P>2.5", "P<2.5"),
    ("PS", CLOSING): ("PSCH", "PSCD", "PSCA", "PC>2.5", "PC<2.5"),
    ("BFE", PRE_CLOSING): ("BFEH", "BFED", "BFEA", "BFE>2.5", "BFE<2.5"),
    ("BFE", CLOSING): ("BFECH", "BFECD", "BFECA", "BFEC>2.5", "BFEC<2.5"),
}
OUTCOMES = ((H2H, "H"), (H2H, "D"), (H2H, "A"), (TOTALS_25, "over"), (TOTALS_25, "under"))


def one_match(content: bytes, *, season: str | None = "2526") -> HistMatch:
    result = parse_file(content, league=E0 if season else BRA, season=season)
    assert result.rejected == (), result.rejected
    (match,) = result.matches
    return match


def test_odds_vocabulary_has_one_column_name_per_key() -> None:
    """7 kitap × (3 + 2 sonuç) × 2 evre; iki anahtar aynı adı üretirse biri sessizce düşerdi."""
    assert len(ODDS_COLUMNS) == 70
    assert len(set(ODDS_COLUMNS.values())) == 70


@pytest.mark.leakage
def test_the_measured_2025_26_header_maps_to_the_right_book_market_and_phase() -> None:
    """Kapanış bir kapanış öncesi anahtarına düşerse karar bağlamına kapanış sızar."""
    prices = unique_prices(MAIN_2526, after="AR")
    match = one_match(csv_bytes(MAIN_2526, [main_row(0, prices)]))

    for (book, phase), columns in EXPECTED_2526.items():
        for (market, outcome), column in zip(OUTCOMES, columns, strict=True):
            assert match.odds[OddsKey(book, market, outcome, phase)] == float(prices[column]), (
                book,
                phase,
                column,
            )
    assert len(match.odds) == 50, "Asya handikabı ya da başka bahisçi okunmuş"


@pytest.mark.leakage
def test_pre_2019_betbrain_columns_are_pre_closing_and_psc_is_closing() -> None:
    prices = unique_prices(MAIN_OLD, after="AR")
    match = one_match(csv_bytes(MAIN_OLD, [main_row(0, prices)]), season="1718")

    assert match.odds[OddsKey("BbAv", H2H, "H", PRE_CLOSING)] == float(prices["BbAvH"])
    assert match.odds[OddsKey("BbMx", H2H, "A", PRE_CLOSING)] == float(prices["BbMxA"])
    assert match.odds[OddsKey("BbAv", TOTALS_25, "over", PRE_CLOSING)] == float(prices["BbAv>2.5"])
    assert match.odds[OddsKey("BbMx", TOTALS_25, "under", PRE_CLOSING)] == float(prices["BbMx<2.5"])
    assert match.odds[OddsKey("PS", H2H, "D", CLOSING)] == float(prices["PSCD"])
    assert match.odds[OddsKey("PS", H2H, "D", PRE_CLOSING)] == float(prices["PSD"])
    assert len(match.odds) == 19, "B365 3 + PS 3 + BbMx/BbAv 6 + Ü/A 4 + PSC 3"


@pytest.mark.leakage
def test_extra_files_carry_only_closing_prices_and_the_row_season() -> None:
    rows = [extra_row(0), extra_row(1, {"Season": "2024/2025", "Date": "01/03/2025"})]
    result = parse_file(csv_bytes(EXTRA_NEW, rows), league=BRA, season=None)

    assert [match.season for match in result.matches] == ["2025", "2024/2025"]
    assert {key.phase for match in result.matches for key in match.odds} == {CLOSING}
    assert result.matches[0].odds[OddsKey("PS", H2H, "A", CLOSING)] == 2.95
    assert result.matches[0].league == "BRA"


def test_the_19_column_russian_layout_parses_without_betfair_or_bet365() -> None:
    match = one_match(csv_bytes(EXTRA_RUS, [extra_row(0)]), season=None)

    assert {key.book for key in match.odds} == {"PS", "Avg"}


def test_the_2026_27_header_has_no_pinnacle_and_xg_is_not_read() -> None:
    prices = unique_prices(MAIN_2627, after="AR")
    cells = {**prices, "HxG": "1", "AxG": "2"}
    match = one_match(csv_bytes(MAIN_2627, [main_row(0, cells)]), season="2627")

    assert {key.book for key in match.odds} == {"Avg", "Max", "B365", "BFE"}
    assert "HxG" not in match.stats and "AxG" not in match.stats


def test_match_stats_are_read_as_integers_when_present() -> None:
    cells = {"HS": "12", "AS": "7", "HST": "5", "AST": "2", "HF": "10", "AF": "11"}
    cells = {**cells, "HC": "", "AC": "x"}
    match = one_match(csv_bytes(MAIN_2526, [main_row(0, cells)]))

    assert dict(match.stats) == {"HS": 12, "AS": 7, "HST": 5, "AST": 2, "HF": 10, "AF": 11}


def test_a_repeated_header_column_reads_its_first_occurrence() -> None:
    """Yinelenen başlıkta İLK sütun geçerli: sonraki kopya (ör. kaymış bir ek sütun) okunmaz."""
    header = (*MAIN_2526, "AvgH")
    line = ",".join(main_row(0).get(name, "") for name in MAIN_2526) + ",9.99"
    content = (",".join(header) + "\r\n" + line + "\r\n").encode("utf-8")

    match = one_match(content)

    assert match.odds[OddsKey("Avg", H2H, "H", PRE_CLOSING)] == 2.10


def test_utf8_with_bom_is_decoded_and_the_bom_leaves_the_first_column_name() -> None:
    content = csv_bytes(MAIN_2526, [main_row(0, {"HomeTeam": "Çınar Gücü"})], bom=True)

    result = parse_file(content, league=E0, season="2526")

    assert result.encoding == "utf-8-sig"
    assert result.columns[0] == "Div"
    assert result.matches[0].home == "Çınar Gücü"


def test_non_utf8_bytes_fall_back_to_latin1() -> None:
    content = csv_bytes(
        MAIN_2526, [main_row(0, {"AwayTeam": "Sintético Norte"})], encoding="latin-1"
    )

    result = parse_file(content, league=E0, season="2526")

    assert result.encoding == "latin-1"
    assert result.matches[0].away == "Sintético Norte"


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("text", "expected"),
    [("16/08/05", date(2005, 8, 16)), ("16/08/2025", date(2025, 8, 16))],
    ids=["iki-haneli-yil", "dort-haneli-yil"],
)
def test_two_and_four_digit_years_give_the_source_date(text: str, expected: date) -> None:
    match = one_match(csv_bytes(MAIN_2526, [main_row(0, {"Date": text})]))

    assert match.date == expected


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("day", "clock", "expected"),
    [
        ("16/08/2025", "15:00", datetime(2025, 8, 16, 14, 0, tzinfo=UTC)),
        ("06/12/2025", "15:00", datetime(2025, 12, 6, 15, 0, tzinfo=UTC)),
        ("29/03/2026", "01:30", datetime(2026, 3, 29, 1, 30, tzinfo=UTC)),
        ("25/10/2026", "01:30", datetime(2026, 10, 25, 1, 30, tzinfo=UTC)),
    ],
    ids=["yaz-saati", "kis-saati", "ilkbahar-boslugu-gec-okuma", "sonbahar-tekrari-gec-okuma"],
)
def test_london_kickoff_becomes_utc_and_a_dst_edge_takes_the_later_reading(
    day: str, clock: str, expected: datetime
) -> None:
    """D5: Time Europe/London yerel saatidir. Geçişte iki yorumun GEÇ olanı: sonuç bilinme anı
    (başlama + 3 sa) gerçek andan önceye düşmesin."""
    match = one_match(csv_bytes(MAIN_2526, [main_row(0, {"Date": day, "Time": clock})]))

    assert match.kickoff == expected
    assert match.kickoff is not None and match.kickoff.utcoffset() == UTC.utcoffset(None)


@pytest.mark.leakage
def test_no_time_column_or_an_empty_time_gives_no_kickoff() -> None:
    old = one_match(csv_bytes(MAIN_OLD, [main_row(0)]), season="1718")
    empty = one_match(csv_bytes(MAIN_2526, [main_row(0, {"Time": ""})]))

    assert old.kickoff is None and empty.kickoff is None


@pytest.mark.parametrize(
    ("cells", "reason"),
    [
        ({"Date": "31/02/2025"}, REASON_DATE),
        ({"Date": "2025-08-16"}, REASON_DATE),
        ({"Date": ""}, REASON_DATE),
        ({"Time": "25:00"}, REASON_TIME),
        ({"Time": "3pm"}, REASON_TIME),
        ({"HomeTeam": ""}, REASON_TEAM),
        ({"AwayTeam": "  "}, REASON_TEAM),
        ({"FTHG": ""}, REASON_GOALS),
        ({"FTAG": "1.0"}, REASON_GOALS),
        ({"FTHG": "-1"}, REASON_GOALS),
        ({"FTR": "A"}, REASON_RESULT),
        ({"FTR": ""}, REASON_RESULT),
        ({"FTR": "h"}, REASON_RESULT),
    ],
)
def test_a_bad_row_is_rejected_with_its_reason_and_the_others_survive(
    cells: dict[str, str], reason: str
) -> None:
    rows = [main_row(0), main_row(1, cells), main_row(2)]

    result = parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")

    assert [match.source_line for match in result.matches] == [1, 3]
    assert result.rejected == (Rejected(line=2, reason=reason),)


def test_an_extra_row_without_a_season_is_rejected() -> None:
    rows = [extra_row(0), extra_row(1, {"Season": ""})]

    result = parse_file(csv_bytes(EXTRA_NEW, rows), league=BRA, season=None)

    assert result.rejected == (Rejected(line=2, reason=REASON_SEASON),)


def test_a_repeated_date_home_away_keeps_the_first_row_and_rejects_the_rest() -> None:
    rows = [
        main_row(0),
        main_row(1),
        main_row(0, {"FTHG": "0", "FTR": "A"}),
        main_row(0, {"Date": "23/08/2025"}),
    ]

    result = parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")

    assert [match.source_line for match in result.matches] == [1, 2, 4]
    assert result.matches[0].home_goals == 2, "ilk satır değil sonraki kalmış"
    assert result.rejected == (Rejected(line=3, reason=REASON_DUPLICATE),)


def test_blank_rows_are_skipped_silently_without_shifting_line_numbers() -> None:
    content = csv_bytes(MAIN_2526, [main_row(0), {}, main_row(2)]) + b",,,\r\n\r\n"

    result = parse_file(content, league=E0, season="2526")

    assert [match.source_line for match in result.matches] == [1, 3]
    assert result.rejected == ()


def test_unusable_prices_are_dropped_and_counted_while_the_row_survives() -> None:
    cells = {"AvgH": "abc", "AvgD": "1.0", "AvgA": "0.95", "MaxH": "nan", "MaxD": "3.10"}

    result = parse_file(csv_bytes(MAIN_2526, [main_row(0, cells)]), league=E0, season="2526")

    (match,) = result.matches
    assert result.dropped_prices == 4
    assert result.price_cells == 8, "AvgH/D/A + AvgCH/D/A + MaxH/D dolu hücre"
    assert match.prices("Avg", H2H, PRE_CLOSING) is None
    assert match.prices("Avg", H2H, CLOSING) == (2.05, 3.45, 3.60)
    assert match.odds[OddsKey("Max", H2H, "D", PRE_CLOSING)] == 3.10


def test_a_row_without_any_odds_is_kept_as_an_oddsless_match() -> None:
    """T1 2022/23'te maçların %8'i oransız: sayılır, düşürülmez."""
    bare = {name: "" for name in ("AvgH", "AvgD", "AvgA", "AvgCH", "AvgCD", "AvgCA")}

    result = parse_file(csv_bytes(MAIN_2526, [main_row(0, bare)]), league=E0, season="2526")

    assert len(result.matches) == 1 and dict(result.matches[0].odds) == {}
    assert (result.price_cells, result.dropped_prices) == (0, 0)


def test_a_main_file_needs_a_season_and_an_extra_file_refuses_one() -> None:
    with pytest.raises(ValueError, match="season zorunlu"):
        parse_file(csv_bytes(MAIN_2526, [main_row(0)]), league=E0, season=None)
    with pytest.raises(ValueError, match="season verilmez"):
        parse_file(csv_bytes(EXTRA_NEW, [extra_row(0)]), league=BRA, season="2526")


def test_results_are_immutable() -> None:
    result = parse_file(csv_bytes(MAIN_2526, [main_row(0)]), league=E0, season="2526")

    with pytest.raises(TypeError):
        result.matches[0].odds[OddsKey("Avg", H2H, "H", CLOSING)] = 9.0  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.dropped_prices = 1  # type: ignore[misc]


# ── check_quality ───────────────────────────────────────────────────────────


def quality(result: ParseResult, *, season: str | None = "2526") -> None:
    check_quality(result, path="/x.csv", league=E0 if season else BRA, season=season)


@pytest.mark.parametrize(
    ("header", "drop", "season"),
    [(MAIN_2526, "FTHG", "2526"), (MAIN_2526, "Date", "2526"), (EXTRA_NEW, "Res", None)],
)
def test_quality_fails_a_file_without_a_required_column(
    header: tuple[str, ...], drop: str, season: str | None
) -> None:
    kept = tuple(name for name in header if name != drop)
    row = main_row(0) if season else extra_row(0)
    league = E0 if season else BRA

    result = parse_file(csv_bytes(kept, [row]), league=league, season=season)

    with pytest.raises(ContractViolation, match=f"zorunlu sütun yok.*{drop}"):
        quality(result, season=season)


@pytest.mark.parametrize(
    ("header", "rows", "path", "season"),
    [
        (MAIN_2526, [{}], "/mmz4281/2526/E0.csv", "2526"),
        (EXTRA_NEW, [], "/new/BRA.csv", None),
    ],
    ids=["ana-bos-satirli", "ek"],
)
def test_quality_fails_a_header_only_file_as_total_loss(
    header: tuple[str, ...], rows: list[dict[str, str]], path: str, season: str | None
) -> None:
    """R88: yalnız başlık satırı tam kayıptır — reddedilen satır yok, pay 0/0, yine de kırmızı."""
    league = E0 if season else BRA
    result = parse_file(csv_bytes(header, rows), league=league, season=season)

    assert (result.matches, result.rejected) == ((), ())
    with pytest.raises(ContractViolation, match="hiç maç yok") as caught:
        check_quality(result, path=path, league=league, season=season)
    assert str(caught.value).startswith(f"{path}: "), "ihlal mesajı dosyayı adlandırmıyor"


def test_quality_fails_empty_content() -> None:
    result = parse_file(b"", league=E0, season="2526")

    assert result.columns == ()
    with pytest.raises(ContractViolation, match="zorunlu sütun"):
        quality(result)


@pytest.mark.parametrize(
    ("season", "has_avgc", "fails"),
    [("1920", False, True), ("2526", False, True), ("1819", False, False), ("1920", True, False)],
)
def test_quality_expects_avgc_columns_from_2019_20(
    season: str, has_avgc: bool, fails: bool
) -> None:
    header = MAIN_2526 if has_avgc else tuple(n for n in MAIN_2526 if not n.startswith("AvgC"))
    result = parse_file(csv_bytes(header, [main_row(0)]), league=E0, season=season)

    if fails:
        with pytest.raises(ContractViolation, match="dönem beklentisi"):
            quality(result, season=season)
    else:
        quality(result, season=season)


def _with_bad_rows(good: int, bad: int) -> ParseResult:
    rows = [main_row(n) for n in range(good)] + [
        main_row(good + n, {"FTR": "A"}) for n in range(bad)
    ]
    return parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")


def test_quality_accepts_one_percent_rejected_rows_and_not_more() -> None:
    quality(_with_bad_rows(99, 1))  # 1/100 = %1 — sınırda, geçer

    with pytest.raises(ContractViolation, match="reddedilen satır 1/99") as caught:
        quality(_with_bad_rows(98, 1))
    assert REASON_RESULT in str(caught.value)
    assert "Ev " not in str(caught.value), "ihlal mesajı ham satır içeriği taşıyor"


def _with_bad_prices(bad: int) -> ParseResult:
    # 50 satır × 6 dolu Avg hücresi = 300 fiyat hücresi.
    rows = [main_row(n, {"AvgH": "x"} if n < bad else None) for n in range(50)]
    return parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")


def test_quality_accepts_one_percent_dropped_prices_and_not_more() -> None:
    quality(_with_bad_prices(3))  # 3/300 = %1 — sınırda, geçer

    with pytest.raises(ContractViolation, match="fiyat hücresi 4/300"):
        quality(_with_bad_prices(4))
