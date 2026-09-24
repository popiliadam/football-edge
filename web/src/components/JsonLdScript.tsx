import { type JsonLd, serializeLd } from "../lib/jsonld.ts";

// Veri bloğu (spec §9): CSP'ye tabi değildir ve hash listesine girmez (§5.3/7).
export function JsonLdScript({ data }: { data: JsonLd }) {
  return (
    <script
      type="application/ld+json"
      // biome-ignore lint/security/noDangerouslySetInnerHtml: JSON-LD veri bloğu; `<` serializeLd'de kaçışlanır.
      dangerouslySetInnerHTML={{ __html: serializeLd(data) }}
    />
  );
}
