import type { NextConfig } from "next";

// Spec §13: statik dışa aktarım; sunucu, görüntü optimizasyonu, çalışma zamanı yok.
const config: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  reactStrictMode: true,
  // `app/global-not-found.tsx` (DEFERRED 20f: 404 sayfalarında `<html lang>`). Belgelenen deneysel
  // bayrak; 16.3.6 Turbopack derlemesi dosyayı bayraksız da kullanıyor (ölçüldü 2026-10-01), webpack
  // yolu (`build/entries.js`) bayrağa bakar. `check-out` 404'lerin `<html lang>`ını denetler.
  experimental: { globalNotFound: true },
};

export default config;
