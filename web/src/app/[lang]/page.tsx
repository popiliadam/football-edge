import { type Lang, SITE_LANGS } from "../../../site.config.ts";
import { Breadcrumbs } from "../../components/Breadcrumbs.tsx";
import { JsonLdScript } from "../../components/JsonLdScript.tsx";
import { LocalTime } from "../../components/LocalTime.tsx";
import { ProbabilityBar } from "../../components/ProbabilityBar.tsx";
import { t } from "../../i18n/dict.ts";
import { breadcrumbLd, pageLd, websiteLd } from "../../lib/jsonld.ts";
import { pageMetadata } from "../../lib/meta.ts";
import { langOf } from "../../lib/params.ts";
import { homePath, leaguePath, matchPath, trackRecordPath } from "../../lib/routes.ts";
import { leagueById, loadSnapshot } from "../../lib/snapshot.ts";
import { upcomingMatches } from "../../lib/upcoming.ts";
import styles from "../../styles/site.module.css";

type Params = { params: Promise<{ lang: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export async function generateMetadata({ params }: Params) {
  const lang = langOf((await params).lang);
  return pageMetadata(lang, homePath, t(lang, "home.title"), true);
}

export default async function HomePage({ params }: Params) {
  const lang: Lang = langOf((await params).lang);
  const snapshot = loadSnapshot();
  const crumbs = [{ name: t(lang, "nav.home"), path: homePath(lang) }];
  const upcoming = upcomingMatches(snapshot);
  return (
    <main data-fe-page="home">
      <Breadcrumbs crumbs={crumbs} lang={lang} />
      <h1>{t(lang, "home.title")}</h1>
      <p className={styles.lede}>{t(lang, "home.intro")}</p>
      {upcoming.length === 0 ? null : (
        <>
          <h2>{t(lang, "home.upcoming")}</h2>
          <p className={styles.legend} aria-hidden="true">
            <span className={styles.home}>{t(lang, "home.legendHome")}</span>
            <span className={styles.draw}>{t(lang, "match.draw")}</span>
            <span className={styles.away}>{t(lang, "home.legendAway")}</span>
          </p>
          <ul className={styles.upcoming}>
            {upcoming.map((match) => {
              const latest = match.h2h.latest;
              return (
                <li key={match.id}>
                  <LocalTime iso={match.commence_time} lang={lang} />
                  <a href={matchPath(lang, leagueById(snapshot, match.league_id), match)}>
                    {match.home} – {match.away}
                  </a>
                  {latest === null ? null : <ProbabilityBar p={latest.p} />}
                </li>
              );
            })}
          </ul>
        </>
      )}
      <h2>{t(lang, "home.leagues")}</h2>
      <ul className={styles.rows}>
        {snapshot.leagues.map((league) => (
          <li key={league.id}>
            <a href={leaguePath(lang, league)}>{league.name}</a>{" "}
            <span className={styles.muted}>({league.country})</span>
          </li>
        ))}
      </ul>
      <p>
        <a href={trackRecordPath(lang)}>{t(lang, "home.trackRecordLink")}</a>
      </p>
      <JsonLdScript data={pageLd([websiteLd(lang, homePath(lang)), breadcrumbLd(crumbs)])} />
    </main>
  );
}
