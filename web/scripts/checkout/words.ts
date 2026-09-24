import { decodeNamed } from "./entities.ts";

// Görünen metin sözcük listeleri (T5 carry-in 2, T7 carry-in 9). Katlama Türkçe büyük/küçük harfe
// duyarlıdır: `toLocaleLowerCase("tr")` (İ→i, I→ı), aksanlar düşer, ı→i, boşluklar teke iner. Biçim
// karakterleri (sıfır genişlikli boşluk, yumuşak tire: `\p{Cf}`) önce silinir: `Pin\u200bnacle` = `pinnacle`.
export function fold(text: string): string {
  return decodeNamed(text)
    .replace(/\p{Cf}/gu, "")
    .toLocaleLowerCase("tr")
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .replace(/ı/g, "i")
    .replace(/\s+/g, " ");
}

const unique = (items: readonly string[]): string[] =>
  items.filter((item, index) => items.indexOf(item) === index);

// Spec H4 listesi + T7 incelemesinin genişletmesi (licenced/authorised, "resmî ortağ-" kökü).
export const LICENSE_PATTERNS: readonly string[] = unique(
  [
    "lisanslı",
    "licensed",
    "licenced",
    "resmi veri",
    "resmî veri",
    "official data",
    "official partner",
    "resmi ortak",
    "resmî ortak",
    "resmî ortağ",
    "authorized",
    "authorised",
    "yetkili veri",
  ].map(fold),
);

// The Odds API kitap anahtarları (eu/uk/us/au bölgeleri; T5 incelemesinin listesi): anahtarın
// bölge ekinden önceki kökü + boşluklu ticari adlar. Görünen metinde hiçbiri geçmez (B7).
const BOOK_KEYS = `1xbet onexbet 888sport sport888 betclic betfair betfair_ex_eu betfair_ex_uk betfair_ex_au
betfair_sb_uk betonlineag betmgm betrivers betsson betus betvictor betway bovada boylesports casumo coolbet coral
draftkings everygame fanduel grosvenor gtbets leovegas livescorebet ladbrokes_uk lowvig marathonbet matchbook
mybookieag nordicbet paddypower pinnacle pointsbetus pointsbetau skybet smarkets sportsbet superbook suprabets
tabtouch topsport unibet_eu unibet_uk unibet_se unibet_nl unibet_fr unibet_it virginbet williamhill williamhill_us
wynnbet winamax_fr winamax_de neds playup betr_au bluebet espnbet fliff hardrockbet ballybet betparx betanysports
tipico_de codere_it betfred sisal snai goldbet lottomatica bet365 10bet caesars`;
const BOOK_TITLES = [
  "william hill",
  "paddy power",
  "sky bet",
  "bet victor",
  "livescore bet",
  "virgin bet",
  "marathon bet",
  "nordic bet",
  "betonline.ag",
  "mybookie",
  "hard rock bet",
  "bally bet",
  "espn bet",
  "betfair exchange",
  "points bet",
];
export const BOOKMAKERS: readonly string[] = unique([
  ...BOOK_KEYS.split(/\s+/).map((key) => key.split("_")[0] ?? key),
  ...BOOK_TITLES,
]).map(fold);

// Öneri yüzeyi sözcükleri (kök; sağa ek alabilir: values, önerisi, valörü, bankoyu, tavsiyesi).
// Sol sınır zorunlu. Türkçe value/tavsiye dağarcığı controller kararıyla (T9 inceleme I4).
export const SUGGESTION_WORDS: readonly string[] = [
  "value",
  "edge",
  "öneri",
  "değer bahis",
  "değer bahs",
  "değerli bahis",
  "valör",
  "banko",
  "tavsiye",
  "kupon",
  "iddaa",
].map(fold);

// İzinli cümleler TAM cümle olarak SÖZLÜKTEN okunur: sorumluluk reddi, "value önerisi
// yayımlamıyoruz" ve boş sicilin CLV açıklaması. Terim ya da kelime düzeyinde muafiyet YOK.
export const ALLOWED_SENTENCE_KEYS = [
  "home.intro",
  "footer.notAdvice",
  "record.emptyExplain",
] as const;
// Sözlük dışındaki izinli cümleler (yasal taslaklar): birebir, TAM cümle. Kaynağı adıyla yazılır.
export const ALLOWED_SENTENCES: readonly string[] = [
  // content/legal/tr/terms.tsx — "Garanti yoktur" (sorumluluk reddi)
  "Bu sitedeki hiçbir içerik bahis, finans ya da yatırım tavsiyesi değildir.",
];

export const escapeRegExp = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function wordPattern(word: string, stem: boolean): RegExp {
  return new RegExp(
    `(?<![\\p{L}\\p{N}_])${escapeRegExp(word)}${stem ? "" : "(?![\\p{L}\\p{N}_])"}`,
    "u",
  );
}
