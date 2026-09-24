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
  testlerini de koşar); kabın logu CI'da basılmaz (imaj parolayı oraya yazar).
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
  (`test_the_gate_runs_sitedb_tests_only_where_it_names_them`); `ci.yml`e hiçbir adımda `docker logs` girmez
  (`test_ci_never_prints_the_container_log`); `site.yml`e dokunurken `test_site_workflow.py`nin secret sınırı ve sıra
  testleri yeşil kalmalı. `web/fixtures/`e B-2'nin kendi fixture'larını eklemesi serbesttir (B-1'in testi kapsayıcı
  değil, varlık sınar). Not: dışa aktarımın `snapshot.sha256`i `sha256sum` biçimindedir (`<hex>  snapshot.json`);
  yayındaki `/data/snapshot.sha256`in biçimi B-2'nindir — §6.4/3f karşılaştırması ikisinin hex alanını kıyaslamalıdır.

## Canlıya geçiş (kullanıcı onayı, §0.7 — bu dalga YAPMADI)

1. 0013 canlıda + advisors temiz (controller).
2. AK6 onayı → `0014` ROLLBACK'li prova → `apply_migration` (uygulayan rol `postgres` olmalı: görünüm sahibi = tablo
   sahibi, aksi hâlde RLS'li tablolar görünümden HATASIZ 0 satır döner — §4.2) → katalog testleri gerçek DB'ye karşı
   salt okuma kipinde → Supabase advisors 0014'ten SONRA da okunur (spec §4.2; üç şema API'ye açık şemalara
   eklenmemiş, `security_invoker` uyarısı yok).
3. RUNBOOK'a `site_reader` parola/`LOGIN` adımı: parola kullanıcı tarafından istemci tarafı SCRAM ile (`\password
   site_reader`); asistan parolayı görmez ve girmez (AK18).
4. Ölçülecek: Supavisor kullanıcı biçimi (`site_reader.<proje_ref>`) ve rol GUC'lerinin pooler üzerinden uygulandığı (§4.5).
5. Secret'lar: `SITE_DATABASE_URL`, `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID` (ayrı Netlify hesabı/ekibi — AK18), ortam
   kapsamlı; GitHub'da `production` ortamının dağıtım dalı `main`e sınırlanır (kullanıcının depo ayarı).

## Kapının ÖLÇMEDİKLERİ (B-1)

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
    tabandır. Kap kalkmazsa CI yalnız kabın durumunu basar (logu parola taşır): nedeni için yerelde
    `scripts/sandbox_db.sh up` ile yeniden üretilir.
