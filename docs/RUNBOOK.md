# football-edge — Runbook

Kapının KIRMIZI verdiği ama kodun DOĞRU davrandığı durumların elle çıkış yolları.
Buradaki hiçbir adım kapıyı gevşetmez; hepsi insanın karar verip **gerekçesini yazdığı**
işlemlerdir.

---

## 1. Çıpa kilitlenmesi — `verify-chain` exit 1 veriyor ve sistem kendi kendine çıkamıyor

### 1.1 Nasıl tanınır

`seal` iş akışında **Zinciri doğrula** adımı düşer ve stdout şunu yazar:

```
ÇIPA UYUŞMAZLIĞI: çıpanın işaret ettiği satır (id=N) defterde yok (head-YYYY-MM-DD.txt)
```

ya da

```
ÇIPA UYUŞMAZLIĞI: id=N satırının içeriği çıpadaki hash'i üretmiyor (head-YYYY-MM-DD.txt)
```

Kilitlenmenin belirtisi tek bir kırmızı adım değil, **kendi kendine düzelmemesidir**:

- `verify-chain` exit 1 verince `seal.yml`'de sonraki iki adım (`publish-head` ve
  `Dış çıpayı commit'le`) **atlanır** → yeni çıpa yazılmaz.
- Yeni çıpa yazılmadığı için `_anchors()[-1]` de aynı eski dosyada donar → bir sonraki
  tur aynı uyuşmazlığı aynı dosyayla bulur.
- Yani her 15 dakikada bir aynı kırmızı; **çıpalar defteri bir daha hiç yakalayamaz.**

En sık meşru sebep: **defter yeniden kuruldu.** Dev reset, şemanın yeniden uygulanması,
`id` dizisinin kayması, tablonun başka bir projeden restore edilmesi. Bu hâllerde eski
çıpalar artık var olmayan bir deftere işaret eder.

### 1.2 Neden kapalı düşer — ve neden bypass bayrağı YOK

Ürünün sattığı şey kaydın **kurcalanmamış olduğunun kanıtı**. Kanıt üretemediğini
anladığında sistemin yapması gereken tek doğru şey durmaktır: kırık zincirin başı
dışarı yayınlanırsa kurcalanmış hâl çıpalanır ve çıpanın kanıt değeri biter.

Bu yüzden `--force`, `SKIP_ANCHOR_CHECK=1` ya da benzeri bir bayrak **eklenmedi ve
eklenmeyecek.** Böyle bir bayrağa ilk uzanacak iki kişi vardır: saldırgan ve gece
yarısı cron'u yeşile döndürmeye çalışan yorgun operatör. İkisi de aynı tuşa basar.
Çıkış yolu bir bayrak değil, **adı ve gerekçesi kayda geçen bir insan işlemidir.**

### 1.3 Önce teşhis: kilitlenme mi, kurcalama mı?

**Bu adım atlanırsa runbook'un kendisi bypass bayrağına dönüşür.**

Arşivleme, yalnız uyuşmazlığın sebebini **yazabiliyorsan** meşrudur:

| soru | evet ise |
|---|---|
| Defteri sen mi (ya da ekipten biri mi) yeniden kurdun? Tarih/komut biliniyor mu? | kilitlenme → §1.4 |
| `odds_snapshots` satır sayısı çıpadakinden AZ ve bunun bilinen bir sebebi yok mu? | **kurcalama şüphesi** |
| `id=N` satırı duruyor ama içeriği değişmiş mi? | **kurcalama şüphesi** |

Kurcalama şüphesinde **hiçbir çıpa taşınmaz.** Durulur, `ledger/` olduğu gibi bırakılır
(git geçmişindeki eski çıpalar tek dış kanıttır), durum bir insana eskale edilir.

### 1.4 Kurtarma — çıpalar TAŞINIR, **SİLİNMEZ**

Arşivlenen çıpa, taşıdığı kanıtı da götürür: o dosya bir daha karşılaştırılmayacağı
için, **o çıpanın kapsadığı dönem için kuyruk kesme kanıtı ortadan kalkar.** Bu bir
kayıptır; bu yüzden tek karşılığı vardır: **gerekçesi yazılır.**

`rm` YOK. `git rm` YOK. `ledger/head-*.txt` yalnız `ledger/archive/` altına taşınır:

```bash
# 1) Arşiv dizini ve GEREKÇE notu — çıpalardan ÖNCE yazılır.
mkdir -p ledger/archive
cat > ledger/archive/2026-09-19-defter-yeniden-kuruldu.md <<'NOTE'
# Çıpa arşivi — 2026-09-19

**Arşivlenen:** ledger/head-2026-09-18.txt, ledger/head-2026-09-19.txt
**Sebep:** Supabase projesi yeniden kuruldu (0001_init.sql yeniden uygulandı),
odds_snapshots id dizisi 1'den başladı; eski çıpalar artık var olmayan satırlara
işaret ediyor.
**Kim:** <ad> · **Ne zaman:** 2026-09-19T14:05Z
**KAYBEDİLEN KANIT:** 2026-09-17 → 2026-09-19 arası için kuyruk kesme (TRUNCATE +
yeniden zincirleme) tespiti artık yapılamaz. O döneme ait satırların dış kanıtı yok.
NOTE

# 2) Çıpaları TAŞI (silme değil — dosya git geçmişinde de, arşivde de durur).
git mv ledger/head-2026-09-18.txt ledger/archive/
git mv ledger/head-2026-09-19.txt ledger/archive/

# 3) Gerekçe ve taşıma AYNI commit'te gider: biri diğeri olmadan okunamaz.
git add ledger/archive/2026-09-19-defter-yeniden-kuruldu.md
git commit -m "chore: çıpalar arşivlendi — defter yeniden kuruldu (kanıt kaybı notu ekte)"
```

`ledger/archive/` altındaki dosyalar zincir doğrulaması için **okunmaz**
(`_scan_anchors` yalnız `ledger/head-*.txt` glob'una bakar, alt dizine inmez — kuyruk
kesme kontrolü arşivlenmiş bir çıpadan asla kurulmaz). Arşiv, kanıt için değil,
**neyin neden kaybedildiğini okuyabilmek** için durur.

Bununla birlikte `verify-chain` HER turda arşivi de tarar (yalnız isim eşleştirmesi
için, hash yeniden hesaplamaz): git geçmişinde adı geçen ama üst düzeyde artık olmayan
bir çıpa `ledger/archive/`de bulunursa çıktıya "ÇIPA ARŞİVLENDİ (kanıt kapsamı
daraldı): <ad>" satırı basılır. Bu **beklenen** bir çıktıdır, alarm değildir —
yukarıdaki prosedür meşru olduğu için kapıyı kırmızı yapmaz; yalnızca git geçmişinde
olup NE üst düzeyde NE DE arşivde bulunamayan bir çıpa `ÇIPA EKSİK` ile exit 1 verir.

### 1.5 Kurtarma sonrası — kapı ne demeli

```bash
uv run python -m football_edge.collect verify-chain
# beklenen: "ÇIPA ARŞİVLENDİ (kanıt kapsamı daraldı): head-YYYY-MM-DD.txt"
#           + "çıpa yok ya da okunamadı — kuyruk kesme kontrolü ATLANDI"
#           + "zincir: SAĞLAM kontrol=<tüm defter>"

uv run python -m football_edge.collect publish-head
# beklenen: "zincir başı yazıldı: ledger/head-YYYY-MM-DD.txt"
#           (bugünün çıpası aynı başla zaten varsa: "zincir başı değişmedi: …")
```

**`ÇIPA ARŞİVLENDİ` satırı beklenen çıktıdır ve kaybolmaz.** Arşivlenmiş bir çıpa
"hesaba katılmış" sayılır — yani §1.4'ün prosedürü kapıyı KALICI kırmızıya düşürmez —
ama daralan kanıt kapsamı her turda ADIYLA raporlanır. Silmek yerine arşive taşıyan biri
bu satırı üretir; sessiz geçmez. Satır git geçmişindeki taşıma commit'iyle birlikte
okunmalıdır (§1.4 adım 3: gerekçe ve taşıma AYNI commit'te).

Yeni çıpa commit'lenip **push edilmeden** koruma geri gelmez: çalışma ağacındaki çıpa,
defteri yeniden yazabilen birinin ayrıca yazabileceği bir dosyadır. Dış kanıt ancak
uzak depodaki commit'tir.

`ATLANDI` satırı, arşivlemeden sonra en az bir tur **beklenen** çıktıdır ve
kilitlenmenin bittiğinin işaretidir — ama aynı zamanda o turda kuyruk kesme kontrolünün
**koşmadığının** da işaretidir. Atlanan kontrol geçmek değildir; ilk `publish-head`
sonrası bir sonraki turda `ATLANDI` **kaybolmalıdır.** Kaybolmuyorsa çıpa yazılmıyor
demektir → §1.1'e dön.

### 1.6 Aynı ailedeki ikinci çıktı: düşürülmüş çıpa

```
en yeni çıpa okunamadı (head-YYYY-MM-DD.txt) — kuyruk kesme kontrolü bir önceki
çıpaya düşürüldü, EN YENİ ÇIPA ATLANDI
```

Bu kilitlenme değildir: kontrol koşar, yalnız **daha eski** bir çıpadan koşar. Dosya
bozuksa (eksik alan, sayı olmayan `rows`/`last_id`) sebebi bulunur; içerik kasten
değiştirilmişse §1.3'teki kurcalama dalına gidilir. Sessizce görmezden gelinmez:
düşürülmüş kontrol de geçmiş sayılmaz.

---

## 2. Zincir çatalı — iki eşzamanlı yazar defteri kalıcı olarak kırdı

### 2.1 Nasıl tanınır

`verify-chain` şunu yazar ve **her turda aynısını yazar**:

```
zincir: KIRIK kontrol=<N> baş=<16 hane> hata=prev_hash zincire uymuyor
```

`hata=` alanı ayırt edicidir:

| `hata=` | ne demek | nereye |
|---|---|---|
| `prev_hash zincire uymuyor` | zincir **çatallandı**: iki satır aynı önceki hash'ten türemiş | §2.2 |
| `row_hash içerikle uyuşmuyor` | bir satırın **İÇERİĞİ** değişmiş — çatal değil | **kurcalama şüphesi** → §1.3 |

### 2.2 Teşhis: çatal mı, kurcalama mı?

Çatalın imzası **aynı `prev_hash`ı paylaşan iki satırdır**. Kurcalamada böyle bir
çift yoktur; kurcalanan satırın kendi hash'i kendi yükünü üretmez.

```sql
select prev_hash, count(*) as dal, min(id) as ilk, max(id) as son
from odds_snapshots
group by prev_hash
having count(*) > 1
order by ilk;
```

- **Satır dönerse → çatal.** `ilk` ve `son` id'lerin `observed_at`ları birbirine çok
  yakındır (aynı turun iki yazarı). §2.3'e geç.
- **Hiç satır dönmezse** ama zincir yine kırıksa: bu çatal değildir. §1.3'teki
  kurcalama dalına gidilir, hiçbir şey taşınmaz, durum bir insana eskale edilir.

### 2.3 Neden onarılamaz — ve `DISABLE TRIGGER` neden YASAK

Çatalı "düzeltmenin" tek teknik yolu bozuk satırı **silmektir**. O yol kapalıdır:

- `DELETE` append-only tetikleyicisine çarpar (`odds_snapshots append-only bir
  defterdir; DELETE reddedildi`). **Bu doğru davranıştır.**
- Toplayıcı bugün tablonun **sahibi** olarak bağlanıyor, yani `ALTER TABLE
  odds_snapshots DISABLE TRIGGER ...` teknik olarak elinin altında. **Asla
  kullanılmaz.** Bir kez kullanıldığında ürünün sattığı şey geriye dönük biter:
  o tarihten sonra hiç kimse — operatörün kendisi dâhil — bir satırın prosedürle mi
  yoksa saldırganla mı kaldırıldığını ayırt edemez. Tetikleyiciyi kapatan bir
  prosedür, bypass bayrağının SQL'ce yazılmış hâlidir (§1.2).

Yani defter onarılmaz. Yapılabilecek tek dürüst şey **kesittir**: kırık defter
olduğu gibi saklanır, yeni defter yanında başlatılır, ve **neyin kaybedildiği yazılır.**

### 2.4 Önce SEBEBİ kapat — yoksa kesit bir sonraki turda yeniden kırılır

Çatal, kilitsiz bir yazma yolundan gelir. Kesitten **önce** koşan kodun
`src/football_edge/db.py` içindeki `lock_ledger`ı çağırdığı doğrulanır:

```bash
git -C . grep -n "pg_advisory_xact_lock" -- src/football_edge/db.py
# beklenen: insert_snapshots'ın İLK ifadesi olarak alınan kilit
```

Ayrıca **elle koşan tur kalmadığı** teyit edilir: iki cron aynı `odds-collect`
concurrency grubundadır, ama bir dizüstünden koşulan `collect snapshot` o grubun
**içinde değildir.** Kilit bu ikinciyi de yakalar — ama yalnız kilitli sürüm koşuyorsa.

### 2.5 Kesit — tablo SİLİNMEZ, yeniden adlandırılır

```sql
-- 1) Kırık defter DURUR, yalnız adı değişir. drop/truncate YOK.
alter table odds_snapshots rename to odds_snapshots_kirik_20260919;
alter table odds_snapshots_kirik_20260919 rename constraint odds_snapshots_row_hash_key
  to odds_snapshots_kirik_20260919_row_hash_key;

-- 2) Yeni defter 0001_init.sql'den yeniden kurulur (tetikleyici dâhil).
--    Eski tablo yerinde durduğu için hiçbir satır kaybolmaz.
```

Sonra çıpalar §1.4'teki prosedürle `ledger/archive/` altına **taşınır** (silinmez) ve
gerekçe notuna **ne kaybedildiği** yazılır:

```
**KAYBEDİLEN KANIT:** <ilk_id>..<son_id> arasındaki çatal onarılamadı. O aralık için
zincir kanıtı yoktur; satırlar odds_snapshots_kirik_20260919 tablosunda DURUYOR ama
hash zinciri onları artık doğrulamıyor. Çatalın sebebi: <kilitsiz sürüm / elle tur>.
```

### 2.6 Kesit sonrası — kapı ne demeli

```bash
uv run python -m football_edge.collect verify-chain
# beklenen: "çıpa yok ya da okunamadı — kuyruk kesme kontrolü ATLANDI"
#           + "zincir: SAĞLAM kontrol=0"

uv run python -m football_edge.collect publish-head
# beklenen: "zincir başı yazıldı: ledger/head-YYYY-MM-DD.txt"
#           (bugünün çıpası aynı başla zaten varsa: "zincir başı değişmedi: …")
```

`ATLANDI` bir tur beklenir, sonra kaybolmalıdır (§1.5). Kaybolmuyorsa çıpa
yazılmıyordur → §1.1.

**Kesit bedava değildir:** CLV kapanış fiyatını eski defterden okumak isteyen Faz 1
kodu artık iki tabloya bakmak zorundadır. Bu borç `docs/DEFERRED.md`'ye yazılır.

---

## 3. Tetikler (pg_cron → `workflow_dispatch`) ve kırmızı tur alarmı

### 3.1 Neden var
GitHub zamanlanmış workflow'ları garanti etmez. 2026-09-19 → 21 arasında `seal.yml`in `*/15`
cron'u ~203 tur yerine 16 tur koştu; 20 dakikalık mühür penceresi yüzünden 47 maçın kapanış
fiyatı kalıcı olarak kaçtı. Asıl tetik artık Supabase'deki pg_cron:

| İş | Ne zaman | Çağırdığı | Tetiklediği |
|---|---|---|---|
| `seal-dispatch` | her 15 dakikada | `ops.dispatch_seal()` | `seal.yml` |
| `snapshot-dispatch` | her gün 06:22 UTC | `ops.dispatch_snapshot()` | `snapshot.yml` |
| `collect-daily-dispatch` | her gün 07:10 UTC | `ops.dispatch_collect_daily()` | `collect-daily.yml` (`fetch-tff`, `fetch-venues`) |
| `collect-news-dispatch` | 2 saatte bir, :07'de | `ops.dispatch_collect_news()` | `collect-news.yml` (`fetch-news`) |
| launchd (Mac), pg_cron değil | 10:40 yerel (07:40 UTC); 14:40/18:40/22:40 ve oturum açılışı telafi | `scripts/footystats_daily.sh` | `fetch-footystats`, UTC günü başına bir tur — §3.9 |

Hepsi `ops.dispatch_workflow()`a delege eder; o yalnız izinli listedeki bir adı GitHub API'si
üzerinden tetikler (`db/migrations/0003_seal_dispatch.sql`, `0004_workflow_dispatch.sql`,
`0005_collect_dispatch.sql`). `seal.yml`in kendi `schedule`ı yedektir ve bekçiyi koşturur (§3.6);
diğerlerinin `schedule`ı **yok**: iki tetik iki tur demektir, snapshot'ta iki kat kredi.
`fetch-results` zamanlanmadı: `/scores` kredi harcar ve ayda 500 kredilik bütçe snapshot ile
mühüre ayrılmış (R67) — elle koşulur. `fetch-footystats` GitHub'da koşmaz: runner'lar footystats'tan
403 alıyor (Cloudflare veri merkezi IP'lerini geri çeviriyor; aynı kod ve kimlik Mac'ten 200), iş
Mac'te launchd ile koşar (§3.9, R73).

### 3.2 Kurulum (tek sefer)
1. **Token (GitHub):** hazır doldurulmuş form (ad, açıklama, sahip, süre ve **Actions: Read and
   write** gelir; başka izin yok):
   <https://github.com/settings/personal-access-tokens/new?name=football-edge+seal+dispatch&description=pg_cron+triggers+seal.yml+and+snapshot.yml+via+workflow_dispatch%3B+Supabase+Vault%3A+github_seal_dispatch&target_name=popiliadam&expires_in=none&actions=write>
   Elle seçilen tek alan: Repository access → *Only select repositories* → `football-edge`.
   `expires_in=none` bilinçli: yıllık yenileme bir el işidir. Yetki tek depoda yalnız Actions;
   süreli token istenirse tarih seçilir ve §3.4 devreye girer. Token izinli listedeki bütün
   workflow'ları tetikler: `seal.yml`, `snapshot.yml`, `collect-daily.yml`, `collect-news.yml`. Actions yetkisi depodaki her workflow'u tetikleyebilir;
   sınırı `ops.dispatch_workflow`un izinli listesi çizer (`0004_workflow_dispatch.sql`).
2. **Vault (Supabase):** panelde Vault sayfasında *Add new secret* → adı tam olarak
   `github_seal_dispatch`, değeri token. SQL editörü de olur ama token sorgu geçmişinde kalır:
   `select vault.create_secret('<token>', 'github_seal_dispatch');`
3. **Migration:** `0003_seal_dispatch.sql`, `0004_workflow_dispatch.sql`, `0005_collect_dispatch.sql`
   sırayla bir kez uygulanır (asistan Supabase aracıyla uygular). 0005, `collect-*.yml` dosyaları
   `main`de olduktan SONRA uygulanır: GitHub `main`de olmayan bir workflow'u tetiklemez (404). Yeniden çalıştırmak güvenlidir: işler adıyla
   güncellenir, ikinci iş açılmaz. `snapshot.yml`den `schedule`ı kaldıran commit `main`e,
   0004 uygulanmadan gitmez — arada snapshot'ı tetikleyen hiçbir şey kalmaz.

Secret yokken her iş `ops.dispatch_workflow: Vault secret github_seal_dispatch yok — <workflow>
tetiklenmedi` hatası verir; secret eklendiği an kendiliğinden çalışmaya başlar. Secret'ın adı
yalnız mührü anar ama izinli listedeki bütün workflow'lara hizmet eder.

### 3.3 Doğrulama
```sql
select j.jobname, d.status, d.return_message, d.start_time
from cron.job_run_details d join cron.job j using (jobid)
where j.jobname like '%-dispatch'
order by d.start_time desc limit 10;

select status_code, error_msg, created from net._http_response order by created desc limit 5;
```
`204` = GitHub turu başlattı. `401` = token geçersiz ya da süresi dolmuş (§3.4). `403`/`404` =
token bu depoya ya da Actions'a yetkili değil. `422` = workflow'da `workflow_dispatch` yok.
GitHub tarafı: `gh run list --workflow seal.yml --event workflow_dispatch --limit 5` (diğerleri
için `--workflow snapshot.yml`, `collect-daily.yml`, `collect-news.yml`).

**Beklenen kırmızı:** kaçmış bir maç, başlama saatinden sonra 24 saat boyunca her turda
"kaçan mühür" olarak raporlanır (`rounds._seal_candidates`: `commence_time > now - 1 gün`).
Tetik düzeldikten sonra da turlar son kaçan maçın üstünden 24 saat geçene kadar `exit 5` verir.
O turlarda yeni maçların mühürlenip mühürlenmediğine logdan bakılır; kırmızı — ve `seal`
alarmı (§3.6) — kendiliğinden biter.

### 3.4 Token yenileme
Token iptal edilirse (ya da süreli seçildiyse süresi dolarsa) bütün dispatch'ler `401` alır: mühür
yalnız seyrek yedek `schedule`la koşar; snapshot ve toplayıcılar hiç koşmaz. Bekçi yedek turda kendi alarmını
(`🔴 bekçi kırmızı`) açar (§3.6). Yeni tokenı §3.2/1'deki gibi oluştur, sonra:
```sql
select vault.update_secret((select id from vault.secrets where name = 'github_seal_dispatch'),
                           '<yeni token>');
```

### 3.5 Durdurma / yeniden başlatma
```sql
select cron.unschedule('seal-dispatch');       -- mührü durdur
select cron.schedule('seal-dispatch', '*/15 * * * *', 'select ops.dispatch_seal()');       -- başlat
select cron.unschedule('snapshot-dispatch');   -- snapshot'ı durdur
select cron.schedule('snapshot-dispatch', '22 6 * * *', 'select ops.dispatch_snapshot()');  -- başlat
select cron.unschedule('collect-daily-dispatch');  -- günlük toplayıcıları durdur
select cron.schedule('collect-daily-dispatch', '10 7 * * *', 'select ops.dispatch_collect_daily()');
select cron.unschedule('collect-news-dispatch');   -- haberi durdur
select cron.schedule('collect-news-dispatch', '7 */2 * * *', 'select ops.dispatch_collect_news()');
```
Durdurulan iş eşiği aşınca bekçi kendi alarmını açar (§3.6): bilinçli bir durdurma da görünür
kalır. İş yeniden başlayıp bekçi bütün tetikleri taze bulunca alarm kendiliğinden kapanır.

### 3.6 Kırmızı tur alarmı ve bekçi
`scripts/ops_alert.py` her workflow ve bekçi için ayrı bir `ops-alert` issue'su tutar; her biri
yalnız kendi başlığına dokunur:

| Başlık | Açan ya da güncelleyen | Kapatan |
|---|---|---|
| `🔴 seal kırmızı` | kırmızı ya da koşarken iptal edilen (zaman aşımı) `seal.yml` turu | yeşil `seal.yml` turu |
| `🔴 snapshot kırmızı` | kırmızı ya da koşarken iptal edilen (zaman aşımı) `snapshot.yml` turu | yeşil `snapshot.yml` turu |
| `🔴 collect-daily kırmızı` | kırmızı ya da koşarken iptal edilen `collect-daily.yml` turu | yeşil `collect-daily.yml` turu |
| `🔴 collect-news kırmızı` | kırmızı ya da koşarken iptal edilen `collect-news.yml` turu | yeşil `collect-news.yml` turu |
| `🔴 sources-audit kırmızı` | `main`deki kırmızı ya da iptal edilen `sources-audit.yml` turu (§3.7) | `main`deki yeşil tur |
| `🔴 footystats-local kırmızı` | Mac'teki işin `result=fail` raporu (`footystats-local.yml`, §3.9) | `result=ok` raporu |
| `🔴 bekçi kırmızı` | bayat tetik, az ya da ölçülemeyen kredi, ya da ücretli ölçüm bulan bekçi | hepsini temiz bulan bekçi |

- Açık alarm varsa yenisi açılmaz, yalnız gövdesi güncellenir — gövde düzenlemesi bildirim
  üretmez. Kapanırken `yeşile döndü: <tur>` yorumu yazılır. Etiket yoksa ilk açılışta oluşturulur.
- **Alarm aç** `if: failure() || cancelled()`: zaman aşımı turu iptal eder ve `failure()` yanlış
  döner. Kuyrukta beklerken iptal edilen tur hiç adım koşmaz, alarm da açmaz.
- **Alarm kapat** `continue-on-error: true`: kapatma düşerse (ör. GitHub 5xx) yeşil tur kırmızıya
  dönmez; açık alarm sonraki yeşil turda kapanır.
- **Bekçi** yalnız `seal.yml`in yedek `schedule` turunda, mühürden sonra koşar. Eşikler: `seal.yml`in son
  `workflow_dispatch` turu 60 dk, `snapshot.yml` 30 sa, `collect-daily.yml` 30 sa, `collect-news.yml`
  4 sa, `footystats-local.yml` 72 sa (Mac'in kalp atışı, §3.9) (hiç tur yoksa da bayat). Ayrıca Odds API kalan kredisini ücretsiz `/v4/sports` ucundan ölçer:
  60'ın altındaysa, ölçülemiyorsa ya da ölçüm ücretliyse (`x-requests-last` ≠ 0) de alarm. Anahtar
  hiçbir çıktıya yazılmaz. Bulduğunda kendi alarmını açar ve **0 döner**: seal job'ını düşürseydi seal'in sonraki yeşil turu
  alarmı geri alırdı. Gövdede hangi tetiğin ne kadar bayat olduğu ve eşik yazar; teşhis §3.3.
  Ölü snapshot sessiz bir arızadır: maçları yalnız snapshot kaydeder; o durunca mühür de kayıtlı
  maçlar bitince "kaçan" raporu bile vermeden susar. GitHub API'nin kendisi düşerse bekçi düşer ve
  `seal` alarmı açılır.

Haber GitHub'ın issue bildirimiyle gelir: e-posta, depo sahibinin bu depoyu izleme ayarına
bağlıdır. Depo sayfasında *Watch* → *All Activity* (ya da *Custom* → *Issues*) seçili değilse
issue açılır ama kimseye haber gitmez. Bilinen kör noktalar: `docs/DEFERRED.md` §10f.

### 3.7 robots.txt yeniden doğrulaması (otomatik)
`sources-audit.yml` her gün (GitHub `schedule`ı, 05:41 UTC; gecikme 30 günlük pencerede zararsız)
her kaynağın canlı robots.txt'ini anlık görüntüsüyle (`config/robots/<id>.txt`) karşılaştırır.
Satır sonları normalleştirilip baş/son boşluk atıldıktan sonra AYNIYSA ve `robots_verified_at` 7
günden eskiyse bot o tarihi bugüne (UTC) çeker ve `main`e commit'ler — merge, en çok 3 deneme,
asla force; `config/sources.yaml`in geri kalanı byte byte aynı kalır, yazım atomiktir. Sapma ya
da ölçülemeyen (403, 429, 5xx, bağlantı hatası) kaynağın tarihine dokunulmaz; tur kırmızı olur ve
`🔴 sources-audit kırmızı` açılır.

Sapma görülürse (elle): canlı robots.txt'i oku. Beyan ettiğimiz yollara hâlâ izin veriyorsa
`config/robots/<id>.txt`i canlı içerikle, `robots_verified_at`i bugünle güncelle; izin
vermiyorsa kaynağı `enabled: false` yap. Kapı gevşetilerek yeşil alınmaz.

### 3.8 Loglarda sır
`collect.py` log kurulumu (`configure_logging`) her çıktıyı — mesaj ve traceback — redakte eden bir
biçimleyiciyle kurar: `ODDS_API_KEY`, `TYPESAFE_API_KEY`, `DATABASE_URL`in tamamı ve parolası
(libpq'nun ayrıştırdığı ve URL'deki biçimler), ayrıca her `apikey=` sorgu değeri `***` olur.
Yakalanmayan istisna da `sys.excepthook` ile aynı yoldan geçer; httpx istek satırları susturuldu.
Depo public olduğu için Actions logları herkese açıktır: GitHub'ın maskesi yalnız secret'ın
TAMAMINI tanır, bu katman parçaları da kapsar. Yeni bir kimlik bilgisi eklenirse
`_log_secrets`e de eklenmeli (DEFERRED 10o).

### 3.9 FootyStats yerel işi (Mac, launchd)
GitHub'ın barındırdığı runner'lar footystats'tan 403 alıyor (2026-09-22, run 35710579845: 6/6
lig); aynı kod, kimlik ve istek yolu Mac'ten 200 alıyor: Cloudflare veri merkezi IP'lerini geri
çeviriyor (robots.txt'e runner'dan erişim açık — `sources-audit` 35715215485). Kimliği
değiştirmek (R2) ya da bot korumasını aşmak seçenek değil (R73). İş bu yüzden Mac'te koşar:
`scripts/footystats_daily.sh`, launchd ile 10:40 yerel saatte; 14:40, 18:40, 22:40 ve oturum
açılışı kaçan turu telafi eder. UTC günü başına BİR tur toplanır (damga dosyası).

1. Bugünün (UTC) turu zaten koştuysa hiçbir şey yapmaz.
2. İşin kendi temiz klonunda (`~/.local/share/football-edge/collector`; yoksa yeniden klonlar)
   `origin/main`i çeker (6 deneme: uyanıştan sonra ağ geç gelebilir) ve ayrık HEAD'e geçer.
   Çekemezse eski kodla toplamaz ve günü açık bırakır: sonraki dilim yeniden dener.
3. Kurulu kopyası `main`deki sürümden farklıysa kendini günceller (sonraki turdan geçerli).
4. `uv sync --frozen`, ardından `.env`den YALNIZ `DATABASE_URL`i okuyup `fetch-footystats`i koşar
   ve günü damgalar (kırmızı bir toplayıcı aynı gün yeniden istenmez — `collect-daily` gibi).
5. Sonucu `gh workflow run footystats-local.yml -f result=ok|fail` ile GitHub'a bildirir (R74):
   alarmı o workflow `github-actions` kimliğiyle açar ve kapatır (§3.6). Kullanıcının kendi
   token'ıyla açılan issue bildirim üretmezdi: GitHub kişiye kendi eylemi için haber vermez.
   Token işin süreçlerine hiç girmez. GitHub'a ulaşılamazsa Mac'te bir bildirim çıkar.
6. Her rapor bekçi için bir kalp atışıdır: 72 saat rapor yoksa `🔴 bekçi kırmızı` açılır (Mac
   kapalı, launchd işi durmuş ya da `gh` oturumu düşmüş).

Günlük: `~/Library/Logs/football-edge/footystats.log` (launchd stdout ve stderr'i ekler, döndürmez).

Kurulum (yeniden koşmak betiği ve plist'i atomik yeniler, işi yeniden yükler):
```bash
uv run python scripts/install_footystats_agent.py --dry-run
uv run python scripts/install_footystats_agent.py
```
launchd, betiğin klonun DIŞINDAKİ kopyasını (`~/.local/share/football-edge/bin/`) koşar: klondaki
dosya, betiğin kendi `git checkout`u ile koşarken değişebilirdi. Betik değişiklikleri kopyaya
kendiliğinden gelir; kurulumu yeniden koşmak yalnız plist (dilimler, PATH) değişince gerekir.

Denetim ve elle tur:
```bash
launchctl print gui/$(id -u)/com.popiliadam.football-edge.footystats | grep -E 'state|last exit'
tail -n 20 ~/Library/Logs/football-edge/footystats.log
gh run list --workflow footystats-local.yml --limit 3
launchctl kickstart -k gui/$(id -u)/com.popiliadam.football-edge.footystats
```
Aynı gün ikinci bir elle tur için önce damga silinir: `~/.local/share/football-edge/state/footystats-last-run`.
Kaldırma: `launchctl bootout gui/$(id -u)/com.popiliadam.football-edge.footystats`, sonra
`~/Library/LaunchAgents/com.popiliadam.football-edge.footystats.plist` silinir.

Kör noktalar (DEFERRED 10r, 10t): Mac bütün gün kapalıysa o günün xG ara durumu kalıcı kaybolur;
telafi yalnız gün içindedir. Tek bir tur için katı bir süre üst sınırı yok (macOS'ta `timeout` yok):
ağa çıkan adımların kendi sınırları var. `DATABASE_URL` değişirse yalnız `.env` güncellenir: plist
sırrı değil, dosyanın yolunu taşır. Güven sınırı: `main`in ucu her gün bu Mac'te, kullanıcının
yetkisiyle ve insan olmadan koşar (10t).
