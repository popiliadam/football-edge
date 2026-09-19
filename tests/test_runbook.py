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

REPO = Path(__file__).resolve().parent.parent
RUNBOOK = REPO / "docs/RUNBOOK.md"
PHASE_HANDOFF = REPO / "docs/phases/00-kayit-altyapisi/HANDOFF.md"
DEFERRED = REPO / "docs/DEFERRED.md"


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


def test_runbook_covers_a_chain_broken_by_two_concurrent_writers() -> None:
    """C2: kilit koda girdi, ama ZATEN kırılmış bir defterin çıkışı yazılı değildi.

    Kilitsiz koşmuş her tur bu çatalı bırakmış olabilir ve çatal onarılamaz:
    append-only tetikleyici bozuk satırı sildirmez. Prosedür yoksa operatörün
    elinde kalan tek "çözüm" tetikleyiciyi kapatmaktır — ürünün iddiasını o an bitirir.
    """
    text = _runbook()

    assert "prev_hash zincire uymuyor" in text, "çatalın teşhis çıktısı yazılmamış"
    assert "DISABLE TRIGGER" in text, "tetikleyiciyi kapatma yasağı adıyla yazılmamış"
    assert "pg_advisory_xact_lock" in text, "önce SEBEBİN kapatılacağı yazılmamış"


def test_runbook_never_offers_deleting_the_broken_row() -> None:
    """Tek onarım yolu satırı silmektir ve o yol KAPALIDIR: yerine kesit prosedürü var."""
    text = _runbook()

    assert "DELETE" in text and "asla" in text.lower(), "silme yasağı yazılmamış"
    assert "rename" in text.lower(), "bozuk defterin silinmeyip yeniden adlandırılacağı yazılmamış"


def test_phase_handoff_points_at_the_runbook() -> None:
    """Runbook, kimsenin bakmadığı bir dosyada durursa yok sayılır."""
    assert "RUNBOOK.md" in PHASE_HANDOFF.read_text(encoding="utf-8"), (
        "faz devir belgesi runbook'a hiç işaret etmiyor"
    )


def test_the_deferred_ledger_is_tracked_and_pointed_at() -> None:
    """D2: karar kaydının tamamı `.superpowers/sdd/.gitignore` (`*`) altındaydı.

    Ertelenen her bulgu, her ruling, her bilinen ödünleşme orada duruyordu ve
    MERGE OLMAYACAKTI. İzlenen bir dosyaya taşındı; devir belgesi ona işaret
    etmezse Faz 1 onu yine bulamaz.
    """
    assert DEFERRED.is_file(), "docs/DEFERRED.md yok: ertelenen bulgular merge olmuyor"
    assert "DEFERRED.md" in PHASE_HANDOFF.read_text(encoding="utf-8"), (
        "faz devir belgesi ertelenen bulgular listesine hiç işaret etmiyor"
    )
