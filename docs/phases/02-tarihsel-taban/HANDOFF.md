# Faz 2 — Tarihsel Taban, Backtest Harness, Piyasa Verimliliği · Devir Belgesi (HANDOFF)

**Tarih:** 2026-09-22 · **Dal:** `main` (her dalga `--no-ff` ile birleşti; son commit `450d95d`) · **Kapı:**
`./verify.sh` → `KAPI YEŞİL` (10 adım PASS + `zincir` adıyla SKIP; `DATABASE_URL` bağlıyken 11/11) ·
**Test:** 1530 passed / 2 skipped · **contract:** 18 · **leakage:** 265 (`EXPECTED_MIN_LEAKAGE=265`)

> **Bu belgenin en önemli bölümü §3'tür.** §2 kapının **ne ölçtüğünü**, §3 **ölçmediğini** yazar. Yeşil
> bir kapı yalnız §2'yi kanıtlar; §3'teki hiçbir satır "test edildi" sayılamaz.
>
> Faz 0 ve Faz 1'in belgeleri bir kez bayatladı. **Okuyan kişi §2'deki test sayısını ve §2.3'teki canlı
> sayıları `git log`, `config/history_lock.yaml` ve veritabanına karşı bir kez kontrol etsin.** Bu belge
> yazılırken kapı yeniden koşulmadı: sayılar yürütme defterinden (log dosyasından okunmuş koşular) ve
> commit'lerden alındı.
>
> Tasarım: `docs/superpowers/specs/2026-09-22-faz2-tarihsel-taban-design.md` (D1–D20; 2026-09-22 düzeltme
> notları R86, R98, R118, R120, 12j) · Plan: `docs/superpowers/plans/2026-09-22-faz2-tarihsel-taban.md`
> (başta "Düzeltme kaydı" D1–D4) · Ölçümler: `docs/superpowers/specs/2026-09-22-faz2-olcumler-ve-kararlar.md`
> (§2.4–2.6) · Raporlar: `docs/reports/2026-09-22-{piyasa-verimliligi,kapanis-koprusu,sizinti-denetimi}.md` ·
> Ertelenenler: `docs/DEFERRED.md` §11, §12, §14.

---

## 1. Ne bitti

Faz 2 = **modeli ölçecek aracı, model yazılmadan önce kurmak.** football-data.co.uk'tan 38 liglik, kilitli
bir tarihsel taban; sızıntıya yapısal olarak kapalı bir backtest harness'ı; vig temizleme, ölçütler, lig
başına piyasa verimliliği ve tarihsel ↔ canlı kapanış köprüsü; ve hangi liglerde oynanacağına ölçümle
verilmiş bir karar (§5). Model YOK: Elo iskelet katsayılarla koşuyor, Dixon-Coles Faz 3'tür.

### 1.1 Hazırlık (oturum 3, defter `.superpowers/sdd/2026-09-22-faz2-hazirlik/`, R78–R100)

| İş | Sonuç | Commit |
|---|---|---|
| 0a — R77 erişim kuralı testi | yasak araçlar import edilemez, kilide/kuruluma giremez; Scrapling fetcher tarafı yasak (R80), CAPTCHA/IP döndürme (R81) | merge `c3aedaa` |
| 0b — ikinci runner ölçümü | kapanış tarihçesi, holdout 12.093 maç, lisans maddesi yok (ölçüm §2.4) | depoya girmedi (dal silindi) |
| 0c — Scrapling denemesi | BENİMSENMEZ (1.979 yeniden bulmanın 0'ı doğru) | depoya girmedi |
| Tasarım | D1–D20, holdout politikası kullanıcı onaylı | `acdc6b5`, `5b3addd` |
| Plan | 13 görev; iki tur bağımsız plan incelemesi (planın kodu plan metninden tek ağaca kuruldu, ikinci turda her dalga ilk denemede yeşil) | `f1bf664` |

### 1.2 Yürütme (defter `.superpowers/sdd/2026-09-22-faz2-tarihsel-taban/`, R101–R121)

| Dalga | Görev | Ne | Dal commit'leri → merge |
|---|---|---|---|
| 0 | Task 0 | `history/types.py` (HistMatch, OddsKey), numpy 2.4.6, `leakage` işareti | `e521ed5` (controller) |
| 1 | Task 1 — ayrıştırıcı + katalog | `history/football_data.py`, `history/catalog.py`, `config/history_leagues.yaml` (38 lig); satır genişliği denetimi (Important 1), R103–R105 | `e215b27..be402bb` → `45a4881` |
| 1 | Task 2 — vig + ölçütler | `market/devig.py` (çarpımsal, power, Shin), `market/metrics.py` (LL, Brier, RPS, kalibrasyon IRLS, ECE, bootstrap) | `25cbf8e..1107099` → `438cd6a` |
| 1 | Task 3 — kilit + holdout | `history/lock.py`, `history/holdout.py`, `0007_holdout.sql`, AST erişim kuralı | `dcb639a..86ed2d8` → `b792704` |
| 1 | Task 4 — harness | `backtest/{timeline,events,harness,strategies}.py` (MarketPre, EloPointInTime, Placebo) | `8c88969..75cd4ed` → `f0edb37` |
| 1→2 | Task 5 — kapı | `verify.sh`'a `sızıntı` adımı (`EXPECTED_MIN_LEAKAGE=209`), 0007 canlı | `5f033fe` |
| 2 | Task 6 — senkron + önbellek | `history/{store,sync,__main__}.py`, `0006_history.sql` (+ TRUNCATE tetikleyicisi R110), `history.yml`, `sources.yaml` | `4e12380..39e85d6` → `5b6eb35` |
| 2 | Task 7 — köprü | `market/bridge.py`, `config/history_aliases.yaml` | `98fbe76..465679f` → `0a0bff5` |
| 2→3 | Task 8 — canlıya alma | sızıntı alt sınırı 221 (`729dd30`); 0008 pg_cron + bekçi + RUNBOOK §3.10 (`debfdfe`); R111 ayrıştırıcı düzeltmesi (`3893bde..f0ca398` → `b14f3e0`); kilit + 6 ad eşlemesi + ölçüm §2.6 (`a647f36`) | yukarıdaki |
| 3 | Task 9 — verimlilik + `market` CLI | `market/efficiency.py`, `market/__main__.py` (`efficiency`, `bridge`); R114–R116 | `9f32b75..be698ac` → `9470808` |
| 3 | Task 10 — bilinen sonuçlar | `backtest/{evaluate,selftest,__main__}.py`, `history.yml`'e "Bilinen sonuçlar" adımı (R84) | `fb72435..a427bee` → `104a27c` |
| 3→4 | kapı | sızıntı alt sınırı 241 | `0eeba46` |
| 4 | Task 12 Step 3 — varsayılan vig yöntemi | `DEFAULT_METHOD = POWER` (R118) | `bf26e94` → `aec668f` |
| 4 | Task 11 — kırmızı takım denetimi | Critical 0 · Important 2 · Minor 3; düzeltme F1 (R119) + F2 (R120) | `b345b06` → `6be8201`; alt sınır 265 `7ff6457`; rapor `dee3128` |
| 4 | Task 12 Step 1/1b/2 | verimlilik raporu, ilk köprü raporu, gerçek veride K1–K4 | `450d95d` |

Her görev: brief → implementer (izole worktree) → bağımsız inceleme (K1'de fable, K2'de opus; kabuklu
`general-purpose`) → düzeltme turu → kapsamlı yeniden inceleme → controller mutasyon kanıtı (`git archive`
kopyası, `PYTHONDONTWRITEBYTECODE=1`) → `--no-ff` → kapı. Sağ kalan mutantlar R101 ile küçük tek turda kapandı.
Test sayısı: 735 (plan commit'i) → 743 (dalga 0) → 1271 (dalga 1) → 1378 (Task 8) → 1506 (dalga 3) → **1530**.

---

## 2. Kapı ne ölçtü

### 2.1 Adımlar

`verify.sh` on adım + `zincir` koşar: `ruff-check` · `ruff-format` · `mypy` · `pytest` · `paket-kurulu` ·
`kaynak-politikası` · `veri-sözleşmesi` · **`sızıntı`** (Faz 2) · `dil-kalibrasyonu` · `secrets` · `zincir`
(yalnız `DATABASE_URL` varsa; yoksa ADIYLA SKIP).

| Koşu | Sonuç |
|---|---|
| `main` son ölçülen (Task 11 kapanışı: `6be8201` + `7ff6457` sonrası; `dee3128` ve `450d95d` yalnız belge/rapor) | 10 PASS + `zincir` SKIP · **1530 passed / 2 skipped** · contract 18 · **leakage 265** (`EXPECTED_MIN_LEAKAGE=265`, ölçülen 265/1532) · CI 35781161749 |
| `a647f36`, `DATABASE_URL` bağlı (yerel) | **11/11 PASS**, **1380 passed**, zincir SAĞLAM · CI 35773802471 |

**`2 skipped` ve `zincir` SKIP geçmek değildir:** ikisi de ulaşılabilir veritabanı ister (append-only tetikleyici
testleri). CI'da hiç koşmazlar; gerçek oldukları tek yer `DATABASE_URL` bağlı yerel kapıdır.

### 2.2 Faz 2'nin kapıya eklediği ölçümler ve kırmızı verebildiklerinin kanıtı

| Ne | Nerede | Ne ölçüyor | Kırmızı kanıtı |
|---|---|---|---|
| `sızıntı` adımı | `verify.sh` | `leakage` işaretli test sayısını `--collect-only` ile ölçer, alt sınırın altındaysa pytest'siz kırmızı; sonra işaretli testleri koşar | **Evet** (Task 5): m1 işaret silinir → "208 < 209" FAIL · m2 sabit 210 → FAIL · m3 iddia tersine → FAIL `pytest` + `sızıntı`; geri yükleme `cmp` birebir. Alt sınır her dalga sonunda yeniden ölçüldü: 209 → 221 → 241 → 265 |
| Holdout erişim kuralı (AST) | `tests/test_holdout_access_rule.py` | `open_holdout`, `_HOLDOUT_SEAL`, `_load_all` ve (R119) `load_files`, `parse_file`, `sync._parsed` yalnız izinli modüllerde | **Evet**: Task 3 controller 4/4 (dize sabiti `elo.py`ye yazılınca kırmızı); R119 mutant a–e; yeniden inceleme `import *`, `importlib`, izinli modül üzerinden erişim, yeniden ihraç, `getattr`/`attrgetter`/`fromlist` biçimlerini yakaladı. Sınırı §3/26–27 |
| Oracle kanaryası | `tests/test_harness.py` (`leakage`) | sonuç kullanan strateji dürüst harness'ta 0 tahmin (252 maç) | **Evet** (R120): `build_events` yaması (sonuçlar önce) → kırmızı; incelemeci: 10 sa ve üstü erken sızıntıda kırmızı, 9 sa'te yeşil (§3/28) |
| Zaman kuralı, tip ayrımı, `LeakageError` | `tests/test_{timeline,events,harness}.py` | karar < başlama < sonuç; eşzamanlılıkta karar önce; ters sıra → `LeakageError` | **Evet**: Task 4 23/23 + incelemecinin 3 sağ mutantı controller'da 4/4 kırmızı; Task 11 S1 (245.472 tarih×saat, DST dahil) 0 ihlal |
| Kilit | `tests/test_history_lock.py`, CLI'lar exit 9 | her dönem özetinin yeniden hesaplanması; bozuk kilit dosyası `LockViolation` (R99) | **Evet**: Task 3 45/45; Task 11 S3 — 16 mutasyonda Faz 2'nin kullandığı her sütun `LockViolation` |
| R77 erişim kuralı | `tests/test_access_method_rule.py` | yasak araçlar import/kilit/kurulum yolunda | **Evet**: 0a controller M1–M5 5/5 (boşlukları DEFERRED §11) |
| `kaynak-politikası` (Faz 1 adımı) | `config/sources.yaml` | football-data'nın 500 `declared_paths`i robots anlık görüntüsüne karşı; katalogla eşitlik `test_history_registry.py` | Mekanizma Faz 1 Task 3'te kanıtlı; football-data için ayrı mutasyon kaydı yok. Canlı: `sources-audit` 35765117646 "sapma yok: football-data" |

**Kapının DIŞINDA, runner'da koşan ölçümler** (`history.yml`, haftalık, `DATABASE_URL`li, kırmızı → `ops-alert`):

| Adım | Ne ölçüyor | Kırmızı kanıtı |
|---|---|---|
| `Senkron` | fail-closed senkron: başarısız yol ya da `REJECT_LIMIT` aşan ret → exit 7 | **Gerçek kırmızı**: ilk `--all` turu 35765084910 exit 7 → `🔴 history kırmızı` #2 açıldı; yeşil haftalık tur 35773953937 kapattı |
| `Bilinen sonuçlar` | K1, K3, K4 kapı; K2, D1 rapor (§2.4) | Task 10: 33/33 mutasyon + `low > 0` kuralı (A, B) sonradan sabitlendi. **Runner'da HENÜZ koşmadı** (§3/35) |
| Bekçi | `history.yml` 8 günden eski değil (`scripts/ops_alert.py` TRIGGERS, FRESH 7g23s) | Task 8: test önce kırmızı (2 failed); mutasyon 1–7 kırmızı |

### 2.3 Canlı ve doğrulanmış durum

| Şey | Değer | Nasıl doğrulandı |
|---|---|---|
| `0006_history` | `hist_files`, append-only `hist_fetches` + `hist_fetches_no_truncate`; RLS açık, politika 0 | Task 8 Step 2: canlıya uygulandı, tetikleyici ve RLS listesi okundu |
| `0007_holdout` | `holdout_access_log` append-only + `before truncate`; RLS açık, politika 0; `recorded_at` DB saati | Task 5 Step 2: `86ed2d8` hâli, diff 0 |
| `0008_history_dispatch` | `history-dispatch` `50 9 * * 2` (**salı 09:50 UTC**, R85), active | Task 8: `cron.job` sorgusu; diğer dört iş yerinde |
| **Holdout açılış sayısı** | **`holdout_access_log` = 0** | Task 12 Step 5: `select count(*)` → 0. Sınırı: R119'dan önce holdout anahtarsız da kurulabiliyordu (Task 11 F1; bu yolu kullanan kod yoktu, kural artık yasaklıyor) |
| İlk tam yükleme | tur 35765084910: 500 yol, 495 girdi, 5 genişlik reddi (404 yok) → R111 → tur 35770065873: 5 dosya girdi (kırpılan 15/32/32/32/16), 2 geçici `RemoteProtocolError` (`2324/E0`, `2324/F2` önceki sürümle önbellekte) | Actions logları; ölçüm §2.6 |
| Önbellek | 500 dosya, 38 lig; dev + sonrası 214.723 satır | Task 8 |
| Haftalık kip | tur 35773953937: 38 yol, 0 değişti, 0 başarısız, 1 ret; #2 kapandı | Actions logu |
| **Kilit** `config/history_lock.yaml` | `a647f36` · holdout **7.646 ana + 4.446 ek**; dev ek 57.600; holdout ana lig `AvgC` %100, RUS %66,7 · `lock --write` RSS 756 MB, 9 sn · `lock --verify` exit 0 | Task 8 Step 13; 7.647 beklentisinden fark bulundu (R112) |
| Reddedilen satırlar (6) | `gol çözülemedi` ×4 (`2526/F2`, `BRA`, `1415/G1`, `1819/G1`), `Div` uyuşmazlığı ×1 (`1314/T1` son satır), genişlik ×1 (`0607/T1`, R111) | `hist_fetches.rows_rejected` |
| `Date` takvimi (R102) | Londra tarihi: USA'da 06:00 öncesi 4.371 satırın 2.624'ü pazar, 227'si cumartesi; ana liglerde 06:00 öncesi 0 satır | Task 8 Step 10b, ölçüm §2.6 |
| Takım adı eşlemesi | 6 ad; canlı kapanış 4/4 eşleşti | Task 8 Step 12 |
| Yinelenen satır (F3) | (lig, tarih, ev, deplasman) 0 — 38 lig, DEV + sonrası | Task 12 ölçümü |
| **Bilinen sonuçlar, gerçek veri** (yöntem power) | selftest exit 0 · **K1** ΔLL 0.0036 [0.0029, 0.0043], 22/22 ana lig > 0 · **K2** çarpımsal 1.00248 · power 1.00188 · Shin 1.00195 → power · **K3** 0.0003 [0.0001, 0.0004], 348/348 lig-sezon · **K4** Placebo CLV −0.0713 [−0.0721, −0.0704] · **D1** tekdüze artan | Task 12 Step 2 (yerel, `--env-file .env`). Önizlemede (shin) süre 25 sn, RSS 766 MB, K1 n = 45.629 |
| **Piyasa verimliliği** | exit 0; 38 lig ölçüldü, ölçülemeyen yok; aday **32/38** (dışarıda: EC, SC1, SC2, SC3, ROU — Odds API anahtarı yok; RUS — holdout `AvgC` %66,7 < %95) | `docs/reports/2026-09-22-piyasa-verimliligi.md`; önizleme süresi 98 sn |
| **Kapanış köprüsü** | exit 0; **n = 4**, karşılaştırılamayan 0; ortalama fark (bizim − AvgC) H −0.0019 · D +0.0040 [+0.0025, +0.0056] · A −0.0021; RMS 0.0041 | `docs/reports/2026-09-22-kapanis-koprusu.md` (canlı mühürler 2026-09-19+) |
| Raporların içeriği | yalnız toplu sayı; tarih yalnız üretim damgası, takım adı yok | Task 12 Step 1 kontrolü |

---

## 3. Kapının ÖLÇMEDİKLERİ — burası "yeşil" sayılmaz

> Numaralar kararlı kalsın diye tasarım §13'ün (1–14) ve planın (15–24) numaraları korunur; yürütmenin
> eklediği maddeler 25'ten başlar.

### 3.1 Tasarım §13 (on dört madde — hepsi geçerli)

1. **Karar anı kuralı (salı/cuma 12:00 Londra) düzyazıdan çıkarıldı**; D1 yalnız dolaylı sınar (bugün tekdüze).
2. **`Time`'ın saat dilimi belgelenmemiş**, dağılımdan çıkarıldı. `Date`'in Londra tarihi olduğu R102 ile
   ölçüldü — ama yalnız dört ek ligde (madde 38).
3. **2019/20 öncesi ana lig satırlarında saat yok**: gün içi sıralama o dönemde yaklaşık.
4. **`AvgC`'nin kitap kümesi zamanla değişiyor**, satır başına yayımlanmıyor.
5. **Holdout'ta `PSC` kullanılamaz** (%23–55, bayat); `BFEC` yalnız 2024/25'ten.
6. **Asya handikabı ölçülmüyor.**
7. **`HxG`/`AxG`'nin kaynağı bilinmiyor.**
8. **Lisans (spec §10/2) açık**: `disclaimer.php` veri lisansı içermiyor.
9. **Bootstrap maçları bağımsız sayar** — aralıklar olduğundan dar olabilir.
10. **Bilinen sonuçlar yönseldir** (K1–K4); bir makalenin sayılarını yeniden üretmez.
11. **Tek kod yolu yalnız arayüzle zorlanır**; eşitlik kanıtı Faz 3'te — R98'den sonra bağlam VE `observe`
    akışı için.
12. **football-data'nın sonuçlarını bağımsız doğrulayan kaynak yok.**
13. **T7'nin aralığı haftalarca geniş kalır** — ölçüldü: n = 4 (madde 30).
14. **Kilit satırları kapsar, dosya baytlarını değil** (D6).

### 3.2 Planın eklediği (15–24) — yürütmede kapananlar işaretli

15. **Karar anı kuralının doğrulaması dolaylıdır** — açık (D1 çürütebilir, kanıtlayamaz).
16. ~~`load_matches`in belleği ölçülmedi~~ **KAPANDI:** `lock --write` tepe RSS **756 MB** (tahmin ~1,1 GB,
    eşik 2 GB); selftest önizlemesi 766 MB. Ucuz iyileştirme (demet) DEFERRED 12b'de.
17. ~~`first_season: "0506"` lig lig ölçülmedi~~ **KAPANDI:** ilk `--all` turunda **404 yok**.
18. **`current_season` elle ilerletilir** — açık; unutulursa yeni sezon çekilmez, yalnız köprünün `n`i büyümez.
19. **R77 kural testinin boşlukları** — açık (DEFERRED §11).
20. **Eski append-only tablolarda (0001–0005) TRUNCATE/RLS koruması yok** — açık (12a); 0006 (R110) ve 0007'de var.
21. **`open_holdout` bağlantıdaki bekleyen başka yazımları da commit'ler** — açık; yalnız Faz 3 `final_eval` çağırır.
22. **Köprü `n = 0` iken rapor yazmaz** (R93) — bu turda tetiklenmedi (n = 4).
23. **Kilit kanonik satırı ayrıştırılmış değerlerden** (R86) — kaynağın biçim değişikliği görünmez; tasarım
    §5.2 metni düzeltildi.
24. Plan yeniden incelemesinin gözlemleri: `_measure`in yakalama genişliği **KAPANDI** (R115 daralttı ve
    sabitledi) · `load_matches`in gerçek anahtarla pozitif yolu **açık** (Faz 3) · EKSİK kilit dosyası exit 1 +
    traceback — kapandığına dair kayıt yok, **açık** (DEFERRED 14j).

### 3.3 Yürütmenin eklediği

25. **Eşit genişlikli kayma ve R111 boş-kuyruk kayması.** Tırnaksız virgül + eksik hücre yalnız fiyat
    sütunlarındaysa satır başlık genişliğini tutar ve kaymış fiyatlar sessizce girer (CSV'ye içkin). R111'in
    kör noktası aynı sınıftan: son sütunları boş bir satırda tırnaksız `"2,5"` fazla BOŞ hücre üretir, kırpılır
    ve kabul edilir. Div, sezon penceresi ve gol/sonuç denetimleri yakalamazsa kilit bunu dondurur.
26. **Ayrıştırıcının özel yardımcıları AST kuralını atlar.** `_decode → _records → _context → _row` başka bir
    modülden dört özel adla çağrılırsa holdout satırı kurar (DEFERRED 14h).
27. **Hesaplanmış adlar.** `vars(holdout)` + `endswith("SEAL")` ile mühür bulunup sahte anahtar kurulur (Task 11
    F4, kabul); yansıma `HistMatch`e ulaşır (12h). AST kuralı kazara girişi durdurur, kasıtlı kaçışı değil —
    "stratejiler düşmanca kod değildir" varsayımı.
28. **Oracle kanaryasının eşiği ≥ 10 saat.** 1–9 saatlik erken sızıntıyı eski tam-an testleri yakalar; yalnız
    saatsiz maçlarda 1 saatlik sızıntıyı tek bir test (`test_events.py`) yakalar. 12:15 UTC iki yuva eşiği 4
    saate indirir (DEFERRED 14k).
29. **K4 fiyat sütunu negatif kontrolüdür, harness kontrolü değil** (R120). CLV sonuçtan bağımsızdır: CLV
    tabanlı HİÇBİR kapı sonuç sızıntısını göremez; sonuç sızıntısının ölçüsü log loss/Brier ve Oracle kanaryasıdır.
    K4'ün `detail`i bunu yazar.
30. **Canlı kapanış örneği küçük: n = 4.** Köprünün D farkı [+0.0025, +0.0056] sıfırı dışlıyor ama dört maç
    bir sistematik farkı ne kanıtlar ne çürütür; canlı altı lig haftada ~60 maç ekler.
31. **Yerel ağ football-data'ya ulaşamıyor** (DNS doğru, bağlantı sıfırlanıyor). Kaynak ölçümleri yalnız
    runner'da (R104 ölçümü geçici dal `measure/r104-width`); yerelde yalnız önbellek okunur.
32. **`DEFAULT_METHOD = power`, Shin'den yalnız ~7e-5 iyi ve aralıksız** (R118). Farklı bir ortak maç kümesi
    Shin'i seçebilir; yöntem seçimi örneklem içidir (geliştirme raporunun sayıları hafifçe iyimser).
33. **Kademe kuralı gevşek.** "A ya da B" = "iki sıralamanın ikisinde de C değil" (aralık–medyan
    karşılaştırması) → 38 ligin 32'si aday. Aday listesi bir ELEME değildir; öneri A kademesine dayandı (§5).
34. **latin-1 geri dönüşü dosya başına hep-ya-hiç** (12e, 14b): tek bozuk bayt bütün dosyanın adlarını bozar;
    senkron dosya başına kodlamayı loglamıyor (R109). Kilit dev/holdout'ta yakalar; sonrası dönem ve köprü sessiz.
35. **Selftest'in runner'daki haftalık turu hiç gözlenmedi.** Gerçek veride yerel süre 25 sn ölçüldü; ama
    `history.yml`'in "Bilinen sonuçlar" adımı runner'da ilk kez **salı 2026-09-29 09:50 UTC** turunda koşar
    (iş zaman aşımı 60 dk). R84 gereği senkron kırmızıysa o hafta selftest koşmaz.

Task 11 denetiminin açık kalanları (`docs/reports/2026-09-22-sizinti-denetimi.md`):

36. **Erteleme.** Kaynak yalnız OYNANAN tarihi verir; ertelenen maçın kapanış öncesi `Avg`'si ilk tarihten mi
    toplandı bilinmiyor. İlk tarihten ise strateji, fiyatın görmediği haftaların sonuçlarını görür (model lehine
    önyargı). Gerçek veride ölçülmedi.
37. **2019/20+ ana lig penceresinde saatsiz satır sayısı doğrudan ölçülmedi** (0 varsayıldı; saatli 43.772).
    Saatsiz bir cuma/salı maçında 12:00 kararı başlamadan sonra düşebilir.
38. **`Date`'in Londra tarihi olduğu yalnız USA/BRA/ARG/MEX'te ölçüldü**; JPN, CHN gibi diğer ek liglerde varsayım.
39. **Katalog kilitte değil.** `country` alanı Elo reyting grubudur (R94); değişirse ölçüm sessizce değişir.
    R94'ün "aynı ülkede aynı adı taşıyan iki kulüp yok" varsayımı da ölçülmedi.
40. **`load_matches` DEV + POST döner:** Faz 3 bu diziyi `replay`e verirse Elo holdout yılını atlayarak sonrası
    dönemine girer (durum boşluğu; sızıntı değil).
41. **Holdout meta verisi kasıtlı kullanılıyor:** aday seçimi kilitteki holdout `avgc_complete/rows` sayısını
    okur (tasarım §8.4) — satır değil sayı.
42. **`open_holdout`ın veritabanı yolu hiç koşulmadı** (Faz 2 holdout'u açmaz); tabloların tetikleyicileri
    canlıda doğrulandı, fonksiyonun commit sırası değil.
43. **İki yollu OvR kalibrasyonda kesişim simetriyle ≡ 0** (12j): Ü/A'da "kesişim ≈ 0" yanlılık yok demek değildir.

---

## 4. Verilen kararlar (Ruling listesi)

İki defterdeki bütün `Ruling` satırları, numara sırasıyla: **44 karar** (R78–R100 hazırlık, 23; R101–R121
yürütme, 21). Tam gerekçeler defterlerde — **o dizinler gitignored, yalnız bu makinede.** Biçim: karar — *yanlışsa
bedeli*.

1. **R78** 0a K2 sayılır, inceleme kabuklu `general-purpose` (opus) — *boşa yeşil kalan bir kural testi; controller mutasyonu karşılar.*
2. **R79** Kilit yasağı `scrapling[fetchers]`i dışarıda tutar; JS çizimli sayfa gerekirse düz Playwright — *ileride Playwright doğrudan yazılır.*
3. **R80** Scrapling'in fetcher tarafı tamamen yasak (`scrapling.fetchers`, `scrapling.engines`, 10 ad, `ProxyRotator`), ayrıştırıcı serbest — *dürüst bir fetcher gerekirse kural yeniden açılır.*
4. **R81** CAPTCHA çözme ve IP döndürme istemcileri yasak tabloya — *dört satır; liste "ve benzerleri"nin tamamı değildir.*
5. **R82** 0a'nın bütün Minor'ları ve brief bulguları ilk turda kapanır — *dosya ~550 satır.*
6. **R83** Pencereler `holdout.py`ye (T5), `match_probs`/`outcome_index`/`DEFAULT_METHOD` `devig.py`ye (T3) — *birkaç fonksiyonun yeri.*
7. **R84** `history.yml` tek işli; selftest alarmdan önce bir ADIM — *senkron kırmızıysa selftest o hafta koşmaz.*
8. **R85** `history-dispatch` salı 09:50 UTC — *football-data takvimi değişirse bir hafta gecikme.*
9. **R86** Kilidin kanonik satırı ayrıştırılmış değerlerden — *kaynağın biçim değişikliği görünmez.*
10. **R87** 0a Minor'ları ikinci tura girmez, DEFERRED §11'e — *src'ye kazara yazılmış ekli bir `pip install` dizesi inceleme görene dek geçer.*
11. **R88** `check_quality` sıfır maçlı dosyada `ContractViolation` — *meşru boş dosya kırmızı olur.*
12. **R89** `Window` `end > DEV_END` ya da `start >= end` iken `ValueError` — *sonrası dönemde pencere gerekirse ayrı tip.*
13. **R90** 0007'de politikasız RLS + `before truncate`; eski tablolar DEFERRED — *iki satır SQL.*
14. **R91** Köprü raporunun üreticisi: `render_bridge_report` + CLI `bridge` — *bir alt komut.*
15. **R92** `LeagueEfficiency.ou25_margin` — *bir alan.*
16. **R93** Köprü `n = 0` iken rapor yazmaz, `EXIT_NO_PAIRS = 10` — *bir çıkış kodu.*
17. **R94** Elo reytingi (grup, takım) anahtarıyla, grup = ülke — *aynı ülkede aynı adlı iki kulüp (ölçülmedi).*
18. **R95** Katalog The Odds API'nin sunduğu her lig için anahtar taşır — *anahtar listesi elle güncellenir.*
19. **R96** `load_matches` DEV + POST döner, HOLDOUT yalnız anahtarla; `lock` verilirse önce `verify_lock`; `_load_all` modüle özel (AST) — *iki fonksiyon.*
20. **R97** `exchange_gap = LL(AvgC) − LL(BFEC)`, ikisi ≥ %90 dolu dev lig-sezonlarında — *bir alan.*
21. **R98** `DecisionContext` durum görüntüsü taşımaz; durum stratejide (`observe`); Faz 3 eşitlik testi bağlamı VE `observe` akışını karşılaştırır — *Faz 3'te bir görüntü nesnesi eklenir.*
22. **R99** `load_lock` her yapı/biçim hatasında `LockViolation` (exit 9) — *yok.*
23. **R100** `NoClosingPrices` + `render_report(unmeasured=)`: AvgC'siz lig raporu düşürmez — *bir istisna, bir parametre.*
24. **R101** K1 test paketinde sağ kalan mutantlar küçük tek turda kapanır, controller yeniden koşar — *bir implementer turu.*
25. **R102** `Date` takvimi Task 8'de ölçülür; yerel tarih çıkarsa düzeltme Faz 3'ten önce (ölçüldü: Londra tarihi) — *ek lig başlama anı Faz 3'e kadar yanlış olabilirdi.*
26. **R103** Fiyat hücresi sayımı reddedilen ve yinelenen satırları içerir, genişliği tutmayanınkini içermez — *iki satır + bir testin beklenen sayıları.*
27. **R104** Satır genişliği tam eşitlik (fail-closed); ilk senkronda ret çıkarsa önce ölçülür — *eski sezon dosyaları ilk senkronda düşer (düştü → R111).*
28. **R105** Sezon penceresi [06-01, 07-31], yalnız 1920 08-31'de kapanır — *başka bir lig-sezonunun Ağustos tarihleri gürültülü düşer.*
29. **R106** `ci.yml` yorumu on adımın tam listesine, README başlığı "dört adım" — *bir yorum satırı.*
30. **R107** Dalga 2 implementer'ları paralel (ayrı worktree, ayrık dosya) — *merge çakışması T8'de görünür.*
31. **R108** T6 fikstürleri için ayrıştırıcı gevşetilmez, fikstür düzeltilir — *bir fikstür düzeltmesi.*
32. **R109** DEFERRED 12e (dosya başına kodlama logu) T6'ya eklenmez — *latin-1'e düşen dosya logda görünmez.*
33. **R110** 0006'ya `hist_fetches_no_truncate` + test (plan R90'a aykırıydı, spec bağlar) — *bir tetikleyici ve bir test.*
34. **R111** Başlıktan uzun satırın fazlası tamamen boşsa kırpılır ve sayılır; dolu fazla ve kısa satır reddedilir — *2006–08'de 1–2 haftalık blokta kaymış satır kilide girer.*
35. **R112** Kilit 7.646 / 4.446 ile commit'lenir (fark bulundu), plan sayısı değişmez — *kilidi yeniden üretip gerekçeli commit.*
36. **R113** Dalga 3 de paralel — *merge çakışması T11 öncesi görünür.*
37. **R114** Task 9 I1–I4 düzeltilir (ince lig "ölçülemez" olarak kalır), R7/R13 sabitlenir, rapor ifadesi "holdout satırı ölçüme girmedi" — *birkaç test ve bir dal.*
38. **R115** Yakalama daraltılır: yalnız `calibration` fitlerinin `ValueError`'ı ölçülemez sayılır; `--resamples < 1` reddedilir; N1 sabitlenir — *bir tur daha.*
39. **R116** Ü/A 2.5 fiti düşerse yalnız `ou25_*` alanları `None`; 1X2 ve adaylık korunur — *bir satır + test.*
40. **R117** Task 11 denetçisi planın dediği gibi `fable` — *bir denetim turunun maliyeti.*
41. **R118** `DEFAULT_METHOD = power` (K2 nokta tahmini) — *sabit + test; fark çok küçük.*
42. **R119** AST kuralı `load_files`, `parse_file`, `sync._parsed`ı da korur; izin `history/sync.py` + `history/__main__.py` — *bir kural testi; meşru çağıran izin listesine girer.*
43. **R120** Oracle kanaryası + K4 `detail` notu; gerçek veride K5 eklenmez — *bir test.*
44. **R121** F3, F5 ertelenir (F3 Task 12'de ölçüldü: 0), F4 kabul — *defterde yazılmamış; F3 sıfırdan farklı çıkarsa Faz 3 ön koşulu olur.*

---

## 5. Lig önerisi (tasarım §8.4) — kullanıcı onayladı

**Onay (Task 12 Step 4, AskUserQuestion):** A kademesi **N1** (`ned.1`, Eredivisie), **B1** (`bel.1`, First
Division A), **AUT** (`aut.1`, Bundesliga). **T1** zaten canlı. Kanıt (`docs/reports/2026-09-22-piyasa-verimliligi.md`;
kademe: aralığın alt ucu medyanın üstündeyse A):

| Lig | R1 geç bilgi ΔLL (sıra) | R2 kapanış kalibrasyonu, eğim b (sıra) | A kademesi nereden |
|---|---|---|---|
| N1 | 0.0079 [0.0042, 0.0115] (1.) | 0.98 [0.89, 1.07] | R1 |
| B1 | 0.0076 [0.0035, 0.0117] (2.) | 1.05 [0.94, 1.16] | R1 |
| T1 | 0.0063 [0.0026, 0.0101] (4.) | 1.16 [1.04, 1.28] (1.) | R1 ve R2 |
| AUT | — (ek lig, kapanış öncesi fiyat yok) | **0.87 [0.79, 0.96]** (3.) | R2 |

N1, B1, T1'de kapanış öncesi fiyat kapanıştan anlamlı ölçüde az isabetli (geç bilgi fiyata giriyor); T1 ve
AUT'ta kapanışın eğimi 1'i dışlıyor (T1 fazla temkinli, AUT aşırı güvenli). Dördünün de geliştirme N'i ≥ 1000,
holdout `AvgC`'si ≥ %95 ve The Odds API anahtarı var. Aday listesinin kalan 28'i yalnız "iki sıralamada da C
değil" kuralıyla girdi (§3/33) — öneri onlara dayanmadı.

**Eklemek AYRI bir görevdir** (bu fazda `config/leagues.yaml` değişmedi):
- `League` bugün `footystats_path`i zorunlu tutuyor; footystats sayfası olmayan lig için alan isteğe bağlı olmalı
  (ve toplayıcı onu atlamalı).
- Toplayıcılar (snapshot/mühür kapsamı, TFF yalnız TR) ve ad eşlemesi (`config/history_aliases.yaml`) yeni ligler için.
- **The Odds API kredisi:** üç lig mühür + snapshot tüketimini artırır (bütçe 500/ay); bekçi kalan krediyi izler.

---

## 6. Faz 3 ön koşulları

1. **Walk-forward doğrulama.** Faz 2'nin ölçümleri geliştirme döneminde örneklem içidir (§3/32); Faz 3'ün
   model seçimi ve hiperparametreleri yalnız ileriye doğru kayan pencerelerle ölçülür. `load_matches`in DEV +
   POST dönüşündeki holdout boşluğu (§3/40) pencere tasarımında ele alınır.
2. **Canlı bağlam kurucusu + eşitlik testi.** Faz 2 yalnız tarihsel kurucuyu yazdı. Faz 3 canlı kurucuyu
   (defter + gözlem deposu) yazar ve aynı maç için iki kurucunun **hem `DecisionContext`'i hem `observe` akışını**
   özdeş ürettiğini sınar (R98, tasarım §7.2/§7.4). Bu test olmadan backtest'in canlıyı temsil ettiği iddia edilemez.
3. **Elo fiti.** `k`, `home_advantage` ve marj eğrisi hâlâ iskele (Faz 1 §3.5/15); reyting grubu ülke (R94).
   Fit geliştirme döneminde, walk-forward ile.
4. **scipy dalga 0'ı.** Faz 2 yalnız numpy ekledi (D15); Dixon-Coles'un en çok olabilirlik fiti için scipy Faz
   3'ün kendi dalga 0'ında, tek controller commit'iyle eklenir.
5. **`final_eval` işçilere anahtar değil SEÇİLMİŞ SATIR verir** (12i). Sayılan şey açılıştır, kullanım değil:
   mührü kopyalanan bir anahtar sınırsız çoğaltılabilir. `open_holdout` yalnız `backtest/final_eval.py`de
   (AST kuralı); açılış `holdout_access_log`a düşer ve HANDOFF'ta sayılır. Orada `load_matches`in gerçek
   anahtarlı pozitif yolu da ilk kez sınanır (14j).
6. **Faz 3'ten önce okunacaklar:** DEFERRED §12 ve §14 (özellikle 14g: kilit her yenilendiğinde dosyalar arası
   yinelenen sayımı; 14l: Placebo tohumu), bu belgenin §3/36–39'u (erteleme, saatsiz satır, `Date` varsayımı,
   katalog kilitte değil) ve Faz 1 HANDOFF §5/6 (hakem özelliği yok).
