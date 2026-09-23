# Faz 6 İz B · Plan B-1 — Okuma katmanı, dışa aktarım ve K1 testleri Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sitenin salt okuma katmanını (`0014`, `site_reader`, `site`/`site_input`/`site_audit` görünümleri), anlık
görüntü sözleşmesini (JSON Schema + iki sentetik fixture), `verify-snapshot`ı ve dışa aktarıcıyı (tek işlem, tam
zincir, ikinci türetim) K1 testleriyle ve kendi CI adımıyla kurmak — migration canlıya UYGULANMADAN, yayın BAĞLANMADAN.

**Architecture:** DB'ye yalnız Python dokunur (B2). `python -m football_edge.site export`, `site_reader` rolüyle tek
`REPEATABLE READ, READ ONLY` işleminde zinciri GENESIS'ten ve depodaki her çıpaya karşı `site_audit.ledger_rows`
üzerinden doğrular, türetim girdilerini kanonik bir DÖKÜME yazar, dökümden iki kez türetir (ikincisi ayrı süreçte,
başka `PYTHONHASHSEED`le), `verify-snapshot` kurallarını uygular ve ancak hepsi geçerse `snapshot.json` +
`snapshot.sha256` yazar. Görünümler `postgres` sahipli ve `security_barrier`lıdır; holdout tabanı tek yerdedir
(`site.public_floor()` = Python `PUBLIC_FLOOR`). DB testleri atılabilir bir `supabase/postgres` kabında koşar: tam sıra
`postgres` veritabanında geri alınan tek işlemde, davranış şablonlu alt kümenin (`site_tpl`) modül başına kopyasında;
CI'da kap iş içinde doğar (`site-db` adımı).

**Tech Stack:** Python 3.11, uv, psycopg 3, PyYAML, numpy, pytest (`leakage`, yeni `sitedb` işareti), ruff, mypy
(strict), Postgres 17 (`public.ecr.aws/supabase/postgres:17.6.1.143`, özet T0'da sabitlenir), GitHub Actions, JSON
Schema'nın bağımlılıksız alt küme doğrulayıcısı (`site/schema.py`).

**Spec:** `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md` (B1–B13, H1–H7, §4–§6, §12, §14, §15 "Plan B-1",
§18.5). Plana bırakılan üç Minor: `.superpowers/sdd/2026-09-23-oturum9-dalga-a/izb-spec-rereview4.md` m1–m3 (Task 3'te
kapanır, aşağıda "Spec'in bıraktığı sorular").

**Ön koşul (sert):** B-1, Dalga A Task 6'nın 0013 dalı (`.worktrees/wt-s9-rls`, bu plan yazılırken son commit `75cc13c`)
**main'e birleştikten SONRA** başlar. O dal şunları getirir ve bu plan onlara dayanır: `db/migrations/0013_api_roles_
lockdown.sql`, `scripts/sandbox_db.sh`, `tests/test_api_roles_lockdown_db.py`, `tests/test_gate_traceback.py`,
`verify.sh`in `--tb=short`lı üç pytest çağrısı, RUNBOOK §4, DEFERRED 18a–18f. Task 0 Step 1 bunu doğrular; yoksa durur.
Bu plandaki her "düzenle" adımının eski metni o birleşmiş hâlden birebir alınmıştır: eşleşmezse tahmin edilmez, durulur.

## Global Constraints

Spec'ten birebir (her görevin gereksinimidir):

- "Holdout verisi = maç tarihi `[2025-07-01, 2026-07-01)` (Londra) olan her satır VE ondan türetilmiş her sayı" — sitede ASLA görünmez (H1).
- "taban `HOLDOUT_END + 1 gün` = 2026-07-02 00:00 UTC ve Python sabitinden türetildiği testle kanıtlanır" (B4).
- "Üç şema, bir rol: `site` (her kolonu anlık görüntüye BİREBİR girebilir = yayımlanabilir) · `site_input` (hesap girdisi, yayımlanmaz: kitap bazında fiyat) · `site_audit` (yalnız zincir doğrulaması, yayımlanmaz)" (B3).
- "`0014_site_read.sql`: şemalar, rol, görünümler, yer tutucu sicil" — "Migration (YAZILIR, canlıya UYGULANMAZ)" (§4.1).
- "`create role site_reader nologin noinherit` — idempotent … **Parola ve `LOGIN` migration'da YOK**" (§4.2).
- "Migration bağlantısı her iki yerde **`postgres` rolüyledir** (`-U postgres`, `sandbox_db.sh` deseni)" (§4.4/2).
- "**Testte tetikleyiciyi devre dışı bırakmak YASAKTIR**" (§4.4/4).
- "Fixture `SITE_TEST_DATABASE_URL`'in ana makinesi `localhost`/`127.0.0.1`/CI servis adı değilse ya da `DATABASE_URL`e eşitse testleri adıyla REDDEDER (kırmızı). Değişken yoksa: yerelde `SKIP: site-db (SITE_TEST_DATABASE_URL yok)`, **`CI=true` iken FAIL** (B10)." (§4.4/5)
- "Dışa aktarım tek `REPEATABLE READ READ ONLY` işlemidir; zinciri GENESIS'ten ve bütün çıpalara karşı doğrular" (B12).
- "Döküm kitap bazında fiyat taşır → **diske yazılmaz**, alt sürece **stdin** ile verilir, loga düşmez" (§5.1/4).
- "Anlık görüntü sayıları **görüntülenecek hassasiyette** taşır: olasılık ve hareket yüzde puanı 1 ondalık (`45.7`), CLV yüzde 2 ondalık, fiyat 2 ondalık" (§5.4).
- "`books < SITE_MIN_BOOKS` (öneri 3) ise o tur `null`" · "`SITE_MIN_TEAM_MATCHES` (öneri 3)" · "`move_distribution` … maç ≥ 5 ise" (§5.2, §8.4).
- "Anlık görüntü şeması v1'de `value_badge: null`, `analysis: null`, model olasılığı alanı YOK (JSON Schema `const: null`, `additionalProperties: false`)" (B6).
- "Fixture'lar **sentetiktir** (uydurma lig/takım adları, gerçek satır yok): gerçek anlık görüntü depoya commit'lenmez (`.gitignore`: `web/node_modules/`, `web/.next/`, `web/out/`, `web/.snapshot/`)" (§5.2).
- "Site kapısı `verify.sh`in adımıdır (tek kapı)" · "`DATABASE_URL` yine VERİLMEZ (zincir SKIP kalır)" (B10, §12.2).
- "Aynı anda en çok 4 implementer; K1 görevleri kendi worktree'lerinde, `--no-ff` birleştirme." (§15)

Proje süreci (kullanıcı kuralları, her görevde):

- Kapı: `TMPDIR=$(mktemp -d) ./verify.sh > <log> 2>&1`; sonuç LOG DOSYASINDAN okunur. Her görev tam kapıyla biter.
- Her yeni test en az bir mutasyonla kırmızı kanıtlanır: `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`; mutasyon
  `cp` yedeğinden geri yüklenir, `cmp` ile doğrulanır, sonda `git status --short` yalnız görevin dosyalarını gösterir.
- HİÇBİR ŞEY SİLİNMEZ (dosya, dal, satır); mutasyon için oluşturulan geçici dosya scratch'e TAŞINIR. `git add -A` yok —
  yalnız açık yollar. Holdout AÇILMAZ. Canlı DB'ye bağlanılmaz; `.env` okunmaz.
  Tek istisna spec'in kendi tasarımıdır (§4.4/4): atılabilir YEREL kaptaki test veritabanları (`site_tpl`,
  `site_t_*`) `DROP DATABASE … WITH (FORCE)` ile kaldırılır — koruma yerel olmayan adresi reddeder; kaplar
  (`docker rm`) SİLİNMEZ, durdurulur.
- Migration yalnız yerel kapta yazılır ve sınanır; üretime uygulamak kullanıcının §0.7 onayıdır (bu planda YOK).
- Commit biçimi `<type>: <açıklama>` + boş satır + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Anahtar/secret adları testlerde ve betiklerde PARÇALARDAN kurulur (`"SITE_DATABASE" + "_URL"`): kapının secrets
  adımı testleri de tarar. Test DB adresinin adını tests/ altında yalnız `tests/site_db.py` anar (Task 3 kuralı).
- Yorum ve doküman dili Türkçe, kısa "neden"; tarihçe commit mesajında.
- Worktree: `git worktree add .worktrees/wt-b1-t<N> -b feat/faz6-b1-t<N> main`; her dispatch'e ayrı scratch alt
  dizini (`.superpowers/sdd/<oturum>/b1-t<N>-scratch/`), rapor dosyası, kısa son mesaj.
- DB testleri yerelde: `scripts/sandbox_db.sh up` sonra `scripts/sandbox_db.sh test <yol>` (betik `SITE_TEST_DATABASE_URL`i
  BOŞ kaba çevirir — Task 3). Paralel oturumlar kendi `FE_SANDBOX_PREFIX`/`FE_SANDBOX_PORT`unu kullanır (RUNBOOK §4).

Kapının bu plandaki beklenen çıktısı: Task 0–8 boyunca `10 PASS` + `SKIP: zincir (DATABASE_URL yok)`; Task 9'dan sonra
yerelde `10 PASS` + `SKIP: site-db (SITE_TEST_DATABASE_URL yok)` + `SKIP: zincir`, kum havuzu adresiyle ve CI'da
`11 PASS` + `SKIP: zincir`.

**Mutasyon yardımcısı** (her mutasyon adımı bunu kullanır; platformdan bağımsız, çapa yoksa HATA verir — sessizce
hiçbir şeyi değiştirmeyen bir mutasyon "yeşil kaldı" diye okunmasın):

```bash
mutate() {  # kullanım: mutate <dosya> <eski metin> <yeni metin>   (ilk eşleşme)
  python3 - "$@" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
assert old in text, f"mutasyon çapası yok: {old!r}"
open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
PY
}
```
Kalıp her mutasyon için: `cp <dosya> /tmp/<ad>.bak` → `mutate …` → `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider <test>`
(beklenen kırmızı) → `cp /tmp/<ad>.bak <dosya> && cmp /tmp/<ad>.bak <dosya>` → aynı test yeşil.

## Review Focus

Spec'in ima ettiği ama görev testlerinin kendiliğinden sınamayacağı, kullanıcıyı en olası ısıracak beş girdi. Her
birinin testi sahibi görevin "Review Focus" adımındadır:

1. **Oturum saat dilimi UTC değil** (Supavisor `-c timezone=UTC` seçeneğini yok sayarsa psycopg `+03:00`lı zaman
   döner; §4.5 bunu ölçülmemiş bırakıyor) → anlık görüntünün `content_sha256`sı UTC oturumdakiyle AYNI olmalı (Task 6).
2. **Mühürlü ama kapanış turu ince** (mühür turunda yalnız iki tam kitap) → `sealed: true`, `closing`/`latest`
   `null`, `move: null`, `verify-snapshot` geçer; "mühürlüyse kapanış vardır" varsayımı çökmemeli (Task 5).
3. **Tek yayınlı sicil (n = 1)** → özet çökmeden `ci_low = ci_high = mean_clv`; spec yalnız n = 0'ı adlandırıyor (Task 6).
4. **Çıpa kesimin ilerisinde** (yeni checkout, eski/geri yüklenmiş veritabanı: çıpanın `last_id`i defterde yok) →
   adıyla zincir kırmızısı (`id=…`), hiçbir dosya yazılmaz (Task 6).
5. **Ertelenen maç** (`commence_time` turlar arasında UPDATE edilir) → `path_id` ve `slug` değişmez, `date` ve
   `commence_time` yeni anı gösterir (AK20 b'nin URL kalıcılığı) (Task 5).

Ayrıca testli (görev adımlarında): −0.04 pp hareket `-0.0` değil `0.0` basılır (Task 5) · `book_key` tur içinde kitap
sırasıdır ve kitap adı sızmaz (Task 3 davranış) · bir turda eksik kitap yalnız o turun sayısını düşürür (Task 5) · aynı adın iki yazımı aynı slug'a düşerse
yayın durur (Task 5) · `service_role`/JWT/DSN kalıbı hata metnine YANKILANMAZ (Task 4) · çöken ikinci türetimin
traceback'i fiyat taşısa da loga girmez (Task 6) · test DB adresi yerel değilse ya da canlı adrese eşitse testler
reddedilir, hata metni adresi basmaz (Task 3).

## Spec'in bıraktığı sorular ve bu planın kararları

| # | Soru | Karar | Gerekçe |
|---|---|---|---|
| Q1 | JSON Schema doğrulayıcısı: `jsonschema` bağımlılığı mı el yazımı mı (§18.5/7)? | El yazımı alt küme, `site/schema.py`; şema desteklenmeyen anahtar kelime taşırsa `SchemaError` | Yeni bağımlılık yok; doğrulayıcının SESSİZCE yok saydığı bir anahtar kelime, sözleşmede yazılı ama sınanmayan kural olurdu — alt küme bunu kırmızı yapar |
| Q2 | Harness (şablonlu yalıtım) spec §15'te T5'te; ama 0014'ün katalog/davranış testleri (spec T2) onu ister | Harness bu planın Task 3'üne (0014) alındı | Kullanıldığı ilk görev; spec T5'e ertelemek 0014'ü DB'siz bırakırdı |
| Q3 | `verify-snapshot` spec §15'te T5'te; dışa aktarım §5.1/6'da onu çağırır | `verify-snapshot` Task 4, dışa aktarıcı Task 6 | Bağımlılık yönü |
| Q4 | `_LEDGER_COLUMNS` tuple'ı (§4.3) ile `site_audit.ledger_rows` metin testi aynı görevde mi? | Parametreleme Task 2'de; 0014 (Task 3) ondan SONRA | Metin testi tuple'ı import eder |
| Q5 | 0014 tek dosya mı, 0015'e bölünür mü (§4.1)? | Tek dosya `0014_site_read.sql`; şablon listesi 0001, 0002, 0013, 0014 | Bölmeyi gerektiren bir parça yok; m3 listeleri buna göre adıyla |
| Q6 | m1: istisna mutasyonunun tarifi yeşil kalıyordu | İstisnalar (`references`, `ops` hedefi) deyim listesine TAKILMAZ, belge amaçlıdır; mutasyon kanıtı "atlanan bir migration'a yasak deyim, hedefi `leagues`" (`create trigger … on leagues`) | Rereview4 m1(a) |
| Q7 | m2: kara liste sözcük boşlukları | `public.`/tırnaklı ad, `if not exists`, `unique`, `drop trigger/policy/rule … on`, her `drop index`, `create rule … to`, çoklu hedef, `on all … in schema`, site nesnesi/rolü, hedefe DML ve `copy` kalıpları; "ölçmedikleri"ne kara liste notu | Rereview4 m2; her biri parametrik testte |
| Q8 | m3: "atlanan" küme | `TEMPLATE_MIGRATIONS` ve `SKIPPED_MIGRATIONS` adıyla (`tests/site_db.py`); `db/migrations/`teki her dosya tam olarak birinde; bilinmeyen dosya kırmızı | Rereview4 m3 |
| Q9 | CI'da kap `services:` ile mi (§12.2)? | İş içinde `docker run` adımı | "Parola iş içinde üretilir" hizmet kabıyla mümkün değil (hizmet adımlardan önce doğar); `postgres -D /etc/postgresql` komutu hizmet kabına verilemez; yerel kum havuzuyla AYNI başlatma satırı. Bu yüzden izin listesi yalnız loopback (`localhost`, `127.0.0.1`, `::1`) — "CI servis adı" gerekmez |
| Q10 | `postgres` (süper değil, CREATEROLE) yarattığı role `SET ROLE` diyebilir mi? Davranış testleri `site_reader` olarak sorgulamalı | T0 ölçer (`set_role=`); harness `pg_has_role(…,'SET')` yanlışsa YALNIZ test kümesinde `GRANT site_reader TO postgres WITH INHERIT FALSE, SET TRUE` verir; 0014 kimseye üyelik vermez (metin testi) | PG16+ `createrole_self_grant`; üretimde dışa aktarım LOGIN'li `site_reader`in kendisidir |
| Q11 | Vig yöntemi `config/model_faz3.yaml`dan; okuyucu `backtest.model_config` (H1f yasak) | Site dosyadan yalnız `method`i okur (`devig_method`); test `load_model_config(...).method` ile eşitliği sınar | "Model kodu neyse o" + import bekçisi |
| Q12 | `path_id` önek uzunluğu (§18.5/5) | 12 (`PATH_ID_LENGTH`); çakışma türetimi ve `verify-snapshot`ı kırmızı yapar | 48 bit; defterin boyunda çakışma olasılığı ihmal edilir, olursa yayın durur |
| Q13 | "Maç kümesi = kesimde en az bir oran satırı olan" — hangi market? | En az bir **1X2** satırı (site yalnız `site_input.h2h_quotes`i okur) | Sayfa yalnız 1X2 gösterir |
| Q14 | `move_distribution`un maç başına değeri ve yüzdelik yöntemi | Mühürlü, en az iki turlu, iki ucu görünür maçta `max(|Δev|,|Δber|,|Δdep|)`; numpy doğrusal yüzdelik | Tek sayı; elle hesaplanabilir test vektörü (13.5/25.0/30.0) |
| Q15 | Açılış/son/kapanış tanımı | açılış = ilk tur; son = son tur (mühürlüyse kapanış turu); kapanış = son `is_closing` turu; `move` = açılış→kapanış (yoksa son); uçlardan biri `null`sa `move: null` | §5.2 |
| Q16 | `snapshot.sha256` biçimi | `sha256sum` biçimi: `<64 hex>  snapshot.json\n` | `sha256sum -c` ile doğrulanabilir |
| Q17 | Dışa aktarımın `--out` hedefi (`site.yml`) | `web/.snapshot/` (`.gitignore`'da); `--out` boş değilse kırmızı | Bayat dosyayla yayın yok |
| Q18 | `site.yml`in Node adımları B-2'nin; B-1 yazar mı? | B-1 §11'in komut adlarıyla yazar ve yalnız secret sınırını/sırayı sınar; gövdeleri B-2 (B-1 birleştikten sonra) değiştirebilir | H5d testi deploy adımını ister |
| Q19 | `netlify-cli` sabit sürümü | T0 `npm view netlify-cli version` ölçer, `site.yml` onu yazar, test T0 kaydıyla eşitliği sınar | Tahmin edilmiş sürüm yok |
| Q20 | "Adım başta dizini boşaltır" (§12.1) ile "hiçbir şey silme" | Dosyalar SIFIRLANIR (`: > dosya`), silinmez | Bayat dosya reddi `run-id` eşitliğiyle zaten sağlanır |
| Q21 | `sitedb` testleri Task 3–8 arasında CI'da nerede? | Task 3 kapının `pytest` ve `sızıntı` seçicilerini `not sitedb` yapar (yoksa `CI=true` fixture'ı main'i kırmızı yapardı); CI'da koşmaları Task 9 ile başlar — pencere "ölçmedikleri"nde | Dalga sonu birleştirmesi (§12.2) |
| Q22 | DEFERRED 18a (CI kum havuzu testlerini koşmuyor; tetik "bir sonraki DB migration'ı" = 0014) | Task 9'un CI kabı `SANDBOX_DATABASE_URL`i de verir: 0013 kum havuzu testleri `pytest` adımında koşar; `DATABASE_URL`li katalog testleri SKIP kalır; 18a notu güncellenir | Tetik bu planla ateşleniyor; kap zaten var |
| Q23 | Şema ↔ TS tip anahtar eşitliği pytest'i (§5.2, §12.1 "pytest" satırı) TS dosyasını ister | B-2'ye devredilir (TS `Snapshot` tipini B-2 yazar); Task 9 "Produces" bunu B-2 yükümlülüğü olarak yazar | TS dosyası olmadan test anlamsız; atlanan test geçmek değildir |
| Q24 | Dışa aktarım çıkış kodları | 20 yapılandırma · 21 zincir/çıpa · 22 kesim/görünüm/taban/sicil · 23 belirlenimcilik · 24 `verify-snapshot`; benzersizlik `tests/test_jev_budget.py`de | 9–19 dolu |

**Spec §15 numaraları → bu plan:** T0 → Task 0 · T1 → Task 1 (+ geçişli import bekçisi, spec T5'ten) · T3 → Task 2 ·
T2 → Task 3 (+ şablonlu yalıtım, spec T5'ten) · T4 → Task 4 (slug) + Task 5 (türetim) + Task 6 (dışa aktarıcı) ·
T5 → Task 4 (`verify-snapshot`) + Task 7 (uçtan uca) · T6 → Task 8 (`site.yml`, `check_secrets.sh`) + Task 6
(redaksiyon) · dalga sonu birleştirmesi → Task 9.

## Dosya yapısı ve tek-yazar tablosu

| Görev | Oluşturur | Değiştirir | Kademe |
|---|---|---|---|
| 0 | `scripts/site_t0_probe.sh`, `docs/phases/06-site/b1-t0-olcumler.md` | — | Ölçüm |
| 1 | `src/football_edge/site/{__init__,contract,schema}.py`, `web/contract/snapshot.schema.json`, `web/fixtures/snapshot.fixture.json`, `web/fixtures/snapshot.fixture-record.json`, `tests/test_site_{schema,contract,import_rule}.py` | `.gitignore`, `tests/test_jev_budget.py` | K1 |
| 2 | `src/football_edge/market/consensus.py`, `tests/test_market_consensus.py`, `tests/test_ledger_readers.py` | `src/football_edge/live/context.py`, `src/football_edge/collect.py` (okuyucu) | K1 |
| 3 | `db/migrations/0014_site_read.sql`, `tests/{sql_text,site_db}.py`, `tests/test_site_{migration_text,template_subset,harness_rules,views_db}.py` | `pyproject.toml`, `verify.sh` (seçiciler), `scripts/sandbox_db.sh`, `docs/RUNBOOK.md` §4 | K1 |
| 4 | `src/football_edge/site/{slugs,verify,__main__}.py`, `tests/test_site_{slugs,verify}.py` | — | K1 |
| 5 | `src/football_edge/site/{inputs,derive}.py`, `tests/site_builders.py`, `tests/test_site_derive.py` | — | K1 |
| 6 | `src/football_edge/site/export.py`, `tests/fake_site_db.py`, `tests/test_site_{export,determinism,logging}.py` | `src/football_edge/site/__main__.py`, `src/football_edge/collect.py` (`_log_secrets`) | K1 |
| 7 | `tests/test_site_e2e_db.py` | `scripts/sandbox_db.sh` | K1 |
| 8 | `.github/workflows/site.yml`, `tests/test_site_workflow.py`, `tests/test_secrets_scan_netlify.py` | `scripts/check_secrets.sh` | K1 |
| 9 | `tests/test_site_gate.py`, `docs/phases/06-site/HANDOFF.md` | `.github/workflows/ci.yml`, `verify.sh` (site-db, run-id, sayılar), `tests/test_gate_traceback.py`, `docs/RUNBOOK.md` §4, `docs/DEFERRED.md` 18a | K2 (kapı entegrasyonu) |

Ortak dosyaların sırası (paralel yazım YOK): `collect.py` T2 → T6 · `verify.sh` T3 → T9 · `sandbox_db.sh` T3 → T7 ·
`site/__main__.py` T4 → T6 · `docs/RUNBOOK.md` T3 → T9. B-2 `verify.sh`/`ci.yml`/`site.yml`e yalnız Task 9 birleştikten
sonra dokunur (§12.3).

**Sıra ve paralellik:** Task 0 → Task 1 (B-2'nin başlangıç kapısı bu birleşme) → Task 2 → {Task 3 ∥ Task 4} → Task 5
(2 ve 4'ü bekler) → Task 6 → {Task 7 (3'ü de bekler) ∥ Task 8} → Task 9. Aynı anda en çok üç implementer.
Her görev kendi worktree'sinde; controller incelemeden sonra `--no-ff` birleştirir, push öncesi `git fetch origin &&
git merge --no-ff origin/main` + tam kapı. K1 görev incelemeleri mutasyon koşar: DB'ye dokunan görevlerde (3, 7, 9)
inceleyici yerel kapta migration koşabilen bir ajandır (bellek notu "Reviewer needs a shell").

---

### Task 0: T0 — CI kabını ölç ve sabitle

**Kademe:** Ölçüm (üretim kodu yok) · **Spec:** §15 T0, §4.4/2 ("tam etiket B-1 T0'da sabitlenir"), §4.4/4 (kanıt durumu),
§18.5/1 ve /8 · **Bağımlılık:** 0013 main'de · **Worktree:** `wt-b1-t0`

Spec'in ölçmeden kurmayı yasakladığı (B10) varsayımlar burada ölçülür ve bir KAYIT dosyasına `anahtar=değer` olarak
yazılır; sonraki görevler değeri kayıttan OKUR, testler eşitliği sınar. Ölçen komut depoya girer
(`scripts/site_t0_probe.sh`): "belgede donmuş sayı değil, ölçen komut".

**Files:**
- Create: `scripts/site_t0_probe.sh`
- Create (betiğin çıktısı): `docs/phases/06-site/b1-t0-olcumler.md`

**Interfaces:**
- Consumes: main'deki `db/migrations/0001…0013`, Docker, ağ (imaj çekme, `npm view`).
- Produces (Task 3, 8, 9 okur): kayıt dosyasında şu satırlar — `image=public.ecr.aws/supabase/postgres:17.6.1.143`,
  `image_digest=sha256:<64 hex>`, `set_role=direct|after_grant|denied`, `netlify_cli=<X.Y.Z>`,
  `full_sequence_one_transaction=ok`, `template_0001_0002_0013=ok`, `template_copy=ok`, `drop_database_force=ok`,
  `postgres_super_createdb_createrole_bypassrls=<4 bool>`, `ready_seconds=<n>`, `full_sequence_seconds=<n>`.

- [ ] **Step 1: Ön koşulu doğrula**

```bash
git log --oneline -1 main -- db/migrations/0013_api_roles_lockdown.sql tests/test_gate_traceback.py
test -f db/migrations/0013_api_roles_lockdown.sql && test -x scripts/sandbox_db.sh \
  && grep -q 'uv run pytest -q --tb=short' verify.sh && echo ONKOSUL-TAMAM
ls db/migrations/
```
Expected: bir commit satırı, `ONKOSUL-TAMAM`, ve `0001_init.sql` … `0013_api_roles_lockdown.sql` (14. dosya YOK).
Biri eksikse DUR: 0013 dalı birleşmeden B-1 başlamaz (eskalasyon: Defer, controller'a).

- [ ] **Step 2: Ölçüm betiğini yaz**

`scripts/site_t0_probe.sh` (tam içerik):

````bash
#!/usr/bin/env bash
# B-1 T0: CI'ın kuracağı kabın AYNISINI yerelde kurar ve B-1'in dayandığı varsayımları ölçer.
# Kaydı depoya (docs/phases/06-site/b1-t0-olcumler.md), ham çıktıyı scratch'e yazar. Kap durdurulur,
# SİLİNMEZ (`docker rm fe-site-t0` kullanıcının kararıdır).
set -uo pipefail
SCRATCH="${1:?scratch dizini ver}"
IMAGE=public.ecr.aws/supabase/postgres:17.6.1.143
NAME=fe-site-t0
REC=docs/phases/06-site/b1-t0-olcumler.md
RAW="$SCRATCH/t0-raw.log"
mkdir -p "$SCRATCH" docs/phases/06-site
: > "$RAW"
q() { docker exec -i -e PGPASSWORD="$PW" "$NAME" psql -h localhost -U postgres -At "$@"; }

docker pull "$IMAGE" >>"$RAW" 2>&1
DIGEST="$(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGE" | sed 's/^.*@//')"
PW="$(openssl rand -hex 16)"
START=$(date +%s)
docker run -d --name "$NAME" --label football-edge.sandbox=1 -e POSTGRES_PASSWORD="$PW" \
  -p 127.0.0.1:55490:5432 "$IMAGE" postgres -D /etc/postgresql >>"$RAW" 2>&1
until q -d postgres -c 'select 1' >/dev/null 2>&1; do
  [ $(( $(date +%s) - START )) -lt 300 ] || { echo "kap 300 sn'de hazır olmadı" >>"$RAW"; break; }
  sleep 2
done
READY=$(( $(date +%s) - START ))
VERSION="$(q -d postgres -c 'show server_version')"
ROLE="$(q -d postgres -F, -c "select rolsuper, rolcreatedb, rolcreaterole, rolbypassrls from pg_roles where rolname = 'postgres'")"
SELF_GRANT="$(q -d postgres -c 'show createrole_self_grant')"

# (i) 0001→0013 tek işlemde, postgres veritabanında, postgres rolüyle; sonra GERİ AL.
T=$(date +%s)
if { echo 'begin;'; for f in db/migrations/[0-9][0-9][0-9][0-9]_*.sql; do cat "$f"; echo; done
     echo "select 'jobs_in_tx=' || count(*) from cron.job;"; echo 'rollback;'; } \
   | q -d postgres -v ON_ERROR_STOP=1 >>"$RAW" 2>&1; then FULL=ok; else FULL=failed; fi
FULL_SECONDS=$(( $(date +%s) - T ))
CRON_GONE="$(q -d postgres -c "select to_regclass('cron.job') is null")"
POSTGRES_EMPTY="$(q -d postgres -c "select to_regclass('public.odds_snapshots') is null")"

# (ii) şablon: 0001 + 0002 + 0013 ayrı bir veritabanına; kopya; FORCE ile düşürme.
q -d postgres -c 'create database fe_t0_tpl' >>"$RAW" 2>&1
TEMPLATE=ok
for f in 0001_init.sql 0002_sources.sql 0013_api_roles_lockdown.sql; do
  q -d fe_t0_tpl -v ON_ERROR_STOP=1 -1 -f - < "db/migrations/$f" >>"$RAW" 2>&1 || TEMPLATE="failed:$f"
done
if q -d postgres -c 'create database fe_t0_copy template fe_t0_tpl' >>"$RAW" 2>&1; then COPY=ok; else COPY=failed; fi
COPY_TABLES="$(q -d fe_t0_copy -c "select count(*) from pg_class where relnamespace = 'public'::regnamespace and relname in ('leagues', 'matches', 'odds_snapshots')")"
if q -d postgres -c 'drop database fe_t0_copy with (force)' >>"$RAW" 2>&1; then DROP=ok; else DROP=failed; fi
q -d postgres -c 'drop database fe_t0_tpl with (force)' >>"$RAW" 2>&1

# (iii) rol: CREATEROLE'lü postgres yarattığı role SET ROLE diyebiliyor mu, üyeliği kendine verebiliyor mu?
PROBE="$(q -d postgres -v ON_ERROR_STOP=0 2>&1 <<'SQL'
begin;
create role fe_t0_reader nologin noinherit;
alter role fe_t0_reader set default_transaction_read_only = on;
alter role fe_t0_reader set statement_timeout = '30s';
savepoint s;
set local role fe_t0_reader;
select 'became_without_grant=' || current_user;
rollback to savepoint s;
grant fe_t0_reader to postgres with inherit false, set true;
set local role fe_t0_reader;
select 'became_after_grant=' || current_user;
rollback;
SQL
)"
printf '%s\n' "$PROBE" >>"$RAW"
if printf '%s\n' "$PROBE" | grep -qx 'became_without_grant=fe_t0_reader'; then SET_ROLE=direct
elif printf '%s\n' "$PROBE" | grep -qx 'became_after_grant=fe_t0_reader'; then SET_ROLE=after_grant
else SET_ROLE=denied; fi

NETLIFY="$(npm view netlify-cli version 2>>"$RAW")"
docker stop "$NAME" >/dev/null

{
  echo "# Faz 6 İz B · B-1 T0 ölçümleri"
  echo
  echo "Üreten: plan \`docs/superpowers/plans/2026-09-24-faz6-iz-b-1-okuma-katmani.md\` Task 0; tarih $(date -u +%Y-%m-%dT%H:%MZ)."
  echo "Kap CI'ın kuracağı biçimde kuruldu (\`postgres -D /etc/postgresql\`, parola iş içinde üretildi)."
  echo "Sonraki görevler aşağıdaki \`anahtar=değer\` satırlarını OKUR (tahmin etmez); testler eşitliği sınar."
  echo
  echo '```'
  echo "image=$IMAGE"
  echo "image_digest=$DIGEST"
  echo "server_version=$VERSION"
  echo "ready_seconds=$READY"
  echo "postgres_super_createdb_createrole_bypassrls=$ROLE"
  echo "createrole_self_grant=${SELF_GRANT:-bos}"
  echo "full_sequence_one_transaction=$FULL"
  echo "full_sequence_seconds=$FULL_SECONDS"
  echo "cron_gone_after_rollback=$CRON_GONE"
  echo "postgres_db_empty_after_rollback=$POSTGRES_EMPTY"
  echo "template_0001_0002_0013=$TEMPLATE"
  echo "template_copy=$COPY"
  echo "template_copy_tables=$COPY_TABLES"
  echo "drop_database_force=$DROP"
  echo "set_role=$SET_ROLE"
  echo "netlify_cli=$NETLIFY"
  echo '```'
} > "$REC"
cat "$REC"
````

`chmod +x scripts/site_t0_probe.sh`. Betik kabı SİLMEZ (durdurur); kaldırmak kullanıcının kararıdır
(`docker rm fe-site-t0`).

- [ ] **Step 3: Ölç**

```bash
scripts/site_t0_probe.sh .superpowers/sdd/<oturum>/b1-t0-scratch
```
Expected (kayıt dosyasının kod bloğunda): `full_sequence_one_transaction=ok`, `cron_gone_after_rollback=t`,
`postgres_db_empty_after_rollback=t`, `template_0001_0002_0013=ok`, `template_copy=ok`, `template_copy_tables=3`,
`drop_database_force=ok`, `postgres_super_createdb_createrole_bypassrls=f,t,t,t` (Supabase'de `postgres` süper
değildir; CREATEDB ve CREATEROLE taşır), `set_role=direct` ya da `after_grant`, `image_digest=sha256:` + 64 hex,
`netlify_cli=` + `X.Y.Z`.

**Durma koşulları (eskalasyon — Revise, controller'a):** `full_sequence_one_transaction=failed` (§4.4/2(i) kurulamaz),
`template_0001_0002_0013=failed:<dosya>` (R1'in şablonlu alt kümesi kurulamaz; spec §4.4/4 "analizle beklenir"
varsayımı çöktü), `template_copy=failed` ya da `drop_database_force=failed` (yalıtım kurulamaz), CREATEDB `f`,
`set_role=denied` (davranış testleri `site_reader` olarak koşamaz; seçenek: test kümesinde LOGIN'li ayrı bir rol —
spec değişikliği ister). Ham çıktı scratch'teki `t0-raw.log`dadır; hata satırı rapora aynen alınır.

- [ ] **Step 4: Kapı**

Run: `TMPDIR=$(mktemp -d) ./verify.sh > "$TMPDIR/verify.log" 2>&1; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$TMPDIR/verify.log"`
Expected: `10 PASS` + `SKIP: zincir (DATABASE_URL yok)` + `KAPI YEŞİL` (betik bash'tir; `secrets` adımı onu da tarar).

- [ ] **Step 5: Commit**

```bash
git add scripts/site_t0_probe.sh docs/phases/06-site/b1-t0-olcumler.md
git commit -m "docs: Faz 6 B-1 T0 — CI kabı, şablon ve rol ölçümleri

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 1: Anlık görüntü sözleşmesi — şema, sentetik fixture'lar, doğrulayıcı, import bekçisi

**Kademe:** K1 · **Spec:** §5.2, §5.4, B4, B6, H1f, H3, §4.3 (yasak anahtarlar), §13 · **Bağımlılık:** Task 0 ·
**Worktree:** `wt-b1-t1` · **B-2'nin başlangıç kapısı bu görevin birleşmesidir.**

Sözleşme Python tarafında TEK yerdedir (`site/contract.py`): taban, eşikler, `site.record` kolonları, yasak anahtarlar,
çıkış kodları, içerik hash'i. Şema kapalıdır (`additionalProperties: false` her nesnede) ve yalnız doğrulayıcının
desteklediği anahtar kelimeleri kullanır. İki fixture sentetiktir ve B-2'nin sayfa varyantlarının hepsini taşır.
Paket doğduğu anda geçişli import bekçisi de doğar: sonraki her site modülü onun altında yazılır.

**Files:**
- Create: `src/football_edge/site/__init__.py`, `src/football_edge/site/contract.py`, `src/football_edge/site/schema.py`
- Create: `web/contract/snapshot.schema.json`, `web/fixtures/snapshot.fixture.json`, `web/fixtures/snapshot.fixture-record.json`
- Modify: `.gitignore` (sona dört satır), `tests/test_jev_budget.py` (çıkış kodu benzersizliği)
- Test: `tests/test_site_schema.py`, `tests/test_site_contract.py`, `tests/test_site_import_rule.py`

**Interfaces:**
- Consumes: `football_edge.ledger._canonical(payload: dict[str, Any]) -> str`; `football_edge.history.holdout.HOLDOUT_END`
  (YALNIZ testte).
- Produces (Task 2–9 ve B-2):
  ```python
  # football_edge.site.contract
  SCHEMA_VERSION = 1; SCHEMA_PATH = Path("web/contract/snapshot.schema.json")
  DEVIG_CONFIG_PATH = Path("config/model_faz3.yaml")
  PUBLIC_FLOOR = datetime(2026, 7, 2, tzinfo=UTC)
  SITE_MIN_BOOKS = 3; SITE_MIN_TEAM_MATCHES = 3; MOVE_MIN_MATCHES = 5; PATH_ID_LENGTH = 12
  RESERVED_LEAGUE_SLUGS = frozenset({"track-record", "legal"}); RESERVED_TEAM_SLUGS = frozenset({"match"})
  RECORD_COLUMNS: tuple[tuple[str, str], ...]   # (ad, format_type) — site.record ile aynı sıra
  FORBIDDEN_KEYS: frozenset[str]                # §4.3'ün 9 adı
  EXIT_SITE_CONFIG = 20; EXIT_SITE_CHAIN = 21; EXIT_SITE_CUT = 22
  EXIT_SITE_NONDETERMINISTIC = 23; EXIT_SITE_INVALID = 24
  OUTSIDE_CONTENT = ("generated_at", "git_sha", "content_sha256")
  def iso_z(moment: datetime) -> str                           # "2026-09-20T14:00:00Z"
  def content_sha256(snapshot: Mapping[str, Any]) -> str       # OUTSIDE_CONTENT hariç, ledger._canonical
  # football_edge.site.schema
  class SchemaError(ValueError)
  def check_schema(schema: Mapping[str, Any]) -> None
  def property_names(schema: Mapping[str, Any]) -> frozenset[str]
  def validate(instance: Any, schema: Mapping[str, Any]) -> list[str]   # "<$.yol>: <neden>", değer basmaz
  ```
  Dosyalar: `web/contract/snapshot.schema.json` (v1), `web/fixtures/snapshot.fixture.json` (boş sicil; mühürsüz, tek
  turlu, eşik altı turlu maçlar; dolu ve boş hareket dağılımı), `web/fixtures/snapshot.fixture-record.json` (aynısı +
  iki yayınlı, özetli sicil).

- [ ] **Step 1: Doğrulayıcının testini yaz**

`tests/test_site_schema.py` (tam içerik):

````python
"""Sözleşme doğrulayıcısı (`site/schema.py`): desteklenen alt küme, JSON tipleri, kapalı nesne."""

from __future__ import annotations

from typing import Any

import pytest

from football_edge.site.schema import SchemaError, check_schema, property_names, validate

OBJECT: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["n", "tag"],
    "properties": {
        "n": {"type": "integer", "minimum": 0},
        "tag": {"type": "string", "pattern": "^[a-z]+$", "maxLength": 5},
        "maybe": {"type": ["number", "null"]},
        "kind": {"enum": ["a", "b"]},
        "fixed": {"const": None},
        "ref": {"$ref": "#/$defs/flag"},
        "items": {"type": "array", "items": {"type": "boolean"}},
    },
    "$defs": {"flag": {"type": "boolean"}},
}


def test_a_valid_instance_has_no_errors() -> None:
    check_schema(OBJECT)
    instance = {"n": 3, "tag": "ab", "maybe": None, "kind": "a", "fixed": None, "ref": True}

    assert validate({**instance, "items": [True, False]}, OBJECT) == []


@pytest.mark.parametrize(
    ("instance", "needle"),
    [
        ({"tag": "ab"}, "zorunlu 'n'"),
        ({"n": 1, "tag": "ab", "extra": 1}, "bilinmeyen anahtar 'extra'"),
        ({"n": True, "tag": "ab"}, "$.n: tip"),  # JSON'da bool tamsayı değildir
        ({"n": 1.5, "tag": "ab"}, "$.n: tip"),
        ({"n": -1, "tag": "ab"}, "$.n: 0 altında"),
        ({"n": 1, "tag": "AB"}, "$.tag: '^[a-z]+$'"),
        ({"n": 1, "tag": "abcdef"}, "$.tag: 5 karakterden uzun"),
        ({"n": 1, "tag": "ab", "maybe": "x"}, "$.maybe: tip"),
        ({"n": 1, "tag": "ab", "kind": "c"}, "$.kind:"),
        ({"n": 1, "tag": "ab", "fixed": 0}, "$.fixed: sabit"),
        ({"n": 1, "tag": "ab", "ref": 1}, "$.ref: tip"),
        ({"n": 1, "tag": "ab", "items": [True, 0]}, "$.items[1]: tip"),
    ],
)
def test_each_violation_is_named_by_its_json_path(instance: dict[str, Any], needle: str) -> None:
    errors = validate(instance, OBJECT)

    assert any(needle in error for error in errors), errors


def test_const_false_is_not_const_zero() -> None:
    assert validate(0, {"const": False}) != []
    assert validate(False, {"const": 0}) != []


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "properties": {}, "additionalProperties": False, "oneOf": []},
        {"type": "object", "properties": {"a": {"type": "string"}}},
        {"type": "object", "properties": {}, "additionalProperties": True},
        {"type": "string", "format": "date-time"},
        {"type": "decimal"},
        {"$ref": "#/$defs/yok"},
    ],
)
def test_a_schema_outside_the_supported_subset_is_refused(schema: dict[str, Any]) -> None:
    """Doğrulayıcının sessizce yok saydığı bir anahtar kelime, hiç sınanmayan bir kural olurdu."""
    with pytest.raises(SchemaError):
        check_schema(schema)


def test_property_names_reach_every_depth() -> None:
    assert property_names(OBJECT) == {"n", "tag", "maybe", "kind", "fixed", "ref", "items"}
````

- [ ] **Step 2: Sözleşme testini yaz**

`tests/test_site_contract.py` (tam içerik):

````python
"""Anlık görüntü sözleşmesi (Faz 6 İz B §5.2): şema, sentetik fixture'lar ve Python sabitleri.

B-2'nin başlangıç kapısıdır: `web/contract/snapshot.schema.json` ve `web/fixtures/*.json` bu
testlerle birlikte birleşir. Fixture'lar SENTETİKTİR (uydurma lig/takım adları); gerçek anlık
görüntü depoya girmez (`.gitignore`: `web/.snapshot/`).
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest

from football_edge.history.holdout import HOLDOUT_END
from football_edge.site.contract import (
    FORBIDDEN_KEYS,
    PUBLIC_FLOOR,
    SCHEMA_VERSION,
    SITE_MIN_BOOKS,
    content_sha256,
    iso_z,
)
from football_edge.site.schema import check_schema, property_names, validate

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "web/contract/snapshot.schema.json"
FIXTURES = REPO / "web/fixtures"
BASE = FIXTURES / "snapshot.fixture.json"
FULL_RECORD = FIXTURES / "snapshot.fixture-record.json"


def _load(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def test_the_schema_uses_only_the_supported_subset_and_closes_every_object() -> None:
    check_schema(_load(SCHEMA))


@pytest.mark.parametrize("path", [BASE, FULL_RECORD], ids=lambda path: path.name)
def test_every_fixture_satisfies_the_schema_and_its_own_content_hash(path: Path) -> None:
    snapshot = _load(path)

    assert validate(snapshot, _load(SCHEMA)) == []
    assert content_sha256(snapshot) == snapshot["content_sha256"]


def test_the_two_contract_fixtures_exist_under_their_published_names() -> None:
    """B-2 bu adlara dayanır; B-2 kendi fixture'larını aynı dizine ekleyebilir (kapsayıcı değil)."""
    assert {BASE.name, FULL_RECORD.name} <= {path.name for path in FIXTURES.glob("*.json")}


def test_the_fixtures_carry_every_variant_the_site_must_render() -> None:
    """§6.4/1: boş sicil, dolu sicil (özetli), eşik altı tur, mühürsüz maç, tek turlu maç."""
    base, full = _load(BASE), _load(FULL_RECORD)
    matches = base["matches"]

    assert base["record"] == {"published": 0, "entries": [], "summary": None}
    assert full["record"]["published"] >= 1 and full["record"]["summary"] is not None
    assert any(not match["sealed"] for match in matches), "mühürsüz maç yok"
    assert any(match["rounds"] == 1 for match in matches), "tek turlu maç yok"
    assert any(match["rounds"] >= 2 and match["h2h"]["opening"] is None for match in matches), (
        "eşik altı tur yok"
    )
    assert any(league["move_distribution"] is not None for league in base["leagues"])
    assert any(league["move_distribution"] is None for league in base["leagues"])
    assert any(team["indexable"] for team in base["teams"])
    assert any(not match["indexable"] for match in matches)


def test_value_and_analysis_slots_are_const_null_and_no_model_field_exists() -> None:
    """H3/B6: şema sürümü artmadan öneri ya da model olasılığı taşınamaz."""
    schema = _load(SCHEMA)
    names = property_names(schema)

    assert schema["properties"]["value_badge"]["const"] is None
    assert schema["properties"]["analysis"]["const"] is None
    assert not {name for name in names if "model" in name or "value" in name} - {"value_badge"}


def test_the_schema_constants_are_the_python_constants() -> None:
    schema = _load(SCHEMA)

    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert schema["properties"]["floor"]["const"] == iso_z(PUBLIC_FLOOR)
    assert schema["$defs"]["round"]["properties"]["books"]["minimum"] == SITE_MIN_BOOKS


def test_no_forbidden_key_is_declared_by_the_schema() -> None:
    """§4.3: yasak küme şemanın bildirdiği anahtarları dışlar — kesişim boş olmalı."""
    assert FORBIDDEN_KEYS & property_names(_load(SCHEMA)) == frozenset()


@pytest.mark.leakage
def test_the_public_floor_is_one_day_after_the_holdout_end() -> None:
    """B4/H1c: taban Python'da `HOLDOUT_END + 1 gün`den türetilir, elle yazılmış bir tarih değil."""
    expected = datetime.combine(HOLDOUT_END + timedelta(days=1), time(), tzinfo=UTC)

    assert expected == PUBLIC_FLOOR


def test_the_content_hash_ignores_only_build_time_and_source_version() -> None:
    snapshot = _load(BASE)
    moved = {**snapshot, "generated_at": "2030-01-01T00:00:00Z", "git_sha": "f" * 40}
    touched = {**snapshot, "floor": "2026-07-03T00:00:00Z"}

    assert content_sha256(moved) == content_sha256(snapshot)
    assert content_sha256(touched) != content_sha256(snapshot)


@pytest.mark.parametrize(
    "path",
    ["web/.snapshot/snapshot.json", "web/out/index.html", "web/.next/cache", "web/node_modules/x"],
)
def test_the_real_snapshot_and_build_outputs_never_enter_the_repository(path: str) -> None:
    """§5.2/§13: gerçek anlık görüntü (`site.yml`in `web/.snapshot/`i) depoya commit'lenmez."""
    result = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", path], check=False)

    assert result.returncode == 0, f"{path} gitignore'da değil"
````

- [ ] **Step 3: Geçişli import bekçisinin testini yaz**

`tests/test_site_import_rule.py` (tam içerik):

````python
"""H1f: `football_edge.site`in GEÇİŞLİ import kapanışı holdout'a ve tarihsel tabana ulaşamaz.

Faz 6 İz B tasarımı §2 H1f. Bekçi YASAK LİSTEYLE kodlanır (izin listesiyle değil): boş
`football_edge.history` paket `__init__`i kapanışta meşru olarak durur; `history.types`
`market.devig` ve `market.consensus` üzerinden bilinçli olarak kapanıştadır. İki katman: (1) AST ile
her modülün `import`larını — fonksiyon içindekiler dâhil — izleyerek kapanışı kurar; (2) ayrı bir
süreçte paketin her modülünü import edip `sys.modules`i okur. Bilinen sınır: hesaplanmış dizeyle
(`importlib.import_module("football_edge." + ad)`) yapılan import (1)'de görünmez; (2) onu yalnız
import anında çalışan kodda yakalar.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
ROOT = "football_edge.site"
FORBIDDEN = (
    "football_edge.history.store",
    "football_edge.history.lock",
    "football_edge.history.holdout",
    "football_edge.history.football_data",
    "football_edge.history.sync",
    "football_edge.history.catalog",
    "football_edge.backtest",
    "football_edge.live.context",
)

pytestmark = pytest.mark.leakage


def _path_of(module: str, src: Path = SRC) -> Path | None:
    base = src.joinpath(*module.split("."))
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    return None


def _with_parents(module: str) -> set[str]:
    parts = module.split(".")
    return {".".join(parts[:end]) for end in range(1, len(parts) + 1)}


def _imports(module: str, src: Path = SRC) -> set[str]:
    """`module`ün doğrudan yüklediği `football_edge` modülleri (üst paketler dâhil)."""
    path = _path_of(module, src)
    if path is None:
        return set()
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join([*anchor, *([node.module] if node.module else [])])
            else:
                base = node.module or ""
            found.add(base)
            found |= {
                f"{base}.{alias.name}"
                for alias in node.names
                if _path_of(f"{base}.{alias.name}", src) is not None
            }
    return {
        name
        for module_name in found
        if module_name.startswith("football_edge")
        for name in _with_parents(module_name)
    }


def closure(roots: set[str], src: Path = SRC) -> set[str]:
    seen: set[str] = set()
    pending = [name for root in roots for name in _with_parents(root)]
    while pending:
        current = pending.pop()
        if current not in seen:
            seen.add(current)
            pending.extend(_imports(current, src) - seen)
    return seen


def forbidden_in(modules: set[str]) -> list[str]:
    return sorted(
        name
        for name in modules
        if any(name == banned or name.startswith(banned + ".") for banned in FORBIDDEN)
    )


def _site_modules() -> set[str]:
    package = SRC / "football_edge" / "site"
    return {
        ".".join(path.relative_to(SRC).with_suffix("").parts).removesuffix(".__init__")
        for path in package.rglob("*.py")
    }


def test_the_site_package_has_modules_to_scan() -> None:
    assert {ROOT, f"{ROOT}.contract", f"{ROOT}.schema"} <= _site_modules()


def test_the_static_closure_reaches_no_forbidden_module() -> None:
    reached = closure(_site_modules())

    assert forbidden_in(reached) == [], "site kapanışı yasaklı modüle ulaşıyor"


def test_the_static_walker_follows_imports_transitively(tmp_path: Path) -> None:
    """Pozitif kontrol: iki adım ötedeki, fonksiyon içinde import edilen yasaklı modül görünür."""
    package = tmp_path / "football_edge"
    for name, body in {
        "__init__.py": "",
        "site/__init__.py": "",
        "site/a.py": "from football_edge.market import b\n",
        "market/__init__.py": "",
        "market/b.py": "def f():\n    from ..history import holdout\n    return holdout\n",
        "history/__init__.py": "",
        "history/holdout.py": "",
    }.items():
        (package / name).parent.mkdir(parents=True, exist_ok=True)
        (package / name).write_text(body, encoding="utf-8")

    reached = closure({"football_edge.site.a"}, src=tmp_path)

    assert forbidden_in(reached) == ["football_edge.history.holdout"]


_PROBE = """
import importlib, sys
for name in sys.argv[1:]:
    importlib.import_module(name)
print(",".join(sorted(m for m in sys.modules if m.startswith("football_edge"))))
"""


def test_importing_every_site_module_loads_no_forbidden_module() -> None:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, *sorted(_site_modules())],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert forbidden_in(set(result.stdout.strip().split(","))) == []
````

- [ ] **Step 4: Çıkış kodlarını benzersizlik testine kaydet**

`tests/test_jev_budget.py`, `test_every_exit_code_name_owns_exactly_one_value_across_commands` içinde iki düzenleme:

```python
# ESKİ
        "football_edge.jev",
        "football_edge.jev_budget",
    )
# YENİ
        "football_edge.jev",
        "football_edge.jev_budget",
        "football_edge.site.contract",
    )
```
```python
# ESKİ
    assert owners[16] == {"EXIT_BUDGET"}
    assert owners[17] == {"EXIT_NO_JEV_KEY"}
# YENİ
    assert owners[16] == {"EXIT_BUDGET"}
    assert owners[17] == {"EXIT_NO_JEV_KEY"}
    # Faz 6 İz B: site komutu 20–24 (`site/contract.py`).
    assert [owners[code] for code in range(20, 25)] == [
        {"EXIT_SITE_CONFIG"},
        {"EXIT_SITE_CHAIN"},
        {"EXIT_SITE_CUT"},
        {"EXIT_SITE_NONDETERMINISTIC"},
        {"EXIT_SITE_INVALID"},
    ]
```

- [ ] **Step 5: Kırmızıyı gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_schema.py tests/test_site_contract.py tests/test_site_import_rule.py tests/test_jev_budget.py`
Expected: toplama hatası `ModuleNotFoundError: No module named 'football_edge.site'`.

- [ ] **Step 6: Paketi, sözleşmeyi ve doğrulayıcıyı yaz**

`src/football_edge/site/__init__.py` (tam içerik):

````python
"""Halka açık sitenin okuma katmanı (Faz 6 İz B, B-1): dışa aktarım ve anlık görüntü sözleşmesi.

DB'ye yalnız bu paket dokunur, yalnız `site_reader` rolüyle ve yalnız `site`, `site_input`,
`site_audit` görünümlerinden (B2, B3). Paketin geçişli import kapanışı holdout'a, tarihsel tabana,
backtest'e ve `live.context`e ulaşamaz (H1f, `tests/test_site_import_rule.py`).
"""
````

`src/football_edge/site/contract.py` (tam içerik):

````python
"""Anlık görüntü sözleşmesinin Python tarafındaki sabitleri (Faz 6 İz B tasarımı §4–§5, §8).

Sayılar ve adlar TEK yerde: dışa aktarıcı, `verify-snapshot` ve testler buradan okur. Holdout tabanı
`history.holdout`tan import EDİLMEZ (H1f); eşitliği `tests/test_site_contract.py` kanıtlar.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from football_edge.ledger import _canonical

SCHEMA_VERSION = 1
SCHEMA_PATH = Path("web/contract/snapshot.schema.json")
DEVIG_CONFIG_PATH = Path("config/model_faz3.yaml")

# B4: holdout Londra'da 2026-07-01 00:00'da biter; bir günlük pay saat dilimini ve kaynak
# tarihi belirsizliğini kapatır. `site.public_floor()` aynı anı döner (0014, katalog testi).
PUBLIC_FLOOR = datetime(2026, 7, 2, tzinfo=UTC)

SITE_MIN_BOOKS = 3  # §5.2: bu kadar tam kitabı olmayan tur anlık görüntüde null
SITE_MIN_TEAM_MATCHES = 3  # §8.4: takım sayfasının indekslenebilirlik eşiği
MOVE_MIN_MATCHES = 5  # §5.2: ligin hareket dağılımı bu kadar mühürlü maçla yayımlanır
PATH_ID_LENGTH = 12  # §8.1: maç yolunda The Odds API olay kimliğinin öneki (çakışma kırmızı)

RESERVED_LEAGUE_SLUGS = frozenset({"track-record", "legal"})
RESERVED_TEAM_SLUGS = frozenset({"match"})

# `site.record` (B5): Faz 5 `publications`a AYNI ad, tip ve sırayla bağlanır. Katalog testi
# görünümün kolonlarını bu tuple'la karşılaştırır; sona eklenen kolon da kırmızıdır.
RECORD_COLUMNS: tuple[tuple[str, str], ...] = (
    ("publication_id", "bigint"),
    ("match_id", "text"),
    ("market", "text"),
    ("outcome", "text"),
    ("published_at", "timestamp with time zone"),
    ("published_price", "numeric"),
    ("publication_ledger_id", "bigint"),
    ("closing_fair_price", "numeric"),
    ("clv", "double precision"),
    ("publication_hash", "text"),
)

# §4.3: yayımlanmayan kolon adları — (site_input ∪ site_audit) − (site ∪ şemanın anahtarları).
# Katalogdan türetilmiş kümeye eşitliği `tests/test_site_views_db.py` sınar.
FORBIDDEN_KEYS = frozenset(
    {
        "bookmaker",
        "book_key",
        "ledger_id",
        "point",
        "price",
        "bookmaker_last_update",
        "prev_hash",
        "row_hash",
        "is_closing",
    }
)

# Çıkış kodları: collect 2–8 ve 19, backtest/market/live/jev 9–18 (tests/test_jev_budget.py).
EXIT_SITE_CONFIG = 20  # SITE_DATABASE_URL yok, --out boş değil, git SHA okunamadı
EXIT_SITE_CHAIN = 21  # çıpa ya da zincir doğrulanamadı; indirgeme de kırmızıdır
EXIT_SITE_CUT = 22  # kesim, görünüm, taban ya da sicil tutarsız
EXIT_SITE_NONDETERMINISTIC = 23  # ikinci türetim farklı content_sha256 üretti ya da düştü
EXIT_SITE_INVALID = 24  # verify-snapshot kırmızı

# İçerik hash'inin dışında kalan alanlar (§5.2): derleme anı ve kaynak sürümü içerik değildir.
OUTSIDE_CONTENT = ("generated_at", "git_sha", "content_sha256")


def iso_z(moment: datetime) -> str:
    """`2026-09-20T14:00:00Z` — anlık görüntünün tek zaman biçimi (mikrosaniye taşınmaz)."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_sha256(snapshot: Mapping[str, Any]) -> str:
    """`OUTSIDE_CONTENT` hariç gövdenin kanonik JSON'unun (`ledger._canonical`) sha256'sı."""
    inner = {key: value for key, value in snapshot.items() if key not in OUTSIDE_CONTENT}
    return hashlib.sha256(_canonical(inner).encode("utf-8")).hexdigest()
````

`src/football_edge/site/schema.py` (tam içerik):

````python
"""Anlık görüntü şemasının (`web/contract/snapshot.schema.json`) bağımlılıksız doğrulayıcısı.

JSON Schema'nın yalnız sözleşmenin kullandığı alt kümesi desteklenir. Şema bilinmeyen bir anahtar
kelime taşırsa `SchemaError` yükselir: doğrulayıcının SESSİZCE yok saydığı bir kural, sözleşmede
yazılı ama hiç sınanmayan bir kural olurdu. `additionalProperties` yalnız `false` olabilir (B6).
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import Any

SUPPORTED = frozenset(
    {
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "title",
        "description",
        "type",
        "const",
        "enum",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
    }
)
_TYPES = frozenset({"object", "array", "string", "integer", "number", "boolean", "null"})


class SchemaError(ValueError):
    """Şemanın kendisi desteklenen alt kümenin dışında."""


def check_schema(schema: Mapping[str, Any]) -> None:
    """Şemadaki her düğüm yalnız desteklenen anahtar kelimeleri taşır; nesneler kapalıdır."""
    for path, node in _nodes(schema, "#"):
        unknown = sorted(set(node) - SUPPORTED)
        if unknown:
            raise SchemaError(f"{path}: desteklenmeyen anahtar kelime {unknown}")
        if "additionalProperties" in node and node["additionalProperties"] is not False:
            raise SchemaError(f"{path}: additionalProperties yalnız false olabilir")
        if "properties" in node and node.get("additionalProperties") is not False:
            raise SchemaError(f"{path}: nesne additionalProperties: false taşımalı")
        kinds = node.get("type")
        declared = kinds if isinstance(kinds, list) else [kinds] if kinds is not None else []
        if not set(declared) <= _TYPES:
            raise SchemaError(f"{path}: bilinmeyen tip {declared}")
        ref = node.get("$ref")
        if ref is not None and _resolve(schema, ref) is None:
            raise SchemaError(f"{path}: çözülemeyen $ref {ref!r}")


def property_names(schema: Mapping[str, Any]) -> frozenset[str]:
    """Şemanın herhangi bir derinlikte bildirdiği bütün nesne anahtarları."""
    return frozenset(name for _, node in _nodes(schema, "#") for name in node.get("properties", {}))


def validate(instance: Any, schema: Mapping[str, Any]) -> list[str]:
    """Şemaya uymayan her yer için `<json yolu>: <neden>`; boş liste = geçerli."""
    return list(_errors(instance, schema, schema, "$"))


def _nodes(node: Any, path: str) -> Iterator[tuple[str, Mapping[str, Any]]]:
    if not isinstance(node, Mapping):
        return
    yield path, node
    for name, child in node.get("$defs", {}).items():
        yield from _nodes(child, f"{path}/$defs/{name}")
    for name, child in node.get("properties", {}).items():
        yield from _nodes(child, f"{path}/properties/{name}")
    if "items" in node:
        yield from _nodes(node["items"], f"{path}/items")


def _resolve(root: Mapping[str, Any], ref: str) -> Mapping[str, Any] | None:
    if not ref.startswith("#/$defs/"):
        return None
    found = root.get("$defs", {}).get(ref.removeprefix("#/$defs/"))
    return found if isinstance(found, Mapping) else None


def _type_ok(value: Any, kind: str) -> bool:
    if kind == "null":
        return value is None
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "array":
        return isinstance(value, list)
    return isinstance(value, dict)


def _errors(value: Any, node: Mapping[str, Any], root: Mapping[str, Any], at: str) -> Iterator[str]:
    if "$ref" in node:
        target = _resolve(root, node["$ref"])
        if target is None:
            raise SchemaError(f"çözülemeyen $ref {node['$ref']!r}")
        yield from _errors(value, target, root, at)
        return
    kinds = node.get("type")
    if kinds is not None:
        allowed = kinds if isinstance(kinds, list) else [kinds]
        if not any(_type_ok(value, kind) for kind in allowed):
            yield f"{at}: tip {allowed} bekleniyordu, {type(value).__name__} geldi"
            return
    if "const" in node and not _same(value, node["const"]):
        yield f"{at}: sabit {node['const']!r} bekleniyordu"
    if "enum" in node and not any(_same(value, option) for option in node["enum"]):
        yield f"{at}: {node['enum']} dışında"
    if isinstance(value, str):
        yield from _string_errors(value, node, at)
    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in node and value < node["minimum"]:
            yield f"{at}: {node['minimum']} altında"
        if "maximum" in node and value > node["maximum"]:
            yield f"{at}: {node['maximum']} üstünde"
    if isinstance(value, dict):
        yield from _object_errors(value, node, root, at)
    if isinstance(value, list) and "items" in node:
        for index, item in enumerate(value):
            yield from _errors(item, node["items"], root, f"{at}[{index}]")


def _string_errors(value: str, node: Mapping[str, Any], at: str) -> Iterator[str]:
    if "minLength" in node and len(value) < node["minLength"]:
        yield f"{at}: {node['minLength']} karakterden kısa"
    if "maxLength" in node and len(value) > node["maxLength"]:
        yield f"{at}: {node['maxLength']} karakterden uzun"
    if "pattern" in node and re.search(node["pattern"], value) is None:
        yield f"{at}: {node['pattern']!r} kalıbına uymuyor"


def _object_errors(
    value: dict[str, Any], node: Mapping[str, Any], root: Mapping[str, Any], at: str
) -> Iterator[str]:
    properties = node.get("properties", {})
    for name in node.get("required", []):
        if name not in value:
            yield f"{at}: zorunlu {name!r} yok"
    if node.get("additionalProperties") is False:
        for name in sorted(set(value) - set(properties)):
            yield f"{at}: bilinmeyen anahtar {name!r}"
    for name, child in properties.items():
        if name in value:
            yield from _errors(value[name], child, root, f"{at}.{name}")


def _same(left: Any, right: Any) -> bool:
    """JSON eşitliği: `True == 1` Python'da doğrudur, JSON'da değildir."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return bool(left == right)
````

- [ ] **Step 7: Şemayı yaz**

`web/contract/snapshot.schema.json` (tam içerik):

````json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://football-edge.invalid/contract/snapshot.schema.json",
  "title": "football-edge site anlık görüntüsü v1",
  "description": "Faz 6 İz B tasarımı §5.2. Sayılar görüntü hassasiyetindedir (§5.4): olasılık ve hareket yüzde puanı 1 ondalık, CLV yüzde 2 ondalık, fiyat 2 ondalık. Diziler adı geçen anahtarla artan sıralıdır. content_sha256 = generated_at, git_sha ve kendisi hariç gövdenin kanonik JSON'unun (sort_keys, ayırıcılar ',' ':', ensure_ascii=false) sha256'sı.",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "generated_at", "git_sha", "content_sha256", "ledger", "floor", "leagues", "teams", "matches", "record", "value_badge", "analysis"],
  "properties": {
    "schema_version": {"const": 1},
    "generated_at": {"$ref": "#/$defs/instant"},
    "git_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
    "content_sha256": {"$ref": "#/$defs/sha256"},
    "ledger": {
      "type": "object",
      "additionalProperties": false,
      "required": ["rows", "last_id", "head", "anchor"],
      "properties": {
        "rows": {"$ref": "#/$defs/count"},
        "last_id": {"$ref": "#/$defs/count"},
        "head": {"$ref": "#/$defs/sha256"},
        "anchor": {
          "type": "object",
          "additionalProperties": false,
          "required": ["file", "rows", "last_id", "head"],
          "properties": {
            "file": {"type": "string", "pattern": "^head-[0-9]{4}-[0-9]{2}-[0-9]{2}\\.txt$"},
            "rows": {"$ref": "#/$defs/count"},
            "last_id": {"$ref": "#/$defs/count"},
            "head": {"$ref": "#/$defs/sha256"}
          }
        }
      }
    },
    "floor": {"const": "2026-07-02T00:00:00Z"},
    "leagues": {
      "description": "Sıra: id.",
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "slug", "name", "country", "matches", "move_distribution"],
        "properties": {
          "id": {"$ref": "#/$defs/league_id"},
          "slug": {"$ref": "#/$defs/slug"},
          "name": {"$ref": "#/$defs/label"},
          "country": {"$ref": "#/$defs/label"},
          "matches": {"$ref": "#/$defs/count"},
          "move_distribution": {
            "description": "Mühürlü, en az iki turlu maçlarda |açılış→kapanış| hareketinin en büyük bileşeni, yüzde puanı; maç < 5 ise null.",
            "type": ["object", "null"],
            "additionalProperties": false,
            "required": ["p10", "p50", "p90"],
            "properties": {
              "p10": {"$ref": "#/$defs/points"},
              "p50": {"$ref": "#/$defs/points"},
              "p90": {"$ref": "#/$defs/points"}
            }
          }
        }
      }
    },
    "teams": {
      "description": "Sıra: (league_id, slug).",
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["league_id", "slug", "name", "matches", "indexable"],
        "properties": {
          "league_id": {"$ref": "#/$defs/league_id"},
          "slug": {"$ref": "#/$defs/slug"},
          "name": {"$ref": "#/$defs/label"},
          "matches": {"$ref": "#/$defs/count"},
          "indexable": {"type": "boolean"}
        }
      }
    },
    "matches": {
      "description": "Sıra: (commence_time, id).",
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "league_id", "path_id", "slug", "date", "commence_time", "home", "away", "sealed", "rounds", "h2h", "move", "indexable"],
        "properties": {
          "id": {"type": "string", "pattern": "^[0-9a-z]{12,64}$"},
          "league_id": {"$ref": "#/$defs/league_id"},
          "path_id": {"type": "string", "pattern": "^[0-9a-z]{12}$"},
          "slug": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*-vs-[a-z0-9]+(-[a-z0-9]+)*$", "maxLength": 170},
          "date": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
          "commence_time": {"$ref": "#/$defs/instant"},
          "home": {"$ref": "#/$defs/label"},
          "away": {"$ref": "#/$defs/label"},
          "sealed": {"type": "boolean"},
          "rounds": {"$ref": "#/$defs/count"},
          "h2h": {
            "type": "object",
            "additionalProperties": false,
            "required": ["opening", "latest", "closing"],
            "properties": {
              "opening": {"$ref": "#/$defs/round"},
              "latest": {"$ref": "#/$defs/round"},
              "closing": {"$ref": "#/$defs/round"}
            }
          },
          "move": {
            "description": "Açılış→kapanış (mühürsüzse son), yüzde puanı; iki uç da görünür değilse null.",
            "type": ["object", "null"],
            "additionalProperties": false,
            "required": ["home", "draw", "away"],
            "properties": {
              "home": {"$ref": "#/$defs/points"},
              "draw": {"$ref": "#/$defs/points"},
              "away": {"$ref": "#/$defs/points"}
            }
          },
          "indexable": {"type": "boolean"}
        }
      }
    },
    "record": {
      "type": "object",
      "additionalProperties": false,
      "required": ["published", "entries", "summary"],
      "properties": {
        "published": {"$ref": "#/$defs/count"},
        "entries": {
          "description": "Sıra: publication_id. site.record kolonları (B5).",
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["publication_id", "match_id", "market", "outcome", "published_at", "published_price", "publication_ledger_id", "closing_fair_price", "clv", "publication_hash"],
            "properties": {
              "publication_id": {"$ref": "#/$defs/count"},
              "match_id": {"type": "string", "pattern": "^[0-9a-z]{12,64}$"},
              "market": {"enum": ["h2h"]},
              "outcome": {"enum": ["home", "draw", "away"]},
              "published_at": {"$ref": "#/$defs/instant"},
              "published_price": {"$ref": "#/$defs/price"},
              "publication_ledger_id": {"$ref": "#/$defs/count"},
              "closing_fair_price": {"$ref": "#/$defs/price"},
              "clv": {"$ref": "#/$defs/percent2"},
              "publication_hash": {"$ref": "#/$defs/sha256"}
            }
          }
        },
        "summary": {
          "description": "n = 0 iken null.",
          "type": ["object", "null"],
          "additionalProperties": false,
          "required": ["mean_clv", "ci_low", "ci_high", "n"],
          "properties": {
            "mean_clv": {"$ref": "#/$defs/percent2"},
            "ci_low": {"$ref": "#/$defs/percent2"},
            "ci_high": {"$ref": "#/$defs/percent2"},
            "n": {"type": "integer", "minimum": 1}
          }
        }
      }
    },
    "value_badge": {"description": "Faz 5 şema sürümünü artırır (B6).", "const": null},
    "analysis": {"description": "Faz 7 şema sürümünü artırır (B6).", "const": null}
  },
  "$defs": {
    "instant": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"},
    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "count": {"type": "integer", "minimum": 0},
    "league_id": {"type": "string", "pattern": "^[a-z0-9]+(\\.[a-z0-9]+)*$", "maxLength": 20},
    "slug": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$", "maxLength": 80},
    "label": {"description": "Serbest metin yalnız takım, lig ve ülke adıdır (H2b).", "type": "string", "minLength": 1, "maxLength": 80},
    "points": {"description": "Yüzde puanı, 1 ondalık.", "type": "number", "minimum": -100, "maximum": 100},
    "percent": {"description": "Yüzde, 1 ondalık.", "type": "number", "minimum": 0, "maximum": 100},
    "percent2": {"description": "Yüzde, 2 ondalık.", "type": "number", "minimum": -100, "maximum": 10000},
    "price": {"description": "Ondalık oran, 2 ondalık.", "type": "number", "minimum": 1},
    "round": {
      "description": "Konsensüs turu; tam kitap sayısı 3'ün altındaysa null.",
      "type": ["object", "null"],
      "additionalProperties": false,
      "required": ["observed_at", "books", "p"],
      "properties": {
        "observed_at": {"$ref": "#/$defs/instant"},
        "books": {"type": "integer", "minimum": 3},
        "p": {
          "type": "object",
          "additionalProperties": false,
          "required": ["home", "draw", "away"],
          "properties": {
            "home": {"$ref": "#/$defs/percent"},
            "draw": {"$ref": "#/$defs/percent"},
            "away": {"$ref": "#/$defs/percent"}
          }
        }
      }
    }
  }
}
````

- [ ] **Step 8: Sentetik fixture'ları yaz**

Uydurma lig ve takım adları; `content_sha256` gövdenin gerçek hash'idir (Step 10 yeniden hesaplar). Bir satır
değiştirilirse hash de yeniden hesaplanmalı — elle düzenlemek yerine `content_sha256` testinin mesajı okunur.

`web/fixtures/snapshot.fixture.json` (tam içerik):

````json
{
  "analysis": null,
  "content_sha256": "3ad560eead2ffcd59794191c269c370d3ef6595cab6d66c2aa6b5193cc64e588",
  "floor": "2026-07-02T00:00:00Z",
  "generated_at": "2026-09-24T12:00:00Z",
  "git_sha": "0000000000000000000000000000000000000000",
  "leagues": [
    {"country": "Nordland", "id": "tst.1", "matches": 5, "move_distribution": {"p10": 1.3, "p50": 3.1, "p90": 4.6}, "name": "Kuzey Ligi", "slug": "kuzey-ligi"},
    {"country": "Südland", "id": "tst.2", "matches": 3, "move_distribution": null, "name": "Güney Kupası", "slug": "guney-kupasi"}
  ],
  "ledger": {"anchor": {"file": "head-2026-09-23.txt", "head": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "last_id": 128, "rows": 126}, "head": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "last_id": 137, "rows": 135},
  "matches": [
    {"away": "Beta FK", "commence_time": "2026-09-20T17:00:00Z", "date": "2026-09-20", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-20T16:00:00Z", "p": {"away": 23.2, "draw": 27.0, "home": 49.8}}, "latest": {"books": 3, "observed_at": "2026-09-20T16:00:00Z", "p": {"away": 23.2, "draw": 27.0, "home": 49.8}}, "opening": {"books": 3, "observed_at": "2026-09-19T00:00:00Z", "p": {"away": 26.0, "draw": 27.9, "home": 46.1}}}, "home": "Alfa Spor", "id": "1a10c0ffee0000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": -2.8, "draw": -0.9, "home": 3.7}, "path_id": "1a10c0ffee00", "rounds": 2, "sealed": true, "slug": "alfa-spor-vs-beta-fk"},
    {"away": "Alfa Spor", "commence_time": "2026-09-21T17:00:00Z", "date": "2026-09-21", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-21T16:00:00Z", "p": {"away": 36.7, "draw": 29.0, "home": 34.3}}, "latest": {"books": 3, "observed_at": "2026-09-21T16:00:00Z", "p": {"away": 36.7, "draw": 29.0, "home": 34.3}}, "opening": {"books": 3, "observed_at": "2026-09-19T01:00:00Z", "p": {"away": 34.0, "draw": 28.9, "home": 37.1}}}, "home": "Gamma United", "id": "2a20c0ffee1000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": 2.8, "draw": 0.0, "home": -2.8}, "path_id": "2a20c0ffee10", "rounds": 2, "sealed": true, "slug": "gamma-united-vs-alfa-spor"},
    {"away": "Delta Şehir", "commence_time": "2026-09-22T17:00:00Z", "date": "2026-09-22", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-22T16:00:00Z", "p": {"away": 19.6, "draw": 26.2, "home": 54.2}}, "latest": {"books": 3, "observed_at": "2026-09-22T16:00:00Z", "p": {"away": 19.6, "draw": 26.2, "home": 54.2}}, "opening": {"books": 3, "observed_at": "2026-09-19T02:00:00Z", "p": {"away": 22.0, "draw": 26.9, "home": 51.1}}}, "home": "Beta FK", "id": "3a30c0ffee2000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": -2.4, "draw": -0.7, "home": 3.1}, "path_id": "3a30c0ffee20", "rounds": 2, "sealed": true, "slug": "beta-fk-vs-delta-sehir"},
    {"away": "Gamma United", "commence_time": "2026-09-23T17:00:00Z", "date": "2026-09-23", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-23T16:00:00Z", "p": {"away": 31.2, "draw": 29.0, "home": 39.9}}, "latest": {"books": 3, "observed_at": "2026-09-23T16:00:00Z", "p": {"away": 31.2, "draw": 29.0, "home": 39.9}}, "opening": {"books": 3, "observed_at": "2026-09-19T03:00:00Z", "p": {"away": 31.0, "draw": 29.3, "home": 39.7}}}, "home": "Delta Şehir", "id": "4a40c0ffee3000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": 0.2, "draw": -0.3, "home": 0.2}, "path_id": "4a40c0ffee30", "rounds": 2, "sealed": true, "slug": "delta-sehir-vs-gamma-united"},
    {"away": "Delta Şehir", "commence_time": "2026-09-24T17:00:00Z", "date": "2026-09-24", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-24T16:00:00Z", "p": {"away": 16.2, "draw": 22.9, "home": 60.9}}, "latest": {"books": 3, "observed_at": "2026-09-24T16:00:00Z", "p": {"away": 16.2, "draw": 22.9, "home": 60.9}}, "opening": {"books": 3, "observed_at": "2026-09-19T04:00:00Z", "p": {"away": 19.8, "draw": 24.5, "home": 55.6}}}, "home": "Alfa Spor", "id": "5a50c0ffee4000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": -3.7, "draw": -1.6, "home": 5.3}, "path_id": "5a50c0ffee40", "rounds": 2, "sealed": true, "slug": "alfa-spor-vs-delta-sehir"},
    {"away": "Zeta Rovers", "commence_time": "2026-09-27T18:30:00Z", "date": "2026-09-27", "h2h": {"closing": null, "latest": {"books": 3, "observed_at": "2026-09-23T09:00:00Z", "p": {"away": 28.4, "draw": 29.7, "home": 41.9}}, "opening": {"books": 3, "observed_at": "2026-09-21T09:00:00Z", "p": {"away": 31.3, "draw": 30.5, "home": 38.2}}}, "home": "Epsilon Athletic", "id": "b2c0ffee000000000000000000000001", "indexable": true, "league_id": "tst.2", "move": {"away": -2.8, "draw": -0.8, "home": 3.7}, "path_id": "b2c0ffee0000", "rounds": 2, "sealed": false, "slug": "epsilon-athletic-vs-zeta-rovers"},
    {"away": "Eta Kent", "commence_time": "2026-09-28T15:00:00Z", "date": "2026-09-28", "h2h": {"closing": null, "latest": {"books": 3, "observed_at": "2026-09-23T10:00:00Z", "p": {"away": 23.8, "draw": 27.8, "home": 48.5}}, "opening": {"books": 3, "observed_at": "2026-09-23T10:00:00Z", "p": {"away": 23.8, "draw": 27.8, "home": 48.5}}}, "home": "Zeta Rovers", "id": "b3c0ffee000000000000000000000002", "indexable": false, "league_id": "tst.2", "move": {"away": 0.0, "draw": 0.0, "home": 0.0}, "path_id": "b3c0ffee0000", "rounds": 1, "sealed": false, "slug": "zeta-rovers-vs-eta-kent"},
    {"away": "Epsilon Athletic", "commence_time": "2026-09-29T19:00:00Z", "date": "2026-09-29", "h2h": {"closing": null, "latest": {"books": 3, "observed_at": "2026-09-23T11:00:00Z", "p": {"away": 28.4, "draw": 28.7, "home": 42.9}}, "opening": null}, "home": "Eta Kent", "id": "b4c0ffee000000000000000000000003", "indexable": true, "league_id": "tst.2", "move": null, "path_id": "b4c0ffee0000", "rounds": 2, "sealed": false, "slug": "eta-kent-vs-epsilon-athletic"}
  ],
  "record": {"entries": [], "published": 0, "summary": null},
  "schema_version": 1,
  "teams": [
    {"indexable": true, "league_id": "tst.1", "matches": 3, "name": "Alfa Spor", "slug": "alfa-spor"},
    {"indexable": false, "league_id": "tst.1", "matches": 2, "name": "Beta FK", "slug": "beta-fk"},
    {"indexable": true, "league_id": "tst.1", "matches": 3, "name": "Delta Şehir", "slug": "delta-sehir"},
    {"indexable": false, "league_id": "tst.1", "matches": 2, "name": "Gamma United", "slug": "gamma-united"},
    {"indexable": false, "league_id": "tst.2", "matches": 2, "name": "Epsilon Athletic", "slug": "epsilon-athletic"},
    {"indexable": false, "league_id": "tst.2", "matches": 2, "name": "Eta Kent", "slug": "eta-kent"},
    {"indexable": false, "league_id": "tst.2", "matches": 2, "name": "Zeta Rovers", "slug": "zeta-rovers"}
  ],
  "value_badge": null
}
````

`web/fixtures/snapshot.fixture-record.json` (tam içerik):

````json
{
  "analysis": null,
  "content_sha256": "0d8154a3014e0afcfbd85a965cd210519ac4db1a6c2d0b1b6665558967e0e628",
  "floor": "2026-07-02T00:00:00Z",
  "generated_at": "2026-09-24T12:00:00Z",
  "git_sha": "0000000000000000000000000000000000000000",
  "leagues": [
    {"country": "Nordland", "id": "tst.1", "matches": 5, "move_distribution": {"p10": 1.3, "p50": 3.1, "p90": 4.6}, "name": "Kuzey Ligi", "slug": "kuzey-ligi"},
    {"country": "Südland", "id": "tst.2", "matches": 3, "move_distribution": null, "name": "Güney Kupası", "slug": "guney-kupasi"}
  ],
  "ledger": {"anchor": {"file": "head-2026-09-23.txt", "head": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "last_id": 128, "rows": 126}, "head": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "last_id": 137, "rows": 135},
  "matches": [
    {"away": "Beta FK", "commence_time": "2026-09-20T17:00:00Z", "date": "2026-09-20", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-20T16:00:00Z", "p": {"away": 23.2, "draw": 27.0, "home": 49.8}}, "latest": {"books": 3, "observed_at": "2026-09-20T16:00:00Z", "p": {"away": 23.2, "draw": 27.0, "home": 49.8}}, "opening": {"books": 3, "observed_at": "2026-09-19T00:00:00Z", "p": {"away": 26.0, "draw": 27.9, "home": 46.1}}}, "home": "Alfa Spor", "id": "1a10c0ffee0000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": -2.8, "draw": -0.9, "home": 3.7}, "path_id": "1a10c0ffee00", "rounds": 2, "sealed": true, "slug": "alfa-spor-vs-beta-fk"},
    {"away": "Alfa Spor", "commence_time": "2026-09-21T17:00:00Z", "date": "2026-09-21", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-21T16:00:00Z", "p": {"away": 36.7, "draw": 29.0, "home": 34.3}}, "latest": {"books": 3, "observed_at": "2026-09-21T16:00:00Z", "p": {"away": 36.7, "draw": 29.0, "home": 34.3}}, "opening": {"books": 3, "observed_at": "2026-09-19T01:00:00Z", "p": {"away": 34.0, "draw": 28.9, "home": 37.1}}}, "home": "Gamma United", "id": "2a20c0ffee1000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": 2.8, "draw": 0.0, "home": -2.8}, "path_id": "2a20c0ffee10", "rounds": 2, "sealed": true, "slug": "gamma-united-vs-alfa-spor"},
    {"away": "Delta Şehir", "commence_time": "2026-09-22T17:00:00Z", "date": "2026-09-22", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-22T16:00:00Z", "p": {"away": 19.6, "draw": 26.2, "home": 54.2}}, "latest": {"books": 3, "observed_at": "2026-09-22T16:00:00Z", "p": {"away": 19.6, "draw": 26.2, "home": 54.2}}, "opening": {"books": 3, "observed_at": "2026-09-19T02:00:00Z", "p": {"away": 22.0, "draw": 26.9, "home": 51.1}}}, "home": "Beta FK", "id": "3a30c0ffee2000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": -2.4, "draw": -0.7, "home": 3.1}, "path_id": "3a30c0ffee20", "rounds": 2, "sealed": true, "slug": "beta-fk-vs-delta-sehir"},
    {"away": "Gamma United", "commence_time": "2026-09-23T17:00:00Z", "date": "2026-09-23", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-23T16:00:00Z", "p": {"away": 31.2, "draw": 29.0, "home": 39.9}}, "latest": {"books": 3, "observed_at": "2026-09-23T16:00:00Z", "p": {"away": 31.2, "draw": 29.0, "home": 39.9}}, "opening": {"books": 3, "observed_at": "2026-09-19T03:00:00Z", "p": {"away": 31.0, "draw": 29.3, "home": 39.7}}}, "home": "Delta Şehir", "id": "4a40c0ffee3000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": 0.2, "draw": -0.3, "home": 0.2}, "path_id": "4a40c0ffee30", "rounds": 2, "sealed": true, "slug": "delta-sehir-vs-gamma-united"},
    {"away": "Delta Şehir", "commence_time": "2026-09-24T17:00:00Z", "date": "2026-09-24", "h2h": {"closing": {"books": 3, "observed_at": "2026-09-24T16:00:00Z", "p": {"away": 16.2, "draw": 22.9, "home": 60.9}}, "latest": {"books": 3, "observed_at": "2026-09-24T16:00:00Z", "p": {"away": 16.2, "draw": 22.9, "home": 60.9}}, "opening": {"books": 3, "observed_at": "2026-09-19T04:00:00Z", "p": {"away": 19.8, "draw": 24.5, "home": 55.6}}}, "home": "Alfa Spor", "id": "5a50c0ffee4000000000000000000000", "indexable": true, "league_id": "tst.1", "move": {"away": -3.7, "draw": -1.6, "home": 5.3}, "path_id": "5a50c0ffee40", "rounds": 2, "sealed": true, "slug": "alfa-spor-vs-delta-sehir"},
    {"away": "Zeta Rovers", "commence_time": "2026-09-27T18:30:00Z", "date": "2026-09-27", "h2h": {"closing": null, "latest": {"books": 3, "observed_at": "2026-09-23T09:00:00Z", "p": {"away": 28.4, "draw": 29.7, "home": 41.9}}, "opening": {"books": 3, "observed_at": "2026-09-21T09:00:00Z", "p": {"away": 31.3, "draw": 30.5, "home": 38.2}}}, "home": "Epsilon Athletic", "id": "b2c0ffee000000000000000000000001", "indexable": true, "league_id": "tst.2", "move": {"away": -2.8, "draw": -0.8, "home": 3.7}, "path_id": "b2c0ffee0000", "rounds": 2, "sealed": false, "slug": "epsilon-athletic-vs-zeta-rovers"},
    {"away": "Eta Kent", "commence_time": "2026-09-28T15:00:00Z", "date": "2026-09-28", "h2h": {"closing": null, "latest": {"books": 3, "observed_at": "2026-09-23T10:00:00Z", "p": {"away": 23.8, "draw": 27.8, "home": 48.5}}, "opening": {"books": 3, "observed_at": "2026-09-23T10:00:00Z", "p": {"away": 23.8, "draw": 27.8, "home": 48.5}}}, "home": "Zeta Rovers", "id": "b3c0ffee000000000000000000000002", "indexable": false, "league_id": "tst.2", "move": {"away": 0.0, "draw": 0.0, "home": 0.0}, "path_id": "b3c0ffee0000", "rounds": 1, "sealed": false, "slug": "zeta-rovers-vs-eta-kent"},
    {"away": "Epsilon Athletic", "commence_time": "2026-09-29T19:00:00Z", "date": "2026-09-29", "h2h": {"closing": null, "latest": {"books": 3, "observed_at": "2026-09-23T11:00:00Z", "p": {"away": 28.4, "draw": 28.7, "home": 42.9}}, "opening": null}, "home": "Eta Kent", "id": "b4c0ffee000000000000000000000003", "indexable": true, "league_id": "tst.2", "move": null, "path_id": "b4c0ffee0000", "rounds": 2, "sealed": false, "slug": "eta-kent-vs-epsilon-athletic"}
  ],
  "record": {
    "entries": [
      {"closing_fair_price": 2.01, "clv": 2.14, "market": "h2h", "match_id": "1a10c0ffee0000000000000000000000", "outcome": "home", "publication_hash": "1111111111111111111111111111111111111111111111111111111111111111", "publication_id": 1, "publication_ledger_id": 3, "published_at": "2026-09-19T21:00:00Z", "published_price": 2.05},
      {"closing_fair_price": 2.72, "clv": 0.96, "market": "h2h", "match_id": "2a20c0ffee1000000000000000000000", "outcome": "away", "publication_hash": "2222222222222222222222222222222222222222222222222222222222222222", "publication_id": 2, "publication_ledger_id": 6, "published_at": "2026-09-20T21:00:00Z", "published_price": 2.75}
    ],
    "published": 2,
    "summary": {"ci_high": 2.14, "ci_low": 0.96, "mean_clv": 1.55, "n": 2}
  },
  "schema_version": 1,
  "teams": [
    {"indexable": true, "league_id": "tst.1", "matches": 3, "name": "Alfa Spor", "slug": "alfa-spor"},
    {"indexable": false, "league_id": "tst.1", "matches": 2, "name": "Beta FK", "slug": "beta-fk"},
    {"indexable": true, "league_id": "tst.1", "matches": 3, "name": "Delta Şehir", "slug": "delta-sehir"},
    {"indexable": false, "league_id": "tst.1", "matches": 2, "name": "Gamma United", "slug": "gamma-united"},
    {"indexable": false, "league_id": "tst.2", "matches": 2, "name": "Epsilon Athletic", "slug": "epsilon-athletic"},
    {"indexable": false, "league_id": "tst.2", "matches": 2, "name": "Eta Kent", "slug": "eta-kent"},
    {"indexable": false, "league_id": "tst.2", "matches": 2, "name": "Zeta Rovers", "slug": "zeta-rovers"}
  ],
  "value_badge": null
}
````

- [ ] **Step 9: `.gitignore`**

Dosyanın SONUNA ekle:
```gitignore

# Faz 6 İz B (§5.2, §13): derleme çıktıları ve gerçek anlık görüntü depoya girmez.
web/node_modules/
web/.next/
web/out/
web/.snapshot/
```

- [ ] **Step 10: Yeşili gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_schema.py tests/test_site_contract.py tests/test_site_import_rule.py tests/test_jev_budget.py`
Expected: `65 passed` (21 + 14 + 4 + 26).

- [ ] **Step 11: Mutasyonla kırmızı kanıtı** (Global Constraints'teki `mutate` kalıbı; her biri ayrı, geri yüklenir)

| Dosya | Eski → yeni | Kırmızı olması gereken |
|---|---|---|
| `src/football_edge/site/schema.py` | `return isinstance(value, int) and not isinstance(value, bool)` → `return isinstance(value, int)` | `test_site_schema.py`: 1 failed (`{"n": True}` vakası) |
| `src/football_edge/site/contract.py` | `from football_edge.ledger import _canonical` → aynı satır + `\nfrom football_edge.history.holdout import HOLDOUT_END  # noqa: F401` | `test_site_import_rule.py`: 2 failed (statik kapanış + ayrı süreç) |
| `web/fixtures/snapshot.fixture.json` | `"rounds": 2, "sealed": true` → `"rounds": 3, "sealed": true` (ilk eşleşme) | `test_site_contract.py`: 1 failed (içerik hash'i) |

İkinci satırın `mutate` çağrısı: `mutate src/football_edge/site/contract.py 'from football_edge.ledger import _canonical' $'from football_edge.ledger import _canonical\nfrom football_edge.history.holdout import HOLDOUT_END  # noqa: F401'`.
Rapora: her mutasyonun `N failed` satırı, `cmp` çıktısının boşluğu ve geri yükleme sonrası `65 passed`.

- [ ] **Step 12: Lint ve tip**

Run: `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`
Expected: `All checks passed!` · `… files already formatted` · `Success: no issues found in N source files`

- [ ] **Step 13: Tam kapı**

Run: `TMPDIR=$(mktemp -d) ./verify.sh > "$TMPDIR/verify.log" 2>&1; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$TMPDIR/verify.log"`
Expected: `10 PASS` + `SKIP: zincir (DATABASE_URL yok)` + `KAPI YEŞİL`. Eklenen `leakage` testi: 5 (sözleşme 1, bekçi 4);
`verify.sh`ye DOKUNULMAZ (sayı Task 9'da ölçülür).

- [ ] **Step 14: Commit**

```bash
git add src/football_edge/site/__init__.py src/football_edge/site/contract.py src/football_edge/site/schema.py \
  web/contract/snapshot.schema.json web/fixtures/snapshot.fixture.json web/fixtures/snapshot.fixture-record.json \
  tests/test_site_schema.py tests/test_site_contract.py tests/test_site_import_rule.py tests/test_jev_budget.py .gitignore
git commit -m "feat: site anlık görüntü sözleşmesi — şema, sentetik fixture'lar, doğrulayıcı, import bekçisi (Faz 6 B-1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Konsensüs yaprak modülü, zincir okuyucusunun parametrelenmesi, tek yazar varsayımı

**Kademe:** K1 · **Spec:** §4.3 ("Konsensüs tanımı tek"), §6.4/3a (okuyucu parametrelemesi + envanter), §5.1/3
(`lock_ledger` varsayımı), H1f · **Bağımlılık:** Task 1 · **Worktree:** `wt-b1-t2`

`pre_prices`in gövdesindeki tur konsensüsü (tam kitapların ortalaması) yaprak modüle taşınır; `Quote`, `LIVE_H2H`,
`LIVE_DRAW` de taşınır ve `live.context`ten AÇIKÇA yeniden dışa verilir (mypy strict örtük yeniden dışa vermeyi kabul
etmez; `live/store.py` ve testlerin importları değişmez). `"Avg"` literali `consensus.py`de GEÇMEZ
(`test_single_sources.py`). Zincir okuyucusu kolon tuple'ı + kapalı bir ilişki kümesiyle parametrelenir: site aynı
fonksiyonlarla `site_audit.ledger_rows`dan okur — ikinci bir okuyucu yazılmaz.

**`odds_snapshots` okuyucularının envanteri (§6.4/3a, bu planın yazıldığı ağaçta ölçüldü):** `collect.py`
(`_ledger_rows`, `_ledger_row`, `_anchor_break` — bu görev parametreler; `_publish_head_command`in sayımı), `db.py`
(`chain_head`, yazar `INSERT_SNAPSHOTS`), `live/store.py` (`_QUOTES`, `_CLOSING`), `market/bridge.py` (join).
Site yalnız parametrelenen üçlüyü kullanır; ötekiler boru hattınındır ve bu görevde değişmez.

**Files:**
- Create: `src/football_edge/market/consensus.py`
- Modify: `src/football_edge/live/context.py` (importlar, `Quote` sınıfının kaldırılması, `pre_prices` gövdesi)
- Modify: `src/football_edge/collect.py` (`_LEDGER_*` sabitleri → tuple + ilişki kümesi; `_ledger_rows`, `_ledger_row`,
  `_anchor_break`, `_first_anchor_break` imzaları)
- Test: `tests/test_market_consensus.py`, `tests/test_ledger_readers.py`

**Interfaces:**
- Consumes: `football_edge.history.types.RESULTS` (`("H", "D", "A")`).
- Produces (Task 3, 5, 6):
  ```python
  # football_edge.market.consensus
  LIVE_H2H = "h2h"; LIVE_DRAW = "Draw"
  @dataclass(frozen=True) class Quote: match_id: str; observed_at: datetime; bookmaker: str; market: str; outcome: str; price: float
  @dataclass(frozen=True) class RoundConsensus: means: tuple[float, float, float]; books: int
  def round_consensus(quotes: Sequence[Quote], observed_at: datetime, home: str, away: str) -> RoundConsensus | None
  # football_edge.collect
  LEDGER_TABLE = "odds_snapshots"; LEDGER_AUDIT_VIEW = "site_audit.ledger_rows"
  LEDGER_RELATIONS = frozenset({LEDGER_TABLE, LEDGER_AUDIT_VIEW})
  _LEDGER_COLUMNS: tuple[str, ...]   # match_id … row_hash (11 kolon, hash'lenen sıra)
  def _ledger_rows(conn, after_id: int | None, *, relation: str = LEDGER_TABLE) -> tuple[dict[str, Any], ...]
  def _ledger_row(conn, row_id: int, *, relation: str = LEDGER_TABLE) -> dict[str, Any] | None
  def _anchor_break(conn, anchor: Anchor, *, relation: str = LEDGER_TABLE) -> str | None
  def _first_anchor_break(conn, anchors: tuple[Anchor, ...], *, relation: str = LEDGER_TABLE) -> str | None
  ```
  Kapalı küme dışındaki ilişki `ValueError("bilinmeyen defter ilişkisi: …")`.

- [ ] **Step 1: Konsensüs testini yaz**

`tests/test_market_consensus.py` (tam içerik):

````python
"""Tur konsensüsü tek tanım (Faz 6 İz B §4.3): yaprak modül; `pre_prices` ve site onu çağırır."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, OddsKey
from football_edge.live import context
from football_edge.live.context import LiveMatch, pre_prices
from football_edge.market.consensus import LIVE_DRAW, LIVE_H2H, Quote, round_consensus

SRC = Path(__file__).resolve().parent.parent / "src" / "football_edge"
T0 = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
MATCH = LiveMatch("m1", "tst.1", T1 + timedelta(hours=5), "Ev", "Dep")


def _book(book: str, at: datetime, prices: tuple[float, float, float]) -> list[Quote]:
    return [
        Quote("m1", at, book, LIVE_H2H, name, price)
        for name, price in zip(("Ev", LIVE_DRAW, "Dep"), prices, strict=True)
    ]


QUOTES = [
    *_book("a", T0, (2.0, 3.0, 4.0)),
    *_book("b", T0, (2.2, 3.2, 3.8)),
    *_book("a", T1, (2.1, 3.1, 3.9)),
    *_book("b", T1, (2.3, 3.3, 3.7)),
    Quote("m1", T1, "c", LIVE_H2H, "Ev", 9.0),  # eksik kitap: ev ve beraberlik var, deplasman yok
    Quote("m1", T1, "c", LIVE_H2H, LIVE_DRAW, 9.0),
    Quote("m1", T1, "a", "totals", "Over", 1.9),  # başka market
]


def test_the_round_mean_uses_only_full_books_of_that_round() -> None:
    found = round_consensus(QUOTES, T1, "Ev", "Dep")

    assert found is not None
    assert found.books == 2
    assert found.means == pytest.approx((2.2, 3.2, 3.8))


def test_a_round_without_a_full_book_has_no_consensus() -> None:
    assert round_consensus([Quote("m1", T0, "a", LIVE_H2H, "Ev", 2.0)], T0, "Ev", "Dep") is None
    assert round_consensus(QUOTES, T1 + timedelta(minutes=1), "Ev", "Dep") is None


def test_pre_prices_is_the_latest_round_consensus_under_the_reference_key() -> None:
    """Davranış eşitliği: `pre_prices` = karar anından önceki SON turun `round_consensus`u."""
    found = pre_prices(QUOTES, MATCH, T1)
    expected = round_consensus(QUOTES, T1, "Ev", "Dep")

    assert found is not None and expected is not None
    assert [found[OddsKey(context.REFERENCE_BOOK, H2H, o, PRE_CLOSING)] for o in RESULTS] == list(
        expected.means
    )
    assert pre_prices(QUOTES, MATCH, T0 - timedelta(seconds=1)) is None


def test_live_context_re_exports_the_moved_names() -> None:
    """`live/store.py` ve testler importlarını değiştirmez."""
    assert context.Quote is Quote
    assert (context.LIVE_H2H, context.LIVE_DRAW) == (LIVE_H2H, LIVE_DRAW)


def test_the_consensus_module_is_a_leaf_that_imports_only_history_types() -> None:
    tree = ast.parse((SRC / "market" / "consensus.py").read_text(encoding="utf-8"))
    internal = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("football_edge")
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.startswith("football_edge")
    }

    assert internal == {"football_edge.history.types"}
````

- [ ] **Step 2: Okuyucu ve tek yazar testini yaz**

`tests/test_ledger_readers.py` (tam içerik):

````python
"""Defterin tek okuyucusu ve tek yazarı (Faz 6 İz B §5.1/3, §6.4/3a).

(1) Zincir okuyucusu (`collect._ledger_rows`, `_ledger_row`, `_anchor_break`) iki ilişkiden okur —
`odds_snapshots` ve `site_audit.ledger_rows` — ve yalnız bu kapalı kümeden; ikinci bir okuyucu
yazılmaz. (2) Anlık görüntünün kesimi (`max(id)`) defter yazımlarının `lock_ledger` ile
serileştiği varsayımına dayanır: `odds_snapshots`a INSERT yapan tek yol `db.insert_snapshots`tir ve
ilk ifadesi kilittir. Kilitsiz bir yazar eklenirse bu dosya kırmızı olur. Canlı DB'ye elle SQL ile
yazmayı durdurmaz (§12.4/14).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest

from football_edge.anchors import Anchor
from football_edge.collect import (
    _LEDGER_COLUMNS,
    LEDGER_AUDIT_VIEW,
    LEDGER_RELATIONS,
    LEDGER_TABLE,
    _anchor_break,
    _ledger_row,
    _ledger_rows,
)
from tests.fake_db import LEDGER_COLUMNS, FakeChainDb, chained_rows

REPO = Path(__file__).resolve().parent.parent
WRITE = re.compile(r"\b(?:insert\s+into|copy)\s+(?:public\.)?odds_snapshots\b", re.IGNORECASE)


class _Recording:
    """`FakeChainDb`in gönderilen SQL'i kaydeden sargısı."""

    def __init__(self) -> None:
        self.db = FakeChainDb(chained_rows(3))
        self.seen: list[str] = []

    def cursor(self) -> Any:
        cursor = self.db.cursor()
        original = cursor.execute

        def execute(sql: str, params: Any = None) -> None:
            self.seen.append(" ".join(sql.split()))
            original(sql, params)

        cursor.execute = execute  # type: ignore[method-assign]
        return cursor


def test_the_hashed_columns_are_one_tuple_shared_with_the_test_fake() -> None:
    assert _LEDGER_COLUMNS == LEDGER_COLUMNS


@pytest.mark.parametrize("relation", [LEDGER_TABLE, LEDGER_AUDIT_VIEW])
def test_every_reader_reads_the_relation_it_is_given(relation: str) -> None:
    db = _Recording()
    rows = _ledger_rows(db, None, relation=relation)  # type: ignore[arg-type]
    _ledger_row(db, 2, relation=relation)  # type: ignore[arg-type]
    _anchor_break(db, Anchor(Path("x"), 3, 3, str(rows[-1]["row_hash"])), relation=relation)  # type: ignore[arg-type]

    assert db.seen and all(text.split(" FROM ")[1].split()[0] == relation for text in db.seen)


def test_a_relation_outside_the_closed_set_is_refused() -> None:
    with pytest.raises(ValueError, match="bilinmeyen defter ilişkisi"):
        _ledger_rows(FakeChainDb(chained_rows(1)), None, relation="odds_snapshots; drop")  # type: ignore[arg-type]
    assert {"odds_snapshots", "site_audit.ledger_rows"} == LEDGER_RELATIONS


def test_the_only_ledger_writer_is_insert_snapshots_and_it_locks_first() -> None:
    """Envanter: `odds_snapshots`a yazan metin yalnız `db.INSERT_SNAPSHOTS`; SQL fonksiyonu yok."""
    writers = sorted(
        path.relative_to(REPO).as_posix()
        for root in ("src", "scripts", "db/migrations")
        for path in (REPO / root).rglob("*")
        if path.suffix in {".py", ".sql", ".sh"} and WRITE.search(path.read_text(encoding="utf-8"))
    )
    tree = ast.parse((REPO / "src/football_edge/db.py").read_text(encoding="utf-8"))
    users = sorted(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(isinstance(n, ast.Name) and n.id == "INSERT_SNAPSHOTS" for n in ast.walk(node))
    )
    (writer,) = [
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "insert_snapshots"
    ]
    first = [
        s
        for s in writer.body
        if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
    ][0]

    assert writers == ["src/football_edge/db.py"]
    assert users == ["insert_snapshots"]
    assert isinstance(first, ast.Expr) and ast.unparse(first) == "lock_ledger(conn)"
````

- [ ] **Step 3: Kırmızıyı gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_market_consensus.py tests/test_ledger_readers.py`
Expected: toplama hatası — `No module named 'football_edge.market.consensus'` ve `cannot import name 'LEDGER_AUDIT_VIEW'`.

- [ ] **Step 4: Yaprak modülü yaz**

`src/football_edge/market/consensus.py` (tam içerik):

````python
"""Tur konsensüsü: bir snapshot turunun 1X2'sinde üç sonucu da fiyatlayan kitapların ortalaması.

Tanım TEKTİR (Faz 6 İz B tasarımı §4.3): canlı karar fiyatı (`live.context.pre_prices`), mühürlü
kapanış (`live.store.load_closing`, `pre_prices` üzerinden) ve sitenin dışa aktarımı
(`football_edge.site`) bu fonksiyonu çağırır. Yaprak modüldür, yalnız `history.types`i import
eder: `live.context` `backtest.*` ve `history.catalog` taşıdığı için site onu import edemez (H1f).
Referans kitap anahtarını (`OddsKey(REFERENCE_BOOK, …)`) burada kimse kurmaz; o `pre_prices`in
işidir.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from football_edge.history.types import RESULTS

LIVE_H2H = "h2h"
LIVE_DRAW = "Draw"


@dataclass(frozen=True)
class Quote:
    match_id: str
    observed_at: datetime
    bookmaker: str
    market: str
    outcome: str
    price: float


@dataclass(frozen=True)
class RoundConsensus:
    means: tuple[float, float, float]  # RESULTS sırasıyla (H, D, A), ham ortalama fiyat
    books: int  # üç sonucu da fiyatlayan kitap sayısı


def round_consensus(
    quotes: Sequence[Quote], observed_at: datetime, home: str, away: str
) -> RoundConsensus | None:
    """`observed_at` turunun 1X2'si: üç sonucu tam kitapların ortalama fiyatı; tam kitap yoksa None.

    Sonuç adı The Odds API'nin yazımıdır: ev takımının adı, `Draw`, deplasman takımının adı.
    """
    names = {home: "H", LIVE_DRAW: "D", away: "A"}
    books: dict[str, dict[str, float]] = {}
    for quote in quotes:
        if quote.market == LIVE_H2H and quote.observed_at == observed_at and quote.outcome in names:
            books.setdefault(quote.bookmaker, {})[names[quote.outcome]] = quote.price
    full = [book for book in books.values() if set(book) == set(RESULTS)]
    if not full:
        return None
    home_mean, draw_mean, away_mean = (
        math.fsum(book[outcome] for book in full) / len(full) for outcome in RESULTS
    )
    return RoundConsensus((home_mean, draw_mean, away_mean), len(full))
````

- [ ] **Step 5: `live/context.py`yi yaprak modüle bağla** (üç düzenleme)

```python
# ESKİ
import math
from collections.abc import Mapping, Sequence
# YENİ
from collections.abc import Mapping, Sequence
```
```python
# ESKİ
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, HistMatch, OddsKey
from football_edge.naming import normalise_team

LIVE_H2H = "h2h"
LIVE_DRAW = "Draw"
REFERENCE_BOOK = "Avg"
# YENİ
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, HistMatch, OddsKey
from football_edge.market.consensus import LIVE_DRAW as LIVE_DRAW
from football_edge.market.consensus import LIVE_H2H as LIVE_H2H
from football_edge.market.consensus import Quote as Quote
from football_edge.market.consensus import round_consensus
from football_edge.naming import normalise_team

REFERENCE_BOOK = "Avg"
```
(`REFERENCE_BOOK` satırının sonundaki yorum aynen kalır.) `@dataclass(frozen=True) class Quote:` bloğunun tamamı
(altı alan ve ardından gelen iki boş satır) buradan kaldırılır — sınıf `market/consensus.py`ye TAŞINDI. `pre_prices` şöyle olur:

```python
def pre_prices(
    quotes: Sequence[Quote], match: LiveMatch, decided: datetime
) -> Mapping[OddsKey, float] | None:
    """Karar anında ya da önce gözlenen SON snapshot turunun 1X2'si, üç sonucu tam kitapların
    ortalaması (`market.consensus.round_consensus`); tam kitap yoksa None."""
    usable = [q for q in quotes if q.market == LIVE_H2H and q.observed_at <= decided]
    if not usable:
        return None
    latest = max(q.observed_at for q in usable)
    found = round_consensus(usable, latest, match.home, match.away)
    if found is None:
        return None
    return MappingProxyType(
        {
            OddsKey(REFERENCE_BOOK, H2H, outcome, PRE_CLOSING): mean
            for outcome, mean in zip(RESULTS, found.means, strict=True)
        }
    )
```

- [ ] **Step 6: Zincir okuyucusunu parametrele** (`src/football_edge/collect.py`, dört düzenleme)

```python
# ESKİ
_LEDGER_COLUMNS = """
    SELECT match_id, observed_at, bookmaker, market, outcome, point, price,
           bookmaker_last_update, is_closing, prev_hash, row_hash
    FROM odds_snapshots
"""
_LEDGER_ALL = _LEDGER_COLUMNS + " ORDER BY id"
_LEDGER_AFTER = _LEDGER_COLUMNS + " WHERE id > %s ORDER BY id"
_LEDGER_AT = _LEDGER_COLUMNS + " WHERE id = %s"
# YENİ
# Zincirin hash'lediği kolonlar, `ORDER BY id` sırasıyla okunur. Tek okuyucu iki ilişkiden okur:
# boru hattı tablonun kendisinden, site `site_audit.ledger_rows` görünümünden (Faz 6 İz B §6.4/3a).
# İlişki adı SQL'e gömülür; bu yüzden yalnız aşağıdaki kapalı kümeden gelebilir.
LEDGER_TABLE = "odds_snapshots"
LEDGER_AUDIT_VIEW = "site_audit.ledger_rows"
LEDGER_RELATIONS = frozenset({LEDGER_TABLE, LEDGER_AUDIT_VIEW})
_LEDGER_COLUMNS: tuple[str, ...] = (
    "match_id",
    "observed_at",
    "bookmaker",
    "market",
    "outcome",
    "point",
    "price",
    "bookmaker_last_update",
    "is_closing",
    "prev_hash",
    "row_hash",
)


def _known(relation: str) -> str:
    if relation not in LEDGER_RELATIONS:
        raise ValueError(f"bilinmeyen defter ilişkisi: {relation!r}")
    return relation


def _ledger_select(relation: str, where: str = "") -> str:
    return f"SELECT {', '.join(_LEDGER_COLUMNS)} FROM {_known(relation)}{where}"
```
```python
# ESKİ
def _ledger_rows(conn: psycopg.Connection[Any], after_id: int | None) -> tuple[dict[str, Any], ...]:
    """Defteri okur. `after_id` verilince yalnız çıpadan SONRAKİ kuyruk çekilir."""
    with conn.cursor() as cur:
        if after_id is None:
            cur.execute(_LEDGER_ALL)
        else:
            cur.execute(_LEDGER_AFTER, (after_id,))
# YENİ
def _ledger_rows(
    conn: psycopg.Connection[Any], after_id: int | None, *, relation: str = LEDGER_TABLE
) -> tuple[dict[str, Any], ...]:
    """Defteri okur. `after_id` verilince yalnız çıpadan SONRAKİ kuyruk çekilir."""
    with conn.cursor() as cur:
        if after_id is None:
            cur.execute(_ledger_select(relation, " ORDER BY id"))
        else:
            cur.execute(_ledger_select(relation, " WHERE id > %s ORDER BY id"), (after_id,))
```
```python
# ESKİ
def _ledger_row(conn: psycopg.Connection[Any], row_id: int) -> dict[str, Any] | None:
    """Tek satırı yükü ve prev_hash'iyle birlikte okur — hash yeniden hesaplanabilsin diye."""
    with conn.cursor() as cur:
        cur.execute(_LEDGER_AT, (row_id,))
# YENİ
def _ledger_row(
    conn: psycopg.Connection[Any], row_id: int, *, relation: str = LEDGER_TABLE
) -> dict[str, Any] | None:
    """Tek satırı yükü ve prev_hash'iyle birlikte okur — hash yeniden hesaplanabilsin diye."""
    with conn.cursor() as cur:
        cur.execute(_ledger_select(relation, " WHERE id = %s"), (row_id,))
```
`_anchor_break`in imzası `def _anchor_break(\n    conn: psycopg.Connection[Any], anchor: Anchor, *, relation: str = LEDGER_TABLE\n) -> str | None:`
olur (docstring aynen); gövdesinde:
```python
# ESKİ
        cur.execute("SELECT count(*) FROM odds_snapshots")
        total = int((cur.fetchone() or (0,))[0])
    row = _ledger_row(conn, anchor.last_id)
# YENİ
        cur.execute(f"SELECT count(*) FROM {_known(relation)}")
        total = int((cur.fetchone() or (0,))[0])
    row = _ledger_row(conn, anchor.last_id, relation=relation)
```
`_first_anchor_break`in imzası `def _first_anchor_break(\n    conn: psycopg.Connection[Any], anchors: tuple[Anchor, ...], *, relation: str = LEDGER_TABLE\n) -> str | None:`
olur ve döngüdeki çağrı `breakage = _anchor_break(conn, anchor, relation=relation)` olur. `_verify_chain_command` ve
`_publish_head_command` DEĞİŞMEZ (varsayılan ilişki `odds_snapshots`).

- [ ] **Step 7: Yeşili gör — yeni testler ve korunan davranış**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_market_consensus.py tests/test_ledger_readers.py tests/test_context_parity.py tests/test_single_sources.py tests/test_shadow.py tests/test_live_cli.py tests/test_live_report.py tests/test_verify_chain.py tests/test_collect.py tests/test_db.py tests/test_seal_anchor_step.py`
Expected: hepsi yeşil (`… passed`, `skipped` yalnız mevcut DB-bağlı olanlar). `pre_prices`in mevcut testleri (davranış
eşitliği) ve zincir testleri değişmeden geçer.

- [ ] **Step 8: Mutasyonla kırmızı kanıtı**

| Dosya | Eski → yeni | Kırmızı |
|---|---|---|
| `src/football_edge/market/consensus.py` | `if set(book) == set(RESULTS)]` → `if len(book) >= 2]` | `test_market_consensus.py`: 2 failed (eksik kitap sayılır, sonra `KeyError`) |
| `src/football_edge/collect.py` | `    if relation not in LEDGER_RELATIONS:` → `    if False:` | `test_ledger_readers.py`: 1 failed (kapalı küme) |
| `src/football_edge/collect.py` | `cur.execute(f"SELECT count(*) FROM {_known(relation)}")` → `cur.execute("SELECT count(*) FROM odds_snapshots")` | `test_ledger_readers.py`: 1 failed (görünümün sayımı tabloya kaçtı) |
| `src/football_edge/db.py` | `    lock_ledger(conn)\n    payloads = ` → `    payloads = ` | `test_ledger_readers.py`: 1 failed (kilit ilk ifade değil) |

- [ ] **Step 9: Lint ve tip** — Run: `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts` → temiz.

- [ ] **Step 10: Tam kapı** — `TMPDIR=$(mktemp -d) ./verify.sh > "$TMPDIR/verify.log" 2>&1; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$TMPDIR/verify.log"` → `10 PASS` + `SKIP: zincir` + `KAPI YEŞİL`.

- [ ] **Step 11: Commit**

```bash
git add src/football_edge/market/consensus.py src/football_edge/live/context.py src/football_edge/collect.py \
  tests/test_market_consensus.py tests/test_ledger_readers.py
git commit -m "refactor: tur konsensüsü yaprak modülde, zincir okuyucusu ilişki parametreli (Faz 6 B-1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Migration `0014` — rol, şemalar, görünümler; şablonlu test yalıtımı; metin, katalog, davranış testleri

**Kademe:** K1 · **Spec:** B3–B5, B11, H1a–c, H3c–d, §4.1–§4.4, §18.4 I1/n1–n5, rereview4 m1–m3 · **Bağımlılık:** Task 1,
Task 2 (`_LEDGER_COLUMNS` tuple'ı), Task 0 kaydı (`set_role`, CREATEDB) · **Worktree:** `wt-b1-t3`

`0014` canlıya UYGULANMAZ; yalnız yerel kapta uygulanır ve sınanır (§4.5 onaydan sonradır). DB testlerinin yalıtımı
spec §4.4/4'ün (a) seçeneğidir: şablon `site_tpl` = 0001 + 0002 + 0013 + 0014, modül başına dosya düzeyinde kopya,
temizlik `DROP DATABASE … WITH (FORCE)`; tam sıra (0001→0014) `postgres` veritabanında geri alınan tek işlemde.
Tetikleyici ASLA kapatılmaz. `verify.sh`in `pytest` ve `sızıntı` seçicileri bu görevde `not sitedb` olur: aksi hâlde
`CI=true` iken kapsız adımda `sitedb` fixture'ı FAIL verir ve Task 9'a kadar main kırmızı kalırdı (Q21).
0014, DEFERRED 18f'in önerdiği `set lock_timeout … reset lock_timeout` biçimini kullanır (her gönderim biçiminde bağlar).

**Files:**
- Create: `db/migrations/0014_site_read.sql`
- Create: `tests/sql_text.py` (metin → deyim), `tests/site_db.py` (koruma, şablon, kopya, tam sıra, `as_reader`)
- Test: `tests/test_site_migration_text.py`, `tests/test_site_template_subset.py`, `tests/test_site_harness_rules.py`,
  `tests/test_site_views_db.py`
- Modify: `pyproject.toml` (`sitedb` işareti, `tests/test_site_*_db.py` için ruff istisnası), `verify.sh` (iki seçici),
  `scripts/sandbox_db.sh` (`SITE_TEST_DATABASE_URL` = boş kap), `docs/RUNBOOK.md` §4 (bir madde)

**Interfaces:**
- Consumes: Task 1 `RECORD_COLUMNS`, `FORBIDDEN_KEYS`, `PUBLIC_FLOOR`, `property_names`; Task 2 `collect._LEDGER_COLUMNS`,
  `LEDGER_AUDIT_VIEW`.
- Produces (Task 6, 7, 9):
  - SQL: `site.public_floor() → timestamptz`; `site.leagues(id, name, country)`; `site.matches(id, league_id,
    commence_time, home_team, away_team)`; `site.ledger_head(rows, last_id, head)`; `site.record(<RECORD_COLUMNS>)`;
    `site_input.h2h_quotes(ledger_id, match_id, observed_at, is_closing, outcome, price, book_key)`;
    `site_audit.ledger_rows(id, <_LEDGER_COLUMNS>)`; rol `site_reader` (NOLOGIN, NOINHERIT, iki rol GUC'si).
  - `tests/site_db.py`: `TEMPLATE_MIGRATIONS`, `SKIPPED_MIGRATIONS`, `refusal(url, live) -> str | None`,
    `guarded_url() -> str`, fixture'lar `site_cluster` (session, URL döner), `site_db` (module), `site_db_each`
    (function), `full_sequence` (module, cursor), `template_copy(cluster) -> Iterator[str]`,
    `as_reader(cur) -> Iterator[Cursor]`, `apply(cur, name)`.
  - `tests/sql_text.py`: `statements(sql: str) -> list[str]` (yorumsuz, küçük harf, tek boşluk).

- [ ] **Step 1: `sitedb` işaretini ve ruff istisnasını ekle** (`pyproject.toml`)

```toml
# ESKİ
    "leakage: zaman semantiği, dönem ayrımı, kilit ve bağlam/sonuç ayrımı — kapının sızıntı adımı sayar",
]
# YENİ
    "leakage: zaman semantiği, dönem ayrımı, kilit ve bağlam/sonuç ayrımı — kapının sızıntı adımı sayar",
    "sitedb: atılabilir yerel Postgres kabı ister (SITE_TEST_DATABASE_URL) — kapının site-db adımı koşar",
]
```
```toml
# ESKİ
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "T20"]
# YENİ
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "T20"]

[tool.ruff.lint.per-file-ignores]
# `sitedb` fixture'ları `tests/site_db.py`de yaşar (spec §4.4/4); test modülü onları import eder ve
# parametre adıyla kullanır — pyflakes bunu kullanılmayan/yeniden tanımlanan ad sanar.
"tests/test_site_*_db.py" = ["F401", "F811"]
```

- [ ] **Step 2: Metin okuyucusunu ve test düzenini yaz**

`tests/sql_text.py` (tam içerik):

````python
"""Migration METNİNİ deyimlere ayıran küçük okuyucu (yalnız test).

Yorumlar (`--`, `/* */`) atılır; `;` yalnız tek tırnak ve dolar tırnağı (`$$`, `$etiket$`) DIŞINDA
ve açık bir `begin atomic … end` gövdesinin dışında deyim sonudur — `do $$ … $$` bloğu ve fonksiyon
gövdesi TEK deyim olarak kalır, içindeki metin deyimle birlikte taranır. Çıktı küçük harf ve tek
boşlukludur: yorumdaki bir örnek kuralı karşılamış ya da çiğnemiş sayılmasın.
"""

from __future__ import annotations

import re

_DOLLAR = re.compile(r"\$[A-Za-z_]*\$")
_ATOMIC = re.compile(r"\bbegin atomic\b")
_ATOMIC_END = re.compile(r"\bend$")


def statements(sql: str) -> list[str]:
    found: list[str] = []
    current: list[str] = []
    index, quote = 0, ""
    while index < len(sql):
        char = sql[index]
        if quote:
            if sql.startswith(quote, index):
                current.append(quote)
                index += len(quote)
                quote = ""
                continue
            current.append(char)
            index += 1
            continue
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            index = len(sql) if end == -1 else end
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index)
            index = len(sql) if end == -1 else end + 2
            continue
        tag = _DOLLAR.match(sql, index)
        if tag is not None or char == "'":
            quote = tag.group(0) if tag is not None else "'"
            current.append(quote)
            index += len(quote)
            continue
        if char == ";":
            text = " ".join("".join(current).split()).lower()
            if not (_ATOMIC.search(text) and not _ATOMIC_END.search(text)):
                found.append(text)
                current = []
                index += 1
                continue
        current.append(char)
        index += 1
    tail = " ".join("".join(current).split()).lower()
    return [text for text in (*found, tail) if text]
````

`tests/site_db.py` (tam içerik):

````python
"""`sitedb` testlerinin veritabanı düzeni (Faz 6 İz B tasarımı §4.4/2, §4.4/4, §4.4/5).

İki yer. (i) TAM SIRA, `postgres` veritabanında: 0001→0014 tek işlemde uygulanır, katalog okunur,
işlem GERİ ALINIR (`full_sequence`). (ii) DAVRANIŞ, şablonun kopyasında: `site_tpl` yalnız sitenin
kapanışındaki ve 0013'ün dokunduğu migration'larla kurulur, her modül (ve her kurcalama varyantı)
`CREATE DATABASE … TEMPLATE site_tpl` ile kendi kopyasını alır, sonunda `DROP … WITH (FORCE)`.
Append-only tablolar DELETE/TRUNCATE kabul etmez: temizlik veritabanı düzeyindedir, tetikleyici
ASLA kapatılmaz (`tests/test_site_harness_rules.py`).

Koruma: adres yerel (loopback) değilse ya da canlı adrese eşitse testler REDDEDİLİR; adres yoksa
yerelde SKIP, `CI=true` iken FAIL (B10). Hata metni adresi basmaz (parola taşır).
Migration bağlantısı her yerde `postgres` rolüyledir: 0013'ün `alter default privileges for role
postgres` satırı yalnız onun yarattığı nesnelere uygulanır.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

REPO = Path(__file__).resolve().parent.parent
MIGRATIONS = REPO / "db/migrations"
SITE_TEST_VAR = "SITE_TEST_DATABASE" + "_URL"
LIVE_VAR = "DATABASE" + "_URL"
LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
TEMPLATE_DB = "site_tpl"
COPY_PREFIX = "site_t_"
# m3: iki liste de ADIYLA; `db/migrations/`teki her dosya tam olarak birinde olmalı
# (`tests/test_site_template_subset.py`). Bilinmeyen dosya sınıflandırma kararını zorlar.
TEMPLATE_MIGRATIONS = (
    "0001_init.sql",
    "0002_sources.sql",
    "0013_api_roles_lockdown.sql",
    "0014_site_read.sql",
)
SKIPPED_MIGRATIONS = (
    "0003_seal_dispatch.sql",
    "0004_workflow_dispatch.sql",
    "0005_collect_dispatch.sql",
    "0006_history.sql",
    "0007_holdout.sql",
    "0008_history_dispatch.sql",
    "0009_model_predictions.sql",
    "0010_holdout_phase.sql",
    "0011_shadow_dispatch.sql",
    "0012_jev_features.sql",
)
NO_SITE_DB = f"SKIP: site-db ({SITE_TEST_VAR} yok)"


def refusal(url: str, live: str) -> str | None:
    """Atılabilir olmayan hedefin nedeni; atılabilirse None. Metin adresi TAŞIMAZ."""
    try:
        host = conninfo_to_dict(url).get("host")
    except psycopg.ProgrammingError:
        return f"{SITE_TEST_VAR} ayrıştırılamadı — testler reddedildi"
    if host not in LOOPBACK:
        return f"{SITE_TEST_VAR} yerel bir kabı göstermiyor — append-only tablolara yazılmaz"
    if live and url == live:
        return f"{SITE_TEST_VAR} {LIVE_VAR}'e eşit — testler reddedildi"
    return None


def guarded_url() -> str:
    url = os.environ.get(SITE_TEST_VAR, "")
    if not url:
        if os.environ.get("CI") == "true":
            pytest.fail(f"{SITE_TEST_VAR} yok ve CI=true — site-db kapısı atlanamaz (B10)")
        pytest.skip(NO_SITE_DB)
    reason = refusal(url, os.environ.get(LIVE_VAR, ""))
    if reason is not None:
        pytest.fail(reason)
    return url


def apply(cur: psycopg.Cursor[Any], name: str) -> None:
    # Parametresiz execute çok ifadeli metni olduğu gibi gönderir; `%` ve `$$` yorumlanmaz.
    cur.execute((MIGRATIONS / name).read_text(encoding="utf-8").encode())


def _require_postgres(cur: psycopg.Cursor[Any]) -> None:
    cur.execute("SELECT current_user")
    user = (cur.fetchone() or ("?",))[0]
    if user != "postgres":
        pytest.fail(f"migration'lar postgres rolüyle uygulanmalı, bağlantı {user!r}")


def _admin(url: str) -> psycopg.Connection[Any]:
    return psycopg.connect(url, autocommit=True)


@pytest.fixture(scope="session")
def site_cluster() -> str:
    """Oturum başında bayat şablon ve kopyalar silinir, şablon yeniden kurulur (n2)."""
    url = guarded_url()
    with _admin(url) as admin, admin.cursor() as cur:
        _require_postgres(cur)
        cur.execute(
            "SELECT datname FROM pg_database WHERE datname = %s OR starts_with(datname, %s)",
            (TEMPLATE_DB, COPY_PREFIX),
        )
        for (name,) in cur.fetchall():
            cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEMPLATE_DB)))
    with psycopg.connect(make_conninfo(url, dbname=TEMPLATE_DB)) as conn, conn.cursor() as cur:
        _require_postgres(cur)
        for name in TEMPLATE_MIGRATIONS:
            apply(cur, name)
        become_reader_allowed(cur)
        conn.commit()
    return url


def become_reader_allowed(cur: psycopg.Cursor[Any]) -> None:
    """Testin `SET ROLE site_reader` diyebilmesi (yalnız test kümesinde, T0 ölçümü).

    CREATEROLE'lü süper olmayan `postgres` yarattığı role ADMIN taşır ama SET taşımayabilir
    (`createrole_self_grant`). Üyelik KÜME düzeyindedir ve yalnız bu atılabilir kapta verilir;
    0014 kimseye `site_reader` üyeliği vermez (metin testi).
    """
    cur.execute("SELECT pg_has_role(current_user, 'site_reader', 'SET')")
    if not (cur.fetchone() or (False,))[0]:
        cur.execute("GRANT site_reader TO postgres WITH INHERIT FALSE, SET TRUE")


@contextmanager
def template_copy(cluster: str) -> Iterator[str]:
    """Şablonun dosya düzeyinde kopyası (tetikleyici ateşlenmez); çıkışta silinir."""
    name = COPY_PREFIX + secrets.token_hex(6)
    with _admin(cluster) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(name), sql.Identifier(TEMPLATE_DB)
            )
        )
    try:
        yield make_conninfo(cluster, dbname=name)
    finally:
        with _admin(cluster) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture(scope="module")
def site_db(site_cluster: str) -> Iterator[str]:
    """Modül başına şablonun kopyası."""
    with template_copy(site_cluster) as url:
        yield url


@pytest.fixture
def site_db_each(site_cluster: str) -> Iterator[str]:
    """Test başına kopya: kırık bir zincir sonraki vakayı zehirlemesin."""
    with template_copy(site_cluster) as url:
        yield url


@pytest.fixture(scope="module")
def full_sequence(site_cluster: str) -> Iterator[psycopg.Cursor[Any]]:
    """(i): `postgres` veritabanında 0001→0014 tek işlemde; sonunda GERİ ALINIR.

    Kum havuzu kilidi: hedefte `odds_snapshots` varsa (migration'ları uygulanmış bir kap) hiçbir
    şey uygulanmadan kırmızı. Şablon (`site_cluster`) önce kurulur: açık işlemdeki commit'lenmemiş
    rol satırı öteki kurulumu kilitlerdi.
    """
    conn = psycopg.connect(site_cluster)
    try:
        with conn.cursor() as cur:
            _require_postgres(cur)
            cur.execute("SELECT to_regclass('public.odds_snapshots') IS NULL")
            if not (cur.fetchone() or (False,))[0]:
                pytest.fail("postgres veritabanı boş değil — tam sıra uygulanmadı")
            for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql")):
                apply(cur, path.name)
            yield cur
    finally:
        conn.rollback()
        conn.close()


@contextmanager
def as_reader(cur: psycopg.Cursor[Any]) -> Iterator[psycopg.Cursor[Any]]:
    """Geri alınan bir kayıt noktasında `site_reader` olarak sorgular."""
    cur.execute("SAVEPOINT as_reader")
    cur.execute("SET LOCAL ROLE site_reader")
    try:
        yield cur
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT as_reader")
````

- [ ] **Step 3: 0014'ün metin testini yaz**

`tests/test_site_migration_text.py` (tam içerik):

````python
"""0014 METNİ (§4.4/1): her kapıda, DB'siz. Yorumlar ayıklanır, yorumdaki kelime sayılmaz."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from football_edge.collect import _LEDGER_COLUMNS
from football_edge.site.contract import PUBLIC_FLOOR, RECORD_COLUMNS
from tests.sql_text import statements

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/0014_site_read.sql"
VIEWS = (
    "site.leagues",
    "site.matches",
    "site.ledger_head",
    "site.record",
    "site_input.h2h_quotes",
    "site_audit.ledger_rows",
)
SOURCES = {
    "public.leagues",
    "public.matches",
    "public.odds_snapshots",
    "site.leagues",
    "site.matches",
}
# Görünüm başına beklenen süzgeç (§4.4/1): taban yalnız maç satırı taşıyan iki görünümde.
FILTERS = {
    "site.leagues": ("where l.active",),
    "site.matches": (
        "join site.leagues l on l.id = m.league_id",
        "where m.commence_time >= site.public_floor()",
    ),
    "site.ledger_head": (),
    "site.record": ("where false",),
    "site_input.h2h_quotes": ("join site.matches m on m.id = o.match_id", "where o.market = 'h2h'"),
    "site_audit.ledger_rows": (),
}
_TYPES = {"timestamptz": "timestamp with time zone"}


def _statements() -> list[str]:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def _views() -> dict[str, str]:
    found: dict[str, str] = {}
    for text in _statements():
        head = re.match(r"create or replace view ([\w.]+) with \(security_barrier\) as (.*)", text)
        if head is not None:
            found[head.group(1)] = head.group(2)
    return found


def test_0014_bounds_its_lock_wait_in_the_form_every_sender_honours() -> None:
    """DEFERRED 18f: `set local` autocommit gönderimde bağlamaz; `set … reset` her yerde bağlar."""
    assert (_statements()[0], _statements()[-1]) == (
        "set lock_timeout = '5s'",
        "reset lock_timeout",
    )


def test_every_view_is_created_with_security_barrier_and_none_is_invoker() -> None:
    """§4.2: `security_invoker` site_reader'a RLS uygular ve görünüm HATASIZ 0 satır döner."""
    assert sorted(_views()) == sorted(VIEWS)
    assert all("security_invoker" not in text for text in _statements())


def test_views_read_only_the_three_ledger_tables_or_other_site_views() -> None:
    """H1a (metin katmanı): görünümler yalnız leagues/matches/odds_snapshots'a dayanır."""
    for name, body in _views().items():
        sources = set(re.findall(r"\b(?:from|join) ([\w.]+)", body))
        assert sources <= SOURCES, f"{name}: {sorted(sources - SOURCES)}"


@pytest.mark.leakage
@pytest.mark.parametrize("view", VIEWS)
def test_each_view_carries_exactly_its_expected_filter(view: str) -> None:
    """Taban yalnız `site.matches`te yazılır; `site_input.h2h_quotes` onu join'le devralır."""
    body = _views()[view]

    for clause in FILTERS[view]:
        assert clause in body, f"{view}: {clause!r} yok"
    if "public_floor" in body:
        assert view == "site.matches", f"{view} tabanı kendisi süzmemeli"
    if not FILTERS[view]:
        assert " where " not in f" {body} ", f"{view} süzmemeli"


@pytest.mark.leakage
def test_the_floor_function_returns_the_python_floor_and_reads_no_table() -> None:
    (text,) = [
        s for s in _statements() if s.startswith("create or replace function site.public_floor")
    ]
    literal = PUBLIC_FLOOR.strftime("%Y-%m-%d %H:%M:%S+00")

    assert text == (
        "create or replace function site.public_floor() returns timestamptz language sql "
        f"immutable begin atomic select '{literal}'::timestamptz; end"
    )


def test_the_record_placeholder_is_where_false_with_the_contract_columns() -> None:
    """B5/H3c–d: gövde `where false`; kolon adları ve tipleri Python sabitiyle aynı sırada."""
    body = _views()["site.record"]
    columns = re.findall(r"null::([a-z ]+?) as (\w+)", body)

    assert body.endswith("where false")
    assert [(name, _TYPES.get(kind, kind)) for kind, name in columns] == list(RECORD_COLUMNS)


def test_the_audit_view_carries_id_plus_the_hashed_ledger_columns() -> None:
    """C1: `id` hash'i bozmaz (`payload_of` ayıklar); kolonlar zincir okuyucusunun sabitinden."""
    columns = re.findall(r"o\.(\w+)", _views()["site_audit.ledger_rows"].split(" from ")[0])

    assert tuple(columns) == ("id", *_LEDGER_COLUMNS)


def test_grants_go_only_to_site_reader_and_floor_execute_is_granted_explicitly() -> None:
    grants = [text for text in _statements() if text.startswith("grant ")]

    assert grants and all(text.endswith(" to site_reader") for text in grants)
    assert "grant execute on function site.public_floor() to site_reader" in grants
    assert (
        "revoke all on function site.public_floor() from public, anon, authenticated, service_role"
        in _statements()
    )
    assert all("site_reader" not in text for text in grants if " on " not in text)


def test_the_role_is_created_idempotently_without_login_or_password() -> None:
    """§4.2/AK18: parola ve oturum hakkı migration'da YOK; rol küme düzeyinde tekrar yaratılmaz."""
    text = " ".join(_statements())

    assert (
        "do $$ begin if not exists (select 1 from pg_roles where rolname = 'site_reader') "
        "then create role site_reader nologin noinherit; end if; end $$"
    ) in text
    assert re.search(r"\blogin\b", text) is None
    assert re.search(r"\bpassword\b", text) is None
    assert "alter role site_reader set default_transaction_read_only = on" in text
    assert "alter role site_reader set statement_timeout = '30s'" in text


def test_no_statement_names_a_table_outside_the_site_closure() -> None:
    names = set(re.findall(r"\bpublic\.(\w+)", " ".join(_statements())))

    assert names <= {"leagues", "matches", "odds_snapshots"}, sorted(names)
````

- [ ] **Step 4: Şablon alt kümesinin sadakat testini yaz (m1–m3)**

`tests/test_site_template_subset.py` (tam içerik):

````python
"""Şablon alt kümesinin sadakati (§4.4/4, rereview4 m1–m3): her kapıda, DB'siz.

Şablon (`site_tpl`) yalnız `TEMPLATE_MIGRATIONS`la kurulur; ATLANAN migration'lar sitenin
gördüğü dünyayı değiştirmemeli. "Dokunma" DEYİM HEDEFİYLE tanımlanır: hedefi `leagues`,
`matches` ya da `odds_snapshots` olan DDL/DML, site şemalarına ya da `public`e yetki, site
nesnesi, varsayılan yetki.
Adıyla izinli iki istisna deyim listesine TAKILMAZ; belge amaçlıdır: (1) `references matches(id)`
(0009, 0012) — iç RI tetikleyicileri yalnız `matches`in UPDATE/DELETE'inde ateşlenir, site yalnız
okur; (2) `revoke … on function ops.*` ve `on schema ops` (0003–0005, 0008, 0011) — `ops` şablonda
yoktur. Test bir KARA LİSTEDİR: listede olmayan deyimi ve çalışma anında dinamik SQL'i ölçmez.
"""

from __future__ import annotations

import re

import pytest

from tests.site_db import MIGRATIONS, SKIPPED_MIGRATIONS, TEMPLATE_MIGRATIONS
from tests.sql_text import statements

_TARGET = r'(?:public\.)?"?(?:leagues|matches|odds_snapshots)"?(?![\w])'
_SCHEMAS = r'"?(?:public|site|site_input|site_audit)"?(?![\w])'
_LIST = r'(?:[\w."]+\s*,\s*)*'
FORBIDDEN = {
    "alter table": rf"\balter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?{_TARGET}",
    "create trigger": (
        rf"\bcreate\s+(?:or\s+replace\s+)?(?:constraint\s+)?trigger\b[^;]*?\bon\s+{_TARGET}"
    ),
    "drop trigger/policy/rule": rf"\bdrop\s+(?:trigger|policy|rule)\b[^;]*?\bon\s+{_TARGET}",
    "drop index": r"\bdrop\s+index\b",
    "create policy": rf"\bcreate\s+policy\b[^;]*?\bon\s+{_TARGET}",
    "create index": rf"\bcreate\s+(?:unique\s+)?index\b[^;]*?\bon\s+(?:only\s+)?{_TARGET}",
    "create rule": rf"\bcreate\s+(?:or\s+replace\s+)?rule\b[^;]*?\bto\s+{_TARGET}",
    "grant/revoke on table": rf"\b(?:grant|revoke)\b[^;]*?\bon\s+(?:table\s+)?{_LIST}{_TARGET}",
    "grant/revoke on all in schema": (
        rf"\b(?:grant|revoke)\b[^;]*?\bon\s+all\s+\w+\s+in\s+schema\s+{_LIST}{_SCHEMAS}"
    ),
    "grant/revoke on schema": rf"\b(?:grant|revoke)\b[^;]*?\bon\s+schema\s+{_LIST}{_SCHEMAS}",
    "create schema site*": r'\bcreate\s+schema\s+(?:if\s+not\s+exists\s+)?"?site',
    "alter default privileges": r"\balter\s+default\s+privileges\b",
    "site object or role": r"\bsite(?:_input|_audit)?\.|\bsite_reader\b",
    "dml on target": (
        rf"\b(?:insert\s+into|update|delete\s+from|truncate(?:\s+table)?|copy)\s+(?:only\s+)?"
        rf"{_TARGET}"
    ),
}


def findings(sql: str) -> list[str]:
    return [
        name
        for text in statements(sql)
        for name, pattern in FORBIDDEN.items()
        if re.search(pattern, text)
    ]


def test_every_migration_is_in_exactly_one_list() -> None:
    """m3: yeni bir dosya ne şablona girer ne taranır hâlde sessiz kalmaz."""
    on_disk = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    listed = [*TEMPLATE_MIGRATIONS, *SKIPPED_MIGRATIONS]

    assert len(listed) == len(set(listed)), "bir dosya iki listede"
    assert sorted(listed) == on_disk, f"sınıflandırılmamış: {sorted(set(on_disk) - set(listed))}"


@pytest.mark.parametrize("name", SKIPPED_MIGRATIONS)
def test_a_skipped_migration_does_not_touch_what_the_site_reads(name: str) -> None:
    assert findings((MIGRATIONS / name).read_text(encoding="utf-8")) == [], name


@pytest.mark.parametrize(
    ("statement", "rule"),
    [
        ("grant select on matches to anon;", "grant/revoke on table"),
        ("grant select on public.matches to anon;", "grant/revoke on table"),
        ('grant select on hist_files, "matches" to anon;', "grant/revoke on table"),
        ("alter table odds_snapshots add column x int;", "alter table"),
        ("alter table if exists only public.leagues enable row level security;", "alter table"),
        (
            "create trigger t before insert on leagues for each row execute function f();",
            "create trigger",
        ),
        (
            "drop trigger if exists odds_snapshots_append_only on odds_snapshots;",
            "drop trigger/policy/rule",
        ),
        ("drop index if exists matches_commence_idx;", "drop index"),
        ("create unique index if not exists u on matches (id);", "create index"),
        ("create policy p on public.odds_snapshots for select using (true);", "create policy"),
        ("create rule r as on insert to leagues do instead nothing;", "create rule"),
        ("grant usage on schema ops, public to anon;", "grant/revoke on schema"),
        (
            "grant select on all tables in schema public to service_role;",
            "grant/revoke on all in schema",
        ),
        ("create schema if not exists site_input;", "create schema site*"),
        ("alter default privileges grant select on tables to anon;", "alter default privileges"),
        ("create or replace view site.extra as select 1;", "site object or role"),
        ("grant site_reader to anon;", "site object or role"),
        ("insert into leagues values ('x');", "dml on target"),
        ("do $$ begin update public.matches set home_team = 'x'; end $$;", "dml on target"),
    ],
)
def test_each_forbidden_form_is_caught(statement: str, rule: str) -> None:
    """m1–m2: nitelenmiş ad, tırnak, `if not exists`, `unique`, çoklu hedef, DO bloğu."""
    assert rule in findings(f"-- örnek\n{statement}\n")


@pytest.mark.parametrize(
    "statement",
    [
        "create table z (id bigint, match_id text references matches(id));",
        "create table z (league text references leagues(id));",
        "revoke all on function ops.dispatch_seal() from public, anon, authenticated;",
        "revoke all on schema ops from public;",
        "create trigger t before update on hist_fetches for each row execute function f();",
        "-- grant select on matches to anon;",
    ],
)
def test_the_documented_exceptions_and_comments_are_not_findings(statement: str) -> None:
    """İstisnalar belge amaçlıdır: `references` ve `ops` hedefli deyimler listeye takılmaz."""
    assert findings(statement) == []
````

- [ ] **Step 5: Test düzeninin kurallarını ve korumanın birim testini yaz**

`tests/test_site_harness_rules.py` (tam içerik):

````python
"""Site test düzeninin kuralları (§4.4/4): tetikleyici kapatılmaz, fixture'lar tek dosyada.

Kapsam bilinçli olarak dardır: `tests/test_site_*.py` ve `tests/site_db.py`.
`tests/test_runbook.py` RUNBOOK'tan alıntılanmış bir kalıp taşır ve bu kuralın konusu değildir.
Kalıplar parçalardan kurulur: bu dosya kendi kalıbını eşlemesin.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.site_db import SITE_TEST_VAR, guarded_url, refusal

TESTS = Path(__file__).resolve().parent
HARNESS = TESTS / "site_db.py"
SCOPE = sorted({*TESTS.glob("test_site_*.py"), HARNESS})
DISABLING = (
    re.compile("disable" + r"\s+trigger", re.IGNORECASE),
    re.compile("session_replication" + "_role", re.IGNORECASE),
    re.compile(r"alter\s+table\b[^;\n]*\b" + "disable", re.IGNORECASE),
)
SITE_FIXTURES = frozenset({"site_cluster", "site_db", "site_db_each", "full_sequence"})
ENV_PART = "SITE_TEST_" + "DATABASE"


def test_the_scope_is_the_site_tests_and_the_harness() -> None:
    assert HARNESS in SCOPE and len(SCOPE) > 1


def test_no_site_test_disables_a_trigger() -> None:
    """Append-only tetikleyicisi testte de kapatılmaz: temizlik veritabanı düzeyindedir."""
    hits = [
        f"{path.name}: {pattern.pattern}"
        for path in SCOPE
        for pattern in DISABLING
        if pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert hits == []


def _fixture_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any("fixture" in ast.unparse(decorator) for decorator in node.decorator_list)
    }


def test_sitedb_fixtures_live_only_in_the_harness() -> None:
    """n5: `sitedb` fixture'ları ve test DB adresi yalnız `tests/site_db.py`de."""
    elsewhere = {
        path.name: sorted(_fixture_names(path) & SITE_FIXTURES)
        for path in TESTS.glob("*.py")
        if path != HARNESS and _fixture_names(path) & SITE_FIXTURES
    }
    readers = sorted(
        path.name
        for path in TESTS.glob("*.py")
        if path != HARNESS and ENV_PART in path.read_text(encoding="utf-8")
    )

    assert _fixture_names(HARNESS) >= SITE_FIXTURES
    assert elsewhere == {}
    assert readers == []


def test_the_migration_grants_no_membership_in_the_reader_role() -> None:
    """Test kümesi `postgres`e SET üyeliği verebilir (`site_db.py`); 0014 kimseye vermez."""
    text = (TESTS.parent / "db/migrations/0014_site_read.sql").read_text(encoding="utf-8").lower()

    assert re.search(r"grant\s+site_reader\s+to", text) is None


def test_the_gate_runs_sitedb_tests_only_where_it_names_them() -> None:
    """Her `uv run pytest` çağrısı `sitedb`i adıyla seçer ya da dışlar (yalnız `-m contract` hariç).

    Aksi hâlde `CI=true` iken veritabanı kabı olmayan bir adımda `sitedb` fixture'ı FAIL verir, ya
    da testler iki adımda iki kez koşar.
    """
    runs = [
        line.strip()
        for line in (TESTS.parent / "verify.sh").read_text(encoding="utf-8").splitlines()
        if "uv run pytest" in line and not line.lstrip().startswith("#")
    ]

    assert runs, "verify.sh'de pytest çağrısı bulunamadı"
    assert all("sitedb" in run or "-m contract" in run for run in runs), runs


# ── Koruma (§4.4/5): atılabilir olmayan hedef reddedilir, adres metne girmez ──────────────────


@pytest.mark.parametrize(
    ("url", "live", "refused"),
    [
        ("postgresql://postgres:gizli@127.0.0.1:55481/postgres", "", False),
        ("postgresql://postgres:gizli@localhost:5432/postgres", "", False),
        ("postgresql://postgres:gizli@db.uzak.invalid:5432/postgres", "", True),
        ("postgresql:///postgres", "", True),  # soket: ana makine yok
        (
            "postgresql://postgres:gizli@127.0.0.1:5432/postgres",
            "postgresql://postgres:gizli@127.0.0.1:5432/postgres",
            True,
        ),
        ("bu bir adres değil ===", "", True),
    ],
)
def test_only_a_local_disposable_address_is_accepted(url: str, live: str, refused: bool) -> None:
    reason = refusal(url, live)

    assert (reason is not None) is refused, reason
    assert reason is None or "gizli" not in reason


def test_a_missing_address_skips_locally_and_fails_in_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """B10: SKIP'in CI'da sessizce yeşil olması Vaka 1 desenidir.

    İki sonuç da yakalanıp TÜRÜYLE sınanır: yakalanmayan bir SKIP bu testi kırmızı değil "atlandı"
    gösterirdi.
    """
    outcomes = (pytest.skip.Exception, pytest.fail.Exception)
    monkeypatch.delenv(SITE_TEST_VAR, raising=False)
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(outcomes) as local:
        guarded_url()
    monkeypatch.setenv("CI", "true")
    with pytest.raises(outcomes) as ci:
        guarded_url()

    assert local.type is pytest.skip.Exception and "SKIP: site-db" in str(local.value)
    assert ci.type is pytest.fail.Exception and "CI=true" in str(ci.value)
````

- [ ] **Step 6: Katalog ve davranış testlerini yaz**

`tests/test_site_views_db.py` (tam içerik):

````python
"""0014 gerçek Postgres'te (§4.4/2): katalog tam sırada, davranış şablonun kopyasında.

Yalnız atılabilir yerel kapta koşar (`tests/site_db.py`): `scripts/sandbox_db.sh up` ve
`scripts/sandbox_db.sh test tests/test_site_views_db.py`. Değişken yoksa yerelde SKIP, CI'da FAIL.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from football_edge.site.contract import FORBIDDEN_KEYS, PUBLIC_FLOOR, RECORD_COLUMNS
from football_edge.site.schema import property_names
from tests.site_db import as_reader, full_sequence, site_cluster, site_db

pytestmark = pytest.mark.sitedb

REPO = Path(__file__).resolve().parent.parent
SCHEMAS = ("site", "site_input", "site_audit")
API_ROLES = ("anon", "authenticated", "service_role")
BASE_TABLES = {"public.leagues", "public.matches", "public.odds_snapshots"}


def _rows(cur: psycopg.Cursor[Any], query: str, params: tuple[Any, ...] = ()) -> list[Any]:
    cur.execute(query, params)
    return list(cur.fetchall())


QUALIFIED = "n.nspname || '.' || c.relname"
FROM_CLASS = "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"


def _views(cur: psycopg.Cursor[Any]) -> list[tuple[int, str]]:
    return [
        (oid, name)
        for oid, name in _rows(
            cur,
            f"SELECT c.oid::int, {QUALIFIED} {FROM_CLASS} "
            "WHERE n.nspname = ANY(%s) AND c.relkind = 'v' ORDER BY 2",
            (list(SCHEMAS),),
        )
    ]


def closure(cur: psycopg.Cursor[Any]) -> tuple[dict[str, str], set[str]]:
    """Görünümlerin `pg_depend` kapanışı: (ilişki → relkind, fonksiyonlar).

    Görünümün bağımlılığı kuralındadır (`pg_rewrite`); fonksiyonun gövde bağımlılığı `BEGIN ATOMIC`
    ile kaydedilir. Sabitlenmiş (`pg_catalog`) nesneler `pg_depend`e yazılmaz.
    """
    relations: dict[str, str] = {}
    functions: set[str] = set()
    pending = [("r", oid) for oid, _ in _views(cur)]
    seen: set[tuple[str, int]] = set()
    while pending:
        kind, oid = pending.pop()
        if (kind, oid) in seen:
            continue
        seen.add((kind, oid))
        if kind == "r":
            ((name, relkind),) = _rows(
                cur, f"SELECT {QUALIFIED}, c.relkind::text {FROM_CLASS} WHERE c.oid = %s", (oid,)
            )
            relations[name] = relkind
            deps = _rows(
                cur,
                "SELECT d.refclassid::regclass::text, d.refobjid::int FROM pg_rewrite r "
                "JOIN pg_depend d ON d.classid = 'pg_rewrite'::regclass AND d.objid = r.oid "
                "WHERE r.ev_class = %s AND d.refobjid <> %s "
                "AND d.refclassid IN ('pg_class'::regclass, 'pg_proc'::regclass)",
                (oid, oid),
            )
        else:
            ((name,),) = _rows(cur, "SELECT %s::oid::regprocedure::text", (oid,))
            functions.add(name)
            deps = _rows(
                cur,
                "SELECT refclassid::regclass::text, refobjid::int FROM pg_depend "
                "WHERE classid = 'pg_proc'::regclass AND objid = %s "
                "AND refclassid IN ('pg_class'::regclass, 'pg_proc'::regclass)",
                (oid,),
            )
        pending.extend(("r" if table == "pg_class" else "p", ref) for table, ref in deps)
    return relations, functions


# ── (i) tam sıra, postgres veritabanında, geri alınan işlem ──────────────────────────────────


@pytest.mark.leakage
def test_the_views_depend_on_exactly_the_three_ledger_tables_and_the_floor(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    """H1a: temel tablolar = {leagues, matches, odds_snapshots}; fonksiyonlar ⊆ {public_floor}."""
    relations, functions = closure(full_sequence)
    tables = {name for name, kind in relations.items() if kind == "r"}
    others = {name for name, kind in relations.items() if kind != "r"}

    assert tables == BASE_TABLES
    assert all(name.split(".")[0] in SCHEMAS for name in others), sorted(others)
    assert functions <= {"site.public_floor()"}, sorted(functions)


@pytest.mark.leakage
def test_the_floor_is_the_python_floor(full_sequence: psycopg.Cursor[Any]) -> None:
    assert _rows(full_sequence, "SELECT site.public_floor()") == [(PUBLIC_FLOOR,)]


def test_everything_is_owned_by_postgres_and_no_view_is_invoker(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    """§4.2: görünüm sahibi = tablo sahibi = postgres; `security_barrier` var, `invoker` yok."""
    owners = _rows(
        full_sequence,
        f"SELECT {QUALIFIED}, pg_get_userbyid(c.relowner), c.reloptions {FROM_CLASS} "
        f"WHERE (n.nspname = ANY(%s) AND c.relkind = 'v') OR {QUALIFIED} = ANY(%s) ORDER BY 1",
        (list(SCHEMAS), sorted(BASE_TABLES)),
    )
    ((floor_owner,),) = _rows(
        full_sequence,
        "SELECT pg_get_userbyid(proowner) FROM pg_proc "
        "WHERE oid = 'site.public_floor()'::regprocedure",
    )

    assert len(owners) == 6 + 3
    assert {owner for _, owner, _ in owners} == {"postgres"} and floor_owner == "postgres"
    for name, _, options in owners:
        if name not in BASE_TABLES:
            assert "security_barrier=true" in (options or []), name
            assert not any(o.startswith("security_invoker") for o in options or []), name


def test_api_roles_get_nothing_in_the_site_schemas(full_sequence: psycopg.Cursor[Any]) -> None:
    for role in API_ROLES:
        for schema in SCHEMAS:
            assert _rows(
                full_sequence, "SELECT has_schema_privilege(%s, %s, 'USAGE')", (role, schema)
            ) == [(False,)], (role, schema)
        for _, view in _views(full_sequence):
            assert _rows(
                full_sequence, "SELECT has_table_privilege(%s, %s, 'SELECT')", (role, view)
            ) == [(False,)], (role, view)
        assert _rows(
            full_sequence,
            "SELECT has_function_privilege(%s, 'site.public_floor()', 'EXECUTE')",
            (role,),
        ) == [(False,)], role


def test_site_reader_holds_no_table_privilege_and_cannot_log_in(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    held = _rows(
        full_sequence,
        f"SELECT {QUALIFIED} {FROM_CLASS} WHERE c.relkind IN ('r', 'p') AND n.nspname = 'public' "
        "AND has_table_privilege('site_reader', c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')",
    )
    ((login, bypass, inherit),) = _rows(
        full_sequence,
        "SELECT rolcanlogin, rolbypassrls, rolinherit FROM pg_roles WHERE rolname = 'site_reader'",
    )
    settings = _rows(
        full_sequence,
        "SELECT unnest(setconfig) FROM pg_db_role_setting "
        "WHERE setrole = 'site_reader'::regrole AND setdatabase = 0 ORDER BY 1",
    )

    assert held == []
    assert (login, bypass, inherit) == (False, False, False)
    assert settings == [("default_transaction_read_only=on",), ("statement_timeout=30s",)]


def _record_columns(cur: psycopg.Cursor[Any]) -> list[tuple[str, str]]:
    return [
        (name, kind)
        for name, kind in _rows(
            cur,
            "SELECT attname::text, format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = 'site.record'::regclass AND attnum > 0 AND NOT attisdropped "
            "ORDER BY attnum",
        )
    ]


def test_the_record_view_has_the_contract_columns_and_no_rows(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    assert _record_columns(full_sequence) == list(RECORD_COLUMNS)
    assert _rows(full_sequence, "SELECT count(*) FROM site.record") == [(0,)]


@pytest.mark.parametrize(
    "replacement",
    [
        "null::bigint as publication_no",  # ad değişti
        "null::text as publication_id",  # tip değişti
    ],
)
def test_replacing_the_record_view_cannot_rename_or_retype(
    full_sequence: psycopg.Cursor[Any], replacement: str
) -> None:
    """B5: Postgres ad/tip değişikliğini reddeder (vaka 1)."""
    rest = ", ".join(f"null::{kind} as {name}" for name, kind in RECORD_COLUMNS[1:])
    full_sequence.execute("SAVEPOINT replace_record")
    with pytest.raises(psycopg.errors.InvalidTableDefinition):
        full_sequence.execute(
            f"CREATE OR REPLACE VIEW site.record AS SELECT {replacement}, {rest} WHERE false"
        )
    full_sequence.execute("ROLLBACK TO SAVEPOINT replace_record")


def test_appending_a_record_column_is_accepted_by_postgres_but_red_here(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    """B5 vaka 2: sona kolon eklemeye Postgres izin verir; koruma kolon listesi testinden gelir."""
    columns = ", ".join(f"null::{kind} as {name}" for name, kind in RECORD_COLUMNS)
    full_sequence.execute("SAVEPOINT grow_record")
    full_sequence.execute(
        f"CREATE OR REPLACE VIEW site.record AS SELECT {columns}, null::text AS extra WHERE false"
    )
    grown = _record_columns(full_sequence)
    full_sequence.execute("ROLLBACK TO SAVEPOINT grow_record")

    assert grown != list(RECORD_COLUMNS)
    assert grown[: len(RECORD_COLUMNS)] == list(RECORD_COLUMNS)


def test_the_forbidden_key_set_is_the_catalog_difference(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    """§4.3: (site_input ∪ site_audit kolonları) − (site kolonları ∪ şemanın anahtarları)."""

    def columns(schemas: tuple[str, ...]) -> set[str]:
        return {
            name
            for (name,) in _rows(
                full_sequence,
                f"SELECT a.attname::text {FROM_CLASS} JOIN pg_attribute a ON a.attrelid = c.oid "
                "WHERE n.nspname = ANY(%s) AND c.relkind = 'v' AND a.attnum > 0 "
                "AND NOT a.attisdropped",
                (list(schemas),),
            )
        }

    schema = json.loads((REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8"))
    derived = columns(("site_input", "site_audit")) - (columns(("site",)) | property_names(schema))

    assert derived and derived == FORBIDDEN_KEYS


def test_applying_0014_twice_is_harmless(full_sequence: psycopg.Cursor[Any]) -> None:
    """Rol ve nesneler idempotent: önceki oturumdan kalan `site_reader` hata vermez (n2)."""
    full_sequence.execute("SAVEPOINT again")
    full_sequence.execute((REPO / "db/migrations/0014_site_read.sql").read_text().encode())
    assert _record_columns(full_sequence) == list(RECORD_COLUMNS)
    full_sequence.execute("ROLLBACK TO SAVEPOINT again")


# ── (ii) davranış, şablonun kopyasında ───────────────────────────────────────────────────────

ACTIVE, PASSIVE = "tst.1", "tst.9"
HOLDOUT = ("m-holdout", "2026-01-15T12:00:00Z")
EDGE = ("m-edge", "2026-07-01T23:59:59.999999Z")
FLOOR = ("m-floor", "2026-07-02T00:00:00Z")
LIVE = ("m-live", "2026-09-20T18:00:00Z")
ASLEEP = ("m-passive", "2026-09-21T18:00:00Z")


@pytest.fixture(scope="module")
def seeded(site_db: str) -> Iterator[psycopg.Cursor[Any]]:
    """Sahip (`postgres`) olarak zincirsiz tohumlar: bu testler zincir değil süzgeç sınar."""
    conn = psycopg.connect(site_db)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO leagues VALUES (%s, 'k1', 'Deneme Ligi', 'Testland', 'tr', 'TR', true),"
            " (%s, 'k9', 'Uyuyan Lig', 'Testland', 'tr', 'TR', false)",
            (ACTIVE, PASSIVE),
        )
        for match_id, kickoff in (HOLDOUT, EDGE, FLOOR, LIVE, ASLEEP):
            league = PASSIVE if match_id == ASLEEP[0] else ACTIVE
            cur.execute(
                "INSERT INTO matches (id, league_id, commence_time, home_team, away_team) "
                "VALUES (%s, %s, %s, 'Ev', 'Dep')",
                (match_id, league, kickoff),
            )
            for book in ("kitap-b", "kitap-a"):
                cur.execute(
                    "INSERT INTO odds_snapshots (match_id, observed_at, bookmaker, market, "
                    "outcome, price, prev_hash, row_hash) "
                    "VALUES (%s, '2026-06-30T10:00:00Z', %s, 'h2h', 'Ev', 2.0, 'g', %s)",
                    (match_id, book, f"{match_id}-{book}"),
                )
        conn.commit()
        yield cur
    conn.rollback()
    conn.close()


@pytest.mark.leakage
def test_the_floor_filters_holdout_and_its_neighbour_but_keeps_the_floor(
    seeded: psycopg.Cursor[Any],
) -> None:
    """H1b: 2026-01-15 ve 2026-07-01T23:59:59.999999Z → 0 satır; 2026-07-02T00:00Z → 1 satır."""
    with as_reader(seeded) as cur:
        matches = {row[0] for row in _rows(cur, "SELECT id FROM site.matches")}
        quoted = {
            row[0] for row in _rows(cur, "SELECT DISTINCT match_id FROM site_input.h2h_quotes")
        }

    assert matches == {FLOOR[0], LIVE[0]}
    assert quoted == {FLOOR[0], LIVE[0]}


def test_site_reader_sees_rows_through_the_views(seeded: psycopg.Cursor[Any]) -> None:
    """§4.2 bekçi 2 + `grant execute` yük taşır: 0 satır da kırmızıdır."""
    with as_reader(seeded) as cur:
        (count,) = _rows(cur, "SELECT count(*) FROM site.matches")[0]
        leagues = _rows(cur, "SELECT id FROM site.leagues")
        (head,) = _rows(cur, "SELECT rows, last_id FROM site.ledger_head")

    assert count > 0
    assert leagues == [(ACTIVE,)], "pasif lig düşmeli"
    assert head == (10, 10)


def test_book_key_is_the_book_order_within_a_round_and_no_book_name_leaks(
    seeded: psycopg.Cursor[Any],
) -> None:
    with as_reader(seeded) as cur:
        keys = _rows(
            cur,
            "SELECT book_key, ledger_id FROM site_input.h2h_quotes WHERE match_id = %s "
            "ORDER BY ledger_id",
            (LIVE[0],),
        )
        columns = [d.name for d in cur.description or ()]

    # kitap-b önce eklendi (küçük ledger_id) ama sırada kitap-a'dan sonra gelir.
    assert [key for key, _ in keys] == [2, 1]
    assert "bookmaker" not in columns


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT 1 FROM public.odds_snapshots LIMIT 1",
        "SELECT 1 FROM public.matches LIMIT 1",
        "INSERT INTO public.odds_snapshots DEFAULT VALUES",
        "INSERT INTO site.leagues (id, name, country) VALUES ('x', 'x', 'x')",
    ],
)
def test_site_reader_cannot_touch_a_table_or_write_through_a_view(
    seeded: psycopg.Cursor[Any], statement: str
) -> None:
    """Sınır yetkidir: `default_transaction_read_only` kaza önleyicidir, SET ROLE'de etkin değil."""
    with as_reader(seeded) as cur, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cur.execute(statement)
````

- [ ] **Step 7: Kırmızıyı gör (DB'siz)**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_migration_text.py tests/test_site_template_subset.py tests/test_site_harness_rules.py tests/test_site_views_db.py -rs`
Expected: `test_site_migration_text.py` ve `test_the_migration_grants_no_membership…` `FileNotFoundError: …0014_site_read.sql`;
`test_every_migration_is_in_exactly_one_list` kırmızı (liste 0014'ü sayıyor, disk saymıyor);
`test_the_gate_runs_sitedb_tests_only_where_it_names_them` kırmızı (seçiciler henüz yok); `test_site_views_db.py` 18
`SKIP: site-db (SITE_TEST_DATABASE_URL yok)`.

- [ ] **Step 8: Migration'ı yaz**

`db/migrations/0014_site_read.sql` (tam içerik):

````sql
-- Sitenin salt okuma katmanı (Faz 6 İz B tasarımı §4, B3–B5). YAZILIR, canlıya bu görevde UYGULANMAZ
-- (HANDOFF §0.7: AK6 onayı + ROLLBACK'li prova + `apply_migration`).
--
-- Üç şema, bir rol: `site` (her kolonu anlık görüntüye BİREBİR girebilir = yayımlanabilir),
-- `site_input` (hesap girdisi, yayımlanmaz: kitap bazında fiyat), `site_audit` (yalnız zincir
-- doğrulaması, yayımlanmaz). `site_reader` yalnız bu üç şemanın görünümlerini okur; HİÇBİR tabloda
-- yetkisi yoktur. Görünümler sahibinin (`postgres` = tablo sahibi) yetkisiyle okunur: 0013'ün RLS'i
-- politikasızdır ve sahibi bağlamaz. Görünüm sahibi tablo sahibi değilse ya da `security_invoker`
-- taşırsa görünüm HATASIZ 0 satır döner — katalog testi ikisini de kırmızı yapar (§4.2).
-- Parola ve oturum açma hakkı burada YOKTUR: onaydan sonra kullanıcı istemci tarafında verir (AK18).

-- DEFERRED 18f'in biçimi: `set … reset` her gönderim biçiminde bağlar (`set local` yalnız işlem
-- açan biçimlerde). Görünüm kurmak referans verilen tablolarda hafif kilit alır; mühür turunun
-- arkasında sınırsız beklenmez.
set lock_timeout = '5s';

create schema if not exists site;
create schema if not exists site_input;
create schema if not exists site_audit;
revoke all on schema site, site_input, site_audit from public;

-- Rol küme düzeyindedir: şablon kopyaları ve önceki test oturumları aynı kümeyi paylaşır.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'site_reader') then
    create role site_reader nologin noinherit;
  end if;
end
$$;
-- Kaza önleyiciler, güvenlik sınırı DEĞİL (oturumda kapatılabilir). Sınır: yetki yok.
alter role site_reader set default_transaction_read_only = on;
alter role site_reader set statement_timeout = '30s';

-- B4: holdout tabanı TEK yerde. Gövde tablo okumaz; değer Python sabitine eşitliğiyle sınanır.
create or replace function site.public_floor() returns timestamptz
language sql
immutable
begin atomic
  select '2026-07-02 00:00:00+00'::timestamptz;
end;

-- Taban süzgeci yok: lig satırı tarih taşımaz. Pasif lig (ve onun maçları) düşer.
create or replace view site.leagues with (security_barrier) as
  select l.id, l.name, l.country
  from public.leagues l
  where l.active;

-- `sealed_at` alınmaz (UPDATE edilir); `commence_time` de değişkendir — tutarlılık dışa aktarımın
-- tek REPEATABLE READ işlemine dayanır (B12).
create or replace view site.matches with (security_barrier) as
  select m.id, m.league_id, m.commence_time, m.home_team, m.away_team
  from public.matches m
  join site.leagues l on l.id = m.league_id
  where m.commence_time >= site.public_floor();

-- Bütün defter; tarih kolonu taşımaz. `head` saklanan hücredir — dışa aktarım onu KULLANMAZ,
-- zinciri yeniden hesaplar.
create or replace view site.ledger_head with (security_barrier) as
  select count(*)::bigint as rows,
         coalesce(max(o.id), 0)::bigint as last_id,
         coalesce(
           (select o2.row_hash from public.odds_snapshots o2 order by o2.id desc limit 1),
           repeat('0', 64)
         ) as head
  from public.odds_snapshots o;

-- B5: yer tutucu sicil. Faz 5 `publications`a AYNI ad, tip ve sırayla bağlar; gövde o güne dek
-- `where false` kalır (metin testi) ve kolon listesi Python sabitine eşittir (katalog testi).
create or replace view site.record with (security_barrier) as
  select null::bigint as publication_id,
         null::text as match_id,
         null::text as market,
         null::text as outcome,
         null::timestamptz as published_at,
         null::numeric as published_price,
         null::bigint as publication_ledger_id,
         null::numeric as closing_fair_price,
         null::double precision as clv,
         null::text as publication_hash
  where false;

-- Hesap girdisi: kitap adı YOK; `book_key` tur içinde kitabın sırası. Taban `site.matches`ten gelir.
create or replace view site_input.h2h_quotes with (security_barrier) as
  select o.id as ledger_id,
         o.match_id,
         o.observed_at,
         o.is_closing,
         o.outcome,
         o.price,
         dense_rank() over (partition by o.match_id, o.observed_at order by o.bookmaker) as book_key
  from public.odds_snapshots o
  join site.matches m on m.id = o.match_id
  where o.market = 'h2h';

-- Yalnız zincir doğrulaması: bilinçli olarak TABANSIZDIR (zincir GENESIS'ten ancak bütün satırlarla
-- hash'lenir). Holdout tarihli satır (bugün yok) yalnız hash'lenir, türetime girmez.
create or replace view site_audit.ledger_rows with (security_barrier) as
  select o.id, o.match_id, o.observed_at, o.bookmaker, o.market, o.outcome, o.point, o.price,
         o.bookmaker_last_update, o.is_closing, o.prev_hash, o.row_hash
  from public.odds_snapshots o;

-- ── Yetkiler: yalnız site_reader ────────────────────────────────────────────────────────────
revoke all on all tables in schema site, site_input, site_audit from anon, authenticated, service_role;
revoke all on function site.public_floor() from public, anon, authenticated, service_role;
grant usage on schema site, site_input, site_audit to site_reader;
grant select on all tables in schema site to site_reader;
grant select on all tables in schema site_input to site_reader;
grant select on all tables in schema site_audit to site_reader;
-- Yük taşır: görünümdeki fonksiyon çağrısının EXECUTE'u SORGULAYANA göre denetlenir. Bu satır
-- olmadan taban süzen her görünüm site_reader için yetki hatası verir.
grant execute on function site.public_floor() to site_reader;

reset lock_timeout;
````

- [ ] **Step 9: Kapının seçicileri** (`verify.sh`, üç düzenleme; eski metin 0013 birleşmiş main'den)

```bash
# ESKİ
step "pytest"      uv run pytest -q --tb=short
# YENİ
# `sitedb` işaretli testler atılabilir bir Postgres kabı ister: kendi adımlarında (`site-db`,
# Faz 6 B-1 Task 9) koşar. `CI=true` iken kapsız bir adımda o fixture FAIL verir.
step "pytest"      uv run pytest -q -m "not sitedb" --tb=short
```
`sızıntı` adımının içinde iki satır:
```bash
# ESKİ
  collect_output=$(uv run pytest tests/ -q -m leakage --collect-only 2>&1)
# YENİ
  collect_output=$(uv run pytest tests/ -q -m "leakage and not sitedb" --collect-only 2>&1)
```
```bash
# ESKİ
  uv run pytest tests/ -q -m leakage --tb=short
# YENİ
  uv run pytest tests/ -q -m "leakage and not sitedb" --tb=short
```
`EXPECTED_MIN_LEAKAGE` DEĞİŞMEZ (sayı Task 9'da ölçülür; bu görevin `sitedb`siz leakage testleri sayıyı düşürmez).
`tests/test_gate_traceback.py`nin sayımı (verify.sh'de 3 pytest çağrısı) değişmez.

- [ ] **Step 10: Kum havuzu betiği ve RUNBOOK** (`scripts/sandbox_db.sh`, dört düzenleme)

```bash
# ESKİ
SANDBOX_VAR="SANDBOX_DATABASE""_URL"
DEFAULT_TESTS=(tests/test_api_roles_lockdown_db.py tests/test_jev_tables_db.py tests/test_holdout_phase_db.py)
# YENİ
SANDBOX_VAR="SANDBOX_DATABASE""_URL"
# Sitenin `sitedb` testleri (Faz 6 İz B §4.4/4) de BOŞ kabı kullanır: `postgres` veritabanında tam
# sırayı geri alınan işlemde uygular; şablonu ve kopyalarını AYRI veritabanlarında kurar.
SITE_VAR="SITE_TEST_DATABASE""_URL"
DEFAULT_TESTS=(tests/test_api_roles_lockdown_db.py tests/test_jev_tables_db.py tests/test_holdout_phase_db.py
  tests/test_site_views_db.py)
```
```bash
# ESKİ
  printf 'export %s=%q\n' "$SANDBOX_VAR" "$empty_url"
}
# YENİ
  printf 'export %s=%q\n' "$SANDBOX_VAR" "$empty_url"
  printf 'export %s=%q\n' "$SITE_VAR" "$empty_url"
}
```
```bash
# ESKİ
  env "$DB_VAR=$applied_url" "$SANDBOX_VAR=$empty_url" \
# YENİ
  env "$DB_VAR=$applied_url" "$SANDBOX_VAR=$empty_url" "$SITE_VAR=$empty_url" \
```
Başlık yorumunda `scripts/sandbox_db.sh env          elle kullanım için iki \`export\` satırı basar` → `… üç \`export\`
satırı basar`. `docs/RUNBOOK.md` §4'te "`football-edge-sandbox-empty` (127.0.0.1:55481): …" maddesinin HEMEN ALTINA:
```markdown
- **Site testleri** (`sitedb` işareti; `test` komutu `SITE_TEST_DATABASE_URL`i BOŞ kaba çevirir): `postgres`
  veritabanında 0001→0014'ü tek işlemde uygulayıp geri alır; ayrıca `site_tpl` şablonunu (0001, 0002, 0013, 0014) ve
  modül başına `site_t_<rastgele>` kopyalarını kurar, bitince `DROP … WITH (FORCE)` ile kaldırır (oturum başında
  bayatları da). `site_reader` rolü ve testin ona `SET` üyeliği KÜME düzeyinde kalır — yalnız bu atılabilir kapta.
```

- [ ] **Step 11: Yeşili gör — DB'siz katman**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_migration_text.py tests/test_site_template_subset.py tests/test_site_harness_rules.py tests/test_gate_traceback.py`
Expected: `65 passed` (15 + 36 + 12 + 2).

- [ ] **Step 12: Yeşili gör — yerel kapta katalog ve davranış**

```bash
scripts/sandbox_db.sh up
scripts/sandbox_db.sh apply          # uygulanmış kaba 0014'ü de uygular (öteki DB testleri için)
scripts/sandbox_db.sh test tests/test_site_views_db.py tests/test_api_roles_lockdown_db.py
```
Expected: `test_site_views_db.py` **18 passed, 0 skipped** (atlanan varsa yeşil sayılmaz — `-rs` çıktısını oku);
`test_api_roles_lockdown_db.py` önceki sayısıyla yeşil (kum havuzu artık 0001→0014'ü uygular; 0014 `public`e dokunmaz).
Tam sıranın ilk koşusunda T0 kaydındaki `full_sequence_seconds` mertebesinde bekleme normaldir.

- [ ] **Step 13: Mutasyonla kırmızı kanıtı** (DB'li satırlar `scripts/sandbox_db.sh test <dosya>` ile koşar)

| Dosya | Eski → yeni | Kırmızı |
|---|---|---|
| `db/migrations/0014_site_read.sql` | `grant execute on function site.public_floor() to site_reader;` → `` (satır boş) | DB: `test_site_reader_sees_rows_through_the_views` ve `test_the_floor_filters_holdout…` (yetki hatası — spec §4.4/2'nin mutasyon kanıtı; yalnız migration `postgres` rolüyle uygulandığı için olur) |
| `db/migrations/0014_site_read.sql` | `create or replace view site.matches with (security_barrier) as` → `create or replace view site.matches as` | metin: `test_every_view_is_created_with_security_barrier…`; DB: `test_everything_is_owned_by_postgres…` |
| `db/migrations/0014_site_read.sql` | `  where m.commence_time >= site.public_floor();` → `  ;` | metin: `test_each_view_carries_exactly_its_expected_filter[site.matches]`; DB: `test_the_floor_filters_holdout…` (H1b) |
| `db/migrations/0014_site_read.sql` | `  join site.leagues l on l.id = m.league_id\n` → `` | metin: `test_each_view_carries_exactly_its_expected_filter[site.matches]`; DB: `test_the_floor_filters_holdout…` (pasif ligin maçı sızar). `test_the_views_depend_on_exactly…` YEŞİL kalır (kapanış yine üç tablo) — bu, kapanış testinin neyi ölçmediğidir |
| `db/migrations/0012_jev_features.sql` | sona `\ngrant select on matches to anon;\n` eklenir | `test_a_skipped_migration_does_not_touch…[0012_jev_features.sql]` |
| `db/migrations/0012_jev_features.sql` | sona `\nalter table odds_snapshots add column x int;\n` | aynı test |
| `db/migrations/0012_jev_features.sql` | sona `\ncreate trigger t before insert on leagues for each row execute function forbid_ledger_mutation();\n` (m1: yasak deyim, hedef `leagues`) | aynı test |
| (yeni dosya) `db/migrations/0015_probe.sql` = 0012'nin kopyası | — | `test_every_migration_is_in_exactly_one_list` (m3); dosya scratch'e TAŞINIR (`mv`), silinmez |
| `tests/site_db.py` | modül docstring'inin sonuna `session_replication` + `_role` yan yana yazılır | `test_no_site_test_disables_a_trigger` |
| `verify.sh` | `-m "not sitedb" --tb=short` → `--tb=short` | `test_the_gate_runs_sitedb_tests_only_where_it_names_them` |
| `tests/site_db.py` | `    if host not in LOOPBACK:` → `    if False:` | `test_only_a_local_disposable_address_is_accepted` (uzak ve soket adresleri) |
| `tests/site_db.py` | `        if os.environ.get("CI") == "true":` → `        if False:` | `test_a_missing_address_skips_locally_and_fails_in_ci` (CI'da SKIP'e düşer → kırmızı, "atlandı" değil) |

0012'ye ekleme için: `cp db/migrations/0012_jev_features.sql /tmp/0012.bak; printf '\n%s\n' '<deyim>' >> db/migrations/0012_jev_features.sql; …; cp /tmp/0012.bak db/migrations/0012_jev_features.sql && cmp …`.
Her DB mutasyonundan sonra `scripts/sandbox_db.sh test tests/test_site_views_db.py` yeniden 18 passed vermeli (oturum
başında şablon yeniden kurulduğu için bayat 0014 kalmaz — n2).

- [ ] **Step 14: Lint ve tip** — `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`.

- [ ] **Step 15: Tam kapı** — `TMPDIR=$(mktemp -d) ./verify.sh > "$TMPDIR/verify.log" 2>&1; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$TMPDIR/verify.log"` →
`10 PASS` + `SKIP: zincir` + `KAPI YEŞİL`. `pytest` adımının özet satırında `deselected` sayısı = `sitedb` testleri (18).

- [ ] **Step 16: Commit**

```bash
git add db/migrations/0014_site_read.sql tests/sql_text.py tests/site_db.py tests/test_site_migration_text.py \
  tests/test_site_template_subset.py tests/test_site_harness_rules.py tests/test_site_views_db.py \
  pyproject.toml verify.sh scripts/sandbox_db.sh docs/RUNBOOK.md
git commit -m "feat: 0014 — sitenin salt okuma katmanı (site_reader, site/site_input/site_audit) ve şablonlu test yalıtımı (Faz 6 B-1)

Canlıya UYGULANMADI (§0.7 onayı). Kapının pytest/sızıntı seçicileri sitedb'yi dışlar; site-db adımı Task 9.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Slug fonksiyonu ve `verify-snapshot`

**Kademe:** K1 · **Spec:** §5.1 (`verify-snapshot`), H1e, H2b–c, H3a, H5b, §4.3 (yasak anahtarlar), N3 (sıralılık),
§5.4 (hassasiyet), §8.1–§8.2 (slug kuralları) · **Bağımlılık:** Task 1 · **Worktree:** `wt-b1-t4`

`verify-snapshot` DB'sizdir; dışa aktarıcı (Task 6) aynı fonksiyonu yazmadan ÖNCE çağırır, `site.yml` ve B-2 CLI'ı
çağırır. Metin taramaları (H1 tarih, H2, H5, yasak anahtarlar) şekilden bağımsızdır ve şema kırmızı olsa da koşar;
şekle dayanan kontroller yalnız şema geçerse koşar. Hata metinleri JSON yolunu ve kuralı söyler, DEĞERİ basmaz (log
public; reddedilen değer bir DSN olabilir). Slug fonksiyonu `naming.normalise_team`e dayanmaz; dondurulmuş vektörler
fonksiyon değişikliğini kırmızı yapar.

**Files:**
- Create: `src/football_edge/site/slugs.py`, `src/football_edge/site/verify.py`, `src/football_edge/site/__main__.py`
  (bu görevde yalnız `verify-snapshot`; Task 6 `export` ve `derive-stdin`i ekler)
- Test: `tests/test_site_slugs.py`, `tests/test_site_verify.py`

**Interfaces:**
- Consumes: Task 1 `contract` (`FORBIDDEN_KEYS`, `PATH_ID_LENGTH`, `PUBLIC_FLOOR`, `RESERVED_*`,
  `SITE_MIN_TEAM_MATCHES`, `content_sha256`, `iso_z`, `SCHEMA_PATH`, `EXIT_SITE_INVALID`), `schema.validate`,
  `schema.check_schema`; `collect.configure_logging`.
- Produces (Task 5, 6, 8 ve B-2):
  ```python
  # football_edge.site.slugs
  def slugify(text: str) -> str            # ASCII; harf/rakam yoksa ValueError("slug üretilemedi: …")
  def match_slug(home: str, away: str) -> str   # "{slugify(home)}-vs-{slugify(away)}"
  # football_edge.site.verify
  def snapshot_errors(snapshot: object, schema: Mapping[str, Any]) -> list[str]   # boş = yayımlanabilir
  ```
  CLI: `uv run python -m football_edge.site verify-snapshot <snapshot.json> [--sha256 <snapshot.sha256>]` (depo
  kökünden; şemayı `web/contract/snapshot.schema.json`dan okur) → geçerliyse exit 0 ve `anlık görüntü geçerli: <ad>`,
  değilse exit 24 ve her ihlal için `ANLIK GÖRÜNTÜ İHLALİ: <$.yol>: <kural>` satırı.

- [ ] **Step 1: Slug testini yaz**

`tests/test_site_slugs.py` (tam içerik):

````python
"""Site slug'ları (§8.2): dondurulmuş vektörler. Bir vektör değişirse yayımlanmış URL değişir."""

from __future__ import annotations

import pytest

from football_edge.site.slugs import match_slug, slugify

FROZEN = [
    ("Beşiktaş JK", "besiktas-jk"),
    ("İstanbul Başakşehir", "istanbul-basaksehir"),
    ("Kasımpaşa", "kasimpasa"),
    ("IRAN", "iran"),
    ("Çaykur Rizespor", "caykur-rizespor"),
    ("Fenerbahçe", "fenerbahce"),
    ("Göztepe", "goztepe"),
    ("Atlético Madrid", "atletico-madrid"),
    ("Borussia Mönchengladbach", "borussia-monchengladbach"),
    ("Deportivo Alavés", "deportivo-alaves"),
    ("Śląsk Wrocław", "slask-wroclaw"),
    ("Bodø/Glimt", "bodo-glimt"),
    ("Straße", "strasse"),
    ("Gaziantep F.K.", "gaziantep-f-k"),
    ("Fatih Karagümrük A.Ş.", "fatih-karagumruk-a-s"),
    ("1. FC Köln", "1-fc-koln"),
    ("Brighton & Hove Albion", "brighton-hove-albion"),
    ("Paris Saint-Germain", "paris-saint-germain"),
    ("Newell's Old Boys", "newells-old-boys"),
    ("  --Real  Madrid--  ", "real-madrid"),
]


@pytest.mark.parametrize(("name", "slug"), FROZEN)
def test_frozen_vectors(name: str, slug: str) -> None:
    assert slugify(name) == slug


@pytest.mark.parametrize("name", ["", "   ", "---", "‘’"])
def test_a_name_without_letters_or_digits_has_no_slug(name: str) -> None:
    with pytest.raises(ValueError, match="slug üretilemedi"):
        slugify(name)


def test_the_match_segment_joins_the_two_team_slugs() -> None:
    assert match_slug("Beşiktaş JK", "Fenerbahçe") == "besiktas-jk-vs-fenerbahce"


def test_slugs_do_not_follow_the_matching_key() -> None:
    """`naming.normalise_team` ekleri atar; URL'ler eşleşme düzeltmesiyle sessizce değişmemeli."""
    assert slugify("Gaziantep FK") != slugify("Gaziantep")
````

- [ ] **Step 2: `verify-snapshot` testini yaz**

`tests/test_site_verify.py` (tam içerik):

````python
"""`verify-snapshot` (§5.1): DB'siz denetim — H1/H2/H3/H5, §4.3 yasak anahtarlar, sıra, hash.

Her ihlal fixture'ın küçük bir kopyasında kurulur; kopya yeniden hash'lenir ki yalnız sınanan kural
kırmızı versin (hash kuralı kendi testinde).
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from football_edge.site.contract import EXIT_SITE_INVALID, content_sha256
from football_edge.site.verify import snapshot_errors

REPO = Path(__file__).resolve().parent.parent
SCHEMA: dict[str, Any] = json.loads(
    (REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8")
)
BASE = REPO / "web/fixtures/snapshot.fixture.json"
FULL_RECORD = REPO / "web/fixtures/snapshot.fixture-record.json"


def _fixture(path: Path = BASE) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _broken(change: Callable[[dict[str, Any]], None], path: Path = BASE) -> list[str]:
    snapshot = copy.deepcopy(_fixture(path))
    change(snapshot)
    snapshot["content_sha256"] = content_sha256(snapshot)
    return snapshot_errors(snapshot, SCHEMA)


def _set(path: str, value: Any) -> Callable[[dict[str, Any]], None]:
    """`matches.0.home` gibi noktalı yolun hedefine değer yazar."""

    def change(snapshot: dict[str, Any]) -> None:
        node: Any = snapshot
        *parents, last = path.split(".")
        for part in parents:
            node = node[int(part)] if isinstance(node, list) else node[part]
        node[int(last) if isinstance(node, list) else last] = value

    return change


@pytest.mark.parametrize("path", [BASE, FULL_RECORD], ids=lambda path: path.name)
def test_the_fixtures_pass_every_rule(path: Path) -> None:
    assert snapshot_errors(_fixture(path), SCHEMA) == []


@pytest.mark.leakage
def test_a_match_before_the_floor_is_red() -> None:
    """H1e: taban komşusu (2026-07-01) anlık görüntüde olamaz."""

    def before_floor(snapshot: dict[str, Any]) -> None:
        snapshot["matches"][0]["commence_time"] = "2026-07-01T23:59:59Z"
        snapshot["matches"][0]["date"] = "2026-07-01"

    errors = _broken(before_floor)

    assert any("commence_time: holdout tabanından eski" in error for error in errors), errors


@pytest.mark.leakage
def test_an_old_date_in_any_string_is_red_whatever_the_key() -> None:
    errors = _broken(_set("teams.0.name", "Alfa 2026-01-15"))

    assert any("$.teams[0].name: holdout tabanından eski tarih" in e for e in errors), errors


@pytest.mark.parametrize("text", ["http://x.invalid", "HTTPS://X", "a<b", "a>b"])
def test_links_and_markup_in_a_data_string_are_red(text: str) -> None:
    """H2c."""
    errors = _broken(_set("matches.0.home", text))

    assert any("$.matches[0].home: bağlantı ya da işaretleme" in e for e in errors), errors


@pytest.mark.parametrize(
    "text",
    [
        "postgres" + "://u@h/d",
        "postgresql" + "://u@h/d",
        "service" + "_role",
        "eyJ" + "hbGciOi",
        "SUPABASE" + "_ANON",
        "NETLIFY" + "_AUTH_TOKEN",
    ],
)
def test_credential_patterns_are_red_and_the_value_is_not_echoed(text: str) -> None:
    """H5b: hata metni yolu ve kuralı söyler; değeri basmaz (log public)."""
    value = f"önek {text} sonek"
    errors = _broken(_set("leagues.0.country", value))

    assert any("$.leagues[0].country:" in error and "(H5)" in error for error in errors), errors
    assert all(value not in error for error in errors)


def test_a_forbidden_key_is_red_at_any_depth_even_when_the_schema_also_fails() -> None:
    """§4.3: `additionalProperties: false` bilinmeyeni durdurur; yasak anahtar ADIYLA da görünür."""
    errors = _broken(_set("matches.0.h2h.latest.price", 2.1))

    assert any("$.matches[0].h2h.latest.price: yayımlanmayan anahtar" in e for e in errors)


def test_a_value_badge_is_red() -> None:
    """H3/B6."""
    errors = _broken(_set("value_badge", {"match_id": "x"}))

    assert any("$.value_badge" in error for error in errors), errors


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        (lambda s: s["matches"].reverse(), "$.matches[1]: sıra bozuk"),
        (lambda s: s["teams"].reverse(), "$.teams[1]: sıra bozuk"),
        (lambda s: s["leagues"].reverse(), "$.leagues[1]: sıra bozuk"),
    ],
)
def test_every_array_must_follow_its_declared_order(
    change: Callable[[dict[str, Any]], None], needle: str
) -> None:
    """N3: sıralı diziler; `sorted` kaldırılırsa kırmızı bu testten gelir."""
    assert any(needle in error for error in _broken(change)), needle


def test_a_record_entry_out_of_order_is_red() -> None:
    errors = _broken(lambda s: s["record"]["entries"].reverse(), FULL_RECORD)

    assert any("$.record.entries[1]: sıra bozuk" in error for error in errors), errors


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        (_set("matches.0.h2h.opening.p.home", 46.12), "$.matches[0].h2h.opening.p.home: 1 ondalık"),
        (_set("matches.0.move.home", 3.75), "$.matches[0].move.home: 1 ondalık"),
        (_set("leagues.0.move_distribution.p50", 3.14), "move_distribution.p50: 1 ondalık"),
    ],
)
def test_numbers_travel_at_display_precision(
    change: Callable[[dict[str, Any]], None], needle: str
) -> None:
    """§5.4: TS yuvarlamaz; fazla hassasiyet kırmızıdır."""
    assert any(needle in error for error in _broken(change)), needle


def test_a_clv_with_three_decimals_is_red() -> None:
    errors = _broken(_set("record.entries.0.clv", 2.145), FULL_RECORD)

    assert any("$.record.entries[0].clv: 2 ondalıktan fazla" in e for e in errors), errors


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        (_set("record.published", 1), "$.record.published"),
        (_set("leagues.0.matches", 99), "$.leagues[0].matches"),
        (_set("teams.0.matches", 9), "$.teams[0].matches"),
        (_set("teams.1.indexable", True), "$.teams[1].indexable"),
        (_set("matches.0.path_id", "000000000000"), "$.matches[0].path_id"),
        (_set("matches.0.slug", "x-vs-y"), "$.matches[0].slug"),
        (_set("matches.0.date", "2026-09-30"), "$.matches[0].date"),
        (_set("leagues.0.slug", "track-record"), "$.leagues[0].slug"),
        (_set("teams.0.slug", "match"), "$.teams[0].slug"),
        (_set("ledger.anchor.last_id", 10**6), "$.ledger.anchor"),
    ],
)
def test_internal_consistency(change: Callable[[dict[str, Any]], None], needle: str) -> None:
    assert any(needle in error for error in _broken(change)), needle


def test_an_unsealed_match_cannot_show_a_closing_round() -> None:
    def closing_on_unsealed(snapshot: dict[str, Any]) -> None:
        unsealed = next(m for m in snapshot["matches"] if not m["sealed"])
        unsealed["h2h"]["closing"] = unsealed["h2h"]["latest"]

    assert any("mühürsüz maçta kapanış" in error for error in _broken(closing_on_unsealed))


def test_a_stale_content_hash_is_red() -> None:
    snapshot = _fixture()
    snapshot["matches"][0]["rounds"] += 1  # hash yeniden hesaplanmadı

    assert any("$.content_sha256" in error for error in snapshot_errors(snapshot, SCHEMA))


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "football_edge.site", "verify-snapshot", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"},
        check=False,
    )


def test_the_cli_accepts_a_fixture_and_rejects_a_broken_copy(tmp_path: Path) -> None:
    broken = _fixture()
    broken["matches"][0]["home"] = "http://x.invalid"
    target = tmp_path / "snapshot.json"
    target.write_text(json.dumps(broken), encoding="utf-8")

    good, bad = _cli(str(BASE)), _cli(str(target))

    assert good.returncode == 0, good.stdout + good.stderr
    assert bad.returncode == EXIT_SITE_INVALID
    assert "ANLIK GÖRÜNTÜ İHLALİ: $.matches[0].home" in bad.stdout
    assert "http://x.invalid" not in bad.stdout + bad.stderr


def test_the_cli_checks_the_file_hash_when_asked(tmp_path: Path) -> None:
    target = tmp_path / "snapshot.json"
    target.write_bytes(BASE.read_bytes())
    digest = tmp_path / "snapshot.sha256"
    digest.write_text("0" * 64 + "  snapshot.json\n", encoding="utf-8")

    result = _cli(str(target), "--sha256", str(digest))

    assert result.returncode == EXIT_SITE_INVALID
    assert "snapshot.sha256: dosya baytlarının sha256'sı değil" in result.stdout
````

- [ ] **Step 3: Kırmızıyı gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_slugs.py tests/test_site_verify.py`
Expected: toplama hatası `No module named 'football_edge.site.slugs'` / `'football_edge.site.verify'`.

- [ ] **Step 4: Slug fonksiyonunu yaz**

`src/football_edge/site/slugs.py` (tam içerik):

````python
"""Sitenin URL bölütleri (Faz 6 İz B tasarımı §8.2).

`naming.normalise_team`e DAYANMAZ: o, kaynaklar arası eşleşme için yük taşır ve eşleşme düzeltmesi
URL'leri sessizce değiştirmemeli. Bu fonksiyonun her değişikliği `tests/test_site_slugs.py`deki
dondurulmuş vektörleri kırmızı yapar — yayımlanmış bir URL'yi değiştirmek bilinçli bir karardır.
"""

from __future__ import annotations

import re
import unicodedata

# NFKD'nin ayrıştırmadığı harfler (birleştirici işaret taşımazlar).
_FOLD = str.maketrans(
    {
        "İ": "i",
        "I": "i",
        "ı": "i",
        "ß": "ss",
        "ø": "o",
        "Ø": "o",
        "æ": "ae",
        "Æ": "ae",
        "œ": "oe",
        "Œ": "oe",
        "đ": "d",
        "Đ": "d",
        "ł": "l",
        "Ł": "l",
    }
)
_APOSTROPHES = re.compile(r"['’ʼ`]")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """ASCII küçük harf, rakam ve tek tire: `Beşiktaş JK` → `besiktas-jk`.

    Kesme işareti silinir (`Newell's` → `newells`); başka her harf dışı dizi tek tireye iner.
    Harf ya da rakam kalmazsa `ValueError`: boş bölüt yol üretmez.
    """
    folded = unicodedata.normalize("NFKD", text.translate(_FOLD))
    ascii_only = "".join(char for char in folded if not unicodedata.combining(char))
    lowered = _APOSTROPHES.sub("", ascii_only).lower()
    slug = _NON_SLUG.sub("-", lowered).strip("-")
    if not slug:
        raise ValueError(f"slug üretilemedi: {text!r}")
    return slug


def match_slug(home: str, away: str) -> str:
    """Maç yolunun süs bölütü (`{home}-vs-{away}`); yolun kimliği `path_id`dir (§8.1)."""
    return f"{slugify(home)}-vs-{slugify(away)}"
````

- [ ] **Step 5: Denetimi yaz**

`src/football_edge/site/verify.py` (tam içerik):

````python
"""`verify-snapshot`: anlık görüntünün DB'siz denetimi (Faz 6 İz B tasarımı §5.1, H1–H5).

Hata metinleri JSON yolunu ve kuralı adlandırır, DEĞERİ basmaz: log public'tir ve reddedilen değer
tam da sızmaması gereken şey olabilir (ör. bir DSN).
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from football_edge.site.contract import (
    FORBIDDEN_KEYS,
    PATH_ID_LENGTH,
    PUBLIC_FLOOR,
    RESERVED_LEAGUE_SLUGS,
    RESERVED_TEAM_SLUGS,
    SITE_MIN_TEAM_MATCHES,
    content_sha256,
    iso_z,
)
from football_edge.site.schema import validate
from football_edge.site.slugs import match_slug, slugify

_DATE = re.compile(r"(?<![0-9])([0-9]{4})-([0-9]{2})-([0-9]{2})(?![0-9])")
_MARKUP = ("http", "<", ">")  # H2c: bağlantı ve işaretleme taşıyan veri dizesi yok
_SECRETS = ("postgres://", "postgresql://", "service_role", "supabase_", "netlify_auth")
_JWT = "eyJ"  # JWT öneki; büyük/küçük harf duyarlı
_ONE_DECIMAL = ("p", "move", "move_distribution")
_TWO_DECIMALS = ("clv", "mean_clv", "ci_low", "ci_high", "published_price", "closing_fair_price")


def snapshot_errors(snapshot: object, schema: Mapping[str, Any]) -> list[str]:
    """Bütün kuralların ihlalleri; boş liste = yayımlanabilir.

    Metin taramaları (H1 tarih, H2, H5, yasak anahtarlar) şekilden bağımsızdır ve HER ZAMAN koşar;
    şekle dayanan kontroller yalnız şema geçerse koşar.
    """
    found = [*validate(snapshot, schema), *_date_errors(snapshot), *_text_errors(snapshot, "$")]
    if found or not isinstance(snapshot, dict):
        return found
    return [
        *_order_errors(snapshot),
        *_floor_errors(snapshot),
        *_precision_errors(snapshot, "$"),
        *_consistency_errors(snapshot),
        *_ledger_errors(snapshot["ledger"]),
        *_hash_errors(snapshot),
    ]


def _strictly_increasing(items: Sequence[Any], key: Any, name: str) -> Iterator[str]:
    keys = [key(item) for item in items]
    for index in range(1, len(keys)):
        if not keys[index - 1] < keys[index]:
            yield f"$.{name}[{index}]: sıra bozuk ya da tekrar (tanımlı anahtar)"


def _order_errors(snapshot: dict[str, Any]) -> Iterator[str]:
    yield from _strictly_increasing(snapshot["leagues"], lambda item: item["id"], "leagues")
    yield from _strictly_increasing(
        snapshot["teams"], lambda item: (item["league_id"], item["slug"]), "teams"
    )
    yield from _strictly_increasing(
        snapshot["matches"], lambda item: (item["commence_time"], item["id"]), "matches"
    )
    yield from _strictly_increasing(
        snapshot["record"]["entries"], lambda item: item["publication_id"], "record.entries"
    )


def _floor_errors(snapshot: dict[str, Any]) -> Iterator[str]:
    floor_text = iso_z(PUBLIC_FLOOR)
    for index, match in enumerate(snapshot["matches"]):
        if match["commence_time"] < floor_text:
            yield f"$.matches[{index}].commence_time: holdout tabanından eski (H1)"


def _date_errors(snapshot: object) -> Iterator[str]:
    """H1e: tabandan eski HİÇBİR tarih — alan adından bağımsız, her dizede."""
    floor_day = iso_z(PUBLIC_FLOOR)[:10]
    for path, text in _strings(snapshot, "$"):
        for found in _DATE.finditer(text):
            if "-".join(found.groups()) < floor_day:
                yield f"{path}: holdout tabanından eski tarih (H1)"


def _strings(node: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _strings(value, f"{path}[{index}]")


def _text_errors(node: Any, path: str) -> Iterator[str]:
    """H2c, H5b ve §4.3'ün yasak anahtarları; anahtar adları da taranır."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_KEYS:
                yield f"{path}.{key}: yayımlanmayan anahtar (§4.3)"
            yield from _secret_errors(key, f"{path}.{key} (anahtar)")
            yield from _text_errors(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _text_errors(value, f"{path}[{index}]")
    elif isinstance(node, str):
        lowered = node.lower()
        for mark in _MARKUP:
            if mark in lowered:
                yield f"{path}: bağlantı ya da işaretleme ({mark!r}) taşıyor (H2)"
        yield from _secret_errors(node, path)


def _secret_errors(text: str, path: str) -> Iterator[str]:
    lowered = text.lower()
    for mark in _SECRETS:
        if mark in lowered:
            yield f"{path}: kimlik bilgisi kalıbı ({mark!r}) taşıyor (H5)"
    if _JWT in text:
        yield f"{path}: JWT öneki taşıyor (H5)"


def _precision_errors(node: Any, path: str, digits: int | None = None) -> Iterator[str]:
    """§5.4: sayılar görüntü hassasiyetinde taşınır; TS yuvarlamaz."""
    if isinstance(node, dict):
        for key, value in node.items():
            inner = 1 if key in _ONE_DECIMAL else 2 if key in _TWO_DECIMALS else digits
            yield from _precision_errors(value, f"{path}.{key}", inner)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _precision_errors(value, f"{path}[{index}]", digits)
    elif isinstance(node, float) and digits is not None and round(node, digits) != node:
        yield f"{path}: {digits} ondalıktan fazla hassasiyet (§5.4)"


def _consistency_errors(snapshot: dict[str, Any]) -> Iterator[str]:
    leagues = {league["id"]: league for league in snapshot["leagues"]}
    matches = snapshot["matches"]
    league_slugs = [league["slug"] for league in snapshot["leagues"]]
    if len(set(league_slugs)) != len(league_slugs):
        yield "$.leagues: slug tekrarı"
    for index, league in enumerate(snapshot["leagues"]):
        if league["slug"] != slugify(league["name"]) or league["slug"] in RESERVED_LEAGUE_SLUGS:
            yield f"$.leagues[{index}].slug: addan türemiyor ya da ayrılmış (§8.1)"
        own = sum(1 for match in matches if match["league_id"] == league["id"])
        if league["matches"] != own:
            yield f"$.leagues[{index}].matches: maç listesiyle uyuşmuyor"
    yield from _team_errors(snapshot, leagues)
    yield from _match_errors(matches, leagues)
    yield from _record_errors(snapshot["record"])


def _team_errors(snapshot: dict[str, Any], leagues: Mapping[str, Any]) -> Iterator[str]:
    names: dict[tuple[str, str], int] = {}
    for match in snapshot["matches"]:
        for name in (match["home"], match["away"]):
            key = (match["league_id"], name)
            names[key] = names.get(key, 0) + 1
    listed = {(team["league_id"], team["name"]) for team in snapshot["teams"]}
    if listed != set(names):
        yield "$.teams: maçlardaki takım kümesiyle uyuşmuyor"
    for index, team in enumerate(snapshot["teams"]):
        at = f"$.teams[{index}]"
        if team["league_id"] not in leagues:
            yield f"{at}.league_id: bilinmeyen lig"
        if team["slug"] != slugify(team["name"]) or team["slug"] in RESERVED_TEAM_SLUGS:
            yield f"{at}.slug: addan türemiyor ya da ayrılmış (§8.1)"
        if team["matches"] != names.get((team["league_id"], team["name"]), 0):
            yield f"{at}.matches: maç listesiyle uyuşmuyor"
        if team["indexable"] != (team["matches"] >= SITE_MIN_TEAM_MATCHES):
            yield f"{at}.indexable: eşikle uyuşmuyor (§8.4)"


def _match_errors(matches: Sequence[Any], leagues: Mapping[str, Any]) -> Iterator[str]:
    path_ids: set[str] = set()
    for index, match in enumerate(matches):
        at = f"$.matches[{index}]"
        if match["league_id"] not in leagues:
            yield f"{at}.league_id: bilinmeyen lig"
        if match["path_id"] != match["id"][:PATH_ID_LENGTH] or match["path_id"] in path_ids:
            yield f"{at}.path_id: kimliğin öneki değil ya da çakışıyor (§8.1)"
        path_ids.add(match["path_id"])
        if match["slug"] != match_slug(match["home"], match["away"]):
            yield f"{at}.slug: takım adlarından türemiyor"
        if match["date"] != match["commence_time"][:10]:
            yield f"{at}.date: başlama anının UTC günü değil"
        if match["rounds"] < 1:
            yield f"{at}.rounds: kesimde satırı olmayan maç"
        if not match["sealed"] and match["h2h"]["closing"] is not None:
            yield f"{at}.h2h.closing: mühürsüz maçta kapanış"


def _record_errors(record: dict[str, Any]) -> Iterator[str]:
    if record["published"] != len(record["entries"]):
        yield "$.record.published: girdi sayısıyla uyuşmuyor"
    summary = record["summary"]
    if (summary is None) != (record["published"] == 0):
        yield "$.record.summary: yalnız boş sicilde null olur"
    if summary is not None and summary["n"] != record["published"]:
        yield "$.record.summary.n: yayın sayısıyla uyuşmuyor"


def _ledger_errors(ledger: dict[str, Any]) -> Iterator[str]:
    anchor = ledger["anchor"]
    if not ledger["rows"] <= ledger["last_id"]:
        yield "$.ledger: satır sayısı son kimliği aşıyor"
    if anchor["rows"] > ledger["rows"] or anchor["last_id"] > ledger["last_id"]:
        yield "$.ledger.anchor: çıpa kesimden ileride"


def _hash_errors(snapshot: dict[str, Any]) -> Iterator[str]:
    if content_sha256(snapshot) != snapshot["content_sha256"]:
        yield "$.content_sha256: gövdenin yeniden hesaplanan hash'iyle uyuşmuyor"
````

- [ ] **Step 6: CLI'ı yaz (bu görevde yalnız `verify-snapshot`)**

`src/football_edge/site/__main__.py` (tam içerik):

````python
"""`python -m football_edge.site verify-snapshot` (Faz 6 İz B §5.1).

`verify-snapshot`: anlık görüntünün DB'siz denetimi; B-2 ve `site.yml` bu komutu çağırır. Dışa
aktarım (`export`) ve ikinci türetimin iç komutu (`derive-stdin`) Task 6'da eklenir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from football_edge.collect import configure_logging
from football_edge.site.contract import EXIT_SITE_INVALID, SCHEMA_PATH
from football_edge.site.schema import check_schema
from football_edge.site.verify import snapshot_errors


def _schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    check_schema(schema)
    return schema


def _verify(path: Path, sha256_file: Path | None) -> int:
    payload = path.read_bytes()
    errors = snapshot_errors(json.loads(payload), _schema())
    if sha256_file is not None:
        recorded = sha256_file.read_text(encoding="utf-8").split()
        if not recorded or recorded[0] != hashlib.sha256(payload).hexdigest():
            errors.append(f"{sha256_file.name}: dosya baytlarının sha256'sı değil")
    for text in errors:
        sys.stdout.write(f"ANLIK GÖRÜNTÜ İHLALİ: {text}\n")
    if errors:
        return EXIT_SITE_INVALID
    sys.stdout.write(f"anlık görüntü geçerli: {path.name}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m football_edge.site")
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify-snapshot", help="anlık görüntünün DB'siz denetimi")
    verify.add_argument("path", type=Path)
    verify.add_argument("--sha256", type=Path, default=None)
    args = parser.parse_args(argv)
    configure_logging()
    return _verify(args.path, args.sha256)


if __name__ == "__main__":
    raise SystemExit(main())
````

- [ ] **Step 7: Yeşili gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_slugs.py tests/test_site_verify.py tests/test_site_import_rule.py`
Expected: `68 passed` (26 + 38 + 4). Fixture'ların ikisi de BÜTÜN kurallardan geçer.

- [ ] **Step 8: Mutasyonla kırmızı kanıtı**

| Dosya | Eski → yeni | Kırmızı |
|---|---|---|
| `src/football_edge/site/verify.py` | `        *_order_errors(snapshot),\n` → `` | `test_site_verify.py`: 4 failed (N3 — `sorted` kaldırılırsa kırmızının geleceği yer) |
| `src/football_edge/site/verify.py` | `*_date_errors(snapshot), ` → `` (ilk satırdaki liste öğesi) | `test_an_old_date_in_any_string_is_red_whatever_the_key` (H1e) |
| `src/football_edge/site/verify.py` | `"service_role", ` → `` | `test_credential_patterns…[service_role]` (H5b) |
| `src/football_edge/site/verify.py` | `if key in FORBIDDEN_KEYS:` → `if False:` | `test_a_forbidden_key_is_red_at_any_depth…` (§4.3) |
| `src/football_edge/site/slugs.py` | `"ı": "i",` → `` | `test_frozen_vectors[Kasımpaşa-kasimpasa]` |

- [ ] **Step 9: Lint ve tip** — `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`.

- [ ] **Step 10: Tam kapı** — `10 PASS` + `SKIP: zincir` + `KAPI YEŞİL`. Eklenen `leakage` testi: 2.

- [ ] **Step 11: Commit**

```bash
git add src/football_edge/site/slugs.py src/football_edge/site/verify.py src/football_edge/site/__main__.py \
  tests/test_site_slugs.py tests/test_site_verify.py
git commit -m "feat: site slug'ları ve verify-snapshot — H1/H2/H3/H5, yasak anahtarlar, sıra, hassasiyet (Faz 6 B-1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Girdi dökümü ve türetim (`site/inputs.py`, `site/derive.py`)

**Kademe:** K1 · **Spec:** §5.1/4–5 (döküm, iki türetim aynı dökümden), §5.2 (gövde), §5.4 (ham hesap, yuvarlama çıktıda),
§8.1 (`path_id`, slug), §8.4 (`indexable`), §6.4/3d (sicilin defterden yeniden hesabı), B7 · **Bağımlılık:** Task 2
(`round_consensus`), Task 4 (`slugs`) · **Worktree:** `wt-b1-t5`

Döküm kanonik JSON metnidir (`ledger._canonical`): sayılar METİN, zamanlar kanonik UTC metni, bool/None/metin aynen;
tipler dökümün şemasıyla açıktır. DB'nin ham tipleri türetime girmez — iki türetim de `load_inputs(döküm)`ün
tipleriyle çalışır. Türetim saf fonksiyondur: DB, saat, rastgelelik yok; konsensüs `market.consensus`, vig temizleme
`market.devig`, CLV ve güven aralığı `market.metrics` — model neyse site o. Testlerin beklenen değerleri ELLE
hesaplandı: adil kitaplar (Σ 1/o = 1) her yöntemde olduğu gibi döner (`2.0/4.0/4.0` → 50/25/25), simetrik marjlı
tur power yönteminde 33.3'e iner; türetme kodu beklenen değeri üretmek için çağrılmaz.

**Files:**
- Create: `src/football_edge/site/inputs.py`, `src/football_edge/site/derive.py`
- Create: `tests/site_builders.py` (sentetik turlar, zincirli satırlar, git'li çıpa deposu, döküm üretimi — Task 6 ve 7 de kullanır)
- Test: `tests/test_site_derive.py`

**Interfaces:**
- Consumes: `market.consensus.{LIVE_H2H, Quote, round_consensus}`, `market.devig.{devig, InvalidPrices}`,
  `market.metrics.{bootstrap_mean, clv}`, `ledger.{_canonical, canonical_timestamp, chain, GENESIS}`,
  `site.slugs.{slugify, match_slug}`, `site.contract.*`, `tests.fake_db.stored_row`.
- Produces (Task 6, 7):
  ```python
  # football_edge.site.inputs
  DUMP_VERSION = 1
  @dataclass(frozen=True) class DumpConfig: devig_method: str; min_books: int; min_team_matches: int; move_min_matches: int; path_id_length: int
  @dataclass(frozen=True) class LedgerCut: rows: int; last_id: int; head: str
  @dataclass(frozen=True) class AnchorValue: file: str; rows: int; last_id: int; head: str
  LeagueRow(id, name, country); MatchRow(id, league_id, commence_time, home, away)
  QuoteRow(ledger_id, match_id, observed_at, is_closing, outcome, price, book_key)
  RecordRow(<RECORD_COLUMNS sırasıyla>)
  @dataclass(frozen=True) class ExportInputs: config; floor; ledger; anchor; leagues; matches; quotes; record
  def encode(value: object) -> object
  def dump_text(*, config, floor, ledger, anchor, leagues, matches, quotes, record) -> str   # satırlar DB kolon sırasıyla
  def load_inputs(text: str) -> ExportInputs                                            # bozuk dökümde ValueError
  # football_edge.site.derive
  class DeriveError(ValueError)
  OUTCOMES = ("home", "draw", "away")
  def derive(inputs: ExportInputs) -> dict[str, Any]         # generated_at, git_sha, content_sha256 HARİÇ gövde
  def match_views(inputs: ExportInputs) -> tuple[MatchView, ...]
  def record_mismatches(inputs: ExportInputs) -> list[str]   # §6.4/3d; boş = tutarlı
  # tests.site_builders
  EVEN, AWAY_FAVOURED, DRAWISH, WIDE, HOME_HEAVY, HOME_LEAN, SYMMETRIC, BOOKS
  @dataclass(frozen=True) class Round: match_id; observed_at; home; away; books; is_closing=False; drop_away_for=None
  def payloads(rounds) -> tuple[dict[str, Any], ...]; def ledger(rows, *, first_id=1) -> tuple[dict[str, Any], ...]
  def anchored_repo(root: Path, *, rows: int, last_id: int, head: str, day: str) -> Path   # "<root>/ledger"
  def at(text: str) -> datetime; def quote_rows(rounds) -> list[tuple]
  def export_dump(*, leagues, matches, rounds, record=(), method="power") -> str
  def export_inputs(**parts) -> ExportInputs
  ```

- [ ] **Step 1: Test yapıcılarını yaz**

`tests/site_builders.py` (tam içerik):

````python
"""Site testlerinin sentetik defteri: turlar → zincirli satırlar, çıpa deposu, döküm girdileri.

Fiyatlar ADİL kitaplardır (Σ 1/o = 1): `devig` onları her yöntemde olduğu gibi döndürür, beklenen
olasılıklar elle yazılır (`2.0/4.0/4.0` → 50/25/25). Kitaplar arası ortalama da aynı fiyatsa adil
kalır; farklı adil kitapların ortalaması Σ < 1 verir ve temizlenemez — bu yüzden bir turdaki
kitaplar aynı üçlüyü taşır.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from football_edge.ledger import GENESIS, canonical_timestamp, chain
from football_edge.site.contract import (
    MOVE_MIN_MATCHES,
    PATH_ID_LENGTH,
    PUBLIC_FLOOR,
    SITE_MIN_BOOKS,
    SITE_MIN_TEAM_MATCHES,
)
from football_edge.site.inputs import (
    AnchorValue,
    DumpConfig,
    ExportInputs,
    LedgerCut,
    dump_text,
    load_inputs,
)
from tests.fake_db import stored_row

# Adil üçlüler (ev, beraberlik, deplasman) ve elle hesaplanmış yüzdeleri.
EVEN = (2.0, 4.0, 4.0)  # 50.0 / 25.0 / 25.0
AWAY_FAVOURED = (4.0, 4.0, 2.0)  # 25.0 / 25.0 / 50.0
DRAWISH = (5.0, 2.5, 2.5)  # 20.0 / 40.0 / 40.0
WIDE = (2.5, 5.0, 2.5)  # 40.0 / 20.0 / 40.0
HOME_HEAVY = (1.25, 10.0, 10.0)  # 80.0 / 10.0 / 10.0
HOME_LEAN = (1.6, 8.0, 4.0)  # 62.5 / 12.5 / 25.0
# Marjlı ama simetrik: üç kitabın ortalaması 2.8/2.8/2.8 → power yöntemi 33.3 / 33.3 / 33.3.
SYMMETRIC = ((2.7, 2.7, 2.7), (2.8, 2.8, 2.8), (2.9, 2.9, 2.9))
BOOKS = ("kitap-a", "kitap-b", "kitap-c", "kitap-d")


@dataclass(frozen=True)
class Round:
    match_id: str
    observed_at: str  # ISO, Z
    home: str
    away: str
    books: Sequence[tuple[float, float, float]]
    is_closing: bool = False
    drop_away_for: int | None = None  # bu sıradaki kitabın deplasman satırı yok (eksik kitap)


def payloads(rounds: Sequence[Round]) -> tuple[dict[str, Any], ...]:
    """Turları defter yüküne çevirir; sıra = defter sırası (kitap, sonra ev, beraberlik, dep.)."""
    found: list[dict[str, Any]] = []
    for item in rounds:
        for index, (home, draw, away) in enumerate(item.books):
            for outcome, price in ((item.home, home), ("Draw", draw), (item.away, away)):
                if outcome == item.away and item.drop_away_for == index:
                    continue
                found.append(
                    {
                        "match_id": item.match_id,
                        "observed_at": canonical_timestamp(item.observed_at),
                        "bookmaker": BOOKS[index],
                        "market": "h2h",
                        "outcome": outcome,
                        "point": None,
                        "price": price,
                        "bookmaker_last_update": canonical_timestamp(item.observed_at),
                        "is_closing": item.is_closing,
                    }
                )
    return tuple(found)


def ledger(rows: Sequence[dict[str, Any]], *, first_id: int = 1) -> tuple[dict[str, Any], ...]:
    """Zincirlenmiş, psycopg tipleriyle saklanmış satırlar (`id` 1'den)."""
    return tuple(
        {**stored_row(row), "id": index + first_id}
        for index, row in enumerate(chain(tuple(rows), prev_hash=GENESIS))
    )


def anchored_repo(root: Path, *, rows: int, last_id: int, head: str, day: str) -> Path:
    """Çıpa dosyasını geçici bir git deposuna commit'ler; `ledger/` dizinini döner.

    Çıpa eksikliği kontrolü git geçmişi ister (`test_verify_chain.py` deseni); geçmişsiz dizinde
    "ATLANDI" satırı dışa aktarımı her koşuda durdururdu.
    """
    directory = root / "ledger"
    directory.mkdir(parents=True)
    (directory / f"head-{day}.txt").write_text(
        f"{day}T12:00:00+00:00\nrows={rows}\nlast_id={last_id}\nhead={head}\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.email=t@example.com", "-c", "user.name=t"]
        + ["commit", "-q", "-m", "çıpa"],
        check=True,
    )
    return directory


def at(text: str) -> datetime:
    return datetime.fromisoformat(canonical_timestamp(text))


def quote_rows(rounds: Sequence[Round]) -> list[tuple[Any, ...]]:
    """`site_input.h2h_quotes` kolon sırasıyla satırlar; `book_key` = turdaki kitap sırası."""
    return [
        (
            ledger_id,
            row["match_id"],
            at(row["observed_at"]),
            row["is_closing"],
            row["outcome"],
            Decimal(str(row["price"])),
            BOOKS.index(row["bookmaker"]) + 1,
        )
        for ledger_id, row in enumerate(payloads(rounds), start=1)
    ]


def export_dump(
    *,
    leagues: Sequence[tuple[str, str, str]],
    matches: Sequence[tuple[str, str, str, str, str]],
    rounds: Sequence[Round],
    record: Sequence[tuple[Any, ...]] = (),
    method: str = "power",
) -> str:
    """Dışa aktarımın üreteceği döküm METNİ (`dump_text`), DB'siz."""
    quotes = quote_rows(rounds)
    last_id = len(quotes)
    return dump_text(
        config=DumpConfig(
            method, SITE_MIN_BOOKS, SITE_MIN_TEAM_MATCHES, MOVE_MIN_MATCHES, PATH_ID_LENGTH
        ),
        floor=PUBLIC_FLOOR,
        ledger=LedgerCut(last_id, last_id, "c" * 64),
        anchor=AnchorValue("head-2026-09-21.txt", last_id, last_id, "c" * 64),
        leagues=leagues,
        matches=[(mid, league, at(when), home, away) for mid, league, when, home, away in matches],
        quotes=quotes,
        record=record,
    )


def export_inputs(**parts: Any) -> ExportInputs:
    """`export_dump`in çözülmüş hâli — iki türetimin de çalıştığı tipler."""
    return load_inputs(export_dump(**parts))
````

- [ ] **Step 2: Türetim testini yaz (Review Focus 2 ve 5 dâhil)**

`tests/test_site_derive.py` (tam içerik):

````python
"""Döküm → gövde (§5.2, §5.4, §8.4): beklenen değerler ELLE hesaplandı, türetme kodu çağrılmadan.

Adil kitaplar (`site_builders`): `2.0/4.0/4.0` → 50.0/25.0/25.0 vb.; simetrik marjlı tur → 33.3.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from football_edge.site.contract import content_sha256
from football_edge.site.derive import DeriveError, derive, record_mismatches
from football_edge.site.verify import snapshot_errors
from tests.site_builders import (
    AWAY_FAVOURED,
    DRAWISH,
    EVEN,
    HOME_HEAVY,
    HOME_LEAN,
    SYMMETRIC,
    WIDE,
    Round,
    at,
    export_inputs,
)

REPO = Path(__file__).resolve().parent.parent
SCHEMA: dict[str, Any] = json.loads(
    (REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8")
)
LEAGUE = ("tst.1", "Deneme Ligi", "Testland")


def mid(number: int) -> str:
    return f"{number:02d}" + "ab" * 15


SEALED = Round(mid(1), "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3)
SEALED_MIDDLE = Round(
    mid(1), "2026-09-21T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3, drop_away_for=0
)
SEALED_CLOSE = Round(
    mid(1), "2026-09-22T13:00:00Z", "Alfa Spor", "Beta FK", SYMMETRIC, is_closing=True
)
OPEN_FIRST = Round(mid(2), "2026-09-20T11:00:00Z", "Gamma United", "Alfa Spor", [AWAY_FAVOURED] * 3)
OPEN_LATEST = Round(mid(2), "2026-09-21T11:00:00Z", "Gamma United", "Alfa Spor", [DRAWISH] * 3)
THIN = Round(mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [HOME_HEAVY] * 2)
MATCHES = [
    (mid(1), "tst.1", "2026-09-22T14:00:00Z", "Alfa Spor", "Beta FK"),
    (mid(2), "tst.1", "2026-09-23T15:00:00Z", "Gamma United", "Alfa Spor"),
    (mid(3), "tst.1", "2026-09-24T16:00:00Z", "Delta Şehir", "Beta FK"),
]


def _body(rounds: list[Round], **extra: Any) -> dict[str, Any]:
    return derive(export_inputs(leagues=[LEAGUE], matches=MATCHES, rounds=rounds, **extra))


def _match(body: dict[str, Any], number: int) -> dict[str, Any]:
    (found,) = [match for match in body["matches"] if match["id"] == mid(number)]
    return found


ROUNDS = [SEALED, SEALED_MIDDLE, SEALED_CLOSE, OPEN_FIRST, OPEN_LATEST, THIN]


def test_a_sealed_match_shows_opening_latest_closing_and_the_move_to_closing() -> None:
    match = _match(_body(ROUNDS), 1)

    assert match["sealed"] is True and match["rounds"] == 3
    assert match["h2h"]["opening"] == {
        "observed_at": "2026-09-20T10:00:00Z",
        "books": 3,
        "p": {"home": 50.0, "draw": 25.0, "away": 25.0},
    }
    closing = {
        "observed_at": "2026-09-22T13:00:00Z",
        "books": 3,
        "p": {"home": 33.3, "draw": 33.3, "away": 33.3},
    }
    assert match["h2h"]["closing"] == closing and match["h2h"]["latest"] == closing
    # Ham farktan yuvarlanır: 33.33 − 50 = −16.67 → −16.7; 33.33 − 25 = 8.33 → 8.3.
    assert match["move"] == {"home": -16.7, "draw": 8.3, "away": 8.3}
    assert match["indexable"] is True


def test_a_round_with_an_incomplete_book_counts_only_full_books() -> None:
    """Orta turda bir kitabın deplasman satırı yok: 2 tam kitap < 3 → tur sayılır, gösterilmez."""
    match = _match(_body([SEALED, SEALED_MIDDLE]), 1)

    assert match["rounds"] == 2
    assert match["h2h"]["latest"] is None
    assert match["move"] is None, "son tur görünmüyorsa hareket de yok"


def test_an_unsealed_match_moves_to_the_latest_round() -> None:
    match = _match(_body(ROUNDS), 2)

    assert match["sealed"] is False and match["h2h"]["closing"] is None
    assert match["h2h"]["latest"]["p"] == {"home": 20.0, "draw": 40.0, "away": 40.0}
    assert match["move"] == {"home": -5.0, "draw": 15.0, "away": -10.0}


def test_a_thin_single_round_match_is_listed_but_not_indexable() -> None:
    match = _match(_body(ROUNDS), 3)

    assert match["rounds"] == 1
    assert match["h2h"] == {"opening": None, "latest": None, "closing": None}
    assert match["move"] is None and match["indexable"] is False


def test_a_single_round_match_moves_by_exactly_zero() -> None:
    lone = Round(mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [EVEN] * 3)

    assert _match(_body([lone]), 3)["move"] == {"home": 0.0, "draw": 0.0, "away": 0.0}


def test_a_tiny_negative_move_is_shown_as_zero_not_minus_zero() -> None:
    """−0.04 pp bir ondalığa −0.0 yuvarlanır; sayfada "-0,0" görünmesin (§5.4)."""
    home, away = 1 / 0.4996, 1 / 0.2504  # adil kitap: 49.96 / 25.0 / 25.04
    first = Round(mid(3), "2026-09-20T10:00:00Z", "Delta Şehir", "Beta FK", [EVEN] * 3)
    later = Round(mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [(home, 4.0, away)] * 3)
    move = _match(_body([first, later]), 3)["move"]

    assert [str(value) for value in move.values()] == ["0.0", "0.0", "0.0"]


def test_a_round_whose_average_cannot_be_devigged_is_not_shown() -> None:
    """Σ 1/o < 1 (negatif marj) hiçbir yöntemde temizlenmez: tur null, türetim düşmez."""
    negative = Round(
        mid(3), "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [(2.1, 4.2, 4.2)] * 3
    )

    assert _match(_body([negative]), 3)["h2h"]["opening"] is None


def test_the_match_url_parts_and_date() -> None:
    match = _match(_body(ROUNDS), 3)

    assert match["path_id"] == mid(3)[:12]
    assert match["slug"] == "delta-sehir-vs-beta-fk"
    assert (match["date"], match["commence_time"]) == ("2026-09-24", "2026-09-24T16:00:00Z")


def test_teams_count_their_matches_and_cross_the_threshold_at_three() -> None:
    body = _body(ROUNDS)

    assert [(team["slug"], team["matches"], team["indexable"]) for team in body["teams"]] == [
        ("alfa-spor", 2, False),
        ("beta-fk", 2, False),
        ("delta-sehir", 1, False),
        ("gamma-united", 1, False),
    ]


def test_a_league_distribution_needs_five_sealed_moving_matches() -> None:
    """|hareket| en büyük bileşeni: 15, 25, 30, 12.5, 30 → numpy doğrusal yüzdelik 13.5/25/30."""
    ends = [WIDE, AWAY_FAVOURED, HOME_HEAVY, HOME_LEAN, DRAWISH]
    matches, rounds = [], []
    for number, end in enumerate(ends, start=10):
        kickoff = f"2026-09-2{number - 10}T18:00:00Z"
        matches.append((mid(number), "tst.1", kickoff, f"Ev {number}", f"Dep {number}"))
        rounds.append(
            Round(mid(number), "2026-09-19T08:00:00Z", f"Ev {number}", f"Dep {number}", [EVEN] * 3)
        )
        rounds.append(
            Round(
                mid(number),
                kickoff.replace("18:", "17:"),
                f"Ev {number}",
                f"Dep {number}",
                [end] * 3,
                is_closing=True,
            )
        )
    five = derive(export_inputs(leagues=[LEAGUE], matches=matches, rounds=rounds))
    four = derive(export_inputs(leagues=[LEAGUE], matches=matches[:4], rounds=rounds[:8]))

    assert five["leagues"][0]["move_distribution"] == {"p10": 13.5, "p50": 25.0, "p90": 30.0}
    assert four["leagues"][0]["move_distribution"] is None


@pytest.mark.parametrize(
    ("leagues", "matches", "needle"),
    [
        ([("tst.1", "Track Record", "X")], MATCHES, "lig tst.1: slug"),
        ([LEAGUE, ("tst.2", "Deneme  Ligi", "Y")], MATCHES, "lig tst.2: slug"),
        (
            [LEAGUE],
            [*MATCHES[:2], (mid(3), "tst.1", "2026-09-24T16:00:00Z", "Alfa-Spor", "Beta FK")],
            "takım slug",
        ),
        (
            [LEAGUE],
            [*MATCHES[:2], (mid(3), "tst.1", "2026-09-24T16:00:00Z", "Match", "Beta FK")],
            "takım slug",
        ),
    ],
)
def test_slug_collisions_and_reserved_slugs_stop_the_derivation(
    leagues: list[tuple[str, str, str]], matches: list[Any], needle: str
) -> None:
    rounds = [Round(m[0], "2026-09-21T09:00:00Z", m[3], m[4], [EVEN] * 3) for m in matches]

    with pytest.raises(DeriveError, match=needle):
        derive(export_inputs(leagues=leagues, matches=matches, rounds=rounds))


def test_two_matches_sharing_a_path_prefix_stop_the_derivation() -> None:
    twin = mid(1)[:12] + "cd" * 10
    matches = [MATCHES[0], (twin, "tst.1", "2026-09-25T16:00:00Z", "Eta", "Teta")]
    rounds = [SEALED, Round(twin, "2026-09-21T09:00:00Z", "Eta", "Teta", [EVEN] * 3)]

    with pytest.raises(DeriveError, match="path_id"):
        derive(export_inputs(leagues=[LEAGUE], matches=matches, rounds=rounds))


def test_an_empty_record_has_no_summary() -> None:
    assert _body(ROUNDS)["record"] == {"published": 0, "entries": [], "summary": None}


def _publication(
    number: int, outcome: str, price: float, clv: float, fair: float
) -> tuple[Any, ...]:
    return (
        number,
        mid(1),
        "h2h",
        outcome,
        at("2026-09-21T09:00:00Z"),
        price,
        3,
        1.0 / fair,
        clv,
        str(number) * 64,
    )


def test_a_filled_record_rounds_only_at_display_time() -> None:
    """Kapanış 1/3: 3.12 × 1/3 − 1 = 0.04 → %4.00; 3.06 × 1/3 − 1 = 0.02 → %2.00; ortalama %3.00."""
    record = [
        _publication(2, "away", 3.06, 3.06 / 3 - 1, 1 / 3),
        _publication(1, "home", 3.12, 3.12 / 3 - 1, 1 / 3),
    ]
    body = _body(ROUNDS, record=record)

    assert [entry["publication_id"] for entry in body["record"]["entries"]] == [1, 2]
    assert [entry["clv"] for entry in body["record"]["entries"]] == [4.0, 2.0]
    assert body["record"]["entries"][0]["closing_fair_price"] == 3.0
    summary = body["record"]["summary"]
    assert summary["n"] == 2 and summary["mean_clv"] == 3.0
    assert 2.0 <= summary["ci_low"] <= 3.0 <= summary["ci_high"] <= 4.0


def test_record_entries_are_recomputed_from_the_ledger_closing() -> None:
    """§6.4/3d: CLV ve kapanış adil oranı defterin kapanış konsensüsünden yeniden hesaplanır."""
    good = _publication(1, "home", 3.12, 3.12 * 0.3333333333333333 - 1, 0.3333333333333333)
    inputs = export_inputs(leagues=[LEAGUE], matches=MATCHES, rounds=ROUNDS, record=[good])
    assert record_mismatches(inputs) == []

    wrong_clv = (*good[:8], 0.5, good[9])
    unsealed = (good[0], mid(2), *good[2:])
    bad_outcome = (*good[:3], "H", *good[4:])
    late = (*good[:6], 10**6, *good[7:])
    for row, needle in (
        (wrong_clv, "CLV defterden"),
        (unsealed, "kapanış konsensüsü yok"),
        (bad_outcome, "sözleşme dışı"),
        (late, "kesimden sonraki"),
    ):
        broken = export_inputs(leagues=[LEAGUE], matches=MATCHES, rounds=ROUNDS, record=[row])
        assert any(needle in problem for problem in record_mismatches(broken)), needle


def test_the_body_is_the_same_on_every_call() -> None:
    inputs = export_inputs(leagues=[LEAGUE], matches=MATCHES, rounds=ROUNDS)

    assert content_sha256(derive(inputs)) == content_sha256(derive(inputs))


def test_a_derived_snapshot_passes_verify_and_orders_teams_by_slug_not_name() -> None:
    """N3: "Çınar" adda "Delta"dan sonra, slug'da (`cinar`) önce gelir; dizi slug'la sıralıdır."""
    matches = [(mid(1), "tst.1", "2026-09-22T14:00:00Z", "Delta Şehir", "Çınar Spor")]
    rounds = [Round(mid(1), "2026-09-20T10:00:00Z", "Delta Şehir", "Çınar Spor", [EVEN] * 3)]
    body = derive(export_inputs(leagues=[LEAGUE], matches=matches, rounds=rounds))
    snapshot = {**body, "generated_at": "2026-09-24T12:00:00Z", "git_sha": "1" * 40}
    snapshot["content_sha256"] = content_sha256(snapshot)

    assert [team["slug"] for team in body["teams"]] == ["cinar-spor", "delta-sehir"]
    assert snapshot_errors(snapshot, SCHEMA) == []


# ── Review Focus ──────────────────────────────────────────────────────────────────────────────


def test_review_focus_a_sealed_match_with_a_thin_closing_shows_no_closing_and_no_move() -> None:
    """Mühür turu yalnız iki tam kitap gördüyse: mühürlü, ama kapanış ve hareket gösterilmez."""
    opening = Round(mid(3), "2026-09-20T10:00:00Z", "Delta Şehir", "Beta FK", [EVEN] * 3)
    thin_close = Round(
        mid(3), "2026-09-24T15:00:00Z", "Delta Şehir", "Beta FK", [WIDE] * 2, is_closing=True
    )
    body = _body([opening, thin_close])
    match = _match(body, 3)
    snapshot = {**body, "generated_at": "2026-09-24T12:00:00Z", "git_sha": "1" * 40}
    snapshot["content_sha256"] = content_sha256(snapshot)

    assert match["sealed"] is True and match["rounds"] == 2
    assert match["h2h"]["closing"] is None and match["h2h"]["latest"] is None
    assert match["move"] is None and match["indexable"] is True
    assert snapshot_errors(snapshot, SCHEMA) == []


def test_review_focus_a_postponed_match_keeps_its_url_and_moves_its_date() -> None:
    """AK20(b): maç yolu değişmez kimlik taşır; erteleme yalnız görünen tarihi değiştirir."""
    moved = [
        (mid(3), "tst.1", "2026-10-02T19:45:00Z", "Delta Şehir", "Beta FK") if m[0] == mid(3) else m
        for m in MATCHES
    ]
    before = _match(_body(ROUNDS), 3)
    after = _match(derive(export_inputs(leagues=[LEAGUE], matches=moved, rounds=ROUNDS)), 3)

    assert (after["path_id"], after["slug"]) == (before["path_id"], before["slug"])
    assert (after["date"], after["commence_time"]) == ("2026-10-02", "2026-10-02T19:45:00Z")
````

- [ ] **Step 3: Kırmızıyı gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_derive.py`
Expected: toplama hatası `No module named 'football_edge.site.inputs'`.

- [ ] **Step 4: Dökümü yaz**

`src/football_edge/site/inputs.py` (tam içerik):

````python
"""Türetim girdi dökümü (Faz 6 İz B tasarımı §5.1/4–5).

Dışa aktarım işleminde okunan HER türetim girdisi — `site.*` ve `site_input.*` satırları, çıpa,
yapılandırma — tek bir kanonik JSON metnine (`ledger._canonical`) yazılır; iki türetim de bu
metinden çözülen tiplerle çalışır, DB'nin ham tipleri (`Decimal`, `datetime`) türetime girmez.
Sayılar metin olarak taşınır, tip dökümün şemasıyla açıktır. `site_audit` satırları dökümde
YOKTUR: zincir doğrulaması türetimden önce biter. Döküm kitap bazında fiyat taşır: diske ve loga
yazılmaz.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from football_edge.ledger import _canonical, canonical_timestamp

DUMP_VERSION = 1


@dataclass(frozen=True)
class DumpConfig:
    devig_method: str
    min_books: int
    min_team_matches: int
    move_min_matches: int
    path_id_length: int


@dataclass(frozen=True)
class LedgerCut:
    rows: int
    last_id: int
    head: str  # kesimin son satırının YENİDEN HESAPLANMIŞ hash'i


@dataclass(frozen=True)
class AnchorValue:
    file: str
    rows: int
    last_id: int
    head: str


@dataclass(frozen=True)
class LeagueRow:
    id: str
    name: str
    country: str


@dataclass(frozen=True)
class MatchRow:
    id: str
    league_id: str
    commence_time: datetime
    home: str
    away: str


@dataclass(frozen=True)
class QuoteRow:
    ledger_id: int
    match_id: str
    observed_at: datetime
    is_closing: bool
    outcome: str
    price: float
    book_key: int


@dataclass(frozen=True)
class RecordRow:
    publication_id: int
    match_id: str
    market: str
    outcome: str
    published_at: datetime
    published_price: float
    publication_ledger_id: int
    closing_fair_price: float
    clv: float
    publication_hash: str


@dataclass(frozen=True)
class ExportInputs:
    config: DumpConfig
    floor: datetime
    ledger: LedgerCut
    anchor: AnchorValue
    leagues: tuple[LeagueRow, ...]
    matches: tuple[MatchRow, ...]
    quotes: tuple[QuoteRow, ...]
    record: tuple[RecordRow, ...]


def encode(value: object) -> object:
    """DB değeri → döküm değeri: sayı metin, zaman kanonik UTC metni; bool, None, metin aynen."""
    if value is None or isinstance(value, bool | str):
        return value
    if isinstance(value, int | Decimal):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, datetime):
        return canonical_timestamp(value)
    raise TypeError(f"dökümde desteklenmeyen tip: {type(value).__name__}")


def dump_text(
    *,
    config: DumpConfig,
    floor: datetime,
    ledger: LedgerCut,
    anchor: AnchorValue,
    leagues: Sequence[Sequence[object]],
    matches: Sequence[Sequence[object]],
    quotes: Sequence[Sequence[object]],
    record: Sequence[Sequence[object]],
) -> str:
    """Satırları (DB'nin döndürdüğü kolon sırasıyla) kanonik döküm metnine çevirir."""
    return _canonical(
        {
            "version": DUMP_VERSION,
            "config": {name: encode(value) for name, value in vars(config).items()},
            "floor": encode(floor),
            "ledger": {name: encode(value) for name, value in vars(ledger).items()},
            "anchor": {name: encode(value) for name, value in vars(anchor).items()},
            "leagues": [[encode(value) for value in row] for row in leagues],
            "matches": [[encode(value) for value in row] for row in matches],
            "quotes": [[encode(value) for value in row] for row in quotes],
            "record": [[encode(value) for value in row] for row in record],
        }
    )


def load_inputs(text: str) -> ExportInputs:
    """Döküm metnini tiplerine çözer; biçim bozuksa `ValueError`."""
    raw = json.loads(text)
    if raw.get("version") != DUMP_VERSION:
        raise ValueError("döküm sürümü tanınmıyor")
    config = raw["config"]
    return ExportInputs(
        config=DumpConfig(
            devig_method=str(config["devig_method"]),
            min_books=int(config["min_books"]),
            min_team_matches=int(config["min_team_matches"]),
            move_min_matches=int(config["move_min_matches"]),
            path_id_length=int(config["path_id_length"]),
        ),
        floor=_time(raw["floor"]),
        ledger=LedgerCut(
            int(raw["ledger"]["rows"]), int(raw["ledger"]["last_id"]), raw["ledger"]["head"]
        ),
        anchor=_anchor(raw["anchor"]),
        leagues=tuple(LeagueRow(str(a), str(b), str(c)) for a, b, c in raw["leagues"]),
        matches=tuple(_match(row) for row in raw["matches"]),
        quotes=tuple(_quote(row) for row in raw["quotes"]),
        record=tuple(_record(row) for row in raw["record"]),
    )


def _time(text: object) -> datetime:
    return datetime.fromisoformat(str(text))


def _anchor(raw: Mapping[str, Any]) -> AnchorValue:
    return AnchorValue(str(raw["file"]), int(raw["rows"]), int(raw["last_id"]), str(raw["head"]))


def _match(row: Sequence[Any]) -> MatchRow:
    match_id, league_id, commence_time, home, away = row
    return MatchRow(str(match_id), str(league_id), _time(commence_time), str(home), str(away))


def _quote(row: Sequence[Any]) -> QuoteRow:
    ledger_id, match_id, observed_at, is_closing, outcome, price, book_key = row
    if not isinstance(is_closing, bool):
        raise ValueError("is_closing bool değil")
    return QuoteRow(
        int(ledger_id),
        str(match_id),
        _time(observed_at),
        is_closing,
        str(outcome),
        float(price),
        int(book_key),
    )


def _record(row: Sequence[Any]) -> RecordRow:
    (
        publication_id,
        match_id,
        market,
        outcome,
        published_at,
        published_price,
        publication_ledger_id,
        closing_fair_price,
        clv,
        publication_hash,
    ) = row
    return RecordRow(
        int(publication_id),
        str(match_id),
        str(market),
        str(outcome),
        _time(published_at),
        float(published_price),
        int(publication_ledger_id),
        float(closing_fair_price),
        float(clv),
        str(publication_hash),
    )
````

- [ ] **Step 5: Türetimi yaz**

`src/football_edge/site/derive.py` (tam içerik):

````python
"""Döküm → anlık görüntü gövdesi (Faz 6 İz B tasarımı §5.2, §5.4, §8.4).

Saf fonksiyonlar: DB yok, saat yok, rastgelelik yok. Aynı döküm her süreçte, her `PYTHONHASHSEED`le
aynı gövdeyi üretir (B12); ikinci türetim bunu ölçer. Hesap ham değerle yapılır, yuvarlama yalnız
çıktıda (`_shown`). Konsensüs `market.consensus`, vig temizleme `market.devig`, CLV ve güven
aralığı `market.metrics` — model neyse site o; burada ikinci bir tanım yazılmaz.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from football_edge.market.consensus import LIVE_H2H, Quote, round_consensus
from football_edge.market.devig import InvalidPrices, devig
from football_edge.market.metrics import bootstrap_mean, clv
from football_edge.site.contract import (
    RESERVED_LEAGUE_SLUGS,
    RESERVED_TEAM_SLUGS,
    SCHEMA_VERSION,
    iso_z,
)
from football_edge.site.inputs import ExportInputs, MatchRow, QuoteRow, RecordRow
from football_edge.site.slugs import match_slug, slugify

OUTCOMES = ("home", "draw", "away")
_MATCH_ID = re.compile(r"[0-9a-z]+")


class DeriveError(ValueError):
    """Döküm yayımlanabilir bir gövdeye dönüşmüyor (slug çakışması, kimlik biçimi, …)."""


@dataclass(frozen=True)
class RoundView:
    observed_at: datetime
    books: int
    probs: tuple[float, float, float]  # vig'i temizlenmiş, ham (0–1)


@dataclass(frozen=True)
class MatchView:
    row: MatchRow
    rounds: int
    sealed: bool
    opening: RoundView | None
    latest: RoundView | None
    closing: RoundView | None
    indexable: bool


def derive(inputs: ExportInputs) -> dict[str, Any]:
    """Anlık görüntü gövdesi (`generated_at`, `git_sha`, `content_sha256` HARİÇ)."""
    views = match_views(inputs)
    matches = [_match_json(view, inputs) for view in views]
    path_ids = [match["path_id"] for match in matches]
    if len(set(path_ids)) != len(path_ids):
        raise DeriveError("iki maç aynı path_id önekini taşıyor (§8.1)")
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger": {
            "rows": inputs.ledger.rows,
            "last_id": inputs.ledger.last_id,
            "head": inputs.ledger.head,
            "anchor": {
                "file": inputs.anchor.file,
                "rows": inputs.anchor.rows,
                "last_id": inputs.anchor.last_id,
                "head": inputs.anchor.head,
            },
        },
        "floor": iso_z(inputs.floor),
        "leagues": _leagues(inputs, views),
        "teams": _teams(inputs, views),
        "matches": matches,
        "record": _record(inputs.record),
        "value_badge": None,
        "analysis": None,
    }


def match_views(inputs: ExportInputs) -> tuple[MatchView, ...]:
    """Kesimde en az bir 1X2 satırı olan maçlar, (başlama, kimlik) sırasıyla."""
    by_match: dict[str, list[QuoteRow]] = {}
    for quote in inputs.quotes:
        by_match.setdefault(quote.match_id, []).append(quote)
    rows = sorted(
        (row for row in inputs.matches if row.id in by_match),
        key=lambda row: (row.commence_time, row.id),
    )
    return tuple(_view(row, by_match[row.id], inputs) for row in rows)


def _view(row: MatchRow, quotes: Sequence[QuoteRow], inputs: ExportInputs) -> MatchView:
    times = sorted({quote.observed_at for quote in quotes})
    closing_times = sorted({quote.observed_at for quote in quotes if quote.is_closing})
    rounds = {moment: _round(row, quotes, moment, inputs) for moment in times}
    shown = [view for view in rounds.values() if view is not None]
    return MatchView(
        row=row,
        rounds=len(times),
        sealed=bool(closing_times),
        opening=rounds[times[0]],
        latest=rounds[times[-1]],
        closing=rounds[closing_times[-1]] if closing_times else None,
        indexable=len(times) >= 2 and any(view.books >= inputs.config.min_books for view in shown),
    )


def _round(
    row: MatchRow, quotes: Sequence[QuoteRow], moment: datetime, inputs: ExportInputs
) -> RoundView | None:
    """Turun konsensüsü ve vig'i temizlenmiş olasılığı; tam kitap yoksa, temizlenemezse None."""
    found = round_consensus(
        [
            Quote(q.match_id, q.observed_at, str(q.book_key), LIVE_H2H, q.outcome, q.price)
            for q in quotes
            if q.observed_at == moment
        ],
        moment,
        row.home,
        row.away,
    )
    if found is None:
        return None
    try:
        home, draw, away = devig(found.means, inputs.config.devig_method)
    except InvalidPrices:
        return None
    return RoundView(moment, found.books, (home, draw, away))


def _shown(value: float, digits: int) -> float:
    """Görüntü hassasiyetine yuvarlar; `-0.0` `0.0` olur (sayfada "-0,0" görünmesin)."""
    return round(value, digits) + 0.0


def _percent(probs: tuple[float, float, float]) -> dict[str, float]:
    return {name: _shown(100.0 * value, 1) for name, value in zip(OUTCOMES, probs, strict=True)}


def _visible(view: RoundView | None, inputs: ExportInputs) -> RoundView | None:
    return view if view is not None and view.books >= inputs.config.min_books else None


def _round_json(view: RoundView | None, inputs: ExportInputs) -> dict[str, Any] | None:
    shown = _visible(view, inputs)
    if shown is None:
        return None
    return {
        "observed_at": iso_z(shown.observed_at),
        "books": shown.books,
        "p": _percent(shown.probs),
    }


def _move(view: MatchView, inputs: ExportInputs) -> tuple[float, float, float] | None:
    """Açılış → kapanış (yoksa son) hareketi, ham yüzde puanı; iki uç da görünür değilse None."""
    start = _visible(view.opening, inputs)
    end = _visible(view.closing if view.sealed else view.latest, inputs)
    if start is None or end is None:
        return None
    home, draw, away = (
        100.0 * (after - before) for before, after in zip(start.probs, end.probs, strict=True)
    )
    return home, draw, away


def _match_json(view: MatchView, inputs: ExportInputs) -> dict[str, Any]:
    row = view.row
    length = inputs.config.path_id_length
    if _MATCH_ID.fullmatch(row.id) is None or len(row.id) < length:
        raise DeriveError(f"maç kimliği beklenmeyen biçimde (lig {row.league_id})")
    move = _move(view, inputs)
    return {
        "id": row.id,
        "league_id": row.league_id,
        "path_id": row.id[:length],
        "slug": match_slug(row.home, row.away),
        "date": row.commence_time.astimezone(UTC).date().isoformat(),
        "commence_time": iso_z(row.commence_time),
        "home": row.home,
        "away": row.away,
        "sealed": view.sealed,
        "rounds": view.rounds,
        "h2h": {
            "opening": _round_json(view.opening, inputs),
            "latest": _round_json(view.latest, inputs),
            "closing": _round_json(view.closing, inputs),
        },
        "move": None
        if move is None
        else {name: _shown(value, 1) for name, value in zip(OUTCOMES, move, strict=True)},
        "indexable": view.indexable,
    }


def _leagues(inputs: ExportInputs, views: Sequence[MatchView]) -> list[dict[str, Any]]:
    seen: dict[str, str] = {}
    found: list[dict[str, Any]] = []
    for league in sorted(inputs.leagues, key=lambda league: league.id):
        slug = slugify(league.name)
        if slug in RESERVED_LEAGUE_SLUGS or slug in seen:
            raise DeriveError(
                f"lig {league.id}: slug ayrılmış ya da {seen.get(slug)} ile çakışıyor"
            )
        seen[slug] = league.id
        own = [view for view in views if view.row.league_id == league.id]
        found.append(
            {
                "id": league.id,
                "slug": slug,
                "name": league.name,
                "country": league.country,
                "matches": len(own),
                "move_distribution": _distribution(own, inputs),
            }
        )
    return found


def _distribution(views: Sequence[MatchView], inputs: ExportInputs) -> dict[str, float] | None:
    """Mühürlü, en az iki turlu maçlarda |açılış → kapanış| hareketinin en büyük bileşeni."""
    moves = [
        max(abs(value) for value in move)
        for view in views
        if view.sealed and view.rounds >= 2 and (move := _move(view, inputs)) is not None
    ]
    if len(moves) < inputs.config.move_min_matches:
        return None
    p10, p50, p90 = (float(value) for value in np.percentile(np.asarray(moves), [10, 50, 90]))
    return {"p10": _shown(p10, 1), "p50": _shown(p50, 1), "p90": _shown(p90, 1)}


def _teams(inputs: ExportInputs, views: Sequence[MatchView]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = {}
    for view in views:
        for name in (view.row.home, view.row.away):
            key = (view.row.league_id, name)
            counts[key] = counts.get(key, 0) + 1
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for (league_id, name), count in counts.items():
        key = (league_id, slugify(name))
        if key[1] in RESERVED_TEAM_SLUGS or key in entries:
            raise DeriveError(f"lig {league_id}: bir takım slug'ı ayrılmış ya da çakışıyor")
        entries[key] = {
            "league_id": league_id,
            "slug": key[1],
            "name": name,
            "matches": count,
            "indexable": count >= inputs.config.min_team_matches,
        }
    return [entries[key] for key in sorted(entries)]


def _record(rows: Sequence[RecordRow]) -> dict[str, Any]:
    entries = [
        {
            "publication_id": row.publication_id,
            "match_id": row.match_id,
            "market": row.market,
            "outcome": row.outcome,
            "published_at": iso_z(row.published_at),
            "published_price": _shown(row.published_price, 2),
            "publication_ledger_id": row.publication_ledger_id,
            "closing_fair_price": _shown(row.closing_fair_price, 2),
            "clv": _shown(100.0 * row.clv, 2),
            "publication_hash": row.publication_hash,
        }
        for row in sorted(rows, key=lambda row: row.publication_id)
    ]
    summary = None
    if rows:
        interval = bootstrap_mean([row.clv for row in rows])
        summary = {
            "mean_clv": _shown(100.0 * interval.estimate, 2),
            "ci_low": _shown(100.0 * interval.low, 2),
            "ci_high": _shown(100.0 * interval.high, 2),
            "n": len(rows),
        }
    return {"published": len(rows), "entries": entries, "summary": summary}


def record_mismatches(inputs: ExportInputs) -> list[str]:
    """§6.4/3d: her sicil girdisinin CLV'si defterin kapanış konsensüsünden yeniden hesaplanır."""
    views = {view.row.id: view for view in match_views(inputs)}
    problems: list[str] = []
    for row in inputs.record:
        view = views.get(row.match_id)
        closing = None if view is None else view.closing
        if row.market != LIVE_H2H or row.outcome not in OUTCOMES:
            problems.append(f"yayın {row.publication_id}: market/sonuç sözleşme dışı")
        elif row.publication_ledger_id > inputs.ledger.last_id:
            problems.append(f"yayın {row.publication_id}: kesimden sonraki bir satıra bağlı")
        elif closing is None:
            problems.append(f"yayın {row.publication_id}: maçın kesimde kapanış konsensüsü yok")
        else:
            fair = closing.probs[OUTCOMES.index(row.outcome)]
            if not math.isclose(row.clv, clv(row.published_price, fair), abs_tol=1e-9):
                problems.append(f"yayın {row.publication_id}: CLV defterden yeniden hesaplanamıyor")
            if not math.isclose(row.closing_fair_price, 1.0 / fair, rel_tol=1e-9):
                problems.append(
                    f"yayın {row.publication_id}: kapanış adil oranı defterle uyuşmuyor"
                )
    return problems
````

- [ ] **Step 6: Yeşili gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_derive.py tests/test_site_import_rule.py tests/test_site_verify.py`
Expected: `64 passed` (22 + 4 + 38). İmport bekçisi artık `market.consensus`, `market.devig`, `market.metrics` ve
`history.types`i kapanışta görür ve YEŞİL kalır.

- [ ] **Step 7: Mutasyonla kırmızı kanıtı**

| Dosya | Eski → yeni | Kırmızı |
|---|---|---|
| `src/football_edge/site/derive.py` | `    return round(value, digits) + 0.0` → `    return round(value, digits)` | `test_a_tiny_negative_move_is_shown_as_zero_not_minus_zero` |
| `src/football_edge/site/derive.py` | `if len(moves) < inputs.config.move_min_matches:` → `if len(moves) <= inputs.config.move_min_matches:` | `test_a_league_distribution_needs_five_sealed_moving_matches` |
| `src/football_edge/site/derive.py` | `view.books >= inputs.config.min_books else None` → `view.books > inputs.config.min_books else None` | 5 failed (üç kitaplı turlar görünmez olur) |
| `src/football_edge/site/derive.py` | `    return [entries[key] for key in sorted(entries)]` → `    return [entries[key] for key in entries]` | spec §5.1/5 mutasyon (b): 3 failed (`test_a_derived_snapshot_passes_verify_and_orders_teams_by_slug_not_name`, `test_teams_count…`, Review Focus 2'nin `verify` iddiası) — kırmızı `verify-snapshot`in SIRA kuralından gelir; Task 6'nın belirlenimcilik testi bu mutasyonda YEŞİL kalır (iki türetim aynı sırayı üretir) |
| `src/football_edge/site/derive.py` | `        raise DeriveError("iki maç aynı path_id önekini taşıyor (§8.1)")` → `        pass` | `test_two_matches_sharing_a_path_prefix_stop_the_derivation` |

- [ ] **Step 8: Lint ve tip** — `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`.

- [ ] **Step 9: Tam kapı** — `10 PASS` + `SKIP: zincir` + `KAPI YEŞİL`.

- [ ] **Step 10: Commit**

```bash
git add src/football_edge/site/inputs.py src/football_edge/site/derive.py tests/site_builders.py tests/test_site_derive.py
git commit -m "feat: site türetimi — kanonik girdi dökümü, konsensüs/vig/CLV model koduyla, elle hesaplanmış beklenenler (Faz 6 B-1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Dışa aktarıcı — tek işlem, tam zincir, ikinci türetim, iki dosya; log redaksiyonu

**Kademe:** K1 · **Spec:** B12, §5.1 (1–6), §4.2 bekçi 3, H1d, §6.4/3a–d, §12.4/13–14, RUNBOOK §3.8, DEFERRED 10o ·
**Bağımlılık:** Task 2, 4, 5 · **Worktree:** `wt-b1-t6`

`run_export` sırası: `--out` boş değilse kırmızı → işlem `REPEATABLE READ, READ ONLY` (bağlantı ayarı + işlemin kendi
ölçümü) → HER çıpa `_first_anchor_break(…, relation=LEDGER_AUDIT_VIEW)` ve GENESIS'ten `verify_chain`; üç indirgeme
satırı ("çıpa yok", "git geçmişi okunamadı — ATLANDI", "en yeni çıpa okunamadı") dışa aktarımda KIRMIZIDIR →
`site.public_floor()` = Python tabanı, `site.ledger_head` (çıpa satır diyor ama görünüm 0 → kırmızı) → döküm →
yerel türetim + alt süreçte ikinci türetim (stdin, başka tohum, DB adresi ortamdan çıkarılmış, çıktısı yakalanıp
loga AKTARILMAZ) → sicilin defterden yeniden hesabı → `verify-snapshot` → ancak şimdi iki dosya. Log yalnız sayı ve
hash taşır. `SITE_DATABASE_URL` kök handler'da redakte edilir.

**Files:**
- Create: `src/football_edge/site/export.py`, `tests/fake_site_db.py`
- Modify: `src/football_edge/site/__main__.py` (tam hâli: `export`, `verify-snapshot`, `derive-stdin`),
  `src/football_edge/collect.py` (`_log_secrets`)
- Test: `tests/test_site_export.py`, `tests/test_site_determinism.py`, `tests/test_site_logging.py`

**Interfaces:**
- Consumes: `anchors.{ANCHOR_DIR, Anchor, _scan_anchors, archived_anchors, expected_anchor_names, missing_anchors}`,
  `collect.{LEDGER_AUDIT_VIEW, _first_anchor_break, _ledger_rows, configure_logging}`, `ledger.verify_chain`,
  `db.connect(dsn) -> psycopg.Connection` (oturum `timezone=UTC`), Task 5 `derive`, `record_mismatches`, `dump_text`,
  `load_inputs`, Task 4 `snapshot_errors`.
- Produces (Task 7, 8, 9 ve B-2):
  ```python
  # football_edge.site.export
  SNAPSHOT_FILE = "snapshot.json"; HASH_FILE = "snapshot.sha256"
  class ExportRefused(RuntimeError): code: int
  @dataclass(frozen=True) class ExportSummary: matches: int; leagues: int; teams: int; rows: int; last_id: int; content_sha256: str; file_sha256: str
  def devig_method(path: Path) -> str
  def derive_in_subprocess(dump: str, *, hash_seed: str) -> str
  def other_hash_seed(environ: Mapping[str, str]) -> str
  def run_export(conn, out_dir: Path, *, generated_at: datetime, git_sha: str, method: str,
                 schema: Mapping[str, Any], anchor_dir: Path = ANCHOR_DIR,
                 derive_elsewhere: Callable[[str], str] | None = None) -> ExportSummary
  ```
  Dosya biçimi: `snapshot.json` = `ledger._canonical(anlık görüntü) + "\n"` (UTF-8); `snapshot.sha256` =
  `"<64 hex>  snapshot.json\n"` (`sha256sum` biçimi). CLI: `uv run python -m football_edge.site export --out <dizin>`
  (`SITE_DATABASE_URL` yoksa `SITE_DATABASE_URL yok — yayın yapılmadı`, exit 20; reddedilirse
  `DIŞA AKTARIM REDDEDİLDİ: <neden>` ve 21–24).

- [ ] **Step 1: Görünüm taklidini yaz**

`tests/fake_site_db.py` (tam içerik):

````python
"""`site export`in okuduğu görünümlerin bellekteki taklidi (0014'ün süzgeçleriyle aynı kurallar).

Taklit görünüm MANTIĞINI taşır — pasif lig düşer, taban süzer, `book_key` tur içinde kitap sırası —
çünkü dışa aktarıcının birim testleri gerçek Postgres'siz koşar. Gerçek SQL'e karşı aynı yol
`tests/test_site_e2e_db.py`de kapta koşar.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from football_edge.site.contract import PUBLIC_FLOOR, RECORD_COLUMNS
from tests.fake_db import LEDGER_COLUMNS


@dataclass
class FakeSiteDb:
    leagues: Sequence[tuple[str, str, str, bool]]  # id, name, country, active
    matches: Sequence[tuple[str, str, datetime, str, str]]  # id, league_id, başlama, ev, dep.
    ledger: Sequence[dict[str, Any]]  # `tests.site_builders.ledger` satırları
    record: Sequence[tuple[Any, ...]] = ()
    isolation: tuple[str, str] = ("repeatable read", "on")
    floor: datetime = PUBLIC_FLOOR
    head_rows: int | None = None  # site.ledger_head.rows'u ezmek için (sahiplik arızası)
    queries: list[str] = field(default_factory=list)
    isolation_level: Any = None
    read_only: bool | None = None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def site_matches(self) -> list[tuple[str, str, datetime, str, str]]:
        active = {league[0] for league in self.leagues if league[3]}
        return sorted(
            (row for row in self.matches if row[1] in active and row[2] >= PUBLIC_FLOOR),
            key=lambda row: row[0],
        )

    def h2h_quotes(self) -> list[tuple[Any, ...]]:
        shown = {row[0] for row in self.site_matches()}
        found = []
        for row in self.ledger:
            if row["market"] != "h2h" or row["match_id"] not in shown:
                continue
            books = sorted(
                {
                    other["bookmaker"]
                    for other in self.ledger
                    if other["match_id"] == row["match_id"]
                    and other["observed_at"] == row["observed_at"]
                    and other["market"] == "h2h"
                }
            )
            found.append(
                (
                    row["id"],
                    row["match_id"],
                    row["observed_at"],
                    row["is_closing"],
                    row["outcome"],
                    row["price"],
                    books.index(row["bookmaker"]) + 1,
                )
            )
        return found


class _Cursor:
    def __init__(self, db: FakeSiteDb) -> None:
        self._db = db
        self.description: Any = None
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        self._db.queries.append(text)
        db, self.description = self._db, None
        rows = db.ledger
        if text.startswith("SELECT current_setting('transaction_isolation')"):
            self._result = [db.isolation]
        elif text == "SELECT count(*) FROM site_audit.ledger_rows":
            self._result = [(len(rows),)]
        elif text.startswith("SELECT match_id") and "FROM site_audit.ledger_rows" in text:
            self.description = tuple((name,) for name in LEDGER_COLUMNS)
            wanted = [row for row in rows if "WHERE id = %s" not in text or row["id"] == params[0]]
            self._result = [tuple(row[name] for name in LEDGER_COLUMNS) for row in wanted]
        elif text == "SELECT site.public_floor()":
            self._result = [(db.floor,)]
        elif text == "SELECT rows, last_id, head FROM site.ledger_head":
            count = len(rows) if db.head_rows is None else db.head_rows
            last = max((row["id"] for row in rows), default=0)
            head = rows[-1]["row_hash"] if rows else "0" * 64
            self._result = [(count, last, head)]
        elif text.startswith("SELECT id, name, country FROM site.leagues"):
            self._result = sorted((lg[0], lg[1], lg[2]) for lg in db.leagues if lg[3])
        elif text.startswith("SELECT id, league_id, commence_time"):
            self._result = list(db.site_matches())
        elif "FROM site_input.h2h_quotes" in text:
            self._result = [row for row in db.h2h_quotes() if row[0] <= params[0]]
        elif text.startswith(f"SELECT {RECORD_COLUMNS[0][0]}"):
            self._result = list(db.record)
        else:
            raise AssertionError(f"taklit bu sorguyu tanımıyor: {text}")

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)
````

- [ ] **Step 2: Dışa aktarım testini yaz (Review Focus 1, 3, 4 dâhil)**

`tests/test_site_export.py` (tam içerik):

````python
"""`site export` (§5.1) sahte görünümlere karşı: tek işlem, tam zincir, iki türetim, iki dosya.

Gerçek SQL'e karşı aynı yol kapta `tests/test_site_e2e_db.py`de koşar. Burada her kırmızı dalın
ADIYLA ve DOSYA YAZMADAN durduğu sınanır.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest

from football_edge.backtest.model_config import MODEL_CONFIG_PATH, load_model_config
from football_edge.site.contract import (
    DEVIG_CONFIG_PATH,
    EXIT_SITE_CHAIN,
    EXIT_SITE_CONFIG,
    EXIT_SITE_CUT,
    EXIT_SITE_INVALID,
    EXIT_SITE_NONDETERMINISTIC,
)
from football_edge.site.export import (
    ExportRefused,
    devig_method,
    other_hash_seed,
    run_export,
)
from tests.fake_site_db import FakeSiteDb
from tests.site_builders import EVEN, SYMMETRIC, Round, anchored_repo, at, ledger, payloads

REPO = Path(__file__).resolve().parent.parent
SCHEMA: dict[str, Any] = json.loads(
    (REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8")
)
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
M1, M2 = "01" + "ab" * 15, "02" + "ab" * 15
ROUNDS = [
    Round(M1, "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3),
    Round(M2, "2026-09-20T11:00:00Z", "Gamma United", "Alfa Spor", [EVEN] * 3),
    Round(M1, "2026-09-22T13:00:00Z", "Alfa Spor", "Beta FK", SYMMETRIC, is_closing=True),
]
ROWS = ledger(payloads(ROUNDS))


@pytest.fixture(autouse=True)
def _child_imports_this_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    """İkinci türetim `python -m football_edge.site` alt sürecidir: kurulu paket değil bu ağaç."""
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))


def _db(**changes: Any) -> FakeSiteDb:
    db = FakeSiteDb(
        leagues=[("tst.1", "Deneme Ligi", "Testland", True)],
        matches=[
            (M1, "tst.1", at("2026-09-22T14:00:00Z"), "Alfa Spor", "Beta FK"),
            (M2, "tst.1", at("2026-09-23T15:00:00Z"), "Gamma United", "Alfa Spor"),
        ],
        ledger=ROWS,
    )
    return replace(db, **changes)


def _anchors(tmp_path: Path, index: int = 9) -> Path:
    """Çıpa kesimin ortasında (id=10): hem çıpa öncesi hem sonrası satır var."""
    row = ROWS[index]
    return anchored_repo(
        tmp_path / "repo", rows=row["id"], last_id=row["id"], head=row["row_hash"], day="2026-09-21"
    )


def _export(db: FakeSiteDb, tmp_path: Path, **overrides: Any) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = tmp_path / "out"
    options: dict[str, Any] = {
        "generated_at": NOW,
        "git_sha": "1" * 40,
        "method": "power",
        "schema": SCHEMA,
        "anchor_dir": overrides.pop("anchor_dir", None) or _anchors(tmp_path),
        "derive_elsewhere": overrides.pop("derive_elsewhere", None),
    }
    run_export(db, out, **{**options, **overrides})  # type: ignore[arg-type]
    return out


def _refused(db: FakeSiteDb, tmp_path: Path, code: int, needle: str, **overrides: Any) -> None:
    with pytest.raises(ExportRefused, match=needle) as refused:
        _export(db, tmp_path, **overrides)
    assert refused.value.code == code
    out = tmp_path / "out"
    assert not out.exists() or list(out.iterdir()) == [], "kırmızı dışa aktarım dosya yazdı"


def test_a_clean_export_writes_exactly_the_two_files(tmp_path: Path) -> None:
    out = _export(_db(), tmp_path)

    assert sorted(path.name for path in out.iterdir()) == ["snapshot.json", "snapshot.sha256"]
    snapshot = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["ledger"]["rows"] == len(ROWS) and snapshot["ledger"]["last_id"] == len(ROWS)
    assert snapshot["ledger"]["head"] == ROWS[-1]["row_hash"]
    assert snapshot["ledger"]["anchor"]["file"] == "head-2026-09-21.txt"
    assert [match["id"] for match in snapshot["matches"]] == [M1, M2]


def test_the_export_runs_in_one_repeatable_read_read_only_transaction(tmp_path: Path) -> None:
    db = _db()
    _export(db, tmp_path)

    assert db.isolation_level == psycopg.IsolationLevel.REPEATABLE_READ and db.read_only is True


def test_a_transaction_that_is_not_repeatable_read_is_red(tmp_path: Path) -> None:
    """Oturum ayarı ezilmişse (ör. pooler) kesim tutarlılığı vaadi yoktur: işlem kendini ölçer."""
    _refused(_db(isolation=("read committed", "on")), tmp_path, EXIT_SITE_CUT, "REPEATABLE READ")


def test_the_whole_ledger_is_rehashed_through_the_audit_view(tmp_path: Path) -> None:
    db = _db()
    _export(db, tmp_path)
    reads = [q for q in db.queries if q.startswith("SELECT match_id")]

    assert any(q.endswith("FROM site_audit.ledger_rows ORDER BY id") for q in reads), reads
    assert not any("odds_snapshots" in q for q in db.queries), "site tabloya dokunmamalı"


def test_a_non_empty_out_dir_is_refused(tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "eski.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ExportRefused, match="boş değil") as refused:
        _export(_db(), tmp_path)
    assert refused.value.code == EXIT_SITE_CONFIG


@pytest.mark.parametrize("where", ["before", "after"])
def test_a_tampered_price_before_or_after_the_anchor_is_red(tmp_path: Path, where: str) -> None:
    """N1: çıpa öncesi (id 4) ve sonrası (id 20) — saklanan hash'ler eski kalır."""
    index = 3 if where == "before" else 19
    forged = [dict(row) for row in ROWS]
    forged[index]["price"] = forged[index]["price"] + 1

    _refused(_db(ledger=tuple(forged)), tmp_path, EXIT_SITE_CHAIN, "zincir KIRIK")


def test_an_anchor_that_the_ledger_no_longer_produces_is_red(tmp_path: Path) -> None:
    anchors = anchored_repo(tmp_path / "repo", rows=10, last_id=10, head="f" * 64, day="2026-09-21")

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "ÇIPA UYUŞMAZLIĞI", anchor_dir=anchors)


def test_no_anchor_is_red_not_skipped(tmp_path: Path) -> None:
    empty = tmp_path / "ledger"
    empty.mkdir()

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "çıpasız yayın yok", anchor_dir=empty)


def test_an_unreadable_git_history_is_red_not_skipped(tmp_path: Path) -> None:
    loose = tmp_path / "loose" / "ledger"
    loose.mkdir(parents=True)
    row = ROWS[9]
    (loose / "head-2026-09-21.txt").write_text(
        f"x\nrows=10\nlast_id=10\nhead={row['row_hash']}\n", encoding="utf-8"
    )

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "ATLANDI", anchor_dir=loose)


def test_an_unreadable_newest_anchor_is_red_not_downgraded(tmp_path: Path) -> None:
    anchors = _anchors(tmp_path)
    (anchors / "head-2026-09-22.txt").write_text("bozuk\n", encoding="utf-8")

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "indirgeme yok", anchor_dir=anchors)


def test_a_deleted_anchor_is_red(tmp_path: Path) -> None:
    anchors = _anchors(tmp_path)
    extra = anchors / "head-2026-09-20.txt"
    extra.write_text(
        (anchors / "head-2026-09-21.txt").read_text(encoding="utf-8"), encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(anchors), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(anchors), "-c", "user.email=t@example.com", "-c", "user.name=t"]
        + ["commit", "-q", "-m", "ikinci çıpa"],
        check=True,
    )
    extra.unlink()

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "ÇIPA EKSİK", anchor_dir=anchors)


def test_a_view_that_returns_no_rows_under_the_anchor_is_red(tmp_path: Path) -> None:
    """§4.2 bekçi 3: yanlış görünüm sahibi RLS'li tabloyu 0 satır okur — DB içinden görünmez."""
    _refused(_db(head_rows=0), tmp_path, EXIT_SITE_CUT, "görünüm sahipliği")


def test_an_empty_match_set_under_a_nonempty_anchor_is_red(tmp_path: Path) -> None:
    _refused(_db(matches=[]), tmp_path, EXIT_SITE_CUT, "maç kümesi boş")


@pytest.mark.leakage
def test_a_floor_drift_between_db_and_python_is_red(tmp_path: Path) -> None:
    _refused(_db(floor=at("2026-07-01T00:00:00Z")), tmp_path, EXIT_SITE_CUT, "tabanından farklı")


def test_a_different_second_derivation_is_red(tmp_path: Path) -> None:
    _refused(
        _db(),
        tmp_path,
        EXIT_SITE_NONDETERMINISTIC,
        "farklı content_sha256",
        derive_elsewhere=lambda dump: "0" * 64,
    )


def test_a_snapshot_that_fails_verify_is_not_written(tmp_path: Path) -> None:
    """H2: bir takım adı bağlantı taşıyorsa anlık görüntü yazılmaz."""
    matches = [(M1, "tst.1", at("2026-09-22T14:00:00Z"), "http://x.invalid", "Beta FK")]
    rounds = [Round(M1, "2026-09-20T10:00:00Z", "http://x.invalid", "Beta FK", [EVEN] * 3)]
    rows = ledger(payloads(rounds))
    anchors = anchored_repo(
        tmp_path / "repo", rows=3, last_id=3, head=rows[2]["row_hash"], day="2026-09-21"
    )

    _refused(
        _db(matches=matches, ledger=rows),
        tmp_path,
        EXIT_SITE_INVALID,
        "verify-snapshot",
        anchor_dir=anchors,
    )


def test_the_devig_method_is_the_model_config_method() -> None:
    """Site `backtest`i import edemez (H1f); aynı dosyadan okunan yöntem modelinkine eşit olmalı."""
    assert DEVIG_CONFIG_PATH == MODEL_CONFIG_PATH
    assert (
        devig_method(REPO / DEVIG_CONFIG_PATH) == load_model_config(REPO / MODEL_CONFIG_PATH).method
    )


def test_the_other_seed_differs_from_this_process_seed() -> None:
    assert other_hash_seed({"PYTHONHASHSEED": "1"}) == "2"
    assert other_hash_seed({"PYTHONHASHSEED": "7"}) == "1"
    assert other_hash_seed({}) == "1"


def _publication(clv: float) -> tuple[Any, ...]:
    """M1'in kapanışı simetrik (1/3): 3.12 × 1/3 − 1 = 0.04."""
    return (
        1,
        M1,
        "h2h",
        "home",
        at("2026-09-21T09:00:00Z"),
        Decimal("3.12"),
        3,
        Decimal("3"),
        clv,
        "1" * 64,
    )


def test_a_consistent_record_is_exported_with_its_summary(tmp_path: Path) -> None:
    out = _export(_db(record=[_publication(3.12 / 3 - 1)]), tmp_path)
    record = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))["record"]

    assert record["published"] == 1 and record["entries"][0]["clv"] == 4.0
    assert record["summary"] == {"mean_clv": 4.0, "ci_low": 4.0, "ci_high": 4.0, "n": 1}


def test_a_record_entry_the_ledger_cannot_reproduce_is_red(tmp_path: Path) -> None:
    """§6.4/3d: CLV defterin kapanış konsensüsünden yeniden hesaplanır; uyuşmazsa yayın yok."""
    _refused(_db(record=[_publication(0.5)]), tmp_path, EXIT_SITE_CUT, "CLV defterden")


# ── Review Focus ──────────────────────────────────────────────────────────────────────────────


def test_review_focus_a_non_utc_session_exports_the_same_content(tmp_path: Path) -> None:
    """Pooler `-c timezone=UTC`yi yok sayarsa psycopg +03:00'lı zaman döner; içerik değişmemeli."""
    istanbul = timezone(timedelta(hours=3))
    shifted = tuple({**row, "observed_at": row["observed_at"].astimezone(istanbul)} for row in ROWS)
    base = _db()
    local = _db(
        ledger=shifted,
        matches=[(m[0], m[1], m[2].astimezone(istanbul), m[3], m[4]) for m in base.matches],
    )
    utc_out = _export(base, tmp_path / "utc")
    local_out = _export(local, tmp_path / "ist")

    def content(out: Path) -> str:
        return str(
            json.loads((out / "snapshot.json").read_text(encoding="utf-8"))["content_sha256"]
        )

    assert content(local_out) == content(utc_out)


def test_review_focus_an_anchor_beyond_the_cut_is_red(tmp_path: Path) -> None:
    """Eski veritabanına yeni checkout: çıpa kesimde olmayan satırı gösterir → adıyla kırmızı."""
    anchors = anchored_repo(
        tmp_path / "repo", rows=999, last_id=999, head="e" * 64, day="2026-09-21"
    )

    _refused(_db(), tmp_path, EXIT_SITE_CHAIN, "id=999", anchor_dir=anchors)
````

- [ ] **Step 3: Belirlenimcilik testini yaz (spec §5.1/5 mutasyon (a)'nın zemini)**

`tests/test_site_determinism.py` (tam içerik):

````python
"""B12 §5.1/5: ikinci türetim ayrı süreçte, başka `PYTHONHASHSEED`le aynı dökümden AYNI hash verir.

Kanıt olasılıklı değildir (§18.4 n3): fixture ≥ 32 farklı takım adı taşır ve iki sabit tohumla
küme sırasının GERÇEKTEN farklı olduğu önce sınanır. Mutasyon kanıtı plandadır: `_teams` sıralı
anahtar yerine bir `str` kümesi üzerinde dönerse `test_two_seeds_derive_the_same_content_hash`
kırmızı olur.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from football_edge.site import export
from football_edge.site.contract import EXIT_SITE_NONDETERMINISTIC, content_sha256
from football_edge.site.derive import derive
from football_edge.site.export import ExportRefused, derive_in_subprocess
from football_edge.site.inputs import load_inputs
from tests.site_builders import EVEN, Round, export_dump

REPO = Path(__file__).resolve().parent.parent
TEAMS = [f"Takım {chr(0x41 + index % 26)}{index:02d}" for index in range(34)]
LEAGUE = ("tst.1", "Deneme Ligi", "Testland")


def _dump() -> str:
    matches, rounds = [], []
    for number in range(len(TEAMS) // 2):
        match_id = f"{number:02d}" + "cd" * 15
        home, away = TEAMS[2 * number], TEAMS[2 * number + 1]
        matches.append((match_id, "tst.1", f"2026-09-2{number % 10}T18:00:00Z", home, away))
        rounds.append(Round(match_id, "2026-09-19T08:00:00Z", home, away, [EVEN] * 3))
    return export_dump(leagues=[LEAGUE], matches=matches, rounds=rounds)


@pytest.fixture(autouse=True)
def _child_imports_this_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))


def _set_order(seed: str) -> str:
    """`_teams`in anahtar yapısı: (lig, slug) demetlerinin KÜMESİ bu tohumla hangi sırada döner."""
    probe = (
        "import sys\n"
        "from football_edge.site.slugs import slugify\n"
        "print('|'.join(repr(key) for key in {('tst.1', slugify(n)) for n in sys.argv[1:]}))"
    )
    env = {**os.environ, "PYTHONHASHSEED": seed}
    result = subprocess.run(
        [sys.executable, "-c", probe, *TEAMS], capture_output=True, text=True, env=env, check=True
    )
    return result.stdout


def test_the_two_fixed_seeds_really_order_the_fixture_team_set_differently() -> None:
    """Önkoşul: bu olmadan aşağıdaki eşitlik bir küme hatasını yakalayamazdı."""
    assert len(set(TEAMS)) >= 32
    assert _set_order("1") != _set_order("2")


def test_two_seeds_derive_the_same_content_hash() -> None:
    dump = _dump()
    local = content_sha256(derive(load_inputs(dump)))

    assert derive_in_subprocess(dump, hash_seed="1") == local
    assert derive_in_subprocess(dump, hash_seed="2") == local


def test_a_crashing_child_is_named_and_its_output_is_not_relayed() -> None:
    """n4: çocuğun traceback'i bir fiyat taşıyabilir; ana süreç yalnız adlandırılmış hata verir."""
    poisoned = _dump().replace('"4.0"', '"4.47x"', 1)

    with pytest.raises(ExportRefused) as refused:
        derive_in_subprocess(poisoned, hash_seed="1")

    assert refused.value.code == EXIT_SITE_NONDETERMINISTIC
    assert str(refused.value) == "ikinci türetim alt süreci düştü, çıkış kodu 1"


def test_the_child_gets_no_database_address_and_the_other_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Çocuğun ortamında DB adresi yoktur: ikinci türetim yalnız dökümden çalışır."""
    monkeypatch.setenv("SITE_DATABASE" + "_URL", "postgresql://x@127.0.0.1:1/y")
    monkeypatch.setenv("DATABASE" + "_URL", "postgresql://x@127.0.0.1:1/y")
    seen: list[dict[str, str]] = []

    def spy(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs["env"])
        return subprocess.CompletedProcess(args, 0, stdout="0" * 64 + "\n", stderr="")

    monkeypatch.setattr(export.subprocess, "run", spy)

    assert export.derive_in_subprocess("{}", hash_seed="1") == "0" * 64
    assert "SITE_DATABASE" + "_URL" not in seen[0] and "DATABASE" + "_URL" not in seen[0]
    assert seen[0]["PYTHONHASHSEED"] == "1"
````

- [ ] **Step 4: Log testini yaz**

`tests/test_site_logging.py` (tam içerik):

````python
"""Site komutlarının logu (§5.1, RUNBOOK §3.8): public log yalnız sayı ve hash taşır.

Depo ve Actions logları herkese açık. `SITE_DATABASE_URL` kök handler'da redakte edilir; girdi
dökümü (kitap bazında fiyat) ne loga ne diske gider; çöken ikinci türetimin çıktısı aktarılmaz.
"""

from __future__ import annotations

import io
import logging
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from football_edge import collect
from football_edge.site import __main__ as site_main
from football_edge.site.contract import EXIT_SITE_CONFIG, EXIT_SITE_NONDETERMINISTIC
from football_edge.site.export import ExportRefused, derive_in_subprocess
from tests.fake_site_db import FakeSiteDb
from tests.site_builders import EVEN, Round, anchored_repo, at, export_dump, ledger, payloads

REPO = Path(__file__).resolve().parent.parent
DSN_VAR = "SITE_DATABASE" + "_URL"
PASSWORD = "sahte-site-parolasi"
DSN = f"postgresql://site_reader.sahteref:{PASSWORD}@db.sahte.invalid:5432/postgres"
M1 = "01" + "ab" * 15


@contextmanager
def _captured_root() -> Iterator[io.StringIO]:
    """Kökü pytest'in handler'larından arındırıp `configure_logging`in kurduğunu yakalar."""
    root = logging.getLogger()
    saved, hook = root.handlers[:], sys.excepthook
    for handler in saved:
        root.removeHandler(handler)
    stream = io.StringIO()
    try:
        collect.configure_logging(stream)
        yield stream
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        for handler in saved:
            root.addHandler(handler)
        sys.excepthook = hook


def test_the_site_dsn_and_its_password_are_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DSN_VAR, DSN)
    with _captured_root() as stream:
        logging.getLogger("football_edge.site").warning("bağlantı: %s / %s", DSN, PASSWORD)

    assert PASSWORD not in stream.getvalue() and "db.sahte.invalid" not in stream.getvalue()


def test_export_without_the_secret_names_it_and_publishes_nothing(tmp_path: Path) -> None:
    env = {"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, "-m", "football_edge.site", "export", "--out", str(tmp_path / "out")],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
        check=False,
    )

    assert result.returncode == EXIT_SITE_CONFIG
    assert "SITE_DATABASE_URL yok — yayın yapılmadı" in result.stdout
    assert not (tmp_path / "out").exists()


def test_both_public_commands_configure_redacted_logging(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(site_main, "configure_logging", lambda: calls.append("log"))
    monkeypatch.delenv(DSN_VAR, raising=False)

    site_main.main(["export", "--out", str(tmp_path / "out")])
    site_main.main(["verify-snapshot", str(REPO / "web/fixtures/snapshot.fixture.json")])

    assert calls == ["log", "log"]


def test_a_successful_export_logs_counts_and_hashes_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rounds = [Round(M1, "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3)]
    rows = ledger(payloads(rounds))
    db = FakeSiteDb(
        leagues=[("tst.1", "Deneme Ligi", "Testland", True)],
        matches=[(M1, "tst.1", at("2026-09-22T14:00:00Z"), "Alfa Spor", "Beta FK")],
        ledger=rows,
    )
    anchors = anchored_repo(
        tmp_path / "repo", rows=3, last_id=3, head=rows[2]["row_hash"], day="2026-09-21"
    )
    real_export = site_main.run_export

    def run(conn: Any, out: Path, **options: Any) -> Any:
        return real_export(db, out, **{**options, "anchor_dir": anchors})  # type: ignore[arg-type]

    monkeypatch.setenv(DSN_VAR, DSN)
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))
    monkeypatch.setenv("GITHUB_SHA", "1" * 40)
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(site_main, "connect", lambda dsn: _Closing())
    monkeypatch.setattr(site_main, "run_export", run)
    monkeypatch.setattr(site_main, "configure_logging", lambda: None)
    with _captured_root() as stream:
        code = site_main.main(["export", "--out", str(tmp_path / "out")])

    text = stream.getvalue()
    assert code == 0, text
    assert "maç=1 lig=1 takım=2 satır=9 last_id=9" in text
    assert re.search(r"\b\d+\.\d+\b", text.split(" INFO ", 1)[1]) is None, "fiyat benzeri sayı"
    assert "Alfa Spor" not in text and PASSWORD not in text
    written = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    assert written == [
        "out/snapshot.json",
        "out/snapshot.sha256",
        "repo/ledger/head-2026-09-21.txt",
    ]


class _Closing:
    def __enter__(self) -> _Closing:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_a_crashing_second_derivation_relays_no_price(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """n4: çocuğa fiyat içeren bir istisna attırılır; loga giden çıktıda fiyat yok."""
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))
    rounds = [Round(M1, "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3)]
    dump = export_dump(
        leagues=[("tst.1", "Deneme Ligi", "Testland")],
        matches=[(M1, "tst.1", "2026-09-22T14:00:00Z", "Alfa Spor", "Beta FK")],
        rounds=rounds,
    ).replace('"4.0"', '"4.47x"', 1)

    with _captured_root() as stream:
        with pytest.raises(ExportRefused) as refused:
            derive_in_subprocess(dump, hash_seed="1")
        logging.getLogger("football_edge.site").error("%s", refused.value)

    seen = stream.getvalue() + "".join(capsys.readouterr())
    assert refused.value.code == EXIT_SITE_NONDETERMINISTIC
    assert "4.47" not in seen and "Traceback" not in seen
````

- [ ] **Step 5: Kırmızıyı gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_export.py tests/test_site_determinism.py tests/test_site_logging.py`
Expected: toplama hatası `No module named 'football_edge.site.export'`.

- [ ] **Step 6: Dışa aktarıcıyı yaz**

`src/football_edge/site/export.py` (tam içerik):

````python
"""`site export`: tek salt okuma işleminde defteri doğrula, türet, iki kez türet, denetle, yaz.

Faz 6 İz B tasarımı §5.1 (B12). Adımların hepsi `REPEATABLE READ, READ ONLY` TEK işlemdedir:
`matches.commence_time` her snapshot turunda UPDATE edilir, defter kesimi onu dondurmaz — işlem
dondurur. Herhangi bir kontrol kırmızıysa HİÇBİR dosya yazılmaz ve `ExportRefused` adıyla yükselir.
Log yalnız sayı ve hash taşır; girdi dökümü (kitap bazında fiyat) ne diske ne loga gider.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
import yaml

from football_edge.anchors import (
    ANCHOR_DIR,
    Anchor,
    _scan_anchors,
    archived_anchors,
    expected_anchor_names,
    missing_anchors,
)
from football_edge.collect import LEDGER_AUDIT_VIEW, _first_anchor_break, _ledger_rows
from football_edge.ledger import _canonical, verify_chain
from football_edge.market.devig import METHODS
from football_edge.site.contract import (
    EXIT_SITE_CHAIN,
    EXIT_SITE_CONFIG,
    EXIT_SITE_CUT,
    EXIT_SITE_INVALID,
    EXIT_SITE_NONDETERMINISTIC,
    MOVE_MIN_MATCHES,
    PATH_ID_LENGTH,
    PUBLIC_FLOOR,
    RECORD_COLUMNS,
    SITE_MIN_BOOKS,
    SITE_MIN_TEAM_MATCHES,
    content_sha256,
    iso_z,
)
from football_edge.site.derive import DeriveError, derive, record_mismatches
from football_edge.site.inputs import AnchorValue, DumpConfig, LedgerCut, dump_text, load_inputs
from football_edge.site.verify import snapshot_errors

LOGGER = logging.getLogger("football_edge.site.export")
SNAPSHOT_FILE = "snapshot.json"
HASH_FILE = "snapshot.sha256"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHILD_ENV_DROPPED = ("SITE_DATABASE_URL", "DATABASE_URL")

_ISOLATION = (
    "SELECT current_setting('transaction_isolation'), current_setting('transaction_read_only')"
)
_FLOOR = "SELECT site.public_floor()"
_HEAD = "SELECT rows, last_id, head FROM site.ledger_head"
_LEAGUES = "SELECT id, name, country FROM site.leagues ORDER BY id"
_MATCHES = "SELECT id, league_id, commence_time, home_team, away_team FROM site.matches ORDER BY id"
_QUOTES = (
    "SELECT ledger_id, match_id, observed_at, is_closing, outcome, price, book_key "
    "FROM site_input.h2h_quotes WHERE ledger_id <= %s ORDER BY ledger_id"
)
_RECORD = (
    f"SELECT {', '.join(name for name, _ in RECORD_COLUMNS)} FROM site.record "
    "ORDER BY publication_id"
)


class ExportRefused(RuntimeError):
    """Yayın yok: `code` CLI'nin çıkış kodu, mesaj adıyla ne olduğunu söyler (değer taşımaz)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExportSummary:
    matches: int
    leagues: int
    teams: int
    rows: int
    last_id: int
    content_sha256: str
    file_sha256: str


def devig_method(path: Path) -> str:
    """Modelin vig yöntemi (`config/model_faz3.yaml` `method`); `backtest` import edilmez (H1f)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    method = raw.get("method") if isinstance(raw, dict) else None
    if method not in METHODS:
        raise ExportRefused(EXIT_SITE_CONFIG, f"{path}: vig yöntemi okunamadı")
    return str(method)


def derive_in_subprocess(dump: str, *, hash_seed: str) -> str:
    """Aynı dökümden AYRI bir süreçte, verilen `PYTHONHASHSEED`le türetilen `content_sha256`.

    Çocuk DB'ye bağlanamaz (adres ortamından çıkarılır). Çıktısı ve hatası YAKALANIR ve loga
    aktarılmaz: çöken çocuğun traceback'i bir fiyat taşıyabilir.
    """
    env = {key: value for key, value in os.environ.items() if key not in _CHILD_ENV_DROPPED}
    env["PYTHONHASHSEED"] = hash_seed
    result = subprocess.run(
        [sys.executable, "-m", "football_edge.site", "derive-stdin"],
        input=dump,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=300,
    )
    if result.returncode != 0:
        raise ExportRefused(
            EXIT_SITE_NONDETERMINISTIC,
            f"ikinci türetim alt süreci düştü, çıkış kodu {result.returncode}",
        )
    found = result.stdout.strip()
    if _SHA256.fullmatch(found) is None:
        raise ExportRefused(EXIT_SITE_NONDETERMINISTIC, "ikinci türetim beklenmeyen çıktı verdi")
    return found


def other_hash_seed(environ: Mapping[str, str]) -> str:
    """Bu sürecin tohumundan FARKLI sabit bir tohum (ölçülen tek fark hash tohumudur)."""
    return "2" if environ.get("PYTHONHASHSEED") == "1" else "1"


def run_export(
    conn: psycopg.Connection[Any],
    out_dir: Path,
    *,
    generated_at: datetime,
    git_sha: str,
    method: str,
    schema: Mapping[str, Any],
    anchor_dir: Path = ANCHOR_DIR,
    derive_elsewhere: Callable[[str], str] | None = None,
) -> ExportSummary:
    """§5.1'in altı adımı; hepsi geçerse iki dosya yazılır, biri kırmızıysa hiçbiri."""
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ExportRefused(EXIT_SITE_CONFIG, f"{out_dir} boş değil — bayat dosyayla yayın yok")
    conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    conn.read_only = True
    with conn.transaction():
        _require_isolation(conn)
        anchor, head = _verified_chain(conn, anchor_dir)
        cut = _cut(conn, anchor, head)
        dump = _dump(conn, cut, anchor, method)
    inputs = load_inputs(dump)
    try:
        body = derive(inputs)
    except DeriveError as error:
        raise ExportRefused(EXIT_SITE_CUT, str(error)) from None
    local = content_sha256(body)
    elsewhere = derive_elsewhere or (
        lambda text: derive_in_subprocess(text, hash_seed=other_hash_seed(os.environ))
    )
    if elsewhere(dump) != local:
        raise ExportRefused(
            EXIT_SITE_NONDETERMINISTIC, "ikinci türetim farklı content_sha256 üretti"
        )
    problems = record_mismatches(inputs)
    if problems:
        raise ExportRefused(EXIT_SITE_CUT, "; ".join(problems))
    snapshot = {
        **body,
        "generated_at": iso_z(generated_at),
        "git_sha": git_sha,
        "content_sha256": local,
    }
    errors = snapshot_errors(snapshot, schema)
    if errors:
        raise ExportRefused(EXIT_SITE_INVALID, f"verify-snapshot: {len(errors)} ihlal: {errors[0]}")
    return _write(out_dir, snapshot, cut)


def _require_isolation(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(_ISOLATION)
        found = cur.fetchone()
    if found is None or tuple(found) != ("repeatable read", "on"):
        raise ExportRefused(EXIT_SITE_CUT, "işlem REPEATABLE READ, READ ONLY değil")


def _verified_chain(conn: psycopg.Connection[Any], anchor_dir: Path) -> tuple[Anchor, str]:
    """HER çıpa sorulur, kesim GENESIS'ten yeniden hash'lenir (§5.1/1); indirgeme kırmızıdır."""
    scan = _scan_anchors(anchor_dir)
    if scan.downgraded is not None:
        raise ExportRefused(
            EXIT_SITE_CHAIN, f"en yeni çıpa okunamadı ({scan.downgraded.name}) — indirgeme yok"
        )
    if not scan.readable:
        raise ExportRefused(EXIT_SITE_CHAIN, "çıpa yok ya da okunamadı — çıpasız yayın yok")
    expected = expected_anchor_names(anchor_dir)
    if expected is None:
        raise ExportRefused(
            EXIT_SITE_CHAIN, "git geçmişi okunamadı — ÇIPA EKSİKLİĞİ KONTROLÜ ATLANDI (kırmızı)"
        )
    gone = missing_anchors(anchor_dir, recorded=expected)
    if gone:
        raise ExportRefused(EXIT_SITE_CHAIN, "ÇIPA EKSİK: " + ", ".join(gone))
    archived = archived_anchors(anchor_dir, recorded=expected)
    if archived:
        LOGGER.warning("arşivlenmiş çıpa (kanıt kapsamı daraldı): %d", len(archived))
    breakage = _first_anchor_break(conn, scan.readable, relation=LEDGER_AUDIT_VIEW)
    if breakage is not None:
        raise ExportRefused(EXIT_SITE_CHAIN, f"ÇIPA UYUŞMAZLIĞI: {breakage}")
    result = verify_chain(_ledger_rows(conn, None, relation=LEDGER_AUDIT_VIEW))
    if not result.ok:
        raise ExportRefused(
            EXIT_SITE_CHAIN, f"zincir KIRIK: {result.failed_index}. satır, {result.error}"
        )
    return scan.readable[-1], result.head


def _cut(conn: psycopg.Connection[Any], anchor: Anchor, head: str) -> LedgerCut:
    with conn.cursor() as cur:
        cur.execute(_FLOOR)
        floor = (cur.fetchone() or (None,))[0]
        cur.execute(_HEAD)
        found = cur.fetchone()
    if floor != PUBLIC_FLOOR:
        raise ExportRefused(EXIT_SITE_CUT, "site.public_floor() Python tabanından farklı (H1)")
    if found is None:
        raise ExportRefused(EXIT_SITE_CUT, "site.ledger_head satır döndürmedi")
    rows, last_id = int(found[0]), int(found[1])
    if anchor.rows > 0 and rows == 0:
        raise ExportRefused(
            EXIT_SITE_CUT, "çıpa satır diyor, görünüm 0 satır döndü (görünüm sahipliği/RLS?)"
        )
    return LedgerCut(rows, last_id, head)


def _dump(conn: psycopg.Connection[Any], cut: LedgerCut, anchor: Anchor, method: str) -> str:
    with conn.cursor() as cur:
        leagues = _all(cur, _LEAGUES)
        matches = _all(cur, _MATCHES)
        quotes = _all(cur, _QUOTES, (cut.last_id,))
        record = _all(cur, _RECORD)
    quoted = {row[1] for row in quotes}
    shown = [row for row in matches if row[0] in quoted]
    if anchor.rows > 0 and not shown:
        raise ExportRefused(EXIT_SITE_CUT, "defterde satır var ama maç kümesi boş")
    if any(row[2] < PUBLIC_FLOOR for row in matches):
        raise ExportRefused(EXIT_SITE_CUT, "görünüm tabandan eski bir maç döndürdü (H1)")
    return dump_text(
        config=DumpConfig(
            method, SITE_MIN_BOOKS, SITE_MIN_TEAM_MATCHES, MOVE_MIN_MATCHES, PATH_ID_LENGTH
        ),
        floor=PUBLIC_FLOOR,
        ledger=cut,
        anchor=AnchorValue(anchor.path.name, anchor.rows, anchor.last_id, anchor.head),
        leagues=leagues,
        matches=matches,
        quotes=quotes,
        record=record,
    )


def _all(cur: psycopg.Cursor[Any], sql: str, params: tuple[Any, ...] = ()) -> list[Sequence[Any]]:
    cur.execute(sql, params or None)
    return [tuple(row) for row in cur.fetchall()]


def _write(out_dir: Path, snapshot: Mapping[str, Any], cut: LedgerCut) -> ExportSummary:
    payload = (_canonical(dict(snapshot)) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / SNAPSHOT_FILE).write_bytes(payload)
    (out_dir / HASH_FILE).write_text(f"{digest}  {SNAPSHOT_FILE}\n", encoding="utf-8")
    return ExportSummary(
        matches=len(snapshot["matches"]),
        leagues=len(snapshot["leagues"]),
        teams=len(snapshot["teams"]),
        rows=cut.rows,
        last_id=cut.last_id,
        content_sha256=str(snapshot["content_sha256"]),
        file_sha256=digest,
    )
````

- [ ] **Step 7: CLI'ın tam hâli** (`src/football_edge/site/__main__.py` dosyasının TAMAMI bununla değişir)

`src/football_edge/site/__main__.py` (tam içerik):

````python
"""`python -m football_edge.site {export,verify-snapshot,derive-stdin}` (Faz 6 İz B §5.1).

`export`: `SITE_DATABASE_URL` (yalnız `site_reader`) ile tek salt okuma işleminde anlık görüntü
üretir; secret'ın varlığını kendisi denetler. `verify-snapshot`: DB'siz denetim. `derive-stdin`:
dışa aktarımın ikinci türetimi için İÇ komut — girdi dökümünü stdin'den okur, yalnız
`content_sha256` basar, DB'ye bağlanmaz.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from football_edge.collect import configure_logging
from football_edge.db import connect
from football_edge.site.contract import (
    DEVIG_CONFIG_PATH,
    EXIT_SITE_CONFIG,
    EXIT_SITE_INVALID,
    SCHEMA_PATH,
    content_sha256,
)
from football_edge.site.derive import derive
from football_edge.site.export import ExportRefused, devig_method, run_export
from football_edge.site.inputs import load_inputs
from football_edge.site.schema import check_schema
from football_edge.site.verify import snapshot_errors

LOGGER = logging.getLogger("football_edge.site")
DSN_VAR = "SITE_DATABASE" + "_URL"


def _schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    check_schema(schema)
    return schema


def _git_sha() -> str:
    found = os.environ.get("GITHUB_SHA", "")
    if not found:
        try:
            found = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=30
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            found = ""
    if len(found) != 40:
        raise ExportRefused(EXIT_SITE_CONFIG, "git SHA okunamadı")
    return found


def _export(out_dir: Path) -> int:
    dsn = os.environ.get(DSN_VAR, "")
    if not dsn:
        sys.stdout.write(f"{DSN_VAR} yok — yayın yapılmadı\n")
        return EXIT_SITE_CONFIG
    try:
        method = devig_method(DEVIG_CONFIG_PATH)
        git_sha = _git_sha()
        with connect(dsn) as conn:
            summary = run_export(
                conn,
                out_dir,
                generated_at=datetime.now(UTC),
                git_sha=git_sha,
                method=method,
                schema=_schema(),
            )
    except ExportRefused as refused:
        sys.stdout.write(f"DIŞA AKTARIM REDDEDİLDİ: {refused}\n")
        return refused.code
    LOGGER.info(
        "anlık görüntü yazıldı: maç=%d lig=%d takım=%d satır=%d last_id=%d "
        "content_sha256=%s dosya_sha256=%s",
        summary.matches,
        summary.leagues,
        summary.teams,
        summary.rows,
        summary.last_id,
        summary.content_sha256,
        summary.file_sha256,
    )
    return 0


def _verify(path: Path, sha256_file: Path | None) -> int:
    payload = path.read_bytes()
    errors = snapshot_errors(json.loads(payload), _schema())
    if sha256_file is not None:
        recorded = sha256_file.read_text(encoding="utf-8").split()
        if not recorded or recorded[0] != hashlib.sha256(payload).hexdigest():
            errors.append(f"{sha256_file.name}: dosya baytlarının sha256'sı değil")
    for text in errors:
        sys.stdout.write(f"ANLIK GÖRÜNTÜ İHLALİ: {text}\n")
    if errors:
        return EXIT_SITE_INVALID
    sys.stdout.write(f"anlık görüntü geçerli: {path.name}\n")
    return 0


def _derive_stdin() -> int:
    sys.stdout.write(content_sha256(derive(load_inputs(sys.stdin.read()))) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m football_edge.site")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="DB → snapshot.json + snapshot.sha256")
    export.add_argument("--out", type=Path, required=True)
    verify = commands.add_parser("verify-snapshot", help="anlık görüntünün DB'siz denetimi")
    verify.add_argument("path", type=Path)
    verify.add_argument("--sha256", type=Path, default=None)
    commands.add_parser("derive-stdin", help="İÇ: dışa aktarımın ikinci türetimi")
    args = parser.parse_args(argv)
    if args.command == "derive-stdin":
        return _derive_stdin()
    configure_logging()
    if args.command == "export":
        return _export(args.out)
    return _verify(args.path, args.sha256)


if __name__ == "__main__":
    raise SystemExit(main())
````

- [ ] **Step 8: Site DSN'ini redaksiyona ekle** (`src/football_edge/collect.py`)

```python
# ESKİ
def _log_secrets() -> tuple[str, ...]:
    """Pipeline'ın ortamdan aldığı her credential; boş olanı `redact` zaten atlar."""
    dsn = os.getenv("DATABASE_URL", "")
    # Tam DSN parolasından ÖNCE değişir: yoksa URL'nin kalanı (kullanıcı, host) açıkta kalır.
    return (
        os.getenv("ODDS_API_KEY", ""),
        os.getenv("TYPESAFE_API_KEY", ""),
        dsn,
        *dsn_password_forms(dsn),
    )
# YENİ
def _log_secrets() -> tuple[str, ...]:
    """Pipeline'ın ortamdan aldığı her credential; boş olanı `redact` zaten atlar.

    `SITE_DATABASE_URL` sitenin salt okuma rolünün adresidir (Faz 6 İz B §5.1, DEFERRED 10o):
    `site export` aynı kök handler'dan loglar.
    """
    dsns = (os.getenv("DATABASE_URL", ""), os.getenv("SITE_DATABASE_URL", ""))
    # Tam DSN parolasından ÖNCE değişir: yoksa URL'nin kalanı (kullanıcı, host) açıkta kalır.
    return (
        os.getenv("ODDS_API_KEY", ""),
        os.getenv("TYPESAFE_API_KEY", ""),
        *dsns,
        *(form for dsn in dsns for form in dsn_password_forms(dsn)),
    )
```

- [ ] **Step 9: Yeşili gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_export.py tests/test_site_determinism.py tests/test_site_logging.py tests/test_log_redaction.py tests/test_site_verify.py tests/test_site_import_rule.py tests/test_jev_budget.py`
Expected: hepsi yeşil — yeni üç dosya `32 passed` (23 + 4 + 5); `test_log_redaction.py` değişmeden yeşil.

- [ ] **Step 10: Mutasyonla kırmızı kanıtı**

Önce spec §5.1/5 mutasyon (a) — olasılıksız kanıt: `test_the_two_fixed_seeds_really_order_the_fixture_team_set_differently`
yeşil olmalı (iki sabit tohum bu fixture'da küme sırasını GERÇEKTEN ayırıyor). Sonra:

| Dosya | Eski → yeni | Kırmızı |
|---|---|---|
| `src/football_edge/site/derive.py` | `    return [entries[key] for key in sorted(entries)]` → `    return [entries[key] for key in set(entries)]` | (a) `test_two_seeds_derive_the_same_content_hash` — dışa aktarımın belirlenimcilik ADIMI kırmızı (tohum 1 ≠ tohum 2) |
| `src/football_edge/site/export.py` | `        _require_isolation(conn)\n` → `` | `test_a_transaction_that_is_not_repeatable_read_is_red` |
| `src/football_edge/site/export.py` | `    if scan.downgraded is not None:` → `    if False:` | `test_an_unreadable_newest_anchor_is_red_not_downgraded` |
| `src/football_edge/site/export.py` | `    if expected is None:` → `    if False:` | `test_an_unreadable_git_history_is_red_not_skipped` |
| `src/football_edge/site/export.py` | `    problems = record_mismatches(inputs)` → `    problems: list[str] = []` | `test_a_record_entry_the_ledger_cannot_reproduce_is_red` |
| `src/football_edge/site/export.py` | `return "2" if environ.get("PYTHONHASHSEED") == "1" else "1"` → `return "1"` | `test_the_other_seed_differs_from_this_process_seed` |
| `src/football_edge/site/export.py` | `    env = {key: value for key, value in os.environ.items() if key not in _CHILD_ENV_DROPPED}` → `    env = dict(os.environ)` | `test_the_child_gets_no_database_address_and_the_other_seed` |
| `src/football_edge/site/contract.py` + `src/football_edge/site/inputs.py` (İKİ NOKTA birlikte) | `    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` → `    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")` VE `        return canonical_timestamp(value)` → `        return value.isoformat()` | Review Focus 1: `test_review_focus_a_non_utc_session_exports_the_same_content`. Savunma iki katmanlıdır (döküm UTC'ye çevirir, `iso_z` de çevirir): tek noktalı mutasyon YEŞİL kalır — ölçüldü, beklenen budur |
| `src/football_edge/collect.py` | `dsns = (os.getenv("DATABASE_URL", ""), os.getenv("SITE_DATABASE_URL", ""))` → `dsns = (os.getenv("DATABASE_URL", ""), "")` | `test_the_site_dsn_and_its_password_are_redacted` |

- [ ] **Step 11: Lint ve tip** — `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`.

- [ ] **Step 12: Tam kapı** — `10 PASS` + `SKIP: zincir` + `KAPI YEŞİL`. Eklenen `leakage` testi: 1.

- [ ] **Step 13: Commit**

```bash
git add src/football_edge/site/export.py src/football_edge/site/__main__.py src/football_edge/collect.py \
  tests/fake_site_db.py tests/test_site_export.py tests/test_site_determinism.py tests/test_site_logging.py
git commit -m "feat: site export — tek salt okuma işlemi, tam zincir, ikinci türetim, verify-snapshot, iki dosya (Faz 6 B-1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Uçtan uca kap testi — gerçek görünüm SQL'i → dışa aktarıcı → `verify-snapshot`

**Kademe:** K1 · **Spec:** §4.4/3, §6.4/2, N1 (iki kurcalama), §12.1 (`site-db` adımının sabit dizini), §12.4/12 ·
**Bağımlılık:** Task 3 (0014 + harness), Task 6 (dışa aktarıcı) · **Worktree:** `wt-b1-t7`

Şablonun kopyasında sentetik ama GEÇERLİ zincirli defter tohumlanır (`ledger.chain`), çıpa geçici bir git deposunda
kesimin ORTASINI (`id=40`) gösterir, dışa aktarım `site_reader` olarak koşar, çıktı `verify-snapshot` CLI'ından geçer
ve ELLE hesaplanmış beklenenlerle karşılaştırılır — açılış/son/kapanış `p`, `move`, `rounds`, her görünen turun
`books`u, `sealed`, eşik altı tur → `null`, mühürsüz maç → `closing: null`, taban komşusu
(`2026-07-01T23:59:59.999999Z`), holdout maçı ve pasif ligin maçı anlık görüntüde YOK. İki kurcalama varyantı
(çıpa öncesi `id=20`, sonrası `id=60`) satır INSERT'ten ÖNCE değiştirilerek kurulur; saklanan hash'ler eski kalır;
her varyant kendi kopyasında (`site_db_each`); ikisi de exit 21 ve hiçbir dosya. Başarılı koşu anlık görüntüyü
`SITE_E2E_DIR` tanımlıysa oraya bu `verify.sh` koşusunun kimliğiyle (`FE_VERIFY_RUN_ID`) bırakır (Task 9 adımı, B-2 okur).
**Sınır:** `site.record` Faz 5'e kadar `where false`; sicil uçtan uca yalnız BOŞ hâliyle koşar (§12.4/12) — dolu sicil
Task 6'nın sahte görünümleriyle sınandı.

**Files:**
- Test: `tests/test_site_e2e_db.py`
- Modify: `scripts/sandbox_db.sh` (`DEFAULT_TESTS`e e2e dosyası)

**Interfaces:**
- Consumes: `tests.site_db.{site_cluster, site_db_each}`, `tests.site_builders.*`, `site.export.{run_export,
  devig_method, ExportRefused}`, `site.contract.{DEVIG_CONFIG_PATH, EXIT_SITE_CHAIN}`.
- Produces (Task 9, B-2): `SITE_E2E_DIR` tanımlıyken `<SITE_E2E_DIR>/snapshot.json`, `snapshot.sha256`, `run-id`
  (içerik = `FE_VERIFY_RUN_ID`, satır sonu yok).

- [ ] **Step 1: Uçtan uca testi yaz**

`tests/test_site_e2e_db.py` (tam içerik):

````python
"""Uçtan uca (§4.4/3): gerçek görünüm SQL'i → dışa aktarıcı → `verify-snapshot`, kapta.

Beklenen değerler ELLE hesaplandı; türetme kodu çağrılmaz (adil kitaplar, `site_builders`).
Kurcalama iki varyant: çıpa ÖNCESİ ve SONRASI bir satırın fiyatı INSERT'ten ÖNCE değiştirilir,
saklanan hash'ler eski kalır — UPDATE ve tetikleyici kapatma yoktur. Her varyant kendi kopyasında.
Sınır: `site.record` Faz 5'e kadar `where false`; sicil yalnız BOŞ hâliyle koşar (§12.4/12).
Başarılı koşu anlık görüntüyü `SITE_E2E_DIR`e (verify.sh `site-db` adımı) bu koşunun kimliğiyle
bırakır; B-2'nin `next build` adımı onu okur.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest

from football_edge.site.contract import DEVIG_CONFIG_PATH, EXIT_SITE_CHAIN
from football_edge.site.export import ExportRefused, devig_method, run_export
from tests.site_builders import (
    AWAY_FAVOURED,
    DRAWISH,
    EVEN,
    HOME_HEAVY,
    SYMMETRIC,
    Round,
    anchored_repo,
    ledger,
    payloads,
)
from tests.site_db import site_cluster, site_db_each

pytestmark = pytest.mark.sitedb

REPO = Path(__file__).resolve().parent.parent
SCHEMA: dict[str, Any] = json.loads(
    (REPO / "web/contract/snapshot.schema.json").read_text(encoding="utf-8")
)
M1, M2, M3 = ("01" + "ef" * 15), ("02" + "ef" * 15), ("03" + "ef" * 15)
EDGE, HOLDOUT, ASLEEP = ("04" + "ef" * 15), ("05" + "ef" * 15), ("06" + "ef" * 15)
MATCHES = [
    (M1, "e2e.1", "2026-09-22T14:00:00Z", "Alfa Spor", "Beta FK"),
    (M2, "e2e.1", "2026-09-23T15:00:00Z", "Gamma United", "Alfa Spor"),
    (M3, "e2e.1", "2026-09-24T16:00:00Z", "Delta Şehir", "Beta FK"),
    (EDGE, "e2e.1", "2026-07-01T23:59:59.999999Z", "Kenar A", "Kenar B"),
    (HOLDOUT, "e2e.1", "2026-01-15T12:00:00Z", "Eski A", "Eski B"),
    (ASLEEP, "e2e.9", "2026-09-21T18:00:00Z", "Uyku A", "Uyku B"),
]
ROUNDS = [
    Round(HOLDOUT, "2026-01-14T10:00:00Z", "Eski A", "Eski B", [EVEN] * 3),  # id 1–9
    Round(EDGE, "2026-06-30T10:00:00Z", "Kenar A", "Kenar B", [EVEN] * 3),  # 10–18
    Round(M1, "2026-09-20T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3),  # 19–27
    Round(ASLEEP, "2026-09-20T09:00:00Z", "Uyku A", "Uyku B", [EVEN] * 3),  # 28–36
    Round(M2, "2026-09-20T11:00:00Z", "Gamma United", "Alfa Spor", [AWAY_FAVOURED] * 3),  # 37–45
    Round(M1, "2026-09-21T10:00:00Z", "Alfa Spor", "Beta FK", [EVEN] * 3, drop_away_for=0),  # 46–53
    Round(M2, "2026-09-21T11:00:00Z", "Gamma United", "Alfa Spor", [DRAWISH] * 3),  # 54–62
    Round(M3, "2026-09-21T12:00:00Z", "Delta Şehir", "Beta FK", [HOME_HEAVY] * 2),  # 63–68
    Round(M1, "2026-09-22T13:00:00Z", "Alfa Spor", "Beta FK", SYMMETRIC, is_closing=True),  # 69–77
]
ROWS = ledger(payloads(ROUNDS))
ANCHOR_ID = 40  # kesimin ortası: öncesi ve sonrası satır var
CLOSE = {
    "observed_at": "2026-09-22T13:00:00Z",
    "books": 3,
    "p": {"home": 33.3, "draw": 33.3, "away": 33.3},
}
EXPECTED_MATCHES = [
    {
        "id": M1,
        "league_id": "e2e.1",
        "path_id": M1[:12],
        "slug": "alfa-spor-vs-beta-fk",
        "date": "2026-09-22",
        "commence_time": "2026-09-22T14:00:00Z",
        "home": "Alfa Spor",
        "away": "Beta FK",
        "sealed": True,
        "rounds": 3,
        "h2h": {
            "opening": {
                "observed_at": "2026-09-20T10:00:00Z",
                "books": 3,
                "p": {"home": 50.0, "draw": 25.0, "away": 25.0},
            },
            "latest": CLOSE,
            "closing": CLOSE,
        },
        "move": {"home": -16.7, "draw": 8.3, "away": 8.3},
        "indexable": True,
    },
    {
        "id": M2,
        "league_id": "e2e.1",
        "path_id": M2[:12],
        "slug": "gamma-united-vs-alfa-spor",
        "date": "2026-09-23",
        "commence_time": "2026-09-23T15:00:00Z",
        "home": "Gamma United",
        "away": "Alfa Spor",
        "sealed": False,
        "rounds": 2,
        "h2h": {
            "opening": {
                "observed_at": "2026-09-20T11:00:00Z",
                "books": 3,
                "p": {"home": 25.0, "draw": 25.0, "away": 50.0},
            },
            "latest": {
                "observed_at": "2026-09-21T11:00:00Z",
                "books": 3,
                "p": {"home": 20.0, "draw": 40.0, "away": 40.0},
            },
            "closing": None,
        },
        "move": {"home": -5.0, "draw": 15.0, "away": -10.0},
        "indexable": True,
    },
    {
        "id": M3,
        "league_id": "e2e.1",
        "path_id": M3[:12],
        "slug": "delta-sehir-vs-beta-fk",
        "date": "2026-09-24",
        "commence_time": "2026-09-24T16:00:00Z",
        "home": "Delta Şehir",
        "away": "Beta FK",
        "sealed": False,
        "rounds": 1,
        "h2h": {"opening": None, "latest": None, "closing": None},
        "move": None,
        "indexable": False,
    },
]


@pytest.fixture(autouse=True)
def _child_imports_this_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))


def _seed(url: str, rows: tuple[dict[str, Any], ...]) -> None:
    columns = (
        "match_id",
        "observed_at",
        "bookmaker",
        "market",
        "outcome",
        "point",
        "price",
        "bookmaker_last_update",
        "is_closing",
        "prev_hash",
        "row_hash",
    )
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO leagues VALUES "
            "('e2e.1', 'k1', 'Deneme Ligi', 'Testland', 'tr', 'TR', true), "
            "('e2e.9', 'k9', 'Uyuyan Lig', 'Testland', 'tr', 'TR', false)"
        )
        cur.executemany(
            "INSERT INTO matches (id, league_id, commence_time, home_team, away_team) "
            "VALUES (%s, %s, %s, %s, %s)",
            MATCHES,
        )
        cur.executemany(
            f"INSERT INTO odds_snapshots ({', '.join(columns)}) "
            f"VALUES ({', '.join(['%s'] * len(columns))})",
            [tuple(row[name] for name in columns) for row in rows],
        )
        cur.execute("SELECT max(id) FROM odds_snapshots")
        assert cur.fetchone() == (len(rows),), "kimlikler 1..N olmalı (çıpa id'ye bağlı)"


def _export(url: str, tmp_path: Path) -> Path:
    anchors = anchored_repo(
        tmp_path / "repo",
        rows=ANCHOR_ID,
        last_id=ANCHOR_ID,
        head=str(ROWS[ANCHOR_ID - 1]["row_hash"]),
        day="2026-09-21",
    )
    out = tmp_path / "out"
    conn = psycopg.connect(url, autocommit=True, options="-c timezone=UTC")
    try:
        conn.execute("SET ROLE site_reader")  # canlıda LOGIN'li site_reader'ın kendisi
        conn.autocommit = False
        run_export(
            conn,
            out,
            generated_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
            git_sha="1" * 40,
            method=devig_method(REPO / DEVIG_CONFIG_PATH),
            schema=SCHEMA,
            anchor_dir=anchors,
        )
    finally:
        conn.close()
    return out


def _hand_to_the_site_build(out: Path) -> None:
    """§12.1: `site-db` adımının sabit dizini; `run-id` bu `verify.sh` koşusunun kimliği."""
    target = os.environ.get("SITE_E2E_DIR", "")
    if not target:
        return
    directory = Path(target)
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("snapshot.json", "snapshot.sha256"):
        (directory / name).write_bytes((out / name).read_bytes())
    (directory / "run-id").write_text(os.environ.get("FE_VERIFY_RUN_ID", ""), encoding="utf-8")


@pytest.mark.leakage
def test_the_real_views_export_the_hand_computed_snapshot(
    site_db_each: str, tmp_path: Path
) -> None:
    _seed(site_db_each, ROWS)

    out = _export(site_db_each, tmp_path)

    assert sorted(path.name for path in out.iterdir()) == ["snapshot.json", "snapshot.sha256"]
    payload = (out / "snapshot.json").read_bytes()
    snapshot = json.loads(payload)
    assert (out / "snapshot.sha256").read_text(encoding="utf-8") == (
        f"{hashlib.sha256(payload).hexdigest()}  snapshot.json\n"
    )
    assert snapshot["matches"] == EXPECTED_MATCHES, "taban komşusu, holdout ya da pasif lig sızdı"
    assert snapshot["ledger"] == {
        "rows": len(ROWS),
        "last_id": len(ROWS),
        "head": ROWS[-1]["row_hash"],
        "anchor": {
            "file": "head-2026-09-21.txt",
            "rows": ANCHOR_ID,
            "last_id": ANCHOR_ID,
            "head": ROWS[ANCHOR_ID - 1]["row_hash"],
        },
    }
    assert snapshot["leagues"] == [
        {
            "id": "e2e.1",
            "slug": "deneme-ligi",
            "name": "Deneme Ligi",
            "country": "Testland",
            "matches": 3,
            "move_distribution": None,
        }
    ]
    assert [(t["slug"], t["matches"], t["indexable"]) for t in snapshot["teams"]] == [
        ("alfa-spor", 2, False),
        ("beta-fk", 2, False),
        ("delta-sehir", 1, False),
        ("gamma-united", 1, False),
    ]
    assert snapshot["record"] == {"published": 0, "entries": [], "summary": None}
    assert (snapshot["value_badge"], snapshot["analysis"]) == (None, None)
    verified = subprocess.run(
        [
            sys.executable,
            "-m",
            "football_edge.site",
            "verify-snapshot",
            str(out / "snapshot.json"),
            "--sha256",
            str(out / "snapshot.sha256"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr
    _hand_to_the_site_build(out)


@pytest.mark.parametrize(("where", "row_id"), [("çıpa öncesi", 20), ("çıpa sonrası", 60)])
def test_a_tampered_price_stops_the_export_before_any_file(
    site_db_each: str, tmp_path: Path, where: str, row_id: int
) -> None:
    """N1: dışa aktarım GENESIS'ten hash'ler; iki konum da exit ≠ 0 ve dosya yok."""
    forged = [dict(row) for row in ROWS]
    forged[row_id - 1]["price"] = Decimal(str(forged[row_id - 1]["price"])) + 1
    _seed(site_db_each, tuple(forged))

    with pytest.raises(ExportRefused, match="zincir KIRIK") as refused:
        _export(site_db_each, tmp_path)

    assert refused.value.code == EXIT_SITE_CHAIN, where
    assert not (tmp_path / "out").exists()
````

- [ ] **Step 2: Kum havuzunun varsayılan dosyalarına ekle** (`scripts/sandbox_db.sh`)

```bash
# ESKİ
DEFAULT_TESTS=(tests/test_api_roles_lockdown_db.py tests/test_jev_tables_db.py tests/test_holdout_phase_db.py
  tests/test_site_views_db.py)
# YENİ
DEFAULT_TESTS=(tests/test_api_roles_lockdown_db.py tests/test_jev_tables_db.py tests/test_holdout_phase_db.py
  tests/test_site_views_db.py tests/test_site_e2e_db.py)
```

- [ ] **Step 3: DB'siz koşuda adıyla SKIP, `CI=true`de FAIL olduğunu gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider -rs tests/test_site_e2e_db.py`
Expected: `3 skipped` ve `SKIP: site-db (SITE_TEST_DATABASE_URL yok)`.
Run: `CI=true PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_e2e_db.py`
Expected: `3 errors` — `SITE_TEST_DATABASE_URL yok ve CI=true — site-db kapısı atlanamaz (B10)`.

- [ ] **Step 4: Yerel kapta yeşil**

Run: `scripts/sandbox_db.sh test tests/test_site_e2e_db.py tests/test_site_views_db.py`
Expected: **21 passed, 0 skipped** (3 + 18). Bu test yeni üretim kodu istemez: Task 3 ve 6 birleşik hâlde doğruysa ilk
koşuda yeşildir; kanıt Step 5'in mutasyonlarıdır.

- [ ] **Step 5: Mutasyonla kırmızı kanıtı** (`scripts/sandbox_db.sh test tests/test_site_e2e_db.py`)

| Dosya | Eski → yeni | Kırmızı |
|---|---|---|
| `db/migrations/0014_site_read.sql` | `  join site.leagues l on l.id = m.league_id\n` → `` | `test_the_real_views_export_the_hand_computed_snapshot`: pasif ligin maçı görünüme sızar, `verify-snapshot` `bilinmeyen lig` der, dışa aktarım exit 24 |
| `db/migrations/0014_site_read.sql` | `grant execute on function site.public_floor() to site_reader;` → `` | `test_the_real_views_export_the_hand_computed_snapshot` (`site.public_floor()` yetki hatası). Kurcalama testleri YEŞİL kalır: zincir adımı tabandan önce durur — beklenen |
| `src/football_edge/site/export.py` | `    if not result.ok:` → `    if False:` | iki kurcalama testi (N1: çıpa öncesi ve sonrası) |
| `tests/test_site_e2e_db.py` | `        head=str(ROWS[ANCHOR_ID - 1]["row_hash"]),` → `        head=str(ROWS[ANCHOR_ID]["row_hash"]),` (yalnız `_export` içindeki) | üç test de: dışa aktarım `ÇIPA UYUŞMAZLIĞI` ile exit 21 verir (başarılı test dosya bulamaz, kurcalama testleri `zincir KIRIK` yerine çıpa mesajı görür) — çıpa kontrolünün kapta GERÇEKTEN koştuğunun kanıtı |

Son satır bir test mutasyonudur (üretim kodu değil); geri yüklenir.

- [ ] **Step 6: Lint ve tip** — `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`.

- [ ] **Step 7: Tam kapı** — `10 PASS` + `SKIP: zincir` + `KAPI YEŞİL` (e2e `pytest` adımında `deselected`).

- [ ] **Step 8: Commit**

```bash
git add tests/test_site_e2e_db.py scripts/sandbox_db.sh
git commit -m "test: site uçtan uca — görünüm SQL'i, dışa aktarım, verify-snapshot, iki kurcalama (Faz 6 B-1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `site.yml` (bağlanmamış) ve secret taraması

**Kademe:** K1 (spec §14: "`site.yml` adım secret sınırı") · **Spec:** B9, H5c–d, §11, AK15, AK16, AK18 ·
**Bağımlılık:** Task 6 (CLI adları), Task 0 kaydı (`netlify_cli=`) · **Worktree:** `wt-b1-t8`

`site.yml` yalnız `workflow_dispatch`le tetiklenir; `schedule` ve pg_cron tetiği YOK. Secret'lar ADIM düzeyindedir:
`SITE_DATABASE_URL` yalnız dışa aktarım adımında, `NETLIFY_AUTH_TOKEN`/`NETLIFY_SITE_ID` yalnız yayın adımında; kurulum,
derleme ve tarayıcı adımları secret'sızdır; `DATABASE_URL`, `ODDS_API_KEY`, `TYPESAFE_API_KEY` hiçbir yerde yok.
Node adımlarının GÖVDELERİ B-2'nindir (§11'in komut adlarıyla yazıldı; B-2, B-1 birleştikten sonra değiştirebilir —
bu görevin testi yalnız secret sınırını ve sırayı sınar). Kaybolan-slug kontrolü (AK20 b) ve yayın sonrası kontrol
(§6.4/3f) B-2'nin eklediği adımlardır. `check_secrets.sh` Netlify tokenını adıyla tanır; site DSN'i `DATABASE_URL`
alt dizesiyle zaten yakalanır.

**Files:**
- Create: `.github/workflows/site.yml`
- Modify: `scripts/check_secrets.sh` (regex + yorum)
- Test: `tests/test_site_workflow.py`, `tests/test_secrets_scan_netlify.py`

**Interfaces:**
- Consumes: `tests.workflow_helpers.{_steps, _index_of, _triggers}`; Task 0 kaydındaki `netlify_cli=`.
- Produces (B-2): `site.yml` adım sırası — checkout (`fetch-depth: 0`, `persist-credentials: false`) → `uv sync
  --frozen` → secret taraması → `site export --out web/.snapshot` (`SITE_DATABASE_URL`) → `verify-snapshot
  web/.snapshot/snapshot.json --sha256 web/.snapshot/snapshot.sha256` → `actions/setup-node` (`web/.nvmrc`) →
  `pnpm/action-setup` (`web/package.json`) → `pnpm -C web install --frozen-lockfile` → `pnpm -C web exec next build` →
  `node web/scripts/check-out.ts` → `npx --yes netlify-cli@<T0> deploy --prod --dir web/out --config web/netlify.toml`
  (`NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID`).

- [ ] **Step 1: İş akışı testini yaz**

`tests/test_site_workflow.py` (tam içerik):

````python
"""`site.yml` (§11, H5d): elle tetiklenir, secret ADIM düzeyinde, yalnız iki adımda.

Ham metin taraması değil ayrıştırılmış belge okunur (`tests/test_workflows.py` gerekçesi: yorum da
secret adını yazar). `${{ secrets.X }}` ifadesi yalnız bir adımın `env`inde durabilir; `run` metnine
gömülürse secret betik metnine girer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from tests.workflow_helpers import _index_of, _steps, _triggers

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / ".github/workflows/site.yml"
T0_RECORD = REPO / "docs/phases/06-site/b1-t0-olcumler.md"
EXPORT = "football_edge.site export"
DEPLOY = "deploy --prod --dir web/out"
SECRET = re.compile(r"\$\{\{\s*secrets\.(\w+)\s*\}\}")
PIPELINE_ONLY = ("DATABASE" + "_URL", "ODDS_API" + "_KEY", "TYPESAFE_API" + "_KEY")


def _document() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(SITE.read_text(encoding="utf-8"))
    return loaded


def _secrets_in(node: Any) -> set[str]:
    return set(SECRET.findall(yaml.safe_dump(node))) if node else set()


def test_site_is_dispatched_by_hand_only() -> None:
    """B9/AK15: `schedule`, `push`, pg_cron tetiği yok."""
    assert set(_triggers(SITE)) == {"workflow_dispatch"}


def test_site_reads_the_repository_and_deploys_one_at_a_time() -> None:
    document = _document()
    (job,) = document["jobs"].values()

    assert document["permissions"] == {"contents": "read"}
    assert "permissions" not in job
    assert document["concurrency"]["group"] == "site-deploy"
    (checkout,) = [s for s in _steps(SITE) if str(s.get("uses", "")).startswith("actions/checkout")]
    assert checkout["with"] == {"fetch-depth": 0, "persist-credentials": False}


def test_no_secret_lives_at_workflow_or_job_level() -> None:
    document = _document()
    (job,) = document["jobs"].values()

    assert _secrets_in(document.get("env")) == set()
    assert _secrets_in(job.get("env")) == set()


def test_each_secret_is_given_to_exactly_one_named_step_through_env() -> None:
    """H5d: DB adresi yalnız dışa aktarımda, Netlify kimliği yalnız yayında; öteki adımlar temiz."""
    given = {
        index: _secrets_in(step) for index, step in enumerate(_steps(SITE)) if _secrets_in(step)
    }
    export, deploy = _index_of(_steps(SITE), EXPORT), _index_of(_steps(SITE), DEPLOY)

    assert given == {
        export: {"SITE_DATABASE_URL"},
        deploy: {"NETLIFY_AUTH_TOKEN", "NETLIFY_SITE_ID"},
    }
    for index in given:
        step = _steps(SITE)[index]
        assert _secrets_in({key: value for key, value in step.items() if key != "env"}) == set()
        assert set(step["env"]) == given[index], "secret yalnız kendi adıyla env'e girer"


def test_the_pipeline_credentials_never_reach_the_site_job() -> None:
    names = {name for step in _steps(SITE) for name in (step.get("env") or {})}

    assert names.isdisjoint(PIPELINE_ONLY)
    assert _secrets_in(_document()).isdisjoint(PIPELINE_ONLY)


def test_the_export_is_scanned_verified_and_precedes_every_node_step() -> None:
    steps = _steps(SITE)
    scan = _index_of(steps, "scripts/check_secrets.sh")
    export = _index_of(steps, EXPORT)
    verify = _index_of(steps, "football_edge.site verify-snapshot")
    node = _index_of(steps, "actions/setup-node", key="uses")
    deploy = _index_of(steps, DEPLOY)

    assert None not in (scan, export, verify, node, deploy)
    assert scan < export < verify < node < deploy  # type: ignore[operator]
    assert "--out web/.snapshot" in steps[export]["run"]  # type: ignore[index]
    assert "--sha256 web/.snapshot/snapshot.sha256" in steps[verify]["run"]  # type: ignore[index]


def test_the_netlify_cli_is_pinned_to_the_t0_version() -> None:
    """Sürüm aralığı değil tam sürüm; değer T0 kaydından (tek kaynak)."""
    (recorded,) = re.findall(r"^netlify_cli=(\S+)$", T0_RECORD.read_text(encoding="utf-8"), re.M)
    (pinned,) = re.findall(
        r"netlify-cli@(\S+)", _steps(SITE)[_index_of(_steps(SITE), DEPLOY)]["run"]
    )  # type: ignore[index]

    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", pinned), pinned
    assert pinned == recorded
````

- [ ] **Step 2: Secret taraması testini yaz**

`tests/test_secrets_scan_netlify.py` (tam içerik):

````python
"""`scripts/check_secrets.sh` Netlify tokenını ve site DSN'ini de tanır (H5c).

Tarama geçici bir git deposunda koşturulur (git grep izlenen dosyaları okur). Ad=değer satırları
parçalardan kurulur: kapının kendi taraması bu test dosyasını eşlemesin.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts/check_secrets.sh"


def _scan(tmp_path: Path, line: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts/check_secrets.sh")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / "ayar.txt").write_text(line + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    return subprocess.run(
        ["bash", "scripts/check_secrets.sh"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "line",
    [
        "NETLIFY_AUTH" + "_TOKEN=nfp_" + "a1b2c3d4e5f6g7h8i9j0",
        "SITE_DATABASE" + "_URL=postgresql://site_reader:" + "gizli-parola-123@h:5432/postgres",
    ],
    ids=["netlify", "site-dsn"],
)
def test_a_filled_site_or_netlify_secret_turns_the_scan_red(tmp_path: Path, line: str) -> None:
    result = _scan(tmp_path, line)

    assert result.returncode == 1, result.stdout
    assert "HATA: izlenen dosyada dolu secret ataması var" in result.stdout


def test_an_empty_assignment_stays_clean(tmp_path: Path) -> None:
    result = _scan(tmp_path, "NETLIFY_AUTH" + "_TOKEN=")

    assert result.returncode == 0, result.stdout
````

- [ ] **Step 3: Kırmızıyı gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_workflow.py tests/test_secrets_scan_netlify.py`
Expected: `site.yml` testleri `FileNotFoundError`; `test_a_filled_site_or_netlify_secret_turns_the_scan_red[netlify]` kırmızı
(regex tokenı tanımıyor); `[site-dsn]` ve boş atama testi yeşil (DSN zaten yakalanıyor).

- [ ] **Step 4: İş akışını yaz**

`.github/workflows/site.yml` (tam içerik):

````yaml
name: site

# Faz 6 İz B (B9, §11): HAZIR, BAĞLI DEĞİL. Yalnız elle tetiklenir; zamanlama ve pg_cron tetiği
# YOK (AK15). Secret'lar (SITE_DATABASE_URL, NETLIFY_AUTH_TOKEN, NETLIFY_SITE_ID) kullanıcı
# onayından sonra eklenir (AK18); yokken dışa aktarım "SITE_DATABASE_URL yok — yayın yapılmadı"
# ile ADIYLA kırmızıdır — ayrı bir ön adım yoktur, secret yalnız o adıma verilir ve `if:` içinde
# okunamaz. Secret ADIM düzeyindedir (H5d): DB adresi yalnız dışa aktarımda, Netlify kimliği yalnız
# yayında; kurulum, derleme ve tarayıcı adımları secret'sızdır. Depo ve Actions logları public.
# Netlify derlemez (AK16): hazır `web/out` dizini CLI ile yüklenir.
on:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: site-deploy
  cancel-in-progress: false

jobs:
  site:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          # Çıpa eksikliği kontrolü git geçmişi ister; sığ klonda "ATLANDI" dışa aktarımı durdurur.
          fetch-depth: 0
          persist-credentials: false
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.11"
      - run: uv sync --frozen
      - name: Secret taraması
        run: ./scripts/check_secrets.sh
      - name: Anlık görüntü
        env:
          SITE_DATABASE_URL: ${{ secrets.SITE_DATABASE_URL }}
        run: uv run python -m football_edge.site export --out web/.snapshot
      - name: Anlık görüntü denetimi
        run: >-
          uv run python -m football_edge.site verify-snapshot web/.snapshot/snapshot.json
          --sha256 web/.snapshot/snapshot.sha256
      - uses: actions/setup-node@v4
        with:
          node-version-file: web/.nvmrc
      - uses: pnpm/action-setup@v4
        with:
          package_json_file: web/package.json
      - name: Site bağımlılıkları
        run: pnpm -C web install --frozen-lockfile
      - name: Statik derleme
        run: pnpm -C web exec next build
      - name: Çıktı tarayıcısı
        run: node web/scripts/check-out.ts
      - name: Yayın
        env:
          NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}
          NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}
        run: npx --yes netlify-cli@T0_NETLIFY_CLI deploy --prod --dir web/out --config web/netlify.toml
````

- [ ] **Step 5: `netlify-cli` sürümünü T0 kaydından yerleştir** (tahmin edilmez; test eşitliği sınar)

```bash
version="$(sed -n 's/^netlify_cli=//p' docs/phases/06-site/b1-t0-olcumler.md)"
test -n "$version" && python3 - "$version" <<'PY'
import sys
path = ".github/workflows/site.yml"
text = open(path, encoding="utf-8").read()
assert "netlify-cli@T0_NETLIFY_CLI" in text
open(path, "w", encoding="utf-8").write(text.replace("T0_NETLIFY_CLI", sys.argv[1]))
PY
grep -n "netlify-cli@" .github/workflows/site.yml
```
Expected: `npx --yes netlify-cli@<X.Y.Z> deploy …` (T0 kaydındaki değer).

- [ ] **Step 6: Secret taramasını genişlet** (`scripts/check_secrets.sh`)

```bash
# ESKİ
# Dolu değer atanmış secret benzeri satırlar (boş .env.example şablonu hariç).
git grep -nIE '(ODDS_API_KEY|DATABASE_URL|SUPABASE_[A-Z_]*KEY|TYPESAFE_API_KEY)[[:space:]]*=[[:space:]]*.?[A-Za-z0-9+/:@._-]{12,}' \
# YENİ
# Dolu değer atanmış secret benzeri satırlar (boş .env.example şablonu hariç). `SITE_DATABASE_URL`
# `DATABASE_URL` alt dizesiyle yakalanır; Netlify kişisel erişim tokenı hesabın bütün sitelerine
# yetkilidir (AK18) — adıyla listededir.
git grep -nIE '(ODDS_API_KEY|DATABASE_URL|SUPABASE_[A-Z_]*KEY|TYPESAFE_API_KEY|NETLIFY_AUTH_TOKEN)[[:space:]]*=[[:space:]]*.?[A-Za-z0-9+/:@._-]{12,}' \
```

- [ ] **Step 7: Yeşili gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_workflow.py tests/test_secrets_scan_netlify.py tests/test_workflows.py tests/test_access_method_rule.py`
Expected: hepsi yeşil — yeni iki dosya `10 passed` (7 + 3); `test_workflows.py`nin "yalnız push'layan iş akışı token'ı
diskte tutar" testi `site.yml`i de kapsar ve yeşildir. Ayrıca `./scripts/check_secrets.sh` → `secret taraması temiz`.

- [ ] **Step 8: Mutasyonla kırmızı kanıtı**

| Dosya | Eski → yeni | Kırmızı |
|---|---|---|
| `.github/workflows/site.yml` | `permissions:\n  contents: read\n` → `permissions:\n  contents: read\n\nenv:\n  SITE_DATABASE_URL: ${{ secrets.SITE_DATABASE_URL }}\n` | `test_no_secret_lives_at_workflow_or_job_level` |
| `.github/workflows/site.yml` | `          NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}\n` → `` ve `run: pnpm -C web exec next build` → `run: pnpm -C web exec next build ${{ secrets.NETLIFY_SITE_ID }}` | `test_each_secret_is_given_to_exactly_one_named_step_through_env` |
| `.github/workflows/site.yml` | `          fetch-depth: 0\n` → `` | `test_site_reads_the_repository_and_deploys_one_at_a_time` |
| `.github/workflows/site.yml` | `  workflow_dispatch:\n` → `  workflow_dispatch:\n  schedule:\n    - cron: "0 5 * * *"\n` | `test_site_is_dispatched_by_hand_only` |
| `scripts/check_secrets.sh` | `\|NETLIFY_AUTH_TOKEN)` → `)` | `test_a_filled_site_or_netlify_secret_turns_the_scan_red[netlify]` |

- [ ] **Step 9: Lint ve tip** — `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`.

- [ ] **Step 10: Tam kapı** — `10 PASS` + `SKIP: zincir` + `KAPI YEŞİL` (`secrets` adımı genişlemiş regex'le temiz).

- [ ] **Step 11: Commit**

```bash
git add .github/workflows/site.yml scripts/check_secrets.sh tests/test_site_workflow.py tests/test_secrets_scan_netlify.py
git commit -m "ci: site.yml hazır, bağlı değil — secret adım düzeyinde; secret taraması Netlify tokenını tanır (Faz 6 B-1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Dalga sonu birleştirmesi — CI kabı, `site-db` adımı, sayılar, B-2'ye devir

**Kademe:** K2 (kapı entegrasyonu, spec §14) · **Spec:** B10, §12.1 (`site-db` satırı, `FE_VERIFY_RUN_ID`, sabit dizin),
§12.2 (B-1 aşaması), §12.3 · **Bağımlılık:** Task 0–8 birleşmiş · **Worktree:** `wt-b1-t9` (controller yürütür —
`EXPECTED_MIN_*` dalga sonunda controller'ındır)

CI'ın `gate` işine iş içinde doğan bir `supabase/postgres` kabı eklenir (imaj ve özet T0 kaydından), `verify.sh`e
`site-db` adımı (`CI=true` iken kapsız → FAIL, yerelde adıyla SKIP), bu koşunun kimliği ve uçtan uca dizinin
sıfırlanması. Aynı kap `SANDBOX_DATABASE_URL`i de verir: 0013'ün kum havuzu testleri artık CI'da koşar (DEFERRED 18a'nın
tetiği bu migration'la ateşlendi); `DATABASE_URL` yine VERİLMEZ.

**Files:**
- Modify: `.github/workflows/ci.yml`, `verify.sh`, `tests/test_gate_traceback.py`, `docs/RUNBOOK.md` §4, `docs/DEFERRED.md` 18a
- Create: `tests/test_site_gate.py`, `docs/phases/06-site/HANDOFF.md`

**Interfaces:**
- Consumes: T0 kaydı (`image=`, `image_digest=`); Task 3 (`sitedb` işareti, seçiciler), Task 7 (`SITE_E2E_DIR`,
  `FE_VERIFY_RUN_ID` okuması).
- Produces: aşağıdaki "B-1 → B-2 devri" bloğu.

- [ ] **Step 1: Kapı bağlantısının testini yaz**

`tests/test_site_gate.py` (tam içerik):

````python
"""Site kapısının bağlantısı (§12.1–12.2, B10): CI kabı, `site-db` adımı, bayat dosya kimliği.

Metin ve ayrıştırılmış YAML okunur; kabın gerçekten kalktığını CI koşusunun kendisi kanıtlar
(Task 9 raporu).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from tests.workflow_helpers import _index_of, _steps

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github/workflows/ci.yml"
VERIFY = REPO / "verify.sh"
T0_RECORD = REPO / "docs/phases/06-site/b1-t0-olcumler.md"
SITE_DB = "Site test veritabanı"
# Parçalardan: test DB adresini yalnız `tests/site_db.py` anar (`test_site_harness_rules.py`).
VAR = "SITE_TEST_" + "DATABASE_URL"


def _recorded(key: str) -> str:
    (value,) = re.findall(rf"^{key}=(\S+)$", T0_RECORD.read_text(encoding="utf-8"), re.M)
    return value


def _site_db_step() -> dict[str, object]:
    (step,) = [step for step in _steps(CI) if step.get("name") == SITE_DB]
    return step


def test_ci_starts_the_site_database_before_the_gate() -> None:
    steps = _steps(CI)
    sync, site_db, gate = (
        _index_of(steps, "uv sync"),
        _index_of(steps, SITE_DB, key="name"),
        _index_of(steps, "./verify.sh"),
    )

    assert None not in (sync, site_db, gate)
    assert sync < site_db < gate  # type: ignore[operator]


def test_the_ci_image_is_the_t0_pinned_image_with_its_digest() -> None:
    """Tek kaynak: T0 kaydı. Etiket kayarsa CI başka bir Postgres'i ölçerdi."""
    env = _site_db_step()["env"]

    assert env == {"SITE_DB_IMAGE": f"{_recorded('image')}@{_recorded('image_digest')}"}  # type: ignore[comparison-overlap]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", _recorded("image_digest"))


def test_the_site_database_is_local_and_its_password_is_generated_and_masked() -> None:
    run = str(_site_db_step()["run"])

    assert 'password="$(openssl rand -hex 16)"' in run
    assert 'echo "::add-mask::${password}"' in run
    assert "-p 127.0.0.1:55432:5432" in run
    assert 'address="postgresql://postgres:${password}@127.0.0.1:55432/postgres"' in run
    assert 'for name in "SITE_TEST_' + 'DATABASE""_URL" "SANDBOX_DATABASE""_URL"; do' in run
    assert 'echo "${name}=${address}" >> "${GITHUB_ENV}"' in run
    assert "secrets." not in yaml.safe_dump(_site_db_step())


def _verify_text() -> str:
    return VERIFY.read_text(encoding="utf-8")


def test_the_run_id_is_exported_before_any_step() -> None:
    text = _verify_text()

    assert text.index("export FE_VERIFY_RUN_ID") < text.index('step "ruff-check"')


def test_sitedb_tests_run_exactly_once_in_their_own_step() -> None:
    text = _verify_text()

    assert 'step "pytest"      uv run pytest -q -m "not sitedb" --tb=short' in text
    assert text.count('-m "leakage and not sitedb"') == 2
    assert "uv run pytest tests/ -q -m sitedb -rs --tb=short" in text


def test_site_db_is_red_in_ci_and_named_skip_locally_without_a_database() -> None:
    text = _verify_text()
    branch = text[text.index(f'if [ -n "${{{VAR}:-}}" ]; then') :]

    assert 'elif [ "${CI:-}" = "true" ]; then' in branch
    assert 'site-db atlanamaz (B10)"; exit 1' in branch
    assert f'echo "SKIP: site-db ({VAR} yok)"' in branch


def test_the_end_to_end_directory_is_emptied_before_the_step_without_deleting() -> None:
    text = _verify_text()
    start = text.index('SITE_E2E_DIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e"')
    block = text[start : text.index(f'if [ -n "${{{VAR}:-}}" ]; then')]

    for name in ("snapshot.json", "snapshot.sha256", "run-id"):
        assert f': > "$SITE_E2E_DIR/{name}"' in block
    assert "rm " not in block
````

- [ ] **Step 2: Traceback sayımını güncelle** (`tests/test_gate_traceback.py`)

```python
# ESKİ
    [("verify.sh", 3), ("scripts/sandbox_db.sh", 1)],
# YENİ
    [("verify.sh", 4), ("scripts/sandbox_db.sh", 1)],
```

- [ ] **Step 3: Kırmızıyı gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_gate.py tests/test_gate_traceback.py`
Expected: `test_site_gate.py` 7 failed (adım ve bloklar yok), `test_gate_traceback.py` `verify.sh` vakası kırmızı (3 ≠ 4).

- [ ] **Step 4: CI kabı** (`.github/workflows/ci.yml`, üç düzenleme)

```yaml
# ESKİ
    timeout-minutes: 10
# YENİ
    # Site test kabı (çekme + hazır olma) ve `site-db` adımı eklendi; değer ölçülerek artırıldı
    # (Faz 6 İz B §12.2, B-1 Task 9 raporu).
    timeout-minutes: 20
```
`      - run: uv sync --frozen` satırının HEMEN ALTINA (`- name: Kapı` adımından önce):
```yaml
      # Faz 6 İz B §12.2/B10: sitenin katalog, davranış ve uçtan uca testleri gerçek Postgres ister.
      # Kap bu işin içinde doğar ve ölür; imaj T0'da ölçülüp sabitlendi (`docs/phases/06-site/
      # b1-t0-olcumler.md`, tek kaynak — test eşitliği sınar). Parola burada üretilir: depo secret'ı
      # DEĞİLDİR (`test_ci_reads_no_repository_secret_at_all`) ve maskelenir. Adres yalnız
      # 127.0.0.1'i gösterir (koşucunun kendi Postgres'iyle çakışmasın diye 55432); test düzeni başka
      # adresi reddeder. Aynı kap 0013'ün kum havuzu testlerini de koşar (DEFERRED 18a).
      # `DATABASE_URL` yine VERİLMEZ: katalog testleri adıyla SKIP.
      - name: Site test veritabanı
        env:
          SITE_DB_IMAGE: public.ecr.aws/supabase/postgres:17.6.1.143@T0_IMAGE_DIGEST
        run: |
          password="$(openssl rand -hex 16)"
          echo "::add-mask::${password}"
          docker run -d --name fe-site-db -e POSTGRES_PASSWORD="${password}" \
            -p 127.0.0.1:55432:5432 "${SITE_DB_IMAGE}" postgres -D /etc/postgresql
          for attempt in $(seq 1 90); do
            if docker exec -e PGPASSWORD="${password}" fe-site-db \
              psql -h localhost -U postgres -d postgres -Atc 'select 1' >/dev/null 2>&1; then
              address="postgresql://postgres:${password}@127.0.0.1:55432/postgres"
              # Adlar parçalardan: kapının secrets taraması `AD=değer` biçimini arar.
              for name in "SITE_TEST_DATABASE""_URL" "SANDBOX_DATABASE""_URL"; do
                echo "${name}=${address}" >> "${GITHUB_ENV}"
              done
              echo "site test veritabanı hazır (deneme ${attempt})"
              exit 0
            fi
            sleep 2
          done
          echo "HATA: site test veritabanı 180 sn'de hazır olmadı"
          docker logs fe-site-db 2>&1 | tail -n 40
          exit 1
```
`Kapı` adımının yorumunda: `Geri kalan on adım koşar:` → `Geri kalan on bir adım koşar:` ve
`# veri-sözleşmesi · sızıntı · dil-kalibrasyonu · secrets.` → `# veri-sözleşmesi · sızıntı · site-db · dil-kalibrasyonu · secrets.`

Özeti T0 kaydından yerleştir (tahmin edilmez; test eşitliği sınar):
```bash
digest="$(sed -n 's/^image_digest=//p' docs/phases/06-site/b1-t0-olcumler.md)"
test -n "$digest" && python3 - "$digest" <<'PY'
import sys
path = ".github/workflows/ci.yml"
text = open(path, encoding="utf-8").read()
assert "@T0_IMAGE_DIGEST" in text
open(path, "w", encoding="utf-8").write(text.replace("T0_IMAGE_DIGEST", sys.argv[1]))
PY
grep -n "SITE_DB_IMAGE:" .github/workflows/ci.yml
```

- [ ] **Step 5: `site-db` adımı ve koşu kimliği** (`verify.sh`, üç düzenleme; eski metin Task 3 sonrası hâl)

```bash
# ESKİ
LOG="${TMPDIR:-/tmp}/football-edge-verify.log"
: > "$LOG"
FAILED=0
# YENİ
LOG="${TMPDIR:-/tmp}/football-edge-verify.log"
: > "$LOG"
FAILED=0

# Bu koşunun kimliği (Faz 6 İz B §12.1): `site-db` adımının uçtan uca anlık görüntüsü bununla
# etiketlenir; sitenin derleme adımı yalnız AYNI koşunun dosyasını kabul eder — önceki koşudan
# kalmış bayat bir anlık görüntüyle PASS yok.
FE_VERIFY_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM}"
export FE_VERIFY_RUN_ID
```
```bash
# ESKİ
step "sızıntı" bash -c '
  EXPECTED_MIN_LEAKAGE=418
# YENİ
# `sitedb` işaretli sızıntı testleri (holdout tohumları, bağımlılık kapanışı) `site-db` adımında
# koşar ve orada sayılır: her test kapıda tam bir kez koşar.
step "sızıntı" bash -c '
  EXPECTED_MIN_LEAKAGE=434
```
`sızıntı` adımının kapanış satırlarından (`  uv run pytest tests/ -q -m "leakage and not sitedb" --tb=short` ve
ardından gelen `'`) HEMEN SONRA, `dil-kalibrasyonu` yorumundan önce:
```bash

# Site okuma katmanı (Faz 6 İz B §4.4, §12.1, B10): 0014'ün kataloğu, davranışı ve uçtan uca dışa
# aktarım GERÇEK Postgres ister — atılabilir yerel kap (`SITE_TEST_DATABASE_URL`; yerelde
# `scripts/sandbox_db.sh`, CI'da iş içinde doğan kap). Değişken yoksa yerelde ADIYLA SKIP, `CI=true`
# iken FAIL: SKIP'in CI'da sessizce yeşil olması Vaka 1 desenidir. Uçtan uca test anlık görüntüyü
# `$SITE_E2E_DIR`e bu koşunun kimliğiyle bırakır; dizin önce BOŞALTILIR (dosyalar sıfırlanır,
# silinmez) ki önceki koşunun dosyası bu koşunun sanılmasın.
SITE_E2E_DIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e"
export SITE_E2E_DIR
mkdir -p "$SITE_E2E_DIR"
: > "$SITE_E2E_DIR/snapshot.json"
: > "$SITE_E2E_DIR/snapshot.sha256"
: > "$SITE_E2E_DIR/run-id"
if [ -n "${SITE_TEST_DATABASE_URL:-}" ]; then
  step "site-db" bash -c '
    EXPECTED_MIN_SITEDB=21

    collect_output=$(uv run pytest tests/ -q -m sitedb --collect-only 2>&1)
    collected=$(printf "%s" "$collect_output" | grep -oE "^[0-9]+/" | head -1 | tr -d "/")
    collected=${collected:-0}
    if [ "$collected" -lt "$EXPECTED_MIN_SITEDB" ]; then
      printf "%s\n" "$collect_output"
      echo "HATA: sitedb etiketli test sayısı ($collected) beklenen alt sınırın ($EXPECTED_MIN_SITEDB) altında"
      exit 1
    fi

    uv run pytest tests/ -q -m sitedb -rs --tb=short
  '
elif [ "${CI:-}" = "true" ]; then
  step "site-db" bash -c 'echo "HATA: CI=true ama site test veritabanı yok — site-db atlanamaz (B10)"; exit 1'
else
  # SKIP GEÇMEK DEĞİLDİR: adıyla yazılır, `zincir` adımı gibi.
  echo "SKIP: site-db (SITE_TEST_DATABASE_URL yok)" | tee -a "$LOG"
fi
```

- [ ] **Step 6: Sayıları ÖLÇ ve yaz** (ölçümden büyük sayı yazılmaz; bu planın ağacında 434 ve 21 ölçüldü)

```bash
leak="$(uv run pytest tests/ -q -m 'leakage and not sitedb' --collect-only 2>&1 | grep -oE '^[0-9]+/' | head -1 | tr -d /)"
site="$(uv run pytest tests/ -q -m sitedb --collect-only 2>&1 | grep -oE '^[0-9]+/' | head -1 | tr -d /)"
echo "leakage(not sitedb)=$leak sitedb=$site"
python3 - "$leak" "$site" <<'PY'
import re, sys
path = "verify.sh"
text = open(path, encoding="utf-8").read()
text = re.sub(r"EXPECTED_MIN_LEAKAGE=\d+", f"EXPECTED_MIN_LEAKAGE={sys.argv[1]}", text, count=1)
text = re.sub(r"EXPECTED_MIN_SITEDB=\d+", f"EXPECTED_MIN_SITEDB={sys.argv[2]}", text, count=1)
open(path, "w", encoding="utf-8").write(text)
PY
```
Expected: `sitedb=21` (18 görünüm + 3 uçtan uca). Farklıysa rapora nedeniyle yazılır.

- [ ] **Step 7: Belgeler**

`docs/RUNBOOK.md` §4'te "**Neden var.** …" paragrafının (son satırı "Vault hazır gelir).") HEMEN ALTINA:
```markdown

**CI'da (Faz 6 B-1 Task 9'dan beri):** `ci.yml`in "Site test veritabanı" adımı aynı imajla iş içinde bir kap kurar;
`SITE_TEST_DATABASE_URL` ve `SANDBOX_DATABASE_URL` onu gösterir. `sitedb` testleri `verify.sh`in `site-db` adımında,
0013'ün kum havuzu testleri `pytest` adımında koşar. `DATABASE_URL` verilmez: katalog testleri CI'da hâlâ adıyla
SKIP (DEFERRED 18a).
```
`docs/DEFERRED.md` 18a satırının açıklama hücresinde `**CI kum havuzu DB testlerini koşmuyor.**` ifadesinin ÖNÜNE şu
metin eklenir (satırın geri kalanı AYNEN kalır):
`**KISMEN KAPANDI (Faz 6 B-1 Task 9):** CI'da iş içi kap — kum havuzu ve \`sitedb\` testleri koşar; \`DATABASE_URL\`li katalog testleri SKIP kalır.`

`docs/phases/06-site/HANDOFF.md` oluştur:

`docs/phases/06-site/HANDOFF.md` (tam içerik):

````markdown
# Faz 6 İz B — HANDOFF (B-1: okuma katmanı)

Spec: `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md`. Plan: `docs/superpowers/plans/2026-09-24-faz6-iz-b-1-okuma-katmani.md`.
T0 ölçümleri: `docs/phases/06-site/b1-t0-olcumler.md` (ölçen komut `scripts/site_t0_probe.sh`).

## B-1'in kurduğu

- `db/migrations/0014_site_read.sql` — `site_reader` (NOLOGIN), `site`/`site_input`/`site_audit` görünümleri,
  `site.public_floor()`. **Canlıya UYGULANMADI.**
- `python -m football_edge.site export | verify-snapshot` — tek salt okuma işlemi, tam zincir, ikinci türetim.
- Kapı: `verify.sh` `site-db` adımı; CI'da iş içinde doğan `supabase/postgres` kabı (aynı kap 0013 kum havuzu
  testlerini de koşar).
- `.github/workflows/site.yml` — yalnız `workflow_dispatch`; secret'lar eklenmedi.

## Canlıya geçiş (kullanıcı onayı, §0.7 — bu dalga YAPMADI)

1. 0013 canlıda + advisors temiz (controller).
2. AK6 onayı → `0014` ROLLBACK'li prova → `apply_migration` (uygulayan rol `postgres` olmalı: görünüm sahibi = tablo
   sahibi, aksi hâlde RLS'li tablolar görünümden HATASIZ 0 satır döner — §4.2) → katalog testleri gerçek DB'ye karşı
   salt okuma kipinde.
3. RUNBOOK'a `site_reader` parola/`LOGIN` adımı: parola kullanıcı tarafından istemci tarafı SCRAM ile (`\password
   site_reader`); asistan parolayı görmez ve girmez (AK18).
4. Ölçülecek: Supavisor kullanıcı biçimi (`site_reader.<proje_ref>`) ve rol GUC'lerinin pooler üzerinden uygulandığı (§4.5).
5. Secret'lar: `SITE_DATABASE_URL`, `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID` (ayrı Netlify hesabı/ekibi — AK18).

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
10. `site.yml`in Node adımları (B-2) ve `netlify-cli` sürümü koşmadı; test yalnız secret sınırını, sırayı ve sürüm
    sabitlemesini ölçer.
11. Task 3–8 birleşmeleri arasında `sitedb` testleri CI'da koşmadı (Task 9'da başladı); o pencerede kanıt yereldir
    (görev raporları).
````

- [ ] **Step 8: Yeşili gör**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider tests/test_site_gate.py tests/test_gate_traceback.py tests/test_site_harness_rules.py tests/test_workflows.py tests/test_access_method_rule.py`
Expected: hepsi yeşil (`test_site_gate.py` 7, `test_gate_traceback.py` 2).

- [ ] **Step 9: Kapıyı üç koşulda koş ve ÇIKTIYI oku**

```bash
# (a) yerel, test DB'si yok → adıyla SKIP
TMPDIR=$(mktemp -d) ./verify.sh > "$TMPDIR/a.log" 2>&1; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$TMPDIR/a.log"
# (b) CI=true, test DB'si yok → site-db FAIL (B10 kanıtı; KAPI KIRMIZI beklenir)
TMPDIR=$(mktemp -d) CI=true ./verify.sh > "$TMPDIR/b.log" 2>&1; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$TMPDIR/b.log"
# (c) kum havuzu adresleri (DATABASE_URL VERİLMEZ — zincir adımı canlıyı aramasın)
scripts/sandbox_db.sh up
( eval "$(scripts/sandbox_db.sh env | grep -E '^export (SITE_TEST|SANDBOX)_DATABASE_URL=')"
  T=$(mktemp -d); start=$(date +%s); TMPDIR=$T ./verify.sh > "$T/c.log" 2>&1
  echo "süre_sn=$(( $(date +%s) - start ))"; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$T/c.log"
  wc -c "$T/site-e2e/snapshot.json" "$T/site-e2e/run-id"
  uv run python -m football_edge.site verify-snapshot "$T/site-e2e/snapshot.json" --sha256 "$T/site-e2e/snapshot.sha256" )
```
Expected: (a) `10 PASS` + `SKIP: site-db (SITE_TEST_DATABASE_URL yok)` + `SKIP: zincir` + `KAPI YEŞİL`;
(b) `FAIL: site-db` + `KAPI KIRMIZI`; (c) `11 PASS` (site-db dâhil) + `SKIP: zincir` + `KAPI YEŞİL`, `run-id` boş değil,
`snapshot.json` boş değil, `anlık görüntü geçerli: snapshot.json`. `süre_sn` rapora.

- [ ] **Step 10: Mutasyonla kırmızı kanıtı**

| Dosya | Eski → yeni | Kırmızı |
|---|---|---|
| `verify.sh` | `elif [ "${CI:-}" = "true" ]; then` bloğunun iki satırı → `` (else'e düşer: CI'da SKIP) | `test_site_db_is_red_in_ci_and_named_skip_locally_without_a_database` |
| `verify.sh` | `: > "$SITE_E2E_DIR/run-id"\n` → `` | `test_the_end_to_end_directory_is_emptied_before_the_step_without_deleting` |
| `.github/workflows/ci.yml` | `@sha256:` → `@sha256:0` (özet bozulur) | `test_the_ci_image_is_the_t0_pinned_image_with_its_digest` |
| `.github/workflows/ci.yml` | `-p 127.0.0.1:55432:5432` → `-p 55432:5432` | `test_the_site_database_is_local_and_its_password_is_generated_and_masked` |
| `verify.sh` | `uv run pytest tests/ -q -m sitedb -rs --tb=short` → `uv run pytest tests/ -q -m sitedb -rs` | `test_every_pytest_run_prints_no_local_variables[verify.sh-4]` (0013'ün traceback bekçisi) |

- [ ] **Step 11: `timeout-minutes`i ölç** — Step 9(c)'nin `süre_sn`i + CI koşusunun (Step 14) `gate` süresi okunur;
`timeout-minutes` = `max(20, ceil(2 × CI dakikası))`. 20'den farklıysa değer ve iki ölçüm commit mesajına yazılır.

- [ ] **Step 12: Lint ve tip** — `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`.

- [ ] **Step 13: Commit**

```bash
git add .github/workflows/ci.yml verify.sh tests/test_site_gate.py tests/test_gate_traceback.py \
  docs/RUNBOOK.md docs/DEFERRED.md docs/phases/06-site/HANDOFF.md
git commit -m "ci: site-db adımı — iş içi supabase/postgres kabı, koşu kimliği, sayılar ölçüldü (Faz 6 B-1 dalga sonu)

EXPECTED_MIN_LEAKAGE ve EXPECTED_MIN_SITEDB --collect-only ile ölçüldü. DEFERRED 18a kısmen kapandı.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 14: CI'da kanıt (controller)** — dal `git fetch origin && git merge --no-ff origin/main` + tam kapıdan sonra
push'lanır; CI koşusunun `verify-log` eserinde `PASS: site-db`, `pytest` adımının özetinde
`test_api_roles_lockdown_db.py`nin kum havuzu testlerinin GEÇTİĞİ (skipped değil) ve `SKIP: zincir` okunur. Kap
kalkmazsa (imaj çekme, 180 sn) adımın `docker logs` kuyruğu rapora. `main`e `--no-ff`.

#### B-1 → B-2 devri (Produces — B-2 yalnız bunlara dayanır)

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
- **Uçtan uca anlık görüntü:** `verify.sh` `site-db` adımı `${RUNNER_TEMP:-${TMPDIR:-/tmp}}/site-e2e/` altına
  `snapshot.json`, `snapshot.sha256`, `run-id` bırakır; `run-id` içeriği `verify.sh`in başta dışa verdiği
  `FE_VERIFY_RUN_ID`e eşittir (satır sonu yok). Adım başında üç dosya SIFIRLANIR; test DB'si yoksa dosyalar boş kalır →
  B-2'nin derleme adımı `run-id` ≠ `FE_VERIFY_RUN_ID` gördüğünde yerelde SKIP, `CI=true` iken FAIL (§12.1).
- **B-2'nin yükümlülükleri (B-1 yapmadı):** şema ↔ TS `Snapshot` tipi anahtar eşitliği pytest'i (Q23); `site.yml`in
  kaybolan-slug ve yayın sonrası kontrol adımları; Node adımlarını `verify.sh`in `site-db` adımından SONRA eklemek;
  `verify.sh`e eklenen her `uv run pytest` çağrısı `--tb=short` taşımalı (`tests/test_gate_traceback.py` sayımı
  güncellenir) ve `sitedb`i adıyla seçmeli/dışlamalı ya da `-m contract` olmalı
  (`test_the_gate_runs_sitedb_tests_only_where_it_names_them`); `site.yml`e dokunurken `test_site_workflow.py`nin
  secret sınırı ve sıra testleri yeşil kalmalı (adım `env`inde `secrets.*` yalnız dışa aktarım ve yayında).
  `web/fixtures/`e B-2'nin kendi fixture'larını eklemesi serbesttir (B-1'in testi kapsayıcı değil, varlık sınar).
  Not: dışa aktarımın `snapshot.sha256`i `sha256sum` biçimindedir (`<hex>  snapshot.json`); yayındaki
  `/data/snapshot.sha256`in biçimi B-2'nindir — §6.4/3f karşılaştırması ikisinin hex alanını kıyaslamalıdır.

---

## Kapının ölçmedikleri (bu plan)

Task 9'un `docs/phases/06-site/HANDOFF.md`sindeki on bir madde bu planın tam listesidir (spec §12.4'ün B-1'e düşen
kısmı + rereview4 m2'nin kara liste notu + `SET ROLE`/LOGIN farkı + Task 3–8 CI penceresi). Faz geçişi için
(qa-loop "Phase geçişi"): tüm görevler kapıdan geçti, critical/high bulgu yok ve bu liste yazıldı.

## Öz-inceleme (plan yazarı, 2026-09-24)

**1. Spec kapsamı (§15 Plan B-1):** T0 ölçümleri → Task 0 · `snapshot.schema.json` + sentetik fixture'lar + biçimleme
sözleşmesi → Task 1 · `0014` + metin/katalog/davranış testleri → Task 3 · `market/consensus.py` + `pre_prices` +
zincir okuyucusunun ayrılması + `lock_ledger` varsayım testi → Task 2 · dışa aktarıcı (tek işlem, tam zincir, alt
süreçte ikinci türetim) → Task 6, slug fonksiyonu → Task 4 · `verify-snapshot` + geçişli import bekçisi → Task 4 ve
Task 1 · şablonlu yalıtım → Task 3 · beklenen değerli uçtan uca kap testi (iki kurcalama) → Task 7 · `site.yml` + adım
ortamı testi + redaksiyon + `check_secrets.sh` → Task 8 ve Task 6 · dalga sonu birleştirmesi (`ci.yml` kabı, `site-db`,
`EXPECTED_MIN_LEAKAGE`) → Task 9. H1 a–g: a Task 3 (`closure`), b Task 3 (tohumlar) + Task 7, c Task 1 + Task 3,
d Task 6 (`görünüm tabandan eski bir maç`), e Task 4, f Task 1, g Task 9 (sayı ölçülerek). H2 b–c Task 1/4; H3 a–d
Task 1/2; H5 b–d Task 4/8; H6 (Python tarafı) Task 5. §4.2 üç bekçi: katalog Task 3, davranış Task 3, DB dışı Task 6.
§4.4/4 tetikleyici yasağı ve fixture yeri Task 3. §5.1/4 döküm diske/loga yok, çöken çocuk Task 6. §5.1/5 iki
mutasyon: (b) Task 5, (a) Task 6. §6.4/3d Task 5 + Task 6. rereview4 m1–m3 Task 3. Şema ↔ TS anahtar eşitliği
BİLİNÇLİ olarak B-2'ye devredildi (Q23).

**2. Yer tutucu taraması:** "TBD/TODO/sonra" yok. İki işaretçi (`T0_NETLIFY_CLI`, `T0_IMAGE_DIGEST`) yer tutucu değil,
T0 kaydından değer yerleştiren komutların hedefidir; kalırlarsa testler kırmızıdır (`test_the_netlify_cli_is_pinned_
to_the_t0_version`, `test_the_ci_image_is_the_t0_pinned_image_with_its_digest`). `EXPECTED_MIN_*` değerleri Task 9'da
ölçülür; bu planın ağacında ölçülen değerler (434, 21) yazılıdır.

**3. Tip ve ad tutarlılığı:** `run_export`, `derive_in_subprocess`, `other_hash_seed`, `devig_method`, `snapshot_errors`,
`content_sha256`, `iso_z`, `round_consensus`, `LEDGER_AUDIT_VIEW`, `_ledger_rows(..., relation=)`,
`_first_anchor_break(..., relation=)`, `site_db`/`site_db_each`/`site_cluster`/`full_sequence`, `export_dump`/
`export_inputs`, `anchored_repo` her görevde aynı imzayla anıldı; bütün kod blokları bir prova ağacında (bu planın
scratch dizini) ruff + mypy strict + pytest ile koşturuldu: DB'siz testler yeşil (`2445 passed`, `sitedb` 21 test
yerelde adıyla SKIP); DB'li testler ve SQL gerçek Postgres'te koşmadı — kanıtları Task 3, 7, 9'un kap adımlarıdır.

**4. Review Focus:** beş girdi, her birinin testi sahibi görevde (Task 5: 2 ve 5; Task 6: 1, 3, 4).
