// Kök yerleşim dil bölütündedir: `<html lang>` sayfanın diliyle aynıdır (spec §5.3/8).
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SITE_LANGS, SITE_NAME } from "../../../site.config.ts";
import { AgeGate } from "../../components/AgeGate.tsx";
import { SiteFooter, SiteHeader } from "../../components/SiteChrome.tsx";
import { t } from "../../i18n/dict.ts";
import { langOf } from "../../lib/params.ts";
import styles from "../../styles/site.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export const metadata: Metadata = { title: { template: `%s · ${SITE_NAME}`, default: SITE_NAME } };

export default async function LangLayout(props: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const lang = langOf((await props.params).lang);
  const labels = {
    title: t(lang, "age.title"),
    body: t(lang, "age.body"),
    confirm: t(lang, "age.confirm"),
    leave: t(lang, "age.leave"),
    strip: t(lang, "age.strip"),
  };
  return (
    <html lang={lang}>
      <body className={styles.body}>
        <AgeGate labels={labels} />
        <SiteHeader lang={lang} />
        {props.children}
        <SiteFooter lang={lang} />
      </body>
    </html>
  );
}
