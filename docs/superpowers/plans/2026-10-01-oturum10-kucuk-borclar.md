# Oturum 10 — Küçük Borçlar (HANDOFF §0.A/2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** HANDOFF §0.A/2'deki kullanıcı girdisi gerektirmeyen DEFERRED satırlarını kapatmak: 11a/11h (Scrapling bekçi ve
test boşlukları), 18g(b) (bozuk DSN'de parola yankısı), 19a (adsız exit 1), 19b/19c (secret taraması kapsamı, CI
bekçisi), 20a/20d/20f/20k/20l/20m (B-2 küçükleri), 17h (AST bekçisi kaçışları), 16g (tasarım notu).

**Architecture:** Davranış değişikliği yalnız hata yollarında (18g(b), 19a) ve iki workflow'a eklenen tarama adımında
(19b); geri kalanı test/bekçi sıkılaştırması. Her görev ayrık dosya kümesine yazar → dalga 1 paralel, her görev kendi
worktree'sinde (`.worktrees/wt-s10-tN`, dal `feat/s10-tN`), sonra `integ/s10` dalında birleşir.

**Tech Stack:** Python 3.11, pytest, ruff, mypy strict; `web/` Next.js 16 + vitest + biome (pnpm 10, Node 24.21.0).

**Spec:** `docs/DEFERRED.md` ilgili satırlar (metinleri spec'tir) + `docs/HANDOFF.md` §0.A/2, §0.D.

## Global Constraints

- **HİÇBİR ŞEY SİLME** (dosya, dal, kap, worktree). Holdout AÇMA. Canlı DB'ye bağlanma, `.env` okuma yok. Ücretli API
  çağrısı yok. Migration yok. Mühürlü dosyalara dokunma: `config/model_faz3.yaml`, `config/blend_weights_faz3.yaml`,
  `config/history_lock.yaml`, `config/faz3_preregistration.yaml`.
- **`docs/DEFERRED.md` ve `docs/HANDOFF.md`'ye görevler YAZMAZ** (tek yazar: controller). Her görev raporunun sonunda
  "DEFERRED güncellemesi" başlığı altında satırın yeni metnini önerir (kapandı / kısmen + kalan).
- **Scratch:** yalnız kendi alt dizinin `<WS>/tN/` (WS = `/Users/apple/dev/football-edge/.superpowers/sdd/2026-10-01-oturum10-kucuk-borclar`),
  dosya adları `tN-` önekli. Paylaşılan scratchpad ve `/tmp` YASAK. Kap gerekirse `scripts/sandbox_db.sh` kendi
  önekinle (`s10tN-`); başkasının kabına dokunma.
- **Kapı (her commit'ten sonra, tam):** worktree kökünde
  `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh > <WS>/tN/tN-verify-<k>.log 2>&1`
  — sonuç LOG DOSYASINDAN okunur (beklenen: 16 PASS + adıyla 3 SKIP `site-db`, `site-derleme/e2e`, `zincir`; son satır
  "KAPI YEŞİL"). Kurulum yoksa önce `uv sync --frozen --extra scrape`. TMPDIR depo DIŞINDA olmalı (DEFERRED 20l).
- **Mutasyon kanıtı:** her yeni test için, testin hedeflediği satırı bozup testin KIRMIZI olduğunu göster, sonra geri al
  (`PYTHONDONTWRITEBYTECODE=1`; geri alınca `git diff` temiz). Kanıt rapora komut + çıktı ile.
- Commit biçimi `<type>: <açıklama>` (test/fix/ci/docs); her commit mesajı `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` ile biter. Push YOK, merge YOK (controller yapar).
- Proje dili: yorumlar, docstring'ler, log/hata mesajları Türkçe; çevredeki kodun yoğunluğunu ve deyimini izle.
- Secret taraması testleri de tarar: testte `ANAHTAR=değer` biçiminde dolu atama yazma (adları parçadan kur).

## Review Focus

1. Yeni her test bir mutasyonla kırmızıya düşürülebilmeli (inceleyici `git archive` kopyasında bağımsız koşar).
2. Hata yollarında hiçbir koşulda DSN/parola parçası stdout/stderr/log'a çıkmamalı (18g(b), 19a).
3. Bekçi sıkılaştırması depodaki mevcut kodda yanlış pozitif üretmemeli (kapı yeşil kalmalı).
4. Workflow değişikliği (19b) tarama adımını `{"name": "Secret taraması", "run": "./scripts/check_secrets.sh"}` biçiminde, ilk adımlardan biri olarak, `if`/`continue-on-error` olmadan eklemeli.

---

## Dalga 1 (paralel)

### Task 1: Scrapling geçidi test boşlukları ve erişim kuralı (DEFERRED 11a, 11h)

**Files:** Modify `tests/test_scrape.py`, `tests/test_access_method_rule.py`. (Gerekirse `src/football_edge/scrape.py` — yalnız testin ortaya çıkardığı gerçek hata için.)

- [ ] 11h(a): `_carries_credentials`in ters bölü dalı için test — `Location: /\evil.example/x` sıçraması (ve doğrudan `\` taşıyan URL) reddedilir. Mutasyon: `or "\\" in url` silinince kırmızı.
- [ ] 11h(b): `_robots` önbellekli yoldaki `max(state.delay, …)` için test — önce `Crawl-delay: 9` alan UA, sonra gecikmesiz UA → bekleme hâlâ 9. Mutasyon: `max(...)` → yalnız ikinci terim kırmızı. N7–N9 (`OverflowError`/`IndexError`/`TypeError` eşdeğer mutant) için test YAZILMAZ; `scrape.py:279` yanına kısa yorum ("3.11'de atılmaz; savunma") eklenebilir.
- [ ] 11a: `test_access_method_rule.py`ye iki denetim: (i) yasak paket adı + sürüm işleci/`[`/`@`/`;`/`(` taşıyan dize (ör. `"camoufox==0.4"`); (ii) kurulum fiili (`pip install`, `uv pip install`, `uv add`, `poetry add`) + yasak ad taşıyan dize. Depodaki mevcut dizelerde 0 yanlış pozitif (kapı yeşil); sentetik örneklerde dört biçim (`"camoufox==0.4"`, `"pip install camoufox"`, `os.system("uv pip install camoufox")`, ekstra taşıyan) kırmızı. Yasak ad listesi dosyadaki mevcut listeden okunur (yeni liste kurma).
- [ ] 11h(c): `test_access_method_rule.py` modül docstring'inin "Bilinen sınırlar" bölümüne T2 Minor-B/C/D'yi ekle: yanlış pozitifler (düzyazıdaki `--proxy`/`--solve-cloudflare`/`scrapling shell`; savunma amaçlı `{'proxy'}` yasak listesi) ve kaçışlar (`shutil.which("scrapling")` argv başı, kabuk satır devamı, demet hedefli UA, `scrapling-mcp`).
- [ ] Tam kapı; commit(ler).

### Task 2: Hata yollarında DSN hijyeni ve adlı çıkış kodları (DEFERRED 18g(b), 19a, 20l)

**Files:** Modify `src/football_edge/db.py`, `src/football_edge/site/__main__.py`; testler: yeni `tests/test_db_connect_redaction.py`, ilgili `tests/test_site_*.py`.

- [ ] 18g(b): `db.connect` bozuk DSN'de (libpq ayrıştırma hatası: `invalid percent-encoded token`, `missing "=" after`, `invalid connection option` vb.) parolayı yankılamamalı. Uygulama: `psycopg.connect`in DSN ayrıştırma hatasını (`psycopg.ProgrammingError` — önce gerçek sınıfı ölç) yakala ve metni taşımayan bir hata yükselt (`from None` — zincir/`__context__` da parola taşımamalı; traceback'e bak). Test: parola parçası içeren üç bozuk DSN biçimiyle `connect` çağrısı → yükselen hatanın `str`ü, `repr`i, `__cause__`/`__context__` zinciri ve `pytest`in `--tb=short` çıktısı parolayı İÇERMEZ (alt süreçte bir CLI üzerinden de bir kez: ör. `python -m football_edge.<db kullanan komut>` bozuk `DATABASE_URL` ile → stdout+stderr'de parola yok, exit ≠ 0). Ağ yok: bozuk DSN bağlanmadan önce düşer; geçerli biçimli DSN'le bağlanma DENEME.
- [ ] Bu ağ dışında `DATABASE_URL`/`SITE_DATABASE_URL`yi `psycopg.connect`e doğrudan veren başka çağrı varsa (`grep -rn "psycopg.connect" src scripts`) aynı korumadan geçir ya da raporda adıyla listele.
- [ ] 19a: `site/__main__._export` `devig_method`/`_schema()` `OSError`u ve `run_export`tan gelen beklenmeyen istisnayı traceback'le exit 1 yerine adlı bir koda çevirmeli (mevcut 20–24 aralığından anlamca uyanı; yeni kod gerekiyorsa `site` exit kodu kaydına — dosyada nasıl kayıtlıysa — ekle ve tekillik testine uy). Mesaj istisna METNİNİ basmaz (yalnız sınıf adı), parola sızmaz. Test: her iki yol için monkeypatch'li çağrı → beklenen kod + mesajda sınıf adı.
- [ ] 20l: `TMPDIR` bir git ağacının içindeyken kırmızı olan iki B-1 testini bul (ipucu: `git SHA okunamadı` / `_git_sha` yolunu test edenler) ve alt süreç ortamına `GIT_CEILING_DIRECTORIES` vererek yalıt (`tests/test_secrets_scan_netlify.py:38`deki kalıp). Kanıt: `TMPDIR=<depo içi bir dizin>` ile o iki test önce kırmızı, sonra yeşil.
- [ ] Tam kapı; commit(ler).

### Task 3: Secret taraması kapsamı ve CI bekçileri (DEFERRED 19b, 19c)

**Files:** Modify `.github/workflows/sources-audit.yml`, `.github/workflows/full-scan.yml`, `tests/test_secrets_scan_netlify.py`, `tests/test_site_gate.py`; seal bekçisi için ilgili workflow testi (mevcut `tests/test_*workflow*.py` içinden seal'ı test edeni bul).

- [ ] 19b(1): `sources-audit.yml` ve `full-scan.yml`e checkout'tan hemen sonra `- name: Secret taraması` / `run: ./scripts/check_secrets.sh` adımı (diğer yedi workflow'daki yerle aynı konum). `test_every_workflow_runs_the_scan_bare_so_a_finding_stops_it` sayımı `>= 7` → bugünkü gerçek sayıya (9) ve ayrıca "secret taşıyan (`secrets.` geçen) ya da `contents: write` izinli her workflow taramayı koşar" bekçisi (yalnız sayıma güvenme; workflow adı listesi değil, özellik üzerinden). `ci.yml` bu kuraldan muafsa (kapı zaten taraması koşuyorsa) gerekçesiyle açıkça muaf tut.
- [ ] 19b(2): bekçi testi: tarama adımı taşıyan HER workflow'da, taramayı içeren İŞ düzeyinde `continue-on-error` yoktur (seal'daki `Alarm kapat` ADIM düzeyi `continue-on-error`ı kasıtlı ve serbest kalmalı). Mutasyon: seal işine iş düzeyinde `continue-on-error: true` → kırmızı.
- [ ] 19c: `test_ci_never_prints_the_container_log`: `docker inspect -f`/`--format` biçiminde `.Config` (ya da `.Config.Env`) içeren satırı reddet (tek regex). Mutasyon: `ci.yml`e `docker inspect -f '{{json .Config.Env}}' x` satırı → kırmızı; bugünkü `ci.yml` yeşil.
- [ ] Tam kapı; commit(ler).

### Task 4: Web yüzeyi küçükleri (DEFERRED 20a, 20d, 20m, 20f, 20k)

**Files:** `web/src/lib/jsonld.test.ts`, `web/vitest.config.ts` bekçisi için `tests/test_site_web_deps.py`, `web/src/components/*` (nav), `web/src/app/**` (404), `_headers` ayrıştırıcılarının testleri (Python: `tests/test_site_web_*.py`ten ilgili; TS: `web/scripts` ya da `web/src`te ilgili test) + ortak fixture `web/fixtures/` altında.

- [ ] 20d+20m: DEFERRED 20d'deki hazır parçacığı `jsonld.test.ts`e ekle (eksik `matchPath` importuyla). Mutasyon: `jsonld.ts`de `eventStatus` karşılaştırmasında `>` → `>=` kırmızı.
- [ ] 20a: `test_site_web_deps.py` bekçisi `vitest.config.ts`de `dir`/`root` ayarını reddetsin (ya da include kalıplarının çözüldüğü kökü sabitlesin). Mutasyon: `root: "src"` eklenince kırmızı.
- [ ] 20f: iki `<nav>`a ayırt edici erişilebilir ad (`aria-label`, metinler sözlükten — `web/src/i18n` — en/tr; yeni sözlük anahtarı varsa her iki dilde). 404 sayfalarında `<html lang>`: Next 16 statik dışa aktarımında mümkünse ekle; mümkün değilse NEDENİNİ ölçüp raporla (ertelenir). Var olan sayfa/metin testleri ve `check-out` yeşil kalmalı.
- [ ] 20k: Python ve TS `_headers` ayrıştırıcılarını aynı fixture dosyasından besleyen birer test (iki ayrıştırıcı aynı fixture'dan aynı sonucu çıkarır; beklenen sonuç fixture'ın yanında JSON). Mutasyon: bir ayrıştırıcıda tek davranış bozulunca kendi testi kırmızı.
- [ ] Web adımları kapıdan geçer (`site-*` adımları); tam kapı; commit(ler).

### Task 5: AST bekçisi kaçışları (DEFERRED 17h)

**Files:** `tests/test_jev_item_answers_readers.py`, bütçe bekçisini taşıyan test dosyası (`tests/test_jev_budget.py` ya da `grep -rln "TypeSafeJev" tests`), import kuralı (`tests/test_feature_import_rule.py`).

- [ ] 17a bekçisi (2026-09-24 eklenenler): `%`-dict (`"… %(t)s" % {"t": TABLO}`), `TABLO.upper()`, birleştirilmiş sabit (`TABLO = "jev_" + "item_answers"`), `" ".join((…, TABLO))` — her biri sentetik ağaçta adıyla kırmızı; `obj.gates_from(...)` çağrı biçimi için test (dal silinince kırmızı).
- [ ] Bütçe bekçisi: `TypeSafeJev as X` takma adıyla import ve sarmadan önce çıplak kullanım → kırmızı (sentetik).
- [ ] Import kuralı: yerel adla yeniden bağlama (`m = football_edge.x; m.y`) ve `getattr(modul, "ad")` — ucuz yakalanabiliyorsa yakala; yakalanamıyorsa docstring "Bilinen sınırlar"a yaz.
- [ ] Depoda yanlış pozitif yok (kapı yeşil). Tam kapı; commit(ler).

## Dalga 2

### Task 6: DC memo anahtarı tasarım notu (DEFERRED 16g) — yalnız belge

**Files:** Create `docs/superpowers/specs/2026-10-01-dc-memo-anahtari.md`.

- [ ] `src/football_edge/model/strategies.py` DC memo'sunu oku; B1 senaryosunu (aynı nesne başka maç kümesine oynatılırsa fitleri taşır) bir sentetik koşuyla scratch'te ölç (kod değişikliği commit'lenmez).
- [ ] Seçenekleri karşılaştır: (a) "`at`ten önceki gözlem sayısı" anahtarı + sıralı parça yapısı, (b) maç kümesinin kimliği (hash) ile memo'yu nesneye bağlama, (c) her oynatmada yeni nesne zorunluluğu (bekçiyle). Her biri için maliyet, mühürlü Faz 3 sonuçlarının bayt eşliğine etkisi, test planı.
- [ ] Öneri + uygulama ne zaman (Faz 4 model değişikliğiyle). Kod commit'i YOK.

### Task 7: E2 parite testinin DC ayağı hiçbir şey ölçmüyor (Task 6 yan bulgusu)

**Files:** Modify `tests/test_context_parity.py` (yalnız test; `src/` değişmez).

- [ ] Sorun (T6 incelemesinde doğrulandı): `tests/test_context_parity.py:181-191` E2'nin DC ayağında canlı tahmin memo isabetidir — canlı akış boş, gol çevrilmiş ya da kesik olsa da test yeşil. Taze nesneyle doğru akışta fark ~3,19e-06 (sıcak/soğuk başlangıç) ve mevcut `approx` toleransını aşar.
- [ ] Düzeltme: canlı ayağı memo'dan bağımsız kur (taze strateji nesnesi). Karşılaştırmayı tolerans gevşeterek DEĞİL, aynı başlangıç koşuluyla yap: iki ayağı da taze nesneyle (soğuk başlangıç) üret ve bayt/`approx` eşitliğini ölç; sıcak başlangıçla karşılaştırma gerekiyorsa farkın kaynağını docstring'de yaz. Tolerans büyütmek yasak (kapı gevşetme).
- [ ] Kanıt: canlı akışı boşaltan, golü çeviren ve kesen üç mutasyon artık kırmızı; düzeltilmemiş testte üçü de yeşildi (önce göster).
- [ ] Tasarım notu `docs/superpowers/specs/2026-10-01-dc-memo-anahtari.md` (T6, dal `feat/s10-t6`) bu testi E2 satırında anar — okumak serbest, YAZMA.
- [ ] Tam kapı; commit.
