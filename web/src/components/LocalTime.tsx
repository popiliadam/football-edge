"use client";
// Başlama anı (spec §7): sunucu çıktısı UTC'dir ve betiksiz tarayıcı onu görür; betik
// açıksa aynı an ziyaretçinin yerel saatine çevrilir ve dilimin adı yazılır (DEFERRED 20e).
// `datetime` değişmez.
import { useEffect, useState } from "react";

export function utcLabel(iso: string): string {
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}

export function localLabel(iso: string, lang: string, timeZone: string): string {
  const text = new Date(iso).toLocaleString(lang, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  });
  return `${text} (${timeZone})`;
}

export function LocalTime({ iso, lang }: { iso: string; lang: string }) {
  const [label, setLabel] = useState(utcLabel(iso));
  useEffect(() => {
    setLabel(localLabel(iso, lang, Intl.DateTimeFormat().resolvedOptions().timeZone));
  }, [iso, lang]);
  return <time dateTime={iso}>{label}</time>;
}
