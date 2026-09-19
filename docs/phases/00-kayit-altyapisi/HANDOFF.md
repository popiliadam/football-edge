# Faz 0 — Kayıt Altyapısı · Devir Belgesi (HANDOFF)

**Tarih:** 2026-09-19 · **Dal:** `faz-0-kayit-altyapisi` · **Kapı:** `./verify.sh` → `KAPI YEŞİL`

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
| Kapı | `verify.sh` + `scripts/check_secrets.sh` | 7 adım, bu görevde 3 adım eklendi |

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

`./verify.sh` çıktısı özet değil, **log dosyasından** (`$TMPDIR/football-edge-verify.log`):

```
=== ruff-check ===
All checks passed!
=== ruff-format ===
18 files already formatted
=== mypy ===
Success: no issues found in 6 source files
=== pytest ===
..................................ss...................................  [100%]
69 passed, 2 skipped in 0.11s
=== paket-kurulu ===
/Users/apple/dev/football-edge/src/football_edge/__init__.py
=== secrets ===
secret taraması temiz
SKIP: zincir (DATABASE_URL yok)
```

`KAPI YEŞİL`, exit 0.

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

1. **`zincir` adımı ATLANDI.** Yerel kabukta `DATABASE_URL` tanımlı değil; kapı
   `SKIP: zincir (DATABASE_URL yok)` bastı. **Kapı bugüne kadar hiçbir zinciri doğrulamadı.**
   Adımın koştuğu ve kırmızı verebildiği ayrıca kanıtlandı (§2), ama **gerçek defter üstünde
   `zincir: SAĞLAM` çıktısı hiç alınmadı.**
2. **Append-only tetikleyici testleri SKIP.** `test_append_only_trigger_blocks_update` ve
   `..._blocks_delete` — `69 passed, **2 skipped**` içindeki iki skip tam olarak bunlar.
   Defter boş olduğu sürece skip kalırlar. **Bu Faz 0'ın merkezî iddiasıdır ve test paketi
   şu an onu ölçmüyor.** (Tetikleyici canlıda bir kez elle kanıtlandı — geri alınan bir
   transaction içinde — ama bu kapının ölçümü değildir.)
3. **`skipif` yanıltıcı olabilir.** Guard yalnız değişkenin **tanımlı olmasına** bakar;
   veritabanına ulaşılabildiğine ya da defterin dolu olduğuna değil. Ölçüldü: sahte bir
   `DATABASE_URL` ile bu iki test skip'ten çıkıp **FAIL** oldu (`2 failed, 69 passed`).
   Yani `DATABASE_URL` set etmek kapının ölçüm şeklini değiştirir; gerçek URL + boş defter
   hâlinde ise içerideki `pytest.skip("defter boş")` devreye girer ve yine ölçülmez.

### 3.2 Hiç koşmamış şeyler

4. **Hiçbir workflow bir kez bile koşmadı.** İki bağımsız sebep, ikisi de geçerli:
   - Dal push edilmedi: `origin/faz-0-kayit-altyapisi` = `e0f0b1a`, yerel HEAD = `818e730`.
     Workflow'ları ekleyen commit (`36b1c3d`) **12 push'lanmamış commit'in içinde.**
   - Push edilse bile **GitHub `schedule` tetiğini yalnız varsayılan dalda onurlandırır.**
     Varsayılan dal `main` ve `main` yalnız `.env.example`, `.gitignore`, `docs/` taşıyor —
     workflow YAML'ları orada yok. Cron ancak merge'den sonra çalışmaya başlar.
   Dolayısıyla: secret'ların okunabildiği, `uv sync --frozen`un runner'da çalıştığı,
   concurrency grubunun iki turu gerçekten serileştirdiği, `seal.yml`'deki commit+push
   adımının `contents: write` ile geçtiği — **hiçbiri ölçülmedi.**
5. **Gerçek snapshot koşmadı.** Bu görevde kasıtlı olarak atlandı (defter append-only:
   doğrulanmamış kodun yazdığı satır asla silinemez). Yani `matches`/`odds_snapshots`
   **boş**; §3.1'deki skip'lerin sebebi de budur.
6. **Yeni SQL şekilleri gerçek Postgres'e karşı hiç koşmadı.** `_LEDGER_AFTER`, `_LEDGER_AT`,
   `_seal_candidates` sorgusu, `_stamp_sealed`'in `id = ANY(%s)` UPDATE'i, `publish-head`'in
   `count(*), coalesce(max(id),0)` sorgusu — hepsi yalnız `tests/fake_db.py` üzerinde koştu.
   Sahte bağlantı SQL metnini **parse etmez**; yazım hatası, tip uyumsuzluğu ya da eksik
   sütun ancak canlıda patlar.
7. **Dış çıpa hiç yayınlanmadı.** `ledger/` yalnız `.gitkeep` taşıyor. `verify-chain` bu
   hâlde `çıpa yok ya da okunamadı — kuyruk kesme kontrolü ATLANDI` basar ve GENESIS'ten
   doğrular. **Kuyruk kesme (TRUNCATE + sahte yeniden zincirleme) tespiti ölçülmedi.**

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
15. **Tarama CI'da koşmuyor.** Hiçbir workflow `verify.sh` ya da `check_secrets.sh` çağırmıyor;
    pre-commit hook da yok. Tarama yalnız **kapıyı elle koşan** geliştiriciyi korur.
    Push, tarama koşulmadan da yapılabilir.

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
5. **§3.1–3.2'nin kapatılması.** İlk gerçek `snapshot` + `seal` turundan sonra:
   `./verify.sh` `DATABASE_URL` tanımlıyken koşulur, `zincir` adımı **SKIP olmamalı**,
   append-only testleri **PASS olmalı** (skip değil). Bu koşu Faz 0'ın gerçek kapanışıdır.

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

### Faz 0'dan devreden ertelenmiş minor bulgular

- **T2:** `load_leagues`, YAML kökünde `leagues` anahtarı yoksa çıplak `KeyError` fırlatıyor.
- **T3:** `fetch_odds` içinde `params[...] = ...` item ataması (yerel, atılabilir dict).
- **T4:** rezerve anahtarlar çıplak isim eşleşmesiyle hariç tutuluyor (dokümante değil);
  `verify_chain` eksik alanla `KeyError` fırlatıyor; `checked` ve `failed_index` hata
  yolunda aynı değeri taşıyor.
