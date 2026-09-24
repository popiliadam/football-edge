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
