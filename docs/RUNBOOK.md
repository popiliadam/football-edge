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

`ledger/archive/` altındaki dosyalar **hiçbir kontrol tarafından okunmaz**
(`_scan_anchors` yalnız `ledger/head-*.txt` glob'una bakar, alt dizine inmez).
Arşiv, kanıt için değil, **neyin neden kaybedildiğini okuyabilmek** için durur.

### 1.5 Kurtarma sonrası — kapı ne demeli

```bash
uv run python -m football_edge.collect verify-chain
# beklenen: "çıpa yok ya da okunamadı — kuyruk kesme kontrolü ATLANDI"
#           + "zincir: SAĞLAM kontrol=<tüm defter>"

uv run python -m football_edge.collect publish-head
# beklenen: "zincir başı yazıldı: ledger/head-YYYY-MM-DD.txt"
```

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
