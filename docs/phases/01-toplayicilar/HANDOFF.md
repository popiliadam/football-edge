# Faz 1 — Toplayıcılar, Varlık Eşleme, Dil Kalibrasyonu · Devir Belgesi (HANDOFF)

**Tarih:** 2026-09-19 · **Dal:** `faz-1-toplayicilar` · **Kapı:** `./verify.sh` → `KAPI YEŞİL`
(9 adım PASS + `zincir` adımı ADIYLA SKIP) · **Test:** 365 passed / 2 skipped · **contract:** 18

> **Bu belgenin en önemli bölümü §3'tür.** §2 kapının **ne ölçtüğünü**, §3 **ölçmediğini**
> yazar. Yeşil bir kapı yalnız §2'yi kanıtlar; §3'teki hiçbir satır "test edildi" sayılamaz.
>
> **Faz 0'ın belgesi bir kez bayatladı** ve bayat hâliyle taşınmaya devam etti: "hiç snapshot
> koşmadı", "`ledger/` yalnız `.gitkeep` taşıyor" satırları canlı tur tarafından yanlışlandığı
> hâlde aylarca doğru gibi okundu. **Aynısı bu belgeye de olur.** Okuyan kişi, §2'deki test
> sayısını ve §2.2'deki canlı sayıları `git log` ve veritabanına karşı **bir kez** kontrol etsin.
>
> **Bu fazın en pahalı dersi de tam buydu:** doğrulanmamış bir ölçüm YÖNTEMİNDEN çıkan sonuç,
> hiç ölçmemekten tehlikelidir — çünkü "ölçüldü" etiketiyle dolaşır ve doğru olan kaydı devirir
> (§6.1, TFF `pageID` geri alması).

---

## 1. Ne bitti

Faz 1 = **toplayıcı katmanı.** Faz 0 oran defterini kurmuştu; Faz 1 modelin ihtiyaç duyduğu
diğer veri türlerini — xG, hakem, haber, sonuç, stadyum/hava, güç reytingi — izinli
kaynaklardan, append-only ve `observed_at` damgalı biçimde toplayan katmanı kurdu.

### 1.1 Altyapı ve kural katmanı

| Parça | Dosya | Durum |
|---|---|---|
| Kaynak kayıt defteri | `config/sources.yaml`, `sources.py` | 7 kaynak; 4 açık, 3 kapalı |
| robots.txt zorlaması (RFC 9309) | `sources.py` → `protego` | kapı adımı: `kaynak-politikası` |
| robots anlık görüntüleri | `config/robots/*.txt` | 7 dosya, ölçüm tarihi 2026-09-19 |
| Canlı robots sapma ölçümü | `scripts/robots_drift.py`, `.github/workflows/sources-audit.yml` | günlük cron — **hiç koşmadı** (§3.2) |
| Toplayıcı çatısı | `collector.py` (`fetch_text`/`assert_schema`/`assert_fresh`/`ContractViolation`) | 246 satır |
| Gözlem deposu | `observations.py`, `db/migrations/0002_sources.sql` | append-only tetikleyicili 3 tablo |
| Ad normalleştirme | `naming.py` | TR kuralları; `ı`→`i` katlaması (R19) |
| Veri sözleşmesi kapısı | `verify.sh` → `veri-sözleşmesi` | `EXPECTED_MIN_CONTRACT=18` |
| Oran defterine toplu yazma | `db.py` → `insert_snapshots` | Faz 0'ın §4.1 borcu kapandı |
| `verify-chain --full` + çıpa eksikliği | `collect.py`, `anchors.py`, `full-scan.yml` | Faz 0'ın §1.1/§1.3 borcu kapandı |

### 1.2 Toplayıcılar

| Kaynak | Modül | CLI | Ne topluyor | Durum |
|---|---|---|---|---|
| FootyStats | `collectors/footystats.py` | `fetch-footystats` | 6 ligin `xg_per_match`/`xga_per_match` tablosu | **çalışıyor** |
| TFF | `collectors/tff.py` | `fetch-tff` | bu haftanın hakem atamaları (windows-1254) | **çalışıyor** |
| Ajansspor | `collectors/news.py` | `fetch-news` | sitemap/news urlset → haber öğeleri | **çalışıyor** |
| Google News | `collectors/news.py` (adaptör) | `fetch-news` | RSS — **`enabled: false`** | kapalı (lisans + robots) |
| Wikidata + Open-Meteo | `collectors/venues.py`, `weather.py` | `fetch-venues` | stadyum koordinatı + maç saati havası | **kısmen** (§3.3/12) |
| The Odds API `/scores` | `collectors/results.py` | `fetch-results` | tamamlanmış maç skorları | **hiç koşmadı** (§3.2/3) |
| (kaynak yok) | `elo.py` | — | saf Elo motoru, ClubElo'nun yerine | iskele (§3.5/8) |

### 1.3 Varlık eşleme ve dil

| Parça | Dosya | Durum |
|---|---|---|
| Jev sarmalayıcısı | `jev.py` (`JevClient` Protocol, `TypeSafeJev`) | sahte istemciye karşı test edildi |
| Varlık eşleme | `mapping.py`, CLI `map-entities` | kod aday çıkarır, Jev seçer, eşik 0.75 |
| Dil kalibrasyon harness'ı | `calibration.py`, CLI `calibrate` | **hiçbir dil ölçülmedi** (§3.1/2) |
| Üretim kapısı | `config/languages.yaml`, CLI `check-languages` | raporsuz dil açılamaz — kapı zorluyor |

### 1.4 Modül bölünmeleri (`collect.py` üç kez bölündü)

`collect.py` 800 satırlık sert sınıra bu fazda **üç kez** dayandı. Her seferinde bölme,
davranış-nötr ve kendi commit'inde yapıldı:

| Ruling | Ne taşındı | Nereye | `collect.py` |
|---|---|---|---|
| R11 | çıpa/git-geçmişi mantığı | `anchors.py` (185) | 799 → 629 |
| R50 | toplayıcı CLI dispatch'i | `fetch.py` (144) | 774 → 684 |
| R53 | tur orkestrasyonu (`run_snapshot`/`run_seal`/mühür adaylığı/ayna) | `rounds.py` (312) | 799 → **515** |

**Neden 799'da teslim edilmedi (R53):** bir satırlık marj, devralan mühendisin İLK
düzenlemesinin kapıyı düşürmesi demektir — bu, "kapı gevşetilmez" kuralını devralanın sırtına
yıkmaktır.

---

## 2. Kapı ne ölçtü

Kapı çıktısı özet değil, **log dosyasından** (`$TMPDIR/football-edge-verify.log`).

### 2.1 Taze koşu — `4158f81` ağacı (ve bunu izleyen dokümantasyon commit'leri)

```
=== ruff-check ===          PASS  (All checks passed!)
=== ruff-format ===         PASS  (59 files already formatted)
=== mypy ===                PASS  (Success: no issues found in 25 source files)
=== pytest ===              PASS  (365 passed, 2 skipped)
=== paket-kurulu ===        PASS  (kurulu paket import edildi, PYTHONPATH boş)
=== kaynak-politikası ===   PASS  (kaynak politikası: TEMİZ)
=== veri-sözleşmesi ===     PASS  (18 passed, 349 deselected — EXPECTED_MIN_CONTRACT=18)
=== dil-kalibrasyonu ===    PASS  (dil kalibrasyonu: TEMİZ)
=== secrets ===             PASS  (secret taraması temiz)
SKIP: zincir (DATABASE_URL yok)
KAPI YEŞİL
```

**Bu koşu DOKUZ adımı ölçtü, onu değil.** `zincir` ATLANDI, çünkü koşulduğu kabukta
`DATABASE_URL` tanımlı değildi; `2 skipped` de append-only tetikleyici testleridir ve sebebi
aynı (ulaşılabilir veritabanı + dolu defter yok). **SKIP geçmek değildir.**

### 2.2 Faz 1'in eklediği dört kapı adımı ve kırmızı verebildiklerinin kanıtı

| adım | ne ölçüyor | kırmızı kanıtı |
|---|---|---|
| `kaynak-politikası` | `config/sources.yaml`'daki her `declared_paths`, `config/robots/<id>.txt` anlık görüntüsüne karşı; `api_terms` kaynaklarda `terms_url` zorunlu; `robots_verified_at` 30 günden eski olamaz | **Evet.** Task 3: yasaklı yol eklenince exit 6; gelecek-tarihli `robots_verified_at` sessiz geçiş yolu bulunup kapatıldı ve mutasyonla kırmızı kanıtlandı |
| `veri-sözleşmesi` | `contract` etiketli test sayısını `--collect-only` ile ÖLÇER; `EXPECTED_MIN_CONTRACT`in altındaysa pytest hiç çalışmadan kırmızı | **Evet, iki kez.** Task 5: TEK marker kaldırıldı (3→2), kapı kırmızı verdi, geri eklenince yeşile döndü. Task M: 3→18 bumpu kırıp-onararak kanıtlandı |
| `dil-kalibrasyonu` | `config/languages.yaml`'daki her `production_enabled: true` için kalibrasyon raporunun VAR olduğunu ve `production_ready()`yi geçtiğini sorar. **Ağa çıkmaz, para harcamaz** | **Evet.** Task 12: raporsuz bir dil `true` yapıldığında exit 8; 24 testin hepsi tek tek mutasyonla RED kanıtlı |
| `scripts/` kapsama alındı (R15) | `ruff`/`mypy` artık `scripts/`i de görüyor (`pytest` hariç — `scripts/` test taşımaz) | — (kapsam genişletmesi, ayrı adım değil) |

### 2.3 Canlı ve doğrulanmış durum

**Her satırın "nasıl doğrulandı" sütunu vardır. Sütunu boş bırakılamayan bir tablo, iddia
ile ölçümü ayrı tutmanın tek yoludur.**

| Şey | Değer | Nasıl doğrulandı |
|---|---|---|
| `0002_sources.sql` migrasyonu | 3 tablo + 2 append-only tetikleyici + 3 indeks | Task 4: canlı Supabase'e uygulandı, tablo listesi rapora yapıştırıldı |
| `source_observations` append-only | UPDATE **ve** DELETE reddedildi | Task 4: gerçek veritabanında, tam yetkili rolle denendi — ikisi de reddedildi |
| Oran defterine toplu yazma | 200 satır yazıldı, geri alındı; `ON CONFLICT … RETURNING` yinelenen satırda BOŞ döndü | Task 1: canlı Postgres sondası; satırlar `ORDER BY id` ile geri okunup zincir bağı doğrulandı, sonda geri alındı |
| `verify-chain --full` | `SAĞLAM kontrol=3717` | Task 2: gerçek 3 717 satırlık deftere karşı canlı koşuldu |
| FootyStats 6 lig | altısı da HTTP 200 | Task 5: canlı, her yol tek tek |
| `collect_footystats` idempotentliği | tur 1: **114 gözlem**, tur 2: **0 gözlem** | Task 5: canlı tur ×2; hem CLI çıktısı hem doğrudan DB sorgusuyla |
| TFF sayfa şekli | `pageID=600`: 7 lig bloğu / **63 maç satırı**, rol sayımı H=62 Y=124 D=62 **V=11 A=11**; 420 KB'da yalnız 3 `<table>` | Task 6 + inceleme: ikisi de fixture'ları diff'ten çıkarıp gerçek ayrıştırıcıyı bağımsız koşturdu |
| `collect_tff` idempotentliği | tur 1: **62 gözlem**, tur 2: 0 | Task 6: canlı site + canlı DB, ×2 |
| `fetch-tff` (CLI) | **20 yeni**, sonra 0 yeni, exit 0 | Task M: canlı ×2 (20 < 62 çünkü Task 6'nın turu çoğunu zaten yazmıştı — `content_hash` tekilliği) |
| `fetch-news` (CLI) | **1000 yeni gözlem**, exit 0 | Task M: canlı; Ajansspor `/sitemap/news` gerçekten akıyor |
| `fetch-venues` (CLI) | **1 yeni** — yalnız stadyum koordinatı | Task M: canlı; **hava yolu HİÇ ÇALIŞMADI** (§3.2/4) |
| Wikidata QID | `Q81492` = Rams Park, `P625` = 41.1034N / 28.991E | Task 7 + inceleme: fixture'a karşı; plandaki `Q170980` bir **dikilitaş**tı ve `P625` taşımıyordu |
| Ajansspor `<image:loc>` çakışması | naif gezinme 40 `<url>`den **80 item** çıkarıyor (yarısı CDN fotoğrafı); teslim edilen 40 çıkarıyor, 0 CDN | Task 8 + inceleme: gerçek fixture'a karşı yeniden üretildi |
| Google News fixture'ı geçmişte YOK | `git log --all -- '*googlenews-tr.xml'` → **boş** | Task 8: dal tek commit taşıyordu, `--amend` ile geçmişe hiç girmedi; koordinatör ayrıca kendi doğruladı |
| Paralel küme tek-yazar disiplini | **sıfır çakışma**, beş dal da `--no-ff` ile temiz birleşti | Task 6-10 birleştirme: hiçbir dosyada elle çözüm gerekmedi |
| `robots_verified_at` | 7 kaynağın hepsi **2026-09-19** | `kaynak-politikası` adımı her koşuda 30 günlük tazeliği sorar |

---

## 3. Kapının ÖLÇMEDİĞİ — burası "yeşil" sayılmaz

> Yol haritasının faz geçiş kuralı üç şey ister: her task kapıdan geçsin, critical/high bulgu
> kalmasın, ve **kapının kör noktaları ADIYLA yazılsın.** Üçüncüsü en sık atlanan ve en pahalı
> olandır: yazılmayan bir boşluk, bir sonraki fazda "doğrulanmıştı" varsayımıyla üstüne inşa
> edilir. Aşağıdaki maddelerin hiçbiri "belki"dir; hepsi bu faz boyunca ADIYLA görüldü.

### 3.1 Fazın kendi hedefini karşılamayan şeyler

**1. TOPLAYICILAR HİÇBİR YERDE KOŞMUYOR.** Zamanlama yok, cron yok, workflow yok. Beş
`fetch-*` komutu kütüphane + CLI olarak teslim edildi; onları `.github/workflows/` altına
bağlamak **kapsam dışı bırakıldı (R43)** — bir dağıtım kararıdır ve planda yoktu.
**Hiç koşmayan bir toplayıcı hiçbir şey toplamaz.** Faz 1 sonunda veri AKMIYOR; akması için
Faz 2'nin ilk işi bu bağlantıdır (§5/1). Faz 0'ın `snapshot.yml`/`seal.yml`'i bundan
etkilenmez — onlar ayrı ve zaten zamanlı.

**2. DİL KALİBRASYONU HİÇBİR ŞEY ÖLÇMEDİ — spec §5.4'ün Faz 1 şartı KARŞILANMADI.**
Harness var: `calibrate --language <kod>` komutu, eşik mantığı, `production_ready()`, ve
raporsuz bir dilin açılmasını engelleyen kapı adımı. **Ama:**
- Bu ortamda `TYPESAFE_API_KEY` **yok** — tek bir canlı Jev çağrısı yapılmadı.
- Dil başına ~100 **elle etiketlenmiş** haber gerekiyor; **hiç üretilmedi.**
  `data/calibration/tr.jsonl` yalnız BİÇİM örneği taşıyor (10 satır, insan onaylı değil).
- Sonuç: `config/languages.yaml`'daki **her dil `production_enabled: false`.**

Yani "Jev'in çok dilli doğruluğu" — spec §10'un 4 numaralı açık sorusu, Faz 1'in kapatmak
için var olduğu soru — **hâlâ açık.** Kapı YEŞİL, çünkü kapının ölçtüğü şey "ölçülmemiş bir
dil açık mı" sorusudur ve cevap "hayır"dır. **Yeşil kapı, ölçümün yapıldığı anlamına
GELMİYOR.** Anahtar ve etiketler geldiğinde tek komut yeter: `calibrate --language tr`.

Aynı sınıftan bir madde daha son bütün-dal incelemesinde bulundu: **PFDK hiç uygulanmadı** —
§3.9/30.

### 3.2 Hiç koşmamış kod yolları

**3. `fetch-results` bir kez bile koşmadı.** Bilinçli (R45): The Odds API **kredi yakar** ve
komut zaten 25 testle fixture'a karşı kapsamlı sınandı. İlk gerçek koşuda CLI yolunda bir
yazım hatası çıkabilir; kod yolu `collect_footystats`in kanıtlanmış desenini izliyor.

**4. `fetch-venues`'in HAVA ve UTC dönüşüm yolu bir kez bile koşmadı (R46).** Sebebi
yapısal: mekân kaydı yalnız Galatasaray'ı tanıyor (madde 12) ve Faz 0'ın 51 maçlık anlık
görüntüsünde Galatasaray'ın ev sahibi maçı YOK — yani `fetch-venues` bir koordinat yazıp
duruyor, hava yarısı ATIL. Zorlamak için veritabanına sahte maç yazmak append-only tabloya
kirlilik sokardı (madde 13'ün dersi). **Bu, diff'teki tek hiç çalışmamış kod yoluydu** ve
inceleme tam orada yanıt tarafında (`timezone=GMT` gönderilmiyordu) gerçek bir açık buldu.

**5. Faz 1'in eklediği hiçbir workflow bir runner'da koşmadı.** `sources-audit.yml` (günlük
canlı robots sapması) ve `full-scan.yml` (haftalık tam zincir taraması) yazıldı ama dal
push/merge edilmediği için **hiç tetiklenmedi.** Dolayısıyla: canlı robots sapması hiç
ölçülmedi, haftalık tam tarama hiç koşmadı, ve `ci.yml`in Faz 1'de eklenen dört adımı
(`kaynak-politikası`, `veri-sözleşmesi`, `dil-kalibrasyonu` ve genişletilmiş `scripts/`
kapsamı) runner'da hiç yeşil vermedi.

### 3.3 Kanıt zincirinin ve tazeliğin kör noktaları

**6. `source_observations`ın HASH ZİNCİRİ YOK.** Bilinçli (`0002_sources.sql` başındaki
yorum): zincir, ürünün "bu kayıt kurcalanmadı" iddiasını taşıyan **oran** defteri içindir.
**Sonuç:** özellik girdisi kurcalanırsa **dış çıpa bunu göstermez.** Tablo append-only ve
`observed_at` damgalı, ama tablonun SAHİBİ hâlâ `DISABLE TRIGGER` + `TRUNCATE` yapabiliyor
(DEFERRED §2.1 — Faz 0'dan devreden, kapanmadı) ve bu kez onu yakalayacak bir çıpa yok.

**7. `assert_fresh` toplayıcı çıktısı üzerinde TOTOLOJİK (R23).** Bir toplayıcı her satıra
kendi `now`unu basıp sonra "en yenisi taze mi" diye soruyorsa iddia **her zaman doğrudur** —
kırmızı veremeyen bir kontroldür. Kural koda geçirildi: `assert_fresh` YALNIZ `observed_at`i
KAYNAĞIN verdiği gözlemlerde çağrılır (haber `pubDate`i). `footystats`, `tff` ve `venues`
onu çağırmıyor ve **neden çağırmadıkları docstring'lerinde yazılı.** `news.py` yapısal olarak
zorluyor: `AjansporAdapter`ın `_news_published_at`i `now` parametresi hiç almıyor.
**Ölçülmeyen eksen:** gerçek kaynak bayatlığı — `content_hash`in N turdur DEĞİŞMEMESİ —
ERTELENDİ. Bugün "kaynak dondu" ile "kaynak aynı veriyi veriyor" ayırt edilemiyor.

**8. `contract` testleri KAYDEDİLMİŞ fixture'a bakar, canlı sayfaya değil.** 18 contract
testi "ayrıştırıcı hâlâ beklenen şekli üretiyor" der; "kaynak hâlâ o şekli yayınlıyor"
DEMEZ. Sayfa şekli değişirse bunu ancak canlı bir tur yakalar — ve madde 1 gereği canlı tur
zamanlanmış değil. Google News adaptörünün ise **hiç contract testi yok**: sentetik fixture
canlı gerçekliğe karşı yeniden ölçülemediği için marker bilerek kaldırıldı.

**9. `cur.rowcount`un `executemany` sonrası davranışı canlı Postgres'e karşı doğrulanmadı
(R35).** Yanlış olabilecek şey **LOG SAYISI**dır, yazılan satırlar değil: `WHERE EXISTS` ve
`ON CONFLICT` sunucu tarafında değerlendiriliyor. Yani riski bilinen ve sınırlı — ama
ölçülmemiş.

**10. `seal.yml` SIĞ checkout yapıyor → çıpa silme tespiti 15 dakikalık turda DEĞİL, haftalık
`full-scan.yml`de yakalanır; gecikme en fazla 7 GÜN.** Bilinçli maliyet ödünleşmesi (R
kararı, DEFERRED §1.3): `seal.yml`in kendisi günde ~96 çıpa commit'i üretiyor, 15 dakikada
bir tam geçmiş çekmek bileşen bir maliyete dönüşürdü. **Geciken ALARM'dır, KANIT değil** —
silinen çıpanın izi git geçmişinde durur.

### 3.4 Varlık eşlemenin kör noktaları

**11. VARLIK EŞLEMENİN İNSAN GERÇEK-REFERANSI YOK.** `resolve` üç koruma uyguluyor: NO_MATCH
kabul edilir, 0.75 eşiğinin altı REDDEDİLİR, ve (R51'den sonra) modelin cevabı **sunulan
seçenekler kümesinde** olmak zorundadır. **Ama hiçbiri bir eşleşmenin DOĞRU olduğunu
doğrulamaz** — yalnız şeklinin geçerli olduğunu. Eşiğin üstünde dönen yanlış bir kanonik ad
yazılır ve arkada yakalayacak bir şey yoktur: `entity_aliases.canonical_id text not null`,
`matches`e **FOREIGN KEY YOK**. Bir doğruluk ölçümü için elle etiketlenmiş bir eşleme kümesi
gerekir; üretilmedi.

**12. `map-entities` bugün YALNIZ `footystats`ı anlamlı biçimde eşliyor.** TFF
`entity_kind="team"` gözlemi üretmiyor — `fixture_official` yazıyor. Yani "kaynaklar arası
eşleme" bugün **tek kaynaklı**: karşılaştırılacak ikinci bir kaynak yok. Ajansspor haber
öğeleri de takım varlığı üretmiyor.

**13. `entity_aliases` tablosunu ÜRETİMDE HİÇBİR ŞEY OKUMUYOR.** `mapping.py` yazıyor;
`grep` ile doğrulandı: okuyan tek kod yolu yok. Sözlük var, tüketicisi yok — yani eşlemenin
doğru olup olmadığı **bugün hiçbir çıktıyı etkilemiyor**, ve bu da sessiz bir yanlış
eşlemenin fark edilmemesini kolaylaştırıyor.

**14. Eşik (0.75) bir bayrakla değiştirilemez.** `--threshold` yok; politika değişikliği kod
düzenlemesi gerektiriyor. `confidence` sütunu SAKLANIYOR (eşiği sonradan yükseltmek için
yeniden çıkarım gerekmesin diye), ama `jev.py`nin aldığı **`probabilities` hiçbir yerde
okunmuyor/saklanmıyor** (#M45) — spec §5.2'nin "ham yargıları sakla" gerekçesi açısından en
HAM olan atılıyor.

### 3.5 Model tarafında ölçülmemiş olan

**15. Elo'nun `k`, `home_advantage` VE MARJ EĞRİSİ fit edilmemiş İSKELEDİR.** `k = 20.0`,
`home_advantage = 65.0` ve `_margin_multiplier`'ın eğri şekli — **üçü de** uydurulmuş
başlangıç değeridir, ölçüm değil. Spec §4/3: "özellikler fit edilir, elle katsayı verilmez."
Üçü de kodda docstring'le iskele olarak İŞARETLENDİ (R40: marj eğrisi başta işaretlenmemişti
ve asimetri, Faz 2'nin o sabiti ihmal yoluyla gerçek sanmasına yol açardı). **Faz 2'nin fit
listesi:** `k`, `home_advantage`, marj eğrisi.

**16. `elo.py` hiçbir şey toplamıyor ve hiçbir CLI komutu yok** — ve olmamalı. Faz 2 onu
kendi harness'ından çağırır.

### 3.6 Kapanan kaynaklar — Faz 3'e kadar taşınacak eksikler

**17. Understat KAPALI** (`robots.txt` = `Disallow: /`, 26 bayt). xG kapsamını FootyStats
devraldı: **altı ligin xG'si artık TEK kaynağa bağlı, yedek YOK.** O kaynak düşerse model
girdisinin tamamı düşer.

**18. FBref KAPALI** — içerik sayfası **ve `robots.txt`'in kendisi** 403 Cloudflare veriyor;
politikayı OKUMAK bile bot korumasını aşmayı gerektiriyor (spec §3.2/2, SofaScore'u eleyen
kuralın aynısı). **Sonuç: GLOBAL HAKEM VE SEYİRCİ VERİSİ YOK.** TR'de TFF hakem atamasını
karşılıyor; başka hiçbir ligde karşılık yok. **Faz 3'ün baz modeli hakem özelliği OLMADAN
kurulmalıdır** — "zaten vardı" varsayımı yanlıştır.

**19. ClubElo KULLANILAMAZ** — `api.clubelo.com/Fixtures` 200 `text/csv` ile *"Fixtures API
deactivated"* dönüyor; tarih ve kulüp uçları ısrarlı 502. Spec §4/1'in "ClubElo önseli"
ifadesi bu yüzden madde 15 fit edilene kadar **karşılıksızdır**.

**20. Google News robots ile kapalı VE lisansı amaçlanan kullanımı yasaklıyor.**
`/rss/search` yolu robots.txt'te **her user-agent için** kapalı (ve `ClaudeBot`,
`anthropic-ai`, `GPTBot`, `CCBot`, `PerplexityBot` adıyla ayrıca); üstüne feed'in kendi
`<copyright>`'ı kişisel olmayan her kullanımı açıkça yasaklıyor. **Adaptör KODU kaldı**
(bizim kodumuz), `enabled: false` olarak teslim edildi. **Bu, spec §3.2/1'in kaçış yolunu
kapatır:** "kapalı kaynaklara yalnız Google News RSS üzerinden, başlık düzeyinde bakılır"
cümlesinin karşılığı artık yok.

**21. TFF yalnız BU HAFTAYI veriyor.** `__VIEWSTATE` + RadComboBox ⇒ başka hafta/lig
**postback** ister, postback POST'tur ve `outward_action_gate` onu `net_post` olarak
engeller. Geçmiş hafta ve diğer ligler alınamıyor. **VAR/AVAR atamaları sayfada VAR** —
`(V)` ve `(A)` rol işaretleriyle, düz "VAR" kelimesiyle değil (ölçüldü: V=11, A=11) — ama
**toplanmıyor**, çünkü sözleşme tek bir `referee` alanı istiyor.

**22. Ajansspor'un YAPISAL yolları KAPALI.** `robots.txt`: `/lineup/*`, `/mac/`, `/oyuncu/`,
`/lig/` ve `*rsc=*` **Disallow**. **Yani MUHTEMEL 11 ve SAKAT/CEZALI listesi ALINAMIYOR** —
spec §3.1 tam olarak bunları bu kaynaktan bekliyordu. Açık olan yalnız haber yolları
(`/sitemap`, `/sitemap/news`).

### 3.7 Kapsam ve kirlilik

**23. `fetch-venues` TAM OLARAK BİR stadyum kapsıyor** (`VenueSpec(home_team="Galatasaray",
qid="Q81492")`). Süper Lig'deki diğer 17 takım ve Faz 0'ın izlediği diğer beş ligin HİÇBİRİ
için mekân/hava verisi yok. Bilinçli (R44): genişletmek takım→QID eşlemesi ister ve o tam
olarak varlık eşlemenin işi; şimdi elle ikinci bir eşleme yazmak iki kez yazılan iş olurdu.
**Yanlışsa bedeli:** Faz 2'ye "hava özelliği var" varsayımıyla geçilirse varsayım yanlıştır.

**24. `source_observations`ta İKİ KALICI SONDA SATIRI var ve kaldırılamaz.**
`source_id='migration-check'` ve `source_id='task4-verify'`. Tek kaldırma yolu
`DISABLE TRIGGER`; RUNBOOK §2.3 bunu açıkça yasaklıyor ve ürünün bütünlük iddiasını taşıyan
mekanizmayı iki atıl satır için kapatmak zararın kendisinden kötü olurdu. **Zararsız:**
hiçbir gerçek kaynak bu `source_id` değerlerini üretmiyor, `latest_observations` her zaman
`source_id`ye göre filtreliyor. **Aynı zamanda korumanın ÇALIŞTIĞININ kanıtı** — bize karşı
da tuttu. Doğru prosedür DEFERRED §2.3'te yazılı.

**25. `/sitemap` beyan edildi ama alt-sitemap keşfi uygulanmadı.** `collect_news` yalnız
`/sitemap/news`i çekiyor; `/sitemap` (index) robots.txt'in gerçekten adlandırdığı bir giriş
noktası olduğu için beyan edildi, ama kodda tüketicisi yok.

### 3.8 Faz 0'dan devreden ve KAPANMAYAN eksenler

**26.** `shellcheck` / `actionlint` / `yamllint` hâlâ **yok** — `verify.sh`, `check_secrets.sh`
ve **beş** workflow YAML'ı kapının parçası ama kapı onları ölçmüyor.
**27.** `mypy` `tests/`i hâlâ görmüyor (`files = ["src", "scripts"]`); **coverage ölçülmüyor.**
**28.** Secret taraması hâlâ **git GEÇMİŞİNİ taramıyor** (DEFERRED §5 / Faz 0 §3.4). Tarayıcı
artık DÖRT isim kalıbı biliyor — `ODDS_API_KEY`, `DATABASE_URL`, `SUPABASE_*KEY` ve bu fazın
`TYPESAFE_API_KEY`i (son bütün-dal incelemesinin I-2'si; ondan önce tanımıyordu). **Liste ELLE
tutuluyor:** hiçbir şey onu `.env.example`ten türetmiyor, yani bir sonraki yeni secret adı
I-2'yi tekrarlar (R60) — DEFERRED §9.6i.
**29.** En az yetkili veritabanı rolü hâlâ **YOK** — toplayıcı tablo SAHİBİ olarak bağlanıyor
(DEFERRED §2.1). Faz 1 bu tabloyu üçe çıkardı, yani boşluğun yüzeyi büyüdü.

### 3.9 Son bütün-dal incelemesinin eklediği

Numaralar kararlı kalsın diye sona eklendi (R58): 1–29 değişmedi, başka belgeler onlara
"§3.7/25" biçiminde atıf yapıyor. Parantezdeki I-n/M-n o incelemenin bulgu numaralarıdır.

**30. PFDK HİÇ UYGULANMADI.** Spec §3.1'in "Hakem + ceza (TR)" satırı (satır 81) TFF'den
"PFDK kararları" bekliyor; plan Task 6'nın başlığı "hakem ataması ve PFDK". Ama Task 6
brief'inin gövdesi PFDK'yı hiç tanımlamadı, implementer "kapsam dışı" dedi ve kimse
kaydetmedi. `pageID=246` beyanlıydı ama hiçbir kod onu fetch etmiyordu; son inceleme turunda
kaldırıldı (M-1). **Kod yok, beyanlı yol yok, veri yok.** "Fazın kendi hedefi" sınıfındandır
(§3.1). Kaydedildi, uygulanmadı (R57) — DEFERRED §9.7.

**31. `latest_observations` bir değer GERİ DÖNÜNCE ARADAKİ satırı döner** (X → Y → X gözlenirse
"en yeni" **Y** çıkar). UNIQUE kısıtı `content_hash` üzerinde ve hash `observed_at`i dışlıyor;
üçüncü yazım ilk X ile çakışır, `ON CONFLICT DO NOTHING` onu sessizce düşürür — hatasız,
makul görünen yanlış değer. **Bugün etki sıfır:** tek okuyucu `mapping.resolve_source_aliases`
ve footystats yükleri monoton `matches_played` taşıyor. Ama hakem yeniden atamaları ve özdeş
yeniden yayınlar geri dönebilir. Şema değişmedi, sınırlama docstring'de yazılı; düzeltme
migrasyon ister (Faz 2): anahtar başına SON hash'e karşı tekilleştir (I-5) — DEFERRED §9.6e.

**32. Kaynak kapısı declared → robots'u ve (yeni test) fetched ⊆ declared'ı bağlar;
declared-ama-fetch-edilmeyen yön bağlı DEĞİL.** `kaynak-politikası` her beyanlı yolu robots'a
sorar; `test_each_collectors_fetched_path_is_declared` toplayıcıların gerçekten istediği her
yolun beyanlı olduğunu sabitler. Ters yönü hiçbir test bağlamıyor: `pageID=246` bu fazın
sonuna kadar böyle yaşadı; ajansspor `/sitemap` bilinçli (madde 25). R7'nin "beyan = gerçek
istek" sözleşmesi o yönde hâlâ prose (M-1, R59) — DEFERRED §9.1h.

**33. `EXPECTED_MIN_CONTRACT` bir TABAN, eşitlik değil** (`verify.sh`, `-lt` karşılaştırması).
Sayıyı artırmadan eklenen contract testleri görünmez; sonra o kadar test kaldırılırsa o da fark
edilmez — taban sessizce aşınır. Bugün ölçülen 18 (M-2) — DEFERRED §9.6g.

**34. `dil-kalibrasyonu` provenance'sız bir raporu kabul eder.** `CalibrationReport` ne
`measured_at` ne etiket dosyasının hash'ini taşıyor: `tr.jsonl` değişse bile bayat bir rapor bir
dili açık tutabilir. Bugün etkisiz (rapor yok, her dil `production_enabled: false`); **ilk gerçek
kalibrasyondan ÖNCE** düzeltilmeli (M-5) — DEFERRED §9.6h.

**35. Haberde kısmî kayıp SESSİZ.** `_sitemap_item` `<loc>`suz bir `<url>` için `None` döner ve
bunları kimse saymaz; yalnız TOPLAM kayıp hata verir. footystats (R31) ve tff (R36) kısa-düşüş
korumasına sahip, news değil: §4.2/8'in kuralı ona uygulanmadı (M-4) — DEFERRED §9.3o.

---

## 4. Verilen kararlar (Ruling listesi)

Tam gerekçeler `.superpowers/sdd/2026-09-19-faz1-toplayicilar/progress.md` içinde — **o dizin
gitignored, yani merge etmez ve yalnız bu makinede durur.** Kalıcı olması gerekenler buraya,
`docs/DEFERRED.md`'ye ve `docs/RUNBOOK.md`'ye taşındı. Aşağıdakiler defterdeki ruling'lerin
içinden **Faz 2'yi bağlayanlardır.**

### 4.1 Kaynak politikası ve dürüstlük

1. **`declared_paths` GERÇEKTEN ÇEKİLEBİLİR URL olmalı, temsilî ÖNEK değil (R7).** Önek
   yazılırsa kapı **hiç istenmeyen** bir yolu ölçer: izinli bir kaynağı yanlışlıkla kapatır
   (Wikidata'ya oldu) ya da — daha kötüsü — izinsiz bir yolu geçirir. Aynı hata Ajansspor'da
   var olmayan bir `/sitemap.xml`i ölçtürdü (canlıda 404).
2. **User-agent sahteciliği YOK (R9).** Plan `ClaudeBot/1.0` kullanıyordu çünkü FootyStats
   robots'u ClaudeBot'a Disallow'suz kendi grubunu veriyor. ClaudeBot Anthropic'in
   tarayıcısıdır; biz değiliz. **Ölçüldü: dürüst kimliğin bedeli SIFIR** — altı xG yolunun
   altısı da `*` grubunda izinli. `crawl_delay` 5.0 seçildi: sitenin herhangi bir
   adlandırılmış üçüncü tarafa verdiği **en hızlı** değer (R13).
3. **`access_basis: robots | api_terms` (R8).** Open-Meteo bir API HOST'udur, insan için
   sayfa sunan bir site değil; robots.txt tarayıcıları yönetir, dokümante bir API'nin
   istemcisini değil. **Ama tek seferlik dipnot olarak bırakılmadı:** `api_terms` kaynaklar
   `terms_url` taşımak ZORUNDA ve kapı bunu denetliyor — karar makine tarafından okunabilir.
4. **RFC 9309 uyumlu ayrıştırıcı zorunlu (R10).** stdlib `urllib.robotparser` üç eksende
   yanlıştı ve **iki YÖNDE birden**: fazla kapatıyor (Wikidata) VE az kapatıyor
   (`Disallow: /*.php` hiçbir şeyi engellemiyordu). `protego`ya geçildi. **Semantiği bilinen
   biçimde yanlış olan bir guard, kırmızı veremeyen bir testle aynı sınıf kusurdur.**
5. **Ham üçüncü taraf içeriği depoya girmez (R38).** 154 KB'lık birebir Google News feed
   kopyası fixture olarak commit'lenmişti; spec §3.2/4 ham içeriğin yeniden yayınlanmasını
   yasaklıyor ve **commit etmek yayınlamaktır** (depo public). `--amend` ile geçmişe hiç
   girmedi; yerine sentetik RSS fixture'ı kondu. **KAPI BUNU YAPISAL OLARAK GÖREMEZ:** kaynak
   `enabled: false` ve `declared_paths: []`, yani `kaynak-politikası` adımı ona hiç bakmıyor.
6. **`scripts/` kapıya girer, politika kararı `src`'ye taşınır (R15).** "Bir HTTP durumu
   robots anlık görüntüsü için ne anlama gelir" sorusu script tesisatı değil KAYNAK
   POLİTİKASI mantığıdır; `sources.py`ye taşındı ve otomatik olarak lint+tip+test kapsamına
   girdi. Bundan önce projenin en yeni güvenlik kontrolü kapının hiç bakmadığı bir dosyadaydı.

### 4.2 Toplayıcı sözleşmeleri

7. **`follow_redirects=False` (R21).** `True` ile `guard_path` yalnız İLK atlamayı koruyordu;
   httpx her 3xx'i, **çapraz host dahil**, korumasız takip ediyordu. Kısıt "guard_path
   HERHANGİ bir istek atılmadan ÖNCE patlar" — yönlendirme zinciri tam o istekleri atıyordu.
8. **Kısmî kayıp SESSİZ GEÇEMEZ (R29, R31, R36).** Üç ayrı toplayıcıda aynı desen: bulunan
   satır sayısından AZ yazan bir tur "başarı" raporluyordu. Kural: bulunan ile yazılan
   arasındaki fark **o çağrıda bulunan satır sayısına karşı** kontrol edilir ve yetersizse
   `ContractViolation` fırlatılır. Sabit bir alt sınır (`minimum_rows=10`) yeterli değildir.
9. **Lig izolasyonu SESSİZ olamaz (R29).** Altı ligin ALTISI da düşse komut `0 yeni gözlem`
   basıp exit 0 veriyordu — idempotent ikinci turla **birebir aynı çıktı**, ki bu tam da
   doğruluk kanıtı olarak kullanılan çıktıydı. `EXIT_SOURCE_FAILED` ile ayrıldı.
10. **`enabled: false` toplayıcıyı da durdurmalı (R28).** Toplayıcı `load_sources`tan
    seçiyordu, `enabled_sources`tan değil: operatörün kill switch'i denetimden çıkarıyor ama
    çekmeyi sürdürüyordu — sessizce silahsızlanmış bir anahtar.
11. **`written` COMMIT'TEN SONRA sayılır (R48).** Dört toplayıcıda commit'ten ÖNCE sayılıyordu:
    commit düşerse satırlar geri alınır ama sayılmış olur ve tur "N yeni gözlem" basar. Bu
    Faz 0'ın **dört düzeltme turuna mal olan** G1 hatasının aynısıdır: *"başarısız değil" ≠
    "kalıcı olarak yazıldı."* R48 venues/news/results'ı düzeltti; REFERANS toplayıcı
    footystats ancak son bütün-dal incelemesinde düzeldi (I-1) — testi
    `test_collect_does_not_count_a_league_whose_commit_fails`. tff'de `written` commit'ten
    önce atanır ama yalnız commit başarılıysa DÖNER (tek sayfa, döngü ve toplam sayaç yok).
12. **Saat dilimi İKİ TARAFTA da zorlanır (R41 + R47).** İstek tarafı: `parse_forecast` artık
    UTC olmayan/naive bir kickoff'u REDDEDİYOR (TRT duvar saati UTC sanılırsa 3 saatlik kayma
    BAŞKA AMA GEÇERLİ bir saatlik dilime düşüyor ve `_MAX_GAP` yakalamıyor — ölçüldü:
    20.3 yerine 19.1, istisna yok). Yanıt tarafı: `timezone=GMT` artık AÇIKÇA gönderiliyor;
    önce satıcının bugünkü varsayılanına yaslanıyordu. **200, doğru veriyi aldığımızın kanıtı
    değildir** — aynı ilke yanıt tarafında.
13. **`xg`/`xga` MAÇ BAŞINA ORTALAMADIR, sezon toplamı değil (R27).** Alan adları
    `xg_per_match`/`xga_per_match`. Yanlış yorum 10 katlık bir birim kaymasını sessizce
    geçirirdi ve bu altı ligin TEK xG kaynağıdır.
14. **"Tamamlandı ama skor yok" GÖRÜNÜR olur (R34).** Sessizce atlanmaya devam eder (asla
    uydurma skor yazılmaz) ama WARNING + sayımla raporlanır: aksi hâlde "tamamlandı ama skor
    yok" ile "henüz oynanmadı" çıktıda ayırt edilemiyor ve Elo sessizce aç kalabiliyor.
15. **`normalise_team` boru hattının SONUNDA `ı`→`i` katlar (R19).** Türkçe kuralı tek kulübü
    İKİ anahtara bölüyordu: TFF (windows-1254) `İstanbulspor`, FootyStats ASCII `Istanbulspor`
    yazıyor. Fonksiyon tam da önlemek için var olduğu sessiz join hatasını bir adım öteye
    taşıyordu.

### 4.3 Süreç ve kapı

16. **Beş implementer İZOLE WORKTREE'lerde paralel koştu (R32).** `subagent-driven-development`
    skill'inin "asla paralel dispatch etme" kuralı ORTAK çalışma ağacı içindir. Pre-flight
    taraması tek-yazar sınırını önceden doğruladı (R1: paralel küme `collect.py`'a DOKUNMAZ;
    CLI kaydı birleştirmede tek adımda). **Sonuç: sıfır çakışma.**
17. **`EXPECTED_MIN_CONTRACT` gerçek bir SAYIM olmalı (R24, R30, R33).** İlk sürüm yalnız
    exit-5'i (TOPLANAN=0) kontrol ediyordu: üç marker'dan YALNIZ BİRİ kaldırılsa pytest exit 0
    verir ve karşılaştırma hiç yapılmazdı. Artık `--collect-only` ile gerçek sayı ölçülüyor,
    pytest hiç ÇALIŞTIRILMADAN önce. Bump **birleştirmede bir kez**, toplam sayıyla yapılır.
18. **Zamanlama Faz 1 kapsamı DEĞİL (R43)** — ama "hiç koşmayan toplayıcı hiçbir şey
    toplamaz" gerçeği §3.1/1'e adıyla yazıldı, sessizce varsayılmadı.
19. **`fetch-venues` tek stadyumda kalır (R44)**, `fetch-results` bilerek koşturulmaz (R45),
    `fetch-venues`in hava yolu fiilen doğrulanmadı ve **olmuş gibi sayılmadı** (R46).
20. **Kalibrasyon harness'ı yazılır, ÖLÇÜM ERTELENİR (operatör kararı).** Kapı zaten raporsuz
    bir dilin açılmasını engelliyor — harness kendi şartını zorluyor. **Bu, spec §5.4'ün
    şartını KARŞILAMIYOR ve karşıladığını iddia etmiyoruz; fark yazılı** (§3.1/2).
21. **Modelin cevabı sunulan seçeneklerin İÇİNDE olmak zorunda (R51).** `resolve` üç
    korumanın ikisini kodda uyguluyor, üçüncüsünü satıcıya bırakıyordu: sunulan liste
    `[…, Gaziantep FK, …]` iken `"Gaziantep Basketbol"` dönen bir istemci o değeri
    `canonical_id` olarak YAZDIRIYORDU. **Tipli bir arayüz cevabın ŞEKLİNİ garanti eder,
    DOĞRULUĞUNU asla.**
22. **`collect.py` 800 satır sınırında teslim edilmez (R53).** Bkz. §1.4.
23. **Fonksiyon uzunluğunda kodu değil KURALI değiştir (R54).** `parse_referees` (59),
    `collect_venues` (105) ve `resolve` (52) 50 satırı aşıyor; aşan her satır bir incelemenin
    TALEP ETTİĞİ düzeltme (R36 kısa-düşüş koruması, R49 izolasyon, R51 üyelik kontrolü) ve
    fonksiyonlar tutarlı. Kapı bunu zaten ölçmüyor (ruff'ta fonksiyon uzunluğu kuralı yok):
    50 satır bir KILAVUZDUR (DEFERRED §9.5). **Yanlışsa bedeli:** üç fonksiyon uzun kalır.
24. **Yarıda kalan düzeltme dalgasının diff'i KORUNDU, yeniden yapılmadı (R55).** Son bütün-dal
    incelemesinin düzeltme turu API limitine takılıp dokuz dosyada commit'lenmemiş iş bıraktı;
    sekiz kod maddesi dokuz mutasyon + bir klon kanıtıyla doğrulandı, yalnız biçim ve atıf
    hataları düzeltildi — doğrulanmış işi yeniden yaptırmak bir tur yakardı. **Yanlışsa
    bedeli:** korunan diff'te ince bir kusur; bu yüzden yeniden inceleme tamamlama commit'ini
    değil TÜM dalgayı (`7b5158d`'den itibaren) kapsar.
25. **#M10 GERÇEKTEN kapatıldı (R56).** `test_full_scan_workflow_is_read_only` skaler
    `permissions: read-all`/`write-all` kısayolunda artık çıplak `AttributeError` değil temiz
    bir assertion veriyor (RED→GREEN kanıtlı); `_concurrency_group` docstring'i kendini #M10
    sanan yanlış iddiadan arındırıldı. **Yanlışsa bedeli:** birkaç satır test kodu.
26. **PFDK boşluğu KAYDA geçer, UYGULANMAZ (R57).** Yeni bir toplayıcı bir düzeltme dalgasının
    işi değildir (yeni yetenek); kayıt §3.9/30'da, §3.1'deki işarette ve DEFERRED §9.7'de.
    **Yanlışsa bedeli:** Faz 2 PFDK verisi var sanabilirdi — kayıt tam bunu önler.
27. **Yeni §3 maddeleri §3.9'a, 30'dan numaralanarak girer; 1–29 DEĞİŞMEZ (R58).** Belgeler ve
    inceleme raporları "§3.7/25", "§3.8/28" biçiminde atıf yapıyor; araya ekleme bu atıfları
    sessizce kaydırırdı. Metni artık YANLIŞ olan madde (28) yerinde düzeltildi. Aynı gerekçeyle
    R54–R61 de §4'ün sonuna, 23'ten numaralanarak girdi. **Yanlışsa bedeli:** konu gruplaması
    biraz zayıflar.
28. **Kaynak bağlayıcı testi TEK yönlüdür: fetched ⊆ declared (R59).** Tehlikeli yön, kapının
    HİÇ denetlemediği bir fetch'tir; o bağlandı. Ters yön (beyanlı ama fetch edilmeyen)
    bağlanmadı, §3.9/32'de adıyla yazıldı; aksini ima eden iki metin (test yorumu ve
    `sources.yaml`ın tff notu) düzeltildi. **Yanlışsa bedeli:** fazla beyan edilmiş bir yol
    fark edilmeden geri gelebilir; robots açısından zararsız.
29. **Secret deseni asgari düzeltildi (R60).** `TYPESAFE_API_KEY` desene eklendi. Secret
    adlarını `.env.example`ten türeten bir test SONRAKİ unutmayı yakalardı ama yeni yetenek;
    ölçülmeyen eksen olarak §3.8/28'de yazılı. **Yanlışsa bedeli:** bir sonraki yeni secret adı
    aynı boşluğu tekrarlar.
30. **Devir belgelerindeki DONMUŞ sayılar güncellenmez, KALDIRILIR (R61).** "22 madde",
    "48 minor", §3.1'in "iki şey"i. Depo donmuş commit sayısını zaten komutla değiştirmişti
    (`7b5158d`); minor bulgu sayısının kaynağı gitignore'lu bir dosya, okur için yeniden
    üretilebilir bir komut yok. **Yanlışsa bedeli:** okur boyut hissini kaybeder.

---

## 5. Faz 2 ön koşulları

1. **Toplayıcıları bir zamanlamaya bağlamak — Faz 2'nin İLK işi.** Beş `fetch-*` komutu
   çalışıyor ama hiçbiri koşmuyor (§3.1/1). Faz 2 tarihsel taban ve backtest harness'ı
   kuruyor; o harness'ın besleneceği canlı özellik akışı bugün YOK. Dikkat: `fetch-results`
   API kredisi harcar (Faz 0 bütçesi 500/ay, snapshot zaten ~186 kullanıyor) ve `fetch-news`
   turu 1000 gözlem yazabiliyor.
2. **`robots_verified_at` 30 GÜNLÜK ZAMANLAYICIYLA ÇALIŞIYOR.** Yedi kaynağın hepsi
   `2026-09-19`. **Yaklaşık 2026-10-19'da `kaynak-politikası` adımı KENDİLİĞİNDEN KIRMIZI
   VERİR.** Bu bir arıza değil tasarım; tazelemek için robots anlık görüntüleri yeniden
   çekilir ve tarihler güncellenir (`config/sources.yaml` başındaki not). **Bunu bilmeden
   kırmızı bir kapıyla karşılaşan biri kapıyı gevşetmeye çalışabilir — yapılmaz.**
3. **`TYPESAFE_API_KEY` + dil başına ~100 elle etiketlenmiş haber.** İkisi olmadan spec
   §5.4'ün şartı karşılanamaz ve hiçbir dil üretime alınamaz (§3.1/2).
4. **Varlık eşleme için ikinci bir takım kaynağı.** Bugün yalnız `footystats`
   `entity_kind="team"` üretiyor (§3.4/12); "kaynaklar arası eşleme" iddiası bir ikinci
   kaynak gelene kadar karşılıksız.
5. **Elo'nun üç sabitinin FİT EDİLMESİ:** `k`, `home_advantage`, marj eğrisi (§3.5/15).
   Faz 2'nin tarihsel tabanı (`xgabora/Club-Football-Match-Data`) bunun için var.
6. **Faz 3 planlanırken: HAKEM ÖZELLİĞİ YOK.** FBref kapalı (§3.6/18). TR dışında hiçbir lig
   için hakem verisi gelmiyor. Baz model bu özellik olmadan kurulmalı.
7. **`docs/DEFERRED.md` OKUNMUŞ OLMALI.** Faz 1 o listeyi tek tek kapatmak zorunda değildi ve
   kapatmadı; Faz 2 de zorunda değil, ama **okumadan** başlamamalı. Özellikle §2.1 (en az
   yetkili rol yok — Faz 1 tablo sayısını üçe çıkardı) ve §9.4 (jev `probabilities` atılıyor)
   Faz 2'nin tasarımını etkiler. §9.2'nin en önemli maddesi (`full-scan.yml`in concurrency
   YOKLUĞUNU sabitleyen test) son bütün-dal incelemesinde kapandı.
8. **Dalın merge'i.** Faz 1'in beş workflow'unun hiçbiri koşmadı (§3.2/5). GitHub `schedule`
   yalnız varsayılan dalda çalışır.

---

## 6. Bu fazın YÖNTEM dersleri

Aşağıdakiler kod hakkında değil, **nasıl çalışıldığı** hakkındadır. Faz 1'in en pahalı
bulguları bunlardı ve hiçbiri bir testin yakalayabileceği türden değildi.

### 6.1 Doğrulanmamış bir ölçüm YÖNTEMİ, hiç ölçmemekten tehlikelidir

Oturumun başında `pageID=600`de "Hakem" 181 kez geçiyordu. Bağlam regex'i
(`.{130}Hakem.{170}`) yalnız **1 eşleşme** verdi ve buradan "600'de hakem verisi YOK"
sonucuna varıldı — sonra bu sonuçla **spec "düzeltildi"** ve plan `pageID=433`e taşındı.

Hata veride değil **yöntemdeydi:** `finditer` ÖRTÜŞEN eşleşmeleri yutar, yani 300 karakterlik
pencere içindeki ardışık geçişler tek eşleşmeye düştü. Üstüne veri `<table>` sanılarak
arandı — oysa 420 KB'lık sayfada yalnız **3** `<table>` var ve veri `<div>` bloklarında.

Uygulama ve inceleme bunu iki kez, birbirinden bağımsız biçimde çürüttü: `pageID=433`ün
varsayılan GET'i gönderilmemiş üç katmanlı bir arama formu döndürüyor ve engellenmiş bir POST
olmadan **asla** hakem satırı vermiyor. **Spec BAŞTAN BERİ DOĞRUYDU; düzeltilen şey bozuk
değildi.** Aynı sebeple "sayfada VAR dizesi hiç geçmiyor" ölçümü de yanlıştı: VAR/AVAR orada,
yalnız `(V)`/`(A)` rol işaretiyle.

**Kural:** bir ölçüm yöntemini doğrulamadan ondan çıkan sonucu kural hâline getirme. Yanlış
sonuç "ölçüldü" etiketiyle dolaşır ve doğru olan kaydı devirir.

### 6.2 Kırmızı veremeyen bir test, test değildir — ve planın KENDİ verdiği testlerde EN AZ DÖRT KEZ çıktı

Bu projenin kuralı zaten yazılıydı ("bir test konusunu yeniden yazıyorsa yalnız aynı kodu iki
kez yazabildiğinizi kanıtlar"). Faz 1'de ihlali **planın kendi tedarik ettiği test kodunda**
bulundu — yani kuralı yazan taraf, kendi ürettiği testlerde çiğnedi:

| nerede | neden kırmızı veremiyordu |
|---|---|
| Task 1 `test_insert_snapshots_preserves_chain_order` | Taklidi sınıyordu, SQL'i değil: sahte bağlantı SQL'i ayrıştırmıyor, `WITH ORDINALITY`/`ORDER BY ord` silinse bile yeşil kalıyordu. Implementer'ın RED kanıtı bunu doğruladı: test, `db.py`ye dokunulmadan ÖNCE de PASSED |
| Task 2 (R3'ün sığ-klon testi) | Test aslında **sığ klon YARATMIYORDU** — guard tamamen silinse sıfır test düşerdi. Aynı task'ta ikinci boşluk: `_verify_chain_command`'ın "ÇIPA EKSİK → return 1" yolu uçtan uca hiç sınanmıyordu |
| Task 9 `test_skips_events_that_have_not_completed` | Olayda hem `completed=False` hem `scores=None` vardı: iki koruma birbirini maskeliyordu, biri silinse test yine geçerdi |
| Task 11 `test_high_confidence_match_is_accepted` | Alias `"Galatasaray A.Ş."`, kanonik liste `"Galatasaray"` — `normalise_team` ikisini de `galatasaray` yapıyor, **birebir eşleşme kısa devresi** ateşleniyor ve MODEL HİÇ ÇAĞRILMIYORDU. "Yüksek güvenli eşleşme kabul edilir" diyen test, model yolunu hiç çalıştırmıyormuş |
| Task 10 (sıfır-toplam testi) | Yalnız `FLAT` (home_advantage=0.0) ile koşuyordu; orada sigmoid antisimetrisi hatayı TESADÜFEN sıfıra topluyor. Modülün KENDİ varsayılanı altında aynı hata 3.70 puanlık gerçek sızıntı veriyor |

**Kural:** her testin kırmızı verebildiği **mutasyonla** kanıtlanır, ve planın yazarlığı kendi
işini notlandıramaz.

### 6.3 Tipli bir arayüz cevabın ŞEKLİNİ garanti eder, DOĞRULUĞUNU asla

`resolve` üç korumanın ikisini (NO_MATCH, eşik) kodda uyguluyordu; üçüncüsünü — cevabın
sunulan seçenekler arasında olup olmadığını — tamamen satıcıya bırakıyordu. Sunulan liste
`[Besiktas, Fenerbahce, Galatasaray, Gaziantep FK, Trabzonspor, none of the above]` iken
`"Gaziantep Basketbol"` dönen bir istemci o değeri `canonical_id` olarak yazdırıyordu —
arkada yakalayacak bir şey yok (`matches`e FK yok). Bu, task'ın **önlemek için var olduğu**
geri alınamaz yanlış join'in ta kendisi ve brief'in KENDİ örnek vakasıydı.

**Kural:** bir modelden gelen cevabın tipi doğru olabilir ve cevap yine de sunulan evrenin
dışından gelebilir. Üyelik **bizim tarafımızda** kontrol edilir — ve kontrol, modele verilen
**tam aynı** yerel değişkene bakmalıdır, yeniden türetilmiş bir listeye değil.

### 6.4 Kapı, BAKTIĞI şeyi ölçer — ve yanlış şeye bakabilir

`declared_paths` temsilî bir ÖNEK olarak yazıldığında kapı, kodun **hiç istemediği** bir yolu
ölçtü ve izinli bir kaynağı (Wikidata) yanlışlıkla kapattı. Aynı hata Ajansspor'da **var
olmayan** bir `/sitemap.xml`i ölçtürdü. Ters yön daha tehlikelidir: stdlib robots
ayrıştırıcısı `Disallow: /*.php`yi hiçbir şeyle eşleşmeyen düz bir dizeye çeviriyordu — yani
kapı, kapalı bir yolu **açık** sayıyordu.

**Kural:** bir kapının yeşil olması, doğru şeye baktığı kanıtlanmadan bir şey ifade etmez.
"Kapı ne ölçtü" ile "kapı neye baktı" ayrı sorulardır.

### 6.5 Tek-yazar disiplini paralelliği gerçekten mümkün kıldı

Beş implementer beş izole worktree'de eşzamanlı koştu. Pre-flight taraması dosya paylaşan her
task çiftini önceden listeledi ve **paralel kümede hiçbir ortak yazılabilir dosya
bırakmadı** (R1: `collect.py` salt okunur, CLI kaydı birleştirmede tek adımda; R2: paylaşılan
`normalise_team` çatıya taşındı). **Sonuç: beş dal da `--no-ff` ile sıfır çakışmayla
birleşti; hiçbir dosyada elle çözüm gerekmedi.**

---

## 7. Açık sorular

Faz 0'dan devredenler (`docs/phases/00-kayit-altyapisi/HANDOFF.md` §5) hâlâ geçerli. Faz 1'in
kapattığı ve açtığı:

| # | Soru | Faz 1'deki durum |
|---|---|---|
| 1 | **Jev'in çok dilli doğruluğu** | **HÂLÂ AÇIK.** Faz 1'in kapatma şartıydı; harness var, ölçüm yok (§3.1/2) |
| 2 | **Transfermarkt robots.txt** | **HÂLÂ AÇIK.** Faz 1'de doğrulanacaktı; kaynak hiç ele alınmadı |
| 3 | **İddaa boşluğu** | değişmedi — TR kullanıcısı İddaa'da oynuyor, marj Avrupa ortalamasının üstünde |
| 4 | **Lisans zinciri** (`Club-Football-Match-Data` → football-data.co.uk) | değişmedi; **Faz 2'nin birincil girdisi bu CSV** — ticari lansman öncesi avukat |
| 5 | **Google News lisans çatışması** | **YENİ.** Feed'in `<copyright>`'ı kişisel olmayan kullanımı yasaklıyor; MIT CSV ile aynı muamele (§3.6/20) |
| 6 | **Hakem özelliği nereden gelecek?** | **YENİ.** FBref kapalı; TR dışında kaynak yok (§3.6/18) |
| 7 | **Altı ligin xG'si tek kaynakta** | **YENİ.** Understat kapalı; FootyStats düşerse yedek yok (§3.6/17) |
| 8 | Highlightly / API-Football | değişmedi, kullanılmıyor — kayıt amaçlı |

### Faz 1'den devreden ertelenmiş bulgular → **`docs/DEFERRED.md` §9**

Minor bulgular bu faz boyunca ADIYLA kaydedildi ve bilerek ertelendi. Okur-yüzlü tam liste
orada (§9); burada ikinci kez tutulmuyor — **iki kopya, biri diğerinden sessizce ayrışır.**
