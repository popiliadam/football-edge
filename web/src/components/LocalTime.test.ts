import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LocalTime, localLabel, utcLabel } from "./LocalTime.tsx";

// DEFERRED 20e, AK2 onayı (2026-10-02): yerel saat, hangi saat diliminde olduğunu adıyla söyler;
// betiksiz (sunucu) çıktı UTC'dir ve bunu da yazar.
const ISO = "2026-10-09T18:45:00Z";

describe("LocalTime (spec §7)", () => {
  it("betiksiz etiket UTC'dir ve adını taşır", () => {
    expect(utcLabel(ISO)).toBe("2026-10-09 18:45 UTC");
  });

  it("sunucu çıktısı UTC etiketidir; datetime değişmez", () => {
    expect(renderToStaticMarkup(createElement(LocalTime, { iso: ISO, lang: "en" }))).toBe(
      `<time dateTime="${ISO}">2026-10-09 18:45 UTC</time>`,
    );
  });

  // Aynı dil (`tr`, 24 saat) ve üç farklı saat: makinenin dilimi hangisi olursa olsun, dilimi yok
  // sayan bir çeviri en az ikisinde yanlış saati basar (`en` "9:45 PM" basar — karşılaştırmayı boşa
  // düşürürdü).
  it("yerel etiket verilen saat dilimine çevrilir ve dilimin adını gösterir", () => {
    const cases = [
      ["Europe/Istanbul", "21:45"],
      ["Europe/London", "19:45"],
      ["UTC", "18:45"],
    ] as const;
    for (const [zone, clock] of cases) {
      const label = localLabel(ISO, "tr", zone);
      expect(label).toContain(clock);
      expect(label.endsWith(` (${zone})`)).toBe(true);
    }
  });
});
