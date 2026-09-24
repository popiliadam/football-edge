// Faz 5 (value) ve Faz 7 (analiz) yuvaları. Şema v1'de ikisi de `const null`dır; bileşen
// null iken HİÇBİR şey çizmez — boş kutu, "yakında" yazısı yok (spec §7, §8.6).
export function ValueBadge({ value }: { value: null }) {
  return value;
}

export function AnalysisSlot({ value }: { value: null }) {
  return value;
}
