// schema.org JSON-LD oluşturucuları (spec §9). Anlık görüntüden üretilir; oran, teklif,
// bahis bağlantısı, konum, skor YOK. `eventStatus` yalnız maç dışa aktarım anından sonraysa.
import { type Lang, SITE_NAME, SITE_URL } from "../../site.config.ts";
import { absoluteUrl } from "./routes.ts";
import type { League, Match, Team } from "./snapshot-types.ts";

export type JsonLd = Record<string, unknown>;
export type Crumb = { name: string; path: string };

const CONTEXT = "https://schema.org";

export function websiteLd(lang: Lang, homePath: string): JsonLd {
  return {
    "@type": "WebSite",
    name: SITE_NAME,
    url: absoluteUrl(homePath),
    inLanguage: lang,
    publisher: organizationLd(),
  };
}

export function organizationLd(): JsonLd {
  return { "@type": "Organization", name: SITE_NAME, url: SITE_URL };
}

export function leagueLd(league: League, path: string): JsonLd {
  return {
    "@type": "SportsOrganization",
    name: league.name,
    sport: "Soccer",
    location: { "@type": "Country", name: league.country },
    url: absoluteUrl(path),
  };
}

export function teamLd(team: Team, league: League, path: string): JsonLd {
  return {
    "@type": "SportsTeam",
    name: team.name,
    sport: "Soccer",
    memberOf: { "@type": "SportsOrganization", name: league.name },
    url: absoluteUrl(path),
  };
}

export function matchLd(match: Match, league: League, path: string, generatedAt: string): JsonLd {
  const event: JsonLd = {
    "@type": "SportsEvent",
    name: `${match.home} – ${match.away}`,
    startDate: match.commence_time,
    sport: "Soccer",
    homeTeam: { "@type": "SportsTeam", name: match.home },
    awayTeam: { "@type": "SportsTeam", name: match.away },
    organizer: { "@type": "SportsOrganization", name: league.name },
    url: absoluteUrl(path),
  };
  if (Date.parse(match.commence_time) > Date.parse(generatedAt)) {
    event.eventStatus = `${CONTEXT}/EventScheduled`;
  }
  return event;
}

export function breadcrumbLd(crumbs: readonly Crumb[]): JsonLd {
  return {
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.name,
      item: absoluteUrl(crumb.path),
    })),
  };
}

// Spec §9: sayfa başına TEK veri bloğu — varlık(lar) + BreadcrumbList aynı `@graph`ta.
export function pageLd(nodes: readonly JsonLd[]): JsonLd {
  return { "@context": CONTEXT, "@graph": nodes };
}

// `</script>` kırılmasına karşı `<` kaçışlanır; JSON anlamı değişmez.
export function serializeLd(value: JsonLd): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}
