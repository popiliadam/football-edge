#!/usr/bin/env bash
# Site kapısının Node adımları (spec §12.1, Plan B-2). `verify.sh` her alt komutu ayrı bir
# `step` olarak koşar. Burada SKIP YOKTUR: Node ya da pnpm yoksa ya da sürüm `.nvmrc` /
# `packageManager` ile uyuşmuyorsa adım FAIL'dir — site kapının parçasıdır.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$REPO/web"
# Next derlemesi varsayılan olarak anonim telemetri GÖNDERİR; kapı ağa yazmaz.
export NEXT_TELEMETRY_DISABLED=1

fail() {
  echo "HATA: $*"
  exit 1
}

toolchain() {
  local want_node want_pnpm have_node have_pnpm
  want_node="$(tr -d '[:space:]' < "$WEB/.nvmrc")"
  want_pnpm="$(sed -nE 's/.*"packageManager": *"pnpm@([0-9]+)\..*/\1/p' "$WEB/package.json")"
  have_node="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null)" || fail "node yok"
  have_pnpm="$(pnpm --version 2>/dev/null)" || fail "pnpm yok"
  have_pnpm="${have_pnpm%%.*}"
  [ "$have_node" = "$want_node" ] || fail "Node $have_node, .nvmrc $want_node istiyor"
  [ "$have_pnpm" = "$want_pnpm" ] || fail "pnpm $have_pnpm, packageManager $want_pnpm istiyor"
  echo "node $have_node · pnpm $have_pnpm"
}

# Her satır: ad|anlık görüntü|SITE_INDEXABLE. Uçtan uca varyantı verify.sh seçer (spec §12.1).
variants() {
  echo "fixture-full|$WEB/fixtures/snapshot.fixture.web-full.json|"
  echo "fixture-full-indexable|$WEB/fixtures/snapshot.fixture.web-full.json|1"
  echo "fixture-empty|$WEB/fixtures/snapshot.fixture.web-empty.json|"
  if [ -n "${SITE_E2E_SNAPSHOT:-}" ]; then
    echo "e2e|$SITE_E2E_SNAPSHOT|"
  fi
}

# Uçtan uca anlık görüntünün seçimi (spec §12.1 `site-derleme`): yalnız BU `verify.sh`
# koşusunun `site-db` adımının yazdığı dosya (`run-id` = FE_VERIFY_RUN_ID) kullanılır.
# Tek satır basar: `USE <yol>` · `SKIP <neden>` (yerel) · `FAIL <neden>` (CI=true, exit 1).
e2e() {
  local dir="${SITE_E2E_DIR:-${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e}"
  if [ -n "${FE_VERIFY_RUN_ID:-}" ] && [ -f "$dir/snapshot.json" ] \
    && [ "$(cat "$dir/run-id" 2>/dev/null)" = "$FE_VERIFY_RUN_ID" ]; then
    echo "USE $dir/snapshot.json"
  elif [ "${CI:-}" = "true" ]; then
    echo "FAIL CI=true ve bu koşunun uçtan uca anlık görüntüsü yok ya da bayat ($dir)"
    return 1
  else
    echo "SKIP bu koşunun uçtan uca anlık görüntüsü yok ya da bayat ($dir)"
  fi
}

build() {
  : "${SITE_BUILDS:?SITE_BUILDS tanımlı değil — verify.sh başta mktemp ile kurar}"
  local name snapshot flag sha
  while IFS='|' read -r name snapshot flag; do
    echo "--- $name: verify-snapshot"
    # Dışa aktarımın `snapshot.sha256`i yanındaysa (uçtan uca) dosya baytları da sınanır.
    sha="$(dirname "$snapshot")/snapshot.sha256"
    set -- "$snapshot"
    if [ -s "$sha" ]; then set -- "$snapshot" --sha256 "$sha"; fi
    (cd "$REPO" && uv run python -m football_edge.site verify-snapshot "$@") \
      || fail "anlık görüntü doğrulanmadı: $name"
    echo "--- $name: derleme (SITE_INDEXABLE=${flag:-yok})"
    SITE_SNAPSHOT="$snapshot" SITE_INDEXABLE="$flag" pnpm -C "$WEB" run build \
      || fail "derleme düştü: $name"
    mkdir -p "$SITE_BUILDS/$name"
    cp -R "$WEB/out/." "$SITE_BUILDS/$name/" || fail "çıktı kopyalanamadı: $name"
  done < <(variants)
}

check() {
  : "${SITE_BUILDS:?SITE_BUILDS tanımlı değil — verify.sh başta mktemp ile kurar}"
  local name snapshot flag failed=0
  while IFS='|' read -r name snapshot flag; do
    echo "--- $name: çıktı tarayıcısı"
    if [ ! -d "$SITE_BUILDS/$name" ]; then
      echo "HATA: $name derlenmemiş"
      failed=1
      continue
    fi
    SITE_INDEXABLE="$flag" node "$WEB/scripts/check-out.ts" \
      --snapshot "$snapshot" --out "$SITE_BUILDS/$name" || failed=1
  done < <(variants)
  return "$failed"
}

case "${1:-}" in
  toolchain) toolchain ;;
  e2e) e2e ;;
  install) toolchain && pnpm -C "$WEB" install --frozen-lockfile ;;
  build) build ;;
  check) check ;;
  *) fail "kullanım: $0 {toolchain|e2e|install|build|check}" ;;
esac
