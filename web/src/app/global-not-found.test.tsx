// DEFERRED 21c düzeltme turu 1 (inceleme M3): 404'ün görünür metni ve işaretlemesi artık bu depodaki
// `global-not-found.tsx`te; AK2 metin onayı beklenirken DEĞİŞMEZ. Beklenen işaretleme Next 16.3.6
// yerleşik 404'ünün (`builtin/global-not-found.js`) `renderToStaticMarkup` çıktısıdır, tek fark
// `<html lang="en">` (üretildi 2026-10-01, aşağıdaki tarifle). Next yükseltilirken yerleşik 404
// bu tarifle yeniden render edilip `fixtures/global-not-found.expected.html` ile karşılaştırılır.
//
// Yeniden üretim tarifi (son inceleme M-2). Bilerek yalnız YORUM: `web/` altında izlenen bir betik
// Next'in iç yolunu taşıyacağı için `test_web_sources_do_not_import_next_internals` bekçisini
// kırmızıya düşürür; yorum satırları o bekçiden muaftır. Aşağıdaki satırlar `//` önekleri
// atılarak depo DIŞINDA bir `.cjs` dosyasına yazılır, `node <dosya> <web dizini>` ile koşulur;
// çıktının ilk satırı Next sürümü, ikincisi fixture'la karşılaştırılacak işaretlemedir.
//   const { createRequire } = require("node:module");
//   const web = process.argv[2];
//   const req = createRequire(`${web}/package.json`);
//   const React = req("react");
//   const { renderToStaticMarkup } = req("react-dom/server");
//   const builtin = req("next/dist/client/components/builtin/global-not-found.js").default;
//   const tree = builtin();
//   const withLang = React.cloneElement(tree, { lang: "en" });
//   process.stdout.write(`${req("next/package.json").version}\n${renderToStaticMarkup(withLang)}\n`);
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
