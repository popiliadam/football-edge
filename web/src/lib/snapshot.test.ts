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

describe("parseSnapshot — yönlendirmenin dayandığı değişmezler", () => {
  it("B-2 fixture'ını kabul eder", () => {
    expect(fixture.matches).toHaveLength(6);
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
  ] as const)("%s → SnapshotError", (_, path, value) => {
    expect(() => parseSnapshot(withChange(path, value))).toThrow(SnapshotError);
  });

  it("SITE_SNAPSHOT yoksa varsayılan dosyaya DÜŞMEZ, adıyla düşer", () => {
    expect(() => loadSnapshot({})).toThrow(/SITE_SNAPSHOT tanımlı değil/);
  });
});
