from __future__ import annotations

import pytest

from football_edge.elo import EloConfig, expected_home, run, updated

CONFIG = EloConfig()
FLAT = EloConfig(home_advantage=0.0, goal_scaling=False)


def test_equal_ratings_with_no_home_advantage_expect_half() -> None:
    assert expected_home(1500.0, 1500.0, FLAT) == pytest.approx(0.5)


def test_home_advantage_raises_the_expectation() -> None:
    assert expected_home(1500.0, 1500.0, CONFIG) > 0.5


def test_stronger_team_expects_more() -> None:
    assert expected_home(1700.0, 1500.0, FLAT) > expected_home(1500.0, 1700.0, FLAT)


def test_rating_change_is_zero_sum() -> None:
    """Elo kapalı bir sistemdir: biri ne kazanırsa diğeri onu kaybeder.

    Sıfır toplam bozulursa lig ortalaması sürüklenir ve ligler arası ortak ölçek
    (Faz 3, task 3) anlamını yitirir.

    HEM `FLAT` HEM `CONFIG` altında sınanır: `home_advantage=0.0`'da (`FLAT`)
    `sigmoid(z) + sigmoid(-z) = 1` matematiksel bir RASTLANTIYLA sağlanır — bağımsız
    hesaplanmış iki beklenti (ör. `expected_home`e ters argümanla ikinci bir çağrı) bu
    özel durumda YİNE sıfır toplam verir ve testi yanıltır. `CONFIG`'in sıfır olmayan
    `home_advantage`'ı (üretim varsayılanı, Faz 2 de buna yakın bir değere fit edecek)
    bu rastlantıyı bozar; gerçek bir sızıntı yalnız orada görünür.
    """
    home, away = updated(1500.0, 1500.0, 2, 1, FLAT)
    assert (home - 1500.0) == pytest.approx(-(away - 1500.0))

    home_ha, away_ha = updated(1500.0, 1500.0, 2, 1, CONFIG)
    assert (home_ha - 1500.0) == pytest.approx(-(away_ha - 1500.0))


def test_draw_between_equals_changes_nothing() -> None:
    assert updated(1500.0, 1500.0, 1, 1, FLAT) == pytest.approx((1500.0, 1500.0))


def test_away_win_raises_the_away_rating_and_lowers_the_home_rating() -> None:
    """`_outcome`'un `home_goals < away_goals` dalını sınayan tek test.

    Diğer 11 testin hepsi ev sahibi galibiyeti ya da berabereyle çağırıyor; deplasman
    galibiyetini yalnız bu test doğrudan sınıyor.
    """
    home, away = updated(1500.0, 1500.0, 0, 1, FLAT)
    assert away > 1500.0
    assert home < 1500.0


def test_beating_a_stronger_team_gains_more_than_beating_a_weaker_one() -> None:
    underdog, _ = updated(1400.0, 1700.0, 1, 0, FLAT)
    favourite, _ = updated(1700.0, 1400.0, 1, 0, FLAT)
    assert (underdog - 1400.0) > (favourite - 1700.0)


def test_bigger_margin_moves_the_rating_more_when_goal_scaling_is_on() -> None:
    narrow, _ = updated(1500.0, 1500.0, 1, 0, CONFIG)
    wide, _ = updated(1500.0, 1500.0, 4, 0, CONFIG)
    assert wide > narrow


def test_margin_is_ignored_when_goal_scaling_is_off() -> None:
    narrow, _ = updated(1500.0, 1500.0, 1, 0, FLAT)
    wide, _ = updated(1500.0, 1500.0, 4, 0, FLAT)
    assert narrow == pytest.approx(wide)


def test_run_is_deterministic_and_order_sensitive() -> None:
    """Sıra ÖNEMLİDİR: Elo yol bağımlıdır. Testin bunu bilmesi, backtest'in de bilmesini sağlar."""
    forward = (("a", "b", 2, 0), ("b", "c", 1, 0))
    backward = (("b", "c", 1, 0), ("a", "b", 2, 0))
    assert run(forward, FLAT) == run(forward, FLAT)
    assert run(forward, FLAT) != run(backward, FLAT)


def test_run_seeds_unknown_teams_at_the_initial_rating() -> None:
    ratings = run((("a", "b", 1, 0),), FLAT)
    assert set(ratings) == {"a", "b"}
    assert sum(ratings.values()) == pytest.approx(2 * FLAT.initial)


def test_run_accepts_a_seed_and_does_not_mutate_it() -> None:
    """Faz 2'nin MIT veri setindeki ClubElo sütunu tohum olarak geçirilecek."""
    seed = {"a": 1800.0}
    ratings = run((("a", "b", 1, 0),), FLAT, seed=seed)
    assert seed == {"a": 1800.0}, "tohum sözlüğü mutasyona uğradı"
    assert ratings["a"] > 1800.0
