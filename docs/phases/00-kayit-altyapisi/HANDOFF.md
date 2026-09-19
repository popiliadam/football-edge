# Faz 0 — Kayıt Altyapısı · Devir Belgesi (HANDOFF)

**Tarih:** 2026-09-19 · **Dal:** `faz-0-kayit-altyapisi` · **Kapı:** `./verify.sh` → `KAPI YEŞİL`

> **Bu belge bir kez bayatladı.** §2 ve §3, ilk canlı turdan ÖNCE yazılmıştı ve
> canlı tur (`dce3013`) onları yanlışladı: "hiç snapshot koşmadı", "`ledger/` yalnız
> `.gitkeep` taşıyor", "append-only testleri SKIP" — üçü de artık **yanlıştı** ve
> belge onları doğru diye taşımaya devam etti. Kapının ölçmediğini yazan bir belgenin
> kendisi ölçülmüyordu. 2026-09-19 birleştirme koşulları turunda gerçek HEAD'e karşı
> yeniden yazıldı. **Aynısı yine olur:** bu belgeyi okuyan, §2'deki test sayısını ve
> §3.2'deki commit'i `git log`a karşı bir kez kontrol etsin.

Bu belgenin en önemli bölümü §3'tür. §2 kapının ne ölçtüğünü, §3 **ölçmediğini** yazar.
Yeşil bir kapı yalnız §2'yi kanıtlar; §3'teki hiçbir satır "test edildi" sayılamaz.

---

## 1. Ne bitti

| Parça | Dosya | Durum |
|---|---|---|
| Şema + append-only tetikleyici | `db/migrations/0001_init.sql` | Supabase'e uygulandı |
| Lig konfigürasyonu | `config/leagues.yaml`, `leagues.py` | 6 aktif lig |
| Oran istemcisi + kota koruması | `odds_api.py` | birim testli |
| Hash zinciri (saf fonksiyonlar) | `ledger.py` | birim testli |
| Postgres yazma yolu | `db.py` | birim testli (sahte bağlantı) |
| CLI: `snapshot`/`seal`/`verify-chain`/`publish-head` | `collect.py` | birim testli |
| Zamanlanmış işler | `.github/workflows/{snapshot,seal}.yml` | yazıldı, **hiç koşmadı** (§3.2) |
| CI kapısı | `.github/workflows/ci.yml` | `push` + `pull_request` → `./verify.sh`, secret'sız; **hiç koşmadı** (§3.2) |
| Kapı | `verify.sh` + `scripts/check_secrets.sh` | 7 adım, bu görevde 3 adım eklendi |
| Operatör runbook'u | `docs/RUNBOOK.md` | §1 çıpa kilitlenmesi · §2 zincir çatalı (eşzamanlı yazar) |
| Ertelenen bulgular | `docs/DEFERRED.md` | karar kaydı gitignore'daydı; sonuçları izlenen dosyaya taşındı |
| Giriş noktası | `README.md` | kurulum, `DATABASE_URL`, migrasyon, kapı, belge haritası |
| İlk canlı tur | `ledger/head-2026-09-19.txt` | **3 717 satır**, 51 maç, 25 bahisçi, 6 kredi |

**Bu görevde (Task 8) eklenen üç adım:**

1. `paket-kurulu` — `env PYTHONPATH= uv run python -c "import football_edge..."`.
   Testler `pythonpath = ["src"]` ile koşar ve **kurulu paket bozuk olsa bile geçer**;
   CI ise `python -m football_edge.collect` ile kurulu paketi çağırır. Bu adım farkı kapatır.
2. `secrets` — `scripts/check_secrets.sh`. Depo **public**, `.env` canlı bir API anahtarı ve
   veritabanı parolası tutuyor; kaçan secret insan kontrol noktası olmadan halka açılır.
3. `zincir` — `verify-chain`, **yalnız `DATABASE_URL` tanımlıysa**. Tanımlı değilse
   `SKIP: zincir (DATABASE_URL yok)` basar. **SKIP geçmek değildir** (§3.1).

---

## 2. Kapı ne ölçtü

`./verify.sh` çıktısı özet değil, **log dosyasından** (`$TMPDIR/football-edge-verify.log`).

**Taze koşu — `710c4cb` + bunu izleyen dokümantasyon commit'leri** (yalnız `docs/`
ve `README.md`; kod ve test değişmedi, o yüzden sayılar aynı kalır):

```
=== ruff-check ===
All checks passed!
=== ruff-format ===
20 files already formatted
=== mypy ===
Success: no issues found in 6 source files
=== pytest ===
........................................ss.............................. [ 73%]
..........................                                               [100%]
96 passed, 2 skipped in 0.13s
=== paket-kurulu ===
/Users/apple/dev/football-edge/src/football_edge/__init__.py
=== secrets ===
secret taraması temiz
SKIP: zincir (DATABASE_URL yok)
```

`KAPI YEŞİL`, exit 0.

**Bu koşu ALTI adımı ölçtü, yedisini değil.** `zincir` ATLANDI, çünkü koşulduğu
kabukta `DATABASE_URL` tanımlı değildi; `2 skipped` de append-only testleridir ve
sebebi aynı (ulaşılabilir veritabanı + dolu defter yok). **SKIP geçmek değildir.**

### Yedi adımın hepsinin gerçekten koştuğu TEK ölçüm

`DATABASE_URL` bağlıyken, **2026-09-19 01:31–01:33 UTC** (yerel 04:31, +03:00),
commit `fa225ef` ağacında (çıpa commit'i `dce3013` bunun üzerine yalnız
`ledger/head-2026-09-19.txt` ekledi):

```
ruff-check · ruff-format · mypy · pytest · paket-kurulu · secrets · zincir
→ HEPSİ PASS, KAPI YEŞİL, exit 0
   pytest: 77 passed, 0 skipped      (append-only testleri İLK KEZ koştu)
   zincir: SAĞLAM kontrol=0          (tüm satırlar çıpanın last_id'sinin altında)
```

O koşudaki test sayısı (77) bugünkünden (96) düşüktür: aradaki 19 test bu turda
C1/C2/I4 için eklendi. **Yeniden ölçülmesi gereken şey:** `DATABASE_URL` bağlıyken
yedi adımın bugünkü ağaçta da yeşil verdiği. Kimlik bilgisi olmadan bu tekrarlanamaz;
merge sonrası ilk `seal` turu bunu kendiliğinden ölçecek (`zincir` adımı orada koşar).

### Her adımın kırmızı verebildiği kanıtlandı mı?

| adım | kırmızı kanıtı |
|---|---|
| `secrets` | **Evet.** Sahte secret index'e alındı → dosya/satır basıldı, **exit 1**. Geri alındı → **exit 0**. |
| `paket-kurulu` | **Evet (simülasyon).** `.pth`'in eklediği `src` girdisi `sys.path`'ten çıkarılınca `ModuleNotFoundError` → exit 1. Kurulum dosyalarına dokunulmadı. |
| `zincir` | **Evet.** Ulaşılamaz bir `DATABASE_URL` ile adım koştu, `psycopg.OperationalError` ile düştü, kapı `KAPI KIRMIZI` verdi. |
| ruff / mypy / pytest | Task 1–7 boyunca defalarca kırmızı verdi (plan düzeltme kayıtları). |

---

## 3. Kapının ÖLÇMEDİĞİ — burası "yeşil" sayılmaz

### 3.1 Atlanan kontroller (bu koşuda fiilen çalışmadı)

1. **`zincir` adımı bu koşuda ATLANDI.** Yerel kabukta `DATABASE_URL` tanımlı değil;
   kapı `SKIP: zincir (DATABASE_URL yok)` bastı. *(Bu madde eskiden "kapı bugüne kadar
   hiçbir zinciri doğrulamadı, gerçek defter üstünde `zincir: SAĞLAM` çıktısı hiç
   alınmadı" diyordu — ilk canlı tur onu yanlışladı.)*
   **Bir kez doğrulandı:** 2026-09-19 01:32 UTC, `zincir: SAĞLAM kontrol=3717
   baş=4768f367` (çıpadan önce) ve `kontrol=0` (çıpadan sonra, kuyruk boş).
   **Değişmeyen ve asıl mesele:** o TEK koşu dışında kapı hiçbir zinciri doğrulamıyor.
   `DATABASE_URL` olmayan her koşuda — **CI dâhil, kasıtlı olarak** (§3.6/1) — adım
   atlanır. Adım bugün düzenli olarak yalnız `seal.yml` içinde koşacak, o da ancak
   **merge'den sonra** (§3.2/4).
2. **Append-only tetikleyici testleri artık KOŞUYOR — ama yalnız bağlıyken.**
   *(Bu madde "defter boş olduğu sürece skip kalırlar, Faz 0'ın merkezî iddiası
   ölçülmüyor" diyordu; ilk canlı tur onu yanlışladı ve belge bir süre yanlış taşıdı.)*
   `test_append_only_trigger_blocks_update` ve `..._blocks_delete` 2026-09-19 01:32
   UTC'de **İLK KEZ gerçekten koştu ve PASS etti**: canlı Postgres, 3 717 satırlık
   defterde `UPDATE`i de `DELETE`i de reddetti. Faz 0'ın merkezî iddiası artık test
   paketinin ölçtüğü bir şeydir.
   **Değişmeyen:** guard hâlâ **ulaşılabilir veritabanı + dolu defter** arıyor, yani
   `DATABASE_URL` olmayan her koşuda (CI dâhil, §3.6/1) bu ikisi yine SKIP olur.
   Yukarıdaki taze transkriptteki `2 skipped` tam olarak bunlardır.
3. ~~**`skipif` yanıltıcı olabilir.**~~ **Round 3'te düzeltildi (G5).** Guard yalnız
   değişkenin **tanımlı olmasına** bakıyordu: sahte bir `DATABASE_URL` ile bu iki test
   skip'ten çıkıp **FAIL** ediyordu (`2 failed, 69 passed` — ölçüldü). Artık guard testin
   gerçek ön koşulunu sorar: **ulaşılabilir veritabanı + en az bir defter satırı**
   (`_live_ledger_row_id`). Sahte DSN ile ölçüldü → `2 skipped`, sebebi adıyla yazılıyor.
   **Değişen:** bu maddenin asıl konusu (2 numara) ilk canlı turda kapandı — guard
   artık gerçekten koşuyor. Ulaşılamayan veritabanı burada yutulur ama kapıda
   yutulmaz: `zincir` adımı `DATABASE_URL` tanımlıyken bağlanamazsa adıyla düşer.

### 3.2 Hiç koşmamış şeyler

4. **Hiçbir workflow bir kez bile koşmadı.** ÜÇÜ de (`snapshot`, `seal`, ve bu turda
   eklenen `ci`). İki bağımsız sebep, ikisi de geçerli:
   - Dal push edilmedi: `origin/faz-0-kayit-altyapisi` = `e0f0b1a`, yerel HEAD
     bu belgenin yazıldığı anda **`710c4cb`** (+ bu dokümantasyon commit'i), yani
     **18+ push'lanmamış commit.** Workflow'ları ekleyen commit'ler (`36b1c3d`,
     `710c4cb`) o yığının içinde. *(Bu madde eskiden HEAD'i `818e730` diyordu.)*
   - Push edilse bile **GitHub `schedule` tetiğini yalnız varsayılan dalda onurlandırır.**
     Varsayılan dal `main` ve `main` yalnız `.env.example`, `.gitignore`, `docs/` taşıyor —
     workflow YAML'ları orada yok. Cron ancak merge'den sonra çalışmaya başlar.
     **`ci.yml` farklıdır:** `push`/`pull_request` ile tetiklenir, yani dal push
     edilir edilmez — merge beklemeden — koşar. Push, ilk ölçümdür.
   Dolayısıyla: secret'ların okunabildiği, `uv sync --frozen`un runner'da çalıştığı,
   concurrency grubunun iki turu gerçekten serileştirdiği, `seal.yml`'deki commit+push
   adımının `contents: write` ile geçtiği, `ci.yml`'in runner'da yeşil verdiği —
   **hiçbiri ölçülmedi.**
5. **Gerçek snapshot KOŞTU — tablolar artık dolu.** *(Bu madde "gerçek snapshot
   koşmadı, tablolar boş" diyordu; ilk canlı tur onu yanlışladı.)* 2026-09-19 01:31
   UTC (yerel 04:31), `exit 0`: **6 lig · 51 maç · 25 bahisçi · 3 717 defter satırı**, min oran
   1.12 / max 22, kredi 500 → 494 (lig başına tam 1, öngörüldüğü gibi).
   `is_closing` satırı 0 — doğru, o an mühür penceresinde maç yoktu.
   **O turun ölçtüğü ve kapının göremediği şey:** yazma ~4 dakika sürdü (120 sn
   beklentisinin üstünde), çünkü `insert_snapshots` satır başına bir INSERT atıyor
   (~3 700 pooler gidiş-dönüşü). Sahte bağlantı anında döndüğü için testlerde,
   kapı veritabanına dokunmadığı için kapıda görünmedi → `docs/DEFERRED.md` §4.1.
6. **Yeni SQL şekilleri gerçek Postgres'e karşı hiç koşmadı.** `_LEDGER_AFTER`, `_LEDGER_AT`,
   `_seal_candidates` sorgusu, `_stamp_sealed`'in `id = ANY(%s)` UPDATE'i, `publish-head`'in
   `count(*), coalesce(max(id),0)` sorgusu — hepsi yalnız `tests/fake_db.py` üzerinde koştu.
   Sahte bağlantı SQL metnini **parse etmez**; yazım hatası, tip uyumsuzluğu ya da eksik
   sütun ancak canlıda patlar.
7. **Dış çıpa YAYINLANDI — `ledger/` artık canlı bir çıpa taşıyor.** *(Bu madde
   "hiç yayınlanmadı, `ledger/` yalnız `.gitkeep` taşıyor" diyordu; `dce3013` onu
   yanlışladı.)* `ledger/head-2026-09-19.txt`:
   `rows=3717 last_id=3718 head=4768f367…c0f5`, commit `dce3013`.
   Çıpadan ÖNCE `verify-chain` beklendiği gibi `çıpa yok ya da okunamadı — kuyruk
   kesme kontrolü ATLANDI` + `zincir: SAĞLAM kontrol=3717` bastı; çıpadan SONRA
   `kontrol=0` (tüm satırlar `last_id`nin altında) ve çıpa satırının hash'i yükünden
   **yeniden hesaplanıp** eşleşti.
   `rows`(3717) ≠ `last_id`(3718): geri alınan bir sonda işlemi bir sequence değeri
   tüketti (sequence rollback olmaz). Tutarlı ve zararsız — `_anchor_break` yalnız
   `total < anchor.rows` hâlinde kırmızı verir.
   **Değişmeyen:** kuyruk kesme tespitinin kendisi hâlâ **canlıda ölçülmedi**; tek
   çıpa var, yani "en eski + en yeni çıpayı ayrı ayrı sor" dalı da hiç koşmadı.
   Çıpanın dış kanıt olması için **push edilmesi** gerekir; dal hâlâ push'lanmadı (§3.2/4).

### 3.3 Zincir doğrulamanın kendi kör noktaları

8. **Zincirin İÇİ hiç yeniden hash'lenmiyor.** Bir çıpa varken `_verify_chain_command`
   yalnız iki şeyi ölçer: (i) çıpaların işaret ettiği **tek** satırın içeriği (`_anchor_break`),
   (ii) **en yeni çıpadan sonraki kuyruk** (`_ledger_rows(conn, newest.last_id)`).
   En eski ve en yeni çıpa arasındaki satırlar **hiç yeniden hash'lenmez.** Oradaki bir
   kurcalama ancak bir sonraki çıpa o aralığa düştüğünde ya da tam doğrulama elle
   koşulduğunda görünür.
9. **İkiden fazla çıpa varsa aradakiler hiç sorulmaz.** `asked = anchors if len(anchors) == 1
   else (anchors[0], anchors[-1])` — 30 günlük çıpa birikince 28'i hiç okunmaz.
10. **Çıpa dosyası çalışma ağacından okunur.** En yeni çıpayı yeniden yazabilen biri defteri
    de yeniden yazabilir; koruma yalnız **git geçmişine commit'lenmiş** eski çıpalardan gelir.
    Bu commit'lerin gerçekten push edildiği (yani dışarıdan doğrulanabilir olduğu) **ölçülmüyor.**

> **Kilitlenme ve elle çıkışı.** `verify-chain` exit 1 verince `publish-head` atlanır:
> yeni çıpa yazılmaz, en yeni çıpa da donar — sistem bu hâlden **kendi kendine çıkamaz**
> ve meşru bir defter yeniden kurulumu da bunu tetikler. Kapalı düşmek kasıtlıdır;
> **bypass bayrağı yok ve eklenmeyecek** (ilk ona uzanan saldırgan ve yorgun operatördür).
> Elle çıkış yolu: **`docs/RUNBOOK.md` §1** — çıpalar `ledger/archive/` altına **taşınır**,
> asla silinmez, ve taşınan çıpanın götürdüğü kanıt gerekçesiyle birlikte commit'lenir.

### 3.4 Secret taramasının kör noktaları

11. **Git GEÇMİŞİ taranmıyor.** `git grep` yalnız **izlenen dosyaların çalışma ağacı hâlini**
    tarar. Daha önce commit'lenip sonra silinmiş bir secret geçmişte durur ve tarama onu
    **göremez.** (gitleaks'in aksine.) Public depoda geçmiş de halka açıktır.
12. **Yalnız üç isim kalıbı biliniyor:** `ODDS_API_KEY`, `DATABASE_URL`, `SUPABASE_*KEY`.
    Başka adla (`PGPASSWORD`, `GH_TOKEN`, `OPENAI_API_KEY`, …) yazılmış bir secret geçer.
13. **Yalnız `AD=değer` biçimi yakalanıyor.** Gömülü parolalı bir URL
    (`postgresql://user:parola@host/db`), JSON `"key": "..."`, YAML `key: ...`, base64 blob
    ya da çıplak bir anahtar değeri — hiçbiri eşleşmez.
14. **`*.md`, `.env.example` ve `uv.lock` pathspec ile taramadan ÇIKARILDI.** Bu depo
    dokümantasyon ağırlıklı; bir Markdown dosyasına yapıştırılan gerçek anahtar kapıya
    görünmez. Bilinçli bir ödünleşme (aksi hâlde plan/spec metinleri yanlış alarm verir),
    ama **bir boşluktur.**
15. **Tarama CI'da koşmuyordu — Round 3'te eklendi (G6), ama boşluk tamamen kapanmadı.**
    `scripts/check_secrets.sh` artık `snapshot.yml` ve `seal.yml`'de checkout'tan hemen
    sonra koşuyor. **Kapanmayan kısım:** bu iki iş akışı yalnız `schedule` ve
    `workflow_dispatch` ile tetikleniyor; **`push`/`pull_request` tetiği yok.** Yani
    push'lanan bir secret CI'ı ANINDA kırmızıya düşürmez — en erken bir sonraki
    zamanlanmış turda (varsayılan dalda `seal` ≈ 15 dakika) görünür, **dal merge edilene
    kadar hiç görünmez** (cron yalnız varsayılan dalda koşar, §3.2). `snapshot.yml`'e
    `push` tetiği EKLENMEDİ: o iş akışının kendisi ücretli çağrı yapıyor, her push'ta
    kredi yakardı. Pre-commit hook hâlâ yok.
    **Adımın getirdiği yeni bağ:** `seal.yml`'de tarama mühür adımından ÖNCE koşuyor;
    tarama düşerse (gerçek bulgu ya da `git grep`in kendisi patlarsa) o turun mührü
    de kaçar. Mühürle ilgisi olmayan bir kontrol artık kapanış fiyatına mal olabilir.
    Kasıtlı: public depoda canlı bir anahtar varken `contents: write` taşıyan bir işin
    koşmaya devam etmesi daha ağır. Geçici arızayı 15 dakikalık cron telafi eder.

### 3.5 Kapının hiç bakmadığı eksenler

16. **Kabuk ve YAML hiç denetlenmiyor.** `shellcheck`, `actionlint`, `yamllint` yok.
    `verify.sh` ve `scripts/check_secrets.sh` kapının parçası ama **kapı onları ölçmüyor.**
17. **`mypy` yalnız `src`'yi görüyor** (`files = ["src"]`). `tests/` tip denetiminden geçmiyor.
18. **Coverage ölçülmüyor.** `pytest-cov` kurulu değil, kapıda eşik yok.
19. **`snapshot`/`seal` komutlarının kendileri hiç çalıştırılmadı.** `paket-kurulu` yalnız
    `import football_edge`'i kanıtlar; CLI giriş noktalarının uçtan uca koştuğunu değil.
20. **Kapanış mührünün gerçek maç saatiyle hizası** canlı bir maçta doğrulanmadı
    (`window_minutes=20` ↔ `*/15` cron). Kaçan mühür kalıcı veri kaybıdır.
21. **`config/leagues.yaml`'daki `odds_api_key` değerleri kapı tarafından doğrulanmıyor.**
    (Elle bir kez `/v4/sports` çıktısına karşı bakıldı — 2026-09-19; kapı bunu tekrarlamaz,
    anahtar sezon arası devre dışı kalırsa kapı sessiz kalır.)
22. **Kredi tüketiminin aylık bütçeye oturduğu gözlenmedi.** Aritmetik `snapshot.yml`
    yorumunda var (6 lig × 1 kredi × 31 gün ≈ 186/500) ama **tam bir ay boyunca ölçülmedi.**
23. **GitHub deposundaki secret'ların (`ODDS_API_KEY`, `DATABASE_URL`) geçerliliği**
    kapı tarafından kontrol edilmiyor.
24. **Ayna arızasında tur artık HİÇ koşmuyor — G3'ün ödünleşmesi.** `_mirror_leagues`
    düşerse `main()` tek bir ücretli çağrı yapmadan exit 4 verir. Kazanç: kalıcı bir ayna
    arızası 500 kredilik aylık katmanı ~2 günde bitiremez. **Bedeli:** ayna yalnız GEÇİCİ
    bir sebeple tazelenemediyse (tablo bir önceki turun aynasını hâlâ taşıyor olabilir)
    o turun mührü **kaçar** ve kapanış fiyatı geri gelmez — round 2'nin F3'te kapattığı
    zararın küçük bir hâli, kredi güvenliği için **bilerek** geri alındı. Kapı bu seçimi
    ölçmez: "ayna düştü ama leagues tablosu aslında sağlamdı" senaryosu üretilmedi.
25. **Runbook hiç koşulmadı.** `docs/RUNBOOK.md` §1 prosedürü gerçek bir kilitlenmede
    denenmedi; `ledger/archive/` dizini henüz yok, `git mv` adımı canlıda yürütülmedi.
    Kapı yalnız runbook'un **varlığını** ve "sil" demediğini ölçer
    (`tests/test_runbook.py`), **doğruluğunu değil.**

### 3.6 Final incelemenin §3'te BULAMADIĞI yedi boşluk

Bunlar 2026-09-19 dal-geneli incelemesinin çıkardığı ve bu belgede **hiç yazmayan**
maddelerdir. Üçü aynı turda kapatıldı; kapatılanlar da burada kalır, çünkü
**kapatılmış bir bulgunun ölçülmemiş yanı vardır.**

26. **CI kapıyı hiç koşmuyordu.** `.github/workflows/` yalnız `schedule` +
    `workflow_dispatch` taşıyan iki dosyaydı; dizini `verify.sh|pytest|ruff|mypy` için
    taramak tek eşleşme veriyordu ve **o da bir yorumdu.** Yani projenin gerçek kapısı
    tek adımdı (`check_secrets.sh`) ama bu belge yedi diyordu.
    **Kapatıldı (`710c4cb`):** `ci.yml`, `push` + `pull_request` → `./verify.sh`.
    **Ölçülmeyen:** runner'da hiç koşmadı (§3.2/4). Ayrıca CI kapısı **altı adımdır**:
    `DATABASE_URL` kasıtlı olarak verilmiyor (canlı defter append-only; her fork PR'ı
    üretim veritabanına erişirdi), o yüzden `zincir` adımı orada hep `SKIP` basar ve
    append-only testleri hep `2 skipped` olur. **Yedinci adım yalnız `seal.yml`'de ve
    yerelde koşar.**
27. **Eşzamanlı yazar güvenliği test edilmiyordu — ve zincir kırılabiliyordu.**
    `db.py` başı okuyup Python'da zincirleyip yazıyordu; kilit yoktu. READ COMMITTED
    altında iki yazar aynı başı okur, `UNIQUE (row_hash)` bunu yakalamaz (yükler
    farklı), ikisi de commit eder ve `verify_chain` **sonsuza dek** "prev_hash zincire
    uymuyor" der. Append-only tetikleyici bozuk satırı sildirmez, `verify-chain` exit 1
    de `publish-head`i durdurur: kanıt üretimi biter.
    **Kapatıldı (`efca310`):** `pg_advisory_xact_lock`, `insert_snapshots`ın ilk
    ifadesi; kurtarma prosedürü RUNBOOK §2.
    **Ölçülmeyen:** kilidin gerçekten beklettiği. Test sahte bağlantıyla **ifade
    sırasını** kanıtlıyor; iki gerçek oturumun serileştiği canlıda hiç denenmedi.
28. **Toplayıcı tablonun SAHİBİ olarak bağlanıyor.** Append-only tetikleyici `UPDATE`
    ve `DELETE`i reddediyor — **ama sahibe karşı değil.** Bugünkü `DATABASE_URL`
    `ALTER TABLE odds_snapshots DISABLE TRIGGER …` ve `TRUNCATE` yapabilir; TRUNCATE
    satır tetikleyicisini zaten hiç ateşlemez. Yani koruma, ürünün vaadinin **adını
    koyduğu aktöre** karşı savunma yapmıyor; kazayı ve daha az yetkili bir yoldan
    geleni durduruyor. Dış çıpa boşluğu kısmen kapatır (TRUNCATE'i yakalar), yetkiyi
    kapatmaz. **En az yetkili rol yok** → `docs/DEFERRED.md` §2.1.
29. **Çıpa SİLİNMESİ, bozulmasından daha sessiz.** Bozuk çıpa `ÇIPA UYUŞMAZLIĞI` ya da
    `EN YENİ ÇIPA ATLANDI` bastırır; **silinen** çıpa hiçbir şey bastırmaz —
    `_scan_anchors` yalnız var olanı görür, "dün kaç çıpa vardı" hiçbir yerde tutulmaz.
    Üstelik silme, RUNBOOK §1.4'teki **meşru arşivleme** prosedüründen ayırt edilemez:
    ikisi de dosyayı `ledger/head-*.txt` glob'undan çıkarır. Yani en gürültüsüz saldırı,
    en normal operatör işlemiyle aynı ize sahip.
30. **Kaçan mühür exit 0 veriyordu.** `_report` "kaçan mühür: …"i KALICIDIR diyen bir
    yorumun altında yazıyor, ama `_exit_code` `missed_seals`e hiç bakmıyordu ve
    `seal.yml` 0'ı "mühür turu tamam" diye okuyordu: **Faz 0'ın önlemek için var olduğu
    tek sonuç başarı olarak raporlanıyordu.**
    **Kapatıldı (`cc8e9af`):** `EXIT_MISSED_SEAL = 5` + `seal.yml`'de adlandırılmış arm.
    **Ölçülmeyen:** gerçek bir turda hiç gözlenmedi; ayrıca kod tek değer taşır —
    aynı turda kredi de bittiyse 2 döner (rapor ikisini de yazar).
31. **`matches.commence_time` hiç tazelenmiyor.** `ON CONFLICT (id) DO NOTHING` eski
    saati bırakıyor. Ertelenen maçta satır filtresi API'nin (güncel) saatine, mühür
    adaylığı veritabanının (bayat) saatine bakar; **eski saatinden 24 saat sonra maç
    `commence_time > now - interval '1 day'` penceresinden sessizce düşer** — ne
    mühürlenir ne de kaçan mühür olarak raporlanır. Kapanış fiyatı kaybolur ve exit 5
    bile görünmez.
32. **`matches` tablosuna hiç girmemiş maç, kaçan mühür raporunda görünmez.** Rapor
    `matches`i tarıyor. Lig o turda düştüyse, API olayı hiç dönmediyse ya da maçın tüm
    fiyatları `price > 1.0` kontrolünü ihlal ettiyse maç hiç yazılmaz ve rapor onu
    **bilmez.** "Kaçan mühür yok" cümlesi, "bildiğimiz maçlarda kaçan mühür yok" demek.

---

## 4. Faz 1 ön koşulları

1. **Çalışan `DATABASE_URL`** — session pooler
   (`aws-0-<bölge>.pooler.supabase.com:5432`). Transaction pooler (6543) kullanılacaksa
   `prepare_threshold=None` şart (`db.py` yorumu).
2. **En az 7 günlük anlık görüntü birikimi.** Öncesinde CLV hesaplanamaz; zincirin
   kuyruk-kesme kontrolü de çıpa biriktirmeden anlamlı olmaz.
3. **Doğrulanmış lig anahtarları** — `/v4/sports` çıktısına karşı, sezon başında yeniden.
4. **Dalın merge'i.** Cron ancak varsayılan dalda çalışır (§3.2). Merge edilmeden
   sistem hiç koşmaz; kaçan kapanış oranı geri gelmez.
5. **§3.1–3.2'nin kapatılması — YARISI bitti.** İlk gerçek `snapshot` koştu
   (2026-09-19 01:31 UTC): `zincir` adımı SKIP olmadan koştu, append-only testleri
   PASS etti, çıpa yayınlandı. **Kalan:** (a) aynı ölçümün BUGÜNKÜ ağaçta tekrarı —
   o koşudan bu yana 19 test eklendi; (b) gerçek bir `seal` turu hiç koşmadı, yani
   mühür penceresinin canlı maç saatiyle hizası hâlâ ölçülmedi (§3.5/20).
6. **`docs/DEFERRED.md` okunmuş olmalı.** Faz 1 planı o listeyi tek tek kapatmak
   zorunda değil, ama **okumadan** başlamamalı: §3.1 (zincirin içi hiç yeniden
   hash'lenmiyor), §2.1 (en az yetkili rol yok) ve §4.1 (satır başına bir INSERT →
   ~4 dakikalık tur, mühür kuyruğuyla etkileşimi) Faz 1'in tasarımını etkiler.

> **Dizüstünden elle `collect snapshot` koşulacaksa:** artık güvenlidir (`efca310`
> defter kilidini ekledi), ama **yalnız kilitli sürümü koşan** bir çalışma ağacından.
> Daha eski bir checkout'tan koşulan bir tur, aynı anda koşan bir cron'la zinciri
> kalıcı olarak çatallar; kurtarma yolu RUNBOOK §2'dedir ve bedeli kesittir.

---

## 5. Açık sorular (spec §10'dan devredilenler)

1. **İddaa boşluğu.** TR kullanıcısı yalnız İddaa'da oynuyor ve marj Avrupa ortalamasının
   üstünde — Avrupa konsensüsüne göre bulunan value orada value olmayabilir.
   Nesine ToS §4.2.1 ticari kullanımı yasaklıyor → veri kaynağı hukuki soru.
2. **Lisans zinciri.** `xgabora/Club-Football-Match-Data` MIT ilan ediyor ama verisi
   football-data.co.uk'tan türemiş; o kaynağın lisansı ticari türevleri dışlıyor.
   **Ticari lansman öncesi avukata sorulacak.** Şimdilik: eğitim verisi, ham satır yayınlanmaz.
3. **Transfermarkt robots.txt** doğrulanmadı (Faz 1).
4. **Jev'in çok dilli doğruluğu** ölçülmedi (Faz 1 şartı).
5. **Highlightly $9.49 planında oran var mı** — teyit alınmadı; yedek olarak duruyor.
6. **API-Football ücretsiz katman sezon aralığı** birincil kaynaktan doğrulanmadı
   (kullanılmıyor, kayıt amaçlı).

### Faz 0'dan devreden ertelenmiş bulgular → **`docs/DEFERRED.md`**

Üç minor bulgu (T2 `load_leagues`'in çıplak `KeyError`'ı, T3 `fetch_odds`'taki item
ataması, T4 `verify_chain`'in eksik alanda `KeyError`'ı) buradaydı; **tam liste artık
`docs/DEFERRED.md` §6'dadır** ve zincirin kör noktaları, yetki sınırı, mühür
bütünlüğü ile yazma maliyeti de oraya eklendi.

Sebebi D2: kararların tamamı `.superpowers/sdd/…` altında yaşıyordu ve o dizinin
`.gitignore`'u tek satır — `*`. Yani **hiçbiri merge olmayacaktı.** Liste burada ikinci
kez tutulmuyor: iki kopya, biri diğerinden sessizce ayrışır.
