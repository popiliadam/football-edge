// Çıktı tarayıcısının kontrolleri (spec §5.3 (1)–(8), H4–H7, §9). Her fonksiyon bulgu
// listesi döner; boş liste = geçti. Bulgu metni sayfa yolunu ve neyin tuttuğunu adlandırır.
import { createHash } from "node:crypto";
import { DEFAULT_LANG, SITE_LANGS } from "../../site.config.ts";
import { formatNumber } from "../../src/lib/format.ts";
import { absoluteUrl } from "../../src/lib/routes.ts";
import type { Snapshot } from "../../src/lib/snapshot-types.ts";
import {
  feElements,
  feOpenings,
  headingLevels,
  isExecutableInline,
  isJsonLd,
  scriptOpenings,
  scripts,
  stripScripts,
  tags,
  visibleText,
} from "../lib/html.ts";
import { type ExpectedPage, expectedLabel, fieldKind, resolveField } from "./expect.ts";
import { surfaceTexts } from "./surface.ts";
import { squash } from "./text.ts";
import { fold, LICENSE_PATTERNS } from "./words.ts";

export type Built = { path: string; html: string };
export type Headers = Map<string, [string, string][]>;

export function sameSet(a: readonly string[], b: readonly string[]): boolean {
  const left = [...a].sort();
  const right = [...b].sort();
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

// Next'in hata/404 gövdeleri: eksik kayıtta (`notFound()`) `next build` 0 ile çıkıp o yola boş bir
// `<html id="__next_error__">` kabuğu yazar (T4 carry-in 14; gerçek derlemede ölçüldü); kök 404 ise
// `next-error-h1` taşır.
const NOT_FOUND = /<html\b[^>]*\bid="__next_error__"|class="next-error-h1"|<title>404\b/;

// (1) her kayıt için tam bir sayfa, her sayfa için tam bir kayıt; sayfa kendi kaydını söyler.
export function checkPages(expected: readonly ExpectedPage[], built: readonly Built[]): string[] {
  const findings: string[] = [];
  const byPath = new Map(built.map((page) => [page.path, page]));
  const wanted = new Set(expected.map((page) => page.path));
  if (wanted.size !== expected.length) findings.push("iki kayıt aynı yola düşüyor");
  for (const page of expected) {
    const html = byPath.get(page.path)?.html;
    if (html === undefined) {
      findings.push(`${page.path}: kaydın sayfası yok (${page.id})`);
      continue;
    }
    if (NOT_FOUND.test(html)) {
      findings.push(`${page.path}: 404 sayfası (kayıt derlemede bulunamadı: ${page.id})`);
    }
    const mains = tags(html, "main");
    if (mains.length !== 1 || mains[0]?.["data-fe-page"] !== page.id) {
      findings.push(`${page.path}: <main data-fe-page> ${page.id} değil`);
    }
  }
  for (const page of built) {
    if (!wanted.has(page.path)) findings.push(`${page.path}: anlık görüntüde kaydı olmayan sayfa`);
  }
  return findings;
}

// (2)(3) H6c: öznitelik = anlık görüntü değeri birebir; görünen metin = format(değer); değeri
// öznitelikte olan alanın görünen etiketi = sözlük/kayıt. Yinelenen anahtar izinli, her öğe ayrı.
export function checkFields(snapshot: Snapshot, page: ExpectedPage, html: string): string[] {
  const findings: string[] = [];
  const elements = feElements(html);
  if (elements.length !== feOpenings(html)) {
    findings.push(`${page.path}: okunamayan data-fe öğesi (çocuk tek metin değil)`);
  }
  const seen = [...new Set(elements.map((element) => element.attrs["data-fe"] ?? ""))];
  if (!sameSet(seen, page.fields)) {
    const missing = page.fields.filter((key) => !seen.includes(key));
    const extra = seen.filter((key) => !page.fields.includes(key));
    findings.push(
      `${page.path}: data-fe kümesi eksik ${missing.join(",")} fazla ${extra.join(",")}`,
    );
  }
  for (const element of elements) {
    const key = element.attrs["data-fe"] ?? "";
    const kind = fieldKind(key);
    const value = resolveField(snapshot, key);
    if (kind === undefined || value === undefined || value === null) {
      findings.push(`${page.path}: çözülemeyen alan ${key}`);
      continue;
    }
    const attr = element.attrs["data-fe-value"];
    if (attr !== String(value)) {
      findings.push(`${page.path}: ${key} özniteliği ${attr} ≠ ${String(value)}`);
    }
    if (kind === "attr") {
      const label = expectedLabel(snapshot, key, page.lang);
      if (element.text !== label) {
        findings.push(`${page.path}: ${key} etiketi "${element.text}" ≠ "${label ?? "?"}"`);
      }
      continue;
    }
    const shown = kind === "text" ? String(value) : formatNumber(value as number, kind, page.lang);
    if (element.text !== shown) {
      findings.push(`${page.path}: ${key} metni "${element.text}" ≠ "${shown}"`);
    }
  }
  return findings;
}

type Alternate = { lang: string; href: string };

function alternates(html: string): Alternate[] {
  return tags(html, "link")
    .filter((link) => link.rel === "alternate" && link.hreflang !== undefined)
    .map((link) => ({ lang: link.hreflang ?? "", href: link.href ?? "" }));
}

// (4) hreflang: bütün diller + x-default, kendine atıflı, karşılıklı; kanonik = kendi URL'si.
export function checkHreflang(
  pages: readonly ExpectedPage[],
  built: Map<string, string>,
): string[] {
  const findings: string[] = [];
  for (const page of pages) {
    const html = built.get(page.path);
    if (html === undefined) continue; // checkPages zaten raporlar
    const links = alternates(html);
    const want = [...SITE_LANGS, "x-default"];
    if (
      !sameSet(
        links.map((link) => link.lang),
        want,
      )
    ) {
      findings.push(`${page.path}: hreflang dilleri ${links.map((link) => link.lang).join(",")}`);
      continue;
    }
    const href = (lang: string) => links.find((link) => link.lang === lang)?.href;
    if (href(page.lang) !== absoluteUrl(page.path)) {
      findings.push(`${page.path}: hreflang kendine atıflı değil`);
    }
    if (href("x-default") !== absoluteUrl(page.paths[DEFAULT_LANG])) {
      findings.push(`${page.path}: x-default yanlış`);
    }
    const canonical = tags(html, "link").find((link) => link.rel === "canonical")?.href;
    if (canonical !== absoluteUrl(page.path)) {
      findings.push(`${page.path}: kanonik ${canonical ?? "yok"}`);
    }
    for (const lang of SITE_LANGS) {
      const target = page.paths[lang];
      if (href(lang) !== absoluteUrl(target)) {
        findings.push(`${page.path}: hreflang ${lang} ${href(lang)} ≠ ${absoluteUrl(target)}`);
        continue;
      }
      const back = alternates(built.get(target) ?? "").find((link) => link.lang === page.lang);
      if (back?.href !== absoluteUrl(page.path)) {
        findings.push(`${page.path}: ${target} geri bağlanmıyor`);
      }
    }
  }
  return findings;
}

const effective = (page: ExpectedPage, flag: boolean) => flag && page.recordIndexable;

// Site haritası girdisi: <loc>(lar) ve (hreflang → href) çiftleri; sayfanın <head>'iyle aynı kaynak.
// `<url >` yazımı ve girdi başına ikinci `<loc>` da okunur (T9 inceleme M4).
function sitemapEntries(xml: string): { loc: string; locs: number; links: string[] }[] {
  return [...xml.matchAll(/<url\b[^>]*>([\s\S]*?)<\/url>/g)].map((match) => {
    const body = match[1] ?? "";
    const links = [...body.matchAll(/<xhtml:link\b[^>]*>/g)].map((link) => {
      const lang = /hreflang="([^"]*)"/.exec(link[0])?.[1] ?? "";
      return `${lang}=${/href="([^"]*)"/.exec(link[0])?.[1] ?? ""}`;
    });
    const locs = [...body.matchAll(/<loc\b[^>]*>([^<]*)<\/loc>/g)].map((loc) => loc[1] ?? "");
    return { loc: locs.length === 1 ? (locs[0] ?? "") : "", locs: locs.length, links };
  });
}

// (5) + H7: noindex meta ↔ etkin indekslenebilirlik birebir; site haritası = indekslenebilir
// sayfa kümesi (her girdide bütün diller + x-default); bayrak kapalıyken X-Robots-Tag; robots.txt
// Disallow'suz.
export function checkIndexing(
  pages: readonly ExpectedPage[],
  built: Map<string, string>,
  sitemapXml: string,
  headers: Headers,
  robotsTxt: string,
  flag: boolean,
): string[] {
  const findings: string[] = [];
  for (const page of pages) {
    const html = built.get(page.path);
    if (html === undefined) continue;
    const robots = tags(html, "meta").find((meta) => meta.name === "robots");
    const noindex = (robots?.content ?? "").split(/[\s,]+/).includes("noindex");
    if (noindex === effective(page, flag)) {
      findings.push(
        `${page.path}: noindex=${noindex}, beklenen indekslenebilir=${effective(page, flag)}`,
      );
    }
  }
  const entries = sitemapEntries(sitemapXml);
  const indexable = pages.filter((page) => effective(page, flag));
  const want = indexable.map((page) => absoluteUrl(page.path));
  if (
    !sameSet(
      entries.map((entry) => entry.loc),
      want,
    )
  ) {
    findings.push(`sitemap.xml: ${entries.length} URL, beklenen ${want.length}`);
  }
  const totalLocs = (sitemapXml.match(/<loc\b/g) ?? []).length;
  if (totalLocs !== entries.length || entries.some((entry) => entry.locs !== 1)) {
    findings.push(
      `sitemap.xml: ${totalLocs} <loc>, ${entries.length} <url> (girdi başına tam bir)`,
    );
  }
  for (const entry of entries) {
    const page = indexable.find((each) => absoluteUrl(each.path) === entry.loc);
    if (page === undefined) continue;
    const links = [
      ...SITE_LANGS.map((lang) => `${lang}=${absoluteUrl(page.paths[lang])}`),
      `x-default=${absoluteUrl(page.paths[DEFAULT_LANG])}`,
    ];
    if (!sameSet(entry.links, links)) findings.push(`sitemap.xml: alternatif ${entry.loc}`);
  }
  const global = headers.get("/*") ?? [];
  const robotsTag = global.some(([name, value]) => name === "X-Robots-Tag" && value === "noindex");
  if (robotsTag === flag) {
    findings.push(`_headers: X-Robots-Tag noindex=${robotsTag}, bayrak=${flag}`);
  }
  if (/^\s*disallow\s*:\s*\S/im.test(robotsTxt)) findings.push("robots.txt: Disallow taşıyor (H7)");
  return findings;
}

// robots.txt birebir: Disallow yok ve TEK site haritası (ikinci `Sitemap:` başka bir URL kümesi
// yayımlardı; T9 inceleme M4).
export function checkRobots(robotsTxt: string): string[] {
  const lines = robotsTxt
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const want = ["User-Agent: *", "Allow: /", `Sitemap: ${absoluteUrl("/sitemap.xml")}`];
  return lines.join("\n") === want.join("\n") ? [] : [`robots.txt: ${lines.join(" | ")}`];
}

export const ALLOW_MARKER = 'data-fe-allow="license-negation"';
const ALLOWED = /<([a-z]+)\b[^>]*\bdata-fe-allow="license-negation"[^>]*>[\s\S]*?<\/\1>/g;

// H4: lisans iddiası yok (işaretli olumsuz cümle hariç). Taranan: ham metin, görünen metin
// (etiketler boşluğa), satır içi etiketlerle bölünmüş sözcükler, öznitelikler, `<meta content>`
// ve JSON-LD dizeleri (T9 inceleme I3, M2). Biçim karakterleri `fold`da silinir.
export function scanLicense(where: string, texts: readonly string[]): string[] {
  const folded = texts.map(fold).join("\n");
  return LICENSE_PATTERNS.filter((pattern) => folded.includes(pattern)).map(
    (pattern) => `${where}: lisans iddiası kalıbı "${pattern}" (H4)`,
  );
}

export function licenseFindings(where: string, text: string): string[] {
  const cleaned = text.replace(ALLOWED, " ");
  return scanLicense(where, [
    stripScripts(cleaned),
    visibleText(cleaned),
    ...surfaceTexts(cleaned),
  ]);
}

// Olumsuzlama öğelerinin görünen metni: RSC verisinde aynı cümle işaretsiz dize olarak geçer.
export function negationTexts(html: string): string[] {
  return [...html.matchAll(ALLOWED)].map((match) => squash(visibleText(match[0])));
}

export function countMarkers(text: string): number {
  return text.split(ALLOW_MARKER).length - 1;
}

export const SECRET_PATTERNS = [
  "postgres://",
  "postgresql://",
  "service_role",
  "eyJ",
  "SUPABASE_",
  "NETLIFY_AUTH",
];

// H5: anahtar kalıpları hiçbir çıktı dosyasında yok.
export function secretFindings(where: string, text: string): string[] {
  return SECRET_PATTERNS.filter((pattern) => text.includes(pattern)).map(
    (pattern) => `${where}: gizli anahtar kalıbı "${pattern}" (H5)`,
  );
}

// H1 (§12.4/4 sınırı: yalnız tarih kalıbı): tabandan eski ISO ya da GG.AA.YYYY tarih yok;
// görünen metinde "NaN"/"undefined"/"null" yok (boş değer sayı gibi basılmış olurdu).
export function contentFindings(where: string, html: string, floor: string): string[] {
  const findings: string[] = [];
  const floorDay = floor.slice(0, 10);
  for (const match of html.matchAll(/\b(\d{4})-(\d{2})-(\d{2})\b/g)) {
    if (match[0] < floorDay) findings.push(`${where}: tabandan eski tarih ${match[0]} (H1)`);
  }
  for (const match of html.matchAll(/\b(\d{2})\.(\d{2})\.(\d{4})\b/g)) {
    const iso = `${match[3]}-${match[2]}-${match[1]}`;
    if (iso < floorDay) findings.push(`${where}: tabandan eski tarih ${match[0]} (H1)`);
  }
  const word = /\b(NaN|undefined|null)\b/.exec(visibleText(html));
  if (word) findings.push(`${where}: görünen metinde "${word[1]}"`);
  return findings;
}

// Tarayıcının hash'lediği baytlar: gövdenin UTF-8 kodlaması. `cspHash`ten BAĞIMSIZ (T8 I1).
function sha256Token(body: string): string {
  return `'sha256-${createHash("sha256").update(Buffer.from(body, "utf8")).digest("base64")}'`;
}

// (7) CSP: sayfanın yürütülebilir satır içi betiklerinin hash kümesi = CSP'deki hash kümesi
// BİREBİR (T8 carry-in 11); JSON-LD hash'i listede DEĞİL; `unsafe-` yok; tam bir CSP başlığı.
export function checkCsp(page: ExpectedPage, html: string, headers: Headers): string[] {
  const findings: string[] = [];
  const all = scripts(html);
  if (all.length !== scriptOpenings(html)) {
    findings.push(`${page.path}: okunamayan <script> etiketi`);
  }
  const policies = (headers.get(page.path) ?? []).filter(
    ([name]) => name === "Content-Security-Policy",
  );
  if (policies.length !== 1) {
    findings.push(`${page.path}: ${policies.length} CSP başlığı`);
    return findings;
  }
  const policy = policies[0]?.[1] ?? "";
  if (policy.includes("'unsafe-")) findings.push(`${page.path}: CSP 'unsafe-' taşıyor`);
  const scriptSrc = policy
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("script-src"));
  const declared = (scriptSrc ?? "").split(/\s+/).filter((token) => token.startsWith("'sha256-"));
  const actual = new Set(all.filter(isExecutableInline).map((script) => sha256Token(script.body)));
  for (const token of actual) {
    if (!declared.includes(token)) {
      findings.push(`${page.path}: CSP'nin izin vermediği satır içi betik`);
    }
  }
  const ld = new Set(all.filter(isJsonLd).map((script) => sha256Token(script.body)));
  for (const token of declared.filter((each) => !actual.has(each))) {
    findings.push(
      ld.has(token)
        ? `${page.path}: JSON-LD hash'i CSP'de (gereksiz)`
        : `${page.path}: CSP'de sayfada olmayan hash ${token}`,
    );
  }
  return findings;
}

// Next'in satır içi betikleri sabittir (T9 inceleme M9): tam iki yürütülebilir betik — önyükleme ve
// RSC verisi. Hash'i `_headers`'a da eklenmiş fazladan bir betik küme denetiminden geçerdi.
const BOOT = "(self.__next_f=self.__next_f||[]).push([0])";

export function inlineScriptFindings(where: string, html: string): string[] {
  const bodies = scripts(html)
    .filter(isExecutableInline)
    .map((script) => script.body);
  const data = bodies[1] ?? "";
  const shaped =
    bodies.length === 2 &&
    bodies[0] === BOOT &&
    data.startsWith('self.__next_f.push([1,"') &&
    data.endsWith('"])');
  return shaped
    ? []
    : [`${where}: satır içi betikler beklenen iki biçimde değil (${bodies.length})`];
}

// Beklenen `/*` güvenlik başlıkları (emit.ts'ten bağımsız yazılır).
const GLOBAL_HEADERS: readonly [string, string][] = [
  ["X-Content-Type-Options", "nosniff"],
  ["Referrer-Policy", "strict-origin-when-cross-origin"],
  ["Permissions-Policy", "camera=(), microphone=(), geolocation=()"],
];

// `_headers` blokları: `/*` var, güvenlik başlıklarını taşır ve CSP taşımaz (tarayıcı iki CSP'nin
// kesişimini uygulardı); sayfası olmayan blok yok.
export function checkHeaderBlocks(headers: Headers, builtPaths: readonly string[]): string[] {
  const findings: string[] = [];
  const global = headers.get("/*");
  for (const [name, value] of GLOBAL_HEADERS) {
    if (!global?.some(([n, v]) => n === name && v === value)) {
      findings.push(`_headers: /* bloğu yok ya da ${name}: ${value} eksik`);
    }
  }
  if (global?.some(([name]) => name === "Content-Security-Policy")) {
    findings.push("_headers: /* bloğunda CSP");
  }
  for (const path of headers.keys()) {
    if (path !== "/*" && !builtPaths.includes(path)) {
      findings.push(`_headers: sayfası olmayan blok ${path}`);
    }
  }
  return findings;
}

// (8) basit erişilebilirlik.
export function checkA11y(page: ExpectedPage, html: string): string[] {
  const findings: string[] = [];
  const lang = /<html\b[^>]*\blang="([^"]*)"/.exec(html)?.[1];
  if (lang !== page.lang) findings.push(`${page.path}: <html lang="${lang ?? ""}"> ≠ ${page.lang}`);
  const levels = headingLevels(html);
  if (levels.filter((level) => level === 1).length !== 1) {
    findings.push(`${page.path}: tek <h1> yok`);
  }
  if (levels[0] !== 1) findings.push(`${page.path}: ilk başlık h1 değil`);
  for (let index = 1; index < levels.length; index += 1) {
    const [previous = 0, level = 0] = [levels[index - 1], levels[index]];
    if (level > previous + 1) findings.push(`${page.path}: h${previous}→h${level} atlıyor`);
  }
  if (tags(html, "main").length !== 1) findings.push(`${page.path}: tek <main> yok`);
  if (tags(html, "img").some((img) => img.alt === undefined)) {
    findings.push(`${page.path}: alt'sız <img>`);
  }
  return findings;
}

// §9: sayfa başına TEK JSON-LD bloğu; ayrışır; `@graph` türleri beklenen; maçta teklif/oran
// yok; `eventStatus` yalnız başlama anı dışa aktarım anından sonraysa.
export function checkJsonLd(snapshot: Snapshot, page: ExpectedPage, html: string): string[] {
  const blocks = scripts(html).filter(isJsonLd);
  if (blocks.length !== 1) return [`${page.path}: ${blocks.length} JSON-LD bloğu`];
  let data: { "@graph"?: Record<string, unknown>[] };
  try {
    data = JSON.parse(blocks[0]?.body ?? "");
  } catch {
    return [`${page.path}: JSON-LD ayrışmıyor`];
  }
  const graph = data["@graph"] ?? [];
  const findings: string[] = [];
  const types = graph.map((node) => String(node["@type"]));
  if (!sameSet(types, page.ldTypes)) {
    findings.push(`${page.path}: JSON-LD türleri ${types.join(",")}`);
  }
  if (page.kind === "match") {
    const event = graph.find((node) => node["@type"] === "SportsEvent") ?? {};
    const match = snapshot.matches.find((each) => `match:${each.id}` === page.id);
    const future =
      match !== undefined && Date.parse(match.commence_time) > Date.parse(snapshot.generated_at);
    if ("eventStatus" in event !== future) {
      findings.push(`${page.path}: eventStatus ${future ? "eksik" : "fazla"}`);
    }
    if ("eventStatus" in event && event.eventStatus !== "https://schema.org/EventScheduled") {
      findings.push(
        `${page.path}: eventStatus ${String(event.eventStatus)} (EventScheduled değil)`,
      );
    }
    for (const banned of ["offers", "location", "odds"]) {
      if (banned in event) findings.push(`${page.path}: SportsEvent '${banned}' taşıyor`);
    }
  }
  return findings;
}

// Yayın dosyaları: `_redirects`, `data/slugs.json`, `data/snapshot.sha256`.
export function checkData(
  redirects: string,
  expectedRedirects: string,
  slugs: string,
  expectedSlugs: string,
  shaFile: string,
  digest: string,
): string[] {
  const findings: string[] = [];
  if (redirects !== expectedRedirects) findings.push("_redirects beklenenden farklı");
  if (/ 301!$/m.test(redirects)) findings.push("_redirects zorlamalı 301! taşıyor");
  if (slugs !== expectedSlugs) findings.push("data/slugs.json beklenenden farklı");
  if (shaFile.split(/\s+/)[0] !== digest) {
    findings.push("data/snapshot.sha256 dosya baytlarıyla eşleşmiyor");
  }
  return findings;
}

// Aynı yol iki blokta geçerse başlıklar BİRLEŞİR (üzerine yazılmaz): yinelenen CSP görünür kalır.
export function parseHeaders(text: string): Headers {
  const headers: Headers = new Map();
  let current: string | undefined;
  for (const line of text.split("\n")) {
    if (line.trim() === "") continue;
    if (!/^\s/.test(line)) {
      current = line.trim();
      if (!headers.has(current)) headers.set(current, []);
    } else if (current !== undefined) {
      const index = line.indexOf(":");
      headers.get(current)?.push([line.slice(0, index).trim(), line.slice(index + 1).trim()]);
    }
  }
  return headers;
}
