import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LEGAL_DOCS, SITE_LANGS } from "../../site.config.ts";
import LegalPage from "../../src/app/[lang]/legal/[doc]/page.tsx";
import { t } from "../../src/i18n/dict.ts";

const DIR = import.meta.dirname;
const read = (lang: string, doc: string) => readFileSync(resolve(DIR, lang, `${doc}.tsx`), "utf-8");
const PAIRS = SITE_LANGS.flatMap((lang) => LEGAL_DOCS.map((doc) => [lang, doc] as const));

// H4 (spec §3.2/5): büyük/küçük harf ve aksan katlanmış kalıplar. Türkçe yerel ayarıyla küçültülür
// ("LİSANSLI" → "lisanslı"), sonra noktasız ı da i'ye katlanır: böylece Türkçe küçültmenin
// "LICENSED"ı "lıcensed" yapması ve noktasız yazılmış "LISANSLI" da yakalanır.
function fold(text: string): string {
  return text
    .toLocaleLowerCase("tr")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/ı/g, "i")
    .replace(/\s+/g, " ")
    .trim();
}

const LICENSE_NEGATION = /<p data-fe-allow="license-negation">([\s\S]*?)<\/p>/g;

// Spec H4 listesi + yaygın biçimler (inceleme T7 m1): İngiliz yazımı ve Türkçe k→ğ yumuşaması
// ("resmî ortağıyız" katlanınca "resmi ortag…" olur, "resmi ortak" kalıbına uymaz).
const H4_PATTERNS = [
  "lisanslı",
  "licensed",
  "licenced",
  "resmi veri",
  "resmî veri",
  "official data",
  "official partner",
  "resmi ortak",
  "resmî ortak",
  "resmi ortağ",
  "resmî ortağ",
  "authorized",
  "authorised",
  "yetkili veri",
].map(fold);

// İzinli olumsuzlama paragrafı sabittir: içine olumlu bir iddia girerse işaret onu örtmesin.
const NEGATION_TEXT: Record<(typeof SITE_LANGS)[number], string> = {
  en: "We make no claim that our data is licensed, that it is official data, or that we are an official partner of any league, club or data provider.",
  tr: "Verilerimizin lisanslı olduğu, resmî veri olduğu ya da herhangi bir lig, kulüp veya veri sağlayıcının resmî ortağı olduğumuz yönünde hiçbir iddiada bulunmuyoruz.",
};

// İnceleme ile düzeltilen yanlış ya da kapsamsız iddialar (T7 I1, I2) geri gelmez.
const RETRACTED_CLAIMS = [
  "public, hash-chained ledger",
  "herkese açık, hash zincirli",
  "we do not collect personal data.",
  "kişisel veri toplamıyoruz.",
].map(fold);

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

describe("yasal taslaklar (spec §10.1)", () => {
  it("her dilde dört belge var, fazlası yok", () => {
    for (const lang of SITE_LANGS) {
      const files = readdirSync(resolve(DIR, lang)).sort();
      expect(files).toEqual(LEGAL_DOCS.map((doc) => `${doc}.tsx`).sort());
    }
  });

  it.each(PAIRS)(
    "%s/%s sayfası 'TASLAK — avukat onayı bekler' işaretini başlığın altında görünür basar",
    async (lang, doc) => {
      const draft = t(lang, "legal.draft");
      expect(draft.startsWith("TASLAK — avukat onayı bekler")).toBe(true);
      const html = renderToStaticMarkup(
        await LegalPage({ params: Promise.resolve({ lang, doc }) }),
      );
      // Yalnız sınıf özniteliği: `hidden`, `style` ya da yoruma alınmış bir işaret eşleşmez.
      expect(html).toMatch(new RegExp(`</h1><p(?: class="[^"]*")?>${escapeRegExp(draft)}</p>`));
      // Tek kaynak: içerik dosyaları işareti kendileri taşımaz.
      expect(read(lang, doc)).not.toContain("TASLAK");
    },
  );

  it("yardım hattı listesinde her satır [DOĞRULANACAK] işaretli", () => {
    for (const lang of SITE_LANGS) {
      const items = read(lang, "responsible-gambling").match(/<li>[\s\S]*?<\/li>/g) ?? [];
      expect(items.length).toBeGreaterThanOrEqual(2);
      for (const item of items) expect(item, `${lang}: ${item}`).toContain("[DOĞRULANACAK]");
    }
  });

  it("gizlilik metninin avukat soruları işaretli: IP kayıtları, işleyen/aktarım, haber hattı", () => {
    for (const lang of SITE_LANGS) {
      expect(read(lang, "privacy").split("[AVUKAT SORUSU]")).toHaveLength(4);
    }
  });

  it("lisans olumsuzlaması yalnız koşullar belgesinde ve tam bir kez işaretli (H4)", () => {
    for (const [lang, doc] of PAIRS) {
      const markers = read(lang, doc).split('data-fe-allow="license-negation"').length - 1;
      expect(markers, `${lang}/${doc}`).toBe(doc === "terms" ? 1 : 0);
    }
  });

  it("olumsuzlama paragrafının metni sabittir (içine olumlu iddia giremez)", () => {
    for (const lang of SITE_LANGS) {
      const paragraphs = [...read(lang, "terms").matchAll(LICENSE_NEGATION)].map((m) =>
        fold(m[1] ?? ""),
      );
      expect(paragraphs).toEqual([fold(NEGATION_TEXT[lang])]);
    }
  });

  it("H4 kalıpları olumsuzlama paragrafı dışında geçmez (Türkçe büyük harf ve aksan katlanır)", () => {
    for (const [lang, doc] of PAIRS) {
      const source = read(lang, doc);
      if (doc === "terms") {
        // Katlama boşa düşerse olumsuzlama paragrafının kalıbı da görünmez olurdu.
        const negation = fold((source.match(LICENSE_NEGATION) ?? []).join(" "));
        expect(H4_PATTERNS.some((pattern) => negation.includes(pattern))).toBe(true);
      }
      const rest = fold(source.replace(LICENSE_NEGATION, ""));
      for (const pattern of H4_PATTERNS) {
        expect(rest.includes(pattern), `${lang}/${doc}: ${pattern}`).toBe(false);
      }
    }
  });

  it("düzeltilen iddialar geri gelmez: defter satırları yayımlanmaz, veri cümlesi ziyaretçiyle sınırlı", () => {
    for (const [lang, doc] of PAIRS) {
      const text = fold(read(lang, doc));
      for (const claim of RETRACTED_CLAIMS) {
        expect(text.includes(claim), `${lang}/${doc}: ${claim}`).toBe(false);
      }
    }
  });
});
