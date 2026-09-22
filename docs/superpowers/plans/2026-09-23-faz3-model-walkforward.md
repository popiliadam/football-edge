# Faz 3 — Baz Model, Walk-Forward, Canlı Bağlam ve Tek Holdout Açılışı — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jev'siz baz modeli (fit Elo + zaman sönümlü Dixon-Coles + piyasa ile log-doğrusal havuz) Faz 2
harness'ına takmak, yalnız geliştirme döneminde ileri yürüyen doğrulamayla seçmek ve ölçmek, canlı bağlam
kurucusunu tarihsel olanla eşitliği kanıtlanmış biçimde yazmak ve holdout'u TEK, kayıtlı, önceden yazılmış
karşılaştırmalarla açmak.

**Architecture:** Modeller (`model/`) saf fonksiyonlar ve harness'ın `Strategy` arayüzüne uyan değişmez
stratejilerdir. Walk-forward (`backtest/walkforward.py`, `wf_eval.py`, `wf_run.py`, `selection.py`) ülke grubu
başına yeniden oynatır, bileşen tablosu kurar, hiperparametreleri yalnız S bölgesinde (2012/13–2018/19)
seçer ve E bölgesinde (2019/20–2024/25) raporlar. Bağlamın tek son adımı `backtest/context.py`dedir; canlı
kurucu (`live/context.py`) defteri aynı ara kayda çevirir ve eşitlik testi iki kaynağın aynı bağlamı ve aynı
`observe` akışını ürettiğini sınar. Holdout yalnız `backtest/final_eval.py`de, ön kayıt denetiminden sonra,
bir kez açılır; değerlendirme anahtarı değil seçilmiş satırları alır.

**Tech Stack:** Python 3.11, uv, numpy, **scipy (Faz 3'ün tek yeni bağımlılığı)**, psycopg3, PyYAML,
pytest, ruff, mypy (strict), Supabase Postgres (pg_cron → `workflow_dispatch`), GitHub Actions.

**Durum:** **TASLAK — kullanıcı onayı bekliyor.** Uygulama yalnız bu plan kullanıcı tarafından onaylanınca
başlar. İz A (N1 · B1 · AUT) `main`e birleşti (`dd038f7`, belgeler `a398c31`) — önceki "İz A önce birleşmeli"
koşulu SAĞLANDI. Canlı kapsam bugün **8 aktif lig**: eng.1, esp.1, ita.1, ger.1, fra.1, tur.1, ned.1, bel.1;
`aut.1` `config/leagues.yaml`da var ama `active: false` (kredi kararı): AUT'un snapshot'ı ve mührü yoktur, bu
yüzden gölge ve E3 onu kapsamaz; AUT Faz 3'te yalnız tarihte, yalnız model olarak ölçülür (R137).
**Spec:** `docs/superpowers/specs/2026-09-23-faz3-model-walkforward-design.md` (onaylı 2026-09-23, R128–R139)
— ana spec `docs/superpowers/specs/2026-09-19-football-edge-design.md` (§4, §6.2 holdout politikası, §6.3).
**Önceki faz:** `docs/phases/02-tarihsel-taban/HANDOFF.md` (§3 ölçülmeyenler, §4 R78–R121, §6 ön koşullar).
**Süreç:** `docs/superpowers/plans/2026-09-21-yol-haritasi-v2-paralel-izler.md` (§3 risk kademeleri, §4 paralellik).

**Planın kodu nasıl doğrulandı (plan yazımında, 2026-09-23):** Her görevin kodu bu metinden AYNEN alınarak
`main` `a398c31`'in (İz A birleşmiş) `git archive` kopyasına dalga dalga kuruldu; her dalganın sonunda ve paralel
dalgalarda her görev TEK BAŞINA tam `verify.sh`'tan geçti (10 PASS + `zincir` ADIYLA SKIP). Her görevin "Mutasyon kanıtı" tablosundaki her satır o ağaçta
uygulanıp KIRMIZI görüldü ve geri alındı (`PYTHONDONTWRITEBYTECODE=1`). Ayrıntı: sondaki Self-review.

## Global Constraints

- Python `>=3.11`; `from __future__ import annotations` her modülde.
- Yeni bağımlılık YALNIZ `scipy>=1.14` (tasarım §11 dalga 0, D15'in devamı). pandas ve statsmodels YOK.
  scipy tip bilgisi taşımaz: `pyproject.toml`da `scipy.*` için `ignore_missing_imports`; dönüşler çağıran yerde
  `float()`/`np.asarray` ile daraltılır.
- `mypy --strict` `src` ve `scripts`te geçer; `ruff check` + `ruff format --check` (satır ≤ 100, kurallar
  `E F I UP B SIM T20` — `src/`de `print` yok).
- Kod yorumu kısa bir "neden" taşır; tarihçe commit mesajında. Test adları İngilizce; yorumlar, docstring'ler,
  hata ve log mesajları Türkçe.
- Değişmezlik: veri tipleri `@dataclass(frozen=True)`, eşleme alanları `types.MappingProxyType`; fonksiyonlar
  girdiyi değiştirmez. Tek bilinçli istisna: Dixon-Coles'un fit memo'su (P5) — saf bir fonksiyonun sonucunu
  (grup, fit günü) anahtarıyla saklar ve eşitliğe girmez.
- Dosya ≤ 800 satır (hedef 200–400); fonksiyon < 50 satır kılavuzdur.
- Ham üçüncü taraf içeriği depoya, loga, artifact'e GİRMEZ (spec §3.2/4): testler SENTETİK maç ve fiyat
  kullanır (`tests/model_builders.py`, `tests/backtest_builders.py`); raporlar yalnız toplu sayı taşır.
- Secret taraması test dosyalarını da tarar: kaynakta `DATABASE_URL=` ya da `ODDS_API_KEY=` biçimli dize yazılmaz.
- Dönemler (kaynağın `Date`'ine göre): geliştirme `< 2025-07-01`, holdout `[2025-07-01, 2026-07-01)`, sonrası
  `≥ 2026-07-01`. Walk-forward bölgeleri YALNIZ geliştirme döneminde: S ana `[2012-07-01, 2019-07-01)`, ek
  `[2013-01-01, 2018-07-01)`; E ana `[2019-07-01, 2025-07-01)`, ek `[2018-07-01, 2025-07-01)`.
- **Holdout Task 13'ün 8. adımına kadar AÇILMAZ.** `open_holdout` yalnız `backtest/final_eval.py`de; anahtar
  yalnız `load_matches(..., key=key)`e verilir (AST kuralı, Task 10). Faz 3 en çok bir açılış + (yalnız çöküşte,
  rapor yokken, aynı git SHA'sıyla) bir kayıtlı yeniden koşu yapar (R135).
- Karar anı ve sonuç anı Faz 2'nin kuralıdır (`backtest/timeline.py`), değişmez: karar cuma/salı 12:00
  Europe/London; sonuç başlama + 3 sa, saat yoksa ertesi gün 03:00 Londra.
- Vig yöntemi `power` (R118). CLV bahis kuralı: maç başına en çok bir bahis, en büyük `p · o − 1`, eşik
  `τ = 0.02`; duyarlılık `{0, 0.05}` (R139). Kapanış referansı vig'i temizlenmiş `AvgC`.
- Append-only tablolar 0001'in `forbid_ledger_mutation()` tetikleyicisiyle, TRUNCATE tetikleyicisiyle ve
  politikasız RLS ile (0006/0007 deseni) korunur.
- Commit: `<type>: <açıklama>` + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; yalnız açık yollar
  `git add` edilir (`git add -A` YOK).
- Her commit'ten SONRA kapının tamamı: `TMPDIR=$(mktemp -d) ./verify.sh`, log DOSYASINDAN okunur, `SKIP` adıyla
  yazılır; paralel işler yüzünden `TMPDIR` her koşuda ayrı.
- Mutasyon kanıtı `PYTHONDONTWRITEBYTECODE=1` ile, her mutasyon geri alınır; son doğrulama taze klonda.
- **HİÇBİR ŞEY SİLİNMEZ** (worktree, dal, scratch dahil); silme gerekiyorsa kullanıcıya sorulur.

## Review Focus

Tasarımın ima ettiği ama "mutlu yol" testlerinin atlayabileceği beş girdi sınıfı; her biri sahibi olan görevde
bir testle sabitlendi:

1. **Görülmemiş (terfi eden) takım** — Dixon-Coles o takımı fit penceresinde hiç görmediyse tahmin YOK; satır
   ortak kümeye girmez ve "bileşeni eksik" olarak SAYILIR (Task 6 `test_rows_missing_a_component_are_counted_not_blended`;
   Elo tarafı Task 2 `test_a_newcomer_starts_below_the_group_mean`).
2. **Yakınsamayan Dixon-Coles fiti** — bayat parametreyle tahmin YOK, `None` döner (Task 1
   `test_a_fit_that_does_not_converge_returns_nothing`).
3. **Yaz saati geçişi ve gece yarısı başlamaları** — canlı maç Londra tarihine göre anahtarlanır ve 2026-10-25
   geçişini kapsayan bütün bir sezonda bağlam birebir aynıdır (Task 8
   `test_a_live_night_kickoff_takes_the_london_date`, `test_the_live_builder_reproduces_the_historical_context_and_stream`).
4. **football-data'nın gecikmesi** — tarihsel kuralın "bilinir" saydığı bir grup sonucu tabanda yoksa canlı
   tahmin YOK, bayat olarak sayılır (Task 8 `test_a_group_result_missing_from_the_base_makes_the_state_stale`).
5. **Eşlenemeyen canlı takım adı** — tahmin yok, `unmapped` olarak sayılır; takma ad yalnız takma adla bulunan adı
   da çözer (Task 8 `test_an_unmapped_match_gets_no_context`, `test_names_map_through_aliases_then_normalisation`).

---

## Tasarım ↔ görev eşlemesi

| Tasarım | Görev | Dalga | Kademe |
|---|---|---|---|
| §11 dalga 0, M15 | Task 0 — scipy, paketler, ölçümler (controller) | 0 | — |
| §6.2, M6 | Task 1 — Dixon-Coles (saf) | 1 | K1 |
| §6.1, M5 | Task 2 — fit edilebilir Elo | 1 | K1 |
| §6.3, M7 | Task 3 — log-doğrusal havuz | 1 | K1 |
| §7.1, §7.5, M9; 14g, 14k, 14l | Task 4 — ortak bağlam son adımı, `MatchKey`, Placebo tohumu | 1 | K1 |
| §11, §13/R2 | Task 5 — dalga 1 birleştirmesi, süre ölçümü (controller) | 1 sonu | — |
| §4, §5.1–5.3, §6.4–6.6, M2, M8 | Task 6 — Dixon-Coles stratejisi, walk-forward satırları ve değerlendirmesi | 2 | K1 |
| §5.2, M3; R129 | Task 7 — S'de seçim, model yapılandırması, `select`/`walkforward` CLI | 3 | K1 |
| §7.2–7.4, M10, M11; R132, R133 | Task 8 — canlı bağlam kurucusu + eşitlik testi E1–E2 | 3 | K1 |
| §5.2 | Task 9 — seçim ve walk-forward raporu gerçek veride (controller) | 3 sonu | — |
| §8, M12; R135, 12i, 14h, 14j | Task 10 — `final_eval`, ön kayıt, tek açılış, 0010, AST kuralı | 4 | K1 |
| §10, M14; R132, R134 | Task 11 — canlı gölge, E3 eşitlik raporu, 0009/0011, `shadow.yml` | 4 | K1 |
| §9 G4, M13; R130 | Task 12 — modelin bilinen sonuçları W1–W4 (`history.yml`) | 5 | K1 |
| §8.1–8.3, §10 (kırmızı takım), §12 | Task 13 — ön kayıt, prova, kırmızı takım, TEK açılış, HANDOFF (controller) | 6 | — |

## Dosya yapısı

| Dosya | Sorumluluk | Görev |
|---|---|---|
| `src/football_edge/model/__init__.py` · `live/__init__.py` | boş paket işaretleri | 0 |
| `pyproject.toml` · `uv.lock` · `verify.sh` (`paket-kurulu`) | scipy + mypy istisnası; kapı scipy'ı da yükler | 0 |
| `src/football_edge/model/dixon_coles.py` | saf DC: fit (L-BFGS-B, analitik gradyan), skor matrisi, 1X2 ve Ü/A | 1 |
| `src/football_edge/model/elo_model.py` | `EloModelConfig`, `EloModel` stratejisi, `elo_probs`, `fit_draw` | 2 |
| `src/football_edge/model/pool.py` | `pool`, `fit_weights` | 3 |
| `src/football_edge/backtest/records.py` | `MatchKey`, `ResultRecord`, `DecisionContext` (+ `.key`) | 4 |
| `src/football_edge/backtest/context.py` | `MatchRecord`, `record_of`, `context_of`, `result_of`, `check_unique`, `pre_only` | 4 |
| `backtest/harness.py`, `backtest/strategies.py` (değişir) | kayıtlar `records.py`den; yineleme reddi; `placebo_pick` | 4 |
| `src/football_edge/model/strategies.py` | `DixonColesStrategy`, `fit_day` | 6 |
| `src/football_edge/backtest/walkforward.py` | bölgeler, grup başına oynatma, `Row`, `group_rows` | 6 |
| `src/football_edge/backtest/wf_eval.py` | ağırlık katları, `frozen_weights`, bahis kuralı, `summarise` | 6 |
| `src/football_edge/backtest/model_config.py` | `config/model_faz3.yaml` okuma/yazma | 7 |
| `src/football_edge/backtest/selection.py` | koordinat inişi, S kayıpları, `select` | 7 |
| `src/football_edge/backtest/wf_run.py` | DEV grupları, stratejiler, `run_rows`, boşluk cezası (R128), rapor | 7 |
| `backtest/__main__.py` (değişir) | `select`, `walkforward` (T7) · `final-eval` (T10) · `model-selftest` (T12) | 7, 10, 12 |
| `src/football_edge/live/context.py` · `live/store.py` | canlı kurucu, bayat durum koruması; defter okuma | 8 |
| `src/football_edge/backtest/preregistration.py` · `final_eval.py` | ön kayıt, tek açılış, prova, holdout raporu | 10 |
| `db/migrations/0010_holdout_phase.sql` | faz başına tek açılış (ifade indeksi) | 10 |
| `src/football_edge/live/shadow.py` · `live/__main__.py` | gölge satırları; `shadow` ve `parity` (E3) CLI | 11 |
| `db/migrations/0009_model_predictions.sql` · `0011_shadow_dispatch.sql` · `.github/workflows/shadow.yml` | gölge tablosu; pg_cron işleri | 11 |
| `scripts/ops_alert.py` (değişir) | bekçi `shadow.yml`i izler | 11 |
| `src/football_edge/backtest/model_selftest.py` · `.github/workflows/history.yml` (değişir) | W1–W4 | 12 |
| `config/model_faz3.yaml` · `config/faz3_preregistration.yaml` · `docs/reports/*` | controller çıktıları | 9, 13 |

Testler düz `tests/` altında, mevcut desenle. Yeni test yardımcıları: `tests/model_builders.py` (Task 6).

## Arayüz sözleşmesi

Bütün görevler bu adlara ve tiplere karşı yazılır; ad değiştirmek bir plan kusurudur. Tam kod görevlerde.

```python
# Task 1 — football_edge.model.dixon_coles
GoalRecord(home: str, away: str, home_goals: int, away_goals: int, day: date)
DCConfig(xi=0.0019, ridge=0.01, window_days=1095, max_goals=10, rho_bound=0.2, min_matches=30)
DCParams(teams: tuple[str, ...], attack, defence: tuple[float, ...], home: float, rho: float, fitted_on: date)
    .index(team) -> int | None
fit(records: Sequence[GoalRecord], *, at: date, config: DCConfig, start: DCParams | None = None) -> DCParams | None
score_matrix(params, home: str, away: str, max_goals: int) -> NDArray | None
outcome_probs(matrix) -> tuple[float, float, float]      # (H, D, A)
totals_probs(matrix, line=2.5) -> tuple[float, float]     # (üst, alt)
strengths(params) -> Mapping[str, tuple[float, float]]

# Task 2 — football_edge.model.elo_model
NO_MARGIN, LINEAR_MARGIN, LOG_MARGIN: str; MARGINS; MAX_DRAW = 0.5
EloModelConfig(k=20.0, home_advantage=65.0, margin="linear", regress=0.0, newcomer_offset=0.0,
               draw=0.26, season_gap_days=60, initial=1500.0)
EloModel(config, groups: Mapping[str, str], ratings, last_seen)   # Strategy, name "elo_fit"
margin_multiplier(home_goals, away_goals, form) -> float
elo_probs(expected: float, draw: float) -> tuple[float, float, float]   # P(D) = δ·4E(1−E)
expectation(probs) -> float                                            # E = H + D/2
fit_draw(expectations: Sequence[float], outcomes: Sequence[int]) -> float

# Task 3 — football_edge.model.pool
MIN_FIT_MATCHES = 300; MAX_WEIGHT = 5.0; class TooFewMatches(ValueError)
pool(components: Sequence[Sequence[float]], weights: Sequence[float]) -> tuple[float, ...]
fit_weights(components: Sequence[Sequence[Sequence[float]]], outcomes: Sequence[int]) -> tuple[float, ...]

# Task 4 — football_edge.backtest.records / context (harness bunları yeniden ihraç eder)
MatchKey(league: str, date: date, home: str, away: str)            # frozen, order=True
DecisionContext(... Faz 2 alanları ...).key -> MatchKey             # ÖZELLİK, alan değil
MatchRecord(key: MatchKey, season: str, kickoff: datetime | None, pre_prices: Mapping[OddsKey, float],
            goals: tuple[int, int] | None)
CONTEXT_BOOK = "Avg"; CONTEXT_MARKETS = frozenset({H2H}); class DuplicateMatch(ValueError)
pre_only(prices) -> Mapping[OddsKey, float]          # yalnız PRE_CLOSING, Avg, 1X2
record_of(match: HistMatch) -> MatchRecord
context_of(index: int, record: MatchRecord, decided: datetime) -> DecisionContext
result_of(record: MatchRecord, known_at: datetime) -> ResultRecord
check_unique(keys: Iterable[MatchKey]) -> None
# football_edge.backtest.strategies
placebo_pick(seed: int, key: MatchKey) -> str

# Task 6 — football_edge.model.strategies / backtest.walkforward / backtest.wf_eval
DixonColesStrategy(config=DCConfig(), groups, market=H2H|TOTALS_25, active_from: date | None, cadence_days=1)
fit_day(decided_on: date, cadence_days: int) -> date
SELECTION = "S"; EVALUATION = "E"; MARKET = "market"; ELO = "elo_fit"; DC = "dixon_coles";
DC_TOTALS = "dixon_coles_ou25"; ELO_SCAFFOLD = "elo_scaffold"; BLEND_COMPONENTS = (MARKET, ELO, DC)
Row(key, kind, zone, season, outcome, totals_outcome, components, totals, pre, closing, totals_pre, totals_closing)
zone_of(match, kind) -> str | None
group_matches(leagues, groups) -> Mapping[str, tuple[HistMatch, ...]]
group_rows(matches, kinds, strategies, *, method, zoning=zone_of) -> tuple[Row, ...]
LEAGUE_MIN_MATCHES = 1000; BLEND = "blend"; MARKET_ONLY = (1.0, 0.0, 0.0)
fold_weights(rows) -> tuple[Weights, tuple[str, ...]]
frozen_weights(rows, targets: Sequence[tuple[str, str]]) -> tuple[Weights, tuple[str, ...]]
blended(rows, weights) -> tuple[tuple[Row, tuple[float, ...]], ...]
bet_clv(probs, pre, closing, tau) -> float | None
summarise(rows, *, tau, sensitivity, resamples, zone=EVALUATION, given=None) -> Summary

# Task 7 — backtest.model_config / selection / wf_run / __main__
ModelConfig(selected_at, catalog_sha256, lock_sha256, method, elo: EloModelConfig, dixon_coles: DCConfig,
            cadence_days: int, tau: float, sensitivity: tuple[float, ...])
load_model_config(path) -> ModelConfig; dump_model_config(config) -> str; file_sha256(path) -> str
coordinate_descent(start, grid, loss) -> (best, trace); select(groups, kinds, rating_groups, *, cadence_days, method)
development_groups(leagues, rating_groups); model_strategies(matches, kinds, rating_groups, config)
run_rows(groups, kinds, rating_groups, config) -> tuple[Row, ...]
gap_penalty(groups, kinds, rating_groups, config, *, resamples, skipped=GAP_SKIPPED, measured=GAP_MEASURED)
    -> Mapping[str, Interval]                      # ELO, DC → LL(boşluklu) − LL(tam)
score_table(title, scores) -> list[str]; format_interval(interval) -> str
backtest CLI: EXIT_CONFIG_MISMATCH = 11; kinds_of(catalog); rating_groups(catalog) (Faz 2)

# Task 8 — football_edge.live.context / live.store
LiveMatch(match_id, league_id, kickoff, home, away); Quote(match_id, observed_at, bookmaker, market, outcome, price)
Naming(codes, aliases, known); LiveDecision(match_id, record, context, results); LiveBatch(decisions, unmapped, stale, no_quote)
naming_from(history, codes, aliases); canonical(naming, code, live_name); live_key(match, naming)
season_of(history, day, kind); pre_prices(quotes, match, decided); observe_stream(group, decided)
build_batch(live, quotes, groups, *, now, naming, kinds, rating_groups) -> LiveBatch
load_live_matches(conn, *, since, until); load_quotes(conn, match_ids, *, until)

# Task 10 — backtest.preregistration / final_eval
PHASE = "faz3"; RERUN = "faz3-rerun"; COMPARISONS = ("C1", …, "C6"); Git(head, clean, committed)
preflight(*, prereg_path, model_path, lock_path, catalog_path, git) -> Preregistration
purpose_for(previous, *, prereg_sha256, git_sha, report_exists, rerun_reason) -> str
run_final(connect, *, catalog, lock, config, prereg, prereg_sha256, git_sha, now, report_path, rerun_reason=None)
run_rehearsal(connect, *, catalog, lock, config, prereg, start, end); render_final(report, *, generated_at)
backtest CLI: EXIT_PREFLIGHT = 12, EXIT_ALREADY_OPENED = 13, EXIT_OPENED_FAILED = 14

# Task 11 — live.shadow / live.__main__
shadow_rows(batch, *, config, rating_groups, config_sha256, git_sha) -> tuple[ShadowRow, ...]
write_shadow(conn, rows) -> int; parity(live, history, *, codes, aliases, kinds) -> ParityReport; EXIT_PARITY = 15

# Task 12 — backtest.model_selftest
W1_MARGIN = 0.001; model_rows(groups, kinds, rating_groups, config); model_checks(rows, *, resamples) -> tuple[Check, ...]
```

## Paralellik ve worktree protokolü

- Dalga başına en çok 4 implementer, her biri `.worktrees/wt-<görev>` altında kendi dalında
  (`feat/faz3-<görev>`), taban o dalganın başındaki `main`. Worktree `git worktree add` ile elle açılır
  (`Agent` `isolation: "worktree"` bu makinede çalışmıyor).
- Tek-yazar: aşağıdaki tablo dışında paralel görevler ortak dosyaya YAZMAZ. Ortak dosyalar (`pyproject.toml`,
  `uv.lock`, `verify.sh` sabitleri, `config/model_faz3.yaml`, `config/faz3_preregistration.yaml`) yalnız controller
  görevlerinde (0, 5, 9, 13) değişir.

| Dalga | Görevler | Yazdıkları | Kesişim |
|---|---|---|---|
| 1 | 1 · 2 · 3 · 4 | `model/dixon_coles.py` · `model/elo_model.py` · `model/pool.py` · `backtest/{records,context,harness,strategies}.py` + testleri | yok. Task 2'nin testleri bağlamı YALNIZ `harness._context`/`replay` ile kurar: Task 4 `DecisionContext`i taşır |
| 2 | 6 | `model/strategies.py`, `backtest/{walkforward,wf_eval}.py`, `tests/model_builders.py` | — (dalga 1'in hepsini tüketir) |
| 3 | 7 · 8 | `backtest/{model_config,selection,wf_run,__main__}.py` · `live/{context,store}.py` | yok |
| 4 | 10 · 11 | `backtest/{preregistration,final_eval,__main__}.py`, `0010`, iki test yaması · `live/{shadow,__main__}.py`, `0009`, `0011`, `shadow.yml`, `scripts/ops_alert.py` | yok (`live/__main__.py` `backtest/__main__.py`yi yalnız OKUR; migration numaraları ayrık) |
| 5 | 12 | `backtest/{model_selftest,__main__}.py`, `history.yml` | — (Task 10'un `__main__.py`sinin üstüne) |

**İz A (birleşti, `a398c31`) ve canlı kapsam:** Task 8 (canlı ad/lig eşlemesi `config/history_aliases.yaml` ve
katalog `league_id`), Task 11 (gölge, aktif ligler) ve Task 13'ün canlı adımları (E3 raporu, ilk gölge turu) İz A'nın
birleşmiş lig kümesine karşı koşar. Kod lig sayısına bağlı değildir (`config/leagues.yaml` ve katalogdan okur);
bağımlılık VERİdedir: yeni liglerin ilk canlı maçlarından sonra takma adlar İz A'nın 5. adımıyla girer. Bugün 8 aktif
lig; `aut.1` kapalı olduğu için defterde AUT maçı yoktur — gölge ve E3 onu görmez; lig kredi onayıyla açılırsa
kod değişmeden kapsar.

## Plan yazımında verilen kararlar (P1–P25; R141)

Tasarımın açık bıraktığı ya da planın kodu yazılırken netleşen noktalar. Biçim: karar — *yanlışsa bedeli*.

1. **P1** Bağlam yalnız `Avg` 1X2 kapanış öncesi fiyatını taşır (`CONTEXT_BOOK`, `CONTEXT_MARKETS`). Canlı
   defter yalnız 1X2 toplar (`markets=h2h`) ve kitap ortalaması `Avg`'ye denktir; başka kitap/market bağlamda
   kalsaydı E1 eşitliği sözde kalırdı. Faz 2'nin bir testi (`test_a_decision_context_carries_only_pre_closing_prices`)
   buna göre güncellenir — *`Max`/`PS`/Ü/A kapanış öncesi fiyatı okuyan bir strateji bağlamdan alamaz
   (bugün yok; `Placebo(book="Max")` bahis yapamaz hâle gelir).*
2. **P2** `DecisionContext.key` alan değil ÖZELLİK — *Faz 2'nin alan seti ve alan testi değişmez.*
3. **P3** `replay` yinelenen `MatchKey`'i `DuplicateMatch` ile reddeder (14g, 14r); iki Faz 2 test fikstürü ayrı
   adlara taşınır — *gerçek veride yineleme çıkarsa oynatma kırmızı düşer (ölçülen: 0).*
4. **P4** Placebo tohumu `sha256(seed|lig|tarih|ev|deplasman)` (14l) — *K4'ün gerçek veri sayısı değişir; Faz 2
   raporundaki −0.0713 yeniden üretilmez, yeni sayı haftalık selftest'te.*
5. **P5** Dixon-Coles fit memo'su değişebilir (bilinçli istisna), anahtar (grup, fit günü); fit yalnız fit
   gününden önceki maçları okur — *en kötü hâli bayatlık, sızıntı değil.*
6. **P6** Harness 3-demet taşır: DC'nin Ü/A tahmini `(üst, alt, 0.0)`. Canlıda Ü/A yok (snapshot yalnız h2h;
   Ü/A toplamak kredi harcar) — *Ü/A yalnız tarihte ölçülür (C5).*
7. **P7** Ek liglerde S `2013-01-01`den başlar (2012 ısınma); tasarım "2012 →" diyordu — *S'den bir yıl eksik.*
8. **P8** Lig kendi eğitim satırı `< 1000` ise havuzlanmış ağırlık (`LEAGUE_MIN_MATCHES`) — *bir ligin ilk E
   katları kendi ağırlığını değil ana liglerin ortak ağırlığını kullanır.*
9. **P9** W1 = "ortalama ΔLL(harman − piyasa) ≤ δ = 0.001" (tasarım §9 G4'ün metni); aralığın alt ucu değil.
   Sentetik ölçüm: tek ligin ~400 maçlık katında örneklem dışı ağırlık gürültüsü δ'yı aşıyordu (P8 bu yüzden) —
   *δ keyfîdir; gerçek veride W1 kırmızıysa kapı gevşetilmez, Task 12 eskalasyonu.*
10. **P10** Seçim: tek turluk koordinat inişi, sabit ızgaralar — Elo `k` {10,15,20,25,30}, ev avantajı
    {40,65,90}, marj {yok, doğrusal, log}, dönüş {0,0.2,0.4}, yeni takım farkı {0,75,150}; DC `ξ`
    {0.0010,0.0019,0.0030}, sırt {0.003,0.01,0.03}; fit penceresi 1095 gün sabit — *yerel optimum; iz raporda.*
11. **P11** Elo'nun 1X2 eşlemesi `P(D) = δ·4E(1−E)`, `H = E − D/2` (tek parametre, kapalı biçimde fit);
    tasarım §6.1 "sıralı lojit" diyordu — *beraberlik reyting farkına bağlı ama tek biçimli; sıralı lojit
    Faz 5 istiflemesinde denenebilir.*
12. **P12** E3'te başlama farkı eşiği 30 dk: saat dilimi/yaz saati hatası ≥ 60 dk kaydırır — *30 dk altı
    kaymalar (yayın saati) görünmez.*
13. **P13** `final_eval` kilidi açılıştan ÖNCE anahtarsız yüklemeyle doğrular (+~10 sn, ~760 MB) — *kilit ihlali
    açılış harcamaz.*
14. **P14** Açılıştan hemen önce kullanıcı durağı (Task 13 Step 7): ön kayıt, prova raporu ve kırmızı takım
    sonucu gösterilir; açılış yalnız açık "evet"le — *bir oturum gecikmesi.*
15. **P15** Çıkış kodları: 11 yapılandırma uyuşmazlığı, 12 ön kayıt (açılmadı), 13 zaten açıldı (açılmadı),
    14 açıldı ama rapor yok, 15 E3 yapısal fark — *collect'in 2–8'i, 9 kilit, 10 köprüyle çakışmaz.*
16. **P16** scipy için `ignore_missing_imports` (stub paketi yerine) — *scipy çağrı imzaları mypy'de denetlenmez;
    testler kapsar.*
17. **P17** `history.yml` iş zaman aşımı 60 → 120 dk (W1–W4 E bölgesini yeniden oynatır). Task 9'da ölçülen
    `walkforward` süresi (`--gap`siz) **90 dk'yı** aşarsa Task 12 başlamaz, eskalasyon. Tasarım §9'un "W3 lig alt
    kümesine iner" yedeği REDDEDİLDİ (kapıyı sessizce daraltmak olurdu; inceleme m9) — *takılan bir tur alarmı
    120 dk geç açar.*
18. **P18** DC `active_from` = grubun S başlangıcı (ısınma fitleri yapılmaz); `cadence_days` varsayılan 1,
    Task 5 ölçümüne göre `select --cadence-days 7` — *haftalık fitte salı kararı hafta sonu sonuçlarını görür,
    cuma kararı salı–perşembe sonuçlarını GÖRMEZ (bayatlık).*
19. **P19** Gölge satırı bileşen olasılıklarını ve karar anı fiyatını saklar; harman ve bahis haftalık raporda,
    dondurulmuş ağırlıkla hesaplanır — *harman satırı tabloda yok; girdileri karar anının bilgisi.*
20. **P20** Numaralar: gölge Task 11, model bilinen sonuçları Task 12 (tasarım §11 tablosundan farklı sıra) —
    *yok.*
21. **P21** E3 (`live parity`) eşleşmeyen maçı sayar, kapı yapmaz; yalnız eşleşmiş maçta yapısal fark exit 15 —
    *bir ligin `Date` takvimi yanlışsa maç eşleşmez ve yalnız sayı büyür; sayı raporda izlenir. AUT kapalı olduğu
    sürece (`a398c31`) E3 AUT'u hiç görmez — §3/38 AUT için açık kalır.*
22. **P22** Prova (R135): E'nin son sezonu `[2024-07-01, 2025-07-01)` anahtarsız sahte holdout; ağırlıklar
    ondan önceki E satırlarından — *prova sayıları E raporundakinden farklıdır (ağırlık kümesi daha kısa).*
23. **P23** `live/__main__.py` `backtest/__main__.py`nin sabitlerini ve iki yardımcısını (`kinds_of`,
    `rating_groups`) içe alır — *iki CLI arasında bağ; ayrı bir modüle taşımak ek dosya.*
24. **P24** Gölge her koşuda grubun durumunu DEV + POST'tan baştan kurar (grup başına bir Elo, bir DC fiti) —
    *koşu başına ~10 sn yükleme + fit; Task 13'te ölçülür.*
25. **P25** Tasarım §10'un gölge CLV raporu (harman + bahis + mühürlü kapanış, haftalık) Faz 3'te YAZILMAZ: Faz 3
    sicili biriktirir, rapor Faz 4'ün ilk görevidir (DEFERRED'a, Task 13 Step 10). R128'nin canlı ayağı (C6 −
    gölge) da bu rapora kadar ölçülmez; boşluk cezası bu fazda DEV simülasyonu (`walkforward --gap`, Task 7/9)
    ve C6 ile ölçülür — *ilk haftaların gölge sayıları okunmaz; sicil yine append-only birikir.*

26. **R141** (controller kararı, inceleme I1) — bayat durum koruması modelin BÜTÜN grup liglerine genişletildi:
    defterde fikstürü olmayan ligler (E1–E3, D2, I2, SP2, F2 …) için football-data'nın kendi tarihleri
    (`league_lagging`: son sonuç, geçen yılın olağan maç günü aralığının %95'liği + 1 günden eskiyse lig geride;
    21 günü aşan ara yargılanmaz). P26'ya gerek kalmadı — *sezgiseldir: bir ligin olağan aralığı içinde kalan
    (ör. tek maçlık) gecikme görünmez; milli ara başında yanlış "bayat" tahmin kaybettirir (güvenli yön).*

**Kullanıcı onayı isteyenler (plan incelemesi):** P1, P9, P11, P25 ve R141 onaylı spec'i ya da onaylı bir kapıyı
değiştirir; plan onayıyla birlikte AYRICA onaylanır. P4 ve P8 bilgi içindir.

## Plan incelemesinin düzeltmeleri (2026-09-23, "approve with fixes")

| Bulgu | Düzeltme | Görev · test · mutasyon |
|---|---|---|
| C1 holdout'taki yineleme tek açılışı yakabilirdi | `load_matches` bütün dönemlerde yinelemeyi anahtar yokken reddeder (`DuplicateMatches`); açılış öncesi yükleme → exit 12 | T10 · `test_a_duplicate_inside_the_holdout_is_refused_before_any_key_exists`, `test_a_duplicate_found_by_the_keyless_load_stops_before_open` |
| I1 bayat koruması yalnız defter ligleri | R141: grup liglerinin football-data tarihleri (`league_lagging`) | T8 · `test_a_group_league_without_ledger_fixtures_that_falls_behind_makes_the_state_stale`, `test_a_weekly_league_lags_after_its_usual_gap_plus_one_day` |
| I2 `frozen_weights`in E süzgeci testsiz | holdout/sonrası satırları ağırlığı değiştirmez testi | T6 · `test_frozen_weights_never_see_holdout_or_post_rows` |
| I3 `≤` → `<` mutantı sağ | karar anında TAM gözlenen snapshot turu | T8 · `_quotes` fikstürü |
| I4 açılış sonrası çıkış kodu eksik | açılış sonrası her arıza exit 14; 0010 reddi exit 13; rapor yazımı exit 14; 1/137 Task 13 tablosunda | T10 · `test_any_failure_after_the_opening_is_reported_as_opened`, `test_the_phase_index_rejecting_the_insert_is_not_an_opening`, CLI testi; T13 Step 8 tablosu |
| I5 Task 13 açılıştan önce ağacı kirletiyordu | prova, kırmızı takım ve ölçüm belgesi Step 5'te commit'lenir | T13 |
| I6 0010 hiç reddetmedi | `tests/test_holdout_phase_db.py` (gerçek DB, geri alınan işlem; yoksa ADIYLA SKIP); dalga 4 sonunda 0010'dan ÖNCE kırmızı, SONRA yeşil | T10 · dalga 4 sonu |
| m1 `<` → `<=` mutantı sağ | sonucu tam karar anında bilinen maç fikstürü | T8 |
| m6 seçim E'yi boşa oynatıyordu | `select` girdiyi S sonunda keser | T7 |
| m7 E görüldükten sonra "Revise" | Task 9 Step 5: revizyon Ruling olarak yazılır, E bundan sonra örneklem dışı SAYILMAZ | T9 |
| m8 walk-forward özet yok; scipy toleransı | `rows_digest` raporda; Task 5'te iki koşunun özeti karşılaştırılır | T7 · `test_the_rows_digest_is_stable_and_sees_a_changed_probability`; T5 |
| m9 P17 çelişkisi | 90 dk eşiği, alt küme yedeği reddedildi | P17 |
| m10 kredi güvenliği yalnız gözle | `shadow.yml` ve `history.yml` `ODDS_API_KEY` almaz testi | T11 · `test_the_credit_free_workflows_never_receive_the_odds_api_key` |
| m2, m3, m4, m5 | ERTELENDİ — aşağıdaki "ölçmedikleri" 24–27 | — |

## Plan-zamanı ölçümler

Bu plan yazılırken veritabanına bağlanılmadı; gerçek veride hiçbir şey ölçülmedi. Aşağıdakiler SENTETİK veride
ölçüldü ve yalnız kodun davranışını anlatır: bütün testler 1.757 passed / 3 skipped (taban `a398c31`: 1.553 passed / 2 skipped; üçüncü SKIP `test_holdout_phase_db`, `DATABASE_URL yok`); `leakage`
işaretli 333 (taban 265); DC fiti 6 takım × 180 maçta ~0,6 ms (gerçek bir ülke grubunda
takım ve maç sayısı onlarca kat büyük — süre Task 5'te ölçülür, tahmin edilmez). Gerçek veri ölçümleri (saatsiz satır,
yineleme, DC ve Elo süresi/RSS, seçim ve walk-forward süresi) Task 0, 5 ve 9'da, ölçüm belgesi
`docs/superpowers/specs/2026-09-23-faz3-olcumler.md`e yazılır.

---

## Görevler

### Task 0: scipy, paketler ve gerçek veri ölçümleri (dalga 0, controller)

**Kademe:** — (controller, tek commit + ölçüm belgesi) · **Dalga:** 0 · **Dal:** `main` üzerinde doğrudan

Dalga 1'in dört görevi paralel koşar; ikisi scipy'a, ikisi yeni paketlere yazar. Bağımlılık, mypy istisnası,
paket işaretleri ve kapının scipy'ı da yükleyen `paket-kurulu` adımı bu yüzden dalgadan ÖNCE tek commit'te gelir
(tek-yazar kuralı). Aynı görev, dalga 1'in tasarımını etkileyebilecek iki gerçek veri ölçümünü yapar.

**Files:**
- Create: `src/football_edge/model/__init__.py`, `src/football_edge/live/__init__.py` (boş)
- Modify: `pyproject.toml` (bağımlılık `scipy>=1.14`; `scipy.*` için mypy istisnası), `uv.lock`, `verify.sh` (`paket-kurulu`)
- Create: `docs/superpowers/specs/2026-09-23-faz3-olcumler.md` (Step 5)

**Interfaces:** Consumes — · Produces: `import scipy.optimize` her yerde; `football_edge.model`, `football_edge.live` paketleri.

- [ ] **Step 1: Kırmızı olduğunu gör** — kapının yeni biçimi scipy yokken düşmeli:

Run: `env PYTHONPATH= uv run python -c "import football_edge, scipy.optimize"`
Expected: FAIL — `ModuleNotFoundError: No module named 'scipy'`

- [ ] **Step 2: Paketler, bağımlılık, kapı**

<!-- plan: yeni src/football_edge/model/__init__.py -->
`src/football_edge/model/__init__.py` — boş dosya (paket işareti).
<!-- plan: yeni src/football_edge/live/__init__.py -->
`src/football_edge/live/__init__.py` — boş dosya (paket işareti).

`pyproject.toml` yaması:

<!-- plan: yama pyproject.toml -->
```diff
diff --git a/pyproject.toml b/pyproject.toml
index aa0dc83..fdb5d9d 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -11,6 +11,7 @@ dependencies = [
     "defusedxml>=0.7",
     "typesafe-sdk>=0.1",
     "numpy>=2.1",
+    "scipy>=1.14",
 ]
 
 [dependency-groups]
@@ -49,3 +50,8 @@ select = ["E", "F", "I", "UP", "B", "SIM", "T20"]
 python_version = "3.11"
 strict = true
 files = ["src", "scripts"]
+
+# scipy tip bilgisi taşımaz (Faz 3 dalga 0): dönüşleri çağıran yerde float()/np.asarray ile daraltılır.
+[[tool.mypy.overrides]]
+module = ["scipy", "scipy.*"]
+ignore_missing_imports = true
```

`verify.sh` yaması:

<!-- plan: yama verify.sh -->
```diff
diff --git a/verify.sh b/verify.sh
index 5962c1b..be92715 100755
--- a/verify.sh
+++ b/verify.sh
@@ -29,8 +29,9 @@ step "pytest"      uv run pytest -q
 # CI ise `python -m football_edge.collect` ile kurulu paketi çağırır. PYTHONPATH'in
 # boşaltılması kasıtlıdır — import'un src/'den değil kurulumdan geldiğini kanıtlar.
 # Kırmızı verirse onarım `uv sync --reinstall-package football-edge`; kapı gevşetilmez.
+# Faz 3: scipy'ın derlenmiş optimizer'ı da yüklenebilmeli (Dixon-Coles, havuz, seçim).
 step "paket-kurulu" env PYTHONPATH= uv run python -c \
-  "import football_edge, sys; sys.stdout.write(football_edge.__file__ + chr(10))"
+  "import football_edge, scipy.optimize, sys; sys.stdout.write(football_edge.__file__ + chr(10))"
 
 # Kaynak politikası ÇEVRİMDIŞI sorulur: ağ yok, secret yok, her push'ta koşar. Canlı sapmayı
 # sources-audit.yml günde bir ölçer. Robots'u ölçmeden "izinli" demek, spec §3.2'yi prose'a
```

Run: `uv lock && uv sync`
Expected: `uv.lock`ta `scipy` (Python 3.11 için 1.17.x); `uv sync` hatasız.

- [ ] **Step 3: Yeşil olduğunu gör**

Run: `TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-t0.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-t0.log`
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir`; pytest 1.553 passed / 2 skipped (taban `a398c31`, değişmedi).

- [ ] **Step 4: Mutasyon kanıtı** — `pyproject.toml`dan `"scipy>=1.14",` satırı çıkarılır, `uv sync` → `FAIL:
paket-kurulu` (ve `mypy`); geri alınır, `uv sync`.

- [ ] **Step 5: Gerçek veri ölçümleri** (yerel, `--env-file .env`; holdout anahtarsız okunamaz — `load_matches`
yalnız DEV + POST döner). Sonuçlar ölçüm belgesine, komutlarıyla:

```bash
uv run --env-file .env python - <<'PY'
from collections import Counter
from pathlib import Path
from football_edge.db import connect
from football_edge.history.catalog import MAIN, load_catalog
from football_edge.history.holdout import DEV_END
from football_edge.history.lock import load_lock
from football_edge.history.sync import load_matches
catalog = load_catalog(Path("config/history_leagues.yaml"))
kinds = {league.code: league.kind for league in catalog.leagues}
with connect() as conn:
    leagues = load_matches(conn, catalog, lock=load_lock(Path("config/history_lock.yaml")))
untimed = sum(1 for code, ms in leagues.items() if kinds[code] == MAIN for m in ms
              if m.season >= "1920" and m.date < DEV_END and m.kickoff is None)
keys = Counter((m.league, m.date, m.home, m.away) for ms in leagues.values() for m in ms)
print("§3/37 saatsiz 2019/20+ ana lig satırı (DEV):", untimed)
print("14g yinelenen (lig, tarih, ev, deplasman), DEV + sonrası:", sum(1 for n in keys.values() if n > 1))
PY
```

Beklenen: iki sayı da yazılır. Yinelenen sayısı 0 değilse Task 4'ün `DuplicateMatch`i gerçek veride oynatmayı
düşürür: dalga 1 başlamaz, bulgu kullanıcıya (tasarım 14g "Faz 3 ön koşulu"). Saatsiz sayısı ölçüm belgesine
ve Faz 3 HANDOFF'una girer (§3/37 kapanır ya da sayıyla açık kalır).

- [ ] **Step 6: Commit ve dalga 1'in açılışı**

```bash
git add pyproject.toml uv.lock verify.sh src/football_edge/model/__init__.py \
  src/football_edge/live/__init__.py docs/superpowers/specs/2026-09-23-faz3-olcumler.md
git commit -m "feat: Faz 3 dalga 0 — scipy, model/live paketleri, kapı scipy'ı yükler; ölçümler

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Kapı yeniden (Step 3'ün komutu). Sonra `git fetch origin && git merge --no-ff origin/main` (bot çıpaları;
rebase/force YOK), taze klon kapısı, `git push origin main`. Dalga 1'in dört worktree'si bu commit'ten açılır.

---

### Task 1: Dixon-Coles — saf fit ve skor matrisi (T1)

**Kademe:** K1 · **Dalga:** 1 · **Worktree/dal:** `.worktrees/wt-dc` · `feat/faz3-dc`

Zaman sönümlü, ρ düzeltmeli, sırt cezalı Dixon-Coles (tasarım §6.2). Fit L-BFGS-B ve ANALİTİK gradyanla (sayısal gradyan 2n+2 parametrede her adımda 2n+2 değerlendirme ister); gradyan bir testle sonlu farklara karşı sınanır. Fit yalnız `at`ten önceki ve pencere içindeki maçları okur — harness zaten geleceği vermez, bu ikinci katmandır ve Task 6'nın gelecek-fit kanaryası buna dayanır. Yakınsamayan fit `None` döner (Review Focus 2).

**Files:**
- Create: `src/football_edge/model/dixon_coles.py`
- Create: `tests/test_dixon_coles.py`

**Interfaces:**
- Consumes: `scipy.optimize.minimize` (Task 0), numpy.
- Produces: `GoalRecord`, `DCConfig`, `DCParams`, `fit`, `score_matrix`, `outcome_probs`, `totals_probs`, `strengths` (sözleşmedeki imzalar).

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_dixon_coles.py`:

<!-- plan: yeni tests/test_dixon_coles.py -->
```python
"""Dixon-Coles (Faz 3 tasarımı §6.2): gradyan, geri kazanım, zaman sınırı, skor matrisi.

Veri SENTETİK: bilinen güçlerle numpy'nin tohumlu üreteciyle çekilmiş goller.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pytest
from scipy.optimize import check_grad

from football_edge.model import dixon_coles as dc
from football_edge.model.dixon_coles import DCConfig, DCParams, GoalRecord

TEAMS = ("Alfa", "Beta", "Gama", "Delta", "Epsilon", "Zeta")
ATTACK = (0.45, 0.25, 0.05, -0.05, -0.25, -0.45)
DEFENCE = (-0.35, -0.2, 0.0, 0.05, 0.2, 0.3)
HOME = 0.3
FIRST = date(2020, 8, 1)
AT = date(2023, 7, 1)
FAST = DCConfig(xi=0.0, ridge=0.001, window_days=5000, min_matches=30)


def _season_records(rng: np.random.Generator, seasons: int = 6) -> tuple[GoalRecord, ...]:
    """Her sezon çift devreli lig; gün, sezonun ilk gününden maç sırasıyla artar."""
    found: list[GoalRecord] = []
    for season in range(seasons):
        day = FIRST + timedelta(days=season * 120)
        for h, home in enumerate(TEAMS):
            for a, away in enumerate(TEAMS):
                if h == a:
                    continue
                lam = math.exp(ATTACK[h] + DEFENCE[a] + HOME)
                mu = math.exp(ATTACK[a] + DEFENCE[h])
                found.append(
                    GoalRecord(home, away, int(rng.poisson(lam)), int(rng.poisson(mu)), day)
                )
                day += timedelta(days=1)
    return tuple(found)


RECORDS = _season_records(np.random.default_rng(20260923))


def _params(rho: float = 0.0, home: float = HOME) -> DCParams:
    order = sorted(range(len(TEAMS)), key=lambda index: TEAMS[index])
    return DCParams(
        teams=tuple(TEAMS[index] for index in order),
        attack=tuple(ATTACK[index] for index in order),
        defence=tuple(DEFENCE[index] for index in order),
        home=home,
        rho=rho,
        fitted_on=AT,
    )


def test_the_gradient_matches_finite_differences() -> None:
    used = dc._used(RECORDS, AT, 5000)
    teams = tuple(sorted(TEAMS))
    data = dc._data(used, teams, AT, 0.002)
    theta = np.random.default_rng(1).normal(0.0, 0.2, 2 * len(teams) + 2)
    theta[-1] = 0.05

    error = check_grad(
        lambda t: dc._objective(t, data, 0.01)[0],
        lambda t: dc._objective(t, data, 0.01)[1],
        theta,
    )

    assert error < 1e-5


def test_the_fit_recovers_known_strength_order_and_home_advantage() -> None:
    params = dc.fit(RECORDS, at=AT, config=FAST)

    assert params is not None
    strengths = dc.strengths(params)
    net = {team: attack - defence for team, (attack, defence) in strengths.items()}
    assert sorted(net, key=net.__getitem__, reverse=True)[:2] == ["Alfa", "Beta"]
    assert sorted(net, key=net.__getitem__)[:2] == ["Zeta", "Epsilon"]
    assert params.home == pytest.approx(HOME, abs=0.12)
    assert abs(params.rho) <= FAST.rho_bound


@pytest.mark.leakage
def test_the_fit_ignores_matches_on_or_after_the_fit_day() -> None:
    """Gelecek-fit savunması: `at` günü ve sonrası hiçbir maç parametreyi değiştirmez."""
    future = (
        GoalRecord("Zeta", "Alfa", 9, 0, AT),
        GoalRecord("Zeta", "Beta", 8, 0, AT + timedelta(days=3)),
    )

    assert dc.fit((*RECORDS, *future), at=AT, config=FAST) == dc.fit(RECORDS, at=AT, config=FAST)


def test_the_fit_ignores_matches_older_than_the_window() -> None:
    windowed = DCConfig(xi=0.0, ridge=0.001, window_days=400, min_matches=30)
    old = GoalRecord("Zeta", "Alfa", 9, 0, AT - timedelta(days=401))

    assert dc.fit((*RECORDS, old), at=AT, config=windowed) == dc.fit(
        RECORDS, at=AT, config=windowed
    )


def test_time_decay_weights_recent_matches_more() -> None:
    """Son sezonda Zeta'yı güçlü yapan maçlar sönümle daha çok, sönümsüz daha az etki eder."""
    late = tuple(
        GoalRecord("Zeta", other, 3, 0, AT - timedelta(days=5 + index))
        for index, other in enumerate(TEAMS[:5] * 2)
    )
    decayed = dc.fit((*RECORDS, *late), at=AT, config=DCConfig(xi=0.01, ridge=0.001))
    flat = dc.fit((*RECORDS, *late), at=AT, config=DCConfig(xi=0.0, ridge=0.001, window_days=5000))

    assert decayed is not None and flat is not None
    assert dc.strengths(decayed)["Zeta"][0] > dc.strengths(flat)["Zeta"][0]


def test_too_few_matches_give_no_fit() -> None:
    assert dc.fit(RECORDS[:29], at=AT, config=FAST) is None


def test_warm_start_reaches_the_same_optimum() -> None:
    cold = dc.fit(RECORDS, at=AT, config=FAST)
    assert cold is not None

    warm = dc.fit(RECORDS, at=AT, config=FAST, start=cold)

    assert warm is not None
    assert warm.attack == pytest.approx(cold.attack, abs=1e-4)
    assert warm.home == pytest.approx(cold.home, abs=1e-4)


def test_the_fit_is_deterministic() -> None:
    assert dc.fit(RECORDS, at=AT, config=FAST) == dc.fit(RECORDS, at=AT, config=FAST)


def test_an_unknown_team_has_no_score_matrix() -> None:
    assert dc.score_matrix(_params(), "Alfa", "Yabancı", 10) is None


def test_without_rho_the_matrix_is_the_normalised_product_of_two_poissons() -> None:
    matrix = dc.score_matrix(_params(rho=0.0), "Alfa", "Zeta", 10)

    assert matrix is not None
    lam = math.exp(ATTACK[0] + DEFENCE[5] + HOME)
    mu = math.exp(ATTACK[5] + DEFENCE[0])
    raw = np.outer(
        [math.exp(-lam) * lam**k / math.factorial(k) for k in range(11)],
        [math.exp(-mu) * mu**k / math.factorial(k) for k in range(11)],
    )
    assert matrix == pytest.approx(raw / raw.sum())
    assert float(matrix.sum()) == pytest.approx(1.0)


def test_rho_moves_mass_between_the_four_low_scores() -> None:
    plain = dc.score_matrix(_params(rho=0.0), "Gama", "Delta", 10)
    adjusted = dc.score_matrix(_params(rho=-0.1), "Gama", "Delta", 10)

    assert plain is not None and adjusted is not None
    # ρ < 0: 0-0 ve 1-1 artar, 1-0 ve 0-1 azalır (normalize öncesi çarpanların yönü).
    assert adjusted[0, 0] > plain[0, 0] and adjusted[1, 1] > plain[1, 1]
    assert adjusted[1, 0] < plain[1, 0] and adjusted[0, 1] < plain[0, 1]


def test_outcome_probabilities_read_rows_as_home_goals() -> None:
    matrix = np.zeros((3, 3))
    matrix[2, 0], matrix[1, 1], matrix[0, 1] = 0.5, 0.3, 0.2

    assert dc.outcome_probs(matrix) == pytest.approx((0.5, 0.3, 0.2))


def test_totals_count_three_or_more_goals_as_over() -> None:
    matrix = np.zeros((4, 4))
    matrix[1, 1], matrix[2, 1], matrix[0, 3] = 0.6, 0.3, 0.1

    assert dc.totals_probs(matrix) == pytest.approx((0.4, 0.6))


def test_a_stronger_home_side_is_favoured() -> None:
    matrix = dc.score_matrix(_params(), "Alfa", "Zeta", 10)

    assert matrix is not None
    home, draw, away = dc.outcome_probs(matrix)
    assert home > draw and home > away
    assert home + draw + away == pytest.approx(1.0)


def test_a_fit_that_does_not_converge_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bayat parametreyle tahmin hatayı gizlerdi: yakınsamayan fit None, strateji tahmin vermez."""

    @dataclass(frozen=True)
    class Failed:
        x: np.ndarray
        success: bool = False
        message: str = "ABNORMAL_TERMINATION_IN_LNSRCH"

    monkeypatch.setattr(dc, "minimize", lambda fun, x0, **kwargs: Failed(x0))

    assert dc.fit(RECORDS, at=AT, config=FAST) is None
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_dixon_coles.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.model.dixon_coles'`

- [ ] **Step 3: Uygulamayı yaz**

`src/football_edge/model/dixon_coles.py`:

<!-- plan: yeni src/football_edge/model/dixon_coles.py -->
```python
"""Zaman sönümlü Dixon-Coles (Faz 3 tasarımı §6.2, R131): saf fit ve skor matrisi.

Gol süreci: ev golü `Poisson(exp(a_ev + d_dep + h))`, deplasman golü `Poisson(exp(a_dep + d_ev))`;
düşük skorlarda `τ(ρ)` düzeltmesi. Maç ağırlığı `exp(−ξ · gün)`; güçlere sırt (L2) cezası hem
az maçlı takımı hem kimlik kısıtını karşılar. Fit YALNIZ `at`ten önceki maçları görür — çağıran
ne verirse versin (sızıntı savunması burada da bir katman). Yakınsamayan fit `None` döner:
bayat parametreyle tahmin etmek hatayı gizlerdi.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.optimize import minimize

Floats = npt.NDArray[np.float64]
Ints = npt.NDArray[np.int64]

_TAU_FLOOR = 1e-10
_START_HOME = 0.25
_MAX_ITERATIONS = 500


@dataclass(frozen=True)
class GoalRecord:
    home: str
    away: str
    home_goals: int
    away_goals: int
    day: date


@dataclass(frozen=True)
class DCConfig:
    xi: float = 0.0019  # gün başına sönüm; yarı ömür ~1 yıl (S'de seçilir)
    ridge: float = 0.01
    window_days: int = 1095
    max_goals: int = 10
    rho_bound: float = 0.2
    min_matches: int = 30


@dataclass(frozen=True)
class DCParams:
    teams: tuple[str, ...]  # sıralı
    attack: tuple[float, ...]  # log ölçek
    defence: tuple[float, ...]  # log ölçek; büyük = kötü savunma
    home: float
    rho: float
    fitted_on: date

    def index(self, team: str) -> int | None:
        position = bisect.bisect_left(self.teams, team)
        if position < len(self.teams) and self.teams[position] == team:
            return position
        return None


@dataclass(frozen=True)
class _Data:
    home: Ints
    away: Ints
    x: Floats
    y: Floats
    w: Floats
    size: int


def _used(records: Sequence[GoalRecord], at: date, window_days: int) -> list[GoalRecord]:
    return [
        record for record in records if record.day < at and (at - record.day).days <= window_days
    ]


def _data(used: Sequence[GoalRecord], teams: tuple[str, ...], at: date, xi: float) -> _Data:
    position = {team: index for index, team in enumerate(teams)}
    ages = np.array([(at - record.day).days for record in used], dtype=np.float64)
    return _Data(
        home=np.array([position[record.home] for record in used], dtype=np.int64),
        away=np.array([position[record.away] for record in used], dtype=np.int64),
        x=np.array([record.home_goals for record in used], dtype=np.float64),
        y=np.array([record.away_goals for record in used], dtype=np.float64),
        w=np.exp(-xi * ages),
        size=len(teams),
    )


def _tau_terms(
    data: _Data, lam: Floats, mu: Floats, rho: float
) -> tuple[Floats, Floats, Floats, Floats]:
    """(τ, ∂logτ/∂η_ev, ∂logτ/∂η_dep, ∂logτ/∂ρ) maç başına."""
    zero_zero = (data.x == 0) & (data.y == 0)
    zero_one = (data.x == 0) & (data.y == 1)
    one_zero = (data.x == 1) & (data.y == 0)
    one_one = (data.x == 1) & (data.y == 1)
    tau = np.ones_like(lam)
    tau = np.where(zero_zero, 1.0 - lam * mu * rho, tau)
    tau = np.where(zero_one, 1.0 + lam * rho, tau)
    tau = np.where(one_zero, 1.0 + mu * rho, tau)
    tau = np.where(one_one, 1.0 - rho, tau)
    tau = np.maximum(tau, _TAU_FLOOR)
    d_home = np.where(zero_zero, -lam * mu * rho / tau, 0.0)
    d_home = np.where(zero_one, lam * rho / tau, d_home)
    d_away = np.where(zero_zero, -lam * mu * rho / tau, 0.0)
    d_away = np.where(one_zero, mu * rho / tau, d_away)
    d_rho = np.where(zero_zero, -lam * mu / tau, 0.0)
    d_rho = np.where(zero_one, lam / tau, d_rho)
    d_rho = np.where(one_zero, mu / tau, d_rho)
    d_rho = np.where(one_one, -1.0 / tau, d_rho)
    return tau, d_home, d_away, d_rho


def _objective(theta: Floats, data: _Data, ridge: float) -> tuple[float, Floats]:
    """Ağırlıklı ortalama negatif log olabilirlik + sırt cezası ve gradyanı."""
    n = data.size
    attack, defence = theta[:n], theta[n : 2 * n]
    home, rho = float(theta[2 * n]), float(theta[2 * n + 1])
    eta_home = attack[data.home] + defence[data.away] + home
    eta_away = attack[data.away] + defence[data.home]
    lam, mu = np.exp(eta_home), np.exp(eta_away)
    tau, d_home, d_away, d_rho = _tau_terms(data, lam, mu, rho)
    total = float(np.sum(data.w))
    ll = data.w * (np.log(tau) + data.x * eta_home - lam + data.y * eta_away - mu)
    g_home = data.w * (data.x - lam + d_home)
    g_away = data.w * (data.y - mu + d_away)
    grad_attack = np.bincount(data.home, g_home, n) + np.bincount(data.away, g_away, n)
    grad_defence = np.bincount(data.away, g_home, n) + np.bincount(data.home, g_away, n)
    penalty = ridge * float(attack @ attack + defence @ defence)
    value = -float(np.sum(ll)) / total + penalty
    gradient = np.concatenate(
        [
            -grad_attack / total + 2.0 * ridge * attack,
            -grad_defence / total + 2.0 * ridge * defence,
            np.array([-float(np.sum(g_home)) / total, -float(np.sum(data.w * d_rho)) / total]),
        ]
    )
    return value, gradient


def _start(teams: tuple[str, ...], start: DCParams | None) -> Floats:
    n = len(teams)
    theta = np.zeros(2 * n + 2)
    theta[2 * n] = _START_HOME
    if start is None:
        return theta
    for index, team in enumerate(teams):
        previous = start.index(team)
        if previous is not None:
            theta[index] = start.attack[previous]
            theta[n + index] = start.defence[previous]
    theta[2 * n] = start.home
    theta[2 * n + 1] = start.rho
    return theta


def fit(
    records: Sequence[GoalRecord],
    *,
    at: date,
    config: DCConfig,
    start: DCParams | None = None,
) -> DCParams | None:
    """`at`ten ÖNCEKİ ve pencere içindeki maçlarla fit; az maçta ya da yakınsamazsa None."""
    used = _used(records, at, config.window_days)
    if len(used) < config.min_matches:
        return None
    teams = tuple(sorted({record.home for record in used} | {record.away for record in used}))
    data = _data(used, teams, at, config.xi)
    n = len(teams)
    bounds = [(None, None)] * (2 * n + 1) + [(-config.rho_bound, config.rho_bound)]
    result: Any = minimize(
        _objective,
        _start(teams, start),
        args=(data, config.ridge),
        jac=True,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": _MAX_ITERATIONS},
    )
    theta = np.asarray(result.x, dtype=np.float64)
    if not bool(result.success) or not bool(np.all(np.isfinite(theta))):
        return None
    return DCParams(
        teams=teams,
        attack=tuple(float(value) for value in theta[:n]),
        defence=tuple(float(value) for value in theta[n : 2 * n]),
        home=float(theta[2 * n]),
        rho=float(theta[2 * n + 1]),
        fitted_on=at,
    )


def _poisson(rate: float, max_goals: int) -> Floats:
    return np.array(
        [math.exp(k * math.log(rate) - rate - math.lgamma(k + 1)) for k in range(max_goals + 1)]
    )


def score_matrix(params: DCParams, home: str, away: str, max_goals: int) -> Floats | None:
    """P(ev = i, deplasman = j), i, j ≤ `max_goals`, toplamı 1'e normalize; takım yoksa None."""
    h, a = params.index(home), params.index(away)
    if h is None or a is None:
        return None
    lam = math.exp(params.attack[h] + params.defence[a] + params.home)
    mu = math.exp(params.attack[a] + params.defence[h])
    matrix = np.outer(_poisson(lam, max_goals), _poisson(mu, max_goals))
    matrix[0, 0] *= max(1.0 - lam * mu * params.rho, _TAU_FLOOR)
    matrix[0, 1] *= max(1.0 + lam * params.rho, _TAU_FLOOR)
    matrix[1, 0] *= max(1.0 + mu * params.rho, _TAU_FLOOR)
    matrix[1, 1] *= max(1.0 - params.rho, _TAU_FLOOR)
    return np.asarray(matrix / matrix.sum(), dtype=np.float64)


def outcome_probs(matrix: Floats) -> tuple[float, float, float]:
    """(ev, beraberlik, deplasman) — satır ev golü, sütun deplasman golü."""
    home = float(np.tril(matrix, -1).sum())
    draw = float(np.trace(matrix))
    away = float(np.triu(matrix, 1).sum())
    return home, draw, away


def totals_probs(matrix: Floats, line: float = 2.5) -> tuple[float, float]:
    """(üst, alt) — `MARKET_OUTCOMES[TOTALS_25]` sırası."""
    goals = np.add.outer(np.arange(matrix.shape[0]), np.arange(matrix.shape[1]))
    over = float(matrix[goals > line].sum())
    return over, 1.0 - over


def strengths(params: DCParams) -> Mapping[str, tuple[float, float]]:
    """Takım → (atak, savunma); rapor ve test için."""
    return MappingProxyType(
        {
            team: (params.attack[index], params.defence[index])
            for index, team in enumerate(params.teams)
        }
    )
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_dixon_coles.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — 15 passed

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `_used`: `record.day < at` → `record.day <= at` | `tests/test_dixon_coles.py::test_the_fit_ignores_matches_on_or_after_the_fit_day` |
| 2 | `_objective`: ρ gradyanının işareti ters | `tests/test_dixon_coles.py::test_the_gradient_matches_finite_differences` |
| 3 | `fit`: `not bool(result.success) or` silinir | `tests/test_dixon_coles.py::test_a_fit_that_does_not_converge_returns_nothing` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add src/football_edge/model/dixon_coles.py \
  tests/test_dixon_coles.py
git commit -m "feat: Faz 3 T1 — zaman sönümlü Dixon-Coles (analitik gradyan, ρ, sırt cezası)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
### Task 2: Fit edilebilir Elo stratejisi (T3)

**Kademe:** K1 · **Dalga:** 1 · **Worktree/dal:** `.worktrees/wt-elo` · `feat/faz3-elo`

İskele `EloPointInTime`ın yerine geçen, seçimi S bölgesinde yapılacak Elo (tasarım §6.1): marj biçimi (yok/doğrusal/log), sezon arası ortalamaya dönüş (`season_gap_days` aşılınca), görülmemiş takımın grup ortalamasının `newcomer_offset` altından başlaması ve beraberliğin reyting farkına bağlanması `P(D) = δ·4E(1−E)` (P11). `fit_draw` δ'yı sabit E dizisinde kapalı biçimde fit eder: seçim her aday için δ'yı yeniden oynatmadan bulur. Reyting (grup, takım) anahtarlı (R94). Testler bağlamı YALNIZ `harness._context`/`replay` ile kurar (Task 4 aynı dalgada `DecisionContext`i taşıyor).

**Files:**
- Create: `src/football_edge/model/elo_model.py`
- Create: `tests/test_elo_model.py`

**Interfaces:**
- Consumes: `football_edge.elo.expected_home`, `EloConfig`; harness'ın `DecisionContext`, `Prediction`, `ResultRecord`; scipy `minimize_scalar`.
- Produces: `EloModelConfig`, `EloModel` (`name == "elo_fit"`), `margin_multiplier`, `elo_probs`, `expectation`, `fit_draw`, `MAX_DRAW`, marj sabitleri.

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_elo_model.py`:

<!-- plan: yeni tests/test_elo_model.py -->
```python
"""Fit edilebilir Elo (Faz 3 tasarımı §6.1). Bağlamlar yalnız `harness._context` ve `replay` ile
kurulur: `DecisionContext`in alanları dalga 1'in başka bir görevinde değişebilir."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from types import MappingProxyType

import numpy as np
import pytest

from football_edge.backtest import harness
from football_edge.backtest.harness import DecisionContext, ResultRecord, replay
from football_edge.elo import EloConfig, expected_home, updated
from football_edge.model.elo_model import (
    LINEAR_MARGIN,
    LOG_MARGIN,
    NO_MARGIN,
    EloModel,
    EloModelConfig,
    elo_probs,
    expectation,
    fit_draw,
    margin_multiplier,
)
from tests.backtest_builders import hist_match

DECIDED = datetime(2024, 8, 9, 11, tzinfo=UTC)


def _result(
    home: str, away: str, goals: tuple[int, int], day: date = date(2024, 8, 3), league: str = "E0"
) -> ResultRecord:
    return ResultRecord(
        league=league,
        date=day,
        home=home,
        away=away,
        home_goals=goals[0],
        away_goals=goals[1],
        known_at=datetime.combine(day, time(17), tzinfo=UTC),
    )


def _context(
    home: str = "Alfa", away: str = "Beta", day: date = date(2024, 8, 10), league: str = "E0"
) -> DecisionContext:
    match = hist_match(
        day=day,
        kickoff=datetime.combine(day, time(14), tzinfo=UTC),
        home=home,
        away=away,
        league=league,
    )
    return harness._context(0, match, DECIDED)


def test_with_scaffold_settings_the_update_equals_the_phase_one_engine() -> None:
    config = EloModelConfig(k=20.0, home_advantage=65.0, margin=LINEAR_MARGIN)

    model = EloModel(config=config).observe(_result("Alfa", "Beta", (3, 0)))

    home, away = updated(1500.0, 1500.0, 3, 0, EloConfig(k=20.0, home_advantage=65.0))
    assert model.ratings[("E0", "Alfa")] == pytest.approx(home)
    assert model.ratings[("E0", "Beta")] == pytest.approx(away)


def test_margin_forms() -> None:
    assert margin_multiplier(1, 0, LINEAR_MARGIN) == 1.0
    assert margin_multiplier(4, 0, NO_MARGIN) == 1.0
    assert margin_multiplier(4, 0, LINEAR_MARGIN) == 2.5
    assert margin_multiplier(0, 4, LOG_MARGIN) == pytest.approx(1.0 + math.log(4))


@pytest.mark.parametrize("expected", [0.0, 0.2, 0.5, 0.83, 1.0])
def test_probabilities_are_valid_and_the_draw_peaks_at_even(expected: float) -> None:
    home, draw, away = elo_probs(expected, 0.5)

    assert min(home, draw, away) >= 0.0
    assert home + draw + away == pytest.approx(1.0)
    assert expectation((home, draw, away)) == pytest.approx(expected)
    assert draw <= elo_probs(0.5, 0.5)[1]


def test_the_prediction_uses_the_home_advantage_and_the_draw_share() -> None:
    config = EloModelConfig(home_advantage=80.0, draw=0.3)
    model = EloModel(
        config=config, ratings=MappingProxyType({("E0", "Alfa"): 1600.0, ("E0", "Beta"): 1550.0})
    )

    prediction = model.predict(_context())

    expected = expected_home(1600.0, 1550.0, EloConfig(home_advantage=80.0))
    assert prediction.probs == pytest.approx(elo_probs(expected, 0.3))
    assert prediction.strategy == "elo_fit"


def test_invalid_settings_are_refused() -> None:
    with pytest.raises(ValueError, match="marj"):
        EloModelConfig(margin="square")
    with pytest.raises(ValueError, match="beraberlik"):
        EloModelConfig(draw=0.6)
    with pytest.raises(ValueError, match="dönüş"):
        EloModelConfig(regress=1.5)


def test_a_newcomer_starts_below_the_group_mean() -> None:
    ratings = MappingProxyType(
        {("E0", "Alfa"): 1600.0, ("E0", "Beta"): 1500.0, ("SP1", "Gama"): 2000.0}
    )
    model = EloModel(config=EloModelConfig(newcomer_offset=100.0, draw=0.0), ratings=ratings)

    prediction = model.predict(_context(home="Yeni", away="Beta"))

    expected = expected_home(1450.0, 1500.0, EloConfig())
    assert prediction.probs == pytest.approx(elo_probs(expected, 0.0))


def test_the_first_team_of_a_group_starts_at_the_initial_rating() -> None:
    model = EloModel(config=EloModelConfig(newcomer_offset=100.0))

    assert model._current(("E0", "Alfa"), date(2024, 8, 3)) == pytest.approx(1400.0)


def test_a_long_gap_regresses_the_rating_toward_the_group_mean() -> None:
    ratings = MappingProxyType({("E0", "Alfa"): 1700.0, ("E0", "Beta"): 1500.0})
    seen = MappingProxyType({("E0", "Alfa"): date(2024, 5, 20), ("E0", "Beta"): date(2024, 8, 1)})
    model = EloModel(config=EloModelConfig(regress=0.25), ratings=ratings, last_seen=seen)

    # grup ortalaması 1600; dönüş payı 0.25 → 1600 + 0.75 · 100
    assert model._current(("E0", "Alfa"), date(2024, 8, 10)) == pytest.approx(1675.0)
    assert model._current(("E0", "Beta"), date(2024, 8, 10)) == pytest.approx(1500.0)


def test_observe_stores_the_regressed_rating_before_the_update() -> None:
    ratings = MappingProxyType({("E0", "Alfa"): 1700.0, ("E0", "Beta"): 1500.0})
    seen = MappingProxyType({("E0", "Alfa"): date(2024, 5, 20), ("E0", "Beta"): date(2024, 5, 20)})
    config = EloModelConfig(regress=0.25, k=0.0)

    model = EloModel(config=config, ratings=ratings, last_seen=seen).observe(
        _result("Alfa", "Beta", (1, 1), date(2024, 8, 10))
    )

    assert model.ratings[("E0", "Alfa")] == pytest.approx(1675.0)
    assert model.last_seen[("E0", "Alfa")] == date(2024, 8, 10)


def test_observe_returns_a_new_value_and_leaves_the_old_one_untouched() -> None:
    before = EloModel()

    after = before.observe(_result("Alfa", "Beta", (2, 0)))

    assert dict(before.ratings) == {} and after is not before
    assert isinstance(after.ratings, MappingProxyType)


def test_groups_keep_same_named_teams_apart_and_join_leagues_of_a_country() -> None:
    groups = MappingProxyType({"E0": "England", "E1": "England", "SP1": "Spain"})
    model = EloModel(groups=groups).observe(_result("Alfa", "Beta", (2, 0), league="E1"))

    assert ("England", "Alfa") in model.ratings
    assert (
        model._current(("Spain", "Alfa"), date(2024, 8, 10)) != model.ratings[("England", "Alfa")]
    )


@pytest.mark.leakage
def test_ratings_at_a_decision_come_only_from_results_known_before_it() -> None:
    """Cuma kararı cumartesi sonucunu görmez; bir sonraki haftanın kararı görür."""
    days = [date(2024, 8, 3) + timedelta(weeks=week) for week in range(2)]
    matches = tuple(
        hist_match(
            day=day,
            kickoff=datetime.combine(day, time(14), tzinfo=UTC),
            goals=(4, 0),
            line=index + 1,
        )
        for index, day in enumerate(days)
    )

    result = replay(matches, EloModel(config=EloModelConfig(draw=0.0)))

    first, second = (prediction.probs for prediction in result.predictions)
    assert first == pytest.approx(elo_probs(expected_home(1500.0, 1500.0, EloConfig()), 0.0))
    assert second[0] > first[0]


def test_fit_draw_recovers_the_draw_share() -> None:
    rng = np.random.default_rng(11)
    expectations = [float(value) for value in rng.uniform(0.2, 0.8, 6000)]
    outcomes = [int(rng.choice(3, p=elo_probs(e, 0.3))) for e in expectations]

    assert fit_draw(expectations, outcomes) == pytest.approx(0.3, abs=0.03)


def test_fit_draw_refuses_mismatched_input() -> None:
    with pytest.raises(ValueError):
        fit_draw([0.5], [])
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_elo_model.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.model.elo_model'`

- [ ] **Step 3: Uygulamayı yaz**

`src/football_edge/model/elo_model.py`:

<!-- plan: yeni src/football_edge/model/elo_model.py -->
```python
"""Fit edilebilir Elo (Faz 3 tasarımı §6.1, R131): iskele `EloPointInTime`ın yerine geçen strateji.

Yenilikler: marj biçimi seçilir (yok / doğrusal / log), sezon arası ortalamaya dönüş, görülmemiş
takımın grup ortalamasının altından başlaması ve beraberliğin reyting farkına bağlanması
(`P(D) = δ · 4E(1 − E)`; iskele sabit `draw_rate` kullanıyordu). Reyting (grup, takım)
anahtarlıdır (R94). Değerler iskeledir; seçimi walk-forward'un S bölgesi yapar (R129).
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

from scipy.optimize import minimize_scalar

from football_edge.backtest.harness import DecisionContext, Prediction, ResultRecord
from football_edge.elo import EloConfig, expected_home

NO_MARGIN = "none"
LINEAR_MARGIN = "linear"
LOG_MARGIN = "log"
MARGINS = frozenset({NO_MARGIN, LINEAR_MARGIN, LOG_MARGIN})
MAX_DRAW = 0.5
_LOG_FLOOR = 1e-15

Key = tuple[str, str]


@dataclass(frozen=True)
class EloModelConfig:
    k: float = 20.0
    home_advantage: float = 65.0
    margin: str = LINEAR_MARGIN
    regress: float = 0.0  # sezon arasında ortalamaya dönüş payı, [0, 1]
    newcomer_offset: float = 0.0  # görülmemiş takım: grup ortalaması − offset
    draw: float = 0.26  # δ, [0, MAX_DRAW]
    season_gap_days: int = 60
    initial: float = 1500.0

    def __post_init__(self) -> None:
        if self.margin not in MARGINS:
            raise ValueError(f"bilinmeyen marj biçimi: {self.margin!r}")
        if not 0.0 <= self.draw <= MAX_DRAW:
            raise ValueError(f"beraberlik payı [0, {MAX_DRAW}] dışında: {self.draw}")
        if not 0.0 <= self.regress <= 1.0:
            raise ValueError(f"ortalamaya dönüş payı [0, 1] dışında: {self.regress}")


def margin_multiplier(home_goals: int, away_goals: int, form: str) -> float:
    margin = abs(home_goals - away_goals)
    if form == NO_MARGIN or margin <= 1:
        return 1.0
    if form == LINEAR_MARGIN:
        return 1.0 + (margin - 1) * 0.5
    return 1.0 + math.log(margin)


def elo_probs(expected: float, draw: float) -> tuple[float, float, float]:
    """E (ev beklentisi) → (H, D, A); `draw ≤ 0.5` iken üçü de ≥ 0 ve toplam 1."""
    tie = draw * 4.0 * expected * (1.0 - expected)
    return expected - tie / 2.0, tie, 1.0 - expected - tie / 2.0


def expectation(probs: Sequence[float]) -> float:
    """`elo_probs`un tersi: E = H + D/2 (δ'dan bağımsız)."""
    return probs[0] + probs[1] / 2.0


def fit_draw(expectations: Sequence[float], outcomes: Sequence[int]) -> float:
    """Sabit E dizisi ve sonuçlar (0=H, 1=D, 2=A) → log loss'u en küçük δ."""
    if len(expectations) != len(outcomes) or not outcomes:
        raise ValueError(f"{len(expectations)} beklenti, {len(outcomes)} sonuç")

    def loss(draw: float) -> float:
        return -math.fsum(
            math.log(max(elo_probs(e, draw)[o], _LOG_FLOOR))
            for e, o in zip(expectations, outcomes, strict=True)
        ) / len(outcomes)

    result: Any = minimize_scalar(loss, bounds=(0.0, MAX_DRAW), method="bounded")
    return float(result.x)


def _empty_ratings() -> Mapping[Key, float]:
    return MappingProxyType({})


def _empty_days() -> Mapping[Key, dt.date]:
    return MappingProxyType({})


def _empty_groups() -> Mapping[str, str]:
    return MappingProxyType({})


@dataclass(frozen=True)
class EloModel:
    config: EloModelConfig = EloModelConfig()
    groups: Mapping[str, str] = field(default_factory=_empty_groups)
    ratings: Mapping[Key, float] = field(default_factory=_empty_ratings)
    last_seen: Mapping[Key, dt.date] = field(default_factory=_empty_days)

    @property
    def name(self) -> str:
        return "elo_fit"

    def _key(self, league: str, team: str) -> Key:
        return self.groups.get(league, league), team

    def _group_mean(self, group: str) -> float:
        values = [rating for (owner, _), rating in self.ratings.items() if owner == group]
        return math.fsum(values) / len(values) if values else self.config.initial

    def _current(self, key: Key, day: dt.date) -> float:
        """`day`deki reyting: görülmemişse grup ortalaması − offset; uzun aradan sonra dönüş."""
        rating = self.ratings.get(key)
        if rating is None:
            return self._group_mean(key[0]) - self.config.newcomer_offset
        seen = self.last_seen.get(key)
        if seen is not None and (day - seen).days > self.config.season_gap_days:
            mean = self._group_mean(key[0])
            return mean + (1.0 - self.config.regress) * (rating - mean)
        return rating

    def _expected(self, home: float, away: float) -> float:
        return expected_home(
            home, away, EloConfig(k=self.config.k, home_advantage=self.config.home_advantage)
        )

    def observe(self, result: ResultRecord) -> EloModel:
        home_key = self._key(result.league, result.home)
        away_key = self._key(result.league, result.away)
        home = self._current(home_key, result.date)
        away = self._current(away_key, result.date)
        actual = (
            1.0
            if result.home_goals > result.away_goals
            else 0.0
            if result.home_goals < result.away_goals
            else 0.5
        )
        multiplier = margin_multiplier(result.home_goals, result.away_goals, self.config.margin)
        change = self.config.k * multiplier * (actual - self._expected(home, away))
        return replace(
            self,
            ratings=MappingProxyType(
                {**self.ratings, home_key: home + change, away_key: away - change}
            ),
            last_seen=MappingProxyType(
                {**self.last_seen, home_key: result.date, away_key: result.date}
            ),
        )

    def predict(self, context: DecisionContext) -> Prediction:
        home = self._current(self._key(context.league, context.home), context.date)
        away = self._current(self._key(context.league, context.away), context.date)
        probs = elo_probs(self._expected(home, away), self.config.draw)
        return Prediction(context.match_index, self.name, probs)
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_elo_model.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — 18 passed

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `elo_probs`: `tie / 2.0` yerine `tie` (normalize bozulur) | `tests/test_elo_model.py` |
| 2 | `_current`: `(1.0 - regress)` yerine `regress` | `tests/test_elo_model.py::test_a_long_gap_regresses_the_rating_toward_the_group_mean` |
| 3 | `_current`: `- newcomer_offset` yerine `+` | `tests/test_elo_model.py::test_a_newcomer_starts_below_the_group_mean` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add src/football_edge/model/elo_model.py \
  tests/test_elo_model.py
git commit -m "feat: Faz 3 T3 — fit edilebilir Elo (marj biçimi, ortalamaya dönüş, reyting farkına bağlı beraberlik)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
### Task 3: Log-doğrusal görüş havuzu (T4)

**Kademe:** K1 · **Dalga:** 1 · **Worktree/dal:** `.worktrees/wt-pool` · `feat/faz3-pool`

`p ∝ exp(Σ wᵢ log pᵢ)`, ağırlıklar `[0, 5]` (tasarım §6.3). Başlangıç yalnız piyasa `(1, 0, …)`: `w = (1, 0, 0)` havuzun içinde olduğu için fit edildiği veride harman piyasadan kötü olamaz — W1'in (Task 12) dayanağı bir testle sabitlenir. Fit L-BFGS-B, analitik gradyan (testle sonlu farka karşı).

**Files:**
- Create: `src/football_edge/model/pool.py`
- Create: `tests/test_pool.py`

**Interfaces:**
- Consumes: scipy `minimize` (Task 0).
- Produces: `pool`, `fit_weights`, `TooFewMatches`, `MIN_FIT_MATCHES = 300`, `MAX_WEIGHT = 5.0`.

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_pool.py`:

<!-- plan: yeni tests/test_pool.py -->
```python
"""Görüş havuzu (Faz 3 tasarımı §6.3): havuzlama kuralı ve ağırlık fiti. Veri SENTETİK."""

from __future__ import annotations

import math

import numpy as np
import pytest

from football_edge.model import pool as pooling
from football_edge.model.pool import MIN_FIT_MATCHES, TooFewMatches, fit_weights, pool

MARKET = (0.5, 0.3, 0.2)
MODEL = (0.2, 0.3, 0.5)


def test_weight_one_on_the_first_component_returns_it() -> None:
    assert pool((MARKET, MODEL), (1.0, 0.0)) == pytest.approx(MARKET)


def test_pooling_is_geometric_and_normalised() -> None:
    raw = [math.sqrt(m * o) for m, o in zip(MARKET, MODEL, strict=True)]

    assert pool((MARKET, MODEL), (0.5, 0.5)) == pytest.approx([value / sum(raw) for value in raw])


def test_zero_weights_give_the_uniform_distribution() -> None:
    assert pool((MARKET, MODEL), (0.0, 0.0)) == pytest.approx((1 / 3, 1 / 3, 1 / 3))


def test_a_zero_probability_does_not_break_the_pool() -> None:
    probs = pool(((1.0, 0.0, 0.0), MODEL), (1.0, 1.0))

    assert all(math.isfinite(value) for value in probs)
    assert sum(probs) == pytest.approx(1.0)


def test_negative_or_mismatched_weights_are_refused() -> None:
    with pytest.raises(ValueError, match="negatif"):
        pool((MARKET, MODEL), (1.0, -0.1))
    with pytest.raises(ValueError, match="ağırlık"):
        pool((MARKET, MODEL), (1.0,))


def _sample(
    count: int, truth: int, seed: int = 5
) -> tuple[list[list[tuple[float, ...]]], list[int]]:
    """İki bileşen; sonuçlar `truth` numaralı bileşenden çekilir."""
    rng = np.random.default_rng(seed)
    components: list[list[tuple[float, ...]]] = []
    outcomes: list[int] = []
    for _ in range(count):
        first = tuple(float(v) for v in rng.dirichlet((4.0, 3.0, 3.0)))
        second = tuple(float(v) for v in rng.dirichlet((3.0, 3.0, 4.0)))
        components.append([first, second])
        outcomes.append(int(rng.choice(3, p=(first, second)[truth])))
    return components, outcomes


def test_the_fit_puts_the_weight_on_the_component_that_generated_the_outcomes() -> None:
    components, outcomes = _sample(4000, truth=1)

    first, second = fit_weights(components, outcomes)

    assert second == pytest.approx(1.0, abs=0.15)
    assert first < 0.15


def test_the_fitted_pool_is_never_worse_than_the_first_component_in_sample() -> None:
    """G4/W1'in dayanağı: `(1, 0)` havuzun içinde; fit ondan kötü bir noktada duramaz."""
    components, outcomes = _sample(2000, truth=0, seed=9)
    weights = fit_weights(components, outcomes)

    def loss(ws: tuple[float, ...]) -> float:
        return -float(
            np.mean(
                [
                    math.log(pool(match, ws)[outcome])
                    for match, outcome in zip(components, outcomes, strict=True)
                ]
            )
        )

    assert loss(weights) <= loss((1.0, 0.0)) + 1e-9


def test_the_gradient_matches_finite_differences() -> None:
    from scipy.optimize import check_grad

    components, outcomes = _sample(500, truth=0)
    logs = pooling._logs([list(match) for match in components])
    target = np.asarray(outcomes, dtype=np.int64)

    error = check_grad(
        lambda w: pooling._objective(w, logs, target)[0],
        lambda w: pooling._objective(w, logs, target)[1],
        np.array([0.7, 0.4]),
    )

    assert error < 1e-6


def test_too_few_matches_are_refused() -> None:
    components, outcomes = _sample(MIN_FIT_MATCHES - 1, truth=0)

    with pytest.raises(TooFewMatches):
        fit_weights(components, outcomes)


def test_weights_stay_within_bounds() -> None:
    components, outcomes = _sample(1000, truth=1, seed=3)

    assert all(0.0 <= weight <= pooling.MAX_WEIGHT for weight in fit_weights(components, outcomes))
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_pool.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.model.pool'`

- [ ] **Step 3: Uygulamayı yaz**

`src/football_edge/model/pool.py`:

<!-- plan: yeni src/football_edge/model/pool.py -->
```python
"""Log-doğrusal görüş havuzu (Faz 3 tasarımı §6.3, R131).

`p ∝ exp(Σ wᵢ · log pᵢ)`, ağırlıklar ≥ 0. `w = (1, 0, …)` havuzun içindedir: doğru fit edilmiş bir
harman, fit edildiği veride ilk bileşenden (piyasa) kötü olamaz — kapının akıl sağlığı sınaması
(G4/W1) buna yaslanır. Ağırlık için ön bilgi girilmez; başlangıç noktası yalnız piyasadır.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.optimize import minimize

Floats = npt.NDArray[np.float64]

LOG_FLOOR = 1e-15
MAX_WEIGHT = 5.0
MIN_FIT_MATCHES = 300


class TooFewMatches(ValueError):
    """Ağırlık fiti için maç sayısı `MIN_FIT_MATCHES`in altında."""


def _logs(components: npt.ArrayLike) -> Floats:
    return np.log(np.maximum(np.asarray(components, dtype=np.float64), LOG_FLOOR))


def pool(components: Sequence[Sequence[float]], weights: Sequence[float]) -> tuple[float, ...]:
    """Bileşen olasılıkları (her biri aynı sonuç sırasıyla) → havuzlanmış, toplamı 1."""
    if len(components) != len(weights):
        raise ValueError(f"{len(components)} bileşen, {len(weights)} ağırlık")
    if any(weight < 0 for weight in weights):
        raise ValueError(f"negatif ağırlık: {tuple(weights)}")
    exponent = np.asarray(weights, dtype=np.float64) @ _logs(components)
    shifted = np.exp(exponent - exponent.max())
    return tuple(float(value) for value in shifted / shifted.sum())


def _objective(
    weights: Floats, logs: Floats, outcomes: npt.NDArray[np.int64]
) -> tuple[float, Floats]:
    """Ortalama log loss ve ağırlıklara göre gradyanı; `logs` şekli (maç, bileşen, sonuç)."""
    exponent = np.einsum("c,mcs->ms", weights, logs)
    exponent = exponent - exponent.max(axis=1, keepdims=True)
    probs = np.exp(exponent)
    probs = probs / probs.sum(axis=1, keepdims=True)
    rows = np.arange(len(outcomes))
    chosen = np.maximum(probs[rows, outcomes], LOG_FLOOR)
    expected = np.einsum("ms,mcs->mc", probs, logs)
    gradient = -(logs[rows, :, outcomes] - expected).mean(axis=0)
    return float(-np.log(chosen).mean()), gradient


def fit_weights(
    components: Sequence[Sequence[Sequence[float]]], outcomes: Sequence[int]
) -> tuple[float, ...]:
    """Maç başına bileşen olasılıkları ve gerçekleşen sonuç sırası → log loss'u en küçük ağırlık."""
    if len(components) != len(outcomes):
        raise ValueError(f"{len(components)} maç, {len(outcomes)} sonuç")
    if len(outcomes) < MIN_FIT_MATCHES:
        raise TooFewMatches(f"{len(outcomes)} maç < {MIN_FIT_MATCHES}")
    logs = _logs(components)
    count = logs.shape[1]
    start = np.zeros(count)
    start[0] = 1.0
    result: Any = minimize(
        _objective,
        start,
        args=(logs, np.asarray(outcomes, dtype=np.int64)),
        jac=True,
        method="L-BFGS-B",
        bounds=[(0.0, MAX_WEIGHT)] * count,
    )
    if not bool(result.success):
        raise ValueError(f"ağırlık fiti yakınsamadı: {result.message}")
    return tuple(float(value) for value in np.asarray(result.x, dtype=np.float64))
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_pool.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — 10 passed

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `pool`: `shifted / shifted.sum()` yerine `shifted` | `tests/test_pool.py::test_pooling_is_geometric_and_normalised` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add src/football_edge/model/pool.py \
  tests/test_pool.py
git commit -m "feat: Faz 3 T4 — log-doğrusal görüş havuzu ve ağırlık fiti

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
### Task 4: Ortak bağlam son adımı, `MatchKey`, yineleme reddi, Placebo tohumu (P2a; 14g, 14k, 14l)

**Kademe:** K1 · **Dalga:** 1 · **Worktree/dal:** `.worktrees/wt-context` · `feat/faz3-context`

Bağlam ve sonuç kaydı kaynaktan bağımsız bir ara kayıttan (`MatchRecord`) kurulur (tasarım §7.1): tarihsel ve canlı kurucunun ortak son adımı. Tipler döngüsüz olsun diye `records.py`ye taşınır, harness onları YENİDEN İHRAÇ eder (eski import'lar değişmez). `DecisionContext.key` bir özelliktir (P2). Bağlam yalnız `Avg` 1X2 kapanış öncesi fiyatını taşır (P1). `replay` yinelenen maçı reddeder (P3). Placebo tohumu maç kimliğinden (P4, 14l). Oracle kanaryasına 12:15 UTC'lik iki yuva eklenir (14k: eşik 10 sa → 4 sa).

**Files:**
- Create: `src/football_edge/backtest/records.py`
- Create: `src/football_edge/backtest/context.py`
- Modify: `src/football_edge/backtest/harness.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `src/football_edge/backtest/strategies.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `tests/test_harness.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `tests/test_strategies.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `tests/test_selftest.py` (yama aşağıda, `git apply` ile uygulanır)

**Interfaces:**
- Consumes: Faz 2'nin `HistMatch`, `OddsKey`, `PRE_CLOSING`, `H2H`; `backtest/events.py`, `timeline.py`.
- Produces: `MatchKey`, `MatchRecord`, `record_of`, `context_of`, `result_of`, `check_unique`, `pre_only`, `DuplicateMatch`, `CONTEXT_BOOK`, `CONTEXT_MARKETS`, `DecisionContext.key`, `placebo_pick`.

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_harness.py` yaması:

<!-- plan: yama tests/test_harness.py -->
```diff
diff --git a/tests/test_harness.py b/tests/test_harness.py
index 959306e..293ec3d 100644
--- a/tests/test_harness.py
+++ b/tests/test_harness.py
@@ -9,17 +9,19 @@ from types import MappingProxyType
 import pytest
 
 from football_edge.backtest import harness
+from football_edge.backtest.context import DuplicateMatch
 from football_edge.backtest.events import DECISION, RESULT, Event
 from football_edge.backtest.harness import (
     DecisionContext,
     LeakageError,
+    MatchKey,
     Outcome,
     Prediction,
     ResultRecord,
     replay,
 )
 from football_edge.backtest.timeline import result_known_at
-from football_edge.history.types import CLOSING, PRE_CLOSING, RESULTS, TOTALS_25, HistMatch
+from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, RESULTS, TOTALS_25, HistMatch
 from tests.backtest_builders import hist_match, quote
 
 FRIDAY_NOON_BST = datetime(2024, 8, 9, 11, tzinfo=UTC)
@@ -186,9 +188,13 @@ def test_a_decision_context_carries_only_pre_closing_prices() -> None:
     replay((match,), recorder)
 
     context = recorder.contexts[0]
+    # Faz 3 (R98 eşitliği): yalnız canlı defterin de üretebildiği `Avg` 1X2 kapanış öncesi fiyatı.
     assert dict(context.pre_prices) == {
-        key: price for key, price in FULL_ODDS.items() if key.phase == PRE_CLOSING
+        key: price
+        for key, price in FULL_ODDS.items()
+        if key.phase == PRE_CLOSING and key.book == "Avg" and key.market == H2H
     }
+    assert len(context.pre_prices) == 3
     assert isinstance(context.pre_prices, MappingProxyType)
     assert (context.league, context.season, context.date) == ("E0", "2425", date(2024, 8, 10))
     assert (context.home, context.away, context.decision_at) == ("Alfa", "Beta", FRIDAY_NOON_BST)
@@ -199,7 +205,15 @@ def test_outcomes_hold_only_closing_prices_and_only_for_predicted_matches() -> N
     kickoff = datetime(2024, 8, 10, 14, tzinfo=UTC)
     matches = (
         hist_match(day=date(2024, 8, 10), kickoff=kickoff, goals=(2, 1), odds=FULL_ODDS),
-        hist_match(day=date(2024, 8, 10), kickoff=kickoff, goals=(0, 0), odds=FULL_ODDS, line=2),
+        hist_match(
+            day=date(2024, 8, 10),
+            kickoff=kickoff,
+            home="Gama",
+            away="Delta",
+            goals=(0, 0),
+            odds=FULL_ODDS,
+            line=2,
+        ),
     )
 
     result = replay(matches, _recorder(predict_for=frozenset({0})))
@@ -401,6 +415,10 @@ _SLOTS: tuple[tuple[int, time | None], ...] = (
     (2, time(0, 30)),  # pazartesi 00:30
     (3, time(18, 45)),  # salı akşamı
     (4, time(23, 30)),  # çarşamba gece
+    # 14k: karar anına (11:00 UTC, BST) 1 sa 15 dk kala başlayan cuma ve salı maçları; sonucu
+    # 4 sa erken sızdıran bir harness'ı yalnız bu iki yuva yakalar.
+    (-1, time(12, 15)),  # cuma öğlen
+    (3, time(12, 15)),  # salı öğlen
 )
 _CANARY_LEAGUES = ("E0", "SP1", "BRA")
 
@@ -451,3 +469,40 @@ def test_an_oracle_that_uses_results_gets_no_prediction_from_the_honest_harness(
     # görmediği için susuyor.
     assert (result.no_decision, result.no_prediction) == (0, len(schedule))
     assert sum(prediction.probs[0] > 0 for prediction in earlier.predictions) > len(schedule) // 2
+
+
+@pytest.mark.leakage
+def test_replay_refuses_the_same_match_twice() -> None:
+    """14g/14r: aynı (lig, tarih, ev, deplasman) iki kez → iki karar ve çift durum güncellemesi."""
+    day = date(2024, 8, 10)
+    kickoff = datetime(2024, 8, 10, 14, tzinfo=UTC)
+    twice = (hist_match(day=day, kickoff=kickoff), hist_match(day=day, kickoff=kickoff, line=2))
+
+    with pytest.raises(DuplicateMatch, match="yinelenen maç"):
+        replay(twice, _recorder())
+
+
+def test_the_context_key_is_the_match_identity() -> None:
+    match = hist_match(day=date(2024, 8, 10), kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC))
+
+    context = harness._context(4, match, FRIDAY_NOON_BST)
+
+    assert context.key == MatchKey("E0", date(2024, 8, 10), "Alfa", "Beta")
+
+
+@pytest.mark.leakage
+def test_the_context_carries_only_prices_the_live_ledger_can_rebuild() -> None:
+    """R98 eşitliği (Faz 3): canlı defter yalnız kitap ortalaması 1X2 kurar; başka kitap ya da
+    market bağlama girerse canlı bağlam onu taşıyamaz."""
+    odds = {
+        **quote("Avg", PRE_CLOSING, (2.6, 3.3, 2.8)),
+        **quote("Max", PRE_CLOSING, (2.8, 3.6, 3.1)),
+        **quote("Avg", PRE_CLOSING, (1.9, 1.95), market=TOTALS_25),
+    }
+    match = hist_match(
+        day=date(2024, 8, 10), kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC), odds=odds
+    )
+
+    context = harness._context(0, match, FRIDAY_NOON_BST)
+
+    assert dict(context.pre_prices) == quote("Avg", PRE_CLOSING, (2.6, 3.3, 2.8))
```

`tests/test_strategies.py` yaması:

<!-- plan: yama tests/test_strategies.py -->
```diff
diff --git a/tests/test_strategies.py b/tests/test_strategies.py
index 0104e90..3fd72b9 100644
--- a/tests/test_strategies.py
+++ b/tests/test_strategies.py
@@ -2,6 +2,7 @@
 
 from __future__ import annotations
 
+import hashlib
 import random
 from collections.abc import Mapping, Sequence
 from dataclasses import dataclass
@@ -84,7 +85,8 @@ def _elo_probs(
 
 
 def _pick(strategy: Placebo, index: int) -> str:
-    prediction = strategy.predict(_context(AVG_PRE, index=index))
+    """`index`. maç: adı sıradan gelen ayrı bir maç (tohum kimlikten, sıradan değil — 14l)."""
+    prediction = strategy.predict(_context(AVG_PRE, index=index, home=f"Ev {index}"))
     assert prediction is not None and prediction.bet is not None
     return prediction.bet.outcome
 
@@ -308,12 +310,18 @@ def test_elo_ratings_at_a_decision_come_only_from_results_known_before_it() -> N
     assert probs[2] == pytest.approx(_elo_probs(beta, 1500.0, CONFIG, 0.26))
 
 
+def _sha_pick(seed: int, league: str, day: date, home: str, away: str) -> str:
+    """Sözleşmedeki tohumun testteki bağımsız yazımı (14l)."""
+    digest = hashlib.sha256(f"{seed}|{league}|{day.isoformat()}|{home}|{away}".encode()).digest()
+    return random.Random(int.from_bytes(digest[:8], "big")).choice(RESULTS)
+
+
 def test_placebo_bets_its_seeded_pick_at_the_books_pre_closing_price() -> None:
     strategy = Placebo(devig=_normalise, seed=7)
 
     prediction = strategy.predict(_context(AVG_PRE, index=3))
 
-    pick = random.Random(7 * 1_000_003 + 3).choice(RESULTS)
+    pick = _sha_pick(7, "E0", date(2024, 8, 10), "Alfa", "Beta")
     assert prediction is not None and prediction.bet is not None
     assert prediction.bet.outcome == pick
     assert prediction.bet.price == dict(zip(RESULTS, (2.6, 3.3, 2.8), strict=True))[pick]
@@ -323,17 +331,28 @@ def test_placebo_bets_its_seeded_pick_at_the_books_pre_closing_price() -> None:
     assert strategy.predict(_context(AVG_PRE, index=3)) == prediction
 
 
-def test_placebo_picks_follow_the_per_match_seed_over_a_grid() -> None:
-    """Tek örnek yanlış bir tohum biçimini (ör. `seed + index`) şans eseri geçirebilir."""
+def test_placebo_picks_follow_the_match_identity_seed_over_a_grid() -> None:
+    """Tek örnek yanlış bir tohum biçimini (ör. ev adı atlanmış) şans eseri geçirebilir."""
     grid = [(seed, index) for seed in (1, 7, 20260922) for index in range(6)]
 
     picks = [_pick(Placebo(devig=_normalise, seed=seed), index) for seed, index in grid]
 
     assert picks == [
-        random.Random(seed * 1_000_003 + index).choice(RESULTS) for seed, index in grid
+        _sha_pick(seed, "E0", date(2024, 8, 10), f"Ev {index}", "Beta") for seed, index in grid
     ]
 
 
+def test_placebo_pick_ignores_the_replay_position() -> None:
+    """14l: aynı maç, oynatmadaki sırası değişince aynı sonucu seçer."""
+    strategy = Placebo(devig=_normalise)
+
+    picks = {strategy.predict(_context(AVG_PRE, index=index)) for index in range(20)}
+
+    assert (
+        len({prediction.bet.outcome for prediction in picks if prediction and prediction.bet}) == 1
+    )
+
+
 def test_placebo_picks_vary_across_matches() -> None:
     strategy = Placebo(devig=_normalise)
 
```

`tests/test_selftest.py` yaması:

<!-- plan: yama tests/test_selftest.py -->
```diff
diff --git a/tests/test_selftest.py b/tests/test_selftest.py
index cad9fd8..d386f7d 100644
--- a/tests/test_selftest.py
+++ b/tests/test_selftest.py
@@ -6,7 +6,6 @@ Placebo'nun seçtiği tarafın fiyatı kapanışa doğru kısalırsa (gelecek fi
 
 from __future__ import annotations
 
-import random
 import re
 from collections.abc import Callable, Mapping, Sequence
 from datetime import UTC, date, datetime, time, timedelta
@@ -15,8 +14,9 @@ from functools import partial
 import pytest
 
 from football_edge.backtest import selftest
+from football_edge.backtest.records import MatchKey
 from football_edge.backtest.selftest import Check, run_selftest
-from football_edge.backtest.strategies import Placebo
+from football_edge.backtest.strategies import Placebo, placebo_pick
 from football_edge.backtest.timeline import LONDON
 from football_edge.history.holdout import DEV, HoldoutKey
 from football_edge.history.types import CLOSING, PRE_CLOSING, RESULTS, HistMatch, OddsKey
@@ -82,8 +82,8 @@ def _match(
         kickoff=kickoff,
         league=league,
         season=season,
-        home=f"{league} ev",
-        away=f"{league} konuk",
+        home=f"{league} ev {line}",
+        away=f"{league} konuk {line}",
         goals=SCORES[result],
         odds=odds,
         line=line,
@@ -331,8 +331,14 @@ def test_k3_measures_main_leagues_only_inside_the_main_window() -> None:
 
 
 def _placebo_pick(index: int) -> str:
-    """Placebo'nun havuzdaki `index`. maç için seçeceği sonuç (Task 4: maç başına tohum)."""
-    return random.Random(PLACEBO_SEED * 1_000_003 + index).choice(RESULTS)
+    """Placebo'nun havuzdaki `index`. maç için seçeceği sonuç (14l: tohum maç kimliğinden).
+
+    `_k4_history`in maçları: cumartesiler 2023-08-05'ten, `line = index + 1`, adlar `_match`ten.
+    """
+    kickoff = _saturdays(index + 1, date(2023, 8, 5))[index]
+    day = kickoff.astimezone(LONDON).date()
+    key = MatchKey("E0", day, f"E0 ev {index + 1}", f"E0 konuk {index + 1}")
+    return placebo_pick(PLACEBO_SEED, key)
 
 
 def _close_for(pick: str, target: float) -> Prices:
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_harness.py tests/test_strategies.py tests/test_selftest.py -q`
Expected: FAIL — `ImportError: cannot import name 'DuplicateMatch'` (test_harness), `cannot import name 'placebo_pick'` (test_strategies, test_selftest) — toplama hatası; 14k'nın iki yuvası tek başına yeşil kalabilir (dürüst harness'ı sınar, kırmızısı mutasyonla).

- [ ] **Step 3: Uygulamayı yaz**

`src/football_edge/backtest/records.py`:

<!-- plan: yeni src/football_edge/backtest/records.py -->
```python
"""Stratejinin gördüğü kayıtlar (Faz 2 tasarımı §7.2, Faz 3 tasarımı §7.1).

Tipler burada, kurucular `backtest/context.py`de, oynatma `backtest/harness.py`de: harness ve
kurucu bu modülü paylaşır, birbirini import etmez (döngü yok). `harness` bu adları yeniden ihraç
eder; eski `from football_edge.backtest.harness import DecisionContext` çağrıları değişmez.
"""

from __future__ import annotations

import datetime as dt  # `date` bir alan adı: sınıf gövdesinde tip adını gölgelerdi
from collections.abc import Mapping
from dataclasses import dataclass

from football_edge.history.types import OddsKey


@dataclass(frozen=True, order=True)
class MatchKey:
    """Maçın kaynaktan bağımsız kimliği: lig kodu, kaynağın (Londra) tarihi, kanonik adlar.

    `match_index` yeniden oynatmaya özgü bir SIRADIR; canlıda karşılığı yoktur (tasarım §7.5).
    """

    league: str
    date: dt.date
    home: str
    away: str


@dataclass(frozen=True)
class ResultRecord:
    league: str
    date: dt.date
    home: str
    away: str
    home_goals: int
    away_goals: int
    known_at: dt.datetime


@dataclass(frozen=True)
class DecisionContext:
    """Stratejinin gördüğü TEK kayıt: kapanış, sonuç ve durum görüntüsü alanı yoktur (R98).

    Durum stratejinin içindedir (`observe` yeni değer döner); zamanı harness yönetir.
    """

    match_index: int
    league: str
    season: str
    date: dt.date
    home: str
    away: str
    decision_at: dt.datetime
    pre_prices: Mapping[OddsKey, float]  # yalnız PRE_CLOSING anahtarları

    @property
    def key(self) -> MatchKey:
        return MatchKey(league=self.league, date=self.date, home=self.home, away=self.away)
```

`src/football_edge/backtest/context.py`:

<!-- plan: yeni src/football_edge/backtest/context.py -->
```python
"""Bağlamın tek son adımı (Faz 3 tasarımı §7.1, R98).

Tarihsel ve canlı kurucu kaynaklarını önce aynı ara kayda (`MatchRecord`) çevirir; bağlam ve
sonuç kaydı YALNIZ buradan kurulur. Eşitlik testi böylece "iki kod aynı şeyi mi yazdı"yı değil
"iki kaynak aynı kaydı mı üretti"yi sınar. Karar ve sonuç anları çağıranın (`timeline`)
kuralından gelir; burada hesaplanmaz.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from football_edge.backtest.records import DecisionContext, MatchKey, ResultRecord
from football_edge.history.types import H2H, PRE_CLOSING, HistMatch, OddsKey


class DuplicateMatch(ValueError):
    """Aynı `MatchKey` iki kez geçti: iki karar ve çift durum güncellemesi olurdu (14g, 14r)."""


@dataclass(frozen=True)
class MatchRecord:
    key: MatchKey
    season: str
    kickoff: dt.datetime | None
    pre_prices: Mapping[OddsKey, float]  # yalnız PRE_CLOSING anahtarları
    goals: tuple[int, int] | None  # sonuç henüz yoksa None


# Bağlam yalnız İKİ kaynağın da üretebildiği fiyatları taşır: canlı defter 1X2'yi kitap kitap
# toplar (snapshot `markets=h2h`); football-data karşılığı kitap ortalaması `Avg`'dir. Başka kitap
# ya da market bağlama girerse canlı bağlam onu taşıyamaz ve eşitlik (R98) sözde kalır.
CONTEXT_BOOK = "Avg"
CONTEXT_MARKETS = frozenset({H2H})


def pre_only(prices: Mapping[OddsKey, float]) -> Mapping[OddsKey, float]:
    """Kapanış öncesi `Avg` 1X2 anahtarları, değiştirilemez görünümde."""
    return MappingProxyType(
        {
            key: price
            for key, price in prices.items()
            if key.phase == PRE_CLOSING
            and key.book == CONTEXT_BOOK
            and key.market in CONTEXT_MARKETS
        }
    )


def record_of(match: HistMatch) -> MatchRecord:
    return MatchRecord(
        key=MatchKey(league=match.league, date=match.date, home=match.home, away=match.away),
        season=match.season,
        kickoff=match.kickoff,
        pre_prices=pre_only(match.odds),
        goals=(match.home_goals, match.away_goals),
    )


def context_of(index: int, record: MatchRecord, decided: dt.datetime) -> DecisionContext:
    return DecisionContext(
        match_index=index,
        league=record.key.league,
        season=record.season,
        date=record.key.date,
        home=record.key.home,
        away=record.key.away,
        decision_at=decided,
        pre_prices=pre_only(record.pre_prices),
    )


def result_of(record: MatchRecord, known_at: dt.datetime) -> ResultRecord:
    if record.goals is None:
        raise ValueError(f"{record.key}: sonucu olmayan maçtan sonuç kaydı kurulamaz")
    home_goals, away_goals = record.goals
    return ResultRecord(
        league=record.key.league,
        date=record.key.date,
        home=record.key.home,
        away=record.key.away,
        home_goals=home_goals,
        away_goals=away_goals,
        known_at=known_at,
    )


def check_unique(keys: Iterable[MatchKey]) -> None:
    seen: set[MatchKey] = set()
    for key in keys:
        if key in seen:
            raise DuplicateMatch(f"yinelenen maç: {key}")
        seen.add(key)
```

`src/football_edge/backtest/harness.py` yaması:

<!-- plan: yama src/football_edge/backtest/harness.py -->
```diff
diff --git a/src/football_edge/backtest/harness.py b/src/football_edge/backtest/harness.py
index 8435959..f443984 100644
--- a/src/football_edge/backtest/harness.py
+++ b/src/football_edge/backtest/harness.py
@@ -13,42 +13,18 @@ from dataclasses import dataclass
 from types import MappingProxyType
 from typing import Protocol
 
+from football_edge.backtest.context import check_unique, context_of, record_of, result_of
 from football_edge.backtest.events import DECISION, RESULT, Event, build_events
-from football_edge.history.types import CLOSING, PRE_CLOSING, HistMatch, OddsKey
+from football_edge.backtest.records import DecisionContext as DecisionContext
+from football_edge.backtest.records import MatchKey as MatchKey
+from football_edge.backtest.records import ResultRecord as ResultRecord
+from football_edge.history.types import CLOSING, HistMatch, OddsKey
 
 
 class LeakageError(RuntimeError):
     """Bir karar, anı karar anına eşit ya da sonra olan bir sonucu görmüş olurdu."""
 
 
-@dataclass(frozen=True)
-class ResultRecord:
-    league: str
-    date: dt.date
-    home: str
-    away: str
-    home_goals: int
-    away_goals: int
-    known_at: dt.datetime
-
-
-@dataclass(frozen=True)
-class DecisionContext:
-    """Stratejinin gördüğü TEK kayıt: kapanış, sonuç ve durum görüntüsü alanı yoktur (R98).
-
-    Durum stratejinin içindedir (`observe` yeni değer döner); zamanı harness yönetir.
-    """
-
-    match_index: int
-    league: str
-    season: str
-    date: dt.date
-    home: str
-    away: str
-    decision_at: dt.datetime
-    pre_prices: Mapping[OddsKey, float]  # yalnız PRE_CLOSING anahtarları
-
-
 @dataclass(frozen=True)
 class Outcome:
     match_index: int
@@ -96,28 +72,11 @@ def _phase_prices(match: HistMatch, phase: str) -> Mapping[OddsKey, float]:
 
 
 def _result_record(match: HistMatch, known_at: dt.datetime) -> ResultRecord:
-    return ResultRecord(
-        league=match.league,
-        date=match.date,
-        home=match.home,
-        away=match.away,
-        home_goals=match.home_goals,
-        away_goals=match.away_goals,
-        known_at=known_at,
-    )
+    return result_of(record_of(match), known_at)
 
 
 def _context(index: int, match: HistMatch, decided: dt.datetime) -> DecisionContext:
-    return DecisionContext(
-        match_index=index,
-        league=match.league,
-        season=match.season,
-        date=match.date,
-        home=match.home,
-        away=match.away,
-        decision_at=decided,
-        pre_prices=_phase_prices(match, PRE_CLOSING),
-    )
+    return context_of(index, record_of(match), decided)
 
 
 def _outcome(index: int, match: HistMatch) -> Outcome:
@@ -163,7 +122,12 @@ def _walk(
 
 
 def replay(matches: Sequence[HistMatch], strategy: Strategy) -> ReplayResult:
-    """Maçları olay akışıyla oynatır; sonuç kayıtları döngü BİTTİKTEN sonra kurulur."""
+    """Maçları olay akışıyla oynatır; sonuç kayıtları döngü BİTTİKTEN sonra kurulur.
+
+    Yinelenen `MatchKey` `DuplicateMatch` verir: aynı maçın iki kararı ve çift durum güncellemesi
+    sessiz geçmez (Faz 3 tasarımı §7.5).
+    """
+    check_unique(record_of(match).key for match in matches)
     events = build_events(matches)
     predictions, no_prediction = _walk(matches, events, strategy)
     decisions = sum(1 for event in events if event.kind == DECISION)
```

`src/football_edge/backtest/strategies.py` yaması:

<!-- plan: yama src/football_edge/backtest/strategies.py -->
```diff
diff --git a/src/football_edge/backtest/strategies.py b/src/football_edge/backtest/strategies.py
index 752882d..8219db4 100644
--- a/src/football_edge/backtest/strategies.py
+++ b/src/football_edge/backtest/strategies.py
@@ -6,12 +6,14 @@ gerçek bağlantı bütünleşik harness'ta (`functools.partial(devig, method=..
 
 from __future__ import annotations
 
+import hashlib
 import random
 from collections.abc import Callable, Mapping, Sequence
 from dataclasses import dataclass, field, replace
 from types import MappingProxyType
 
 from football_edge.backtest.harness import Bet, DecisionContext, Prediction, ResultRecord
+from football_edge.backtest.records import MatchKey
 from football_edge.elo import EloConfig, expected_home, updated
 from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, OddsKey
 
@@ -19,8 +21,6 @@ Devig = Callable[[Sequence[float]], tuple[float, ...]]
 
 _FLOOR = 0.01
 _CEILING = 0.98
-# Maç başına tohum: bir maçın seçimi, başka maçların karar alıp almamasından bağımsızdır.
-_SEED_STRIDE = 1_000_003
 
 
 def _h2h_pre(context: DecisionContext, book: str) -> tuple[float, float, float] | None:
@@ -43,6 +43,17 @@ def _fair(devig: Devig, prices: tuple[float, float, float]) -> tuple[float, floa
     return probs[0], probs[1], probs[2]
 
 
+def placebo_pick(seed: int, key: MatchKey) -> str:
+    """Maç KİMLİĞİNE bağlı tohumlu seçim (DEFERRED 14l).
+
+    Giriş sırasına bağlı tohumda bir lig eklenince seçimlerin çoğu değişirdi; kimlik canlıda da
+    aynıdır (Faz 3 tasarımı §7.5). `hash()` süreçten sürece değiştiği için sha256.
+    """
+    text = f"{seed}|{key.league}|{key.date.isoformat()}|{key.home}|{key.away}"
+    digest = hashlib.sha256(text.encode("utf-8")).digest()
+    return random.Random(int.from_bytes(digest[:8], "big")).choice(RESULTS)
+
+
 def _clamp(value: float) -> float:
     return min(max(value, _FLOOR), _CEILING)
 
@@ -133,7 +144,7 @@ class EloPointInTime:
 
 @dataclass(frozen=True)
 class Placebo:
-    """K4 negatif kontrolü: maç başına tohumlu rastgele sonuç, `book`un kapanış öncesi fiyatı."""
+    """K4 negatif kontrolü: maç kimliğiyle tohumlu sonuç, `book`un kapanış öncesi fiyatı."""
 
     devig: Devig
     seed: int = 20260922
@@ -151,6 +162,6 @@ class Placebo:
         probs = None if prices is None else _fair(self.devig, prices)
         if prices is None or probs is None:
             return None
-        pick = random.Random(self.seed * _SEED_STRIDE + context.match_index).choice(RESULTS)
+        pick = placebo_pick(self.seed, context.key)
         bet = Bet(outcome=pick, price=prices[RESULTS.index(pick)], book=self.book)
         return Prediction(match_index=context.match_index, strategy=self.name, probs=probs, bet=bet)
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_harness.py tests/test_strategies.py tests/test_selftest.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — test_harness 21 · test_strategies 26 · test_selftest 33 passed; tam paket 1.557 passed

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `pre_only`: `and key.book == CONTEXT_BOOK` silinir | `tests/test_harness.py::test_the_context_carries_only_prices_the_live_ledger_can_rebuild` |
| 2 | `replay`: `check_unique(...)` satırı silinir | `tests/test_harness.py::test_replay_refuses_the_same_match_twice` |
| 3 | `placebo_pick`: tohum metninden `|{key.home}` düşer | `tests/test_strategies.py::test_placebo_picks_follow_the_match_identity_seed_over_a_grid` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add src/football_edge/backtest/records.py \
  src/football_edge/backtest/context.py \
  src/football_edge/backtest/harness.py \
  src/football_edge/backtest/strategies.py \
  tests/test_harness.py \
  tests/test_strategies.py \
  tests/test_selftest.py
git commit -m "feat: Faz 3 P2a — ortak bağlam son adımı, MatchKey, yineleme reddi, Placebo tohumu kimlikten

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
### Task 5: Dalga 1 birleştirmesi, sızıntı alt sınırı, süre ölçümü (controller)

**Kademe:** — (controller) · **Dalga:** 1 sonu · **Önkoşul:** Task 1–4'ün inceleme döngüleri kapandı (defterde `complete`).

- [ ] **Step 1: Dört dalı sırayla birleştir** — dosya kümeleri ayrık, çakışma beklenmez.

```bash
git checkout main
for branch in feat/faz3-dc feat/faz3-elo feat/faz3-pool feat/faz3-context; do
  git merge --no-ff "$branch" -m "merge: $branch (Faz 3 dalga 1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || break
  TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-merge.log 2>&1 || { grep -E '^(FAIL)' /tmp/verify-merge.log; break; }
done
```
Expected: her birleştirmeden sonra `KAPI YEŞİL`. Kırmızı adım o görevin implementer'ına bulgu olarak döner.

- [ ] **Step 2: `leakage` testlerini say ve alt sınırı yükselt**

Run: `uv run pytest tests/ -q -m leakage --collect-only 2>&1 | tail -1`
Expected: `269/… tests collected` (plan yazımında ölçülen: 265 + Task 1 · 2 · 4'ün 1 + 1 + 2'si). `verify.sh`te
`EXPECTED_MIN_LEAKAGE=265` → ölçülen sayı (269 değilse sayı ölçülene göre yazılır ve fark defterde açıklanır).
Mutasyon: bir `@pytest.mark.leakage` silinir → `FAIL: sızıntı` ("alt sınırın altında"); geri alınır.

- [ ] **Step 3: Süre ve bellek ölçümü (gerçek veri, yerel)** — walk-forward'un ve seçimin koşup koşamayacağını
KOD YAZILMADAN önce bilmek için. Ölçüm belgesine komutuyla yazılır:

```bash
uv run --env-file .env python - <<'PY'
import resource, time
from datetime import date
from pathlib import Path
from football_edge.backtest.__main__ import rating_groups
from football_edge.backtest.harness import replay
from football_edge.db import connect
from football_edge.history.catalog import load_catalog
from football_edge.history.holdout import DEV, select_periods
from football_edge.history.lock import load_lock
from football_edge.history.sync import load_matches
from football_edge.model.dixon_coles import DCConfig, GoalRecord, fit
from football_edge.model.elo_model import EloModel
catalog = load_catalog(Path("config/history_leagues.yaml"))
groups = rating_groups(catalog)
with connect() as conn:
    leagues = load_matches(conn, catalog, lock=load_lock(Path("config/history_lock.yaml")))
dev = {code: select_periods(ms, periods=frozenset({DEV})) for code, ms in leagues.items()}
england = sorted((m for code, ms in dev.items() if groups[code] == "England" for m in ms),
                 key=lambda m: (m.date, m.league, m.home))
start = time.perf_counter(); replay(england, EloModel(groups=groups)); elo = time.perf_counter() - start
records = [GoalRecord(m.home, m.away, m.home_goals, m.away_goals, m.date) for m in england]
days = [date(2016, 1, 8), date(2019, 11, 1), date(2022, 3, 4), date(2024, 10, 4)]
start = time.perf_counter()
for day in days:
    fit(records, at=day, config=DCConfig())
per_fit = (time.perf_counter() - start) / len(days)
print(f"England grubu: {len(england)} maç · Elo replay {elo:.1f} sn · DC fit {per_fit:.2f} sn/fit")
print("tepe RSS MB:", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20)
PY
```

Karar kuralı (ölçümden SONRA, defterde Ruling olarak): İngiltere en büyük gruptur. Walk-forward'un DC maliyeti ≈
Σ_grup (karar günü sayısı × fit süresi); karar günü S + E boyunca haftada ~2. Kestirilen toplam (S + E, bütün
gruplar, H2H + Ü/A aynı memo) **45 dk'nın altındaysa** `cadence_days = 1`; üstündeyse `select --cadence-days 7`
(P18) ve yeniden kestirim; hâlâ üstündeyse Task 6 başlamaz, eskalasyon (Decompose: lig başına DC, R136'un
yedeği). Kapı gevşetilmez; ızgara (P10) küçültülmez — küçültmek seçimi değiştirir ve ayrı bir karardır.

- [ ] **Step 3b: Belirlenimcilik (tasarım §5.3, inceleme m8)** — Task 9'da `walkforward` yerelde İKİ kez koşulur;
iki raporun `satır özeti sha256`sı eşit olmalı (değilse sıraya bağlı bir sonuç var: bulgu). Runner ile yerel
arasındaki kayan nokta farkı bu fazda ölçülmez (ölçmedikleri 22).

- [ ] **Step 4: Commit, taze klon kapısı, push**

```bash
git add verify.sh docs/superpowers/specs/2026-09-23-faz3-olcumler.md
git commit -m "ci: Faz 3 dalga 1 — sızıntı alt sınırı ölçüldü; Dixon-Coles ve Elo süre ölçümü

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Taze klon (`TMPDIR` klonun dışında) → `./verify.sh` → 10 PASS + `SKIP: zincir`. `git fetch origin && git merge
--no-ff origin/main`, `git push origin main`, CI yeşil. Dalga 2 (Task 6) bu commit'ten açılır.

---

### Task 6: Dixon-Coles stratejisi, walk-forward satırları ve değerlendirmesi (P1)

**Kademe:** K1 · **Dalga:** 2 · **Worktree/dal:** `.worktrees/wt-walkforward` · `feat/faz3-walkforward`

Tasarım §5 ve §6.4–6.6. `DixonColesStrategy` harness'a takılır: gözlenen goller grup başına 256'lık parçalarda (O(n²) kopya yok), fit (grup, fit günü) başına bir kez memo'da (P5). `walkforward.py` bölgeleri, grup başına oynatmayı ve `Row` tablosunu kurar; piyasa bileşeni maçın kendi kapanış öncesi fiyatıdır (S'de `BbAv`, E'de `Avg`). `wf_eval.py` ağırlık katlarını (E sezonu `s` yalnız `s`'den öncekini görür; ilk kat S'yi; lig < 1000 satırsa havuzlanmış — P8), `frozen_weights`i (holdout/sonrası için, yalnız DEV'in E'si), sabit bahis kuralını ve özeti kurar. Karşılaştırmalar ORTAK satırlarda. G2 (gelecek-fit kanaryası), G3 (katlar arası sızıntı) ve G7 (belirlenimcilik) bu görevde.

**Files:**
- Create: `src/football_edge/model/strategies.py`
- Create: `src/football_edge/backtest/walkforward.py`
- Create: `src/football_edge/backtest/wf_eval.py`
- Create: `tests/model_builders.py`
- Create: `tests/test_model_strategies.py`
- Create: `tests/test_walkforward.py`

**Interfaces:**
- Consumes: Task 1 (`fit`, `score_matrix`, `outcome_probs`, `totals_probs`), Task 2 (`EloModel`), Task 3 (`pool`, `fit_weights`), Task 4 (`record_of`, `MatchKey`), Faz 2 (`replay`, `decision_at`, `Window`, `match_probs`, `outcome_index`, metrikler).
- Produces: `DixonColesStrategy`, `fit_day`, `CHUNK`; walkforward sabitleri, `Row`, `zone_of`, `group_matches`, `group_kind`, `model_probs`, `group_rows(..., zoning=)`; `Score`, `Summary`, `complete`, `fold_weights`, `frozen_weights`, `blended`, `bet_clv`, `score`, `summarise(..., zone=, given=)`, `LEAGUE_MIN_MATCHES`; test yardımcısı `tests/model_builders.py`.

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/model_builders.py`:

<!-- plan: yeni tests/model_builders.py -->
```python
"""Model ve walk-forward testlerinin SENTETİK sezonları.

Takım adları ve fiyatlar uydurma (spec §3.2/4); goller bilinen güçlerle tohumlu Poisson'dan. Ana
lig sezonlarında 2019/20'den önce kapanış öncesi kitap `BbAv` (kapanış yok), sonra `Avg` + `AvgC`
— football-data'nın sütun tarihçesi gibi (Faz 2 ölçüm §2.4).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

import numpy as np

from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch, OddsKey
from tests.backtest_builders import hist_match, quote

TEAMS = ("Alfa", "Beta", "Gama", "Delta", "Epsilon", "Zeta", "Eta", "Teta")
STRENGTH = (0.5, 0.35, 0.2, 0.05, -0.05, -0.2, -0.35, -0.5)
HOME = 0.25
MARGIN = 1.05


def _probs(home: int, away: int) -> tuple[tuple[float, float, float], tuple[float, float]]:
    lam = math.exp(STRENGTH[home] - STRENGTH[away] + HOME)
    mu = math.exp(STRENGTH[away] - STRENGTH[home])
    pmf_h = [math.exp(-lam) * lam**k / math.factorial(k) for k in range(11)]
    pmf_a = [math.exp(-mu) * mu**k / math.factorial(k) for k in range(11)]
    grid = np.outer(pmf_h, pmf_a)
    grid = grid / grid.sum()
    h, d, a = float(np.tril(grid, -1).sum()), float(np.trace(grid)), float(np.triu(grid, 1).sum())
    goals = np.add.outer(np.arange(11), np.arange(11))
    over = float(grid[goals > 2.5].sum())
    return (h, d, a), (over, 1.0 - over)


def _prices(probs: Sequence[float]) -> tuple[float, ...]:
    return tuple(round(1.0 / (p * MARGIN), 2) for p in probs)


def season(
    code: str,
    first: date,
    *,
    league: str = "E0",
    seed: int = 1,
    rounds: int = 14,
    teams: Sequence[str] = TEAMS,
) -> tuple[HistMatch, ...]:
    """Cumartesi 14:00 UTC turları; `code >= "1920"` ise Avg/AvgC, değilse yalnız BbAv."""
    rng = np.random.default_rng(seed)
    count = len(teams)
    found: list[HistMatch] = []
    line = 0
    for week in range(rounds):
        day = first + timedelta(weeks=week)
        order = [(index + week) % count for index in range(count)]
        for pair in range(count // 2):
            home, away = order[pair], order[count - 1 - pair]
            if week % 2:
                home, away = away, home
            h2h, totals = _probs(home, away)
            goals = (
                int(rng.poisson(math.exp(STRENGTH[home] - STRENGTH[away] + HOME))),
                int(rng.poisson(math.exp(STRENGTH[away] - STRENGTH[home]))),
            )
            odds: dict[OddsKey, float] = {}
            if code >= "1920":
                odds |= quote("Avg", PRE_CLOSING, _prices(h2h))
                odds |= quote("Avg", CLOSING, _prices(h2h))
                odds |= quote("Avg", PRE_CLOSING, _prices(totals), market=TOTALS_25)
                odds |= quote("Avg", CLOSING, _prices(totals), market=TOTALS_25)
            else:
                odds |= quote("BbAv", PRE_CLOSING, _prices(h2h))
            line += 1
            found.append(
                hist_match(
                    day=day,
                    kickoff=datetime.combine(day, time(14), tzinfo=UTC),
                    league=league,
                    season=code,
                    home=teams[home],
                    away=teams[away],
                    goals=goals,
                    odds=odds,
                    line=line,
                )
            )
    return tuple(found)


def main_history(
    first_year: int = 2011, last_year: int = 2024, *, league: str = "E0"
) -> tuple[HistMatch, ...]:
    """`first_year` → `last_year` başlangıçlı sezonlar; her biri ağustosun ilk cumartesisi."""
    found: list[HistMatch] = []
    for year in range(first_year, last_year + 1):
        code = f"{year % 100:02d}{(year + 1) % 100:02d}"
        first = date(year, 8, 1)
        first += timedelta(days=(5 - first.weekday()) % 7)
        found.extend(season(code, first, league=league, seed=year))
    return tuple(found)


H2H_KEYS = tuple(OddsKey("Avg", H2H, outcome, PRE_CLOSING) for outcome in ("H", "D", "A"))
```

`tests/test_model_strategies.py`:

<!-- plan: yeni tests/test_model_strategies.py -->
```python
"""Dixon-Coles stratejisi (Faz 3 tasarımı §6.2): memo, aktiflik, Ü/A ve gelecek-fit kanaryası."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from football_edge.backtest import harness
from football_edge.backtest.events import RESULT, Event, build_events
from football_edge.backtest.harness import ResultRecord, replay
from football_edge.history.types import TOTALS_25, HistMatch
from football_edge.model import strategies as model_strategies
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModel
from football_edge.model.strategies import DixonColesStrategy, fit_day
from tests.model_builders import main_history

HISTORY = main_history(2021, 2023)
CONFIG = DCConfig(xi=0.002, ridge=0.01, min_matches=40)
ACTIVE = date(2022, 7, 1)


def _probs(matches: Sequence[HistMatch], strategy: object) -> dict[int, tuple[float, ...]]:
    result = replay(matches, strategy)  # type: ignore[arg-type]
    return {prediction.match_index: prediction.probs for prediction in result.predictions}


def test_fit_day_steps_back_to_the_cadence_calendar() -> None:
    friday = date(2024, 8, 9)
    assert fit_day(friday, 1) == friday
    assert fit_day(friday, 7) == date(2024, 8, 5)  # pazartesi
    assert fit_day(date(2024, 8, 5), 7) == date(2024, 8, 5)


def test_nothing_is_predicted_before_the_active_day() -> None:
    probs = _probs(HISTORY, DixonColesStrategy(config=CONFIG, active_from=ACTIVE))

    assert probs
    assert all(HISTORY[index].date >= ACTIVE for index in probs)


def test_predictions_are_distributions_that_favour_the_stronger_side() -> None:
    probs = _probs(HISTORY, DixonColesStrategy(config=CONFIG, active_from=ACTIVE))

    for index, (home, draw, away) in probs.items():
        assert home + draw + away == pytest.approx(1.0)
        match = HISTORY[index]
        if (match.home, match.away) == ("Alfa", "Teta"):
            assert home > away


def test_totals_market_returns_over_under_and_a_zero_third_slot() -> None:
    probs = _probs(HISTORY, DixonColesStrategy(config=CONFIG, active_from=ACTIVE, market=TOTALS_25))

    assert probs
    for over, under, third in probs.values():
        assert over + under == pytest.approx(1.0) and third == 0.0


def test_the_fit_runs_once_per_group_and_fit_day(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[date] = []
    real = model_strategies.fit

    def counting(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls.append(kwargs["at"])  # type: ignore[arg-type]
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(model_strategies, "fit", counting)
    strategy = DixonColesStrategy(config=CONFIG, active_from=ACTIVE)
    totals = DixonColesStrategy(
        config=CONFIG, active_from=ACTIVE, market=TOTALS_25, memo=strategy.memo
    )

    _probs(HISTORY, strategy)
    _probs(HISTORY, totals)

    assert len(calls) == len(set(calls)) > 0


def test_invalid_settings_are_refused() -> None:
    with pytest.raises(ValueError, match="market"):
        DixonColesStrategy(market="ah")
    with pytest.raises(ValueError, match="cadence"):
        DixonColesStrategy(cadence_days=0)


def test_observe_keeps_old_values_intact_and_chunks_history() -> None:
    first = DixonColesStrategy()
    record = ResultRecord(
        "E0", date(2022, 8, 6), "Alfa", "Beta", 1, 0, datetime(2022, 8, 6, 17, tzinfo=UTC)
    )
    current = first
    for _ in range(model_strategies.CHUNK + 1):
        current = current.observe(record)

    assert first.history == {}
    assert [len(chunk) for chunk in current.history["E0"]] == [model_strategies.CHUNK, 1]


@pytest.mark.leakage
def test_leaked_future_results_do_not_reach_the_dixon_coles_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2: sonuçları üç gün ERKEN açan bozuk harness'ta Elo'nun tahmini değişir (kanarya canlı);
    Dixon-Coles'unki değişmez, çünkü fit yalnız fit gününden önce oynanmış maçları okur."""
    dc = DixonColesStrategy(config=CONFIG, active_from=ACTIVE)
    honest_dc, honest_elo = _probs(HISTORY, dc), _probs(HISTORY, EloModel())

    def leaking(matches: Sequence[HistMatch]) -> tuple[Event, ...]:
        events = build_events(matches)
        return tuple(
            sorted(
                replace(event, at=event.at - timedelta(days=3)) if event.kind == RESULT else event
                for event in events
            )
        )

    monkeypatch.setattr(harness, "build_events", leaking)
    leaked_dc = _probs(HISTORY, DixonColesStrategy(config=CONFIG, active_from=ACTIVE))
    leaked_elo = _probs(HISTORY, EloModel())

    assert leaked_elo != honest_elo
    assert leaked_dc == pytest.approx(honest_dc)
```

`tests/test_walkforward.py`:

<!-- plan: yeni tests/test_walkforward.py -->
```python
"""Walk-forward satırları ve değerlendirmesi (Faz 3 tasarımı §5, §6.3–6.5). Veri SENTETİK."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from types import MappingProxyType

import pytest

from football_edge.backtest import wf_eval
from football_edge.backtest.records import MatchKey
from football_edge.backtest.walkforward import (
    DC,
    DC_TOTALS,
    ELO,
    EVALUATION,
    MARKET,
    SELECTION,
    Row,
    group_kind,
    group_matches,
    group_rows,
    zone_of,
)
from football_edge.backtest.wf_eval import (
    BLEND,
    MARKET_ONLY,
    bet_clv,
    fold_weights,
    summarise,
)
from football_edge.history.catalog import EXTRA, MAIN
from football_edge.history.types import TOTALS_25
from football_edge.market.devig import POWER
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModel
from football_edge.model.pool import MIN_FIT_MATCHES
from football_edge.model.strategies import DixonColesStrategy
from tests.backtest_builders import hist_match
from tests.model_builders import main_history

KINDS = MappingProxyType({"E0": MAIN, "E1": MAIN, "BRA": EXTRA})


def _strategies() -> dict[str, object]:
    dc = DixonColesStrategy(config=DCConfig(min_matches=40), active_from=date(2012, 7, 1))
    return {
        ELO: EloModel(),
        DC: dc,
        DC_TOTALS: DixonColesStrategy(
            config=dc.config, active_from=dc.active_from, market=TOTALS_25, memo=dc.memo
        ),
    }


@pytest.mark.parametrize(
    ("day", "kind", "zone"),
    [
        (date(2012, 6, 30), MAIN, None),
        (date(2012, 7, 1), MAIN, SELECTION),
        (date(2019, 6, 30), MAIN, SELECTION),
        (date(2019, 7, 1), MAIN, EVALUATION),
        (date(2025, 6, 30), MAIN, EVALUATION),
        (date(2025, 7, 1), MAIN, None),
        (date(2012, 12, 31), EXTRA, None),
        (date(2013, 1, 1), EXTRA, SELECTION),
        (date(2018, 7, 1), EXTRA, EVALUATION),
        (date(2026, 8, 1), EXTRA, None),
    ],
)
@pytest.mark.leakage
def test_zones_stay_inside_the_development_period(day: date, kind: str, zone: str | None) -> None:
    assert zone_of(hist_match(day=day), kind) == zone


def test_groups_join_the_leagues_of_a_country_in_a_fixed_order() -> None:
    late = hist_match(day=date(2020, 1, 4), league="E1", home="Gama", away="Delta")
    early = hist_match(day=date(2020, 1, 3), league="E0")
    other = hist_match(day=date(2020, 1, 2), league="BRA")

    grouped = group_matches(
        {"E1": (late,), "E0": (early,), "BRA": (other,)},
        {"E0": "England", "E1": "England", "BRA": "Brazil"},
    )

    assert list(grouped) == ["Brazil", "England"]
    assert grouped["England"] == (early, late)


def test_a_group_mixing_main_and_extra_leagues_is_refused() -> None:
    with pytest.raises(ValueError, match="ana ve ek"):
        group_kind(
            (hist_match(day=date(2020, 1, 4)), hist_match(day=date(2020, 1, 4), league="BRA")),
            KINDS,
        )


@pytest.fixture(scope="module")
def rows() -> tuple[Row, ...]:
    return group_rows(main_history(2011, 2021), KINDS, _strategies(), method=POWER)  # type: ignore[arg-type]


def test_rows_come_only_from_the_selection_and_evaluation_zones(rows: tuple[Row, ...]) -> None:
    assert {row.zone for row in rows} == {SELECTION, EVALUATION}
    assert min(row.key.date for row in rows) >= date(2012, 7, 1)


def test_the_market_component_reads_bbav_in_selection_and_avg_in_evaluation(
    rows: tuple[Row, ...],
) -> None:
    selection = [row for row in rows if row.zone == SELECTION]
    evaluation = [row for row in rows if row.zone == EVALUATION]

    assert all(MARKET in row.components and row.closing is None for row in selection)
    assert all(MARKET in row.components and row.closing is not None for row in evaluation)
    assert all(row.pre is not None for row in rows)
    assert all(
        MARKET in row.totals and DC in row.totals for row in evaluation if row.components.get(DC)
    )


def test_model_components_are_present_once_the_models_have_history(rows: tuple[Row, ...]) -> None:
    late = [row for row in rows if row.key.date >= date(2014, 1, 1)]

    assert all(ELO in row.components for row in late)
    assert sum(DC in row.components for row in late) == len(late)


def _row(league: str, season: str, zone: str, outcome: int, index: int) -> Row:
    market, elo, dc = (0.5, 0.3, 0.2), (0.2, 0.3, 0.5), (0.34, 0.33, 0.33)
    return Row(
        key=MatchKey(league, date(2020, 1, 1), f"Ev {index}", f"Konuk {index}"),
        kind=MAIN,
        zone=zone,
        season=season,
        outcome=outcome,
        totals_outcome=0,
        components=MappingProxyType({MARKET: market, ELO: elo, DC: dc}),
        totals=MappingProxyType({}),
        pre=(2.0, 3.2, 4.5),
        closing=(0.48, 0.3, 0.22),
        totals_pre=None,
        totals_closing=None,
    )


def _table(outcome_of: dict[str, int], count: int = MIN_FIT_MATCHES) -> list[Row]:
    """Sezon → her maçta hep aynı sonuç: 0 piyasayı, 2 Elo'yu haklı çıkarır."""
    zones = {"1819": SELECTION, "1920": EVALUATION, "2021": EVALUATION, "2122": EVALUATION}
    return [
        _row("E0", season, zones[season], outcome, index + 1000 * position)
        for position, (season, outcome) in enumerate(outcome_of.items())
        for index in range(count)
    ]


@pytest.mark.leakage
def test_a_seasons_weights_never_see_that_season_or_later() -> None:
    """G3: `s`'nin satırları değişince `s`'nin ağırlığı değişmez, `s`'den sonrakininki değişir."""
    base = _table({"1819": 0, "1920": 0, "2021": 0, "2122": 0})
    flipped = _table({"1819": 0, "1920": 0, "2021": 2, "2122": 0})

    before, _ = fold_weights(base)
    after, _ = fold_weights(flipped)

    assert after[("E0", "1920")] == before[("E0", "1920")]
    assert after[("E0", "2021")] == before[("E0", "2021")]
    assert after[("E0", "2122")] != before[("E0", "2122")]


def test_the_first_evaluation_season_uses_the_selection_rows() -> None:
    weights, _ = fold_weights(_table({"1819": 2, "1920": 0}))

    market, elo, _dc = weights[("E0", "1920")]
    assert elo > market


def test_a_thin_league_falls_back_to_the_pooled_rows_and_then_to_the_market() -> None:
    thin = _table({"1819": 0, "1920": 0}, count=10)

    weights, fallback = fold_weights(thin)

    assert weights[("E0", "1920")] == MARKET_ONLY
    assert fallback == ("E0/1920",)


def test_a_league_below_the_league_minimum_takes_the_pooled_weights() -> None:
    """Tek ligin ~bir sezonu (< LEAGUE_MIN_MATCHES) kendi ağırlığını fit etmez: gürültüsü W1'i
    aşardı."""
    small = _table({"1819": 0, "1920": 0}, count=wf_eval.LEAGUE_MIN_MATCHES - 1)

    _, fallback = fold_weights(small)

    assert fallback == ("E0/1920",)


@pytest.mark.parametrize(
    ("probs", "tau", "expected"),
    [
        ((0.6, 0.25, 0.15), 0.02, 2.0 * 0.48 - 1.0),  # H: 0.6·2.0 − 1 = 0.2 en büyük, > τ
        ((0.5, 0.3, 0.2), 0.02, None),  # en büyük EV 0.0 ≤ τ
        ((0.45, 0.2, 0.35), 0.5, 4.5 * 0.22 - 1.0),  # A: 0.35·4.5 − 1 = 0.575 > 0.5
        ((0.45, 0.2, 0.35), 0.6, None),  # 0.575 ≤ 0.6
    ],
)
def test_the_bet_rule_takes_the_largest_edge_above_tau(
    probs: tuple[float, float, float], tau: float, expected: float | None
) -> None:
    found = bet_clv(probs, (2.0, 3.2, 4.5), (0.48, 0.3, 0.22), tau)

    if expected is None:
        assert found is None
    else:
        assert found == pytest.approx(expected)


def test_no_bet_without_a_pre_price_or_a_closing() -> None:
    assert bet_clv((0.9, 0.05, 0.05), None, (0.4, 0.3, 0.3), 0.0) is None
    assert bet_clv((0.9, 0.05, 0.05), (2.0, 3.0, 4.0), None, 0.0) is None


def test_the_summary_compares_on_common_rows_and_is_deterministic(rows: tuple[Row, ...]) -> None:
    """G7: aynı satırlar → aynı özet."""
    first = summarise(rows, tau=0.02, sensitivity=(0.0, 0.05), resamples=50)
    second = summarise(rows, tau=0.02, sensitivity=(0.0, 0.05), resamples=50)

    assert first == second
    assert set(first.main) == {MARKET, ELO, DC, BLEND}
    assert len({score.n for score in first.main.values()}) == 1
    assert first.blend_gap is not None and set(first.league_gaps) == {"E0"}
    assert set(first.clv_sensitivity) == {0.0, 0.05}
    assert set(first.totals) == {MARKET, DC}


def test_rows_missing_a_component_are_counted_not_blended(rows: tuple[Row, ...]) -> None:
    evaluation = [row for row in rows if row.zone == EVALUATION]
    broken = replace(evaluation[0], components=MappingProxyType({MARKET: (0.5, 0.3, 0.2)}))

    summary = summarise((*rows, broken), tau=0.02, sensitivity=(), resamples=20)

    assert wf_eval.complete(broken) is False
    assert summary.incomplete == 1
    assert summary.main[BLEND].n == len(evaluation)


@pytest.mark.leakage
def test_frozen_weights_never_see_holdout_or_post_rows() -> None:
    """I2: `final_eval`in satırları holdout ve sonrası bölgelerini TAM bileşenle taşır; ağırlık
    yalnız geliştirmenin E'sinden gelir: holdout satırları Elo'yu haklı çıkarsa da ağırlık aynı."""
    development = _table({"1819": 0, "1920": 0}, count=wf_eval.LEAGUE_MIN_MATCHES)
    holdout = [
        replace(
            _row("E0", "2526", zone, 2, index),
            key=MatchKey("E0", date(2026, 1, 1), f"H{index}", "K"),
        )
        for zone in ("holdout", "post")
        for index in range(3000)
    ]

    alone, _ = wf_eval.frozen_weights(development, [("E0", "2526")])
    mixed, _ = wf_eval.frozen_weights([*development, *holdout], [("E0", "2526")])

    assert mixed == alone
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/model_builders.py tests/test_model_strategies.py tests/test_walkforward.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.model.strategies'` ve `'football_edge.backtest.walkforward'`

- [ ] **Step 3: Uygulamayı yaz**

`src/football_edge/model/strategies.py`:

<!-- plan: yeni src/football_edge/model/strategies.py -->
```python
"""Dixon-Coles'u harness'ın `Strategy` arayüzüne takar (Faz 3 tasarımı §6.2).

Durum: grup (ülke, R94/R136) başına gözlenen goller, parça parça demetlerde (`CHUNK`): her
`observe` yalnız son parçayı kopyalar — ~45 bin sonuçlu bir grupta tam demet kopyası O(n²) olurdu.
Fit, karar gününün ISO günlük/haftalık tabanında (`cadence_days`) bir kez yapılır ve bir memo'da
tutulur. Memo eşitliğe girmez; anahtarı (grup, fit günü) ve fit yalnız `fit günü`nden ÖNCEKİ
maçları okur (`dixon_coles.fit`), bu yüzden memo geleceği taşıyamaz — en kötü hâli bayatlıktır.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from types import MappingProxyType

from football_edge.backtest.harness import DecisionContext, Prediction, ResultRecord
from football_edge.backtest.timeline import LONDON
from football_edge.history.types import H2H, TOTALS_25
from football_edge.model.dixon_coles import (
    DCConfig,
    DCParams,
    GoalRecord,
    fit,
    outcome_probs,
    score_matrix,
    totals_probs,
)

CHUNK = 256
_ANCHOR_MONDAY = date(2000, 1, 3)
Chunks = tuple[tuple[GoalRecord, ...], ...]


@dataclass
class _FitMemo:
    """Değişebilir memo — bilinçli istisna: saf bir fonksiyonun sonucunu (grup, gün) ile saklar."""

    fits: dict[tuple[str, date], DCParams | None] = field(default_factory=dict)
    latest: dict[str, DCParams] = field(default_factory=dict)


def _append(chunks: Chunks, record: GoalRecord) -> Chunks:
    if not chunks or len(chunks[-1]) >= CHUNK:
        return (*chunks, (record,))
    return (*chunks[:-1], (*chunks[-1], record))


def fit_day(decided_on: date, cadence_days: int) -> date:
    """Karar gününden geriye, `cadence_days` adımlı sabit takvimde en yakın gün (≤ karar günü)."""
    return decided_on - timedelta(days=(decided_on - _ANCHOR_MONDAY).days % cadence_days)


def _no_history() -> Mapping[str, Chunks]:
    return MappingProxyType({})


def _no_groups() -> Mapping[str, str]:
    return MappingProxyType({})


@dataclass(frozen=True)
class DixonColesStrategy:
    config: DCConfig = DCConfig()
    groups: Mapping[str, str] = field(default_factory=_no_groups)
    market: str = H2H
    active_from: date | None = None  # öncesinde tahmin (ve fit) yok: ısınma hesabı boşa gitmez
    cadence_days: int = 1
    history: Mapping[str, Chunks] = field(default_factory=_no_history)
    memo: _FitMemo = field(default_factory=_FitMemo, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.market not in (H2H, TOTALS_25):
            raise ValueError(f"desteklenmeyen market: {self.market!r}")
        if self.cadence_days < 1:
            raise ValueError(f"cadence_days ≥ 1 olmalı: {self.cadence_days}")

    @property
    def name(self) -> str:
        return "dixon_coles" if self.market == H2H else "dixon_coles_ou25"

    def _group(self, league: str) -> str:
        return self.groups.get(league, league)

    def observe(self, result: ResultRecord) -> DixonColesStrategy:
        group = self._group(result.league)
        record = GoalRecord(
            result.home, result.away, result.home_goals, result.away_goals, result.date
        )
        chunks = _append(self.history.get(group, ()), record)
        return replace(self, history=MappingProxyType({**self.history, group: chunks}))

    def params(self, group: str, at: date) -> DCParams | None:
        key = (group, at)
        if key not in self.memo.fits:
            latest = self.memo.latest.get(group)
            start = latest if latest is not None and latest.fitted_on < at else None
            records = [record for chunk in self.history.get(group, ()) for record in chunk]
            found = fit(records, at=at, config=self.config, start=start)
            self.memo.fits[key] = found
            if found is not None and (latest is None or latest.fitted_on < at):
                self.memo.latest[group] = found
        return self.memo.fits[key]

    def predict(self, context: DecisionContext) -> Prediction | None:
        if self.active_from is not None and context.date < self.active_from:
            return None
        decided_on = context.decision_at.astimezone(LONDON).date()
        found = self.params(self._group(context.league), fit_day(decided_on, self.cadence_days))
        if found is None:
            return None
        matrix = score_matrix(found, context.home, context.away, self.config.max_goals)
        if matrix is None:
            return None
        if self.market == H2H:
            probs = outcome_probs(matrix)
        else:
            over, under = totals_probs(matrix)
            probs = (over, under, 0.0)  # Ü/A iki yollu; üçüncü yuva hep 0 (harness 3-demet taşır)
        return Prediction(context.match_index, self.name, probs)
```

`src/football_edge/backtest/walkforward.py`:

<!-- plan: yeni src/football_edge/backtest/walkforward.py -->
```python
"""Walk-forward satırları (Faz 3 tasarımı §5, R129): grup başına yeniden oynatma → bileşen tablosu.

Yalnız geliştirme dönemi: bölgeler `Window` ile kurulur ve `Window` holdout'a uzanamaz (R89).
Isınma bölgesi durumu ısıtır, satır üretmez. Model bileşenleri (Elo, Dixon-Coles) harness'tan
geçer; piyasa bileşeni maçın KENDİ kapanış öncesi fiyatıdır — `MarketPre`in bağlamdan okuduğunun
aynısı (kapanış ve sonuç satıra yalnız değerlendirme alanı olarak girer, hiçbir bileşene girmez).
Yeniden oynatma ülke grubu başına (R94, R136): gruplar arasında durum etkileşimi yoktur.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType

from football_edge.backtest.context import record_of
from football_edge.backtest.harness import Strategy, replay
from football_edge.backtest.records import MatchKey
from football_edge.backtest.timeline import decision_at
from football_edge.history.catalog import EXTRA, MAIN
from football_edge.history.holdout import DEV_END, MAIN_WINDOW, Window, in_window
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch
from football_edge.market.devig import match_probs
from football_edge.market.metrics import outcome_index

SELECTION = "S"
EVALUATION = "E"
MAIN_SELECTION = Window(date(2012, 7, 1), date(2019, 7, 1))
MAIN_EVALUATION = MAIN_WINDOW
# Ek dosyalar 2012'de başlar: ilk yıl yalnız ısınma.
EXTRA_SELECTION = Window(date(2013, 1, 1), date(2018, 7, 1))
EXTRA_EVALUATION = Window(date(2018, 7, 1), DEV_END)
ZONES: Mapping[str, Mapping[str, Window]] = MappingProxyType(
    {
        MAIN: MappingProxyType({SELECTION: MAIN_SELECTION, EVALUATION: MAIN_EVALUATION}),
        EXTRA: MappingProxyType({SELECTION: EXTRA_SELECTION, EVALUATION: EXTRA_EVALUATION}),
    }
)
# S'de kapanış öncesi ortalama Betbrain'in (`BbAv`), E'de football-data'nın `Avg`'si (ölçüm §2.4).
PRE_BOOK: Mapping[str, str] = MappingProxyType({SELECTION: "BbAv", EVALUATION: "Avg"})
REFERENCE_BOOK = "Avg"
MARKET = "market"
ELO = "elo_fit"
DC = "dixon_coles"
DC_TOTALS = "dixon_coles_ou25"
ELO_SCAFFOLD = "elo_scaffold"  # Faz 2 iskelesi (`EloPointInTime`): kıyas, harmana girmez
BLEND_COMPONENTS: tuple[str, ...] = (MARKET, ELO, DC)
_NO_KICKOFF = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Row:
    """Bir maçın walk-forward kaydı: bileşenler + yalnız değerlendirmenin okuduğu alanlar."""

    key: MatchKey
    kind: str
    zone: str
    season: str
    outcome: int  # RESULTS sırası
    totals_outcome: int  # 0 üst, 1 alt
    components: Mapping[str, tuple[float, ...]]  # 1X2 (H, D, A)
    totals: Mapping[str, tuple[float, ...]]  # Ü/A 2.5 (üst, alt)
    pre: tuple[float, ...] | None  # bölgenin kitabının kapanış öncesi 1X2 fiyatı (bahis fiyatı)
    closing: tuple[float, ...] | None  # vig'i temizlenmiş AvgC 1X2
    totals_pre: tuple[float, ...] | None
    totals_closing: tuple[float, ...] | None


def zone_of(match: HistMatch, kind: str) -> str | None:
    for zone, window in ZONES[kind].items():
        if in_window(match, window):
            return zone
    return None


def group_matches(
    leagues: Mapping[str, Sequence[HistMatch]], groups: Mapping[str, str]
) -> Mapping[str, tuple[HistMatch, ...]]:
    """Grup (ülke) → maçlar; (tarih, başlama, lig, ev) sırasıyla — `replay` sırayı zaten olaydan
    kurar, bu sıra yalnız `match_index`i belirlenimci yapar."""
    found: dict[str, list[HistMatch]] = {}
    for code in sorted(leagues):
        found.setdefault(groups.get(code, code), []).extend(leagues[code])
    return MappingProxyType(
        {
            group: tuple(
                sorted(
                    matches,
                    key=lambda m: (m.date, m.kickoff or _NO_KICKOFF, m.league, m.home),
                )
            )
            for group, matches in sorted(found.items())
        }
    )


def group_kind(matches: Sequence[HistMatch], kinds: Mapping[str, str]) -> str:
    found = {kinds[match.league] for match in matches}
    if len(found) != 1:
        raise ValueError(f"bir grupta ana ve ek lig birlikte: {sorted(found)}")
    return found.pop()


def model_probs(
    matches: Sequence[HistMatch], strategies: Mapping[str, Strategy]
) -> Mapping[str, Mapping[int, tuple[float, ...]]]:
    """Strateji adı → maç sırası → tahmin olasılıkları (tek grup, strateji başına bir oynatma)."""
    found: dict[str, Mapping[int, tuple[float, ...]]] = {}
    for name, strategy in strategies.items():
        result = replay(matches, strategy)
        found[name] = MappingProxyType(
            {prediction.match_index: prediction.probs for prediction in result.predictions}
        )
    return MappingProxyType(found)


def _market(match: HistMatch, book: str, market: str, method: str) -> tuple[float, ...] | None:
    return match_probs(match, book=book, market=market, phase=PRE_CLOSING, method=method)


def _row(
    index: int,
    match: HistMatch,
    kind: str,
    zone: str,
    probs: Mapping[str, Mapping[int, tuple[float, ...]]],
    method: str,
) -> Row:
    book = PRE_BOOK.get(zone, REFERENCE_BOOK)
    components: dict[str, tuple[float, ...]] = {
        name: found[index] for name, found in probs.items() if name != DC_TOTALS and index in found
    }
    market = _market(match, book, H2H, method)
    if market is not None:
        components[MARKET] = market
    totals: dict[str, tuple[float, ...]] = {}
    if index in probs.get(DC_TOTALS, {}):
        totals[DC] = probs[DC_TOTALS][index][:2]
    market_totals = _market(match, REFERENCE_BOOK, TOTALS_25, method)
    if market_totals is not None and zone != SELECTION:
        totals[MARKET] = market_totals
    return Row(
        key=record_of(match).key,
        kind=kind,
        zone=zone,
        season=match.season,
        outcome=outcome_index(match, H2H),
        totals_outcome=outcome_index(match, TOTALS_25),
        components=MappingProxyType(components),
        totals=MappingProxyType(totals),
        pre=match.prices(book, H2H, PRE_CLOSING),
        closing=match_probs(match, book=REFERENCE_BOOK, market=H2H, phase=CLOSING, method=method),
        totals_pre=match.prices(REFERENCE_BOOK, TOTALS_25, PRE_CLOSING),
        totals_closing=match_probs(
            match, book=REFERENCE_BOOK, market=TOTALS_25, phase=CLOSING, method=method
        ),
    )


def group_rows(
    matches: Sequence[HistMatch],
    kinds: Mapping[str, str],
    strategies: Mapping[str, Strategy],
    *,
    method: str,
    zoning: Callable[[HistMatch, str], str | None] = zone_of,
) -> tuple[Row, ...]:
    """Bir grubun bölge satırları (varsayılan S ve E); kararı olmayan ve bölgesiz maç satır
    üretmez. `final_eval` kendi bölgelemesini (holdout, sonrası) verir."""
    kind = group_kind(matches, kinds)
    probs = model_probs(matches, strategies)
    rows: list[Row] = []
    for index, match in enumerate(matches):
        zone = zoning(match, kind)
        if zone is None or decision_at(match.date, match.kickoff) is None:
            continue
        rows.append(_row(index, match, kind, zone, probs, method))
    return tuple(rows)
```

`src/football_edge/backtest/wf_eval.py`:

<!-- plan: yeni src/football_edge/backtest/wf_eval.py -->
```python
"""Walk-forward değerlendirmesi (Faz 3 tasarımı §5.2–5.3, §6.3–6.5; R129, R137, R139).

Havuz ağırlığı lig başına genişleyen sezon katlarıyla: E'nin sezonu `s` için ağırlık YALNIZ E'nin
`s`'den önceki sezonlarının satırlarıyla fit edilir; E'nin ilk sezonu S'nin satırlarını kullanır.
Ligin eğitim satırı `LEAGUE_MIN_MATCHES`ın altındaysa aynı kural bütün ana liglerin havuzuyla, o da
`MIN_FIT_MATCHES`ın altındaysa yalnız piyasa `(1, 0, 0)`. Eşik gürültüye karşıdır: üç ağırlığın
örneklem dışı bedeli ~ 3 / 2n; tek ligin bir sezonu (~380 maç) bunu W1'in δ'sının üstüne çıkarır.
Karşılaştırmalar ORTAK satırlarda (bütün bileşenleri olan maçlar) yapılır: aynı maç kümesi.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from football_edge.backtest.walkforward import (
    BLEND_COMPONENTS,
    DC,
    ELO,
    EVALUATION,
    MARKET,
    SELECTION,
    Row,
)
from football_edge.history.catalog import EXTRA, MAIN
from football_edge.market.metrics import (
    Calibration,
    Interval,
    bootstrap_mean,
    brier,
    calibration,
    clv,
    per_match_log_loss,
    rps,
)
from football_edge.model.pool import TooFewMatches, fit_weights, pool

BLEND = "blend"
CLOSING_NAME = "closing"
MARKET_ONLY: tuple[float, ...] = (1.0, 0.0, 0.0)
LEAGUE_MIN_MATCHES = 1000
Weights = Mapping[tuple[str, str], tuple[float, ...]]  # (lig, sezon) → ağırlık


@dataclass(frozen=True)
class Score:
    name: str
    n: int
    log_loss: Interval
    brier: float
    rps: float | None  # yalnız 1X2 (sıralı üç sonuç)
    calibration: Calibration | None  # yakınsamazsa None (ölçülemedi)
    clv: Interval | None
    bets: int


@dataclass(frozen=True)
class Summary:
    main: Mapping[str, Score]  # E, ana ligler, ortak satırlar: market, elo_fit, dixon_coles, blend
    blend_gap: Interval | None  # LL(blend) − LL(market), eşleştirilmiş
    league_gaps: Mapping[str, Interval]
    extra: Mapping[str, Score]  # E, ek ligler: elo_fit, dixon_coles, closing (kıyas)
    totals: Mapping[str, Score]  # E, ana ligler, Ü/A 2.5: market, dixon_coles
    clv_sensitivity: Mapping[float, Interval | None]  # τ → harman CLV'si
    rows: int
    incomplete: int  # bileşeni eksik E satırı (ortak kümeye girmedi)
    fallback: tuple[str, ...]  # havuzlanmış ya da yalnız piyasa ağırlığı alan (lig, sezon)


def complete(row: Row, names: Sequence[str] = BLEND_COMPONENTS) -> bool:
    return all(name in row.components for name in names)


def _fit_or_none(rows: Sequence[Row]) -> tuple[float, ...] | None:
    try:
        return fit_weights(
            [[row.components[name] for name in BLEND_COMPONENTS] for row in rows],
            [row.outcome for row in rows],
        )
    except TooFewMatches:
        return None


def _training(rows: Sequence[Row], season: str) -> list[Row]:
    earlier = [row for row in rows if row.zone == EVALUATION and row.season < season]
    return earlier or [row for row in rows if row.zone == SELECTION]


def fold_weights(rows: Sequence[Row]) -> tuple[Weights, tuple[str, ...]]:
    """(lig, E sezonu) → ağırlık ve geri düşülen anahtarlar; yalnız ana ligler ve tam satırlar."""
    usable = [row for row in rows if row.kind == MAIN and complete(row)]
    weights: dict[tuple[str, str], tuple[float, ...]] = {}
    fallback: list[str] = []
    for league in sorted({row.key.league for row in usable}):
        own = [row for row in usable if row.key.league == league]
        seasons = sorted({row.season for row in own if row.zone == EVALUATION})
        for season in seasons:
            training = _training(own, season)
            found = _fit_or_none(training) if len(training) >= LEAGUE_MIN_MATCHES else None
            if found is None:
                fallback.append(f"{league}/{season}")
                found = _fit_or_none(_training(usable, season)) or MARKET_ONLY
            weights[(league, season)] = found
    return MappingProxyType(weights), tuple(fallback)


def frozen_weights(
    rows: Sequence[Row], targets: Sequence[tuple[str, str]]
) -> tuple[Weights, tuple[str, ...]]:
    """Geliştirme satırlarının BÜTÜN E'siyle fit edilmiş ağırlık, verilen (lig, sezon) için —
    holdout ve sonrası dönemi ağırlığı hiç görmez (`final_eval`)."""
    usable = [row for row in rows if row.kind == MAIN and complete(row) and row.zone == EVALUATION]
    weights: dict[tuple[str, str], tuple[float, ...]] = {}
    fallback: list[str] = []
    pooled = _fit_or_none(usable) or MARKET_ONLY
    for league, season in sorted(set(targets)):
        own = [row for row in usable if row.key.league == league]
        found = _fit_or_none(own) if len(own) >= LEAGUE_MIN_MATCHES else None
        if found is None:
            fallback.append(f"{league}/{season}")
            found = pooled
        weights[(league, season)] = found
    return MappingProxyType(weights), tuple(fallback)


def blended(rows: Sequence[Row], weights: Weights) -> tuple[tuple[Row, tuple[float, ...]], ...]:
    return tuple(
        (
            row,
            pool(
                [row.components[name] for name in BLEND_COMPONENTS],
                weights[(row.key.league, row.season)],
            ),
        )
        for row in rows
        if (row.key.league, row.season) in weights and complete(row)
    )


def bet_clv(
    probs: Sequence[float],
    pre: Sequence[float] | None,
    closing: Sequence[float] | None,
    tau: float,
) -> float | None:
    """Sabit kural (§6.4): en büyük `p · o − 1` sonucu, eşiği aşıyorsa; CLV kapanışa karşı."""
    if pre is None or closing is None:
        return None
    values = [p * o - 1.0 for p, o in zip(probs, pre, strict=True)]
    pick = max(range(len(values)), key=values.__getitem__)
    if values[pick] <= tau:
        return None
    return clv(pre[pick], closing[pick])


def _calibration(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> Calibration | None:
    try:
        return calibration(probs, outcomes)
    except ValueError:
        return None


def score(
    name: str,
    probs: Sequence[Sequence[float]],
    outcomes: Sequence[int],
    clvs: Sequence[float],
    *,
    resamples: int,
) -> Score:
    return Score(
        name=name,
        n=len(probs),
        log_loss=bootstrap_mean(per_match_log_loss(probs, outcomes), resamples=resamples),
        brier=brier(probs, outcomes),
        rps=rps(probs, outcomes) if len(probs[0]) == 3 else None,
        calibration=_calibration(probs, outcomes),
        clv=bootstrap_mean(clvs, resamples=resamples) if clvs else None,
        bets=len(clvs),
    )


def _clvs(pairs: Sequence[tuple[Row, Sequence[float]]], tau: float) -> list[float]:
    found = [bet_clv(probs, row.pre, row.closing, tau) for row, probs in pairs]
    return [value for value in found if value is not None]


def _gap(
    first: Sequence[Sequence[float]],
    second: Sequence[Sequence[float]],
    outcomes: Sequence[int],
    resamples: int,
) -> Interval:
    a = per_match_log_loss(first, outcomes)
    b = per_match_log_loss(second, outcomes)
    return bootstrap_mean([x - y for x, y in zip(a, b, strict=True)], resamples=resamples)


def _main_scores(
    pairs: Sequence[tuple[Row, tuple[float, ...]]], tau: float, resamples: int
) -> dict[str, Score]:
    """Harman ve bütün satırlarda bulunan her bileşen (ör. `final_eval`in iskele Elo'su)."""
    outcomes = [row.outcome for row, _ in pairs]
    names = sorted(set.intersection(*(set(row.components) for row, _ in pairs)))
    found: dict[str, Score] = {}
    for name in names:
        column = [(row, row.components[name]) for row, _ in pairs]
        found[name] = score(
            name, [p for _, p in column], outcomes, _clvs(column, tau), resamples=resamples
        )
    found[BLEND] = score(
        BLEND, [p for _, p in pairs], outcomes, _clvs(pairs, tau), resamples=resamples
    )
    return found


def _extra_scores(rows: Sequence[Row], resamples: int) -> dict[str, Score]:
    usable = [row for row in rows if complete(row, (ELO, DC)) and row.closing is not None]
    if not usable:
        return {}
    outcomes = [row.outcome for row in usable]
    found = {
        name: score(
            name, [row.components[name] for row in usable], outcomes, (), resamples=resamples
        )
        for name in (ELO, DC)
    }
    closing = [row.closing for row in usable if row.closing is not None]
    found[CLOSING_NAME] = score(CLOSING_NAME, closing, outcomes, (), resamples=resamples)
    return found


def _totals_scores(rows: Sequence[Row], tau: float, resamples: int) -> dict[str, Score]:
    usable = [row for row in rows if MARKET in row.totals and DC in row.totals]
    if not usable:
        return {}
    outcomes = [row.totals_outcome for row in usable]
    found: dict[str, Score] = {}
    for name in (MARKET, DC):
        clvs = [
            bet_clv(row.totals[name], row.totals_pre, row.totals_closing, tau) for row in usable
        ]
        found[name] = score(
            name,
            [row.totals[name] for row in usable],
            outcomes,
            [value for value in clvs if value is not None],
            resamples=resamples,
        )
    return found


def summarise(
    rows: Sequence[Row],
    *,
    tau: float,
    sensitivity: Sequence[float],
    resamples: int,
    zone: str = EVALUATION,
    given: tuple[Weights, tuple[str, ...]] | None = None,
) -> Summary:
    """`zone` bölgesinin özeti; ağırlık verilmezse genişleyen katlar (`fold_weights`)."""
    weights, fallback = fold_weights(rows) if given is None else given
    evaluation = [row for row in rows if row.zone == zone]
    main = [row for row in evaluation if row.kind == MAIN]
    pairs = blended(main, weights)
    outcomes = [row.outcome for row, _ in pairs]
    market = [row.components[MARKET] for row, _ in pairs]
    leagues = sorted({row.key.league for row, _ in pairs})
    return Summary(
        main=MappingProxyType(_main_scores(pairs, tau, resamples) if pairs else {}),
        blend_gap=_gap([p for _, p in pairs], market, outcomes, resamples) if pairs else None,
        league_gaps=MappingProxyType(
            {
                league: _gap(
                    [p for row, p in pairs if row.key.league == league],
                    [row.components[MARKET] for row, _ in pairs if row.key.league == league],
                    [row.outcome for row, _ in pairs if row.key.league == league],
                    resamples,
                )
                for league in leagues
            }
        ),
        extra=MappingProxyType(
            _extra_scores([row for row in evaluation if row.kind == EXTRA], resamples)
        ),
        totals=MappingProxyType(_totals_scores(main, tau, resamples)),
        clv_sensitivity=MappingProxyType(
            {
                value: (
                    bootstrap_mean(found, resamples=resamples)
                    if (found := _clvs(pairs, value))
                    else None
                )
                for value in sensitivity
            }
        ),
        rows=len(evaluation),
        incomplete=sum(1 for row in main if not complete(row)),
        fallback=fallback,
    )
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/model_builders.py tests/test_model_strategies.py tests/test_walkforward.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — test_model_strategies 8 · test_walkforward 27 passed

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `dixon_coles._used`: `record.day < at and` silinir (fit geleceği okur) | `tests/test_model_strategies.py::test_leaked_future_results_do_not_reach_the_dixon_coles_fit` |
| 2 | `fit_day`: `% cadence_days` → `% 7` | `tests/test_model_strategies.py::test_fit_day_steps_back_to_the_cadence_calendar` |
| 3 | `_training`: `row.season < season` → `<=` | `tests/test_walkforward.py::test_a_seasons_weights_never_see_that_season_or_later` |
| 4 | `PRE_BOOK`: S'de `BbAv` → `Avg` | `tests/test_walkforward.py::test_the_market_component_reads_bbav_in_selection_and_avg_in_evaluation` |
| 5 | `bet_clv`: `<= tau` → `<= -1.0` | `tests/test_walkforward.py::test_the_bet_rule_takes_the_largest_edge_above_tau` |
| 6 | `fold_weights`: `LEAGUE_MIN_MATCHES` yerine 300 | `tests/test_walkforward.py::test_a_league_below_the_league_minimum_takes_the_pooled_weights` |
| 7 | `frozen_weights`: `and row.zone == EVALUATION` silinir (holdout satırları ağırlığa girer; inceleme I2) | `tests/test_walkforward.py::test_frozen_weights_never_see_holdout_or_post_rows` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add src/football_edge/model/strategies.py \
  src/football_edge/backtest/walkforward.py \
  src/football_edge/backtest/wf_eval.py \
  tests/model_builders.py \
  tests/test_model_strategies.py \
  tests/test_walkforward.py
git commit -m "feat: Faz 3 P1 — Dixon-Coles stratejisi, walk-forward satırları, ağırlık katları ve özet

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
**Dalga 2 sonu (controller, Task 6 birleşince):** `git merge --no-ff feat/faz3-walkforward` → kapı → `leakage`
sayısı ölçülür (plan yazımında 282) ve `EXPECTED_MIN_LEAKAGE` güncellenir → commit `ci: Faz 3 dalga 2 — sızıntı
alt sınırı` → taze klon kapısı → push. Dalga 3 (Task 7, 8) bu commit'ten açılır.

---

### Task 7: S'de seçim, model yapılandırması, `select` ve `walkforward` CLI (P1 devamı)

**Kademe:** K1 · **Dalga:** 3 · **Worktree/dal:** `.worktrees/wt-select` · `feat/faz3-select`

R129: hiperparametreler S'de BİR kez seçilir, `config/model_faz3.yaml`da dondurulur (katalog ve kilidin sha256'sıyla). Seçim tek turluk koordinat inişi (P10); Elo'nun δ'sı her adayda `fit_draw` ile. `walkforward` yapılandırmayı okur, katalog/kilit özeti değiştiyse exit 11 ve rapor YAZMAZ; yalnız DEV okunur (`development_groups`), rapor yalnız toplu sayı. Rapor yardımcıları (`score_table`, `format_interval`) Task 10'un holdout raporunca da kullanılır — adları sözleşmede. `gap_penalty` R128'nin DEV simülasyonudur: E'nin 2022/23 sezonu girdiden çıkarılır, 2023/24'ün AYNI maçları iki koşuda karşılaştırılır (`walkforward --gap`). Rapor satırların sha256 özetini taşır (`rows_digest`, tasarım §5.3). `select` girdiyi S'nin sonunda keser: S tahminleri ondan sonrasına bağlı değildir, E'yi her adayda yeniden oynatmak boşa süre (inceleme m6).

**Files:**
- Create: `src/football_edge/backtest/model_config.py`
- Create: `src/football_edge/backtest/selection.py`
- Create: `src/football_edge/backtest/wf_run.py`
- Create: `tests/test_model_selection.py`
- Modify: `src/football_edge/backtest/__main__.py` (yama aşağıda, `git apply` ile uygulanır)

**Interfaces:**
- Consumes: Task 2, Task 6 (`group_rows`, `summarise`, `Row`, bölgeler, `DixonColesStrategy`), Faz 2 CLI (`rating_groups`, `_log`).
- Produces: `ModelConfig`, `ModelConfigError`, `MODEL_CONFIG_PATH`, `load_model_config`, `dump_model_config`, `file_sha256`; `coordinate_descent`, `ELO_GRID`, `DC_GRID`, `elo_loss`, `dc_loss`, `select`, `active_from`; `development_groups`, `model_strategies`, `run_rows`, `gap_penalty`, `render_walkforward(..., gap=)`, `score_table`, `format_interval`; `rows_digest`; CLI `select`, `walkforward [--gap]`, `kinds_of`, `EXIT_CONFIG_MISMATCH = 11`, `DEFAULT_TAU`, `DEFAULT_SENSITIVITY`.

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_model_selection.py`:

<!-- plan: yeni tests/test_model_selection.py -->
```python
"""Seçim (S bölgesi), model yapılandırması ve `select`/`walkforward` CLI tutkalı (Faz 3 §5.2)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType

import pytest

from football_edge.backtest import __main__ as cli
from football_edge.backtest.model_config import (
    ModelConfig,
    ModelConfigError,
    dump_model_config,
    file_sha256,
    load_model_config,
)
from football_edge.backtest.selection import coordinate_descent, dc_loss, elo_loss
from football_edge.backtest.walkforward import DC, ELO
from football_edge.backtest.wf_eval import summarise
from football_edge.backtest.wf_run import (
    development_groups,
    gap_penalty,
    render_walkforward,
    rows_digest,
    run_rows,
)
from football_edge.history.catalog import MAIN, Catalog, HistoryLeague
from football_edge.history.lock import build_lock, dump_lock
from football_edge.market.devig import POWER
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModelConfig
from tests.model_builders import TEAMS, main_history

KINDS = MappingProxyType({"E0": MAIN})
GROUPS = MappingProxyType({"E0": "Ülke"})
HISTORY = {"E0": main_history(2011, 2020)}
CATALOG = Catalog(
    current_season="2627",
    leagues=(HistoryLeague("E0", "test.1", "Test", "Ülke", 1, MAIN, "1112", ""),),
)


@dataclass(frozen=True)
class Point:
    x: float = 0.0
    y: float = 0.0


def test_coordinate_descent_tries_each_parameter_once_in_order() -> None:
    grid = {"x": (-1.0, 2.0, 3.0), "y": (5.0, 1.0)}

    best, trace = coordinate_descent(Point(), grid, lambda p: (p.x - 2.0) ** 2 + (p.y - 1.0) ** 2)

    assert best == Point(2.0, 1.0)
    assert [dict(params) for params, _ in trace] == [
        {"x": 0.0, "y": 0.0},
        {"x": -1.0, "y": 0.0},
        {"x": 2.0, "y": 0.0},
        {"x": 3.0, "y": 0.0},
        {"x": 2.0, "y": 5.0},
        {"x": 2.0, "y": 1.0},
    ]


def test_coordinate_descent_keeps_the_first_of_equal_losses() -> None:
    best, _ = coordinate_descent(Point(), {"x": (1.0, 2.0)}, lambda p: 0.0)

    assert best == Point()


@pytest.mark.leakage
def test_selection_losses_read_only_the_selection_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    """S bölgesinin sonuçları değişince kayıp değişir; E bölgesininkiler değişince DEĞİŞMEZ."""
    groups = development_groups(HISTORY, GROUPS)
    base = elo_loss(groups, KINDS, GROUPS, EloModelConfig(), method=POWER)
    late = {
        "E0": tuple(
            replace(
                m,
                home_goals=m.away_goals,
                away_goals=m.home_goals,
                result={"H": "A", "A": "H", "D": "D"}[m.result],
            )
            if m.date >= date(2019, 7, 1)
            else m
            for m in HISTORY["E0"]
        )
    }

    assert (
        elo_loss(development_groups(late, GROUPS), KINDS, GROUPS, EloModelConfig(), method=POWER)
        == base
    )


def test_selection_losses_are_finite_and_the_draw_is_fitted() -> None:
    groups = development_groups(HISTORY, GROUPS)

    loss, draw = elo_loss(groups, KINDS, GROUPS, EloModelConfig(), method=POWER)
    dc = dc_loss(groups, KINDS, GROUPS, DCConfig(min_matches=40), cadence_days=7, method=POWER)

    assert 0.5 < loss < 1.2 and 0.0 <= draw <= 0.5
    assert 0.5 < dc < 1.2


def _config(tmp: Path) -> ModelConfig:
    return ModelConfig(
        selected_at="2026-10-01",
        catalog_sha256=file_sha256(tmp / "catalog.yaml"),
        lock_sha256=file_sha256(tmp / "lock.yaml"),
        method=POWER,
        elo=EloModelConfig(k=25.0, draw=0.28),
        dixon_coles=DCConfig(xi=0.001, min_matches=40),
        cadence_days=7,
        tau=0.02,
        sensitivity=(0.0, 0.05),
    )


def _files(tmp: Path) -> None:
    (tmp / "catalog.yaml").write_text("katalog\n", encoding="utf-8")
    (tmp / "lock.yaml").write_text(
        dump_lock(build_lock({}, locked_at=date(2026, 9, 22))), encoding="utf-8"
    )


def test_the_model_config_round_trips(tmp_path: Path) -> None:
    _files(tmp_path)
    path = tmp_path / "model.yaml"
    path.write_text(dump_model_config(_config(tmp_path)), encoding="utf-8")

    assert load_model_config(path) == _config(tmp_path)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda text: text.replace("version: 1", "version: 2"),
        lambda text: text.replace("method: power", "method: guess"),
        lambda text: text.replace("  k: 25.0\n", ""),
        lambda text: text.replace("margin: linear", "margin: square"),
        lambda text: text + "extra: 1\n",
        lambda text: "[",
    ],
    ids=["version", "method", "missing-field", "invalid-value", "extra-field", "broken-yaml"],
)
def test_a_bad_model_config_is_refused(tmp_path: Path, corrupt: object) -> None:
    _files(tmp_path)
    path = tmp_path / "model.yaml"
    path.write_text(corrupt(dump_model_config(_config(tmp_path))), encoding="utf-8")  # type: ignore[operator]

    with pytest.raises(ModelConfigError):
        load_model_config(path)


def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_catalog", lambda path: CATALOG)
    monkeypatch.setattr(cli, "connect", lambda: _Connection())
    monkeypatch.setattr(cli, "load_matches", lambda conn, catalog, *, lock=None, key=None: HISTORY)


class _Connection:
    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


@pytest.mark.leakage
def test_walkforward_refuses_a_changed_catalog_or_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _files(tmp_path)
    _patch(monkeypatch)
    config = tmp_path / "model.yaml"
    config.write_text(dump_model_config(_config(tmp_path)), encoding="utf-8")
    (tmp_path / "catalog.yaml").write_text("değişti\n", encoding="utf-8")

    code = cli.main(
        [
            "walkforward",
            "--config",
            str(config),
            "--catalog",
            str(tmp_path / "catalog.yaml"),
            "--lock",
            str(tmp_path / "lock.yaml"),
            "--out",
            str(tmp_path / "r.md"),
        ]
    )

    assert code == cli.EXIT_CONFIG_MISMATCH == 11
    assert not (tmp_path / "r.md").exists()
    assert any("katalog değişti" in message for message in caplog.messages)


def test_walkforward_writes_an_aggregate_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _files(tmp_path)
    _patch(monkeypatch)
    config = tmp_path / "model.yaml"
    config.write_text(dump_model_config(_config(tmp_path)), encoding="utf-8")

    code = cli.main(
        [
            "walkforward",
            "--config",
            str(config),
            "--catalog",
            str(tmp_path / "catalog.yaml"),
            "--lock",
            str(tmp_path / "lock.yaml"),
            "--out",
            str(tmp_path / "r.md"),
            "--resamples",
            "20",
        ]
    )

    report = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert code == 0
    assert "ΔLL harman − piyasa" in report and "holdout ve sonrası dönemi okunmadı" in report
    assert re.search(r"satır özeti sha256 `[0-9a-f]{64}`", report), "rapor tahmin özetini taşımıyor"
    assert not any(team in report for team in TEAMS)


def test_select_writes_a_loadable_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _files(tmp_path)
    _patch(monkeypatch)
    small = {"k": (20.0, 30.0)}
    monkeypatch.setattr("football_edge.backtest.selection.ELO_GRID", small)
    monkeypatch.setattr("football_edge.backtest.selection.DC_GRID", {"xi": (0.0019,)})
    caplog.set_level(logging.INFO)
    out = tmp_path / "model.yaml"

    code = cli.main(
        [
            "select",
            "--catalog",
            str(tmp_path / "catalog.yaml"),
            "--lock",
            str(tmp_path / "lock.yaml"),
            "--out",
            str(out),
            "--cadence-days",
            "7",
        ]
    )

    config = load_model_config(out)
    assert code == 0
    assert config.cadence_days == 7 and config.tau == 0.02
    assert config.lock_sha256 == file_sha256(tmp_path / "lock.yaml")
    assert sum("aday elo" in message for message in caplog.messages) == 2


def test_the_report_renderer_names_unmeasured_sections(tmp_path: Path) -> None:
    _files(tmp_path)
    rows = run_rows(development_groups(HISTORY, GROUPS), KINDS, GROUPS, _config(tmp_path))
    summary = summarise(rows, tau=0.02, sensitivity=(0.0,), resamples=20)

    text = render_walkforward(
        summary,
        _config(tmp_path),
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
        config_sha256="0" * 64,
    )

    assert "Ek ligler" in text and "ölçülemedi: satır yok" in text


def test_the_gap_penalty_rescores_the_same_matches_without_the_skipped_season(
    tmp_path: Path,
) -> None:
    """R128: 2022/23 girdiden çıkınca 2023/24'ün AYNI maçları başka olasılık alır; fark ölçülür."""
    _files(tmp_path)
    groups = development_groups({"E0": main_history(2019, 2023)}, GROUPS)

    gap = gap_penalty(groups, KINDS, GROUPS, _config(tmp_path), resamples=20)

    assert set(gap) == {ELO, DC}
    assert gap[ELO].estimate != 0.0 and gap[DC].estimate != 0.0
    text = render_walkforward(
        summarise(
            run_rows(groups, KINDS, GROUPS, _config(tmp_path)),
            tau=0.02,
            sensitivity=(),
            resamples=20,
        ),
        _config(tmp_path),
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
        config_sha256="0" * 64,
        gap=gap,
    )
    assert "Boşluk cezası (R128" in text


def test_the_rows_digest_is_stable_and_sees_a_changed_probability(tmp_path: Path) -> None:
    """m8 (tasarım §5.3): aynı satırlar → aynı özet; tek olasılık değişirse özet değişir."""
    _files(tmp_path)
    rows = run_rows(development_groups(HISTORY, GROUPS), KINDS, GROUPS, _config(tmp_path))
    first = rows[-1]
    changed = replace(
        first, components=MappingProxyType({**first.components, ELO: (0.5, 0.25, 0.25)})
    )

    assert rows_digest(rows) == rows_digest(tuple(reversed(rows)))
    assert rows_digest((*rows[:-1], changed)) != rows_digest(rows)
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_model_selection.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.backtest.model_config'`

- [ ] **Step 3: Uygulamayı yaz**

`src/football_edge/backtest/model_config.py`:

<!-- plan: yeni src/football_edge/backtest/model_config.py -->
```python
"""Dondurulmuş hiperparametreler (Faz 3 tasarımı §5.2, R129): `config/model_faz3.yaml`.

Dosyayı `select` yazar, controller commit'ler; walk-forward, ön kayıt ve `final_eval` yalnız bu
dosyayı okur. Katalog ve kilidin sha256'sı dosyadadır: ikisinden biri değişirse walk-forward
reddeder (§12/8 — katalog kilitte değil, ama modelin gördüğü katalog sabitlenir).
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from football_edge.market.devig import METHODS
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModelConfig

VERSION = 1
MODEL_CONFIG_PATH = Path("config/model_faz3.yaml")
_TOP = frozenset(
    {
        "version",
        "selected_at",
        "catalog_sha256",
        "lock_sha256",
        "method",
        "elo",
        "dixon_coles",
        "cadence_days",
        "tau",
        "sensitivity",
    }
)


class ModelConfigError(ValueError):
    """Model yapılandırması okunamadı ya da eksik/fazla alan taşıyor."""


@dataclass(frozen=True)
class ModelConfig:
    selected_at: str
    catalog_sha256: str
    lock_sha256: str
    method: str
    elo: EloModelConfig
    dixon_coles: DCConfig
    cadence_days: int
    tau: float
    sensitivity: tuple[float, ...]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump_model_config(config: ModelConfig) -> str:
    payload = {
        "version": VERSION,
        "selected_at": config.selected_at,
        "catalog_sha256": config.catalog_sha256,
        "lock_sha256": config.lock_sha256,
        "method": config.method,
        "elo": asdict(config.elo),
        "dixon_coles": asdict(config.dixon_coles),
        "cadence_days": config.cadence_days,
        "tau": config.tau,
        "sensitivity": list(config.sensitivity),
    }
    return yaml.safe_dump(payload, sort_keys=True, allow_unicode=True)


def _section(raw: dict[str, Any], name: str, fields: frozenset[str]) -> dict[str, Any]:
    section = raw.get(name)
    if not isinstance(section, dict) or set(section) != fields:
        raise ModelConfigError(f"{name}: alanlar {sorted(fields)} olmalı")
    return section


def load_model_config(path: Path) -> ModelConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ModelConfigError(f"{path}: okunamadı: {error}") from error
    if not isinstance(raw, dict) or set(raw) != _TOP:
        raise ModelConfigError(f"{path}: üst alanlar {sorted(_TOP)} olmalı")
    if raw["version"] != VERSION:
        raise ModelConfigError(f"{path}: sürüm {raw['version']!r}, beklenen {VERSION}")
    if raw["method"] not in METHODS:
        raise ModelConfigError(f"{path}: bilinmeyen vig yöntemi {raw['method']!r}")
    try:
        elo = EloModelConfig(**_section(raw, "elo", frozenset(asdict(EloModelConfig()))))
        dc = DCConfig(**_section(raw, "dixon_coles", frozenset(asdict(DCConfig()))))
        return ModelConfig(
            selected_at=str(raw["selected_at"]),
            catalog_sha256=str(raw["catalog_sha256"]),
            lock_sha256=str(raw["lock_sha256"]),
            method=str(raw["method"]),
            elo=elo,
            dixon_coles=dc,
            cadence_days=int(raw["cadence_days"]),
            tau=float(raw["tau"]),
            sensitivity=tuple(float(value) for value in raw["sensitivity"]),
        )
    except (TypeError, ValueError) as error:
        raise ModelConfigError(f"{path}: geçersiz değer: {error}") from error
```

`src/football_edge/backtest/selection.py`:

<!-- plan: yeni src/football_edge/backtest/selection.py -->
```python
"""Hiperparametre seçimi — yalnız S bölgesinde (Faz 3 tasarımı §5.2, §6.1–6.2; R129).

Koordinat inişi: iskele değerlerden başlanır, parametreler SABİT sırayla tek tek ızgarada denenir,
her birinde en düşük S log loss'u tutulur; tek tur. Elo'nun beraberlik payı `δ` her adayda S'nin
beklentileri üzerinde kapalı biçimde fit edilir (`fit_draw`). E ve holdout hiçbir adımda okunmaz.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from types import MappingProxyType
from typing import Any, TypeVar

from football_edge.backtest.harness import Strategy
from football_edge.backtest.walkforward import (
    DC,
    ELO,
    EXTRA_SELECTION,
    MAIN_SELECTION,
    SELECTION,
    Row,
    group_kind,
    group_rows,
)
from football_edge.history.catalog import MAIN
from football_edge.history.types import HistMatch
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import (
    LINEAR_MARGIN,
    LOG_MARGIN,
    NO_MARGIN,
    EloModel,
    EloModelConfig,
    elo_probs,
    expectation,
    fit_draw,
)
from football_edge.model.strategies import DixonColesStrategy

ELO_GRID: Mapping[str, tuple[Any, ...]] = MappingProxyType(
    {
        "k": (10.0, 15.0, 20.0, 25.0, 30.0),
        "home_advantage": (40.0, 65.0, 90.0),
        "margin": (NO_MARGIN, LINEAR_MARGIN, LOG_MARGIN),
        "regress": (0.0, 0.2, 0.4),
        "newcomer_offset": (0.0, 75.0, 150.0),
    }
)
DC_GRID: Mapping[str, tuple[Any, ...]] = MappingProxyType(
    {"xi": (0.0010, 0.0019, 0.0030), "ridge": (0.003, 0.01, 0.03)}
)
_LOG_FLOOR = 1e-15
Groups = Mapping[str, Sequence[HistMatch]]
T = TypeVar("T")


@dataclass(frozen=True)
class Trial:
    model: str
    params: Mapping[str, Any]
    log_loss: float


def coordinate_descent(
    start: T, grid: Mapping[str, tuple[Any, ...]], loss: Callable[[T], float]
) -> tuple[T, tuple[tuple[Mapping[str, Any], float], ...]]:
    """Tek tur; aynı aday iki kez ölçülmez. Eşitlikte önce denenen (ızgara sırası) kalır."""
    seen: dict[tuple[tuple[str, Any], ...], float] = {}
    trace: list[tuple[Mapping[str, Any], float]] = []

    def measure(candidate: T) -> float:
        key = tuple((name, getattr(candidate, name)) for name in grid)
        if key not in seen:
            seen[key] = loss(candidate)
            trace.append((MappingProxyType(dict(key)), seen[key]))
        return seen[key]

    best = start
    best_loss = measure(start)
    for name in grid:
        for value in grid[name]:
            candidate = replace(best, **{name: value})  # type: ignore[type-var]
            found = measure(candidate)
            if found < best_loss:
                best, best_loss = candidate, found
    return best, tuple(trace)


def _before_selection_end(
    matches: Sequence[HistMatch], kinds: Mapping[str, str]
) -> tuple[HistMatch, ...]:
    end = (MAIN_SELECTION if group_kind(matches, kinds) == MAIN else EXTRA_SELECTION).end
    return tuple(match for match in matches if match.date < end)


def active_from(matches: Sequence[HistMatch], kinds: Mapping[str, str]) -> date | None:
    window = MAIN_SELECTION if group_kind(matches, kinds) == MAIN else EXTRA_SELECTION
    return window.start


def _selection_rows(
    groups: Groups,
    kinds: Mapping[str, str],
    build: Callable[[Sequence[HistMatch]], Mapping[str, Strategy]],
    method: str,
) -> list[Row]:
    return [
        row
        for matches in groups.values()
        for row in group_rows(matches, kinds, build(matches), method=method)
        if row.zone == SELECTION
    ]


def elo_loss(
    groups: Groups,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: EloModelConfig,
    *,
    method: str,
) -> tuple[float, float]:
    """(S log loss'u, o adayda fit edilen δ)."""
    rows = [
        row
        for row in _selection_rows(
            groups, kinds, lambda _: {ELO: EloModel(config=config, groups=rating_groups)}, method
        )
        if ELO in row.components
    ]
    expectations = [expectation(row.components[ELO]) for row in rows]
    outcomes = [row.outcome for row in rows]
    draw = fit_draw(expectations, outcomes)
    loss = -math.fsum(
        math.log(max(elo_probs(e, draw)[o], _LOG_FLOOR))
        for e, o in zip(expectations, outcomes, strict=True)
    ) / len(rows)
    return loss, draw


def dc_loss(
    groups: Groups,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: DCConfig,
    *,
    cadence_days: int,
    method: str,
) -> float:
    def build(matches: Sequence[HistMatch]) -> Mapping[str, Strategy]:
        return {
            DC: DixonColesStrategy(
                config=config,
                groups=rating_groups,
                active_from=active_from(matches, kinds),
                cadence_days=cadence_days,
            )
        }

    rows = [row for row in _selection_rows(groups, kinds, build, method) if DC in row.components]
    return -math.fsum(
        math.log(max(row.components[DC][row.outcome], _LOG_FLOOR)) for row in rows
    ) / len(rows)


def select(
    groups: Groups,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    *,
    cadence_days: int,
    method: str,
) -> tuple[EloModelConfig, DCConfig, tuple[Trial, ...]]:
    # S satırlarının tahmini yalnız S'nin sonundan önceki sonuçlara bağlıdır: E'yi oynatmak boşa
    # (plan incelemesi m6 — DC her adayda E'yi de fit ederdi).
    groups = MappingProxyType(
        {name: _before_selection_end(matches, kinds) for name, matches in groups.items() if matches}
    )
    draws: dict[EloModelConfig, float] = {}

    def elo_objective(candidate: EloModelConfig) -> float:
        loss, draw = elo_loss(groups, kinds, rating_groups, candidate, method=method)
        draws[candidate] = draw
        return loss

    elo, elo_trace = coordinate_descent(EloModelConfig(), ELO_GRID, elo_objective)
    dc, dc_trace = coordinate_descent(
        DCConfig(),
        DC_GRID,
        lambda candidate: dc_loss(
            groups, kinds, rating_groups, candidate, cadence_days=cadence_days, method=method
        ),
    )
    trials = tuple(Trial("elo", params, loss) for params, loss in elo_trace) + tuple(
        Trial("dixon_coles", params, loss) for params, loss in dc_trace
    )
    return replace(elo, draw=draws[elo]), dc, trials
```

`src/football_edge/backtest/wf_run.py`:

<!-- plan: yeni src/football_edge/backtest/wf_run.py -->
```python
"""Walk-forward'u dondurulmuş yapılandırmayla koşturur ve raporlar (Faz 3 tasarımı §5.3).

Girdi `load_matches`in anahtarsız dönüşüdür (DEV + POST); burada yalnız DEV kalır — sonrası dönemi
spec §6.2'nin son ileri testidir ve hiçbir seçime girmez. Rapor yalnız toplu sayı taşır.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from types import MappingProxyType

from football_edge.backtest.harness import Strategy
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.selection import active_from
from football_edge.backtest.walkforward import (
    DC,
    DC_TOTALS,
    ELO,
    Row,
    group_matches,
    group_rows,
)
from football_edge.backtest.wf_eval import Score, Summary
from football_edge.history.holdout import DEV, Window, in_window, select_periods
from football_edge.history.types import TOTALS_25, HistMatch
from football_edge.market.metrics import Interval, bootstrap_mean, per_match_log_loss
from football_edge.model.elo_model import EloModel
from football_edge.model.strategies import DixonColesStrategy


def development_groups(
    leagues: Mapping[str, Sequence[HistMatch]], rating_groups: Mapping[str, str]
) -> Mapping[str, tuple[HistMatch, ...]]:
    development = {
        code: select_periods(matches, periods=frozenset({DEV})) for code, matches in leagues.items()
    }
    return group_matches(development, rating_groups)


def model_strategies(
    matches: Sequence[HistMatch],
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
) -> Mapping[str, Strategy]:
    """Elo, Dixon-Coles 1X2 ve Ü/A; iki DC aynı memo'yu paylaşır (aynı veri, aynı fit)."""
    h2h = DixonColesStrategy(
        config=config.dixon_coles,
        groups=rating_groups,
        active_from=active_from(matches, kinds),
        cadence_days=config.cadence_days,
    )
    return {
        ELO: EloModel(config=config.elo, groups=rating_groups),
        DC: h2h,
        DC_TOTALS: DixonColesStrategy(
            config=h2h.config,
            groups=rating_groups,
            market=TOTALS_25,
            active_from=h2h.active_from,
            cadence_days=h2h.cadence_days,
            memo=h2h.memo,
        ),
    }


def run_rows(
    groups: Mapping[str, Sequence[HistMatch]],
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
) -> tuple[Row, ...]:
    return tuple(
        row
        for matches in groups.values()
        for row in group_rows(
            matches,
            kinds,
            model_strategies(matches, kinds, rating_groups, config),
            method=config.method,
        )
    )


# R128 boşluk cezası (DEV simülasyonu): E'nin bir sezonu girdiden çıkarılır, sonraki sezon iki
# koşuda aynı maçlarda ölçülür. Canlı ve anahtarsız yollar holdout yılını böyle atlar.
GAP_SKIPPED = Window(date(2022, 7, 1), date(2023, 7, 1))
GAP_MEASURED = Window(date(2023, 7, 1), date(2024, 7, 1))


def gap_penalty(
    groups: Mapping[str, Sequence[HistMatch]],
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
    *,
    resamples: int,
    skipped: Window = GAP_SKIPPED,
    measured: Window = GAP_MEASURED,
) -> Mapping[str, Interval]:
    """Bileşen → ölçülen sezonda maç başına LL(boşluklu) − LL(tam), eşleşen satırlarda."""
    full = run_rows(groups, kinds, rating_groups, config)
    cut = {name: tuple(m for m in ms if not in_window(m, skipped)) for name, ms in groups.items()}
    gapped = {row.key: row for row in run_rows(cut, kinds, rating_groups, config)}
    found: dict[str, Interval] = {}
    for name in (ELO, DC):
        pairs = [
            (row, gapped[row.key])
            for row in full
            if measured.start is not None
            and measured.start <= row.key.date < measured.end
            and row.key in gapped
            and name in row.components
            and name in gapped[row.key].components
        ]
        if not pairs:
            continue
        outcomes = [row.outcome for row, _ in pairs]
        before = per_match_log_loss([row.components[name] for row, _ in pairs], outcomes)
        after = per_match_log_loss([other.components[name] for _, other in pairs], outcomes)
        found[name] = bootstrap_mean(
            [b - a for a, b in zip(before, after, strict=True)], resamples=resamples
        )
    return MappingProxyType(found)


def rows_digest(rows: Sequence[Row]) -> str:
    """Satırların (anahtar, bölge, bileşen olasılıkları 1e-9'a yuvarlı) sha256'sı — tasarım §5.3."""
    lines = (
        f"{row.key}|{row.zone}|"
        + ",".join(f"{p:.9f}" for name in sorted(row.components) for p in row.components[name])
        for row in sorted(rows, key=lambda r: (r.key, r.zone))
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def format_interval(interval: Interval | None) -> str:
    if interval is None:
        return "ölçülemedi"
    return f"{interval.estimate:.4f} [{interval.low:.4f}, {interval.high:.4f}]"


def _score_line(score: Score) -> str:
    calibration = (
        "ölçülemedi"
        if score.calibration is None
        else f"b={score.calibration.slope:.3f} ECE={score.calibration.ece:.4f}"
    )
    rps = "—" if score.rps is None else f"{score.rps:.4f}"
    loss = format_interval(score.log_loss)
    return (
        f"| {score.name} | {score.n} | {loss} | {score.brier:.4f} | {rps} | "
        f"{calibration} | {format_interval(score.clv)} | {score.bets} |"
    )


def score_table(title: str, scores: Mapping[str, Score]) -> list[str]:
    if not scores:
        return [f"### {title}", "", "ölçülemedi: satır yok", ""]
    return [
        f"### {title}",
        "",
        "| strateji | n | log loss [%95] | Brier | RPS | kalibrasyon | CLV [%95] | bahis |",
        "|---|---|---|---|---|---|---|---|",
        *(_score_line(score) for score in scores.values()),
        "",
    ]


def render_walkforward(
    summary: Summary,
    config: ModelConfig,
    *,
    generated_at: datetime,
    config_sha256: str,
    gap: Mapping[str, Interval] | None = None,
    digest: str | None = None,
) -> str:
    lines = [
        f"# Faz 3 walk-forward raporu — {generated_at.date().isoformat()}",
        "",
        f"Üretim: {generated_at.isoformat()} · `config/model_faz3.yaml` sha256 `{config_sha256}` · "
        f"vig `{config.method}` · τ = {config.tau} · satır özeti sha256 `{digest or 'yok'}`. "
        "Yalnız geliştirme dönemi (E bölgesi); "
        "holdout ve sonrası dönemi okunmadı. Toplu sayılar; maç satırı yok.",
        "",
        f"E satırı {summary.rows} · bileşeni eksik (ortak kümeye girmedi) {summary.incomplete} · "
        f"geri düşülen ağırlık katı {len(summary.fallback)}",
        "",
        *score_table("Ana ligler, 1X2 (ortak satırlar)", summary.main),
        f"ΔLL harman − piyasa: {format_interval(summary.blend_gap)}",
        "",
        "| lig | ΔLL harman − piyasa [%95] |",
        "|---|---|",
        *(f"| {league} | {format_interval(gap)} |" for league, gap in summary.league_gaps.items()),
        "",
        *score_table("Ek ligler, 1X2 (yalnız model; kapanış kıyas)", summary.extra),
        *score_table("Ana ligler, Ü/A 2.5 (ikincil)", summary.totals),
        "### CLV duyarlılığı (harman)",
        "",
        *(
            f"- τ = {tau}: {format_interval(interval)}"
            for tau, interval in summary.clv_sensitivity.items()
        ),
        "",
    ]
    if gap is not None:
        lines += [
            "### Boşluk cezası (R128, DEV simülasyonu)",
            "",
            f"{GAP_SKIPPED.start}–{GAP_SKIPPED.end} sezonu girdiden çıkarıldı; "
            f"{GAP_MEASURED.start}–{GAP_MEASURED.end} maçlarında LL(boşluklu) − LL(tam):",
            "",
            *(f"- {name}: {format_interval(interval)}" for name, interval in gap.items()),
            "",
        ]
    return "\n".join(lines)
```

`src/football_edge/backtest/__main__.py` yaması:

<!-- plan: yama src/football_edge/backtest/__main__.py -->
```diff
--- a/src/football_edge/backtest/__main__.py
+++ b/src/football_edge/backtest/__main__.py
@@ -1,4 +1,8 @@
-"""`python -m football_edge.backtest selftest` — kilitli geliştirme verisinde bilinen sonuçlar.
+"""`python -m football_edge.backtest {selftest,select,walkforward}` — kilitli geliştirme verisinde.
+
+`selftest`: bilinen sonuçlar. `select`: S bölgesinde hiperparametre seçimi →
+`config/model_faz3.yaml` (controller commit'ler). `walkforward`: dondurulmuş yapılandırmayla E
+bölgesi raporu.
 
 Önce kilit: kilit dosyası bozuksa ya da önbellek kilitli dönemlerin özetinden farklıysa hiçbir
 ölçüm koşmaz (exit 9). Sonra her denetim adıyla loglanır; kapı denetimlerinden biri kırmızıysa
@@ -9,17 +13,36 @@
 
 import argparse
 import logging
-from collections.abc import Mapping
+from collections.abc import Callable, Mapping, Sequence
+from datetime import UTC, datetime
 from pathlib import Path
 from types import MappingProxyType
 
 from football_edge.backtest.evaluate import DEFAULT_RESAMPLES
+from football_edge.backtest.model_config import (
+    MODEL_CONFIG_PATH,
+    ModelConfig,
+    ModelConfigError,
+    dump_model_config,
+    file_sha256,
+    load_model_config,
+)
+from football_edge.backtest.selection import select
 from football_edge.backtest.selftest import Check, run_selftest
+from football_edge.backtest.wf_eval import summarise
+from football_edge.backtest.wf_run import (
+    development_groups,
+    gap_penalty,
+    render_walkforward,
+    rows_digest,
+    run_rows,
+)
 from football_edge.collect import configure_logging
 from football_edge.db import connect
 from football_edge.history.catalog import MAIN, Catalog, load_catalog
 from football_edge.history.lock import LockViolation, load_lock
 from football_edge.history.sync import load_matches
+from football_edge.history.types import HistMatch
 from football_edge.market.devig import DEFAULT_METHOD, METHODS
 
 LOGGER = logging.getLogger("football_edge.backtest")
@@ -29,6 +52,11 @@
 EXIT_GATE_FAILED = 1
 # collect.EXIT_* (2–8) ile çakışmaz; history.yml'deki selftest adımı bu kodu adıyla karşılar.
 EXIT_LOCK_VIOLATION = 9
+# 10 köprünün (`market bridge`) "eşleşme yok"u; 11: model yapılandırması okunamadı ya da
+# katalog/kilit yapılandırmadaki özetle uyuşmuyor — walk-forward koşmaz.
+EXIT_CONFIG_MISMATCH = 11
+DEFAULT_TAU = 0.02  # R139
+DEFAULT_SENSITIVITY = (0.0, 0.05)
 
 
 def _parser() -> argparse.ArgumentParser:
@@ -39,6 +67,19 @@
     selftest.add_argument("--catalog", type=Path, default=CATALOG_PATH)
     selftest.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
     selftest.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
+    chooser = commands.add_parser("select", help="S bölgesinde hiperparametre seçimi")
+    chooser.add_argument("--lock", type=Path, default=LOCK_PATH)
+    chooser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
+    chooser.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
+    chooser.add_argument("--cadence-days", type=int, default=1)
+    chooser.add_argument("--out", type=Path, default=MODEL_CONFIG_PATH)
+    walk = commands.add_parser("walkforward", help="E bölgesi raporu (dondurulmuş yapılandırma)")
+    walk.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
+    walk.add_argument("--lock", type=Path, default=LOCK_PATH)
+    walk.add_argument("--catalog", type=Path, default=CATALOG_PATH)
+    walk.add_argument("--out", type=Path, required=True)
+    walk.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
+    walk.add_argument("--gap", action="store_true", help="R128 boşluk cezası (iki ek koşu)")
     return parser
 
 
@@ -79,9 +120,113 @@
     return 0
 
 
+def kinds_of(catalog: Catalog) -> Mapping[str, str]:
+    return MappingProxyType({league.code: league.kind for league in catalog.leagues})
+
+
+def _locked_matches(
+    catalog_path: Path, lock_path: Path
+) -> tuple[Catalog, Mapping[str, Sequence[HistMatch]]] | None:
+    catalog = load_catalog(catalog_path)
+    try:
+        lock = load_lock(lock_path)
+        with connect() as conn:
+            return catalog, load_matches(conn, catalog, lock=lock)
+    except LockViolation as error:
+        LOGGER.error("kilit ihlali — koşulmadı: %s", "; ".join(error.differences))
+        return None
+
+
+def _select(args: argparse.Namespace) -> int:
+    loaded = _locked_matches(args.catalog, args.lock)
+    if loaded is None:
+        return EXIT_LOCK_VIOLATION
+    catalog, matches = loaded
+    groups = rating_groups(catalog)
+    elo, dc, trials = select(
+        development_groups(matches, groups),
+        kinds_of(catalog),
+        groups,
+        cadence_days=args.cadence_days,
+        method=args.method,
+    )
+    for trial in trials:
+        LOGGER.info("aday %s %s → S log loss %.6f", trial.model, dict(trial.params), trial.log_loss)
+    config = ModelConfig(
+        selected_at=datetime.now(UTC).date().isoformat(),
+        catalog_sha256=file_sha256(args.catalog),
+        lock_sha256=file_sha256(args.lock),
+        method=args.method,
+        elo=elo,
+        dixon_coles=dc,
+        cadence_days=args.cadence_days,
+        tau=DEFAULT_TAU,
+        sensitivity=DEFAULT_SENSITIVITY,
+    )
+    args.out.write_text(dump_model_config(config), encoding="utf-8")
+    LOGGER.info("yazıldı: %s (%d aday)", args.out, len(trials))
+    return 0
+
+
+def _checked_config(args: argparse.Namespace) -> ModelConfig | None:
+    try:
+        config = load_model_config(args.config)
+    except ModelConfigError as error:
+        LOGGER.error("model yapılandırması: %s", error)
+        return None
+    for name, expected, path in (
+        ("katalog", config.catalog_sha256, args.catalog),
+        ("kilit", config.lock_sha256, args.lock),
+    ):
+        if file_sha256(path) != expected:
+            LOGGER.error("%s değişti: %s yapılandırmadaki özetle uyuşmuyor", name, path)
+            return None
+    return config
+
+
+def _walkforward(args: argparse.Namespace) -> int:
+    config = _checked_config(args)
+    if config is None:
+        return EXIT_CONFIG_MISMATCH
+    loaded = _locked_matches(args.catalog, args.lock)
+    if loaded is None:
+        return EXIT_LOCK_VIOLATION
+    catalog, matches = loaded
+    groups = rating_groups(catalog)
+    development = development_groups(matches, groups)
+    rows = run_rows(development, kinds_of(catalog), groups, config)
+    summary = summarise(
+        rows, tau=config.tau, sensitivity=config.sensitivity, resamples=args.resamples
+    )
+    gap = (
+        gap_penalty(development, kinds_of(catalog), groups, config, resamples=args.resamples)
+        if args.gap
+        else None
+    )
+    args.out.write_text(
+        render_walkforward(
+            summary,
+            config,
+            generated_at=datetime.now(UTC),
+            config_sha256=file_sha256(args.config),
+            gap=gap,
+            digest=rows_digest(rows),
+        ),
+        encoding="utf-8",
+    )
+    LOGGER.info("walk-forward raporu yazıldı: %s (E satırı %d)", args.out, summary.rows)
+    return 0
+
+
+COMMANDS: Mapping[str, Callable[[argparse.Namespace], int]] = MappingProxyType(
+    {"selftest": _selftest, "select": _select, "walkforward": _walkforward}
+)
+
+
 def main(argv: list[str] | None = None) -> int:
     configure_logging()
-    return _selftest(_parser().parse_args(argv))
+    args = _parser().parse_args(argv)
+    return COMMANDS[args.command](args)
 
 
 if __name__ == "__main__":
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_model_selection.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — 17 passed; `tests/test_backtest_cli.py` (Faz 2) değişmeden yeşil

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `_selection_rows`: `row.zone == SELECTION` → `row.zone != ""` (E sızar) | `tests/test_model_selection.py::test_selection_losses_read_only_the_selection_zone` |
| 2 | `_checked_config`: özet karşılaştırması `if False:` | `tests/test_model_selection.py::test_walkforward_refuses_a_changed_catalog_or_lock` |
| 3 | `gap_penalty`: atlanan sezon girdiden çıkarılmaz (`tuple(ms)`) | `tests/test_model_selection.py::test_the_gap_penalty_rescores_the_same_matches_without_the_skipped_season` |
| 4 | `rows_digest`: olasılıklar özete girmez (inceleme m8) | `tests/test_model_selection.py::test_the_rows_digest_is_stable_and_sees_a_changed_probability` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add src/football_edge/backtest/model_config.py \
  src/football_edge/backtest/selection.py \
  src/football_edge/backtest/wf_run.py \
  src/football_edge/backtest/__main__.py \
  tests/test_model_selection.py
git commit -m "feat: Faz 3 P1 — S bölgesinde seçim, dondurulmuş model yapılandırması, select/walkforward CLI

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
### Task 8: Canlı bağlam kurucusu + eşitlik testi E1–E2 (P2b)

**Kademe:** K1 · **Dalga:** 3 · **Worktree/dal:** `.worktrees/wt-live` · `feat/faz3-live`

> **İz A'ya bağlı (canlı kapsam):** İz A birleşti (`a398c31`): 8 aktif lig (ned.1, bel.1 dahil; aut.1 kapalı). Katalogda ned.1 → N1, bel.1 → B1 eşlemesi hazır; yeni liglerin takma adları (`config/history_aliases.yaml`) ilk canlı kapanışlardan sonra İz A'nın 5. adımıyla girer. Testler SENTETİK lig kimliği (`t.1`) kullanır ve `config/leagues.yaml`a bağlı değildir; gerçek eşleşme dalga 4 sonundaki E3 raporunda ölçülür.

Tasarım §7.2–7.4, R132, R133. Defterin maç ve snapshot satırları `MatchRecord`a çevrilir: lig `history_leagues.yaml`'ın `league_id`sinden, tarih Londra tarihi, adlar takma ad → normalize eşitliği, fiyat karar anında ya da önce gözlenen SON snapshot turunun tam kitap ortalaması. `observe` akışı harness'ın olay düzeniyle (bilinme anı, gruptaki sıra) aynı fonksiyondan; gerçek varış anı kullanılmaz. Bayat durum koruması iki katmanlı: (a) grubun defterde fikstürü olan ligleri için son 10 günde bitmiş sayılan bir canlı maç tabanda yoksa tahmin YOK; (b) R141 (inceleme I1): defterde fikstürü OLMAYAN grup ligleri (E1–E3, D2, I2, SP2, F2 …) için football-data'nın kendi tarihleri — ligin son sonucu geçen yılın olağan maç günü aralığından (%95'lik + 1 gün) eskiyse lig geride, karar bayattır; 21 günü aşan ara yargılanmaz. E1 bir sezonun BÜTÜN maçlarında (2026-10-25 yaz saati geçişi ve gece yarısı maçı dahil) bağlamın `match_index` dışındaki bütün alanlarını ve akışı birebir karşılaştırır; E2 aynı stratejinin iki kurucudan aynı tahmini verdiğini.

**Files:**
- Create: `src/football_edge/live/context.py`
- Create: `src/football_edge/live/store.py`
- Create: `tests/test_context_parity.py`

**Interfaces:**
- Consumes: Task 4 (`MatchRecord`, `context_of`, `record_of`, `result_of`), Task 6 (`group_matches`, `tests/model_builders.py`, `DixonColesStrategy`), Task 2, Faz 2 (`timeline`, `normalise_team`).
- Produces: `LiveMatch`, `Quote`, `Naming`, `LiveDecision`, `LiveBatch`, `naming_from`, `canonical`, `live_key`, `season_of`, `pre_prices`, `observe_stream`, `is_stale`, `league_lagging`, `lagging_leagues`, `build_batch`, `LIVE_H2H`, `REFERENCE_BOOK`, `IN_SEASON_GAP`; `load_live_matches`, `load_quotes`.

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_context_parity.py`:

<!-- plan: yeni tests/test_context_parity.py -->
```python
"""Canlı ↔ tarihsel eşitlik (Faz 3 tasarımı §7.4 E1–E2, R98): aynı maç için iki kurucu aynı
`DecisionContext`i ve aynı `observe` akışını üretir. Veri SENTETİK; canlı taraf aynı maçı defter
satırı biçiminde taşır (The Odds API adları, kitap başına fiyat, birden çok snapshot turu)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.backtest.harness import DecisionContext, Prediction, ResultRecord, replay
from football_edge.backtest.timeline import decision_at
from football_edge.backtest.walkforward import group_matches
from football_edge.history.catalog import EXTRA, MAIN
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, HistMatch
from football_edge.live.context import (
    LiveMatch,
    Quote,
    build_batch,
    canonical,
    league_lagging,
    naming_from,
    observe_stream,
    pre_prices,
    season_of,
)
from football_edge.live.store import load_live_matches, load_quotes
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModel
from football_edge.model.strategies import DixonColesStrategy
from tests.backtest_builders import hist_match, quote
from tests.model_builders import season

LEAGUE_ID = "tst.1"
GROUPS = MappingProxyType({"E0": "Ülke"})
KINDS = MappingProxyType({"E0": MAIN})
ALIASES = MappingProxyType({"Alfa FC": "Alfa", "Birinci Takım": "Beta"})
# Cumartesi 23:30 UTC (BST): Londra'da pazar 00:30 — football-data'nın Date'i pazar.
LATE = hist_match(
    day=date(2026, 9, 13),
    kickoff=datetime(2026, 9, 12, 23, 30, tzinfo=UTC),
    season="2627",
    home="Gece",
    away="Yarasa",
    odds=quote("Avg", PRE_CLOSING, (2.4, 3.3, 3.1)),
    line=999,
)
# Cuma 08:00 UTC başlama: sonucu 11:00 UTC'de, cumartesi maçlarının karar anında TAM bilinir —
# harness eşzamanlılıkta kararı önce koyar; canlı akış onu da dışarıda bırakmalı (m1).
EARLY = hist_match(
    day=date(2026, 9, 11),
    kickoff=datetime(2026, 9, 11, 8, tzinfo=UTC),
    season="2627",
    home="Sabah",
    away="Erken",
    odds=quote("Avg", PRE_CLOSING, (2.2, 3.4, 3.3)),
    line=998,
)
HISTORY = (
    *season("2526", date(2025, 8, 2), seed=4),
    *season("2627", date(2026, 8, 1), seed=5),
    LATE,
    EARLY,
)
GROUP = group_matches({"E0": HISTORY}, GROUPS)["Ülke"]
NAMING = naming_from({"E0": HISTORY}, {LEAGUE_ID: "E0"}, ALIASES)


def _live_name(name: str) -> str:
    return "Alfa FC" if name == "Alfa" else name.upper()  # normalize eşitliği + takma ad


def _live(match: HistMatch) -> LiveMatch:
    assert match.kickoff is not None
    return LiveMatch(
        f"id-{match.source_line}",
        LEAGUE_ID,
        match.kickoff,
        _live_name(match.home),
        _live_name(match.away),
    )


def _quotes(match: HistMatch, live: LiveMatch) -> list[Quote]:
    """Karar anında TAM olarak gözlenen tur (iki tam kitap = Avg, bir eksik kitap), ondan önce iki
    farklı fiyatlı tur ve karar SONRASI bir tur (I3: `≤` → `<` kırmızı olsun)."""
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None
    prices = match.prices("Avg", H2H, PRE_CLOSING)
    assert prices is not None
    names = (live.home, "Draw", live.away)
    found: list[Quote] = []
    for at, book, values in (
        (decided - timedelta(days=1), "eski", (9.0, 9.0, 9.0)),
        (decided - timedelta(hours=5), "önce", (8.0, 8.0, 8.0)),
        (decided, "b1", prices),
        (decided, "b2", prices),
        (decided + timedelta(hours=1), "sonra", (1.5, 5.0, 7.0)),
    ):
        found.extend(
            Quote(live.match_id, at, book, "h2h", name, value)
            for name, value in zip(names, values, strict=True)
        )
    found.append(Quote(live.match_id, decided, "eksik", "h2h", live.home, 1.01))
    return found


@dataclass(frozen=True)
class Recorder:
    """Her kararda gördüğü bağlamı ve o ana dek gözlediği sonuçları ortak sözlüklere yazar."""

    contexts: dict[int, DecisionContext]
    streams: dict[int, tuple[ResultRecord, ...]]
    seen: tuple[ResultRecord, ...] = ()

    @property
    def name(self) -> str:
        return "recorder"

    def observe(self, result: ResultRecord) -> Recorder:
        return replace(self, seen=(*self.seen, result))

    def predict(self, context: DecisionContext) -> Prediction | None:
        self.contexts[context.match_index] = context
        self.streams[context.match_index] = self.seen
        return None


@pytest.fixture(scope="module")
def historical() -> Recorder:
    recorder = Recorder(contexts={}, streams={})
    replay(GROUP, recorder)
    return recorder


def _targets() -> list[int]:
    """2026/27'nin kararı olan bütün maçları (yaz saati bitişi 2026-10-25, gece maçı dahil)."""
    return [
        index
        for index, match in enumerate(GROUP)
        if match.season == "2627" and decision_at(match.date, match.kickoff) is not None
    ]


def _batch(match: HistMatch, *, extra_live: tuple[LiveMatch, ...] = ()) -> Any:
    live = _live(match)
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None
    return build_batch(
        (live, *extra_live),
        _quotes(match, live),
        {"Ülke": GROUP},
        now=decided + timedelta(minutes=30),
        naming=NAMING,
        kinds=KINDS,
        rating_groups=GROUPS,
    )


@pytest.mark.leakage
def test_the_live_builder_reproduces_the_historical_context_and_stream(
    historical: Recorder,
) -> None:
    """E1: bağlamın `match_index` dışındaki BÜTÜN alanları ve `observe` akışı birebir."""
    targets = _targets()
    assert len(targets) > 50 and GROUP.index(LATE) in targets

    for index in targets:
        batch = _batch(GROUP[index])
        (decision,) = batch.decisions
        assert replace(decision.context, match_index=index) == historical.contexts[index]
        assert decision.results == historical.streams[index]


@pytest.mark.leakage
def test_the_same_strategy_predicts_the_same_from_both_builders() -> None:
    """E2: Elo ve Dixon-Coles'a iki kurucudan gelen girdi aynı tahmini verir."""
    index = _targets()[40]
    strategies = (EloModel(), DixonColesStrategy(config=DCConfig(min_matches=40)))
    for strategy in strategies:
        replayed = {p.match_index: p.probs for p in replay(GROUP, strategy).predictions}
        (decision,) = _batch(GROUP[index]).decisions
        state = strategy
        for result in decision.results:
            state = state.observe(result)  # type: ignore[assignment]
        live = state.predict(replace(decision.context, match_index=index))
        assert live is not None and live.probs == pytest.approx(replayed[index])


def test_snapshots_after_the_decision_and_incomplete_books_are_ignored() -> None:
    match = GROUP[_targets()[3]]
    live = _live(match)
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None

    found = pre_prices(_quotes(match, live), live, decided)

    assert found is not None
    assert tuple(
        found[key] for key in sorted(found, key=lambda k: RESULTS.index(k.outcome))
    ) == match.prices("Avg", H2H, PRE_CLOSING)
    assert pre_prices(_quotes(match, live), live, decided - timedelta(days=2)) is None


def test_a_live_night_kickoff_takes_the_london_date() -> None:
    (decision,) = _batch(LATE).decisions

    assert decision.record.key.date == date(2026, 9, 13)


def test_names_map_through_aliases_then_normalisation() -> None:
    assert canonical(NAMING, "E0", "Alfa FC") == "Alfa"
    assert canonical(NAMING, "E0", "Birinci Takım") == "Beta"  # yalnız takma adla bulunur
    assert canonical(NAMING, "E0", "BETA") == "Beta"
    assert canonical(NAMING, "E0", "Bilinmez") is None


def test_an_unmapped_match_gets_no_context() -> None:
    match = GROUP[_targets()[2]]
    stranger = replace(_live(match), match_id="yabancı", home="Bilinmez")
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None

    batch = build_batch(
        (stranger,),
        [],
        {"Ülke": GROUP},
        now=decided,
        naming=NAMING,
        kinds=KINDS,
        rating_groups=GROUPS,
    )

    assert batch.unmapped == ("yabancı",) and batch.decisions == ()


def test_a_group_result_missing_from_the_base_makes_the_state_stale() -> None:
    """R132: tarihsel kural sonucu bilinir sayıyor, tabanda yok → tahmin yok, adıyla sayılır."""
    match = GROUP[_targets()[30]]
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None
    missing = LiveMatch("kayıp", LEAGUE_ID, decided - timedelta(days=2), "ZETA", "ETA")

    batch = _batch(match, extra_live=(missing,))

    assert batch.decisions == () and batch.stale == (_live(match).match_id,)


def test_a_match_without_a_pre_decision_quote_is_counted() -> None:
    match = GROUP[_targets()[5]]
    live = _live(match)
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None

    batch = build_batch(
        (live,), [], {"Ülke": GROUP}, now=decided, naming=NAMING, kinds=KINDS, rating_groups=GROUPS
    )

    assert batch.no_quote == (live.match_id,)


def test_matches_not_yet_decided_or_already_started_are_skipped() -> None:
    match = GROUP[_targets()[5]]
    live = _live(match)
    decided = decision_at(match.date, match.kickoff)
    assert decided is not None and match.kickoff is not None

    for now in (decided - timedelta(minutes=1), match.kickoff):
        batch = build_batch(
            (live,),
            _quotes(match, live),
            {"Ülke": GROUP},
            now=now,
            naming=NAMING,
            kinds=KINDS,
            rating_groups=GROUPS,
        )
        assert batch.decisions == ()


def test_season_codes() -> None:
    extra = (hist_match(day=date(2026, 3, 1), league="BRA", season="2026"),)

    assert season_of((), date(2026, 9, 1), MAIN) == "2627"
    assert season_of((), date(2027, 3, 1), MAIN) == "2627"
    assert season_of(extra, date(2026, 9, 1), EXTRA) == "2026"
    assert season_of(extra, date(2026, 2, 1), EXTRA) is None


def test_the_stream_is_ordered_like_the_harness_events() -> None:
    decided = datetime.combine(date(2026, 10, 2), time(11), tzinfo=UTC)

    stream = observe_stream(GROUP, decided)

    assert [r.known_at for r in stream] == sorted(r.known_at for r in stream)
    assert all(r.known_at < decided for r in stream)


class _Cursor:
    def __init__(self, rows: list[tuple[Any, ...]], log: list[tuple[str, tuple[Any, ...]]]) -> None:
        self.rows, self.log = rows, log

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.log.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


class _Connection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows, self.log = rows, []  # type: ignore[var-annotated]

    def cursor(self) -> _Cursor:
        return _Cursor(self.rows, self.log)


def test_the_store_reads_matches_and_numeric_prices() -> None:
    at = datetime(2026, 9, 5, 6, 22, tzinfo=UTC)
    matches = _Connection([("m1", LEAGUE_ID, at, "Alfa FC", "BETA")])
    quotes = _Connection([("m1", at, "b1", "h2h", "Draw", Decimal("3.40"))])

    (live,) = load_live_matches(matches, since=at, until=at + timedelta(days=7))  # type: ignore[arg-type]
    (found,) = load_quotes(quotes, ("m1",), until=at)  # type: ignore[arg-type]

    assert live == LiveMatch("m1", LEAGUE_ID, at, "Alfa FC", "BETA")
    assert found.price == 3.4 and isinstance(found.price, float)
    assert quotes.log[0][1] == (["m1"], "h2h", at)
    assert load_quotes(_Connection([]), (), until=at) == ()  # type: ignore[arg-type]


def test_a_group_league_without_ledger_fixtures_that_falls_behind_makes_the_state_stale() -> None:
    """R141 (plan incelemesi I1): E1'in defterde fikstürü yok; football-data'daki son sonucu,
    lig haftalık oynarken 13 gün eskiyse E0 kararı bayattır; 21 günü aşan ara yargılanmaz."""
    second = (
        *season("2526", date(2025, 8, 2), league="E1", seed=6),
        *season("2627", date(2026, 8, 1), league="E1", seed=7, rounds=6),  # son sonuç 2026-09-05
    )
    groups = MappingProxyType({"E0": "Ülke", "E1": "Ülke"})
    group = group_matches({"E0": HISTORY, "E1": second}, groups)["Ülke"]
    naming = naming_from({"E0": HISTORY, "E1": second}, {LEAGUE_ID: "E0"}, ALIASES)

    def batch(day: date) -> Any:
        match = next(m for m in HISTORY if m.date == day)
        live = _live(match)
        decided = decision_at(match.date, match.kickoff)
        assert decided is not None
        return build_batch(
            (live,),
            _quotes(match, live),
            {"Ülke": group},
            now=decided + timedelta(minutes=30),
            naming=naming,
            kinds=KINDS,
            rating_groups=groups,
        )

    assert len(batch(date(2026, 9, 12)).decisions) == 1  # E1'in son sonucu 6 gün önce: olağan
    assert batch(date(2026, 9, 19)).stale  # 13 gün: E1 geride
    assert len(batch(date(2026, 10, 3)).decisions) == 1  # 27 gün: ara, yargılanmaz


@pytest.mark.parametrize(
    ("gap", "lagging"), [(6, False), (8, False), (9, True), (21, True), (22, False)]
)
def test_a_weekly_league_lags_after_its_usual_gap_plus_one_day(gap: int, lagging: bool) -> None:
    last = date(2026, 9, 5)
    weekly = [last - timedelta(weeks=week) for week in range(20)]

    assert league_lagging(weekly, last + timedelta(days=gap)) is lagging
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_context_parity.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.live.context'`

- [ ] **Step 3: Uygulamayı yaz**

`src/football_edge/live/context.py`:

<!-- plan: yeni src/football_edge/live/context.py -->
```python
"""Canlı bağlam kurucusu (Faz 3 tasarımı §7.2–7.3; R128, R132, R133).

Kaynak: defterdeki maç ve snapshot satırları (`live/store.py`) + tarihsel tabanın anahtarsız
dönüşü (DEV + POST — R128: holdout yılı canlıda da yoktur). Son adım tarihsel kurucuyla ORTAKTIR
(`backtest/context.py`): canlı kurucu yalnız kaynağı `MatchRecord`a çevirir. Karar ve sonuç anları
`timeline`ın kuralıyla hesaplanır; gerçek varış anı KULLANILMAZ. Tarihsel kuralın "bilinir" saydığı
bir sonuç tabanda yoksa maç için bağlam kurulmaz (bayat durum). Defterde fikstürü olan ligde bu
kesindir; defterde olmayan grup liglerinde (E1–E3 …) football-data'nın tarih yoğunluğundan
sezgiseldir (R141) — orada gecikme erken fark edilmezse akış tarihsel akıştan ayrışabilir.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import MappingProxyType

from football_edge.backtest.context import MatchRecord, context_of, record_of, result_of
from football_edge.backtest.records import DecisionContext, MatchKey, ResultRecord
from football_edge.backtest.timeline import LONDON, RESULT_LAG, decision_at, result_known_at
from football_edge.history.catalog import MAIN
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, HistMatch, OddsKey
from football_edge.naming import normalise_team

LIVE_H2H = "h2h"
LIVE_DRAW = "Draw"
REFERENCE_BOOK = "Avg"  # canlı kitap ortalaması, football-data'nın `Avg`'sinin yapısal karşılığı
STALE_LOOKBACK = timedelta(days=10)
# R141: defterde fikstürü olmayan grup ligleri (E1–E3, D2, I2, SP2, F2 …) için bayatlık
# football-data'nın KENDİ tarihlerinden okunur: ligin son sonucu, geçen yılın olağan maç günü
# aralığından (%95'lik) daha eskiyse lig geride sayılır. 21 günden uzun ara yargılanmaz.
IN_SEASON_GAP = 21
MIN_HISTORY_DATES = 10
LAG_QUANTILE = 0.95


@dataclass(frozen=True)
class LiveMatch:
    match_id: str
    league_id: str
    kickoff: datetime  # UTC, saat dilimli
    home: str  # The Odds API adı
    away: str


@dataclass(frozen=True)
class Quote:
    match_id: str
    observed_at: datetime
    bookmaker: str
    market: str
    outcome: str
    price: float


@dataclass(frozen=True)
class Naming:
    codes: Mapping[str, str]  # canlı lig kimliği → football-data kodu
    aliases: Mapping[str, str]  # The Odds API adı → football-data adı
    known: Mapping[str, Mapping[str, str]]  # kod → normalize ad → football-data adı


@dataclass(frozen=True)
class LiveDecision:
    match_id: str
    record: MatchRecord
    context: DecisionContext
    results: tuple[ResultRecord, ...]


@dataclass(frozen=True)
class LiveBatch:
    decisions: tuple[LiveDecision, ...]
    unmapped: tuple[str, ...]  # lig ya da ad eşlenemedi
    stale: tuple[str, ...]  # grubun bilinmesi gereken bir sonucu tabanda yok
    no_quote: tuple[str, ...]  # karar anından önce tam 1X2 snapshot'ı yok


def naming_from(
    history: Mapping[str, Sequence[HistMatch]], codes: Mapping[str, str], aliases: Mapping[str, str]
) -> Naming:
    known = {
        code: MappingProxyType(
            {normalise_team(name): name for match in matches for name in (match.home, match.away)}
        )
        for code, matches in history.items()
    }
    return Naming(MappingProxyType(dict(codes)), aliases, MappingProxyType(known))


def canonical(naming: Naming, code: str, live_name: str) -> str | None:
    """Takma ad varsa O (football-data adı), yoksa tabanda normalize adı tutan ad."""
    if live_name in naming.aliases:
        return naming.aliases[live_name]
    return naming.known.get(code, {}).get(normalise_team(live_name))


def live_key(match: LiveMatch, naming: Naming) -> MatchKey | None:
    code = naming.codes.get(match.league_id)
    if code is None:
        return None
    home, away = canonical(naming, code, match.home), canonical(naming, code, match.away)
    if home is None or away is None:
        return None
    # football-data'nın `Date`i İngiltere tarihidir (R102; köprüyle aynı kural).
    return MatchKey(code, match.kickoff.astimezone(LONDON).date(), home, away)


def season_of(history: Sequence[HistMatch], day: date, kind: str) -> str | None:
    """Ana lig: temmuzda başlayan sezon kodu (`2627`); ek lig: tabandaki son maçın sezonu."""
    if kind == MAIN:
        start = day.year if day.month >= 7 else day.year - 1
        return f"{start % 100:02d}{(start + 1) % 100:02d}"
    earlier = [match for match in history if match.date <= day]
    return max(earlier, key=lambda match: match.date).season if earlier else None


def pre_prices(
    quotes: Sequence[Quote], match: LiveMatch, decided: datetime
) -> Mapping[OddsKey, float] | None:
    """Karar anında ya da önce gözlenen SON snapshot turunun 1X2'si, üç sonucu tam kitapların
    ortalaması; tam kitap yoksa None."""
    usable = [q for q in quotes if q.market == LIVE_H2H and q.observed_at <= decided]
    if not usable:
        return None
    latest = max(q.observed_at for q in usable)
    names = {match.home: "H", LIVE_DRAW: "D", match.away: "A"}
    books: dict[str, dict[str, float]] = {}
    for quote in usable:
        if quote.observed_at == latest and quote.outcome in names:
            books.setdefault(quote.bookmaker, {})[names[quote.outcome]] = quote.price
    full = [book for book in books.values() if set(book) == set(RESULTS)]
    if not full:
        return None
    return MappingProxyType(
        {
            OddsKey(REFERENCE_BOOK, H2H, outcome, PRE_CLOSING): math.fsum(
                book[outcome] for book in full
            )
            / len(full)
            for outcome in RESULTS
        }
    )


def observe_stream(group: Sequence[HistMatch], decided: datetime) -> tuple[ResultRecord, ...]:
    """Harness'ın `decided` anındaki karardan önce `observe`a verdiği sonuçlar, AYNI sırayla:
    (bilinme anı, gruptaki sıra) — `build_events`in sonuç olaylarının düzeni."""
    known = sorted(
        (result_known_at(match.date, match.kickoff), index)
        for index, match in enumerate(group)
        if result_known_at(match.date, match.kickoff) < decided
    )
    return tuple(result_of(record_of(group[index]), at) for at, index in known)


def is_stale(
    match: LiveMatch,
    group_live: Sequence[LiveMatch],
    naming: Naming,
    history_keys: frozenset[MatchKey],
    decided: datetime,
) -> bool:
    """Grubun, karar anından önce bitmiş sayılan (başlama + 3 sa) son 10 gündeki bir canlı maçı
    tabanda yoksa True — eşlenemeyen maç da doğrulanamadığı için bayat sayılır."""
    for other in group_live:
        if other.match_id == match.match_id:
            continue
        finished = other.kickoff + RESULT_LAG < decided
        recent = other.kickoff >= decided - STALE_LOOKBACK
        if finished and recent and live_key(other, naming) not in history_keys:
            return True
    return False


def league_lagging(dates: Sequence[date], decided_on: date) -> bool:
    """Bir ligin son sonuç tarihi, geçen yılki olağan aralığa göre fazla eski mi (R141)."""
    past = sorted({day for day in dates if day < decided_on})
    if len(past) < MIN_HISTORY_DATES:
        return False
    gap = (decided_on - past[-1]).days
    if gap > IN_SEASON_GAP:
        return False
    usual = sorted(
        (later - earlier).days
        for earlier, later in zip(past, past[1:], strict=False)
        if (decided_on - later).days <= 365 and (later - earlier).days <= IN_SEASON_GAP
    )
    if not usual:
        return False
    return gap > usual[int(LAG_QUANTILE * (len(usual) - 1))] + 1


def lagging_leagues(group: Sequence[HistMatch], decided: datetime) -> tuple[str, ...]:
    """Grubun (defterde olsun olmasın) geride kalan ligleri, karar gününe (Londra) göre."""
    decided_on = decided.astimezone(LONDON).date()
    dates: dict[str, list[date]] = {}
    for match in group:
        dates.setdefault(match.league, []).append(match.date)
    return tuple(code for code in sorted(dates) if league_lagging(dates[code], decided_on))


def build_batch(
    live: Sequence[LiveMatch],
    quotes: Sequence[Quote],
    groups: Mapping[str, Sequence[HistMatch]],
    *,
    now: datetime,
    naming: Naming,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
) -> LiveBatch:
    """`now`da kararı verilmiş ama başlamamış maçların bağlamları. `groups`: grup → tarihsel
    maçlar (`backtest.walkforward.group_matches` sırasıyla, DEV + POST)."""
    decisions: list[LiveDecision] = []
    unmapped: list[str] = []
    stale: list[str] = []
    no_quote: list[str] = []
    keys = frozenset(record_of(m).key for matches in groups.values() for m in matches)
    for match in sorted(live, key=lambda m: (m.kickoff, m.match_id)):
        key = live_key(match, naming)
        if key is None:
            unmapped.append(match.match_id)
            continue
        decided = decision_at(key.date, match.kickoff)
        if decided is None or not decided <= now < match.kickoff:
            continue
        group_name = rating_groups.get(key.league, key.league)
        group = groups.get(group_name, ())
        same_group = [
            m
            for m in live
            if rating_groups.get(naming.codes.get(m.league_id, ""), "") == group_name
        ]
        if is_stale(match, same_group, naming, keys, decided) or lagging_leagues(group, decided):
            stale.append(match.match_id)
            continue
        prices = pre_prices([q for q in quotes if q.match_id == match.match_id], match, decided)
        season = season_of(
            [m for m in group if m.league == key.league], key.date, kinds.get(key.league, MAIN)
        )
        if prices is None or season is None:
            no_quote.append(match.match_id)
            continue
        record = MatchRecord(key, season, match.kickoff, prices, None)
        decisions.append(
            LiveDecision(
                match.match_id,
                record,
                context_of(0, record, decided),
                observe_stream(group, decided),
            )
        )
    return LiveBatch(tuple(decisions), tuple(unmapped), tuple(stale), tuple(no_quote))
```

`src/football_edge/live/store.py`:

<!-- plan: yeni src/football_edge/live/store.py -->
```python
"""Defterden canlı kurucunun okuduğu satırlar (salt okuma). Yazan yol yok."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg

from football_edge.live.context import LIVE_H2H, LiveMatch, Quote

_MATCHES = """
    SELECT id, league_id, commence_time, home_team, away_team
    FROM matches
    WHERE commence_time >= %s AND commence_time < %s
    ORDER BY commence_time, id
"""
_QUOTES = """
    SELECT match_id, observed_at, bookmaker, market, outcome, price
    FROM odds_snapshots
    WHERE match_id = ANY(%s) AND market = %s AND observed_at <= %s
    ORDER BY match_id, observed_at, bookmaker, outcome
"""


def load_live_matches(
    conn: psycopg.Connection[Any], *, since: datetime, until: datetime
) -> tuple[LiveMatch, ...]:
    with conn.cursor() as cur:
        cur.execute(_MATCHES, (since, until))
        rows = cur.fetchall()
    return tuple(
        LiveMatch(str(row[0]), str(row[1]), row[2], str(row[3]), str(row[4])) for row in rows
    )


def load_quotes(
    conn: psycopg.Connection[Any], match_ids: tuple[str, ...], *, until: datetime
) -> tuple[Quote, ...]:
    """`until`e kadar gözlenen 1X2 satırları; fiyat `numeric` → float."""
    if not match_ids:
        return ()
    with conn.cursor() as cur:
        cur.execute(_QUOTES, (list(match_ids), LIVE_H2H, until))
        rows = cur.fetchall()
    return tuple(
        Quote(str(row[0]), row[1], str(row[2]), str(row[3]), str(row[4]), float(row[5]))
        for row in rows
    )
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_context_parity.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — 18 passed

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `pre_prices`: `and q.observed_at <= decided` silinir | `tests/test_context_parity.py::test_snapshots_after_the_decision_and_incomplete_books_are_ignored` |
| 2 | `observe_stream`: sıralama anahtarı `(index, index)` | `tests/test_context_parity.py::test_the_live_builder_reproduces_the_historical_context_and_stream` |
| 3 | `live_key`: Londra yerine başlamanın UTC tarihi | `tests/test_context_parity.py::test_a_live_night_kickoff_takes_the_london_date` |
| 4 | `is_stale`: hep `False` | `tests/test_context_parity.py::test_a_group_result_missing_from_the_base_makes_the_state_stale` |
| 5 | `canonical`: takma ad dalı `if False:` | `tests/test_context_parity.py::test_names_map_through_aliases_then_normalisation` |
| 6 | `pre_prices`: `<= decided` → `< decided` (karar anındaki tur düşer; inceleme I3) | `tests/test_context_parity.py` |
| 7 | `observe_stream`: `< decided` → `<= decided` (karar anında bilinen sonuç sızar; inceleme m1) | `tests/test_context_parity.py::test_the_live_builder_reproduces_the_historical_context_and_stream` |
| 8 | `build_batch`: `or lagging_leagues(group, decided)` silinir (R141) | `tests/test_context_parity.py::test_a_group_league_without_ledger_fixtures_that_falls_behind_makes_the_state_stale` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add src/football_edge/live/context.py \
  src/football_edge/live/store.py \
  tests/test_context_parity.py
git commit -m "feat: Faz 3 P2b — canlı bağlam kurucusu, bayat durum koruması, eşitlik testi E1–E2

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
### Task 9: Dalga 3 birleştirmesi, S'de seçim ve E raporu gerçek veride (controller)

**Kademe:** — (controller) · **Dalga:** 3 sonu · **Önkoşul:** Task 7 ve 8 `complete`.

- [ ] **Step 1: Birleştir** — `feat/faz3-select`, `feat/faz3-live` sırayla `--no-ff`, her birinden sonra kapı.
`leakage` sayısı ölçülür (plan yazımında 286), `EXPECTED_MIN_LEAKAGE` güncellenir.

- [ ] **Step 2: Seçim (yalnız S)** — `--cadence-days` Task 5'in kararıdır.

Run: `/usr/bin/time -l uv run --env-file .env python -m football_edge.backtest select --cadence-days <Task 5 kararı> > /tmp/select.log 2>&1; echo exit=$?`
Expected: exit 0; `config/model_faz3.yaml` yazıldı; logda her aday için `aday elo …`/`aday dixon_coles …` satırı
(koordinat inişi her parametrede bir değeri zaten ölçtüğü için Elo 1 + 4 + 2 + 2 + 2 + 2 = 13, DC 1 + 2 + 2 = 5
aday); süre ve tepe RSS ölçüm belgesine. Seçilen değerler
bir ızgaranın UCUNDAYSA (ör. `k = 30`) bu bir bulgudur: ölçüm belgesine yazılır, ızgara bu fazda GENİŞLETİLMEZ
(genişletmek S'de ikinci bir arama, yani yeni bir seçimdir — kullanıcıya sorulur).

- [ ] **Step 3: Seçimin iz kaydı** — `grep "aday " /tmp/select.log` çıktısı ölçüm belgesine (yalnız parametreler
ve S log loss'ları; maç satırı yok).

- [ ] **Step 4: E bölgesi raporu**

Run: `/usr/bin/time -l uv run --env-file .env python -m football_edge.backtest walkforward --gap --out docs/reports/<tarih>-faz3-walkforward.md; echo exit=$?`
Expected: exit 0; raporun sonunda "Boşluk cezası (R128, DEV simülasyonu)" bölümü (Elo ve DC için LL farkı ve
aralığı). `--gap` iki ek koşu demektir: süre üçe katlanır, ölçüm belgesine ayrı yazılır. Rapor yalnız toplu sayı
taşır — kontrol:

```bash
uv run --env-file .env python - <<'PY'
from pathlib import Path
from football_edge.db import connect
from football_edge.history.catalog import load_catalog
from football_edge.history.sync import load_matches
catalog = load_catalog(Path("config/history_leagues.yaml"))
with connect() as conn:
    names = {n for ms in load_matches(conn, catalog).values() for m in ms for n in (m.home, m.away)}
text = Path("docs/reports/<tarih>-faz3-walkforward.md").read_text(encoding="utf-8")
print("rapordaki takım adı:", sorted(n for n in names if len(n) > 3 and n in text))
PY
```
Expected: `rapordaki takım adı: []`. Süre ölçüm belgesine. **`walkforward` (`--gap`siz) 90 dk'yı aşarsa Task 12 başlamaz** (P17) — eskalasyon.

- [ ] **Step 5: Okuma** — raporda W1'in ham hâli (`ΔLL harman − piyasa`) görünür. Harman piyasadan > 0.001 kötüyse
bu Task 12'nin kapısını baştan kırmızı yapar: Task 12'ye geçmeden `fold_weights` ve bileşenler incelenir
(Revise), δ büyütülmez. **Revizyon E'yi gördükten sonra yapılan bir model değişikliğidir** (inceleme m7):
defterde Ruling olarak yazılır, E raporu bundan sonra örneklem dışı SAYILMAZ (HANDOFF adıyla yazar); holdout'un
güvenliği etkilenmez (ön kayıt revizyondan sonra yazılır).

- [ ] **Step 6: Commit, taze klon kapısı, push**

```bash
git add config/model_faz3.yaml docs/reports/<tarih>-faz3-walkforward.md \
  docs/superpowers/specs/2026-09-23-faz3-olcumler.md verify.sh
git commit -m "feat: Faz 3 — S'de seçilen hiperparametreler dondu; E bölgesi walk-forward raporu

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Taze klon kapısı, `git fetch origin && git merge --no-ff origin/main`, push, CI yeşil. Dalga 4 bu commit'ten
açılır.

---

### Task 10: `final_eval` — ön kayıt, tek kayıtlı açılış, prova; 0010 ve AST kuralı (P5; 12i, 14h, 14j)

**Kademe:** K1 · **Dalga:** 4 · **Worktree/dal:** `.worktrees/wt-final` · `feat/faz3-final-eval`

Tasarım §8, R135. `preregistration.py`: `config/faz3_preregistration.yaml` commit'lenmiş, ağaç temiz, üç özet (model yapılandırması, kilit, katalog) tutuyor — değilse `PreflightError`, HİÇBİR ŞEY açılmaz. `final_eval.py`: önce kilit anahtarsız doğrulanır ve Faz 3 açılışları sayılır (P13), sonra TAZE bağlantıda `open_holdout`; anahtar yalnız `load_matches`e verilir ve bırakılır; holdout satır sayısı kilitle eşleşmezse `OpenedButFailed`. Değerlendirme tam durumla (DEV + HOLDOUT + POST) oynatır, ağırlıklar yalnız DEV'in E'sinden (`frozen_weights`); C1–C6 ve Placebo raporlanır. `--rehearse` aynı yolu anahtarsız, 2024/25'i sahte holdout yaparak koşar (P22). `0010`: faz başına tek açılış ve tek yeniden koşu (ifade indeksi). AST kuralı: `HoldoutKey` yalnız üç modülde; anahtarın `load_matches(key=…)` ve `del` dışındaki her kullanımı yasak (12i); `history/` dışından ayrıştırıcı/önbelleğin `_`-önekli adlarına erişim yasak (14h). 14j: `load_matches`in gerçek anahtarlı pozitif yolu. **İnceleme düzeltmeleri:** C1 — `history/sync.py` `load_matches` BÜTÜN dönemlerde (holdout dahil) yinelenen maçı anahtar yokken `DuplicateMatches` ile reddeder (mesaj holdout satırı taşımaz); açılış öncesi yükleme bunu exit 12'ye çevirir. I4 — açılış kayda düştükten sonraki HER arıza (`load_matches`, sayım, değerlendirme, rapor yazımı) `OpenedButFailed`/exit 14; 0010'un `UniqueViolation`ı açılış değildir → exit 13; süreç dışı ölüm (OOM 137) yakalanamaz, Task 13 tablosu onu okur. I6 — `tests/test_holdout_phase_db.py` 0010'u gerçek veritabanında, geri alınan tek işlemde sınar (`DATABASE_URL` yoksa ADIYLA SKIP).

**Files:**
- Create: `src/football_edge/backtest/preregistration.py`
- Create: `src/football_edge/backtest/final_eval.py`
- Create: `db/migrations/0010_holdout_phase.sql`
- Create: `tests/test_final_eval.py`
- Create: `tests/test_holdout_phase_db.py`
- Modify: `src/football_edge/history/sync.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `src/football_edge/backtest/__main__.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `tests/test_holdout_access_rule.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `tests/test_history_sync.py` (yama aşağıda, `git apply` ile uygulanır)

**Interfaces:**
- Consumes: Task 6 (`group_rows(zoning=)`, `frozen_weights`, `summarise(zone=, given=)`, `ELO_SCAFFOLD`), Task 7 (`ModelConfig`, `model_strategies`, `score_table`, `format_interval`, CLI), Faz 2 (`open_holdout`, `load_matches`, `HistoryLock`, `Placebo`, `clv_values`).
- Produces: `Preregistration`, `Git`, `real_git`, `preflight`, `load_preregistration`, `PHASE`, `RERUN`, `COMPARISONS`, `PreflightError`; `FinalReport`, `AlreadyOpened`, `OpenedButFailed`, `HoldoutCountMismatch`, `purpose_for`, `previous_openings`, `check_holdout_count`, `final_zone`, `rehearsal_zone`, `evaluate_selected`, `run_final`, `run_rehearsal`, `render_final`; CLI `final-eval [--rehearse] [--rerun-reason]`, çıkış 12/13/14.

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_final_eval.py`:

<!-- plan: yeni tests/test_final_eval.py -->
```python
"""Faz 3'ün tek holdout açılışı (Faz 3 tasarımı §8; R130, R135): ön kayıt, sayım, sıra, satırlar.

Veritabanı yok: `open_holdout` ve `load_matches` `final_eval` modülünde yamalanır ve ÇAĞRI SIRASI
kaydedilir; değerlendirme SENTETİK sezonlarda gerçekten koşar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from football_edge.backtest import final_eval
from football_edge.backtest.final_eval import (
    AlreadyOpened,
    HoldoutCountMismatch,
    OpenedButFailed,
    check_holdout_count,
    purpose_for,
    render_final,
    run_final,
    run_rehearsal,
)
from football_edge.backtest.model_config import ModelConfig, file_sha256
from football_edge.backtest.preregistration import (
    COMPARISONS,
    Git,
    PreflightError,
    Preregistration,
    load_preregistration,
    preflight,
)
from football_edge.history.catalog import MAIN, Catalog, HistoryLeague
from football_edge.history.holdout import HOLDOUT, HoldoutKey, period_of
from football_edge.history.lock import LockViolation, build_lock
from football_edge.market.devig import POWER
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModelConfig
from tests.model_builders import TEAMS, main_history
from tests.workflow_helpers import MIGRATIONS

SHA = "a" * 40
NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)
CATALOG = Catalog("2627", (HistoryLeague("E0", "t.1", "Test", "Ülke", 1, MAIN, "1112", ""),))
EVERYTHING = {"E0": main_history(2011, 2026)}
LOCK = build_lock(EVERYTHING, locked_at=date(2026, 9, 22))
PREREG = Preregistration("faz3", "m", "l", "c", COMPARISONS, 0.02, (0.0, 0.05), 50)
CONFIG = ModelConfig(
    "2026-10-01", "c", "l", POWER, EloModelConfig(), DCConfig(min_matches=40), 7, 0.02, (0.0,)
)


def test_the_first_opening_carries_the_preregistration_hash() -> None:
    assert (
        purpose_for((), prereg_sha256="p" * 64, git_sha=SHA, report_exists=False, rerun_reason=None)
        == "faz3:" + "p" * 64
    )


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("previous", "report", "sha", "reason"),
    [
        ((("faz3:x", SHA),), False, SHA, None),  # ikinci açılış, neden yok
        ((("faz3:x", SHA),), True, SHA, "çöktü"),  # rapor üretilmiş
        ((("faz3:x", "b" * 40),), False, SHA, "çöktü"),  # kod değişmiş
        ((("faz3:x", SHA), ("faz3-rerun:y:x", SHA)), False, SHA, "yine"),  # ikinci yeniden koşu
        ((), False, SHA, "çöktü"),  # açılış yokken yeniden koşu
        ((("faz3:x", SHA),), False, SHA, "  "),  # boş neden
    ],
)
def test_a_second_opening_is_refused_unless_the_rerun_rule_holds(
    previous: tuple[tuple[str, str], ...], report: bool, sha: str, reason: str | None
) -> None:
    with pytest.raises(AlreadyOpened):
        purpose_for(
            previous, prereg_sha256="p", git_sha=sha, report_exists=report, rerun_reason=reason
        )


def test_one_logged_rerun_after_a_crash_without_a_report() -> None:
    found = purpose_for(
        (("faz3:p", SHA),), prereg_sha256="p", git_sha=SHA, report_exists=False, rerun_reason="OOM"
    )

    assert found == "faz3-rerun:OOM:p"


def _git(*, clean: bool = True, committed: bool = True) -> Git:
    return Git(head=lambda: SHA, clean=lambda: clean, committed=lambda path: committed)


def _prereg_files(tmp: Path) -> dict[str, Path]:
    paths = {name: tmp / f"{name}.yaml" for name in ("model", "lock", "catalog")}
    for name, path in paths.items():
        path.write_text(f"{name}\n", encoding="utf-8")
    prereg = tmp / "prereg.yaml"
    prereg.write_text(
        "phase: faz3\n"
        f"model_config_sha256: {file_sha256(paths['model'])}\n"
        f"lock_sha256: {file_sha256(paths['lock'])}\n"
        f"catalog_sha256: {file_sha256(paths['catalog'])}\n"
        "comparisons: [C1, C2, C3, C4, C5, C6]\n"
        "tau: 0.02\nsensitivity: [0.0, 0.05]\nresamples: 2000\n",
        encoding="utf-8",
    )
    return {**paths, "prereg": prereg}


def _preflight(paths: dict[str, Path], git: Git) -> Preregistration:
    return preflight(
        prereg_path=paths["prereg"],
        model_path=paths["model"],
        lock_path=paths["lock"],
        catalog_path=paths["catalog"],
        git=git,
    )


def test_preflight_passes_a_committed_matching_preregistration(tmp_path: Path) -> None:
    prereg = _preflight(_prereg_files(tmp_path), _git())

    assert prereg.comparisons == COMPARISONS and prereg.tau == 0.02


@pytest.mark.leakage
@pytest.mark.parametrize("change", ["dirty", "uncommitted", "model", "lock", "catalog", "phase"])
def test_preflight_refuses_before_anything_opens(tmp_path: Path, change: str) -> None:
    paths = _prereg_files(tmp_path)
    git = _git(clean=change != "dirty", committed=change != "uncommitted")
    if change in ("model", "lock", "catalog"):
        paths[change].write_text("değişti\n", encoding="utf-8")
    if change == "phase":
        text = paths["prereg"].read_text(encoding="utf-8").replace("phase: faz3", "phase: faz4")
        paths["prereg"].write_text(text, encoding="utf-8")

    with pytest.raises(PreflightError):
        _preflight(paths, git)


def test_a_malformed_preregistration_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text("phase: faz3\n", encoding="utf-8")

    with pytest.raises(PreflightError, match="alanlar"):
        load_preregistration(path)


@dataclass
class _Db:
    previous: list[tuple[str, str]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def __call__(self) -> _Db:
        self.calls.append("connect")
        return self

    def __enter__(self) -> _Db:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def cursor(self) -> _Db:
        return self

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.calls.append("count")

    def fetchall(self) -> list[tuple[str, str]]:
        return self.previous


def _patch(
    monkeypatch: pytest.MonkeyPatch, db: _Db, *, lock_error: bool = False, drop: int = 0
) -> None:
    def open_holdout(conn: object, *, purpose: str, git_sha: str, now: datetime) -> HoldoutKey:
        db.calls.append(f"open {purpose}")
        return HoldoutKey(opened_at=now, purpose=purpose, git_sha=git_sha)

    def load_matches(
        conn: object, catalog: object, *, lock: object = None, key: object = None
    ) -> object:
        db.calls.append("load keyed" if key is not None else "load")
        if lock_error and key is None:
            raise LockViolation("E0/holdout: fark")
        if key is None:
            return {"E0": tuple(m for m in EVERYTHING["E0"] if period_of(m.date) != HOLDOUT)}
        holdout = [m for m in EVERYTHING["E0"] if period_of(m.date) == HOLDOUT]
        return {"E0": tuple(m for m in EVERYTHING["E0"] if m not in holdout[:drop])}

    monkeypatch.setattr(final_eval, "open_holdout", open_holdout)
    monkeypatch.setattr(final_eval, "load_matches", load_matches)


def _run(db: _Db, tmp: Path, **kwargs: Any) -> Any:
    return run_final(
        db,  # type: ignore[arg-type]
        catalog=CATALOG,
        lock=LOCK,
        config=CONFIG,
        prereg=PREREG,
        prereg_sha256="p" * 64,
        git_sha=SHA,
        now=NOW,
        report_path=tmp / "rapor.md",
        **kwargs,
    )


@pytest.mark.leakage
def test_the_lock_is_verified_and_openings_counted_before_the_single_opening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db()
    _patch(monkeypatch, db)

    report = _run(db, tmp_path)

    assert db.calls == [
        "connect",
        "load",
        "count",
        "connect",
        "open faz3:" + "p" * 64,
        "load keyed",
    ]
    assert report.holdout_rows == sum(1 for m in EVERYTHING["E0"] if period_of(m.date) == HOLDOUT)
    assert report.holdout.main and report.post.main


@pytest.mark.leakage
def test_a_previous_opening_stops_before_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db(previous=[("faz3:x", SHA)])
    _patch(monkeypatch, db)

    with pytest.raises(AlreadyOpened):
        _run(db, tmp_path)
    assert not any(call.startswith("open") for call in db.calls)


@pytest.mark.leakage
def test_a_lock_violation_stops_before_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db()
    _patch(monkeypatch, db, lock_error=True)

    with pytest.raises(LockViolation):
        _run(db, tmp_path)
    assert not any(call.startswith("open") for call in db.calls)


def test_a_holdout_count_that_differs_from_the_lock_fails_after_the_opening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = _Db()
    _patch(monkeypatch, db, drop=1)

    with pytest.raises(HoldoutCountMismatch) as raised:
        _run(db, tmp_path)
    assert isinstance(raised.value, OpenedButFailed)
    assert any(call.startswith("open") for call in db.calls)


def test_check_holdout_count_matches_the_lock() -> None:
    assert check_holdout_count(LOCK, EVERYTHING) == sum(
        1 for m in EVERYTHING["E0"] if period_of(m.date) == HOLDOUT
    )


def test_the_report_is_aggregate_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = _Db()
    _patch(monkeypatch, db)

    text = render_final(_run(db, tmp_path), generated_at=NOW)

    assert "C1 ΔLL harman − piyasa" in text and "C6" in text and "Placebo" in text
    assert not any(team in text for team in TEAMS)


def test_the_phase_index_migration_allows_one_opening_and_one_rerun_per_phase() -> None:
    sql = (MIGRATIONS / "0010_holdout_phase.sql").read_text(encoding="utf-8")

    assert "create unique index if not exists holdout_access_log_one_per_phase" in sql
    assert "((split_part(purpose, ':', 1)))" in sql
    assert "where purpose ~ '^faz[0-9]+(-rerun)?:'" in sql


@pytest.mark.leakage
def test_the_rehearsal_runs_the_whole_path_without_opening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _Db()
    _patch(monkeypatch, db)

    report = run_rehearsal(
        db,  # type: ignore[arg-type]
        catalog=CATALOG,
        lock=LOCK,
        config=CONFIG,
        prereg=PREREG,
        start=date(2024, 7, 1),
        end=date(2025, 7, 1),
    )

    assert db.calls == ["connect", "load"]
    assert report.purpose == "prova" and report.holdout_rows > 0
    assert report.holdout.main and not report.post.main


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("failure", "code"),
    [("preflight", 12), ("duplicate", 12), ("already", 13), ("opened", 14), ("render", 14)],
)
def test_the_cli_names_where_it_stopped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str, code: int
) -> None:
    from football_edge.backtest import __main__ as cli

    paths = _prereg_files(tmp_path)
    monkeypatch.setattr(cli, "real_git", lambda: _git(clean=failure != "preflight"))
    monkeypatch.setattr(cli, "load_model_config", lambda path: CONFIG)
    monkeypatch.setattr(cli, "load_catalog", lambda path: CATALOG)
    monkeypatch.setattr(cli, "load_lock", lambda path: LOCK)

    def run_final(*args: object, **kwargs: object) -> object:
        if failure == "duplicate":
            from football_edge.history.sync import DuplicateMatches

            raise DuplicateMatches("yinelenen maç: E0 ×1")
        if failure == "render":
            return object()  # render_final bu nesneyle düşer: açıldı ama rapor yok
        raise AlreadyOpened("x") if failure == "already" else OpenedButFailed("y")

    monkeypatch.setattr(cli, "run_final", run_final)
    out = tmp_path / "rapor.md"

    returned = cli.main(
        [
            "final-eval",
            "--prereg",
            str(paths["prereg"]),
            "--config",
            str(paths["model"]),
            "--lock",
            str(paths["lock"]),
            "--catalog",
            str(paths["catalog"]),
            "--out",
            str(out),
        ]
    )

    assert returned == code and not out.exists()


@pytest.mark.leakage
def test_a_duplicate_found_by_the_keyless_load_stops_before_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C1: bütün dönemlerdeki yineleme reddi açılıştan önce gelir; CLI onu exit 12 sayar."""
    from football_edge.history.sync import DuplicateMatches

    db = _Db()
    _patch(monkeypatch, db)

    def refusing(
        conn: object, catalog: object, *, lock: object = None, key: object = None
    ) -> object:
        db.calls.append("load")
        raise DuplicateMatches("football-data: yinelenen maç (bütün dönemler, 14g): E0 ×1")

    monkeypatch.setattr(final_eval, "load_matches", refusing)

    with pytest.raises(DuplicateMatches):
        _run(db, tmp_path)
    assert not any(call.startswith("open") for call in db.calls)


@pytest.mark.leakage
def test_any_failure_after_the_opening_is_reported_as_opened(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I4: açılış kayda düştükten sonraki her arıza exit 14 sınıfıdır (yeniden koşu ona bakar)."""
    db = _Db()
    _patch(monkeypatch, db)

    def broken(*args: object, **kwargs: object) -> object:
        raise RuntimeError("değerlendirme çöktü")

    monkeypatch.setattr(final_eval, "evaluate_selected", broken)

    with pytest.raises(OpenedButFailed, match="RuntimeError"):
        _run(db, tmp_path)
    assert any(call.startswith("open") for call in db.calls)


def test_the_phase_index_rejecting_the_insert_is_not_an_opening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """I4: 0010'un `UniqueViolation`ı INSERT'i geri alır — açılış yok, exit 13 sınıfı."""
    import psycopg

    db = _Db()
    _patch(monkeypatch, db)

    def rejected(conn: object, *, purpose: str, git_sha: str, now: datetime) -> HoldoutKey:
        raise psycopg.errors.UniqueViolation("holdout_access_log_one_per_phase")

    monkeypatch.setattr(final_eval, "open_holdout", rejected)

    with pytest.raises(AlreadyOpened, match="0010"):
        _run(db, tmp_path)
    assert "load keyed" not in db.calls
```

`tests/test_holdout_phase_db.py`:

<!-- plan: yeni tests/test_holdout_phase_db.py -->
```python
"""0010'un tekil indeksi GERÇEK veritabanında (Faz 3 tasarımı §9 G6, plan incelemesi I6).

Tek işlemde, sonunda geri alınarak: aynı fazın ikinci açılışı ve ikinci yeniden koşusu
`UniqueViolation` verir, ilk yeniden koşu kabul edilir. Faz adı `faz99` — gerçek fazlarla
karışmaz; geri alma satır bırakmaz (append-only tetikleyiciler yalnız UPDATE/DELETE/TRUNCATE'i
durdurur). `DATABASE_URL` yoksa ADIYLA atlanır (`zincir` adımı gibi); 0010 uygulanmamış bir
veritabanında KIRMIZIDIR — doğru davranış.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import psycopg
import pytest

from football_edge.db import connect

INSERT = "INSERT INTO holdout_access_log (opened_at, git_sha, purpose) VALUES (%s, %s, %s)"
NO_DATABASE = "DATABASE_URL yok — 0010 gerçek veritabanında sınanmadı"


def _rejects(cur: psycopg.Cursor[object], purpose: str, savepoint: str) -> bool:
    cur.execute(f"SAVEPOINT {savepoint}")
    try:
        cur.execute(INSERT, (datetime.now(UTC), "a" * 40, purpose))
    except psycopg.errors.UniqueViolation:
        cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        return True
    return False


@pytest.mark.skipif(not os.getenv("DATABASE" + "_URL"), reason=NO_DATABASE)
def test_the_phase_index_allows_one_opening_and_one_rerun_per_phase() -> None:
    with connect() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(INSERT, (datetime.now(UTC), "a" * 40, "faz99:ilk"))
                assert _rejects(cur, "faz99:ikinci", "s1"), "ikinci faz99 açılışı kabul edildi"
                assert not _rejects(cur, "faz99-rerun:çöktü:ilk", "s2"), (
                    "ilk yeniden koşu reddedildi"
                )
                assert _rejects(cur, "faz99-rerun:yine:ilk", "s3"), (
                    "ikinci yeniden koşu kabul edildi"
                )
                assert not _rejects(cur, "faz98:başka", "s4"), "başka faz reddedildi"
        finally:
            conn.rollback()
```

`tests/test_holdout_access_rule.py` yaması:

<!-- plan: yama tests/test_holdout_access_rule.py -->
```diff
diff --git a/tests/test_holdout_access_rule.py b/tests/test_holdout_access_rule.py
index bd68c21..f6c9da8 100644
--- a/tests/test_holdout_access_rule.py
+++ b/tests/test_holdout_access_rule.py
@@ -52,6 +52,12 @@ GUARDED: dict[str, tuple[frozenset[str], str]] = {
         frozenset({HOLDOUT_MODULE}),
         "mühürle elle kurulan anahtar açılışı kayda yazmaz",
     ),
+    # 12i (Faz 3): anahtar yalnız tanımlandığı, tüketildiği ve açıldığı üç modülde anılır;
+    # işçiler anahtar değil seçilmiş satır alır.
+    "HoldoutKey": (
+        frozenset({HOLDOUT_MODULE, SYNC_MODULE, FINAL_EVAL}),
+        "anahtar yalnız final_eval'de açılır ve load_matches'e verilir (12i)",
+    ),
     "_load_all": (
         frozenset({SYNC_MODULE, HISTORY_CLI}),
         "bütün dönemleri döner; holdout satırları history/'den anahtarsız çıkmaz (R96)",
@@ -144,7 +150,9 @@ REFERENCES = [
     '__import__("football_edge.history.holdout", fromlist=["open_holdout"])',
     "from football_edge.history.holdout import *",
     "from football_edge.history.holdout import _HOLDOUT_SEAL",
-    "HoldoutKey(opened_at=t, purpose='x', git_sha=s, _seal=holdout._HOLDOUT_SEAL)",
+    "make(opened_at=t, purpose='x', git_sha=s, _seal=holdout._HOLDOUT_SEAL)",
+    "from football_edge.history.holdout import HoldoutKey",
+    "def f(key: holdout.HoldoutKey) -> None: ...",
     'select_periods.__globals__["_HOLDOUT_SEAL"]',
     'vars(holdout)["_HOLDOUT_SEAL"]',
     "from football_edge.history.sync import _load_all",
@@ -167,7 +175,7 @@ MENTIONS = [
     'def f() -> None:\n    """open_holdout burada çağrılmaz."""\n',
     "# open_holdout(conn)",
     'LOGGER.info("open_holdout çağrılmadı")',
-    "from football_edge.history.holdout import HoldoutKey, select_periods",
+    "from football_edge.history.holdout import HOLDOUT, select_periods",
     "open_holdout_count = 0",
     "log_fetch(conn, rows_parsed=len(result.matches))",
     '"""parse_file dönem süzmez; load_files önbellek baytını döner."""',
@@ -303,3 +311,166 @@ def test_holdout_is_opened_only_where_allowed() -> None:
     violations = _scan(REPO)
 
     assert not violations, "holdout izinsiz açılabiliyor:\n" + "\n".join(violations)
+
+
+# ── Faz 3: anahtarın akışı (12i) ve ayrıştırıcının özel yardımcıları (14h) ──────────────────
+
+
+def key_misuses(source: str) -> list[str]:
+    """`open_holdout`un döndürdüğü adın `load_matches(..., key=ad)` ve `del ad` DIŞINDA her
+    kullanımı: anahtar döndürülemez, saklanamaz, başka bir fonksiyona verilemez."""
+    tree = ast.parse(source)
+    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
+    keys = {
+        target.id
+        for node in ast.walk(tree)
+        if isinstance(node, ast.Assign) and _calls(node.value, "open_holdout")
+        for target in node.targets
+        if isinstance(target, ast.Name)
+    }
+    return [
+        f"{node.lineno}: {node.id}"
+        for node in ast.walk(tree)
+        if isinstance(node, ast.Name)
+        and node.id in keys
+        and isinstance(node.ctx, ast.Load)
+        and not _is_load_matches_key(node, parents)
+    ]
+
+
+def _calls(node: ast.AST, name: str) -> bool:
+    if not isinstance(node, ast.Call):
+        return False
+    func = node.func
+    return (isinstance(func, ast.Name) and func.id == name) or (
+        isinstance(func, ast.Attribute) and func.attr == name
+    )
+
+
+def _is_load_matches_key(node: ast.Name, parents: dict[ast.AST, ast.AST]) -> bool:
+    keyword = parents.get(node)
+    if not isinstance(keyword, ast.keyword) or keyword.arg != "key":
+        return False
+    call = parents.get(keyword)
+    return call is not None and _calls(call, "load_matches")
+
+
+PROTECTED_MODULES = ("football_edge.history.football_data", "football_edge.history.store")
+HISTORY_PACKAGE = "src/football_edge/history/"
+
+
+def private_accesses(source: str, path: str) -> list[str]:
+    """14h: `history/` dışından ayrıştırıcının ve önbelleğin `_`-önekli adlarına erişim."""
+    if path.startswith(HISTORY_PACKAGE):
+        return []
+    tree = ast.parse(source)
+    aliases: set[str] = set()
+    found: list[str] = []
+    for node in ast.walk(tree):
+        if isinstance(node, ast.Import):
+            aliases |= {
+                alias.asname or alias.name
+                for alias in node.names
+                if alias.name in PROTECTED_MODULES
+            }
+        elif isinstance(node, ast.ImportFrom) and node.module:
+            for alias in node.names:
+                full = f"{node.module}.{alias.name}"
+                if full in PROTECTED_MODULES:
+                    aliases.add(alias.asname or alias.name)
+                elif node.module in PROTECTED_MODULES and alias.name.startswith("_"):
+                    found.append(f"{path}:{node.lineno}: from {node.module} import {alias.name}")
+    for node in ast.walk(tree):
+        if (
+            isinstance(node, ast.Attribute)
+            and node.attr.startswith("_")
+            and not node.attr.startswith("__")
+            and _root(node.value) in aliases
+        ):
+            found.append(f"{path}:{node.lineno}: .{node.attr} erişimi")
+    return found
+
+
+def _root(node: ast.AST) -> str | None:
+    if isinstance(node, ast.Name):
+        return node.id
+    if isinstance(node, ast.Attribute):
+        dotted = _root(node.value)
+        return None if dotted is None else f"{dotted}.{node.attr}"
+    return None
+
+
+@pytest.mark.leakage
+def test_the_real_final_eval_hands_the_key_only_to_load_matches() -> None:
+    source = (REPO / FINAL_EVAL).read_text(encoding="utf-8")
+
+    assert "open_holdout(" in source, "kural boşa yeşil kalmasın: final_eval anahtarı açıyor"
+    assert key_misuses(source) == []
+
+
+KEY_MISUSES = [
+    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nreturn key",
+    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nself.key = key",
+    "key = holdout.open_holdout(c, purpose=p, git_sha=s, now=n)\nevaluate(rows, key)",
+    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nkeys = [key]",
+    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nselect_periods(m, periods=x, key=key)",
+    "key = open_holdout(c, purpose=p, git_sha=s, now=n)\nload_matches(c, catalog, None, key)",
+]
+
+
+@pytest.mark.leakage
+@pytest.mark.parametrize("snippet", KEY_MISUSES)
+def test_every_other_use_of_the_key_is_a_misuse(snippet: str) -> None:
+    assert len(key_misuses(snippet)) == 1
+
+
+@pytest.mark.leakage
+def test_handing_the_key_to_load_matches_and_deleting_it_is_allowed() -> None:
+    snippet = (
+        "key = open_holdout(c, purpose=p, git_sha=s, now=n)\n"
+        "rows = load_matches(c, catalog, lock=lock, key=key)\n"
+        "del key\n"
+    )
+
+    assert key_misuses(snippet) == []
+
+
+PRIVATE_ACCESSES = [
+    "from football_edge.history.football_data import _records",
+    "from football_edge.history.store import _LOAD_FILES",
+    "from football_edge.history import football_data\nfootball_data._decode(b'x')",
+    "from football_edge.history import store as s\ns._LOAD_FILES",
+    "import football_edge.history.football_data as fd\nfd._row(ctx, rec)",
+    "import football_edge.history.football_data\nfootball_edge.history.football_data._context(r)",
+]
+
+
+@pytest.mark.leakage
+@pytest.mark.parametrize("snippet", PRIVATE_ACCESSES)
+def test_private_parser_helpers_are_closed_outside_history(snippet: str) -> None:
+    assert len(private_accesses(snippet, ELSEWHERE)) == 1
+
+
+@pytest.mark.leakage
+@pytest.mark.parametrize(
+    ("snippet", "path"),
+    [
+        ("from football_edge.history.football_data import parse", ELSEWHERE),
+        ("from football_edge.history import football_data\nfootball_data.__name__", ELSEWHERE),
+        ("from football_edge.history.football_data import _records", SYNC_MODULE),
+        ("from football_edge.backtest import harness\nharness._context(0, m, t)", ELSEWHERE),
+    ],
+)
+def test_public_names_dunders_and_the_history_package_stay_clean(snippet: str, path: str) -> None:
+    assert private_accesses(snippet, path) == []
+
+
+@pytest.mark.leakage
+def test_no_module_outside_history_reaches_the_private_parser_helpers() -> None:
+    violations = [
+        found
+        for path in _python_files(REPO)
+        for found in private_accesses(path.read_text(encoding="utf-8"), _rel(path, REPO))
+    ]
+
+    assert not violations, "ayrıştırıcının özel yardımcılarına erişim:\n" + "\n".join(violations)
```

`tests/test_history_sync.py` yaması:

<!-- plan: yama tests/test_history_sync.py -->
```diff
diff --git a/tests/test_history_sync.py b/tests/test_history_sync.py
index 8b4c360..55fd23b 100644
--- a/tests/test_history_sync.py
+++ b/tests/test_history_sync.py
@@ -12,10 +12,25 @@ from protego import Protego
 
 from football_edge.collector import ContractViolation
 from football_edge.history.catalog import Catalog, declared_paths, load_catalog
-from football_edge.history.holdout import DEV, HOLDOUT, POST, HoldoutKey, HoldoutLocked, period_of
+from football_edge.history.holdout import (
+    DEV,
+    HOLDOUT,
+    POST,
+    HoldoutKey,
+    HoldoutLocked,
+    open_holdout,
+    period_of,
+)
 from football_edge.history.lock import LockViolation, build_lock
 from football_edge.history.store import save_file
-from football_edge.history.sync import SyncReport, _load_all, load_matches, mutable_paths, sync
+from football_edge.history.sync import (
+    DuplicateMatches,
+    SyncReport,
+    _load_all,
+    load_matches,
+    mutable_paths,
+    sync,
+)
 from football_edge.history.types import HistMatch
 from tests.fake_hist_db import FakeHistDb, at
 from tests.fake_sources import fake_source
@@ -318,6 +333,45 @@ def test_a_hand_built_key_does_not_open_the_holdout() -> None:
         load_matches(_cached_periods(), CATALOG, key=forged)
 
 
+class _AccessLog:
+    """`open_holdout`ın yazdığı tek INSERT'i ve commit'i sayan en küçük bağlantı."""
+
+    def __init__(self) -> None:
+        self.inserts: list[tuple[object, ...]] = []
+        self.commits = 0
+
+    def cursor(self) -> _AccessLog:
+        return self
+
+    def __enter__(self) -> _AccessLog:
+        return self
+
+    def __exit__(self, *exc: object) -> None:
+        return None
+
+    def execute(self, sql: str, params: tuple[object, ...]) -> None:
+        self.inserts.append(params)
+
+    def commit(self) -> None:
+        self.commits += 1
+
+    def rollback(self) -> None:
+        raise AssertionError("rollback beklenmiyordu")
+
+
+@pytest.mark.leakage
+def test_a_key_from_open_holdout_returns_the_holdout_rows_once_logged() -> None:
+    """14j: `load_matches`in gerçek anahtarlı pozitif yolu — açılış kayda düşer, sonra holdout
+    satırları DEV ve sonrası dönemiyle birlikte döner."""
+    log = _AccessLog()
+    key = open_holdout(log, purpose="faz3:deneme", git_sha="a" * 40, now=at(0))  # type: ignore[arg-type]
+
+    loaded = load_matches(_cached_periods(), CATALOG, key=key)
+
+    assert (len(log.inserts), log.commits) == (1, 1)
+    assert _periods(loaded) == {"E0": [HOLDOUT, POST], "BRA": [DEV, HOLDOUT, POST]}
+
+
 @pytest.mark.leakage
 def test_the_lock_is_checked_over_every_period_before_the_holdout_is_filtered_out() -> None:
     """Süzgeçten SONRA doğrulansaydı kilitteki holdout özeti eksik satırlarla tutmazdı."""
@@ -350,3 +404,23 @@ def test_load_matches_rechecks_the_contract_of_every_cached_file() -> None:
 
     with pytest.raises(ContractViolation, match="zorunlu sütun"):
         load_matches(db, CATALOG)
+
+
+@pytest.mark.leakage
+def test_a_duplicate_inside_the_holdout_is_refused_before_any_key_exists() -> None:
+    """C1: 2025/26 ve 2026/27 dosyalarının pencereleri haziranda çakışır; aynı maç holdout'ta iki
+    kez geçerse anahtarsız yükleme reddeder — açılış hiç denenmez. Mesaj holdout satırı taşımaz."""
+    twin = main_row(7, {"Date": "30/06/2026"})
+    files = {
+        **PERIODS_FILES,
+        OLD: csv_bytes(MAIN_2526, [*(main_row(n) for n in range(3)), twin]),
+        CURRENT: csv_bytes(
+            MAIN_2627, [main_row(n, {"Date": "22/08/2026"}) for n in range(2)] + [twin]
+        ),
+    }
+    db = FakeHistDb()
+    run(db, Site(files))
+
+    with pytest.raises(DuplicateMatches, match=r"E0 ×1") as raised:
+        load_matches(db, CATALOG)
+    assert "Ev 7" not in str(raised.value) and "2026-06-30" not in str(raised.value)
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_final_eval.py tests/test_holdout_phase_db.py tests/test_holdout_access_rule.py tests/test_history_sync.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.backtest.final_eval'`; `ImportError: cannot import name 'DuplicateMatches'` (test_history_sync); `test_the_real_final_eval_hands_the_key_only_to_load_matches` `FileNotFoundError`. 14j testi (`test_a_key_from_open_holdout_returns_the_holdout_rows_once_logged`) MEVCUT kodu sabitler ve baştan yeşildir — kırmızısı mutasyon 6'da.

- [ ] **Step 3: Uygulamayı yaz**

`src/football_edge/backtest/preregistration.py`:

<!-- plan: yeni src/football_edge/backtest/preregistration.py -->
```python
"""Faz 3 holdout ön kaydı (tasarım §8.1; R130, R135, R139): `config/faz3_preregistration.yaml`.

Açılıştan ÖNCE commit'lenir; `final_eval` dosyanın commit'lenmiş hâliyle çalışma ağacındakinin aynı
olduğunu, ağacın temiz olduğunu ve üç özetin (model yapılandırması, kilit, katalog) tuttuğunu
açmadan sınar. Açılışın `purpose`u ön kaydın sha256'sını taşır.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from football_edge.backtest.model_config import file_sha256

PREREGISTRATION_PATH = Path("config/faz3_preregistration.yaml")
PHASE = "faz3"
RERUN = "faz3-rerun"
COMPARISONS = ("C1", "C2", "C3", "C4", "C5", "C6")
_FIELDS = frozenset(
    {
        "phase",
        "model_config_sha256",
        "lock_sha256",
        "catalog_sha256",
        "comparisons",
        "tau",
        "sensitivity",
        "resamples",
    }
)


class PreflightError(RuntimeError):
    """Açılış öncesi denetimlerden biri tutmadı: holdout AÇILMAZ."""


@dataclass(frozen=True)
class Preregistration:
    phase: str
    model_config_sha256: str
    lock_sha256: str
    catalog_sha256: str
    comparisons: tuple[str, ...]
    tau: float
    sensitivity: tuple[float, ...]
    resamples: int


@dataclass(frozen=True)
class Git:
    """Git'e yalnız okuma soruları; testlerde sahte fonksiyonlarla kurulur."""

    head: Callable[[], str]
    clean: Callable[[], bool]
    committed: Callable[[Path], bool]  # dosya izleniyor ve HEAD'deki hâliyle aynı


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(("git", *args), capture_output=True, text=True, check=False)


def real_git() -> Git:
    return Git(
        head=lambda: _git("rev-parse", "HEAD").stdout.strip(),
        clean=lambda: _git("status", "--porcelain").stdout.strip() == "",
        committed=lambda path: (
            _git("ls-files", "--error-unmatch", str(path)).returncode == 0
            and _git("diff", "--quiet", "HEAD", "--", str(path)).returncode == 0
        ),
    )


def load_preregistration(path: Path) -> Preregistration:
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise PreflightError(f"{path}: okunamadı: {error}") from error
    if not isinstance(raw, dict) or set(raw) != _FIELDS:
        raise PreflightError(f"{path}: alanlar {sorted(_FIELDS)} olmalı")
    if raw["phase"] != PHASE or tuple(raw["comparisons"]) != COMPARISONS:
        raise PreflightError(f"{path}: faz {PHASE!r} ve karşılaştırmalar {COMPARISONS} olmalı")
    return Preregistration(
        phase=str(raw["phase"]),
        model_config_sha256=str(raw["model_config_sha256"]),
        lock_sha256=str(raw["lock_sha256"]),
        catalog_sha256=str(raw["catalog_sha256"]),
        comparisons=tuple(str(item) for item in raw["comparisons"]),
        tau=float(raw["tau"]),
        sensitivity=tuple(float(value) for value in raw["sensitivity"]),
        resamples=int(raw["resamples"]),
    )


def preflight(
    *, prereg_path: Path, model_path: Path, lock_path: Path, catalog_path: Path, git: Git
) -> Preregistration:
    """Açılış öncesi bütün denetimler; biri tutmazsa `PreflightError` (hiçbir şey açılmaz)."""
    if not git.clean():
        raise PreflightError("çalışma ağacı temiz değil")
    if not git.committed(prereg_path):
        raise PreflightError(f"{prereg_path}: commit'lenmemiş ya da HEAD'dekinden farklı")
    prereg = load_preregistration(prereg_path)
    for name, expected, path in (
        ("model yapılandırması", prereg.model_config_sha256, model_path),
        ("kilit", prereg.lock_sha256, lock_path),
        ("katalog", prereg.catalog_sha256, catalog_path),
    ):
        if file_sha256(path) != expected:
            raise PreflightError(f"{name} ön kayıttaki özetle uyuşmuyor: {path}")
    return prereg
```

`src/football_edge/backtest/final_eval.py`:

<!-- plan: yeni src/football_edge/backtest/final_eval.py -->
```python
"""Faz 3'ün TEK, kayıtlı holdout açılışı (Faz 3 tasarımı §8; R128, R130, R135).

`open_holdout`ın anılabildiği TEK modül (`tests/test_holdout_access_rule.py`). Anahtar yalnız
`load_matches`e verilir ve hemen bırakılır: değerlendirme anahtarı değil SEÇİLMİŞ SATIRLARI alır
(DEFERRED 12i). Açılıştan önce ön kayıt denetimi (`preflight`) ve açılış sayımı: Faz 3 için önceki
bir açılış varsa açılmaz — yalnız çöküş sonrası, rapor üretilmemişse ve git SHA'sı aynıysa tek bir
kayıtlı yeniden koşu (`faz3-rerun`). Veritabanında `0010`un tekil indeksi ikinci katmandır.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from functools import partial
from pathlib import Path
from typing import Any

import psycopg

from football_edge.backtest.evaluate import clv_values
from football_edge.backtest.harness import replay
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.preregistration import PHASE, RERUN, Preregistration
from football_edge.backtest.strategies import EloPointInTime, Placebo
from football_edge.backtest.walkforward import (
    ELO_SCAFFOLD,
    Row,
    group_matches,
    group_rows,
    zone_of,
)
from football_edge.backtest.wf_eval import Summary, frozen_weights, summarise
from football_edge.backtest.wf_run import format_interval, model_strategies, score_table
from football_edge.history.catalog import Catalog
from football_edge.history.holdout import HOLDOUT, POST, open_holdout, period_of
from football_edge.history.lock import HistoryLock
from football_edge.history.sync import load_matches
from football_edge.history.types import HistMatch
from football_edge.market.devig import devig
from football_edge.market.metrics import Interval, bootstrap_mean

_OPENINGS = "SELECT purpose, git_sha FROM holdout_access_log WHERE purpose LIKE %s ORDER BY id"


class AlreadyOpened(RuntimeError):
    """Faz 3 holdout'u zaten açıldı; yeniden koşu kuralı karşılanmadı."""


class OpenedButFailed(RuntimeError):
    """Açılış KAYDA DÜŞTÜ ama değerlendirme tamamlanmadı: rapor yazılmaz, HANDOFF adıyla sayar."""


class HoldoutCountMismatch(OpenedButFailed):
    """Açılan holdout satır sayısı kilitteki sayıdan farklı."""


@dataclass(frozen=True)
class FinalReport:
    purpose: str
    holdout: Summary
    post: Summary
    placebo_holdout: Interval | None
    placebo_post: Interval | None
    holdout_rows: int
    predictions_sha256: str


def previous_openings(conn: psycopg.Connection[Any]) -> tuple[tuple[str, str], ...]:
    with conn.cursor() as cur:
        cur.execute(_OPENINGS, (f"{PHASE}%",))
        return tuple((str(row[0]), str(row[1])) for row in cur.fetchall())


def purpose_for(
    previous: Sequence[tuple[str, str]],
    *,
    prereg_sha256: str,
    git_sha: str,
    report_exists: bool,
    rerun_reason: str | None,
) -> str:
    """İlk açılış `faz3:<sha>`; yeniden koşu YALNIZ tek ilk açılıştan sonra, rapor yokken, aynı
    SHA ile ve adıyla (`faz3-rerun:<neden>:<sha>`)."""
    if not previous:
        if rerun_reason is not None:
            raise AlreadyOpened("yeniden koşu istendi ama önceki açılış yok")
        return f"{PHASE}:{prereg_sha256}"
    if rerun_reason is None or not rerun_reason.strip():
        raise AlreadyOpened(f"Faz 3 holdout'u zaten açıldı ({len(previous)} kayıt)")
    if len(previous) != 1 or report_exists or previous[0][1] != git_sha:
        raise AlreadyOpened("yeniden koşu kuralı: tek açılış, rapor yok ve aynı git SHA'sı")
    return f"{RERUN}:{rerun_reason.strip()}:{prereg_sha256}"


def check_holdout_count(lock: HistoryLock, leagues: Mapping[str, Sequence[HistMatch]]) -> int:
    expected = sum(periods[HOLDOUT].rows for periods in lock.leagues.values() if HOLDOUT in periods)
    found = sum(1 for matches in leagues.values() for m in matches if period_of(m.date) == HOLDOUT)
    if found != expected:
        raise HoldoutCountMismatch(f"holdout satırı {found}, kilitte {expected}")
    return found


def final_zone(match: HistMatch, kind: str) -> str | None:
    """Geliştirmede S/E (ağırlıklar yalnız buradan), sonra holdout ve sonrası bölgeleri."""
    period = period_of(match.date)
    return zone_of(match, kind) if period not in (HOLDOUT, POST) else period


Zoning = Callable[[HistMatch, str], str | None]


def rehearsal_zone(start: date, end: date) -> Zoning:
    """Prova (R135): [start, end) sahte holdout — geliştirme döneminin içinde, anahtarsız."""

    def zone(match: HistMatch, kind: str) -> str | None:
        if start <= match.date < end:
            return HOLDOUT
        return zone_of(match, kind)

    return zone


def _placebo(
    groups: Mapping[str, Sequence[HistMatch]],
    method: str,
    zone: Callable[[HistMatch], str | None],
) -> tuple[Interval | None, Interval | None]:
    """Placebo'nun holdout ve sonrası CLV'si (C3'ün yanındaki negatif kontrol)."""
    found: dict[str, list[float]] = {HOLDOUT: [], POST: []}
    for matches in groups.values():
        result = replay(matches, Placebo(devig=partial(devig, method=method)))
        for period, values in found.items():
            chosen = tuple(p for p in result.predictions if zone(matches[p.match_index]) == period)
            values.extend(clv_values(replace(result, predictions=chosen), method=method))
    holdout, post = (
        bootstrap_mean(values) if values else None for values in (found[HOLDOUT], found[POST])
    )
    return holdout, post


def evaluate_selected(
    leagues: Mapping[str, Sequence[HistMatch]],
    *,
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
    prereg: Preregistration,
    purpose: str,
    zoning: Zoning = final_zone,
) -> FinalReport:
    """Anahtar görmez: seçilmiş satırlar (DEV + HOLDOUT + POST) tam durumla oynatılır."""
    groups = group_matches(leagues, rating_groups)
    rows: list[Row] = []
    for matches in groups.values():
        strategies = {
            **model_strategies(matches, kinds, rating_groups, config),
            ELO_SCAFFOLD: EloPointInTime(groups=rating_groups),
        }
        rows.extend(group_rows(matches, kinds, strategies, method=config.method, zoning=zoning))
    targets = [(row.key.league, row.season) for row in rows if row.zone in (HOLDOUT, POST)]
    weights = frozen_weights(rows, targets)
    holdout, post = (
        summarise(
            rows,
            tau=prereg.tau,
            sensitivity=prereg.sensitivity,
            resamples=prereg.resamples,
            zone=zone,
            given=weights,
        )
        for zone in (HOLDOUT, POST)
    )
    placebo_holdout, placebo_post = _placebo(
        groups, config.method, lambda match: zoning(match, kinds[match.league])
    )
    digest = hashlib.sha256(
        "\n".join(
            f"{row.key}|{row.zone}|"
            + ",".join(f"{p:.9f}" for c in sorted(row.components) for p in row.components[c])
            for row in sorted(rows, key=lambda r: (r.key, r.zone))
            if row.zone in (HOLDOUT, POST)
        ).encode("utf-8")
    ).hexdigest()
    return FinalReport(
        purpose=purpose,
        holdout=holdout,
        post=post,
        placebo_holdout=placebo_holdout,
        placebo_post=placebo_post,
        holdout_rows=sum(1 for row in rows if row.zone == HOLDOUT),
        predictions_sha256=digest,
    )


def run_final(
    connect: Callable[[], psycopg.Connection[Any]],
    *,
    catalog: Catalog,
    lock: HistoryLock,
    config: ModelConfig,
    prereg: Preregistration,
    prereg_sha256: str,
    git_sha: str,
    now: datetime,
    report_path: Path,
    rerun_reason: str | None = None,
) -> FinalReport:
    """Kilit, yineleme ve sayım (açılıştan ÖNCE) → TAZE bağlantıda tek açılış → seçilmiş satırlar.

    Açılış kayda düştükten sonraki HER arıza `OpenedButFailed`dır (exit 14): yeniden koşu kuralı
    (R135) yalnız bu sınıfa bakar. 0010'un ikinci açılışı reddetmesi açılış değildir (exit 13).
    Süreç dışı ölüm (OOM, 137) burada yakalanamaz: Task 13'ün tablosu onu "kaydı say" diye okur.
    """
    with connect() as conn:
        # Kilit ve yineleme (C1) holdout dahil AÇILIŞTAN ÖNCE: ihlal açılış harcamaz.
        load_matches(conn, catalog, lock=lock)
        purpose = purpose_for(
            previous_openings(conn),
            prereg_sha256=prereg_sha256,
            git_sha=git_sha,
            report_exists=report_path.exists(),
            rerun_reason=rerun_reason,
        )
    with connect() as conn:
        try:
            key = open_holdout(conn, purpose=purpose, git_sha=git_sha, now=now)
        except psycopg.errors.UniqueViolation as error:
            raise AlreadyOpened(f"0010 ikinci açılışı reddetti: {error}") from error
        try:
            leagues = load_matches(conn, catalog, lock=lock, key=key)
        except Exception as error:
            raise OpenedButFailed(f"açılıştan sonra yükleme düştü: {error}") from error
        del key
    try:
        check_holdout_count(lock, leagues)
        return evaluate_selected(
            leagues,
            kinds={league.code: league.kind for league in catalog.leagues},
            rating_groups={league.code: league.country for league in catalog.leagues},
            config=config,
            prereg=prereg,
            purpose=purpose,
        )
    except OpenedButFailed:
        raise
    except Exception as error:
        raise OpenedButFailed(
            f"açılıştan sonra değerlendirme düştü: {type(error).__name__}: {error}"
        ) from error


def render_final(report: FinalReport, *, generated_at: datetime) -> str:
    """Yalnız toplu sayı; ham satır yok. C1–C6 ön kayıttaki adlarıyla."""
    return "\n".join(
        [
            f"# Faz 3 holdout raporu — {generated_at.date().isoformat()}",
            "",
            f"Açılış amacı `{report.purpose}` · holdout satırı {report.holdout_rows} · tahmin "
            f"özeti sha256 `{report.predictions_sha256}`. Tek açılış (R135); ağırlıklar ve "
            "hiperparametreler yalnız geliştirme döneminden.",
            "",
            *score_table("C1–C4 · holdout, ana ligler, 1X2 (ortak satırlar)", report.holdout.main),
            f"C1 ΔLL harman − piyasa: {format_interval(report.holdout.blend_gap)}",
            f"C3 Placebo CLV (negatif kontrol): {format_interval(report.placebo_holdout)}",
            "",
            *score_table("Holdout, ek ligler (yalnız model)", report.holdout.extra),
            *score_table("C5 · holdout, Ü/A 2.5", report.holdout.totals),
            *score_table("C6 · sonrası dönemi, tam durum", report.post.main),
            f"C6 ΔLL harman − piyasa: {format_interval(report.post.blend_gap)}",
            f"C6 Placebo CLV: {format_interval(report.placebo_post)}",
            "",
        ]
    )


def run_rehearsal(
    connect: Callable[[], psycopg.Connection[Any]],
    *,
    catalog: Catalog,
    lock: HistoryLock,
    config: ModelConfig,
    prereg: Preregistration,
    start: date,
    end: date,
) -> FinalReport:
    """Açılışın bütün yolu, anahtarsız ve kayıtsız: E'nin son sezonu sahte holdout olur."""
    with connect() as conn:
        leagues = load_matches(conn, catalog, lock=lock)
    return evaluate_selected(
        leagues,
        kinds={league.code: league.kind for league in catalog.leagues},
        rating_groups={league.code: league.country for league in catalog.leagues},
        config=config,
        prereg=prereg,
        purpose="prova",
        zoning=rehearsal_zone(start, end),
    )
```

`db/migrations/0010_holdout_phase.sql`:

<!-- plan: yeni db/migrations/0010_holdout_phase.sql -->
```sql
-- Faz 3: faz başına en çok bir holdout açılışı (Faz 3 tasarımı §8.3, R135).
--
-- `final_eval` açmadan önce `holdout_access_log`u sayar; bu indeks ikinci katmandır. Amaç
-- `<faz>:<ön kayıt sha256>` ya da `<faz>-rerun:<neden>:<sha256>` biçimindedir; ilk parçası (faz ya
-- da faz-rerun) tekildir: ikinci bir `faz3` açılışı ve ikinci bir `faz3-rerun` INSERT'te düşer.
-- Faz 2'nin biçimsiz amaçları (yok — sayım 0) ve başka amaçlar kapsam dışıdır. Tablo değişmez
-- (satır tetikleyicileri 0007'de): yalnız bir ifade indeksi eklenir.

create unique index if not exists holdout_access_log_one_per_phase
  on holdout_access_log ((split_part(purpose, ':', 1)))
  where purpose ~ '^faz[0-9]+(-rerun)?:';
```

`src/football_edge/history/sync.py` yaması:

<!-- plan: yama src/football_edge/history/sync.py -->
```diff
diff --git a/src/football_edge/history/sync.py b/src/football_edge/history/sync.py
index 74193d6..20f6cb7 100644
--- a/src/football_edge/history/sync.py
+++ b/src/football_edge/history/sync.py
@@ -16,6 +16,7 @@ kuralı (`tests/test_holdout_access_rule.py`) başka her anmayı kırmızıya ç
 from __future__ import annotations
 
 import logging
+from collections import Counter
 from collections.abc import Callable, Mapping, Sequence
 from dataclasses import dataclass
 from datetime import UTC, date, datetime
@@ -240,6 +241,26 @@ def _load_all(
     )
 
 
+class DuplicateMatches(ContractViolation):
+    """Aynı (lig, tarih, ev, deplasman) BÜTÜN dönemlerde (holdout dahil) iki kez geçti.
+
+    Faz 3 plan incelemesi C1: yineleme yalnız oynatmada yakalansaydı holdout'taki bir yineleme
+    açılıştan SONRA patlar ve tek açılışı harcardı. Denetim anahtar yokken, burada koşar; mesaj
+    holdout satırını (tarih, ad) dışarı vermez — yalnız lig ve sayı.
+    """
+
+
+def _refuse_duplicates(everything: Mapping[str, Sequence[HistMatch]]) -> None:
+    found = {
+        code: sum(n - 1 for n in Counter((m.date, m.home, m.away) for m in matches).values())
+        for code, matches in everything.items()
+    }
+    repeated = {code: count for code, count in sorted(found.items()) if count}
+    if repeated:
+        detail = ", ".join(f"{code} ×{count}" for code, count in repeated.items())
+        raise DuplicateMatches(f"{SOURCE_ID}: yinelenen maç (bütün dönemler, 14g): {detail}")
+
+
 def load_matches(
     conn: psycopg.Connection[Any],
     catalog: Catalog,
@@ -254,6 +275,7 @@ def load_matches(
     `select_periods`te `HoldoutLocked` verir.
     """
     everything = _load_all(conn, catalog)
+    _refuse_duplicates(everything)
     if lock is not None:
         verify_lock(lock, everything)
     periods = _OPEN_PERIODS if key is None else _OPEN_PERIODS | {HOLDOUT}
```

`src/football_edge/backtest/__main__.py` yaması:

<!-- plan: yama src/football_edge/backtest/__main__.py -->
```diff
--- a/src/football_edge/backtest/__main__.py
+++ b/src/football_edge/backtest/__main__.py
@@ -2,7 +2,7 @@
 
 `selftest`: bilinen sonuçlar. `select`: S bölgesinde hiperparametre seçimi →
 `config/model_faz3.yaml` (controller commit'ler). `walkforward`: dondurulmuş yapılandırmayla E
-bölgesi raporu.
+bölgesi raporu. `final-eval`: Faz 3'ün TEK holdout açılışı (`backtest/final_eval.py`, R135).
 
 Önce kilit: kilit dosyası bozuksa ya da önbellek kilitli dönemlerin özetinden farklıysa hiçbir
 ölçüm koşmaz (exit 9). Sonra her denetim adıyla loglanır; kapı denetimlerinden biri kırmızıysa
@@ -14,11 +14,18 @@
 import argparse
 import logging
 from collections.abc import Callable, Mapping, Sequence
-from datetime import UTC, datetime
+from datetime import UTC, date, datetime
 from pathlib import Path
 from types import MappingProxyType
 
 from football_edge.backtest.evaluate import DEFAULT_RESAMPLES
+from football_edge.backtest.final_eval import (
+    AlreadyOpened,
+    OpenedButFailed,
+    render_final,
+    run_final,
+    run_rehearsal,
+)
 from football_edge.backtest.model_config import (
     MODEL_CONFIG_PATH,
     ModelConfig,
@@ -26,6 +33,12 @@
     dump_model_config,
     file_sha256,
     load_model_config,
+)
+from football_edge.backtest.preregistration import (
+    PREREGISTRATION_PATH,
+    PreflightError,
+    preflight,
+    real_git,
 )
 from football_edge.backtest.selection import select
 from football_edge.backtest.selftest import Check, run_selftest
@@ -38,8 +51,10 @@
     run_rows,
 )
 from football_edge.collect import configure_logging
+from football_edge.collector import ContractViolation
 from football_edge.db import connect
 from football_edge.history.catalog import MAIN, Catalog, load_catalog
+from football_edge.history.holdout import DEV_END
 from football_edge.history.lock import LockViolation, load_lock
 from football_edge.history.sync import load_matches
 from football_edge.history.types import HistMatch
@@ -55,7 +70,13 @@
 # 10 köprünün (`market bridge`) "eşleşme yok"u; 11: model yapılandırması okunamadı ya da
 # katalog/kilit yapılandırmadaki özetle uyuşmuyor — walk-forward koşmaz.
 EXIT_CONFIG_MISMATCH = 11
+# final-eval: 12 ön kayıt denetimi tutmadı (AÇILMADI); 13 Faz 3 açılışı zaten var (AÇILMADI);
+# 14 AÇILDI ama değerlendirme tamamlanmadı (rapor yok) — HANDOFF'a adıyla, R135 yeniden koşusu.
+EXIT_PREFLIGHT = 12
+EXIT_ALREADY_OPENED = 13
+EXIT_OPENED_FAILED = 14
 DEFAULT_TAU = 0.02  # R139
+REHEARSAL_START = date(2024, 7, 1)  # prova: E'nin son sezonu (R135)
 DEFAULT_SENSITIVITY = (0.0, 0.05)
 
 
@@ -80,6 +101,18 @@
     walk.add_argument("--out", type=Path, required=True)
     walk.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
     walk.add_argument("--gap", action="store_true", help="R128 boşluk cezası (iki ek koşu)")
+    final = commands.add_parser("final-eval", help="Faz 3'ün tek, kayıtlı holdout açılışı")
+    final.add_argument("--prereg", type=Path, default=PREREGISTRATION_PATH)
+    final.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
+    final.add_argument("--lock", type=Path, default=LOCK_PATH)
+    final.add_argument("--catalog", type=Path, default=CATALOG_PATH)
+    final.add_argument("--out", type=Path, required=True)
+    final.add_argument("--rerun-reason", default=None)
+    final.add_argument(
+        "--rehearse",
+        action="store_true",
+        help="prova: E'nin son sezonu sahte holdout, anahtarsız, AÇILIŞ YOK",
+    )
     return parser
 
 
@@ -218,8 +251,69 @@
     return 0
 
 
+def _final_eval(args: argparse.Namespace) -> int:
+    git = real_git()
+    try:
+        prereg = preflight(
+            prereg_path=args.prereg,
+            model_path=args.config,
+            lock_path=args.lock,
+            catalog_path=args.catalog,
+            git=git,
+        )
+        config = load_model_config(args.config)
+        if args.rehearse:
+            report = run_rehearsal(
+                connect,
+                catalog=load_catalog(args.catalog),
+                lock=load_lock(args.lock),
+                config=config,
+                prereg=prereg,
+                start=REHEARSAL_START,
+                end=DEV_END,
+            )
+            args.out.write_text(
+                render_final(report, generated_at=datetime.now(UTC)), encoding="utf-8"
+            )
+            LOGGER.info("prova raporu yazıldı: %s — holdout AÇILMADI", args.out)
+            return 0
+        report = run_final(
+            connect,
+            catalog=load_catalog(args.catalog),
+            lock=load_lock(args.lock),
+            config=config,
+            prereg=prereg,
+            prereg_sha256=file_sha256(args.prereg),
+            git_sha=git.head(),
+            now=datetime.now(UTC),
+            report_path=args.out,
+            rerun_reason=args.rerun_reason,
+        )
+    except (PreflightError, ModelConfigError, LockViolation, ContractViolation) as error:
+        LOGGER.error("holdout AÇILMADI — ön denetim: %s", error)
+        return EXIT_PREFLIGHT
+    except AlreadyOpened as error:
+        LOGGER.error("holdout AÇILMADI — %s", error)
+        return EXIT_ALREADY_OPENED
+    except OpenedButFailed as error:
+        LOGGER.error("holdout AÇILDI ama rapor yazılmadı: %s", error)
+        return EXIT_OPENED_FAILED
+    try:
+        args.out.write_text(render_final(report, generated_at=datetime.now(UTC)), encoding="utf-8")
+    except Exception as error:
+        LOGGER.error("holdout AÇILDI ama rapor yazılamadı: %s", error)
+        return EXIT_OPENED_FAILED
+    LOGGER.info("holdout raporu yazıldı: %s (amaç %s)", args.out, report.purpose)
+    return 0
+
+
 COMMANDS: Mapping[str, Callable[[argparse.Namespace], int]] = MappingProxyType(
-    {"selftest": _selftest, "select": _select, "walkforward": _walkforward}
+    {
+        "selftest": _selftest,
+        "select": _select,
+        "walkforward": _walkforward,
+        "final-eval": _final_eval,
+    }
 )
 
 
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_final_eval.py tests/test_holdout_phase_db.py tests/test_holdout_access_rule.py tests/test_history_sync.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — test_final_eval 32 · test_holdout_access_rule 81 · test_history_sync 21 passed · test_holdout_phase_db 1 SKIP (`DATABASE_URL yok` — adıyla; kırmızı/yeşil kanıtı dalga 4 sonunda gerçek veritabanında)

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `purpose_for`: `report_exists or` silinir | `tests/test_final_eval.py::test_a_second_opening_is_refused_unless_the_rerun_rule_holds` |
| 2 | `run_final`: açılış öncesi `load_matches(conn, catalog, lock=lock)` silinir | `tests/test_final_eval.py::test_a_lock_violation_stops_before_open` |
| 3 | `run_final`: `del key`ten önce `kept = key` | `tests/test_holdout_access_rule.py::test_the_real_final_eval_hands_the_key_only_to_load_matches` |
| 4 | `preflight`: temiz ağaç denetimi `if False:` | `tests/test_final_eval.py::test_preflight_refuses_before_anything_opens` |
| 5 | `run_final`: `check_holdout_count(...)` silinir | `tests/test_final_eval.py::test_a_holdout_count_that_differs_from_the_lock_fails_after_the_opening` |
| 6 | `history/sync.py` `load_matches`: `_OPEN_PERIODS | {HOLDOUT}` → `_OPEN_PERIODS` | `tests/test_history_sync.py::test_a_key_from_open_holdout_returns_the_holdout_rows_once_logged` |
| 7 | `private_accesses`: öznitelik kuralı `and False` | `tests/test_holdout_access_rule.py::test_private_parser_helpers_are_closed_outside_history` |
| 8 | `load_matches`: `_refuse_duplicates(everything)` silinir (inceleme C1) | `tests/test_history_sync.py::test_a_duplicate_inside_the_holdout_is_refused_before_any_key_exists` |
| 9 | `run_final`: açılış sonrası `except Exception` → `except KeyError` (inceleme I4) | `tests/test_final_eval.py::test_any_failure_after_the_opening_is_reported_as_opened` |
| 10 | `run_final`: `except psycopg.errors.UniqueViolation` → `except KeyError` | `tests/test_final_eval.py::test_the_phase_index_rejecting_the_insert_is_not_an_opening` |
| 11 | CLI `final-eval`: ön denetim `except`inden `ContractViolation` düşer | `tests/test_final_eval.py::test_the_cli_names_where_it_stopped` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add src/football_edge/backtest/preregistration.py \
  src/football_edge/backtest/final_eval.py \
  db/migrations/0010_holdout_phase.sql \
  src/football_edge/history/sync.py \
  src/football_edge/backtest/__main__.py \
  tests/test_final_eval.py \
  tests/test_holdout_phase_db.py \
  tests/test_holdout_access_rule.py \
  tests/test_history_sync.py
git commit -m "feat: Faz 3 P5 — final_eval (ön kayıt, tek kayıtlı açılış, prova), 0010, anahtar akışı ve 14h kuralı

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
### Task 11: Canlı gölge tahmin, E3 eşitlik raporu, 0009/0011, `shadow.yml` (R132, R134)

**Kademe:** K1 · **Dalga:** 4 · **Worktree/dal:** `.worktrees/wt-shadow` · `feat/faz3-shadow`

> **İz A'ya bağlı (canlı kapsam):** gölge defterdeki maçları işler; defter yalnız `config/leagues.yaml`ın AKTİF liglerinden dolar — bugün 8 (aut.1 kapalı, snapshot'ı yok). Testler sentetik lig kimliğiyle; kod lig sayısına bağlı değildir.

Tasarım §10. `live shadow` salı ve cuma karar anından sonra (pg_cron `35 12 * * 2,5`, 0011) kararı verilmiş maçların bileşen olasılıklarını (piyasa, fit Elo, DC) ve karar anı fiyatını append-only `model_predictions`a (0009) yazar; yayın ve kredi YOK (P19). Aynı (grup, karar anı) için durum bir kez kurulur. `live parity` (E3) sonrası dönemde defter ↔ taban eşleşmelerinin yapısal alanlarını karşılaştırır; sezon ya da > 30 dk başlama farkı exit 15 (P12, P21). 0011 cuma 09:50 UTC'ye tarihsel senkron ekler (R132). Bekçi `shadow.yml`i 4 gün 12 sa eşiğiyle izler.

**Files:**
- Create: `db/migrations/0009_model_predictions.sql`
- Create: `db/migrations/0011_shadow_dispatch.sql`
- Create: `src/football_edge/live/shadow.py`
- Create: `src/football_edge/live/__main__.py`
- Create: `.github/workflows/shadow.yml`
- Create: `tests/test_shadow.py`
- Create: `tests/test_shadow_workflow.py`
- Modify: `scripts/ops_alert.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `tests/test_ops_alert.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `tests/test_history_dispatch.py` (yama aşağıda, `git apply` ile uygulanır)

**Interfaces:**
- Consumes: Task 7 (`ModelConfig`, `file_sha256`, CLI sabitleri `kinds_of`, `rating_groups`), Task 8 (`build_batch`, `live_key`, `naming_from`, `season_of`, `load_live_matches`, `load_quotes`), Task 6 (`DixonColesStrategy`, bileşen adları), Task 2.
- Produces: `ShadowRow`, `shadow_rows`, `write_shadow`; CLI `python -m football_edge.live {shadow,parity}`, `parity`, `ParityReport`, `EXIT_PARITY = 15`, `KICKOFF_TOLERANCE`; migration'lar 0009, 0011; `shadow.yml`; bekçi tetiği.

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_shadow.py`:

<!-- plan: yeni tests/test_shadow.py -->
```python
"""Canlı gölge tahmin (Faz 3 tasarımı §10, R134) ve eşitlik raporu E3. Veritabanı yok; veri
SENTETİK (tests/model_builders.py) — canlı taraf aynı maçları defter biçiminde taşır."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.backtest.harness import replay
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.timeline import decision_at
from football_edge.backtest.walkforward import DC, ELO, MARKET, group_matches
from football_edge.history.catalog import MAIN
from football_edge.history.types import H2H, PRE_CLOSING
from football_edge.live import __main__ as live_cli
from football_edge.live.context import LiveMatch, Quote, build_batch, naming_from
from football_edge.live.shadow import ShadowRow, shadow_rows, write_shadow
from football_edge.market.devig import POWER, devig
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModel, EloModelConfig
from tests.model_builders import season

GROUPS = MappingProxyType({"E0": "Ülke"})
KINDS = MappingProxyType({"E0": MAIN})
HISTORY = (
    *season("2526", datetime(2025, 8, 2).date(), seed=4),
    *season("2627", datetime(2026, 8, 1).date(), seed=5),
)
GROUP = group_matches({"E0": HISTORY}, GROUPS)["Ülke"]
NAMING = naming_from({"E0": HISTORY}, {"t.1": "E0"}, MappingProxyType({}))
CONFIG = ModelConfig("x", "c", "l", POWER, EloModelConfig(), DCConfig(min_matches=40), 7, 0.02, ())
SHA256 = "e" * 64
GIT = "f" * 40


def _slot_matches(week_day: datetime) -> list[int]:
    return [index for index, m in enumerate(GROUP) if m.date == week_day.date()]


def _batch(indexes: list[int]) -> Any:
    live = [
        LiveMatch(f"id-{i}", "t.1", GROUP[i].kickoff, GROUP[i].home, GROUP[i].away) for i in indexes
    ]  # type: ignore[arg-type]
    decided = decision_at(GROUP[indexes[0]].date, GROUP[indexes[0]].kickoff)
    assert decided is not None
    quotes = [
        Quote(m.match_id, decided - timedelta(hours=4), "b1", "h2h", name, price)
        for m, i in zip(live, indexes, strict=True)
        for name, price in zip(
            (m.home, "Draw", m.away), GROUP[i].prices("Avg", H2H, PRE_CLOSING) or (), strict=True
        )
    ]
    return build_batch(
        live,
        quotes,
        {"Ülke": GROUP},
        now=decided + timedelta(minutes=35),
        naming=NAMING,
        kinds=KINDS,
        rating_groups=GROUPS,
    )


def test_each_decided_match_gets_market_elo_and_dixon_coles_rows() -> None:
    indexes = _slot_matches(datetime(2026, 10, 3))
    batch = _batch(indexes)

    rows = shadow_rows(
        batch, config=CONFIG, rating_groups=GROUPS, config_sha256=SHA256, git_sha=GIT
    )

    assert len(batch.decisions) == len(indexes) == 4
    assert {(row.match_id, row.strategy) for row in rows} == {
        (f"id-{i}", name) for i in indexes for name in (DC, ELO, MARKET)
    }
    for row in rows:
        assert sum(row.probs) == pytest.approx(1.0)
        assert (row.model_config_sha256, row.git_sha) == (SHA256, GIT)


@pytest.mark.leakage
def test_shadow_elo_equals_the_replayed_prediction() -> None:
    """E2'nin gölge yolu: grup başına bir kez kurulan durum harness'ın tahminini verir."""
    indexes = _slot_matches(datetime(2026, 10, 3))
    replayed = {
        p.match_index: p.probs
        for p in replay(GROUP, EloModel(config=CONFIG.elo, groups=GROUPS)).predictions
    }

    rows = shadow_rows(
        _batch(indexes), config=CONFIG, rating_groups=GROUPS, config_sha256=SHA256, git_sha=GIT
    )

    for row in rows:
        if row.strategy == ELO:
            index = int(row.match_id.removeprefix("id-"))
            assert row.probs == pytest.approx(replayed[index])


def test_the_market_row_is_the_devigged_pre_price() -> None:
    (index, *_) = _slot_matches(datetime(2026, 10, 3))
    rows = shadow_rows(
        _batch([index]), config=CONFIG, rating_groups=GROUPS, config_sha256=SHA256, git_sha=GIT
    )

    (market,) = [row for row in rows if row.strategy == MARKET]
    assert market.probs == pytest.approx(devig(market.pre, POWER))
    assert market.pre == GROUP[index].prices("Avg", H2H, PRE_CLOSING)


class _Cursor:
    def __init__(self, log: list[tuple[str, tuple[Any, ...]]], seen: set[tuple[Any, ...]]) -> None:
        self.log, self.seen, self.rowcount = log, seen, 0

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.log.append((sql, params))
        key = (params[0], params[2], params[10])
        self.rowcount = 0 if key in self.seen else 1
        self.seen.add(key)


class _Connection:
    def __init__(self) -> None:
        self.log: list[tuple[str, tuple[Any, ...]]] = []
        self.seen: set[tuple[Any, ...]] = set()
        self.commits = 0

    def cursor(self) -> _Cursor:
        return _Cursor(self.log, self.seen)

    def commit(self) -> None:
        self.commits += 1


def test_rows_are_written_once_per_match_strategy_and_config() -> None:
    row = ShadowRow(
        "m1",
        "E0|2026-10-03|Alfa|Beta",
        ELO,
        (0.5, 0.3, 0.2),
        (2.0, 3.3, 4.0),
        datetime(2026, 10, 2, 11, tzinfo=UTC),
        SHA256,
        GIT,
    )
    conn = _Connection()

    assert write_shadow(conn, (row, row, replace(row, strategy=DC))) == 2  # type: ignore[arg-type]
    assert conn.commits == 1
    sql, params = conn.log[0]
    assert "ON CONFLICT (match_id, strategy, model_config_sha256) DO NOTHING" in sql
    assert params == (
        "m1",
        row.match_key,
        ELO,
        0.5,
        0.3,
        0.2,
        2.0,
        3.3,
        4.0,
        row.decided_at,
        SHA256,
        GIT,
    )


def test_parity_pairs_live_matches_and_flags_a_shifted_kickoff() -> None:
    target = GROUP[-3]
    assert target.kickoff is not None
    good = LiveMatch("a", "t.1", target.kickoff, target.home.upper(), target.away)
    shifted = replace(good, match_id="b", kickoff=target.kickoff + timedelta(hours=1))
    stranger = LiveMatch("c", "t.1", target.kickoff, "Yok", target.away)

    report = live_cli.parity(
        [good, stranger], {"E0": HISTORY}, codes={"t.1": "E0"}, aliases={}, kinds=KINDS
    )
    bad = live_cli.parity([shifted], {"E0": HISTORY}, codes={"t.1": "E0"}, aliases={}, kinds=KINDS)

    assert (report.paired, report.unmatched, report.season_mismatch, report.kickoff_mismatch) == (
        1,
        1,
        0,
        0,
    )
    assert bad.kickoff_mismatch == 1
```

`tests/test_shadow_workflow.py`:

<!-- plan: yeni tests/test_shadow_workflow.py -->
```python
"""`shadow.yml`: yalnız pg_cron (0011), secret yalnız gölge adımında, çıkış kodları adıyla."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.workflow_helpers import (
    REPO,
    _allow_list,
    _cron_jobs,
    _functions,
    _index_of,
    _steps,
    _triggers,
)

SHADOW = REPO / ".github/workflows/shadow.yml"
COMMAND = "football_edge.live shadow"
FAKE_UV = """\
#!/usr/bin/env bash
echo "$*" >> "$CALLS"
exit "${FAIL_CODE:-0}"
"""


def test_shadow_is_dispatched_by_pg_cron_after_the_decision_on_tuesday_and_friday() -> None:
    spec, command = _cron_jobs()["shadow-dispatch"]

    assert command == "select ops.dispatch_shadow()"
    assert spec == "35 12 * * 2,5"
    assert "ops.dispatch_workflow('shadow.yml')" in _functions()["dispatch_shadow"]
    assert "shadow.yml" in _allow_list()
    assert set(_triggers(SHADOW)) == {"workflow_dispatch"}


def test_only_the_shadow_step_gets_the_database() -> None:
    steps = _steps(SHADOW)
    index = _index_of(steps, COMMAND)
    holders = [i for i, step in enumerate(steps) if "DATABASE_URL" in str(step.get("env", {}))]

    assert index is not None and holders == [index]
    assert _index_of(steps, "scripts/check_secrets.sh") is not None
    assert _index_of(steps, "scripts/check_secrets.sh") < index  # type: ignore[operator]


@pytest.mark.parametrize(
    ("code", "named"), [(0, ""), (9, "kilit"), (11, "yapılandırması"), (3, "beklenmedik")]
)
def test_the_shadow_step_names_every_exit_code_and_keeps_the_run_red(
    tmp_path: Path, code: int, named: str
) -> None:
    fake = tmp_path / "uv"
    fake.write_text(FAKE_UV, encoding="utf-8")
    fake.chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAIL_CODE": str(code),
    }
    body = str(_steps(SHADOW)[_index_of(_steps(SHADOW), COMMAND)]["run"])  # type: ignore[index]

    result = subprocess.run(
        ["bash", "-e", "-c", body], env=env, capture_output=True, text=True, timeout=30, check=False
    )

    errors = [line for line in result.stdout.splitlines() if line.startswith("::error::")]
    assert calls.read_text(encoding="utf-8").splitlines() == [f"run python -m {COMMAND}"]
    assert result.returncode == code
    if code == 0:
        assert errors == []
    else:
        assert len(errors) == 1 and named in errors[0] and f"exit {code}" in errors[0], errors


@pytest.mark.parametrize("name", ["shadow.yml", "history.yml"])
def test_the_credit_free_workflows_never_receive_the_odds_api_key(name: str) -> None:
    """m10: gölge ve (cuma ek turu dahil) tarihsel senkron KREDİ harcamaz — anahtar hiç verilmez."""
    text = (REPO / ".github/workflows" / name).read_text(encoding="utf-8")

    assert "ODDS" + "_API_KEY" not in text
```

`tests/test_ops_alert.py` yaması:

<!-- plan: yama tests/test_ops_alert.py -->
```diff
diff --git a/tests/test_ops_alert.py b/tests/test_ops_alert.py
index 1a3f535..4f1409b 100644
--- a/tests/test_ops_alert.py
+++ b/tests/test_ops_alert.py
@@ -308,6 +308,7 @@ FRESH = {
     "collect-news.yml": [_workflow_run("workflow_dispatch", timedelta(hours=3, minutes=59))],
     "footystats-local.yml": [_workflow_run("workflow_dispatch", timedelta(hours=71))],
     "history.yml": [_workflow_run("workflow_dispatch", timedelta(days=7, hours=23))],
+    "shadow.yml": [_workflow_run("workflow_dispatch", timedelta(days=4, hours=11))],
 }
 STALE_SNAPSHOT = [_workflow_run("workflow_dispatch", timedelta(hours=31))]
 
@@ -777,3 +778,16 @@ def test_a_stale_history_trigger_is_named_in_the_watchdog_alarm() -> None:
     assert alarm["title"] == WATCHDOG_ALARM
     for needle in ("history.yml: ", "history-dispatch"):
         assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"
+
+
+def test_a_stale_shadow_trigger_is_named_in_the_watchdog_alarm() -> None:
+    """Gölge tahminin tek tetiği pg_cron (0011): cuma → salı 4 gün, eşik 4 gün 12 sa."""
+    stale = [_workflow_run("workflow_dispatch", timedelta(days=4, hours=13))]
+    fake = FakeGitHub(runs={**FRESH, "shadow.yml": stale})
+
+    assert _watchdog(fake) == 0
+
+    (alarm,) = fake.issues
+    assert alarm["title"] == WATCHDOG_ALARM
+    for needle in ("shadow.yml: ", "shadow-dispatch"):
+        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"
```

`tests/test_history_dispatch.py` yaması:

<!-- plan: yama tests/test_history_dispatch.py -->
```diff
diff --git a/tests/test_history_dispatch.py b/tests/test_history_dispatch.py
index 7da8dcf..b7997fa 100644
--- a/tests/test_history_dispatch.py
+++ b/tests/test_history_dispatch.py
@@ -33,3 +33,12 @@ def test_history_dispatch_runs_weekly_outside_time_critical_minutes() -> None:
     assert re.fullmatch(r"\d+", minute) and int(minute) not in taken, (minute, sorted(taken))
     assert re.fullmatch(r"\d+", hour), hour
     assert (day, month, weekday) == ("*", "*", "2"), "haftada bir, salı değil"
+
+
+def test_history_is_also_synced_on_friday_before_the_friday_decision() -> None:
+    """R132: cuma kararından önce taban bir kez daha tazelenir; aynı fonksiyon, ayrı iş."""
+    spec, command = _cron_jobs()["history-dispatch-friday"]
+    minute, hour, day, month, weekday = spec.split()
+
+    assert command == "select ops.dispatch_history()"
+    assert (minute, hour, day, month, weekday) == ("50", "9", "*", "*", "5")
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_shadow.py tests/test_shadow_workflow.py tests/test_ops_alert.py tests/test_history_dispatch.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.live.shadow'`; `KeyError: 'shadow-dispatch'`; bekçi testi `shadow.yml` izlenmediği için alarm açmaz

- [ ] **Step 3: Uygulamayı yaz**

`db/migrations/0009_model_predictions.sql`:

<!-- plan: yeni db/migrations/0009_model_predictions.sql -->
```sql
-- Faz 3: canlı gölge tahminleri (Faz 3 tasarımı §10, R134). YAYIN YOK.
--
-- Salı ve cuma karar anından sonra `live shadow` aktif liglerin kararı verilmiş maçları için
-- bileşen olasılıklarını (piyasa, fit Elo, Dixon-Coles) ve karar anındaki kapanış öncesi fiyatı
-- yazar. Harman ve bahis bu satırlardan, dondurulmuş ağırlıkla haftalık raporda hesaplanır: bütün
-- girdiler karar anının bilgisidir. Satır append-only: bir tahmin sonradan değiştirilemez, silinemez,
-- tablo boşaltılamaz — gölge sicil ancak böyle kanıt olur.

create table if not exists model_predictions (
  id                   bigserial primary key,
  match_id             text not null references matches(id),
  match_key            text not null,
  strategy             text not null,
  p_home               double precision not null check (p_home >= 0 and p_home <= 1),
  p_draw               double precision not null check (p_draw >= 0 and p_draw <= 1),
  p_away               double precision not null check (p_away >= 0 and p_away <= 1),
  pre_home             numeric not null check (pre_home > 1.0),
  pre_draw             numeric not null check (pre_draw > 1.0),
  pre_away             numeric not null check (pre_away > 1.0),
  decided_at           timestamptz not null,
  model_config_sha256  text not null check (model_config_sha256 ~ '^[0-9a-f]{64}$'),
  git_sha              text not null check (git_sha ~ '^[0-9a-f]{40}$'),
  recorded_at          timestamptz not null default now(),
  unique (match_id, strategy, model_config_sha256)
);

create index if not exists model_predictions_decided_idx on model_predictions (decided_at);

-- API rolleri tabloya erişemez (R90 deseni): RLS açık, politika yok.
alter table model_predictions enable row level security;

drop trigger if exists model_predictions_append_only on model_predictions;
create trigger model_predictions_append_only
  before update or delete on model_predictions
  for each row execute function forbid_ledger_mutation();

drop trigger if exists model_predictions_no_truncate on model_predictions;
create trigger model_predictions_no_truncate
  before truncate on model_predictions
  for each statement execute function forbid_ledger_mutation();
```

`db/migrations/0011_shadow_dispatch.sql`:

<!-- plan: yeni db/migrations/0011_shadow_dispatch.sql -->
```sql
-- Faz 3: gölge tahmin işi (shadow.yml) ve tarihsel tabanın cuma senkronu pg_cron'dan (R132, R134).
--
-- NEDEN: gölge tahmin karar anından (salı/cuma 12:00 Londra) SONRA koşmalı; GitHub'ın `schedule`ı
-- güvenilmez (0003). Canlı `observe` akışı football-data'nın sonrası dönemidir: cuma kararından önce
-- tabanı bir kez daha tazelemek, bayat durum korumasının düşürdüğü tahmin sayısını azaltır (ücretsiz).
--
-- NE: izinli listeye `shadow.yml` eklenir (`create or replace` listeyi BAŞTAN yazar: 0008'in beş adı
-- da burada). `history-dispatch-friday` aynı `ops.dispatch_history()`i cuma 09:50 UTC'de çağırır.

create or replace function ops.dispatch_workflow(p_workflow text) returns bigint
language plpgsql
set search_path = ''
as $$
declare
  token text;
begin
  if p_workflow is null or not (p_workflow = any (array[
    'seal.yml', 'snapshot.yml', 'collect-daily.yml', 'collect-news.yml', 'history.yml',
    'shadow.yml'
  ])) then
    raise exception 'ops.dispatch_workflow: izinli listede olmayan workflow: %', p_workflow;
  end if;

  select decrypted_secret into token
  from vault.decrypted_secrets
  where name = 'github_seal_dispatch';

  if token is null or token = '' then
    raise exception 'ops.dispatch_workflow: Vault secret github_seal_dispatch yok — % tetiklenmedi',
      p_workflow;
  end if;

  return net.http_post(
    url := 'https://api.github.com/repos/popiliadam/football-edge/actions/workflows/'
           || p_workflow || '/dispatches',
    body := jsonb_build_object('ref', 'main'),
    headers := jsonb_build_object(
      'Accept', 'application/vnd.github+json',
      'Authorization', 'Bearer ' || token,
      'Content-Type', 'application/json',
      'User-Agent', 'football-edge-pg-cron',
      'X-GitHub-Api-Version', '2022-11-28'
    ),
    timeout_milliseconds := 10000
  );
end;
$$;

create or replace function ops.dispatch_shadow() returns bigint
language plpgsql
set search_path = ''
as $$
begin
  return ops.dispatch_workflow('shadow.yml');
end;
$$;

revoke all on function ops.dispatch_workflow(text) from public, anon, authenticated;
revoke all on function ops.dispatch_shadow() from public, anon, authenticated;

-- Salı ve cuma 12:35 UTC: 12:00 Londra yaz saatinde 11:00, kışın 12:00 UTC — ikisinden de sonra.
-- Dakika mühür (:00/:15/:30/:45) ve snapshot (:22) dakikalarının dışında.
select cron.schedule('shadow-dispatch', '35 12 * * 2,5', 'select ops.dispatch_shadow()');
-- Cuma 09:50 UTC: salı işinin ikizi (0008), cuma kararından önce.
select cron.schedule('history-dispatch-friday', '50 9 * * 5', 'select ops.dispatch_history()');
```

`src/football_edge/live/shadow.py`:

<!-- plan: yeni src/football_edge/live/shadow.py -->
```python
"""Canlı gölge tahmin (Faz 3 tasarımı §10, R134): kararı verilmiş maçların bileşen olasılıkları.

Yayın YOK. Aynı (grup, karar anı) için durum BİR kez kurulur: `observe` akışı o karardaki bütün
maçlar için aynıdır. Harman ve bahis bu satırlardan, dondurulmuş ağırlıkla sonradan hesaplanır —
satır karar anının bütün girdisini (bileşenler, kapanış öncesi fiyat) taşır.
"""

from __future__ import annotations

import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg

from football_edge.backtest.harness import Strategy
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.walkforward import DC, ELO, MARKET
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, OddsKey
from football_edge.live.context import REFERENCE_BOOK, LiveBatch, LiveDecision
from football_edge.market.devig import InvalidPrices, devig
from football_edge.model.elo_model import EloModel
from football_edge.model.strategies import DixonColesStrategy

_INSERT = """
    INSERT INTO model_predictions
      (match_id, match_key, strategy, p_home, p_draw, p_away, pre_home, pre_draw, pre_away,
       decided_at, model_config_sha256, git_sha)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (match_id, strategy, model_config_sha256) DO NOTHING
"""


@dataclass(frozen=True)
class ShadowRow:
    match_id: str
    match_key: str
    strategy: str
    probs: tuple[float, float, float]
    pre: tuple[float, float, float]
    decided_at: datetime
    model_config_sha256: str
    git_sha: str


def _pre(decision: LiveDecision) -> tuple[float, float, float]:
    home, draw, away = (
        decision.record.pre_prices[OddsKey(REFERENCE_BOOK, H2H, outcome, PRE_CLOSING)]
        for outcome in RESULTS
    )
    return home, draw, away


def _states(
    decisions: Sequence[LiveDecision], config: ModelConfig, rating_groups: Mapping[str, str]
) -> dict[tuple[str, datetime], dict[str, Strategy]]:
    """(grup, karar anı) → gözlenmiş stratejiler; akış aynı olduğu için bir kez."""
    found: dict[tuple[str, datetime], dict[str, Strategy]] = {}
    for decision in decisions:
        slot = (
            rating_groups.get(decision.record.key.league, decision.record.key.league),
            decision.context.decision_at,
        )
        if slot in found:
            continue
        states: dict[str, Strategy] = {
            ELO: EloModel(config=config.elo, groups=rating_groups),
            DC: DixonColesStrategy(
                config=config.dixon_coles, groups=rating_groups, cadence_days=config.cadence_days
            ),
        }
        for result in decision.results:
            states = {name: state.observe(result) for name, state in states.items()}
        found[slot] = states
    return found


def shadow_rows(
    batch: LiveBatch,
    *,
    config: ModelConfig,
    rating_groups: Mapping[str, str],
    config_sha256: str,
    git_sha: str,
) -> tuple[ShadowRow, ...]:
    states = _states(batch.decisions, config, rating_groups)
    rows: list[ShadowRow] = []
    for decision in batch.decisions:
        key = decision.record.key
        pre = _pre(decision)
        found: dict[str, tuple[float, ...]] = {}
        with contextlib.suppress(InvalidPrices):
            found[MARKET] = devig(pre, config.method)
        slot = (rating_groups.get(key.league, key.league), decision.context.decision_at)
        for name, state in states[slot].items():
            prediction = state.predict(decision.context)
            if prediction is not None:
                found[name] = prediction.probs
        rows.extend(
            ShadowRow(
                match_id=decision.match_id,
                match_key=f"{key.league}|{key.date.isoformat()}|{key.home}|{key.away}",
                strategy=name,
                probs=(probs[0], probs[1], probs[2]),
                pre=pre,
                decided_at=decision.context.decision_at,
                model_config_sha256=config_sha256,
                git_sha=git_sha,
            )
            for name, probs in sorted(found.items())
        )
    return tuple(rows)


def write_shadow(conn: psycopg.Connection[Any], rows: Sequence[ShadowRow]) -> int:
    """Satırları yazar ve commit'ler; aynı (maç, strateji, yapılandırma) ikinci kez yazılmaz."""
    written = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                _INSERT,
                (
                    row.match_id,
                    row.match_key,
                    row.strategy,
                    *row.probs,
                    *row.pre,
                    row.decided_at,
                    row.model_config_sha256,
                    row.git_sha,
                ),
            )
            written += max(cur.rowcount, 0)
    conn.commit()
    return written
```

`src/football_edge/live/__main__.py`:

<!-- plan: yeni src/football_edge/live/__main__.py -->
```python
"""`python -m football_edge.live {shadow,parity}` — canlı gölge tahmin ve eşitlik raporu (E3).

`shadow`: kararı verilmiş, başlamamış maçlar → `model_predictions` (yayın yok, kredi yok).
`parity`: sonrası dönemde hem defterde hem tabanda olan maçların yapısal alanları (lig, tarih,
adlar, sezon, başlama) birebir mi — fark varsa exit 15. Fiyat farkı rapordur, kapı değil.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType

from football_edge.backtest.__main__ import (
    CATALOG_PATH,
    EXIT_CONFIG_MISMATCH,
    EXIT_LOCK_VIOLATION,
    LOCK_PATH,
    kinds_of,
    rating_groups,
)
from football_edge.backtest.context import record_of
from football_edge.backtest.model_config import (
    MODEL_CONFIG_PATH,
    ModelConfigError,
    file_sha256,
    load_model_config,
)
from football_edge.backtest.records import MatchKey
from football_edge.backtest.walkforward import group_matches
from football_edge.collect import configure_logging
from football_edge.db import connect
from football_edge.history.catalog import Catalog, load_catalog
from football_edge.history.holdout import HOLDOUT_END
from football_edge.history.lock import LockViolation, load_lock
from football_edge.history.sync import load_matches
from football_edge.history.types import HistMatch
from football_edge.live.context import LiveMatch, build_batch, live_key, naming_from, season_of
from football_edge.live.shadow import shadow_rows, write_shadow
from football_edge.live.store import load_live_matches, load_quotes
from football_edge.market.bridge import load_aliases

LOGGER = logging.getLogger("football_edge.live")
ALIASES_PATH = Path("config/history_aliases.yaml")
HORIZON = timedelta(days=8)
LOOKBACK = timedelta(days=10)
EXIT_PARITY = 15
# Saat dilimi ya da yaz saati hatası ≥ 60 dk kaydırır; yayıncı kaynaklı küçük saat farkları değil.
KICKOFF_TOLERANCE = timedelta(minutes=30)


def head_sha() -> str:
    return subprocess.run(
        ("git", "rev-parse", "HEAD"), capture_output=True, text=True, check=True
    ).stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.live")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("shadow", "parity"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
        command.add_argument("--lock", type=Path, default=LOCK_PATH)
        command.add_argument("--catalog", type=Path, default=CATALOG_PATH)
        command.add_argument("--aliases", type=Path, default=ALIASES_PATH)
    commands.choices["parity"].add_argument(
        "--since",
        type=lambda text: datetime.fromisoformat(text).replace(tzinfo=UTC),
        default=datetime.combine(HOLDOUT_END, datetime.min.time(), tzinfo=UTC),
    )
    return parser


def _codes(catalog: Catalog) -> Mapping[str, str]:
    return MappingProxyType({league.league_id: league.code for league in catalog.leagues})


def _shadow(args: argparse.Namespace) -> int:
    try:
        config = load_model_config(args.config)
    except ModelConfigError as error:
        LOGGER.error("model yapılandırması: %s", error)
        return EXIT_CONFIG_MISMATCH
    if (file_sha256(args.catalog), file_sha256(args.lock)) != (
        config.catalog_sha256,
        config.lock_sha256,
    ):
        LOGGER.error("katalog ya da kilit model yapılandırmasındaki özetle uyuşmuyor")
        return EXIT_CONFIG_MISMATCH
    catalog = load_catalog(args.catalog)
    now = datetime.now(UTC)
    try:
        with connect() as conn:
            history = load_matches(conn, catalog, lock=load_lock(args.lock))
            live = load_live_matches(conn, since=now - LOOKBACK, until=now + HORIZON)
            quotes = load_quotes(
                conn, tuple(m.match_id for m in live if m.kickoff > now), until=now
            )
            groups = rating_groups(catalog)
            batch = build_batch(
                live,
                quotes,
                group_matches(history, groups),
                now=now,
                naming=naming_from(history, _codes(catalog), load_aliases(args.aliases)),
                kinds=kinds_of(catalog),
                rating_groups=groups,
            )
            rows = shadow_rows(
                batch,
                config=config,
                rating_groups=groups,
                config_sha256=file_sha256(args.config),
                git_sha=head_sha(),
            )
            written = write_shadow(conn, rows)
    except LockViolation as error:
        LOGGER.error("kilit ihlali — gölge tahmin koşulmadı: %s", "; ".join(error.differences))
        return EXIT_LOCK_VIOLATION
    LOGGER.info(
        "gölge: karar %d · yazılan satır %d · eşlenemeyen %d · bayat durum %d · fiyatsız %d",
        len(batch.decisions),
        written,
        len(batch.unmapped),
        len(batch.stale),
        len(batch.no_quote),
    )
    return 0


@dataclass(frozen=True)
class ParityReport:
    paired: int
    unmatched: int
    season_mismatch: int
    kickoff_mismatch: int


def parity(
    live: Sequence[LiveMatch],
    history: Mapping[str, Sequence[HistMatch]],
    *,
    codes: Mapping[str, str],
    aliases: Mapping[str, str],
    kinds: Mapping[str, str],
) -> ParityReport:
    """E3: defterdeki maç ↔ taban satırı yapısal alanları (fiyat hariç)."""
    naming = naming_from(history, codes, aliases)
    index: dict[MatchKey, HistMatch] = {
        record_of(match).key: match for matches in history.values() for match in matches
    }
    paired = unmatched = seasons = kickoffs = 0
    for match in live:
        key = live_key(match, naming)
        found = None if key is None else index.get(key)
        if key is None or found is None:
            unmatched += 1
            continue
        paired += 1
        league = [m for m in history.get(key.league, ()) if m is not found]
        if season_of(league, key.date, kinds.get(key.league, "")) not in (None, found.season):
            seasons += 1
        if found.kickoff is not None and abs(found.kickoff - match.kickoff) > KICKOFF_TOLERANCE:
            kickoffs += 1
    return ParityReport(paired, unmatched, seasons, kickoffs)


def _parity(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.catalog)
    try:
        with connect() as conn:
            history = load_matches(conn, catalog, lock=load_lock(args.lock))
            live = load_live_matches(conn, since=args.since, until=datetime.now(UTC))
    except LockViolation as error:
        LOGGER.error("kilit ihlali — eşitlik raporu koşulmadı: %s", "; ".join(error.differences))
        return EXIT_LOCK_VIOLATION
    report = parity(
        live,
        history,
        codes=_codes(catalog),
        aliases=load_aliases(args.aliases),
        kinds=kinds_of(catalog),
    )
    LOGGER.info(
        "eşitlik (E3): eşleşen %d · eşlenemeyen %d · sezon farkı %d · başlama farkı %d",
        report.paired,
        report.unmatched,
        report.season_mismatch,
        report.kickoff_mismatch,
    )
    if report.season_mismatch or report.kickoff_mismatch:
        LOGGER.error("yapısal alan farkı: canlı bağlam tarihsel bağlamla aynı değil")
        return EXIT_PARITY
    return 0


COMMANDS: Mapping[str, Callable[[argparse.Namespace], int]] = MappingProxyType(
    {"shadow": _shadow, "parity": _parity}
)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
```

`.github/workflows/shadow.yml`:

<!-- plan: yeni .github/workflows/shadow.yml -->
```yaml
name: shadow

on:
  # Tek tetik pg_cron (0011): salı ve cuma 12:35 UTC, karar anından (12:00 Londra) sonra. GitHub
  # `schedule`ı KASITLI olarak yok: seyrek ve gecikmeli koşar (0003).
  workflow_dispatch:

concurrency:
  # Kendi grubu: iki tur aynı maça aynı yapılandırmayla yazmaz (tekil kısıt yine de korur).
  group: shadow
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  shadow:
    runs-on: ubuntu-latest
    # Tabanı yükle (~10 sn, ~760 MB) + grup başına bir Elo ve bir Dixon-Coles durumu.
    timeout-minutes: 30
    permissions:
      contents: read
      issues: write
      actions: read
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - name: Secret taraması
        run: ./scripts/check_secrets.sh
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.11"
      - run: uv sync --frozen
      - name: Gölge tahmin
        # Faz 3 (R134): yayın yok, kredi yok. Exit 9 kilit ihlali, 11 model yapılandırması
        # katalog/kilitle uyuşmuyor. Veritabanı secret'ını yalnız bu adım alır.
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          set +e
          uv run python -m football_edge.live shadow
          code=$?
          set -e
          case "$code" in
            0) ;;
            9) echo "::error::live shadow: kilit ihlali (exit 9) — tahmin yazılmadı" ;;
            11) echo "::error::live shadow: model yapılandırması katalog/kilitle uyuşmuyor (exit 11)" ;;
            *) echo "::error::live shadow beklenmedik kodla düştü (exit $code)" ;;
          esac
          exit "$code"
      - name: Alarm aç
        if: ${{ failure() || cancelled() }}
        env:
          GITHUB_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: uv run python scripts/ops_alert.py fail --workflow shadow --run-url "$RUN_URL"
      - name: Alarm kapat
        if: success()
        continue-on-error: true
        env:
          GITHUB_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: uv run python scripts/ops_alert.py ok --workflow shadow --run-url "$RUN_URL"
```

`scripts/ops_alert.py` yaması:

<!-- plan: yama scripts/ops_alert.py -->
```diff
diff --git a/scripts/ops_alert.py b/scripts/ops_alert.py
index e3c7ef4..11baf52 100755
--- a/scripts/ops_alert.py
+++ b/scripts/ops_alert.py
@@ -102,6 +102,13 @@ TRIGGERS = (
         max_age=timedelta(days=8),
         hint="pg_cron history-dispatch durmuş olabilir — RUNBOOK §3.3",
     ),
+    # Gölge tahmin salı ve cuma (0011, 12:35): en uzun ara cuma → salı 4 gün; eşik 4 gün 12 sa.
+    Trigger(
+        workflow="shadow.yml",
+        event=None,
+        max_age=timedelta(days=4, hours=12),
+        hint="pg_cron shadow-dispatch durmuş olabilir — RUNBOOK §3.3",
+    ),
 )
 
 
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_shadow.py tests/test_shadow_workflow.py tests/test_ops_alert.py tests/test_history_dispatch.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — test_shadow 5 · test_shadow_workflow 8 · test_ops_alert 49 · test_history_dispatch 3 passed; `tests/test_workflows.py`nin alarm kuralları `shadow.yml`i izinli listeden kendiliğinden kapsar

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `shadow_rows`: piyasa `devig(pre, "multiplicative")` | `tests/test_shadow.py::test_the_market_row_is_the_devigged_pre_price` |
| 2 | bekçi: shadow eşiği `days=5` | `tests/test_ops_alert.py::test_a_stale_shadow_trigger_is_named_in_the_watchdog_alarm` |
| 3 | 0011: `'35 12 * * 2,5'` → `'35 12 * * 2'` | `tests/test_shadow_workflow.py` |
| 4 | `shadow.yml`: gölge adımına `ODDS_API_KEY` eklenir (inceleme m10) | `tests/test_shadow_workflow.py::test_the_credit_free_workflows_never_receive_the_odds_api_key` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add db/migrations/0009_model_predictions.sql \
  db/migrations/0011_shadow_dispatch.sql \
  src/football_edge/live/shadow.py \
  src/football_edge/live/__main__.py \
  .github/workflows/shadow.yml \
  scripts/ops_alert.py \
  tests/test_shadow.py \
  tests/test_shadow_workflow.py \
  tests/test_ops_alert.py \
  tests/test_history_dispatch.py
git commit -m "feat: Faz 3 — canlı gölge tahmin, E3 eşitlik raporu, 0009/0011 ve shadow.yml

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
**Dalga 4 sonu (controller, Task 10 ve 11 birleşince):**

- [ ] `feat/faz3-final-eval`, `feat/faz3-shadow` sırayla `--no-ff`, her birinden sonra kapı. `leakage` ölçülür
  (plan yazımında 333), `EXPECTED_MIN_LEAKAGE` güncellenir, commit `ci: Faz 3 dalga 4 — sızıntı alt sınırı`.
- [ ] **Migration'lar canlıya** (Supabase `apply_migration`, ad = dosya adı, içerik = dosyanın kendisi):
  `0009_model_predictions`, `0010_holdout_phase`, `0011_shadow_dispatch`. Doğrulama YALNIZ okuma sorgusuyla —
  append-only tablolara deneme satırı YAZILMAZ (DEFERRED §2.3):

```sql
select count(*) from holdout_access_log;                                   -- 0
select indexdef from pg_indexes where indexname = 'holdout_access_log_one_per_phase';
select tgname from pg_trigger where tgrelid = 'model_predictions'::regclass and not tgisinternal;
select relrowsecurity from pg_class where relname = 'model_predictions';  -- true
select jobname, schedule, command, active from cron.job
 where jobname in ('shadow-dispatch', 'history-dispatch-friday', 'history-dispatch');
```
  Expected: 0; indeks ifadesi `split_part(purpose, ':'::text, 1)`; iki tetikleyici (`…_append_only`,
  `…_no_truncate`); `true`; üç iş `active`.
- [ ] **0010'un reddettiğinin kanıtı (inceleme I6):** `0010`u uygulamadan ÖNCE
  `uv run --env-file .env pytest tests/test_holdout_phase_db.py -q` → **FAIL** ("ikinci faz99 açılışı kabul
  edildi"); `0010` uygulandıktan SONRA aynı komut → **1 passed**. Test tek işlemde çalışır ve geri alır; sonra
  `select count(*) from holdout_access_log` → 0 (satır kalmadı). `DATABASE_URL` bağlı tam kapı: 11/11.
- [ ] **İlk gölge turu (8 aktif lig):** `gh workflow run shadow.yml -R popiliadam/football-edge` → tur yeşil;
  logda `gölge: karar N · yazılan satır M · eşlenemeyen U · bayat durum B · fiyatsız Q`. Karar günü değilse
  N = 0 normaldir (yol yine uçtan uca koşar). `U > 0` ise o adlar `config/history_aliases.yaml`a İz A'nın 5.
  adımıyla (ad TAHMİN edilmez, canlı kapanıştan ölçülür) girer.
- [ ] **E3 eşitlik raporu:** `uv run --env-file .env python -m football_edge.live parity` → exit 0; eşleşen,
  eşlenemeyen, sezon ve başlama farkı sayıları ölçüm belgesine. Exit 15 ise canlı bağlam tarihsel bağlamla aynı
  değildir: Task 11'in sahibine bulgu (ned.1 ve bel.1'in `Date` eşleşmesi burada ilk kez ölçülür; AUT kapalı olduğu için §3/38 AUT için
  açık kalır).
- [ ] Taze klon kapısı, push. Dalga 5 (Task 12) bu commit'ten açılır.

---

### Task 12: Modelin bilinen sonuçları W1–W4 ve `history.yml` adımı (G4, R130)

**Kademe:** K1 · **Dalga:** 5 · **Worktree/dal:** `.worktrees/wt-model-selftest` · `feat/faz3-model-selftest`

Tasarım §9 G4. Kapı: W1 ortalama ΔLL(harman − piyasa) ≤ δ = 0.001 (P9) · W2 fit Elo iskeleden isabetli · W3 DC, S'nin sonuç oranlarından isabetli. Rapor: W4 harman kalibrasyonu. Ölçülemeyen denetim GEÇMEZ. `history.yml` `Bilinen sonuçlar`dan sonra, alarmdan önce `Model bilinen sonuçları` adımını koşar; iş zaman aşımı 120 dk (P17). **Başlamadan önce:** Task 9'un ölçtüğü walk-forward süresi 60 dk'yı aşıyorsa bu görev başlamaz, eskalasyon.

**Files:**
- Create: `src/football_edge/backtest/model_selftest.py`
- Create: `tests/test_model_selftest.py`
- Modify: `src/football_edge/backtest/__main__.py` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `.github/workflows/history.yml` (yama aşağıda, `git apply` ile uygulanır)
- Modify: `tests/test_history_workflow.py` (yama aşağıda, `git apply` ile uygulanır)

**Interfaces:**
- Consumes: Task 6, Task 7 (`model_strategies`, `development_groups`, `_checked_config`, `_locked_matches`), Task 10'un `__main__.py`si, Faz 2 `Check`, `EloPointInTime`.
- Produces: `model_rows`, `model_checks`, `W1_MARGIN`; CLI `model-selftest`; `history.yml` adımı.

Yamalar tabandaki (`main`, o dalganın başı) dosyaya karşı yazılmıştır: `git apply --check` önce, sonra
`git apply`. Yeni dosyalar bloktaki içerikle AYNEN yazılır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_model_selftest.py`:

<!-- plan: yeni tests/test_model_selftest.py -->
```python
"""Modelin bilinen sonuçları W1–W4 (Faz 3 tasarımı §9 G4): her kapı kırmızı verebiliyor."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from types import MappingProxyType

import numpy as np
import pytest

from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.model_selftest import model_checks, model_rows
from football_edge.backtest.records import MatchKey
from football_edge.backtest.walkforward import DC, ELO, ELO_SCAFFOLD, MARKET, Row
from football_edge.backtest.wf_run import development_groups
from football_edge.history.catalog import MAIN
from football_edge.market.devig import POWER
from football_edge.model.dixon_coles import DCConfig
from football_edge.model.elo_model import EloModelConfig
from tests.model_builders import main_history

GROUPS = MappingProxyType({"E0": "Ülke"})
KINDS = MappingProxyType({"E0": MAIN})
CONFIG = ModelConfig(
    "x", "c", "l", POWER, EloModelConfig(draw=0.28), DCConfig(min_matches=40), 7, 0.02, ()
)


@pytest.fixture(scope="module")
def rows() -> tuple[Row, ...]:
    groups = development_groups({"E0": main_history(2011, 2022)}, GROUPS)
    return model_rows(groups, KINDS, GROUPS, CONFIG)


def _checks(rows: tuple[Row, ...]) -> dict[str, object]:
    return {check.id: check for check in model_checks(rows, resamples=50)}


def test_honest_model_rows_pass_w2_and_w3_and_report_w4(rows: tuple[Row, ...]) -> None:
    checks = _checks(rows)

    assert [check.id for check in checks.values()] == ["W1", "W2", "W3", "W4"]  # type: ignore[attr-defined]
    assert checks["W2"].passed and checks["W3"].passed  # type: ignore[attr-defined]
    assert checks["W4"].gate is False  # type: ignore[attr-defined]


def _market_table(market_right: bool, count: int = 3000) -> tuple[Row, ...]:
    """İki sezon S + iki sezon E. Doğruysa piyasa gerçek dağılımı verir, modeller düz; değilse
    S'de modeller sonucu bilir, piyasa yanıltır — E'de piyasa bilir, modeller düz."""
    rng = np.random.default_rng(7)
    found: list[Row] = []
    for position, (season, zone) in enumerate(
        (("1718", "S"), ("1819", "S"), ("1920", "E"), ("2021", "E"))
    ):
        for index in range(count):
            outcome = int(rng.choice(3, p=(0.6, 0.25, 0.15)))
            knows = tuple(0.9 if i == outcome else 0.05 for i in range(3))
            misleads = tuple(0.05 if i == outcome else 0.475 for i in range(3))
            flat = (1 / 3, 1 / 3, 1 / 3)
            if market_right:
                market, model = (0.6, 0.25, 0.15), flat
            elif zone == "E":
                market, model = knows, flat
            else:
                market, model = misleads, knows
            found.append(
                Row(
                    key=MatchKey("E0", date(2020, 1, 1), f"Ev {position}-{index}", "Konuk"),
                    kind=MAIN,
                    zone=zone,
                    season=season,
                    outcome=outcome,
                    totals_outcome=0,
                    components=MappingProxyType({MARKET: market, ELO: model, DC: model}),
                    totals=MappingProxyType({}),
                    pre=None,
                    closing=None,
                    totals_pre=None,
                    totals_closing=None,
                )
            )
    return tuple(found)


def test_w1_passes_when_the_fitted_blend_keeps_the_market() -> None:
    assert _checks(_market_table(market_right=True))["W1"].passed is True  # type: ignore[attr-defined]


def test_w1_fails_when_weights_learnt_earlier_hurt_later() -> None:
    """İlk E katı S'den modellere ağırlık verdi; E'de modeller düz, piyasa doğru → harman
    piyasadan çok kötü (bozuk bir ağırlık fitinin ya da kayan bir hattın imzası)."""
    assert _checks(_market_table(market_right=False))["W1"].passed is False  # type: ignore[attr-defined]


def _swap(
    rows: tuple[Row, ...], name: str, probs: tuple[float, ...] | None = None
) -> tuple[Row, ...]:
    """E satırlarında bir bileşeni bozar: gerçek sonuca en düşük olasılığı verir."""

    def broken(row: Row) -> Row:
        wrong = tuple(0.05 if index == row.outcome else 0.475 for index in range(3))
        return replace(row, components=MappingProxyType({**row.components, name: probs or wrong}))

    return tuple(broken(row) if row.zone == "E" else row for row in rows)


@pytest.mark.parametrize(("name", "check"), [(ELO, "W2"), (DC, "W3")])
def test_a_broken_model_turns_its_gate_red(rows: tuple[Row, ...], name: str, check: str) -> None:
    assert _checks(_swap(rows, name))[check].passed is False  # type: ignore[attr-defined]


def test_without_rows_every_gate_is_unmeasured_and_red() -> None:
    checks = _checks(())

    assert all("ölçülemedi" in c.detail and not c.passed for c in checks.values())  # type: ignore[attr-defined]


def test_the_scaffold_elo_is_in_the_rows(rows: tuple[Row, ...]) -> None:
    assert any(ELO_SCAFFOLD in row.components for row in rows if row.zone == "E")
```

`tests/test_history_workflow.py` yaması:

<!-- plan: yama tests/test_history_workflow.py -->
```diff
diff --git a/tests/test_history_workflow.py b/tests/test_history_workflow.py
index e7cb3f3..b57ad4d 100644
--- a/tests/test_history_workflow.py
+++ b/tests/test_history_workflow.py
@@ -24,9 +24,9 @@ from tests.workflow_helpers import REPO, _index_of, _steps, _triggers
 
 HISTORY = REPO / ".github/workflows/history.yml"
 SYNC = "football_edge.history sync"
-# DATABASE_URL'i alan adımlar, adlarıyla: senkron ve bilinen sonuçlar. Başka hiçbir adım
-# (checkout, secret taraması, üçüncü taraf setup-uv, `uv sync`, alarm) secret görmez.
-DATABASE_STEPS: tuple[str, ...] = ("Senkron", "Bilinen sonuçlar")
+# DATABASE_URL'i alan adımlar, adlarıyla: senkron, bilinen sonuçlar ve modelinkiler. Başka hiçbir
+# adım (checkout, secret taraması, üçüncü taraf setup-uv, `uv sync`, alarm) secret görmez.
+DATABASE_STEPS: tuple[str, ...] = ("Senkron", "Bilinen sonuçlar", "Model bilinen sonuçları")
 
 
 def _document() -> dict[str, Any]:
@@ -91,8 +91,8 @@ def test_the_sync_step_takes_the_all_input_from_the_dispatch() -> None:
 
 
 def test_history_is_bounded_by_a_job_timeout() -> None:
-    """`--all` ≈ 25 dk; sınırsız bir tur takılırsa alarm hiç açılmaz (`cancelled()` dalı)."""
-    assert _document()["jobs"]["history"]["timeout-minutes"] == 60
+    """`--all` ≈ 25 dk + model denetimi (Faz 3); sınırsız bir tur takılırsa alarm hiç açılmaz."""
+    assert _document()["jobs"]["history"]["timeout-minutes"] == 120
 
 
 RULES: tuple[Callable[[Path], None], ...] = (
@@ -237,3 +237,63 @@ def test_selftest_names_every_exit_code_and_keeps_the_run_red(
         assert errors == []
     else:
         assert len(errors) == 1 and named in errors[0] and f"exit {code}" in errors[0], errors
+
+
+# ── Model bilinen sonuçları (Faz 3, G4) ──────────────────────────────────────────────────────
+
+MODEL_SELFTEST = "football_edge.backtest model-selftest"
+
+
+def _model_index() -> int:
+    index = _index_of(_steps(HISTORY), MODEL_SELFTEST)
+    assert index is not None, "history.yml modelin bilinen sonuçlarını hiç koşmuyor"
+    return index
+
+
+def test_the_model_checks_run_after_the_known_results_and_before_the_alarms() -> None:
+    steps = _steps(HISTORY)
+    opens = _index_of(steps, "scripts/ops_alert.py fail --workflow history ")
+
+    assert opens is not None
+    assert _selftest_index() < _model_index() < opens
+    step = steps[_model_index()]
+    assert step.get("env") == {"DATABASE_URL": "${{ secrets.DATABASE_URL }}"}
+    assert "if" not in step and not step.get("continue-on-error")
+
+
+@pytest.mark.parametrize(
+    ("code", "named"),
+    [
+        (0, ""),
+        (backtest_cli.EXIT_GATE_FAILED, "W kapısı"),
+        (backtest_cli.EXIT_LOCK_VIOLATION, "kilit"),
+        (backtest_cli.EXIT_CONFIG_MISMATCH, "yapılandırması"),
+        (3, "beklenmedik"),
+    ],
+    ids=["yesil", "kapi", "kilit", "yapilandirma", "beklenmedik"],
+)
+def test_the_model_step_names_every_exit_code_and_keeps_the_run_red(
+    tmp_path: Path, code: int, named: str
+) -> None:
+    fake = tmp_path / "uv"
+    fake.write_text(FAKE_UV, encoding="utf-8")
+    fake.chmod(0o755)
+    calls = tmp_path / "calls"
+    calls.touch()
+    env = {
+        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
+        "CALLS": str(calls),
+        "FAIL_CODE": str(code),
+    }
+    body = str(_steps(HISTORY)[_model_index()]["run"])
+    result = subprocess.run(
+        ["bash", "-e", "-c", body], env=env, capture_output=True, text=True, timeout=30, check=False
+    )
+
+    errors = [line for line in result.stdout.splitlines() if line.startswith("::error::")]
+    assert calls.read_text(encoding="utf-8").splitlines() == [f"run python -m {MODEL_SELFTEST}"]
+    assert result.returncode == code
+    if code == 0:
+        assert errors == []
+    else:
+        assert len(errors) == 1 and named in errors[0] and f"exit {code}" in errors[0], errors
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_model_selftest.py tests/test_history_workflow.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.backtest.model_selftest'`; `history.yml` model adımı yok

- [ ] **Step 3: Uygulamayı yaz**

`src/football_edge/backtest/model_selftest.py`:

<!-- plan: yeni src/football_edge/backtest/model_selftest.py -->
```python
"""Modelin bilinen sonuçları (Faz 3 tasarımı §9 G4; R130): E bölgesinde, haftalık.

Kapı: W1 harman piyasadan `W1_MARGIN`dan fazla KÖTÜ değil (ortalama ΔLL ≤ δ) — `w = (1, 0, 0)`
havuzun içinde olduğu için doğru bir fit örneklem içinde buna kesin uyar; örneklem dışında yalnız
ağırlık tahmin gürültüsü kadar (~ bileşen sayısı / 2n) sapar. Kırmızıysa fit ya da hat bozuktur ·
W2 fit Elo iskele Elo'dan isabetli (ortalama ΔLL < 0) · W3 Dixon-Coles S'nin sonuç oranlarından
isabetli.
Rapor: W4 harmanın kalibrasyonu. Ölçülemeyen denetim GEÇMEZ ("ölçülemedi" yazar).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from football_edge.backtest.harness import Strategy
from football_edge.backtest.model_config import ModelConfig
from football_edge.backtest.selftest import Check
from football_edge.backtest.strategies import EloPointInTime
from football_edge.backtest.walkforward import (
    DC,
    ELO,
    ELO_SCAFFOLD,
    EVALUATION,
    MARKET,
    SELECTION,
    Row,
    group_rows,
)
from football_edge.backtest.wf_eval import blended, complete, fold_weights
from football_edge.backtest.wf_run import model_strategies
from football_edge.history.catalog import MAIN
from football_edge.history.types import HistMatch
from football_edge.market.metrics import Interval, bootstrap_mean, calibration, per_match_log_loss

_LOG_FLOOR = 1e-15
# ~5 bin maçlık bir katta üç ağırlığın örneklem dışı gürültüsü ~3e-4; δ bunun üç katı.
W1_MARGIN = 0.001


def model_rows(
    groups: Mapping[str, Sequence[HistMatch]],
    kinds: Mapping[str, str],
    rating_groups: Mapping[str, str],
    config: ModelConfig,
) -> tuple[Row, ...]:
    def strategies(matches: Sequence[HistMatch]) -> Mapping[str, Strategy]:
        return {
            **model_strategies(matches, kinds, rating_groups, config),
            ELO_SCAFFOLD: EloPointInTime(groups=rating_groups),
        }

    return tuple(
        row
        for matches in groups.values()
        for row in group_rows(matches, kinds, strategies(matches), method=config.method)
    )


def _text(interval: Interval) -> str:
    return f"{interval.estimate:.5f} [%95 {interval.low:.5f}, {interval.high:.5f}]"


def _gap(
    first: Sequence[Sequence[float]],
    second: Sequence[Sequence[float]],
    outcomes: Sequence[int],
    resamples: int,
) -> Interval:
    a = per_match_log_loss(first, outcomes)
    b = per_match_log_loss(second, outcomes)
    return bootstrap_mean([x - y for x, y in zip(a, b, strict=True)], resamples=resamples)


def _unmeasured(check_id: str, gate: bool) -> Check:
    return Check(check_id, gate, False, f"{check_id} ölçülemedi: E bölgesinde uygun satır yok")


def _w1(rows: Sequence[Row], resamples: int) -> tuple[Check, Check]:
    weights, _ = fold_weights(rows)
    main = [row for row in rows if row.zone == EVALUATION and row.kind == MAIN]
    pairs = blended(main, weights)
    if not pairs:
        return _unmeasured("W1", True), _unmeasured("W4", False)
    outcomes = [row.outcome for row, _ in pairs]
    probs = [p for _, p in pairs]
    gap = _gap(probs, [row.components[MARKET] for row, _ in pairs], outcomes, resamples)
    try:
        fitted = calibration(probs, outcomes)
        w4 = Check(
            "W4", False, True, f"harman kalibrasyonu b={fitted.slope:.3f} ECE={fitted.ece:.4f}"
        )
    except ValueError as error:
        w4 = Check("W4", False, False, f"W4 ölçülemedi: {error}")
    return (
        Check(
            "W1",
            True,
            gap.estimate <= W1_MARGIN,
            f"ΔLL harman − piyasa {_text(gap)} ≤ {W1_MARGIN} n={len(pairs)}",
        ),
        w4,
    )


def _w2(rows: Sequence[Row], resamples: int) -> Check:
    usable = [
        row
        for row in rows
        if row.zone == EVALUATION and row.kind == MAIN and complete(row, (ELO, ELO_SCAFFOLD))
    ]
    if not usable:
        return _unmeasured("W2", True)
    gap = _gap(
        [row.components[ELO] for row in usable],
        [row.components[ELO_SCAFFOLD] for row in usable],
        [row.outcome for row in usable],
        resamples,
    )
    return Check(
        "W2", True, gap.estimate < 0.0, f"ΔLL fit Elo − iskele {_text(gap)} n={len(usable)}"
    )


def _w3(rows: Sequence[Row]) -> Check:
    base_rows = [row for row in rows if row.zone == SELECTION and row.kind == MAIN]
    usable = [
        row for row in rows if row.zone == EVALUATION and row.kind == MAIN and DC in row.components
    ]
    if not base_rows or not usable:
        return _unmeasured("W3", True)
    counts = [sum(1 for row in base_rows if row.outcome == index) for index in range(3)]
    base = [count / len(base_rows) for count in counts]
    dc = math.fsum(-math.log(max(row.components[DC][row.outcome], _LOG_FLOOR)) for row in usable)
    rate = math.fsum(-math.log(max(base[row.outcome], _LOG_FLOOR)) for row in usable)
    dc, rate = dc / len(usable), rate / len(usable)
    return Check(
        "W3", True, dc < rate, f"LL Dixon-Coles {dc:.5f} < S oranları {rate:.5f} n={len(usable)}"
    )


def model_checks(rows: Sequence[Row], *, resamples: int) -> tuple[Check, ...]:
    w1, w4 = _w1(rows, resamples)
    return (w1, _w2(rows, resamples), _w3(rows), w4)
```

`src/football_edge/backtest/__main__.py` yaması:

<!-- plan: yama src/football_edge/backtest/__main__.py -->
```diff
--- a/src/football_edge/backtest/__main__.py
+++ b/src/football_edge/backtest/__main__.py
@@ -34,6 +34,7 @@
     file_sha256,
     load_model_config,
 )
+from football_edge.backtest.model_selftest import model_checks, model_rows
 from football_edge.backtest.preregistration import (
     PREREGISTRATION_PATH,
     PreflightError,
@@ -101,6 +102,11 @@
     walk.add_argument("--out", type=Path, required=True)
     walk.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
     walk.add_argument("--gap", action="store_true", help="R128 boşluk cezası (iki ek koşu)")
+    model = commands.add_parser("model-selftest", help="modelin bilinen sonuçları W1–W4")
+    model.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
+    model.add_argument("--lock", type=Path, default=LOCK_PATH)
+    model.add_argument("--catalog", type=Path, default=CATALOG_PATH)
+    model.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
     final = commands.add_parser("final-eval", help="Faz 3'ün tek, kayıtlı holdout açılışı")
     final.add_argument("--prereg", type=Path, default=PREREGISTRATION_PATH)
     final.add_argument("--config", type=Path, default=MODEL_CONFIG_PATH)
@@ -248,6 +254,27 @@
         encoding="utf-8",
     )
     LOGGER.info("walk-forward raporu yazıldı: %s (E satırı %d)", args.out, summary.rows)
+    return 0
+
+
+def _model_selftest(args: argparse.Namespace) -> int:
+    config = _checked_config(args)
+    if config is None:
+        return EXIT_CONFIG_MISMATCH
+    loaded = _locked_matches(args.catalog, args.lock)
+    if loaded is None:
+        return EXIT_LOCK_VIOLATION
+    catalog, matches = loaded
+    groups = rating_groups(catalog)
+    rows = model_rows(development_groups(matches, groups), kinds_of(catalog), groups, config)
+    checks = model_checks(rows, resamples=args.resamples)
+    for check in checks:
+        _log(check)
+    failed = [check.id for check in checks if check.gate and not check.passed]
+    if failed:
+        LOGGER.error("kırmızı model denetimi: %s", ", ".join(failed))
+        return EXIT_GATE_FAILED
+    LOGGER.info("model bilinen sonuçları: kapı denetimlerinin hepsi geçti")
     return 0
 
 
@@ -312,6 +339,7 @@
         "selftest": _selftest,
         "select": _select,
         "walkforward": _walkforward,
+        "model-selftest": _model_selftest,
         "final-eval": _final_eval,
     }
 )
```

`.github/workflows/history.yml` yaması:

<!-- plan: yama .github/workflows/history.yml -->
```diff
diff --git a/.github/workflows/history.yml b/.github/workflows/history.yml
index fff5eb1..334b4c2 100644
--- a/.github/workflows/history.yml
+++ b/.github/workflows/history.yml
@@ -26,8 +26,9 @@ jobs:
   # bu yüzden ikinci bir job değil, `Senkron` ile alarm adımları arasında bir ADIMDIR.
   history:
     runs-on: ubuntu-latest
-    # `--all`: 500 dosya × 3 sn nezaket aralığı ≈ 25 dk + indirme; haftalık tur ~40 dosya.
-    timeout-minutes: 60
+    # `--all`: 500 dosya × 3 sn nezaket aralığı ≈ 25 dk + indirme; haftalık tur ~40 dosya. Faz 3
+    # model denetimi (W1–W4) E bölgesini yeniden oynatır — süresi Task 9'da ölçüldü.
+    timeout-minutes: 120
     permissions:
       # Job düzeyi üst düzeyi TAMAMEN ezer: checkout için `contents: read` burada da yazılı.
       contents: read
@@ -48,7 +49,8 @@ jobs:
           python-version: "3.11"
       - run: uv sync --frozen
       - name: Senkron
-        # Veritabanı secret'ını yalnız veritabanını kullanan adımlar alır (bu ve selftest) — liste
+        # Veritabanı secret'ını yalnız veritabanını kullanan adımlar alır (bu, selftest ve model
+        # denetimi) — liste
         # tests/test_history_workflow.py::DATABASE_STEPS. Girdi `env` ile gelir, betiğe `${{ }}`
         # ile gömülmez.
         env:
@@ -86,6 +88,24 @@ jobs:
             *) echo "::error::selftest beklenmedik kodla düştü (exit $code)" ;;
           esac
           exit "$code"
+      - name: Model bilinen sonuçları
+        # Faz 3 (G4, R136): W1–W3 kapı, W4 rapor. Örtük `success()`: kırmızı senkron ya da selftest
+        # sonrası koşmaz. Exit 11: `config/model_faz3.yaml` katalog/kilitle uyuşmuyor.
+        env:
+          DATABASE_URL: ${{ secrets.DATABASE_URL }}
+        run: |
+          set +e
+          uv run python -m football_edge.backtest model-selftest
+          code=$?
+          set -e
+          case "$code" in
+            0) ;;
+            1) echo "::error::model-selftest: W kapısı kırmızı ya da beklenmedik arıza (exit 1) — hangi W olduğu yukarıdaki satırlarda" ;;
+            9) echo "::error::model-selftest: kilit ihlali (exit 9) — W1–W4 koşulmadı" ;;
+            11) echo "::error::model-selftest: model yapılandırması katalog/kilitle uyuşmuyor (exit 11)" ;;
+            *) echo "::error::model-selftest beklenmedik kodla düştü (exit $code)" ;;
+          esac
+          exit "$code"
       - name: Alarm aç
         # Önceki HERHANGİ bir adım kırmızıysa `ops-alert` issue'su açılır; açıksa yalnız gövdesi
         # güncellenir. `cancelled()`: zaman aşımı turu iptal eder ve `failure()` yanlış döner.
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_model_selftest.py tests/test_history_workflow.py -q && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src scripts`
Expected: PASS — test_model_selftest 7 · test_history_workflow 26 passed

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır; plan yazımında
hepsi KIRMIZI görüldü)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | W1: `gap.estimate <= W1_MARGIN` → `>=` | `tests/test_model_selftest.py` |

- [ ] **Step 6: Commit ve kapı**

```bash
git add src/football_edge/backtest/model_selftest.py \
  src/football_edge/backtest/__main__.py \
  .github/workflows/history.yml \
  tests/test_model_selftest.py \
  tests/test_history_workflow.py
git commit -m "feat: Faz 3 G4 — modelin bilinen sonuçları W1–W4 ve history.yml adımı

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
TMPDIR=$(mktemp -d) ./verify.sh > /tmp/verify-$$.log 2>&1; echo exit=$?; grep -E '^(PASS|FAIL|SKIP)|KAPI' /tmp/verify-$$.log
```
Expected: `KAPI YEŞİL` — 10 PASS + `SKIP: zincir (DATABASE_URL yok)` adıyla. Sonra inceleme döngüsü
(kabuklu `general-purpose`, K1'de `fable`), düzeltme, controller mutasyon kanıtı, `--no-ff` birleştirme.

---
### Task 13: Ön kayıt, prova, kırmızı takım, TEK holdout açılışı, Faz 3 HANDOFF (controller)

**Kademe:** — (controller; kırmızı takım fable) · **Dalga:** 6 · **Önkoşul:** Task 0–12 `complete`, açık
Critical/Important yok, Task 12 `history.yml`in model adımıyla bir haftalık tur YEŞİL (`gh run list -w
history.yml`).

Bu görevin 8. adımı geri alınamaz: holdout'un Faz 3 açılışı. Önceki her adım onu tek seferde doğru yapmak için.

- [ ] **Step 1: Dalga 5'i birleştir** — `feat/faz3-model-selftest` `--no-ff`, kapı; `leakage` yeniden ölçülür
  (333 beklenir); push; `gh workflow run history.yml` → `Model bilinen sonuçları` adımı yeşil (W1–W3 GEÇTİ,
  W4 raporlandı), süre ölçüm belgesine.

- [ ] **Step 2: Ön kayıt** — `config/faz3_preregistration.yaml` (alanlar `load_preregistration`in istediği
  tam küme):

```bash
cat > config/faz3_preregistration.yaml <<EOF
# Faz 3 holdout ön kaydı (tasarım §8.1; R130, R135, R139). Açılıştan ÖNCE commit'lenir; değişirse
# final-eval açmaz. Karşılaştırmalar: C1 harman–piyasa ΔLL · C2 DC, fit Elo, iskele Elo · C3 harman
# bahis CLV + Placebo · C4 harman kalibrasyonu · C5 Ü/A 2.5 · C6 sonrası dönemi, tam durum.
phase: faz3
model_config_sha256: $(shasum -a 256 config/model_faz3.yaml | cut -d' ' -f1)
lock_sha256: $(shasum -a 256 config/history_lock.yaml | cut -d' ' -f1)
catalog_sha256: $(shasum -a 256 config/history_leagues.yaml | cut -d' ' -f1)
comparisons: [C1, C2, C3, C4, C5, C6]
tau: 0.02
sensitivity: [0.0, 0.05]
resamples: 2000
EOF
git add config/faz3_preregistration.yaml
git commit -m "docs: Faz 3 holdout ön kaydı — karşılaştırmalar, eşik ve özetler açılıştan önce

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Kapı; push. **Bu commit'ten sonra `config/model_faz3.yaml`, kilit, katalog ve ön kayıt DEĞİŞMEZ** (değişirse
`final-eval` exit 12 verir — doğru davranış).

- [ ] **Step 3: Prova** (R135, P22) — aynı makinede, aynı kaynakla, AÇILIŞSIZ:

Run: `/usr/bin/time -l uv run --env-file .env python -m football_edge.backtest final-eval --rehearse --out docs/reports/<tarih>-faz3-prova.md; echo exit=$?`
Expected: exit 0; `holdout AÇILMADI` logu; rapor C1–C4'ü sahte holdout (2024/25) için taşır, C6 boş; süre ve tepe
RSS ölçüm belgesine. `select count(*) from holdout_access_log` → hâlâ 0. Prova kırmızıysa açılış yapılmaz;
bulgu sahibine.

- [ ] **Step 4: Kırmızı takım** (tasarım §11: açılıştan ÖNCE; fable, kabuklu `general-purpose`, rapor son mesajda)
  — brief: tasarım §5, §7, §8, §9 ve bu planın Global Constraints'i; modüller `model/*`, `backtest/{context,
  records,harness,walkforward,wf_eval,wf_run,selection,model_config,preregistration,final_eval,model_selftest}.py`,
  `live/*`. Görev: "bu fazda ileriye bakma ve holdout sızıntısı bul". Bakılacaklar: hiperparametrenin E'den ya
  da holdout'tan seçime sızması (seçim yalnız S mi — `_selection_rows`); ağırlık katlarının sınırı (`_training`);
  `frozen_weights`in holdout satırı görmemesi; DC memo'sunun (grup, gün) anahtarı ve `fit`in `day < at`
  süzgeci; canlı kurucunun karar sonrası snapshot'ı ya da gerçek varış anını kullanması; bayat durum
  korumasının kaçırdığı durumlar; ön kaydın açılıştan sonra değiştirilebilirliği; `final_eval`in anahtarı
  kaçırabileceği yollar (AST kuralının sınırları, 12h/14h); `0010` indeksinin atlatılması; Placebo tohumu.
  Ajan her şüpheyi ÇALIŞTIRARAK sınar (izole `git archive` kopyası, `PYTHONDONTWRITEBYTECODE=1`); holdout'u
  AÇMAZ (`open_holdout` çağrısı yasak — kopyada da). Critical/Important bulgular normal düzeltme döngüsüne; kapanmadan
  Step 7'ye geçilmez. Rapor `docs/reports/<tarih>-faz3-sizinti-denetimi.md`.

- [ ] **Step 5: Açılış öncesi eserleri commit'le, sonra temiz ağaç ve sayım** (inceleme I5 — `preflight` kirli
ağaçta açmaz; eserler açılıştan ÖNCE commit'lenmelidir):

```bash
git add docs/reports/<tarih>-faz3-prova.md docs/reports/<tarih>-faz3-sizinti-denetimi.md \
  docs/superpowers/specs/2026-09-23-faz3-olcumler.md
git commit -m "docs: Faz 3 prova raporu, kırmızı takım denetimi ve ölçümler — açılıştan önce

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main               # kapı + CI yeşil olduktan sonra
git status --porcelain            # boş olmalı
git log -1 --format=%H             # açılışın SHA'sı: ölçüm belgesine
```
```sql
select count(*) from holdout_access_log;   -- 0
```

- [ ] **Step 6: Çöküş planı yazılı** — açılış sonrası exit 14 ya da süreç çökmesi: rapor dosyası YOKSA ve
  `git log -1` aynıysa TEK yeniden koşu `--rerun-reason "<neden>"` ile (R135); kod değiştiyse yeniden koşu YOK,
  holdout Faz 3 için harcanmış sayılır ve HANDOFF adıyla yazar. Açılış öncesi ölçüm belgesine eklenecek her şey
  Step 5'te commit'lendi; açılış SONRASI ölçümler Step 9'da ayrı commit'e girer (ağaç açılışa kadar temiz).

- [ ] **Step 7: Kullanıcı durağı (P14)** — kullanıcıya: ön kayıt dosyası, prova raporunun özeti, kırmızı takımın
  sonucu, açılışın geri alınamazlığı. Açılış YALNIZ açık "evet"le.

- [ ] **Step 8: TEK açılış**

Run: `uv run --env-file .env python -m football_edge.backtest final-eval --out docs/reports/<tarih>-faz3-holdout.md > /tmp/final.log 2>&1; echo exit=$?`
Expected: exit 0; logda `holdout raporu yazıldı: … (amaç faz3:<ön kayıt sha256>)`. Çıkış kodu tablosu (inceleme I4):

| exit | anlamı | ne yapılır |
|---|---|---|
| 0 | açıldı, rapor yazıldı | Step 9 |
| 12 | ön denetim (kirli ağaç, ön kayıt/özet uyuşmazlığı, kilit ihlali, yinelenen maç) — AÇILMADI | logu oku, düzelt (ön kayıt değişirse Step 2'den), Step 5'ten |
| 13 | Faz 3 açılışı zaten var ya da 0010 INSERT'i reddetti — AÇILMADI | açılış kaydını oku; yeniden koşu kuralı mı? |
| 14 | açıldı, değerlendirme ya da rapor yazımı düştü (rapor yok) | Step 6 |
| 1, 137 ya da başka | süreç dışı ölüm (OOM 137, sinyal) ya da yakalanmamış arıza — DURUM BİLİNMİYOR | önce aşağıdaki sorgu: satır varsa "açıldı" (Step 6), yoksa "açılmadı" |

```sql
select id, opened_at, recorded_at, git_sha, purpose from holdout_access_log order by id;   -- tam 1 satır
```

- [ ] **Step 9: Holdout raporunu oku ve commit'le** — yalnız toplu sayı (Task 9'un takım adı kontrolü bu dosyada
  da). R130: kenar şartı yoktur; sayılar kaydedilir, yorum HANDOFF'ta. Boşluk cezası (R128): Task 9 raporunun
  DEV simülasyonu ve C6'nın tam durum sayısı yan yana; canlı ayağı (C6 − gölge) P25 ile ertelendi.

```bash
git add docs/reports/<tarih>-faz3-holdout.md docs/superpowers/specs/2026-09-23-faz3-olcumler.md
git commit -m "docs: Faz 3 holdout raporu — tek kayıtlı açılış

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 10: Faz 3 HANDOFF** — `docs/phases/03-baz-model/HANDOFF.md`: ne bitti; kapı ne ölçtü (adım adım, log
  dosyasından; `SKIP` adıyla); **kapının ölçmedikleri** (aşağıdaki liste + yürütmenin eklediği); verilen kararlar
  (R128–R139, P1–P25, R141, defterin `Ruling:` satırları); inceleme m4 notu: `report_exists` denetimi farklı bir
  `--out` ile atlanabilir — aynı SHA + temiz ağaç aynı kodu, yapılandırmayı ve ön kaydı garanti ettiği için
  zararsız, 0010 yeniden koşuyu yine bire sınırlar; **holdout açılış sayısı** (`holdout_access_log`tan; 1 ya da
  yeniden koşuyla 2, adıyla); ertelenenler (`docs/DEFERRED.md` yeni bölüm — gölge CLV raporu P25 dahil); Faz 4 ön koşulları (dil kalibrasyonu,
  Jev istemcisi; gölge sicilin büyüklüğü; R128: holdout Faz 5 açılışından sonra durum verisi olur). `docs/HANDOFF.md`
  §0 güncellenir. Taze klon kapısı, push, CI yeşil.

---

## Faz 3 kapısının ÖLÇMEYECEKLERİ — Task 13'ün başlangıç listesi

Tasarım §12'nin on üç maddesi aynen geçerlidir. Plan yazılırken eklenenler:

14. **Bağlam `Avg` 1X2 dışındaki kapanış öncesi fiyatı taşımaz** (P1): Ü/A ve tek kitap fiyatları bağlamdan
    düştü; bir strateji onları isteyemez. Ü/A'nın piyasa bileşeni walk-forward satırında maçtan okunur (tarihte);
    canlıda Ü/A yok.
15. **Placebo'nun K4 sayısı değişti** (P4): Faz 2 raporundaki −0.0713 artık yeniden üretilmez.
16. **Seçim yerel optimumdur** (P10): tek tur koordinat inişi, sabit ızgaralar; ızgara ucunda duran bir değer
    bulgu olarak yazılır ama genişletilmez.
17. **W1'in δ'sı (0.001) keyfîdir** (P9); P8'in 1.000 eşiği sentetik ölçümden türetildi, gerçek veride ölçülmedi.
18. **Dixon-Coles görülmemiş takımı tahmin etmez**: o maçlar ortak kümeden düşer (sayılır); E sayıları terfi eden
    takımların ilk maçlarını içermez.
19. **Gölge harmanı, bahsi ve CLV'si bu fazda hesaplanmaz** (P19, P25): tablo bileşenleri ve karar anı fiyatını
    tutar; rapor Faz 4'ün ilk görevi. R128'nin canlı ayağı o rapora kadar ölçülmez.
20. **Kitap kümesi farkı** (The Odds API ortalaması ↔ football-data `Avg`) E3'te ölçülmez; yalnız yapısal alanlar.
21. **30 dk'nın altındaki başlama kaymaları görünmez** (P12).
22. **Cross-platform kayan nokta** (macOS yerel ↔ Linux runner): tahmin özeti 1e-9'a yuvarlanır; iki platform
    arasındaki fark ölçülmedi (belirlenimcilik testi aynı platformda).
23. **Açılış öncesi kilit ikinci kez yüklenir** (P13): iki yükleme arasında önbellek değişirse ikinci doğrulama
    açılıştan SONRA kırmızı verir (exit 14) — haftalık senkron salı/cuma 09:50 UTC; açılış bu saatlerden uzakta yapılır.
24. **R141 bayat koruması sezgiseldir**: defterde fikstürü olmayan grup liglerinde (E1–E3 …) olağan aralık
    içinde kalan tek maçlık bir gecikme görünmez; o zaman canlı `observe` akışı tarihsel akıştan ayrışabilir.
25. **(inceleme m2, ERTELENDİ)** Ek liglerde `season_of` tabandaki son maçın sezonunu alır: takvim yılı dönümünde
    (ocak maçı, football-data yeni dosyayı yayımlamadan) önceki sezonu verir ve E3 sezon farkı raporlar. AUT
    kapalıyken (bugün) etkisiz; bir ek lig açılırsa önce bu düzeltilir.
26. **(inceleme m3, ERTELENDİ)** Anahtar akışı AST kuralı yalnız `final_eval.py`yi ve düz `x = open_holdout(...)`
    atamasını görür; walrus, `AnnAssign` ve demet hedefleri görünmez — 12h/§12.12'nin "kazara girişi durdurur"
    varsayımı.
27. **(inceleme m5, ERTELENDİ)** Prova gerçek veride C6'yı (sonrası) boş bırakır (anahtarsız sonrası dönemi prova
    bölgelemesinde yok); C6 yolu yalnız sentetik testte (`report.post.main`) koşar.

## Self-review — plan tasarıma karşı (yazıldığı gün)

- **Kapsam:** tasarım §3 bileşenleri → Task 1–12 dosyaları (tablo) · §4 grup başına oynatma → Task 6
  (`group_matches`), P24 · §5.1 bölgeler → Task 6 · §5.2/A → Task 6 (`fold_weights`) + Task 7 (`select`) · §5.3
  → Task 6/7 (rapor, belirlenimcilik) · §5.4/H1 → Global Constraints (anahtarsız DEV + POST), Task 7
  `gap_penalty` (DEV simülasyonu), Task 10 C6, Task 11 (gölge boşluklu); canlı ayağı P25 ile ertelendi · §6.1 → Task 2 (P11 farkı) · §6.2 → Task 1, 6 · §6.3 → Task 3, 6 · §6.4 → Task 6 `bet_clv` ·
  §6.5 → Task 6 `_extra_scores`, P7 · §6.6 → Task 6 Ü/A · §7.1 → Task 4 · §7.2–7.3 → Task 8 · §7.4 E1–E2 → Task 8,
  E3 → Task 11 · §7.5 → Task 4 · §8.1 → Task 10 + Task 13 Step 2 · §8.2 → Task 10 (AST, 14j) · §8.3 → Task 10
  (0010, yeniden koşu) + Task 13 Step 3/6 · §9 G1 → Task 5/9/13 sabitleri · G2 → Task 6 · G3 → Task 6 · G4 →
  Task 12 · G5 → Task 10 · G6 → Task 10 · G7 → Task 6 · G8 → Task 0 · §10 → Task 11 (tablo, iş, E3); haftalık
  gölge CLV raporu → ERTELENDİ (P25) · §11 → dalgalar · §12 →
  yukarıdaki liste · §13 riskleri → Task 5 ölçümü (R2), R3 P21/§22, R6 Task 13 Step 6 · §14 → R128–R139.
- **Yer tutucu taraması:** "TBD/TODO/benzer şekilde/uygun hata" yok. `<tarih>`, `<Task 5 kararı>` ve ölçülen
  `leakage` sayıları çalışma zamanı değerleridir (aşağıda tanımlı).
- **Tip tutarlılığı:** planın bütün kod blokları bu metinden bir ağaca kuruldu; her dalga sonunda ve paralel
  görevler tek başına `mypy --strict` + `ruff` + `pytest` yeşil. İsim sözleşmesi (yukarıdaki blok) kodla
  karşılaştırıldı.
- **Kodun kendisi:** planın METNİNDEN (`<!-- plan: yeni|yama … -->` işaretli bloklar, sırayla) `a398c31`'e (İz A birleşmiş) kurulan
  ağaç, kodun yazıldığı ağaçla bayt bayt aynı (`uv.lock` dahil, `uv lock` ile üretilince); tam `verify.sh` 10 PASS
  + `SKIP: zincir`; 1.757 passed / 3 skipped (üçüncü SKIP `test_holdout_phase_db`: `DATABASE_URL yok`); `leakage` 333. Her dalga sonunda ve paralel görev tek başına tam `verify.sh`
  koşuldu (hepsi 10 PASS + `zincir` SKIP). Dalga sonu test sayıları: 1.553 · 1.600 · 1.635 · 1.670 · 1.744 ·
  1.757; paralel görevler tek başına: T1 1.568 · T2 1.571 · T3 1.563 · T4 1.557 · T7 1.652 · T8 1.653 ·
  T10 1.725 · T11 1.689. Görev tablolarındaki 45 mutasyonun (plan incelemesinin sağ kalan üç mutantı — I2, I3,
  m1 — dahil) her biri uygulandı, KIRMIZI görüldü,
  geri alındı.
- **Bilinen boşluk:** hiçbir sayı gerçek veride ölçülmedi (bağlantı yok); Task 0/5/9'un ölçümleri kararları
  (P18 kadansı, P17 süresi) belirler ve kural önceden yazılıdır.

## Yürütme

- **Yöntem:** `superpowers:subagent-driven-development`, bu projenin kurallarıyla: görev başına taze implementer
  (izole worktree, dal adı görev başlığındaki), controller'ın ürettiği inceleme paketiyle bağımsız inceleme
  (kabuklu `general-purpose`; K1'de model `fable`), düzeltme turu, kapsamlı yeniden inceleme, controller mutasyon
  kanıtı (`git archive` kopyası, `PYTHONDONTWRITEBYTECODE=1`), her commit'ten sonra `verify.sh`'ın tamamı, `main`e
  `--no-ff`, taze klon kapısı, push (önce `git fetch` + `git merge --no-ff origin/main`; rebase/force YOK).
- **Dalgalar:** 0 → 1 (Task 1–4 paralel) → 5 → 2 (Task 6) → 3 (Task 7, 8 paralel) → 9 → 4 (Task 10, 11
  paralel) → 5 (Task 12) → 6 (Task 13). Aynı anda en çok 4 implementer. Her dalgadan önce tek-yazar taraması
  defterde yeniden yapılır.
- **Her dispatch'e:** "HİÇBİR ŞEY SİLME" (kendi scratch'i dahil); paralel ajanlara scratchpad'de AYRI alt dizin;
  rapor son mesajda (bazı implementer'lar dosya yazamıyor, controller kaydeder); holdout'u AÇMA.
- **Model:** varsayılan opus; K1 incelemeleri, Task 13'ün kırmızı takımı ve bütün-dal incelemesi fable; haiku hiçbir yerde.
- **Defter:** `.superpowers/sdd/2026-09-23-faz3-model-walkforward/progress.md` (gitignored); Ruling numaraları R141'den (R140 controller'ın, R122–R127 İz A'nın).
- **Çalışma zamanı değerleri:** `<tarih>` komutun koşulduğu gün (`YYYY-MM-DD`); `<Task 5 kararı>` Task 5 Step 3'ün
  kuralının çıktısı (1 ya da 7); `leakage` alt sınırları ölçülerek yazılır (plan yazımında 269 · 282 · 286 · 333).
- **Onay kapıları:** (1) bu plan kullanıcı onayından önce uygulanmaz (İz A'nın birleşmesi koşulu `a398c31` ile sağlandı); (2) Task 13
  Step 7 (holdout açılışı) ayrıca kullanıcı "evet"i ister; (3) kredi harcayan hiçbir adım yoktur — K6'nın ek
  snapshot'ı bu planın dışındadır ve ayrı onay ister.
