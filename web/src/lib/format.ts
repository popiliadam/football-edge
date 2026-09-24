// Biçimleme sözleşmesi (spec §5.4): sayı anlık görüntüde GÖRÜNTÜ hassasiyetindedir.
// Bu fonksiyon yalnız ondalık ayracı ve birim ekler; yuvarlamaz, çarpmaz, toplamaz.
// Hassasiyetten fazla ondalık taşıyan değer sözleşme ihlalidir → hata (sessiz yuvarlama yok).
import type { Lang } from "../../site.config.ts";

export type NumberKind = "pct1" | "pp1" | "pct2" | "price2" | "int";

const DECIMALS: Record<NumberKind, number> = { pct1: 1, pp1: 1, pct2: 2, price2: 2, int: 0 };
const SEPARATOR: Record<Lang, string> = { en: ".", tr: "," };

export class FormatError extends Error {}

function digits(value: number, decimals: number, lang: Lang): string {
  if (!Number.isFinite(value)) throw new FormatError(`sonlu olmayan sayı: ${value}`);
  const text = String(value);
  if (/e/i.test(text)) throw new FormatError(`üslü gösterim: ${text}`);
  const negative = text.startsWith("-");
  const [whole, fraction = ""] = (negative ? text.slice(1) : text).split(".");
  if (fraction.length > decimals) {
    throw new FormatError(`${text} görüntü hassasiyetinden (${decimals}) fazla ondalık taşıyor`);
  }
  const padded = decimals === 0 ? "" : SEPARATOR[lang] + fraction.padEnd(decimals, "0");
  return (negative ? "-" : "") + whole + padded;
}

export function formatNumber(value: number, kind: NumberKind, lang: Lang): string {
  const number = digits(value, DECIMALS[kind], lang);
  if (kind === "pct1" || kind === "pct2") return lang === "tr" ? `%${number}` : `${number}%`;
  if (kind === "pp1") return lang === "tr" ? `${number} puan` : `${number} pp`;
  return number;
}
