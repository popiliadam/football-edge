# Faz 3 — Baz model, walk-forward, canlı bağlam, tek holdout açılışı — Devir

**Tarih:** 2026-09-23 (oturum 6) · **Durum:** TAMAMLANDI, `main`de · **Plan:**
`docs/superpowers/plans/2026-09-23-faz3-model-walkforward.md` · **Tasarım:**
`docs/superpowers/specs/2026-09-23-faz3-model-walkforward-design.md` · **Ölçümler:**
`docs/superpowers/specs/2026-09-23-faz3-olcumler.md` · **Defter (gitignored, bu makinede):**
`.superpowers/sdd/2026-09-23-faz3-model-walkforward/progress.md` (R149–R156)

## 1. Ne bitti

| Görev | Ne | Commit(ler) | İnceleme |
|---|---|---|---|
| 0 | scipy, `model/` + `live/` paketleri, kapı scipy'ı yükler; yineleme 0, saatsiz 2019/20+ satır 0 | `8bb8507` | controller; mutasyon kırmızı |
| 1 | Dixon-Coles (analitik gradyan, ρ, sırt, `day < at`) | `81f90b0` | temiz, 3/3 mutasyon |
| 2 | Fit edilebilir Elo (marj, dönüş, yeni takım, quadratic/ordered) | `8fc02cc` | temiz, 7/7 |
| 3 | Log-doğrusal havuz, `fit_weights` | `7ce55df` | temiz, 1/1 + gradyan |
| 4 | `MatchKey`, ortak bağlam son adımı, yineleme reddi, Placebo tohumu | `fcfc771` | temiz, 3/3 + 14k kanaryası |
| 5 | Dalga 1 birleştirmesi, `leakage` 269, süre ölçümü → kadans 1 (R152) | `267157d` | controller |
| 6 | DC stratejisi, walk-forward satırları, ağırlık katları, özet | `e92209e` | temiz, 7/7 |
| 7 | S'de seçim, `model_config`, `select`/`walkforward` CLI, boşluk cezası | `bb8520f` | temiz, 7/7 |
| 8 | Canlı bağlam kurucusu + E1–E2 | `bb48bcf`, `e0a7eb7` (R153) | 1 düzeltme turu, 10/10 + 1 |
| 9 | Seçim ve E raporu gerçek veride; `leakage` 287 | `a30bc9e` | controller |
| 10 | `final_eval`, ön kayıt, prova, 0010, AST kuralları | `bf315c9`, `e69376d` (R154) | 1 düzeltme turu, 11/11 + X1–X6; 1 parked |
| 11 | Gölge, E3, 0009/0011, `shadow.yml`, bekçi | `0bff050` | temiz, 4/4 |
| 12 | Modelin bilinen sonuçları W1–W4, `history.yml` adımı | `d3ca2e6`, `fcafe9f` (R155) | 1 düzeltme turu, 2/2 + O5–O7, O9, O13 |
| 13 | Ön kayıt, prova, kırmızı takım, TEK açılış, bu belge | `c129cc3`, `bf5a06d`, `9158b66` | kullanıcı "evet"i; bütün dal incelemesi: kapanabilir |

Dalga sonları: dalga 4'te 0009/0010/0011 canlıya uygulandı (`apply_migration`); ilk gölge turu, E3 ve 38 canlı
takma ad (`f346b2b`).

**Seçilen model** (`config/model_faz3.yaml`, sha256 `26b81642…`): Elo k = 10, ev avantajı 65, marj doğrusal,
dönüş 0,2, yeni takım farkı 75, beraberlik `ordered` (s = 1,0672, c = 0,5952); Dixon-Coles ξ = 0,003,
sırt = 0,003, pencere 1095 gün; kadans 1 gün; vig `power`; τ = 0,02.

**Holdout — TEK açılış:** `holdout_access_log` id 13, 2026-09-23 08:48:20 UTC, git `485134b`, amaç
`faz3:4d88d944…` (ön kayıt dosyasının sha256'sı). Faz 3'ün açılış sayısı: **1** (yeniden koşu yok). Rapor
`docs/reports/2026-09-23-faz3-holdout.md`:

| Karşılaştırma | Sonuç |
|---|---|
| C1 ΔLL harman − piyasa (ana ligler, 1X2, n = 7.613) | 0,0001 [−0,0005, 0,0007] |
| C2 LL (DC · fit Elo · iskele Elo · piyasa) | 1,0241 · 1,0254 · 1,0415 · 1,0026 |
| C3 harman bahis CLV (54 bahis) · Placebo CLV | −0,0497 [−0,0687, −0,0318] · −0,0868 [−0,0887, −0,0848] |
| C4 harman kalibrasyonu | b = 0,987, ECE = 0,0075 |
| C5 Ü/A 2.5 LL (piyasa · DC) | 0,6804 · 0,6913; DC kalibrasyonu b = 0,538 |
| C6 sonrası, tam durum (n = 1.266) ΔLL harman − piyasa | 0,0002 [−0,0013, 0,0018] |

**Yorum (R130: kenar şartı yok, sayılar kaydedilir):** Jev'siz baz model piyasayı log loss'ta YENMİYOR; harman
piyasadan ayırt edilemez (C1 aralığı 0'ı kapsar) ve bahis kuralı kapanışa karşı negatif CLV verir, yine de Placebo'dan
iyidir. Modellerin tek başına payı piyasadan ~0,022 LL geride. Bu, Faz 4'ün (dil sinyali, Jev) karşılaştıracağı baz
çizgidir. E raporu (`docs/reports/2026-09-23-faz3-walkforward.md`) aynı resmi verir: ΔLL 0,0002 [0,0000, 0,0005].

## 2. Kapı ne ölçtü

`verify.sh`, log dosyasından okunur: `ruff-check`, `ruff-format`, `mypy`, `pytest`, `paket-kurulu` (artık
`scipy.optimize`i de yükler), `kaynak-politikası`, `veri-sözleşmesi`, `sızıntı` (`EXPECTED_MIN_LEAKAGE=336`),
`dil-kalibrasyonu`, `secrets` → 10 PASS; `zincir` `DATABASE_URL` yokken **ADIYLA SKIP**, bağlıyken PASS (11/11,
dalga 4 sonunda ölçüldü). pytest 1.790 passed / 3 skipped (üçü de `DATABASE_URL yok`: `test_db.py` ×2,
`test_holdout_phase_db.py`).

Faz 3'ün kapıya ve CI'ya eklediği, kırmızı verebildiği kanıtlanmış ölçümler:
- **G2–G3, G7:** gelecek-fit kanaryası, katlar arası sızıntı, belirlenimcilik (Task 6 mutasyonları; Task 9'da iki koşu
  aynı satır özeti `b346641b…`).
- **G4 — `history.yml` "Model bilinen sonuçları":** W1 (daha kötü olmama, üst uç ≤ 0,001), W2 (fit Elo > iskele),
  W3 (DC > S oranları) kapı, W4 rapor. Runner'da yeşil (run 35837046245). CLI'nın kırmızı W'de exit 1 verdiği
  O13 mutasyonuyla kanıtlı.
- **G5/G6 — tek açılış:** `final_eval`in ön denetimi + 0010 indeksi (gerçek DB'de önce kırmızı, sonra yeşil).
- **AST kuralları** (12i anahtar akışı, 14h özel adlar) ve m10 (`shadow.yml`/`history.yml` `ODDS_API_KEY` almaz).
- **E3 (`live parity`):** eşleşmiş maçta yapısal fark → exit 15.

## 3. Kapının ÖLÇMEDİKLERİ — burası "yeşil" sayılmaz

### 3.1 Tasarım §12 (on üç madde — hepsi geçerli)
Fiyat değerinde canlı ↔ tarihsel eşitlik; football-data gecikmesi; S'de `BbAv`, E'de `Avg`; S'de başlama saati yok;
canlı `pre` saatler önce toplanır; AUT ve ek liglerde harman/CLV yok; boşluk cezası yalnız simülasyon + C6; §3/36–39;
bootstrap bağımsızlık varsayımı; tek açılış bir kez harcanır; Elo grup = ülke varsayımı; AST kuralı kasıtlı kaçışı
durdurmaz; kapı kâr ölçmez.

### 3.2 Planın eklediği (14–27; plan "Faz 3 kapısının ÖLÇMEYECEKLERİ")
14 bağlam yalnız `Avg` 1X2 · 15 Placebo K4 sayısı değişti · 16 seçim yerel optimum · 17 W1 δ keyfî; sıralı lojit
küresel · 18 DC görülmemiş takımı tahmin etmez · 19 gölge harmanı/CLV'si yok (P25) · 20 kitap kümesi farkı E3'te yok ·
21 < 30 dk başlama kayması görünmez · 22 macOS ↔ Linux kayan nokta (W1–W4 bu fazda iki platformda gösterilen
hassasiyette AYNI çıktı) · 23 açılış öncesi kilit ikinci kez yüklenir · 24 R141 sezgisel · 25 ek liglerde `season_of`
yıl dönümü · 26 AST kuralı AnnAssign/walrus görmez (kırmızı takım B4 ile ölçüldü: 10/10 kaçış) · 27 prova C6'yı boş
bırakır.

### 3.3 Yürütmenin eklediği
1. **Izgara ucu:** Elo `k = 10` (alt uç), DC `ξ = 0,003` (üst uç), `sırt = 0,003` (alt uç). Kullanıcı açılışı
   ızgarayı genişletmeden onayladı; genişletme Faz 4'te yeni bir seçimdir.
2. **Holdout raporunda `incomplete` ve `fallback` sayıları basılmadı:** 7.613 ortak satırın kaç maçta bileşen
   kaybettiği ve hangi ligin havuzlanmış ağırlıkla koştuğu bilinmiyor (fallback yarısı anahtarsız hesaplanabilir).
3. **111 holdout maçı satır üretmedi** (kilit 12.092, satır 11.981); neden (başlama ≤ karar anı / görülmemiş takım)
   sınıflanmadı.
4. **C2 ve C5 eşleştirilmemiş:** tasarım §8.1 ΔLL + GA der; rapor yalnız harman − piyasa için eşleştirilmiş ΔLL basar,
   ötekiler strateji başına LL aralığı. Holdout satırları gitti; yeniden hesaplanamaz. Ön kaydın "strateji listesi,
   bootstrap tohumu" kısmı dosyada değil, kaydedilen SHA'daki kod sabitindedir.
5. **Holdout harmanı `frozen_weights` (altı E sezonunun hepsi) ile, E raporu ve W1 genişleyen katlarla:** W1'in δ'sı
   yalnız kat tahmincisinde doğrulandı; holdout tahmincisi bir kez provada koştu. Bahis sayısı farkı (54/7.613 ↔
   1.127/45.510) farklı ağırlık rejimiyle tutarlı, ölçülmedi.
6. **Haftalık W1–W3 kilitli E verisinde bir kod regresyon denetimidir, kayma ölçmez:** aynı kilit ve yapılandırmayla
   aynı sayıyı verir. Bedeli runner'da ~7,5 dk/hafta.
7. **Katalog/kilit özeti bağı (işletme sözleşmesi):** `history_leagues.yaml` ya da `history_lock.yaml` değişirse
   `walkforward`/`model-selftest` ve **gölge** exit 11 verir — gölge satırı yazılmaz, `history.yml` kırmızı olur —
   `model_faz3.yaml` yeniden üretilene dek. Özet elle düzenlenirse yeni `model_config_sha256` 0009'un tekil
   anahtarına girer: gölge serisi ikiye bölünür.
8. **Eşlenemeyen canlı fikstürün bayatlık yarıçapı grubun tamamıdır, 10 gün:** tek bir takma adsız ad o ülke
   grubunun bütün kararlarını bayat yapar (ilk turda 27 eşlenemeyen; 38 takma adla E3 50/1'e indi). Log yalnız
   `bayat durum N` basar, grup etkisini değil.
9. **DC aynı Londra gününün sonuçlarını dışarıda bırakır (`day < at`), Elo karar öncesi biliniyorsa kullanır:**
   canlıda ve tarihte aynı (eşitlik korunur); asimetrinin LL bedeli ölçülmedi.
10. **`devig` power/multiplicative'de toplamı 1'in altındaki satırı kabul eder:** E raporundaki Ü/A "piyasa 1 bahis,
    CLV 0,749" satırı budur; 1X2'de E ve holdout'ta rastlanmadı ama korunmuyor.
11. **0010 yalnız `DATABASE_URL` bağlıyken kanıtlanır:** yerel yeşil kapı onu içermez (3 SKIP).
12. **R153 kör noktası:** `naming.codes`da olup o batch'te fikstürü olmayan bir defter ligi ne (a) `is_stale` ne (b)
    `lagging_leagues` ile yargılanır.
13. **Kırmızı takım B2:** bayat koruması karara göre 10 gün geriye bakar, gölge defteri `now − 10 gün`den yükler; salı/cuma
    12:35 koşusunda fark < 1 gün, elle geç koşuda kör nokta büyür.
14. **Lost-ack (Task 10 parked):** `open_holdout` satırı commit'ledikten sonra kendisi hata verirse süreç exit 1 ile
    biter (14 değil). Kural: **exit 1/137/başka → önce `select … from holdout_access_log`**; satır varsa açılmış sayılır.
15. **ned.1/bel.1 `Date` eşleşmesi:** E3 penceresinde bu liglerin canlı maçı yoktu (milli ara); ilk maç haftasından
    sonra ölçülür. AUT kapalı (§3/38 AUT için açık).

## 4. Verilen kararlar

Tasarım R128–R139; plan P1–P25, R141–R148 (planın "Plan yazımında verilen kararlar"). Yürütmenin kararları (defter):

| No | Karar | Yanlışsa bedeli |
|---|---|---|
| R149 | Task 0 planın dediği gibi `main`de, controller tarafından | 1 controller commit'i görev incelemesiz (kapı + mutasyon koştu) |
| R150 | Dalga 1'in dört implementer'ı ayrı worktree'lerde paralel | birleştirmede çakışma (olmadı) |
| R151 | Implementer'lar oturum modelini miras alır; K1 incelemeleri fable | maliyet |
| R152 | Kadans 1 gün (DC fiti 0,02 sn; üst sınır ~12 dk < 45 dk) | seçim süresi (ölçülen 200 sn) |
| R153 | `lagging_leagues` defter liglerini yargılamaz (R141'in yazılı kapsamı) | defter liginin kendi dosyası gecikirse bir tur bayat durumla tahmin |
| R154 | `final_eval`: açılış sonrası `__exit__` arızası exit 14; `--rehearse` ve yeniden koşu amacı testli | `final_eval.py` plan metninden sapar |
| R155 | Task 12: CLI ve kapı bayrağı testleri eklenir | yok |
| R156 | Kırmızı takımın B1–B5'i açılıştan önce düzeltilmez (yalnız Minor) | açılış yanlış ön kayıtla yapılsaydı sha256 gösterirdi ama holdout harcanırdı (açılış kanonik yollarla yapıldı) |
| parked | Lost-ack → exit 1; veritabanı gerçeğin kaynağı | §3.3/14 |

**İnceleme m4 notu:** `report_exists` denetimi farklı bir `--out` ile atlanabilir — aynı SHA + temiz ağaç aynı kodu,
yapılandırmayı ve ön kaydı garanti ettiği için zararsız; 0010 yeniden koşuyu yine bire sınırlar.

## 5. Ertelenenler

`docs/DEFERRED.md` §16 — **açılıştan önce düzeltilmesi gerekenler** (bir sonraki açılış, Faz 4/5): açılış sonrası
arıza yolları (`--out` dizini, `fit_weights` yakınsamama), ön kaydın kanonik yolu (B3), ön kayıt ↔ rapor
sözü (C2/C5 eşleştirilmiş). Gölge CLV raporu (P25) Faz 4'ün ilk görevi.

## 6. Faz 4 ön koşulları

- **Gölge sicili birikiyor:** `model_predictions` (salı/cuma 12:35 UTC `shadow-dispatch`, ilk karar turu
  2026-09-26 cuma); haftalık gölge CLV raporu (harman + bahis + mühürlü kapanış) Faz 4'ün ilk görevi (P25). Sicilin
  büyüklüğü ölçülerek başlanır.
- **Takma ad hijyeni:** her yeni eşlenemeyen ad (log `eşlenemeyen U`) aynı gün/lig/konum kuralıyla
  `config/history_aliases.yaml`a — yoksa o grup 10 gün bayat (§3.3/8).
- **Dil kalibrasyonu ve Jev istemcisi** (Faz 4'ün asıl işi); baz çizgi bu belgedeki C1–C6.
- **R128:** holdout (2025/26) Faz 5 açılışından sonra durum verisi olur; bir sonraki fazın holdout'u ayrıca tasarlanır.
- **Bir sonraki açılıştan önce:** DEFERRED §16'nın "açılış öncesi" satırları, `preregistration.PHASE` parametreleşir
  (M5), ön kayıt tam olarak raporun bastığını listeler.
