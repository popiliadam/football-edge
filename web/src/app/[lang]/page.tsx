import { type Lang, SITE_LANGS } from "../../../site.config.ts";
import { Breadcrumbs } from "../../components/Breadcrumbs.tsx";
import { JsonLdScript } from "../../components/JsonLdScript.tsx";
import { t } from "../../i18n/dict.ts";
import { breadcrumbLd, pageLd, websiteLd } from "../../lib/jsonld.ts";
import { pageMetadata } from "../../lib/meta.ts";
import { langOf } from "../../lib/params.ts";
import { homePath, leaguePath, trackRecordPath } from "../../lib/routes.ts";
import { loadSnapshot } from "../../lib/snapshot.ts";

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
  return (
    <main data-fe-page="home">
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{t(lang, "home.title")}</h1>
      <p>{t(lang, "home.intro")}</p>
      <h2>{t(lang, "home.leagues")}</h2>
      <ul>
        {snapshot.leagues.map((league) => (
          <li key={league.id}>
            <a href={leaguePath(lang, league)}>{league.name}</a> ({league.country})
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
