import { SITE_LANGS, SITE_NAME } from "../../../site.config.ts";

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export default function HomePage() {
  return (
    <main data-fe-page="home">
      <h1>{SITE_NAME}</h1>
    </main>
  );
}
