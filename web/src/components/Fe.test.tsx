import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Flag, Num, Txt } from "./Fe.tsx";
import { AnalysisSlot, ValueBadge } from "./Slots.tsx";

describe("Fe bileşenleri (H6c)", () => {
  it("Num: öznitelik ham değer, çocuk TEK metin (renderToString yorum düğümü koymaz)", () => {
    const html = renderToString(
      createElement(Num, { fe: "k", value: 40, kind: "pct1", lang: "tr" }),
    );
    expect(html).toBe('<span data-fe="k" data-fe-value="40">%40,0</span>');
  });

  it("Txt ve Flag", () => {
    expect(renderToString(createElement(Txt, { fe: "h", value: "abc" }))).toBe(
      '<code data-fe="h" data-fe-value="abc">abc</code>',
    );
    // Çocuk JSX ile verilir: Biome `noChildrenProp` prop olarak `children`ı reddeder,
    // `createElement`in üçüncü argümanı ise Flag'in zorunlu `children` tipini karşılamaz.
    expect(
      renderToString(
        <Flag fe="s" value={false}>
          Bekleniyor
        </Flag>,
      ),
    ).toBe('<span data-fe="s" data-fe-value="false">Bekleniyor</span>');
  });

  it("value ve analiz yuvaları null iken HİÇBİR şey çizmez (spec §7, §8.6)", () => {
    expect(renderToString(createElement(ValueBadge, { value: null }))).toBe("");
    expect(renderToString(createElement(AnalysisSlot, { value: null }))).toBe("");
  });
});
