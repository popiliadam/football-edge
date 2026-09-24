// Sayfa üst verisi (spec §8.3, §8.4, H7): hreflang + kanonik her sayfada; `noindex`
// bayrak kapalıyken HER sayfada, açıkken kaydın `indexable`ına göre.
import type { Metadata } from "next";
import { indexingEnabled, type Lang } from "../../site.config.ts";
import { alternatesFor } from "./hreflang.ts";

export function pageMetadata(
  lang: Lang,
  pathOf: (lang: Lang) => string,
  title: string,
  recordIndexable: boolean,
): Metadata {
  const indexable = indexingEnabled() && recordIndexable;
  return {
    title,
    alternates: alternatesFor(lang, pathOf),
    ...(indexable ? {} : { robots: { index: false } }),
  };
}
