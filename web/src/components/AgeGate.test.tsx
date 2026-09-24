import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  CONSENT_KEY,
  type ConsentStore,
  confirmGate,
  type GateDialog,
  giveConsent,
  hasConsent,
  openGateIfNeeded,
} from "../lib/consent.ts";
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

  it("onay yoksa kapı kipli açılır (showModal), varsa açılmaz", () => {
    const fresh = fakeDialog();
    expect(openGateIfNeeded(fresh, memoryStore())).toBe(true);
    expect(fresh.modalCalls).toBe(1);
    expect(fresh.open).toBe(true);

    const consented = memoryStore();
    consented.data.set(CONSENT_KEY, "1");
    const quiet = fakeDialog();
    expect(openGateIfNeeded(quiet, consented)).toBe(false);
    expect(quiet.modalCalls).toBe(0);

    const blocked = fakeDialog();
    expect(openGateIfNeeded(blocked, throwing)).toBe(true);
    expect(blocked.modalCalls).toBe(1);
    expect(openGateIfNeeded(null, memoryStore())).toBe(false);
  });

  it("onay düğmesi onayı yazar ve kapıyı kapatır; yazamazsa da kapatır", () => {
    const store = memoryStore();
    const dialog = fakeDialog();
    openGateIfNeeded(dialog, store);
    expect(confirmGate(dialog, store)).toBe(true);
    expect(store.data.get(CONSENT_KEY)).toBe("1");
    expect(dialog.open).toBe(false);
    expect(openGateIfNeeded(fakeDialog(), store)).toBe(false);

    const failing = fakeDialog();
    openGateIfNeeded(failing, throwing);
    expect(confirmGate(failing, throwing)).toBe(false);
    expect(failing.open).toBe(false);
  });
});

function fakeDialog(): GateDialog & { modalCalls: number } {
  return {
    open: false,
    modalCalls: 0,
    showModal() {
      this.open = true;
      this.modalCalls += 1;
    },
    close() {
      this.open = false;
    },
  };
}
