"""Dixon-Coles'u harness'ın `Strategy` arayüzüne takar (Faz 3 tasarımı §6.2).

Durum: grup (ülke, R94/R136) başına gözlenen goller, parça parça demetlerde (`CHUNK`): her
`observe` yalnız son parçayı kopyalar — ~45 bin sonuçlu bir grupta tam demet kopyası O(n²) olurdu.
Fit, karar gününün ISO günlük/haftalık tabanında (`cadence_days`) bir kez yapılır ve bir memo'da
tutulur. Memo eşitliğe girmez; anahtarı (grup, fit günü) ve fit yalnız `fit günü`nden ÖNCEKİ
maçları okur (`dixon_coles.fit`), bu yüzden memo geleceği taşıyamaz — en kötü hâli bayatlıktır.

Soy bekçisi (DEFERRED 16g (c), `docs/superpowers/specs/2026-10-01-dc-memo-anahtari.md`): `observe`
memo'yu yeni nesneye aynen taşır, yani aynı kök nesne ikinci bir maç kümesine oynatılırsa memo
başka kümenin fit'ini (isabet) ya da sıcak başlangıcını (ıska) verirdi. Her girdi fit anındaki
akışla mühürlenir; isabette girdinin, ıskada `latest`in mührü şimdiki akışın öneki değilse
`MemoReuseError`. Bekçi yalnız yükseltir: anahtar, fit ve `start` aynen — aynı soyda akış yalnız
uzar, bekçi tetiklenemez. Her oynatmaya yeni nesne kurulur (üretim yolları zaten öyle).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from types import MappingProxyType

from football_edge.backtest.harness import DecisionContext, Prediction, ResultRecord
from football_edge.backtest.timeline import LONDON
from football_edge.history.types import H2H, TOTALS_25
from football_edge.model.dixon_coles import (
    DCConfig,
    DCParams,
    GoalRecord,
    fit,
    outcome_probs,
    score_matrix,
    totals_probs,
)

CHUNK = 256
_ANCHOR_MONDAY = date(2000, 1, 3)
Chunk = tuple[GoalRecord, ...]
Chunks = tuple[Chunk, ...]


class MemoReuseError(RuntimeError):
    """Memo başka bir gözlem akışında kurulmuş: aynı nesne ikinci bir maç kümesine oynatıldı."""


@dataclass
class _FitMemo:
    """Değişebilir memo — bilinçli istisna: saf bir fonksiyonun sonucunu (grup, gün) ile saklar.

    `seals`: girdi başına fit anındaki akış (aynı parça nesneleri, kopya değil). `verified`: önek
    denetiminde içerikçe eşit bulunmuş DOLU parça çiftleri, (yeni, mühürlü) — 1X2/Ü-A paylaşımında
    her dolu parça bir kez karşılaştırılır; nesne tutulduğu için `id` başka nesneye geçemez."""

    fits: dict[tuple[str, date], DCParams | None] = field(default_factory=dict)
    latest: dict[str, DCParams] = field(default_factory=dict)
    seals: dict[tuple[str, date], Chunks] = field(default_factory=dict)
    verified: dict[int, tuple[Chunk, Chunk]] = field(default_factory=dict)


def _extends(sealed: Chunks, current: Chunks, verified: dict[int, tuple[Chunk, Chunk]]) -> bool:
    """Mühürlü akış şimdiki akışın öneki mi — kesin karşılaştırma (özet yok, çakışma yok).

    Parça sınırları konumdan gelir (`_append` hep son parçayı doldurur): mühürlü i. parça şimdiki
    i. parçanın başı olmalı. Aynı soyda dolu parçalar aynı nesnedir (`is`); son parça kayıtları
    aynı nesneler olduğundan dilim karşılaştırması da kısadır."""
    if len(current) < len(sealed):
        return False
    for old, new in zip(sealed, current, strict=False):
        if old is new:
            continue
        known = verified.get(id(new))
        if known is not None and known[0] is new and known[1] is old:
            continue
        if new[: len(old)] != old:
            return False
        if len(old) == len(new) == CHUNK:
            verified[id(new)] = (new, old)
    return True


def _append(chunks: Chunks, record: GoalRecord) -> Chunks:
    if not chunks or len(chunks[-1]) >= CHUNK:
        return (*chunks, (record,))
    return (*chunks[:-1], (*chunks[-1], record))


def fit_day(decided_on: date, cadence_days: int) -> date:
    """Karar gününden geriye, `cadence_days` adımlı sabit takvimde en yakın gün (≤ karar günü)."""
    return decided_on - timedelta(days=(decided_on - _ANCHOR_MONDAY).days % cadence_days)


def _no_history() -> Mapping[str, Chunks]:
    return MappingProxyType({})


def _no_groups() -> Mapping[str, str]:
    return MappingProxyType({})


@dataclass(frozen=True)
class DixonColesStrategy:
    config: DCConfig = DCConfig()
    groups: Mapping[str, str] = field(default_factory=_no_groups)
    market: str = H2H
    active_from: date | None = None  # öncesinde tahmin (ve fit) yok: ısınma hesabı boşa gitmez
    cadence_days: int = 1
    history: Mapping[str, Chunks] = field(default_factory=_no_history)
    memo: _FitMemo = field(default_factory=_FitMemo, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.market not in (H2H, TOTALS_25):
            raise ValueError(f"desteklenmeyen market: {self.market!r}")
        if self.cadence_days < 1:
            raise ValueError(f"cadence_days ≥ 1 olmalı: {self.cadence_days}")

    @property
    def name(self) -> str:
        return "dixon_coles" if self.market == H2H else "dixon_coles_ou25"

    def _group(self, league: str) -> str:
        return self.groups.get(league, league)

    def observe(self, result: ResultRecord) -> DixonColesStrategy:
        group = self._group(result.league)
        record = GoalRecord(
            result.home, result.away, result.home_goals, result.away_goals, result.date
        )
        chunks = _append(self.history.get(group, ()), record)
        return replace(self, history=MappingProxyType({**self.history, group: chunks}))

    def _guard(self, key: tuple[str, date], sealed: tuple[str, date], path: str) -> None:
        current = self.history.get(key[0], ())
        if not _extends(self.memo.seals[sealed], current, self.memo.verified):
            group, at = key
            raise MemoReuseError(
                f"DC memo'su başka bir gözlem akışında kurulmuş ({path}; grup {group!r}, fit günü "
                f"{at.isoformat()}): memo'nun {sealed[1].isoformat()} fit'inin mührü bu nesnenin "
                "gözlediği sonuçların öneki değil — aynı nesne ikinci bir maç kümesine "
                "oynatılamaz, her oynatmaya yeni nesne kurun"
            )

    def params(self, group: str, at: date) -> DCParams | None:
        key = (group, at)
        if key in self.memo.fits:
            self._guard(key, key, "isabet")
        else:
            latest = self.memo.latest.get(group)
            if latest is not None:
                self._guard(key, (group, latest.fitted_on), "ıska, sıcak başlangıç adayı")
            start = latest if latest is not None and latest.fitted_on < at else None
            chunks = self.history.get(group, ())
            records = [record for chunk in chunks for record in chunk]
            found = fit(records, at=at, config=self.config, start=start)
            self.memo.fits[key] = found
            self.memo.seals[key] = chunks
            if found is not None and (latest is None or latest.fitted_on < at):
                self.memo.latest[group] = found
        return self.memo.fits[key]

    def predict(self, context: DecisionContext) -> Prediction | None:
        if self.active_from is not None and context.date < self.active_from:
            return None
        decided_on = context.decision_at.astimezone(LONDON).date()
        found = self.params(self._group(context.league), fit_day(decided_on, self.cadence_days))
        if found is None:
            return None
        matrix = score_matrix(found, context.home, context.away, self.config.max_goals)
        if matrix is None:
            return None
        if self.market == H2H:
            probs = outcome_probs(matrix)
        else:
            over, under = totals_probs(matrix)
            probs = (over, under, 0.0)  # Ü/A iki yollu; üçüncü yuva hep 0 (harness 3-demet taşır)
        return Prediction(context.match_index, self.name, probs)
