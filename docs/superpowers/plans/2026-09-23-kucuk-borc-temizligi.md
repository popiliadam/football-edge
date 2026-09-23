# Küçük Borç Temizliği (DEFERRED 16j, 17i, 16k-c, 17m) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faz 3 ve Faz 4 Plan 1'den ertelenen kod tekrarlarını tek kaynağa indirmek ve üç küçük doğrulama açığını kapatmak — davranış (rapor metinleri, çıkış kodları, sayılar) bayt bayt aynı kalır.

**Architecture:** Her tekrar, zaten doğru katmanda duran modüle taşınır: sabitler `history/types.py` ve `market/metrics.py`ye, katalog eşlemleri `history/catalog.py`ye, kilit çıkışı `history/lock.py`ye, Jev tavanı `jev_budget.py`ye. Kopyalar silinir, çağıranlar import eder. Bekçi testleri (AST) tekrarın geri gelmesini kırmızıya bağlar.

**Tech Stack:** Python 3.11, pytest, ruff, mypy (strict), `./verify.sh` kapısı.

**Spec:** `docs/DEFERRED.md` §16 (16g, 16j, 16k) ve §17 (17i, 17m) — tasarım belgesi yok; kalemlerin metni spec'tir.

## Global Constraints

- Davranış değişmez: bütün rapor/log satırları, çıkış kodları ve sayılar bayt bayt aynı; var olan 2123 test değiştirilmeden geçer (yalnız taşınan private adlara başvuran testlerin import satırı güncellenir).
- Mühürlü dosyalara dokunulmaz: `config/model_faz3.yaml`, `config/blend_weights_faz3.yaml`, `config/history_lock.yaml`, `config/faz3_preregistration.yaml`.
- Holdout açılmaz; DB'ye yazılmaz; migration yok; ücretli Jev çağrısı yok.
- Kapı: `TMPDIR=$(mktemp -d) ./verify.sh > <log> 2>&1`, sonuç LOG DOSYASINDAN; 10 PASS + `SKIP: zincir` adıyla (DB bağlıyken 11/11). Her commit'ten sonra tam kapı.
- Commit biçimi `<type>: <açıklama>` (refactor/fix/test/docs); her commit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` ile biter.
- Mutasyon kanıtları `PYTHONDONTWRITEBYTECODE=1` ile koşulur (bayat `.pyc` kanıtı geçersiz kılar).
- `$SCRATCH`: oturumun scratchpad dizini (depo dışı); kapı logları ve mutasyon yedekleri oraya.
- Dal: `chore/borc-temizligi` (main'den); `main`e `--no-ff`; push öncesi `git fetch && git merge --no-ff origin/main`; force/rebase yok.

## Kapsam dışı (gerekçeli — Task 7 DEFERRED'a yazar)

- **16g** (DC memo anahtarı): DEFERRED'ın önerdiği "gruptaki gözlem sayısı" düz uygulanırsa `cadence_days > 1`de aynı fit günü içinde her yeni gözlem yeniden fit tetikler (fit yalnız `at`ten önceki maçları okur → sonuç aynı, maliyet katlanır). Doğru anahtar "`at`ten önceki gözlem sayısı"dır ve ucuz hesabı sıralı parça yapısı ister — ayrı tasarım işi.
- **16k-a**: `frozen_weights` hedeflerindeki fazla lig anahtarları = 17d; Plan 2 T10 (ön kayıt ↔ renderer).
- **16k-b**: `draw` alanı `ordered` biçimde ölü, ama mühürlü `config/model_faz3.yaml` onu taşıyor (`draw: 0.26`, `draw_form: ordered`) — reddetmek mühürlü dosyayı kırar.
- **17m** kalanları: `QUESTIONS_PATH` CWD-göreli ama projedeki bütün CLI varsayılanları öyle (`CATALOG_PATH`, `LOCK_PATH`, `config/model_{phase}.yaml`) — tek başına değiştirmek tutarsızlık; `forbid_ledger_mutation()` mesajı migration ister; `_words` karesel ve yakın eşdoğrusal sorular Plan 2 tier1 işi; test dosyası boyutları ve rapordaki sabit yol düşük değer.

## Review Focus

1. **Bayt eşliği:** birleştirilen biçimleyici (`interval_text`) dört çağıranın basamak ve etiketini aynen üretmeli — `%95 ` etiketi yalnız iki denetim modülünde, 5 basamak yalnız `model_selftest`te. Var olan detay-metni testleri bunu sabitler; inceleyici `git archive` kopyasında bir çağıranın `digits`ini değiştirip kırmızıyı görmeli.
2. **Bütçe bekçisinin gevşemesi:** bekçiye `jev_budget.py`nin sarmalayıcılarını tanıtmak, o modüldeki SARMAYAN bir fonksiyonu da tanımamalı — Task 5'te mutasyonla kanıtlanır (`month_bounds(jev...)` kırmızı).
3. **`autocommit`:** `features tier1` bugün autocommit'i çağrıdan önce ayarlıyor; ortak sarmalayıcı ayarladığında `PostgresSpendLedger`in autocommit kontrolü yine geçmeli — Task 5 birim testi autocommit'in sarmalayıcıda ayarlandığını sabitler.
4. **`version: true`:** YAML `true` Python'da `== 1`dir; iki okuyucu da bool sürümü reddetmeli — Task 6 ikisini de test eder.
5. **Katalog eşlemlerinin değişmezliği:** taşınan `kinds_of`/`rating_groups` `MappingProxyType` dönmeye devam etmeli (çağıranlar paylaşır) — Task 3 testi yazmayı dener.

---

### Task 1: Tek kaynaklı sabitler — referans kitap ve log tabanı

**Files:**
- Create: `tests/test_single_sources.py`
- Modify: `src/football_edge/history/types.py` (sabit ekle)
- Modify (sabiti sil, import et): `src/football_edge/backtest/{context,evaluate,selftest,strategies,walkforward}.py`, `src/football_edge/history/lock.py`, `src/football_edge/market/{bridge,efficiency}.py`, `src/football_edge/backtest/{model_selftest,selection}.py`, `src/football_edge/model/{elo_model,pool}.py`

**Interfaces:**
- Produces: `football_edge.history.types.REFERENCE_BOOK: str = "Avg"`; `football_edge.market.metrics.LOG_FLOOR` (zaten var) tek log tabanı.

- [ ] **Step 1: Write the failing test**

```python
"""Tek kaynaklı sabitler ve yardımcılar (DEFERRED 16j, 17i): bir kez tanımlanır, her yer import eder."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "football_edge"


def _files_with_literal(value: object) -> set[str]:
    found: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.Constant)
            and type(node.value) is type(value)
            and node.value == value
            for node in ast.walk(tree)
        ):
            found.add(path.relative_to(SRC).as_posix())
    return found


def test_the_reference_book_literal_lives_in_one_place() -> None:
    # `football_data.BOOKS` kaynağın sütun adlarını sayar; `live/context` canlı kitap ortalamasının
    # yapısal karşılığıdır (başka kaynak) — ikisi de referans kitabın tanımı değildir.
    assert _files_with_literal("Avg") == {
        "history/types.py",
        "history/football_data.py",
        "live/context.py",
    }


def test_the_log_floor_literal_lives_in_one_place() -> None:
    assert _files_with_literal(1e-15) == {"market/metrics.py"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_single_sources.py -v`
Expected: 2 FAIL — "Avg" kümesinde fazladan `backtest/context.py, backtest/evaluate.py, backtest/selftest.py, backtest/strategies.py, backtest/walkforward.py, history/lock.py, market/bridge.py, market/efficiency.py`; 1e-15 kümesinde fazladan `backtest/model_selftest.py, backtest/selection.py, model/elo_model.py, model/pool.py`.

- [ ] **Step 3: Minimal implementation**

`src/football_edge/history/types.py`, `CLOSING = "close"` satırından sonra:

```python
# football-data'nın piyasa ortalaması: (REFERENCE_BOOK, CLOSING) = AvgC, referans kapanış (D3);
# (REFERENCE_BOOK, PRE_CLOSING) = Avg. Tarihsel tabanın her okuyucusu kitabı buradan alır.
REFERENCE_BOOK = "Avg"
```

Her modülde yerel tanımı sil, `from football_edge.history.types import REFERENCE_BOOK` ekle (modülün var olan `history.types` importuna katılır):
- `backtest/evaluate.py:26`, `backtest/selftest.py:36`, `backtest/walkforward.py:43` — `REFERENCE_BOOK = "Avg"` satırı silinir; `walkforward.py:42` `PRE_BOOK`teki `"Avg"` → `REFERENCE_BOOK` (tanım sırası: `REFERENCE_BOOK` artık import, `PRE_BOOK` onu kullanabilir).
- `backtest/context.py:36` — `CONTEXT_BOOK = "Avg"` silinir; `:47`deki kullanım `REFERENCE_BOOK` olur.
- `backtest/strategies.py:74, :151` — `book: str = "Avg"` → `book: str = REFERENCE_BOOK`.
- `history/lock.py:38` — `_REFERENCE_BOOK = "Avg"` silinir; `:109` `REFERENCE_BOOK` olur (import satırı `from football_edge.history.types import CLOSING, H2H, REFERENCE_BOOK, HistMatch` — ruff isort sırasına bırak).
- `market/bridge.py:34` — `REFERENCE_BOOK = "Avg"  # ...` satırı silinir, yorumu `types.py`dekiyle aynı olduğu için taşınmaz; `:178` aynı adla çalışır.
- `market/efficiency.py:46` — `AVERAGE = "Avg"  # ...` silinir; `:178, :210, :230, :253, :304`deki `AVERAGE` → `REFERENCE_BOOK`.

Log tabanı: `from football_edge.market.metrics import LOG_FLOOR` ekle, yerel tanımı sil, kullanımları yeniden adlandır:
- `backtest/model_selftest.py:38` (`_LOG_FLOOR`) — `:141, :142` → `LOG_FLOOR` (bu modül `market.metrics`ten zaten import ediyor: listeye ekle).
- `backtest/selection.py:59` — `:147, :174` → `LOG_FLOOR`.
- `model/elo_model.py:36` — `:119, :135` → `LOG_FLOOR`.
- `model/pool.py:19` — `LOG_FLOOR = 1e-15` silinir, yerine `from football_edge.market.metrics import LOG_FLOOR` (adı modülde kalır; `pool.LOG_FLOOR`a başvuran olursa bozulmaz).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_single_sources.py -v && grep -rnE '(_REFERENCE_BOOK|CONTEXT_BOOK|\bAVERAGE\b|_LOG_FLOOR)' src/`
Expected: 2 PASS; grep çıktısı boş.

- [ ] **Step 5: Full gate + commit**

```bash
TMPDIR=$(mktemp -d) ./verify.sh > "$SCRATCH/t1.log" 2>&1; echo $?; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$SCRATCH/t1.log"
git add -A src tests/test_single_sources.py
git commit -m "refactor: referans kitap ve log tabanı tek kaynaktan (DEFERRED 16j)"
```
Expected: exit 0, `KAPI YEŞİL`.

---

### Task 2: Paylaşılan ölçüm yardımcıları — aralık metni, ΔLL, "ölçülemedi", kalibrasyon

**Files:**
- Modify: `src/football_edge/market/metrics.py` (`interval_text`, `calibration_or_none` ekle)
- Modify: `src/football_edge/backtest/wf_eval.py` (`_gap` → `log_loss_gap` public; `_calibration` silinir)
- Modify: `src/football_edge/backtest/selftest.py` (`_unmeasured` → `unmeasured` public; `_interval` silinir)
- Modify: `src/football_edge/backtest/model_selftest.py` (`_gap`, `_unmeasured`, `_text` silinir)
- Modify: `src/football_edge/backtest/wf_run.py` (`format_interval` delege eder)
- Modify: `src/football_edge/market/efficiency.py` (`_interval` delege eder)
- Modify: `src/football_edge/backtest/evaluate.py` (`calibration_or_none`; `Evaluation.calibration: Calibration | None`)
- Test: `tests/test_metrics.py`, `tests/test_evaluate.py`, `tests/test_walkforward.py` (yalnız `wf_eval._calibration` başvuruları)

**Interfaces:**
- Consumes: Task 1'in `REFERENCE_BOOK` importları (aynı dosyalar; çakışma yok, sırayla).
- Produces: `metrics.interval_text(interval: Interval, *, digits: int = 4, label: str = "") -> str`; `metrics.calibration_or_none(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> Calibration | None`; `wf_eval.log_loss_gap(first, second, outcomes, resamples) -> Interval`; `selftest.unmeasured(check_id: str, *, gate: bool, reason: str) -> Check`.

- [ ] **Step 1: Write the failing tests**

`tests/test_metrics.py` sonuna (import listesine `Interval, calibration_or_none, interval_text` ve `CalibrationUnfit` eklenir):

```python
# ── Tek aralık biçimi ve ölçülemeyen kalibrasyon (DEFERRED 16j, 17i) ─────────────────────────


def test_interval_text_keeps_every_callers_digits_and_label() -> None:
    interval = Interval(estimate=0.123456, low=-0.000049, high=1.5)

    assert interval_text(interval) == "0.1235 [-0.0000, 1.5000]"
    assert interval_text(interval, label="%95 ") == "0.1235 [%95 -0.0000, 1.5000]"
    assert interval_text(interval, digits=5, label="%95 ") == "0.12346 [%95 -0.00005, 1.50000]"


def test_an_unmeasurable_calibration_is_none() -> None:
    """Yayılımsız tahmin (tekil fit) "ölçülemedi"dir: None, koşu sürer."""
    assert calibration_or_none(((0.5, 0.5),) * 4, (0, 1, 0, 1)) is None


def test_a_shape_error_in_calibration_or_none_is_raised_not_swallowed() -> None:
    """Bileşen hatası "ölçülemedi" basılırsa açılış kalibrasyonsuz harcanır (R135)."""
    with pytest.raises(ValueError, match="sayısı farklı") as raised:
        calibration_or_none(((0.6, 0.4), (0.3, 0.7)), (0,))

    assert not isinstance(raised.value, CalibrationUnfit)
```

`Interval`in alan adları `estimate, low, high` (`market/metrics.py:35`); kurucusu farklı alan istiyorsa testte o alanlar da verilir — Step 2'de görülür.

`tests/test_evaluate.py` sonuna (import: `from dataclasses import replace`):

```python
def test_an_unmeasurable_calibration_is_none_not_a_crash() -> None:
    """Yayılımsız tahmin (tekil fit) ölçülemez: değerlendirme None taşır, düşmez (DEFERRED 17i)."""
    result = _replay()
    flat = replace(
        result, predictions=tuple(replace(p, probs=OPEN) for p in result.predictions)
    )

    assert evaluate(flat, method=MULTIPLICATIVE, resamples=50).calibration is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_metrics.py tests/test_evaluate.py -v -k "interval_text or unmeasurable or calibration_or_none"`
Expected: test_metrics ImportError (`interval_text` tanımsız) ; test_evaluate `CalibrationUnfit` yükselir. (Tek biçimli 3'lü olasılık tekil fit vermezse — yani evaluate testi CalibrationUnfit DEĞİL başka bir şeyle düşerse ya da geçerse — dur ve bildir; test verisi yanlıştır.)

- [ ] **Step 3: Minimal implementation**

`market/metrics.py`, `calibration()` tanımından sonra:

```python
def calibration_or_none(
    probs: Sequence[Sequence[float]], outcomes: Sequence[int]
) -> Calibration | None:
    """Yalnız ölçülemeyen fit (`CalibrationUnfit`) None'dır; biçim/değer hatası yükselir.

    Bileşen hatası "ölçülemedi" diye basılsaydı açılış kalibrasyonsuz harcanırdı (R135)."""
    try:
        return calibration(probs, outcomes)
    except CalibrationUnfit:
        return None


def interval_text(interval: Interval, *, digits: int = 4, label: str = "") -> str:
    """`tahmin [etiket alt, üst]` — raporların ve denetimlerin tek aralık biçimi (DEFERRED 16j)."""
    return (
        f"{interval.estimate:.{digits}f} "
        f"[{label}{interval.low:.{digits}f}, {interval.high:.{digits}f}]"
    )
```

`backtest/wf_eval.py`: `_calibration` fonksiyonu silinir, `score()` içinde `calibration=calibration_or_none(probs, outcomes)`; import listesinden `calibration`/`CalibrationUnfit` kullanılmıyorsa çıkar, `calibration_or_none` eklenir. `def _gap(` → `def log_loss_gap(`; `:232, :242, :323, :327` çağrıları yeniden adlandırılır.

`backtest/evaluate.py`: `Evaluation.calibration: Calibration | None`; `:85` `calibration=calibration_or_none(probs, outcomes)`; import `calibration` → `calibration_or_none`.

`backtest/selftest.py`: `def _unmeasured(` → `def unmeasured(`; `:100, :130, :161, :180, :216` yeniden adlandırılır. `_interval` silinir; `:106, :166, :185`de `_interval(interval)` → `interval_text(interval, label="%95 ")` (import `from football_edge.market.metrics import ... interval_text`).

`backtest/model_selftest.py`:
- `_text`, `_gap`, `_unmeasured` silinir.
- Modül sabiti: `E_UNMEASURED = "E bölgesinde uygun satır yok"`.
- `_unmeasured("W1", True)` → `unmeasured("W1", gate=True, reason=E_UNMEASURED)`; `:91, :120, :138`deki her çağrı `gate=` değeri korunarak aynı biçime.
- `_gap(` → `log_loss_gap(` (`:94, :121`); `_text(x)` → `interval_text(x, digits=5, label="%95 ")` (`:107, :128`).
- Importlar: `from football_edge.backtest.selftest import Check, unmeasured`; `from football_edge.backtest.wf_eval import blended, complete, fold_weights, log_loss_gap`; `interval_text` metrics importuna.

`backtest/wf_run.py:139`:

```python
def format_interval(interval: Interval | None) -> str:
    return "ölçülemedi" if interval is None else interval_text(interval)
```

`market/efficiency.py:432`:

```python
def _interval(interval: Interval | None) -> str:
    return "—" if interval is None else interval_text(interval)
```

`tests/test_walkforward.py:455-476`: `wf_eval._calibration` → `calibration_or_none` (import `from football_edge.market.metrics import calibration_or_none`); test gövdeleri değişmez.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_metrics.py tests/test_evaluate.py tests/test_walkforward.py tests/test_selftest.py tests/test_model_selftest.py tests/test_final_eval.py tests/test_market_cli.py -q && grep -rnE 'def (_gap|_unmeasured|_calibration|_text)\(' src/football_edge/backtest/`
Expected: hepsi PASS; grep boş.

- [ ] **Step 5: Full gate + commit**

```bash
TMPDIR=$(mktemp -d) ./verify.sh > "$SCRATCH/t2.log" 2>&1; echo $?; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$SCRATCH/t2.log"
git add -A src tests
git commit -m "refactor: aralık metni, ΔLL, ölçülemedi ve kalibrasyon yardımcıları tek yerde (DEFERRED 16j, 17i)"
```

---

### Task 3: Katalog eşlemleri `history/catalog.py`de

**Files:**
- Modify: `src/football_edge/history/catalog.py` (`kinds_of`, `rating_groups` ekle)
- Modify: `src/football_edge/backtest/__main__.py:141-145, :178-179` (tanımlar silinir, import)
- Modify: `src/football_edge/live/__main__.py:25-28` (import kaynağı)
- Modify: `src/football_edge/backtest/final_eval.py:287, :361` (satır içi sözlük → `rating_groups(catalog)`)
- Test: `tests/test_history_catalog.py`

**Interfaces:**
- Produces: `catalog.kinds_of(catalog: Catalog) -> Mapping[str, str]`, `catalog.rating_groups(catalog: Catalog) -> Mapping[str, str]` — ikisi de `MappingProxyType`.

- [ ] **Step 1: Write the failing test**

`tests/test_history_catalog.py` import listesine `kinds_of, rating_groups`; sona:

```python
def test_kinds_and_rating_groups_map_every_league_code_read_only() -> None:
    """Elo grubu (R94) ülke, tür katalogdaki tür; eşlemler paylaşıldığı için yazılamaz."""
    catalog = load_catalog(CATALOG)
    codes = {league.code for league in catalog.leagues}

    assert set(kinds_of(catalog)) == codes == set(rating_groups(catalog))
    assert all(rating_groups(catalog)[lg.code] == lg.country for lg in catalog.leagues)
    assert all(kinds_of(catalog)[lg.code] == lg.kind for lg in catalog.leagues)
    with pytest.raises(TypeError):
        kinds_of(catalog)["XX"] = "main"  # type: ignore[index]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_history_catalog.py -v -k kinds_and_rating`
Expected: ImportError (`kinds_of` catalog'da yok).

- [ ] **Step 3: Minimal implementation**

`history/catalog.py` (importlar: `from collections.abc import Mapping`, `from types import MappingProxyType`), `load_catalog`tan sonra:

```python
def kinds_of(catalog: Catalog) -> Mapping[str, str]:
    """Lig kodu → tür (ana/alt lig): walk-forward satırları ve ağırlık fiti buradan okur."""
    return MappingProxyType({league.code: league.kind for league in catalog.leagues})


def rating_groups(catalog: Catalog) -> Mapping[str, str]:
    """Elo'nun reyting grubu (R94): lig kodu → ülke. Elo'yu kuran her yol grupları buradan alır;
    selftest Elo kurmaz (K1–K4 fiyat ve Placebo ile ölçülür)."""
    return MappingProxyType({league.code: league.country for league in catalog.leagues})
```

`backtest/__main__.py`: iki tanım silinir; `from football_edge.history.catalog import ...` listesine `kinds_of, rating_groups` (adlar modül isim alanında kalır: `tests/test_backtest_cli.py:279`deki `cli.rating_groups` çalışır). `live/__main__.py:25-28`: `kinds_of, rating_groups` `backtest.__main__` import bloğundan çıkar, `history.catalog` importuna girer. `final_eval.py:287, :361`: `rating_groups={league.code: league.country for league in catalog.leagues}` → `rating_groups=rating_groups(catalog)` (import eklenir; yerel parametre adı `rating_groups` ile gölgelenme varsa — `:168` fonksiyon parametresi — import `from football_edge.history import catalog as history_catalog` ile yapılır ve `history_catalog.rating_groups(catalog)` çağrılır).

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_history_catalog.py tests/test_backtest_cli.py tests/test_live_cli.py tests/test_final_eval.py -q && grep -rn "def kinds_of\|def rating_groups" src/`
Expected: PASS; grep yalnız `history/catalog.py`.

- [ ] **Step 5: Full gate + commit**

```bash
TMPDIR=$(mktemp -d) ./verify.sh > "$SCRATCH/t3.log" 2>&1; echo $?; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$SCRATCH/t3.log"
git add -A src tests
git commit -m "refactor: kinds_of ve rating_groups history/catalog.py'de (DEFERRED 16j)"
```

---

### Task 4: Kilit ihlali çıkışı tek yerde

**Files:**
- Modify: `src/football_edge/history/lock.py` (`EXIT_LOCK_VIOLATION`, `refuse_on_violation`)
- Modify: `src/football_edge/backtest/__main__.py:74, :161-163, :190-192`; `src/football_edge/live/__main__.py:164-166, :221-223, :269-271, :328-330`; `src/football_edge/history/__main__.py:51`; `src/football_edge/market/__main__.py:51`
- Test: `tests/test_history_lock.py`

**Interfaces:**
- Produces: `lock.EXIT_LOCK_VIOLATION: int = 9`; `lock.refuse_on_violation(logger: logging.Logger, error: LockViolation, what: str) -> int`.

- [ ] **Step 1: Write the failing test**

`tests/test_history_lock.py` (import: `import logging`, ve lock'tan `EXIT_LOCK_VIOLATION, refuse_on_violation`):

```python
def test_a_lock_violation_is_logged_by_name_and_exits_nine(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Kilidi okuyan her CLI aynı satırı ve aynı kodu verir (R99; DEFERRED 17i)."""
    logger = logging.getLogger("test.lock")
    with caplog.at_level(logging.ERROR, logger="test.lock"):
        code = refuse_on_violation(logger, LockViolation("E0: a", "E1: b"), "gölge tahmin koşulmadı")

    assert (code, EXIT_LOCK_VIOLATION) == (9, 9)
    assert caplog.messages == ["kilit ihlali — gölge tahmin koşulmadı: E0: a; E1: b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_history_lock.py -v -k exits_nine`
Expected: ImportError.

- [ ] **Step 3: Minimal implementation**

`history/lock.py` (import `logging`), `LockViolation` sınıfından sonra:

```python
EXIT_LOCK_VIOLATION = 9  # kilidi okuyan her CLI'ın veri farkı çıkışı (R99)


def refuse_on_violation(logger: logging.Logger, error: LockViolation, what: str) -> int:
    """`kilit ihlali — <ne yapılmadı>: <farklar>` yazar ve kilit çıkış kodunu döner."""
    logger.error("kilit ihlali — %s: %s", what, "; ".join(error.differences))
    return EXIT_LOCK_VIOLATION
```

Altı blok bu biçime iner (mesajın `—` sonrası ile `:` arası `what` olur, bayt bayt aynı):

```python
    except LockViolation as error:
        return refuse_on_violation(LOGGER, error, "gölge tahmin koşulmadı")
```

`what` değerleri: `backtest/__main__.py:161` "bilinen sonuçlar koşulmadı", `:190` "koşulmadı"; `live/__main__.py:164` "gölge tahmin koşulmadı", `:221` "eşitlik raporu koşulmadı", `:269` "ağırlık dondurulmadı", `:328` "gölge raporu koşulmadı".

`EXIT_LOCK_VIOLATION = 9` tanımları (`backtest/__main__.py:74`, `history/__main__.py:51`, `market/__main__.py:51`) silinir, `history.lock`tan import edilir; `live/__main__.py` onu `backtest.__main__` yerine `history.lock`tan alır. `history/__main__.py:111` ve `market/__main__.py:121` blokları FARKLI mesaj basar ("KİLİT İHLALİ: …", "kilit doğrulanamadı — …") — onlara dokunulmaz, yalnız sabit ortaklaşır.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_history_lock.py tests/test_backtest_cli.py tests/test_live_cli.py tests/test_history_cli.py tests/test_market_cli.py -q && grep -rn "EXIT_LOCK_VIOLATION = " src/`
Expected: PASS; grep yalnız `history/lock.py`.

- [ ] **Step 5: Full gate + commit**

```bash
TMPDIR=$(mktemp -d) ./verify.sh > "$SCRATCH/t4.log" 2>&1; echo $?; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$SCRATCH/t4.log"
git add -A src tests
git commit -m "refactor: kilit ihlali çıkışı history/lock.py'de tek yardımcı (DEFERRED 17i)"
```

---

### Task 5: Jev tavan sarmalayıcısı `jev_budget.py`de; bekçi onu tanır

**Files:**
- Modify: `src/football_edge/jev_budget.py` (`budgeted_jev`)
- Modify: `src/football_edge/collect.py:369-380` ve `:390, :473`; `src/football_edge/features/__main__.py:85-92`, `:120`, `:128`
- Modify: `tests/test_jev_spend_paths.py` (`_call_sites`: bütçe modülünün sarmalayıcıları)
- Test: `tests/test_jev_budget.py`

**Interfaces:**
- Produces: `jev_budget.budgeted_jev(jev: JevClient, spend_conn: psycopg.Connection[Any], *, clock: Callable[[], datetime]) -> BudgetedJev`.

- [ ] **Step 1: Write the failing test**

`tests/test_jev_budget.py` (import: `from football_edge.jev_budget import budgeted_jev` ve var olan `BudgetExceeded`, `MONTHLY_CAP_USD`; `from tests.fake_spend_db import FakeSpendConn`; `from tests.fake_jev import FakeJev`; `ChoiceAnswer`):

```python
def test_budgeted_jev_opens_an_autocommit_ledger_and_enforces_the_monthly_cap() -> None:
    """Her Jev yolunun ortak sarmalayıcısı (DEFERRED 17i): defter autocommit, tavan dolu ayda
    çağrı YAPILMAZ."""
    conn = FakeSpendConn(total=Decimal(str(MONTHLY_CAP_USD)))
    jev = FakeJev(ChoiceAnswer(choice="a", confidence=0.9, probabilities={}))

    client = budgeted_jev(jev, conn, clock=lambda: datetime(2026, 9, 23, tzinfo=UTC))  # type: ignore[arg-type]

    assert conn.autocommit is True
    with pytest.raises(BudgetExceeded):
        client.ask_choice({"x": 1}, "hangisi?", {"a": "a"})
```

(`FakeJev`in çağrı sayacının adı `tests/fake_jev.py`den okunur; varsa `assert <sayaç> == 0` eklenir.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_jev_budget.py -v -k budgeted_jev_opens`
Expected: ImportError (`budgeted_jev`).

- [ ] **Step 3: Minimal implementation**

`jev_budget.py`, `BudgetedJev` sınıfından sonra:

```python
def budgeted_jev(
    jev: JevClient, spend_conn: psycopg.Connection[Any], *, clock: Callable[[], datetime]
) -> BudgetedJev:
    """Her Jev çağrı yolunun ortak tavanı (spec §9, R159): her çağrı `jev_spend`e AYRI,
    autocommit bağlantıda yazılır — komutun işlemi geri alınsa da faturalanan çağrının kaydı kalır."""
    spend_conn.autocommit = True
    return BudgetedJev(
        jev,
        PostgresSpendLedger(spend_conn),
        cap_usd=MONTHLY_CAP_USD,
        estimate_usd=ESTIMATE_USD_UNMEASURED,
        clock=clock,
    )
```

`collect.py`: `_budgeted` silinir; `:390` ve `:473` → `budgeted_jev(jev, spend_conn, clock=lambda: datetime.now(UTC))`; kullanılmayan importlar (`BudgetedJev`, `PostgresSpendLedger`, `MONTHLY_CAP_USD`, `ESTIMATE_USD_UNMEASURED`) ruff'ın gösterdiği kadarıyla çıkar. `features/__main__.py`: `_budgeted` silinir; `:120` `spend_conn.autocommit = True` silinir (sarmalayıcı ayarlar; `load_news` vb. `conn`u kullanır, `spend_conn`u değil — satırdan önce `spend_conn` okunmadığı Step 4'te grep ile doğrulanır); `:128` → `budgeted_jev(jev, spend_conn, clock=_now)`.

`tests/test_jev_spend_paths.py`:

```python
BUDGET_MODULE = SRC / "jev_budget.py"
```
(EXEMPT'in altına), ve `_call_sites` içinde:

```python
        parents = _parents(tree)
        # Bütçe modülünün kendi sarmalayıcıları (`budgeted_jev`) import edilip çağrılır; o modülün
        # SARMAYAN fonksiyonları tanınmaz — `_wrappers` yalnız `BudgetedJev(ilk_param, …)` kuranları sayar.
        wrappers = _wrappers(tree) | _wrappers(ast.parse(BUDGET_MODULE.read_text(encoding="utf-8")))
```

- [ ] **Step 4: Run tests + mutation proofs**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_jev_budget.py tests/test_jev_spend_paths.py tests/test_feature_tier1.py tests/test_collect.py -q && grep -rn "def _budgeted" src/`
Expected: PASS; grep boş.

Mutasyonlar (her biri `git stash`siz, dosya kopyasıyla geri alınır; `PYTHONDONTWRITEBYTECODE=1`):
1. `jev_budget.py`ye SARMAYAN bir fonksiyon ekle (`def leak(jev: JevClient, spend_conn: Any, *, clock: Any) -> JevClient: return jev`) ve `collect.py`nin `_map_entities_main`indeki `budgeted_jev(jev, …)` çağrısını `leak(jev, …)` yap (import ederek) → `test_every_type_safe_jev_outside_the_budget_module_is_wrapped_in_budgeted_jev` KIRMIZI olmalı (`collect.py:<satır>` sarılmamış). Yeşil kalırsa bekçi bütçe modülünün her adını tanıyor demektir: dur.
2. `budgeted_jev`ten `spend_conn.autocommit = True` satırını sil → yeni birim testi ve `test_map_entities_records_every_jev_call_in_the_spend_ledger` KIRMIZI.
Geri al, `git diff --stat` yalnız görev değişikliklerini göstermeli.

- [ ] **Step 5: Full gate + commit**

```bash
TMPDIR=$(mktemp -d) ./verify.sh > "$SCRATCH/t5.log" 2>&1; echo $?; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$SCRATCH/t5.log"
git add -A src tests
git commit -m "refactor: Jev tavan sarmalayıcısı jev_budget.budgeted_jev; bekçi bütçe modülünün sarmalayıcılarını tanır (DEFERRED 17i)"
```

---

### Task 6: Üç doğrulama açığı — Elo yapılandırması, bool sürüm, kaydırma uzunluğu

**Files:**
- Modify: `src/football_edge/model/elo_model.py:55-67`
- Modify: `src/football_edge/backtest/model_config.py:90`, `src/football_edge/live/weights.py:167`
- Modify: `src/football_edge/features/shift.py:16`
- Test: `tests/test_elo_model.py`, `tests/test_model_selection.py`, `tests/test_live_weights.py`, `tests/test_feature_shift.py`

**Interfaces:** yok (yalnız reddetme).

- [ ] **Step 1: Write the failing tests**

`tests/test_elo_model.py` (import `EloModelConfig` zaten varsa kullanılır):

```python
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("k", 0.0, "K pozitif"),
        ("k", float("nan"), "K pozitif"),
        ("home_advantage", float("inf"), "ev avantajı"),
        ("initial", float("nan"), "başlangıç"),
        ("initial", 0.0, "başlangıç"),
        ("season_gap_days", 0, "sezon arası"),
        ("season_gap_days", 60.5, "sezon arası"),
        ("season_gap_days", True, "sezon arası"),
    ],
)
def test_an_invalid_elo_config_is_refused_by_name(field: str, value: object, message: str) -> None:
    """NaN K ya da sıfır başlangıç sessizce NaN reyting üretirdi (DEFERRED 16k)."""
    with pytest.raises(ValueError, match=message):
        EloModelConfig(**{field: value})  # type: ignore[arg-type]


def test_the_sealed_faz3_elo_config_still_loads() -> None:
    from football_edge.backtest.model_config import load_model_config

    config = load_model_config(Path("config/model_faz3.yaml"))
    assert config.elo.k == 10.0
```

(`Path` importu yoksa eklenir; testler depo kökünden koşar — kapı öyle koşar.)

`tests/test_model_selection.py:181` parametrize listesine `lambda text: text.replace("version: 1", "version: true"),` ve `ids`e `"version-bool"`.

`tests/test_live_weights.py:196` listesine `(lambda p: p.update(version=True), "sürüm"),`.

`tests/test_feature_shift.py`:

```python
@pytest.mark.parametrize("probs", [(0.5, 0.5), (0.2, 0.3, 0.3, 0.2)])
def test_a_probability_vector_that_is_not_three_way_is_refused(probs: tuple[float, ...]) -> None:
    """`β·f = 0` kısa yolu girdiyi aynen döndürürdü: 2'li vektör 1X2 diye geçerdi (DEFERRED 17m)."""
    with pytest.raises(ValueError, match="üç olasılık"):
        shift(probs, [], [])  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_elo_model.py tests/test_model_selection.py tests/test_live_weights.py tests/test_feature_shift.py -q -k "invalid_elo or sealed_faz3 or version or malformed or three_way"`
Expected: 8 Elo durumu FAIL (DID NOT RAISE), `version-bool` FAIL, `version=True` FAIL, 2 shift FAIL; `sealed_faz3` PASS (bekçi: mühürlü dosya bugün yükleniyor).

- [ ] **Step 3: Minimal implementation**

`elo_model.py` `__post_init__` sonuna:

```python
        if not (math.isfinite(self.k) and self.k > 0.0):
            raise ValueError(f"K pozitif ve sonlu olmalı: {self.k}")
        if not math.isfinite(self.home_advantage):
            raise ValueError(f"ev avantajı sonlu olmalı: {self.home_advantage}")
        if not (math.isfinite(self.initial) and self.initial > 0.0):
            raise ValueError(f"başlangıç reytingi pozitif ve sonlu olmalı: {self.initial}")
        if type(self.season_gap_days) is not int or self.season_gap_days < 1:
            raise ValueError(f"sezon arası ≥ 1 tam gün olmalı: {self.season_gap_days!r}")
```

`model_config.py:90` ve `weights.py:167`:

```python
    if type(raw["version"]) is not int or raw["version"] != VERSION:
```

(YAML `true` Python'da `== 1`dir; bool `int`in alt sınıfı olduğu için `isinstance` yetmez.)

`shift.py`, fonksiyonun ilk satırı:

```python
    if len(probs) != 3:
        raise ValueError(f"üç olasılık (ev, beraberlik, deplasman) olmalı: {probs}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: aynı komut, sonra `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_model_selection.py tests/test_elo_model.py -q`
Expected: hepsi PASS (ızgara değerleri — `selection.ELO_GRID` — ve mühürlü `model_faz3.yaml` yeni kontrollerden geçer).

- [ ] **Step 5: Full gate + commit**

```bash
TMPDIR=$(mktemp -d) ./verify.sh > "$SCRATCH/t6.log" 2>&1; echo $?; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$SCRATCH/t6.log"
git add -A src tests
git commit -m "fix: Elo yapılandırması, bool sürüm ve 3'lü olmayan kaydırma adıyla reddedilir (DEFERRED 16k, 17m)"
```

---

### Task 7: DEFERRED ve HANDOFF

**Files:**
- Modify: `docs/DEFERRED.md` §16 (16g, 16j, 16k satırları), §17 (17i, 17m satırları)
- Modify: `docs/HANDOFF.md` §0 (başlık durumu, §0.4 seçenek 2 "yapıldı", kapının ölçmediği)

- [ ] **Step 1:** 16j ve 17i satırlarının "Ne zaman bakılır" hücresine `**Kapandı 2026-09-23** (plan 2026-09-23-kucuk-borc-temizligi, T1–T5)` yaz.
- [ ] **Step 2:** 16k: "(c) kapandı (T6); (a) = 17d, Plan 2 T10; (b) mühürlü `model_faz3.yaml` `draw` taşıyor — reddetmek mühürlü dosyayı kırar, bir sonraki model dosyası `ordered`da `draw`sız yazılır".
- [ ] **Step 3:** 16g: "Ne zaman bakılır" hücresine bu planın "Kapsam dışı" gerekçesini ekle (gözlem sayısı anahtarı `cadence_days > 1`de her gözlemde yeniden fit; doğru anahtar `at`ten önceki gözlem sayısı).
- [ ] **Step 4:** 17m: kapananlar (`version: true`, `shift` uzunluğu); kalanların gerekçesi (planın "Kapsam dışı"ı).
- [ ] **Step 5:** HANDOFF §0.4'ün 2. seçeneğine "yapıldı (2026-09-23)" ve kapsam; §0'a "kapının ölçmediği": birleştirmeler davranışı korur ama bayt eşliğini yalnız var olan detay-metni testleri sabitler — metnini test etmeyen bir rapor satırı (ör. `efficiency` tablo satırları `test_market_cli`nin kapsadığı kadar) değişse kapı görmez.
- [ ] **Step 6: Full gate + commit**

```bash
TMPDIR=$(mktemp -d) ./verify.sh > "$SCRATCH/t7.log" 2>&1; echo $?; grep -E '^(PASS|FAIL|SKIP)|KAPI' "$SCRATCH/t7.log"
git add docs/DEFERRED.md docs/HANDOFF.md
git commit -m "docs: DEFERRED 16g/16j/16k/17i/17m durumu; HANDOFF §0 borç temizliği"
```

---

## Bitiş

1. Bütün-dal incelemesi (`general-purpose`, kabuk ister): planla eşlik, Review Focus'un 5 maddesi, her görevin mutasyonu `git archive` kopyasında BAĞIMSIZ.
2. `git checkout main && git merge --no-ff chore/borc-temizligi`; tam kapı (DB bağlı 11/11); `git fetch && git merge --no-ff origin/main`; push; CI yeşil.
