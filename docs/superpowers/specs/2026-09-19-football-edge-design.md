# Football Edge — Tasarım Dokümanı

- **Tarih:** 2026-09-19
- **Durum:** Onaylandı (mimari), uygulama planı bekliyor
- **Çalışma adı:** `football-edge` — marka adı ayrı karar (Faz 6)

## 0. Karar özeti

| Karar | Seçim | Onay |
|---|---|---|
| Mimari | **A — Piyasa-çapalı hibrit** | ✅ |
| Kapsam | Global, ~35-40 lig | ✅ |
| Lig seçimi | Ölçerek (piyasa verimliliği sıralaması) | ✅ |
| Canlı oran | The Odds API 20K planı, $30/ay | ✅ |
| Yığın | Python worker + Supabase + Next.js | ✅ |
| Çalışma yeri | GitHub Actions + Supabase cron (ücretsiz) | ✅ |
| Sicil | Radikal şeffaflık, append-only, kamuya açık CLV | ✅ |
| Gelir | Önce para yok — önce kanıt (3-6 ay) | ✅ |
| Faz yönetimi | `~/dev/football-edge` + GSD | ✅ |
| FotMob | **Kullanılmayacak** (ToS + train/serve sapması) | ✅ |

## 1. Ürün

### 1.1 Ne
Futbol maçları için, piyasa oranıyla model tahmini arasındaki **sapmayı** tespit eden ve bunu
doğrulanabilir bir sicille yayınlayan bir analiz sistemi. Her maç için bir analiz sayfası;
yalnız EV eşiğini geçenlere "value" işareti ve önerilen bahis oranı.

### 1.2 Kime
Global. İngilizce birincil; yerel dillerde programatik SEO ile büyüme (pt-BR, tr, pl, ja, ko, el).

### 1.3 Ne değil — kapsam dışı (YAGNI)
- Bahis kabul etmez, bahisçiye yönlendirmez, affiliate linki içermez (Faz 8'e kadar).
- Canlı (in-play) bahis yok. Yalnız maç öncesi.
- Kullanıcı hesabı / ödeme yok (Faz 8'e kadar).
- Mobil uygulama yok (web/PWA).
- Futbol dışı spor yok.

### 1.4 Başarı ölçütü
Tek kuzey yıldızı: **CLV (Closing Line Value)** — yayınlanan seçimin aldığı oranın,
kapanış konsensüs oranına göre üstünlüğü. Tutturma oranı ikincil ve tek başına
yanıltıcıdır (1.20 oranlarla %80 tutturup zarar edilebilir).

Referans kapanış — kaynağı döneme göre ayrılır:
- **Tarihsel backtest:** football-data.co.uk `AvgC*` + `BFEC*` sütunları.
- **Canlı:** kendi defterimizde mühürlenen kapanış anlık görüntüsü (The Odds API,
  28 kitabın konsensüsü + Betfair Exchange). Bu ikisi **aynı büyüklük değildir**;
  Faz 2'de örtüşen dönemde karşılaştırılıp sistematik fark ölçülecek ve düzeltilecek.
Pinnacle referans DEĞİLDİR — public API'si 2025-07-23'te kapandı, sonrasındaki
fiyatları sistematik olarak bayattır (kaynak: football-data.co.uk kendi notu +
`pinnacleapi/pinnacleapi-documentation` README).

## 2. Temel tez

Bookmaker oranı, piyasadaki tüm bilginin sıkıştırılmış hâlidir; vig çıkarıldığında
tek başına en iyi tahmindir. Dolayısıyla model **mutlak olasılık** değil, piyasadan
**sapma** üretir. Edge'in yaşadığı yer:

1. **Yerel dil × ince piyasa.** İngilizce dışı liglerin takım haberini yabancı kitaplar
   geç fiyatlar (Brezilya, Japonya, Kore, Türkiye, Yunanistan, Polonya).
2. **Yan marketler.** 1X2 piyasanın en verimli yeri. Toplam gol, KG, Asya handikabı,
   korner ve kart marketlerinde bookmaker efor ve marj profili farklıdır.
3. **Açılış oranları.** Piyasa henüz para görmeden yumuşaktır.

## 3. Veri mimarisi

### 3.1 Kaynak envanteri (2026-09-19 itibarıyla doğrulanmış)

| Katman | Kaynak | Kapsam | Lisans / robots |
|---|---|---|---|
| Eğitim geçmişi | `xgabora/Club-Football-Match-Data` | 38 lig, 238.858 maç, ClubElo + form birleşik | **MIT** |
| Tarihsel kapanış oranı | football-data.co.uk | 22 Avrupa + 16 dünya, 1993/94→, C-prefix kapanış + O/U + AH | Özel kullanım kısıtı — yalnız doğrulama/karşılaştırma için, **ticari türev veri tabanı DEĞİL** |
| Canlı + kapanış oranı | The Odds API ($30/ay) | 40+ futbol anahtarı, 28 AB kitabı + Betfair Exchange | Ticari hizmet; **"lisanslı" iddiası yok** — sitede böyle bir beyan yok |
| xG (6 lig) | Understat | EPL/LaLiga/Bundesliga/SerieA/Ligue1/RFPL, 2014/15→ | Kısıt yok. **JS render gerekir** (eski `var teamsData` deseni kalktı) |
| xG (TR + geniş) | FootyStats public sayfalar | 20 TR organizasyonu dahil | `ClaudeBot Crawl-delay: 1` — izinli |
| Baz istatistik + hakem | FBref (Opta sonrası) | 40+ ülke: şut, SoT, korner, kart, faul, **hakem**, seyirci | Cloudflare korumalı. **xG YOK** (2026-01-20'de Opta lisansı iptal) |
| Güç vekili | Transfermarkt piyasa değeri | Global | **robots.txt Faz 1'de doğrulanacak** |
| Reyting | ClubElo API (`api.clubelo.com`) | Tüm Avrupa, günlük, anahtarsız | Ücretsiz |
| Takım haberi | Google News RSS (`hl`/`gl` ile çok dilli) | Global | Lisanslı yüzey |
| Takım haberi (TR) | Ajansspor sitemap/news | 18 takım: sakat/cezalı/eksik + muhtemel 11 + sarı kart sayacı | Kısıt yok |
| Hakem + ceza (TR) | TFF `pageID=600`, `pageID=246` | Hakem/VAR ataması maç öncesi; PFDK kararları | robots.txt yok. **windows-1254** |
| Coğrafya | Wikidata + OSM | Stadyum koordinatı, kapasite, rakım | CC |
| Hava | Open-Meteo | Global, anahtarsız | Ücretsiz |
| Erken sinyal | DataForSEO trends (mevcut MCP) | Oyuncu adı arama sıçraması | Mevcut bakiye |

### 3.2 Kaynak seçim politikası

1. **robots.txt'i AI/otomatik erişime kapalı olan kaynak taranmaz.** Bu kaynaklara
   yalnız Google News RSS üzerinden, başlık düzeyinde bakılır.
2. **Erişim kontrolü aşılmaz.** 403 dönen kaynak (SofaScore) kullanılmaz.
3. **ToS'u otomatik erişimi yasaklayan kaynak kullanılmaz** (FotMob, bet365, Pinnacle).
4. **Ham içerik yeniden yayınlanmaz.** Kaynaklardan yalnız sayısal özellik türetilir.
5. Veri kaynağı hakkında sitede **lisans iddiasında bulunulmaz**.

### 3.3 Elenen kaynaklar ve gerekçeleri

| Kaynak | Gerekçe |
|---|---|
| **FotMob** | robots.txt `/api/*` yasak + ToS otomatik erişimi men ediyor. Ayrıca: üretimde besleyemeyeceğimiz veriyle kalibrasyon = train/serve sapması |
| **SofaScore** | Her isteğe 403 — erişim kontrolü aşmak gerekir |
| **Pinnacle (doğrudan ve reseller)** | Public API 2025-07-23'te kapandı; v3.3 şartları (Ara 2025) oranları adıyla sayıp CFAA'ya atıf yapıyor |
| **Betfair doğrudan** | Türkiye'den erişilemez; 7258 s.k. m.5 kapsamında risk. Exchange fiyatı The Odds API üzerinden geliyor |
| **Bookmaker JSON uçları** | bet365 ToS oranları adıyla yasaklıyor; tümü TR'den bloklu |
| **worldfootballR** | Arşivlendi (Eyl 2025), bakımı bırakıldı |
| **football-data.org** | Süper Lig Tier 3 — ücretsiz planda yok, ücretli ~$131 |

### 3.4 `leagues.yaml`
Lig eklemek **kod değil konfigürasyon** olmalıdır. Her lig için: kaynak anahtarları
(odds key, FootyStats slug, FBref comp id, ClubElo eşlemesi), dil/ülke kodu
(`hl`/`gl`), zaman dilimi, takım adı sözlüğü, aktiflik bayrağı.

## 4. Model mimarisi

1. **Baz güç:** Dixon-Coles (zaman sönümlü, düşük skor düzeltmeli) + ClubElo önseli.
   xG mevcut liglerde xG-ağırlıklı varyant.
2. **Piyasa harmanı:** vig temizlenmiş piyasa olasılığı ile model olasılığı
   logistic opinion pooling ile harmanlanır. Harman ağırlığı **lig başına fit edilir**
   (verimli liglerde piyasa ağırlığı yüksek olmalı — bunu veri söyler).
3. **Jev özellik katmanı:** §5. Özellikler **fit edilir**, elle katsayı verilmez.
4. **İstifleme:** Dixon-Coles + Elo + piyasa + özellikler üzerinde gradient boosting
   → meta-model. Tek modele bağımlılık kırılgandır.
5. **Bahis boyutu:** kesirli Kelly (¼), üst sınır, banka simülasyonu.

## 5. Jev / Opus / Sonnet iş bölümü

### 5.1 Kim ne yapar

| Katman | Görev | Gerekçe |
|---|---|---|
| **Kod** | Oran→olasılık, vig temizleme, Dixon-Coles, Kelly, tüm kontrol akışı | Deterministik, test edilebilir |
| **Jev** | Maç başına ~35 tipli yargı + boru hattı sağlamlığı (§5.3) | ~100ms, ~$0.0004/maç, kalibre olasılık |
| **Sonnet 5** | Yayına giden analiz metinleri (hacim) | Maliyet/kalite dengesi |
| **Opus 5** | Sızıntı avı (red team), haftalık otopsi, özellik keşif döngüsü, faz planlama | Pahalı, seyrek, muhakeme yoğun |

Haiku hiçbir katmanda kullanılmaz.

### 5.2 Soru bataryası — cömert sor, seçici tüket

| Katman | İçerik | Muamele |
|---|---|---|
| **T1 — Kapı** | `haber_bu_maca_ait`, `haber_guvenilirligi`, `kaynak_celiskisi` | Model özelliği değil **filtre**. Düşükse diğer cevaplar atılır |
| **T2 — Çekirdek** | Kadro/sakatlık etkisi (hücum/savunma ayrı), rotasyon riski, hava cezası | Modele girer, katsayı fit edilir |
| **T3 — Aday** | Motivasyon asimetrisi, hoca baskısı, derbi gerilimi, seyahat yükü, dead rubber | Ham saklanır; holdout'ta **marjinal CLV katkısı** ölçülür, ödemiyorsa düşer |
| **T4 — Spekülatif** | Soyunma odası, sözleşme krizi, taraftar baskısı, hakem tartışması | Yalnız kaydedilir, modele **girmez**. Veri birikince test edilir |

**Tasarım kuralı:** her yeni soru şu testi geçmeli — *"bunun cevabı tabloda zaten var mı?"*
Varsa sorulmaz. Eşanlamlı sorular eşdoğrusallık yaratır: bilgi eklemeden varyans şişirir.

**Sayısal disiplin:** ~35 soru sorulur, modele giren özellik sayısı **≤15**. Hangi 15
olduğuna dondurulmuş holdout üzerindeki marjinal CLV karar verir. Çoklu test için
Benjamini-Hochberg FDR düzeltmesi. Düşük `confidence` cevapları sıfırlanır.

**Neden cömert sormak güvenli:** ham cevaplar saklandığı sürece ağırlık/filtre değişimi
yeniden çıkarım gerektirmez. Bugün sorulmayan soru ise o maç için kalıcı olarak kayıptır.

### 5.3 Jev'in boru hattı rolleri (özellik çıkarımının ötesinde)

| Rol | Ne yapar | Neden kritik |
|---|---|---|
| Kendini onaran ayrıştırıcı | Kod aday blokları çıkarır, Jev `Choice` ile doğrusunu seçer | Ücretsiz kaynakların HTML'i garanti vermez; regex kırıldığında sistem **sessizce** boş veri üretir |
| Varlık eşleme | Takım/oyuncu adlarını kaynaklar arası eşler | **Sessiz join hatası bu projenin bir numaralı ölüm sebebi** |
| Kaynak çelişkisi hakemi | Çelişen haberlerde hangisinin güvenilir olduğunu yargılar | Ortalama almak yerine karar vermek |
| Haber kümeleme | Aynı olayın tekrarlarını birleştirir | Tekrarlar sinyali şişirir |
| Yayın öncesi doğrulama | Sonnet metnindeki olgusal iddiaları state'e karşı kontrol eder | Güven temelli üründe uydurma istatistik felakettir |
| Kayıp otopsisi triyajı | Kaybeden bahisleri sınıflar: model / haber / varyans | Opus'un haftalık incelemesine temiz girdi |

### 5.4 Çok dillilik
Jev'in Türkçe ve diğer dillerdeki doğruluğu **ölçülmemiştir**. Faz 1'e **dil kalibrasyon
testi** dahildir: dil başına ~100 elle etiketlenmiş haber, Jev cevaplarıyla karşılaştırma.
Ölçülmeden hiçbir dil üretime alınmaz.

## 6. Ölçüm ve kapı

### 6.1 Ölçülenler
- **CLV** — birincil. Yayın anındaki oran vs kapanış konsensüs oranı.
- **Kalibrasyon** — Brier skoru, log loss, olasılık kovasına göre güvenilirlik diyagramı.
- **ROI** — ikincil, varyansı yüksek.
- **Kapsam** — kaç maç işlendi, kaç kaynak tazeydi.

### 6.2 Kapı (bu projenin `qa-loop` kapısı)
1. Birim testler
2. Veri sözleşmesi kontrolleri (şema + tazelik iddiaları)
3. **Dondurulmuş holdout üzerinde CLV** — bozulursa değişiklik geri alınır
4. **Sızıntı kontrolü** — özellikler yalnız `observed_at < kickoff` veriden
5. Secret taraması

"Daha iyi göründü" geçerli gerekçe değildir. Kapı çıktısı dosyadan okunur, özeti değil.
Her faz handoff'unda **kapının neyi ölçmediği** açıkça yazılır.

### 6.3 Sızıntıya karşı yapısal önlemler
- Her satırda `observed_at`; append-only.
- Backtest ve canlı **aynı özellik kodunu** çağırır — iki ayrı yol yazılmaz.
- Sona kadar dokunulmayan dondurulmuş holdout dönemi.
- Her fazda Opus red-team denetimi: "bu backtest'te sızıntıyı bul".

## 7. Teknik yığın

- **Toplayıcılar + model:** Python (pandas, scipy, statsmodels)
- **Veri:** Supabase Postgres (append-only ledger + özellik deposu)
- **Zamanlama:** GitHub Actions (kritik, kaçırılamaz işler) + Supabase pg_cron
  - GitHub Actions runner'ları ABD/AB'de → football-data.co.uk'a TR SNI blokunu aşarak erişir
  - **Not:** runner konumu *erişim* sorununu çözer, *uyum* sorununu çözmez (bkz. Football Dataco v Sportradar, C-173/11)
- **Site:** Next.js · Netlify
- **Bilinen tuzaklar:**
  - football-data.co.uk apex'inin HTTPS dinleyicisi yok → daima `https://www.` ile doğrudan çek, yönlendirme izleme
  - TFF sayfaları `windows-1254`
  - Bazı RSS uçları 200 dönüp yanlış içerik verir → `content_type` + içerik doğrulaması zorunlu
  - Understat XHR uçları POST → `outward_action_gate` `net_post` olarak engeller, geliştirmede onay gerekir

## 8. Riskler ve panzehirler

| Risk | Panzehir |
|---|---|
| Backtest sızıntısı | §6.3 |
| Train/serve sapması | Tek özellik kodu; üretimde besleyemediğimiz kaynakla kalibre edilmez |
| p-hacking | Dondurulmuş holdout + FDR düzeltmesi |
| Sessiz kaynak arızası | Toplayıcı başına tazelik + şema iddiası; içerik doğrulaması |
| Aşırı bahis | ¼ Kelly, üst sınır, banka simülasyonu |
| Kaynak kırılganlığı | Jev kendini onaran ayrıştırıcı; kaynak başına devre kesici |
| Hukuki maruziyet | §3.2 politikası; ticari lansman öncesi avukat incelemesi |

## 9. Fazlar

| Faz | İçerik | Kapı |
|---|---|---|
| **0** | Supabase şeması + oran toplayıcı + **kapanış mühürleme** cron'u | Ledger append-only mı, kapanış yakalanıyor mu |
| **1** | Toplayıcılar (Understat, FootyStats, FBref, ClubElo, Google News çok dilli, TFF, Open-Meteo, Wikidata/OSM) + varlık eşleme + **dil kalibrasyon testi**. Lig kümesi bu fazda **geçici ve geniştir** — ücretsiz kaynakların kapsadığı her lig alınır; budama Faz 2'de ölçümle yapılır | Şema + tazelik iddiaları; dil doğruluğu ölçüldü mü |
| **2** | Tarihsel taban (MIT CSV) + backtest harness + **piyasa verimliliği sıralaması** (lig seçimi burada yapılır) + Opus sızıntı denetimi | Sızıntı yok mu |
| **3** | Baz model: Dixon-Coles + Elo + piyasa harmanı (Jev'siz baz çizgi) | Holdout CLV baz çizgisi |
| **4** | Jev sinyal katmanı + özellik deposu + budama | Baz çizgiye karşı marjinal CLV |
| **5** | İstifleme + staking + **CLV kapısı** üretime alınır | Kapı kendisi test edilir (judge-selftest) |
| **6** | Next.js + pSEO maç sayfaları + halka açık sicil | Sayfa üretimi + sicil doğruluğu |
| **7** | İçerik hattı (Sonnet 5, katmanlı: şablon vs anlatı) | Jev yayın öncesi doğrulama |
| **8** | Büyüme / monetizasyon | — |

Her faz sonunda `HANDOFF.md`: ne bitti · kapı ne ölçtü · **kapının ölçmediği ne** ·
sonraki fazın ön koşulları · açık sorular.

## 10. Açık sorular

1. **İddaa boşluğu.** TR kullanıcısı yalnız İddaa'da oynayabiliyor ve İddaa marjı
   Avrupa ortalamasının üstünde — Avrupa konsensüsüne göre bulunan value orada value
   olmayabilir. Global kapsamda önceliği düştü ama TR trafiği için çözülmeli.
   Nesine ToS §4.2.1 ticari kullanımı yasaklıyor → veri kaynağı hukuki soru.
2. **Lisans zinciri: MIT CSV'nin kaynağı.** `xgabora/Club-Football-Match-Data` MIT
   ilan ediyor ama verisi büyük ölçüde football-data.co.uk'tan türetilmiş; o kaynağın
   lisansı ticari/otomatik türev ürünleri dışlıyor. MIT yeniden lisanslaması bu zinciri
   temizler mi — **ticari lansman öncesi avukata sorulacak.** Şimdilik: eğitim verisi
   olarak kullanılır, ham satırları yeniden yayınlanmaz.
3. **Transfermarkt robots.txt** doğrulanmadı (Faz 1).
4. **Jev'in çok dilli doğruluğu** ölçülmedi (Faz 1).
5. **Highlightly** $9.49 planında oran var mı — teyit alınmadı. The Odds API $30 seçildiği
   için kritik değil, yedek olarak kalsın.
6. **API-Football ücretsiz katman sezon aralığı** (2022-2024 iddiası birincil kaynaktan
   doğrulanmadı). Kullanmıyoruz; kayıt amaçlı.
