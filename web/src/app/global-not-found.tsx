// Eşleşmeyen her yolun 404'ü (DEFERRED 20f, 21c). Kök yerleşim `[lang]` bölütünde olduğu için Next'in
// yerleşik 404'ü `<html lang>`sız yazılıyordu; bu dosya yerleşik olanın (Next 16.3.6
// `client/components/builtin/global-not-found.js` + `http-access-fallback/error-fallback.js` +
// `styles/access-error-styles.js`) satır içi AYNISIDIR, yalnız `<html lang>` varsayılan dili taşır.
// Next'in iç modül yolu içe aktarılmaz (21c); derlenmiş 404 baytları iç importlu sürümle aynıdır
// (ölçüldü 2026-10-01). Görünen metin Next'indir, sözlüğe girmez (AK2 metin onayı dışı). Tek dosya
// her dile sunulur; `check-out` dili `checkFrameworkLang` ile denetler.
import type { CSSProperties } from "react";
import { DEFAULT_LANG } from "../../site.config.ts";

const STATUS = 404;
const MESSAGE = "This page could not be found.";

// Next'in küçültülmüş CSS'i (açık/koyu tema), değiştirilmeden.
const CSS =
  "body{color:#000;background:#fff;margin:0}.next-error-h1{border-right:1px solid rgba(0,0,0,.3)}@media (prefers-color-scheme:dark){body{color:#fff;background:#000}.next-error-h1{border-right:1px solid rgba(255,255,255,.3)}}";

const STYLES = {
  error: {
    fontFamily:
      'system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji"',
    height: "100vh",
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
  },
  desc: { display: "inline-block" },
  h1: {
    display: "inline-block",
    margin: "0 20px 0 0",
    padding: "0 23px 0 0",
    fontSize: 24,
    fontWeight: 500,
    verticalAlign: "top",
    lineHeight: "49px",
  },
  h2: { fontSize: 14, fontWeight: 400, lineHeight: "49px", margin: 0 },
} satisfies Record<string, CSSProperties>;

export default function GlobalNotFound() {
  return (
    <html lang={DEFAULT_LANG}>
      <body>
        <title>{`${STATUS}: ${MESSAGE}`}</title>
        <div style={STYLES.error}>
          <div>
            {/* biome-ignore lint/security/noDangerouslySetInnerHtml: Next'in sabit CSS'i; dış girdi yok. */}
            <style dangerouslySetInnerHTML={{ __html: CSS }} />
            <h1 className="next-error-h1" style={STYLES.h1}>
              {STATUS}
            </h1>
            <div style={STYLES.desc}>
              <h2 style={STYLES.h2}>{MESSAGE}</h2>
            </div>
          </div>
        </div>
      </body>
    </html>
  );
}
