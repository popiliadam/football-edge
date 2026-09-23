# Faz 6 İz B — halka açık web sitesi, okuma katmanı, sicil (tasarım)

**Tarih:** 2026-09-23 · **Durum:** TASLAK, kullanıcı onayı bekler (HANDOFF §0.6/5). Düzeltme turu 1 işlendi
(bağımsız inceleme `.superpowers/sdd/2026-09-23-oturum9-dalga-a/izb-spec-review.md`: C1–C2, I1–I13, Minor'lar §18).
Bu belgedeki her karar **Öneri**dir; onaylananlar R-numarası alır. Numaralar geçici: tasarım önerileri `B1…`,
açık kararlar `AK1…`.
**Sonraki adım:** onaydan sonra `superpowers:writing-plans` (iki plan, §15) + bağımsız plan incelemesi.
**Girdi:** ana tasarım `2026-09-19-football-edge-design.md` §1, §3.2, §6, §9, §10 · yol haritası
`2026-09-19-faz-1-7-yol-haritasi.md` Faz 6–7 · `2026-09-21-yol-haritasi-v2-paralel-izler.md` §2 İz B, §3, §4 ·
`docs/HANDOFF.md` §0.5–§0.7 · `docs/phases/03-baz-model/HANDOFF.md` §1 · `db/migrations/0001–0012` + Dalga A Task 6
(`0013_api_roles_lockdown.sql`) · `docs/reports/2026-09-23-kaynak-kosullari.md`, `2026-09-23-ek-kaynaklar.md` ·
`verify.sh`, `.github/workflows/ci.yml`, `seal.yml`, `tests/test_workflows.py`.

> **R163 notu.** Faz 4 tasarımı R163 "İz B Faz 4'le paralel başlamaz" diyordu (gerekçe: dört implementer sınırı,
> Netlify yok). Kullanıcının 2026-09-23 kararı (HANDOFF §0.6) İz B'yi oturum 9 Dalga B'ye aldı: Faz 4 Plan 2 en erken
> 2026-10-07'de başlıyor, arada implementer kapasitesi boş. Dört implementer sınırı aynen geçerli.

> **Yol haritasından bilinçli sapmalar (adıyla).** (1) Faz 6 çıktısı "kamuya açık CLV/**ROI** sicili" diyor; ilk
> sürümde skor kaynağı olmadığı için ROI yok, yalnız CLV (AK10). (2) v2 §2 "Faz 7'nin T1–T2'si Faz 6 iskeletiyle"
> diyor; HANDOFF §0.6/5–6 İz B'yi Faz 7'siz tanımlıyor — bu spec Faz 7'yi kapsam dışı bırakır, yalnız yerini açar (§8.6).

---

## 0. Önerilen tasarım kararları

| No | Öneri | Gerekçe | Yanlışsa bedeli |
|---|---|---|---|
| B1 | **Mimari A:** derleme anında salt okuma rolüyle DB'den anlık görüntü → statik site → Netlify'a hazır dizin yüklenir (§3) | Tarayıcıya ve Netlify'a DB anahtarı gitmez; SEO için tam HTML; sayfa ↔ veri uyuşması derleme anında ölçülebilir | Tazelik derleme sıklığına bağlı (dakikalar–saat) |
| B2 | **DB'ye yalnız Python dokunur.** Dışa aktarım `src/football_edge/site/` (Python) → tek JSON anlık görüntü; Next.js yalnız bu JSON'u okur, Node tarafında DB sürücüsü yok | Oran/olasılık/CLV hesabı modelle AYNI kodla yapılır (spec §6.3 "iki yol yazılmaz"); K1 kodu mevcut kapının (ruff, mypy, pytest) altında kalır | İki dil arasında sözleşme dosyası (§5) bakımı |
| B3 | **Üç şema, bir rol:** `site` (her kolonu anlık görüntüye BİREBİR girebilir = yayımlanabilir) · `site_input` (hesap girdisi, yayımlanmaz: kitap bazında fiyat) · `site_audit` (yalnız zincir doğrulaması, yayımlanmaz). Rol `site_reader` yalnız bu üçünü okur, hiçbir tabloya yetkisi yoktur | "Siteye ne açık?" sorusunun cevabı tek şemadır (`site`); hesap girdisi ile yayımlanabilir veri karışmaz | Görünüm sahibinin yetkisiyle okunur — görünüm tanımı güvenlik sınırıdır, K1 |
| B4 | **Holdout tabanı:** her maç satırı taşıyan görünüm `commence_time >= site.public_floor()` süzer; taban `HOLDOUT_END + 1 gün` = 2026-07-02 00:00 UTC ve Python sabitinden türetildiği testle kanıtlanır | Holdout üyeliği football-data `Date`iyle, yani **Londra tarihiyle** belirlenir (R102); holdout Londra'da 2026-07-01 00:00'da (UTC 06-30 23:00) biter. Bir günlük pay saat dilimi ve kaynak tarihi belirsizliğini kapatır; canlı defter 2026-09-19'da başladığı için bedeli sıfır | — |
| B5 | **Sicil yer tutucu görünümü:** `site.record` bugün `WHERE false` ile tipli ve 0 satırlı; kolon listesi Python sabitiyle katalogdan sınanır; gövdenin `where false` kaldığını metin testi Faz 5 kapısına kadar zorlar | Postgres `CREATE OR REPLACE VIEW` ad/tip/sıra değişikliğini reddeder ama listenin SONUNA kolon eklemeye izin verir — büyümeye karşı koruma DB'den değil testten gelir | — |
| B6 | **Anlık görüntü şeması v1'de `value_badge: null`, `analysis: null`, model olasılığı alanı YOK** (JSON Schema `const: null`, `additionalProperties: false`) | "Sitede value önerisi yok" ve "Faz 7 doğrulama geçidi olmadan metin yok" kodla zorlanır; şema sürümü artmadan dolamaz | — |
| B7 | **Maç sayfası yalnız vig'i temizlenmiş piyasa konsensüs olasılığını gösterir** — kitap adı, kitap bazında oran, bağlantı yok (AK8) | Kaynak politikası §3.2/4, TR'de bahis reklamı riski (§10.3), The Odds API koşulları okunmadı (AK17) | İçerik incelir (§8.5 panzehirleri) |
| B8 | **İlk sürümlerde her sayfa `noindex`**; indekslemeye açma ayrı bayrak (`SITE_INDEXABLE`) ve AK14 onayına bağlı; `X-Robots-Tag` ve CSP derlemenin ürettiği `out/_headers`ten TEK kaynaktan gelir | Hukuk metinleri onaysızken kazara yayın bile arama motoruna girmesin; iki kaynak ayrışmasın | — |
| B9 | **Deploy hazır, bağlı değil:** `web/netlify.toml` + `.github/workflows/site.yml` yalnız `workflow_dispatch`, secret yoksa adıyla kırmızı; zamanlama/pg_cron tetiği YOK | HANDOFF §0.6/6 | — |
| B10 | **Site kapısı `verify.sh`in adımıdır** (tek kapı); DB davranış testleri CI'da geçici `supabase/postgres` servis kabında koşar; `CI=true` iken test veritabanı yoksa adım **FAIL** | "Kapı = CI'ın koştuğu adımlar"; görünüm testleri gerçek Postgres ister; SKIP'in CI'da sessizce yeşil olması Vaka 1 desenidir | CI süresi uzar (ölçülecek) |
| B11 | **Eski tabloların API açığı (DEFERRED 12a) Dalga A Task 6 `0013_api_roles_lockdown.sql` ile kapanır** (RLS, `anon`/`authenticated` yetkileri ve varsayılan yetkileri geri alma, append-only üçlüde TRUNCATE bekçisi, `forbid_ledger_mutation` `search_path`); canlıya bu oturumda controller uygular. Sitenin migration'ı **0014** (gerekirse 0015) | Tek açık tek migration'da kapanır; site onu varsayar, tekrar etmez | — |
| B12 | **Dışa aktarım tek `REPEATABLE READ READ ONLY` işlemidir; zinciri GENESIS'ten ve bütün çıpalara karşı doğrular;** belirlenimcilik `content_sha256` (zaman damgası ve git SHA'sı hariç gövde, `ledger._canonical`) ile, ayrı alt süreçte farklı `PYTHONHASHSEED`le yapılan ikinci türetimle ölçülür; yayımlanan dosyanın tamamı ayrıca `snapshot.sha256` taşır | `matches.commence_time` her snapshot turunda UPDATE edilir (`db.upsert_matches`); defter kesimi `matches`i dondurmaz — tek işlem dondurur | Uzun işlem (saniyeler) — sorun değil |
| B13 | **İki plan:** B-1 okuma katmanı + dışa aktarım + K1 testleri + onların CI adımı (İLK); B-2 web yüzeyi + Node kapı adımları + deploy hazırlığı (B-1'in sözleşme görevinden sonra paralel; `verify.sh`/`ci.yml`e B-1 birleştikten SONRA dokunur) (§15) | Tek plan K1 ile K3'ü aynı inceleme ağırlığına zorlar; K1 testleri B-2'yi beklememeli | — |

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
  §1). Faz 5'in CLV kapısı geçilene kadar sitede öneri yayımlanmaz.
- Faz 7 içerik hattı (Sonnet metni, Jev doğrulama geçidi). Yeri hazırdır (§8.6), içerik yoktur.
- Haber, sakatlık, kadro, hakem, hava, stadyum verisi — sitede HİÇBİR kaynak metni ya da oyuncu düzeyi bilgi yok
  (§2 H2; sakatlık = sağlık verisi, KVKK md. 6 — HANDOFF §0.7/7).
- football-data.co.uk'tan türetilmiş her şey (Elo, verimlilik sıralaması, tarihsel form, skor): yazılı izin yok
  (spec §10/2) ve holdout o kaynağın içinde yaşar.
- Canlıya migration uygulamak, Netlify'a yayın, alan adı, secret eklemek (HANDOFF §0.7).

**Bugünkü gerçek (tasarımın dayandığı durum):**
- Defter (`odds_snapshots`) 2026-09-19'dan beri hash zinciriyle yazılıyor. `seal.yml` her mühür turunda zincir başı
  değiştiyse `ledger/head-<UTC günü>.txt`yi yeniden yazıp public depoya commit'liyor (15 dakikalık turlar; günde
  bir dosya, gün içinde birden çok commit). Zincir yalnız oran defterini kapsar; `model_predictions` ve diğer
  tablolar append-only ama zincirsiz.
- **Defterde yayınlanmış tahmin YOK.** `model_predictions` gölge satırlarıdır, "YAYIN YOK" (0009).
- Gölge raporu sonucu football-data'dan alıyor (`live/report.py`); sitenin kendi hakkıyla gösterebileceği bir skor
  kaynağı bugün yok (AK10).
- `matches.commence_time` her snapshot turunda UPSERT'le güncellenir (erteleme, saat düzeltmesi).
- Depo ve Actions logları public (RUNBOOK §3.8): derleme logu yayın kanalıdır.
- Bütün boru hattı tablo sahibi `postgres` olarak bağlanır (controller ölçümü, Dalga A Task 6).

---

## 2. Sert kurallar ve nasıl zorlandıkları

Her kural kodda bir bekçiye bağlanır; prose kural yazılmaz. "Kapının ölçmediği" §12.4'te.

| Kural | Zorlayan (hepsi kapıda) |
|---|---|
| **H1 — Holdout verisi sitede ASLA görünmez.** Holdout verisi = maç tarihi `[2025-07-01, 2026-07-01)` (Londra) olan her satır VE ondan türetilmiş her sayı (Faz 3 raporunun C1–C6 sayıları dahil). Sitede holdout sonucu en çok nitel bir cümleyle anılır | (a) **ilişki** bağımlılık kapanışı: `site`/`site_input`/`site_audit` görünümlerinin `pg_depend` kapanışındaki **temel tablolar** (`relkind = 'r'`) = {`leagues`, `matches`, `odds_snapshots`} (ara `site.*` görünümleri kapanışta yer alır, eşitliğe girmez); **fonksiyon** kapanışı ⊆ {`site.public_floor`} — sabitlenmiş (pinned) `pg_catalog` nesneleri `pg_depend`e yazılmadığı için bu test fiilen sabitlenmemiş fonksiyonları sınar; `site.public_floor()` gövdesinde tablo referansı yok (§4.4) · (b) davranış testi: holdout ve sınır tohumları (§4.4/2) · (c) `site.public_floor()` ↔ `HOLDOUT_END + 1 gün` eşitlik testi · (d) dışa aktarıcı her maç için `commence_time >= floor` iddia eder, aksi hâlde adıyla exit · (e) `verify-snapshot` (DB'siz, Python) anlık görüntüde tabandan eski tarih bulursa kırmızı · (f) **import bekçisi, GEÇİŞLİ kapanış üzerinde:** `football_edge.site`in geçişli import kapanışı `history.{store,lock,holdout,football_data,sync,catalog}`, `backtest.*` ve `live.context` İÇEREMEZ. Bekçi **yasak listeyle** kodlanır (izin listesiyle değil: boş `football_edge.history` paket `__init__`i kapanışta durur ve izin listesi onu yakalardı); `history.types` `market.devig` ve `market.consensus` üzerinden bilinçli olarak kapanıştadır. Bugünkü kapanış (ölçüldü, 2 yeniden inceleme) yasak modül içermiyor. Bunun için konsensüs yaprak modüle taşınır (§4.3, `market/consensus.py`); `live.context.pre_prices` onu çağırır, `site` `live.context`i import etmez · (g) testler `leakage` işaretini taşır, `EXPECTED_MIN_LEAKAGE` ölçülerek yükseltilir |
| **H2 — Ham kaynak metni ve oyuncu düzeyi bilgi yok** (spec §3.2/4) | (a) aynı ilişki allowlist'i · (b) anlık görüntü şeması `additionalProperties: false`; serbest metin alanı yalnız takım adı, lig adı, ülke — tip ve uzunluk sınırlı · (c) `verify-snapshot` `http`, `<`, `>` taşıyan veri dizesini reddeder |
| **H3 — Value önerisi ve model olasılığı yok** (Faz 5'e kadar) | (a) şema `value_badge: const null`; model alanı şemada yok · (b) `model_predictions` ilişki allowlist'inde yok · (c) `site.record` gövdesinin `where false` kaldığını sınayan metin testi (B5) · (d) `site.record` kolon listesi = Python sabit tuple'ı (katalogdan) |
| **H4 — Lisans iddiası yok** (spec §3.2/5) | Metin tarayıcısı `web/content/**` ve derlenmiş HTML'de büyük/küçük harf ve aksan katlanmış kalıpları kırmızı yapar: "lisanslı", "licensed", "resmi/resmî veri", "official data", "official partner", "resmi/resmî ortak", "authorized", "yetkili veri". Olumsuz cümle (ör. "lisans iddiasında bulunmuyoruz") yalnız derlemeden sağ çıkan `data-fe-allow="license-negation"` öznitelikli öğede geçer (yasal metinler düz TSX olduğu için öznitelik derlemeden aynen geçer, §10.1); işaret sayısı kaynakta ve derlenmiş HTML'de ayrı ayrı sınanır ve eşittir |
| **H5 — Tarayıcıya ve Netlify'a hiçbir anahtar gitmez; Node DB'ye bağlanmaz** | (a) `web/package.json` bağımlılık allowlist testi (DB sürücüsü, `@supabase/*` yok) · (b) `verify-snapshot` ve çıktı tarayıcısı `postgres://`, `postgresql://`, `service_role`, `eyJ` (JWT öneki), `SUPABASE_`, `NETLIFY_AUTH` kalıplarını kırmızı yapar · (c) `scripts/check_secrets.sh` regex'i `NETLIFY_AUTH_TOKEN`ı da kapsayacak biçimde genişler; testlerde bu adlar parçalardan kurulur (bellek notu `full-gate-every-commit`) · (d) `site.yml` testi **adım düzeyinde**: `SITE_DATABASE_URL` yalnız dışa aktarım adımının `env`inde, `NETLIFY_AUTH_TOKEN`/`NETLIFY_SITE_ID` yalnız deploy adımında; pnpm/next/tarayıcı adımları secret'sız; iş düzeyinde `env` secret taşımaz; `DATABASE_URL`, `ODDS_API_KEY`, `TYPESAFE_API_KEY` hiçbir adımda yok; checkout `persist-credentials: false` (`test_workflows.py` kuralı) |
| **H6 — Sicil yalnız defterden türetilir, elle yazılmaz; TS sayı HESAPLAMAZ** | (a) §6.4 uyuşma kontrolleri · (b) anlık görüntü sayfanın gösterdiği HER türevi taşır (§5.2); TS yalnız yerel ayraç ve birim ekler (§5.4) · (c) çıktı tarayıcısı hem `data-fe-*` özniteliğinin anlık görüntüye birebir eşitliğini hem görünen METNİN `format(değer)`e eşitliğini sınar |
| **H7 — Onaysız indeksleme yok** | `SITE_INDEXABLE` yoksa her sayfa `<meta name="robots" content="noindex">` + derlemenin ürettiği `out/_headers`te `X-Robots-Tag: noindex`; `robots.txt` bu dönemde `Disallow` TAŞIMAZ (taşırsa tarayıcı `noindex`i göremez); tarayıcı bayrak kapalıyken bir tane indekslenebilir sayfa görürse kırmızı; bayrak açık varyant da kapıda derlenir (§12.1) |

---

## 3. Mimari yaklaşımlar

### 3.1 Seçenekler

**(A) Derleme anında anlık görüntü, statik yayın.** Actions işi `site_reader` rolüyle bağlanır, tek bir salt okuma
işleminde `site`/`site_input` görünümlerini okur, zinciri `site_audit` üzerinden doğrular, tek bir JSON anlık görüntü
üretir; `next build` (`output: 'export'`) bu JSON'dan statik HTML üretir; Netlify CLI hazır dizini yükler. Netlify
derleme yapmaz, DB kimliği tutmaz; tarayıcı yalnız HTML/CSS/JS ve statik JSON görür.

**(B) Supabase anon anahtarı + RLS'li salt okuma görünümleri, istemci/ISR.** Görünümler PostgREST'e açılır,
tarayıcı ya da Netlify fonksiyonu anon anahtarıyla okur; SEO için sunucu tarafı çizim/ISR (Netlify'da Next çalışma
zamanı ve fonksiyonlar).

**(C) Karma.** A'nın statik sayfaları + canlı parçalar (ör. son oran turu) için B'nin anon okuması.

### 3.2 Karşılaştırma

| Ölçüt | A | B | C |
|---|---|---|---|
| Anahtar sızması | DB kimliği yalnız Actions secret'ında, yalnız dışa aktarım adımında; tarayıcıda yok | Anon anahtarı tasarım gereği public; tek güvence RLS/yetki doğruluğu | B ile aynı |
| Eski tabloların API açığı (12a) | Etkilenmez: `site_reader` tabloya dokunmaz; 0013 hijyen olarak kapatır | **Ön koşul:** 0013 canlıda uygulanıp advisors ile doğrulanmadan anon anahtarı yayımlanamaz | B ile aynı |
| Append-only defter | Yazma yolu yok çünkü **yetki yok**; `default_transaction_read_only` yalnız kaza önleyici | Anon'a yazma yetkisi kalırsa INSERT tetikleyiciye takılmaz (tetikleyici UPDATE/DELETE/TRUNCATE'i durdurur) — 0013 bunu geri alır | B ile aynı |
| Veri yüzeyi | Yalnız anlık görüntüdeki alanlar; kazıyıcı en çok sitenin kendisini alır | PostgREST süzme/sıralama: görünümün tamamı sorgulanabilir; hız sınırı bizde | Kısmen B |
| Supabase tuzağı | Görünüm sahibi ↔ RLS etkileşimi (§4.2) katalog testiyle | Görünümler varsayılan olarak sahibinin yetkisiyle koşar; `security_invoker` unutulursa RLS atlanır | B ile aynı |
| Public loglar | Dışa aktarım logu yalnız sayı ve hash basar (test edilir) | Log riski düşük; istemci ağ trafiği herkese açık | — |
| Tazelik | Derleme sıklığı (öneri: günlük tur + saatte en çok bir mühür sonrası, AK15) | Saniyeler | Karma |
| SEO | Tam statik HTML, en hızlı TTFB | ISR/SSR gerekir; istemci çizimi arama motoruna zayıf | İyi |
| Maliyet | Actions dakikası (public depo) + Netlify statik barındırma; sunucu fonksiyonu yok | Netlify fonksiyon çağrıları + Supabase API trafiği (ziyaretçi başına) | İkisi |
| Sayfa ↔ defter uyuşması | **Derleme anında ölçülebilir:** yayımlanan her bayt doğrulanmış anlık görüntüden gelir, hash'i yayımlanır | Her istekte farklı veri; "bu sayfa defterle uyuştu" iddiası anlık kanıtlanamaz | Statik kısım için A kadar |
| Bağımlılık | `next`, `react`, `react-dom` + dev araçları | + Supabase istemcisi, Netlify Next çalışma zamanı | En geniş |

### 3.3 Öneri: A (B1)

Gerekçe sırasıyla: (1) **şeffaflık iddiası ölçülebilir kalır** — site bir anlık görüntünün çizimidir, anlık görüntü
defterle aynı işlemde karşılaştırılır ve hash'i yayımlanır (dosya AK21'le açılana dek bu kamu için taahhüttür); B'de "gösterilen = defter" iddiasını kanıtlayan bir an
yoktur. (2) **Sızıntı yüzeyi en küçük** — anahtar tarayıcıya gitmez. (3) **Maç öncesi ürün** (spec §1.3, in-play
yok): dakikalık tazelik gerekmez. (4) En az bağımlılık, sunucu yok. Bedel: tazelik derleme sıklığıdır; mühür sonrası
tetik (AK15) kapanışın sitede görünme gecikmesini ≤ 1 saat tutar. C'nin canlı parçası ihtiyaç ölçülürse statik
JSON'la A içinde çözülür; anon anahtarı gerekmez.

---

## 4. Okuma katmanı sözleşmesi

### 4.1 Migration (YAZILIR, canlıya UYGULANMAZ)

- **0013 (Dalga A Task 6, bu spec'in işi değil):** eski altı tabloda RLS (FORCE yok), `anon`/`authenticated`
  yetkilerinin ve varsayılan yetkilerin geri alınması, append-only üçlüde `before truncate`, `forbid_ledger_mutation`
  `search_path=''` + `tg_table_name`. DEFERRED 12a bununla kapanır. Site bunu varsayar.
- **`0014_site_read.sql`:** şemalar, rol, görünümler, yer tutucu sicil (aşağıda). Tek dosyaya sığmayan bir parça
  çıkarsa (ör. rol ile görünümler ayrı uygulanmak istenirse) 0015; plan karar verir.

### 4.2 Rol, yetki ve görünüm sahipliği

- `create role site_reader nologin noinherit` — idempotent: `DO` bloğu `pg_roles`ta rol yoksa yaratır (rol küme
  düzeyindedir; test oturumları ve şablon kopyaları aynı kümeyi paylaşır, §4.4/4). **Parola ve `LOGIN` migration'da YOK** —
  onaydan sonra RUNBOOK adımıyla verilir: parola kullanıcı tarafından istemci tarafı SCRAM ile girilir (`psql`
  `\password site_reader` ya da Supabase paneli); `ALTER ROLE … PASSWORD '…'` SQL editöründe ya da `execute_sql` ile
  YAZILMAZ (deyim loglarına düz metin düşebilir). Asistan parolayı görmez ve girmez (AK18).
- İki ayrı deyim: `alter role site_reader set default_transaction_read_only = on;` ve
  `alter role site_reader set statement_timeout = '30s';`. İkisi de **kaza önleyicidir, güvenlik sınırı değildir**
  (kullanıcı oturumda kapatabilir). Sınır: `site_reader`in hiçbir tabloda yazma ya da okuma yetkisi yoktur.
- `revoke all on schema site, site_input, site_audit from public`; `grant usage` ve `grant select on all tables in
  schema …` yalnız `site_reader`'a. `grant execute on function site.public_floor() to site_reader` açıkça yazılır ve
  **yük taşır:** görünümdeki fonksiyon çağrısının EXECUTE yetkisi sorgulayana göre denetlenir, ve 0013'ün genel
  `alter default privileges for role postgres revoke execute on functions from public` satırı 0014'te yaratılan
  fonksiyonun PUBLIC EXECUTE'unu baştan kaldırır — bu satır olmadan taban süzen her görünüm `site_reader` için
  yetki hatası verir (§4.4/2'nin "`site_reader` olarak > 0 satır" testi eksikliği yakalar). Başka hiçbir fonksiyona
  yeni yetki verilmez. `anon`, `authenticated`, `service_role` bu şemalara hiçbir yetki almaz.
- Üç şema da Supabase'in API'ye açık şemalarına (`public`, `graphql_public`) EKLENMEZ; uygulama anında advisors okunur.
- **Görünüm sahipliği ↔ 0013 RLS etkileşimi (açıkça):** 0013'ten sonra `leagues`, `matches`, `odds_snapshots`
  RLS'li ve politikasızdır (FORCE yok). Bir görünüm, sahibinin yetkisiyle ve sahibine uygulanan RLS ile okunur:
  - görünüm sahibi **tablo sahibi** (`postgres`) ise sahip RLS'i atlar, görünüm satırları döner — istenen durum;
  - görünüm sahibi tablo sahibi DEĞİLSE (migration başka rolle uygulandı, ya da biri `alter view … owner to`
    yaptı) RLS politikasız olduğu için görünüm **hata vermeden 0 satır** döner; site "maç yok" diye yayımlanır;
  - görünüm `security_invoker = true` taşırsa `site_reader`in kendisine RLS uygulanır ve yine 0 satır.
  Üç bekçi: (1) katalog testi: her `site`/`site_input`/`site_audit` görünümünün `relowner`ı = temel tabloların
  `relowner`ı, `reloptions` `security_invoker=true` TAŞIMAZ; (2) davranış testi: `site_reader` olarak tohumlanmış
  maçlar > 0 satır döner — 0 satır da kırmızıdır; (3) canlıda asıl bekçi DB DIŞI kanıttır: yanlış sahiplikte
  `site.ledger_head` da RLS'li `odds_snapshots`i okur ve `rows = 0` döner, yani "defterde satır var ama maç yok"
  koşulu DB içinden görülemez. Dışa aktarıcı bu yüzden depodaki çıpaya bakar: `anchor.rows > 0` iken
  `site.ledger_head.rows = 0` ya da maç kümesi boşsa adıyla exit; aynı durumu zincir doğrulamasının çıpa kontrolü de
  ("çıpanın işaret ettiği satır defterde yok") yakalar.
- **Süzen görünümler `with (security_barrier)`** kurulur (taban süzgecinden önce satırı gören sızdıran fonksiyon
  saldırısına karşı — `PUBLIC`in varsayılan `TEMP` yetkisiyle `pg_temp` fonksiyonu yazılabilir); katalog testi
  `reloptions`ta `security_barrier=true` arar.

### 4.3 Görünümler

`site` şemasındaki her kolon anlık görüntüye birebir girebilir (= yayımlanabilir); eklenen her kolon AK6 onayı ister.
`site_input` ve `site_audit` kolonları yayımlanmaz. `verify-snapshot` bunu **açık bir yasak anahtar kümesiyle**
sınar: `(site_input ∪ site_audit kolonları) − (site kolonları ∪ şemanın bildirdiği anahtarlar)`; bugün
`{bookmaker, book_key, ledger_id, point, price, bookmaker_last_update, prev_hash, row_hash, is_closing}`. Küme
katalogdan türetilir, testte boş olmadığı da iddia edilir; anlık görüntünün herhangi bir derinliğinde bu adlardan biri
anahtar olarak geçerse kırmızı. (`additionalProperties: false` bilinmeyen anahtarı zaten durdurur; izinli bir
anahtarın altına kitap fiyatı konmasını ise ancak §4.4/3'ün elle hesaplanmış beklenen değerleri yakalar.)

| Görünüm | Kolonlar | Kaynak ve süzgeç |
|---|---|---|
| `site.public_floor()` | `timestamptz` döner: `2026-07-02 00:00:00+00` | `IMMUTABLE`, `BEGIN ATOMIC` SQL fonksiyonu, sabit döner; gövdede tablo yok; tek yer |
| `site.leagues` | `id`, `name`, `country` | `leagues where active` (taban süzgeci yok — lig satırı tarih taşımaz) |
| `site.matches` | `id`, `league_id`, `commence_time`, `home_team`, `away_team` | `matches` ⋈ `site.leagues` (pasif ligin maçı düşer) `where commence_time >= site.public_floor()`; `security_barrier`. `sealed_at` alınmaz (UPDATE edilir; mühür durumu defter kesiminden türetilir). **`commence_time` de değişkendir** (UPSERT) — belirlenimcilik B12'nin tek işlemine dayanır |
| `site.ledger_head` | `rows`, `last_id`, `head` | `count(*)`, `max(id)`, son satırın `row_hash`i (bütün defter; süzgeç yok — tarih kolonu taşımaz) |
| `site.record` (B5) | `publication_id bigint`, `match_id text`, `market text`, `outcome text`, `published_at timestamptz`, `published_price numeric`, `publication_ledger_id bigint`, `closing_fair_price numeric`, `clv double precision`, `publication_hash text` | Bugün `select … where false` (0 satır, tipli). Faz 5 `publications` tablosuna aynı kolonlarla bağlar |
| `site_input.h2h_quotes` | `ledger_id`, `match_id`, `observed_at`, `is_closing`, `outcome`, `price`, `book_key` | `odds_snapshots` ⋈ `site.matches`, `market = 'h2h'`; `security_barrier`. `book_key` = tur içinde `dense_rank() over (partition by match_id, observed_at order by bookmaker)`: kitap adı taşımaz; kitap kümesi turlar arasında aynı kaldıkça aynı kitap aynı anahtarı alır (kısmen izlenebilir) — yayımlanmadığı için sorun değildir. `outcome` takım adı ya da `Draw`dır (`pre_prices` eşlemesi) |
| `site_audit.ledger_rows` | `id` + `collect._LEDGER_COLUMNS`in kolonları (`match_id, observed_at, bookmaker, market, outcome, point, price, bookmaker_last_update, is_closing, prev_hash, row_hash`) | Bütün `odds_snapshots`; yalnız zincir doğrulaması için. **Bilinçli olarak tabansızdır:** zincir GENESIS'ten ancak bütün satırlarla hash'lenir; holdout tarihli satırlar (bugün yok — defter 2026-09-19'da başladı) yalnız hash'lenir, türetime ve girdi dökümüne girmez. `id` hash'i bozmaz (`ledger.payload_of` onu ayıklar). Metin testi kolon kümesini `{id} ∪ _LEDGER_COLUMNS`ten türetir; `_LEDGER_COLUMNS` bugün bir SQL METNİDİR (`SELECT … FROM odds_snapshots`), kolon tuple'ı değildir — tuple'a ayrılması §6.4/3a'nın parametreleme refactor'uyla AYNI görevde yapılır |

**Konsensüs tanımı tek:** "turun üç sonucu tam kitaplarının ortalaması" (`live/context.pre_prices`). `pre_prices` tam
kitap SAYISINI döndürmüyor ve turu "`decided` anında ya da öncesindeki son tur" diye seçiyor; site açılış/son/kapanış
turlarını ve kitap sayısını istiyor. Plan bir K1 refactor'u yazar: tur-seçimsiz fonksiyon (tur → üç sonuç
ortalamaları + tam kitap sayısı) **yaprak modül** `football_edge/market/consensus.py`ye taşınır. Bugün konsensüs
`pre_prices` gövdesinde satır içidir (`_full_books` diye bir ad kodda yok). Fonksiyonun girdi tipi `Quote` ve
ihtiyaç duyduğu sabitler (`LIVE_H2H`, `LIVE_DRAW`) de `consensus.py`ye taşınır ve `live.context`ten yeniden dışa
verilir (`live/store.py` ve testlerin importları değişmez); dışa aktarıcı `Quote.bookmaker = book_key` ile çağırır.
`consensus.py` yalnız ortalamaları ve sayıyı döner, `OddsKey(REFERENCE_BOOK, …)`u `pre_prices` kurar: `"Avg"`
literali `consensus.py`de GEÇMEZ (`test_single_sources.py` literalin tam üç dosyada durmasını ister). Modül yalnız
`history.types` sabitlerini import eder.
`live.context.pre_prices` onu çağırır; `football_edge.site` de onu çağırır ve `live.context`i import ETMEZ (H1f
geçişli bekçisi bunu zorlar: `live.context` `backtest.*` ve `history.catalog` import ettiği için dışa aktarıcının
kapanışında olamaz). Davranış eşitliği mevcut `pre_prices` testleriyle korunur.

### 4.4 Testler

1. **Metin (her kapıda, DB'siz):** `0014`te yasak tablo adları geçmez; **görünüm başına** beklenen süzgeç satır satır
   yazılır (`site.matches` ve `site_input.h2h_quotes` tabanla süzer; `site.leagues`, `site.ledger_head`,
   `site.record`, `site_audit.ledger_rows` süzmez — her biri adıyla); `site.record` gövdesi `where false`;
   `grant` satırları yalnız `site_reader`; kelime sınırlı `\bLOGIN\b` ve `\bPASSWORD\b` yok (`NOLOGIN` hariç;
   test SQL yorumlarını ayıklayıp koşar — migration yorumundaki "LOGIN" kelimesi eşleşmesin);
   `site_audit.ledger_rows` kolon kümesi Python sabitinden.
2. **Katalog + davranış (yerel Postgres kabı, `supabase/postgres` 17.6 — tam etiket B-1 T0'da sabitlenir).** İki
   yer (yalıtım §4.4/4): **(i) tam sıra, `postgres` veritabanında:** 0001→0014 SIRAYLA tek işlemde uygulanır, katalog
   iddiaları okunur, işlem GERİ ALINIR (0013 kum havuzu deseni; `CREATE EXTENSION` ve `cron.schedule` işlemseldir,
   geri alınınca cron işi kalmaz). **(ii) davranış, modül başına taze veritabanında** (§4.4/4). Migration bağlantısı
   her iki yerde **`postgres` rolüyledir** (`-U postgres`, `sandbox_db.sh` deseni): 0013'ün
   `alter default privileges for role postgres …` satırı yalnız `postgres`in yarattığı nesnelere uygulanır; imajın
   süper kullanıcısıyla (`supabase_admin`) uygulanırsa `site.public_floor()` PUBLIC EXECUTE'u korur, `grant execute`
   satırı ölçülmemiş olur ve görünüm sahibi canlıdan ayrışır. Ölçülenler: ilişki ve fonksiyon kapanışı
   (H1a); `site.public_floor` gövdesi tablo referanssız; `pg_get_userbyid(relowner) = 'postgres'` (üç tablo, bütün
   görünümler, `site.public_floor`) ve görünüm sahibi = tablo sahibi, `security_invoker` yok,
   `security_barrier` var (§4.2); `has_schema_privilege('anon','site','usage') = false` (üç şema);
   `has_table_privilege('site_reader','public.odds_snapshots','select') = false`; `site_reader` INSERT deneyi
   reddedilir; `rolbypassrls = false`; `site.record` kolon listesi = Python sabiti; `CREATE OR REPLACE VIEW
   site.record` ile kolon ADI/TİPİ değişikliği hata verir, sona kolon EKLEMEK hata vermez ama kolon listesi testi
   kırmızıdır (iki vaka). Holdout tohumları: `2026-01-15T12:00Z` → 0 satır, `2026-07-01T23:59:59.999999Z` → 0
   satır (sınırın komşusu), `2026-07-02T00:00Z` → 1 satır; `site_reader` olarak tohumlanmış maçlar > 0 satır.
   **Mutasyon kanıtı (planda):** 0014'ten `grant execute on function site.public_floor()` satırı silinince bu
   "> 0 satır" testi kırmızı olmalı (yalnız migration `postgres` rolüyle uygulanırsa olur).
3. **Uçtan uca (kapta, sentetik, ELLE HESAPLANMIŞ BEKLENEN DEĞERLERLE):** `ledger.chain` ile geçerli zincirli
   sentetik defter + maçlar + çıpa dosyası (kesimin ortasında bir `last_id`i işaret eder; çıpa, eksik çıpa kontrolü
   git geçmişi istediği için geçici bir depoda `git init` + commit ile kurulur — `test_verify_chain.py` deseni; aksi
   hâlde "ATLANDI" satırı dışa aktarımı her koşuda durdurur) tohumlanır → `site export`
   (B-1) → `verify-snapshot`; B-2 birleştirmesinde aynı JSON'la `next build` + `check-out` (§12.1). Test, türetmeyi
   yapan kodu ÇAĞIRMADAN elle yazılmış beklenenleri iddia eder: en az bir maç için açılış/son/kapanış `p` (görüntü
   hassasiyetinde, §5.4), `move`, `rounds`, her turun `books`u, `sealed`; eşik altı kitaplı bir tur → `null`;
   mühürsüz bir maç → `sealed: false`, `closing: null`; taban komşusu maç (`2026-07-01T23:59:59.999999Z`) anlık
   görüntüde YOK. Kurcalama iki varyant, ikisi de exit ≠ 0 ve hiçbir dosya yazılmaz: (a) çıpa SONRASI bir satırın
   fiyatı, (b) çıpa ÖNCESİ bir satırın fiyatı değiştirilmiş (N1: dışa aktarım GENESIS'ten hash'ler, §5.1). Kurcalanmış
   hâl tohumda kurulur — satır INSERT'ten ÖNCE değiştirilir, saklanan hash'ler eski kalır; UPDATE ve tetikleyici
   kapatma yoktur. **Sınır:** `site.record` Faz 5'e kadar `where false` olduğu için bu test sicilin defter tarafını
   yalnız BOŞ hâliyle koşar (§12.4/12).
4. **Yalıtım — seçim: şablonlu alt küme (inceleme R1'in (a) seçeneği).** Kısıtlar: append-only tablolar
   DELETE/TRUNCATE kabul etmez (0001 satır tetikleyicisi, 0013 TRUNCATE bekçisi) → temizlik ancak veritabanı
   düzeyinde olur; 0003 `pg_cron`u yalnız `cron.database_name` (`postgres`) veritabanında yaratabilir; `postgres`
   veritabanı şablon olamaz (pg_cron başlatıcısı ve pg_net işçisi ona sürekli bağlı).
   - **Şablon** `site_tpl`, `postgres` rolüyle yalnız sitenin kapanışındaki ve 0013'ün dokunduğu migration'larla
     kurulur: **0001, 0002, 0013, 0014**. Kanıt durumu: 0001+0002'nin ayrı bir veritabanına uygulanabildiği
     `test_api_roles_lockdown_db.py`nin kilit sondasıyla kanıtlı (sonda 0013'ün kilitte DÜŞMESİNİ bekler, onu
     uygulamaz); 0013'ün uygulanabildiği analizle beklenir — adla yalnız 0001/0002 nesnelerine başvurur, `ops`/`cron`/
     `vault`a başvurmaz — ve B-1 T0'da ölçülür. cron/Vault dispatch'leri (0003–0005, 0008, 0011) ve sitenin okumadığı
     tablolar (0006, 0007, 0009, 0010, 0012) dışarıda kalır. Tam sıranın kendisi (i)'de `postgres` veritabanında ölçülür.
   - **Alt küme sadakat testi (metin, her kapıda) — "dokunma" DEYİM HEDEFİYLE tanımlanır.** Atlanan migration'lar
     yorumlar ayıklanmış metinde şu deyimlerden hiçbirini taşımaz: hedefi `leagues`, `matches` ya da `odds_snapshots`
     olan `alter table`, `create trigger … on`, `create policy … on`, `create index … on`, `grant … on (table )?`,
     `revoke … on (table )?`; `… on schema (public|site|site_input|site_audit)` taşıyan `grant`/`revoke`; `create
     schema site*`; `alter default privileges`. **Adıyla izinli iki istisna:** (1) `references matches(id)` (0009,
     0012) — Postgres `matches` üzerine iç RI tetikleyicileri ekler, ama bunlar yalnız `matches`in UPDATE/DELETE'inde
     ateşlenir; site yalnız okur, testler yalnız ekler, dolayısıyla sitenin gördüğü dünya değişmez; (2) `revoke … on
     function ops.*` ve `revoke … on schema ops` (0003, 0004, 0005, 0008, 0011) — hedef `ops` şemasıdır ve `ops`
     şablonda yoktur. Başka her eşleşme kırmızıdır; yeni bir istisna ancak gerekçesiyle spec'e yazılarak eklenir.
     **Kendi mutasyon kanıtı (planda):** atlanan bir migration'a (ör. 0012) `grant select on matches to anon` ya da
     `alter table odds_snapshots …` eklenince test kırmızı; istisna satırlarından birinin hedefi `matches` yerine
     `leagues` yapılınca (ör. `create trigger … on leagues`) yine kırmızı.
   - **Oturum kurulumu (yerel ve CI, her oturum sıfırdan):** önce `DROP DATABASE IF EXISTS site_tpl` ve artık
     `site_t_*` veritabanları silinir, sonra şablon yeniden kurulur — önceki oturumdan kalan bayat bir `site_tpl`
     eski bir 0014'e karşı test koşturmaz. Roller küme düzeyinde kalır; 0014'teki rol yaratımı idempotenttir (`DO` +
     `pg_roles` denetimi; `NOLOGIN` metin testi değişmez), bu yüzden önceki oturumdan kalan `site_reader` hata
     vermez. Şablon kurulumu ile (i)'nin işlemi SIRALIDIR, eşzamanlı değil (açık bir işlemdeki commit'lenmemiş rol
     satırı öteki kurulumu kilitlerdi). (i) mevcut kum havuzunun hedef kilidini taşır: `current_user = 'postgres'`
     ve (i)'nin işlemi başında `to_regclass('public.odds_snapshots') IS NULL` — migration'ları zaten uygulanmış bir
     `sandbox_db.sh` kabına bağlanınca yanlış yere uygulamaz, adıyla reddeder.
   - **Her `sitedb` test modülü** (ve her kurcalama varyantı) `CREATE DATABASE site_t_<rastgele> TEMPLATE site_tpl`
     ile kendi kopyasını alır (dosya düzeyinde kopya: satır/ifade tetikleyicisi ateşlenmez), sonunda
     `DROP DATABASE … WITH (FORCE)` (TRUNCATE/DELETE değildir; tetikleyiciye takılmaz). Fixture şablon bağlantısını
     kopyalamadan önce kapatır. Roller küme düzeyindedir: `site_reader` ve rol GUC'leri bütün kopyalarda ortaktır.
     Veritabanı yaratma/silme ayrı bir bağlantıda olabilir; `postgres`in kapta `CREATEDB` taşıdığı T0'da ölçülür.
   - Böylece zincirsiz holdout tohumları (§4.4/2), geçerli zincirli defter (§4.4/3) ve her kurcalanmış zincir ayrı
     veritabanlarında durur; kırık bir zincir sonraki vakaları zehirlemez.
   - **Neden (b) değil** (şablonsuz, tek `postgres` veritabanında her şey `ledger.chain`den): kurcalama varyantları
     tanım gereği KIRIK zincir ister; tek paylaşılan zincirde ilk kurcalama sonraki bütün vakaları kırmızı yapar,
     yani her kurcalama için yeni kap (CI'da iş başına birden çok kap) gerekirdi. (a) bunu tek kapla çözer; bedeli alt
     kümenin sadakatini sınayan metin testidir.
   - **Testte tetikleyiciyi devre dışı bırakmak YASAKTIR:** bir metin testi `tests/test_site_*.py` ve `sitedb`
     fixture'larının KENDİ dosyasında (`tests/site_db.py`; `sitedb` fixture'ları başka dosyada durmaz, bunu da aynı
     test sınar) `disable trigger`, `session_replication_role` ve
     `alter table … disable` kalıplarının geçmediğini sınar; kalıplar testte parçalardan kurulur (kendini eşlemesin).
     Kapsam bilinçli olarak dardır: `tests/test_runbook.py` bugün RUNBOOK'tan alıntılanmış bir "DISABLE TRIGGER"
     literali taşır ve bu kuralın konusu değildir.
5. **Koruma:** davranış testleri append-only tablolara satır yazar — yalnız ATILABİLİR veritabanında. Fixture
   `SITE_TEST_DATABASE_URL`'in ana makinesi `localhost`/`127.0.0.1`/CI servis adı değilse ya da `DATABASE_URL`e
   eşitse testleri adıyla REDDEDER (kırmızı). Değişken yoksa: yerelde `SKIP: site-db (SITE_TEST_DATABASE_URL yok)`,
   **`CI=true` iken FAIL** (B10). Üretimde bu fixture hiç koşmaz.

### 4.5 Uygulama (onaydan sonra; bu tasarımın işi değil)
0013 canlıda (controller) → AK6 onayı → `0014` ROLLBACK'li prova → `apply_migration` → katalog testleri gerçek DB'ye
karşı salt okuma kipinde (`test_jev_tables_db.py` deseni) → RUNBOOK'a `site_reader` parola/`LOGIN` adımı →
**ölçülecek:** Supavisor kullanıcı biçimi (`site_reader.<proje_ref>`, `db.connect` session pooler'ı öngörüyor) ve rol
düzeyi GUC'lerin (`statement_timeout`, `default_transaction_read_only`) pooler üzerinden uygulandığı.

---

## 5. Dışa aktarım ve anlık görüntü sözleşmesi

### 5.1 Modül ve komutlar
`src/football_edge/site/` — `export.py`, `verify.py`, `slugs.py`, `__main__.py`. `__main__` `configure_logging`i
çağırır (test); `SITE_DATABASE_URL` `_log_secrets`e eklenir (RUNBOOK §3.8, DEFERRED 10o), redaksiyon testi genişler.
- `python -m football_edge.site export --out <dizin>` — önce `SITE_DATABASE_URL`in varlığını kendisi denetler (yoksa
  "SITE_DATABASE_URL yok — yayın yapılmadı" ile adıyla exit; `site.yml`de ayrı bir ön adım yoktur, çünkü secret
  yalnız bu adıma verilir ve `if:` içinde okunamaz). Sonra **tek** `BEGIN ISOLATION LEVEL REPEATABLE READ, READ ONLY`
  işleminde (B12) sırayla:
  1. **Zincirin TAMAMI:** depodaki HER çıpa sorulur (`_anchor_break`) ve kesim GENESIS'ten yeniden hash'lenir
     (`verify-chain --full` semantiği, `site_audit.ledger_rows` üzerinden). Anlık görüntü açılış konsensüsünü, `move`u,
     `rounds`u ve `move_distribution`ı tabandan beri BÜTÜN kesimden türettiği için yalnız çıpa kuyruğunu doğrulamak
     yetmez. Maliyet: defter bugün birkaç bin satır, tek `SELECT` 30 sn'lik `statement_timeout`un çok altında; büyüme
     AK22 ölçümüne bağlı. Çıpa eksikliği kontrolü git geçmişi ister: `site.yml` checkout'u `fetch-depth: 0`; git
     geçmişi okunamazsa ("ÇIPA EKSİKLİĞİ KONTROLÜ ATLANDI") dışa aktarım bunu SKIP değil kırmızı sayar ve durur.
     `_verify_chain_command`ın diğer iki indirgeme satırı da dışa aktarımda **kırmızıdır**: "çıpa yok ya da okunamadı —
     kuyruk kesme kontrolü ATLANDI" ve "en yeni çıpa okunamadı — bir önceki çıpaya düşürüldü" (en yeni çıpa
     okunamazsa `snapshot.ledger.anchor` zaten tanımsız kalır).
  2. `site.ledger_head`'den kesim `last_id`; `snapshot.ledger.head` = son satırın yeniden hesaplanmış hash'i.
  3. Oran sorguları `ledger_id <= last_id`; maç kümesi = kesim içinde en az bir oran satırı olan `site.matches`.
     **Varsayım (adıyla):** bütün defter yazımları `db.insert_snapshots` → `lock_ledger` (`pg_advisory_xact_lock`)
     ile serileşir; id'ler commit sırasıyla atanır ve anlık görüntüde görünen satırlar **commit'li id'lerin önekidir —
     boşluk olabilir** (geri alınan INSERT dizi değeri tüketir; ör. `ledger/head-2026-09-23.txt`te `rows` < `last_id`). Plan
     `rows == last_id` gibi bir iddia YAZMAZ. Kilitsiz
     bir defter yazarı eklenirse `max(id)` kesimi bozulur — plan bu varsayımı bir teste bağlar (defter INSERT'i yapan her
     yol `lock_ledger`ı çağırır).
  4. **Girdi dökümü** (yeni K1 yüzeyi, sınırları adıyla): işlemde okunan türetim girdileri — `site.*` ve
     `site_input.*` satırları, çıpa değerleri, yapılandırma (`devig` yöntemi, eşikler) — kanonik JSON'a
     (`ledger._canonical`; sayılar metin olarak, tipler açık) serileştirilir. **`site_audit` satırlarını TAŞIMAZ**:
     zincir doğrulaması 1. adımda biter, türetim onlara bakmaz. Döküm kitap bazında fiyat taşır (`site_input`) →
     **diske yazılmaz**, alt sürece **stdin** ile verilir, loga düşmez (redaksiyon testi dökümden bir parçanın loga
     girmediğini sınar). Alt sürecin **stdout ve stderr'i ana süreç tarafından yakalanır ve loga AKTARILMAZ**:
     çocuk çökerse traceback bir değer (ör. `ValueError` mesajında fiyat) taşıyabilir; ana süreç yalnız
     adlandırılmış bir hata basar ("ikinci türetim alt süreci düştü, çıkış kodu N"). Redaksiyon testine "çocuk
     çöker" vakası eklenir (çocuğa fiyat içeren bir istisna attırılır; public loga giden çıktıda fiyat yok).
  5. **İki türetim de AYNI dökümden:** süreç içinde `derive(load(döküm))`, ayrıca ayrı bir alt süreçte farklı
     `PYTHONHASHSEED` ile aynı çağrı (DB'ye bağlanmadan). DB'nin ham tipleri (`Decimal`, `datetime`) türetime hiç
     girmez; ikisi de dökümden çözülen tiplerle çalışır — ölçülen tek fark hash tohumudur ve iki `content_sha256` eşit
     olmalı. **Mutasyon kanıtları (planda, ayrı ayrı):** (a) dizi kurulumunda bir `str` KÜMESİ üzerinde dönmek → bu
     adım kırmızı (`int` hash'i tohumlanmaz; iki türetim aynı dökümü aynı sırayla okuduğu için yalnız küme sırası
     farkı doğurur). Kanıt olasılıklı OLMAMALI: mutasyon fixture'ı ≥ 32 farklı takım adı taşır VE kanıt iki sabit,
     farklı `PYTHONHASHSEED` ile önce bu fixture'da küme sırasının gerçekten farklı olduğunu sınar, sonra adımın
     kırmızı olduğunu; (b) `sorted(...)`ı kaldırmak → `verify-snapshot`in sıralılık kontrolü kırmızı (bu adım değil).
  6. §6.4/3d–e kontrolleri.
  Hepsi geçerse `snapshot.json` + `snapshot.sha256` (dosya baytlarının sha256'sı) yazar; biri kırmızıysa hiçbir dosya
  yazmadan adıyla exit. Log yalnız sayı ve hash basar. **Test:** `export` sonrası `--out` dizini TAM OLARAK
  `{snapshot.json, snapshot.sha256}` içerir (döküm ya da ara dosya sızmaz).
- `python -m football_edge.site verify-snapshot <dosya>` — **DB'siz**: şema, dizilerin tanımlı anahtarla sıralı olması,
  H1/H2/H3/H5 içerik kontrolleri, §4.3'ün yasak anahtar kümesi, `content_sha256` yeniden hesabı. CI'da fixture'lar ve
  §4.4/3'ün JSON'u, `site.yml`de gerçek anlık görüntü üzerinde koşar.

### 5.2 Anlık görüntü v1 (`web/contract/snapshot.schema.json`, JSON Schema; her nesnede `additionalProperties: false`)

```
schema_version: 1
generated_at, git_sha                        # content_sha256'ya GİRMEZ
content_sha256                               # generated_at, git_sha ve kendisi hariç gövdenin sha256'sı;
                                             # kanonikleştirici `ledger._canonical` (sort_keys, (",", ":"),
                                             # ensure_ascii=False) — defter hash'iyle aynı fonksiyon
ledger:   { rows, last_id, head, anchor: { file, rows, last_id, head } }   # çıpa: depodaki en yeni ledger/head-*.txt
floor:    "2026-07-02T00:00:00Z"
leagues:  [ { id, slug, name, country, matches: int,        # sıra: id
              move_distribution: { p10, p50, p90 } | null } ]   # |açılış→kapanış hareketi| yüzde puanı, maç ≥ 5 ise
teams:    [ { league_id, slug, name, matches: int,           # sıra: (league_id, slug)
              indexable: bool } ]                              # §8.4, Python'da
matches:  [ { id, league_id, path_id, slug, date,              # sıra: (commence_time, id); date = UTC takvim günü
              commence_time, home, away,
              sealed: bool,                                    # kesim içinde is_closing satırı var mı
              rounds: int,                                     # kesim içindeki h2h gözlem turu sayısı
              h2h: { opening|latest|closing: { observed_at, books: int,
                                                p: { home, draw, away } } | null },
              move: { home, draw, away } | null,               # açılış→kapanış (yoksa son), yüzde puanı
              indexable: bool } ]                              # §8.4, Python'da
record:   { published: int, entries: [ … site.record kolonları … ],   # sıra: publication_id
            summary: { mean_clv, ci_low, ci_high, n } | null } # n = 0 iken null
value_badge: null          # const null — Faz 5 şema sürümünü artırır
analysis:   null           # const null — Faz 7 şema sürümünü artırır
```
- `p` = vig'i temizlenmiş konsensüs, `market.devig` ile, yöntem `config/model_faz3.yaml`'daki (`power`) — model kodu
  neyse o. `books < SITE_MIN_BOOKS` (öneri 3) ise o tur `null`. `summary` aralığı `market.metrics.bootstrap_mean`
  (sabit tohum), CLV `market.metrics.clv`.
- Her dizi yukarıdaki anahtarla sıralıdır; `verify-snapshot` sıralılığı sınar (N3).
- Python şemayı dışa aktarımda ve fixture'larda doğrular (doğrulayıcı seçimi — `jsonschema` bağımlılığı mı el yazımı
  mı — planda). TS `Snapshot` tipini elle taşır; fixture `satisfies Snapshot` ile `tsc`'de sınanır; bir pytest
  şemanın anahtar kümesini TS tip dosyasınınkiyle karşılaştırır.
- Fixture'lar **sentetiktir** (uydurma lig/takım adları, gerçek satır yok): gerçek anlık görüntü depoya commit'lenmez
  (`.gitignore`: `web/node_modules/`, `web/.next/`, `web/out/`, `web/.snapshot/`).

### 5.3 Çıktı tarayıcısı (`web/scripts/check-out.ts`)
Node 24'ün yerleşik tip ayıklamasıyla, bağımlılıksız koşar. Kısıt: enum, namespace, yol takma adı (`@/lib`) yok;
importlar `.ts` uzantılı; uygulama koduyla paylaşılan modüller için `tsconfig` `allowImportingTsExtensions` +
`verbatimModuleSyntax`. HTML'i bağımlılıksız ayrıştırmanın sağlamlığı planda ölçülür (kırılgansa `data-fe-*` ve
JSON-LD dışındaki kontroller daraltılır; bağımlılık eklemek bilinçli commit).
Girdi: anlık görüntü + `web/out/**`. Ölçer: (1) her maç/lig/takım için tam bir sayfa, her sayfa için tam bir kayıt;
(2) H6c (öznitelik ve görünen metin); (3) sicil sayfasındaki `rows`, `last_id`, `head`, `published`, `summary` ve
`content_sha256` anlık görüntüye eşit (sayfa DOSYA hash'ini değil `content_sha256`i gösterir: dosya hash'i dosyanın
içinde olamaz ve derleme girdisi değildir); (4) `hreflang` karşılıklı, kendine atıflı, `x-default` var; (5) site haritası =
`indexable: true` kayıtların sayfa kümesi; `noindex` meta ↔ `indexable` birebir; (6) H4/H5/H7 kalıpları; (7) CSP: her satır içi YÜRÜTÜLEBİLİR betiğin sha256'sı
`out/_headers` CSP'sinde (AK19); `type="application/ld+json"` veri blokları CSP'ye tabi değildir ve hash listesine
girmez (girerse `_headers` gereksiz büyür); (8) basit erişilebilirlik: `<html lang>`, tek `<h1>`, `alt`, `<main>`, başlık sırası.

### 5.4 Biçimleme sözleşmesi
Anlık görüntü sayıları **görüntülenecek hassasiyette** taşır: olasılık ve hareket yüzde puanı 1 ondalık
(`45.7`), CLV yüzde 2 ondalık, fiyat 2 ondalık. TS yalnız dile göre ondalık ayracı (`45,7` / `45.7`) ve birim (`%`,
`pp`) ekler; yuvarlama, çarpma, toplama yapmaz. `format` fonksiyonu tek yerdedir ve tarayıcı onu çağırarak H6c'yi
sınar. **Hesap ham değerle, yuvarlama yalnız çıktıda:** `move`, `move_distribution`, `summary` ve `indexable` Python'da
yuvarlanmamış değerlerden hesaplanır, sonra görüntü hassasiyetine yuvarlanır. Yuvarlanmış üç `p`nin toplamı 100,0
olmayabilir; ne `verify-snapshot` ne tarayıcı toplamı sınar.

---

## 6. Sicil sayfası (T3)

### 6.1 Ne gösterir
- **Yayınlanmış tahminler** (`record.entries`): an, maç, market, sonuç, yayın oranı, kapanış adil oranı, CLV; özet
  (`record.summary`): sayı, ortalama CLV, güven aralığı — hepsi Python'da hesaplanmış.
- **Defter durumu:** zincir başı (`head`), satır sayısı, son id, dışa aktarım anı; depodaki en yeni çıpa dosyasının
  adı, değeri ve GitHub'daki geçmiş bağlantısı; anlık görüntünün `content_sha256`sı. `/data/snapshot.json` toplu
  indirmesi AK21'e bağlıdır. Dosya yayımlanmadıkça gösterilen hash bir **doğrulama değil taahhüttür**: bugün kimse onu
  yeniden hesaplayamaz; dosya sonradan açıklanırsa o gün doğrulanır. Sayfa bunu bu sözcüklerle yazar.
- **Nasıl doğrulanır** bölümü (§6.3).

### 6.2 Sicil boşken (bugün) — dürüst metin
"Yayınlanmış tahmin: **0**." Altında, sayı taşımadan (H1): "Temel modelimiz kapanış piyasasını geçmediği için henüz
tahmin yayımlamıyoruz. Tahmin yayını, önceden kaydedilecek bir kapanış değeri (CLV) ölçütü geçildiğinde başlayacak;
o güne kadar defter oranları ve kapanışları kaydetmeye devam ediyor." (Faz 5 kapısı henüz tasarlanmadı; cümle bir
tarih ya da eşik vaadi vermez — metin AK2 onay kapsamındadır.) Defter durumu bloğu dolu gösterilir: kayıt altyapısının
çalıştığının kanıtı odur. Boş durum bir **hata değil, bir durumdur**: `record.published = 0`, boş liste ve
`summary: null` tutarlı olmalı; ayrışırsa kapı kırmızı. "Yakında", sahte örnek, geriye dönük backtest sonucu
GÖSTERİLMEZ (backtest yayın değildir ve holdout'u taşır).

### 6.3 Zincir başının kullanıcıya gösterimi ve doğrulamanın sınırı
Gösterilen: DB'deki baş + depodaki çıpa. Aynı `last_id` ise "çıpa ile eşleşiyor"; defter çıpadan ilerideyse "son
çıpa `<dosya>`: `<last_id>` satırına kadar; sonrası sonraki mühür turunun çıpasında" yazılır.
**Dürüst sınır (sayfada yazılır):**
1. Zincir doğrusaldır; bir satırın başa bağlandığını göstermek ondan sonraki bütün satırları ister. Bugün
   yayımlanan: çıpaların git geçmişi ve anlık görüntü hash'i. Üçüncü kişi zinciri GENESIS'ten doğrulayamaz — defter
   satırının yükü kitap adı ve kitap fiyatı taşır (`payload_of`); tam döküm de tahmin başına kanıt satırı da bunları
   yayımlamak demektir (AK9, AK8, AK17).
2. **Git geçmişi güvenilir zaman damgası değildir:** depo sahibi geçmişi yeniden yazabilir (force-push); commit
   tarihi botun beyanıdır. Üçüncü kişi çelişkiyi ancak kendi aynası ya da GitHub'ın olay kaydıyla yakalar.
3. Satır bütünlüğünü yeniden hesaplamak kanonik JSON tarifini ister: `price`/`point` float metni,
   `canonical_timestamp` ISO biçimi (UTC, `+00:00`), `sort_keys`, ayırıcılar `(",", ":")`, `ensure_ascii=False`
   (`collect._normalised`, `ledger._canonical`). Tarif kanıt satırı yayımlanırsa (AK9 b) sözleşmeye girer (§6.5).

### 6.4 Kapı: sayfa ↔ defter birebir
Üç katman, çünkü CI'ın gerçek DB'si yok (bilinçli, `ci.yml` yorumu):
1. **CI'da (her push, DB'siz):** sentetik fixture'lar → `verify-snapshot` → `next build` → çıktı tarayıcısı §5.3
   (sayfa ↔ anlık görüntü). Fixture varyantları: boş sicil, dolu sicil (özetli), `books` eşik altı, mühürsüz maç,
   tek turlu maç. Dolu sicil YALNIZ burada (JSON → sayfa) ve dışa aktarıcının sahte DB birim testlerinde sınanır.
2. **CI'da (her push, geçici kapta):** §4.4/3 — gerçek görünüm SQL'i → dışa aktarıcı → `verify-snapshot` (B-1), sonra
   → `next build` → tarayıcı (B-2 birleşince), elle hesaplanmış beklenen değerlerle. Uçtan uca koşan: **maç ve defter
   durumu yolu** (defter → görünüm → türev sayılar → sayfa) ve iki kurcalama varyantı. **Sicil yolu Faz 5'e kadar
   yalnız BOŞ hâliyle** uçtan uca koşar: `site.record` `where false` (§12.4/12).
3. **`site.yml`'de (gerçek DB, yayından önce; biri kırmızıysa yayın yok):**
   a. zincir: HER çıpa + kesimin GENESIS'ten yeniden hash'lenmesi (§5.1/1), `site_audit.ledger_rows` üzerinden,
      mevcut `verify_chain` ve `_anchor_break` ile — ikinci bir zincir okuyucusu yazılmaz. Plan maddesi (K1):
      `collect._LEDGER_COLUMNS` / `_LEDGER_ALL` / `_LEDGER_AFTER` / `_LEDGER_AT` bugün `FROM odds_snapshots` gömülü SQL
      metinleri ve `_anchor_break` `SELECT count(*) FROM odds_snapshots` sabitini taşıyor; bunlar kolon tuple'ı +
      ilişki adı parametresi olarak ayrılır (varsayılan `odds_snapshots`, site `site_audit.ledger_rows`).
      `odds_snapshots` okuyucularının envanteri (`collect.py`, `db.py`, `live/store.py`) planda çıkarılır; bugün
      onlar için bir okuyucu bekçisi yoktur;
   b. `snapshot.ledger.head` = kesimdeki son satırın YENİDEN HESAPLANMIŞ hash'i (hücre değil — `_anchor_break` ilkesi);
   c. belirlenimcilik (§5.1/5): ayrı alt süreçte, farklı `PYTHONHASHSEED` ile, işlemin girdi dökümünden ikinci türetim
      aynı `content_sha256`yı üretir. İşlem kapandıktan sonra DB'den yeniden türetme bu eşitliği vaat etmez
      (`matches` değişebilir) ve vaat edilmez;
   d. `record.published` = `site.record` satır sayısı; her girdinin CLV'si defter satırlarından `market.metrics.clv`
      ile yeniden hesaplanır;
   e. `verify-snapshot` + §5.3 tarayıcısı gerçek anlık görüntüyle;
   f. yayından sonra: canlı `/data/snapshot.sha256` indirilir ve derlenmiş olanla karşılaştırılır (AK21 kapalıyken
      dosyanın kendisi yayımlanmaz ama hash dosyası yayımlanır); `curl -I` ile örnek sayfalarda `X-Robots-Tag` ve
      CSP başlıkları okunur (yayımlanan = doğrulanan).

### 6.5 Faz 5'e devredilen şartlar (İz B bunları KURMAZ, sözleşmeye yazar)
- `publications` tablosu append-only + TRUNCATE tetikleyicisi + kendi hash zinciri; `site.record` ona B5 ile bağlanır.
- **Zaman kanıtı:** bir tahminin maçtan ÖNCE yayımlandığı kanıtlanmalı. Sorun çıpa sıklığı değil (çıpa her mühür
  turunda commit'leniyor): git commit tarihi güvenilir zaman damgası değildir (§6.3/2) ve bugün tahmin zinciri yoktur.
  Seçenekler: yayın turunda tahmin zincirinin başını commit'leyip siteyi aynı turda yayımlamak; ek olarak harici zaman
  damgası (ör. OpenTimestamps) ile başı bağımsız bir tanığa bağlamak.
- CLV tek fonksiyon: `market.metrics.clv(price, fair_probability)`; sitede yeniden yazılmaz.
- Kanonik JSON tarifi (§6.3/3) kanıt satırı yayımlanacaksa sözleşmeye girer.

---

## 7. Maç sayfası (T2) ve value yeri

İçerik (hepsi anlık görüntüden, hesap yok): lig, takımlar, başlama anı (`<time datetime>` UTC; yerel saat küçük bir
istemci betiğiyle, betiksiz UTC görünür), 1X2 konsensüs olasılıkları açılış/son/kapanış, açılış→kapanış hareketi
(`move`), kitap SAYISI, gözlem turu sayısı, mühür durumu ("kapanış kaydedildi" / "bekleniyor"). **Kitap adı, kitap
oranı, bağlantı yok** (B7). Value rozeti bileşeni vardır ve `value_badge === null` iken HİÇBİR şey çizmez (boş kutu,
"yakında" yazısı yok); Faz 5 şema sürümünü artırıp alanı doldurduğunda çizer. Skor yok (AK10).

---

## 8. Programatik SEO (T4)

### 8.1 URL şeması (sabit bölüt adları İngilizce, dil öneki arayüz dilini seçer)
Öneri AK20(b)'ye göre (maç yolu değişmez kimlik taşır, tarih taşımaz):

| Sayfa | Yol |
|---|---|
| Dil ana sayfası | `/{lang}/` (`/` → `/en/`, `out/_redirects`; `x-default` = `/en/`) |
| Lig | `/{lang}/{league}/` |
| Takım | `/{lang}/{league}/{team}/` |
| Maç | `/{lang}/{league}/match/{path_id}/{home}-vs-{away}/` — `path_id` = The Odds API olay kimliğinin sabit uzunlukta öneki (çakışma testli); isim bölütü süstür |
| Sicil | `/{lang}/track-record/` |
| Yasal | `/{lang}/legal/{terms,privacy,cookies,responsible-gambling}/` |

Kurallar: lig slug'ı `track-record`/`legal` olamaz; takım slug'ı `match` olamaz; `path_id` çakışması derlemeyi
kırmızı yapar (test). `generateStaticParams` + `dynamicParams = false`: anlık görüntüde olmayan yol 404'tür. Her
maç için `out/_redirects`e `/{lang}/{league}/match/{path_id}/*` → güncel yol **zorlamasız** `301` (`301!` DEĞİL)
yazılır: güncel yol dosya olarak var olduğu için kural onu gölgelemez ve kendine yönlenmez; takım adı değişse de eski
maç URL'si çözülür. Erteleme URL'yi değiştirmez (tarih yolda değil; görünen metinde, UTC). `path_id` The Odds API olay
kimliğini kamuya açar → AK17'nin okuma kapsamına girer; olay kimliğinin ertelemede korunduğu ölçülmedi (§17).
Lig pasifleşirse (`active = false`) lig, takımları ve maçları anlık görüntüden düşer. AK20(b)'nin kaybolan-slug
kontrolü bunu `config/site_redirects.yaml`daki tek bir `gone: <lig>` girdisiyle kabul eder (lig altındaki bütün
slug'lar muaf; sunulan durum 404 ya da 410 — Netlify davranışı planda ölçülür); girdi yoksa kırmızı. Saklama AK22.

### 8.2 Slug'lar
Kendi testli fonksiyonu `site/slugs.py` (`naming.normalise_team`a DAYANMAZ — o eşleşme için load-bearing'dir,
eşleşme düzeltmesi URL'leri sessizce değiştirmemeli). Dondurulmuş test vektörleri (Türkçe İ/ı, aksan, ek, noktalama)
fonksiyon değişikliğini kırmızı yapar. Kalıcılık deposu AK20.

### 8.3 Diller — YER TUTUCU (AK5)
Sözlükler `web/src/i18n/{lang}.json`, tipli erişimci; kütüphane yok. Dil listesi tek yerde (`web/site.config.ts`,
`SITE_LANGS`). Her sayfa etkin bütün dillere `alternates.languages` + `x-default`; site haritası girdileri de
`alternates` taşır. Veri dilden bağımsızdır; yalnız arayüz metni çevrilir. Öneri: ilk sürüm `en` + `tr` (spec §1.2
EN birincil; TR yasal inceleme zaten gerekiyor). Makine çevirisi yayımlanmaz.

### 8.4 İndeksleme politikası (B8'in üstünde, `SITE_INDEXABLE` açıkken)
`indexable` Python'da hesaplanır ve anlık görüntüye yazılır (anlık görüntü yalnız açılış/son/kapanış turlarının
`books`unu taşıdığı için eşik oradan türetilemez). Maç: `rounds ≥ 2` VE kesimdeki turlardan en az birinde
`books ≥ SITE_MIN_BOOKS`. Takım: `matches ≥ SITE_MIN_TEAM_MATCHES` (öneri 3). `indexable: false` sayfa `noindex` alır
ve site haritasına girmez; tarayıcı ikisini `indexable`a karşı sınar. Kanonik URL alan adıdır (AK4); `*.netlify.app`
alt alanı her zaman `noindex` (yöntem planda ölçülür, §18).

### 8.5 İnce/kopya içerik riski
Faz 7 yokken maç sayfası yalnız sayısal türev taşır; binlerce benzer sayfa "ince içerik" sayılabilir. Panzehirler:
(1) §8.4 eşikleri; (2) her sayfada maça özgü türev (hareket, kitap sayısı, tur sayısı, mühür durumu) — şablon
cümlesi değil sayı; (3) lig sayfası o ligin hareket dağılımı (`move_distribution`, Python'da); (4) diller arası
aynı veri `hreflang` ile bağlı (kopya değil alternatif). Kalan risk: arama motorunun yargısı ölçülemez (§12.4).

### 8.6 Faz 7'nin yeri
Maç şablonunda `analysis` yuvası (bileşen + şema alanı) var, `null`dır; Faz 7 Jev doğrulama geçidini kurunca şema
sürümü artar. Yuva boşken sayfa hiçbir yer tutucu metin çizmez.

---

## 9. schema.org (T5)

JSON-LD, sayfa başına bir `<script type="application/ld+json">` (veri bloğu; CSP'den etkilenmez), anlık görüntüden
üretilir, `schema-dts` yalnız tip olarak (çalışma zamanı bağımlılığı değil; plan kaldırabilir):
- Ana sayfa: `WebSite` + `Organization` (ad = marka yer tutucusu, AK3; `url` = alan adı yer tutucusu, AK4).
- Lig: `SportsOrganization` (ad, ülke). Takım: `SportsTeam` (ad, `memberOf` lig).
- Maç: `SportsEvent` — `name`, `startDate`, `homeTeam`/`awayTeam` (`SportsTeam`), `sport: "Soccer"`, `organizer` lig.
  `eventStatus: EventScheduled` YALNIZ başlama anı dışa aktarım anından sonraysa; geçmiş maçta alan basılmaz (durum/skor
  bilgimiz yok). `location` yok; `offers`, oran, bahis bağlantısı YOK.
- Her sayfa: `BreadcrumbList`.
Test: oluşturucular birim testli; tarayıcı her sayfada JSON-LD'nin ayrıştığını ve `@type`ın beklenen olduğunu sınar.
Google Zengin Sonuç doğrulaması kapıda değil (ağ, §12.4).

---

## 10. 18+, sorumlu bahis, KVKK, çerez (T6) ve Türkiye riski

### 10.1 Metin taslakları — hepsi "TASLAK — avukat onayı bekler" başlığıyla (`web/content/legal/{lang}/*.tsx`)
**Çizim yolu:** yasal metinler markdown DEĞİL, düz TSX içerik bileşenleridir (çalışma zamanı bağımlılığı yalnız
`next`/`react`/`react-dom`; markdown çizicisi yok ve çiziciler ham HTML'i varsayılan olarak düşürür). Böylece H4'ün
`data-fe-allow="license-negation"` özniteliği kaynakta yazıldığı gibi derlenmiş HTML'e geçer ve "kaynaktaki işaret
sayısı = derlenmiş HTML'deki sayı" eşitliği anlamlıdır. Avukat incelemesi için metinler ayrıca düz metin olarak
dışa aktarılabilir (plan).
- **Kullanım koşulları:** site bilgi amaçlıdır, bahis kabul etmez, bahisçiye yönlendirmez, bağlantı içermez;
  olasılıklar garanti değildir; geçmiş performans geleceği göstermez; veri kaynağı hakkında lisans iddiası yok (H4 —
  olumsuz cümle işaretli paragrafta).
- **Sorumlu bahis:** 18+; bahis bağımlılığı riski; yardım kaynakları (TR: Yeşilay danışma hattı; EN: ülkeye göre) —
  **iletişim bilgileri yayından önce birincil kaynaktan doğrulanır, taslakta `[DOĞRULANACAK]` işaretli.**
- **KVKK aydınlatma / gizlilik:** site kişisel veri TOPLAMAZ (hesap, form, analitik yok); barındırıcının erişim
  kayıtları (IP) veri sorumlusu–işleyen ilişkisi ve yurt dışı aktarım (Netlify) — avukat sorusu olarak işaretli.
  Sitede oyuncu sağlık bilgisi yayımlanmaz (H2); projenin genel md. 6 sorusu HANDOFF §0.7/7'de.
- **Çerez:** yalnız zorunlu yerel depolama (18+ onayı). Analitik yok (AK12) → çerez bandı yalnız bilgi.

### 10.2 18+ kapısı
İlk ziyarette tam ekran bildirim ("18 yaşından büyüğüm" / çıkış), onay `localStorage`'da; betiksiz tarayıcıda
sayfa üstünde kalıcı 18+ şeridi (CSS/`<noscript>`). **Bu bir yaş doğrulaması DEĞİLDİR** (§12.4); içerik HTML'de durur.
İstemci betiği CSP kararına (AK19) bağlıdır.

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

- **`web/netlify.toml`:** `[build] publish = "out"`; `command` Netlify'da derlemeyi reddeden bir komut (Netlify Git'e
  bağlanmaz; yayın yalnız CLI ile hazır dizindir). CLI `web/` dizininden (ya da `--config web/netlify.toml` ile)
  koşar, yoksa dosya okunmaz. **Başlıklar `netlify.toml`de değil, derlemenin ürettiği `out/_headers`te** (B8, AK19):
  CSP, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, bayrak kapalıyken `X-Robots-Tag: noindex`.
  `_redirects` de `out/` içinde üretilir (§8.1).
- **`.github/workflows/site.yml`:** yalnız `workflow_dispatch`; `permissions: contents: read`; `concurrency`
  `site-deploy`; checkout `persist-credentials: false`, **`fetch-depth: 0`** (çıpa eksikliği kontrolü git geçmişi
  ister; sığ checkout'ta "ATLANDI" satırı dışa aktarımı durdurur, §5.1/1); adımlar: `uv sync --frozen` →
  `site export` (**yalnız bu adım** `SITE_DATABASE_URL` alır; secret'ın varlığını komut kendisi denetler, ayrı ön adım
  yok) → `verify-snapshot` → kaybolan-slug kontrolü (önceki yayının `/data/slugs.json`ı ↔ yeni derleme, AK20 b;
  önceki yayın yoksa yalnız açık `--first-publish` girdisiyle geçer, site erişilemezse kırmızı) → pnpm kurulum →
  `next build` → çıktı tarayıcısı → `netlify deploy --prod --dir out` (**yalnız bu adım** `NETLIFY_AUTH_TOKEN`,
  `NETLIFY_SITE_ID` alır; `netlify-cli` sürümü sabit) → yayın sonrası kontrol (§6.4/3f). `schedule` YOK; pg_cron
  dispatch YOK (AK15). Test: adım başına ortam anahtar kümesi (H5d), tetik kümesi = `{workflow_dispatch}`.
- **Neden Netlify'da derleme değil (AK16):** Netlify derlerse DB kimliği Netlify'a verilmek zorunda kalır ve dışa
  aktarımın doğrulaması Actions'ın dışında koşar.

---

## 12. Site kapısı

### 12.1 Adımlar (`verify.sh`; her biri `step` ile adıyla PASS/FAIL)
| Adım | Plan | Komut | Ölçer |
|---|---|---|---|
| `pytest` (mevcut) | B-1 | `tests/test_site_*.py` | Migration metin testleri, dışa aktarıcı (sahte DB), `verify-snapshot` fixture'larda, import bekçisi, şema ↔ TS anahtar eşitliği, `site.yml` adım ortamı, log redaksiyonu, slug vektörleri |
| `sızıntı` (mevcut) | B-1 | `leakage` işaretli site testleri | H1; `EXPECTED_MIN_LEAKAGE` B-1 birleştirmesinde ölçülerek yükseltilir |
| `site-db` (yeni) | B-1 | `pytest -m sitedb` | §4.4/2–4 katalog, davranış, uçtan uca (dışa aktarıma kadar, beklenen değerlerle); `CI=true` ve değişken yok → FAIL. Uçtan uca vakanın ürettiği anlık görüntüyü sabit dizine yazar: `${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e/` (GitHub'ın Ubuntu koşucularında `TMPDIR` tanımsızdır). Adım BAŞTA bu dizini boşaltır, sonra `snapshot.json` ile birlikte bu `verify.sh` koşusunun kimliğini (`verify.sh`in başta ürettiği `FE_VERIFY_RUN_ID`) `run-id` dosyasına yazar; Node adımlarından ÖNCE koşar |
| `site-kurulum` | B-2 | `pnpm -C web install --frozen-lockfile` | Kilit dosyası ↔ `package.json`; bağımlılık yaşam döngüsü betikleri kapalı (pnpm varsayılanı; izin listesi boş) |
| `site-tip` | B-2 | `pnpm -C web exec tsc --noEmit` | Tipler, fixture `satisfies Snapshot` |
| `site-lint` | B-2 | `pnpm -C web exec biome ci` | Lint + biçim (tek bağımlılık) |
| `site-test` | B-2 | `pnpm -C web exec vitest run` | `format`, `hreflang`, JSON-LD, 18+ bileşeni |
| `site-derleme` | B-2 | `next build` üç kez: fixture bayraksız, fixture `SITE_INDEXABLE=1` (yayımlanmaz), `${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e/snapshot.json` | Statik üretim; bayrak açık yol; uçtan uca JSON'un sayfaya dönüşmesi. Uçtan uca JSON yoksa ya da `run-id` bu koşunun `FE_VERIFY_RUN_ID`sine eşit değilse (önceki koşudan kalmış BAYAT dosya): yerelde adıyla SKIP, **`CI=true` iken FAIL** — bayat veriyle PASS yok |
| `site-uyum` | B-2 | `node web/scripts/check-out.ts` (üç derlemenin her biri) | §5.3 — sayfa ↔ anlık görüntü, H4–H7, `hreflang`, site haritası ↔ `noindex`, §8.4 eşikleri, CSP hash'leri, basit erişilebilirlik |

pnpm ya da Node yoksa B-2 adımları **FAIL** (SKIP değil): site kapının parçasıdır.

### 12.2 CI bağlantısı (`ci.yml`) — iki aşamada, sıralı
- **B-1 dalga sonu birleştirmesi:** mevcut `gate` işine `services: postgres: supabase/postgres:<T0'da sabitlenen tam
  etiket>` (parola iş içinde üretilir, secret değil — `test_ci_reads_no_repository_secret_at_all` uyumlu) ve
  `SITE_TEST_DATABASE_URL`; `verify.sh`e `site-db` adımı ve `EXPECTED_MIN_LEAKAGE` artışı. `DATABASE_URL` yine
  VERİLMEZ (zincir SKIP kalır). `timeout-minutes` ölçülerek artırılır. B-1'in K1 testleri böylece B-1 birleştiği
  anda CI'da koşar; B-2'yi beklemez.
- **B-2 son görevi (B-1 birleştikten SONRA):** `actions/setup-node` (sürüm `web/.nvmrc`) + `pnpm/action-setup`
  (`packageManager`) ve Node adımları.

### 12.3 Tek yazar
`verify.sh` ve `ci.yml` ortak dosyadır: önce B-1'in birleştirme görevi, sonra B-2'nin son görevi yazar — iki plan
aynı dosyaya aynı anda yazmaz; sıralama kuralı korur (yol haritası §4).

### 12.4 Kapının ÖLÇMEDİKLERİ (ön liste — faz HANDOFF'unda tamamlanır)
1. **Gerçek veriyle sayfa ↔ defter uyuşması** yalnız `site.yml`de ölçülür; `site.yml` bağlı değil → bugün gerçek
   veride HİÇ ölçülmedi (sentetik veride her push'ta ölçülür, §6.4/2).
2. Canlı DB'de görünüm ve yetkiler (0014 uygulanmadı); CI kabı Supabase'in canlı rol/varsayılan yetki kurulumunun
   birebir kopyası değildir. Pooler üzerinden rol GUC'lerinin uygulanması (§4.5).
3. Üçüncü kişi zinciri baştan doğrulayamaz (§6.3/1); git geçmişi güvenilir zaman damgası değildir (§6.3/2); Faz 5
   öncesi yayın anı kanıtı yok (§6.5).
4. H1 veriyi ve görünümleri kapsar; **elle yazılmış metne** (yasal sayfa, açıklama) holdout sayısı yazılmasını
   anlamsal olarak yakalamaz — yalnız tarih kalıplarını tarar.
5. H4 kalıp listesidir: listede olmayan bir ifadeyle yapılan lisans iddiasını yakalamaz.
6. 18+ kapısı yaş doğrulaması değildir; yasal metinlerin doğruluğu (taslak) ölçülmez.
7. SEO sonucu, indekslenme, ince içerik yargısı, Zengin Sonuç doğrulaması, Core Web Vitals.
8. Tam erişilebilirlik (axe, ekran okuyucu), görsel regresyon, tarayıcılar arası çizim; istemci betiklerinin tarayıcıda
   CSP altında gerçekten çalıştığı (yalnız hash eşleşmesi ölçülür).
9. Netlify'ın başlıkları her sayfada sunduğu (yayın sonrası kontrol örnek sayfalarda).
10. Çeviri kalitesi; takım/lig slug'larının sağlayıcı ad değişikliklerine dayanıklılığı (AK20'nin seçimine bağlı).
11. The Odds API koşullarına ve TR mevzuatına uyum (AK13, AK17).
12. **Dolu sicilin defter tarafı** (görünüm → dışa aktarıcı → CLV yeniden hesabı) Faz 5 `publications` gelene kadar
    yalnız sahte DB ile sınanır; kapta uçtan uca yalnız boş sicil koşar (§6.4/2).
13. Belirlenimcilik kontrolü (§5.1/5) hash tohumuna bağlı sıra ve `now()`/rastgelelik kullanımını yakalar — küme
    sırası hatasını ancak OLASILIKLA yakalar (küçük bir `str` kümesi iki tohumda aynı sırada dönebilir; üretimde
    tohumlar rastgeledir); işlemler
    arası (DB değiştikten sonra) yeniden üretilebilirliği ölçmez ve vaat etmez.
14. Kesim tutarlılığı defter yazarlarının `lock_ledger` ile serileştiği varsayımına dayanır (§5.1/3); varsayımı bir
    test sınar ama kilitsiz bir yazarın canlı DB'ye başka yoldan (elle SQL) yazmasını durdurmaz.
15. Tam zincir taraması defter büyüdükçe uzar; süre ölçülmez, AK22'ye bağlıdır.

---

## 13. Dizin yapısı, sürümler, bağımlılıklar

```
web/
  package.json · pnpm-lock.yaml · .nvmrc · tsconfig.json · next.config.ts · biome.json · netlify.toml · site.config.ts
  contract/snapshot.schema.json          # Python ile ortak sözleşme
  fixtures/snapshot.fixture*.json        # sentetik
  content/legal/{lang}/*.tsx             # TASLAK (düz TSX, markdown yok)
  scripts/check-out.ts · scripts/emit-headers.ts   # tarayıcı; _headers/_redirects üretimi (CSP hash'leri)
  src/app/[lang]/…                       # §8.1 yolları; sitemap.ts, robots.ts
  src/lib/{snapshot,hreflang,jsonld,format}.ts · src/i18n/{lang}.json · src/components/…
src/football_edge/site/{__init__,__main__,export,verify,slugs}.py
src/football_edge/market/consensus.py    # yaprak modül: tur → ortalamalar + tam kitap sayısı
db/migrations/0014_site_read.sql
.github/workflows/site.yml
tests/test_site_*.py
```
- **Node 24 LTS** (`.nvmrc` + `engines`; Node 26 LTS'e geçiş ayrı iş), **pnpm 10** (`packageManager` alanı).
- **Next.js** App Router, `output: 'export'`, `images.unoptimized: true`, `trailingSlash: true`; sürüm plan günündeki
  kararlı sürüm, kilit dosyasıyla sabit.
- **Çalışma zamanı bağımlılığı yalnız** `next`, `react`, `react-dom`. Dev: `typescript`, `@types/react`,
  `@types/node`, `vitest`, `@biomejs/biome`, (isteğe bağlı) `schema-dts`. CSS modülleri; i18n, durum yönetimi, UI
  kütüphanesi, Supabase istemcisi YOK. Bağımlılık allowlist testi (H5a) bu listeyi sabitler; eklemek bilinçli commit.
  `netlify-cli` depo bağımlılığı değildir; `site.yml`de sabit sürümle çağrılır.
- `.gitignore`: `web/node_modules/`, `web/.next/`, `web/out/`, `web/.snapshot/`.

---

## 14. Risk kademeleri (yol haritası v2 §3)

| Kademe | İş | Süreç |
|---|---|---|
| **K1** | `0014` (rol, yetki, sahiplik, `security_barrier`, görünümler, holdout tabanı, yer tutucu sicil) · `pre_prices` refactor'u · zincir okuyucusunun parametrelenmesi · dışa aktarıcı (tek işlem, zincir, yeniden türetme, CLV) · `verify-snapshot` (H1/H2/H3/H5 içerik) · import bekçisi · `site.yml` adım secret sınırı · log redaksiyonu · çıktı tarayıcısının H6 (sayfa ↔ anlık görüntü) ve CSP kısmı | TDD + görev incelemesi (mutasyonlu; yerel kapta migration koşan inceleyici) + bütün-dal incelemesi. B-2'deki tarayıcı görevi de bu süreçle işaretlenir |
| **K2** | pSEO (slug, `hreflang`, site haritası, `noindex` eşikleri, `_redirects`) · schema.org oluşturucuları · kapı entegrasyonu (`verify.sh`, `ci.yml`) · `_headers` üretimi | TDD + tek görev incelemesi |
| **K3** | Görsel şablonlar, i18n sözlükleri, yasal metin taslakları (hukuk onayı ayrıca AK13) | Controller doğrulaması |

---

## 15. Planlara bölünme (tek plana sığmaz)

- **Plan B-1 — okuma katmanı, dışa aktarım ve K1 testleri (İLK):**
  T0 CI servis kabında ölç ve sabitle (ölçmeden B10 yok): imaj etiketi; 0001→0013'ün `postgres` veritabanında
  `postgres` rolüyle tek işlemde uygulanıp geri alınabildiği; 0001+0002+0013'ün ayrı bir şablon veritabanına
  uygulanabildiği; `postgres` rolünün `CREATEDB` taşıdığı ve `CREATE DATABASE … TEMPLATE site_tpl`in çalıştığı;
  T1 `snapshot.schema.json` + sentetik fixture'lar + biçimleme sözleşmesi (sözleşme görevi — B-2'nin başlangıç kapısı
  bu commit); T2 `0014` + metin/katalog/davranış testleri; T3 `market/consensus.py` yaprak modülü + `pre_prices`in ona
  bağlanması + zincir okuyucusunun (kolon tuple'ı + ilişki parametresi) ayrılması + `lock_ledger` varsayım testi;
  T4 dışa aktarıcı (tek işlem, tam zincir, alt süreçte ikinci türetim) + slug fonksiyonu; T5 `verify-snapshot` +
  geçişli import bekçisi + şablon veritabanlı test yalıtımı + beklenen değerli uçtan uca kap testi (iki kurcalama); T6 `site.yml` (bağlanmamış) + adım ortamı testi + redaksiyon + `check_secrets.sh` genişlemesi;
  **dalga sonu birleştirme:** `ci.yml` servis kabı + `verify.sh` `site-db` + `EXPECTED_MIN_LEAKAGE`.
- **Plan B-2 — web yüzeyi (K2/K3, tarayıcı K1 süreciyle; B-1 T1 birleşince paralel):** iskelet + sözlükler;
  maç/lig/takım/sicil/yasal sayfaları; slug yolları + `hreflang` + site haritası + `_redirects`; JSON-LD; 18+;
  `_headers` üretimi (CSP, AK19); yasal taslaklar; çıktı tarayıcısı; `netlify.toml`; **son görev (B-1
  birleştikten SONRA):** `verify.sh` Node adımları + `ci.yml` Node kurulumu ve kapı süresi ölçümü; §4.4/3'ün JSON'uyla
  `next build` + tarayıcı.
- Aynı anda en çok 4 implementer; K1 görevleri kendi worktree'lerinde, `--no-ff` birleştirme.

---

## 16. Açık kararlar (HANDOFF §0.7'ye eklenecek)

| No | Karar | Seçenekler | Öneri | Neyi bloklar |
|---|---|---|---|---|
| AK1 | Mimari yaklaşım | A · B · C (§3) | **A** | Her iki planın yazımı |
| AK2 | Bu spec'in onayı (sicil boş durum metni §6.2 dahil) | onay · düzeltme | — | `writing-plans` |
| AK3 | Marka adı (§0.7/1) | kullanıcı | — (yer tutucu `SITE_NAME`) | `Organization` JSON-LD, yasal metinler, alan adı, deploy |
| AK4 | Alan adı + kayıt yeri + Netlify hesabı (§0.7/2) | Cloudflare Registrar · Namecheap · Netlify | Kullanıcı; kayıt yeri Netlify DNS'e bağlanabilen herhangi biri | Kanonik URL, site haritası, `hreflang` mutlak adresleri (yer tutucu `https://example.invalid`), deploy |
| AK5 | İlk sürüm site dilleri | `en` · `en`+`tr` · spec §1.2'nin yedisi | **`en` + `tr`** | Sözlükler, yasal metin dilleri, hukuk kapsamı |
| AK6 | Halka açık okuma katmanı (§0.7/3) | §4.3 listesi · daraltılmış · genişletilmiş | **§4.3 listesi** (`site` yayımlanabilir; `site_input`, `site_audit` yayımlanmaz) | `0014`ün uygulanması |
| AK7 | Eski tablolara RLS + TRUNCATE + yetki geri alma (12a) | — | **Kapandı: Dalga A Task 6 `0013`, canlıya controller uygular.** A için ön koşul değil; B/C için "0013 canlıda + advisors temiz" ön koşul | — |
| AK8 | Maç sayfasında oran biçimi | (a) vig'siz olasılık · (b) + adil oran · (c) kitap adı ve oranları | **(a)** | Maç şablonu |
| AK9 | Kamu doğrulamasının derinliği | (a) çıpalar + baş + anlık görüntü hash'i · (b) + tahmin başına kanıt satırları · (c) tam defter dökümü | **Şimdi (a).** (b) ve (c) kitap adı ve kitap fiyatı yayımlar → AK8(c) + AK17 onayına bağlı; onaylanırsa (b) Faz 5'te, kanonik JSON tarifiyle | Sicil "nasıl doğrulanır" metni |
| AK10 | Skor kaynağı | yok · The Odds API `scores` (kredi) · football-data (yazılı izin yok → hayır) | **İlk sürümde skor yok** (CLV sicili skor gerektirmez; ROI yok) | Sonuç/ROI gösterimi |
| AK11 | Gölge seri (`model_predictions`) sitede mi | hayır · maç bitince toplu özet | **Hayır** (H3; model piyasayı geçmedi) | — (gelecek şema sürümü) |
| AK12 | Analitik | yok · Netlify sunucu tarafı · üçüncü taraf | **Yok** | Çerez metni |
| AK13 | Hukuk metinleri ve TR riski (§0.7/7) | avukat onayı | — | İndekslemeye açma, TR dili yayını |
| AK14 | İndekslemeye açma (`SITE_INDEXABLE`) | ilk yayından · onaylardan sonra | **AK3, AK4, AK13'ten sonra** | Arama trafiği |
| AK15 | Yeniden derleme tetiği (bağlanınca) | elle · günlük snapshot sonrası · + saatte en çok bir mühür sonrası (pg_cron → `ops.dispatch_workflow('site.yml')`) | **Günlük + saatlik mühür sonrası** | `site.yml`in otomatiği. **Yeni migration gerekir** (pg_cron izinli listesi); `test_workflows.py` izinli listedeki her workflow'da alarm adımları + `issues: write` ister → `permissions: contents: read` ile uzlaştırılmalı |
| AK16 | Netlify yayın yöntemi | Actions'tan hazır dizin (CLI) · Netlify Git derlemesi | **CLI** | `site.yml` |
| AK17 | The Odds API koşullarının türetilmiş olasılık yayımı açısından okunması | asistan salt okuma araştırması → karar kullanıcıda | **Plan B-2'den önce oku** (kapsam: türetilmiş olasılık, toplu döküm, olay kimliğinin `path_id` olarak kamuya açılması) | AK8'in kesinleşmesi, AK9 (b)/(c), AK20 (b), AK21 |
| AK18 | `site_reader` parolası + GitHub secret'ları (`SITE_DATABASE_URL`, `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`) | kullanıcı ekler (parola istemci tarafı SCRAM ile, §4.2) | Netlify kişisel erişim tokenı site başına kısıtlanamaz, hesabın bütün sitelerine yetkilidir → **yalnız bu siteyi barındıran ayrı Netlify hesabı/ekibi** | İlk gerçek dışa aktarım ve deploy |
| AK19 | **CSP ↔ Next.js satır içi betikleri** (App Router statik çıktısı her sayfaya satır içi RSC betiği basar; sunucu olmadığı için nonce yok; `script-src 'self'` hidrasyonu, 18+ kapısını ve yerel saati kırar) | (a) derleme sonrası satır içi betiklerin sha256'larını toplayıp `out/_headers` CSP'sine yazan adım · (b) `script-src 'self' 'unsafe-inline'` · (c) istemci betiklerini kaldırıp 18+'yı CSS/`<noscript>` ile çözmek (satır içi RSC betikleri yine kalır → (a) ya da (b) yine gerekir) | **(a)**; tarayıcı CSP'nin izin vermediği satır içi betik bulursa kırmızı. (a) ölçümde kırılgan çıkarsa (sayfa başına farklı hash listesi `_headers` boyutunu şişirirse) (b)'ye düşmek AYRI bir kullanıcı kararıdır | `_headers` üretimi, 18+ kapısı, B-2 |
| AK20 | **Slug kalıcılığı** (`site.yml` `contents: read` — dışa aktarımda dosyaya eklemek commit'lenemez; commit yolu seal botuyla yarışır; `commence_time` değişir) | (a) DB'de append-only `site_slugs` tablosu (yazarı boru hattı, okuyucusu `site` görünümü) · (b) maç yolu değişmez kimlikten (`path_id`) + kimlik altında joker yönlendirme; takım/lig slug'ları için önceki yayının `/data/slugs.json`ı depo sayılır: yeni derlemede kaybolan eski slug, depoda elle commit'lenmiş `config/site_redirects.yaml`da yönlendirmesi ya da `gone: <lig>` girdisi (pasifleşen lig, AK22) yoksa `site.yml` kırmızı; önceki yayın yoksa (ilk yayın) yalnız açık `--first-publish` ile geçer, site erişilemezse kırmızı · (c) elle commit'lenen slug dosyası + dışa aktarımda bilinmeyen slug → kırmızı | **(b)**: yeni tablo ve yazar gerektirmez; erteleme ve ad değişikliği maç URL'sini kırmaz; takım adı değişikliği nadir ve yayından önce kırmızıyla görünür. (c) her yükselen takımda yayını durdurur | §8.1 URL şeması, `site.yml` |
| AK21 | `/data/snapshot.json` toplu indirmesi | yayımla · yalnız hash yayımla | **Yalnız hash, AK17'ye kadar** (dosya bütün maçların türetilmiş oranlarının toplu dökümüdür). Bedeli adıyla: yayımlanmayan dosyanın hash'i doğrulama değil **taahhüttür**; bu süre boyunca §3.3'ün "anlık görüntü doğrulanabilir" iddiası kamu için değil yalnız bizim kapımız için geçerlidir ve sayfa bunu söyler (§6.1) | Sicil "indir" bağlantısı, kamu doğrulaması |
| AK22 | Veri saklama ve büyüme | tabandan beri her maç sonsuza dek · son N sezon | **Tabandan beri hepsi; anlık görüntü boyutu, derleme süresi ve tam zincir taraması süresi ölçülür, eşik aşılınca yeniden karar.** Pasifleşen lig her durumda düşer ve `config/site_redirects.yaml`da `gone: <lig>` girdisiyle kabul edilir (AK20 b ile tutarlı) | Derleme süresi, Actions dakikası, pasif lig URL'leri |

---

## 17. Öz-inceleme (2026-09-24, düzeltme turu 4 sonrası)

- **Yer tutucu dışında TBD yok:** açık kalanlar §16'da satır ya da plana bırakılan uygulama ayrıntısı (JSON Schema
  doğrulayıcı seçimi, imaj etiketi, CI süresi, HTML ayrıştırma sağlamlığı) olarak adıyla işaretli.
- **İç çelişki taraması:** B3 (şema = yayımlanabilirlik) ↔ B7 (kitap fiyatı yayımlanmaz) artık tutarlı:
  kitap bazında fiyat `site_input`te. H3 ↔ §7 ↔ B6 ↔ B5 tutarlı. H5 ↔ B2 ↔ §13 tutarlı. H6 ↔ §5.2 (türevler şemada)
  ↔ §5.4 (TS yalnız ayraç) tutarlı. Belirlenimcilik yalnız tek işlem içinde vaat edilir (B12, §6.4/3c); `sealed_at` ve
  `commence_time` değişkenliği yazılı. Holdout tabanı üç yerde aynı (B4, §4.3, H1) ve tek kaynaklı. Maç URL'si tarih
  taşımadığı için erteleme URL'yi kırmaz (§8.1, AK20). Pasif lig AK20(b) ↔ AK22 ↔ §8.1'de aynı `gone: <lig>` kuralıyla.
  "Uçtan uca" iddiası sicil için daraltıldı (§6.4/2, §12.4/12). Import bekçisi geçişli ve konsensüs yaprak modülde —
  `live.context` dışa aktarıcının kapanışında değil (H1f ↔ §4.3). Yasak anahtar kümesi açık ve `site` anahtarlarını
  dışlıyor (§4.3). Test yalıtımı tetikleyici kapatmadan, veritabanı düzeyinde; şablon pg_cron'suz alt küme, tam sıra
  `postgres`te geri alınan işlemde (§4.4/2, §4.4/4). Migration rolü her yerde `postgres` (§4.4/2 ↔ §4.2 `grant
  execute` iddiası). Girdi dökümü `site_audit`siz ve diske yazılmıyor (§5.1/4 ↔ B7 ↔ §4.3 yasak anahtar kümesi).
- **Kapsam:** tek plana sığmıyor → §15'te iki plan; ilk B-1; K1 testleri B-1'in kendi CI adımında koşar.
- **Bilinen varsayımlar (ölçülmedi):** CI servis kabında 0003–0005'in koşması; Netlify fiyat/limitleri; takım adı
  değişim sıklığı; pooler üzerinden rol GUC'leri; `path_id` önek uzunluğunun çakışmasızlığı (test onu yakalar); The
  Odds API olay kimliğinin ertelemede korunduğu; defter yazarlarının hepsinin `lock_ledger`dan geçtiği (plan testle
  bağlar); tam zincir taramasının defter büyüdükçe süresi.

---

## 18. Düzeltme turları — bulgu eşlemesi ve açık küçük noktalar

### 18.1 Tur 1 (`izb-spec-review.md`)

**Kapatılanlar:** C1 (§4.3 `site_audit.ledger_rows` `id` taşır; §6.4/3a parametreleme) · C2 (B12, §5.1, §6.4/3c) ·
I1 (B11, §4.1, §4.2 sahiplik etkileşimi, AK7) · I2 (B3, `site_input`, `book_key` cümlesi) · I3 (H1a iki küme, görünüm
başına süzgeç, `BEGIN ATOMIC` taban, import bekçisi H1f) · I4 (B5, H3c–d, §4.4/2 iki vaka) · I5 (§5.2 türevler, §5.4,
H6c) · I6 (H5d adım düzeyi, `persist-credentials`, `netlify-cli` sabit, AK18 notu) · I7 (§4.2 kaza önleyici,
`grant execute`, `security_barrier`) · I8 (AK19, tarayıcı CSP kontrolü) · I9 (AK20, §8.1 `path_id`, §8.2 ayrı slug
fonksiyonu) · I10 (§12.2 iki aşama, §15, §14 tarayıcı K1 süreci) · I11 (§4.4/3 uçtan uca, `CI=true` FAIL) · I12
(§1 çıpa sıklığı, §6.3 dürüst sınır, AK9, §6.5 zaman kanıtı) · I13 (§12.1 iki derleme varyantı, `_headers` tek
kaynak).
Minor'lar: M1 (B4 Londra, sınır tohumu), M2, M3 (`site.matches` ⋈ `site.leagues`, AK22), M4 (H4), M5 (§4.3 refactor),
M6 (`market.metrics.clv`), M7 (§6.4/3a atıf ve envanter), M8 (`date` UTC; tarih yoldan çıktı), M9 (tam etiket T0'da;
cron gürültüsü §4.4/2), M10 (H5c), M11 (§11 CLI dizini, `_redirects`/`_headers` `out/`ta, §6.4/3f `curl -I`), M12
(§5.3), M13 (AK15), M14 (başlık notu), M15 (§6.2), M16 (H7, §8.4), M17 (§4.2), M18 (§4.5, §5.1), M19 (§9), M20
(AK19–AK22; (e) tarih dilimi UTC olarak §5.2'de karara bağlandı), M21 (§4.2).

### 18.2 Tur 2 (`izb-spec-rereview.md`)
**Kapatılanlar:** N1 (§5.1/1 her çıpa + GENESIS'ten, `fetch-depth: 0`, §4.4/3 çıpa öncesi/sonrası iki kurcalama,
B12) · N2 (§4.4/3 elle hesaplanmış beklenen değerler, §6.4/2 daraltıldı, §12.4/12) · N3 (§5.1/4–5 girdi dökümü + ayrı
alt süreç + farklı `PYTHONHASHSEED`, §5.2 sıralı diziler ve `ledger._canonical`, §12.4/13) · N4 (`market/consensus.py`
yaprak modül, H1f geçişli bekçi, §4.3) · N5 (§4.3 açık yasak anahtar kümesi) · N6 (§4.4/4 şablondan taze veritabanı,
tetikleyici kapatma yasağı ve metin testi) · 0013 notu (§4.2 `grant execute` yük taşır, gerekçesiyle).
Minor'lar: m1 (§4.2 bekçi 3 DB dışı çıpaya bağlandı) · m2 (§12.1 uçtan uca JSON'un sabit yolu, `CI=true` FAIL) · m3
(H4 `data-fe-allow` özniteliği, iki katmanda sayım) · m4 (§8.1 zorlamasız 301, `gone: <lig>`, `--first-publish`,
`path_id` → AK17; AK20/AK22 tutarlı) · m5 (§6.1 taahhüt dili, sayfa `content_sha256` gösterir, AK21, §3.3) · m6
(§5.1 secret varlık kontrolü komutta, `fetch-depth: 0`, ATLANDI = kırmızı) · m7 (§5.4 ham hesap/çıktıda yuvarlama,
toplam sınanmaz; `indexable` Python'da, §8.4) · m8 (H1a temel tablolar, sabitlenmiş nesneler notu) · m9 (§5.3/7
JSON-LD hash listesi dışında). C2 analizinin `lock_ledger` önek varsayımı §5.1/3 ve §12.4/14'e; `\bLOGIN\b` yorum
notu §4.4/1'e; `_LEDGER_COLUMNS` tuple'ı §4.3'e yazıldı.

### 18.3 Tur 3 (`izb-spec-rereview2.md`)
**Kapatılanlar:** R1 (§4.4/4: şablonlu alt küme seçildi — 0001, 0002, 0013, 0014 şablonda, tam sıra `postgres`te geri
alınan tek işlemde; alt küme sadakati metin testiyle; (b)'nin neden seçilmediği yazıldı; §15 T0 ölçümleri) · R2
(§4.4/2 migration `postgres` rolüyle, `pg_get_userbyid(relowner) = 'postgres'`, `grant execute` mutasyon kanıtı) · R3
(§5.1/4–5 döküm içeriği `site`+`site_input`+çıpa+yapılandırma, `site_audit` yok, stdin, diske ve loga yok, iki
türetim aynı dökümden, `--out` = tam iki dosya testi; §4.3 `site_audit` tabansızlık cümlesi).
Minor'lar: r1 (§4.4/3 çıpa geçici git deposunda; §5.1/1 diğer iki indirgeme satırı da kırmızı) · r2 (§5.1/3 "commit'li
id'lerin öneki, boşluk olabilir") · r3 (§5.1/5 iki ayrı mutasyon) · r4 (§4.3 `Quote`/sabitler taşınır ve yeniden dışa
verilir, `"Avg"` yok; H1f yasak listeyle) · r5 (§4.4/4 metin testi kapsamı ve `test_runbook.py` istisnası) · r6 (§12.1
`RUNNER_TEMP` yedekli yol, başta boşaltma, `FE_VERIFY_RUN_ID` ile bayat dosya reddi) · r7 (§10.1 yasal metinler düz TSX).

### 18.4 Tur 4 (`izb-spec-rereview3.md`)
**Kapatılanlar:** I1 (§4.4/4 "dokunma" deyim hedefiyle; iki adlandırılmış istisna ve gerekçesi; testin kendi mutasyon
kanıtı) · n1 (kanıt ifadesi: 0001+0002 kanıtlı, 0013 analizle beklenir ve T0'da ölçülür) · n2 (§4.2 idempotent rol;
§4.4/4 oturum başında `site_tpl` ve `site_t_*` silinip yeniden kurulur, şablon ile (i) sıralı, (i) kum havuzu kilidi)
· n3 (§5.1/5 ≥ 32 adlı fixture + iki sabit tohumla önce sıra farkı; §12.4/13 olasılık notu) · n4 (§5.1/4 alt süreç
çıktısı yakalanır, adlandırılmış hata, redaksiyon testinde çöken çocuk vakası) · n5 (`sitedb` fixture'ları
`tests/site_db.py`de; metin testinin kapsamı dosya adıyla).

### 18.5 Açık küçük noktalar (plana bırakılan ölçümler)
1. `supabase/postgres` tam imaj etiketi ve kapta 0003–0005'in koştuğu — B-1 T0 (M9).
2. Bağımlılıksız HTML ayrıştırmanın sağlamlığı; kırılgansa tarayıcı kapsamı daraltılır ya da bağımlılık bilinçli
   eklenir (M12).
3. Supavisor kullanıcı biçimi ve rol GUC'lerinin pooler üzerinden uygulanması — 0014 uygulama adımında (M18).
4. `*.netlify.app` alt alanının `noindex`ini `_headers` ile mi kanonik etiketle mi sağlamanın en sağlam olduğu —
   Netlify davranışı ölçülür (M16).
5. `path_id` önek uzunluğu (çakışma testiyle seçilir) (AK20).
6. Netlify'da `gone: <lig>` girdisinin 404 mü 410 mu sunduğu (§8.1).
7. JSON Schema doğrulayıcısı (`jsonschema` bağımlılığı ya da el yazımı) (§5.2).
8. B-1 T0 listesi (§15): `postgres` rolünün `CREATEDB`i, şablon kopyası, `postgres` veritabanında tek işlemde geri
   alınan tam sıra (R1, R2).
