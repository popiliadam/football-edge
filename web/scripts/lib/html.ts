// Bağımlılıksız, DAR bir HTML okuyucusu (spec §5.3). Genel bir ayrıştırıcı değildir:
// yalnız bu sitenin kendi ürettiği biçimi okur ve okuyamadığını adıyla raporlar.
// Kapsam sınırı: `data-fe` öğesinin çocuğu tek bir metin olmalıdır (Fe.tsx bunu garanti eder).
import { createHash } from "node:crypto";

export type Attrs = Record<string, string>;
export type Script = { attrs: Attrs; body: string };
export type Element = { tag: string; attrs: Attrs; text: string };

const ATTR = /([A-Za-z_:][-A-Za-z0-9_:.]*)(?:\s*=\s*"([^"]*)")?/g;
const SCRIPT = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
const FE_ELEMENT = /<([a-z][a-z0-9]*)\b([^>]*\bdata-fe="[^"]*"[^>]*)>([^<]*)<\/\1>/g;

// Öznitelik adları küçük harfe katlanır: React `hrefLang`, `dateTime`, `colSpan` basar.
export function parseAttrs(source: string): Attrs {
  const attrs: Attrs = {};
  for (const match of source.matchAll(ATTR)) {
    const name = match[1];
    if (name) attrs[name.toLowerCase()] = decodeEntities(match[2] ?? "");
  }
  return attrs;
}

export function decodeEntities(text: string): string {
  return text
    .replace(/&#x([0-9a-f]+);/gi, (_, hex: string) =>
      String.fromCodePoint(Number.parseInt(hex, 16)),
    )
    .replace(/&#(\d+);/g, (_, dec: string) => String.fromCodePoint(Number.parseInt(dec, 10)))
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

export function scripts(html: string): Script[] {
  return [...html.matchAll(SCRIPT)].map((match) => ({
    attrs: parseAttrs(match[1] ?? ""),
    body: match[2] ?? "",
  }));
}

// `<script` açılışlarının bağımsız sayımı: `scripts()` birini kaçırırsa eşitlik bozulur.
export function scriptOpenings(html: string): number {
  return (html.match(/<script\b/gi) ?? []).length;
}

export function isJsonLd(script: Script): boolean {
  return script.attrs.type === "application/ld+json";
}

// Satır içi YÜRÜTÜLEBİLİR betik: `src` yok ve tip JS (yok, text/javascript ya da module).
export function isExecutableInline(script: Script): boolean {
  const type = script.attrs.type;
  const js = type === undefined || type === "" || type === "module" || type === "text/javascript";
  return script.attrs.src === undefined && js;
}

export function cspHash(body: string): string {
  return `'sha256-${createHash("sha256").update(body, "utf8").digest("base64")}'`;
}

export function stripScripts(html: string): string {
  return html.replace(SCRIPT, "");
}

export function feElements(html: string): Element[] {
  return [...stripScripts(html).matchAll(FE_ELEMENT)].map((match) => ({
    tag: match[1] ?? "",
    attrs: parseAttrs(match[2] ?? ""),
    text: decodeEntities(match[3] ?? ""),
  }));
}

// `data-fe` taşıyan açılış etiketi sayısı: `feElements` okuyamadığı biçimi atlarsa görünür.
export function feOpenings(html: string): number {
  return (stripScripts(html).match(/<[a-z][a-z0-9]*\b[^>]*\bdata-fe="/g) ?? []).length;
}

export function tags(html: string, tag: string): Attrs[] {
  const pattern = new RegExp(`<${tag}\\b([^>]*?)\\/?>`, "gi");
  return [...stripScripts(html).matchAll(pattern)].map((match) => parseAttrs(match[1] ?? ""));
}

export function headingLevels(html: string): number[] {
  return [...stripScripts(html).matchAll(/<h([1-6])\b/gi)].map((match) => Number(match[1]));
}

export function visibleText(html: string): string {
  const withoutCode = stripScripts(html).replace(/<style\b[\s\S]*?<\/style>/gi, "");
  return decodeEntities(withoutCode.replace(/<!--[\s\S]*?-->/g, "").replace(/<[^>]+>/g, " "));
}
