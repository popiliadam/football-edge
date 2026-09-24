import { describe, expect, it } from "vitest";
import { fullFixture } from "./fixture.ts";
import { outcomeLabel } from "./outcome.ts";

const match = fullFixture().matches[0];

describe("sonuç etiketi (sicil tablosu)", () => {
  it("home → ev sahibi, away → deplasman, draw → sözlük etiketi", () => {
    if (!match) throw new Error("fixture boş");
    expect(outcomeLabel("home", match, "Beraberlik")).toBe(match.home);
    expect(outcomeLabel("away", match, "Beraberlik")).toBe(match.away);
    expect(outcomeLabel("draw", match, "Beraberlik")).toBe("Beraberlik");
  });

  it("maç anlık görüntüde yoksa ham değer (uydurma ad yok)", () => {
    expect(outcomeLabel("home", undefined, "Beraberlik")).toBe("home");
  });
});
