import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { fullFixture } from "../lib/fixture.ts";
import { RoundsTable } from "./RoundsTable.tsx";

// Şerit satırı: veri satırının ARDINDAN, tek hücre beş sütunu kaplar, hücre ekran okuyucudan gizli;
// başlık hücresine girmez (check-out'un eksik tur kalıbı `<th>…</th><td colspan="4">`ye değmez).
describe("RoundsTable şerit satırları", () => {
  const snapshot = fullFixture();
  const match = snapshot.matches.find(
    (each) => each.h2h.opening !== null && each.h2h.latest !== null && each.h2h.closing !== null,
  );
  if (!match) throw new Error("fixture üç turu dolu maç taşımıyor");
  const html = renderToStaticMarkup(
    <RoundsTable match={match} lang="en" generatedAt={snapshot.generated_at} />,
  );

  it("dolu her tur için bir şerit satırı, colspan 5, aria-hidden hücrede", () => {
    const bars = [...html.matchAll(/<tr[^>]*><td colSpan="5" aria-hidden="true"><svg/g)];
    expect(bars).toHaveLength(3);
    expect(html).not.toMatch(/<th[^>]*>[^<]*<svg/);
  });

  it("eksik tur şerit satırı almaz", () => {
    const partial = snapshot.matches.find((each) => each.h2h.opening === null);
    if (!partial) throw new Error("fixture açılışı eksik maç taşımıyor");
    const shown = (["opening", "latest", "closing"] as const).filter(
      (round) => partial.h2h[round] !== null,
    ).length;
    const out = renderToStaticMarkup(
      <RoundsTable match={partial} lang="en" generatedAt={snapshot.generated_at} />,
    );
    expect([...out.matchAll(/<svg/g)]).toHaveLength(shown);
  });
});
