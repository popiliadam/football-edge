import { describe, expect, it } from "vitest";
import { indexingEnabled, isLang, SITE_LANGS } from "../../site.config.ts";

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
