// Sicil girdisinin sonucu sözleşmede `home`/`draw`/`away`dır (şema enum'u). Ekranda takım adı ya da
// sözlüğün "Beraberlik"i basılır — hesap değil eşleme. Çıktı tarayıcısı yalnız ham özniteliği sınar;
// bu eşlemenin doğruluğu BURADA birim testiyle ölçülür (outcome.test.ts).
import type { Match, RecordEntry } from "./snapshot-types.ts";

export function outcomeLabel(
  outcome: RecordEntry["outcome"],
  match: Match | undefined,
  drawLabel: string,
): string {
  if (outcome === "draw") return drawLabel;
  return match ? match[outcome] : outcome;
}
