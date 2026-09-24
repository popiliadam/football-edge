import { describe, expect, it } from "vitest";
import { DEFAULT_LANG, SITE_URL } from "../../site.config.ts";
import { fullFixture } from "./fixture.ts";
import { alternatesFor } from "./hreflang.ts";
import { leaguePath, matchPath, matchStem, teamPath } from "./routes.ts";

const snapshot = fullFixture();
const [league] = snapshot.leagues;
const match = snapshot.matches[0];
const team = snapshot.teams[0];

describe("URL şeması (spec §8.1)", () => {
  it("maç yolu kimlik taşır, tarih taşımaz; isim bölütü sonda", () => {
    if (!league || !match) throw new Error("fixture boş");
    expect(match.id.startsWith(match.path_id)).toBe(true);
    expect(matchPath("en", league, match)).toBe(
      `/en/synthetic-league-alpha/match/${match.path_id}/kuzeyspor-vs-guneykoy-idmanyurdu/`,
    );
    expect(matchStem("tr", league, match)).toBe(
      `/tr/synthetic-league-alpha/match/${match.path_id}/`,
    );
    expect(matchPath("en", league, match)).not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  it("takım ve lig yolları", () => {
    if (!league || !team) throw new Error("fixture boş");
    expect(leaguePath("tr", league)).toBe("/tr/synthetic-league-alpha/");
    expect(teamPath("en", league, team)).toBe("/en/synthetic-league-alpha/dogu-bati-fk/");
  });
});

describe("hreflang (spec §8.3)", () => {
  it("bütün diller + x-default, kanonik kendi URL'si", () => {
    if (!league) throw new Error("fixture boş");
    const result = alternatesFor("tr", (lang) => leaguePath(lang, league));
    expect(result.canonical).toBe(`${SITE_URL}/tr/synthetic-league-alpha/`);
    expect(result.languages).toEqual({
      en: `${SITE_URL}/en/synthetic-league-alpha/`,
      tr: `${SITE_URL}/tr/synthetic-league-alpha/`,
      "x-default": `${SITE_URL}/${DEFAULT_LANG}/synthetic-league-alpha/`,
    });
  });
});
