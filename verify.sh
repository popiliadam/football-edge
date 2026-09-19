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
step "paket-kurulu" env PYTHONPATH= uv run python -c \
  "import football_edge, sys; sys.stdout.write(football_edge.__file__ + chr(10))"

# Kaynak politikası ÇEVRİMDIŞI sorulur: ağ yok, secret yok, her push'ta koşar. Canlı sapmayı
# sources-audit.yml günde bir ölçer. Robots'u ölçmeden "izinli" demek, spec §3.2'yi prose'a
# geri çevirir; bu adım onu kuralda tutar.
step "kaynak-politikası" env PYTHONPATH= uv run python -m football_edge.collect sources-audit

# Veri sözleşmesi: toplayıcıların KAYDEDİLMİŞ fixture'ları üzerinde tazelik/şema iddiaları.
# Ağa çıkmaz — fixture'lar repoda. Canlı tazeliği snapshot turu ölçer; burada ölçülen,
# AYRIŞTIRICININ hâlâ beklenen şekli ürettiğidir.
#
# Task 4 sonunda `contract` marker'ını taşıyan HİÇBİR test yok — toplayıcılar (Task 5-8)
# ekleyecek. `pytest -m contract` eşleşme yokken exit 5 ("no tests collected") verir; bu
# FAIL DEĞİL, boş seçimdir. Ayrım burada AÇIKÇA yapılır — aksi hâlde exit 5 kapıyı yanlış
# sebepten kırmızı yapar ve gerçek bir arıza gibi okunur (bkz. qa-loop "SKIP geçmek
# değildir" ilkesi — burada tersi: BOŞ SEÇİM de arıza değildir, ama sessiz geçilmez).
#
# BU İZİN SÜRESİZ DEĞİL (review #7). "Bugün 0" iddiası SABİT KALIRSA, ileride marker
# yeniden adlandırılır / typo yapılır / bir collection hatası her şeyi deselect ederse
# yine exit 5 döner ve "boş seçim, hataya sayılmaz" YANLIŞ olur — kapı bakmayı bırakmış
# olur (`~/.claude/rules/qa-loop.md` Vaka 1: bir ay boyunca kapı yeşildi çünkü bakmıyordu).
# EXPECTED_MIN_CONTRACT bu iddianın kaydıdır: exit 5, "gerçekte toplanan test sayısı
# BUNUN ALTINDAYSA" değil, "exit 5 = toplanan 0" pytest'in kendi tanımıdır (resmî exit
# kodu belgesi) — yani 0 < EXPECTED_MIN_CONTRACT ancak biri bu sayıyı >0'a yükseltip
# (Task 5+ contract test eklerken KENDİ commit'inde yapar) sonra bir regresyon toplananı
# yeniden 0'a düşürürse doğru olur. O ana kadar (bugün) EXPECTED_MIN_CONTRACT=0 olduğu
# için bu kontrol bir NO-OP'tur — ama artık İLERİYE dönük, sessizce eskimiyor.
step "veri-sözleşmesi" bash -c '
  EXPECTED_MIN_CONTRACT=0

  uv run pytest tests/ -q -m contract
  code=$?

  if [ "$code" -eq 5 ]; then
    if [ "0" -lt "$EXPECTED_MIN_CONTRACT" ]; then
      echo "HATA: contract etiketli test sayısı (0) beklenen alt sınırın ($EXPECTED_MIN_CONTRACT) altında — boş seçim ARTIK GEÇERLİ DEĞİL, bir toplayıcı testi sessizce deselect ediliyor olabilir"
      exit 1
    fi
    echo "NOT: contract etiketiyle eşleşen test yok (boş seçim, beklenen alt sınır=$EXPECTED_MIN_CONTRACT karşılandı) — henüz hiçbir toplayıcı yok, hataya sayılmaz"
    exit 0
  fi
  exit "$code"
'

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
