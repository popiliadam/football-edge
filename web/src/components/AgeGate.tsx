"use client";
// 18+ bildirimi (spec §10.2). Sunucu çıktısında `<dialog>` KAPALIdır (open yok): içerik
// HTML'de durur ve betiksiz tarayıcı `<noscript>` şeridini görür. Betik açıksa ve onay
// yoksa kapı `showModal()` ile kipli açılır (odak içeride, arka plan etkisiz). Bir
// bildirimdir; yaş doğrulaması DEĞİLDİR (§12.4/6).
import { useEffect, useRef } from "react";
import { type ConsentStore, confirmGate, openGateIfNeeded } from "../lib/consent.ts";
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
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    openGateIfNeeded(dialog.current, browserStore());
  }, []);
  return (
    <>
      <noscript>
        <p className={styles.ageStrip}>{labels.strip}</p>
      </noscript>
      <dialog
        ref={dialog}
        aria-labelledby="age-gate-title"
        className={styles.ageGate}
        // Esc ile kapanma yok: karar iki düğmeden biriyle verilir. Tarayıcı yine de kapatırsa
        // onay yazılmamıştır ve kapı bir sonraki sayfada yeniden açılır.
        onCancel={(event) => event.preventDefault()}
      >
        <p id="age-gate-title" className={styles.ageTitle}>
          {labels.title}
        </p>
        <p>{labels.body}</p>
        <button type="button" onClick={() => confirmGate(dialog.current, browserStore())}>
          {labels.confirm}
        </button>
        <button type="button" onClick={() => window.location.replace("about:blank")}>
          {labels.leave}
        </button>
      </dialog>
    </>
  );
}
