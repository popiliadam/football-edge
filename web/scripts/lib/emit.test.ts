import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { fullFixture } from "../../src/lib/fixture.ts";
import { csp, headersFile, inlineHashes, redirectsFile, slugIndex } from "./emit.ts";

describe("_headers (spec §11, AK19 a, H7)", () => {
  it("bayrak kapalıyken /* X-Robots-Tag taşır; CSP yalnız sayfa bloklarında", () => {
    const text = headersFile([{ path: "/en/", hashes: ["'sha256-AAA='"] }], false);
    const [global, page] = text.split("\n\n");
    expect(global).toContain("X-Robots-Tag: noindex");
    expect(global).not.toContain("Content-Security-Policy");
    expect(page).toBe(`/en/\n  Content-Security-Policy: ${csp(["'sha256-AAA='"])}\n`);
  });

  it("bayrak açıkken X-Robots-Tag yok", () => {
    expect(headersFile([], true)).not.toContain("X-Robots-Tag");
  });

  it("JSON-LD ve src'li betik hash listesine girmez", () => {
    const html =
      '<script type="application/ld+json">{}</script><script src="/a.js"></script><script>a()</script><script>a()</script>';
    expect(inlineHashes(html)).toHaveLength(1);
  });

  // Next'in veri betiği JSON-LD'nin metnini (ve tip adını) bir kez daha taşır: hash her GERÇEK
  // satır içi betiğin gövdesinden, bayt bayt ve bir kez alınır; JSON-LD öğesinin kendisi girmez.
  it("her yürütülebilir satır içi betiğin gövdesi birebir hash'lenir", () => {
    const ld = '{"@context":"https://schema.org","name":"Doğu &amp; Batı"}';
    const boot = "(self.__next_f=self.__next_f||[]).push([0])";
    const data = `self.__next_f.push([1,"[\\"$\\",\\"script\\",null,{\\"type\\":\\"application/ld+json\\"}]"])`;
    const html = `<p>x</p><script type="application/ld+json">${ld}</script><script>${boot}</script><script>${data}</script>`;
    const sha = (body: string) =>
      `'sha256-${createHash("sha256").update(body, "utf8").digest("base64")}'`;
    expect(inlineHashes(html)).toEqual([sha(boot), sha(data)].sort());
  });

  it("CSP unsafe-inline taşımaz", () => {
    expect(csp(["'sha256-AAA='"])).not.toContain("unsafe-inline");
  });
});

describe("_redirects ve slug deposu (spec §8.1, AK20 b)", () => {
  const snapshot = fullFixture();

  it("kök → varsayılan dil; her dil × maç için zorlamasız 301", () => {
    const lines = redirectsFile(snapshot).trimEnd().split("\n");
    expect(lines[0]).toBe("/ /en/ 301");
    expect(lines).toHaveLength(1 + 2 * snapshot.matches.length);
    expect(lines.every((line) => line.endsWith(" 301"))).toBe(true);
    const stem = `/tr/synthetic-league-alpha/match/${snapshot.matches[0]?.path_id}/`;
    expect(lines).toContain(`${stem}* ${stem}kuzeyspor-vs-guneykoy-idmanyurdu/ 301`);
  });

  it("slug deposu sıralı ve lig önekli", () => {
    const index = slugIndex(snapshot);
    expect(index.leagues).toEqual(["synthetic-league-alpha", "synthetic-league-beta"]);
    expect(index.teams[0]).toBe("synthetic-league-alpha/dogu-bati-fk");
    expect(index.teams).toEqual([...index.teams].sort());
    // Fixture zaten sıralı gelir; ters sırada verilen girdi aynı depoyu üretmeli.
    const reversed = {
      ...snapshot,
      leagues: [...snapshot.leagues].reverse(),
      teams: [...snapshot.teams].reverse(),
    };
    expect(slugIndex(reversed)).toEqual(index);
  });
});
