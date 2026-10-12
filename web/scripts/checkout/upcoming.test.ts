// Denetçinin ana sayfa kuralı (`numbers.upcomingOf`) ve ana sayfa denetimi (`content.homeFindings`).
// İzin listesi tek yönlüdür (fazlası bulgu vermez); bu yüzden kural burada birebir sabitlenir.
import { describe, expect, it } from "vitest";
import { fullFixture } from "../../src/lib/fixture.ts";
import type { Snapshot } from "../../src/lib/snapshot-types.ts";
import { homeFindings } from "./content.ts";
import { expectedPages } from "./expect.ts";
import { upcomingOf, utcText } from "./numbers.ts";

const snapshot = fullFixture();
const home = expectedPages(snapshot).find((page) => page.id === "home" && page.lang === "en");
if (!home) throw new Error("ana sayfa beklenmiyor");

describe("upcomingOf (denetçi)", () => {
  it("fixture: başlamamış, son turlu iki maç, saate göre; sınırdaki maç dışarıda", () => {
    expect(upcomingOf(snapshot).map((match) => match.commence_time)).toEqual([
      "2026-09-26T18:00:00Z",
      "2026-09-27T13:00:00Z",
    ]);
  });

  it("son turu olmayan gelecek maç ve tavan: en çok 8, saat + kimlik sırası", () => {
    const base = snapshot.matches.find((match) => match.h2h.latest !== null);
    if (!base) throw new Error("fixture son turlu maç taşımıyor");
    const later = (index: number) => ({
      ...base,
      id: `m${String(index).padStart(2, "0")}`,
      commence_time: "2099-01-01T00:00:00Z",
    });
    const many: Snapshot = {
      ...snapshot,
      matches: [
        { ...later(0), h2h: { ...base.h2h, latest: null } },
        ...[12, 11, 10, 9, 8, 7, 6, 5, 4, 3].map(later),
      ],
    };
    expect(upcomingOf(many).map((match) => match.id)).toEqual([
      "m03",
      "m04",
      "m05",
      "m06",
      "m07",
      "m08",
      "m09",
      "m10",
    ]);
  });
});

describe("homeFindings: ana sayfanın yaklaşan maç saatleri kuralla birebir", () => {
  const time = (iso: string) => `<time dateTime="${iso}">${utcText(iso)}</time>`;
  const page = (times: string[]) =>
    `<main><ul>${times.map((iso) => `<li>${time(iso)}</li>`).join("")}</ul></main>`;
  const want = upcomingOf(snapshot).map((match) => match.commence_time);

  it("birebir geçer; eksik, fazla ya da sırası bozuk kırmızı", () => {
    expect(homeFindings(snapshot, home, page(want))).toEqual([]);
    expect(homeFindings(snapshot, home, page(want.slice(1)))).toHaveLength(1);
    expect(homeFindings(snapshot, home, page([...want, "2026-09-28T13:00:00Z"]))).toHaveLength(1);
    expect(homeFindings(snapshot, home, page([...want].reverse()))).toHaveLength(1);
  });

  it("bölüm tümden silinirse kırmızı (yaklaşan maç varken)", () => {
    expect(homeFindings(snapshot, home, "<main><p>x</p></main>")[0]).toContain("yaklaşan maç");
  });

  it("ana sayfa dışında sessiz", () => {
    const other = expectedPages(snapshot).find((each) => each.kind === "league");
    if (!other) throw new Error("lig sayfası beklenmiyor");
    expect(homeFindings(snapshot, other, "<main></main>")).toEqual([]);
  });
});
