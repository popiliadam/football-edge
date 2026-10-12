import { describe, expect, it } from "vitest";
import { fullFixture } from "./fixture.ts";
import type { Snapshot } from "./snapshot-types.ts";
import { UPCOMING_LIMIT, upcomingMatches } from "./upcoming.ts";

// Ana sayfanın "yaklaşan maçlar" şeridi: dışa aktarım anından SONRA başlayan ve son turu görünen maçlar,
// başlama saatine (eşitlikte kimliğe) göre, en çok UPCOMING_LIMIT tane.
describe("upcomingMatches", () => {
  const snapshot = fullFixture();

  it("yalnız başlamamış ve son turu olan maçlar, saate göre sıralı", () => {
    const found = upcomingMatches(snapshot);
    expect(found.length).toBeGreaterThan(0);
    for (const match of found) {
      expect(Date.parse(match.commence_time)).toBeGreaterThan(Date.parse(snapshot.generated_at));
      expect(match.h2h.latest).not.toBeNull();
    }
    const times = found.map((match) => match.commence_time);
    expect([...times].sort()).toEqual(times);
  });

  it("son turu görünmeyen gelecek maç yaklaşan değildir", () => {
    const base = snapshot.matches.find((match) => match.h2h.latest !== null);
    if (!base) throw new Error("fixture son turlu maç taşımıyor");
    const blind = { ...base, id: "blind", commence_time: "2099-01-01T00:00:00Z" };
    const withBlind: Snapshot = {
      ...snapshot,
      matches: [...snapshot.matches, { ...blind, h2h: { ...blind.h2h, latest: null } }],
    };
    expect(upcomingMatches(withBlind).map((match) => match.id)).not.toContain("blind");
  });

  it("tam dışa aktarım anında başlayan maç yaklaşan değildir", () => {
    const edge = snapshot.matches.find((match) => match.commence_time === snapshot.generated_at);
    if (!edge) throw new Error("fixture sınır maçı taşımıyor");
    expect(upcomingMatches(snapshot).map((match) => match.id)).not.toContain(edge.id);
  });

  it("tavan uygulanır; eşit saatte kimlik sırası", () => {
    const base = snapshot.matches.find((match) => match.h2h.latest !== null);
    if (!base) throw new Error("fixture son turlu maç taşımıyor");
    const many: Snapshot = {
      ...snapshot,
      matches: Array.from({ length: UPCOMING_LIMIT + 3 }, (_, index) => ({
        ...base,
        id: `z${String(UPCOMING_LIMIT + 3 - index).padStart(2, "0")}`,
        commence_time: "2099-01-01T00:00:00Z",
      })),
    };
    const ids = upcomingMatches(many).map((match) => match.id);
    expect(UPCOMING_LIMIT).toBe(8);
    expect(ids).toHaveLength(8);
    expect([...ids].sort()).toEqual(ids);
  });
});
