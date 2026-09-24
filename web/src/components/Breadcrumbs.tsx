import type { Crumb } from "../lib/jsonld.ts";
import styles from "../styles/site.module.css";

export function Breadcrumbs({ crumbs, label }: { crumbs: readonly Crumb[]; label: string }) {
  return (
    <nav aria-label={label} className={styles.crumbs}>
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
