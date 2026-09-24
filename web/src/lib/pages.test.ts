import { describe, expect, it } from "vitest";
import { DEFAULT_LANG, SITE_URL } from "../../site.config.ts";
import { fullFixture } from "./fixture.ts";
import { sitemapEntries } from "./pages.ts";

const snapshot = fullFixture();

describe("site haritası girdileri (spec §5.3/5, §8.4, H7)", () => {
  it("bayrak kapalıyken boş", () => {
    expect(sitemapEntries(snapshot, false)).toEqual([]);
  });

  it("bayrak açıkken yalnız indekslenebilir kayıtlar, her dilde, bütün dillere alternatif; yasal yok", () => {
    const entries = sitemapEntries(snapshot, true);
    const perLang =
      2 +
      snapshot.leagues.length +
      snapshot.teams.filter((team) => team.indexable).length +
      snapshot.matches.filter((match) => match.indexable).length;
    expect(entries).toHaveLength(2 * perLang);
    expect(entries.some((entry) => entry.url.includes("/legal/"))).toBe(false);
    expect(new Set(entries.map((entry) => entry.url)).size).toBe(entries.length);
    for (const entry of entries) {
      expect(Object.keys(entry.alternates.languages).sort()).toEqual(["en", "tr", "x-default"]);
      expect(entry.alternates.languages["x-default"]).toBe(
        entry.alternates.languages[DEFAULT_LANG],
      );
      expect(entry.alternates.languages).toHaveProperty(entry.url.split("/")[3] ?? "", entry.url);
      expect(entry.url.startsWith(`${SITE_URL}/`)).toBe(true);
    }
  });
});
