"""Sentetik football-data CSV'leri: ölçülen sütun adları, programla kurulan SENTETİK satırlar.

Ölçülen başlığın kendisi yalnız `MAIN_2526` (ölçüm belgesi §2.2) ve 25 sütunlu `EXTRA_NEW`dir
(§2.2). `MAIN_2627`, `MAIN_OLD` ve `EXTRA_RUS` ölçülen sütun AİLELERİNDEN kurulur (§2.2/§2.4):
o dönemin biçimini taşırlar ama gerçek bir dosyanın başlığı değildirler.

Sütun adları içerik değildir; takım adları ("Ev 3"), tarihler ve fiyatlar uydurmadır. Depoya,
loga ya da artifact'e gerçek maç/oran satırı girmez (tasarım §4.3, Ruling 4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from football_edge.history.catalog import EXTRA, MAIN, HistoryLeague

# Ölçülen 2025/26 ana lig başlığı (132 sütun, /mmz4281/2526/E0.csv — ölçüm belgesi §2.2).
_MAIN_2526 = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Referee,HS,AS,HST,AST,HF,"
    "AF,HC,AC,HY,AY,HR,AR,B365H,B365D,B365A,BFDH,BFDD,BFDA,BMGMH,BMGMD,BMGMA,BVH,BVD,BVA,"
    "BWH,BWD,BWA,CLH,CLD,CLA,LBH,LBD,LBA,PSH,PSD,PSA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,BFEH,"
    "BFED,BFEA,B365>2.5,B365<2.5,P>2.5,P<2.5,Max>2.5,Max<2.5,Avg>2.5,Avg<2.5,BFE>2.5,"
    "BFE<2.5,AHh,B365AHH,B365AHA,PAHH,PAHA,MaxAHH,MaxAHA,AvgAHH,AvgAHA,BFEAHH,BFEAHA,"
    "B365CH,B365CD,B365CA,BFDCH,BFDCD,BFDCA,BMGMCH,BMGMCD,BMGMCA,BVCH,BVCD,BVCA,BWCH,BWCD,"
    "BWCA,CLCH,CLCD,CLCA,LBCH,LBCD,LBCA,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA,"
    "BFECH,BFECD,BFECA,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,MaxC>2.5,MaxC<2.5,AvgC>2.5,"
    "AvgC<2.5,BFEC>2.5,BFEC<2.5,AHCh,B365CAHH,B365CAHA,PCAHH,PCAHA,MaxCAHH,MaxCAHA,AvgCAHH,"
    "AvgCAHA,BFECAHH,BFECAHA"
)
MAIN_2526: tuple[str, ...] = tuple(_MAIN_2526.split(","))

_PINNACLE = frozenset(
    {"PSH", "PSD", "PSA", "PSCH", "PSCD", "PSCA", "P>2.5", "P<2.5", "PC>2.5", "PC<2.5"}
    | {"PAHH", "PAHA", "PCAHH", "PCAHA"}
)


def _season_2627() -> tuple[str, ...]:
    """2026/27 biçimi: `HxG`, `AxG` Referee'den sonra; Pinnacle sütunları yok (ölçüm §2.4).

    Ölçülen dosya 114 sütun; burada 120 — düşen öteki altı sütun ölçüm belgesinde adlandırılmıyor
    ve hiçbiri ayrıştırıcının okuduğu sütunlardan değil.
    """
    kept = tuple(name for name in MAIN_2526 if name not in _PINNACLE)
    at = kept.index("Referee") + 1
    return (*kept[:at], "HxG", "AxG", *kept[at:])


MAIN_2627: tuple[str, ...] = _season_2627()

# 2012/13–2018/19 biçimi, ölçülen sütun ailelerinden kurulmuş (§2.4 tarihçesi; ölçülen bir
# dosyanın başlığı DEĞİL): Time yok; kapanış öncesi Betbrain ortalaması/en iyisi (BbAv/BbMx),
# Pinnacle kapanışı (PSC) 2012/13'ten; AvgC/MaxC henüz yok.
_MAIN_OLD = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Referee,HS,AS,HST,AST,HF,AF,HC,"
    "AC,HY,AY,HR,AR,B365H,B365D,B365A,PSH,PSD,PSA,BbMxH,BbAvH,BbMxD,BbAvD,BbMxA,BbAvA,"
    "BbMx>2.5,BbAv>2.5,BbMx<2.5,BbAv<2.5,BbAH,BbAHh,PSCH,PSCD,PSCA"
)
MAIN_OLD: tuple[str, ...] = tuple(_MAIN_OLD.split(","))

# Ek lig dosyası (/new/<kod>.csv, 25 sütun) ve RUS'un 19 sütunlu biçimi (BFEC*, B365C* yok).
_EXTRA = (
    "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,"
    "AvgCH,AvgCD,AvgCA,BFECH,BFECD,BFECA,B365CH,B365CD,B365CA"
)
EXTRA_NEW: tuple[str, ...] = tuple(_EXTRA.split(","))
EXTRA_RUS: tuple[str, ...] = tuple(
    name for name in EXTRA_NEW if not name.startswith(("BFEC", "B365C"))
)

E0 = HistoryLeague(
    code="E0",
    league_id="eng.1",
    name="Premier League",
    country="England",
    tier=1,
    kind=MAIN,
    first_season="2526",
    odds_api_key="soccer_epl",
)
BRA = HistoryLeague(
    code="BRA",
    league_id="bra.1",
    name="Serie A",
    country="Brazil",
    tier=1,
    kind=EXTRA,
    first_season="",
    odds_api_key="",
)


def main_row(n: int = 0, cells: Mapping[str, str] | None = None) -> dict[str, str]:
    """Geçerli sentetik ana lig satırı (2-1 ev sahibi galibiyeti); `cells` alanları ezer."""
    base = {
        "Div": "E0",
        "Date": "16/08/2025",
        "Time": "15:00",
        "HomeTeam": f"Ev {n}",
        "AwayTeam": f"Deplasman {n}",
        "FTHG": "2",
        "FTAG": "1",
        "FTR": "H",
        "AvgH": "2.10",
        "AvgD": "3.40",
        "AvgA": "3.50",
        "AvgCH": "2.05",
        "AvgCD": "3.45",
        "AvgCA": "3.60",
    }
    return {**base, **(cells or {})}


def extra_row(n: int = 0, cells: Mapping[str, str] | None = None) -> dict[str, str]:
    """Geçerli sentetik ek lig satırı (1-1 beraberlik, yalnız kapanış); `cells` alanları ezer."""
    base = {
        "Country": "Ulke",
        "League": "Lig",
        "Season": "2025",
        "Date": "16/08/2025",
        "Time": "23:30",
        "Home": f"Ev {n}",
        "Away": f"Deplasman {n}",
        "HG": "1",
        "AG": "1",
        "Res": "D",
        "PSCH": "2.55",
        "PSCD": "3.30",
        "PSCA": "2.95",
        "AvgCH": "2.50",
        "AvgCD": "3.20",
        "AvgCA": "2.90",
    }
    return {**base, **(cells or {})}


def unique_prices(header: Sequence[str], after: str) -> dict[str, str]:
    """`after`dan sonraki HER sütuna ayrı bir fiyat: hangi sütunun hangi anahtara gittiği
    değerden okunur (2.00, 2.01, …)."""
    start = list(header).index(after) + 1
    return {name: f"{2 + index / 100:.2f}" for index, name in enumerate(header[start:])}


def csv_bytes(
    header: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    *,
    encoding: str = "utf-8",
    bom: bool = False,
) -> bytes:
    """football-data biçimi: virgül, CRLF; başlıkta olmayan anahtar yazılmaz."""
    lines = [",".join(header), *(",".join(row.get(name, "") for name in header) for row in rows)]
    body = ("\r\n".join(lines) + "\r\n").encode(encoding)
    return b"\xef\xbb\xbf" + body if bom else body
