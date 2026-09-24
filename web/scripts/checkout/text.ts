// Görünen metin düğümleri ve ata bağlamları: dar bir etiket yığını yürüyüşü (spec §5.3). Genel bir
// HTML ayrıştırıcısı değildir — bu sitenin ürettiği biçimi okur. Betik ve stil gövdeleri metin
// değildir; yorumlar atlanır. Kapanmayan etiket (ör. `<p>` örtük kapanışı) yığında kalır: bağlam
// fazla geniş okunur, dar değil — gizli sayılan bir düğüm yanlışlıkla görünür sayılmaz.
import { type Attrs, decodeEntities, parseAttrs, stripScripts } from "../lib/html.ts";

export type Ancestor = { tag: string; attrs: Attrs };
export type TextNode = { text: string; ancestors: readonly Ancestor[] };

const VOID = new Set([
  "area",
  "base",
  "br",
  "col",
  "embed",
  "hr",
  "img",
  "input",
  "link",
  "meta",
  "source",
  "track",
  "wbr",
]);
const TOKEN =
  /<!--[\s\S]*?-->|<\/([a-zA-Z][a-zA-Z0-9-]*)\s*>|<([a-zA-Z][a-zA-Z0-9-]*)\b([^>]*)>|<[^>]*>|([^<]+)/g;

export function textNodes(html: string): TextNode[] {
  const source = stripScripts(html).replace(/<style\b[\s\S]*?<\/style>/gi, "");
  const nodes: TextNode[] = [];
  let stack: readonly Ancestor[] = [];
  for (const token of source.matchAll(TOKEN)) {
    const [whole, closing, opening, attrs, text] = token;
    if (closing !== undefined) {
      const index = stack.map((each) => each.tag).lastIndexOf(closing.toLowerCase());
      if (index >= 0) stack = stack.slice(0, index);
    } else if (opening !== undefined) {
      const tag = opening.toLowerCase();
      if (!VOID.has(tag) && !whole.endsWith("/>")) {
        stack = [...stack, { tag, attrs: parseAttrs(attrs ?? "") }];
      }
    } else if (text !== undefined) {
      nodes.push({ text: decodeEntities(text), ancestors: stack });
    }
  }
  return nodes;
}

const HIDING_STYLE = /display\s*:\s*none|visibility\s*:\s*hidden/i;

// Ziyaretçiye hiç gösterilmeyen içerik: `hidden`, `<template>`, `aria-hidden`, satır içi gizleme.
export function isHidden(node: TextNode): boolean {
  return node.ancestors.some(
    (each) =>
      each.tag === "template" ||
      each.attrs.hidden !== undefined ||
      each.attrs["aria-hidden"] === "true" ||
      HIDING_STYLE.test(each.attrs.style ?? ""),
  );
}

// Varsayılan olarak gösterilmeyen ama koşulla açılan içerik (18+ penceresi, betiksiz şerit).
export function isDeferred(node: TextNode): boolean {
  return node.ancestors.some((each) => each.tag === "dialog" || each.tag === "noscript");
}

export const within = (node: TextNode, tag: string): boolean =>
  node.ancestors.some((each) => each.tag === tag);

export const inFe = (node: TextNode): boolean =>
  node.ancestors.some((each) => each.attrs["data-fe"] !== undefined);

// Boşlukları tek boşluğa indirir: metin karşılaştırmaları satır kırmasından etkilenmez.
export const squash = (text: string): string => text.replace(/\s+/g, " ").trim();

export function joined(nodes: readonly TextNode[]): string {
  return squash(nodes.map((node) => node.text).join(" "));
}
