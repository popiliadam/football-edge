// Ana sayfanın "yaklaşan maçlar" şeridi: dışa aktarım anından SONRA başlayan ve son turu görünen maçlar,
// başlama saatine (eşitlikte kimliğe) göre. Saat anlık görüntünün `generated_at`idir (deterministik).
// check-out aynı kuralı kendisi yeniden türetir (`scripts/checkout/numbers.ts` `upcomingOf`).
import type { Match, Snapshot } from "./snapshot-types.ts";

export const UPCOMING_LIMIT = 8;

export function upcomingMatches(snapshot: Snapshot): Match[] {
  const now = Date.parse(snapshot.generated_at);
  return snapshot.matches
    .filter((match) => Date.parse(match.commence_time) > now && match.h2h.latest !== null)
    .sort((a, b) => a.commence_time.localeCompare(b.commence_time) || a.id.localeCompare(b.id))
    .slice(0, UPCOMING_LIMIT);
}
