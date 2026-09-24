// B-2 bütün-dal son incelemesi (final-review.md m1–m4; T9 yeniden inceleme 2 B1/B2/B4, x21): asgari
// kırmızı girdiler. Gerçek derleme kanıtları düzeltme raporundadır.
import { describe, expect, it } from "vitest";
import { secretFindings } from "./checks.ts";
import { scanWords, wordFindings } from "./content.ts";
import { entityFindings } from "./entities.ts";
import { flightTextRowFindings } from "./surface.ts";

describe("m1 'yakında' vaadi görünen metinde yok (spec §6.2, §7)", () => {
  it("Türkçe büyük harf ve İngilizce kırmızı; 'yakındaki' geçer", () => {
    expect(wordFindings("p", "<nav><a href='/tr/'>Sicil YAKINDA</a></nav>")).toEqual([
      'p: vaat ifadesi "yakinda"',
    ]);
    expect(scanWords("p", ["Yakında tahmin yayını"])).toEqual(['p: vaat ifadesi "yakinda"']);
    expect(scanWords("p", ["Predictions COMING SOON"])).toEqual(['p: vaat ifadesi "coming soon"']);
    expect(scanWords("p", ["Stadın yakındaki durağı"])).toEqual([]);
  });
});

describe("m2 `;`siz karakter başvurusu (B1/B2 kapalı kural)", () => {
  it("React'in bastığı dört ad ve `;` ile biten sayısal başvuru geçer", () => {
    expect(entityFindings("p", "<p>a &amp; b &lt; &gt; &quot; &#39; &#x27; &#X2F;</p>")).toEqual(
      [],
    );
    expect(entityFindings("p", "<script>if (a && b) x('&#47')</script>")).toEqual([]);
  });

  it("`;`siz sayısal ya da adlı başvuru ve çıplak `&` kırmızı", () => {
    expect(entityFindings("p", '<a href="/&#47evil.example/">x</a>')).toEqual([
      'p: izinsiz karakter başvurusu "&#47evil" (yalnız &amp; &lt; &gt; &quot; ve ; ile biten sayısal)',
    ]);
    for (const html of [
      '<a href="/&#x2Fevil.example/">x</a>',
      '<a href="/&#92evil.example/">x</a>',
      '<meta http-equiv="refresh" content="0;url=/&#47tracker.example/"/>',
      "<p>Pin&shynacle</p>",
      "<p>Pin&#xADnacle</p>",
      "<p>licen&shysed</p>",
      "<p>fish & chips</p>",
      "<p>&amp</p>",
    ]) {
      expect(entityFindings("p", html)).toHaveLength(1);
    }
  });

  it("adlı `;`li varlık eski iletiyle kalır", () => {
    expect(entityFindings("p", '<a href="/&sol;bet365.com/">x</a>')).toEqual([
      "p: adlı HTML varlığı &sol; (React yalnız &amp; &lt; &gt; &quot; basar)",
    ]);
  });
});

describe("m3 Supabase gizli anahtar biçimi", () => {
  it("sb_secret_ öneki kırmızı (belirteç parçalardan kurulur)", () => {
    const token = ["sb", "secret", "AbCdEfGhIjKlMnOpQrStUv"].join("_");
    expect(secretFindings("f", `key=${token}`)).toEqual([
      `f: gizli anahtar kalıbı "${["sb", "secret", ""].join("_")}" (H5)`,
    ]);
  });
});

describe("m4 React Flight T satırı tuzak teli (B4)", () => {
  it("satır başındaki `<id>:T<uzunluk>,` bulgu; tırnaklı dize ve düz satır geçer", () => {
    expect(flightTextRowFindings("f", '1:"$Sreact.fragment"\n99:T29,Pinnacle value picks')).toEqual(
      ["f: React Flight metin (T) satırı — sözcük taraması okumaz (B4 tuzak teli)"],
    );
    expect(flightTextRowFindings("f", "1a:T400,x")).toHaveLength(1);
    expect(flightTextRowFindings("f", '0:{"a":"1:T29,metin"}\n2:["$","p",null]')).toEqual([]);
  });
});
