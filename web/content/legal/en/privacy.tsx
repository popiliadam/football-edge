import styles from "../../../src/styles/site.module.css";

export default function Privacy() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler (draft, pending legal review)</p>
      <h2>What we collect</h2>
      <p>
        We do not collect personal data. The site has no accounts, no forms, no newsletter, no
        comments and no analytics.
      </p>
      <h2>Hosting</h2>
      <p>
        The site is served as static files by a hosting provider, which may keep technical access
        logs (such as IP addresses) to operate its service.
      </p>
      <p>
        [AVUKAT SORUSU] Is the hosting provider a processor acting for us, or an independent
        controller for its own logs? Does serving the site from abroad amount to a cross-border
        transfer that needs a legal basis or notice?
      </p>
      <h2>Health data</h2>
      <p>We do not publish player health, injury or any other player-level information.</p>
      <h2>Local storage</h2>
      <p>
        Your browser stores a single entry recording that you confirmed you are 18 or older. It
        never leaves your device.
      </p>
    </article>
  );
}
