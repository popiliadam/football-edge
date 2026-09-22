# football-edge

Futbol maçlarında **piyasa oranı ile model tahmini arasındaki sapmayı** bulan ve bunu
kurcalanmaya karşı doğrulanabilir bir sicille yayınlayan analiz sistemi.

Kuzey yıldızı **CLV**'dir (yayın anındaki oran ↔ kapanış oranı), tutturma oranı değil.
CLV'yi ölçebilmek için yayın anının ve kapanış anının **o an** kaydedilmiş olması
gerekir; sonradan üretilemez.

**Faz 0 = kayıt altyapısı · Faz 1 = toplayıcılar. Model hâlâ yok.** Sebebi tek cümle:
**kaçırılan kapanış oranı geri gelmez.** Bu yüzden veri, model beklemeden birikir.

> **Faz 1 toplayıcıları kütüphane + CLI olarak teslim edildi ve HİÇBİR ZAMANLAMAYA BAĞLI
> DEĞİL.** `snapshot`/`seal` Supabase pg_cron'dan tetikleniyor (`docs/RUNBOOK.md` §3);
> `fetch-*` komutları **elle** koşar.
> Hiç koşmayan bir toplayıcı hiçbir şey toplamaz — ayrıntı:
> [`docs/phases/01-toplayicilar/HANDOFF.md`](docs/phases/01-toplayicilar/HANDOFF.md) §3.

## Nasıl çalışır

### Oran defteri (Faz 0)

The Odds API'den çekilen her fiyat satırı, `odds_snapshots` tablosuna bir **hash
zinciri** hâlinde yazılır: her satır kendinden önceki satırın hash'ini taşır. Tablo
veritabanı seviyesinde **append-only**'dir (bir tetikleyici `UPDATE` ve `DELETE`i
reddeder). Zincirin başı düzenli olarak `ledger/head-YYYY-MM-DD.txt` altına yazılıp
depoya commit'lenir — bu **dış çıpa**, tablonun kesilip yeniden zincirlenmesini
(TRUNCATE + sahte kuyruk) yakalayan tek kanıttır.

### Kaynak gözlemleri (Faz 1)

Toplayıcılar her satırı `source_observations`a yazar: `source_id`, `entity_kind`,
`entity_key`, `observed_at`, `payload` ve bir `content_hash`. Tablo **append-only**'dir
ve `content_hash` tekilliği turları **idempotent** yapar — aynı veri ikinci kez yazılmaz.
**Hash zinciri YOKTUR** ve bu bilinçlidir: zincir, ürünün bütünlük iddiasını taşıyan
*oran* defteri içindir (`db/migrations/0002_sources.sql` başındaki yorum).

Her giden istek önce `config/sources.yaml` + `config/robots/*.txt`e karşı
**`guard_path`**'ten geçer: robots'un kapattığı bir yola istek **atılmaz**, yönlendirme
zincirinin her adımı ayrıca sorulur. Bu kural kodda zorlanır, prose'da değil — kapının
`kaynak-politikası` adımı her push'ta denetler.

| Komut | Ne yapar |
|---|---|
| `snapshot` | Aktif liglerin önümüzdeki 7 günlük maçlarının oranlarını yazar. |
| `seal` | Başlamak üzere olan maçların (varsayılan 20 dk pencere) **kapanış** oranını yazar ve maçı mühürler. |
| `verify-chain [--full]` | Zinciri ve dış çıpaları doğrular. `--full` defteri GENESIS'ten yeniden hash'ler ve HER çıpayı sorar. Kırıksa **exit 1** — ve çıpa yayını durur. |
| `publish-head` | Zincirin o anki başını `ledger/` altına yazar; baş o gün değişmediyse dosyaya dokunmaz (`zincir başı değişmedi`). |
| `sources-audit` | Kaynak kayıt defterini robots anlık görüntülerine karşı ÇEVRİMDIŞI denetler. |
| `fetch-footystats` | 6 ligin maç-başına xG/xGA tablosunu toplar. |
| `fetch-tff` | TFF'den **bu haftanın** hakem atamalarını toplar (windows-1254). |
| `fetch-news` | Etkin haber adaptörlerini koşturur (bugün: Ajansspor sitemap). |
| `fetch-venues` | Stadyum koordinatı (Wikidata REST) + maç saati havası (Open-Meteo). |
| `fetch-results` | Tamamlanmış maç skorlarını yazar (The Odds API `/scores` — **kredi harcar**). |
| `map-entities --league <id>` | Kaynak takma adlarını kanonik takımlara eşler (kod aday çıkarır, Jev seçer). |
| `calibrate --language <kod>` | Dil kalibrasyonunu ÖLÇER — **canlı Jev çağrısı, para harcar.** |
| `check-languages` | Ölçülmemiş bir dilin üretime açılmadığını doğrular (kapı adımı). |

**Kod haritası** — `src/football_edge/`:

| Katman | Modüller |
|---|---|
| Oran turu | `odds_api.py` (istemci + kota koruması) · `rounds.py` (tur orkestrasyonu) · `ledger.py` (saf hash) · `db.py` (yazma yolu + defter kilidi) · `anchors.py` (çıpa/git geçmişi) |
| Toplayıcı çatısı | `collector.py` (`fetch_text`/`assert_schema`/`assert_fresh`) · `sources.py` (robots zorlaması) · `observations.py` (gözlem deposu) · `naming.py` |
| Toplayıcılar | `collectors/` → `footystats.py` · `tff.py` · `news.py` · `venues.py` · `weather.py` · `results.py` |
| Model / eşleme | `elo.py` (**fit edilmemiş iskele**) · `mapping.py` · `jev.py` · `calibration.py` |
| CLI | `collect.py` (dispatch + defter/denetim komutları) · `fetch.py` (toplayıcı dispatch'i) · `leagues.py` |

## Kurulum

Gereken: Python ≥ 3.11 ve [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/popiliadam/football-edge.git
cd football-edge
uv sync
```

### 1. `DATABASE_URL`

**Session pooler** kullanılmalıdır (port **5432**):

```bash
# .env — gitignore'da, ASLA commit edilmez
DATABASE_URL="postgresql://postgres.<ref>:<parola>@aws-0-<bölge>.pooler.supabase.com:5432/postgres"
ODDS_API_KEY="<the-odds-api anahtarı>"
TYPESAFE_API_KEY="<typesafe anahtarı>"   # YALNIZ `calibrate` için; yoksa harness koşmaz
```

Transaction pooler (**6543**) kullanılacaksa psycopg3'ün hazırlanmış ifadeleri
kapatılmalıdır (`prepare_threshold=None`), yoksa bağlantı birkaç çağrıdan sonra
bozulur — gerekçe `db.py` → `connect()` yorumunda.

`connect()` oturum saat dilimini UTC'ye sabitler: zincir hash'i zaman damgasının
**metin hâlini** kapsar, oturum TZ'si değişirse geri okumada zincir kırılır.

Depo **public**. `.env` canlı bir API anahtarı ve veritabanı parolası tutar; kapının
`secrets` adımı `.env`in gitignore'da ve izlenmiyor olduğunu her koşuda kontrol eder.

### 2. Şema

İki migrasyon vardır ve **ikisi de idempotent'tir** (`create table if not exists` +
`create or replace function` + `drop trigger if exists`). **Sırayla** uygulanır:

```bash
psql "$DATABASE_URL" -f db/migrations/0001_init.sql     # oran defteri + maçlar + ligler
psql "$DATABASE_URL" -f db/migrations/0002_sources.sql  # gözlemler + sonuçlar + takma adlar
```

Supabase SQL Editor'a yapıştırmak da olur. **Tetikleyicilerin gerçekten kurulduğunu
doğrulayın** — append-only garantisi tamamen onlara bağlı:

```sql
select tgname from pg_trigger
where tgrelid in ('odds_snapshots'::regclass,
                  'source_observations'::regclass,
                  'match_results'::regclass);
-- beklenen: odds_snapshots_append_only, source_observations_append_only,
--           match_results_append_only
```

### 3. Çalıştırma

```bash
uv run python -m football_edge.collect snapshot              # oran turu
uv run python -m football_edge.collect seal                  # kapanış mührü
uv run python -m football_edge.collect verify-chain --full   # zincir + HER çıpa
uv run python -m football_edge.collect publish-head          # çıpa yayını

uv run python -m football_edge.collect fetch-footystats      # xG
uv run python -m football_edge.collect fetch-tff             # hakem ataması
uv run python -m football_edge.collect fetch-news            # haber
uv run python -m football_edge.collect fetch-venues          # stadyum + hava
uv run python -m football_edge.collect fetch-results         # skorlar (KREDİ HARCAR)
uv run python -m football_edge.collect map-entities --league tur.1
```

Çıkış kodları (`collect.py` → `EXIT_*`; her birinin workflow'da adlandırılmış bir
`case` arm'ı vardır): `0` arızasız · `1` zincir kırık / beklenmedik · `2` kredi
tükendi · `3` en az bir lig düştü · `4` lig aynası tazelenemedi · `5` **kaçan mühür
(kalıcı veri kaybı)** · `6` kaynak politikası ihlali · `7` en az bir kaynak düştü ·
`8` ölçülmemiş bir dil üretime açık.

`snapshot` ve `seal` komutlarını `.github/workflows/snapshot.yml` (günde bir, 06:22 UTC) ve
`seal.yml` (15 dakikada bir) koşturur. Tetik GitHub'ın `schedule`ı DEĞİL — o güvenilmez çıktı
(51 saatte ~203 mühür turunun 16'sı koştu) — Supabase pg_cron → `workflow_dispatch`
(`docs/RUNBOOK.md` §3). `seal.yml`in kendi `schedule`ı yalnız yedek ve bekçidir. Kırmızı bir
tur `ops-alert` etiketli bir GitHub issue'su açar; yeşil tur kapatır.

> **`fetch-*` komutlarının HİÇBİRİ zamanlanmış DEĞİL.** Bir toplayıcıyı cron'a bağlamak
> Faz 1'in kapsamı dışında bırakıldı ve bu, Faz 2'nin ilk işidir. Bugün elle koşulurlar.

## Kapı

```bash
./verify.sh
```

**On adım:** `ruff-check` · `ruff-format` · `mypy` · `pytest` · `paket-kurulu` ·
`kaynak-politikası` · `veri-sözleşmesi` · `dil-kalibrasyonu` · `secrets` · `zincir`.
Sonunda `KAPI YEŞİL` yazmalı.

Faz 1'in eklediği üç adım **ağa çıkmaz ve para harcamaz**:

- **`kaynak-politikası`** — `config/sources.yaml`'daki her `declared_paths`i
  `config/robots/<id>.txt` anlık görüntüsüne karşı sorar; `access_basis: api_terms`
  kaynaklarda `terms_url` zorunludur; `robots_verified_at` **30 günden eski olamaz.**
  *Bu son madde bir zamanlayıcıdır:* anlık görüntüler tazelenmezse kapı kendiliğinden
  kırmızı verir. Beklenen davranıştır — kapı gevşetilerek yeşil alınmaz.
- **`veri-sözleşmesi`** — `contract` etiketli testleri koşar ve **sayılarını ölçer**
  (`EXPECTED_MIN_CONTRACT`, bugün 18). Bir marker sessizce kaybolursa kapı kırmızı verir.
- **`dil-kalibrasyonu`** — `config/languages.yaml`'da `production_enabled: true` olan her
  dilin geçerli bir kalibrasyon raporu taşıdığını sorar. **Bugün hiçbir dil açık değil.**

Kapı her `push` ve `pull_request`te `.github/workflows/ci.yml` ile de koşar — **ama
secret'sız**: CI'a `DATABASE_URL` verilmez (defter append-only, her yazma kalıcıdır).
O yüzden CI'da `zincir` adımı koşmaz ve `SKIP: zincir (DATABASE_URL yok)` basar.
**Atlanan kontrol geçmek değildir**; bu yüzden adıyla yazılır. On adımın hepsinin
gerçekten koştuğu tek yer, `DATABASE_URL` bağlıyken koşulan yerel kapıdır.

Özet değil **çıktı** okunur: ayrıntı `$TMPDIR/football-edge-verify.log` dosyasındadır.

## Nereye bakmalı

| Dosya | Ne için |
|---|---|
| [`docs/phases/01-toplayicilar/HANDOFF.md`](docs/phases/01-toplayicilar/HANDOFF.md) | **Faz 1 devir belgesi. §3 kapının ÖLÇMEDİĞİNİ yazar — en önemli bölüm.** §6 bu fazın yöntem dersleri. |
| [`docs/phases/00-kayit-altyapisi/HANDOFF.md`](docs/phases/00-kayit-altyapisi/HANDOFF.md) | Faz 0 devir belgesi. **§3 kapının ÖLÇMEDİĞİNİ yazar.** |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Operatör prosedürleri: çıpa kilitlenmesi (§1), zincir çatalı (§2). |
| [`docs/DEFERRED.md`](docs/DEFERRED.md) | Bilerek ertelenen bulgular ve ödünleşmeler. §1-§7 Faz 0, §8-§9 Faz 1. Bir sonraki faz bunu okumadan başlamamalı. |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Oturum devri: **sırada ne var, ne push edilmeli, neye bakılmalı.** |
| `docs/superpowers/specs/` · `docs/superpowers/plans/` | Tasarım spec'i ve faz planları. **Plan belgeleri tarihseldir** — ölçüm onları yanlışladığında düzeltme notu taşırlar, ama kaynak-gerçek koddur. |

> **Bu belgelerin hepsi bayatlayabilir ve bir kez bayatladılar.** Faz 0'ın devir belgesi,
> canlı turun yanlışladığı satırları doğru diye taşımaya devam etti. Okuyan kişi test
> sayılarını ve canlı ölçümleri `git log` ile veritabanına karşı **bir kez** kontrol etsin.
