# football-edge — Ertelenen bulgular ve bilinen ödünleşmeler

**Kapsam:** Faz 0 (`faz-0-kayit-altyapisi`) ve **Faz 1** (`faz-1-toplayicilar`) boyunca
bilerek ERTELENEN her şey. Hiçbiri "unutuldu" değildir; her biri görüldü, tartışıldı ve
şimdilik kabul edildi. **§1–§7 Faz 0'ındır, §8–§9 Faz 1'indir.**

**Bu dosya neden var.** Kararların tamamı `.superpowers/sdd/2026-09-19-faz0-kayit-altyapisi/`
altında yaşıyordu ve o dizinin `.gitignore`'u tek satır: `*`. Yani her ruling, her
bulgu, her ertelenen madde **merge olmayacaktı**: Faz 1'i devralan mühendis temiz bir
`main` görecek ve bu listenin hiçbirini bilmeyecekti. Karar kaydının kendisi
gitignore'da kalmaya devam ediyor (süreç artığı); **sonuçları burada, izlenen bir
dosyada.**

**Faz 1'de aynı şey ikinci kez olacaktı:** o fazın defteri
(`.superpowers/sdd/2026-09-19-faz1-toplayicilar/progress.md`, 944 satır, 111 ruling ve
ertelenen bulgu) de aynı `*` altındaydı. Dayanıklı olanı §9'a taşındı; kalan süreç artığıdır.

Öncelik etiketi yok — sıra tematik. Bir faz planı bu listeyi **tek tek** ele almak
zorunda değil, ama **okumadan** başlamamalı.

---

## 1. Zincirin kanıt değeri — açık kalan delikler

### 1.1 Zincirin İÇİ hiç yeniden hash'lenmiyor

`verify-chain` bir çıpa varken yalnız iki şeye bakar: (i) çıpanın gösterdiği **tek**
satırın içeriği, (ii) **en yeni çıpadan sonraki kuyruk**. En eski ve en yeni çıpa
arasındaki satırlar hiç yeniden hash'lenmez. Oradaki bir kurcalama ancak bir sonraki
çıpa o aralığa düştüğünde görünür — ki düşmez, çünkü çıpalar hep ileri gider.

**Gereken:** `verify-chain --full` seçeneği (tüm defteri GENESIS'ten tarar) ya da
haftalık bir tam tarama işi. Maliyeti gerçek: 3 717 satır bugün ucuz, 12 ayda değil.

**Faz 1 / Task 2 notu — "Gereken"in İKİSİ de karşılandı.** `verify-chain --full` yazıldı
(GENESIS'ten yeniden hash'ler ve HER çıpayı sorar — yani §1.2'yi de kapatır) ve haftalık
tam tarama işi eklendi: `.github/workflows/full-scan.yml`, Pazar 04:23 UTC,
`fetch-depth: 0`. **Canlı doğrulandı:** gerçek 3 717 satırlık deftere karşı
`SAĞLAM kontrol=3717`. **Kapanmayan:** `--full` YALNIZ haftalık işte ve elle koşuluyor;
15 dakikalık mühür turu hâlâ yalnız kuyruğu tarar, yani zincirin içi **en fazla 7 gün**
yeniden hash'lenmemiş kalabilir. Maliyet endişesi de duruyor: 12 aylık defterde haftalık
tam tarama ölçülmedi. Ayrıca `full-scan.yml` **hiç koşmadı** (dal merge edilmedi).

### 1.2 (KAPANDI — Faz 1 / Task 2, yalnız `--full` yolunda) İkiden fazla çıpa varsa aradakiler hiç sorulmuyor

`asked = anchors if len(anchors) == 1 else (anchors[0], anchors[-1])`. 30 günlük çıpa
birikince 28'i hiç okunmaz. **`--full` HER çıpayı sorar** (bkz. §1.1) — ama varsayılan
(bayrağsız) yol, yani günde ~96 kez koşan yol, hâlâ yalnız ilk ve son çıpayı okur.

### 1.3 Çıpa SİLİNMESİ, bozulmasından daha sessiz

Bozuk bir çıpa `ÇIPA UYUŞMAZLIĞI` ya da `EN YENİ ÇIPA ATLANDI` bastırır. **Silinen**
çıpa hiçbir şey bastırmaz: `_scan_anchors` yalnız var olan dosyaları görür, "dün üç
çıpa vardı" bilgisi hiçbir yerde tutulmuyor. Üstelik silme, RUNBOOK §1.4'teki **meşru
arşivleme** prosedüründen ayırt edilemez — ikisi de `ledger/head-*.txt`i yerinden
kaldırır.

**Gereken:** beklenen çıpa kümesinin dışarıda tutulması (ör. git geçmişinden türetilen
bir sayım) ve eksilme hâlinde adıyla kırmızı.

**Faz 1 / Task 2 notu — yukarıdaki "Gereken" karşılandı, ama 15 dakikalık turda DEĞİL:**
`expected_anchor_names`/`missing_anchors` artık var, ama `seal.yml` `actions/checkout@v4`i
`fetch-depth` vermeden koşuyor (varsayılan: **SIĞ**, `fetch-depth: 1`). Bu yüzden sığ-klon
koruması her seferinde devreye girip `None` döner ve `_verify_chain_command`
"git geçmişi okunamadı — ÇIPA EKSİKLİĞİ KONTROLÜ ATLANDI" basar — **günde ~96 turun
hiçbirinde** çıpa-eksikliği kontrolü gerçekten koşmaz. Silinen bir çıpa yalnız haftalık
`full-scan.yml`de (o `fetch-depth: 0` çeker) yakalanır; tespit gecikmesi en fazla **7 gün**.

Bu KASITLI bir maliyet ödünleşmesidir, gözden kaçmış değil: `seal.yml` günde ~96 kez
koşuyor; her turda tam geçmiş çekmek (geçmiş her gün en az bir çıpa commit'iyle büyüyor) gerçek
ve büyüyen bir maliyete dönüşürdü. Geciken **ALARM**dır, **KANIT** değil — silinen
çıpanın git geçmişindeki izi hâlâ durur, yalnız fark edilmesi haftaya kadar sürebilir.

### 1.4 `ON CONFLICT (row_hash) DO NOTHING` sahte bir zincir kopukluğu üretebilir

Bir satır ON CONFLICT ile düşerse ondan sonraki satırlar düşen satırın hash'inden
zincirlenmiş olarak yazılır ve defterde `prev_hash` boşluğu kalır. Pratikte bugün
ulaşılamaz (aynı `row_hash` ancak birebir aynı yük demektir), ama **ölü dal değil**:
yeniden deneme senaryosunda tetiklenebilir.

### 1.5 Bir maç için birden fazla `is_closing` satırı mümkün

`sealed_at` damgası maçı bir daha aday yapmaz, ama şemada tekillik yok: mühürlenmiş
bir maça elle ya da başka bir yoldan ikinci bir `is_closing` satırı yazılabilir. CLV
hesabı "kapanış fiyatı" derken hangisini kastedeceğini bilmez.

---

## 2. Yetki ve güven sınırı

### 2.1 En az yetkili veritabanı rolü YOK — toplayıcı tablo SAHİBİ olarak bağlanıyor

Ürünün sattığı şey "bu kayıt kurcalanmadı" kanıtı. Append-only tetikleyici `UPDATE` ve
`DELETE`i reddediyor — **ama tablonun sahibine karşı değil.** Bugünkü `DATABASE_URL`
sahiple bağlanıyor, yani şunlar elinin altında:

```sql
alter table odds_snapshots disable trigger odds_snapshots_append_only;  -- korumayı kapat
truncate odds_snapshots;                                                 -- tetikleyiciyi hiç ateşlemez
```

Yani tetikleyici, ürünün vaadinin ADINI KOYDUĞU aktöre karşı savunma yapmıyor; yalnız
kazayı ve daha düşük yetkili bir yoldan gelen saldırıyı durduruyor. Dış çıpa bu boşluğu
KISMEN kapatır (TRUNCATE'i yakalar) ama yetki sorununu çözmez.

**Gereken:** `INSERT` + `SELECT` yetkili ayrı bir toplayıcı rolü; şema sahipliği ayrı
bir rolde ve o rolün kimlik bilgisi CI'da hiç bulunmasın.

### 2.2 `DISABLE TRIGGER` yasağı yalnız PROSEDÜRDE yazılı

RUNBOOK §2.3 bunu açıkça yasaklıyor, ama yasağı zorlayan hiçbir şey yok — bkz. 2.1.

### 2.3 İlk canlı sınama: iki kalıcı prob satırı (Task 4, 2026-09-19)

2.1/2.2'nin tarif ettiği boşluk — tetikleyici SAHİBE karşı savunmasız, yasağı zorlayan
tek şey RUNBOOK §2.3 — Task 4'ün migrasyon doğrulamasında GERÇEK yetkiyle (tablo sahibi
`DATABASE_URL`) ilk kez fiilen sınandı: bir unit test değil, tam veritabanı yetkisine
sahip bir aktör. **Prosedürel yasak tuttu** — `DISABLE TRIGGER` hiç denenmedi — ama
bedeli iki kalıcı satır oldu.

`source_observations`da şu iki satır KALICI olarak duruyor:

- `source_id='migration-check', entity_kind='team', entity_key='probe'` — 0002
  migrasyonunun uyguladığı tabloları/tetikleyiciyi doğrularken: satır INSERT + commit
  edildi, sonra append-only tetikleyicinin UPDATE'i reddettiği ayrı sınandı (reddetti,
  doğru), ardından DELETE'i de reddettiği sınanırken (o da reddetti, doğru) script
  istisnayı yakalamadan düştü ve satır temizlenemeden kaldı.
- `source_id='task4-verify', entity_kind='team', entity_key='probe-a'` — `latest_
  observations`in taklide değil GERÇEK veritabanına karşı uçtan uca doğrulaması;
  temizleme hiç denenmedi (aşağıdaki sebeple zaten mümkün değil).

**Neden kalıcı:** tek kaldırma yolu `alter table source_observations disable trigger
source_observations_append_only` — RUNBOOK §2.3 bunu açıkça yasaklıyor (bkz. 2.1/2.2).
İki satırı temizlemek için ürünün bütünlük iddiasını taşıyan mekanizmayı kapatmak,
satırların kendisinden daha kötü olurdu; denenmedi.

**Neden zararsız:** `config/sources.yaml`'daki hiçbir gerçek kaynak (footystats, tff,
ajansspor, openmeteo, wikidata, understat) bu `source_id` değerlerini üretmez;
`latest_observations` her zaman `source_id`ye göre filtreler, yani bu satırlar hiçbir
gerçek okuma yolunda GÖRÜNMEZ.

**Doğru sıra buydu (ve bir dahaki sefere budur):** tek transaction içinde INSERT →
UPDATE dene (reddedilir, transaction abort olur) → ROLLBACK; ayrı bir transaction'da
yeniden INSERT → DELETE dene (reddedilir) → ROLLBACK. Hiçbir adım commit edilmez, tablo
dokunulmamış kalır — tetikleyici transaction kapsamlı ateşlendiği için bu, korumayı
KAPATMADAN aynı kanıtı verir. Bunun yerine satır erken commit'lendi; hata oradaydı.

---

## 3. Mühür ve veri bütünlüğü

### 3.1 (KAPANDI — Faz 1 / Task 1) `matches.commence_time` hiç tazelenmiyor

> **Bu madde artık ERTELENMİŞ bir sorun DEĞİL — tarihi bir kayıt olarak tutuluyor.**
> Aşağıdaki "Gereken" birebir uygulandı: `upsert_matches` artık
> `ON CONFLICT (id) DO UPDATE SET commence_time = excluded.commence_time` kullanıyor
> (`db.py:176`) ve mühür penceresiyle etkileşiminin testi de yazıldı. **Yan etki adıyla
> kaydedildi:** dönen sayı artık "yeni maç" değil "GÖRÜLEN maç"tır (`DO UPDATE` her satır
> için 1 bildirir) — çağıran bu değeri karar için kullanmaz. Değişmemiş bir
> `commence_time`ın da yeniden yazılması (WAL + ölü tuple) minor olarak ertelendi:
> `WHERE ... IS DISTINCT FROM` no-op'u gerçek no-op yapardı.

`upsert_matches` `ON CONFLICT (id) DO NOTHING` kullanıyordu: bir maç ertelenirse
veritabanı ESKİ saati taşımaya devam eder. İki sonuç:

- Satır filtresi API'nin (güncel) saatine, mühür adaylığı ise veritabanının (bayat)
  saatine bakar; ikisi çelişir.
- Ertelenen maç eski saatinden 24 saat sonra `_seal_candidates` penceresinden
  (`commence_time > now - interval '1 day'`) **sessizce düşer**: ne mühürlenir ne de
  kaçan mühür olarak raporlanır. Kapanış fiyatı kaybolur ve kimse görmez.

**Gereken:** `ON CONFLICT (id) DO UPDATE SET commence_time = excluded.commence_time`
(ve bunun mühür penceresiyle etkileşiminin testi).

### 3.2 `matches` tablosuna hiç girmemiş maç, kaçan mühür raporunda görünmez

Kaçan mühür raporu `matches` tablosunu tarıyor. Bir maç hiç yazılmadıysa (lig o turda
düştü, API olayı hiç dönmedi, tüm fiyatları `price > 1.0` kontrolünü ihlal etti) rapor
onu **bilmez**. Yani "kaçan mühür yok" cümlesi "bildiğimiz maçlarda kaçan mühür yok"
demek.

### 3.3 Kaçan mühür raporu 24 saat sonra kendini temizliyor

Aynı `commence_time > now - interval '1 day'` sınırı: kaçan mühür bir gün raporlanır,
sonra sessizce listeden düşer. Exit 5 (bkz. `collect.py`) de onunla birlikte kaybolur.

### 3.4 YAML'dan çıkarılan lig tabloda kalıyor

`upsert_leagues` yalnız ekler/günceller. `config/leagues.yaml`'dan silinen bir lig
`leagues` tablosunda `active=true` olarak durmaya devam eder (yabancı anahtar silmeyi
zaten engelliyor). Bugün zararsız — toplayıcı ligleri YAML'dan okuyor — ama tablo
konfigürasyonun aynası olduğunu iddia ediyor ve bu iddia yanlış.

---

## 4. Yazma yolunun maliyeti

### 4.1 (KAPANDI — Faz 1 / Task 1) Satır başına bir INSERT — ilk canlı tur ~4 dakika sürdü

> **Bu madde artık ERTELENMİŞ bir sorun DEĞİL — tarihi bir kayıt olarak tutuluyor.**
> "Gereken"in İLK seçeneği uygulandı: `insert_snapshots` artık `executemany` + toplu
> `RETURNING` kullanıyor ve zincir sırası `WITH ORDINALITY` + `ORDER BY ord` ile
> korunuyor. Canlı Postgres'e karşı doğrulandı: 200 satır yazıldı, `ORDER BY id` ile geri
> okunup zincir bağı kontrol edildi, sonra geri alındı. `ON CONFLICT … RETURNING`in gerçek
> bir yinelenen satırda BOŞ döndüğü de ayrıca gösterildi — "yalnız GERÇEKTEN yazılan
> `match_id` döner" özelliği (Faz 0'ın F1'i) korunuyor.
> **İKİNCİ seçenek uygulanmadı:** mühür turu hâlâ `snapshot` ile aynı `odds-collect`
> concurrency grubunda. Aşağıdaki "Etkileşim" paragrafı bu yüzden GEÇERLİLİĞİNİ KORUYOR,
> yalnız tetikleyici süre kısaldı. (Faz 1'in `full-scan.yml`i bilerek `odds-collect`
> grubunun DIŞINDA — ne üst düzeyde ne bir job'da concurrency bloğu var; ~~o ayrımı sabitleyen
> bir test YOK~~ artık bir test, `seal.yml`/`snapshot.yml` dışında hiçbir workflow'un bu grubu
> üst düzeyde ya da bir job'da bildirmediğini sabitliyor — kapsamı §9.2a'da.)

`insert_snapshots` her satır için ayrı bir `cur.execute` atıyordu: 3 717 satır =
3 717 pooler gidiş-dönüşü, ölçülen süre ~4 dakika (120 saniyelik beklentinin çok
üstünde). Testlerde görünmedi (sahte bağlantı anında dönüyor), kapıda görünmedi
(kapı veritabanına dokunmuyor).

**Etkileşim — bu madde tek başına okunmamalı:** `snapshot` ve `seal` **aynı
`odds-collect` concurrency grubunda** ve grup `cancel-in-progress: false`. Uzun süren
bir snapshot turu, arkasına mühür turlarını kuyruğa dizer; mühür penceresi 20 dakika
ve **kaçan mühür geri gelmez**. Lig sayısı 6'dan 35-40'a çıktığında bu sıra gerçek bir
risk hâline gelir.

**Gereken:** `executemany` / `COPY` ile toplu yazma (zincir sırası korunarak) ya da
mühür turunun snapshot'tan ayrı bir concurrency grubuna alınması — ikincisi C2'nin
kapattığı yarışı geri açar, yani **kilit olmadan yapılamaz.**

### 4.2 ~~Çıpa commit'i günde ~96 ek CI koşusu doğuruyor~~ — YANLIŞTI, konusu da kalmadı (2026-09-22)

Bot `GITHUB_TOKEN` ile push'lar ve GitHub bu push'lardan yeni workflow tetiklemez: CI yalnız
insan push'larında koştu (ölçüldü). Çıpa da artık yalnız zincir başı değiştiğinde ya da yeni UTC
gününde commit'lenir (`publish-head`). `ci.yml`e dal filtresi yine bilinçli olarak eklenmedi.

---

## 5. Kapının hiç bakmadığı eksenler

### 5.1 `shellcheck` / `actionlint` / `yamllint` yok

`verify.sh`, `scripts/check_secrets.sh` ve ~~üç~~ **beş** workflow YAML'ı (Faz 1
`full-scan.yml` ve `sources-audit.yml`i ekledi) kapının **parçası** ama kapı onları
ölçmüyor. `tests/test_workflows.py` YAML'ları ayrıştırıp yapısal iddialar kuruyor — bu bir
linter değildir: ifade sözdizimi, geçersiz `uses` referansı, hatalı girinti ancak runner'da
patlar. Faz 1 kapsamı genişletti: `scripts/` artık `ruff`+`mypy` görüyor (R15), ama kabuk
ve YAML hâlâ denetimsiz.

### 5.2 Eşzamanlılık gerçek Postgres'e karşı hiç sınanmadı

C2'nin kilidi var ve **ifade sırası** test ediliyor (sahte bağlantıyla), ama iki gerçek
oturumun serileştiği ölçülmedi. `pg_advisory_xact_lock`in gerçekten beklettiği, iki
paralel `collect snapshot` ile doğrulanmalı.

### 5.3 `mypy` `tests/`i görmüyor; coverage ölçülmüyor

`files = ["src", "scripts"]` (R15 `scripts/`i de kapsama aldı) — ama `tests/` hâlâ tip
denetiminden geçmiyor. `pytest-cov` kurulu değil, kapıda eşik yok.

### 5.4 Workflow'ların hiçbiri bir runner'da koşmadı — **kısmen kapandı, Faz 1'de yeniden açıldı**

~~`ci.yml` dâhil.~~ **Faz 0 sonunda `ci.yml` koştu ve GEÇTİ** (2026-09-19 06:24 UTC, `main`
ve `faz-0` üzerinde, 17-19 sn) — bkz. `docs/HANDOFF.md`. Dal merge edilene kadar `schedule`
koşmaz (GitHub `schedule`'ı yalnız varsayılan dalda onurlandırır); merge sonrası **ilk koşu
izlenmelidir.**

**Faz 1 boşluğu yeniden açtı, daha dar biçimde.** `faz-1-toplayicilar` dalı push/merge
edilmedi, yani:
- Faz 1'in iki YENİ workflow'u (`sources-audit.yml` günlük canlı robots sapması,
  `full-scan.yml` haftalık tam zincir taraması) **hiç koşmadı** — canlı robots sapması
  bugüne kadar bir kez bile ölçülmedi.
- `ci.yml`in Faz 1'de eklenen dört kapı adımı (`kaynak-politikası`, `veri-sözleşmesi`,
  `dil-kalibrasyonu` ve genişletilmiş `scripts/` kapsamı) **bir runner'da hiç yeşil
  vermedi.** Yerelde yeşil; runner'da `uv sync --frozen` ile yeni bağımlılıkların
  (`protego`, `beautifulsoup4`, `typesafe-sdk`) çözülüp çözülmediği ölçülmedi.

### 5.5 (KAPANDI — R10) stdlib `robotparser`ın ÜÇ sınırı vardı; `protego`ya geçilerek düzeltildi

**Bu madde artık ERTELENMİŞ bir sorun DEĞİL — tarihi bir kayıt olarak tutuluyor.** Faz 1
Task 3'te bulundu (joker karakter eksikliği), revizyonda (R7 incelemesi) iki tane daha
bulundu (boş-satır blok kesilmesi; dosya-sırası önceliği). `urllib.robotparser` RFC 9309'u
üç eksende karşılamıyordu:

1. **Joker karakter (`*`/`$`) DESTEKLENMİYORDU** — `RuleLine` her deseni `urllib.parse.quote`
   'tan geçirip `*`/`?`yi `%2A`/`%3F`ye çeviriyordu; `Disallow: /*.php` gerçek bir istekte
   HİÇBİR ZAMAN eşleşmeyen düz bir dizeye dönüyordu. Ölçüldü: `footystats.txt`
   (`Disallow: /*.php`, `/matches?*`) ve `ajansspor.txt` (`Disallow: /lineup/*`).
2. **Bir blok içindeki boş satır, YENİ bir `User-agent:` satırı görmeden kural birikimini
   SESSİZCE kesiyordu** — RFC 9309'a aykırı (yalnız yeni User-agent satırı ya da EOF bir
   grubu bitirir). Wikidata'nın gerçek robots.txt'i (446 satır, TEK "User-agent: *" satırı)
   bunun kurbanıydı: satır 422/423/425'teki boş satırlar yüzünden 435-436'daki kurallar hiç
   okunmuyordu.
3. **Çakışan kurallarda "en ÖZGÜL (en uzun) kazanır" DEĞİL, dosya SIRASINDAKİ İLK eşleşen
   kural kazanıyordu** (`Entry.allowance()`). Wikidata'nın robots.txt'i `Disallow:
   /wiki/Special:` (geniş, erken) İLE `Allow: /wiki/Special:EntityData/*.` (özgül, geç)
   taşıyor; erken/geniş olan kazanıyordu, geç/özgül olan HİÇ sorulmuyordu.

Üçü BİRLİKTE `wikidata`'yı yanlışlıkla kapalı tutuyordu: `declared_paths:
['/wiki/Special:EntityData/Q170980.json']` (R7'nin düzelttiği, gerçekten fetch edilen URL)
Wikimedia'nın kendi `Allow` kuralıyla AÇIKÇA izinliydi, ama stdlib bunu göremiyordu.

**Düzeltme (R10):** `urllib.robotparser` yerine `protego` (Scrapy ekibi, RFC 9309: joker
karakter + en-uzun-eşleşme + doğru blok birikimi) — `pyproject.toml`'a eklenen tek yeni
bağımlılık. `sources.robots_for()`/`allows()`/`guard_path()` imzaları AYNI kaldı, yalnız
`robots_for`'ın dönüş tipi `Protego`. Üç sınırın hepsi `tests/test_sources.py`'de dedike
testlerle pinlendi (`test_wildcard_disallow_actually_blocks_a_matching_path`,
`test_longest_match_lets_a_narrow_allow_override_a_broad_disallow`,
`test_blank_line_mid_block_does_not_drop_the_rule_that_follows`) — üçü de stdlib'e
dönülürse (mutation ile kanıtlandı) KIRMIZI verir. `wikidata` artık `enabled: true`
(ölçüldü: `/wiki/Special:EntityData/Q170980.json` artık `True`).

---

## 6. Devralınan minor bulgular (Faz 0 incelemelerinden)

| # | Nerede | Ne |
|---|---|---|
| T2 | `leagues.load_leagues` | YAML kökünde `leagues` anahtarı yoksa **çıplak `KeyError`** fırlatıyor; operatöre ne olduğunu söylemiyor. |
| T3 | `odds_api.fetch_odds` | `params[...] = ...` item ataması. Yerel, dışarı sızmayan bir dict — ihlal değil ama projenin "mutasyon yok" kuralına aykırı. |
| T4 | `ledger.verify_chain` | Eksik alanlı satırda **çıplak `KeyError`**: "defter bozuk" ile "kod bozuk" ayırt edilemiyor. Ayrıca rezerve anahtarlar (`prev_hash`/`row_hash`/`id`) çıplak isim eşleşmesiyle hariç tutuluyor ve bu dokümante değil; `checked` ile `failed_index` hata yolunda aynı değeri taşıyor. |

---

## 7. Faz 0'dan devreden açık sorular

Bunlar bulgu değil, **cevabı olmayan sorular** — `docs/phases/00-kayit-altyapisi/HANDOFF.md`
§5'te tam hâlleri var: İddaa'nın marj farkı (Avrupa konsensüsüne göre bulunan value TR'de
value olmayabilir), `Club-Football-Match-Data` lisans zinciri (ticari lansman öncesi
avukat), Transfermarkt `robots.txt`, Jev'in çok dilli doğruluğu, Highlightly planında
oran olup olmadığı.

---

## 8. Faz 1 merge adımı (Task M, 2026-09-19) — `fetch-venues` bilinçli olarak TEK stadyum topluyor

**Bulgu değil, kasıtlı kapsam kararı — ama sessizce varsayılmasın diye burada.**
`src/football_edge/collectors/venues.py:VENUES` şu an tek girdi taşıyor:
`VenueSpec(home_team="Galatasaray", qid="Q81492")`. `fetch-venues` bugün yalnız Galatasaray'ın
ev sahibi maçları için stadyum koordinatı ve maç-saati havası topluyor — Süper Lig'deki
diğer 17 takım, hatta Faz 0'ın odds toplayıcısının izlediği diğer beş ligin HİÇBİRİ için değil.

**Neden genişletilmedi (Ruling R44, coordinator):** `declared_paths`in TEK girdi taşıması
(`config/sources.yaml`, wikidata kaydı) bu sınırı ZORUNLU KILMIYOR — `declared_paths` kapının
çevrimdışı denetimi için TEMSİLİ yollardır, çalışma zamanında her gerçek istek `fetch_text`
içindeki `guard_path` ile AYRI AYRI doğrulanır (tek beyan edilen yol zaten bu şekli kapsar).
Asıl kısıt: genişletmek bir takım→QID (Wikidata varlık kimliği) eşlemesi gerektirir, ve bu TAM
OLARAK Task 11'in işi (kaynaklar arası varlık eşleme, Jev `Choice`). Şimdi elle tutulan ikinci
bir eşleme yazmak, Task 11'i onu ya devralmak ya da silmek zorunda bırakırdı — iki kez yazılan
iş. Bu yüzden kayıt MİNİMAL kalıyor: `declared_paths`e yeni bir stadyum eklemek + `VENUES`e yeni
bir `VenueSpec` eklemek yeterli olurdu (kod bunu destekliyor, mimari bir engel yok), ama bunu
YAPMAK Task 11'in gerçek varlık-eşleme altyapısını beklemeli.

**Yanlışsa bedeli:** Faz 1 boyunca yalnız Galatasaray'ın maç-saati havası toplanır; diğer
takımların stadyum/hava özelliği modele hiç girmez. Task 11 tamamlandığında bu kayıt (ya da
onun yerini alacak gerçek eşleme) genişletilmeli — genişletilmediği fark edilmeden Faz 2'ye
geçilirse "hava özelliği var" varsayımı yanlış olur.

Ayrıca (küçük, aynı görev): `config/sources.yaml`nin ajansspor kaydı artık `/sitemap` (index)
ve `/sitemap/news` (urlset) declared_paths'lerinin İKİSİNİ de taşıyor, ama `collect_news`
yalnız `/sitemap/news`i fetch ediyor — `/sitemap` beyan edilmiş ama alt-sitemap keşfi
uygulanmamış bir giriş noktası (bkz. `task-M-report.md`, M4).

---

## 9. Faz 1'den devreden borç (`faz-1-toplayicilar`, 2026-09-19)

Faz 1'in devir belgesi: `docs/phases/01-toplayicilar/HANDOFF.md`. **Kapının ölçmediği
şeyler orada §3'tedir** ve burada tekrarlanmaz — bu bölüm, o §3'ün üstüne, **kapatılması
gereken somut borcu** taşır. Hepsi görüldü ve adıyla ertelendi.

Kapanmış olanlar burada yeniden açılmasın diye tek satırda: `collect.py`'nin 800 satır
sınırı üç bölmeyle kapandı (R11/R50/R53 → 515 satır); `scripts/` kapı kapsamına alındı
(R15); §5.3'teki bayat `mypy` kapsamı düzeltildi; `tff.py`'deki ölü `LOGGER` R36'nın
uygulamasıyla gitti; son bütün-dal incelemesinin düzeltme turunda (`4158f81`) §9.1b (#M13),
§9.1e (#M20), §9.2a (#M11; kapsamı `28cbd4f`'de tamamlandı), §9.2b (#M10) ve §9.3j'nin
fetched ⊆ declared yarısı (#M28) kapandı
— onlar aşağıda satırlarında KAPANDI diye işaretli, tarihi kayıt olarak duruyor.

### 9.1 Kaynak kayıt defteri ve `kaynak-politikası` adımının delikleri

| # | Nerede | Ne |
|---|---|---|
| 9.1a | `sources.audit_offline` | `terms_url` yalnız **boş-değil** diye kontrol ediliyor; URL şekli ya da erişilebilirliği değil. `access_basis: api_terms` kaynakların tek kanıtı bu alan |
| 9.1b | `sources.load_sources` | **KAPANDI (son inceleme, #M13):** `sources._validate` liste olmayan `declared_paths`i adıyla reddediyor (`test_registry_rejects_a_scalar_declared_paths`). ~~**Tip doğrulaması yok.** `declared_paths` skaler bir dize yazılırsa Python onu KARAKTERLERE böler ve kapı harf harf yol sorar — sessiz ve anlamsız bir "ölçüm"~~ |
| 9.1c | `access_basis: api_terms` | Bypass **host genişliğindedir**: o kaynakta `declared_paths` atıl kalır ve bunun testi yok. Bugün tek `api_terms` kaynak Open-Meteo |
| 9.1d | `openmeteo` kaydı | `/v1/forecast` zorunlu query parametresi taşıyor; çıplak yol "ölçülmüş" sayılmamalı |
| 9.1e | `sources.audit_offline` | **KAPANDI (son inceleme, #M20):** `enabled` + `access_basis: robots` + boş `declared_paths` artık adıyla bir ihlal (`test_enabled_robots_source_with_empty_declared_paths_is_a_violation`; `api_terms` kaynakta yanlış alarm vermediği de sınanıyor). ~~`enabled: true` ama `declared_paths: []` olan bir kaynak denetimden **hiçbir şey ölçmeden** geçer~~ |
| 9.1f | `collect.py` + `scripts/robots_drift.py` | `SOURCES_PATH` / `ROBOTS_DIR` iki yerde ayrı ayrı hardcoded — biri değişirse diğeri sessizce ayrışır |
| 9.1g | `sources.allows` | `bool(parser.can_fetch(...))` artık gereksiz sarmalayıcı (`protego` zaten `bool` döner) |
| 9.1h | `declared_paths` ↔ toplayıcılar | Yalnız **fetched ⊆ declared** bağlı (#M28, `test_each_collectors_fetched_path_is_declared`). Ters yön — beyanlı ama hiç fetch edilmeyen yol — **hiçbir testle bağlı değil**: `pageID=246` bu fazın sonuna kadar böyle yaşadı, ajansspor `/sitemap` bilinçli. Robots açısından zararsız yön, ama R7'nin "beyan = gerçek istek" sözleşmesi o yönde prose (R59; HANDOFF §3.9/32) |
| 9.1i | `scripts/robots_drift.py` → `main` | Anlık görüntüsü OLMAYAN bir kaynağı **sessizce atlıyor** (`continue`, satır basılmıyor). `enabled` kaynaklarda `audit_offline` eksik anlık görüntüyü zaten ihlal sayıyor; kapalı ve anlık görüntüsüz bir kaynak ise ölçülmüyor ve bu hiçbir yerde yazılmıyor. Bugün gizli: yedi kaynağın yedisinin de anlık görüntüsü var (son inceleme M-9) |

### 9.2 Workflow regresyon yolları — ~~en önemlisi burada~~ **en önemlisi (9.2a) KAPANDI**

**9.2a (KAPANDI — son inceleme, I-3/#M11; ÖNEMLİ, kalıcı veri kaybına giden yoldu).**

> **Bu madde artık ERTELENMİŞ bir sorun DEĞİL — tarihi bir kayıt olarak tutuluyor.**
> `tests/test_workflows.py::test_no_workflow_besides_seal_and_snapshot_shares_the_odds_collect_group`
> `seal.yml`in grubunu okur, `.github/workflows/` altındaki `*.yml` VE `*.yaml` dosyalarını
> dinamik tarar ve `seal.yml`/`snapshot.yml` DIŞINDA o grubu üst düzeyde YA DA herhangi bir
> job'da — mapping (`{group: odds-collect}`) ya da skaler (`concurrency: odds-collect`)
> biçimde — bildiren her workflow'da kırmızı verir. Grup adı dize olarak karşılaştırılır:
> `${{ }}` ifadesiyle üretilen bir ad değerlendirilmez. İlk sürüm (`4158f81`) yalnız üst
> düzeyi ve `*.yml`i okuyordu; yeniden inceleme job düzeyindeki ve `.yaml` dosyasındaki grubun
> kaçtığını gösterdi, `28cbd4f` kapattı (R62). Beş durum da mutasyonla kırmızı kanıtlandı:
> üst düzey ve job düzeyinde iki biçim, artı atılabilir bir klonda bir `.yaml` workflow'u.

Hiçbir test `full-scan.yml`in
**concurrency bloğunun YOKLUĞUNU** sabitlemiyor. Dosyada yalnız bir yorum var
(`# concurrency: BİLİNÇLİ OLARAK YOK`). İleride biri `group: odds-collect`i sessizce geri
eklerse GitHub, aynı gruptaki bekleyen run'ı yenisi geldiğinde **İPTAL EDER**: 30 dakikalık
tam tarama, 15 dakikada bir koşan mühür turlarını düşürür → `EXIT_MISSED_SEAL` →
**kapanış fiyatı KALICI kayıp.** Faz 0'ın önlemek için var olduğu tek sonuç. Bugün yalnız
elle inceleme yakalar.

**9.2b (KAPANDI — son inceleme, #M10, R56).**

> **Tarihi kayıt.** `_contents_permission` hem mapping'i hem `read-all`/`write-all`
> kısayolunu okuyor. Aynı mutasyon (`permissions: write-all`) artık çıplak `AttributeError`
> değil temiz bir `AssertionError` veriyor — job seviyesinde job'u adıyla anarak, üst düzeyde
> "salt-okunur olmalı" diyerek (RED → GREEN kanıtlı).

`tests/test_workflows.py`'nin job-permission kontrolü, YAML skaler kısayolu
(`permissions: write-all`) karşısında temiz bir assertion yerine `AttributeError` veriyor.

**9.2c.** `full-scan.yml`in `WORKFLOWS` demetinden çıkarılma gerekçesi yalnız görev
raporunda; tuple'a bir yorum satırı gerekiyor.

### 9.3 Toplayıcılardaki somut kusurlar

| # | Nerede | Ne |
|---|---|---|
| 9.3a | `collectors/results.py` → `_goals` | `raw.lstrip("-").isdigit()` kullanıyor, yani **`"-5"` geçiyor** ve temiz bir `ContractViolation` yerine Postgres check kısıtına çarpıyor. Gürültülü başarısız oluyor, sessiz değil — ama yanlış katmanda |
| 9.3b | `collector.fetch_text` | `_MAX_REDIRECTS = 5` sınırı **hiçbir testle tetiklenmiyor**; `Location`'ı boş bir 3xx aynı URL'yi 5 kez tekrar ister sonra patlar |
| 9.3c | `collectors/footystats.py` | `thead`/`tbody` seçimi hâlâ **özyinelemeli** (satır ve hücre seçimi değil). Bugün güvenli; iç içe tablo gelirse değil |
| 9.3d | `collector.assert_schema` | FootyStats `required` kümesi `matches_played`ı atlıyor — oysa makul-aralık sınırının BÖLENİ o |
| 9.3e | `collectors/footystats.py` | Ayrıştırılamayan bir `tbody` satırı artık **tüm ligi düşürüyor** (istenen davranış, R31); FootyStats `tbody`ye reklam/footer satırı koyarsa etkisi geniş olur |
| 9.3f | `collectors/*` | Kaynak kaydı yoksa **çıplak `StopIteration`** — adlandırılmış bir hata değil |
| 9.3g | `collectors/venues.py` | `except` mesajı artık `_due_matches` arızasında da "koordinat toplanamadı" diyor. Tanısal olarak yanıltıcı; **sayaçlar doğru** |
| 9.3h | `tests/test_footystats.py` | Fixture yolu **CWD-bağımlı**; deponun diğer iki fixture testi `__file__` tabanlı |
| 9.3i | `leagues.py` | Kök anahtar `ValueError` dalı testsiz |
| 9.3j | (test boşluğu) | **YARISI KAPANDI (son inceleme, #M28):** etkin liglerin `footystats_path`inin `declared_paths`te olduğunu artık `test_each_collectors_fetched_path_is_declared` sabitliyor; ters yön (beyanlı ama hiçbir etkin ligin istemediği yol) açık — §9.1h. ~~`leagues.yaml`ın `footystats_path`i ile `sources.yaml`ın `declared_paths`ini **bağlayan hiçbir test yok** — ikisi sessizce ayrışabilir~~ |
| 9.3k | (test boşluğu) | `main(["fetch-footystats"])` CLI seviyesinde `EXIT_LEAGUE_FAILED` testi yok; kapsam fonksiyon seviyesinde duruyor |
| 9.3l | `collectors/tff.py` | `_text(node: Any)` `mypy --strict`i o noktada fiilen devre dışı bırakıyor |
| 9.3m | `tests/test_tff.py` | `test_parses_this_weeks_fixtures` (`>=5`) artık `==62` testi tarafından kapsanıyor; **bağımsız olarak kırmızı veremez** |
| 9.3n | `fetch.py` | CLI arıza izolasyonu **tekdüze değil**: yalnız `_fetch_tff_command` toplayıcısını `try/except → EXIT_SOURCE_FAILED` ile sarıyor. footystats/venues/news/results'ta kurulum düzeyindeki bir arıza (bozuk bir YAML kaydı; footystats/venues'ta kapalı kaynak ya da eksik robots anlık görüntüsü; results'ta eksik `ODDS_API_KEY`) lig/kaynak izolasyonunun DIŞINDA kalır ve `main()`e çıplak traceback olarak çıkar, exit 1. Hepsi gürültülü; tutarsız olan operatör deneyimi (son inceleme M-3) |
| 9.3o | `collectors/news.py` → `_sitemap_item` | **Kısmî kayıp sessiz:** `<loc>`suz bir `<url>` için `None` döner ve bunları kimse saymaz; yalnız TOPLAM kayıp hata verir. footystats (R31) ve tff (R36) kısa-düşüş korumasına sahip, news değil. Düzeltme, robots filtresinin BİLEREK düşürdüğü URL'leri kayıptan ayırarak saymalı (son inceleme M-4; HANDOFF §3.9/35) |

### 9.4 Varlık eşleme ve Jev

| # | Nerede | Ne |
|---|---|---|
| 9.4a | `jev.py` | `probabilities` Protocol'den geçiyor ama **hiçbir yerde okunmuyor/saklanmıyor.** Spec §5.2 "ham yargıları sakla" diyor; en HAM olan atılıyor. Saklamak bir migrasyon ister |
| 9.4b | `mapping.py` | **`--threshold` bayrağı yok** — politika değişikliği kod düzenlemesi gerektiriyor (`DEFAULT_THRESHOLD = 0.75`) |
| 9.4c | `mapping.py` | `LOGGER` tanımlı, hiç kullanılmıyor (brief'ten miras) |
| 9.4d | `entity_aliases` | **Üretimde hiçbir şey OKUMUYOR.** Yazan var (`write_aliases`), tüketen yok — yani yanlış bir eşleme bugün hiçbir çıktıyı etkilemiyor ve tam bu yüzden fark edilmez |
| 9.4e | `collect.py` → `map-entities` | `--source tff` "gözlem yok" ile **exit 0** veriyor — "bu kaynak `team` türü hiç üretmiyor"dan ayırt edilemez (TFF `fixture_official` yazıyor). İkinci bir takım kaynağı gelene kadar kozmetik (son inceleme M-8) |

### 9.5 Boyut kılavuzunu aşan yerler

Proje kuralı: fonksiyon <50 satır, dosya 200-400 normal / 800 sert sınır.

| Nerede | Satır | Not |
|---|---|---|
| `collectors/footystats.py` → `parse_xg_table` | 69 | Bu dalda kabul edildi; `parse_referees` onu ayna aldı |
| `collectors/tff.py` → `parse_referees` | 59 | R36'nın istediği kısmî-kayıp koruması ekledi |
| `collectors/venues.py` → `collect_venues` | ~105 | |
| `mapping.py` → `resolve` | 52 | Eklenen 13 satır R51'in birebir istediği düzeltme |
| `collectors/news.py` | 489 | 200-400 bandının üstünde, 800 sert sınırının altında |

**Karar (R54): kod değil KURAL değişir.** 50 satır, kapının ölçmediği bir KILAVUZDUR:
`pyproject.toml`daki ruff seçimi `select = ["E", "F", "I", "UP", "B", "SIM", "T20"]` ve
bunların hiçbiri fonksiyon uzunluğu ölçmüyor (satır uzunluğu E501 ölçülüyor, fonksiyon uzunluğu
değil). Gerekçe (son incelemenin önerisi): `parse_referees`, `collect_venues` ve `resolve`daki
aşım bir incelemenin TALEP ETTİĞİ düzeltmedir (R36 kısa-düşüş koruması, R49 izolasyon, R51
üyelik kontrolü) ve fonksiyonlar tutarlı. İleride bölünmeye değer tek fonksiyon
`collect_venues`: maç başına hava döngüsü ayrı bir fonksiyona çıkarılır. `news.py`nin 489
satırı kabul (#M40): 800'ün altında, adaptör/bağlama dikişi büyürse bölünmeye hazır.

### 9.6 Ölçülmeyen eksenler (Faz 2'nin tasarımını etkiler)

**9.6a — Gerçek kaynak bayatlığı ölçülmüyor.** `assert_fresh` yalnız KAYNAĞIN verdiği
`observed_at` üzerinde anlamlıdır (R23); toplayıcı kendi `now`unu basıyorsa iddia her zaman
doğrudur. Asıl ölçüm — **`content_hash`in N turdur DEĞİŞMEMESİ** — ertelendi. Bugün "kaynak
dondu" ile "kaynak aynı veriyi veriyor" **ayırt edilemiyor.**

**9.6b — `cur.rowcount`un `executemany` sonrası davranışı canlı Postgres'e karşı
doğrulanmadı (R35).** Etkilenen şey **raporlanan sayı**dır, yazılan satırlar değil:
`WHERE EXISTS` ve `ON CONFLICT` sunucu tarafında.

**9.6c — `source_observations`ın hash zinciri YOK** ve bu bilinçli (`0002_sources.sql`
başındaki yorum). Özellik girdisi kurcalanırsa **dış çıpa bunu göstermez.** §2.1'in yetki
boşluğu bu tabloları da kapsıyor ve Faz 1 tablo sayısını üçe çıkardı.

**9.6d — `contract` testleri canlı sayfayı değil KAYDEDİLMİŞ fixture'ı ölçer.** Google News
adaptörünün **hiç contract testi yok**: sentetik fixture canlı gerçekliğe karşı yeniden
ölçülemediği için marker bilerek kaldırıldı.

**9.6e — `latest_observations` geri dönen bir değerde ARADAKİ satırı döner (son inceleme
I-5).** UNIQUE kısıtı `(source_id, entity_kind, entity_key, content_hash)` ve hash `observed_at`i
dışlıyor: X → Y → X'in üçüncü yazımı `ON CONFLICT DO NOTHING` ile düşer, "en yeni" **Y** çıkar.
Bugün etki sıfır (tek okuyucu `mapping.resolve_source_aliases`), ama Faz 2 bu deponun "en
yeni"sini güncel durum sanmamalı. **Düzeltme migrasyon ister:** anahtar başına SON hash'e karşı
tekilleştir. Son incelemenin önerisi: 9.4a'yla (`probabilities`i saklamak da migrasyon) birlikte
karar verilsin. Sınırlama `latest_observations` docstring'inde ve HANDOFF §3.9/31'de yazılı.

**9.6f — `match_results`in içerik tekilleştirmesi yok (son inceleme M-7).** Birincil anahtar
`(match_id, observed_at)` ve her koşu kendi `now`unu basıyor; `daysFrom=3` tamamlanmış bir maçı
üç gün boyunca döndürdüğü için günde bir koşuda maç başına ~3 özdeş satır birikir. "Gözlem"
semantiği olarak bilinçli — ama Faz 2'nin okuyucusu maç başına EN YENİSİNİ almalı.

**9.6g — `EXPECTED_MIN_CONTRACT` bir TABAN ve zamanla aşınır (son inceleme M-2).** `verify.sh`
toplanan contract sayısını `-lt` ile karşılaştırıyor: sayıyı artırmadan eklenen testler görünmez,
sonra aynı sayıda kaldırma da fark edilmez. Ayrıştırma bugün doğru (18) ve biçim değişirse 0'a
düşüp kırmızı verir (doğru yönde kapanır). Seçenek: `-ne` ile tam eşitlik + zorunlu bump, ya da
aşınmayı sabitin yorumuna yazmak. HANDOFF §3.9/33.

**9.6h — Kalibrasyon raporu provenance taşımıyor (son inceleme M-5).** `CalibrationReport`ta
`measured_at` de etiket dosyasının hash'i de yok; `check-languages` raporun VAR olduğunu ve
`production_ready()`yi geçtiğini sorar, hangi etiketlere karşı ne zaman ölçüldüğünü sormaz. Bugün
etkisiz (rapor yok, her dil `false`) — ilk gerçek `calibrate`ten ÖNCE eklenmeli. HANDOFF §3.9/34.

**9.6i — Secret tarayıcısının isim listesi ELLE tutuluyor (R60).** `scripts/check_secrets.sh`
dört isim kalıbı biliyor (`TYPESAFE_API_KEY` son incelemede eklendi, I-2); hiçbir şey listeyi
`.env.example`ten türetmiyor. `.env.example`teki adları desene karşı sınayan bir test SONRAKİ
unutmayı yakalardı — yeni yetenek olduğu için düzeltme turunda yapılmadı. HANDOFF §3.8/28.

### 9.7 TFF: VAR/AVAR görünür ama toplanmıyor — PFDK hiç uygulanmadı

`pageID=600` hakem atamalarını **rol işaretleriyle** yayınlıyor: `(H)` hakem, `(Y)` yardımcı,
`(D)` dördüncü, **`(V)` VAR, `(A)` AVAR** (ölçüldü: tek turda V=11, A=11). Toplayıcı yalnız
`referee` alanını yazıyor, çünkü `Observation` sözleşmesi tek bir hakem alanı istiyor.

> **Bir zamanlar bu maddenin yerinde "sayfada `VAR` dizesi hiç geçmiyor" yazıyordu ve o
> YANLIŞTI.** Ölçüm düz kelimeyi aradı, rol işaretini değil. Düzeltmenin tam hikâyesi
> `docs/phases/01-toplayicilar/HANDOFF.md` §6.1'de — aynı yanlış yöntem `pageID`yi de
> yanlış "düzelttirmişti".

Ayrıca: `__VIEWSTATE` postback'i engellendiği için **yalnız BU HAFTA** alınabiliyor; geçmiş
hafta ve diğer ligler kapalı.

**PFDK hiç uygulanmadı (R57).** Spec §3.1'in "Hakem + ceza (TR)" satırı TFF'den "PFDK
kararları" bekliyor ve plan Task 6'nın başlığı onu adlandırıyor; ama toplayıcı yok, beyanlı yol
yok, veri yok. `pageID=246` beyanlıydı ama hiç fetch edilmiyordu ve son incelemede kaldırıldı —
PFDK sayfası olduğu bile doğrulanmadı (Task 6 raporu "muhtemelen PFDK" diyor). Bir PFDK
toplayıcısı yeni bir iştir, sayfa şekli ölçülerek başlar. HANDOFF §3.9/30.

### 9.8 Küçük artıklar

| Nerede | Ne |
|---|---|
| `anchors.expected_anchor_names` | Unborn-HEAD dalı "geçmiş okunamıyor"u "geçmiş boş"a indirgiyor; fonksiyon 62 satır (bir `_git()` yardımcısı isterdi) |
| `collect._first_anchor_break` | Docstring `--full` eklendikten sonra bayat |
| `tests/test_verify_chain.py` | İki testte ~15 satır aynı git-repo kurulumu tekrar ediyor; test gövdelerinde yerel `import subprocess` (4 yer); kullanılmayan `capsys: Any` parametresi |
| `tests/test_sources.py` (satır 174/184) | YAML loader testinde hâlâ `user_agent: ClaudeBot/1.0` dizesi var. **HTTP isteği değil**, yalnız loader kurgusu; R9'un asıl konusu (satır 28-36, 80-87) artık açıkça belgelenmiş durumda — bu ikisi kalan kozmetik artık |
| `tests/test_venues.py` | Takas edilmiş lat/lon testi sentetik payload'da `latitude`u önce yazıyor, yani saf konumsal okumayı ayırt etmiyor (gerçek risk olan dönüş sırası takasını yakalıyor — çerçeveleme notu) |

## 10. İşletme — mühür olayı (2026-09-21, Faz 1 merge'ünden sonra bulundu)

`seal.yml` 2026-09-19 14:39'dan 09-21 14:15'e kadar 16 kez koştu (`*/15` cron'u ~203 tur
beklerdi) ve bu turların 15'i `EXIT_MISSED_SEAL` verdi: 47 maçın kapanış fiyatı kalıcı olarak
kayıp. Düzeltme: pg_cron → `workflow_dispatch` (`db/migrations/0003_seal_dispatch.sql`; snapshot
için `0004_workflow_dispatch.sql`; `docs/RUNBOOK.md` §3). Açık kalanlar:

| # | Ne | Neden önemli |
|---|---|---|
| 10a | ~~**Kırmızı bir tura bakan kimse yoktu.**~~ **KAPANDI (2026-09-22):** ilk canlı döngü — `🔴 collect-daily kırmızı` #1 09:29 UTC açıldı (github-actions, `ops-alert` etiketi iliştirildi, etiket açıklamasıyla oluşturuldu), 10:57:58'de yeşil turla "yeşile döndü" yorumuyla kapandı (run 35718803834) | Açık kalan tek koşul: haber GitHub'ın issue bildirimidir; e-posta depo sahibinin bu depoyu izleme (Watch) ayarına bağlı ve bu oturumda ölçülemedi (`gh` token'ında `notifications` yetkisi yok). Kişinin kendi token'ıyla açtığı issue bildirim üretmez: yerel iş bu yüzden raporlar, alarmı github-actions açar (R74) |
| 10b | Kaçan maç 24 saat boyunca her turda yeniden raporlanıyor | Tek bir kayıp, bir gün boyunca her 15 dakikada bir kırmızı üretir; gerçek yeni kaybı gürültüde saklar. "Yalnız YENİ kayıp" ayrımı şema değişikliği ister (raporlandı damgası) |
| 10c | Dispatch tokenı iptal edilebilir (süreli seçilirse süresi de dolar) | O durumda mühür yalnız seyrek yedek `schedule`la koşar; snapshot ve toplayıcılar hiç koşmaz; yedek turdaki bekçi kendi alarmını açar, ama o tur da seyrek olduğundan haber saatler sürebilir. Varsayılan süresiz token (RUNBOOK §3.2) |
| 10d | Kredi bütçesi ilk kez gerçekten kullanılacak | Mühürler bugüne kadar çoğunlukla kaçtığı için ayda ~314 kredilik mühür payı hiç tüketilmedi; güvenilir tetikle ay sonuna doğru `EXIT_QUOTA_EXHAUSTED` görülebilir. Erken uyarı var: bekçi kalan kredi 60'ın altına inince kendi alarmını açar (RUNBOOK §3.6) — ama bekçi seyrek yedek turda koşar (10f) |
| 10e | `snapshot.yml`in tek tetiği pg_cron (`snapshot-dispatch`); GitHub `schedule`ı kaldırıldı | İki tetik aynı gün iki tur, yani iki kat kredi demek. Bedeli: pg_cron durursa snapshot'ın yedeği yok — bekçi 30 saatte kendi alarmını açar |
| 10f | Alarmın kör noktaları | (1) Bekçi yalnız GitHub'ın seyrek yedek `schedule` turunda koşar: bayat tetik saatler sonra görünür, bekçi alarmı da ancak iki tetiği taze bulan sonraki yedek turda kapanır. (2) Alarm açıkken yeni bir kırmızı yeni bildirim üretmez, yalnız gövdeyi günceller — 10b'nin "yalnız YENİ kayıp" ayrımı gelene kadar açık alarm "son tura bak" demektir. (3) Alarm adımı `uv run` ile koşar: `uv` kurulmadan önce düşen bir tur (checkout, secret taraması) alarm açamayabilir. (4) GitHub'ın kendi "run failed" e-postaları (dispatch'i tetikleyen hesaba, hesap ayarına göre) `ops-alert`in tekilleştirmesinin dışındadır: kırmızı sürdükçe her tur ayrı bir e-posta olabilir |
| 10g | `publish-head` satır sayısını ve zincir başını İKİ ayrı sorguda okuyor (READ COMMITTED) | Arada bir yazım commit edilirse çıpanın `head`i `last_id` satırının hash'i olmaz. Otomatik turlarda risk düşük (seal ve snapshot aynı `odds-collect` grubunda); risk, elle çalıştırılan bir komutun bir turla çakışması. Düzeltme: tek ifade ya da REPEATABLE READ (Task A incelemesi, 2026-09-22) |
| 10h | Tek alarm iki toplayıcıyı örtüyor (`collect-daily`: tff, venues; footystats 2026-09-22'den beri kendi `footystats-local` alarmında, 10r) | Açık alarm yalnız gövdesi güncellenerek sürer: kırmızı kalan bir `fetch-tff`, ardından gelen ilgisiz bir `fetch-venues` arızasını bildirimsiz bırakır. İlk canlı turda gerçekleşti: footystats'ın her gün tekrarlayacak 403'ü alarmı kalıcı açık tutacaktı. Çözüm: gövdeye düşen komutların adı ya da toplayıcı başına başlık (C3 incelemesi) |
| 10i | Haber alarmı dalgalanabilir | `collect-news` günde 12 kez koşar; kararsız bir kaynak her dalgalanmada yeni issue + kapanış yorumu üretir. Çözüm: art arda iki kırmızıdan sonra aç (C3 incelemesi) |
| 10j | Hizmet şartları (ToS) periyodik olarak yeniden okunmuyor | robots.txt tarihi artık otomatik ilerliyor; elle 30 günlük yenileme, birinin kayıt defterine düzenli bakmasının tek anıydı. `api_terms` kaynakların (Open-Meteo) asıl erişim dayanağı ToS — değişirse kimse görmez (C4 incelemesi) |
| 10k | ~~`seal.yml` push'u yeniden denemiyor ve değişiklik olmasa da push'luyor~~ **KAPANDI (C6)** | Çıpa adımı yalnız commit varsa push'lar; ret gelirse `main`i merge edip en çok 3 kez dener (rebase/force yok); checkout `ref: github.ref` ile güncel ucu çeker, kuyrukta bekleyen tur bayat tabandan çakışmaz. Kalan: `main` dışı bir dalda elle tetiklenen seal, reddedilen push'ta `main`i o dala birleştirir (pg_cron hep `main`i tetikler) |
| 10l | `ops-alert` etiketinin açıklaması yalnız ilk oluşturmada yazılır | Etiket bir kez oluştuktan sonra koddaki açıklama değişirse canlı etiket eski kalır; elle `gh label edit` gerekir (C5 incelemesi) |
| 10m | `fetch-results` zamanlanmadı (R67) | `/scores` kredi harcar; ayda 500 kredilik bütçe snapshot + mühüre ayrılmış. Sonuç verisi elle koşulana kadar birikmez; Odds API plan kararıyla açılır |
| 10n | Loglarda sır redaksiyonu (C7) runner'da koştu (2026-09-22), maskelemesi hiç sınanmadı | Kök biçimleyici Odds/TypeSafe anahtarını, `DATABASE_URL`i ve parolasını (libpq + URL biçimleri) mesajda ve traceback'te gizler; yakalanmayan istisna `sys.excepthook` ile aynı yoldan geçer; httpx istek satırı susturuldu. Kapsam dışı: `threading.excepthook` (hat iş parçacığı açmıyor), `?password=` değerinde `%00` (libpq reddeder, yedek sorgu parametresini okumaz). **2026-09-22 ilk runner turları:** `collect-daily`, `collect-news` ve `seal` (09:30) loglarında `DATABASE_URL`in tamamı, parolası ve Odds anahtarı **0** kez geçiyor (sır basmayan sayım). Maskeleme yolunun kendisi SINANMADI: o turlarda hiçbir hata mesajı sır taşımıyordu |
| 10o | Kimlik bilgisi adları birden çok yerde elle tutuluyor | `_log_secrets`, `_require_env`, `db.connect`, `jev` — yeni bir secret eklenip listeye yazılmazsa hiçbir şey fark etmez. Tek liste + `os.getenv(` çağrılarını tarayan bir test (C7 incelemesi) |
| 10p | İki redaksiyon uygulaması var | `football_edge.redaction` (hat) ve `scripts/ops_alert.py`nin kendi `_redact`i (bekçi). Davranışları eşit ama ayrı; birleştirilmeli (C7 incelemesi) |
| 10q | Testlerde strict mypy çalışmıyor ve 4 eski `index` hatası var | Kapının mypy kapsamı `src scripts`; `test_workflows.py`deki `steps[opens]` (`opens` None olabilir) (C6 raporu; Faz 1 HANDOFF §3.8/27) |
| 10r | footystats GitHub runner'larında koşamıyor; iş Mac'te launchd ile koşuyor (R73–R75, RUNBOOK §3.9) | İlk canlı turda 6/6 lig 403 (Cloudflare veri merkezi IP'lerini geri çeviriyor; robots.txt runner'dan okunuyor), aynı kod ve kimlik Mac'ten 200. Kapatılanlar: sonuç `footystats-local.yml`e raporlanır ve alarmı github-actions açar (kullanıcının kendi token'ıyla açılan issue bildirim üretmezdi); raporlar bekçinin kalp atışıdır (72 sa); dört dilim + oturum açılışı gün içindeki kaçışı telafi eder; uyanışta ağ için 6 deneme. Kalanlar: Mac BÜTÜN GÜN kapalıysa o günün xG ara durumu kalıcı kaybolur; bir tur için katı süre sınırı yok (macOS'ta `timeout` yok, ağ adımları sınırlı); günlük dosyası döndürülmüyor; birden çok `DATABASE_URL` satırında ilki alınır (test edilmiyor) |
| 10s | TFF: bütün görevli hücreleri boş bir sayfa "henüz açıklanmadı" sayılır (R72) | Hakemler her hafta maçlardan birkaç gün önce açıklanır; o günlerde sayfa 63/63 boş hücre taşır (ölçüldü 2026-09-22) ve tur 0 yazıp yeşil kalır. TFF görevlileri `Hakemler` div'inin DIŞINA taşır ve hücreyi boş bırakırsa bu durum sayfadan ayırt EDİLEMEZ. Ayıracak olan zaman boyutu: maç iki günden yakınken hâlâ 0 gözlem → alarm. Ayrıca sezon arasında sayfa hiç maç satırı taşımazsa tur her gün `hiç maç satırı tanınmadı` ile kırmızı olur (ölçülmedi, sonraki yaz arası) |
| 10t | `main`in ucu her gün kişisel Mac'te, kullanıcının yetkisiyle ve insansız koşuyor (T2 incelemesi, güvenlik) | Runner'da kod geçici bir makinede, tur bitince geçersizleşen `issues: write` token'ıyla koşuyordu. Yerel işte GitHub hesabı ele geçirilip `main`e kötü bir commit itilirse (ya da `uv.lock` bozuk bir paket getirirse) kod bir gün içinde bu Mac'te, kullanıcının dosyalarına ve anahtar zincirine erişebilen bir süreç olarak çalışır. R74 GitHub token'ını işin süreçlerinden çıkardı; geliştirme sırasında aynı kod bu Mac'te zaten elle koşuyor. Kalıcı çözüm: işi yetkisiz ayrı bir macOS kullanıcısında koşmak (yönetici yetkisi, kullanıcı kararı) ya da yalnız imzalı commit'leri koşturmak. Şimdilik kabul edildi, kullanıcıya bildirildi |

## 11. R77 erişim kuralı testinin bilinen boşlukları (`tests/test_access_method_rule.py`, 2026-09-22)

Test kazara girişi durdurur; kasıtlı kaçışa karşı bir güvenlik sınırı değildir. İnceleme ve yeniden inceleme
37 + 60'tan fazla mutasyonla sınadı; kalanlar (R87 — ikinci tura alınmadı):

| # | Boşluk | Arkasındaki ağ |
|---|---|---|
| 11a | Ek taşıyan dizeler görünmez: `"camoufox==0.4"`, `"pip install camoufox"`, `os.system("uv pip install …")` | yok — çalışma zamanı kurulumu kilide girmez. İncelemecinin ölçtüğü iki denetim (yasak ad + sürüm işleci/`[`/`@`/`;`/`(`; kurulum fiili + ad) depodaki 1.098 dizede 0 yanlış pozitifle dört biçimi de yakalıyor — ucuz kapanır |
| 11b | Elle yazılmış proxy döndürme (ör. httpx `proxy=` döngüsü) ölçülmüyor; yalnız adı bilinen iki döndürücü (`ProxyRotator`, `requests-ip-rotator`) aranıyor. Docstring'in "ölçülmeyenler" listesinden bu madde düştü | yok |
| 11c | R80'in yol listesi `scrapling.spiders`, `core.ai`, `core.shell`, `cli`yi kapsamıyor (hepsi fetcher'lara ulaşır) | `scrapling/engines/static.py` import anında `curl_cffi` istiyor: kilit testi + çalışma zamanı `ImportError` |
| 11d | `import_module(name="camoufox.sync_api")` (anahtar biçimli alt modül), ad dizesiyle erişim (`__import__(..., fromlist=[...])`, `attrgetter`), iki kabuk yazımı (zsh kaçışlı `scrapling\[fetchers\]`, `"scrapling"[fetchers]`) | kilit testi (paket kurulu değilse çalışmaz) |
| 11e | Dize kuralının iki alt parçası (import köküyle `STRING_REASONS`, Scrapling modül yolu uzantısı) sabitsiz; neden aramasında Unicode büyük/küçük katlama `KeyError` (yine kırmızı) | — |
| 11f | Form 4 (`.Fetcher` gibi öznitelik adları) genel adlarda ileride yanlış pozitif verebilir | kırmızı verir, sessiz değil |

## 12. Faz 2 planından ertelenenler (2026-09-22)

| # | Ne | Neden önemli |
|---|---|---|
| 12a | Eski append-only tablolarda (0001–0005: `odds_snapshots`, `source_observations`, `match_results`) TRUNCATE tetikleyicisi ve RLS yok | Satır tetikleyicisi UPDATE/DELETE'i durdurur, TRUNCATE'i durdurmaz; RLS'siz tablo, Supabase'in API rolleri yetkiliyse REST'ten okunabilir. 0006/0007 ikisini de açıyor (R90) — eski tablolar ayrı bir migration ister (Supabase advisors ile birlikte bakılmalı). Aynı migration 0001'in tetikleyici mesajını da düzeltmeli: her tabloda "odds_snapshots" diyor (`tg_table_name` kullanılmalı; Task 3 incelemesi) |
| 12b | `HistMatch.odds` sözlük + float nesneleri: plan incelemesinin deneyi maç başına ~4,4 KB → ~240 bin maçta ~1,1 GB | Runner'a sığıyor; `ODDS_COLUMNS` sırasına hizalı bir demet belleği birkaç kat düşürür. Task 8 gerçek tepeyi ölçer |
| 12c | `hist_match` iki ayrı test yardımcısında (`tests/market_factory.py`, `tests/backtest_builders.py`) | Dalga 1'de paralel yazıldılar; birleştirme bir sonraki temizlikte |
| 12d | Plan yeniden incelemesinin kalan gözlemleri (plan §"ölçmeyecekler" 24): `_measure` yakalama genişliği testsiz, `load_matches`in gerçek anahtarlı pozitif yolu testsiz, EKSİK kilit dosyası exit 1 | Uygulama incelemelerinde kapanır |
| 12e | Ayrıştırıcının latin-1 geri dönüşü dosya başına hep-ya-hiç: tek bozuk bayt bütün dosyayı latin-1 çözer, takım adları bozulur (Task 1 incelemesi, Minor 4) | Kilit dev/holdout'ta yakalar; sonrası dönemde ve T7 eşleştirmesinde sessiz. Senkron raporu dosya başına kodlamayı loglamalı (Task 6) |
| 12f | `match_probs` bilinmeyen EVREDE sessizce `None` döner; `bool` sonuç kabul ediliyor (Ü/A'da `True` = "under"); küçük örnekte tek kesin ıskalama kalibrasyonu yakınsatmıyor ve mesaj yanlışlıkla "ayrışmış örnek" diyor (Task 2 incelemesi) | Çağıranlar bugün sabit kullanıyor; bir yazım hatası bütün veriyi sessizce düşürürdü |
| 12g | Ayrıştırıcı artıkları (Task 1 düzeltme turu): ek lig satırının `Date`'i `Season` ile çapraz denetlenmiyor; `"YYYY/YYYY"` ardışık yıl istemiyor; `float()` `"1_000"` ve `"1e1"`i fiyat sayıyor; `\d` ASCII olmayan rakamı eşliyor. Bilinen sağ mutantlar: M4 (cp1252 ≈ latin-1), M18 (ek ligin zorunlu sütunlarından `Season` düşer — satır yine `sezon boş` ile reddedilir), M20 (yalnız boşluk hücreli kayıt) | Kaynakta bugün görülmeyen biçimler; ilk gerçek senkronun ret nedenleri gösterir |
| 12h | Harness: Python yansıması (`sys._getframe(1).f_locals`, `gc.get_referrers`) `HistMatch`e ulaşır (Task 4 incelemesi) | Tip ayrımının dışında, harness kapatamaz → Task 11 raporuna "stratejiler düşmanca kod değildir" varsayımı yazılır |
| 12i | Holdout anahtarı: gerçek bir anahtarın mührü kopyalanarak sınırsız anahtar üretilebilir — sayılan şey AÇILIŞ, kullanım değil (Task 3 incelemesi) | Faz 3 `final_eval` işçilere anahtar değil SEÇİLMİŞ satır vermeli |
| 12j | Belge düzeltmeleri (Task 2 incelemesi): tasarım §6 "k ≥ 1" → "B ≥ 1 iken k ≥ 1"; iki yollu OvR kalibrasyonunda kesişim simetriyle ≡ 0 — Ü/A'da "kesişim ≈ 0" yanlılık yok demek değildir | Task 12'nin belge adımında (tasarım metni) ve Task 9 raporunda not |

## 13. Değerlendirilen dış araçlar (2026-09-22)

### 13a. `withqwerty/football-docs` — veri kaynağı DEĞİL; kurulmadı

Futbol veri sağlayıcılarının belgelerini yerel bir SQLite tam metin dizininde arayan stdio MCP sunucusu
("futbol verisi için Context7"; 24 sağlayıcı/kütüphane, çoğu olay ve tracking verisi: Opta, StatsBomb, Wyscout,
SkillCorner, Sportmonks, Sportradar…). Salt okunur inceleme `gh api` ile yapıldı (`38dadf5`/v0.11.1, üstüne
`bd224f6`); hiçbir şey klonlanmadı, kurulmadı, çalıştırılmadı. Pratikte tek kişilik bakım, 1.0 öncesi.

| Faz | Ne işe yarar | Hüküm |
|---|---|---|
| 0, 2, 3, 5 | Oran modellemesi yok: The Odds API, kapanış çizgisi, CLV, devig, piyasa verimliliği, Dixon-Coles, Kelly kapsanmıyor; football-data.co.uk yalnız URL deseni + Bet365 1X2 (kapanış, AH, Ü/A sütunları yok) | Yok |
| 1 | `docs/free-sources/contextual-story-joins.md` (hava, stadyum, yolculuk, Elo birleştirmeleri) ve sağlayıcı başına kimlik alanı notları | Yalnız okuma; tarifleri UYGULANMAZ (aşağıda) |
| 3–4 | Sportmonks belgeleri hakem, sakatlık, muhtemel 11, xG ve haber uçlarını listeliyor — bizim bilinen boşluklarımız (FBref kapandığından beri küresel hakem verisi yok; TR dışında kadro/sakatlık kaynağı yok) | Aday İZ: Süper Lig kapsamı ve fiyat belgede YOK → karar Sportmonks'un kendi şartları, fiyatı ve kapsamıyla (§3.2.1 `api_terms`, `terms_url`); bu depo üzerinden değil |
| 6–7 | Grafik tarifleri (xG zaman çizelgesi, skor şeridi, kadro) | Yalnız tasarım esini; ham içerik ve metin kopyalanmaz |
| — | Aynı kuruluşun **Reep** kimlik sicili (Wikidata'dan; eski v0 CC0 ama donmuş) — sağlayıcı kimliklerini eşler | Ayrı iz: yalnız kimlikli bir sağlayıcı eklenirse; bugünkü eşleşmemiz (The Odds API adı ↔ football-data adı) kimlik taşımaz |

Neden kurulmadı ve kurulursa koşulları:
- **Lisans belirsiz:** LICENSE dosyası yok; yalnız `package.json` ve README "MIT" diyor (metin ve telif sahibi yok).
  Derlemin çoğu sağlayıcı belgelerinin birebir taranmış metni — onların fikrî mülkü. Araç olarak okunabilir;
  metni ya da şartnameleri depomuza ve sayfalarımıza kopyalanmaz (§3.2/4).
- **Ücretsiz kaynak tavsiyeleri politikamızla ÇELİŞİYOR:** Understat için robots'tan söz etmeden kazıma
  (ölçümümüz `Disallow: /`); ClubElo'yu çalışan API diye sunuyor (ölçümümüz: kapatıldı; bir testi ölü adresi
  sabitliyor); Transfermarkt şartları yasaklarken ipucu, WhoScored için başlıklı tarayıcıyla kazıma, sahte başlık
  ve gizli istemci önerileri (§3.2.1 yasak listesi). football-data.co.uk için "ticari kullanım: Yes" kaynaksız —
  bizim sorumuz açık (ana spec §10/2). Bu MCP'yi kullanan bir ajan için bu tavsiyeler ONAYSIZDIR.
- **Ağ ve tedarik zinciri:** ağa çıkan tek araç `resolve_entity` (Reep: yerel DuckDB kopyası ya da elle verilen
  anahtarla API; tazelik denetimi `data.reep.football`a) — sorgulanan ad/kimlik üçüncü tarafa gider, kullanılmaz.
  Sunucunun talimatı ajanlara DuckDB indirme komutu önermelerini söylüyor — her indirme kullanıcı onayı ister.
  Önerilen `npx -y football-docs` sürüm sabitlemiyor; kurulursa sürüm sabitlenir.

## 14. Faz 2 yürütmesinden ertelenenler (2026-09-22)

Kaynak: yürütme defteri (`.superpowers/sdd/2026-09-22-faz2-tarihsel-taban/progress.md`, gitignored) — her
`minor (deferred)` satırı, park edilen işler ve Task 11 denetiminin açık bulguları; yinelenenler birleştirildi.
§12'de zaten duran madde burada tekrar yazılmaz, yalnız EKİ yazılır. Kapının ölçmediği eksenler (erteleme,
`Date` takviminin ölçülmediği ligler, katalog kilitte değil…) ayrıca `docs/phases/02-tarihsel-taban/HANDOFF.md`
§3'te. Her satırın bugünkü etkisi kendi "neden bekliyor" hücresinde; Critical/Important bulguların hiçbiri
ertelenmedi, hepsi kapatıldı.

### 14.1 Ayrıştırıcı ve senkron (`history/football_data.py`, `history/sync.py`, `0006`)

| # | Ne | Neden bekliyor | Ne zaman bakılır |
|---|---|---|---|
| 14a | `AvgC` doluluk kuralında iki test eksik: `_check_closing_coverage`'da `all` → `any` (K) ve kuralın yalnız `season > "1920"` koşulu (L) sağ kalıyor. Kod doğru (Task 1 yeniden incelemesi) | Yalnız test boşluğu; eksik: tek `AvgCD` boş örnek + "1920" sezonunda `_with_closing` örneği | Ayrıştırıcıya dokunan ilk görevde |
| 14b | §12e'ye ek: latin-1 geri dönüşünde BOM → `ï»¿Div` → HER satır `REASON_DIVISION` (gürültülü, dosya düşer). Senkron dosya başına kodlamayı hâlâ loglamıyor (R109: `parse_file` kodlamayı dışarı vermiyor) | Gürültülü, sessiz değil; logu eklemek T1 API'sini değiştirir | 12e ile birlikte; ilk "latin-1'e düştü" şüphesinde |
| 14c | Çok satırlı kayıt hata mesajı satır numarasını 0'dan sayar | Kozmetik | Ayrıştırıcıya dokunan ilk görevde |
| 14d | R111 yeniden ayrıştırma yolu (`sync.py` ~202–206) kırpmayı loglamaz — aynı dosya için yinelenen log satırı olmasın diye, BİLİNÇLİ | İlk ayrıştırma logluyor; ikinci yol aynı dosya | Değişmez; kayıt amaçlı |
| 14e | Task 6 artıkları: sahte DB docstring'i `memoryview` iddia ediyor (H, zararsız) · `_record_failure` `except` içinde: DB giderse kalan yollar atlanır (koşu yine KIRMIZI) · `history.yml` testi (L) yalnız env değerini sabitliyor, `all` girdisinin bildirimini değil · `forbid_ledger_mutation` mesajı "odds_snapshots" (→ §12a) | Hepsi gürültülü ya da kozmetik | 12a migration'ında / `history.yml`e dokunan ilk görevde |
| 14f | `sync.py` modül docstring'i yalnız R96'yı (`_load_all`) anıyor; R119'un korunan adları (`load_files`, `parse_file`, `_parsed`) eklenmeli | Belge; kural testte yaşıyor | Sonraki `sync.py` değişikliğinde |
| 14g | **Task 11 F3:** sezon pencereleri Haz–Tem çakışır; aynı `(lig, tarih, ev, deplasman)` iki sezon dosyasında olursa iki karar + çift Elo güncellemesi, kilit ikisini de özetler (R121) | **Ölçüldü: gerçek veride 0 yinelenen** (38 lig, DEV + sonrası) — bugün etkisiz | Her kilit yenilemesinde sayım; sıfırdan farklıysa Faz 3 ön koşulu (`_load_all`da dosyalar arası ikinci geçiş) |

### 14.2 Holdout erişimi (`tests/test_holdout_access_rule.py`)

| # | Ne | Neden bekliyor | Ne zaman bakılır |
|---|---|---|---|
| 14h | Ayrıştırıcının ÖZEL yardımcıları (`_decode` → `_records` → `_context` → `_row`) başka bir modülden dört özel adla çağrılırsa holdout satırı kurar; AST kuralı görmez (R119 yeniden incelemesi). Ham SQL / `store._LOAD_FILES` yalnız bayt verir | Kasıtlı yeniden kurma — hesaplanmış adla aynı sınıf (§12h, 12i); kural kazara girişi durdurur | İsteğe bağlı sertleştirme: `history/` dışından `football_data`/`store`un `_`-önekli adlarına erişimi yasaklayan genel kural. Faz 3 `final_eval`den önce |
| 14i | R119'un korunan adları genel (`parse_file`, `_parsed`): ilgisiz bir modülün yerel `_parsed`ı yanlış pozitif verir | Güvenli yönde hata (kırmızı, sessiz değil) | İlk yanlış pozitifte |
| 14j | §12d'nin güncel durumu: `_measure`in yakalama genişliği **KAPANDI** (R115 daraltıp sabitledi); `load_matches`in gerçek anahtarla holdout döndüren pozitif yolu hâlâ testsiz (Task 6 incelemesi A); EKSİK kilit dosyası exit 9 değil exit 1 + traceback — kapandığına dair kayıt yok | Faz 2 anahtar açmaz | Faz 3 `final_eval` (pozitif yol orada sınanır) |

### 14.3 Harness ve bilinen sonuçlar (`backtest/`)

| # | Ne | Neden bekliyor | Ne zaman bakılır |
|---|---|---|---|
| 14k | **Oracle kanaryasının eşiği ≥ 10 sa:** sonucu 10 saatten az erken sızdıran bir harness kanaryayı yeşil bırakır; 1–9 sa'i eski tam-an testleri yakalar, yalnız saatsiz maçlarda 1 sa'lik sızıntıyı yalnız `test_events.py::test_event_instants_come_from_the_timeline` yakalar. Keskinleştirme ölçüldü: takvime 12:15 UTC'de iki yuva (bir cuma, bir salı) eşiği **4 sa**'e indirir; 3 sa altı kendi-sonucu Oracle'ı için yapısal olarak erişilemez | Kanarya bugün 252 maçta 0 tahmin, sızdırılan harness'ta kırmızı — amacına yetiyor | `test_harness.py`ye dokunan ilk görevde (iki yuva, düşük maliyet) |
| 14l | **Task 11 F5:** Placebo tohumu maç kimliğine değil giriş SIRASINA bağlı — yeniden karıştırmada 1.200 seçimin 775'i değişir; bir lig eklenince K4 "başka bir sayı" verir (R121) | Sızıntı değil, tekrarlanabilirlik; sıra bugün belirlenimci (lig koduyla) | Katalog değişince / Faz 3; öneri: tohum `sha256(seed|lig|tarih|ev|deplasman)` |
| 14m | `REFERENCE_BOOK = "Avg"` `selftest.py` ve `evaluate.py`de iki kez; `backtest` CLI'ında exit 1 hem kırmızı kapı hem çöküş (brif bilinçli) | Açık kalmaz — tur yine kırmızı | `backtest/`e dokunan ilk görevde |
| 14n | K3'ün `resamples`i sabitlenmemiş (spy fikstüründe PSC yok — ek mutant sağ); K4 yöntem testlerinde (D/E) CLV payı ince: 8,2e-5 fark, `abs=5e-5` | Test hassasiyeti; kod doğru | Aynı |

### 14.4 Verimlilik, yöntem seçimi ve köprü (`market/`)

| # | Ne | Neden bekliyor | Ne zaman bakılır |
|---|---|---|---|
| 14o | Ü/A 2.5 marj/log-loss bootstrap'larının Ü/A `try` DIŞINDA oluşu sabitlenmemiş (OU_INCATCH sağ) · `SEED`/`LEVEL` tekrarı, "%95" sabit metin · `load_catalog`/`method_scores`/`candidates`'ın `ValueError`'ı traceback basar · k = 3 ince lig testleri `RESAMPLES`e bağlı · `efficiency.py` 400 satırı aşıyor (incelemede 502, `main`de 568; sert sınır 800) | Rapor doğru üretiliyor; hepsi kalite | `market/efficiency.py`ye dokunan ilk görevde (bölme ile birlikte) |
| 14p | BFEC'te `Σ 1/o < 1` (borsa düşük toplamı) Shin'de "eksik" sayılır → borsa kapsamı yanlılığı (Shin artık varsayılan değil, R118) | `exchange_gap` yalnız rapor | Borsa fiyatı modele girerse (Faz 3+) |
| 14q | `method_scores` penceresiz DEV kullanır (lig tablosu pencereli); yöntem seçimi örneklem içi — geliştirme raporunun sayıları hafifçe iyimser (Task 11 §3/5) | Holdout'a etkisi yok; Faz 3'te dev'de seçilmiş sabit yöntem meşru | Faz 3 walk-forward kurulurken |
| 14r | Köprü `pair()`: yinelenen (lig, Londra tarihi, adlar) anahtarında iki canlı maç aynı tarihsel satıra eşlenir → `n` şişer; sayılmıyor, loglanmıyor (Task 7 incelemesi) | Bugün n = 4, yineleme yok | Canlı örnek büyüdükçe (haftada ~60 maç); ilk şüpheli `n`de |
| 14s | Ölçüm tarihçesi `devig.py` ve `test_devig.py` yorumlarında tekrar ediyor (commit mesajında zaten var) — bayatlayan yorum riski | Kozmetik | Sonraki `devig.py` değişikliğinde |
| — | ~~Köprü CLI `--since` varsayılanı ≥ 2026-07-01~~ **KAPANDI** — Task 9 brifi varsayılanı `HOLDOUT_END` yaptı | — | — |

### 14.5 Park edilenler

| # | Ne | Neden bekliyor | Ne zaman bakılır |
|---|---|---|---|
| 14t | Faz 2 worktree'leri ve dalları: `.worktrees/wt-{parser,devig,lock,harness,sync,bridge,efficiency,selftest,r111,method,t11fix,measure}` ve `feat/faz2-*` dalları; uzak dal `measure/r104-width` (R104 ölçümünün geçici dalı) | Silme kullanıcı onayı ister; hepsi `main`e birleşti (measure hariç — main'e girmez) | Kullanıcı onayı gelince |
| 14u | CI'da `astral-sh/setup-uv@v5` bir kez 10 dk takıldı (hazırlık, rerun yeşil) | Tek olay | Tekrarlarsa adım düzeyi `timeout-minutes` |
