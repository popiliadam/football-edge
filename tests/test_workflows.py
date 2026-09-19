"""CI kapının secret adımını da koşmalı: depo PUBLIC, kaçan secret anında halka açılır.

`scripts/check_secrets.sh` yalnız `./verify.sh` içinde, yalnız YEREL koşuyordu (G6):
kapıyı elle koşmayan bir push taramadan geçmeden iner. Tarama ucuzdur, credential
istemez ve checkout'tan sonra her runner'da çalışır — CI'da koşmaması bir tercih değil,
bir boşluktu (HANDOFF §3.4/15).

Bu dosya iş akışlarının İÇERİĞİNİ okur, koşmaz: runner'da gerçekten yeşil verdiği
ölçülmedi (workflow'lar hâlâ hiç koşmadı — HANDOFF §3.2).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from football_edge import collect

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = (
    REPO / ".github/workflows/snapshot.yml",
    REPO / ".github/workflows/seal.yml",
)
SCAN_SCRIPT = "scripts/check_secrets.sh"


def _steps(path: Path) -> list[dict[str, Any]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    (job,) = document["jobs"].values()
    return list(job["steps"])


def _index_of(steps: list[dict[str, Any]], needle: str, key: str = "run") -> int | None:
    for index, step in enumerate(steps):
        if needle in str(step.get(key, "")):
            return index
    return None


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_scans_for_secrets_before_the_paid_run(path: Path) -> None:
    """Tarama checkout'tan SONRA, toplayıcıdan ÖNCE koşmalı."""
    steps = _steps(path)
    checkout = _index_of(steps, "actions/checkout", key="uses")
    scan = _index_of(steps, SCAN_SCRIPT)
    collector = _index_of(steps, "football_edge.collect")

    assert scan is not None, f"{path.name} secret taramasını hiç koşmuyor"
    assert checkout is not None, "checkout adımı yok: git tabanlı tarama koşamaz"
    assert collector is not None, "iş akışı toplayıcıyı çağırmıyor — test kurgusu bayatlamış"
    assert checkout < scan, f"{path.name}: tarama checkout'tan önce, depo henüz yok"
    assert scan < collector, f"{path.name}: tarama ücretli/secret'lı adımdan sonra koşuyor"


# ── I4: seal.yml, toplayıcının verdiği her kodu ADIYLA karşılamalı ──────────
# Adı olmayan bir kod `*)` arm'ına düşer ve "beklenmedik kodla düştü" der: operatör
# kalıcı kaybolmuş bir kapanış fiyatını, bilinmeyen bir arızadan ayırt edemez.

SEAL = REPO / ".github/workflows/seal.yml"


def _seal_run_body() -> str:
    step = next(
        step for step in _steps(SEAL) if "football_edge.collect seal" in str(step.get("run", ""))
    )
    return str(step["run"])


# BU LİSTE ELLE TUTULUR — `collect`'in TÜM `EXIT_*` sabitlerinden otomatik türetilmez.
# Yalnız `football_edge.collect seal`in (yukarıdaki `_seal_run_body`) DÖNEBİLECEĞİ kodları
# taşır. Yeni bir `EXIT_*` sabiti eklemek bu listeyi OTOMATİK genişletmez — adı olmayan bir
# kod bunu sessizce geçer, kırmadan (bkz. Task 3 brief'in "Things the brief cannot know" §3).
# `EXIT_SOURCE_POLICY = 6` KASITLI OLARAK YOKTUR: `sources-audit` `seal`den TAMAMEN AYRI bir
# alt komuttur ve `seal.yml` onu hiç çağırmaz (yalnız `football_edge.collect seal` çalıştırır)
# — yani `_seal_run_body()`nin döndürdüğü metin 6'yı üretecek bir case arm'ı ASLA taşımaz;
# burada 6 için bir vaka eklemek var olmayan bir çağrıyı adlandırmış olurdu. `sources-audit`ı
# gerçekten çalıştıran iki yer (`verify.sh`, `sources-audit.yml`) case arm'ı taşımaz; ikisi de
# adımın çıkışını ham haliyle "adım başarılı/başarısız" diye okur — bkz. `collect.py`'deki
# `EXIT_SOURCE_POLICY` yorumu.
@pytest.mark.parametrize(
    ("code", "name"),
    [
        (collect.EXIT_QUOTA_EXHAUSTED, "kredi"),
        (collect.EXIT_LEAGUE_FAILED, "lig"),
        (collect.EXIT_MIRROR_FAILED, "ayna"),
        (collect.EXIT_MISSED_SEAL, "mühür"),
    ],
)
def test_seal_workflow_names_every_exit_code_the_collector_can_return(code: int, name: str) -> None:
    body = _seal_run_body()
    arm = next((line for line in body.splitlines() if line.strip().startswith(f"{code})")), None)

    assert arm is not None, (
        f"seal.yml exit {code} için case arm'ı taşımıyor: '*)' dalına düşer ve "
        "operatör arızayı adıyla göremez"
    )
    assert name in arm, f"exit {code} arm'ı arızayı adlandırmıyor ({name!r} geçmiyor): {arm!r}"


# ── C1: CI kapıyı HİÇ koşmuyordu ────────────────────────────────────────────
# `.github/workflows/` yalnız `snapshot.yml` ve `seal.yml` taşıyordu, ikisi de
# `schedule` + `workflow_dispatch`. Yani projenin GERÇEK kapısı tek adımdı
# (`check_secrets.sh`), dokümantasyon ise yedi diyordu. Merge sonrası bozuk bir
# push 15 dakikalık mühür cron'una KAPISIZ ulaşır ve kalıcı, yanlış etiketli
# satırlar yazar — append-only: o satırlar silinemez.

CI = REPO / ".github/workflows/ci.yml"


def _triggers(path: Path) -> dict[str, Any]:
    """Tetikleyicileri döner.

    PyYAML (YAML 1.1) `on:` anahtarını BOOLEAN True'ya çevirir — `document["on"]`
    KeyError verir. Bu tuzak sessizce "tetik yok" sonucunu üretir, o yüzden iki
    yazım da kabul edilir.
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(document.get("on") or document.get(True) or {})


def test_a_ci_workflow_exists_at_all() -> None:
    assert CI.is_file(), (
        "`.github/workflows/ci.yml` yok: kapı hiçbir push'ta koşmuyor, "
        "projenin gerçek kapısı tek adım (secret taraması)"
    )


@pytest.mark.parametrize("trigger", ["push", "pull_request"])
def test_ci_runs_the_gate_on_every_push_and_pull_request(trigger: str) -> None:
    assert trigger in _triggers(CI), (
        f"ci.yml `{trigger}` ile tetiklenmiyor — kapı yine yalnız zamanlanmış turlarda koşar"
    )


def test_ci_actually_runs_the_gate_script() -> None:
    """`./verify.sh` koşmayan bir CI, adı CI olan bir dosyadır."""
    assert _index_of(_steps(CI), "./verify.sh") is not None, "ci.yml kapıyı hiç koşmuyor"


def test_ci_checks_out_and_installs_before_running_the_gate() -> None:
    """Kapının `paket-kurulu` adımı KURULU paketi arar; `uv sync` olmadan düşer."""
    steps = _steps(CI)
    checkout = _index_of(steps, "actions/checkout", key="uses")
    sync = _index_of(steps, "uv sync")
    gate = _index_of(steps, "./verify.sh")

    assert checkout is not None, "checkout yok: git tabanlı secret taraması koşamaz"
    assert sync is not None, "`uv sync` yok: `paket-kurulu` adımı kurulu paketi bulamaz"
    assert gate is not None
    assert checkout < sync < gate, f"adım sırası yanlış: {checkout}, {sync}, {gate}"


def _env_keys(path: Path) -> set[str]:
    """Workflow/job/step seviyesindeki TÜM `env` anahtarları.

    Ham metin taraması burada yanlış cevap verir: bir secret'ın NEDEN verilmediğini
    anlatan yorum da `DATABASE_URL` yazar. C1'in bulunduğu yerin aynısı — `grep`
    tek eşleşme bulmuştu ve o da bir YORUMDU. Bu yüzden AYRIŞTIRILMIŞ belge okunur.
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    keys = set(document.get("env") or {})
    for job in document["jobs"].values():
        keys |= set(job.get("env") or {})
        for step in job["steps"]:
            keys |= set(step.get("env") or {})
    return keys


def test_ci_is_never_given_the_live_database() -> None:
    """CI CANLI DEFTERE DOKUNMAZ.

    `DATABASE_URL` verilirse kapının `zincir` adımı canlı deftere bağlanır ve her
    fork PR'ı üretim veritabanına erişmiş olur — defter append-only, her yazma
    kalıcı. Kapı secret'sız DOĞRU biçimde bozulur: `zincir` adımı ATLANDI'yı
    ADIYLA basar (atlanan kontrol geçmek değildir), geri kalan altı adım koşar.
    """
    bound = _env_keys(CI)

    assert "DATABASE_URL" not in bound, "ci.yml canlı deftere bağlanıyor"
    assert "ODDS_API_KEY" not in bound, "ci.yml ücretli API anahtarını taşıyor"


def test_ci_reads_no_repository_secret_at_all() -> None:
    """Bir sonraki mühendis `secrets.*` eklerse kapı kırmızı versin.

    Aranan şey İFADEDİR, çıplak kelime değil: kapının `secrets` adlı bir adımı var
    ve düz metin araması onu da yakalardı — C1'i gizleyen hatanın aynısı, yalnız
    ters yönde (yanlış alarm). Yanlış alarm da kaçırılan bulgu kadar zararlıdır.
    """
    expressions = re.findall(r"\$\{\{(.*?)\}\}", CI.read_text(encoding="utf-8"), flags=re.S)
    leaking = [text.strip() for text in expressions if "secrets" in text]

    assert leaking == [], (
        f"ci.yml depo secret'ı okuyor {leaking}: kapı her push'ta (fork PR'ları "
        "dâhil) üretim kimlik bilgilerine erişmiş olur"
    )


def test_the_scanned_script_exists_and_is_executable() -> None:
    """`run: ./scripts/check_secrets.sh` ancak dosya çalıştırılabilirse koşar."""
    script = REPO / SCAN_SCRIPT

    assert script.is_file(), f"{SCAN_SCRIPT} yok: iş akışı adımı ilk koşuda düşer"
    assert os.access(script, os.X_OK), f"{SCAN_SCRIPT} çalıştırılabilir değil"


# ── DEFERRED §1.1/§1.2: çıpa varken defterin İÇİ bir daha hash'lenmiyordu ────
# `seal.yml` yalnız en yeni çıpadan SONRAKİ kuyruğu tarar ve çıpalar hep ileri gider;
# aradaki satırlar hiçbir zamanlanmış koşuda doğrulanmayacaktı. Haftalık `full-scan.yml`
# bu boşluğu kapatır — `seal.yml`'e dokunulmadı, o hâlâ yalnız kuyruğu tarar (maliyet).

FULL_SCAN = REPO / ".github/workflows/full-scan.yml"


def test_full_scan_workflow_exists_and_is_scheduled() -> None:
    assert FULL_SCAN.is_file(), (
        "full-scan.yml yok: defterin içi hiçbir zamanlanmış turda yeniden hash'lenmiyor"
    )
    assert "schedule" in _triggers(FULL_SCAN), "full-scan.yml zamanlanmış koşmuyor"


# ── I2: yalnız zarfı değil, YÜKÜ de sına ────────────────────────────────────
# Önceki iki test dosyanın var olduğunu, zamanlanmış koştuğunu ve salt-okunur
# olduğunu ölçüyordu — ama HİÇBİRİ `--full`ün ya da `fetch-depth: 0`ın gerçekten
# orada olduğunu iddia etmiyordu. `--full` silinirse haftalık tarama sessizce
# TAIL-ONLY'e döner (bu görevin kapattığı boşluk yeniden açılır); `fetch-depth: 0`
# silinirse çıpa-eksikliği kontrolü HER haftalık koşuda kendini atlar — ikisi de
# yeşil bir kapıyla olurdu.


def test_full_scan_workflow_runs_full_verify_chain() -> None:
    assert _index_of(_steps(FULL_SCAN), "verify-chain --full") is not None, (
        "full-scan.yml --full'ü koşmuyor: haftalık tarama yalnız kuyruğu tarıyor olurdu"
    )


def test_full_scan_workflow_checks_out_full_history() -> None:
    """`fetch-depth: 0` olmadan çıpa-eksikliği kontrolü kendini atlar (full-scan.yml'in
    kendi yorumu bunu söylüyor: sığ klon geçmişi görmez)."""
    steps = _steps(FULL_SCAN)
    checkout = _index_of(steps, "actions/checkout", key="uses")

    assert checkout is not None, "full-scan.yml checkout adımı yok"
    assert steps[checkout].get("with", {}).get("fetch-depth") == 0, (
        "full-scan.yml tam geçmiş çekmiyor: çıpa-eksikliği kontrolü ATLANDI basar"
    )


def test_full_scan_workflow_is_read_only() -> None:
    """Deftere YAZMAZ, yalnız okur — `seal.yml`nin `contents: write` yetkisine gerek yok.

    Yalnız iş akışı-seviyesi izne bakmak YETMEZ (I3): `seal.yml`deki gibi bir JOB kendi
    `permissions:` bloğuyla bunu genişletebilir ve üst düzey `contents: read` görünürken
    o job yine de yazabilir. İsim "salt-okunur" der; assertion yalnız üst düzeyi ölçerse
    bu genişletmeyi göremez ve isim ölçtüğünden fazlasını vaat eder.
    """
    document = yaml.safe_load(FULL_SCAN.read_text(encoding="utf-8"))

    assert document.get("permissions", {}).get("contents") == "read", (
        "full-scan.yml salt-okunur olmalı"
    )
    for name, job in document["jobs"].items():
        widened = (job.get("permissions") or {}).get("contents")
        assert widened in (None, "read"), (
            f"full-scan.yml: '{name}' job'ı contents iznini '{widened}'e genişletiyor"
        )
