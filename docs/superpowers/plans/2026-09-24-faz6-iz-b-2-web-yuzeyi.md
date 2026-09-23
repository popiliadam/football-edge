# Faz 6 İz B · Plan B-2 — Web yüzeyi Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Anlık görüntü JSON'undan (B-1'in sözleşmesi) `noindex` statik bir Next.js sitesi üretmek — maç/lig/takım/sicil/yasal
sayfaları, pSEO yolları, hreflang, schema.org, 18+ bildirimi, yasal TASLAKLAR, derlemenin ürettiği `_headers` (CSP hash'leri)
ve `_redirects`, sayfa ↔ anlık görüntü eşitliğini ölçen çıktı tarayıcısı, bağlanmamış `netlify.toml` — ve sitenin Node
adımlarını tek kapıya (`verify.sh` + `ci.yml`) bağlamak. Deploy YOK, Netlify hesabı YOK, ağa yazma YOK.

**Architecture:** Spec'in Mimari A'sı (B1): Python dışa aktarır (B-1), Node yalnız `SITE_SNAPSHOT`un gösterdiği JSON'u okur
(H5 — Node DB'ye bağlanmaz). `next build` (`output: 'export'`) → `scripts/emit-headers.ts` (CSP hash'leri, X-Robots-Tag,
`_redirects`, `data/`) → `scripts/check-out.ts` (spec §5.3'ün sekiz ölçümü). Sayfalar sayı HESAPLAMAZ; her değer
`data-fe` öznitelikli tek bir öğeyle basılır ve tarayıcı öznitelik ile görünen metni anlık görüntüye karşı sınar (H6).
B-2 B-1'den YALNIZ şunları tüketir: `web/contract/snapshot.schema.json` (B-1 T1) ve `verify-snapshot` CLI'ı (B-1 T5);
geliştirme ve test B-2'nin kendi sentetik fixture'larıyla yapılır.

**Tech Stack:** Node 24 LTS (yerleşik TS tip ayıklaması), pnpm 10, Next.js 16 App Router (statik dışa aktarım), React 19,
TypeScript 5.9 (`erasableSyntaxOnly`), Vitest 4 (Node ortamı, DOM kütüphanesi yok), Biome 2, CSS modülleri; Python tarafında
pytest (`tests/test_site_web_*.py`), PyYAML, `tomllib`. Plan yazımında kod, `~/dev/skala`nın kurulu Next 16.2.9 / React
19.2.4 / TS 5.9.3 / Vitest 4.1.9'uyla kazıma dizininde DERLENDİ ve KOŞTURULDU (`b2-plan-scratch/proto/`); Biome yerelde
kurulu olmadığı için biçim/lint yalnız T1'de ölçülür.

**Spec:** `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md` (§15 Plan B-2; dayandığı bölümler §2 H1–H7, §5.2–§5.4,
§6, §7, §8, §9, §10, §11, §12, §13, §14, §16 AK3–AK5/AK13/AK14/AK19–AK21, §18.5). Kardeş plan B-1 (okuma katmanı, dışa
aktarım, `verify-snapshot`, `site.yml`) ayrı yazılır; iki plan arasındaki TEK arayüz aşağıdaki "B-1 ile arayüz" bölümüdür.

## Global Constraints

Spec'ten birebir (her görevin gereksinimine örtük olarak dahildir):

- Sürümler: "**Node 24 LTS** (`.nvmrc` + `engines`; Node 26 LTS'e geçiş ayrı iş), **pnpm 10** (`packageManager` alanı)." (§13)
- "**Next.js** App Router, `output: 'export'`, `images.unoptimized: true`, `trailingSlash: true`; sürüm plan günündeki
  kararlı sürüm, kilit dosyasıyla sabit." (§13)
- "**Çalışma zamanı bağımlılığı yalnız** `next`, `react`, `react-dom`. Dev: `typescript`, `@types/react`, `@types/node`,
  `vitest`, `@biomejs/biome`, (isteğe bağlı) `schema-dts`. CSS modülleri; i18n, durum yönetimi, UI kütüphanesi, Supabase
  istemcisi YOK. Bağımlılık allowlist testi (H5a) bu listeyi sabitler; eklemek bilinçli commit." — Bu plan bilinçli olarak
  YALNIZ `@types/react-dom` (tip paketi; `react-dom/server` testleri) ekler ve `schema-dts`i kullanmaz (Açık sorular/5).
- "`netlify-cli` depo bağımlılığı değildir; `site.yml`de sabit sürümle çağrılır." (§13)
- "`.gitignore`: `web/node_modules/`, `web/.next/`, `web/out/`, `web/.snapshot/`." (§13) — bu plan ek olarak Next'in
  ürettiği `web/next-env.d.ts` ve `web/*.tsbuildinfo`yu ekler.
- "B-2 → `verify.sh`/`ci.yml`e B-1 birleştikten SONRA dokunur" (B13, §12.3 tek yazar).
- H3/B6: "Anlık görüntü şeması v1'de `value_badge: null`, `analysis: null`, model olasılığı alanı YOK." Sitede value
  önerisi YOK; "Value rozeti bileşeni vardır ve `value_badge === null` iken HİÇBİR şey çizmez (boş kutu, "yakında" yazısı
  yok)." (§7)
- B7: "Maç sayfası yalnız vig'i temizlenmiş piyasa konsensüs olasılığını gösterir — kitap adı, kitap bazında oran,
  bağlantı yok." Skor yok (AK10).
- H4 kalıpları: "lisanslı", "licensed", "resmi/resmî veri", "official data", "official partner", "resmi/resmî ortak",
  "authorized", "yetkili veri"; olumsuz cümle yalnız `data-fe-allow="license-negation"` öznitelikli öğede.
- H5 kalıpları: `postgres://`, `postgresql://`, `service_role`, `eyJ` (JWT öneki), `SUPABASE_`, `NETLIFY_AUTH`.
- H6: "Sicil yalnız defterden türetilir, elle yazılmaz; TS sayı HESAPLAMAZ." §5.4: "olasılık ve hareket yüzde puanı 1
  ondalık (`45.7`), CLV yüzde 2 ondalık, fiyat 2 ondalık. TS yalnız dile göre ondalık ayracı (`45,7` / `45.7`) ve birim
  (`%`, `pp`) ekler; yuvarlama, çarpma, toplama yapmaz. `format` fonksiyonu tek yerdedir."
- H7: "`SITE_INDEXABLE` yoksa her sayfa `<meta name="robots" content="noindex">` + derlemenin ürettiği `out/_headers`te
  `X-Robots-Tag: noindex`; `robots.txt` bu dönemde `Disallow` TAŞIMAZ."
- URL şeması (§8.1, AK20 b): `/{lang}/` · `/{lang}/{league}/` · `/{lang}/{league}/{team}/` ·
  `/{lang}/{league}/match/{path_id}/{home}-vs-{away}/` · `/{lang}/track-record/` ·
  `/{lang}/legal/{terms,privacy,cookies,responsible-gambling}/`; "`/` → `/en/`, `out/_redirects`; `x-default` = `/en/`";
  "lig slug'ı `track-record`/`legal` olamaz; takım slug'ı `match` olamaz"; `dynamicParams = false`; maç başına
  "**zorlamasız** `301` (`301!` DEĞİL)".
- Yer tutucular: marka `SITE_NAME` (AK3), alan adı `https://example.invalid` (AK4), diller `web/site.config.ts`
  `SITE_LANGS` = `en` + `tr` (AK5). Kod bu değerleri başka yerde literal taşımaz.
- AK19 (a): "derleme sonrası satır içi betiklerin sha256'larını toplayıp `out/_headers` CSP'sine yazan adım"; JSON-LD
  "CSP'ye tabi değildir ve hash listesine girmez". (b) `'unsafe-inline'`e düşmek AYRI kullanıcı kararıdır.
- Yasal metinler: "hepsi 'TASLAK — avukat onayı bekler' başlığıyla (`web/content/legal/{lang}/*.tsx`)", düz TSX,
  markdown yok; yardım hattı iletişim bilgileri "`[DOĞRULANACAK]` işaretli".
- Deploy (§11): "`web/netlify.toml`: `[build] publish = "out"`; `command` Netlify'da derlemeyi reddeden bir komut";
  "Başlıklar `netlify.toml`de değil, derlemenin ürettiği `out/_headers`te".
- "pnpm ya da Node yoksa B-2 adımları **FAIL** (SKIP değil)." (§12.1)

Proje süreci (HANDOFF/bellek, her görevde):

- **Kapı:** `TMPDIR=$(mktemp -d) ./verify.sh > .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-tN-gate.log 2>&1`; sonuç
  LOG DOSYASINDAN okunur (özet değil). T0'ın kaydettiği taban PASS sayısı + adıyla SKIP'ler aynen kalır; T10'dan sonra
  altı site adımı da PASS. Her commit'ten sonra TAM kapı.
- **WEB-KAPI** (T1–T9; T10'da `verify.sh`in parçası olur), depo kökünden:
  ```bash
  source ~/.nvm/nvm.sh && nvm use "$(cat web/.nvmrc)" >/dev/null
  export NEXT_TELEMETRY_DISABLED=1          # Next derlemesi ağa telemetri yazmasın
  pnpm -C web install --frozen-lockfile
  pnpm -C web exec tsc --noEmit
  pnpm -C web exec biome ci .
  pnpm -C web exec vitest run
  ```
  Görevin kendi derleme/tarama adımları ayrıca yazılıdır.
- Her yeni test bir mutasyonla KIRMIZI kanıtlanır, sonra geri alınır; geri alma `git diff --stat -- <dosya>` boş çıktısıyla
  kanıtlanır (`git checkout -- <yol>` / `git restore` KULLANILMAZ — izin katmanında onaylıdır). Python mutasyonları
  `PYTHONDONTWRITEBYTECODE=1` ile koşar (bellek: bayat `.pyc`).
- HİÇBİR ŞEY SİLİNMEZ (`rm` yok; derleme çıktıları `mktemp -d` dizinlerine kopyalanır). `git add -A` / `git add .` YOK —
  dosyalar adıyla eklenir. Deploy, Netlify hesabı, secret, ağa yazma YOK. DB'ye bağlanılmaz.
- Commit: `<type>: <açıklama>` + boş satır + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Worktree: `.worktrees/wt-s9-b2`, dal `feat/s9-iz-b2` (controller kurar); `main`e yalnız `--no-ff`; rebase/force yok.
- İndirme gerektiren adımlar (Node 24, pnpm 10, `pnpm install`) controller onayıyla koşar (paket kayıt defterinden
  OKUMA/indirme; yazma değil).

## Review Focus

Spec'in ima ettiği ama görev testlerinin kendiliğinden kapsamayacağı, kullanıcıyı en olası ısıracak girdiler. Her birinin
testi sahibi görevin adımındadır:

1. **HTML'de kaçış isteyen adlar** (`Doğu & Batı FK`, `O'Brien Rovers`, `Güneyköy İdmanyurdu`): React `&amp;`, `&#x27;`
   basar; tarayıcı metni çözmeden karşılaştırırsa her doğru sayfa kırmızı, çözmeyi unutursa `&` taşıyan veri H6'dan
   kaçar; JSON-LD'de `</script>` kırılması → fixture bu adları taşır (T2), `decodeEntities` testi (T8), `serializeLd`
   `</script>` testi (T4), gerçek derlemede başlık ve tablo başlığı (T5 duman, T9).
2. **Sayı sınır biçimleri:** JSON `40.0` → JS `40` (`"40"` basılırsa kopuk), `-0`, negatif hareket/CLV, üslü gösterim
   (`1e-7`), sözleşmeden fazla ondalık (`45.75`) → `formatNumber` doldurur, ASLA yuvarlamaz, sözleşme dışını adıyla reddeder
   (T3); fixture'da `40.0`, `-1.3`, `-4.76` var (T2).
3. **Kısmi maç verisi:** eşik altı açılış (`null`), mühürsüz maç (`closing: null`), tek turlu maç, hareketsiz maç →
   sayfa çökmez, sayı UYDURMAZ, "NaN/undefined/null" basmaz, neden yazar ("Yetersiz kitap" / "Kapanış bekleniyor") —
   fixture (T2), beklenen alan kümesi + görünen metin taraması (T9), duman (T5).
4. **Yol çakışması ve ayrılmış slug:** lig slug'ı `track-record`/`legal`/`data`/`_next`, takım slug'ı `match`, aynı lig
   altında aynı `path_id` → iki kayıt tek sayfaya yazılır ya da sabit bir sayfayı gölgeler → yükleyici adıyla düşer (T2),
   tarayıcı "iki kayıt aynı yola düşüyor" (T9).
5. **Yanlış/eksik/bayat anlık görüntü girdisi:** `SITE_SNAPSHOT` yok → sessizce fixture'a DÜŞMEZ (T2); önceki koşudan
   kalmış uçtan uca JSON → yerelde adıyla SKIP, `CI=true` iken FAIL (T10); derlenmiş `out/` başka bir anlık görüntüye
   karşı taranırsa kırmızı (T9 mutasyonu).

**Kapının ölçmedikleri (bu plan; faz HANDOFF'una):** (a) CSP'nin tarayıcıda gerçekten uygulandığı ve istemci
betiklerinin (18+, yerel saat) CSP altında çalıştığı — yalnız hash eşleşmesi ölçülür (§12.4/8); (b) Netlify'ın
`_headers`/`_redirects`i gerçekten uyguladığı, `*.netlify.app` alt alanının `noindex`i (§18.5/4) ve pasif lig için 404/410
(§18.5/6) — Netlify hesabı olmadan ölçülemez; (c) Next'in `404.html` sayfası `_headers`te CSP almaz (Netlify 404 yanıtında
yalnız `/*` başlıkları uygulanır; `/*`e CSP konamaz — sayfa CSP'leriyle kesişir); (d) `config/site_redirects.yaml`deki
takım/lig yeniden adlandırma yönlendirmeleri `_redirects`e girmez (spec biçimi tanımlamıyor — Açık sorular/4); (e) H4
kalıp listesidir, listede olmayan ifadeyi yakalamaz; H1 yalnız tarih kalıbı tarar (§12.4/4–5); (f) `_headers` boyutu sayfa
sayısıyla doğrusal büyür (ölçüm T9'da kaydedilir; eşik aşılırsa AK19 (b) kullanıcı kararıdır); (g) görsel düzen,
duyarlı tasarım, tam erişilebilirlik (axe), çeviri kalitesi, yasal metinlerin doğruluğu (§12.4/6–8, /10); (h) TS'in sayı
hesaplamadığı yalnız dolaylı ölçülür: basılan her sayı anlık görüntüde birebir karşılık bulmalıdır (H6c), `data-fe`siz
basılan sayı tarayıcıdan kaçar (sayfa kodu incelemesi, T5/T6).

---

## B-1 ile arayüz (B-2'nin tükettiği ve ürettiği HER şey)

**Tüketir (B-1 üretir):**

| Ne | Nerede | İlk gerektiği görev |
|---|---|---|
| Anlık görüntü JSON Schema v1 | `web/contract/snapshot.schema.json` (B-1 T1) | T2 (anahtar kümesi ↔ TS tipi, fixture şekli) |
| `verify-snapshot` CLI | `uv run python -m football_edge.site verify-snapshot <dosya>` (B-1 T5); başarıda exit 0 | T10 (her derleme varyantından önce) |
| Uçtan uca anlık görüntü | `${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e/snapshot.json` + `run-id` = `FE_VERIFY_RUN_ID` (B-1 `site-db` adımı) | T10 |
| `verify.sh` `site-db` adımı ve `export FE_VERIFY_RUN_ID` | B-1 dalga sonu birleştirmesi | T10 |
| `.github/workflows/site.yml` | B-1 T6 (§15) | T10 (Node adımları B-2 komutlarıyla hizalanır) |

**Üretir (B-1 ve `site.yml` kullanır):**

| Ne | Biçim |
|---|---|
| Kurulum | `pnpm -C web install --frozen-lockfile` |
| Derleme | `SITE_SNAPSHOT=<mutlak yol> [SITE_INDEXABLE=1] NEXT_TELEMETRY_DISABLED=1 pnpm -C web run build` → `web/out/` (`next build` + `scripts/emit-headers.ts`; ÇIPLAK `next build` `_headers`/`_redirects`/`data/` ÜRETMEZ) |
| Çıktı tarayıcısı | `[SITE_INDEXABLE=1] node web/scripts/check-out.ts --snapshot <dosya> --out <dizin>`; bulgu yoksa exit 0 |
| Yayın dosyaları | `out/_headers`, `out/_redirects`, `out/data/snapshot.sha256` (anlık görüntü dosya baytlarının sha256 hex'i + `\n`), `out/data/slugs.json` = `{"version": 1, "leagues": [<lig slug'ı>…], "teams": ["<lig slug'ı>/<takım slug'ı>"…]}` (ikisi de sıralı; AK20 b'nin kaybolan-slug kontrolünün deposu) |
| Sentetik fixture'lar | `web/fixtures/snapshot.fixture.web-full.json`, `web/fixtures/snapshot.fixture.web-empty.json` (`tests/site_web_fixtures.py` üretir) |

**Sıralama:** T0 ve T1 B-1'den bağımsızdır (hemen başlar). T2–T9 B-1 T1'in sözleşme commit'i `main`e birleştikten
sonra başlar (spec §15 "B-1 T1 birleşince paralel"). T10 B-1'in dalga sonu birleştirmesinden SONRA (spec §12.2–§12.3).

---

## Dosya yapısı ve tek-yazar tablosu

| Görev | Oluşturur | Değiştirir |
|---|---|---|
| 0 | `.superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t0-olcum.md` (depo dışı) | — |
| 1 | `web/{package.json,pnpm-lock.yaml,.nvmrc,tsconfig.json,next.config.ts,biome.json,vitest.config.ts,site.config.ts}`, `web/src/types/next.d.ts`, `web/src/app/[lang]/{layout,page}.tsx` (geçici), `web/src/lib/site-config.test.ts`, `tests/test_site_web_deps.py` | `.gitignore` |
| 2 | `tests/site_web_fixtures.py`, `tests/test_site_web_contract.py`, `web/fixtures/snapshot.fixture.web-{full,empty}.json`, `web/src/lib/{snapshot-types,snapshot,fixture}.ts`, `web/src/lib/snapshot.test.ts` | — |
| 3 | `web/src/lib/{format,fe}.ts`, `web/src/lib/format.test.ts`, `web/src/i18n/{en.json,tr.json,dict.ts,dict.test.ts}` | — |
| 4 | `web/src/lib/{routes,hreflang,jsonld,meta,params}.ts`, `web/src/lib/{routes,jsonld}.test.ts` | — |
| 5 | `web/src/components/{Fe,Breadcrumbs,JsonLdScript,LocalTime,Slots,RoundsTable,SiteChrome}.tsx`, `web/src/components/Fe.test.tsx`, `web/src/styles/site.module.css`, `web/src/app/[lang]/[league]/page.tsx`, `…/[team]/page.tsx`, `…/match/[pathId]/[slug]/page.tsx` | `web/src/app/[lang]/{layout,page}.tsx`, `web/src/lib/site-config.test.ts` |
| 6 | `web/src/app/[lang]/track-record/page.tsx`, `web/src/components/RecordTable.tsx` | — |
| 7 | `web/src/lib/consent.ts`, `web/src/components/{AgeGate.tsx,AgeGate.test.tsx}`, `web/content/legal/{en,tr}/{terms,privacy,cookies,responsible-gambling}.tsx`, `web/content/legal/{index.ts,legal.test.ts}`, `web/src/app/[lang]/legal/[doc]/page.tsx` | `web/src/app/[lang]/layout.tsx` |
| 8 | `web/src/app/{sitemap,robots}.ts`, `web/src/lib/pages.ts`, `web/scripts/lib/{html,outdir,emit}.ts`, `web/scripts/lib/{html,emit}.test.ts`, `web/scripts/emit-headers.ts`, `web/netlify.toml`, `tests/test_site_web_netlify.py` | `web/package.json` (`build` betiği) |
| 9 | `web/scripts/checkout/{expect,checks}.ts`, `web/scripts/checkout/checks.test.ts`, `web/scripts/check-out.ts` | — |
| 10 | `scripts/site_gate.sh`, `tests/test_site_web_gate.py` | `verify.sh`, `.github/workflows/ci.yml`, `.github/workflows/site.yml` (yalnız Node adımları, gerekirse), `tests/site_web_fixtures.py` (yalnız `PATH_ID_LENGTH`, gerekirse) |

B-1'in dosyalarına (T10'daki sıralı istisnalar dışında) HİÇ yazılmaz. `tests/test_site_web_*.py` öneki B-1'in
`tests/test_site_*.py` dosyalarıyla çakışmaz.

**Yürütme sırası:** tek implementer, sıralı: T0 → T1 → (B-1 T1 birleşimi) → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 →
(B-1 dalga sonu) → T10. T3/T4 ve T7'nin yasal metinleri birbirinden bağımsızdır ama hepsi `web/package.json`/kilit
dosyasının tek yazarı T1'e dayanır; paralelleştirme kazancı küçük, çakışma riski (tek `layout.tsx`) büyük.

**Risk kademeleri (spec §14):** K1 süreci (TDD + mutasyonlu görev incelemesi + bütün-dal incelemesi): **T9** (spec: "B-2'deki
tarayıcı görevi de bu süreçle işaretlenir"). K2 (TDD + tek görev incelemesi): T1, T2, T3, T4, T6, T8, T10. K3 (controller
doğrulaması): T5 (görsel şablonlar; veri bağlantısı T9'da ölçülür), T7 (yasal taslaklar, i18n metni). T0 ölçümdür.

---

### Task 0: Araç zinciri ve sözleşme durumunun ölçümü (kayıt, kod yok)

**Kademe:** ölçüm · **Spec:** §13 (Node 24, pnpm 10, "sürüm plan günündeki kararlı sürüm"), §15 (B-1 T1 başlangıç kapısı), §12.1
("pnpm ya da Node yoksa … FAIL")

Sonraki görevlerin sabitlediği her sürüm BU kayıttan okunur; hiçbir görev sürümü ezberden yazmaz. Kayıt depoya
girmez (`.superpowers/sdd/` gitignore'da); sürümlerin kalıcı kaydı T1'in `package.json`, `.nvmrc` ve kilit dosyasıdır.

**Files:**
- Create: `.superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t0-olcum.md`

**Interfaces:**
- Produces (T1, T10 okur): kayıt dosyasında tam olarak şu satırlar —
  `NODE_VERSION=24.x.y` · `PNPM_VERSION=10.x.y` · `NEXT_VERSION=16.x.y` · `REACT_VERSION=19.x.y` ·
  `TYPESCRIPT_VERSION=5.9.x` · `TYPES_REACT_VERSION=19.x.y` · `TYPES_REACT_DOM_VERSION=19.x.y` ·
  `TYPES_NODE_VERSION=24.x.y` · `VITEST_VERSION=4.x.y` · `BIOME_VERSION=2.x.y` · `B1_CONTRACT=var|yok (<commit>)` ·
  `B1_VERIFY_SNAPSHOT=var|yok` · `GATE_BASELINE=<N> PASS + <adıyla SKIP listesi>`.

- [ ] **Step 1: Kapının tabanını ölç**

Run: `TMPDIR=$(mktemp -d) ./verify.sh > .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t0-gate.log 2>&1; echo "exit=$?"; grep -E "^(PASS|FAIL|SKIP)" .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t0-gate.log`
Expected: `exit=0`, `KAPI YEŞİL`; bugün 10 PASS + `SKIP: zincir (DATABASE_URL yok)` (B-1 birleştiyse `site-db` de PASS).
Sayıyı `GATE_BASELINE=` satırına yaz. Kırmızıysa DUR: B-2 kırmızı tabana kurulmaz, controller'a bildir.

- [ ] **Step 2: Node 24'ü ölç**

Run: `source ~/.nvm/nvm.sh; nvm ls 24; nvm ls-remote --lts | grep -E ' v24\.' | tail -1`
Expected: yazım anında (2026-09-24) yerelde Node 24 YOK (kurulu: v20.20.2, v22.20.0; varsayılan 22) ve en yeni 24 LTS
`v24.21.0 (Latest LTS: Krypton)`. Yerelde yoksa: **controller onayıyla** `nvm install 24.21.0` (nodejs.org'dan ~30 MB
indirme; kurulum `~/.nvm` altındadır, depoya dokunmaz). Sonra `nvm use 24 && node -v` → `v24.21.0`.
`NODE_VERSION=` satırına yaz. Varsayılan nvm takma adı DEĞİŞTİRİLMEZ (başka projeler 22 kullanıyor).

- [ ] **Step 3: pnpm 10'u ölç**

Run: `nvm use 24 >/dev/null; npm view pnpm@10 version | tail -1; pnpm -v 2>/dev/null || echo "pnpm yok"`
Expected: kayıt defterinde `pnpm@10.34.5` (yazım anı). Node 24 altında pnpm yoksa ya da ana sürümü 10 değilse (yerelde
Node 22 altında `11.9.0` var — kullanılmaz): **controller onayıyla** `npm install -g pnpm@<ölçülen 10.x.y>` (yalnız Node 24'ün
nvm önekine kurulur). `pnpm -v` → `10.x.y`. `PNPM_VERSION=` satırına yaz.

- [ ] **Step 4: Paket sürümlerini ölç (kayıt defterinden OKUMA)**

Run:
```bash
for spec in next react@19 react-dom@19 typescript@5 @types/react@19 @types/react-dom@19 @types/node@24 vitest@4 @biomejs/biome@2; do
  printf '%s ' "$spec"; npm view "$spec" version | tail -1
done
```
Expected (2026-09-24 ölçümü): `next 16.3.6` · `react 19.3.0` · `react-dom 19.3.0` · `typescript 5.9.3` ·
`@types/react 19.3.0` · `@types/react-dom 19.3.0` · `@types/node 24.13.6` · `vitest 4.1.11` · `@biomejs/biome 2.5.14`.
Karar kuralları (kayda yaz): `next` spec gereği en yeni kararlı sürümdür — ana sürüm 16 DEĞİLSE DUR ve eskale et (plan kodu
Next 16'nın `params: Promise<…>` API'sine göre yazıldı). TypeScript bilinçli olarak 5.x'te tutulur (kayıt defterinde 6.x ve
7.x var; Next'in derleme içi tip denetimi TS'in JS API'sine dayanır, 7.x yerel sürümde bu API ölçülmedi). Vitest 4.x'te
tutulur (plan testleri 4.1.9'la koşturuldu; 5.x `vite`ı eş bağımlılık yapıyor). Biome 2.x.

- [ ] **Step 5: B-1 sözleşmesinin durumunu ölç**

Run:
```bash
git log --oneline -3 main -- web/contract/snapshot.schema.json
test -f web/contract/snapshot.schema.json && echo "şema var" || echo "şema yok"
ls src/football_edge/site/ 2>/dev/null || echo "site paketi yok"
uv run python -m football_edge.site verify-snapshot --help 2>&1 | head -3
grep -rn "PATH_ID\|path_id" src/football_edge/site/slugs.py 2>/dev/null | head -5
```
Expected: B-1 T1 birleşmediyse "şema yok" — T2 başlayamaz; T1 yine koşar. `B1_CONTRACT=` ve `B1_VERIFY_SNAPSHOT=` satırlarını
yaz; `slugs.py` varsa `path_id` önek uzunluğunu da yaz (`PATH_ID_LENGTH=`; yoksa `bilinmiyor`).

- [ ] **Step 6: Kaydı yaz ve oku**

Kayıt dosyası şu biçimde (örnek değerler Step 1–5'in yazım anı ölçümüdür; dosyaya ÖLÇÜLENLER yazılır):
```text
# B-2 T0 ölçümü — <tarih saat UTC>
NODE_VERSION=24.21.0
PNPM_VERSION=10.34.5
NEXT_VERSION=16.3.6
REACT_VERSION=19.3.0
TYPESCRIPT_VERSION=5.9.3
TYPES_REACT_VERSION=19.3.0
TYPES_REACT_DOM_VERSION=19.3.0
TYPES_NODE_VERSION=24.13.6
VITEST_VERSION=4.1.11
BIOME_VERSION=2.5.14
B1_CONTRACT=yok
B1_VERIFY_SNAPSHOT=yok
PATH_ID_LENGTH=bilinmiyor
GATE_BASELINE=10 PASS + SKIP: zincir (DATABASE_URL yok)
```
Run: `cat .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t0-olcum.md`
Expected: 14 satır + başlık; hiçbir değer boş değil. Commit YOK (kayıt depo dışında).

---

### Task 1: Web iskeleti, araç zinciri sabitleri, bağımlılık allowlist'i

**Kademe:** K2 · **Spec:** §13, H5a, §12.1 (`site-kurulum`, `site-tip`, `site-lint`, `site-test`), B8

**Files:**
- Create: `web/package.json`, `web/pnpm-lock.yaml` (pnpm üretir), `web/.nvmrc`, `web/tsconfig.json`, `web/next.config.ts`,
  `web/biome.json`, `web/vitest.config.ts`, `web/site.config.ts`, `web/src/types/next.d.ts`,
  `web/src/app/[lang]/layout.tsx` (geçici; T5 yeniden yazar), `web/src/app/[lang]/page.tsx` (geçici; T5 yeniden yazar),
  `web/src/lib/site-config.test.ts`
- Modify: `.gitignore` (sona altı satır)
- Test: `tests/test_site_web_deps.py`

**Interfaces:**
- Consumes: T0 kaydı (`*_VERSION` satırları).
- Produces (bütün sonraki görevler): `web/site.config.ts` —
  ```ts
  export const SITE_NAME: string;            // "[site-name]" yer tutucu (AK3)
  export const SITE_URL: string;             // "https://example.invalid" (AK4)
  export const LEDGER_HISTORY_URL: string;   // çıpa geçmişi bağlantısının tabanı (yer tutucu)
  export const SITE_LANGS: readonly ["en", "tr"];  export type Lang = "en" | "tr";
  export const DEFAULT_LANG: Lang;           // "en"
  export const RESERVED_LEAGUE_SLUGS: readonly string[];  // track-record, legal, data, _next
  export const RESERVED_TEAM_SLUGS: readonly string[];    // match
  export const LEGAL_DOCS: readonly ["terms","privacy","cookies","responsible-gambling"]; export type LegalDoc;
  export function isLang(value: string): value is Lang;
  export function indexingEnabled(env?: Record<string, string | undefined>): boolean; // yalnız SITE_INDEXABLE === "1"
  ```
  `package.json` betikleri: `build` (T8'e kadar yalnız `next build`), `typecheck`, `lint`, `test`.

- [ ] **Step 1: Başarısız testi yaz — `tests/test_site_web_deps.py`**

```python
"""H5a: web tarafının bağımlılık listesi sabit; Node DB'ye bağlanamaz (spec §2 H5, §13).

Çalışma zamanı bağımlılığı YALNIZ `next`, `react`, `react-dom`. Dev araçları izinli
listeden. Kilit dosyasının TAMAMINDA (geçişli bağımlılıklar dahil) DB sürücüsü ve
Supabase istemcisi yok. Bağımlılık eklemek bilinçli bir commit'tir: bu dosyadaki liste
de değişir ve inceleme görür.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WEB = REPO / "web"
PACKAGE = WEB / "package.json"
LOCK = WEB / "pnpm-lock.yaml"

RUNTIME = {"next", "react", "react-dom"}
# Spec §13'ün dev listesi + `@types/react-dom` (react-dom/server tipleri; plan kararı, yalnız tip).
DEV_ALLOWED = {
    "typescript",
    "@types/react",
    "@types/react-dom",
    "@types/node",
    "vitest",
    "@biomejs/biome",
    "schema-dts",
}
# Geçişli dahil hiçbir yerde olmayacaklar: DB sürücüleri, ORM'ler, Supabase istemcileri.
BANNED = {
    "pg",
    "pg-native",
    "postgres",
    "@neondatabase/serverless",
    "mysql",
    "mysql2",
    "better-sqlite3",
    "sqlite3",
    "prisma",
    "@prisma/client",
    "drizzle-orm",
    "kysely",
    "knex",
    "sequelize",
    "typeorm",
    "netlify-cli",
}
BANNED_SCOPES = ("@supabase/",)


def _package() -> dict[str, Any]:
    return json.loads(PACKAGE.read_text(encoding="utf-8"))


def lock_package_names(text: str) -> set[str]:
    """pnpm kilit v9 `packages:` anahtarları `ad@sürüm`dür; kapsamlı ad `@` ile başlar."""
    packages = yaml.safe_load(text).get("packages") or {}
    return {key[: key.rindex("@")] for key in packages}


def test_runtime_dependencies_are_exactly_next_and_react() -> None:
    assert set(_package()["dependencies"]) == RUNTIME


def test_dev_dependencies_stay_inside_the_allow_list() -> None:
    extra = set(_package()["devDependencies"]) - DEV_ALLOWED
    assert not extra, f"izin listesi dışı dev bağımlılığı: {sorted(extra)}"


@pytest.mark.parametrize("section", ["dependencies", "devDependencies"])
def test_versions_are_pinned_exactly(section: str) -> None:
    loose = {name: spec for name, spec in _package()[section].items() if not spec[:1].isdigit()}
    assert not loose, f"tam sürüm değil: {loose}"


def test_lock_parser_reads_scoped_and_plain_names() -> None:
    text = "packages:\n  '@supabase/ssr@0.1.0':\n    {}\n  pg@8.0.0:\n    {}\n"
    assert lock_package_names(text) == {"@supabase/ssr", "pg"}


def test_no_database_client_anywhere_in_the_lockfile() -> None:
    names = lock_package_names(LOCK.read_text(encoding="utf-8"))
    assert {"next", "react", "react-dom"} <= names, "kilit ayrıştırılamadı"
    leaking = sorted(name for name in names if name in BANNED or name.startswith(BANNED_SCOPES))
    assert not leaking, f"DB/Supabase istemcisi kilitte (H5): {leaking}"


def test_toolchain_is_pinned_where_ci_reads_it() -> None:
    package = _package()
    assert (WEB / ".nvmrc").read_text(encoding="utf-8").strip() == "24"
    assert package["engines"] == {"node": ">=24 <25"}
    assert package["packageManager"].startswith("pnpm@10.")
    assert package["type"] == "module"


def test_dependency_lifecycle_scripts_stay_closed() -> None:
    """pnpm 10 bağımlılık betiklerini varsayılan olarak koşmaz; izin listesi boş kalır."""
    assert "pnpm" not in _package(), "package.json `pnpm` ayarı taşıyor"
    workspace = WEB / "pnpm-workspace.yaml"
    if workspace.exists():
        settings = yaml.safe_load(workspace.read_text(encoding="utf-8")) or {}
        opened = {"onlyBuiltDependencies", "dangerouslyAllowAllBuilds"} & set(settings)
        assert not opened, f"bağımlılık betikleri açılmış: {sorted(opened)}"


@pytest.mark.parametrize(
    "path",
    [
        "web/node_modules/x",
        "web/.next/x",
        "web/out/x",
        "web/.snapshot/x",
        "web/next-env.d.ts",
        "web/tsconfig.tsbuildinfo",
    ],
)
def test_build_output_never_enters_git(path: str) -> None:
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO, check=False)
    assert result.returncode == 0, f"{path} gitignore'da değil"
```

- [ ] **Step 2: Testi koştur, kırmızı olduğunu gör**

Run: `uv run pytest -q tests/test_site_web_deps.py`
Expected: FAIL — `FileNotFoundError: … web/package.json` (paket testleri) ve `web/node_modules/x gitignore'da değil`
(check-ignore testleri).

- [ ] **Step 3: `.gitignore`a derleme çıktılarını ekle**

`.gitignore`un SONUNA (mevcut satırlara dokunmadan; B-1 T1 aynı satırlardan bazılarını eklemişse yalnız eksikleri):
```gitignore
web/node_modules/
web/.next/
web/out/
web/.snapshot/
web/next-env.d.ts
web/*.tsbuildinfo
```

- [ ] **Step 4: Araç zinciri dosyalarını yaz**

`web/.nvmrc`:
```text
24
```

`web/package.json` — sürümler T0 kaydından (aşağıdaki değerler 2026-09-24 ölçümüdür; kayıt farklıysa KAYDI yaz):
```json
{
  "name": "football-edge-web",
  "private": true,
  "type": "module",
  "packageManager": "pnpm@10.34.5",
  "engines": {
    "node": ">=24 <25"
  },
  "scripts": {
    "build": "next build",
    "typecheck": "tsc --noEmit",
    "lint": "biome ci .",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "16.3.6",
    "react": "19.3.0",
    "react-dom": "19.3.0"
  },
  "devDependencies": {
    "@biomejs/biome": "2.5.14",
    "@types/node": "24.13.6",
    "@types/react": "19.3.0",
    "@types/react-dom": "19.3.0",
    "typescript": "5.9.3",
    "vitest": "4.1.11"
  }
}
```

`web/tsconfig.json` — Next'in derlemede yeniden yazdığı biçimde (kazımada iki ardışık `next build` sonrası bayt bayt
değişmedi; farklı biçimde yazılırsa Next her derlemede dosyayı değiştirir ve çalışma ağacı kirlenir):
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": [
      "dom",
      "dom.iterable",
      "esnext"
    ],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "erasableSyntaxOnly": true,
    "noUncheckedIndexedAccess": true,
    "types": [
      "node"
    ],
    "plugins": [
      {
        "name": "next"
      }
    ],
    "noUnusedLocals": true,
    "noUnusedParameters": true
  },
  "include": [
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts"
  ],
  "exclude": [
    "node_modules",
    "out"
  ]
}
```

`web/next.config.ts`:
```ts
import type { NextConfig } from "next";

// Spec §13: statik dışa aktarım; sunucu, görüntü optimizasyonu, çalışma zamanı yok.
const config: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  reactStrictMode: true,
};

export default config;
```

`web/biome.json` (`tsconfig.json` biçimi Next'e aittir, fixture/sözleşme JSON'u Python'a; ikisi de Biome dışında):
```json
{
  "$schema": "./node_modules/@biomejs/biome/configuration_schema.json",
  "vcs": { "enabled": true, "clientKind": "git", "useIgnoreFile": true, "root": ".." },
  "files": {
    "includes": [
      "**",
      "!**/fixtures",
      "!**/contract",
      "!**/tsconfig.json",
      "!**/next-env.d.ts",
      "!**/.next",
      "!**/out"
    ]
  },
  "formatter": { "enabled": true, "indentStyle": "space", "indentWidth": 2, "lineWidth": 100 },
  "linter": { "enabled": true, "rules": { "recommended": true } },
  "assist": { "enabled": true, "actions": { "source": { "organizeImports": "on" } } }
}
```

`web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";

// Birim testleri Node ortamında koşar; tarayıcı/DOM kütüphanesi yok (bağımlılık listesi §13).
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}", "scripts/**/*.test.ts", "content/**/*.test.ts"],
  },
});
```

`web/src/types/next.d.ts` (CSS modülü tipleri; `next-env.d.ts` gitignore'da ve CI'da `tsc` derlemeden önce koşar):
```ts
/// <reference types="next" />
```

`web/site.config.ts`:
```ts
// Sitenin yer tutucu kimliği ve dil listesi — TEK kaynak (spec §8.3, AK3, AK4, AK5).
// Marka, alan adı ve diller kullanıcı kararıdır; kodun başka hiçbir yeri bu değerleri
// literal olarak taşımaz (src/lib/site-config.test.ts sınar).

export const SITE_NAME = "[site-name]";
export const SITE_URL = "https://example.invalid";
// Çıpa geçmişinin herkese açık adresi (spec §6.1): depo adı da bir yayın kararıdır.
export const LEDGER_HISTORY_URL = "https://example.invalid/ledger-history";

export const SITE_LANGS = ["en", "tr"] as const;
export type Lang = (typeof SITE_LANGS)[number];
export const DEFAULT_LANG: Lang = "en";

// §8.1: lig slug'ı sabit bölüt adı olamaz; `data` ve `_next` derleme çıktısının dizinleridir.
export const RESERVED_LEAGUE_SLUGS: readonly string[] = ["track-record", "legal", "data", "_next"];
export const RESERVED_TEAM_SLUGS: readonly string[] = ["match"];

export const LEGAL_DOCS = ["terms", "privacy", "cookies", "responsible-gambling"] as const;
export type LegalDoc = (typeof LEGAL_DOCS)[number];

export function isLang(value: string): value is Lang {
  return (SITE_LANGS as readonly string[]).includes(value);
}

// H7/B8: bayrak yoksa HER sayfa noindex. Yalnız tam olarak "1" açar.
export function indexingEnabled(env: Record<string, string | undefined> = process.env): boolean {
  return env.SITE_INDEXABLE === "1";
}
```

- [ ] **Step 5: Geçici kök yerleşim ve ana sayfa (T5 yeniden yazar)**

`web/src/app/[lang]/layout.tsx`:
```tsx
// Kök yerleşim dil bölütündedir: `<html lang>` sayfanın diliyle aynıdır (spec §5.3/8).
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { isLang, SITE_LANGS } from "../../../site.config.ts";

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export default async function LangLayout(props: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await props.params;
  if (!isLang(lang)) notFound();
  return (
    <html lang={lang}>
      <body>{props.children}</body>
    </html>
  );
}
```

`web/src/app/[lang]/page.tsx`:
```tsx
import { SITE_LANGS, SITE_NAME } from "../../../site.config.ts";

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export default function HomePage() {
  return (
    <main data-fe-page="home">
      <h1>{SITE_NAME}</h1>
    </main>
  );
}
```

`web/src/lib/site-config.test.ts` (T5 yer tutucu taramasını ekler):
```ts
import { describe, expect, it } from "vitest";
import { indexingEnabled, isLang, SITE_LANGS } from "../../site.config.ts";

describe("site.config (spec §8.3, H7)", () => {
  it("indeksleme yalnız SITE_INDEXABLE=1 ile açılır", () => {
    expect(indexingEnabled({})).toBe(false);
    expect(indexingEnabled({ SITE_INDEXABLE: "0" })).toBe(false);
    expect(indexingEnabled({ SITE_INDEXABLE: "true" })).toBe(false);
    expect(indexingEnabled({ SITE_INDEXABLE: "1" })).toBe(true);
  });

  it("dil listesi yer tutucudur: en + tr (AK5 önerisi)", () => {
    expect(SITE_LANGS).toEqual(["en", "tr"]);
    expect(isLang("tr")).toBe(true);
    expect(isLang("de")).toBe(false);
  });
});
```

- [ ] **Step 6: Bağımlılıkları kur, kilit dosyasını üret (controller onayıyla indirme)**

Run: `source ~/.nvm/nvm.sh && nvm use 24 >/dev/null && pnpm -C web install`
Expected: `web/pnpm-lock.yaml` oluşur; pnpm 10 bağımlılık yaşam döngüsü betiklerini koşmaz ve "Ignored build scripts: …"
uyarısı basabilir — bu BEKLENEN durumdur (spec §12.1 "izin listesi boş"); `pnpm approve-builds` KOŞULMAZ,
`onlyBuiltDependencies` EKLENMEZ. Ardından: `pnpm -C web install --frozen-lockfile` → "Lockfile is up to date".

- [ ] **Step 7: Python testini koştur, yeşil**

Run: `uv run pytest -q tests/test_site_web_deps.py`
Expected: `14 passed` (8 test fonksiyonu; `section` 2, `path` 6 parametreyle genişler).

- [ ] **Step 8: Biçim ve lint (Biome'un ilk ölçümü)**

Run: `pnpm -C web exec biome check --write . && pnpm -C web exec biome ci .`
Expected: ilk komut yalnız biçim/import sırası düzeltir; ikincisi `Checked N files … No errors`. Bu plandaki kod Biome ile
koşturulmadı (yerelde kurulu değildi): kalan bir lint HATASI kural kapatılarak DEĞİL kod düzeltilerek giderilir;
`biome.json`a kural kapatma satırı eklemek bu görevin kapsamı DIŞINDADIR (gerekirse eskalasyon). Biome `vcs.root`
seçeneğini tanımazsa (`biome ci` yapılandırma hatası verir) o anahtar kaldırılır; `.next`/`out` zaten `files.includes`ta
dışlı.

- [ ] **Step 9: Tip denetimi, birim testi, derleme dumanı**

Run:
```bash
pnpm -C web exec tsc --noEmit && pnpm -C web exec vitest run
NEXT_TELEMETRY_DISABLED=1 pnpm -C web run build
ls web/out/en/index.html web/out/tr/index.html && grep -o '<html lang="tr"' web/out/tr/index.html
git status --short web/
```
Expected: tsc çıktısız; vitest `2 passed`; derleme `○ /_not-found`, `● /[lang]` (`/en`, `/tr`); `<html lang="tr"`;
`git status` yalnız bu görevin YENİ dosyalarını gösterir — `web/tsconfig.json` derlemeden sonra DEĞİŞMİŞ görünmez
(değişmişse Next'in yazdığı biçimi kabul et, farkı raporla, ikinci derlemede sabit kaldığını göster).

- [ ] **Step 10: Mutasyon kanıtları (her biri kırmızı, sonra geri)**

1. `web/package.json` `dependencies`e `"pg": "8.13.0",` ekle (kurmadan) → `uv run pytest -q tests/test_site_web_deps.py`
   → `test_runtime_dependencies_are_exactly_next_and_react` FAIL. Satırı sil; `git diff --stat -- web/package.json` boş.
2. `web/pnpm-lock.yaml`de `packages:` bölümünün ilk girdisinden önce iki satır ekle: `  '@supabase/supabase-js@2.0.0':` ve `    {}` →
   `test_no_database_client_anywhere_in_the_lockfile` FAIL ("DB/Supabase istemcisi kilitte"). Geri al; diff boş.
3. `"next": "16.3.6"` → `"next": "^16.3.6"` → `test_versions_are_pinned_exactly[dependencies]` FAIL. Geri al.
4. `web/site.config.ts`de `env.SITE_INDEXABLE === "1"` → `env.SITE_INDEXABLE !== undefined` →
   `pnpm -C web exec vitest run` → "indeksleme yalnız SITE_INDEXABLE=1 ile açılır" FAIL. Geri al; diff boş.

- [ ] **Step 11: Tam kapı**

Run: `TMPDIR=$(mktemp -d) ./verify.sh > .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t1-gate.log 2>&1; echo exit=$?`
ve WEB-KAPI (Global Constraints). Expected: `exit=0`, T0 tabanı kadar PASS (pytest yeni 17 testle); WEB-KAPI dört komutu da 0.

- [ ] **Step 12: Commit**

```bash
git add .gitignore tests/test_site_web_deps.py web/package.json web/pnpm-lock.yaml web/.nvmrc web/tsconfig.json \
  web/next.config.ts web/biome.json web/vitest.config.ts web/site.config.ts web/src/types/next.d.ts \
  "web/src/app/[lang]/layout.tsx" "web/src/app/[lang]/page.tsx" web/src/lib/site-config.test.ts
git commit -m "feat: web iskeleti — statik dışa aktarım, araç zinciri sabitleri, bağımlılık allowlist'i (İz B · B-2 T1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Anlık görüntü sözleşmesinin web tarafı — TS tipi, yükleyici, sentetik fixture'lar

**Kademe:** K2 · **Spec:** §5.2 ("TS `Snapshot` tipini elle taşır; fixture `satisfies Snapshot` ile `tsc`'de sınanır; bir pytest
şemanın anahtar kümesini TS tip dosyasınınkiyle karşılaştırır"; "Fixture'lar **sentetiktir**"), §6.4/1 (fixture varyantları),
§8.1 (ayrılmış slug'lar, `path_id` çakışması), H3, B6 · **Ön koşul:** B-1 T1 (`web/contract/snapshot.schema.json`) `main`de.

**Files:**
- Create: `tests/site_web_fixtures.py` (fixture'ların TEK kaynağı), `tests/test_site_web_contract.py`,
  `web/fixtures/snapshot.fixture.web-full.json`, `web/fixtures/snapshot.fixture.web-empty.json` (üreticinin çıktısı),
  `web/src/lib/snapshot-types.ts`, `web/src/lib/snapshot.ts`, `web/src/lib/fixture.ts`, `web/src/lib/snapshot.test.ts`

**Interfaces:**
- Consumes: `web/contract/snapshot.schema.json` (B-1 T1); `football_edge.ledger._canonical(payload: dict) -> str`.
- Produces:
  ```ts
  // web/src/lib/snapshot-types.ts — tipler: Triple, Round, H2h, Anchor, Ledger, MoveDistribution, League, Team,
  //   Match, RecordEntry, RecordSummary, TrackRecord, Snapshot (alan adları spec §5.2 ile birebir)
  // web/src/lib/snapshot.ts
  export class SnapshotError extends Error {}
  export function parseSnapshot(text: string): Snapshot;           // yönlendirme değişmezleri, ihlalde SnapshotError
  export function loadSnapshot(env?: Record<string, string | undefined>): Snapshot;  // SITE_SNAPSHOT; önbellekli
  export function leagueById(snapshot: Snapshot, id: string): League;
  export function teamsOf(snapshot: Snapshot, league: League): Team[];
  export function matchesOf(snapshot: Snapshot, league: League): Match[];
  export function matchesOfTeam(snapshot: Snapshot, team: Team): Match[];
  export function teamByName(snapshot: Snapshot, leagueId: string, name: string): Team | undefined;
  // web/src/lib/fixture.ts (yalnız testler)
  export const FULL_FIXTURE: string; export function fullFixtureText(): string; export function fullFixture(): Snapshot;
  ```
  ```python
  # tests/site_web_fixtures.py
  FULL: Path; EMPTY: Path; PATH_ID_LENGTH: int  # = 12
  def content_sha256(document: dict[str, Any]) -> str
  def build(*, full: bool) -> dict[str, Any]
  def expected_files() -> dict[Path, str]
  ```
  Fixture içeriği (sonraki görevlerin testleri bunlara dayanır): ligler `xla.1` "Synthetic League Alpha"
  (`synthetic-league-alpha`, 5 maç, `move_distribution` dolu) ve `xlb.1` "Synthetic League Beta" (1 maç, `null`); takımlar
  Kuzeyspor, Güneyköy İdmanyurdu, Doğu & Batı FK, O'Brien Rovers, Delta City, Epsilon Town; altı maç (ilki
  `407957362b2a…` Kuzeyspor–Güneyköy, mühürlü; `34e5be017510…` açılışı eşik altı; `cdc63e7b45d9…` tek turlu, mühürsüz,
  gelecekte; `9694c89e7056…` mühürsüz, gelecekte; `40bb30156880…` `40.0` taşıyan); dolu sicil 2 girdi (`clv` 6.28 ve
  −4.76), boş sicil 0 girdi. `content_sha256`: dolu `84b758af18c8bc52930d8998f9600b4217f5d191152b73eba55a5dfc581890b3`,
  boş `21a8bcf01b07804c7b38abbd8b322bea7a50dd2562e3b888888f5a80a4b8ede7`.

- [ ] **Step 1: B-1'in sözleşmesini dala al**

Run: `git merge --no-ff main -m "Merge main: B-1 T1 sözleşmesi (B-2 T2 ön koşulu)"` ve `test -f web/contract/snapshot.schema.json && echo var`
Expected: `var`. Yoksa DUR (T2 başlayamaz; T0 kaydındaki `B1_CONTRACT` güncellenir).

- [ ] **Step 2: Başarısız sözleşme testini yaz — `tests/test_site_web_contract.py`**

```python
"""B-2 ↔ sözleşme: TS tipi, JSON Schema ve B-2'nin sentetik fixture'ları aynı şekli taşır.

Sözleşmenin sahibi `web/contract/snapshot.schema.json`dur (B-1 T1). TS `Snapshot` tipini
elle taşır (spec §5.2); bir anahtar bir tarafta kalırsa sayfa ya sessizce boş basar ya da
derleme olmayan bir alanı okur. Bu dosya iki yönü de kırmızı yapar. Fixture'ların tam
içerik denetimi `verify-snapshot`in (B-1) işidir; burada yalnız B-2'nin dayandığı şekil,
sıralama ve `content_sha256` sınanır — `verify-snapshot` fixture'larda T10'dan beri kapıda.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from tests import site_web_fixtures

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "web/contract/snapshot.schema.json"
TS_TYPES = REPO / "web/src/lib/snapshot-types.ts"
B2_FIXTURES = (site_web_fixtures.FULL, site_web_fixtures.EMPTY)

# Şemadaki her nesne yolu → onu taşıyan TS tipi. `[]` dizi öğesidir.
TYPE_OF_PATH = {
    "": "Snapshot",
    "ledger": "Ledger",
    "ledger.anchor": "Anchor",
    "leagues[]": "League",
    "leagues[].move_distribution": "MoveDistribution",
    "teams[]": "Team",
    "matches[]": "Match",
    "matches[].h2h": "H2h",
    "matches[].h2h.opening": "Round",
    "matches[].h2h.latest": "Round",
    "matches[].h2h.closing": "Round",
    "matches[].h2h.opening.p": "Triple",
    "matches[].h2h.latest.p": "Triple",
    "matches[].h2h.closing.p": "Triple",
    "matches[].move": "Triple",
    "record": "TrackRecord",
    "record.entries[]": "RecordEntry",
    "record.summary": "RecordSummary",
}
SORT_KEYS = {
    "leagues": ("id",),
    "teams": ("league_id", "slug"),
    "matches": ("commence_time", "id"),
}

Shape = dict[str, tuple[set[str], set[str]]]  # yol → (properties, required)
_TYPE_OPEN = re.compile(r"^export type (\w+) = \{$")
_KEY_LINE = re.compile(r"^  (\w+): ([^;]+);$")


def _resolve(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        target: Any = root
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def _branches(node: dict[str, Any], root: dict[str, Any]) -> list[dict[str, Any]]:
    """Null olmayan alternatifler: `anyOf`/`oneOf` açılır, `null` ve `const: null` düşer."""
    node = _resolve(node, root)
    for key in ("anyOf", "oneOf"):
        if key in node:
            return [branch for sub in node[key] for branch in _branches(sub, root)]
    if node.get("type") == "null" or ("const" in node and node["const"] is None):
        return []
    return [node]


def _types(node: dict[str, Any]) -> list[Any]:
    kind = node.get("type")
    return kind if isinstance(kind, list) else [kind]


def schema_shape(node: dict[str, Any], root: dict[str, Any], path: str = "") -> Shape:
    shape: Shape = {}
    for branch in _branches(node, root):
        if "object" in _types(branch) or "properties" in branch:
            properties = branch.get("properties", {})
            shape[path] = (set(properties), set(branch.get("required", [])))
            for key, sub in properties.items():
                shape |= schema_shape(sub, root, f"{path}.{key}" if path else key)
        if "array" in _types(branch) or "items" in branch:
            shape |= schema_shape(branch["items"], root, f"{path}[]")
    return shape


def ts_shape(text: str) -> dict[str, set[str]]:
    """`snapshot-types.ts`in katı biçimini okur; biçim dışı her satır kırmızıdır."""
    types: dict[str, set[str]] = {}
    current: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if current is None:
            opened = _TYPE_OPEN.match(line)
            if opened:
                current = opened[1]
                types[current] = set()
            else:
                assert not line.startswith("export type"), f"satır {number}: biçim dışı tip"
            continue
        if line == "};":
            current = None
            continue
        key = _KEY_LINE.match(line)
        assert key, f"satır {number}: tip gövdesinde ayrıştırılamayan satır {line!r}"
        types[current].add(key[1])
    assert current is None, "kapanmamış tip bloğu"
    return types


def document_paths(value: Any, path: str = "") -> dict[str, list[set[str]]]:
    """Belgedeki her nesnenin anahtar kümesi, yola göre (dizi indisi `[]`e katlanır)."""
    found: dict[str, list[set[str]]] = {}
    if isinstance(value, dict):
        found.setdefault(path, []).append(set(value))
        for key, sub in value.items():
            for sub_path, keys in document_paths(sub, f"{path}.{key}" if path else key).items():
                found.setdefault(sub_path, []).extend(keys)
    elif isinstance(value, list):
        for item in value:
            for sub_path, keys in document_paths(item, f"{path}[]").items():
                found.setdefault(sub_path, []).extend(keys)
    return found


@pytest.fixture(scope="module")
def schema() -> Shape:
    assert SCHEMA.exists(), (
        f"{SCHEMA.relative_to(REPO)} yok — B-1 T1 (sözleşme) birleşmeden T2 başlamaz"
    )
    root = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return schema_shape(root, root)


def test_every_schema_object_has_a_mapped_ts_type(schema: Shape) -> None:
    assert set(schema) == set(TYPE_OF_PATH), (
        f"şemada eşlenmemiş nesne: {sorted(set(schema) - set(TYPE_OF_PATH))}; "
        f"eşlemede şemada olmayan: {sorted(set(TYPE_OF_PATH) - set(schema))}"
    )


@pytest.mark.parametrize("path", sorted(TYPE_OF_PATH))
def test_ts_type_keys_equal_schema_keys(schema: Shape, path: str) -> None:
    ts = ts_shape(TS_TYPES.read_text(encoding="utf-8"))
    properties, _ = schema[path]
    assert ts[TYPE_OF_PATH[path]] == properties, f"{path} ↔ {TYPE_OF_PATH[path]}"


def test_ts_parser_rejects_a_line_it_cannot_read() -> None:
    with pytest.raises(AssertionError, match="ayrıştırılamayan"):
        ts_shape("export type X = {\n  a: number; b: number;\n};\n")


@pytest.mark.parametrize("fixture", B2_FIXTURES, ids=lambda path: path.name)
def test_fixture_objects_fit_the_schema(schema: Shape, fixture: Path) -> None:
    document = json.loads(fixture.read_text(encoding="utf-8"))
    for path, key_sets in document_paths(document).items():
        assert path in schema, f"{fixture.name}: şemada olmayan nesne yolu {path!r}"
        properties, required = schema[path]
        for keys in key_sets:
            assert keys <= properties, f"{fixture.name} {path}: fazla {sorted(keys - properties)}"
            assert required <= keys, f"{fixture.name} {path}: eksik {sorted(required - keys)}"


def test_committed_fixtures_equal_the_generator_output() -> None:
    for path, text in site_web_fixtures.expected_files().items():
        assert path.read_text(encoding="utf-8") == text, (
            f"{path.name} üreticiden sapmış: `uv run python -m tests.site_web_fixtures`"
        )


@pytest.mark.parametrize("fixture", B2_FIXTURES, ids=lambda path: path.name)
def test_fixture_content_hash_and_order(fixture: Path) -> None:
    document = json.loads(fixture.read_text(encoding="utf-8"))
    assert document["content_sha256"] == site_web_fixtures.content_sha256(document)
    for array, keys in SORT_KEYS.items():
        rows = [tuple(row[key] for key in keys) for row in document[array]]
        assert rows == sorted(rows), f"{fixture.name}: {array} {keys} sırasında değil"
    ids = [entry["publication_id"] for entry in document["record"]["entries"]]
    assert ids == sorted(ids)


@pytest.mark.parametrize("fixture", B2_FIXTURES, ids=lambda path: path.name)
def test_fixture_record_is_internally_consistent(fixture: Path) -> None:
    record = json.loads(fixture.read_text(encoding="utf-8"))["record"]
    assert record["published"] == len(record["entries"])
    assert (record["published"] == 0) == (record["summary"] is None)
```

- [ ] **Step 3: Koştur, kırmızı**

Run: `uv run pytest -q tests/test_site_web_contract.py`
Expected: toplama hatası — `ModuleNotFoundError: No module named 'tests.site_web_fixtures'`.

- [ ] **Step 4: Fixture üreticisini yaz — `tests/site_web_fixtures.py`**

```python
"""B-2'nin sentetik anlık görüntü fixture'ları: TEK kaynak burası, JSON dosyaları bunun çıktısı.

Uydurma lig/takım adları, gerçek satır yok (spec §5.2). Dosyalar elle düzenlenmez:
`uv run python -m tests.site_web_fixtures` yeniden yazar; `test_site_web_contract.py`
depodaki dosyaların bu çıktıya bayt bayt eşit olduğunu sınar (sürüklenme bekçisi).

Kapsanan durumlar (spec §6.4/1): dolu ve boş sicil · eşik altı açılış turu (`null`) ·
mühürsüz maç (`closing: null`) · tek turlu maç · tam sayı değerli ondalık (`40.0`) ·
negatif hareket · HTML'de kaçış isteyen adlar (`&`, `'`) · Türkçe harfler · çıpa geride
(dolu) ve çıpa eşit (boş) · dışa aktarım anından önce ve sonra başlayan maçlar.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from football_edge.ledger import _canonical

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "web/fixtures"
FULL = FIXTURES / "snapshot.fixture.web-full.json"
EMPTY = FIXTURES / "snapshot.fixture.web-empty.json"
# The Odds API olay kimliğinin sabit uzunluklu öneki (spec §8.1). Uzunluk B-1'in
# `site/slugs.py` sabitidir; T10 `verify-snapshot` ile uzlaştırır.
PATH_ID_LENGTH = 12
HASHED_OUT = ("generated_at", "git_sha", "content_sha256")

Json = dict[str, Any]


def _hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _event_id(number: int) -> str:
    return hashlib.md5(f"fixture-match-{number}".encode()).hexdigest()


def content_sha256(document: Json) -> str:
    """Spec §5.2: `generated_at`, `git_sha` ve kendisi hariç gövdenin kanonik sha256'sı."""
    body = {key: value for key, value in document.items() if key not in HASHED_OUT}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _round(observed_at: str, books: int, home: float, draw: float, away: float) -> Json:
    return {"observed_at": observed_at, "books": books, "p": _triple(home, draw, away)}


def _triple(home: float, draw: float, away: float) -> Json:
    return {"home": home, "draw": draw, "away": away}


TEAMS = {
    "kz": ("Kuzeyspor", "kuzeyspor"),
    "gn": ("Güneyköy İdmanyurdu", "guneykoy-idmanyurdu"),
    "db": ("Doğu & Batı FK", "dogu-bati-fk"),
    "ob": ("O'Brien Rovers", "obrien-rovers"),
    "dc": ("Delta City", "delta-city"),
    "et": ("Epsilon Town", "epsilon-town"),
}


def _match(number: int, league: str, when: str, home: str, away: str, **rest: Any) -> Json:
    event = _event_id(number)
    (home_name, home_slug), (away_name, away_slug) = TEAMS[home], TEAMS[away]
    h2h = {"opening": rest["opening"], "latest": rest["latest"], "closing": rest["closing"]}
    return {
        "id": event,
        "league_id": league,
        "path_id": event[:PATH_ID_LENGTH],
        "slug": f"{home_slug}-vs-{away_slug}",
        "date": when[:10],
        "commence_time": when,
        "home": home_name,
        "away": away_name,
        "sealed": rest["sealed"],
        "rounds": rest["rounds"],
        "h2h": h2h,
        "move": rest["move"],
        "indexable": rest["indexable"],
    }


def _matches() -> list[Json]:
    close1 = _round("2026-09-19T13:45:00Z", 7, 48.3, 26.0, 25.7)
    close2 = _round("2026-09-20T16:15:00Z", 5, 38.0, 29.5, 32.5)
    close4 = _round("2026-09-22T19:30:00Z", 6, 28.9, 28.0, 43.1)
    only3 = _round("2026-09-23T06:00:00Z", 4, 36.1, 30.0, 33.9)
    close6 = _round("2026-09-23T16:45:00Z", 4, 42.5, 29.0, 28.5)
    matches = [
        _match(
            1,
            "xla.1",
            "2026-09-19T14:00:00Z",
            "kz",
            "gn",
            sealed=True,
            rounds=12,
            opening=_round("2026-09-16T06:00:00Z", 6, 45.7, 27.1, 27.2),
            latest=close1,
            closing=close1,
            move=_triple(2.6, -1.1, -1.5),
            indexable=True,
        ),
        # Açılış turunda 2 kitap: eşik altı → null; hareket de açılışsız → null.
        _match(
            2,
            "xla.1",
            "2026-09-20T16:30:00Z",
            "db",
            "ob",
            sealed=True,
            rounds=9,
            opening=None,
            latest=close2,
            closing=close2,
            move=None,
            indexable=True,
        ),
        # Tek tur, mühürsüz, dışa aktarım anından SONRA başlıyor.
        _match(
            3,
            "xla.1",
            "2026-09-26T18:00:00Z",
            "gn",
            "db",
            sealed=False,
            rounds=1,
            opening=only3,
            latest=only3,
            closing=None,
            move=None,
            indexable=False,
        ),
        _match(
            4,
            "xla.1",
            "2026-09-22T19:45:00Z",
            "ob",
            "kz",
            sealed=True,
            rounds=14,
            opening=_round("2026-09-19T06:00:00Z", 5, 30.2, 28.4, 41.4),
            latest=close4,
            closing=close4,
            move=_triple(-1.3, -0.4, 1.7),
            indexable=True,
        ),
        # Mühürsüz, iki turlu: hareket açılış→son.
        _match(
            5,
            "xla.1",
            "2026-09-27T13:00:00Z",
            "kz",
            "db",
            sealed=False,
            rounds=6,
            opening=_round("2026-09-21T06:00:00Z", 5, 51.0, 25.3, 23.7),
            latest=_round("2026-09-24T05:45:00Z", 5, 52.4, 24.9, 22.7),
            closing=None,
            move=_triple(1.4, -0.4, -1.0),
            indexable=True,
        ),
        # `40.0` / `30.0`: tam sayı değerli ondalık — JS `40` okur, biçim `40.0` basmalı.
        _match(
            6,
            "xlb.1",
            "2026-09-23T17:00:00Z",
            "dc",
            "et",
            sealed=True,
            rounds=5,
            opening=_round("2026-09-20T06:00:00Z", 3, 40.0, 30.0, 30.0),
            latest=close6,
            closing=close6,
            move=_triple(2.5, -1.0, -1.5),
            indexable=True,
        ),
    ]
    return sorted(matches, key=lambda match: (match["commence_time"], match["id"]))


def _leagues() -> list[Json]:
    return [
        {
            "id": "xla.1",
            "slug": "synthetic-league-alpha",
            "name": "Synthetic League Alpha",
            "country": "Testland",
            "matches": 5,
            "move_distribution": {"p10": 0.4, "p50": 1.8, "p90": 4.1},
        },
        {
            "id": "xlb.1",
            "slug": "synthetic-league-beta",
            "name": "Synthetic League Beta",
            "country": "Otherland",
            "matches": 1,
            "move_distribution": None,
        },
    ]


def _teams() -> list[Json]:
    counts = (
        ("xla.1", "kz", 3),
        ("xla.1", "gn", 2),
        ("xla.1", "db", 3),
        ("xla.1", "ob", 2),
        ("xlb.1", "dc", 1),
        ("xlb.1", "et", 1),
    )
    teams = [
        {
            "league_id": league,
            "slug": TEAMS[key][1],
            "name": TEAMS[key][0],
            "matches": count,
            "indexable": count >= 3,
        }
        for league, key, count in counts
    ]
    return sorted(teams, key=lambda team: (team["league_id"], team["slug"]))


def _full_record() -> Json:
    entries = [
        {
            "publication_id": 1,
            "match_id": _event_id(1),
            "market": "h2h",
            "outcome": "Kuzeyspor",
            "published_at": "2026-09-18T09:00:00Z",
            "published_price": 2.2,
            "publication_ledger_id": 1201,
            "closing_fair_price": 2.07,
            "clv": 6.28,
            "publication_hash": _hex("fixture-publication-1"),
        },
        {
            "publication_id": 2,
            "match_id": _event_id(4),
            "market": "h2h",
            "outcome": "Draw",
            "published_at": "2026-09-21T09:00:00Z",
            "published_price": 3.4,
            "publication_ledger_id": 1455,
            "closing_fair_price": 3.57,
            "clv": -4.76,
            "publication_hash": _hex("fixture-publication-2"),
        },
    ]
    summary = {"mean_clv": 0.76, "ci_low": -4.76, "ci_high": 6.28, "n": 2}
    return {"published": 2, "entries": entries, "summary": summary}


def _anchor(rows: int, last_id: int) -> Json:
    return {
        "file": "ledger/head-2026-09-24.txt",
        "rows": rows,
        "last_id": last_id,
        "head": _hex(f"fixture-head-{last_id}"),
    }


def build(*, full: bool) -> Json:
    document: Json = {
        "schema_version": 1,
        "generated_at": "2026-09-24T06:00:00Z",
        "git_sha": _hex("fixture-git")[:40],
        "content_sha256": "",
        "ledger": {
            "rows": 1834,
            "last_id": 1840,
            "head": _hex("fixture-head-1840"),
            "anchor": _anchor(1830, 1836) if full else _anchor(1834, 1840),
        },
        "floor": "2026-07-02T00:00:00Z",
        "leagues": _leagues(),
        "teams": _teams(),
        "matches": _matches(),
        "record": _full_record() if full else {"published": 0, "entries": [], "summary": None},
        "value_badge": None,
        "analysis": None,
    }
    document["content_sha256"] = content_sha256(document)
    return document


def render(document: Json) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def expected_files() -> dict[Path, str]:
    return {FULL: render(build(full=True)), EMPTY: render(build(full=False))}


def main() -> int:
    for path, text in expected_files().items():
        path.write_text(text, encoding="utf-8")
        sys.stdout.write(f"{path.relative_to(REPO)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Fixture'ları üret ve hash'leri doğrula**

Run: `mkdir -p web/fixtures && uv run python -m tests.site_web_fixtures && grep -h content_sha256 web/fixtures/snapshot.fixture.web-*.json`
Expected: iki yol basılır; hash'ler `21a8bcf01b07804c7b38abbd8b322bea7a50dd2562e3b888888f5a80a4b8ede7` (empty) ve
`84b758af18c8bc52930d8998f9600b4217f5d191152b73eba55a5dfc581890b3` (full). Farklıysa üretici plandan sapmıştır — düzelt.

- [ ] **Step 6: TS tipini yaz — `web/src/lib/snapshot-types.ts` (katı biçim; ayrıştırıcı testte)**

```ts
// Anlık görüntü v1'in TS karşılığı (spec §5.2). Sözleşmenin sahibi
// `web/contract/snapshot.schema.json`dur; bu dosya onu ELLE taşır.
// BİÇİM KURALI (tests/test_site_web_contract.py bu biçimi ayrıştırır):
// her tip `export type Ad = {` ile açılır, `};` ile kapanır, her satırda tek anahtar.

export type Triple = {
  home: number;
  draw: number;
  away: number;
};

export type Round = {
  observed_at: string;
  books: number;
  p: Triple;
};

export type H2h = {
  opening: Round | null;
  latest: Round | null;
  closing: Round | null;
};

export type Anchor = {
  file: string;
  rows: number;
  last_id: number;
  head: string;
};

export type Ledger = {
  rows: number;
  last_id: number;
  head: string;
  anchor: Anchor;
};

export type MoveDistribution = {
  p10: number;
  p50: number;
  p90: number;
};

export type League = {
  id: string;
  slug: string;
  name: string;
  country: string;
  matches: number;
  move_distribution: MoveDistribution | null;
};

export type Team = {
  league_id: string;
  slug: string;
  name: string;
  matches: number;
  indexable: boolean;
};

export type Match = {
  id: string;
  league_id: string;
  path_id: string;
  slug: string;
  date: string;
  commence_time: string;
  home: string;
  away: string;
  sealed: boolean;
  rounds: number;
  h2h: H2h;
  move: Triple | null;
  indexable: boolean;
};

export type RecordEntry = {
  publication_id: number;
  match_id: string;
  market: string;
  outcome: string;
  published_at: string;
  published_price: number;
  publication_ledger_id: number;
  closing_fair_price: number;
  clv: number;
  publication_hash: string;
};

export type RecordSummary = {
  mean_clv: number;
  ci_low: number;
  ci_high: number;
  n: number;
};

export type TrackRecord = {
  published: number;
  entries: RecordEntry[];
  summary: RecordSummary | null;
};

export type Snapshot = {
  schema_version: 1;
  generated_at: string;
  git_sha: string;
  content_sha256: string;
  ledger: Ledger;
  floor: string;
  leagues: League[];
  teams: Team[];
  matches: Match[];
  record: TrackRecord;
  value_badge: null;
  analysis: null;
};
```

- [ ] **Step 7: Sözleşme testini koştur**

Run: `uv run pytest -q tests/test_site_web_contract.py`
Expected: PASS — `27 passed` (mock şemayla ölçüldü: 18 yol × tip + 2 × 3 fixture + 3 tekil). **Şema spec §5.2'den farklıysa**
(B-1 bir alanı yeniden adlandırdı, ekledi ya da `$defs` düzeni `TYPE_OF_PATH`e uymuyor): sözleşmenin sahibi şemadır —
`snapshot-types.ts`, `TYPE_OF_PATH` ve üreticiyi şemaya uydur, farkı görev raporuna yaz. Fark spec'in yasakladığı bir
alan ise (model olasılığı, kitap adı/fiyatı, dolu `value_badge`) uydurma: DUR, controller'a eskale et.

- [ ] **Step 8: Yükleyicinin başarısız testini yaz — `web/src/lib/fixture.ts` ve `web/src/lib/snapshot.test.ts`**

`web/src/lib/fixture.ts`:
```ts
// Birim testlerinin ortak girdisi: B-2'nin dolu fixture'ı (tests/site_web_fixtures.py üretir).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseSnapshot } from "./snapshot.ts";
import type { Snapshot } from "./snapshot-types.ts";

export const FULL_FIXTURE = resolve(import.meta.dirname, "../../fixtures/snapshot.fixture.web-full.json");

export function fullFixtureText(): string {
  return readFileSync(FULL_FIXTURE, "utf-8");
}

export function fullFixture(): Snapshot {
  return parseSnapshot(fullFixtureText());
}
```

`web/src/lib/snapshot.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { fullFixture, fullFixtureText } from "./fixture.ts";
import { loadSnapshot, parseSnapshot, SnapshotError } from "./snapshot.ts";

type Key = string | number;

function withChange(path: readonly Key[], value: unknown): string {
  const doc: unknown = JSON.parse(fullFixtureText());
  let node = doc as Record<Key, unknown>;
  for (const key of path.slice(0, -1)) node = node[key] as Record<Key, unknown>;
  node[path[path.length - 1] as Key] = value;
  return JSON.stringify(doc);
}

const fixture = fullFixture();
const firstLeagueSlug = fixture.leagues[0]?.slug;
const firstTeamSlug = fixture.teams[0]?.slug;
const firstPathId = fixture.matches[0]?.path_id;

describe("parseSnapshot — yönlendirmenin dayandığı değişmezler", () => {
  it("B-2 fixture'ını kabul eder", () => {
    expect(fixture.matches).toHaveLength(6);
  });

  it.each([
    ["ayrılmış lig slug'ı track-record", ["leagues", 0, "slug"], "track-record"],
    ["ayrılmış lig slug'ı legal", ["leagues", 0, "slug"], "legal"],
    ["ayrılmış lig slug'ı data", ["leagues", 0, "slug"], "data"],
    ["ayrılmış takım slug'ı", ["teams", 0, "slug"], "match"],
    ["lig slug'ı çakışıyor", ["leagues", 1, "slug"], firstLeagueSlug],
    ["takım slug'ı çakışıyor", ["teams", 1, "slug"], firstTeamSlug],
    ["path_id çakışıyor", ["matches", 1, "path_id"], firstPathId],
    ["maç yok", ["matches"], []],
    ["value_badge dolu (H3)", ["value_badge"], { pick: "home" }],
    ["analysis dolu", ["analysis"], "metin"],
    ["published ≠ girdi sayısı", ["record", "published"], 3],
    ["summary tutarsız", ["record", "summary"], null],
    ["schema_version", ["schema_version"], 2],
    ["maçın ligi yok", ["matches", 0, "league_id"], "yok.1"],
  ] as const)("%s → SnapshotError", (_, path, value) => {
    expect(() => parseSnapshot(withChange(path, value))).toThrow(SnapshotError);
  });

  it("SITE_SNAPSHOT yoksa varsayılan dosyaya DÜŞMEZ, adıyla düşer", () => {
    expect(() => loadSnapshot({})).toThrow(/SITE_SNAPSHOT tanımlı değil/);
  });
});
```

Run: `pnpm -C web exec vitest run src/lib/snapshot.test.ts`
Expected: FAIL — `Failed to load url ./snapshot.ts`.

- [ ] **Step 9: Yükleyiciyi yaz — `web/src/lib/snapshot.ts`**

```ts
// Anlık görüntünün derleme anı okuyucusu. Node DB'ye bağlanmaz (H5): tek girdi,
// `SITE_SNAPSHOT` ortam değişkeninin gösterdiği JSON dosyasıdır. Varsayılan dosya YOK —
// yanlış ya da eksik yol adıyla düşer; sessizce fixture'a dönen bir derleme gerçek
// yayını sentetik veriyle üretebilirdi.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { RESERVED_LEAGUE_SLUGS, RESERVED_TEAM_SLUGS } from "../../site.config.ts";
import type { League, Match, Snapshot, Team } from "./snapshot-types.ts";

export class SnapshotError extends Error {}

function fail(message: string): never {
  throw new SnapshotError(`anlık görüntü reddedildi: ${message}`);
}

function unique(values: readonly string[], what: string): void {
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) fail(`${what} çakışıyor: ${value}`);
    seen.add(value);
  }
}

// Tam şema denetimi `verify-snapshot`in (Python, B-1) işidir. Burada yalnız sitenin
// YÖNLENDİRMESİNİN dayandığı değişmezler sınanır: çakışan yol iki kaydı tek sayfaya yazar.
export function parseSnapshot(text: string): Snapshot {
  const snapshot = JSON.parse(text) as Snapshot;
  if (snapshot.schema_version !== 1) fail(`schema_version ${String(snapshot.schema_version)}`);
  if (snapshot.value_badge !== null) fail("value_badge null değil (H3)");
  if (snapshot.analysis !== null) fail("analysis null değil (§8.6)");
  if (snapshot.matches.length === 0) fail("maç yok — dışa aktarıcı bunu zaten reddetmeliydi");
  for (const league of snapshot.leagues) {
    if (RESERVED_LEAGUE_SLUGS.includes(league.slug)) fail(`ayrılmış lig slug'ı: ${league.slug}`);
  }
  for (const team of snapshot.teams) {
    if (RESERVED_TEAM_SLUGS.includes(team.slug)) fail(`ayrılmış takım slug'ı: ${team.slug}`);
  }
  unique(snapshot.leagues.map((league) => league.slug), "lig slug'ı");
  unique(snapshot.teams.map((team) => `${team.league_id}/${team.slug}`), "takım slug'ı");
  unique(snapshot.matches.map((match) => `${match.league_id}/${match.path_id}`), "path_id");
  const leagueIds = new Set(snapshot.leagues.map((league) => league.id));
  for (const match of snapshot.matches) {
    if (!leagueIds.has(match.league_id)) fail(`maçın ligi yok: ${match.id}`);
  }
  const { record } = snapshot;
  if (record.published !== record.entries.length) fail("record.published ≠ girdi sayısı");
  if ((record.published === 0) !== (record.summary === null)) fail("record.summary tutarsız");
  return snapshot;
}

let cached: Snapshot | undefined;

export function loadSnapshot(env: Record<string, string | undefined> = process.env): Snapshot {
  if (cached) return cached;
  const path = env.SITE_SNAPSHOT;
  if (!path) fail("SITE_SNAPSHOT tanımlı değil");
  cached = parseSnapshot(readFileSync(resolve(path), "utf-8"));
  return cached;
}

export function leagueById(snapshot: Snapshot, id: string): League {
  return snapshot.leagues.find((league) => league.id === id) ?? fail(`lig yok: ${id}`);
}

export function teamsOf(snapshot: Snapshot, league: League): Team[] {
  return snapshot.teams.filter((team) => team.league_id === league.id);
}

export function matchesOf(snapshot: Snapshot, league: League): Match[] {
  return snapshot.matches.filter((match) => match.league_id === league.id);
}

export function matchesOfTeam(snapshot: Snapshot, team: Team): Match[] {
  return snapshot.matches.filter(
    (match) =>
      match.league_id === team.league_id && (match.home === team.name || match.away === team.name),
  );
}

export function teamByName(snapshot: Snapshot, leagueId: string, name: string): Team | undefined {
  return snapshot.teams.find((team) => team.league_id === leagueId && team.name === name);
}
```

- [ ] **Step 10: Yeşil + tip denetimi (`satisfies` yerine tip atamalı yükleyici)**

Run: `pnpm -C web exec vitest run && pnpm -C web exec tsc --noEmit`
Expected: vitest `18 passed` (site-config 2 + snapshot 16); tsc çıktısız. Not: spec'in "fixture `satisfies Snapshot`"
kontrolü bu planda iki parçadır — JSON'un ŞEKLİ pytest'te şemaya karşı (Step 7), TS tipinin şemaya eşitliği pytest'te;
JSON içe aktarmak (`import … with { type: "json" }` + `satisfies`) fixture'ı derleme paketine sokardı (Açık sorular/6).

- [ ] **Step 11: Mutasyon kanıtları (her biri kırmızı, sonra geri; `PYTHONDONTWRITEBYTECODE=1`)**

1. `snapshot-types.ts` `Round` tipinden `  books: number;` satırını SİL → `uv run pytest -q tests/test_site_web_contract.py`
   → `test_ts_type_keys_equal_schema_keys[matches[].h2h.opening]` (ve latest/closing) FAIL. Satırı geri koy.
2. `web/fixtures/snapshot.fixture.web-full.json`de ilk `45.7`yi `45.8` yap → `test_committed_fixtures_equal_the_generator_output`
   ve `test_fixture_content_hash_and_order[…full…]` FAIL. Geri al.
3. `tests/site_web_fixtures.py` `_teams()` sonundaki `sorted(...)`ı kaldır (listeyi doğrudan döndür) ve fixture'ları yeniden
   üret → `test_fixture_content_hash_and_order` "teams ('league_id', 'slug') sırasında değil" FAIL. Geri al, yeniden üret,
   `git diff --stat -- web/fixtures tests/site_web_fixtures.py` boş.
4. `snapshot.ts`de `RESERVED_LEAGUE_SLUGS` döngüsünü yorum satırına al → vitest "ayrılmış lig slug'ı track-record" (ve
   legal, data) FAIL. Geri al.
5. `loadSnapshot`ta `if (!path) fail(...)`ı `const path = env.SITE_SNAPSHOT ?? "fixtures/snapshot.fixture.web-full.json";`
   yap → "SITE_SNAPSHOT yoksa varsayılan dosyaya DÜŞMEZ" FAIL (Review Focus 5). Geri al.

- [ ] **Step 12: Tam kapı**

`verify.sh` (log `b2-t2-gate.log`) + WEB-KAPI. Expected: taban PASS; pytest yeni 27 + 14 testle yeşil.

- [ ] **Step 13: Commit**

```bash
git add tests/site_web_fixtures.py tests/test_site_web_contract.py web/fixtures/snapshot.fixture.web-full.json \
  web/fixtures/snapshot.fixture.web-empty.json web/src/lib/snapshot-types.ts web/src/lib/snapshot.ts \
  web/src/lib/fixture.ts web/src/lib/snapshot.test.ts
git commit -m "feat: anlık görüntü sözleşmesinin web tarafı — TS tipi, yükleyici, sentetik fixture'lar (B-2 T2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Biçimleme sözleşmesi, `data-fe` anahtarı, arayüz sözlükleri

**Kademe:** K2 (biçim H6c'nin tek yeridir; T9'un K1 incelemesi onu yeniden sınar) · **Spec:** §5.4, H6, §8.3, §6.2 (boş
sicil metni — AK2 onay kapsamında), §7

**Files:**
- Create: `web/src/lib/format.ts`, `web/src/lib/format.test.ts`, `web/src/lib/fe.ts`, `web/src/i18n/en.json`,
  `web/src/i18n/tr.json`, `web/src/i18n/dict.ts`, `web/src/i18n/dict.test.ts`

**Interfaces:**
- Consumes: `Lang` (T1).
- Produces:
  ```ts
  // format.ts
  export type NumberKind = "pct1" | "pp1" | "pct2" | "price2" | "int";
  export class FormatError extends Error {}
  export function formatNumber(value: number, kind: NumberKind, lang: Lang): string;
  //   en: 45.7 → "45.7%", -1.3 pp1 → "-1.3 pp", 2.2 price2 → "2.20"; tr: "%45,7", "-1,3 puan", "2,20"
  // fe.ts
  export type FeEntity = "match" | "league" | "team" | "ledger" | "record" | "entry" | "root";
  export function feKey(entity: FeEntity, id: string, path: string): string;   // "<varlık>:<kimlik>:<yol>"
  export const teamKey: (leagueId: string, slug: string) => string;            // "<lig>/<slug>"
  // i18n/dict.ts
  export type DictKey = keyof typeof en;   export const DICTIONARIES: Record<Lang, Record<DictKey, string>>;
  export function t(lang: Lang, key: DictKey): string;
  ```
  Birim sözleşmesi (T9 bu dosyayı ÇAĞIRARAK sınar): yüzde `pct1`/`pct2` (en sonek `%`, tr önek `%`), yüzde puan `pp1` (en
  `pp`, tr `puan`), fiyat `price2` birimsiz, `int` birimsiz ve binlik ayraçsız.

- [ ] **Step 1: Başarısız testi yaz — `web/src/lib/format.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import { FormatError, formatNumber } from "./format.ts";

describe("formatNumber — yalnız ayraç ve birim, yuvarlama yok (spec §5.4)", () => {
  it.each([
    [45.7, "pct1", "en", "45.7%"],
    [45.7, "pct1", "tr", "%45,7"],
    [40, "pct1", "en", "40.0%"],
    [-1.3, "pp1", "en", "-1.3 pp"],
    [-1.3, "pp1", "tr", "-1,3 puan"],
    [-0, "pp1", "en", "0.0 pp"],
    [2.2, "price2", "en", "2.20"],
    [3.57, "price2", "tr", "3,57"],
    [-4.76, "pct2", "tr", "%-4,76"],
    [1834, "int", "en", "1834"],
  ] as const)("%s %s %s → %s", (value, kind, lang, expected) => {
    expect(formatNumber(value, kind, lang)).toBe(expected);
  });

  it.each([
    [45.75, "pct1"],
    [2.205, "price2"],
    [1.5, "int"],
    [1e-7, "pct1"],
    [Number.NaN, "pct1"],
    [Number.POSITIVE_INFINITY, "int"],
  ] as const)("%s (%s) sözleşme dışı → FormatError, sessiz yuvarlama yok", (value, kind) => {
    expect(() => formatNumber(value, kind, "en")).toThrow(FormatError);
  });
});
```

- [ ] **Step 2: Koştur, kırmızı**

Run: `pnpm -C web exec vitest run src/lib/format.test.ts`
Expected: FAIL — `Failed to load url ./format.ts`.

- [ ] **Step 3: `web/src/lib/format.ts`**

```ts
// Biçimleme sözleşmesi (spec §5.4): sayı anlık görüntüde GÖRÜNTÜ hassasiyetindedir.
// Bu fonksiyon yalnız ondalık ayracı ve birim ekler; yuvarlamaz, çarpmaz, toplamaz.
// Hassasiyetten fazla ondalık taşıyan değer sözleşme ihlalidir → hata (sessiz yuvarlama yok).
import type { Lang } from "../../site.config.ts";

export type NumberKind = "pct1" | "pp1" | "pct2" | "price2" | "int";

const DECIMALS: Record<NumberKind, number> = { pct1: 1, pp1: 1, pct2: 2, price2: 2, int: 0 };
const SEPARATOR: Record<Lang, string> = { en: ".", tr: "," };

export class FormatError extends Error {}

function digits(value: number, decimals: number, lang: Lang): string {
  if (!Number.isFinite(value)) throw new FormatError(`sonlu olmayan sayı: ${value}`);
  const text = String(value);
  if (/e/i.test(text)) throw new FormatError(`üslü gösterim: ${text}`);
  const negative = text.startsWith("-");
  const [whole, fraction = ""] = (negative ? text.slice(1) : text).split(".");
  if (fraction.length > decimals) {
    throw new FormatError(`${text} görüntü hassasiyetinden (${decimals}) fazla ondalık taşıyor`);
  }
  const padded = decimals === 0 ? "" : SEPARATOR[lang] + fraction.padEnd(decimals, "0");
  return (negative ? "-" : "") + whole + padded;
}

export function formatNumber(value: number, kind: NumberKind, lang: Lang): string {
  const number = digits(value, DECIMALS[kind], lang);
  if (kind === "pct1" || kind === "pct2") return lang === "tr" ? `%${number}` : `${number}%`;
  if (kind === "pp1") return lang === "tr" ? `${number} puan` : `${number} pp`;
  return number;
}
```

- [ ] **Step 4: Yeşil**

Run: `pnpm -C web exec vitest run src/lib/format.test.ts`
Expected: `16 passed`.

- [ ] **Step 5: `web/src/lib/fe.ts`**

```ts
// `data-fe` anahtar dilbilgisi (spec H6c): `<varlık>:<kimlik>:<noktalı yol>`.
// Sayfa bu anahtarı basar, çıktı tarayıcısı kendi beklenen kümesini BAĞIMSIZ kurar ve
// değeri anlık görüntüden bu yolla çözer. Kimliği olmayan varlıkta kimlik `-`dir.
export type FeEntity = "match" | "league" | "team" | "ledger" | "record" | "entry" | "root";

export function feKey(entity: FeEntity, id: string, path: string): string {
  return `${entity}:${id}:${path}`;
}

export const teamKey = (leagueId: string, slug: string): string => `${leagueId}/${slug}`;
```

- [ ] **Step 6: Sözlük testini yaz — `web/src/i18n/dict.test.ts`, koştur, kırmızı**

```ts
import { describe, expect, it } from "vitest";
import en from "./en.json" with { type: "json" };
import tr from "./tr.json" with { type: "json" };

describe("sözlükler (spec §8.3)", () => {
  it("tr ve en aynı anahtar kümesini taşır, boş metin yok", () => {
    expect(Object.keys(tr).sort()).toEqual(Object.keys(en).sort());
    for (const text of [...Object.values(en), ...Object.values(tr)]) expect(text.trim()).not.toBe("");
  });

  it("boş sicil metni spec §6.2'deki cümledir (AK2 onay kapsamında)", () => {
    expect(tr["record.emptyExplain"]).toBe(
      "Temel modelimiz kapanış piyasasını geçmediği için henüz tahmin yayımlamıyoruz. Tahmin yayını, önceden kaydedilecek bir kapanış değeri (CLV) ölçütü geçildiğinde başlayacak; o güne kadar defter oranları ve kapanışları kaydetmeye devam ediyor.",
    );
  });

  it("hiçbir arayüz metni 'yakında' vaadi ya da value önerisi taşımaz", () => {
    const all = [...Object.values(en), ...Object.values(tr)].join("\n").toLowerCase();
    for (const banned of ["yakında", "coming soon", "value bet", "tip of the day", "günün tahmini"]) {
      expect(all).not.toContain(banned);
    }
  });
});
```

Run: `pnpm -C web exec vitest run src/i18n/dict.test.ts`
Expected: FAIL — `./en.json` yüklenemiyor.

- [ ] **Step 7: Sözlükler ve erişimci**

`web/src/i18n/en.json`:
```json
{
  "nav.home": "Home",
  "nav.trackRecord": "Track record",
  "nav.legal": "Legal",
  "age.title": "This site is for adults (18+) only.",
  "age.body": "Content concerns betting markets. Please confirm that you are 18 or older.",
  "age.confirm": "I am 18 or older",
  "age.leave": "Leave",
  "age.strip": "18+ only. This site does not accept bets and does not link to bookmakers.",
  "footer.notAdvice": "Information only. Probabilities are not guarantees; past performance does not predict future results.",
  "footer.responsible": "Gambling can be addictive. Please play responsibly.",
  "home.title": "Market consensus and a public track record",
  "home.intro": "We show vig-free market consensus probabilities derived from a hash-chained odds ledger. This is not betting advice and we publish no value picks.",
  "home.leagues": "Leagues",
  "home.trackRecordLink": "See the track record and ledger status",
  "league.country": "Country",
  "league.matches": "Matches in the record",
  "league.moveTitle": "How much did the market move? (opening → closing, absolute, percentage points)",
  "league.p10": "10th percentile",
  "league.p50": "Median",
  "league.p90": "90th percentile",
  "league.moveTooFew": "Not enough matches yet to show the distribution.",
  "league.teams": "Teams",
  "league.matchList": "Matches",
  "team.league": "League",
  "team.matches": "Matches in the record",
  "team.matchList": "Matches",
  "match.kickoff": "Kick-off",
  "match.consensus": "Market consensus (vig-free, averaged over complete bookmakers)",
  "match.round": "Snapshot",
  "match.opening": "Opening",
  "match.latest": "Latest",
  "match.closing": "Closing",
  "match.draw": "Draw",
  "match.books": "Bookmakers",
  "match.insufficient": "Not enough bookmakers",
  "match.awaitingClose": "Awaiting close",
  "match.rounds": "Observed snapshots",
  "match.move": "Move from opening to closing (or latest)",
  "match.noMove": "No move to show.",
  "match.status": "Status",
  "match.sealed": "Closing recorded",
  "match.pending": "Pending",
  "record.title": "Track record",
  "record.published": "Published predictions",
  "record.emptyExplain": "Our base model has not beaten the closing market, so we do not publish predictions yet. Publishing will start once a closing line value (CLV) criterion, registered in advance, is passed; until then the ledger keeps recording odds and closing prices.",
  "record.tableCaption": "Published predictions",
  "record.colTime": "Published at",
  "record.colMatch": "Match",
  "record.colMarket": "Market",
  "record.colOutcome": "Outcome",
  "record.colPrice": "Published price",
  "record.colFair": "Closing fair price",
  "record.colClv": "CLV",
  "record.colLedger": "Ledger row",
  "record.colHash": "Publication hash",
  "record.summaryTitle": "Summary",
  "record.summaryN": "Count",
  "record.summaryMean": "Mean CLV",
  "record.summaryCi": "Confidence interval",
  "record.ledgerTitle": "Ledger status",
  "record.head": "Chain head",
  "record.rows": "Rows",
  "record.lastId": "Last id",
  "record.exportedAt": "Snapshot taken at",
  "record.anchorTitle": "Latest public anchor",
  "record.anchorMatches": "The ledger matches the anchor.",
  "record.anchorBehindBefore": "The latest anchor",
  "record.anchorBehindMiddle": "covers the ledger up to row",
  "record.anchorBehindAfter": "; later rows will be covered by the next seal round's anchor.",
  "record.anchorHistory": "Anchor history",
  "record.contentHash": "Snapshot content hash",
  "record.commitment": "Until the snapshot file is published, this hash is a commitment, not a verification: nobody can recompute it today; if the file is released later, it can be verified on that day.",
  "record.howTitle": "How can this be verified — and where it stops",
  "record.limit1": "The chain is linear: showing that a row belongs to the head requires every row after it. Today we publish the anchors' git history and the snapshot hash. A third party cannot verify the chain from genesis, because ledger rows carry bookmaker names and prices, which we do not publish.",
  "record.limit2": "Git history is not a trusted timestamp: the repository owner could rewrite it, and commit dates are the bot's own claim. A contradiction can only be caught with an independent mirror or GitHub's event log.",
  "record.limit3": "Recomputing a row's hash requires the canonical JSON recipe (float text for prices, UTC ISO timestamps, sorted keys, compact separators, non-ASCII kept).",
  "legal.draft": "TASLAK — avukat onayı bekler",
  "legal.terms": "Terms of use",
  "legal.privacy": "Privacy notice",
  "legal.cookies": "Cookies and local storage",
  "legal.responsible-gambling": "Responsible gambling"
}
```

`web/src/i18n/tr.json`:
```json
{
  "nav.home": "Ana sayfa",
  "nav.trackRecord": "Sicil",
  "nav.legal": "Yasal",
  "age.title": "Bu site yalnız yetişkinler (18+) içindir.",
  "age.body": "İçerik bahis piyasalarıyla ilgilidir. Lütfen 18 yaşından büyük olduğunuzu onaylayın.",
  "age.confirm": "18 yaşından büyüğüm",
  "age.leave": "Çıkış",
  "age.strip": "Yalnız 18+. Bu site bahis kabul etmez ve bahis sitelerine bağlantı vermez.",
  "footer.notAdvice": "Yalnız bilgi amaçlıdır. Olasılıklar garanti değildir; geçmiş performans geleceği göstermez.",
  "footer.responsible": "Bahis bağımlılık yapabilir. Lütfen sorumlu davranın.",
  "home.title": "Piyasa konsensüsü ve herkese açık sicil",
  "home.intro": "Hash zincirli bir oran defterinden türetilen, vig'i temizlenmiş piyasa konsensüs olasılıklarını gösteriyoruz. Bu bir bahis tavsiyesi değildir ve value önerisi yayımlamıyoruz.",
  "home.leagues": "Ligler",
  "home.trackRecordLink": "Sicili ve defter durumunu gör",
  "league.country": "Ülke",
  "league.matches": "Kayıttaki maç",
  "league.moveTitle": "Piyasa ne kadar hareket etti? (açılış → kapanış, mutlak, yüzde puan)",
  "league.p10": "10. yüzdelik",
  "league.p50": "Medyan",
  "league.p90": "90. yüzdelik",
  "league.moveTooFew": "Dağılımı göstermek için henüz yeterli maç yok.",
  "league.teams": "Takımlar",
  "league.matchList": "Maçlar",
  "team.league": "Lig",
  "team.matches": "Kayıttaki maç",
  "team.matchList": "Maçlar",
  "match.kickoff": "Başlama",
  "match.consensus": "Piyasa konsensüsü (vig'i temizlenmiş, tam kitapların ortalaması)",
  "match.round": "Tur",
  "match.opening": "Açılış",
  "match.latest": "Son",
  "match.closing": "Kapanış",
  "match.draw": "Beraberlik",
  "match.books": "Kitap sayısı",
  "match.insufficient": "Yetersiz kitap",
  "match.awaitingClose": "Kapanış bekleniyor",
  "match.rounds": "Gözlenen tur",
  "match.move": "Açılıştan kapanışa (yoksa sona) hareket",
  "match.noMove": "Gösterilecek hareket yok.",
  "match.status": "Durum",
  "match.sealed": "Kapanış kaydedildi",
  "match.pending": "Bekleniyor",
  "record.title": "Sicil",
  "record.published": "Yayınlanmış tahmin",
  "record.emptyExplain": "Temel modelimiz kapanış piyasasını geçmediği için henüz tahmin yayımlamıyoruz. Tahmin yayını, önceden kaydedilecek bir kapanış değeri (CLV) ölçütü geçildiğinde başlayacak; o güne kadar defter oranları ve kapanışları kaydetmeye devam ediyor.",
  "record.tableCaption": "Yayınlanmış tahminler",
  "record.colTime": "Yayın anı",
  "record.colMatch": "Maç",
  "record.colMarket": "Market",
  "record.colOutcome": "Sonuç",
  "record.colPrice": "Yayın oranı",
  "record.colFair": "Kapanış adil oranı",
  "record.colClv": "CLV",
  "record.colLedger": "Defter satırı",
  "record.colHash": "Yayın hash'i",
  "record.summaryTitle": "Özet",
  "record.summaryN": "Sayı",
  "record.summaryMean": "Ortalama CLV",
  "record.summaryCi": "Güven aralığı",
  "record.ledgerTitle": "Defter durumu",
  "record.head": "Zincir başı",
  "record.rows": "Satır",
  "record.lastId": "Son id",
  "record.exportedAt": "Anlık görüntü anı",
  "record.anchorTitle": "En yeni kamu çıpası",
  "record.anchorMatches": "Defter çıpa ile eşleşiyor.",
  "record.anchorBehindBefore": "Son çıpa",
  "record.anchorBehindMiddle": "defteri şu satıra kadar kapsıyor:",
  "record.anchorBehindAfter": "; sonrası sonraki mühür turunun çıpasında.",
  "record.anchorHistory": "Çıpa geçmişi",
  "record.contentHash": "Anlık görüntü içerik hash'i",
  "record.commitment": "Anlık görüntü dosyası yayımlanmadıkça gösterilen hash bir doğrulama değil taahhüttür: bugün kimse onu yeniden hesaplayamaz; dosya sonradan açıklanırsa o gün doğrulanır.",
  "record.howTitle": "Nasıl doğrulanır — ve nerede durur",
  "record.limit1": "Zincir doğrusaldır: bir satırın başa bağlandığını göstermek ondan sonraki bütün satırları ister. Bugün yayımlanan: çıpaların git geçmişi ve anlık görüntü hash'i. Defter satırları kitap adı ve kitap fiyatı taşıdığı ve bunları yayımlamadığımız için üçüncü kişi zinciri başlangıcından doğrulayamaz.",
  "record.limit2": "Git geçmişi güvenilir bir zaman damgası değildir: depo sahibi geçmişi yeniden yazabilir, commit tarihi botun kendi beyanıdır. Çelişki ancak bağımsız bir ayna ya da GitHub'ın olay kaydıyla yakalanır.",
  "record.limit3": "Bir satırın hash'ini yeniden hesaplamak kanonik JSON tarifini ister (fiyatlar için ondalık metin, UTC ISO zaman damgaları, sıralı anahtarlar, sıkışık ayırıcılar, ASCII dışı karakterler korunur).",
  "legal.draft": "TASLAK — avukat onayı bekler",
  "legal.terms": "Kullanım koşulları",
  "legal.privacy": "KVKK aydınlatma metni ve gizlilik",
  "legal.cookies": "Çerezler ve yerel depolama",
  "legal.responsible-gambling": "Sorumlu bahis"
}
```

`web/src/i18n/dict.ts`:
```ts
// Arayüz sözlükleri (spec §8.3): kütüphane yok, tipli erişimci. Anahtar kümesi `en`
// sözlüğünden türetilir; `tr` aynı kümeyi taşımak zorundadır (dict.test.ts). Veri
// dilden bağımsızdır — yalnız arayüz metni çevrilir.
import type { Lang } from "../../site.config.ts";
import en from "./en.json" with { type: "json" };
import tr from "./tr.json" with { type: "json" };

export type DictKey = keyof typeof en;

export const DICTIONARIES: Record<Lang, Record<DictKey, string>> = { en, tr };

export function t(lang: Lang, key: DictKey): string {
  return DICTIONARIES[lang][key];
}
```

- [ ] **Step 8: Yeşil + tip**

Run: `pnpm -C web exec vitest run && pnpm -C web exec tsc --noEmit`
Expected: vitest `37 passed` (2 + 16 + 16 + 3); tsc çıktısız.

- [ ] **Step 9: Mutasyon kanıtları**

1. `format.ts` `digits` gövdesini `return value.toFixed(decimals).replace(".", SEPARATOR[lang]);` yap →
   `45.75 (pct1) sözleşme dışı` ve `2.205 (price2)` testleri FAIL (sessiz yuvarlama). Geri al.
2. `digits`de `fraction.padEnd(decimals, "0")` → `fraction` → `40 pct1 en → 40.0%` ve `2.2 price2 → 2.20` FAIL (Review
   Focus 2). Geri al.
3. `tr.json`dan `"match.noMove"` satırını sil → dict testi "aynı anahtar kümesi" FAIL ve `tsc` `DICTIONARIES` atamasında
   hata verir. Geri al.
4. `tr.json` `record.emptyExplain` metninde "kapanış piyasasını" → "kapanış oranlarını" → "boş sicil metni spec §6.2'deki
   cümledir" FAIL. Geri al; `git diff --stat -- web/src` boş.

- [ ] **Step 10: Tam kapı** — `verify.sh` (`b2-t3-gate.log`) + WEB-KAPI; taban PASS.

- [ ] **Step 11: Commit**

```bash
git add web/src/lib/format.ts web/src/lib/format.test.ts web/src/lib/fe.ts web/src/i18n/en.json web/src/i18n/tr.json \
  web/src/i18n/dict.ts web/src/i18n/dict.test.ts
git commit -m "feat: biçimleme sözleşmesi, data-fe anahtarı ve arayüz sözlükleri (B-2 T3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: URL şeması, hreflang, schema.org oluşturucuları, sayfa üst verisi

**Kademe:** K2 · **Spec:** §8.1, §8.3, §8.4, §9, H7

**Files:**
- Create: `web/src/lib/routes.ts`, `web/src/lib/hreflang.ts`, `web/src/lib/jsonld.ts`, `web/src/lib/meta.ts`,
  `web/src/lib/params.ts`, `web/src/lib/routes.test.ts`, `web/src/lib/jsonld.test.ts`, `web/src/lib/meta.test.ts`

**Interfaces:**
- Consumes: `site.config.ts` (T1), `snapshot-types.ts`, `fixture.ts` (T2).
- Produces:
  ```ts
  // routes.ts
  export const homePath: (lang: Lang) => string;           // "/en/"
  export const trackRecordPath: (lang: Lang) => string;    // "/en/track-record/"
  export const legalPath: (lang: Lang, doc: LegalDoc) => string;
  export const leaguePath: (lang: Lang, league: League) => string;
  export function teamPath(lang: Lang, league: League, team: Team): string;
  export function matchStem(lang: Lang, league: League, match: Match): string;   // ".../match/<path_id>/"
  export function matchPath(lang: Lang, league: League, match: Match): string;   // stem + "<slug>/"
  export const absoluteUrl: (path: string) => string;      // SITE_URL + path
  // hreflang.ts
  export type Alternates = { canonical: string; languages: Record<string, string> };
  export function alternatesFor(lang: Lang, pathOf: (lang: Lang) => string): Alternates;
  // jsonld.ts
  export type JsonLd = Record<string, unknown>; export type Crumb = { name: string; path: string };
  export function websiteLd(lang: Lang, homePath: string): JsonLd; export function organizationLd(): JsonLd;
  export function leagueLd(league: League, path: string): JsonLd;
  export function teamLd(team: Team, league: League, path: string): JsonLd;
  export function matchLd(match: Match, league: League, path: string, generatedAt: string): JsonLd;
  export function breadcrumbLd(crumbs: readonly Crumb[]): JsonLd;
  export function pageLd(nodes: readonly JsonLd[]): JsonLd;       // {"@context", "@graph"} — sayfa başına TEK blok
  export function serializeLd(value: JsonLd): string;             // `<` → <
  // meta.ts
  export function pageMetadata(lang: Lang, pathOf: (lang: Lang) => string, title: string, recordIndexable: boolean): Metadata;
  // params.ts (bulunamazsa notFound())
  export function langOf(value: string): Lang;
  export function leagueOf(snapshot: Snapshot, slug: string): League;
  export function teamOf(snapshot: Snapshot, league: League, slug: string): Team;
  export function matchOf(snapshot: Snapshot, league: League, pathId: string, slug: string): Match;
  ```

- [ ] **Step 1: Başarısız testleri yaz**

`web/src/lib/routes.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { DEFAULT_LANG, SITE_URL } from "../../site.config.ts";
import { fullFixture } from "./fixture.ts";
import { alternatesFor } from "./hreflang.ts";
import { leaguePath, matchPath, matchStem, teamPath } from "./routes.ts";

const snapshot = fullFixture();
const [league] = snapshot.leagues;
const match = snapshot.matches[0];
const team = snapshot.teams[0];

describe("URL şeması (spec §8.1)", () => {
  it("maç yolu kimlik taşır, tarih taşımaz; isim bölütü sonda", () => {
    if (!league || !match) throw new Error("fixture boş");
    expect(match.id.startsWith(match.path_id)).toBe(true);
    expect(matchPath("en", league, match)).toBe(
      `/en/synthetic-league-alpha/match/${match.path_id}/kuzeyspor-vs-guneykoy-idmanyurdu/`,
    );
    expect(matchStem("tr", league, match)).toBe(`/tr/synthetic-league-alpha/match/${match.path_id}/`);
    expect(matchPath("en", league, match)).not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  it("takım ve lig yolları", () => {
    if (!league || !team) throw new Error("fixture boş");
    expect(leaguePath("tr", league)).toBe("/tr/synthetic-league-alpha/");
    expect(teamPath("en", league, team)).toBe("/en/synthetic-league-alpha/dogu-bati-fk/");
  });
});

describe("hreflang (spec §8.3)", () => {
  it("bütün diller + x-default, kanonik kendi URL'si", () => {
    if (!league) throw new Error("fixture boş");
    const result = alternatesFor("tr", (lang) => leaguePath(lang, league));
    expect(result.canonical).toBe(`${SITE_URL}/tr/synthetic-league-alpha/`);
    expect(result.languages).toEqual({
      en: `${SITE_URL}/en/synthetic-league-alpha/`,
      tr: `${SITE_URL}/tr/synthetic-league-alpha/`,
      "x-default": `${SITE_URL}/${DEFAULT_LANG}/synthetic-league-alpha/`,
    });
  });
});
```

`web/src/lib/jsonld.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { fullFixture } from "./fixture.ts";
import { breadcrumbLd, matchLd, pageLd, serializeLd } from "./jsonld.ts";

const snapshot = fullFixture();
const league = snapshot.leagues[0];
const byId = (n: number) => snapshot.matches[n];

describe("schema.org (spec §9)", () => {
  it("geçmiş maçta eventStatus YOK, gelecek maçta EventScheduled", () => {
    const past = byId(0);
    const future = snapshot.matches.find((match) => match.commence_time > snapshot.generated_at);
    if (!league || !past || !future) throw new Error("fixture boş");
    expect(matchLd(past, league, "/x/", snapshot.generated_at)).not.toHaveProperty("eventStatus");
    expect(matchLd(future, league, "/x/", snapshot.generated_at).eventStatus).toBe(
      "https://schema.org/EventScheduled",
    );
  });

  it("maç düğümü oran, teklif, konum taşımaz", () => {
    const match = byId(0);
    if (!league || !match) throw new Error("fixture boş");
    const node = matchLd(match, league, "/x/", snapshot.generated_at);
    for (const banned of ["offers", "location", "odds"]) expect(node).not.toHaveProperty(banned);
    expect(node["@type"]).toBe("SportsEvent");
  });

  it("tek blok: @graph, `<` kaçışlı", () => {
    const text = serializeLd(pageLd([breadcrumbLd([{ name: "</script><x>", path: "/en/" }])]));
    expect(text).not.toContain("</script>");
    expect(JSON.parse(text)["@graph"][0].itemListElement[0].name).toBe("</script><x>");
  });
});
```

`web/src/lib/meta.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { SITE_URL } from "../../site.config.ts";
import { pageMetadata } from "./meta.ts";
import { homePath } from "./routes.ts";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("pageMetadata (H7, spec §8.4)", () => {
  it("bayrak kapalıyken kayıt indekslenebilir olsa da noindex", () => {
    vi.stubEnv("SITE_INDEXABLE", "");
    expect(pageMetadata("en", homePath, "t", true).robots).toEqual({ index: false });
  });

  it("bayrak açıkken kaydın indexable'ına göre", () => {
    vi.stubEnv("SITE_INDEXABLE", "1");
    expect(pageMetadata("en", homePath, "t", true).robots).toBeUndefined();
    expect(pageMetadata("en", homePath, "t", false).robots).toEqual({ index: false });
  });

  it("kanonik ve hreflang her sayfada", () => {
    const meta = pageMetadata("tr", homePath, "t", true);
    expect(meta.alternates?.canonical).toBe(`${SITE_URL}/tr/`);
    expect(Object.keys(meta.alternates?.languages ?? {}).sort()).toEqual(["en", "tr", "x-default"]);
  });
});
```

- [ ] **Step 2: Koştur, kırmızı**

Run: `pnpm -C web exec vitest run src/lib/routes.test.ts src/lib/jsonld.test.ts src/lib/meta.test.ts`
Expected: FAIL — üç dosya da modül yükleyemez.

- [ ] **Step 3: Uygulama**

`web/src/lib/routes.ts`:
```ts
// URL şeması (spec §8.1, AK20 b) — TEK kaynak: sayfalar, site haritası, `_redirects` ve
// çıktı tarayıcısı yolu buradan kurar. Bölüt adları sabit ve İngilizcedir.
import { type Lang, type LegalDoc, SITE_URL } from "../../site.config.ts";
import type { League, Match, Team } from "./snapshot-types.ts";

export const homePath = (lang: Lang): string => `/${lang}/`;
export const trackRecordPath = (lang: Lang): string => `/${lang}/track-record/`;
export const legalPath = (lang: Lang, doc: LegalDoc): string => `/${lang}/legal/${doc}/`;
export const leaguePath = (lang: Lang, league: League): string => `/${lang}/${league.slug}/`;

export function teamPath(lang: Lang, league: League, team: Team): string {
  return `/${lang}/${league.slug}/${team.slug}/`;
}

// Maç yolu değişmez kimliği (`path_id`) taşır; isim bölütü süstür (spec §8.1).
export function matchStem(lang: Lang, league: League, match: Match): string {
  return `/${lang}/${league.slug}/match/${match.path_id}/`;
}

export function matchPath(lang: Lang, league: League, match: Match): string {
  return `${matchStem(lang, league, match)}${match.slug}/`;
}

export const absoluteUrl = (path: string): string => `${SITE_URL}${path}`;
```

`web/src/lib/hreflang.ts`:
```ts
// hreflang (spec §8.3): her sayfa etkin BÜTÜN dillere + x-default'a bağlanır, kendine atıflıdır.
import { DEFAULT_LANG, type Lang, SITE_LANGS } from "../../site.config.ts";
import { absoluteUrl } from "./routes.ts";

export type Alternates = { canonical: string; languages: Record<string, string> };

export function alternatesFor(lang: Lang, pathOf: (lang: Lang) => string): Alternates {
  const languages: Record<string, string> = {};
  for (const each of SITE_LANGS) languages[each] = absoluteUrl(pathOf(each));
  languages["x-default"] = absoluteUrl(pathOf(DEFAULT_LANG));
  return { canonical: absoluteUrl(pathOf(lang)), languages };
}
```

`web/src/lib/jsonld.ts`:
```ts
// schema.org JSON-LD oluşturucuları (spec §9). Anlık görüntüden üretilir; oran, teklif,
// bahis bağlantısı, konum, skor YOK. `eventStatus` yalnız maç dışa aktarım anından sonraysa.
import { type Lang, SITE_NAME, SITE_URL } from "../../site.config.ts";
import { absoluteUrl } from "./routes.ts";
import type { League, Match, Team } from "./snapshot-types.ts";

export type JsonLd = Record<string, unknown>;
export type Crumb = { name: string; path: string };

const CONTEXT = "https://schema.org";

export function websiteLd(lang: Lang, homePath: string): JsonLd {
  return {
    "@type": "WebSite",
    name: SITE_NAME,
    url: absoluteUrl(homePath),
    inLanguage: lang,
    publisher: organizationLd(),
  };
}

export function organizationLd(): JsonLd {
  return { "@type": "Organization", name: SITE_NAME, url: SITE_URL };
}

export function leagueLd(league: League, path: string): JsonLd {
  return {
    "@type": "SportsOrganization",
    name: league.name,
    sport: "Soccer",
    location: { "@type": "Country", name: league.country },
    url: absoluteUrl(path),
  };
}

export function teamLd(team: Team, league: League, path: string): JsonLd {
  return {
    "@type": "SportsTeam",
    name: team.name,
    sport: "Soccer",
    memberOf: { "@type": "SportsOrganization", name: league.name },
    url: absoluteUrl(path),
  };
}

export function matchLd(match: Match, league: League, path: string, generatedAt: string): JsonLd {
  const event: JsonLd = {
    "@type": "SportsEvent",
    name: `${match.home} – ${match.away}`,
    startDate: match.commence_time,
    sport: "Soccer",
    homeTeam: { "@type": "SportsTeam", name: match.home },
    awayTeam: { "@type": "SportsTeam", name: match.away },
    organizer: { "@type": "SportsOrganization", name: league.name },
    url: absoluteUrl(path),
  };
  if (Date.parse(match.commence_time) > Date.parse(generatedAt)) {
    event.eventStatus = `${CONTEXT}/EventScheduled`;
  }
  return event;
}

export function breadcrumbLd(crumbs: readonly Crumb[]): JsonLd {
  return {
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.name,
      item: absoluteUrl(crumb.path),
    })),
  };
}

// Spec §9: sayfa başına TEK veri bloğu — varlık(lar) + BreadcrumbList aynı `@graph`ta.
export function pageLd(nodes: readonly JsonLd[]): JsonLd {
  return { "@context": CONTEXT, "@graph": nodes };
}

// `</script>` kırılmasına karşı `<` kaçışlanır; JSON anlamı değişmez.
export function serializeLd(value: JsonLd): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}
```

`web/src/lib/meta.ts`:
```ts
// Sayfa üst verisi (spec §8.3, §8.4, H7): hreflang + kanonik her sayfada; `noindex`
// bayrak kapalıyken HER sayfada, açıkken kaydın `indexable`ına göre.
import type { Metadata } from "next";
import { indexingEnabled, type Lang } from "../../site.config.ts";
import { alternatesFor } from "./hreflang.ts";

export function pageMetadata(
  lang: Lang,
  pathOf: (lang: Lang) => string,
  title: string,
  recordIndexable: boolean,
): Metadata {
  const indexable = indexingEnabled() && recordIndexable;
  return {
    title,
    alternates: alternatesFor(lang, pathOf),
    ...(indexable ? {} : { robots: { index: false } }),
  };
}
```

`web/src/lib/params.ts`:
```ts
// Yol parametrelerini anlık görüntü kayıtlarına çevirir. `dynamicParams = false` olduğu
// için derlenmemiş yol zaten 404'tür; burada bulunamayan kayıt bir derleme hatasıdır.
import { notFound } from "next/navigation";
import { isLang, type Lang } from "../../site.config.ts";
import type { League, Match, Snapshot, Team } from "./snapshot-types.ts";

export function langOf(value: string): Lang {
  if (!isLang(value)) notFound();
  return value;
}

export function leagueOf(snapshot: Snapshot, slug: string): League {
  return snapshot.leagues.find((league) => league.slug === slug) ?? notFound();
}

export function teamOf(snapshot: Snapshot, league: League, slug: string): Team {
  const team = snapshot.teams.find((each) => each.league_id === league.id && each.slug === slug);
  return team ?? notFound();
}

export function matchOf(snapshot: Snapshot, league: League, pathId: string, slug: string): Match {
  const match = snapshot.matches.find(
    (each) => each.league_id === league.id && each.path_id === pathId && each.slug === slug,
  );
  return match ?? notFound();
}
```

- [ ] **Step 4: Yeşil + tip**

Run: `pnpm -C web exec vitest run && pnpm -C web exec tsc --noEmit`
Expected: vitest `46 passed` (37 + routes 3 + jsonld 3 + meta 3); tsc çıktısız.

- [ ] **Step 5: Mutasyon kanıtları**

1. `hreflang.ts`de `absoluteUrl(pathOf(DEFAULT_LANG))` → `absoluteUrl(pathOf(lang))` → routes testi "bütün diller +
   x-default" FAIL (tr sayfasında x-default tr'ye gider). Geri al.
2. `jsonld.ts` `matchLd`de `if (Date.parse(...) > Date.parse(generatedAt))` koşulunu kaldır (her zaman ekle) → "geçmiş
   maçta eventStatus YOK" FAIL. Geri al.
3. `serializeLd`den `.replace(/</g, "\\u003c")`yi kaldır → "tek blok: @graph, `<` kaçışlı" FAIL (Review Focus 1). Geri al.
4. `meta.ts`de `indexingEnabled() && recordIndexable` → `recordIndexable` → "bayrak kapalıyken … noindex" FAIL (H7). Geri al.
5. `routes.ts` `matchPath`e tarih ekle (`${match.date}/${match.slug}/`) → "maç yolu kimlik taşır, tarih taşımaz" FAIL
   (AK20 b). Geri al; `git diff --stat -- web/src` boş.

- [ ] **Step 6: Tam kapı** — `verify.sh` (`b2-t4-gate.log`) + WEB-KAPI; taban PASS.

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/routes.ts web/src/lib/hreflang.ts web/src/lib/jsonld.ts web/src/lib/meta.ts web/src/lib/params.ts \
  web/src/lib/routes.test.ts web/src/lib/jsonld.test.ts web/src/lib/meta.test.ts
git commit -m "feat: URL şeması, hreflang, schema.org oluşturucuları ve sayfa üst verisi (B-2 T4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Ana, lig, takım ve maç sayfaları; value ve analiz yuvaları boş

**Kademe:** K3 (görsel şablonlar; veri bağlantısının ölçümü T9) · **Spec:** §7, §8.1, §8.5, §8.6, §9, B7, H3, H6

Sayfalar hiçbir sayı hesaplamaz: her değer `Num`/`Txt`/`Flag` ile basılır. Kitap adı, kitap oranı, bahis bağlantısı, skor
YOK. Eşik altı tur "Yetersiz kitap", mühürsüz maçın kapanışı "Kapanış bekleniyor" yazar — sayı uydurulmaz.

**Files:**
- Create: `web/src/components/{Fe,Breadcrumbs,JsonLdScript,LocalTime,Slots,RoundsTable,SiteChrome}.tsx`,
  `web/src/components/Fe.test.tsx`, `web/src/styles/site.module.css`, `web/src/app/[lang]/[league]/page.tsx`,
  `web/src/app/[lang]/[league]/[team]/page.tsx`, `web/src/app/[lang]/[league]/match/[pathId]/[slug]/page.tsx`
- Modify (tamamen yeniden yazılır): `web/src/app/[lang]/layout.tsx`, `web/src/app/[lang]/page.tsx`,
  `web/src/lib/site-config.test.ts`

**Interfaces:**
- Consumes: T2 (`loadSnapshot`, `leagueById`, `teamsOf`, `matchesOf`, `matchesOfTeam`), T3 (`formatNumber`, `feKey`,
  `teamKey`, `t`), T4 (yollar, `pageMetadata`, `langOf`/`leagueOf`/`teamOf`/`matchOf`, JSON-LD oluşturucuları).
- Produces (T6, T7, T9):
  ```ts
  export function Num(props: { fe: string; value: number; kind: NumberKind; lang: Lang }): JSX.Element;
  //   → <span data-fe={fe} data-fe-value={String(value)}>{formatNumber(...)}</span>  (tek metin çocuk)
  export function Txt(props: { fe: string; value: string }): JSX.Element;  // <code data-fe data-fe-value>{value}</code>
  export function Flag(props: { fe: string; value: boolean; children: ReactNode }): JSX.Element; // yalnız öznitelik sınanır
  export function ValueBadge(props: { value: null }): null;  export function AnalysisSlot(props: { value: null }): null;
  export function JsonLdScript(props: { data: JsonLd }): JSX.Element;       // tek <script type="application/ld+json">
  export function Breadcrumbs(props: { crumbs: readonly Crumb[]; label: string }): JSX.Element;
  export function LocalTime(props: { iso: string; lang: string }): JSX.Element;  // "use client"; SSR metni UTC
  export function SiteHeader/SiteFooter(props: { lang: Lang }): JSX.Element;
  ```
  Her sayfanın `<main>`i `data-fe-page` taşır: `home` · `league:<id>` · `team:<lig>/<slug>` · `match:<id>` (T6:
  `track-record`, T7: `legal:<doc>`). Sayfa başına tam bir `<h1>`, tam bir JSON-LD bloğu.

- [ ] **Step 1: Bileşen testini yaz — `web/src/components/Fe.test.tsx`; koştur, kırmızı**

```tsx
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Flag, Num, Txt } from "./Fe.tsx";
import { AnalysisSlot, ValueBadge } from "./Slots.tsx";

describe("Fe bileşenleri (H6c)", () => {
  it("Num: öznitelik ham değer, çocuk TEK metin (renderToString yorum düğümü koymaz)", () => {
    const html = renderToString(createElement(Num, { fe: "k", value: 40, kind: "pct1", lang: "tr" }));
    expect(html).toBe('<span data-fe="k" data-fe-value="40">%40,0</span>');
  });

  it("Txt ve Flag", () => {
    expect(renderToString(createElement(Txt, { fe: "h", value: "abc" }))).toBe(
      '<code data-fe="h" data-fe-value="abc">abc</code>',
    );
    expect(renderToString(createElement(Flag, { fe: "s", value: false, children: "Bekleniyor" }))).toBe(
      '<span data-fe="s" data-fe-value="false">Bekleniyor</span>',
    );
  });

  it("value ve analiz yuvaları null iken HİÇBİR şey çizmez (spec §7, §8.6)", () => {
    expect(renderToString(createElement(ValueBadge, { value: null }))).toBe("");
    expect(renderToString(createElement(AnalysisSlot, { value: null }))).toBe("");
  });
});
```

Run: `pnpm -C web exec vitest run src/components/Fe.test.tsx`
Expected: FAIL — `./Fe.tsx` yüklenemiyor.

- [ ] **Step 2: Bileşenler ve stil**

`web/src/components/Fe.tsx`:
```tsx
// Anlık görüntüden gelen HER değer bu bileşenlerle basılır (spec H6c): öznitelik anlık
// görüntüdeki değerin birebir metni, görünen metin `formatNumber(değer)`. Çocuk TEK bir
// dizedir — React iki komşu metin arasına `<!-- -->` koyar ve tarayıcı eşitliği bozulur.
import type { ReactNode } from "react";
import type { Lang } from "../../site.config.ts";
import { formatNumber, type NumberKind } from "../lib/format.ts";

export function Num(props: { fe: string; value: number; kind: NumberKind; lang: Lang }) {
  return (
    <span data-fe={props.fe} data-fe-value={String(props.value)}>
      {formatNumber(props.value, props.kind, props.lang)}
    </span>
  );
}

export function Txt(props: { fe: string; value: string }) {
  return (
    <code data-fe={props.fe} data-fe-value={props.value}>
      {props.value}
    </code>
  );
}

// Değeri metin olarak GÖSTERİLMEYEN alan (ör. mühür durumu): yalnız öznitelik sınanır.
export function Flag(props: { fe: string; value: boolean; children: ReactNode }) {
  return (
    <span data-fe={props.fe} data-fe-value={String(props.value)}>
      {props.children}
    </span>
  );
}
```

`web/src/components/Slots.tsx`:
```tsx
// Faz 5 (value) ve Faz 7 (analiz) yuvaları. Şema v1'de ikisi de `const null`dır; bileşen
// null iken HİÇBİR şey çizmez — boş kutu, "yakında" yazısı yok (spec §7, §8.6).
export function ValueBadge({ value }: { value: null }) {
  return value;
}

export function AnalysisSlot({ value }: { value: null }) {
  return value;
}
```

`web/src/components/JsonLdScript.tsx`:
```tsx
import { type JsonLd, serializeLd } from "../lib/jsonld.ts";

// Veri bloğu (spec §9): CSP'ye tabi değildir ve hash listesine girmez (§5.3/7).
export function JsonLdScript({ data }: { data: JsonLd }) {
  return (
    <script
      type="application/ld+json"
      // biome-ignore lint/security/noDangerouslySetInnerHtml: JSON-LD veri bloğu; `<` serializeLd'de kaçışlanır.
      dangerouslySetInnerHTML={{ __html: serializeLd(data) }}
    />
  );
}
```

`web/src/components/Breadcrumbs.tsx`:
```tsx
import type { Crumb } from "../lib/jsonld.ts";
import styles from "../styles/site.module.css";

export function Breadcrumbs({ crumbs, label }: { crumbs: readonly Crumb[]; label: string }) {
  return (
    <nav aria-label={label} className={styles.crumbs}>
      <ol>
        {crumbs.map((crumb) => (
          <li key={crumb.path}>
            <a href={crumb.path}>{crumb.name}</a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
```

`web/src/components/LocalTime.tsx`:
```tsx
"use client";
// Başlama anı (spec §7): sunucu çıktısı UTC'dir ve betiksiz tarayıcı onu görür; betik
// açıksa aynı an ziyaretçinin yerel saatine çevrilir. `datetime` değişmez.
import { useEffect, useState } from "react";

export function utcLabel(iso: string): string {
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}

export function LocalTime({ iso, lang }: { iso: string; lang: string }) {
  const [label, setLabel] = useState(utcLabel(iso));
  useEffect(() => {
    setLabel(new Date(iso).toLocaleString(lang, { dateStyle: "medium", timeStyle: "short" }));
  }, [iso, lang]);
  return <time dateTime={iso}>{label}</time>;
}
```

`web/src/components/RoundsTable.tsx`:
```tsx
// Açılış / son / kapanış konsensüsü. Eşik altı tur `null`dır: sayı UYDURULMAZ, neden yazılır.
import type { Lang } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";
import { feKey } from "../lib/fe.ts";
import type { Match } from "../lib/snapshot-types.ts";
import styles from "../styles/site.module.css";
import { Num } from "./Fe.tsx";

const ROUNDS = ["opening", "latest", "closing"] as const;
const SIDES = ["home", "draw", "away"] as const;

export function RoundsTable({ match, lang }: { match: Match; lang: Lang }) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th scope="col">{t(lang, "match.round")}</th>
          <th scope="col">{match.home}</th>
          <th scope="col">{t(lang, "match.draw")}</th>
          <th scope="col">{match.away}</th>
          <th scope="col">{t(lang, "match.books")}</th>
        </tr>
      </thead>
      <tbody>
        {ROUNDS.map((name) => {
          const round = match.h2h[name];
          const missing = name === "closing" && !match.sealed ? "match.awaitingClose" : "match.insufficient";
          return (
            <tr key={name}>
              <th scope="row">{t(lang, `match.${name}`)}</th>
              {round === null ? (
                <td colSpan={4}>{t(lang, missing)}</td>
              ) : (
                <>
                  {SIDES.map((side) => (
                    <td key={side}>
                      <Num
                        fe={feKey("match", match.id, `h2h.${name}.p.${side}`)}
                        value={round.p[side]}
                        kind="pct1"
                        lang={lang}
                      />
                    </td>
                  ))}
                  <td>
                    <Num
                      fe={feKey("match", match.id, `h2h.${name}.books`)}
                      value={round.books}
                      kind="int"
                      lang={lang}
                    />
                  </td>
                </>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
```

`web/src/components/SiteChrome.tsx`:
```tsx
import { type Lang, LEGAL_DOCS, SITE_NAME } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";
import { homePath, legalPath, trackRecordPath } from "../lib/routes.ts";
import styles from "../styles/site.module.css";

export function SiteHeader({ lang }: { lang: Lang }) {
  return (
    <header className={styles.header}>
      <a href={homePath(lang)} className={styles.brand}>
        {SITE_NAME}
      </a>
      <nav aria-label={t(lang, "nav.home")}>
        <a href={homePath(lang)}>{t(lang, "nav.home")}</a>{" "}
        <a href={trackRecordPath(lang)}>{t(lang, "nav.trackRecord")}</a>
      </nav>
    </header>
  );
}

export function SiteFooter({ lang }: { lang: Lang }) {
  return (
    <footer className={styles.footer}>
      <p>{t(lang, "age.strip")}</p>
      <p>{t(lang, "footer.notAdvice")}</p>
      <p>{t(lang, "footer.responsible")}</p>
      <nav aria-label={t(lang, "nav.legal")}>
        <ul>
          {LEGAL_DOCS.map((doc) => (
            <li key={doc}>
              <a href={legalPath(lang, doc)}>{t(lang, `legal.${doc}`)}</a>
            </li>
          ))}
        </ul>
      </nav>
    </footer>
  );
}
```

`web/src/styles/site.module.css` (18+ ve taslak sınıfları T7'de kullanılır):
```css
.body {
  margin: 0 auto;
  max-width: 60rem;
  padding: 0 1rem;
  font-family: system-ui, sans-serif;
  line-height: 1.5;
  color: #1a1a1a;
  background: #fff;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 1rem 0;
  border-bottom: 1px solid #ddd;
}
.brand {
  font-weight: 700;
  text-decoration: none;
  color: inherit;
}
.footer {
  margin-top: 3rem;
  padding: 1rem 0;
  border-top: 1px solid #ddd;
  font-size: 0.875rem;
}
.crumbs ol {
  display: flex;
  gap: 0.5rem;
  list-style: none;
  padding: 0;
}
.table {
  border-collapse: collapse;
  width: 100%;
}
.table th,
.table td {
  border-bottom: 1px solid #eee;
  padding: 0.25rem 0.5rem;
  text-align: left;
}
.ageStrip {
  background: #111;
  color: #fff;
  padding: 0.5rem 1rem;
  margin: 0;
}
.ageGate {
  border: 0;
  width: 100%;
  height: 100%;
  max-width: none;
  max-height: none;
  margin: 0;
  position: fixed;
  inset: 0;
  z-index: 10;
  background: #fff;
  padding: 2rem;
}
.ageTitle {
  font-size: 1.5rem;
  font-weight: 700;
}
.draft {
  border: 2px solid #b00;
  color: #b00;
  padding: 0.5rem 1rem;
  font-weight: 700;
}
.muted {
  color: #555;
}
```

Run: `pnpm -C web exec vitest run src/components/Fe.test.tsx`
Expected: `3 passed`.

- [ ] **Step 3: Kök yerleşim ve sayfalar**

`web/src/app/[lang]/layout.tsx` (T7 18+ bildirimini ekler):
```tsx
// Kök yerleşim dil bölütündedir: `<html lang>` sayfanın diliyle aynıdır (spec §5.3/8).
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SITE_LANGS, SITE_NAME } from "../../../site.config.ts";
import { SiteFooter, SiteHeader } from "../../components/SiteChrome.tsx";
import { langOf } from "../../lib/params.ts";
import styles from "../../styles/site.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export const metadata: Metadata = { title: { template: `%s · ${SITE_NAME}`, default: SITE_NAME } };

export default async function LangLayout(props: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const lang = langOf((await props.params).lang);
  return (
    <html lang={lang}>
      <body className={styles.body}>
        <SiteHeader lang={lang} />
        {props.children}
        <SiteFooter lang={lang} />
      </body>
    </html>
  );
}
```

`web/src/app/[lang]/page.tsx`:
```tsx
import { type Lang, SITE_LANGS } from "../../../site.config.ts";
import { Breadcrumbs } from "../../components/Breadcrumbs.tsx";
import { JsonLdScript } from "../../components/JsonLdScript.tsx";
import { t } from "../../i18n/dict.ts";
import { breadcrumbLd, pageLd, websiteLd } from "../../lib/jsonld.ts";
import { pageMetadata } from "../../lib/meta.ts";
import { langOf } from "../../lib/params.ts";
import { homePath, leaguePath, trackRecordPath } from "../../lib/routes.ts";
import { loadSnapshot } from "../../lib/snapshot.ts";

type Params = { params: Promise<{ lang: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export async function generateMetadata({ params }: Params) {
  const lang = langOf((await params).lang);
  return pageMetadata(lang, homePath, t(lang, "home.title"), true);
}

export default async function HomePage({ params }: Params) {
  const lang: Lang = langOf((await params).lang);
  const snapshot = loadSnapshot();
  const crumbs = [{ name: t(lang, "nav.home"), path: homePath(lang) }];
  return (
    <main data-fe-page="home">
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{t(lang, "home.title")}</h1>
      <p>{t(lang, "home.intro")}</p>
      <h2>{t(lang, "home.leagues")}</h2>
      <ul>
        {snapshot.leagues.map((league) => (
          <li key={league.id}>
            <a href={leaguePath(lang, league)}>{league.name}</a> ({league.country})
          </li>
        ))}
      </ul>
      <p>
        <a href={trackRecordPath(lang)}>{t(lang, "home.trackRecordLink")}</a>
      </p>
      <JsonLdScript data={pageLd([websiteLd(lang, homePath(lang)), breadcrumbLd(crumbs)])} />
    </main>
  );
}
```

`web/src/app/[lang]/[league]/page.tsx`:
```tsx
import { SITE_LANGS } from "../../../../site.config.ts";
import { Breadcrumbs } from "../../../components/Breadcrumbs.tsx";
import { Num } from "../../../components/Fe.tsx";
import { JsonLdScript } from "../../../components/JsonLdScript.tsx";
import { LocalTime } from "../../../components/LocalTime.tsx";
import { t } from "../../../i18n/dict.ts";
import { feKey, teamKey } from "../../../lib/fe.ts";
import { breadcrumbLd, leagueLd, pageLd } from "../../../lib/jsonld.ts";
import { pageMetadata } from "../../../lib/meta.ts";
import { langOf, leagueOf } from "../../../lib/params.ts";
import { homePath, leaguePath, matchPath, teamPath } from "../../../lib/routes.ts";
import { loadSnapshot, matchesOf, teamsOf } from "../../../lib/snapshot.ts";

type Params = { params: Promise<{ lang: string; league: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  const { leagues } = loadSnapshot();
  return SITE_LANGS.flatMap((lang) => leagues.map((league) => ({ lang, league: league.slug })));
}

export async function generateMetadata({ params }: Params) {
  const { lang: rawLang, league: slug } = await params;
  const lang = langOf(rawLang);
  const league = leagueOf(loadSnapshot(), slug);
  return pageMetadata(lang, (each) => leaguePath(each, league), league.name, true);
}

export default async function LeaguePage({ params }: Params) {
  const { lang: rawLang, league: slug } = await params;
  const lang = langOf(rawLang);
  const snapshot = loadSnapshot();
  const league = leagueOf(snapshot, slug);
  const path = leaguePath(lang, league);
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: league.name, path },
  ];
  const distribution = league.move_distribution;
  return (
    <main data-fe-page={`league:${league.id}`}>
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{league.name}</h1>
      <dl>
        <dt>{t(lang, "league.country")}</dt>
        <dd>{league.country}</dd>
        <dt>{t(lang, "league.matches")}</dt>
        <dd>
          <Num fe={feKey("league", league.id, "matches")} value={league.matches} kind="int" lang={lang} />
        </dd>
      </dl>
      <h2>{t(lang, "league.moveTitle")}</h2>
      {distribution === null ? (
        <p>{t(lang, "league.moveTooFew")}</p>
      ) : (
        <dl>
          {(["p10", "p50", "p90"] as const).map((key) => (
            <div key={key}>
              <dt>{t(lang, `league.${key}`)}</dt>
              <dd>
                <Num
                  fe={feKey("league", league.id, `move_distribution.${key}`)}
                  value={distribution[key]}
                  kind="pp1"
                  lang={lang}
                />
              </dd>
            </div>
          ))}
        </dl>
      )}
      <h2>{t(lang, "league.teams")}</h2>
      <ul>
        {teamsOf(snapshot, league).map((team) => (
          <li key={teamKey(team.league_id, team.slug)}>
            <a href={teamPath(lang, league, team)}>{team.name}</a>
          </li>
        ))}
      </ul>
      <h2>{t(lang, "league.matchList")}</h2>
      <ul>
        {matchesOf(snapshot, league).map((match) => (
          <li key={match.id}>
            <LocalTime iso={match.commence_time} lang={lang} />{" "}
            <a href={matchPath(lang, league, match)}>
              {match.home} – {match.away}
            </a>
          </li>
        ))}
      </ul>
      <JsonLdScript data={pageLd([leagueLd(league, path), breadcrumbLd(crumbs)])} />
    </main>
  );
}
```

`web/src/app/[lang]/[league]/[team]/page.tsx`:
```tsx
import { SITE_LANGS } from "../../../../../site.config.ts";
import { Breadcrumbs } from "../../../../components/Breadcrumbs.tsx";
import { Num } from "../../../../components/Fe.tsx";
import { JsonLdScript } from "../../../../components/JsonLdScript.tsx";
import { LocalTime } from "../../../../components/LocalTime.tsx";
import { t } from "../../../../i18n/dict.ts";
import { feKey, teamKey } from "../../../../lib/fe.ts";
import { breadcrumbLd, pageLd, teamLd } from "../../../../lib/jsonld.ts";
import { pageMetadata } from "../../../../lib/meta.ts";
import { langOf, leagueOf, teamOf } from "../../../../lib/params.ts";
import { homePath, leaguePath, matchPath, teamPath } from "../../../../lib/routes.ts";
import { leagueById, loadSnapshot, matchesOfTeam } from "../../../../lib/snapshot.ts";

type Params = { params: Promise<{ lang: string; league: string; team: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  const snapshot = loadSnapshot();
  return SITE_LANGS.flatMap((lang) =>
    snapshot.teams.map((team) => ({
      lang,
      league: leagueById(snapshot, team.league_id).slug,
      team: team.slug,
    })),
  );
}

export async function generateMetadata({ params }: Params) {
  const { lang: rawLang, league: leagueSlug, team: teamSlug } = await params;
  const lang = langOf(rawLang);
  const snapshot = loadSnapshot();
  const league = leagueOf(snapshot, leagueSlug);
  const team = teamOf(snapshot, league, teamSlug);
  return pageMetadata(lang, (each) => teamPath(each, league, team), team.name, team.indexable);
}

export default async function TeamPage({ params }: Params) {
  const { lang: rawLang, league: leagueSlug, team: teamSlug } = await params;
  const lang = langOf(rawLang);
  const snapshot = loadSnapshot();
  const league = leagueOf(snapshot, leagueSlug);
  const team = teamOf(snapshot, league, teamSlug);
  const path = teamPath(lang, league, team);
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: league.name, path: leaguePath(lang, league) },
    { name: team.name, path },
  ];
  return (
    <main data-fe-page={`team:${teamKey(team.league_id, team.slug)}`}>
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{team.name}</h1>
      <dl>
        <dt>{t(lang, "team.league")}</dt>
        <dd>
          <a href={leaguePath(lang, league)}>{league.name}</a>
        </dd>
        <dt>{t(lang, "team.matches")}</dt>
        <dd>
          <Num
            fe={feKey("team", teamKey(team.league_id, team.slug), "matches")}
            value={team.matches}
            kind="int"
            lang={lang}
          />
        </dd>
      </dl>
      <h2>{t(lang, "team.matchList")}</h2>
      <ul>
        {matchesOfTeam(snapshot, team).map((match) => (
          <li key={match.id}>
            <LocalTime iso={match.commence_time} lang={lang} />{" "}
            <a href={matchPath(lang, league, match)}>
              {match.home} – {match.away}
            </a>
          </li>
        ))}
      </ul>
      <JsonLdScript data={pageLd([teamLd(team, league, path), breadcrumbLd(crumbs)])} />
    </main>
  );
}
```

`web/src/app/[lang]/[league]/match/[pathId]/[slug]/page.tsx`:
```tsx
// Maç sayfası (spec §7): yalnız vig'i temizlenmiş piyasa konsensüsü, kitap SAYISI, tur
// sayısı, hareket ve mühür durumu. Kitap adı, kitap oranı, bağlantı, skor YOK (B7, AK10).
import { SITE_LANGS } from "../../../../../../../site.config.ts";
import { Breadcrumbs } from "../../../../../../components/Breadcrumbs.tsx";
import { Flag, Num } from "../../../../../../components/Fe.tsx";
import { JsonLdScript } from "../../../../../../components/JsonLdScript.tsx";
import { LocalTime } from "../../../../../../components/LocalTime.tsx";
import { RoundsTable } from "../../../../../../components/RoundsTable.tsx";
import { AnalysisSlot, ValueBadge } from "../../../../../../components/Slots.tsx";
import { t } from "../../../../../../i18n/dict.ts";
import { feKey } from "../../../../../../lib/fe.ts";
import { breadcrumbLd, matchLd, pageLd } from "../../../../../../lib/jsonld.ts";
import { pageMetadata } from "../../../../../../lib/meta.ts";
import { langOf, leagueOf, matchOf } from "../../../../../../lib/params.ts";
import { homePath, leaguePath, matchPath } from "../../../../../../lib/routes.ts";
import { leagueById, loadSnapshot } from "../../../../../../lib/snapshot.ts";

type Params = {
  params: Promise<{ lang: string; league: string; pathId: string; slug: string }>;
};

export const dynamicParams = false;

export function generateStaticParams() {
  const snapshot = loadSnapshot();
  return SITE_LANGS.flatMap((lang) =>
    snapshot.matches.map((match) => ({
      lang,
      league: leagueById(snapshot, match.league_id).slug,
      pathId: match.path_id,
      slug: match.slug,
    })),
  );
}

async function resolve(params: Params["params"]) {
  const { lang: rawLang, league: leagueSlug, pathId, slug } = await params;
  const snapshot = loadSnapshot();
  const league = leagueOf(snapshot, leagueSlug);
  return { lang: langOf(rawLang), snapshot, league, match: matchOf(snapshot, league, pathId, slug) };
}

export async function generateMetadata({ params }: Params) {
  const { lang, league, match } = await resolve(params);
  const title = `${match.home} – ${match.away}`;
  return pageMetadata(lang, (each) => matchPath(each, league, match), title, match.indexable);
}

export default async function MatchPage({ params }: Params) {
  const { lang, snapshot, league, match } = await resolve(params);
  const path = matchPath(lang, league, match);
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: league.name, path: leaguePath(lang, league) },
    { name: `${match.home} – ${match.away}`, path },
  ];
  const move = match.move;
  return (
    <main data-fe-page={`match:${match.id}`}>
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{`${match.home} – ${match.away}`}</h1>
      <p>
        <a href={leaguePath(lang, league)}>{league.name}</a> · {t(lang, "match.kickoff")}:{" "}
        <LocalTime iso={match.commence_time} lang={lang} />
      </p>
      <ValueBadge value={snapshot.value_badge} />
      <h2>{t(lang, "match.consensus")}</h2>
      <RoundsTable match={match} lang={lang} />
      <dl>
        <dt>{t(lang, "match.rounds")}</dt>
        <dd>
          <Num fe={feKey("match", match.id, "rounds")} value={match.rounds} kind="int" lang={lang} />
        </dd>
        <dt>{t(lang, "match.status")}</dt>
        <dd>
          <Flag fe={feKey("match", match.id, "sealed")} value={match.sealed}>
            {t(lang, match.sealed ? "match.sealed" : "match.pending")}
          </Flag>
        </dd>
      </dl>
      <h2>{t(lang, "match.move")}</h2>
      {move === null ? (
        <p>{t(lang, "match.noMove")}</p>
      ) : (
        <dl>
          {(["home", "draw", "away"] as const).map((side) => (
            <div key={side}>
              <dt>{side === "draw" ? t(lang, "match.draw") : match[side]}</dt>
              <dd>
                <Num fe={feKey("match", match.id, `move.${side}`)} value={move[side]} kind="pp1" lang={lang} />
              </dd>
            </div>
          ))}
        </dl>
      )}
      <AnalysisSlot value={snapshot.analysis} />
      <JsonLdScript
        data={pageLd([matchLd(match, league, path, snapshot.generated_at), breadcrumbLd(crumbs)])}
      />
    </main>
  );
}
```

- [ ] **Step 4: Yer tutucu taramasını ekle — `web/src/lib/site-config.test.ts` (tam dosya)**

```ts
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  indexingEnabled,
  isLang,
  LEDGER_HISTORY_URL,
  SITE_LANGS,
  SITE_NAME,
  SITE_URL,
} from "../../site.config.ts";

const WEB = resolve(import.meta.dirname, "../..");

// Dizin henüz yoksa (content/ T7'de, scripts/ T8'de gelir) boş sayılır; gelince kendiliğinden taranır.
function sources(dir: string): string[] {
  if (!existsSync(resolve(WEB, dir))) return [];
  return readdirSync(resolve(WEB, dir), { recursive: true, encoding: "utf8" })
    .filter((file) => /\.tsx?$/.test(file) && !/\.test\.tsx?$/.test(file))
    .map((file) => join(WEB, dir, file));
}

describe("site.config (spec §8.3, H7)", () => {
  it("indeksleme yalnız SITE_INDEXABLE=1 ile açılır", () => {
    expect(indexingEnabled({})).toBe(false);
    expect(indexingEnabled({ SITE_INDEXABLE: "0" })).toBe(false);
    expect(indexingEnabled({ SITE_INDEXABLE: "true" })).toBe(false);
    expect(indexingEnabled({ SITE_INDEXABLE: "1" })).toBe(true);
  });

  it("dil listesi yer tutucudur: en + tr (AK5 önerisi)", () => {
    expect(SITE_LANGS).toEqual(["en", "tr"]);
    expect(isLang("tr")).toBe(true);
    expect(isLang("de")).toBe(false);
  });
});

describe("yer tutucular tek kaynaktan (AK3, AK4)", () => {
  it("marka, alan adı ve çıpa adresi site.config.ts dışında literal olarak geçmez", () => {
    const files = ["src", "content", "scripts"].flatMap(sources);
    expect(files.length).toBeGreaterThan(10);
    for (const file of files) {
      const text = readFileSync(file, "utf-8");
      for (const literal of [SITE_NAME, SITE_URL, LEDGER_HISTORY_URL]) {
        expect(text.includes(literal), `${file} ${literal}`).toBe(false);
      }
    }
  });
});
```

`content/` (T7) ve `scripts/` (T8) henüz yoktur; `sources()` onları boş sayar ve geldiklerinde kendiliğinden tarar.

- [ ] **Step 5: Derleme dumanı (tam kapsamlı ölçüm T9'da)**

Run (depo kökünden):
```bash
source ~/.nvm/nvm.sh && nvm use 24 >/dev/null && export NEXT_TELEMETRY_DISABLED=1
SITE_SNAPSHOT="$PWD/web/fixtures/snapshot.fixture.web-full.json" pnpm -C web run build
node -e '
const fs = require("fs");
const read = (p) => fs.readFileSync("web/out/" + p, "utf8");
const want = {
  "tr/synthetic-league-alpha/match/34e5be017510/dogu-bati-fk-vs-obrien-rovers/index.html": [
    "data-fe-page=\"match:34e5be017510d1e27d6773ffd0954e1e\"", ">%38,0<", "Yetersiz kitap", ">Kapanış kaydedildi<",
    "<h1>Doğu &amp; Batı FK – O&#x27;Brien Rovers</h1>", "<meta name=\"robots\" content=\"noindex\"/>"],
  "en/synthetic-league-beta/match/40bb30156880/delta-city-vs-epsilon-town/index.html": [">40.0%<", ">-1.5 pp<"],
  "en/synthetic-league-alpha/match/cdc63e7b45d9/guneykoy-idmanyurdu-vs-dogu-bati-fk/index.html": [
    "Awaiting close", "No move to show.", "EventScheduled"],
  "en/synthetic-league-alpha/index.html": ["data-fe-page=\"league:xla.1\"", ">1.8 pp<"],
  "en/synthetic-league-beta/index.html": ["Not enough matches yet"],
};
for (const [page, needles] of Object.entries(want)) for (const n of needles)
  if (!read(page).includes(n)) { console.error("YOK:", page, n); process.exit(1); }
for (const p of Object.keys(want)) for (const bad of ["NaN", "undefined"])
  if (read(p).replace(/<script[\s\S]*?<\/script>/g, "").includes(bad)) { console.error("VAR:", p, bad); process.exit(1); }
console.log("duman ok");'
```
Expected: derleme `● /[lang]/[league]/match/[pathId]/[slug]` altında 12 yol; `duman ok`.

- [ ] **Step 6: Yeşil + tip + biçim**

Run: `pnpm -C web exec biome check --write . && pnpm -C web exec biome ci . && pnpm -C web exec tsc --noEmit && pnpm -C web exec vitest run`
Expected: Biome hatasız; tsc çıktısız; vitest `50 passed` (46 + Fe 3 + yer tutucu 1).

- [ ] **Step 7: Mutasyon kanıtları**

1. `Fe.tsx` `Num`da çocuğu ikiye böl (`{formatNumber(...).slice(0, 1)}` ve `{formatNumber(...).slice(1)}`) →
   `Fe.test.tsx` "çocuk TEK metin" FAIL (`renderToString` araya `<!-- -->` koyar; gerçek sayfada tarayıcı bu öğeyi
   okuyamazdı). Geri al.
2. `Slots.tsx` `ValueBadge` `return <div className="value" />;` → "value ve analiz yuvaları null iken HİÇBİR şey çizmez"
   FAIL (H3/§7). Geri al.
3. `SiteChrome.tsx`de `{SITE_NAME}` yerine literal `[site-name]` yaz → yer tutucu taraması FAIL (AK3). Geri al;
   `git diff --stat -- web/src` boş.

- [ ] **Step 8: Tam kapı** — `verify.sh` (`b2-t5-gate.log`) + WEB-KAPI; taban PASS.

- [ ] **Step 9: Commit**

```bash
git add web/src/components/Fe.tsx web/src/components/Fe.test.tsx web/src/components/Slots.tsx \
  web/src/components/JsonLdScript.tsx web/src/components/Breadcrumbs.tsx web/src/components/LocalTime.tsx \
  web/src/components/RoundsTable.tsx web/src/components/SiteChrome.tsx web/src/styles/site.module.css \
  "web/src/app/[lang]/layout.tsx" "web/src/app/[lang]/page.tsx" "web/src/app/[lang]/[league]/page.tsx" \
  "web/src/app/[lang]/[league]/[team]/page.tsx" "web/src/app/[lang]/[league]/match/[pathId]/[slug]/page.tsx" \
  web/src/lib/site-config.test.ts
git commit -m "feat: ana, lig, takım ve maç sayfaları; value ve analiz yuvaları boş (B-2 T5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Sicil sayfası — boş durum, defter durumu, doğrulamanın dürüst sınırı

**Kademe:** K2 · **Spec:** §6.1, §6.2, §6.3, AK21 (hash "doğrulama değil taahhüt"), H6

**Files:**
- Create: `web/src/app/[lang]/track-record/page.tsx`, `web/src/components/RecordTable.tsx`

**Interfaces:**
- Consumes: T5 bileşenleri (`Num`, `Txt`, `LocalTime`, `Breadcrumbs`, `JsonLdScript`), T3 sözlük anahtarları `record.*`.
- Produces: `/{lang}/track-record/` — `data-fe-page="track-record"`; `data-fe` anahtarları: `ledger:-:{rows,last_id,head,
  anchor.file,anchor.rows,anchor.last_id,anchor.head}`, `record:-:published`, dolu sicilde `record:-:summary.{n,mean_clv,
  ci_low,ci_high}` ve girdi başına `entry:<publication_id>:{market,outcome,published_price,closing_fair_price,clv,
  publication_ledger_id,publication_hash}`, `root:-:content_sha256` (T9'un beklenen kümesi budur).

- [ ] **Step 1: Kırmızı duman (sayfa yok)**

Run: `test -f web/out/en/track-record/index.html && echo var || echo yok` (T5 derlemesinden sonra)
Expected: `yok`.

- [ ] **Step 2: Sicil tablosu — `web/src/components/RecordTable.tsx`**

```tsx
// Dolu sicil (spec §6.1): her değer Python'da hesaplanmış, TS yalnız biçimler.
import type { Lang } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";
import { feKey } from "../lib/fe.ts";
import type { Snapshot } from "../lib/snapshot-types.ts";
import styles from "../styles/site.module.css";
import { Num, Txt } from "./Fe.tsx";
import { LocalTime } from "./LocalTime.tsx";

export function RecordTable({ snapshot, lang }: { snapshot: Snapshot; lang: Lang }) {
  const { entries, summary } = snapshot.record;
  const names = new Map(snapshot.matches.map((match) => [match.id, `${match.home} – ${match.away}`]));
  return (
    <>
      <table className={styles.table}>
        <caption>{t(lang, "record.tableCaption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t(lang, "record.colTime")}</th>
            <th scope="col">{t(lang, "record.colMatch")}</th>
            <th scope="col">{t(lang, "record.colMarket")}</th>
            <th scope="col">{t(lang, "record.colOutcome")}</th>
            <th scope="col">{t(lang, "record.colPrice")}</th>
            <th scope="col">{t(lang, "record.colFair")}</th>
            <th scope="col">{t(lang, "record.colClv")}</th>
            <th scope="col">{t(lang, "record.colLedger")}</th>
            <th scope="col">{t(lang, "record.colHash")}</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const id = String(entry.publication_id);
            return (
              <tr key={id}>
                <td>
                  <LocalTime iso={entry.published_at} lang={lang} />
                </td>
                <td>{names.get(entry.match_id) ?? entry.match_id}</td>
                <td>
                  <Txt fe={feKey("entry", id, "market")} value={entry.market} />
                </td>
                <td>
                  <Txt fe={feKey("entry", id, "outcome")} value={entry.outcome} />
                </td>
                <td>
                  <Num fe={feKey("entry", id, "published_price")} value={entry.published_price} kind="price2" lang={lang} />
                </td>
                <td>
                  <Num fe={feKey("entry", id, "closing_fair_price")} value={entry.closing_fair_price} kind="price2" lang={lang} />
                </td>
                <td>
                  <Num fe={feKey("entry", id, "clv")} value={entry.clv} kind="pct2" lang={lang} />
                </td>
                <td>
                  <Num fe={feKey("entry", id, "publication_ledger_id")} value={entry.publication_ledger_id} kind="int" lang={lang} />
                </td>
                <td>
                  <Txt fe={feKey("entry", id, "publication_hash")} value={entry.publication_hash} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {summary === null ? null : (
        <>
          <h2>{t(lang, "record.summaryTitle")}</h2>
          <dl>
            <dt>{t(lang, "record.summaryN")}</dt>
            <dd>
              <Num fe={feKey("record", "-", "summary.n")} value={summary.n} kind="int" lang={lang} />
            </dd>
            <dt>{t(lang, "record.summaryMean")}</dt>
            <dd>
              <Num fe={feKey("record", "-", "summary.mean_clv")} value={summary.mean_clv} kind="pct2" lang={lang} />
            </dd>
            <dt>{t(lang, "record.summaryCi")}</dt>
            <dd>
              <Num fe={feKey("record", "-", "summary.ci_low")} value={summary.ci_low} kind="pct2" lang={lang} />
              {" … "}
              <Num fe={feKey("record", "-", "summary.ci_high")} value={summary.ci_high} kind="pct2" lang={lang} />
            </dd>
          </dl>
        </>
      )}
    </>
  );
}
```

- [ ] **Step 3: Sayfa — `web/src/app/[lang]/track-record/page.tsx`**

```tsx
// Sicil (spec §6): defterden türetilir, sayı hesaplamaz (H6). Boş sicil bir DURUMdur;
// "yakında", sahte örnek, backtest sonucu GÖSTERİLMEZ (§6.2).
import { LEDGER_HISTORY_URL, SITE_LANGS } from "../../../../site.config.ts";
import { Breadcrumbs } from "../../../components/Breadcrumbs.tsx";
import { Num, Txt } from "../../../components/Fe.tsx";
import { JsonLdScript } from "../../../components/JsonLdScript.tsx";
import { LocalTime } from "../../../components/LocalTime.tsx";
import { RecordTable } from "../../../components/RecordTable.tsx";
import { t } from "../../../i18n/dict.ts";
import { feKey } from "../../../lib/fe.ts";
import { breadcrumbLd, pageLd } from "../../../lib/jsonld.ts";
import { pageMetadata } from "../../../lib/meta.ts";
import { langOf } from "../../../lib/params.ts";
import { homePath, trackRecordPath } from "../../../lib/routes.ts";
import { loadSnapshot } from "../../../lib/snapshot.ts";

type Params = { params: Promise<{ lang: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export async function generateMetadata({ params }: Params) {
  const lang = langOf((await params).lang);
  return pageMetadata(lang, trackRecordPath, t(lang, "record.title"), true);
}

export default async function TrackRecordPage({ params }: Params) {
  const lang = langOf((await params).lang);
  const snapshot = loadSnapshot();
  const { ledger, record } = snapshot;
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: t(lang, "record.title"), path: trackRecordPath(lang) },
  ];
  const ledgerNum = (path: string, value: number) => (
    <Num fe={feKey("ledger", "-", path)} value={value} kind="int" lang={lang} />
  );
  return (
    <main data-fe-page="track-record">
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{t(lang, "record.title")}</h1>
      <p>
        {t(lang, "record.published")}:{" "}
        <strong>
          <Num fe={feKey("record", "-", "published")} value={record.published} kind="int" lang={lang} />
        </strong>
      </p>
      {record.published === 0 ? (
        <p>{t(lang, "record.emptyExplain")}</p>
      ) : (
        <RecordTable snapshot={snapshot} lang={lang} />
      )}
      <h2>{t(lang, "record.ledgerTitle")}</h2>
      <dl>
        <dt>{t(lang, "record.head")}</dt>
        <dd>
          <Txt fe={feKey("ledger", "-", "head")} value={ledger.head} />
        </dd>
        <dt>{t(lang, "record.rows")}</dt>
        <dd>{ledgerNum("rows", ledger.rows)}</dd>
        <dt>{t(lang, "record.lastId")}</dt>
        <dd>{ledgerNum("last_id", ledger.last_id)}</dd>
        <dt>{t(lang, "record.exportedAt")}</dt>
        <dd>
          <LocalTime iso={snapshot.generated_at} lang={lang} />
        </dd>
      </dl>
      <h2>{t(lang, "record.anchorTitle")}</h2>
      <dl>
        <dt>{t(lang, "record.anchorHistory")}</dt>
        <dd>
          <a href={`${LEDGER_HISTORY_URL}/${ledger.anchor.file}`}>
            <Txt fe={feKey("ledger", "-", "anchor.file")} value={ledger.anchor.file} />
          </a>
        </dd>
        <dt>{t(lang, "record.head")}</dt>
        <dd>
          <Txt fe={feKey("ledger", "-", "anchor.head")} value={ledger.anchor.head} />
        </dd>
        <dt>{t(lang, "record.rows")}</dt>
        <dd>{ledgerNum("anchor.rows", ledger.anchor.rows)}</dd>
        <dt>{t(lang, "record.lastId")}</dt>
        <dd>{ledgerNum("anchor.last_id", ledger.anchor.last_id)}</dd>
      </dl>
      {ledger.anchor.last_id === ledger.last_id ? (
        <p>{t(lang, "record.anchorMatches")}</p>
      ) : (
        <p>
          {t(lang, "record.anchorBehindBefore")}{" "}
          <Txt fe={feKey("ledger", "-", "anchor.file")} value={ledger.anchor.file} />{" "}
          {t(lang, "record.anchorBehindMiddle")} {ledgerNum("anchor.last_id", ledger.anchor.last_id)}
          {t(lang, "record.anchorBehindAfter")}
        </p>
      )}
      <h2>{t(lang, "record.contentHash")}</h2>
      <p>
        <Txt fe={feKey("root", "-", "content_sha256")} value={snapshot.content_sha256} />
      </p>
      <p>{t(lang, "record.commitment")}</p>
      <h2>{t(lang, "record.howTitle")}</h2>
      <ol>
        <li>{t(lang, "record.limit1")}</li>
        <li>{t(lang, "record.limit2")}</li>
        <li>{t(lang, "record.limit3")}</li>
      </ol>
      <JsonLdScript data={pageLd([breadcrumbLd(crumbs)])} />
    </main>
  );
}
```

- [ ] **Step 4: İki fixture'la duman**

Run:
```bash
source ~/.nvm/nvm.sh && nvm use 24 >/dev/null && export NEXT_TELEMETRY_DISABLED=1
SITE_SNAPSHOT="$PWD/web/fixtures/snapshot.fixture.web-full.json" pnpm -C web run build
node -e '
const h = require("fs").readFileSync("web/out/en/track-record/index.html", "utf8");
for (const n of ["data-fe=\"record:-:published\" data-fe-value=\"2\"", ">6.28%<", ">-4.76%<", ">2.20<",
  "covers the ledger up to row", "a commitment, not a verification", "Kuzeyspor – Güneyköy İdmanyurdu"])
  if (!h.includes(n)) { console.error("YOK:", n); process.exit(1); }
console.log("dolu ok");'
SITE_SNAPSHOT="$PWD/web/fixtures/snapshot.fixture.web-empty.json" pnpm -C web run build
node -e '
const h = require("fs").readFileSync("web/out/tr/track-record/index.html", "utf8");
for (const n of ["data-fe=\"record:-:published\" data-fe-value=\"0\"", "Temel modelimiz kapanış piyasasını geçmediği için",
  "Defter çıpa ile eşleşiyor.", "doğrulama değil taahhüttür"])
  if (!h.includes(n)) { console.error("YOK:", n); process.exit(1); }
for (const bad of ["<table", "Yakında", "yakında", "backtest"])
  if (h.replace(/<script[\s\S]*?<\/script>/g, "").includes(bad)) { console.error("VAR:", bad); process.exit(1); }
console.log("boş ok");'
```
Expected: `dolu ok`, `boş ok` (boş sicilde tablo, "yakında" ve backtest YOK — §6.2).

- [ ] **Step 5: Mutasyon kanıtı (dumanın ısırdığını göster)**

`page.tsx`de boş durum dalını `<p>{t(lang, "record.emptyExplain")}</p>` yerine `<p>{t(lang, "record.tableCaption")}</p>`
yap → boş-fixture dumanı `YOK: Temel modelimiz…` ile düşer. Geri al; `git diff --stat -- web/src` boş. (Sayfanın bütün
`data-fe` alanlarının kümesi ve metin eşitliği T9'da K1 süreciyle ölçülür.)

- [ ] **Step 6: Biçim, tip, test, tam kapı**

Run: `pnpm -C web exec biome check --write . && pnpm -C web exec biome ci . && pnpm -C web exec tsc --noEmit && pnpm -C web exec vitest run`
ve `verify.sh` (`b2-t6-gate.log`). Expected: vitest `50 passed`; taban PASS.

- [ ] **Step 7: Commit**

```bash
git add "web/src/app/[lang]/track-record/page.tsx" web/src/components/RecordTable.tsx
git commit -m "feat: sicil sayfası — boş durum, defter durumu, doğrulamanın sınırı (B-2 T6)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 18+ bildirimi ve yasal metin taslakları (avukat onayı bekler)

**Kademe:** K3 (metin; hukuk onayı ayrıca AK13) + K2 (18+ bileşeni ve onay deposu testli) · **Spec:** §10.1, §10.2, §10.3,
H2, H4, AK12, AK13, §12.4/6

Metinler TASLAKTIR ve hukuki görüş değildir; her dosya "TASLAK — avukat onayı bekler" başlığını taşır. Yardım hattı
iletişim bilgileri uydurulmaz: `[DOĞRULANACAK]`. KVKK'nın açık soruları `[AVUKAT SORUSU]` işaretlidir. Lisans olumsuzlaması
yalnız `data-fe-allow="license-negation"` öznitelikli paragrafta (H4). Yasal sayfalar taslak oldukları sürece bayraktan
bağımsız `noindex`tir ve site haritasına girmez (AK13, AK14 — `pageMetadata(..., false)`).

**Files:**
- Create: `web/src/lib/consent.ts`, `web/src/components/AgeGate.tsx`, `web/src/components/AgeGate.test.tsx`,
  `web/content/legal/en/{terms,privacy,cookies,responsible-gambling}.tsx`,
  `web/content/legal/tr/{terms,privacy,cookies,responsible-gambling}.tsx`, `web/content/legal/index.ts`,
  `web/content/legal/legal.test.ts`, `web/src/app/[lang]/legal/[doc]/page.tsx`
- Modify: `web/src/app/[lang]/layout.tsx` (tam dosya; `AgeGate` eklenir)

**Interfaces:**
- Consumes: T1 `LEGAL_DOCS`, `LegalDoc`; T3 sözlük `age.*`, `legal.*`; T4 `pageMetadata`, `legalPath`; T5 bileşenleri.
- Produces:
  ```ts
  // consent.ts
  export const CONSENT_KEY = "fe-age-18";
  export type ConsentStore = Pick<Storage, "getItem" | "setItem">;
  export function hasConsent(store: ConsentStore | null): boolean;   // atarsa false (kapı yeniden gösterilir)
  export function giveConsent(store: ConsentStore | null): boolean;
  // AgeGate.tsx ("use client")
  export type AgeGateLabels = { title: string; body: string; confirm: string; leave: string; strip: string };
  export function AgeGate(props: { labels: AgeGateLabels }): JSX.Element;  // SSR: <dialog> KAPALI + <noscript> şeridi
  // content/legal/index.ts
  export const LEGAL_CONTENT: Record<Lang, Record<LegalDoc, ComponentType>>;
  ```
  Yasal sayfa: `data-fe-page="legal:<doc>"`, tek `<h1>` (belge başlığı; içerik bölümleri `<h2>`).

- [ ] **Step 1: Başarısız testleri yaz**

`web/src/components/AgeGate.test.tsx`:
```tsx
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CONSENT_KEY, type ConsentStore, giveConsent, hasConsent } from "../lib/consent.ts";
import { AgeGate } from "./AgeGate.tsx";

const labels = { title: "T", body: "B", confirm: "C", leave: "L", strip: "STRIP-18" };

function memoryStore(): ConsentStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return { data, getItem: (key) => data.get(key) ?? null, setItem: (key, value) => void data.set(key, value) };
}

const throwing: ConsentStore = {
  getItem: () => {
    throw new Error("SecurityError");
  },
  setItem: () => {
    throw new Error("QuotaExceededError");
  },
};

describe("18+ kapısı (spec §10.2)", () => {
  it("sunucu çıktısında kapı gizli, içerik engellenmez, betiksiz şerit var", () => {
    const html = renderToStaticMarkup(createElement(AgeGate, { labels }));
    expect(html).toMatch(/<dialog\b/);
    expect(html).not.toMatch(/<dialog\b[^>]*\bopen\b/);
    expect(html).toContain("<noscript>");
    expect(html).toContain("STRIP-18");
  });

  it("onay yazılıp okunur", () => {
    const store = memoryStore();
    expect(hasConsent(store)).toBe(false);
    expect(giveConsent(store)).toBe(true);
    expect(store.data.get(CONSENT_KEY)).toBe("1");
    expect(hasConsent(store)).toBe(true);
  });

  it("depolama atarsa onay YOK sayılır (kapı yeniden gösterilir)", () => {
    expect(hasConsent(throwing)).toBe(false);
    expect(giveConsent(throwing)).toBe(false);
    expect(hasConsent(null)).toBe(false);
  });
});
```

`web/content/legal/legal.test.ts`:
```ts
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { LEGAL_DOCS, SITE_LANGS } from "../../site.config.ts";

const DIR = import.meta.dirname;
const read = (lang: string, doc: string) => readFileSync(resolve(DIR, lang, `${doc}.tsx`), "utf-8");

describe("yasal taslaklar (spec §10.1)", () => {
  it("her dilde dört belge var, fazlası yok", () => {
    for (const lang of SITE_LANGS) {
      const files = readdirSync(resolve(DIR, lang)).sort();
      expect(files).toEqual(LEGAL_DOCS.map((doc) => `${doc}.tsx`).sort());
    }
  });

  it.each(SITE_LANGS.flatMap((lang) => LEGAL_DOCS.map((doc) => [lang, doc] as const)))(
    "%s/%s 'TASLAK — avukat onayı bekler' başlığını taşır",
    (lang, doc) => {
      expect(read(lang, doc)).toContain("TASLAK — avukat onayı bekler");
    },
  );

  it("yardım hattı iletişim bilgileri [DOĞRULANACAK] işaretli", () => {
    for (const lang of SITE_LANGS) expect(read(lang, "responsible-gambling")).toContain("[DOĞRULANACAK]");
  });

  it("KVKK soruları avukat sorusu olarak işaretli", () => {
    for (const lang of SITE_LANGS) expect(read(lang, "privacy")).toContain("[AVUKAT SORUSU]");
  });

  it("lisans olumsuzlaması her dilin koşullarında tam bir kez işaretli (H4)", () => {
    for (const lang of SITE_LANGS) {
      expect(read(lang, "terms").split('data-fe-allow="license-negation"')).toHaveLength(2);
    }
  });
});
```

Run: `pnpm -C web exec vitest run src/components/AgeGate.test.tsx content/legal/legal.test.ts`
Expected: FAIL — `../lib/consent.ts` ve `content/legal/en` bulunamıyor.

- [ ] **Step 2: Onay deposu ve 18+ bileşeni**

`web/src/lib/consent.ts`:
```ts
// 18+ onayının yerel depolaması (spec §10.2). BU BİR YAŞ DOĞRULAMASI DEĞİLDİR (§12.4/6).
// Depolama erişimi atabilir (gizli pencere, kapalı site verisi): atarsa onay yok sayılır
// ve kapı yeniden gösterilir — yanlış yöne değil, güvenli yöne düşer.
export const CONSENT_KEY = "fe-age-18";

export type ConsentStore = Pick<Storage, "getItem" | "setItem">;

export function hasConsent(store: ConsentStore | null): boolean {
  try {
    return store?.getItem(CONSENT_KEY) === "1";
  } catch {
    return false;
  }
}

export function giveConsent(store: ConsentStore | null): boolean {
  try {
    store?.setItem(CONSENT_KEY, "1");
    return store !== null;
  } catch {
    return false;
  }
}
```

`web/src/components/AgeGate.tsx`:
```tsx
"use client";
// 18+ bildirimi (spec §10.2). Sunucu çıktısında `<dialog>` KAPALIdır (open yok): içerik
// HTML'de durur ve betiksiz tarayıcı `<noscript>` şeridini görür. Betik açıksa ve onay
// yoksa kapı açılır. Kipsiz bir bildirimdir; yaş doğrulaması DEĞİLDİR (§12.4/6).
import { useEffect, useState } from "react";
import { type ConsentStore, giveConsent, hasConsent } from "../lib/consent.ts";
import styles from "../styles/site.module.css";

export type AgeGateLabels = {
  title: string;
  body: string;
  confirm: string;
  leave: string;
  strip: string;
};

function browserStore(): ConsentStore | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function AgeGate({ labels }: { labels: AgeGateLabels }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setOpen(!hasConsent(browserStore()));
  }, []);
  return (
    <>
      <noscript>
        <p className={styles.ageStrip}>{labels.strip}</p>
      </noscript>
      <dialog open={open} aria-labelledby="age-gate-title" className={styles.ageGate}>
        <p id="age-gate-title" className={styles.ageTitle}>
          {labels.title}
        </p>
        <p>{labels.body}</p>
        <button
          type="button"
          onClick={() => {
            giveConsent(browserStore());
            setOpen(false);
          }}
        >
          {labels.confirm}
        </button>
        <button type="button" onClick={() => window.location.replace("about:blank")}>
          {labels.leave}
        </button>
      </dialog>
    </>
  );
}
```

- [ ] **Step 3: Yasal taslaklar (sekiz dosya) ve harita**

`web/content/legal/en/terms.tsx`:
```tsx
import styles from "../../../src/styles/site.module.css";

export default function Terms() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler (draft, pending legal review)</p>
      <h2>What this site is</h2>
      <p>
        This site is for information only. It shows market consensus probabilities derived from
        bookmaker prices that we record in a public, hash-chained ledger. It does not accept bets,
        does not direct visitors to any bookmaker and contains no links to betting operators.
      </p>
      <h2>No guarantee</h2>
      <p>
        Probabilities are estimates, not guarantees. Past performance does not predict future
        results. Nothing on this site is betting, financial or investment advice.
      </p>
      <h2>Data sources</h2>
      <p data-fe-allow="license-negation">
        We make no claim that our data is licensed, that it is official data, or that we are an
        official partner of any league, club or data provider.
      </p>
      <h2>Age</h2>
      <p>This site is intended for adults aged 18 or over.</p>
      <h2>Open questions for counsel</h2>
      <p>[AVUKAT SORUSU] Governing law, jurisdiction and liability limitation wording.</p>
    </article>
  );
}
```

`web/content/legal/tr/terms.tsx`:
```tsx
import styles from "../../../src/styles/site.module.css";

export default function Terms() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler</p>
      <h2>Bu site nedir</h2>
      <p>
        Bu site yalnız bilgi amaçlıdır. Herkese açık, hash zincirli bir defterde kaydettiğimiz
        bahis sitesi fiyatlarından türetilen piyasa konsensüs olasılıklarını gösterir. Bahis kabul
        etmez, ziyaretçiyi hiçbir bahis sitesine yönlendirmez ve bahis işletmecilerine bağlantı
        içermez.
      </p>
      <h2>Garanti yoktur</h2>
      <p>
        Olasılıklar tahmindir, garanti değildir. Geçmiş performans geleceği göstermez. Bu sitedeki
        hiçbir içerik bahis, finans ya da yatırım tavsiyesi değildir.
      </p>
      <h2>Veri kaynakları</h2>
      <p data-fe-allow="license-negation">
        Verilerimizin lisanslı olduğu, resmî veri olduğu ya da herhangi bir lig, kulüp veya veri
        sağlayıcının resmî ortağı olduğumuz yönünde hiçbir iddiada bulunmuyoruz.
      </p>
      <h2>Yaş</h2>
      <p>Bu site 18 yaşından büyükler içindir.</p>
      <h2>Avukata sorular</h2>
      <p>[AVUKAT SORUSU] Uygulanacak hukuk, yetkili mahkeme ve sorumluluk sınırlaması ifadesi.</p>
    </article>
  );
}
```

`web/content/legal/en/privacy.tsx`:
```tsx
import styles from "../../../src/styles/site.module.css";

export default function Privacy() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler (draft, pending legal review)</p>
      <h2>What we collect</h2>
      <p>
        We do not collect personal data. The site has no accounts, no forms, no newsletter, no
        comments and no analytics.
      </p>
      <h2>Hosting</h2>
      <p>
        The site is served as static files by a hosting provider, which may keep technical access
        logs (such as IP addresses) to operate its service.
      </p>
      <p>
        [AVUKAT SORUSU] Is the hosting provider a processor acting for us, or an independent
        controller for its own logs? Does serving the site from abroad amount to a cross-border
        transfer that needs a legal basis or notice?
      </p>
      <h2>Health data</h2>
      <p>We do not publish player health, injury or any other player-level information.</p>
      <h2>Local storage</h2>
      <p>
        Your browser stores a single entry recording that you confirmed you are 18 or older. It
        never leaves your device.
      </p>
    </article>
  );
}
```

`web/content/legal/tr/privacy.tsx`:
```tsx
import styles from "../../../src/styles/site.module.css";

export default function Privacy() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler</p>
      <h2>Hangi verileri topluyoruz</h2>
      <p>
        Kişisel veri toplamıyoruz. Sitede hesap, form, bülten, yorum ve analitik yoktur.
      </p>
      <h2>Barındırma</h2>
      <p>
        Site, bir barındırma sağlayıcısı tarafından statik dosyalar olarak sunulur; sağlayıcı
        hizmetini işletmek için teknik erişim kayıtları (ör. IP adresi) tutabilir.
      </p>
      <p>
        [AVUKAT SORUSU] Barındırma sağlayıcısı bizim adımıza veri işleyen mi, yoksa kendi
        kayıtları için ayrı bir veri sorumlusu mu? Sitenin yurt dışından sunulması KVKK anlamında
        yurt dışına aktarım sayılır mı; sayılırsa hangi hukuki dayanak ve aydınlatma gerekir?
      </p>
      <h2>Sağlık verisi</h2>
      <p>Oyuncu sağlık ya da sakatlık bilgisi ve oyuncu düzeyinde hiçbir bilgi yayımlamıyoruz.</p>
      <h2>Yerel depolama</h2>
      <p>
        Tarayıcınız yalnız 18 yaşından büyük olduğunuzu onayladığınızı kaydeden tek bir girdi
        saklar. Bu girdi cihazınızdan çıkmaz.
      </p>
    </article>
  );
}
```

`web/content/legal/en/cookies.tsx`:
```tsx
import styles from "../../../src/styles/site.module.css";

export default function Cookies() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler (draft, pending legal review)</p>
      <h2>Cookies</h2>
      <p>This site sets no cookies and uses no analytics or advertising trackers.</p>
      <h2>Strictly necessary local storage</h2>
      <p>
        When you confirm that you are 18 or older, your browser stores the entry
        <code>fe-age-18</code> so that the notice is not shown again. You can remove it at any time
        by clearing this site&apos;s data in your browser.
      </p>
    </article>
  );
}
```

`web/content/legal/tr/cookies.tsx`:
```tsx
import styles from "../../../src/styles/site.module.css";

export default function Cookies() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler</p>
      <h2>Çerezler</h2>
      <p>Bu site çerez kullanmaz; analitik ya da reklam izleyicisi yoktur.</p>
      <h2>Zorunlu yerel depolama</h2>
      <p>
        18 yaşından büyük olduğunuzu onayladığınızda tarayıcınız bildirimin tekrar gösterilmemesi
        için <code>fe-age-18</code> girdisini saklar. Tarayıcınızda bu sitenin verilerini silerek
        girdiyi istediğiniz an kaldırabilirsiniz.
      </p>
    </article>
  );
}
```

`web/content/legal/en/responsible-gambling.tsx`:
```tsx
import styles from "../../../src/styles/site.module.css";

export default function ResponsibleGambling() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler (draft, pending legal review)</p>
      <h2>18+ only</h2>
      <p>This site is for adults aged 18 or over. We do not accept bets.</p>
      <h2>Gambling can be addictive</h2>
      <p>
        Betting can lead to financial loss and addiction. Set limits, never chase losses and stop
        if gambling stops being fun.
      </p>
      <h2>Where to get help</h2>
      <p>
        Help is available in your country. Contact details below are placeholders and are checked
        against their primary sources before publication.
      </p>
      <ul>
        <li>United Kingdom: national gambling helpline [DOĞRULANACAK]</li>
        <li>Türkiye: Yeşilay advice line [DOĞRULANACAK]</li>
      </ul>
    </article>
  );
}
```

`web/content/legal/tr/responsible-gambling.tsx`:
```tsx
import styles from "../../../src/styles/site.module.css";

export default function ResponsibleGambling() {
  return (
    <article>
      <p className={styles.draft}>TASLAK — avukat onayı bekler</p>
      <h2>Yalnız 18+</h2>
      <p>Bu site 18 yaşından büyükler içindir. Bahis kabul etmiyoruz.</p>
      <h2>Bahis bağımlılık yapabilir</h2>
      <p>
        Bahis maddi kayba ve bağımlılığa yol açabilir. Sınır koyun, kaybı geri kazanmaya
        çalışmayın ve eğlence olmaktan çıktığında bırakın.
      </p>
      <h2>Nereden yardım alınır</h2>
      <p>
        Aşağıdaki iletişim bilgileri yer tutucudur; yayından önce birincil kaynaklarından
        doğrulanır.
      </p>
      <ul>
        <li>Yeşilay danışma hattı [DOĞRULANACAK]</li>
        <li>Yeşilay Danışmanlık Merkezi (YEDAM) [DOĞRULANACAK]</li>
      </ul>
    </article>
  );
}
```

`web/content/legal/index.ts`:
```ts
// Yasal taslakların tek haritası: dil × belge. Eksik bir hücre tip hatasıdır.
import type { ComponentType } from "react";
import type { Lang, LegalDoc } from "../../site.config.ts";
import EnCookies from "./en/cookies.tsx";
import EnPrivacy from "./en/privacy.tsx";
import EnResponsible from "./en/responsible-gambling.tsx";
import EnTerms from "./en/terms.tsx";
import TrCookies from "./tr/cookies.tsx";
import TrPrivacy from "./tr/privacy.tsx";
import TrResponsible from "./tr/responsible-gambling.tsx";
import TrTerms from "./tr/terms.tsx";

export const LEGAL_CONTENT: Record<Lang, Record<LegalDoc, ComponentType>> = {
  en: { terms: EnTerms, privacy: EnPrivacy, cookies: EnCookies, "responsible-gambling": EnResponsible },
  tr: { terms: TrTerms, privacy: TrPrivacy, cookies: TrCookies, "responsible-gambling": TrResponsible },
};
```

- [ ] **Step 4: Yasal rota ve 18+'lı kök yerleşim**

`web/src/app/[lang]/legal/[doc]/page.tsx`:
```tsx
// Yasal metin TASLAKLARI (spec §10.1): düz TSX, markdown yok. Taslak oldukları sürece
// bayraktan bağımsız olarak `noindex` ve site haritası dışıdır (AK13, AK14).
import { LEGAL_CONTENT } from "../../../../../content/legal/index.ts";
import { LEGAL_DOCS, type LegalDoc, SITE_LANGS } from "../../../../../site.config.ts";
import { Breadcrumbs } from "../../../../components/Breadcrumbs.tsx";
import { JsonLdScript } from "../../../../components/JsonLdScript.tsx";
import { t } from "../../../../i18n/dict.ts";
import { breadcrumbLd, pageLd } from "../../../../lib/jsonld.ts";
import { pageMetadata } from "../../../../lib/meta.ts";
import { langOf } from "../../../../lib/params.ts";
import { homePath, legalPath } from "../../../../lib/routes.ts";
import { notFound } from "next/navigation";

type Params = { params: Promise<{ lang: string; doc: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.flatMap((lang) => LEGAL_DOCS.map((doc) => ({ lang, doc })));
}

function docOf(value: string): LegalDoc {
  return LEGAL_DOCS.find((doc) => doc === value) ?? notFound();
}

export async function generateMetadata({ params }: Params) {
  const { lang: rawLang, doc: rawDoc } = await params;
  const lang = langOf(rawLang);
  const doc = docOf(rawDoc);
  return pageMetadata(lang, (each) => legalPath(each, doc), t(lang, `legal.${doc}`), false);
}

export default async function LegalPage({ params }: Params) {
  const { lang: rawLang, doc: rawDoc } = await params;
  const lang = langOf(rawLang);
  const doc = docOf(rawDoc);
  const Content = LEGAL_CONTENT[lang][doc];
  const crumbs = [
    { name: t(lang, "nav.home"), path: homePath(lang) },
    { name: t(lang, `legal.${doc}`), path: legalPath(lang, doc) },
  ];
  return (
    <main data-fe-page={`legal:${doc}`}>
      <Breadcrumbs crumbs={crumbs} label={t(lang, "nav.home")} />
      <h1>{t(lang, `legal.${doc}`)}</h1>
      <Content />
      <JsonLdScript data={pageLd([breadcrumbLd(crumbs)])} />
    </main>
  );
}
```

`web/src/app/[lang]/layout.tsx` (tam dosya):
```tsx
// Kök yerleşim dil bölütündedir: `<html lang>` sayfanın diliyle aynıdır (spec §5.3/8).
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SITE_LANGS, SITE_NAME } from "../../../site.config.ts";
import { AgeGate } from "../../components/AgeGate.tsx";
import { SiteFooter, SiteHeader } from "../../components/SiteChrome.tsx";
import { t } from "../../i18n/dict.ts";
import { langOf } from "../../lib/params.ts";
import styles from "../../styles/site.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return SITE_LANGS.map((lang) => ({ lang }));
}

export const metadata: Metadata = { title: { template: `%s · ${SITE_NAME}`, default: SITE_NAME } };

export default async function LangLayout(props: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const lang = langOf((await props.params).lang);
  const labels = {
    title: t(lang, "age.title"),
    body: t(lang, "age.body"),
    confirm: t(lang, "age.confirm"),
    leave: t(lang, "age.leave"),
    strip: t(lang, "age.strip"),
  };
  return (
    <html lang={lang}>
      <body className={styles.body}>
        <AgeGate labels={labels} />
        <SiteHeader lang={lang} />
        {props.children}
        <SiteFooter lang={lang} />
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Yeşil + tip + biçim**

Run: `pnpm -C web exec biome check --write . && pnpm -C web exec biome ci . && pnpm -C web exec tsc --noEmit && pnpm -C web exec vitest run`
Expected: vitest `65 passed` (50 + AgeGate 3 + yasal 12). Yer tutucu taraması artık `content/`i de tarar.

- [ ] **Step 6: Derleme dumanı (bayrak AÇIK varyantta bile yasal sayfa noindex)**

Run:
```bash
source ~/.nvm/nvm.sh && nvm use 24 >/dev/null && export NEXT_TELEMETRY_DISABLED=1
SITE_SNAPSHOT="$PWD/web/fixtures/snapshot.fixture.web-full.json" SITE_INDEXABLE=1 pnpm -C web run build
node -e '
const fs = require("fs");
const read = (p) => fs.readFileSync("web/out/" + p, "utf8");
const legal = read("tr/legal/terms/index.html");
for (const n of ["TASLAK — avukat onayı bekler", "data-fe-allow=\"license-negation\"", "<meta name=\"robots\" content=\"noindex\"/>",
  "data-fe-page=\"legal:terms\"", "<dialog", "<noscript>"])
  if (!legal.includes(n)) { console.error("YOK:", n); process.exit(1); }
if (/<dialog[^>]*\bopen\b/.test(legal)) { console.error("kapı sunucu çıktısında AÇIK"); process.exit(1); }
if (read("en/index.html").includes("name=\"robots\"")) { console.error("bayrak açıkken ana sayfa noindex"); process.exit(1); }
console.log("yasal ok");'
```
Expected: `● /[lang]/legal/[doc]` altında 8 yol; `yasal ok`.

- [ ] **Step 7: Mutasyon kanıtları**

1. `AgeGate.tsx`de `useState(false)` → `useState(true)` → "sunucu çıktısında kapı gizli" FAIL (betiksiz tarayıcıda içerik
   kapanırdı). Geri al.
2. `consent.ts` `hasConsent`in `catch` dalını `return true;` yap → "depolama atarsa onay YOK sayılır" FAIL. Geri al.
3. `tr/privacy.tsx`ten `TASLAK — avukat onayı bekler` başlık satırını sil → "tr/privacy … başlığını taşır" FAIL. Geri al.
4. `en/terms.tsx`teki `data-fe-allow="license-negation"` özniteliğini sil → "lisans olumsuzlaması … tam bir kez" FAIL (derlenmiş
   HTML'deki sayım T9'da ayrıca ölçülür). Geri al.
5. `en/responsible-gambling.tsx`de iki `[DOĞRULANACAK]`ı da gerçek görünümlü bir numarayla değiştir → "[DOĞRULANACAK]
   işaretli" FAIL. Geri al; `git diff --stat -- web` boş.

- [ ] **Step 8: Tam kapı** — `verify.sh` (`b2-t7-gate.log`) + WEB-KAPI; taban PASS.

- [ ] **Step 9: Commit**

```bash
git add web/src/lib/consent.ts web/src/components/AgeGate.tsx web/src/components/AgeGate.test.tsx \
  web/content/legal/en/terms.tsx web/content/legal/en/privacy.tsx web/content/legal/en/cookies.tsx \
  web/content/legal/en/responsible-gambling.tsx web/content/legal/tr/terms.tsx web/content/legal/tr/privacy.tsx \
  web/content/legal/tr/cookies.tsx web/content/legal/tr/responsible-gambling.tsx web/content/legal/index.ts \
  web/content/legal/legal.test.ts "web/src/app/[lang]/legal/[doc]/page.tsx" "web/src/app/[lang]/layout.tsx"
git commit -m "feat: 18+ bildirimi ve yasal metin taslakları — avukat onayı bekler (B-2 T7)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Site haritası, robots, `_headers` (CSP hash'leri), `_redirects`, `data/`, `netlify.toml`

**Kademe:** K2 (`_headers` üretimi; CSP'nin sayfa kapsamını ölçen kısım T9'da K1) · **Spec:** H7, B8, B9, §8.1 (`_redirects`,
zorlamasız 301, `/` → `/en/`), §8.4, §11, AK16, AK19 (a), AK20 (b), AK21

`emit-headers.ts` `next build`in ardından koşar; `pnpm run build` ikisini birlikte çağırır. ÇIPLAK `next build`
`_headers`/`_redirects`/`data/` üretmez — kapı ve `site.yml` yalnız `run build` kullanır (T10 testi).

**Files:**
- Create: `web/src/app/sitemap.ts`, `web/src/app/robots.ts`, `web/src/lib/pages.ts`, `web/src/lib/pages.test.ts`,
  `web/scripts/lib/html.ts`, `web/scripts/lib/html.test.ts`, `web/scripts/lib/outdir.ts`, `web/scripts/lib/emit.ts`,
  `web/scripts/lib/emit.test.ts`, `web/scripts/emit-headers.ts`, `web/netlify.toml`, `tests/test_site_web_netlify.py`
- Modify: `web/package.json` (`"build"` betiği)

**Interfaces:**
- Consumes: T2 `parseSnapshot`, T4 `routes.ts`, `absoluteUrl`, T1 `indexingEnabled`.
- Produces (T9 ve `site.yml`):
  ```ts
  // scripts/lib/html.ts — dar HTML okuyucusu (T9 da kullanır)
  export type Attrs = Record<string, string>; export type Script = { attrs: Attrs; body: string };
  export type Element = { tag: string; attrs: Attrs; text: string };
  export function parseAttrs(source: string): Attrs;          // ad küçük harfe katlanır (hrefLang → hreflang)
  export function decodeEntities(text: string): string;
  export function scripts(html: string): Script[]; export function scriptOpenings(html: string): number;
  export function isJsonLd(script: Script): boolean; export function isExecutableInline(script: Script): boolean;
  export function cspHash(body: string): string;              // "'sha256-<base64>'"
  export function stripScripts(html: string): string;
  export function feElements(html: string): Element[]; export function feOpenings(html: string): number;
  export function tags(html: string, tag: string): Attrs[];
  export function headingLevels(html: string): number[]; export function visibleText(html: string): string;
  // scripts/lib/outdir.ts
  export type PageFile = { path: string; file: string }; export const FRAMEWORK_PAGES: readonly string[]; // /404/, /_not-found/
  export function walk(dir: string): string[]; export function pageFiles(outDir: string): PageFile[];
  export function readText(file: string): string;
  // scripts/lib/emit.ts
  export type PageHashes = { path: string; hashes: string[] };
  export const SECURITY_HEADERS: readonly [string, string][];
  export function inlineHashes(html: string): string[]; export function csp(hashes: readonly string[]): string;
  export function headersFile(pages: readonly PageHashes[], indexable: boolean): string;
  export function redirectsFile(snapshot: Snapshot): string;
  export type SlugIndex = { version: 1; leagues: string[]; teams: string[] };
  export function slugIndex(snapshot: Snapshot): SlugIndex; export function sha256Hex(bytes: Buffer): string;
  // src/lib/pages.ts
  export type SitemapEntry = { url: string; alternates: { languages: Record<string, string> } };
  export function sitemapEntries(snapshot: Snapshot, enabled: boolean): SitemapEntry[];
  ```
  Çıktı: `out/_headers` (`/*` bloğu: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy: camera=(), microphone=(), geolocation=()`, bayrak kapalıyken `X-Robots-Tag: noindex`; her sayfa
  yolu için YALNIZ `Content-Security-Policy`), `out/_redirects`, `out/data/slugs.json`, `out/data/snapshot.sha256`.

- [ ] **Step 1: Başarısız testleri yaz**

`web/src/lib/pages.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { SITE_URL } from "../../site.config.ts";
import { fullFixture } from "./fixture.ts";
import { sitemapEntries } from "./pages.ts";

const snapshot = fullFixture();

describe("site haritası girdileri (spec §5.3/5, §8.4, H7)", () => {
  it("bayrak kapalıyken boş", () => {
    expect(sitemapEntries(snapshot, false)).toEqual([]);
  });

  it("bayrak açıkken yalnız indekslenebilir kayıtlar, her dilde, bütün dillere alternatif; yasal yok", () => {
    const entries = sitemapEntries(snapshot, true);
    const perLang =
      2 +
      snapshot.leagues.length +
      snapshot.teams.filter((team) => team.indexable).length +
      snapshot.matches.filter((match) => match.indexable).length;
    expect(entries).toHaveLength(2 * perLang);
    expect(entries.some((entry) => entry.url.includes("/legal/"))).toBe(false);
    for (const entry of entries) {
      expect(Object.keys(entry.alternates.languages).sort()).toEqual(["en", "tr"]);
      expect(entry.url.startsWith(`${SITE_URL}/`)).toBe(true);
    }
  });
});
```

`web/scripts/lib/html.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import {
  cspHash,
  decodeEntities,
  feElements,
  feOpenings,
  isExecutableInline,
  scriptOpenings,
  scripts,
  visibleText,
} from "./html.ts";

describe("dar HTML okuyucusu", () => {
  it("React'in kaçışlarını çözer (& ' \" < >)", () => {
    expect(decodeEntities("Doğu &amp; Batı &#x27;x&#x27; &quot;q&quot; &lt;&gt; &#39;")).toBe(
      "Doğu & Batı 'x' \"q\" <> '",
    );
  });

  it("data-fe öğesini, öznitelik adlarını küçük harfe katlayarak okur", () => {
    const html = '<p><span data-fe="a:b:c" data-fe-value="38">38.0%</span><time dateTime="x">t</time></p>';
    expect(feElements(html)).toEqual([
      { tag: "span", attrs: { "data-fe": "a:b:c", "data-fe-value": "38" }, text: "38.0%" },
    ]);
    expect(feOpenings(html)).toBe(1);
  });

  it("çocuğu metin olmayan data-fe öğesini OKUMAZ ama açılış sayımı onu görür", () => {
    const html = '<span data-fe="a:b:c" data-fe-value="1">1<!-- -->%</span>';
    expect(feElements(html)).toEqual([]);
    expect(feOpenings(html)).toBe(1);
  });

  it("betik sınıflandırması: src'li, JSON-LD ve yürütülebilir satır içi", () => {
    const html =
      '<script src="/a.js" async=""></script><script type="application/ld+json">{"a":1}</script><script>self.x=1</script>';
    const found = scripts(html);
    expect(found).toHaveLength(3);
    expect(scriptOpenings(html)).toBe(3);
    expect(found.map(isExecutableInline)).toEqual([false, false, true]);
    expect(cspHash("self.x=1")).toMatch(/^'sha256-[A-Za-z0-9+/]+=*'$/);
  });

  it("görünen metin betik ve yorum içermez", () => {
    expect(visibleText("<p>a<!-- x --></p><script>b</script><p>c &amp; d</p>").replace(/\s+/g, " ").trim()).toBe(
      "a c & d",
    );
  });
});
```

`web/scripts/lib/emit.test.ts`:
```ts
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
    const html = '<script type="application/ld+json">{}</script><script src="/a.js"></script><script>a()</script><script>a()</script>';
    expect(inlineHashes(html)).toHaveLength(1);
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
  });
});
```

`tests/test_site_web_netlify.py`:
```python
"""`web/netlify.toml`: hazır, bağlı değil (spec §11, B8, B9, AK16).

Netlify tarafında derleme reddedilir; başlık ve yönlendirme bu dosyada değil, derlemenin
ürettiği `out/_headers` / `out/_redirects`te (tek kaynak). Dosya secret ve ortam taşımaz.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
NETLIFY = REPO / "web/netlify.toml"


def _config() -> dict[str, Any]:
    return tomllib.loads(NETLIFY.read_text(encoding="utf-8"))


def test_only_the_build_table_with_publish_and_command() -> None:
    config = _config()
    assert set(config) == {"build"}, "başlık/yönlendirme/ortam netlify.toml'a girmez (B8)"
    assert set(config["build"]) == {"publish", "command"}
    assert config["build"]["publish"] == "out"


def test_a_netlify_side_build_refuses_by_name() -> None:
    result = subprocess.run(
        ["bash", "-c", _config()["build"]["command"]],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "derleme yapilmaz" in result.stderr
```

Run: `pnpm -C web exec vitest run src/lib/pages.test.ts scripts/lib && uv run pytest -q tests/test_site_web_netlify.py`
Expected: FAIL — `./pages.ts`, `./html.ts`, `./emit.ts` yüklenemiyor; pytest `FileNotFoundError: … web/netlify.toml`.

- [ ] **Step 2: Site haritası ve robots**

`web/src/lib/pages.ts`:
```ts
// Sitenin sayfa listesi, site haritası için. Çıktı tarayıcısı beklenen sayfaları BU
// modülü kullanmadan kendisi kurar (scripts/checkout/expect.ts): iki bağımsız liste
// birbirini denetler.
import { type Lang, SITE_LANGS } from "../../site.config.ts";
import { absoluteUrl, homePath, leaguePath, matchPath, teamPath, trackRecordPath } from "./routes.ts";
import type { Snapshot } from "./snapshot-types.ts";
import { leagueById } from "./snapshot.ts";

export type SitemapEntry = { url: string; alternates: { languages: Record<string, string> } };

type IndexablePage = { pathOf: (lang: Lang) => string; indexable: boolean };

function indexablePages(snapshot: Snapshot): IndexablePage[] {
  return [
    { pathOf: homePath, indexable: true },
    { pathOf: trackRecordPath, indexable: true },
    ...snapshot.leagues.map((league) => ({
      pathOf: (lang: Lang) => leaguePath(lang, league),
      indexable: true,
    })),
    ...snapshot.teams.map((team) => ({
      pathOf: (lang: Lang) => teamPath(lang, leagueById(snapshot, team.league_id), team),
      indexable: team.indexable,
    })),
    ...snapshot.matches.map((match) => ({
      pathOf: (lang: Lang) => matchPath(lang, leagueById(snapshot, match.league_id), match),
      indexable: match.indexable,
    })),
  ];
}

export function sitemapEntries(snapshot: Snapshot, enabled: boolean): SitemapEntry[] {
  if (!enabled) return [];
  return indexablePages(snapshot)
    .filter((page) => page.indexable)
    .flatMap((page) =>
      SITE_LANGS.map((lang) => ({
        url: absoluteUrl(page.pathOf(lang)),
        alternates: {
          languages: Object.fromEntries(
            SITE_LANGS.map((each) => [each, absoluteUrl(page.pathOf(each))]),
          ),
        },
      })),
    );
}
```

`web/src/app/sitemap.ts`:
```ts
// Site haritası (spec §5.3/5, §8.4): yalnız etkin olarak indekslenebilir sayfalar; her
// girdi bütün dillere `alternates` taşır. Bayrak kapalıyken BOŞTUR (her sayfa noindex).
import type { MetadataRoute } from "next";
import { indexingEnabled } from "../../site.config.ts";
import { sitemapEntries } from "../lib/pages.ts";
import { loadSnapshot } from "../lib/snapshot.ts";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return sitemapEntries(loadSnapshot(), indexingEnabled());
}
```

`web/src/app/robots.ts`:
```ts
// H7: `noindex` döneminde robots.txt `Disallow` TAŞIMAZ — taşırsa tarayıcı sayfayı hiç
// çekmez ve `noindex`i göremez.
import type { MetadataRoute } from "next";
import { absoluteUrl } from "../lib/routes.ts";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", allow: "/" }, sitemap: absoluteUrl("/sitemap.xml") };
}
```

- [ ] **Step 3: HTML okuyucusu, çıktı dizini, yayın dosyaları**

`web/scripts/lib/html.ts`:
```ts
// Bağımlılıksız, DAR bir HTML okuyucusu (spec §5.3). Genel bir ayrıştırıcı değildir:
// yalnız bu sitenin kendi ürettiği biçimi okur ve okuyamadığını adıyla raporlar.
// Kapsam sınırı: `data-fe` öğesinin çocuğu tek bir metin olmalıdır (Fe.tsx bunu garanti eder).
import { createHash } from "node:crypto";

export type Attrs = Record<string, string>;
export type Script = { attrs: Attrs; body: string };
export type Element = { tag: string; attrs: Attrs; text: string };

const ATTR = /([A-Za-z_:][-A-Za-z0-9_:.]*)(?:\s*=\s*"([^"]*)")?/g;
const SCRIPT = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
const FE_ELEMENT = /<([a-z][a-z0-9]*)\b([^>]*\bdata-fe="[^"]*"[^>]*)>([^<]*)<\/\1>/g;

// Öznitelik adları küçük harfe katlanır: React `hrefLang`, `dateTime`, `colSpan` basar.
export function parseAttrs(source: string): Attrs {
  const attrs: Attrs = {};
  for (const match of source.matchAll(ATTR)) {
    const name = match[1];
    if (name) attrs[name.toLowerCase()] = decodeEntities(match[2] ?? "");
  }
  return attrs;
}

export function decodeEntities(text: string): string {
  return text
    .replace(/&#x([0-9a-f]+);/gi, (_, hex: string) => String.fromCodePoint(Number.parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec: string) => String.fromCodePoint(Number.parseInt(dec, 10)))
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

export function scripts(html: string): Script[] {
  return [...html.matchAll(SCRIPT)].map((match) => ({
    attrs: parseAttrs(match[1] ?? ""),
    body: match[2] ?? "",
  }));
}

// `<script` açılışlarının bağımsız sayımı: `scripts()` birini kaçırırsa eşitlik bozulur.
export function scriptOpenings(html: string): number {
  return (html.match(/<script\b/gi) ?? []).length;
}

export function isJsonLd(script: Script): boolean {
  return script.attrs.type === "application/ld+json";
}

// Satır içi YÜRÜTÜLEBİLİR betik: `src` yok ve tip JS (yok, text/javascript ya da module).
export function isExecutableInline(script: Script): boolean {
  const type = script.attrs.type;
  const js = type === undefined || type === "" || type === "module" || type === "text/javascript";
  return script.attrs.src === undefined && js;
}

export function cspHash(body: string): string {
  return `'sha256-${createHash("sha256").update(body, "utf8").digest("base64")}'`;
}

export function stripScripts(html: string): string {
  return html.replace(SCRIPT, "");
}

export function feElements(html: string): Element[] {
  return [...stripScripts(html).matchAll(FE_ELEMENT)].map((match) => ({
    tag: match[1] ?? "",
    attrs: parseAttrs(match[2] ?? ""),
    text: decodeEntities(match[3] ?? ""),
  }));
}

// `data-fe` taşıyan açılış etiketi sayısı: `feElements` okuyamadığı biçimi atlarsa görünür.
export function feOpenings(html: string): number {
  return (stripScripts(html).match(/<[a-z][a-z0-9]*\b[^>]*\bdata-fe="/g) ?? []).length;
}

export function tags(html: string, tag: string): Attrs[] {
  const pattern = new RegExp(`<${tag}\\b([^>]*?)\\/?>`, "gi");
  return [...stripScripts(html).matchAll(pattern)].map((match) => parseAttrs(match[1] ?? ""));
}

export function headingLevels(html: string): number[] {
  return [...stripScripts(html).matchAll(/<h([1-6])\b/gi)].map((match) => Number(match[1]));
}

export function visibleText(html: string): string {
  const withoutCode = stripScripts(html).replace(/<style\b[\s\S]*?<\/style>/gi, "");
  return decodeEntities(withoutCode.replace(/<!--[\s\S]*?-->/g, "").replace(/<[^>]+>/g, " "));
}
```

`web/scripts/lib/outdir.ts`:
```ts
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
```

`web/scripts/lib/emit.ts`:
```ts
// Derleme SONRASI üretilen yayın dosyaları (spec §8.1, §11, AK19 a, AK20 b, AK21):
// `_headers` (CSP hash'leri, güvenlik başlıkları, bayrak kapalıyken X-Robots-Tag),
// `_redirects`, `data/slugs.json`, `data/snapshot.sha256`. Başlıklar TEK kaynaktan
// buradan gelir; `netlify.toml` başlık/yönlendirme taşımaz (B8).
import { createHash } from "node:crypto";
import { DEFAULT_LANG, SITE_LANGS } from "../../site.config.ts";
import { matchPath, matchStem } from "../../src/lib/routes.ts";
import type { Snapshot } from "../../src/lib/snapshot-types.ts";
import { cspHash, isExecutableInline, scripts } from "./html.ts";

export type PageHashes = { path: string; hashes: string[] };

export const SECURITY_HEADERS: readonly [string, string][] = [
  ["X-Content-Type-Options", "nosniff"],
  ["Referrer-Policy", "strict-origin-when-cross-origin"],
  ["Permissions-Policy", "camera=(), microphone=(), geolocation=()"],
];

export function inlineHashes(html: string): string[] {
  const hashes = scripts(html).filter(isExecutableInline).map((script) => cspHash(script.body));
  return [...new Set(hashes)].sort();
}

export function csp(hashes: readonly string[]): string {
  return [
    "default-src 'self'",
    `script-src 'self' ${hashes.join(" ")}`.trimEnd(),
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
  ].join("; ");
}

// CSP YALNIZ sayfa bloklarında: `/*` bloğunda ikinci bir CSP olsaydı tarayıcı ikisinin
// kesişimini uygular ve sayfa hash'leri geçersizleşirdi.
export function headersFile(pages: readonly PageHashes[], indexable: boolean): string {
  const global = [...SECURITY_HEADERS, ...(indexable ? [] : [["X-Robots-Tag", "noindex"]])];
  const blocks = [["/*", ...global.map(([name, value]) => `  ${name}: ${value}`)].join("\n")];
  for (const page of pages) {
    blocks.push(`${page.path}\n  Content-Security-Policy: ${csp(page.hashes)}`);
  }
  return `${blocks.join("\n\n")}\n`;
}

// Maç yolu kimlik taşır; isim bölütü değişirse eski URL zorlamasız 301 ile yeni yola
// gider. Güncel yol dosya olarak var olduğu için kural onu gölgelemez (spec §8.1).
export function redirectsFile(snapshot: Snapshot): string {
  const lines = [`/ /${DEFAULT_LANG}/ 301`];
  const leagues = new Map(snapshot.leagues.map((league) => [league.id, league]));
  for (const lang of SITE_LANGS) {
    for (const match of snapshot.matches) {
      const league = leagues.get(match.league_id);
      if (!league) throw new Error(`maçın ligi yok: ${match.id}`);
      lines.push(`${matchStem(lang, league, match)}* ${matchPath(lang, league, match)} 301`);
    }
  }
  return `${lines.join("\n")}\n`;
}

// Kaybolan-slug kontrolünün (AK20 b) deposu: bir sonraki yayın bununla karşılaştırılır.
export type SlugIndex = { version: 1; leagues: string[]; teams: string[] };

export function slugIndex(snapshot: Snapshot): SlugIndex {
  const slugOf = new Map(snapshot.leagues.map((league) => [league.id, league.slug]));
  return {
    version: 1,
    leagues: snapshot.leagues.map((league) => league.slug).sort(),
    teams: snapshot.teams.map((team) => `${slugOf.get(team.league_id)}/${team.slug}`).sort(),
  };
}

export function sha256Hex(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}
```

`web/scripts/emit-headers.ts`:
```ts
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
```

`web/package.json`de YALNIZ `"build"` satırı:
```json
    "build": "next build && node scripts/emit-headers.ts",
```

- [ ] **Step 4: `web/netlify.toml` (hazır, bağlı değil)**

```toml
# Netlify DERLEMEZ (spec §11, AK16): yayın yalnız `site.yml`in hazır `out/` dizinini
# Netlify CLI ile yüklemesidir. Netlify Git'e bağlanırsa aşağıdaki komut derlemeyi adıyla
# reddeder — DB kimliği Netlify'a hiç verilmez. Başlıklar ve yönlendirmeler burada DEĞİL,
# derlemenin ürettiği `out/_headers` ve `out/_redirects`tedir (tek kaynak, B8).
[build]
  publish = "out"
  command = "echo 'Netlify tarafinda derleme yapilmaz: yayin yalniz site.yml hazir dizini (spec 11, AK16)' >&2; exit 1"
```

- [ ] **Step 5: Yeşil + tip + biçim**

Run: `pnpm -C web exec biome check --write . && pnpm -C web exec biome ci . && pnpm -C web exec tsc --noEmit && pnpm -C web exec vitest run && uv run pytest -q tests/test_site_web_netlify.py`
Expected: vitest `78 passed` (65 + pages 2 + html 5 + emit 6); pytest `2 passed`. Yer tutucu taraması artık `scripts/`i de tarar.

- [ ] **Step 6: Derleme dumanı ve `_headers` ölçümü (iki bayrak)**

Run:
```bash
source ~/.nvm/nvm.sh && nvm use 24 >/dev/null && export NEXT_TELEMETRY_DISABLED=1
FULL="$PWD/web/fixtures/snapshot.fixture.web-full.json"
SITE_SNAPSHOT="$FULL" pnpm -C web run build
head -6 web/out/_headers; head -2 web/out/_redirects; cat web/out/robots.txt; grep -c "<url>" web/out/sitemap.xml
wc -c web/out/_headers; grep -c "^/.*/$" web/out/_headers
shasum -a 256 "$FULL" | cut -d" " -f1; cat web/out/data/snapshot.sha256
SITE_SNAPSHOT="$FULL" SITE_INDEXABLE=1 pnpm -C web run build
grep -c "X-Robots-Tag" web/out/_headers; grep -c "<url>" web/out/sitemap.xml
```
Expected (kazımada ölçülen): bayrak kapalı — `emit-headers: 40 sayfa, CSP + _redirects + data/`; `/*` bloğunda
`X-Robots-Tag: noindex`; `_redirects` ilk satırı `/ /en/ 301`; robots.txt `User-Agent: *` · `Allow: /` · `Sitemap: …`
(Disallow YOK); site haritasında `0` URL (`grep -c` 0 basar ve exit 1 verir — beklenen); `_headers` ≈ 31 KB, 40 sayfa bloğu
(sayfa başına ≈ 780 bayt); iki sha256 satırı eşit. Bayrak açık — `X-Robots-Tag` sayısı `0`, site haritasında `22` URL.
`_headers` boyutunu ve sayfa başına baytı görev raporuna yaz (AK19: gerçek anlık görüntünün sayfa sayısıyla çarpılıp
izlenir; eşik aşımı (b)'ye düşme kararı KULLANICININDIR).

- [ ] **Step 7: Mutasyon kanıtları**

1. `emit.ts` `headersFile`de `X-Robots-Tag` koşulunu kaldır (her zaman ekle) → emit testi "bayrak açıkken X-Robots-Tag yok"
   FAIL. Geri al.
2. `csp()`ye `"'unsafe-inline'"` ekle → "CSP unsafe-inline taşımaz" FAIL (AK19 (b) kullanıcı kararıdır). Geri al.
3. `html.ts` `isExecutableInline`da `script.attrs.src === undefined &&` koşulunu kaldır → "betik sınıflandırması" FAIL
   (src'li betik hash'lenirdi). Geri al.
4. `redirectsFile`de `301` → `301!` → "zorlamasız 301" FAIL. Geri al.
5. `pages.ts`de `.filter((page) => page.indexable)` kaldır → "yalnız indekslenebilir kayıtlar" FAIL. Geri al.
6. `web/netlify.toml`a `[[headers]]` tablosu ekle (`for = "/*"` + `[headers.values]` `X-Frame-Options = "DENY"`) →
   `test_only_the_build_table_with_publish_and_command` FAIL (B8 tek kaynak). Geri al; `git diff --stat -- web` boş.

- [ ] **Step 8: Tam kapı** — `verify.sh` (`b2-t8-gate.log`; pytest +2) + WEB-KAPI; taban PASS.

- [ ] **Step 9: Commit**

```bash
git add web/src/app/sitemap.ts web/src/app/robots.ts web/src/lib/pages.ts web/src/lib/pages.test.ts \
  web/scripts/lib/html.ts web/scripts/lib/html.test.ts web/scripts/lib/outdir.ts web/scripts/lib/emit.ts \
  web/scripts/lib/emit.test.ts web/scripts/emit-headers.ts web/package.json web/netlify.toml tests/test_site_web_netlify.py
git commit -m "feat: site haritası, robots, _headers (CSP hash'leri), _redirects, data/ ve bağlanmamış netlify.toml (B-2 T8)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Çıktı tarayıcısı — sayfa ↔ anlık görüntü, H4–H7, CSP, erişilebilirlik (K1)

**Kademe:** **K1** (spec §14: "çıktı tarayıcısının H6 (sayfa ↔ anlık görüntü) ve CSP kısmı … B-2'deki tarayıcı görevi de bu
süreçle işaretlenir") — TDD + mutasyonlu görev incelemesi (inceleyici kabukla gerçek derleme üzerinde kırma-geri-yükleme koşar;
bellek: "Reviewer needs a shell" → `general-purpose`) + bütün-dal incelemesi. · **Spec:** §5.3 (1)–(8), H1 (tarih kalıbı),
H4, H5b, H6c, H7, §6.1/§6.2 (sicil tutarlılığı), §8.3, §8.4, §9, AK19 (a), AK21, §18.5/2

Beklentiler sayfa kodundan BAĞIMSIZ kurulur (`scripts/checkout/expect.ts`): hangi sayfaların olacağı, her sayfada hangi
`data-fe` anahtarlarının olacağı ve her anahtarın biçimi tarayıcının kendi tablosundadır. Paylaşılan yalnız URL şeması
(`routes.ts`, T4'te testli) ve `format.ts`dir — spec: "`format` fonksiyonu tek yerdedir ve tarayıcı onu çağırarak H6c'yi sınar".

**Files:**
- Create: `web/scripts/checkout/expect.ts`, `web/scripts/checkout/checks.ts`, `web/scripts/checkout/checks.test.ts`,
  `web/scripts/check-out.ts`

**Interfaces:**
- Consumes: T8 `scripts/lib/{html,outdir}.ts`; T4 `routes.ts`; T3 `formatNumber`; T2 `parseSnapshot`, tipler.
- Produces:
  ```ts
  // expect.ts
  export type PageKind = "home" | "league" | "team" | "match" | "track-record" | "legal";
  export type ExpectedPage = { path: string; lang: Lang; kind: PageKind; id: string; recordIndexable: boolean;
    fields: string[]; ldTypes: string[]; paths: Record<Lang, string> };
  export type FieldKind = NumberKind | "text" | "attr";
  export function fieldKind(key: string): FieldKind | undefined;
  export function resolveField(snapshot: Snapshot, key: string): unknown;
  export function expectedPages(snapshot: Snapshot): ExpectedPage[];
  // checks.ts — her biri bulgu listesi döner (boş = geçti)
  export function checkPages(expected, built): string[];            // (1)
  export function checkFields(snapshot, page, html): string[];      // (2)(3) H6c
  export function checkHreflang(pages, built): string[];            // (4)
  export function checkIndexing(pages, built, sitemapXml, headers, robotsTxt, flag): string[];  // (5) + H7
  export function licenseFindings(where, text): string[]; export function countMarkers(text): number;  // H4
  export function secretFindings(where, text): string[];            // H5
  export function contentFindings(where, html, floor): string[];    // H1 tarih kalıbı + NaN/undefined/null
  export function checkCsp(page, html, headers): string[]; export function checkGlobalCsp(headers): string[];  // (7)
  export function checkA11y(page, html): string[];                  // (8)
  export function checkJsonLd(snapshot, page, html): string[];      // §9
  export function checkData(redirects, expectedRedirects, slugs, expectedSlugs, shaFile, digest): string[];
  export function parseHeaders(text: string): Map<string, [string, string][]>;
  ```
  CLI: `node web/scripts/check-out.ts --snapshot <dosya> --out <dizin>`; bayrak `SITE_INDEXABLE`den (derlemeyle aynı);
  her bulgu `BULGU: …` satırı; son satır `check-out: <N> sayfa, <M> bulgu (indexable=<bool>)`; bulgu varsa exit 1.

- [ ] **Step 1: Başarısız birim testlerini yaz — `web/scripts/checkout/checks.test.ts`**

```ts
// Her kontrolün kırmızıya döndüğü asgari girdi (kendi mutasyon kanıtları). Gerçek derleme
// üzerindeki kırma-geri-yükleme kanıtları planın Task 9 adımlarındadır.
import { describe, expect, it } from "vitest";
import { fullFixture } from "../../src/lib/fixture.ts";
import {
  checkA11y,
  checkCsp,
  checkFields,
  checkIndexing,
  checkJsonLd,
  checkPages,
  contentFindings,
  licenseFindings,
  parseHeaders,
  secretFindings,
} from "./checks.ts";
import { type ExpectedPage, expectedPages, fieldKind } from "./expect.ts";

const snapshot = fullFixture();
const pages = expectedPages(snapshot);
const page = (id: string, lang = "en"): ExpectedPage => {
  const found = pages.find((each) => each.id === id && each.lang === lang);
  if (!found) throw new Error(`beklenen sayfa yok: ${id}`);
  return found;
};
const match = snapshot.matches[0];
if (!match) throw new Error("fixture boş");
const matchPage = page(`match:${match.id}`);
const span = (key: string, value: string, text: string) =>
  `<span data-fe="${key}" data-fe-value="${value}">${text}</span>`;

describe("beklenen sayfalar", () => {
  it("her dil × (ana, sicil, 4 yasal, lig, takım, maç)", () => {
    const perLang = 2 + 4 + snapshot.leagues.length + snapshot.teams.length + snapshot.matches.length;
    expect(pages).toHaveLength(2 * perLang);
  });

  it("eşik altı tur alan üretmez; hareket yoksa hareket alanı yok", () => {
    const second = snapshot.matches.find((each) => each.h2h.opening === null);
    if (!second) throw new Error("fixture eşik altı açılış taşımıyor");
    const fields = page(`match:${second.id}`).fields;
    expect(fields.some((key) => key.includes("h2h.opening"))).toBe(false);
    expect(fields.some((key) => key.includes(":move."))).toBe(false);
  });

  it("bilinmeyen anahtarın biçimi yok", () => {
    expect(fieldKind(`match:${match.id}:h2h.opening.p.home`)).toBe("pct1");
    expect(fieldKind(`match:${match.id}:model_probability`)).toBeUndefined();
  });
});

describe("(1) sayfa ↔ kayıt", () => {
  it("fazla sayfa ve yanlış data-fe-page kırmızı", () => {
    const built = [
      { path: "/en/", html: '<main data-fe-page="league:x"></main>' },
      { path: "/en/extra/", html: "<main></main>" },
    ];
    const findings = checkPages([page("home")], built);
    expect(findings).toEqual([
      "/en/: <main data-fe-page> home değil",
      "/en/extra/: anlık görüntüde kaydı olmayan sayfa",
    ]);
  });
});

describe("(2)(3) H6c alanlar", () => {
  const key = `match:${match.id}:h2h.opening.p.home`;
  const opening = match.h2h.opening;
  if (!opening) throw new Error("fixture açılışı null");
  const good = span(key, String(opening.p.home), "45.7%");

  it("öznitelik ≠ değer kırmızı", () => {
    const findings = checkFields(snapshot, matchPage, span(key, "45.8", "45.7%"));
    expect(findings.some((f) => f.includes("özniteliği 45.8 ≠ 45.7"))).toBe(true);
  });

  it("metin ≠ format(değer) kırmızı (yuvarlanmış ya da yanlış ayraç)", () => {
    const findings = checkFields(snapshot, matchPage, span(key, "45.7", "46%"));
    expect(findings.some((f) => f.includes('metni "46%" ≠ "45.7%"'))).toBe(true);
  });

  it("eksik alan kırmızı (sayfa bir sayıyı hiç basmazsa)", () => {
    const findings = checkFields(snapshot, matchPage, good);
    expect(findings.some((f) => f.includes("data-fe kümesi eksik"))).toBe(true);
  });

  it("okunamayan data-fe öğesi kırmızı", () => {
    const findings = checkFields(snapshot, matchPage, `<span data-fe="${key}" data-fe-value="45.7">45.7<!-- -->%</span>`);
    expect(findings.some((f) => f.includes("okunamayan data-fe"))).toBe(true);
  });
});

describe("(5) + H7 indeksleme", () => {
  const home = page("home");
  const built = new Map([[home.path, '<meta name="robots" content="noindex"/>']]);
  const headers = parseHeaders("/*\n  X-Robots-Tag: noindex\n");

  it("bayrak kapalı: noindex + X-Robots-Tag + boş site haritası geçer", () => {
    expect(checkIndexing([home], built, "<urlset></urlset>", headers, "Allow: /", false)).toEqual([]);
  });

  it("robots.txt Disallow kırmızı", () => {
    const findings = checkIndexing([home], built, "<urlset></urlset>", headers, "Disallow: /", false);
    expect(findings).toContain("robots.txt: Disallow taşıyor (H7)");
  });

  it("bayrak kapalıyken indekslenebilir sayfa kırmızı", () => {
    const findings = checkIndexing([home], new Map([[home.path, ""]]), "<urlset></urlset>", headers, "", false);
    expect(findings.some((f) => f.includes("noindex=false"))).toBe(true);
  });
});

describe("(6) kalıplar", () => {
  it("H4: aksan ve büyük harf katlanır; işaretli olumsuzlama muaf", () => {
    expect(licenseFindings("p", "<p>RESMÎ VERİ kaynağı</p>")).toHaveLength(1);
    expect(licenseFindings("p", "<p>Lisanslı veri</p>")).toHaveLength(1);
    expect(licenseFindings("p", '<p data-fe-allow="license-negation">not licensed</p>')).toEqual([]);
  });

  it("H5: JWT öneki ve bağlantı dizesi", () => {
    expect(secretFindings("f", "x eyJhbGciOi y")).toHaveLength(1);
    expect(secretFindings("f", "postgresql://u@h/db")).toHaveLength(1);
  });

  it("H1: tabandan eski tarih (ISO ve GG.AA.YYYY) ve görünen 'undefined'", () => {
    expect(contentFindings("p", "<p>2026-07-01</p>", snapshot.floor)).toHaveLength(1);
    expect(contentFindings("p", "<p>01.07.2026</p>", snapshot.floor)).toHaveLength(1);
    expect(contentFindings("p", "<p>2026-07-02</p>", snapshot.floor)).toEqual([]);
    expect(contentFindings("p", "<p>NaN%</p>", snapshot.floor)).toHaveLength(1);
  });
});

describe("(7) CSP", () => {
  const headers = parseHeaders(
    `${matchPage.path}\n  Content-Security-Policy: default-src 'self'; script-src 'self' 'sha256-Z='\n`,
  );

  it("izin verilmeyen satır içi betik kırmızı", () => {
    expect(checkCsp(matchPage, "<script>a()</script>", headers)).toEqual([
      `${matchPage.path}: CSP'nin izin vermediği satır içi betik`,
    ]);
  });

  it("CSP'siz sayfa kırmızı", () => {
    expect(checkCsp(page("home"), "", headers)).toEqual(["/en/: 0 CSP başlığı"]);
  });
});

describe("(8) erişilebilirlik ve §9 JSON-LD", () => {
  it("lang uyuşmazlığı, iki h1, başlık atlaması, <main> yokluğu kırmızı", () => {
    const findings = checkA11y(matchPage, '<html lang="tr"><h1>a</h1><h1>b</h1><h3>c</h3>');
    expect(findings).toHaveLength(4);
  });

  it("iki JSON-LD bloğu ya da yanlış tür kırmızı", () => {
    const ld = (body: string) => `<script type="application/ld+json">${body}</script>`;
    expect(checkJsonLd(snapshot, matchPage, ld("{}") + ld("{}"))).toEqual([`${matchPage.path}: 2 JSON-LD bloğu`]);
    const wrong = ld(JSON.stringify({ "@graph": [{ "@type": "WebSite" }] }));
    expect(checkJsonLd(snapshot, matchPage, wrong)[0]).toContain("JSON-LD türleri");
  });
});
```

Run: `pnpm -C web exec vitest run scripts/checkout`
Expected: FAIL — `./checks.ts` ve `./expect.ts` yüklenemiyor.

- [ ] **Step 2: Beklentiler — `web/scripts/checkout/expect.ts`**

```ts
// Çıktı tarayıcısının BEKLENTİLERİ, sayfa kodundan bağımsız kurulur (spec §5.3): sayfa
// hangi alanı basarsa bassın, burada anlık görüntüden türetilen küme karşılaştırılır.
// Paylaşılan tek şeyler URL şeması (routes.ts) ve biçim (format.ts) — ikisi de kendi
// birim testleriyle sınanır.
import { LEGAL_DOCS, type Lang, SITE_LANGS } from "../../site.config.ts";
import type { NumberKind } from "../../src/lib/format.ts";
import {
  homePath,
  leaguePath,
  legalPath,
  matchPath,
  teamPath,
  trackRecordPath,
} from "../../src/lib/routes.ts";
import type { League, Match, Snapshot } from "../../src/lib/snapshot-types.ts";

export type PageKind = "home" | "league" | "team" | "match" | "track-record" | "legal";
export type ExpectedPage = {
  path: string;
  lang: Lang;
  kind: PageKind;
  id: string; // `data-fe-page` değeri
  recordIndexable: boolean;
  fields: string[]; // beklenen `data-fe` anahtarları
  ldTypes: string[]; // beklenen JSON-LD `@type` kümesi
  paths: Record<Lang, string>; // aynı kaydın her dildeki yolu (hreflang)
};
export type FieldKind = NumberKind | "text" | "attr";

const ROUNDS = ["opening", "latest", "closing"] as const;
const SIDES = ["home", "draw", "away"] as const;

// Anahtar → biçim. Tabloda olmayan anahtar bulgudur.
const FIELD_KINDS: readonly [string, RegExp, FieldKind][] = [
  ["match", /^h2h\.(opening|latest|closing)\.p\.(home|draw|away)$/, "pct1"],
  ["match", /^h2h\.(opening|latest|closing)\.books$/, "int"],
  ["match", /^move\.(home|draw|away)$/, "pp1"],
  ["match", /^rounds$/, "int"],
  ["match", /^sealed$/, "attr"],
  ["league", /^matches$/, "int"],
  ["league", /^move_distribution\.(p10|p50|p90)$/, "pp1"],
  ["team", /^matches$/, "int"],
  ["ledger", /^(rows|last_id|anchor\.rows|anchor\.last_id)$/, "int"],
  ["ledger", /^(head|anchor\.head|anchor\.file)$/, "text"],
  ["record", /^(published|summary\.n)$/, "int"],
  ["record", /^summary\.(mean_clv|ci_low|ci_high)$/, "pct2"],
  ["entry", /^(published_price|closing_fair_price)$/, "price2"],
  ["entry", /^clv$/, "pct2"],
  ["entry", /^publication_ledger_id$/, "int"],
  ["entry", /^(market|outcome|publication_hash)$/, "text"],
  ["root", /^content_sha256$/, "text"],
];

export function fieldKind(key: string): FieldKind | undefined {
  const [entity = "", , path = ""] = key.split(":");
  return FIELD_KINDS.find(([owner, pattern]) => owner === entity && pattern.test(path))?.[2];
}

function dig(value: unknown, path: string): unknown {
  let current = value;
  for (const part of path.split(".")) {
    if (current === null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

// `varlık:kimlik:yol` → anlık görüntüdeki değer; çözülemezse `undefined`.
export function resolveField(snapshot: Snapshot, key: string): unknown {
  const [entity, id = "", path = ""] = key.split(":");
  const owners: Record<string, unknown> = {
    match: snapshot.matches.find((match) => match.id === id),
    league: snapshot.leagues.find((league) => league.id === id),
    team: snapshot.teams.find((team) => `${team.league_id}/${team.slug}` === id),
    ledger: id === "-" ? snapshot.ledger : undefined,
    record: id === "-" ? snapshot.record : undefined,
    entry: snapshot.record.entries.find((entry) => String(entry.publication_id) === id),
    root: id === "-" ? snapshot : undefined,
  };
  return dig(owners[entity ?? ""], path);
}

function matchFields(match: Match): string[] {
  const key = (path: string) => `match:${match.id}:${path}`;
  const fields = [key("rounds"), key("sealed")];
  for (const round of ROUNDS) {
    if (match.h2h[round] === null) continue;
    fields.push(...SIDES.map((side) => key(`h2h.${round}.p.${side}`)), key(`h2h.${round}.books`));
  }
  if (match.move !== null) fields.push(...SIDES.map((side) => key(`move.${side}`)));
  return fields;
}

function leagueFields(league: League): string[] {
  const fields = [`league:${league.id}:matches`];
  if (league.move_distribution !== null) {
    fields.push(...["p10", "p50", "p90"].map((p) => `league:${league.id}:move_distribution.${p}`));
  }
  return fields;
}

function recordFields(snapshot: Snapshot): string[] {
  const ledger = ["rows", "last_id", "head", "anchor.file", "anchor.rows", "anchor.last_id"];
  const fields = [...ledger, "anchor.head"].map((path) => `ledger:-:${path}`);
  fields.push("record:-:published", "root:-:content_sha256");
  if (snapshot.record.summary !== null) {
    fields.push(...["n", "mean_clv", "ci_low", "ci_high"].map((p) => `record:-:summary.${p}`));
  }
  for (const entry of snapshot.record.entries) {
    const paths = ["market", "outcome", "published_price", "closing_fair_price", "clv"];
    paths.push("publication_ledger_id", "publication_hash");
    fields.push(...paths.map((path) => `entry:${entry.publication_id}:${path}`));
  }
  return fields;
}

function perLang(pathOf: (lang: Lang) => string): Record<Lang, string> {
  return Object.fromEntries(SITE_LANGS.map((lang) => [lang, pathOf(lang)])) as Record<Lang, string>;
}

type RecordSpec = Omit<ExpectedPage, "path" | "lang" | "paths"> & { pathOf: (lang: Lang) => string };

function records(snapshot: Snapshot): RecordSpec[] {
  const leagueOf = (id: string): League => {
    const league = snapshot.leagues.find((each) => each.id === id);
    if (!league) throw new Error(`lig yok: ${id}`);
    return league;
  };
  const crumbs = "BreadcrumbList";
  return [
    {
      kind: "home",
      id: "home",
      recordIndexable: true,
      fields: [],
      ldTypes: ["WebSite", crumbs],
      pathOf: homePath,
    },
    {
      kind: "track-record",
      id: "track-record",
      recordIndexable: true,
      fields: recordFields(snapshot),
      ldTypes: [crumbs],
      pathOf: trackRecordPath,
    },
    ...LEGAL_DOCS.map((doc): RecordSpec => ({
      kind: "legal",
      id: `legal:${doc}`,
      recordIndexable: false,
      fields: [],
      ldTypes: [crumbs],
      pathOf: (lang) => legalPath(lang, doc),
    })),
    ...snapshot.leagues.map((league): RecordSpec => ({
      kind: "league",
      id: `league:${league.id}`,
      recordIndexable: true,
      fields: leagueFields(league),
      ldTypes: ["SportsOrganization", crumbs],
      pathOf: (lang) => leaguePath(lang, league),
    })),
    ...snapshot.teams.map((team): RecordSpec => ({
      kind: "team",
      id: `team:${team.league_id}/${team.slug}`,
      recordIndexable: team.indexable,
      fields: [`team:${team.league_id}/${team.slug}:matches`],
      ldTypes: ["SportsTeam", crumbs],
      pathOf: (lang) => teamPath(lang, leagueOf(team.league_id), team),
    })),
    ...snapshot.matches.map((match): RecordSpec => ({
      kind: "match",
      id: `match:${match.id}`,
      recordIndexable: match.indexable,
      fields: matchFields(match),
      ldTypes: ["SportsEvent", crumbs],
      pathOf: (lang) => matchPath(lang, leagueOf(match.league_id), match),
    })),
  ];
}

export function expectedPages(snapshot: Snapshot): ExpectedPage[] {
  return records(snapshot).flatMap(({ pathOf, ...record }) =>
    SITE_LANGS.map((lang) => ({ ...record, lang, path: pathOf(lang), paths: perLang(pathOf) })),
  );
}
```

- [ ] **Step 3: Kontroller — `web/scripts/checkout/checks.ts`**

```ts
// Çıktı tarayıcısının kontrolleri (spec §5.3 (1)–(8), H4–H7, §9). Her fonksiyon bulgu
// listesi döner; boş liste = geçti. Bulgu metni sayfa yolunu ve neyin tuttuğunu adlandırır.
import { DEFAULT_LANG, SITE_LANGS } from "../../site.config.ts";
import { formatNumber } from "../../src/lib/format.ts";
import { absoluteUrl } from "../../src/lib/routes.ts";
import type { Snapshot } from "../../src/lib/snapshot-types.ts";
import {
  cspHash,
  feElements,
  feOpenings,
  headingLevels,
  isExecutableInline,
  isJsonLd,
  scriptOpenings,
  scripts,
  tags,
  visibleText,
} from "../lib/html.ts";
import { type ExpectedPage, fieldKind, resolveField } from "./expect.ts";

export type Built = { path: string; html: string };
export type Headers = Map<string, [string, string][]>;

function sameSet(a: readonly string[], b: readonly string[]): boolean {
  const left = [...a].sort();
  const right = [...b].sort();
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

// (1) her kayıt için tam bir sayfa, her sayfa için tam bir kayıt; sayfa kendi kaydını söyler.
export function checkPages(expected: readonly ExpectedPage[], built: readonly Built[]): string[] {
  const findings: string[] = [];
  const byPath = new Map(built.map((page) => [page.path, page]));
  const wanted = new Set(expected.map((page) => page.path));
  if (wanted.size !== expected.length) findings.push("iki kayıt aynı yola düşüyor");
  for (const page of expected) {
    const html = byPath.get(page.path)?.html;
    if (html === undefined) {
      findings.push(`${page.path}: kaydın sayfası yok (${page.id})`);
      continue;
    }
    const mains = tags(html, "main");
    if (mains.length !== 1 || mains[0]?.["data-fe-page"] !== page.id) {
      findings.push(`${page.path}: <main data-fe-page> ${page.id} değil`);
    }
  }
  for (const page of built) {
    if (!wanted.has(page.path)) findings.push(`${page.path}: anlık görüntüde kaydı olmayan sayfa`);
  }
  return findings;
}

// (2)(3) H6c: öznitelik = anlık görüntü değeri birebir; görünen metin = format(değer).
export function checkFields(snapshot: Snapshot, page: ExpectedPage, html: string): string[] {
  const findings: string[] = [];
  const elements = feElements(html);
  if (elements.length !== feOpenings(html)) {
    findings.push(`${page.path}: okunamayan data-fe öğesi (çocuk tek metin değil)`);
  }
  const seen = elements.map((element) => element.attrs["data-fe"] ?? "");
  if (!sameSet([...new Set(seen)], page.fields)) {
    const missing = page.fields.filter((key) => !seen.includes(key));
    const extra = [...new Set(seen)].filter((key) => !page.fields.includes(key));
    findings.push(`${page.path}: data-fe kümesi eksik ${missing.join(",")} fazla ${extra.join(",")}`);
  }
  for (const element of elements) {
    const key = element.attrs["data-fe"] ?? "";
    const kind = fieldKind(key);
    const value = resolveField(snapshot, key);
    if (kind === undefined || value === undefined || value === null) {
      findings.push(`${page.path}: çözülemeyen alan ${key}`);
      continue;
    }
    if (element.attrs["data-fe-value"] !== String(value)) {
      findings.push(`${page.path}: ${key} özniteliği ${element.attrs["data-fe-value"]} ≠ ${String(value)}`);
    }
    if (kind === "attr") continue;
    const shown = kind === "text" ? String(value) : formatNumber(value as number, kind, page.lang);
    if (element.text !== shown) findings.push(`${page.path}: ${key} metni "${element.text}" ≠ "${shown}"`);
  }
  return findings;
}

type Alternate = { lang: string; href: string };

function alternates(html: string): Alternate[] {
  return tags(html, "link")
    .filter((link) => link.rel === "alternate" && link.hreflang !== undefined)
    .map((link) => ({ lang: link.hreflang ?? "", href: link.href ?? "" }));
}

// (4) hreflang: bütün diller + x-default, kendine atıflı, karşılıklı; kanonik = kendi URL'si.
export function checkHreflang(pages: readonly ExpectedPage[], built: Map<string, string>): string[] {
  const findings: string[] = [];
  for (const page of pages) {
    const html = built.get(page.path);
    if (html === undefined) continue; // checkPages zaten raporlar
    const links = alternates(html);
    const want = [...SITE_LANGS, "x-default"];
    if (!sameSet(links.map((link) => link.lang), want)) {
      findings.push(`${page.path}: hreflang dilleri ${links.map((link) => link.lang).join(",")}`);
      continue;
    }
    const href = (lang: string) => links.find((link) => link.lang === lang)?.href;
    if (href(page.lang) !== absoluteUrl(page.path)) findings.push(`${page.path}: hreflang kendine atıflı değil`);
    if (href("x-default") !== absoluteUrl(page.paths[DEFAULT_LANG])) findings.push(`${page.path}: x-default yanlış`);
    const canonical = tags(html, "link").find((link) => link.rel === "canonical")?.href;
    if (canonical !== absoluteUrl(page.path)) findings.push(`${page.path}: kanonik ${canonical ?? "yok"}`);
    for (const lang of SITE_LANGS) {
      const target = page.paths[lang];
      if (href(lang) !== absoluteUrl(target)) {
        findings.push(`${page.path}: hreflang ${lang} ${href(lang)} ≠ ${absoluteUrl(target)}`);
        continue;
      }
      const back = alternates(built.get(target) ?? "").find((link) => link.lang === page.lang);
      if (back?.href !== absoluteUrl(page.path)) findings.push(`${page.path}: ${target} geri bağlanmıyor`);
    }
  }
  return findings;
}

const effective = (page: ExpectedPage, flag: boolean) => flag && page.recordIndexable;

// (5) + H7: noindex meta ↔ etkin indekslenebilirlik birebir; site haritası = indekslenebilir
// sayfa kümesi (her girdide bütün diller); bayrak kapalıyken X-Robots-Tag; robots.txt Disallow'suz.
export function checkIndexing(
  pages: readonly ExpectedPage[],
  built: Map<string, string>,
  sitemapXml: string,
  headers: Headers,
  robotsTxt: string,
  flag: boolean,
): string[] {
  const findings: string[] = [];
  for (const page of pages) {
    const html = built.get(page.path);
    if (html === undefined) continue;
    const robots = tags(html, "meta").find((meta) => meta.name === "robots");
    const noindex = (robots?.content ?? "").split(/[\s,]+/).includes("noindex");
    if (noindex === effective(page, flag)) {
      findings.push(`${page.path}: noindex=${noindex}, beklenen indekslenebilir=${effective(page, flag)}`);
    }
  }
  const urls = [...sitemapXml.matchAll(/<url>([\s\S]*?)<\/url>/g)].map((match) => match[1] ?? "");
  const locs = urls.map((url) => /<loc>([^<]*)<\/loc>/.exec(url)?.[1] ?? "");
  const want = pages.filter((page) => effective(page, flag)).map((page) => absoluteUrl(page.path));
  if (!sameSet(locs, want)) findings.push(`sitemap.xml: ${locs.length} URL, beklenen ${want.length}`);
  for (const url of urls) {
    const langs = [...url.matchAll(/hreflang="([^"]+)"/g)].map((match) => match[1] ?? "");
    if (!sameSet(langs, [...SITE_LANGS])) findings.push(`sitemap.xml: alternates eksik ${url.slice(0, 80)}`);
  }
  const robotsTag = (headers.get("/*") ?? []).some(([name, value]) => name === "X-Robots-Tag" && value === "noindex");
  if (robotsTag === flag) findings.push(`_headers: X-Robots-Tag noindex=${robotsTag}, bayrak=${flag}`);
  if (/^\s*disallow\s*:\s*\S/im.test(robotsTxt)) findings.push("robots.txt: Disallow taşıyor (H7)");
  return findings;
}

// Karşılaştırma için katlama: aksan düşer, Türkçe ı/İ düzleşir, küçük harf.
export function fold(text: string): string {
  return text.normalize("NFKD").replace(/\p{M}/gu, "").replace(/ı/g, "i").toLowerCase();
}

// Spec H4'teki liste; katlama "resmi/resmî" çiftlerini tek kalıba indirir.
export const LICENSE_PATTERNS = [
  "lisanslı",
  "licensed",
  "resmi veri",
  "resmî veri",
  "official data",
  "official partner",
  "resmi ortak",
  "resmî ortak",
  "authorized",
  "yetkili veri",
]
  .map(fold)
  .filter((pattern, index, all) => all.indexOf(pattern) === index);
export const SECRET_PATTERNS = ["postgres://", "postgresql://", "service_role", "eyJ", "SUPABASE_", "NETLIFY_AUTH"];
const ALLOWED = /<([a-z]+)\b[^>]*\bdata-fe-allow="license-negation"[^>]*>[\s\S]*?<\/\1>/g;
export const ALLOW_MARKER = 'data-fe-allow="license-negation"';

// H4: lisans iddiası yok (işaretli olumsuz cümle hariç); işaret sayısı kaynak = derlenmiş.
export function licenseFindings(where: string, text: string): string[] {
  const folded = fold(text.replace(ALLOWED, " "));
  return LICENSE_PATTERNS.filter((pattern) => folded.includes(pattern)).map(
    (pattern) => `${where}: lisans iddiası kalıbı "${pattern}" (H4)`,
  );
}

export function countMarkers(text: string): number {
  return text.split(ALLOW_MARKER).length - 1;
}

// H5: anahtar kalıpları hiçbir çıktı dosyasında yok.
export function secretFindings(where: string, text: string): string[] {
  return SECRET_PATTERNS.filter((pattern) => text.includes(pattern)).map(
    (pattern) => `${where}: gizli anahtar kalıbı "${pattern}" (H5)`,
  );
}

// H1 (§12.4/4 sınırı: yalnız tarih kalıbı): tabandan eski ISO ya da GG.AA.YYYY tarih yok;
// görünen metinde "NaN"/"undefined"/"null" yok (boş değer sayı gibi basılmış olurdu).
export function contentFindings(where: string, html: string, floor: string): string[] {
  const findings: string[] = [];
  const floorDay = floor.slice(0, 10);
  for (const match of html.matchAll(/\b(\d{4})-(\d{2})-(\d{2})\b/g)) {
    if (match[0] < floorDay) findings.push(`${where}: tabandan eski tarih ${match[0]} (H1)`);
  }
  for (const match of html.matchAll(/\b(\d{2})\.(\d{2})\.(\d{4})\b/g)) {
    const iso = `${match[3]}-${match[2]}-${match[1]}`;
    if (iso < floorDay) findings.push(`${where}: tabandan eski tarih ${match[0]} (H1)`);
  }
  const word = /\b(NaN|undefined|null)\b/.exec(visibleText(html));
  if (word) findings.push(`${where}: görünen metinde "${word[1]}"`);
  return findings;
}

// (7) CSP: her yürütülebilir satır içi betiğin hash'i sayfanın CSP'sinde; JSON-LD hash'i
// listede DEĞİL; CSP yalnız sayfa bloğunda, tam bir kez; `/*`de CSP yok.
export function checkCsp(page: ExpectedPage, html: string, headers: Headers): string[] {
  const findings: string[] = [];
  const all = scripts(html);
  if (all.length !== scriptOpenings(html)) findings.push(`${page.path}: okunamayan <script> etiketi`);
  const policies = (headers.get(page.path) ?? []).filter(([name]) => name === "Content-Security-Policy");
  if (policies.length !== 1) {
    findings.push(`${page.path}: ${policies.length} CSP başlığı`);
    return findings;
  }
  const scriptSrc = (policies[0]?.[1] ?? "").split(";").map((part) => part.trim()).find((part) => part.startsWith("script-src"));
  const allowed = new Set((scriptSrc ?? "").split(/\s+/));
  for (const script of all.filter(isExecutableInline)) {
    if (!allowed.has(cspHash(script.body))) findings.push(`${page.path}: CSP'nin izin vermediği satır içi betik`);
  }
  for (const script of all.filter(isJsonLd)) {
    if (allowed.has(cspHash(script.body))) findings.push(`${page.path}: JSON-LD hash'i CSP'de (gereksiz)`);
  }
  return findings;
}

export function checkGlobalCsp(headers: Headers): string[] {
  const global = headers.get("/*") ?? [];
  return global.some(([name]) => name === "Content-Security-Policy") ? ["_headers: /* bloğunda CSP"] : [];
}

// (8) basit erişilebilirlik.
export function checkA11y(page: ExpectedPage, html: string): string[] {
  const findings: string[] = [];
  const lang = /<html\b[^>]*\blang="([^"]*)"/.exec(html)?.[1];
  if (lang !== page.lang) findings.push(`${page.path}: <html lang="${lang ?? ""}"> ≠ ${page.lang}`);
  const levels = headingLevels(html);
  if (levels.filter((level) => level === 1).length !== 1) findings.push(`${page.path}: tek <h1> yok`);
  if (levels[0] !== 1) findings.push(`${page.path}: ilk başlık h1 değil`);
  for (let index = 1; index < levels.length; index += 1) {
    const [previous = 0, level = 0] = [levels[index - 1], levels[index]];
    if (level > previous + 1) findings.push(`${page.path}: h${previous}→h${level} atlıyor`);
  }
  if (tags(html, "main").length !== 1) findings.push(`${page.path}: tek <main> yok`);
  if (tags(html, "img").some((img) => img.alt === undefined)) findings.push(`${page.path}: alt'sız <img>`);
  return findings;
}

// §9: sayfa başına TEK JSON-LD bloğu; ayrışır; `@graph` türleri beklenen; maçta teklif/oran
// yok; `eventStatus` yalnız başlama anı dışa aktarım anından sonraysa.
export function checkJsonLd(snapshot: Snapshot, page: ExpectedPage, html: string): string[] {
  const blocks = scripts(html).filter(isJsonLd);
  if (blocks.length !== 1) return [`${page.path}: ${blocks.length} JSON-LD bloğu`];
  let data: { "@graph"?: Record<string, unknown>[] };
  try {
    data = JSON.parse(blocks[0]?.body ?? "");
  } catch {
    return [`${page.path}: JSON-LD ayrışmıyor`];
  }
  const graph = data["@graph"] ?? [];
  const findings: string[] = [];
  const types = graph.map((node) => String(node["@type"]));
  if (!sameSet(types, page.ldTypes)) findings.push(`${page.path}: JSON-LD türleri ${types.join(",")}`);
  if (page.kind === "match") {
    const event = graph.find((node) => node["@type"] === "SportsEvent") ?? {};
    const match = snapshot.matches.find((each) => `match:${each.id}` === page.id);
    const future = match !== undefined && Date.parse(match.commence_time) > Date.parse(snapshot.generated_at);
    if (("eventStatus" in event) !== future) findings.push(`${page.path}: eventStatus ${future ? "eksik" : "fazla"}`);
    for (const banned of ["offers", "location", "odds"]) {
      if (banned in event) findings.push(`${page.path}: SportsEvent '${banned}' taşıyor`);
    }
  }
  return findings;
}

// Yayın dosyaları: `_redirects`, `data/slugs.json`, `data/snapshot.sha256`.
export function checkData(
  redirects: string,
  expectedRedirects: string,
  slugs: string,
  expectedSlugs: string,
  shaFile: string,
  digest: string,
): string[] {
  const findings: string[] = [];
  if (redirects !== expectedRedirects) findings.push("_redirects beklenenden farklı");
  if (/ 301!$/m.test(redirects)) findings.push("_redirects zorlamalı 301! taşıyor");
  if (slugs !== expectedSlugs) findings.push("data/slugs.json beklenenden farklı");
  if (shaFile.split(/\s+/)[0] !== digest) findings.push("data/snapshot.sha256 dosya baytlarıyla eşleşmiyor");
  return findings;
}

export function parseHeaders(text: string): Headers {
  const headers: Headers = new Map();
  let current: string | undefined;
  for (const line of text.split("\n")) {
    if (line.trim() === "") continue;
    if (!/^\s/.test(line)) {
      current = line.trim();
      headers.set(current, []);
    } else if (current !== undefined) {
      const index = line.indexOf(":");
      headers.get(current)?.push([line.slice(0, index).trim(), line.slice(index + 1).trim()]);
    }
  }
  return headers;
}
```

- [ ] **Step 4: Birim testleri yeşil**

Run: `pnpm -C web exec vitest run scripts/checkout && pnpm -C web exec tsc --noEmit`
Expected: `18 passed`; tsc çıktısız.

- [ ] **Step 5: CLI — `web/scripts/check-out.ts`**

```ts
// Çıktı tarayıcısı (spec §5.3). Kullanım:
//   node scripts/check-out.ts --snapshot <snapshot.json> --out <derlenmiş dizin>
// Bayrak derlemeyle AYNI ortamdan okunur (SITE_INDEXABLE). Bulgu varsa exit 1.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { DEFAULT_LANG, indexingEnabled, SITE_LANGS } from "../site.config.ts";
import { matchPath, matchStem } from "../src/lib/routes.ts";
import { parseSnapshot } from "../src/lib/snapshot.ts";
import type { Snapshot } from "../src/lib/snapshot-types.ts";
import {
  checkA11y,
  checkCsp,
  checkData,
  checkFields,
  checkGlobalCsp,
  checkHreflang,
  checkIndexing,
  checkJsonLd,
  checkPages,
  contentFindings,
  countMarkers,
  licenseFindings,
  parseHeaders,
  secretFindings,
} from "./checkout/checks.ts";
import { expectedPages } from "./checkout/expect.ts";
import { stripScripts } from "./lib/html.ts";
import { pageFiles, readText, walk } from "./lib/outdir.ts";

const CONTENT = resolve(import.meta.dirname, "../content");
const TEXT_FILE = /\.(html|txt|xml|json|js|css|sha256)$|\/_headers$|\/_redirects$/;

function arg(name: string): string {
  const index = process.argv.indexOf(name);
  const value = index >= 0 ? process.argv[index + 1] : undefined;
  if (!value) throw new Error(`check-out: ${name} eksik`);
  return resolve(value);
}

function optional(file: string): string {
  return existsSync(file) ? readText(file) : "";
}

function expectedRedirects(snapshot: Snapshot): string {
  const lines = [`/ /${DEFAULT_LANG}/ 301`];
  for (const lang of SITE_LANGS) {
    for (const match of snapshot.matches) {
      const league = snapshot.leagues.find((each) => each.id === match.league_id);
      if (league) lines.push(`${matchStem(lang, league, match)}* ${matchPath(lang, league, match)} 301`);
    }
  }
  return `${lines.join("\n")}\n`;
}

function expectedSlugs(snapshot: Snapshot): string {
  const slugOf = new Map(snapshot.leagues.map((league) => [league.id, league.slug]));
  const index = {
    version: 1,
    leagues: snapshot.leagues.map((league) => league.slug).sort(),
    teams: snapshot.teams.map((team) => `${slugOf.get(team.league_id)}/${team.slug}`).sort(),
  };
  return `${JSON.stringify(index, null, 2)}\n`;
}

function main(): number {
  const snapshotFile = arg("--snapshot");
  const out = arg("--out");
  const bytes = readFileSync(snapshotFile);
  const snapshot = parseSnapshot(bytes.toString("utf-8"));
  const flag = indexingEnabled();
  const expected = expectedPages(snapshot);
  const built = pageFiles(out).map((page) => ({ path: page.path, html: readText(page.file) }));
  const byPath = new Map(built.map((page) => [page.path, page.html]));
  const headers = parseHeaders(optional(join(out, "_headers")));

  const findings = [
    ...checkPages(expected, built),
    ...checkHreflang(expected, byPath),
    ...checkIndexing(expected, byPath, optional(join(out, "sitemap.xml")), headers, optional(join(out, "robots.txt")), flag),
    ...checkGlobalCsp(headers),
    ...checkData(
      optional(join(out, "_redirects")),
      expectedRedirects(snapshot),
      optional(join(out, "data/slugs.json")),
      expectedSlugs(snapshot),
      optional(join(out, "data/snapshot.sha256")),
      createHash("sha256").update(bytes).digest("hex"),
    ),
  ];
  let htmlMarkers = 0;
  for (const page of expected) {
    const html = byPath.get(page.path);
    if (html === undefined) continue;
    findings.push(
      ...checkFields(snapshot, page, html),
      ...checkCsp(page, html, headers),
      ...checkA11y(page, html),
      ...checkJsonLd(snapshot, page, html),
      ...licenseFindings(page.path, stripScripts(html)),
      ...contentFindings(page.path, html, snapshot.floor),
    );
    htmlMarkers += countMarkers(stripScripts(html));
  }
  let sourceMarkers = 0;
  for (const file of walk(CONTENT).filter((each) => /\.tsx?$/.test(each) && !/\.test\.tsx?$/.test(each))) {
    const text = readText(file);
    findings.push(...licenseFindings(file, text));
    sourceMarkers += countMarkers(text);
  }
  if (sourceMarkers !== htmlMarkers) {
    findings.push(`H4 işaret sayısı: kaynak ${sourceMarkers} ≠ derlenmiş ${htmlMarkers}`);
  }
  for (const file of walk(out).filter((each) => TEXT_FILE.test(each))) {
    findings.push(...secretFindings(file, readText(file)));
  }
  for (const finding of findings) process.stdout.write(`BULGU: ${finding}\n`);
  process.stdout.write(`check-out: ${built.length} sayfa, ${findings.length} bulgu (indexable=${flag})\n`);
  return findings.length === 0 ? 0 : 1;
}

process.exitCode = main();
```

- [ ] **Step 6: Üç derleme, sıfır bulgu (sağlamlık ölçümü, spec §18.5/2)**

Run:
```bash
source ~/.nvm/nvm.sh && nvm use 24 >/dev/null && export NEXT_TELEMETRY_DISABLED=1
FULL="$PWD/web/fixtures/snapshot.fixture.web-full.json"; EMPTY="$PWD/web/fixtures/snapshot.fixture.web-empty.json"
SITE_SNAPSHOT="$FULL" pnpm -C web run build && node web/scripts/check-out.ts --snapshot "$FULL" --out web/out
SITE_SNAPSHOT="$FULL" SITE_INDEXABLE=1 pnpm -C web run build && SITE_INDEXABLE=1 node web/scripts/check-out.ts --snapshot "$FULL" --out web/out
SITE_SNAPSHOT="$EMPTY" pnpm -C web run build && node web/scripts/check-out.ts --snapshot "$EMPTY" --out web/out
```
Expected: üç kez `check-out: 40 sayfa, 0 bulgu` (`indexable=false`, `true`, `false`). Bağımlılıksız ayrıştırmanın sağlamlığı
bu koşuyla ölçülür: her sayfada `data-fe` açılış sayısı = okunan öğe sayısı ve `<script` açılış sayısı = sınıflandırılan
betik sayısı (ikisi de sayfa başına bulgudur; kazımada 40 sayfada sıfır sapma). Sapma çıkarsa kapsamı DARALTMA — bulguyu
raporla, eskalasyon (spec §5.3: "bağımlılık eklemek bilinçli commit").

- [ ] **Step 6b: Yasal taslakların düz metin dökümü (avukat incelemesi için; spec §10.1 "düz metin olarak dışa aktarılabilir")**

Son derleme boş-fixture'lıdır (Step 6); yasal sayfalar fixture'dan bağımsızdır. Döküm depo DIŞINA yazılır:
```bash
D=.superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-legal-text; mkdir -p "$D"
node --input-type=module -e '
import { readFileSync, writeFileSync } from "node:fs";
import { visibleText } from "./web/scripts/lib/html.ts";
const dir = process.argv[1];
for (const lang of ["en", "tr"]) for (const doc of ["terms", "privacy", "cookies", "responsible-gambling"]) {
  const html = readFileSync(`web/out/${lang}/legal/${doc}/index.html`, "utf8");
  const main = html.slice(html.indexOf("<main"), html.indexOf("</main>"));
  const text = visibleText(main).replace(/[ \t]+/g, " ").replace(/\s*\n\s*/g, "\n").trim();
  writeFileSync(`${dir}/${lang}-${doc}.txt`, `${text}\n`);
}' "$D"
ls "$D"
```
Expected: sekiz `.txt` dosyası; her biri "TASLAK — avukat onayı bekler" içerir. Controller bunları AK13 için kullanıcıya iletir.

- [ ] **Step 7: Gerçek derleme üzerinde kırma-geri-yükleme (her biri KIRMIZI olmalı)**

Tam fixture'la bayraksız derlemeden sonra (Step 6'nın ilk satırı yeniden koşulur), her mutasyon `out/`un TAZE bir kopyasında
yapılır — `web/out` değişmez, hiçbir şey silinmez:
```bash
FULL="$PWD/web/fixtures/snapshot.fixture.web-full.json"; EMPTY="$PWD/web/fixtures/snapshot.fixture.web-empty.json"
P=en/synthetic-league-alpha/match/34e5be017510/dogu-bati-fk-vs-obrien-rovers/index.html
mut() { # $1 ad · $2 kopya dizininde ($D) düzenleme · $3 SITE_INDEXABLE · $4 anlık görüntü
  D="$(mktemp -d)"; cp -R web/out/. "$D/"; eval "$2"
  echo "== $1"; SITE_INDEXABLE="${3:-}" node web/scripts/check-out.ts --snapshot "${4:-$FULL}" --out "$D" | tail -3
}
mut "öznitelik"        "perl -pi -e 's/data-fe-value=\"29.5\"/data-fe-value=\"29.6\"/' \"\$D/$P\""
mut "görünen metin"    "perl -pi -e 's/>29.5%</>29.6%</' \"\$D/$P\""
mut "CSP hash'i"       "perl -0pi -e \"s/ 'sha256-[^']+'//\" \"\$D/_headers\""
mut "lisans iddiası"   "perl -pi -e 's/<h1>/<h1>licensed /' \"\$D/$P\""
mut "eksik sayfa"      "mv \"\$D/en/track-record/index.html\" \"\$D/track-record-moved.html\""
mut "fazla sayfa"      "mkdir -p \"\$D/en/extra\" && cp \"\$D/en/index.html\" \"\$D/en/extra/index.html\""
mut "bayrak uyuşmazlığı" "true" 1
mut "gizli anahtar"    "f=\$(ls \"\$D\"/_next/static/chunks/*.js | head -1); echo 'x=\"eyJhbGc\"' >> \"\$f\""
mut "hreflang"         "perl -pi -e 's/<link rel=\"alternate\" hrefLang=\"tr\"[^>]*>//' \"\$D/$P\""
mut "iki h1"           "perl -pi -e 's/<h2>/<h1>/' \"\$D/$P\""
mut "holdout tarihi"   "perl -pi -e 's#</main>#<p>2025-12-01</p></main>#' \"\$D/$P\""
mut "undefined"        "perl -pi -e 's#</main>#<p>undefined</p></main>#' \"\$D/$P\""
mut "H4 işareti"       "perl -pi -e 's/ data-fe-allow=\"license-negation\"//' \"\$D/en/legal/terms/index.html\""
mut "snapshot.sha256"  "echo 0000 > \"\$D/data/snapshot.sha256\""
mut "başka anlık görüntü" "true" "" "$EMPTY"
```
Expected (sırayla, kazımada ölçülen): `özniteliği 29.6 ≠ 29.5` · `metni "29.6%" ≠ "29.5%"` · `/en/: CSP'nin izin vermediği
satır içi betik` · `lisans iddiası kalıbı "licensed" (H4)` · `/en/track-record/: kaydın sayfası yok` · `/en/extra/: anlık
görüntüde kaydı olmayan sayfa` · `sitemap.xml: 0 URL, beklenen 22` ve `_headers: X-Robots-Tag noindex=true, bayrak=true` ·
`gizli anahtar kalıbı "eyJ" (H5)` · `hreflang dilleri en,x-default` · `tek <h1> yok` · `tabandan eski tarih 2025-12-01 (H1)` ·
`görünen metinde "undefined"` · `H4 işaret sayısı: kaynak 2 ≠ derlenmiş 1` · `data/snapshot.sha256 dosya baytlarıyla
eşleşmiyor` · `root:-:content_sha256 özniteliği 84b7… ≠ 21a8…` (bayat derleme). HER satırda son satır `… N bulgu` ile N ≥ 1.
Biri 0 bulgu verirse o kontrol ISIRMIYOR — görev bitmemiştir.

- [ ] **Step 8: Kaynak tarafı mutasyonları (birim + CLI)**

1. `checks.ts` `checkFields`de metin karşılaştırmasını (`if (element.text !== shown) …`) yorum satırına al → birim testi
   "metin ≠ format(değer) kırmızı" FAIL ve Step 7'nin "görünen metin" mutasyonu 0 bulgu verir. Geri al.
2. `expect.ts` `matchFields`de `if (match.h2h[round] === null) continue;` satırını kaldır → birim "eşik altı tur alan
   üretmez" FAIL ve temiz derlemede `çözülemeyen alan …h2h.opening…` bulguları. Geri al.
3. `checks.ts` `fold()`dan `.replace(/ı/g, "i")`yi kaldır → "H4: … Lisanslı veri" FAIL (Türkçe büyük/küçük harf, Review
   Focus 1). Geri al.
4. `html.ts` `decodeEntities`ten `.replace(/&amp;/g, "&")` satırını kaldır → `html.test.ts` "React'in kaçışlarını çözer"
   FAIL (Review Focus 1: `&` taşıyan bir `Txt` alanı sessizce kırmızıya düşerdi). Geri al; `git diff --stat -- web/scripts` boş.

- [ ] **Step 9: Biçim, tip, test, tam kapı**

Run: `pnpm -C web exec biome check --write . && pnpm -C web exec biome ci . && pnpm -C web exec tsc --noEmit && pnpm -C web exec vitest run`
ve `verify.sh` (`b2-t9-gate.log`). Expected: vitest `96 passed` (78 + 18); taban PASS.

- [ ] **Step 10: Commit**

```bash
git add web/scripts/checkout/expect.ts web/scripts/checkout/checks.ts web/scripts/checkout/checks.test.ts \
  web/scripts/check-out.ts
git commit -m "feat: çıktı tarayıcısı — sayfa ↔ anlık görüntü, H4–H7, CSP, erişilebilirlik (B-2 T9)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Site kapısının Node adımları `verify.sh` / `ci.yml` / `site.yml`e bağlanır (B-1 birleştikten SONRA)

**Kademe:** K2 · **Spec:** §12.1 (`site-kurulum`…`site-uyum`, `pnpm ya da Node yoksa FAIL`, uçtan uca JSON'un `run-id`
denetimi, `CI=true` iken FAIL), §12.2 ("B-2 son görevi: `actions/setup-node` (sürüm `web/.nvmrc`) + `pnpm/action-setup`
(`packageManager`) ve Node adımları"), §12.3 (tek yazar), §15 ("§4.4/3'ün JSON'uyla `next build` + tarayıcı"), §11 (`site.yml`
adımları) · **Ön koşul:** B-1'in dalga sonu birleştirmesi `main`de (`site-db` adımı, `FE_VERIFY_RUN_ID`, `verify-snapshot`,
`site.yml`).

**Files:**
- Create: `scripts/site_gate.sh` (çalıştırılabilir), `tests/test_site_web_gate.py`
- Modify: `verify.sh` (B-1'in `site-db` adımından SONRA, `zincir` bloğundan ÖNCE bir blok), `.github/workflows/ci.yml`
  (`uv sync` ile `./verify.sh` arasına iki adım + adım listesi yorumu), `.github/workflows/site.yml` (YALNIZ Node adımları,
  B-2 arayüzüyle uyuşmuyorsa), `tests/site_web_fixtures.py` (YALNIZ `PATH_ID_LENGTH`, `verify-snapshot` gerektirirse)

**Interfaces:**
- Consumes: B-1 — `verify.sh`te `step "site-db"` ve `export FE_VERIFY_RUN_ID`; `${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e/
  {snapshot.json,run-id}`; `uv run python -m football_edge.site verify-snapshot <dosya>` (exit 0 = geçerli);
  `.github/workflows/site.yml`. B-2 T1–T9'un bütün komutları.
- Produces: `scripts/site_gate.sh {toolchain|e2e|install|build|check}`; `verify.sh` adımları `site-kurulum`, `site-tip`,
  `site-lint`, `site-test`, `site-derleme`, `site-uyum` (+ CI'da uçtan uca JSON yoksa `site-e2e` FAIL); yerel SKIP satırı
  `SKIP: site-derleme/e2e (…)`.

- [ ] **Step 1: B-1'i dala al ve arayüzü ölç**

Run:
```bash
git merge --no-ff main -m "Merge main: B-1 dalga sonu (B-2 T10 ön koşulu)"
grep -n 'step "site-db"' verify.sh; grep -n 'FE_VERIFY_RUN_ID' verify.sh
test -f .github/workflows/site.yml && echo "site.yml var"
uv run python -m football_edge.site verify-snapshot web/fixtures/snapshot.fixture.web-full.json; echo "full exit=$?"
uv run python -m football_edge.site verify-snapshot web/fixtures/snapshot.fixture.web-empty.json; echo "empty exit=$?"
```
Expected: `site-db` adımı ve `FE_VERIFY_RUN_ID` (dışa aktarılmış) var; `site.yml var`; iki fixture `exit=0`. Arayüzden biri
YOKSA DUR (B-1 ile arayüz ihlali; controller'a eskale et — B-2 B-1'in adımını kendisi YAZMAZ). `verify-snapshot` bir B-2
fixture'ını reddederse nedeni oku: (a) `path_id` uzunluğu → `tests/site_web_fixtures.py`de `PATH_ID_LENGTH`i B-1'in
`slugs.py` sabitine eşitle, `uv run python -m tests.site_web_fixtures` ile yeniden üret, yeni `content_sha256`ları rapora yaz,
`pnpm -C web exec vitest run` ve `uv run pytest -q tests/test_site_web_contract.py` yeşil (rota testleri `path_id`yi
fixture'dan okur); (b) başka bir biçim kuralı → üreticiyi B-1'in kuralına uydur; kural spec'le çelişiyorsa DUR, eskale et.

- [ ] **Step 2: Başarısız testi yaz — `tests/test_site_web_gate.py`**

```python
"""Site kapısının Node adımları `verify.sh` / `ci.yml` / `site.yml`e doğru bağlı (spec §12.1–§12.3).

Adımlar B-1'in `site-db` adımından SONRA koşar (uçtan uca anlık görüntüyü o yazar); CI
Node ve pnpm'i `web/.nvmrc` / `packageManager`dan kurar; uçtan uca anlık görüntü yalnız bu
koşunundur (bayat dosyayla PASS yok, CI'da yokluğu FAIL); `site.yml` derlemeyi `_headers`
üreten `run build` ile yapar ve yayından önce çıktı tarayıcısını koşar.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
VERIFY = REPO / "verify.sh"
CI = REPO / ".github/workflows/ci.yml"
SITE = REPO / ".github/workflows/site.yml"
GATE = REPO / "scripts/site_gate.sh"
NODE_STEPS = ("site-kurulum", "site-tip", "site-lint", "site-test", "site-derleme", "site-uyum")


def _step_names() -> list[str]:
    return re.findall(r'^step "([^"]+)"', VERIFY.read_text(encoding="utf-8"), flags=re.M)


def _steps(path: Path) -> list[dict[str, Any]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [step for job in document["jobs"].values() for step in job["steps"]]


def _index(steps: list[dict[str, Any]], needle: str, key: str = "run") -> int:
    for index, step in enumerate(steps):
        if needle in str(step.get(key, "")):
            return index
    raise AssertionError(f"adım yok: {needle!r}")


def test_node_steps_run_in_order_after_site_db() -> None:
    names = _step_names()
    positions = [names.index(name) for name in ("site-db", *NODE_STEPS)]
    assert positions == sorted(positions), f"sıra yanlış: {names}"


def test_builds_go_to_a_fresh_directory_per_run_and_nothing_is_deleted() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    assert 'SITE_BUILDS="$(mktemp -d' in text
    assert "export SITE_BUILDS" in text
    assert not re.search(r"^\s*rm\s", GATE.read_text(encoding="utf-8"), flags=re.M)


def test_ci_installs_node_and_pnpm_from_the_pins_before_the_gate() -> None:
    steps = _steps(CI)
    pnpm = _index(steps, "pnpm/action-setup", key="uses")
    node = _index(steps, "actions/setup-node", key="uses")
    gate = _index(steps, "./verify.sh")
    assert pnpm < node < gate
    assert steps[pnpm]["with"]["package_json_file"] == "web/package.json"
    assert steps[node]["with"]["node-version-file"] == "web/.nvmrc"


def _gate(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(GATE), *args],
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], **env},
        check=False,
    )


def _e2e_dir(tmp_path: Path, run_id: str | None) -> Path:
    directory = tmp_path / "site-e2e"
    directory.mkdir()
    (directory / "snapshot.json").write_text("{}", encoding="utf-8")
    if run_id is not None:
        (directory / "run-id").write_text(run_id + "\n", encoding="utf-8")
    return directory


@pytest.mark.parametrize("ci", ["", "true"])
def test_e2e_snapshot_of_this_run_is_used(tmp_path: Path, ci: str) -> None:
    directory = _e2e_dir(tmp_path, "run-7")
    env = {"RUNNER_TEMP": str(tmp_path), "FE_VERIFY_RUN_ID": "run-7", "CI": ci}
    result = _gate(["e2e"], env)
    assert (result.returncode, result.stdout.strip()) == (0, f"USE {directory}/snapshot.json")


@pytest.mark.parametrize("run_id", ["run-6", None])
def test_stale_or_unlabelled_e2e_snapshot_is_skipped_locally_and_fails_in_ci(
    tmp_path: Path, run_id: str | None
) -> None:
    _e2e_dir(tmp_path, run_id)
    local = _gate(["e2e"], {"RUNNER_TEMP": str(tmp_path), "FE_VERIFY_RUN_ID": "run-7"})
    assert (local.returncode, local.stdout.split(" ")[0]) == (0, "SKIP")
    env = {"RUNNER_TEMP": str(tmp_path), "FE_VERIFY_RUN_ID": "run-7", "CI": "true"}
    ci = _gate(["e2e"], env)
    assert (ci.returncode, ci.stdout.split(" ")[0]) == (1, "FAIL")


def test_missing_run_id_variable_never_accepts_a_file(tmp_path: Path) -> None:
    _e2e_dir(tmp_path, "")
    result = _gate(["e2e"], {"RUNNER_TEMP": str(tmp_path)})
    assert result.stdout.startswith("SKIP ")


def _fake_tools(tmp_path: Path, node: str, pnpm: str) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, output in (("node", node), ("pnpm", pnpm)):
        tool = bin_dir / name
        tool.write_text(f"#!/bin/sh\n{output}\n", encoding="utf-8")
        tool.chmod(0o755)
    return {"PATH": f"{bin_dir}:/usr/bin:/bin"}


@pytest.mark.parametrize(
    ("node", "pnpm", "message"),
    [
        ("echo 22", "echo 10.34.5", "Node 22, .nvmrc 24 istiyor"),
        ("echo 24", "echo 11.9.0", "pnpm 11, packageManager 10 istiyor"),
        ("exit 127", "echo 10.34.5", "node yok"),
        ("echo 24", "exit 127", "pnpm yok"),
    ],
)
def test_wrong_or_missing_toolchain_fails_by_name(
    tmp_path: Path, node: str, pnpm: str, message: str
) -> None:
    result = subprocess.run(
        [str(GATE), "toolchain"],
        capture_output=True,
        text=True,
        env=_fake_tools(tmp_path, node, pnpm),
        check=False,
    )
    assert result.returncode == 1
    assert message in result.stdout


def test_matching_toolchain_passes(tmp_path: Path) -> None:
    env = _fake_tools(tmp_path, "echo 24", "echo 10.34.5")
    result = subprocess.run(
        [str(GATE), "toolchain"], capture_output=True, text=True, env=env, check=False
    )
    assert result.returncode == 0, result.stdout


def test_site_workflow_builds_with_headers_and_checks_before_deploy() -> None:
    steps = _steps(SITE)
    install = _index(steps, "pnpm -C web install --frozen-lockfile")
    build = _index(steps, "pnpm -C web run build")
    check = _index(steps, "web/scripts/check-out.ts")
    deploy = _index(steps, "deploy --prod")
    assert install < build < check < deploy
    assert steps[build]["env"]["NEXT_TELEMETRY_DISABLED"] == "1"
    assert not any("next build" in str(step.get("run", "")) for step in steps), (
        "çıplak `next build` `_headers`/`_redirects` üretmez; `run build` kullanılır"
    )


def test_site_workflow_never_turns_indexing_on() -> None:
    assert "SITE_INDEXABLE" not in SITE.read_text(encoding="utf-8"), "AK14 onayı yok"
```

Run: `uv run pytest -q tests/test_site_web_gate.py`
Expected: FAIL — `site-kurulum` adım listesinde yok (`ValueError: 'site-kurulum' is not in list`), `pnpm/action-setup` adımı
yok, `scripts/site_gate.sh` yok (`FileNotFoundError`/`PermissionError`). `site.yml` testleri B-1'in komutlarına göre geçebilir
ya da düşebilir — düşerse Step 6'da hizalanır.

- [ ] **Step 3: `scripts/site_gate.sh`**

```bash
#!/usr/bin/env bash
# Site kapısının Node adımları (spec §12.1, Plan B-2). `verify.sh` her alt komutu ayrı bir
# `step` olarak koşar. Burada SKIP YOKTUR: Node ya da pnpm yoksa ya da sürüm `.nvmrc` /
# `packageManager` ile uyuşmuyorsa adım FAIL'dir — site kapının parçasıdır.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$REPO/web"
# Next derlemesi varsayılan olarak anonim telemetri GÖNDERİR; kapı ağa yazmaz.
export NEXT_TELEMETRY_DISABLED=1

fail() {
  echo "HATA: $*"
  exit 1
}

toolchain() {
  local want_node want_pnpm have_node have_pnpm
  want_node="$(tr -d '[:space:]' < "$WEB/.nvmrc")"
  want_pnpm="$(sed -nE 's/.*"packageManager": *"pnpm@([0-9]+)\..*/\1/p' "$WEB/package.json")"
  have_node="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null)" || fail "node yok"
  have_pnpm="$(pnpm --version 2>/dev/null)" || fail "pnpm yok"
  have_pnpm="${have_pnpm%%.*}"
  [ "$have_node" = "$want_node" ] || fail "Node $have_node, .nvmrc $want_node istiyor"
  [ "$have_pnpm" = "$want_pnpm" ] || fail "pnpm $have_pnpm, packageManager $want_pnpm istiyor"
  echo "node $have_node · pnpm $have_pnpm"
}

# Her satır: ad|anlık görüntü|SITE_INDEXABLE. Uçtan uca varyantı verify.sh seçer (spec §12.1).
variants() {
  echo "fixture-full|$WEB/fixtures/snapshot.fixture.web-full.json|"
  echo "fixture-full-indexable|$WEB/fixtures/snapshot.fixture.web-full.json|1"
  echo "fixture-empty|$WEB/fixtures/snapshot.fixture.web-empty.json|"
  if [ -n "${SITE_E2E_SNAPSHOT:-}" ]; then
    echo "e2e|$SITE_E2E_SNAPSHOT|"
  fi
}

# Uçtan uca anlık görüntünün seçimi (spec §12.1 `site-derleme`): yalnız BU `verify.sh`
# koşusunun `site-db` adımının yazdığı dosya (`run-id` = FE_VERIFY_RUN_ID) kullanılır.
# Tek satır basar: `USE <yol>` · `SKIP <neden>` (yerel) · `FAIL <neden>` (CI=true, exit 1).
e2e() {
  local dir="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e"
  if [ -n "${FE_VERIFY_RUN_ID:-}" ] && [ -f "$dir/snapshot.json" ] \
    && [ "$(cat "$dir/run-id" 2>/dev/null)" = "$FE_VERIFY_RUN_ID" ]; then
    echo "USE $dir/snapshot.json"
  elif [ "${CI:-}" = "true" ]; then
    echo "FAIL CI=true ve bu koşunun uçtan uca anlık görüntüsü yok ya da bayat ($dir)"
    return 1
  else
    echo "SKIP bu koşunun uçtan uca anlık görüntüsü yok ya da bayat ($dir)"
  fi
}

build() {
  : "${SITE_BUILDS:?SITE_BUILDS tanımlı değil — verify.sh başta mktemp ile kurar}"
  local name snapshot flag
  while IFS='|' read -r name snapshot flag; do
    echo "--- $name: verify-snapshot"
    (cd "$REPO" && uv run python -m football_edge.site verify-snapshot "$snapshot") \
      || fail "anlık görüntü doğrulanmadı: $name"
    echo "--- $name: derleme (SITE_INDEXABLE=${flag:-yok})"
    SITE_SNAPSHOT="$snapshot" SITE_INDEXABLE="$flag" pnpm -C "$WEB" run build \
      || fail "derleme düştü: $name"
    mkdir -p "$SITE_BUILDS/$name"
    cp -R "$WEB/out/." "$SITE_BUILDS/$name/" || fail "çıktı kopyalanamadı: $name"
  done < <(variants)
}

check() {
  : "${SITE_BUILDS:?SITE_BUILDS tanımlı değil — verify.sh başta mktemp ile kurar}"
  local name snapshot flag failed=0
  while IFS='|' read -r name snapshot flag; do
    echo "--- $name: çıktı tarayıcısı"
    if [ ! -d "$SITE_BUILDS/$name" ]; then
      echo "HATA: $name derlenmemiş"
      failed=1
      continue
    fi
    SITE_INDEXABLE="$flag" node "$WEB/scripts/check-out.ts" \
      --snapshot "$snapshot" --out "$SITE_BUILDS/$name" || failed=1
  done < <(variants)
  return "$failed"
}

case "${1:-}" in
  toolchain) toolchain ;;
  e2e) e2e ;;
  install) toolchain && pnpm -C "$WEB" install --frozen-lockfile ;;
  build) build ;;
  check) check ;;
  *) fail "kullanım: $0 {toolchain|e2e|install|build|check}" ;;
esac
```

Run: `chmod +x scripts/site_gate.sh`

- [ ] **Step 4: `verify.sh` — blok, B-1'in `site-db` adımından hemen SONRA, `if [ -n "${DATABASE_URL:-}" ]` satırından ÖNCE**

```bash
# ── Site (Plan B-2, spec §12.1) ───────────────────────────────────────────────────────────
# Node adımları `site-db`den SONRA koşar: uçtan uca anlık görüntüyü o adım yazar. Her koşu
# derlemelerini KENDİ geçici dizinine kopyalar (silme yok, bayat çıktı yok). Uçtan uca
# anlık görüntünün seçimi ve bayat dosya reddi `site_gate.sh e2e`dedir (testli).
SITE_BUILDS="$(mktemp -d "${TMPDIR:-/tmp}/site-builds.XXXXXX")"
export SITE_BUILDS
SITE_E2E_SNAPSHOT=""
e2e_decision="$(./scripts/site_gate.sh e2e)"
case "$e2e_decision" in
  "USE "*) SITE_E2E_SNAPSHOT="${e2e_decision#USE }" ;;
  "SKIP "*) echo "SKIP: site-derleme/e2e (${e2e_decision#SKIP })" | tee -a "$LOG" ;;
  *)
    echo "$e2e_decision" | tee -a "$LOG"
    step "site-e2e" false
    ;;
esac
export SITE_E2E_SNAPSHOT
step "site-kurulum" ./scripts/site_gate.sh install
step "site-tip"     pnpm -C web exec tsc --noEmit
step "site-lint"    pnpm -C web exec biome ci .
step "site-test"    pnpm -C web exec vitest run
step "site-derleme" ./scripts/site_gate.sh build
step "site-uyum"    ./scripts/site_gate.sh check
```

- [ ] **Step 5: `.github/workflows/ci.yml` — `- run: uv sync --frozen` satırının hemen ARDINA**

```yaml
      # Site kapısının Node adımları (Plan B-2): sürümler `web/.nvmrc` ve `packageManager`dan
      # okunur — kapının `site-kurulum` adımı yerelde de aynısını ister.
      - uses: pnpm/action-setup@v4
        with:
          package_json_file: web/package.json
      - uses: actions/setup-node@v4
        with:
          node-version-file: web/.nvmrc
          cache: pnpm
          cache-dependency-path: web/pnpm-lock.yaml
```
Aynı dosyada `Kapı` adımının yorumundaki "Geri kalan … adım koşar:" listesinin sonuna
`· site-kurulum · site-tip · site-lint · site-test · site-derleme · site-uyum` ekle (sayıyı da güncelle). Secret EKLENMEZ
(`test_ci_reads_no_repository_secret_at_all`). `timeout-minutes` Step 9'un ölçümüyle güncellenir.

- [ ] **Step 6: `.github/workflows/site.yml`i B-2 arayüzüyle hizala (yalnız Node adımları)**

Run: `grep -nE "pnpm|next build|check-out|setup-node|action-setup|SITE_INDEXABLE|NEXT_TELEMETRY" .github/workflows/site.yml`
Hedef (B-1'in yazdığı adımlar zaten böyleyse DOKUNMA): `pnpm/action-setup@v4` (`package_json_file: web/package.json`) ve
`actions/setup-node@v4` (`node-version-file: web/.nvmrc`) kurulum adımları pnpm adımından önce; kurulum
`run: pnpm -C web install --frozen-lockfile`; derleme adımı
```yaml
      - name: Site derlemesi (next build + _headers/_redirects/data)
        env:
          SITE_SNAPSHOT: ${{ github.workspace }}/web/.snapshot/snapshot.json
          NEXT_TELEMETRY_DISABLED: "1"
        run: pnpm -C web run build
```
ve deploy adımından ÖNCE `run: node web/scripts/check-out.ts --snapshot web/.snapshot/snapshot.json --out web/out`.
`web/.snapshot/` spec §13'ün gitignore'daki anlık görüntü dizinidir; B-1'in `site export --out` değeri başka bir dizinse
(Step 6'nın grep çıktısı) iki satırdaki yol O dizinle yazılır. `SITE_INDEXABLE` hiçbir
yerde (AK14). Bu adımlar secret TAŞIMAZ (H5d). Değişiklik yaptıysan B-1'in adım ortamı testini koş:
`uv run pytest -q -k "site and workflow"` → yeşil.

- [ ] **Step 7: Gate testi yeşil**

Run: `uv run pytest -q tests/test_site_web_gate.py`
Expected: `15 passed` (kazımada B-1 benzetimiyle ölçüldü: sıra 1 · dizin 1 · CI 1 · uçtan uca 2 + 2 + 1 · araç zinciri 4 + 1
· `site.yml` 2).

- [ ] **Step 8: Tam kapı — Node 24 etkin, yerel**

Run:
```bash
source ~/.nvm/nvm.sh && nvm use 24 >/dev/null
start=$(date +%s); TMPDIR=$(mktemp -d) ./verify.sh > .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t10-gate.log 2>&1; echo "exit=$? süre=$(( $(date +%s)-start ))s"
grep -E "^(PASS|FAIL|SKIP)" .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t10-gate.log
grep -E "^(--- |check-out:)" .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t10-gate.log
```
Expected: `exit=0`, `KAPI YEŞİL`; T0 tabanı + B-1'in `site-db`si + altı site adımı PASS. Yerelde `SITE_TEST_DATABASE_URL`
yoksa `site-db` adıyla SKIP basar (B-1 kuralı) ve bu koşuda `SKIP: site-derleme/e2e (bu koşunun uçtan uca anlık görüntüsü yok
ya da bayat …)` satırı görünür — ATLANAN KONTROL GEÇMEK DEĞİLDİR: Step 10 uçtan uca yolu kapla ayrıca koşar. Üç fixture
varyantı için `check-out: 40 sayfa, 0 bulgu`. Node 22 etkin iken koşulursa `FAIL: site-kurulum` (`HATA: Node 22, .nvmrc 24
istiyor`) BEKLENEN davranıştır.

- [ ] **Step 9: Kapı süresini ölç, `timeout-minutes`i güncelle**

Run: `source ~/.nvm/nvm.sh && nvm use 24 >/dev/null; export SITE_BUILDS=$(mktemp -d); s=$(date +%s); ./scripts/site_gate.sh install && pnpm -C web exec tsc --noEmit && pnpm -C web exec biome ci . && pnpm -C web exec vitest run && ./scripts/site_gate.sh build && ./scripts/site_gate.sh check; echo "site adımları=$(( $(date +%s)-s ))s"`
Expected: sayı rapora yazılır (S saniye). `ci.yml` `timeout-minutes` = B-1'in bıraktığı değer + max(5, ⌈2·S/60⌉). İlk CI
koşusu bu değerin %70'ini aşarsa controller yeniden ölçer (HANDOFF'a satır).

- [ ] **Step 10: Uçtan uca yol (B-1'in kabıyla) ve CI kipi**

Run (B-1'in RUNBOOK/`sandbox_db.sh` tarifiyle yerel `supabase/postgres` kabı ayaktayken, `SITE_TEST_DATABASE_URL` ile):
```bash
source ~/.nvm/nvm.sh && nvm use 24 >/dev/null
export SITE_TEST_DATABASE_URL   # B-1'in yerel kap tarifinin verdiği adres (RUNBOOK §4 / B-1 T0 kaydı)
TMPDIR=$(mktemp -d) ./verify.sh > .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t10-e2e.log 2>&1; echo "exit=$?"
grep -E "^(PASS|FAIL|SKIP)|--- e2e|check-out:" .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t10-e2e.log
CI=true TMPDIR=$(mktemp -d) ./verify.sh > .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t10-ci-nodb.log 2>&1; echo "exit=$?"
grep -E "^(PASS|FAIL)|FAIL CI=true" .superpowers/sdd/2026-09-23-oturum9-dalga-a/b2-t10-ci-nodb.log
```
Expected: ilk koşu `exit=0`, `--- e2e: verify-snapshot`, `--- e2e: derleme`, dört `check-out: … 0 bulgu` (dördüncüsü uçtan
uca JSON'un sayfası). İkinci koşu (`CI=true`, DB yok) `exit=1`: B-1'in `site-db`si FAIL ve `FAIL: site-e2e` + `FAIL CI=true ve
bu koşunun uçtan uca anlık görüntüsü yok ya da bayat …` — CI'da SKIP yeşili yok (B10). Kap kurulamıyorsa uçtan uca yol yerelde
ÖLÇÜLMEMİŞ olarak raporlanır; CI'da (B-1'in servis kabıyla) ilk push'ta ölçülür (controller).

- [ ] **Step 11: Mutasyon kanıtları**

1. `verify.sh`de `site-derleme` ile `site-uyum` satırlarının yerini değiştir → `test_node_steps_run_in_order_after_site_db`
   FAIL. Geri al.
2. `site_gate.sh` `e2e`de `[ -n "${FE_VERIFY_RUN_ID:-}" ] &&` koşulunu kaldır → `test_missing_run_id_variable_never_accepts_a_file`
   FAIL (boş `run-id` boş değişkene eşit sayılırdı). Geri al.
3. `site_gate.sh` `toolchain`de Node karşılaştırma satırını `true` yap → `test_wrong_or_missing_toolchain_fails_by_name[echo 22-…]`
   FAIL. Geri al.
4. `ci.yml`de `node-version-file: web/.nvmrc` → `node-version: 22` → `test_ci_installs_node_and_pnpm_from_the_pins_before_the_gate`
   FAIL. Geri al.
5. `site.yml` derleme adımında `pnpm -C web run build` → `pnpm -C web exec next build` →
   `test_site_workflow_builds_with_headers_and_checks_before_deploy` FAIL. Geri al.
6. `web/src/components/Fe.tsx` `Num`da `data-fe-value={String(props.value)}` → `data-fe-value={String(props.value).slice(0, -1)}`
   → tam kapıda `FAIL: site-uyum` (log: `özniteliği … ≠ …`). Geri al; `git diff --stat` boş (yalnız bu görevin dosyaları
   değişmiş görünür).

- [ ] **Step 12: Tam kapı (son)** — Step 8'in komutu; `exit=0`.

- [ ] **Step 13: Commit**

```bash
git add scripts/site_gate.sh tests/test_site_web_gate.py verify.sh .github/workflows/ci.yml
# yalnız değiştiyse: git add .github/workflows/site.yml tests/site_web_fixtures.py web/fixtures/snapshot.fixture.web-full.json web/fixtures/snapshot.fixture.web-empty.json
git commit -m "ci: site kapısının Node adımları verify.sh ve ci.yml'e bağlandı (B-2 T10)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 14: Controller'a devir (rapor)**

Rapora yaz: (a) yerel kapı komutu artık Node 24 ister — HANDOFF'taki kapı tarifine `source ~/.nvm/nvm.sh && nvm use 24`
eklenmeli (controller dosyası); (b) Step 9 süresi ve yeni `timeout-minutes`; (c) uçtan uca yolun yerelde koşup koşmadığı;
(d) `_headers` boyutu (T8) ve uçtan uca JSON'un sayfa sayısı.

---

## Controller adımları (sıra önemli)

1. **T0 öncesi:** worktree `.worktrees/wt-s9-b2` (`feat/s9-iz-b2`, `main`den). T0 Step 2–3'ün indirmeleri (Node 24.21.0,
   pnpm 10.x) ve T1 Step 6'nın `pnpm install`ı (npm kayıt defterinden okuma) için onay.
2. **B-1'e iletilecek üç nokta (B-1 T1/T4'ün sözleşmesine dokunur, B-2 yazamaz):** (a) lig slug'ı `data` ve `_next` de
   ayrılmıştır (derleme çıktısının dizinleri; B-2 yükleyicisi bunları reddeder — B-1'in `slugs.py`si üretmemeli);
   (b) `path_id` önek uzunluğu B-2 fixture'ında 12'dir, B-1'in sabiti farklıysa T10 Step 1 uzlaştırır; (c) `out/data/slugs.json`
   biçimi yukarıdaki arayüz tablosundadır — `site.yml`in kaybolan-slug kontrolü onu okur.
3. **B-1 T1 `main`e birleşince:** B-2 T2 başlar (T2 Step 1 `main`i dala alır).
4. **T9:** K1 süreci — mutasyonlu görev incelemesi kabuklu inceleyiciyle (`general-purpose`), T9 Step 7'nin 15 kırma-geri-
   yükleme vakası inceleyici tarafından yeniden koşulur.
5. **B-1 dalga sonu birleştirmesi `main`de olduktan SONRA:** B-2 T10. Ardından bütün-dal incelemesi, `main`e `--no-ff`,
   `git fetch origin && git merge --no-ff origin/main` + tam kapı (Node 24 etkin) + push; ilk CI koşusunun süresi
   `timeout-minutes`e karşı okunur; uçtan uca varyantın CI'da `check-out: … 0 bulgu` verdiği logdan doğrulanır.
6. **HANDOFF (controller dosyası):** kapı tarifine `source ~/.nvm/nvm.sh && nvm use 24` eklenir; "Kapının ölçmedikleri
   (bu plan)" listesi faz HANDOFF'una taşınır; AK19 için `_headers` boyut ölçümü yazılır.

---

## Öz-inceleme

**1. Spec kapsamı (§15 Plan B-2 maddeleri → görev):** iskelet + sözlükler → T1, T3 · maç/lig/takım/sicil/yasal sayfaları →
T5, T6, T7 · slug yolları + `hreflang` + site haritası + `_redirects` → T4, T8 · JSON-LD → T4 (+ T9 doğrulaması) · 18+ → T7 ·
`_headers` üretimi (CSP, AK19) → T8 · yasal taslaklar → T7 · çıktı tarayıcısı → T9 · `netlify.toml` → T8 · son görev:
`verify.sh` Node adımları + `ci.yml` Node kurulumu + kapı süresi ölçümü + §4.4/3'ün JSON'uyla `next build` + tarayıcı → T10.
Bölüm bazında: §5.2 TS tipi/anahtar eşitliği/fixture'lar → T2 · §5.3 (1)–(8) → T9 · §5.4 → T3 · §6.1–§6.3 → T6 · §6.4/1
fixture varyantları (boş/dolu sicil, eşik altı, mühürsüz, tek tur) → T2 · §7 → T5 · §8.1–§8.6 → T4, T5, T8 · §9 → T4, T9 ·
§10.1–§10.2 → T7 (düz metin dökümü T9 Step 6b) · §11 `netlify.toml` → T8, `site.yml` hizalama → T10 · §12.1–§12.3 → T10 · §13 → T1 · H4/H5b/H6c/H7 → T8,
T9 · H5a → T1 · §18.5/2 ölçümü → T9 Step 6. Boşluk: §18.5/4 ve /6 (Netlify davranışı) ölçülemez → "Kapının ölçmedikleri";
AK20 b'nin kaybolan-slug karşılaştırması `site.yml` adımıdır (B-1 T6), B-2 yalnız deposunu (`data/slugs.json`) üretir.

**2. Yer tutucu taraması:** kod adımlarının tamamı kazımada derlenmiş ve koşturulmuş dosyalardan birebir alındı. Kalan
bilinçli değişkenler yalnız ÖLÇÜM sonuçlarıdır (T0 sürümleri; T10'da B-1'in `site.yml` dışa aktarım dizini ve yerel kap
adresi) ve her birinin nereden okunacağı yazılıdır. "TBD/TODO/uygun hata yönetimi" yok.

**3. Tip tutarlılığı:** `formatNumber(value, kind, lang)` (T3) — T5 `Num`, T9 `checkFields` aynı imza; `feKey(entity, id,
path)` (T3) ↔ T9 `resolveField` aynı `varlık:kimlik:yol` dilbilgisi; `ExpectedPage.fields` anahtarları T5/T6 bileşenlerinin
bastıklarıyla kazımada birebir (15 mutasyon + 3 temiz derleme); `pageFiles`/`walk`/`readText` (T8) ↔ T9; `sitemapEntries`
(T8) ↔ T9'un site haritası beklentisi (bağımsız kurulur); `site_gate.sh` alt komutları (T10) ↔ `verify.sh` bloğu ↔ gate testi.

**4. Review Focus:** beş satırın her birinin testi sahibi görevde (T2 fixture + yükleyici, T3 biçim, T4 JSON-LD kaçışı, T8
`decodeEntities`, T9 alan kümesi/metin taraması, T10 uçtan uca seçim).

**Doğrulanmadan kalanlar (adıyla):** Biome 2 yerelde kurulu değildi — biçim/lint T1 Step 8'de ilk kez ölçülür; kod Next
16.2.9 / React 19.2.4 / Vitest 4.1.9 ile koşturuldu, plan 16.3.x / 19.3.x / 4.1.11 sabitler (aynı ana sürümler); pnpm 10 ile
kilit dosyası ve `--frozen-lockfile` davranışı T1'de ölçülür; `verify.sh`/`ci.yml` değişikliği ve gate testi B-1'in
`site-db`sinin BENZETİMİYLE koşturuldu (gerçek B-1 adımı T10'da).

---

## Açık sorular — spec'in cevaplamadığı ve bu plandaki kararlar

1. **`site.yml` kimin?** Görev tanımı deploy iş akışını B-2'ye sayıyor; spec §15 onu B-1 T6'ya veriyor (bağlayıcı otorite
   spec). **Karar:** `site.yml`i B-1 yazar; B-2 `netlify.toml`u yazar ve T10'da `site.yml`in YALNIZ Node adımlarını B-2
   arayüzüyle hizalar (sıralı, tek yazar korunur). Yanlışsa: T10 Step 6 tam `site.yml` yazımına genişler.
2. **B-2 ne zaman başlar?** Spec "B-1 T1 birleşince paralel"; görev tanımı "B-1 inmeden önce koşabilsin". **Karar:** T0–T1
   B-1'den bağımsız; T2–T9 yalnız B-1 T1'in şema dosyasını ister (başka hiçbir B-1 çıktısını değil); geliştirme B-2'nin kendi
   sentetik fixture'larıyla. `verify-snapshot` ve uçtan uca JSON yalnız T10'da tüketilir.
3. **Şema ↔ TS anahtar eşitliği testinin sahibi.** Spec §12.1 onu B-1'in `pytest` satırında sayıyor ama TS dosyası B-2'nin.
   **Karar:** B-2 T2 yazar (`tests/test_site_web_contract.py`); B-1 de yazdıysa controller birini tutar (ikisi çelişmez).
4. **`config/site_redirects.yaml` yönlendirmeleri `_redirects`e nasıl girer?** Spec dosyayı kaybolan-slug kontrolü için
   tanımlıyor, biçimini ve `_redirects`e aktarımını tanımlamıyor. **Karar:** B-2 bu dosyayı okumaz; yeniden adlandırılan
   takım/lig URL'si yönlendirilmez ("Kapının ölçmedikleri" d). Kaybolan-slug kontrolünü yazan görev (B-1 T6 ya da deploy
   bağlama işi) biçimi belirlerken bu aktarımı da planlamalı.
5. **Bağımlılık listesi.** Spec'in dev listesi `@types/react-dom`u içermiyor; `react-dom/server` testleri (18+, `Fe`) onsuz
   tip denetiminden geçmez. **Karar:** bilinçli ekleme (yalnız tip paketi), allowlist testinde adıyla; `schema-dts`
   kullanılmıyor (spec "plan kaldırabilir"). TypeScript 5.9 ve Vitest 4'te tutuldu (kayıt defterinde TS 7, Vitest 5 var):
   spec yalnız Next için "en yeni kararlı" diyor; Next'in derleme içi tip denetimi TS 7 yerel sürümüyle ölçülmedi.
6. **"Fixture `satisfies Snapshot` ile `tsc`'de sınanır."** JSON'u TS'e `satisfies`le içe aktarmak fixture'ı derleme
   paketine sokar. **Karar:** eşdeğer iki kontrol — fixture'ın şekli şemaya karşı, TS tipinin anahtarları şemaya karşı
   (ikisi de pytest, T2); yükleyici `Snapshot` tipini döndürür.
7. **Ayrılmış lig slug'ları.** Spec yalnız `track-record`/`legal` diyor; `data` (yayın dosyaları) ve `_next` (Next
   varlıkları) da derleme çıktısında dizin. **Karar:** dördü de ayrılmış (yükleyici reddeder); B-1'e iletilir (Controller 2a).
8. **Yasal sayfaların indekslenmesi.** Spec bayrak açıkken yasal sayfalar için politika vermiyor. **Karar:** taslak
   oldukları sürece (AK13) bayraktan bağımsız `noindex` ve site haritası dışı.
9. **Bayrak kapalıyken site haritası.** **Karar:** boş `urlset` (spec: site haritası = indekslenebilir sayfa kümesi; hepsi
   `noindex`). `robots.txt` Disallow'suz (H7).
10. **18+ bildiriminin biçimi.** "Tam ekran bildirim" + betiksiz kalıcı şerit. **Karar:** sunucu çıktısında KAPALI `<dialog>`
    (tam ekran CSS), onay yoksa istemci açar; kipsiz (odak tuzağı yok) — yaş doğrulaması olmadığı spec'te yazılı (§12.4/6).
11. **Marka ve çıpa geçmişi yer tutucuları.** **Karar:** `SITE_NAME = "[site-name]"` (`"SITE_NAME"` değeri, tanımlayıcının
    kendisiyle çakıştığı için yer tutucu taramasını kör ederdi); GitHub çıpa geçmişi bağlantısı depo adını kamuya bağlar →
    `LEDGER_HISTORY_URL` yer tutucu (AK3/AK4 ile birlikte karar).
12. **Next telemetrisi.** Spec sessiz; `next build` varsayılan olarak anonim telemetri gönderir (ağa yazma). **Karar:** her
    derleme `NEXT_TELEMETRY_DISABLED=1` ile (kapı betiği, `site.yml`, plan komutları).
13. **Derleme varyantları.** Spec §12.1 üç derleme sayıyor. **Karar:** dört — boş sicil fixture'ı da derlenir (§6.2 bugünün
    gerçeği; uçtan uca JSON yerelde çoğu zaman yok).
14. **AK17.** Spec The Odds API koşullarının "Plan B-2'den önce" okunmasını öneriyor (türetilmiş olasılık, `path_id` olarak
    olay kimliği). **Karar:** plan yazıldı, çünkü hiçbir şey yayımlanmıyor ve URL şeması/gösterim geri alınabilir; AK17
    sonucu `path_id`i ya da maç sayfası içeriğini değiştirirse T4/T5 yeniden açılır. Kullanıcı kararı olarak kalır.
15. **Next'in 404 sayfası ve `*.netlify.app`.** Netlify hesabı olmadan ölçülemez (§18.5/4, /6); 404 yanıtına sayfa CSP'si
    konamaz. **Karar:** "Kapının ölçmedikleri"ne yazıldı; deploy bağlanırken ölçülür.
