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
```

`ATLANDI` bir tur beklenir, sonra kaybolmalıdır (§1.5). Kaybolmuyorsa çıpa
yazılmıyordur → §1.1.

**Kesit bedava değildir:** CLV kapanış fiyatını eski defterden okumak isteyen Faz 1
kodu artık iki tabloya bakmak zorundadır. Bu borç `docs/DEFERRED.md`'ye yazılır.
