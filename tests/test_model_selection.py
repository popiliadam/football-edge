"""Seçim (S bölgesi), model yapılandırması ve `select`/`walkforward` CLI tutkalı (Faz 3 §5.2)."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType

import pytest

from football_edge.backtest import __main__ as cli
from football_edge.backtest.model_config import (
    ModelConfig,
    ModelConfigError,
    dump_model_config,
    file_sha256,
    load_model_config,
)
from football_edge.backtest.selection import coordinate_descent, dc_loss, elo_loss, select
from football_edge.backtest.selftest import Check
from football_edge.backtest.walkforward import DC, ELO, SELECTION, group_rows
from football_edge.backtest.wf_eval import summarise
from football_edge.backtest.wf_run import (
    development_groups,
    gap_penalty,
    render_walkforward,
    rows_digest,
    run_rows,
)
from football_edge.history.catalog import MAIN, Catalog, HistoryLeague
from football_edge.history.lock import build_lock, dump_lock
from football_edge.market.devig import POWER
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import (
    ORDERED,
    QUADRATIC,
    EloModel,
    EloModelConfig,
    expectation,
    fit_ordered,
    ordered_probs,
)
from tests.model_builders import TEAMS, main_history

KINDS = MappingProxyType({"E0": MAIN})
GROUPS = MappingProxyType({"E0": "Ülke"})
HISTORY = {"E0": main_history(2011, 2020)}
CATALOG = Catalog(
    current_season="2627",
    leagues=(HistoryLeague("E0", "test.1", "Test", "Ülke", 1, MAIN, "1112", ""),),
)


@dataclass(frozen=True)
class Point:
    x: float = 0.0
    y: float = 0.0


def test_coordinate_descent_tries_each_parameter_once_in_order() -> None:
    grid = {"x": (-1.0, 2.0, 3.0), "y": (5.0, 1.0)}

    best, trace = coordinate_descent(Point(), grid, lambda p: (p.x - 2.0) ** 2 + (p.y - 1.0) ** 2)

    assert best == Point(2.0, 1.0)
    assert [dict(params) for params, _ in trace] == [
        {"x": 0.0, "y": 0.0},
        {"x": -1.0, "y": 0.0},
        {"x": 2.0, "y": 0.0},
        {"x": 3.0, "y": 0.0},
        {"x": 2.0, "y": 5.0},
        {"x": 2.0, "y": 1.0},
    ]


def test_coordinate_descent_keeps_the_first_of_equal_losses() -> None:
    best, _ = coordinate_descent(Point(), {"x": (1.0, 2.0)}, lambda p: 0.0)

    assert best == Point()


@pytest.mark.leakage
@pytest.mark.parametrize("form", [QUADRATIC, ORDERED])
def test_selection_losses_read_only_the_selection_zone(form: str) -> None:
    """S bölgesinin sonuçları değişince kayıp değişir; E bölgesininkiler değişince DEĞİŞMEZ — iki
    beraberlik biçiminde de (R142: biçimin parametreleri de yalnız S'de fit edilir)."""
    groups = development_groups(HISTORY, GROUPS)
    config = EloModelConfig(draw_form=form)
    base = elo_loss(groups, KINDS, GROUPS, config, method=POWER)
    late = {
        "E0": tuple(
            replace(
                m,
                home_goals=m.away_goals,
                away_goals=m.home_goals,
                result={"H": "A", "A": "H", "D": "D"}[m.result],
            )
            if m.date >= date(2019, 7, 1)
            else m
            for m in HISTORY["E0"]
        )
    }

    assert elo_loss(development_groups(late, GROUPS), KINDS, GROUPS, config, method=POWER) == base


def test_selection_losses_are_finite_and_the_draw_is_fitted() -> None:
    groups = development_groups(HISTORY, GROUPS)

    loss, fitted = elo_loss(groups, KINDS, GROUPS, EloModelConfig(), method=POWER)
    ordered_loss, ordered = elo_loss(
        groups, KINDS, GROUPS, EloModelConfig(draw_form=ORDERED), method=POWER
    )
    dc = dc_loss(groups, KINDS, GROUPS, DCConfig(min_matches=40), cadence_days=7, method=POWER)

    assert 0.5 < loss < 1.2 and 0.0 <= fitted.draw <= 0.5
    assert 0.5 < ordered_loss < 1.2 and ordered.draw_form == ORDERED
    assert ordered.ordered_cut != EloModelConfig().ordered_cut
    assert 0.5 < dc < 1.2


def test_the_draw_form_is_chosen_on_s_and_only_the_winner_is_returned_fitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R142: biçim kategorik hiperparametre; `select` kazananı S'de fit edilmiş hâliyle döner."""
    monkeypatch.setattr(
        "football_edge.backtest.selection.ELO_GRID", {"draw_form": (QUADRATIC, ORDERED)}
    )
    monkeypatch.setattr("football_edge.backtest.selection.DC_GRID", {"xi": (0.0019,)})
    groups = development_groups(HISTORY, GROUPS)
    losses = {
        form: elo_loss(groups, KINDS, GROUPS, EloModelConfig(draw_form=form), method=POWER)
        for form in (QUADRATIC, ORDERED)
    }

    elo, _, trials = select(groups, KINDS, GROUPS, cadence_days=7, method=POWER)

    winner = min(losses, key=lambda form: losses[form][0])
    assert elo == losses[winner][1]
    assert {trial.params["draw_form"] for trial in trials if trial.model == "elo"} == {
        QUADRATIC,
        ORDERED,
    }


def _config(tmp: Path) -> ModelConfig:
    return ModelConfig(
        selected_at="2026-10-01",
        catalog_sha256=file_sha256(tmp / "catalog.yaml"),
        lock_sha256=file_sha256(tmp / "lock.yaml"),
        method=POWER,
        elo=EloModelConfig(k=25.0, draw=0.28),
        dixon_coles=DCConfig(xi=0.001, min_matches=40),
        cadence_days=7,
        tau=0.02,
        sensitivity=(0.0, 0.05),
    )


def _files(tmp: Path) -> None:
    (tmp / "catalog.yaml").write_text("katalog\n", encoding="utf-8")
    (tmp / "lock.yaml").write_text(
        dump_lock(build_lock({}, locked_at=date(2026, 9, 22))), encoding="utf-8"
    )


def test_the_model_config_round_trips(tmp_path: Path) -> None:
    _files(tmp_path)
    path = tmp_path / "model.yaml"
    path.write_text(dump_model_config(_config(tmp_path)), encoding="utf-8")

    assert load_model_config(path) == _config(tmp_path)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda text: text.replace("version: 1", "version: 2"),
        lambda text: text.replace("method: power", "method: guess"),
        lambda text: text.replace("  k: 25.0\n", ""),
        lambda text: text.replace("margin: linear", "margin: square"),
        lambda text: text + "extra: 1\n",
        lambda text: "[",
    ],
    ids=["version", "method", "missing-field", "invalid-value", "extra-field", "broken-yaml"],
)
def test_a_bad_model_config_is_refused(tmp_path: Path, corrupt: object) -> None:
    _files(tmp_path)
    path = tmp_path / "model.yaml"
    path.write_text(corrupt(dump_model_config(_config(tmp_path))), encoding="utf-8")  # type: ignore[operator]

    with pytest.raises(ModelConfigError):
        load_model_config(path)


def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_catalog", lambda path: CATALOG)
    monkeypatch.setattr(cli, "connect", lambda: _Connection())
    monkeypatch.setattr(cli, "load_matches", lambda conn, catalog, *, lock=None, key=None: HISTORY)


class _Connection:
    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


@pytest.mark.leakage
def test_walkforward_refuses_a_changed_catalog_or_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _files(tmp_path)
    _patch(monkeypatch)
    config = tmp_path / "model.yaml"
    config.write_text(dump_model_config(_config(tmp_path)), encoding="utf-8")
    (tmp_path / "catalog.yaml").write_text("değişti\n", encoding="utf-8")

    code = cli.main(
        [
            "walkforward",
            "--config",
            str(config),
            "--catalog",
            str(tmp_path / "catalog.yaml"),
            "--lock",
            str(tmp_path / "lock.yaml"),
            "--out",
            str(tmp_path / "r.md"),
        ]
    )

    assert code == cli.EXIT_CONFIG_MISMATCH == 11
    assert not (tmp_path / "r.md").exists()
    assert any("katalog değişti" in message for message in caplog.messages)


def test_walkforward_writes_an_aggregate_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _files(tmp_path)
    _patch(monkeypatch)
    config = tmp_path / "model.yaml"
    config.write_text(dump_model_config(_config(tmp_path)), encoding="utf-8")

    code = cli.main(
        [
            "walkforward",
            "--config",
            str(config),
            "--catalog",
            str(tmp_path / "catalog.yaml"),
            "--lock",
            str(tmp_path / "lock.yaml"),
            "--out",
            str(tmp_path / "r.md"),
            "--resamples",
            "20",
        ]
    )

    report = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert code == 0
    assert "ΔLL harman − piyasa" in report and "holdout ve sonrası dönemi okunmadı" in report
    assert "Ortak kümeye girmeyen ana lig maçı (nedene göre): kickoff_before_decision" in report
    assert "Vig'i temizlenemeyen fiyat kümesi (Σ 1/o < 1 dahil): 1x2/pre 0" in report
    assert re.search(r"satır özeti sha256 `[0-9a-f]{64}`", report), "rapor tahmin özetini taşımıyor"
    assert not any(team in report for team in TEAMS)


MODEL_GREEN = (
    Check("W1", True, True, "w1 ayrıntı"),
    Check("W2", True, True, "w2 ayrıntı"),
    Check("W3", True, True, "w3 ayrıntı"),
)


@pytest.mark.parametrize(
    ("checks", "expected", "named"),
    [
        (MODEL_GREEN, 0, None),
        ((*MODEL_GREEN, Check("W4", False, False, "w4 ayrıntı")), 0, None),
        ((Check("W1", True, False, "w1 kaldı"), *MODEL_GREEN[1:]), cli.EXIT_GATE_FAILED, "W1"),
        ((*MODEL_GREEN[:2], Check("W3", True, False, "w3 kaldı")), cli.EXIT_GATE_FAILED, "W3"),
    ],
    ids=["hepsi-gecti", "rapor-kaldi", "w1-kapi-kaldi", "w3-kapi-kaldi"],
)
def test_model_selftest_exits_one_only_for_a_red_gate_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    checks: tuple[Check, ...],
    expected: int,
    named: str | None,
) -> None:
    """Kırmızı bir W1–W3 exit 1 vermezse history.yml'nin alarmı hiç açılmaz (R155/I1)."""
    _files(tmp_path)
    _patch(monkeypatch)
    seen: list[int] = []

    def fake_checks(rows: tuple[object, ...], *, resamples: int) -> tuple[Check, ...]:
        seen.append(resamples)
        return checks

    monkeypatch.setattr(cli, "model_checks", fake_checks)
    caplog.set_level(logging.INFO)
    config = tmp_path / "model.yaml"
    config.write_text(dump_model_config(_config(tmp_path)), encoding="utf-8")

    code = cli.main(
        [
            "model-selftest",
            "--config",
            str(config),
            "--catalog",
            str(tmp_path / "catalog.yaml"),
            "--lock",
            str(tmp_path / "lock.yaml"),
            "--resamples",
            "20",
        ]
    )

    assert code == expected
    assert seen == [20]
    if named is None:
        assert not any(m.startswith("kırmızı model denetimi") for m in caplog.messages)
    else:
        assert f"kırmızı model denetimi: {named}" in caplog.messages


def test_select_writes_a_loadable_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _files(tmp_path)
    _patch(monkeypatch)
    small = {"k": (20.0, 30.0)}
    monkeypatch.setattr("football_edge.backtest.selection.ELO_GRID", small)
    monkeypatch.setattr("football_edge.backtest.selection.DC_GRID", {"xi": (0.0019,)})
    caplog.set_level(logging.INFO)
    out = tmp_path / "model.yaml"

    code = cli.main(
        [
            "select",
            "--catalog",
            str(tmp_path / "catalog.yaml"),
            "--lock",
            str(tmp_path / "lock.yaml"),
            "--out",
            str(out),
            "--cadence-days",
            "7",
        ]
    )

    config = load_model_config(out)
    assert code == 0
    assert config.cadence_days == 7 and config.tau == 0.02
    assert config.lock_sha256 == file_sha256(tmp_path / "lock.yaml")
    assert sum("aday elo" in message for message in caplog.messages) == 2


def test_the_report_renderer_names_unmeasured_sections(tmp_path: Path) -> None:
    _files(tmp_path)
    rows = run_rows(development_groups(HISTORY, GROUPS), KINDS, GROUPS, _config(tmp_path))
    summary = summarise(rows, tau=0.02, sensitivity=(0.0,), resamples=20)

    text = render_walkforward(
        summary,
        _config(tmp_path),
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
        config_sha256="0" * 64,
    )

    assert "Ek ligler" in text and "ölçülemedi: satır yok" in text


def test_the_gap_penalty_rescores_the_same_matches_without_the_skipped_season(
    tmp_path: Path,
) -> None:
    """R128: 2022/23 girdiden çıkınca 2023/24'ün AYNI maçları başka olasılık alır; fark ölçülür."""
    _files(tmp_path)
    groups = development_groups({"E0": main_history(2019, 2023)}, GROUPS)

    gap = gap_penalty(groups, KINDS, GROUPS, _config(tmp_path), resamples=20)

    assert set(gap) == {ELO, DC}
    assert gap[ELO].estimate != 0.0 and gap[DC].estimate != 0.0
    text = render_walkforward(
        summarise(
            run_rows(groups, KINDS, GROUPS, _config(tmp_path)),
            tau=0.02,
            sensitivity=(),
            resamples=20,
        ),
        _config(tmp_path),
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
        config_sha256="0" * 64,
        gap=gap,
    )
    assert "Boşluk cezası (R128" in text


def test_the_rows_digest_is_stable_and_sees_a_changed_probability(tmp_path: Path) -> None:
    """m8 (tasarım §5.3): aynı satırlar → aynı özet; tek olasılık değişirse özet değişir."""
    _files(tmp_path)
    rows = run_rows(development_groups(HISTORY, GROUPS), KINDS, GROUPS, _config(tmp_path))
    first = rows[-1]
    changed = replace(
        first, components=MappingProxyType({**first.components, ELO: (0.5, 0.25, 0.25)})
    )

    assert rows_digest(rows) == rows_digest(tuple(reversed(rows)))
    assert rows_digest((*rows[:-1], changed)) != rows_digest(rows)


def test_an_ordered_candidate_is_scored_on_the_quadratic_replays_expectations() -> None:
    """R147 (yeniden inceleme N1a): `elo_loss` ORDERED adayı için bağımsız hesapla aynı —
    quadratic oynatma → E'yi geri oku → sıralı lojiti fit et → puanla. Aday kendi biçimiyle
    oynatılsaydı `expectation` yanlış E okurdu."""
    groups = development_groups(HISTORY, GROUPS)
    candidate = EloModelConfig(draw_form=ORDERED, k=25.0)
    rows = [
        row
        for matches in groups.values()
        for row in group_rows(
            matches,
            KINDS,
            {ELO: EloModel(config=replace(candidate, draw_form=QUADRATIC), groups=GROUPS)},
            method=POWER,
        )
        if row.zone == SELECTION and ELO in row.components
    ]
    expectations = [expectation(row.components[ELO]) for row in rows]
    outcomes = [row.outcome for row in rows]
    scale, cut = fit_ordered(expectations, outcomes)
    independent = -sum(
        math.log(ordered_probs(e, scale, cut)[o])
        for e, o in zip(expectations, outcomes, strict=True)
    ) / len(rows)

    loss, fitted = elo_loss(groups, KINDS, GROUPS, candidate, method=POWER)

    assert loss == pytest.approx(independent, rel=1e-9)
    assert (fitted.ordered_scale, fitted.ordered_cut) == pytest.approx((scale, cut))


def test_the_production_selection_grid_offers_both_draw_forms() -> None:
    """R142 (yeniden inceleme N1b): üretim ızgarası iki biçimi de sunar; biri düşerse S seçemez."""
    from football_edge.backtest.selection import ELO_GRID

    assert set(ELO_GRID["draw_form"]) == {QUADRATIC, ORDERED}
