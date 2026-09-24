// Bir sayfanın ziyaretçiye ya da arama motoruna gösterdiği BÜTÜN metin yüzeyleri (T9 inceleme I3, M2,
// M9): metin düğümleri, satır içi etiketlerle bölünmüş sözcüklerin birleşik hâli, görünen/okunan
// öznitelikler (`alt`, `title`, `placeholder`, `value`, `aria-*`, `<meta content>`), JSON-LD dize
// yaprakları ve Next'in istemci gezinmesinde gösterdiği RSC verisi (satır içi `self.__next_f` ve `.txt`).
import { isJsonLd, scripts, stripScripts, tags } from "../lib/html.ts";
import { textNodes } from "./text.ts";

// Görünüşte sözcük bölmeyen (satır içi) öğeler: `val<b></b>ue` tarayıcıda `value` okunur.
const INLINE =
  "a|abbr|b|bdi|bdo|cite|code|data|dfn|em|i|kbd|mark|q|s|samp|small|span|strong|sub|sup|u|var|wbr";
const INLINE_TAG = new RegExp(`<\\/?(?:${INLINE})\\b[^>]*>`, "gi");

// Yorumlar ve satır içi etiketler silinir (boşluk BIRAKILMAZ); blok sınırları korunur.
export function mergeInline(html: string): string {
  return stripScripts(html)
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(INLINE_TAG, "");
}

const TEXT_ATTRS = ["alt", "title", "placeholder", "value"];

export function attrTexts(html: string): string[] {
  return tags(html, "[a-z][a-z0-9-]*").flatMap((attrs) =>
    Object.entries(attrs)
      .filter(
        ([name]) => TEXT_ATTRS.includes(name) || name.startsWith("aria-") || name === "content",
      )
      .map(([, value]) => value),
  );
}

// Arama sonucunda görünen `<meta>` metni (sayı kuralı için; `viewport`/`robots` değil).
export function metaTexts(html: string): string[] {
  return tags(html, "meta")
    .filter((meta) => /^(description|og:|twitter:)/.test(meta.name ?? meta.property ?? ""))
    .map((meta) => meta.content ?? "");
}

export type LdString = { key: string; value: string };

function leaves(value: unknown, key: string): LdString[] {
  if (typeof value === "string") return [{ key, value }];
  if (value === null || typeof value !== "object") return [];
  return Object.entries(value).flatMap(([name, inner]) =>
    leaves(inner, Array.isArray(value) ? key : name),
  );
}

export function ldStrings(html: string): LdString[] {
  return scripts(html)
    .filter(isJsonLd)
    .flatMap((block) => {
      try {
        return leaves(JSON.parse(block.body), "");
      } catch {
        return []; // ayrışmayan JSON-LD'yi checkJsonLd raporlar
      }
    });
}

const isUrl = (text: string): boolean => /^[a-z][a-z0-9+.-]*:\/\//i.test(text);

// Sözcük ve lisans taramalarının gördüğü metinler.
export function surfaceTexts(html: string): string[] {
  return [
    ...textNodes(html).map((node) => node.text),
    ...textNodes(mergeInline(html)).map((node) => node.text),
    ...attrTexts(html),
    ...ldStrings(html)
      .map((leaf) => leaf.value)
      .filter((value) => !isUrl(value)),
  ];
}

// RSC metnindeki JSON dize DEĞERLERİ: nesne anahtarları (`"data-fe-value":`, `"unauthorized":`),
// React başvuruları (`$…`), yollar ve URL'ler hariç.
export function rscStrings(text: string): string[] {
  const found: string[] = [];
  for (const match of text.matchAll(/"(?:[^"\\\n]|\\.)*"/g)) {
    const literal = match[0];
    if (text[(match.index ?? 0) + literal.length] === ":") continue;
    try {
      const value = JSON.parse(literal) as string;
      if (!/^[$/]/.test(value) && !isUrl(value)) found.push(value);
    } catch {
      // JSON olmayan parça (RSC satır öneki vb.) metin değildir
    }
  }
  return found;
}

// Sayfaya gömülü RSC verisi: `self.__next_f.push([1,"…"])` gövdelerindeki metin.
export function inlineRscStrings(html: string): string[] {
  return scripts(html).flatMap((script) => {
    const call = /^self\.__next_f\.push\((\[[\s\S]*\])\)$/.exec(script.body)?.[1];
    if (call === undefined) return [];
    try {
      const payload = JSON.parse(call) as unknown[];
      return typeof payload[1] === "string" ? rscStrings(payload[1]) : [];
    } catch {
      return [];
    }
  });
}
