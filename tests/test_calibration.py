"""Task 12 — dil kalibrasyonu: Jev'in çok dilli doğruluğu hiç ÖLÇÜLMEMİŞTİ (spec §5.4,
açık soru #4). Bu dosya `calibration.py`nin ÖLÇÜM mantığını sınar — `FakeJev` ile, ağsız,
tıpkı Task 11'in `mapping.py`yi sınadığı gibi. Gerçek Jev çağrısı burada YOKTUR: bu ortamda
`TYPESAFE_API_KEY` yok, ve etiketleri modele ürettirmek ölçümü ölçülenin kopyası yapardı.

`language_config_violations`/`write_report` brief'te YOKTU — brief bu iki işi `collect.py`
içine gömüyordu (`_check_languages_command`). `collect.py` 757/800 satırdaydı (task
uyarısı: iki yeni alt komut sınırı zorlar); bu mantık BURAYA taşındı ki `collect.py` yalnız
ince bir CLI sevk katmanı kalsın — aynı gerekçeyle `fetch.py` Task 11'de ayrıldı (R50).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_edge.calibration import (
    CalibrationReport,
    LabelledItem,
    language_config_violations,
    load_labels,
    production_ready,
    run_calibration,
    score_language,
    write_report,
)
from football_edge.jev import ChoiceAnswer
from tests.fake_jev import FakeJev


def item(relevant: bool, title: str = "Galatasaray'da sakatlık") -> LabelledItem:
    return LabelledItem(
        title=title, url=f"https://x/{title}", language="tr", relevant=relevant, team="Galatasaray"
    )


def answer(choice: str, confidence: float = 0.9) -> ChoiceAnswer:
    return ChoiceAnswer(choice=choice, confidence=confidence, probabilities={choice: confidence})


# ---------------------------------------------------------------------------
# score_language
# ---------------------------------------------------------------------------


def test_perfect_agreement_scores_one() -> None:
    report = score_language((item(True), item(True)), FakeJev(answer("relevant")), language="tr")
    assert report.accuracy == pytest.approx(1.0)
    assert report.n == 2


def test_disagreement_is_split_into_false_positive_and_false_negative() -> None:
    """Tek bir 'doğruluk' sayısı yönü gizler. Hangi yönde yanıldığı KARAR değiştirir."""
    report = score_language((item(False), item(False)), FakeJev(answer("relevant")), language="tr")
    assert report.accuracy == pytest.approx(0.0)
    assert report.false_positive == 2
    assert report.false_negative == 0


def test_language_below_the_sample_floor_is_not_production_ready() -> None:
    """%100 doğruluk 12 örnekte hiçbir şey kanıtlamaz."""
    report = score_language((item(True),) * 12, FakeJev(answer("relevant")), language="tr")
    ready, reason = production_ready(report)
    assert ready is False
    assert "örnek" in reason


def test_language_below_the_accuracy_floor_is_not_production_ready() -> None:
    items = (item(True),) * 80 + (item(False),) * 40
    report = score_language(items, FakeJev(answer("relevant")), language="tr")
    ready, reason = production_ready(report)
    assert ready is False
    assert "doğruluk" in reason


def test_labels_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "tr.jsonl"
    target.write_text(
        '{"title":"a","url":"u","language":"tr","team":"Galatasaray","relevant":true}\n'
        '{"title":"b","url":"v","language":"tr","team":"Fenerbahce","relevant":false}\n',
        encoding="utf-8",
    )
    loaded = load_labels(target)
    assert len(loaded) == 2
    assert loaded[0].relevant is True and loaded[1].relevant is False


# ---------------------------------------------------------------------------
# run_calibration — `collect._calibrate_command`in TEK işi; `load_labels` + `score_language`
# + `write_report` + `production_ready`nin kompozisyonu (`collect.py`yi ince tutmak için
# burada, bkz. modül docstring'i).
# ---------------------------------------------------------------------------


def test_run_calibration_writes_a_report_and_returns_its_verdict(tmp_path: Path) -> None:
    (tmp_path / "tr.jsonl").write_text(
        '{"title":"a","url":"u","language":"tr","team":"Galatasaray","relevant":true}\n'
        '{"title":"b","url":"v","language":"tr","team":"Galatasaray","relevant":false}\n',
        encoding="utf-8",
    )

    path, reason = run_calibration(
        "tr", tmp_path, FakeJev(ChoiceAnswer(choice="relevant", confidence=0.9, probabilities={}))
    )

    assert path == tmp_path / "tr.report.json"
    written = CalibrationReport(**json.loads(path.read_text(encoding="utf-8")))
    assert written.n == 2
    assert written.accuracy == pytest.approx(0.5)
    assert "tr" in reason


# ---------------------------------------------------------------------------
# write_report — `calibrate`in tek disk-yazan adımı
# ---------------------------------------------------------------------------


def test_write_report_writes_the_language_named_file(tmp_path: Path) -> None:
    report = CalibrationReport(
        language="tr", n=100, accuracy=0.9, false_positive=5, false_negative=5, mean_confidence=0.8
    )

    path = write_report(report, tmp_path)

    assert path == tmp_path / "tr.report.json"
    assert path.is_file()


def test_write_report_round_trips_through_json(tmp_path: Path) -> None:
    """Yazılan JSON, `CalibrationReport(**...)` ile GERİ okunca aynı raporu üretmeli —
    `language_config_violations`in gerçekte okuduğu biçim budur."""
    report = CalibrationReport(
        language="tr",
        n=120,
        accuracy=0.91,
        false_positive=6,
        false_negative=5,
        mean_confidence=0.83,
    )

    path = write_report(report, tmp_path)
    loaded = CalibrationReport(**json.loads(path.read_text(encoding="utf-8")))

    assert loaded == report


# ---------------------------------------------------------------------------
# language_config_violations — kapının `dil-kalibrasyonu` adımının çağırdığı fonksiyon
# ---------------------------------------------------------------------------


def _write_config(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_zero_enabled_languages_is_clean_not_an_error(tmp_path: Path) -> None:
    """HİÇBİR dil production_enabled=true değilse kapı TEMİZ geçmeli — hata değil."""
    config = _write_config(
        tmp_path / "languages.yaml",
        "languages:\n"
        "  - code: tr\n"
        "    production_enabled: false\n"
        "    calibration_report: data/calibration/tr.report.json\n"
        "  - code: en\n"
        "    production_enabled: false\n"
        "    calibration_report: data/calibration/en.report.json\n",
    )

    assert language_config_violations(config) == ()


def test_an_empty_language_list_is_also_clean(tmp_path: Path) -> None:
    config = _write_config(tmp_path / "languages.yaml", "languages: []\n")

    assert language_config_violations(config) == ()


def test_production_enabled_without_a_report_file_is_a_violation(tmp_path: Path) -> None:
    config = _write_config(
        tmp_path / "languages.yaml",
        "languages:\n"
        "  - code: tr\n"
        "    production_enabled: true\n"
        "    calibration_report: data/calibration/does-not-exist.report.json\n",
    )

    violations = language_config_violations(config)

    assert len(violations) == 1
    assert "tr" in violations[0]
    assert "rapor yok" in violations[0]


def test_a_report_that_fails_the_accuracy_floor_is_a_violation(tmp_path: Path) -> None:
    report_path = tmp_path / "tr.report.json"
    report_path.write_text(
        json.dumps(
            {
                "language": "tr",
                "n": 120,
                "accuracy": 0.5,
                "false_positive": 30,
                "false_negative": 30,
                "mean_confidence": 0.7,
            }
        ),
        encoding="utf-8",
    )
    config = _write_config(
        tmp_path / "languages.yaml",
        "languages:\n"
        "  - code: tr\n"
        "    production_enabled: true\n"
        f"    calibration_report: {report_path}\n",
    )

    violations = language_config_violations(config)

    assert len(violations) == 1
    assert "doğruluk" in violations[0]


def test_a_report_that_clears_the_bar_is_clean(tmp_path: Path) -> None:
    report_path = tmp_path / "tr.report.json"
    report_path.write_text(
        json.dumps(
            {
                "language": "tr",
                "n": 120,
                "accuracy": 0.9,
                "false_positive": 6,
                "false_negative": 6,
                "mean_confidence": 0.85,
            }
        ),
        encoding="utf-8",
    )
    config = _write_config(
        tmp_path / "languages.yaml",
        "languages:\n"
        "  - code: tr\n"
        "    production_enabled: true\n"
        f"    calibration_report: {report_path}\n",
    )

    assert language_config_violations(config) == ()


def test_one_enabled_language_missing_a_report_is_named_even_if_another_is_clean(
    tmp_path: Path,
) -> None:
    """Birden çok dil varken sorunlu OLAN adıyla çıkmalı, temiz olan susmalı."""
    clean_report = tmp_path / "en.report.json"
    clean_report.write_text(
        json.dumps(
            {
                "language": "en",
                "n": 100,
                "accuracy": 0.95,
                "false_positive": 2,
                "false_negative": 3,
                "mean_confidence": 0.9,
            }
        ),
        encoding="utf-8",
    )
    config = _write_config(
        tmp_path / "languages.yaml",
        "languages:\n"
        "  - code: tr\n"
        "    production_enabled: true\n"
        "    calibration_report: data/calibration/does-not-exist.report.json\n"
        "  - code: en\n"
        "    production_enabled: true\n"
        f"    calibration_report: {clean_report}\n",
    )

    violations = language_config_violations(config)

    assert len(violations) == 1
    assert "tr" in violations[0]
