// DEFERRED 20k/21d: `_headers`ın iki ayrıştırıcısı (bu `parseHeaders` ve Python'da
// `scripts/site_publish.py::parse_headers`) AYNI fixture'dan aynı sonucu çıkarır. Beklenen sonuç
// fixture'ın yanındadır: yol → küçük harfli ad → değer (Python'un biçimi; başlık adları büyük-küçük
// harfe duyarsızdır). Eşi: `tests/test_site_web_publish.py`.
// Netlify'ın belgelediği biçim (docs.netlify.com/manage/routing/headers): `#` ile başlayan satır
// yorumdur; aynı adlı başlıklar tek başlıkta virgülle birleşir (RFC 7230 §3.2.2). `parseHeaders`
// değerlerin HEPSİNİ sırasıyla tutar (yinelenen CSP `checkCsp`te görünür kalır); Netlify'ın sunduğu
// tek başlık buradaki birleştirmedir.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { type Headers, parseHeaders } from "./checks.ts";

const FIXTURES = resolve(import.meta.dirname, "../../fixtures");

// Bir bloğun Netlify'ın sunduğu hâli: aynı adlı başlıkların değerleri sırasıyla virgülle birleşir.
function served(pairs: readonly (readonly [string, string])[]): Record<string, string> {
  const values = new Map<string, string[]>();
  for (const [name, value] of pairs) {
    const key = name.toLowerCase();
    values.set(key, [...(values.get(key) ?? []), value]);
  }
  return Object.fromEntries([...values].map(([key, list]) => [key, list.join(",")]));
}

function normalized(headers: Headers): Record<string, Record<string, string>> {
  return Object.fromEntries([...headers].map(([path, pairs]) => [path, served(pairs)]));
}

describe("_headers ortak fixture", () => {
  it("TS ayrıştırıcısı Python'unkiyle aynı sonucu verir", () => {
    const text = readFileSync(resolve(FIXTURES, "headers.fixture.txt"), "utf-8");
    const expected = JSON.parse(
      readFileSync(resolve(FIXTURES, "headers.fixture.expected.json"), "utf-8"),
    );
    expect(normalized(parseHeaders(text))).toEqual(expected);
  });
});
