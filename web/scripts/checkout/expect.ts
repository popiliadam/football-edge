// Çıktı tarayıcısının BEKLENTİLERİ, sayfa kodundan bağımsız kurulur (spec §5.3): sayfa
// hangi alanı basarsa bassın, burada anlık görüntüden türetilen küme karşılaştırılır.
// Paylaşılan tek şeyler URL şeması (routes.ts), biçim (format.ts) ve arayüz sözlüğü
// (etiket metinleri) — üçü de kendi birim testleriyle sınanır.
import { type Lang, LEGAL_DOCS, SITE_LANGS } from "../../site.config.ts";
import { t } from "../../src/i18n/dict.ts";
import type { NumberKind } from "../../src/lib/format.ts";
import {
  homePath,
  leaguePath,
  legalPath,
  matchPath,
  teamPath,
  trackRecordPath,
} from "../../src/lib/routes.ts";
import type { League, Match, Snapshot } from "../../src/lib/snapshot-types.ts";

export type PageKind = "home" | "league" | "team" | "match" | "track-record" | "legal";
export type ExpectedPage = {
  path: string;
  lang: Lang;
  kind: PageKind;
  id: string; // `data-fe-page` değeri
  recordIndexable: boolean;
  fields: string[]; // beklenen `data-fe` anahtarları
  ldTypes: string[]; // beklenen JSON-LD `@type` kümesi
  paths: Record<Lang, string>; // aynı kaydın her dildeki yolu (hreflang)
};
export type FieldKind = NumberKind | "text" | "attr";

const ROUNDS = ["opening", "latest", "closing"] as const;
const SIDES = ["home", "draw", "away"] as const;

// Anahtar → biçim. Tabloda olmayan anahtar bulgudur.
const FIELD_KINDS: readonly [string, RegExp, FieldKind][] = [
  ["match", /^h2h\.(opening|latest|closing)\.p\.(home|draw|away)$/, "pct1"],
  ["match", /^h2h\.(opening|latest|closing)\.books$/, "int"],
  ["match", /^move\.(home|draw|away)$/, "pp1"],
  ["match", /^rounds$/, "int"],
  ["match", /^sealed$/, "attr"],
  ["league", /^matches$/, "int"],
  ["league", /^move_distribution\.(p10|p50|p90)$/, "pp1"],
  ["team", /^matches$/, "int"],
  ["ledger", /^(rows|last_id|anchor\.rows|anchor\.last_id)$/, "int"],
  ["ledger", /^(head|anchor\.head|anchor\.file)$/, "text"],
  ["record", /^(published|summary\.n)$/, "int"],
  ["record", /^summary\.(mean_clv|ci_low|ci_high)$/, "pct2"],
  ["entry", /^(published_price|closing_fair_price)$/, "price2"],
  ["entry", /^clv$/, "pct2"],
  ["entry", /^publication_ledger_id$/, "int"],
  ["entry", /^(market|publication_hash)$/, "text"],
  ["entry", /^outcome$/, "attr"],
  ["root", /^content_sha256$/, "text"],
];

// Anahtar TAM üç bölüttür (`varlık:kimlik:yol`); kimliğinde `:` taşıyan anahtar başka bir
// kaydın anahtarıyla çakışabilir, bu yüzden çözülmez (T3 carry-in 13).
function parts(key: string): [string, string, string] | undefined {
  const split = key.split(":");
  return split.length === 3 ? [split[0] ?? "", split[1] ?? "", split[2] ?? ""] : undefined;
}

export function fieldKind(key: string): FieldKind | undefined {
  const [entity, , path] = parts(key) ?? ["", "", ""];
  return FIELD_KINDS.find(([owner, pattern]) => owner === entity && pattern.test(path))?.[2];
}

function dig(value: unknown, path: string): unknown {
  let current = value;
  for (const part of path.split(".")) {
    if (current === null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

// `varlık:kimlik:yol` → anlık görüntüdeki değer; çözülemezse `undefined`.
export function resolveField(snapshot: Snapshot, key: string): unknown {
  const split = parts(key);
  if (split === undefined) return undefined;
  const [entity, id, path] = split;
  const owners: Record<string, unknown> = {
    match: snapshot.matches.find((match) => match.id === id),
    league: snapshot.leagues.find((league) => league.id === id),
    team: snapshot.teams.find((team) => `${team.league_id}/${team.slug}` === id),
    ledger: id === "-" ? snapshot.ledger : undefined,
    record: id === "-" ? snapshot.record : undefined,
    entry: snapshot.record.entries.find((entry) => String(entry.publication_id) === id),
    root: id === "-" ? snapshot : undefined,
  };
  return dig(owners[entity], path);
}

// Değeri metin olarak basılmayan (`attr`) alanın GÖRÜNEN etiketi (T5 carry-in 4, T6 carry-in 6):
// mühür durumu sözlükten, sonuç `draw` ise sözlükten, değilse maçın o taraftaki takım adı.
export function expectedLabel(snapshot: Snapshot, key: string, lang: Lang): string | undefined {
  const split = parts(key);
  const value = resolveField(snapshot, key);
  if (split === undefined || value === undefined) return undefined;
  const [entity, id, path] = split;
  if (entity === "match" && path === "sealed") {
    return t(lang, value === true ? "match.sealed" : "match.pending");
  }
  if (entity === "entry" && path === "outcome") {
    if (value === "draw") return t(lang, "match.draw");
    const entry = snapshot.record.entries.find((each) => String(each.publication_id) === id);
    const match = snapshot.matches.find((each) => each.id === entry?.match_id);
    return value === "home" || value === "away" ? match?.[value] : undefined;
  }
  return undefined;
}

function matchFields(match: Match): string[] {
  const key = (path: string) => `match:${match.id}:${path}`;
  const fields = [key("rounds"), key("sealed")];
  for (const round of ROUNDS) {
    if (match.h2h[round] === null) continue;
    fields.push(...SIDES.map((side) => key(`h2h.${round}.p.${side}`)), key(`h2h.${round}.books`));
  }
  if (match.move !== null) fields.push(...SIDES.map((side) => key(`move.${side}`)));
  return fields;
}

function leagueFields(league: League): string[] {
  const fields = [`league:${league.id}:matches`];
  if (league.move_distribution !== null) {
    fields.push(...["p10", "p50", "p90"].map((p) => `league:${league.id}:move_distribution.${p}`));
  }
  return fields;
}

function recordFields(snapshot: Snapshot): string[] {
  const ledger = ["rows", "last_id", "head", "anchor.file", "anchor.rows", "anchor.last_id"];
  const fields = [...ledger, "anchor.head"].map((path) => `ledger:-:${path}`);
  fields.push("record:-:published", "root:-:content_sha256");
  if (snapshot.record.summary !== null) {
    fields.push(...["n", "mean_clv", "ci_low", "ci_high"].map((p) => `record:-:summary.${p}`));
  }
  for (const entry of snapshot.record.entries) {
    const paths = ["market", "outcome", "published_price", "closing_fair_price", "clv"];
    paths.push("publication_ledger_id", "publication_hash");
    fields.push(...paths.map((path) => `entry:${entry.publication_id}:${path}`));
  }
  return fields;
}

function perLang(pathOf: (lang: Lang) => string): Record<Lang, string> {
  return Object.fromEntries(SITE_LANGS.map((lang) => [lang, pathOf(lang)])) as Record<Lang, string>;
}

type RecordSpec = Omit<ExpectedPage, "path" | "lang" | "paths"> & {
  pathOf: (lang: Lang) => string;
};

function records(snapshot: Snapshot): RecordSpec[] {
  const leagueOf = (id: string): League => {
    const league = snapshot.leagues.find((each) => each.id === id);
    if (!league) throw new Error(`lig yok: ${id}`);
    return league;
  };
  const crumbs = "BreadcrumbList";
  return [
    {
      kind: "home",
      id: "home",
      recordIndexable: true,
      fields: [],
      ldTypes: ["WebSite", crumbs],
      pathOf: homePath,
    },
    {
      kind: "track-record",
      id: "track-record",
      recordIndexable: true,
      fields: recordFields(snapshot),
      ldTypes: [crumbs],
      pathOf: trackRecordPath,
    },
    ...LEGAL_DOCS.map(
      (doc): RecordSpec => ({
        kind: "legal",
        id: `legal:${doc}`,
        recordIndexable: false,
        fields: [],
        ldTypes: [crumbs],
        pathOf: (lang) => legalPath(lang, doc),
      }),
    ),
    ...snapshot.leagues.map(
      (league): RecordSpec => ({
        kind: "league",
        id: `league:${league.id}`,
        recordIndexable: true,
        fields: leagueFields(league),
        ldTypes: ["SportsOrganization", crumbs],
        pathOf: (lang) => leaguePath(lang, league),
      }),
    ),
    ...snapshot.teams.map(
      (team): RecordSpec => ({
        kind: "team",
        id: `team:${team.league_id}/${team.slug}`,
        recordIndexable: team.indexable,
        fields: [`team:${team.league_id}/${team.slug}:matches`],
        ldTypes: ["SportsTeam", crumbs],
        pathOf: (lang) => teamPath(lang, leagueOf(team.league_id), team),
      }),
    ),
    ...snapshot.matches.map(
      (match): RecordSpec => ({
        kind: "match",
        id: `match:${match.id}`,
        recordIndexable: match.indexable,
        fields: matchFields(match),
        ldTypes: ["SportsEvent", crumbs],
        pathOf: (lang) => matchPath(lang, leagueOf(match.league_id), match),
      }),
    ),
  ];
}

export function expectedPages(snapshot: Snapshot): ExpectedPage[] {
  return records(snapshot).flatMap(({ pathOf, ...record }) =>
    SITE_LANGS.map((lang) => ({ ...record, lang, path: pathOf(lang), paths: perLang(pathOf) })),
  );
}
