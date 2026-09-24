// Birim testlerinin ortak girdisi: B-2'nin dolu fixture'ı (tests/site_web_fixtures.py üretir).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseSnapshot } from "./snapshot.ts";
import type { Snapshot } from "./snapshot-types.ts";

export const FULL_FIXTURE = resolve(
  import.meta.dirname,
  "../../fixtures/snapshot.fixture.web-full.json",
);

export function fullFixtureText(): string {
  return readFileSync(FULL_FIXTURE, "utf-8");
}

export function fullFixture(): Snapshot {
  return parseSnapshot(fullFixtureText());
}
