// Kapanış durumu (DEFERRED 9.7g): mühürlü · bekleniyor (maç başlamadı ya da tam başlama anı) ·
// kaydedilmedi (başlama anı geçti, kapanış mühürlenmedi — artık gelmez). Sınır boru hattıyla aynı:
// `rounds.seal_window` mühürü tam başlama anında hâlâ kabul eder, kaçırılanı `commence_time < now` sayar. Saat, derlemenin tek saati olan anlık görüntünün `generated_at`idir:
// aynı anlık görüntü her derlemede aynı sayfayı verir. Çözülemeyen zaman sessizce "bekleniyor" sayılmaz.
import type { Match } from "./snapshot-types.ts";

export type ClosingState = "sealed" | "awaiting" | "missed";

function instant(iso: string, field: string): number {
  const value = Date.parse(iso);
  if (Number.isNaN(value)) throw new Error(`${field} çözülemedi: ${iso}`);
  return value;
}

export function closingState(
  match: Pick<Match, "sealed" | "commence_time">,
  generatedAt: string,
): ClosingState {
  const now = instant(generatedAt, "generated_at");
  const kickoff = instant(match.commence_time, "commence_time");
  if (match.sealed) return "sealed";
  return kickoff < now ? "missed" : "awaiting";
}
