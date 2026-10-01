// Eşleşmeyen her yolun 404'ü (DEFERRED 20f). Kök yerleşim `[lang]` bölütünde olduğu için Next'in
// yerleşik 404'ü `<html lang>`sız yazılıyordu; bu dosya yerleşik olanın (Next 16.3.6
// `client/components/builtin/global-not-found.js`) AYNISIDIR, yalnız `<html lang>` varsayılan dili
// taşır. Görünen metin Next'indir, sözlüğe girmez (AK2 metin onayı dışı). Tek dosya her dile sunulur.
import { HTTPAccessErrorFallback } from "next/dist/client/components/http-access-fallback/error-fallback";
import { DEFAULT_LANG } from "../../site.config.ts";

export default function GlobalNotFound() {
  return (
    <html lang={DEFAULT_LANG}>
      <body>
        <HTTPAccessErrorFallback status={404} message="This page could not be found." />
      </body>
    </html>
  );
}
