import styles from "../../../src/styles/site.module.css";

export default function Terms() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler (draft, pending legal review)</p>
      <h2>What this site is</h2>
      <p>
        This site is for information only. It shows market consensus probabilities derived from
        bookmaker prices that we record in a public, hash-chained ledger. It does not accept bets,
        does not direct visitors to any bookmaker and contains no links to betting operators.
      </p>
      <h2>No guarantee</h2>
      <p>
        Probabilities are estimates, not guarantees. Past performance does not predict future
        results. Nothing on this site is betting, financial or investment advice.
      </p>
      <h2>Data sources</h2>
      <p data-fe-allow="license-negation">
        We make no claim that our data is licensed, that it is official data, or that we are an
        official partner of any league, club or data provider.
      </p>
      <h2>Age</h2>
      <p>This site is intended for adults aged 18 or over.</p>
      <h2>Open questions for counsel</h2>
      <p>[AVUKAT SORUSU] Governing law, jurisdiction and liability limitation wording.</p>
    </article>
  );
}
