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

Bu KASITLI bir maliyet ödünleşmesidir, gözden kaçmış değil: `seal.yml`in kendisi günde
~96 çıpa commit'i üretiyor, 15 dakikada bir tam geçmiş çekmek bu sıklıkla bileşip gerçek
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
> yalnız tetikleyici süre kısaldı. (Faz 1'in `full-scan.yml`i bilerek KENDİ grubunda —
> bkz. §9.2a: o ayrımı sabitleyen bir test YOK.)

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

### 4.2 Çıpa commit'i günde ~96 ek CI koşusu doğuruyor

`seal.yml` her mühür turunda `ledger/` altına commit atıp push'luyor; `ci.yml`
`push` ile tetiklendiği için her biri bir kapı koşusu demek. Depo public → Actions
dakikası ücretsiz, yani bugün yalnız gürültü. `paths-ignore` ile susturulabilir ama
bu kapıya filtre eklemektir; **bilinçli olarak yapılmadı.**

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
uygulamasıyla gitti.

### 9.1 Kaynak kayıt defteri ve `kaynak-politikası` adımının delikleri

| # | Nerede | Ne |
|---|---|---|
| 9.1a | `sources.audit_offline` | `terms_url` yalnız **boş-değil** diye kontrol ediliyor; URL şekli ya da erişilebilirliği değil. `access_basis: api_terms` kaynakların tek kanıtı bu alan |
| 9.1b | `sources.load_sources` | **Tip doğrulaması yok.** `declared_paths` skaler bir dize yazılırsa Python onu KARAKTERLERE böler ve kapı harf harf yol sorar — sessiz ve anlamsız bir "ölçüm" |
| 9.1c | `access_basis: api_terms` | Bypass **host genişliğindedir**: o kaynakta `declared_paths` atıl kalır ve bunun testi yok. Bugün tek `api_terms` kaynak Open-Meteo |
| 9.1d | `openmeteo` kaydı | `/v1/forecast` zorunlu query parametresi taşıyor; çıplak yol "ölçülmüş" sayılmamalı |
| 9.1e | `sources.audit_offline` | `enabled: true` ama `declared_paths: []` olan bir kaynak denetimden **hiçbir şey ölçmeden** geçer |
| 9.1f | `collect.py` + `scripts/robots_drift.py` | `SOURCES_PATH` / `ROBOTS_DIR` iki yerde ayrı ayrı hardcoded — biri değişirse diğeri sessizce ayrışır |
| 9.1g | `sources.allows` | `bool(parser.can_fetch(...))` artık gereksiz sarmalayıcı (`protego` zaten `bool` döner) |

### 9.2 Workflow regresyon yolları — **en önemlisi burada**

**9.2a (ÖNEMLİ, kalıcı veri kaybına giden yol).** Hiçbir test `full-scan.yml`in
**concurrency bloğunun YOKLUĞUNU** sabitlemiyor. Dosyada yalnız bir yorum var
(`# concurrency: BİLİNÇLİ OLARAK YOK`). İleride biri `group: odds-collect`i sessizce geri
eklerse GitHub, aynı gruptaki bekleyen run'ı yenisi geldiğinde **İPTAL EDER**: 30 dakikalık
tam tarama, 15 dakikada bir koşan mühür turlarını düşürür → `EXIT_MISSED_SEAL` →
**kapanış fiyatı KALICI kayıp.** Faz 0'ın önlemek için var olduğu tek sonuç. Bugün yalnız
elle inceleme yakalar.

**9.2b.** `tests/test_workflows.py`'nin job-permission kontrolü, YAML skaler kısayolu
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
| 9.3j | (test boşluğu) | `leagues.yaml`ın `footystats_path`i ile `sources.yaml`ın `declared_paths`ini **bağlayan hiçbir test yok** — ikisi sessizce ayrışabilir |
| 9.3k | (test boşluğu) | `main(["fetch-footystats"])` CLI seviyesinde `EXIT_LEAGUE_FAILED` testi yok; kapsam fonksiyon seviyesinde duruyor |
| 9.3l | `collectors/tff.py` | `_text(node: Any)` `mypy --strict`i o noktada fiilen devre dışı bırakıyor |
| 9.3m | `tests/test_tff.py` | `test_parses_this_weeks_fixtures` (`>=5`) artık `==62` testi tarafından kapsanıyor; **bağımsız olarak kırmızı veremez** |

### 9.4 Varlık eşleme ve Jev

| # | Nerede | Ne |
|---|---|---|
| 9.4a | `jev.py` | `probabilities` Protocol'den geçiyor ama **hiçbir yerde okunmuyor/saklanmıyor.** Spec §5.2 "ham yargıları sakla" diyor; en HAM olan atılıyor. Saklamak bir migrasyon ister |
| 9.4b | `mapping.py` | **`--threshold` bayrağı yok** — politika değişikliği kod düzenlemesi gerektiriyor (`DEFAULT_THRESHOLD = 0.75`) |
| 9.4c | `mapping.py` | `LOGGER` tanımlı, hiç kullanılmıyor (brief'ten miras) |
| 9.4d | `entity_aliases` | **Üretimde hiçbir şey OKUMUYOR.** Yazan var (`write_aliases`), tüketen yok — yani yanlış bir eşleme bugün hiçbir çıktıyı etkilemiyor ve tam bu yüzden fark edilmez |

### 9.5 Boyut kılavuzunu aşan yerler

Proje kuralı: fonksiyon <50 satır, dosya 200-400 normal / 800 sert sınır.

| Nerede | Satır | Not |
|---|---|---|
| `collectors/footystats.py` → `parse_xg_table` | 69 | Bu dalda kabul edildi; `parse_referees` onu ayna aldı |
| `collectors/tff.py` → `parse_referees` | 59 | R36'nın istediği kısmî-kayıp koruması ekledi |
| `collectors/venues.py` → `collect_venues` | ~105 | |
| `mapping.py` → `resolve` | 52 | Eklenen 13 satır R51'in birebir istediği düzeltme |
| `collectors/news.py` | 489 | 200-400 bandının üstünde, 800 sert sınırının altında |

**Kural koddaki birden çok yerde çiğneniyorsa ya kural ya kod değişmeli** — bu karar Faz 2'ye
bırakıldı, sessizce görmezden gelinmedi.

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

### 9.7 TFF: VAR/AVAR görünür ama toplanmıyor

`pageID=600` hakem atamalarını **rol işaretleriyle** yayınlıyor: `(H)` hakem, `(Y)` yardımcı,
`(D)` dördüncü, **`(V)` VAR, `(A)` AVAR** (ölçüldü: tek turda V=11, A=11). Toplayıcı yalnız
`referee` alanını yazıyor, çünkü `Observation` sözleşmesi tek bir hakem alanı istiyor.

> **Bir zamanlar bu maddenin yerinde "sayfada `VAR` dizesi hiç geçmiyor" yazıyordu ve o
> YANLIŞTI.** Ölçüm düz kelimeyi aradı, rol işaretini değil. Düzeltmenin tam hikâyesi
> `docs/phases/01-toplayicilar/HANDOFF.md` §6.1'de — aynı yanlış yöntem `pageID`yi de
> yanlış "düzelttirmişti".

Ayrıca: `__VIEWSTATE` postback'i engellendiği için **yalnız BU HAFTA** alınabiliyor; geçmiş
hafta ve diğer ligler kapalı.

### 9.8 Küçük artıklar

| Nerede | Ne |
|---|---|
| `anchors.expected_anchor_names` | Unborn-HEAD dalı "geçmiş okunamıyor"u "geçmiş boş"a indirgiyor; fonksiyon 62 satır (bir `_git()` yardımcısı isterdi) |
| `collect._first_anchor_break` | Docstring `--full` eklendikten sonra bayat |
| `tests/test_verify_chain.py` | İki testte ~15 satır aynı git-repo kurulumu tekrar ediyor; test gövdelerinde yerel `import subprocess` (4 yer); kullanılmayan `capsys: Any` parametresi |
| `tests/test_sources.py` (satır 174/184) | YAML loader testinde hâlâ `user_agent: ClaudeBot/1.0` dizesi var. **HTTP isteği değil**, yalnız loader kurgusu; R9'un asıl konusu (satır 28-36, 80-87) artık açıkça belgelenmiş durumda — bu ikisi kalan kozmetik artık |
| `tests/test_venues.py` | Takas edilmiş lat/lon testi sentetik payload'da `latitude`u önce yazıyor, yani saf konumsal okumayı ayırt etmiyor (gerçek risk olan dönüş sırası takasını yakalıyor — çerçeveleme notu) |
