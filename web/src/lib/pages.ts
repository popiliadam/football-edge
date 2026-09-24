// Sitenin sayfa listesi, site haritası için. Çıktı tarayıcısı beklenen sayfaları BU
// modülü kullanmadan kendisi kurar (scripts/checkout/expect.ts): iki bağımsız liste
// birbirini denetler.
import { type Lang, SITE_LANGS } from "../../site.config.ts";
import {
  absoluteUrl,
  homePath,
  leaguePath,
  matchPath,
  teamPath,
  trackRecordPath,
} from "./routes.ts";
import { leagueById } from "./snapshot.ts";
import type { Snapshot } from "./snapshot-types.ts";

export type SitemapEntry = { url: string; alternates: { languages: Record<string, string> } };

type IndexablePage = { pathOf: (lang: Lang) => string; indexable: boolean };

function indexablePages(snapshot: Snapshot): IndexablePage[] {
  return [
    { pathOf: homePath, indexable: true },
    { pathOf: trackRecordPath, indexable: true },
    ...snapshot.leagues.map((league) => ({
      pathOf: (lang: Lang) => leaguePath(lang, league),
      indexable: true,
    })),
    ...snapshot.teams.map((team) => ({
      pathOf: (lang: Lang) => teamPath(lang, leagueById(snapshot, team.league_id), team),
      indexable: team.indexable,
    })),
    ...snapshot.matches.map((match) => ({
      pathOf: (lang: Lang) => matchPath(lang, leagueById(snapshot, match.league_id), match),
      indexable: match.indexable,
    })),
  ];
}

export function sitemapEntries(snapshot: Snapshot, enabled: boolean): SitemapEntry[] {
  if (!enabled) return [];
  return indexablePages(snapshot)
    .filter((page) => page.indexable)
    .flatMap((page) =>
      SITE_LANGS.map((lang) => ({
        url: absoluteUrl(page.pathOf(lang)),
        alternates: {
          languages: Object.fromEntries(
            SITE_LANGS.map((each) => [each, absoluteUrl(page.pathOf(each))]),
          ),
        },
      })),
    );
}
