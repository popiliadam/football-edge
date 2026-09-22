# Faz 2 — Tarihsel taban, backtest harness, piyasa verimliliği · Tasarım

**Tarih:** 2026-09-22 · **Durum:** kullanıcı onayı bekliyor (onay kapısı: bu belge onaylanmadan TDD
planı yazılmaz, plan onaylanmadan Faz 2 kodu yazılmaz) · **Spec:** `2026-09-19-football-edge-design.md`
· **Girdi:** `2026-09-22-faz2-olcumler-ve-kararlar.md` (bütün sayılar oradaki komutlarla ölçüldü) ·
**Yol haritası:** `../plans/2026-09-19-faz-1-7-yol-haritasi.md` (Faz 2 görevleri),
`../plans/2026-09-21-yol-haritasi-v2-paralel-izler.md` (sıra ve süreç)

Kullanıcı 2026-09-22'de tasarım kararlarını asistanın önerisine bıraktı; aşağıdaki her karar gerekçesi
ve yanlışsa bedeliyle yazılıdır. Tek istisna §14/1: spec'in holdout kullanımına dokunduğu için AYRICA
onay ister.

## 0. Özet

Faz 2, modeli ölçecek aracı model yazılmadan önce kurar ve hangi liglerde oynanacağına ölçümle karar
verir. Beş parça:

1. **Tarihsel taban** — football-data.co.uk'un CSV'leri runner'da çekilir (TR'den erişilemiyor),
   özel veritabanında ham dosya olarak önbelleğe alınır, kodla ayrıştırılır.
2. **Dönemler ve kilit** — geliştirme `< 2025-07-01`, holdout `[2025-07-01, 2026-07-01)`, sonrası
   `≥ 2026-07-01`. Geliştirme ve holdout satırlarının özetleri depoya kilitlenir; holdout satırları kayıt
   bırakan bir anahtar olmadan okunamaz. Faz 2 holdout'u HİÇ açmaz.
3. **Vig temizleme** — çarpımsal, power, Shin; saf fonksiyonlar.
4. **Backtest harness** — olay akışıyla yeniden oynatma; tahmin anında yalnız o andan ÖNCE bilinen
   görünür, sonuç ve kapanış tiple ayrılmış ayrı bir değerlendirme kaydındadır.
5. **Piyasa verimliliği** — lig başına, yalnız geliştirme döneminde: kapanışın kalibrasyonu, kapanış
   öncesi → kapanış bilgi kazancı, marj, keskin/ortalama farkı. Çıktı iki sıralama ve lig önerisidir.

Harness'ın doğruluğu, literatürde bilinen sonuçları yeniden üreterek (kapanış, kapanış öncesinden daha
isabetlidir; bilgisiz bahis pozitif CLV üretmez) haftalık bir iş akışında sınanır.

## 1. Kapsam

**Faz 2'nin görevleri** (eski yol haritasının numaralarıyla): T1 yükleyici · T2 harness · T3 vig ·
T4 piyasa verimliliği · T5 dondurulmuş holdout · T6 sızıntı denetimi · T7 tarihsel ↔ canlı kapanış.

**Kapsam dışı (YAGNI):**
- Model (Dixon-Coles, Elo katsayı fiti, harman) — Faz 3. Faz 2'de Elo yalnız iskelet katsayılarla
  bir taban çizgi stratejisidir.
- Jev özellikleri — Faz 4. Staking ve CLV kapısı — Faz 5.
- Asya handikabı marketi (çeyrek çizgiler yarım kazanç/kayıp ister) — sütunlar önbellekte durur,
  ölçülmez (§13).
- `HxG`/`AxG` özellik olarak — kaynağı belgesiz (§4.6).
- `xgabora/Club-Football-Match-Data` — bırakılır (D1).
- Canlı tahmin hattı — Faz 3–5; Faz 2 yalnız onun uyacağı arayüzü tanımlar (§7.4).

## 2. Girdiler (ölçülmüş)

Ayrıntı ölçüm belgesinde (§2.1–2.4, §4.1). Tasarımı bağlayanlar:

| Olgu | Değer |
|---|---|
| Erişim | football-data.co.uk Türkiye'den TLS reset (SNI); GitHub runner'dan tam erişim; kanonik adres kök alan adı (`www` → 302) |
| robots.txt | `User-agent: *` + boş `Disallow:` — her yol izinli, crawl-delay yok |
| Kapanış öncesi oranların toplandığı an | hafta sonu maçları cuma öğleden sonra, hafta içi maçları salı öğleden sonra (`notes.txt`) |
| `Time` | başlama saati; saat dilimi yazmıyor — İngiltere yerel saati ölçümle çıkarıldı |
| Kapanış tarihçesi | `PSC` 2012/13+ · `AvgC` `MaxC` `B365C` 2019/20+ · `BFEC` 2024/25+ · `PS*` 2026/27'de yok |
| `Time` doluluğu | ana liglerde 2019/20'den önce yok; ek liglerde %100 |
| Holdout | 22 ana lig 7.647 + 16 ek lig 4.446 = **12.093 maç**; ana liglerde `AvgC` %100, `PSC` %23–55 (Pinnacle API'si 2025-07-23'te kapandı) |
| Ek ligler | tek dosyada 2012→bugün, yalnız kapanış sütunları; geliştirme 57.601 maç |
| Lisans | `disclaimer.php` yalnız sorumluluk reddi; veri lisansı maddesi yok (spec §10/2 açık) |
| Canlı defter | kapanışı mühürlenmiş maç 4 (2026-09-22) — T7 haftalarca veri bekler |

## 3. Mimari

```
           GitHub runner (haftalık, pg_cron → workflow_dispatch)
football-data.co.uk ──► history/sync.py ──► hist_files (son sürüm, gzip)   ◄── özel Postgres
   (robots, 3 sn,        _guarded_get        hist_fetches (her çekme; append-only)
    dürüst kimlik)       doğrula                   │
                                                   ▼
                        history/football_data.py  (bayt → HistMatch; saf, dönem-bilinçli sütun haritası)
                                                   │
                        history/lock.py ◄── config/history_lock.yaml (dev + holdout satır özetleri)
                        history/holdout.py ── holdout_access_log (append-only) — anahtarsız holdout yok
                                                   │
                ┌──────────────────────────────────┼───────────────────────────────┐
                ▼                                  ▼                               ▼
       backtest/ (timeline, events,        market/efficiency.py            market/bridge.py (T7)
       harness, strategies)                (T4, yalnız dev)                canlı mühür ↔ AvgC
                │                                  │
       market/devig.py · market/metrics.py (saf, ortak)
                │
       docs/reports/*.md (yalnız toplu sayılar) · backtest-selftest.yml (K1–K4, haftalık, alarm)
```

Harness ve rapor üretimi `DATABASE_URL` olan her yerde koşar (Mac ya da runner): önbellek
veritabanında olduğu için TR engeli yalnız çekmeyi ilgilendirir.

## 4. Veri

### 4.1 Kaynak ve kayıt defteri (D1, D7, D20)

- **D1 — Birincil ve tek tarihsel kaynak football-data.co.uk.** xgabora bırakılır: football-data'dan
  türemiş (bağımsız bir çapraz doğrulama olamaz), kapanış oranı yok, ek ligleri 2024-12'de bitiyor ve
  kendine özgü sütunları (`HomeElo`, `C_*`, form) maç öncesi olduğu kanıtlanamadığı için özellik olarak
  zaten yasaktı. *Yanlışsa bedeli:* football-data'nın sonuçlarını bağımsız doğrulayan ikinci bir kaynak
  yok (§13).
- **D7 — Çekme runner'da.** `history-sync.yml` haftalık (pazartesi, pg_cron → `workflow_dispatch`,
  RUNBOOK §3 deseni) ve elle; ilk tam yükleme elle tetiklenir. İstek katmanı projenin `_guarded_get`i:
  robots her yolda sorulur, yönlendirmenin her sıçraması denetlenir, dürüst kimlik, istekler arası
  3 sn (robots bir değer vermiyor; 0b ölçümünün kullandığı nezaket aralığı). Kırmızı tur `ops-alert`
  açar, bekçi işin tazeliğini izler.
- **D20 — `config/sources.yaml`a `football-data` girer.** `base_url: https://football-data.co.uk`,
  `access_basis: robots`, robots anlık görüntüsü `config/robots/football-data.txt` (09-22 runner
  ölçümündeki 173 baytlık dosya). `declared_paths` gerçek CSV yollarıdır (R7) ve lig kataloğundan
  türetilir: bir test, `declared_paths` kümesinin kataloğun genişletmesine EŞİT olduğunu sınar
  (R59'un fetched ⊆ declared bağı böylece yapıdan gelir; `sources.py` değişmez). *Yanlışsa bedeli:*
  `sources.yaml`da ~500 satırlık bir liste; her yeni sezon için 22 satır elle eklenir, test eksik
  satırı adıyla söyler.

### 4.2 Lig kataloğu (D19)

`config/history_leagues.yaml`: football-data kodu → bizim lig kimliğimiz (`E0` → `eng.1`), ad, ülke,
kademe, dosya türü (`main`: sezon başına dosya, `extra`: tek dosya), sezon kapsamı, bilinen
`odds_api_key` (boş olabilir). 22 ana + 16 ek lig. Ana liglerde sezon aralığı **2005/06 → güncel**:
Elo'nun ısınması için 2012/13'ten (ilk keskin kapanış) önce yedi sezon. Canlı `config/leagues.yaml`
değişmez; Faz 2'nin çıktısı hangi ligin oraya terfi edeceğinin önerisidir (§8.4). *Yanlışsa bedeli:*
iki lig dosyası; eşleme kimlik üzerinden tek yönlü.

### 4.3 Depolama (D6)

Migration `0006_history.sql`:

| Tablo | İçerik | Kural |
|---|---|---|
| `hist_files` | `path` (PK), `sha256`, `fetched_at`, `http_last_modified`, `byte_size`, `row_count`, `content` (gzip bytea) | Yol başına SON sürüm; güncellenir |
| `hist_fetches` | `path`, `fetched_at`, `sha256`, `http_status`, `rows_parsed`, `rows_rejected` | append-only (0001'in tetikleyicisi) |

**D6 — `hist_files` bir önbellektir, kanıt değil.** Kanıt, çekme günlüğü (hangi an hangi özet) ile
depodaki kilittir (§5.2). Her sürümü saklamak ek liglerin haftada değişen tek dosyası yüzünden yılda
~130 MB eder (ücretsiz sınır 500 MB); son sürüm ~20 MB. Tekrarlanabilirlik dosya baytlarından değil,
kilitli dönemlerin satır özetlerinden gelir: football-data eski bir satırı düzeltirse kilit
doğrulaması kırmızı verir ve karar insana düşer. *Yanlışsa bedeli:* kilitli olmayan (sonrası) dönemin
eski sürümleri yeniden üretilemez — o dönem zaten değişkendir.

Ham üçüncü taraf içeriği yalnız bu özel tabloda durur: depo, log ve artifact ham satır taşımaz
(spec §3.2/4, Ruling 4). Testler gerçek başlıklarla SENTETİK satırlar kullanır.

### 4.4 Ayrıştırma

`history/football_data.py` saf bir fonksiyondur: `parse(content: bytes, *, league, kind) →
ParseResult(matches: tuple[HistMatch, ...], rejected: tuple[Rejected, ...], encoding)`.

- Kod çözme: `utf-8-sig`, olmazsa `latin-1` (hangisi olduğu sonuçta).
- Tarih `DD/MM/YY` ya da `DD/MM/YYYY` (ölçülen dosyalarda ikisi de var).
- Ana ve ek lig başlıkları farklıdır (`HomeTeam`/`Home`, `FTHG`/`HG`, `FTR`/`Res`); tek sütun haritası
  ikisini aynı kayda indirir.
- Oranlar `(kitap, market, sonuç, evre)` anahtarlı; `evre ∈ {kapanış_öncesi, kapanış}`. Boş hücre =
  yok. `1.0`'dan küçük ya da eşit oran reddedilir.
- `FTR`, goller ile tutarlı olmalı; aynı `(lig, tarih, ev, deplasman)` iki kez geçemez.
- **Kısmî kayıp sessiz geçemez (Ruling 6):** reddedilen her satır nedeniyle sayılır. Oransız satır
  (T1 2022/23'te %8) reddedilmez, oransız kayıt olarak geçer. Bir dosyada reddedilen SATIRLARIN
  payı %1'i aşarsa tur kırmızıdır. Dönem beklentisi: 2019/20 ve sonrası ana lig dosyasında `AvgCH` sütunu
  yoksa kırmızı (sütun tarihçesi §2).
- `HistMatch`: `league`, `season`, `date` (kaynağın tarihi), `kickoff` (UTC, saat yoksa `None`), `home`,
  `away`, `home_goals`, `away_goals`, `result`, `odds`, `stats` (şut, isabetli şut, korner, kart —
  varsa). Ham takım adı korunur; eşleme §9'da.

### 4.5 Zaman semantiği (D4, D5)

Sızıntının tamamı bu tabloya bağlıdır. Kurallar `backtest/timeline.py`de TEK yerde yaşar ve özellik
testleriyle sabitlenir.

| Veri | Ne zaman bilinir | Dayanak |
|---|---|---|
| Kapanış öncesi oranlar | **karar anı** — maç cuma, cumartesi, pazar ya da pazartesi ise o tarihte ya da öncesindeki son **cuma**; salı, çarşamba ya da perşembe ise son **salı**; saat **12:00 Europe/London** | `notes.txt` ("Friday/Tuesday afternoons") |
| Kapanış oranları | başlama anı | `notes.txt` ("closing") |
| Sonuç ve maç istatistiği | başlama + 3 saat; saat yoksa ertesi gün 03:00 Europe/London | kural (tutucu) |
| `HxG`/`AxG` | sonuçla aynı — Faz 2'de kullanılmaz | belgesiz |

- **D4 — karar anı neden 12:00:** öğleden sonranın EN ERKEN anı. Özellikler karar anından önce bilinen
  veriyle sınırlanır; fiyat gerçekte 16:00'da toplanmışsa kural gereğinden sıkıdır (güvenli), 12:00'dan
  önce toplanmış olamaz ("afternoon"). Karar anı başlama anına eşit ya da sonrasındaysa maçın karar
  noktası yoktur ve CLV'ye girmez (sayısı raporlanır).
- **Kural düzyazıdan çıkarıldı, ölçülmüş değil.** T2 onu dolaylı olarak sınar: karar anı ile başlama
  arasındaki süre uzadıkça kapanış öncesi → kapanış fiyat kayması büyümelidir (cuma→cuma akşamı <
  cuma→cumartesi < cuma→pazar < cuma→pazartesi). Tekdüze değilse kural şüphelidir ve rapor bunu söyler.
- **D5 — `Time` Europe/London yerel saatidir** (E0 15:00 başlamalarının yaz/kış saatinde kaymaması ve
  ek liglerin dağılımı; ölçüm belgesi §2.1–2.2). Dönüşüm `zoneinfo` ile, yaz saati geçişi dahil.
- Dönem üyeliği kaynağın `Date` sütunuyla belirlenir (saat dilimi dönüşümüne bağlı değil,
  deterministik).

### 4.6 `HxG`/`AxG` (D16)

2026/27'de 22 ana ligin 18'inde %100 dolu, footystats'ın altı ligi dahil. Ham dosyayla önbelleğe girer,
Faz 2'de hiçbir yerde kullanılmaz: `notes.txt` tanımını ve kaynağını vermiyor ve maç sonrası bir
büyüklük. Mac'teki footystats işini (DEFERRED 10r) emekliye ayırma adayıdır; bu ayrı bir karardır
(kaynak ve şartlar netleşince). *Yanlışsa bedeli:* yok; veri zaten önbellekte.

## 5. Dönemler, kilit ve holdout

### 5.1 Dönemler (K1 kararı, 09-22)

| Dönem | Tarih (`Date`) | Kullanım |
|---|---|---|
| geliştirme | `< 2025-07-01` | serbest: fit, doğrulama, lig sıralaması |
| holdout | `[2025-07-01, 2026-07-01)` | anahtarsız okunamaz; Faz 2'de açılmaz |
| sonrası | `≥ 2026-07-01` | değişken (her hafta büyür); T7 ve ileri-dönem ölçümü |

### 5.2 Kilit (D8)

- **Kanonik satır:** sabit, sıralı bir sütun listesinin KAYNAK METNİ (float'a çevrilmeden; biçimlendirme
  kayması olmasın), sekmeyle birleştirilmiş: lig, sezon, tarih, saat, ev, deplasman, goller, sonuç ve
  Faz 2'nin kullandığı oran sütunları. Sütun listesi sürümlüdür (`canonical_version`).
- **Özet:** her `(lig, dönem)` için satır sayısı ve kanonik satırların sıralı birleşiminin sha256'sı.
- `config/history_lock.yaml` (depoda, yalnız sayı ve özet — içerik değil): `canonical_version`,
  `locked_at`, dönem sınırları, lig başına `dev` ve `holdout` için `{rows, sha256}`. İlk tam yüklemeden
  sonra T1b üretir ve commit'ler.
- **Her yüklemede doğrulama:** harness geliştirme ve holdout özetlerini yeniden hesaplar; fark varsa
  `LockViolation` ile reddeder. Holdout özeti içeride hesaplanır, satırlar anahtarsız dışarı çıkmaz.
- **Kilidi güncellemek bir commit'tir** (ör. football-data eski bir skoru düzeltti): gerekçesi commit
  mesajında, eski özet git geçmişinde.

### 5.3 Holdout erişimi

- `open_holdout(conn, purpose) → HoldoutKey`: `holdout_access_log`a (append-only; migration
  `0007_holdout.sql`) açılış anı, git SHA'sı, amaç yazar ve anahtarı döner. Holdout satırları yalnız bu
  anahtarla yüklenir.
- Bir AST testi `open_holdout`ın yalnız izin verilen tek modülde (`backtest/final_eval.py`, Faz 3'te
  yazılır) çağrılabildiğini sınar — kural prose'da kalmaz.
- **Faz 2 holdout'u sıfır kez açar.** Faz 2 HANDOFF'u açılış sayısını yazar; sıfır değilse faz geçmez.

## 6. Vig temizleme (D9)

`market/devig.py`, saf fonksiyonlar. `q_i = 1/o_i`, `B = Σ q_i`:

| Yöntem | Tanım | Çözüm |
|---|---|---|
| çarpımsal | `p_i = q_i / B` | kapalı biçim |
| power | `p_i = q_i^k`, `Σ q_i^k = 1` | `k` üzerinde ikiye bölme |
| Shin | `p_i = (√(z² + 4(1−z)·q_i²/B) − z) / (2(1−z))`, `Σ p_i = 1` | `z ∈ [0, 0.5)` üzerinde ikiye bölme |

- scipy gerekmez: tek değişkenli, tekdüze kök bulma stdlib ile ikiye bölmedir (tolerans `1e-12`).
- Özellikler testlerle: toplam 1, sıra korunur, `B = 1` iken `p = q`, `z ≥ 0`, `k ≥ 1`; iki yollu
  (Ü/A) ve üç yollu (1X2) marketler; eksik ya da `≤ 1.0` fiyat reddedilir.
- **Varsayılan yöntem ölçümle seçilir:** geliştirme döneminde kapanış `AvgC`'nin log loss'u en düşük
  olan (beklenen: Shin ya da power, favori–sürpriz yanlılığı nedeniyle). Seçim verimlilik raporuna ve
  bir sabite yazılır; Faz 3 onu kullanır.

## 7. Backtest harness (D10, D11)

### 7.1 Olay akışı

Yeniden oynatma, zaman sırasına dizilmiş olaylardır:

| Olay | Zaman | Etki |
|---|---|---|
| `ResultKnown` | sonuç bilinme anı (§4.5) | durumu günceller (Elo, form) |
| `Decision` | karar anı | stratejiye bağlam verilir, tahmin DONDURULUR |

Aynı andaki olaylarda `Decision` önce gelir (tutucu: eşzamanlı sonuç görülmez). Kapanış oranları ve
maç sonucu olay akışına HİÇ girmez: değerlendirme kaydında durur ve yalnız bütün tahminler dondurulduktan
sonra birleştirilir.

### 7.2 Tiple ayrılmış iki kayıt

- `DecisionContext`: maç kimliği, lig, ev, deplasman, karar anı, maçın kendi kapanış öncesi fiyatları,
  durumun o anki görüntüsü (yalnız okuma: `results_before`, Elo reytingleri). Kapanış ve sonuç alanı
  YOKTUR — bir strateji onları isteyemez, çünkü tip onları taşımaz.
- `Outcome`: sonuç, goller, kapanış fiyatları. Yalnız değerlendirici görür.

### 7.3 Stratejiler (Faz 2)

| Strateji | Ne | Rolü |
|---|---|---|
| `MarketPre` | kapanış öncesi `Avg`'nin vig'i temizlenmiş olasılığı | piyasa taban çizgisi; K1'in bir yanı |
| `EloPointInTime` | olay akışının Elo'su (iskelet katsayılar) | model taban çizgisi; Faz 3 fit eder |
| `Placebo` | tohumlu rastgele sonuç seçip `Avg` kapanış öncesi fiyatından bahis | K4 negatif kontrolü |

Faz 3 bu arayüze Dixon-Coles'u ve harmanı takar.

### 7.4 Tek kod yolu (spec §6.3)

Stratejiler ve özellikler yalnız `DecisionContext`'e bağımlıdır. Faz 2 tek bir bağlam kurucusu yazar
(tarihsel); Faz 3 canlı kurucuyu (defter + gözlem deposu) yazar ve bir **eşitlik testi** ekler: aynı
maç için iki kurucu aynı bağlamı üretmeli. Bu, Faz 2'de arayüzle zorlanır, kanıtı Faz 3'tedir (§13).

### 7.5 Değerlendirme ölçütleri (`market/metrics.py`)

- İsabet: log loss, Brier, RPS (1X2 sıralı).
- Kalibrasyon: tek-karşı-hepsi havuzlanmış `y ~ a + b·logit(p)` lojistik yeniden kalibrasyonu (eğim
  `b`, kesişim `a`; numpy ile IRLS) ve 10 eşit kovalı ECE.
- CLV: fiyat `o` ile alınan bahis için `CLV = o · p_kapanış − 1`; `p_kapanış` seçilen yöntemle vig'i
  temizlenmiş `AvgC`.
- Güven aralığı: maç düzeyinde 2.000 tekrarlı yüzdelik bootstrap, sabit tohum.

## 8. Piyasa verimliliği (T4, D12)

### 8.1 Pencere

Yalnız geliştirme dönemi (holdout'a dokunmaz — lig seçimi holdout'u kirletmemeli).
- Ana ligler: 2019/20–2024/25 (kapanış öncesi `Avg` ve kapanış `AvgC` birlikte var, saat var).
- Ek ligler: 2012 → 2025-06 (yalnız kapanış).

### 8.2 Lig başına ölçütler

| Ölçüt | Tanım | Ligler |
|---|---|---|
| `N` | `AvgC` 1X2'si ve sonucu tam maç | hepsi |
| kapanış marjı | `B − 1`, `AvgC` 1X2 | hepsi |
| kapanış isabeti | log loss, Brier, RPS | hepsi |
| kapanış kalibrasyonu | eğim `b` (+ %95 GA), ECE | hepsi |
| geç bilgi | `ΔLL = LL(kapanış öncesi Avg) − LL(kapanış AvgC)` (+ GA) | ana |
| en iyi fiyat değer sıklığı | bir sonucun `Max` kapanış öncesi fiyatı × adil kapanış olasılığı `> 1` olan maçların payı — **geriye dönük üst sınır, ulaşılabilir değil** | ana |
| keskinlik farkı | `LL(AvgC) − LL(PSC)` — iki sütunun birlikte en az %90 dolu olduğu sezonlarda (ana liglerde 2019/20–2024/25, ek liglerde 2012 → 2025-06) | hepsi |
| Ü/A 2.5 | marj, log loss, kalibrasyon eğimi (`AvgC>2.5`, `AvgC<2.5`) | ana |

### 8.3 Sıralama

Tek bir bileşik puan YOK (ağırlıklar keyfî olurdu). İki sıralama:
- **R1 geç bilgi** (`ΔLL`, ana ligler): büyükse bilgi kapanış öncesinden sonra geliyor — yerel dilde
  haberi erken yakalamanın (spec §2/1) değer bulabileceği yer.
- **R2 kapanış kalibrasyon hatası** (`|b − 1|` ve ECE, bütün ligler): kapanış bile yanlış
  kalibre ise model katkısı için yer var.

Güven aralıkları ayrışan gruplara göre üç kademe (A/B/C).

### 8.4 Lig önerisi (Faz 2'nin çıktısı)

Bir lig aday olur: geliştirme `N ≥ 1.000` · holdout'ta `AvgC` doluluğu `≥ %95` · The Odds API'de anahtarı
var (canlı CLV ölçülebilir; `/v4/sports` kredi harcamaz) · R1 ya da R2'de A veya B kademesi. Öneri Faz 2
HANDOFF'unda kullanıcıya sunulur; `config/leagues.yaml` kullanıcı onayıyla değişir.

Rapor `docs/reports/<üretim tarihi>-piyasa-verimliligi.md`: yalnız toplu sayılar ve aralıklar, ham
satır yok.

## 9. Tarihsel ↔ canlı kapanış köprüsü (T7)

- Kendi defterimizde mühürlenen maçlar (`odds_snapshots.is_closing`) ile football-data'nın sonrası
  dönemindeki aynı maçlar `(lig, tarih, ev, deplasman)` ile eşlenir. Takım adları: normalize edilmiş ad
  eşitliği + `config/history_aliases.yaml` (canlı altı lig için elle, küçük). Eşlenemeyen maç düşürülmez,
  sayılır ve raporlanır.
- Ölçü: sonuç başına `p_bizim − p_AvgC` (ikisi de aynı yöntemle vig'i temizlenmiş) ortalaması, RMS'si,
  eşleştirilmiş güven aralığı. Anlamlı bir sistematik fark çıkarsa doğrusal bir düzeltme ÖNERİLİR,
  uygulanmaz.
- Veri birikmeden sonuç anlamsızdır: 4 mühürlü maçla başlıyoruz; canlı altı lig haftada ~60 maç verir.
  Kod Faz 2'de yazılır, rapor her hafta yeniden üretilir; Faz 2 kapısı kodu ve o günkü `N` ile raporu
  ister, dar bir aralık istemez (§13).

## 10. Sızıntı denetimi (T6, D14)

**Yapısal korumalar (kod ve testle):**
1. Tip ayrımı (§7.2): bağlamda kapanış ve sonuç alanı yok.
2. Zaman kuralları tek modülde, özellik testleriyle: her `ResultKnown` başlamadan sonradır; her `Decision`
   başlamadan öncedir; eşzamanlılıkta karar önce.
3. Harness, bir kararın durumuna zamanı karar anına eşit ya da sonra olan bir olayın girdiğini görürse
   `LeakageError` fırlatır (savunma katmanı; olay sıralaması zaten bunu önler).
4. Kilit doğrulaması (§5.2) ve holdout anahtarı (§5.3).
5. Negatif kontrol: `Placebo`'nun ortalama CLV'si pozitif çıkamaz (K4).
6. `pytest -m leakage` işaretli testler kapıda kendi adımıyla koşar (§11).

**Kırmızı takım (T6):** dalga sonunda bir inceleme ajanı (fable) harness'ı ve bu belgeyi "bu
backtest'te ileriye bakma hatasını bul" göreviyle inceler. Bakacağı yerler: sezon düzeyinde
normalizasyonlar (tüm sezonun ortalaması gelecek bilgisidir), terfi eden takımın başlangıç reytingi,
çift maç satırları, saat dilimi ve yaz saati, karar anı kuralı, erteleme, holdout'un hiperparametre
seçimi yoluyla sızması. Bulgular normal düzeltme döngüsüne girer; rapor `docs/reports/`a.

## 11. Kapı ve zamanlanmış doğrulama (D13)

**`verify.sh` (CI, çevrimdışı):** yeni adım `sızıntı` — `pytest -m leakage`, `EXPECTED_MIN_LEAKAGE` ile
(veri-sözleşmesi adımının deseni: toplanan sayı `--collect-only` ile ölçülür, alt sınırın altındaysa
kırmızı). Sayı, işaretli testleri getiren dalga birleşirken ölçülüp yazılır. `verify.sh` ortak
dosyadır: yalnız dalga sonu birleştirmesinde değişir.

**`backtest-selftest.yml` (haftalık, `DATABASE_URL`li, kırmızı → `ops-alert`):** kilitli geliştirme
verisinde bilinen sonuçlar:

| # | Beklenen | Tür |
|---|---|---|
| K1 | Kapanış, kapanış öncesinden isabetli: havuzlanmış `ΔLL > 0` ve %95 GA sıfırı dışlar; ana liglerin en az 18/22'sinde `ΔLL > 0` | kapı |
| K2 | Shin ya da power, kapanışta çarpımsaldan düşük log loss (havuzlanmış) | rapor (yöntem seçimi; kapı değil) |
| K3 | İkisinin birlikte dolu olduğu geliştirme sezonlarında (§8.2) `PSC`, `AvgC`'den düşük log loss (havuzlanmış) — keskin kitap ortalamadan isabetli | kapı |
| K4 | `Placebo`'nun ortalama CLV'si negatif, GA'nın üst ucu sıfırın altında | kapı |

K1 ve K4, zaman semantiği ya da birleştirme bozulursa düşer (kapanış ile kapanış öncesi yer değiştirirse
K1, gelecek fiyat sızarsa K4). Bekçi bu iki yeni işin tazeliğini izler (`scripts/ops_alert.py` tetik
listesi — ortak dosya, dalga sonu).

## 12. Görevler, dalgalar, riskler

| Dalga | Görev | Yazdığı başlıca dosyalar | Kademe |
|---|---|---|---|
| 0 | Bağımlılık: `numpy` (tek controller commit'i) | `pyproject.toml`, `uv.lock` | — |
| 1 | **T1a** ayrıştırıcı + lig kataloğu | `history/football_data.py`, `history/catalog.py`, `config/history_leagues.yaml` | K2 |
| 1 | **T3** vig + ölçütler | `market/devig.py`, `market/metrics.py` | K1 |
| 1 | **T5** kilit + holdout | `history/lock.py`, `history/holdout.py`, `db/migrations/0007_holdout.sql` | K1 |
| 1 | **T2a** harness iskeleti (sentetik veri) | `backtest/timeline.py`, `backtest/events.py`, `backtest/harness.py`, `backtest/strategies.py` | K1 |
| 2 | **T1b** senkron + önbellek + ilk tam yükleme + kilit commit'i | `history/store.py`, `history/sync.py`, `0006_history.sql`, `history-sync.yml`, `sources.yaml`, robots anlık görüntüsü | K2 |
| 2 | **T7** köprü kodu (sentetik + ilk gerçek rapor) | `market/bridge.py`, `config/history_aliases.yaml` | K2 |
| 3 | **T4** verimlilik raporu (gerçek veri) | `market/efficiency.py`, `backtest/report.py`, `docs/reports/…` | K1 |
| 3 | **T2b** bütünleşik harness + K1–K4 + zamanlanmış iş | `backtest-selftest.yml`, harness'ın gerçek veri yolu | K1 |
| 4 | **T6** kırmızı takım + Faz 2 HANDOFF + lig önerisi | rapor, belgeler | K1 |

- Her dalgadan önce tek-yazar taraması; en çok 4 paralel implementer, her biri izole worktree'de.
- Dalga 1'in dört görevi dosya olarak ayrık. T2a, T3'le aynı dalgada koştuğu için vig'i ve ölçütleri
  ENJEKTE edilen fonksiyonlar olarak alır (sentetik testlerde basit bir yer tutucuyla); gerçek bağlantı
  T2b'de kurulur — iki paralel görev aynı fonksiyonu iki kez yazmaz.
- Ortak dosyalar (`verify.sh`, `pyproject.toml`/`uv.lock`,
  `sources.yaml`, `ops_alert.py`, pg_cron dispatch izin listesi) yalnız dalga 0'da ya da dalga sonu
  birleştirmesinde değişir.
- Migration'lar numarayla ayrılır (`0006` T1b, `0007` T5, pg_cron işi için `0008` dalga sonunda).
- Yeni modüller `collect.py`ye DOKUNMAZ (597/800 satır): kendi `__main__`leriyle çağrılır
  (`python -m football_edge.history sync`).
- Her iş: brief → implementer → bağımsız inceleme (kabuklu ajan; K1'de fable) → düzeltme → controller
  mutasyonu (`PYTHONDONTWRITEBYTECODE=1`) → her commit'ten sonra `verify.sh`'ın tamamı → `--no-ff` →
  taze klon kapısı → push.

**D15 — bağımlılık yalnız `numpy`.** pandas yok (mypy strict ile tipli kayıtlar; örtük NaN/tip
dönüşümleri sızıntı ve doğruluk riski), scipy yok (ikiye bölme yeter), statsmodels yok (iki parametreli
lojistik için IRLS). Faz 3 Dixon-Coles'un en çok olabilirlik fiti için scipy'ı kendi dalga 0'ında ekler.
*Yanlışsa bedeli:* birkaç yardımcı fonksiyon elle yazılır.

## 13. Kapının ÖLÇMEYECEKLERİ (şimdiden)

1. **Karar anı kuralı düzyazıdan çıkarıldı**; yalnız fiyat kayması–süre tekdüzeliğiyle dolaylı sınanır.
2. **`Time`'ın saat dilimi belgelenmemiş**; dağılımdan çıkarıldı.
3. **2019/20 öncesi ana lig satırlarında saat yok**: gün içi sıralama o dönemde yaklaşık (tutucu kural).
4. **`AvgC`'nin kitap kümesi zamanla değişiyor** ve satır başına yayımlanmıyor: referans sezonlar arası
   sabit bir büyüklük değildir.
5. **Holdout'ta `PSC` kullanılamaz** (%23–55, bayat); `BFEC` yalnız 2024/25'ten.
6. **Asya handikabı ölçülmüyor.**
7. **`HxG`/`AxG`'nin kaynağı bilinmiyor.**
8. **Lisans (spec §10/2) açık**: `disclaimer.php` bir veri lisansı içermiyor.
9. **Bootstrap maçları bağımsız sayar**; aynı haftanın maçları arasındaki ortak şoklar aralıkları
   olduğundan dar gösterebilir.
10. **Bilinen sonuçlar yönseldir** (K1–K4); yayımlanmış bir makalenin sayılarını birebir yeniden
    üretmez.
11. **Tek kod yolu Faz 2'de yalnız arayüzle zorlanır**; eşitlik kanıtı canlı kurucuyla Faz 3'te.
12. **football-data'nın sonuçlarını bağımsız doğrulayan kaynak yok** (xgabora bırakıldı; türevdir).
13. **T7'nin aralığı haftalarca geniş kalır** (4 mühürlü maçla başlıyor).
14. **Kilit tekrarlanabilirliği dönem satırlarını kapsar, dosya baytlarını değil** (D6).

## 14. Spec'e etkiler ve kullanıcı kararı isteyenler

1. **Holdout kullanım politikası — AYRICA onay ister.** Spec §5.2 özellik seçimini "dondurulmuş holdout
   üzerindeki marjinal CLV"ye, §6.2/3 her değişikliği "holdout üzerinde CLV"ye bağlıyor. Holdout'u her
   kararda kullanmak onu bir doğrulama kümesine çevirir ve p-hacking'e karşı tek korumayı harcar.
   **Öneri:** özellik seçimi ve günlük kapı geliştirme dönemi içinde ileri yürüyen doğrulamayla
   (walk-forward) yapılır; holdout yalnız faz kapılarında, önceden yazılmış karşılaştırmalarla ve
   `holdout_access_log`a kayıt düşerek açılır (Faz 3, 4, 5 — en çok üç kez); açılış sayısı her faz
   HANDOFF'unda yazılır. "Sonrası" dönemi (≥ 2026-07-01) dokunulmamış son ileri test olarak kalır.
2. Spec §7 "football-data apex'inin HTTPS dinleyicisi yok → daima `https://www.`" notu ESKİ: `www`
   kök alan adına 302 veriyor (ölçüm belgesi §2.2). Spec'te düzeltilir.
3. Spec §3.1 "Eğitim geçmişi = xgabora (MIT)" satırı D1 ile değişir; §10/2'nin sorusu artık doğrudan
   football-data içindir: ticari lansmandan önce avukat ve site sahibinden yazılı izin (§3.2.1
   "kaynaktan izin istemek").
4. Spec §5.3 "kendini onaran ayrıştırıcı": Scrapling'in yapısal yeniden bulması TFF'de sıfır doğru
   verdi ve gürültülü hatayı sessiz yanlışa çevirebildi (ölçüm belgesi §4.1). Kendini onarma yapılacaksa
   adaylar ANLAMLA doğrulanır (Faz 4, Jev) — bu belge bir şey değiştirmez, kaydı düşer.

## 15. Karar kaydı

| # | Karar | Bölüm |
|---|---|---|
| D1 | Tek tarihsel kaynak football-data; xgabora bırakılır | §4.1 |
| D2 | Dönemler kaynağın `Date`'ine göre; K1 holdout | §5.1 |
| D3 | Referans kapanış `AvgC`; `PSC` yalnız dev'de ikincil; `BFEC` varsa raporlanır | §7.5, §8 |
| D4 | Karar anı: cuma/salı 12:00 Europe/London | §4.5 |
| D5 | `Time` Europe/London; sonuç başlama + 3 sa | §4.5 |
| D6 | Ham dosya önbelleği son sürüm; kanıt = çekme günlüğü + kilit | §4.3 |
| D7 | Çekme runner'da, haftalık, `_guarded_get`, 3 sn | §4.1 |
| D8 | Satır düzeyi kilit + anahtarlı, kayıtlı holdout | §5 |
| D9 | Vig: çarpımsal, power, Shin; varsayılan ölçümle | §6 |
| D10 | Olay akışlı harness, tiple ayrılmış bağlam/sonuç | §7 |
| D11 | Ölçütler: LL, Brier, RPS, kalibrasyon, CLV, bootstrap | §7.5 |
| D12 | Verimlilik yalnız dev'de; iki sıralama, bileşik puan yok | §8 |
| D13 | K1–K4 haftalık iş akışında; `sızıntı` adımı `verify.sh`te | §11 |
| D14 | Yapısal sızıntı korumaları + fable kırmızı takımı | §10 |
| D15 | Bağımlılık yalnız numpy | §12 |
| D16 | `HxG`/`AxG` önbellekte, kullanılmaz | §4.6 |
| D17 | Scrapling benimsenmez (0c), R79/R80 geçerli | §14/4 |
| D18 | Lisans açık; özel depolama, türetilmiş sayı, ham yayın yok | §4.3, §14/3 |
| D19 | Ayrı lig kataloğu; `leagues.yaml` değişmez | §4.2 |
| D20 | `declared_paths` katalogdan, eşitlik testiyle | §4.1 |
