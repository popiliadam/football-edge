"""Modelin bilinen sonuçları W1–W4 (Faz 3 tasarımı §9 G4): her kapı kırmızı verebiliyor."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from types import MappingProxyType
from typing import Any

import numpy as np
import pytest

from football_edge.backtest import model_selftest
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.model_selftest import model_checks, model_rows, w1_passes
from football_edge.backtest.records import MatchKey
from football_edge.backtest.walkforward import DC, ELO, ELO_SCAFFOLD, MARKET, Row
from football_edge.backtest.wf_run import development_groups
from football_edge.history.catalog import MAIN
from football_edge.market.devig import POWER
from football_edge.market.metrics import CalibrationUnfit, Interval, bootstrap_mean
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModelConfig
from tests.model_builders import main_history

GROUPS = MappingProxyType({"E0": "Ülke"})
KINDS = MappingProxyType({"E0": MAIN})
CONFIG = ModelConfig(
    "x", "c", "l", POWER, EloModelConfig(draw=0.28), DCConfig(min_matches=40), 7, 0.02, ()
)


@pytest.fixture(scope="module")
def rows() -> tuple[Row, ...]:
    groups = development_groups({"E0": main_history(2011, 2022)}, GROUPS)
    return model_rows(groups, KINDS, GROUPS, CONFIG)


def _checks(rows: tuple[Row, ...]) -> dict[str, object]:
    return {check.id: check for check in model_checks(rows, resamples=50)}


def test_honest_model_rows_pass_w2_and_w3_and_report_w4(rows: tuple[Row, ...]) -> None:
    checks = _checks(rows)

    assert [check.id for check in checks.values()] == ["W1", "W2", "W3", "W4"]  # type: ignore[attr-defined]
    assert checks["W2"].passed and checks["W3"].passed  # type: ignore[attr-defined]
    assert [check.gate for check in checks.values()] == [True, True, True, False]  # type: ignore[attr-defined]


def _market_table(market_right: bool, count: int = 3000) -> tuple[Row, ...]:
    """İki sezon S + iki sezon E. Doğruysa piyasa gerçek dağılımı verir, modeller düz; değilse
    S'de modeller sonucu bilir, piyasa yanıltır — E'de piyasa bilir, modeller düz."""
    rng = np.random.default_rng(7)
    found: list[Row] = []
    for position, (season, zone) in enumerate(
        (("1718", "S"), ("1819", "S"), ("1920", "E"), ("2021", "E"))
    ):
        for index in range(count):
            outcome = int(rng.choice(3, p=(0.6, 0.25, 0.15)))
            knows = tuple(0.9 if i == outcome else 0.05 for i in range(3))
            misleads = tuple(0.05 if i == outcome else 0.475 for i in range(3))
            flat = (1 / 3, 1 / 3, 1 / 3)
            if market_right:
                market, model = (0.6, 0.25, 0.15), flat
            elif zone == "E":
                market, model = knows, flat
            else:
                market, model = misleads, knows
            found.append(
                Row(
                    key=MatchKey("E0", date(2020, 1, 1), f"Ev {position}-{index}", "Konuk"),
                    kind=MAIN,
                    zone=zone,
                    season=season,
                    outcome=outcome,
                    totals_outcome=0,
                    components=MappingProxyType({MARKET: market, ELO: model, DC: model}),
                    totals=MappingProxyType({}),
                    pre=None,
                    closing=None,
                    totals_pre=None,
                    totals_closing=None,
                )
            )
    return tuple(found)


_FIVE_DECIMALS = re.compile(r"-?\d+\.\d{5} \[%95 -?\d+\.\d{5}, -?\d+\.\d{5}\]")


def test_w1_and_w2_report_their_interval_with_five_decimals(rows: tuple[Row, ...]) -> None:
    """Rapor metni `interval_text(digits=5, label="%95 ")` ile basılır (DEFERRED 16j birleştirmesi):
    basamak ya da etiket kayarsa kapı değil ama operatörün okuduğu satır değişir."""
    w1 = _checks(_market_table(market_right=True))["W1"].detail  # type: ignore[attr-defined]
    w2 = _checks(rows)["W2"].detail  # type: ignore[attr-defined]

    assert _FIVE_DECIMALS.search(w1), w1
    assert _FIVE_DECIMALS.search(w2), w2


def test_w1_passes_when_the_fitted_blend_keeps_the_market() -> None:
    assert _checks(_market_table(market_right=True))["W1"].passed is True  # type: ignore[attr-defined]


def test_w1_fails_when_weights_learnt_earlier_hurt_later() -> None:
    """İlk E katı S'den modellere ağırlık verdi; E'de modeller düz, piyasa doğru → harman
    piyasadan çok kötü (bozuk bir ağırlık fitinin ya da kayan bir hattın imzası)."""
    assert _checks(_market_table(market_right=False))["W1"].passed is False  # type: ignore[attr-defined]


def _swap(
    rows: tuple[Row, ...], name: str, probs: tuple[float, ...] | None = None
) -> tuple[Row, ...]:
    """E satırlarında bir bileşeni bozar: gerçek sonuca en düşük olasılığı verir."""

    def broken(row: Row) -> Row:
        wrong = tuple(0.05 if index == row.outcome else 0.475 for index in range(3))
        return replace(row, components=MappingProxyType({**row.components, name: probs or wrong}))

    return tuple(broken(row) if row.zone == "E" else row for row in rows)


@pytest.mark.parametrize(("name", "check"), [(ELO, "W2"), (DC, "W3")])
def test_a_broken_model_turns_its_gate_red(rows: tuple[Row, ...], name: str, check: str) -> None:
    assert _checks(_swap(rows, name))[check].passed is False  # type: ignore[attr-defined]


def test_without_rows_every_gate_is_unmeasured_and_red() -> None:
    checks = _checks(())

    assert all("ölçülemedi" in c.detail and not c.passed for c in checks.values())  # type: ignore[attr-defined]
    assert [c.gate for c in checks.values()] == [True, True, True, False]  # type: ignore[attr-defined]


def _rate_row(zone: str, outcome: int, index: int) -> Row:
    dc = (0.25, 0.3, 0.45)
    return Row(
        key=MatchKey("E0", date(2020, 1, 1), f"Ev {zone}-{index}", "Konuk"),
        kind=MAIN,
        zone=zone,
        season="1718" if zone == "S" else "1920",
        outcome=outcome,
        totals_outcome=0,
        components=MappingProxyType({DC: dc}),
        totals=MappingProxyType({}),
        pre=None,
        closing=None,
        totals_pre=None,
        totals_closing=None,
    )


def test_w3_compares_against_the_outcome_rates_of_s_not_of_e() -> None:
    """S oranları (0.6, 0.25, 0.15), E oranları (0.2, 0.3, 0.5); DC (0.25, 0.3, 0.45) E'nin kendi
    oranlarından kötü, S'ninkinden iyi. Taban E'den alınsaydı W3 kalırdı (sızıntılı bir taban)."""
    s = [0] * 60 + [1] * 25 + [2] * 15
    e = [0] * 20 + [1] * 30 + [2] * 50
    rows = tuple(_rate_row("S", o, i) for i, o in enumerate(s)) + tuple(
        _rate_row("E", o, i) for i, o in enumerate(e)
    )

    w3 = _checks(rows)["W3"]

    assert w3.passed is True, w3.detail  # type: ignore[attr-defined]


def test_the_scaffold_elo_is_in_the_rows(rows: tuple[Row, ...]) -> None:
    assert any(ELO_SCAFFOLD in row.components for row in rows if row.zone == "E")


@pytest.mark.parametrize(
    ("estimate", "low", "high", "passes"),
    [
        (0.0005, -0.0010, 0.0020, False),  # nokta tahmini < δ ama üst uç > δ → KALIR (R143)
        (0.0005, -0.0005, 0.0009, True),
        (-0.0030, -0.0050, 0.0010, True),  # üst uç tam δ: geçer
        (0.0020, 0.0015, 0.0030, False),
    ],
)
def test_w1_is_a_non_inferiority_test_on_the_upper_bound(
    estimate: float, low: float, high: float, passes: bool
) -> None:
    assert w1_passes(Interval(estimate, low, high)) is passes


def test_w1_uses_the_phase_two_bootstrap_settings() -> None:
    """R143: yeniden örnekleme birimi, tohum, düzey ve B Faz 2 verimlilik raporlarıyla aynı."""
    from football_edge.backtest.evaluate import DEFAULT_RESAMPLES
    from football_edge.market import efficiency

    assert (efficiency.RESAMPLES, efficiency.SEED, efficiency.LEVEL) == (
        DEFAULT_RESAMPLES,
        20260922,
        0.95,
    )
    assert bootstrap_mean.__kwdefaults__ == {"resamples": 2000, "seed": 20260922, "level": 0.95}


def _raising(error: Exception) -> Any:
    def fit(*_a: object, **_k: object) -> Any:
        raise error

    return fit


def test_w4_reports_only_an_unfit_calibration_as_unmeasured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tekil fit "ölçülemedi"dir, koşu sürer (R135 deseni; son inceleme M-7)."""
    monkeypatch.setattr(model_selftest, "calibration", _raising(CalibrationUnfit("fit tekil")))

    w4 = _checks(_market_table(market_right=True))["W4"]

    assert (w4.passed, w4.detail) == (False, "W4 ölçülemedi: fit tekil")  # type: ignore[attr-defined]


def test_w4_raises_a_shape_error_instead_of_reporting_it_as_unmeasured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bileşen hatası "ölçülemedi" basılırsa hata raporda kaybolur (son inceleme M-7)."""
    monkeypatch.setattr(model_selftest, "calibration", _raising(ValueError("sayısı farklı")))

    with pytest.raises(ValueError, match="sayısı farklı"):
        _checks(_market_table(market_right=True))
