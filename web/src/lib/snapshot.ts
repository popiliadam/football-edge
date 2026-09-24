// Anlık görüntünün derleme anı okuyucusu. Node DB'ye bağlanmaz (H5): tek girdi,
// `SITE_SNAPSHOT` ortam değişkeninin gösterdiği JSON dosyasıdır. Varsayılan dosya YOK —
// yanlış ya da eksik yol adıyla düşer; sessizce fixture'a dönen bir derleme gerçek
// yayını sentetik veriyle üretebilirdi.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { RESERVED_LEAGUE_SLUGS, RESERVED_TEAM_SLUGS } from "../../site.config.ts";
import type { League, Match, Snapshot, Team } from "./snapshot-types.ts";

export class SnapshotError extends Error {}

function fail(message: string): never {
  throw new SnapshotError(`anlık görüntü reddedildi: ${message}`);
}

function unique(values: readonly string[], what: string): void {
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) fail(`${what} çakışıyor: ${value}`);
    seen.add(value);
  }
}

// Tam şema denetimi `verify-snapshot`in (Python, B-1) işidir. Burada yalnız sitenin
// YÖNLENDİRMESİNİN dayandığı değişmezler sınanır: çakışan yol iki kaydı tek sayfaya yazar.
export function parseSnapshot(text: string): Snapshot {
  const snapshot = JSON.parse(text) as Snapshot;
  if (snapshot.schema_version !== 1) fail(`schema_version ${String(snapshot.schema_version)}`);
  if (snapshot.value_badge !== null) fail("value_badge null değil (H3)");
  if (snapshot.analysis !== null) fail("analysis null değil (§8.6)");
  if (snapshot.matches.length === 0) fail("maç yok — dışa aktarıcı bunu zaten reddetmeliydi");
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
  unique(
    snapshot.matches.map((match) => `${match.league_id}/${match.path_id}`),
    "path_id",
  );
  const leagueIds = new Set(snapshot.leagues.map((league) => league.id));
  for (const match of snapshot.matches) {
    if (!leagueIds.has(match.league_id)) fail(`maçın ligi yok: ${match.id}`);
  }
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
