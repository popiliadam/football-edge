// Görünen içerik denetimleri — T5–T8 incelemelerinin kalıcı hâli (task-9-carryins.md 1–10):
// yalnız iç bağlantı, görünen metinde yasak sözcük, data-fe dışında sayı yok, durum etiketleri,
// sicil dürüstlük metinleri ve hücreleri, TASLAK görünürlüğü, olumsuzlama işareti, 18+ işaretlemesi.
import { type LegalDoc, SITE_NAME, SITE_URL } from "../../site.config.ts";
import { DICTIONARIES, type DictKey, t } from "../../src/i18n/dict.ts";
import type { Snapshot } from "../../src/lib/snapshot-types.ts";
import { isJsonLd, scripts, stripScripts, tags, visibleText } from "../lib/html.ts";
import { ALLOW_MARKER, countMarkers } from "./checks.ts";
import type { ExpectedPage } from "./expect.ts";
import { inFe, isDeferred, isHidden, joined, squash, textNodes, within } from "./text.ts";
import {
  ALLOWED_SENTENCE_KEYS,
  ALLOWED_TERMS,
  BOOKMAKERS,
  fold,
  SUGGESTION_WORDS,
  wordPattern,
} from "./words.ts";

// (T5 1) URL taşıyan öznitelikler: göreli iç yol ya da yer tutucu alan adı. schema.org yalnız
// JSON-LD'de: `@context` ve `eventStatus` numaralandırma değeri olarak.
const URL_ATTRS = ["href", "src", "action", "formaction", "poster", "srcset", "data"];
const SCHEMA = "https://schema.org";
const SCHEMA_ENUM_KEYS = ["eventStatus"];
const ANY_TAG = "[a-z][a-z0-9-]*";

function internal(url: string): boolean {
  if (url.startsWith("#")) return true;
  if (url.startsWith("/")) return !url.startsWith("//");
  return url === SITE_URL || url.startsWith(`${SITE_URL}/`);
}

function ldUrlFindings(where: string, value: unknown, key: string): string[] {
  if (typeof value === "string") {
    if (!/^[a-z][a-z0-9+.-]*:/i.test(value)) return [];
    if (key === "@context" && value === SCHEMA) return [];
    if (SCHEMA_ENUM_KEYS.includes(key) && /^https:\/\/schema\.org\/[A-Z][A-Za-z]+$/.test(value)) {
      return [];
    }
    return internal(value) ? [] : [`${where}: JSON-LD dış URL ${key}=${value}`];
  }
  if (value === null || typeof value !== "object") return [];
  return Object.entries(value).flatMap(([name, inner]) =>
    ldUrlFindings(where, inner, Array.isArray(value) ? key : name),
  );
}

export function linkFindings(where: string, html: string): string[] {
  const findings: string[] = [];
  for (const attrs of tags(html, ANY_TAG)) {
    for (const name of URL_ATTRS) {
      const value = attrs[name];
      if (value === undefined) continue;
      const urls =
        name === "srcset"
          ? value.split(",").map((part) => part.trim().split(/\s+/)[0] ?? "")
          : [value];
      for (const url of urls.filter((each) => !internal(each))) {
        findings.push(`${where}: dış bağlantı ${name}="${url}"`);
      }
    }
  }
  for (const block of scripts(html).filter(isJsonLd)) {
    try {
      findings.push(...ldUrlFindings(where, JSON.parse(block.body), ""));
    } catch {
      // Ayrışmayan JSON-LD'yi checkJsonLd raporlar.
    }
  }
  // Ham metin (Next'in veri betikleri dahil): izinli iki host dışında mutlak URL yok.
  const allowedHosts = [new URL(SITE_URL).host, new URL(SCHEMA).host];
  for (const match of html.matchAll(/(?:https?:)?\/\/([A-Za-z0-9.-]+\.[A-Za-z]{2,})/g)) {
    if (!allowedHosts.includes(match[1] ?? "")) findings.push(`${where}: izinsiz host ${match[1]}`);
  }
  return [...new Set(findings)];
}

// (T5 2) Görünen metinde bahis şirketi adı ve öneri sözcüğü yok. Sözlükteki izinli cümleler
// (sorumluluk reddi, "value önerisi yayımlamıyoruz") önce çıkarılır. `alt`/`title`/`aria-label`
// da görünen metindir.
export function wordFindings(where: string, html: string): string[] {
  const allowed = ALLOWED_SENTENCE_KEYS.flatMap((key) =>
    Object.values(DICTIONARIES).map((dict) => squash(dict[key])),
  );
  const labels = tags(html, ANY_TAG)
    .flatMap((attrs) => [attrs.alt, attrs.title, attrs["aria-label"]])
    .filter((value): value is string => value !== undefined);
  const texts = [...textNodes(html).map((node) => node.text), ...labels].map((text) => {
    const rest = fold(
      allowed.reduce((part, sentence) => part.split(sentence).join(" "), squash(text)),
    );
    return ALLOWED_TERMS.reduce((part, term) => part.split(term).join(" "), rest);
  });
  const findings: string[] = [];
  for (const [list, stem, label] of [
    [BOOKMAKERS, false, "bahis şirketi adı"],
    [SUGGESTION_WORDS, true, "öneri sözcüğü"],
  ] as const) {
    for (const word of list) {
      const pattern = wordPattern(word, stem);
      if (texts.some((text) => pattern.test(text))) findings.push(`${where}: ${label} "${word}"`);
    }
  }
  return findings;
}

// (T5 3) Görünen metinde `data-fe`/`<time>` dışındaki rakamlar yalnız izin listesinden: yüzdelik
// etiketleri (10, 90), 18+, 404. Anlık görüntüden birebir gelen adlar (takım, lig, ülke) ve marka
// önce çıkarılır — "Schalke 04" bir veri metnidir, hesap değil. Yasal taslağın kendi yasal atfı
// belge başına adıyla izinli (KVKK md. 6).
export const FREE_NUMBERS: readonly string[] = ["10", "90", "18", "404"];
export const LEGAL_NUMBERS: Partial<Record<LegalDoc, readonly string[]>> = { privacy: ["6"] };

function snapshotNames(snapshot: Snapshot): string[] {
  const names = [
    SITE_NAME,
    ...snapshot.leagues.flatMap((league) => [league.name, league.country]),
    ...snapshot.teams.map((team) => team.name),
    ...snapshot.matches.flatMap((match) => [match.home, match.away]),
  ];
  return [...new Set(names)].sort((a, b) => b.length - a.length);
}

export function numberFindings(snapshot: Snapshot, page: ExpectedPage, html: string): string[] {
  const doc = page.kind === "legal" ? (page.id.split(":")[1] as LegalDoc) : undefined;
  const allowed = [...FREE_NUMBERS, ...((doc && LEGAL_NUMBERS[doc]) ?? [])];
  const names = snapshotNames(snapshot);
  const findings: string[] = [];
  for (const node of textNodes(html)) {
    if (inFe(node) || within(node, "time")) continue;
    const text = names.reduce((rest, name) => rest.split(name).join(" "), node.text);
    for (const [number] of text.matchAll(/\d+(?:[.,]\d+)*/g)) {
      if (!allowed.includes(number)) {
        findings.push(
          `${page.path}: data-fe dışında sayı "${number}" ("${squash(node.text).slice(0, 60)}")`,
        );
      }
    }
  }
  return findings;
}

const ROUNDS = ["opening", "latest", "closing"] as const;

function contains(nodes: string, key: DictKey, lang: ExpectedPage["lang"]): boolean {
  return nodes.includes(squash(t(lang, key)));
}

// (T5 4) Durum etiketleri: eşik altı turun NEDENİ (kapanış bekleniyor / yetersiz kitap), hareket ve
// dağılım yoksa boş durum cümlesi. Mühür etiketi checkFields'te (data-fe `attr` etiketi).
export function stateFindings(snapshot: Snapshot, page: ExpectedPage, html: string): string[] {
  const findings: string[] = [];
  const text = joined(textNodes(html).filter((node) => within(node, "main")));
  const presence = (key: DictKey, want: boolean) => {
    if (contains(text, key, page.lang) !== want) {
      findings.push(`${page.path}: "${t(page.lang, key)}" ${want ? "yok" : "fazla"}`);
    }
  };
  if (page.kind === "match") {
    const match = snapshot.matches.find((each) => `match:${each.id}` === page.id);
    if (match === undefined) return [`${page.path}: maç kaydı yok`];
    const rows = [
      ...html.matchAll(/<th\b[^>]*>([^<]*)<\/th>\s*<td\b[^>]*\bcolspan="4"[^>]*>([^<]*)<\/td>/gi),
    ];
    const shown = rows.map(
      (row) => `${squash(visibleText(row[1] ?? ""))}=${squash(visibleText(row[2] ?? ""))}`,
    );
    const want = ROUNDS.filter((round) => match.h2h[round] === null).map((round) => {
      const reason =
        round === "closing" && !match.sealed ? "match.awaitingClose" : "match.insufficient";
      return `${t(page.lang, `match.${round}`)}=${t(page.lang, reason)}`;
    });
    if (shown.sort().join("|") !== want.sort().join("|")) {
      findings.push(
        `${page.path}: eksik tur nedenleri [${shown.join("; ")}] ≠ [${want.join("; ")}]`,
      );
    }
    presence("match.noMove", match.move === null);
  }
  if (page.kind === "league") {
    const league = snapshot.leagues.find((each) => `league:${each.id}` === page.id);
    presence("league.moveTooFew", league?.move_distribution === null);
  }
  return findings;
}

// (T6 5) Sicil dürüstlük metinleri SÖZLÜKTEN: taahhüt cümlesi + üç doğrulama sınırı her durumda;
// boş sicilde açıklama var ve tablo YOK; dolu sicilde tablo var ve açıklama yok; çıpa durumu doğru.
export function honestyFindings(snapshot: Snapshot, page: ExpectedPage, html: string): string[] {
  if (page.kind !== "track-record") return [];
  const findings: string[] = [];
  const text = joined(textNodes(html).filter((node) => within(node, "main") && !isHidden(node)));
  const presence = (key: DictKey, want: boolean) => {
    if (contains(text, key, page.lang) !== want) {
      findings.push(`${page.path}: dürüstlük metni ${key} ${want ? "yok" : "fazla"}`);
    }
  };
  for (const key of [
    "record.commitment",
    "record.limit1",
    "record.limit2",
    "record.limit3",
  ] as const) {
    presence(key, true);
  }
  const empty = snapshot.record.published === 0;
  presence("record.emptyExplain", empty);
  const main = html.slice(html.indexOf("<main"), html.indexOf("</main>"));
  if (/<table\b/.test(main) === empty) {
    findings.push(`${page.path}: sicil tablosu ${empty ? "fazla" : "yok"}`);
  }
  const anchored = snapshot.ledger.anchor.last_id === snapshot.ledger.last_id;
  presence("record.anchorMatches", anchored);
  presence("record.anchorBehindBefore", !anchored);
  return findings;
}

// (T6 6) Dolu sicilde her girdinin satırı: yayın anı (`<time>` = published_at, sunucu metni UTC),
// maç adı. Sonuç etiketi ve CLV hücresi data-fe'dir (checkFields).
export const utcText = (iso: string): string => `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;

export function recordCellFindings(snapshot: Snapshot, page: ExpectedPage, html: string): string[] {
  if (page.kind !== "track-record") return [];
  const findings: string[] = [];
  const rows = [...html.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/g)].map((row) => row[1] ?? "");
  for (const entry of snapshot.record.entries) {
    const marker = `data-fe="entry:${entry.publication_id}:market"`;
    const mine = rows.filter((row) => row.includes(marker));
    if (mine.length !== 1) {
      findings.push(`${page.path}: girdi ${entry.publication_id} için ${mine.length} satır`);
      continue;
    }
    const cells = [...(mine[0] ?? "").matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/g)].map(
      (cell) => cell[1] ?? "",
    );
    const time = tags(cells[0] ?? "", "time")[0];
    const shownTime = squash(visibleText(cells[0] ?? ""));
    if (time?.datetime !== entry.published_at || shownTime !== utcText(entry.published_at)) {
      findings.push(
        `${page.path}: girdi ${entry.publication_id} yayın anı "${shownTime}" ≠ ${entry.published_at}`,
      );
    }
    const match = snapshot.matches.find((each) => each.id === entry.match_id);
    const name = squash(visibleText(cells[1] ?? ""));
    if (match === undefined || name !== `${match.home} – ${match.away}`) {
      findings.push(`${page.path}: girdi ${entry.publication_id} maç adı "${name}"`);
    }
  }
  return findings;
}

// (T7 8) TASLAK işareti yasal sayfada GÖRÜNÜR: gizli/şablon/pencere içinde değil, <main>'de; metin
// sözlükten. Ucuz CSS denetimi: işaretin (ve atalarının) sınıfı derlenmiş CSS'te gizlenmiyor.
const CSS_HIDES = /display\s*:\s*none|visibility\s*:\s*hidden/i;

export function cssHidingFindings(
  where: string,
  css: string,
  classes: readonly string[],
): string[] {
  const findings: string[] = [];
  for (const [, selector = "", body = ""] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!CSS_HIDES.test(body)) continue;
    for (const name of classes) {
      if (new RegExp(`\\.${name.replace(/[^\w-]/g, "\\$&")}(?![\\w-])`).test(selector)) {
        findings.push(`${where}: TASLAK işaretinin sınıfı ${name} CSS'te gizleniyor`);
      }
    }
  }
  return findings;
}

export function draftFindings(
  page: ExpectedPage,
  html: string,
  css: (href: string) => string,
): string[] {
  if (page.kind !== "legal") return [];
  const draft = squash(t(page.lang, "legal.draft"));
  const visible = textNodes(html).filter(
    (node) =>
      squash(node.text) === draft && within(node, "main") && !isHidden(node) && !isDeferred(node),
  );
  if (visible.length !== 1) {
    return [`${page.path}: görünür TASLAK işareti ${visible.length} (1 bekleniyor)`];
  }
  const classes = (visible[0]?.ancestors ?? []).flatMap((each) =>
    (each.attrs.class ?? "").split(/\s+/).filter(Boolean),
  );
  const sheets = tags(html, "link").filter((link) => link.rel === "stylesheet" && link.href);
  return sheets.flatMap((sheet) => cssHidingFindings(page.path, css(sheet.href ?? ""), classes));
}

// (T7 9) Olumsuzlama işareti yalnız koşullar belgesinde, tam bir kez.
export function markerFindings(page: ExpectedPage, html: string): string[] {
  const want = page.id === "legal:terms" ? 1 : 0;
  const count = countMarkers(stripScripts(html));
  return count === want ? [] : [`${page.path}: ${ALLOW_MARKER} ${count} kez (${want} bekleniyor)`];
}

// (T7 10) 18+ bildiriminin DURAĞAN işaretlemesi: kapalı tek <dialog> (başlık sözlükten) ve betiksiz
// şerit. Açılma/onay/odak davranışı DOM ortamı olmadan ölçülmez (sınır).
export function ageGateFindings(page: ExpectedPage, html: string): string[] {
  const findings: string[] = [];
  const dialogs = tags(html, "dialog");
  if (dialogs.length !== 1 || dialogs[0]?.open !== undefined) {
    findings.push(
      `${page.path}: 18+ penceresi ${dialogs.length} adet ya da sunucu çıktısında açık`,
    );
  }
  const nodes = textNodes(html);
  const has = (tag: string, key: DictKey) =>
    nodes.some((node) => within(node, tag) && squash(node.text) === squash(t(page.lang, key)));
  if (!has("dialog", "age.title")) findings.push(`${page.path}: 18+ penceresinde başlık yok`);
  if (!has("noscript", "age.strip")) findings.push(`${page.path}: betiksiz 18+ şeridi yok`);
  return findings;
}
