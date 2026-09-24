import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { LEGAL_DOCS, SITE_LANGS } from "../../site.config.ts";

const DIR = import.meta.dirname;
const read = (lang: string, doc: string) => readFileSync(resolve(DIR, lang, `${doc}.tsx`), "utf-8");

// H4 (spec §3.2/5): büyük/küçük harf ve aksan katlanmış kalıplar. Türkçe yerel ayarıyla küçültülür
// ("LİSANSLI" → "lisanslı"), sonra noktasız ı da i'ye katlanır: böylece Türkçe küçültmenin
// "LICENSED"ı "lıcensed" yapması ve noktasız yazılmış "LISANSLI" da yakalanır.
function fold(text: string): string {
  return text
    .toLocaleLowerCase("tr")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/ı/g, "i")
    .replace(/\s+/g, " ");
}

const LICENSE_NEGATION = /<p data-fe-allow="license-negation">[\s\S]*?<\/p>/g;

const H4_PATTERNS = [
  "lisanslı",
  "licensed",
  "resmi veri",
  "resmî veri",
  "official data",
  "official partner",
  "resmi ortak",
  "resmî ortak",
  "authorized",
  "yetkili veri",
].map(fold);

describe("yasal taslaklar (spec §10.1)", () => {
  it("her dilde dört belge var, fazlası yok", () => {
    for (const lang of SITE_LANGS) {
      const files = readdirSync(resolve(DIR, lang)).sort();
      expect(files).toEqual(LEGAL_DOCS.map((doc) => `${doc}.tsx`).sort());
    }
  });

  it.each(SITE_LANGS.flatMap((lang) => LEGAL_DOCS.map((doc) => [lang, doc] as const)))(
    "%s/%s 'TASLAK — avukat onayı bekler' başlığını taşır",
    (lang, doc) => {
      expect(read(lang, doc)).toContain("TASLAK — avukat onayı bekler");
    },
  );

  it("yardım hattı iletişim bilgileri [DOĞRULANACAK] işaretli", () => {
    for (const lang of SITE_LANGS)
      expect(read(lang, "responsible-gambling")).toContain("[DOĞRULANACAK]");
  });

  it("KVKK soruları avukat sorusu olarak işaretli", () => {
    for (const lang of SITE_LANGS) expect(read(lang, "privacy")).toContain("[AVUKAT SORUSU]");
  });

  it("lisans olumsuzlaması her dilin koşullarında tam bir kez işaretli (H4)", () => {
    for (const lang of SITE_LANGS) {
      expect(read(lang, "terms").split('data-fe-allow="license-negation"')).toHaveLength(2);
    }
  });

  it("H4 kalıpları olumsuzlama paragrafı dışında geçmez (Türkçe büyük harf ve aksan katlanır)", () => {
    for (const lang of SITE_LANGS) {
      for (const doc of LEGAL_DOCS) {
        const source = read(lang, doc);
        const negations = source.match(LICENSE_NEGATION) ?? [];
        if (doc === "terms") {
          // Katlama boşa düşerse olumsuzlama paragrafının kalıbı da görünmez olurdu.
          expect(H4_PATTERNS.some((pattern) => fold(negations.join(" ")).includes(pattern))).toBe(
            true,
          );
        }
        const rest = fold(source.replace(LICENSE_NEGATION, ""));
        for (const pattern of H4_PATTERNS) {
          expect(rest.includes(pattern), `${lang}/${doc}: ${pattern}`).toBe(false);
        }
      }
    }
  });
});
