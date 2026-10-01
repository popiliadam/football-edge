// DEFERRED 20k: `_headers`ın iki ayrıştırıcısı (bu `parseHeaders` ve Python'da
// `scripts/site_publish.py::parse_headers`) AYNI fixture'dan aynı sonucu çıkarır. Beklenen sonuç
// fixture'ın yanındadır: yol → küçük harfli ad → değer (Python'un biçimi; başlık adları büyük-küçük
// harfe duyarsızdır). Eşi: `tests/test_site_web_publish.py`.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { type Headers, parseHeaders } from "./checks.ts";

const FIXTURES = resolve(import.meta.dirname, "../../fixtures");

function normalized(headers: Headers): Record<string, Record<string, string>> {
  return Object.fromEntries(
    [...headers].map(([path, pairs]) => [
      path,
      Object.fromEntries(pairs.map(([name, value]) => [name.toLowerCase(), value])),
    ]),
  );
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
