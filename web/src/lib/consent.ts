// 18+ onayının yerel depolaması (spec §10.2). BU BİR YAŞ DOĞRULAMASI DEĞİLDİR (§12.4/6).
// Depolama erişimi atabilir (gizli pencere, kapalı site verisi): atarsa onay yok sayılır
// ve kapı yeniden gösterilir — yanlış yöne değil, güvenli yöne düşer.
export const CONSENT_KEY = "fe-age-18";

export type ConsentStore = Pick<Storage, "getItem" | "setItem">;

export function hasConsent(store: ConsentStore | null): boolean {
  try {
    return store?.getItem(CONSENT_KEY) === "1";
  } catch {
    return false;
  }
}

export function giveConsent(store: ConsentStore | null): boolean {
  try {
    store?.setItem(CONSENT_KEY, "1");
    return store !== null;
  } catch {
    return false;
  }
}

// Kapının açılma/kapanma kararı bileşenden ayrıdır: DOM test ortamı olmadan sınanabilsin diye
// `<dialog>`ın yalnız kullanılan yüzü alınır. Kapı `showModal()` ile KİPLİ açılır: odak pencereye
// gelir, arka plan etkisizleşir (Tab örtünün altındaki bağlantılara kaçmaz).
export type GateDialog = Pick<HTMLDialogElement, "open" | "showModal" | "close">;

export function openGateIfNeeded(dialog: GateDialog | null, store: ConsentStore | null): boolean {
  if (dialog === null || dialog.open || hasConsent(store)) return false;
  dialog.showModal();
  return true;
}

// Onay yazılamasa da kapı kapanır; kayıt yoksa bir sonraki sayfada yeniden açılır.
export function confirmGate(dialog: GateDialog | null, store: ConsentStore | null): boolean {
  const stored = giveConsent(store);
  dialog?.close();
  return stored;
}
