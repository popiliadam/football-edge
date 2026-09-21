"""Task 12 — `calibrate`/`check-languages` CLI kablolaması.

Aynı desen: `test_collect_map_entities.py`. Bu dosya DAĞITIM katmanını sınar —
`language_config_violations`/`score_language`/`production_ready`in KENDİ mantığı zaten
`tests/test_calibration.py`de kanıtlanmış, burada TEKRAR edilmez. Burada sınanan yalnız:
doğru kolaborasyon doğru argümanla çağrılıyor mu, stdout/exit kodu doğru mu, ve — Ruling
R4'ün kalbi — `check-languages` GERÇEKTEN ağa/DB'ye hiç dokunmadan mı koşuyor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from football_edge import collect
from football_edge.calibration import CalibrationReport
from football_edge.jev import ChoiceAnswer
from tests.fake_jev import FakeJev


def _explode(*_a: object, **_k: object) -> object:
    raise AssertionError("bu kolaborasyon ÇAĞRILMAMALIYDI")


@dataclass
class _NullConn:
    """`connect()`in yerini tutar. `check-languages`/`calibrate` hiçbir yolda ONU bile
    çağırmamalı (Ruling R4: ikisi de `connect()` açılmadan önce dallanır) — ama testler
    bunu `collect.connect`i `_explode`e bağlayarak KANITLAR, yalnız yorumla iddia etmez."""

    closed: bool = field(default=False)

    def __enter__(self) -> _NullConn:
        return self

    def __exit__(self, *exc: object) -> None:
        self.closed = True


def _write_languages(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _check_languages_command
# ---------------------------------------------------------------------------


def test_check_languages_passes_when_zero_languages_are_enabled(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bugünkü GERÇEK durum: `config/languages.yaml`'da HER dil false. Kapı bunu
    TEMİZ geçmeli — boş/kapalı liste bir hata DEĞİLDİR."""
    languages = _write_languages(
        tmp_path / "languages.yaml",
        "languages:\n"
        "  - code: tr\n"
        "    production_enabled: false\n"
        "    calibration_report: data/calibration/tr.report.json\n"
        "  - code: en\n"
        "    production_enabled: false\n"
        "    calibration_report: data/calibration/en.report.json\n",
    )

    code = collect._check_languages_command(languages_path=languages)

    out = capsys.readouterr().out
    assert code == 0
    assert "dil kalibrasyonu: TEMİZ" in out


def test_check_languages_fails_when_an_enabled_language_has_no_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    languages = _write_languages(
        tmp_path / "languages.yaml",
        "languages:\n"
        "  - code: tr\n"
        "    production_enabled: true\n"
        "    calibration_report: data/calibration/does-not-exist.report.json\n",
    )

    code = collect._check_languages_command(languages_path=languages)

    out = capsys.readouterr().out
    assert code == collect.EXIT_LANGUAGE_UNCALIBRATED
    assert "DİL KALİBRASYON İHLALİ" in out
    assert "tr" in out and "rapor yok" in out


def test_check_languages_never_touches_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling R4: `check-languages` ağa çıkmaz VE veritabanına dokunmaz — kapı bunu
    HER push'ta koşar."""
    languages = _write_languages(tmp_path / "languages.yaml", "languages: []\n")
    monkeypatch.setattr(collect, "connect", _explode)

    code = collect._check_languages_command(languages_path=languages)

    assert code == 0


# ---------------------------------------------------------------------------
# _calibrate_command
# ---------------------------------------------------------------------------


def test_calibrate_command_writes_a_report_and_prints_the_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "tr.jsonl").write_text(
        '{"title":"a","url":"u","language":"tr","team":"Galatasaray","relevant":true}\n',
        encoding="utf-8",
    )
    fake = FakeJev(ChoiceAnswer(choice="relevant", confidence=0.9, probabilities={}))
    monkeypatch.setattr(collect, "TypeSafeJev", lambda: fake)

    code = collect._calibrate_command("tr", calibration_dir=tmp_path)

    out = capsys.readouterr().out
    report_path = tmp_path / "tr.report.json"
    assert code == 0
    assert report_path.is_file()
    assert "calibrate:" in out
    assert "rapor yazıldı" in out
    written = CalibrationReport(**json.loads(report_path.read_text(encoding="utf-8")))
    assert written.n == 1
    assert written.accuracy == pytest.approx(1.0)


def test_calibrate_command_refuses_a_missing_label_file_without_constructing_jev(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Etiket dosyası yoksa Jev hiç KURULMAZ — `TYPESAFE_API_KEY` boş bir turda bile
    istenmez (aynı desen: `map-entities`'in boş kanonik liste kısayolu)."""
    monkeypatch.setattr(collect, "TypeSafeJev", _explode)

    code = collect._calibrate_command("tr", calibration_dir=tmp_path)

    out = capsys.readouterr().out
    assert code == collect.EXIT_LANGUAGE_UNCALIBRATED
    assert "önce elle etiketlenmeli" in out


def test_calibrate_command_requires_typesafe_api_key_when_labels_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anahtarsız SESSİZCE geçmez: `TypeSafeJev()` adıyla patlar — canlı çağrı asla
    denenmez, kurulum hatası hemen görünür olur (map-entities'le AYNI desen)."""
    (tmp_path / "tr.jsonl").write_text(
        '{"title":"a","url":"u","language":"tr","team":"Galatasaray","relevant":true}\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        collect._calibrate_command("tr", calibration_dir=tmp_path)


# ---------------------------------------------------------------------------
# main() kablolaması
# ---------------------------------------------------------------------------


def test_main_check_languages_reads_the_real_repo_config_and_never_connects(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Uçtan uca: gerçek `config/languages.yaml` — Task 12'nin bıraktığı hâliyle, iki dil
    de false — TEMİZ vermeli, ve `connect()`e hiç dokunmamalı."""
    monkeypatch.setattr(collect, "connect", _explode)

    code = collect.main(["check-languages"])

    out = capsys.readouterr().out
    assert code == 0
    assert "dil kalibrasyonu: TEMİZ" in out


def test_main_calibrate_requires_language(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        collect.main(["calibrate"])

    assert exc_info.value.code == 2
    assert "--language" in capsys.readouterr().err


def test_main_routes_calibrate_before_connecting(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`calibrate` `connect()`den ÖNCE dallanır (Ruling R4). `CALIBRATION_DIR`i
    monkeypatch'lemek İŞE YARAMAZ — `_calibrate_command`in varsayılan argümanı DEF
    ANINDA bağlanır, modül sabiti sonradan değişse de o bağ değişmez (gerçek bir hata
    burada bulundu: eski test tam bunu varsayıyordu). Bunun yerine hiç etiket dosyası
    olmayan bir dil kodu kullanılır — GERÇEK `data/calibration/` dizinine karşı."""
    monkeypatch.setattr(collect, "connect", _explode)
    monkeypatch.setattr(collect, "TypeSafeJev", _explode)

    code = collect.main(["calibrate", "--language", "zz-does-not-exist"])

    out = capsys.readouterr().out
    assert code == collect.EXIT_LANGUAGE_UNCALIBRATED
    assert "önce elle etiketlenmeli" in out


def test_main_choices_include_the_two_new_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    """`choices`e eklenmezse argparse bunları hiç kabul etmez: geçersiz komut hatası
    argparse'ın KENDİ metninde TÜM geçerli seçenekleri adıyla listeler — ikisi orada
    yoksa `choices` tuple'ına hiç eklenmemiş demektir."""
    with pytest.raises(SystemExit) as exc_info:
        collect.main(["not-a-real-command"])

    err = capsys.readouterr().err
    assert exc_info.value.code == 2
    assert "'calibrate'" in err
    assert "'check-languages'" in err
