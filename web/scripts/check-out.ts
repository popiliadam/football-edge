// Çıktı tarayıcısı (spec §5.3). Kullanım:
//   node scripts/check-out.ts --snapshot <snapshot.json> --out <derlenmiş dizin>
// Bayrak derlemeyle AYNI ortamdan okunur (SITE_INDEXABLE). Bulgu varsa exit 1.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
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
  contentFindings,
  countMarkers,
  type Headers,
  licenseFindings,
  parseHeaders,
  secretFindings,
} from "./checkout/checks.ts";
import {
  ageGateFindings,
  draftFindings,
  honestyFindings,
  linkFindings,
  markerFindings,
  numberFindings,
  recordCellFindings,
  stateFindings,
  wordFindings,
} from "./checkout/content.ts";
import { type ExpectedPage, expectedPages } from "./checkout/expect.ts";
import { stripScripts } from "./lib/html.ts";
import { pageFiles, readText, walk } from "./lib/outdir.ts";

const CONTENT = resolve(import.meta.dirname, "../content");
const TEXT_FILE = /\.(html|txt|xml|json|js|css|sha256)$|\/_headers$|\/_redirects$/;

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
      if (league)
        lines.push(`${matchStem(lang, league, match)}* ${matchPath(lang, league, match)} 301`);
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

// Sayfa başına bütün denetimler (her biri bulgu listesi döner).
type Site = { snapshot: Snapshot; headers: Headers; css: (href: string) => string };

function pageFindings(
  { snapshot, headers, css }: Site,
  page: ExpectedPage,
  html: string,
): string[] {
  return [
    ...checkFields(snapshot, page, html),
    ...checkCsp(page, html, headers),
    ...checkA11y(page, html),
    ...checkJsonLd(snapshot, page, html),
    ...licenseFindings(page.path, stripScripts(html)),
    ...contentFindings(page.path, html, snapshot.floor),
    ...linkFindings(page.path, html),
    ...wordFindings(page.path, html),
    ...numberFindings(snapshot, page, html),
    ...stateFindings(snapshot, page, html),
    ...honestyFindings(snapshot, page, html),
    ...recordCellFindings(snapshot, page, html),
    ...draftFindings(page, html, css),
    ...markerFindings(page, html),
    ...ageGateFindings(page, html),
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
  const site = { snapshot, headers, css: (href: string) => optional(join(out, href)) };

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
  for (const file of walk(CONTENT).filter(
    (each) => /\.tsx?$/.test(each) && !/\.test\.tsx?$/.test(each),
  )) {
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
