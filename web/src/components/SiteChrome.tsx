import { type Lang, LEGAL_DOCS, SITE_NAME } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";
import { homePath, legalPath, trackRecordPath } from "../lib/routes.ts";
import styles from "../styles/site.module.css";

export function SiteHeader({ lang }: { lang: Lang }) {
  return (
    <header className={styles.header}>
      <a href={homePath(lang)} className={styles.brand}>
        {SITE_NAME}
      </a>
      <nav aria-label={t(lang, "nav.home")}>
        <a href={homePath(lang)}>{t(lang, "nav.home")}</a>{" "}
        <a href={trackRecordPath(lang)}>{t(lang, "nav.trackRecord")}</a>
      </nav>
    </header>
  );
}

export function SiteFooter({ lang }: { lang: Lang }) {
  return (
    <footer className={styles.footer}>
      <p>{t(lang, "age.strip")}</p>
      <p>{t(lang, "footer.notAdvice")}</p>
      <p>{t(lang, "footer.responsible")}</p>
      <nav aria-label={t(lang, "nav.legal")}>
        <ul>
          {LEGAL_DOCS.map((doc) => (
            <li key={doc}>
              <a href={legalPath(lang, doc)}>{t(lang, `legal.${doc}`)}</a>
            </li>
          ))}
        </ul>
      </nav>
    </footer>
  );
}
