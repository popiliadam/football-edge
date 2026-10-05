import { CONTACT_EMAIL, SITE_NAME } from "../../../site.config.ts";

export default function Terms() {
  return (
    <article>
      <h2>What this site is</h2>
      <p>
        This site is for information only. It shows market consensus probabilities derived from
        bookmaker prices that we record in a hash-chained ledger. We publish the ledger's head
        hashes, not its rows. The site does not accept bets, does not direct visitors to any
        bookmaker and contains no links to betting operators.
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
      <h2>Operator and contact</h2>
      <p>
        This site is operated under the name {SITE_NAME}. Contact: {CONTACT_EMAIL}.
      </p>
      <h2>Liability</h2>
      <p>
        The site is provided as it is. To the extent the law allows, we are not liable for losses
        arising from decisions made in reliance on its content. Nothing in these terms limits
        liability that cannot be limited by law.
      </p>
      <h2>Governing law and courts</h2>
      <p>
        These terms are governed by the laws of England and Wales, and the courts of England and
        Wales have jurisdiction over disputes. If you use the site as a consumer, this does not
        remove the protection of the mandatory consumer laws of the country where you live or your
        right to bring proceedings there.
      </p>
    </article>
  );
}
