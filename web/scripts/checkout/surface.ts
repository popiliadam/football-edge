// Bir sayfanın ziyaretçiye ya da arama motoruna gösterdiği BÜTÜN metin yüzeyleri (T9 inceleme I3, M2,
// M9): metin düğümleri, satır içi etiketlerle bölünmüş sözcüklerin birleşik hâli, görünen/okunan
// öznitelikler (`alt`, `title`, `placeholder`, `value`, `aria-*`, `<meta content>`), JSON-LD dize
// yaprakları ve Next'in istemci gezinmesinde gösterdiği RSC verisi (satır içi `self.__next_f` ve `.txt`).
import { isExecutableInline, isJsonLd, scripts, stripScripts, tags } from "../lib/html.ts";
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

// JSON metnindeki dize DEĞİŞMEZLERİ, ham okumayla (JSON.parse değil): yinelenen anahtarın ilk değeri
// de görünür (T9 yeniden inceleme N4b). Nesne anahtarları değer değildir; bir değerin anahtarı, hemen
// önünde `"anahtar":` duruyorsa odur, dizi öğesinde boştur.
export function jsonValues(text: string): LdString[] {
  const found: LdString[] = [];
  let key = "";
  for (const match of text.matchAll(/"(?:[^"\\\n]|\\.)*"/g)) {
    const literal = match[0];
    const start = match.index ?? 0;
    let value: string;
    try {
      value = JSON.parse(literal) as string;
    } catch {
      continue; // JSON olmayan parça (RSC satır öneki vb.)
    }
    if (/^\s*:/.test(text.slice(start + literal.length, start + literal.length + 8))) {
      key = value;
      continue;
    }
    const keyed = /:\s*$/.test(text.slice(Math.max(0, start - 8), start));
    found.push({ key: keyed ? key : "", value });
  }
  return found;
}

export function ldStrings(html: string): LdString[] {
  return scripts(html)
    .filter(isJsonLd)
    .flatMap((block) => jsonValues(block.body));
}

// Yalnız TAM biçimleri atlanır (N3/N4a): Next başvurusu, boşluksuz yol, boşluksuz URL. `\s` NBSP'yi de
// kapsar: "https://…/ Pinnacle value" bir URL değil metindir. Yollar ve URL'ler bağlantı denetimine gider.
const EXACT_REF = /^\$[\w@:$.-]*$/;
export const EXACT_LINK = /^(?:\/\S*|[a-z][a-z0-9+.-]*:\/\/\S*)$/i;

// Sözcük ve lisans taramalarının gördüğü metinler. JSON-LD'de ardışık iki değer bir de bitişik okunur:
// iki anahtara bölünmüş ad (`"Pinn"`, `"acle"`) görünür (yeniden inceleme n04a).
export function surfaceTexts(html: string): string[] {
  const ld = ldStrings(html)
    .map((leaf) => leaf.value)
    .filter((value) => !EXACT_LINK.test(value));
  return [
    ...textNodes(html).map((node) => node.text),
    ...textNodes(mergeInline(html)).map((node) => node.text),
    ...attrTexts(html),
    ...ld,
    ...ld.slice(1).map((value, index) => `${ld[index]}${value}`),
  ];
}

// RSC metni: taranacak dizeler (başvuru ve bağlantı hariç) ve bağlantı denetimine gidenler.
export function rscStrings(text: string): string[] {
  return jsonValues(text)
    .map((leaf) => leaf.value)
    .filter((value) => !EXACT_REF.test(value) && !EXACT_LINK.test(value));
}

export function rscLinks(text: string): string[] {
  return jsonValues(text)
    .map((leaf) => leaf.value)
    .filter((value) => EXACT_LINK.test(value));
}

// Next'in satır içi betikleri (T9 yeniden inceleme FP1, N2): önce birebir önyükleme, ardından BİR YA DA
// DAHA FAZLA veri itişi. Her itiş TAM ayrışmalı: `self.__next_f.push(` + JSON dizi `[1,"…"]` + `)`.
// Büyük sayfada Next veriyi birden çok itişe böler (700 maçlık lig sayfasında 4). RSC metni itişlerin
// sırayla birleşimidir.
export const BOOT = "(self.__next_f=self.__next_f||[]).push([0])";

export type NextPushes = { boot: boolean; payload: string; malformed: number; pushes: number };

export function nextPushes(html: string): NextPushes {
  const [first, ...rest] = scripts(html)
    .filter(isExecutableInline)
    .map((script) => script.body);
  let malformed = 0;
  let payload = "";
  for (const body of rest) {
    const call = /^self\.__next_f\.push\(([\s\S]*)\)$/.exec(body)?.[1];
    let data: unknown;
    try {
      data = call === undefined ? undefined : JSON.parse(call);
    } catch {
      data = undefined;
    }
    if (Array.isArray(data) && data.length === 2 && data[0] === 1 && typeof data[1] === "string") {
      payload += data[1];
    } else {
      malformed += 1;
    }
  }
  return { boot: first === BOOT, payload, malformed, pushes: rest.length };
}
