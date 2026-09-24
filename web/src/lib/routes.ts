// URL şeması (spec §8.1, AK20 b) — TEK kaynak: sayfalar, site haritası, `_redirects` ve
// çıktı tarayıcısı yolu buradan kurar. Bölüt adları sabit ve İngilizcedir.
import { type Lang, type LegalDoc, SITE_URL } from "../../site.config.ts";
import type { League, Match, Team } from "./snapshot-types.ts";

export const homePath = (lang: Lang): string => `/${lang}/`;
export const trackRecordPath = (lang: Lang): string => `/${lang}/track-record/`;
export const legalPath = (lang: Lang, doc: LegalDoc): string => `/${lang}/legal/${doc}/`;
export const leaguePath = (lang: Lang, league: League): string => `/${lang}/${league.slug}/`;

export function teamPath(lang: Lang, league: League, team: Team): string {
  return `/${lang}/${league.slug}/${team.slug}/`;
}

// Maç yolu değişmez kimliği (`path_id`) taşır; isim bölütü süstür (spec §8.1).
export function matchStem(lang: Lang, league: League, match: Match): string {
  return `/${lang}/${league.slug}/match/${match.path_id}/`;
}

export function matchPath(lang: Lang, league: League, match: Match): string {
  return `${matchStem(lang, league, match)}${match.slug}/`;
}

export const absoluteUrl = (path: string): string => `${SITE_URL}${path}`;
