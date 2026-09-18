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

step "ruff-check"  uv run ruff check src tests
step "ruff-format" uv run ruff format --check src tests
step "mypy"        uv run mypy src
step "pytest"      uv run pytest -q

echo
echo "Tam çıktı: $LOG"
if [ "$FAILED" -ne 0 ]; then
  echo "KAPI KIRMIZI"
  exit 1
fi
echo "KAPI YEŞİL"
