import { describe, expect, it } from "vitest";
import en from "./en.json" with { type: "json" };
import tr from "./tr.json" with { type: "json" };

describe("sözlükler (spec §8.3)", () => {
  it("tr ve en aynı anahtar kümesini taşır, boş metin yok", () => {
    expect(Object.keys(tr).sort()).toEqual(Object.keys(en).sort());
    for (const text of [...Object.values(en), ...Object.values(tr)])
      expect(text.trim()).not.toBe("");
  });

  it("boş sicil metni spec §6.2'deki cümledir (AK2 onay kapsamında)", () => {
    expect(tr["record.emptyExplain"]).toBe(
      "Temel modelimiz kapanış piyasasını geçmediği için henüz tahmin yayımlamıyoruz. Tahmin yayını, önceden kaydedilecek bir kapanış değeri (CLV) ölçütü geçildiğinde başlayacak; o güne kadar defter oranları ve kapanışları kaydetmeye devam ediyor.",
    );
  });

  it("hiçbir arayüz metni 'yakında' vaadi ya da value önerisi taşımaz", () => {
    const all = [...Object.values(en), ...Object.values(tr)].join("\n").toLowerCase();
    for (const banned of [
      "yakında",
      "coming soon",
      "value bet",
      "tip of the day",
      "günün tahmini",
    ]) {
      expect(all).not.toContain(banned);
    }
  });
});
