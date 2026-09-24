import { describe, expect, it } from "vitest";
import { fullFixture } from "./fixture.ts";
import { breadcrumbLd, matchLd, pageLd, serializeLd } from "./jsonld.ts";

const snapshot = fullFixture();
const league = snapshot.leagues[0];
const byId = (n: number) => snapshot.matches[n];

describe("schema.org (spec §9)", () => {
  it("geçmiş maçta eventStatus YOK, gelecek maçta EventScheduled", () => {
    const past = byId(0);
    const future = snapshot.matches.find((match) => match.commence_time > snapshot.generated_at);
    if (!league || !past || !future) throw new Error("fixture boş");
    expect(matchLd(past, league, "/x/", snapshot.generated_at)).not.toHaveProperty("eventStatus");
    expect(matchLd(future, league, "/x/", snapshot.generated_at).eventStatus).toBe(
      "https://schema.org/EventScheduled",
    );
  });

  it("maç düğümü oran, teklif, konum taşımaz", () => {
    const match = byId(0);
    if (!league || !match) throw new Error("fixture boş");
    const node = matchLd(match, league, "/x/", snapshot.generated_at);
    for (const banned of ["offers", "location", "odds"]) expect(node).not.toHaveProperty(banned);
    expect(node["@type"]).toBe("SportsEvent");
  });

  it("tek blok: @graph, `<` kaçışlı", () => {
    const text = serializeLd(pageLd([breadcrumbLd([{ name: "</script><x>", path: "/en/" }])]));
    expect(text).not.toContain("</script>");
    expect(JSON.parse(text)["@graph"][0].itemListElement[0].name).toBe("</script><x>");
  });
});
