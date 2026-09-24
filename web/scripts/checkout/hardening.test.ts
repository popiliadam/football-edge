// T9 incelemesi düzeltme turu 1 (task-9-review.md I1–I4, M1–M9): her hayatta kalan saldırının
// asgari kırmızı girdisi. Gerçek derleme kopyalarındaki kanıtlar görev raporundadır.
import { describe, expect, it } from "vitest";
import { SITE_URL } from "../../site.config.ts";
import { t } from "../../src/i18n/dict.ts";
import { fullFixture } from "../../src/lib/fixture.ts";
import {
  checkIndexing,
  checkJsonLd,
  checkRobots,
  inlineScriptFindings,
  licenseFindings,
  parseHeaders,
} from "./checks.ts";
import { draftFindings, linkFindings, stateFindings, utcText, wordFindings } from "./content.ts";
import { type ExpectedPage, expectedPages } from "./expect.ts";
import { frameworkNumberFindings, numberFindings } from "./numbers.ts";
import { nextPushes, rscLinks, rscStrings } from "./surface.ts";

const snapshot = fullFixture();
const pages = expectedPages(snapshot);
const page = (id: string, lang = "en"): ExpectedPage => {
  const found = pages.find((each) => each.id === id && each.lang === lang);
  if (!found) throw new Error(`beklenen sayfa yok: ${id}`);
  return found;
};
const league = snapshot.leagues[0];
const match = snapshot.matches.find((each) => each.league_id === league?.id);
if (!league || !match) throw new Error("fixture boş");
const leaguePage = page(`league:${league.id}`);
const matchPage = page(`match:${match.id}`);
const ld = (data: object) => `<script type="application/ld+json">${JSON.stringify(data)}</script>`;

describe("I1 izinli cümle TAM cümledir", () => {
  it("boş sicil açıklaması geçer; 'closing line value picks' kırmızı", () => {
    expect(wordFindings("p", `<p>${t("en", "record.emptyExplain")}</p>`)).toEqual([]);
    expect(wordFindings("p", "<p>Our closing line value picks: back the home side</p>")).toContain(
      'p: öneri sözcüğü "value"',
    );
  });
});

describe("I2 <time> muafiyeti yalnız anlık görüntü zamanına", () => {
  const time = (iso: string, text: string) => `<p><time dateTime="${iso}">${text}</time></p>`;

  it("sayfanın zamanı + UTC metni geçer; başka metin ya da zaman kırmızı", () => {
    const iso = match.commence_time;
    expect(numberFindings(snapshot, matchPage, time(iso, utcText(iso)))).toEqual([]);
    expect(numberFindings(snapshot, matchPage, time(iso, "Odds 2.15"))).toContain(
      `${matchPage.path}: data-fe dışında sayı "2.15" ("Odds 2.15")`,
    );
    const other = "2026-09-21T18:30:00Z";
    expect(numberFindings(snapshot, matchPage, time(other, utcText(other))).length).toBeGreaterThan(
      0,
    );
  });

  it("maç sayfasında başlama anı commence_time ile eşleşmeli", () => {
    const wrong = `<main>${time(match.commence_time, "2026-09-21 18:30 UTC")}</main>`;
    expect(stateFindings(snapshot, matchPage, wrong)).toContain(
      `${matchPage.path}: başlama anı <time> commence_time ile eşleşmiyor`,
    );
  });
});

describe("I3 JSON-LD, meta ve öznitelik yüzeyleri", () => {
  it("JSON-LD dizesi, meta içeriği, placeholder ve aria-* taranır", () => {
    const inLd = ld({ "@graph": [{ description: "Bet365 value bets, official data partner" }] });
    expect(wordFindings("p", inLd)).toContain('p: bahis şirketi adı "bet365"');
    expect(licenseFindings("p", inLd)).toContain('p: lisans iddiası kalıbı "official data" (H4)');
    const meta = '<meta name="description" content="Pinnacle edge"/>';
    expect(wordFindings("p", meta)).toContain('p: öneri sözcüğü "edge"');
    expect(wordFindings("p", '<input placeholder="Search Bet365"/>')).toContain(
      'p: bahis şirketi adı "bet365"',
    );
    expect(wordFindings("p", '<div aria-description="value picks"></div>')).toContain(
      'p: öneri sözcüğü "value"',
    );
  });

  it("meta ve JSON-LD description'daki sayı kırmızı", () => {
    const meta = '<meta name="description" content="Home 2.15"/>';
    expect(numberFindings(snapshot, matchPage, meta)).toHaveLength(1);
    expect(numberFindings(snapshot, matchPage, ld({ description: "at 2.15" }))).toHaveLength(1);
  });
});

describe("I4 Türkçe value/tavsiye dağarcığı", () => {
  it("değer bahsi, valör, banko, tavsiye, kupon, iddaa (büyük harf dahil) kırmızı", () => {
    for (const [text, word] of [
      ["Günün değer bahsi burada", "deger bahs"],
      ["GÜNÜN VALÖRÜ", "valor"],
      ["Günün banko tavsiyesi", "banko"],
      ["BAHİS TAVSİYESİ", "tavsiye"],
      ["Kuponunu yap", "kupon"],
      ["İDDAA oranları", "iddaa"],
    ]) {
      expect(wordFindings("p", `<p>${text}</p>`)).toContain(`p: öneri sözcüğü "${word}"`);
    }
  });

  it("sözlükteki ve yasal taslaktaki sorumluluk reddi TAM cümle olarak geçer", () => {
    const disclaimer = "Bu sitedeki hiçbir içerik bahis, finans ya da yatırım tavsiyesi değildir.";
    expect(wordFindings("p", `<p>${t("tr", "home.intro")}</p><p>${disclaimer}</p>`)).toEqual([]);
    expect(wordFindings("p", "<p>Bu sitedeki içerik bahis tavsiyesidir.</p>")).toContain(
      'p: öneri sözcüğü "tavsiye"',
    );
  });
});

describe("M1 bağlantı normalleştirme", () => {
  it("ters eğik çizgi, gömülü sekme ve meta refresh url= kırmızı", () => {
    expect(linkFindings("p", '<a href="/\\bet365.com/">x</a>')).toContain(
      'p: dış bağlantı href="/\\bet365.com/"',
    );
    expect(linkFindings("p", '<a href="/&#9;/bet365.com/">x</a>').length).toBeGreaterThan(0);
    const refresh = '<meta http-equiv="refresh" content="0;url=/\\bet365.com/"/>';
    expect(linkFindings("p", refresh)).toContain(
      'p: dış bağlantı meta refresh url="/\\bet365.com/"',
    );
    expect(linkFindings("p", '<meta http-equiv="refresh" content="0;url=/en/"/>')).toEqual([]);
  });
});

describe("M2 biçim karakterleri ve bölünmüş sözcük", () => {
  it("boş öğeyle bölünmüş ya da sıfır genişlikli/yumuşak tireli sözcük kırmızı", () => {
    expect(wordFindings("p", "<p>Pinn<span></span>acle</p>")).toContain(
      'p: bahis şirketi adı "pinnacle"',
    );
    expect(wordFindings("p", "<p>val<b></b>ue picks</p>")).toContain('p: öneri sözcüğü "value"');
    expect(wordFindings("p", "<p>Pin\u200bnacle</p>")).toContain('p: bahis şirketi adı "pinnacle"');
    expect(licenseFindings("p", "<p>licen<i></i>sed</p>")).toHaveLength(1);
    expect(licenseFindings("p", "<p>licen&shy;sed</p>")).toHaveLength(1);
    expect(numberFindings(snapshot, leaguePage, "<p>10<i></i>.90</p>")).toContain(
      `${leaguePage.path}: data-fe dışında sayı "10.90" ("10.90")`,
    );
  });
});

describe("M3 kapalı <details>", () => {
  const draft = t("en", "legal.draft");
  it("kapalı details içindeki TASLAK görünür sayılmaz; açık details ya da özet görünür", () => {
    const legal = page("legal:terms");
    const css = () => "";
    const closed = `<main><details><summary>x</summary><p>${draft}</p></details></main>`;
    expect(draftFindings(legal, closed, css)[0]).toContain("görünür TASLAK işareti 0");
    expect(draftFindings(legal, closed.replace("<details>", '<details open="">'), css)).toEqual([]);
    const summary = `<main><details><summary>${draft}</summary></details></main>`;
    expect(draftFindings(legal, summary, css)).toEqual([]);
  });
});

describe("M4 site haritası ve robots.txt", () => {
  const home = page("home");
  const open = new Map([[home.path, ""]]);
  const none = parseHeaders("/*\n  X-Content-Type-Options: nosniff\n");
  const links = ["en", "tr", "x-default"]
    .map((lang) => {
      const path = lang === "tr" ? "/tr/" : "/en/";
      return `<xhtml:link rel="alternate" hreflang="${lang}" href="${SITE_URL}${path}" />`;
    })
    .join("");
  const entry = (url: string, extra = "") =>
    `<${url}><loc>${SITE_URL}/en/</loc>${extra}${links}</url>`;

  it("<url > yazımı ve girdi içinde ikinci <loc> kırmızı", () => {
    expect(checkIndexing([home], open, `<urlset>${entry("url")}</urlset>`, none, "", true)).toEqual(
      [],
    );
    const spaced = `<urlset>${entry("url")}${entry("url ").replace("/en/</loc>", "/en/legal/terms/</loc>")}</urlset>`;
    expect(checkIndexing([home], open, spaced, none, "", true)[0]).toContain("sitemap.xml:");
    const second = `<urlset>${entry("url", `<loc>${SITE_URL}/en/legal/terms/</loc>`)}</urlset>`;
    expect(checkIndexing([home], open, second, none, "", true)).toContain(
      "sitemap.xml: 2 <loc>, 1 <url> (girdi başına tam bir)",
    );
  });

  it("robots.txt birebir; ikinci Sitemap satırı kırmızı", () => {
    const robots = `User-Agent: *\nAllow: /\n\nSitemap: ${SITE_URL}/sitemap.xml\n`;
    expect(checkRobots(robots)).toEqual([]);
    expect(checkRobots(`${robots}Sitemap: ${SITE_URL}/sitemap-2.xml\n`)).toHaveLength(1);
  });
});

describe("M5–M7 sayı kuralı", () => {
  it("ASCII olmayan rakamlar (Arap-Hint, tam genişlik) kırmızı", () => {
    expect(numberFindings(snapshot, matchPage, "<p>Price ٢٫١٥</p>")).toHaveLength(1);
    const wide = numberFindings(snapshot, matchPage, "<p>Price ２．１５</p>");
    expect(wide).toHaveLength(1);
    expect(wide[0]).toContain('data-fe dışında sayı "2.15"');
  });

  it("10/90/18/404 yalnız kendi bağlamında", () => {
    expect(numberFindings(snapshot, leaguePage, `<dt>${t("en", "league.p90")}</dt>`)).toEqual([]);
    for (const text of ["Home win chance 90%", "Stake 10 units", "Odds 18/10", "404"]) {
      expect(numberFindings(snapshot, leaguePage, `<p>${text}</p>`).length).toBeGreaterThan(0);
    }
    expect(numberFindings(snapshot, page("home"), `<p>${t("en", "league.p10")}</p>`)).toHaveLength(
      1,
    );
    expect(frameworkNumberFindings("/404.html", "<h1>404</h1>")).toEqual([]);
    expect(frameworkNumberFindings("/404.html", "<p>2.15</p>")).toHaveLength(1);
  });

  it("ad sağ sınırlı ve sayfaya özgü: 'Hannover 96%' ve başka sayfanın adı kırmızı", () => {
    const team = snapshot.teams.find((each) => each.league_id === league.id);
    const foreign = snapshot.teams.find((each) => each.league_id !== league.id);
    if (!team || !foreign) throw new Error("fixture iki ligli değil");
    const named = {
      ...snapshot,
      teams: snapshot.teams.map((each) =>
        each === team
          ? { ...each, name: "Hannover 96" }
          : each === foreign
            ? { ...each, name: "Leeds 1919" }
            : each,
      ),
    };
    expect(numberFindings(named, leaguePage, "<p>Hannover 96</p>")).toEqual([]);
    expect(numberFindings(named, leaguePage, "<p>Hannover 96%</p>")).toHaveLength(1);
    expect(numberFindings(named, leaguePage, "<p>Leeds 1919</p>")).toHaveLength(1);
  });
});

describe("M8 eventStatus sabit", () => {
  it("EventScheduled dışındaki değer kırmızı (JSON-LD ve bağlantı denetimi)", () => {
    const future = snapshot.matches.find(
      (each) => Date.parse(each.commence_time) > Date.parse(snapshot.generated_at),
    );
    if (!future) throw new Error("fixture gelecek maç taşımıyor");
    const cancelled = "https://schema.org/EventCancelled";
    const html = ld({
      "@graph": [{ "@type": "SportsEvent", eventStatus: cancelled }, { "@type": "BreadcrumbList" }],
    });
    const futurePage = page(`match:${future.id}`);
    expect(checkJsonLd(snapshot, futurePage, html)).toContain(
      `${futurePage.path}: eventStatus ${cancelled} (EventScheduled değil)`,
    );
    expect(linkFindings("p", html)).toContain(`p: JSON-LD dış URL eventStatus=${cancelled}`);
  });
});

describe("M9 satır içi betikler ve RSC (yeniden inceleme FP1, N2, N3)", () => {
  const boot = "<script>(self.__next_f=self.__next_f||[]).push([0])</script>";
  const data = (text: string) =>
    `<script>self.__next_f.push(${JSON.stringify([1, text])})</script>`;

  it("önyükleme + bir ya da daha çok TAM ayrışan itiş; başka betik ya da ekli JS kırmızı", () => {
    expect(inlineScriptFindings("p", boot + data('1:"x"\n'))).toEqual([]);
    expect(inlineScriptFindings("p", boot + data('1:"x') + data('y"\n') + data("2:[]\n"))).toEqual(
      [],
    );
    expect(inlineScriptFindings("p", `${boot + data('1:"x"\n')}<script>a()</script>`)).toHaveLength(
      1,
    );
    expect(inlineScriptFindings("p", `${boot}<script>a()</script>`)).toHaveLength(1);
    expect(inlineScriptFindings("p", data('1:"x"\n'))).toHaveLength(1);
    const injected = `<script>self.__next_f.push([1,"a"]);location.replace("/\\\\bet365.com");self.__next_f.push([1,""])</script>`;
    expect(inlineScriptFindings("p", boot + injected)).toHaveLength(1);
  });

  it("RSC dizeleri: yalnız TAM başvuru/yol/URL atlanır; itişler birleşik okunur", () => {
    const rsc =
      '0:["$","p",null,{"data-fe-value":"x","children":"Best value at Bet365"}]\n1:"$Sreact"\n2:"/_next/a.js"\n3:"/ Pinnacle value"\n';
    expect(rscStrings(rsc)).toEqual(["p", "x", "Best value at Bet365", "/ Pinnacle value"]);
    expect(rscLinks(rsc)).toEqual(["/_next/a.js"]);
    const split = boot + data('0:"Best val') + data('ue at Bet365"\n');
    expect(rscStrings(nextPushes(split).payload)).toContain("Best value at Bet365");
  });
});
