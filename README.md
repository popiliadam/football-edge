# football-edge

Futbol maçlarında **piyasa oranı ile model tahmini arasındaki sapmayı** bulan ve bunu
kurcalanmaya karşı doğrulanabilir bir sicille yayınlayan analiz sistemi.

Kuzey yıldızı **CLV**'dir (yayın anındaki oran ↔ kapanış oranı), tutturma oranı değil.
CLV'yi ölçebilmek için yayın anının ve kapanış anının **o an** kaydedilmiş olması
gerekir; sonradan üretilemez.

**Faz 0 = kayıt altyapısı.** Model henüz yok. Sebebi tek cümle:
**kaçırılan kapanış oranı geri gelmez.** Bu yüzden veri, model beklemeden birikir.

## Nasıl çalışır

The Odds API'den çekilen her fiyat satırı, `odds_snapshots` tablosuna bir **hash
zinciri** hâlinde yazılır: her satır kendinden önceki satırın hash'ini taşır. Tablo
veritabanı seviyesinde **append-only**'dir (bir tetikleyici `UPDATE` ve `DELETE`i
reddeder). Zincirin başı düzenli olarak `ledger/head-YYYY-MM-DD.txt` altına yazılıp
depoya commit'lenir — bu **dış çıpa**, tablonun kesilip yeniden zincirlenmesini
(TRUNCATE + sahte kuyruk) yakalayan tek kanıttır.

| Komut | Ne yapar |
|---|---|
| `snapshot` | Aktif liglerin önümüzdeki 7 günlük maçlarının oranlarını yazar. |
| `seal` | Başlamak üzere olan maçların (varsayılan 20 dk pencere) **kapanış** oranını yazar ve maçı mühürler. |
| `verify-chain` | Zinciri ve dış çıpaları doğrular. Kırıksa **exit 1** — ve çıpa yayını durur. |
| `publish-head` | Zincirin o anki başını `ledger/` altına yazar. |

Kod haritası: `src/football_edge/` → `odds_api.py` (istemci + kota koruması) ·
`ledger.py` (saf hash fonksiyonları) · `db.py` (yazma yolu + defter kilidi) ·
`leagues.py` (konfigürasyon) · `collect.py` (CLI).

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
```

Transaction pooler (**6543**) kullanılacaksa psycopg3'ün hazırlanmış ifadeleri
kapatılmalıdır (`prepare_threshold=None`), yoksa bağlantı birkaç çağrıdan sonra
bozulur — gerekçe `db.py` → `connect()` yorumunda.

`connect()` oturum saat dilimini UTC'ye sabitler: zincir hash'i zaman damgasının
**metin hâlini** kapsar, oturum TZ'si değişirse geri okumada zincir kırılır.

Depo **public**. `.env` canlı bir API anahtarı ve veritabanı parolası tutar; kapının
`secrets` adımı `.env`in gitignore'da ve izlenmiyor olduğunu her koşuda kontrol eder.

### 2. Şema

`db/migrations/0001_init.sql` tek dosyadır ve idempotent'tir
(`create table if not exists` + `create or replace function`):

```bash
psql "$DATABASE_URL" -f db/migrations/0001_init.sql
```

Supabase SQL Editor'a yapıştırmak da olur. **Tetikleyicinin gerçekten kurulduğunu
doğrulayın** — append-only garantisi tamamen ona bağlı:

```sql
select tgname from pg_trigger where tgrelid = 'odds_snapshots'::regclass;
-- beklenen: odds_snapshots_append_only
```

### 3. Çalıştırma

```bash
uv run python -m football_edge.collect snapshot       # oran turu
uv run python -m football_edge.collect seal           # kapanış mührü
uv run python -m football_edge.collect verify-chain   # zincir + çıpa doğrulaması
uv run python -m football_edge.collect publish-head   # çıpa yayını
```

Çıkış kodları (`collect.py` → `EXIT_*`; her birinin workflow'da adlandırılmış bir
`case` arm'ı vardır): `0` arızasız · `1` zincir kırık / beklenmedik · `2` kredi
tükendi · `3` en az bir lig düştü · `4` lig aynası tazelenemedi · `5` **kaçan mühür
(kalıcı veri kaybı)**.

Üretimde bu komutları `.github/workflows/snapshot.yml` (günde bir) ve `seal.yml`
(15 dakikada bir) koşturur. GitHub `schedule` tetiğini **yalnız varsayılan dalda**
onurlandırır: dal merge edilmeden hiçbir cron çalışmaz.

## Kapı

```bash
./verify.sh
```

Yedi adım: `ruff-check` · `ruff-format` · `mypy` · `pytest` · `paket-kurulu` ·
`secrets` · `zincir`. Sonunda `KAPI YEŞİL` yazmalı.

Kapı her `push` ve `pull_request`te `.github/workflows/ci.yml` ile de koşar — **ama
secret'sız**: CI'a `DATABASE_URL` verilmez (defter append-only, her yazma kalıcıdır).
O yüzden CI'da `zincir` adımı koşmaz ve `SKIP: zincir (DATABASE_URL yok)` basar.
**Atlanan kontrol geçmek değildir**; bu yüzden adıyla yazılır. Yedi adımın hepsinin
gerçekten koştuğu tek yer, `DATABASE_URL` bağlıyken koşulan yerel kapıdır.

Özet değil **çıktı** okunur: ayrıntı `$TMPDIR/football-edge-verify.log` dosyasındadır.

## Nereye bakmalı

| Dosya | Ne için |
|---|---|
| [`docs/phases/00-kayit-altyapisi/HANDOFF.md`](docs/phases/00-kayit-altyapisi/HANDOFF.md) | Faz 0 devir belgesi. **§3 kapının ÖLÇMEDİĞİNİ yazar** — en önemli bölüm. |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Operatör prosedürleri: çıpa kilitlenmesi (§1), zincir çatalı (§2). |
| [`docs/DEFERRED.md`](docs/DEFERRED.md) | Bilerek ertelenen bulgular ve ödünleşmeler. Faz 1 bunu okumadan başlamamalı. |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Oturum devri (süreç notları). |
| `docs/superpowers/specs/` · `docs/superpowers/plans/` | Tasarım spec'i ve faz planları. |
