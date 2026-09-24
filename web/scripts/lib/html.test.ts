import { describe, expect, it } from "vitest";
import {
  cspHash,
  decodeEntities,
  feElements,
  feOpenings,
  isExecutableInline,
  scriptOpenings,
  scripts,
  visibleText,
} from "./html.ts";

describe("dar HTML okuyucusu", () => {
  it("React'in kaçışlarını çözer (& ' \" < >)", () => {
    expect(decodeEntities("Doğu &amp; Batı &#x27;x&#x27; &quot;q&quot; &lt;&gt; &#39;")).toBe(
      "Doğu & Batı 'x' \"q\" <> '",
    );
  });

  it("data-fe öğesini, öznitelik adlarını küçük harfe katlayarak okur", () => {
    const html =
      '<p><span data-fe="a:b:c" data-fe-value="38">38.0%</span><time dateTime="x">t</time></p>';
    expect(feElements(html)).toEqual([
      { tag: "span", attrs: { "data-fe": "a:b:c", "data-fe-value": "38" }, text: "38.0%" },
    ]);
    expect(feOpenings(html)).toBe(1);
  });

  it("çocuğu metin olmayan data-fe öğesini OKUMAZ ama açılış sayımı onu görür", () => {
    const html = '<span data-fe="a:b:c" data-fe-value="1">1<!-- -->%</span>';
    expect(feElements(html)).toEqual([]);
    expect(feOpenings(html)).toBe(1);
  });

  it("betik sınıflandırması: src'li, JSON-LD ve yürütülebilir satır içi", () => {
    const html =
      '<script src="/a.js" async=""></script><script type="application/ld+json">{"a":1}</script><script>self.x=1</script>';
    const found = scripts(html);
    expect(found).toHaveLength(3);
    expect(scriptOpenings(html)).toBe(3);
    expect(found.map(isExecutableInline)).toEqual([false, false, true]);
    expect(cspHash("self.x=1")).toMatch(/^'sha256-[A-Za-z0-9+/]+=*'$/);
  });

  // Bilinen cevap: gövde UTF-8 baytlarıyla hash'lenir (tarayıcının hash'lediği baytlar). T9'un
  // CSP denetimi de `cspHash`i kullanır; kodlama hatası iki tarafta birden görünmez kalırdı.
  it("cspHash gövdeyi UTF-8 baytlarıyla hash'ler (bilinen cevap)", () => {
    expect(cspHash("ğ")).toBe("'sha256-L6+Iw9+lTlq3M+J90iY2FW2/N6egpt6X6W3mwOIrNIE='");
  });

  it("görünen metin betik ve yorum içermez", () => {
    expect(
      visibleText("<p>a<!-- x > y --></p><script>b</script><p>c &amp; d</p>")
        .replace(/\s+/g, " ")
        .trim(),
    ).toBe("a c & d");
  });
});
