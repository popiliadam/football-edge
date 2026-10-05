"""Faz 4 canlı ayağın ön kaydı (Plan 3 spec §4; R188–R199): `config/faz4_preregistration.yaml`.

İki katman. (1) Yükleyici şemayı birebir ister: eksik/fazla alan, yanlış tür ve desteklenmeyen
yöntem adı adıyla reddedilir — değerlendirme kodu yalnız ön kaydın adlandırdığı yöntemi uygular.
(2) Mühür denetimi (`gate4.seal`) dosyayı depoyla karşılaştırır: kalıcı denetim donmuş dosyaları,
küme sürümünü, bileşiğin `tier2`yi tam bölmesini, D8 listesini, kod sabitlerini, D5/dil kümesini
sorar ve her push'ta koşar; mühür anı denetimi kollar dâhil her dosyanın birebirliğini sorar.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from football_edge.gate4.preregistration import (
    COMPARISONS,
    COUNTS_PRINTED,
    FROZEN_FILES,
    PREREGISTRATION_PATH,
    RECORDED_FILES,
    PreregistrationError,
    load_preregistration,
)
from football_edge.gate4.seal import seal_time_violations, seal_violations

REPO = Path(__file__).resolve().parent.parent
REAL = REPO / PREREGISTRATION_PATH
CONFIGS = (
    "model_faz3.yaml",
    "blend_weights_faz3.yaml",
    "history_lock.yaml",
    "history_leagues.yaml",
    "history_aliases.yaml",
    "faz4_live.yaml",
    "faz4_ops.yaml",
    "jev_questions.yaml",
    "languages.yaml",
    "leagues.yaml",
)


def _raw() -> dict[str, Any]:
    loaded = yaml.safe_load(REAL.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _write(tmp_path: Path, raw: dict[str, Any]) -> Path:
    path = tmp_path / "prereg.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _repo_copy(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    for name in CONFIGS:
        shutil.copyfile(REPO / "config" / name, root / "config" / name)
    shutil.copyfile(REAL, root / PREREGISTRATION_PATH)
    return root


# ── Gerçek dosya ────────────────────────────────────────────────────────────────────────────


def test_real_preregistration_loads_and_is_sealed_against_the_repo() -> None:
    prereg = load_preregistration(REAL)
    assert seal_violations(prereg, root=REPO) == ()


def test_real_preregistration_carries_the_spec_constants() -> None:
    """Spec §0/§1/§4'ün sayıları — yükleyici türü, bu test DEĞERİ sabitler."""
    prereg = load_preregistration(REAL)
    assert prereg.n_stop == 1800
    assert prereg.date_limit == datetime(2027, 6, 30, 23, 59, 59, tzinfo=UTC)
    assert prereg.evaluation_lag_days == 21
    assert prereg.weakness == (
        "t2_hucum_eksik",
        "t2_savunma_eksik",
        "t2_orta_saha_eksik",
        "t2_kaleci_eksik",
        "t2_supheli",
        "t2_rotasyon",
    )
    assert prereg.strength == ("t2_donus",)
    assert prereg.excluded == ("t2_hoca_degisim", "t2_yeni_transfer")
    assert prereg.divisor == 7
    assert prereg.c_min == 0.0
    assert (prereg.ridge_lambda, prereg.beta_lower, prereg.beta_upper) == (1.0, 0.0, 5.0)
    assert prereg.tol == 1e-10
    assert prereg.gap_hours == 3
    assert (prereg.resamples, prereg.seed, prereg.level) == (10000, 20261005, 0.95)
    assert prereg.tau == 0.02
    assert prereg.calibration_bins == 10
    assert prereg.sealed_languages == ("tr",)
    assert (prereg.entry_min_n, prereg.entry_min_accuracy) == (100, 0.85)
    assert prereg.descriptive_bounds == (-5.0, 5.0)
    assert prereg.gate == "D1"
    assert prereg.comparisons == COMPARISONS
    assert prereg.counts_printed == COUNTS_PRINTED


def test_every_sealed_file_is_either_frozen_or_recorded() -> None:
    prereg = load_preregistration(REAL)
    assert set(prereg.sha256) == FROZEN_FILES | RECORDED_FILES
    assert not FROZEN_FILES & RECORDED_FILES


# ── Yükleyici: şema birebir ─────────────────────────────────────────────────────────────────


def test_unknown_top_level_field_is_rejected(tmp_path: Path) -> None:
    raw = _raw() | {"extra": 1}
    with pytest.raises(PreregistrationError, match="extra"):
        load_preregistration(_write(tmp_path, raw))


def test_missing_top_level_field_is_rejected(tmp_path: Path) -> None:
    raw = _raw()
    del raw["bootstrap"]
    with pytest.raises(PreregistrationError, match="bootstrap"):
        load_preregistration(_write(tmp_path, raw))


@pytest.mark.parametrize(
    ("section", "key"),
    [
        ("window", "start"),
        ("stop", "tie"),
        ("feature", "sign"),
        ("beta", "solver"),
        ("bootstrap", "order"),
        ("languages", "entry"),
    ],
)
def test_missing_nested_field_is_rejected(tmp_path: Path, section: str, key: str) -> None:
    raw = _raw()
    del raw[section][key]
    with pytest.raises(PreregistrationError, match=key):
        load_preregistration(_write(tmp_path, raw))


def test_unknown_nested_field_is_rejected(tmp_path: Path) -> None:
    raw = _raw()
    raw["beta"]["train"]["extra"] = 1
    with pytest.raises(PreregistrationError, match="extra"):
        load_preregistration(_write(tmp_path, raw))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("phase",), "faz3"),
        (("leg",), "archive"),
        (("window", "start"), "first_write"),
        (("stop", "tie"), "date"),
        (("feature", "sign"), "home_minus_away"),
        (("feature", "level_score"), "expectation"),
        (("feature", "asked_after_kickoff"), "keep"),
        (("beta", "solver"), "newton"),
        (("beta", "train", "result_date"), "same_day"),
        (("bootstrap", "order"), ["match_id"]),
        (("gate",), "D2"),
    ],
)
def test_unsupported_method_name_is_rejected(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    raw = _raw()
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(PreregistrationError, match=path[-1]):
        load_preregistration(_write(tmp_path, raw))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("stop", "n_stop"), 1799),
        (("stop", "n_stop"), True),
        (("stop", "n_stop"), "1800"),
        (("stop", "evaluation_lag_days"), 0),
        (("feature", "divisor"), 6),
        (("feature", "c_min"), -0.1),
        (("beta", "lambda"), 0.0),
        (("beta", "lower"), 6.0),
        (("beta", "tol"), 0.0),
        (("beta", "empty"), 1.0),
        (("beta", "train", "gap_hours"), -1),
        (("bootstrap", "resamples"), 0),
        (("bootstrap", "level"), 1.0),
        (("tau",), -0.01),
        (("calibration_bins",), 0),
        (("languages", "entry", "min_accuracy"), 1.5),
        (("descriptive_bounds", "lower"), 1.0),
    ],
)
def test_out_of_range_value_is_rejected(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    raw = _raw()
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(PreregistrationError, match=path[-1]):
        load_preregistration(_write(tmp_path, raw))


def test_date_limit_without_timezone_is_rejected(tmp_path: Path) -> None:
    raw = _raw()
    raw["stop"]["date_limit"] = datetime(2027, 6, 30, 23, 59, 59)
    with pytest.raises(PreregistrationError, match="date_limit"):
        load_preregistration(_write(tmp_path, raw))


def test_divisor_must_count_the_composite_questions(tmp_path: Path) -> None:
    raw = _raw()
    raw["feature"]["weakness"] = raw["feature"]["weakness"][:-1]
    raw["feature"]["excluded"] = [*raw["feature"]["excluded"], "t2_rotasyon"]
    with pytest.raises(PreregistrationError, match="divisor"):
        load_preregistration(_write(tmp_path, raw))


def test_feature_lists_must_be_disjoint(tmp_path: Path) -> None:
    raw = _raw()
    raw["feature"]["excluded"] = [*raw["feature"]["excluded"], "t2_donus"]
    with pytest.raises(PreregistrationError, match="ayrık"):
        load_preregistration(_write(tmp_path, raw))


def test_comparisons_must_be_the_renderer_contract(tmp_path: Path) -> None:
    raw = _raw()
    raw["comparisons"] = [c for c in raw["comparisons"] if c != "D10"]
    with pytest.raises(PreregistrationError, match="comparisons"):
        load_preregistration(_write(tmp_path, raw))


def test_counts_printed_must_be_the_renderer_contract(tmp_path: Path) -> None:
    raw = _raw()
    raw["counts_printed"] = raw["counts_printed"][1:]
    with pytest.raises(PreregistrationError, match="counts_printed"):
        load_preregistration(_write(tmp_path, raw))


def test_bad_sha_is_rejected(tmp_path: Path) -> None:
    raw = _raw()
    raw["sha256"]["config/model_faz3.yaml"] = "abc"
    with pytest.raises(PreregistrationError, match="model_faz3"):
        load_preregistration(_write(tmp_path, raw))


def test_verdict_text_must_be_present(tmp_path: Path) -> None:
    raw = _raw()
    raw["verdicts"]["passed"] = " "
    with pytest.raises(PreregistrationError, match="passed"):
        load_preregistration(_write(tmp_path, raw))


# ── Mühür denetimi: dosya ↔ depo ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(FROZEN_FILES))
def test_changed_frozen_file_breaks_the_seal(tmp_path: Path, name: str) -> None:
    root = _repo_copy(tmp_path)
    with (root / name).open("a", encoding="utf-8") as handle:
        handle.write("\n# değişti\n")
    found = seal_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root)
    assert any(name in line for line in found), found


@pytest.mark.parametrize("name", sorted(RECORDED_FILES))
def test_changed_recorded_file_does_not_break_the_seal(tmp_path: Path, name: str) -> None:
    """Spec §5: kapasite/veri hijyeni kolları pencerede değişebilir; rapor sha'yı karşılaştırır."""
    root = _repo_copy(tmp_path)
    with (root / name).open("a", encoding="utf-8") as handle:
        handle.write("\n# değişti\n")
    assert seal_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root) == ()


def test_tier2_prompt_version_is_questions_plus_live_bytes(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    raw = yaml.safe_load((root / PREREGISTRATION_PATH).read_text(encoding="utf-8"))
    questions = (root / "config/jev_questions.yaml").read_bytes()
    live = (root / "config/faz4_live.yaml").read_bytes()
    assert raw["window"]["tier2_prompt_version"] == hashlib.sha256(questions + live).hexdigest()
    raw["window"]["tier2_prompt_version"] = hashlib.sha256(live + questions).hexdigest()
    path = _write(tmp_path, raw)
    found = seal_violations(load_preregistration(path), root=root)
    assert any("tier2_prompt_version" in line for line in found), found


def _violations_after(tmp_path: Path, edit: Any) -> tuple[str, ...]:
    root = _repo_copy(tmp_path)
    raw = yaml.safe_load((root / PREREGISTRATION_PATH).read_text(encoding="utf-8"))
    edit(raw)
    return seal_violations(load_preregistration(_write(tmp_path, raw)), root=root)


def test_composite_must_cover_tier2_exactly(tmp_path: Path) -> None:
    def drop(raw: dict[str, Any]) -> None:
        raw["feature"]["excluded"] = ["t2_hoca_degisim"]

    found = _violations_after(tmp_path, drop)
    assert any("t2_yeni_transfer" in line for line in found), found


def test_composite_must_not_name_unknown_questions(tmp_path: Path) -> None:
    def rename(raw: dict[str, Any]) -> None:
        raw["feature"]["strength"] = ["t2_donus_yok"]

    found = _violations_after(tmp_path, rename)
    assert any("t2_donus_yok" in line for line in found), found


def test_d8_questions_are_composite_excluded_and_tier3(tmp_path: Path) -> None:
    def drop(raw: dict[str, Any]) -> None:
        raw["d8_questions"] = [q for q in raw["d8_questions"] if q != "t3_kart_siniri"]

    found = _violations_after(tmp_path, drop)
    assert any("d8_questions" in line for line in found), found


def test_d8_questions_must_be_unique(tmp_path: Path) -> None:
    raw = _raw()
    raw["d8_questions"] = [*raw["d8_questions"], raw["d8_questions"][0]]
    with pytest.raises(PreregistrationError, match="d8_questions"):
        load_preregistration(_write(tmp_path, raw))


def test_d5_leagues_must_be_known_leagues(tmp_path: Path) -> None:
    def add(raw: dict[str, Any]) -> None:
        raw["d5_leagues"] = [*raw["d5_leagues"], "xxx.1"]

    found = _violations_after(tmp_path, add)
    assert any("d5_leagues" in line and "xxx.1" in line for line in found), found


def test_d5_leagues_must_be_unique(tmp_path: Path) -> None:
    raw = _raw()
    raw["d5_leagues"] = [*raw["d5_leagues"], "eng.1"]
    with pytest.raises(PreregistrationError, match="d5_leagues"):
        load_preregistration(_write(tmp_path, raw))


def test_sealed_languages_must_be_in_production(tmp_path: Path) -> None:
    def add(raw: dict[str, Any]) -> None:
        raw["languages"]["sealed"] = ["tr", "en"]

    found = _violations_after(tmp_path, add)
    assert any("en" in line and "languages" in line for line in found), found


def test_entry_model_must_be_the_frozen_jev_model(tmp_path: Path) -> None:
    def change(raw: dict[str, Any]) -> None:
        raw["languages"]["entry"]["jev_model"] = "jev-2.0.0"

    found = _violations_after(tmp_path, change)
    assert any("jev_model" in line for line in found), found


def test_missing_sealed_file_is_a_violation_not_a_crash(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    (root / "config/history_lock.yaml").unlink()
    found = seal_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root)
    assert any("history_lock" in line for line in found), found


def test_d8_questions_must_not_carry_extra_ids(tmp_path: Path) -> None:
    def add(raw: dict[str, Any]) -> None:
        raw["d8_questions"] = [*raw["d8_questions"], "t4_disiplin"]

    found = _violations_after(tmp_path, add)
    assert any("d8_questions" in line for line in found), found


@pytest.mark.parametrize("name", ["config/jev_questions.yaml", "config/faz4_live.yaml"])
def test_missing_question_or_live_file_is_a_violation_not_a_crash(
    tmp_path: Path, name: str
) -> None:
    root = _repo_copy(tmp_path)
    (root / name).unlink()
    found = seal_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root)
    assert any(name in line for line in found), found


def test_malformed_languages_file_is_a_violation_not_a_crash(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    (root / "config/languages.yaml").write_text(
        'languages:\n  - code: tr\n    production_enabled: "true"\n', encoding="utf-8"
    )
    found = seal_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root)
    assert any("languages" in line for line in found), found


def test_sealed_languages_must_be_unique(tmp_path: Path) -> None:
    raw = _raw()
    raw["languages"]["sealed"] = ["tr", "tr"]
    with pytest.raises(PreregistrationError, match="sealed"):
        load_preregistration(_write(tmp_path, raw))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("beta", "lambda"), True),
        (("bootstrap", "resamples"), True),
        (("descriptive_bounds", "upper"), -1.0),
        (("beta", "lower"), -1.0),
        (("bootstrap", "order"), ["match_id", "decided_at"]),
        (("languages", "entry", "jev_model"), " "),
        (("feature", "excluded"), []),
        (("languages", "sealed"), [""]),
        (("window", "tier2_prompt_version"), "a" * 63),
        (("closure_kinds",), ["n_stop", "date", "user", "vendor"]),
        (("methods", "log_loss"), "market.metrics.log_loss"),
        (("methods", "d1b"), "match"),
        (("methods", "d9_sd_ddof"), 0),
        (("level_scores", "low"), 1.5),
        (("methods", "d9_sd_ddof"), True),
        (("beta", "train", "requires"), ["haberli", "harman_complete", "settled", "in_window"]),
        (
            ("beta", "train", "requires"),
            ["harman_complete", "haberli", "settled", "in_window", "gate_language"],
        ),
        (("beta", "lower"), 5.0),
        (("window", "tier2_prompt_version"), "a" * 65),
        (("window", "tier2_prompt_version"), "A" * 64),
    ],
)
def test_survivor_values_are_rejected(tmp_path: Path, path: tuple[str, ...], value: object) -> None:
    raw = _raw()
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(PreregistrationError, match=path[-1]):
        load_preregistration(_write(tmp_path, raw))


def test_reversed_comparisons_are_rejected(tmp_path: Path) -> None:
    raw = _raw()
    raw["comparisons"] = list(reversed(raw["comparisons"]))
    with pytest.raises(PreregistrationError, match="comparisons"):
        load_preregistration(_write(tmp_path, raw))


def test_missing_sha_key_is_rejected(tmp_path: Path) -> None:
    raw = _raw()
    del raw["sha256"]["config/faz4_ops.yaml"]
    with pytest.raises(PreregistrationError, match="sha256"):
        load_preregistration(_write(tmp_path, raw))


def test_extra_sha_key_is_rejected(tmp_path: Path) -> None:
    raw = _raw()
    raw["sha256"]["config/sources.yaml"] = "0" * 64
    with pytest.raises(PreregistrationError, match="sha256"):
        load_preregistration(_write(tmp_path, raw))


def test_short_sha_is_rejected(tmp_path: Path) -> None:
    raw = _raw()
    raw["sha256"]["config/history_aliases.yaml"] = "a" * 40
    with pytest.raises(PreregistrationError, match="history_aliases"):
        load_preregistration(_write(tmp_path, raw))


def test_duplicate_yaml_key_is_rejected(tmp_path: Path) -> None:
    """Mühürlü metni okuyan insan kodun kullandığı sayıyı görsün (yoksa son anahtar kazanırdı)."""
    text = REAL.read_text(encoding="utf-8").replace(
        "  n_stop: 1800\n", "  n_stop: 900\n  n_stop: 1800\n"
    )
    path = tmp_path / "prereg.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(PreregistrationError, match="n_stop"):
        load_preregistration(path)


def test_level_scores_must_be_the_code_scale(tmp_path: Path) -> None:
    """R190: düzey değerleri `derive.LEVEL_SCORES`la birebir; kod değişirse mühür kırmızı."""
    root = _repo_copy(tmp_path)
    prereg = load_preregistration(root / PREREGISTRATION_PATH)
    assert dict(prereg.level_scores) == {"none": 0.0, "low": 1 / 3, "medium": 2 / 3, "high": 1.0}
    raw = yaml.safe_load((root / PREREGISTRATION_PATH).read_text(encoding="utf-8"))
    raw["level_scores"] = {"none": 0.0, "low": 0.25, "medium": 2 / 3, "high": 1.0}
    found = seal_violations(load_preregistration(_write(tmp_path, raw)), root=root)
    assert any("level_scores" in line for line in found), found


@pytest.mark.parametrize(("key", "value"), [("min_accuracy", 0.8), ("min_n", 50)])
def test_entry_thresholds_must_be_the_calibration_defaults(
    tmp_path: Path, key: str, value: float
) -> None:
    def change(raw: dict[str, Any]) -> None:
        raw["languages"]["entry"][key] = value

    found = _violations_after(tmp_path, change)
    assert any(key in line for line in found), found


# ── Mühür anı: kollar dâhil her dosya birebir, lig ve dil kümesi eşit ──────────────────────


def test_real_preregistration_matches_the_seal_time_state_or_names_the_drift() -> None:
    """Mühür commit'inde boş döner; sonra yalnız kollar (spec §5) adıyla görünebilir."""
    found = seal_time_violations(load_preregistration(REAL), root=REPO)
    allowed = tuple(sorted(RECORDED_FILES))
    assert all(
        line.startswith(allowed) or line.startswith(("d5_leagues", "languages")) for line in found
    ), found


@pytest.mark.parametrize("name", sorted(RECORDED_FILES))
def test_seal_time_check_names_a_changed_recorded_file(tmp_path: Path, name: str) -> None:
    root = _repo_copy(tmp_path)
    with (root / name).open("a", encoding="utf-8") as handle:
        handle.write("\n# değişti\n")
    found = seal_time_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root)
    assert any(line.startswith(name) for line in found), found


def test_seal_time_check_is_clean_on_an_unchanged_copy(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    assert seal_time_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root) == ()


def test_seal_time_d5_must_equal_the_active_leagues(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    raw = yaml.safe_load((root / PREREGISTRATION_PATH).read_text(encoding="utf-8"))
    raw["d5_leagues"] = [league for league in raw["d5_leagues"] if league != "bel.1"]
    found = seal_time_violations(load_preregistration(_write(tmp_path, raw)), root=root)
    assert any("d5_leagues" in line for line in found), found


def test_seal_time_languages_must_equal_production(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    text = (root / "config/languages.yaml").read_text(encoding="utf-8")
    patched = text.replace(
        "  - code: en\n    production_enabled: false", "  - code: en\n    production_enabled: true"
    )
    assert patched != text
    (root / "config/languages.yaml").write_text(patched, encoding="utf-8")
    found = seal_time_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root)
    assert any(line.startswith("languages.sealed") for line in found), found


def test_seal_time_d5_must_not_carry_inactive_leagues(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    raw = yaml.safe_load((root / PREREGISTRATION_PATH).read_text(encoding="utf-8"))
    raw["d5_leagues"] = [*raw["d5_leagues"], "aut.1"]
    prereg = load_preregistration(_write(tmp_path, raw))
    assert seal_violations(prereg, root=root) == ()  # kalıcı denetim: bilinen lig yeter
    found = seal_time_violations(prereg, root=root)
    assert any("d5_leagues" in line for line in found), found


def test_seal_time_sealed_languages_must_not_exceed_production(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    raw = yaml.safe_load((root / PREREGISTRATION_PATH).read_text(encoding="utf-8"))
    raw["languages"]["sealed"] = ["tr", "en"]
    found = seal_time_violations(load_preregistration(_write(tmp_path, raw)), root=root)
    assert any(line.startswith("languages.sealed") for line in found), found


def test_seal_time_malformed_languages_file_is_a_violation_not_a_crash(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    (root / "config/languages.yaml").write_text(
        'languages:\n  - code: tr\n    production_enabled: "true"\n', encoding="utf-8"
    )
    found = seal_time_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root)
    assert any(line.startswith("languages: ") for line in found), found


@pytest.mark.parametrize("check", [seal_violations, seal_time_violations])
def test_malformed_leagues_file_is_a_violation_not_a_crash(tmp_path: Path, check: Any) -> None:
    root = _repo_copy(tmp_path)
    (root / "config/leagues.yaml").write_text("ligler: []\n", encoding="utf-8")
    found = check(load_preregistration(root / PREREGISTRATION_PATH), root=root)
    assert any(line.startswith("config/leagues.yaml: okunamadı") for line in found), found


def test_seal_time_check_also_names_a_changed_frozen_file(tmp_path: Path) -> None:
    root = _repo_copy(tmp_path)
    with (root / "config/model_faz3.yaml").open("a", encoding="utf-8") as handle:
        handle.write("\n# değişti\n")
    found = seal_time_violations(load_preregistration(root / PREREGISTRATION_PATH), root=root)
    assert any(line.startswith("config/model_faz3.yaml") for line in found), found
