"use client";
// Başlama anı (spec §7): sunucu çıktısı UTC'dir ve betiksiz tarayıcı onu görür; betik
// açıksa aynı an ziyaretçinin yerel saatine çevrilir. `datetime` değişmez.
import { useEffect, useState } from "react";

export function utcLabel(iso: string): string {
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}

export function LocalTime({ iso, lang }: { iso: string; lang: string }) {
  const [label, setLabel] = useState(utcLabel(iso));
  useEffect(() => {
    setLabel(new Date(iso).toLocaleString(lang, { dateStyle: "medium", timeStyle: "short" }));
  }, [iso, lang]);
  return <time dateTime={iso}>{label}</time>;
}
