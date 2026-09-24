import type { NextConfig } from "next";

// Spec §13: statik dışa aktarım; sunucu, görüntü optimizasyonu, çalışma zamanı yok.
const config: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  reactStrictMode: true,
};

export default config;
