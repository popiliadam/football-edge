// Anlık görüntüden gelen HER değer bu bileşenlerle basılır (spec H6c): öznitelik anlık
// görüntüdeki değerin birebir metni, görünen metin `formatNumber(değer)`. Çocuk TEK bir
// dizedir — React iki komşu metin arasına `<!-- -->` koyar ve tarayıcı eşitliği bozulur.
import type { ReactNode } from "react";
import type { Lang } from "../../site.config.ts";
import { formatNumber, type NumberKind } from "../lib/format.ts";

export function Num(props: { fe: string; value: number; kind: NumberKind; lang: Lang }) {
  return (
    <span data-fe={props.fe} data-fe-value={String(props.value)}>
      {formatNumber(props.value, props.kind, props.lang)}
    </span>
  );
}

export function Txt(props: { fe: string; value: string }) {
  return (
    <code data-fe={props.fe} data-fe-value={props.value}>
      {props.value}
    </code>
  );
}

// Değeri metin olarak GÖSTERİLMEYEN alan (mühür durumu, yerelleştirilmiş sonuç adı): yalnız
// öznitelik sınanır; görünen metin sözlükten ya da kayıttan gelir.
export function Flag(props: { fe: string; value: boolean | string; children: ReactNode }) {
  return (
    <span data-fe={props.fe} data-fe-value={String(props.value)}>
      {props.children}
    </span>
  );
}
