import { describe, expect, it } from "vitest";
import { fullFixture, fullFixtureText } from "./fixture.ts";
import { loadSnapshot, parseSnapshot, SnapshotError } from "./snapshot.ts";

type Key = string | number;

function withChange(path: readonly Key[], value: unknown): string {
  const doc: unknown = JSON.parse(fullFixtureText());
  let node = doc as Record<Key, unknown>;
  for (const key of path.slice(0, -1)) node = node[key] as Record<Key, unknown>;
  node[path[path.length - 1] as Key] = value;
  return JSON.stringify(doc);
}

const fixture = fullFixture();
const firstLeagueSlug = fixture.leagues[0]?.slug;
const firstTeamSlug = fixture.teams[0]?.slug;
const firstPathId = fixture.matches[0]?.path_id;
const otherLeagueMatch = fixture.matches.findIndex(
  (match) => match.league_id !== fixture.matches[0]?.league_id,
);

describe("parseSnapshot — yönlendirmenin dayandığı değişmezler", () => {
  it("B-2 fixture'ını kabul eder", () => {
    expect(fixture.matches).toHaveLength(9);
  });

  it.each([
    ["ayrılmış lig slug'ı track-record", ["leagues", 0, "slug"], "track-record"],
    ["ayrılmış lig slug'ı legal", ["leagues", 0, "slug"], "legal"],
    ["ayrılmış lig slug'ı data", ["leagues", 0, "slug"], "data"],
    ["ayrılmış takım slug'ı", ["teams", 0, "slug"], "match"],
    ["lig slug'ı çakışıyor", ["leagues", 1, "slug"], firstLeagueSlug],
    ["takım slug'ı çakışıyor", ["teams", 1, "slug"], firstTeamSlug],
    ["path_id çakışıyor", ["matches", 1, "path_id"], firstPathId],
    ["maç yok", ["matches"], []],
    ["value_badge dolu (H3)", ["value_badge"], { pick: "home" }],
    ["analysis dolu", ["analysis"], "metin"],
    ["published ≠ girdi sayısı", ["record", "published"], 3],
    ["summary tutarsız", ["record", "summary"], null],
    ["schema_version", ["schema_version"], 2],
    ["maçın ligi yok", ["matches", 0, "league_id"], "yok.1"],
    ["takımın ligi yok", ["teams", 0, "league_id"], "yok.1"],
    ["path_id ligler arası çakışıyor", ["matches", otherLeagueMatch, "path_id"], firstPathId],
    ["lig slug'ı eğik çizgi", ["leagues", 0, "slug"], "a/b"],
    ["lig slug'ı ..", ["leagues", 0, "slug"], ".."],
    ["lig slug'ı boş", ["leagues", 0, "slug"], ""],
    ["lig slug'ı büyük harfli ayrılmış ad", ["leagues", 0, "slug"], "Data"],
    ["takım slug'ı büyük harfli ayrılmış ad", ["teams", 0, "slug"], "Match"],
    ["takım slug'ı yok", ["teams", 0, "slug"], undefined],
    ["takım adı yok", ["teams", 0, "name"], undefined],
    ["path_id biçimi", ["matches", 0, "path_id"], "ABC/../x"],
    ["maç slug'ı biçimi", ["matches", 0, "slug"], "a-vs-b/../c"],
    ["yasak anahtar (§4.3) maçta", ["matches", 0, "bookmaker"], "x"],
    ["yasak anahtar (§4.3) derinde", ["record", "entries", 0, "price"], 2.2],
    ["model alanı (H3) derinde", ["matches", 0, "h2h", "latest", "model_p"], 0.5],
    ["value alanı (H3)", ["leagues", 0, "value_pick"], "home"],
    ["maçlar dizi değil", ["matches"], {}],
    ["maç nesne değil", ["matches", 0], "x"],
    ["record yok", ["record"], undefined],
    ["record.entries dizi değil", ["record", "entries"], null],
    ["sicil girdisi nesne değil", ["record", "entries", 0], "x"],
  ] as const)("%s → SnapshotError", (_, path, value) => {
    expect(() => parseSnapshot(withChange(path, value))).toThrow(SnapshotError);
  });

  it.each([
    ["kök null", "null"],
    ["kök dizi", "[]"],
    ["JSON değil", "{"],
    ["NaN literali", fullFixtureText().replace("45.7", "NaN")],
    ["sonlu olmayan sayı (1e400)", fullFixtureText().replace("45.7", "1e400")],
  ])("%s → SnapshotError (TypeError değil)", (_, text) => {
    expect(() => parseSnapshot(text)).toThrow(SnapshotError);
  });

  it("SITE_SNAPSHOT yoksa varsayılan dosyaya DÜŞMEZ, adıyla düşer", () => {
    expect(() => loadSnapshot({})).toThrow(/SITE_SNAPSHOT tanımlı değil/);
  });
});
