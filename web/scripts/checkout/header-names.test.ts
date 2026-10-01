// DEFERRED 21d düzeltme turu 1 (inceleme I1): başlık adları büyük/küçük harfe duyarsızdır (Netlify
// belgesi) ve Netlify aynı adlı başlıkları TEK başlıkta birleştirir. `parseHeaders` ham listeyi
// tutar; bu yüzden (a) tüketiciler adı harfe duyarsız karşılaştırır, (b) bir blokta (birleşen
// bloklar dahil) yinelenen ad kırmızıdır — kabul edilen her `_headers`ta ham liste ile Netlify'ın
// sunduğu birleşik hâl ÇAKIŞIR. Eşi: `tests/test_site_web_publish.py` (yinelenen ad).
import { describe, expect, it } from "vitest";
import { fullFixture } from "../../src/lib/fixture.ts";
import { checkCsp, checkHeaderBlocks, checkIndexing, parseHeaders } from "./checks.ts";
import { expectedPages } from "./expect.ts";

const home = expectedPages(fullFixture()).find((each) => each.id === "home" && each.lang === "en");
if (!home) throw new Error("fixture ana sayfası yok");
const GLOBAL =
  "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n";
const CSP = "default-src 'self'; script-src 'self'";

describe("_headers başlık adları (harfe duyarsız, blokta tek)", () => {
  it("küçük harfli ikinci CSP: iki CSP başlığı ve yinelenen ad kırmızı", () => {
    const headers = parseHeaders(
      `${GLOBAL}\n/en/\n  Content-Security-Policy: ${CSP}\n  content-security-policy: default-src *\n`,
    );
    expect(checkCsp(home, "", headers)).toEqual(["/en/: 2 CSP başlığı"]);
    expect(checkHeaderBlocks(headers, ["/en/"])).toEqual([
      "_headers: /en/ bloğunda yinelenen başlık content-security-policy",
    ]);
  });

  it("/*'ta yinelenen X-Robots-Tag kırmızı (Netlify `noindex,noindex` sunardı)", () => {
    const headers = parseHeaders(`${GLOBAL}  X-Robots-Tag: noindex\n  x-robots-tag: noindex\n`);
    expect(checkHeaderBlocks(headers, [])).toEqual([
      "_headers: /* bloğunda yinelenen başlık x-robots-tag",
    ]);
  });

  it("aynı yolun iki bloğunda aynı ad da yinelenen sayılır", () => {
    const block = `/en/\n  Content-Security-Policy: ${CSP}\n`;
    const headers = parseHeaders(`${GLOBAL}\n${block}\n${block}`);
    expect(checkHeaderBlocks(headers, ["/en/"])).toEqual([
      "_headers: /en/ bloğunda yinelenen başlık content-security-policy",
    ]);
  });

  it("tüketiciler adı harfe duyarsız okur", () => {
    const lower = parseHeaders(`${GLOBAL.toLowerCase()}  x-robots-tag: noindex\n`);
    expect(checkHeaderBlocks(lower, [])).toEqual([]);
    const built = new Map([[home.path, '<meta name="robots" content="noindex"/>']]);
    expect(checkIndexing([home], built, "<urlset></urlset>", lower, "", false)).toEqual([]);
    expect(checkHeaderBlocks(parseHeaders(`${GLOBAL}  content-security-policy: x\n`), [])).toEqual([
      "_headers: /* bloğunda CSP",
    ]);
    expect(checkCsp(home, "", parseHeaders(`/en/\n  content-security-policy: ${CSP}\n`))).toEqual(
      [],
    );
  });
});
