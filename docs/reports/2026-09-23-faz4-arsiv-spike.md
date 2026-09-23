# Faz 4 T0c — arşiv ve kaynak spike'ı: karar raporu

**Tarih:** 2026-09-23 · **Spec:** `docs/superpowers/specs/2026-09-23-faz4-jev-sinyal-design.md` §3 (R157, R166,
R172) · **Ölçümler ve komutlar:** `docs/superpowers/specs/2026-09-23-faz4-olcumler.md` §T0c · **Durum:** kullanıcı
onayı bekliyor (Plan 1 Task 6 Step 8).

Bu rapor yalnız toplu sayı taşır; ham başlık, gövde ya da sayfa metni yoktur. Kaynak politikası spec
`2026-09-19-football-edge-design.md` §3.2 / §3.2.1 aynen uygulandı: robots kodla soruldu (`_guarded_get` +
`protego`), dürüst kimlik, 429'da yalnız bekleme, hiçbir engel aşılmadı, hiçbir ham içerik depoya girmedi.

## 1. Karar özeti

| Çıktı (Plan 2'ye) | Değer |
|---|---|
| **Arşiv ayağı** | **KAPALI** — spec §3'ün 2. koşulu (ölçülmüş kapsam) sağlanamadı; 3. koşul yetersiz örneklemle. §7.3'ün yalnız-canlı yolu uygulanır |
| `lag_a_p99` | **7,41 saat** (GDELT mentions ↔ ajansspor iddiası; n=14 eşleşme, eşleşmeyen %98,9 — zayıf; n=14'te p99 = en büyük fark) |
| **EN canlı kaynak (T2)** | **GDELT DOC 2.0 API** — adaylar içinde ToS'u temiz tek kaynak; iki koşulla (§5) |
| **Haber gövdesi (ajansspor)** | **Okunabilir** — robots 1.251/1.251 makale yolunu izinli sayıyor; gövde JSON-LD `NewsArticle.articleBody`. Sinyal başlık düzeyiyle sınırlı değil |

## 2. Spec §3'ün üç koşulu

| # | Koşul | Ölçülen | Tutuyor mu |
|---|---|---|---|
| 1 | Lisans / robots temiz | GDELT: koşullar ticari dahil sınırsız (atıf zorunlu); API ve ham dosya host'larında robots yok (404). CC-NEWS: `data.commoncrawl.org` robots `Disallow: /`, CDX uçları kapalı, ToS ticari kullanım için "legal counsel" öneriyor → elendi. Internet Archive: "scholarship and research purposes only" → elendi. Google News RSS: kişisel/ticari olmayan → elendi | **Evet, yalnız GDELT için** (üçüncü taraf başlık notu §5) |
| 2 | TR ya da EN'de E bölgesi + holdout için lig-sezon başına ölçülmüş kapsam; holdout'ta haberli maç payı ≥ %30 | **ÖLÇÜLEMEDİ.** GDELT DOC API 2019'a iniyor (ölçüldü: 2019-12'de 200, 250 kayıt) ama yerel ağdan 429 — 2 yanıt / 19 istek, ~1 yanıt / 25 dk (20 dk sessizlik sonrası da). 2.800 sorguluk örneklem bu ağda koşulamaz; ham GKG ile maç başına ~14 GB — bütçe dışı; BigQuery ücretli + hesap (yasak). Runner'dan ölçüm bu görevde yapılmadı (push yok) | **Hayır** (ölçülmemiş kapsam "yeterli" sayılamaz) |
| 3 | Eşleşen haberde arşiv damgası ↔ yayıncı iddiası \|fark\| p99 ≤ 24 saat | GDELT 2.0 mentions (20 gün, 3.951 dosya): 1.251 iddianın **14**'ü URL ile eşleşti (eşleşmeyen %98,9); fark medyan 6,31 · p95 7,24 · p99 7,41 saat; negatif 0 | **Evet, ama n=14** — tek başına güvenilir bir p99 değil |

Spec §3: "Biri tutmazsa arşiv ayağı kapalıdır." 2. koşul tutmadığı için karar koşul 3'ün sonucundan bağımsızdır.

## 3. Ölçüm sonuçları (toplu)

**GDELT (T0c/1).** Türkçe içerik translation akışında; güncel hacim düşük: üç 15 dk'lık translation GKG
dosyasında 8.467 kaydın 483'ü Türkçe (40 alan adı), `ajansspor.com` 0. DOC API belgeden derin arıyor (2019-12
sorgusu 250 kayıtla tavanda, hepsi Türkçe). Ham dosya host'u yerel ağdan sorunsuz; DOC API değil (429).

**Kapsam (T0c/3).** Koşulamadı. Örneklem betiği hazır: 8 lig × 7 sezon × 50 maç, tohum `20260923`, pencere
`[gün−7, gün 12:00Z)`, dil ayrımı kaydın `language` alanından. Runner'da DOC API açıksa aynı betik
koşulabilir (§6).

**Yayın zamanı (T0c/4).** DOC API 429 verdiği için ham GDELT 2.0 mentions dosyaları (ana + translation, 15 dk,
2026-09-03 → 09-23; 3.951 dosya, 314 MB, bellekte açıldı) tarandı. ajansspor 16 tekil URL ile görünüyor (hepsi
translation akışında); 14'ü iddiayla URL üzerinden eşleşti. Arşiv damgası her zaman iddiadan SONRA (+3,85…+7,41
saat): GDELT'in çeviri kuyruğu gecikmesi. Tutarsızlık yok, ama eşleşme %1,1 — ajansspor GDELT'te seyrek.

**Gövde (T0c/5).** Canlı robots anlık görüntüyle aynı; 1.251/1.251 `/haber/` yolu izinli; Content-Signal
`ai-input=yes` (Jev girdisi izinli), `ai-train=no`. Tohumlu tek sayfa: 200, JSON-LD `NewsArticle` + `articleBody`
+ `datePublished`/`dateModified`. Seçici: başlık `h1`/JSON-LD `headline`, gövde JSON-LD `articleBody` (Tailwind
sınıfları kırılgan, kullanılmaz). ajansspor ToS'u robots'ta `Disallow` olduğundan okunmadı.

**EN adayları (T0c/6).** Son 7 gün, lig başına başlık (E0/SP1/I1/D1/F1/T1/N1/B1):

| Aday | Kapsam | ToS | Karar |
|---|---|---|---|
| BBC Sport RSS | 31/0/0/0/0/0/0/0 | §15 RSS'ten meta veri "koparmak" yasak; yapay zekâ/bilgisayarla analiz izne tabi | Elendi |
| The Guardian RSS + Open Platform | 18/7/1/2/2/0/0/0 | yapay zekâ ve metin/veri madenciliği açıkça yasak | Elendi |
| ESPN RSS | 4/3/0/2/0/0/0/0 | otomatik erişim, yapay zekâ ve veri madenciliği yasak | Elendi |
| Sky Sports RSS | 9/0/0/2/0/0/0/0 | koşul metni okunamadı (JS) → temiz sayılamaz | Elendi |
| **GDELT DOC API** | ≈ 3.696/432/72/192/312/24/72/48 (GKG 1/24 örneği ×24; E0 şehir adları yüzünden üst sınır) | ticari dahil sınırsız, atıf | **Seçildi** |

Seçim ölçütü sırası (ToS temiz > lig kapsamı > yapısal alanlar) tek sonuca götürüyor: ToS'u temiz olan tek aday
GDELT; 8 ligin hepsinde haftalık başlık var (T1 ve B1 zayıf); `seendate` GDELT'in kendi gözlem saatidir (yayıncı
iddiası değil — R172 açısından değerli bir üçüncü saat).

## 4. Ölçülmeyenler

- Lig × sezon kapsam payı (koşul 2). (DOC API'nin 2019'a indiği ölçüldü.)
- DOC API'nin GitHub Actions runner'dan erişimi (bu görevde push yok).
- GKG (tüm makaleler) üzerinden ajansspor eşleşmesi — yalnız mentions (olay taşıyan makaleler) tarandı.
- ajansspor ve Sky Sports ToS metinleri.
- §3/2b (yayıncı iddiası ↔ `first_seen_at`) — Plan 2'de, Task 9'dan ≥ 2 hafta sonra.

## 5. EN kaynağının koşulları (kullanıcı kararı)

1. **Erişim ortamı:** DOC API bu ağdan 429 veriyor. Canlı toplayıcı runner'da koşar (R73: kaynağın açık olduğu
   meşru ortam); runner'dan erişim Plan 2'nin T2'sinde ilk iş olarak ölçülür. Runner da 429 alırsa GDELT'in ham 15
   dk dosyaları (`data.gdeltproject.org`, robots yok, sorunsuz) aynı veriyi taşır: GKG `<PAGE_TITLE>` + URL +
   15 dk damga.
2. **Üçüncü taraf başlıkları:** GDELT'in lisansı kendi veri setlerini kapsar; başlıklar yayıncılarındır. ToS'u
   yapay zekâ kullanımını açıkça yasaklayan alan adları (bu spike'ta ölçülen: `theguardian.com`, `bbc.co.uk` /
   `bbc.com`, `espn.com`) toplayıcıda dışlanmalı. Liste ve ilke kullanıcı kararıdır.

## 6. Arşiv ayağını yeniden açmanın yolu (isteğe bağlı, bu faz için önerilmez)

Kapsam ölçümü runner'da tek kullanımlık dalla koşulabilir (`step3_coverage.py 50 50`, ~2.800 sorgu, 6 sn aralıkla
~4,7 saat). Derinlik engel değil (2019-12 ölçüldü); engel yerel ağdaki 429 ve koşul 3'ün örneklemi (§2). Runner da
429 alırsa ayak kapalı kalır. Yalnız-canlı yol (§7.3) bu kararla zaten tanımlıdır; öneri: ayak kapalı, Plan 2
canlı yolla yazılır.
