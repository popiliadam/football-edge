from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime

import pytest

from football_edge.collector import ContractViolation
from football_edge.history.catalog import HistoryLeague
from football_edge.history.football_data import (
    CLOSING_REFERENCE,
    ODDS_COLUMNS,
    REASON_DATE,
    REASON_DIVISION,
    REASON_DUPLICATE,
    REASON_GOALS,
    REASON_RESULT,
    REASON_SEASON,
    REASON_SEASON_FORMAT,
    REASON_TEAM,
    REASON_TIME,
    REASON_WIDTH,
    REASON_WINDOW,
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
    widen,
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


def main_line(row: Mapping[str, str]) -> str:
    """Ana lig kaydı, tırnaksız: virgül içeren hücre kaydın genişliğini değiştirir."""
    return ",".join(row.get(name, "") for name in MAIN_2526)


def lines_bytes(*lines: str) -> bytes:
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


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
    row = main_row(0, {**prices, "Date": "19/08/2017"})
    match = one_match(csv_bytes(MAIN_OLD, [row]), season="1718")

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
    cells = {**prices, "HxG": "1", "AxG": "2", "Date": "15/08/2026"}
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


def test_header_names_are_stripped_before_the_columns_are_looked_up() -> None:
    padded = ",".join(f" {name} " for name in MAIN_2526)

    result = parse_file(lines_bytes(padded, main_line(main_row(0))), league=E0, season="2526")

    (match,) = result.matches
    assert result.columns == MAIN_2526
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
    ("text", "season", "expected"),
    [
        ("16/08/05", "0506", date(2005, 8, 16)),
        ("18/08/12", "1213", date(2012, 8, 18)),
        ("16/08/2025", "2526", date(2025, 8, 16)),
    ],
    ids=["iki-haneli-yil", "iki-haneli-yil-2012", "dort-haneli-yil"],
)
def test_two_and_four_digit_years_give_the_source_date(
    text: str, season: str, expected: date
) -> None:
    match = one_match(csv_bytes(MAIN_2526, [main_row(0, {"Date": text})]), season=season)

    assert match.date == expected


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("16/08/68", date(2068, 8, 16)),
        ("16/08/69", date(1969, 8, 16)),
        ("16/08/99", date(1999, 8, 16)),
    ],
    ids=["68-2068", "69-1969", "99-1999"],
)
def test_two_digit_years_follow_the_posix_century_rule(text: str, expected: date) -> None:
    """`datetime.strptime("%y")` kuralı: 69–99 → 19xx, 00–68 → 20xx. Ek lig düzeninde sınanır:
    ana ligde sezon penceresi bu tarihleri zaten reddeder."""
    match = one_match(csv_bytes(EXTRA_NEW, [extra_row(0, {"Date": text})]), season=None)

    assert match.date == expected


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("day", "clock", "season", "expected"),
    [
        ("16/08/2025", "15:00", "2526", datetime(2025, 8, 16, 14, 0, tzinfo=UTC)),
        ("06/12/2025", "15:00", "2526", datetime(2025, 12, 6, 15, 0, tzinfo=UTC)),
        ("29/03/2026", "01:30", "2526", datetime(2026, 3, 29, 1, 30, tzinfo=UTC)),
        ("25/10/2026", "01:30", "2627", datetime(2026, 10, 25, 1, 30, tzinfo=UTC)),
    ],
    ids=["yaz-saati", "kis-saati", "ilkbahar-boslugu-gec-okuma", "sonbahar-tekrari-gec-okuma"],
)
def test_london_kickoff_becomes_utc_and_a_dst_edge_takes_the_later_reading(
    day: str, clock: str, season: str, expected: datetime
) -> None:
    """D5: Time Europe/London yerel saatidir. Geçişte iki yorumun GEÇ olanı: sonuç bilinme anı
    (başlama + 3 sa) gerçek andan önceye düşmesin."""
    row = main_row(0, {"Date": day, "Time": clock})
    match = one_match(csv_bytes(MAIN_2526, [row]), season=season)

    assert match.kickoff == expected
    assert match.kickoff is not None and match.kickoff.utcoffset() == UTC.utcoffset(None)


@pytest.mark.leakage
def test_no_time_column_or_an_empty_time_gives_no_kickoff() -> None:
    old = one_match(csv_bytes(MAIN_OLD, [main_row(0, {"Date": "19/08/2017"})]), season="1718")
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


# Son sütunu dolu kayıt: kayma son hücreyi başlığın dışına iter, fazla hücre DOLU kalır.
_LAST_FILLED = {MAIN_2526[-1]: "1.90"}


@pytest.mark.parametrize(
    "record",
    [
        pytest.param(main_line(main_row(1)).rsplit(",", 1)[0], id="kisa-satir"),
        pytest.param(main_line(main_row(1)).rsplit(",", 3)[0], id="kisa-satir-uc-eksik"),
        pytest.param(main_line(main_row(1)) + ",x", id="uzun-satir-sonu-dolu"),
        pytest.param(main_line(main_row(1)) + ",,, x", id="uzun-satir-bos-sonra-dolu"),
        pytest.param(
            main_line(main_row(1, {**_LAST_FILLED, "HomeTeam": "Ev, 1"})), id="tirnaksiz-virgul"
        ),
        pytest.param(main_line(main_row(1, {**_LAST_FILLED, "AvgH": "2,5"})), id="virgullu-fiyat"),
    ],
)
def test_a_record_whose_width_differs_from_the_header_is_rejected(record: str) -> None:
    """Kaymış kayıt fiyatları yanlış sütuna taşır: sayılır ve düşer, hücresi fiyat sayılmaz. Kısa
    kayda hoşgörü yok; uzun kayıt yalnız fazlası TÜMÜYLE boşsa kırpılır (R111) — fazlada tek dolu
    hücre kaymanın izidir."""
    content = lines_bytes(
        ",".join(MAIN_2526), main_line(main_row(0)), record, main_line(main_row(2))
    )

    result = parse_file(content, league=E0, season="2526")

    assert [match.source_line for match in result.matches] == [1, 3]
    assert result.rejected == (Rejected(line=2, reason=REASON_WIDTH),)
    assert (result.price_cells, result.dropped_prices) == (12, 0), "kaymış kaydın hücresi sayılmış"
    assert result.trimmed_rows == 0, "reddedilen kayıt kırpılmış sayıldı"


_THREE = [main_row(n) for n in range(3)]


@pytest.mark.parametrize(
    "excess",
    [
        pytest.param(",", id="bir-bos"),
        pytest.param(",,,", id="uc-bos-olculen-bicim"),
        pytest.param(", ,\t,  ", id="yalniz-bosluk"),
    ],
)
def test_a_longer_record_with_only_empty_excess_is_trimmed_and_parsed_like_a_normal_row(
    excess: str,
) -> None:
    """R111: fazla hücreler sonda ve boşsa (`.strip()` sonrası) kayıt başlık genişliğine kırpılır;
    sonuç, fazlasız aynı kaydın ayrıştırmasıyla birebir aynıdır."""
    plain = parse_file(csv_bytes(MAIN_2526, _THREE), league=E0, season="2526")

    result = parse_file(widen(csv_bytes(MAIN_2526, _THREE), 2, excess), league=E0, season="2526")

    assert result.rejected == ()
    assert result.matches == plain.matches
    assert (result.price_cells, result.dropped_prices) == (18, 0)
    assert result.trimmed_rows == 1
    assert plain.trimmed_rows == 0


def test_the_trimmed_count_is_per_record_not_a_flag() -> None:
    content = csv_bytes(MAIN_2526, [main_row(n) for n in range(4)])

    result = parse_file(widen(widen(content, 1, ",,,"), 3, ","), league=E0, season="2526")

    assert (len(result.matches), result.rejected, result.trimmed_rows) == (4, (), 2)


def test_a_trimmed_record_still_faces_every_row_check() -> None:
    """Kırpma yalnız genişliği onarır: kırpılan kayıt öteki kurallardan aynen geçer ve hücreleri
    normal kayıt gibi sayılır (R103 yalnız genişlik reddinde sıfır sayar)."""
    rows = [main_row(0), main_row(1, {"FTR": "A"}), main_row(2)]

    result = parse_file(widen(csv_bytes(MAIN_2526, rows), 2, ",,,"), league=E0, season="2526")

    assert [match.source_line for match in result.matches] == [1, 3]
    assert result.rejected == (Rejected(line=2, reason=REASON_RESULT),)
    assert (result.price_cells, result.trimmed_rows) == (18, 1)


_UNCLOSED_LAST = [*(main_row(n) for n in range(4)), main_row(4, {"HomeTeam": '"Ev 4'})]
_QUOTE_PAIR = [
    main_row(0),
    main_row(1, {"HomeTeam": '"Ev 1'}),
    main_row(2),
    main_row(3, {"HomeTeam": 'Ev 3"'}),
    main_row(4),
]


@pytest.mark.parametrize(
    ("content", "league", "season", "path"),
    [
        pytest.param(
            csv_bytes(MAIN_2526, _UNCLOSED_LAST),
            E0,
            "2526",
            "/mmz4281/2526/E0.csv",
            id="dengesiz-tirnak-sonda",
        ),
        pytest.param(
            csv_bytes(MAIN_2526, _UNCLOSED_LAST).rstrip(b"\r\n"),
            E0,
            "2526",
            "/mmz4281/2526/E0.csv",
            id="dengesiz-tirnak-son-satir-sonsuz",
        ),
        pytest.param(
            csv_bytes(MAIN_2526, [main_row(0), main_row(1, {"HomeTeam": '"Ev 1"x'}), main_row(2)]),
            E0,
            "2526",
            "/mmz4281/2526/E0.csv",
            id="kapanan-tirnaktan-sonra-metin",
        ),
        pytest.param(
            csv_bytes(MAIN_2526, _QUOTE_PAIR),
            E0,
            "2526",
            "/mmz4281/2526/E0.csv",
            id="kayitlar-arasi-tirnak-cifti",
        ),
        pytest.param(
            csv_bytes(EXTRA_NEW, [extra_row(0), extra_row(1, {"Home": '"Ev 1'})]),
            BRA,
            None,
            "/new/BRA.csv",
            id="ek-lig-dengesiz-tirnak",
        ),
    ],
)
def test_broken_quoting_fails_the_whole_file_and_names_it(
    content: bytes, league: HistoryLeague, season: str | None, path: str
) -> None:
    """Dengesiz tırnak sonraki satırları sayılmadan yutar: kısmî ayrıştırma yok, dosya düşer
    (Ruling 6). Katı okuyucu kapanmayan tırnağı (satır sonu olmayan son satırda da) ve kapanan
    tırnaktan sonraki metni hata sayar; kayıtlar arasında kapanan tırnak çifti hata değildir ama
    iki kaydı tam genişlikte tek kayda katlayabilir — aradaki satır sessizce kaybolurdu. İhlal
    dosyayı adlandırır, satır içeriği taşımaz (Ruling 4)."""
    with pytest.raises(ContractViolation, match="CSV") as caught:
        parse_file(content, league=league, season=season)

    assert str(caught.value).startswith(f"{path}: ")
    assert "Ev " not in str(caught.value), "ihlal mesajı ham satır içeriği taşıyor"


def test_a_quote_pair_across_records_is_caught_with_cr_only_line_endings_too() -> None:
    """Yalnız CR satır sonlu dosyada yutulan satırlar hücreye `\\r` ile girer, `\\n` ile değil."""
    rows = [
        main_row(0),
        main_row(1, {"HomeTeam": '"Ev 1'}),
        main_row(2),
        main_row(3, {"HomeTeam": 'Ev 3"'}),
    ]
    content = csv_bytes(MAIN_2526, rows).replace(b"\r\n", b"\r")

    with pytest.raises(ContractViolation, match="birden çok satıra"):
        parse_file(content, league=E0, season="2526")


def test_a_main_row_of_another_division_is_rejected() -> None:
    """E0 dosyasında `Div` E1 olan satır başka ligin maçıdır (karışık ya da yanlış dosya)."""
    rows = [main_row(0), main_row(1, {"Div": "E1"}), main_row(2, {"Div": ""})]

    result = parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")

    assert [match.source_line for match in result.matches] == [1]
    assert result.rejected == (Rejected(2, REASON_DIVISION), Rejected(3, REASON_DIVISION))


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("season", "day", "kept"),
    [
        ("2526", "01/06/2025", True),
        ("2526", "31/07/2026", True),
        ("1920", "26/07/2020", True),
        ("2526", "31/05/2025", False),
        ("2526", "01/08/2026", False),
        ("2526", "16/08/2015", False),
        ("1920", "02/08/2020", True),
        ("1920", "31/08/2020", True),
        ("1920", "01/09/2020", False),
    ],
    ids=[
        "pencere-basi",
        "pencere-sonu",
        "uzatilmis-2019-20",
        "pencereden-once",
        "pencereden-sonra",
        "baska-sezon",
        "serie-a-2019-20-agustos",
        "uzatilmis-pencere-sonu",
        "uzatilmis-pencereden-sonra",
    ],
)
def test_a_main_row_is_kept_only_inside_its_season_window(
    season: str, day: str, kept: bool
) -> None:
    """Sezon "YYyy" → [YYYY-06-01, YYYY+1-07-31]; tek istisna COVID ile uzayan 2019/20, penceresi
    31/08/2020'de kapanır (Serie A son haftası 1–2 Ağustos 2020, R105). İstisna yalnız o sezondur:
    pencere dönem sınırını korur. Pencere dışı tarih başka sezonun satırıdır ve dönem ayrımı tarihe
    bakar: 2025/26 dosyasındaki 2015 tarihi geliştirme dönemine sızardı."""
    result = parse_file(
        csv_bytes(MAIN_2526, [main_row(0, {"Date": day})]), league=E0, season=season
    )

    assert len(result.matches) == (1 if kept else 0)
    assert result.rejected == (() if kept else (Rejected(1, REASON_WINDOW),))


def test_an_extra_row_without_a_season_is_rejected() -> None:
    rows = [extra_row(0), extra_row(1, {"Season": ""})]

    result = parse_file(csv_bytes(EXTRA_NEW, rows), league=BRA, season=None)

    assert result.rejected == (Rejected(line=2, reason=REASON_SEASON),)


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        ("2000", True),
        ("2100", True),
        ("2024/2025", True),
        ("1999", False),
        ("2101", False),
        ("2024/1999", False),
        ("x", False),
        ("25", False),
        ("2024-2025", False),
    ],
)
def test_an_extra_season_must_be_a_year_or_a_year_pair(text: str, kept: bool) -> None:
    """Ek lig `Season`ı "YYYY" ya da "YYYY/YYYY", yıllar [2000, 2100]; başka her şey kaymış ya da
    bozuk satırdır ve `HistMatch.season`a girmez."""
    result = parse_file(
        csv_bytes(EXTRA_NEW, [extra_row(0, {"Season": text})]), league=BRA, season=None
    )

    assert result.rejected == (() if kept else (Rejected(1, REASON_SEASON_FORMAT),))


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


@pytest.mark.parametrize("text", ["inf", "-inf", "nan", "1e400"])
def test_a_non_finite_price_is_dropped(text: str) -> None:
    """`nan > 1.0` zaten yanlış ama `inf > 1.0` doğru: sonluluk denetimi olmadan inf fiyat
    olurdu."""
    result = parse_file(
        csv_bytes(MAIN_2526, [main_row(0, {"AvgH": text})]), league=E0, season="2526"
    )

    assert result.dropped_prices == 1
    assert result.matches[0].prices("Avg", H2H, PRE_CLOSING) is None


def test_a_price_just_above_one_is_kept() -> None:
    result = parse_file(
        csv_bytes(MAIN_2526, [main_row(0, {"AvgH": "1.001"})]), league=E0, season="2526"
    )

    assert result.dropped_prices == 0
    assert result.matches[0].odds[OddsKey("Avg", H2H, "H", PRE_CLOSING)] == 1.001


def test_price_cells_of_rejected_and_duplicate_rows_are_counted() -> None:
    """Sayım bütün dolu satırlar üzerindendir: reddedilen ve yinelenen satırın hücresi de paya ve
    paydaya girer. Yalnız genişliği farklı kayıt dışarıda kalır — hücresi hiçbir sütuna ait
    değildir."""
    rows = [main_row(0), main_row(1, {"FTR": "A", "AvgH": "x"}), main_row(0, {"AvgD": "y"})]

    result = parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")

    assert [entry.reason for entry in result.rejected] == [REASON_RESULT, REASON_DUPLICATE]
    assert (result.price_cells, result.dropped_prices) == (18, 2)


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
    with pytest.raises(ValueError, match="sezon kodu"):
        parse_file(csv_bytes(MAIN_2526, [main_row(0)]), league=E0, season="2527")


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
    row = main_row(0, {"Date": f"16/08/20{season[:2]}"})
    result = parse_file(csv_bytes(header, [row]), league=E0, season=season)

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


@pytest.mark.parametrize("missing", CLOSING_REFERENCE)
def test_quality_expects_every_avgc_1x2_column_from_2019_20(missing: str) -> None:
    """Üç sütundan YALNIZ BİRİ eksikse de dönem beklentisi bozulur (kırpılmış ya da kaymış
    dosya)."""
    header = tuple(name for name in MAIN_2526 if name != missing)
    result = parse_file(csv_bytes(header, [main_row(0)]), league=E0, season="2526")

    with pytest.raises(ContractViolation, match=re.escape(f"['{missing}'] sütunu yok")):
        quality(result)


def _with_closing(complete: int, total: int) -> ParseResult:
    """`total` maç; ilk `complete` tanesinde AvgC 1X2 dolu, ötekilerde sütun var ama hücre boş."""
    empty = dict.fromkeys(CLOSING_REFERENCE, "")
    rows = [main_row(n, None if n < complete else empty) for n in range(total)]
    return parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")


def test_quality_expects_avgc_1x2_prices_in_at_least_half_the_matches() -> None:
    """Sütunlar var ama fiyatlar boşsa kapanış referansı (D3) yoktur: sessiz geçemez. Tam %50
    geçer."""
    quality(_with_closing(2, 4))

    with pytest.raises(ContractViolation, match="AvgC 1X2 1/3 maçta tam"):
        quality(_with_closing(1, 3))
    with pytest.raises(ContractViolation, match="AvgC 1X2 0/380 maçta tam"):
        quality(_with_closing(0, 380))


def test_quality_reports_the_rejections_when_every_row_is_rejected() -> None:
    """Bütün satırları reddedilen dosya ret nedenleriyle düşer; "yalnız başlık satırı" değildir."""
    with pytest.raises(ContractViolation, match="reddedilen satır 3/3") as caught:
        quality(_with_bad_rows(0, 3))

    assert "hiç maç yok" not in str(caught.value)


def _missing_column() -> ParseResult:
    kept = tuple(name for name in MAIN_2526 if name != "FTR")
    return parse_file(csv_bytes(kept, [main_row(0)]), league=E0, season="2526")


def _no_closing_columns() -> ParseResult:
    kept = tuple(name for name in MAIN_2526 if not name.startswith("AvgC"))
    return parse_file(csv_bytes(kept, [main_row(0)]), league=E0, season="2526")


def _header_only() -> ParseResult:
    return parse_file(csv_bytes(MAIN_2526, []), league=E0, season="2526")


@pytest.mark.parametrize(
    ("build", "reason"),
    [
        (_missing_column, "zorunlu sütun yok"),
        (_no_closing_columns, "sütunu yok"),
        (lambda: _with_closing(0, 2), "maçta tam"),
        (lambda: _with_bad_rows(98, 2), "reddedilen satır"),
        (lambda: _with_bad_prices(4), "yok sayılan fiyat hücresi"),
        (_header_only, "hiç maç yok"),
    ],
    ids=[
        "zorunlu-sutun",
        "donem-sutunu",
        "donem-dolulugu",
        "reddedilen-satir",
        "fiyat-hucresi",
        "hic-mac-yok",
    ],
)
def test_every_quality_violation_names_the_file_first(
    build: Callable[[], ParseResult], reason: str
) -> None:
    """İhlal loga düşer (Ruling 4): hangi dosya olduğunu her mesaj ilk sözcüğüyle söyler."""
    path = "/mmz4281/2526/E0.csv"

    with pytest.raises(ContractViolation, match=reason) as caught:
        check_quality(build(), path=path, league=E0, season="2526")

    assert str(caught.value).startswith(f"{path}: "), "ihlal mesajı dosyayı adlandırmıyor"
