import type { Lang } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";
import type { Crumb } from "../lib/jsonld.ts";
import styles from "../styles/site.module.css";

// Erişilebilir adı sözlükten gelir: üst menüden ve yasal menüden ayrı (DEFERRED 20f).
export function Breadcrumbs({ crumbs, lang }: { crumbs: readonly Crumb[]; lang: Lang }) {
  return (
    <nav aria-label={t(lang, "nav.breadcrumb")} className={styles.crumbs}>
      <ol>
        {crumbs.map((crumb) => (
          <li key={crumb.path}>
            <a href={crumb.path}>{crumb.name}</a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
