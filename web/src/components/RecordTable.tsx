// Dolu sicil (spec §6.1): her değer Python'da hesaplanmış, TS yalnız biçimler.
import type { Lang } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";
import { feKey } from "../lib/fe.ts";
import { outcomeLabel } from "../lib/outcome.ts";
import type { Snapshot } from "../lib/snapshot-types.ts";
import styles from "../styles/site.module.css";
import { Flag, Num, Txt } from "./Fe.tsx";
import { LocalTime } from "./LocalTime.tsx";

export function RecordTable({ snapshot, lang }: { snapshot: Snapshot; lang: Lang }) {
  const { entries, summary } = snapshot.record;
  const names = new Map(
    snapshot.matches.map((match) => [match.id, `${match.home} – ${match.away}`]),
  );
  return (
    <>
      <table className={styles.table}>
        <caption>{t(lang, "record.tableCaption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t(lang, "record.colTime")}</th>
            <th scope="col">{t(lang, "record.colMatch")}</th>
            <th scope="col">{t(lang, "record.colMarket")}</th>
            <th scope="col">{t(lang, "record.colOutcome")}</th>
            <th scope="col">{t(lang, "record.colPrice")}</th>
            <th scope="col">{t(lang, "record.colFair")}</th>
            <th scope="col">{t(lang, "record.colClv")}</th>
            <th scope="col">{t(lang, "record.colLedger")}</th>
            <th scope="col">{t(lang, "record.colHash")}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const id = String(entry.publication_id);
            return (
              <tr key={id}>
                <td>
                  <LocalTime iso={entry.published_at} lang={lang} />
                </td>
                <td>{names.get(entry.match_id) ?? entry.match_id}</td>
                <td>
                  <Txt fe={feKey("entry", id, "market")} value={entry.market} />
                </td>
                <td>
                  <Flag fe={feKey("entry", id, "outcome")} value={entry.outcome}>
                    {outcomeLabel(
                      entry.outcome,
                      snapshot.matches.find((match) => match.id === entry.match_id),
                      t(lang, "match.draw"),
                    )}
                  </Flag>
                </td>
                <td>
                  <Num
                    fe={feKey("entry", id, "published_price")}
                    value={entry.published_price}
                    kind="price2"
                    lang={lang}
                  />
                </td>
                <td>
                  <Num
                    fe={feKey("entry", id, "closing_fair_price")}
                    value={entry.closing_fair_price}
                    kind="price2"
                    lang={lang}
                  />
                </td>
                <td>
                  <Num fe={feKey("entry", id, "clv")} value={entry.clv} kind="pct2" lang={lang} />
                </td>
                <td>
                  <Num
                    fe={feKey("entry", id, "publication_ledger_id")}
                    value={entry.publication_ledger_id}
                    kind="int"
                    lang={lang}
                  />
                </td>
                <td>
                  <Txt fe={feKey("entry", id, "publication_hash")} value={entry.publication_hash} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {summary === null ? null : (
        <>
          <h2>{t(lang, "record.summaryTitle")}</h2>
          <dl>
            <dt>{t(lang, "record.summaryN")}</dt>
            <dd>
              <Num
                fe={feKey("record", "-", "summary.n")}
                value={summary.n}
                kind="int"
                lang={lang}
              />
            </dd>
            <dt>{t(lang, "record.summaryMean")}</dt>
            <dd>
              <Num
                fe={feKey("record", "-", "summary.mean_clv")}
                value={summary.mean_clv}
                kind="pct2"
                lang={lang}
              />
            </dd>
            <dt>{t(lang, "record.summaryCi")}</dt>
            <dd>
              <Num
                fe={feKey("record", "-", "summary.ci_low")}
                value={summary.ci_low}
                kind="pct2"
                lang={lang}
              />
              {" … "}
              <Num
                fe={feKey("record", "-", "summary.ci_high")}
                value={summary.ci_high}
                kind="pct2"
                lang={lang}
              />
            </dd>
          </dl>
        </>
      )}
    </>
  );
}
