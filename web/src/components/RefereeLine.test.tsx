import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RefereeLine } from "./RefereeLine.tsx";

describe("RefereeLine (spec 2026-10-02 §6)", () => {
  it("dolu hakem: kaynağı adıyla tek satır, iki dilde", () => {
    expect(renderToString(<RefereeLine name="Deniz Örnek" lang="tr" />)).toBe(
      "<p>Hakem: Deniz Örnek (TFF ataması)</p>",
    );
    expect(renderToString(<RefereeLine name="Deniz Örnek" lang="en" />)).toBe(
      "<p>Referee: Deniz Örnek (TFF appointment)</p>",
    );
  });

  it("null: HİÇBİR şey çizilmez (yer tutucu, 'yakında' yok)", () => {
    expect(renderToString(<RefereeLine name={null} lang="tr" />)).toBe("");
  });

  it("adın içindeki $& değiştirme kalıbı yorumlanmaz, & kaçırılır", () => {
    expect(renderToString(<RefereeLine name="A $& B" lang="en" />)).toBe(
      "<p>Referee: A $&amp; B (TFF appointment)</p>",
    );
  });
});
