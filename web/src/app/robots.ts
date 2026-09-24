// H7: `noindex` döneminde robots.txt `Disallow` TAŞIMAZ — taşırsa tarayıcı sayfayı hiç
// çekmez ve `noindex`i göremez.
import type { MetadataRoute } from "next";
import { absoluteUrl } from "../lib/routes.ts";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", allow: "/" }, sitemap: absoluteUrl("/sitemap.xml") };
}
