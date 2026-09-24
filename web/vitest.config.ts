import { defineConfig } from "vitest/config";

// Birim testleri Node ortamında koşar; tarayıcı/DOM kütüphanesi yok (bağımlılık listesi §13).
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}", "scripts/**/*.test.ts", "content/**/*.test.ts"],
  },
});
