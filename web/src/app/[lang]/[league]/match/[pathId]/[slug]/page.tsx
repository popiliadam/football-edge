// Maç sayfası (spec §7): yalnız vig'i temizlenmiş piyasa konsensüsü, kitap SAYISI, tur
// sayısı, hareket ve mühür durumu. Kitap adı, kitap oranı, bağlantı, skor YOK (B7, AK10).
import { SITE_LANGS } from "../../../../../../../site.config.ts";
import { Breadcrumbs } from "../../../../../../components/Breadcrumbs.tsx";
import { Flag, Num } from "../../../../../../components/Fe.tsx";
import { JsonLdScript } from "../../../../../../components/JsonLdScript.tsx";
import { LocalTime } from "../../../../../../components/LocalTime.tsx";
import { RoundsTable } from "../../../../../../components/RoundsTable.tsx";
import { AnalysisSlot, ValueBadge } from "../../../../../../components/Slots.tsx";
import { t } from "../../../../../../i18n/dict.ts";
import { feKey } from "../../../../../../lib/fe.ts";
import { breadcrumbLd, matchLd, pageLd } from "../../../../../../lib/jsonld.ts";
import { pageMetadata } from "../../../../../../lib/meta.ts";
import { langOf, leagueOf, matchOf } from "../../../../../../lib/params.ts";
import { homePath, leaguePath, matchPath } from "../../../../../../lib/routes.ts";
import { leagueById, loadSnapshot } from "../../../../../../lib/snapshot.ts";

type Params = {
  params: Promise<{ lang: string; league: string; pathId: string; slug: string }>;
};

export const dynamicParams = false;

export function generateStaticParams() {
  const snapshot = loadSnapshot();
  return SITE_LANGS.flatMap((lang) =>
    snapshot.matches.map((match) => ({
      lang,
      league: leagueById(snapshot, match.league_id).slug,
      pathId: match.path_id,
      slug: match.slug,
    })),
  );
}

async function resolve(params: Params["params"]) {
  const { lang: rawLang, league: leagueSlug, pathId, slug } = await params;
  const snapshot = loadSnapshot();
  const league = leagueOf(snapshot, leagueSlug);
  return {
    lang: langOf(rawLang),
    snapshot,
    league,
    match: matchOf(snapshot, league, pathId, slug),
  };
}

export async function generateMetadata({ params }: Params) {
  const { lang, league, match } = await resolve(params);
  const title = `${match.home} – ${match.away}`;
  return pageMetadata(lang, (each) => matchPath(each, league, match), title, match.indexable);
}

export default async function MatchPage({ params }: Params) {
  const { lang, snapshot, league, match } = await resolve(params);
  const path = matchPath(lang, league, match);
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: league.name, path: leaguePath(lang, league) },
    { name: `${match.home} – ${match.away}`, path },
  ];
  const move = match.move;
  return (
    <main data-fe-page={`match:${match.id}`}>
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{`${match.home} – ${match.away}`}</h1>
      <p>
        <a href={leaguePath(lang, league)}>{league.name}</a> · {t(lang, "match.kickoff")}:{" "}
        <LocalTime iso={match.commence_time} lang={lang} />
      </p>
      <ValueBadge value={snapshot.value_badge} />
      <h2>{t(lang, "match.consensus")}</h2>
      <RoundsTable match={match} lang={lang} />
      <dl>
        <dt>{t(lang, "match.rounds")}</dt>
        <dd>
          <Num
            fe={feKey("match", match.id, "rounds")}
            value={match.rounds}
            kind="int"
            lang={lang}
          />
        </dd>
        <dt>{t(lang, "match.status")}</dt>
        <dd>
          <Flag fe={feKey("match", match.id, "sealed")} value={match.sealed}>
            {t(lang, match.sealed ? "match.sealed" : "match.pending")}
          </Flag>
        </dd>
      </dl>
      <h2>{t(lang, "match.move")}</h2>
      {move === null ? (
        <p>{t(lang, "match.noMove")}</p>
      ) : (
        <dl>
          {(["home", "draw", "away"] as const).map((side) => (
            <div key={side}>
              <dt>{side === "draw" ? t(lang, "match.draw") : match[side]}</dt>
              <dd>
                <Num
                  fe={feKey("match", match.id, `move.${side}`)}
                  value={move[side]}
                  kind="pp1"
                  lang={lang}
                />
              </dd>
            </div>
          ))}
        </dl>
      )}
      <AnalysisSlot value={snapshot.analysis} />
      <JsonLdScript
        data={pageLd([matchLd(match, league, path, snapshot.generated_at), breadcrumbLd(crumbs)])}
      />
    </main>
  );
}
