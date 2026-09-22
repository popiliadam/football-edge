#!/usr/bin/env bash
# Mac'te günlük footystats turu (RUNBOOK §3.9). GitHub runner'ları footystats'tan 403 alıyor
# (DEFERRED 10r): Cloudflare veri merkezi IP'lerini geri çeviriyor, aynı kod ve kimlik buradan
# 200 alıyor. launchd koşturur (scripts/install_footystats_agent.py); elle de koşulabilir.
set -uo pipefail

: "${FOOTBALL_EDGE_CLONE:?işin kendi temiz klonu — geliştirme ağacı DEĞİL}"
: "${FOOTBALL_EDGE_ENV_FILE:?DATABASE_URL okunacak .env dosyası}"
: "${FOOTBALL_EDGE_LOG:?launchd bu işin çıktısını buraya yazar}"

WORKFLOW="footystats-local"
REPOSITORY="popiliadam/football-edge"

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S')" "$*"
}

# Alarm GitHub'da açılır. Bu iş bir runner'da koşmadığı için tur bağlantısı yok; issue'ya
# makine ve günlüğün yeri yazılır. Token yalnız bu sürecin ortamına verilir.
alarm() {
  local token
  if ! token="$(gh auth token 2>/dev/null)" || [ -z "$token" ]; then
    log "HATA: gh oturumu yok — alarm ($1) GitHub'a iletilemedi"
    return 1
  fi
  GITHUB_TOKEN="$token" GITHUB_REPOSITORY="$REPOSITORY" \
    uv run --frozen python scripts/ops_alert.py "$1" --workflow "$WORKFLOW" \
    --run-url "yerel launchd işi ($(uname -n)) — günlük: $FOOTBALL_EDGE_LOG"
}

fail() {
  log "HATA: $1"
  alarm fail
  exit "${2:-1}"
}

# Yalnız DATABASE_URL okunur: `.env`in geri kalanı (Odds anahtarı) bu işe gerekmez.
database_url() {
  local value
  value="$(sed -n 's/^DATABASE_URL=//p' "$FOOTBALL_EDGE_ENV_FILE" 2>/dev/null | head -n 1)"
  value="${value%\"}" && value="${value#\"}"
  value="${value%\'}" && value="${value#\'}"
  printf '%s' "$value"
}

cd "$FOOTBALL_EDGE_CLONE" || {
  log "HATA: klon yok: $FOOTBALL_EDGE_CLONE — alarm iletilemedi"
  exit 1
}
log "footystats yerel turu başlıyor"

# `main`in son hâli: iş incelenip birleşmiş kodu koşar. Çekilemezse eski kodla toplanmaz.
git fetch --quiet origin main || fail "git fetch düştü"
git checkout --quiet --detach FETCH_HEAD || fail "git checkout düştü"
log "kod: $(git rev-parse --short HEAD)"
uv sync --frozen --quiet || fail "uv sync düştü"

url="$(database_url)"
[ -n "$url" ] || fail "DATABASE_URL okunamadı: $FOOTBALL_EDGE_ENV_FILE"

DATABASE_URL="$url" uv run --frozen python -m football_edge.collect fetch-footystats
code=$?
[ "$code" -eq 0 ] || fail "fetch-footystats exit $code" "$code"

# Kapatma düşerse tur kırmızıya dönmez; açık alarm sonraki yeşil turda kapanır.
alarm ok || log "UYARI: alarm kapatılamadı — sonraki yeşil turda yeniden denenir"
log "footystats yerel turu tamam"
