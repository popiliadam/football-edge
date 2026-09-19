"""Dış çıpa: kuyruk kesme yakalanmalı, çıpa yoksa ATLANDI denmeli, tarama sabit kalmalı."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge.collect import _latest_anchor, _publish_head_command, _verify_chain_command
from tests.fake_db import FakeChainDb, chained_rows

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _write_anchor(
    directory: Path, *, rows: int, last_id: int, head: str, name: str = "head-2026-09-19.txt"
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
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


# ── F2: çıpa kontrolü saldırganın YAZABİLDİĞİ sütuna güvenmemeli ────────────
# Yayınlanmış head HERKESE AÇIK (depoya commit'lenir). Veritabanına yazabilen biri
# o açık değeri last_id satırının row_hash HÜCRESİNE yazar, sahte kuyruğunu oradan
# zincirler; saklanan hücre ile çıpa birebir tutar ve kontrol exit 0 verir.


def test_anchor_row_hash_cell_alone_does_not_prove_the_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F2: hash saklanan hücreden değil, satırın İÇERİĞİNDEN yeniden hesaplanmalı."""
    genuine = chained_rows(3)
    head = str(genuine[-1]["row_hash"])
    _write_anchor(tmp_path, rows=3, last_id=3, head=head)

    forged = chained_rows(3, bookmaker="forged_book")
    # Saldırgan yalnız hücreyi yazar; satırın içeriği sahte kalır.
    prefix = (*forged[:2], {**forged[2], "row_hash": head})
    tail = chained_rows(2, start_hash=head, first_id=4)

    code = _verify_chain_command(FakeChainDb((*prefix, *tail)), anchor_dir=tmp_path)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert code == 1, f"açık head hücreye yazıldı ve kontrol geçti: {out!r}"
    assert "ÇIPA UYUŞMAZLIĞI" in out


def test_rewritten_prefix_is_caught_by_the_oldest_anchor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F2: çalışma ağacındaki EN YENİ çıpa dosyası da saldırganın yazabildiği bir dosyadır.

    Defteri baştan sona yeniden zincirleyip `ledger/`deki son çıpayı da kendi head'iyle
    değiştiren biri, yalnız en yeni çıpaya bakan bir kontrolden geçer. Eski çıpa git
    GEÇMİŞİNDE durur — öneki yeniden yazılmış defteri gösteren tek şey odur.
    """
    genuine = chained_rows(3)
    _write_anchor(
        tmp_path, rows=3, last_id=3, head=str(genuine[-1]["row_hash"]), name="head-2026-09-18.txt"
    )
    forged = chained_rows(5, bookmaker="forged_book")
    _write_anchor(tmp_path, rows=5, last_id=5, head=str(forged[-1]["row_hash"]))

    code = _verify_chain_command(FakeChainDb(forged), anchor_dir=tmp_path)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert code == 1, f"önek yeniden yazıldı, en eski çıpa sorulmadı: {out!r}"
    assert "ÇIPA UYUŞMAZLIĞI" in out
    assert "head-2026-09-18.txt" in out, f"hangi çıpanın tutmadığı yazılmalı: {out!r}"


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
