// Derleme SONRASI üretilen yayın dosyaları (spec §8.1, §11, AK19 a, AK20 b, AK21):
// `_headers` (CSP hash'leri, güvenlik başlıkları, bayrak kapalıyken X-Robots-Tag),
// `_redirects`, `data/slugs.json`, `data/snapshot.sha256`. Başlıklar TEK kaynaktan
// buradan gelir; `netlify.toml` başlık/yönlendirme taşımaz (B8).
import { createHash } from "node:crypto";
import { DEFAULT_LANG, SITE_LANGS } from "../../site.config.ts";
import { matchPath, matchStem } from "../../src/lib/routes.ts";
import type { Snapshot } from "../../src/lib/snapshot-types.ts";
import { cspHash, isExecutableInline, scripts } from "./html.ts";

export type PageHashes = { path: string; hashes: string[] };

export const SECURITY_HEADERS: readonly [string, string][] = [
  ["X-Content-Type-Options", "nosniff"],
  ["Referrer-Policy", "strict-origin-when-cross-origin"],
  ["Permissions-Policy", "camera=(), microphone=(), geolocation=()"],
];

export function inlineHashes(html: string): string[] {
  const hashes = scripts(html)
    .filter(isExecutableInline)
    .map((script) => cspHash(script.body));
  return [...new Set(hashes)].sort();
}

export function csp(hashes: readonly string[]): string {
  return [
    "default-src 'self'",
    `script-src 'self' ${hashes.join(" ")}`.trimEnd(),
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
  ].join("; ");
}

// CSP YALNIZ sayfa bloklarında: `/*` bloğunda ikinci bir CSP olsaydı tarayıcı ikisinin
// kesişimini uygular ve sayfa hash'leri geçersizleşirdi.
export function headersFile(pages: readonly PageHashes[], indexable: boolean): string {
  const global = [...SECURITY_HEADERS, ...(indexable ? [] : [["X-Robots-Tag", "noindex"]])];
  const blocks = [["/*", ...global.map(([name, value]) => `  ${name}: ${value}`)].join("\n")];
  for (const page of pages) {
    blocks.push(`${page.path}\n  Content-Security-Policy: ${csp(page.hashes)}`);
  }
  return `${blocks.join("\n\n")}\n`;
}

// Maç yolu kimlik taşır; isim bölütü değişirse eski URL zorlamasız 301 ile yeni yola
// gider. Güncel yol dosya olarak var olduğu için kural onu gölgelemez (spec §8.1).
export function redirectsFile(snapshot: Snapshot): string {
  const lines = [`/ /${DEFAULT_LANG}/ 301`];
  const leagues = new Map(snapshot.leagues.map((league) => [league.id, league]));
  for (const lang of SITE_LANGS) {
    for (const match of snapshot.matches) {
      const league = leagues.get(match.league_id);
      if (!league) throw new Error(`maçın ligi yok: ${match.id}`);
      lines.push(`${matchStem(lang, league, match)}* ${matchPath(lang, league, match)} 301`);
    }
  }
  return `${lines.join("\n")}\n`;
}

// Kaybolan-slug kontrolünün (AK20 b) deposu: bir sonraki yayın bununla karşılaştırılır.
export type SlugIndex = { version: 1; leagues: string[]; teams: string[] };

export function slugIndex(snapshot: Snapshot): SlugIndex {
  const slugOf = new Map(snapshot.leagues.map((league) => [league.id, league.slug]));
  return {
    version: 1,
    leagues: snapshot.leagues.map((league) => league.slug).sort(),
    teams: snapshot.teams.map((team) => `${slugOf.get(team.league_id)}/${team.slug}`).sort(),
  };
}

export function sha256Hex(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}
