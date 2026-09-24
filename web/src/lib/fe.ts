// `data-fe` anahtar dilbilgisi (spec H6c): `<varlık>:<kimlik>:<noktalı yol>`.
// Sayfa bu anahtarı basar, çıktı tarayıcısı kendi beklenen kümesini BAĞIMSIZ kurar ve
// değeri anlık görüntüden bu yolla çözer. Kimliği olmayan varlıkta kimlik `-`dir.
export type FeEntity = "match" | "league" | "team" | "ledger" | "record" | "entry" | "root";

export function feKey(entity: FeEntity, id: string, path: string): string {
  return `${entity}:${id}:${path}`;
}

export const teamKey = (leagueId: string, slug: string): string => `${leagueId}/${slug}`;
