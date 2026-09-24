// `data-fe` dışında sayı yok (T5 carry-in 3; T9 inceleme I2, M5, M6, M7). Görünen metinde `data-fe`
// öğeleri ve anlık görüntü zamanını birebir gösteren `<time>` dışındaki her rakam bulgudur; izinler
// BAĞLAMLIDIR: `18+` işareti ve 18+ bildiriminin sözlük cümleleri, lig sayfasında yüzdelik etiketleri
// (sözlük), Next'in 404 sayfasında `404`, yasal taslakta belge başına adıyla yazılmış atıflar.
import { type LegalDoc, SITE_NAME } from "../../site.config.ts";
import { type DictKey, t } from "../../src/i18n/dict.ts";
import type { Snapshot } from "../../src/lib/snapshot-types.ts";
import { decodeEntities, parseAttrs, stripScripts } from "../lib/html.ts";
import type { ExpectedPage } from "./expect.ts";
import { ldStrings, mergeInline, metaTexts } from "./surface.ts";
import { squash, textNodes } from "./text.ts";

// Sunucu çıktısındaki zaman metni (LocalTime.tsx'ten bağımsız yazılır).
export const utcText = (iso: string): string => `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;

// Yasal taslağın kendi rakamları, belge başına: 18 yaş atfı (her belgede), KVKK md. 6 (gizlilik).
export const LEGAL_NUMBERS: Record<LegalDoc, readonly string[]> = {
  terms: ["18"],
  privacy: ["6", "18"],
  cookies: ["18"],
  "responsible-gambling": ["18"],
};
const AGE_SENTENCES: readonly DictKey[] = ["age.body", "age.confirm"];
const PERCENTILE_LABELS: readonly DictKey[] = ["league.p10", "league.p90"];

const FE_ELEMENT = /<([a-z][a-z0-9]*)\b[^>]*\bdata-fe="[^"]*"[^>]*>[^<]*<\/\1>/g;
const TIME = /<time\b([^>]*)>([^<]*)<\/time>/gi;
const NUMBER = /\p{Nd}+(?:[.,٫٬]\p{Nd}+)*/gu;
const escapeRegExp = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export type NumberContext = {
  allowed: readonly string[];
  names: readonly string[];
  sentences: readonly string[];
  times: readonly string[];
};

// Sayfanın gösterdiği anlık görüntü zamanları: yalnız bunları UTC metniyle gösteren `<time>` muaftır.
export function pageTimes(snapshot: Snapshot, page: ExpectedPage): string[] {
  const [, id = ""] = page.id.split(":");
  const matches = snapshot.matches.filter((match) => {
    if (page.kind === "match") return page.id === `match:${match.id}`;
    if (page.kind === "league") return match.league_id === id;
    const team = snapshot.teams.find((each) => page.id === `team:${each.league_id}/${each.slug}`);
    return (
      team !== undefined &&
      match.league_id === team.league_id &&
      (match.home === team.name || match.away === team.name)
    );
  });
  if (page.kind === "track-record") {
    return [snapshot.generated_at, ...snapshot.record.entries.map((entry) => entry.published_at)];
  }
  return ["match", "league", "team"].includes(page.kind)
    ? matches.map((match) => match.commence_time)
    : [];
}

// Sayfanın kendi varlıklarının adları (anlık görüntüden birebir): "Schalke 04" veri metnidir.
export function pageNames(snapshot: Snapshot, page: ExpectedPage): string[] {
  const [, id = ""] = page.id.split(":");
  const league = snapshot.leagues.find(
    (each) => each.id === id || id.startsWith(`${each.id}/`) || page.id === `league:${each.id}`,
  );
  const matchOf = (each: { home: string; away: string }) => [each.home, each.away];
  const names: Record<ExpectedPage["kind"], () => string[]> = {
    home: () => snapshot.leagues.flatMap((each) => [each.name, each.country]),
    league: () => [
      ...(league ? [league.name, league.country] : []),
      ...snapshot.teams.filter((team) => team.league_id === id).map((team) => team.name),
      ...snapshot.matches.filter((match) => match.league_id === id).flatMap(matchOf),
    ],
    team: () => {
      const team = snapshot.teams.find((each) => `${each.league_id}/${each.slug}` === id);
      const own = snapshot.matches.filter(
        (match) =>
          match.league_id === team?.league_id && [match.home, match.away].includes(team.name),
      );
      return [
        ...(team ? [team.name] : []),
        ...(league ? [league.name] : []),
        ...own.flatMap(matchOf),
      ];
    },
    match: () => {
      const match = snapshot.matches.find((each) => each.id === id);
      const own = snapshot.leagues.find((each) => each.id === match?.league_id);
      return [...(own ? [own.name] : []), ...(match ? matchOf(match) : [])];
    },
    "track-record": () =>
      snapshot.record.entries.flatMap((entry) =>
        snapshot.matches.filter((match) => match.id === entry.match_id).flatMap(matchOf),
      ),
    legal: () => [],
  };
  return [SITE_NAME, ...names[page.kind]()];
}

export function pageNumberContext(snapshot: Snapshot, page: ExpectedPage): NumberContext {
  const doc = page.kind === "legal" ? (page.id.split(":")[1] as LegalDoc) : undefined;
  const keys = [...AGE_SENTENCES, ...(page.kind === "league" ? PERCENTILE_LABELS : [])];
  return {
    allowed: doc ? LEGAL_NUMBERS[doc] : [],
    names: pageNames(snapshot, page),
    sentences: keys.map((key) => t(page.lang, key)),
    times: pageTimes(snapshot, page),
  };
}

// Sayı taranacak metinler: data-fe öğeleri ve muaf `<time>`lar boşluğa; satır içi etiketler birleşir
// (`10<i></i>.90` = `10.90`); arama sonucunda görünen meta ve JSON-LD `description` de dahil.
export function numberTexts(html: string, times: readonly string[]): string[] {
  const cleaned = stripScripts(html)
    .replace(/<style\b[\s\S]*?<\/style>/gi, "")
    .replace(FE_ELEMENT, " ")
    .replace(TIME, (_, attrs: string, text: string) => {
      const iso = parseAttrs(attrs).datetime ?? "";
      return times.includes(iso) && decodeEntities(text) === utcText(iso) ? " " : ` ${text} `;
    });
  return [
    ...textNodes(mergeInline(cleaned)).map((node) => node.text),
    ...metaTexts(html),
    ...ldStrings(html)
      .filter((leaf) => leaf.key === "description")
      .map((leaf) => leaf.value),
  ];
}

export function scanNumbers(
  where: string,
  texts: readonly string[],
  context: NumberContext,
): string[] {
  const names = [...new Set(context.names)].sort((a, b) => b.length - a.length);
  const findings: string[] = [];
  for (const text of texts) {
    let rest = squash(text.normalize("NFKC").replace(/\p{Cf}/gu, ""));
    for (const sentence of context.sentences) rest = rest.split(squash(sentence)).join(" ");
    for (const name of names) {
      const pattern = new RegExp(
        `(?<![\\p{L}\\p{N}])${escapeRegExp(name)}(?![\\p{L}\\p{N}%]|[.,]\\p{N})`,
        "gu",
      );
      rest = rest.replace(pattern, " ");
    }
    rest = rest.replace(/(?<![\p{N}.,])18\+/gu, " ");
    for (const [number] of rest.matchAll(NUMBER)) {
      if (!context.allowed.includes(number)) {
        findings.push(
          `${where}: data-fe dışında sayı "${number}" ("${squash(text).slice(0, 60)}")`,
        );
      }
    }
  }
  return findings;
}

export function numberFindings(snapshot: Snapshot, page: ExpectedPage, html: string): string[] {
  const context = pageNumberContext(snapshot, page);
  return scanNumbers(page.path, numberTexts(html, context.times), context);
}

// Next'in 404 sayfaları: yalnız `404`.
export function frameworkNumberFindings(where: string, html: string): string[] {
  const context = { allowed: ["404"], names: [SITE_NAME], sentences: [], times: [] };
  return scanNumbers(where, numberTexts(html, []), context);
}
