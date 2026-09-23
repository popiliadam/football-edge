"""CI kapının secret adımını da koşmalı: depo PUBLIC, kaçan secret anında halka açılır.

`scripts/check_secrets.sh` yalnız `./verify.sh` içinde, yalnız YEREL koşuyordu (G6):
kapıyı elle koşmayan bir push taramadan geçmeden iner. Tarama ucuzdur, credential
istemez ve checkout'tan sonra her runner'da çalışır — CI'da koşmaması bir tercih değil,
bir boşluktu (HANDOFF §3.4/15).

Bu dosya iş akışlarının İÇERİĞİNİ okur, hiçbir adımı koşmaz; bir runner'da yeşil verdikleri
burada ölçülmez. Kabuk gövdelerini sahtelerle koşan testler `test_collect_workflows.py`
(toplama adımları) ve `test_seal_anchor_step.py`de (çıpa adımı).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from football_edge import collect
from tests.workflow_helpers import (
    COLLECTORS,
    REPO,
    SEAL,
    _allow_list,
    _dispatch_targets,
    _functions,
    _index_of,
    _migrations,
    _steps,
    _triggers,
)

WORKFLOWS = (
    REPO / ".github/workflows/snapshot.yml",
    REPO / ".github/workflows/seal.yml",
    REPO / ".github/workflows/collect-daily.yml",
    REPO / ".github/workflows/collect-news.yml",
)
SCAN_SCRIPT = "scripts/check_secrets.sh"


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
# `EXIT_SOURCE_FAILED = 7` (M7, 2026-09-19 merge) AYNI GEREKÇEYLE KASITLI OLARAK YOKTUR:
# `fetch-tff`/`fetch-venues`/`fetch-news` `seal.yml`/`snapshot.yml` tarafından HİÇ çağrılmaz
# (onları `collect-daily.yml`/`collect-news.yml` çağırır ve 7'yi orada adlandırır — bkz.
# `test_a_red_collector_*`). `_seal_run_body()`nin döndürdüğü metin bu yüzden 7'yi üretecek
# bir case arm'ı ASLA taşımaz; `fetch-results` ise `EXIT_LEAGUE_FAILED`ı (3, zaten listede)
# yeniden kullanıyor — bkz. `collect.py`'deki `EXIT_SOURCE_FAILED` yorumu ve
# `collectors.results.collect_results` docstring'i.
# `EXIT_LANGUAGE_UNCALIBRATED = 8` (Task 12, spec §5.4) AYNI GEREKÇEYLE KASITLI OLARAK
# YOKTUR (M-6, Faz 1 SON inceleme — bu yorum 8 eklendiğinde GÜNCELLENMEMİŞTİ, yalnız 6 ve 7'yi
# adlandırıyordu): `check-languages`/`calibrate` de `seal.yml`/`snapshot.yml` tarafından HİÇ
# çağrılmaz. `_seal_run_body()`nin döndürdüğü metin bu yüzden 8'i üretecek bir case arm'ı da
# ASLA taşımaz — bkz. `collect.py`'deki `EXIT_LANGUAGE_UNCALIBRATED` yorumu.
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


def _snapshot_run_body() -> str:
    step = next(
        step
        for step in _steps(REPO / ".github/workflows/snapshot.yml")
        if "football_edge.collect snapshot" in str(step.get("run", ""))
    )
    return str(step["run"])


# Aynı bağ `snapshot.yml` için. Bu liste de ELLE tutulur ve yalnız `football_edge.collect
# snapshot`un DÖNEBİLECEĞİ kodları taşır: 5 (kaçan mühür) yalnız `run_seal`den gelir.
# `EXIT_EMPTY_ROUND = 19` (boş tur bekçisi) bu listenin sebebidir: 19 `*)` dalına düşseydi
# "beklenmedik kod" derdi ve operatör sessiz arızayı milli aradan ayıran tek satırı göremezdi.
@pytest.mark.parametrize(
    ("code", "name"),
    [
        (collect.EXIT_QUOTA_EXHAUSTED, "kredi"),
        (collect.EXIT_LEAGUE_FAILED, "lig"),
        (collect.EXIT_MIRROR_FAILED, "ayna"),
        (collect.EXIT_EMPTY_ROUND, "fikstür"),
    ],
)
def test_snapshot_workflow_names_every_exit_code_the_collector_can_return(
    code: int, name: str
) -> None:
    body = _snapshot_run_body()
    arm = next((line for line in body.splitlines() if line.strip().startswith(f"{code})")), None)

    assert arm is not None, (
        f"snapshot.yml exit {code} için case arm'ı taşımıyor: '*)' dalına düşer ve "
        "operatör arızayı adıyla göremez"
    )
    assert "::error::" in arm, f"exit {code} arm'ı Actions'ta hata olarak görünmüyor: {arm!r}"
    assert name in arm, f"exit {code} arm'ı arızayı adlandırmıyor ({name!r} geçmiyor): {arm!r}"


# ── C1: CI kapıyı HİÇ koşmuyordu ────────────────────────────────────────────
# `.github/workflows/` yalnız `snapshot.yml` ve `seal.yml` taşıyordu, ikisi de
# `schedule` + `workflow_dispatch`. Yani projenin GERÇEK kapısı tek adımdı
# (`check_secrets.sh`), dokümantasyon ise yedi diyordu. Merge sonrası bozuk bir
# push 15 dakikalık mühür cron'una KAPISIZ ulaşır ve kalıcı, yanlış etiketli
# satırlar yazar — append-only: o satırlar silinemez.

CI = REPO / ".github/workflows/ci.yml"


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


def _contents_permission(value: Any) -> str | None:
    """Bir `permissions:` değerindeki `contents` düzeyini döner; blok yoksa `None`.

    #M10 (DEFERRED §9.2b, R56 ile kapatıldı): GitHub Actions `permissions:`i MAPPING
    (`{contents: read, ...}`) olarak da, skaler kısayol olarak da (`read-all`/`write-all` —
    her kapsama aynı düzey) kabul eder. Eski okuma yalnız mapping varsayıyordu; kısayol
    gelince `.get` ÇIPLAK bir `AttributeError` veriyordu, temiz bir assertion değil.
    Tanınmayan bir skaler olduğu gibi (dize olarak) döner — assertion onu adıyla raporlar.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        contents = value.get("contents")
        return None if contents is None else str(contents)
    return {"read-all": "read", "write-all": "write"}.get(str(value), str(value))


def test_full_scan_workflow_is_read_only() -> None:
    """Deftere YAZMAZ, yalnız okur — `seal.yml`nin `contents: write` yetkisine gerek yok.

    Yalnız iş akışı-seviyesi izne bakmak YETMEZ (I3): `seal.yml`deki gibi bir JOB kendi
    `permissions:` bloğuyla bunu genişletebilir ve üst düzey `contents: read` görünürken
    o job yine de yazabilir. İsim "salt-okunur" der; assertion yalnız üst düzeyi ölçerse
    bu genişletmeyi göremez ve isim ölçtüğünden fazlasını vaat eder.
    """
    document = yaml.safe_load(FULL_SCAN.read_text(encoding="utf-8"))

    assert _contents_permission(document.get("permissions")) == "read", (
        "full-scan.yml salt-okunur olmalı"
    )
    for name, job in document["jobs"].items():
        widened = _contents_permission(job.get("permissions"))
        assert widened in (None, "read"), (
            f"full-scan.yml: '{name}' job'ı contents iznini '{widened}'e genişletiyor"
        )


# ── Faz 1 SON inceleme, I-3: full-scan.yml'in concurrency YOKLUĞU tek koruma yorumdu ────────
# `full-scan.yml`deki `# concurrency: BİLİNÇLİ OLARAK YOK` yalnız bir YORUM: kod hiçbir şeyi
# ZORLAMIYORdu. Reviewer bunu dışa aktarılmış bir kopyada mutasyonla kanıtladı:
# `concurrency: {group: odds-collect}` eklenince 18 workflow testinin 18'i de YEŞİL kaldı.
# Grup paylaşılırsa GitHub, aynı gruptaki BEKLEYEN bir run'ı yenisi geldiğinde İPTAL EDER
# (bkz. full-scan.yml'in üst yorumu) — 30 dakikalık full-scan, 15 dakikada bir koşan mühür
# turlarından birini kuyruğa dizip iptal eder → `EXIT_MISSED_SEAL` → kapanış fiyatı KALICI
# kayıp (Faz 0'ın önlemek için var olduğu TEK sonuç). Bu, ertelenmiş bulgular içindeki TEK
# kalıcı veri kaybına giden yol (DEFERRED §9.2a).


def _group_of(concurrency: Any) -> str | None:
    """Bir `concurrency:` değerinin grup adını döner; blok yoksa `None`.

    `concurrency:` MAPPING (`{group: ..., cancel-in-progress: ...}`) olarak da, skaler
    kısayol olarak da (`concurrency: <grup adı>`) GEÇERLİDİR. Yalnız mapping varsayan bir
    okuma kısayolda `.get` çağırırken ÇIPLAK bir `AttributeError` verir — #M10'un
    permissions kısayolunda verdiği hatayla (`_contents_permission`, yukarıda) AYNI ŞEKİL,
    temiz bir assertion değil. Bu fonksiyon iki biçimi de okur.
    """
    if concurrency is None:
        return None
    if isinstance(concurrency, dict):
        group = concurrency.get("group")
        return None if group is None else str(group)
    return str(concurrency)  # skaler kısayol: değerin KENDİSİ grup adıdır


def _concurrency_groups(path: Path) -> frozenset[str]:
    """Bir workflow'un TÜM concurrency gruplarını döner: üst düzeydekini VE her job'unkini.

    GitHub `concurrency:`yi `jobs.<id>.concurrency` olarak da kabul eder ve iki düzeyin
    grupları AYNI depo-geneli ad uzayındadır: `odds-collect`i job düzeyinde bildiren bir
    workflow da bekleyen bir mühür turunu iptal ettirir. İlk sürüm yalnız üst düzeyi
    okuyordu ve bu biçim ondan kaçıyordu (yeniden inceleme, R62).
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = document.get("jobs") or {}
    blocks = (
        document.get("concurrency"),
        *(job.get("concurrency") for job in jobs.values() if isinstance(job, dict)),
    )
    return frozenset(group for group in map(_group_of, blocks) if group is not None)


def test_no_workflow_besides_seal_and_snapshot_shares_the_odds_collect_group() -> None:
    """`seal.yml`in kendi grubunu (`odds-collect`) `snapshot.yml` DIŞINDA hiçbir workflow
    paylaşmamalı. Yeni bir workflow (ör. `full-scan.yml`) bu gruba GİRERSE, bekleyen bir
    mühür turu sessizce iptal edilebilir — kapanış fiyatı bir daha OLUŞMAZ.

    Liste `.github/workflows/` altındaki `*.yml` VE `*.yaml` dosyalarından (GitHub ikisini
    de workflow sayar) DİNAMİK kurulur, sabit bir tuple DEĞİL: yeni bir workflow dosyası
    eklenip grup paylaşılırsa bu test onu OTOMATİK görür. Grup üst düzeyde YA DA herhangi bir
    job'da, mapping ya da skaler biçimde bildirilse yakalanır. Grup adı DİZE olarak
    karşılaştırılır: `${{ }}` ifadesiyle üretilen bir ad değerlendirilmez.
    """
    seal_groups = _concurrency_groups(SEAL)
    assert seal_groups, "seal.yml artık concurrency grubu taşımıyor — test bayatladı"

    directory = REPO / ".github/workflows"
    all_workflows = sorted((*directory.glob("*.yml"), *directory.glob("*.yaml")))
    sharing = tuple(
        path.name
        for path in all_workflows
        if path.name not in {"seal.yml", "snapshot.yml"} and _concurrency_groups(path) & seal_groups
    )

    assert sharing == (), (
        f"{sharing} seal.yml'in {sorted(seal_groups)} concurrency grubunu paylaşıyor — GitHub "
        "aynı gruptaki bekleyen bir run'ı yenisi geldiğinde İPTAL EDER; bir mühür turu kuyruktan "
        "düşerse kapanış fiyatı KALICI olarak kaybolur (EXIT_MISSED_SEAL)"
    )


# ── Tetikler pg_cron'da (db/migrations/) ─────────────────────────────────────────────────────
# GitHub'ın `schedule`ı 51 saatte ~203 tur yerine 16 tur koştu ve 47 maçın kapanış mührü kaçtı.
# Asıl tetik artık pg_cron → `workflow_dispatch`. İki uç birbirine yalnız bir dosya adıyla ve bir
# tetik adıyla bağlı: izinli listedeki bir workflow yeniden adlandırılırsa ya da
# `workflow_dispatch`i kaldırılırsa GitHub her çağrıyı reddeder ve o tur hiç koşmaz.

SNAPSHOT = REPO / ".github/workflows/snapshot.yml"
GITHUB_TOKEN_PATTERN = re.compile(r"github_pat_|gh[pousr]_[A-Za-z0-9]{20,}")


def test_every_workflow_pg_cron_may_dispatch_exists_and_accepts_a_bare_dispatch() -> None:
    """Dispatch yalnız `ref` gönderir: eksik tetik ya da zorunlu girdi o turu reddettirir."""
    targets = set().union(*map(_dispatch_targets, _migrations().values()))
    expected = {"seal.yml", "snapshot.yml", *(path.name for path in COLLECTORS)}
    assert expected <= targets, (
        f"izinli listede beklenen workflow yok: {sorted(expected - targets)}"
    )

    for name in sorted(targets):
        path = REPO / ".github/workflows" / name
        assert path.is_file(), f"pg_cron {name} tetikliyor ama workflow yok"
        triggers = _triggers(path)
        assert "workflow_dispatch" in triggers, f"{name}: pg_cron'un çağırdığı tetik kaldırılmış"
        inputs = (triggers["workflow_dispatch"] or {}).get("inputs") or {}
        required = sorted(key for key, spec in inputs.items() if (spec or {}).get("required"))
        assert required == [], f"{name}: dispatch zorunlu girdiyle reddedilir: {required}"


def test_every_dispatching_migration_targets_main_with_a_vault_token() -> None:
    dispatching = {name: sql for name, sql in _migrations().items() if "/dispatches" in sql}
    assert dispatching, "hiçbir migration workflow tetiklemiyor — test bayatladı"

    for name, sql in dispatching.items():
        assert "jsonb_build_object('ref', 'main')" in sql, f"{name}: varsayılan dala gitmiyor"
        assert "vault.decrypted_secrets" in sql, f"{name}: token Vault'tan okunmuyor"


def test_no_migration_carries_a_github_token() -> None:
    """Depo public ve `check_secrets.sh` GitHub token biçimini tanımıyor: bekçi bu test."""
    leaking = sorted(
        name for name, sql in _migrations().items() if GITHUB_TOKEN_PATTERN.search(sql)
    )

    assert leaking == [], f"migration'da GitHub token'ı: {leaking}"


def test_every_dispatch_wrapper_targets_the_allow_list_in_force() -> None:
    """`ops.dispatch_workflow` listede olmayan adı reddeder ve her tanım listeyi BAŞTAN yazar:
    yeni listeden düşen ya da hiç girmeyen bir workflow'un cron işi her turda hata verir, tur hiç
    koşmaz ve tek iz `cron.job_run_details`te kalır."""
    wrapped = {
        target
        for body in _functions().values()
        for target in re.findall(r"ops\.dispatch_workflow\('([\w.-]+)'\)", body)
    }
    expected = {"seal.yml", "snapshot.yml", *(path.name for path in COLLECTORS)}

    assert expected <= wrapped, f"sarmalayıcısı olmayan workflow: {sorted(expected - wrapped)}"
    assert wrapped <= _allow_list(), (
        f"izinli listede olmayan sarmalayıcı hedefi: {sorted(wrapped - _allow_list())}"
    )


def test_no_api_role_may_call_a_dispatch_function() -> None:
    """`ops` şeması API'ye zaten kapalı; fonksiyon düzeyindeki revoke ikinci katmandır. Postgres
    yeni fonksiyonun EXECUTE'unu PUBLIC'e verir: revoke unutulursa o katman sessizce yok olur."""
    sql = "\n".join(_migrations().values())
    exposed = sorted(
        name
        for name in _functions()
        if not re.search(
            rf"revoke all on function ops\.{name}\([^)]*\) from public, anon, authenticated;", sql
        )
    )

    assert exposed == [], f"API rollerinden geri alınmamış ops fonksiyonu: {exposed}"


def test_snapshot_is_triggered_by_pg_cron_alone() -> None:
    """İki tetik aynı gün iki tur, yani iki kat kredi demek. Tek tetik pg_cron'daki
    `snapshot-dispatch`; sessizce durmasına karşı koruma `seal.yml`deki bekçidir."""
    assert "schedule" not in _triggers(SNAPSHOT), "snapshot.yml GitHub'dan da tetikleniyor"

    scheduling = [
        name
        for name, sql in _migrations().items()
        if re.search(r"cron\.schedule\(\s*'snapshot-dispatch'[^;]*ops\.dispatch_snapshot\(\)", sql)
    ]
    assert scheduling, "snapshot.yml'i ne GitHub ne pg_cron zamanlıyor: tur hiç koşmaz"


def test_snapshot_dispatch_lands_between_two_seal_dispatches() -> None:
    """Mühür ve snapshot aynı `odds-collect` grubunda sıraya girer ve grup tek bir BEKLEYEN tur
    tutar: bir mühür dispatch'inin hemen ardından tetiklenen snapshot o turun arkasında bekler,
    kuyruğa giren üçüncü bir tur onu sessizce iptal ettirir. Snapshot iki mühür dispatch'inin
    ortasına düşmeli."""
    sql = "\n".join(_migrations().values())
    seal = re.search(r"cron\.schedule\(\s*'seal-dispatch',\s*'\*/(\d+) \* \* \* \*'", sql)
    snapshot = re.search(r"cron\.schedule\(\s*'snapshot-dispatch',\s*'(\d+) \d+ \* \* \*'", sql)
    assert seal is not None and snapshot is not None, "pg_cron zamanlamaları okunamadı"

    period, minute = int(seal.group(1)), int(snapshot.group(1))
    after_seal = minute % period
    assert period // 3 <= after_seal <= period - period // 3, (
        f"snapshot :{minute:02d}, bir mühür dispatch'inden {after_seal} dk sonra — kuyrukta "
        "onun arkasında bekler"
    )


# ── Kırmızı tur alarmı (scripts/ops_alert.py) ──────────────────────────────────────────────
# 15 kırmızı mühür turu iki gün fark edilmedi. Kırmızı tur `ops-alert` issue'su açar (açıksa
# gövdesini günceller), yeşil tur kapatır. Burada ölçülen, adımların VAR ve DOĞRU YERDE
# olduğudur; betiğin davranışı `tests/test_ops_alert.py`de.

# pg_cron'un tetiklediği turlara kimse bakmıyor: izinli listeye giren HER workflow alarm taşır.
ALARMED = tuple(REPO / ".github/workflows" / name for name in sorted(_allow_list()))


def _condition(step: dict[str, Any]) -> str:
    """Adımın `if:` ifadesi; varsa `${{ }}` sarmalı soyulmuş."""
    text = str(step.get("if", "")).strip()
    if text.startswith("${{") and text.endswith("}}"):
        return text[3:-2].strip()
    return text


def _alarm_steps(path: Path) -> tuple[list[dict[str, Any]], int | None, int | None]:
    steps = _steps(path)
    opens = _index_of(steps, f"scripts/ops_alert.py fail --workflow {path.stem} ")
    closes = _index_of(steps, f"scripts/ops_alert.py ok --workflow {path.stem} ")
    return steps, opens, closes


@pytest.mark.parametrize("path", ALARMED, ids=lambda path: path.name)
def test_red_run_opens_the_alarm_and_green_run_closes_it(path: Path) -> None:
    """`failure()`/`success()` yalnız ÖNCEKİ adımları görür: alarm adımları job'ın son iki
    adımıdır, yoksa sonrasına eklenen bir adımın kırmızısı alarmsız kalır. Zaman aşımı turu
    İPTAL eder ve `failure()` yanlış döner, bu yüzden alarm `cancelled()`da da açılır —
    kuyrukta beklerken iptal edilen tur hiç adım koşmaz, gürültü üretmez."""
    steps, opens, closes = _alarm_steps(path)

    assert (opens, closes) == (len(steps) - 2, len(steps) - 1), (
        f"{path.name}: alarm aç/kapat job'ın son iki adımı değil ({opens}, {closes})"
    )
    opens_on = {part.strip() for part in _condition(steps[opens]).split("||")}
    assert opens_on == {"failure()", "cancelled()"}, (
        f"{path.name}: alarm kırmızıda ya da zaman aşımında açılmıyor: {_condition(steps[opens])!r}"
    )
    assert _condition(steps[closes]) == "success()", f"{path.name}: alarm yeşilde kapanmıyor"
    for step in (steps[opens], steps[closes]):
        env = step.get("env") or {}
        assert env.get("GITHUB_TOKEN") == "${{ github.token }}", f"{path.name}: token yok"
        assert str(env.get("RUN_URL", "")).endswith("/actions/runs/${{ github.run_id }}"), (
            f"{path.name}: alarm kırmızı tura bağlanmıyor"
        )
        assert '--run-url "$RUN_URL"' in str(step["run"])


@pytest.mark.parametrize("path", ALARMED, ids=lambda path: path.name)
def test_only_the_closing_step_may_fail_without_turning_the_run_red(path: Path) -> None:
    """Yeşil turda `ok` düşerse (ör. GitHub 502) tur alarmsız kırmızıya dönerdi: `Alarm kapat`
    `continue-on-error` taşır. Başka HİÇBİR adım taşımaz — alarm açan ya da bekçi düşerse tur
    kırmızı kalmalı ki bozuk alarm yolu görünsün."""
    steps, _, closes = _alarm_steps(path)
    tolerant = [index for index, step in enumerate(steps) if step.get("continue-on-error")]

    assert closes is not None and tolerant == [closes], (
        f"{path.name}: continue-on-error taşıyan adımlar {tolerant}, beklenen yalnız [{closes}]"
    )
    assert steps[closes]["continue-on-error"] is True


@pytest.mark.parametrize("path", ALARMED, ids=lambda path: path.name)
def test_alarm_jobs_may_write_issues_and_read_runs(path: Path) -> None:
    """Job düzeyindeki `permissions:` üst düzeyi TAMAMEN ezer, listelenmeyen izin `none` olur:
    `contents` açıkça yazılmazsa checkout düşer. Yalnız seal `write` taşır: çıpa commit'i."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    (job,) = document["jobs"].values()
    permissions = job.get("permissions") or {}
    contents = "write" if path == SEAL else "read"

    assert permissions.get("issues") == "write", f"{path.name}: alarm issue açamaz"
    assert permissions.get("actions") == "read", f"{path.name}: turlar okunamaz"
    assert _contents_permission(permissions) == contents, f"{path.name}: contents izni değişti"


def _pushes(path: Path) -> bool:
    """Bir adım `git … push` koşuyor mu (`git -c … push` de sayılır, yorum satırı sayılmaz)."""
    return any(
        re.search(r"\bgit\b.*\bpush\b", line)
        for step in _steps(path)
        for line in str(step.get("run", "")).splitlines()
        if not line.lstrip().startswith("#")
    )


ALL_WORKFLOWS = tuple(sorted((REPO / ".github/workflows").glob("*.y*ml")))


@pytest.mark.parametrize("path", ALL_WORKFLOWS, ids=lambda path: path.name)
def test_only_a_pushing_workflow_keeps_the_checkout_token_on_disk(path: Path) -> None:
    """`actions/checkout` job token'ını varsayılan olarak `.git/config`e yazar; sonraki her adım
    (üçüncü taraf `setup-uv` eylemi dâhil) onu diskten okuyabilir. Push'lamayan workflow
    `persist-credentials: false` taşır — alarm adımları token'ı kendi `env`lerinden alır.
    Push'layan (seal'in çıpa commit'i) taşıyamaz: token diskte olmazsa push düşer."""
    checkouts = [
        step for step in _steps(path) if str(step.get("uses", "")).startswith("actions/checkout")
    ]
    on_disk = [
        str((step.get("with") or {}).get("persist-credentials", True)).lower() != "false"
        for step in checkouts
    ]

    assert checkouts, f"{path.name}: checkout adımı yok — test kurgusu bayatlamış"
    assert on_disk == [_pushes(path)] * len(checkouts), (
        f"{path.name}: push'luyor={_pushes(path)}, checkout token'ı diskte={on_disk}"
    )


def test_seal_runs_the_watchdog_on_its_backup_schedule_after_the_seal() -> None:
    """Bekçi pg_cron tetiklerini ölçer, bu yüzden GitHub'ın seyrek yedek `schedule`ında koşar:
    mühürden SONRA (mührü asla engellemez). Bayat tetikte kendi alarmını açar ve 0 döner; GitHub
    API'nin kendisi düşerse düşer ve seal alarmı açılır — alarm adımlarından ÖNCE olması bu
    yüzden. Ölü dispatch'in seyrek turları çoğunlukla zaten kırmızıdır (kaçan mühür); örtük
    `success()` bekçiyi tam o turlarda atlardı — `!cancelled()` bu yüzden."""
    steps = _steps(SEAL)
    seal = _index_of(steps, "football_edge.collect seal")
    watchdog = _index_of(steps, "scripts/ops_alert.py watchdog")
    alarm = _index_of(steps, "scripts/ops_alert.py fail")

    assert "schedule" in _triggers(SEAL), "yedek schedule yok: bekçi hiç koşmaz"
    assert watchdog is not None, "seal.yml bekçiyi koşmuyor"
    assert seal is not None and alarm is not None
    assert seal < watchdog < alarm, f"bekçinin yeri: mühür {seal}, bekçi {watchdog}, alarm {alarm}"
    condition = _condition(steps[watchdog])
    conjuncts = {part.strip() for part in condition.split("&&")}
    assert "||" not in condition and "github.event_name == 'schedule'" in conjuncts, (
        f"bekçi yalnız schedule turunda koşmuyor: {condition!r}"
    )
    assert "!cancelled()" in conjuncts, f"bekçi kırmızı mühür turunda atlanıyor: {condition!r}"
    env = steps[watchdog].get("env") or {}
    assert env.get("GITHUB_TOKEN") == "${{ github.token }}", "bekçiye token verilmiyor"
    assert str(env.get("RUN_URL", "")).endswith("/actions/runs/${{ github.run_id }}"), (
        "bekçi alarmı bekçi turuna bağlanmıyor"
    )
    assert '--run-url "$RUN_URL"' in str(steps[watchdog]["run"])
