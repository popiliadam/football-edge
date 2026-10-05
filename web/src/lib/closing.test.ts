import { describe, expect, it } from "vitest";
import { closingState } from "./closing.ts";

// DEFERRED 9.7g: başlamış ama kapanışı mühürlenmemiş maç "bekleniyor" demez — kapanış artık gelmez.
// Zaman, derlemenin tek saati olan anlık görüntünün `generated_at`idir (derleme deterministik kalır).
describe("closingState", () => {
  const at = "2026-10-05T12:00:00Z";

  it("mühürlü maç her zaman kaydedildi", () => {
    expect(closingState({ sealed: true, commence_time: "2026-10-01T18:00:00Z" }, at)).toBe(
      "sealed",
    );
    expect(closingState({ sealed: true, commence_time: "2026-10-09T18:00:00Z" }, at)).toBe(
      "sealed",
    );
  });

  it("başlamamış ya da tam başlama anındaki mühürsüz maç bekleniyor (boru hattı sınırı)", () => {
    expect(closingState({ sealed: false, commence_time: "2026-10-05T12:00:01Z" }, at)).toBe(
      "awaiting",
    );
    expect(closingState({ sealed: false, commence_time: at }, at)).toBe("awaiting");
  });

  it("başlama anı geçmiş mühürsüz maç kaydedilmedi", () => {
    expect(closingState({ sealed: false, commence_time: "2026-10-05T11:59:59Z" }, at)).toBe(
      "missed",
    );
    expect(closingState({ sealed: false, commence_time: "2026-09-19T17:00:00Z" }, at)).toBe(
      "missed",
    );
  });

  it("çözülemeyen zaman sessizce bekleniyor sayılmaz", () => {
    expect(() => closingState({ sealed: false, commence_time: "yok" }, at)).toThrow();
    expect(() => closingState({ sealed: false, commence_time: at }, "yok")).toThrow();
    expect(() => closingState({ sealed: true, commence_time: "yok" }, at)).toThrow();
  });
});
