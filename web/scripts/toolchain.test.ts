import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Spec §13 "pnpm 10 (`packageManager` alanı)"; §12.1 "pnpm yoksa FAIL (SKIP değil)".
// B-2 T0 ölçümü: kabuk profili Node 22'nin bin dizinini `nvm use`dan bağımsız PATH'e koyar ve orada
// pnpm 11 durur. Node 24 önekinde pnpm yoksa kapı sessizce pnpm 11'e düşerdi; `packageManager`
// alanı tek başına bunu görünür kılmaz. Bu test PATH'teki `pnpm`in ana sürümünü adıyla sınar.
const WEB_DIR = fileURLToPath(new URL("..", import.meta.url));

describe("araç zinciri (spec §13, §12.1)", () => {
  it("PATH'teki pnpm ana sürüm 10", () => {
    const version = execFileSync("pnpm", ["-v"], { cwd: WEB_DIR, encoding: "utf8" }).trim();
    expect(version, `pnpm -v "${version}" — 10. ile başlamıyor (Node 24 önekinin pnpm'i?)`).toMatch(
      /^10\./,
    );
  });
});
