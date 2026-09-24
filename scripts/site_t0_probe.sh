#!/usr/bin/env bash
# B-1 T0: CI'ın kuracağı kabın AYNISINI yerelde kurar ve B-1'in dayandığı varsayımları ölçer.
# Kaydı depoya (docs/phases/06-site/b1-t0-olcumler.md), ham çıktıyı scratch'e yazar. Kap durdurulur,
# SİLİNMEZ (`docker rm <ad>` kullanıcının kararıdır; ad `$FE_SANDBOX_PREFIX-site-t0`).
set -uo pipefail
SCRATCH="${1:?scratch dizini ver}"
IMAGE=public.ecr.aws/supabase/postgres:17.6.1.143
# Paralel oturumlar kum havuzu gibi KENDİ önek ve portunu kullanır (RUNBOOK §4); yeniden koşu
# durdurulmuş kabı başlatır. Her koşu yeni bir kapla ölçmek isterse FE_SITE_T0_NAME'i değiştirir.
PREFIX="${FE_SANDBOX_PREFIX:-football-edge-sandbox}"
NAME="${FE_SITE_T0_NAME:-$PREFIX-site-t0}"
PORT="${FE_SITE_T0_PORT:-55490}"
LABEL=football-edge.sandbox
REC=docs/phases/06-site/b1-t0-olcumler.md
RAW="$SCRATCH/t0-raw.log"
mkdir -p "$SCRATCH" docs/phases/06-site
: > "$RAW"
die() { echo "site_t0_probe: $*" | tee -a "$RAW" >&2; exit 1; }
password() {
  docker container inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$NAME" \
    | sed -n 's/^POSTGRES_PASSWORD=//p'
}
q() { docker exec -i -e PGPASSWORD="$PW" "$NAME" psql -h localhost -U postgres -At "$@"; }

docker pull "$IMAGE" >>"$RAW" 2>&1 || die "imaj çekilemedi: $IMAGE"
DIGEST="$(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGE" | sed 's/^.*@//')"
START=$(date +%s)
if docker container inspect "$NAME" >/dev/null 2>&1; then
  [ "$(docker container inspect -f "{{index .Config.Labels \"$LABEL\"}}" "$NAME")" = "1" ] \
    || die "$NAME adında başkasının kabı var — FE_SITE_T0_NAME ile başka ad seç"
  docker start "$NAME" >>"$RAW" 2>&1 || die "docker start başarısız: $NAME"
else
  docker run -d --name "$NAME" --label "$LABEL=1" \
    -e POSTGRES_PASSWORD="$(openssl rand -hex 16)" \
    -p "127.0.0.1:$PORT:5432" "$IMAGE" postgres -D /etc/postgresql >>"$RAW" 2>&1 \
    || die "docker run başarısız: $NAME (port $PORT dolu olabilir: FE_SITE_T0_PORT)"
fi
PW="$(password)"
until q -d postgres -c 'select 1' >/dev/null 2>&1; do
  # Hazır olmayan kapla ölçülmez: kayıt dosyası YAZILMADAN çıkılır (commit'li kayıt ezilmez).
  [ $(( $(date +%s) - START )) -lt 300 ] || die "kap 300 sn'de hazır olmadı (docker logs $NAME)"
  sleep 2
done
READY=$(( $(date +%s) - START ))
# Ölçülen tam sıra 0001→0013'tür (T0 0014'ten önce koşar); sonraki bir koşuda 0014+ dışarıda kalır.
FULL_SEQUENCE=()
for f in db/migrations/[0-9][0-9][0-9][0-9]_*.sql; do
  [ "$(basename "$f" | cut -c1-4)" -le 13 ] && FULL_SEQUENCE+=("$f")
done
VERSION="$(q -d postgres -c 'show server_version')"
ROLE="$(q -d postgres -F, -c "select rolsuper, rolcreatedb, rolcreaterole, rolbypassrls from pg_roles where rolname = 'postgres'")"
SELF_GRANT="$(q -d postgres -c 'show createrole_self_grant')"

# (i) 0001→0013 tek işlemde, postgres veritabanında, postgres rolüyle; sonra GERİ AL.
T=$(date +%s)
if { echo 'begin;'; for f in "${FULL_SEQUENCE[@]}"; do cat "$f"; echo; done
     echo "select 'jobs_in_tx=' || count(*) from cron.job;"; echo 'rollback;'; } \
   | q -d postgres -v ON_ERROR_STOP=1 >>"$RAW" 2>&1; then FULL=ok; else FULL=failed; fi
FULL_SECONDS=$(( $(date +%s) - T ))
CRON_GONE="$(q -d postgres -c "select to_regclass('cron.job') is null")"
POSTGRES_EMPTY="$(q -d postgres -c "select to_regclass('public.odds_snapshots') is null")"

# (ii) şablon: 0001 + 0002 + 0013 ayrı bir veritabanına; kopya; FORCE ile düşürme. Önceki koşudan
# kalmış olabilecek ölçüm veritabanları önce düşürülür (atılabilir kap, §4.4/4 deseni).
q -d postgres -c 'drop database if exists fe_t0_copy with (force)' >>"$RAW" 2>&1
q -d postgres -c 'drop database if exists fe_t0_tpl with (force)' >>"$RAW" 2>&1
q -d postgres -c 'create database fe_t0_tpl' >>"$RAW" 2>&1
TEMPLATE=ok
for f in 0001_init.sql 0002_sources.sql 0013_api_roles_lockdown.sql; do
  q -d fe_t0_tpl -v ON_ERROR_STOP=1 -1 -f - < "db/migrations/$f" >>"$RAW" 2>&1 || TEMPLATE="failed:$f"
done
if q -d postgres -c 'create database fe_t0_copy template fe_t0_tpl' >>"$RAW" 2>&1; then COPY=ok; else COPY=failed; fi
COPY_TABLES="$(q -d fe_t0_copy -c "select count(*) from pg_class where relnamespace = 'public'::regnamespace and relname in ('leagues', 'matches', 'odds_snapshots')")"
if q -d postgres -c 'drop database fe_t0_copy with (force)' >>"$RAW" 2>&1; then DROP=ok; else DROP=failed; fi
q -d postgres -c 'drop database fe_t0_tpl with (force)' >>"$RAW" 2>&1

# (iii) rol: CREATEROLE'lü postgres yarattığı role SET ROLE diyebiliyor mu, üyeliği kendine verebiliyor mu?
PROBE="$(q -d postgres -v ON_ERROR_STOP=0 2>&1 <<'SQL'
begin;
create role fe_t0_reader nologin noinherit;
alter role fe_t0_reader set default_transaction_read_only = on;
alter role fe_t0_reader set statement_timeout = '30s';
savepoint s;
set local role fe_t0_reader;
select 'became_without_grant=' || current_user;
rollback to savepoint s;
grant fe_t0_reader to postgres with inherit false, set true;
set local role fe_t0_reader;
select 'became_after_grant=' || current_user;
rollback;
SQL
)"
printf '%s\n' "$PROBE" >>"$RAW"
if printf '%s\n' "$PROBE" | grep -qx 'became_without_grant=fe_t0_reader'; then SET_ROLE=direct
elif printf '%s\n' "$PROBE" | grep -qx 'became_after_grant=fe_t0_reader'; then SET_ROLE=after_grant
else SET_ROLE=denied; fi

NETLIFY="$(npm view netlify-cli version 2>>"$RAW")"
docker stop "$NAME" >/dev/null

{
  echo "# Faz 6 İz B · B-1 T0 ölçümleri"
  echo
  echo "Üreten: plan \`docs/superpowers/plans/2026-09-24-faz6-iz-b-1-okuma-katmani.md\` Task 0; tarih $(date -u +%Y-%m-%dT%H:%MZ)."
  echo "Kap CI'ın kuracağı biçimde kuruldu (\`postgres -D /etc/postgresql\`, parola iş içinde üretildi; kap: $NAME)."
  echo "Sonraki görevler aşağıdaki \`anahtar=değer\` satırlarını OKUR (tahmin etmez); testler eşitliği sınar."
  echo
  echo '```'
  echo "image=$IMAGE"
  echo "image_digest=$DIGEST"
  echo "server_version=$VERSION"
  echo "ready_seconds=$READY"
  echo "postgres_super_createdb_createrole_bypassrls=$ROLE"
  echo "createrole_self_grant=${SELF_GRANT:-bos}"
  echo "full_sequence_one_transaction=$FULL"
  echo "full_sequence_seconds=$FULL_SECONDS"
  echo "cron_gone_after_rollback=$CRON_GONE"
  echo "postgres_db_empty_after_rollback=$POSTGRES_EMPTY"
  echo "template_0001_0002_0013=$TEMPLATE"
  echo "template_copy=$COPY"
  echo "template_copy_tables=$COPY_TABLES"
  echo "drop_database_force=$DROP"
  echo "set_role=$SET_ROLE"
  echo "netlify_cli=$NETLIFY"
  echo '```'
} > "$SCRATCH/b1-t0-olcumler.md"
mv "$SCRATCH/b1-t0-olcumler.md" "$REC"   # yalnız tam bir ölçüm kaydın yerine geçer
cat "$REC"
