"""Dış çıpa: kuyruk kesme yakalanmalı, çıpa yoksa ATLANDI denmeli, tarama sabit kalmalı."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge.collect import _latest_anchor, _publish_head_command, _verify_chain_command
from tests.fake_db import FakeChainDb, chained_rows

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _write_anchor(directory: Path, *, rows: int, last_id: int, head: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "head-2026-09-19.txt"
    target.write_text(
        f"{NOW.isoformat()}\nrows={rows}\nlast_id={last_id}\nhead={head}\n", encoding="utf-8"
    )
    return target


def test_truncate_and_refill_with_the_same_row_count_is_caught(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E4: TRUNCATE satır tetikleyicisini ateşlemez; aynı sayıda sahte satır zinciri kendi
    içinde tutarlıdır. Yalnız çıpanın işaret ettiği satırın hash'i arızayı gösterir."""
    genuine = chained_rows(3)
    forged = chained_rows(3, bookmaker="forged_book")
    _write_anchor(tmp_path, rows=3, last_id=3, head=str(genuine[-1]["row_hash"]))

    code = _verify_chain_command(FakeChainDb(forged), anchor_dir=tmp_path)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert code == 1, f"kuyruk kesilip yeniden dolduruldu ama kontrol geçti: {out!r}"
    assert "ÇIPA UYUŞMAZLIĞI" in out


def test_intact_ledger_after_the_anchor_verifies_only_the_tail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E4: tarama sabit maliyete inmeli — çıpadan sonrası kontrol edilir, tüm defter değil."""
    head = chained_rows(3)
    tail = chained_rows(2, start_hash=str(head[-1]["row_hash"]), first_id=4)
    _write_anchor(tmp_path, rows=3, last_id=3, head=str(head[-1]["row_hash"]))

    code = _verify_chain_command(FakeChainDb((*head, *tail)), anchor_dir=tmp_path)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert code == 0, out
    assert "kontrol=2" in out, f"tüm defter yeniden hash'lendi: {out!r}"


def test_missing_anchor_is_reported_as_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E5: atlanan kontrol geçmek değildir — adıyla raporlanır."""
    code = _verify_chain_command(FakeChainDb(chained_rows(2)), anchor_dir=tmp_path)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert "ATLANDI" in out, f"çıpa yok ama sessiz kalındı: {out!r}"
    assert code == 0


def test_corrupt_anchor_file_is_reported_not_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """E5: bozuk çıpa dosyası traceback ile düşmez, adıyla raporlanır."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "head-2026-09-19.txt").write_text(
        "2026-09-19\nrows=abc\nlast_id=xyz\nhead=deadbeef\n", encoding="utf-8"
    )

    code = _verify_chain_command(FakeChainDb(chained_rows(2)), anchor_dir=tmp_path)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert "ATLANDI" in out, f"bozuk çıpa sessizce yutuldu: {out!r}"
    assert code == 0


def test_anchor_without_last_id_is_reported_as_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eski biçimli çıpa (last_id yok) kuyruk kesme kontrolünü sessizce geçiremez."""
    (tmp_path / "head-2026-09-19.txt").write_text(
        "2026-09-19\nrows=2\nhead=abc\n", encoding="utf-8"
    )

    _verify_chain_command(FakeChainDb(chained_rows(2)), anchor_dir=tmp_path)  # type: ignore[arg-type]

    assert "ATLANDI" in capsys.readouterr().out


def test_publish_head_records_last_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """E4: çıpa last_id yazmazsa kuyruk kesme kontrolü kurulamaz."""
    db = FakeChainDb(chained_rows(3))

    code = _publish_head_command(db, NOW, directory=tmp_path)  # type: ignore[arg-type]

    capsys.readouterr()
    anchor = _latest_anchor(tmp_path)
    assert code == 0
    assert anchor is not None
    assert anchor.last_id == 3
    assert anchor.rows == 3
    assert anchor.head == db.rows[-1]["row_hash"]
