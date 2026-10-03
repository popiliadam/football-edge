// Check-out ad listesi hakemi taşır (spec 2026-10-02 §6): hakem adı veri metnidir, içindeki rakam bulgu değildir.
import { describe, expect, it } from "vitest";
import { fullFixture } from "../../src/lib/fixture.ts";
import { expectedPages } from "./expect.ts";
import { numberFindings } from "./numbers.ts";

const snapshot = fullFixture();
const match = snapshot.matches.find((each) => each.referee !== null);
if (!match) throw new Error("fixture hakemli maç taşımıyor");
const page = expectedPages(snapshot).find(
  (each) => each.id === `match:${match.id}` && each.lang === "en",
);
if (!page) throw new Error("hakemli maçın sayfası yok");

describe("check-out ad listesi hakemi taşır", () => {
  it("hakem adındaki rakam veri metnidir; yanına eklenen sayı kırmızı", () => {
    const named = {
      ...snapshot,
      matches: snapshot.matches.map((each) =>
        each.id === match.id ? { ...each, referee: "Ali 2 Veli" } : each,
      ),
    };
    expect(numberFindings(named, page, "<p>Referee: Ali 2 Veli (TFF appointment)</p>")).toEqual([]);
    expect(numberFindings(named, page, "<p>Referee: Ali 2 Veli (3)</p>")).toHaveLength(1);
  });
});
