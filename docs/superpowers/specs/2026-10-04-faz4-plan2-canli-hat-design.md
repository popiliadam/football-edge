# Faz 4 Plan 2 — canlı Jev sinyal hattı (tasarım deltası)

**Tarih:** 2026-10-04 · **Durum:** kullanıcı kararları asistanın önerisine devretti ("en iyi senaryo, senin
önerilerine göre"; bellek `user-delegates-to-recommendation`); onay yerine bağımsız spec incelemesi (0 C / 11 I / 8 M, hepsi aşağıya işlendi — §5) · **Ana
tasarım:** `2026-09-23-faz4-jev-sinyal-design.md` (R157–R172) — burada yazılmayan her şey aynen geçerli.
**Girdi:** DEFERRED 17k (arşiv ayağı KAPALI, 2026-10-04) · HANDOFF §0.S (K/4 kaynak kararı, K/6 ücretli Jev onayı,
tavan 25 $) · `docs/reports/2026-10-02-en-haber-kaynaklari.md` · `docs/reports/2026-09-23-ek-kaynaklar.md` ·
avukat paketi S5/S8.

---

## 0. Karar özeti

| No | Karar | Gerekçe | Yanlışsa bedeli |
|---|---|---|---|
| R173 | **Yalnız-canlı yol (§7.3).** Seçim dilimi **ilk kademe 2 `real` yazımıyla** başlar (ana spec "T6'dan itibaren" diyordu). `harman_jev` satırı β ve özellik listesi donmadan (`model_faz4.yaml`, Plan 3) **yazılmaz** | β = 0'lı `harman_jev` `harman`ın kopyası olur, gölge serisini anlamsız böler; seçim için gereken tek şey karar anında kaydedilmiş Jev cevaplarıdır | Seçim dilimi kademe 2 çalışana dek başlamaz |
| R174 | **Plan 2 = canlı hat:** kaynaklar, dil kapısı, kademe 1 zamanlaması, TR kalibrasyon ölçümü, kademe 2 koşucusu, dilim sayacı. **Plan 3** (≥ 900 haberli maç): T8 budama, T9 eşdoğrusallık, `harman_jev` yazımı, T10 ön kayıt (+ `lag_b_p99`, güç yeniden hesabı), kapı dilimi | Budama verisi yokken yazılan plan bayatlar | — |
| R175 | **Kaynaklar (K/4 aynen):** EN Sports Mole, Independent, Evening Standard, GFFN, Football Oranje; TR Fotomaç, A Spor — RSS. **Saklanan yalnız başlık + URL** (özet/gövde tutulmaz; bugünkü `news_observation` biçimi) | K/4 kullanıcı kararı (koşullu iç kullanım). Independent/Standard koşulları başlık + URL'yi açıkça serbest bırakan tek biçim; özet saklamak saklama maddesine girer | Avukat S8 olumsuzsa kaynak kapanır; append-only satırlar KALIR (kabul edilen risk, K/4) |
| R176 | **GDELT canlıda da yok:** DOC API runner'dan ve yerelden 429 (17k). **Wikidata P286** (teknik direktör değişimi) Plan 3 adayı. **SportMonks denemesi ertelenir:** değerlendirecek toplayıcı yokken 14 günlük deneme boşa geçer | YAGNI; ölçülmüş erişilemezlik | EN kapsamı yalnız RSS'lerle |
| R177 | **Ücret anahtarı = tek commit.** Jev'li adımlar workflow'lara anahtarsız eklenir; anahtar yokken `exit 17` adıyla **"Jev kapalı"** — adım yeşil, alarm yok, özet satırı. Ücreti açan commit `TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}` **ve `JEV_ENABLED: "1"`** env satırlarını ekler; `JEV_ENABLED=1` iken 17 **kırmızıdır** (I-5: boş/yanlış adlı secret sessiz kalmasın). Workflow testleri `TYPESAFE_API_KEY`yi YALNIZ kademe 1/2 adımlarının env'inde kabul edecek biçimde Plan 2'de yeniden yazılır (I-4); yama testlere dokunmaz. **Kullanıcı koşar** (hazır yama + tek komut) | Asistan ortamı ücret açan commit'i reddeder (bellek `credit-activation-commit-blocked`); bütün kod anahtarsız kapıdan geçmiş olur | Kullanıcı commit'i koşmazsa sinyal sessizce toplanmaz — HANDOFF ve adım özeti adıyla söyler |
| R178 | **Dil kapısı Jev'den önce:** kademe 1 ve kademe 2 yalnız `production_enabled: true` dillerin haberini sorar | Kalibre olmayan dilin cevabı kullanılmaz (§9); boşa harcama | EN sinyali EN kalibrasyonuna dek yok |
| R179 | **Kademe 1 `collect-news.yml` içinde**, `sync-news`ten hemen sonra (2 saatte bir) | Canlı `asked_at < decided_at` (§5/1): haber karar anından önce sorulmuş olmalı; ayrı workflow ikinci bir dispatch + eşzamanlılık yüzeyi | Jev kesintisi haber turunu kırmızı yapmaz: exit 7/16/17 adıyla ayrılır |
| R180 | **Kademe 2 `shadow.yml` içinde**, `live shadow`dan sonra. Maç kümesi **o turun gölge satırlarıdır** (`model_predictions`te `(match_id, decided_at)` varlığı; yalnız varlık okunur, olasılık okunmaz — I-2, M-1): eşlenemeyen/bayat/fiyatsız maç sorulmaz. Taraf başına tek batarya (T2 + T3 + T4 = 30 soru); taraf kümesi ev = ev ∪ ikisi, deplasman = deplasman ∪ ikisi, `item_set_hash` taraf başına (M-4); haber kümesi `derive.select_items`; kademe 1 kapıları yalnız `asked_at < decided_at` satırlarından (I-3). Haberi olmayan taraf **sorulmaz**; özellikte ölçeğin "yok" seviyesine deterministik atanır ve `imputed` sayılır (I-1). Yalnız `variant = real` (kanarya arşiv içindi, R167). `now − decided_at > 6 saat` ise sormaz (M-2); cevaplanmış taraf yeniden sorulmaz (M-3) | Gölge satırlarıyla `(match_id, decided_at)` üzerinden birebir eşleşir; `live.store` import edilmez (AST kuralı) | Gölge turu kaçarsa o karar anının Jev satırı da yok (aynı yön, tutucu) |
| R181 | **Dilim sayacı:** `features slice-status` = en az bir tarafında `real` cevabı olan **ve gölge satırı olan** (maç, karar anı) sayısı, **dondurulmuş küme başına** (R185); haftalık hız ve 900'e varış tahmini; `shadow.yml` özetine. Sonuç/tahmin OKUMAZ | 900'e varış Plan 3'ün tetiği; mühür bozulmaz | — |
| R182 | **TR kalibrasyonu ölçülür:** `calibrate --language tr` (CLI var), 100 çağrı, tavan içinde. Asistan yerelde koşar; ortam reddederse kullanıcıya tek satır. Eşik **önceden bağlı:** `min_n = 100`, `min_accuracy = 0,85` (bugünkü değerler) — gevşetmek **kullanıcı durağı** (I-11). `c_min` budamanın parametresidir (ana spec §6), burada seçilmez. Yalnız geçerse `tr: production_enabled: true` | §9 dil kapısı; placeholder eşikler (0,85) ölçüm olmadan değişmez | TR geçmezse Plan 2 sinyalsiz kalır — sonuç adıyla raporlanır |
| R183 | **EN etiket paketi** EN `news_items` ≥ 150 olunca: Opus ön etiket + bağımsız ikinci etiket → kullanıcı onayı (**kullanıcı durağı**) → EN kalibrasyonu | T5 (Plan 1) TR deseni | EN sinyali gecikir |
| R184 | **Maliyet önce kuru koşuyla:** TR üretimde VARSAYILARAK kademe 1 (`candidate_fixtures`) ve kademe 2 üst sınırı (adaylı taraf × gölge karar anı) Jev'siz sayılır; günlük çağrı, haftalık haberli maç hızı, **900'e varış tarihi** basılır (I-10). Ardından **tek gerçek kademe 1 + tek gerçek kademe 2 çağrısı**: gecikme ve model adı ölçülür, **kullanıcı birim fiyatı TypeSafe panelinden okur** (I-9). Aylık tahmin > 20 $ ya da 900 tarihi 2027-06-30'u aşıyorsa **kullanıcı durağı** | Tavan 25 $; tavan dolarsa ayın kalanı sinyalsiz | Birim fiyat ölçülmedi (SDK maliyet vermiyor) |
| R185 | **Dondurulmuş küme:** ilk gerçek kademe 2 yazımından önce `prompt_version`, Jev modeli (sabitlenir, `jev-latest` değil), `min_belongs`, `min_reliability` `config/faz4_live.yaml`a yazılır ve sha256'sı (soru dosyasıyla birlikte) her kademe 2 satırına girer; operasyonel ayarlar (tahmin birimleri, tur tavanları, karar yaşı sınırı) hash DIŞINDA — fiyat düzeltmesi sayacı sıfırlamasın (plan incelemesi M4). Taraf başına durum işareti `side_status:<side>` (asked/no_news/…) yazılır — Plan 3 karar anındaki dil kümesini yeniden kurmak zorunda kalmaz (plan incelemesi I5); değişirse yeni küme, sayaç küme başına (I-11) | Seçim verisi append-only; parametre kayması diliminin yarısını yetim bırakır | Yeni küme sayacı sıfırdan başlatır |
| R187 | **Takvim ölçüldü (I-10, 2026-10-04):** Jev'siz `candidate_fixtures` sayımı, yalnız TR haber, yayıncı damgası: 2026-W38'de 51 maçın 33'ü haberli (tur.1 11/13, eng.1 8/15, esp.1 8/14, ger.1 7/15, ita.1 5/12, fra.1 4/14, bel.1/ned.1 0). ~33/hafta → 900'e ~27 hafta (≈ 2027-05); kapı dilimine 2027-06-30'a dek ~300 maç → §7.3 yolu bu sezon **neredeyse kesin GÜÇ YETERSİZ**. Plan 2 hattı bu karardan bağımsızdır (30 cevabın hepsi kaydedilir); **Plan 3 önerisi (kullanıcı durağı):** ayrı seçim dilimi kaldırılır, önceden kayıtlı TEK bileşik özellik (T2 çekirdeğinin eşit ağırlıklı farkı, işaret önceden) + prequential β (her maçın β'sı yalnız öncekilerle) → bütün canlı veri kapı verisi | Budama 35 aday × 900 maçta zayıf ve çoklu test yükü taşır; prequential değerlendirme dürüst örnek dışıdır | Tek özellik sinyalin bir kısmını kaçırır (T3/T4 betimsel kalır) |
| R186 | **Alarmlar ayrık:** Jev adımları kendi alarm anahtarıyla (`jev`); `fetch-news` exit 7 olsa da `sync-news` ve kademe 1 koşar, tur sonunda kırmızı biter (I-6, I-7). `shadow.yml` sırası: shadow → report → tier2 → slice-status. Tur başına öğe tavanı + parti başına commit (I-8) | Bütçe kırmızısı ayın kalanında gerçek kaynak arızasını gizlemesin (10h dersi); zaman aşımı ödenmiş cevabı yutmasın | — |

---

## 1. Bileşenler ve dosya kümeleri

| Görev | Kademe | Ne | Dosyalar (tek yazar) |
|---|---|---|---|
| **P2-T1** RSS kaynakları | K2 | Genel RSS bağdaştırıcısı: kaynak başına **yol listesi** (`_ARTICLE_PATHS` → çoklu), kaynak başına beklenen içerik türü (`application/rss+xml`, `text/xml`, `application/xml`), `pubDate`'siz öğe bugünkü bayrakla. 7 kaynak: `sources.yaml` kaydı + `config/robots/<id>.txt` canlı ölçümle (tek istek, bizim kimlik) + bildirilen yollar izinli. `NEWS_SOURCE_LANGS` 7 kaynakla | `collectors/news.py`, `features/news.py` (yalnız dil eşlemi), `config/sources.yaml`, `config/robots/*`, testler, fixture'lar |
| **P2-T2** Dil kapısı + kademe 1 zamanlaması | K1 | `tier1` yalnız üretim dillerini sorar; `gates_from` yalnız `asked_at < decided_at` (I-3, T3 kullanır); tur başına öğe tavanı + parti commit'i; `collect-news.yml`e `features tier1` adımı (exit 7 "Jev kesintisi", 16 "bütçe", 17 "Jev kapalı" adıyla; yalnız 0/17 yeşil-sessiz, 7/16 alarm) | `features/tier1.py`, `features/__main__.py`, `collect-news.yml`, workflow testleri |
| **P2-T3** Kademe 2 koşucusu | K1 | `config/faz4_live.yaml` (R185), `derive` "yok" ataması (I-1), `features tier2`: gölge turunun maçları, `select_items`, taraf bataryası, `jev_match_answers` yazıcısı (idempotent, tekil anahtar), okuyucu 17a mührü altında; `shadow.yml` adımı | yeni `features/tier2.py`, `features/__main__.py` (T2'den sonra — sıralı), `shadow.yml` |
| **P2-T4** Dilim sayacı | K2 | `features slice-status` + `shadow.yml` özet satırı | `features/slice.py`, `features/__main__.py`, `shadow.yml` (T3'ten sonra) |
| **P2-T5** Kuru koşu + tek gerçek çağrı | K2 | R184: Jev'siz sayım (salt okuma), 900 tahmini; tek gerçek kademe 1/2 çağrısı (gecikme, model) → ölçüm belgesi; **kullanıcı birim fiyatı okur** | `docs/superpowers/specs/2026-09-23-faz4-olcumler.md` |
| **P2-T6** TR kalibrasyonu + ücret yaması | K1 | ücretli ölçüm (R182), eşik gerekçesi, `config/languages.yaml`; ücret açan yama dosyası + kullanıcıya tek komut | `config/languages.yaml`, `data/calibration/tr.report.json`, ölçüm belgesi |

**TR yolları (ölçüldü 2026-10-04, proje kimliğiyle birer istek):** Fotomaç ve A Spor robots'u `Content-Signal: search=yes,
ai-input=yes, ai-train=no`, `/rss/` kapalı değil. A Spor `/rss/futbol.xml` → 200 `application/xml`, 100 öğe, güncel.
Fotomaç `/rss/futbol.xml` ve `/rss/anasayfa.xml` **bayat** (son öğe 2025-05-31) → yol **`/rss/news.xml`** (200
`text/xml`, 212 öğe, güncel). EN yolları rapordaki ölçümden (`/football/rss.xml`, `/sport/football/rss`, `/feed/`);
T1 her birini yeniden ölçer ve robots anlık görüntüsünü yazar.

Sıra: T1 ∥ T2 (ayrık dosyalar) → T3 → T4; T5 T1–T3'ten sonra; T6 T5'ten sonra (maliyet bilinmeden ücret açılmaz).
Kullanıcı durakları: **birim fiyat okuma** (R184), **900 tarihi / > 20 $ tahmin** çıkarsa karar (R184), **TR eşiği tutmazsa gevşetme kararı** (R182), **ücret yaması commit'i** (R177), **EN etiket onayı** (R183, tarih koşullu).

## 2. Veri akışı

```
RSS (7) ─collect fetch-news─► source_observations ─sync-news─► news_items(lang)
   └─ 2 saatte bir ─► features tier1 (üretim dili, ufuk 8 gün) ─► jev_item_answers
shadow.yml (salı/cuma 12:35) ─► live shadow ─► model_predictions (baz)
                              └► live report (baz)
                              └► features tier2 (bu turun gölge satırları) ─► jev_match_answers(real)
                              └► features slice-status ─► özet: "seçim dilimi N / 900 · tahmini varış"
```

## 3. Hata yolları ve kapı

- Kaynak düşerse yalnız o kaynak sayılır (bugünkü yalıtım); `collect fetch-news` exit 7 adıyla.
- Jev: 17 (anahtar yok) yeşil + özet "Jev kapalı" — `JEV_ENABLED=1` iken kırmızı; 16 (tavan) ve 7 (kesinti) **ayrı `jev` alarmı**. Kademe 2 kısmi başarı: yazılan
  taraflar kalır, eksik taraf `incomplete` (özelliğe `f = 0`, §6).
- Kapıya eklenenler (her biri "nasıl kırmızı verir" testiyle): üretim dışı dilin haberi Jev'e gitmez · kademe 2
  `available_at < decided_at` ve `asked_at < decided_at` (mutasyon `<` → `<=`) · kademe 2 yazıcısı idempotent ·
  `slice-status` sonuç/tahmin tablosu okumaz · kuru koşu ve testler `jev_match_answers`e yazmaz (M-8) · `JEV_ENABLED=1` + 17 kırmızı · `TYPESAFE_API_KEY` yalnız kademe adımlarının env'inde · workflow'lar exit kodlarını adıyla ayırır · yeni kaynakların robots
  anlık görüntüsü ve bildirilen yolları (`kaynak-politikası` zaten zorlar).

## 4. Kapının ÖLÇMEYECEKLERİ (ana spec §11'e ek)

1. RSS öğesinin `pubDate`'i yayıncı iddiasıdır; `first_seen_at` 2 saatlik toplama aralığı kadar geç (R172 aynen).
2. Avukat S8 olumsuz dönerse saklanmış başlıklar append-only tabloda kalır.
3. Kademe 1/2 birim fiyatı ölçülmedi (0,01 $ tahmin); tavan tahminle sayar.
4. EN kaynaklarının lig dağılımı dengesiz (B1/T1 için EN yok); D5 betimsel.
5. Gölge turu kaçarsa o karar anının kademe 2 satırı da yoktur.
6. Kademe 2 `asked_at` her zaman `decided_at`ten sonradır (12:35 tetiği); Jev'in canlı bilgi aramadığı VARSAYILIR (ölçülmez).
7. Dil kalibrasyonu yalnız başlık-ilgililik görevini ölçer; kademe 1/2 cevaplarının doğruluğunu ölçmez (M-7).
8. Haberi olmayan tarafa "yok" ataması bir varsayımdır (I-1); `imputed` sayısı raporlanır.
9. Başlıkların TypeSafe'e gönderimi avukat S8 sorusuna eklenmeli (M-8; kullanıcı paketi gönderirken). Her kaynağın
   `Content-Signal: ai-input` değeri `note`a yazılır; `no` olan kaynağın haberi Jev'e gitmez.

## 5. İnceleme izi

Bağımsız inceleme (2026-10-04): doğrulananlar — R180 zamanlama ve AST uyumu, R175 saklama (yalnız başlık/URL/tarih),
R178 (bugün dil süzgeci yok), şema iki tarafa izin verir (`<q>:<side>`), R173 istatistiksel olarak sağlam. I-1…I-11 ve
M-1…M-8 yukarıdaki R173–R186 ve §1–§4'e işlendi; dil kümesi ön kayıtta (Plan 3) donar, EN seçim diliminde açılabilir (M-6).
