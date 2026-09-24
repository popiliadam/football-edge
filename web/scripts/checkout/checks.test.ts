// Her kontrolün kırmızıya döndüğü asgari girdi (kendi mutasyon kanıtları). Gerçek derleme
// üzerindeki kırma-geri-yükleme kanıtları planın Task 9 adımlarındadır.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { SITE_URL } from "../../site.config.ts";
import { fullFixture } from "../../src/lib/fixture.ts";
import { parseSnapshot } from "../../src/lib/snapshot.ts";
import {
  checkA11y,
  checkCsp,
  checkFields,
  checkHeaderBlocks,
  checkIndexing,
  checkJsonLd,
  checkPages,
  contentFindings,
  licenseFindings,
  parseHeaders,
  secretFindings,
} from "./checks.ts";
import { type ExpectedPage, expectedPages, fieldKind } from "./expect.ts";

const snapshot = fullFixture();
const pages = expectedPages(snapshot);
const page = (id: string, lang = "en"): ExpectedPage => {
  const found = pages.find((each) => each.id === id && each.lang === lang);
  if (!found) throw new Error(`beklenen sayfa yok: ${id}`);
  return found;
};
const match = snapshot.matches[0];
if (!match) throw new Error("fixture boş");
const matchPage = page(`match:${match.id}`);
const span = (key: string, value: string, text: string) =>
  `<span data-fe="${key}" data-fe-value="${value}">${text}</span>`;

describe("beklenen sayfalar", () => {
  it("her dil × (ana, sicil, 4 yasal, lig, takım, maç)", () => {
    const perLang =
      2 + 4 + snapshot.leagues.length + snapshot.teams.length + snapshot.matches.length;
    expect(pages).toHaveLength(2 * perLang);
  });

  it("eşik altı tur alan üretmez; hareket yoksa hareket alanı yok", () => {
    const second = snapshot.matches.find((each) => each.h2h.opening === null);
    if (!second) throw new Error("fixture eşik altı açılış taşımıyor");
    const fields = page(`match:${second.id}`).fields;
    expect(fields.some((key) => key.includes("h2h.opening"))).toBe(false);
    expect(fields.some((key) => key.includes(":move."))).toBe(false);
  });

  it("bilinmeyen anahtarın biçimi yok", () => {
    expect(fieldKind(`match:${match.id}:h2h.opening.p.home`)).toBe("pct1");
    expect(fieldKind(`match:${match.id}:model_probability`)).toBeUndefined();
  });

  // T6 carry-in 6: sicil sayfasının anahtar kümesi dolu fixture'da 27, boşta 9.
  it("sicil anahtar kümesi: dolu 27, boş 9", () => {
    const empty = parseSnapshot(
      readFileSync(
        resolve(import.meta.dirname, "../../fixtures/snapshot.fixture.web-empty.json"),
        "utf-8",
      ),
    );
    expect(page("track-record").fields).toHaveLength(27);
    const emptyRecord = expectedPages(empty).find((each) => each.id === "track-record");
    expect(emptyRecord?.fields).toHaveLength(9);
  });
});

describe("(1) sayfa ↔ kayıt", () => {
  it("fazla sayfa ve yanlış data-fe-page kırmızı", () => {
    const built = [
      { path: "/en/", html: '<main data-fe-page="league:x"></main>' },
      { path: "/en/extra/", html: "<main></main>" },
    ];
    const findings = checkPages([page("home")], built);
    expect(findings).toEqual([
      "/en/: <main data-fe-page> home değil",
      "/en/extra/: anlık görüntüde kaydı olmayan sayfa",
    ]);
  });

  // T4 carry-in 14: eksik kayıtta `next build` o yola Next'in 404 sayfasını yazar ve 0 ile çıkar.
  it("beklenen yolda Next'in 404 sayfası kırmızı", () => {
    const notFound =
      '<html lang="en"><title>404: This page could not be found.</title><h1 class="next-error-h1">404</h1></html>';
    const findings = checkPages([page("home")], [{ path: "/en/", html: notFound }]);
    expect(findings).toContain("/en/: 404 sayfası (kayıt derlemede bulunamadı: home)");
    // Gerçek derlemede `notFound()` sayfası: gövdesiz hata kabuğu (params.ts mutasyonuyla ölçüldü).
    const shell = '<html id="__next_error__"><head><title>x</title></head><body></body></html>';
    expect(checkPages([page("home")], [{ path: "/en/", html: shell }])).toContain(
      "/en/: 404 sayfası (kayıt derlemede bulunamadı: home)",
    );
  });
});

describe("(2)(3) H6c alanlar", () => {
  const key = `match:${match.id}:h2h.opening.p.home`;
  const opening = match.h2h.opening;
  if (!opening) throw new Error("fixture açılışı null");
  const good = span(key, String(opening.p.home), "45.7%");

  it("öznitelik ≠ değer kırmızı", () => {
    const findings = checkFields(snapshot, matchPage, span(key, "45.8", "45.7%"));
    expect(findings.some((f) => f.includes("özniteliği 45.8 ≠ 45.7"))).toBe(true);
  });

  it("metin ≠ format(değer) kırmızı (yuvarlanmış ya da yanlış ayraç)", () => {
    const findings = checkFields(snapshot, matchPage, span(key, "45.7", "46%"));
    expect(findings.some((f) => f.includes('metni "46%" ≠ "45.7%"'))).toBe(true);
  });

  it("eksik alan kırmızı (sayfa bir sayıyı hiç basmazsa)", () => {
    const findings = checkFields(snapshot, matchPage, good);
    expect(findings.some((f) => f.includes("data-fe kümesi eksik"))).toBe(true);
  });

  it("okunamayan data-fe öğesi kırmızı", () => {
    const findings = checkFields(
      snapshot,
      matchPage,
      `<span data-fe="${key}" data-fe-value="45.7">45.7<!-- -->%</span>`,
    );
    expect(findings.some((f) => f.includes("okunamayan data-fe"))).toBe(true);
  });

  // T6 carry-in 7: aynı anahtar iki kez (eşit değerle) izinli; her öğe AYRI denetlenir.
  it("yinelenen anahtar izinli, ama her kopya ayrı denetlenir", () => {
    const team = snapshot.teams[0];
    if (!team) throw new Error("fixture takımsız");
    const teamPage = page(`team:${team.league_id}/${team.slug}`);
    const once = span(
      `team:${team.league_id}/${team.slug}:matches`,
      String(team.matches),
      String(team.matches),
    );
    expect(checkFields(snapshot, teamPage, once + once)).toEqual([]);
    const twice = good + good;
    const findings = checkFields(snapshot, matchPage, twice);
    expect(findings.some((f) => f.includes(key))).toBe(false);
    const drifted = checkFields(snapshot, matchPage, good + span(key, "45.7", "45.8%"));
    expect(drifted.some((f) => f.includes('metni "45.8%" ≠ "45.7%"'))).toBe(true);
  });

  // T3 carry-in 13: kimliğinde `:` taşıyan anahtar başka bir anahtarla çakışabilir → çözülmez.
  // Gevşek bir okuyucu (`[varlık, kimlik, yol] = split(":")`) `…:rounds:x`i `rounds`a çözerdi.
  it("üç bölütten fazla anahtar çözülemez (kırmızı)", () => {
    const colliding = `match:${match.id}:rounds:x`;
    const findings = checkFields(snapshot, matchPage, span(colliding, "9", "9"));
    expect(findings).toContain(`${matchPage.path}: çözülemeyen alan ${colliding}`);
    expect(fieldKind(colliding)).toBeUndefined();
  });

  // T5 carry-in 4: değeri öznitelikte olan alanın GÖRÜNEN etiketi de sözlüğe/kayda eşit.
  it("mühür etiketi takası kırmızı", () => {
    const sealed = `match:${match.id}:sealed`;
    const swapped = span(
      sealed,
      String(match.sealed),
      match.sealed ? "Pending" : "Closing recorded",
    );
    const findings = checkFields(snapshot, matchPage, swapped);
    expect(findings.some((f) => f.includes(`${sealed} etiketi`))).toBe(true);
  });

  it("sonuç etiketi takası kırmızı (yalnız öznitelik değil, görünen metin)", () => {
    const entry = snapshot.record.entries.find((each) => each.outcome === "home");
    if (!entry) throw new Error("fixture home sonucu taşımıyor");
    const key = `entry:${entry.publication_id}:outcome`;
    const findings = checkFields(snapshot, page("track-record"), span(key, "home", "Draw"));
    expect(findings.some((f) => f.includes(`${key} etiketi "Draw"`))).toBe(true);
  });
});

describe("(5) + H7 indeksleme", () => {
  const home = page("home");
  const built = new Map([[home.path, '<meta name="robots" content="noindex"/>']]);
  const headers = parseHeaders("/*\n  X-Robots-Tag: noindex\n");

  it("bayrak kapalı: noindex + X-Robots-Tag + boş site haritası geçer", () => {
    expect(checkIndexing([home], built, "<urlset></urlset>", headers, "Allow: /", false)).toEqual(
      [],
    );
  });

  it("robots.txt Disallow kırmızı", () => {
    const findings = checkIndexing(
      [home],
      built,
      "<urlset></urlset>",
      headers,
      "Disallow: /",
      false,
    );
    expect(findings).toContain("robots.txt: Disallow taşıyor (H7)");
  });

  it("bayrak kapalıyken indekslenebilir sayfa kırmızı", () => {
    const findings = checkIndexing(
      [home],
      new Map([[home.path, ""]]),
      "<urlset></urlset>",
      headers,
      "",
      false,
    );
    expect(findings.some((f) => f.includes("noindex=false"))).toBe(true);
  });

  // T8 M3: site haritası girdisi sayfanın <head>'iyle aynı alternatifleri taşır (x-default dahil).
  it("site haritası girdisinin alternatifleri eksik ya da yanlış ise kırmızı", () => {
    const url = (lang: string, path: string) =>
      `<xhtml:link rel="alternate" hreflang="${lang}" href="${SITE_URL}${path}" />`;
    const entry = (links: string) =>
      `<urlset><url><loc>${SITE_URL}/en/</loc>${links}</url></urlset>`;
    const open = new Map([[home.path, ""]]);
    const none = parseHeaders("/*\n  X-Content-Type-Options: nosniff\n");
    const full = url("en", "/en/") + url("tr", "/tr/") + url("x-default", "/en/");
    const ok = checkIndexing([home], open, entry(full), none, "", true);
    expect(ok).toEqual([]);
    const missing = checkIndexing(
      [home],
      open,
      entry(url("en", "/en/") + url("tr", "/tr/")),
      none,
      "",
      true,
    );
    expect(missing.some((f) => f.includes("sitemap.xml: alternatif"))).toBe(true);
    const wrong = url("en", "/en/") + url("tr", "/en/") + url("x-default", "/en/");
    const bad = checkIndexing([home], open, entry(wrong), none, "", true);
    expect(bad.some((f) => f.includes("sitemap.xml: alternatif"))).toBe(true);
  });
});

describe("(6) kalıplar", () => {
  it("H4: aksan ve büyük harf katlanır; işaretli olumsuzlama muaf", () => {
    expect(licenseFindings("p", "<p>RESMÎ VERİ kaynağı</p>")).toHaveLength(1);
    expect(licenseFindings("p", "<p>Lisanslı veri</p>")).toHaveLength(1);
    // Büyük harf Türkçe: `İ` NFKD'de `I` + nokta, `I` küçük harfte `i` — ikisi de `lisansli`ye katlanmalı.
    expect(licenseFindings("p", "<p>LİSANSLI veri</p>")).toHaveLength(1);
    expect(licenseFindings("p", "<p>LISANSLI veri</p>")).toHaveLength(1);
    expect(licenseFindings("p", '<p data-fe-allow="license-negation">not licensed</p>')).toEqual(
      [],
    );
  });

  // T7 carry-in 9: genişletilmiş liste; etiket ve satır kırması kalıbı bölmez.
  it("H4 genişletilmiş: licenced/authorised/resmî ortağı; etiketle bölünmüş kalıp", () => {
    expect(licenseFindings("p", "<p>a LICENCED feed</p>")).toHaveLength(1);
    expect(licenseFindings("p", "<p>Authorised data</p>")).toHaveLength(1);
    expect(licenseFindings("p", "<p>ligin RESMÎ ORTAĞIYIZ</p>")).toHaveLength(1);
    expect(licenseFindings("p", "<p>official <b>data</b></p>")).toHaveLength(1);
    expect(licenseFindings("p", "<p>official\n   partner</p>")).toHaveLength(1);
  });

  it("H5: JWT öneki ve bağlantı dizesi", () => {
    expect(secretFindings("f", "x eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2ln y")).toHaveLength(1);
    expect(secretFindings("f", "postgresql://u@h/db")).toHaveLength(1);
  });

  it("H1: tabandan eski tarih (ISO ve GG.AA.YYYY) ve görünen 'undefined'", () => {
    expect(contentFindings("p", "<p>2026-07-01</p>", snapshot.floor)).toHaveLength(1);
    expect(contentFindings("p", "<p>01.07.2026</p>", snapshot.floor)).toHaveLength(1);
    expect(contentFindings("p", "<p>2026-07-02</p>", snapshot.floor)).toEqual([]);
    expect(contentFindings("p", "<p>NaN%</p>", snapshot.floor)).toHaveLength(1);
  });
});

describe("(7) CSP", () => {
  const policy = (hashes: string) =>
    `${matchPage.path}\n  Content-Security-Policy: default-src 'self'; script-src 'self'${hashes}\n`;
  const headers = parseHeaders(policy(" 'sha256-Z='"));

  it("izin verilmeyen satır içi betik kırmızı", () => {
    expect(checkCsp(matchPage, "<script>a()</script>", headers)).toContain(
      `${matchPage.path}: CSP'nin izin vermediği satır içi betik`,
    );
  });

  it("CSP'siz sayfa kırmızı", () => {
    expect(checkCsp(page("home"), "", headers)).toEqual(["/en/: 0 CSP başlığı"]);
  });

  // T8 carry-in 11: küme BİREBİR — sayfada olmayan hash de kırmızı; hash UTF-8 baytlarıyla,
  // `cspHash`ten bağımsız hesaplanır (T8 I1: latin1 kodlaması iki tarafta birden görünmezdi).
  it("CSP kümesi birebir; hash UTF-8 (bilinen cevap)", () => {
    const utf8 = " 'sha256-L6+Iw9+lTlq3M+J90iY2FW2/N6egpt6X6W3mwOIrNIE='";
    const latin1 = " 'sha256-/+Z5u4MclbZ9wXgZxjxQkNIhqsb0x79TD1lKtD0h+h4='";
    expect(checkCsp(matchPage, "<script>ğ</script>", parseHeaders(policy(utf8)))).toEqual([]);
    expect(checkCsp(matchPage, "<script>ğ</script>", parseHeaders(policy(latin1)))).toContain(
      `${matchPage.path}: CSP'nin izin vermediği satır içi betik`,
    );
    expect(checkCsp(matchPage, "", headers)).toEqual([
      `${matchPage.path}: CSP'de sayfada olmayan hash 'sha256-Z='`,
    ]);
  });

  it("JSON-LD hash'i CSP'de ise ve unsafe-inline kırmızı", () => {
    const body = "{}";
    const ldHash = " 'sha256-RBNvo1WzZ4oRRq0W9+hknpT7T8If536DEMBg9hyq/4o='";
    const html = `<script type="application/ld+json">${body}</script>`;
    expect(checkCsp(matchPage, html, parseHeaders(policy(ldHash)))).toContain(
      `${matchPage.path}: JSON-LD hash'i CSP'de (gereksiz)`,
    );
    expect(checkCsp(matchPage, "", parseHeaders(policy(" 'unsafe-inline'")))).toContain(
      `${matchPage.path}: CSP 'unsafe-' taşıyor`,
    );
  });

  it("_headers blokları: /* CSP'siz ve güvenlik başlıklı; sayfasız ya da yinelenen blok kırmızı", () => {
    const global =
      "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n";
    const csp = (path: string) => `${path}\n  Content-Security-Policy: default-src 'self'\n`;
    expect(checkHeaderBlocks(parseHeaders(`${global}\n${csp("/en/")}`), ["/en/"])).toEqual([]);
    expect(checkHeaderBlocks(parseHeaders(`${csp("/en/")}`), ["/en/"])).toContain(
      "_headers: /* bloğu yok ya da X-Content-Type-Options: nosniff eksik",
    );
    expect(
      checkHeaderBlocks(parseHeaders(`${global}  Content-Security-Policy: x\n`), []),
    ).toContain("_headers: /* bloğunda CSP");
    expect(checkHeaderBlocks(parseHeaders(`${global}\n${csp("/gone/")}`), ["/en/"])).toContain(
      "_headers: sayfası olmayan blok /gone/",
    );
    const twice = parseHeaders(`${global}\n${csp("/en/")}\n${csp("/en/")}`);
    expect(checkCsp(page("home"), "", twice)).toEqual(["/en/: 2 CSP başlığı"]);
  });
});

describe("(8) erişilebilirlik ve §9 JSON-LD", () => {
  it("lang uyuşmazlığı, iki h1, başlık atlaması, <main> yokluğu kırmızı", () => {
    const findings = checkA11y(matchPage, '<html lang="tr"><h1>a</h1><h1>b</h1><h3>c</h3>');
    expect(findings).toHaveLength(4);
  });

  it("iki JSON-LD bloğu ya da yanlış tür kırmızı", () => {
    const ld = (body: string) => `<script type="application/ld+json">${body}</script>`;
    expect(checkJsonLd(snapshot, matchPage, ld("{}") + ld("{}"))).toEqual([
      `${matchPage.path}: 2 JSON-LD bloğu`,
    ]);
    const wrong = ld(JSON.stringify({ "@graph": [{ "@type": "WebSite" }] }));
    expect(checkJsonLd(snapshot, matchPage, wrong)[0]).toContain("JSON-LD türleri");
  });
});
