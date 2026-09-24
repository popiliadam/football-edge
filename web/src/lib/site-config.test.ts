import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  indexingEnabled,
  isLang,
  LEDGER_HISTORY_URL,
  SITE_LANGS,
  SITE_NAME,
  SITE_URL,
} from "../../site.config.ts";

const WEB = resolve(import.meta.dirname, "../..");

// Dizin henüz yoksa (content/ T7'de, scripts/ T8'de gelir) boş sayılır; gelince kendiliğinden taranır.
function sources(dir: string): string[] {
  if (!existsSync(resolve(WEB, dir))) return [];
  return readdirSync(resolve(WEB, dir), { recursive: true, encoding: "utf8" })
    .filter((file) => /\.tsx?$/.test(file) && !/\.test\.tsx?$/.test(file))
    .map((file) => join(WEB, dir, file));
}

describe("site.config (spec §8.3, H7)", () => {
  it("indeksleme yalnız SITE_INDEXABLE=1 ile açılır", () => {
    expect(indexingEnabled({})).toBe(false);
    expect(indexingEnabled({ SITE_INDEXABLE: "0" })).toBe(false);
    expect(indexingEnabled({ SITE_INDEXABLE: "true" })).toBe(false);
    expect(indexingEnabled({ SITE_INDEXABLE: "1" })).toBe(true);
  });

  it("dil listesi yer tutucudur: en + tr (AK5 önerisi)", () => {
    expect(SITE_LANGS).toEqual(["en", "tr"]);
    expect(isLang("tr")).toBe(true);
    expect(isLang("de")).toBe(false);
  });
});

describe("yer tutucular tek kaynaktan (AK3, AK4)", () => {
  it("marka, alan adı ve çıpa adresi site.config.ts dışında literal olarak geçmez", () => {
    const files = ["src", "content", "scripts"].flatMap(sources);
    expect(files.length).toBeGreaterThan(10);
    for (const file of files) {
      const text = readFileSync(file, "utf-8");
      for (const literal of [SITE_NAME, SITE_URL, LEDGER_HISTORY_URL]) {
        expect(text.includes(literal), `${file} ${literal}`).toBe(false);
      }
    }
  });
});
