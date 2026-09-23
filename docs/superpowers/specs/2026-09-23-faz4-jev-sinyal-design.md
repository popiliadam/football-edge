# Faz 4 — Jev sinyal katmanı, özellik deposu, budama (tasarım)

**Tarih:** 2026-09-23 · **Durum:** kullanıcı onaylı tasarım (brainstorming, 2026-09-23) · **Sonraki adım:**
`superpowers:writing-plans`
**Girdi:** `docs/HANDOFF.md` §0.2–§0.4 · `docs/phases/03-baz-model/HANDOFF.md` §3, §6 · `docs/DEFERRED.md` §16 ·
ana tasarım `2026-09-19-football-edge-design.md` §4, §5, §6.2, §9 · yol haritası
`2026-09-21-yol-haritasi-v2-paralel-izler.md` §2–§5 · Faz 3 tasarımı §5, §7, §8, §10.

---

## 0. Karar özeti

| No | Karar | Gerekçe | Yanlışsa bedeli |
|---|---|---|---|
| R157 | **Hibrit değerlendirme:** önce arşiv spike'ı (T0c); arşiv uygunsa seçim arşivde, kapı arşiv holdout'u + canlı mühürlü pencerede; uygun değilse yalnız canlı | Dil sinyalinin tarihi yok (§0.2/1); yalnız canlı ~24+ hafta | Spike 1–2 gün boşa |
| R158 | Diller **TR + EN**; ön etiket **Opus 5.5 (high effort)**, onay kullanıcıda, ölçüm insan etiketine karşı | EN birçok ligin uluslararası haberini kapsar; 2×100 etiket taşınabilir yük | Yerel dil tezi (ES/IT/DE/FR/NL) Faz 4'te test edilmez |
| R159 | `TYPESAFE_API_KEY` Faz 4 başında; **$25/ay sert tavan**; arşiv geri doldurması ayrı tek seferlik onay | Tahmini canlı maliyet $0,15–$5/ay (ölçülmedi) | Tavan erken dolarsa canlı Jev satırı düşer (sayılır, sessiz değil) |
| R160 | Gölge CLV raporu (16o) + 16a–16d + 16f **Faz 4 dalga 0** | Canlı baz serisi 2026-09-26'dan birikir; açılış öncesi düzeltmeler plansız kalmasın | — |
| R161 | **Baz donmuş** (`model_faz3.yaml`); ızgara genişletmesi (16n) Faz 5'e | Marjinal ölçüm tek değişken ister; gölge serisi `model_config_sha256` ile bölünür | Baz yerel optimumda kalır; Faz 5'te düzelir |
| R162 | Holdout **iki ayak, ikisi de ön kayıtlı:** 2025/26'nın 2. açılışı (arşiv uygunsa) + 2026/27 canlı mühürlü pencere | Spec §6.2: faz kapılarında en çok üç açılış; Faz 3 birini kullandı | Faz 5'e tek açılış kalır |
| R163 | İz B Faz 4'le paralel başlamaz | Dalga 0 dört implementer sınırını doldurur; Netlify/alan adı yok | İz B gecikir |
| R164 | **İki kademeli Jev:** kademe 1 haber başı T1 kapı soruları; kademe 2 karar anında maç başı T2–T4 bataryası | Spec §5.2 T1 "filtre, özellik değil"; maliyet haber × 3–4 + maç × ~30 | İki istem sürümü, iki tablo |
| R165 | **Canlı saat erken başlar:** arşiv ayağı açıksa canlı pencere T6'nın ilk canlı yazımında başlar; karşılaştırma mühürlü | Uzun direk canlı pencere; seçim arşivde olduğu için canlı veri seçime girmez | Arşiv kapalıysa geçerli değil (§7.3) |
| R166 | Tek zaman alanı **`available_at`** + `availability_basis` | Canlı ve arşiv aynı özellik kodundan geçer (spec §6.3) | Güvenlik payı kuyruğu (§11) |
| R167 | **Bilgi sızıntısı kanaryası** (boş + karıştırılmış haber) arşiv ayağının geçerlilik koşulu | Dil modeli arşiv maçının sonucunu eğitiminden bilebilir | Kanarya istatistikseldir, kanıt değil |
| R168 | Jev özellikleri **harman çıkışında logit kaydırma** `p_jev ∝ p_harman · exp(β·f)`; `f = 0 ⇒ p_jev = p_harman` | Piyasa zaten harmanda; eşleştirme maç başına kesin; gölge serisi bölünmez | Harman içindeki ağırlıkla etkileşim modellenmez |
| R169 | Budama: genişleyen katlarda marjinal ΔLL, **BH q = 0,10**, **≤ 15** özellik, **\|ρ\| > 0,8** çiftten biri atılır | Spec §5.2 sayısal disiplin | Eşikler keyfî başlangıç; ön kayda girer |
| R170 | **Kapı ölçüsü D1 (eşleştirilmiş ΔLL)**, CLV (D3) ikincil — spec §9'un "marjinal CLV" ifadesinden bilinçli sapma | Faz 3 holdout'u sezonda 54 bahis üretti; CLV GA'sı her gerçekçi etkiyi içerir | Kâr ölçülmez (zaten ölçülmüyordu) |
| R172 | **Bizim saatimiz `first_seen_at`:** `news_items` her haberin ilk görüldüğü anı veritabanı saatiyle tutar; canlı `available_at = max(first_seen_at, published_at_claimed)`; `sync-news` `collect-news` iş akışında toplamanın hemen ardından koşar | `source_observations.observed_at` ajansspor için YAYINCININ iddiasıdır, toplama saati değil (`collectors/news.py` `news_observation`, R23) — plan yazımında bulundu (2026-09-23) | 2026-09-04'ten beri biriken haberler ilk senkron anından itibaren "mevcut" sayılır (tutucu) |
| R171 | Canlı pencerede **uzatma yok:** ≥ 1.800 haberli maç **ya da** 2027-03-31, hangisi önce; ulaşılmazsa "güç yetersiz" | İsteğe bağlı durdurma canlı p-hacking'dir | Güç yetersiz sonuç |

---

## 1. Amaç, kapsam, kapsam dışı

**Amaç:** Jev'li bir sinyal katmanının donmuş Faz 3 bazına (`harman`, `config/model_faz3.yaml`) **marjinal**
katkısını önceden kaydedilmiş iki ayakta ölçmek. "Jev sinyali ödemiyor" da geçerli bir faz sonucudur.

**Kapsam:**
- Jev istemcisi (tipli batarya, kredi sayacı, tavan), iki kademeli soru hattı, özellik deposu.
- TR + EN dil kalibrasyonu; bir EN canlı haber kaynağı.
- §5.3 boru hattı rollerinden kademe 1'e oturan üçü: **varlık eşleme** (haber → maç/taraf), **haber kümeleme**,
  **kaynak çelişkisi** (güvenilirlik sorusu).
- Budama, eşdoğrusallık, ön kayıt, holdout 2. açılışı, canlı mühürlü pencere.
- Dalga 0: gölge CLV raporu ve DEFERRED §16'nın açılış öncesi satırları.

**Kapsam dışı (YAGNI):** baz modeli yeniden seçmek ve ızgara (Faz 5, R161) · istifleme, staking (Faz 5) · İz B ·
TR/EN dışındaki diller · Sonnet metinleri · kendini onaran ayrıştırıcı, yayın öncesi doğrulama, kayıp otopsisi
(sonraki fazlar) · Ü/A ve ikincil marketlerde Jev (yalnız 1X2).

---

## 2. Dalgalar

Aynı anda en çok 4 implementer, ayrık dosya kümeleri, ayrı worktree (`git worktree add`). Kademeler yol haritası §3.

| Dalga | Görev | Kademe | Anahtar |
|---|---|---|---|
| **0** | **T0a** gölge CLV raporu (16o): harman + bahis + mühürlü kapanış, haftalık; 16e ölçümü (bayatlık yarıçapı kararı ölçümle); 16f (`since = now − LOOKBACK − 1 gün`) | K1 | — |
| 0 | **T0b** açılış öncesi düzeltmeler: 16a (`--out` yoklaması, `fit_weights` `ValueError` → `fallback`), 16b (kanonik yollar), 16c (renderer eşleştirilmiş ΔLL + `incomplete`/`fallback`), 16d (faz parametresi), 16i (`devig` toplam < 1 koruması + sayım), 16l (test boşlukları), 16p (111 maçın anahtarsız sınıflaması) | K1 | — |
| 0 | **T0c** arşiv ve kaynak spike'ı (§3) — kod tutulmaz, karar raporu | spike | — |
| 0 | **T0d** Jev istemcisi: `JevClient` protokolüne batarya çağrısı, `jev_spend` sayacı, tavan, sahte istemciyle TDD | K1 | — |
| **1** | **T1** özellik deposu: migration `0012` (§4), saf özellik türetimi, AST kuralı | K1 | — |
| 1 | **T2** EN canlı haber kaynağı (T0c'nin seçtiği), `sources.yaml` + robots + toplayıcı | K2 | — |
| 1 | **T3** dil kalibrasyonu: 100 TR + 100 EN haber; Opus 5.5 high ön etiket; kullanıcı onayı; Jev ölçümü; `production_ready` eşikleri ölçümden sonra gerekçeyle | K1 | gerekir |
| 1 | **T4** kademe 1 istemi ve koşucusu (T1 soruları, kümeleme, eşleme) | K2 | gerekir |
| **2** | **T5** kademe 2 bataryası (T2–T4, ~30 soru) | K2 | gerekir |
| 2 | **T6** canlı gölgeye `harman_jev` stratejisi (karşılaştırma mühürlü); 16g (DC memo anahtarı — `model/strategies.py`nin ilk değişikliği) | K1 | gerekir |
| 2 | **T7** arşiv geri doldurması — yalnız T0c olumluysa ve kullanıcının ölçülmüş tahminle verdiği tek seferlik onayla | K2 | gerekir |
| **3** | **T8** budama · **T9** eşdoğrusallık · `config/model_faz4.yaml` donar | K1 | — |
| 3 | **T10** ön kayıt (`config/faz4_preregistration.yaml`) + prova + kırmızı takım (fable) | K1 | — |
| 3 | **T11** holdout 2. açılışı (kullanıcının açık "evet"i) · canlı pencere ön kaydı mühürlenir | K1 | — |

**Kilometre taşları:** (1) *uygulama bitti* — T0–T11 `main`de, holdout ayağı açıldı, canlı pencere sayıyor;
(2) *faz kapısı kararı* — canlı pencere kapanınca (§7.3). Aradaki süre Faz 5'in kararıdır.

**Kullanıcı durakları:** T0c raporu (arşiv açık/kapalı) · anahtarın `.env`e konması · T3 etiket onayı · T7 bütçe
onayı · ücretli harcamayı açan commit (kullanıcı koşar) · T11 açılış "evet"i.

---

## 3. T0c — arşiv ve kaynak spike'ı

Çıktı: `docs/reports/<tarih>-faz4-arsiv-spike.md`. Dört ölçüm, her biri komutuyla:

1. **Lisans ve robots:** GDELT ve CC-NEWS (ve spike'ın bulduğu başka açık arşiv). Kaynak politikası spec §3.2 ve
   §3.2.1 aynen: ham içerik yeniden yayınlanmaz, yalnız sayısal özellik türetilir. TR + EN kapsamı, lig × sezon
   dağılımı (E bölgesi 2019/20–2024/25 ve holdout 2025/26).
2. **Yayın zamanının güvenilirliği:** `source_observations.observed_at` yayıncının iddiasıdır (R172), bizim
   saatimiz değil. Bu yüzden iki ölçüm: (a) T0c'de arşiv damgası ↔ yayıncı iddiası uyumu (aynı haber, URL /
   başlık eşleşmesi; medyan, p95, p99, eşleşmeyen pay) — iki iddianın tutarlılığı; (b) Task 9 birleştikten sonra
   canlıda yayıncı iddiası ↔ `first_seen_at` farkı (bizim saatimiz; toplama aralığı 2 saat olduğu için yukarı
   yanlı = tutucu), en az 2 hafta birikim. Güvenlik payı = max((a)'nın p99'u, (b)'nin p99'u), bir üst tam saate
   yuvarlanır; Plan 2'de ölçülür ve ön kayda girer.
3. **Haber gövdesi:** `ajansspor` makale sayfaları robots'a göre okunabilir mi. Okunamıyorsa sinyal başlık
   düzeyinde kalır (§11).
4. **EN canlı kaynak adayları:** robots, ToS, RSS/sitemap, lig kapsamı. Bir tanesi seçilir (T2).

**Arşiv ayağı açık sayılır ancak:** lisans/robots temiz · TR ya da EN'de E bölgesi ve holdout için lig-sezon
başına ölçülmüş yeterli kapsam (rapor sayıyı basar; eşik: haberli maç payı holdout'ta ≥ %30) · eşleşen haberde
arşiv damgası p99 ≤ 24 saat. Biri tutmazsa arşiv ayağı kapalıdır ve §7.3'ün yalnız-canlı yolu uygulanır.

---

## 4. Veri modeli (migration `0012`)

Bütün tablolar append-only: `0009`daki gibi UPDATE/DELETE/TRUNCATE tetikleyicileri. Doğrulama yalnız okuma
sorgusuyla; append-only tablolara deneme satırı yazılmaz.

| Tablo | Bir satır | Tekil anahtar |
|---|---|---|
| `news_items` | kaynak, `lang`, başlık, gövde (nullable), URL, `published_at_claimed` (nullable), `first_seen_at`, `available_at`, `availability_basis` ∈ {`observed`, `archive_claimed`}, `content_hash` | `(source_id, content_hash)` |
| `jev_item_answers` | kademe 1: haber × T1 sorusu; `match_id` (nullable), taraf, küme kimliği, olasılıklar, `confidence`, `prompt_version`, `jev_model`, `asked_at`, `cost_usd` | `(item_id, prompt_version, question_id)` |
| `jev_match_answers` | kademe 2: maç × `decided_at` × soru; `item_set_hash`, olasılıklar, `confidence`, `prompt_version`, `jev_model`, `asked_at`, `cost_usd`; kanarya satırları `variant` ∈ {`real`, `blank`, `shuffled`} | `(match_id, decided_at, prompt_version, question_id, variant)` |
| `jev_spend` | her çağrı: zaman, maliyet, çağrı türü | `id` |
| `model_predictions` (var) | `harman_jev` yeni bir `strategy`, kendi `model_config_sha256`ı (`model_faz4.yaml`) | mevcut |

- **Canlı haber:** `available_at = max(first_seen_at, published_at_claimed)`; `first_seen_at` veritabanı saatidir
  (R172). **Arşiv haberi:** `available_at = published_at_claimed + güvenlik
  payı` (§3/2). `source_observations` değişmez; `news_items` canlı toplayıcılardan da beslenir (tek okuma yolu).
- Soru metinleri ve `question_id`ler `config/jev_questions.yaml`da, sürümlü; `prompt_version` dosyanın sha256'sı.

---

## 5. Sızıntıya karşı önlemler

1. **Karar anı filtresi tek yerde:** kademe 2'nin haber kümesi `available_at < decided_at` ve (yalnız canlıda)
   kademe 1 `asked_at < decided_at`. `item_set_hash` kümeyi yeniden üretilebilir kılar.
2. **Bilgi sızıntısı kanaryası (R167):** arşivde her kademe 2 turunun rastgele (tohumlu) %10'unda aynı batarya
   `blank` (haber yok) ve `shuffled` (başka ligdeki başka maçın haberi, takım adları korunur) varyantlarıyla da
   sorulur. D4: kanarya özellikleriyle kurulan D1'in GA'sı sıfırı içermeli. İçermezse **arşiv ayağı geçersiz**,
   budama canlı seçim dilimine düşer (§7.3).
3. **Canlı ↔ arşiv eşitlik testi:** 2026-09-04'ten beri canlı gözlenen TR haberleri için özellikler canlı yoldan
   ve arşiv yolundan (arşivde bulunanlar) kurulur; fark ve eşleşmeyen pay raporlanır (Faz 3 E3'ün karşılığı).
4. **AST kuralı:** özellik modülü (`features/` ya da plan yazımında belirlenen yol) sonuç, kapanış mühürü ve
   holdout modüllerini import edemez; `HoldoutKey` kuralı (Faz 3 §8.2) aynen.
5. **Mühürlü karşılaştırma:** `harman_jev − harman` farkını hesaplayan kod yalnız ön kayıtlı kapanış komutunda
   bulunur; haftalık gölge raporu (T0a) yalnız baz serisini basar — bir test raporun `harman_jev`i okumadığını
   zorlar.

---

## 6. Özellikler, modele giriş, budama

**Batarya (spec §5.2):** T1 kapı (`haber_bu_maca_ait`, `haber_guvenilirligi`, `kaynak_celiskisi` + küme) kademe
1'de, **filtre**dir. T2 çekirdek ve T3 aday kademe 2'de, **özellik**tir. T4 spekülatif yalnız kaydedilir.
Toplam ~35. Her yeni soru "cevabı tabloda var mı?" testinden geçer. `confidence < c_min` cevap sıfırlanır
(`c_min` yapılandırmada; T3 ölçümünden sonra gerekçeyle).

**Özellik:** taraf başına cevaplardan `f_k = ev_k − dep_k`; haber yoksa ya da cevap eksikse `f_k = 0` ve
`incomplete` sayılır.

**Modele giriş (R168):** `logit` uzayında ev `+β·f`, deplasman `−β·f`, beraberlik 0; normalize edilir.
`β` genişleyen walk-forward eğitim katlarında sırt cezalı en çok olabilirlikle fit edilir (ceza tek, katlar içinde
seçilir). Harman ve ağırlıkları dokunulmaz.

**Budama (T8/T9) yalnız seçim verisinde:** arşiv açıksa E bölgesinin haberli maçları; kapalıysa canlı seçim dilimi.
Her aday tek başına harmana eklenince katlar üzerinden marjinal ΔLL ve p-değeri (eşleştirilmiş bootstrap);
BH q = 0,10; geçenlerden ΔLL'ye göre en çok 15; |ρ| > 0,8 çiftlerde düşük ΔLL'li atılır; kalanlarla ortak fit.
Çıktı `config/model_faz4.yaml`: özellik listesi, `β`lar, `c_min`, `prompt_version`, `model_faz3.yaml` sha256.

---

## 7. Ölçüm ve iki ayak

### 7.1 Karşılaştırmalar

| # | Ne | Ölçü |
|---|---|---|
| **D1** | `harman_jev` − `harman`, haberli maçlar | eşleştirilmiş ΔLL, bootstrap GA — **birincil (kapı)** |
| D2 | aynısı, bütün maçlar | ΔLL |
| D3 | Jev'li bahisler − baz bahisler, Placebo yan yana | ortalama CLV, GA — ikincil |
| D4 | kanarya (`blank`, `shuffled`) ile D1 | GA sıfırı içermeli (arşiv ayağının geçerlilik koşulu) |
| D5 | D1 TR / EN / `availability_basis` kırılımı | betimsel |
| D6 | `harman_jev` kalibrasyonu | eğim `b`, ECE |

### 7.2 Kapı (R170)

**GEÇTİ:** açık her ayakta D1 GA alt sınırı > 0 **ve** arşiv ayağında D4 temiz. **KALDI:** herhangi bir açık
ayakta D1 GA alt sınırı ≤ 0. **GÜÇ YETERSİZ:** canlı pencere 1.800 haberli maça ulaşmadan tarih sınırına geldi ve
GA sıfırı içeriyor. KALDI ve GÜÇ YETERSİZ'de Jev katmanı Faz 5 istiflemesine özellik olarak girmez; ham cevaplar
toplanmaya devam eder (T4 gibi). D3 her durumda raporlanır, kapıyı belirlemez.

### 7.3 Ayaklar

- **Arşiv ayağı (açıksa):** 2025/26 holdout'unun 2. açılışı; `final_eval` `phase = faz4` ile (16d); satırlar
  anahtar görmeyen işçilere seçilmiş olarak verilir (Faz 3 §8.2). Prova 2024/25 üzerinde.
- **Canlı ayak, arşiv açıksa (R165):** pencere T6'nın ilk canlı `harman_jev` yazımında başlar; durma ≥ 1.800
  haberli maç ya da 2027-03-31 (R171). Ön kayıt T10'da, pencere hakkında hiçbir sonuç hesaplanmadan mühürlenir.
- **Canlı ayak, arşiv kapalıysa:** önce **seçim dilimi** (T6'dan itibaren ≥ 900 haberli maç), budama orada; sonra
  ön kayıt mühürlenir ve **kapı dilimi** ertesi gün başlar: ≥ 1.800 haberli maç ya da 2027-06-30. Takvim uzar;
  bedel budur.

`≥ 1.800` güç tahmini: E bölgesi GA'sından maç başı ΔLL SD ≈ 0,027; ΔLL 0,002 için %80 güç. Tahmindir; T0a'nın
canlı serisiyle T10'da yeniden hesaplanır ve ön kayda gerçek sayı yazılır (pencere başlamadan önce).

---

## 8. Ön kayıt ve açılış

`config/faz4_preregistration.yaml` **raporun bastığı her şeyi birebir** listeler (16c dersi): D1–D6; bootstrap
tohumu ve tekrar sayısı; `model_faz4.yaml`, `model_faz3.yaml`, kilit ve katalog sha256; güvenlik payı; kanarya
oranı ve tohumu; canlı pencere başlangıcı ve durma kuralı; basılacak `incomplete` / `fallback` / `no_decision`
sayıları; geçti/kaldı/güç yetersiz ölçütleri. Renderer bu listeden fazlasını ya da eksiğini basarsa test kırmızı.

Açılış Faz 3'ün kanonik yolunu izler: temiz ağaç, commit'li ön kayıt, özet eşleşmeleri, prova yeşil, kullanıcının
açık "evet"i, `holdout_access_log` `phase = faz4` tekil. 16a/16b açılıştan önce kapanmış olmalıdır.

---

## 9. Bütçe ve hata yolları

- **Tavan:** her çağrıdan önce `jev_spend`de ayın toplamı + tahmini maliyet ≤ $25; değilse çağrı yapılmaz, adlı
  çıkış kodu, alarm (Odds API bütçe deseni). İlk 100 gerçek çağrının maliyeti ölçüm belgesine komutuyla.
- **Ücretli harcamayı açan commit** kullanıcı tarafından koşulur (asistan ortamı bunu reddediyor); plan tek satırlık
  komutu verir.
- **Jev hatası:** zaman aşımı/5xx → sınırlı yeniden deneme → satır yazılmaz, log `jev: soru N · başarısız F`;
  eksik cevap `f = 0` + `incomplete`.
- **Jev model sürümü** her satırda; pencere içinde değişirse rapor dilimleri ayrı basar.
- **Dil kapısı:** `production_enabled: false` dilin haberi kademe 2'ye girmez (`dil-kalibrasyonu` adımı mevcut).
- **Anahtar yoksa** Jev gerektiren komutlar adlı hatayla çıkar; kapı Jev çağırmaz (Ruling R4).

---

## 10. Kapıya eklenenler

Her biri için "nasıl kırmızı verir" testi planda yazılır ve dalga sonunda `/loop-kit:judge-selftest` ile kanıtlanır:
`available_at` filtresi (mutasyon: `<` → `<=` kırmızı) · özellik modülü AST kuralı · haftalık raporun `harman_jev`
okumaması · harcama tavanı · `0012` append-only tetikleyicileri (DB bağlıyken) · ön kayıt ↔ renderer birebirliği ·
`leakage` etiketli yeni testler (`EXPECTED_MIN_LEAKAGE` yeniden ölçülür).

---

## 11. Kapının ÖLÇMEYECEKLERİ (ön liste — faz HANDOFF'unda tamamlanır)

1. Kanarya hafıza sızıntısını istatistiksel olarak dışlar, kanıtlamaz.
2. Sinyal başlık düzeyinde olabilir (T0c/3).
3. EN kaynağının lig dağılımı dengesiz olabilir; D5 betimsel.
4. Güvenlik payı p99: kuyruktaki geç damgalar içeride.
5. TypeSafe'in model güncellemeleri; yalnız sürüm kaydı ve dilimleme.
6. Canlı pencerede `harman_jev` satırları veritabanında okunabilir; mühür kod düzeyindedir, erişim düzeyinde değil.
7. Budama eşikleri (q, 15, ρ, `c_min`) sezgisel başlangıç.
8. Logit kaydırma harman içi ağırlıkla etkileşimi modellemez.
9. Kapı kâr ölçmez; D3'ün gücü düşüktür.
10. Kalibrasyon 100 örnekle; insan etiketi tek kişiden.
11. Faz 3 §3.1–§3.3'ün geçerli maddeleri aynen sürer.
12. `first_seen_at` toplama aralığı kadar (≤ 2 saat + iş akışı süresi) geç damgalar: haber bizden erken yayındaydı;
    yön tutucudur (özellik geç görür), bedeli kaçan sinyaldir ve ölçülmez.
13. 2026-09-04 → Task 9 senkronu arasındaki haberlerin gerçek toplama anı bilinmez; ilk senkron anı kullanılır.

---

## 12. Plan yazımına bırakılanlar

Modül yolları ve dosya kümeleri (tek-yazar taraması) · migration SQL'i · `jev_questions.yaml`ın ilk ~35 sorusu
(spec §5.2 tablosundan) · T0a raporunun biçimi ve zamanlaması · kanarya örneklemesinin kodu · ölçüm belgesi
`docs/superpowers/specs/2026-*-faz4-olcumler.md` (T0c, maliyet, güç yeniden hesabı).
