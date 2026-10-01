"""DC memo'sunun soy bekçisi ve sıcak başlangıç yolu (DEFERRED 16g (c), 21b).

Tasarım: `docs/superpowers/specs/2026-10-01-dc-memo-anahtari.md` §3 (c), §5. Memo anahtarı
(grup, fit günü) aynen kalır; her girdi fit anındaki gözlem akışıyla mühürlenir. Bekçi isabette
girdinin, ıskada `memo.latest`in mührünü okur: mühür şimdiki akışın öneki değilse
`MemoReuseError`. Aynı nesne, mühürlü akışın öneki OLMADIĞI ikinci bir maç kümesine oynatılınca
sessizce eski fit'i ya da yabancı soydan sıcak başlangıcı taşımaz, adıyla düşer. Bilinen sınır
(`strategies.py` docstring'i): ilk kümeyi aynen içerip yalnız SONA kayıt ekleyen küme öneki korur.
Bekçi yalnız yükseltir: anahtar, fit ve `start` değişmez. Veri SENTETİK.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from football_edge.backtest.harness import ResultRecord, replay
from football_edge.history.types import TOTALS_25, HistMatch
from football_edge.model import strategies as model_strategies
from football_edge.model.dixon_coles import DCConfig, DCParams, GoalRecord
from football_edge.model.strategies import DixonColesStrategy, MemoReuseError
from tests.model_builders import TEAMS, main_history, season

CONFIG = DCConfig(xi=0.002, ridge=0.01, min_matches=40)
ACTIVE = date(2020, 7, 1)
HISTORY = main_history(2019, 2023)
DROPPED = "2223"
# I1 (inceleme r1): fark yalnız DOLU (eski) parçada — fit penceresindeki düzeltilmiş eski sezon.
LONG = main_history(2011, 2023)
LONG_ACTIVE = date(2016, 7, 1)
CORRECTED = "1415"


def _strategy(**kwargs: Any) -> DixonColesStrategy:
    return DixonColesStrategy(config=CONFIG, active_from=ACTIVE, **kwargs)


def _probs(
    matches: Sequence[HistMatch], strategy: DixonColesStrategy
) -> dict[int, tuple[float, ...]]:
    return {p.match_index: p.probs for p in replay(matches, strategy).predictions}


def _midweek(first_year: int, last_year: int) -> tuple[HistMatch, ...]:
    """Haftada iki tur: cumartesi (karar cuma) ve çarşamba (karar salı) — kadans 7'de iki karar
    aynı pazartesiye düşer, arada gözlenen sonuçlar memo isabetine akış olarak eklenir."""
    found: list[HistMatch] = []
    for year in range(first_year, last_year + 1):
        code = f"{year % 100:02d}{(year + 1) % 100:02d}"
        first = date(year, 8, 1)
        first += timedelta(days=(5 - first.weekday()) % 7)
        found.extend(season(code, first, seed=year))
        found.extend(
            replace(match, source_line=match.source_line + 1000)
            for match in season(code, first + timedelta(days=4), seed=year + 1000)
        )
    return tuple(sorted(found, key=lambda match: (match.date, match.source_line)))


def _dropped() -> tuple[HistMatch, ...]:
    return tuple(match for match in HISTORY if match.season != DROPPED)


def _flipped(history: Sequence[HistMatch] = HISTORY, code: str = DROPPED) -> tuple[HistMatch, ...]:
    """B1': gözlem SAYISI aynı, İÇERİK farklı — bir sezonun golleri ev↔deplasman çevrilir."""
    return tuple(
        replace(
            match,
            home_goals=match.away_goals,
            away_goals=match.home_goals,
            result={"H": "A", "A": "H"}.get(match.result, match.result),
        )
        if match.season == code
        else match
        for match in history
    )


def _corrected_old_season() -> tuple[HistMatch, ...]:
    """2014/15'in golleri düzeltilmiş (çevrilmiş) küme: `active_from` 2016'dan önce, fit penceresi
    içinde. İkinci oynatmanın ilk `params`ı bir isabettir; akış > 256 kayıt, fark 0. (dolu)
    parçada, son parça aynı — yalnız son parçayı karşılaştıran bekçi 448/448 eski fit'i taşırdı."""
    return _flipped(LONG, CORRECTED)


def _shifted() -> tuple[HistMatch, ...]:
    """Aynı maçlar üç gün sonra (cumartesi → salı): karar günleri ayrık, memo hiç isabet almaz."""
    return tuple(
        replace(
            match,
            date=match.date + timedelta(days=3),
            kickoff=None if match.kickoff is None else match.kickoff + timedelta(days=3),
        )
        for match in HISTORY
    )


@pytest.mark.parametrize(
    ("first", "active", "second", "path", "day"),
    [
        pytest.param(HISTORY, ACTIVE, _dropped, "isabet", "2023-08-04", id="B1-sezon-cikarildi"),
        pytest.param(HISTORY, ACTIVE, _flipped, "isabet", "2022-08-12", id="B1'-goller-cevrildi"),
        pytest.param(HISTORY, ACTIVE, _shifted, "ıska", "2020-08-04", id="1b-uc-gun-kaydirildi"),
        pytest.param(
            LONG,
            LONG_ACTIVE,
            _corrected_old_season,
            "isabet",
            "2016-08-05",
            id="I1-eski-sezon-dolu-parcada",
        ),
    ],
)
def test_a_strategy_replayed_on_a_second_match_set_is_refused(
    first: Sequence[HistMatch], active: date, second: Any, path: str, day: str
) -> None:
    """§5/1, 1b, 2: aynı kök nesne, mühürlü akışın öneki olmayan ikinci kümeye verilince bekçi ilk
    isabette ya da ilk ıskada adıyla düşer. Bekçisiz kod B1'de 2023/24'ün 56/56 tahminini tam
    kümeninkiyle BİREBİR döndürürdü; +3 günde fit'ler yabancı soydan (ya da soğuk) başlardı."""
    reused = DixonColesStrategy(config=CONFIG, active_from=active)
    _probs(first, reused)

    with pytest.raises(MemoReuseError, match=f"{path}.*{day}"):
        _probs(second(), reused)


def _chunk(goals: int) -> tuple[GoalRecord, ...]:
    return tuple(
        GoalRecord("Alfa", "Beta", goals, 0, date(2020, 1, 1) + timedelta(days=day))
        for day in range(model_strategies.CHUNK)
    )


def test_a_shorter_stream_is_not_extended_by_its_seal() -> None:
    """M1 (inceleme r1): akış tam parça sınırında biter, mühür bir kısmi parça daha taşır →
    önek değil (uzunluk denetimi)."""
    full = _chunk(1)
    extra = (GoalRecord("Gama", "Delta", 2, 2, date(2021, 1, 1)),)

    assert model_strategies._extends((full, extra), (full,), {}) is False
    assert model_strategies._extends((full,), (full, extra), {}) is True


def test_a_verified_chunk_is_rechecked_against_a_different_sealed_chunk() -> None:
    """M1: `verified` önbelleği (yeni, mühürlü) ÇİFTİNİ tutar; aynı yeni parça içerikçe farklı
    başka bir mühürlü parçayla karşılaştırılınca önbellek isabet saymaz."""
    sealed, other = _chunk(1), _chunk(3)
    current = tuple(list(sealed))  # içerikçe eşit, başka nesne
    verified: dict[int, Any] = {}

    assert current is not sealed
    assert model_strategies._extends((sealed,), (current,), verified) is True
    assert model_strategies._extends((other,), (current,), verified) is False


def test_the_refusal_names_the_cause_in_turkish() -> None:
    reused = _strategy()
    _probs(HISTORY, reused)

    with pytest.raises(MemoReuseError) as error:
        _probs(_dropped(), reused)

    message = str(error.value)
    assert "E0" in message and "öneki değil" in message and "yeni nesne" in message


@pytest.mark.parametrize(
    ("kind", "cadence", "fits"),
    [("main", 1, 56), ("main", 7, 56), ("midweek", 1, 112), ("midweek", 7, 60)],
)
def test_fresh_replays_keep_their_fit_count_and_bytes(
    monkeypatch: pytest.MonkeyPatch, kind: str, cadence: int, fits: int
) -> None:
    """§5/4: taze nesne + 1X2/Ü-A ortak memo (`wf_run.model_strategies` gibi) bekçiyi hiç
    tetiklemez; fit sayısı bekçisiz kodla aynı (ölçüldü: 56/56/112/60) ve olasılıklar bekçisi
    süreç içinde susturulmuş koşuyla `==`. Kadans 7'de anahtara toplam gözlem sayısı girerse cuma
    yeniden fit eder (haftada iki turda fit sayısı artar)."""
    history = HISTORY if kind == "main" else _midweek(2019, 2023)
    calls: list[date] = []
    real = model_strategies.fit

    def counting(*args: Any, **kwargs: Any) -> DCParams | None:
        calls.append(kwargs["at"])
        return real(*args, **kwargs)

    def both() -> list[dict[int, tuple[float, ...]]]:
        h2h = _strategy(cadence_days=cadence)
        totals = _strategy(cadence_days=cadence, market=TOTALS_25, memo=h2h.memo)
        return [_probs(history, h2h), _probs(history, totals)]

    monkeypatch.setattr(model_strategies, "fit", counting)
    guarded = both()
    assert len(calls) == len(set(calls)) == fits

    monkeypatch.setattr(model_strategies, "_extends", lambda *args: True)
    assert both() == guarded


@dataclass(frozen=True)
class _Call:
    group: str
    at: date
    start: DCParams | None
    found: DCParams | None


def _recording(monkeypatch: pytest.MonkeyPatch, groups: dict[str, str]) -> list[_Call]:
    """`fit`i sarar: her çağrının grubu (kayıtların takımından), günü, başlangıcı ve sonucu."""
    calls: list[_Call] = []
    real = model_strategies.fit

    def recording(
        records: Sequence[GoalRecord], *, at: date, config: DCConfig, start: DCParams | None
    ) -> DCParams | None:
        found = real(records, at=at, config=config, start=start)
        calls.append(_Call(groups[records[0].home], at, start, found))
        return found

    monkeypatch.setattr(model_strategies, "fit", recording)
    return calls


SECOND_TEAMS = ("Kuzey", "Güney", "Doğu", "Batı", "Dağ", "Ova", "Göl", "Irmak")


def test_each_fit_warm_starts_from_the_previous_fit_of_its_own_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """21b: backtest'in sıcak başlangıç zinciri (`memo.latest`) — her grubun ilk fit'i soğuk,
    sonrakiler aynı grubun bir önceki fit'inden başlar (nesne kimliği). Hep soğuk başlatan ya da
    başka grubun `latest`ini veren kaynak kırmızı olur."""
    second = tuple(
        match
        for year in range(2019, 2022)
        for match in season(
            f"{year % 100:02d}{(year + 1) % 100:02d}",
            date(year, 8, 3),
            league="E1",
            seed=year + 500,
            teams=SECOND_TEAMS,
        )
    )
    first = main_history(2019, 2021)
    matches = tuple(sorted((*first, *second), key=lambda m: (m.date, m.league, m.source_line)))
    team_group = {**dict.fromkeys(TEAMS, "Bir"), **dict.fromkeys(SECOND_TEAMS, "İki")}
    calls = _recording(monkeypatch, team_group)

    _probs(matches, _strategy(groups={"E0": "Bir", "E1": "İki"}))

    previous: dict[str, DCParams] = {}
    for call in calls:
        assert call.found is not None, call
        assert call.start is previous.get(call.group), call
        previous[call.group] = call.found
    assert set(previous) == {"Bir", "İki"}
    assert len(calls) > 2 * len(previous)


def test_a_fit_for_an_earlier_day_never_starts_from_a_later_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """21b: `latest.fitted_on < at` koşulu — sonraki günün fit'i önceki günün optimizer başlangıcı
    olmaz (sıra dışı çağrı) ve `latest`i geri almaz. Aynı nesnede sıra dışı çağrı bekçiyi
    tetiklemez: akış aynı."""
    state = DixonColesStrategy(config=CONFIG)
    for match in HISTORY:
        known = datetime.combine(match.date + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        state = state.observe(
            ResultRecord(
                match.league,
                match.date,
                match.home,
                match.away,
                match.home_goals,
                match.away_goals,
                known,
            )
        )
    calls = _recording(monkeypatch, dict.fromkeys(TEAMS, "E0"))
    late, early, later = date(2023, 1, 2), date(2022, 1, 3), date(2023, 6, 5)

    late_fit = state.params("E0", late)
    state.params("E0", early)
    state.params("E0", later)

    assert [call.at for call in calls] == [late, early, later]
    assert calls[0].start is None
    assert calls[1].start is None  # gelecekteki fit başlangıç olmaz
    assert late_fit is not None and calls[2].start is late_fit  # erken fit latest'i geri almadı
