// Sitenin yer tutucu kimliği ve dil listesi — TEK kaynak (spec §8.3, AK3, AK4, AK5).
// Marka, alan adı ve diller kullanıcı kararıdır; kodun başka hiçbir yeri bu değerleri
// literal olarak taşımaz (src/lib/site-config.test.ts sınar).

export const SITE_NAME = "[site-name]";
export const SITE_URL = "https://example.invalid";
// Çıpa geçmişinin herkese açık adresi (spec §6.1): depo adı da bir yayın kararıdır. Taban, deponun
// `ledger/` DİZİNİNİN geçmişidir — sayfa ona çıplak `head-YYYY-MM-DD.txt` adını ekler (sözleşmenin çıpa
// `file` alanı dizinsizdir). Gerçek değer AK3/AK4 ile birlikte yazılır, ör. `…/commits/main/ledger`.
export const LEDGER_HISTORY_URL = "https://example.invalid/ledger";

export const SITE_LANGS = ["en", "tr"] as const;
export type Lang = (typeof SITE_LANGS)[number];
export const DEFAULT_LANG: Lang = "en";

// §8.1: lig slug'ı sabit bölüt adı olamaz; `data` ve `_next` derleme çıktısının dizinleridir.
export const RESERVED_LEAGUE_SLUGS: readonly string[] = ["track-record", "legal", "data", "_next"];
export const RESERVED_TEAM_SLUGS: readonly string[] = ["match"];

export const LEGAL_DOCS = ["terms", "privacy", "cookies", "responsible-gambling"] as const;
export type LegalDoc = (typeof LEGAL_DOCS)[number];

export function isLang(value: string): value is Lang {
  return (SITE_LANGS as readonly string[]).includes(value);
}

// H7/B8: bayrak yoksa HER sayfa noindex. Yalnız tam olarak "1" açar.
export function indexingEnabled(env: Record<string, string | undefined> = process.env): boolean {
  return env.SITE_INDEXABLE === "1";
}
