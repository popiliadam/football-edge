// Yasal taslakların tek haritası: dil × belge. Eksik bir hücre tip hatasıdır.
import type { ComponentType } from "react";
import type { Lang, LegalDoc } from "../../site.config.ts";
import EnCookies from "./en/cookies.tsx";
import EnPrivacy from "./en/privacy.tsx";
import EnResponsible from "./en/responsible-gambling.tsx";
import EnTerms from "./en/terms.tsx";
import TrCookies from "./tr/cookies.tsx";
import TrPrivacy from "./tr/privacy.tsx";
import TrResponsible from "./tr/responsible-gambling.tsx";
import TrTerms from "./tr/terms.tsx";

export const LEGAL_CONTENT: Record<Lang, Record<LegalDoc, ComponentType>> = {
  en: {
    terms: EnTerms,
    privacy: EnPrivacy,
    cookies: EnCookies,
    "responsible-gambling": EnResponsible,
  },
  tr: {
    terms: TrTerms,
    privacy: TrPrivacy,
    cookies: TrCookies,
    "responsible-gambling": TrResponsible,
  },
};
