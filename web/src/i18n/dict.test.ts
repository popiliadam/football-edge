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

  // İki katlama (son inceleme m1): düz `toLowerCase()` "YAKINDA"yı `yakinda`ya çevirir (noktasız ı
  // kaybolur); `toLocaleLowerCase("tr")` "COMING"i `comıng`e çevirir. Her yasak ifade ikisinde de aranır.
  it("hiçbir arayüz metni 'yakında' vaadi ya da value önerisi taşımaz", () => {
    const joined = [...Object.values(en), ...Object.values(tr)].join("\n");
    const folds = [joined.toLowerCase(), joined.toLocaleLowerCase("tr")];
    for (const banned of [
      "yakında",
      "coming soon",
      "value bet",
      "tip of the day",
      "günün tahmini",
    ]) {
      for (const all of folds) expect(all).not.toContain(banned);
    }
  });
});
