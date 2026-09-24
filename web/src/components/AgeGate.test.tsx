import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CONSENT_KEY, type ConsentStore, giveConsent, hasConsent } from "../lib/consent.ts";
import { AgeGate } from "./AgeGate.tsx";

const labels = { title: "T", body: "B", confirm: "C", leave: "L", strip: "STRIP-18" };

function memoryStore(): ConsentStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
  };
}

const throwing: ConsentStore = {
  getItem: () => {
    throw new Error("SecurityError");
  },
  setItem: () => {
    throw new Error("QuotaExceededError");
  },
};

describe("18+ kapısı (spec §10.2)", () => {
  it("sunucu çıktısında kapı gizli, içerik engellenmez, betiksiz şerit var", () => {
    const html = renderToStaticMarkup(createElement(AgeGate, { labels }));
    expect(html).toMatch(/<dialog\b/);
    expect(html).not.toMatch(/<dialog\b[^>]*\bopen\b/);
    expect(html).toContain("<noscript>");
    expect(html).toContain("STRIP-18");
  });

  it("onay yazılıp okunur", () => {
    const store = memoryStore();
    expect(hasConsent(store)).toBe(false);
    expect(giveConsent(store)).toBe(true);
    expect(store.data.get(CONSENT_KEY)).toBe("1");
    expect(hasConsent(store)).toBe(true);
  });

  it("depolama atarsa onay YOK sayılır (kapı yeniden gösterilir)", () => {
    expect(hasConsent(throwing)).toBe(false);
    expect(giveConsent(throwing)).toBe(false);
    expect(hasConsent(null)).toBe(false);
  });
});
