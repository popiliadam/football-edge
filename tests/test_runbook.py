"""Çıpa kilitlenmesinin YAZILI bir kurtarma yolu var mı?

`verify-chain` exit 1 verince `publish-head` atlanır: yeni çıpa yazılmaz, en yeni çıpa
da donar — sistem bu hâlden kendi kendine ÇIKAMAZ. Meşru bir defter yeniden kurulumu
(dev reset, id kayması) de bu hâli tetikler.

Kapalı düşmek DOĞRU davranıştır ve öyle kalır: bir bypass bayrağı hem saldırganın hem
yorgun operatörün ilk uzanacağı şeydir. Eksik olan kod değil, PROSEDÜRDÜ (G2). Kapı bir
prosedürün doğruluğunu ölçemez; varlığını ve "sil" demediğini ölçebilir — runbook
silinirse ya da tarif "arşivle"den "sil"e dönerse bu iki test kırmızı verir.
"""

from __future__ import annotations

from pathlib import Path

RUNBOOK = Path(__file__).resolve().parent.parent / "docs/RUNBOOK.md"
PHASE_HANDOFF = Path(__file__).resolve().parent.parent / "docs/phases/00-kayit-altyapisi/HANDOFF.md"


def _runbook() -> str:
    assert RUNBOOK.is_file(), "docs/RUNBOOK.md yok: kilitlenmenin yazılı çıkışı da yok"
    return RUNBOOK.read_text(encoding="utf-8")


def test_runbook_explains_how_to_recognise_the_anchor_lockout() -> None:
    """Teşhis: operatör hangi çıktıyı görünce bu bölüme geleceğini bilmeli."""
    text = _runbook()

    assert "ÇIPA UYUŞMAZLIĞI" in text, "kilitlenmenin teşhis çıktısı yazılmamış"
    assert "publish-head" in text, "yeni çıpanın neden yazılmadığı yazılmamış"
    assert "kapalı" in text, "kontrollü kapanmanın KASITLI olduğu yazılmamış"


def test_runbook_recovery_archives_the_anchors_instead_of_deleting_them() -> None:
    """Kurtarma TAŞIMADIR: silinen çıpanın taşıdığı kanıt geri gelmez."""
    text = _runbook()

    assert "ledger/archive/" in text, "arşiv hedefi yazılmamış"
    assert "git mv" in text, "kurtarma adımı taşıma komutunu vermiyor"
    assert "SİLİNMEZ" in text, "silme yasağı adıyla yazılmamış"
    assert "gerekçe" in text, "arşivleme gerekçesinin kayda geçirileceği yazılmamış"


def test_phase_handoff_points_at_the_runbook() -> None:
    """Runbook, kimsenin bakmadığı bir dosyada durursa yok sayılır."""
    assert "RUNBOOK.md" in PHASE_HANDOFF.read_text(encoding="utf-8"), (
        "faz devir belgesi runbook'a hiç işaret etmiyor"
    )
