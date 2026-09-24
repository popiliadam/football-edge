"use client";
// 18+ bildirimi (spec §10.2). Sunucu çıktısında `<dialog>` KAPALIdır (open yok): içerik
// HTML'de durur ve betiksiz tarayıcı `<noscript>` şeridini görür. Betik açıksa ve onay
// yoksa kapı açılır. Kipsiz bir bildirimdir; yaş doğrulaması DEĞİLDİR (§12.4/6).
import { useEffect, useState } from "react";
import { type ConsentStore, giveConsent, hasConsent } from "../lib/consent.ts";
import styles from "../styles/site.module.css";

export type AgeGateLabels = {
  title: string;
  body: string;
  confirm: string;
  leave: string;
  strip: string;
};

function browserStore(): ConsentStore | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function AgeGate({ labels }: { labels: AgeGateLabels }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setOpen(!hasConsent(browserStore()));
  }, []);
  return (
    <>
      <noscript>
        <p className={styles.ageStrip}>{labels.strip}</p>
      </noscript>
      <dialog open={open} aria-labelledby="age-gate-title" className={styles.ageGate}>
        <p id="age-gate-title" className={styles.ageTitle}>
          {labels.title}
        </p>
        <p>{labels.body}</p>
        <button
          type="button"
          onClick={() => {
            giveConsent(browserStore());
            setOpen(false);
          }}
        >
          {labels.confirm}
        </button>
        <button type="button" onClick={() => window.location.replace("about:blank")}>
          {labels.leave}
        </button>
      </dialog>
    </>
  );
}
