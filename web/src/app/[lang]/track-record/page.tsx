// Sicil (spec §6): defterden türetilir, sayı hesaplamaz (H6). Boş sicil bir DURUMdur;
// "yakında", sahte örnek, backtest sonucu GÖSTERİLMEZ (§6.2).
import { LEDGER_HISTORY_URL, SITE_LANGS } from "../../../../site.config.ts";
import { Breadcrumbs } from "../../../components/Breadcrumbs.tsx";
import { Num, Txt } from "../../../components/Fe.tsx";
import { JsonLdScript } from "../../../components/JsonLdScript.tsx";
import { LocalTime } from "../../../components/LocalTime.tsx";
import { RecordTable } from "../../../components/RecordTable.tsx";
import { t } from "../../../i18n/dict.ts";
import { feKey } from "../../../lib/fe.ts";
import { breadcrumbLd, pageLd } from "../../../lib/jsonld.ts";
import { pageMetadata } from "../../../lib/meta.ts";
import { langOf } from "../../../lib/params.ts";
import { homePath, trackRecordPath } from "../../../lib/routes.ts";
import { loadSnapshot } from "../../../lib/snapshot.ts";

type Params = { params: Promise<{ lang: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export async function generateMetadata({ params }: Params) {
  const lang = langOf((await params).lang);
  return pageMetadata(lang, trackRecordPath, t(lang, "record.title"), true);
}

export default async function TrackRecordPage({ params }: Params) {
  const lang = langOf((await params).lang);
  const snapshot = loadSnapshot();
  const { ledger, record } = snapshot;
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: t(lang, "record.title"), path: trackRecordPath(lang) },
  ];
  const ledgerNum = (path: string, value: number) => (
    <Num fe={feKey("ledger", "-", path)} value={value} kind="int" lang={lang} />
  );
  return (
    <main data-fe-page="track-record">
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{t(lang, "record.title")}</h1>
      <p>
        {t(lang, "record.published")}:{" "}
        <strong>
          <Num
            fe={feKey("record", "-", "published")}
            value={record.published}
            kind="int"
            lang={lang}
          />
        </strong>
      </p>
      {record.published === 0 ? (
        <p>{t(lang, "record.emptyExplain")}</p>
      ) : (
        <RecordTable snapshot={snapshot} lang={lang} />
      )}
      <h2>{t(lang, "record.ledgerTitle")}</h2>
      <dl>
        <dt>{t(lang, "record.head")}</dt>
        <dd>
          <Txt fe={feKey("ledger", "-", "head")} value={ledger.head} />
        </dd>
        <dt>{t(lang, "record.rows")}</dt>
        <dd>{ledgerNum("rows", ledger.rows)}</dd>
        <dt>{t(lang, "record.lastId")}</dt>
        <dd>{ledgerNum("last_id", ledger.last_id)}</dd>
        <dt>{t(lang, "record.exportedAt")}</dt>
        <dd>
          <LocalTime iso={snapshot.generated_at} lang={lang} />
        </dd>
      </dl>
      <h2>{t(lang, "record.anchorTitle")}</h2>
      <dl>
        <dt>{t(lang, "record.anchorHistory")}</dt>
        <dd>
          <a href={`${LEDGER_HISTORY_URL}/${ledger.anchor.file}`}>
            <Txt fe={feKey("ledger", "-", "anchor.file")} value={ledger.anchor.file} />
          </a>
        </dd>
        <dt>{t(lang, "record.head")}</dt>
        <dd>
          <Txt fe={feKey("ledger", "-", "anchor.head")} value={ledger.anchor.head} />
        </dd>
        <dt>{t(lang, "record.rows")}</dt>
        <dd>{ledgerNum("anchor.rows", ledger.anchor.rows)}</dd>
        <dt>{t(lang, "record.lastId")}</dt>
        <dd>{ledgerNum("anchor.last_id", ledger.anchor.last_id)}</dd>
      </dl>
      {ledger.anchor.last_id === ledger.last_id ? (
        <p>{t(lang, "record.anchorMatches")}</p>
      ) : (
        <p>
          {t(lang, "record.anchorBehindBefore")}{" "}
          <Txt fe={feKey("ledger", "-", "anchor.file")} value={ledger.anchor.file} />{" "}
          {t(lang, "record.anchorBehindMiddle")}{" "}
          {ledgerNum("anchor.last_id", ledger.anchor.last_id)}
          {t(lang, "record.anchorBehindAfter")}
        </p>
      )}
      <h2>{t(lang, "record.contentHash")}</h2>
      <p>
        <Txt fe={feKey("root", "-", "content_sha256")} value={snapshot.content_sha256} />
      </p>
      <p>{t(lang, "record.commitment")}</p>
      <h2>{t(lang, "record.howTitle")}</h2>
      <ol>
        <li>{t(lang, "record.limit1")}</li>
        <li>{t(lang, "record.limit2")}</li>
        <li>{t(lang, "record.limit3")}</li>
      </ol>
      <JsonLdScript data={pageLd([breadcrumbLd(crumbs)])} />
    </main>
  );
}
