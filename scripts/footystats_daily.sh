#!/usr/bin/env bash
# Mac'te günlük footystats turu (RUNBOOK §3.9). GitHub runner'ları footystats'tan 403 alıyor
# (DEFERRED 10r): Cloudflare veri merkezi IP'lerini geri çeviriyor, aynı kod ve kimlik buradan
# 200 alıyor. launchd günde dört kez ve oturum açılışında çağırır; UTC günü başına bir tur koşar,
# kaçan dilimi sonraki telafi eder (scripts/install_footystats_agent.py). Elle de koşulabilir.
set -uo pipefail

: "${FOOTBALL_EDGE_CLONE:?işin kendi temiz klonu — geliştirme ağacı DEĞİL}"
: "${FOOTBALL_EDGE_ENV_FILE:?DATABASE_URL okunacak .env dosyası}"
: "${FOOTBALL_EDGE_STAMP:?bugünün turunun koştuğunu işaretleyen dosya}"

REPOSITORY="popiliadam/football-edge"
REPORT="footystats-local.yml"
# Kurulu kopyanın mutlak yolu `cd`den ÖNCE çözülür: göreli bir çağrı yolu klonun içini gösterirdi.
INSTALLED="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
# Uykudan uyanınca ağ birkaç saniye yok olabilir: fetch birkaç kez denenir.
FETCH_ATTEMPTS=6
RETRY_DELAY="${FOOTBALL_EDGE_RETRY_DELAY:-10}"
# Takılan bir ağ launchd'nin sonraki çağrılarını da bekletirdi: ağa çıkan her adımın sınırı var.
GIT_NET=(git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60)
export UV_HTTP_TIMEOUT=60

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S')" "$*"
}

# Sonuç GitHub'daki rapor workflow'una gider (R74): alarmı github-actions kimliği açar ki bildirim
# gelsin (kişiye kendi eylemi için bildirim gitmez) ve her rapor bekçi için kalp atışıdır. GitHub
# token'ı bu betiğin hiçbir sürecine girmez: `gh` kendi oturumunu kullanır.
report() {
  if gh workflow run "$REPORT" --repo "$REPOSITORY" --ref main -f result="$1" >/dev/null 2>&1; then
    return 0
  fi
  log "HATA: sonuç ($1) GitHub'a iletilemedi — gh oturumu ya da ağ yok"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"footystats turu: $1 — GitHub'a iletilemedi\"\
 with title \"football-edge\"" >/dev/null 2>&1
  fi
  return 1
}

fail() {
  log "HATA: $1"
  report fail
  exit "${2:-1}"
}

# Yalnız DATABASE_URL okunur: `.env`in geri kalanı (Odds anahtarı) bu işe gerekmez.
database_url() {
  local value
  value="$(sed -n 's/^DATABASE_URL=//p' "$FOOTBALL_EDGE_ENV_FILE" 2>/dev/null | head -n 1)"
  value="${value%$'\r'}"
  value="${value%\"}" && value="${value#\"}"
  value="${value%\'}" && value="${value#\'}"
  printf '%s' "$value"
}

# Koşan kopya `main`in gerisindeyse kendini günceller; yeni sürüm SONRAKİ turdan geçerlidir.
# `mv` dizin girdisini değiştirir: koşan bash eski dosyayı okumayı sürdürür.
follow_main() {
  [ -f scripts/footystats_daily.sh ] || return 0
  cmp -s scripts/footystats_daily.sh "$INSTALLED" && return 0
  if cp scripts/footystats_daily.sh "$INSTALLED.new" && chmod 755 "$INSTALLED.new" &&
    mv -f "$INSTALLED.new" "$INSTALLED"; then
    log "betik main'e güncellendi — sonraki turdan geçerli"
  else
    log "UYARI: betik güncellenemedi: $INSTALLED"
  fi
}

today="$(date -u +%F)"
if [ "$(cat "$FOOTBALL_EDGE_STAMP" 2>/dev/null)" = "$today" ]; then
  log "bugünün (UTC $today) turu zaten koştu — atlandı"
  exit 0
fi
log "footystats yerel turu başlıyor"

if [ ! -d "$FOOTBALL_EDGE_CLONE/.git" ]; then
  log "klon yok, yeniden klonlanıyor: $FOOTBALL_EDGE_CLONE"
  "${GIT_NET[@]}" clone --quiet "https://github.com/$REPOSITORY.git" "$FOOTBALL_EDGE_CLONE" ||
    fail "git clone düştü"
fi
cd "$FOOTBALL_EDGE_CLONE" || fail "klona girilemedi: $FOOTBALL_EDGE_CLONE"

# `main`in son hâli: iş incelenip birleşmiş kodu koşar. Çekilemezse eski kodla toplanmaz ve
# damga yazılmaz — sonraki dilim yeniden dener.
attempt=1
until "${GIT_NET[@]}" fetch --quiet origin main; do
  [ "$attempt" -lt "$FETCH_ATTEMPTS" ] || fail "git fetch $FETCH_ATTEMPTS denemede de düştü"
  attempt=$((attempt + 1))
  sleep "$RETRY_DELAY"
done
git checkout --quiet --detach FETCH_HEAD || fail "git checkout düştü"
log "kod: $(git rev-parse --short HEAD)"
follow_main
uv sync --frozen --quiet || fail "uv sync düştü"

url="$(database_url)"
[ -n "$url" ] || fail "DATABASE_URL okunamadı: $FOOTBALL_EDGE_ENV_FILE"

DATABASE_URL="$url" uv run --frozen python -m football_edge.collect fetch-footystats
code=$?
# Toplayıcı koştuysa, sonucu ne olursa olsun bugünün denemesi budur (collect-daily gibi günde
# bir): kırmızı bir kaynak her dilimde yeniden istenmez.
mkdir -p "$(dirname "$FOOTBALL_EDGE_STAMP")" && printf '%s\n' "$today" >"$FOOTBALL_EDGE_STAMP" ||
  log "UYARI: damga yazılamadı: $FOOTBALL_EDGE_STAMP"
[ "$code" -eq 0 ] || fail "fetch-footystats exit $code" "$code"

# Rapor gitmezse veri yine toplanmıştır: tur yeşil kalır, eksik kalp atışını bekçi yakalar.
report ok || true
log "footystats yerel turu tamam"
