// Çıktı tarayıcısı (spec §5.3). Kullanım:
//   node scripts/check-out.ts --snapshot <snapshot.json> --out <derlenmiş dizin>
// Bayrak derlemeyle AYNI ortamdan okunur (SITE_INDEXABLE). Bulgu varsa exit 1.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import { DEFAULT_LANG, indexingEnabled, SITE_LANGS } from "../site.config.ts";
import { matchPath, matchStem } from "../src/lib/routes.ts";
import { parseSnapshot } from "../src/lib/snapshot.ts";
import type { Snapshot } from "../src/lib/snapshot-types.ts";
import {
  checkA11y,
  checkCsp,
  checkData,
  checkFields,
  checkHeaderBlocks,
  checkHreflang,
  checkIndexing,
  checkJsonLd,
  checkPages,
  checkRobots,
  contentFindings,
  countMarkers,
  type Headers,
  inlineScriptFindings,
  licenseFindings,
  negationTexts,
  parseHeaders,
  scanLicense,
  secretFindings,
} from "./checkout/checks.ts";
import {
  ageGateFindings,
  cssContentTexts,
  draftFindings,
  honestyFindings,
  hostFindings,
  internal,
  linkFindings,
  markerFindings,
  recordCellFindings,
  scanWords,
  stateFindings,
  wordFindings,
} from "./checkout/content.ts";
import { entityFindings } from "./checkout/entities.ts";
import { type ExpectedPage, expectedPages } from "./checkout/expect.ts";
import { frameworkNumberFindings, numberFindings } from "./checkout/numbers.ts";
import { nextPushes, rscLinks, rscStrings } from "./checkout/surface.ts";
import { squash } from "./checkout/text.ts";
import { stripScripts, tags } from "./lib/html.ts";
import { pageFiles, readText, walk } from "./lib/outdir.ts";

const CONTENT = resolve(import.meta.dirname, "../content");
const TEXT_FILE = /\.(html|txt|xml|json|js|css|sha256)$|\/_headers$|\/_redirects$/;
// Next'in kendi 404 sayfaları: sitenin kaydı değildir ama yayımlanır ve içerik denetiminden geçer.
const FRAMEWORK_FILES = ["404.html", "404/index.html", "_not-found/index.html"];

function arg(name: string): string {
  const index = process.argv.indexOf(name);
  const value = index >= 0 ? process.argv[index + 1] : undefined;
  if (!value) throw new Error(`check-out: ${name} eksik`);
  return resolve(value);
}

function optional(file: string): string {
  return existsSync(file) ? readText(file) : "";
}

function expectedRedirects(snapshot: Snapshot): string {
  const lines = [`/ /${DEFAULT_LANG}/ 301`];
  for (const lang of SITE_LANGS) {
    for (const match of snapshot.matches) {
      const league = snapshot.leagues.find((each) => each.id === match.league_id);
      if (league) {
        lines.push(`${matchStem(lang, league, match)}* ${matchPath(lang, league, match)} 301`);
      }
    }
  }
  return `${lines.join("\n")}\n`;
}

function expectedSlugs(snapshot: Snapshot): string {
  const slugOf = new Map(snapshot.leagues.map((league) => [league.id, league.slug]));
  const index = {
    version: 1,
    leagues: snapshot.leagues.map((league) => league.slug).sort(),
    teams: snapshot.teams.map((team) => `${slugOf.get(team.league_id)}/${team.slug}`).sort(),
  };
  return `${JSON.stringify(index, null, 2)}\n`;
}

type Site = {
  snapshot: Snapshot;
  headers: Headers;
  css: (href: string) => string;
  negations: readonly string[];
};

// RSC verisi (satır içi `self.__next_f` itişlerinin birleşimi ya da istemci gezinmesinin `.txt` dosyası):
// sözcük ve lisans taraması, tam yol/URL dizelerinin bağlantı denetimi, ham host taraması. İşaretli
// olumsuzlama öğesinin cümlesi (HTML'de sayılı) burada işaretsiz dize olarak geçer ve çıkarılır.
function rscFindings(where: string, raw: string, negations: readonly string[]) {
  const label = `${where} (RSC)`;
  const texts = rscStrings(raw).map((text) =>
    negations.reduce((rest, negation) => rest.split(negation).join(" "), squash(text)),
  );
  return [
    ...scanWords(label, texts),
    ...scanLicense(label, texts),
    ...rscLinks(raw)
      .filter((link) => !internal(link))
      .map((link) => `${label}: dış bağlantı "${link}"`),
    ...hostFindings(label, raw),
  ];
}

// Yayımlanan HER HTML için ortak metin denetimleri (içerik sayfaları ve Next'in 404 sayfaları).
function textFindings(where: string, html: string, site: Site): string[] {
  return [
    ...inlineScriptFindings(where, html),
    ...licenseFindings(where, html),
    ...contentFindings(where, html, site.snapshot.floor),
    ...linkFindings(where, html),
    ...wordFindings(where, html),
    ...entityFindings(where, html),
    ...rscFindings(where, nextPushes(html).payload, site.negations),
  ];
}

function frameworkFindings(site: Site, out: string): string[] {
  return FRAMEWORK_FILES.filter((file) => existsSync(join(out, file))).flatMap((file) => {
    const html = readText(join(out, file));
    const robots = tags(html, "meta").find((meta) => meta.name === "robots")?.content ?? "";
    return [
      ...(robots.split(/[\s,]+/).includes("noindex") ? [] : [`/${file}: noindex yok`]),
      ...textFindings(`/${file}`, html, site),
      ...frameworkNumberFindings(`/${file}`, html),
    ];
  });
}

// Sayfa başına bütün denetimler (her biri bulgu listesi döner).
function pageFindings(site: Site, page: ExpectedPage, html: string): string[] {
  const { snapshot, headers, css } = site;
  return [
    ...checkFields(snapshot, page, html),
    ...checkCsp(page, html, headers),
    ...checkA11y(page, html),
    ...checkJsonLd(snapshot, page, html),
    ...textFindings(page.path, html, site),
    ...numberFindings(snapshot, page, html),
    ...stateFindings(snapshot, page, html),
    ...honestyFindings(snapshot, page, html),
    ...recordCellFindings(snapshot, page, html),
    ...draftFindings(page, html, css),
    ...markerFindings(page, html),
    ...ageGateFindings(page, html),
  ];
}

// Yayın dizininin kendisi: robots.txt, fazladan XML, RSC `.txt` dosyaları, CSS `content` metni.
function outputFindings(out: string, negations: readonly string[]): string[] {
  const files = walk(out).map((file) => relative(out, file).split(sep).join("/"));
  return [
    ...checkRobots(optional(join(out, "robots.txt"))),
    ...files
      .filter((file) => file.endsWith(".xml") && file !== "sitemap.xml")
      .map((file) => `${file}: beklenmeyen XML dosyası (ikinci site haritası?)`),
    ...files
      .filter((file) => file.endsWith(".txt") && file !== "robots.txt")
      .flatMap((file) => rscFindings(file, readText(join(out, file)), negations)),
    ...files
      .filter((file) => file.endsWith(".css"))
      .flatMap((file) => {
        const texts = cssContentTexts(readText(join(out, file)));
        return [
          ...scanWords(`${file} (CSS content)`, texts),
          ...scanLicense(`${file} (CSS content)`, texts),
        ];
      }),
  ];
}

function main(): number {
  const snapshotFile = arg("--snapshot");
  const out = arg("--out");
  const bytes = readFileSync(snapshotFile);
  const snapshot = parseSnapshot(bytes.toString("utf-8"));
  const flag = indexingEnabled();
  const expected = expectedPages(snapshot);
  const built = pageFiles(out).map((page) => ({ path: page.path, html: readText(page.file) }));
  const byPath = new Map(built.map((page) => [page.path, page.html]));
  const headers = parseHeaders(optional(join(out, "_headers")));
  const negations = [...new Set(built.flatMap((page) => negationTexts(page.html)))];
  const site = { snapshot, headers, css: (href: string) => optional(join(out, href)), negations };

  const findings = [
    ...checkPages(expected, built),
    ...checkHreflang(expected, byPath),
    ...checkIndexing(
      expected,
      byPath,
      optional(join(out, "sitemap.xml")),
      headers,
      optional(join(out, "robots.txt")),
      flag,
    ),
    ...outputFindings(out, negations),
    ...frameworkFindings(site, out),
    ...checkHeaderBlocks(
      headers,
      built.map((page) => page.path),
    ),
    ...checkData(
      optional(join(out, "_redirects")),
      expectedRedirects(snapshot),
      optional(join(out, "data/slugs.json")),
      expectedSlugs(snapshot),
      optional(join(out, "data/snapshot.sha256")),
      createHash("sha256").update(bytes).digest("hex"),
    ),
  ];
  let htmlMarkers = 0;
  for (const page of expected) {
    const html = byPath.get(page.path);
    if (html === undefined) continue;
    findings.push(...pageFindings(site, page, html));
    htmlMarkers += countMarkers(stripScripts(html));
  }
  let sourceMarkers = 0;
  const sources = walk(CONTENT).filter(
    (each) => /\.tsx?$/.test(each) && !/\.test\.tsx?$/.test(each),
  );
  for (const file of sources) {
    const text = readText(file);
    findings.push(...licenseFindings(file, text));
    sourceMarkers += countMarkers(text);
  }
  if (sourceMarkers !== htmlMarkers) {
    findings.push(`H4 işaret sayısı: kaynak ${sourceMarkers} ≠ derlenmiş ${htmlMarkers}`);
  }
  for (const file of walk(out).filter((each) => TEXT_FILE.test(each))) {
    findings.push(...secretFindings(file, readText(file)));
  }
  for (const finding of findings) process.stdout.write(`BULGU: ${finding}\n`);
  process.stdout.write(
    `check-out: ${built.length} sayfa, ${findings.length} bulgu (indexable=${flag})\n`,
  );
  return findings.length === 0 ? 0 : 1;
}

process.exitCode = main();
