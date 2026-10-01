// DEFERRED 21j: `checkFrameworkLang`in birim testi `checkout/checks.test.ts`tedir; bu test onun
// check-out'a BAĞLI olduğunu sınar (çağrı silinirse ya da Next'in bir 404 dosyası listeden düşerse
// kırmızı). `check-out.ts` içe aktarılınca koştuğu için ayrı süreçte çalıştırılır. Fixture yalnız
// Next'in üç 404 dosyasıdır ve üçü de `<html lang>`sızdır; öteki bulgular (eksik sayfalar) beklenir
// ve burada sayılmaz.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const WEB_DIR = fileURLToPath(new URL("..", import.meta.url));

describe("check-out: Next'in 404 sayfalarının dili", () => {
  it("lang'sız 404 dosyalarının üçü de bulgu, çıkış kodu 1", () => {
    const run = spawnSync(
      process.execPath,
      [
        "scripts/check-out.ts",
        "--snapshot",
        "fixtures/snapshot.fixture.web-empty.json",
        "--out",
        "fixtures/checkout-404-nolang",
      ],
      { cwd: WEB_DIR, encoding: "utf8" },
    );
    const lang = run.stdout.split("\n").filter((line) => line.includes("<html lang="));
    expect(lang).toEqual([
      'BULGU: /404.html: <html lang=""> ≠ en',
      'BULGU: /404/index.html: <html lang=""> ≠ en',
      'BULGU: /_not-found/index.html: <html lang=""> ≠ en',
    ]);
    expect(run.status).toBe(1);
  });
});
