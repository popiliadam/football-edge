import { createElement, Fragment } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SITE_LANGS } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";
import { Breadcrumbs } from "./Breadcrumbs.tsx";
import { SiteFooter, SiteHeader } from "./SiteChrome.tsx";

// DEFERRED 20f: bir sayfadaki üç `<nav>` (üst menü, sayfa yolu, yasal) ayrı erişilebilir ad taşır.
// DEFERRED 21j: adlar o dilin sözlüğünden gelir (sabit yazılmış ad tr'de ayrık kalsa da kırmızı).
function navLabels(html: string): string[] {
  return [...html.matchAll(/<nav\b[^>]*?\baria-label="([^"]*)"/g)].map((match) => match[1] ?? "");
}

describe("site çerçevesi gezinme adları", () => {
  for (const lang of SITE_LANGS) {
    it(`${lang}: her <nav> adlı ve adlar ayrık`, () => {
      const html = renderToStaticMarkup(
        createElement(
          Fragment,
          null,
          createElement(SiteHeader, { lang }),
          createElement(Breadcrumbs, { crumbs: [{ name: "x", path: "/x/" }], lang }),
          createElement(SiteFooter, { lang }),
        ),
      );
      const labels = navLabels(html);
      expect((html.match(/<nav\b/g) ?? []).length).toBe(3);
      expect(labels).toHaveLength(3);
      for (const label of labels) expect(label.trim()).not.toBe("");
      expect(new Set(labels).size).toBe(3);
      expect(labels).toEqual([
        t(lang, "nav.main"),
        t(lang, "nav.breadcrumb"),
        t(lang, "nav.legal"),
      ]);
    });
  }
});
