// Yasal metin TASLAKLARI (spec §10.1): düz TSX, markdown yok. Taslak oldukları sürece
// bayraktan bağımsız olarak `noindex` ve site haritası dışıdır (AK13, AK14).

import { notFound } from "next/navigation";
import { LEGAL_CONTENT } from "../../../../../content/legal/index.ts";
import { LEGAL_DOCS, type LegalDoc, SITE_LANGS } from "../../../../../site.config.ts";
import { Breadcrumbs } from "../../../../components/Breadcrumbs.tsx";
import { JsonLdScript } from "../../../../components/JsonLdScript.tsx";
import { t } from "../../../../i18n/dict.ts";
import { breadcrumbLd, pageLd } from "../../../../lib/jsonld.ts";
import { pageMetadata } from "../../../../lib/meta.ts";
import { langOf } from "../../../../lib/params.ts";
import { homePath, legalPath } from "../../../../lib/routes.ts";

type Params = { params: Promise<{ lang: string; doc: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.flatMap((lang) => LEGAL_DOCS.map((doc) => ({ lang, doc })));
}

function docOf(value: string): LegalDoc {
  return LEGAL_DOCS.find((doc) => doc === value) ?? notFound();
}

export async function generateMetadata({ params }: Params) {
  const { lang: rawLang, doc: rawDoc } = await params;
  const lang = langOf(rawLang);
  const doc = docOf(rawDoc);
  return pageMetadata(lang, (each) => legalPath(each, doc), t(lang, `legal.${doc}`), false);
}

export default async function LegalPage({ params }: Params) {
  const { lang: rawLang, doc: rawDoc } = await params;
  const lang = langOf(rawLang);
  const doc = docOf(rawDoc);
  const Content = LEGAL_CONTENT[lang][doc];
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: t(lang, `legal.${doc}`), path: legalPath(lang, doc) },
  ];
  return (
    <main data-fe-page={`legal:${doc}`}>
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{t(lang, `legal.${doc}`)}</h1>
      <Content />
      <JsonLdScript data={pageLd([breadcrumbLd(crumbs)])} />
    </main>
  );
}
