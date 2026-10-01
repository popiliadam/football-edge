# Oturum 10b — Kalan Kullanıcısız Borçlar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Oturum 10'un açık bıraktığı kullanıcısız satırları kapatmak: 16g (c) soy bekçisinin uygulanması + 21b/21e
testleri; 19b kalanı + 21a + 21k (workflow bekçileri); 21c/21d/21j (web küçükleri).

**Architecture:** Üç ayrık dosya kümesi, üç paralel worktree (`.worktrees/wt-s10b-uN`, dal `feat/s10b-uN`),
`integ/s10b` üzerinden `main`e. Davranış değişikliği: U1'de yalnız aynı strateji nesnesinin başka akışa yeniden
oynatılmasında `MemoReuseError` (bugün üretimde tetiklenmiyor); U2'de seal/sources-audit adım koşulları (kırmızı tarama
sonrası secret'lı adım koşmaz). Geri kalanı test/bekçi.

**Tech Stack:** Python 3.11, pytest, ruff, mypy strict; `web/` Next.js 16.3.6 + vitest (Node 24.21.0).

**Spec:** `docs/DEFERRED.md` 16g, 19b, §21 (21a–21k) satırları; 16g için tasarım notu
`docs/superpowers/specs/2026-10-01-dc-memo-anahtari.md` (öneri (c), §5 test planı) bağlayıcıdır.

## Global Constraints

- **HİÇBİR ŞEY SİLME.** Holdout AÇMA (holdout okuyan/açan komut koşma). Canlı DB'ye bağlanma, `.env` okuma yok. Ücretli API
  yok. Migration yok. Workflow tetikleme (`gh workflow run`) yok. Mühürlü dosyalara dokunma: `config/model_faz3.yaml`,
  `config/blend_weights_faz3.yaml`, `config/history_lock.yaml`, `config/faz3_preregistration.yaml`.
- **`docs/DEFERRED.md` ve `docs/HANDOFF.md`'ye görevler YAZMAZ** (tek yazar: controller); rapor sonunda "DEFERRED güncellemesi".
- **Scratch:** yalnız `<WS>/uN/` (WS = `/Users/apple/dev/football-edge/.superpowers/sdd/2026-10-01-oturum10b-kalan-borclar`),
  dosya adları `uN-` önekli. `/tmp` ve paylaşılan scratchpad YASAK. Kap gerekirse `scripts/sandbox_db.sh` `s10bN-` önekiyle.
- **Kapı (her commit'ten sonra, tam):** worktree kökünde
  `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); (echo "# commit: $(git rev-parse --short HEAD)"; env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh) > <WS>/uN/uN-verify-<k>.log 2>&1`
  — sonuç LOG'dan (16 PASS + adıyla 3 SKIP `site-db`, `site-derleme/e2e`, `zincir`; "KAPI YEŞİL"). Kurulum yoksa önce
  `uv sync --frozen --extra scrape`.
- **Mutasyon kanıtı:** her yeni test/bekçi, hedeflediği satır bozulunca KIRMIZI (`PYTHONDONTWRITEBYTECODE=1`; geri al,
  `git diff` temiz). Komut + çıktı rapora.
- Commit `<type>: <açıklama>`; her mesaj `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` ile biter. Push/merge YOK.
- Türkçe yorum/docstring/mesaj; çevredeki deyim. Testte `ANAHTAR=değer` dolu atama yazma (secret taraması testleri de tarar).

## Review Focus

1. U1: mühürlü Faz 3 çıktılarının bayt eşliği — bekçi yalnız yükseltir, hiçbir olasılığı değiştirmez; tam pytest'te 0 `MemoReuseError`.
2. U2: seal her 15 dk koşar — adım koşulu değişikliği yeşil turun davranışını DEĞİŞTİRMEMELİ (alarm aç/kapat, bekçi); yalnız kırmızı tarama sonrası secret'lı adımlar düşer.
3. U3: görünür metin değişmez (AK2 bekliyor); CSP/`_headers`/check-out yeşil.

---

### Task 1 (U1): 16g (c) soy bekçisi + sıcak başlangıç ve harman testleri (DEFERRED 16g, 21b, 21e)

**Files:** `src/football_edge/model/strategies.py` (+ gerekiyorsa aynı paketteki memo modülü), yeni test dosyası
`tests/test_memo_lineage.py`, `tests/test_context_parity.py` (21e).

- [ ] Tasarım notu §3 (c) + §5 test planını uygula: memo isabetinde VE ıskada soy denetimi (`latest` mührü şimdiki akışın
  öneki değilse `MemoReuseError`), anahtar aynen. Mesaj Türkçe ve nedeni adlandırır.
- [ ] Testler (notun §5'i): B1, B1', +3 gün ıska senaryoları kırmızı (`MemoReuseError`); taze oynatmalar bayt eşit ve fit
  sayıları korunur (56/56/112/56 gibi notun ölçtükleri); bekçi kaldırılınca bu testler kırmızı.
- [ ] 21b: backtest'in kullandığı sıcak başlangıç yolu (`memo.latest`, `fitted_on < at`, grup kapsamı) testle sabitlenir —
  T7 incelemesinin üç kaynak mutantı (bkz. `.superpowers/sdd/_kalici/defterler/2026-10-01-oturum10-kucuk-borclar/task-7-review-r1.md`) kırmızı.
- [ ] 21e: E2 paritesine harman ayağı (aynı soğuk başlangıç/`==` kalıbıyla) — ya da harmanın canlı yolda olmadığını
  ölçüp gerekçesiyle raporla.
- [ ] Tam pytest'te 0 `MemoReuseError`; tam kapı; commit(ler).

### Task 2 (U2): 19b kalanı + 21a + 21k — workflow bekçileri

**Files:** `.github/workflows/seal.yml`, `.github/workflows/sources-audit.yml`, `tests/test_secrets_scan_netlify.py`,
`tests/test_site_gate.py`, seal/sources-audit'i test eden mevcut workflow testleri (grep ile bul; bayt/sıra pinlerine uy).

- [ ] 19b kalanı: kırmızı secret taramasından sonra secret okuyan HİÇBİR adım koşmamalı. seal'daki `always()`/`!cancelled()`
  adımlar ve sources-audit'teki `!cancelled()` adımlar: secret okuyan ya da `git push` yapanlar tarama adımının
  başarısına bağlanır (ör. tarama adımına `id` + koşula `steps.<id>.outcome == 'success'`); secret okumayan alarm/yansıtma
  adımları bugünkü davranışını korur. Her adım için kararı rapora yaz. Yeşil turun davranışı DEĞİŞMEZ (Review Focus 2).
  Özellik bekçisi: taramayı taşıyan işte, taramadan sonra `always()`/`!cancelled()`/`failure()` koşullu ve secret okuyan
  ya da push yapan adım tarama başarısına bağlı olmalı; iş düzeyi `env:` secret'ı da kapsanır.
- [ ] 21k: `git -c … push`/`git -C dir push` biçimli push'u sıra bekçisi görür; iş düzeyi `if: always()` + `needs` taşıyan
  işi ele al; `Secrets.X` büyük/küçük harf (GitHub ifadeleri harf duyarsız mı — ölç/belgeye dayan, öyleyse IGNORECASE).
  Yanlış pozitifleri (zincirli `needs`, yeniden kullanılabilir workflow `KeyError`) ucuzsa düzelt, değilse docstring.
- [ ] 21a: `test_ci_never_prints_the_container_log`: `docker inspect -f/--format` şablonunda yalnız `.State.*` alanları
  serbest (beyaz liste); `{{json .}}`, `{{.}}` ve `\` satır devamıyla bölünmüş satır (satırları birleştirerek) kırmızı.
- [ ] Mutasyonlar; tam kapı; commit(ler).

### Task 3 (U3): web kalanları (DEFERRED 21c, 21d, 21j)

**Files:** `web/src/app/global-not-found.tsx`, `_headers` ayrıştırıcıları (Python: `src/football_edge/site/` içindeki
`parse_headers`; TS: `web/scripts/checkout/` içindeki `parseHeaders`) ve testleri, `web/fixtures/headers.fixture*`,
nav testi (`web/src/components/SiteChrome.test.tsx`), `checkFrameworkLang` testi.

- [ ] 21c: `global-not-found.tsx`teki iç import (`next/dist/client/components/http-access-fallback/error-fallback`)
  yerine Next'in yerleşik 404 içeriğiyle BAYT AYNI çıktıyı veren satır içi JSX (görünür metin aynı — ölç: base/head
  `out/` 404 HTML'i görünür içerikte bayt eşit). Deneysel `globalNotFound` bayrağı kalır (belge gereği).
- [ ] 21d: iki `_headers` ayrıştırıcısı aynı davranışa gelir: aynı blokta tekrar eden başlık (ikisi de aynı kuralı — hangisi
  Netlify davranışına uyuyorsa, ölç/belgeye dayan) ve `#` yorum satırı (ikisi de yorum sayar); ortak fixture bu iki durumu
  içerir, iki dilin testi aynı beklenen JSON'u üretir.
- [ ] 21j: nav testi etiketleri sözlük anahtarlarına bağlar (en+tr); `checkFrameworkLang` için birim testi (eksik `lang`
  kırmızı).
- [ ] Mutasyonlar; site adımları + tam kapı; commit(ler).
