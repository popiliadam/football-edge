// `next build`in ardından koşar (`pnpm run build`). Girdi: SITE_SNAPSHOT, SITE_INDEXABLE.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { indexingEnabled } from "../site.config.ts";
import { parseSnapshot } from "../src/lib/snapshot.ts";
import { headersFile, inlineHashes, redirectsFile, sha256Hex, slugIndex } from "./lib/emit.ts";
import { pageFiles, readText } from "./lib/outdir.ts";

const OUT = resolve("out");

function main(): number {
  const source = process.env.SITE_SNAPSHOT;
  if (!source) {
    process.stderr.write("emit-headers: SITE_SNAPSHOT tanımlı değil\n");
    return 1;
  }
  const bytes = readFileSync(resolve(source));
  const snapshot = parseSnapshot(bytes.toString("utf-8"));
  const pages = pageFiles(OUT).map((page) => ({
    path: page.path,
    hashes: inlineHashes(readText(page.file)),
  }));
  const digest = sha256Hex(bytes);
  // Dışa aktarıcının kendi `snapshot.sha256`sı varsa (gerçek yayın) aynı dosyayı anlatmalı.
  const sibling = join(dirname(resolve(source)), "snapshot.sha256");
  if (existsSync(sibling) && readFileSync(sibling, "utf-8").split(/\s+/)[0] !== digest) {
    process.stderr.write("emit-headers: snapshot.sha256 dosyanın baytlarıyla eşleşmiyor\n");
    return 1;
  }
  mkdirSync(join(OUT, "data"), { recursive: true });
  writeFileSync(join(OUT, "_headers"), headersFile(pages, indexingEnabled()));
  writeFileSync(join(OUT, "_redirects"), redirectsFile(snapshot));
  writeFileSync(join(OUT, "data/slugs.json"), `${JSON.stringify(slugIndex(snapshot), null, 2)}\n`);
  writeFileSync(join(OUT, "data/snapshot.sha256"), `${digest}\n`);
  process.stdout.write(`emit-headers: ${pages.length} sayfa, CSP + _redirects + data/\n`);
  return 0;
}

process.exitCode = main();
