import styles from "../../../src/styles/site.module.css";

export default function ResponsibleGambling() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler (draft, pending legal review)</p>
      <h2>18+ only</h2>
      <p>This site is for adults aged 18 or over. We do not accept bets.</p>
      <h2>Gambling can be addictive</h2>
      <p>
        Betting can lead to financial loss and addiction. Set limits, never chase losses and stop if
        gambling stops being fun.
      </p>
      <h2>Where to get help</h2>
      <p>
        Help is available in your country. Contact details below are placeholders and are checked
        against their primary sources before publication.
      </p>
      <ul>
        <li>United Kingdom: national gambling helpline [DOĞRULANACAK]</li>
        <li>Türkiye: Yeşilay advice line [DOĞRULANACAK]</li>
      </ul>
    </article>
  );
}
