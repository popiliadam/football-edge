# football-edge — Ertelenen bulgular ve bilinen ödünleşmeler

**Kapsam:** Faz 0 (`faz-0-kayit-altyapisi`) boyunca bilerek ERTELENEN her şey.
Hiçbiri "unutuldu" değildir; her biri görüldü, tartışıldı ve şimdilik kabul edildi.

**Bu dosya neden var.** Kararların tamamı `.superpowers/sdd/2026-09-19-faz0-kayit-altyapisi/`
altında yaşıyordu ve o dizinin `.gitignore`'u tek satır: `*`. Yani her ruling, her
bulgu, her ertelenen madde **merge olmayacaktı**: Faz 1'i devralan mühendis temiz bir
`main` görecek ve bu listenin hiçbirini bilmeyecekti. Karar kaydının kendisi
gitignore'da kalmaya devam ediyor (süreç artığı); **sonuçları burada, izlenen bir
dosyada.**

Öncelik etiketi yok — sıra tematik. Faz 1 planı bu listeyi **tek tek** ele almak
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

### 1.2 İkiden fazla çıpa varsa aradakiler hiç sorulmuyor

`asked = anchors if len(anchors) == 1 else (anchors[0], anchors[-1])`. 30 günlük çıpa
birikince 28'i hiç okunmaz.

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

---

## 3. Mühür ve veri bütünlüğü

### 3.1 `matches.commence_time` hiç tazelenmiyor

`upsert_matches` `ON CONFLICT (id) DO NOTHING` kullanıyor: bir maç ertelenirse
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

### 4.1 Satır başına bir INSERT — ilk canlı tur ~4 dakika sürdü

`insert_snapshots` her satır için ayrı bir `cur.execute` atıyor: 3 717 satır =
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

`verify.sh`, `scripts/check_secrets.sh` ve üç workflow YAML'ı kapının **parçası** ama
kapı onları ölçmüyor. `tests/test_workflows.py` YAML'ları ayrıştırıp yapısal iddialar
kuruyor — bu bir linter değildir: ifade sözdizimi, geçersiz `uses` referansı, hatalı
girinti ancak runner'da patlar.

### 5.2 Eşzamanlılık gerçek Postgres'e karşı hiç sınanmadı

C2'nin kilidi var ve **ifade sırası** test ediliyor (sahte bağlantıyla), ama iki gerçek
oturumun serileştiği ölçülmedi. `pg_advisory_xact_lock`in gerçekten beklettiği, iki
paralel `collect snapshot` ile doğrulanmalı.

### 5.3 `mypy` yalnız `src`'yi görüyor; coverage ölçülmüyor

`files = ["src"]` — `tests/` tip denetiminden geçmiyor. `pytest-cov` kurulu değil,
kapıda eşik yok.

### 5.4 Workflow'ların hiçbiri bir runner'da koşmadı

`ci.yml` dâhil. Dal merge edilene kadar `schedule` de koşmaz (GitHub `schedule`'ı
yalnız varsayılan dalda onurlandırır). Merge sonrası **ilk koşu izlenmelidir.**

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
