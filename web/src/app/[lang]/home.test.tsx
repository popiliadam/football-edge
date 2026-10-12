import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { FULL_FIXTURE, fullFixture } from "../../lib/fixture.ts";
import { upcomingMatches } from "../../lib/upcoming.ts";

// Ana sayfanın yaklaşan maçlar bölümü: renk anahtarı ekran okuyucudan gizli (yalnız şeridin anahtarı),
// her yaklaşan maç için bir satır ve bir şerit.
process.env.SITE_SNAPSHOT = FULL_FIXTURE;
const { default: HomePage } = await import("./page.tsx");

describe("ana sayfa — yaklaşan maçlar", () => {
  it("renk anahtarı aria-hidden; satır ve şerit sayısı kuralla aynı", async () => {
    const html = renderToStaticMarkup(await HomePage({ params: Promise.resolve({ lang: "en" }) }));
    expect(html).toMatch(/<p class="[^"]*legend[^"]*" aria-hidden="true">/);
    const count = upcomingMatches(fullFixture()).length;
    expect(count).toBeGreaterThan(0);
    expect([...html.matchAll(/<svg/g)]).toHaveLength(count);
  });
});
