"""Donmuş harman ağırlığı (Faz 4 tasarımı §2 T0a, R161). Veri SENTETİK; veritabanı yok."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
import yaml

from football_edge.backtest.model_config import MODEL_CONFIG_PATH, file_sha256, load_model_config
from football_edge.backtest.records import MatchKey
from football_edge.backtest.walkforward import (
    BLEND_COMPONENTS,
    DC,
    ELO,
    EVALUATION,
    MARKET,
    SELECTION,
    Row,
)
from football_edge.backtest.wf_eval import LEAGUE_MIN_MATCHES, MARKET_ONLY, frozen_weights
from football_edge.history.catalog import MAIN
from football_edge.live import __main__ as live_cli
from football_edge.live.weights import (
    BlendWeights,
    BlendWeightsError,
    dump_blend_weights,
    freeze,
    load_blend_weights,
    weights_for,
)
from football_edge.model.pool import MIN_FIT_MATCHES

DIGESTS = {"model_config_sha256": "a" * 64, "lock_sha256": "b" * 64, "catalog_sha256": "c" * 64}


def _row(league: str, zone: str, outcome: int, index: int) -> Row:
    """Piyasa evi, Elo deplasmanı tutar: sonuç 0 piyasayı, 2 Elo'yu haklı çıkarır."""
    return Row(
        key=MatchKey(league, date(2021, 1, 1), f"Ev {index}", f"Konuk {index}"),
        kind=MAIN,
        zone=zone,
        season="2021",
        outcome=outcome,
        totals_outcome=0,
        components=MappingProxyType(
            {MARKET: (0.5, 0.3, 0.2), ELO: (0.2, 0.3, 0.5), DC: (0.34, 0.33, 0.33)}
        ),
        totals=MappingProxyType({}),
        pre=(2.0, 3.2, 4.5),
        closing=(0.48, 0.3, 0.22),
        totals_pre=None,
        totals_closing=None,
    )


def _rows(league: str, count: int, *, zone: str = EVALUATION, outcome: int = 0) -> list[Row]:
    return [_row(league, zone, (outcome if i % 3 else 1), i) for i in range(count)]


def test_a_league_with_enough_rows_keeps_its_own_weights_and_the_rest_pool() -> None:
    rows = [*_rows("E0", LEAGUE_MIN_MATCHES, outcome=2), *_rows("E1", MIN_FIT_MATCHES)]

    weights = freeze(rows, ["E0", "E1"], **DIGESTS)

    expected, _ = frozen_weights(rows, [("E0", "x"), ("E1", "x")])
    assert set(weights.leagues) == {"E0"}
    assert weights.leagues["E0"] == expected[("E0", "x")]
    assert weights.pooled == expected[("E1", "x")]
    assert weights.fallback == ("E1",)
    assert weights_for(weights, "E1") == weights.pooled
    assert weights.components == BLEND_COMPONENTS == (MARKET, ELO, DC)
    market, elo, _dc = weights.leagues["E0"]
    assert elo > market


def test_without_evaluation_rows_every_league_takes_the_market_alone() -> None:
    weights = freeze(_rows("E0", 50, zone=SELECTION), ["E0", "E1"], **DIGESTS)

    assert weights.pooled == MARKET_ONLY
    assert dict(weights.leagues) == {}
    assert weights.fallback == ("E0", "E1")


@pytest.mark.leakage
def test_holdout_and_post_rows_never_move_the_frozen_weights() -> None:
    """Holdout ve sonrası satırları Elo'yu haklı çıkarsa da ağırlık aynı kalır (R161)."""
    development = [*_rows("E0", LEAGUE_MIN_MATCHES), *_rows("E1", MIN_FIT_MATCHES)]
    later = [
        replace(row, key=replace(row.key, date=date(2026, 1, 1)))
        for zone in ("holdout", "post")
        for row in _rows("E0", 3000, zone=zone, outcome=2)
    ]

    alone = freeze(development, ["E0", "E1"], **DIGESTS)
    mixed = freeze([*development, *later], ["E0", "E1"], **DIGESTS)

    assert mixed == alone


@pytest.mark.leakage
def test_selection_rows_never_enter_the_frozen_weights() -> None:
    """Yalnız E: S satırları seçimin kendisidir, ağırlığın örneklemi değil."""
    evaluation = _rows("E0", LEAGUE_MIN_MATCHES)
    selection = _rows("E0", 2000, zone=SELECTION, outcome=2)

    assert freeze([*evaluation, *selection], ["E0"], **DIGESTS) == freeze(
        evaluation, ["E0"], **DIGESTS
    )


def test_the_weights_file_round_trips(tmp_path: Path) -> None:
    weights = freeze(
        [*_rows("E0", LEAGUE_MIN_MATCHES, outcome=2), *_rows("E1", MIN_FIT_MATCHES)],
        ["E0", "E1"],
        **DIGESTS,
    )
    path = tmp_path / "w.yaml"
    path.write_text(dump_blend_weights(weights), encoding="utf-8")

    assert load_blend_weights(path) == weights


def _payload() -> dict[str, Any]:
    return {
        "version": 1,
        **DIGESTS,
        "components": list(BLEND_COMPONENTS),
        "pooled": [1.0, 0.0, 0.0],
        "leagues": {"E0": [0.8, 0.1, 0.2]},
        "fallback": ["E1"],
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda p: p.pop("fallback"), "üst alanlar"),
        (lambda p: p.update(extra=1), "üst alanlar"),
        (lambda p: p.update(version=2), "sürüm"),
        (lambda p: p.update(components=[MARKET, DC, ELO]), "bileşenler"),
        (lambda p: p.update(pooled=[1.0, 0.0]), "pooled"),
        (lambda p: p.update(pooled=[1.0, -0.1, 0.0]), "≥ 0"),
        (lambda p: p.update(pooled=[1.0, float("nan"), 0.0]), "sonlu"),
        (lambda p: p.update(leagues={"E0": ["x", 0.0, 0.0]}), "sayı"),
        (lambda p: p.update(fallback=["E0"]), "hem kendi"),
        (lambda p: p.update(lock_sha256="B" * 64), "sha256"),
    ],
)
def test_a_malformed_weights_file_is_refused_by_name(
    tmp_path: Path, change: Any, message: str
) -> None:
    payload = _payload()
    change(payload)
    path = tmp_path / "w.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(BlendWeightsError, match=message):
        load_blend_weights(path)


def test_a_missing_weights_file_is_a_named_error(tmp_path: Path) -> None:
    with pytest.raises(BlendWeightsError, match="okunamadı"):
        load_blend_weights(tmp_path / "yok.yaml")


def test_blend_weights_are_frozen_values() -> None:
    weights = BlendWeights("a" * 64, "b" * 64, "c" * 64, BLEND_COMPONENTS, MARKET_ONLY, {}, ())

    with pytest.raises(AttributeError):
        weights.pooled = (0.0, 1.0, 0.0)  # type: ignore[misc]


class _Conn:
    def __enter__(self) -> _Conn:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_freeze_weights_writes_the_digests_of_the_files_it_was_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI: anahtarsız `load_matches` (holdout döndürmez) → walk-forward DEV satırları → dosya."""
    seen: dict[str, Any] = {}

    def load_matches(conn: object, catalog: object, **kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(live_cli, "connect", _Conn)
    monkeypatch.setattr(live_cli, "load_matches", load_matches)
    out = tmp_path / "w.yaml"

    assert live_cli.main(["freeze-weights", "--out", str(out)]) == 0

    weights = load_blend_weights(out)
    config = load_model_config(MODEL_CONFIG_PATH)
    assert "key" not in seen and seen["lock"] is not None
    assert weights.model_config_sha256 == file_sha256(MODEL_CONFIG_PATH)
    assert (weights.lock_sha256, weights.catalog_sha256) == (
        config.lock_sha256,
        config.catalog_sha256,
    )
    assert weights.pooled == MARKET_ONLY and dict(weights.leagues) == {}
    assert weights.fallback  # boş tabanda her ana lig havuza düşer


def test_freeze_weights_refuses_a_config_whose_digests_do_not_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "model.yaml"
    config.write_text(
        MODEL_CONFIG_PATH.read_text(encoding="utf-8").replace("lock_sha256: ", "lock_sha256: 0"),
        encoding="utf-8",
    )
    monkeypatch.setattr(live_cli, "connect", _Conn)
    out = tmp_path / "w.yaml"

    code = live_cli.main(["freeze-weights", "--config", str(config), "--out", str(out)])

    assert code == live_cli.EXIT_CONFIG_MISMATCH
    assert not out.exists()


def test_a_digit_only_digest_survives_the_round_trip_and_an_unquoted_one_is_refused(
    tmp_path: Path,
) -> None:
    """Review Focus: YAML tırnaksız yalnız-rakam bir özeti tamsayı okur — elle düzenlenen dosyada
    `str()` onu sessizce kabul ederdi; yazıcı tırnaklar, okuyucu tipi de denetler."""
    digits = "1234567890" * 6 + "1234"
    weights = freeze(
        (), ["E0"], model_config_sha256=digits, lock_sha256="b" * 64, catalog_sha256="c" * 64
    )
    path = tmp_path / "w.yaml"
    path.write_text(dump_blend_weights(weights), encoding="utf-8")

    assert load_blend_weights(path).model_config_sha256 == digits
    path.write_text(
        path.read_text(encoding="utf-8").replace(f"'{digits}'", digits), encoding="utf-8"
    )
    with pytest.raises(BlendWeightsError, match="model_config_sha256"):
        load_blend_weights(path)


@pytest.mark.parametrize("league", ["E1", "BRA", ""])
def test_a_league_without_its_own_weights_takes_the_pooled_ones(league: str) -> None:
    """Review Focus: havuza düşen, katalogda ek lig olan ya da hiç bilinmeyen kod — hepsi havuz;
    KeyError ya da başka ligin ağırlığı değil."""
    weights = freeze(
        [*_rows("E0", LEAGUE_MIN_MATCHES, outcome=2), *_rows("E1", MIN_FIT_MATCHES)],
        ["E0", "E1"],
        **DIGESTS,
    )

    assert weights_for(weights, league) == weights.pooled != weights.leagues["E0"]


def test_shadow_refuses_a_lock_whose_digest_does_not_match_before_touching_the_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`shadow` de `_frozen_config`ten geçer: kilit özeti uyuşmazsa exit 11, tabana gidilmez."""
    lock = tmp_path / "lock.yaml"
    lock.write_text(live_cli.LOCK_PATH.read_text(encoding="utf-8") + "\n# fark\n", encoding="utf-8")

    def connect() -> None:
        raise AssertionError("uyuşmazlıkta tabana bağlanılmaz")

    monkeypatch.setattr(live_cli, "connect", connect)

    assert live_cli.main(["shadow", "--lock", str(lock)]) == live_cli.EXIT_CONFIG_MISMATCH
