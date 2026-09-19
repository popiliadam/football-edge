"""Dış çıpa: kuyruk kesme yakalanmalı, çıpa yoksa ATLANDI denmeli, tarama sabit kalmalı."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from football_edge.collect import (
    _latest_anchor,
    _publish_head_command,
    _verify_chain_command,
    archived_anchors,
    expected_anchor_names,
    missing_anchors,
)
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


# ── G4: EN YENİ çıpa okunamayınca kontrol sessizce bir öncekine düşüyordu ────
# `_anchors` okunamayan dosyayı eliyor; `anchors[-1]` en yeni OKUNABİLİR çıpa oluyor ve
# stdout `zincir: SAĞLAM` diyor. Tek iz bir log uyarısı. Bu projenin kuralı: atlanan ya da
# düşürülen kontrol geçmek değildir, adıyla raporlanır — round 2 öncesi de böyleydi.


def test_corrupt_newest_anchor_is_reported_not_silently_downgraded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """G4: bozuk EN YENİ çıpa, sağlam bir eskisinin arkasına saklanamaz."""
    genuine = chained_rows(3)
    _write_anchor(
        tmp_path, rows=3, last_id=3, head=str(genuine[-1]["row_hash"]), name="head-2026-09-18.txt"
    )
    (tmp_path / "head-2026-09-19.txt").write_text(
        "2026-09-19\nrows=abc\nlast_id=xyz\nhead=deadbeef\n", encoding="utf-8"
    )

    code = _verify_chain_command(FakeChainDb(genuine), anchor_dir=tmp_path)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert "ATLANDI" in out, f"en yeni çıpa okunamadı ama çıktı bunu söylemedi: {out!r}"
    assert "head-2026-09-19.txt" in out, f"hangi çıpanın okunamadığı yazılmalı: {out!r}"
    assert code == 0, out


# ── DEFERRED §1.1/§1.2: çıpa varken defterin İÇİ bir daha hash'lenmiyordu ────
# `_verify_chain_command` yalnız (i) çıpanın gösterdiği tek satırı ve (ii) en yeni
# çıpadan sonraki kuyruğu ölçüyordu. Aradaki satırlar hiçbir zamanlanmış koşuda
# doğrulanmıyordu — çıpalar hep ileri gittiği için hiç doğrulanmayacaktı.


def test_full_scan_rehashes_rows_before_the_anchor(tmp_path: Path) -> None:
    """Varsayılan mod çıpanın ÖNCESİNİ hiç okumuyor; --full okumak zorunda."""
    rows = list(chained_rows(6))
    anchor = tmp_path / "head-2026-09-19.txt"
    anchor.write_text(
        f"2026-09-19T00:00:00+00:00\nrows=6\nlast_id=6\nhead={rows[-1]['row_hash']}\n",
        encoding="utf-8",
    )
    rows[2] = {**rows[2], "price": Decimal("9.99")}  # çıpanın ÖNÜNDEKİ bir satır kurcalandı
    db = FakeChainDb(rows=tuple(rows))

    assert _verify_chain_command(db, anchor_dir=tmp_path) == 0, "varsayılan mod bunu göremez"
    assert _verify_chain_command(db, anchor_dir=tmp_path, full=True) == 1


def test_full_scan_asks_every_anchor_not_just_first_and_last(tmp_path: Path) -> None:
    """asked = (anchors[0], anchors[-1]) — 30 günde 28 çıpa hiç sorulmuyordu."""
    rows = chained_rows(9)
    for index, count in ((0, 3), (1, 6), (2, 9)):
        day = 17 + index
        (tmp_path / f"head-2026-09-{day}.txt").write_text(
            f"2026-09-{day}T00:00:00+00:00\nrows={count}\nlast_id={count}\n"
            f"head={rows[count - 1]['row_hash']}\n",
            encoding="utf-8",
        )
    # ORTADAKİ çıpayı yalancı yap: ne ilk ne son.
    (tmp_path / "head-2026-09-18.txt").write_text(
        "2026-09-18T00:00:00+00:00\nrows=6\nlast_id=6\nhead=" + "b" * 64 + "\n",
        encoding="utf-8",
    )
    db = FakeChainDb(rows=rows)

    assert _verify_chain_command(db, anchor_dir=tmp_path) == 0, "orta çıpa sorulmuyordu"
    assert _verify_chain_command(db, anchor_dir=tmp_path, full=True) == 1


def test_missing_anchor_is_reported_by_name(tmp_path: Path, capsys: Any) -> None:
    """Silinen çıpa bozulandan SESSİZDİR: _scan_anchors yalnız var olanı görür."""
    (tmp_path / "head-2026-09-19.txt").write_text(
        "x\nrows=0\nlast_id=0\nhead=z\n", encoding="utf-8"
    )
    recorded = ("head-2026-09-18.txt", "head-2026-09-19.txt")

    assert missing_anchors(tmp_path, recorded=recorded) == ("head-2026-09-18.txt",)


def test_missing_anchor_check_is_named_when_git_is_absent(tmp_path: Path) -> None:
    """Atlanan kontrol geçmek değildir; git yoksa None döner ve çağıran adıyla yazar."""
    assert expected_anchor_names(tmp_path) is None


def test_verify_chain_command_fails_when_git_history_shows_a_deleted_anchor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Entegrasyon kanıtı: `missing_anchors` doğru hesaplansa da `_verify_chain_command`
    onu hiç SORMAZSA silinen çıpa yine sessiz kalır. `expected_anchor_names`/`missing_anchors`
    birim testleri `_verify_chain_command`'ı hiç çağırmıyor — DEFERRED §1.3'ü kapatan asıl
    tel budur, birim parçaların doğruluğu tek başına yetmez.
    """
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    genuine = chained_rows(2)
    _write_anchor(
        tmp_path, rows=2, last_id=2, head=str(genuine[-1]["row_hash"]), name="head-2026-09-18.txt"
    )
    _write_anchor(
        tmp_path, rows=2, last_id=2, head=str(genuine[-1]["row_hash"]), name="head-2026-09-19.txt"
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.email=t@example.com", "-c", "user.name=t"]
        + ["commit", "-q", "-m", "iki çıpa"],
        check=True,
    )
    # Bu GERÇEK bir silme (unlink) — RUNBOOK §1.4'teki arşivleme (taşıma) DEĞİL. Arşivlenen
    # bir çıpanın exit 1 VERMEMESİ gerektiği ayrı bir kanıt ister: bkz.
    # test_verify_chain_command_accepts_archived_anchor_without_failing.
    (tmp_path / "head-2026-09-18.txt").unlink()

    code = _verify_chain_command(FakeChainDb(genuine), anchor_dir=tmp_path)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert code == 1, f"git geçmişinde duran ama diskte olmayan çıpa sessizce geçti: {out!r}"
    assert "head-2026-09-18.txt" in out, f"hangi çıpanın eksik olduğu yazılmalı: {out!r}"


# ── Koordinatör düzeltmesi: RUNBOOK §1.4 arşivlemesi kapıyı KALICI kırmızı yapıyordu ──
# `missing_anchors` yalnız üst düzeye (`directory.glob`) bakıyordu; RUNBOOK §1.4'ün MEŞRU
# arşivleme prosedürü (`ledger/head-*.txt` → `ledger/archive/`) çıpayı üst düzeyden
# kaldırıyor. Sonuç: dokümante edilmiş kurtarma adımının kendisi `verify-chain`'i
# kalıcı olarak kırmızıya düşürüyordu. Çözüm sessiz bir "var say" DEĞİL (bir saldırgan
# o zaman çıpayı silmek yerine TAŞIYARAK kontrolü atlatabilirdi) — arşivlenen çıpa
# ADIYLA raporlanır ("kanıt kapsamı daraldı") ama exit 1 VERMEZ; gerçekten hiçbir yerde
# olmayan çıpa hâlâ exit 1 verir.


def test_archived_anchor_is_not_reported_missing(tmp_path: Path) -> None:
    """RUNBOOK §1.4: `archive/`e TAŞINAN çıpa artık `missing_anchors`a düşmez, ama
    `archived_anchors` onu adıyla döner — kanıt kapsamının daraldığı iz bırakır."""
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    (archive_dir / "head-2026-09-18.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "head-2026-09-19.txt").write_text("x\n", encoding="utf-8")
    recorded = ("head-2026-09-18.txt", "head-2026-09-19.txt")

    assert missing_anchors(tmp_path, recorded=recorded) == ()
    assert archived_anchors(tmp_path, recorded=recorded) == ("head-2026-09-18.txt",)


def test_verify_chain_command_accepts_archived_anchor_without_failing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """RUNBOOK §1.4: arşivleme (TAŞIMA) meşrudur, silme değildir. Kanıt kapsamı daralır
    ve bu ADIYLA yazılır, ama dokümante edilmiş kurtarma adımı kapıyı kırmızı YAPMAZ.
    """
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    genuine = chained_rows(2)
    _write_anchor(
        tmp_path, rows=2, last_id=2, head=str(genuine[-1]["row_hash"]), name="head-2026-09-18.txt"
    )
    _write_anchor(
        tmp_path, rows=2, last_id=2, head=str(genuine[-1]["row_hash"]), name="head-2026-09-19.txt"
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.email=t@example.com", "-c", "user.name=t"]
        + ["commit", "-q", "-m", "iki çıpa"],
        check=True,
    )
    # RUNBOOK §1.4: "rm YOK, git rm YOK" — yalnız `ledger/archive/`e TAŞIMA.
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    (tmp_path / "head-2026-09-18.txt").rename(archive_dir / "head-2026-09-18.txt")

    code = _verify_chain_command(FakeChainDb(genuine), anchor_dir=tmp_path)  # type: ignore[arg-type]

    out = capsys.readouterr().out
    assert code == 0, f"arşivlenen (taşınan) çıpa kapıyı kırmızı vermemeli: {out!r}"
    assert "ÇIPA ARŞİVLENDİ" in out, f"kanıt kapsamının daraldığı yazılmalı: {out!r}"
    assert "head-2026-09-18.txt" in out, f"hangi çıpanın arşivlendiği yazılmalı: {out!r}"


def test_shallow_clone_skips_by_name_rather_than_passing_vacuously(tmp_path: Path) -> None:
    """Sığ klonda `git log` BAŞARILI olup boş döner — kontrol sessizce geçerdi.

    `actions/checkout` varsayılanı `fetch-depth: 1`. Boş liste dönmek, "hiç çıpa yok" ile
    "geçmişi göremiyorum"u aynı şeye indirger. İkincisi bir ATLAMADIR ve adıyla yazılır.
    """
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "ledger").mkdir()
    # Sığ olmayan taze depo: geçmiş var (boş), None DEĞİL boş demet beklenir.
    assert expected_anchor_names(tmp_path / "ledger") == ()


def test_actual_shallow_clone_is_recognized_and_skipped_by_name(tmp_path: Path) -> None:
    """Yukarıdaki test GERÇEK bir sığ klon üretmiyor: `git init` ile kurulan taze depo asla
    sığ olmaz. Sığ-klon korumasının (`--is-shallow-repository` kontrolünün) kendisini
    kanıtlamak için burada GERÇEKTEN sığ bir klon kurulur — kontrol geçici olarak devre
    dışı bırakılıp doğrulandı: onsuz bu dosyadaki 14 testin TAMAMI PASS veriyordu.
    """
    import subprocess

    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    (origin / "ledger").mkdir()
    (origin / "ledger" / "head-2026-09-01.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(origin), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(origin), "-c", "user.email=t@example.com", "-c", "user.name=t"]
        + ["commit", "-q", "-m", "anchor"],
        check=True,
    )
    shallow = tmp_path / "shallow"
    # `file://` şart: yerel bir YOL klonlanırken git `--depth`i SESSİZCE yok sayar
    # ("--depth is ignored in local clones") ve sonuç sığ OLMAZ — `file://` gerçek
    # git aktarım protokolünü zorlar.
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{origin}", str(shallow)], check=True
    )

    assert expected_anchor_names(shallow / "ledger") is None
