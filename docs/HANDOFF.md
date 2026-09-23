# football-edge — Oturum Devri (Handoff)

**Son güncelleme:** 2026-09-23 (oturum 8: robots #3 kapandı, küçük borç temizliği) · **Durum:** **Faz 4 tasarımı + Plan 1 (dalga 0–1,
11 görev) `main`de** (`4a629c2`) · Plan 2 ön koşulları bekleniyor (§0.2) · holdout Faz 3 için bir kez açıldı, Faz 4'te
henüz açılmadı · `0012` canlı, `news_items` dolu, `collect-news` her turda senkronlar · **Dal:** `main` = `origin/main` ·
kapı **10 adım yeşil + `zincir` adıyla SKIP** (DATABASE_URL bağlıyken 11/11) · `EXPECTED_MIN_LEAKAGE` 418

> Giriş sırası: `README.md` → bu dosya → `docs/DEFERRED.md`.
> **Faz 3'ün devir belgesi ve "ölçülmeyenler" listesi: `docs/phases/03-baz-model/HANDOFF.md` §3.**
> Faz 2'nin devir belgesi ve "ölçülmeyenler" listesi: `docs/phases/02-tarihsel-taban/HANDOFF.md` §3.**
> Faz 1'inki: `docs/phases/01-toplayicilar/HANDOFF.md` §3. Faz 0'ınki: `docs/phases/00-kayit-altyapisi/HANDOFF.md` §3.
> Arıza prosedürleri: `docs/RUNBOOK.md`.

---

## 0. Sonraki oturum — buradan başla (2026-09-23, Faz 4 Plan 1 sonunda)

**Faz 4 Plan 1 bitti.** Tasarım `docs/superpowers/specs/2026-09-23-faz4-jev-sinyal-design.md` (R157–R172), plan
`docs/superpowers/plans/2026-09-23-faz4-plan1-dalga0-1.md`, T0c raporu `docs/reports/2026-09-23-faz4-arsiv-spike.md`,
ölçümler `docs/superpowers/specs/2026-09-23-faz4-olcumler.md`, ertelenenler **DEFERRED §17**. SDD defteri (gitignored,
bütün kararlar ve kanıtlar) `.superpowers/sdd/2026-09-23-faz4-plan1-dalga0-1/progress.md`.

### 0.0 Taze oturum — başlatma

**Başlatma istemi (yeni oturuma yapıştır):**
> "`docs/HANDOFF.md` §0'dan devam et. Önce §0.3 izlenecekleri kontrol et (gölge turu, salı raporu, collect-news
> senkronu). Tarih 2026-10-07'den önceyse Plan 2'ye başlama: §0.2'deki kontrol listesi bekler; bana §0.4'teki ara iş
> seçeneklerini sor. 2026-10-07 veya sonrasıysa §0.2'yi sırayla yürüt, sonra Plan 2'yi `superpowers:writing-plans`
> ile yaz."

**Kullanıcı kararı (2026-09-23):** §0.2'deki ön koşullar acil değil — Plan 2'nin başlangıç kontrol listesidir. Haber
senkronu ve gölge raporu kendiliğinden birikir; arşiv kapsam ölçümü Plan 2 yazılırken (en erken 2026-10-07) yapılır.

### 0.1 Ne yapıldı (hepsi görev incelemesi + bütün-dal incelemesinden geçti)
- **Dalga 0:** T1 `live freeze-weights` + `config/blend_weights_faz3.yaml` (19 lig; çoğunda model ağırlığı 0 — Faz 3
  bulgusuyla tutarlı) · T2 haftalık gölge CLV raporu (`shadow.yml` salı adımı, yalnız baz stratejileri — mühür testli;
  sonuç football-data'dan `match_key` ile, çünkü `match_results` boş) · T3–T5 açılış öncesi düzeltmeler 16a–16d, 16i,
  16l, 16p (`final-eval --phase` zorunlu) · T6 spike · T7 Jev batarya + $25/ay tavan (`jev_spend`) · T8 `0012`.
- **Dalga 1:** T9 `news_items` + `sync-news` (R172: `available_at = greatest(now(), iddia)`) · T10 karar anı filtresi,
  logit kaydırma, import kuralı · T11 34 soruluk `config/jev_questions.yaml`, kademe 1 koşucusu (`features tier1`, sahte
  istemciyle; gerçek Jev çağrısı YOK).
- **Son inceleme düzeltmeleri:** bütçesiz Jev yolları kapandı (`map-entities`, `calibrate` artık `BudgetedJev`), havuz
  fiti yakınsamazsa `freeze-weights` exit 18, kademe 1 haber başına 3 deneme tavanı (`t1_failed:<n>` işaretleri),
  `CalibrationUnfit`.
- **Gerçek veritabanı işlemleri:** `0012` uygulandı ve okuma sorgularıyla doğrulandı · `sync-news --since 2026-09-04`
  geri doldurması 1.259 haber (önce ROLLBACK'li kuru koşu) · 16i ölçümü: 1X2/pre red 0, W1–W4 GEÇTİ.

### 0.2 Plan 2'nin başlangıç kontrol listesi (acil değil — en erken 2026-10-07; Plan 2 bunlar olmadan yazılmaz)
1. **Arşiv kapsamı runner'da (DEFERRED 17k)** — asistan yapar: geçici dal + `workflow_dispatch`, T0c betiği. ≥ %30 ise
   arşiv ayağı yeniden açılır; değilse spec §7.3 yalnız-canlı yolu (seçim dilimi ≥ 900 haberli maç, kapı dilimi ≥ 1.800,
   2027-06-30). **Şu anki karar: KAPALI** (koşul ölçülmediği için).
2. ~~`TYPESAFE_API_KEY`~~ — **2026-09-23 eklendi** (secret + `.env`). Ücretli harcamayı açan commit'i asistan yapamaz —
   tek satırlık komutu kullanıcıya verir.
3. **`lag_b_p99`**: `sync-news` en az 2 hafta koşmuş olmalı (en erken **2026-10-07**) — yayıncı iddiası ↔ `first_seen_at`.
4. **Gölge raporunun ilk turları** (ilk salı 2026-09-29): canlı ΔLL SD'si → güç yeniden hesabı (spec §7.3).
5. EN kaynağı: GDELT DOC API, runner'dan; ToS'u AI kullanımını yasaklayan alan adları dışlanır. ajansspor gövdesi için
   ToS okunmalı (17l).

**Plan 2'ye taşınacaklar (brief'lere):** 17a okuyucu mühürü (T5 ilk adım), 17b kesinti hafifletmesi (T4), 17c–17e
açılış öncesi (T10), 17h kırmızı takım. Plan metnindeki Task 9 Step 8 kuru koşusunda `min(boolean)` yok — `bool_and`.

### 0.3 İzlenecekler
1. **2026-09-26 cuma 12:35 UTC** ilk karar günlü gölge turu (Faz 3 §0.6 aynen).
2. **2026-09-29 salı** ilk haftalık gölge CLV raporu (`shadow.yml` iş özeti): `sonuçsuz N` ve lig kapsamı tablosu —
   ilk raporlarda `fikstür ≫ karar` penceredendir (17j). Exit 9/11 → RUNBOOK.
3. `collect-news` her turda yeni "Haber deposunu güncelle" adımını koşar; kırmızıysa alarm (ops_alert).
4. `history.yml` model W1–W4 16i sonrası da GEÇTİ (yerelde ölçüldü); runner'da ilk tur 2026-09-26/29.
5. **2026-09-23 football-data robots sapması (#3, oturum 8'de kapatıldı):** site AI eğitim botlarını ve kazıyıcıları
   adıyla kapattı (GPTBot, ClaudeBot, CCBot… 12 grup); `*` açık kaldı. RUNBOOK §3.7 uygulandı: bizim UA ile protego
   500/500 yol izinli (ClaudeBot 0/500) → anlık görüntü (runner diff'inden birebir kuruldu, hunk sayıları doğrulandı)
   ve `robots_verified_at` güncellendi; test yeni kural listesini birebir sabitler. **Sınır:** football-data verisi
   Jev'e/AI'a verilmiyor — Plan 2'de verilecekse bu kaynak yeniden değerlendirilir (sitenin niyeti açık).

### 0.4 Plan 2'ye kadar ara iş seçenekleri (kullanıcıya sorulur; hiçbiri Plan 2'yi bloklamaz)
1. **İz B** (Faz 6 iskeleti, Netlify + alan adı) — kullanıcının Netlify sitesi ve alan adı kararı gerekir.
2. ~~**Küçük borç temizliği**~~ — **yapıldı 2026-09-23** (oturum 8, plan
   `docs/superpowers/plans/2026-09-23-kucuk-borc-temizligi.md`, 7 görev, satır içi yürütme + bütün-dal incelemesi):
   16j ve 17i kapandı, 16k-c ve 17m'nin iki doğrulama açığı kapandı; 16g, 16k-a/b ve 17m kalanları gerekçesiyle
   DEFERRED'da. **Kapının ölçmediği:** birleştirmeler rapor metnini bayt bayt korur ama bunu yalnız metni test
   edilen satırlar için kanıtlar — `model_selftest`in 5 basamaklı biçimi hiç sabit değildi (mutant yaşadı), şimdi
   `test_w1_and_w2_report_their_interval_with_five_decimals` sabitler; metnini test etmeyen başka bir rapor satırı
   kayarsa kapı görmez.
3. **Takma ad hijyeni** (Faz 3 §3.3/8, DEFERRED 16e): 09-26 gölge turunun `eşlenemeyen U` satırından sonra
   `config/history_aliases.yaml` (aynı gün/lig/konum kuralı, tahmin yok).
4. Hiçbiri — 2026-10-07'ye kadar yalnız izleme.

### 0.5 Çalışma disiplini (Faz 3 §0.5 aynen geçerli; bu oturumun ekledikleri)
- SDD betikleri ANA depo kökünden, BASE/HEAD açık SHA ile (`review-package`); worktree'ler `.worktrees/wt-faz4-*`.
- Plan yazımı: sözleşmeli paralel yazar ajanlar + tek-ağaç bağımsız plan incelemesi (iki tur) — dört görevler arası
  kırılmayı yürütmeden önce yakaladı.
- Gerçek DB'ye ilk yazım öncesi aynı SQL ROLLBACK içinde koşulur; K1 inceleyicileri yerel Postgres kabında (supabase
  17.6 imajı) migration ve INSERT'i gerçekten koşabilir.
- Temizlik: `.worktrees/wt-faz4-{a,b,c,d,e,f,fix}` ve dalları `feat/faz4-{a..f}`, `fix/faz4-plan1-final` 2026-09-23'te
  silindi (kullanıcı onayı; hepsi birleşmişti, uzakta dal yoktu). SDD defteri korunur.
- `TYPESAFE_API_KEY` 2026-09-23'te GitHub secret'ına ve `.env`e eklendi (kullanıcı; değer okunmadı). Anahtar henüz hiç
  çağrılmadı — ilk ücretli çağrı Plan 2'nin maliyet ölçümünde, kullanıcı onayıyla.

## 0.eski Önceki oturum (2026-09-23, Faz 3 kapanışında yazıldı — tarihçe)

**Faz 3 bitti.** 14 görevin hepsi `main`de; ayrıntı, kapının ne ölçtüğü ve ÖLÇMEDİKLERİ, R149–R156 ve Faz 4 ön
koşulları: **`docs/phases/03-baz-model/HANDOFF.md`**. Kısaca:
- Kapı: 1790 passed / 3 skipped (üçü `DATABASE_URL yok`) · `leakage` 336 · migration 0009/0010/0011 canlı.
- **Holdout — tek açılış** (kullanıcı onaylı): C1 ΔLL harman − piyasa 0,0001 [−0,0005, 0,0007]; harman bahis CLV
  −0,0497 (54 bahis), Placebo −0,0868; C6 0,0002 [−0,0013, 0,0018]. Jev'siz baz model piyasayı yenmiyor — Faz 4'ün
  baz çizgisi. Rapor `docs/reports/2026-09-23-faz3-holdout.md`.
- Ertelenenler DEFERRED §16 (16a–16c **bir sonraki açılıştan ÖNCE**). Defter (gitignored)
  `.superpowers/sdd/2026-09-23-faz3-model-walkforward/`.

### 0.1 Sıradaki oturum — FAZ 4 TASARIMI (taze oturum)

**Başlatma istemi (yeni oturuma yapıştır):**
> "`docs/HANDOFF.md` §0'dan devam et. Faz 4 tasarımını `superpowers:brainstorming` ile benimle başlat;
> §0.3'teki açık kararları bana sor. Kod yazma; tasarım onayından sonra `superpowers:writing-plans`."

**Okuma sırası (bu sırayla, başka bir şey okumadan):**
1. Bu bölüm (§0.1–§0.5).
2. `docs/phases/03-baz-model/HANDOFF.md` — Faz 3'ün sonucu, §3 ölçülmeyenler (özellikle §3.3), §6 Faz 4 ön koşulları.
3. `docs/DEFERRED.md` §16 (Faz 3), §15 (İz A), §14 (Faz 2).
4. Ana tasarım `docs/superpowers/specs/2026-09-19-football-edge-design.md` §4 (model), **§5 (Jev / soru bataryası /
   boru hattı rolleri / çok dillilik)**, §6.2 (holdout politikası), §9 (fazlar: Faz 4 = "Jev sinyal katmanı + özellik
   deposu + budama", kapı "baz çizgiye karşı marjinal CLV").
5. Yol haritası `docs/superpowers/plans/2026-09-21-yol-haritasi-v2-paralel-izler.md` §2 (Faz 4 dalgaları: T1 Jev
   istemcisi · T7 özellik deposu → T2–T5 soru bataryaları · T6 boru hattı rolleri → T8 budama · T9 eşdoğrusallık),
   §3 (K1/K2/K3 kademeleri), §4 (paralellik), §5 (insan kararları).
6. Faz 3 tasarımı `docs/superpowers/specs/2026-09-23-faz3-model-walkforward-design.md` — yalnız Faz 4'ün tüketeceği
   arayüzler: §5 (walk-forward bölgeleri S/E), §7 (canlı bağlam, E1–E3), §8 (ön kayıt ve tek açılış), §10 (gölge).

**Faz 3'ün Faz 4'e bıraktığı baz çizgi (karşılaştırılacak sayılar):**
- Holdout (2025/26, tek açılış): C1 ΔLL harman − piyasa 0,0001 [−0,0005, 0,0007]; LL piyasa 1,0026 · DC 1,0241 ·
  fit Elo 1,0254; harman bahis CLV −0,0497 (54 bahis); Placebo CLV −0,0868. E bölgesi (2019/20–2024/25): ΔLL 0,0002
  [0,0000, 0,0005]. **Sonuç: dil sinyali olmayan model piyasayı yenmiyor; model payı piyasadan ~0,022 LL geride.**
- Donmuş model `config/model_faz3.yaml` (sha256 `26b81642…`); harman ağırlıkları `backtest/wf_eval.frozen_weights`.

### 0.2 Faz 4'ün önündeki gerçek (2026-09-23 ölçüldü — tasarımın ilk sorusu)

1. **Dil sinyalinin tarihi YOK.** Walk-forward'un gücü 13 sezonluk fiyat tarihinden geliyordu; haber için böyle bir
   arşiv yok. `source_observations`: haber yalnız `ajansspor` (TR), **1.243 kayıt, 2026-09-04'ten beri**; başka dil
   yok. Faz 4'ün kapısı "baz çizgiye karşı marjinal CLV" ise örneklem yalnız CANLI birikimden gelir (gölge sicili +
   haber). Tasarım bunu çözmek zorunda: (a) geriye dönük haber arşivi kaynağı (lisans + robots, spec §3.2) var mı;
   (b) yoksa ölçüm yalnız ileriye dönük gölge üzerinde mi — o zaman ne kadar hafta gerekir (güç hesabı);
   (c) holdout politikası (§6.2) canlı-yalnız bir sinyal için nasıl uygulanır.
2. **Jev hiç çağrılmadı.** `.env`de `TYPESAFE_API_KEY` yok. `src/football_edge/jev.py` bir `JevClient` protokolü ve
   `TypeSafeJev` sarmalayıcısı taşır (Faz 1, varlık eşlemesi için; testler protokolü taklit eder). `typesafe-sdk`
   bağımlılığı `pyproject.toml`da. **Ön koşul (insan): API anahtarı.**
3. **Dil kalibrasyonu yapılmadı.** `config/languages.yaml`: `tr` ve `en` `production_enabled: false`;
   `data/calibration/tr.jsonl` yalnız 10 BİÇİM örneği (gerçek etiket değil). Spec §5.4: dil başına ~100 insan etiketli
   haber; ölçülmeden hiçbir dil üretime alınmaz (kapının `dil-kalibrasyonu` adımı zorlar). Yol haritası önerisi:
   Opus ön-etiketler, insan onaylar, ölçüm insan etiketine karşı.
4. **Gölge sicili yeni başladı:** `model_predictions` boş; ilk karar günlü tur 2026-09-26 cuma 12:35 UTC. Faz 3
   HANDOFF §3.3/8: eşlenemeyen tek canlı ad o ülke grubunu 10 gün bayat yapar (takma ad hijyeni şart).
5. **Maliyet tavanı:** Odds API bütçesi 500/ay (8 aktif lig, beklenen ≈455/ay, İz A R125); Jev ~$0,0004/maç (spec §5.1,
   ölçülmedi); ~35 soru × maç × lig. Haber toplama ücretsiz kaynaklarla (spec §3.2).

### 0.3 Kullanıcıya sorulacak açık kararlar (brainstorming'de)

1. Faz 4'ün değerlendirme stratejisi: geriye dönük haber arşivi mi aranacak, yoksa yalnız ileriye dönük gölge
   birikimi mi (kaç hafta, hangi güçte)? Bu karar fazın takvimini belirler.
2. `TYPESAFE_API_KEY` ne zaman verilecek; aylık Jev harcama tavanı.
3. Dil kalibrasyonu: hangi diller (TR + EN? 8 aktif ligin dilleri: EN, ES, IT, DE, FR, TR, NL)? Etiket yükü
   (dil başına ~100) kimde; Opus ön-etiket + insan onayı kabul mü?
4. Faz 4'ün ilk görevi gölge CLV raporu mu (P25, DEFERRED 16o), yoksa Faz 4'ten önce ayrı bir iş olarak mı?
5. Izgara ucu (DEFERRED 16n): Faz 4'te baz model yeniden seçilecekse ızgara genişletilsin mi?
6. Bir sonraki holdout: Faz 3 holdout'u (2025/26) harcandı; R128'e göre Faz 5 açılışından sonra durum verisi olur.
   Faz 4'ün kendi holdout'u ne (2026/27'nin bir dilimi mi)? Ön kayıt DEFERRED 16c'ye göre raporun bastığını birebir
   listelemeli.
7. Paralel iz: İz B (Netlify + alan adı — kullanıcıdan hâlâ bekleniyor) Faz 4'le paralel başlasın mı?

### 0.4 Bir sonraki holdout açılışından ÖNCE düzeltilecekler (Faz 4 planına girmeli)

DEFERRED **16a** (açılış sonrası arıza yolları: `--out` yoklaması, `fit_weights` yakınsamama), **16b** (ön kayıt
kanonik yol), **16c** (ön kayıt ↔ rapor: eşleştirilmiş ΔLL + `incomplete`/`fallback`), **16d** (faz parametresi).
Bunlar plansız kalırsa bir sonraki tek açılış riske girer.

### 0.5 Çalışma disiplini (bu projede kanıtlanmış; taze oturum bunları bilmez)

- **Süreç:** tasarım → kullanıcı onayı → plan (`writing-plans`; planın kodu plan metninden tek ağaca kurulup kapıdan
  geçirilir) → bağımsız plan incelemesi → `subagent-driven-development`. Faz 3 bu düzende 1 günde bitti.
- **Kapı:** `TMPDIR=$(mktemp -d) ./verify.sh > <log> 2>&1`, sonuç LOG DOSYASINDAN; 10 PASS + `SKIP: zincir` adıyla
  (DB bağlıyken 11/11). Her commit'ten sonra tam kapı; `main`e `--no-ff`; push öncesi `git fetch && git merge --no-ff
  origin/main`; taze klon kapısı; CI yeşil. Force/rebase yok (bot çıpaları).
- **Worktree:** `git worktree add .worktrees/wt-<görev> -b feat/<faz>-<görev> main` (Agent'ın `isolation: worktree`ü
  bu makinede çalışmıyor). Dalga başına ≤ 4 paralel implementer, ayrık dosya kümeleri.
- **SDD betikleri** (`review-package`, `task-brief`) ANA depo kökünden koşulur (worktree'den koşulursa paketi
  worktree'nin `.superpowers/`una yazar).
- **Her dispatch'e:** "HİÇBİR ŞEY SİLME", ayrı scratch alt dizini, rapor dosyası + kısa son mesaj, holdout'u AÇMA,
  DB/.env yok (gerekmedikçe). Model parametresi verilmez (opus miras); K1 incelemeleri ve kırmızı takım `fable`.
- **İnceleme kalıbı:** inceleyici görev kodunun planla bayt eşliğini mekanik doğrular ve mutasyon tablosunu `git archive`
  kopyasında BAĞIMSIZ koşar; kendi mutasyonlarını da dener — Faz 3'te üç Important (R153–R155) böyle bulundu.
- **Ölçüm önce:** gerçek veri kararları (kadans, süre, yineleme) ölçülür, ölçüm belgesine komutuyla yazılır.
- **Takma adlar TAHMİN edilmez:** aynı gün, aynı lig, aynı ev/deplasman konumundaki tek satırdan okunur.
- **Migration'lar** Supabase `apply_migration` (proje `aaxadphezxavohkhqdrf`), doğrulama yalnız okuma sorgusuyla;
  append-only tablolara deneme satırı yazılmaz.
- **Temizlik:** Faz 3'ün worktree ve dalları 2026-09-23'te silindi (kullanıcı onayı); SDD defterleri
  (`.superpowers/sdd/*`, gitignored) korunur — kararların tam kaydı oradadır.

### 0.6 İzlenecekler (Faz 3'ün ekledikleri)
1. **2026-09-26 cuma 12:35 UTC** ilk karar günlü gölge turu: `gölge: karar N · yazılan satır M · eşlenemeyen U ·
   bayat durum B`; `U > 0` ise adlar aynı gün/lig/konum kuralıyla `config/history_aliases.yaml`a (yoksa grup 10 gün
   bayat). ned.1/bel.1'in ilk canlı maçlarından sonra `live parity` (E3) yeniden.
2. **2026-09-26 cuma 09:50 UTC** ilk `history-dispatch-friday`; **2026-09-29 salı 09:50** haftalık `history.yml`
   (selftest + model W1–W4, ~7,5 dk).
3. `history_leagues.yaml`/`history_lock.yaml` değişirse gölge ve model adımı exit 11 — `model_faz3.yaml` yeniden
   üretilmeli (Faz 3 HANDOFF §3.3/7).

**Geçmiş: oturum 6'nın açılış öncesi durağı (2026-09-23 ~09:00 UTC; kullanıcı "evet" dedi, açılış yapıldı):**
- Task 0–12 `main`de (son `bf5a06d`, CI yeşil); defter `.superpowers/sdd/2026-09-23-faz3-model-walkforward/progress.md`
  (R149–R156). Migration 0009/0010/0011 canlı; I6 kanıtı (0010 önce kırmızı, sonra yeşil); DB bağlı kapı 11/11.
- Seçim (S) `config/model_faz3.yaml`: Elo k=10, ha=65, linear, regress 0,2, newcomer 75, **ordered**; DC ξ=0,003,
  sırt=0,003. **Izgara ucu bulgusu** (k, ξ, sırt) — genişletme kararı kullanıcıda.
- E raporu `docs/reports/2026-09-23-faz3-walkforward.md`: W1 ham ΔLL 0,0002 [0,0000, 0,0005]; runner'da W1–W3 GEÇTİ.
- Ön kayıt `config/faz3_preregistration.yaml` (`c129cc3`), prova yeşil (holdout AÇILMADI), kırmızı takım temiz
  (5 Minor, R156 ile ertelendi). `holdout_access_log` = 0.
- **Sıradaki adım: Task 13 Step 7 — kullanıcının açık "evet"i, sonra Step 8 TEK açılış** (plan Task 13).

**Önceki plan notu — FAZ 3 UYGULAMASI:** "`docs/HANDOFF.md` §0'dan devam et" → planı `superpowers:subagent-driven-development`
ile yürüt; yeni worktree (`git worktree add`), dalga 0 (Task 0: scipy controller commit'i + iki gerçek veri ölçümü).
Durma noktaları: Task 13 holdout açılışı ÖNCESİ kullanıcının açık "evet"i (P14). Plan, ölçülmeyenler listesini ve
yürütme defterini kendisi taşır.

**Geçmiş: oturum 5'in başlatma tablosu (izler bitti)**

**Sıradaki oturum — PARALEL İZLER (kullanıcı kararı 2026-09-22: izler birbirini kırmadan paralel yürür)**

Yeni oturumda: "`docs/HANDOFF.md` §0'dan devam et" → bu tabloyu oku → `git worktree list` ile başla. İzler
ayrı worktree'de, ayrı dalda, AYRIK dosya kümeleriyle yürür; her iz kendi SDD defterini tutar
(`.superpowers/sdd/<plan-adı>/`). Bir izin dosyasına öteki YAZMAZ (tek-yazar kuralı).

| İz | İş | Dal · worktree | Yazdığı dosyalar (YALNIZ bunlar) | Dokunmaz |
|---|---|---|---|---|
| **A** | Lig ekleme: N1, B1, AUT (Faz 2 HANDOFF §5) | `feat/leagues-n1-b1-aut` · `.worktrees/wt-leagues` | `config/leagues.yaml`, `src/football_edge/leagues.py` (`footystats_path` isteğe bağlı), `src/football_edge/collectors/*` ve `odds_api.py` kayıtları, bunların testleri; kapı sabitleri (`verify.sh` `EXPECTED_MIN_*`) GEREKİRSE yalnız bu iz | `docs/superpowers/**`, `history/`, `backtest/`, `market/` |
| **B** | Faz 3 tasarımı ve TDD planı (model + walk-forward) | `docs/faz3-plan` · `.worktrees/wt-faz3` | yalnız `docs/superpowers/specs/2026-*-faz3-*.md`, `docs/superpowers/plans/2026-*-faz3-*.md` (+ ölçüm belgesi) — KOD YOK | `src/`, `tests/`, `config/`, `verify.sh` |
| **C** | İzleme + temizlik (ana oturum, controller) | `main` | `docs/HANDOFF.md`, `docs/RUNBOOK.md` (gerekirse) | izlerin dosyaları |

- **A — adımlar:** (1) footystats sayfası var mı ölç (yalnız `collector._guarded_get`, robots; football-data ölçümü
  gerekirse runner'da — yerel ağ ulaşamıyor); (2) `footystats_path` isteğe bağlı, altı canlı ligin davranışı sabit
  (TDD); (3) The Odds API anahtarları (ölçüm belgesi §2.5) ve **günlük kredi maliyeti hesaplanıp kullanıcıya
  sorulur — kredi harcayan etkinleştirme onaysız YOK** (bütçe 500/ay); (4) toplayıcı başına uygunluk (tff yalnız
  Türkiye); (5) `config/history_aliases.yaml` ilk canlı kapanışlardan sonra — ad TAHMİN edilmez.
- **B — adımlar:** `superpowers:brainstorming` → tasarım (kullanıcı onayı) → `superpowers:writing-plans` →
  bağımsız plan incelemesi (Faz 2 deseni: planın kodu plan metninden tek ağaca kurulur). Girdi: Faz 2 HANDOFF §3
  (ölçülmeyenler, 43 madde) ve §6 (ön koşullar: walk-forward, canlı bağlam kurucusu + eşitlik testi — bağlam VE
  `observe` akışı, Elo fiti, scipy dalga 0'ı, `final_eval` işçilere anahtar değil SEÇİLMİŞ satır verir — 12i),
  DEFERRED §12, §14. Holdout Faz 3'e dek AÇILMAZ; tasarım açılışı tek sefer ve kayıtlı yapar. Uygulama, plan
  onaylandıktan SONRA ve A birleştikten sonra başlar (A'nın lig kümesi Faz 3'ün canlı kapsamını belirler).
- **C — adımlar:** (1) 2026-09-23 sabahı ilk cron'lu `collect-daily` + footystats; (2) **2026-09-29 09:50 UTC**
  `history.yml` — selftest adımının runner'daki ilk turu (yerelde 25 sn); kırmızıysa logu oku, kapıyı gevşetme;
  (3) temizlik YALNIZ kullanıcı onayıyla: `.worktrees/wt-{parser,devig,lock,harness,sync,bridge,efficiency,selftest,
  r111,method,t11fix,measure}`, dalları `feat/faz2-*`, yerel + uzak `measure/r104-width` (hepsi birleşti ya da
  ölçüm artığı) ve Faz 2 SDD defter dizinleri.
- **Birleştirme kuralı (her iz):** kendi dalında her commit'ten sonra tam `verify.sh` (log dosyasından, SKIP adıyla);
  `main`e `--no-ff` merge ÖNCESİ `git fetch origin && git merge origin/main` + kapı; push, CI yeşil. Force/rebase yok.
  İki iz aynı anda merge ediyorsa sırayla: önce biri push'lar, öteki yeniden fetch + merge + kapı.
- **Başlatma istemi (yeni oturuma yapıştır):** "`docs/HANDOFF.md` §0'dan devam et. İz A ve İz B'yi paralel
  başlat (ayrı worktree, SDD, her dispatch'e 'hiçbir şey silme'); İz C'yi ana oturumda izle. Durma noktaları:
  A'da kredi harcayan etkinleştirme, B'de tasarım onayı."

**Oturum 4'ün kararları** (gerekçe ve bedel defterde; tam liste Faz 2 HANDOFF §4): R106 — `ci.yml` yorumu ·
R107/R113 — dalga implementer'ları ayrı worktree'lerde paralel · R108 — fikstür için ayrıştırıcı gevşetilmez ·
R109 — DEFERRED 12e T6'ya eklenmez · R110 — 0006'ya TRUNCATE tetikleyicisi · R111 — boş fazla kuyruk kırpılır ·
R112 — kilit 7.646 ile · R114–R116 — verimlilik raporu tek lig yüzünden düşmez, yakalama dar · R117 — denetçi fable ·
R118 — `DEFAULT_METHOD = power` · R119 — AST kuralı `load_files`/`parse_file`/`_parsed`ı korur · R120 — Oracle
kanaryası; K4 fiyat sütunu kontrolü · R121 — F3/F5 ertelendi, F4 kabul.

**Oturum düzeni (öğrenilenler)**
- Bağlam ~%95'e yaklaşınca devir: koşan görev bitince defter + bu bölüm + commit/push, sonra yeni oturum —
  otomatik sıkıştırmaya güvenme.
- `Agent`'ın `isolation: "worktree"`ü bu makinede çalışmıyor (WorktreeCreate hook yol döndürmüyor) → worktree'yi
  `git worktree add` ile elle aç.
- Alt ajanlar izinsiz `rm -rf` yaptı (kendi scratch dizinleri) → her dispatch'e "hiçbir şey silme" yaz; paralel
  ajanlara scratchpad'de AYRI alt dizin ver. Bazı implementer'lar rapor dosyasını yazamıyor → raporu son mesajda
  iste, controller kaydeder.
- Yerel ağ football-data.co.uk'a ULAŞAMIYOR (bağlantı sıfırlanıyor) — kaynak ölçümleri runner'da, geçici dalda.
- Scratchpad'den `gh` çağrısı → `-R popiliadam/football-edge`.

**İzlenecekler (kendiliğinden olmalı; olmazsa RUNBOOK §3)**
1. **2026-09-29 09:50 UTC `history.yml`** — selftest adımının runner'daki ilk turu (yukarıda, adım 3).
2. 2026-09-23 07:10 UTC ilk cron'lu `collect-daily` ve 10:40 yerel ilk zamanlanmış footystats turu:
   ikisi de yeşil, `açık alarm yok`. TFF atanmamış günlerde `tff: 0 yeni gözlem` normaldir (R72).
3. Bekçinin yeni kodla ilk turu (seal'in seyrek `schedule` turu): `🔴 bekçi kırmızı` açılmamalı.
4. 2026-09-26'dan itibaren `sources-audit` (05:41 UTC) robots tarihini ilk kez kendisi ilerletir.
5. CI'da bir kez `astral-sh/setup-uv` 10 dk takıldı (2026-09-22, rerun yeşil); tekrarlarsa adım düzeyi timeout
   (DEFERRED 14u).
6. **İz A sonrası:** ~~06:22 snapshot 8 anahtar~~ (09-23 yeşil); N1/B1 maçlı ilk mühür turu yeşil ve maçı mühürlüyor
   (milli ara sonrası ilk hafta); 10:40 yerel footystats turu 8 lig ok (bel.1 satır sayısı — DEFERRED 15d).

**Kullanıcıdan beklenenler** (2026-09-23 güncel)
1. Depoyu GitHub'da **Watch** etmek (alarm e-postaları) — ölçülemedi (`gh` token'ında `notifications` yok).
2. DEFERRED 10t kararı (yerel işi yetkisiz ayrı macOS kullanıcısında koşturmak) — şimdilik kabul.
3. İz B için Netlify sitesi ve alan adı.
4. **Faz 4 için `TYPESAFE_API_KEY`** ve dil kalibrasyon etiketleri (dil başına ~100; §0.3/2–3).
5. ~~Faz 2 Task 12'de lig önerisi~~ — verildi (N1, B1, AUT). ~~Worktree/dal silme onayları~~ — Faz 2 ve Faz 3 için yapıldı.
6. ~~Faz 3 holdout açılışı~~ — **2026-09-23 onaylandı ve yapıldı** (tek açılış).

---

## 1. Senin yapacağın şeyler

**1. Tetikler canlı — yapman gereken bir şey yok.** `seal` (15 dakikada bir) ve `snapshot`
(06:22 UTC) Supabase pg_cron'dan `workflow_dispatch` ile tetikleniyor (0003/0004, RUNBOOK §3);
token Vault'ta `github_seal_dispatch` adıyla, süresiz. Kırmızı bir tur `ops-alert` etiketli bir
issue açar, yeşil tur kapatır; tetikler durursa bekçi `🔴 bekçi kırmızı` açar. Toplayıcılar da aynı
yolla koşar: `collect-daily` (tff, venues; 07:10 UTC) ve `collect-news` (2 saatte bir); footystats
senin Mac'inde launchd ile koşar (RUNBOOK §3.9 — Mac'in gün içinde bir kez açık olması yeter);
`fetch-results` kredi harcadığı için elle (R67). Bekçi kalan Odds API kredisini de izler. Haber
almak için depoyu GitHub'da **Watch** etmen yeterli. (GitHub'ın `schedule`ı 51 saatte ~203 mühür turunun
16'sını koşturmuş, 47 maçın kapanış fiyatı kalıcı kaçmıştı — DEFERRED §10.)

**2. Push, merge ve migration'ları asistan yapar.** Bu projede SEO eklentisi (ve onun push kapısı)
`.claude/settings.local.json` ile kapalı; Supabase migration araçlarına izin verildi.
**Asla `--force`:** `seal.yml`in bot commit'leri zincir çıpalarıdır, force push onları siler.
Push reddedilirse önce `git pull --no-rebase origin main`.

**3. robots.txt doğrulaması otomatik.** `kaynak-politikası` adımı `robots_verified_at` için
**30 günlük** tazelik ister; `sources-audit.yml` canlı robots.txt anlık görüntüyle aynıysa tarihi
kendisi ilerletir (RUNBOOK §3.7). Bir robots.txt değişirse tarih ilerlemez, tur kırmızı olur ve
`🔴 sources-audit kırmızı` açılır: o zaman robots'u elle incele. **Kapı gevşetilerek yeşil alınmaz.**

---

## 2. Canlı ve doğrulanmış durum

| Şey | Değer | Nasıl doğrulandı |
|---|---|---|
| Supabase | `football-edge` · `aaxadphezxavohkhqdrf` · eu-central-1 | ACTIVE_HEALTHY |
| Bağlantı | `aws-0-eu-central-1.pooler.supabase.com:5432` (**session** pooler) | canlı bağlanıldı, `TimeZone=UTC` |
| **Oran defteri** | **3.717 satır · 51 maç · 25 bookmaker** | Faz 0 canlı snapshot, exit 0 |
| Zincir | **SAĞLAM**, `--full` ile GENESIS'ten tarandı | Task 2: canlı `verify-chain --full` → `kontrol=3717` |
| Çıpa | `ledger/head-2026-09-19.txt` | `publish-head` |
| Append-only (oran) | UPDATE ve DELETE **reddedildi** | Faz 0: 2 test, gerçek Postgres |
| **Yeni şema** | `source_observations` · `match_results` · `entity_aliases` | Task 4: canlı migrasyon, tablo listesi doğrulandı |
| Append-only (gözlem) | UPDATE ve DELETE **reddedildi** | Task 4: gerçek veritabanında, **tam yetkili rolle** denendi |
| Toplu yazma | 200 satır yazıldı → zincir bağı geri okundu → geri alındı | Task 1: canlı Postgres sondası |
| FootyStats | 6 lig 200; tur 1 **114 gözlem**, tur 2 **0** · 09-22: runner'dan 6/6 **403**, Mac'ten 200 → iş Mac'te (R73) | Task 5: canlı ×2 · 09-22: run 35710579845 + yerel tanı |
| TFF | `pageID=600`: 7 lig / **63 satır**; tur 1 **62 gözlem**, tur 2 **0** · 09-22: 63/63 hücre boş (hakemler açıklanmamış) → 0 gözlem, hata değil (R72) | Task 6 + bağımsız inceleme · 09-22: yerel tanı, sayfa şekli sağlam |
| Ajansspor haber | **1000 yeni gözlem**, exit 0 · runner: **193** (09-22 09:28, elle) + **3** (10:07, cron) | Task M: `fetch-news` canlı · 09-22: `collect-news` turları |
| Stadyum koordinatı | **1 yeni** (Rams Park, `Q81492`) | Task M: `fetch-venues` canlı |
| **Hava yolu** | **HİÇ ÇALIŞMADI** | veritabanında uygun maç yok (R46) — olmuş gibi sayılmadı |
| **`fetch-results`** | **HİÇ KOŞMADI** | bilinçli (R45): API kredisi yakar |
| **Dil kalibrasyonu** | **HİÇBİR DİL ÖLÇÜLMEDİ** | `TYPESAFE_API_KEY` yok, insan etiketi yok |
| Kapı | 10 adım PASS + `zincir` SKIP · `main` (Task 11 kapanışı, `7ff6457` sonrası): **1530 passed, 2 skipped** · contract 18 · **leakage 265** · `a647f36`'da DATABASE_URL bağlı: 11/11, 1380 passed, zincir SAĞLAM | `main`: yerel, `TMPDIR` depo dışında, log dosyasından okundu; CI yeşil · dalga 0 (`e521ed5`) taze klonda aynı sayı |
| **Mühür (`seal.yml`)** | 09-19 14:39 → 09-21 14:15: **16 tur** (~203 beklenirdi), 15'i `exit 5`; **47 maç kalıcı kayıp** | `gh run list` + tur loglarındaki "kaçan mühür" listelerinin birleşimi |
| Tetikler (pg_cron → `workflow_dispatch`) | `seal-dispatch` (her 15 dk) ve `snapshot-dispatch` (06:22 UTC) **canlı**; 0004 09-22 06:06 UTC uygulandı; `snapshot.yml`in `schedule`ı kalktı | seal 05:45/06:00/06:15 ve snapshot 06:22 → cron `succeeded` + `204` → turlar success (controller, 09-22) |
| Toplayıcı tetikleri | `collect-daily-dispatch` (07:10 UTC), `collect-news-dispatch` (2 saatte bir) — 0005 09-22 09:27 UTC uygulandı | elle 09:28 → `204`/`204`; cron 10:07 → `succeeded` + `204` → `collect-news` yeşil |
| Alarm ve bekçi | `ops-alert` issue'ları; bekçi tetikleri, Odds API kredisini ve Mac'in kalp atışını (72 sa) izler | #1 `🔴 collect-daily kırmızı` 09:29 açıldı (github-actions, etiketli) — 10:57:58'de yeşil `collect-daily` turuyla (run 35718803834) "yeşile döndü" yorumuyla kapandı; bekçi yeni kodla henüz koşmadı |
| robots doğrulaması | otomatik (`sources-audit.yml`, RUNBOOK §3.7) | elle tur 09-22 (35715215485): 7/7 kaynak sapma yok, runner footystats robots'unu okuyor; ilk otomatik ilerletme 09-26'dan itibaren |
| Loglarda sır | Odds/TypeSafe anahtarı, `DATABASE_URL` ve parolası redakte; yakalanmayan istisna da (C7) | uçtan uca bozuk DSN → parola parçası 0; runner turlarında (daily/news/seal) sır sayımı 0/0/0 — maskeleme sınanmadı (10n) |
| Çıpa push'u | yalnız commit varsa, merge ile en çok 3 deneme, checkout güncel uç (C6) | 09:30 turu `zincir başı değişmedi — commit ve push yok`: gürültü durdu; ret→merge yolu henüz koşmadı |
| Kırmızı tur alarmı | `ops-alert` issue + dispatch bekçisi (`scripts/ops_alert.py`, RUNBOOK §3.6) | runner'da ve gerçek GitHub'da koştu: #1 açıldı, 10:57:58'de yeşil `collect-daily` turuyla (run 35718803834) "yeşile döndü" yorumuyla kapandı |
| footystats yerel işi (Mac) | launchd, 4 dilim + oturum açılışı, UTC günü başına bir tur; rapor `footystats-local.yml`; kalp atışı 72 sa, kendi alarmı (R73–R76) | Kuruldu 2026-09-22 10:57 UTC: ilk tur `main` `6dccfa8` ile **114 yeni gözlem**, exit 0; rapor → `footystats-local.yml` yeşil (`açık alarm yok`) |
| Odds API | **494/500 kredi** | Faz 1 bir kredi bile harcamadı |

`.env` (gitignored, izin 600): `ODDS_API_KEY`, `DATABASE_URL`. **`TYPESAFE_API_KEY` `.env`de ve
repoda YOK** — ama kullanıcının kabuk ortamında tanımlı (09-22 ölçüldü, değer okunmadı). Dil
kalibrasyonu (`calibrate`, PARA HARCAR) bununla koşulabilir; karar kullanıcıda.

---

## 3. Faz 1 ne üretti

13 görev · 5 paralel worktree · **0 Critical** bulgu · **40'tan fazla Important**, hepsi
kapatıldı · 98 → **365 test** (+18 `contract` etiketli).

Her görev ayrı bir inceleme ajanından geçti; her düzeltme turu kendi re-review'ünü aldı.
İncelemeciler rapora güvenmedi: mutasyonları izole klonlarda (`git archive`) canlı uygulayıp
RED gördüler, sonra geri aldılar.

**Ne kuruldu:** kaynak kayıt defteri ve robots.txt'in **kodla zorlanması** · toplayıcı çatısı
(`fetch → doğrula → yaz`) · append-only gözlem deposu · beş toplayıcı (FootyStats xG, TFF
hakem, Ajansspor haber, stadyum/hava, maç sonucu) · saf Elo motoru · varlık eşleme (Jev) ·
dil kalibrasyon harness'ı ve üretim kapısı. Ayrıca Faz 0'ın iki borcu kapandı: oran defterine
**toplu yazma** ve `verify-chain --full` + haftalık tam tarama.

**Öğretici olan üç şey** — ayrıntı `docs/phases/01-toplayicilar/HANDOFF.md` §6:

1. **Doğrulanmamış bir ölçüm YÖNTEMİ, hiç ölçmemekten tehlikelidir.** Bir regex'in örtüşen
   eşleşmeleri yutması, doğru olan spec'i "düzelttirdi" ve toplayıcıyı boş bir sayfaya
   yönlendirecekti. Yanlış sonuç "ölçüldü" etiketiyle dolaşır.
2. **Kırmızı veremeyen bir test, planın KENDİ verdiği kodda en az dört kez çıktı.** Kuralı
   yazan taraf, kendi ürettiği testlerde çiğnedi. Artık her testin kırmızı verebildiği
   mutasyonla kanıtlanıyor.
3. **Tipli bir arayüz cevabın ŞEKLİNİ garanti eder, DOĞRULUĞUNU asla.** Model, sunulan
   seçenekler kümesinin dışından bir cevap döndürebiliyordu ve o değer veritabanına
   yazılıyordu. Üyelik artık BİZİM tarafımızda kontrol ediliyor.

---

## 4. Verilen kararlar (Ruling listesi)

Tam gerekçeler `.superpowers/sdd/2026-09-19-faz1-toplayicilar/progress.md` içinde — **o dizin
gitignored, yani merge etmez ve yalnız bu makinede durur.** Faz 2'yi bağlayan ruling'ler
`docs/phases/01-toplayicilar/HANDOFF.md` **§4**'te; ertelenen minor bulgular
`docs/DEFERRED.md` **§9**'da. Başlıcaları:

1. **`declared_paths` GERÇEKTEN ÇEKİLEBİLİR URL olmalı, temsilî önek değil.** Önek, kapının
   hiç istenmeyen bir yolu ölçmesine yol açar — izinli kaynağı kapatır ya da izinsizi geçirir.
2. **User-agent sahteciliği YOK.** Plan `ClaudeBot` kimliğini kullanıyordu; ClaudeBot
   Anthropic'in tarayıcısıdır, biz değiliz. *Ölçüldü: dürüst kimliğin bedeli sıfır.*
   **2026-09-22 (R77):** erişim yöntemi kuralı olarak genişletildi — izinli (dürüst kimlikli
   headless tarayıcı, adaptive seçiciler, resmî API, izin istemek, meşru ortam) ve yasak
   (kimlik/parmak izi taklidi, bot kontrolü ya da CAPTCHA aşma, IP/proxy döndürme, 403/429'u
   yok sayma) listeleri spec §3.2.1'de.
3. **RFC 9309 uyumlu ayrıştırıcı zorunlu** (`protego`). stdlib iki YÖNDE birden yanlıştı.
4. **Ham üçüncü taraf içeriği depoya girmez** — public depoda commit etmek yayınlamaktır.
5. **`access_basis: robots | api_terms`** — API host'u ile web sitesi ayrımı koda geçti,
   `api_terms` kaynaklar `terms_url` taşımak zorunda ve kapı denetliyor.
6. **Kısmî kayıp sessiz geçemez** — bulunandan az yazan bir tur "başarı" raporlayamaz.
7. **`written` COMMIT'TEN SONRA sayılır.** Faz 0'ın dört düzeltme turuna mal olan hata:
   *"başarısız değil" ≠ "kalıcı olarak yazıldı."* R48 venues/news/results'ta düzeltti;
   footystats ancak son bütün-dal incelemesinde düzeldi (I-1,
   `test_collect_does_not_count_a_league_whose_commit_fails`). tff sayıyı yalnız commit
   başarılıysa döndürür.
8. **Saat dilimi iki tarafta da zorlanır** — istek tarafında UTC guard, yanıt tarafında
   `timezone=GMT`. *200, doğru veriyi aldığımızın kanıtı değildir.*
9. **`assert_fresh` yalnız KAYNAĞIN verdiği `observed_at` üzerinde çağrılır** — toplayıcı
   kendi `now`unu basıyorsa iddia her zaman doğrudur, yani hiçbir şey ölçmez.
10. **Zamanlama Faz 1 kapsamı değil** — ama "hiç koşmayan toplayıcı hiçbir şey toplamaz"
    gerçeği adıyla yazıldı, sessizce varsayılmadı.
11. **Kalibrasyon harness'ı yazılır, ölçüm ertelenir.** Spec §5.4'ün şartını **karşılamıyor
    ve karşıladığını iddia etmiyoruz.**
12. **`collect.py` 800 satır sınırında teslim edilmez** — üç kez bölündü (`anchors.py`,
    `fetch.py`, `rounds.py`), 515'e indi.

---

## 5. Kapının ÖLÇMEDİĞİ şeyler

**Tam liste: `docs/phases/01-toplayicilar/HANDOFF.md` §3 — hepsi adıyla.**
Bir sonraki fazın üstüne inşa etmemesi gerekenler:

1. ~~**TOPLAYICILAR HİÇBİR YERDE KOŞMUYOR.**~~ **09-22'den beri koşuyor:** `collect-daily`
   (tff, venues) ve `collect-news` pg_cron'dan, footystats Mac'te launchd ile (R73). Kapsam hâlâ
   dar: TFF yalnız bu haftayı, venues tek stadyumu veriyor (madde 9, 10).
2. **DİL KALİBRASYONU HİÇBİR ŞEY ÖLÇMEDİ** ve spec §5.4'ün Faz 1 şartı **KARŞILANMADI.**
   Kapı yeşil, çünkü ölçtüğü soru "ölçülmemiş bir dil açık mı" ve cevap "hayır". **Yeşil
   kapı, ölçümün yapıldığı anlamına gelmiyor.**
3. **`fetch-results` hiç koşmadı** (bilinçli, kredi); **`fetch-venues`in hava/UTC yolu hiç
   koşmadı** (veritabanında uygun maç yok).
4. **`source_observations`ın HASH ZİNCİRİ YOK** — özellik girdisi kurcalanırsa dış çıpa
   bunu göstermez.
5. **Varlık eşlemenin insan gerçek-referansı YOK.** Eşiğin altı reddediliyor, ama eşiğin
   ÜSTÜNDEKİ bir eşleşmenin DOĞRU olduğunu hiçbir şey doğrulamıyor. `map-entities` bugün
   yalnız `footystats`ı eşliyor ve **`entity_aliases`ı üretimde hiçbir şey okumuyor.**
6. **Elo'nun `k`, `home_advantage` ve marj eğrisi FİT EDİLMEMİŞ iskeledir.**
7. **FBref kapalı → GLOBAL HAKEM VE SEYİRCİ VERİSİ YOK.** Faz 3'ün baz modeli hakem
   özelliği **olmadan** kurulmalı. Understat kapalı → altı ligin xG'si **tek kaynakta**,
   yedek yok. ClubElo kullanılamaz.
8. **Google News hem robots ile kapalı hem lisansı amaçlanan kullanımı yasaklıyor** —
   adaptör `enabled: false` teslim edildi; spec §3.2/1'in kaçış yolu fiilen kapalı.
9. **TFF yalnız bu haftayı veriyor**; VAR/AVAR sayfada `(V)`/`(A)` olarak **var ama
   toplanmıyor.** **Ajansspor'un yapısal yolları kapalı → muhtemel 11 ve sakat/cezalı
   listesi ALINAMIYOR** (spec §3.1 bunları bekliyordu).
10. **`fetch-venues` tam olarak BİR stadyum kapsıyor** — "hava özelliği var" varsayımı
    bugün yanlıştır.
11. **`source_observations`ta iki kalıcı sonda satırı var** ve kaldırılamaz (kaldırmanın tek
    yolu `DISABLE TRIGGER`, RUNBOOK §2.3 yasaklıyor). Korumanın çalıştığının da kanıtı.
12. **`seal.yml` sığ checkout yapıyor** → çıpa silme tespiti 15 dakikalık turda değil,
    haftalık `full-scan.yml`de: gecikme **en fazla 7 gün**.
13. **`cur.rowcount`un `executemany` sonrası davranışı canlı Postgres'e karşı doğrulanmadı**
    — etkilenen raporlanan SAYI, yazılan satırlar değil.
14. ~~**Faz 1'in beş workflow'unun hiçbiri bir runner'da koşmadı**~~ 09-22'de `collect-daily`,
    `collect-news` ve `sources-audit` koştu (canlı robots sapması: 7/7 kaynak yok). `full-scan`
    henüz koşmadı; `collect-daily`nin ilk turu footystats 403'ü ve TFF'nin atanmamış haftasını
    buldu (R72, R73).
15. Faz 0'dan devreden ve kapanmayan: en az yetkili rol yok · `shellcheck`/`actionlint` yok ·
    `mypy` `tests/`i görmüyor · coverage yok · secret taraması git geçmişini taramıyor.
16. **`latest_observations` güncel durumu DEĞİL, içerik başına İLK görüleni döner.** Bir değer
    geri dönerse (X → Y → X) "en yeni" **Y** çıkar, hatasız. Faz 2 gözlem deposunun "en
    yeni"sini güncel durum sanmamalı; düzeltme migrasyon ister —
    `docs/phases/01-toplayicilar/HANDOFF.md` §3.9/31.

---

## 6. Faz 2 — nereden başlanır

**Yol haritası:** `docs/superpowers/plans/2026-09-19-faz-1-7-yol-haritasi.md` (Faz 2 bölümü)
**Ön koşullar:** `docs/phases/01-toplayicilar/HANDOFF.md` §5
**Devralınan borç:** `docs/DEFERRED.md` (§9 Faz 1'indir)

Faz 2 = tarihsel taban · backtest harness · piyasa verimliliği · sızıntı denetimi. **Tamamlandı (2026-09-22) —
devir belgesi `docs/phases/02-tarihsel-taban/HANDOFF.md`**; bu bölüm yalnız başlangıç bağlamıdır.

**Birincil girdi football-data.co.uk'tur** (Faz 2 tasarımı D1; `xgabora/Club-Football-Match-Data` bırakıldı:
kapanış oranı yok, ek ligler 2024-12'de bitiyor — ölçüm belgesi
`docs/superpowers/specs/2026-09-22-faz2-olcumler-ve-kararlar.md`). Lisans sorusu artık doğrudan football-data
içindir (ana spec §10/2): özel depolama, yalnız türetilmiş sayısal özellik, ham satır yayımlanmaz; ticari
lansmandan önce avukat ve site sahibinden yazılı izin.

**Faz 1'in zamanlama borcu İz C'de ödendi:** dört `fetch-*` komutu `collect-daily` / `collect-news` ile
pg_cron'dan tetikleniyor (0005 uygulandı — §2); `fetch-results` kredi harcadığı için elle (R67).

---

## 7. Çalışma disiplini (bu projede öğrenilenler)

- Kapı çıktısı **dosyadan** okunur. `SKIP` geçmek değildir, adıyla raporlanır.
- **Bir ölçüm YÖNTEMİ doğrulanmadan sonucu kural yapılmaz.** Yanlış sonuç "ölçüldü"
  etiketiyle dolaşır ve doğru olan kaydı devirir.
- Bir test, konusunu **yeniden yazıyorsa** yalnız aynı kodu iki kez yazabildiğinizi
  kanıtlar. Her testin **kırmızı verebildiği mutasyonla kanıtlanır.**
- **Planın yazarlığı kendi işini notlandıramaz.** Plan-mandated bir bulgu da bulgudur.
- **Tipli bir arayüz cevabın şeklini garanti eder, doğruluğunu asla.**
- Implementer koşarken **`git add -A` yok** — yalnız açık yollar.
- Append-only tabloya test satırı yazma: silinemez. Sondayı **transaction içinde** koş,
  geri al. (Bu kural Faz 1'de ihlal edildi ve bedeli iki kalıcı satır oldu.)
- Paralel implementer **yalnız izole worktree'de**, ve **tek-yazar** sınırı dispatch'ten
  ÖNCE taranır. Faz 1'de beş dal sıfır çakışmayla birleşti.
- Her görev: implementer → rapor → inceleme paketi → inceleme ajanı → defter. Atlanmaz.
- Model: varsayılan **opus**, çok karmaşık işlerde **fable**, **haiku asla**.
- Mutasyon kanıtı `PYTHONDONTWRITEBYTECODE=1` ile koşulur: aynı boyutlu, aynı saniyede geri alınan
  düzenleme bayat `.pyc` bırakır ve geri yüklenen kaynak mutant bytecode'u çalıştırır.
- Son doğrulama taze bir klonda ve `TMPDIR` klonun DIŞINDA: bir test `tmp_path`in git deposu
  dışında olduğunu varsayıyor (R63).
- GitHub `schedule`ı güvenilmez (51 saatte ~203 turun 16'sı): kaçırılamaz işler pg_cron →
  `workflow_dispatch` ile tetiklenir.
- `main`e bot yazıyor: push'tan önce fetch + merge, asla rebase ya da force.
- Loglar public: yeni bir kimlik bilgisi `_log_secrets`e de eklenir (RUNBOOK §3.8, DEFERRED 10o).
- Risk kademeleri ve paralel dalga kuralları yol haritası v2 §3–§4'te: K1 (defter, mühür, model,
  güvenlik) tam inceleme; en çok 4 paralel implementer; her dalgadan önce tek-yazar taraması.

---

## 8. 2026-09-21/22 oturumunda verilen görevler

Her ajan işi aynı yoldan geçti: brief → implementer (izole worktree) → bağımsız inceleme (opus) →
düzeltme turu → controller mutasyon doğrulaması → `main`e `--no-ff` → taze klon kapısı.

### 8.1 Ajanlara verilen görevler
1. **Faz 1 son inceleme düzeltme turu (Task F)** — limite takılıp yarım kalan dalga tamamlandı:
   `4158f81` (kod), `370caae` (belgeler); kontrol incelemesi 12/12 ADDRESSED; yedi artık (R62):
   `28cbd4f`, `1f6a9b6`.
2. **Faz 1'in `main`e alınması** (controller): `e9acd0f` (origin çıpaları, merge), `668ec61`.
3. **C1 — mühür tetiği** (controller): migration 0003 + testler + RUNBOOK §3 (`e4a3dae`, `1975e5c`,
   `940caef`); yol haritası v2 (`ee65f52`).
4. **Task A — çıpa gürültüsü:** `b2658d7` + düzeltme `10b7e11` → `ee07601`. İnceleme: tek-alan testi
   eksikti (Important), UTF-8 olmayan çıpa (Minor) — ikisi de düzeltildi.
5. **Task B — snapshot pg_cron + `ops-alert` + bekçi:** `8d7ab72`, `1df6d83` + `f4c2d57`, `a75c302`
   → `3b00066`; 0004 uygulandı ve canlıda doğrulandı. İnceleme: bekçi alarmı kendini geri
   çekiyordu → kendi issue'su (R66).
6. **Task C3 — toplayıcı zamanlaması:** `151620f` + `6c12d0d` → `36fc89c` (0005 uygulanmadı — §0).
7. **Task C5 — kredi bekçisi + toplayıcı tetik izleme:** `9c687af`, `d6e46c6` + `49fa13a` → `6fdf093`.
8. **Task C4 — robots otomatik yeniden doğrulama:** `4383c6a`, `b27c062`, `368a189` + `07b2af9`,
   `6c82e11`, `9de9875` → `1f89c17` (controller'ın bulduğu `os.replace` kör noktası kapatıldı).
9. **Entegrasyon** (controller): bekçinin izlediği her workflow var + push'lamayan her checkout
   token'ı diske yazmaz (`d0e37c7`), belgeler (`a02158c`), E501 (`8a5456c`).
10. **Task C7 — loglarda sır (K1):** `1a605a0`, `5c6c407` + `f46ac76` → `596b025`, yorum `8465077`.
    İnceleme: yakalanmayan istisna parolayı public loga basıyordu, DSN parolası libpq ile
    uyuşmuyordu — düzeltildi, uçtan uca doğrulandı.
11. **Task C6 — çıpa push'u + checkout güncel uç + test bölme:** `ace2abc`, `731fc4d`, `d38fa9d` →
    `3009c5b` (`tests/test_workflows.py` 1030 → 610 satır; saf taşıma).
12. **Belgeler:** `40dc723`, `6973cde`, `d086d4f`, `f86bb03` ve bu devir.

### 8.2 Kullanıcıya verilen görevler
1. `git push origin main` (iki kez) — **yapıldı** (`4b6a143..668ec61`, `dd963ce..b1eea7c`).
2. `git pull --no-rebase origin main` — **yapıldı** (gerek kalmamıştı).
3. Migration 0003'ü SQL editöründe çalıştırmak — **yapıldı**.
4. Fine-grained GitHub token (hazır form: yalnız bu depo, Actions: Read and write, süresiz) — **yapıldı**.
5. Token'ı Vault'a `github_seal_dispatch` adıyla koymak — **yapıldı**.
6. `.claude/settings.local.json` (SEO eklentisi kapalı + Supabase migration izni) — **yapıldı**,
   yeni oturumda etkin.
7. Depoyu GitHub'da **Watch** etmek — **açık** (alarm e-postaları için).
8. `/pseo-approve` — **kullanılmamalı**: onay ilgisiz `bigcat-tr` defterine düşer.

### 8.3 Bu oturumun kararları (R55–R71; gerekçe ve bedel defterde)
R55 yarım dalganın diff'i korundu (mutasyonla doğrulandı) · R56 #M10 gerçekten kapatıldı · R57 PFDK
uygulanmadı, kayda geçti · R58 yeni §3 maddeleri §3.9'da, eski numaralar sabit · R59 #M28 tek yönlü
bağ (fetched ⊆ declared) · R60 secret adı elle eklendi, türetme testi ertelendi · R61 donmuş sayılar
kaldırıldı · R62 yedi artık tek turda · R63 `TMPDIR` test varsayımı park edildi · R64 origin/main
rebase değil merge · R65 A'nın iki bulgusu düzeltildi · R66 bekçinin kendi alarmı · R67
`fetch-results` zamanlanmadı (kredi) · R68 C3 Minor'ları + `persist-credentials` · R69 C4 Minor'ları;
seal push'u ayrı iş (C6) · R70 C7: excepthook + libpq + bütün kök handler'lar · R71 seal checkout
güncel uç + test dosyası bölme.

### 8.4 2026-09-22 oturum 2 (HANDOFF §0'dan devam)
**Operasyon (controller):** 13 bot çıpa commit'i `--no-ff` birleşti (`646e4d8`), taze klon kapısı,
push; 0005 uygulandı; toplayıcılar elle ve cron'la tetiklendi; ilk `collect-daily` turunun iki
kırmızısı teşhis edildi (yerel tanı, kaynak başına tek istek, veritabanına yazmadan).

**Ajanlara verilen görevler**
1. **T1 — TFF atanmamış hafta (K2):** controller TDD + 5/5 mutasyon → `063e0b6`; inceleme
   (feature-dev:code-reviewer) APPROVED + 1 Important (ayırt edilemeyen durum adıyla, `76739f2`)
   → `c715e01`. Not: bu ajan tipinin kabuğu yok, mutasyonları elle izledi.
2. **T2 — footystats yerel işi (K2):** `c5489b1` (collect-daily'den çıkar) + `cce76f7` (launchd
   işi, 16/16 mutasyon); inceleme (general-purpose, kabuklu) CHANGES REQUESTED: 4 Important,
   20 mutasyonun 12'si kaçtı. Düzeltme turu `e1e3054` (R74, R75; 35/35 mutasyon) → yeniden
   inceleme CHANGES REQUESTED: **Critical** — test dosyasının sahte `.env` satırları kapının
   `secrets` adımını düşürüyordu (birleşseydi mühür turları ilk adımda düşerdi; dalda
   `verify.sh`'ın tamamı koşulmamıştı) + 2 Important → `19a921c` (R76; taze klonda kapı yeşil,
   12/12 mutasyon) → son kontrol APPROVED.

**Kullanıcıya verilen görev:** FootyStats kararı (AskUserQuestion) — **"Mac'te günlük iş"** seçildi.

**Kararlar (gerekçe ve bedel defterde):** R72 TFF: sıfır maç satırı fırlatır, hepsi meşru
görevlisizse boş sonuç; "boş hücre" = `<a>` yok VE metin yok · R73 footystats GitHub-hosted
runner'da koşmaz (test sabitliyor), Mac'te launchd · R74 sonuç `footystats-local.yml`e raporlanır:
alarmı github-actions açar (kendi token'ınla açılan issue bildirim üretmez), raporlar bekçinin kalp
atışı (72 sa) · R75 dört dilim + oturum açılışı + UTC-gün damgası, fetch yeniden denemesi, klon
yoksa yeniden klon, betik `main`den kendini günceller, kurucu atomik yazar ve `bootstrap`ı yeniden
dener · R76 Mac'in kalp atışı bekçi alarmını paylaşmaz (`footystats-local` başlığı, bekçi yalnız
açar); bir deponun kendi `scripts/` kopyası kendini güncellemez.
