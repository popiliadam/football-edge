"""Dönemler ve holdout erişimi (tasarım §5.1, §5.3; D2, D8).

Dönem üyeliği yalnız kaynağın `Date`'iyle (`HistMatch.date`) belirlenir: başlama saatinin saat
dilimi dönüşümüne bağlı değildir, her makinede aynı sonucu verir. Holdout satırları
`select_periods`ten yalnız `open_holdout`un kurduğu anahtarla çıkar. `open_holdout` açılışı
`holdout_access_log`a (append-only, 0007) yazar ve anahtarı ancak kayıt commit'lendikten SONRA
döner; faz kapıları açılış sayısını bu kayıttan okur (Faz 2: sıfır). `open_holdout`ın yalnız
`backtest/final_eval.py`de, mührün yalnız bu modülde anılabildiğini
`tests/test_holdout_access_rule.py` zorlar.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import psycopg

from football_edge.history.types import HistMatch

DEV_END = date(2025, 7, 1)
HOLDOUT_END = date(2026, 7, 1)
DEV = "dev"
HOLDOUT = "holdout"
POST = "post"
_PERIODS = frozenset({DEV, HOLDOUT, POST})

# Modüle özel mühür: geçerli anahtarı yalnız `open_holdout` kurar. Elle kurulan bir `HoldoutKey`
# bu nesneyi taşımaz ve holdout'u açmaz.
_HOLDOUT_SEAL = object()
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_INSERT_ACCESS = "INSERT INTO holdout_access_log (opened_at, git_sha, purpose) VALUES (%s, %s, %s)"


class HoldoutLocked(RuntimeError):
    """Holdout geçerli bir anahtar olmadan istendi."""


@dataclass(frozen=True)
class HoldoutKey:
    """Kayda geçmiş bir holdout açılışı. Geçerli anahtarı yalnız `open_holdout` kurar."""

    opened_at: datetime
    purpose: str
    git_sha: str
    _seal: object = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class Window:
    """Maçın kaynak tarihine göre [start, end); `start` None ise alt sınır yoktur.

    Kurulum iki durumda `ValueError` verir (R89). `end > DEV_END`: `in_window` anahtar sormaz,
    bu yüzden pencere holdout'a uzanamaz. `start >= end`: boş ya da ters pencere sessizce hiçbir
    şey seçmesin.
    """

    start: date | None
    end: date

    def __post_init__(self) -> None:
        if self.end > DEV_END:
            raise ValueError(f"pencere holdout'a uzanamaz: end {self.end}, sınır {DEV_END}")
        if self.start is not None and self.start >= self.end:
            raise ValueError(f"boş pencere: start {self.start}, end {self.end}")


# Ana ligler: kapanış öncesi Avg, kapanış AvgC ve başlama saati 2019/20'den beri birlikte var.
MAIN_WINDOW = Window(date(2019, 7, 1), DEV_END)
# Ek ligler: yalnız kapanış sütunları; dosyanın ilk satırından geliştirme sonuna.
EXTRA_WINDOW = Window(None, DEV_END)


def in_window(match: HistMatch, window: Window) -> bool:
    after_start = window.start is None or match.date >= window.start
    return after_start and match.date < window.end


def period_of(match_date: date) -> str:
    if match_date < DEV_END:
        return DEV
    if match_date < HOLDOUT_END:
        return HOLDOUT
    return POST


def open_holdout(
    conn: psycopg.Connection[Any], *, purpose: str, git_sha: str, now: datetime
) -> HoldoutKey:
    """Açılışı `holdout_access_log`a yazar; anahtarı YALNIZ kayıt commit'lendikten sonra döner.

    Maç verisi okumaz: anahtar yalnız `select_periods`e verilir. `conn.transaction()` yerine açık
    commit: çağıranın açık bir işlemi varsa `transaction()` yalnız savepoint açar ve commit
    etmez — anahtar, kayıt kalıcı olmadan dönerdi. Açık commit bağlantının bekleyen başka
    yazımlarını da kalıcı kılar; açılış kendi işleminde yapılmalı.
    """
    _check_opening(purpose=purpose, git_sha=git_sha, now=now)
    try:
        with conn.cursor() as cur:
            cur.execute(_INSERT_ACCESS, (now, git_sha, purpose))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return HoldoutKey(opened_at=now, purpose=purpose, git_sha=git_sha, _seal=_HOLDOUT_SEAL)


def _check_opening(*, purpose: str, git_sha: str, now: datetime) -> None:
    """Veritabanının CHECK'lerinden önce: geçersiz açılış hiçbir ifade yürütmeden reddedilir."""
    if not purpose.strip():
        raise ValueError("holdout açılışının amacı boş olamaz")
    # `fullmatch`: `re.match(r"^…$")` sondaki satır sonunu kabul ederdi.
    if not _GIT_SHA.fullmatch(git_sha):
        raise ValueError(f"git_sha 40 küçük harfli onaltılık karakter olmalı: {git_sha!r}")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("holdout açılış anı saat dilimli olmalı")


def select_periods(
    matches: Sequence[HistMatch], *, periods: frozenset[str], key: HoldoutKey | None = None
) -> tuple[HistMatch, ...]:
    """İstenen dönemlerin maçları, giriş sırasıyla. HOLDOUT geçerli bir anahtar ister."""
    unknown = periods - _PERIODS
    if unknown:
        raise ValueError(f"bilinmeyen dönem: {sorted(unknown)}")
    if HOLDOUT in periods and (key is None or key._seal is not _HOLDOUT_SEAL):
        raise HoldoutLocked("holdout istendi ama open_holdout'un kurduğu bir anahtar yok")
    return tuple(match for match in matches if period_of(match.date) in periods)
