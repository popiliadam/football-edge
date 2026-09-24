import { afterEach, describe, expect, it, vi } from "vitest";
import { SITE_URL } from "../../site.config.ts";
import { pageMetadata } from "./meta.ts";
import { homePath } from "./routes.ts";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("pageMetadata (H7, spec §8.4)", () => {
  it("bayrak kapalıyken kayıt indekslenebilir olsa da noindex", () => {
    vi.stubEnv("SITE_INDEXABLE", "");
    expect(pageMetadata("en", homePath, "t", true).robots).toEqual({ index: false });
  });

  it("bayrak açıkken kaydın indexable'ına göre", () => {
    vi.stubEnv("SITE_INDEXABLE", "1");
    expect(pageMetadata("en", homePath, "t", true).robots).toBeUndefined();
    expect(pageMetadata("en", homePath, "t", false).robots).toEqual({ index: false });
  });

  it("kanonik ve hreflang her sayfada", () => {
    const meta = pageMetadata("tr", homePath, "t", true);
    expect(meta.alternates?.canonical).toBe(`${SITE_URL}/tr/`);
    expect(Object.keys(meta.alternates?.languages ?? {}).sort()).toEqual(["en", "tr", "x-default"]);
  });
});
