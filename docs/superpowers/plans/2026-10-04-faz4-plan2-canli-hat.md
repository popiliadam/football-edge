# Faz 4 Plan 2 — Canlı Jev Sinyal Hattı — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Yedi RSS kaynağından (5 EN + 2 TR) gelen haber başlıkları, yalnız kalibre (üretim) dilinde ve
`ai-input=no` demeyen kaynaktan, iki saatte bir kademe 1 Jev kapı sorularıyla; salı/cuma gölge turunun
kararlarında taraf başına kademe 2 bataryasıyla (T2+T3+T4 = 30 soru) `jev_match_answers`e `real` satır
olarak yazılır; dondurulmuş küme başına seçim dilimi sayacı 900'e varışı basar. Ücret anahtarı yokken her
şey "Jev kapalı" diye yeşil koşar; ücreti açan tek commit kullanıcınındır.

**Architecture:** `collectors/news.py` kaynak başına akış listesi (yol + ölçülmüş içerik türü) ve
kaynak başına tazelik sınırıyla genel bir RSS bağdaştırıcısını yedi kaynağa bağlar; `features/news.py`
`load_news`i Jev'e giden TEK okuma yolu yapar ve robots `Content-Signal: ai-input=no` diyen kaynağı orada
düşürür. `features tier1` (`collect-news.yml`, `sync-news`ten hemen sonra) yalnız üretim dillerini, tur
başına çağrı tavanı (en yeni haber önce) ve parti başına commit'le sorar. `features tier2` (`shadow.yml`,
gölge + rapordan sonra) bu turun gölge satırlarının (varlık) taraflarını `config/faz4_live.yaml` dondurulmuş
kümesiyle sorar ve her taraf için bir DURUM İŞARETİ yazar (`side_status:<taraf>:<sonuç>`); `prompt_version` =
sha256(soru dosyası + küme dosyası); işletme ayarları (`config/faz4_ops.yaml`) hash'e girmez. `features
slice-status` dilimi küme başına `asked` işaretinden sayar; `features estimate` (Jev'siz, salt okuma) ve `features probe` (tek ücretli çağrı, cevap yazmaz)
Task 5'in ölçüm araçlarıdır. Jev arızası haber/gölge turunu kırmızı yapmaz: `jev-kademe1` /
`jev-kademe2` adlı ayrı alarm açar.

**Tech Stack:** Python 3.11 (uv, pytest, mypy `--strict`, ruff 100 sütun), psycopg 3, PyYAML,
defusedxml, protego, httpx (MockTransport), typesafe-sdk 0.7 (`system_one(..., model=)`), GitHub Actions
(bash `-e`), Postgres (Supabase; bu planda migration YOK).

**Spec:** docs/superpowers/specs/2026-10-04-faz4-plan2-canli-hat-design.md (R173–R187) · ana tasarım
docs/superpowers/specs/2026-09-23-faz4-jev-sinyal-design.md (R157–R172; burada yazılmayan her şey aynen)

## Global Constraints

Spec'ten (değerler aynen; her görevin gereksinimine örtük olarak dahildir):

- Tavan **25 $/ay** (`jev_budget.MONTHLY_CAP_USD = 25.0`, `EXIT_BUDGET = 16`); her Jev çağrısı `budgeted_jev`ten
  geçer (`tests/test_jev_spend_paths.py` AST kuralı); tahmin birimi ölçülene dek **0,01 $**
  (`ESTIMATE_USD_UNMEASURED`).
- Dil kapısı Jev'den ÖNCE (R178): kademe 1 ve 2 yalnız `config/languages.yaml`'da `production_enabled: true`
  VE raporu `production_ready()` geçen dillerin haberini sorar; eşikler **önceden bağlı**: `min_n = 100`,
  `min_accuracy = 0,85` (R182, I-11) — gevşetmek **kullanıcı durağı**.
- Saklanan yalnız **başlık + URL** (+ yayıncı zamanı); RSS `<description>` okunmaz, saklanmaz (R175).
- Kademe 1 ufku **`HORIZON` = 8 gün**, küme penceresi **72 saat** (`tier1.py`, değişmez).
- Kademe 2: maç kümesi bu turun gölge satırları (`model_predictions`, yalnız `(match_id, decided_at)`
  VARLIĞI, `decided_at ≥ now − 6 sa`; olasılık okunmaz — I-2, M-1); taraf başına TEK batarya **T2 + T3 + T4 = 9 + 9 + 12 = 30 soru**
  (ölçüldü: `load_questions` → 4/9/9/12); taraf kümesi ev = ev ∪ ikisi, deplasman = deplasman ∪ ikisi,
  `item_set_hash` taraf başına (M-4); kademe 1 kapıları yalnız `asked_at < decided_at` satırlarından (I-3);
  haberi olmayan taraf **sorulmaz**, özellikte ölçeğin `"none"` düzeyine atanır, `imputed` sayılır (I-1);
  yalnız `variant = "real"`; **`now − decided_at > 6 saat`** ise sormaz (M-2); cevaplanmış taraf yeniden
  sorulmaz (M-3). Her gölge tarafı için durum işareti (inceleme I5): `question_id = side_status:<taraf>:<sonuç>`,
  sonuç ∈ {`asked`, `no_news`, `stale`, `deferred`, `error`, `budget`, `outage`, `model_drift`}; "yok" ataması ve
  dilim sayacı bu işaretlerden türetilir; özellik okuyucusu `STATUS_PREFIX`i süzer.
- Dondurulmuş küme (R185) `config/faz4_live.yaml` YALNIZ seçim-anlamlı alanlar: `tier1_prompt_version`,
  `jev_model` (sabit; `latest` değil), `min_belongs`, `min_reliability`. Kademe 2 satırının `prompt_version`ı =
  `sha256(bytes(config/jev_questions.yaml) + bytes(config/faz4_live.yaml))` — **yeni migration yok** (0012'nin
  `^[0-9a-f]{64}$` kısıtına uyar); küme değişirse sayaç sıfırdan (küme başına) sayar. İşletme ayarları AYRI
  `config/faz4_ops.yaml`: `estimate_usd: {tier1, tier2}`, `max_sides_per_run`, `max_decision_age_hours: 6` —
  hash'e GİRMEZ. **Spec R185'ten bilinçli sapma** (spec "tahmin birimleri"ni kümeye sayıyor): birim fiyat ya da
  tavan düzeltmesi seçim dilimi sayacını sıfırlamasın (inceleme M4; spec'i controller günceller). Kademe 1 de
  aynı `jev_model`i kullanır (inceleme I8; `null` iken hesabın varsayılanı).
- Seçim dilimi hedefi **900** (dondurulmuş küme başına; R181); kullanıcı durağı eşikleri: aylık tahmin
  **> 20 $** ya da 900 tarihi **> 2027-06-30** (R184).
- Exit kodları adıyla: **0** tamam · **7** `EXIT_SOURCE_FAILED` (Jev kesintisi / kaynak) · **16** tavan ·
  **17** `EXIT_NO_JEV_KEY` ("Jev kapalı"; `JEV_ENABLED=1` iken kırmızı) · **25** `EXIT_FROZEN_SET` (YENİ:
  küme/işletme dosyası eksik ya da bozuk — kademe 1 ve 2 —, kademe 2 kümesi donmamış ya da dönen model
  kümedekinden farklı; 18–24 dolu, ölçüldü). Kademe 2'de hiç taraf cevaplanmadı ve hata var → 7 (inceleme I4).
- Workflow: `TYPESAFE_API_KEY` YALNIZ kademe 1/2 adımlarının `env`inde kabul edilir (I-4); ücret açan commit
  yalnız `TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}` ve `JEV_ENABLED: "1"` env satırlarını ekler,
  testlere dokunmaz (R177). Jev adımları turu kırmızı yapmaz; kendi alarm başlığı: `jev-kademe1`
  (`collect-news.yml`), `jev-kademe2` (`shadow.yml`) — **spec'ten bilinçli sapma:** spec tek `jev` anahtarı
  diyor; iki workflow aynı başlığı paylaşsa yeşil kademe 1 turu kırmızı kademe 2 alarmını kapatırdı.
- `fetch-news` exit 7 `sync-news` ve kademe 1'i durdurmaz, tur yine kırmızı biter (I-6, I-7).
- `shadow.yml` sırası: shadow → report → tier2 → slice-status (R186).
- Tur başına tavan + parti başına commit (I-8): kademe 1 `MAX_CALLS_PER_RUN = 40` çağrı, tavan altında EN YENİ
  haber önce (inceleme I6), `BATCH_SIZE = 10` haber/parti; kademe 2 `max_sides_per_run = 80`, taraf başına
  commit, sıra ev → deplasman.
- Kaynak başına tazelik (kontrolör ölçümü 2026-10-04): varsayılan 2 gün; `football-oranje` **7 gün** (en yeni
  öğe 3 gün önce, 10 öğe); `gffn` **4 gün** (10 öğe, günde ~1–3).

Proje süreci (HANDOFF/bellek; her görevde):

- **TAM KAPI** (her görevin SON adımı; sonuç LOG DOSYASINDAN okunur):
  ```bash
  PATH=$HOME/.nvm/versions/node/v24.21.0/bin:$PATH; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T PYTHONDONTWRITEBYTECODE=1 ./verify.sh > "$T/verify.log" 2>&1; grep -E "^(PASS|FAIL|SKIP)|KAPI" "$T/verify.log"
  ```
  Beklenen: hiç `FAIL:` yok; adıyla SKIP'ler (`site-db`, `site-derleme/e2e`, `zincir`); son satır `KAPI YEŞİL`.
  Kırmızıysa `$T/verify.log`un ilgili `=== adım ===` bölümü okunur; kapı gevşetilmez, düzeltme yeni commit'tir.
- Python: `PYTHONDONTWRITEBYTECODE=1 uv run pytest …`, `uv run mypy src scripts`, `uv run ruff check src tests scripts`,
  commit'ten önce `uv run ruff format src tests scripts`.
- **MUTASYON KALIBI** (her "Mutasyon kanıtı" adımı; `PYTHONDONTWRITEBYTECODE=1` ZORUNLU — aynı boyutlu düzenleme
  bayat `.pyc`yi geçerli bırakır, bellek `mutation-proof-stale-pyc`):
  ```bash
  F=<dosya>; B=$(mktemp -d); cp "$F" "$B/orig"
  PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" '<OLD>' '<NEW>'
  PYTHONDONTWRITEBYTECODE=1 uv run pytest <test> -q; echo "exit=$?"
  cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
  ```
  Beklenen her mutasyonda `exit=1`, adı geçen test kırmızı, `GERI-KONDU`. `rm`, `git checkout -- <yol>`,
  `git restore` KULLANILMAZ.
- Satır numaraları YAKLAŞIKTIR (taban `0c060f7`); esas olan metin çapasıdır.
- Immutability: paylaşılan/girdi objesi mutate edilmez (yerel liste/sözlük doldurmak serbest). Fonksiyonlar < 50 satır.
- Testler gerçek yayıncı içeriği GÖMMEZ: RSS gövdeleri sentetik, uydurma başlıklı, küçük. Kapının secrets adımı
  testleri de tarar: secret adı parçalardan kurulur (`"TYPESAFE" + "_API_KEY"`, `"DATABASE" + "_URL"`);
  `AD=değer` biçimi yazılmaz.
- `git add` dosya ADIYLA. Commit: `<type>: <açıklama>` (feat, fix, refactor, docs, test, chore, perf, ci), boş
  satır, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Commit'ten SONRA tam kapı (bellek
  `full-gate-every-commit`).
- Canlı DB, `.env`, ağ, ücretli çağrı: implementer görevlerinde YOK. Yalnız controller görevleri (0, 5, 6)
  ağa/DB'ye çıkar ve her ücretli adım adıyla işaretlidir.
- Holdout AÇILMAZ; `features/` `live.store`, `history.holdout`, `history.sync`, `backtest.final_eval` import
  edemez (`tests/test_feature_import_rule.py`) — gölge strateji adları `tier2.SHADOW_STRATEGIES`te yazılır,
  eşitliği testle sabitlenir.
- Görev K1 incelemesi kabuk taşıyan `general-purpose` bir inceleyiciye verilir (mutasyon koşturabilmeli;
  bellek `reviewer-needs-shell`).

## Review Focus

Spec'in ima ettiği ama görev testlerinin kendiliğinden kapsamayacağı, kullanıcıyı en olası ısıracak beş girdi;
her birinin testi sahibi görevin adımındadır:

1. **Kalibre olmayan dilin (EN) başlığı Jev'e KÜME ADAYI olarak sızar.** Kademe 1 yalnız sorulacak haberi
   süzseydi, aynı takımı anan EN haber `earlier_news`te başlığıyla Jev'e giderdi. Pencere sorgudan hemen sonra
   dille süzülür (Task 2, `test_a_non_production_language_item_never_reaches_jev_even_as_earlier_news`);
   kademe 2'de aynısı (Task 3, `test_news_in_a_non_production_language_is_not_in_a_side_set`). `ai-input=no`
   kaynağı `load_news`te düşer (Task 1, `test_load_news_drops_a_source_whose_robots_denies_ai_input`).
2. **Karar anında ya da sonrasında sorulmuş kademe 1 cevabı kademe 2 kapısına girer.** Gölge turu 12:35'te,
   kademe 1 iki saatte bir koşar; aynı dakikada sorulan cevap karara yetişmiş sayılamaz (tam eşit an
   DIŞARIDA). `gates_as_of` satırları `asked_at < decided_at` ile süzer (Task 3,
   `test_gates_use_only_tier1_answers_asked_before_the_decision`, mutasyon `<` → `<=`); karardan sonra cevaplanan
   bir küme bağı da haberleri birleştiremez (`test_a_cluster_link_answered_after_the_decision_does_not_merge_side_news`,
   mutasyon `gates_as_of` → `gates_from`).
3. **Gölge turu elle yeniden koşulur** (aynı gün ikinci kez, ya da ertesi gün): cevaplanmış taraf yeniden
   satın alınmaz (M-3, `test_an_answered_side_is_not_asked_again_nor_marked_again` +
   `test_a_second_tier2_run_buys_nothing_again`); yalnız `asked` işareti tarafı kapatır, `error`/`budget` işareti
   kapatmaz (`test_match_answers_are_written_once_and_only_asked_markers_close_a_side`); karar anından 6 saat
   sonra hiç sorulmaz (M-2, `test_a_decision_older_than_six_hours_is_not_asked`, sınır 6 sa dahil / 6 sa + 1 sn
   hariç; yükleme sınırı aynı, M1).
4. **Boş ya da yanlış adlı secret ile ücret açılır** (`JEV_ENABLED=1`, `TYPESAFE_API_KEY` boş): komut 17
   döner; anahtarsız dönemde yeşil "Jev kapalı" olan 17 burada `jev-kademe1/2` alarmını açmalı (I-5).
   (Task 2, `test_the_tier1_step_never_turns_the_news_run_red_and_names_every_jev_outcome[enabled-17]`;
   Task 3 aynısı kademe 2 için.)
5. **Düşük hacimli ya da `+0300` damgalı akış:** Football Oranje'nin en yeni öğesi 3 gün önce — 2 günlük
   sınır her sakin turda exit 7 ve alarm gürültüsü verirdi; Fotomaç/A Spor `+0300` damgası saat dilimi
   yanlış okunursa öğe "gelecekte" görünür ve `assert_fresh` kaynağı kırmızı yapar. (Task 1,
   `test_low_volume_feeds_have_their_own_freshness_window`, `*_beyond_its_own_window_is_red`,
   `test_a_plus_three_hour_feed_is_not_future_dated_at_collection`, saat dilimi parametreleri.)

**Kapının ölçmedikleri (bu plan; Task 6 faz HANDOFF'una yazar, spec §4'e ek):** (a) yayıncının `pubDate`
iddiası ve RSS'in gerçekten futbol haberi taşıdığı (lig dağılımı) ölçülmez; (b) robots anlık görüntüsü
yalnız `sources-audit.yml`'ın günlük canlı turunda tazelenir — `Content-Signal` sonradan `ai-input=no`'ya
dönerse `load_news` ancak anlık görüntü güncellenince keser; (c) kademe 1 parti sınırında bölünen bir Jev
kesinti serisi en çok `OUTAGE_STREAK − 1` ek çağrı ve işarete mal olur (seri parti içinde sayılır);
(d) kademe 2 taraf kümesinde küme temsilcisi `select_items`in en erken haberidir — aynı kümenin farklı
taraflı sonraki haberi kümeye girmez; (e) `features estimate` kademe 2 için ÜST SINIR verir (kademe 1
kapısı yokken takım adı geçen her haber); (f) `features probe` cevabı hiçbir tabloya yazılmaz, yalnız
harcama defterine; (g) birim fiyat SDK'dan okunamaz (kullanıcı TypeSafe panelinden okur); (h)
`jev-kademe1/2` alarmlarının canlıda açılıp kapandığı yalnız ilk ücretli turlarda görülür; (i) tier2'nin
gerçek gecikmesi `max_sides_per_run = 80` × gecikme < `shadow.yml` zaman aşımı varsayımına dayanır — Task 5
ölçer; (j) Jev'e verilen başlama saati (`kickoff`) kademe 2 koşu anında `matches`ten okunur — karar ile koşu
arasında ertelenen maçta Jev yeni saati görür (inceleme M5; karar anının saati saklanmaz); (k) kademe 1 tavanı
taşan eski haber sonraki turda sorulur ama o arada bir karar anı geçtiyse o karara yetişmez (en yeni önce
seçiminin bedeli, I6); (l) `side_status` işaretinin `no_news` sonucu karar anındaki dil kümesine göredir — sonra
açılan bir dil (EN) geçmiş kararları değiştirmez.

---

## Dosya yapısı ve dalgalar

| Dosya | Görev | Sorumluluk |
|---|---|---|
| `config/robots/{sportsmole,independent,standard,gffn,football-oranje,fotomac,aspor}.txt` | Yeni (T1 Step 0, controller) | Kontrolörün 2026-10-04 proje UA'sıyla aldığı robots anlık görüntüleri |
| `config/sources.yaml` | Değişir (T1) | Yedi `enabled: true` kayıt, `robots_verified_at: 2026-10-04`, Content-Signal notu |
| `src/football_edge/collectors/news.py` | Değişir (T1) | `RssAdapter`, `RSS_SOURCES`, `Feed`, `_ARTICLE_PATHS` → akış demeti, `_MAX_AGE`, `_fetch_items`, `_collect_source` |
| `src/football_edge/features/news.py` | Değişir (T1) | `NEWS_SOURCE_LANGS` 8 kaynak, `ROBOTS_DIR`, `ai_input_denied`, `jev_blocked_sources`, `load_news` süzgeci |
| `tests/test_news.py`, `tests/test_feature_news.py`, `tests/test_sources.py` | Değişir (T1) | RSS/akış/tazelik/saat dilimi; ai-input süzgeci; `Feed` yolları beyanlı |
| `src/football_edge/calibration.py` | Değişir (T2) | `production_languages` |
| `src/football_edge/features/tier1.py` | Değişir (T2) | `max_calls`, `Tier1Run.calls/deferred`, `batches`, `newest_within_cap`, `merge_runs`, `EMPTY_RUN`, `MAX_CALLS_PER_RUN`, `BATCH_SIZE` |
| `src/football_edge/features/__main__.py` | Değişir (T2 → T3 → T4, SIRALI) | tier1 dil kapısı + partiler; tier2; slice-status, estimate, probe |
| `.github/workflows/collect-news.yml` | Değişir (T2 → T3, SIRALI) | `id`ler, `fetch` çıktısı, sync/tier1 `if:`, tier1 adımı, `jev-kademe1` alarmı, zaman aşımı 20 dk; T3: `25)` kolu |
| `tests/jev_workflow_helpers.py`, `tests/test_tier1_workflow.py` | Yeni (T2; helpers T3'te `JEV_CASES`e 25) | Jev adımı koşturucu + kademe 1 workflow testleri |
| `tests/test_feature_tier1.py`, `tests/test_calibration.py`, `tests/test_collect_workflows.py`, `tests/test_news_sync_workflow.py`, `tests/test_workflows.py` | Değişir (T2; `test_feature_tier1.py` T3'te taklitler + iki test) | Kademe 1 dil/tavan/parti/en yeni önce; üretim dili; secret yolları; sync `if:`; Jev alarm kapatmanın toleransı |
| `config/faz4_live.yaml`, `config/faz4_ops.yaml`, `src/football_edge/features/live_config.py` | Yeni (T3) | Dondurulmuş küme (hash'li) + işletme ayarları (hash'siz) + yükleyici, `EXIT_FROZEN_SET = 25` |
| `src/football_edge/features/derive.py` | Değişir (T3) | `LEVEL_SCORES`, `level_answer`, `IMPUTED`, `side_answers` (I-1) |
| `src/football_edge/features/tier2.py`, `tests/fake_tier2_db.py`, `tests/test_feature_tier2.py`, `tests/test_feature_live_config.py` | Yeni (T3; `fake_tier2_db.py` T4'te büyür) | Kademe 2 koşucusu, taraf durum işaretleri, sorgular, yazıcı; taklit DB; testler |
| `src/football_edge/jev.py`, `src/football_edge/jev_budget.py` | Değişir (T3) | `TypeSafeJev(model=)`; `budgeted_jev(estimate_usd=)` |
| `tests/test_jev.py`, `tests/test_jev_budget.py`, `tests/test_jev_item_answers_readers.py`, `tests/test_feature_derive.py` | Değişir (T3) | model argümanı; tahmin birimi + exit 25 sahipliği; yeni okuyucu; "yok" ataması |
| `.github/workflows/shadow.yml`, `tests/test_shadow_workflow.py`, `verify.sh` | Değişir (T3 → T4, SIRALI) | tier2 + `jev-kademe2` alarmı; slice-status; `EXPECTED_MIN_LEAKAGE` |
| `src/football_edge/features/{slice,estimate,probe}.py`, `tests/test_feature_{slice,estimate,probe}.py` | Yeni (T4) | Sayaç, kuru koşu, tek çağrı ölçümü |
| `docs/superpowers/specs/2026-09-23-faz4-olcumler.md` | Değişir (T5, T6 — controller) | Kuru koşu, gecikme/model, birim fiyat, TR kalibrasyonu |
| `config/languages.yaml`, `data/calibration/tr.report.json` | Değişir (T6 — controller) | TR üretime (yalnız geçerse) |
| `docs/superpowers/plans/2026-10-04-faz4-plan2-ucret-yamasi.patch` | Yeni (T6 — controller) | Ücret yaması (kullanıcı commit'i) |

**Dalgalar ve tek-yazar taraması:** **Dalga A: Task 1 ∥ Task 2** — dosya kümeleri ayrık (ölçüldü: T1 yalnız
`collectors/news.py`, `features/news.py`, `config/sources.yaml`, `config/robots/*`, `tests/test_news.py`,
`tests/test_feature_news.py`, `tests/test_sources.py`; T2 yalnız yukarıdaki T2 satırları). T2'nin CLI testleri
`load_news`i (T1 dosyası) değiştirmeden çağırır ve depodaki `config/robots/ajansspor.txt`'ye (`ai-input=yes`)
dayanır — iki dal birleşince davranış aynı. Ayrı worktree; birleştirme sırası T1, sonra T2. **Dalga B: Task 3**
(T2'nin `__main__.py`, `test_feature_tier1.py`, `collect-news.yml` ve `tests/jev_workflow_helpers.py` dosyalarına
yazar — T2 birleşmeden başlamaz).
**Dalga C: Task 4** (T3'ün `__main__.py`, `shadow.yml`, `fake_tier2_db.py`, `test_shadow_workflow.py`,
`verify.sh` dosyalarına yazar — sıralı). **Dalga D: Task 5 → Task 6** (controller; T6, T5'in maliyet ölçümü
olmadan başlamaz).

---

### Task 1: RSS kaynakları — akış listesi, içerik türü, kaynak başına tazelik, ai-input süzgeci

**Kademe:** K2

**Files:**
- Create: `config/robots/{sportsmole,independent,standard,gffn,football-oranje,fotomac,aspor}.txt` (Step 0, controller)
- Modify: `config/sources.yaml` (ajansspor kaydından sonra, ~satır 113; yedi kayıt)
- Modify: `src/football_edge/collectors/news.py:1-20` (import), `:190-196` (GoogleNewsAdapter sonrası), `:360-363` (`_ADAPTERS`), `:375-489` (`_ARTICLE_PATHS`, `collect_news`)
- Modify: `src/football_edge/features/news.py:11-36` (import, sabitler), `:206-225` (`load_news`)
- Test: `tests/test_news.py` (590-640 arası iki `monkeypatch.setitem`; sona yeni testler), `tests/test_feature_news.py` (sona), `tests/test_sources.py:442`

**Interfaces:**
- Consumes: `collector.fetch_text(client, source, path, parser, *, expect: str) -> str`;
  `collector.assert_fresh(observations, now, *, max_age, source_id) -> None`;
  `sources.robots_for(source, robots_dir) -> Protego`; `observations.write_observations(conn, obs) -> int`.
- Produces: `collectors.news.RSS_SOURCES: tuple[str, ...]`;
  `@dataclass(frozen=True) class RssAdapter(source_id: str)` (`parse(body, *, now) -> tuple[NewsItem, ...]`);
  `@dataclass(frozen=True) class Feed(path: str, content_type: str)`;
  `collectors.news._ARTICLE_PATHS: dict[str, tuple[Feed, ...]]`; `_MAX_AGE: Mapping[str, timedelta]`;
  `features.news.NEWS_SOURCE_LANGS` (8 kaynak); `features.news.ROBOTS_DIR = Path("config/robots")`;
  `features.news.ai_input_denied(robots_text: str) -> bool`;
  `features.news.jev_blocked_sources(robots_dir: Path = ROBOTS_DIR) -> frozenset[str]`;
  `features.news.load_news(conn, *, since: datetime, robots_dir: Path = ROBOTS_DIR) -> tuple[StoredNews, ...]`
  (imza geriye uyumlu; T2/T3/T4 değiştirmeden çağırır).

**Karar — `ai-input=no` nerede kesilir:** `load_news`te (Jev'e giden TEK okuma yolu: kademe 1, kademe 2, probe,
estimate). `sync-news`te kesmek sonradan `no`ya dönen kaynağın DEPODAKİ eski satırlarını açık bırakırdı;
`load_news` her okumada GÜNCEL anlık görüntüye bakar. Yalnız AÇIK `no` keser (spec §4/9; EN beş kaynakta
`Content-Signal` satırı yok — "belirtilmemiş" `no` değildir). Anlık görüntüsü OLMAYAN canlı kaynak da kesilir
(ölçülmemiş = izin yok). `NEWS_SOURCE_LANGS` dışındaki (arşiv) kaynak süzülmez.

- [ ] **Step 0 (CONTROLLER, implementer'dan ÖNCE): robots anlık görüntülerini yerleştir ve doğrula**

Kontrolör yedi robots.txt'yi 2026-10-04'te proje kimliğiyle (`football-edge/0.1 (+https://github.com/popiliadam/football-edge)`)
birer istekle ZATEN aldı; hepsi 200. Yeniden çekilmez — kopyalanır:

```bash
S=/private/tmp/claude-501/-Users-apple-dev-football-edge/f62a1769-203e-499b-85b7-a34d1672663a/scratchpad/robots; for id in sportsmole independent standard gffn football-oranje fotomac aspor; do cp "$S/$id.txt" "config/robots/$id.txt"; done; ls -l config/robots/
```

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
from pathlib import Path
from protego import Protego
UA = "football-edge/0.1 (+https://github.com/popiliadam/football-edge)"
FEEDS = {
    "sportsmole": ("https://www.sportsmole.co.uk", "/football/rss.xml"),
    "independent": ("https://www.independent.co.uk", "/sport/football/rss"),
    "standard": ("https://www.standard.co.uk", "/sport/football/rss"),
    "gffn": ("https://www.getfootballnewsfrance.com", "/feed/"),
    "football-oranje": ("https://www.football-oranje.com", "/feed/"),
    "fotomac": ("https://www.fotomac.com.tr", "/rss/news.xml"),
    "aspor": ("https://www.aspor.com.tr", "/rss/futbol.xml"),
}
for sid, (base, path) in FEEDS.items():
    text = Path(f"config/robots/{sid}.txt").read_text(encoding="utf-8")
    signal = [line.strip() for line in text.splitlines() if line.lower().startswith("content-signal")]
    allowed = Protego.parse(text).can_fetch(url=base + path, user_agent=UA)
    print(f"{sid:16} izinli={allowed} signal={signal or 'YOK'}")
    assert allowed, sid
PY
```
Expected (kontrolörde ölçüldü): yedisinde `izinli=True`; `fotomac` ve `aspor` `signal=['Content-Signal: search=yes, ai-input=yes, ai-train=no']`;
EN beşinde `signal=YOK`. Dosyalar implementer'ın worktree'sine bu adımın commit'iyle girer:

```bash
git add config/robots/sportsmole.txt config/robots/independent.txt config/robots/standard.txt config/robots/gffn.txt config/robots/football-oranje.txt config/robots/fotomac.txt config/robots/aspor.txt
git commit -F - <<'EOF'
chore: yedi RSS kaynağının robots anlık görüntüsü (2026-10-04, proje UA)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```
(`kaynak-politikası` adımı yalnız `enabled` kaynakları denetler; kayıtlar Step 5'te açılınca anlık görüntüler
hazırdır. Bu commit tek başına kapıyı değiştirmez.)

- [ ] **Step 1: Başarısız testleri yaz — `tests/test_news.py` sonuna**

Önce dosyanın import bloğunu genişlet (`from football_edge.collectors.news import (...)` listesine `RSS_SOURCES`,
`Feed`, `RssAdapter` eklenir) ve 590–640 arasındaki iki `monkeypatch.setitem(news_module._ARTICLE_PATHS, "googlenews", "/rss/search?q=Galatasaray&hl=tr&gl=TR&ceid=TR:tr")`
çağrısının değerini `(Feed("/rss/search?q=Galatasaray&hl=tr&gl=TR&ceid=TR:tr", "application/xml"),)` yap (ikisi de).
Sonra sona ekle:

```python
# ---------------------------------------------------------------------------
# Plan 2 Task 1 — yedi RSS kaynağı. Gövdeler SENTETİK (uydurma başlık, `*.test` alanları);
# içerik türleri ve tazelik pencereleri kontrolörün 2026-10-04 ölçümüdür.
# ---------------------------------------------------------------------------

OCT3 = datetime(2026, 10, 3, 11, 30, tzinfo=UTC)
MEASURED_FEEDS = {
    "sportsmole": (Feed("/football/rss.xml", "application/xml"),),
    "independent": (Feed("/sport/football/rss", "text/xml"),),
    "standard": (Feed("/sport/football/rss", "text/xml"),),
    "gffn": (Feed("/feed/", "application/rss+xml"),),
    "football-oranje": (Feed("/feed/", "application/rss+xml"),),
    "fotomac": (Feed("/rss/news.xml", "text/xml"),),
    "aspor": (Feed("/rss/futbol.xml", "application/xml"),),
}


def _synthetic_rss(entries: list[tuple[str, str | None]], host: str) -> str:
    """`entries`: (kısa ad, RFC 2822 pubDate ya da None). Özet (`description`) KASITLI var."""
    items = "".join(
        f"<item><title>Uydurma başlık {slug}</title><link>https://{host}/{slug}</link>"
        + (f"<pubDate>{pub_date}</pubDate>" if pub_date else "")
        + f"<description>Uydurma özet {slug}</description></item>"
        for slug, pub_date in entries
    )
    return f"<rss version='2.0'><channel><title>sentetik</title>{items}</channel></rss>"


def _rss_sources_yaml(tmp_path: Path, ids: tuple[str, ...]) -> Path:
    blocks = "".join(
        f"""
  - id: {sid}
    base_url: https://{sid}.test
    user_agent: football-edge-test/0.1
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-10-03
    declared_paths: ['{MEASURED_FEEDS[sid][0].path}']
    enabled: true
    access_basis: robots
    terms_url: ''
    note: ''
"""
        for sid in ids
    )
    path = tmp_path / "sources.yaml"
    path.write_text("sources:" + blocks, encoding="utf-8")
    for sid in ids:
        write_robots(tmp_path, sid, "")
    return path


def _typed_handler(bodies: dict[str, tuple[str, str]], seen: list[str] | None = None) -> object:
    """host → (gövde, content-type). `seen` her isteğin URL'sini toplar."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(str(request.url))
        for host, (body, content_type) in bodies.items():
            if host in str(request.url):
                return httpx.Response(200, text=body, headers={"content-type": content_type})
        return httpx.Response(404, text="not found")

    return handler


def _collect(tmp_path: Path, ids: tuple[str, ...], bodies: dict[str, tuple[str, str]]) -> Any:
    client = httpx.Client(transport=httpx.MockTransport(_typed_handler(bodies)))  # type: ignore[arg-type]
    return collect_news(
        FakeObservationDb(),  # type: ignore[arg-type]
        client,
        sources_path=_rss_sources_yaml(tmp_path, ids),
        robots_dir=tmp_path,
        now=OCT3,
    )


def _rfc(when: datetime) -> str:
    return when.strftime("%a, %d %b %Y %H:%M:%S +0000")


def test_every_rss_source_is_registered_with_its_measured_feed_and_content_type() -> None:
    assert set(RSS_SOURCES) == set(MEASURED_FEEDS)
    assert {sid: news_module._ARTICLE_PATHS[sid] for sid in RSS_SOURCES} == MEASURED_FEEDS
    registry = load_sources(Path("config/sources.yaml"))
    adapters = {adapter.source_id: adapter for adapter in enabled_adapters(registry)}
    assert all(isinstance(adapters[sid], RssAdapter) for sid in RSS_SOURCES)


def test_rss_adapter_keeps_title_link_and_date_but_never_the_summary() -> None:
    body = _synthetic_rss([("a", "Sat, 03 Oct 2026 10:00:00 GMT")], "fotomac.test")

    (item,) = RssAdapter("fotomac").parse(body, now=OCT3)

    assert (item.title, item.url, item.source_id) == (
        "Uydurma başlık a",
        "https://fotomac.test/a",
        "fotomac",
    )
    assert set(news_observation(item).payload) == {"title", "url", "published_at", "source_id"}
    assert "Uydurma özet" not in str(news_observation(item).payload)


@pytest.mark.parametrize(
    "pub_date",
    [
        "Sat, 03 Oct 2026 14:00:00 +0300",
        "Sat, 03 Oct 2026 12:00:00 +0100",
        "Sat, 03 Oct 2026 11:00:00 GMT",
        "Sat, 03 Oct 2026 11:00:00 +0000",
    ],
)
def test_rss_pubdate_offsets_are_converted_to_the_same_utc_instant(pub_date: str) -> None:
    body = _synthetic_rss([("a", pub_date)], "aspor.test")

    (item,) = RssAdapter("aspor").parse(body, now=OCT3)

    assert item.published_at == datetime(2026, 10, 3, 11, 0, tzinfo=UTC)
    assert item.published_at.tzinfo is UTC
    assert item.published_at_is_source_provided is True


def test_a_plus_three_hour_feed_is_not_future_dated_at_collection(tmp_path: Path) -> None:
    """11:20 UTC = 14:20 +0300. Saat dilimi atılsaydı öğe 14:20 UTC, yani `now`dan (11:30) SONRA
    olurdu ve `assert_fresh` kaynağı "gelecekte" diye kırmızı yapardı."""
    body = _synthetic_rss([("taze", "Sat, 03 Oct 2026 14:20:00 +0300")], "fotomac.test")

    result = _collect(tmp_path, ("fotomac",), {"fotomac.test": (body, "text/xml")})

    assert result == NewsCollectResult(written=1, self_stamped=0, failed_sources=())


def test_each_feed_is_fetched_with_its_own_measured_content_type(tmp_path: Path) -> None:
    fresh = _rfc(OCT3 - timedelta(hours=1))
    ids = ("independent", "gffn")
    right = {
        "independent.test": (_synthetic_rss([("i", fresh)], "independent.test"), "text/xml"),
        "gffn.test": (_synthetic_rss([("g", fresh)], "gffn.test"), "application/rss+xml"),
    }

    assert _collect(tmp_path, ids, right).failed_sources == ()

    wrong = {**right, "independent.test": (right["independent.test"][0], "application/xml")}
    assert _collect(tmp_path, ids, wrong).failed_sources == ("independent",)


@pytest.mark.parametrize(
    ("source_id", "age"),
    [
        ("football-oranje", timedelta(days=5)),
        ("gffn", timedelta(days=3)),
        ("sportsmole", timedelta(days=1, hours=20)),
    ],
)
def test_low_volume_feeds_have_their_own_freshness_window(
    tmp_path: Path, source_id: str, age: timedelta
) -> None:
    feed = MEASURED_FEEDS[source_id][0]
    body = _synthetic_rss([("eski", _rfc(OCT3 - age))], f"{source_id}.test")

    result = _collect(tmp_path, (source_id,), {f"{source_id}.test": (body, feed.content_type)})

    assert result.failed_sources == (), f"{source_id} {age} yaşındaki öğeyle kırmızı"


@pytest.mark.parametrize(
    ("source_id", "age"),
    [
        ("football-oranje", timedelta(days=7, hours=1)),
        ("gffn", timedelta(days=4, hours=1)),
        ("sportsmole", timedelta(days=3)),
    ],
)
def test_a_feed_beyond_its_own_window_is_red(tmp_path: Path, source_id: str, age: timedelta) -> None:
    feed = MEASURED_FEEDS[source_id][0]
    body = _synthetic_rss([("bayat", _rfc(OCT3 - age))], f"{source_id}.test")

    result = _collect(tmp_path, (source_id,), {f"{source_id}.test": (body, feed.content_type)})

    assert result.failed_sources == (source_id,)


def test_a_url_seen_in_two_feeds_of_a_source_is_written_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        news_module._ARTICLE_PATHS,
        "sportsmole",
        (Feed("/football/rss.xml", "application/xml"), Feed("/premier-league/rss.xml", "application/xml")),
    )
    body = _synthetic_rss([("ortak", _rfc(OCT3 - timedelta(hours=1)))], "sportsmole.test")
    seen: list[str] = []
    client = httpx.Client(
        transport=httpx.MockTransport(  # type: ignore[arg-type]
            _typed_handler({"sportsmole.test": (body, "application/xml")}, seen)
        )
    )
    db = FakeObservationDb()

    result = collect_news(
        db,  # type: ignore[arg-type]
        client,
        sources_path=_rss_sources_yaml(tmp_path, ("sportsmole",)),
        robots_dir=tmp_path,
        now=OCT3,
    )

    assert len(seen) == 2, "iki akış da istenmeli"
    assert result.written == 1 and len(db.rows) == 1
```

`from typing import Any` dosyanın import bloğuna eklenir. (`_rss_sources_yaml` `declared_paths`e akış yolunu
yazar ama `/premier-league/rss.xml`yi yazmaz; testte `robots` boş olduğu için `guard_path` izin verir — R7
denetimi gerçek kayıt defteri için `tests/test_sources.py`te.)

- [ ] **Step 2: Başarısız testleri yaz — `tests/test_feature_news.py` sonuna ve `tests/test_sources.py:442`**

`tests/test_feature_news.py` import bloğuna: `from pathlib import Path`, `from football_edge import collect`,
`from football_edge.collectors.news import RSS_SOURCES`, ve `features.news`tan `NEWS_SOURCE_LANGS`,
`ROBOTS_DIR`, `ai_input_denied`, `jev_blocked_sources`. Sona:

```python
REPO = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("robots", "denied"),
    [
        ("User-agent: *\nContent-Signal: search=yes, ai-input=no, ai-train=no\n", True),
        ("User-agent: *\nContent-Signal: ai-train=no, search=yes, ai-input=yes\n", False),
        ("User-agent: *\nDisallow:\n", False),
        ("user-agent: *\ncontent-signal: AI-INPUT = No\n", True),
        ("User-agent: *\nContent-Signal: ai-train=no\n", False),
    ],
)
def test_only_an_explicit_ai_input_no_denies_jev(robots: str, denied: bool) -> None:
    assert ai_input_denied(robots) is denied


def _snapshots(tmp_path: Path, **overrides: str) -> Path:
    for source_id in NEWS_SOURCE_LANGS:
        (tmp_path / f"{source_id}.txt").write_text(
            overrides.get(source_id, "User-agent: *\nDisallow:\n"), encoding="utf-8"
        )
    return tmp_path


def test_load_news_drops_a_source_whose_robots_denies_ai_input(tmp_path: Path) -> None:
    robots = _snapshots(tmp_path, fotomac="User-agent: *\nContent-Signal: ai-input=no\n")
    db = FakeNewsDb(now=T0)
    db.observe("ajansspor", T0, _payload())
    db.observe("fotomac", T0, _payload(title="Uydurma Fotomaç başlığı", url="https://fotomac.test/1"))
    sync_news(db)  # type: ignore[arg-type]

    found = load_news(db, since=T0, robots_dir=robots)  # type: ignore[arg-type]

    assert [item.source_id for item in found] == ["ajansspor"]


def test_a_live_source_without_a_robots_snapshot_is_blocked(tmp_path: Path) -> None:
    robots = _snapshots(tmp_path)
    (robots / "aspor.txt").rename(robots / "aspor.yedek")

    assert jev_blocked_sources(robots) == frozenset({"aspor"})


def test_no_live_news_source_is_blocked_by_todays_robots_snapshots() -> None:
    assert jev_blocked_sources(REPO / "config" / "robots") == frozenset()


def test_the_jev_robots_dir_is_the_collectors() -> None:
    assert ROBOTS_DIR == collect.ROBOTS_DIR


def test_every_news_source_has_a_language() -> None:
    assert set(NEWS_SOURCE_LANGS) == {"ajansspor", *RSS_SOURCES}
    assert {sid for sid, lang in NEWS_SOURCE_LANGS.items() if lang == "tr"} == {
        "ajansspor",
        "fotomac",
        "aspor",
    }
    assert {sid for sid, lang in NEWS_SOURCE_LANGS.items() if lang == "en"} == {
        "sportsmole",
        "independent",
        "standard",
        "gffn",
        "football-oranje",
    }
```

(`rename` silme değildir; `tmp_path` pytest'in kendi dizinidir.)

`tests/test_sources.py:442` satırını değiştir:

```python
    pairs += tuple(
        (source_id, feed.path)  # anahtar = adaptörün kaynak id'si; her akış ayrı beyan edilmeli
        for source_id, feeds in news._ARTICLE_PATHS.items()
        for feed in feeds
    )
```

- [ ] **Step 3: Koş — kırmızı**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_news.py tests/test_feature_news.py tests/test_sources.py -q`
Expected: toplama hatası `ImportError: cannot import name 'RSS_SOURCES' from 'football_edge.collectors.news'`.

- [ ] **Step 4: En küçük uygulama — `src/football_edge/collectors/news.py`**

(a) Import bloğu (satır 3-19): `from collections.abc import Mapping` ve `from types import MappingProxyType` ekle.

(b) `GoogleNewsAdapter` sınıfından (satır ~190-195) hemen sonra ekle:

```python
# ---------------------------------------------------------------------------
# Genel RSS 2.0 akışları (Plan 2 R175): 5 EN + 2 TR kaynak. Yalnız başlık, bağlantı ve `pubDate`
# okunur — `<description>` (özet) OKUNMAZ, saklanmaz: Independent/Standard koşulları yalnız başlık
# + URL ile bağlantıyı serbest bırakır. `pubDate`'siz öğe bugünkü bayrakla (`now`, M6) yazılır.
# ---------------------------------------------------------------------------

RSS_SOURCES: tuple[str, ...] = (
    "sportsmole",
    "independent",
    "standard",
    "gffn",
    "football-oranje",
    "fotomac",
    "aspor",
)


@dataclass(frozen=True)
class RssAdapter:
    source_id: str

    def parse(self, body: str, *, now: datetime) -> tuple[NewsItem, ...]:
        return _rss_items(body, self.source_id, now)
```

(c) `_ADAPTERS` (satır ~360):

```python
_ADAPTERS: dict[str, NewsAdapter] = {
    "ajansspor": AjansporAdapter(),
    "googlenews": GoogleNewsAdapter(),
    **{source_id: RssAdapter(source_id) for source_id in RSS_SOURCES},
}
```

(d) `_ARTICLE_PATHS: dict[str, str] = {"ajansspor": "/sitemap/news"}` satırını (satır ~388) değiştir:

```python
@dataclass(frozen=True)
class Feed:
    """Bir kaynağın GERÇEKTEN istenen bir yolu (R7) ve o yolun ölçülmüş içerik türü (spec §7)."""

    path: str
    content_type: str


# Ölçüldü 2026-10-04 (kontrolör, proje kimliğiyle kaynak başına tek istek): içerik türü KAYNAĞA
# göre değişir; `fetch_text` 200'ün doğru veri olduğunu ancak türle bilir. Kaynak birden çok akış
# taşıyabilir (demet); her akış `config/sources.yaml` `declared_paths`te beyanlıdır
# (`tests/test_sources.py::test_each_collectors_fetched_path_is_declared`).
_ARTICLE_PATHS: dict[str, tuple[Feed, ...]] = {
    "ajansspor": (Feed("/sitemap/news", "application/xml"),),
    "sportsmole": (Feed("/football/rss.xml", "application/xml"),),
    "independent": (Feed("/sport/football/rss", "text/xml"),),
    "standard": (Feed("/sport/football/rss", "text/xml"),),
    "gffn": (Feed("/feed/", "application/rss+xml"),),
    "football-oranje": (Feed("/feed/", "application/rss+xml"),),
    "fotomac": (Feed("/rss/news.xml", "text/xml"),),
    "aspor": (Feed("/rss/futbol.xml", "application/xml"),),
}

# Kaynak başına tazelik sınırı; yoksa `collect_news(max_age=)` (2 gün). Ölçüldü 2026-10-04:
# football-oranje 10 öğe, EN YENİSİ 3 gün önce; gffn 10 öğe, günde ~1–3. İki günlük sınır bu iki
# düşük hacimli akışı her sakin haftada exit 7'ye ve alarm gürültüsüne düşürürdü. Pay: oranje
# ölçülen 3 günün iki katından fazla → 7 gün; gffn → 4 gün. Pencereyi aşan kaynak yine kırmızıdır
# (`tests/test_news.py::test_a_feed_beyond_its_own_window_is_red`).
_MAX_AGE: Mapping[str, timedelta] = MappingProxyType(
    {"football-oranje": timedelta(days=7), "gffn": timedelta(days=4)}
)
```

(e) `collect_news`in döngüsünü (satır ~448-487) iki yardımcıya böl. `_source_by_id`den sonra ekle:

```python
def _fetch_items(
    client: httpx.Client,
    source: Source,
    adapter: NewsAdapter,
    robots_dir: Path,
    now: datetime,
) -> tuple[NewsItem, ...]:
    """Kaynağın bütün akışları; aynı URL iki akışta görünürse ilki kalır (tek gözlem).

    Eşlemesiz adaptör bir wiring hatasıdır (`RuntimeError`) ve çağıranın `try`ı İÇİNDE düşer:
    adaptör bazlı izolasyon korunur (bkz. `collect_news`)."""
    feeds = _ARTICLE_PATHS.get(adapter.source_id)
    if not feeds:
        raise RuntimeError(f"{adapter.source_id}: fetch yolu tanımlı değil — wiring eksik")
    parser = robots_for(source, robots_dir)
    items: tuple[NewsItem, ...] = ()
    seen: frozenset[str] = frozenset()
    for feed in feeds:
        body = fetch_text(client, source, feed.path, parser, expect=feed.content_type)
        fresh = tuple(item for item in adapter.parse(body, now=now) if item.url not in seen)
        items = (*items, *fresh)
        seen = seen | {item.url for item in fresh}
    return items


def _collect_source(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    source: Source,
    adapter: NewsAdapter,
    *,
    robots_dir: Path,
    now: datetime,
    max_age: timedelta,
) -> tuple[int, int]:
    """(yeni yazılan, kendi-damgalı) — yalnız commit edilen turda sayılır (Minor #4)."""
    items = _fetch_items(client, source, adapter, robots_dir, now)
    sourced = tuple(item for item in items if item.published_at_is_source_provided)
    if sourced:
        assert_fresh(
            tuple(news_observation(item) for item in sourced),
            now,
            max_age=_MAX_AGE.get(adapter.source_id, max_age),
            source_id=adapter.source_id,
        )
    new_rows = write_observations(conn, tuple(news_observation(item) for item in items))
    conn.commit()
    return new_rows, len(items) - len(sourced)
```

ve `collect_news`in gövdesindeki `for adapter in enabled_adapters(sources):` döngüsünü (docstring aynen kalır;
"M6 kararı" paragrafının sonuna bir cümle ekle: "Tazelik penceresi kaynak başınadır: `_MAX_AGE`, yoksa
`max_age`.") şununla değiştir:

```python
    for adapter in enabled_adapters(sources):
        try:
            source = _source_by_id(sources, adapter.source_id)
            new_rows, stamped = _collect_source(
                conn,
                client,
                source,
                adapter,
                robots_dir=robots_dir,
                now=now,
                max_age=max_age,
            )
            written += new_rows
            self_stamped += stamped
        except Exception:
            conn.rollback()
            LOGGER.exception("kaynak=%s haber toplanamadı", adapter.source_id)
            failed = (*failed, adapter.source_id)
```

Satır 375-386'daki yorum bloğunun ilk cümlesini "Her adaptörün GERÇEKTEN fetch ettiği akışlar burada
adlandırılır (R7) — kaynak başına `Feed` demeti." diye güncelle.

- [ ] **Step 5: En küçük uygulama — `src/football_edge/features/news.py` ve `config/sources.yaml`**

`features/news.py` import bloğuna `import logging`, `from pathlib import Path`; satır 31-32'yi değiştir:

```python
LOGGER = logging.getLogger("football_edge.features.news")

# Kaynak → haber dili (Plan 2 R175). Dilsiz kaynak okunmaz; EN kalibrasyonu (R183) bitene dek EN
# haberi depoya girer ama Jev'e gitmez (dil kapısı kademelerdedir, R178).
NEWS_SOURCE_LANGS: Mapping[str, str] = MappingProxyType(
    {
        "ajansspor": "tr",
        "fotomac": "tr",
        "aspor": "tr",
        "sportsmole": "en",
        "independent": "en",
        "standard": "en",
        "gffn": "en",
        "football-oranje": "en",
    }
)
# Toplayıcının robots anlık görüntüleri (`collect.ROBOTS_DIR` ile aynı; testle sabit).
ROBOTS_DIR = Path("config/robots")
```

`write_news`ten önce ekle:

```python
def ai_input_denied(robots_text: str) -> bool:
    """`Content-Signal` satırlarından biri `ai-input=no` diyor mu (Plan 2 spec §4/9).

    Yalnız AÇIK `no` engeller: satır yoksa ya da `ai-input` anılmıyorsa False (EN beş kaynakta
    satır yok — ölçüldü 2026-10-04). Grup ayrımı yapılmaz: herhangi bir grubun `no`su yeter."""
    for line in robots_text.splitlines():
        key, _, value = line.partition(":")
        if key.strip().casefold() != "content-signal":
            continue
        for part in value.split(","):
            name, _, flag = part.partition("=")
            if name.strip().casefold() == "ai-input" and flag.strip().casefold() == "no":
                return True
    return False


def jev_blocked_sources(robots_dir: Path = ROBOTS_DIR) -> frozenset[str]:
    """Haberi Jev'e GİTMEYEN canlı kaynaklar: anlık görüntüsü `ai-input=no` diyen ya da anlık
    görüntüsü OLMAYAN (ölçülmemiş = izin yok) `NEWS_SOURCE_LANGS` kaynakları."""
    blocked: frozenset[str] = frozenset()
    for source_id in NEWS_SOURCE_LANGS:
        snapshot = robots_dir / f"{source_id}.txt"
        if not snapshot.is_file() or ai_input_denied(snapshot.read_text(encoding="utf-8")):
            blocked = blocked | {source_id}
    return blocked
```

`load_news`i değiştir:

```python
def load_news(
    conn: psycopg.Connection[Any], *, since: datetime, robots_dir: Path = ROBOTS_DIR
) -> tuple[StoredNews, ...]:
    """Jev'e giden TEK okuma yolu (kademe 1, kademe 2, ölçüm komutları). Robots'u `ai-input=no`
    diyen canlı kaynağın haberi BURADA düşer (spec §4/9); arşiv kaynağı (`NEWS_SOURCE_LANGS`
    dışı) süzülmez."""
    blocked = jev_blocked_sources(robots_dir)
    if blocked:
        LOGGER.warning("haber: Jev'e kapalı kaynak %s (ai-input=no ya da anlık görüntü yok)", sorted(blocked))
    with conn.cursor() as cur:
        cur.execute(_SELECT_NEWS, (since,))
        rows = cur.fetchall()
    return tuple(
        StoredNews(
            item_id=int(row[0]),
            source_id=str(row[1]),
            lang=str(row[2]),
            title=str(row[3]),
            body=None if row[4] is None else str(row[4]),
            url=str(row[5]),
            published_at_claimed=row[6],
            available_at=row[7],
            availability_basis=str(row[8]),
            content_hash=str(row[9]),
            first_seen_at=row[10],
        )
        for row in rows
        if str(row[1]) not in blocked
    )
```

(`LOGGER.warning` satırı 100 sütunu aşarsa `ruff format` böler.)

`config/sources.yaml`'da `ajansspor` kaydından sonra (`openmeteo`dan önce) yedi kayıt; ortak alanlar:
`user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)`, `crawl_delay_seconds: 2.0`,
`robots_verified_at: 2026-10-04`, `enabled: true`, `access_basis: robots`.

```yaml
  - id: sportsmole
    base_url: https://www.sportsmole.co.uk
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-04
    declared_paths: ['/football/rss.xml']
    enabled: true
    access_basis: robots
    terms_url: https://www.sportsmole.co.uk/about/information/terms-and-conditions_467.html
    note: >-
      Plan 2 R175 (K/4 kullanıcı kararı: koşullu iç kullanım; docs/reports/2026-10-02-en-haber-kaynaklari.md).
      Content-Signal satırı YOK (ai-input belirtilmemiş — yalnız açık `no` Jev'i keser, spec §4/9).
      Ölçüldü 2026-10-04: 200 application/xml, 82 öğe, güncel. Saklanan yalnız başlık + URL; özet okunmaz.
      Koşullar (12.05.2026): kişisel/ticari olmayan; her kullanım yazılı izne bağlı — ticari lansmandan
      önce yazılı izin; başlıkların TypeSafe'e gönderimi avukat S8 sorusunda (M-8).

  - id: independent
    base_url: https://www.independent.co.uk
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-04
    declared_paths: ['/sport/football/rss']
    enabled: true
    access_basis: robots
    terms_url: https://www.independent.co.uk/service/user-policies-a6184151.html
    note: >-
      Plan 2 R175 (K/4). Content-Signal satırı YOK (ai-input belirtilmemiş). Ölçüldü 2026-10-04: 200
      text/xml, 11 öğe. Koşullar başlık + URL ile bağlantıyı açıkça serbest bırakır; izinsiz saklama/
      arşivleme yasak → saklanan YALNIZ başlık + URL (R175). Avukat S8.

  - id: standard
    base_url: https://www.standard.co.uk
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-04
    declared_paths: ['/sport/football/rss']
    enabled: true
    access_basis: robots
    terms_url: https://www.standard.co.uk/service/terms-of-use-6902768.html
    note: >-
      Plan 2 R175 (K/4). Independent ile aynı koşul metni. Content-Signal satırı YOK. Ölçüldü
      2026-10-04: 200 text/xml, 23 öğe. Saklanan yalnız başlık + URL. Avukat S8.

  - id: gffn
    base_url: https://www.getfootballnewsfrance.com
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-04
    declared_paths: ['/feed/']
    enabled: true
    access_basis: robots
    terms_url: ''
    note: >-
      Plan 2 R175 (K/4). robots'ta `User-agent: *` grubu yok (yalnız bingbot/AmazonAdBot, Crawl-delay 1)
      → kısıtsız; Content-Signal satırı YOK. Ölçüldü 2026-10-04: 200 application/rss+xml, 10 öğe
      (bugün). Düşük hacim: tazelik penceresi 4 gün (collectors/news.py `_MAX_AGE`). Koşul sayfası yok —
      koşul yokluğu hak verilmesi demek değil. Avukat S8.

  - id: football-oranje
    base_url: https://www.football-oranje.com
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-04
    declared_paths: ['/feed/']
    enabled: true
    access_basis: robots
    terms_url: ''
    note: >-
      Plan 2 R175 (K/4). robots `*` için `Disallow:` boş; Content-Signal satırı YOK. Ölçüldü 2026-10-04:
      200 application/rss+xml, 10 öğe, EN YENİSİ 3 gün önce → tazelik penceresi 7 gün
      (collectors/news.py `_MAX_AGE`). Hollanda futbolu (milli takım ağırlıklı). Koşul sayfası bulunamadı.

  - id: fotomac
    base_url: https://www.fotomac.com.tr
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-04
    declared_paths: ['/rss/news.xml']
    enabled: true
    access_basis: robots
    terms_url: ''
    note: >-
      Plan 2 R175 (K/4). Content-Signal: search=yes, ai-input=yes, ai-train=no. `/rss/futbol.xml` ve
      `/rss/anasayfa.xml` BAYAT (son öğe 2025-05-31) → yol `/rss/news.xml` (ölçüldü 2026-10-04: 200
      text/xml, 214 öğe, güncel). Koşul sayfası okunmadı — avukat paketi S5/S8.

  - id: aspor
    base_url: https://www.aspor.com.tr
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-04
    declared_paths: ['/rss/futbol.xml']
    enabled: true
    access_basis: robots
    terms_url: ''
    note: >-
      Plan 2 R175 (K/4). Content-Signal: search=yes, ai-input=yes, ai-train=no. Ölçüldü 2026-10-04: 200
      application/xml, 100 öğe, güncel. Koşul sayfası okunmadı — avukat paketi S5/S8.
```

- [ ] **Step 6: Koş — yeşil**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_news.py tests/test_feature_news.py tests/test_sources.py tests/test_feature_tier1.py -q && uv run mypy src scripts && uv run python -m football_edge.collect sources-audit`
Expected: hepsi `passed`; mypy `Success`; `sources-audit` "TEMİZ" (yedi kayıt enabled, anlık görüntüler var,
tarih 2026-10-04, beyan edilen yollar izinli). `test_feature_tier1.py` de yeşil (ajansspor `ai-input=yes`).

- [ ] **Step 7: Mutasyon kanıtı (dört)**

(a) Oranje'nin kendi penceresi kalkarsa — `F=src/football_edge/collectors/news.py`, OLD
`{"football-oranje": timedelta(days=7), "gffn": timedelta(days=4)}`, NEW `{"gffn": timedelta(days=4)}`;
test `tests/test_news.py -k low_volume`. Expected: `exit=1`, `[football-oranje-age0]` kırmızı.

(b) Ölçülmüş içerik türü yerine sabit tür — OLD `expect=feed.content_type)`, NEW `expect="application/xml")`;
test `tests/test_news.py -k "content_type or plus_three"`. Expected: `exit=1`,
`test_each_feed_is_fetched_with_its_own_measured_content_type` ve `test_a_plus_three_hour_feed_is_not_future_dated_at_collection` kırmızı.

(c) Saat dilimi atılırsa — OLD `return _ensure_aware_utc(published), True`, NEW
`return published.replace(tzinfo=UTC), True`; test `tests/test_news.py -k "offsets or plus_three"`. Expected:
`exit=1`; `+0300` ve `+0100` parametreleri ile `plus_three` kırmızı, `GMT`/`+0000` yeşil.

(d) `ai-input=no` süzgeci kalkarsa — `F=src/football_edge/features/news.py`, OLD
`        if str(row[1]) not in blocked\n` (çok satırlı argüman olarak: `'        for row in rows
        if str(row[1]) not in blocked
'`), NEW `'        for row in rows
'`; test `tests/test_feature_news.py -k denies_ai_input`. Expected: `exit=1`,
`test_load_news_drops_a_source_whose_robots_denies_ai_input` kırmızı.

- [ ] **Step 8: Commit**

```bash
uv run ruff format src tests scripts
git add config/sources.yaml src/football_edge/collectors/news.py src/football_edge/features/news.py tests/test_news.py tests/test_feature_news.py tests/test_sources.py
git commit -F - <<'EOF'
feat: yedi RSS kaynağı — akış/içerik türü listesi, kaynak başına tazelik, ai-input süzgeci

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 9: TAM KAPI** — Global Constraints'teki komut. Expected: `FAIL:` yok; `PASS: kaynak-politikası`; `KAPI YEŞİL`.

---

### Task 2: Dil kapısı, kademe 1 tur tavanı + parti commit'i, `collect-news.yml` kademe 1 adımı

**Kademe:** K1

**Files:**
- Modify: `src/football_edge/calibration.py:181` (önüne `production_languages`)
- Modify: `src/football_edge/features/tier1.py:65-74` (sabitler), `:116-126` (`Tier1Run`), `:342-430` (`run_tier1`), `:431` sonrası (`batches`, `merge_runs`, `EMPTY_RUN`)
- Modify: `src/football_edge/features/__main__.py:24-46` (import), `:60-68` (`_parser`), `:83-139` (`_report`, `_tier1`)
- Modify: `.github/workflows/collect-news.yml` (bütün iş)
- Create: `tests/jev_workflow_helpers.py`, `tests/test_tier1_workflow.py`
- Modify: `tests/test_feature_tier1.py:647-695` (`_db_with`, `_cli`) + sona yeni testler; `tests/test_calibration.py` (sona);
  `tests/test_collect_workflows.py:105-135` (secret testi), `:170-213` (`GITHUB_OUTPUT`);
  `tests/test_news_sync_workflow.py:44-51`; `tests/test_workflows.py:560-570`

**Interfaces:**
- Consumes: `features.news.load_news(conn, *, since)` (Task 1 imzası geriye uyumlu);
  `calibration.CalibrationReport`, `calibration.production_ready`; `collect.LANGUAGES_PATH`.
- Produces: `calibration.production_languages(languages_path: Path) -> frozenset[str]`;
  `tier1.MAX_CALLS_PER_RUN = 40`, `tier1.BATCH_SIZE = 10`;
  `Tier1Run.calls: int = 0`, `Tier1Run.deferred: int = 0`;
  `run_tier1(..., max_calls: int | None = None) -> Tier1Run`;
  `tier1.batches(items: Sequence[StoredNews], size: int) -> tuple[tuple[StoredNews, ...], ...]`;
  `tier1.newest_within_cap(items, fixtures, *, attempts: Mapping[int, int], cap: int) -> tuple[tuple[StoredNews, ...], int]`;
  `tier1.merge_runs(first: Tier1Run, second: Tier1Run) -> Tier1Run`; `tier1.EMPTY_RUN: Tier1Run`;
  CLI `features tier1 [--languages PATH] [--max-calls N]`;
  `tests.jev_workflow_helpers`: `JEV_SECRET`, `SWITCH`, `AFTER_FETCH`, `JEV_CASES`, `StepRun`, `run_step(...)`,
  `with_jev_key(document, needle)` (Task 3 tüketir).

**Karar — çağrı tavanı neyi sayar ve hangi sırayla:** adayı olan, vazgeçilmemiş (Jev'e gidecek) haberi.
Adaysız haber bedavadır ve tavanı tüketmez. Tavan altında EN YENİDEN EN ESKİYE seçilir (inceleme I6: karara en
yakın haber önce; `newest_within_cap`); seçilenler partilerde yine zaman sırasıyla sorulur (küme nedenselliği).
Tavanı aşan haber `deferred` sayılır, işaret YAZILMAZ ve sonraki turda yeniden sorulur.
**Parti:** CLI haberleri `BATCH_SIZE`lik partilere böler, her partiden sonra yazar ve commit'ler (zaman aşımı
ödenmiş cevabı yutmaz, I-8). Sonraki partinin küme adayı havuzu önceki partileri `history` olarak görür.

- [ ] **Step 1: Başarısız testleri yaz — `tests/test_calibration.py` sonuna**

Import: `from football_edge.calibration import production_languages` (mevcut import listesine), `import json`
(yoksa).

```python
def _languages_file(tmp_path: Path, *, enabled: bool, accuracy: float, n: int = 100) -> Path:
    report = tmp_path / "tr.report.json"
    report.write_text(
        json.dumps(
            {
                "language": "tr",
                "n": n,
                "accuracy": accuracy,
                "false_positive": 0,
                "false_negative": 0,
                "mean_confidence": 0.9,
            }
        ),
        encoding="utf-8",
    )
    path = tmp_path / "languages.yaml"
    path.write_text(
        "languages:\n"
        f"  - code: tr\n    production_enabled: {'true' if enabled else 'false'}\n"
        f"    calibration_report: {report}\n"
        f"  - code: en\n    production_enabled: false\n"
        f"    calibration_report: {tmp_path / 'en.report.json'}\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("enabled", "accuracy", "n", "expected"),
    [
        (True, 0.85, 100, {"tr"}),
        (True, 0.84, 100, set()),
        (True, 0.95, 99, set()),
        (False, 0.95, 100, set()),
    ],
)
def test_production_languages_need_the_flag_and_a_passing_report(
    tmp_path: Path, enabled: bool, accuracy: float, n: int, expected: set[str]
) -> None:
    """R178/R182: bayrak tek başına yetmez — rapor `min_n = 100`, `min_accuracy = 0,85`i geçmeli."""
    path = _languages_file(tmp_path, enabled=enabled, accuracy=accuracy, n=n)

    assert production_languages(path) == frozenset(expected)
```

- [ ] **Step 2: Başarısız testleri yaz — `tests/test_feature_tier1.py`**

Import listesine `field` (zaten var), `Callable` (`from collections.abc import Callable, Mapping, Sequence`),
`tier1`den `BATCH_SIZE`, `batches`, `merge_runs`, `newest_within_cap`, `EMPTY_RUN`. `_db_with`i fabrika alacak biçimde değiştir:

```python
def _db_with(*items: StoredNews, factory: Callable[..., FakeNewsDb] = FakeNewsDb) -> FakeNewsDb:
    """Veritabanı saati haberlerden önce: yazılan haberin `available_at`i = iddia = kendi anı."""
    db = factory(now=T0 - timedelta(days=30))
```
(gövdenin kalanı aynı). `_cli`ye, `monkeypatch.setattr(cli, "_now", ...)` satırından sonra ekle:

```python
    # Bugün hiçbir dil üretimde değil (config/languages.yaml); testler TR'yi üretimde sayar.
    monkeypatch.setattr(cli, "production_languages", lambda path: frozenset({"tr"}))
```

Sona ekle:

```python
# ── Plan 2 Task 2: tur tavanı, partiler, dil kapısı ────────────────────────────────────────


def test_the_call_cap_defers_the_rest_without_markers() -> None:
    client = FakeBatteryJev()
    items = [news(n, f"Galatasaray'da haber {n}", T0 + timedelta(minutes=n)) for n in (1, 2, 3)]

    result = run_tier1(
        items, client, QUESTIONS, fixtures=FIXTURES, clock=lambda: ASKED, max_calls=2
    )

    assert (len(client.seen), result.calls, result.deferred) == (2, 2, 1)
    assert result.failures == ()


def test_news_without_a_candidate_does_not_use_the_call_cap() -> None:
    client = FakeBatteryJev()
    items = [news(1, "Hava durumu"), news(2, "Galatasaray'da sakatlık", T0 + timedelta(minutes=1))]

    result = run_tier1(
        items, client, QUESTIONS, fixtures=FIXTURES, clock=lambda: ASKED, max_calls=1
    )

    assert (result.no_candidate, result.calls, result.deferred) == (1, 1, 0)


def test_batches_split_the_items_in_time_order() -> None:
    items = [news(n, f"h{n}", T0 + timedelta(minutes=-n)) for n in range(1, 6)]

    found = batches(items, 2)

    assert [[i.item_id for i in batch] for batch in found] == [[5, 4], [3, 2], [1]]
    with pytest.raises(ValueError, match="parti"):
        batches(items, 0)


def test_merged_runs_add_up_and_keep_the_order() -> None:
    first = run([news(1, "Galatasaray'da sakatlık")], FakeBatteryJev())
    second = run([news(2, "Trabzonspor'da kriz", T0 + timedelta(minutes=1))], FakeBatteryJev())

    merged = merge_runs(merge_runs(EMPTY_RUN, first), second)

    assert merged.rows == (*first.rows, *second.rows)
    assert (merged.asked, merged.calls) == (first.asked + second.asked, 2)
    assert merged.budget_hit is False and merged.outage is False


@dataclass
class _CommitLog(FakeNewsDb):
    """Her commit anında yazılmış cevap sayısı: ödenmiş cevabın hangi partide kalıcılaştığı."""

    committed: list[int] = field(default_factory=list)

    def commit(self) -> None:
        self.committed = [*self.committed, len(self.answers)]
        super().commit()


TWELVE = tuple(news(n, f"Galatasaray'da gelişme {n}", T0 + timedelta(minutes=n)) for n in range(1, 13))


def test_each_batch_is_committed_before_the_next_is_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db_with(*TWELVE, factory=_CommitLog)
    _cli(monkeypatch, db, FakeBatteryJev())

    assert cli.main(["tier1"]) == 0

    assert isinstance(db, _CommitLog)
    first_batch = len([a for a in db.answers if a["item_id"] <= BATCH_SIZE])
    assert db.committed == [first_batch, len(db.answers)]


class _Killed(BaseException):
    """Zaman aşımının taklidi: `_ask`in `Exception` yakalayıcısını geçer, koşuyu öldürür."""


def test_a_run_killed_in_the_second_batch_keeps_the_first_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @dataclass
    class DiesOnEleventh(FakeBatteryJev):
        def ask_battery(
            self, state: Mapping[str, Any], questions: Sequence[Question]
        ) -> BatteryAnswer:
            if len(self.seen) == BATCH_SIZE:
                raise _Killed()
            return super().ask_battery(state, questions)

    db = _db_with(*TWELVE, factory=_CommitLog)
    _cli(monkeypatch, db, DiesOnEleventh())

    with pytest.raises(_Killed):
        cli.main(["tier1"])

    assert isinstance(db, _CommitLog)
    assert len(db.committed) == 1 and db.committed[0] > 0


def test_the_command_stops_asking_at_the_call_cap(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db_with(news(1, "Galatasaray'da sakatlık"), news(2, "Trabzonspor'da kriz"))
    client = FakeBatteryJev()
    _cli(monkeypatch, db, client)

    with caplog.at_level(logging.INFO):
        assert cli.main(["tier1", "--max-calls", "1"]) == 0

    assert len(client.seen) == 1
    assert "ertelenen 1" in caplog.text


def test_under_the_call_cap_the_newest_news_is_asked_first(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """I6: tavan altında en yeniden en eskiye — karar anına en yakın haber önce satın alınır."""
    db = _db_with(
        *(news(n, f"Galatasaray'da gelişme {n}", T0 + timedelta(minutes=n)) for n in (1, 2, 3))
    )
    client = FakeBatteryJev()
    _cli(monkeypatch, db, client)

    with caplog.at_level(logging.INFO):
        assert cli.main(["tier1", "--max-calls", "2"]) == 0

    asked = [call["state"]["news"]["title"] for call in client.seen]
    assert asked == ["Galatasaray'da gelişme 2", "Galatasaray'da gelişme 3"]
    assert "ertelenen 1" in caplog.text


def test_the_cap_skips_news_without_a_candidate_and_given_up_news() -> None:
    items = [
        news(1, "Hava durumu"),
        *(news(n, f"Galatasaray'da {n}", T0 + timedelta(minutes=n)) for n in (2, 3)),
    ]

    kept, deferred = newest_within_cap(items, FIXTURES, attempts={3: MAX_ATTEMPTS}, cap=1)

    assert ([i.item_id for i in kept], deferred) == ([1, 2, 3], 0)


def test_a_non_production_language_item_never_reaches_jev_even_as_earlier_news(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review Focus 1: EN haber sorulmaz VE küme adayı olarak başlığıyla Jev'e gitmez (R178).
    EN haber önceden SORULMUŞ işaretlenir: süzgeç yalnız sorulacakları (`items`) süzseydi, sorulmuş
    haber `history`ye, oradan `earlier_news`e girerdi — pencerenin kendisi süzülmeli."""
    english = replace(news(1, "Galatasaray injury update", T0 - timedelta(hours=1)), lang="en")
    db = _db_with(english, news(2, "Galatasaray'da sakatlık"))
    asked = ItemAnswerRow(
        1, QUESTIONS.prompt_version, MATCH_QUESTION, NO_MATCH, {NO_MATCH: 1.0}, 0.9, None,
        "jev-fake", T0, 0.0,
    )
    write_item_answers(db, [asked])  # type: ignore[arg-type]
    client = FakeBatteryJev()
    _cli(monkeypatch, db, client)

    cli.main(["tier1"])

    (call,) = client.seen
    assert call["state"]["news"]["title"] == "Galatasaray'da sakatlık"
    assert call["state"]["earlier_news"] == []


def test_without_a_production_language_nothing_is_asked_and_the_database_is_untouched(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    def _explode() -> Any:
        raise AssertionError("üretim dili yokken veritabanına bağlanılmamalı")

    languages = tmp_path / "languages.yaml"
    languages.write_text(
        "languages:\n  - code: tr\n    production_enabled: false\n"
        f"    calibration_report: {tmp_path / 'tr.report.json'}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "TypeSafeJev", lambda: FakeBatteryJev())
    monkeypatch.setattr(cli, "connect", _explode)

    with caplog.at_level(logging.INFO):
        assert cli.main(["tier1", "--languages", str(languages)]) == 0

    assert "üretimde dil yok" in caplog.text
```

- [ ] **Step 3: Başarısız workflow testlerini yaz — `tests/jev_workflow_helpers.py` (yeni)**

```python
"""Jev adımlarının (kademe 1 `collect-news.yml`, kademe 2 `shadow.yml`) ortak sınama yardımcıları.

Adımın `run:` gövdesi `uv` yerine kayıt tutan bir sahteyle `bash -e -c` altında koşulur
(`test_collect_workflows.py` deseni); `GITHUB_OUTPUT` ve `GITHUB_STEP_SUMMARY` geçici dosyadır.
Secret adı parçalardan kurulur: kapının secrets adımı testleri de tarar.
"""

from __future__ import annotations

import copy
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.workflow_helpers import _index_of

JEV_SECRET = "TYPESAFE" + "_API_KEY"
# Toplama exit 7 (bir kaynak düştü) senkronu ve kademe 1'i durdurmaz (I-6, I-7); tur yine kırmızı
# biter çünkü toplama adımının kendisi 7 döner. Taramaya bağlı: kırmızı taramadan sonra secret'lı
# adım koşmaz (DEFERRED 19b, `test_secrets_scan_netlify.py`).
AFTER_FETCH = (
    "${{ !cancelled() && steps.secret_scan.outcome == 'success' && "
    "(success() || steps.fetch.outputs.code == '7') }}"
)
# (komutun kodu, JEV_ENABLED, beklenen `jev` çıktısı, hata satırında geçmesi gereken sözcük)
JEV_CASES = [
    (0, None, "ok", ""),
    (17, None, "ok", ""),
    (17, "1", "fail", "JEV_ENABLED"),
    (7, None, "fail", "kesinti"),
    (16, None, "fail", "tavan"),
    (1, None, "fail", "beklenmedik"),
]
JEV_CASE_IDS = ["ok", "off-17", "enabled-17", "outage-7", "budget-16", "other-1"]
# Ücret yamasının (R177) Jev adımına eklediği env satırları — yamalı/yamasız hâl ikisi de geçerli.
SWITCH = {JEV_SECRET: "${{ secrets." + JEV_SECRET + " }}", "JEV_ENABLED": "1"}
FAKE_UV = """\
#!/usr/bin/env bash
echo "$*" >> "$CALLS"
exit "${FAIL_CODE:-0}"
"""


@dataclass(frozen=True)
class StepRun:
    returncode: int
    errors: tuple[str, ...]
    outputs: dict[str, str]
    summary: str
    calls: tuple[str, ...]


def run_step(tmp_path: Path, body: str, *, code: int, jev_enabled: str | None = None) -> StepRun:
    fake = tmp_path / "uv"
    fake.write_text(FAKE_UV, encoding="utf-8")
    fake.chmod(0o755)
    calls, output, summary = tmp_path / "calls", tmp_path / "output", tmp_path / "summary.md"
    for path in (calls, output, summary):
        path.touch()
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAIL_CODE": str(code),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(summary),
        **({} if jev_enabled is None else {"JEV_ENABLED": jev_enabled}),
    }
    result = subprocess.run(
        ["bash", "-e", "-c", body], env=env, capture_output=True, text=True, timeout=30, check=False
    )
    lines = output.read_text(encoding="utf-8").splitlines()
    return StepRun(
        returncode=result.returncode,
        errors=tuple(line for line in result.stdout.splitlines() if line.startswith("::error::")),
        outputs=dict(line.split("=", 1) for line in lines if "=" in line),
        summary=summary.read_text(encoding="utf-8"),
        calls=tuple(calls.read_text(encoding="utf-8").splitlines()),
    )


def with_jev_key(document: dict[str, Any], needle: str) -> dict[str, Any]:
    """Ücreti açan commit'in (R177) belgeye yaptığı tek şey: Jev adımının env'ine iki satır."""
    switched = copy.deepcopy(document)
    ((_, job),) = switched["jobs"].items()
    index = _index_of(job["steps"], needle)
    assert index is not None, f"{needle} adımı yok"
    step = job["steps"][index]
    step["env"] = {**step["env"], **SWITCH}
    return switched
```

- [ ] **Step 4: Başarısız workflow testlerini yaz — `tests/test_tier1_workflow.py` (yeni)**

```python
"""`collect-news.yml` kademe 1 adımı (Plan 2 R177, R179, R186; I-4…I-7).

Kademe 1 `sync-news`ten hemen sonra koşar; Jev arızası haber turunu kırmızı yapmaz, `jev-kademe1`
alarmını açar; anahtarsız 17 "Jev kapalı" yeşildir, `JEV_ENABLED=1` iken kırmızıdır (alarm).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.jev_workflow_helpers import AFTER_FETCH, JEV_CASE_IDS, JEV_CASES, SWITCH, run_step
from tests.workflow_helpers import COLLECT_NEWS, _index_of, _steps

TIER1 = "football_edge.features tier1"
OPEN = "scripts/ops_alert.py fail --workflow jev-kademe1 "
CLOSE = "scripts/ops_alert.py ok --workflow jev-kademe1 "
OPEN_IF = "${{ !cancelled() && steps.tier1.outputs.jev == 'fail' }}"
CLOSE_IF = "${{ !cancelled() && steps.tier1.outputs.jev == 'ok' }}"


def _at(steps: list[dict[str, Any]], needle: str) -> int:
    index = _index_of(steps, needle)
    assert index is not None, f"collect-news.yml: {needle!r} adımı yok"
    return index


def _tier1_body() -> str:
    steps = _steps(COLLECT_NEWS)
    return str(steps[_at(steps, TIER1)]["run"])


def test_tier1_runs_right_after_sync_and_even_after_a_failed_source() -> None:
    steps = _steps(COLLECT_NEWS)
    fetch = _at(steps, "football_edge.collect fetch-news")
    sync = _at(steps, "football_edge.features sync-news")
    tier1 = _at(steps, TIER1)

    assert (sync, tier1) == (fetch + 1, fetch + 2)
    assert steps[fetch]["id"] == "fetch"
    assert steps[tier1]["id"] == "tier1"
    assert steps[tier1]["if"] == AFTER_FETCH
    assert "continue-on-error" not in steps[tier1]


def test_tier1_gets_the_database_and_at_most_the_paid_switch() -> None:
    """Anahtar ücret yamasıyla gelir (R177); o güne dek adım anahtarsız koşar ve 17 = Jev kapalı.
    Yama testlere dokunmaz: test iki hâli de (yamasız / yamalı) kabul eder; anahtar ve
    `JEV_ENABLED` yalnız BİRLİKTE gelir (I-5)."""
    steps = _steps(COLLECT_NEWS)
    env = dict(steps[_at(steps, TIER1)]["env"])

    assert env.pop("DATABASE_URL") == "${{ secrets.DATABASE_URL }}"
    assert env in ({}, SWITCH)


@pytest.mark.parametrize(("code", "enabled", "jev", "named"), JEV_CASES, ids=JEV_CASE_IDS)
def test_the_tier1_step_never_turns_the_news_run_red_and_names_every_jev_outcome(
    tmp_path: Path, code: int, enabled: str | None, jev: str, named: str
) -> None:
    run = run_step(tmp_path, _tier1_body(), code=code, jev_enabled=enabled)

    assert run.calls == (f"run python -m {TIER1}",)
    assert run.returncode == 0, "Jev arızası haber turunu kırmızı yapmamalı (R179)"
    assert run.outputs == {"jev": jev}
    if jev == "ok":
        assert run.errors == ()
    else:
        assert len(run.errors) == 1 and named in run.errors[0] and f"exit {code}" in run.errors[0]


def test_jev_off_is_written_to_the_run_summary(tmp_path: Path) -> None:
    run = run_step(tmp_path, _tier1_body(), code=17)

    assert "Jev kapalı" in run.summary


def test_a_failed_jev_step_opens_its_own_alarm_before_the_news_alarm() -> None:
    steps = _steps(COLLECT_NEWS)
    tier1, opens, closes = _at(steps, TIER1), _at(steps, OPEN), _at(steps, CLOSE)
    news_opens = _at(steps, "scripts/ops_alert.py fail --workflow collect-news ")

    assert tier1 < opens < closes < news_opens
    assert (steps[opens]["if"], steps[closes]["if"]) == (OPEN_IF, CLOSE_IF)
    assert steps[closes].get("continue-on-error") is True
    for index in (opens, closes):
        env = steps[index]["env"]
        assert env["GITHUB_TOKEN"] == "${{ github.token }}"
        assert str(env["RUN_URL"]).endswith("/actions/runs/${{ github.run_id }}")


def test_the_news_run_has_room_for_the_capped_tier1() -> None:
    """40 çağrı × gecikme + toplama: 10 dakika yetmez (Task 5 gecikmeyi ölçer)."""
    document = yaml.safe_load(COLLECT_NEWS.read_text(encoding="utf-8"))
    assert document["jobs"]["collect"]["timeout-minutes"] == 20
```

- [ ] **Step 5: Mevcut workflow testlerini güncelle**

`tests/test_news_sync_workflow.py:44-51`'deki testi değiştir:

```python
def test_sync_step_gets_only_the_database_and_runs_after_a_failed_source() -> None:
    """Toplama exit 7 (bir kaynak düştü) senkronu durdurmaz (Plan 2 I-6); başka bir toplama
    kırmızısında koşmaz. `continue-on-error` yok: senkronun kendi kırmızısı turu kırmızı yapar."""
    step = _sync_step()

    assert step.get("env") == {"DATABASE_URL": "${{ secrets.DATABASE_URL }}"}
    assert step.get("if") == AFTER_FETCH
    assert not step.get("continue-on-error", False)
```
Import: `from tests.jev_workflow_helpers import AFTER_FETCH`.

`tests/test_collect_workflows.py` — üst import bloğuna `import copy` gerekmez; ekle:
`from tests.jev_workflow_helpers import JEV_SECRET, with_jev_key`. `DATABASE_STEPS` (satır ~103) ve secret
testini (satır ~108-135) değiştir:

```python
# Veritabanına yazan adımlar: toplayıcı; collect-news'te ayrıca haber deposu (R172) ve kademe 1.
DATABASE_STEPS = {
    COLLECT_DAILY: ("football_edge.collect",),
    COLLECT_NEWS: (
        "football_edge.collect",
        "football_edge.features sync-news",
        "football_edge.features tier1",
    ),
}
# Ücret anahtarı (R177, I-4) YALNIZ Jev adımının env'inde durabilir; bugün hiçbirinde yok.
JEV_STEPS: dict[Path, tuple[str, ...]] = {
    COLLECT_DAILY: (),
    COLLECT_NEWS: ("football_edge.features tier1",),
}


def _value(document: Any, path: tuple[Any, ...]) -> Any:
    node = document
    for key in path:
        node = node[key]
    return node


def _secret_violations(path: Path, document: dict[str, Any]) -> list[str]:
    """Secret'ın ulaştığı her yer izinli mi: DATABASE_URL yalnız veritabanı adımlarında (hepsinde),
    Jev anahtarı yalnız Jev adımlarında (varsa). Workflow/job `env`i ya da başka adım ihlaldir."""
    ((job_id, job),) = document["jobs"].items()
    steps = job["steps"]

    def at(needle: str, name: str) -> tuple[Any, ...]:
        return ("jobs", job_id, "steps", _index_of(steps, needle), "env", name)

    database = {at(n, "DATABASE_URL"): "secrets.DATABASE_URL" for n in DATABASE_STEPS[path]}
    jev = {at(n, JEV_SECRET): f"secrets.{JEV_SECRET}" for n in JEV_STEPS[path]}
    allowed = {**database, **jev}
    reached = {
        where: _secret_expressions(str(_value(document, where)))
        for where in _secret_paths(document)
    }
    wrong = [f"{w}: {e}" for w, e in reached.items() if e != [allowed.get(w)]]
    missing = [f"{w}: yok" for w in database if w not in reached]
    return wrong + missing


@pytest.mark.parametrize("path", COLLECTORS, ids=lambda path: path.name)
def test_only_database_steps_get_the_database_and_only_jev_steps_may_get_the_jev_key(
    path: Path,
) -> None:
    """Toplayıcılar ücretli API çağırmaz: `ODDS_API_KEY` hiç yok. `DATABASE_URL` YALNIZ veritabanına
    yazan adımların `env`inde; Jev anahtarı YALNIZ kademe adımının `env`inde (bugün hiçbirinde).
    Yorumdaki `${{ secrets.X }}` de sayılır (metin taraması)."""
    text = path.read_text(encoding="utf-8")
    secrets = set(_secret_expressions(text))

    assert secrets <= {"secrets.DATABASE_URL", f"secrets.{JEV_SECRET}"}, secrets
    assert _secret_violations(path, yaml.safe_load(text)) == []


def test_the_paid_switch_is_env_lines_on_the_jev_step_only() -> None:
    """R177: ücret yaması yalnız kademe 1 adımına iki env satırı ekler ve bu test yeşil kalır."""
    document = yaml.safe_load(COLLECT_NEWS.read_text(encoding="utf-8"))

    assert _secret_violations(COLLECT_NEWS, with_jev_key(document, "football_edge.features tier1")) == []
    misplaced = with_jev_key(document, "football_edge.features sync-news")
    assert _secret_violations(COLLECT_NEWS, misplaced) != []
```

Aynı dosyada `test_a_red_collector_does_not_stop_the_others_and_turns_the_run_red`in `env` sözlüğüne
`"GITHUB_OUTPUT": str(tmp_path / "output"),` ekle ve sonuna:

```python
    if path == COLLECT_NEWS:
        # Senkron ve kademe 1 bu çıktıya bakar (I-6): kod her zaman yazılır, yutulmaz.
        assert (tmp_path / "output").read_text(encoding="utf-8") == f"code={code}\n"
```
(`(tmp_path / "output")` dosyası testte önceden `touch()` edilir: `env` sözlüğünden önce
`(tmp_path / "output").touch()`.)

`tests/test_workflows.py:560-570` (`test_only_the_closing_step_may_fail_without_turning_the_run_red`):

```python
JEV_CLOSE = "scripts/ops_alert.py ok --workflow jev-"


@pytest.mark.parametrize("path", ALARMED, ids=lambda path: path.name)
def test_only_the_closing_step_may_fail_without_turning_the_run_red(path: Path) -> None:
    """Yeşil turda `ok` düşerse (ör. GitHub 502) tur alarmsız kırmızıya dönerdi: `Alarm kapat`
    `continue-on-error` taşır; Jev alarmını kapatan adım da (Plan 2 R186: aynı gerekçe, kendi
    başlığı). Başka HİÇBİR adım taşımaz — alarm açan ya da bekçi düşerse tur kırmızı kalmalı."""
    steps, _, closes = _alarm_steps(path)
    tolerant = [index for index, step in enumerate(steps) if step.get("continue-on-error")]
    jev_closes = [i for i, step in enumerate(steps) if JEV_CLOSE in str(step.get("run", ""))]

    assert closes is not None and tolerant == sorted([*jev_closes, closes]), (
        f"{path.name}: continue-on-error taşıyan adımlar {tolerant}"
    )
    assert steps[closes]["continue-on-error"] is True
```

- [ ] **Step 6: Koş — kırmızı**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_calibration.py tests/test_feature_tier1.py tests/test_tier1_workflow.py tests/test_collect_workflows.py tests/test_news_sync_workflow.py tests/test_workflows.py -q`
Expected: toplama hatası `ImportError: cannot import name 'production_languages'` (önce `test_calibration.py`,
ardından `BATCH_SIZE`); düzeltildikçe workflow testleri `KeyError: 'id'` / `None` indeks iddialarıyla kırmızı.

- [ ] **Step 7: En küçük uygulama — `calibration.py` ve `tier1.py`**

`calibration.py`, `language_config_violations`tan önce:

```python
def production_languages(languages_path: Path) -> frozenset[str]:
    """Kademe 1 ve 2'nin sorabildiği diller (Plan 2 R178): `production_enabled: true` VE raporu
    `production_ready()`yi (`min_n = 100`, `min_accuracy = 0,85`) geçen. Kapı (`dil-kalibrasyonu`)
    ikisinin ayrışmasını zaten kırmızı yapar; burada yine sorulur ki ayrışmış bir dosya kalibre
    olmayan haberi Jev'e göndermesin."""
    raw = yaml.safe_load(languages_path.read_text(encoding="utf-8"))
    enabled: frozenset[str] = frozenset()
    for entry in raw.get("languages") or ():
        report_path = Path(entry["calibration_report"])
        if not entry["production_enabled"] or not report_path.is_file():
            continue
        report = CalibrationReport(**json.loads(report_path.read_text(encoding="utf-8")))
        if production_ready(report)[0]:
            enabled = enabled | {str(entry["code"])}
    return enabled
```

`tier1.py` sabitler (satır ~74'ten sonra):

```python
# Tur başına en çok bu kadar Jev çağrısı (I-8): taşan haber `deferred`, işaretsiz, sonraki turda.
MAX_CALLS_PER_RUN = 40
# Parti başına commit: bir zaman aşımı en çok bir partinin ödenmiş cevabını götürür (I-8).
BATCH_SIZE = 10
```

`Tier1Run`a iki alan (son alanın, `outage`ın, altına):

```python
    calls: int = 0  # yapılan Jev çağrısı (tavanın saydığı)
    deferred: int = 0  # çağrı tavanı yüzünden bu turda sorulmayan, adaylı haber
```

`run_tier1`: imzaya `max_calls: int | None = None` (son parametre), docstring'e "`max_calls` adaylı haber
başına çağrıyı sayar; tavanı aşan haber `deferred`, işaretsiz." cümlesi. Gövdede
`asked = failed = no_candidate = given_up = 0` satırını `asked = failed = no_candidate = given_up = calls = deferred = 0`
yap; `if not candidates: … continue` bloğundan hemen sonra:

```python
        if max_calls is not None and calls >= max_calls:
            deferred += 1
            continue
```
`at = clock()` satırından hemen önce `calls += 1`; üç `Tier1Run(...)` dönüşüne `calls=calls, deferred=deferred,`
ekle (budget dönüşünde `calls` artmamıştır: çağrı yapılmadı).

`gates_from`un önüne (Kapı özeti başlığından önce) ekle:

```python
EMPTY_RUN = Tier1Run((), 0, 0, 0, budget_hit=False)


def batches(items: Sequence[StoredNews], size: int) -> tuple[tuple[StoredNews, ...], ...]:
    """(zaman, kimlik) sırasıyla `size`lık partiler; CLI her partiden sonra commit'ler (I-8)."""
    if size < 1:
        raise ValueError(f"parti boyu en az 1 olmalı: {size}")
    ordered = sorted(items, key=_order)
    return tuple(tuple(ordered[start : start + size]) for start in range(0, len(ordered), size))


def newest_within_cap(
    items: Sequence[StoredNews],
    fixtures: Sequence[LiveMatch],
    *,
    attempts: Mapping[int, int],
    cap: int,
) -> tuple[tuple[StoredNews, ...], int]:
    """Tur tavanı altında EN YENİDEN EN ESKİYE (karara en yakın haber önce): Jev'e gidecek (adayı
    olan, vazgeçilmemiş) haberlerden en yeni `cap` tanesi kalır. Dönüş: (kalan haberler, ertelenen).
    Adaysız ve vazgeçilmiş haber tavanı tüketmez; `run_tier1` onları ayrıca sayar."""
    askable = [
        item
        for item in items
        if attempts.get(_order(item)[1], 0) < MAX_ATTEMPTS and candidate_fixtures(item, fixtures)
    ]
    dropped = {_order(item) for item in sorted(askable, key=_order, reverse=True)[cap:]}
    return tuple(item for item in items if _order(item) not in dropped), len(dropped)


def merge_runs(first: Tier1Run, second: Tier1Run) -> Tier1Run:
    """Ardışık iki partinin koşusu tek koşu: sayılar toplanır, satırlar sırayla eklenir."""
    return Tier1Run(
        rows=(*first.rows, *second.rows),
        asked=first.asked + second.asked,
        failed=first.failed + second.failed,
        no_candidate=first.no_candidate + second.no_candidate,
        budget_hit=first.budget_hit or second.budget_hit,
        failures=(*first.failures, *second.failures),
        given_up=first.given_up + second.given_up,
        outage=first.outage or second.outage,
        calls=first.calls + second.calls,
        deferred=first.deferred + second.deferred,
    )
```

- [ ] **Step 8: En küçük uygulama — `features/__main__.py`**

Modül belgesinin `tier1` paragrafından önce (100 sütuna sarılı):

```text
`tier1` yalnız üretim dillerinin (`config/languages.yaml`, rapor geçerli) haberini sorar ve
pencereyi sorgudan hemen sonra dille süzer — kalibre olmayan dilin başlığı küme adayı olarak da
Jev'e gitmez (R178). Tur başına `MAX_CALLS_PER_RUN` çağrı, EN YENİ haber önce (inceleme I6); her
`BATCH_SIZE` haberde commit (I-8).
```
Import: `from collections.abc import Callable, Mapping, Sequence`;
`from football_edge.calibration import production_languages`;
`from football_edge.collect import EXIT_SOURCE_FAILED, LANGUAGES_PATH, configure_logging`;
`from football_edge.features.questions import QUESTIONS_PATH, QuestionSet, load_questions`;
`from football_edge.features.types import StoredNews`; `from football_edge.live.context import LiveMatch`;
`from football_edge.jev import EXIT_NO_JEV_KEY, JevClient, MissingJevKey, TypeSafeJev`;
`from dataclasses import replace`; tier1 importlarına `BATCH_SIZE, EMPTY_RUN, MAX_CALLS_PER_RUN, batches,
merge_runs, newest_within_cap`.

`_parser`ta `tier1` alt komutuna:

```python
    tier1.add_argument("--languages", type=Path, default=LANGUAGES_PATH)
    tier1.add_argument("--max-calls", type=int, default=MAX_CALLS_PER_RUN)
```

`_report` ve `_tier1`i değiştir:

```python
def _report(run: Tier1Run, items: int, written: int, marked: int) -> None:
    LOGGER.info("jev: soru %d · başarısız %d · çağrı %d", run.asked, run.failed, run.calls)
    LOGGER.info(
        "kademe 1: haber %d · adaysız %d · yazılan cevap %d · ertelenen %d (tur tavanı)",
        items,
        run.no_candidate,
        written,
        run.deferred,
    )
    # Vazgeçilen haber bu `prompt_version` için bir daha sorulmaz: operatör onu buradan görür.
    LOGGER.info(
        "kademe 1: başarısızlık işareti %d · vazgeçilen haber %d (%d başarısız deneme)",
        marked,
        run.given_up,
        MAX_ATTEMPTS,
    )


def _ask_in_batches(
    conn: Any,
    client: JevClient,
    questions: QuestionSet,
    *,
    items: Sequence[StoredNews],
    history: Sequence[StoredNews],
    fixtures: Sequence[LiveMatch],
    attempts: Mapping[int, int],
    max_calls: int,
) -> tuple[Tier1Run, int, int]:
    """Partiler: her partiden sonra yaz + commit (I-8); sonraki partinin küme havuzu öncekileri
    görür. Tavan ya da kesinti kalan partileri durdurur. Dönüş: (birleşik koşu, cevap, işaret)."""
    total, written, marked = EMPTY_RUN, 0, 0
    done: tuple[StoredNews, ...] = ()
    for batch in batches(items, BATCH_SIZE):
        run = run_tier1(
            batch,
            client,
            questions,
            fixtures=fixtures,
            clock=_now,
            history=(*history, *done),
            attempts=attempts,
            max_calls=max_calls - total.calls,
        )
        written += write_item_answers(conn, run.rows)
        marked += write_item_answers(conn, run.failures)
        conn.commit()  # parti başına (I-8): zaman aşımı ödenmiş cevabı yutmaz
        total, done = merge_runs(total, run), (*done, *batch)
        if run.budget_hit or run.outage:
            break
    return total, written, marked


def _tier1_exit(run: Tier1Run) -> int:
    if run.budget_hit:
        LOGGER.error("jev: aylık tavan $%.2f doldu — kalan haberler sorulmadı", MONTHLY_CAP_USD)
        return EXIT_BUDGET
    if run.outage:
        # Kesinti bir bağımlılığın (Jev) arızasıdır, haberlerin değil: `sync-news`in kaynak kodu.
        LOGGER.error(
            "jev: kesinti — art arda %d haber Jev hatasıyla düştü, koşu durdu; serinin işareti "
            "yazılmadı, sonraki koşu yeniden sorar",
            OUTAGE_STREAK,
        )
        return EXIT_SOURCE_FAILED
    return 0


def _tier1(args: argparse.Namespace) -> int:
    try:
        jev = TypeSafeJev()
    except MissingJevKey as error:
        LOGGER.error("kademe 1 koşulmadı: %s", error)
        return EXIT_NO_JEV_KEY
    languages = production_languages(args.languages)
    if not languages:
        LOGGER.info("kademe 1: üretimde dil yok (%s) — Jev'e haber gitmedi", args.languages)
        return 0
    questions = load_questions(args.questions)
    now = _now()
    # Varsayılan pencere: adayı hâlâ başlamamış olabilecek haberler (fikstür ufku kadar geri).
    since = args.since or now - HORIZON
    with connect() as conn, connect() as spend_conn:
        # Üretim dışı dilin haberi ne sorulur ne küme adayı olur: başlığı Jev'e hiç gitmez (R178).
        window = tuple(
            n for n in load_news(conn, since=since - CLUSTER_WINDOW) if n.lang in languages
        )
        ids = [item.item_id for item in window if item.item_id is not None]
        asked = asked_item_ids(conn, questions.prompt_version, ids)
        unasked = tuple(n for n in window if n.item_id not in asked and n.available_at >= since)
        # Başlamış maç için sorulan cevap hiçbir karara yetişmez; yalnız gelecek fikstürler.
        fixtures = load_fixtures(conn, since=now, until=now + HORIZON)
        attempts = failed_attempts(conn, questions.prompt_version, ids)
        # Tavan altında en yeni haber önce (I6); seçilenler partilerde zaman sırasıyla sorulur.
        items, deferred = newest_within_cap(
            unasked, fixtures, attempts=attempts, cap=args.max_calls
        )
        run, written, marked = _ask_in_batches(
            conn,
            budgeted_jev(jev, spend_conn, clock=_now),
            questions,
            items=items,
            # Pencerenin kalanı küme adayıdır: sorulmuşlar ve `since`ten önceki (72 saatlik) kuyruk.
            history=tuple(n for n in window if n.item_id in asked or n.available_at < since),
            fixtures=fixtures,
            attempts=attempts,
            max_calls=args.max_calls,
        )
    run = replace(run, deferred=run.deferred + deferred)
    _report(run, len(unasked), written, marked)
    return _tier1_exit(run)
```

(`from typing import Any` import'u; `conn: Any` — `psycopg.Connection[Any]` de olur, taklitler `# type: ignore`suz
geçsin diye `Any`.)

- [ ] **Step 9: En küçük uygulama — `.github/workflows/collect-news.yml`**

`timeout-minutes: 10` → `20` (yorum: "Plan 2: kademe 1 en çok 40 çağrı (`MAX_CALLS_PER_RUN`); gecikme Task 5'te
ölçülür."). "Secret taraması" adımına `id: secret_scan` (yoruma: "Taramadan sonra `success()`i ezen secret'lı
adımlar `steps.secret_scan.outcome`a bağlıdır (DEFERRED 19b)."). "Haberleri topla" adımına `id: fetch` ve gövdenin
`exit "$code"` satırından hemen önce:

```bash
          # Senkron ve kademe 1 bu koda bakar: 7 (bir kaynak düştü) onları durdurmaz, tur yine
          # kırmızı biter (Plan 2 I-6, I-7). Hiçbir kod yutulmaz.
          echo "code=$code" >> "$GITHUB_OUTPUT"
```

"Haber deposunu güncelle" adımının yorumundaki "Toplama kırmızıysa bu adım koşmaz" cümlesini "Toplama exit 7
(bir kaynak düştü) ise yine koşar — öbür kaynakların haberi bu turda depoya girer (Plan 2 I-6); başka bir
toplama kırmızısında koşmaz." ile değiştir ve adıma ekle:

```yaml
        if: ${{ !cancelled() && steps.secret_scan.outcome == 'success' && (success() || steps.fetch.outputs.code == '7') }}
```

Senkron adımından sonra, "Alarm aç"tan önce üç adım:

```yaml
      - name: Kademe 1 (Jev)
        id: tier1
        # Plan 2 R179: haber karar anından önce sorulmuş olmalı (asked_at < decided_at), bu yüzden
        # senkronun hemen ardından. Yalnız üretim dilleri (R178); tur başına 40 çağrı, parti başına
        # commit (I-8). Jev arızası haber turunu kırmızı yapmaz: `jev-kademe1` alarmı (R186).
        # Anahtar ücret yamasıyla gelir (R177): o güne dek 17 = "Jev kapalı", yeşil; yamanın
        # `JEV_ENABLED: "1"`i varken 17 kırmızıdır (I-5: boş/yanlış adlı secret sessiz kalmasın).
        if: ${{ !cancelled() && steps.secret_scan.outcome == 'success' && (success() || steps.fetch.outputs.code == '7') }}
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          set +e
          uv run python -m football_edge.features tier1
          code=$?
          set -e
          jev=fail
          case "$code" in
            0) jev=ok; echo "kademe 1 tamam" ;;
            17)
              if [ "${JEV_ENABLED:-}" = "1" ]; then
                echo "::error::tier1: JEV_ENABLED=1 ama TYPESAFE_API_KEY yok ya da boş (exit 17) — secret adını ve değerini denetle"
              else
                jev=ok
                echo "kademe 1: Jev kapalı (exit 17, anahtar yok) — sinyal toplanmıyor"
                echo "Jev kapalı: kademe 1 sorulmadı (anahtar yok; ücret yaması bekleniyor, R177)" >> "$GITHUB_STEP_SUMMARY"
              fi
              ;;
            7) echo "::error::tier1: Jev kesintisi (exit 7) — art arda Jev hatası, koşu durdu, sonraki tur yeniden sorar" ;;
            16) echo "::error::tier1: Jev aylık tavanı doldu (exit 16) — kalan haberler sorulmadı" ;;
            *) echo "::error::tier1 beklenmedik kodla düştü (exit $code)" ;;
          esac
          echo "jev=$jev" >> "$GITHUB_OUTPUT"
          # Haber turunun sonucu değil: Jev'in sonucu kendi alarmına gider (sonraki iki adım).
          exit 0
      - name: Jev alarmı aç
        # Kendi başlığı (`🔴 jev-kademe1 kırmızı`): tavan ayın kalanında kırmızı kalsa da gerçek bir
        # kaynak arızası `collect-news` alarmını bildirimle açar (DEFERRED 10h dersi, R186).
        if: ${{ !cancelled() && steps.tier1.outputs.jev == 'fail' }}
        env:
          GITHUB_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: uv run python scripts/ops_alert.py fail --workflow jev-kademe1 --run-url "$RUN_URL"
      - name: Jev alarmı kapat
        if: ${{ !cancelled() && steps.tier1.outputs.jev == 'ok' }}
        continue-on-error: true
        env:
          GITHUB_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: uv run python scripts/ops_alert.py ok --workflow jev-kademe1 --run-url "$RUN_URL"
```

- [ ] **Step 10: Koş — yeşil**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_calibration.py tests/test_feature_tier1.py tests/test_tier1_workflow.py tests/test_collect_workflows.py tests/test_news_sync_workflow.py tests/test_workflows.py tests/test_secrets_scan_netlify.py tests/test_jev_spend_paths.py -q && uv run mypy src scripts`
Expected: hepsi `passed` (`test_secrets_scan_netlify.py`: sync/tier1 adımları `steps.secret_scan.outcome`a bağlı;
`test_jev_spend_paths.py`: `jev` yalnız `budgeted_jev`in ilk argümanı); mypy `Success`.

- [ ] **Step 11: Mutasyon kanıtı (beş)**

(a) Yalnız sorulacaklar süzülür, PENCERE süzülmez (inceleme I1) — `F=src/football_edge/features/__main__.py`, OLD
`n for n in load_news(conn, since=since - CLUSTER_WINDOW) if n.lang in languages`, NEW
`n for n in load_news(conn, since=since - CLUSTER_WINDOW)`; test `tests/test_feature_tier1.py -k non_production`.
Expected: `exit=1`, `test_a_non_production_language_item_never_reaches_jev_even_as_earlier_news` kırmızı
(sorulmuş EN haber `history` → `earlier_news`; plan incelemesi kopyasında ölçüldü).

(e) En yeni önce kalkarsa (I6) — `F=src/football_edge/features/tier1.py`, OLD
`sorted(askable, key=_order, reverse=True)[cap:]`, NEW `sorted(askable, key=_order)[cap:]`; test
`tests/test_feature_tier1.py -k newest`. Expected: `exit=1`, `test_under_the_call_cap_the_newest_news_is_asked_first` kırmızı.

(b) Tavan bir fazla geçirirse — `F=src/football_edge/features/tier1.py`, OLD
`if max_calls is not None and calls >= max_calls:`, NEW `if max_calls is not None and calls > max_calls:`;
test `tests/test_feature_tier1.py -k "call_cap"`. Expected: `exit=1`, `test_the_call_cap_defers_the_rest_without_markers`
kırmızı (CLI'da tavanı `newest_within_cap` uygular; `run_tier1`deki sınır probe ve doğrudan çağrı içindir).

(c) Parti commit'i kalkarsa — `F=src/football_edge/features/__main__.py`, OLD
`        conn.commit()  # parti başına (I-8): zaman aşımı ödenmiş cevabı yutmaz
`, NEW `` (boş); test `tests/test_feature_tier1.py -k "batch"`. Expected: `exit=1`,
`test_each_batch_is_committed_before_the_next_is_asked` ve `test_a_run_killed_in_the_second_batch_keeps_the_first_batch` kırmızı.

(d) `JEV_ENABLED` yok sayılırsa — `F=.github/workflows/collect-news.yml`, OLD `if [ "${JEV_ENABLED:-}" = "1" ]; then`,
NEW `if false; then`; test `tests/test_tier1_workflow.py -k enabled-17`. Expected: `exit=1`, `[enabled-17]` kırmızı
(`jev=ok` döner, alarm açılmaz).

- [ ] **Step 12: Commit**

```bash
uv run ruff format src tests scripts
git add src/football_edge/calibration.py src/football_edge/features/tier1.py src/football_edge/features/__main__.py .github/workflows/collect-news.yml tests/jev_workflow_helpers.py tests/test_tier1_workflow.py tests/test_feature_tier1.py tests/test_calibration.py tests/test_collect_workflows.py tests/test_news_sync_workflow.py tests/test_workflows.py
git commit -F - <<'EOF'
feat: kademe 1 dil kapısı, tur tavanı ve parti commit'i; collect-news kademe 1 adımı ve jev-kademe1 alarmı

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 13: TAM KAPI** — Global Constraints'teki komut. Expected: `FAIL:` yok; `KAPI YEŞİL`.

---

### Task 3: Kademe 2 koşucusu — dondurulmuş küme + işletme ayarları, durum işaretleri, `features tier2`, `shadow.yml`

**Kademe:** K1

**Files:**
- Create: `config/faz4_live.yaml`, `config/faz4_ops.yaml`, `src/football_edge/features/live_config.py`,
  `src/football_edge/features/tier2.py`, `tests/fake_tier2_db.py`, `tests/test_feature_live_config.py`,
  `tests/test_feature_tier2.py`
- Modify: `src/football_edge/features/derive.py` (sona), `src/football_edge/jev.py:132-165`,
  `src/football_edge/jev_budget.py:253-265`, `src/football_edge/features/__main__.py` (`_parser`, `_live_config`,
  `_tier1` başı, tier2 komutu), `.github/workflows/shadow.yml`, `.github/workflows/collect-news.yml` (tier1 adımına
  `25)` kolu), `verify.sh` (`EXPECTED_MIN_LEAKAGE`)
- Test (Modify): `tests/test_feature_derive.py` (sona), `tests/test_feature_tier1.py` (`_cli`, iki `TypeSafeJev`
  taklidi, sona iki test), `tests/test_jev.py` (`_patch_sdk` + sona), `tests/test_jev_budget.py` (çıkış kodu
  sahipliği + sona), `tests/test_jev_item_answers_readers.py:38-61`, `tests/test_shadow_workflow.py`,
  `tests/jev_workflow_helpers.py` (`JEV_CASES`e 25)

**Interfaces:**
- Consumes: Task 1 `load_news`; Task 2 `production_languages`, `newest_within_cap`, `tests.jev_workflow_helpers`
  (`JEV_CASES`, `JEV_CASE_IDS`, `run_step`, `with_jev_key`, `JEV_SECRET`, `SWITCH`); `derive.select_items`,
  `derive.item_set_hash`, `derive.SideAnswer`; `tier1.gates_from`, `tier1.ItemAnswerRow`, `tier1.HORIZON`,
  `tier1.CLUSTER_WINDOW`, `tier1.OUTAGE_STREAK`, `tier1.FAILED_PREFIX`, `tier1.NO_MODEL`; `questions.for_team`.
- Produces:
  - `live_config`: `LIVE_CONFIG_PATH`, `OPS_CONFIG_PATH`, `EXIT_FROZEN_SET = 25`, `TIER1`, `TIER2`, `LiveConfigError`,
    `LiveConfig(tier1_prompt_version, jev_model, min_belongs, min_reliability, estimate_usd, max_sides_per_run,
    max_decision_age, prompt_version)`, `live_prompt_version(questions_bytes, live_bytes) -> str`,
    `load_live_config(path=LIVE_CONFIG_PATH, *, ops_path=OPS_CONFIG_PATH, questions_path=QUESTIONS_PATH) -> LiveConfig`,
    `frozen_violations(config, *, questions_prompt_version) -> tuple[str, ...]`.
  - `derive`: `NONE_LEVEL`, `LEVEL_SCORES`, `LevelAnswer(value, confidence)`, `IMPUTED`, `level_answer(...)`,
    `MatchAnswers(answers, imputed)`, `side_answers(names, *, home, away) -> MatchAnswers`.
  - `tier2`: `SHADOW_STRATEGIES`, `VARIANT_REAL`, `ITEM_LOOKBACK`, sonuçlar `ASKED, NO_NEWS, STALE, DEFERRED, ERROR,
    BUDGET, OUTAGE, MODEL_DRIFT` (`OUTCOMES`, öncelik sırası), `ANSWERED_BEFORE`, `STATUS_PREFIX = "side_status:"`,
    `status_question(side, outcome) -> str`, `is_status(question_id) -> bool`, `ASKED_MARKERS`,
    `final_status(outcomes) -> str`, `DECISIONS_SQL`, `INSERT_MATCH_ANSWERS`, `Decision`, `SideTask` (`.key`),
    `MatchAnswerRow`, `Tier2Run(rows, outcomes, failed, stop, model_drift)` (`.count()`, `.asked_sides`,
    `.budget_hit`, `.outage`), `gates_as_of`, `side_tasks` (İKİ taraf; haberi olmayanın kümesi boş),
    `side_battery`, `side_state`, `status_row`, `run_tier2(..., sink=_discard) -> Tier2Run`, `load_decisions`,
    `load_item_answers`, `answered_sides` (yalnız `asked` işareti), `write_match_answers`, `collect_tasks`.
  - `jev.TypeSafeJev(api_key=None, *, model: str | None = None)`;
    `jev_budget.budgeted_jev(jev, spend_conn, *, clock, estimate_usd=ESTIMATE_USD_UNMEASURED)`.
  - CLI: `features tier2 [--questions P] [--languages P] [--live-config P] [--ops-config P]` (exit 0/7/16/17/25);
    `features tier1` ayrıca `--live-config`, `--ops-config` alır (model + tahmin birimi; bozuk dosya 25).

**Kararlar:**
1. **Küme kimliği** `prompt_version = sha256(bytes(jev_questions.yaml) + bytes(faz4_live.yaml))`; yeni migration yok.
   `faz4_live.yaml` YALNIZ seçim-anlamlı alanları taşır (kademe 1 sürümü, model, `min_belongs`, `min_reliability`);
   tahmin birimi, taraf tavanı ve karar yaşı `faz4_ops.yaml`'dadır ve hash'e GİRMEZ — **spec R185'ten bilinçli sapma**
   (spec "tahmin birimleri"ni kümeye sayıyor): fiyat düzeltmesi seçim dilimi sayacını sıfırlamasın (inceleme M4;
   spec'i controller günceller).
2. **Model:** `jev_model` bugün `null`; Task 5 ölçer ve sabitler. Kademe 1 de bu modeli kullanır (inceleme I8; `null`
   iken hesabın varsayılanı). Sıra her iki komutta: küme dosyaları (bozuksa 25, inceleme M3) → anahtar (17) →
   (kademe 2) küme donmuş mu (25). Anahtarsız dönemde adımlar yeşil "Jev kapalı" kalır. SDK `system_one(..., model=)`
   kabul eder (typesafe-sdk 0.7); dönen model yine farklıysa o taraf YAZILMAZ, koşu 25 ile durur.
3. **Taraf durum işaretleri (inceleme I5):** her gölge (maç, karar anı, taraf) için `jev_match_answers`e bir işaret
   satırı: `question_id = side_status:<taraf>:<sonuç>`, `variant = real`, `choice` = sonuç, `probabilities
   {sonuç: 1.0}`, `confidence 1.0`, `cost 0`, `jev_model` = dönen model ya da `-`. Sonuçlar kodda gerçekten oluşanlar:
   `asked`, `no_news` (haberi yok → "yok" ataması, I-1), `stale` (M-2), `deferred` (taraf tavanı), `error` (tek
   Jev hatası), `budget`, `outage`, `model_drift` (durunca kalan taraflar da bu sebeple işaretlenir).
   `answered_before` işaretlenmez (zaten işareti var). Sonuç anahtarın parçası olduğu için bir taraf önce `budget`
   sonra `asked` alabilir; geçerli sonuç `final_status` önceliğidir. Cevaplanmış taraf (M-3) ve seçim dilimi (R181)
   YALNIZ `asked` işaretine bakar; özellik okuyucusu (Plan 3) `STATUS_PREFIX`i süzer. Böylece Plan 3 karar anındaki
   dil kümesini yeniden kurmaz.
4. **Kesinti:** art arda `OUTAGE_STREAK` hata ya da hiç taraf cevaplanmadı ve en az bir hata (inceleme I4) → 7.
5. `min_belongs = min_reliability = 0.5` başlangıçtır (açık soru 1); `max_sides_per_run = 80` (~40 maç × 2 taraf).
6. Taraf sırası ev → deplasman (inceleme C1: alfabetik sıra `away`ı önce sorardı).

- [ ] **Step 1: Başarısız testleri yaz — `tests/test_feature_live_config.py` (yeni)**

```python
"""Kademe 2'nin dondurulmuş kümesi (Plan 2 R185; I-11): `faz4_live.yaml` + `faz4_ops.yaml`."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path

import pytest

from football_edge.features.live_config import (
    TIER1,
    TIER2,
    LiveConfig,
    LiveConfigError,
    frozen_violations,
    live_prompt_version,
    load_live_config,
)
from football_edge.features.questions import load_questions

REPO = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = REPO / "config" / "jev_questions.yaml"
PV = load_questions(QUESTIONS_PATH).prompt_version
LIVE = (
    f"tier1_prompt_version: {PV}\njev_model: jev-2026-10\nmin_belongs: 0.5\nmin_reliability: 0.5\n"
)
OPS = (
    "estimate_usd:\n  tier1: 0.01\n  tier2: 0.02\n"
    "max_sides_per_run: 80\nmax_decision_age_hours: 6\n"
)


def _load(tmp_path: Path, live: str = LIVE, ops: str = OPS) -> LiveConfig:
    (tmp_path / "live.yaml").write_text(live, encoding="utf-8")
    (tmp_path / "ops.yaml").write_text(ops, encoding="utf-8")
    return load_live_config(
        tmp_path / "live.yaml", ops_path=tmp_path / "ops.yaml", questions_path=QUESTIONS_PATH
    )


def test_the_set_version_is_the_hash_of_questions_and_the_live_file_only(tmp_path: Path) -> None:
    config = _load(tmp_path)

    expected = hashlib.sha256(QUESTIONS_PATH.read_bytes() + LIVE.encode()).hexdigest()
    assert config.prompt_version == expected
    assert expected == live_prompt_version(QUESTIONS_PATH.read_bytes(), LIVE.encode())
    assert _load(tmp_path, live=LIVE + "# yorum\n").prompt_version != expected


def test_an_operational_change_keeps_the_set_and_its_counter(tmp_path: Path) -> None:
    """M4: birim fiyat ya da tavan düzeltmesi yeni küme DEĞİLDİR (sayaç sıfırlanmaz)."""
    config = _load(tmp_path)
    cheaper = _load(tmp_path, ops=OPS.replace("tier2: 0.02", "tier2: 0.015"))

    assert cheaper.prompt_version == config.prompt_version
    assert cheaper.estimate_usd[TIER2] == 0.015
    assert config.estimate_usd[TIER1] == 0.01
    assert config.max_decision_age == timedelta(hours=6)


@pytest.mark.parametrize(
    ("live_old", "live_new", "ops_old", "ops_new", "needle"),
    [
        ("min_reliability: 0.5\n", "", "", "", "alanlar"),
        ("", "", "max_sides_per_run: 80\n", "", "alanlar"),
        (
            f"tier1_prompt_version: {PV}",
            "tier1_prompt_version: abc",
            "",
            "",
            "tier1_prompt_version",
        ),
        ("jev_model: jev-2026-10", 'jev_model: ""', "", "", "jev_model"),
        ("min_belongs: 0.5", "min_belongs: 1.5", "", "", "min_belongs"),
        ("", "", "tier2: 0.02", "tier2: 0", "estimate_usd"),
        ("", "", "max_sides_per_run: 80", "max_sides_per_run: 0", "max_sides_per_run"),
        ("", "", "max_decision_age_hours: 6", "max_decision_age_hours: 7", "max_decision_age"),
    ],
)
def test_a_malformed_set_is_refused_by_name(
    tmp_path: Path, live_old: str, live_new: str, ops_old: str, ops_new: str, needle: str
) -> None:
    live = LIVE.replace(live_old, live_new) if live_old else LIVE
    ops = OPS.replace(ops_old, ops_new) if ops_old else OPS
    with pytest.raises(LiveConfigError, match=needle):
        _load(tmp_path, live=live, ops=ops)


@pytest.mark.parametrize(("model", "needle"), [("null", "sabitlenmedi"), ("jev-latest", "latest")])
def test_an_unpinned_model_is_not_a_frozen_set(tmp_path: Path, model: str, needle: str) -> None:
    config = _load(tmp_path, live=LIVE.replace("jev_model: jev-2026-10", f"jev_model: {model}"))

    (violation,) = frozen_violations(config, questions_prompt_version=PV)
    assert needle in violation


def test_a_changed_question_file_breaks_the_frozen_set(tmp_path: Path) -> None:
    config = _load(tmp_path)

    assert frozen_violations(config, questions_prompt_version=PV) == ()
    assert frozen_violations(config, questions_prompt_version="f" * 64) != ()


def test_the_committed_set_pins_todays_questions_and_the_spec_limits() -> None:
    config = load_live_config(
        REPO / "config" / "faz4_live.yaml",
        ops_path=REPO / "config" / "faz4_ops.yaml",
        questions_path=QUESTIONS_PATH,
    )
    found = frozen_violations(config, questions_prompt_version=PV)

    assert [violation for violation in found if "jev_model" not in violation] == []
    assert config.max_decision_age == timedelta(hours=6)
    assert (config.min_belongs, config.min_reliability, config.max_sides_per_run) == (0.5, 0.5, 80)
```

- [ ] **Step 2: Başarısız testleri yaz — "yok" ataması, `tests/test_feature_derive.py` sonuna**

Import: derive'dan `IMPUTED, LEVEL_SCORES, NONE_LEVEL, LevelAnswer, level_answer, side_answers`.

```python
def test_the_level_value_is_the_probability_weighted_scale() -> None:
    assert level_answer({"none": 0.5, "high": 0.5}, 0.8) == LevelAnswer(0.5, 0.8)
    assert level_answer({"none": 0.0}, 0.8) is None
    assert level_answer({"belki": 1.0}, 0.8) is None
    assert level_answer({"none": math.nan}, 0.8) is None


def test_an_unasked_side_is_imputed_at_the_none_level_and_counted() -> None:
    """I-1: haberi olmayan taraf sorulmaz; özellikte ölçeğin "yok" düzeyine deterministik atanır."""
    found = side_answers(["t2_x"], home=None, away={"t2_x": LevelAnswer(2 / 3, 0.7)})

    assert found.imputed == 1
    assert (IMPUTED.value, IMPUTED.confidence) == (LEVEL_SCORES[NONE_LEVEL], 1.0) == (0.0, 1.0)
    vector = features_of(found.answers, ["t2_x"], c_min=0.5)
    assert vector.values == pytest.approx((0.0 - 2 / 3,))
    assert vector.missing == 0


def test_an_asked_side_without_an_answer_stays_missing_not_imputed() -> None:
    found = side_answers(["t2_x", "t2_y"], home={"t2_x": LevelAnswer(1.0, 0.9)}, away={})

    assert found.imputed == 0
    assert features_of(found.answers, ["t2_x", "t2_y"], c_min=0.5).missing == 2
```

- [ ] **Step 3: Başarısız testleri yaz — `tests/fake_tier2_db.py` (yeni)**

```python
"""Kademe 2 sorguları için `FakeNewsDb` genişlemesi (Plan 2 Task 3; Task 4 dilim sorgusunu ekler).

Gölge satırları (`model_predictions` — YALNIZ varlık: maç, strateji, karar anı), `matches` adları,
kademe 1 cevap okuması ve `jev_match_answers` (tekil ve yabancı anahtar GERÇEKTEN uygulanır).
Tanımadığı sorguyu `FakeNewsDb`ye bırakır; o da tanımazsa reddeder. `SET TRANSACTION READ ONLY`den
sonra her INSERT reddedilir.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from tests.fake_news_db import FakeNewsDb, _Cursor

MATCH_ANSWER_COLUMNS = (
    "match_id",
    "decided_at",
    "prompt_version",
    "question_id",
    "variant",
    "item_set_hash",
    "choice",
    "probabilities",
    "confidence",
    "jev_model",
    "asked_at",
    "cost_usd",
)
_KEY = ("match_id", "decided_at", "prompt_version", "question_id", "variant")


@dataclass
class FakeTier2Db(FakeNewsDb):
    predictions: list[tuple[str, str, datetime]] = field(default_factory=list)
    matches: dict[str, tuple[str, str, datetime]] = field(default_factory=dict)
    match_answers: list[dict[str, Any]] = field(default_factory=list)
    read_only: bool = False

    def cursor(self) -> _Tier2Cursor:
        return _Tier2Cursor(self)


class _Tier2Cursor(_Cursor):
    def __init__(self, db: FakeTier2Db) -> None:
        super().__init__(db)
        self._t2 = db

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        if self._t2.read_only and text.startswith("INSERT"):
            raise AssertionError(f"salt okuma işleminde yazım: {text[:60]}")
        handler = self._handler(text)
        if handler is None:
            super().execute(sql, params)
            return
        self._t2.statements = [*self._t2.statements, text]
        handler(params)

    def _handler(self, text: str) -> Callable[[Any], None] | None:
        handlers: dict[str, Callable[[Any], None]] = {
            "SET TRANSACTION READ ONLY": self._set_read_only,
            "SELECT DISTINCT p.match_id, p.decided_at": self._decisions,
            "SELECT item_id, prompt_version, question_id": self._item_answers,
            "SELECT DISTINCT match_id, decided_at, split_part": self._answered,
            "INSERT INTO jev_match_answers": self._insert,
        }
        return next((h for prefix, h in handlers.items() if text.startswith(prefix)), None)

    def _set_read_only(self, _params: Any) -> None:
        self._t2.read_only = True
        self._result = []

    def _decisions(self, params: Any) -> None:
        since, until, strategies = params
        found = {
            (match, at)
            for match, strategy, at in self._t2.predictions
            if since <= at <= until and strategy in strategies
        }
        ordered = sorted(found, key=lambda pair: (pair[1], pair[0]))
        self._result = [(match, at, *self._t2.matches[match]) for match, at in ordered]

    def _item_answers(self, params: Any) -> None:
        version, item_ids, prefix = params
        rows = sorted(
            (
                r
                for r in self._t2.answers
                if r["prompt_version"] == version
                and r["item_id"] in item_ids
                and not r["question_id"].startswith(prefix)
            ),
            key=lambda r: (r["item_id"], r["question_id"]),
        )
        names = ("item_id", "prompt_version", "question_id", "choice")
        tail = ("confidence", "match_id", "jev_model", "asked_at", "cost_usd")
        self._result = [
            (*(r[n] for n in names), json.loads(r["probabilities"]), *(r[n] for n in tail))
            for r in rows
        ]

    def _answered(self, params: Any) -> None:
        version, variant, match_ids, question_ids = params
        self._result = sorted(
            {
                (r["match_id"], r["decided_at"], r["question_id"].split(":")[1])
                for r in self._t2.match_answers
                if r["prompt_version"] == version
                and r["variant"] == variant
                and r["match_id"] in match_ids
                and r["question_id"] in question_ids
            }
        )

    def _insert(self, params: Any) -> None:
        keys = {tuple(r[k] for k in _KEY) for r in self._t2.match_answers}
        self._result = []
        for index in range(len(params["match_id"])):
            row = {name: params[name][index] for name in MATCH_ANSWER_COLUMNS}
            if row["match_id"] not in self._t2.matches:
                raise AssertionError(f"matches'ta olmayan maç: {row['match_id']}")
            if not isinstance(json.loads(row["probabilities"]), dict):
                raise AssertionError("probabilities bir JSON nesnesi değil")
            key = tuple(row[k] for k in _KEY)
            if key in keys:
                continue
            keys = keys | {key}
            self._t2.match_answers = [*self._t2.match_answers, row]
            self._result.append((row["match_id"],))
```

- [ ] **Step 4: Başarısız testleri yaz — `tests/test_feature_tier2.py` (yeni)**

```python
"""Kademe 2 koşucusu (Plan 2 R180, R185; I-1…I-3, M-1…M-4): sahte Jev, ağ yok, para yok."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.derive import item_set_hash
from football_edge.features.live_config import EXIT_FROZEN_SET, LiveConfig
from football_edge.features.news import NewsDraft, news_hash, write_news
from football_edge.features.questions import (
    CLUSTER_QUESTION,
    MATCH_QUESTION,
    NEW_EVENT,
    RELIABILITY_QUESTION,
    load_questions,
)
from football_edge.features.tier1 import OUTAGE_STREAK, ItemAnswerRow, write_item_answers
from football_edge.features.tier2 import (
    ASKED,
    BUDGET,
    DECISIONS_SQL,
    ERROR,
    INSERT_MATCH_ANSWERS,
    ITEM_LOOKBACK,
    MODEL_DRIFT,
    NO_NEWS,
    OUTAGE,
    SHADOW_STRATEGIES,
    STALE,
    STATUS_PREFIX,
    VARIANT_REAL,
    Decision,
    MatchAnswerRow,
    SideTask,
    answered_sides,
    final_status,
    gates_as_of,
    is_status,
    load_decisions,
    run_tier2,
    side_battery,
    side_tasks,
    write_match_answers,
)
from football_edge.features.types import AWAY, BOTH, HOME, OBSERVED, StoredNews
from football_edge.jev import NO_MATCH, BatteryAnswer, Question
from football_edge.jev_budget import BudgetExceeded
from football_edge.live.store import BASE_STRATEGIES
from tests.fake_jev import FakeBatteryJev
from tests.fake_tier2_db import FakeTier2Db

REPO = Path(__file__).resolve().parent.parent
QUESTIONS = load_questions(REPO / "config" / "jev_questions.yaml")
T1_PV = QUESTIONS.prompt_version
DECIDED = datetime(2026, 10, 6, 11, 0, tzinfo=UTC)  # salı 12:00 Londra (BST)
NOW = DECIDED + timedelta(minutes=40)
DECISION = Decision("m-gs", DECIDED, "Galatasaray", "Fenerbahce", DECIDED + timedelta(days=4))
CONFIG = LiveConfig(
    tier1_prompt_version=T1_PV,
    jev_model="jev-fake",
    min_belongs=0.5,
    min_reliability=0.5,
    estimate_usd=MappingProxyType({"tier1": 0.01, "tier2": 0.01}),
    max_sides_per_run=80,
    max_decision_age=timedelta(hours=6),
    prompt_version="b" * 64,
)
TR = frozenset({"tr"})


def item(
    item_id: int, title: str, at: datetime = DECIDED - timedelta(days=1), lang: str = "tr"
) -> StoredNews:
    url = f"https://ajansspor.com/haber/{item_id}"
    digest = news_hash("ajansspor", url, title, None)
    return StoredNews(item_id, "ajansspor", lang, title, None, url, at, at, OBSERVED, digest)


def gate_rows(
    item_id: int,
    side: str,
    *,
    asked_at: datetime = DECIDED - timedelta(hours=20),
    belongs: float = 0.9,
    reliable: float = 0.9,
) -> tuple[ItemAnswerRow, ItemAnswerRow]:
    chosen = f"m-gs:{side}"
    match = MappingProxyType({chosen: belongs, NO_MATCH: 1 - belongs})
    trust = MappingProxyType({"official": reliable, "rumour": 1 - reliable})
    return (
        ItemAnswerRow(
            item_id, T1_PV, MATCH_QUESTION, chosen, match, 0.9, "m-gs", "jev-fake", asked_at, 0.001
        ),
        ItemAnswerRow(
            item_id,
            T1_PV,
            RELIABILITY_QUESTION,
            "official",
            trust,
            0.9,
            "m-gs",
            "jev-fake",
            asked_at,
            0.001,
        ),
    )


def tasks(
    items: Sequence[StoredNews], rows: Sequence[ItemAnswerRow], languages: frozenset[str] = TR
) -> tuple[SideTask, ...]:
    return side_tasks(DECISION, items, rows, config=CONFIG, languages=languages)


HOME_NEWS = item(1, "Galatasaray'da sakatlık")
AWAY_NEWS = item(2, "Fenerbahçe'de ceza", DECIDED - timedelta(hours=5))


def _home_and_away() -> tuple[SideTask, ...]:
    return tasks([HOME_NEWS, AWAY_NEWS], [*gate_rows(1, HOME), *gate_rows(2, AWAY)])


def answers(rows: Sequence[MatchAnswerRow]) -> list[MatchAnswerRow]:
    return [row for row in rows if not is_status(row.question_id)]


def statuses(rows: Sequence[MatchAnswerRow]) -> list[tuple[str, str]]:
    """(taraf, sonuç) — işaret satırlarının yazıldığı sırayla."""
    return [
        (row.question_id.split(":")[1], row.choice) for row in rows if is_status(row.question_id)
    ]


def run(
    task_list: Sequence[SideTask],
    client: Any,
    *,
    config: LiveConfig = CONFIG,
    at: datetime = NOW,
    answered: frozenset[Any] = frozenset(),
    sink: Any = None,
) -> Any:
    extra = {} if sink is None else {"sink": sink}
    return run_tier2(
        task_list, client, QUESTIONS, config=config, clock=lambda: at, answered=answered, **extra
    )


# ── Küme (sızıntı) ─────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_gates_use_only_tier1_answers_asked_before_the_decision() -> None:
    """I-3 / Review Focus 2: karar anında ya da sonra sorulan cevap kapıya girmez (eşit an da)."""
    rows = [
        *gate_rows(1, HOME, asked_at=DECIDED - timedelta(seconds=1)),
        *gate_rows(2, HOME, asked_at=DECIDED),
        *gate_rows(3, HOME, asked_at=DECIDED + timedelta(minutes=5)),
    ]

    assert set(gates_as_of(rows, DECIDED)) == {1}


def _chained(item_id: int, asked_at: datetime, parent: str) -> tuple[ItemAnswerRow, ...]:
    link = ItemAnswerRow(
        item_id,
        T1_PV,
        CLUSTER_QUESTION,
        parent,
        MappingProxyType({parent: 1.0}),
        0.9,
        "m-gs",
        "jev-fake",
        asked_at,
        0.0,
    )
    return (*gate_rows(item_id, HOME, asked_at=asked_at), link)


@pytest.mark.leakage
def test_a_cluster_link_answered_after_the_decision_does_not_merge_side_news() -> None:
    """I-3 uçtan uca: C ← A ← B zincirinde A'nın kademe 1 cevabı karardan SONRA sorulmuş. Karar
    anında A yoktu: B kendi kümesidir ve C ile birlikte sorulur. Tüm satırlardan kurulan kapı (A
    dâhil) B'yi C'nin kümesine katar ve B kümenin tekrarı diye düşerdi."""
    c = item(3, "Galatasaray'da sakatlık", DECIDED - timedelta(hours=30))
    a = item(4, "Galatasaray'da sakatlık sürüyor", DECIDED - timedelta(hours=20))
    b = item(5, "Galatasaray'da yeni gelişme", DECIDED - timedelta(hours=10))
    rows = [
        *_chained(3, DECIDED - timedelta(hours=29), NEW_EVENT),
        *_chained(4, DECIDED + timedelta(minutes=5), "item:3"),
        *_chained(5, DECIDED - timedelta(hours=9), "item:4"),
    ]

    home, _ = tasks([c, a, b], rows)

    assert [i.item_id for i in home.items] == [3, 5]


@pytest.mark.leakage
def test_a_side_set_holds_only_news_available_before_the_decision() -> None:
    exact = item(2, "Galatasaray'da ikinci haber", DECIDED)
    rows = [*gate_rows(1, HOME), *gate_rows(2, HOME, asked_at=DECIDED - timedelta(hours=1))]

    home, _ = tasks([HOME_NEWS, exact], rows)

    assert [i.item_id for i in home.items] == [1]


def test_the_news_window_is_fixed_to_the_decision() -> None:
    """M2: pencere karar anına göre sabit (`ITEM_LOOKBACK`): kenar dahil, 1 sn öncesi dışarıda."""
    edge = item(1, "Galatasaray'da kenar", DECIDED - ITEM_LOOKBACK)
    older = item(2, "Galatasaray'da eski", DECIDED - ITEM_LOOKBACK - timedelta(seconds=1))
    rows = [*gate_rows(1, HOME), *gate_rows(2, HOME)]

    home, _ = tasks([edge, older], rows)

    assert [i.item_id for i in home.items] == [1]


@pytest.mark.leakage
def test_the_decision_query_reads_shadow_existence_not_probabilities_or_results() -> None:
    """I-2, M-1: gölge satırından yalnız (maç, karar anı) VARLIĞI; olasılık/fiyat/sonuç okunmaz."""
    text = DECISIONS_SQL.lower()
    for forbidden in ("p_home", "p_draw", "p_away", "pre_", "odds_snapshots", "closing", "result"):
        assert forbidden not in text, forbidden
    assert "from model_predictions" in text
    assert "p.decided_at >= %s" in text, "M1: 6 saatlik sınır dahil (`_skip` ile aynı)"


@pytest.mark.leakage
def test_the_shadow_strategies_are_the_reports_base_strategies() -> None:
    """`features/` `live.store`u import edemez (spec §5/4): ad listesi burada eşitlenir."""
    assert set(SHADOW_STRATEGIES) == BASE_STRATEGIES


# ── Taraf kümeleri ve batarya ──────────────────────────────────────────────────────────────


def test_each_side_set_is_its_own_news_plus_news_about_both() -> None:
    both = item(3, "Derbi öncesi iki takım", DECIDED - timedelta(hours=10))
    rows = [*gate_rows(1, HOME), *gate_rows(2, AWAY), *gate_rows(3, BOTH)]

    home, away = tasks([HOME_NEWS, AWAY_NEWS, both], rows)

    assert (home.side, [i.item_id for i in home.items]) == (HOME, [1, 3])
    assert (away.side, [i.item_id for i in away.items]) == (AWAY, [3, 2])
    assert home.item_set_hash == item_set_hash(home.items) != away.item_set_hash


def test_a_side_without_news_gets_an_empty_set() -> None:
    home, away = tasks([HOME_NEWS], gate_rows(1, HOME))

    assert ([i.item_id for i in home.items], away.items) == ([1], ())


def test_news_below_the_frozen_gate_thresholds_is_not_in_a_side_set() -> None:
    rows = [*gate_rows(1, HOME, belongs=0.4), *gate_rows(2, AWAY, reliable=0.4)]

    assert [task.items for task in tasks([HOME_NEWS, AWAY_NEWS], rows)] == [(), ()]


def test_news_in_a_non_production_language_is_not_in_a_side_set() -> None:
    english = item(1, "Galatasaray injury update", lang="en")

    assert [task.items for task in tasks([english], gate_rows(1, HOME))] == [(), ()]


def test_one_side_battery_is_tiers_two_to_four_bound_to_the_team() -> None:
    battery = side_battery(QUESTIONS, side=AWAY, team="Fenerbahce")

    assert len(battery) == 30
    assert all(q.question_id.endswith(":away") and "Fenerbahce" in q.instructions for q in battery)


# ── Koşucu ve durum işaretleri ─────────────────────────────────────────────────────────────


def test_each_side_is_asked_once_home_first_and_written_as_real_rows_with_a_marker() -> None:
    client = FakeBatteryJev()

    result = run(_home_and_away(), client)

    assert [call["state"]["team"] for call in client.seen] == ["Galatasaray", "Fenerbahce"]
    assert [n["title"] for n in client.seen[0]["state"]["news"]] == ["Galatasaray'da sakatlık"]
    assert (result.asked_sides, len(answers(result.rows))) == (2, 60)
    assert statuses(result.rows) == [(HOME, ASKED), (AWAY, ASKED)]
    assert {(r.variant, r.prompt_version, r.asked_at) for r in result.rows} == {
        (VARIANT_REAL, CONFIG.prompt_version, NOW)
    }


def test_a_side_without_news_is_not_asked_and_is_marked_no_news() -> None:
    """I-1/I5: "yok" ataması `no_news` işaretinden türetilir; dil kümesi yeniden kurulmaz."""
    client = FakeBatteryJev()

    result = run(tasks([HOME_NEWS], gate_rows(1, HOME)), client)

    assert len(client.seen) == 1
    assert statuses(result.rows) == [(HOME, ASKED), (AWAY, NO_NEWS)]


def test_markers_are_never_answers_and_answers_never_markers() -> None:
    rows = run(_home_and_away(), FakeBatteryJev()).rows

    assert all(
        row.question_id.startswith(STATUS_PREFIX) == (row.choice in (ASKED,)) for row in rows
    )
    marker = next(row for row in rows if is_status(row.question_id))
    assert (marker.probabilities, marker.confidence, marker.cost_usd) == ({ASKED: 1.0}, 1.0, 0.0)


def test_the_final_status_lets_asked_override_an_earlier_stop() -> None:
    assert final_status([BUDGET, ASKED]) == ASKED
    assert final_status([ERROR, OUTAGE]) == ERROR
    assert final_status([NO_NEWS]) == NO_NEWS


def test_an_answered_side_is_not_asked_again_nor_marked_again() -> None:
    home, away = _home_and_away()
    client = FakeBatteryJev()

    result = run((home, away), client, answered=frozenset({home.key}))

    assert [call["state"]["team"] for call in client.seen] == ["Fenerbahce"]
    assert (result.count("answered_before"), statuses(result.rows)) == (1, [(AWAY, ASKED)])


@pytest.mark.parametrize(
    ("late", "asked"), [(timedelta(hours=6), 2), (timedelta(hours=6, seconds=1), 0)]
)
def test_a_decision_older_than_six_hours_is_not_asked(late: timedelta, asked: int) -> None:
    client = FakeBatteryJev()

    result = run(_home_and_away(), client, at=DECIDED + late)

    assert (len(client.seen), result.count(STALE)) == (asked, 2 - asked)


def test_the_side_cap_defers_the_rest_of_the_run() -> None:
    result = run(_home_and_away(), FakeBatteryJev(), config=replace(CONFIG, max_sides_per_run=1))

    assert statuses(result.rows) == [(HOME, ASKED), (AWAY, "deferred")]


def test_a_model_other_than_the_frozen_one_is_not_written_and_stops_the_run() -> None:
    handed: list[Any] = []

    result = run(_home_and_away(), FakeBatteryJev(jev_model="jev-yeni"), sink=handed.extend)

    assert (answers(handed), result.model_drift) == ([], "jev-yeni")
    assert statuses(handed) == [(HOME, MODEL_DRIFT), (AWAY, MODEL_DRIFT)]
    assert handed[0].jev_model == "jev-yeni"


def test_each_side_is_handed_to_the_sink_before_the_next_is_asked() -> None:
    client = FakeBatteryJev()
    handed: list[tuple[int, int]] = []

    run(_home_and_away(), client, sink=lambda rows: handed.append((len(rows), len(client.seen))))

    assert handed == [(31, 1), (31, 2)]


def test_a_missing_answer_leaves_its_question_out_and_counts_it_failed() -> None:
    home, _ = _home_and_away()

    result = run((home,), FakeBatteryJev(missing=frozenset({"t2_kaleci_eksik:home"})))

    assert (len(answers(result.rows)), result.failed) == (29, 1)


def test_consecutive_jev_errors_stop_the_run_as_an_outage() -> None:
    many = tuple(
        SideTask(replace(DECISION, match_id=f"m{n}"), HOME, "Galatasaray", (HOME_NEWS,), "c" * 64)
        for n in range(OUTAGE_STREAK + 1)
    )
    client = FakeBatteryJev(error=ConnectionError("jev kapalı"))

    result = run(many, client)

    assert result.outage and len(client.seen) == OUTAGE_STREAK and answers(result.rows) == []
    assert [s for _, s in statuses(result.rows)] == [ERROR] * OUTAGE_STREAK + [OUTAGE]


def test_the_budget_stops_the_run_and_keeps_the_side_already_paid_for() -> None:
    @dataclass
    class BudgetAfterOne(FakeBatteryJev):
        calls: list[int] = field(default_factory=list)

        def ask_battery(
            self, state: Mapping[str, Any], questions: Sequence[Question]
        ) -> BatteryAnswer:
            self.calls.append(1)
            if len(self.calls) > 1:
                raise BudgetExceeded("tavan")
            return super().ask_battery(state, questions)

    result = run(_home_and_away(), BudgetAfterOne())

    assert result.budget_hit and len(answers(result.rows)) == 30
    assert statuses(result.rows) == [(HOME, ASKED), (AWAY, BUDGET)]


# ── Veritabanı ve CLI ──────────────────────────────────────────────────────────────────────


def _db() -> FakeTier2Db:
    db = FakeTier2Db(now=DECIDED - timedelta(days=30))
    drafts = [
        NewsDraft(
            n.source_id, n.lang, n.title, None, n.url, n.available_at, OBSERVED, n.content_hash
        )
        for n in (HOME_NEWS, AWAY_NEWS)
    ]
    write_news(db, drafts)  # type: ignore[arg-type]
    write_item_answers(db, [*gate_rows(1, HOME), *gate_rows(2, AWAY)])  # type: ignore[arg-type]
    db.matches = {
        "m-gs": ("Galatasaray", "Fenerbahce", DECIDED + timedelta(days=4)),
        "m-eski": ("Besiktas JK", "Trabzonspor", DECIDED + timedelta(days=2)),
    }
    db.predictions = [
        *(("m-gs", strategy, DECIDED) for strategy in SHADOW_STRATEGIES),
        ("m-eski", "market", DECIDED - timedelta(days=3)),
        ("m-eski", "harman_jev", DECIDED),
    ]
    return db


def test_load_decisions_reads_this_rounds_base_shadow_rows_once_per_match() -> None:
    found = load_decisions(_db(), now=NOW, max_age=timedelta(hours=6))  # type: ignore[arg-type]

    assert found == (DECISION,)


@pytest.mark.parametrize(
    ("age", "found"), [(timedelta(hours=6), 1), (timedelta(hours=6, seconds=1), 0)]
)
def test_a_decision_exactly_six_hours_old_is_still_loaded(age: timedelta, found: int) -> None:
    """M1: yükleme sınırı `_skip` ile aynı — 6 saat dahil."""
    loaded = load_decisions(_db(), now=DECIDED + age, max_age=timedelta(hours=6))  # type: ignore[arg-type]

    assert len(loaded) == found


def test_the_insert_is_idempotent_on_the_unique_key() -> None:
    """I3: tekil anahtar SQL metninde; taklit uygulasa da asıl koruma bu cümledir."""
    assert (
        "ON CONFLICT (match_id, decided_at, prompt_version, question_id, variant) DO NOTHING"
        in INSERT_MATCH_ANSWERS
    )


def test_match_answers_are_written_once_and_only_asked_markers_close_a_side() -> None:
    db = _db()
    home, away = _home_and_away()
    rows = run((home,), FakeBatteryJev()).rows
    stopped = run((away,), FakeBatteryJev(error=ConnectionError("x"))).rows

    assert write_match_answers(db, [*rows, *stopped]) == 32  # type: ignore[arg-type]
    assert write_match_answers(db, rows) == 0  # type: ignore[arg-type]
    found = answered_sides(db, CONFIG.prompt_version, ["m-gs"])  # type: ignore[arg-type]
    assert found == {("m-gs", DECIDED, HOME)}, "hata işareti tarafı kapatmamalı (yeniden sorulur)"


def _config_files(tmp_path: Path, model: str = "jev-fake") -> list[str]:
    live, ops = tmp_path / "faz4_live.yaml", tmp_path / "faz4_ops.yaml"
    live.write_text(
        f"tier1_prompt_version: {T1_PV}\njev_model: {model}\nmin_belongs: 0.5\n"
        "min_reliability: 0.5\n",
        encoding="utf-8",
    )
    ops.write_text(
        "estimate_usd:\n  tier1: 0.01\n  tier2: 0.01\nmax_sides_per_run: 80\n"
        "max_decision_age_hours: 6\n",
        encoding="utf-8",
    )
    return ["--live-config", str(live), "--ops-config", str(ops)]


def _cli(monkeypatch: pytest.MonkeyPatch, db: Any, client: Any) -> None:
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "TypeSafeJev", lambda **_: client)
    monkeypatch.setattr(cli, "budgeted_jev", lambda jev, spend_conn, **_: jev)
    monkeypatch.setattr(cli, "production_languages", lambda path: TR)
    monkeypatch.setattr(cli, "_now", lambda: NOW)


def _explode(*_a: object, **_k: object) -> Any:
    raise AssertionError("veritabanına bağlanılmamalı")


def test_tier2_command_writes_each_side_and_commits_per_side(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db()
    _cli(monkeypatch, db, FakeBatteryJev())

    with caplog.at_level(logging.INFO):
        code = cli.main(["tier2", *_config_files(tmp_path)])

    assert code == 0
    assert (len(db.match_answers), db.commits) == (62, 2)
    assert "haberi olmayan taraf 0" in caplog.text


def test_a_second_tier2_run_buys_nothing_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Review Focus 3 (M-3): aynı gün yeniden koşulan gölge turu cevaplanmış tarafı satın almaz."""
    db, client = _db(), FakeBatteryJev()
    _cli(monkeypatch, db, client)
    argv = ["tier2", *_config_files(tmp_path)]

    cli.main(argv)
    cli.main(argv)

    assert (len(client.seen), len(db.match_answers)) == (2, 62)


def test_tier2_without_a_key_exits_17_before_the_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TYPESAFE" + "_API_KEY", raising=False)
    monkeypatch.setattr(cli, "connect", _explode)

    assert cli.main(["tier2", *_config_files(tmp_path, "null")]) == 17


def test_an_unpinned_model_with_a_key_exits_25_before_the_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _cli(monkeypatch, None, FakeBatteryJev())
    monkeypatch.setattr(cli, "connect", _explode)

    code = cli.main(["tier2", *_config_files(tmp_path, "null")])

    assert code == EXIT_FROZEN_SET == 25


def test_tier2_without_a_production_language_asks_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _cli(monkeypatch, None, FakeBatteryJev())
    monkeypatch.setattr(cli, "connect", _explode)
    monkeypatch.setattr(cli, "production_languages", lambda path: frozenset())

    assert cli.main(["tier2", *_config_files(tmp_path)]) == 0


@pytest.mark.parametrize(
    ("client", "code"),
    [(FakeBatteryJev(jev_model="jev-yeni"), 25), (FakeBatteryJev(error=ConnectionError("x")), 7)],
    ids=["model-drift", "no-side-answered"],
)
def test_tier2_exit_codes_by_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client: Any, code: int
) -> None:
    """I4: iki hatalı taraf `OUTAGE_STREAK` (3) altında ama HİÇBİR taraf cevaplanmadı: kesinti (7).
    Her iki durumda cevap satırı yazılmaz; yalnız durum işaretleri."""
    db = _db()
    _cli(monkeypatch, db, client)

    assert cli.main(["tier2", *_config_files(tmp_path)]) == code
    assert [row for row in db.match_answers if not is_status(row["question_id"])] == []
```

- [ ] **Step 5: Başarısız testleri yaz — kademe 1 küme dosyası, Jev istemcisi, bütçe, okuyucu mühürü, workflow'lar**

`tests/test_feature_tier1.py`: `_cli` içindeki `monkeypatch.setattr(cli, "TypeSafeJev", lambda: client)` →
`lambda **_: client`; `test_without_a_production_language_…`teki `lambda: FakeBatteryJev()` → `lambda **_: FakeBatteryJev()`;
`_budgeted` imzası `def _budgeted(jev: Any, spend_conn: Any, *, clock: Any, **_: Any) -> Any:`. Sona:

```python
# ── Plan 2 Task 3: kademe 1 küme dosyasından model ve tahmin birimi alır ──────────────────


def test_tier1_asks_with_the_frozen_model_and_the_tier1_estimate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I8: kademe 1 de `faz4_live.yaml`daki modeli kullanır; tahmin birimi `faz4_ops.yaml`dan."""
    live, ops = tmp_path / "live.yaml", tmp_path / "ops.yaml"
    live.write_text(
        f"tier1_prompt_version: {QUESTIONS.prompt_version}\njev_model: jev-2026-10\n"
        "min_belongs: 0.5\nmin_reliability: 0.5\n",
        encoding="utf-8",
    )
    ops.write_text(
        "estimate_usd:\n  tier1: 0.03\n  tier2: 0.01\nmax_sides_per_run: 80\n"
        "max_decision_age_hours: 6\n",
        encoding="utf-8",
    )
    built: list[Any] = []
    db = _db_with(news(1, "Galatasaray'da sakatlık"))
    _cli(monkeypatch, db, FakeBatteryJev())
    monkeypatch.setattr(cli, "TypeSafeJev", lambda **kw: built.append(kw) or FakeBatteryJev())
    monkeypatch.setattr(cli, "budgeted_jev", lambda jev, spend_conn, **kw: built.append(kw) or jev)

    assert cli.main(["tier1", "--live-config", str(live), "--ops-config", str(ops)]) == 0

    assert built[0] == {"model": "jev-2026-10"}
    assert built[1]["estimate_usd"] == 0.03


def test_tier1_with_a_broken_set_file_exits_25_before_the_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """M3: bozuk küme dosyası adlı kodla biter (exit 1 değil); veritabanına dokunulmaz."""

    def _explode() -> Any:
        raise AssertionError("bozuk küme dosyasıyla veritabanına bağlanılmamalı")

    broken = tmp_path / "live.yaml"
    broken.write_text("jev_model: null\n", encoding="utf-8")
    monkeypatch.setattr(cli, "connect", _explode)

    assert cli.main(["tier1", "--live-config", str(broken)]) == cli.EXIT_FROZEN_SET == 25
```

`tests/test_jev.py` `_patch_sdk`taki sahte `_Client.system_one` imzasına `model: str | None = None` ekle ve kaydı
`{"state": state, "questions": questions, "model": model}` yap. Sona:

```python
def test_a_pinned_model_is_sent_with_every_battery(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _patch_sdk(monkeypatch, _response({"a": _choice("evet")}))

    TypeSafeJev(api_key="k" * 16, model="jev-2026-10").ask_battery({}, [_question("a")])
    TypeSafeJev(api_key="k" * 16).ask_battery({}, [_question("a")])

    assert [call["model"] for call in recorder.calls if "model" in call] == ["jev-2026-10", None]
```

`tests/test_jev_budget.py`: `test_every_exit_code_name_owns_exactly_one_value_across_commands`in `modules` demetine
`"football_edge.features.live_config"`, sonuna `assert owners[25] == {"EXIT_FROZEN_SET"}`. Sona (import yoksa:
`FakeBatteryJev`, `FakeSpendConn`, `COST_UNPRICED`, `Question`):

```python
def test_budgeted_jev_takes_the_per_tier_estimate() -> None:
    conn = FakeSpendConn()
    client = budgeted_jev(  # type: ignore[arg-type]
        FakeBatteryJev(cost_basis=COST_UNPRICED), conn, clock=lambda: NOW, estimate_usd=0.05
    )

    client.ask_battery({}, [Question("q", "soru", {"a": "b"})])

    assert conn.inserted[0][2] == 0.05
```

`tests/test_jev_item_answers_readers.py`: `READERS`e `("features/tier2.py", "_ITEM_ANSWERS")` (yorum: "kademe 2 kapı
okuyucusu (Plan 2): işareti DIŞLAR, sonra `gates_as_of` → `gates_from`"); `DIRECTION`a
`("features/tier2.py", "_ITEM_ANSWERS"): re.compile(r"\bAND\s+NOT\s+starts_with\(question_id, %s\)")`.

`tests/jev_workflow_helpers.py`: `JEV_CASES` sonuna `(25, None, "fail", "küme"),`, `JEV_CASE_IDS` sonuna
`"frozen-25"` (kademe 1 ve 2 adımları 25'i adıyla karşılar; `test_tier1_workflow.py` değişmeden yeni vakayı koşar).

`tests/test_shadow_workflow.py`: import `from tests.jev_workflow_helpers import (JEV_CASE_IDS, JEV_CASES, JEV_SECRET,
SWITCH, run_step, with_jev_key)`, `import yaml`, `from typing import Any`.
**İnceleme C2:** `test_a_red_shadow_step_skips_the_report_and_still_raises_the_alarm` içinde
`_index_of(steps, "scripts/ops_alert.py fail")` → `_index_of(steps, "scripts/ops_alert.py fail --workflow shadow ")`
(yoksa iğne yeni `jev-kademe2` adımını yakalar ve `opens == len(steps) - 2` düşer).
`test_only_the_shadow_and_report_steps_get_the_database` yerine aşağıdaki `test_only_the_database_steps_get_the_database`
yazılır; geri kalanı sona eklenir:

```python
TIER2 = "football_edge.features tier2"
AFTER_SHADOW = (
    "${{ !cancelled() && steps.secret_scan.outcome == 'success' && "
    "steps.shadow.outcome == 'success' }}"
)
JEV2_OPEN_IF = "${{ !cancelled() && steps.tier2.outputs.jev == 'fail' }}"


def _at(steps: list[dict[str, Any]], needle: str) -> int:
    index = _index_of(steps, needle)
    assert index is not None, f"shadow.yml: {needle!r} adımı yok"
    return index


def test_only_the_database_steps_get_the_database() -> None:
    steps = _steps(SHADOW)
    shadow, report, tier2 = _at(steps, COMMAND), _at(steps, REPORT), _at(steps, TIER2)
    holders = [i for i, step in enumerate(steps) if "DATABASE_URL" in str(step.get("env", {}))]

    assert holders == [shadow, report, tier2]
    assert _at(steps, "scripts/check_secrets.sh") < shadow < report < tier2
```

```python
def test_tier2_runs_after_the_report_even_when_the_report_is_red() -> None:
    """R180/R186: maç kümesi bu turun gölge satırlarıdır — gölge yeşilse kademe 2 koşar."""
    steps = _steps(SHADOW)
    step = steps[_at(steps, TIER2)]

    env = dict(step["env"])

    assert (step["id"], step["if"]) == ("tier2", AFTER_SHADOW)
    assert env.pop("DATABASE_URL") == "${{ secrets.DATABASE_URL }}"
    assert env in ({}, SWITCH), "ücret anahtarı ile JEV_ENABLED birlikte gelir (R177, I-5)"


@pytest.mark.parametrize(
    ("code", "enabled", "jev", "named"),
    JEV_CASES,
    ids=JEV_CASE_IDS,
)
def test_the_tier2_step_never_turns_the_shadow_run_red_and_names_every_jev_outcome(
    tmp_path: Path, code: int, enabled: str | None, jev: str, named: str
) -> None:
    steps = _steps(SHADOW)

    run = run_step(tmp_path, str(steps[_at(steps, TIER2)]["run"]), code=code, jev_enabled=enabled)

    assert (run.returncode, run.outputs) == (0, {"jev": jev})
    if jev == "ok":
        assert run.errors == ()
    else:
        assert len(run.errors) == 1 and named in run.errors[0] and f"exit {code}" in run.errors[0]


def test_the_jev_key_may_reach_only_the_tier2_step() -> None:
    """Yamasız ve yamalı (R177) belge: anahtar ya hiçbir adımda ya YALNIZ kademe 2'de."""
    document = yaml.safe_load(SHADOW.read_text(encoding="utf-8"))

    for candidate in (document, with_jev_key(document, TIER2)):
        steps = candidate["jobs"]["shadow"]["steps"]
        holders = [i for i, step in enumerate(steps) if JEV_SECRET in str(step.get("env", {}))]
        assert holders in ([], [_at(steps, TIER2)])


def test_a_failed_tier2_opens_the_jev_kademe2_alarm_before_the_shadow_alarm() -> None:
    steps = _steps(SHADOW)
    tier2 = _at(steps, TIER2)
    opens = _at(steps, "scripts/ops_alert.py fail --workflow jev-kademe2 ")
    closes = _at(steps, "scripts/ops_alert.py ok --workflow jev-kademe2 ")

    assert tier2 < opens < closes < _at(steps, "scripts/ops_alert.py fail --workflow shadow ")
    assert steps[opens]["if"] == JEV2_OPEN_IF
```

- [ ] **Step 6: Koş — kırmızı**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_feature_live_config.py tests/test_feature_derive.py tests/test_feature_tier2.py tests/test_feature_tier1.py tests/test_jev.py tests/test_jev_budget.py tests/test_jev_item_answers_readers.py tests/test_shadow_workflow.py tests/test_tier1_workflow.py -q`
Expected: toplama hataları `ModuleNotFoundError: No module named 'football_edge.features.live_config'`,
`ImportError: cannot import name 'IMPUTED'`; workflow testleri "adımı yok" ve `[frozen-25]` ile kırmızı.

- [ ] **Step 7: En küçük uygulama — `config/faz4_live.yaml`, `config/faz4_ops.yaml`, `features/live_config.py`**

`tier1_prompt_version` plan yazımında ölçüldü (`a967064c…d988b`); implementer yeniden ölçer:
`PYTHONDONTWRITEBYTECODE=1 uv run python -c "from pathlib import Path; from football_edge.features.questions import load_questions; print(load_questions(Path('config/jev_questions.yaml')).prompt_version)"`.

```yaml
# Kademe 2'nin dondurulmuş kümesi (Faz 4 Plan 2 R185; I-11) — YALNIZ seçim-anlamlı alanlar. Bu
# dosyanın BAYTLARI soru dosyasının baytlarıyla birlikte her kademe 2 satırının `prompt_version`ına
# girer: prompt_version = sha256(bytes(config/jev_questions.yaml) + bytes(config/faz4_live.yaml)).
# Tek karakter (yorum dâhil) değişirse YENİ küme doğar; `features slice-status` küme başına sayar.
# İşletme ayarları (tahmin birimi, taraf tavanı, karar yaşı) config/faz4_ops.yaml'dadır, hash'e girmez.
#
# jev_model: Task 5 tek gerçek çağrıyla ölçer ve sabitler; null iken (anahtar varsa) `features tier2`
# EXIT_FROZEN_SET (25); kademe 1 null iken hesabın varsayılan modelini kullanır. 'latest' kabul edilmez.
# min_belongs / min_reliability: kademe 1 kapı eşikleri (başlangıç; ilk gerçek yazımdan önce donar).
tier1_prompt_version: a967064cf504f90fe696f01dae0c24e8f701e4b30739376770fc9248c54d988b
jev_model: null
min_belongs: 0.5
min_reliability: 0.5
```

```yaml
# Kademe 1/2 işletme ayarları (Faz 4 Plan 2). Dondurulmuş kümenin (config/faz4_live.yaml) hash'ine
# GİRMEZ: birim fiyat düzeltmesi seçim dilimi sayacını sıfırlamaz.
#
# estimate_usd: kademe başına tahmin birimi ($/çağrı); SDK maliyet bildirmez — kullanıcı TypeSafe
# panelinden okur (R184, I-9). max_sides_per_run: kademe 2 tur tavanı (I-8).
# max_decision_age_hours: M-2 (spec: 6 saat, üst sınır).
estimate_usd:
  tier1: 0.01
  tier2: 0.01
max_sides_per_run: 80
max_decision_age_hours: 6
```

`src/football_edge/features/live_config.py`:

```python
"""Kademe 2'nin dondurulmuş kümesi (Plan 2 R185; I-11) ve işletme ayarları.

İki dosya. `config/faz4_live.yaml` SEÇİM-ANLAMLI alanları taşır (kademe 1 sürümü, Jev modeli, kapı
eşikleri); kümenin kimliği bu dosyanın KENDİSİDİR: `prompt_version = sha256(soru dosyası + bu
dosya)` her kademe 2 satırına girer (yeni migration yok; 0012'nin `^[0-9a-f]{64}$` kısıtı).
`config/faz4_ops.yaml` işletme ayarlarını taşır (tahmin birimi, taraf tavanı, karar yaşı) ve
hash'e GİRMEZ: fiyat düzeltmesi seçim dilimi sayacını sıfırlamaz (spec R185'ten bilinçli sapma).
`frozen_violations` kümenin YAZIMA hazır olduğunu sorar (model sabit, kademe 1 sürümü güncel).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from football_edge.features.questions import QUESTIONS_PATH

LIVE_CONFIG_PATH = Path("config/faz4_live.yaml")
OPS_CONFIG_PATH = Path("config/faz4_ops.yaml")
# Dondurulmuş küme eksik/bozuk ya da dönen model kümedekinden farklı (collect 2–8, backtest 9–14,
# live 15/18, bütçe 16, Jev anahtarı 17, boş tur 19, site 20–24).
EXIT_FROZEN_SET = 25
TIER1 = "tier1"
TIER2 = "tier2"
MAX_DECISION_AGE_HOURS = 6  # spec M-2: daha uzun pencere kabul edilmez
_LIVE_KEYS = frozenset({"tier1_prompt_version", "jev_model", "min_belongs", "min_reliability"})
_OPS_KEYS = frozenset({"estimate_usd", "max_sides_per_run", "max_decision_age_hours"})
_SHA = re.compile(r"^[0-9a-f]{64}$")


class LiveConfigError(ValueError):
    """`config/faz4_live.yaml` ya da `config/faz4_ops.yaml` sözleşmeye uymuyor; alan adıyla."""


@dataclass(frozen=True)
class LiveConfig:
    tier1_prompt_version: str
    jev_model: str | None
    min_belongs: float
    min_reliability: float
    estimate_usd: Mapping[str, float]
    max_sides_per_run: int
    max_decision_age: timedelta
    prompt_version: str


def live_prompt_version(questions_bytes: bytes, live_bytes: bytes) -> str:
    return hashlib.sha256(questions_bytes + live_bytes).hexdigest()


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _unit(raw: Mapping[str, Any], key: str) -> float:
    value = raw[key]
    if not _number(value) or not 0.0 <= value <= 1.0:
        raise LiveConfigError(f"{key}: 0 ile 1 arasında sayı olmalı ({value!r})")
    return float(value)


def _whole(raw: Mapping[str, Any], key: str, low: int, high: int) -> int:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise LiveConfigError(f"{key}: {low}–{high} arası tam sayı olmalı ({value!r})")
    return value


def _estimates(raw: Mapping[str, Any]) -> Mapping[str, float]:
    found = raw["estimate_usd"]
    if not isinstance(found, Mapping) or set(found) != {TIER1, TIER2}:
        raise LiveConfigError(f"estimate_usd: tam olarak {TIER1} ve {TIER2} olmalı")
    for key, value in found.items():
        if not _number(value) or not (math.isfinite(value) and value > 0):
            raise LiveConfigError(f"estimate_usd.{key}: sonlu ve > 0 olmalı ({value!r})")
    return MappingProxyType({str(k): float(v) for k, v in found.items()})


def _model(raw: Mapping[str, Any]) -> str | None:
    value = raw["jev_model"]
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise LiveConfigError(f"jev_model: null ya da boş olmayan metin olmalı ({value!r})")
    return value


def _mapping(path: Path, keys: frozenset[str]) -> tuple[bytes, Mapping[str, Any]]:
    content = path.read_bytes()
    raw = yaml.safe_load(content)
    if not isinstance(raw, Mapping) or set(raw) != keys:
        raise LiveConfigError(f"{path}: alanlar tam olarak {sorted(keys)} olmalı")
    return content, raw


def load_live_config(
    path: Path = LIVE_CONFIG_PATH,
    *,
    ops_path: Path = OPS_CONFIG_PATH,
    questions_path: Path = QUESTIONS_PATH,
) -> LiveConfig:
    content, live = _mapping(path, _LIVE_KEYS)
    _, ops = _mapping(ops_path, _OPS_KEYS)
    version = live["tier1_prompt_version"]
    if not isinstance(version, str) or _SHA.fullmatch(version) is None:
        raise LiveConfigError(f"tier1_prompt_version: 64 haneli sha256 olmalı ({version!r})")
    hours = _whole(ops, "max_decision_age_hours", 1, MAX_DECISION_AGE_HOURS)
    return LiveConfig(
        tier1_prompt_version=version,
        jev_model=_model(live),
        min_belongs=_unit(live, "min_belongs"),
        min_reliability=_unit(live, "min_reliability"),
        estimate_usd=_estimates(ops),
        max_sides_per_run=_whole(ops, "max_sides_per_run", 1, 1000),
        max_decision_age=timedelta(hours=hours),
        prompt_version=live_prompt_version(questions_path.read_bytes(), content),
    )


def frozen_violations(config: LiveConfig, *, questions_prompt_version: str) -> tuple[str, ...]:
    """Kademe 2 YAZIMINA engeller: model sabit değil ya da kademe 1 sürümü eski soru dosyası."""
    found: tuple[str, ...] = ()
    if config.jev_model is None:
        found = (*found, "jev_model sabitlenmedi (null) — Plan 2 Task 5 ölçer ve sabitler")
    elif "latest" in config.jev_model.casefold():
        found = (*found, f"jev_model {config.jev_model!r}: 'latest' takma adı sabit değildir")
    if config.tier1_prompt_version != questions_prompt_version:
        found = (
            *found,
            "tier1_prompt_version soru dosyasının bugünkü sha256'sı değil — kademe 1 cevapları "
            "başka bir sürüme ait; yeni küme gerekir",
        )
    return found
```

- [ ] **Step 8: En küçük uygulama — `derive.py`, `jev.py`, `jev_budget.py`**

`derive.py` import'una `from types import MappingProxyType`; sona:

```python
# ── Taraf cevapları ve "yok" ataması (Plan 2 I-1) ───────────────────────────────────────────

NONE_LEVEL = "none"
# Dört düzeyli ortak ölçeğin (`questions.LEVEL_CRITERIA`) sayısal karşılığı: eşit aralıklı [0, 1].
LEVEL_SCORES: Mapping[str, float] = MappingProxyType(
    {"none": 0.0, "low": 1 / 3, "medium": 2 / 3, "high": 1.0}
)


@dataclass(frozen=True)
class LevelAnswer:
    value: float
    confidence: float


# Haberi olmadığı için SORULMAYAN taraf: "yok" düzeyi, tam güven (eksik değil, atanmış — `imputed`).
IMPUTED = LevelAnswer(LEVEL_SCORES[NONE_LEVEL], 1.0)


def level_answer(probabilities: Mapping[str, float], confidence: float) -> LevelAnswer | None:
    """Olasılık ağırlıklı ölçek değeri ∈ [0, 1]; ölçek dışı, sonlu olmayan ya da boş → None."""
    if not probabilities or not set(probabilities) <= set(LEVEL_SCORES):
        return None
    if not all(math.isfinite(v) and v >= 0 for v in (*probabilities.values(), confidence)):
        return None
    total = math.fsum(probabilities.values())
    if total <= 0:
        return None
    weighted = math.fsum(LEVEL_SCORES[key] * p for key, p in probabilities.items())
    return LevelAnswer(weighted / total, confidence)


@dataclass(frozen=True)
class MatchAnswers:
    answers: Mapping[str, SideAnswer]
    imputed: int  # "yok" atanan (sorulmayan) taraf sayısı


def _pick(side: Mapping[str, LevelAnswer] | None, name: str) -> LevelAnswer | None:
    return IMPUTED if side is None else side.get(name)


def side_answers(
    names: Sequence[str],
    *,
    home: Mapping[str, LevelAnswer] | None,
    away: Mapping[str, LevelAnswer] | None,
) -> MatchAnswers:
    """`None` taraf = haberi olmadığı için SORULMADI: her soruda "yok" (I-1), `imputed` sayılır.
    Sorulmuş ama cevabı gelmemiş soru eksik kalır (`features_of` → 0 ve `missing`)."""
    answers: dict[str, SideAnswer] = {}
    for name in names:
        home_answer, away_answer = _pick(home, name), _pick(away, name)
        given = [a.confidence for a in (home_answer, away_answer) if a is not None]
        answers[name] = SideAnswer(
            home=None if home_answer is None else home_answer.value,
            away=None if away_answer is None else away_answer.value,
            confidence=min(given, default=0.0),
        )
    return MatchAnswers(MappingProxyType(answers), imputed=(home is None) + (away is None))
```

`jev.py` `TypeSafeJev.__init__` imzası `(self, api_key: str | None = None, *, model: str | None = None)`; gövdenin
sonuna `self._model = model  # Plan 2 R185: kademe 2 sabit modelle sorar; None = hesabın varsayılanı`; iki
`client.system_one(` çağrısına `model=self._model,` argümanı. Docstring'e: "`model` her istekte gönderilir; dönen
model yine `BatteryAnswer.jev_model`dedir — çağıran karşılaştırır (kademe 2)."

`jev_budget.py` `budgeted_jev`: imzaya `estimate_usd: float = ESTIMATE_USD_UNMEASURED` (anahtar-yalnız, `clock`tan
sonra); `BudgetedJev(..., estimate_usd=estimate_usd, ...)`; docstring'e "`estimate_usd`: kademe başına tahmin birimi
(`config/faz4_ops.yaml`, Plan 2)."

- [ ] **Step 9: En küçük uygulama — `src/football_edge/features/tier2.py`**

```python
"""Kademe 2: karar anında taraf başına batarya (Plan 2 R180, R185; spec §5/1, §6).

Maç kümesi bu turun GÖLGE satırlarıdır: `model_predictions`te `(match_id, decided_at)` VARLIĞI
okunur, olasılık okunmaz (I-2, M-1). Haber kümesi `derive.select_items` (`available_at <
decided_at`; canlıda kademe 1 `asked_at < decided_at`); kademe 1 kapıları yalnız karardan ÖNCE
sorulmuş cevaplardan kurulur (I-3, `gates_as_of`). Taraf kümesi ev = ev ∪ ikisi, deplasman =
deplasman ∪ ikisi; `item_set_hash` taraf başına (M-4). Taraf başına TEK batarya: T2 + T3 + T4 (30
soru), kimlik `<soru>:<taraf>`. Haberi olmayan taraf SORULMAZ — özellikte "yok" atanır
(`derive.side_answers`, I-1). Yalnız `variant = real` (kanarya arşiv içindi, R167).

Taraf durumu (inceleme I5): her gölge (maç, karar anı, taraf) için sonuç bir İŞARET satırıdır
— `question_id = side_status:<taraf>:<sonuç>`, `choice` = sonuç (`OUTCOMES`), olasılık
`{sonuç: 1}`, maliyet 0 (tier1'in `t1_failed:<n>` deseni). Plan 3 karar anındaki dil kümesini ve
"yok" atamasını (`no_news`) yeniden kurmaz, buradan okur; özellik okuyucusu `STATUS_PREFIX`i süzer.
Bir tarafın birden çok işareti olabilir (önce `budget`, sonra `asked`); geçerli sonuç
`final_status` önceliğidir. Cevaplanmış taraf = `asked` işareti (M-3).

Korumalar: karardan `max_decision_age` (6 sa) sonra sormaz (M-2); dönen model kümedekinden farklıysa
YAZMAZ, durur (R185); tur başına taraf tavanı, taraf başına `sink` (CLI'da yaz + commit, I-8); art
arda `OUTAGE_STREAK` Jev hatası kesintidir.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any

import psycopg

from football_edge.features.derive import item_set_hash, select_items
from football_edge.features.live_config import LiveConfig
from football_edge.features.news import load_news
from football_edge.features.questions import QuestionSet, for_team
from football_edge.features.tier1 import (
    CLUSTER_WINDOW,
    FAILED_PREFIX,
    HORIZON,
    NO_MODEL,
    OUTAGE_STREAK,
    ItemAnswerRow,
    gates_from,
)
from football_edge.features.types import AWAY, BOTH, HOME, ItemGate, StoredNews
from football_edge.jev import BatteryAnswer, ChoiceAnswer, JevClient, Question
from football_edge.jev_budget import BudgetExceeded

LOGGER = logging.getLogger("football_edge.features.tier2")

# Gölge raporunun baz stratejileri (`live.store.BASE_STRATEGIES`): o modül `features/`ten import
# edilemez (spec §5/4) — eşitliği `tests/test_feature_tier2.py` sabitler.
SHADOW_STRATEGIES: tuple[str, ...] = ("dixon_coles", "elo_fit", "market")
VARIANT_REAL = "real"
# Haber penceresi karar anına göre sabit: kademe 1 ufku + küme penceresi (yeniden üretilebilir).
ITEM_LOOKBACK = HORIZON + CLUSTER_WINDOW
_MEMBERS: Mapping[str, frozenset[str]] = MappingProxyType(
    {HOME: frozenset({HOME, BOTH}), AWAY: frozenset({AWAY, BOTH})}
)
_SIDE_ORDER = (HOME, AWAY)

# Taraf sonuçları — öncelik sırasıyla (`final_status`). `ANSWERED_BEFORE` sayılır, işaretlenmez.
ASKED = "asked"
NO_NEWS = "no_news"
STALE = "stale"
DEFERRED = "deferred"
ERROR = "error"
BUDGET = "budget"
OUTAGE = "outage"
MODEL_DRIFT = "model_drift"
OUTCOMES = (ASKED, NO_NEWS, STALE, DEFERRED, ERROR, BUDGET, OUTAGE, MODEL_DRIFT)
ANSWERED_BEFORE = "answered_before"
STATUS_PREFIX = "side_status:"


def status_question(side: str, outcome: str) -> str:
    if side not in _SIDE_ORDER or outcome not in OUTCOMES:
        raise ValueError(f"bilinmeyen taraf ya da sonuç: {side!r}, {outcome!r}")
    return f"{STATUS_PREFIX}{side}:{outcome}"


def is_status(question_id: str) -> bool:
    """İşaret satırı cevap değildir: özellik okuyucusu bunu süzer (Plan 3)."""
    return question_id.startswith(STATUS_PREFIX)


# Cevaplanmış taraf (M-3) ve seçim dilimi (R181) yalnız bu işaretlere bakar.
ASKED_MARKERS: tuple[str, ...] = tuple(status_question(side, ASKED) for side in _SIDE_ORDER)


def final_status(outcomes: Iterable[str]) -> str:
    """Bir tarafın geçerli sonucu: `OUTCOMES` sırasında ilk görülen (`asked` her şeyi ezer)."""
    found = set(outcomes)
    return next(outcome for outcome in OUTCOMES if outcome in found)


@dataclass(frozen=True)
class Decision:
    match_id: str
    decided_at: datetime
    home: str
    away: str
    kickoff: datetime


@dataclass(frozen=True)
class SideTask:
    decision: Decision
    side: str
    team: str
    items: tuple[StoredNews, ...]
    item_set_hash: str

    @property
    def key(self) -> tuple[str, datetime, str]:
        return self.decision.match_id, self.decision.decided_at, self.side


@dataclass(frozen=True)
class MatchAnswerRow:
    match_id: str
    decided_at: datetime
    prompt_version: str
    question_id: str
    variant: str
    item_set_hash: str
    choice: str
    probabilities: Mapping[str, float]
    confidence: float
    jev_model: str
    asked_at: datetime
    cost_usd: float


@dataclass(frozen=True)
class Tier2Run:
    rows: tuple[MatchAnswerRow, ...]  # cevaplar + durum işaretleri
    outcomes: Mapping[str, int]  # sonuç → taraf sayısı (`ANSWERED_BEFORE` dâhil)
    failed: int  # cevapsız ya da geçersiz soru
    stop: str | None = None  # BUDGET | OUTAGE | MODEL_DRIFT: kalan taraflar sorulmadı
    model_drift: str | None = None  # dönen model (cevabı yazılmadı)

    def count(self, outcome: str) -> int:
        return self.outcomes.get(outcome, 0)

    @property
    def asked_sides(self) -> int:
        return self.count(ASKED)

    @property
    def budget_hit(self) -> bool:
        return self.stop == BUDGET

    @property
    def outage(self) -> bool:
        return self.stop == OUTAGE


# ── Küme ───────────────────────────────────────────────────────────────────────────────────


def gates_as_of(rows: Sequence[ItemAnswerRow], decided_at: datetime) -> Mapping[int, ItemGate]:
    """Kademe 1 kapıları yalnız karardan ÖNCE sorulmuş cevaplardan (I-3): sonra sorulan cevap ne
    kapıyı ne kümelemeyi etkiler. Tam eşit an DIŞARIDADIR (`derive` modül belgesi)."""
    if decided_at.tzinfo is None:
        raise ValueError("decided_at saat dilimsiz")
    return gates_from([row for row in rows if row.asked_at < decided_at])


def side_tasks(
    decision: Decision,
    items: Sequence[StoredNews],
    item_rows: Sequence[ItemAnswerRow],
    *,
    config: LiveConfig,
    languages: frozenset[str],
) -> tuple[SideTask, ...]:
    """Kararın İKİ tarafı; haberi olmayan tarafın kümesi boştur (sorulmaz, `no_news`, I-1).
    Yalnız üretim dili (R178) ve karar anına göre sabit pencere (`ITEM_LOOKBACK`)."""
    window = tuple(
        item
        for item in items
        if item.lang in languages and item.available_at >= decision.decided_at - ITEM_LOOKBACK
    )
    ids = {item.item_id for item in window}
    gates = gates_as_of([row for row in item_rows if row.item_id in ids], decision.decided_at)
    usable = select_items(
        window,
        gates,
        match_id=decision.match_id,
        decided_at=decision.decided_at,
        live=True,
        min_belongs=config.min_belongs,
        min_reliability=config.min_reliability,
    )
    found: tuple[SideTask, ...] = ()
    for side, team in ((HOME, decision.home), (AWAY, decision.away)):
        members = tuple(
            item
            for item in usable
            if item.item_id is not None and gates[item.item_id].side in _MEMBERS[side]
        )
        found = (*found, SideTask(decision, side, team, members, item_set_hash(members)))
    return found


# ── Batarya ────────────────────────────────────────────────────────────────────────────────


def side_battery(questions: QuestionSet, *, side: str, team: str) -> tuple[Question, ...]:
    return tuple(
        for_team(question, side=side, team=team)
        for question in (*questions.tier2, *questions.tier3, *questions.tier4)
    )


def side_state(task: SideTask) -> Mapping[str, Any]:
    decision = task.decision
    return {
        "match": {
            "home": decision.home,
            "away": decision.away,
            "kickoff": decision.kickoff.isoformat(),
        },
        "team": task.team,
        "news": [
            {
                "title": item.title,
                "source": item.source_id,
                "language": item.lang,
                "available_at": item.available_at.isoformat(),
            }
            for item in task.items
        ],
    }


def _valid(answer: ChoiceAnswer, question: Question) -> bool:
    values = (answer.confidence, *answer.probabilities.values())
    return (
        answer.choice in question.criteria
        and set(answer.probabilities) <= set(question.criteria)
        and all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values)
    )


def side_rows(
    task: SideTask,
    battery: Sequence[Question],
    answer: BatteryAnswer,
    *,
    prompt_version: str,
    asked_at: datetime,
) -> tuple[MatchAnswerRow, ...]:
    cost = answer.cost_usd / len(battery)
    return tuple(
        MatchAnswerRow(
            match_id=task.decision.match_id,
            decided_at=task.decision.decided_at,
            prompt_version=prompt_version,
            question_id=question.question_id,
            variant=VARIANT_REAL,
            item_set_hash=task.item_set_hash,
            choice=given.choice,
            probabilities=MappingProxyType(dict(given.probabilities)),
            confidence=given.confidence,
            jev_model=answer.jev_model,
            asked_at=asked_at,
            cost_usd=cost,
        )
        for question in battery
        if (given := answer.answers.get(question.question_id)) is not None
        and _valid(given, question)
    )


# ── Koşucu ─────────────────────────────────────────────────────────────────────────────────

Sink = Callable[[tuple[MatchAnswerRow, ...]], None]


def _discard(rows: tuple[MatchAnswerRow, ...]) -> None:
    return None


def status_row(
    task: SideTask, outcome: str, *, prompt_version: str, at: datetime, jev_model: str = NO_MODEL
) -> MatchAnswerRow:
    return MatchAnswerRow(
        match_id=task.decision.match_id,
        decided_at=task.decision.decided_at,
        prompt_version=prompt_version,
        question_id=status_question(task.side, outcome),
        variant=VARIANT_REAL,
        item_set_hash=task.item_set_hash,
        choice=outcome,
        probabilities=MappingProxyType({outcome: 1.0}),
        confidence=1.0,
        jev_model=jev_model,
        asked_at=at,
        cost_usd=0.0,
    )


def _skip(
    task: SideTask,
    *,
    answered: frozenset[tuple[str, datetime, str]],
    now: datetime,
    config: LiveConfig,
    asked: int,
) -> str | None:
    if task.key in answered:
        return ANSWERED_BEFORE
    if not task.items:
        return NO_NEWS
    if now - task.decision.decided_at > config.max_decision_age:
        return STALE
    if asked >= config.max_sides_per_run:
        return DEFERRED
    return None


def _ask(
    task: SideTask,
    client: JevClient,
    questions: QuestionSet,
    *,
    config: LiveConfig,
    clock: Callable[[], datetime],
) -> tuple[str, tuple[MatchAnswerRow, ...], int, str]:
    """(sonuç, cevap satırları, başarısız soru, dönen model). Tavan çağrıdan ÖNCE düşer."""
    battery = side_battery(questions, side=task.side, team=task.team)
    try:
        answer = client.ask_battery(side_state(task), battery)
    except BudgetExceeded:
        return BUDGET, (), 0, NO_MODEL
    except Exception:
        LOGGER.exception("jev: %s %s sorulamadı", task.decision.match_id, task.side)
        return ERROR, (), len(battery), NO_MODEL
    if config.jev_model is not None and answer.jev_model != config.jev_model:
        return MODEL_DRIFT, (), 0, answer.jev_model
    new = side_rows(task, battery, answer, prompt_version=config.prompt_version, asked_at=clock())
    return ASKED, new, len(battery) - len(new), answer.jev_model


def run_tier2(
    tasks: Sequence[SideTask],
    client: JevClient,
    questions: QuestionSet,
    *,
    config: LiveConfig,
    clock: Callable[[], datetime],
    answered: frozenset[tuple[str, datetime, str]] = frozenset(),
    sink: Sink = _discard,
) -> Tier2Run:
    """Görevleri (karar anı, maç, ev → deplasman) sırasıyla sorar; her tarafın cevapları ve durum
    işareti birlikte `sink`e (I-8). Durunca kalan taraflar durma sebebiyle işaretlenir."""
    outcomes: dict[str, int] = {}
    rows: tuple[MatchAnswerRow, ...] = ()
    failed = streak = 0
    stop: str | None = None
    drift: str | None = None
    for task in sorted(tasks, key=_task_order):
        asked = outcomes.get(ASKED, 0)
        outcome = _skip(task, answered=answered, now=clock(), config=config, asked=asked) or stop
        new: tuple[MatchAnswerRow, ...] = ()
        model = NO_MODEL
        if outcome is None:
            outcome, new, lost, model = _ask(task, client, questions, config=config, clock=clock)
            failed, streak = failed + lost, streak + 1 if outcome == ERROR else 0
            drift = model if outcome == MODEL_DRIFT else drift
            if outcome in (BUDGET, MODEL_DRIFT) or streak >= OUTAGE_STREAK:
                stop = OUTAGE if outcome == ERROR else outcome
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if outcome == ANSWERED_BEFORE:
            continue
        marker = status_row(
            task, outcome, prompt_version=config.prompt_version, at=clock(), jev_model=model
        )
        sink((*new, marker))
        rows = (*rows, *new, marker)
    return Tier2Run(rows, MappingProxyType(outcomes), failed, stop=stop, model_drift=drift)


def _task_order(task: SideTask) -> tuple[datetime, str, int]:
    return task.decision.decided_at, task.decision.match_id, _SIDE_ORDER.index(task.side)


# ── Veritabanı ─────────────────────────────────────────────────────────────────────────────

# Yalnız VARLIK: hiçbir olasılık, fiyat ya da sonuç sütunu okunmaz (I-2; testle sabit).
DECISIONS_SQL = """
    SELECT DISTINCT p.match_id, p.decided_at, m.home_team, m.away_team, m.commence_time
    FROM model_predictions p JOIN matches m ON m.id = p.match_id
    WHERE p.decided_at >= %s AND p.decided_at <= %s AND p.strategy = ANY(%s)
    ORDER BY p.decided_at, p.match_id
"""
# İşaret satırını DIŞLAR (`tests/test_jev_item_answers_readers.py` READERS); sonra `gates_as_of`.
_ITEM_ANSWERS = """
    SELECT item_id, prompt_version, question_id, choice, probabilities, confidence, match_id,
           jev_model, asked_at, cost_usd
    FROM jev_item_answers
    WHERE prompt_version = %s AND item_id = ANY(%s) AND NOT starts_with(question_id, %s)
    ORDER BY item_id, question_id
"""
# Cevaplanmış taraf = `asked` işareti (M-3): başka bir işaret (budget, error…) tarafı kapatmaz.
_ANSWERED = """
    SELECT DISTINCT match_id, decided_at, split_part(question_id, ':', 2)
    FROM jev_match_answers
    WHERE prompt_version = %s AND variant = %s AND match_id = ANY(%s) AND question_id = ANY(%s)
"""
_MATCH_COLUMNS: tuple[tuple[str, str], ...] = (
    ("match_id", "text"),
    ("decided_at", "timestamptz"),
    ("prompt_version", "text"),
    ("question_id", "text"),
    ("variant", "text"),
    ("item_set_hash", "text"),
    ("choice", "text"),
    ("probabilities", "jsonb"),
    ("confidence", "float8"),
    ("jev_model", "text"),
    ("asked_at", "timestamptz"),
    ("cost_usd", "numeric"),
)
_MATCH_NAMES = ", ".join(name for name, _ in _MATCH_COLUMNS)
_MATCH_ARRAYS = ", ".join(f"%({name})s::{kind}[]" for name, kind in _MATCH_COLUMNS)
INSERT_MATCH_ANSWERS = f"""
    INSERT INTO jev_match_answers ({_MATCH_NAMES})
    SELECT {_MATCH_NAMES}
    FROM unnest({_MATCH_ARRAYS}) AS t({_MATCH_NAMES})
    ON CONFLICT (match_id, decided_at, prompt_version, question_id, variant) DO NOTHING
    RETURNING match_id
"""


def load_decisions(
    conn: psycopg.Connection[Any], *, now: datetime, max_age: timedelta
) -> tuple[Decision, ...]:
    with conn.cursor() as cur:
        cur.execute(DECISIONS_SQL, (now - max_age, now, list(SHADOW_STRATEGIES)))
        rows = cur.fetchall()
    return tuple(Decision(str(r[0]), r[1], str(r[2]), str(r[3]), r[4]) for r in rows)


def load_item_answers(
    conn: psycopg.Connection[Any], prompt_version: str, item_ids: Sequence[int]
) -> tuple[ItemAnswerRow, ...]:
    if not item_ids:
        return ()
    with conn.cursor() as cur:
        cur.execute(_ITEM_ANSWERS, (prompt_version, list(item_ids), FAILED_PREFIX))
        rows = cur.fetchall()
    return tuple(
        ItemAnswerRow(
            item_id=int(r[0]),
            prompt_version=str(r[1]),
            question_id=str(r[2]),
            choice=str(r[3]),
            probabilities=MappingProxyType({str(k): float(v) for k, v in dict(r[4]).items()}),
            confidence=float(r[5]),
            match_id=None if r[6] is None else str(r[6]),
            jev_model=str(r[7]),
            asked_at=r[8],
            cost_usd=float(r[9]),
        )
        for r in rows
    )


def answered_sides(
    conn: psycopg.Connection[Any], prompt_version: str, match_ids: Sequence[str]
) -> frozenset[tuple[str, datetime, str]]:
    if not match_ids:
        return frozenset()
    with conn.cursor() as cur:
        cur.execute(_ANSWERED, (prompt_version, VARIANT_REAL, list(match_ids), list(ASKED_MARKERS)))
        return frozenset((str(r[0]), r[1], str(r[2])) for r in cur.fetchall())


def _column(row: MatchAnswerRow, name: str) -> Any:
    value = getattr(row, name)
    return json.dumps(dict(value), sort_keys=True) if name == "probabilities" else value


def write_match_answers(conn: psycopg.Connection[Any], rows: Sequence[MatchAnswerRow]) -> int:
    """YENİ yazılan satır sayısı; aynı (maç, karar, küme, soru, varyant) ikinci kez yazılmaz."""
    if not rows:
        return 0
    columns = {name: [_column(row, name) for row in rows] for name, _ in _MATCH_COLUMNS}
    with conn.cursor() as cur:
        cur.execute(INSERT_MATCH_ANSWERS, columns)
        return len(cur.fetchall())


def collect_tasks(
    conn: psycopg.Connection[Any],
    *,
    config: LiveConfig,
    languages: frozenset[str],
    now: datetime,
) -> tuple[tuple[Decision, ...], tuple[SideTask, ...]]:
    decisions = load_decisions(conn, now=now, max_age=config.max_decision_age)
    if not decisions:
        return (), ()
    items = load_news(conn, since=min(d.decided_at for d in decisions) - ITEM_LOOKBACK)
    ids = [item.item_id for item in items if item.item_id is not None]
    rows = load_item_answers(conn, config.tier1_prompt_version, ids)
    tasks = tuple(
        task
        for decision in decisions
        for task in side_tasks(decision, items, rows, config=config, languages=languages)
    )
    return decisions, tasks
```

- [ ] **Step 10: En küçük uygulama — `features/__main__.py`**

Modül belgesine (100 sütun): "`tier2`: bu turun gölge kararlarının taraflarına kademe 2 bataryası (Plan 2 R180) — AĞA
ÇIKAR, PARA HARCAR. Sıra: küme/işletme dosyaları (25) → anahtar (17) → küme donmuş mu (25) → dil → veritabanı. Taraf
başına commit ve durum işareti; tavan 16, kesinti 7, dönen model kümedekinden farklı 25." Import'lar: `live_config`ten
`EXIT_FROZEN_SET, LIVE_CONFIG_PATH, OPS_CONFIG_PATH, TIER1, TIER2, LiveConfig, LiveConfigError, frozen_violations,
load_live_config`; `tier2`den `ANSWERED_BEFORE, ASKED, DEFERRED, ERROR, NO_NEWS, STALE, MatchAnswerRow, Tier2Run,
answered_sides, collect_tasks, run_tier2, write_match_answers`.

`_parser`ta `tier1`in son argümanından sonra (`return parser` ve ardından yeni `_live_config` dâhil):

```python
    tier2 = commands.add_parser("tier2")
    tier2.add_argument("--questions", type=Path, default=QUESTIONS_PATH)
    tier2.add_argument("--languages", type=Path, default=LANGUAGES_PATH)
    for command in (tier1, tier2):
        command.add_argument("--live-config", type=Path, default=LIVE_CONFIG_PATH)
        command.add_argument("--ops-config", type=Path, default=OPS_CONFIG_PATH)
    return parser


def _live_config(args: argparse.Namespace, name: str) -> LiveConfig | None:
    """Küme + işletme ayarları; okunamazsa adıyla loglanır ve None (çağıran `EXIT_FROZEN_SET`)."""
    try:
        return load_live_config(
            args.live_config, ops_path=args.ops_config, questions_path=args.questions
        )
    except (LiveConfigError, OSError) as error:
        LOGGER.error("%s koşulmadı: küme/işletme ayarı okunamadı — %s", name, error)
        return None
```

`_tier1`in başı (dil kapısından önceki kısım) — kademe 1 de küme dosyasından model alır (I8), bozuk dosya 25 (M3):

```python
def _tier1(args: argparse.Namespace) -> int:
    config = _live_config(args, "kademe 1")
    if config is None:
        return EXIT_FROZEN_SET
    try:
        # Kademe 2 ile aynı model (inceleme I8); `null` iken hesabın varsayılanı.
        jev = TypeSafeJev(model=config.jev_model)
    except MissingJevKey as error:
        LOGGER.error("kademe 1 koşulmadı: %s", error)
        return EXIT_NO_JEV_KEY
```

ve aynı fonksiyonda `budgeted_jev(jev, spend_conn, clock=_now)` →
`budgeted_jev(jev, spend_conn, clock=_now, estimate_usd=config.estimate_usd[TIER1])`.

`COMMANDS`tan önce:

```python
def _report_tier2(run: Tier2Run, *, decisions: int, written: int) -> None:
    LOGGER.info(
        "kademe 2: karar %d · sorulan taraf %d · haberi olmayan taraf %d ('yok', imputed) · "
        "daha önce cevaplanmış %d · bayat (> 6 sa) %d · ertelenen %d · hata %d",
        decisions,
        run.count(ASKED),
        run.count(NO_NEWS),
        run.count(ANSWERED_BEFORE),
        run.count(STALE),
        run.count(DEFERRED),
        run.count(ERROR),
    )
    LOGGER.info(
        "kademe 2: yazılan satır %d (işaret dâhil) · başarısız soru %d", written, run.failed
    )


def _tier2_exit(run: Tier2Run, frozen_model: str | None) -> int:
    if run.budget_hit:
        LOGGER.error("jev: aylık tavan $%.2f doldu — kalan taraflar sorulmadı", MONTHLY_CAP_USD)
        return EXIT_BUDGET
    if run.model_drift is not None:
        LOGGER.error(
            "jev: dönen model %r ≠ dondurulmuş %r — yazılmadı; yeni küme gerekir (R185)",
            run.model_drift,
            frozen_model,
        )
        return EXIT_FROZEN_SET
    # Hiç taraf cevaplanmadı ama hata var: kesinti sayılır (inceleme I4), seri kısa olsa da.
    if run.outage or (run.count(ASKED) == 0 and run.count(ERROR) > 0):
        LOGGER.error(
            "jev: kesinti — %d taraf Jev hatasıyla düştü, hiçbiri cevaplanmadı ya da art arda %d",
            run.count(ERROR),
            OUTAGE_STREAK,
        )
        return EXIT_SOURCE_FAILED
    return 0


def _tier2(args: argparse.Namespace) -> int:
    config = _live_config(args, "kademe 2")
    if config is None:
        return EXIT_FROZEN_SET
    try:
        jev = TypeSafeJev(model=config.jev_model)
    except MissingJevKey as error:
        LOGGER.error("kademe 2 koşulmadı: %s", error)
        return EXIT_NO_JEV_KEY
    questions = load_questions(args.questions)
    violations = frozen_violations(config, questions_prompt_version=questions.prompt_version)
    for violation in violations:
        LOGGER.error("kademe 2: dondurulmuş küme — %s", violation)
    if violations:
        return EXIT_FROZEN_SET
    languages = production_languages(args.languages)
    if not languages:
        LOGGER.info("kademe 2: üretimde dil yok (%s) — Jev'e haber gitmedi", args.languages)
        return 0
    written = 0
    with connect() as conn, connect() as spend_conn:

        def sink(rows: tuple[MatchAnswerRow, ...]) -> None:
            nonlocal written
            written += write_match_answers(conn, rows)
            conn.commit()  # taraf başına (I-8)

        decisions, tasks = collect_tasks(conn, config=config, languages=languages, now=_now())
        run = run_tier2(
            tasks,
            budgeted_jev(jev, spend_conn, clock=_now, estimate_usd=config.estimate_usd[TIER2]),
            questions,
            config=config,
            clock=_now,
            answered=answered_sides(conn, config.prompt_version, [d.match_id for d in decisions]),
            sink=sink,
        )
    _report_tier2(run, decisions=len(decisions), written=written)
    return _tier2_exit(run, config.jev_model)
```

`COMMANDS`a `"tier2": _tier2`.

- [ ] **Step 11: En küçük uygulama — workflow'lar ve `verify.sh`**

`shadow.yml`: `timeout-minutes: 30` → `45` (yorum: "+ kademe 2: en çok 80 taraf × gecikme; Task 5 ölçer"); "Secret
taraması"na `id: secret_scan`, "Gölge tahmin"e `id: shadow`; "Haftalık gölge raporu"ndan sonra, "Alarm aç"tan önce:

```yaml
      - name: Kademe 2 (Jev)
        id: tier2
        # Plan 2 R180: bu turun gölge satırlarının (maç, karar anı) haberli taraflarına taraf başına
        # tek batarya (30 soru), dondurulmuş küme config/faz4_live.yaml (R185). Rapor kırmızı olsa da
        # koşar: yalnız gölge adımının başarısına bağlı. Jev arızası gölge turunu kırmızı yapmaz:
        # `jev-kademe2` alarmı (R186). Anahtarsız 17 = "Jev kapalı"; JEV_ENABLED=1 iken kırmızı (I-5).
        if: ${{ !cancelled() && steps.secret_scan.outcome == 'success' && steps.shadow.outcome == 'success' }}
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          set +e
          uv run python -m football_edge.features tier2
          code=$?
          set -e
          jev=fail
          case "$code" in
            0) jev=ok; echo "kademe 2 tamam" ;;
            17)
              if [ "${JEV_ENABLED:-}" = "1" ]; then
                echo "::error::tier2: JEV_ENABLED=1 ama TYPESAFE_API_KEY yok ya da boş (exit 17) — secret adını ve değerini denetle"
              else
                jev=ok
                echo "kademe 2: Jev kapalı (exit 17, anahtar yok) — sinyal toplanmıyor"
                echo "Jev kapalı: kademe 2 sorulmadı (anahtar yok; ücret yaması bekleniyor, R177)" >> "$GITHUB_STEP_SUMMARY"
              fi
              ;;
            7) echo "::error::tier2: Jev kesintisi (exit 7) — art arda Jev hatası, koşu durdu" ;;
            16) echo "::error::tier2: Jev aylık tavanı doldu (exit 16) — kalan taraflar sorulmadı" ;;
            25) echo "::error::tier2: dondurulmuş küme eksik/bozuk ya da model değişti (exit 25) — config/faz4_live.yaml, config/faz4_ops.yaml" ;;
            *) echo "::error::tier2 beklenmedik kodla düştü (exit $code)" ;;
          esac
          echo "jev=$jev" >> "$GITHUB_OUTPUT"
          exit 0
      - name: Jev alarmı aç
        if: ${{ !cancelled() && steps.tier2.outputs.jev == 'fail' }}
        env:
          GITHUB_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: uv run python scripts/ops_alert.py fail --workflow jev-kademe2 --run-url "$RUN_URL"
      - name: Jev alarmı kapat
        if: ${{ !cancelled() && steps.tier2.outputs.jev == 'ok' }}
        continue-on-error: true
        env:
          GITHUB_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: uv run python scripts/ops_alert.py ok --workflow jev-kademe2 --run-url "$RUN_URL"
```

`collect-news.yml` "Kademe 1 (Jev)" adımında `16)` kolundan sonra:

```yaml
            25) echo "::error::tier1: dondurulmuş küme ya da işletme ayarı okunamadı (exit 25) — config/faz4_live.yaml, config/faz4_ops.yaml" ;;
```

`verify.sh` `sızıntı`: ölç — `uv run pytest tests/ -q -m "leakage and not sitedb" --collect-only 2>&1 | tail -1` →
plan incelemesi kopyasında ölçüldü: **455** (450 + 5: `gates_use_only…`, `cluster_link…`, `side_set_holds…`,
`decision_query…`, `shadow_strategies…`). `EXPECTED_MIN_LEAKAGE=450` → ÖLÇÜLEN sayı; yorum: "2026-10-04 Plan 2 Task 3
(kademe 2 küme, zincir ve gölge varlık testleri) 450 → 455 (`--collect-only` ile ölçüldü)." Farklıysa ölçülen yazılır.

- [ ] **Step 12: Koş — yeşil**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_feature_live_config.py tests/test_feature_derive.py tests/test_feature_tier2.py tests/test_feature_tier1.py tests/test_jev.py tests/test_jev_budget.py tests/test_jev_spend_paths.py tests/test_jev_item_answers_readers.py tests/test_feature_import_rule.py tests/test_shadow_workflow.py tests/test_tier1_workflow.py tests/test_workflows.py tests/test_secrets_scan_netlify.py -q && uv run mypy src scripts && uv run ruff check src tests scripts`
Expected: hepsi `passed`; mypy `Success`; ruff `All checks passed!` (plan incelemesi kopyasında koşuldu: tam takım
`3960 passed`).

- [ ] **Step 13: Mutasyon kanıtı (dokuz; hepsi plan incelemesi kopyasında koşuldu, `exit=1`)**

(a) I-3 sınırı — `F=src/football_edge/features/tier2.py`, OLD `return gates_from([row for row in rows if row.asked_at < decided_at])`,
NEW `return gates_from([row for row in rows if row.asked_at <= decided_at])`; test `tests/test_feature_tier2.py -k asked_before`.

(b) I-3 uçtan uca (inceleme I2) — OLD `gates = gates_as_of([row for row in item_rows if row.item_id in ids], decision.decided_at)`,
NEW `gates = gates_from([row for row in item_rows if row.item_id in ids])`; test `tests/test_feature_tier2.py -k cluster_link`.

(c) M-2 sınırı — OLD `if now - task.decision.decided_at > config.max_decision_age:`, NEW
`if now - task.decision.decided_at >= config.max_decision_age:`; test `tests/test_feature_tier2.py -k six_hours`
(`[late0-2]` kırmızı).

(d) M1 yükleme sınırı — OLD `p.decided_at >= %s`, NEW `p.decided_at > %s`; test `tests/test_feature_tier2.py -k query_reads`.

(e) M2 pencere — OLD ` and item.available_at >= decision.decided_at - ITEM_LOOKBACK`, NEW `` (boş); test
`tests/test_feature_tier2.py -k window_is_fixed`.

(f) I3 idempotentlik — OLD (satır sonu dâhil) `    ON CONFLICT (match_id, decided_at, prompt_version, question_id, variant) DO NOTHING
`, NEW ``; test `tests/test_feature_tier2.py -k idempotent`.

(g) C1 taraf sırası — OLD `return task.decision.decided_at, task.decision.match_id, _SIDE_ORDER.index(task.side)`, NEW
`return task.decision.decided_at, task.decision.match_id, -_SIDE_ORDER.index(task.side)`; test
`tests/test_feature_tier2.py -k home_first`.

(h) Model denetimi — OLD `if config.jev_model is not None and answer.jev_model != config.jev_model:`, NEW `if False:`;
test `tests/test_feature_tier2.py -k model` (`…not_written_and_stops_the_run` ve `[model-drift]` kırmızı).

(i) I4 — `F=src/football_edge/features/__main__.py`, OLD `if run.outage or (run.count(ASKED) == 0 and run.count(ERROR) > 0):`,
NEW `if run.outage:`; test `tests/test_feature_tier2.py -k exit_codes` (`[no-side-answered]` kırmızı).

(j) I8 — OLD `jev = TypeSafeJev(model=config.jev_model)\n    except MissingJevKey as error:\n        LOGGER.error("kademe 1`
(üç satır), NEW aynı üç satır `model=None` ile; test `tests/test_feature_tier1.py -k frozen_model`.

(k) "Yok" ataması — `F=src/football_edge/features/derive.py`, OLD `IMPUTED = LevelAnswer(LEVEL_SCORES[NONE_LEVEL], 1.0)`,
NEW `IMPUTED = LevelAnswer(LEVEL_SCORES["low"], 1.0)`; test `tests/test_feature_derive.py -k imputed`.

- [ ] **Step 14: Commit**

```bash
uv run ruff format src tests scripts
git add config/faz4_live.yaml config/faz4_ops.yaml src/football_edge/features/live_config.py src/football_edge/features/tier2.py src/football_edge/features/derive.py src/football_edge/features/__main__.py src/football_edge/jev.py src/football_edge/jev_budget.py .github/workflows/shadow.yml .github/workflows/collect-news.yml verify.sh tests/fake_tier2_db.py tests/test_feature_live_config.py tests/test_feature_tier2.py tests/test_feature_derive.py tests/test_feature_tier1.py tests/test_jev.py tests/test_jev_budget.py tests/test_jev_item_answers_readers.py tests/test_shadow_workflow.py tests/jev_workflow_helpers.py
git commit -F - <<'EOF'
feat: kademe 2 koşucusu — dondurulmuş küme, taraf durum işaretleri, features tier2 ve shadow.yml adımı

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 15: TAM KAPI** — Global Constraints'teki komut. Expected: `FAIL:` yok; `PASS: sızıntı`; `KAPI YEŞİL`.

---

### Task 4: `features slice-status`, `features estimate`, `features probe`

**Kademe:** K2

**Files:**
- Create: `src/football_edge/features/slice.py`, `src/football_edge/features/estimate.py`,
  `src/football_edge/features/probe.py`, `tests/test_feature_slice.py`, `tests/test_feature_estimate.py`,
  `tests/test_feature_probe.py`
- Modify: `src/football_edge/features/__main__.py` (üç komut), `.github/workflows/shadow.yml` (tier2'den sonra bir adım),
  `tests/fake_tier2_db.py` (`_handler`a dilim sorgusu), `tests/test_shadow_workflow.py`, `verify.sh` (`EXPECTED_MIN_LEAKAGE`)

**Interfaces:**
- Consumes: Task 3 `tier2.SHADOW_STRATEGIES`, `VARIANT_REAL`, `ASKED_MARKERS`, `ASKED`, `NO_NEWS`, `status_question`,
  `Decision`, `SideTask`, `load_decisions`, `side_battery`, `side_state`; `live_config.TIER1`, `TIER2`, `LiveConfig`;
  CLI `_live_config(args, name)`; Task 2 `run_tier1(..., max_calls=)`; `tier1.candidate_fixtures`, `tier1.fold`,
  `tier1.team_tokens`, `tier1.load_fixtures`, `tier1.HORIZON`; `derive.item_set_hash`; `features.news.load_news`.
- Produces:
  - `slice`: `TARGET = 900`, `RATE_WINDOW = timedelta(days=28)`, `READ_ONLY = "SET TRANSACTION READ ONLY"`, `SLICE_SQL`,
    `SliceLine(prompt_version, count, weekly_rate, eta, current)`, `eta_for(count, weekly_rate, *, today, target=TARGET)`,
    `slice_lines(rows, *, now, current, target=TARGET)`, `render(lines, *, target=TARGET) -> str`, `read_only(conn)`,
    `select_slice_rows(conn) -> tuple[tuple[str, str, datetime], ...]`.
  - `estimate`: `WINDOW`, `ASSUMED_LANGUAGES = frozenset({"tr"})`, `STOP_MONTHLY_USD = 20.0`, `STOP_DATE = date(2027, 6, 30)`,
    `Estimate(...)`, `mentioned(team, item)`, `news_before(decision, items)`, `candidate_sides(decision, items)`,
    `stops_for(monthly_usd, eta)`, `estimate(items, fixtures, decisions, *, config, slice_count, now)`, `render_estimate`.
  - `probe`: `PROBE_ITEMS = 5`, `ProbeResult`, `TimingJev(inner, timer=time.perf_counter)` (`.timings`),
    `probe_tier1(...)`, `probe_task(decisions, items)`, `probe_tier2(task, client, questions)`.
  - CLI: `features slice-status [--out P]`, `features estimate`, `features probe --tier {1,2}`; üçü de
    `[--questions P] [--live-config P] [--ops-config P]` alır.

**Kararlar:** Sayaç "haberli karar"ı Task 3'ün `asked` durum işaretinden sayar (inceleme I5): en az bir tarafı
`side_status:<taraf>:asked` taşıyan ve o karar anında baz gölge satırı olan (maç, karar anı), küme başına. Üç
komutun veri bağlantısı `SET TRANSACTION READ ONLY` ile açılır ve geri alınır (M-8: kuru koşu ve ölçüm `jev_*`
cevap tablolarına yazmaz; `probe`un harcama kaydı AYRI autocommit bağlantıdadır, tavan gereği). `estimate` Jev
KURMAZ. `probe` R178 dil kapısının bilinçli istisnasıdır: ölçüm TR kalibrasyonundan ÖNCE (Task 5) yapılır, dili
`ASSUMED_LANGUAGES`tır, cevabı hiçbir tabloya ve özelliğe girmez; modeli `faz4_live.yaml`daki (null iken hesap
varsayılanı). Kademe 2 probe'u kademe 1 kapısı olmadan (takım adı geçen son ≤ 5 haberle) tek taraf sorar.
`slice-status` küme dosyası okunamazsa da sayacı basar (geçerli küme işaretsiz); `estimate` ve `probe` 25 döner.

- [ ] **Step 1: Başarısız testleri yaz — `tests/fake_tier2_db.py` ve `tests/test_feature_slice.py`**

`_Tier2Cursor._handler` sözlüğüne `"SELECT a.prompt_version, a.match_id, a.decided_at": self._slice,` ve sınıfın sonuna:

```python
    def _slice(self, params: Any) -> None:
        variant, question_ids, strategies = params
        shadow = {(m, d) for m, s, d in self._t2.predictions if s in strategies}
        self._result = sorted(
            {
                (r["prompt_version"], r["match_id"], r["decided_at"])
                for r in self._t2.match_answers
                if r["variant"] == variant
                and r["question_id"] in question_ids
                and (r["match_id"], r["decided_at"]) in shadow
            }
        )
```

`tests/test_feature_slice.py`:

```python
"""Seçim dilimi sayacı (Plan 2 R181): küme başına sayım, haftalık hız, 900'e varış; mühür."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.slice import (
    SLICE_SQL,
    TARGET,
    eta_for,
    select_slice_rows,
    slice_lines,
)
from football_edge.features.tier2 import ASKED, NO_NEWS, status_question
from football_edge.features.types import HOME
from tests.fake_tier2_db import FakeTier2Db

NOW = datetime(2026, 10, 9, 13, 0, tzinfo=UTC)
D = NOW - timedelta(days=3)
A, B, C = "a" * 64, "b" * 64, "c" * 64


def _answer(
    match_id: str, decided_at: datetime, variant: str = "real", outcome: str = ASKED
) -> dict[str, Any]:
    """Yalnız bir tarafın durum işareti: sayaç cevap İÇERİĞİNE bakmaz (R181, I5)."""
    question_id = status_question(HOME, outcome)
    return {
        "match_id": match_id,
        "decided_at": decided_at,
        "prompt_version": A,
        "variant": variant,
        "question_id": question_id,
    }


@pytest.mark.leakage
def test_the_slice_query_reads_no_answer_content_probability_or_result() -> None:
    """R181: sayaç sonuç, kapanış, olasılık ya da cevap içeriği OKUMAZ — yalnız var olma."""
    text = SLICE_SQL.lower()
    forbidden = ("probabilities", "choice", "confidence", "p_home", "p_draw", "p_away", "pre_")
    for word in (*forbidden, "odds_snapshots", "closing", "result"):
        assert word not in text, word
    assert "exists (" in text and "from model_predictions" in text
    assert "a.question_id = any(%s)" in text, "yalnız `asked` işareti sayılır (haberli karar)"
    assert "p.match_id = a.match_id and p.decided_at = a.decided_at" in text, "aynı karar anı"


@pytest.mark.leakage
def test_only_asked_decisions_with_a_base_shadow_row_are_counted() -> None:
    db = FakeTier2Db()
    db.match_answers = [
        _answer("m1", D),
        _answer("m1", D),
        _answer("m2", D),
        _answer("m3", D),
        _answer("m4", D, variant="blank"),
        _answer("m5", D, outcome=NO_NEWS),
    ]
    db.predictions = [
        ("m1", "market", D),
        ("m3", "harman_jev", D),
        ("m4", "market", D),
        ("m5", "market", D),
    ]

    assert select_slice_rows(db) == ((A, "m1", D),)  # type: ignore[arg-type]


def test_sets_are_counted_separately_and_the_current_set_shows_at_zero() -> None:
    rows = [(A, f"m{n}", NOW - timedelta(days=n)) for n in range(1, 9)]
    rows.append((B, "x", NOW - timedelta(days=60)))

    lines = slice_lines(rows, now=NOW, current=C)

    assert [(x.prompt_version, x.count, x.current) for x in lines] == [
        (A, 8, False),
        (B, 1, False),
        (C, 0, True),
    ]
    assert lines[0].weekly_rate == pytest.approx(2.0)  # 8 karar / 4 hafta
    assert (lines[1].weekly_rate, lines[1].eta) == (0.0, None)


def test_the_eta_is_the_weeks_left_at_the_current_rate() -> None:
    today = date(2026, 10, 9)

    assert eta_for(300, 30.0, today=today) == today + timedelta(days=140)
    assert eta_for(0, 0.0, today=today) is None
    assert eta_for(TARGET, 0.0, today=today) == today


def test_slice_status_appends_to_the_summary_inside_a_read_only_transaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = FakeTier2Db()
    db.match_answers = [_answer("m1", D)]
    db.predictions = [("m1", "market", D)]
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    out = tmp_path / "summary.md"
    out.write_text("önceki\n", encoding="utf-8")

    assert cli.main(["slice-status", "--out", str(out)]) == 0

    text = out.read_text(encoding="utf-8")
    assert text.startswith("önceki\n") and f"1 / {TARGET}" in text and "(geçerli küme)" in text
    assert db.statements[0] == "SET TRANSACTION READ ONLY"
```

- [ ] **Step 2: Başarısız testleri yaz — `tests/test_feature_estimate.py`, `tests/test_feature_probe.py`, workflow**

```python
"""Jev'siz kuru koşu (Plan 2 R184; I-10): sayım, aylık dolar, 900'e varış, kullanıcı durakları."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.estimate import STOP_DATE, estimate, stops_for
from football_edge.features.live_config import LiveConfig
from football_edge.features.news import NewsDraft, news_hash, write_news
from football_edge.features.tier2 import Decision
from football_edge.features.types import OBSERVED, StoredNews
from football_edge.live.context import LiveMatch
from tests.fake_tier2_db import FakeTier2Db

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
CONFIG = LiveConfig(
    tier1_prompt_version="a" * 64,
    jev_model=None,
    min_belongs=0.5,
    min_reliability=0.5,
    estimate_usd=MappingProxyType({"tier1": 0.01, "tier2": 0.02}),
    max_sides_per_run=80,
    max_decision_age=timedelta(hours=6),
    prompt_version="b" * 64,
)
DECISION = Decision(
    "m-gs", NOW - timedelta(days=2), "Galatasaray", "Fenerbahce", NOW - timedelta(days=1)
)
FIXTURE = LiveMatch(
    "m-gs", "soccer_turkey_super_league", NOW - timedelta(days=1), "Galatasaray", "Fenerbahce"
)


def item(item_id: int, title: str, lang: str = "tr") -> StoredNews:
    url, at = f"https://ajansspor.com/haber/{item_id}", NOW - timedelta(days=3)
    digest = news_hash("ajansspor", url, title, None)
    return StoredNews(item_id, "ajansspor", lang, title, None, url, at, at, OBSERVED, digest)


ITEMS = (
    item(1, "Galatasaray'da sakatlık"),
    item(2, "Hava durumu"),
    item(3, "Galatasaray injury update", lang="en"),
)


def test_the_dry_run_counts_tier1_calls_and_tier2_sides_in_the_assumed_language() -> None:
    found = estimate(ITEMS, (FIXTURE,), (DECISION,), config=CONFIG, slice_count=0, now=NOW)

    assert (found.tier1_calls, found.tier2_sides, found.news_decisions) == (1, 1, 1)
    assert found.monthly_usd == pytest.approx(30.4 * (0.01 + 0.02) / 28)


@pytest.mark.parametrize(
    ("monthly", "eta", "stops"),
    [
        (19.0, date(2027, 5, 1), 0),
        (21.0, date(2027, 5, 1), 1),
        (19.0, STOP_DATE + timedelta(days=1), 1),
        (19.0, None, 1),
        (21.0, None, 2),
    ],
)
def test_the_user_stops_are_twenty_dollars_and_the_end_of_june_2027(
    monthly: float, eta: date | None, stops: int
) -> None:
    assert len(stops_for(monthly, eta)) == stops


def _explode(*_a: object, **_k: object) -> Any:
    raise AssertionError("kuru koşu Jev kurmamalı")


def test_the_estimate_command_reads_only_and_never_builds_jev(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = FakeTier2Db(now=NOW - timedelta(days=30))
    drafts = [
        NewsDraft(
            i.source_id, i.lang, i.title, None, i.url, i.available_at, OBSERVED, i.content_hash
        )
        for i in ITEMS
    ]
    write_news(db, drafts)  # type: ignore[arg-type]
    db.fixtures = [
        (FIXTURE.match_id, FIXTURE.league_id, FIXTURE.kickoff, FIXTURE.home, FIXTURE.away)
    ]
    db.matches = {"m-gs": ("Galatasaray", "Fenerbahce", NOW - timedelta(days=1))}
    db.predictions = [("m-gs", "market", NOW - timedelta(days=2))]
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    monkeypatch.setattr(cli, "TypeSafeJev", _explode)
    start = len(db.statements)

    assert cli.main(["estimate"]) == 0

    out = capsys.readouterr().out
    assert "kademe 1 çağrı (son 28 gün): 1" in out and "KULLANICI DURAĞI" in out
    assert db.read_only and db.statements[start] == "SET TRANSACTION READ ONLY"
    assert db.answers == [] and db.match_answers == []
```

`tests/test_feature_probe.py`:

```python
"""Tek gerçek çağrı ölçümü (Plan 2 R184, Task 5): tek batarya, gecikme + model; yazım yok (M-8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from football_edge.features import __main__ as cli
from football_edge.features.news import NewsDraft, news_hash, write_news
from football_edge.features.probe import TimingJev, probe_task, probe_tier1, probe_tier2
from football_edge.features.questions import load_questions
from football_edge.features.tier2 import Decision
from football_edge.features.types import AWAY, OBSERVED, StoredNews
from football_edge.jev import Question
from football_edge.live.context import LiveMatch
from tests.fake_jev import FakeBatteryJev
from tests.fake_tier2_db import FakeTier2Db

QUESTIONS = load_questions(Path(__file__).resolve().parent.parent / "config" / "jev_questions.yaml")
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
FIXTURE = LiveMatch(
    "m-gs", "soccer_turkey_super_league", NOW + timedelta(days=2), "Galatasaray", "Fenerbahce"
)


def item(item_id: int, title: str, at: datetime) -> StoredNews:
    url = f"https://ajansspor.com/haber/{item_id}"
    digest = news_hash("ajansspor", url, title, None)
    return StoredNews(item_id, "ajansspor", "tr", title, None, url, at, at, OBSERVED, digest)


ITEMS = (
    item(1, "Galatasaray'da sakatlık", NOW - timedelta(hours=3)),
    item(2, "Galatasaray'da ikinci haber", NOW - timedelta(hours=2)),
)


def test_timing_records_the_seconds_and_the_returned_model() -> None:
    ticks = iter([10.0, 12.5])
    timing = TimingJev(FakeBatteryJev(jev_model="jev-2026-10"), timer=lambda: next(ticks))

    timing.ask_battery({}, [Question("q", "soru", {"a": "b"})])

    assert timing.timings == ((2.5, "jev-2026-10"),)


def test_the_tier1_probe_asks_exactly_one_battery() -> None:
    client = FakeBatteryJev()

    result = probe_tier1(ITEMS, (FIXTURE,), client, QUESTIONS, clock=lambda: NOW)

    assert len(client.seen) == 1
    assert result is not None and result.jev_model == "jev-fake"


def test_the_tier2_probe_uses_the_latest_decision_with_a_mentioned_side() -> None:
    old = Decision("m-old", NOW - timedelta(days=5), "Galatasaray", "Rizespor", NOW)
    new = Decision("m-new", NOW - timedelta(hours=1), "Trabzonspor", "Galatasaray", NOW)

    task = probe_task((old, new), ITEMS)

    assert task is not None and (task.decision.match_id, task.side) == ("m-new", AWAY)
    result = probe_tier2(task, FakeBatteryJev(), QUESTIONS)
    assert (result.asked, result.answered) == (30, 30)


def test_the_probe_command_prints_the_model_and_writes_no_answer_row(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = FakeTier2Db(now=NOW - timedelta(days=30))
    write_news(  # type: ignore[arg-type]
        db,
        [
            NewsDraft(
                i.source_id, i.lang, i.title, None, i.url, i.available_at, OBSERVED, i.content_hash
            )
            for i in ITEMS
        ],
    )
    db.fixtures = [
        (FIXTURE.match_id, FIXTURE.league_id, FIXTURE.kickoff, FIXTURE.home, FIXTURE.away)
    ]
    monkeypatch.setattr(cli, "connect", lambda: db)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    monkeypatch.setattr(cli, "TypeSafeJev", lambda **_: FakeBatteryJev(jev_model="jev-2026-10"))
    monkeypatch.setattr(cli, "budgeted_jev", lambda jev, spend_conn, **_: jev)

    assert cli.main(["probe", "--tier", "1"]) == 0

    assert "model jev-2026-10" in capsys.readouterr().out
    assert db.read_only and db.answers == [] and db.match_answers == []
```

`tests/test_shadow_workflow.py`: Task 3'ün `test_only_the_database_steps_get_the_database`indeki son iki satırı

```python
    counter = _at(steps, "football_edge.features slice-status")
    assert holders == [shadow, report, tier2, counter]
    assert _at(steps, "scripts/check_secrets.sh") < shadow < report < tier2 < counter
```

yap ve sona ekle:

```python
SLICE = "football_edge.features slice-status"


def test_slice_status_goes_to_the_summary_right_after_tier2() -> None:
    steps = _steps(SHADOW)
    tier2, counter = _at(steps, TIER2), _at(steps, SLICE)

    assert counter == tier2 + 1
    assert steps[counter]["if"] == AFTER_SHADOW
    assert steps[counter]["env"] == {"DATABASE_URL": "${{ secrets.DATABASE_URL }}"}
    assert '--out "$GITHUB_STEP_SUMMARY"' in str(steps[counter]["run"])


@pytest.mark.parametrize(("code", "named"), [(0, ""), (1, "beklenmedik")])
def test_the_slice_step_names_its_exit_code(tmp_path: Path, code: int, named: str) -> None:
    steps = _steps(SHADOW)

    run = run_step(tmp_path, str(steps[_at(steps, SLICE)]["run"]), code=code)

    assert run.returncode == code
    if code == 0:
        assert run.errors == ()
    else:
        assert len(run.errors) == 1 and named in run.errors[0] and f"exit {code}" in run.errors[0]
```

- [ ] **Step 3: Koş — kırmızı**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_feature_slice.py tests/test_feature_estimate.py tests/test_feature_probe.py tests/test_shadow_workflow.py -q`
Expected: `ModuleNotFoundError: No module named 'football_edge.features.slice'` (ve `estimate`, `probe`); workflow
testleri "adımı yok" ile kırmızı.

- [ ] **Step 4: En küçük uygulama — `features/slice.py`**

```python
"""Seçim dilimi sayacı (Plan 2 R181; I-10, I-11): `features slice-status`.

Sayılan birim (küme, maç, karar anı): en az bir tarafı `asked` durum işareti taşıyan (haberli, I5)
VE o karar anında baz gölge satırı (`model_predictions`) bulunan karar. Küme = kademe 2
`prompt_version`ı (R185); küme değişirse sayaç sıfırdan. Sonuç, kapanış, olasılık ya da cevap
içeriği OKUNMAZ — yalnız işaretin var olması (testle sabit).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import psycopg

from football_edge.features.tier2 import ASKED_MARKERS, SHADOW_STRATEGIES, VARIANT_REAL

TARGET = 900
RATE_WINDOW = timedelta(days=28)
READ_ONLY = "SET TRANSACTION READ ONLY"
SLICE_SQL = """
    SELECT a.prompt_version, a.match_id, a.decided_at
    FROM jev_match_answers a
    WHERE a.variant = %s AND a.question_id = ANY(%s) AND EXISTS (
        SELECT 1 FROM model_predictions p
        WHERE p.match_id = a.match_id AND p.decided_at = a.decided_at AND p.strategy = ANY(%s)
    )
    GROUP BY a.prompt_version, a.match_id, a.decided_at
"""


@dataclass(frozen=True)
class SliceLine:
    prompt_version: str
    count: int
    weekly_rate: float
    eta: date | None
    current: bool


def eta_for(count: int, weekly_rate: float, *, today: date, target: int = TARGET) -> date | None:
    """Bugünkü haftalık hızla `target`a varış; hız sıfırsa tahmin yok."""
    if count >= target:
        return today
    if weekly_rate <= 0:
        return None
    return today + timedelta(days=math.ceil((target - count) / weekly_rate * 7))


def _line(
    version: str, decided: Sequence[datetime], *, now: datetime, current: str | None, target: int
) -> SliceLine:
    recent = sum(1 for at in decided if at > now - RATE_WINDOW)
    rate = recent / (RATE_WINDOW / timedelta(weeks=1))
    eta = eta_for(len(decided), rate, today=now.date(), target=target)
    return SliceLine(version, len(decided), rate, eta, version == current)


def slice_lines(
    rows: Sequence[tuple[str, str, datetime]],
    *,
    now: datetime,
    current: str | None,
    target: int = TARGET,
) -> tuple[SliceLine, ...]:
    """Küme başına satır; geçerli küme hiç satırı yoksa da 0 ile görünür."""
    by_set: dict[str, list[datetime]] = {} if current is None else {current: []}
    for version, _match_id, decided_at in rows:
        by_set.setdefault(version, []).append(decided_at)
    return tuple(
        _line(version, decided, now=now, current=current, target=target)
        for version, decided in sorted(by_set.items())
    )


def render(lines: Sequence[SliceLine], *, target: int = TARGET) -> str:
    out = ["## Seçim dilimi (Plan 2 R181)", "", f"Hedef: {target} haberli karar, küme başına.", ""]
    for line in lines:
        mark = " (geçerli küme)" if line.current else ""
        eta = "tahmin yok (hız 0)" if line.eta is None else line.eta.isoformat()
        out.append(
            f"- `{line.prompt_version[:12]}`{mark}: {line.count} / {target} · haftalık "
            f"{line.weekly_rate:.1f} · tahmini varış {eta}"
        )
    return "\n".join(out) + "\n"


def read_only(conn: psycopg.Connection[Any]) -> None:
    """İşlemin İLK ifadesi olmalı: veri bağlantısı bu komutlarda yazamaz (M-8)."""
    with conn.cursor() as cur:
        cur.execute(READ_ONLY)


def select_slice_rows(conn: psycopg.Connection[Any]) -> tuple[tuple[str, str, datetime], ...]:
    with conn.cursor() as cur:
        cur.execute(SLICE_SQL, (VARIANT_REAL, list(ASKED_MARKERS), list(SHADOW_STRATEGIES)))
        rows = cur.fetchall()
    return tuple((str(r[0]), str(r[1]), r[2]) for r in rows)
```

(`slice_lines`te `by_set` ve listeleri yerel olarak doldurulur — girdi mutate edilmez.)

- [ ] **Step 5: En küçük uygulama — `features/estimate.py` ve `features/probe.py`**

```python
"""Jev'siz maliyet ve takvim kuru koşusu (Plan 2 R184; I-10): `features estimate`.

YAZMAZ, Jev KURMAZ: salt okuma işlemi, sonunda geri alma. TR üretimde VARSAYILIR
(`ASSUMED_LANGUAGES`): kademe 1 çağrısı = son `WINDOW`da adayı olan (`candidate_fixtures`) haber;
kademe 2 ÜST SINIRI = gölge kararlarının, karar anından önceki `HORIZON`da takım adı geçen haberi
olan tarafları (kademe 1 kapısı henüz yok). Aylık dolar `config/faz4_ops.yaml` tahmin birimleriyle;
900'e varış geçerli kümenin sayacından ve haberli karar hızından. Kullanıcı durağı: aylık > 20 $ ya
da varış > 2027-06-30.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from football_edge.features.live_config import TIER1, TIER2, LiveConfig
from football_edge.features.slice import TARGET, eta_for
from football_edge.features.tier1 import HORIZON, candidate_fixtures, fold, team_tokens
from football_edge.features.tier2 import Decision
from football_edge.features.types import StoredNews
from football_edge.live.context import LiveMatch

WINDOW = timedelta(days=28)
ASSUMED_LANGUAGES = frozenset({"tr"})
STOP_MONTHLY_USD = 20.0
STOP_DATE = date(2027, 6, 30)
DAYS_PER_MONTH = 30.4


@dataclass(frozen=True)
class Estimate:
    tier1_calls: int
    tier2_sides: int
    news_decisions: int
    monthly_usd: float
    eta: date | None
    stops: tuple[str, ...]


def mentioned(team: str, item: StoredNews) -> bool:
    words = fold(f"{item.title} {item.body or ''}").split()
    return any(word.startswith(token) for token in team_tokens(team) for word in words)


def news_before(decision: Decision, items: Sequence[StoredNews]) -> tuple[StoredNews, ...]:
    start = decision.decided_at - HORIZON
    return tuple(
        item
        for item in items
        if item.lang in ASSUMED_LANGUAGES and start <= item.available_at < decision.decided_at
    )


def candidate_sides(decision: Decision, items: Sequence[StoredNews]) -> int:
    before = news_before(decision, items)
    teams = (decision.home, decision.away)
    return sum(1 for team in teams if any(mentioned(team, item) for item in before))


def stops_for(monthly_usd: float, eta: date | None) -> tuple[str, ...]:
    found: tuple[str, ...] = ()
    if monthly_usd > STOP_MONTHLY_USD:
        found = (*found, f"aylık tahmin ${monthly_usd:.2f} > ${STOP_MONTHLY_USD:.0f} (R184)")
    if eta is None or eta > STOP_DATE:
        found = (*found, f"{TARGET}'e varış {eta or 'tahmin yok'} > {STOP_DATE} (R184, R187)")
    return found


def estimate(
    items: Sequence[StoredNews],
    fixtures: Sequence[LiveMatch],
    decisions: Sequence[Decision],
    *,
    config: LiveConfig,
    slice_count: int,
    now: datetime,
) -> Estimate:
    recent = tuple(
        i for i in items if i.lang in ASSUMED_LANGUAGES and i.available_at >= now - WINDOW
    )
    tier1 = sum(1 for item in recent if candidate_fixtures(item, fixtures))
    sides = tuple(candidate_sides(decision, items) for decision in decisions)
    days = WINDOW / timedelta(days=1)
    daily = (tier1 * config.estimate_usd[TIER1] + sum(sides) * config.estimate_usd[TIER2]) / days
    monthly = DAYS_PER_MONTH * daily
    news_decisions = sum(1 for count in sides if count)
    weekly = news_decisions / (WINDOW / timedelta(weeks=1))
    eta = eta_for(slice_count, weekly, today=now.date())
    return Estimate(tier1, sum(sides), news_decisions, monthly, eta, stops_for(monthly, eta))


def render_estimate(found: Estimate) -> str:
    days, weeks = WINDOW.days, WINDOW.days / 7
    lines = [
        "kuru koşu (Jev'siz, TR üretimde varsayıldı — R184)",
        f"kademe 1 çağrı (son {days} gün): {found.tier1_calls} · "
        f"günlük {found.tier1_calls / days:.1f}",
        f"kademe 2 üst sınır taraf (son {days} gün): {found.tier2_sides}",
        f"haberli karar: {found.news_decisions} · haftalık {found.news_decisions / weeks:.1f}",
        f"aylık tahmin: ${found.monthly_usd:.2f} (tavan $25)",
        f"{TARGET}'e varış: {found.eta or 'tahmin yok'}",
        *(f"KULLANICI DURAĞI: {stop}" for stop in found.stops),
    ]
    return "\n".join(lines) + "\n"
```

`src/football_edge/features/probe.py`:

```python
"""Tek gerçek çağrı ölçümü (Plan 2 R184; Task 5): `features probe --tier {1,2}`.

Bir kademe 1 ya da bir kademe 2 bataryası sorar; gecikmeyi ve DÖNEN model adını basar. CEVAP
TABLOLARINA YAZMAZ (M-8): veri bağlantısı salt okumadır; harcama `jev_spend`e her çağrı gibi
yazılır. Ölçüm TR kalibrasyonundan ÖNCE yapılır: dil `estimate.ASSUMED_LANGUAGES` (R178'in bilinçli
istisnası — cevap hiçbir tabloya ve özelliğe girmez).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from football_edge.features.derive import item_set_hash
from football_edge.features.estimate import mentioned, news_before
from football_edge.features.questions import QuestionSet
from football_edge.features.tier1 import run_tier1
from football_edge.features.tier2 import Decision, SideTask, side_battery, side_state
from football_edge.features.types import AWAY, HOME, StoredNews
from football_edge.jev import BatteryAnswer, ChoiceAnswer, JevClient, Question
from football_edge.live.context import LiveMatch

PROBE_ITEMS = 5


@dataclass(frozen=True)
class ProbeResult:
    tier: str
    seconds: float
    jev_model: str
    answered: int
    asked: int


class TimingJev:
    """Sarılan istemcinin her bataryasının süresini ve dönen modelini kaydeder (kendi kaydı)."""

    def __init__(self, inner: JevClient, timer: Callable[[], float] = time.perf_counter) -> None:
        self._inner = inner
        self._timer = timer
        self.timings: tuple[tuple[float, str], ...] = ()

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        return self._inner.ask_choice(state, instructions, criteria)

    def ask_battery(self, state: Mapping[str, Any], questions: Sequence[Question]) -> BatteryAnswer:
        start = self._timer()
        answer = self._inner.ask_battery(state, questions)
        self.timings = (*self.timings, (self._timer() - start, answer.jev_model))
        return answer


def probe_tier1(
    items: Sequence[StoredNews],
    fixtures: Sequence[LiveMatch],
    client: JevClient,
    questions: QuestionSet,
    *,
    clock: Callable[[], datetime],
) -> ProbeResult | None:
    timing = TimingJev(client)
    run = run_tier1(items, timing, questions, fixtures=fixtures, clock=clock, max_calls=1)
    if not timing.timings:
        return None
    seconds, model = timing.timings[0]
    return ProbeResult("kademe 1", seconds, model, len(run.rows), run.asked)


def probe_task(decisions: Sequence[Decision], items: Sequence[StoredNews]) -> SideTask | None:
    """En yeni kararın, adı haberde geçen ilk tarafı; son `PROBE_ITEMS` haberle."""
    for decision in sorted(decisions, key=lambda d: d.decided_at, reverse=True):
        before = news_before(decision, items)
        for side, team in ((HOME, decision.home), (AWAY, decision.away)):
            news = tuple(item for item in before if mentioned(team, item))[-PROBE_ITEMS:]
            if news:
                return SideTask(decision, side, team, news, item_set_hash(news))
    return None


def probe_tier2(task: SideTask, client: JevClient, questions: QuestionSet) -> ProbeResult:
    timing = TimingJev(client)
    battery = side_battery(questions, side=task.side, team=task.team)
    answer = timing.ask_battery(side_state(task), battery)
    seconds, model = timing.timings[0]
    return ProbeResult("kademe 2", seconds, model, len(answer.answers), len(battery))
```

- [ ] **Step 6: En küçük uygulama — `features/__main__.py` (üç komut) ve `shadow.yml`**

Import'lar: `import sys`; `slice`tan `read_only, render, select_slice_rows, slice_lines`; `estimate`ten
`ASSUMED_LANGUAGES, WINDOW, estimate, render_estimate`; `probe`tan `ProbeResult, probe_task, probe_tier1, probe_tier2`;
`tier2`den ayrıca `load_decisions`.

`_parser`ta `tier2` alt komutundan sonra; Task 3'ün `for command in (tier1, tier2):` döngüsü
`for command in (tier1, tier2, counter, dry, probe):` olur:

```python
    counter = commands.add_parser("slice-status")
    counter.add_argument("--out", type=Path, default=None)
    dry = commands.add_parser("estimate")
    probe = commands.add_parser("probe")
    probe.add_argument("--tier", type=int, choices=(1, 2), required=True)
    for command in (counter, dry, probe):
        command.add_argument("--questions", type=Path, default=QUESTIONS_PATH)
    for command in (tier1, tier2, counter, dry, probe):
        command.add_argument("--live-config", type=Path, default=LIVE_CONFIG_PATH)
        command.add_argument("--ops-config", type=Path, default=OPS_CONFIG_PATH)
```

`COMMANDS`tan önce:

```python
def _slice_status(args: argparse.Namespace) -> int:
    """R181: küme başına dilim sayacı; salt okuma, sonuç/olasılık okumaz. Küme dosyası okunamazsa
    sayaç yine basılır, yalnız geçerli küme işaretsiz kalır."""
    config = _live_config(args, "dilim (geçerli küme işaretsiz)")
    with connect() as conn:
        read_only(conn)
        rows = select_slice_rows(conn)
        conn.rollback()
    current = None if config is None else config.prompt_version
    text = render(slice_lines(rows, now=_now(), current=current))
    if args.out is None:
        sys.stdout.write(text)
    else:
        with args.out.open("a", encoding="utf-8") as handle:
            handle.write(text)
    return 0


def _estimate(args: argparse.Namespace) -> int:
    """R184: Jev'siz kuru koşu — salt okuma, geri alma; Jev KURULMAZ."""
    config = _live_config(args, "estimate")
    if config is None:
        return EXIT_FROZEN_SET
    now = _now()
    with connect() as conn:
        read_only(conn)
        items = load_news(conn, since=now - WINDOW - HORIZON)
        fixtures = load_fixtures(conn, since=now - WINDOW, until=now + HORIZON)
        decisions = load_decisions(conn, now=now, max_age=WINDOW)
        rows = select_slice_rows(conn)
        conn.rollback()
    count = sum(1 for version, _match, _at in rows if version == config.prompt_version)
    found = estimate(items, fixtures, decisions, config=config, slice_count=count, now=now)
    sys.stdout.write(render_estimate(found))
    return 0


def _probe_once(
    conn: Any, client: JevClient, questions: QuestionSet, tier: int, now: datetime
) -> ProbeResult | None:
    items = load_news(conn, since=now - WINDOW - HORIZON)
    if tier == 1:
        fresh = tuple(
            i for i in items if i.lang in ASSUMED_LANGUAGES and i.available_at >= now - HORIZON
        )
        fixtures = load_fixtures(conn, since=now, until=now + HORIZON)
        return probe_tier1(fresh, fixtures, client, questions, clock=_now)
    task = probe_task(load_decisions(conn, now=now, max_age=WINDOW), items)
    return None if task is None else probe_tier2(task, client, questions)


def _probe(args: argparse.Namespace) -> int:
    """R184 / Task 5: TEK ücretli batarya; gecikme + model; cevap tablolarına yazmaz (M-8)."""
    config = _live_config(args, "probe")
    if config is None:
        return EXIT_FROZEN_SET
    try:
        jev = TypeSafeJev(model=config.jev_model)
    except MissingJevKey as error:
        LOGGER.error("probe koşulmadı: %s", error)
        return EXIT_NO_JEV_KEY
    questions = load_questions(args.questions)
    estimate_usd = config.estimate_usd[TIER1 if args.tier == 1 else TIER2]
    now = _now()
    with connect() as conn, connect() as spend_conn:
        read_only(conn)
        client = budgeted_jev(jev, spend_conn, clock=_now, estimate_usd=estimate_usd)
        result = _probe_once(conn, client, questions, args.tier, now)
        conn.rollback()
    if result is None:
        LOGGER.error("probe: sorulacak haber yok — ölçüm yapılmadı")
        return 1
    sys.stdout.write(
        f"probe {result.tier}: gecikme {result.seconds:.2f} sn · model {result.jev_model} · "
        f"cevap {result.answered}/{result.asked}\n"
    )
    return 0
```

`COMMANDS`a `"slice-status": _slice_status, "estimate": _estimate, "probe": _probe`.

`shadow.yml`: "Kademe 2 (Jev)" adımından HEMEN sonra (Jev alarm adımlarından önce):

```yaml
      - name: Seçim dilimi sayacı
        # Plan 2 R181: küme başına (maç, karar anı) sayısı, haftalık hız, 900'e varış — iş özetine.
        # Salt okuma; sonuç/olasılık okumaz. Gölge yeşilse koşar (kademe 2 kırmızı olsa da).
        if: ${{ !cancelled() && steps.secret_scan.outcome == 'success' && steps.shadow.outcome == 'success' }}
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          set +e
          uv run python -m football_edge.features slice-status --out "$GITHUB_STEP_SUMMARY"
          code=$?
          set -e
          case "$code" in
            0) ;;
            *) echo "::error::slice-status beklenmedik kodla düştü (exit $code)" ;;
          esac
          exit "$code"
```

`verify.sh` `sızıntı`: ölç (`--collect-only`); plan incelemesi kopyasında **457** (455 + 2 dilim mührü). Yorum:
"Plan 2 Task 4 (dilim sayacı mührü) 455 → 457". Farklıysa ölçülen yazılır.

- [ ] **Step 7: Koş — yeşil**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_feature_slice.py tests/test_feature_estimate.py tests/test_feature_probe.py tests/test_feature_tier2.py tests/test_shadow_workflow.py tests/test_workflows.py tests/test_secrets_scan_netlify.py tests/test_jev_spend_paths.py tests/test_jev_item_answers_readers.py tests/test_feature_import_rule.py -q && uv run mypy src scripts && uv run ruff check src tests scripts`
Expected: hepsi `passed` (`test_jev_item_answers_readers.py`: yeni modüller `jev_item_answers`i OKUMAZ); mypy
`Success`; ruff temiz (plan incelemesi kopyasında tam takım `3979 passed`).

- [ ] **Step 8: Mutasyon kanıtı (dört)**

(a) Gölge satırı başka karar anında da sayılırsa — `F=src/football_edge/features/slice.py`, OLD
` AND p.decided_at = a.decided_at`, NEW `` (boş); test `tests/test_feature_slice.py -k reads_no`. Expected: `exit=1`.

(b) `asked` işaret süzgeci kalkarsa — OLD `WHERE a.variant = %s AND a.question_id = ANY(%s) AND EXISTS (`, NEW
`WHERE a.variant = %s AND EXISTS (`; test `tests/test_feature_slice.py -k reads_no`. Expected: `exit=1`.

(c) Hafta → gün — OLD `/ weekly_rate * 7))`, NEW `/ weekly_rate * 1))`; test `tests/test_feature_slice.py -k eta`.
Expected: `exit=1`.

(d) Salt okuma kalkarsa — OLD `        cur.execute(READ_ONLY)
`, NEW `        pass
`; test `tests/test_feature_slice.py tests/test_feature_estimate.py tests/test_feature_probe.py -k "command or summary"`.
Expected: `exit=1`, üç komut testi kırmızı.

(e) Probe tek çağrı sınırı — `F=src/football_edge/features/probe.py`, OLD `max_calls=1)`, NEW `max_calls=None)`;
test `tests/test_feature_probe.py -k exactly_one`. Expected: `exit=1`.

- [ ] **Step 9: Commit**

```bash
uv run ruff format src tests scripts
git add src/football_edge/features/slice.py src/football_edge/features/estimate.py src/football_edge/features/probe.py src/football_edge/features/__main__.py .github/workflows/shadow.yml verify.sh tests/fake_tier2_db.py tests/test_feature_slice.py tests/test_feature_estimate.py tests/test_feature_probe.py tests/test_shadow_workflow.py
git commit -F - <<'EOF'
feat: seçim dilimi sayacı, Jev'siz kuru koşu ve tek çağrı ölçümü (slice-status, estimate, probe)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 10: TAM KAPI** — Global Constraints'teki komut. Expected: `FAIL:` yok; `PASS: sızıntı`; `KAPI YEŞİL`.

---

### Task 5 (CONTROLLER): Jev'siz kuru koşu + tek gerçek kademe 1 ve kademe 2 çağrısı; küme dondurulur

**Kademe:** K2 (controller; implementer'a verilmez — canlı DB salt okuma + iki ÜCRETLİ çağrı)

**Files:** Modify `docs/superpowers/specs/2026-09-23-faz4-olcumler.md` (yeni bölüm "Plan 2 T5"),
`config/faz4_live.yaml` (`jev_model` — küme kimliği değişir), `config/faz4_ops.yaml` (`estimate_usd`, gerekirse
`max_sides_per_run` — küme kimliği DEĞİŞMEZ).

**Önkoşul:** Task 1–4 `main`de, tam kapı yeşil; `.env`te veritabanı adresi ve `TYPESAFE_API_KEY` (K/6). Komutlar
`uv run --env-file .env` ile koşar; değerler ekrana basılmaz.

- [ ] **Step 1: Kuru koşu (salt okuma, Jev yok, ücretsiz)**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --env-file .env python -m football_edge.features estimate
```
Expected: altı satır (`kademe 1 çağrı (son 28 gün): N · günlük …`, `kademe 2 üst sınır taraf`, `haberli karar … ·
haftalık …`, `aylık tahmin: $…`, `900'e varış: …`) ve varsa `KULLANICI DURAĞI:` satırları. Çıktı ölçüm belgesine
komutuyla, tarihle yazılır. R187 karşılaştırması: haftalık haberli karar ~33 bekleniyor (W38 ölçümü); farkı adıyla yaz.

- [ ] **Step 2: (KULLANICI DURAĞI — yalnız Step 1 `KULLANICI DURAĞI` bastıysa)** Aylık > 20 $ ya da 900 tarihi
  > 2027-06-30 ise kullanıcıya iki sayıyla sorulur (R184); cevap gelmeden Step 3'e geçilmez. (R187: §7.3 yolunun bu
  sezon büyük olasılıkla GÜÇ YETERSİZ olduğu zaten biliniyor; Plan 3 önerisi kullanıcı durağıdır, Plan 2'yi durdurmaz.)

- [ ] **Step 3: İki ÜCRETLİ ölçüm çağrısı (her biri tek batarya; tahmin ≤ 0,01 $ + 0,01 $; `jev_spend`e yazılır)**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --env-file .env python -m football_edge.features probe --tier 1
PYTHONDONTWRITEBYTECODE=1 uv run --env-file .env python -m football_edge.features probe --tier 2
```
Expected: `probe kademe 1: gecikme X.XX sn · model M1 · cevap a/b` ve `probe kademe 2: gecikme Y.YY sn · model M2 · cevap c/30`.
`sorulacak haber yok` çıkarsa (exit 1) ölçüm yapılmamıştır — adıyla yazılır, bir sonraki gölge turundan sonra tekrarlanır.
`probe kademe N: Jev hatası (<tür>)` (exit 7) ya da `aylık tavan … (bütçe)` (exit 16) çıkarsa da ölçüm yapılmamıştır,
ama bu haber yokluğu DEĞİLDİR: DUR — 7'de anahtar/yetki ve Jev durumu, 16'da `jev_spend` okunur; kullanıcıya adıyla sorulur.
Cevap tablolarına yazılmadığını doğrula (salt okuma):
`uv run --env-file .env python -c "from football_edge.db import connect; c=connect(); cur=c.cursor(); cur.execute('SET TRANSACTION READ ONLY'); cur.execute('select count(*) from jev_match_answers'); print(cur.fetchone()); c.rollback()"`
→ `(0,)`.

- [ ] **Step 4: KULLANICI DURAĞI — birim fiyat (R184, I-9).** Kullanıcı TypeSafe panelinden bu iki çağrının
  ücretini okur (SDK maliyet bildirmez). Kullanıcıya: "Panelde bugün <saat> civarı iki System One çağrısı var:
  kademe 1 (~4 soru) ve kademe 2 (30 soru). Her birinin $ tutarı?" Cevap gelmeden Step 5'e geçilmez.

- [ ] **Step 5: Kümeyi dondur — `config/faz4_live.yaml`; birim fiyat — `config/faz4_ops.yaml`**

`faz4_live.yaml`: `jev_model: null` → `jev_model: <M2>` (probe kademe 2'nin DÖNEN modeli; `latest` içeriyorsa DUR —
sabit model adı yok demektir, kullanıcıya sorulur). Kademe 1 de bu modeli kullanır (I8); probe'lar `null` iken hesap
varsayılanıyla koştu — M1 ≠ M2 ise DUR ve kullanıcıya sor (iki kademe aynı modelde olmalı). Bu değişiklik küme
kimliğini (`prompt_version`) ilk ve son kez gerçek yazımdan ÖNCE değiştirir. `faz4_ops.yaml`: `estimate_usd.tier1` /
`tier2` → kullanıcının okuduğu birim fiyatlar (yukarı yuvarlanmış, 4 ondalık; fazla tahmin tavanı erken kapatır,
görünür — `jev_budget` gerekçesi); hash'e girmez, sayaç sıfırlanmaz (M4). Gecikme denetimi — bağlayıcı sınır
adımın kendi kesicisidir: `40 × L1 ≤ 15 dk` (collect-news kademe 1 adımı, `timeout 15m`) ve `80 × L2 ≤ 25 dk`
(shadow kademe 2 adımı, `timeout 25m`); tutmazsa `faz4_ops.yaml` `max_sides_per_run` düşürülür ya da
`MAX_CALLS_PER_RUN` (kod + test; ayrı commit) — gerekçesi ölçüm belgesine. İş payı: Task 5 ayrıca birleşmeden
sonraki ilk koşulardan (ücretsiz — Jev kapalı, exit 17 yeşil) `fetch-news` + `sync-news` (collect-news) ve
`shadow` + `report` (shadow) adımlarının GERÇEK sürelerini Actions'tan okur; iş zaman aşımına (collect-news 20 dk,
shadow 45 dk) kalan pay — zaman aşımı − bu adımlar − kademe tavanı (`40 × L1` / `80 × L2`) — 3 dakikanın
altındaysa ücret yamasından ÖNCE `timeout-minutes` yükseltilir ya da tavanlar düşürülür (gerekçe ölçüm
belgesine). Sonra yeniden:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --env-file .env python -m football_edge.features estimate
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_feature_live_config.py -q
```
Expected: aylık tahmin ölçülmüş birimle; `> 20 $` ise Step 2'deki gibi kullanıcı durağı. Test yeşil (taahhütlü küme
artık `frozen_violations` boş).

Ölçüm belgesine "Plan 2 T5" bölümü: komutlar, kuru koşu çıktısı (iki kez), iki gecikme, iki model adı, kullanıcının
okuduğu birim fiyatlar, yeni `prompt_version` (`uv run python -c "from football_edge.features.live_config import load_live_config; print(load_live_config().prompt_version)"`),
"ilk dondurulmuş küme" notu.

- [ ] **Step 6: Commit + TAM KAPI**

```bash
git add config/faz4_live.yaml config/faz4_ops.yaml docs/superpowers/specs/2026-09-23-faz4-olcumler.md
git commit -F - <<'EOF'
chore: Plan 2 dondurulmuş küme — Jev modeli ve birim fiyat sabitlendi (Task 5 ölçümü)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```
Ardından tam kapı (Global Constraints). Expected: `KAPI YEŞİL`. (Bu commit ücret açmaz: workflow'larda anahtar yok.)

---

### Task 6 (CONTROLLER): TR kalibrasyonu (ücretli), ücret yaması ve kullanıcının tek komutu

**Kademe:** K1 (controller)

**Files:** Modify `config/languages.yaml` (yalnız geçerse), `data/calibration/tr.report.json` (rapor),
`docs/superpowers/specs/2026-09-23-faz4-olcumler.md`; Create `docs/superpowers/plans/2026-10-04-faz4-plan2-ucret-yamasi.patch`.

**Önkoşul:** Task 5 bitti (maliyet bilinmeden ücret açılmaz). `data/calibration/tr.titles.jsonl` yerelde var
(gitignored; `test -f data/calibration/tr.titles.jsonl && echo VAR`).

- [ ] **Step 1: TR kalibrasyonu — ÜCRETLİ (100 çağrı, tahmin ≤ 1 $; tavan içinde; R182)**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --env-file .env python -m football_edge.collect calibrate --language tr
```
Expected: `calibrate: tr: doğruluk 0.xx, n=100` (ya da `doğruluk … < 0.85 (YP=…, YN=…)`) ve
`rapor yazıldı: data/calibration/tr.report.json`. Ortam ücretli komutu reddederse kullanıcıya aynı TEK satır verilir
(bellek `user-shell-steps-single-command`).

- [ ] **Step 2a: Geçtiyse (`n ≥ 100` VE `accuracy ≥ 0,85`) — TR üretime**

`config/languages.yaml`: `tr` için `production_enabled: true # Plan 2 R182: <tarih> ölçüldü, doğruluk 0.xx, n=100`
(dosya başındaki "BUGÜN … HER dil hâlâ false" paragrafını ölçüm tarihiyle güncelle). Sonra:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -m football_edge.collect check-languages
git add config/languages.yaml data/calibration/tr.report.json docs/superpowers/specs/2026-09-23-faz4-olcumler.md
git commit -F - <<'EOF'
feat: TR dil kalibrasyonu eşiği geçti — tr üretimde (Plan 2 R182)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```
Expected: `dil kalibrasyonu: TEMİZ`; ardından tam kapı `KAPI YEŞİL` (`dil-kalibrasyonu` adımı raporu doğrular).
Ölçüm belgesine: komut, doğruluk, YP/YN, ortalama güven, tarih.

- [ ] **Step 2b: Geçmediyse — KULLANICI DURAĞI (I-11).** Eşik GEVŞETİLMEZ. Rapor yine commit'lenir
  (`docs: TR kalibrasyonu eşiğin altında — sonuç kaydı`), `production_enabled: false` kalır; kullanıcıya sayılarla
  sorulur (gevşetme mi, soru/istem düzeltmesi mi, EN etiketi mi). Plan 2 hattı sinyalsiz kalır ama koşar
  ("üretimde dil yok", exit 0). Ücret yaması yine hazırlanır (Step 3) — dil yokken para harcamaz.

- [ ] **Step 3: Ücret yamasını hazırla (çalışma ağacında; sonra GERİ ALINIR — silme yok)**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
from pathlib import Path

KEY = "TYPESAFE" + "_API_KEY"
ANCHOR = "          DATABASE_URL: ${{ secrets.DATABASE_URL }}\n"
INSERT = f"          {KEY}: ${{{{ secrets.{KEY} }}}}\n          JEV_ENABLED: \"1\"\n"
for name, command in (
    (".github/workflows/collect-news.yml", "uv run python -m football_edge.features tier1"),
    (".github/workflows/shadow.yml", "uv run python -m football_edge.features tier2"),
):
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    assert text.count(command) == 1, name
    head, sep, tail = text.partition(command)
    cut = head.rfind(ANCHOR) + len(ANCHOR)
    assert cut >= len(ANCHOR), name
    path.write_text(head[:cut] + INSERT + head[cut:] + sep + tail, encoding="utf-8")
PY
git diff -- .github/workflows/collect-news.yml .github/workflows/shadow.yml > docs/superpowers/plans/2026-10-04-faz4-plan2-ucret-yamasi.patch
git diff --stat -- .github/workflows/
```
Expected: `2 files changed, 4 insertions(+)` — her dosyada Jev adımının `env`ine iki satır.

Yamalı hâlde testler yeşil kalmalı (R177: yama testlere dokunmaz):

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_tier1_workflow.py tests/test_collect_workflows.py tests/test_news_sync_workflow.py tests/test_shadow_workflow.py tests/test_secrets_scan_netlify.py tests/test_workflows.py -q && ./scripts/check_secrets.sh
```
Expected: hepsi `passed`; `secret taraması temiz`. Sonra yamayı GERİ AL ve geri alındığını kanıtla:

```bash
git apply -R docs/superpowers/plans/2026-10-04-faz4-plan2-ucret-yamasi.patch && git diff --quiet -- .github/workflows/ && echo GERI-ALINDI
git add docs/superpowers/plans/2026-10-04-faz4-plan2-ucret-yamasi.patch
git commit -F - <<'EOF'
docs: Plan 2 ücret yaması — kullanıcının tek commit'i için hazır (R177)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```
Ardından tam kapı `KAPI YEŞİL`.

- [ ] **Step 4: KULLANICI DURAĞI — secret ve tek komut (R177; bellek `credit-activation-commit-blocked`)**

Kullanıcıya iki adım, bu sırayla (önce secret: yama `JEV_ENABLED=1` ile gelir, secret yoksa ilk tur `jev-kademe1`
alarmını AÇAR — bu doğru davranıştır ama gürültüdür):

1. GitHub depo ayarlarında `TYPESAFE_API_KEY` secret'ını ekle (değeri asistan görmez/girmez; `gh secret set
   TYPESAFE_API_KEY` komutunu kullanıcı kendi kabuğunda koşar).
2. Tek komut:
   ```bash
   git apply docs/superpowers/plans/2026-10-04-faz4-plan2-ucret-yamasi.patch && git commit -m "ci: Jev ücretli adımlarını aç (TYPESAFE_API_KEY + JEV_ENABLED)" -- .github/workflows/collect-news.yml .github/workflows/shadow.yml
   ```

- [ ] **Step 5: Asistan — kapı, birleştirme, push, ilk turların gözlemi**

Tam kapı (`KAPI YEŞİL`) → `git fetch origin && git merge origin/main` → tam kapı → `git push` (bellek
`assistant-does-all-ops`; force yok). İlk `collect-news` turunda (≤ 2 sa) iş özetinde "Jev kapalı" OLMAMALI,
`jev-kademe1` alarmı kapalı; ilk salı/cuma `shadow` turunda kademe 2 satırları ve "Seçim dilimi" özeti görünür.
Gözlem HANDOFF §0'a; bu planın "Kapının ölçmedikleri" maddeleri faz HANDOFF'una ve `docs/DEFERRED.md`ye
(EN etiket paketi R183 — EN `news_items` ≥ 150 olunca, kullanıcı durağı) yazılır.

---

## Öz-inceleme: spec kapsamı

| Madde | Nerede | Not |
|---|---|---|
| R173 yalnız-canlı, seçim dilimi kademe 2 `real` ile başlar, `harman_jev` yok | T3 (`VARIANT_REAL`), T4 sayaç | `harman_jev` yazan kod yok |
| R174 Plan 2 kapsamı | T1–T6 | Plan 3 işleri (budama, ön kayıt) yok |
| R175 yedi RSS, yalnız başlık + URL | T1 | özet okunmaz (test) |
| R176 GDELT/SportMonks yok | — | kod yok (bilinçli) |
| R177 ücret anahtarı tek commit; 17 adıyla; `JEV_ENABLED`; testler iki hâli kabul | T2 Step 4–5, T3 Step 5, T6 Step 3–4 | |
| R178 dil kapısı Jev'den önce | T2 (`production_languages`, pencere süzgeci), T3 (`side_tasks`) | probe bilinçli istisna (T4 kararı) |
| R179 kademe 1 collect-news'te, sync'ten hemen sonra | T2 Step 9 | |
| R180 kademe 2 shadow.yml; gölge varlığı; taraf kümeleri; 6 sa; M-3 | T3 | |
| R181 dilim sayacı küme başına, sonuç okumaz | T4 | |
| R182 TR kalibrasyonu, eşikler bağlı | T2 (`production_languages` eşiği), T6 | |
| R183 EN etiket paketi | T6 Step 5 (DEFERRED kaydı) | tarih koşullu kullanıcı durağı; kod yok |
| R184 kuru koşu, tek gerçek çağrı, birim fiyat kullanıcıda | T4 (`estimate`, `probe`), T5 | |
| R185 dondurulmuş küme, sha256 her satırda | T3 (`live_config`, `prompt_version`), T5 | yeni migration yok; tahmin birimi/tavan `faz4_ops.yaml`da, hash dışı (sapma, inceleme M4) |
| R186 ayrık Jev alarmı; fetch 7 sync/tier1'i durdurmaz; shadow sırası; tavan + parti | T2, T3, T4 | alarm başlığı iki ayrı (sapma, gerekçeli) |
| R187 takvim | T5 Step 1–2 | Plan 3 önerisi kullanıcı durağı |
| I-1 "yok" ataması, `imputed` | T3 `derive.side_answers`, `no_news` durum işareti, CLI logu | |
| I-2 / M-1 gölge varlığı, olasılık okunmaz | T3 `DECISIONS_SQL` testi | |
| I-3 kapılar `asked_at < decided_at` | T3 `gates_as_of` + uçtan uca küme zinciri testi (iki mutasyon) | |
| I-4 anahtar yalnız kademe adımlarında | T2, T3 workflow testleri | |
| I-5 `JEV_ENABLED=1` + 17 kırmızı | T2, T3 (`enabled-17`) | |
| I-6 / I-7 fetch 7 durdurmaz, tur kırmızı biter | T2 (`AFTER_FETCH`, `code` çıktısı) | |
| I-8 tur tavanı + parti commit'i | T2 (kademe 1), T3 (taraf başına `sink`) | |
| I-9 birim fiyat kullanıcıda | T5 Step 4 | |
| I-10 kuru koşu, 900 tarihi | T4, T5 | |
| I-11 küme ve eşikler önceden bağlı | T3, T6 Step 2b | |
| M-2 6 saat | T3 (`_skip`, mutasyon) | |
| M-3 cevaplanmış taraf | T3 (`answered_sides`) | |
| M-4 taraf başına `item_set_hash` | T3 | |
| M-5 | — | spec metninde adıyla geçmiyor; ana spec'e işlenmiş sayıldı |
| M-6 dil kümesi Plan 3'te donar | — | Plan 3 |
| M-7 kalibrasyon yalnız ilgililik | "Kapının ölçmedikleri" (spec §4/7) | |
| M-8 kuru koşu/testler `jev_match_answers`e yazmaz; S8 sorusu | T4 (salt okuma testleri), T6 Step 5 (avukat paketi notu) | |
| §4/9 `ai-input=no` Jev'e gitmez | T1 (`load_news`) | |
| İnceleme C1 ev → deplasman sırası · C2 shadow alarm iğnesi | T3 (`_task_order`, mutasyon g) · T3 Step 5 | |
| İnceleme I1 pencere süzgeci (sorulmuş EN haber) · I6 en yeni önce | T2 (testler + mutasyon a, e) | |
| İnceleme I2 · I3 · I4 · I5 · I8 | T3 (zincir testi; `ON CONFLICT` metin testi; hiç cevap yok → 7; durum işaretleri; kademe 1 modeli) | |
| İnceleme M1 · M2 · M3 · M4 · M5 | T3 (`>=` + sınır testi; pencere testi; bozuk dosya 25; `faz4_ops.yaml`); "Kapının ölçmedikleri" (j) | |

Ad tutarlılığı tarandı: `production_languages`, `MAX_CALLS_PER_RUN`, `BATCH_SIZE`, `newest_within_cap`, `LiveConfig`,
`OPS_CONFIG_PATH`, `EXIT_FROZEN_SET`, `SHADOW_STRATEGIES`, `VARIANT_REAL`, `STATUS_PREFIX`, `ASKED_MARKERS`, `SideTask.key`,
`read_only`, `select_slice_rows`, `ASSUMED_LANGUAGES`, `SWITCH`, `AFTER_FETCH`, `jev-kademe1/2` görevler arasında aynı
yazımla. **Doğrulama:** Task 3 ve Task 4'ün kod blokları, plan incelemesi kopyasında (Task 1–3 uygulanmış ağaç)
uygulanıp `ruff check`, `ruff format --check`, `mypy` ve tam `pytest -m "not sitedb"` (3979 passed) geçen
dosyalardan üretildi; Task 2'nin yeni testleri ve mutasyonları da orada koşuldu.

## Açık sorular (kullanıcı ya da controller)

1. **`min_belongs = 0,5`, `min_reliability = 0,5`** başlangıç değerleri; spec sayı vermiyor. İlk gerçek kademe 2
   yazımından ÖNCE, Task 5 Step 5'te donar — değiştirmek yeni küme demektir. Onay ya da başka değer?
2. **TR kaynakların koşul sayfaları** (Fotomaç, A Spor) okunmadı (`terms_url: ''`); avukat paketi S5/S8'e mi eklensin?
3. **Alarm başlığı:** spec tek `jev` anahtarı diyor; plan `jev-kademe1` / `jev-kademe2` kullanıyor (yeşil kademe 1
   turu kırmızı kademe 2 alarmını kapatmasın). Kabul?
4. **`MAX_CALLS_PER_RUN = 40`, `max_sides_per_run = 80`** gecikme ölçülmeden seçildi; Task 5 Step 5 denetler. 12 tur/gün ×
   40 çağrı en kötü durumda tavanı ~5 günde doldurur — kademe 1 hacmi kuru koşudan sonra yeniden değerlendirilmeli mi?
5. **`probe`un dil istisnası** (TR kalibrasyonundan önce TR haberini Jev'e gönderir; cevap hiçbir yere yazılmaz) R178
   ile bilinçli çelişki — kabul mü, yoksa probe TR kalibrasyonundan (Task 6 Step 1) sonraya mı alınsın?
6. **Plan uzunluğu** hedefin (1500–3000) üstünde: görevler gerçek, doğrulanmış kod ve test taşıdığı için kısaltılmadı;
   tek-yazar ayrımı ve sıra değişmedi.
7. **Spec R185 güncellemesi** (controller): tahmin birimi, taraf tavanı ve karar yaşı dondurulmuş kümeden çıkarıldı
   (`faz4_ops.yaml`, inceleme M4) ve taraf durum işaretleri (I5) spec'e işlenmeli.

