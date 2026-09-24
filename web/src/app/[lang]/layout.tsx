// Kök yerleşim dil bölütündedir: `<html lang>` sayfanın diliyle aynıdır (spec §5.3/8).
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { isLang, SITE_LANGS } from "../../../site.config.ts";

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export default async function LangLayout(props: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await props.params;
  if (!isLang(lang)) notFound();
  return (
    <html lang={lang}>
      <body>{props.children}</body>
    </html>
  );
}
