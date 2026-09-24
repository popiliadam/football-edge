# Faz 6 İz B — HANDOFF (B-1: okuma katmanı)

Spec: `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md`. Plan: `docs/superpowers/plans/2026-09-24-faz6-iz-b-1-okuma-katmani.md`.
T0 ölçümleri: `docs/phases/06-site/b1-t0-olcumler.md` (ölçen komut `scripts/site_t0_probe.sh`).

## B-1'in kurduğu

- `db/migrations/0014_site_read.sql` — `site_reader` (NOLOGIN), `site`/`site_input`/`site_audit` görünümleri,
  `site.public_floor()`. **Canlıya UYGULANMADI.**
- `python -m football_edge.site export | verify-snapshot` — tek salt okuma işlemi, tam zincir, ikinci türetim. Çıkış
  kodları `src/football_edge/site/contract.py`: 20 yapılandırma, 21 zincir/çıpa, 22 kesim/görünüm/taban/sicil,
  23 ikinci türetim farklı, 24 `verify-snapshot` kırmızı.
- Kapı: `verify.sh` `site-db` adımı (`sitedb` testleri; alt sınırlar `EXPECTED_MIN_SITEDB=28`,
  `EXPECTED_MIN_SITEDB_LEAKAGE=4`; `sızıntı` adımı `EXPECTED_MIN_LEAKAGE=442` — Task 9'da `--collect-only` ile ölçüldü)
  ve koşu kimliği `FE_VERIFY_RUN_ID`. CI'da iş içinde doğan `supabase/postgres` kabı (aynı kap 0013 kum havuzu
  testlerini de koşar; `CI=true` iken `SANDBOX_DATABASE_URL` yoksa kum havuzu testleri atlanmaz, kırmızı verir);
  kabın logu CI'da basılmaz (derinlemesine savunma: imaj parolayı oraya düz metin yazar).
- `.github/workflows/site.yml` — yalnız `workflow_dispatch`; üç iş: `build` (dışa aktarım, derleme, çıktı tarayıcısı) →
  `deploy` (yalnız `main`, `environment: production`, Netlify kimliği yalnız yayın adımında) → `live`. Secret'lar
  eklenmedi. **Yayın kapıları (kaybolan-slug, yayın sonrası kontrol) ve `netlify deploy`un `--no-build`u B-2 Task
  10'undur** (controller kararı; yerleri `site.yml`de `B-2 T10 →` yorumlarıyla işaretli): B-1 sonunda `site.yml` bu
  kapılardan yoksundur ve `--no-build` olmadan netlify-cli `web/netlify.toml`daki bilerek düşen derlemeyi koşar —
  secret'lar eklenmeden ve B-2 T10 birleşmeden koşulmaz.
- Lig URL bölütleri `config/site_leagues.yaml`da, KALICI (addan türetilmez; `ger.1`/`aut.1` ikisi de "Bundesliga").
- Türetim yalnız maç öncesi satırları kullanır (kapanış satırı tam başlama anında da). Ölçüm (controller, canlı, salt
  okuma): `odds_snapshots`ta `observed_at >= matches.commence_time` olan 51 satır, hepsi 1 maçta (5.763 satırda).

## B-1 → B-2 devri (B-2 yalnız bunlara dayanır)

- **Anlık görüntü sözleşmesi v1:** `web/contract/snapshot.schema.json` (spec §5.2'nin alanları; her nesnede
  `additionalProperties: false`; `schema_version: 1`, `floor: "2026-07-02T00:00:00Z"`, `value_badge`/`analysis`
  `const: null`). Diziler: `leagues` `id`, `teams` `(league_id, slug)`, `matches` `(commence_time, id)`,
  `record.entries` `publication_id` ile artan. Sayılar görüntü hassasiyetinde (olasılık/hareket/dağılım yüzde puanı
  1 ondalık; `clv`, `mean_clv`, `ci_*` yüzde 2 ondalık; fiyatlar 2 ondalık): TS yalnız ondalık ayracı ve birim ekler.
  `content_sha256` = `generated_at`, `git_sha`, `content_sha256` hariç gövdenin `json.dumps(sort_keys=True,
  separators=(",", ":"), ensure_ascii=False)` UTF-8'inin sha256'sı — sicil sayfası dosya hash'ini değil bunu gösterir.
- **Sentetik fixture'lar:** `web/fixtures/snapshot.fixture.json` (boş sicil; mühürsüz, tek turlu, eşik altı turlu maç;
  dolu ve boş `move_distribution`; indekslenebilir ve olmayan takım/maç) ve `web/fixtures/snapshot.fixture-record.json`
  (aynısı + iki yayınlı, özetli sicil). İkisi de `verify-snapshot`tan geçer.
- **`verify-snapshot` CLI:** depo kökünden `uv run python -m football_edge.site verify-snapshot <snapshot.json>
  [--sha256 <snapshot.sha256>]` → geçerliyse exit 0 ve `anlık görüntü geçerli: <ad>`; değilse exit 24 ve her ihlal
  için `ANLIK GÖRÜNTÜ İHLALİ: <$.yol>: <kural>` (değer basılmaz).
- **Dışa aktarım çıktısı:** `site export --out <dizin>` dizinde TAM OLARAK `snapshot.json` (kanonik JSON + `\n`) ve
  `snapshot.sha256` (`<64 hex>  snapshot.json\n`). `site.yml` bunu `web/.snapshot/`a yazar (`.gitignore`'da).
- **Uçtan uca anlık görüntü:** `verify.sh` başta `FE_VERIFY_RUN_ID`i dışa verir; `site-db` bloğundan önce
  `SITE_E2E_DIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e"`i dışa verir ve `snapshot.json`, `snapshot.sha256`, `run-id`
  dosyalarını SIFIRLAR (silmez). Uçtan uca test (`tests/test_site_e2e_db.py`) üçünü yazar; `run-id` içeriği
  `FE_VERIFY_RUN_ID`e eşittir (satır sonu yok). Test DB'si yoksa dosyalar boş kalır → B-2'nin derleme adımı
  `run-id` ≠ `FE_VERIFY_RUN_ID` gördüğünde yerelde SKIP, `CI=true` iken FAIL (§12.1).
- **`verify.sh`teki çapalar (B-2 T10 Step 1'in ölçtüğü):** iki girintili `step "site-db"` satırı (`if` ve `elif`
  dalları), `export FE_VERIFY_RUN_ID`, `export SITE_E2E_DIR`; `site-db` bloğu sütun 0'daki `fi` ile kapanır ve
  `zincir` bloğundan öncedir — B-2'nin bloğu o `fi`nin hemen ardına girer. `ci.yml`de `- run: uv sync --frozen
  --extra scrape` satırı değişmedi (Node adımları onun ardına); "Site test veritabanı" adımı da onun ardındadır —
  B-2'nin iki adımı `./verify.sh`ten önce kaldıkça sıra testleri ikisini de kabul eder. `Kapı` adımının yorum listesi
  bugün "on bir adım … `site-db` …"dır. `timeout-minutes: 20` (B-2 T10 Step 11 bunun üstüne ekler).
- **B-2'nin yükümlülükleri (B-1 yapmadı):** şema ↔ TS `Snapshot` tipi anahtar eşitliği pytest'i (Q23); `site.yml`in
  kaybolan-slug ve yayın sonrası kontrol adımları ve `--no-build`; Node adımlarını `verify.sh`in `site-db` adımından
  SONRA eklemek; `verify.sh`e eklenen her `uv run pytest` çağrısı `--tb=short` taşımalı (`tests/test_gate_traceback.py`
  sayımı — bugün `verify.sh` 4 — güncellenir) ve `sitedb`i adıyla seçmeli/dışlamalı ya da `-m contract` olmalı
  (`test_the_gate_runs_sitedb_tests_only_where_it_names_them`); `ci.yml`e hiçbir adımda `docker logs` ya da
  `-f`siz `docker inspect` girmez (`test_ci_never_prints_the_container_log`); `site.yml`e dokunurken `test_site_workflow.py`nin secret sınırı ve sıra
  testleri yeşil kalmalı. `web/fixtures/`e B-2'nin kendi fixture'larını eklemesi serbesttir (B-1'in testi kapsayıcı
  değil, varlık sınar). Not: dışa aktarımın `snapshot.sha256`i `sha256sum` biçimindedir (`<hex>  snapshot.json`);
  yayındaki `/data/snapshot.sha256`in biçimi B-2'nindir — §6.4/3f karşılaştırması ikisinin hex alanını kıyaslamalıdır.
- **B-2 T10 Step 10'un beklenen çıktısı değişti:** `CI=true` ve test DB'si yokken kapı `FAIL: site-db` ve B-2'nin
  `FAIL: site-e2e`sinin yanında **`FAIL: pytest`** de basar — 0013'ün kum havuzu testleri `CI=true` altında
  atlanmaz, `SANDBOX_DATABASE_URL` yokluğunda hata verir (Faz 6 B-1 Task 9 düzeltme turu 1). Beklenen liste bu
  satırla okunmalı.

## B-2 T10 — site kapısı `verify.sh`/`ci.yml`de, `site.yml` yayın kapıları

- **Kapı komutu:** `source ~/.nvm/nvm.sh && nvm use 24.21.0 && TMPDIR=$(mktemp -d) ./verify.sh > <log> 2>&1`. Site
  adımları (`site-db`den sonra): `site-kurulum` (`scripts/site_gate.sh install`: Node ana sürümü `web/.nvmrc`,
  pnpm ana sürümü `packageManager` ile eşit değilse ya da biri yoksa FAIL — SKIP yok) · `site-tip` · `site-lint` ·
  `site-test` · `site-derleme` (her varyant önce `verify-snapshot`, sonra `pnpm -C web run build`; çıktı koşunun
  `mktemp -d` dizinine kopyalanır) · `site-uyum` (`check-out.ts` her varyanta). Altısı da `scripts/site_gate.sh`in
  alt komutudur. Varyantlar: `fixture-full`, `fixture-full-indexable`, `fixture-empty` + bu koşunun uçtan uca JSON'u
  (`run-id` = `FE_VERIFY_RUN_ID`; yanındaki `snapshot.sha256` ile doğrulanır). `CI=true` iken `build`/`check` uçtan
  uca varyantı işlemediyse kendileri de kırmızıdır (düzeltme turu 1, I1).
- **Node araçlarının ortamı (controller kararı, düzeltme turu 1 I4):** `pnpm`/`node` `env -i` ile yalnız `PATH`,
  `HOME`, `TMPDIR`, `CI`, `PNPM_HOME`, `NEXT_TELEMETRY_DISABLED`, `SITE_SNAPSHOT`, `SITE_INDEXABLE` (+ sabit
  `NO_COLOR=1`) görür; kabuğun DB adresleri, API anahtarları ve Netlify kimliği geçmez (sahte araçlarla testli).
  Python adımları (`verify-snapshot` dâhil) ortamı olduğu gibi alır. Bağlantı `tests/test_site_web_gate.py`de sahte
  `uv`/`pnpm`/`node` ile ve `verify.sh` bloğu baytla sabittir.
- **Kipler (ölçüldü, B-2 T10 raporu, düzeltme turu 1):** (a) yerel DB'siz → 16 PASS + `SKIP: site-db`,
  `SKIP: site-derleme/e2e (…)`, `SKIP: zincir`, `KAPI YEŞİL`; (b) `CI=true` DB'siz → `FAIL: pytest`, `FAIL: site-db`,
  `FAIL: site-e2e` (`FAIL CI=true ve bu koşunun uçtan uca anlık görüntüsü yok ya da bayat …`), `FAIL: site-derleme`,
  `FAIL: site-uyum` (`HATA: CI=true ama uçtan uca varyant işlenmedi …`), `KAPI KIRMIZI`; (c) kum havuzu kabıyla ve
  (d) `CI=true` + kum havuzu kabı (CI'ın kipi) → 17 PASS + `SKIP: zincir`; dört `check-out: … 0 bulgu` (fixture 46
  sayfa, uçtan uca 34).
- **CI:** `pnpm/action-setup@v4` (`package_json_file: web/package.json`) → `actions/setup-node@v4`
  (`node-version-file: web/.nvmrc`, pnpm önbelleği) `uv sync`ın ardında. `timeout-minutes: 25` = 20 + max(5,
  ⌈2·16/60⌉): site adımları yerelde sıcak önbellekle 16 sn (dört derleme). CI tabanı (9ceb874) ~2 dk 24 sn; soğuk
  pnpm kurulumu ve `.next` önbelleksiz derleme ilk push'ta ölçülür — süre 25 dk'nın %70'ini (17,5 dk) aşarsa yeniden
  ölçülür.
- **`site.yml`:** `workflow_dispatch` girdisi `first_publish` (boolean, varsayılan `false`). `build` işinde tarayıcıdan
  sonra, yayın paketinden ÖNCE `scripts/site_publish.py slugs` (önceki yayının `/data/slugs.json`ı ↔ yeni
  `web/out/data/slugs.json`; kaybolan her slug `config/site_redirects.yaml` `gone:`/`renamed:`da kabul edilmeli);
  `deploy`un yayın komutu `--no-build` taşır; `live` işinin sonunda `scripts/site_publish.py live` (canlı
  `/data/snapshot.sha256` = derlenmiş = dışa aktarılmış; örnek sayfaların CSP'si ve `X-Robots-Tag: noindex`i derlenmiş
  `_headers`le aynı). İki adım secret'sız.
- **Bilerek kırmızı:** `web/site.config.ts` `SITE_URL` yer tutucu (`https://example.invalid`) iken iki yayın kapısı da
  ağa çıkmadan kırmızıdır (AK4 kararı yok; testli). İlk yayın `first_publish: true` ile ve YALNIZ site önceki
  `/data/slugs.json` için gerçek bir **404** döndürdüğünde geçer (controller kararı m1); bağlantısızlık (HTTP 0), 403,
  410 ve 5xx kırmızıdır — alan adı önce Netlify'a bağlanıp yanıt verir hâle getirilir.
- **Ölçmedikleri (B-2 T10):** `site.yml` hiç koşmadı (`slugs`/`live` yalnız sahte `get`/`head` ile sınanır;
  netlify-cli `--no-build` gerçek CLI'da koşmadı); CI'daki soğuk süre; kabul edilen `renamed:` eşlemesi `_redirects`e
  yazılmaz (eski URL 404 — plan açık küçük nokta 1); `live` örnek olarak `_headers`teki sayfa yollarının sözlük
  sırasında ilk, orta ve son öğesini okur (bugün `/en/`, `/tr/`, `/tr/track-record/` — maç, lig, takım sayfası
  örneklenmez); izin listeli ortam yalnız Node araçlarını kapsar (Python adımları ve `uv` kabuğun ortamını görür);
  `timeout-minutes` testle sabit değildir (ölçülmüş değer, kapı değil).

## Canlıya geçiş (kullanıcı onayı, §0.7 — bu dalga YAPMADI)

1. 0013 canlıda + advisors temiz (controller).
2. AK6 onayı → `0014` ROLLBACK'li prova → `apply_migration` (uygulayan rol `postgres` olmalı: görünüm sahibi = tablo
   sahibi, aksi hâlde RLS'li tablolar görünümden HATASIZ 0 satır döner — §4.2) → katalog testleri gerçek DB'ye karşı
   salt okuma kipinde → Supabase advisors 0014'ten SONRA da okunur (spec §4.2; üç şema API'ye açık şemalara
   eklenmemiş, `security_invoker` uyarısı yok).
3. **`site_reader`a `LOGIN` verilmeden ÖNCE — pg_net artık riski (kullanıcı kararı, bilerek verilir):**
   - Canlıda `site_reader`ın etkin yetkileri salt okuma sorgusuyla yeniden ölçülür, pg_net'in `net` şeması dâhil
     (şema USAGE'ı; `net.*` tablo, dizi ve fonksiyon yetkileri). Kapta ölçülen kabul listesi:
     `tests/test_site_views_db.py` `PG_NET_RELATIONS`/`PG_NET_FUNCTIONS`; liste dışı her yetki durdurur.
   - Kullanıcıyla teyit edilir: Supabase panelinde API'nin "Exposed schemas" listesinde `net` YOK (§0.7).
   - Kullanıcı artık riski açıkça kabul eder: `LOGIN`li `site_reader` `net.http_post` ile veritabanı sunucusundan
     dışa HTTP isteği atabilir, `net.http_request_queue`yu okuyup yazabilir — bu kuyruk pg_cron dispatch'lerinin
     Bearer GitHub tokenını taşır. `postgres` `supabase_admin`in PUBLIC yetkilerini geri alamaz (Task 3'te kapta
     ölçüldü); `default_transaction_read_only` yalnız kaza önleyicidir, sınır değildir. Kabul yoksa `LOGIN` verilmez.
4. RUNBOOK'a `site_reader` parola/`LOGIN` adımı: parola kullanıcı tarafından istemci tarafı SCRAM ile (`\password
   site_reader`); asistan parolayı görmez ve girmez (AK18).
5. Ölçülecek: Supavisor kullanıcı biçimi (`site_reader.<proje_ref>`) ve rol GUC'lerinin pooler üzerinden uygulandığı (§4.5).
6. Secret'lar: `SITE_DATABASE_URL`, `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID` (ayrı Netlify hesabı/ekibi — AK18), ortam
   kapsamlı; GitHub'da `production` ortamının dağıtım dalı `main`e sınırlanır (kullanıcının depo ayarı).
   **`SITE_DATABASE_URL` ortam kapsamlı bir secret OLMALIDIR:** depo kapsamlı secret'ı her dalın workflow koşusu
   okuyabilir ve bu kimlik bilgisinin erişimi 3. adımdaki kadardır. Bugün `site.yml`in `build` işinde `environment:`
   YOKTUR: ortam kapsamlı secret `build`e görünmez ve dışa aktarım exit 20 ("`SITE_DATABASE_URL` yok") ile durur.
   Bu yüzden secret eklenmeden önce `build` işine dağıtım dalı `main`e sınırlı bir `environment:` eklenir (bu dalga
   eklemedi; değişiklik `tests/test_site_workflow.py`de mutasyon kanıtlı bir testle sabitlenir, Task 8 testleri
   yeşil kalır).

## Kapının ÖLÇMEDİKLERİ (B-1)

Tam liste bu bölümdür (19 madde). 1–13 planın "Kapının ölçmedikleri (bu plan)" bölümünün andığı on üç maddedir;
14–16 Task 6–9 incelemelerinden, 17–19 bütün-dal son incelemesinden sonra eklendi. Plan dosyası değiştirilmedi: oradaki "on üç" sayısı yazıldığı anın
listesidir, güncel liste burasıdır.

1. Gerçek veriyle sayfa ↔ defter uyuşması: `site.yml` hiç koşmadı (secret yok) — sentetik veride her push'ta ölçülür.
2. Canlı DB'de görünümler ve yetkiler (0014 uygulanmadı); CI kabı Supabase'in canlı rol/varsayılan yetki kurulumunun
   birebir kopyası değildir; pooler üzerinden rol GUC'leri ve oturum saat dilimi (dışa aktarım UTC dışı oturuma
   dayanıklı — Review Focus 1 — ama pooler davranışı ölçülmedi).
3. Davranış testleri `site_reader`a `SET ROLE` ile geçer: LOGIN'li bir oturumun rol GUC'leri
   (`default_transaction_read_only`, `statement_timeout`) yalnız katalogda sınanır, oturumda koşmaz. Test kümesi
   `postgres`e `site_reader` SET üyeliği verebilir (yalnız atılabilir kapta; üretimde yok).
4. Şablon alt kümesinin sadakati bir KARA LİSTEDİR (deyim hedefli): listede olmayan deyimi ve çalışma anında dinamik
   SQL'le yapılan değişikliği ölçmez (rereview4 m2).
5. Dolu sicilin defter tarafı (görünüm → dışa aktarıcı → CLV yeniden hesabı) yalnız sahte görünümlerle sınanır;
   kapta uçtan uca yalnız BOŞ sicil koşar (§12.4/12).
6. Belirlenimcilik kontrolü küme sırası hatasını üretimde OLASILIKLA yakalar (tohumlar rastgele); testte iki sabit
   tohumla kesin (§12.4/13). İşlemler arası (DB değiştikten sonra) yeniden üretilebilirlik vaat edilmez.
7. Kesim tutarlılığı defter yazarlarının `lock_ledger`la serileştiği varsayımına dayanır; bekçi `src/`, `scripts/`,
   `db/migrations/` metnini tarar — canlıya elle SQL ile yazan bir yazarı durdurmaz (§12.4/14).
8. Tam zincir taramasının süresi defter büyüdükçe uzar; ölçülmez (AK22).
9. `verify-snapshot`in H1 tarama kuralı `YYYY-MM-DD` kalıbıdır; başka biçimde yazılmış bir tarihi görmez.
10. `site.yml`in Node adımları (B-2) ve netlify-cli (27.8.1, `npm install --global`) koşmadı; test yalnız secret
    sınırını, sırayı ve sürüm sabitlemesini ölçer. Sabitleme yalnız üst paketi kapsar; geçişli bağımlılıklar koşu
    anında çözülür ve Netlify kimliğini gören kod netlify-cli'nin bağımlılık ağacıdır (spec kabul ediyor; bağlanırken
    yeniden bakılır). Workflow düzeyi `env` (ör. `NODE_OPTIONS`) ve `deploy.runs-on` testle sabitlenmedi (T8 R1).
11. Task 3–8 birleşmeleri arasında `sitedb` testleri CI'da koşmadı (Task 9'da başladı); o pencerede kanıt yereldir
    (görev raporları).
12. Maç içi süzgeci `observed_at < commence_time`a dayanır; `observed_at` turun BAŞLADIĞI andır (`now`), ligin çekildiği
    an değil. Uzun bir turda başlamadan saniyeler–dakikalar sonra çekilen bir lig başlamadan önce damgalanır ve süzgeçten
    geçer. Defter hep böyleydi; sitenin "in-play yok" iddiası bu damgaya dayanır, çekim anını ölçmez.
13. Başlama saati öne kayarsa (`commence_time` UPSERT'le erkene çekilir) sitenin sicil kontrolü (`record_mismatches`)
    maç öncesi kapanışı, Faz 5'in `market/bridge.py`si ise her `is_closing` satırını seçer; ikisi farklı kapanış
    satırı seçebilir ve o maçta bir yayın tüm dışa aktarımı exit 22 ("kapanış konsensüsü yok") ile durdurur. Bugün
    `site.record` `where false`tur; Faz 5 sicili bağlarken bakılacak ileri nottur.
14. En yeni çıpadan SONRAKİ tutarlı yeniden yazım (kuyruk yeniden zincirlenir) yayımlanır — tasarımın doğal sınırı;
    kanıt penceresi çıpa sıklığıdır (günlük `publish-head`). Yazımın atomikliği yalnız "yazım anında `--out` yok" ile
    ölçülür; `rename`in çökme güvenliği (fsync) ölçülmez (Task 6 M2).
15. Gizli koşul: tabandan SONRA başlayan bir maçın oranı tabandan ÖNCE gözlenmişse `verify-snapshot` H1 kuralı o tarihi
    reddeder ve dışa aktarım tümüyle exit 24 ile düşer (Task 7 yeniden incelemesi, kapta üretildi). Canlı ölçüm (salt
    okuma): bugün böyle satır 0 — defter 2026-09-19'da başlıyor, geri doldurma yok. Geri doldurma yapılırsa önce bu
    karar açılır (görünümde `observed_at >= taban` süzgeci tek satır).
16. CI kabının soğuk imaj çekme süresi (1,8 GB) ilk CI koşusundan önce ölçülmedi; `timeout-minutes: 20` bu yüzden
    tabandır. Kap kalkmazsa CI yalnız kabın durumunu basar (log parolayı düz taşır; maske en iyi çaba korumasıdır,
    log derinlemesine savunma olarak hiç basılmaz): nedeni için yerelde `scripts/sandbox_db.sh up` ile yeniden
    üretilir.
17. pg_net artık riski: `site_reader`ın `net` erişimi yalnız kapta ölçülür (kabul listesi,
    `tests/test_site_views_db.py`). Canlıdaki etkin yetkiler, panelin "Exposed schemas" ayarı ve `LOGIN`li bir
    oturumun `net.http_post`/`net.http_request_queue` erişimi ölçülmez — Canlıya geçiş 3. adımında ölçülür ve
    kullanıcı kararıdır.
18. H2c bir alt dize kuralıdır (`http`, `<`, `>`, büyük/küçük harf duyarsız): `hxxp`, `www.`, şemasız `//host`,
    Unicode benzeri harfler (tam genişlikli, Kiril), sıfır genişlikli boşluk, yüzde kodlama (`%3C`) ve HTML
    varlıkları (`&lt;`) geçer (`site/verify.py` docstring'i, T4 M3). Kuralı genişletmek spec kararıdır.
19. Yinelenen JSON anahtarı: `verify-snapshot` sonuncu değeri alır ve exit 0 verir (T4 M4). B-2'nin `JSON.parse`ı da
    sonuncuyu aldığından iki taraf aynı nesneyi görür; gizli yük yalnız dosya baytlarında kalır. Ham `snapshot.json`
    yayımlanmadığı sürece etkisizdir; bir gün `out/`a girerse H1/H3/§4.3 denetimi o baytları görmez.

## Kapının ÖLÇMEDİKLERİ (B-2)

Tam liste bu bölümdür. 1–10 planın "Kapının ölçmedikleri (bu plan)" (a)–(j) maddeleridir (plan metni değiştirilmedi);
11–17 görev incelemelerinin "sınır" diye bıraktıkları ve bütün-dal son incelemesinin eklediğidir. T10'un yerel maddeleri
yukarıda "Ölçmedikleri (B-2 T10)" satırındadır. Ertelenen küçük düzeltmeler `docs/DEFERRED.md` §20'dedir.

1. (a) CSP'nin tarayıcıda gerçekten uygulandığı ve istemci betiklerinin (18+, yerel saat) CSP altında çalıştığı —
   yalnız hash eşleşmesi ölçülür (§12.4/8).
2. (b) Netlify'ın `_headers`/`_redirects`i gerçekten uyguladığı, `*.netlify.app` alt alanının `noindex`i (§18.5/4) ve
   pasif lig için 404/410 (§18.5/6) — Netlify hesabı olmadan ölçülemez. Aynı yol için iki `_headers` kuralının
   Netlify'da nasıl birleştiği ve sondaki eğik çizginin (`/en` ↔ `/en/`) hangi bloğa eşlendiği de ölçülmedi (T8 M4/M5);
   `check-out` iki kuralı birleştirerek okur, `live` kapısı yalnız üç örnek sayfayı okur.
3. (c) Next'in `404.html`/`_not-found` sayfaları `_headers`te CSP almaz ve Next'in satır içi `<style>`ını taşır
   (Netlify 404 yanıtında yalnız `/*` başlıkları uygulanır; `/*`e CSP konamaz — sayfa CSP'leriyle kesişir).
4. (d) `config/site_redirects.yaml`de KABUL edilen takım yeniden adlandırmaları `_redirects`e yazılmaz — eski URL 404
   verir (plan açık küçük nokta 1).
5. (e) H4 kalıp listesidir, listede olmayan ifadeyi yakalamaz — Türkçe çekimli biçim de kaçabilir; H1 yalnız tarih
   kalıbı tarar (§12.4/4–5).
6. (f) `_headers` boyutu sayfa sayısıyla doğrusal büyür. **AK19 ölçümü** (son inceleme, bu dalgada yeniden ölçüldü):
   fixture 17 593 B (≈17,6 KB, 46 sayfa; `fixture-full-indexable` 17 569 B), uçtan uca anlık görüntü 12 471 B
   (≈12,5 KB, 34 sayfa); T8'in ölçtüğü eğim ≈ 176 + 379 × sayfa bayt. Eşik aşılırsa AK19 (b) kullanıcı kararıdır.
7. (g) Görsel düzen, duyarlı tasarım, tam erişilebilirlik (axe), çeviri kalitesi, yasal metinlerin doğruluğu
   (§12.4/6–8, /10).
8. (h) TS'in sayı hesaplamadığı yalnız dolaylı ölçülür: basılan her sayı anlık görüntüde birebir karşılık bulmalıdır
   (H6c); `data-fe`siz basılan sayı tarayıcıdan kaçar (sayfa kodu incelemesi, T5/T6).
9. (i) Sicil tablosundaki sonuç ETİKETİ (takım adı / "Beraberlik") tarayıcıda ölçülmez — tarayıcı yalnız ham
   `outcome` özniteliğini sınar; eşlemenin doğruluğu `outcome.test.ts` birim testindedir.
10. (j) Çıpa geçmişi bağlantısı yer tutucudur (`LEDGER_HISTORY_URL` deponun `ledger/` dizininin geçmişine işaret
    etmeli; sayfa ona çıplak `head-YYYY-MM-DD.txt` ekler) — bağlantının çözüldüğü ölçülmez.
11. TASLAK işaretinin CSS ile gizlenmesi (T7): `check-out` yalnız işaretin ve atalarının SINIF seçicilerinde, bağlı
    stil dosyalarındaki `display:none`/`visibility:hidden`ı görür. Başka gizleme biçimi (`opacity:0`, `clip`/
    `clip-path`, ekran dışı konum, `font-size:0`, zeminle aynı renk) ve öğe/öznitelik/kimlik seçicisiyle gizleme
    ölçülmez. Satır içi gizleme (`hidden`, `style`, `aria-hidden`, `<template>`) HTML'de yakalanır.
12. 18+ penceresinin tarayıcı davranışı (T7): açılma, onay kaydı, odak, Esc'in pencereyi kapatmaması, 375 px'de
    `box-sizing: border-box` ile taşmama, `openGateIfNeeded(null, …)` ve `onCancel` bağlantısı. `border-box` silme,
    null pencere ve `onCancel` silme mutasyonları yeşil geçer (DOM test ortamı yok, spec §13); davranış T7 yeniden
    incelemesinde bir kez gerçek Chromium'da ölçüldü, kalıcı değil. `check-out` yalnız durağan işaretlemeyi sınar.
13. JSON dizesinde kaçışlı eğik çizgili URL (`https:\/\/tracker.example\/x`) bir cümlenin içindeyse (satır içi itiş,
    `.txt`, JSON-LD `description`) ham host taraması görmez (T9 B3). Tam bir URL dizesi olarak `rscLinks`/JSON-LD
    bağlantı denetimi yakalar.
14. CSS `content` okuması üç biçimi kaçırır (T9 B5): onaltılık CSS kaçışları (`\6e`), birden çok dize
    (`"Pinn" "acle"`) ve `attr(data-x)` (`data-*` öznitelikleri metin yüzeyinde değil). Site `attr()` kullanmıyor.
15. JWT kalıbı yalnız bitişik biçimi arar (T9 B6, FP2 daraltmasının bedeli): satır kırılarak birleştirilmiş dize,
    `&#46;` ile yazılmış nokta ya da satır kırmalı JWT geçer. Paketleyici ortam dizesini bitişik gömer.
16. İzinli cümle kendi başına durduğu sürece çıkarılır; ÖNCEKİ bir cümlenin anlamı çevirmesi ("Aşağıdaki cümle
    yalandır." + sorumluluk reddi) ölçülmez (T9 x23) — cümle düzeyi izin listesinin sınırı, mekanik çözümü yok.
17. Node araçlarının izin listeli ortamı yalnız ortam DEĞİŞKENLERİNİ kapsar, diski kapsamaz (son inceleme m6):
    `pnpm install` ya da `next build` sırasında koşan bağımlılık kodu, ana checkout'ta duran repo kökündeki `.env`i
    (gitignored) diskten okuyabilir. Worktree'de ve CI'da `.env` yoktur.

## Hukuk incelemesi (HANDOFF §0.7/7'ye)

B-2 Task 7 incelemesinin "Content findings for lawyer review" tablosu (C1–C11; inceleme dosyası gitignored SDD
kaydındadır). Hiçbiri hukuki görüş değil; yasal taslaklar TASLAK işaretiyle, `noindex` ve site haritası dışında durur.
AK13 avukat paketine girer. Belgeler: `web/content/legal/<dil>/<belge>.tsx`.

| # | yer | konu | soru |
|---|---|---|---|
| C1 | en/tr terms | Defterin "kamuya açık" olduğu olgusu | T7 düzeltme turunda metin "yalnız baş hash'lerini yayımlıyoruz" oldu (defter satırları kamuya açık değil). Avukat son hâli teyit etsin |
| C2 | en/tr privacy | "Kişisel veri toplamıyoruz" | T7 düzeltme turunda ziyaretçiyle sınırlandı ve iki `[AVUKAT SORUSU]` eklendi: barındırıcının erişim kayıtlarındaki IP'ler bizim işlediğimiz veri mi; operatörün haber hattı (sakatlık = sağlık verisi mi, §0.7/7) |
| C3 | tr privacy başlığı (`legal.privacy`) | "KVKK aydınlatma metni ve gizlilik" | Başlık KVKK md. 10 aydınlatma metni vaat ediyor; metinde veri sorumlusunun kimliği/iletişimi, amaç ve hukuki sebep, md. 11 hakları ve başvuru yolu yok (marka ve tüzel kişi AK3'e bağlı). Bu başlıkla hangi unsurlar zorunlu? |
| C4 | en/tr cookies | "Zorunlu yerel depolama" nitelendirmesi | Hukuki bir nitelendirme (ePrivacy 5(3) istisnası ya da muadili; spec §10.1). 18+ penceresi çerez/gizlilik metnine bağlantı vermiyor, tam ekran örtü onaydan önce metinleri okumayı engelliyor. Depolamadan önce bilgilendirme gerekir mi? |
| C5 | en/tr sorumlu oyun · `footer.responsible` | "Sınır koyun…" ve "sorumlu oynayın" dili | Metin okurun bahis oynadığını varsayıyor ve bahsi eğlence olarak çerçeveliyor. Türkiye'de yalnız devlet lisanslı bahis yasal (7258). Bu dil normalleştirme sayılır mı? (spec §10.3) |
| C6 | en sorumlu oyun | "Ülkenizde yardım var" genel iddiası | Doğrulanmamış; liste yalnız UK ve TR. Koşullu ifade ya da `[DOĞRULANACAK]` mı? |
| C7 | en/tr sorumlu oyun | Yeşilay ve YEDAM `[DOĞRULANACAK]` | Kurum adları da birincil kaynaktan doğrulanmalı; UK için hangi kuruluş anılacak (GambleAware / National Gambling Helpline)? |
| C8 | en cookies · en privacy | "Çerez yok, analitik yok" | Bugün derlenmiş sitede doğru; barındırıcının çerezi, log saklama süresi, analitik ya da form özelliği açılırsa yanlış olur. Deploy sonrası yeniden doğrulanmalı (§12.4/9) |
| C9 | en terms | "Bahis sitesi fiyatlarından türetilmiş" | Veri kaynağının (The Odds API) koşullarının türetilmiş olasılığın yayınına izin verip vermediği açık (AK17, §12.4/11) |
| C10 | en/tr privacy | Yurt dışından sunmak sınır ötesi aktarım mı | Barındırmanın yurt dışında olacağını varsayıyor; barındırıcı kararına bağlı. Soru olarak işaretli |
| C11 | en/tr terms | "18 yaş ve üzeri yetişkinler için" | 18 eşiği ve yaş doğrulaması olmaması (§12.4/6) hedef ülkeler için yeterli mi? Her yeni dil ayrı çerçeve (§10.3) |
