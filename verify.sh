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
