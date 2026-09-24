// T9 yeniden incelemesi, düzeltme turu 2 (task-9-rereview.md FP2, N1, N4–N7): asgari kırmızı girdiler.
// FP1/N2/N3 hardening.test.ts'in M9 bloğunda. Gerçek derleme kanıtları görev raporundadır.
import { describe, expect, it } from "vitest";
import { SITE_URL } from "../../site.config.ts";
import { licenseFindings, secretFindings } from "./checks.ts";
import {
  cssContentTexts,
  hostFindings,
  internal,
  linkFindings,
  scanWords,
  wordFindings,
} from "./content.ts";
import { entityFindings } from "./entities.ts";
import { ldStrings } from "./surface.ts";

const ld = (body: string) => `<script type="application/ld+json">${body}</script>`;
const DISCLAIMER = "Bu sitedeki hiçbir içerik bahis, finans ya da yatırım tavsiyesi değildir.";

describe("FP2 gizli anahtar: JWT biçimi", () => {
  it("CSP hash'indeki rastlantı eyJ geçer; JWT biçimi kırmızı", () => {
    expect(secretFindings("f", "'sha256-KC8lTj2kJpApP/uibxcDhyyeyJuTcci06K9A5o5Og74='")).toEqual(
      [],
    );
    const jwt = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiJ9.c2lnbmF0dXJlLXZhbHVl";
    expect(secretFindings("f", `key=${jwt}`)).toEqual(['f: gizli anahtar kalıbı "JWT" (H5)']);
  });
});

describe("N1 adlı HTML varlıkları", () => {
  it("React'in basmadığı her adlı varlık bulgu; amp/lt/gt/quot geçer", () => {
    expect(entityFindings("p", "<p>a &amp; b &lt; &gt; &quot; &#x27;</p>")).toEqual([]);
    expect(entityFindings("p", '<a href="/&sol;bet365.com/">x</a>')).toEqual([
      "p: adlı HTML varlığı &sol; (React yalnız &amp; &lt; &gt; &quot; basar)",
    ]);
    expect(entityFindings("p", "<p>&Unknownname;</p>")).toHaveLength(1);
  });

  it("çözülen hâl de denetlenir: &sol;/&bsol;/&Tab; dış bağlantı, &ZeroWidthSpace;/&NoBreak; sözcük", () => {
    for (const href of ["/&sol;bet365.com/", "/&bsol;bet365.com/", "/&Tab;/bet365.com/"]) {
      expect(linkFindings("p", `<a href="${href}">x</a>`).length).toBeGreaterThan(0);
    }
    const refresh = '<meta http-equiv="refresh" content="0;URL=/&sol;tracker.example/"/>';
    expect(linkFindings("p", refresh).length).toBeGreaterThan(0);
    expect(wordFindings("p", "<p>Pin&ZeroWidthSpace;nacle</p>")).toContain(
      'p: bahis şirketi adı "pinnacle"',
    );
    expect(licenseFindings("p", "<p>licen&NoBreak;sed</p>")).toHaveLength(1);
  });
});

describe("N4 JSON-LD ham okuma", () => {
  it("yinelenen anahtarın ilk değeri de taranır", () => {
    const body =
      '{"description":"Pinnacle value picks, officially licensed","description":"Match"}';
    expect(ldStrings(ld(body)).map((leaf) => leaf.value)).toContain(
      "Pinnacle value picks, officially licensed",
    );
    expect(wordFindings("p", ld(body))).toContain('p: bahis şirketi adı "pinnacle"');
    expect(licenseFindings("p", ld(body))).toHaveLength(1);
    const url = '{"url":"https://bookie.example/","url":"https://example.invalid/en/"}';
    expect(linkFindings("p", ld(url))).toContain("p: JSON-LD dış URL url=https://bookie.example/");
  });

  it("iki anahtara bölünmüş ad bitişik okunur", () => {
    const body = '{"sport":"Soccer","alternateName":"Pinn","disambiguatingDescription":"acle"}';
    expect(wordFindings("p", ld(body))).toContain('p: bahis şirketi adı "pinnacle"');
  });

  it("site URL'siyle başlayan, NBSP'li metin URL sayılmaz", () => {
    const nbsp = String.fromCharCode(0xa0);
    const text = `${SITE_URL}/${["", "Pinnacle", "value", "picks"].join(nbsp)}`;
    expect(internal(text)).toBe(false);
    expect(wordFindings("p", ld(JSON.stringify({ description: text })))).toContain(
      'p: bahis şirketi adı "pinnacle"',
    );
  });
});

describe("N5 RSC ve metin dosyalarında host", () => {
  it("izinsiz host kırmızı; site ve schema.org geçer", () => {
    expect(hostFindings("t", `x "${SITE_URL}/en/" "https://schema.org"`)).toEqual([]);
    expect(hostFindings("t", '"See https://tracker.example/x"')).toEqual([
      "t: izinsiz host tracker.example",
    ]);
  });
});

describe("N6 izinli cümle yalnız kendi başına", () => {
  it("cümle başında ya da ardında izinli; önüne ek anlamı çevirirse kırmızı", () => {
    expect(scanWords("p", [DISCLAIMER])).toEqual([]);
    expect(scanWords("p", [`Geçmiş performans geleceği göstermez. ${DISCLAIMER}`])).toEqual([]);
    const flipped = `Bu sayfa dışında, ${DISCLAIMER.charAt(0).toLowerCase()}${DISCLAIMER.slice(1)}`;
    expect(scanWords("p", [flipped])).toContain('p: öneri sözcüğü "tavsiye"');
    expect(scanWords("p", [`${DISCLAIMER.slice(0, -1)} ve kupon.`])).toContain(
      'p: öneri sözcüğü "tavsiye"',
    );
  });
});

describe("N7 yazım bozma ve CSS content", () => {
  it("aralıklı harfler ve tireli ad kırmızı", () => {
    expect(scanWords("p", ["Günün t a v s i y e s i: ev sahibi"])).toContain(
      'p: öneri sözcüğü "tavsiye"',
    );
    expect(scanWords("p", ["Best price at William-Hill"])).toContain(
      'p: bahis şirketi adı "william hill"',
    );
  });

  it("CSS content dizeleri okunur", () => {
    const css =
      ".a{color:red}.x::after{content:\"Bet365 value picks, licensed\"}.y::before{content:''}";
    expect(cssContentTexts(css)).toEqual(["Bet365 value picks, licensed", ""]);
  });
});
