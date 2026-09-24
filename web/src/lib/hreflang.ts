// hreflang (spec §8.3): her sayfa etkin BÜTÜN dillere + x-default'a bağlanır, kendine atıflıdır.
import { DEFAULT_LANG, type Lang, SITE_LANGS } from "../../site.config.ts";
import { absoluteUrl } from "./routes.ts";

export type Alternates = { canonical: string; languages: Record<string, string> };

export function alternatesFor(lang: Lang, pathOf: (lang: Lang) => string): Alternates {
  const languages: Record<string, string> = {};
  for (const each of SITE_LANGS) languages[each] = absoluteUrl(pathOf(each));
  languages["x-default"] = absoluteUrl(pathOf(DEFAULT_LANG));
  return { canonical: absoluteUrl(pathOf(lang)), languages };
}
