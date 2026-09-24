// Arayüz sözlükleri (spec §8.3): kütüphane yok, tipli erişimci. Anahtar kümesi `en`
// sözlüğünden türetilir; `tr` aynı kümeyi taşımak zorundadır (dict.test.ts). Veri
// dilden bağımsızdır — yalnız arayüz metni çevrilir.
import type { Lang } from "../../site.config.ts";
import en from "./en.json" with { type: "json" };
import tr from "./tr.json" with { type: "json" };

export type DictKey = keyof typeof en;

export const DICTIONARIES: Record<Lang, Record<DictKey, string>> = { en, tr };

export function t(lang: Lang, key: DictKey): string {
  return DICTIONARIES[lang][key];
}
