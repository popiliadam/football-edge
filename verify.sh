#!/usr/bin/env bash
# football-edge kapısı. Çıktı dosyaya yazılır; özet değil çıktı okunur.
set -uo pipefail

LOG="${TMPDIR:-/tmp}/football-edge-verify.log"
: > "$LOG"
FAILED=0

step() {
  local name="$1"; shift
  echo "=== $name ===" | tee -a "$LOG"
  if "$@" >>"$LOG" 2>&1; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    FAILED=1
  fi
}

# `scripts` HER ÜÇÜNE de dâhil (review R15): en yeni güvenlik-ilişkili dal (robots.txt
# canlı ölçümünün HTTP durum kararı) burada yaşıyordu ve kapının hiçbiri onu görmüyordu.
# `pytest` DIŞARIDA kalır — testler `tests/`de yaşar, `scripts/` betik değil test taşımaz.
step "ruff-check"  uv run ruff check src tests scripts
step "ruff-format" uv run ruff format --check src tests scripts
step "mypy"        uv run mypy src scripts
step "pytest"      uv run pytest -q

# Testler `pythonpath = ["src"]` ile koşar: KURULU PAKET BOZUK OLSA BİLE geçerler.
# CI ise `python -m football_edge.collect` ile kurulu paketi çağırır. PYTHONPATH'in
# boşaltılması kasıtlıdır — import'un src/'den değil kurulumdan geldiğini kanıtlar.
# Kırmızı verirse onarım `uv sync --reinstall-package football-edge`; kapı gevşetilmez.
# Faz 3: scipy'ın derlenmiş optimizer'ı da yüklenebilmeli (Dixon-Coles, havuz, seçim).
# Oturum 9 Task 3: Scrapling adaptörü (`football_edge.scrape`) `scrape` ekstrasına bağlı; kapı
# ekstrayla koşar (CI: `uv sync --frozen --extra scrape`, yerelde bir kez aynısı). Ekstra yoksa
# bu adım adıyla kırmızı verir — `uv run` ekstrayı kaldırmaz, düz `uv sync` kaldırır.
step "paket-kurulu" env PYTHONPATH= uv run python -c \
  "import football_edge, football_edge.scrape, scipy.optimize, sys; sys.stdout.write(football_edge.__file__ + chr(10))"

# Kaynak politikası ÇEVRİMDIŞI sorulur: ağ yok, secret yok, her push'ta koşar. Canlı sapmayı
# sources-audit.yml günde bir ölçer. Robots'u ölçmeden "izinli" demek, spec §3.2'yi prose'a
# geri çevirir; bu adım onu kuralda tutar.
step "kaynak-politikası" env PYTHONPATH= uv run python -m football_edge.collect sources-audit

# Veri sözleşmesi: toplayıcıların KAYDEDİLMİŞ fixture'ları üzerinde tazelik/şema iddiaları.
# Ağa çıkmaz — fixture'lar repoda. Canlı tazeliği snapshot turu ölçer; burada ölçülen,
# AYRIŞTIRICININ hâlâ beklenen şekli ürettiğidir.
#
# Task 4 sonunda `contract` marker'ını taşıyan HİÇBİR test yoktu; Task 5 (footystats)
# üçünü ekledi: test_parses_every_team_in_the_league,
# test_payload_carries_the_required_fields_in_plausible_ranges,
# test_entity_key_is_league_scoped_and_stable. `pytest -m contract` eşleşme yokken exit 5
# ("no tests collected") verir; bu FAIL DEĞİL, boş seçimdir. Ayrım burada AÇIKÇA yapılır —
# aksi hâlde exit 5 kapıyı yanlış sebepten kırmızı yapar ve gerçek bir arıza gibi okunur
# (bkz. qa-loop "SKIP geçmek değildir" ilkesi — burada tersi: BOŞ SEÇİM de arıza değildir,
# ama sessiz geçilmez).
#
# BU İZİN SÜRESİZ DEĞİL (review #7). "Bugün N" iddiası SABİT KALIRSA, ileride marker
# yeniden adlandırılır / typo yapılır / bir collection hatası bazılarını deselect ederse
# kapı bunu görmeli. EXPECTED_MIN_CONTRACT bu iddianın kaydıdır.
#
# İLK SÜRÜM (Task 5, R24) yalnız exit 5'i (TOPLANAN=0) kontrol ediyordu — Task 5 review
# #4: üç marker'dan YALNIZ BİRİ kaldırılınca (2 kaldı) pytest exit 0 verir ("2 passed, ...
# deselected"), `if code -eq 5` dalına hiç girilmez, EXPECTED_MIN_CONTRACT'e karşı HİÇBİR
# karşılaştırma yapılmaz — kapı yeşil kalırdı. Kırma-geri-yükleme kanıtı (aşağıdaki kod
# yorumu değil, task-5-report.md'nin fix-report bölümü) TÜM ÜÇ marker'ı birden kaldırdığı
# için yalnız exit-5 dalını kanıtlıyordu — bu bir TABAN(1) kanıtıydı, sayı(3) kanıtı değil.
#
# DÜZELTİLMİŞ SÜRÜM gerçek TOPLANAN sayıyı `--collect-only` ile ölçer — pytest'in kendi
# özet satırı ("N/M tests collected"), pass/fail durumundan BAĞIMSIZ, ayrıştırmaya
# (pass/fail metnini regex'le kesmeye) gerek bırakmaz. Sayı EXPECTED_MIN_CONTRACT'in
# ALTINDAYSA kapı kırmızı verir — pytest hiç ÇALIŞTIRILMADAN önce, exit kodu ne olursa
# olsun. Tek marker kaldırılarak (2 kaldı) kanıtlandı: kapı kırmızı verdi, marker geri
# eklenince yeşile döndü (task-5-report.md, fix-report).
# MERGE GÜNCELLEMESİ (M2, 2026-09-19): `uv run pytest -q -m contract` ile ÖLÇÜLDÜ — Task 5'in
# 3'ü artık 18. Task 6-9 (tff/venues+weather/haber/sonuç) kendi `contract` testlerini
# ekledi, sayı yeniden yükseltilmedi (dört paralel worktree birbirinin bu satırına
# DOKUNAMAZDI — sabit budur). Bu sabit YALNIZ bugünün ölçümünü taşır; yeniden ölçmeden
# büyütülmez, bkz. yukarıdaki "DÜZELTİLMİŞ SÜRÜM" notu — kırma/geri-yükleme kanıtı bu
# görevin raporundadır (task-M-report.md, "EXPECTED_MIN_CONTRACT break-and-restore proof").
step "veri-sözleşmesi" bash -c '
  EXPECTED_MIN_CONTRACT=18

  collect_output=$(uv run pytest tests/ -q -m contract --collect-only 2>&1)
  collect_code=$?
  if [ "$collect_code" -eq 5 ]; then
    collected=0
  else
    collected=$(printf "%s" "$collect_output" | grep -oE "^[0-9]+/" | head -1 | tr -d "/")
    collected=${collected:-0}
  fi

  if [ "$collected" -lt "$EXPECTED_MIN_CONTRACT" ]; then
    printf "%s\n" "$collect_output"
    echo "HATA: contract etiketli test sayısı ($collected) beklenen alt sınırın ($EXPECTED_MIN_CONTRACT) altında — bir toplayıcı testi sessizce deselect ediliyor olabilir"
    exit 1
  fi

  uv run pytest tests/ -q -m contract
  code=$?

  if [ "$code" -eq 5 ]; then
    echo "NOT: contract etiketiyle eşleşen test yok (boş seçim, beklenen alt sınır=$EXPECTED_MIN_CONTRACT karşılandı) — henüz hiçbir toplayıcı yok, hataya sayılmaz"
    exit 0
  fi
  exit "$code"
'

# Sızıntı (Faz 2 tasarımı §10): zaman semantiği, dönem ayrımı, kilit, bağlam/sonuç ayrımı.
# Veri-sözleşmesi adımının deseni: toplanan sayı --collect-only ile ölçülür ve alt sınırın
# altındaysa pytest hiç koşmadan kırmızı — bir `leakage` işareti sessizce düşerse kapı görür.
# Sabit yalnız ölçülerek büyütülür (Task 5, Task 12).
step "sızıntı" bash -c '
  EXPECTED_MIN_LEAKAGE=418

  collect_output=$(uv run pytest tests/ -q -m leakage --collect-only 2>&1)
  collect_code=$?
  if [ "$collect_code" -eq 5 ]; then
    collected=0
  else
    collected=$(printf "%s" "$collect_output" | grep -oE "^[0-9]+/" | head -1 | tr -d "/")
    collected=${collected:-0}
  fi

  if [ "$collected" -lt "$EXPECTED_MIN_LEAKAGE" ]; then
    printf "%s\n" "$collect_output"
    echo "HATA: leakage etiketli test sayısı ($collected) beklenen alt sınırın ($EXPECTED_MIN_LEAKAGE) altında"
    exit 1
  fi

  uv run pytest tests/ -q -m leakage
'

# Ölçülmemiş dil üretime alınamaz (spec §5.4, açık soru #4). Bu adım ağa çıkmaz, para
# harcamaz: yalnız `config/languages.yaml`'daki `production_enabled` bayraklarının bir
# kalibrasyon raporuyla desteklendiğini sorar (`calibration.language_config_violations`).
# Rapor yoksa ya da `production_ready()`yi geçmiyorsa bayrak açık olamaz. `calibrate`
# (gerçek Jev çağrısı, PARA HARCAR) kapının parçası DEĞİLDİR — Ruling R4, task-12-brief.
step "dil-kalibrasyonu" uv run python -m football_edge.collect check-languages

step "secrets"     ./scripts/check_secrets.sh

if [ -n "${DATABASE_URL:-}" ]; then
  step "zincir"    uv run python -m football_edge.collect verify-chain
else
  # SKIP GEÇMEK DEĞİLDİR. Atlanan kontrol adıyla yazılır — buraya sessiz bir
  # `true` konulursa kapı, hiç koşmamış bir doğrulamayı yeşil diye raporlar.
  echo "SKIP: zincir (DATABASE_URL yok)" | tee -a "$LOG"
fi

echo
echo "Tam çıktı: $LOG"
if [ "$FAILED" -ne 0 ]; then
  echo "KAPI KIRMIZI"
  exit 1
fi
echo "KAPI YEŞİL"
