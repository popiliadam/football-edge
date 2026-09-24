// `out/` dizinindeki sayfalar: her `index.html` bir URL yoludur (trailingSlash: true).
// Next'in kendi 404 sayfaları sitenin sayfası değildir ve sayılmaz.
import { readdirSync, readFileSync } from "node:fs";
import { join, relative, sep } from "node:path";

export type PageFile = { path: string; file: string };

export const FRAMEWORK_PAGES: readonly string[] = ["/404/", "/_not-found/"];

export function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = join(dir, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });
}

export function pageFiles(outDir: string): PageFile[] {
  return walk(outDir)
    .filter((file) => file.endsWith(`${sep}index.html`))
    .map((file) => {
      const dir = relative(outDir, file).split(sep).slice(0, -1).join("/");
      return { path: dir === "" ? "/" : `/${dir}/`, file };
    })
    .filter((page) => !FRAMEWORK_PAGES.includes(page.path))
    .sort((a, b) => a.path.localeCompare(b.path));
}

export function readText(file: string): string {
  return readFileSync(file, "utf-8");
}
