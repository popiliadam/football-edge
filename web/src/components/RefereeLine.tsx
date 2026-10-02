// TFF'nin maç başlamadan önce açıkladığı baş hakem (spec 2026-10-02 §6; İz B H2b genişlemesi).
// `null` iken HİÇBİR şey çizilmez — yer tutucu, "yakında", tahmin yok (spec §1). Kaynak adıyla
// yazılır ("TFF ataması"): TFF Kullanım Şartları kaynak gösterimi ister (spec §8).
import type { Lang } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";

export function RefereeLine({ name, lang }: { name: string | null; lang: Lang }) {
  if (name === null) return null;
  // Değiştirici FONKSİYON: ad `$&` gibi bir değiştirme kalıbı taşısa da harfiyen basılır.
  return <p>{t(lang, "match.referee").replace("{name}", () => name)}</p>;
}
