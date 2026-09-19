from __future__ import annotations

import math
from dataclasses import dataclass

_SCALE = 400.0


@dataclass(frozen=True)
class EloConfig:
    """Elo parametreleri.

    Değerler BAŞLANGIÇ değeridir, gerçek değil: `k` ve `home_advantage` Faz 2'de tarihsel
    veri üzerinde FIT EDİLİR. Spec §4/3'ün kuralı burada da geçerli — uydurulmuş katsayı
    modelin yanlış olduğunu gizler. Bu sayılar yalnız fit edilene kadar duran iskelelerdir.
    """

    k: float = 20.0
    home_advantage: float = 65.0
    initial: float = 1500.0
    goal_scaling: bool = True


def expected_home(home_rating: float, away_rating: float, config: EloConfig) -> float:
    difference = (home_rating + config.home_advantage) - away_rating
    # `math.pow` yerine `**` kullanılırsa mypy --strict "Returning Any" ile kırılır:
    # `float.__pow__` negatif taban + kesirli üs için `complex` dönebildiğinden typeshed
    # dönüş tipini `Any` işaretler. `math.pow` imzası `(float, float) -> float` sabittir.
    return 1.0 / (1.0 + math.pow(10.0, -difference / _SCALE))


def _outcome(home_goals: int, away_goals: int) -> float:
    if home_goals > away_goals:
        return 1.0
    return 0.0 if home_goals < away_goals else 0.5


def _margin_multiplier(home_goals: int, away_goals: int, config: EloConfig) -> float:
    """Gol farkı çarpanı. Kapalıyken 1.0 — sıfır toplam her iki hâlde de korunur."""
    if not config.goal_scaling:
        return 1.0
    margin = abs(home_goals - away_goals)
    return 1.0 if margin <= 1 else (1.0 + (margin - 1) * 0.5)


def updated(
    home_rating: float,
    away_rating: float,
    home_goals: int,
    away_goals: int,
    config: EloConfig,
) -> tuple[float, float]:
    """Tek maçın ardından yeni reytingler. Değişim SIFIR TOPLAMDIR.

    Tek bir `change` hesaplanıp birine eklenip diğerinden çıkarılır; iki ayrı beklenti
    hesaplamak kayan nokta hatasıyla sızıntı yaratır ve lig ortalaması yıllar içinde
    sürüklenir.
    """
    expected = expected_home(home_rating, away_rating, config)
    actual = _outcome(home_goals, away_goals)
    change = config.k * _margin_multiplier(home_goals, away_goals, config) * (actual - expected)
    return home_rating + change, away_rating - change


def run(
    results: tuple[tuple[str, str, int, int], ...],
    config: EloConfig,
    *,
    seed: dict[str, float] | None = None,
) -> dict[str, float]:
    """Maçları SIRAYLA işler ve nihai reytingleri döner.

    SIRA yük taşır: Elo yol bağımlıdır. Çağıran maçları `commence_time`e göre sıralamak
    zorundadır — sıralanmamış bir dizi sessizce başka bir sayı üretir ve hiçbir şey
    kırmızı vermez.

    `seed` MUTASYONA UĞRAMAZ; kopyalanır (Faz 2'nin MIT ClubElo sütunu buraya geçirilecek).
    """
    ratings = dict(seed or {})
    for home, away, home_goals, away_goals in results:
        home_rating = ratings.get(home, config.initial)
        away_rating = ratings.get(away, config.initial)
        new_home, new_away = updated(home_rating, away_rating, home_goals, away_goals, config)
        ratings = {**ratings, home: new_home, away: new_away}
    return ratings
