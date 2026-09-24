// Açılış / son / kapanış konsensüsü. Eşik altı tur `null`dır: sayı UYDURULMAZ, neden yazılır.
import type { Lang } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";
import { feKey } from "../lib/fe.ts";
import type { Match } from "../lib/snapshot-types.ts";
import styles from "../styles/site.module.css";
import { Num } from "./Fe.tsx";

const ROUNDS = ["opening", "latest", "closing"] as const;
const SIDES = ["home", "draw", "away"] as const;

export function RoundsTable({ match, lang }: { match: Match; lang: Lang }) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">{t(lang, "match.round")}</th>
          <th scope="col">{match.home}</th>
          <th scope="col">{t(lang, "match.draw")}</th>
          <th scope="col">{match.away}</th>
          <th scope="col">{t(lang, "match.books")}</th>
        </tr>
      </thead>
      <tbody>
        {ROUNDS.map((name) => {
          const round = match.h2h[name];
          const missing =
            name === "closing" && !match.sealed ? "match.awaitingClose" : "match.insufficient";
          return (
            <tr key={name}>
              <th scope="row">{t(lang, `match.${name}`)}</th>
              {round === null ? (
                <td colSpan={4}>{t(lang, missing)}</td>
              ) : (
                <>
                  {SIDES.map((side) => (
                    <td key={side}>
                      <Num
                        fe={feKey("match", match.id, `h2h.${name}.p.${side}`)}
                        value={round.p[side]}
                        kind="pct1"
                        lang={lang}
                      />
                    </td>
                  ))}
                  <td>
                    <Num
                      fe={feKey("match", match.id, `h2h.${name}.books`)}
                      value={round.books}
                      kind="int"
                      lang={lang}
                    />
                  </td>
                </>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
