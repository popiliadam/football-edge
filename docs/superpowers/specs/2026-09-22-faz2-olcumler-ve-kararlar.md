# Faz 2 — plan-zamanı ölçümleri ve verilen kararlar

**Tarih:** 2026-09-22 · **Durum:** ölçümler tamam (§2.4 ve §4.1 oturum 3'te eklendi); tasarım belgesi
`2026-09-22-faz2-tarihsel-taban-design.md` ONAYLANDI (2026-09-22); TDD planı yazıldı, onay bekliyor · **Spec:** `2026-09-19-football-edge-design.md` · **Yol haritası:**
`../plans/2026-09-19-faz-1-7-yol-haritasi.md` (Faz 2), `../plans/2026-09-21-yol-haritasi-v2-paralel-izler.md`

Bu belge tasarımın girdisidir, yerine geçmez. Her sayı aşağıda yazan komutla ölçüldü; ölçülmeyen
şey "ölçülmedi" diye yazılıdır.

## 1. Kullanıcı kararları

- **Karar yetkisi:** kullanıcı (2026-09-22) "senin önerine göre en iyi senaryo ne ise o şekilde
  olsun" dedi — tasarım kararları gerekçesiyle asistanın önerisine göre verilir. Onay kapısı
  sürer: Faz 2 KODU, yazılı tasarım + plan kullanıcıya sunulup onaylanmadan yazılmaz.
- **K1 — Dondurulmuş holdout:** başlama tarihi `[2025-07-01, 2026-07-01)` aralığındaki BÜTÜN
  maçlar (lig sezonu tanımından bağımsız; takvim yılı ligleri de tarihle bölünür). Geliştirme
  `< 2025-07-01`; `≥ 2026-07-01` "sonrası" — holdout kilitlenince ikinci bir ileri-dönem ölçümü
  ve canlı kalibrasyon (T7) için ayrılır. Gerekçe: en yeni tam sezon, piyasanın bugünkü
  verimliliğini en iyi temsil eder.

## 2. Ölçümler

### 2.1 `xgabora/Club-Football-Match-Data` — commit `25882a58a736daf7ece3781940eac17ae1117a66` (2026-09-06)
Yöntem: iki CSV ham GitHub'dan geçici dizine indirildi (depoya girmedi), stdlib `csv` ile sayıldı.

| Ölçüm | Değer |
|---|---|
| `Matches.csv` | 238.858 maç · 48 sütun · 38 lig · 2000-07-28 → 2026-09-03 |
| Dönem (K1) | geliştirme 230.557 · **holdout 7.647** · sonrası 654 |
| **Ek 16 lig** (ARG AUT BRA CHN DEN FIN IRL JAP MEX NOR POL ROM RUS SUI SWE USA) | **2024-12'de bitiyor → holdout'ta 0 maç** |
| Ana 22 lig (B1 D1 D2 E0–E3 EC F1 F2 G1 I1 I2 N1 P1 SC0–SC3 SP1 SP2 T1) | holdout'ta Bet365 1X2, Max 1X2, O/U 2.5 %100 dolu (EC %98) |
| Kapanış oranı | **YOK** — yalnız Bet365 (`Odd*`) ve `Max*` (kapanış öncesi) |
| `MatchTime` | %55 boş; **Europe/London yerel saati**: E0 15:00 başlangıçları yaz/kış saati dönemlerinde 395/403 (saat kaymıyor) |
| `HomeElo/AwayElo` | %37 boş; 2025-06-15 sonrası yazarın "provisional continuation"ı |
| `C_*` küme olasılıkları | 112.602 satır dolu; `C_VHD` ortalaması sonuca göre H/D/A 0,148/0,147/0,144 (belirgin sızıntı imzası YOK) — tanımı belgelenmemiş, README "yeniden hesaplanacak" diyor |

### 2.2 football-data.co.uk — runner'dan (Actions 35721490238, 35721633258, 35721743106)
Türkiye'den TLS `Connection reset by peer` (SNI; `robots.txt` bile; WebFetch de `ECONNRESET`).
Ölçüm tek kullanımlık bir dalda, projenin dürüst kimliğiyle, robots `protego` ile sorularak yapıldı;
loga ham satır basılmadı. Dal silindi, tur logları Actions'ta.

| Ölçüm | Değer |
|---|---|
| Kanonik adres | **`https://football-data.co.uk`** — `www` (http ve https) 302 → kök. Spec §7'nin "daima `https://www.`" notu ESKİDİ |
| `robots.txt` | `User-agent: *` · `Disallow:` (boş) → her yol izinli |
| `notes.txt` (Last-Modified 2026-07-31) | "These are for pre-closing odds. For the closing odds, as below but with an additional "C"" · "Time = Time of match kick off" |
| Ana lig 2025/26 (`/mmz4281/2526/E0.csv`) | 132 sütun · 380 maç · 15/08/2025 → 24/05/2026 · tarih `DD/MM/YYYY` |
| Kapanış doluluğu (E0 / T1) | `AvgC*` `MaxC*` `B365C*` `BWC*` %100 · `BFEC*` (Betfair Exchange) %94 · `PSC*` (Pinnacle) %55 / %44 · O/U 2.5 ve AH kapanışı aynı düzen |
| Ana lig 2026/27 (`/mmz4281/2627/E0.csv`) | 114 sütun · 50 maç (→ 20/09/2026) · **yeni `HxG`, `AxG` sütunları** (doluluk ÖLÇÜLMEDİ) |
| Ek ligler (`/new/BRA.csv`, `/new/JPN.csv`) | 25 sütun: Country, League, Season, Date, Time, Home, Away, HG, AG, Res + YALNIZ kapanış (`PSC*` `MaxC*` `AvgC*` `BFEC*` `B365C*` …); BRA 5.597 maç 2012 → 20/09/2026, JPN 4.603 |
| Saat | ana ve ek liglerde başlama saati dağılımı İngiltere saatiyle tutarlı (BRA 00–02 ve 19–23, JPN 04–11) |
| Şartlar | `https://football-data.co.uk/disclaimer.php` — §2.4'te OKUNDU: yalnız sorumluluk reddi, veri lisansı maddesi yok; lisans sorusu açık (spec §10/2) |

### 2.4 football-data.co.uk — ikinci runner ölçümü (Actions 35726122375, oturum 3)
Yöntem: tek kullanımlık dal (`olcum/football-data-2`, ölçümden sonra silindi), dürüst kimlik, robots
`protego` ile, istekler arası 3 sn. Loga yalnız toplu sayılar basıldı. `notes.txt` ve `disclaimer.php`
runner'da açık anahtarla (CMS, AES-256) şifrelenip artifact oldu, yerelde açılıp TAMAMI okundu. Depoya
girmediler.

| Ölçüm | Değer |
|---|---|
| Kapanış öncesi oranların toplandığı an (`notes.txt`) | Hafta sonu maçları **cuma öğleden sonra**, hafta içi maçları **salı öğleden sonra** |
| `Time` (`notes.txt`) | "Time of match kick off" — **saat dilimi yazmıyor**. İngiltere yerel saati §2.1–2.2'deki dağılımdan çıkarıldı, belgeden değil |
| `HxG`/`AxG` | `notes.txt`te **tanımı ve kaynağı yok** (belge 2026-07-31 tarihli) |
| Kaynak teşekkürü (`notes.txt`) | Sonuçlar XScores; istatistik BBC, Flashscore vd.; oranlar Betbrain, Oddsportal, tek tek bahisçiler |
| `disclaimer.php` | Yalnız sorumluluk reddi: doğruluk garanti edilmez, tavsiye değildir, bahsin yasak olduğu yerde site yalnız bilgi amaçlı kullanılır, 18+. **Veri lisansı, çoğaltma ya da ticari kullanım maddesi YOK** (ham HTML'de de "rights reserved/copyright/licence" geçmiyor) |
| Kapanış sütunlarının tarihçesi (E0 0506→2627; T1, SC3, G1 yoklaması aynı) | `PSC*` 2012/13'ten · `AvgC*` `MaxC*` `B365C*` 2019/20'den · `BFEC*` 2024/25'ten · 2026/27'de `PS*` sütunları tamamen yok |
| Kapanış öncesi sütunlar | `BbAv*` `BbMx*` 2005/06–2018/19 · `Avg*` `Max*` 2019/20'den · `PS*` 2012/13–2025/26 · `B365*` hep |
| `Time` doluluğu | Ana liglerde 2019/20'den önce sütun YOK, sonra %100 · ek liglerde %100 |
| Tarih biçimi | 2 haneli yıl 2005/06–2014/15 ve 2016/17, 4 haneli 2015/16 ve 2017/18'den; çözülemeyen tarih 0 |
| Holdout (2025/26) — 22 ana lig | **7.647 maç** (xgabora'nın holdout sayısıyla birebir). `AvgC` `MaxC` `B365C` %100 · `BFEC` %92–98 · `PSC` %23–55 · kapanış öncesi `Avg` %98–100 |
| Holdout — 16 ek lig | **4.446 maç**. `AvgC` %100 (RUS %67 — dosya 19 sütun, `BFEC` yok) · `PSC` %26–94 · `BFEC` %85–100 |
| Geliştirme — ek ligler | 57.601 maç (2012 → 2025-06), yalnız kapanış sütunları |
| 2026/27 `HxG`/`AxG` | 22 ana ligin **18'inde %100 dolu** (EC, SC1, SC2, SC3'te sütun yok) — footystats'ın altı ligi (E0, SP1, I1, D1, F1, T1) dahil |
| Ek lig dosya adları | ARG AUT BRA CHN **DNK** FIN IRL JPN MEX NOR POL **ROU** RUS SWE **SWZ** USA |
| Eksik oranlı satırlar | T1 2022/23: kapanış ve öncesi %92 (maçların %8'i oransız) — yükleyici oransız satırı saymalı, düşürmemeli |

### 2.5 The Odds API futbol anahtarları — `/v4/sports?all=true` (oturum 3, 0 kredi)
`x-requests-last: 0` (uç kredi harcamaz); 67 futbol anahtarı. football-data kataloğuyla eşleşme:
- **Ana ligler (18/22):** E0 `soccer_epl` · E1 `soccer_efl_champ` · E2 `soccer_england_league1` · E3
  `soccer_england_league2` · SC0 `soccer_spl` · D1 `soccer_germany_bundesliga` · D2 `soccer_germany_bundesliga2` ·
  I1 `soccer_italy_serie_a` · I2 `soccer_italy_serie_b` · SP1 `soccer_spain_la_liga` · SP2
  `soccer_spain_segunda_division` · F1 `soccer_france_ligue_one` · F2 `soccer_france_ligue_two` · N1
  `soccer_netherlands_eredivisie` · B1 `soccer_belgium_first_div` · P1 `soccer_portugal_primeira_liga` · T1
  `soccer_turkey_super_league` · G1 `soccer_greece_super_league`. **Anahtarı YOK:** EC, SC1, SC2, SC3.
- **Ek ligler (15/16):** ARG `soccer_argentina_primera_division` · AUT `soccer_austria_bundesliga` · BRA
  `soccer_brazil_campeonato` · CHN `soccer_china_superleague` · DNK `soccer_denmark_superliga` · FIN
  `soccer_finland_veikkausliiga` · IRL `soccer_league_of_ireland` · JPN `soccer_japan_j_league` · MEX
  `soccer_mexico_ligamx` · NOR `soccer_norway_eliteserien` · POL `soccer_poland_ekstraklasa` · RUS
  `soccer_russia_premier_league` · SWE `soccer_sweden_allsvenskan` · SWZ `soccer_switzerland_superleague` · USA
  `soccer_usa_mls`. **Anahtarı YOK:** ROU. (CHN, JPN, POL, RUS ölçüm anında `active: false` — sezon arası ya da
  bahisçi yok; anahtar var.)

### 2.3 Canlı defter ve kapasite (Supabase, 2026-09-22)
Veritabanı 15 MB (ücretsiz sınır 500 MB). `odds_snapshots` 5.763 satır; **kapanışı mühürlenmiş maç 4**
(milli maç arası) → T7 (tarihsel ↔ canlı kapanış kalibrasyonu) haftalarca örtüşen veri ister.

### 2.6 İlk tam yükleme, satır genişliği ve `Date` takvimi (Task 8, oturum 4)

**İlk `--all` turu** (Actions 35765084910): 500 yol, 495 önbelleğe girdi, 5'i genişlik reddiyle düştü —
`0607/T1` 16/306, `0708/F2` 32/380, `0708/N1` 32/306, `0708/P1` 32/240, `0708/SP2` 16/462 (404 yok).
Biçim runner'da ölçüldü (Actions 35768752898; yerel ağ kaynağa ulaşamıyor — bağlantı sıfırlanıyor): 2007/08
dosyalarında başlık 58, bozuk satırların hepsi 61 geniş, **3 fazla hücre sonda ve boş**, son dolu hücre başlığın
içinde; bozuklar tek ardışık blok (1–2 hafta). T1 0607: başlık 55, 16 satır 63 geniş; 15'inin fazlası sonda ve
boş, **1 satırın başlık dışında dolu hücresi var**. Kısa satır yok. → **R111:** fazlası tamamen boş satır başlığa
kırpılır ve normal doğrulanır, sayısı dosya başına loglanır; dolu fazla ve kısa satır reddedilir. İkinci tur
(Actions 35770065873): beş dosya girdi (kırpılan 15/32/32/32/16); iki geçici `RemoteProtocolError`
(`2324/E0`, `2324/F2`) önceki sürümle önbellekte kaldı. Önbellek tam: 38 lig, dev + sonrası 214.723 satır.

**Kilit (Task 8 Step 13, `config/history_lock.yaml`).** Holdout ana ligler **7.646** (§2.4: 7.647), ek ligler
**4.446**; dev ek ligler **57.600** (§2.4: 57.601). İki fark da tek satır ve bulundu: `2526/F2` ve `/new/BRA.csv`
birer satırı **`gol çözülemedi`** ile reddediyor (skoru olmayan — oynanmamış/yarıda kalmış — maç); §2.4 ham satır
saymıştı. Tüm reddedilenler (6): `gol çözülemedi` ×4 (`2526/F2`, `BRA`, `1415/G1`, `1819/G1`), `Div` uyuşmazlığı ×1
(`1314/T1`, son satır), genişlik ×1 (`0607/T1`, R111). Holdout'ta ana liglerin AvgC 1X2'si %100, RUS %66,7.
`lock --write` tepe bellek (RSS) 756 MB, 9 sn; `lock --verify` exit 0.

**`Date` takvimi (R102).** Önbellekten, Londra saatiyle 00:00–05:59 başlayan satırların `Date` günü:

| lig | toplam | 06:00 öncesi | Paz | Cmt | Pzt | Per | Sal | Çar | Cum |
|---|---|---|---|---|---|---|---|---|---|
| USA | 5.736 | 4.371 | 2.624 | 227 | 459 | 876 | 27 | 72 | 86 |
| BRA | 5.155 | 1.294 | 305 | 25 | 62 | 511 | 146 | 40 | 205 |
| ARG | 5.876 | 1.828 | 405 | 376 | 374 | 70 | 401 | 101 | 101 |
| MEX | 4.398 | 3.386 | 1.428 | 805 | 480 | 268 | 50 | 167 | 188 |

Karar kuralı (plan Task 8 Step 10b): MLS maçları ağırlıkla cumartesi yerel akşamı; gece yarısından sonraki Londra
saatleri **pazar**a yığılıyor (2.624'e 227) → `Date` **Londra tarihidir, D5 doğru**; ek liglerde başlama anı
güvenilir. Ana liglerde (rakamlı 21 kod — `EC` sayıma girmedi; saatli 43.772 satır) 06:00 öncesi satır **0**.

## 3. Tasarım önerileri (taslak — tasarım belgesinde kesinleşecek)

1. **Birincil tarihsel kaynak football-data.co.uk (doğrudan).** xgabora onun türevi; kapanış oranı
   yok ve ek ligleri 2024-12'de bitiyor. xgabora yalnız çapraz doğrulama için kalabilir. Yol
   haritasının "T1 = MIT CSV yükleyici" varsayımı buna göre güncellenir.
2. **Yükleyici runner'da koşar** (TR engeli), ham satırı YALNIZ özel depoya (Supabase) yazar: public
   depo, log ve artifact ham veri taşımaz (spec §10/2, Ruling 4). Kaynak kayıt defterine
   `football-data` girer (`base_url` kök alan adı, `declared_paths` gerçek CSV yolları, robots
   anlık görüntüsü runner'dan alınır).
3. **Point-in-time Elo ve form kendi motorumuzdan** (`elo.py`, sonuçlardan); xgabora'nın Elo'su ve
   `C_*` sütunları özellik olarak YASAK (tanımı belgelenmemiş = maç öncesi olduğu kanıtlanamaz).
4. **`observed_at` semantiği:** kapanış = başlama anı; kapanış öncesi oranların toplandığı an
   `notes.txt`in tamamı okunarak yazılır (bu ölçümde grep'e girmedi — ÖLÇÜLMEDİ). Saat
   Europe/London → UTC.
5. **`HxG/AxG` (2026/27):** doluluk ölçülürse footystats'ın altı ligini runner'dan, maç başına
   kapsayabilir — Mac işine (DEFERRED 10r) bağımlılığı azaltma adayı; tarihsel xG değildir.
6. Bağımlılık: Shin ve power yöntemleri kök bulma ister (numpy/scipy); veri işleme için pandas ya
   da stdlib — tasarımda kararlaştırılır.

## 4. Kullanıcı önerisi — Scrapling (`D4Vinci/Scrapling`, 2026-09-22)
- **Aday:** "adaptive" seçiciler (sayfa şekli değişince öğeyi yeniden bulma) — spec §5.3 "kendini
  onaran ayrıştırıcı" hedefi ve TFF'nin 09-22 arızası (R72) aynı sınıf.
- **Kural (R77, spec §3.2.1 — kullanıcı onayıyla 09-22'de netleşti):** ayrıştırıcı (adaptive
  seçiciler) ve dürüst kimlikli tarayıcı fetcher'ı (JS çizimli sayfalar için) İZİNLİ.
  `StealthyFetcher` ve benzeri parmak izi taklidi / bot korumasını aşan parçalar YASAK.
  FootyStats'ın runner 403'ü bu yüzden aşılmadı (R73).
- **Öneri:** küçük bir spike — mevcut ayrıştırıcılardan biri (TFF) üzerinde, dürüst UA, robots kodla
  zorlanır, istek katmanı projenin `_guarded_get`i kalır; ölçüt: fixture'lardan türetilmiş şekil
  değişikliklerinde ayrıştırıcı kaybını sessiz geçirmeden yakalıyor mu.

### 4.1 Deneme sonucu (0c, oturum 3) — BENİMSENMEZ
Atılabilir deneme (dal `spike/scrapling-tff`, main'e girmedi), scrapling 0.4.15 YALNIZ taban paketi, ağ
yok, TFF fixture'ından programla türetilen 17 sayfa biçimi. Sonuç:
- Yeniden bulunan **1.979 öğenin hiçbiri doğru değil**. TFF sayfası neredeyse özdeş kardeşlerden kurulu
  bir ızgara: mutasyon, parmak izinin dayandığı özellikleri değiştiriyor, değişmeyen komşu (başlık satırı,
  deplasman hücresi) daha yüksek puan alıyor. Yanlış seçimlerin puanı (%77,6–91,4) doğru öğeninkiyle
  (%72,2–81,8) örtüşüyor: güvenli bir eşik yok.
- İki biçimde (ev hücresinin sınıfı ya da etiketi değişince) bugünkü ayrıştırıcının **gürültülü hatası
  62/62 sessiz yanlış gözleme** döndü (ev = deplasman ya da ev = hakem etiketi) — Ruling 6'nın en kötü sınıfı.
- Scrapling hiçbir biçimde istisna fırlatmadı; bütün gürültülü sonuçlar projenin kendi R72 sayım
  korumalarından geldi. DEFERRED 10s'yi (görevliler hücre dışına taşınırsa) kapatamaz.
- `auto_save` açıkken tek yanlış yeniden bulma, 9 parmak izinin 4'ünü başlık satırınınkiyle değiştirdi:
  depo zehirleniyor ve zehir kalıcı. Depo varsayılan olarak paketin içinde (SQLite) — runner'da her tur boş.
- Uyarlanabilir mod kapalıyken Scrapling ayrıştırıcısı bs4 ile birebir aynı sonucu veriyor: altı paket
  ekleyip işlevsel kazanç sıfır.
- Fetcher varsayılanları (kaynak okundu, koşulmadı): `Fetcher` Chrome TLS taklidi + Google referer'ı;
  `DynamicFetcher` HeadlessChrome UA'sını gerçek Chrome UA'sıyla değiştiriyor, `--enable-automation`ı
  düşürüyor (kapatılamıyor), Google referer'ı; `StealthyFetcher` bunların üstüne patchright ve tespit
  önleyici bayraklar. **Hiçbirinin varsayılan yolu dürüst kimlik taşımıyor** — R79 doğrulandı, R80 bütün
  fetcher tarafını yasakladı. JS çizimli sayfa gerekirse dürüst yol düz Playwright'tır.
  **R77b ile değişti (2026-09-23):** kullanıcı kararıyla Scrapling tam kullanılır (spec §3.2.1 R77b);
  R80 kapısı (`tests/test_access_method_rule.py`) fetcher'ları serbest bırakacak biçimde yeniden yazıldı —
  proxy, doğrulama çözme (`solve_cloudflare`), adı verilmiş bot User-Agent'ı ve tek geçit
  (`src/football_edge/scrape.py`) kırmızı kalır. Yukarıdaki ölçümler 0c'nin kaydı olarak durur.
- Spec §5.3 "kendini onaran ayrıştırıcı" yapıyla değil ANLAMLA (takım adı biçimi, `(H)` etiketi,
  ev ≠ deplasman) doğrulanan adaylar ister — Faz 4'ün Jev işi; Scrapling aday listesi döndüren bir API
  sunmuyor.

## 5. Sıra
1. ~~Tasarım belgesi~~ yazıldı: `2026-09-22-faz2-tarihsel-taban-design.md` (§3'ün önerileri orada
   kesinleşti; §3/1 D1, §3/4 D4, §3/5 D16, §3/6 D15).
2. ~~`notes.txt`, `disclaimer.php`, `HxG/AxG`~~ ölçüldü (§2.4).
3. Kullanıcıya yazılı tasarımı sun → onay → `superpowers:writing-plans` ile tam TDD planı → plan
   incelemesi (mimari: fable) → onay → dalga 1.
