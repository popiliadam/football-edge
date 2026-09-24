// Carry-in denetimlerinin (task-9-carryins.md 1–10) asgari kırmızı girdileri. Gerçek derleme
// üzerindeki kırma-geri-yükleme kanıtları görev raporundadır.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { SITE_URL } from "../../site.config.ts";
import { t } from "../../src/i18n/dict.ts";
import { fullFixture } from "../../src/lib/fixture.ts";
import { parseSnapshot } from "../../src/lib/snapshot.ts";
import {
  ageGateFindings,
  cssHidingFindings,
  draftFindings,
  honestyFindings,
  linkFindings,
  markerFindings,
  recordCellFindings,
  stateFindings,
  utcText,
  wordFindings,
} from "./content.ts";
import { type ExpectedPage, expectedPages } from "./expect.ts";
import { numberFindings } from "./numbers.ts";
import { textNodes } from "./text.ts";

const snapshot = fullFixture();
const empty = parseSnapshot(
  readFileSync(
    resolve(import.meta.dirname, "../../fixtures/snapshot.fixture.web-empty.json"),
    "utf-8",
  ),
);
const find = (all: ExpectedPage[], id: string, lang = "en"): ExpectedPage => {
  const found = all.find((each) => each.id === id && each.lang === lang);
  if (!found) throw new Error(`beklenen sayfa yok: ${id}`);
  return found;
};
const pages = expectedPages(snapshot);
const page = (id: string, lang = "en") => find(pages, id, lang);

describe("metin yürüyüşü", () => {
  it("ata bağlamı: gizli, pencere, data-fe; betik/stil/yorum metin değil", () => {
    const nodes = textNodes(
      '<div hidden=""><p>a</p></div><dialog><p>b</p></dialog><span data-fe="x">c</span><script>d</script><style>e{}</style><!-- f --><br/><p>g</p>',
    );
    expect(nodes.map((node) => node.text)).toEqual(["a", "b", "c", "g"]);
    expect(nodes.map((node) => node.ancestors.map((each) => each.tag).join(">"))).toEqual([
      "div>p",
      "dialog>p",
      "span",
      "p",
    ]);
  });
});

describe("T5-1 yalnız iç bağlantı", () => {
  it("göreli yol ve yer tutucu alan adı geçer; dış href/src/srcset/action kırmızı", () => {
    const ok = `<a href="/en/">x</a><link rel="canonical" href="${SITE_URL}/en/"/><a href="#top">y</a>`;
    expect(linkFindings("p", ok)).toEqual([]);
    expect(linkFindings("p", '<a href="https://bookie.example/">x</a>')).toContain(
      'p: dış bağlantı href="https://bookie.example/"',
    );
    expect(linkFindings("p", '<a href="//cdn.example/x">x</a>')).toContain(
      'p: dış bağlantı href="//cdn.example/x"',
    );
    expect(
      linkFindings("p", '<img alt="" srcset="/a.png 1x, https://cdn.example/b.png 2x"/>'),
    ).toContain('p: dış bağlantı srcset="https://cdn.example/b.png"');
    expect(linkFindings("p", '<form action="https://x.example/f"></form>').length).toBeGreaterThan(
      0,
    );
  });

  it("schema.org yalnız JSON-LD @context ve eventStatus; veri betiğinde yabancı host kırmızı", () => {
    const ld = (data: object) =>
      `<script type="application/ld+json">${JSON.stringify(data)}</script>`;
    const good = {
      "@context": "https://schema.org",
      "@graph": [{ eventStatus: "https://schema.org/EventScheduled", url: `${SITE_URL}/en/` }],
    };
    expect(linkFindings("p", ld(good))).toEqual([]);
    expect(linkFindings("p", ld({ "@graph": [{ url: "https://schema.org/x" }] }))).toContain(
      "p: JSON-LD dış URL url=https://schema.org/x",
    );
    expect(linkFindings("p", '<script>self.x="https://tracker.example/p"</script>')).toContain(
      "p: izinsiz host tracker.example",
    );
  });
});

describe("T5-2 görünen metinde yasak sözcükler", () => {
  it("bahis şirketi adı (büyük/küçük harf) kırmızı; genel 'bookmakers' geçer", () => {
    expect(wordFindings("p", "<p>Odds from Bet365</p>")).toContain('p: bahis şirketi adı "bet365"');
    expect(wordFindings("p", "<p>PINNACLE closing</p>")).toContain(
      'p: bahis şirketi adı "pinnacle"',
    );
    expect(wordFindings("p", '<p title="William Hill">x</p>')).toContain(
      'p: bahis şirketi adı "william hill"',
    );
    expect(wordFindings("p", "<p>does not link to bookmakers</p>")).toEqual([]);
  });

  it("value/edge/öneri kırmızı (Türkçe büyük harf dahil); sözlükteki izinli cümle geçer", () => {
    expect(wordFindings("p", "<p>Top value bets</p>")).toContain('p: öneri sözcüğü "value"');
    expect(wordFindings("p", "<p>Our EDGE today</p>")).toContain('p: öneri sözcüğü "edge"');
    expect(wordFindings("p", "<p>GÜNÜN ÖNERİLERİ</p>")).toContain('p: öneri sözcüğü "oneri"');
    expect(wordFindings("p", "<p>knowledge</p>")).toEqual([]);
    expect(
      wordFindings("p", `<p>${t("en", "home.intro")}</p><p>${t("tr", "home.intro")}</p>`),
    ).toEqual([]);
    expect(wordFindings("p", `<p>${t("en", "home.intro")} Also value picks.</p>`)).toContain(
      'p: öneri sözcüğü "value"',
    );
    expect(wordFindings("p", `<p>${t("en", "record.emptyExplain")}</p>`)).toEqual([]);
    expect(wordFindings("p", "<p>a closing line value, and value picks</p>")).toContain(
      'p: öneri sözcüğü "value"',
    );
  });
});

describe("T5-3 data-fe dışında sayı yok", () => {
  const league = page(`league:${snapshot.leagues[0]?.id}`);
  it("yüzdelik etiketi, 18+, data-fe ve <time> geçer; başka rakam kırmızı", () => {
    const kickoff = snapshot.matches.find((each) => each.league_id === snapshot.leagues[0]?.id);
    if (!kickoff) throw new Error("fixture ligi maçsız");
    const time = `<time dateTime="${kickoff.commence_time}">${utcText(kickoff.commence_time)}</time>`;
    const ok = `<p>10th percentile</p><p>18+ only</p><span data-fe="a:b:c">7.5</span>${time}`;
    expect(numberFindings(snapshot, league, ok)).toEqual([]);
    expect(numberFindings(snapshot, league, "<p>7 matches</p>")).toEqual([
      `${league.path}: data-fe dışında sayı "7" ("7 matches")`,
    ]);
  });

  it("anlık görüntüdeki adın rakamı veri metnidir; adın yanındaki hesaplanmış sayı kırmızı", () => {
    const team = snapshot.teams[0];
    if (!team) throw new Error("fixture takımsız");
    const named = {
      ...snapshot,
      teams: [{ ...team, name: "Schalke 04" }, ...snapshot.teams.slice(1)],
    };
    expect(numberFindings(named, league, "<p>Schalke 04</p>")).toEqual([]);
    expect(numberFindings(named, league, "<p>Schalke 04 (3)</p>")).toHaveLength(1);
  });

  it("yasal atıf yalnız kendi belgesinde izinli", () => {
    const text = "<p>KVKK md. 6</p>";
    expect(numberFindings(snapshot, page("legal:privacy", "tr"), text)).toEqual([]);
    expect(numberFindings(snapshot, page("legal:terms", "tr"), text)).toHaveLength(1);
  });
});

describe("T5-4 durum etiketleri", () => {
  const match = snapshot.matches.find((each) => each.h2h.opening === null && each.move === null);
  if (!match) throw new Error("fixture eşik altı açılış + hareketsiz maç taşımıyor");
  const matchPage = page(`match:${match.id}`);
  const kickoff = `<time dateTime="${match.commence_time}">${utcText(match.commence_time)}</time>`;
  const row = (reason: string) =>
    `<main><p>${kickoff}</p><table><tr><th scope="row">Opening</th><td colSpan="4">${reason}</td></tr></table><p>No move to show.</p></main>`;

  it("doğru neden geçer; kapanış bekleniyor ↔ yetersiz kitap takası kırmızı", () => {
    expect(stateFindings(snapshot, matchPage, row("Not enough bookmakers"))).toEqual([]);
    expect(stateFindings(snapshot, matchPage, row("Awaiting close"))[0]).toContain(
      "eksik tur nedenleri",
    );
  });

  it("hareket yokken boş durum cümlesi eksikse kırmızı", () => {
    const html = row("Not enough bookmakers").replace("<p>No move to show.</p>", "");
    expect(stateFindings(snapshot, matchPage, html)).toContain(
      `${matchPage.path}: "No move to show." yok`,
    );
  });
});

describe("T6-5/6 sicil", () => {
  const honest = (lang: "en" | "tr", extra: string) => {
    const keys = ["record.commitment", "record.limit1", "record.limit2", "record.limit3"] as const;
    return `<main>${keys.map((key) => `<p>${t(lang, key)}</p>`).join("")}${extra}</main>`;
  };
  const anchor = `<p>${t("en", "record.anchorBehindBefore")} x</p>`;

  it("dolu sicil: dürüstlük metinleri + tablo geçer; bir sınır eksikse kırmızı", () => {
    const record = page("track-record");
    expect(honestyFindings(snapshot, record, honest("en", `<table></table>${anchor}`))).toEqual([]);
    const missing = honest("en", `<table></table>${anchor}`).replace(t("en", "record.limit2"), "");
    expect(honestyFindings(snapshot, record, missing)).toContain(
      `${record.path}: dürüstlük metni record.limit2 yok`,
    );
  });

  it("boş sicil: açıklama var, tablo YOK", () => {
    const record = find(expectedPages(empty), "track-record", "tr");
    const matches = `<p>${t("tr", "record.anchorMatches")}</p>`;
    const good = honest("tr", `<p>${t("tr", "record.emptyExplain")}</p>${matches}`);
    expect(honestyFindings(empty, record, good)).toEqual([]);
    expect(
      honestyFindings(empty, record, good.replace("</main>", "<table></table></main>")),
    ).toContain(`${record.path}: sicil tablosu fazla`);
  });

  it("girdi satırı: yayın anı ve maç adı anlık görüntüyle birebir", () => {
    const entry = snapshot.record.entries[0];
    const match = snapshot.matches.find((each) => each.id === entry?.match_id);
    if (!entry || !match) throw new Error("fixture girdisiz");
    const record = page("track-record");
    const rowWith = (time: string, name: string) =>
      `<table><tr><td><time dateTime="${entry.published_at}">${time}</time></td><td>${name}</td><td><code data-fe="entry:${entry.publication_id}:market">h2h</code></td></tr></table>`;
    const others = snapshot.record.entries
      .slice(1)
      .map((each) =>
        rowWith("", "").replaceAll(
          `entry:${entry.publication_id}:`,
          `entry:${each.publication_id}:`,
        ),
      );
    const good = rowWith(utcText(entry.published_at), `${match.home} – ${match.away}`);
    const own = (findings: string[]) =>
      findings.filter((f) => f.includes(`girdi ${entry.publication_id} `));
    expect(own(recordCellFindings(snapshot, record, good + others.join("")))).toEqual([]);
    expect(
      own(
        recordCellFindings(
          snapshot,
          record,
          rowWith("2026-01-01 00:00 UTC", `${match.home} – ${match.away}`),
        ),
      ),
    ).toHaveLength(1);
    expect(
      own(recordCellFindings(snapshot, record, rowWith(utcText(entry.published_at), match.away))),
    ).toHaveLength(1);
  });
});

describe("T7-8 TASLAK görünür", () => {
  const legal = page("legal:terms");
  const draft = t("en", "legal.draft");
  const css = () => "";

  it("<main>'de görünür işaret geçer; gizli/şablon/pencere/yorum içinde kırmızı", () => {
    expect(draftFindings(legal, `<main><p class="d">${draft}</p></main>`, css)).toEqual([]);
    for (const hidden of [
      `<main><div hidden=""><p>${draft}</p></div></main>`,
      `<main><template><p>${draft}</p></template></main>`,
      `<main><p style="display:none">${draft}</p></main>`,
      `<main><!-- ${draft} --></main>`,
      `<dialog><p>${draft}</p></dialog>`,
    ]) {
      expect(draftFindings(legal, hidden, css)[0]).toContain("görünür TASLAK işareti 0");
    }
  });

  it("işaretin sınıfını gizleyen derlenmiş CSS kırmızı", () => {
    const html = `<link rel="stylesheet" href="/s.css"/><main><p class="m__draft">${draft}</p></main>`;
    expect(draftFindings(legal, html, () => ".m__draft{color:red}")).toEqual([]);
    expect(draftFindings(legal, html, () => ".m__draft{display:none}")[0]).toContain(
      "CSS'te gizleniyor",
    );
    expect(
      cssHidingFindings("p", "@media print{.m__draft{visibility:hidden}}", ["m__draft"]),
    ).toHaveLength(1);
    expect(cssHidingFindings("p", ".m__draftish{display:none}", ["m__draft"])).toEqual([]);
  });
});

describe("T7-9/10 olumsuzlama işareti ve 18+ işaretlemesi", () => {
  const marked = '<p data-fe-allow="license-negation">x</p>';
  it("işaret yalnız koşullarda, tam bir kez", () => {
    expect(markerFindings(page("legal:terms"), marked)).toEqual([]);
    expect(markerFindings(page("legal:terms"), "")).toHaveLength(1);
    expect(markerFindings(page("legal:privacy"), marked)).toHaveLength(1);
    expect(markerFindings(page("home"), marked + marked)).toHaveLength(1);
  });

  it("kapalı tek pencere ve betiksiz şerit; açık pencere kırmızı", () => {
    const home = page("home");
    const gate = (open: string) =>
      `<noscript><p>${t("en", "age.strip")}</p></noscript><dialog${open}><p>${t("en", "age.title")}</p></dialog>`;
    expect(ageGateFindings(home, gate(""))).toEqual([]);
    expect(ageGateFindings(home, gate(' open=""'))).toHaveLength(1);
    expect(ageGateFindings(home, gate("").replace(/<noscript>.*<\/noscript>/, ""))).toHaveLength(1);
  });
});
