# Faz 2 — plan-zamanı ölçümleri ve verilen kararlar

**Tarih:** 2026-09-22 · **Durum:** beyin fırtınası (mimari yol) sürüyor; tasarım belgesi ve TDD
planı YAZILMADI · **Spec:** `2026-09-19-football-edge-design.md` · **Yol haritası:**
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
| Şartlar | `https://football-data.co.uk/disclaimer.php` ("All Rights Reserved") — içeriği OKUNMADI; lisans sorusu açık (spec §10/2) |

### 2.3 Canlı defter ve kapasite (Supabase, 2026-09-22)
Veritabanı 15 MB (ücretsiz sınır 500 MB). `odds_snapshots` 5.763 satır; **kapanışı mühürlenmiş maç 4**
(milli maç arası) → T7 (tarihsel ↔ canlı kapanış kalibrasyonu) haftalarca örtüşen veri ister.

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

## 5. Sonraki oturum — sıra
1. Tasarım belgesi (`docs/superpowers/specs/2026-09-2x-faz2-tarihsel-taban-design.md`): §3'ün
   kesinleşmesi + harness arayüzü, holdout kilidi (manifest + koddan zorlanan yasak), vig
   yöntemleri, piyasa verimliliği metriği, sızıntı denetimi, kapının yeni adımları, "kapının
   ölçmediği".
2. `notes.txt`in tamamını ve `disclaimer.php`yi runner'dan oku; `HxG/AxG` doluluğunu ölç.
3. Kullanıcıya yazılı tasarımı sun → onay → `superpowers:writing-plans` ile tam TDD planı → plan
   incelemesi (mimari: fable) → onay → dalga 1.
