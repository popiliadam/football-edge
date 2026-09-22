from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger("football_edge.anchors")
ANCHOR_DIR = Path("ledger")
_ANCHOR_FIELDS = ("rows", "last_id", "head")


@dataclass(frozen=True)
class Anchor:
    path: Path
    rows: int
    last_id: int
    head: str


@dataclass(frozen=True)
class AnchorScan:
    """Okunabilen çıpalar (eskiden yeniye) ve okunamayan EN YENİ dosyanın adı.

    `downgraded` doluysa `readable[-1]` en yeni çıpa DEĞİLDİR: kontrol bir öncekine
    düşmüştür. Bu, sessizce yapılabilecek bir indirgeme değildir (G4).
    """

    readable: tuple[Anchor, ...]
    downgraded: Path | None


def _anchor_values(target: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def read_anchor(target: Path) -> Anchor | None:
    """Tek çıpa dosyasını okur; bozuksa traceback yerine adıyla uyarı verip None döner."""
    values = _anchor_values(target)
    if any(field not in values for field in _ANCHOR_FIELDS):
        LOGGER.warning("çıpa dosyası eksik alanlı (%s bekleniyor): %s", _ANCHOR_FIELDS, target)
        return None
    try:
        rows, last_id = int(values["rows"]), int(values["last_id"])
    except ValueError:
        LOGGER.warning("çıpa dosyasındaki sayılar okunamadı: %s", target)
        return None
    return Anchor(path=target, rows=rows, last_id=last_id, head=values["head"])


def _scan_anchors(directory: Path = ANCHOR_DIR) -> AnchorScan:
    """Çıpa dosyalarını ESKİDEN YENİYE okur; EN YENİSİ okunamadıysa adını ayrıca taşır.

    En yeni çıpa dosyası çalışma ağacındadır: defteri yeniden yazabilen biri onu da
    yeniden yazabilir. Eski dosyalar git geçmişine commit'lenmiştir; öneki yeniden
    yazılmış bir defteri gösteren tek kanıt onlardır. Bozuk dosya sessizce yutulmaz.
    """
    targets = tuple(sorted(directory.glob("head-*.txt")))
    found = tuple((target, read_anchor(target)) for target in targets)
    readable = tuple(anchor for _, anchor in found if anchor is not None)
    newest_unreadable = bool(found) and found[-1][1] is None
    return AnchorScan(readable=readable, downgraded=targets[-1] if newest_unreadable else None)


def _anchors(directory: Path = ANCHOR_DIR) -> tuple[Anchor, ...]:
    """Okunabilen tüm çıpalar, ESKİDEN YENİYE."""
    return _scan_anchors(directory).readable


def _latest_anchor(directory: Path = ANCHOR_DIR) -> Anchor | None:
    """En son yayınlanmış zincir çıpası; yoksa ya da okunamıyorsa None."""
    anchors = _anchors(directory)
    return anchors[-1] if anchors else None


def expected_anchor_names(directory: Path = ANCHOR_DIR) -> tuple[str, ...] | None:
    """Git geçmişine EKLENMİŞ çıpa dosyalarının adları; git yoksa None.

    Silinen çıpa, bozulan çıpadan sessizdir: `_scan_anchors` yalnız diskte duranı görür ve
    silme, RUNBOOK §1.4'teki meşru arşivlemeden ayırt edilemez (DEFERRED §1.3). Beklenen kümeyi
    DIŞARIDA tutmak gerekir; dışarısı zaten var — defterin dış kanıtı olan aynı git geçmişi.

    Komutlar `-C directory` ile SORULAN dizine bağlanır: `directory` argümanını yok sayıp
    süreç kök dizinindeki depoya bakan bir uygulama, `tmp_path` ile çağrıldığında sessizce
    GERÇEK depoyu ölçer ve test yanlış sebepten geçer.
    """
    try:
        # SIĞ KLON SESSİZ BİR GEÇİŞTİR: `actions/checkout` varsayılanı `fetch-depth: 1` ve
        # sığ bir depoda `git log` BAŞARILI olup boş liste döner. Boş liste "hiç çıpa
        # yayınlanmamış" ile "geçmişi göremiyorum"u aynı şeye indirger ve kontrol hiçbir
        # şey ölçmeden yeşil verir. Atlanan kontrol geçmek değildir — adıyla atlanır.
        shallow = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--is-shallow-repository"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        if shallow.stdout.strip() == "true":
            return None
        # Hiç commit'i olmayan (unborn HEAD) bir depoda `git log` HEAD'i çözemediği için
        # düşer — bu bir ATLAMA değil, GERÇEKTEN boş bir geçmiştir: depo sığ değil,
        # geçmiş görülebiliyor, içinde henüz hiçbir şey yok. `--verify -q` bunu fatal
        # basmadan, yalnız çıkış koduyla bildirir.
        head_exists = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--verify", "-q", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if head_exists.returncode != 0:
            return ()
        found = subprocess.run(
            [
                "git",
                "-C",
                str(directory),
                "log",
                "--diff-filter=A",
                "--name-only",
                "--format=",
                "--",
                ".",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    names = tuple(
        Path(line).name
        for line in found.stdout.splitlines()
        if line.strip() and Path(line).name.startswith("head-")
    )
    return tuple(sorted(set(names)))


def _anchor_names_anywhere(directory: Path) -> set[str]:
    """`directory` altında (alt dizinler DÂHİL) bulunan çıpa dosyalarının adları.

    RUNBOOK §1.4'ün MEŞRU kurtarma adımı `head-*.txt`i `directory/archive/`e TAŞIR:
    üst düzeyden kalkar ama dizinin ALTINDA durmaya devam eder. Yalnız üst düzeye
    bakan bir tarama (`directory.glob`), arşivlemeyi silmeden ayırt edemez — dokümante
    edilmiş kurtarma adımının kendisi kapıyı kalıcı kırmızı yapardı.
    """
    return {target.name for target in directory.rglob("head-*.txt")}


def missing_anchors(
    directory: Path = ANCHOR_DIR, *, recorded: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    """Geçmişte yayınlanmış, NE üst düzeyde NE DE arşivde (`directory` altında hiçbir
    yerde) bulunan çıpalar. Arşivlenen çıpa burada YOKTUR — bkz. `archived_anchors`."""
    expected = expected_anchor_names(directory) if recorded is None else recorded
    if expected is None:
        return ()
    present_anywhere = _anchor_names_anywhere(directory)
    return tuple(name for name in expected if name not in present_anywhere)


def archived_anchors(
    directory: Path = ANCHOR_DIR, *, recorded: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    """Geçmişte yayınlanmış, üst düzeyde YOK ama `directory` altında (RUNBOOK §1.4'teki
    `archive/` gibi) bulunan çıpalar.

    Bunları sessizce "var" saymak, bir saldırganın çıpayı SİLMEK yerine TAŞIYARAK
    kontrolü atlatmasına izin verirdi. Bunun yerine adıyla raporlanır: RUNBOOK §1.4
    zaten "arşivlenen çıpa kanıtı GÖTÜRÜR, bu bir kayıptır" diyor — bu fonksiyon o
    kaybı görünür kılar, `_verify_chain_command` onu SESSİZ bırakmaz (ama kırmızı da
    vermez: meşru bir prosedür kalıcı olarak kapıyı kilitlemez).
    """
    expected = expected_anchor_names(directory) if recorded is None else recorded
    if expected is None:
        return ()
    top_level = {target.name for target in directory.glob("head-*.txt")}
    present_anywhere = _anchor_names_anywhere(directory)
    return tuple(name for name in expected if name in present_anywhere and name not in top_level)
