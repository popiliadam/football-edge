// DEFERRED 21c düzeltme turu 1 (inceleme M3): 404'ün görünür metni ve işaretlemesi artık bu depodaki
// `global-not-found.tsx`te; AK2 metin onayı beklenirken DEĞİŞMEZ. Beklenen işaretleme Next 16.3.6
// yerleşik 404'ünün (`builtin/global-not-found.js`) `renderToStaticMarkup` çıktısıdır, tek fark
// `<html lang="en">` (üretildi 2026-10-01, oturum 10b U3 scratch'i `u3-r1-gen-404.cjs`). Next
// yükseltilirken yerleşik 404 yeniden render edilip bu dosyayla karşılaştırılır.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import GlobalNotFound from "./global-not-found.tsx";

const EXPECTED = resolve(import.meta.dirname, "../../fixtures/global-not-found.expected.html");

describe("404 sayfası (global-not-found)", () => {
  it("Next'in yerleşik 404'üyle aynı işaretleme ve metin, <html lang> varsayılan dil", () => {
    const expected = readFileSync(EXPECTED, "utf-8").trimEnd();
    expect(renderToStaticMarkup(<GlobalNotFound />)).toBe(expected);
  });
});
