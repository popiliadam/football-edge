# Faz 1–7 Yol Haritası

**Tarih:** 2026-09-19 · **Durum:** yol haritası (Faz 1 ayrıca tam plan alacak)
**Spec:** `docs/superpowers/specs/2026-09-19-football-edge-design.md`

Bu doküman, Faz 0'dan sonraki yedi fazın **hedefini, girdisini, çıktısını, kapısını ve
task başlıklarını** tanımlar. Her faz kendi tam TDD planını sırası gelince alır — bu
doküman o planların çerçevesidir, yerine geçmez.

**Değişmeyen kurallar (spec §3.2, §6.2):**
- robots.txt'i otomatik erişime kapalı kaynak taranmaz; erişim kontrolü aşılmaz.
- Ham içerik yeniden yayınlanmaz; yalnız sayısal özellik türetilir.
- Her satırda `observed_at`; özellik yalnız maç öncesi görülmüş veriden hesaplanır.
- Backtest ve canlı **aynı özellik kodunu** çağırır.
- Kapı: birim testler + veri sözleşmeleri + dondurulmuş holdout üzerinde CLV + sızıntı
  kontrolü + secret taraması. "Daha iyi göründü" geçerli gerekçe değildir.

---

## Faz 1 — Toplayıcılar, varlık eşleme, dil kalibrasyonu

**Hedef:** Modelin ihtiyaç duyduğu her veri türünü, izinli kaynaklardan, append-only ve
`observed_at` damgalı biçimde toplamak.

**Girdi:** Faz 0'ın defteri ve şeması · `config/leagues.yaml`
**Çıktı:** Her kaynak için bir toplayıcı modülü + tablolar; varlık eşleme sözlüğü;
Jev'in çok dilli doğruluk ölçümü.

**Kapı:** Faz 0 kapısı + her toplayıcı için **tazelik ve şema iddiası** + varlık eşleme
doğruluk eşiği + dil kalibrasyon raporu.

### Task başlıkları

| # | Task | Paralel? | Not |
|---|---|---|---|
| 1 | Toplayıcı çatısı: ortak `fetch → doğrula → yaz` iskeleti, tazelik/şema iddiaları, devre kesici | ❌ önce bu | Diğer hepsi buna oturur |
| 2 | **Understat** toplayıcı (6 lig, xG/npxG/xGA/PPDA/xPTS) | ✅ | JS render gerekir; XHR POST'u `outward_action_gate` engelliyor |
| 3 | **FootyStats** toplayıcı (Süper Lig + 1. Lig xG, public sayfalar) | ✅ | `Crawl-delay: 1` — izinli tek TR xG yolu |
| 4 | **FBref** toplayıcı (baz istatistik + **hakem** + seyirci, 40+ ülke) | ✅ | Cloudflare korumalı; xG YOK (Opta 2026-01-20'de gitti) |
| 5 | **ClubElo** toplayıcı (anahtarsız günlük Elo) | ✅ | En kolay kaynak |
| 6 | **Google News RSS** çok dilli toplayıcı (`hl`/`gl` parametreli) | ✅ | Haber katmanının global motoru |
| 7 | **TFF** toplayıcı (hakem ataması `pageID=600` + PFDK `pageID=246`) | ✅ | **windows-1254** kodlama |
| 8 | **Open-Meteo + Wikidata/OSM** (stadyum koordinatı, rakım, maç saati hava) | ✅ | Rakım gerçek bir gol etkisidir |
| 9 | **Varlık eşleme** (Jev): takım/oyuncu adlarını kaynaklar arası eşle | ❌ 2-8 sonrası | Sessiz join hatası bu projenin 1 numaralı ölüm sebebi |
| 10 | **Dil kalibrasyon testi**: dil başına ~100 elle etiketlenmiş haber vs Jev cevabı | ❌ en son | Ölçülmeden hiçbir dil üretime alınmaz |

**Paralelleştirme:** Task 2–8 birbirinden bağımsız, farklı dosyalar, ortak arayüz yok →
**izole worktree'lerde paralel.** Her ajana kendi worktree'si + kendi dalı + kendi venv'i;
sonunda merge. Ortak çalışma ağacında paralel implementer **çalıştırılmaz** (Faz 0'da commit
sınırı bozulmasıyla bedeli görüldü).

**Bilinen riskler:**
- Understat artık JS render istiyor; eski `var teamsData` deseni yok.
- FBref Cloudflare arkasında; `soccerdata`'nın FBref modülü CAPTCHA çözücü istiyor.
- Ajansspor'un RSC formatı garanti vermiyor → Jev'in kendini onaran ayrıştırıcısı burada devreye girer.
- **Jev'in çok dilli doğruluğu ölçülmedi.** Kötü çıkarsa mimarinin en global parçası çöker —
  o yüzden Faz 1'in sonunda değil, ölçüm biter bitmez karar verilir.

> **FAZ 1 BİTTİ — YUKARIDAKİ TASK TABLOSU ARTIK TARİHSELDİR (2026-09-19).**
> Gerçekleşen: 13 task, `faz-1-toplayicilar` dalı. Devir belgesi:
> `docs/phases/01-toplayicilar/HANDOFF.md` (**§3 kapının ÖLÇMEDİĞİNİ yazar — en önemli bölüm**).
> Tablonun neresi tutmadı:
>
> | Tablo diyordu | Ölçüm ne dedi |
> |---|---|
> | Task 2 **Understat** toplayıcı | **YAZILMADI** — `robots.txt` `Disallow: /`. xG'yi FootyStats devraldı, yedek yok. |
> | Task 4 **FBref** toplayıcı (hakem + seyirci) | **YAZILMADI** — içerik VE robots.txt 403 Cloudflare. **Global hakem/seyirci verisi yok**; Faz 3 baz modeli hakem özelliği olmadan kurulur. |
> | Task 5 **ClubElo** ("en kolay kaynak") | **YAZILMADI** — API deactivated + 502. Yerine saf Elo motoru (`elo.py`); `k`, `home_advantage` ve marj eğrisi FİT EDİLMEMİŞ iskele → Faz 2'nin işi. |
> | Task 6 **Google News RSS** | Adaptör yazıldı, **`enabled: false`** — robots her ajana kapalı + feed `<copyright>`'ı ticari dışı kullanımı yasaklıyor. |
> | Task 7 **TFF** `pageID=600` | **DOĞRUYDU, aynen kaldı.** Faz 1 planı bunu `433`'e "düzeltmeye" çalıştı; ölçüm planı çürüttü, spec'i doğruladı. |
> | Task 10 **Dil kalibrasyonu** | **HARNESS var, ÖLÇÜM YOK** — `TYPESAFE_API_KEY` yok, insan etiketi yok. Her dil `production_enabled: false`; spec §5.4'ün Faz 1 şartı **KARŞILANMADI**. |
>
> Tabloda hiç olmayan ve gerçekleşen: maç sonucu toplayıcı (`fetch-results`), stadyum
> koordinatı + maç saati havası (`fetch-venues`), kaynak kayıt defteri + robots'un kodla
> zorlanması, `verify-chain --full` + çıpa eksikliği kontrolü, oran defterine toplu yazma.

---

## Faz 2 — Tarihsel taban, backtest harness, piyasa verimliliği, sızıntı denetimi

**Hedef:** Modeli ölçecek aracı, model yazılmadan önce kurmak. Ve hangi liglerde oynanacağına
tahminle değil **ölçümle** karar vermek.

**Girdi:** `xgabora/Club-Football-Match-Data` (MIT, 38 lig, 238.858 maç, ClubElo + form birleşik)
· Faz 0 defterindeki canlı oran geçmişi
**Çıktı:** Backtest harness · lig başına piyasa verimliliği sıralaması · dondurulmuş holdout ·
sızıntı denetim raporu

**Kapı:** Faz 1 kapısı + **sızıntı yok** kanıtı + backtest'in bilinen bir sonucu yeniden üretmesi.

### Task başlıkları

1. MIT CSV yükleyici + şema doğrulama + `observed_at` semantiği
2. Backtest harness: point-in-time özellik hesaplama, tek kod yolu (canlı ile ortak)
3. Vig temizleme (çoklu yöntem: çarpımsal, Shin, power) ve piyasa olasılığı
4. **Piyasa verimliliği ölçümü**: lig başına kapanış oranının tahmin gücü → sömürülebilirlik sıralaması
5. **Dondurulmuş holdout** dönemi tanımı ve kilitlenmesi
6. **Opus red-team sızıntı denetimi**: "bu backtest'te look-ahead bias'ı bul"
7. Tarihsel vs canlı kapanış referansı kalibrasyonu (spec §1.4: `AvgC*` vs kendi defterimiz)

**Kritik:** Bu fazın çıktısı **hangi liglerde oynayacağımız**. Faz 0'daki 6 lig geçici;
budama burada ölçümle yapılır.

**Bilinen riskler:**
- MIT CSV'nin lisans zinciri (spec §10, madde 2) — ticari lansman öncesi avukat.
- Tarihsel kapanış (`AvgC*`) ile kendi defterimizin kapanışı **aynı büyüklük değil**;
  örtüşen dönemde sistematik fark ölçülmeden tek grafikte gösterilmez.

---

## Faz 3 — Baz model (Jev'siz baz çizgi)

**Hedef:** Jev katmanının üstüne ne eklediğini ölçebilmek için **Jev'siz** bir baz çizgi kurmak.

**Girdi:** Faz 1 verisi · Faz 2 harness'ı
**Çıktı:** Dixon-Coles + ClubElo + piyasa harmanı; holdout üzerinde CLV baz çizgisi

**Kapı:** Faz 2 kapısı + **holdout CLV baz çizgisi kayda geçti** + kalibrasyon ölçümleri
(Brier, log loss, olasılık kovasına göre güvenilirlik diyagramı)

### Task başlıkları

1. Dixon-Coles: zaman sönümlü Poisson, düşük-skor düzeltmesi, MLE fit
2. xG-ağırlıklı varyant (yalnız xG'si olan liglerde)
3. ClubElo önseli ve lig geçişlerinde ortak ölçek
4. **Logistic opinion pooling**: model ile piyasa olasılığının harmanı, ağırlık **lig başına fit**
5. Kalibrasyon ölçüm modülü (Brier, log loss, güvenilirlik diyagramı)
6. Baz çizgi raporu: lig × market kırılımında CLV

**Neden ağırlık lig başına fit edilir:** verimli liglerde piyasa ağırlığı yüksek olmalı,
verimsizlerde düşük. Bunu elle seçmek sayı uydurmaktır; veri söyler.

---

## Faz 4 — Jev sinyal katmanı

**Hedef:** Sayıların göremediği boyutları (haber, kadro, motivasyon, bağlam) kalibre edilmiş
sayısal özelliklere çevirmek ve **baz çizgiye kattığı değeri ölçmek**.

**Girdi:** Faz 1 haber verisi · Faz 3 baz çizgisi
**Çıktı:** Maç başına ~35 tipli yargı · özellik deposu · budanmış ≤15 özellikli model

**Kapı:** Faz 3 kapısı + **baz çizgiye karşı marjinal CLV** + FDR düzeltmesi + dil doğruluk eşiği

### Task başlıkları

1. Jev istemcisi: tek istekte paralel soru, `confidence` okuma, hata/yeniden deneme
2. **T1 kapı soruları**: `haber_bu_maca_ait`, `haber_guvenilirligi`, `kaynak_celiskisi`
3. **T2 çekirdek**: kadro/sakatlık etkisi (hücum/savunma ayrı), rotasyon riski, hava cezası
4. **T3 aday**: motivasyon asimetrisi, hoca baskısı, derbi gerilimi, seyahat yükü, dead rubber
5. **T4 spekülatif**: yalnız kaydedilir, modele girmez
6. Jev'in boru hattı rolleri: kendini onaran ayrıştırıcı, kaynak çelişkisi hakemi, haber kümeleme
7. Özellik deposu: ham Jev cevapları versiyonlu saklanır (yeniden çıkarım gerekmesin)
8. **Budama**: holdout'ta marjinal CLV katkısı + Benjamini-Hochberg FDR → ≤15 özellik
9. Eşdoğrusallık denetimi: eşanlamlı sorular ayıklanır

**Değişmez disiplin:** Jev çıktıları modele **elle katsayı olarak girmez**; tarihsel veri
üzerinde fit edilmiş özellikler olarak girer. Uydurulmuş katsayı modelin yanlış olduğunu gizler.

---

## Faz 5 — İstifleme, staking, CLV kapısı

**Hedef:** Tek modele bağımlılığı kırmak, bahis boyutunu disipline etmek, ve **CLV kapısını
üretime almak**.

**Girdi:** Faz 3 baz modeli · Faz 4 özellikleri
**Çıktı:** Meta-model · ¼ Kelly staking · üretimdeki CLV kapısı

**Kapı:** Faz 4 kapısı + **kapının kendisi test edildi** (`/loop-kit:judge-selftest` —
kapıyı bilerek kır, kırmızı verdiğini kanıtla, geri al)

### Task başlıkları

1. İstifleme: Dixon-Coles + Elo + piyasa + Jev özellikleri üzerinde gradient boosting meta-model
2. Kesirli Kelly (¼), üst sınır, banka simülasyonu
3. EV eşiği ve "value" rozeti kararı
4. **CLV kapısı**: model değişikliği holdout CLV'yi bozuyorsa otomatik ret
5. **judge-selftest**: kapının gerçekten kırmızı verdiğini kanıtla
6. Kayıp otopsisi triyajı (Jev): model hatası / haber hatası / varyans

---

## Faz 6 — Web, pSEO, halka açık sicil

**Hedef:** Ürünü görünür kılmak ve **radikal şeffaflık** sözünü yerine getirmek.

**Girdi:** Faz 5 çıktıları · Faz 0 defteri
**Çıktı:** Next.js · Netlify · maç sayfaları · kamuya açık CLV/ROI sicili

**Kapı:** Faz 5 kapısı + sayfa üretim doğruluğu + **sicil sayfasının defterle birebir uyuşması**

### Task başlıkları

1. Next.js iskeleti + Supabase okuma katmanı
2. Maç sayfası şablonu (analiz + value rozeti, spec §1.1 katmanlı model)
3. **Halka açık sicil sayfası**: her tahmin zaman damgalı, CLV hesaplı, zincir başı doğrulanabilir
4. Programatik SEO: lig/takım/maç kırılımı, çok dilli hreflang
5. Schema.org işaretlemesi (SportsEvent, Organization)
6. 18+ kapısı, sorumlu bahis uyarıları, KVKK metinleri
7. Netlify deploy + Actions entegrasyonu

**Dikkat:** Sicil sayfası defterden türetilir, elle yazılmaz. Sayfa ile defter ayrışırsa
şeffaflık iddiası çöker — kapı bunu ölçmeli.

---

## Faz 7 — İçerik hattı

**Hedef:** Ölçeklenebilir, doğrulanmış içerik üretimi.

**Girdi:** Faz 4 Jev çıktıları · Faz 6 sayfa altyapısı
**Çıktı:** Maç başına analiz metni (katmanlı: şablon vs anlatı)

**Kapı:** Faz 6 kapısı + **Jev yayın öncesi doğrulama** (her olgusal iddia state'e karşı kontrol)

### Task başlıkları

1. Katmanlı içerik kararı: uzun kuyruk = şablon + Jev alanları, yüksek trafik = Sonnet 5 anlatısı
2. Sonnet 5 üretim hattı, maliyet tavanı ve toplu işleme
3. **Jev doğrulama geçidi**: uydurma istatistik yayına çıkamaz
4. Çok dilli üretim ve yerelleştirme
5. Trafik verisiyle eşik ayarı (hangi maç anlatı hak ediyor)

**Maliyet gerçeği:** 40 lig × ~10 maç/hafta ≈ ayda 1.600 sayfa. Hepsini LLM'e yazdırmak
pahalı; katmanlama tercih değil zorunluluk.

---

## Faz 8 — Büyüme / monetizasyon

Spec §1.3 gereği **kapsam dışı** tutuldu: kullanıcı hesabı, ödeme, affiliate yok.
Kullanıcı kararı: "önce para yok — önce kanıt" (3–6 ay). Bu faz, sicil birikip
kanıt oluştuktan sonra ayrıca planlanır.

---

## Faz geçiş kuralı

Bir fazdan diğerine geçmek için üçü birden gerekir:
1. Tüm task'lar kapıdan geçti,
2. Critical/high bulgu yok,
3. **Kapının neyi ÖLÇMEDİĞİ** handoff'ta adıyla yazıldı.

Üçüncüsü en çok atlanandır ve en pahalıya patlayandır: ölçülmediği yazılmamış bir boşluk,
sonraki fazda "zaten doğrulanmıştı" sanılarak üstüne inşa edilir.
