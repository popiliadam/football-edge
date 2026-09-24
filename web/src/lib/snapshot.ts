// Anlık görüntünün derleme anı okuyucusu. Node DB'ye bağlanmaz (H5): tek girdi,
// `SITE_SNAPSHOT` ortam değişkeninin gösterdiği JSON dosyasıdır. Varsayılan dosya YOK —
// yanlış ya da eksik yol adıyla düşer; sessizce fixture'a dönen bir derleme gerçek
// yayını sentetik veriyle üretebilirdi.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { RESERVED_LEAGUE_SLUGS, RESERVED_TEAM_SLUGS } from "../../site.config.ts";
import type { League, Match, Snapshot, Team } from "./snapshot-types.ts";

export class SnapshotError extends Error {}

type Json = Record<string, unknown>;

// Yol bölütü desenleri B-1 şemasınınkilerle AYNIDIR (`web/contract/snapshot.schema.json`:
// `$defs.slug`, maçın `path_id` ve `slug`ı); kopyanın eşitliğini tests/test_site_web_contract.py
// sınar. `..`, `/`, boş değer ve büyük harf (`Data` harf duyarsız dosya sisteminde `data/`dır)
// bu desenlere uymaz.
const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const PATH_ID = /^[0-9a-z]{12}$/;
const MATCH_SLUG = /^[a-z0-9]+(-[a-z0-9]+)*-vs-[a-z0-9]+(-[a-z0-9]+)*$/;

// Yayımlanmayan anahtarlar, HERHANGİ bir derinlikte: §4.3 kolonları (B-1
// `contract.FORBIDDEN_KEYS`) ve H3 — adında `model` ya da `value` geçen anahtar (`value_badge`
// dışında; B-1 `test_site_contract` kuralı). Eşitliği tests/test_site_web_contract.py sınar.
const FORBIDDEN_KEYS: readonly string[] = [
  "book_key",
  "bookmaker",
  "bookmaker_last_update",
  "is_closing",
  "ledger_id",
  "point",
  "prev_hash",
  "price",
  "row_hash",
];
const FORBIDDEN_FRAGMENTS: readonly string[] = ["model", "value"];
const ALLOWED_FRAGMENT_KEYS: readonly string[] = ["value_badge"];

function fail(message: string): never {
  throw new SnapshotError(`anlık görüntü reddedildi: ${message}`);
}

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function unique(values: readonly string[], what: string): void {
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) fail(`${what} çakışıyor: ${value}`);
    seen.add(value);
  }
}

function forbidden(key: string): boolean {
  if (FORBIDDEN_KEYS.includes(key)) return true;
  const lower = key.toLowerCase();
  return (
    !ALLOWED_FRAGMENT_KEYS.includes(key) && FORBIDDEN_FRAGMENTS.some((part) => lower.includes(part))
  );
}

// Bütün belge: her sayı sonlu (`1e400` JS'te `Infinity`dir), yasak anahtar hiçbir derinlikte yok.
function scan(value: unknown, at: string): void {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) fail(`${at}: sonlu olmayan sayı`);
  } else if (Array.isArray(value)) {
    for (const [index, item] of value.entries()) scan(item, `${at}[${index}]`);
  } else if (isObject(value)) {
    for (const [key, sub] of Object.entries(value)) {
      if (forbidden(key)) fail(`${at}.${key}: yayımlanmayan anahtar (§4.3, H3)`);
      scan(sub, `${at}.${key}`);
    }
  }
}

function parseJson(text: string): unknown {
  let root: unknown;
  try {
    root = JSON.parse(text);
  } catch (error) {
    fail(`JSON değil (${(error as Error).message})`);
  }
  scan(root, "$");
  return root;
}

function objects(value: unknown, what: string): Json[] {
  if (!Array.isArray(value)) fail(`${what} dizi değil`);
  value.forEach((item, index) => {
    if (!isObject(item)) fail(`${what}[${index}] nesne değil`);
  });
  return value as Json[];
}

function label(row: Json, key: string, at: string): void {
  const value = row[key];
  if (typeof value !== "string" || value === "") fail(`${at}.${key} metin değil`);
}

function segment(row: Json, key: string, pattern: RegExp, at: string): void {
  const value = row[key];
  if (typeof value !== "string" || !pattern.test(value)) {
    fail(`${at}.${key} yol bölütü biçiminde değil: ${JSON.stringify(value)}`);
  }
}

// Yapı: yönlendirmenin okuduğu diziler ve alanlar var ve doğru biçimde; bozuk girdi
// `TypeError` ile değil adıyla düşer.
function checkShape(root: unknown): Snapshot {
  if (!isObject(root)) fail("kök nesne değil");
  objects(root.leagues, "leagues").forEach((league, index) => {
    label(league, "id", `leagues[${index}]`);
    segment(league, "slug", SLUG, `leagues[${index}]`);
  });
  objects(root.teams, "teams").forEach((team, index) => {
    for (const key of ["league_id", "name"]) label(team, key, `teams[${index}]`);
    segment(team, "slug", SLUG, `teams[${index}]`);
  });
  objects(root.matches, "matches").forEach((match, index) => {
    for (const key of ["id", "league_id", "home", "away"]) label(match, key, `matches[${index}]`);
    segment(match, "path_id", PATH_ID, `matches[${index}]`);
    segment(match, "slug", MATCH_SLUG, `matches[${index}]`);
  });
  if (!isObject(root.record)) fail("record nesne değil");
  objects(root.record.entries, "record.entries");
  return root as unknown as Snapshot;
}

// Çakışan ya da ayrılmış yol iki kaydı tek sayfaya yazar; bilinmeyen lig sayfasız kayıt bırakır.
function checkRouting(snapshot: Snapshot): void {
  for (const league of snapshot.leagues) {
    if (RESERVED_LEAGUE_SLUGS.includes(league.slug)) fail(`ayrılmış lig slug'ı: ${league.slug}`);
  }
  for (const team of snapshot.teams) {
    if (RESERVED_TEAM_SLUGS.includes(team.slug)) fail(`ayrılmış takım slug'ı: ${team.slug}`);
  }
  unique(
    snapshot.leagues.map((league) => league.slug),
    "lig slug'ı",
  );
  unique(
    snapshot.teams.map((team) => `${team.league_id}/${team.slug}`),
    "takım slug'ı",
  );
  // Küresel: `verify-snapshot` ile aynı değişmez (yol ligi taşısa da kimlik öneki tekildir).
  unique(
    snapshot.matches.map((match) => match.path_id),
    "path_id",
  );
  const leagueIds = new Set(snapshot.leagues.map((league) => league.id));
  for (const match of snapshot.matches) {
    if (!leagueIds.has(match.league_id)) fail(`maçın ligi yok: ${match.id}`);
  }
  for (const team of snapshot.teams) {
    if (!leagueIds.has(team.league_id)) fail(`takımın ligi yok: ${team.slug}`);
  }
}

// Tam şema denetimi `verify-snapshot`in (Python, B-1) işidir; bu okuyucu şemanın kopyası
// DEĞİLDİR. Burada yalnız sitenin YÖNLENDİRMESİNİN ve güvenliğinin dayandığı değişmezler
// sınanır: yapı, yol bölütü biçimi, çakışma, sonlu sayı, yayımlanmayan anahtar, H3 yuvaları.
export function parseSnapshot(text: string): Snapshot {
  const snapshot = checkShape(parseJson(text));
  if (snapshot.schema_version !== 1) fail(`schema_version ${String(snapshot.schema_version)}`);
  if (snapshot.value_badge !== null) fail("value_badge null değil (H3)");
  if (snapshot.analysis !== null) fail("analysis null değil (§8.6)");
  if (snapshot.matches.length === 0) fail("maç yok — dışa aktarıcı bunu zaten reddetmeliydi");
  checkRouting(snapshot);
  const { record } = snapshot;
  if (record.published !== record.entries.length) fail("record.published ≠ girdi sayısı");
  if ((record.published === 0) !== (record.summary === null)) fail("record.summary tutarsız");
  return snapshot;
}

let cached: Snapshot | undefined;

export function loadSnapshot(env: Record<string, string | undefined> = process.env): Snapshot {
  if (cached) return cached;
  const path = env.SITE_SNAPSHOT;
  if (!path) fail("SITE_SNAPSHOT tanımlı değil");
  cached = parseSnapshot(readFileSync(resolve(path), "utf-8"));
  return cached;
}

export function leagueById(snapshot: Snapshot, id: string): League {
  return snapshot.leagues.find((league) => league.id === id) ?? fail(`lig yok: ${id}`);
}

export function teamsOf(snapshot: Snapshot, league: League): Team[] {
  return snapshot.teams.filter((team) => team.league_id === league.id);
}

export function matchesOf(snapshot: Snapshot, league: League): Match[] {
  return snapshot.matches.filter((match) => match.league_id === league.id);
}

export function matchesOfTeam(snapshot: Snapshot, team: Team): Match[] {
  return snapshot.matches.filter(
    (match) =>
      match.league_id === team.league_id && (match.home === team.name || match.away === team.name),
  );
}

export function teamByName(snapshot: Snapshot, leagueId: string, name: string): Team | undefined {
  return snapshot.teams.find((team) => team.league_id === leagueId && team.name === name);
}
