# Faz 4 Plan 3 — canlı ayağın ön kaydı (tasarım deltası)

**Tarih:** 2026-10-05 · **Durum:** kullanıcı kararları asistanın önerisine devretti (R187 "en iyi senaryo"; bellek
`user-delegates-to-recommendation`); onay yerine bağımsız spec incelemesi (2 C / 10 I / 8 M, hepsi işlendi — §10) ·
**Ana tasarım:** `2026-09-23-faz4-jev-sinyal-design.md` (R157–R172) · **Plan 2 deltası:**
`2026-10-04-faz4-plan2-canli-hat-design.md` (R173–R187) — burada yazılmayan ve §9'da yerine geçilmeyen her şey aynen geçerli.
**Girdi:** HANDOFF §0.U.4 A · DEFERRED 16k, 17c–17f · `config/jev_questions.yaml` · `features/derive.py`,
`features/shift.py`, `features/tier2.py`, `features/slice.py`, `live/report.py`, `market/metrics.py`.

**Zamanlama:** mühür = `config/faz4_preregistration.yaml` commit'i + açıklamalı etiket `faz4-onkayit`, ilk kademe 2
turundan (2026-10-09 12:35 UTC) ÖNCE. Mühürden önce hiçbir `harman_jev` olasılığı ve hiçbir Jev'li ΔLL hesaplanmaz;
o tarihte `jev_match_answers` boştur (açılış kontrolü 2026-10-05: 0 satır) — pencerenin her verisi mühürden sonra doğar.

---

## 0. Karar özeti

| No | Karar | Gerekçe | Yanlışsa bedeli |
|---|---|---|---|
| R188 | **Seçim dilimi KALDIRILIR (R187'nin kabulü).** Ana spec §7.3'ün "önce ≥ 900 seçim, sonra ≥ 1.800 kapı" yolu yerine TEK canlı pencere; bütün pencere verisi kapı verisidir. Budama (T8), eşdoğrusallık (T9), `≤ 15` özellik listesi Faz 4'te YAPILMAZ | R187: ~33 haberli maç/hafta → seçim 2027-05'te biter, kapıya ~300 maç kalır (kesin GÜÇ YETERSİZ); 35 aday × 900 maçta budama zayıf, çoklu test yükü taşır | Tek önceden kayıtlı özellik sinyalin bir kısmını kaçırır; ötekiler betimsel (D8) |
| R189 | **Tek bileşik özellik, işaret önceden.** Taraf başına zayıflık `Z = (Σ_{k∈W} L_k − L_t2_donus) / 7`, `W` = {`t2_hucum_eksik`, `t2_savunma_eksik`, `t2_orta_saha_eksik`, `t2_kaleci_eksik`, `t2_supheli`, `t2_rotasyon`}. Maç özelliği **`f = Z_dep − Z_ev`** (pozitif = ev lehine; `shift` ev logitine `+β·f`). `t2_hoca_degisim`, `t2_yeni_transfer` bileşiğe GİRMEZ (yön önceden savunulamaz) — D8 | Karışık yönlü soruların düz ortalaması sinyali sıfırlardı; işaret soru metninden okunur, veriden değil | Ağırlıklar eşit (tahmin edilmez) |
| R190 | **Seviye = Jev'in SEÇTİĞİ düzey (mod), beklenen değer DEĞİL:** `L_k = LEVEL_SCORES[choice]` (none 0, low ⅓, medium ⅔, high 1). Haberi olmadığı için sorulmayan taraf `IMPUTED` (`L = 0`). Böylece sorulmuş ve "yok" diyen taraf sorulmamış tarafla AYNI sayıyı alır (inceleme C1: beklenen değerde "çoğunlukla yok" cevabı bile `L ≈ 0,11` verirdi ve `f` haberin içeriğini değil haber VARLIĞINI ölçerdi). Kanonik formül: `f_k = L_k^ev − L_k^dep` (`derive.features_of`, `c_min = 0`), `f = −(1/7)·math.fsum(s_k·f_k)`, `s = +1` (W), `−1` (`t2_donus`); eksik/ölçek dışı cevap `f_k = 0` + `missing` | Kapsam (kulüp büyüklüğü) ile içerik ayrılır; mevcut kod yolu | Mod olasılık bilgisini atar (güç kaybı) |
| R191 | **Prequential β:** `β_i = argmax_{0 ≤ β ≤ 5} Σ_{j∈T_i} log p_jev,j(β)[y_j] − λ·β²/2`, **λ = 1**. Eğitim kümesi `T_i` = pencere içi, kapı kitlesinde (R195), harmanı tam, sonucu yeniden oynatmada bulunan haberli maçlar `j`, öyle ki **`matches.commence_time_j ≤ decided_at_i − 3 saat` VE football-data maç tarihi_j < UTC tarihi(decided_at_i)** (ikinci koşul: `commence_time` ertelemede güncellenir, `db.py` `DO UPDATE`). `T_i` boşsa `β_i = 0`. Çözücü: `[0, 5]` üzerinde `dℓ/dβ`'nın izdüşümlü ikiye bölmesi; `ℓ'(0) ≤ 0` ise `β = 0`, `ℓ'(5) ≥ 0` ise `β = 5`; `|Δβ| ≤ 1e-10` | Her tahmin yalnız önce olmuş sonuçlarla — dürüst örnek dışı. `β ≥ 0` önceden kayıtlı yönün tek yönlü sınaması: yön yanlışsa β → 0 ve kapı geçmez (doğru sonuç). Amaç kesin içbükey → tek çözüm | Başlangıçta β ≈ 0 (§3 güç notu) |
| R192 | **Kanonik kapı hesabı = saklı girdilerin deterministik yeniden oynatması:** `model_predictions` baz satırları (`model_faz3.yaml` sha'sı), dondurulmuş kümenin `jev_match_answers` satırları, football-data sonuçları (17f; gölge raporunun kaynağı, `match_key`) → R189–R191 → D1. Sonradan düzeltilen sonuç satırı (maç `i`ninki de olabilir) düzeltilmiş hâliyle girer: karar anı girdisi değildir, sızıntı sayılmaz | Girdiler karar anında append-only yazılmış; hesap canlı yazıcının başlama gününden bağımsız | Sonuç düzeltmeleri ölçülmez (§6) |
| R193 | **Pencere ve durma.** Birim: gölge satırı olan maç (maç başına tek karar, `shadow.py` `ON CONFLICT`). **Pencere** = `tier2_prompt_version`ı mühürdeki olan ve İLK `side_status` işaretinin `asked_at`i `faz4-onkayit` etiketli commit'in committer saatinden sonra olan kararlar. **Haberli karar** = en az bir tarafının son durumu `asked` olan karar (sonuçtan bağımsız sayım). **Kapanış turu** = haberli karar sayısının ilk kez ≥ `N_stop` olduğu karar turu **ya da** `decided_at ≤ 2027-06-30T23:59:59Z` olan son tur, hangisi önce; aynı tur ikisini birden sağlarsa `n_stop` kapanışıdır. Sonraki turlar pencere dışı (uzatma yok, R171). **Değerlendirme** = kapanış turunun `decided_at`i + 21 gün, BİR kez; o gün sonucu olmayan maç sonuçsuz sayılır. Ara bakış YOK | İsteğe bağlı durdurma canlı p-hacking'dir | GÜÇ YETERSİZ olasılığı yüksek |
| R194 | **`N_stop = 1.800`, mühürde sabit.** Mühürden sonra ek `N_stop` commit'i YOK (ana spec §7'nin "T10'da gerçek sayı" cümlesinin yerine geçer). Gölge serisinden `LL(harman) − LL(piyasa)` maç başı SD'si (ddof 1, pencerenin ilk dört haftası) raporda betimsel | İnceleme I1: `max(1.800, ⌈(2,8016·SD/0,002)²⌉)` SD ≤ 0,0303'te 1.800 verir (0,027 → 1.431); harman ≈ piyasa olduğu için kural fiilen boş ve isteğe bağlı commit bir çatallanma kapısıydı | Gerçek Jev etkisinin SD'si bilinmez |
| R195 | **Dil kümesi önceden kayıtlı KURALDIR.** Mühürde `tr`. Bir dil, mühürlü `jev_model`le önceden bağlı eşiği (`min_n = 100`, `min_accuracy = 0,85`; R182) geçen kalibrasyon raporu commit'lendiği andan sonraki karar turlarından itibaren üretimde ve kapı kitlesindedir; kullanıcı kararı GEREKMEZ (Plan 2 M-6'nın yerine). Eşiği geçmeden üretime alınan dil = **kullanıcı kaynaklı kesinti** (§5). Bir tarafın bataryası karışık dilli haber kümesiyle sorulabilir; tarafın dil kümesi raporda `select_items`in `decided_at`te yeniden çalıştırılmasıyla kurulur ve `item_set_hash` eşitliğiyle denetlenir (uymayan sayılır); D5 maçları `tr` / `en` / `mixed` gruplar | Dil kararı sonuçtan bağımsız etiket doğruluğuna bağlı; EN'in mühürden önce yetişmesi gerekmez | EN girişi kitleyi pencere ortasında değiştirir |
| R196 | **Arşiv ayağına bağlı kalemler kapanır:** T11 holdout 2. açılışı GEREKMEZ (Faz 5'e iki açılış kalır) · D4 kanarya yok (R167 arşiv içindi) · `lag_b_p99` kapı parametresi DEĞİL (canlıda `available_at = max(first_seen_at, published_at_claimed)`, `news.py`), ölçüm betimsel (D9) · DEFERRED **17e kapanır**: `faz4` `PHASES`e girmez (Faz 4'te holdout açılışı yok); 17c/17d Faz 5'in açılışından önceye taşınır | Arşiv KAPALI (17k) | — |
| R197 | **Mühürlü karşılaştırma ayrı pakette:** `harman_jev − harman` farkını hesaplayan TEK modül yeni `football_edge.gate4` paketindedir (`features` `live.store`u import edemez — `tests/test_feature_import_rule.py`); komut kapanış turu + 21 gün koşulu tutmadan adlı exit'le reddeder; AST testi bu modül dışında farkı hesaplayan kodu ve haftalık raporun/`slice-status`un `harman_jev` okumasını reddeder | Ara bakış yasağının kod karşılığı | Mühür kod düzeyinde; DB satırları okunabilir (ana spec §11/6) |
| R198 | **Canlı `harman_jev` gölge yazımı (HANDOFF A.5, R173) KAPI DEĞERLENDİRMESİNDEN SONRAYA ertelenir.** Her tur yeniden fit edilen prequential `β_i` pencere içi ΔLL'nin tek yönlü özetidir; yazılması ya da basılması haftalık ara bakış olurdu (inceleme C2-ii). Site/Faz 5 Faz 4 kapısını zaten bekler | Ara bakış yasağı | `harman_jev` satırları kapıdan sonra geriye dönük yazılır (aynı yeniden oynatmadan) |
| R199 | **Kademe 2 cevabı başlama saatinden sonra gelmişse sayılmaz:** `asked_at ≥ matches.commence_time` (yeniden oynatma anındaki değer = gerçekleşen başlama; ertelenen maçta sonraki saat) olan tarafın bütün `f_k`'ları eksik; `asked_after_kickoff` sayılır | Kademe 2 `decided_at`ten 6 saate dek sorabilir (`tier2.py` karar yaşı); erken maçta Jev canlı bilgi görebilirdi (Plan 2 §4/6 varsayımının sigortası) | Erken başlayan maçların bir kısmı haberli sayılmaz |

---

## 1. Karşılaştırmalar

ΔLL = `LL(harman) − LL(harman_jev)`, `LL = market.metrics.per_match_log_loss` (taban 1e-15); **pozitif = Jev daha iyi**.
Harman = `live.report`un donmuş ağırlıklı havuzu (`blend_weights_faz3.yaml`); `harman_jev = shift(harman, [β_i], [f_i])`.

| # | Ne | Kitle | Ölçü | Rol |
|---|---|---|---|---|
| **D1** | `harman_jev − harman` | haberli, harmanı tam, sonuçlu maçlar | ΔLL ortalaması, maç düzeyi yüzdelik bootstrap %95 GA | **KAPI** |
| D1b | aynısı | aynı | karar turu kümeli bootstrap: turlar yerine koymalı çekilir, istatistik çekilen turların bütün maçlarının havuz ortalaması | betimsel |
| D1c | aynısı | iki tarafı da `asked` maçlar | ΔLL GA | betimsel |
| D2 | aynısı | bütün gölge maçları (haber yoksa `f = 0`, ΔLL = 0) | ΔLL GA | betimsel |
| D3 | bahis CLV: `harman_jev`, `harman`, `backtest.strategies.Placebo` | haberli maçlar | her biri için ayrı ortalama CLV ve GA, yan yana (eşleştirilmemiş; fark GA'sı yok); τ = 0,02, `wf_eval.bet_clv` | ikincil |
| D5 | D1 kırılımı: dil (`tr`/`en`/`mixed`, R195) · lig (`config/leagues.yaml`ın aktif 8 ligi) | haberli maçlar | ΔLL GA | betimsel |
| D6 | `harman_jev` ve `harman` kalibrasyonu | haberli maçlar | `market.metrics.calibration_or_none` (10 kova): eğim `b`, ECE | betimsel |
| D7 | β yolu: ilk/son/medyan `β_i`, `β_i = 0` ve `β_i = 5` sayısı | — | sayı | betimsel |
| D8 | soru başına tek değişkenli prequential ΔLL: bileşiğin 7 bileşeni + dışarıdaki 2 T2 + 9 T3 (18 id, §4) — aynı R191 kuralı ama sınır `[−5, 5]` | haberli maçlar | ΔLL GA, **çoklu test düzeltmesi YOK, "betimsel, kapı değil"** | betimsel |
| D9 | `lag_b_p99` (yayıncı iddiası ↔ `first_seen_at`, ≥ 2 hafta) · baz − piyasa SD'si (R194) | — | sayı | betimsel |
| D10 | kapsam plasebosu: `f_cov = 1[ev asked] − 1[dep asked]`, aynı R191 kuralı (sınır `[−5, 5]`) | haberli maçlar | ΔLL GA | betimsel |

**Bootstrap (inceleme I2):** `market.metrics.bootstrap_mean`, **tekrar 10.000, tohum 20261005, düzey 0,95**; girdi sırası
`(decided_at, match_id)` artan; her karşılaştırma ve her kırılım hücresi fonksiyonu TEK çağrıyla, aynı tohumla kullanır.
D1b aynı tohumla kendi tur çekilişini yapar.

**Basılan sayımlar (`counts_printed`):** pencere başlangıcı ve etiket sha'sı · ön kayıt dosyasının sha256'sı · kapanış
türü (`n_stop` / `date` / `vendor` / `user`) · kapanış turu, değerlendirme tarihi · kapanıştaki haberli karar sayısı
(R193 sayımı) ve D1'in `n`i yan yana · `N_stop` · gölge maçı · haberli maç · harmanı eksik (`incomplete`) · fiyatı
reddedilen (`rejected_price`, `live.report` gibi ayrı) · `fallback` ligler · sonuçsuz · `no_decision` (pencere içi
fikstürden gölge satırı olmayan) · taraf son durum dağılımı (`asked`, `no_news`, `stale`, `deferred`, `error`,
`budget`, `outage`, `model_drift`) · `imputed` taraf · `asked_after_kickoff` · soru başına `missing` · dil kuralının
dışarıda bıraktığı karar · mühürden sonra açılan ligin kapı dışı kararı (`league_excluded`) · `item_set_hash` uyuşmazlığı · dondurulmuş küme dışı satır · EN girdiyse kalibrasyon raporu
commit'i ve sha'sı · §5 kollarının değişiklik commit'leri (dosya, sha, tarih).

## 2. Kapı

Değerlendirmede (R193) D1 GA'sı `[low, high]`:

- **GEÇTİ:** `low > 0` ve kapanış türü `user` değil.
- **KALDI:** `high < 0`; ya da kapanış `n_stop` ve `low ≤ 0`.
- **GÜÇ YETERSİZ:** öteki her durum — kapanış `date`/`vendor` ve GA sıfırı içeriyor; kapanış `user` ve `high ≥ 0`;
  D1 boş.

KALDI ve GÜÇ YETERSİZ'de Jev katmanı Faz 5 istiflemesine özellik olarak girmez; ham cevaplar toplanmaya devam eder.
D3 her durumda raporlanır, kapıyı belirlemez (R170). Üç sonuç ayrık ve kapsayıcıdır.

## 3. İstatistik notları

- **Seyrelme:** erken `β_i ≈ 0` maçların ΔLL'i ≈ 0'dır; ortalama ve standart hata aynı oranla küçülür, GA'nın sıfıra göre
  konumu değişmez (inceleme simülasyonu: t 0,803 sabit, yüzdelik alt sınır / SE −1,13 → −1,18). AMA `N_stop` bilgi
  taşımayan maçları da sayar: gerçek güç adlı %80'in altındadır (§6/7).
- **Bağımlılık:** aynı turdaki maçlar aynı `β_i`yi paylaşır; D1b etkiyi gösterir (kapı D1, R170 ve güç hesabının temeli).

## 4. Ön kayıt dosyası — `config/faz4_preregistration.yaml`

Ana spec §8 aynen: raporun bastığı HER şey birebir. Yükleyici bilinmeyen/eksik alanı reddeder. Alanlar:

- `phase: faz4`, `leg: live`, `seal_tag: faz4-onkayit`
- `window: {tier2_prompt_version: <sha>, start: first_asked_after_seal_commit}` · `stop: {n_stop: 1800, date_limit:
  2027-06-30T23:59:59Z, tie: n_stop, evaluation_lag_days: 21}`
- `feature: {weakness: [6 id], strength: [t2_donus], excluded: [t2_hoca_degisim, t2_yeni_transfer], divisor: 7,
  sign: away_minus_home, level_score: choice, c_min: 0.0, asked_after_kickoff: missing}`
- `beta: {lambda: 1.0, lower: 0.0, upper: 5.0, solver: projected_bisection, tol: 1.0e-10, empty: 0.0, train: {gap_hours:
  3, result_date: strictly_before_decision_utc_date, requires: [haberli, harman_complete, settled, in_window,
  gate_language]}}`
- `comparisons: [D1, D1b, D1c, D2, D3, D5, D6, D7, D8, D9, D10]`, `gate: D1` · `descriptive_bounds: {lower: -5.0,
  upper: 5.0}` (D8, D10) · `d8_questions: [18 id]` · `d5_leagues: [8 lig]`
- `bootstrap: {resamples: 10000, seed: 20261005, level: 0.95, order: [decided_at, match_id]}` · `tau: 0.02` ·
  `calibration_bins: 10`
- `languages: {sealed: [tr], entry: {min_n: 100, min_accuracy: 0.85, jev_model: jev-1.13.0}}`
- `level_scores: {none: 0, low: 1/3, medium: 2/3, high: 1}` (R190) · `methods:` LL `market.metrics.per_match_log_loss`,
  bootstrap `market.metrics.bootstrap_mean`, D1b `round_cluster`, D3 `backtest.strategies.Placebo`, D6
  `market.metrics.calibration_or_none`, D9 SD `ddof 1` / `4` hafta, D10 `coverage_indicator` · `closure_kinds: [n_stop,
  date, vendor, user]`
- `sha256:` `model_faz3.yaml`, `blend_weights_faz3.yaml`, `history_lock.yaml` (kilit), `history_leagues.yaml`
  (katalog), `history_aliases.yaml`, `faz4_live.yaml`, `faz4_ops.yaml`, `jev_questions.yaml`, `languages.yaml`,
  `leagues.yaml`
- `counts_printed: [...]` (§1) · `verdicts: {passed, failed, underpowered}` (§2 metinleri)

**Mühür denetimi (bu planda, TDD; `gate4.preregistration` + `gate4.seal`):** yükleyici şemayı birebir ister (yinelenen
YAML anahtarı dâhil reddedilir). İki denetim, ikisi de git'e dayanmaz (CI derinliği 1, etiketsiz):
- **Kalıcı (`seal_violations`, her push'ta pytest):** donmuş dosyaların sha256'sı bugünkü baytlarla tutar;
  `window.tier2_prompt_version = sha256(bytes(jev_questions.yaml) + bytes(faz4_live.yaml))`; `weakness ∪ strength ∪
  excluded` `tier2`yi TAM ve ayrık böler; `d8_questions` = bileşik 7 + `excluded` + bütün `tier3`; `level_scores` =
  `derive.LEVEL_SCORES`; giriş eşikleri = `calibration.production_ready` varsayılanları; `entry.jev_model` =
  `faz4_live.yaml`ınki; `d5_leagues` bilinen lig; mühürlü diller hâlâ üretimde.
- **Mühür anı (`seal_time_violations`, mühür commit'inden hemen önce boş dönmeli; rapor da basar):** kollar dâhil
  dokuz+bir dosya birebir; `d5_leagues` = aktif ligler; `languages.sealed` = üretim dilleri.

Renderer ↔ ön kayıt birebirlik testi değerlendirme kodu yazılınca eklenir ve renderer'ın bastığı alanları `comparisons` +
`counts_printed` ile eşitler (16c dersi).

## 5. Pencere boyunca kollar (inceleme C2)

| Kol | Pencerede değişirse |
|---|---|
| `jev_questions.yaml`, `faz4_live.yaml` (= `tier2_prompt_version`) | yeni kümenin satırları kapı verisi DEĞİL; satıcı zorunluluğu (`jev_model` emekliliği, dış duyuruyla kanıtlı) → kapanış `vendor` (tarih sınırı gibi); öteki her sebep → kapanış `user` (GEÇTİ veremez) |
| `languages.yaml` | yalnız R195 yolu; başka değişiklik → `user` |
| `model_faz3.yaml`, `blend_weights_faz3.yaml`, `history_lock.yaml`, `history_leagues.yaml` | değişmez (R161); değişirse değerlendirme mühürlü baytlarla (git'ten) yapılır |
| `faz4_ops.yaml`, kademe 1 tur tavanı, $25 tavan, `history_aliases.yaml` | kapasite/veri hijyeni kolları — sonuç okumadan, sayımla gerekçeli değişebilir; her değişiklik commit'i raporda listelenir; pencereyi kapatamaz |
| `leagues.yaml` | lig açılabilir/kapanabilir; D1/D5 kitlesi mühürdeki `d5_leagues`la sınırlı — sonradan açılan ligin kararı kapı dışıdır (`league_excluded`); mühürlü bir lig kapanırsa kalan kararları kapıda kalır |

**Donmuş dosya değişince kapı kırmızıdır** (kalıcı mühür denetimi): bu bilinçlidir — değişikliği yapan commit aynı anda
kapanış kaydını (`vendor`/`user`, tarih, sebep; biçimi DEFERRED 23a) yazmadan `main` yeşile dönmez.

**Tavan** ya da Jev kesintisi: o tarafın durumu `budget`/`outage` → bütün `f_k` eksik; sayılır. **Sonuç yok**:
sonuçsuz, D1'e ve eğitime girmez. **Harman eksik**: `incomplete`.

## 6. Kapının ÖLÇMEYECEKLERİ (ana spec §11 + Plan 2 §4'e ek)

1. Bileşiğin ağırlıkları eşit, işaretleri soru metninden; gerçek etki yapısı test edilmez (D8 betimsel).
2. β tek ve ligler arası ortak; lig farkı modellenmez (D5 betimsel).
3. `N_stop` sabit; Jev etkisinin SD'si ölçülmeden seçildi.
4. D8/D10'da çoklu test düzeltmesi yok; oradaki "anlamlı" bulgu keşiftir.
5. EN girişi kitleyi değiştirir; D1 havuzlanmıştır.
6. Yeniden oynatma football-data'nın son hâlini kullanır; sonradan düzeltilen sonuçlar ölçülmez.
7. Sıfır β'lı erken maçlar `N_stop`a sayılır: gerçek güç adlı %80'in altında.
8. Mod seviyesi Jev'in olasılık dağılımını atar.
9. Pencere tek sezonun (2026/27) içinde.

## 7. Plan 3'ün iki yarısı

1. **Mühür (bu deltadan hemen sonra, 2026-10-09 12:35 UTC'den önce):** spec + ön kayıt dosyası + yükleyici ve mühür
   testi (TDD, bağımsız inceleme, mutasyon, tam kapı) → commit + `faz4-onkayit` etiketi + push. Değerlendirme kodu yok.
2. **Değerlendirme kodu (mühürden sonra, `writing-plans` ile):** `gate4` paketi — bileşik özellik (R189–R190, R199),
   prequential fit (R191), yeniden oynatma okuyucusu (R192; 17a okuyucu bekçisi, import kuralları), `faz4 gate` komutu
   (R197; tarih/N koşulu adlı exit), renderer + ön kayıt ↔ renderer birebirliği. `slice-status`a pencere başlangıcı ve
   `model_faz3` sha süzgeci, karar = tekil `match_id`, hedef `N_stop` (bugün sayım `asked` işaretlerinden yapılıyor ama
   pencere/sha süzgeci yok ve hedef 900 — `slice.py`). Hiçbir adım pencere verisinde Jev'li ΔLL ya da β basmaz (testler
   sentetik veriyle). `harman_jev` canlı yazımı yok (R198).

## 8. Zamanlanan ölçümler (HANDOFF §0.U.4 B ile)

`lag_b_p99` ≥ 2026-10-07 (D9) · ilk kademe 2 turu 2026-10-09 · baz − piyasa SD'si pencerenin ilk dört haftasından (D9).

## 9. Yerine geçilen hükümler (açıkça)

Ana spec §7.2 → bu §2 · §7.3 yalnız-canlı yolu → R188/R193 · §7'nin "T10'da gerçek `N` yazılır" cümlesi → R194 · §8
sha listesinden `model_faz4.yaml` düşer (budama yok) · §7.1 D4 düşer, D5'ten `availability_basis` düşer (arşiv yok) ·
§6 "β katlarda sırt cezalı" → R191 · R171 tarihi 2027-03-31 → 2027-06-30 (§7.3'ün kapalı-arşiv tarihi) · Plan 2 R173
"`harman_jev` β donunca yazılır" → R198 · Plan 2 M-6 "EN sonra ise kullanıcı kararı" → R195 · Plan 2 R181 hedef 900 →
`N_stop`.

## 10. İnceleme izi

Bağımsız spec incelemesi (2026-10-05, general-purpose, kopyada simülasyon): **C1** beklenen değer seviyesi haber
varlığını ölçüyordu → R190 mod + D1c + D10 · **C2** kullanıcı kaynaklı kesinti, canlı β yazımı, isteğe bağlı `N_stop`
commit'i → §5, R198, R194 · **I1** `N_stop` kuralı fiilen boş → sabit 1.800 · **I2** bootstrap sıraya duyarlı → `order`,
tek çağrı · **I3** karışık dilli batarya → R195 yeniden kurma + `mixed` · **I4** pencere başlangıcı → etiket + ilk `asked_at`
· **I5** sayımlar → §1 listesi · **I6** karşılaştırma tanımları, çözücü toleransı → §1, R191 · **I7** kanonik formül, alan
adı → R190, §4 · **I8** `features` → `live.store` import yasağı → R197 `gate4` · **I9** başlama sonrası cevap → R199 ·
**I10** sha listesi → §4 · M1 `slice-status` gerçeği → §7/2 · M2 → §9 · M3 eşitlik ve boş D1 → R193, §2 · M4
değerlendirme çapası → `decided_at` + 21 gün · M5 güç → §3, §6/7 · M6 → R192 · M7/M8 → §4. Doğrulananlar: `shift`
işareti, R190 cebiri, bileşik işaretleri soru metinleriyle, `features_of`/`IMPUTED`, maç başı tek karar, `side_status`
biçimi, `prompt_version` hesabı (`9b294a61…`), sonuç kaynağı, `bootstrap_mean` imzası, kalibrasyon eşikleri, 3 sa =
`RESULT_LAG`, amaç kesin içbükey, §2 ayrık/kapsayıcı.

Bağımsız kod incelemesi + mutasyon (2026-10-05, 44 mutasyon, 17 hayatta): kollar mühür anında denetlenmiyordu →
`seal_time_violations`; `leagues.yaml` kol değildi → kol + `league_excluded`; donmuş dosya değişiminin yolu → §5 kapanış
kaydı; yinelenen YAML anahtarı, dil tekilliği, `LEVEL_SCORES`/eşik çapraz denetimi, ham YAML okuma → düzeltildi; yöntem
adları ve kapanış türleri YAML'a (`methods`, `closure_kinds`); hayatta kalan 17 mutasyonun hepsine öldüren test.

İkinci tur (2026-10-05, 63 mutasyon): kritik yok; `min_n` eşiği, `train.requires` tamlığı, mühür anı D5 üst kümesi /
dil üst kümesi / bozuk dil dosyası testsizdi → testler; mühür anı denetimi donmuş dosyaları da sayar; bozuk `leagues.yaml`
adlı ihlal; büyük harf / 65 haneli sha reddi; kapanış kaydı yolu DEFERRED 23a. Prosedür: mühür anı denetimi etiketlenen
commit'in KENDİSİNDE, `origin/main` birleştirmesinden sonra boş döner (commit mesajında kayıtlı). Kalan 6 mutant eşdeğer/önemsiz.
