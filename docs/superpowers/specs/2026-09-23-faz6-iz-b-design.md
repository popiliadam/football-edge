# Faz 6 İz B — halka açık web sitesi, okuma katmanı, sicil (tasarım)

**Tarih:** 2026-09-23 · **Durum:** TASLAK, kullanıcı onayı bekler (HANDOFF §0.6/5). Bu belgedeki her karar
**Öneri**dir; onaylananlar R-numarası alır. Numaralar geçici: tasarım önerileri `B1…`, açık kararlar `AK1…`.
**Sonraki adım:** onaydan sonra `superpowers:writing-plans` (iki plan, §15) + bağımsız plan incelemesi.
**Girdi:** ana tasarım `2026-09-19-football-edge-design.md` §1, §3.2, §6, §9, §10 · yol haritası
`2026-09-19-faz-1-7-yol-haritasi.md` Faz 6–7 · `2026-09-21-yol-haritasi-v2-paralel-izler.md` §2 İz B, §3 ·
`docs/HANDOFF.md` §0.6/5–6, §0.7 · `docs/phases/03-baz-model/HANDOFF.md` §1 · `db/migrations/0001–0012` ·
`docs/reports/2026-09-23-kaynak-kosullari.md`, `2026-09-23-ek-kaynaklar.md` · `verify.sh`, `.github/workflows/ci.yml` ·
`docs/DEFERRED.md` 12a.

> **R163 notu.** Faz 4 tasarımı R163 "İz B Faz 4'le paralel başlamaz" diyordu (gerekçe: dört implementer sınırı,
> Netlify yok). Kullanıcının 2026-09-23 kararı (HANDOFF §0.6) İz B'yi oturum 9 Dalga B'ye aldı: Faz 4 Plan 2 en erken
> 2026-10-07'de başlıyor, arada implementer kapasitesi boş. Dört implementer sınırı aynen geçerli.

---

## 0. Önerilen tasarım kararları

| No | Öneri | Gerekçe | Yanlışsa bedeli |
|---|---|---|---|
| B1 | **Mimari A:** derleme anında salt okuma rolüyle DB'den anlık görüntü → statik site → Netlify'a hazır dizin yüklenir (§3) | Tarayıcıya ve Netlify'a DB anahtarı gitmez; SEO için tam HTML; sayfa ↔ veri uyuşması derleme anında ölçülebilir | Tazelik derleme sıklığına bağlı (dakikalar–saat) |
| B2 | **DB'ye yalnız Python dokunur.** Dışa aktarım `src/football_edge/site/` (Python) → tek JSON anlık görüntü; Next.js yalnız bu JSON'u okur, Node tarafında DB sürücüsü yok | Oran/olasılık/CLV hesabı modelle AYNI kodla yapılır (spec §6.3 "iki yol yazılmaz"); K1 kodu mevcut kapının (ruff, mypy, pytest) altında kalır | İki dil arasında sözleşme dosyası (§5) bakımı |
| B3 | **İki şema, bir rol:** `site` (içindeki her kolon yayımlanabilir) + `site_audit` (yalnız zincir doğrulaması; yayımlanmaz); rol `site_reader` yalnız bu iki şemayı okur, hiçbir tabloya yetkisi yoktur | "Siteye ne açık?" sorusunun cevabı tek bir şema listesi olur; test edilebilir | Görünüm sahibinin (tablo sahibi) yetkisiyle okunur — görünüm tanımı güvenlik sınırıdır, K1 incelemesi şart |
| B4 | **Holdout tabanı:** her `site` görünümü `commence_time >= site.public_floor()` süzer; taban `HOLDOUT_END + 1 gün` (2026-07-02 00:00 UTC) ve Python sabitinden türetildiği testle kanıtlanır | Holdout üyeliği kaynağın YEREL tarihiyle belirlenir (`holdout.py`); UTC−12'de 2026-06-30 akşamı UTC'de 07-01'e düşer — bir günlük pay bunu kapatır. Canlı defter 2026-09-19'da başladığı için payın maliyeti sıfır | — |
| B5 | **Sicil yer tutucu görünümü:** `site.record` bugün `WHERE false` ile tipli ve 0 satırlı; Faz 5 aynı kolonlarla `CREATE OR REPLACE` eder | Postgres `CREATE OR REPLACE VIEW`de kolon değiştirmeye izin vermez: sözleşmeyi veritabanı zorlar | Faz 5 kolon eklemek isterse yeni sürüm görünüm (`record_v2`) |
| B6 | **Anlık görüntü şeması v1'de `value_badge: null`, `analysis: null`, model olasılığı alanı YOK** (JSON Schema `const: null`, `additionalProperties: false`) | "Sitede value önerisi yok" ve "Faz 7 doğrulama geçidi olmadan metin yok" kodla zorlanır; şema sürümü artmadan dolamaz | — |
| B7 | **Maç sayfası yalnız vig'i temizlenmiş piyasa konsensüs olasılığını gösterir** — kitap adı, kitap bazında oran, bağlantı yok (AK8) | Kaynak politikası §3.2/4 (ham içerik yok), TR'de bahis reklamı riski (§10.3), The Odds API koşulları okunmadı (AK17) | İçerik incelir (§8.5 panzehirleri) |
| B8 | **İlk sürümlerde her sayfa `noindex`**; indekslemeye açma ayrı bayrak (`SITE_INDEXABLE`) ve AK14 onayına bağlı | Hukuk metinleri onaysızken kazara yayın bile arama motoruna girmesin | — |
| B9 | **Deploy hazır, bağlı değil:** `web/netlify.toml` + `.github/workflows/site.yml` yalnız `workflow_dispatch`, secret yoksa adıyla kırmızı; zamanlama/pg_cron tetiği YOK | HANDOFF §0.6/6 | — |
| B10 | **Site kapısı `verify.sh`in adımı olur** (tek kapı); DB davranış testleri CI'da geçici `supabase/postgres` servis kabında koşar | "Kapı = CI'ın koştuğu adımlar"; görünüm testleri gerçek Postgres ister, üretim DB'sine bağlanmadan | CI süresi uzar (ölçülecek) |
| B11 | **Eski tablolara RLS + TRUNCATE tetikleyicisi (DEFERRED 12a)** ayrı migration olarak yazılır; uygulanması siteden bağımsız karar (AK7) | Bugün `leagues`, `matches`, `odds_snapshots`, `source_observations`, `match_results`, `entity_aliases` RLS'siz; Supabase API rolleri yetkiliyse REST'ten okunabilir, `odds_snapshots` TRUNCATE ile boşaltılabilir | Boru hattı tablo sahibi değilse RLS yazımı durdurur — uygulama öncesi ROLLBACK'li provada ölçülür |
| B12 | **İki plan:** B-1 okuma katmanı + dışa aktarım + sözleşme (K1) önce; B-2 web yüzeyi + kapı + deploy hazırlığı (K2/K3) B-1'in sözleşme görevinden sonra paralel (§15) | Tek plan K1 ile K3'ü aynı inceleme ağırlığına zorlar | — |

---

## 1. Amaç, kapsam, kapsam dışı

**Amaç:** Faz 6'nın modelden bağımsız kısmını yerelde, deploy etmeden kurmak: statik site iskeleti, salt okuma
katmanı (migration YAZILIR, canlıya UYGULANMAZ), defterden türetilen sicil sayfası ve onun doğrulanabilirliği, pSEO
yapısı, schema.org, yasal metin taslakları, bağlanmamış deploy. Ürün sözü "radikal şeffaflık"tır (spec §0): sicil
sayfası defterle ayrışırsa iddia çöker — kapı bunu ölçer.

**Kapsam (yol haritası Faz 6 T1, T3–T7; T2 yer tutucuyla):**
- T1 Next.js iskeleti + okuma katmanı (§3–§5).
- T2 Maç sayfası şablonu: piyasa konsensüsü, mühür durumu; "value" rozeti Faz 5'e kadar boş yer (§7).
- T3 Sicil sayfası: defterden türetilir, zincir başı gösterilir, sayfa ↔ defter uyuşması kapıda (§6).
- T4 pSEO: lig/takım/maç kırılımı, `hreflang`, site haritası; dil listesi yer tutucu (§8).
- T5 schema.org (§9). T6 18+/sorumlu bahis/KVKK/çerez metin TASLAKLARI (§10). T7 `netlify.toml` + Actions (§11).

**Kapsam dışı (YAGNI):**
- Hesap, ödeme, bülten, form, yorum, affiliate, bahisçi bağlantısı (Faz 8; spec §1.3).
- **Value önerisi ve model olasılığı** — Faz 3 sonucu: Jev'siz baz model piyasayı log loss'ta yenmedi, harman
  piyasadan ayırt edilemez ve bahis kuralı kapanışa karşı negatif CLV verdi (`docs/phases/03-baz-model/HANDOFF.md`
  §1). Bu sonuç Faz 5'in CLV kapısı geçilene kadar sitede öneri yayımlanmamasının sebebidir.
- Faz 7 içerik hattı (Sonnet metni, Jev doğrulama geçidi). Yeri hazırdır (§8.6), içerik yoktur.
- Haber, sakatlık, kadro, hakem, hava, stadyum verisi — sitede HİÇBİR kaynak metni ya da oyuncu düzeyi bilgi yok
  (§2 H2; sakatlık = sağlık verisi, KVKK md. 6 — HANDOFF §0.7/7).
- football-data.co.uk'tan türetilmiş her şey (Elo, verimlilik sıralaması, tarihsel form, skor): yazılı izin yok
  (spec §10/2) ve holdout o kaynağın içinde yaşar.
- Canlıya migration uygulamak, Netlify'a yayın, alan adı, secret eklemek (HANDOFF §0.7).

**Bugünkü gerçek (tasarımın dayandığı ölçülmüş durum):**
- Defter (`odds_snapshots`) 2026-09-19'dan beri hash zinciriyle yazılıyor; zincir başı her gün `ledger/head-*.txt`
  olarak public depoya commit'leniyor (`seal.yml`, `publish-head`). Zincir yalnız oran defterini kapsar;
  `model_predictions` ve diğer tablolar append-only ama zincirsiz.
- **Defterde yayınlanmış tahmin YOK.** `model_predictions` gölge satırlarıdır, "YAYIN YOK" (0009).
- `match_results` dolmuyor; gölge raporu sonucu football-data'dan alıyor (`live/report.py`). Yani sitenin kendi
  hakkıyla gösterebileceği bir skor kaynağı bugün yok (AK10).
- Depo ve Actions logları public (RUNBOOK §3.8): derleme logu yayın kanalıdır.

---

## 2. Sert kurallar ve nasıl zorlandıkları

Her kural kodda bir bekçiye bağlanır; prose kural yazılmaz. "Kapının ölçmediği" §12.4'te.

| Kural | Zorlayan (hepsi kapıda) |
|---|---|
| **H1 — Holdout verisi sitede ASLA görünmez.** Holdout verisi = maç tarihi `[2025-07-01, 2026-07-01)` olan her satır VE ondan türetilmiş her sayı (Faz 3 raporunun C1–C6 sayıları dahil). Sitede holdout sonucu en çok nitel bir cümleyle anılır, sayı taşımaz | (a) görünüm bağımlılık testi: `site`/`site_audit` görünümlerinin `pg_depend` kapanışı yalnız `leagues`, `matches`, `odds_snapshots`; `hist_*`, `holdout_access_log`, `model_predictions`, `news_items`, `jev_*`, `source_observations`, `entity_aliases`, `match_results` YASAK · (b) davranış testi: holdout penceresine, sınırın iki yanına tohumlanan maçlar görünümde 0/1 satır · (c) `site.public_floor()` ↔ `HOLDOUT_END + 1 gün` eşitlik testi · (d) dışa aktarıcı her maç için `commence_time >= floor` iddia eder, aksi hâlde adıyla exit · (e) çıktı tarayıcısı anlık görüntüde tabandan eski tarih bulursa kırmızı · (f) testler `leakage` işaretini taşır, `EXPECTED_MIN_LEAKAGE` ölçülerek yükseltilir |
| **H2 — Ham kaynak metni ve oyuncu düzeyi bilgi yok** (spec §3.2/4) | (a) aynı bağımlılık allowlist'i · (b) anlık görüntü şeması `additionalProperties: false`; serbest metin alanı yalnız takım adı, lig adı, ülke — tip ve uzunluk sınırlı · (c) tarayıcı `http`, `<`, `>` taşıyan veri dizesini reddeder |
| **H3 — Value önerisi ve model olasılığı yok** (Faz 5'e kadar) | Şema `value_badge: const null`; model alanı şemada yok; `model_predictions` görünüm allowlist'inde yok |
| **H4 — Lisans iddiası yok** (spec §3.2/5) | Metin tarayıcısı `web/content/**` ve derlenmiş HTML'de "lisanslı", "licensed", "resmî veri", "official data" ve ilgili kalıpları kırmızı yapar |
| **H5 — Tarayıcıya ve Netlify'a hiçbir anahtar gitmez; Node DB'ye bağlanmaz** | (a) `web/package.json` bağımlılık allowlist testi (DB sürücüsü, `@supabase/*` yok) · (b) çıktı tarayıcısı `postgres://`, `postgresql://`, `service_role`, `eyJ` (JWT öneki), `SUPABASE_`, `NETLIFY_AUTH` kalıplarını kırmızı yapar · (c) `scripts/check_secrets.sh` zaten `SUPABASE_[A-Z_]*KEY` atamasını tarar · (d) `site.yml` testi: iş yalnız `SITE_DATABASE_URL`, `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID` alır; `DATABASE_URL`, `ODDS_API_KEY`, `TYPESAFE_API_KEY` ALMAZ (m10 deseni) |
| **H6 — Sicil yalnız defterden türetilir, elle yazılmaz** | §6.4 uyuşma kontrolleri; TS tarafı sayı HESAPLAMAZ, yalnız biçimler (tarayıcı: sayfada görünen her sayı anlık görüntüde birebir var) |
| **H7 — Onaysız indeksleme yok** | `SITE_INDEXABLE` yoksa her sayfa `<meta name="robots" content="noindex">` + `netlify.toml` `X-Robots-Tag: noindex`; tarayıcı bayrak kapalıyken bir tane indekslenebilir sayfa görürse kırmızı |

---

## 3. Mimari yaklaşımlar

### 3.1 Seçenekler

**(A) Derleme anında anlık görüntü, statik yayın.** Actions işi `site_reader` rolüyle bağlanır, `site` görünümlerini
okur, zinciri `site_audit` üzerinden doğrular, tek bir JSON anlık görüntü üretir; `next build` (`output: 'export'`)
bu JSON'dan statik HTML üretir; `netlify deploy --prod --dir web/out` hazır dizini yükler. Netlify derleme yapmaz,
secret tutmaz; tarayıcı yalnız HTML/CSS/statik JSON görür.

**(B) Supabase anon anahtarı + RLS'li salt okuma görünümleri, istemci/ISR.** Görünümler PostgREST'e açılır,
tarayıcı ya da Netlify fonksiyonu anon anahtarıyla okur; SEO için sunucu tarafı çizim/ISR (Netlify'da Next çalışma
zamanı ve fonksiyonlar).

**(C) Karma.** A'nın statik sayfaları + canlı parçalar (ör. son oran turu) için B'nin anon okuması.

### 3.2 Karşılaştırma

| Ölçüt | A | B | C |
|---|---|---|---|
| Anahtar sızması | DB kimliği yalnız Actions secret'ında; tarayıcıda yok | Anon anahtarı tasarım gereği public; tek güvence RLS/yetki doğruluğu | B ile aynı |
| Bugünkü açık (DEFERRED 12a) | Etkilenmez: `site_reader` tabloya dokunmaz | **Ön koşul:** 12a uygulanmadan anon anahtarı yayımlamak eski tabloları REST'e açabilir (Supabase varsayılan yetkileri) | B ile aynı |
| Append-only defter | Salt okuma rolü + `default_transaction_read_only`; yazma yolu yok | Anon yazma yetkisi yanlışlıkla açıksa INSERT tetikleyiciye takılmaz (tetikleyici yalnız UPDATE/DELETE) | B ile aynı |
| Veri yüzeyi | Yalnız anlık görüntüdeki alanlar; kazıyıcı en çok sitenin kendisini alır | PostgREST süzme/sıralama: görünümün tamamı sorgulanabilir; hız sınırı bizde | Kısmen B |
| Supabase tuzağı | — | Görünümler varsayılan olarak sahibinin yetkisiyle koşar (RLS'i atlar); `security_invoker` unutulursa sızıntı | B ile aynı |
| Public loglar | Derleme logu yalnız sayı ve hash basar (test edilir) | Log riski düşük; istemci ağ trafiği herkese açık | — |
| Tazelik | Derleme sıklığı (öneri: günlük tur + saatte en çok bir mühür sonrası, AK15) | Saniyeler | Karma |
| SEO | Tam statik HTML, en hızlı TTFB | ISR/SSR gerekir; istemci çizimi arama motoruna zayıf | İyi |
| Maliyet | Actions dakikası (public depo) + Netlify statik barındırma; sunucu fonksiyonu yok | Netlify fonksiyon çağrıları + Supabase API trafiği (ziyaretçi başına) | İkisi |
| Sayfa ↔ defter uyuşması | **Derleme anında ölçülebilir:** yayımlanan her bayt doğrulanmış anlık görüntüden gelir, hash'i yayımlanır | Her istekte farklı veri; "bu sayfa defterle uyuştu" iddiası anlık kanıtlanamaz | Statik kısım için A kadar |
| Bağımlılık | `next`, `react`, `react-dom` + dev araçları | + Supabase istemcisi, Netlify Next çalışma zamanı | En geniş |

### 3.3 Öneri: A (B1)

Gerekçe sırasıyla: (1) **şeffaflık iddiası ölçülebilir kalır** — site bir anlık görüntünün çizimidir, anlık görüntü
defterle karşılaştırılır ve hash'i yayımlanır; B'de "gösterilen = defter" iddiasını kanıtlayan bir an yoktur.
(2) **Sızıntı yüzeyi en küçük** — anahtar tarayıcıya gitmez, DEFERRED 12a'nın açığı siteye bağlı kalmaz.
(3) **Maç öncesi ürün** (spec §1.3, in-play yok): dakikalık tazelik gerekmez. (4) En az bağımlılık, sunucu yok.
Bedel: tazelik derleme sıklığıdır; mühür sonrası tetik (AK15) kapanışın sitede görünme gecikmesini ≤ 1 saat tutar.
C'nin canlı parçası ihtiyaç ölçülürse (ör. kullanıcı talebi) statik JSON'la A içinde çözülür; anon anahtarı gerekmez.

---

## 4. Okuma katmanı sözleşmesi

### 4.1 Migration'lar (YAZILIR, canlıya UYGULANMAZ)

Numaralar plan yazılırken yeniden bakılır (bugün sıradaki 0013/0014; Dalga A başka migration eklerse kayar).

1. **`0013_legacy_rls.sql` (B11, DEFERRED 12a):** `leagues`, `matches`, `odds_snapshots`, `source_observations`,
   `match_results`, `entity_aliases` için `enable row level security` (politika YOK, R90 deseni); `odds_snapshots`,
   `source_observations`, `match_results` için `before truncate` ifade tetikleyicisi; `forbid_ledger_mutation()`
   mesajı `tg_table_name` kullanır (12a'nın ikinci yarısı). **Risk:** boru hattı tablo sahibi olarak bağlanmıyorsa RLS
   yazmayı durdurur ve mühür kaybolur — uygulama adımı önce `pg_tables.tableowner` ↔ bağlantı rolü okumasını ve
   ROLLBACK içinde bir snapshot turunu ister (HANDOFF §0.5 "gerçek DB'ye ilk yazım öncesi aynı SQL ROLLBACK içinde").
2. **`0014_site_read.sql`:** şemalar, rol, görünümler, yer tutucu sicil (aşağıda).

### 4.2 Rol ve yetkiler

- `create role site_reader nologin noinherit` (idempotent `DO` bloğu). **Parola ve `LOGIN` migration'da YOK** —
  onaydan sonra RUNBOOK adımıyla elle verilir (parola depoya girmez; AK18).
- `alter role site_reader set default_transaction_read_only = on; set statement_timeout = '30s'`.
- `revoke all on schema site, site_audit from public`; `grant usage` ve `grant select on all tables` yalnız
  `site_reader`'a. `anon`, `authenticated`, `service_role` bu şemalara hiçbir yetki almaz.
- `site_reader` hiçbir `public` tablosunda, `ops` şemasında, fonksiyonda yetki almaz.
- `site` ve `site_audit` Supabase'in API'ye açık şemalarına (`public`, `graphql_public`) EKLENMEZ; uygulama anında
  Supabase advisors okunur.
- Görünümler tablo sahibi olan rolün yetkisiyle koşar (varsayılan): `site_reader` tabloya yetkisiz, yalnız görünümün
  seçtiği kolonları görür. **Görünüm tanımı güvenlik sınırıdır** → K1.

### 4.3 Görünümler

`site` şemasındaki her kolon yayımlanabilir kabul edilir; eklenen her kolon AK6 onayı ister.

| Görünüm | Kolonlar | Kaynak ve süzgeç |
|---|---|---|
| `site.public_floor()` | `timestamptz` döner: `2026-07-02 00:00:00+00` | `IMMUTABLE` SQL fonksiyonu; tek yer |
| `site.leagues` | `id`, `name`, `country` | `leagues where active` |
| `site.matches` | `id`, `league_id`, `commence_time`, `home_team`, `away_team` | `matches where commence_time >= site.public_floor()`; `sealed_at` alınmaz (tabloda UPDATE edilir, anlık görüntü belirlenimsiz olur — mühür durumu defter satırından türetilir) |
| `site.h2h_quotes` | `ledger_id`, `match_id`, `observed_at`, `is_closing`, `outcome`, `price`, `book_key` | `odds_snapshots` ⋈ `site.matches`, `market = 'h2h'`; `book_key` = tur içinde `dense_rank() over (partition by match_id, observed_at order by bookmaker)` — kitap adı yok, turlar arası izlenemez |
| `site.ledger_head` | `rows`, `last_id`, `head` | `count(*)`, `max(id)`, son satırın `row_hash`i |
| `site.record` (B5) | `publication_id bigint`, `match_id text`, `market text`, `outcome text`, `published_at timestamptz`, `published_price numeric`, `publication_ledger_id bigint`, `closing_fair_price numeric`, `clv double precision`, `publication_hash text` | Bugün `select … where false` (0 satır, tipli). Faz 5 `publications` tablosuna aynı kolonlarla bağlar |
| `site_audit.ledger_rows` | `odds_snapshots`in `collect._LEDGER_COLUMNS` ile birebir kolonları | Yalnız zincir doğrulaması için; **yayımlanmaz** (§5.3 tarayıcısı `site_audit` alanlarının anlık görüntüye girmediğini sınar) |

Kitap bazında satır (`book_key`) konsensüsün "üç sonucu tam kitapların ortalaması" tanımı (`live/context.pre_prices`)
için gerekir; dışa aktarıcı AYNI fonksiyonu çağırır (`Quote.bookmaker = book_key`), anlık görüntüye yalnız ortalama
ve kitap SAYISI girer.

### 4.4 Testler (üç katman)

1. **Metin (her kapıda, DB'siz):** `0014` dosyasında yasak tablo adları geçmez; her `create view site.` gövdesi
   `site.matches` ya da `site.public_floor()` üzerinden süzer; `grant` satırları yalnız `site_reader` adını taşır;
   `LOGIN`/`PASSWORD` kelimesi yok. `0013` için mevcut `test_jev_tables_db.py` deseni (RLS + tetikleyici listesi).
2. **Katalog + davranış (yerel Postgres kabı, `supabase/postgres` 17.6 imajı):** 0001→0014 sırayla uygulanır;
   `pg_depend` kapanışı allowlist'e eşit; `has_schema_privilege('anon','site','usage') = false`;
   `has_table_privilege('site_reader','public.odds_snapshots','select') = false`; `site_reader` INSERT deneyi
   reddedilir; `rolbypassrls = false`; holdout tohumları: `2026-01-15`, `2026-07-01 11:59Z` (0 satır), `2026-07-02
   00:00Z` (1 satır); `CREATE OR REPLACE VIEW site.record` farklı kolonla denenince hata (B5'in DB zorlaması).
3. **Koruma:** davranış testleri append-only tablolara satır yazar — yalnız ATILABİLİR veritabanında. Fixture
   `SITE_TEST_DATABASE_URL`'in ana makinesi `localhost`/`127.0.0.1`/CI servis adı değilse ya da `DATABASE_URL`e
   eşitse testleri adıyla REDDEDER (kırmızı, SKIP değil). Değişken yoksa `SKIP: site-db (SITE_TEST_DATABASE_URL yok)`.

### 4.5 Uygulama (onaydan sonra; bu tasarımın işi değil)
AK6/AK7 onayı → ROLLBACK'li prova → `apply_migration` → katalog testleri gerçek DB'ye karşı salt okuma kipinde
(mevcut `test_jev_tables_db.py` deseni) → RUNBOOK'a `site_reader` parola/`LOGIN` adımı.

---

## 5. Dışa aktarım ve anlık görüntü sözleşmesi

### 5.1 Modül ve komutlar
`src/football_edge/site/` — `export.py`, `verify.py`, `__main__.py`. Komutlar:
- `python -m football_edge.site export --out <dizin>` — `SITE_DATABASE_URL` ile bağlanır; `site.ledger_head`'den
  kesim `last_id`'yi alır ve BÜTÜN oran sorgularını `ledger_id <= last_id` ile keser; maç kümesi = kesim içinde en
  az bir oran satırı olan `site.matches` satırları (anlık görüntü aynı kesimle yeniden üretilebilir);
  `snapshot.json` + `snapshot.sha256` yazar. Log yalnız sayı ve hash basar.
- `python -m football_edge.site verify-export <dizin>` — §6.4 kontrolleri; kırmızıda adıyla exit, yayın durur.
- `SITE_DATABASE_URL` `_log_secrets`e eklenir (RUNBOOK §3.8, DEFERRED 10o); redaksiyon testi genişler.

### 5.2 Anlık görüntü v1 (`web/contract/snapshot.schema.json`, JSON Schema; her nesnede `additionalProperties: false`)

```
schema_version: 1
generated_at, git_sha
ledger:   { rows, last_id, head, anchor: { file, rows, last_id, head } }   # çıpa: depodaki en yeni ledger/head-*.txt
floor:    "2026-07-02T00:00:00Z"
leagues:  [ { id, slug, name, country } ]
teams:    [ { league_id, slug, name } ]
matches:  [ { id, league_id, slug, date, commence_time, home, away,
              sealed: bool,                                   # kesim içinde is_closing satırı var mı
              h2h: { opening|latest|closing: { observed_at, books: int, p: { home, draw, away } } | null } } ]
record:   { published: int, entries: [ … site.record kolonları … ] }
value_badge: null          # const null — Faz 5 şema sürümünü artırır
analysis:   null           # const null — Faz 7 şema sürümünü artırır
```
- `p` = vig'i temizlenmiş konsensüs, `market.devig` ile, yöntem `config/model_faz3.yaml`'daki (`power`) — model kodu
  neyse o. `books < SITE_MIN_BOOKS` (öneri 3) ise o tur `null`.
- Olasılıklar 4 ondalığa yuvarlanır (yuvarlama anlık görüntüde, TS'de değil).
- Python şemayı dışa aktarımda ve `web/fixtures/snapshot.fixture.json` üzerinde pytest'te doğrular (doğrulayıcı
  seçimi — `jsonschema` bağımlılığı mı el yazımı mı — planda). TS tarafı `Snapshot` tipini elle taşır ve fixture
  `satisfies Snapshot` ile `tsc`'de sınanır; bir pytest şemanın anahtar kümesini TS tip dosyasınınkiyle karşılaştırır.
- Fixture **sentetiktir** (uydurma lig/takım adları, gerçek satır yok): gerçek anlık görüntü depoya commit'lenmez
  (`.gitignore`: `web/node_modules`, `web/.next`, `web/out`, `web/.snapshot`).

### 5.3 Çıktı tarayıcısı (`web/scripts/check-out.ts`, Node'un yerleşik tip ayıklamasıyla koşar, bağımlılıksız)
Girdi: anlık görüntü + `web/out/**`. Ölçer: (1) her maç/lig/takım için tam bir sayfa, her sayfa için tam bir kayıt;
(2) sayfadaki `data-fe-*` işaretli her sayı anlık görüntüde birebir (H6); (3) sicil sayfasındaki `rows`, `last_id`,
`head`, `published` ve anlık görüntü hash'i anlık görüntüye eşit; (4) `hreflang` karşılıklı, kendine atıflı,
`x-default` var; (5) site haritası = indekslenebilir sayfa kümesi; (6) H1/H2/H4/H5/H7 kalıpları; (7) basit
erişilebilirlik: `<html lang>`, tek `<h1>`, `alt`, `<main>`, başlık sırası.

---

## 6. Sicil sayfası (T3)

### 6.1 Ne gösterir
- **Yayınlanmış tahminler** (`record.entries`): an, maç, market, sonuç, yayın oranı, kapanış adil oranı, CLV;
  özet: sayı, ortalama CLV ve güven aralığı (aralık Python'da `market.metrics.bootstrap_mean` ile hesaplanır).
- **Defter durumu:** zincir başı (`head`), satır sayısı, son id, dışa aktarım anı; depodaki en yeni çıpa dosyasının
  adı, değeri ve GitHub'daki commit bağlantısı; anlık görüntünün sha256'sı ve `/data/snapshot.json` indirmesi.
- **Nasıl doğrulanır** bölümü (§6.3).

### 6.2 Sicil boşken (bugün) — dürüst metin
"Yayınlanmış tahmin: **0**." Altında, sayı taşımadan (H1): "Temel modelimiz kapanış piyasasını geçmediği için henüz
tahmin yayımlamıyoruz. Yayın, önceden kaydedilmiş CLV kapısı geçildiğinde başlar; o güne kadar defter oranları ve
kapanışları kaydetmeye devam ediyor." Defter durumu bloğu dolu gösterilir: kayıt altyapısının çalıştığının kanıtı
odur. Boş durum bir **hata değil, bir durumdur**: `record.published = 0` ile boş liste tutarlı olmalı; ikisi
ayrışırsa kapı kırmızı. "Yakında", sahte örnek, geriye dönük backtest sonucu GÖSTERİLMEZ (backtest yayın değildir
ve holdout'u taşır).

### 6.3 Zincir başının kullanıcıya gösterimi ve doğrulamanın sınırı
Gösterilen: DB'deki baş + depodaki çıpa. Aynı gün ve aynı `last_id` ise "çıpa ile eşleşiyor"; defter çıpadan
ilerideyse "çıpa `<tarih>`: `<last_id>` satırına kadar; sonrası bir sonraki çıpada" yazılır.
**Dürüst sınır (sayfada yazılır):** zincir doğrusal; bir satırın başa bağlandığını göstermek, ondan sonraki bütün
satırları ister. Bugün yayımlanan: çıpaların git geçmişi (zaman içinde tutarlılık) ve anlık görüntü hash'i. Üçüncü
kişi zinciri GENESIS'ten doğrulayamaz — tam defter dökümü kitap bazında oran yayımlamak demektir (AK9, AK17). Faz
5'le birlikte tahmin başına kanıt satırları (yayın satırı + kapanış satırları, `prev_hash`/`row_hash`) indirilebilir
olur: kullanıcı `sha256(prev_hash + kanonik_json(yük))` ile satır bütünlüğünü kendi makinesinde yeniden hesaplar.

### 6.4 Kapı: sayfa ↔ defter birebir
İki katman, çünkü CI'ın DB'si yok (bilinçli, `ci.yml` yorumu):
1. **CI'da (her push):** sentetik fixture → `next build` → çıktı tarayıcısı §5.3 (sayfa ↔ anlık görüntü). Boş sicil,
   dolu sicil, `books` eşik altı, mühürsüz maç fixture varyantlarıyla.
2. **`site.yml`'de (DB bağlı, yayından önce, sırayla; biri kırmızıysa yayın yok):**
   a. zincir: en yeni çıpadan kuyruk `site_audit.ledger_rows` üzerinden, mevcut `verify_chain` + çıpa kontrolü
      (`_anchor_break`) aynı fonksiyonlarla — ikinci bir zincir okuyucusu yazılmaz; okuyucuyu kaynağa parametrelemek
      17a okuyucu mühürü testleriyle birlikte planda ele alınır;
   b. `snapshot.ledger.head` = kesimdeki son satırın YENİDEN HESAPLANMIŞ hash'i (hücre değil — `_anchor_break` ilkesi);
   c. yeniden türetme: aynı kesimle ikinci dışa aktarım aynı sha256'yı üretir (belirlenimcilik);
   d. `record.published` = `site.record` satır sayısı; her girdinin CLV'si defter satırlarından yeniden hesaplanır;
   e. §5.3 tarayıcısı gerçek anlık görüntüyle;
   f. yayından sonra: canlı `/data/snapshot.sha256` indirilir ve derlenmiş olanla karşılaştırılır (yayımlanan =
      doğrulanan).

### 6.5 Faz 5'e devredilen şartlar (İz B bunları KURMAZ, sözleşmeye yazar)
- `publications` tablosu append-only + TRUNCATE tetikleyicisi + kendi hash zinciri; `site.record` ona B5 ile bağlanır.
- **Zaman kanıtı:** bir tahminin maçtan ÖNCE yayımlandığını, yayın anında public bir çıpa kanıtlamalı (günlük çıpa
  yetmez: maçtan sonra geriye tarihli satır eklenip ertesi gün çıpalanabilir). Öneri: yayın turu, tahmin zincirinin
  başını yayın anında commit'ler ve siteyi aynı turda yeniden yayımlar.
- CLV tanımı tek fonksiyon (Faz 3 `wf_eval` CLV hesabından ayrılmış), sitede yeniden yazılmaz.

---

## 7. Maç sayfası (T2) ve value yeri

İçerik (hepsi anlık görüntüden): lig, takımlar, başlama anı (`<time datetime>` UTC; yerel saat küçük bir istemci
betiğiyle, betiksiz UTC görünür), 1X2 konsensüs olasılıkları açılış/son/kapanış, açılış→kapanış hareketi (yüzde puanı),
kitap SAYISI, mühür durumu ("kapanış kaydedildi" / "bekleniyor"). **Kitap adı, kitap oranı, bağlantı yok** (B7).
Value rozeti bileşeni vardır ve `value_badge === null` iken HİÇBİR şey çizmez (boş kutu, "yakında" yazısı yok); Faz 5
şema sürümünü artırıp alanı doldurduğunda çizer. Skor yok (AK10).

---

## 8. Programatik SEO (T4)

### 8.1 URL şeması (sabit bölüt adları İngilizce, dil öneki arayüz dilini seçer)
| Sayfa | Yol |
|---|---|
| Dil ana sayfası | `/{lang}/` (`/` → `/en/`, Netlify `_redirects`; `x-default` = `/en/`) |
| Lig | `/{lang}/{league}/` |
| Takım | `/{lang}/{league}/{team}/` |
| Maç | `/{lang}/{league}/{yyyy-mm-dd}/{home}-vs-{away}/` |
| Sicil | `/{lang}/track-record/` |
| Yasal | `/{lang}/legal/{terms,privacy,cookies,responsible-gambling}/` |

Kurallar: lig slug'ı `track-record`/`legal` olamaz; takım slug'ı tarih biçiminde olamaz; aynı lig+gün+eşleşmede
çakışma derlemeyi kırmızı yapar (test). `generateStaticParams` + `dynamicParams = false`: anlık görüntüde olmayan yol
404'tür.

### 8.2 Slug'lar
`naming.normalise_team` üstüne ASCII transliterasyon (Türkçe İ/ı kuralları korunur). URL kalıcılığı: slug'lar
`config/site_slugs.yaml`'a dışa aktarımda eklenir, **hiç silinmez**; sağlayıcı ad değiştirirse eski slug `_redirects`
ile 301. (Ölçülmedi: The Odds API takım adlarının ne sıklıkla değiştiği.)

### 8.3 Diller — YER TUTUCU (AK5)
Sözlükler `web/src/i18n/{lang}.json`, tipli erişimci; kütüphane yok. Dil listesi tek yerde (`web/site.config.ts`,
`SITE_LANGS`). Her sayfa etkin bütün dillere `alternates.languages` + `x-default`; site haritası girdileri de
`alternates` taşır. Veri dilden bağımsızdır; yalnız arayüz metni çevrilir. Öneri: ilk sürüm `en` + `tr` (spec §1.2
EN birincil; TR yasal inceleme zaten gerekiyor). Makine çevirisi yayımlanmaz.

### 8.4 İndeksleme politikası (B8'in üstünde, `SITE_INDEXABLE` açıkken)
Maç sayfası en az iki gözlem turu ve `books ≥ SITE_MIN_BOOKS` olana dek `noindex`; takım sayfası defterde en az
`SITE_MIN_TEAM_MATCHES` (öneri 3) maç olana dek `noindex`; `noindex` sayfa site haritasına girmez.

### 8.5 İnce/kopya içerik riski
Faz 7 yokken maç sayfası yalnız sayısal türev taşır; binlerce benzer sayfa "ince içerik" sayılabilir. Panzehirler:
(1) §8.4 eşikleri; (2) her sayfada maça özgü türev (hareket, kitap sayısı, mühür durumu) — şablon cümlesi değil
sayı; (3) lig sayfası o ligin bütün maçlarının konsensüs hareketi dağılımı (defterden türetilir); (4) diller arası
aynı veri `hreflang` ile bağlı (kopya değil alternatif). Kalan risk: arama motorunun yargısı ölçülemez (§12.4).

### 8.6 Faz 7'nin yeri
Maç şablonunda `analysis` yuvası (bileşen + şema alanı) var, `null`dır; Faz 7 Jev doğrulama geçidini kurunca şema
sürümü artar. Yuva boşken sayfa hiçbir yer tutucu metin çizmez.

---

## 9. schema.org (T5)

JSON-LD, sayfa başına bir `<script type="application/ld+json">`, anlık görüntüden üretilir, `schema-dts` yalnız tip
olarak (çalışma zamanı bağımlılığı değil; plan kaldırabilir):
- Ana sayfa: `WebSite` + `Organization` (ad = marka yer tutucusu, AK3; `url` = alan adı yer tutucusu, AK4).
- Lig: `SportsOrganization` (ad, ülke). Takım: `SportsTeam` (ad, `memberOf` lig).
- Maç: `SportsEvent` — `name`, `startDate`, `homeTeam`/`awayTeam` (`SportsTeam`), `sport: "Soccer"`,
  `eventStatus: EventScheduled`, `organizer` lig. `location` yok (stadyum verisi bu sürümde yok); `offers`, oran,
  bahis bağlantısı YOK.
- Her sayfa: `BreadcrumbList`.
Test: oluşturucular birim testli; tarayıcı her sayfada JSON-LD'nin ayrıştığını ve `@type`ın beklenen olduğunu
sınar. Google Zengin Sonuç doğrulaması kapıda değil (ağ, §12.4).

---

## 10. 18+, sorumlu bahis, KVKK, çerez (T6) ve Türkiye riski

### 10.1 Metin taslakları — hepsi "TASLAK — avukat onayı bekler" başlığıyla (`web/content/legal/{lang}/*.md`)
- **Kullanım koşulları:** site bilgi amaçlıdır, bahis kabul etmez, bahisçiye yönlendirmez, bağlantı içermez;
  olasılıklar garanti değildir; geçmiş performans geleceği göstermez; veri kaynağı hakkında lisans iddiası yok (H4).
- **Sorumlu bahis:** 18+; bahis bağımlılığı riski; yardım kaynakları (TR: Yeşilay danışma hattı; EN: ülkeye göre) —
  **iletişim bilgileri yayından önce birincil kaynaktan doğrulanır, taslakta `[DOĞRULANACAK]` işaretli.**
- **KVKK aydınlatma / gizlilik:** site kişisel veri TOPLAMAZ (hesap, form, analitik yok); barındırıcının erişim
  kayıtları (IP) veri sorumlusu–işleyen ilişkisi ve yurt dışı aktarım (Netlify) — avukat sorusu olarak işaretli.
  Sitede oyuncu sağlık bilgisi yayımlanmaz (H2); projenin genel md. 6 sorusu HANDOFF §0.7/7'de.
- **Çerez:** yalnız zorunlu yerel depolama (18+ onayı). Analitik yok (AK12) → çerez bandı yalnız bilgi.

### 10.2 18+ kapısı
İlk ziyarette tam ekran bildirim ("18 yaşından büyüğüm" / çıkış), onay `localStorage`'da; betiksiz tarayıcıda
sayfa üstünde kalıcı 18+ şeridi. **Bu bir yaş doğrulaması DEĞİLDİR** (§12.4); içerik HTML'de durur.

### 10.3 Türkiye'de bahis içeriği riski (hukuki görüş değildir; §0.7/7'de avukata gider)
- 7258 sayılı Kanun yasa dışı bahsi düzenlemeyi, kolaylaştırmayı ve reklamını yaptırıma bağlar; erişim engeli
  kararları yaygındır. Risk: yurt dışı bahisçi adı, oranı ya da bağlantısı gösteren içerik tanıtım sayılabilir →
  B7 (kitap adı/oranı/bağlantı yok) ve "yönlendirme yok" bu yüzden.
- İddaa/Nesine verisi kullanılmaz (Nesine ToS §4.2.1, spec §10/1).
- Her yeni dil yeni bir düzenleyici çerçeve demektir (ör. Birleşik Krallık reklam kuralları, Brezilya'nın düzenlenmiş
  bahis reklamı çerçevesi) → dil listesi (AK5) hukuk incelemesine (AK13) bağlıdır.
- Erişim engeli riski alan adı ve marka kararını (AK3, AK4) da etkiler.

---

## 11. Deploy (T7) — hazır, bağlı değil

- **`web/netlify.toml`:** `[build] publish = "out"`, `command` Netlify'da derlemeyi reddeden bir komut (Netlify Git'e
  bağlanmaz; yayın yalnız CLI ile hazır dizindir); başlıklar: sıkı CSP (`default-src 'self'`, üçüncü taraf betik
  yok), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `X-Robots-Tag: noindex` (H7 kalkana dek).
- **`.github/workflows/site.yml`:** yalnız `workflow_dispatch`; `permissions: contents: read`; `concurrency`
  `site-deploy`; adımlar: checkout → `uv sync --frozen` → secret yoksa adıyla exit ("SITE_DATABASE_URL yok — yayın
  yapılmadı") → `site export` → `site verify-export` → pnpm kurulum → `next build` → çıktı tarayıcısı →
  `netlify deploy --prod --dir web/out` → canlı hash kontrolü (§6.4/2f). `schedule` YOK; pg_cron dispatch YOK
  (AK15). Test: workflow'un ortam anahtar kümesi (H5), tetik kümesi = `{workflow_dispatch}`.
- **Neden Netlify'da derleme değil (AK16):** Netlify derlerse DB kimliği Netlify'a verilmek zorunda kalır ve
  doğrulama (verify-export) Actions'ın dışında koşar.

---

## 12. Site kapısı

### 12.1 Adımlar (`verify.sh`e eklenir; her biri `step` ile adıyla PASS/FAIL)
| Adım | Komut | Ölçer |
|---|---|---|
| `site-kurulum` | `pnpm -C web install --frozen-lockfile` | Kilit dosyası ↔ `package.json`; bağımlılık yaşam döngüsü betikleri kapalı (pnpm varsayılanı; izin listesi boş) |
| `site-tip` | `pnpm -C web exec tsc --noEmit` | Tipler, fixture `satisfies Snapshot` |
| `site-lint` | `pnpm -C web exec biome ci` | Lint + biçim (tek bağımlılık) |
| `site-test` | `pnpm -C web exec vitest run` | Slug, `hreflang`, JSON-LD, biçimleyiciler, 18+ bileşeni |
| `site-derleme` | `next build` (fixture ile, `SITE_INDEXABLE` yok) | Statik üretim |
| `site-uyum` | `node web/scripts/check-out.ts` | §5.3 — sayfa ↔ anlık görüntü, H1–H7, `hreflang`, site haritası, basit erişilebilirlik |
| `pytest` (mevcut) | `tests/test_site_*.py` | Migration metin testleri, dışa aktarıcı (sahte DB), şema ↔ TS anahtar eşitliği, `site.yml` ortamı, log redaksiyonu |
| `sızıntı` (mevcut) | `leakage` işaretli site testleri | H1; `EXPECTED_MIN_LEAKAGE` ölçülerek yükseltilir |
| `site-db` (yeni) | `pytest -m sitedb` | §4.4/2 katalog + davranış; `SITE_TEST_DATABASE_URL` yoksa `SKIP: site-db (…)` adıyla |

pnpm ya da Node yoksa adımlar **FAIL** (SKIP değil): site kapının parçasıdır.

### 12.2 CI bağlantısı (`ci.yml`)
Mevcut `gate` işine: `actions/setup-node` (sürüm `web/.nvmrc`'den) + `pnpm/action-setup` (`packageManager`'dan) +
`services: postgres: supabase/postgres:17.6.x` (parola iş içinde üretilir, secret değil) ve
`SITE_TEST_DATABASE_URL`. `DATABASE_URL` yine VERİLMEZ (zincir SKIP kalır). `timeout-minutes` ölçülerek artırılır;
imajda 0003–0005'in `pg_cron`/`pg_net`/`vault` bağımlılıklarının koştuğu planın ilk görevinde ölçülür (HANDOFF §0.5
K1 inceleyicileri aynı imajda koşabildi; CI servisinde ölçülmedi).

### 12.3 Tek yazar
`verify.sh` ve `ci.yml` ortak dosyadır: yalnız B-2'nin dalga sonu birleştirme görevinde değişir (yol haritası §4).

### 12.4 Kapının ÖLÇMEDİKLERİ (ön liste — faz HANDOFF'unda tamamlanır)
1. **Gerçek veriyle sayfa ↔ defter uyuşması** yalnız `site.yml`de ölçülür; `site.yml` bağlı değil → bugün gerçek
   veride HİÇ ölçülmedi.
2. Canlı DB'de görünüm ve yetkiler (migration uygulanmadı); CI kabı Supabase'in rol/varsayılan yetki kurulumunun
   birebir kopyası değildir.
3. Üçüncü kişi zinciri baştan doğrulayamaz (§6.3); Faz 5 öncesi yayın anı kanıtı yok (§6.5).
4. H1 veriyi ve görünümleri kapsar; **elle yazılmış metne** (yasal sayfa, açıklama) holdout sayısı yazılmasını
   anlamsal olarak yakalamaz — yalnız tarih kalıplarını tarar.
5. 18+ kapısı yaş doğrulaması değildir; yasal metinlerin doğruluğu (taslak) ölçülmez.
6. SEO sonucu, indekslenme, ince içerik yargısı, Zengin Sonuç doğrulaması, Core Web Vitals.
7. Tam erişilebilirlik (axe, ekran okuyucu), görsel regresyon, tarayıcılar arası çizim.
8. Netlify'ın başlıkları gerçekten sunduğu (yalnız dosya içeriği test edilir; yayın sonrası kontrol yalnız hash).
9. Çeviri kalitesi; slug kalıcılığının sağlayıcı ad değişikliklerine dayanıklılığı.
10. The Odds API koşullarına ve TR mevzuatına uyum (AK13, AK17).
11. CSP'nin etkinliği (yalnız varlığı).

---

## 13. Dizin yapısı, sürümler, bağımlılıklar

```
web/
  package.json · pnpm-lock.yaml · .nvmrc · tsconfig.json · next.config.ts · biome.json · netlify.toml · site.config.ts
  contract/snapshot.schema.json          # Python ile ortak sözleşme
  fixtures/snapshot.fixture*.json        # sentetik
  content/legal/{lang}/*.md              # TASLAK
  scripts/check-out.ts                   # çıktı tarayıcısı
  src/app/[lang]/…                       # §8.1 yolları; sitemap.ts, robots.ts
  src/lib/{snapshot,slug,hreflang,jsonld,format}.ts · src/i18n/{lang}.json · src/components/…
src/football_edge/site/{__init__,__main__,export,verify}.py
db/migrations/0013_legacy_rls.sql · 0014_site_read.sql
.github/workflows/site.yml
tests/test_site_*.py
config/site_slugs.yaml
```
- **Node 24 LTS** (`.nvmrc` + `engines`; Node 26 LTS'e geçiş ayrı iş), **pnpm 10** (`packageManager` alanı).
- **Next.js** App Router, `output: 'export'`, `images.unoptimized: true`, `trailingSlash: true`; sürüm plan günündeki
  kararlı sürüm, kilit dosyasıyla sabit.
- **Çalışma zamanı bağımlılığı yalnız** `next`, `react`, `react-dom`. Dev: `typescript`, `@types/react`,
  `@types/node`, `vitest`, `@biomejs/biome`, (isteğe bağlı) `schema-dts`. CSS modülleri; i18n, durum yönetimi, UI
  kütüphanesi, Supabase istemcisi YOK. Bağımlılık allowlist testi (H5) bu listeyi sabitler; eklemek bilinçli commit.
- `.gitignore`: `web/node_modules/`, `web/.next/`, `web/out/`, `web/.snapshot/`.

---

## 14. Risk kademeleri (yol haritası v2 §3)

| Kademe | İş | Süreç |
|---|---|---|
| **K1** | `0014` (rol, yetki, görünümler, holdout tabanı, yer tutucu sicil) · `0013` (12a) · dışa aktarıcı + `verify-export` (zincir, yeniden türetme, CLV) · çıktı tarayıcısının H1/H5/H6 kısmı · `site.yml` secret sınırı · log redaksiyonu | TDD + görev incelemesi (mutasyonlu; yerel kapta migration koşan inceleyici) + bütün-dal incelemesi |
| **K2** | pSEO (slug, `hreflang`, site haritası, `noindex` eşikleri) · schema.org oluşturucuları · kapı entegrasyonu (`verify.sh`, `ci.yml`) · `netlify.toml` başlıkları | TDD + tek görev incelemesi |
| **K3** | Görsel şablonlar, i18n sözlükleri, yasal metin taslakları (hukuk onayı ayrıca AK13) | Controller doğrulaması |

---

## 15. Planlara bölünme (tek plana sığmaz)

- **Plan B-1 — okuma katmanı ve sözleşme (K1, İLK):** T0 CI servis kabında 0001–0012'nin koştuğunu ölç (ölçmeden
  B10 yok); T1 `snapshot.schema.json` + sentetik fixture'lar (sözleşme görevi — B-2'nin kapısı bu commit);
  T2 `0014` + metin/katalog/davranış testleri; T3 `0013` (12a) + testleri; T4 dışa aktarıcı; T5 `verify-export`
  (zincir okuyucusunun parametrelenmesi, 17a mühürüyle); T6 `site.yml` (bağlanmamış) + ortam testi + redaksiyon.
- **Plan B-2 — web yüzeyi (K2/K3; B-1 T1 birleşince paralel):** iskelet + sözlükler; maç/lig/takım/sicil/yasal
  sayfaları; slug + `hreflang` + site haritası; JSON-LD; 18+; yasal taslaklar; çıktı tarayıcısı; `netlify.toml`;
  **son görev:** `verify.sh` + `ci.yml` entegrasyonu (tek yazar) ve kapı süresi ölçümü.
- Aynı anda en çok 4 implementer; B-1'in K1 görevleri kendi worktree'lerinde, `--no-ff` birleştirme.

---

## 16. Açık kararlar (HANDOFF §0.7'ye eklenecek)

| No | Karar | Seçenekler | Öneri | Neyi bloklar |
|---|---|---|---|---|
| AK1 | Mimari yaklaşım | A · B · C (§3) | **A** | Her iki planın yazımı |
| AK2 | Bu spec'in onayı | onay · düzeltme | — | `writing-plans` |
| AK3 | Marka adı (§0.7/1) | kullanıcı | — (yer tutucu `SITE_NAME`) | `Organization` JSON-LD, yasal metinler, alan adı, deploy |
| AK4 | Alan adı + kayıt yeri + Netlify hesabı (§0.7/2) | Cloudflare Registrar · Namecheap · Netlify | Kullanıcı; kayıt yeri Netlify DNS'e bağlanabilen herhangi biri | Kanonik URL, site haritası, `hreflang` mutlak adresleri (yer tutucu `https://example.invalid`), deploy |
| AK5 | İlk sürüm site dilleri | `en` · `en`+`tr` · spec §1.2'nin yedisi | **`en` + `tr`** | Sözlükler, yasal metin dilleri, hukuk kapsamı |
| AK6 | Halka açık okuma katmanı (§0.7/3) | §4.3 listesi · daraltılmış · genişletilmiş | **§4.3 listesi** | `0014`ün uygulanması |
| AK7 | Eski tablolara RLS + TRUNCATE (12a) uygulaması | şimdi (siteden bağımsız) · siteyle · hiç | **Şimdi, ROLLBACK'li provadan sonra** | B mimarisinin ön koşulu; A için hijyen |
| AK8 | Maç sayfasında oran biçimi | (a) vig'siz olasılık · (b) + adil oran · (c) kitap adı ve oranları | **(a)** | Maç şablonu |
| AK9 | Kamu doğrulamasının derinliği | (a) çıpalar + baş + anlık görüntü hash'i · (b) + tahmin başına kanıt satırları (Faz 5) · (c) tam defter dökümü | **Şimdi (a), Faz 5'te (b); (c) AK13+AK17 sonrası** | Sicil "nasıl doğrulanır" metni |
| AK10 | Skor kaynağı | yok · The Odds API `scores` (kredi) · football-data (yazılı izin yok → hayır) | **İlk sürümde skor yok** (CLV sicili skor gerektirmez) | Sonuç/ROI gösterimi |
| AK11 | Gölge seri (`model_predictions`) sitede mi | hayır · maç bitince toplu özet | **Hayır** (H3; model piyasayı geçmedi) | — (gelecek şema sürümü) |
| AK12 | Analitik | yok · Netlify sunucu tarafı · üçüncü taraf | **Yok** | Çerez metni |
| AK13 | Hukuk metinleri ve TR riski (§0.7/7) | avukat onayı | — | İndekslemeye açma, TR dili yayını |
| AK14 | İndekslemeye açma (`SITE_INDEXABLE`) | ilk yayından · onaylardan sonra | **AK3, AK4, AK13'ten sonra** | Arama trafiği |
| AK15 | Yeniden derleme tetiği (bağlanınca) | elle · günlük snapshot sonrası · + saatte en çok bir mühür sonrası (pg_cron → `ops.dispatch_workflow('site.yml')`) | **Günlük + saatlik mühür sonrası** | `site.yml`in otomatiği |
| AK16 | Netlify yayın yöntemi | Actions'tan hazır dizin (CLI) · Netlify Git derlemesi | **CLI** | `site.yml` |
| AK17 | The Odds API koşullarının türetilmiş olasılık yayımı açısından okunması | asistan salt okuma araştırması → karar kullanıcıda | **Plan B-2'den önce oku** | AK8'in kesinleşmesi, AK9 (c) |
| AK18 | `site_reader` parolası + GitHub secret'ları (`SITE_DATABASE_URL`, `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`) | kullanıcı ekler | — | İlk gerçek dışa aktarım ve deploy |

---

## 17. Öz-inceleme (2026-09-23)

- **Yer tutucu dışında TBD yok:** açık kalanların hepsi §16'da satır (marka, alan adı, diller, okuma katmanı, hukuk,
  secret'lar) ya da plana bırakılan uygulama ayrıntısı (JSON Schema doğrulayıcı seçimi, migration numarası, CI
  süresi) olarak adıyla işaretli.
- **İç çelişki taraması:** "sitede value/model yok" (H3) ↔ maç sayfası yalnız piyasa (§7) ↔ şema `const null` (B6)
  tutarlı; "Node DB'ye bağlanmaz" (H5) ↔ B2 ↔ §13 bağımlılıkları tutarlı; `sealed_at` görünümden bilinçli dışarıda,
  mühür durumu defter kesiminden (§4.3, §5.2) — belirlenimcilik (§6.4c) buna dayanır; holdout tabanı üç yerde aynı
  (B4, §4.3, H1) ve tek kaynaklı.
- **Kapsam:** tek plana sığmıyor → §15'te iki plan; ilk B-1 (sözleşme görevi B-2'nin başlangıç kapısı).
- **Bilinen varsayımlar (ölçülmedi):** CI servis kabında 0003–0005'in koşması; Netlify fiyat/limitleri; takım adı
  değişim sıklığı; boru hattının tablo sahibi olarak bağlandığı (0006/0007 yorumları öyle diyor, 12a uygulanmadan
  canlıda okunur).
