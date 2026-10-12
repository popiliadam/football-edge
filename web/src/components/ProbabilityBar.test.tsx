import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ProbabilityBar } from "./ProbabilityBar.tsx";

// Görsel şerit: sayılar tabloda kalır; şerit metin taşımaz, ekran okuyucudan gizlidir ve satır içi
// stil kullanmaz (CSP `style-src 'self'`) — genişlikler SVG öznitelikleridir.
describe("ProbabilityBar", () => {
  const html = renderToString(<ProbabilityBar p={{ home: 45.7, draw: 27.1, away: 27.2 }} />);

  it("dekoratif: aria-hidden, metin yok, style özniteliği yok", () => {
    expect(html).toContain('aria-hidden="true"');
    expect(html.replace(/<[^>]*>/g, "")).toBe("");
    expect(html).not.toContain("style=");
  });

  it("üç parça ev → beraberlik → deplasman, toplamı tam genişlik", () => {
    const rects = [...html.matchAll(/<rect x="([\d.]+)" y="0" width="([\d.]+)"/g)].map((m) => [
      Number(m[1]),
      Number(m[2]),
    ]);
    expect(rects).toHaveLength(3);
    expect(rects[0]?.[0]).toBe(0);
    expect(rects[1]?.[0]).toBeCloseTo(rects[0]?.[1] ?? 0, 6);
    const end = (rects[2]?.[0] ?? 0) + (rects[2]?.[1] ?? 0);
    expect(end).toBeCloseTo(100, 6);
    expect(rects[0]?.[1]).toBeCloseTo((45.7 / 100) * 100, 6);
  });

  it("toplam 100 değilse orantılanır; sıfır toplam çizilmez", () => {
    const scaled = renderToString(<ProbabilityBar p={{ home: 1, draw: 1, away: 2 }} />);
    const widths = [...scaled.matchAll(/width="([\d.]+)"/g)].map((m) => Number(m[1]));
    expect(widths).toEqual([25, 25, 50]);
    expect(renderToString(<ProbabilityBar p={{ home: 0, draw: 0, away: 0 }} />)).toBe("");
  });
});
