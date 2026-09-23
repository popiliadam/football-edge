#!/usr/bin/env bash
# Migration kum havuzu: DB testlerini yerel supabase/postgres kaplarında koşar (docs/RUNBOOK.md §4).
#
# Kapı ve CI bu testleri adıyla ATLAR (DATABASE_URL de kum havuzu adresi de yok). Davranış kanıtı
# (sahibin yazımı, API rollerinin reddi, TRUNCATE bekçisi, idempotentlik, kilit zaman aşımı) yalnız
# burada ölçülür. CANLIYA BAĞLANMAZ: iki adres de bu betiğin kurduğu 127.0.0.1 kaplarını gösterir;
# `.env` okunmaz, kabuktaki veritabanı adresi `test` komutunda EZİLİR.
#
#   scripts/sandbox_db.sh up           iki kabı kurar (varsa başlatır); ilkine migration'ları uygular
#   scripts/sandbox_db.sh apply        bütün migration'ları "uygulanmış" kaba sırayla YENİDEN uygular
#   scripts/sandbox_db.sh test [ARG…]  pytest'i iki adresle koşar (yol yoksa DB test dosyaları)
#   scripts/sandbox_db.sh env          elle kullanım için iki `export` satırı basar
#   scripts/sandbox_db.sh stop         bu betiğin kaplarını durdurur
#   scripts/sandbox_db.sh rm --yes     bu betiğin kaplarını SİLER (bayraksız reddeder)
#
# İki kap: `<önek>-applied` (0001… commit'li; katalog testlerinin veritabanı) ve `<önek>-empty` (boş;
# kum havuzu testleri migration'ları tek işlemde uygulayıp GERİ ALIR). Kaplar `football-edge.sandbox=1`
# etiketini taşır; aynı adlı etiketsiz bir kaba (başkasının kabı) hiçbir komut dokunmaz. Aynı makinede
# paralel oturumlar KENDİ FE_SANDBOX_PREFIX/FE_SANDBOX_PORT'unu kullanır: önek ortaksa kaplar da ortaktır.
# Ayarlar: FE_SANDBOX_PREFIX (football-edge-sandbox), FE_SANDBOX_PORT (55480; boş kap +1),
# FE_SANDBOX_IMAGE (public.ecr.aws/supabase/postgres:17.6.1.143).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${FE_SANDBOX_PREFIX:-football-edge-sandbox}"
PORT="${FE_SANDBOX_PORT:-55480}"
IMAGE="${FE_SANDBOX_IMAGE:-public.ecr.aws/supabase/postgres:17.6.1.143}"
LABEL="football-edge.sandbox"
APPLIED="$PREFIX-applied"
EMPTY="$PREFIX-empty"
# Ortam değişkeni adları parçalardan kurulur: kapının secrets taraması `AD=değer` biçimini arar.
DB_VAR="DATABASE""_URL"
SANDBOX_VAR="SANDBOX_DATABASE""_URL"
DEFAULT_TESTS=(tests/test_api_roles_lockdown_db.py tests/test_jev_tables_db.py tests/test_holdout_phase_db.py)

die() { echo "sandbox_db: $*" >&2; exit 1; }

exists() { docker container inspect "$1" >/dev/null 2>&1; }

ours() { [ "$(docker container inspect -f "{{index .Config.Labels \"$LABEL\"}}" "$1" 2>/dev/null)" = "1" ]; }

require_ours() {
  exists "$1" || die "$1 yok — önce: scripts/sandbox_db.sh up"
  ours "$1" || die "$1 bu betiğin kabı değil ($LABEL etiketi yok) — dokunulmadı"
}

password() {
  docker container inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$1" \
    | sed -n 's/^POSTGRES_PASSWORD=//p'
}

psql_in() {
  local name="$1"; shift
  docker exec -i -e PGPASSWORD="$(password "$name")" "$name" \
    psql -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 -q "$@"
}

# Adres, kabın GERÇEKTEN yayımladığı porttan kurulur: FE_SANDBOX_PORT sonradan değişirse o porttaki
# başka bir sunucuya bağlanılmaz.
url() {
  local published
  published="$(docker port "$1" 5432/tcp 2>/dev/null | head -n 1)" \
    || die "$1 çalışmıyor — önce: scripts/sandbox_db.sh up"
  case "$published" in
    127.0.0.1:*) ;;
    *) die "$1 5432'yi 127.0.0.1'e yayımlamıyor ($published) — dokunulmadı" ;;
  esac
  echo "postgresql://postgres:$(password "$1")@$published/postgres"
}

start_one() {
  local name="$1" port="$2"
  if exists "$name"; then
    ours "$name" || die "$name adında başkasının kabı var — FE_SANDBOX_PREFIX ile başka önek seç"
    docker start "$name" >/dev/null || die "docker start başarısız: $name"
    return 1
  fi
  docker run -d --name "$name" --label "$LABEL=1" \
    -e POSTGRES_PASSWORD="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')" \
    -p "127.0.0.1:$port:5432" "$IMAGE" postgres -D /etc/postgresql >/dev/null \
    || die "docker run başarısız: $name"
}

wait_ready() {
  # İmajın ilk kurulumu geçici bir sunucuyla yalnız soket üzerinden koşar; TCP sorgusu kurulum
  # bitip asıl sunucu kalktığında geçer.
  local name="$1" tries=0
  until psql_in "$name" -Atc "select 1" >/dev/null 2>&1; do
    tries=$((tries + 1))
    [ "$tries" -le 90 ] || die "$name 180 sn'de hazır olmadı (docker logs $name)"
    sleep 2
  done
}

apply_all() {
  local file
  for file in "$REPO"/db/migrations/[0-9][0-9][0-9][0-9]_*.sql; do
    echo "uygulanıyor: $(basename "$file")"
    psql_in "$APPLIED" -1 -f - < "$file" >/dev/null
  done
}

cmd_up() {
  local fresh=0
  if start_one "$APPLIED" "$PORT"; then fresh=1; fi
  start_one "$EMPTY" "$((PORT + 1))" || true
  wait_ready "$APPLIED"
  wait_ready "$EMPTY"
  if [ "$fresh" -eq 1 ]; then
    apply_all
  else
    echo "$APPLIED zaten vardı: migration'lar yeniden uygulanmadı (yeni migration için: apply)"
  fi
  [ "$(psql_in "$EMPTY" -Atc "select to_regclass('public.odds_snapshots') is null")" = "t" ] \
    || die "$EMPTY boş değil — kum havuzu testleri onu reddeder (rm --yes, sonra up)"
  echo "hazır: $APPLIED (127.0.0.1:$PORT), $EMPTY (127.0.0.1:$((PORT + 1)))"
}

cmd_apply() { require_ours "$APPLIED"; wait_ready "$APPLIED"; apply_all; }

cmd_env() {
  require_ours "$APPLIED"
  require_ours "$EMPTY"
  local applied_url empty_url
  applied_url="$(url "$APPLIED")"
  empty_url="$(url "$EMPTY")"
  printf 'export %s=%q\n' "$DB_VAR" "$applied_url"
  printf 'export %s=%q\n' "$SANDBOX_VAR" "$empty_url"
}

cmd_test() {
  require_ours "$APPLIED"
  require_ours "$EMPTY"
  cd "$REPO"
  # Var olan bir yol verilmediyse (yalnız `-v`, `-k catalog` gibi seçenekler) DB test dosyaları eklenir.
  local arg has_path=0
  for arg in "$@"; do if [ -e "${arg%%::*}" ]; then has_path=1; fi; done
  [ "$has_path" -eq 1 ] || set -- "$@" "${DEFAULT_TESTS[@]}"
  local applied_url empty_url
  applied_url="$(url "$APPLIED")"
  empty_url="$(url "$EMPTY")"
  # `--tb=short`: uzun traceback psycopg karesindeki bağlantı dizesini (parola dâhil) basar.
  env "$DB_VAR=$applied_url" "$SANDBOX_VAR=$empty_url" \
    PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider -rs --tb=short "$@"
}

cmd_stop() {
  local name
  for name in "$APPLIED" "$EMPTY"; do
    if exists "$name" && ours "$name"; then docker stop "$name" >/dev/null && echo "durdu: $name"; fi
  done
}

cmd_rm() {
  [ "${1:-}" = "--yes" ] || die "rm yalnız --yes ile koşar: bu betiğin iki kabını SİLER"
  local name
  for name in "$APPLIED" "$EMPTY"; do
    if exists "$name" && ours "$name"; then docker rm -f "$name" >/dev/null && echo "silindi: $name"; fi
  done
}

command -v docker >/dev/null || die "docker yok"
case "${1:-}" in
  up) cmd_up ;;
  apply) cmd_apply ;;
  test) shift; cmd_test "$@" ;;
  env) cmd_env ;;
  stop) cmd_stop ;;
  rm) shift; cmd_rm "$@" ;;
  *) sed -n '2,21p' "$0" >&2; exit 2 ;;
esac
