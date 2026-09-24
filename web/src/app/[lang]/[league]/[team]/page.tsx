import { SITE_LANGS } from "../../../../../site.config.ts";
import { Breadcrumbs } from "../../../../components/Breadcrumbs.tsx";
import { Num } from "../../../../components/Fe.tsx";
import { JsonLdScript } from "../../../../components/JsonLdScript.tsx";
import { LocalTime } from "../../../../components/LocalTime.tsx";
import { t } from "../../../../i18n/dict.ts";
import { feKey, teamKey } from "../../../../lib/fe.ts";
import { breadcrumbLd, pageLd, teamLd } from "../../../../lib/jsonld.ts";
import { pageMetadata } from "../../../../lib/meta.ts";
import { langOf, leagueOf, teamOf } from "../../../../lib/params.ts";
import { homePath, leaguePath, matchPath, teamPath } from "../../../../lib/routes.ts";
import { leagueById, loadSnapshot, matchesOfTeam } from "../../../../lib/snapshot.ts";

type Params = { params: Promise<{ lang: string; league: string; team: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  const snapshot = loadSnapshot();
  return SITE_LANGS.flatMap((lang) =>
    snapshot.teams.map((team) => ({
      lang,
      league: leagueById(snapshot, team.league_id).slug,
      team: team.slug,
    })),
  );
}

export async function generateMetadata({ params }: Params) {
  const { lang: rawLang, league: leagueSlug, team: teamSlug } = await params;
  const lang = langOf(rawLang);
  const snapshot = loadSnapshot();
  const league = leagueOf(snapshot, leagueSlug);
  const team = teamOf(snapshot, league, teamSlug);
  return pageMetadata(lang, (each) => teamPath(each, league, team), team.name, team.indexable);
}

export default async function TeamPage({ params }: Params) {
  const { lang: rawLang, league: leagueSlug, team: teamSlug } = await params;
  const lang = langOf(rawLang);
  const snapshot = loadSnapshot();
  const league = leagueOf(snapshot, leagueSlug);
  const team = teamOf(snapshot, league, teamSlug);
  const path = teamPath(lang, league, team);
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: league.name, path: leaguePath(lang, league) },
    { name: team.name, path },
  ];
  return (
    <main data-fe-page={`team:${teamKey(team.league_id, team.slug)}`}>
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{team.name}</h1>
      <dl>
        <dt>{t(lang, "team.league")}</dt>
        <dd>
          <a href={leaguePath(lang, league)}>{league.name}</a>
        </dd>
        <dt>{t(lang, "team.matches")}</dt>
        <dd>
          <Num
            fe={feKey("team", teamKey(team.league_id, team.slug), "matches")}
            value={team.matches}
            kind="int"
            lang={lang}
          />
        </dd>
      </dl>
      <h2>{t(lang, "team.matchList")}</h2>
      <ul>
        {matchesOfTeam(snapshot, team).map((match) => (
          <li key={match.id}>
            <LocalTime iso={match.commence_time} lang={lang} />{" "}
            <a href={matchPath(lang, league, match)}>
              {match.home} – {match.away}
            </a>
          </li>
        ))}
      </ul>
      <JsonLdScript data={pageLd([teamLd(team, league, path), breadcrumbLd(crumbs)])} />
    </main>
  );
}
