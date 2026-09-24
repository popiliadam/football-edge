// Site haritası (spec §5.3/5, §8.4): yalnız etkin olarak indekslenebilir sayfalar; her
// girdi bütün dillere `alternates` taşır. Bayrak kapalıyken BOŞTUR (her sayfa noindex).
import type { MetadataRoute } from "next";
import { indexingEnabled } from "../../site.config.ts";
import { sitemapEntries } from "../lib/pages.ts";
import { loadSnapshot } from "../lib/snapshot.ts";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return sitemapEntries(loadSnapshot(), indexingEnabled());
}
