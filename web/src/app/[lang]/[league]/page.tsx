import { SITE_LANGS } from "../../../../site.config.ts";
import { Breadcrumbs } from "../../../components/Breadcrumbs.tsx";
import { Num } from "../../../components/Fe.tsx";
import { JsonLdScript } from "../../../components/JsonLdScript.tsx";
import { LocalTime } from "../../../components/LocalTime.tsx";
import { t } from "../../../i18n/dict.ts";
import { feKey, teamKey } from "../../../lib/fe.ts";
import { breadcrumbLd, leagueLd, pageLd } from "../../../lib/jsonld.ts";
import { pageMetadata } from "../../../lib/meta.ts";
import { langOf, leagueOf } from "../../../lib/params.ts";
import { homePath, leaguePath, matchPath, teamPath } from "../../../lib/routes.ts";
import { loadSnapshot, matchesOf, teamsOf } from "../../../lib/snapshot.ts";

type Params = { params: Promise<{ lang: string; league: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  const { leagues } = loadSnapshot();
  return SITE_LANGS.flatMap((lang) => leagues.map((league) => ({ lang, league: league.slug })));
}

export async function generateMetadata({ params }: Params) {
  const { lang: rawLang, league: slug } = await params;
  const lang = langOf(rawLang);
  const league = leagueOf(loadSnapshot(), slug);
  return pageMetadata(lang, (each) => leaguePath(each, league), league.name, true);
}

export default async function LeaguePage({ params }: Params) {
  const { lang: rawLang, league: slug } = await params;
  const lang = langOf(rawLang);
  const snapshot = loadSnapshot();
  const league = leagueOf(snapshot, slug);
  const path = leaguePath(lang, league);
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: league.name, path },
  ];
  const distribution = league.move_distribution;
  return (
    <main data-fe-page={`league:${league.id}`}>
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{league.name}</h1>
      <dl>
        <dt>{t(lang, "league.country")}</dt>
        <dd>{league.country}</dd>
        <dt>{t(lang, "league.matches")}</dt>
        <dd>
          <Num
            fe={feKey("league", league.id, "matches")}
            value={league.matches}
            kind="int"
            lang={lang}
          />
        </dd>
      </dl>
      <h2>{t(lang, "league.moveTitle")}</h2>
      {distribution === null ? (
        <p>{t(lang, "league.moveTooFew")}</p>
      ) : (
        <dl>
          {(["p10", "p50", "p90"] as const).map((key) => (
            <div key={key}>
              <dt>{t(lang, `league.${key}`)}</dt>
              <dd>
                <Num
                  fe={feKey("league", league.id, `move_distribution.${key}`)}
                  value={distribution[key]}
                  kind="pp1"
                  lang={lang}
                />
              </dd>
            </div>
          ))}
        </dl>
      )}
      <h2>{t(lang, "league.teams")}</h2>
      <ul>
        {teamsOf(snapshot, league).map((team) => (
          <li key={teamKey(team.league_id, team.slug)}>
            <a href={teamPath(lang, league, team)}>{team.name}</a>
          </li>
        ))}
      </ul>
      <h2>{t(lang, "league.matchList")}</h2>
      <ul>
        {matchesOf(snapshot, league).map((match) => (
          <li key={match.id}>
            <LocalTime iso={match.commence_time} lang={lang} />{" "}
            <a href={matchPath(lang, league, match)}>
              {match.home} – {match.away}
            </a>
          </li>
        ))}
      </ul>
      <JsonLdScript data={pageLd([leagueLd(league, path), breadcrumbLd(crumbs)])} />
    </main>
  );
}
