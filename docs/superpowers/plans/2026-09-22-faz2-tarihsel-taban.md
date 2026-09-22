# Faz 2 — Tarihsel Taban, Backtest Harness, Piyasa Verimliliği — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modeli ölçecek aracı model yazılmadan önce kurmak — football-data.co.uk'tan kilitli bir
tarihsel taban, sızıntıya yapısal olarak kapalı bir backtest harness'ı, vig temizleme ve lig başına
piyasa verimliliği ölçümü — ve hangi liglerde oynanacağına ölçümle karar vermek.

**Architecture:** CSV'ler runner'da `_guarded_get` ile çekilir ve özel Postgres'te ham dosya olarak
önbelleğe alınır; ayrıştırma saf koddur (`history/`). Geliştirme ve holdout dönemlerinin satır
özetleri depoya kilitlenir; holdout satırları kayıt bırakan bir anahtar olmadan okunamaz. Harness
(`backtest/`) olay akışıyla yeniden oynatır: strateji yalnız karar anından önce bilinen sonuçları
görür, kapanış ve sonuç tiple ayrılmış bir değerlendirme kaydındadır. Vig, ölçütler, verimlilik ve
canlı köprü `market/` altında saf fonksiyonlardır.

**Tech Stack:** Python 3.11, uv, numpy (tek yeni bağımlılık), httpx, protego, psycopg3, PyYAML,
pytest, ruff, mypy (strict), Supabase Postgres (pg_cron → `workflow_dispatch`), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-22-faz2-tarihsel-taban-design.md` (onaylı, D1–D20) — ana
spec `docs/superpowers/specs/2026-09-19-football-edge-design.md` (§3.2.1, §6.2 holdout politikası).
**Ölçümler:** `docs/superpowers/specs/2026-09-22-faz2-olcumler-ve-kararlar.md` (§2.1–2.4, §4.1).
**Süreç:** `docs/superpowers/plans/2026-09-21-yol-haritasi-v2-paralel-izler.md` (§3 risk kademeleri,
§4 paralellik).

## Global Constraints

- Python `>=3.11`; `from __future__ import annotations` her modülde.
- Yeni bağımlılık YALNIZ `numpy>=2.1` (D15). pandas, scipy, statsmodels YOK.
- `mypy --strict` `src` ve `scripts`te geçer; `ruff check` + `ruff format --check` (satır ≤ 100,
  kurallar `E F I UP B SIM T20` — `src/`de `print` yok).
- Kod yorumu kısa bir "neden" taşır; tarihçe commit mesajında. Test adları İngilizce; yorumlar,
  docstring'ler ve hata/log mesajları Türkçe.
- Değişmezlik: veri tipleri `@dataclass(frozen=True)`; eşleme alanları `types.MappingProxyType`;
  fonksiyonlar girdiyi değiştirmez, yeni değer döner.
- Dosya ≤ 800 satır (hedef 200–400); fonksiyon < 50 satır kılavuzdur.
- Ham üçüncü taraf içeriği depoya, loga, artifact'e GİRMEZ (spec §3.2/4, Ruling 4): testler gerçek
  football-data BAŞLIKLARIYLA sentetik satırlar kullanır; raporlar yalnız toplu sayı taşır.
- Secret taraması test dosyalarını da tarar: kaynakta `DATABASE_URL=` ya da `ODDS_API_KEY=` biçimli
  dize yazılmaz; gerekiyorsa ad parçalardan kurulur (`"DATABASE" + "_URL"`).
- Erişim: yalnız `collector._guarded_get` (robots her yolda, yönlendirme sıçramaları denetlenir),
  dürüst kimlik `football-edge/0.1 (+https://github.com/popiliadam/football-edge)`, istekler arası
  3 sn. Scrapling fetcher'ları ve tablodaki yasak araçlar kullanılamaz (R77, R80;
  `tests/test_access_method_rule.py` zorlar).
- Dönemler (kaynağın `Date`'ine göre): geliştirme `< 2025-07-01`, holdout `[2025-07-01,
  2026-07-01)`, sonrası `≥ 2026-07-01`. **Faz 2 holdout'u hiç açmaz** (`open_holdout` çağrısı yok).
- Karar anı: maç günü cuma/cumartesi/pazar/pazartesi → o gün ya da önceki son CUMA; salı/çarşamba/
  perşembe → son SALI; saat 12:00 Europe/London. Sonuç: başlama + 3 sa; saat yoksa ertesi gün
  03:00 Europe/London (D4, D5).
- Referans kapanış `AvgC*` (D3); vig yöntemleri `multiplicative`, `power`, `shin` (D9).
- Append-only tablolar 0001'in `forbid_ledger_mutation()` tetikleyicisiyle korunur.
- Commit: `<type>: <açıklama>` + `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`; yalnız açık
  yollar `git add` edilir (`git add -A` YOK).
- Her commit'ten SONRA kapının tamamı: `TMPDIR=$(mktemp -d) ./verify.sh`, log DOSYASINDAN okunur;
  paralel işler yüzünden `TMPDIR` her koşuda ayrı.
- Mutasyon kanıtı `PYTHONDONTWRITEBYTECODE=1` ile, her mutasyon geri alınır; son doğrulama taze
  klonda, `TMPDIR` klonun dışında.

---

## Tasarım ↔ görev eşlemesi

| Tasarım | Görev | Dalga | Kademe |
|---|---|---|---|
| §12 dalga 0, D15 | Task 0 — ortak tipler ve bağımlılık (controller) | 0 | — |
| §4.2, §4.4, D19 | Task 1 — lig kataloğu ve ayrıştırıcı (T1a) | 1 | K2 |
| §6, §7.5, D9, D11 | Task 2 — vig ve ölçütler (T3) | 1 | K1 |
| §5, D8 | Task 3 — kilit ve holdout (T5) | 1 | K1 |
| §4.5, §7.1–7.4, D4, D5, D10 | Task 4 — harness iskeleti (T2a) | 1 | K1 |
| §11 | Task 5 — dalga 1 birleştirmesi ve `sızıntı` adımı (controller) | 1 sonu | — |
| §4.1, §4.3, D6, D7, D20 | Task 6 — senkron, önbellek, kayıt defteri (T1b) | 2 | K2 |
| §9 | Task 7 — tarihsel ↔ canlı köprü (T7) | 2 | K2 |
| §4.1, §5.2 | Task 8 — dalga 2 birleştirmesi, ilk tam yükleme, kilit commit'i (controller) | 2 sonu | — |
| §8, D12 | Task 9 — piyasa verimliliği raporu (T4) | 3 | K1 |
| §11, D13 | Task 10 — bütünleşik harness ve bilinen sonuçlar (T2b) | 3 | K1 |
| §10, D14 | Task 11 — kırmızı takım sızıntı denetimi (T6) | 4 | K1 |
| §13, §8.4 | Task 12 — Faz 2 kapısı, lig önerisi, HANDOFF (controller) | 4 | — |

## Dosya yapısı

| Dosya | Sorumluluk | Görev |
|---|---|---|
| `src/football_edge/history/__init__.py` · `market/__init__.py` · `backtest/__init__.py` | boş paket işaretleri | 0 |
| `src/football_edge/history/types.py` | `HistMatch`, `OddsKey`, market/evre sabitleri | 0 |
| `src/football_edge/history/catalog.py` | `config/history_leagues.yaml` yükleyici, yol üretimi | 1 |
| `src/football_edge/history/football_data.py` | CSV bayt → `ParseResult`; kalite denetimi | 1 |
| `config/history_leagues.yaml` | 22 ana + 16 ek lig, `current_season` | 1 |
| `src/football_edge/market/devig.py` | çarpımsal, power, Shin | 2 |
| `src/football_edge/market/metrics.py` | log loss, Brier, RPS, kalibrasyon, CLV, bootstrap | 2 |
| `src/football_edge/history/holdout.py` | dönemler, `HoldoutKey`, `open_holdout`, `select_periods` | 3 |
| `src/football_edge/history/lock.py` | kanonik satır, özet, kilit dosyası, doğrulama | 3 |
| `db/migrations/0007_holdout.sql` | `holdout_access_log` (append-only) | 3 |
| `src/football_edge/backtest/timeline.py` | karar anı, sonuç bilinme anı | 4 |
| `src/football_edge/backtest/events.py` | olay tipi ve sıralı olay akışı | 4 |
| `src/football_edge/backtest/harness.py` | bağlam/sonuç tipleri, `Strategy`, `replay` | 4 |
| `src/football_edge/backtest/strategies.py` | `MarketPre`, `EloPointInTime`, `Placebo` | 4 |
| `verify.sh` | `sızıntı` adımı | 5 |
| `src/football_edge/history/store.py` | `hist_files`/`hist_fetches` okuma-yazma | 6 |
| `src/football_edge/history/sync.py` | çekme → doğrulama → önbellek; `load_matches` | 6 |
| `src/football_edge/history/__main__.py` | CLI: `sync`, `lock` | 6 |
| `db/migrations/0006_history.sql` | `hist_files`, `hist_fetches` | 6 |
| `.github/workflows/history.yml` | haftalık tek-işli workflow (`sync` adımı; Task 10 alarmdan önce `selftest` ADIMI ekler — `_steps()` tek iş varsayar) | 6 |
| `config/sources.yaml` · `config/robots/football-data.txt` | kaynak kaydı, robots anlık görüntüsü | 6 |
| `src/football_edge/market/bridge.py` · `config/history_aliases.yaml` | canlı mühür ↔ `AvgC` | 7 |
| `db/migrations/0008_history_dispatch.sql` · `scripts/ops_alert.py` | pg_cron işi, bekçi tetiği | 8 |
| `config/history_lock.yaml` | dev + holdout satır özetleri | 8 |
| `src/football_edge/market/efficiency.py` · `market/__main__.py` | verimlilik ölçütleri, sıralama, rapor | 9 |
| `docs/reports/<tarih>-piyasa-verimliligi.md` | toplu sayılar | 9 |
| `src/football_edge/backtest/evaluate.py` · `selftest.py` · `__main__.py` | değerlendirme, K1–K4 | 10 |

Testler düz `tests/` altında (`tests/test_<modül>.py`), mevcut desenle.

## Arayüz sözleşmesi

Bütün görevler bu adlara ve tiplere karşı yazılır; ad değiştirmek bir plan kusurudur. "Üretir"
listesindeki her şey o görevin testleriyle sabitlenir.

### Task 0 (dalga 0) üretir — tam kod Task 0'da

```python
# football_edge/history/types.py
PRE_CLOSING: str = "pre"
CLOSING: str = "close"
H2H: str = "1x2"
TOTALS_25: str = "ou25"
MARKET_OUTCOMES: Mapping[str, tuple[str, ...]]   # {H2H: ("H", "D", "A"), TOTALS_25: ("over", "under")}
RESULTS: tuple[str, ...]                          # ("H", "D", "A")

@dataclass(frozen=True, order=True)
class OddsKey:
    book: str      # football-data öneki: "Avg", "Max", "B365", "PS", "BFE", "BbAv", "BbMx"
    market: str    # H2H | TOTALS_25
    outcome: str   # MARKET_OUTCOMES[market] içinden
    phase: str     # PRE_CLOSING | CLOSING

@dataclass(frozen=True)
class HistMatch:
    league: str               # football-data kodu: "E0", "BRA"
    season: str               # ana lig: "2526"; ek lig: satırın Season değeri ("2025" ya da "2024/2025")
    date: date                # kaynağın Date'i (İngiltere yerel tarihi) — dönem üyeliği bununla
    kickoff: datetime | None  # UTC, tz-aware; Time yoksa None
    home: str
    away: str
    home_goals: int
    away_goals: int
    result: str               # RESULTS içinden, gollerle tutarlı
    odds: Mapping[OddsKey, float]   # MappingProxyType; her fiyat > 1.0
    stats: Mapping[str, int]        # HS AS HST AST HF AF HC AC HY AY HR AR — varsa
    source_line: int                # dosyadaki 1 tabanlı veri satırı (başlık hariç)

    def prices(self, book: str, market: str, phase: str) -> tuple[float, ...] | None: ...
        # MARKET_OUTCOMES[market] sırasıyla; biri eksikse None
```

### Task 1 (T1a) üretir

```python
# football_edge/history/catalog.py
MAIN: str = "main"; EXTRA: str = "extra"
@dataclass(frozen=True)
class HistoryLeague:
    code: str; league_id: str; name: str; country: str; tier: int
    kind: str            # MAIN | EXTRA
    first_season: str    # MAIN: "0506"; EXTRA: ""
    odds_api_key: str    # The Odds API anahtarı (R95: /v4/sports ölçümü, ölçüm belgesi §2.5); yoksa ""
@dataclass(frozen=True)
class Catalog:
    current_season: str                  # "2627"
    leagues: tuple[HistoryLeague, ...]
def load_catalog(path: Path) -> Catalog
def season_codes(first: str, last: str) -> tuple[str, ...]        # ("0506", …, "2627")
def file_paths(league: HistoryLeague, *, current_season: str) -> tuple[str, ...]
    # MAIN: "/mmz4281/{season}/{code}.csv" her sezon; EXTRA: ("/new/{code}.csv",)
def declared_paths(catalog: Catalog) -> tuple[str, ...]            # sıralı, tekil
def season_of_path(path: str) -> str | None                        # "/mmz4281/2526/E0.csv" → "2526"; ek → None

# football_edge/history/football_data.py
REJECT_LIMIT: float = 0.01
@dataclass(frozen=True)
class Rejected:
    line: int; reason: str
@dataclass(frozen=True)
class ParseResult:
    matches: tuple[HistMatch, ...]
    rejected: tuple[Rejected, ...]       # düşürülen SATIRLAR
    dropped_prices: int                  # yok sayılan fiyat HÜCRELERİ (sayısal değil ya da ≤ 1.0)
    price_cells: int                     # okunan dolu fiyat hücresi sayısı
    encoding: str                        # "utf-8-sig" | "latin-1"
    columns: tuple[str, ...]
def parse_file(content: bytes, *, league: HistoryLeague, season: str | None) -> ParseResult
    # MAIN için season zorunlu ("2526"); EXTRA için None — satırın Season sütunu kullanılır
def check_quality(result: ParseResult, *, path: str, league: HistoryLeague, season: str | None) -> None
    # collector.ContractViolation: zorunlu sütun yok · dönem beklentisi (MAIN ve season ≥ "1920" iken
    # AvgCH/AvgCD/AvgCA yok) · reddedilen satır payı > REJECT_LIMIT · düşen fiyat payı > REJECT_LIMIT
    # · hiç maç yok (yalnız başlık satırı = tam kayıp; R88)
```

### Task 2 (T3) üretir

```python
# football_edge/market/devig.py
MULTIPLICATIVE: str = "multiplicative"; POWER: str = "power"; SHIN: str = "shin"
METHODS: tuple[str, ...] = (MULTIPLICATIVE, POWER, SHIN)
TOLERANCE: float = 1e-12
DEFAULT_METHOD: str = SHIN      # Task 9'un ölçümü (K2) başka yöntemi seçerse controller Task 12'de günceller
class InvalidPrices(ValueError): ...
def overround(prices: Sequence[float]) -> float                    # Σ 1/o − 1
def devig(prices: Sequence[float], method: str) -> tuple[float, ...]
    # ≥ 2 fiyat, hepsi sonlu ve > 1.0; SHIN için Σ 1/o ≥ 1 (değilse InvalidPrices)
def match_probs(match: HistMatch, *, book: str, market: str, phase: str, method: str) -> tuple[float, ...] | None
    # match.prices(...) eksikse ya da InvalidPrices ise None — T4, T7, T10 bunu paylaşır

# football_edge/market/metrics.py
@dataclass(frozen=True)
class Interval:
    estimate: float; low: float; high: float
@dataclass(frozen=True)
class Calibration:
    slope: float; intercept: float; ece: float; n: int
def per_match_log_loss(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> tuple[float, ...]
def log_loss(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float
def brier(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float
def rps(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float     # sıralı sonuçlar
def calibration(probs: Sequence[Sequence[float]], outcomes: Sequence[int], *, bins: int = 10) -> Calibration
def clv(price: float, fair_probability: float) -> float                          # price · p − 1
def bootstrap_mean(values: Sequence[float], *, resamples: int = 2000, seed: int = 20260922,
                   level: float = 0.95) -> Interval
def outcome_index(match: HistMatch, market: str) -> int
    # H2H: RESULTS.index(match.result); TOTALS_25: toplam gol > 2.5 ise 0 ("over"), değilse 1
# outcomes: sonucun MARKET_OUTCOMES içindeki sırası (1X2'de H=0, D=1, A=2)
```

### Task 3 (T5) üretir

```python
# football_edge/history/holdout.py
DEV_END: date = date(2025, 7, 1)
HOLDOUT_END: date = date(2026, 7, 1)
DEV: str = "dev"; HOLDOUT: str = "holdout"; POST: str = "post"
class HoldoutLocked(RuntimeError): ...
@dataclass(frozen=True)
class HoldoutKey:
    opened_at: datetime; purpose: str; git_sha: str
    # yalnız open_holdout kurar; select_periods modül-içi bir işaretle doğrular
@dataclass(frozen=True)
class Window:
    start: date | None; end: date                 # [start, end) — maç tarihine (Date) göre
    # R89: end > DEV_END ya da start >= end → ValueError (pencere holdout'a asla uzanmaz)
MAIN_WINDOW: Window = Window(date(2019, 7, 1), DEV_END)    # ana ligler: Avg/AvgC ve saat birlikte var
EXTRA_WINDOW: Window = Window(None, DEV_END)               # ek ligler: yalnız kapanış
def in_window(match: HistMatch, window: Window) -> bool
def period_of(match_date: date) -> str
def open_holdout(conn: psycopg.Connection[Any], *, purpose: str, git_sha: str, now: datetime) -> HoldoutKey
def select_periods(matches: Sequence[HistMatch], *, periods: frozenset[str],
                   key: HoldoutKey | None = None) -> tuple[HistMatch, ...]
    # HOLDOUT istenip geçerli anahtar yoksa HoldoutLocked

# football_edge/history/lock.py
CANONICAL_VERSION: int = 1
class LockViolation(RuntimeError): ...      # LockViolation(*differences); .differences: tuple[str, ...]
    # canonical_line: tz'siz kickoff ya da sekme/satır sonu taşıyan değer → ValueError (R86 kanonik biçim)
@dataclass(frozen=True)
class Digest:
    rows: int; sha256: str; avgc_complete: int   # AvgC 1X2'si tam satır sayısı (kapsam bilgisi)
@dataclass(frozen=True)
class HistoryLock:
    canonical_version: int; locked_at: date; dev_end: date; holdout_end: date
    leagues: Mapping[str, Mapping[str, Digest]]   # kod → {DEV: Digest, HOLDOUT: Digest}
def canonical_line(match: HistMatch) -> str
def digest(matches: Sequence[HistMatch]) -> Digest
def build_lock(matches_by_league: Mapping[str, Sequence[HistMatch]], *, locked_at: date) -> HistoryLock
def dump_lock(lock: HistoryLock) -> str
def load_lock(path: Path) -> HistoryLock                           # R99: bozuk/eksik yapı → LockViolation (CLI'lar exit 9)
def verify_lock(lock: HistoryLock, matches_by_league: Mapping[str, Sequence[HistMatch]]) -> None
    # LockViolation: her farklı (lig, dönem) için beklenen/gerçek satır ve özet; kilitte olmayan lig
```

### Task 4 (T2a) üretir

```python
# football_edge/backtest/timeline.py
LONDON: ZoneInfo                    # ZoneInfo("Europe/London")
RESULT_LAG: timedelta               # 3 saat
DECISION_HOUR: int                  # 12
def decision_at(match_date: date, kickoff: datetime | None) -> datetime | None   # UTC; karar ≥ başlama → None
def result_known_at(match_date: date, kickoff: datetime | None) -> datetime       # UTC

# football_edge/backtest/events.py
DECISION: int = 0; RESULT: int = 1           # eşzamanlıda karar önce
@dataclass(frozen=True, order=True)
class Event:
    at: datetime; kind: int; match_index: int
def build_events(matches: Sequence[HistMatch]) -> tuple[Event, ...]

# football_edge/backtest/harness.py
class LeakageError(RuntimeError): ...
@dataclass(frozen=True)
class ResultRecord:
    league: str; date: date; home: str; away: str; home_goals: int; away_goals: int; known_at: datetime
@dataclass(frozen=True)
class DecisionContext:                       # kapanış ve sonuç alanı YOK; durum görüntüsü de yok — durum stratejide, observe() ile (R98)
    match_index: int; league: str; season: str; date: date; home: str; away: str
    decision_at: datetime
    pre_prices: Mapping[OddsKey, float]      # yalnız PRE_CLOSING anahtarları
@dataclass(frozen=True)
class Outcome:
    match_index: int; result: str; home_goals: int; away_goals: int
    closing: Mapping[OddsKey, float]         # yalnız CLOSING anahtarları
@dataclass(frozen=True)
class Bet:
    outcome: str; price: float; book: str
@dataclass(frozen=True)
class Prediction:
    match_index: int; strategy: str; probs: tuple[float, float, float]; bet: Bet | None = None
class Strategy(Protocol):
    @property
    def name(self) -> str: ...
    def observe(self, result: ResultRecord) -> Strategy: ...        # yeni strateji değeri döner
    def predict(self, context: DecisionContext) -> Prediction | None: ...
@dataclass(frozen=True)
class ReplayResult:
    strategy: str
    predictions: tuple[Prediction, ...]
    outcomes: Mapping[int, Outcome]          # yalnız tahmin edilen maçlar; döngü BİTTİKTEN sonra kurulur
    no_decision: int; no_prediction: int
def replay(matches: Sequence[HistMatch], strategy: Strategy) -> ReplayResult

# football_edge/backtest/strategies.py
Devig = Callable[[Sequence[float]], tuple[float, ...]]
@dataclass(frozen=True)
class MarketPre:            # name "market_pre"; book="Avg"; devig enjekte edilir
    devig: Devig; book: str = "Avg"
@dataclass(frozen=True)
class EloPointInTime:       # name "elo"; ratings MappingProxyType; draw_rate=0.26
    config: EloConfig = EloConfig(); draw_rate: float = 0.26
    groups: Mapping[str, str] = …   # R94: lig kodu → reyting grubu (ülke); eşlenmeyen lig kendi kodu
    ratings: Mapping[tuple[str, str], float] = …   # (grup, takım) — yalın ad ülkeler arası kimlik değildir
@dataclass(frozen=True)
class Placebo:              # name "placebo"; tohumlu rastgele sonuç, `book` kapanış öncesi fiyatından bahis
    devig: Devig; seed: int = 20260922; book: str = "Avg"
```

### Task 6 (T1b) üretir

```python
# football_edge/history/store.py
@dataclass(frozen=True)
class CachedFile:
    path: str; sha256: str; fetched_at: datetime; content: bytes      # content açılmış (gzip değil)
def save_file(conn: psycopg.Connection[Any], *, path: str, content: bytes, fetched_at: datetime,
              last_modified: str | None, row_count: int) -> bool      # içerik değiştiyse True
def log_fetch(conn: psycopg.Connection[Any], *, path: str, fetched_at: datetime, sha256: str | None,
              http_status: int | None, rows_parsed: int, rows_rejected: int) -> None
def load_files(conn: psycopg.Connection[Any], paths: Sequence[str]) -> Mapping[str, CachedFile]

# football_edge/history/sync.py
SOURCE_ID: str = "football-data"
@dataclass(frozen=True)
class SyncReport:
    requested: int; changed: int; unchanged: int
    failed: tuple[tuple[str, str], ...]          # (yol, neden)
    rejected_rows: int
def mutable_paths(catalog: Catalog) -> tuple[str, ...]     # güncel sezon ana dosyaları + ek lig dosyaları
def sync(conn: psycopg.Connection[Any], client: httpx.Client, *, source: Source, parser: Protego,
         catalog: Catalog, paths: Sequence[str], now: Callable[[], datetime]) -> SyncReport
def load_matches(conn: psycopg.Connection[Any], catalog: Catalog, *, lock: HistoryLock | None = None,
                 key: HoldoutKey | None = None) -> Mapping[str, tuple[HistMatch, ...]]
    # R96: lig kodu → (date, kickoff, home) sırasıyla DEV + POST; HOLDOUT yalnız geçerli anahtarla.
    # lock verilirse ÖNCE bütün satırlar üzerinde verify_lock (LockViolation). Holdout history/'den anahtarsız çıkmaz.
# _load_all(conn, catalog): modüle özel, bütün dönemler — yalnız sync.py ve history/__main__.py (kilit komutu); AST kuralı korur

# CLI: python -m football_edge.history sync [--all] · lock --write PATH · lock --verify PATH
```

### Task 7 (T7) üretir

```python
# football_edge/market/bridge.py
@dataclass(frozen=True)
class LiveClosing:
    match_id: str; league_id: str; kickoff: datetime; home: str; away: str
    prices: tuple[float, float, float]     # kitapların kapanış fiyatlarının aritmetik ortalaması (H, D, A)
    books: int
@dataclass(frozen=True)
class Pairing:
    pairs: tuple[tuple[LiveClosing, HistMatch], ...]
    unmatched_live: tuple[LiveClosing, ...]
@dataclass(frozen=True)
class BridgeReport:
    n: int; method: str
    mean_diff: tuple[Interval, Interval, Interval]    # p_bizim − p_AvgC (H, D, A)
    rms: float; unmatched: int
def load_aliases(path: Path) -> Mapping[str, str]
def load_live_closings(conn: psycopg.Connection[Any], *, since: datetime) -> tuple[LiveClosing, ...]
def pair(live: Sequence[LiveClosing], hist: Sequence[HistMatch], *, aliases: Mapping[str, str],
         codes_by_league_id: Mapping[str, str]) -> Pairing
def compare(pairing: Pairing, *, method: str) -> BridgeReport
def render_bridge_report(report: BridgeReport, *, generated_at: datetime, since: date) -> str   # R91
# pair() yalnız POST dönemi satırlarına bakar (select_periods) — köprü holdout'a dokunmaz
# CLI (Task 9): python -m football_edge.market bridge --out PATH [--since …] — ilk gerçek rapor Task 12'de
```

### Task 9 (T4) ve Task 10 (T2b) üretir

```python
# football_edge/market/efficiency.py  (pencereler Task 3'ün holdout.py'sinden: Window, MAIN_WINDOW, EXTRA_WINDOW)
@dataclass(frozen=True)
class LeagueEfficiency:
    code: str; league_id: str; kind: str; n: int
    margin: Interval; log_loss: Interval; brier: float; rps: float
    calibration: Calibration; slope: Interval
    late_info: Interval | None; value_rate: Interval | None; sharp_gap: Interval | None
    ou25_margin: Interval | None; ou25_log_loss: Interval | None; ou25_calibration: Calibration | None   # R92
    exchange_gap: Interval | None     # R97: LL(AvgC) − LL(BFEC), ikisi ≥ %90 dolu lig-sezonlarda (D3)
@dataclass(frozen=True)
class Ranking:
    late_info: tuple[str, ...]; miscalibration: tuple[str, ...]; tiers: Mapping[str, str]
def method_scores(matches: Sequence[HistMatch]) -> Mapping[str, float]   # yöntem → havuzlanmış AvgC LL
def best_method(scores: Mapping[str, float]) -> str                      # en düşük LL; DEFAULT_METHOD'dan farklıysa rapor uyarır
def league_efficiency(league: HistoryLeague, matches: Sequence[HistMatch], *, method: str,
                      resamples: int = RESAMPLES) -> LeagueEfficiency
def rank(rows: Sequence[LeagueEfficiency]) -> Ranking
def candidates(rows: Sequence[LeagueEfficiency], ranking: Ranking, *, lock: HistoryLock,
               leagues: Sequence[HistoryLeague]) -> tuple[str, ...]      # tasarım §8.4
class NoClosingPrices(ValueError): ...   # R100: AvgC 1X2'si tam hiçbir maçı olmayan lig — rapor düşmez
def render_report(rows: Sequence[LeagueEfficiency], ranking: Ranking, *, scores: Mapping[str, float],
                  candidates: Sequence[str], generated_at: datetime,
                  unmeasured: Sequence[HistoryLeague] = ()) -> str   # ölçülemeyen lig N=0 ve "—" ile satırda kalır

# football_edge/backtest/evaluate.py
@dataclass(frozen=True)
class Evaluation:
    strategy: str; n: int; log_loss: Interval; brier: float; rps: float
    calibration: Calibration; clv: Interval | None; bets: int
def evaluate(result: ReplayResult, *, method: str, resamples: int = 2000) -> Evaluation
def clv_values(result: ReplayResult, *, method: str) -> tuple[float, ...]   # K4 bunu kullanır

# football_edge/backtest/selftest.py
@dataclass(frozen=True)
class Check:
    id: str; gate: bool; passed: bool; detail: str
def run_selftest(matches_by_league: Mapping[str, Sequence[HistMatch]], *, method: str,
                 main_codes: frozenset[str], resamples: int = 2000) -> tuple[Check, ...]
    # main_codes: katalogdaki MAIN liglerin kodları (K1'in 18/22 eşiği ve pencere seçimi için)
```

## Paralellik ve worktree protokolü

- Dalga başına en çok 4 implementer, her biri `.worktrees/wt-<görev>` altında kendi dalında
  (`feat/faz2-<görev>`), taban o dalganın başındaki `main`.
- Tek-yazar: aşağıdaki tablo dışında paralel görevler ortak dosyaya YAZMAZ. Ortak dosyalar
  (`pyproject.toml`, `uv.lock`, `verify.sh`, `config/sources.yaml`, `scripts/ops_alert.py`,
  `db/migrations/0008_*`) yalnız controller görevlerinde (0, 5, 8, 12) değişir.

| Dalga | Görevler | Yazdıkları | Kesişim |
|---|---|---|---|
| 1 | 1 · 2 · 3 · 4 | `history/catalog.py`, `history/football_data.py`, `config/history_leagues.yaml` · `market/devig.py`, `market/metrics.py` · `history/holdout.py`, `history/lock.py`, `0007` · `backtest/timeline.py`, `events.py`, `harness.py`, `strategies.py` + her birinin testleri | yok — hepsi `history/types.py`e (Task 0) karşı yazar |
| 2 | 6 · 7 | `history/store.py`, `sync.py`, `__main__.py`, `0006`, `history.yml`, `config/sources.yaml`, robots · `market/bridge.py`, `config/history_aliases.yaml` | yok (`sources.yaml` Task 6'nın tek yazarlı işi; dalga 2'de başka yazan yok) |
| 3 | 9 · 10 | `market/efficiency.py`, `market/__main__.py`, rapor · `backtest/evaluate.py`, `selftest.py`, `backtest/__main__.py`, `history.yml`e `selftest` adımı | yok |

---

## Görevler

### Task 0: Ortak tipler ve bağımlılık (dalga 0, controller)

**Kademe:** — (controller, tek commit) · **Dalga:** 0 · **Dal:** `main` üzerinde doğrudan

Dalga 1'in dört görevi paralel koşar ve üçü (`HistMatch`i üreten ayrıştırıcı, onu özetleyen kilit,
onu yeniden oynatan harness) aynı tiplere karşı yazar. Tipler, `numpy` bağımlılığı, `leakage` pytest
işareti ve paket dosyaları bu yüzden dalgadan ÖNCE tek bir commit'te gelir (tek-yazar kuralı).

**Files:**
- Create: `src/football_edge/history/__init__.py`, `src/football_edge/market/__init__.py`,
  `src/football_edge/backtest/__init__.py` (boş)
- Create: `src/football_edge/history/types.py`
- Modify: `pyproject.toml` (`dependencies`e `numpy`, `markers`a `leakage`), `uv.lock`
- Test: `tests/test_history_types.py`

**Interfaces:**
- Consumes: —
- Produces: `football_edge.history.types` — `PRE_CLOSING`, `CLOSING`, `H2H`, `TOTALS_25`,
  `MARKET_OUTCOMES`, `RESULTS`, `OddsKey`, `HistMatch` (sözleşmedeki birebir tanım).

- [ ] **Step 1: Başarısız testleri yaz**

```python
# tests/test_history_types.py
from __future__ import annotations

import dataclasses
import datetime as dt
from types import MappingProxyType

import pytest

from football_edge.history.types import (
    CLOSING,
    H2H,
    MARKET_OUTCOMES,
    PRE_CLOSING,
    RESULTS,
    TOTALS_25,
    HistMatch,
    OddsKey,
)


def _match(odds: dict[OddsKey, float]) -> HistMatch:
    return HistMatch(
        league="E0",
        season="2526",
        date=dt.date(2025, 8, 16),
        kickoff=dt.datetime(2025, 8, 16, 14, 0, tzinfo=dt.UTC),
        home="Ev",
        away="Deplasman",
        home_goals=2,
        away_goals=1,
        result="H",
        odds=MappingProxyType(odds),
        stats=MappingProxyType({}),
        source_line=1,
    )


def test_outcome_order_is_fixed_per_market() -> None:
    assert MARKET_OUTCOMES[H2H] == ("H", "D", "A")
    assert MARKET_OUTCOMES[TOTALS_25] == ("over", "under")
    assert RESULTS == ("H", "D", "A")


def test_prices_follow_market_outcome_order_not_insertion_order() -> None:
    odds = {
        OddsKey("Avg", H2H, "A", PRE_CLOSING): 4.0,
        OddsKey("Avg", H2H, "H", PRE_CLOSING): 2.0,
        OddsKey("Avg", H2H, "D", PRE_CLOSING): 3.5,
    }
    assert _match(odds).prices("Avg", H2H, PRE_CLOSING) == (2.0, 3.5, 4.0)


def test_prices_is_none_when_one_outcome_is_missing() -> None:
    odds = {
        OddsKey("Avg", H2H, "H", CLOSING): 2.0,
        OddsKey("Avg", H2H, "D", CLOSING): 3.5,
    }
    assert _match(odds).prices("Avg", H2H, CLOSING) is None


def test_prices_does_not_mix_phases() -> None:
    odds = {OddsKey("Avg", H2H, outcome, PRE_CLOSING): 3.0 for outcome in RESULTS}
    assert _match(odds).prices("Avg", H2H, CLOSING) is None


def test_totals_prices_are_over_then_under() -> None:
    odds = {
        OddsKey("PS", TOTALS_25, "under", CLOSING): 1.9,
        OddsKey("PS", TOTALS_25, "over", CLOSING): 2.0,
    }
    assert _match(odds).prices("PS", TOTALS_25, CLOSING) == (2.0, 1.9)


def test_odds_keys_sort_deterministically() -> None:
    keys = [OddsKey("PS", H2H, "H", CLOSING), OddsKey("Avg", H2H, "H", PRE_CLOSING)]
    assert sorted(keys)[0].book == "Avg"


def test_match_is_immutable() -> None:
    match = _match({})
    with pytest.raises(dataclasses.FrozenInstanceError):
        match.home = "başka"  # type: ignore[misc]


def test_market_outcomes_cannot_be_modified() -> None:
    with pytest.raises(TypeError):
        MARKET_OUTCOMES["yeni"] = ("x",)  # type: ignore[index]
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_history_types.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.history'`

- [ ] **Step 3: Paketleri ve tipleri yaz**

Üç boş dosya: `src/football_edge/history/__init__.py`, `src/football_edge/market/__init__.py`,
`src/football_edge/backtest/__init__.py`.

```python
# src/football_edge/history/types.py
"""Tarihsel tabanın ortak tipleri.

Ayrıştırıcı, kilit ve harness aynı dalgada paralel yazılır ve üçü de bu tiplere karşı yazar; bu
yüzden tipler dalga 0'da, tek bir controller commit'inde gelir. `datetime` modül adıyla alınır:
`date` bir alan adıdır ve sınıf gövdesinde tip adını gölgelerdi.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

PRE_CLOSING = "pre"
CLOSING = "close"
H2H = "1x2"
TOTALS_25 = "ou25"
MARKET_OUTCOMES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {H2H: ("H", "D", "A"), TOTALS_25: ("over", "under")}
)
RESULTS: tuple[str, ...] = MARKET_OUTCOMES[H2H]


@dataclass(frozen=True, order=True)
class OddsKey:
    book: str
    market: str
    outcome: str
    phase: str


@dataclass(frozen=True)
class HistMatch:
    """Tek tarihsel maç. Eşlemeler değiştirilemez ama hash'lenemez (küme anahtarı olamaz)."""

    league: str
    season: str
    date: dt.date
    kickoff: dt.datetime | None
    home: str
    away: str
    home_goals: int
    away_goals: int
    result: str
    odds: Mapping[OddsKey, float]
    stats: Mapping[str, int]
    source_line: int

    def prices(self, book: str, market: str, phase: str) -> tuple[float, ...] | None:
        """Marketin bütün sonuçlarının fiyatı MARKET_OUTCOMES sırasıyla; biri eksikse None.

        Vig temizleme sonuç kümesinin tamamını ister: eksik bir sonucu atlamak kalan olasılıkları
        yanlış normalize eder.
        """
        found: list[float] = []
        for outcome in MARKET_OUTCOMES[market]:
            price = self.odds.get(OddsKey(book, market, outcome, phase))
            if price is None:
                return None
            found.append(price)
        return tuple(found)
```

- [ ] **Step 4: Bağımlılığı ve işareti ekle**

`pyproject.toml`:
- `[project] dependencies` listesine `"numpy>=2.1",` (alfabetik sıra korunmaz; mevcut sırayı bozma,
  sona ekle).
- `[tool.pytest.ini_options] markers` listesine
  `"leakage: zaman semantiği, dönem ayrımı, kilit ve bağlam/sonuç ayrımı — kapının sızıntı adımı sayar",`

Run: `uv lock && uv sync`
Expected: `uv.lock`ta `numpy` paketi; `uv sync` hatasız.

- [ ] **Step 5: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_history_types.py -q`
Expected: PASS (8 passed)

- [ ] **Step 6: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | `prices`: eksik fiyatta `return None` yerine `continue` | `test_prices_is_none_when_one_outcome_is_missing` |
| 2 | `prices`: `MARKET_OUTCOMES[market]` yerine sözlüğün ekleme sırası | `test_prices_follow_market_outcome_order_not_insertion_order` |
| 3 | `prices`: anahtarda `phase` yerine sabit `PRE_CLOSING` | `test_prices_does_not_mix_phases` |
| 4 | `HistMatch`: `frozen=True` kaldırılır | `test_match_is_immutable` |
| 5 | `MARKET_OUTCOMES`: `MappingProxyType` yerine düz `dict` | `test_market_outcomes_cannot_be_modified` |
| 6 | `TOTALS_25` sonuçları `("under", "over")` | `test_totals_prices_are_over_then_under` |

- [ ] **Step 7: Commit**

```bash
git add src/football_edge/history/__init__.py src/football_edge/market/__init__.py \
  src/football_edge/backtest/__init__.py src/football_edge/history/types.py \
  tests/test_history_types.py pyproject.toml uv.lock
git commit -m "feat: Faz 2 dalga 0 — tarihsel taban ortak tipleri, numpy ve leakage işareti

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 8: Kapının tamamı, sonra push**

Run: `TMPDIR=$(mktemp -d) ./verify.sh` — log dosyasından oku. Expected: 9 PASS + `SKIP: zincir`.
Sonra `git fetch origin && git merge --no-ff origin/main` (bot çıpaları; rebase/force YOK), taze klon
kapısı, `git push origin main`. Dalga 1'in worktree'leri bu commit'ten açılır.

---

### Task 1: Lig kataloğu ve football-data ayrıştırıcısı (T1a)

**Kademe:** K2 · **Dalga:** 1 · **Worktree/dal:** `.worktrees/wt-parser` · `feat/faz2-parser`

**Files:**
- Create: `src/football_edge/history/catalog.py` — `config/history_leagues.yaml` yükleyici, yol üretimi
- Create: `src/football_edge/history/football_data.py` — CSV bayt → `ParseResult`; `check_quality`
- Create: `config/history_leagues.yaml` — 22 ana + 16 ek lig, `current_season: "2627"`
- Create: `tests/history_csv.py` — ölçülen başlıklar + sentetik satır kurucuları (Task 6 da kullanır)
- Test: `tests/test_history_catalog.py`, `tests/test_football_data.py`

Dokunulmaz: `src/football_edge/history/__init__.py` ve `history/types.py` (Task 0), `pyproject.toml`
(`leakage` işaretini Task 0 kaydeder), `config/leagues.yaml` (D19: canlı lig listesi değişmez).

**Interfaces:**
- Consumes (Task 0, `football_edge.history.types`): `PRE_CLOSING`, `CLOSING`, `H2H`, `TOTALS_25`,
  `MARKET_OUTCOMES: Mapping[str, tuple[str, ...]]`, `RESULTS: tuple[str, ...]`,
  `OddsKey(book, market, outcome, phase)`, `HistMatch(league, season, date, kickoff, home, away,
  home_goals, away_goals, result, odds, stats, source_line)` ve
  `HistMatch.prices(book: str, market: str, phase: str) -> tuple[float, ...] | None`.
  Mevcut kod: `football_edge.collector.ContractViolation`; `football_edge.leagues.load_leagues`
  (yalnız test, canlı anahtar bağı için).
- Produces (sözleşme, birebir):
```python
# football_edge/history/catalog.py
MAIN: str = "main"; EXTRA: str = "extra"
@dataclass(frozen=True)
class HistoryLeague:
    code: str; league_id: str; name: str; country: str; tier: int
    kind: str            # MAIN | EXTRA
    first_season: str    # MAIN: "0506"; EXTRA: ""
    odds_api_key: str    # The Odds API anahtarı (R95: /v4/sports ölçümü, ölçüm belgesi §2.5); yoksa ""
@dataclass(frozen=True)
class Catalog:
    current_season: str                  # "2627"
    leagues: tuple[HistoryLeague, ...]
def load_catalog(path: Path) -> Catalog
def season_codes(first: str, last: str) -> tuple[str, ...]        # ("0506", …, "2627")
def file_paths(league: HistoryLeague, *, current_season: str) -> tuple[str, ...]
    # MAIN: "/mmz4281/{season}/{code}.csv" her sezon; EXTRA: ("/new/{code}.csv",)
def declared_paths(catalog: Catalog) -> tuple[str, ...]            # sıralı, tekil
def season_of_path(path: str) -> str | None                        # "/mmz4281/2526/E0.csv" → "2526"; ek → None

# football_edge/history/football_data.py
REJECT_LIMIT: float = 0.01
@dataclass(frozen=True)
class Rejected:
    line: int; reason: str
@dataclass(frozen=True)
class ParseResult:
    matches: tuple[HistMatch, ...]
    rejected: tuple[Rejected, ...]       # düşürülen SATIRLAR
    dropped_prices: int                  # yok sayılan fiyat HÜCRELERİ (sayısal değil ya da ≤ 1.0)
    price_cells: int                     # okunan dolu fiyat hücresi sayısı
    encoding: str                        # "utf-8-sig" | "latin-1"
    columns: tuple[str, ...]
def parse_file(content: bytes, *, league: HistoryLeague, season: str | None) -> ParseResult
    # MAIN için season zorunlu ("2526"); EXTRA için None — satırın Season sütunu kullanılır
def check_quality(result: ParseResult, *, path: str, league: HistoryLeague, season: str | None) -> None
    # collector.ContractViolation: zorunlu sütun yok · dönem beklentisi (MAIN ve season ≥ "1920" iken
    # AvgCH/AvgCD/AvgCA yok) · reddedilen satır payı > REJECT_LIMIT · düşen fiyat payı > REJECT_LIMIT
    # · hiç maç yok (yalnız başlık satırı = tam kayıp; R88)
```
- Ek (sözleşme dışı, public): `catalog.KINDS`, `catalog.REQUIRED_FIELDS`;
  `football_data.BOOKS`, `STAT_COLUMNS`, `ODDS_COLUMNS: Mapping[str, OddsKey]` (70 sütun adı),
  `CLOSING_ERA = "1920"`, `CLOSING_REFERENCE`, `REASON_*` (ret nedeni metinleri);
  `tests/history_csv.py`: `MAIN_2526`, `MAIN_2627`, `MAIN_OLD`, `EXTRA_NEW`, `EXTRA_RUS`, `E0`,
  `BRA`, `main_row`, `extra_row`, `unique_prices`, `csv_bytes`.

**Bu görevin kararları (hepsini testler sabitler):**
- Oran sütun adı (kitap, market, sonuç, evre) dörtlüsünden ÜRETİLİR: 1X2 `{kitap}[C]{H|D|A}`,
  Ü/A 2.5 `{önek}[C]{>2.5|<2.5}`; Pinnacle'ın Ü/A öneki `P`tir (`PS` değil). 7 kitap × 5 sonuç ×
  2 evre = 70 ad; başlıkta olmayan yok sayılır. Asya handikabı, diğer bahisçiler (BW, CL, LB, …),
  `HxG`/`AxG` okunmaz.
- Satır ret nedenleri (`REASON_*`, sayılır, satır düşer): tarih; **saat** (dolu ama `HH:MM` değil);
  takım adı boş; gol (`\d+` değil — negatif ve `1.0` dahil); sonuç (`H/D/A` dışı ya da gollerle
  tutarsız); **sezon** (ek dosyada `Season` boş); yinelenen (tarih, ev, deplasman) — ilki kalır.
  Kalın ikisi controller listesine EKLENDİ: bozuk saat sessizce `None` olsaydı başlama ve sonuç
  anı kural dışı kayardı; boş sezon `HistMatch.season`ı boş bırakırdı. İkisi de `REJECT_LIMIT`
  payına girer, yani gürültülüdür.
- Fiyat hücresi: boş hücre yok demektir (sayılmaz); dolu hücre `price_cells`e sayılır; sayı değil,
  sonlu değil ya da `≤ 1.0` ise `dropped_prices`e sayılır ve atlanır — satır yaşar. Sayım,
  reddedilenler dahil bütün dolu satırlar üzerindendir. Oransız satır geçerli maçtır (`odds == {}`).
- `source_line`: başlığın altındaki 1 tabanlı CSV kaydı. Bütünüyle boş kayıt (`,,,,` ya da boş
  satır) sessizce atlanır ama numarayı tüketir — numara dosyadaki konumla eşleşir.
- `Time` Europe/London → UTC (`zoneinfo`). **Yaz saati kenarı:** iki yorumdan GEÇ olan an seçilir
  — ilkbahar boşluğunda (29/03/2026 01:30 yok) geçiş öncesi ofset → 01:30 UTC, sonbahar
  tekrarında (25/10/2026 01:30 iki kez) ikinci geçiş → 01:30 UTC. Sonuç bilinme anı (başlama + 3 sa)
  böylece olası gerçek andan önceye düşmez; karar anı (önceki cuma/salı 12:00) bu saatlerden
  günlerce uzaktır. `zoneinfo`nun varsayılanı (fold=0) sonbaharda ERKEN anı verirdi.
- Kod çözme `utf-8-sig`, olmazsa `latin-1` (`ParseResult.encoding`); BOM ilk sütun adından düşer.
- `check_quality` sırası: zorunlu sütun (ana: `Date HomeTeam AwayTeam FTHG FTAG FTR`; ek: `Season
  Date Home Away HG AG Res`) → dönem beklentisi (ana lig, `season >= "1920"`, `AvgCH/AvgCD/AvgCA`)
  → reddedilen satır payı `> REJECT_LIMIT` (payda: maç + reddedilen) → yok sayılan fiyat payı
  `> REJECT_LIMIT` (payda: `price_cells`) → **hiç maç yok** (yalnız başlık satırı = tam kayıp,
  R88). Tam %1 geçer. "Hiç maç yok" EN SONDA: bütün satırları reddedilen dosya ret nedenleriyle
  düşer, yalnız başlık satırı olan dosya (payda 0) buraya kalır. Mesaj `"{path}: "` ile başlar,
  yalnız sayı ve neden taşır, satır içeriği taşımaz (Ruling 4: ihlal mesajı loga düşer).
- Katalog: sezon kodu DİZE ve ardışık `YYyy` (tırnaksız YAML `0506` sekizlik 326 okunur); ana
  ligde `first_season ≤ current_season`; ek ligde `first_season == ""`; `tier` bool olmayan
  `int ≥ 1`; `code` ve `league_id` tekil; eksik ya da bilinmeyen alan reddedilir (`leagues.py`
  deseni); kökte yalnız `current_season` ve `leagues` (fazladan anahtar reddedilir). Sezon kodları
  yalnız 2000–2099.
- `odds_api_key` (R95): The Odds API'nin sunduğu HER ligin anahtarı (`/v4/sports?all=true`, 0
  kredi, ölçüm belgesi §2.5) — 33 lig; sunulmayan beş lig (EC, SC1, SC2, SC3, ROU) `""`. Testle
  zorlanan kurallar: canlı altı ligin anahtarı `config/leagues.yaml`dakiyle AYNI; dolu anahtarlar
  tekil ve `soccer_[a-z0-9_]+` biçiminde; beş anahtarsız lig boş; ölçümün tamamı `EXPECTED`
  tablosunda sabit. Lig önerisi (§8.4) böylece canlı olmayan bir ligi de aday gösterebilir.
- Yinelenen başlık adında İLK sütun okunur (sonraki kopya — ör. kaymış bir ek sütun — okunmaz).

- [ ] **Step 1: Katalog testlerini ve sentetik CSV yardımcısını yaz**

Create `tests/history_csv.py` (başlıklar ölçüm belgesi §2.2/§2.4'ten; satırlar uydurma):
```python
"""Sentetik football-data CSV'leri: GERÇEK başlıklar, programla kurulan SENTETİK satırlar.

Sütun adları içerik değildir; takım adları ("Ev 3"), tarihler ve fiyatlar uydurmadır. Depoya,
loga ya da artifact'e gerçek maç/oran satırı girmez (tasarım §4.3, Ruling 4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from football_edge.history.catalog import EXTRA, MAIN, HistoryLeague

# Ölçülen 2025/26 ana lig başlığı (132 sütun, /mmz4281/2526/E0.csv — ölçüm belgesi §2.2).
_MAIN_2526 = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Referee,HS,AS,HST,AST,HF,"
    "AF,HC,AC,HY,AY,HR,AR,B365H,B365D,B365A,BFDH,BFDD,BFDA,BMGMH,BMGMD,BMGMA,BVH,BVD,BVA,"
    "BWH,BWD,BWA,CLH,CLD,CLA,LBH,LBD,LBA,PSH,PSD,PSA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,BFEH,"
    "BFED,BFEA,B365>2.5,B365<2.5,P>2.5,P<2.5,Max>2.5,Max<2.5,Avg>2.5,Avg<2.5,BFE>2.5,"
    "BFE<2.5,AHh,B365AHH,B365AHA,PAHH,PAHA,MaxAHH,MaxAHA,AvgAHH,AvgAHA,BFEAHH,BFEAHA,"
    "B365CH,B365CD,B365CA,BFDCH,BFDCD,BFDCA,BMGMCH,BMGMCD,BMGMCA,BVCH,BVCD,BVCA,BWCH,BWCD,"
    "BWCA,CLCH,CLCD,CLCA,LBCH,LBCD,LBCA,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA,"
    "BFECH,BFECD,BFECA,B365C>2.5,B365C<2.5,PC>2.5,PC<2.5,MaxC>2.5,MaxC<2.5,AvgC>2.5,"
    "AvgC<2.5,BFEC>2.5,BFEC<2.5,AHCh,B365CAHH,B365CAHA,PCAHH,PCAHA,MaxCAHH,MaxCAHA,AvgCAHH,"
    "AvgCAHA,BFECAHH,BFECAHA"
)
MAIN_2526: tuple[str, ...] = tuple(_MAIN_2526.split(","))

_PINNACLE = frozenset(
    {"PSH", "PSD", "PSA", "PSCH", "PSCD", "PSCA", "P>2.5", "P<2.5", "PC>2.5", "PC<2.5"}
    | {"PAHH", "PAHA", "PCAHH", "PCAHA"}
)


def _season_2627() -> tuple[str, ...]:
    """2026/27 biçimi: `HxG`, `AxG` Referee'den sonra; Pinnacle sütunları yok (ölçüm §2.4).

    Ölçülen dosya 114 sütun; burada 120 — düşen öteki altı sütun ölçüm belgesinde adlandırılmıyor
    ve hiçbiri ayrıştırıcının okuduğu sütunlardan değil.
    """
    kept = tuple(name for name in MAIN_2526 if name not in _PINNACLE)
    at = kept.index("Referee") + 1
    return (*kept[:at], "HxG", "AxG", *kept[at:])


MAIN_2627: tuple[str, ...] = _season_2627()

# 2012/13–2018/19 biçimi: Time yok; kapanış öncesi Betbrain ortalaması/en iyisi (BbAv/BbMx),
# Pinnacle kapanışı (PSC) 2012/13'ten; AvgC/MaxC henüz yok.
_MAIN_OLD = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,Referee,HS,AS,HST,AST,HF,AF,HC,"
    "AC,HY,AY,HR,AR,B365H,B365D,B365A,PSH,PSD,PSA,BbMxH,BbAvH,BbMxD,BbAvD,BbMxA,BbAvA,"
    "BbMx>2.5,BbAv>2.5,BbMx<2.5,BbAv<2.5,BbAH,BbAHh,PSCH,PSCD,PSCA"
)
MAIN_OLD: tuple[str, ...] = tuple(_MAIN_OLD.split(","))

# Ek lig dosyası (/new/<kod>.csv, 25 sütun) ve RUS'un 19 sütunlu biçimi (BFEC*, B365C* yok).
_EXTRA = (
    "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,"
    "AvgCH,AvgCD,AvgCA,BFECH,BFECD,BFECA,B365CH,B365CD,B365CA"
)
EXTRA_NEW: tuple[str, ...] = tuple(_EXTRA.split(","))
EXTRA_RUS: tuple[str, ...] = tuple(
    name for name in EXTRA_NEW if not name.startswith(("BFEC", "B365C"))
)

E0 = HistoryLeague(
    code="E0",
    league_id="eng.1",
    name="Premier League",
    country="England",
    tier=1,
    kind=MAIN,
    first_season="2526",
    odds_api_key="soccer_epl",
)
BRA = HistoryLeague(
    code="BRA",
    league_id="bra.1",
    name="Serie A",
    country="Brazil",
    tier=1,
    kind=EXTRA,
    first_season="",
    odds_api_key="",
)


def main_row(n: int = 0, cells: Mapping[str, str] | None = None) -> dict[str, str]:
    """Geçerli sentetik ana lig satırı (2-1 ev sahibi galibiyeti); `cells` alanları ezer."""
    base = {
        "Div": "E0",
        "Date": "16/08/2025",
        "Time": "15:00",
        "HomeTeam": f"Ev {n}",
        "AwayTeam": f"Deplasman {n}",
        "FTHG": "2",
        "FTAG": "1",
        "FTR": "H",
        "AvgH": "2.10",
        "AvgD": "3.40",
        "AvgA": "3.50",
        "AvgCH": "2.05",
        "AvgCD": "3.45",
        "AvgCA": "3.60",
    }
    return {**base, **(cells or {})}


def extra_row(n: int = 0, cells: Mapping[str, str] | None = None) -> dict[str, str]:
    """Geçerli sentetik ek lig satırı (1-1 beraberlik, yalnız kapanış); `cells` alanları ezer."""
    base = {
        "Country": "Ulke",
        "League": "Lig",
        "Season": "2025",
        "Date": "16/08/2025",
        "Time": "23:30",
        "Home": f"Ev {n}",
        "Away": f"Deplasman {n}",
        "HG": "1",
        "AG": "1",
        "Res": "D",
        "PSCH": "2.55",
        "PSCD": "3.30",
        "PSCA": "2.95",
        "AvgCH": "2.50",
        "AvgCD": "3.20",
        "AvgCA": "2.90",
    }
    return {**base, **(cells or {})}


def unique_prices(header: Sequence[str], after: str) -> dict[str, str]:
    """`after`dan sonraki HER sütuna ayrı bir fiyat: hangi sütunun hangi anahtara gittiği
    değerden okunur (2.00, 2.01, …)."""
    start = list(header).index(after) + 1
    return {name: f"{2 + index / 100:.2f}" for index, name in enumerate(header[start:])}


def csv_bytes(
    header: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    *,
    encoding: str = "utf-8",
    bom: bool = False,
) -> bytes:
    """football-data biçimi: virgül, CRLF; başlıkta olmayan anahtar yazılmaz."""
    lines = [",".join(header), *(",".join(row.get(name, "") for name in header) for row in rows)]
    body = ("\r\n".join(lines) + "\r\n").encode(encoding)
    return b"\xef\xbb\xbf" + body if bom else body
```

Create `tests/test_history_catalog.py`:
```python
from __future__ import annotations

import re
from pathlib import Path

import pytest

from football_edge.history.catalog import (
    EXTRA,
    MAIN,
    Catalog,
    HistoryLeague,
    declared_paths,
    file_paths,
    load_catalog,
    season_codes,
    season_of_path,
)
from football_edge.leagues import load_leagues
from tests.history_csv import BRA, E0

REPO = Path(__file__).resolve().parent.parent
CATALOG = REPO / "config/history_leagues.yaml"
SPORT_KEY = re.compile(r"soccer_[a-z0-9_]+")

# kod → (league_id, tier, kind, odds_api_key) — tasarım D19, ölçüm §2.4'teki ek lig dosya adları ve
# R95'in The Odds API ölçümü (`/v4/sports?all=true`, ölçüm §2.5; "" = o lig sunulmuyor).
EXPECTED = {
    "E0": ("eng.1", 1, MAIN, "soccer_epl"),
    "E1": ("eng.2", 2, MAIN, "soccer_efl_champ"),
    "E2": ("eng.3", 3, MAIN, "soccer_england_league1"),
    "E3": ("eng.4", 4, MAIN, "soccer_england_league2"),
    "EC": ("eng.5", 5, MAIN, ""),
    "SC0": ("sco.1", 1, MAIN, "soccer_spl"),
    "SC1": ("sco.2", 2, MAIN, ""),
    "SC2": ("sco.3", 3, MAIN, ""),
    "SC3": ("sco.4", 4, MAIN, ""),
    "D1": ("ger.1", 1, MAIN, "soccer_germany_bundesliga"),
    "D2": ("ger.2", 2, MAIN, "soccer_germany_bundesliga2"),
    "I1": ("ita.1", 1, MAIN, "soccer_italy_serie_a"),
    "I2": ("ita.2", 2, MAIN, "soccer_italy_serie_b"),
    "SP1": ("esp.1", 1, MAIN, "soccer_spain_la_liga"),
    "SP2": ("esp.2", 2, MAIN, "soccer_spain_segunda_division"),
    "F1": ("fra.1", 1, MAIN, "soccer_france_ligue_one"),
    "F2": ("fra.2", 2, MAIN, "soccer_france_ligue_two"),
    "N1": ("ned.1", 1, MAIN, "soccer_netherlands_eredivisie"),
    "B1": ("bel.1", 1, MAIN, "soccer_belgium_first_div"),
    "P1": ("por.1", 1, MAIN, "soccer_portugal_primeira_liga"),
    "T1": ("tur.1", 1, MAIN, "soccer_turkey_super_league"),
    "G1": ("gre.1", 1, MAIN, "soccer_greece_super_league"),
    "ARG": ("arg.1", 1, EXTRA, "soccer_argentina_primera_division"),
    "AUT": ("aut.1", 1, EXTRA, "soccer_austria_bundesliga"),
    "BRA": ("bra.1", 1, EXTRA, "soccer_brazil_campeonato"),
    "CHN": ("chn.1", 1, EXTRA, "soccer_china_superleague"),
    "DNK": ("den.1", 1, EXTRA, "soccer_denmark_superliga"),
    "FIN": ("fin.1", 1, EXTRA, "soccer_finland_veikkausliiga"),
    "IRL": ("irl.1", 1, EXTRA, "soccer_league_of_ireland"),
    "JPN": ("jpn.1", 1, EXTRA, "soccer_japan_j_league"),
    "MEX": ("mex.1", 1, EXTRA, "soccer_mexico_ligamx"),
    "NOR": ("nor.1", 1, EXTRA, "soccer_norway_eliteserien"),
    "POL": ("pol.1", 1, EXTRA, "soccer_poland_ekstraklasa"),
    "ROU": ("rou.1", 1, EXTRA, ""),
    "RUS": ("rus.1", 1, EXTRA, "soccer_russia_premier_league"),
    "SWE": ("swe.1", 1, EXTRA, "soccer_sweden_allsvenskan"),
    "SWZ": ("sui.1", 1, EXTRA, "soccer_switzerland_superleague"),
    "USA": ("usa.1", 1, EXTRA, "soccer_usa_mls"),
}

VALID = """
current_season: "2627"
leagues:
  - {code: E0, league_id: eng.1, name: "Premier League", country: England, tier: 1, kind: main,
     first_season: "2425", odds_api_key: "soccer_epl"}
  - {code: BRA, league_id: bra.1, name: "Serie A", country: Brazil, tier: 1, kind: extra,
     first_season: "", odds_api_key: ""}
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "history_leagues.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_real_catalog_holds_22_main_and_16_extra_leagues_as_designed() -> None:
    catalog = load_catalog(CATALOG)

    assert catalog.current_season == "2627"
    got = {
        league.code: (league.league_id, league.tier, league.kind, league.odds_api_key)
        for league in catalog.leagues
    }
    assert got == EXPECTED
    assert {league.first_season for league in catalog.leagues if league.kind == MAIN} == {"0506"}
    assert {league.first_season for league in catalog.leagues if league.kind == EXTRA} == {""}


def test_the_six_live_leagues_carry_the_key_of_the_live_config() -> None:
    """Canlı defterin anahtarıyla tarihsel katalogunki ayrışırsa köprü ve aday listesi yanlış ligi
    anar (R95)."""
    live = {league.id: league.odds_api_key for league in load_leagues(REPO / "config/leagues.yaml")}
    keys = {league.league_id: league.odds_api_key for league in load_catalog(CATALOG).leagues}

    assert {league_id: keys[league_id] for league_id in live} == live


def test_odds_api_keys_are_unique_and_shaped_like_sport_keys() -> None:
    """Aynı anahtar iki ligde olursa canlı CLV ölçümü iki ligi tek pazar sanar (§8.4)."""
    keys = [league.odds_api_key for league in load_catalog(CATALOG).leagues]
    filled = [key for key in keys if key]

    assert len(filled) == len(set(filled)), f"yinelenen anahtar: {sorted(filled)}"
    assert [key for key in filled if not SPORT_KEY.fullmatch(key)] == []


def test_leagues_the_odds_api_does_not_offer_carry_no_key() -> None:
    keys = {league.code: league.odds_api_key for league in load_catalog(CATALOG).leagues}

    assert {code: keys[code] for code in ("EC", "SC1", "SC2", "SC3", "ROU")} == dict.fromkeys(
        ("EC", "SC1", "SC2", "SC3", "ROU"), ""
    )


def test_the_real_catalog_declares_500_sorted_unique_paths() -> None:
    paths = declared_paths(load_catalog(CATALOG))

    assert len(paths) == 22 * 22 + 16, "22 ana lig × 22 sezon (0506…2627) + 16 ek lig"
    assert list(paths) == sorted(set(paths))
    assert "/mmz4281/0506/E0.csv" in paths and "/mmz4281/2627/G1.csv" in paths
    assert "/new/SWZ.csv" in paths and "/mmz4281/0405/E0.csv" not in paths


def test_a_valid_file_loads_into_frozen_records(tmp_path: Path) -> None:
    catalog = load_catalog(write(tmp_path, VALID))

    assert catalog == Catalog(
        current_season="2627",
        leagues=(
            HistoryLeague(
                "E0", "eng.1", "Premier League", "England", 1, MAIN, "2425", "soccer_epl"
            ),
            HistoryLeague("BRA", "bra.1", "Serie A", "Brazil", 1, EXTRA, "", ""),
        ),
    )


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [("0506", "0708", ("0506", "0607", "0708")), ("2627", "2627", ("2627",))],
)
def test_season_codes_expand_inclusively(first: str, last: str, expected: tuple[str, ...]) -> None:
    assert season_codes(first, last) == expected


@pytest.mark.parametrize(
    ("first", "last"),
    [("0507", "0708"), ("506", "0708"), ("2627", "2526"), ("0506", "26/27")],
)
def test_season_codes_reject_a_malformed_or_reversed_range(first: str, last: str) -> None:
    with pytest.raises(ValueError, match="sezon"):
        season_codes(first, last)


def test_file_paths_give_one_file_per_main_season_and_one_file_per_extra_league() -> None:
    assert file_paths(E0, current_season="2627") == (
        "/mmz4281/2526/E0.csv",
        "/mmz4281/2627/E0.csv",
    )
    assert file_paths(BRA, current_season="2627") == ("/new/BRA.csv",)


@pytest.mark.parametrize(
    ("path", "season"),
    [
        ("/mmz4281/2526/E0.csv", "2526"),
        ("/mmz4281/0506/SC3.csv", "0506"),
        ("/new/BRA.csv", None),
        ("/mmz4281/2526/E0.csv?x=1", None),
    ],
)
def test_season_of_path_reads_the_season_directory(path: str, season: str | None) -> None:
    assert season_of_path(path) == season


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('first_season: "2425"', "first_season: 2425", "dize olmayan"),
        ('first_season: "2425"', "first_season: 0506", "dize olmayan"),
        ('current_season: "2627"', "current_season: 2627", "sezon kodu"),
        ('first_season: "2425"', 'first_season: "2527"', "sezon kodu"),
        ('first_season: "2425"', 'first_season: "2728"', "güncel sezondan sonra"),
        ('first_season: ""', 'first_season: "2425"', "first_season boş olmalı"),
        ("kind: extra", "kind: cup", "kind"),
        ("tier: 1, kind: main", "tier: 0, kind: main", "tier"),
        ("tier: 1, kind: main", "tier: true, kind: main", "tier"),
        ("code: BRA", "code: E0", "yinelenen code"),
        ("league_id: bra.1", "league_id: eng.1", "yinelenen league_id"),
        ("country: Brazil, ", "", "eksik alan"),
        ("country: Brazil, ", "country: Brazil, footystats_path: /x, ", "bilinmeyen alan"),
        ('name: "Serie A"', "name: 7", "dize olmayan"),
    ],
)
def test_an_invalid_catalog_is_refused_by_name(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    assert old in VALID, f"test kurgusu bayat: {old!r}"

    with pytest.raises(ValueError, match=message):
        load_catalog(write(tmp_path, VALID.replace(old, new, 1)))


def test_a_catalog_without_current_season_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="current_season"):
        load_catalog(write(tmp_path, VALID.replace('current_season: "2627"\n', "")))


def test_a_catalog_with_an_unknown_top_level_key_is_refused(tmp_path: Path) -> None:
    """Yanlış yazılmış bir anahtar (ör. `curent_season`) sessizce yok sayılmasın."""
    with pytest.raises(ValueError, match="kökte tam olarak"):
        load_catalog(write(tmp_path, VALID.replace("leagues:\n", "notes: x\nleagues:\n", 1)))
```

- [ ] **Step 2: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_history_catalog.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.history.catalog'` (toplama
hatası; `tests/history_csv.py` kataloğu import ediyor)

- [ ] **Step 3: Kataloğu ve lig dosyasını yaz**

Create `src/football_edge/history/catalog.py`:
```python
"""Tarihsel lig kataloğu (`config/history_leagues.yaml`) ve football-data yol üretimi.

Katalog, kaynak kayıt defterindeki `football-data` `declared_paths`inin TEK kaynağıdır: yollar
buradan türetilir ve bir test ikisinin eşit olduğunu zorlar (tasarım D20). Canlı
`config/leagues.yaml` bu dosyadan bağımsızdır (D19).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MAIN: str = "main"
EXTRA: str = "extra"
KINDS = frozenset({MAIN, EXTRA})

REQUIRED_FIELDS = frozenset(
    {"code", "league_id", "name", "country", "tier", "kind", "first_season", "odds_api_key"}
)
_TEXT_FIELDS = ("code", "league_id", "name", "country", "kind", "first_season", "odds_api_key")
_SEASON = re.compile(r"\d{4}")
_MAIN_PATH = re.compile(r"/mmz4281/(\d{4})/[A-Za-z0-9]+\.csv")


@dataclass(frozen=True)
class HistoryLeague:
    code: str
    league_id: str
    name: str
    country: str
    tier: int
    kind: str
    first_season: str
    odds_api_key: str


@dataclass(frozen=True)
class Catalog:
    current_season: str
    leagues: tuple[HistoryLeague, ...]


def _check_season(code: object) -> str:
    """Sezon kodu `YYyy` (ör. "0506"): dört rakam, ikinci çift birincinin bir fazlası.

    Tırnaksız YAML değeri sayı okunur (`0506` sekizlik 326 olur); dize olmayan her şey reddedilir.
    """
    if not isinstance(code, str) or not _SEASON.fullmatch(code):
        raise ValueError(f"geçersiz sezon kodu: {code!r} (tırnaklı 'YYyy', ör. '0506')")
    if (int(code[:2]) + 1) % 100 != int(code[2:]):
        raise ValueError(f"geçersiz sezon kodu: {code!r} (yıllar ardışık değil)")
    return code


def season_codes(first: str, last: str) -> tuple[str, ...]:
    """`first`ten `last`e (ikisi dahil) sezon kodları; yalnız 2000–2099 sezonları."""
    start, end = int(_check_season(first)[:2]), int(_check_season(last)[:2])
    if start > end:
        raise ValueError(f"sezon aralığı ters: {first} > {last}")
    return tuple(f"{year:02d}{(year + 1) % 100:02d}" for year in range(start, end + 1))


def _check_fields(entry: dict[str, Any]) -> None:
    keys = frozenset(entry)
    missing = REQUIRED_FIELDS - keys
    if missing:
        raise ValueError(f"lig kaydında eksik alan: {sorted(missing)} ({entry.get('code', '?')})")
    unknown = keys - REQUIRED_FIELDS
    if unknown:
        raise ValueError(f"lig kaydında bilinmeyen alan: {sorted(unknown)} ({entry['code']})")
    wrong = [name for name in _TEXT_FIELDS if not isinstance(entry[name], str)]
    if wrong:
        raise ValueError(f"lig kaydında dize olmayan alan: {wrong} ({entry['code']})")
    tier = entry["tier"]
    if isinstance(tier, bool) or not isinstance(tier, int) or tier < 1:
        raise ValueError(f"lig kaydında geçersiz tier: {tier!r} ({entry['code']})")


def _league(entry: object, current_season: str) -> HistoryLeague:
    if not isinstance(entry, dict):
        raise ValueError(f"lig kaydı eşleme değil: {entry!r}")
    _check_fields(entry)
    if entry["kind"] not in KINDS:
        raise ValueError(f"geçersiz kind: {entry['kind']!r} ({entry['code']})")
    if entry["kind"] == EXTRA and entry["first_season"] != "":
        raise ValueError(f"ek lig tek dosyadır, first_season boş olmalı ({entry['code']})")
    if entry["kind"] == MAIN and _check_season(entry["first_season"]) > current_season:
        raise ValueError(f"first_season güncel sezondan sonra ({entry['code']})")
    return HistoryLeague(**entry)


def _check_unique(leagues: tuple[HistoryLeague, ...]) -> None:
    for field in ("code", "league_id"):
        values = [getattr(league, field) for league in leagues]
        repeated = sorted({value for value in values if values.count(value) > 1})
        if repeated:
            raise ValueError(f"yinelenen {field}: {repeated}")


def load_catalog(path: Path) -> Catalog:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"current_season", "leagues"}:
        raise ValueError(f"{path}: kökte tam olarak 'current_season' ve 'leagues' olmalı")
    current = _check_season(raw["current_season"])
    if not isinstance(raw["leagues"], list):
        raise ValueError(f"{path}: 'leagues' bir liste olmalı")
    leagues = tuple(_league(entry, current) for entry in raw["leagues"])
    _check_unique(leagues)
    return Catalog(current_season=current, leagues=leagues)


def file_paths(league: HistoryLeague, *, current_season: str) -> tuple[str, ...]:
    """Ana lig: sezon başına bir dosya; ek lig: bütün yılları taşıyan tek dosya."""
    if league.kind == EXTRA:
        return (f"/new/{league.code}.csv",)
    seasons = season_codes(league.first_season, current_season)
    return tuple(f"/mmz4281/{season}/{league.code}.csv" for season in seasons)


def declared_paths(catalog: Catalog) -> tuple[str, ...]:
    """Kataloğun istediği her yol, sıralı ve tekil — `sources.yaml`ın beyanı bununla EŞİT olmalı."""
    return tuple(
        sorted(
            {
                path
                for league in catalog.leagues
                for path in file_paths(league, current_season=catalog.current_season)
            }
        )
    )


def season_of_path(path: str) -> str | None:
    """`/mmz4281/2526/E0.csv` → "2526"; ek lig (`/new/BRA.csv`) ya da tanınmayan yol → None."""
    found = _MAIN_PATH.fullmatch(path)
    return None if found is None else found.group(1)
```

Create `config/history_leagues.yaml` (satır başına bir lig; `odds_api_key` R95'in The Odds API
ölçümü, canlı altı lig `config/leagues.yaml` ile aynı):
```yaml
# Faz 2 tarihsel lig kataloğu (tasarım §4.2, D19): football-data.co.uk kodu → bizim lig kimliğimiz.
# Canlı `config/leagues.yaml` DEĞİŞMEZ; Faz 2'nin çıktısı hangi ligin oraya terfi edeceğinin
# önerisidir (§8.4). Sezon kodları TIRNAKLI: YAML 1.1 tırnaksız `0506`yı sekizlik sayı (326) okur;
# yükleyici dize olmayan sezonu reddeder.
#
# main : sezon başına dosya /mmz4281/<sezon>/<kod>.csv, 2005/06'dan `current_season`a.
# extra: bütün yılları taşıyan tek dosya /new/<kod>.csv, yalnız kapanış oranları; first_season "".
# `current_season` her yeni sezonda elle ilerletilir; ardından config/sources.yaml'daki
# `football-data` declared_paths'i yeniden üretilir (tests/test_history_registry.py eşitliği zorlar).
# odds_api_key: The Odds API'nin o lig için sunduğu anahtar (R95 — `/v4/sports?all=true`, 0 kredi,
# ölçüm belgesi §2.5); sunulmayan ligde "". Canlı altı ligin anahtarı config/leagues.yaml ile aynı,
# boş olmayan anahtarlar tekil (tests/test_history_catalog.py zorlar).
current_season: "2627"
leagues:
  - {code: E0,  league_id: eng.1, name: "Premier League",   country: England,     tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_epl"}
  - {code: E1,  league_id: eng.2, name: "Championship",     country: England,     tier: 2, kind: main,  first_season: "0506", odds_api_key: "soccer_efl_champ"}
  - {code: E2,  league_id: eng.3, name: "League One",       country: England,     tier: 3, kind: main,  first_season: "0506", odds_api_key: "soccer_england_league1"}
  - {code: E3,  league_id: eng.4, name: "League Two",       country: England,     tier: 4, kind: main,  first_season: "0506", odds_api_key: "soccer_england_league2"}
  - {code: EC,  league_id: eng.5, name: "National League",  country: England,     tier: 5, kind: main,  first_season: "0506", odds_api_key: ""}
  - {code: SC0, league_id: sco.1, name: "Premiership",      country: Scotland,    tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_spl"}
  - {code: SC1, league_id: sco.2, name: "Championship",     country: Scotland,    tier: 2, kind: main,  first_season: "0506", odds_api_key: ""}
  - {code: SC2, league_id: sco.3, name: "League One",       country: Scotland,    tier: 3, kind: main,  first_season: "0506", odds_api_key: ""}
  - {code: SC3, league_id: sco.4, name: "League Two",       country: Scotland,    tier: 4, kind: main,  first_season: "0506", odds_api_key: ""}
  - {code: D1,  league_id: ger.1, name: "Bundesliga",       country: Germany,     tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_germany_bundesliga"}
  - {code: D2,  league_id: ger.2, name: "2. Bundesliga",    country: Germany,     tier: 2, kind: main,  first_season: "0506", odds_api_key: "soccer_germany_bundesliga2"}
  - {code: I1,  league_id: ita.1, name: "Serie A",          country: Italy,       tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_italy_serie_a"}
  - {code: I2,  league_id: ita.2, name: "Serie B",          country: Italy,       tier: 2, kind: main,  first_season: "0506", odds_api_key: "soccer_italy_serie_b"}
  - {code: SP1, league_id: esp.1, name: "La Liga",          country: Spain,       tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_spain_la_liga"}
  - {code: SP2, league_id: esp.2, name: "Segunda Division", country: Spain,       tier: 2, kind: main,  first_season: "0506", odds_api_key: "soccer_spain_segunda_division"}
  - {code: F1,  league_id: fra.1, name: "Ligue 1",          country: France,      tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_france_ligue_one"}
  - {code: F2,  league_id: fra.2, name: "Ligue 2",          country: France,      tier: 2, kind: main,  first_season: "0506", odds_api_key: "soccer_france_ligue_two"}
  - {code: N1,  league_id: ned.1, name: "Eredivisie",       country: Netherlands, tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_netherlands_eredivisie"}
  - {code: B1,  league_id: bel.1, name: "First Division A", country: Belgium,     tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_belgium_first_div"}
  - {code: P1,  league_id: por.1, name: "Primeira Liga",    country: Portugal,    tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_portugal_primeira_liga"}
  - {code: T1,  league_id: tur.1, name: "Super Lig",        country: Turkey,      tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_turkey_super_league"}
  - {code: G1,  league_id: gre.1, name: "Super League",     country: Greece,      tier: 1, kind: main,  first_season: "0506", odds_api_key: "soccer_greece_super_league"}
  - {code: ARG, league_id: arg.1, name: "Liga Profesional", country: Argentina,   tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_argentina_primera_division"}
  - {code: AUT, league_id: aut.1, name: "Bundesliga",       country: Austria,     tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_austria_bundesliga"}
  - {code: BRA, league_id: bra.1, name: "Serie A",          country: Brazil,      tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_brazil_campeonato"}
  - {code: CHN, league_id: chn.1, name: "Super League",     country: China,       tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_china_superleague"}
  - {code: DNK, league_id: den.1, name: "Superliga",        country: Denmark,     tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_denmark_superliga"}
  - {code: FIN, league_id: fin.1, name: "Veikkausliiga",    country: Finland,     tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_finland_veikkausliiga"}
  - {code: IRL, league_id: irl.1, name: "Premier Division", country: Ireland,     tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_league_of_ireland"}
  - {code: JPN, league_id: jpn.1, name: "J1 League",        country: Japan,       tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_japan_j_league"}
  - {code: MEX, league_id: mex.1, name: "Liga MX",          country: Mexico,      tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_mexico_ligamx"}
  - {code: NOR, league_id: nor.1, name: "Eliteserien",      country: Norway,      tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_norway_eliteserien"}
  - {code: POL, league_id: pol.1, name: "Ekstraklasa",      country: Poland,      tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_poland_ekstraklasa"}
  - {code: ROU, league_id: rou.1, name: "Liga I",           country: Romania,     tier: 1, kind: extra, first_season: "",  odds_api_key: ""}
  - {code: RUS, league_id: rus.1, name: "Premier League",   country: Russia,      tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_russia_premier_league"}
  - {code: SWE, league_id: swe.1, name: "Allsvenskan",      country: Sweden,      tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_sweden_allsvenskan"}
  - {code: SWZ, league_id: sui.1, name: "Super League",     country: Switzerland, tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_switzerland_superleague"}
  - {code: USA, league_id: usa.1, name: "MLS",              country: USA,         tier: 1, kind: extra, first_season: "",  odds_api_key: "soccer_usa_mls"}
```

- [ ] **Step 4: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_history_catalog.py -q`
Expected: PASS (33 passed)

- [ ] **Step 5: Ayrıştırıcı testlerini yaz**

Create `tests/test_football_data.py`:
```python
from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime

import pytest

from football_edge.collector import ContractViolation
from football_edge.history.football_data import (
    ODDS_COLUMNS,
    REASON_DATE,
    REASON_DUPLICATE,
    REASON_GOALS,
    REASON_RESULT,
    REASON_SEASON,
    REASON_TEAM,
    REASON_TIME,
    ParseResult,
    Rejected,
    check_quality,
    parse_file,
)
from football_edge.history.types import (
    CLOSING,
    H2H,
    PRE_CLOSING,
    TOTALS_25,
    HistMatch,
    OddsKey,
)
from tests.history_csv import (
    BRA,
    E0,
    EXTRA_NEW,
    EXTRA_RUS,
    MAIN_2526,
    MAIN_2627,
    MAIN_OLD,
    csv_bytes,
    extra_row,
    main_row,
    unique_prices,
)

# (kitap, evre) → sütunlar, sırayla H, D, A, Ü2.5, A2.5 — ölçülen 2025/26 başlığından elle yazıldı.
EXPECTED_2526 = {
    ("Avg", PRE_CLOSING): ("AvgH", "AvgD", "AvgA", "Avg>2.5", "Avg<2.5"),
    ("Avg", CLOSING): ("AvgCH", "AvgCD", "AvgCA", "AvgC>2.5", "AvgC<2.5"),
    ("Max", PRE_CLOSING): ("MaxH", "MaxD", "MaxA", "Max>2.5", "Max<2.5"),
    ("Max", CLOSING): ("MaxCH", "MaxCD", "MaxCA", "MaxC>2.5", "MaxC<2.5"),
    ("B365", PRE_CLOSING): ("B365H", "B365D", "B365A", "B365>2.5", "B365<2.5"),
    ("B365", CLOSING): ("B365CH", "B365CD", "B365CA", "B365C>2.5", "B365C<2.5"),
    ("PS", PRE_CLOSING): ("PSH", "PSD", "PSA", "P>2.5", "P<2.5"),
    ("PS", CLOSING): ("PSCH", "PSCD", "PSCA", "PC>2.5", "PC<2.5"),
    ("BFE", PRE_CLOSING): ("BFEH", "BFED", "BFEA", "BFE>2.5", "BFE<2.5"),
    ("BFE", CLOSING): ("BFECH", "BFECD", "BFECA", "BFEC>2.5", "BFEC<2.5"),
}
OUTCOMES = ((H2H, "H"), (H2H, "D"), (H2H, "A"), (TOTALS_25, "over"), (TOTALS_25, "under"))


def one_match(content: bytes, *, season: str | None = "2526") -> HistMatch:
    result = parse_file(content, league=E0 if season else BRA, season=season)
    assert result.rejected == (), result.rejected
    (match,) = result.matches
    return match


def test_odds_vocabulary_has_one_column_name_per_key() -> None:
    """7 kitap × (3 + 2 sonuç) × 2 evre; iki anahtar aynı adı üretirse biri sessizce düşerdi."""
    assert len(ODDS_COLUMNS) == 70
    assert len(set(ODDS_COLUMNS.values())) == 70


@pytest.mark.leakage
def test_the_measured_2025_26_header_maps_to_the_right_book_market_and_phase() -> None:
    """Kapanış bir kapanış öncesi anahtarına düşerse karar bağlamına kapanış sızar."""
    prices = unique_prices(MAIN_2526, after="AR")
    match = one_match(csv_bytes(MAIN_2526, [main_row(0, prices)]))

    for (book, phase), columns in EXPECTED_2526.items():
        for (market, outcome), column in zip(OUTCOMES, columns, strict=True):
            assert match.odds[OddsKey(book, market, outcome, phase)] == float(prices[column]), (
                book,
                phase,
                column,
            )
    assert len(match.odds) == 50, "Asya handikabı ya da başka bahisçi okunmuş"


@pytest.mark.leakage
def test_pre_2019_betbrain_columns_are_pre_closing_and_psc_is_closing() -> None:
    prices = unique_prices(MAIN_OLD, after="AR")
    match = one_match(csv_bytes(MAIN_OLD, [main_row(0, prices)]), season="1718")

    assert match.odds[OddsKey("BbAv", H2H, "H", PRE_CLOSING)] == float(prices["BbAvH"])
    assert match.odds[OddsKey("BbMx", H2H, "A", PRE_CLOSING)] == float(prices["BbMxA"])
    assert match.odds[OddsKey("BbAv", TOTALS_25, "over", PRE_CLOSING)] == float(prices["BbAv>2.5"])
    assert match.odds[OddsKey("BbMx", TOTALS_25, "under", PRE_CLOSING)] == float(prices["BbMx<2.5"])
    assert match.odds[OddsKey("PS", H2H, "D", CLOSING)] == float(prices["PSCD"])
    assert match.odds[OddsKey("PS", H2H, "D", PRE_CLOSING)] == float(prices["PSD"])
    assert len(match.odds) == 19, "B365 3 + PS 3 + BbMx/BbAv 6 + Ü/A 4 + PSC 3"


@pytest.mark.leakage
def test_extra_files_carry_only_closing_prices_and_the_row_season() -> None:
    rows = [extra_row(0), extra_row(1, {"Season": "2024/2025", "Date": "01/03/2025"})]
    result = parse_file(csv_bytes(EXTRA_NEW, rows), league=BRA, season=None)

    assert [match.season for match in result.matches] == ["2025", "2024/2025"]
    assert {key.phase for match in result.matches for key in match.odds} == {CLOSING}
    assert result.matches[0].odds[OddsKey("PS", H2H, "A", CLOSING)] == 2.95
    assert result.matches[0].league == "BRA"


def test_the_19_column_russian_layout_parses_without_betfair_or_bet365() -> None:
    match = one_match(csv_bytes(EXTRA_RUS, [extra_row(0)]), season=None)

    assert {key.book for key in match.odds} == {"PS", "Avg"}


def test_the_2026_27_header_has_no_pinnacle_and_xg_is_not_read() -> None:
    prices = unique_prices(MAIN_2627, after="AR")
    cells = {**prices, "HxG": "1", "AxG": "2"}
    match = one_match(csv_bytes(MAIN_2627, [main_row(0, cells)]), season="2627")

    assert {key.book for key in match.odds} == {"Avg", "Max", "B365", "BFE"}
    assert "HxG" not in match.stats and "AxG" not in match.stats


def test_match_stats_are_read_as_integers_when_present() -> None:
    cells = {"HS": "12", "AS": "7", "HST": "5", "AST": "2", "HF": "10", "AF": "11"}
    cells = {**cells, "HC": "", "AC": "x"}
    match = one_match(csv_bytes(MAIN_2526, [main_row(0, cells)]))

    assert dict(match.stats) == {"HS": 12, "AS": 7, "HST": 5, "AST": 2, "HF": 10, "AF": 11}


def test_a_repeated_header_column_reads_its_first_occurrence() -> None:
    """Yinelenen başlıkta İLK sütun geçerli: sonraki kopya (ör. kaymış bir ek sütun) okunmaz."""
    header = (*MAIN_2526, "AvgH")
    line = ",".join(main_row(0).get(name, "") for name in MAIN_2526) + ",9.99"
    content = (",".join(header) + "\r\n" + line + "\r\n").encode("utf-8")

    match = one_match(content)

    assert match.odds[OddsKey("Avg", H2H, "H", PRE_CLOSING)] == 2.10


def test_utf8_with_bom_is_decoded_and_the_bom_leaves_the_first_column_name() -> None:
    content = csv_bytes(MAIN_2526, [main_row(0, {"HomeTeam": "Çınar Gücü"})], bom=True)

    result = parse_file(content, league=E0, season="2526")

    assert result.encoding == "utf-8-sig"
    assert result.columns[0] == "Div"
    assert result.matches[0].home == "Çınar Gücü"


def test_non_utf8_bytes_fall_back_to_latin1() -> None:
    content = csv_bytes(
        MAIN_2526, [main_row(0, {"AwayTeam": "Sintético Norte"})], encoding="latin-1"
    )

    result = parse_file(content, league=E0, season="2526")

    assert result.encoding == "latin-1"
    assert result.matches[0].away == "Sintético Norte"


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("text", "expected"),
    [("16/08/05", date(2005, 8, 16)), ("16/08/2025", date(2025, 8, 16))],
    ids=["iki-haneli-yil", "dort-haneli-yil"],
)
def test_two_and_four_digit_years_give_the_source_date(text: str, expected: date) -> None:
    match = one_match(csv_bytes(MAIN_2526, [main_row(0, {"Date": text})]))

    assert match.date == expected


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("day", "clock", "expected"),
    [
        ("16/08/2025", "15:00", datetime(2025, 8, 16, 14, 0, tzinfo=UTC)),
        ("06/12/2025", "15:00", datetime(2025, 12, 6, 15, 0, tzinfo=UTC)),
        ("29/03/2026", "01:30", datetime(2026, 3, 29, 1, 30, tzinfo=UTC)),
        ("25/10/2026", "01:30", datetime(2026, 10, 25, 1, 30, tzinfo=UTC)),
    ],
    ids=["yaz-saati", "kis-saati", "ilkbahar-boslugu-gec-okuma", "sonbahar-tekrari-gec-okuma"],
)
def test_london_kickoff_becomes_utc_and_a_dst_edge_takes_the_later_reading(
    day: str, clock: str, expected: datetime
) -> None:
    """D5: Time Europe/London yerel saatidir. Geçişte iki yorumun GEÇ olanı: sonuç bilinme anı
    (başlama + 3 sa) gerçek andan önceye düşmesin."""
    match = one_match(csv_bytes(MAIN_2526, [main_row(0, {"Date": day, "Time": clock})]))

    assert match.kickoff == expected
    assert match.kickoff is not None and match.kickoff.utcoffset() == UTC.utcoffset(None)


@pytest.mark.leakage
def test_no_time_column_or_an_empty_time_gives_no_kickoff() -> None:
    old = one_match(csv_bytes(MAIN_OLD, [main_row(0)]), season="1718")
    empty = one_match(csv_bytes(MAIN_2526, [main_row(0, {"Time": ""})]))

    assert old.kickoff is None and empty.kickoff is None


@pytest.mark.parametrize(
    ("cells", "reason"),
    [
        ({"Date": "31/02/2025"}, REASON_DATE),
        ({"Date": "2025-08-16"}, REASON_DATE),
        ({"Date": ""}, REASON_DATE),
        ({"Time": "25:00"}, REASON_TIME),
        ({"Time": "3pm"}, REASON_TIME),
        ({"HomeTeam": ""}, REASON_TEAM),
        ({"AwayTeam": "  "}, REASON_TEAM),
        ({"FTHG": ""}, REASON_GOALS),
        ({"FTAG": "1.0"}, REASON_GOALS),
        ({"FTHG": "-1"}, REASON_GOALS),
        ({"FTR": "A"}, REASON_RESULT),
        ({"FTR": ""}, REASON_RESULT),
        ({"FTR": "h"}, REASON_RESULT),
    ],
)
def test_a_bad_row_is_rejected_with_its_reason_and_the_others_survive(
    cells: dict[str, str], reason: str
) -> None:
    rows = [main_row(0), main_row(1, cells), main_row(2)]

    result = parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")

    assert [match.source_line for match in result.matches] == [1, 3]
    assert result.rejected == (Rejected(line=2, reason=reason),)


def test_an_extra_row_without_a_season_is_rejected() -> None:
    rows = [extra_row(0), extra_row(1, {"Season": ""})]

    result = parse_file(csv_bytes(EXTRA_NEW, rows), league=BRA, season=None)

    assert result.rejected == (Rejected(line=2, reason=REASON_SEASON),)


def test_a_repeated_date_home_away_keeps_the_first_row_and_rejects_the_rest() -> None:
    rows = [
        main_row(0),
        main_row(1),
        main_row(0, {"FTHG": "0", "FTR": "A"}),
        main_row(0, {"Date": "23/08/2025"}),
    ]

    result = parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")

    assert [match.source_line for match in result.matches] == [1, 2, 4]
    assert result.matches[0].home_goals == 2, "ilk satır değil sonraki kalmış"
    assert result.rejected == (Rejected(line=3, reason=REASON_DUPLICATE),)


def test_blank_rows_are_skipped_silently_without_shifting_line_numbers() -> None:
    content = csv_bytes(MAIN_2526, [main_row(0), {}, main_row(2)]) + b",,,\r\n\r\n"

    result = parse_file(content, league=E0, season="2526")

    assert [match.source_line for match in result.matches] == [1, 3]
    assert result.rejected == ()


def test_unusable_prices_are_dropped_and_counted_while_the_row_survives() -> None:
    cells = {"AvgH": "abc", "AvgD": "1.0", "AvgA": "0.95", "MaxH": "nan", "MaxD": "3.10"}

    result = parse_file(csv_bytes(MAIN_2526, [main_row(0, cells)]), league=E0, season="2526")

    (match,) = result.matches
    assert result.dropped_prices == 4
    assert result.price_cells == 8, "AvgH/D/A + AvgCH/D/A + MaxH/D dolu hücre"
    assert match.prices("Avg", H2H, PRE_CLOSING) is None
    assert match.prices("Avg", H2H, CLOSING) == (2.05, 3.45, 3.60)
    assert match.odds[OddsKey("Max", H2H, "D", PRE_CLOSING)] == 3.10


def test_a_row_without_any_odds_is_kept_as_an_oddsless_match() -> None:
    """T1 2022/23'te maçların %8'i oransız: sayılır, düşürülmez."""
    bare = {name: "" for name in ("AvgH", "AvgD", "AvgA", "AvgCH", "AvgCD", "AvgCA")}

    result = parse_file(csv_bytes(MAIN_2526, [main_row(0, bare)]), league=E0, season="2526")

    assert len(result.matches) == 1 and dict(result.matches[0].odds) == {}
    assert (result.price_cells, result.dropped_prices) == (0, 0)


def test_a_main_file_needs_a_season_and_an_extra_file_refuses_one() -> None:
    with pytest.raises(ValueError, match="season zorunlu"):
        parse_file(csv_bytes(MAIN_2526, [main_row(0)]), league=E0, season=None)
    with pytest.raises(ValueError, match="season verilmez"):
        parse_file(csv_bytes(EXTRA_NEW, [extra_row(0)]), league=BRA, season="2526")


def test_results_are_immutable() -> None:
    result = parse_file(csv_bytes(MAIN_2526, [main_row(0)]), league=E0, season="2526")

    with pytest.raises(TypeError):
        result.matches[0].odds[OddsKey("Avg", H2H, "H", CLOSING)] = 9.0  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.dropped_prices = 1  # type: ignore[misc]


# ── check_quality ───────────────────────────────────────────────────────────


def quality(result: ParseResult, *, season: str | None = "2526") -> None:
    check_quality(result, path="/x.csv", league=E0 if season else BRA, season=season)


@pytest.mark.parametrize(
    ("header", "drop", "season"),
    [(MAIN_2526, "FTHG", "2526"), (MAIN_2526, "Date", "2526"), (EXTRA_NEW, "Res", None)],
)
def test_quality_fails_a_file_without_a_required_column(
    header: tuple[str, ...], drop: str, season: str | None
) -> None:
    kept = tuple(name for name in header if name != drop)
    row = main_row(0) if season else extra_row(0)
    league = E0 if season else BRA

    result = parse_file(csv_bytes(kept, [row]), league=league, season=season)

    with pytest.raises(ContractViolation, match=f"zorunlu sütun yok.*{drop}"):
        quality(result, season=season)


@pytest.mark.parametrize(
    ("header", "rows", "path", "season"),
    [
        (MAIN_2526, [{}], "/mmz4281/2526/E0.csv", "2526"),
        (EXTRA_NEW, [], "/new/BRA.csv", None),
    ],
    ids=["ana-bos-satirli", "ek"],
)
def test_quality_fails_a_header_only_file_as_total_loss(
    header: tuple[str, ...], rows: list[dict[str, str]], path: str, season: str | None
) -> None:
    """R88: yalnız başlık satırı tam kayıptır — reddedilen satır yok, pay 0/0, yine de kırmızı."""
    league = E0 if season else BRA
    result = parse_file(csv_bytes(header, rows), league=league, season=season)

    assert (result.matches, result.rejected) == ((), ())
    with pytest.raises(ContractViolation, match="hiç maç yok") as caught:
        check_quality(result, path=path, league=league, season=season)
    assert str(caught.value).startswith(f"{path}: "), "ihlal mesajı dosyayı adlandırmıyor"


def test_quality_fails_empty_content() -> None:
    result = parse_file(b"", league=E0, season="2526")

    assert result.columns == ()
    with pytest.raises(ContractViolation, match="zorunlu sütun"):
        quality(result)


@pytest.mark.parametrize(
    ("season", "has_avgc", "fails"),
    [("1920", False, True), ("2526", False, True), ("1819", False, False), ("1920", True, False)],
)
def test_quality_expects_avgc_columns_from_2019_20(
    season: str, has_avgc: bool, fails: bool
) -> None:
    header = MAIN_2526 if has_avgc else tuple(n for n in MAIN_2526 if not n.startswith("AvgC"))
    result = parse_file(csv_bytes(header, [main_row(0)]), league=E0, season=season)

    if fails:
        with pytest.raises(ContractViolation, match="dönem beklentisi"):
            quality(result, season=season)
    else:
        quality(result, season=season)


def _with_bad_rows(good: int, bad: int) -> ParseResult:
    rows = [main_row(n) for n in range(good)] + [
        main_row(good + n, {"FTR": "A"}) for n in range(bad)
    ]
    return parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")


def test_quality_accepts_one_percent_rejected_rows_and_not_more() -> None:
    quality(_with_bad_rows(99, 1))  # 1/100 = %1 — sınırda, geçer

    with pytest.raises(ContractViolation, match="reddedilen satır 1/99") as caught:
        quality(_with_bad_rows(98, 1))
    assert REASON_RESULT in str(caught.value)
    assert "Ev " not in str(caught.value), "ihlal mesajı ham satır içeriği taşıyor"


def _with_bad_prices(bad: int) -> ParseResult:
    # 50 satır × 6 dolu Avg hücresi = 300 fiyat hücresi.
    rows = [main_row(n, {"AvgH": "x"} if n < bad else None) for n in range(50)]
    return parse_file(csv_bytes(MAIN_2526, rows), league=E0, season="2526")


def test_quality_accepts_one_percent_dropped_prices_and_not_more() -> None:
    quality(_with_bad_prices(3))  # 3/300 = %1 — sınırda, geçer

    with pytest.raises(ContractViolation, match="fiyat hücresi 4/300"):
        quality(_with_bad_prices(4))
```

- [ ] **Step 6: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_football_data.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.history.football_data'`

- [ ] **Step 7: Ayrıştırıcıyı yaz**

Create `src/football_edge/history/football_data.py`:
```python
"""football-data.co.uk CSV baytı → `HistMatch`; saf, ağsız, veritabanısız (tasarım §4.4).

Kısmî kayıp sessiz geçemez (Ruling 6): düşürülen her satır nedeniyle `rejected`e, yok sayılan her
fiyat hücresi `dropped_prices`e sayılır; `check_quality` payları `REJECT_LIMIT`e karşı sorar.
Oransız satır reddedilmez (T1 2022/23'te %8) — oransız kayıt olarak geçer.

Sütun adları football-data'nın başlıklarıdır; ana (`/mmz4281/`) ve ek (`/new/`) dosyalar farklı
adlar taşır, `_LAYOUTS` ikisini aynı kayda indirir. Oran sütunu adları (kitap, market, sonuç,
evre) dörtlüsünden ÜRETİLİR; başlıkta olmayan ad yok sayılır, başlıkta olup sözlükte olmayan
sütun (Asya handikabı, diğer bahisçiler, `HxG`) okunmaz.
"""

from __future__ import annotations

import csv
import io
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from types import MappingProxyType
from zoneinfo import ZoneInfo

from football_edge.collector import ContractViolation
from football_edge.history.catalog import EXTRA, MAIN, HistoryLeague
from football_edge.history.types import (
    CLOSING,
    H2H,
    MARKET_OUTCOMES,
    PRE_CLOSING,
    RESULTS,
    TOTALS_25,
    HistMatch,
    OddsKey,
)

REJECT_LIMIT: float = 0.01
BOOKS: tuple[str, ...] = ("Avg", "Max", "B365", "PS", "BFE", "BbAv", "BbMx")
# Şut, isabetli şut, faul, korner, sarı, kırmızı — ev ve deplasman.
STAT_COLUMNS: tuple[str, ...] = (
    "HS",
    "AS",
    "HST",
    "AST",
    "HF",
    "AF",
    "HC",
    "AC",
    "HY",
    "AY",
    "HR",
    "AR",
)
# `AvgC*` 2019/20'den beri her ana lig dosyasında var (ölçüm belgesi §2.4); yoksa sütun kaymıştır.
CLOSING_ERA: str = "1920"
CLOSING_REFERENCE: tuple[str, ...] = ("AvgCH", "AvgCD", "AvgCA")

REASON_DATE = "tarih çözülemedi"
REASON_TIME = "saat çözülemedi"
REASON_TEAM = "takım adı boş"
REASON_GOALS = "gol çözülemedi"
REASON_RESULT = "sonuç gollerle tutarsız"
REASON_SEASON = "sezon boş"
REASON_DUPLICATE = "yinelenen maç (tarih, ev, deplasman)"

_LONDON = ZoneInfo("Europe/London")
_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{2}|\d{4})")
_TIME = re.compile(r"(\d{2}):(\d{2})")
_COUNT = re.compile(r"\d+")
# Pinnacle'ın 1X2 sütunları `PS…`, Ü/A sütunları `P…` önekini taşır.
_TOTALS_PREFIX: Mapping[str, str] = MappingProxyType({"PS": "P"})
_TOTALS_SUFFIX: Mapping[str, str] = MappingProxyType({"over": ">2.5", "under": "<2.5"})


@dataclass(frozen=True)
class _Layout:
    home: str
    away: str
    home_goals: str
    away_goals: str
    result: str
    season: str | None  # ek dosyada sezon satırdadır


_LAYOUTS: Mapping[str, _Layout] = MappingProxyType(
    {
        MAIN: _Layout("HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", None),
        EXTRA: _Layout("Home", "Away", "HG", "AG", "Res", "Season"),
    }
)


def _column(book: str, market: str, outcome: str, phase: str) -> str:
    closing = "C" if phase == CLOSING else ""
    if market == H2H:
        return f"{book}{closing}{outcome}"
    return f"{_TOTALS_PREFIX.get(book, book)}{closing}{_TOTALS_SUFFIX[outcome]}"


ODDS_COLUMNS: Mapping[str, OddsKey] = MappingProxyType(
    {
        _column(book, market, outcome, phase): OddsKey(book, market, outcome, phase)
        for book in BOOKS
        for market in (H2H, TOTALS_25)
        for outcome in MARKET_OUTCOMES[market]
        for phase in (PRE_CLOSING, CLOSING)
    }
)


@dataclass(frozen=True)
class Rejected:
    line: int
    reason: str


@dataclass(frozen=True)
class ParseResult:
    matches: tuple[HistMatch, ...]
    rejected: tuple[Rejected, ...]
    dropped_prices: int
    price_cells: int
    encoding: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class _Context:
    league: HistoryLeague
    season: str | None
    layout: _Layout
    index: Mapping[str, int]
    odds: tuple[tuple[int, OddsKey], ...]
    stats: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class _Fields:
    season: str
    date: date
    kickoff: datetime | None
    home: str
    away: str
    home_goals: int
    away_goals: int
    result: str


@dataclass(frozen=True)
class _Row:
    outcome: HistMatch | Rejected
    price_cells: int
    dropped: int


def _decode(content: bytes) -> tuple[str, str]:
    try:
        return content.decode("utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        return content.decode("latin-1"), "latin-1"


def _cell(row: Sequence[str], position: int | None) -> str:
    if position is None or position >= len(row):
        return ""
    return row[position].strip()


def _kickoff_utc(match_date: date, clock: time) -> datetime:
    """Europe/London yerel saati → UTC (tasarım D5).

    Yaz saati geçişinde iki yorumdan GEÇ olan an seçilir: ilkbahar boşluğunda (29/03/2026 01:30
    yok) geçiş öncesi ofset, sonbahar tekrarında (25/10/2026 01:30 iki kez) ikinci geçiş. Sonuç
    bilinme anı (başlama + 3 sa) böylece olası gerçek andan hiçbir zaman önceye düşmez.
    """
    local = datetime.combine(match_date, clock, tzinfo=_LONDON)
    return max(local.replace(fold=0).astimezone(UTC), local.replace(fold=1).astimezone(UTC))


def _date(text: str) -> date | None:
    found = _DATE.fullmatch(text)
    if found is None:
        return None
    day, month, year = found.groups()
    try:
        return date(int(year) + (2000 if len(year) == 2 else 0), int(month), int(day))
    except ValueError:
        return None


def _clock(text: str) -> time | None:
    found = _TIME.fullmatch(text)
    if found is None:
        return None
    try:
        return time(int(found.group(1)), int(found.group(2)))
    except ValueError:
        return None


def _price(text: str) -> float | None:
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) and value > 1.0 else None


def _prices(row: Sequence[str], ctx: _Context) -> tuple[Mapping[OddsKey, float], int, int]:
    """(geçerli fiyatlar, dolu fiyat hücresi, yok sayılan hücre)."""
    read = ((key, _cell(row, position)) for position, key in ctx.odds)
    filled = tuple((key, text) for key, text in read if text)
    parsed = tuple((key, _price(text)) for key, text in filled)
    kept = {key: value for key, value in parsed if value is not None}
    return MappingProxyType(kept), len(filled), len(filled) - len(kept)


def _stats(row: Sequence[str], ctx: _Context) -> Mapping[str, int]:
    """Faz 2'de kullanılmaz (sonuçla aynı anda bilinir); sayı olmayan hücre atlanır."""
    cells = ((name, _cell(row, position)) for position, name in ctx.stats)
    return MappingProxyType({name: int(text) for name, text in cells if _COUNT.fullmatch(text)})


def _winner(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "H"
    return "A" if home_goals < away_goals else "D"


def _fields(line: int, row: Sequence[str], ctx: _Context) -> _Fields | Rejected:
    """Satırın maç alanları; ilk bozuk alanın nedeniyle `Rejected`."""
    get = ctx.index.get
    match_date = _date(_cell(row, get("Date")))
    if match_date is None:
        return Rejected(line, REASON_DATE)
    clock_text = _cell(row, get("Time"))
    clock = _clock(clock_text) if clock_text else None
    if clock_text and clock is None:
        return Rejected(line, REASON_TIME)
    home, away = _cell(row, get(ctx.layout.home)), _cell(row, get(ctx.layout.away))
    if not home or not away:
        return Rejected(line, REASON_TEAM)
    goals = (_cell(row, get(ctx.layout.home_goals)), _cell(row, get(ctx.layout.away_goals)))
    if not all(_COUNT.fullmatch(text) for text in goals):
        return Rejected(line, REASON_GOALS)
    home_goals, away_goals = int(goals[0]), int(goals[1])
    result = _cell(row, get(ctx.layout.result))
    if result not in RESULTS or result != _winner(home_goals, away_goals):
        return Rejected(line, REASON_RESULT)
    season = ctx.season if ctx.layout.season is None else _cell(row, get(ctx.layout.season))
    if not season:
        return Rejected(line, REASON_SEASON)
    kickoff = None if clock is None else _kickoff_utc(match_date, clock)
    return _Fields(season, match_date, kickoff, home, away, home_goals, away_goals, result)


def _row(line: int, row: Sequence[str], ctx: _Context) -> _Row:
    odds, cells, dropped = _prices(row, ctx)
    fields = _fields(line, row, ctx)
    if isinstance(fields, Rejected):
        return _Row(fields, cells, dropped)
    match = HistMatch(
        league=ctx.league.code,
        season=fields.season,
        date=fields.date,
        kickoff=fields.kickoff,
        home=fields.home,
        away=fields.away,
        home_goals=fields.home_goals,
        away_goals=fields.away_goals,
        result=fields.result,
        odds=odds,
        stats=_stats(row, ctx),
        source_line=line,
    )
    return _Row(match, cells, dropped)


def _context(header: Sequence[str], league: HistoryLeague, season: str | None) -> _Context:
    names = [name.strip() for name in header]
    # Yinelenen başlıkta İLK sütun geçerli: ters sırada kurulan sözlükte öndeki konum kazanır.
    index = {name: position for position, name in reversed(list(enumerate(names))) if name}
    return _Context(
        league=league,
        season=season,
        layout=_LAYOUTS[league.kind],
        index=MappingProxyType(index),
        odds=tuple((index[name], key) for name, key in ODDS_COLUMNS.items() if name in index),
        stats=tuple((index[name], name) for name in STAT_COLUMNS if name in index),
    )


def _without_duplicates(rows: Sequence[_Row]) -> tuple[_Row, ...]:
    """Aynı (tarih, ev, deplasman) ikinci kez geçerse sonraki satır reddedilir, ilki kalır."""
    found = [
        (position, row.outcome)
        for position, row in enumerate(rows)
        if isinstance(row.outcome, HistMatch)
    ]
    first = {(match.date, match.home, match.away): position for position, match in reversed(found)}
    repeated = {
        position: match.source_line
        for position, match in found
        if first[(match.date, match.home, match.away)] != position
    }
    return tuple(
        _Row(Rejected(repeated[position], REASON_DUPLICATE), row.price_cells, row.dropped)
        if position in repeated
        else row
        for position, row in enumerate(rows)
    )


def _check_season_argument(league: HistoryLeague, season: str | None) -> None:
    if league.kind == MAIN and season is None:
        raise ValueError(f"{league.code}: ana lig dosyası için season zorunlu")
    if league.kind == EXTRA and season is not None:
        raise ValueError(f"{league.code}: ek lig dosyasında sezon satırdan okunur, season verilmez")


def parse_file(content: bytes, *, league: HistoryLeague, season: str | None) -> ParseResult:
    _check_season_argument(league, season)
    text, encoding = _decode(content)
    records = list(csv.reader(io.StringIO(text, newline="")))
    if not records:
        return ParseResult((), (), 0, 0, encoding, ())
    ctx = _context(records[0], league, season)
    rows = _without_duplicates(
        tuple(
            _row(line, record, ctx)
            for line, record in enumerate(records[1:], start=1)
            if any(cell.strip() for cell in record)
        )
    )
    return ParseResult(
        matches=tuple(row.outcome for row in rows if isinstance(row.outcome, HistMatch)),
        rejected=tuple(row.outcome for row in rows if isinstance(row.outcome, Rejected)),
        dropped_prices=sum(row.dropped for row in rows),
        price_cells=sum(row.price_cells for row in rows),
        encoding=encoding,
        columns=tuple(name.strip() for name in records[0] if name.strip()),
    )


def _required(league: HistoryLeague) -> tuple[str, ...]:
    layout = _LAYOUTS[league.kind]
    names = (layout.season, "Date", layout.home, layout.away)
    return (*(name for name in names if name), layout.home_goals, layout.away_goals, layout.result)


def check_quality(
    result: ParseResult, *, path: str, league: HistoryLeague, season: str | None
) -> None:
    """Dosya düzeyinde veri sözleşmesi; ihlal `ContractViolation` — mesaj yalnız sayı taşır."""
    missing = [name for name in _required(league) if name not in result.columns]
    if missing:
        raise ContractViolation(f"{path}: zorunlu sütun yok {missing}")
    if league.kind == MAIN and season is not None and season >= CLOSING_ERA:
        absent = [name for name in CLOSING_REFERENCE if name not in result.columns]
        if absent:
            raise ContractViolation(f"{path}: {season} dönem beklentisi — {absent} sütunu yok")
    rows = len(result.matches) + len(result.rejected)
    if rows and len(result.rejected) / rows > REJECT_LIMIT:
        reasons = Counter(entry.reason for entry in result.rejected).most_common()
        raise ContractViolation(
            f"{path}: reddedilen satır {len(result.rejected)}/{rows} > {REJECT_LIMIT:.0%} "
            f"— nedenler {reasons}"
        )
    if result.price_cells and result.dropped_prices / result.price_cells > REJECT_LIMIT:
        raise ContractViolation(
            f"{path}: yok sayılan fiyat hücresi {result.dropped_prices}/{result.price_cells} "
            f"> {REJECT_LIMIT:.0%}"
        )
    if not result.matches:
        # Kırılan kaynak boş liste üretir; boş liste başarıdan ayırt edilemez (R88, Ruling 6).
        raise ContractViolation(f"{path}: hiç maç yok — yalnız başlık satırı, tam kayıp")
```

- [ ] **Step 8: Yeşil olduğunu gör, statik denetim**
Run: `uv run pytest tests/test_football_data.py -q`
Expected: PASS (49 passed)
Run: `uv run pytest tests/test_football_data.py tests/test_history_catalog.py -q -m leakage`
Expected: `10 passed, 72 deselected`
Run: `uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src`
Expected: temiz (`All checks passed!`, `Success: no issues found`)

- [ ] **Step 9: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır)

Her satır plan yazılırken ayrı bir kopyada uygulandı ve adı geçen test KIRMIZI ölçüldü.

| # | Mutasyon (dosya:ne değişir) | Kırmızı olması gereken test |
|---|---|---|
| 1 | `football_data.py:_kickoff_utc` `max(` → `min(` | `test_london_kickoff_becomes_utc_and_a_dst_edge_takes_the_later_reading[ilkbahar-boslugu-gec-okuma]` |
| 2 | `football_data.py:_kickoff_utc` gövdesi → `return local.astimezone(UTC)` (varsayılan fold=0) | `…[sonbahar-tekrari-gec-okuma]` |
| 3 | `football_data.py:_TOTALS_PREFIX` → `MappingProxyType({})` (Pinnacle Ü/A `PS>2.5` aranır) | `test_the_measured_2025_26_header_maps_to_the_right_book_market_and_phase` |
| 4 | `football_data.py:_column` `phase == CLOSING` → `phase == PRE_CLOSING` (evreler yer değiştirir) | `test_the_measured_2025_26_header_maps_to_the_right_book_market_and_phase` |
| 5 | `football_data.py:_price` `value > 1.0` → `value >= 1.0` | `test_unusable_prices_are_dropped_and_counted_while_the_row_survives` |
| 6 | `football_data.py:check_quality` `len(result.rejected) / rows > REJECT_LIMIT` → `>=` | `test_quality_accepts_one_percent_rejected_rows_and_not_more` |
| 7 | `football_data.py:_without_duplicates` `reversed(found)` → `found` (sonuncu kalır) | `test_a_repeated_date_home_away_keeps_the_first_row_and_rejects_the_rest` |
| 8 | `football_data.py:_decode` `decode("utf-8-sig")` → `decode("utf-8")` | `test_utf8_with_bom_is_decoded_and_the_bom_leaves_the_first_column_name` |
| 9 | `football_data.py:_fields` `or result != _winner(home_goals, away_goals)` silinir | `test_a_bad_row_is_rejected_with_its_reason_and_the_others_survive[cells10-…]` (`FTR: A`) |
| 10 | `football_data.py:check_quality` `season >= CLOSING_ERA` → `>` | `test_quality_expects_avgc_columns_from_2019_20[1920-False-True]` |
| 11 | `football_data.py:_date` `2000 if len(year) == 2` → `1900 if len(year) == 2` | `test_two_and_four_digit_years_give_the_source_date[iki-haneli-yil]` |
| 12 | `football_data.py:parse_file` `if any(cell.strip() for cell in record)` → `if record` | `test_blank_rows_are_skipped_silently_without_shifting_line_numbers` |
| 13 | `football_data.py:_prices` dönüşteki `len(filled) - len(kept)` → `0` | `test_quality_accepts_one_percent_dropped_prices_and_not_more` |
| 14 | `football_data.py:_fields` `season = ctx.season if … else _cell(…)` → `season = ctx.season` | `test_extra_files_carry_only_closing_prices_and_the_row_season` |
| 15 | `catalog.py:_check_season` ardışıklık koşulu → `if False:` | `test_season_codes_reject_a_malformed_or_reversed_range[0507-0708]` |
| 16 | `catalog.py:_check_fields` `isinstance(tier, bool) or ` silinir | `test_an_invalid_catalog_is_refused_by_name[tier: 1, kind: main-tier: true, kind: main-tier]` |
| 17 | `catalog.py:declared_paths` `sorted(` → `list(` | `test_the_real_catalog_declares_500_sorted_unique_paths` |
| 18 | `history_leagues.yaml` `league_id: sui.1` → `swz.1` | `test_the_real_catalog_holds_22_main_and_16_extra_leagues_as_designed` |
| 19 | `history_leagues.yaml` T1 `odds_api_key: "soccer_turkey_super_league"` → `""` | `test_the_six_live_leagues_carry_the_key_of_the_live_config` |
| 20 | `football_data.py:check_quality` `if not result.matches:` → `if False:` (R88 kuralı düşer) | `test_quality_fails_a_header_only_file_as_total_loss[ana-bos-satirli]` ve `[ek]` |
| 21 | `football_data.py:check_quality` R88 mesajındaki `{path}: ` öneki silinir | `test_quality_fails_a_header_only_file_as_total_loss[ek]` |
| 22 | `history_leagues.yaml` E1 `odds_api_key: "soccer_efl_champ"` → `""` (R95 ölçümü kaybolur) | `test_the_real_catalog_holds_22_main_and_16_extra_leagues_as_designed` |
| 23 | `history_leagues.yaml` T1 anahtarı → `"soccer_turkey_super_lig"` (canlıdan ayrışır) | `test_the_six_live_leagues_carry_the_key_of_the_live_config` |
| 24 | `history_leagues.yaml` E2 anahtarı → `"soccer_epl"` (yinelenen) | `test_odds_api_keys_are_unique_and_shaped_like_sport_keys` |
| 25 | `history_leagues.yaml` E1 anahtarı → `"Soccer-EFL-Champ"` (biçim dışı) | `test_odds_api_keys_are_unique_and_shaped_like_sport_keys` |
| 26 | `history_leagues.yaml` SC1 `odds_api_key: ""` → `"soccer_scotland_championship"` | `test_leagues_the_odds_api_does_not_offer_carry_no_key` |
| 27 | `football_data.py:_context` `reversed(list(enumerate(names)))` → `enumerate(names)` (son kopya kazanır) | `test_a_repeated_header_column_reads_its_first_occurrence` |
| 28 | `catalog.py:load_catalog` `set(raw) != {…}` → `not {…} <= set(raw)` (fazladan kök anahtar kabul) | `test_a_catalog_with_an_unknown_top_level_key_is_refused` |

- [ ] **Step 10: Commit**
```bash
git add src/football_edge/history/catalog.py src/football_edge/history/football_data.py \
  config/history_leagues.yaml tests/history_csv.py tests/test_history_catalog.py \
  tests/test_football_data.py
git commit -m "feat: tarihsel lig kataloğu ve football-data ayrıştırıcısı (T1a)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 11: Kapının tamamı**
Run: `TMPDIR=$(mktemp -d) ./verify.sh` — log DOSYASINDAN oku.
Expected: 9 adım PASS + `SKIP: zincir (DATABASE_URL yok)`.

---

### Task 2: Vig temizleme ve olasılık ölçütleri (T3)

**Kademe:** K1 · **Dalga:** 1 · **Worktree/dal:** `.worktrees/wt-devig` · `feat/faz2-devig`

**Files:**
- Create: `src/football_edge/market/devig.py`
- Create: `src/football_edge/market/metrics.py`
- Create: `tests/market_factory.py` (sentetik `HistMatch` kurucusu; Task 7 ve Task 9 da okur, başka
  görev YAZMAZ)
- Test: `tests/test_devig.py`, `tests/test_metrics.py`

**Interfaces:**
- Consumes: Task 0 — `football_edge.history.types`: `PRE_CLOSING`, `CLOSING`, `H2H`, `TOTALS_25`,
  `MARKET_OUTCOMES: Mapping[str, tuple[str, ...]]`, `RESULTS: tuple[str, ...]`,
  `OddsKey(book, market, outcome, phase)`, `HistMatch` (12 alan) ve
  `HistMatch.prices(book: str, market: str, phase: str) -> tuple[float, ...] | None`; `numpy>=2.1`
  (Task 0'ın `pyproject.toml`u).
- Produces:
```python
# football_edge/market/devig.py
MULTIPLICATIVE: str = "multiplicative"; POWER: str = "power"; SHIN: str = "shin"
METHODS: tuple[str, ...] = (MULTIPLICATIVE, POWER, SHIN)
TOLERANCE: float = 1e-12
DEFAULT_METHOD: str = SHIN      # Task 9'un ölçümü (K2) başka yöntemi seçerse controller Task 12'de günceller
class InvalidPrices(ValueError): ...
def overround(prices: Sequence[float]) -> float                    # Σ 1/o − 1
def devig(prices: Sequence[float], method: str) -> tuple[float, ...]
    # ≥ 2 fiyat, hepsi sonlu ve > 1.0; SHIN için Σ 1/o ≥ 1 (değilse InvalidPrices)
    # (kabul edildi) bilinmeyen `method` InvalidPrices DEĞİL düz ValueError: match_probs yutmaz
def match_probs(match: HistMatch, *, book: str, market: str, phase: str, method: str) -> tuple[float, ...] | None
    # match.prices(...) eksikse ya da InvalidPrices ise None — T4, T7, T10 bunu paylaşır

# football_edge/market/metrics.py
@dataclass(frozen=True)
class Interval:
    estimate: float; low: float; high: float
@dataclass(frozen=True)
class Calibration:
    slope: float; intercept: float; ece: float; n: int      # n = havuzlanmış çift sayısı (maç × sonuç)
def per_match_log_loss(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> tuple[float, ...]
def log_loss(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float
def brier(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float
def rps(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float     # sıralı sonuçlar
def calibration(probs: Sequence[Sequence[float]], outcomes: Sequence[int], *, bins: int = 10) -> Calibration
def clv(price: float, fair_probability: float) -> float                          # price · p − 1
def bootstrap_mean(values: Sequence[float], *, resamples: int = 2000, seed: int = 20260922,
                   level: float = 0.95) -> Interval
def outcome_index(match: HistMatch, market: str) -> int
    # H2H: RESULTS.index(match.result); TOTALS_25: toplam gol > 2.5 ise 0 ("over"), değilse 1

# tests/market_factory.py (test yardımcısı — Task 7 ve 9 okur)
Prices = Mapping[tuple[str, str, str], tuple[float, ...]]    # (kitap, market, evre) → fiyatlar
def odds_from(prices: Prices) -> MappingProxyType[OddsKey, float]
def result_of(home_goals: int, away_goals: int) -> str
def hist_match(*, league="M1", season="2324", day=date(2024, 1, 6), kickoff=None, home="Alpha Town",
               away="Beta City", goals=(1, 0), prices=None, line=1) -> HistMatch
def with_prices(match: HistMatch, prices: Prices) -> HistMatch
```

- [ ] **Step 1: Başarısız testleri yaz — test yardımcısı ve vig**
`tests/market_factory.py` — tam içerik:
```python
"""Piyasa testlerinin SENTETİK `HistMatch` kurucusu — gerçek maç, takım ya da oran satırı değil.

Fiyatlar `{(kitap, market, evre): (fiyatlar…)}` biçiminde verilir; sıra MARKET_OUTCOMES'unkidir.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime
from types import MappingProxyType

from football_edge.history.types import MARKET_OUTCOMES, HistMatch, OddsKey

Prices = Mapping[tuple[str, str, str], tuple[float, ...]]


def odds_from(prices: Prices) -> MappingProxyType[OddsKey, float]:
    table = {
        OddsKey(book=book, market=market, outcome=outcome, phase=phase): value
        for (book, market, phase), values in prices.items()
        for outcome, value in zip(MARKET_OUTCOMES[market], values, strict=True)
    }
    return MappingProxyType(table)


def result_of(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "H"
    return "A" if home_goals < away_goals else "D"


def hist_match(
    *,
    league: str = "M1",
    season: str = "2324",
    day: date = date(2024, 1, 6),
    kickoff: datetime | None = None,
    home: str = "Alpha Town",
    away: str = "Beta City",
    goals: tuple[int, int] = (1, 0),
    prices: Prices | None = None,
    line: int = 1,
) -> HistMatch:
    home_goals, away_goals = goals
    return HistMatch(
        league=league,
        season=season,
        date=day,
        kickoff=kickoff,
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        result=result_of(home_goals, away_goals),
        odds=odds_from(prices or {}),
        stats=MappingProxyType({}),
        source_line=line,
    )


def with_prices(match: HistMatch, prices: Prices) -> HistMatch:
    """Aynı maç, eklenmiş (ya da değiştirilmiş) fiyatlarla — yeni değer; girdi değişmez."""
    merged = {**match.odds, **odds_from(prices)}
    return replace(match, odds=MappingProxyType(merged))
```

`tests/test_devig.py` — tam içerik:
```python
"""Vig temizleme: üç yöntemin tanımı, özellikleri ve reddettiği girdiler (tasarım §6)."""

from __future__ import annotations

import math
from dataclasses import replace
from types import MappingProxyType

import pytest

from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, OddsKey
from football_edge.market.devig import (
    DEFAULT_METHOD,
    METHODS,
    MULTIPLICATIVE,
    POWER,
    SHIN,
    TOLERANCE,
    InvalidPrices,
    devig,
    match_probs,
    overround,
)
from tests.market_factory import hist_match

LOPSIDED = (1.30, 5.50, 11.0)  # net favori + iki sürpriz; Σ 1/o ≈ 1.051
BALANCED = (2.10, 3.40, 3.60)
TWO_WAY = (1.50, 2.60)
LONGSHOT = (1.05, 12.0, 30.0)
UNDER_ROUND = (2.2, 4.4, 4.4)  # Σ 1/o = 0.909: borsa en iyi fiyatlarında görülebilir
MARKETS = (LOPSIDED, BALANCED, TWO_WAY, LONGSHOT, (1.90, 1.90))


def test_contract_constants() -> None:
    assert METHODS == (MULTIPLICATIVE, POWER, SHIN) == ("multiplicative", "power", "shin")
    assert DEFAULT_METHOD == SHIN
    assert TOLERANCE == 1e-12


def test_overround_is_the_implied_sum_minus_one() -> None:
    assert overround((2.0, 4.0, 4.0)) == 0.0  # 1/2 + 1/4 + 1/4 = 1: adil kitap
    assert overround((1.9, 1.9)) == pytest.approx(2.0 / 1.9 - 1.0, abs=1e-15)
    assert overround(UNDER_ROUND) < 0.0


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("prices", MARKETS)
def test_probabilities_sum_to_one(method: str, prices: tuple[float, ...]) -> None:
    probs = devig(prices, method)
    assert len(probs) == len(prices)
    assert math.fsum(probs) == pytest.approx(1.0, abs=1e-9)
    assert all(0.0 < p < 1.0 for p in probs)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("prices", (LOPSIDED, BALANCED, TWO_WAY, (3.4, 3.5, 2.2)))
def test_shorter_price_gets_higher_probability(method: str, prices: tuple[float, ...]) -> None:
    probs = devig(prices, method)
    by_price = sorted(range(len(prices)), key=lambda index: prices[index])
    by_probability = sorted(range(len(prices)), key=lambda index: -probs[index])
    assert by_price == by_probability


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("prices", ((2.0, 4.0, 4.0), (2.0, 2.0), (4.0, 4.0, 4.0, 4.0)))
def test_fair_book_returns_the_implied_probabilities_exactly(
    method: str, prices: tuple[float, ...]
) -> None:
    assert devig(prices, method) == tuple(1.0 / price for price in prices)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("prices", ((1.9, 1.9), (2.8, 2.8, 2.8)))
def test_symmetric_prices_give_equal_probabilities(method: str, prices: tuple[float, ...]) -> None:
    share = 1.0 / len(prices)
    assert devig(prices, method) == pytest.approx((share,) * len(prices), abs=1e-12)


def test_multiplicative_divides_by_the_book_sum() -> None:
    # 1/1.9 + 2 · 1/3.8 = 1.0526… → p = (0.5263/1.0526, 0.2632/1.0526, …) = (0.5, 0.25, 0.25)
    assert devig((1.9, 3.8, 3.8), MULTIPLICATIVE) == pytest.approx((0.5, 0.25, 0.25), abs=1e-12)


@pytest.mark.parametrize("prices", (LOPSIDED, BALANCED, TWO_WAY, UNDER_ROUND))
def test_power_probabilities_are_one_common_power_of_the_implied(prices: tuple[float, ...]) -> None:
    implied = tuple(1.0 / price for price in prices)
    probs = devig(prices, POWER)
    exponents = [math.log(p) / math.log(q) for p, q in zip(probs, implied, strict=True)]
    assert max(exponents) - min(exponents) < 1e-9
    # B > 1 ise k > 1 (marj uzak sonuçlardan daha çok alınır), B < 1 ise k < 1
    assert (exponents[0] > 1.0) == (math.fsum(implied) > 1.0)


@pytest.mark.parametrize("prices", (LOPSIDED, BALANCED, TWO_WAY, LONGSHOT))
def test_shin_probabilities_solve_the_shin_equation_with_one_nonnegative_z(
    prices: tuple[float, ...],
) -> None:
    implied = tuple(1.0 / price for price in prices)
    total = math.fsum(implied)
    probs = devig(prices, SHIN)
    # p_i = (√(z² + 4(1−z)·q_i²/B) − z) / (2(1−z))  ⇔  z = (q_i²/B − p_i²) / (p_i(1 − p_i))
    zs = [(q * q / total - p * p) / (p * (1.0 - p)) for p, q in zip(probs, implied, strict=True)]
    assert min(zs) >= 0.0
    assert max(zs) < 0.5
    assert max(zs) - min(zs) < 1e-9


@pytest.mark.parametrize("method", (POWER, SHIN))
def test_power_and_shin_give_the_favourite_more_than_multiplicative(method: str) -> None:
    plain = devig(LOPSIDED, MULTIPLICATIVE)
    adjusted = devig(LOPSIDED, method)
    assert adjusted[0] > plain[0]  # favori
    assert adjusted[2] < plain[2]  # en uzak sürpriz


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "prices",
    ((), (2.0,), (1.0, 3.0), (0.9, 3.0), (-2.0, 3.0), (0.0, 3.0), (math.nan, 3.0), (math.inf, 3.0)),
    ids=("bos", "tek", "bir", "birin-alti", "negatif", "sifir", "nan", "sonsuz"),
)
def test_invalid_prices_are_rejected(method: str, prices: tuple[float, ...]) -> None:
    with pytest.raises(InvalidPrices):
        devig(prices, method)
    with pytest.raises(InvalidPrices):
        overround(prices)


def test_shin_rejects_a_book_under_one_hundred_percent() -> None:
    with pytest.raises(InvalidPrices, match="Shin"):
        devig(UNDER_ROUND, SHIN)
    assert math.fsum(devig(UNDER_ROUND, POWER)) == pytest.approx(1.0, abs=1e-9)
    assert devig(UNDER_ROUND, MULTIPLICATIVE) == pytest.approx((0.5, 0.25, 0.25), abs=1e-12)


def test_shin_rejects_a_margin_it_cannot_explain_below_z_one_half() -> None:
    # (1.25, 1.25): Σ 1/o = 1.6 — z = 0.5'te bile Σ p > 1, çözüm aralıkta yok
    with pytest.raises(InvalidPrices, match="z"):
        devig((1.25, 1.25), SHIN)


def test_unknown_method_is_a_programming_error_not_invalid_prices() -> None:
    with pytest.raises(ValueError, match="bilinmeyen") as caught:
        devig((2.0, 2.0), "additive")
    assert not isinstance(caught.value, InvalidPrices)


def test_match_probs_devigs_the_requested_book_market_and_phase() -> None:
    match = hist_match(
        prices={
            ("Avg", H2H, CLOSING): (1.9, 3.8, 3.8),
            ("Avg", H2H, PRE_CLOSING): (2.0, 4.0, 4.0),
            ("Avg", TOTALS_25, CLOSING): (1.9, 1.9),
        }
    )
    closing = match_probs(match, book="Avg", market=H2H, phase=CLOSING, method=MULTIPLICATIVE)
    assert closing == pytest.approx((0.5, 0.25, 0.25), abs=1e-12)
    early = match_probs(match, book="Avg", market=H2H, phase=PRE_CLOSING, method=MULTIPLICATIVE)
    assert early == (0.5, 0.25, 0.25)
    totals = match_probs(match, book="Avg", market=TOTALS_25, phase=CLOSING, method=SHIN)
    assert totals == pytest.approx((0.5, 0.5), abs=1e-12)


def test_match_probs_is_none_when_a_price_is_missing() -> None:
    match = hist_match(prices={("Avg", H2H, CLOSING): (1.9, 3.8, 3.8)})
    assert match_probs(match, book="PS", market=H2H, phase=CLOSING, method=SHIN) is None
    assert match_probs(match, book="Avg", market=H2H, phase=PRE_CLOSING, method=SHIN) is None
    partial = replace(
        match,
        odds=MappingProxyType(
            {
                OddsKey("Avg", H2H, "H", CLOSING): 1.9,
                OddsKey("Avg", H2H, "A", CLOSING): 3.8,
            }
        ),
    )
    assert match_probs(partial, book="Avg", market=H2H, phase=CLOSING, method=SHIN) is None


def test_match_probs_is_none_when_the_method_cannot_solve_the_prices() -> None:
    match = hist_match(prices={("Avg", H2H, CLOSING): UNDER_ROUND})
    assert match_probs(match, book="Avg", market=H2H, phase=CLOSING, method=SHIN) is None
    assert match_probs(match, book="Avg", market=H2H, phase=CLOSING, method=POWER) is not None


def test_match_probs_does_not_hide_an_unknown_method() -> None:
    bare = hist_match()  # fiyatsız maç: yazım hatası yine de sessiz None olmamalı
    with pytest.raises(ValueError, match="bilinmeyen"):
        match_probs(bare, book="Avg", market=H2H, phase=CLOSING, method="shinn")
```

- [ ] **Step 2: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_devig.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.market.devig'`

- [ ] **Step 3: En küçük uygulamayı yaz — `devig.py`**

İki kök fonksiyonu da parametresinde kesin azalandır — power'da `q_i < 1` olduğu için, Shin'de
`q_i²/B < 1` olduğu için her `p_i` z'de azalır — tek kök vardır ve ikiye bölme onu bulur (plan
yazımında 50 bin rastgele geçerli kitapla da sınandı: marj ≤ %30 iken Shin'in kökü hep [0, 0.5)'te).
`(1.25, 1.25)` gibi saçma bir marjda kök yoktur → `InvalidPrices`. `B == 1` iken bütün yöntemler
`q`yu AYNEN döner: kök aramak yalnız yuvarlama gürültüsü katardı.
`src/football_edge/market/devig.py` — tam içerik:
```python
"""Vig temizleme: bahisçi marjını fiyatlardan ayırıp adil olasılık üretir (tasarım §6, D9).

`q_i = 1/o_i`, `B = Σ q_i`. Üç yöntem saf fonksiyondur; kök bulma stdlib ikiye bölmesidir
(scipy yok, D15). Her iki kök fonksiyonu da parametresinde kesin azalandır — bu yüzden tek kök
vardır ve ikiye bölme onu bulur.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from football_edge.history.types import HistMatch

MULTIPLICATIVE: str = "multiplicative"
POWER: str = "power"
SHIN: str = "shin"
METHODS: tuple[str, ...] = (MULTIPLICATIVE, POWER, SHIN)
TOLERANCE: float = 1e-12
# Task 9'un ölçümü (K2) başka yöntemi seçerse controller Task 12'de günceller.
DEFAULT_METHOD: str = SHIN

# Aralık her adımda yarılanır: 200 adım float çözünürlüğünün çok ötesidir; sonsuz döngü olmaz.
_MAX_STEPS = 200
# Shin'in içeriden bilgi payı z ∈ [0, 0.5); üst uçta kök yoksa çözüm tanımsızdır.
_SHIN_Z_LIMIT = 0.5


class InvalidPrices(ValueError):
    """Vig'i temizlenemeyen fiyat kümesi (sayı, değer ya da yöntemin koşulu tutmuyor)."""


def _check_method(method: str) -> None:
    # Bilinmeyen yöntem veri değil programlama hatasıdır: InvalidPrices DEĞİL, düz ValueError.
    # `match_probs` InvalidPrices'ı None'a çevirir; yazım hatası her maçı sessizce düşürmesin.
    if method not in METHODS:
        raise ValueError(f"bilinmeyen vig yöntemi: {method!r} (seçenekler: {', '.join(METHODS)})")


def _implied(prices: Sequence[float]) -> tuple[float, ...]:
    if len(prices) < 2:
        raise InvalidPrices(f"en az iki fiyat gerekir, {len(prices)} verildi")
    for price in prices:
        if not math.isfinite(price) or price <= 1.0:
            raise InvalidPrices(f"fiyat sonlu ve 1.0'dan büyük olmalı: {price!r}")
    return tuple(1.0 / price for price in prices)


def overround(prices: Sequence[float]) -> float:
    """Kitabın marjı: Σ 1/o − 1 (adil kitapta 0)."""
    return math.fsum(_implied(prices)) - 1.0


def _bisect(excess: Callable[[float], float], low: float, high: float) -> float:
    """Azalan `excess` için excess(low) > 0 ≥ excess(high) aralığındaki kökü döner."""
    for _ in range(_MAX_STEPS):
        if high - low <= TOLERANCE:
            break
        middle = (low + high) / 2.0
        if excess(middle) > 0.0:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _power(implied: tuple[float, ...], total: float) -> tuple[float, ...]:
    def excess(k: float) -> float:
        return math.fsum(math.pow(q, k) for q in implied) - 1.0

    # Σ q^k k'da azalır ve k = 1'de B − 1'dir: B > 1 ise kök k > 1'de, B < 1 ise k < 1'de.
    low, high = (1.0, 2.0) if total > 1.0 else (0.5, 1.0)
    while excess(high) > 0.0:
        high *= 2.0
    while excess(low) <= 0.0:
        low /= 2.0
    k = _bisect(excess, low, high)
    return tuple(math.pow(q, k) for q in implied)


def _shin_probs(implied: tuple[float, ...], total: float, z: float) -> tuple[float, ...]:
    return tuple(
        (math.sqrt(z * z + 4.0 * (1.0 - z) * q * q / total) - z) / (2.0 * (1.0 - z))
        for q in implied
    )


def _shin(implied: tuple[float, ...], total: float) -> tuple[float, ...]:
    if total < 1.0:
        raise InvalidPrices(f"Shin yöntemi Σ 1/o ≥ 1 ister, {total:.6f} verildi")

    def excess(z: float) -> float:
        return math.fsum(_shin_probs(implied, total, z)) - 1.0

    # z = 0'da Σ p = √B > 1; her p_i z'de kesin azalır (q_i²/B < 1 olduğu için).
    if excess(_SHIN_Z_LIMIT) >= 0.0:
        raise InvalidPrices(f"Shin çözümü z ∈ [0, 0.5) aralığında yok (Σ 1/o = {total:.6f})")
    return _shin_probs(implied, total, _bisect(excess, 0.0, _SHIN_Z_LIMIT))


def devig(prices: Sequence[float], method: str) -> tuple[float, ...]:
    """Vig'i temizlenmiş olasılıklar, `prices` sırasıyla; toplamları 1'dir.

    ≥ 2 fiyat, hepsi sonlu ve > 1.0; SHIN için Σ 1/o ≥ 1 — değilse InvalidPrices.
    """
    _check_method(method)
    implied = _implied(prices)
    total = math.fsum(implied)
    if total == 1.0:
        # Adil kitap: marj yok, her yöntemde p = q. Kök aramak yalnız yuvarlama gürültüsü katar.
        return implied
    if method == MULTIPLICATIVE:
        return tuple(q / total for q in implied)
    if method == POWER:
        return _power(implied, total)
    return _shin(implied, total)


def match_probs(
    match: HistMatch, *, book: str, market: str, phase: str, method: str
) -> tuple[float, ...] | None:
    """Kitap/market/evre fiyatlarının adil olasılıkları; fiyat eksik ya da çözülemezse None.

    T4, T7 ve T10 bu tek yolu paylaşır: aynı eksik-veri kuralı üç yerde ayrı yazılmaz.
    """
    _check_method(method)
    prices = match.prices(book, market, phase)
    if prices is None:
        return None
    try:
        return devig(prices, method)
    except InvalidPrices:
        return None
```

- [ ] **Step 4: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_devig.py -q`
Expected: PASS (86 passed)

- [ ] **Step 5: Başarısız testleri yaz — ölçütler**
`tests/test_metrics.py` — tam içerik:
```python
"""Ölçütler: elle hesaplanan değerler ve kalibrasyon/bootstrap özellikleri (tasarım §7.5)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest

from football_edge.history.types import H2H, TOTALS_25
from football_edge.market.metrics import (
    LOG_FLOOR,
    Interval,
    bootstrap_mean,
    brier,
    calibration,
    clv,
    log_loss,
    outcome_index,
    per_match_log_loss,
    rps,
)
from tests.market_factory import hist_match

# İki satırlık elle hesaplanan örnek (1X2; sonuçlar H ve D):
#   satır 1: p = (0.5, 0.3, 0.2), y = (1, 0, 0)
#     LL = −ln 0.5 = 0.693147 · Brier = 0.25 + 0.09 + 0.04 = 0.38
#     RPS = ((0.5 − 1)² + (0.8 − 1)²) / 2 = (0.25 + 0.04) / 2 = 0.145
#   satır 2: p = (0.2, 0.3, 0.5), y = (0, 1, 0)
#     LL = −ln 0.3 = 1.203973 · Brier = 0.04 + 0.49 + 0.25 = 0.78
#     RPS = ((0.2 − 0)² + (0.5 − 1)²) / 2 = (0.04 + 0.25) / 2 = 0.145
#   ortalama: LL = 0.948560 · Brier = 0.58 · RPS = 0.145
TWO_ROWS = ((0.5, 0.3, 0.2), (0.2, 0.3, 0.5))
TWO_OUTCOMES = (0, 1)
Metric = Callable[..., object]
Sample = tuple[tuple[tuple[float, ...], ...], tuple[int, ...]]


def test_two_row_example_by_hand() -> None:
    assert per_match_log_loss(TWO_ROWS, TWO_OUTCOMES) == pytest.approx(
        (-math.log(0.5), -math.log(0.3))
    )
    assert log_loss(TWO_ROWS, TWO_OUTCOMES) == pytest.approx(0.948560, abs=1e-6)
    assert brier(TWO_ROWS, TWO_OUTCOMES) == pytest.approx(0.58)
    assert rps(TWO_ROWS, TWO_OUTCOMES) == pytest.approx(0.145)


def test_perfect_forecast_scores_zero() -> None:
    probs = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    outcomes = (0, 2)
    assert log_loss(probs, outcomes) == 0.0
    assert brier(probs, outcomes) == 0.0
    assert rps(probs, outcomes) == 0.0


def test_uniform_forecast_by_hand() -> None:
    uniform = (1 / 3, 1 / 3, 1 / 3)
    # LL = ln 3 · Brier = (2/3)² + 2·(1/3)² = 2/3
    # RPS: H → ((1/3 − 1)² + (2/3 − 1)²)/2 = 5/18 · D → ((1/3)² + (2/3 − 1)²)/2 = 1/9
    #      A → ((1/3)² + (2/3)²)/2 = 5/18
    assert log_loss((uniform,), (1,)) == pytest.approx(math.log(3))
    assert brier((uniform,), (0,)) == pytest.approx(2 / 3)
    assert rps((uniform,), (0,)) == pytest.approx(5 / 18)
    assert rps((uniform,), (1,)) == pytest.approx(1 / 9)
    assert rps((uniform,) * 3, (0, 1, 2)) == pytest.approx((5 / 18 + 1 / 9 + 5 / 18) / 3)


def test_rps_penalises_mass_on_distant_outcomes_where_brier_does_not() -> None:
    near = ((0.4, 0.6, 0.0),)  # sonuç H; kaçan kütle komşu D'de
    far = ((0.4, 0.0, 0.6),)  # kaçan kütle uzak A'da
    assert brier(near, (0,)) == pytest.approx(0.72)
    assert brier(far, (0,)) == pytest.approx(0.72)
    assert rps(near, (0,)) == pytest.approx(0.18)  # (0.36 + 0) / 2
    assert rps(far, (0,)) == pytest.approx(0.36)  # (0.36 + 0.36) / 2


def test_a_certain_miss_is_floored_not_infinite() -> None:
    assert LOG_FLOOR == 1e-15
    assert per_match_log_loss(((1.0, 0.0, 0.0),), (1,)) == (-math.log(1e-15),)


@pytest.mark.parametrize("metric", (per_match_log_loss, log_loss, brier, rps, calibration))
@pytest.mark.parametrize(
    ("probs", "outcomes"),
    (
        ((), ()),
        (((0.5, 0.5),), (0, 1)),
        (((0.5, 0.5), (0.2, 0.3, 0.5)), (0, 0)),
        (((1.0,),), (0,)),
        (((0.5, 0.5),), (2,)),
        (((0.5, 0.5),), (-1,)),
        (((1.5, -0.5),), (0,)),
        (((math.nan, 0.5),), (0,)),
    ),
    ids=("bos", "uzunluk", "genislik", "tek-sonuc", "sira-ust", "sira-negatif", "aralik", "nan"),
)
def test_malformed_input_is_rejected(
    metric: Metric, probs: tuple[tuple[float, ...], ...], outcomes: tuple[int, ...]
) -> None:
    with pytest.raises(ValueError):
        metric(probs, outcomes)


def test_frequencies_that_match_the_forecasts_give_slope_one_and_no_ece() -> None:
    # (0.75, 0.25) dört maçta, üçünde ilk sonuç: p = 0.75 çiftlerinde ȳ = 3/4, p = 0.25'te 1/4.
    # İki ayrık logit değeri, iki parametre: doygun fit tam olarak a = 0, b = 1 verir.
    result = calibration(((0.75, 0.25),) * 4, (0, 0, 0, 1))
    assert result.slope == pytest.approx(1.0, abs=1e-9)
    assert result.intercept == pytest.approx(0.0, abs=1e-9)
    assert result.ece == pytest.approx(0.0, abs=1e-12)
    assert result.n == 8


def test_forecasts_that_carry_no_information_give_slope_zero() -> None:
    # Aynı tahmin, sonuçlar yarı yarıya: y p'den bağımsız → b = 0, a = 0.
    # ECE = ½·|0.5 − 0.75| + ½·|0.5 − 0.25| = 0.25
    result = calibration(((0.75, 0.25),) * 4, (0, 0, 1, 1))
    assert result.slope == pytest.approx(0.0, abs=1e-9)
    assert result.intercept == pytest.approx(0.0, abs=1e-9)
    assert result.ece == pytest.approx(0.25)


def test_ece_weights_each_bin_by_its_share_of_pairs() -> None:
    # Havuzlanmış 10 çift: p=.75 → y 1,0,1 · p=.25 → y 0,1,0 · p=.35 → y 0,0 · p=.65 → y 1,1
    # 10 kova: (3/10)·|2/3 − 0.75| + (3/10)·|1/3 − 0.25| + (2/10)·0.35 + (2/10)·0.35 = 0.19
    #   (ağırlıksız kova ortalaması 0.2167 olurdu)
    # 2 kova: [0, .5) → |Σy − Σp| = |1 − 1.45| = 0.45 · [.5, 1] → |4 − 3.55| = 0.45 → 0.9/10 = 0.09
    probs = ((0.75, 0.25),) * 3 + ((0.35, 0.65),) * 2
    outcomes = (0, 1, 0, 1, 1)
    assert calibration(probs, outcomes).ece == pytest.approx(0.19)
    assert calibration(probs, outcomes, bins=2).ece == pytest.approx(0.09)


def _synthetic(size: int, *, sharpen: float) -> Sample:
    """Gerçek olasılıktan çekilmiş sonuçlar; tahmin `truth ** sharpen` (1 = kalibre)."""
    rng = np.random.default_rng(7)
    weights = np.exp(rng.normal(0.0, 1.0, size=(size, 3)))
    truth = weights / weights.sum(axis=1, keepdims=True)
    draws = rng.random(size)
    outcomes = np.minimum((np.cumsum(truth, axis=1) < draws[:, None]).sum(axis=1), 2)
    stated = truth**sharpen
    stated = stated / stated.sum(axis=1, keepdims=True)
    probs = tuple(tuple(float(value) for value in row) for row in stated)
    return probs, tuple(int(value) for value in outcomes)


def test_a_calibrated_forecast_has_slope_near_one_and_intercept_near_zero() -> None:
    result = calibration(*_synthetic(20_000, sharpen=1.0))
    assert result.slope == pytest.approx(1.0, abs=0.05)
    assert result.intercept == pytest.approx(0.0, abs=0.05)
    assert result.ece < 0.02
    assert result.n == 60_000


def test_an_over_confident_forecast_has_slope_below_one() -> None:
    confident = calibration(*_synthetic(20_000, sharpen=2.0))
    assert confident.slope < 0.8
    assert confident.ece > calibration(*_synthetic(20_000, sharpen=1.0)).ece


def test_calibration_refuses_forecasts_without_spread() -> None:
    with pytest.raises(ValueError, match="tekil"):
        calibration(((0.5, 0.5),) * 4, (0, 1, 0, 1))


def test_calibration_refuses_a_perfectly_separated_sample() -> None:
    # En olası sonuç HER maçta gerçekleşti: ML eğimi sonsuza gider, fit yakınsayamaz.
    with pytest.raises(ValueError, match="kalibrasyon fiti"):
        calibration(((0.7, 0.3), (0.3, 0.7)), (0, 1))


def test_clv_is_price_times_fair_probability_minus_one() -> None:
    assert clv(2.2, 0.5) == pytest.approx(0.1)
    assert clv(1.8, 0.5) == pytest.approx(-0.1)
    assert clv(2.0, 0.5) == 0.0


@pytest.mark.parametrize(
    ("price", "probability"),
    ((1.0, 0.5), (0.5, 0.5), (math.inf, 0.5), (2.0, -0.1), (2.0, 1.1), (2.0, math.nan)),
)
def test_clv_rejects_impossible_inputs(price: float, probability: float) -> None:
    with pytest.raises(ValueError):
        clv(price, probability)


def test_bootstrap_is_deterministic_for_a_seed() -> None:
    values = tuple(float(value) for value in range(50))
    first = bootstrap_mean(values, resamples=500, seed=3)
    assert first == bootstrap_mean(values, resamples=500, seed=3)
    assert first != bootstrap_mean(values, resamples=500, seed=4)


def test_bootstrap_defaults_are_2000_resamples_the_project_seed_and_95_percent() -> None:
    values = (0.0, 1.0) * 50
    assert bootstrap_mean(values) == bootstrap_mean(
        values, resamples=2000, seed=20260922, level=0.95
    )


def test_bootstrap_interval_brackets_the_sample_mean() -> None:
    interval = bootstrap_mean((0.0, 1.0) * 200, resamples=2000, seed=11)
    assert interval.estimate == 0.5
    # ortalamanın standart hatası 0.5/√400 = 0.025 → %95 aralık ≈ 0.5 ± 0.049
    assert interval.low == pytest.approx(0.451, abs=0.01)
    assert interval.high == pytest.approx(0.549, abs=0.01)


def test_bootstrap_level_sets_the_width() -> None:
    values = (0.0, 1.0) * 200
    wide = bootstrap_mean(values, resamples=1000, level=0.95)
    narrow = bootstrap_mean(values, resamples=1000, level=0.50)
    assert wide.low < narrow.low < 0.5 < narrow.high < wide.high


def test_constant_values_give_a_zero_width_interval() -> None:
    assert bootstrap_mean((0.25,) * 10, resamples=50) == Interval(0.25, 0.25, 0.25)


@pytest.mark.parametrize(
    "kwargs",
    ({"resamples": 0}, {"level": 1.0}, {"level": 0.0}),
    ids=("tekrar-yok", "duzey-bir", "duzey-sifir"),
)
def test_bootstrap_rejects_meaningless_settings(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        bootstrap_mean((0.1, 0.2), **kwargs)
    with pytest.raises(ValueError):
        bootstrap_mean(())


@pytest.mark.parametrize(("goals", "index"), (((2, 0), 0), ((1, 1), 1), ((0, 3), 2)))
def test_outcome_index_for_1x2_follows_results_order(goals: tuple[int, int], index: int) -> None:
    assert outcome_index(hist_match(goals=goals), H2H) == index


@pytest.mark.parametrize(
    ("goals", "index"), (((2, 1), 0), ((3, 0), 0), ((1, 1), 1), ((2, 0), 1), ((0, 0), 1))
)
def test_outcome_index_for_totals_is_over_from_three_goals(
    goals: tuple[int, int], index: int
) -> None:
    assert outcome_index(hist_match(goals=goals), TOTALS_25) == index


def test_outcome_index_rejects_an_unknown_market() -> None:
    with pytest.raises(ValueError, match="bilinmeyen"):
        outcome_index(hist_match(), "ah")
```

- [ ] **Step 6: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_metrics.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.market.metrics'`

- [ ] **Step 7: En küçük uygulamayı yaz — `metrics.py`**

Kalibrasyon fiti Newton/IRLS'dir, başlangıç mükemmel kalibrasyon `(a, b) = (0, 1)`. Tekil tasarım
(bütün `logit(p)` aynı) ve yakınsamayan fit (ayrışan örnek) adıyla `ValueError`dır — sessiz bir
sayı değil. `bootstrap_mean` tekrar başına çeker: `n × resamples` indis matrisi havuzlanmış K1'de
(~45 bin maç × 2000) yüzlerce MB olurdu.
`src/football_edge/market/metrics.py` — tam içerik:
```python
"""Olasılık tahmini ölçütleri: log loss, Brier, RPS, kalibrasyon, CLV, bootstrap (tasarım §7.5).

`outcomes` her maçta gerçekleşen sonucun MARKET_OUTCOMES içindeki sırasıdır (1X2'de H=0, D=1,
A=2). Saf fonksiyonlar; yalnız numpy (D15).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from football_edge.history.types import H2H, RESULTS, TOTALS_25, HistMatch

# log(0) sonsuzdur: tek bir kesin yanlış tahmin ortalamayı sonsuza götürmesin.
LOG_FLOOR = 1e-15
# logit(0) ve logit(1) tanımsız: kalibrasyon fiti uçları kırpar.
LOGIT_CLIP = 1e-6
_IRLS_STEPS = 100
_IRLS_TOLERANCE = 1e-10
# exp taşmasın: |η| > 500'de sigmoid zaten 0 ya da 1'dir.
_ETA_LIMIT = 500.0

Floats = npt.NDArray[np.float64]
Indices = npt.NDArray[np.int64]


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float


@dataclass(frozen=True)
class Calibration:
    slope: float
    intercept: float
    ece: float
    n: int  # havuzlanmış (olasılık, gerçekleşme) çifti sayısı: maç × sonuç


def _checked(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> tuple[Floats, Indices]:
    if len(probs) != len(outcomes):
        raise ValueError(f"olasılık ({len(probs)}) ve sonuç ({len(outcomes)}) sayısı farklı")
    if len(probs) == 0:
        raise ValueError("ölçüt boş örnekte tanımsız")
    widths = {len(row) for row in probs}
    if len(widths) != 1 or min(widths) < 2:
        raise ValueError(f"her satır aynı sayıda (≥ 2) sonuç taşımalı: {sorted(widths)}")
    matrix = np.asarray(probs, dtype=np.float64)
    if not np.all(np.isfinite(matrix)) or np.any(matrix < 0.0) or np.any(matrix > 1.0):
        raise ValueError("olasılıklar sonlu ve [0, 1] aralığında olmalı")
    index = np.asarray(outcomes, dtype=np.int64)
    if np.any(index < 0) or np.any(index >= matrix.shape[1]):
        raise ValueError("sonuç sırası olasılık satırının dışında")
    return matrix, index


def _one_hot(index: Indices, width: int) -> Floats:
    return np.eye(width, dtype=np.float64)[index]


def per_match_log_loss(
    probs: Sequence[Sequence[float]], outcomes: Sequence[int]
) -> tuple[float, ...]:
    """Maç başına −log(max(p[sonuç], 1e-15))."""
    matrix, index = _checked(probs, outcomes)
    hit = matrix[np.arange(index.size), index]
    return tuple(float(value) for value in -np.log(np.maximum(hit, LOG_FLOOR)))


def log_loss(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float:
    values = per_match_log_loss(probs, outcomes)
    return math.fsum(values) / len(values)


def brier(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float:
    """Çok sınıflı Brier: maç başına Σ_k (p_k − y_k)², maçlar üzerinde ortalama."""
    matrix, index = _checked(probs, outcomes)
    gap = matrix - _one_hot(index, matrix.shape[1])
    return float(np.mean(np.sum(gap * gap, axis=1)))


def rps(probs: Sequence[Sequence[float]], outcomes: Sequence[int]) -> float:
    """Sıralı sonuçlar için RPS: (1/(K−1)) Σ_{k<K} (Σ_{j≤k} p_j − Σ_{j≤k} y_j)², ortalama."""
    matrix, index = _checked(probs, outcomes)
    width = matrix.shape[1]
    gap = np.cumsum(matrix, axis=1) - np.cumsum(_one_hot(index, width), axis=1)
    return float(np.mean(np.sum(gap[:, :-1] ** 2, axis=1) / (width - 1)))


def _logistic_fit(x: Floats, y: Floats) -> tuple[float, float]:
    """y ~ a + b·x lojistik fiti (Newton/IRLS); (a, b) döner."""
    if float(np.ptp(x)) == 0.0:
        raise ValueError("kalibrasyon fiti tekil: bütün logit(p) değerleri aynı")
    design = np.column_stack((np.ones_like(x), x))
    beta = np.array([0.0, 1.0])  # mükemmel kalibrasyondan başlar
    for _ in range(_IRLS_STEPS):
        eta = np.clip(design @ beta, -_ETA_LIMIT, _ETA_LIMIT)
        mu = 1.0 / (1.0 + np.exp(-eta))
        hessian = design.T @ (design * (mu * (1.0 - mu))[:, None])
        try:
            step = np.linalg.solve(hessian, design.T @ (y - mu))
        except np.linalg.LinAlgError as error:
            raise ValueError("kalibrasyon fiti tekil (Hessian tersinmez)") from error
        beta = beta + step
        if not np.all(np.isfinite(beta)):
            raise ValueError("kalibrasyon fiti ıraksadı")
        if float(np.max(np.abs(step))) < _IRLS_TOLERANCE:
            return float(beta[0]), float(beta[1])
    raise ValueError("kalibrasyon fiti yakınsamadı (ayrışan örnek olabilir)")


def _ece(p: Floats, y: Floats, bins: int) -> float:
    # Σ (n_b/n)·|ȳ_b − p̄_b| = Σ |Σy_b − Σp_b| / n; boş kova katkı vermez.
    which = np.minimum((p * bins).astype(np.int64), bins - 1)
    hits = np.bincount(which, weights=y, minlength=bins)
    stated = np.bincount(which, weights=p, minlength=bins)
    return float(np.sum(np.abs(hits - stated)) / p.size)


def calibration(
    probs: Sequence[Sequence[float]], outcomes: Sequence[int], *, bins: int = 10
) -> Calibration:
    """Tek-karşı-hepsi havuzlanmış (p, y) çiftlerinde y ~ a + b·logit(p) ve eşit kovalı ECE."""
    if bins < 1:
        raise ValueError(f"kova sayısı ≥ 1 olmalı: {bins}")
    matrix, index = _checked(probs, outcomes)
    p = matrix.ravel()
    y = _one_hot(index, matrix.shape[1]).ravel()
    clipped = np.clip(p, LOGIT_CLIP, 1.0 - LOGIT_CLIP)
    intercept, slope = _logistic_fit(np.log(clipped / (1.0 - clipped)), y)
    return Calibration(slope=slope, intercept=intercept, ece=_ece(p, y, bins), n=int(p.size))


def clv(price: float, fair_probability: float) -> float:
    """Kapanışa göre değer: price · p − 1 (p vig'i temizlenmiş kapanış olasılığı)."""
    if not math.isfinite(price) or price <= 1.0:
        raise ValueError(f"fiyat sonlu ve 1.0'dan büyük olmalı: {price!r}")
    if not 0.0 <= fair_probability <= 1.0:
        raise ValueError(f"olasılık [0, 1] aralığında olmalı: {fair_probability!r}")
    return price * fair_probability - 1.0


def bootstrap_mean(
    values: Sequence[float],
    *,
    resamples: int = 2000,
    seed: int = 20260922,
    level: float = 0.95,
) -> Interval:
    """Ortalama ve maç düzeyinde yerine koymalı yüzdelik bootstrap aralığı (sabit tohum)."""
    if len(values) == 0:
        raise ValueError("boş örneğin ortalaması yok")
    if resamples < 1:
        raise ValueError(f"yeniden örnekleme sayısı ≥ 1 olmalı: {resamples}")
    if not 0.0 < level < 1.0:
        raise ValueError(f"güven düzeyi (0, 1) aralığında olmalı: {level}")
    data = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    # Tekrar başına bir çekiliş: bellek n × resamples'a büyümez (havuzlanmış K1'de ~45 bin maç).
    means = np.array(
        [float(np.mean(data[rng.integers(0, data.size, size=data.size)])) for _ in range(resamples)]
    )
    tail = (1.0 - level) / 2.0 * 100.0
    low, high = np.percentile(means, [tail, 100.0 - tail])
    return Interval(estimate=math.fsum(values) / len(values), low=float(low), high=float(high))


def outcome_index(match: HistMatch, market: str) -> int:
    """Gerçekleşen sonucun MARKET_OUTCOMES[market] içindeki sırası."""
    if market == H2H:
        return RESULTS.index(match.result)
    if market == TOTALS_25:
        return 0 if match.home_goals + match.away_goals > 2.5 else 1
    raise ValueError(f"bilinmeyen market: {market!r}")
```

- [ ] **Step 8: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_devig.py tests/test_metrics.py -q`
Expected: PASS (162 passed)
Run: `uv run mypy src scripts && uv run ruff check src tests && uv run ruff format --check src tests`
Expected: `Success: no issues found …` · `All checks passed!` · `… files already formatted`

- [ ] **Step 9: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır)
| # | Mutasyon (dosya:ne değişir) | Kırmızı olması gereken test |
|---|---|---|
| 1 | `devig.py:devig` — `if total == 1.0:` → `if total == 1.0 and method == MULTIPLICATIVE:` | `test_fair_book_returns_the_implied_probabilities_exactly` (power, shin) |
| 2 | `devig.py:_implied` — `price <= 1.0` → `price < 1.0` | `test_invalid_prices_are_rejected[bir-*]` |
| 3 | `devig.py:_shin_probs` — `4.0 * (1.0 - z) * q * q / total` → `… * q / total` | `test_shin_probabilities_solve_the_shin_equation_with_one_nonnegative_z` |
| 4 | `devig.py:_shin` — `if total < 1.0:` → `if total < 0.0:` | `test_shin_rejects_a_book_under_one_hundred_percent` |
| 5 | `devig.py:match_probs` — baştaki `_check_method(method)` silinir | `test_match_probs_does_not_hide_an_unknown_method` |
| 6 | `devig.py:_check_method` — `raise ValueError(…)` → `raise InvalidPrices(…)` | `test_unknown_method_is_a_programming_error_not_invalid_prices` |
| 7 | `devig.py:devig` — POWER dalı `return tuple(q / total for q in implied)` | `test_power_probabilities_are_one_common_power_of_the_implied` |
| 8 | `devig.py:devig` — son satır (Shin) `return tuple(q / total for q in implied)` | `test_power_and_shin_give_the_favourite_more_than_multiplicative[shin]` |
| 9 | `metrics.py:rps` — `/ (width - 1)` → `/ width` | `test_two_row_example_by_hand` |
| 10 | `metrics.py:rps` — kümülatif yerine `gap = matrix - _one_hot(index, width)` | `test_rps_penalises_mass_on_distant_outcomes_where_brier_does_not` |
| 11 | `metrics.py` — `LOG_FLOOR = 1e-15` → `1e-12` | `test_a_certain_miss_is_floored_not_infinite` |
| 12 | `metrics.py:_ece` — ağırlıklı toplam yerine dolu kovaların AĞIRLIKSIZ ortalaması | `test_ece_weights_each_bin_by_its_share_of_pairs` |
| 13 | `metrics.py:calibration` — `_ece(p, y, bins)` → `_ece(p, y, 10)` | `test_ece_weights_each_bin_by_its_share_of_pairs` |
| 14 | `metrics.py:calibration` — `intercept, slope = _logistic_fit(…)` → `slope, intercept = …` | `test_frequencies_that_match_the_forecasts_give_slope_one_and_no_ece` |
| 15 | `metrics.py:bootstrap_mean` — `default_rng(seed)` → `default_rng()` | `test_bootstrap_is_deterministic_for_a_seed` |
| 16 | `metrics.py:bootstrap_mean` — `[tail, 100.0 - tail]` → `[0.0, 100.0]` | `test_bootstrap_interval_brackets_the_sample_mean` |
| 17 | `metrics.py:outcome_index` — `> 2.5` → `>= 2` | `test_outcome_index_for_totals_is_over_from_three_goals` |

- [ ] **Step 10: Commit**
```bash
git add src/football_edge/market/devig.py src/football_edge/market/metrics.py \
  tests/market_factory.py tests/test_devig.py tests/test_metrics.py
git commit -m "feat: vig temizleme (çarpımsal, power, Shin) ve olasılık ölçütleri (T3)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 11: Kapının tamamı**
Run: `TMPDIR=$(mktemp -d) ./verify.sh` — log DOSYASINDAN oku.
Expected: 9 adım PASS + `SKIP: zincir (DATABASE_URL yok)`.

---

### Task 3: Kilit ve holdout (T5)

**Kademe:** K1 · **Dalga:** 1 · **Worktree/dal:** `.worktrees/wt-lock` · `feat/faz2-lock`

Dönemler, pencereler, holdout anahtarı ve açılış kaydı (`0007`), kilit ve holdout erişim kuralı.
Görevi dört karar biçimlendirir:

1. **Kanonik satır AYRIŞTIRILMIŞ değerlerden kurulur (Ruling R86)** — tasarım §5.2'nin "kaynak
   metni" ifadesinin yerine: lig, sezon, ISO tarih, UTC ISO başlama (yoksa `""`), ev, deplasman,
   goller, sonuç; sonra `OddsKey` sırasıyla her fiyat `kitap|market|sonuç|evre=repr(fiyat)`, sonra ad
   sırasıyla her istatistik `ad=değer`; sekmeyle birleşir. `source_line` girmez.
2. **Holdout'un tek kapısı `select_periods`tir.** Geçerli anahtarı yalnız `open_holdout` kurar: açılışı
   `holdout_access_log`a yazar ve anahtarı kayıt COMMIT'lendikten sonra döner. Anahtar modüle özel
   bir mühür taşır; elle kurulan `HoldoutKey` holdout'u açmaz. `open_holdout` yalnız
   `backtest/final_eval.py`de (Faz 3), mühür yalnız `holdout.py`de, bütün dönemleri dönen `_load_all`
   (Task 6, Ruling R96) yalnız `history/sync.py` ve `history/__main__.py`de anılabilir — AST testi
   zorlar.
3. **Kilit holdout makinesidir, açılış değildir.** Holdout satırlarını `period_of` ile ayırıp içeride
   özetler, dışarı yalnız sayı ve özet verir; `HoldoutKey` kullanmaz. Sonrası dönemi
   (`≥ 2026-07-01`) her hafta büyüdüğü için kilitlenmez.
4. **Pencere holdout'a uzanamaz (Ruling R89).** `in_window` anahtar sormaz; bu yüzden sınır pencere
   KURULURKEN konur: `Window` `end > DEV_END` ya da `start >= end` ise `ValueError` verir.

Dönem üyeliği yalnız kaynağın tarihiyle (`match.date`) belirlenir. `0007` açılış kaydını API
rollerine kapatır (RLS açık, politika yok — hat tablonun sahibi olarak bağlanır ve RLS'yi atlar) ve
TRUNCATE'i bir deyim tetikleyicisiyle engeller (Ruling R90); eski append-only tablolardaki aynı
boşluklar bu görevin kapsamı dışında (controller DEFERRED'a yazar). Bu görevin BÜTÜN testleri
`@pytest.mark.leakage` taşır (Task 5'in `sızıntı` adımı sayar). `0007` bu görevde canlıya
UYGULANMAZ (Task 5 Step 2, controller).

**Files:**
- Create: `src/football_edge/history/holdout.py` (dönemler, pencereler, anahtar, `open_holdout`, `select_periods`)
- Create: `src/football_edge/history/lock.py` (kanonik satır, özet, kilit dosyası, doğrulama)
- Create: `db/migrations/0007_holdout.sql` (`holdout_access_log`: append-only, TRUNCATE yasak, RLS açık ve politikasız)
- Test: `tests/test_holdout.py`, `tests/test_holdout_access_rule.py`, `tests/test_history_lock.py`

**Interfaces:**
- Consumes: Task 0 — `football_edge.history.types`: `CLOSING`, `H2H`, `PRE_CLOSING` (yalnız
  testler), `OddsKey`, `HistMatch` ve `HistMatch.prices(book: str, market: str, phase: str) ->
  tuple[float, ...] | None`. Mevcut: `forbid_ledger_mutation()` (0001),
  `tests.workflow_helpers.MIGRATIONS`.
- Produces:

```python
# football_edge/history/holdout.py
DEV_END: date = date(2025, 7, 1)
HOLDOUT_END: date = date(2026, 7, 1)
DEV: str = "dev"; HOLDOUT: str = "holdout"; POST: str = "post"
class HoldoutLocked(RuntimeError): ...
@dataclass(frozen=True)
class HoldoutKey:
    opened_at: datetime; purpose: str; git_sha: str
    # yalnız open_holdout kurar; select_periods modül-içi bir işaretle doğrular
@dataclass(frozen=True)
class Window:
    start: date | None; end: date                 # [start, end) — maç tarihine (Date) göre
    # R89: end > DEV_END ya da start >= end → ValueError (pencere holdout'a asla uzanmaz)
MAIN_WINDOW: Window = Window(date(2019, 7, 1), DEV_END)    # ana ligler: Avg/AvgC ve saat birlikte var
EXTRA_WINDOW: Window = Window(None, DEV_END)               # ek ligler: yalnız kapanış
def in_window(match: HistMatch, window: Window) -> bool
def period_of(match_date: date) -> str
def open_holdout(conn: psycopg.Connection[Any], *, purpose: str, git_sha: str, now: datetime) -> HoldoutKey
def select_periods(matches: Sequence[HistMatch], *, periods: frozenset[str],
                   key: HoldoutKey | None = None) -> tuple[HistMatch, ...]
    # HOLDOUT istenip geçerli anahtar yoksa HoldoutLocked

# football_edge/history/lock.py
CANONICAL_VERSION: int = 1
class LockViolation(RuntimeError): ...      # LockViolation(*differences); .differences: tuple[str, ...]
    # canonical_line: tz'siz kickoff ya da sekme/satır sonu taşıyan değer → ValueError (R86 kanonik biçim)
@dataclass(frozen=True)
class Digest:
    rows: int; sha256: str; avgc_complete: int   # AvgC 1X2'si tam satır sayısı (kapsam bilgisi)
@dataclass(frozen=True)
class HistoryLock:
    canonical_version: int; locked_at: date; dev_end: date; holdout_end: date
    leagues: Mapping[str, Mapping[str, Digest]]   # kod → {DEV: Digest, HOLDOUT: Digest}
def canonical_line(match: HistMatch) -> str
def digest(matches: Sequence[HistMatch]) -> Digest
def build_lock(matches_by_league: Mapping[str, Sequence[HistMatch]], *, locked_at: date) -> HistoryLock
def dump_lock(lock: HistoryLock) -> str
def load_lock(path: Path) -> HistoryLock                           # R99: bozuk/eksik yapı → LockViolation (CLI'lar exit 9)
def verify_lock(lock: HistoryLock, matches_by_league: Mapping[str, Sequence[HistMatch]]) -> None
    # LockViolation: her farklı (lig, dönem) için beklenen/gerçek satır ve özet; kilitte olmayan lig
```

Controller'ın kabul ettiği, sözleşmeyle uyumlu ekler: `LockViolation(*differences: str)` farkları
`.differences: tuple[str, ...]` olarak da taşır (`raise LockViolation("metin")` yine çalışır; Task
6'nın `lock --verify`i `str(err)`i loglayıp exit 9 verir) · `HoldoutKey`in dördüncü, modüle özel alanı
`_seal` (`field(default=None, repr=False, compare=False)`) · `Window.__post_init__` (R89): `end >
DEV_END` ya da `start >= end` → `ValueError`; `MAIN_WINDOW` ve `EXTRA_WINDOW` bu sınırın içindedir
· `load_lock` (R99) her yapı ve biçim hatasında dosyayı adıyla anan tek farklı `LockViolation`
fırlatır — kilidi okuyan CLI'lar veri farkındaki çıkışı (9) verir.

Hatalar (tüketen görevler için): `Window(...)` holdout'a uzanan ya da boş pencerede `ValueError`
(pencere yalnız geliştirme döneminin içinde kurulur) · `open_holdout` boş amaç, 40 küçük harfli
onaltılık olmayan SHA ya da saat dilimsiz `now` için HİÇBİR ifade yürütmeden `ValueError` ·
`select_periods` bilinmeyen dönem adında `ValueError`, anahtarsız HOLDOUT'ta `HoldoutLocked` ·
`canonical_line` (dolayısıyla `digest`, `build_lock`, `verify_lock`) saat dilimsiz başlamada ya da
sekme/satır sonu içeren değerde `ValueError` · `load_lock` eksik/bilinmeyen alan, sürüm uyuşmazlığı,
bozuk YAML ya da UTF-8 olmayan dosya, 64-hex olmayan özet, geçersiz sayı ya da tarihte
`LockViolation` (R99; veriyle karşılaştırmaz — veri farkını `verify_lock` bildirir).

- [ ] **Step 1: Başarısız testleri yaz — dönemler, anahtar, `0007` ve erişim kuralı**

`FakeAccessLogDb` bu dosyada yaşar (dosya listesi sabit) ve `tests/fake_db.py`nin commit/rollback
desenini izler: bekleyen satır yalnız commit'le kalıcı olur, rollback onu atar; INSERT dışındaki her
ifade reddedilir (açılış maç verisi okumaz).

```python
# tests/test_holdout.py
"""Dönemler, pencereler ve holdout anahtarı (tasarım §5.1, §5.3; D2, D8).

Holdout'un tek kapısı `select_periods`tir ve anahtarı yalnız `open_holdout` kurar; açılış
`holdout_access_log`a commit'lenmeden anahtar dönmez. Veritabanı sahte bir bağlantıyla taklit
edilir; migration metin üzerinden sınanır (gerçek veritabanı testi yok).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.history.holdout import (
    DEV,
    DEV_END,
    EXTRA_WINDOW,
    HOLDOUT,
    HOLDOUT_END,
    MAIN_WINDOW,
    POST,
    HoldoutKey,
    HoldoutLocked,
    Window,
    in_window,
    open_holdout,
    period_of,
    select_periods,
)
from football_edge.history.types import HistMatch
from tests.workflow_helpers import MIGRATIONS

SHA = "0123456789abcdef0123456789abcdef01234567"
NOW = dt.datetime(2026, 9, 22, 12, 0, tzinfo=dt.UTC)
PURPOSE = "Faz 3 kapısı: önceden yazılmış karşılaştırma"


class InsertFailed(Exception):
    """INSERT düştü (bağlantı koptu ya da kısıt ihlali)."""


class CommitFailed(Exception):
    """COMMIT düştü, bağlantı ayakta — `tests/fake_db.py:CommitFailed` deseni."""


@dataclass
class FakeAccessLogDb:
    """`holdout_access_log` taklidi: bekleyen satırlar yalnız commit'le kalıcı olur, rollback
    onları atar. INSERT dışındaki her ifade reddedilir — açılış maç verisi okumaz."""

    fail_insert: bool = False
    fail_commit: bool = False
    statements: list[tuple[str, Any]] = field(default_factory=list)
    pending: list[Any] = field(default_factory=list)
    committed: list[Any] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0

    def cursor(self) -> _AccessCursor:
        return _AccessCursor(self)

    def commit(self) -> None:
        if self.fail_commit:
            raise CommitFailed("COMMIT düştü, bağlantı ayakta")
        self.commits += 1
        self.committed = [*self.committed, *self.pending]
        self.pending = []

    def rollback(self) -> None:
        self.rollbacks += 1
        self.pending = []


class _AccessCursor:
    def __init__(self, db: FakeAccessLogDb) -> None:
        self._db = db

    def __enter__(self) -> _AccessCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        self._db.statements = [*self._db.statements, (text, params)]
        if not text.startswith("INSERT INTO holdout_access_log"):
            raise AssertionError(f"taklit veritabanı bu sorguyu tanımıyor: {text}")
        if self._db.fail_insert:
            raise InsertFailed("INSERT düştü")
        self._db.pending = [*self._db.pending, params]


def _match(day: dt.date, *, kickoff: dt.datetime | None = None, home: str = "Ev A") -> HistMatch:
    return HistMatch(
        league="E0",
        season="2425",
        date=day,
        kickoff=kickoff,
        home=home,
        away="Deplasman B",
        home_goals=1,
        away_goals=1,
        result="D",
        odds=MappingProxyType({}),
        stats=MappingProxyType({}),
        source_line=1,
    )


# İngiltere tarihi 1 Temmuz, başlama UTC'de 30 Haziran 23:30 (00:30 BST): dönem Date'ten gelir.
LATE_KICKOFF = dt.datetime(2025, 6, 30, 23, 30, tzinfo=dt.UTC)
DEV_MATCH = _match(dt.date(2025, 6, 30), home="Ev A")
FIRST_HOLDOUT = _match(dt.date(2025, 7, 1), kickoff=LATE_KICKOFF, home="Ev B")
LAST_HOLDOUT = _match(dt.date(2026, 6, 30), home="Ev C")
POST_MATCH = _match(dt.date(2026, 7, 1), home="Ev D")
MATCHES = (POST_MATCH, DEV_MATCH, LAST_HOLDOUT, FIRST_HOLDOUT)  # kasıtlı olarak sırasız


# ── Dönemler ve pencereler ────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_period_constants_are_the_approved_boundaries() -> None:
    assert (dt.date(2025, 7, 1), dt.date(2026, 7, 1)) == (DEV_END, HOLDOUT_END)
    assert (DEV, HOLDOUT, POST) == ("dev", "holdout", "post")


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("day", "period"),
    [
        (dt.date(2012, 3, 1), DEV),
        (dt.date(2025, 6, 30), DEV),
        (dt.date(2025, 7, 1), HOLDOUT),
        (dt.date(2026, 6, 30), HOLDOUT),
        (dt.date(2026, 7, 1), POST),
        (dt.date(2026, 9, 20), POST),
    ],
)
def test_period_follows_the_source_date_at_every_boundary(day: dt.date, period: str) -> None:
    assert period_of(day) == period


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("day", "inside"),
    [
        (dt.date(2019, 6, 30), False),
        (dt.date(2019, 7, 1), True),
        (dt.date(2025, 6, 30), True),
        (dt.date(2025, 7, 1), False),
    ],
)
def test_main_window_is_half_open_from_2019_07_01_to_dev_end(day: dt.date, inside: bool) -> None:
    assert in_window(_match(day), MAIN_WINDOW) is inside


@pytest.mark.leakage
def test_extra_window_has_no_lower_bound_and_stops_at_dev_end() -> None:
    assert in_window(_match(dt.date(2012, 3, 25)), EXTRA_WINDOW)
    assert not in_window(_match(DEV_END), EXTRA_WINDOW)


@pytest.mark.leakage
def test_window_membership_uses_the_source_date_not_the_kickoff() -> None:
    assert not in_window(FIRST_HOLDOUT, MAIN_WINDOW)
    assert not in_window(FIRST_HOLDOUT, EXTRA_WINDOW)


@pytest.mark.leakage
def test_approved_windows_construct_with_their_documented_bounds() -> None:
    assert Window(dt.date(2019, 7, 1), DEV_END) == MAIN_WINDOW
    assert Window(None, DEV_END) == EXTRA_WINDOW


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("start", "end"),
    [
        (None, HOLDOUT_END),
        (dt.date(2025, 1, 1), dt.date(2026, 1, 1)),
        (None, dt.date(2025, 7, 2)),
    ],
    ids=["open-start-to-holdout-end", "across-dev-end", "one-day-past-dev-end"],
)
def test_window_reaching_past_dev_end_is_rejected(start: dt.date | None, end: dt.date) -> None:
    """R89: `in_window` anahtar sormaz; holdout'a uzanan pencere hiç kurulamamalı."""
    with pytest.raises(ValueError, match="holdout'a uzanamaz"):
        Window(start, end)


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("start", "end"),
    [(dt.date(2020, 1, 1), dt.date(2020, 1, 1)), (dt.date(2021, 1, 1), dt.date(2020, 1, 1))],
    ids=["empty", "reversed"],
)
def test_window_with_start_not_before_end_is_rejected(start: dt.date, end: dt.date) -> None:
    with pytest.raises(ValueError, match="boş pencere"):
        Window(start, end)


# Dönem sınırları, çevreleri ve iki uç: kurulabilen ve kurulamayan pencereleri birlikte üretir.
GRID_DAYS = (
    dt.date.min,
    dt.date(2019, 7, 1),
    dt.date(2025, 6, 30),
    DEV_END,
    dt.date(2025, 7, 2),
    dt.date(2026, 1, 1),
    HOLDOUT_END,
    dt.date(2026, 9, 20),
    dt.date.max,
)
MIXED = (*MATCHES, _match(dt.date(2012, 3, 1), home="Ev E"), _match(dt.date(2026, 9, 20)))


def _constructible(start: dt.date | None, end: dt.date) -> Window | None:
    try:
        return Window(start, end)
    except ValueError:
        return None


@pytest.mark.leakage
def test_no_constructible_window_returns_a_holdout_or_later_match() -> None:
    """R89'un özelliği: kurulabilen HER pencere yalnız geliştirme maçı seçer. Izgaranın iki yanı
    da denediği (kurulan ve reddedilen pencere var) ve boşa seçmediği ayrıca ölçülür."""
    candidates = [(start, end) for start in (None, *GRID_DAYS) for end in GRID_DAYS]
    windows = [window for window in (_constructible(*pair) for pair in candidates) if window]
    leaked = [
        (window, match.date)
        for window in windows
        for match in MIXED
        if in_window(match, window) and period_of(match.date) != DEV
    ]

    assert 0 < len(windows) < len(candidates), "ızgara kurulabilirliğin iki yanını denemiyor"
    assert any(in_window(match, window) for window in windows for match in MIXED)
    assert leaked == [], f"holdout'a ya da sonrasına uzanan pencere: {leaked}"


# ── select_periods ve anahtar ─────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_dev_and_post_need_no_key_and_keep_input_order() -> None:
    assert select_periods(MATCHES, periods=frozenset({DEV, POST})) == (POST_MATCH, DEV_MATCH)


@pytest.mark.leakage
def test_dev_selection_uses_the_source_date_not_the_kickoff() -> None:
    assert select_periods(MATCHES, periods=frozenset({DEV})) == (DEV_MATCH,)


@pytest.mark.leakage
@pytest.mark.parametrize(
    "periods",
    [frozenset({HOLDOUT}), frozenset({DEV, HOLDOUT}), frozenset({HOLDOUT, POST})],
    ids=["holdout", "dev+holdout", "holdout+post"],
)
def test_holdout_without_a_key_is_locked(periods: frozenset[str]) -> None:
    with pytest.raises(HoldoutLocked):
        select_periods(MATCHES, periods=periods)


@pytest.mark.leakage
@pytest.mark.parametrize("seal", [{}, {"_seal": object()}], ids=["no-seal", "foreign-seal"])
def test_hand_built_key_does_not_open_the_holdout(seal: dict[str, object]) -> None:
    forged = HoldoutKey(opened_at=NOW, purpose=PURPOSE, git_sha=SHA, **seal)

    with pytest.raises(HoldoutLocked):
        select_periods(MATCHES, periods=frozenset({HOLDOUT}), key=forged)


@pytest.mark.leakage
def test_key_from_open_holdout_opens_the_holdout_by_source_date() -> None:
    key = open_holdout(FakeAccessLogDb(), purpose=PURPOSE, git_sha=SHA, now=NOW)

    selected = select_periods(MATCHES, periods=frozenset({HOLDOUT}), key=key)

    assert selected == (LAST_HOLDOUT, FIRST_HOLDOUT)


@pytest.mark.leakage
def test_select_periods_rejects_unknown_period_names() -> None:
    with pytest.raises(ValueError, match="bilinmeyen dönem"):
        select_periods(MATCHES, periods=frozenset({"holdot"}))


# ── open_holdout ──────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_open_holdout_commits_one_access_row_before_returning_the_key() -> None:
    db = FakeAccessLogDb()

    key = open_holdout(db, purpose=PURPOSE, git_sha=SHA, now=NOW)

    assert (db.committed, db.pending, db.commits) == ([(NOW, SHA, PURPOSE)], [], 1)
    assert (key.opened_at, key.purpose, key.git_sha) == (NOW, PURPOSE, SHA)


@pytest.mark.leakage
def test_open_holdout_passes_values_as_query_parameters() -> None:
    """Amaç serbest metindir: SQL metnine girerse tırnak içeren bir amaç ifadeyi bozar."""
    purpose = "K3'ün son ölçümü; DROP TABLE"
    db = FakeAccessLogDb()

    open_holdout(db, purpose=purpose, git_sha=SHA, now=NOW)

    ((sql, params),) = db.statements
    assert sql == (
        "INSERT INTO holdout_access_log (opened_at, git_sha, purpose) VALUES (%s, %s, %s)"
    )
    assert params == (NOW, SHA, purpose)


@pytest.mark.leakage
def test_open_holdout_returns_no_key_when_the_insert_fails() -> None:
    db = FakeAccessLogDb(fail_insert=True)

    with pytest.raises(InsertFailed):
        open_holdout(db, purpose=PURPOSE, git_sha=SHA, now=NOW)

    assert (db.committed, db.pending, db.commits, db.rollbacks) == ([], [], 0, 1)


@pytest.mark.leakage
def test_open_holdout_returns_no_key_when_the_commit_fails() -> None:
    db = FakeAccessLogDb(fail_commit=True)

    with pytest.raises(CommitFailed):
        open_holdout(db, purpose=PURPOSE, git_sha=SHA, now=NOW)

    assert (db.committed, db.pending, db.rollbacks) == ([], [], 1)


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"purpose": ""}, "amacı"),
        ({"purpose": "   "}, "amacı"),
        ({"git_sha": SHA.upper()}, "git_sha"),
        ({"git_sha": SHA[:-1]}, "git_sha"),
        ({"git_sha": SHA + "0"}, "git_sha"),
        ({"git_sha": SHA + "\n"}, "git_sha"),
        ({"now": NOW.replace(tzinfo=None)}, "saat dilimli"),
    ],
    ids=["empty", "blank", "upper", "short", "long", "newline", "naive-now"],
)
def test_open_holdout_rejects_bad_openings_before_writing(
    changes: dict[str, Any], message: str
) -> None:
    db = FakeAccessLogDb()
    arguments: dict[str, Any] = {"purpose": PURPOSE, "git_sha": SHA, "now": NOW, **changes}

    with pytest.raises(ValueError, match=message):
        open_holdout(db, **arguments)

    assert db.statements == []


@pytest.mark.leakage
def test_key_is_immutable() -> None:
    key = open_holdout(FakeAccessLogDb(), purpose=PURPOSE, git_sha=SHA, now=NOW)

    with pytest.raises(dataclasses.FrozenInstanceError):
        key.purpose = "başka"  # type: ignore[misc]


# ── Migration 0007 (metin) ────────────────────────────────────────────────────────────────


def _migration_sql() -> str:
    """Yorumsuz, tek boşluklu metin: yoruma alınmış bir satır iddiayı karşılamasın."""
    text = (MIGRATIONS / "0007_holdout.sql").read_text(encoding="utf-8")
    return " ".join(re.sub(r"--[^\n]*", "", text).split())


def _table_columns(sql: str) -> tuple[str, ...]:
    body = re.search(r"create table if not exists holdout_access_log \((.*?)\);", sql)
    assert body is not None, "0007 holdout_access_log tablosunu kurmuyor"
    return tuple(column.strip() for column in body.group(1).split(", "))


@pytest.mark.leakage
def test_access_log_migration_defines_checked_columns() -> None:
    assert _table_columns(_migration_sql()) == (
        "id bigserial primary key",
        "opened_at timestamptz not null",
        "git_sha text not null check (git_sha ~ '^[0-9a-f]{40}$')",
        "purpose text not null check (length(purpose) > 0)",
    )


@pytest.mark.leakage
def test_access_log_migration_is_append_only_with_the_ledger_trigger() -> None:
    """Açılış sayısı ancak kayıt silinemiyorsa kanıttır. Tetikleyici fonksiyonu 0001'in; 0007 onu
    yeniden tanımlamaz (yeniden tanım korumayı sessizce gevşetebilirdi)."""
    sql = _migration_sql()

    assert (
        "create trigger holdout_access_log_append_only before update or delete on "
        "holdout_access_log for each row execute function forbid_ledger_mutation();"
    ) in sql
    assert "create or replace function" not in sql


@pytest.mark.leakage
def test_access_log_migration_blocks_truncate() -> None:
    """Satır tetikleyicisi TRUNCATE'i görmez; bu olmasa sayım tek komutla silinirdi."""
    assert (
        "create trigger holdout_access_log_no_truncate before truncate on holdout_access_log "
        "for each statement execute function forbid_ledger_mutation();"
    ) in _migration_sql()


@pytest.mark.leakage
def test_access_log_migration_closes_the_table_to_api_roles() -> None:
    """R90: RLS açık ve politika yok — API rolleri satır okuyamaz, yazamaz. Hat tablonun sahibi
    olarak RLS'yi atlar; FORCE sahibi de politikaya bağlar ve açılış yazımını durdururdu."""
    sql = _migration_sql()

    assert "alter table holdout_access_log enable row level security;" in sql
    assert "create policy" not in sql
    assert "force row level security" not in sql


@pytest.mark.leakage
def test_open_holdout_writes_exactly_the_migration_columns() -> None:
    """Taklit sütun adını denetlemez: yazım hatasını gerçek veritabanına gitmeden bu yakalar.
    `id` dışındaki her sütun NOT NULL ve varsayılansızdır; hepsi yazılmalı."""
    db = FakeAccessLogDb()
    open_holdout(db, purpose=PURPOSE, git_sha=SHA, now=NOW)
    ((sql, _),) = db.statements
    written = re.search(r"INSERT INTO holdout_access_log \(([^)]*)\)", sql)
    assert written is not None, sql

    defined = [column.split()[0] for column in _table_columns(_migration_sql())]

    assert written.group(1).split(", ") == [name for name in defined if name != "id"]
```

Kural testi `tests/test_access_method_rule.py`nin desenini izler. Korunan üç ad: `open_holdout`,
`_HOLDOUT_SEAL` ve R96'nın `_load_all`ı (Task 6 yazana dek depoda hiç anılmaz). Dedektör test
dosyasında yaşar; sentetik öz-testler her anma biçimini tek tek kırmızıya çevirir, tarama korumaları
taranan kümenin bilinen dosyaları içerdiğini ve dedektörün GERÇEK `holdout.py`de mührü gördüğünü
ölçer, depo testi bütün ihlalleri tek iddiada listeler.

```python
# tests/test_holdout_access_rule.py
"""Holdout erişim kuralı (tasarım §5.3, D8) prose'da kalmaz: holdout yalnız izinli yerde açılır.

Her açılış `holdout_access_log`a düşer ve faz kapıları açılış sayısını ister (Faz 2: sıfır). Kaydı
atlamanın üç yolu burada yakalanır: `open_holdout`ı izinsiz bir modülden çağırmak; anahtarın modüle
özel mührünü (`_HOLDOUT_SEAL`) `holdout.py` dışında anmak — mühürle elle kurulan bir `HoldoutKey`
açılışı kayda yazmadan holdout'u açardı; ve bütün dönemleri dönen `_load_all`ı (R96) kilit yolunun
dışında anmak — holdout satırları `history/` paketinden anahtarsız çıkmaz.

`open_holdout` yalnız `src/football_edge/backtest/final_eval.py`de anılabilir; o dosya Faz 3'te
yazılır, yani Faz 2 boyunca hiçbir yerde. `_load_all` yalnız `history/sync.py` (tanım ve
`load_matches`) ve `history/__main__.py` (kilit komutu) içinde. Bir `def` anma değil, tanımdır.
Taranan: `src/` ve `scripts/` altındaki her `.py`, özyinelemeli (`tests/` taranmaz: testler
holdout'u taklit bağlantıyla açar).

Anma biçimleri: ad (çağrı, atama), öznitelik (`holdout.open_holdout`), `from … import` (takma adlı
da), `getattr(x, "open_holdout")`, holdout modülünden `*`. Docstring, yorum ve düz dize anma
sayılmaz. Bilinen sınırlar: hesaplanmış adlar (`"open_" + "holdout"`), `operator.attrgetter`,
`exec`/`eval` görünmez — bu test kazara girişi durdurur, kasıtlı kaçışı kırmızı takım denetimi
(Task 11) arar.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RULE = "(tasarım §5.3, D8)"
FINAL_EVAL = "src/football_edge/backtest/final_eval.py"
HOLDOUT_MODULE = "src/football_edge/history/holdout.py"
SYNC_MODULE = "src/football_edge/history/sync.py"
HISTORY_CLI = "src/football_edge/history/__main__.py"
PYTHON_ROOTS = ("src", "scripts")
# Korunan ad → (anılabildiği dosyalar, neden). Yollar depo köküne göre, tam eşleşme.
GUARDED: dict[str, tuple[frozenset[str], str]] = {
    "open_holdout": (
        frozenset({FINAL_EVAL}),
        "holdout yalnız son değerlendirmede açılır; açılış kayda düşer",
    ),
    "_HOLDOUT_SEAL": (
        frozenset({HOLDOUT_MODULE}),
        "mühürle elle kurulan anahtar açılışı kayda yazmaz",
    ),
    "_load_all": (
        frozenset({SYNC_MODULE, HISTORY_CLI}),
        "bütün dönemleri döner; holdout satırları history/'den anahtarsız çıkmaz (R96)",
    ),
}

Finding = tuple[int, str, str]  # (satır, korunan ad, anma biçimi)


def rule_violations(source: str, path: str) -> list[str]:
    """`path`teki korunan adların izinsiz BÜTÜN anmaları, satır sırasıyla."""
    findings = sorted(_findings(ast.parse(source, filename=path)))
    return [
        f"{path}:{line}: {form} — {GUARDED[name][1]} {RULE}"
        for line, name, form in findings
        if path not in GUARDED[name][0]
    ]


def _findings(tree: ast.AST) -> Iterator[Finding]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in GUARDED:
            yield node.lineno, node.id, f"{node.id} adı"
        elif isinstance(node, ast.Attribute) and node.attr in GUARDED:
            yield node.lineno, node.attr, f".{node.attr} erişimi"
        elif isinstance(node, ast.ImportFrom):
            yield from _import_findings(node)
        elif isinstance(node, ast.Call):
            yield from _getattr_findings(node)


def _import_findings(node: ast.ImportFrom) -> Iterator[Finding]:
    module = "." * node.level + (node.module or "")
    for alias in node.names:
        if alias.name in GUARDED:
            yield node.lineno, alias.name, f"from {module} import {alias.name}"
        elif alias.name == "*" and module.rsplit(".", 1)[-1] == "holdout":
            # `*` open_holdout'u getirir ve adı gizler; mühür `_` ile başladığı için gelmez.
            yield node.lineno, "open_holdout", f"from {module} import *"


def _getattr_findings(node: ast.Call) -> Iterator[Finding]:
    is_getattr = isinstance(node.func, ast.Name) and node.func.id == "getattr"
    name = node.args[1] if is_getattr and len(node.args) > 1 else None
    if isinstance(name, ast.Constant) and isinstance(name.value, str) and name.value in GUARDED:
        yield node.lineno, name.value, f"getattr(..., {name.value!r})"


def _python_files(root: Path) -> list[Path]:
    return sorted(path for sub in PYTHON_ROOTS for path in (root / sub).rglob("*.py"))


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _scan(root: Path) -> list[str]:
    return [
        found
        for path in _python_files(root)
        for found in rule_violations(path.read_text(encoding="utf-8"), _rel(path, root))
    ]


# ── Koruma 1: dedektör kırmızı verebiliyor mu ──────────────────────────────────────────────

ELSEWHERE = "src/football_edge/market/efficiency.py"
REFERENCES = [
    'open_holdout(conn, purpose="son", git_sha=sha, now=now)',
    "from football_edge.history.holdout import open_holdout",
    "from .holdout import open_holdout as ac",
    "key = holdout.open_holdout(conn, purpose='x', git_sha=sha, now=now)",
    "opener = holdout.open_holdout",
    'getattr(holdout, "open_holdout")',
    "from football_edge.history.holdout import *",
    "from football_edge.history.holdout import _HOLDOUT_SEAL",
    "HoldoutKey(opened_at=t, purpose='x', git_sha=s, _seal=holdout._HOLDOUT_SEAL)",
    "from football_edge.history.sync import _load_all",
    "rows = sync._load_all(conn, catalog)",
    "_load_all(conn, catalog)",
    'getattr(sync, "_load_all")',
]
MENTIONS = [
    '"""open_holdout yalnız final_eval.py\'de çağrılır."""',
    'def f() -> None:\n    """open_holdout burada çağrılmaz."""\n',
    "# open_holdout(conn)",
    'LOGGER.info("open_holdout çağrılmadı")',
    "from football_edge.history.holdout import HoldoutKey, select_periods",
    "open_holdout_count = 0",
]


@pytest.mark.leakage
@pytest.mark.parametrize("snippet", REFERENCES)
def test_detector_sees_every_reference_form_once(snippet: str) -> None:
    violations = rule_violations(snippet, ELSEWHERE)

    assert len(violations) == 1, f"tek ihlal bekleniyordu: {snippet!r} → {violations}"


@pytest.mark.leakage
@pytest.mark.parametrize("snippet", MENTIONS)
def test_detector_ignores_mere_mentions(snippet: str) -> None:
    assert rule_violations(snippet, ELSEWHERE) == []


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("snippet", "path"),
    [
        ("from football_edge.history.holdout import open_holdout", FINAL_EVAL),
        (
            "key = HoldoutKey(opened_at=t, purpose=p, git_sha=s, _seal=_HOLDOUT_SEAL)",
            HOLDOUT_MODULE,
        ),
        ("matches = _load_all(conn, catalog)", SYNC_MODULE),
        ("from football_edge.history.sync import _load_all", HISTORY_CLI),
    ],
)
def test_each_guarded_name_is_allowed_only_in_its_files(snippet: str, path: str) -> None:
    assert rule_violations(snippet, path) == []


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("snippet", "path"),
    [
        ("open_holdout(conn)", "scripts/final_eval.py"),
        ("open_holdout(conn)", "src/football_edge/history/final_eval.py"),
        ("_HOLDOUT_SEAL", "src/football_edge/backtest/holdout.py"),
        ("_load_all(conn, catalog)", "src/football_edge/backtest/sync.py"),
        ("_load_all(conn, catalog)", "src/football_edge/market/__main__.py"),
    ],
)
def test_allow_list_matches_the_exact_path_not_the_file_name(snippet: str, path: str) -> None:
    assert len(rule_violations(snippet, path)) == 1


@pytest.mark.leakage
def test_violations_name_path_line_and_reason() -> None:
    source = "import os\nfrom football_edge.history.holdout import open_holdout\nopen_holdout(c)\n"
    reason = GUARDED["open_holdout"][1]

    assert rule_violations(source, "scripts/x.py") == [
        f"scripts/x.py:2: from football_edge.history.holdout import open_holdout — {reason} {RULE}",
        f"scripts/x.py:3: open_holdout adı — {reason} {RULE}",
    ]


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.leakage
def test_tree_scan_walks_both_roots_recursively(tmp_path: Path) -> None:
    """Dosyaya "ulaşmak" yetmez: okunduğu ve bulgunun köke göreli yolla geldiği ölçülür."""
    _write(tmp_path, "src/paket/alt/derin.py", "open_holdout(conn)\n")
    _write(tmp_path, "scripts/araclar/betik.py", "from x.holdout import open_holdout\n")
    _write(tmp_path, "tests/test_x.py", "open_holdout(conn)\n")

    found = {violation.split(":", 1)[0] for violation in _scan(tmp_path)}

    assert found == {"src/paket/alt/derin.py", "scripts/araclar/betik.py"}


# ── Koruma 2: tarama gerçek kaynağa ulaşıyor ─────────────────────────────────────────────────


@pytest.mark.leakage
def test_scan_reaches_the_known_sources() -> None:
    """Kök kayar ya da özyineleme düşerse kural hiçbir şeyi taramadan yeşil kalırdı."""
    scanned = {_rel(path, REPO) for path in _python_files(REPO)}
    expected = {HOLDOUT_MODULE, "src/football_edge/fetch.py", "scripts/ops_alert.py"}

    assert expected <= scanned, f"taranmayan: {sorted(expected - scanned)}"


@pytest.mark.leakage
def test_detector_sees_the_seal_in_the_real_holdout_module() -> None:
    """Gerçek dosyada pozitif kontrol: mühür yeniden adlandırılırsa kuralın yarısı sessizce söner;
    aynı metin başka bir yolda okunduğunda kırmızı vermeli."""
    source = (REPO / HOLDOUT_MODULE).read_text(encoding="utf-8")

    assert "_HOLDOUT_SEAL" in {name for _, name, _ in _findings(ast.parse(source))}
    assert rule_violations(source, HOLDOUT_MODULE) == []
    assert rule_violations(source, "src/football_edge/history/lock.py") != []


# ── Depo ───────────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_holdout_is_opened_only_where_allowed() -> None:
    violations = _scan(REPO)

    assert not violations, "holdout izinsiz açılabiliyor:\n" + "\n".join(violations)
```

- [ ] **Step 2: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_holdout.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.history.holdout'`
(`Interrupted: 1 error during collection`)

Run: `uv run pytest tests/test_holdout_access_rule.py -q`
Expected: FAIL — `2 failed, 31 passed`: `test_scan_reaches_the_known_sources` (`taranmayan:
['src/football_edge/history/holdout.py']`) ve `test_detector_sees_the_seal_in_the_real_holdout_module`
(`FileNotFoundError`). Geçen 31 test dedektörün kendisini sınar (dedektör test dosyasında yaşar);
onların kırmızısı Step 9'daki kural mutasyonlarıyla (#40–#43) kanıtlanır.

- [ ] **Step 3: En küçük uygulamayı yaz — `holdout.py` ve `0007`**

```python
# src/football_edge/history/holdout.py
"""Dönemler ve holdout erişimi (tasarım §5.1, §5.3; D2, D8).

Dönem üyeliği yalnız kaynağın `Date`'iyle (`HistMatch.date`) belirlenir: başlama saatinin saat
dilimi dönüşümüne bağlı değildir, her makinede aynı sonucu verir. Holdout satırları
`select_periods`ten yalnız `open_holdout`un kurduğu anahtarla çıkar. `open_holdout` açılışı
`holdout_access_log`a (append-only, 0007) yazar ve anahtarı ancak kayıt commit'lendikten SONRA
döner; faz kapıları açılış sayısını bu kayıttan okur (Faz 2: sıfır). `open_holdout`ın yalnız
`backtest/final_eval.py`de, mührün yalnız bu modülde anılabildiğini
`tests/test_holdout_access_rule.py` zorlar.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import psycopg

from football_edge.history.types import HistMatch

DEV_END = date(2025, 7, 1)
HOLDOUT_END = date(2026, 7, 1)
DEV = "dev"
HOLDOUT = "holdout"
POST = "post"
_PERIODS = frozenset({DEV, HOLDOUT, POST})

# Modüle özel mühür: geçerli anahtarı yalnız `open_holdout` kurar. Elle kurulan bir `HoldoutKey`
# bu nesneyi taşımaz ve holdout'u açmaz.
_HOLDOUT_SEAL = object()
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_INSERT_ACCESS = "INSERT INTO holdout_access_log (opened_at, git_sha, purpose) VALUES (%s, %s, %s)"


class HoldoutLocked(RuntimeError):
    """Holdout geçerli bir anahtar olmadan istendi."""


@dataclass(frozen=True)
class HoldoutKey:
    """Kayda geçmiş bir holdout açılışı. Geçerli anahtarı yalnız `open_holdout` kurar."""

    opened_at: datetime
    purpose: str
    git_sha: str
    _seal: object = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class Window:
    """Maçın kaynak tarihine göre [start, end); `start` None ise alt sınır yoktur.

    Pencere holdout'a uzanamaz (R89): `in_window` anahtar sormaz, bu yüzden sınır kurulurken
    konur — `end` en çok `DEV_END`. Boş pencere de reddedilir: sessizce hiçbir şey seçmesin.
    """

    start: date | None
    end: date

    def __post_init__(self) -> None:
        if self.end > DEV_END:
            raise ValueError(f"pencere holdout'a uzanamaz: end {self.end}, sınır {DEV_END}")
        if self.start is not None and self.start >= self.end:
            raise ValueError(f"boş pencere: start {self.start}, end {self.end}")


# Ana ligler: kapanış öncesi Avg, kapanış AvgC ve başlama saati 2019/20'den beri birlikte var.
MAIN_WINDOW = Window(date(2019, 7, 1), DEV_END)
# Ek ligler: yalnız kapanış sütunları; dosyanın ilk satırından geliştirme sonuna.
EXTRA_WINDOW = Window(None, DEV_END)


def in_window(match: HistMatch, window: Window) -> bool:
    after_start = window.start is None or match.date >= window.start
    return after_start and match.date < window.end


def period_of(match_date: date) -> str:
    if match_date < DEV_END:
        return DEV
    if match_date < HOLDOUT_END:
        return HOLDOUT
    return POST


def open_holdout(
    conn: psycopg.Connection[Any], *, purpose: str, git_sha: str, now: datetime
) -> HoldoutKey:
    """Açılışı `holdout_access_log`a yazar; anahtarı YALNIZ kayıt commit'lendikten sonra döner.

    Maç verisi okumaz: anahtar yalnız `select_periods`e verilir. `conn.transaction()` yerine açık
    commit: çağıranın açık bir işlemi varsa `transaction()` yalnız savepoint açar ve commit
    etmez — anahtar, kayıt kalıcı olmadan dönerdi. Açık commit bağlantının bekleyen başka
    yazımlarını da kalıcı kılar; açılış kendi işleminde yapılmalı.
    """
    _check_opening(purpose=purpose, git_sha=git_sha, now=now)
    try:
        with conn.cursor() as cur:
            cur.execute(_INSERT_ACCESS, (now, git_sha, purpose))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return HoldoutKey(opened_at=now, purpose=purpose, git_sha=git_sha, _seal=_HOLDOUT_SEAL)


def _check_opening(*, purpose: str, git_sha: str, now: datetime) -> None:
    """Veritabanının CHECK'lerinden önce: geçersiz açılış hiçbir ifade yürütmeden reddedilir."""
    if not purpose.strip():
        raise ValueError("holdout açılışının amacı boş olamaz")
    # `fullmatch`: `re.match(r"^…$")` sondaki satır sonunu kabul ederdi.
    if not _GIT_SHA.fullmatch(git_sha):
        raise ValueError(f"git_sha 40 küçük harfli onaltılık karakter olmalı: {git_sha!r}")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("holdout açılış anı saat dilimli olmalı")


def select_periods(
    matches: Sequence[HistMatch], *, periods: frozenset[str], key: HoldoutKey | None = None
) -> tuple[HistMatch, ...]:
    """İstenen dönemlerin maçları, giriş sırasıyla. HOLDOUT geçerli bir anahtar ister."""
    unknown = periods - _PERIODS
    if unknown:
        raise ValueError(f"bilinmeyen dönem: {sorted(unknown)}")
    if HOLDOUT in periods and (key is None or key._seal is not _HOLDOUT_SEAL):
        raise HoldoutLocked("holdout istendi ama open_holdout'un kurduğu bir anahtar yok")
    return tuple(match for match in matches if period_of(match.date) in periods)
```

```sql
-- db/migrations/0007_holdout.sql
-- Faz 2: holdout açılış kaydı (tasarım §5.3, D8).
--
-- Holdout (maç tarihi 2025-07-01 ile 2026-07-01 arası) yalnız `open_holdout` ile açılır ve her
-- açılış buraya bir satır yazar: an, git SHA'sı, amaç. Faz kapıları açılış sayısını bu tablodan
-- okur (Faz 2 sonunda sıfır). Kayıt append-only'dir: bir açılış silinemez, değiştirilemez, tablo
-- boşaltılamaz — sayım ancak böyle kanıt olur. Kısıtlar kodun doğrulamasının ikinci katmanıdır.

create table if not exists holdout_access_log (
  id         bigserial primary key,
  opened_at  timestamptz not null,
  git_sha    text not null check (git_sha ~ '^[0-9a-f]{40}$'),
  purpose    text not null check (length(purpose) > 0)
);

-- API rolleri (anon, authenticated) tabloya hiç erişemez: RLS açık, politika YOK (R90). Hat
-- tablonun sahibi olarak bağlanır ve sahip RLS'yi atlar; FORCE kasıtlı olarak yok — açılış
-- yazımı durmasın.
alter table holdout_access_log enable row level security;

-- Append-only zorlaması. forbid_ledger_mutation() 0001'de tanımlandı; yeniden yazılmaz.
drop trigger if exists holdout_access_log_append_only on holdout_access_log;
create trigger holdout_access_log_append_only
  before update or delete on holdout_access_log
  for each row execute function forbid_ledger_mutation();

-- Satır tetikleyicisi TRUNCATE'i görmez: açılış sayısı tek komutla silinemesin (R90).
drop trigger if exists holdout_access_log_no_truncate on holdout_access_log;
create trigger holdout_access_log_no_truncate
  before truncate on holdout_access_log
  for each statement execute function forbid_ledger_mutation();
```

- [ ] **Step 4: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_holdout.py tests/test_holdout_access_rule.py -q`
Expected: PASS (79 passed)

- [ ] **Step 5: Başarısız testleri yaz — kilit**

Takım adları sentetiktir; sabitlenen kanonik satır, Task 0'ın sabit DEĞERLERİNİ (`"1x2"`, `"close"`,
`"pre"`) de içerir — bilerek: onlardan biri değişirse bütün özetler değişir ve bu test
`CANONICAL_VERSION` artışını zorlar.

```python
# tests/test_history_lock.py
"""Tarihsel taban kilidi (tasarım §5.2, D8; kanonik satır: Ruling R86).

Kanonik satırın biçimi burada harfiyen sabitlenir: biçim değişirse `CANONICAL_VERSION` artar ve
kilit yeniden üretilir. Holdout özeti anahtarsız hesaplanır ama satırlar dışarı çıkmaz;
`verify_lock` farkların hepsini tek istisnada söyler. Takım adları sentetiktir.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.history.holdout import DEV, DEV_END, HOLDOUT, HOLDOUT_END
from football_edge.history.lock import (
    CANONICAL_VERSION,
    Digest,
    HistoryLock,
    LockViolation,
    build_lock,
    canonical_line,
    digest,
    dump_lock,
    load_lock,
    verify_lock,
)
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, HistMatch, OddsKey

AVGC = {
    OddsKey("Avg", H2H, "H", CLOSING): 1.95,
    OddsKey("Avg", H2H, "D", CLOSING): 3.6,
    OddsKey("Avg", H2H, "A", CLOSING): 4.2,
}
PRE_HOME = {OddsKey("Avg", H2H, "H", PRE_CLOSING): 2.0}
BASE = HistMatch(
    league="E0",
    season="2425",
    date=dt.date(2025, 3, 15),
    kickoff=dt.datetime(2025, 3, 15, 15, 0, tzinfo=dt.UTC),
    home="Ev A",
    away="Deplasman B",
    home_goals=2,
    away_goals=1,
    result="H",
    odds=MappingProxyType({**AVGC, **PRE_HOME}),
    stats=MappingProxyType({"HS": 12, "AS": 7}),
    source_line=4,
)


def _match(**changes: Any) -> HistMatch:
    return replace(BASE, **changes)


def _described(value: Digest) -> str:
    return f"rows={value.rows} sha256={value.sha256} avgc_complete={value.avgc_complete}"


PARTIAL_AVGC = {key: price for key, price in AVGC.items() if key.outcome != "A"}
# İngiltere tarihi 1 Temmuz, başlama UTC'de 30 Haziran 23:30: dönem Date'ten gelir.
LATE_KICKOFF = dt.datetime(2025, 6, 30, 23, 30, tzinfo=dt.UTC)
E0_DEV = _match()
E0_DEV_PARTIAL = _match(
    date=dt.date(2025, 6, 30), home="Ev C", away="Deplasman D", odds=MappingProxyType(PARTIAL_AVGC)
)
E0_HOLDOUT = _match(
    season="2526", date=dt.date(2025, 7, 1), kickoff=LATE_KICKOFF, home="Ev E", away="Deplasman F"
)
E0_POST = _match(
    season="2627", date=dt.date(2026, 7, 1), kickoff=None, home="Ev G", away="Deplasman H"
)
E0 = (E0_DEV, E0_DEV_PARTIAL, E0_HOLDOUT)
SP1 = (_match(league="SP1", home="Ev I", away="Deplasman J"),)
F1 = (_match(league="F1", home="Ev K", away="Deplasman L"),)
LOCKED_AT = dt.date(2026, 10, 6)


# ── Kanonik satır ──────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_canonical_line_is_exactly_the_documented_layout() -> None:
    """Oranlar OddsKey, istatistikler ad sırasıyla — eşlemelerin ekleme sırası değil."""
    assert CANONICAL_VERSION == 1
    assert canonical_line(BASE) == "\t".join(
        [
            "E0",
            "2425",
            "2025-03-15",
            "2025-03-15T15:00:00+00:00",
            "Ev A",
            "Deplasman B",
            "2",
            "1",
            "H",
            "Avg|1x2|A|close=4.2",
            "Avg|1x2|D|close=3.6",
            "Avg|1x2|H|close=1.95",
            "Avg|1x2|H|pre=2.0",
            "AS=7",
            "HS=12",
        ]
    )


@pytest.mark.leakage
def test_canonical_line_writes_the_kickoff_in_utc() -> None:
    plus_one = dt.timezone(dt.timedelta(hours=1))
    shifted = _match(kickoff=dt.datetime(2025, 3, 15, 16, 0, tzinfo=plus_one))

    assert canonical_line(shifted) == canonical_line(BASE)


@pytest.mark.leakage
def test_canonical_line_leaves_an_unknown_kickoff_empty() -> None:
    assert canonical_line(_match(kickoff=None)).split("\t")[3] == ""


@pytest.mark.leakage
@pytest.mark.parametrize(
    "changes",
    [
        {"league": "E1"},
        {"season": "2324"},
        {"date": dt.date(2025, 3, 16)},
        {"kickoff": dt.datetime(2025, 3, 15, 17, 30, tzinfo=dt.UTC)},
        {"home": "Ev Z"},
        {"away": "Deplasman Z"},
        {"home_goals": 3},
        {"away_goals": 0},
        {"result": "D"},
        {"odds": MappingProxyType({**AVGC, **PRE_HOME, OddsKey("Avg", H2H, "H", CLOSING): 1.96})},
        {"odds": MappingProxyType(AVGC)},
        {"stats": MappingProxyType({"HS": 13, "AS": 7})},
        {"stats": MappingProxyType({"HS": 12})},
    ],
    ids=[
        "league",
        "season",
        "date",
        "kickoff",
        "home",
        "away",
        "home_goals",
        "away_goals",
        "result",
        "price",
        "odds-key",
        "stat-value",
        "stat-key",
    ],
)
def test_canonical_line_changes_when_any_locked_value_changes(changes: dict[str, Any]) -> None:
    assert canonical_line(_match(**changes)) != canonical_line(BASE)


@pytest.mark.leakage
def test_canonical_line_ignores_the_source_line() -> None:
    assert canonical_line(_match(source_line=99)) == canonical_line(BASE)


@pytest.mark.leakage
@pytest.mark.parametrize(
    "changes",
    [
        {"kickoff": dt.datetime(2025, 3, 15, 15, 0)},
        {"home": "Ev\tA"},
        {"away": "Deplasman\nB"},
    ],
    ids=["naive-kickoff", "tab", "newline"],
)
def test_canonical_line_rejects_values_that_would_blur_the_digest(changes: dict[str, Any]) -> None:
    """Saat dilimsiz başlama özeti makinenin yerel saatine bağlardı; ayraç içeren bir değer iki
    farklı veriyi aynı metne indirebilirdi."""
    with pytest.raises(ValueError):
        canonical_line(_match(**changes))


# ── Özet ───────────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_digest_is_sha256_of_the_sorted_newline_joined_lines() -> None:
    lines = sorted([canonical_line(E0_DEV), canonical_line(E0_DEV_PARTIAL)])
    expected = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    reverse_sorted = sorted([E0_DEV, E0_DEV_PARTIAL], key=canonical_line, reverse=True)

    assert digest(reverse_sorted).sha256 == expected


@pytest.mark.leakage
def test_digest_ignores_match_order() -> None:
    assert digest([E0_DEV, E0_DEV_PARTIAL, E0_HOLDOUT]) == digest(
        [E0_HOLDOUT, E0_DEV, E0_DEV_PARTIAL]
    )


@pytest.mark.leakage
def test_digest_counts_rows_and_complete_avgc_1x2() -> None:
    """Yalnız AvgC 1X2'si tam satır sayılır: kapanış öncesi Avg, eksik sonuç ya da başka kitap
    sayılmaz."""
    pre_only = _match(
        home="Ev M",
        odds=MappingProxyType({OddsKey("Avg", H2H, side, PRE_CLOSING): 2.9 for side in "HDA"}),
    )
    max_close = _match(
        home="Ev N",
        odds=MappingProxyType({OddsKey("Max", H2H, side, CLOSING): 3.1 for side in "HDA"}),
    )

    result = digest([E0_DEV, E0_HOLDOUT, E0_DEV_PARTIAL, pre_only, max_close])

    assert (result.rows, result.avgc_complete) == (5, 2)


@pytest.mark.leakage
def test_digest_of_no_matches_is_the_empty_sha256() -> None:
    assert digest([]) == Digest(rows=0, sha256=hashlib.sha256(b"").hexdigest(), avgc_complete=0)


# ── Kilit kurma ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_build_lock_splits_by_source_date_and_leaves_post_out() -> None:
    lock = build_lock({"E0": (*E0, E0_POST)}, locked_at=LOCKED_AT)

    assert dict(lock.leagues["E0"]) == {
        DEV: digest([E0_DEV, E0_DEV_PARTIAL]),
        HOLDOUT: digest([E0_HOLDOUT]),
    }


@pytest.mark.leakage
def test_build_lock_records_the_code_constants() -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)

    assert (lock.canonical_version, lock.locked_at, lock.dev_end, lock.holdout_end) == (
        CANONICAL_VERSION,
        LOCKED_AT,
        DEV_END,
        HOLDOUT_END,
    )


@pytest.mark.leakage
def test_lock_cannot_be_modified_after_it_is_built() -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)

    with pytest.raises(TypeError):
        lock.leagues["E0"][DEV] = Digest(0, "0" * 64, 0)  # type: ignore[index]


# ── Dosya ───────────────────────────────────────────────────────────────────────────────────

LOCK = HistoryLock(
    canonical_version=CANONICAL_VERSION,
    locked_at=LOCKED_AT,
    dev_end=DEV_END,
    holdout_end=HOLDOUT_END,
    leagues=MappingProxyType(
        {
            "SP1": MappingProxyType({DEV: Digest(3, "c" * 64, 1), HOLDOUT: Digest(1, "d" * 64, 1)}),
            "E0": MappingProxyType({HOLDOUT: Digest(2, "b" * 64, 2), DEV: Digest(5, "a" * 64, 4)}),
        }
    ),
)


@pytest.mark.leakage
def test_dump_lock_writes_the_documented_text() -> None:
    """Lig kodları sıralı, anahtar sırası sabit; başlık içerik taşımadığını ve değişikliğin
    gerekçeli commit olduğunu söyler."""
    header, body = dump_lock(LOCK).split("canonical_version:", 1)

    assert header.splitlines(), "başlık yorumu yok"
    assert all(line.startswith("# ") for line in header.splitlines())
    assert "İÇERİK TAŞIMAZ" in header and "gerekçeli bir commit" in header
    assert "canonical_version:" + body == "\n".join(
        [
            "canonical_version: 1",
            "locked_at: 2026-10-06",
            "dev_end: 2025-07-01",
            "holdout_end: 2026-07-01",
            "leagues:",
            "  E0:",
            "    dev:",
            "      rows: 5",
            f"      sha256: {'a' * 64}",
            "      avgc_complete: 4",
            "    holdout:",
            "      rows: 2",
            f"      sha256: {'b' * 64}",
            "      avgc_complete: 2",
            "  SP1:",
            "    dev:",
            "      rows: 3",
            f"      sha256: {'c' * 64}",
            "      avgc_complete: 1",
            "    holdout:",
            "      rows: 1",
            f"      sha256: {'d' * 64}",
            "      avgc_complete: 1",
            "",
        ]
    )


@pytest.mark.leakage
def test_dump_then_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "history_lock.yaml"
    path.write_text(dump_lock(LOCK), encoding="utf-8")

    assert load_lock(path) == LOCK


@pytest.mark.leakage
def test_dumped_lock_carries_no_match_content() -> None:
    text = dump_lock(build_lock({"E0": E0, "SP1": SP1}, locked_at=LOCKED_AT))

    assert not [name for match in (*E0, *SP1) for name in (match.home, match.away) if name in text]


@pytest.mark.leakage
@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("canonical_version: 1", "canonical_version: 2", "canonical_version"),
        ("canonical_version: 1", "canonical_version: true", "canonical_version"),
        (f"sha256: {'a' * 64}", f"sha256: {'a' * 63}", "sha256"),
        (f"sha256: {'a' * 64}", f"sha256: {'A' * 64}", "sha256"),
        ("rows: 5", "rows: -5", "rows"),
        ("rows: 5", "rows: true", "rows"),
        ("avgc_complete: 4", "avgc_complete: 6", "avgc_complete"),
        ("locked_at: 2026-10-06", "locked_at: 2026-10-06 12:00:00", "locked_at"),
        ("  SP1:\n    dev:", "  SP1:\n    post:", "SP1"),
        ("leagues:\n", "locked_by: x\nleagues:\n", "bilinmeyen"),
        ("holdout_end: 2026-07-01\n", "", "eksik alan ['holdout_end']"),
        ("leagues:\n", "leagues: [\n", "okunamıyor"),
    ],
    ids=[
        "version",
        "version-bool",
        "short-sha",
        "upper-sha",
        "negative-rows",
        "bool-rows",
        "coverage-above-rows",
        "datetime",
        "unknown-period",
        "unknown-key",
        "missing-key",
        "broken-yaml",
    ],
)
def test_load_lock_rejects_malformed_files(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    """R99: her yapı ve biçim hatası dosyayı adıyla anan TEK farklı bir LockViolation'dır —
    kilidi okuyan CLI'lar veri farkıyla aynı çıkışı (9) verir, traceback değil."""
    text = dump_lock(LOCK)
    assert old in text, "değişiklik metne uymuyor — test kurgusu bayatlamış"
    path = tmp_path / "history_lock.yaml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

    with pytest.raises(LockViolation, match=re.escape(message)) as caught:
        load_lock(path)

    (difference,) = caught.value.differences
    assert str(path) in difference


@pytest.mark.leakage
def test_load_lock_reports_an_undecodable_file_as_a_violation(tmp_path: Path) -> None:
    path = tmp_path / "history_lock.yaml"
    path.write_bytes(dump_lock(LOCK).encode("utf-8").replace(b"# ", b"# \xff", 1))

    with pytest.raises(LockViolation, match="okunamıyor"):
        load_lock(path)


# ── Doğrulama ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.leakage
def test_verify_lock_accepts_unchanged_data_in_any_order_and_new_post_rows() -> None:
    lock = build_lock({"E0": E0, "SP1": SP1}, locked_at=LOCKED_AT)

    verify_lock(lock, {"SP1": SP1, "E0": (E0_POST, *reversed(E0))})


@pytest.mark.leakage
@pytest.mark.parametrize(("index", "period"), [(0, DEV), (2, HOLDOUT)], ids=["dev", "holdout"])
def test_verify_lock_reports_a_corrected_score_in_each_locked_period(
    index: int, period: str
) -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)
    corrected = tuple(
        replace(match, home_goals=3) if position == index else match
        for position, match in enumerate(E0)
    )
    actual = build_lock({"E0": corrected}, locked_at=LOCKED_AT).leagues["E0"][period]

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": corrected})

    expected = lock.leagues["E0"][period]
    assert caught.value.differences == (
        f"E0/{period}: beklenen {_described(expected)} · gerçek {_described(actual)}",
    )


@pytest.mark.leakage
def test_verify_lock_reports_a_removed_row() -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)

    with pytest.raises(LockViolation, match=r"E0/dev: beklenen rows=2 .* gerçek rows=1 "):
        verify_lock(lock, {"E0": E0[1:]})


@pytest.mark.leakage
def test_verify_lock_reports_a_league_absent_from_the_lock() -> None:
    lock = build_lock({"E0": E0}, locked_at=LOCKED_AT)

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": E0, "F1": F1})

    assert caught.value.differences == ("F1: veride var, kilitte yok",)


@pytest.mark.leakage
def test_verify_lock_reports_a_locked_league_missing_from_the_data() -> None:
    lock = build_lock({"E0": E0, "SP1": SP1}, locked_at=LOCKED_AT)

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": E0})

    assert caught.value.differences == ("SP1: kilitte var, veride yok",)


@pytest.mark.leakage
def test_verify_lock_reports_a_period_missing_from_the_lock() -> None:
    built = build_lock({"E0": E0}, locked_at=LOCKED_AT)
    dev_only = MappingProxyType({DEV: built.leagues["E0"][DEV]})

    with pytest.raises(LockViolation) as caught:
        verify_lock(replace(built, leagues=MappingProxyType({"E0": dev_only})), {"E0": E0})

    actual = _described(built.leagues["E0"][HOLDOUT])
    assert caught.value.differences == (f"E0/holdout: beklenen yok · gerçek {actual}",)


@pytest.mark.leakage
def test_verify_lock_reports_moved_boundaries_and_a_foreign_version() -> None:
    lock = replace(
        build_lock({"E0": E0}, locked_at=LOCKED_AT),
        canonical_version=2,
        dev_end=dt.date(2025, 6, 30),
        holdout_end=dt.date(2026, 7, 2),
    )

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": E0})

    assert caught.value.differences == (
        "canonical_version: kilit 2, kod 1",
        "dev_end: kilit 2025-06-30, kod 2025-07-01",
        "holdout_end: kilit 2026-07-02, kod 2026-07-01",
    )


@pytest.mark.leakage
def test_verify_lock_lists_every_difference_in_one_violation() -> None:
    lock = replace(
        build_lock({"E0": E0, "SP1": SP1}, locked_at=LOCKED_AT), dev_end=dt.date(2025, 6, 30)
    )
    corrected = replace(E0_DEV, away_goals=0)

    with pytest.raises(LockViolation) as caught:
        verify_lock(lock, {"E0": (corrected, *E0[1:]), "F1": F1})

    before = lock.leagues["E0"][DEV]
    after = digest([corrected, E0_DEV_PARTIAL])
    assert caught.value.differences == (
        "dev_end: kilit 2025-06-30, kod 2025-07-01",
        f"E0/dev: beklenen {_described(before)} · gerçek {_described(after)}",
        "F1: veride var, kilitte yok",
        "SP1: kilitte var, veride yok",
    )
    assert str(caught.value).splitlines()[1:] == list(caught.value.differences)
```

- [ ] **Step 6: Kırmızı olduğunu gör**

Run: `uv run pytest tests/test_history_lock.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.history.lock'`

- [ ] **Step 7: En küçük uygulamayı yaz — `lock.py`**

`dump_lock` YAML'ı elle yazar (anahtar sırası ve başlık yorumu sabit kalsın diye); `load_lock`
`yaml.safe_load` ile okur ve yapıyı doğrular; her yapı ve biçim hatası tek farklı bir
`LockViolation`dır (R99). `bool` bir `int`, `datetime` bir `date` alt sınıfıdır: tip denetimleri
`type(x) is …` ile yapılır.

```python
# src/football_edge/history/lock.py
"""Tarihsel taban kilidi (tasarım §5.2, D8; kanonik satır: Ruling R86).

Geliştirme ve holdout dönemlerinin satırları, lig başına, satır sayısına ve kanonik satırların
sha256 özetine indirgenir; özetler `config/history_lock.yaml`da depoya girer — içerik değil, yalnız
sayı ve özet. Her yüklemede veriden yeniden hesaplanır: kaynak eski bir satırı değiştirirse
`verify_lock` farkların hepsini tek bir `LockViolation`da söyler ve karar insana düşer.

Kanonik satır AYRIŞTIRILMIŞ değerlerden kurulur (R86): kaynak metni `HistMatch`te yoktur ve
"2.10" → "2.1" gibi bir biçim farkını yanlış ihlal sayardı; değer değişikliğini ikisi de yakalar.
Biçim değişirse `CANONICAL_VERSION` artar ve kilit yeniden üretilir.

Kilit holdout makinesidir, bir açılış değildir: holdout satırları burada `period_of` ile ayrılıp
özetlenir, dışarı yalnız satır sayısı, özet ve AvgC kapsamı çıkar; satırın kendisi hiç dönmez. Bu
yüzden `HoldoutKey` kullanmaz ve `holdout_access_log`a yazmaz — holdout'u OKUYAN her yol
`select_periods` + `open_holdout`tan geçer. Sonrası dönemi kilitlenmez: her hafta büyür.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from football_edge.history.holdout import DEV, DEV_END, HOLDOUT, HOLDOUT_END, period_of
from football_edge.history.types import CLOSING, H2H, HistMatch

CANONICAL_VERSION = 1
# Kilitlenen dönemler, dosyadaki sırasıyla.
_LOCKED_PERIODS = (DEV, HOLDOUT)
# Kapsam bilgisi referans kapanıştan (D3): lig önerisi holdout doluluğunu açmadan buradan okur.
_REFERENCE_BOOK = "Avg"
_SEPARATORS = ("\t", "\n", "\r")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ROOT_KEYS = frozenset({"canonical_version", "locked_at", "dev_end", "holdout_end", "leagues"})
_DIGEST_KEYS = frozenset({"rows", "sha256", "avgc_complete"})
_HEADER = (
    "# Tarihsel taban kilidi (tasarım §5.2, D8): `python -m football_edge.history lock --write`.",
    "# İÇERİK TAŞIMAZ: yalnız dönem başına satır sayısı, kanonik satırların sha256 özeti ve AvgC",
    "# 1X2'si tam satır sayısı. Kilitli dönemler dev ve holdout; sonrası her hafta değiştiği için",
    "# kilitlenmez. Bu dosyayı değiştirmek gerekçeli bir commit'tir (ör. kaynak eski bir skoru",
    "# düzeltti): gerekçe commit mesajına yazılır, eski özet git geçmişinde kalır.",
)


class LockViolation(RuntimeError):
    """Kilitli dönemlerin verisi kilitten farklı. Farkların HEPSİ tek istisnada, sırayla."""

    def __init__(self, *differences: str) -> None:
        self.differences = differences
        super().__init__(f"kilit ihlali — {len(differences)} fark:\n" + "\n".join(differences))


@dataclass(frozen=True)
class Digest:
    rows: int
    sha256: str
    avgc_complete: int  # AvgC 1X2'si tam satır sayısı (kapsam bilgisi)


@dataclass(frozen=True)
class HistoryLock:
    canonical_version: int
    locked_at: date
    dev_end: date
    holdout_end: date
    leagues: Mapping[str, Mapping[str, Digest]]  # kod → {DEV: Digest, HOLDOUT: Digest}


def canonical_line(match: HistMatch) -> str:
    """Kimlik ve sonuç alanları, `OddsKey` sırasıyla her fiyat (`kitap|market|sonuç|evre=repr`),
    ad sırasıyla her istatistik (`ad=değer`); sekmeyle. `source_line` girmez: dosyadaki yer
    içerik değildir, kaynak araya satır eklese eski maçların özeti değişmemeli."""
    where = f"{match.league} {match.date} satır {match.source_line}"
    if match.kickoff is not None and match.kickoff.utcoffset() is None:
        raise ValueError(f"{where}: başlama saati saat dilimsiz — özet makineye bağlı olurdu")
    kickoff = "" if match.kickoff is None else match.kickoff.astimezone(UTC).isoformat()
    fields = (
        match.league,
        match.season,
        match.date.isoformat(),
        kickoff,
        match.home,
        match.away,
        str(match.home_goals),
        str(match.away_goals),
        match.result,
        *(
            f"{key.book}|{key.market}|{key.outcome}|{key.phase}={match.odds[key]!r}"
            for key in sorted(match.odds)
        ),
        *(f"{name}={value}" for name, value in sorted(match.stats.items())),
    )
    if any(separator in value for value in fields for separator in _SEPARATORS):
        raise ValueError(f"{where}: bir değer ayraç içeriyor — kanonik satır belirsizleşirdi")
    return "\t".join(fields)


def digest(matches: Sequence[HistMatch]) -> Digest:
    """Sıradan bağımsız özet: kanonik satırlar SIRALANIP `\\n` ile birleştirilir."""
    lines = sorted(canonical_line(match) for match in matches)
    complete = sum(
        1 for match in matches if match.prices(_REFERENCE_BOOK, H2H, CLOSING) is not None
    )
    return Digest(
        rows=len(lines),
        sha256=hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest(),
        avgc_complete=complete,
    )


def build_lock(
    matches_by_league: Mapping[str, Sequence[HistMatch]], *, locked_at: date
) -> HistoryLock:
    return HistoryLock(
        canonical_version=CANONICAL_VERSION,
        locked_at=locked_at,
        dev_end=DEV_END,
        holdout_end=HOLDOUT_END,
        leagues=MappingProxyType(
            {code: _period_digests(matches) for code, matches in sorted(matches_by_league.items())}
        ),
    )


def _period_digests(matches: Sequence[HistMatch]) -> Mapping[str, Digest]:
    """Dönem üyeliği kaynağın tarihiyle; holdout satırları bu fonksiyondan dışarı çıkmaz."""
    return MappingProxyType(
        {
            period: digest([match for match in matches if period_of(match.date) == period])
            for period in _LOCKED_PERIODS
        }
    )


def dump_lock(lock: HistoryLock) -> str:
    """Belirlenimci YAML: sabit anahtar sırası, sıralı lig kodları, başlık yorumu."""
    head = (
        *_HEADER,
        f"canonical_version: {lock.canonical_version}",
        f"locked_at: {lock.locked_at.isoformat()}",
        f"dev_end: {lock.dev_end.isoformat()}",
        f"holdout_end: {lock.holdout_end.isoformat()}",
        "leagues:" if lock.leagues else "leagues: {}",
    )
    body = tuple(
        line for code in sorted(lock.leagues) for line in _league_lines(code, lock.leagues[code])
    )
    return "\n".join((*head, *body)) + "\n"


def _league_lines(code: str, periods: Mapping[str, Digest]) -> tuple[str, ...]:
    return (
        f"  {code}:",
        *(
            line
            for period in _LOCKED_PERIODS
            for line in (
                f"    {period}:",
                f"      rows: {periods[period].rows}",
                f"      sha256: {periods[period].sha256}",
                f"      avgc_complete: {periods[period].avgc_complete}",
            )
        ),
    )


def load_lock(path: Path) -> HistoryLock:
    """Yapıyı, 64 haneli özetleri ve `canonical_version`ı doğrular. Her yapı ve biçim hatası tek
    farklı bir `LockViolation`dır (R99): kilidi okuyan CLI'lar veri farkındaki çıkışı (9) verir."""
    root = _fields(_read(path), _ROOT_KEYS, str(path))
    version = root["canonical_version"]
    if type(version) is not int or version != CANONICAL_VERSION:
        raise LockViolation(
            f"{path}: canonical_version {version!r}, kod {CANONICAL_VERSION} bekliyor — kilit "
            "başka bir kanonik biçimle üretilmiş, yeniden üretilmeli"
        )
    return HistoryLock(
        canonical_version=version,
        locked_at=_day(root["locked_at"], f"{path}: locked_at"),
        dev_end=_day(root["dev_end"], f"{path}: dev_end"),
        holdout_end=_day(root["holdout_end"], f"{path}: holdout_end"),
        leagues=_leagues(root["leagues"], f"{path}: leagues"),
    )


def _read(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        # Hata metni çok satırlı olabilir; farklar satır başına bir tanedir.
        reason = " ".join(str(error).split())
        raise LockViolation(f"{path}: kilit dosyası okunamıyor ({reason})") from error


def _fields(raw: object, keys: frozenset[str], where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise LockViolation(f"{where}: eşleme bekleniyordu, {type(raw).__name__} geldi")
    missing = sorted(keys - raw.keys())
    unknown = sorted(str(key) for key in raw.keys() - keys)
    if missing or unknown:
        raise LockViolation(f"{where}: eksik alan {missing}, bilinmeyen alan {unknown}")
    return raw


def _leagues(raw: object, where: str) -> Mapping[str, Mapping[str, Digest]]:
    if not isinstance(raw, dict):
        raise LockViolation(f"{where}: lig kodu → dönem eşlemesi bekleniyordu")
    codes = tuple(raw)
    if not all(isinstance(code, str) and code for code in codes):
        raise LockViolation(f"{where}: lig kodları boş olmayan metin olmalı: {codes!r}")
    return MappingProxyType(
        {code: _periods(raw[code], f"{where}.{code}") for code in sorted(codes)}
    )


def _periods(raw: object, where: str) -> Mapping[str, Digest]:
    fields = _fields(raw, frozenset(_LOCKED_PERIODS), where)
    return MappingProxyType(
        {period: _digest_entry(fields[period], f"{where}.{period}") for period in _LOCKED_PERIODS}
    )


def _digest_entry(raw: object, where: str) -> Digest:
    fields = _fields(raw, _DIGEST_KEYS, where)
    rows = _count(fields["rows"], f"{where}.rows")
    complete = _count(fields["avgc_complete"], f"{where}.avgc_complete")
    sha = fields["sha256"]
    if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
        raise LockViolation(f"{where}.sha256: 64 küçük harfli onaltılık karakter olmalı")
    if complete > rows:
        raise LockViolation(f"{where}: avgc_complete ({complete}) satır sayısını ({rows}) aşamaz")
    return Digest(rows=rows, sha256=sha, avgc_complete=complete)


def _count(value: object, where: str) -> int:
    # `bool` bir `int` alt sınıfıdır: `rows: true` sayı yerine geçmesin.
    if type(value) is int and value >= 0:
        return value
    raise LockViolation(f"{where}: negatif olmayan tam sayı olmalı: {value!r}")


def _day(value: object, where: str) -> date:
    # `datetime` bir `date` alt sınıfıdır: saatli bir değer tarih yerine geçmesin.
    if type(value) is date:
        return value
    raise LockViolation(f"{where}: YYYY-AA-GG tarihi olmalı: {value!r}")


def verify_lock(lock: HistoryLock, matches_by_league: Mapping[str, Sequence[HistMatch]]) -> None:
    """Kilitli dönemleri veriden yeniden hesaplar; farkların HEPSİ tek `LockViolation`da: kod
    sabitlerinden farklı dönem sınırı ya da sürüm, özeti değişen (lig, dönem), kilitte olmayan lig,
    veride olmayan kilitli lig."""
    codes = sorted(set(lock.leagues) | set(matches_by_league))
    differences = (
        *_header_differences(lock),
        *(
            difference
            for code in codes
            for difference in _league_differences(
                code, lock.leagues.get(code), matches_by_league.get(code)
            )
        ),
    )
    if differences:
        raise LockViolation(*differences)


def _header_differences(lock: HistoryLock) -> tuple[str, ...]:
    pairs: tuple[tuple[str, object, object], ...] = (
        ("canonical_version", lock.canonical_version, CANONICAL_VERSION),
        ("dev_end", lock.dev_end, DEV_END),
        ("holdout_end", lock.holdout_end, HOLDOUT_END),
    )
    return tuple(
        f"{name}: kilit {locked}, kod {code}" for name, locked, code in pairs if locked != code
    )


def _league_differences(
    code: str, locked: Mapping[str, Digest] | None, matches: Sequence[HistMatch] | None
) -> tuple[str, ...]:
    if locked is None:
        return (f"{code}: veride var, kilitte yok",)
    if matches is None:
        return (f"{code}: kilitte var, veride yok",)
    actual = _period_digests(matches)
    return tuple(
        f"{code}/{period}: beklenen {_described(locked.get(period))} · "
        f"gerçek {_described(actual[period])}"
        for period in _LOCKED_PERIODS
        if locked.get(period) != actual[period]
    )


def _described(value: Digest | None) -> str:
    if value is None:
        return "yok"
    return f"rows={value.rows} sha256={value.sha256} avgc_complete={value.avgc_complete}"
```

- [ ] **Step 8: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_history_lock.py tests/test_holdout.py tests/test_holdout_access_rule.py -q`
Expected: PASS (131 passed)

Run: `uv run pytest tests/test_history_lock.py tests/test_holdout.py tests/test_holdout_access_rule.py -q -m "not leakage"`
Expected: `131 deselected`, çıkış kodu 5 — işaretsiz test yok.

Run: `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`
Expected: `All checks passed!` · `… files already formatted` · `Success: no issues found`

- [ ] **Step 9: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır)

| # | Mutasyon (dosya: ne değişir) | Kırmızı olması gereken test |
|---|---|---|
| 1 | `holdout.py` `period_of`: `match_date < DEV_END` → `<=` (2025-07-01 geliştirmeye kayar) | `test_period_follows_the_source_date_at_every_boundary[day2-holdout]` |
| 2 | `holdout.py` `period_of`: `match_date < HOLDOUT_END` → `<=` (2026-07-01 holdout'a kayar) | `test_period_follows_the_source_date_at_every_boundary[day4-post]` |
| 3 | `holdout.py`: `DEV_END = date(2025, 7, 2)` | `test_period_constants_are_the_approved_boundaries`, `test_period_follows_the_source_date_at_every_boundary[day2-holdout]` |
| 4 | `holdout.py` `in_window`: `match.date < window.end` → `<=` | `test_main_window_is_half_open_from_2019_07_01_to_dev_end[day3-False]`, `test_extra_window_has_no_lower_bound_and_stops_at_dev_end`, `test_no_constructible_window_returns_a_holdout_or_later_match` |
| 5 | `holdout.py` `Window.__post_init__`: `end > DEV_END` denetimi (iki satır) silinir (R89) | `test_window_reaching_past_dev_end_is_rejected` (3'ü de), `test_no_constructible_window_returns_a_holdout_or_later_match` |
| 6 | `holdout.py` `Window.__post_init__`: `self.end > DEV_END` → `self.end > HOLDOUT_END` | `test_window_reaching_past_dev_end_is_rejected` (3'ü de), `test_no_constructible_window_returns_a_holdout_or_later_match` |
| 7 | `holdout.py` `Window.__post_init__`: `start >= end` denetimi (iki satır) silinir (R89) | `test_window_with_start_not_before_end_is_rejected[empty]`, `[reversed]` |
| 8 | `holdout.py` `select_periods`: `(key is None or key._seal is not _HOLDOUT_SEAL)` → `key is None` (mühür yok sayılır) | `test_hand_built_key_does_not_open_the_holdout[no-seal]`, `[foreign-seal]` |
| 9 | `holdout.py` `select_periods`: `HOLDOUT in periods` → `periods == {HOLDOUT}` | `test_holdout_without_a_key_is_locked[dev+holdout]`, `[holdout+post]` |
| 10 | `holdout.py` `select_periods`: `period_of(match.date)` → `period_of(match.kickoff.date() if match.kickoff else match.date)` | `test_dev_selection_uses_the_source_date_not_the_kickoff`, `test_key_from_open_holdout_opens_the_holdout_by_source_date` |
| 11 | `holdout.py` `open_holdout`: `conn.commit()` satırının yerine `return HoldoutKey(opened_at=now, purpose=purpose, git_sha=git_sha, _seal=_HOLDOUT_SEAL)` (anahtar commit'ten önce döner) | `test_open_holdout_commits_one_access_row_before_returning_the_key` |
| 12 | `holdout.py` `open_holdout`: `except` bloğundaki `raise` silinir (hata yutulur, anahtar döner) | `test_open_holdout_returns_no_key_when_the_insert_fails`, `test_open_holdout_returns_no_key_when_the_commit_fails` |
| 13 | `holdout.py` `open_holdout`: değerler f-string ile SQL metnine gömülür, parametre verilmez | `test_open_holdout_passes_values_as_query_parameters` |
| 14 | `holdout.py` `_check_opening`: `_GIT_SHA.fullmatch(git_sha)` → `re.match(r"^[0-9a-f]{40}$", git_sha)` | `test_open_holdout_rejects_bad_openings_before_writing[newline]` |
| 15 | `0007`: satır tetikleyicisinin üç satırı `--` ile yoruma alınır | `test_access_log_migration_is_append_only_with_the_ledger_trigger` |
| 16 | `0007`: `opened_at` sütunu `opened` olur | `test_access_log_migration_defines_checked_columns`, `test_open_holdout_writes_exactly_the_migration_columns` |
| 17 | `0007`: `before truncate` tetikleyicisinin üç satırı silinir (R90) | `test_access_log_migration_blocks_truncate` |
| 18 | `0007`: `alter table holdout_access_log enable row level security;` silinir (R90) | `test_access_log_migration_closes_the_table_to_api_roles` |
| 19 | `0007`: `create policy anon_insert on holdout_access_log for insert to anon with check (true);` eklenir | `test_access_log_migration_closes_the_table_to_api_roles` |
| 20 | `lock.py` `canonical_line`: oranları üreten `*( … for key in sorted(match.odds))` parçası silinir | `test_canonical_line_is_exactly_the_documented_layout`, `test_canonical_line_changes_when_any_locked_value_changes[price]`, `[odds-key]` |
| 21 | `lock.py` `canonical_line`: istatistikleri üreten `*( … sorted(match.stats.items()))` parçası silinir | `test_canonical_line_is_exactly_the_documented_layout`, `test_canonical_line_changes_when_any_locked_value_changes[stat-value]`, `[stat-key]` |
| 22 | `lock.py` `canonical_line`: `match.result,`tan sonra `str(match.source_line),` eklenir | `test_canonical_line_ignores_the_source_line` |
| 23 | `lock.py` `canonical_line`: `.astimezone(UTC)` kaldırılır | `test_canonical_line_writes_the_kickoff_in_utc` |
| 24 | `lock.py` `digest`: `sorted(canonical_line(match) for match in matches)` → `[canonical_line(match) for match in matches]` | `test_digest_is_sha256_of_the_sorted_newline_joined_lines`, `test_digest_ignores_match_order`, `test_verify_lock_accepts_unchanged_data_in_any_order_and_new_post_rows` |
| 25 | `lock.py` `digest`: `prices(_REFERENCE_BOOK, H2H, CLOSING)` → `prices(_REFERENCE_BOOK, H2H, "pre")` | `test_digest_counts_rows_and_complete_avgc_1x2` |
| 26 | `lock.py` `_period_digests`: `period_of(match.date)` → `period_of(match.kickoff.date() if match.kickoff else match.date)` | `test_build_lock_splits_by_source_date_and_leaves_post_out` |
| 27 | `lock.py` `_period_digests`: `period_of(match.date) == period` → `period_of(match.date) in (period, "post")` | `test_build_lock_splits_by_source_date_and_leaves_post_out`, `test_verify_lock_accepts_unchanged_data_in_any_order_and_new_post_rows` |
| 28 | `lock.py` `dump_lock`: `sorted(lock.leagues)` → `lock.leagues` | `test_dump_lock_writes_the_documented_text` |
| 29 | `lock.py`: `_SHA256` deseninde `{64}` → `{63,64}` | `test_load_lock_rejects_malformed_files[short-sha]` |
| 30 | `lock.py` `load_lock`: sürüm koşulu `if False:` | `test_load_lock_rejects_malformed_files[version]`, `[version-bool]` |
| 31 | `lock.py` `load_lock`: sürüm uyuşmazlığında `raise LockViolation(` → `raise ValueError(` (R99) | `test_load_lock_rejects_malformed_files[version]`, `[version-bool]` |
| 32 | `lock.py` `_fields`: `eksik alan …` hatasında `LockViolation` → `ValueError` (R99) | `test_load_lock_rejects_malformed_files[unknown-period]`, `[unknown-key]`, `[missing-key]` |
| 33 | `lock.py` `_read`: `except (UnicodeDecodeError, yaml.YAMLError)` → `except UnicodeDecodeError` (bozuk YAML yakalanmaz) | `test_load_lock_rejects_malformed_files[broken-yaml]` |
| 34 | `lock.py` `_read`: `except (UnicodeDecodeError, yaml.YAMLError)` → `except yaml.YAMLError` (UTF-8 olmayan dosya yakalanmaz) | `test_load_lock_reports_an_undecodable_file_as_a_violation` |
| 35 | `lock.py` `_league_differences`: `for period in _LOCKED_PERIODS` → `for period in (DEV,)` (holdout atlanır) | `test_verify_lock_reports_a_corrected_score_in_each_locked_period[holdout]`, `test_verify_lock_reports_a_period_missing_from_the_lock` |
| 36 | `lock.py` `_league_differences`: `veride var, kilitte yok` dönüşü → `return ()` | `test_verify_lock_reports_a_league_absent_from_the_lock`, `test_verify_lock_lists_every_difference_in_one_violation` |
| 37 | `lock.py` `_league_differences`: `kilitte var, veride yok` dönüşü → `return ()` | `test_verify_lock_reports_a_locked_league_missing_from_the_data`, `test_verify_lock_lists_every_difference_in_one_violation` |
| 38 | `lock.py` `verify_lock`: `*_header_differences(lock),` satırı silinir | `test_verify_lock_reports_moved_boundaries_and_a_foreign_version`, `test_verify_lock_lists_every_difference_in_one_violation` |
| 39 | `lock.py` `verify_lock`: `LockViolation(*differences)` → `LockViolation(differences[0])` | `test_verify_lock_lists_every_difference_in_one_violation` |
| 40 | `test_holdout_access_rule.py` `rule_violations`: `if path not in GUARDED[name][0]` → `if False` (her dosya serbest) | `test_detector_sees_every_reference_form_once` (13'ü de), `test_allow_list_matches_the_exact_path_not_the_file_name` (5'i de), `test_violations_name_path_line_and_reason`, `test_tree_scan_walks_both_roots_recursively`, `test_detector_sees_the_seal_in_the_real_holdout_module` |
| 41 | aynı satır: `if Path(path).name not in {Path(item).name for item in GUARDED[name][0]}` (tam yol yerine dosya adı) | `test_allow_list_matches_the_exact_path_not_the_file_name` (5'i de) |
| 42 | `test_holdout_access_rule.py` `_python_files`: `rglob("*.py")` → `glob("*.py")` | `test_tree_scan_walks_both_roots_recursively`, `test_scan_reaches_the_known_sources` |
| 43 | `test_holdout_access_rule.py` `GUARDED`: `"_load_all": (…)` girdisi silinir (R96) | `test_detector_sees_every_reference_form_once[from football_edge.history.sync import _load_all]`, `[rows = sync._load_all(conn, catalog)]`, `[_load_all(conn, catalog)]`, `test_allow_list_matches_the_exact_path_not_the_file_name[_load_all(conn, catalog)-src/football_edge/backtest/sync.py]` |
| 44 | depoya ihlal: `lock.py`nin import'larına `from football_edge.history.holdout import open_holdout` eklenir | `test_holdout_is_opened_only_where_allowed` |
| 45 | depoya ihlal: `scripts/ops_alert.py`nin `if __name__ == "__main__":` satırından önce `from football_edge.history.sync import _load_all` eklenir (R96) | `test_holdout_is_opened_only_where_allowed` |

Her mutasyondan sonra dosya geri alınır ve üç dosya yine `131 passed` verir. Plan yazılırken tablonun
her satırı, Task 0 kodu eklenmiş bir `git archive` kopyasında (main `c3aedaa`) betikle ölçüldü:
45/45 kırmızı, her geri yüklemeden sonra yeşil.

- [ ] **Step 10: Commit**

```bash
git add src/football_edge/history/holdout.py src/football_edge/history/lock.py \
  db/migrations/0007_holdout.sql tests/test_holdout.py tests/test_holdout_access_rule.py \
  tests/test_history_lock.py
git commit -m "feat: Faz 2 dönemleri, holdout anahtarı ve tarihsel taban kilidi (0007)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 11: Kapının tamamı**

Run: `TMPDIR=$(mktemp -d) ./verify.sh` — log DOSYASINDAN oku.
Expected: 9 adım PASS + `SKIP: zincir (DATABASE_URL yok)`. `pytest` adımı bu görevin 131 testini
içerir; `test_access_method_rule.py` (R77) yeni modüllerde yasak araç bulmaz.

---

### Task 4: Backtest harness iskeleti — zaman kuralları, olay akışı, bağlam/sonuç ayrımı, taban stratejiler (T2a)

**Kademe:** K1 · **Dalga:** 1 · **Worktree/dal:** `.worktrees/wt-harness` · `feat/faz2-harness`

**Files:**
- Create: `src/football_edge/backtest/timeline.py` — karar anı, sonucun bilindiği an (D4, D5)
- Create: `src/football_edge/backtest/events.py` — olay tipi, sıralı olay akışı
- Create: `src/football_edge/backtest/harness.py` — bağlam/sonuç tipleri, `Strategy`, `replay`
- Create: `src/football_edge/backtest/strategies.py` — `MarketPre`, `EloPointInTime`, `Placebo`
- Create: `tests/backtest_builders.py` — sentetik `HistMatch` kurucuları (Task 10 de kullanır)
- Test: `tests/test_timeline.py`, `tests/test_events.py`, `tests/test_harness.py`, `tests/test_strategies.py`

Dokunulmaz: `football_edge.market` (Task 2 aynı dalgada yazıyor — vig temizleme ENJEKTE edilir,
import edilmez), `src/football_edge/elo.py` (yalnız kullanılır), ortak dosyalar (`pyproject.toml`,
`uv.lock`, `verify.sh`).

**Interfaces:**
- Consumes:
  - Task 0 — `football_edge.history.types`: `PRE_CLOSING = "pre"`, `CLOSING = "close"`, `H2H = "1x2"`,
    `TOTALS_25 = "ou25"`, `MARKET_OUTCOMES: Mapping[str, tuple[str, ...]]`, `RESULTS = ("H", "D", "A")`,
    `OddsKey(book, market, outcome, phase)` (`frozen=True, order=True`), `HistMatch(league, season,
    date, kickoff, home, away, home_goals, away_goals, result, odds, stats, source_line)`;
    boş `src/football_edge/backtest/__init__.py`; `pyproject.toml`da kayıtlı `leakage` işareti.
  - Mevcut kod — `football_edge.elo`: `EloConfig(k=20.0, home_advantage=65.0, initial=1500.0,
    goal_scaling=True)`, `expected_home(home_rating: float, away_rating: float, config: EloConfig)
    -> float`, `updated(home_rating: float, away_rating: float, home_goals: int, away_goals: int,
    config: EloConfig) -> tuple[float, float]`.
- Produces (sözleşme, birebir — plan başıyla aynı; R94 `EloPointInTime`, R98 `DecisionContext`):
```python
# football_edge/backtest/timeline.py
LONDON: ZoneInfo                    # ZoneInfo("Europe/London")
RESULT_LAG: timedelta               # 3 saat
DECISION_HOUR: int                  # 12
def decision_at(match_date: date, kickoff: datetime | None) -> datetime | None   # UTC; karar ≥ başlama → None
def result_known_at(match_date: date, kickoff: datetime | None) -> datetime       # UTC

# football_edge/backtest/events.py
DECISION: int = 0; RESULT: int = 1           # eşzamanlıda karar önce
@dataclass(frozen=True, order=True)
class Event:
    at: datetime; kind: int; match_index: int
def build_events(matches: Sequence[HistMatch]) -> tuple[Event, ...]

# football_edge/backtest/harness.py
class LeakageError(RuntimeError): ...
@dataclass(frozen=True)
class ResultRecord:
    league: str; date: date; home: str; away: str; home_goals: int; away_goals: int; known_at: datetime
@dataclass(frozen=True)
class DecisionContext:                       # kapanış ve sonuç alanı YOK; durum görüntüsü de yok — durum stratejide, observe() ile (R98)
    match_index: int; league: str; season: str; date: date; home: str; away: str
    decision_at: datetime
    pre_prices: Mapping[OddsKey, float]      # yalnız PRE_CLOSING anahtarları
@dataclass(frozen=True)
class Outcome:
    match_index: int; result: str; home_goals: int; away_goals: int
    closing: Mapping[OddsKey, float]         # yalnız CLOSING anahtarları
@dataclass(frozen=True)
class Bet:
    outcome: str; price: float; book: str
@dataclass(frozen=True)
class Prediction:
    match_index: int; strategy: str; probs: tuple[float, float, float]; bet: Bet | None = None
class Strategy(Protocol):
    @property
    def name(self) -> str: ...
    def observe(self, result: ResultRecord) -> Strategy: ...        # yeni strateji değeri döner
    def predict(self, context: DecisionContext) -> Prediction | None: ...
@dataclass(frozen=True)
class ReplayResult:
    strategy: str
    predictions: tuple[Prediction, ...]
    outcomes: Mapping[int, Outcome]          # yalnız tahmin edilen maçlar; döngü BİTTİKTEN sonra kurulur
    no_decision: int; no_prediction: int
def replay(matches: Sequence[HistMatch], strategy: Strategy) -> ReplayResult

# football_edge/backtest/strategies.py
Devig = Callable[[Sequence[float]], tuple[float, ...]]
@dataclass(frozen=True)
class MarketPre:            # name "market_pre"; book="Avg"; devig enjekte edilir
    devig: Devig; book: str = "Avg"
@dataclass(frozen=True)
class EloPointInTime:       # name "elo"; ratings MappingProxyType; draw_rate=0.26
    config: EloConfig = EloConfig(); draw_rate: float = 0.26
    groups: Mapping[str, str] = …   # R94: lig kodu → reyting grubu (ülke); eşlenmeyen lig kendi kodu
    ratings: Mapping[tuple[str, str], float] = …   # (grup, takım) — yalın ad ülkeler arası kimlik değildir
@dataclass(frozen=True)
class Placebo:              # name "placebo"; tohumlu rastgele sonuç, `book` kapanış öncesi fiyatından bahis
    devig: Devig; seed: int = 20260922; book: str = "Avg"
```
- Ek (sözleşme dışı): `harness._walk(matches, events, strategy) -> tuple[tuple[Prediction, ...], int]`
  (modül-içi olay döngüsü; bir test ona bilerek yanlış sıralı olay verir ve `LeakageError` görür);
  `tests/backtest_builders.py`: `quote(book, phase, values, *, market=H2H) -> dict[OddsKey, float]`,
  `hist_match(*, day, kickoff=None, league="E0", season="2324", home="Alfa", away="Beta",
  goals=(1, 0), odds=None, line=1) -> HistMatch`.

**Bu görevin kararları (hepsini testler sabitler):**
- Karar günü: `w = match_date.weekday()` (pazartesi 0). Salı–perşembe `w − 1`, cuma–pazartesi
  `(w − 4) % 7` gün geri; saat 12:00 Europe/London, UTC'ye çevrilir. Ofset KARAR GÜNÜNÜN kuralından
  gelir: yaz saati geçişi karar günüyle maç günü arasına düşebilir.
- Başlama biliniyor ve karar ≥ başlama → `None` (eşitlik dahil: cuma 12:00 BST başlayan maçın kararı
  yok). Saatsiz maçın kararı her zaman vardır.
- Sonuç: başlama + 3 sa; saat yoksa ertesi gün 03:00 Europe/London. İki fonksiyonun döndürdüğü an
  `tzinfo is UTC`. Saat dilimsiz başlama `ValueError` verir — sessizce yerel saat sayılmaz.
- `Event(at, kind, match_index)` alan sırası sıralamanın kendisidir: aynı anda `DECISION (0)`,
  `RESULT (1)`den önce; sonra maç sırası.
- `_walk` görülen sonuçların EN GEÇ anını (`max`) tutar, sonuncusunu değil; karar anı ≤ o an →
  `LeakageError`. Strateji başka bir maç için tahmin dönerse `ValueError` (değerlendirme o tahmini
  yanlış maçın sonucuyla eşlerdi).
- `DecisionContext` durum görüntüsü (`results_before`, reytingler) TAŞIMAZ (R98): durum stratejinin
  içindedir (`observe` yeni değer döner), zamanı harness yönetir — sızıntı açısından eşdeğer; Faz 3'ün
  eşitlik testi bağlamı VE `observe` akışını karşılaştırır (tasarım §7.2 metnini controller düzeltir).
- `DecisionContext.pre_prices` maçın BÜTÜN `PRE_CLOSING` anahtarları (1X2 ve Ü/A), `Outcome.closing`
  bütün `CLOSING` anahtarları; ikisi de `MappingProxyType`. `ReplayResult.outcomes` döngü bittikten
  SONRA, yalnız tahmin edilen maçlar için kurulur.
- Stratejiler vig temizleyicinin `ValueError`ını (Task 2'nin `InvalidPrices`ı onun alt sınıfı) ve eksik
  kapanış öncesi fiyatı "tahmin yok" sayar (`no_prediction`). Bir kapanış fiyatı kapanış öncesi eksiği
  TAMAMLAYAMAZ: anahtarlar evreyle birlikte aranır.
- `EloPointInTime` reytingleri `(grup, takım)` ile tutar (R94): grup = `groups.get(lig, lig)`, `groups`
  lig kodu → ülke (varsayılan boş: her lig kendi grubu). Ham takım adı ülkeler arasında kimlik
  değildir (sessiz birleştirme); lig kodu anahtarı ise terfi/küme düşmede reytingi sıfırlardı. Aynı
  grubun ligleri arasında reyting taşınır; hiç görülmemiş `(grup, takım)` `config.initial`dan başlar.
  `groups = MappingProxyType({})` varsayılanını Python 3.11 dataclass'ı reddeder ("mutable default"):
  aynı anlam `field(default_factory=…)` ile.
- `Placebo`nun seçimi `random.Random(seed * 1_000_003 + match_index).choice(RESULTS)`: maç başına
  tohum — bir maçın seçimi başka maçların karar alıp almamasından bağımsızdır.

- [ ] **Step 1: Sentetik kurucuları ve zaman/olay testlerini yaz**

Create `tests/backtest_builders.py`:
```python
"""Backtest testlerinin SENTETİK maç kurucuları.

Takım adları uydurma, fiyatlar elle seçilmiş: gerçek bir maç, takım ya da oran satırı yok
(spec §3.2/4). Yalnız anahtar biçimi (`OddsKey`) football-data'nın sütun düzenini izler.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from types import MappingProxyType

from football_edge.history.types import H2H, MARKET_OUTCOMES, HistMatch, OddsKey


def quote(
    book: str, phase: str, values: Sequence[float], *, market: str = H2H
) -> dict[OddsKey, float]:
    """Bir kitabın bir evredeki fiyatları, `MARKET_OUTCOMES[market]` sırasıyla."""
    outcomes = MARKET_OUTCOMES[market]
    return {
        OddsKey(book=book, market=market, outcome=outcome, phase=phase): value
        for outcome, value in zip(outcomes, values, strict=True)
    }


def hist_match(
    *,
    day: date,
    kickoff: datetime | None = None,
    league: str = "E0",
    season: str = "2324",
    home: str = "Alfa",
    away: str = "Beta",
    goals: tuple[int, int] = (1, 0),
    odds: Mapping[OddsKey, float] | None = None,
    line: int = 1,
) -> HistMatch:
    home_goals, away_goals = goals
    result = "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D"
    return HistMatch(
        league=league,
        season=season,
        date=day,
        kickoff=kickoff,
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        result=result,
        odds=MappingProxyType(dict(odds or {})),
        stats=MappingProxyType({}),
        source_line=line,
    )
```

Create `tests/test_timeline.py`:
```python
"""Zaman semantiği: karar anı ve sonucun bilindiği an (tasarım §4.5, D4, D5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest

from football_edge.backtest.timeline import (
    DECISION_HOUR,
    LONDON,
    RESULT_LAG,
    decision_at,
    result_known_at,
)

pytestmark = pytest.mark.leakage


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_constants_pin_london_noon_and_a_three_hour_lag() -> None:
    assert LONDON.key == "Europe/London"
    assert DECISION_HOUR == 12
    assert timedelta(hours=3) == RESULT_LAG


@pytest.mark.parametrize(
    ("match_date", "decided"),
    [
        (date(2024, 8, 5), _utc(2024, 8, 2, 11)),  # pazartesi → önceki cuma
        (date(2024, 8, 6), _utc(2024, 8, 6, 11)),  # salı → aynı gün
        (date(2024, 8, 7), _utc(2024, 8, 6, 11)),  # çarşamba → salı
        (date(2024, 8, 8), _utc(2024, 8, 6, 11)),  # perşembe → salı
        (date(2024, 8, 9), _utc(2024, 8, 9, 11)),  # cuma → aynı gün
        (date(2024, 8, 10), _utc(2024, 8, 9, 11)),  # cumartesi → cuma
        (date(2024, 8, 11), _utc(2024, 8, 9, 11)),  # pazar → cuma
    ],
    ids=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
)
def test_every_weekday_maps_to_friday_or_tuesday_noon_london_in_summer(
    match_date: date, decided: datetime
) -> None:
    assert decision_at(match_date, None) == decided


@pytest.mark.parametrize(
    ("match_date", "decided"),
    [
        (date(2024, 1, 15), _utc(2024, 1, 12, 12)),  # pazartesi → cuma
        (date(2024, 1, 17), _utc(2024, 1, 16, 12)),  # çarşamba → salı
        (date(2024, 1, 20), _utc(2024, 1, 19, 12)),  # cumartesi → cuma
    ],
    ids=["mon", "wed", "sat"],
)
def test_decision_is_noon_london_in_winter_too(match_date: date, decided: datetime) -> None:
    assert decision_at(match_date, None) == decided


@pytest.mark.parametrize(
    ("match_date", "decided"),
    [
        (date(2024, 3, 31), _utc(2024, 3, 29, 12)),  # yaz saatine geçilen pazar; karar günü kışta
        (date(2024, 4, 1), _utc(2024, 3, 29, 12)),  # maç günü yazda, karar günü kışta
        (date(2024, 10, 28), _utc(2024, 10, 25, 11)),  # maç günü kışta, karar günü yazda
    ],
    ids=["spring-sunday", "spring-monday", "autumn-monday"],
)
def test_the_offset_comes_from_the_decision_day_across_a_clock_change(
    match_date: date, decided: datetime
) -> None:
    assert decision_at(match_date, None) == decided


@pytest.mark.parametrize(
    ("kickoff", "decided"),
    [
        (_utc(2024, 8, 9, 10, 30), None),  # cuma 11:30 BST: kararın önünde
        (_utc(2024, 8, 9, 11), None),  # tam 12:00 BST: eşitlikte karar yok
        (_utc(2024, 8, 9, 11, 1), _utc(2024, 8, 9, 11)),  # 12:01 BST
        (_utc(2024, 8, 9, 18, 45), _utc(2024, 8, 9, 11)),
    ],
    ids=["before", "equal", "one-minute-after", "evening"],
)
def test_a_friday_match_has_a_decision_only_when_it_kicks_off_after_noon(
    kickoff: datetime, decided: datetime | None
) -> None:
    assert decision_at(date(2024, 8, 9), kickoff) == decided


def test_a_tuesday_noon_kickoff_in_winter_has_no_decision() -> None:
    assert decision_at(date(2024, 1, 16), _utc(2024, 1, 16, 12)) is None
    assert decision_at(date(2024, 1, 16), _utc(2024, 1, 16, 12, 1)) == _utc(2024, 1, 16, 12)


def test_without_a_kickoff_every_day_of_a_year_decides_on_the_last_tuesday_or_friday() -> None:
    for offset in range(366):
        day = date(2024, 1, 1) + timedelta(days=offset)
        decided = decision_at(day, None)
        assert decided is not None, day
        local = decided.astimezone(LONDON)
        assert (local.hour, local.minute) == (DECISION_HOUR, 0), day
        assert local.weekday() == (1 if day.weekday() in (1, 2, 3) else 4), day
        assert timedelta(0) <= day - local.date() <= timedelta(days=3), day


def test_a_result_is_known_three_hours_after_a_known_kickoff() -> None:
    assert result_known_at(date(2024, 8, 10), _utc(2024, 8, 10, 14)) == _utc(2024, 8, 10, 17)


@pytest.mark.parametrize(
    ("match_date", "known"),
    [
        (date(2024, 1, 20), _utc(2024, 1, 21, 3)),  # kış
        (date(2024, 8, 10), _utc(2024, 8, 11, 2)),  # yaz
        (date(2024, 3, 30), _utc(2024, 3, 31, 2)),  # ertesi gün yaz saatine geçiliyor
        (date(2024, 10, 26), _utc(2024, 10, 27, 3)),  # ertesi gün kışa dönülüyor
    ],
    ids=["winter", "summer", "spring-forward", "fall-back"],
)
def test_without_a_kickoff_the_result_is_known_next_day_at_three_london(
    match_date: date, known: datetime
) -> None:
    assert result_known_at(match_date, None) == known


def test_both_instants_come_back_in_utc() -> None:
    decided = decision_at(date(2024, 8, 10), None)
    london_kickoff = datetime(2024, 8, 10, 15, tzinfo=LONDON)
    instants = (
        decided,
        result_known_at(date(2024, 8, 10), None),
        result_known_at(date(2024, 8, 10), london_kickoff),
    )
    assert all(instant is not None and instant.tzinfo is UTC for instant in instants)
    assert instants[2] == _utc(2024, 8, 10, 17)


@pytest.mark.parametrize("function", [decision_at, result_known_at], ids=["decision", "result"])
def test_a_naive_kickoff_is_refused(function: Callable[[date, datetime | None], object]) -> None:
    with pytest.raises(ValueError, match="saat dilimsiz"):
        function(date(2024, 8, 10), datetime(2024, 8, 10, 14))


def test_every_decision_precedes_its_kickoff_and_every_result_follows_it() -> None:
    start = _utc(2024, 3, 25, 0)  # yaz saati geçişini kapsayan iki hafta
    for hours in range(0, 24 * 14, 5):
        kickoff = start + timedelta(hours=hours)
        match_date = kickoff.astimezone(LONDON).date()
        decided = decision_at(match_date, kickoff)
        assert decided is None or decided < kickoff, kickoff
        assert result_known_at(match_date, kickoff) > kickoff, kickoff
```

Create `tests/test_events.py`:
```python
"""Olay akışı: her maçın bir sonucu, varsa bir kararı; aynı anda karar önce."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from football_edge.backtest.events import DECISION, RESULT, Event, build_events
from football_edge.backtest.timeline import decision_at, result_known_at
from football_edge.history.types import HistMatch
from tests.backtest_builders import hist_match

pytestmark = pytest.mark.leakage

FRIDAY_NOON_BST = datetime(2024, 8, 9, 11, tzinfo=UTC)


def _matches() -> tuple[HistMatch, ...]:
    return (
        # cuma 09:00 BST başlıyor: kararı yok, sonucu tam cuma 12:00 BST'de bilinir
        hist_match(day=date(2024, 8, 9), kickoff=datetime(2024, 8, 9, 8, tzinfo=UTC)),
        # cumartesi maçı: kararı tam da o an (cuma 12:00 BST)
        hist_match(day=date(2024, 8, 10), kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC)),
        # saatsiz çarşamba maçı: karar salı, sonuç perşembe 03:00 Londra
        hist_match(day=date(2024, 8, 7)),
    )


def test_a_decision_sorts_before_a_result_at_the_same_instant() -> None:
    assert DECISION < RESULT
    assert Event(FRIDAY_NOON_BST, DECISION, 9) < Event(FRIDAY_NOON_BST, RESULT, 0)


def test_every_match_gets_one_result_and_a_decision_only_when_it_has_one() -> None:
    events = build_events(_matches())

    assert sorted(event.match_index for event in events if event.kind == RESULT) == [0, 1, 2]
    assert sorted(event.match_index for event in events if event.kind == DECISION) == [1, 2]


def test_event_instants_come_from_the_timeline() -> None:
    matches = _matches()

    for event in build_events(matches):
        match = matches[event.match_index]
        expected = (
            decision_at(match.date, match.kickoff)
            if event.kind == DECISION
            else result_known_at(match.date, match.kickoff)
        )
        assert event.at == expected


def test_events_run_in_time_order_with_the_decision_first_on_a_tie() -> None:
    events = build_events(_matches())

    assert list(events) == sorted(events)
    assert [(event.kind, event.match_index) for event in events] == [
        (DECISION, 2),
        (RESULT, 2),
        (DECISION, 1),  # cuma 12:00 BST — 0. maçın sonucuyla aynı an
        (RESULT, 0),
        (RESULT, 1),
    ]


def test_no_matches_make_no_events() -> None:
    assert build_events(()) == ()
```

- [ ] **Step 2: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_timeline.py tests/test_events.py -q`
Expected: FAIL — `Interrupted: 2 errors during collection`:
`ModuleNotFoundError: No module named 'football_edge.backtest.timeline'` ve
`ModuleNotFoundError: No module named 'football_edge.backtest.events'`

- [ ] **Step 3: Zaman kurallarını ve olay akışını yaz**

Create `src/football_edge/backtest/timeline.py`:
```python
"""Zaman semantiği (tasarım §4.5, D4, D5): sızıntının tamamı buradaki iki kurala bağlıdır.

Kapanış öncesi oranlar hafta sonu maçları için cuma, hafta içi maçları için salı öğleden sonra
toplanır (`notes.txt`); karar anı o öğleden sonranın EN ERKEN anıdır, 12:00 Europe/London. Sonuç
başlamadan 3 saat sonra, saat yoksa ertesi gün 03:00 Europe/London bilinir (tutucu kural).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
DECISION_HOUR = 12
RESULT_LAG = timedelta(hours=3)
_RESULT_HOUR_WITHOUT_KICKOFF = 3
_TUESDAY = 1
_FRIDAY = 4
_MIDWEEK = frozenset({1, 2, 3})  # salı, çarşamba, perşembe


def _decision_day(match_date: date) -> date:
    """Cuma–pazartesi maçı: o gün ya da önceki son cuma; salı–perşembe maçı: son salı."""
    weekday = match_date.weekday()
    back = weekday - _TUESDAY if weekday in _MIDWEEK else (weekday - _FRIDAY) % 7
    return match_date - timedelta(days=back)


def _london(day: date, hour: int) -> datetime:
    # Ofset o GÜNÜN kuralından gelir: yaz saati geçişi karar günüyle maç günü arasına düşebilir.
    return datetime.combine(day, time(hour), tzinfo=LONDON).astimezone(UTC)


def _aware(kickoff: datetime) -> datetime:
    # Saat dilimsiz başlama sessizce yerel saat sayılırdı; HistMatch.kickoff UTC taşır.
    if kickoff.utcoffset() is None:
        raise ValueError(f"başlama anı saat dilimsiz: {kickoff.isoformat()}")
    return kickoff


def decision_at(match_date: date, kickoff: datetime | None) -> datetime | None:
    """Karar anı (UTC). Başlama biliniyor ve karar ondan önce değilse None: maçın kararı yok."""
    instant = _london(_decision_day(match_date), DECISION_HOUR)
    if kickoff is not None and instant >= _aware(kickoff):
        return None
    return instant


def result_known_at(match_date: date, kickoff: datetime | None) -> datetime:
    """Sonucun (ve maç istatistiğinin) bilindiği an (UTC)."""
    if kickoff is not None:
        return (_aware(kickoff) + RESULT_LAG).astimezone(UTC)
    return _london(match_date + timedelta(days=1), _RESULT_HOUR_WITHOUT_KICKOFF)
```

Create `src/football_edge/backtest/events.py`:
```python
"""Olay akışı (tasarım §7.1): karar ve sonuç anları zaman sırasına dizilir.

Aynı andaki olaylarda karar ÖNCE gelir (tutucu): tam karar anında bilinen sonuç o kararda
görülmez. Akış yalnız anları ve maçın sırasını taşır — kapanış oranı ve sonuç akışa girmez.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from football_edge.backtest.timeline import decision_at, result_known_at
from football_edge.history.types import HistMatch

DECISION: int = 0
RESULT: int = 1


@dataclass(frozen=True, order=True)
class Event:
    at: datetime
    kind: int
    match_index: int


def _events_of(index: int, match: HistMatch) -> tuple[Event, ...]:
    result = Event(result_known_at(match.date, match.kickoff), RESULT, index)
    decision = decision_at(match.date, match.kickoff)
    if decision is None:
        return (result,)
    return (Event(decision, DECISION, index), result)


def build_events(matches: Sequence[HistMatch]) -> tuple[Event, ...]:
    """Her maça bir sonuç olayı, kararı olana bir karar olayı; (an, tür, sıra) düzeninde."""
    return tuple(
        sorted(event for index, match in enumerate(matches) for event in _events_of(index, match))
    )
```

- [ ] **Step 4: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_timeline.py tests/test_events.py -q`
Expected: PASS (34 passed) — uyarı yok (`leakage` işareti Task 0'da kayıtlı; `PytestUnknownMarkWarning`
görülürse Task 0 eksiktir, burada düzeltilmez).

- [ ] **Step 5: Harness testlerini yaz**

Create `tests/test_harness.py`:
```python
"""Harness: bağlam/sonuç ayrımı, olay sırası, sızıntı savunması, sayımlar."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import UTC, date, datetime, time, timedelta
from types import MappingProxyType

import pytest

from football_edge.backtest import harness
from football_edge.backtest.events import DECISION, RESULT, Event
from football_edge.backtest.harness import (
    DecisionContext,
    LeakageError,
    Outcome,
    Prediction,
    ResultRecord,
    replay,
)
from football_edge.history.types import CLOSING, PRE_CLOSING, TOTALS_25, HistMatch
from tests.backtest_builders import hist_match, quote

FRIDAY_NOON_BST = datetime(2024, 8, 9, 11, tzinfo=UTC)
FULL_ODDS = {
    **quote("Avg", PRE_CLOSING, (2.6, 3.3, 2.8)),
    **quote("Avg", CLOSING, (1.9, 3.6, 4.2)),
    **quote("PS", CLOSING, (1.8, 3.7, 4.6)),
    **quote("Avg", PRE_CLOSING, (1.9, 1.95), market=TOTALS_25),
    **quote("Avg", CLOSING, (1.8, 2.05), market=TOTALS_25),
}


@dataclass(frozen=True)
class Recorder:
    """Her kararda o ana kadar gördüğü sonuçları ve aldığı bağlamı kaydeder."""

    seen: dict[int, tuple[tuple[str, str], ...]]
    contexts: dict[int, DecisionContext]
    predict_for: frozenset[int] | None = None
    observed: tuple[tuple[str, str], ...] = ()

    @property
    def name(self) -> str:
        return "recorder"

    def observe(self, result: ResultRecord) -> Recorder:
        return replace(self, observed=(*self.observed, (result.home, result.away)))

    def predict(self, context: DecisionContext) -> Prediction | None:
        self.seen[context.match_index] = self.observed
        self.contexts[context.match_index] = context
        if self.predict_for is not None and context.match_index not in self.predict_for:
            return None
        return Prediction(context.match_index, self.name, (0.5, 0.3, 0.2))


@dataclass(frozen=True)
class Counter:
    """Gördüğü sonuç sayısını tahmininin ilk olasılığına yazar."""

    count: int = 0

    @property
    def name(self) -> str:
        return "counter"

    def observe(self, result: ResultRecord) -> Counter:
        return Counter(self.count + 1)

    def predict(self, context: DecisionContext) -> Prediction:
        return Prediction(context.match_index, self.name, (float(self.count), 0.0, 0.0))


@dataclass(frozen=True)
class Logged:
    """Her çağrıyı ortak bir günlüğe yazar."""

    log: list[str]

    @property
    def name(self) -> str:
        return "logged"

    def observe(self, result: ResultRecord) -> Logged:
        self.log.append("observe")
        return self

    def predict(self, context: DecisionContext) -> Prediction:
        self.log.append("predict")
        return Prediction(context.match_index, self.name, (0.4, 0.3, 0.3))


@dataclass(frozen=True)
class Stray:
    """Başka bir maç için tahmin döndüren bozuk strateji."""

    @property
    def name(self) -> str:
        return "stray"

    def observe(self, result: ResultRecord) -> Stray:
        return self

    def predict(self, context: DecisionContext) -> Prediction:
        return Prediction(context.match_index + 1, self.name, (0.4, 0.3, 0.3))


def _recorder(predict_for: frozenset[int] | None = None) -> Recorder:
    return Recorder(seen={}, contexts={}, predict_for=predict_for)


def _weekly(count: int) -> tuple[HistMatch, ...]:
    """Ardışık cumartesiler 14:00 UTC: her cuma kararı bir önceki haftanın sonucunu görür."""
    days = [date(2024, 8, 3) + timedelta(weeks=week) for week in range(count)]
    return tuple(
        hist_match(
            day=day,
            kickoff=datetime.combine(day, time(14), tzinfo=UTC),
            home=f"Ev {index}",
            away=f"Konuk {index}",
            line=index + 1,
        )
        for index, day in enumerate(days)
    )


@pytest.mark.leakage
def test_the_context_type_has_no_field_for_closing_prices_or_the_result() -> None:
    assert {field.name for field in fields(DecisionContext)} == {
        "match_index",
        "league",
        "season",
        "date",
        "home",
        "away",
        "decision_at",
        "pre_prices",
    }


@pytest.mark.leakage
def test_results_and_outcomes_are_separate_records() -> None:
    assert {field.name for field in fields(ResultRecord)} == {
        "league",
        "date",
        "home",
        "away",
        "home_goals",
        "away_goals",
        "known_at",
    }
    assert {field.name for field in fields(Outcome)} == {
        "match_index",
        "result",
        "home_goals",
        "away_goals",
        "closing",
    }


@pytest.mark.leakage
def test_a_decision_context_carries_only_pre_closing_prices() -> None:
    match = hist_match(
        day=date(2024, 8, 10),
        kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC),
        season="2425",
        home="Alfa",
        away="Beta",
        odds=FULL_ODDS,
    )
    recorder = _recorder()

    replay((match,), recorder)

    context = recorder.contexts[0]
    assert dict(context.pre_prices) == {
        key: price for key, price in FULL_ODDS.items() if key.phase == PRE_CLOSING
    }
    assert isinstance(context.pre_prices, MappingProxyType)
    assert (context.league, context.season, context.date) == ("E0", "2425", date(2024, 8, 10))
    assert (context.home, context.away, context.decision_at) == ("Alfa", "Beta", FRIDAY_NOON_BST)


@pytest.mark.leakage
def test_outcomes_hold_only_closing_prices_and_only_for_predicted_matches() -> None:
    kickoff = datetime(2024, 8, 10, 14, tzinfo=UTC)
    matches = (
        hist_match(day=date(2024, 8, 10), kickoff=kickoff, goals=(2, 1), odds=FULL_ODDS),
        hist_match(day=date(2024, 8, 10), kickoff=kickoff, goals=(0, 0), odds=FULL_ODDS, line=2),
    )

    result = replay(matches, _recorder(predict_for=frozenset({0})))

    assert set(result.outcomes) == {0}
    outcome = result.outcomes[0]
    assert dict(outcome.closing) == {
        key: price for key, price in FULL_ODDS.items() if key.phase == CLOSING
    }
    assert (outcome.match_index, outcome.result, outcome.home_goals, outcome.away_goals) == (
        0,
        "H",
        2,
        1,
    )
    assert isinstance(result.outcomes, MappingProxyType)
    assert isinstance(outcome.closing, MappingProxyType)


@pytest.mark.leakage
def test_outcomes_are_built_only_after_every_prediction_is_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    real = harness._outcome

    def spy(index: int, match: HistMatch) -> Outcome:
        log.append("outcome")
        return real(index, match)

    monkeypatch.setattr(harness, "_outcome", spy)

    replay(_weekly(3), Logged(log))

    assert log.count("predict") == 3
    assert log[-3:] == ["outcome"] * 3
    assert "outcome" not in log[:-3]


@pytest.mark.leakage
def test_a_result_known_exactly_at_a_decision_is_not_seen_by_that_decision() -> None:
    matches = (
        # cuma 09:00 BST başlıyor: sonucu tam cuma 12:00 BST'de bilinir
        hist_match(
            day=date(2024, 8, 9),
            kickoff=datetime(2024, 8, 9, 8, tzinfo=UTC),
            home="Gama",
            away="Delta",
        ),
        # cumartesi maçı: kararı tam cuma 12:00 BST
        hist_match(
            day=date(2024, 8, 10),
            kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC),
            home="Alfa",
            away="Beta",
            line=2,
        ),
        # salı maçı: kararı ikisinin sonucundan da sonra
        hist_match(
            day=date(2024, 8, 13),
            kickoff=datetime(2024, 8, 13, 18, 45, tzinfo=UTC),
            home="Beta",
            away="Gama",
            line=3,
        ),
    )
    recorder = _recorder()

    replay(matches, recorder)

    assert recorder.seen[1] == ()
    assert recorder.seen[2] == (("Gama", "Delta"), ("Alfa", "Beta"))


@pytest.mark.leakage
@pytest.mark.parametrize(
    "delay",
    [timedelta(0), timedelta(seconds=1), timedelta(days=1)],
    ids=["same-instant", "one-second-later", "one-day-later"],
)
def test_the_walk_refuses_a_result_that_was_not_known_before_the_decision(
    delay: timedelta,
) -> None:
    matches = (hist_match(day=date(2024, 8, 9)), hist_match(day=date(2024, 8, 10), line=2))
    events = (Event(FRIDAY_NOON_BST + delay, RESULT, 0), Event(FRIDAY_NOON_BST, DECISION, 1))

    with pytest.raises(LeakageError):
        harness._walk(matches, events, _recorder())


@pytest.mark.leakage
def test_the_walk_lets_a_decision_see_a_result_known_strictly_before_it() -> None:
    matches = (hist_match(day=date(2024, 8, 9)), hist_match(day=date(2024, 8, 10), line=2))
    events = (
        Event(FRIDAY_NOON_BST - timedelta(microseconds=1), RESULT, 0),
        Event(FRIDAY_NOON_BST, DECISION, 1),
    )
    recorder = _recorder()

    predictions, skipped = harness._walk(matches, events, recorder)

    assert recorder.seen[1] == (("Alfa", "Beta"),)
    assert ([prediction.match_index for prediction in predictions], skipped) == ([1], 0)


@pytest.mark.leakage
def test_the_walk_remembers_the_latest_result_not_the_last_one_seen() -> None:
    matches = tuple(hist_match(day=date(2024, 8, 9), line=line) for line in (1, 2, 3))
    events = (
        Event(FRIDAY_NOON_BST + timedelta(days=1), RESULT, 0),
        Event(FRIDAY_NOON_BST - timedelta(hours=1), RESULT, 1),
        Event(FRIDAY_NOON_BST, DECISION, 2),
    )

    with pytest.raises(LeakageError):
        harness._walk(matches, events, _recorder())


def test_replay_threads_the_strategy_value_that_observe_returns() -> None:
    result = replay(_weekly(4), Counter())

    assert [prediction.probs[0] for prediction in result.predictions] == [0.0, 1.0, 2.0, 3.0]


def test_replay_counts_matches_without_a_decision_and_decisions_without_a_prediction() -> None:
    matches = (
        hist_match(day=date(2024, 8, 9), kickoff=datetime(2024, 8, 9, 10, tzinfo=UTC)),
        hist_match(day=date(2024, 8, 10), kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC), line=2),
        hist_match(day=date(2024, 8, 11), kickoff=datetime(2024, 8, 11, 15, tzinfo=UTC), line=3),
    )

    result = replay(matches, _recorder(predict_for=frozenset({1})))

    assert (result.strategy, result.no_decision, result.no_prediction) == ("recorder", 1, 1)
    assert [prediction.match_index for prediction in result.predictions] == [1]


def test_a_prediction_for_another_match_is_refused() -> None:
    with pytest.raises(ValueError, match="başka bir"):
        replay(_weekly(1), Stray())


def test_predictions_follow_decision_order_not_input_order() -> None:
    result = replay(tuple(reversed(_weekly(3))), _recorder())

    assert [prediction.match_index for prediction in result.predictions] == [2, 1, 0]


def test_an_empty_history_replays_to_nothing() -> None:
    result = replay((), _recorder())

    assert (result.predictions, dict(result.outcomes)) == ((), {})
    assert (result.no_decision, result.no_prediction) == (0, 0)
```

- [ ] **Step 6: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_harness.py -q`
Expected: FAIL — `ImportError: cannot import name 'harness' from 'football_edge.backtest'`
(`Interrupted: 1 error during collection`)

- [ ] **Step 7: Harness'ı yaz**

Create `src/football_edge/backtest/harness.py`:
```python
"""Olay akışlı yeniden oynatma (tasarım §7.1–7.2, §10).

Strateji yalnız karar anından ÖNCE bilinen sonuçları görür. Bağlam kapanış ve sonuç alanı
taşımaz; kapanış ve sonuç ayrı bir değerlendirme kaydındadır ve bütün tahminler dondurulduktan
SONRA kurulur. Olay sıralaması sızıntıyı zaten önler; `_walk`teki denetim ikinci katmandır.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Protocol

from football_edge.backtest.events import DECISION, RESULT, Event, build_events
from football_edge.history.types import CLOSING, PRE_CLOSING, HistMatch, OddsKey


class LeakageError(RuntimeError):
    """Bir karar, anı karar anına eşit ya da sonra olan bir sonucu görmüş olurdu."""


@dataclass(frozen=True)
class ResultRecord:
    league: str
    date: date
    home: str
    away: str
    home_goals: int
    away_goals: int
    known_at: datetime


@dataclass(frozen=True)
class DecisionContext:
    """Stratejinin gördüğü TEK kayıt: kapanış, sonuç ve durum görüntüsü alanı yoktur (R98).

    Durum stratejinin içindedir (`observe` yeni değer döner); zamanı harness yönetir.
    """

    match_index: int
    league: str
    season: str
    date: date
    home: str
    away: str
    decision_at: datetime
    pre_prices: Mapping[OddsKey, float]  # yalnız PRE_CLOSING anahtarları


@dataclass(frozen=True)
class Outcome:
    match_index: int
    result: str
    home_goals: int
    away_goals: int
    closing: Mapping[OddsKey, float]  # yalnız CLOSING anahtarları


@dataclass(frozen=True)
class Bet:
    outcome: str
    price: float
    book: str


@dataclass(frozen=True)
class Prediction:
    match_index: int
    strategy: str
    probs: tuple[float, float, float]
    bet: Bet | None = None


class Strategy(Protocol):
    @property
    def name(self) -> str: ...

    def observe(self, result: ResultRecord) -> Strategy: ...

    def predict(self, context: DecisionContext) -> Prediction | None: ...


@dataclass(frozen=True)
class ReplayResult:
    strategy: str
    predictions: tuple[Prediction, ...]
    outcomes: Mapping[int, Outcome]  # yalnız tahmin edilen maçlar
    no_decision: int
    no_prediction: int


def _phase_prices(match: HistMatch, phase: str) -> Mapping[OddsKey, float]:
    return MappingProxyType({key: price for key, price in match.odds.items() if key.phase == phase})


def _result_record(match: HistMatch, known_at: datetime) -> ResultRecord:
    return ResultRecord(
        league=match.league,
        date=match.date,
        home=match.home,
        away=match.away,
        home_goals=match.home_goals,
        away_goals=match.away_goals,
        known_at=known_at,
    )


def _context(index: int, match: HistMatch, decided: datetime) -> DecisionContext:
    return DecisionContext(
        match_index=index,
        league=match.league,
        season=match.season,
        date=match.date,
        home=match.home,
        away=match.away,
        decision_at=decided,
        pre_prices=_phase_prices(match, PRE_CLOSING),
    )


def _outcome(index: int, match: HistMatch) -> Outcome:
    return Outcome(
        match_index=index,
        result=match.result,
        home_goals=match.home_goals,
        away_goals=match.away_goals,
        closing=_phase_prices(match, CLOSING),
    )


def _walk(
    matches: Sequence[HistMatch], events: Sequence[Event], strategy: Strategy
) -> tuple[tuple[Prediction, ...], int]:
    """Olayları verilen sırayla oynatır; (dondurulan tahminler, tahminsiz karar sayısı) döner."""
    current = strategy
    latest: datetime | None = None
    predictions: list[Prediction] = []
    skipped = 0
    for event in events:
        match = matches[event.match_index]
        if event.kind == RESULT:
            current = current.observe(_result_record(match, event.at))
            latest = event.at if latest is None else max(latest, event.at)
            continue
        if latest is not None and event.at <= latest:
            raise LeakageError(
                f"maç {event.match_index}: karar {event.at.isoformat()}, oysa "
                f"{latest.isoformat()} anında bilinen bir sonuç zaten görüldü"
            )
        prediction = current.predict(_context(event.match_index, match, event.at))
        if prediction is None:
            skipped += 1
            continue
        if prediction.match_index != event.match_index:
            raise ValueError(
                f"strateji {prediction.strategy}: maç {event.match_index} kararında başka bir "
                f"maç ({prediction.match_index}) için tahmin döndü"
            )
        predictions.append(prediction)
    return tuple(predictions), skipped


def replay(matches: Sequence[HistMatch], strategy: Strategy) -> ReplayResult:
    """Maçları olay akışıyla oynatır; sonuç kayıtları döngü BİTTİKTEN sonra kurulur."""
    events = build_events(matches)
    predictions, no_prediction = _walk(matches, events, strategy)
    decisions = sum(1 for event in events if event.kind == DECISION)
    predicted = [prediction.match_index for prediction in predictions]
    outcomes = MappingProxyType({index: _outcome(index, matches[index]) for index in predicted})
    return ReplayResult(
        strategy=strategy.name,
        predictions=predictions,
        outcomes=outcomes,
        no_decision=len(matches) - decisions,
        no_prediction=no_prediction,
    )
```

- [ ] **Step 8: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_harness.py -q`
Expected: PASS (16 passed)

- [ ] **Step 9: Strateji testlerini yaz**

Create `tests/test_strategies.py`:
```python
"""Faz 2 taban stratejileri: kapanış öncesi piyasa, nokta-zamanlı Elo, placebo."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from types import MappingProxyType

import pytest

from football_edge.backtest.harness import (
    DecisionContext,
    Prediction,
    ResultRecord,
    Strategy,
    replay,
)
from football_edge.backtest.strategies import EloPointInTime, MarketPre, Placebo
from football_edge.elo import EloConfig, expected_home, updated
from football_edge.history.types import CLOSING, PRE_CLOSING, RESULTS, OddsKey
from tests.backtest_builders import hist_match, quote

CONFIG = EloConfig()
FLAT = EloConfig(home_advantage=0.0, goal_scaling=False)
AVG_PRE = quote("Avg", PRE_CLOSING, (2.6, 3.3, 2.8))


def _normalise(prices: Sequence[float]) -> tuple[float, ...]:
    """Yer tutucu vig temizleyici (çarpımsal); gerçeği market/devig.py'de."""
    inverse = [1.0 / price for price in prices]
    total = sum(inverse)
    return tuple(value / total for value in inverse)


def _refusing(prices: Sequence[float]) -> tuple[float, ...]:
    raise ValueError("geçersiz fiyat")


def _context(
    pre: Mapping[OddsKey, float] | None = None,
    *,
    index: int = 0,
    home: str = "Alfa",
    away: str = "Beta",
    league: str = "E0",
) -> DecisionContext:
    return DecisionContext(
        match_index=index,
        league=league,
        season="2324",
        date=date(2024, 8, 10),
        home=home,
        away=away,
        decision_at=datetime(2024, 8, 9, 11, tzinfo=UTC),
        pre_prices=MappingProxyType(dict(pre or {})),
    )


def _record(
    home: str, away: str, home_goals: int, away_goals: int, *, league: str = "E0"
) -> ResultRecord:
    return ResultRecord(
        league=league,
        date=date(2024, 8, 3),
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        known_at=datetime(2024, 8, 3, 17, tzinfo=UTC),
    )


def _elo_probs(
    home_rating: float, away_rating: float, config: EloConfig, draw_rate: float
) -> tuple[float, float, float]:
    """Sözleşmedeki formülün testteki bağımsız yazımı."""
    expected = expected_home(home_rating, away_rating, config)
    home = min(max(expected - draw_rate / 2, 0.01), 0.98)
    away = min(max(1.0 - home - draw_rate, 0.01), 0.98)
    total = home + draw_rate + away
    return home / total, draw_rate / total, away / total


def _pick(strategy: Placebo, index: int) -> str:
    prediction = strategy.predict(_context(AVG_PRE, index=index))
    assert prediction is not None and prediction.bet is not None
    return prediction.bet.outcome


def test_market_pre_devigs_the_pre_closing_prices_of_its_book_in_h_d_a_order() -> None:
    received: list[tuple[float, ...]] = []

    def recording(prices: Sequence[float]) -> tuple[float, ...]:
        received.append(tuple(prices))
        return _normalise(prices)

    pre = {
        **quote("Avg", PRE_CLOSING, (1.9, 3.5, 4.2)),
        **quote("Max", PRE_CLOSING, (2.1, 3.8, 4.6)),
    }

    prediction = MarketPre(devig=recording).predict(_context(pre))

    assert received == [(1.9, 3.5, 4.2)]
    assert prediction is not None
    assert prediction.probs == pytest.approx(_normalise((1.9, 3.5, 4.2)))
    assert (prediction.match_index, prediction.strategy, prediction.bet) == (0, "market_pre", None)


def test_market_pre_reads_the_configured_book() -> None:
    pre = {
        **quote("Avg", PRE_CLOSING, (1.9, 3.5, 4.2)),
        **quote("Max", PRE_CLOSING, (2.1, 3.8, 4.6)),
    }

    prediction = MarketPre(devig=_normalise, book="Max").predict(_context(pre))

    assert prediction is not None
    assert prediction.probs == pytest.approx(_normalise((2.1, 3.8, 4.6)))


@pytest.mark.leakage
def test_market_pre_never_completes_a_pre_closing_quote_with_a_closing_price() -> None:
    avg_pre = quote("Avg", PRE_CLOSING, (1.9, 3.5, 4.2))
    pre = {
        **{key: price for key, price in avg_pre.items() if key.outcome != "D"},
        **quote("Avg", CLOSING, (1.8, 3.6, 4.4)),
    }

    assert MarketPre(devig=_normalise).predict(_context(pre)) is None


def test_market_pre_predicts_nothing_when_devig_refuses_the_prices() -> None:
    assert MarketPre(devig=_refusing).predict(_context(AVG_PRE)) is None


def test_market_pre_is_stateless() -> None:
    strategy = MarketPre(devig=_normalise)

    assert strategy.observe(_record("Alfa", "Beta", 1, 0)) == strategy


def test_elo_starts_teams_it_has_never_seen_at_the_initial_rating() -> None:
    prediction = EloPointInTime(config=FLAT).predict(_context())

    assert prediction.probs == pytest.approx((0.37, 0.26, 0.37))
    assert (prediction.strategy, prediction.bet) == ("elo", None)


def test_elo_observe_returns_a_new_value_and_leaves_the_old_one_untouched() -> None:
    before = EloPointInTime(config=FLAT)

    after = before.observe(_record("Alfa", "Beta", 2, 0))

    home, away = updated(1500.0, 1500.0, 2, 0, FLAT)
    assert dict(before.ratings) == {}
    assert dict(after.ratings) == pytest.approx({("E0", "Alfa"): home, ("E0", "Beta"): away})
    assert isinstance(after.ratings, MappingProxyType)


def test_elo_probabilities_follow_the_expectation_and_the_draw_rate() -> None:
    strategy = EloPointInTime(
        ratings=MappingProxyType({("E0", "Alfa"): 1600.0, ("E0", "Beta"): 1450.0})
    )

    prediction = strategy.predict(_context())

    assert prediction.probs == pytest.approx(_elo_probs(1600.0, 1450.0, CONFIG, 0.26))
    assert sum(prediction.probs) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("home_rating", "away_rating", "draw_rate", "expected"),
    [
        (2600.0, 1000.0, 0.26, _elo_probs(2600.0, 1000.0, FLAT, 0.26)),  # deplasman tabanda
        (1000.0, 2600.0, 0.26, (0.01, 0.26, 0.73)),  # ev tabanda
        (2600.0, 1000.0, 0.0, (0.98, 0.0, 0.02)),  # ev tavanda
    ],
    ids=["away-floor", "home-floor", "home-ceiling"],
)
def test_elo_clamps_extreme_expectations_and_renormalises(
    home_rating: float, away_rating: float, draw_rate: float, expected: tuple[float, ...]
) -> None:
    strategy = EloPointInTime(
        config=FLAT,
        draw_rate=draw_rate,
        ratings=MappingProxyType({("E0", "Alfa"): home_rating, ("E0", "Beta"): away_rating}),
    )

    probs = strategy.predict(_context()).probs

    assert probs == pytest.approx(expected)
    assert sum(probs) == pytest.approx(1.0)


def test_elo_keeps_same_named_teams_of_different_groups_apart() -> None:
    """R94: ham takım adı ülkeler arasında kimlik değildir — sessiz birleştirme hatası olurdu."""
    groups = MappingProxyType({"E0": "England", "BRA": "Brazil"})

    after = EloPointInTime(config=FLAT, groups=groups).observe(
        _record("Alfa", "Beta", 2, 0, league="E0")
    )

    assert set(after.ratings) == {("England", "Alfa"), ("England", "Beta")}
    elsewhere = after.predict(_context(home="Alfa", away="Beta", league="BRA"))
    assert elsewhere.probs == pytest.approx((0.37, 0.26, 0.37))


def test_elo_carries_a_rating_across_leagues_of_the_same_group() -> None:
    """Terfi eden takım reytingini taşır: E1'de oynadığı maç E0'daki ilk kararını besler."""
    groups = MappingProxyType({"E0": "England", "E1": "England"})

    after = EloPointInTime(config=FLAT, groups=groups).observe(
        _record("Alfa", "Beta", 2, 0, league="E1")
    )

    promoted, _ = updated(1500.0, 1500.0, 2, 0, FLAT)
    prediction = after.predict(_context(home="Alfa", away="Gama", league="E0"))
    assert prediction.probs == pytest.approx(_elo_probs(promoted, 1500.0, FLAT, 0.26))


def test_elo_groups_an_unmapped_league_by_its_own_code() -> None:
    after = EloPointInTime(config=FLAT, groups=MappingProxyType({"E0": "England"})).observe(
        _record("Alfa", "Beta", 2, 0, league="XX")
    )

    assert set(after.ratings) == {("XX", "Alfa"), ("XX", "Beta")}
    mapped = after.predict(_context(home="Alfa", away="Beta", league="E0"))
    assert mapped.probs == pytest.approx((0.37, 0.26, 0.37))


@dataclass(frozen=True)
class _RatingSpy:
    """Her kararda sarmaladığı Elo'nun reytinglerini kaydeder."""

    inner: EloPointInTime
    seen: dict[int, dict[tuple[str, str], float]]

    @property
    def name(self) -> str:
        return self.inner.name

    def observe(self, result: ResultRecord) -> _RatingSpy:
        return _RatingSpy(self.inner.observe(result), self.seen)

    def predict(self, context: DecisionContext) -> Prediction | None:
        self.seen[context.match_index] = dict(self.inner.ratings)
        return self.inner.predict(context)


@pytest.mark.leakage
def test_elo_ratings_at_a_decision_come_only_from_results_known_before_it() -> None:
    matches = (
        hist_match(
            day=date(2024, 8, 3),
            kickoff=datetime(2024, 8, 3, 14, tzinfo=UTC),
            home="Alfa",
            away="Beta",
            goals=(2, 0),
        ),
        # cuma 09:00 BST: kararı yok; sonucu tam 2. maçın karar anında (cuma 12:00 BST) bilinir
        hist_match(
            day=date(2024, 8, 9),
            kickoff=datetime(2024, 8, 9, 8, tzinfo=UTC),
            home="Gama",
            away="Delta",
            goals=(3, 1),
            line=2,
        ),
        hist_match(
            day=date(2024, 8, 10),
            kickoff=datetime(2024, 8, 10, 14, tzinfo=UTC),
            home="Beta",
            away="Gama",
            goals=(1, 1),
            line=3,
        ),
        hist_match(
            day=date(2024, 8, 13),
            kickoff=datetime(2024, 8, 13, 18, 45, tzinfo=UTC),
            home="Alfa",
            away="Delta",
            goals=(0, 1),
            line=4,
        ),
    )
    seen: dict[int, dict[tuple[str, str], float]] = {}

    result = replay(matches, _RatingSpy(EloPointInTime(config=CONFIG), seen))

    alfa, beta = updated(1500.0, 1500.0, 2, 0, CONFIG)
    gama, delta = updated(1500.0, 1500.0, 3, 1, CONFIG)
    beta_after, gama_after = updated(beta, gama, 1, 1, CONFIG)
    assert set(seen) == {0, 2, 3}
    assert seen[0] == {}
    assert seen[2] == pytest.approx({("E0", "Alfa"): alfa, ("E0", "Beta"): beta})
    assert seen[3] == pytest.approx(
        {
            ("E0", "Alfa"): alfa,
            ("E0", "Beta"): beta_after,
            ("E0", "Gama"): gama_after,
            ("E0", "Delta"): delta,
        }
    )
    probs = {prediction.match_index: prediction.probs for prediction in result.predictions}
    assert probs[2] == pytest.approx(_elo_probs(beta, 1500.0, CONFIG, 0.26))


def test_placebo_bets_its_seeded_pick_at_the_books_pre_closing_price() -> None:
    strategy = Placebo(devig=_normalise, seed=7)

    prediction = strategy.predict(_context(AVG_PRE, index=3))

    pick = random.Random(7 * 1_000_003 + 3).choice(RESULTS)
    assert prediction is not None and prediction.bet is not None
    assert prediction.bet.outcome == pick
    assert prediction.bet.price == dict(zip(RESULTS, (2.6, 3.3, 2.8), strict=True))[pick]
    assert prediction.bet.book == "Avg"
    assert prediction.probs == pytest.approx(_normalise((2.6, 3.3, 2.8)))
    assert prediction.strategy == "placebo"
    assert strategy.predict(_context(AVG_PRE, index=3)) == prediction


def test_placebo_picks_vary_across_matches() -> None:
    strategy = Placebo(devig=_normalise)

    assert {_pick(strategy, index) for index in range(60)} == set(RESULTS)


def test_placebo_picks_depend_on_the_seed() -> None:
    assert {_pick(Placebo(devig=_normalise, seed=seed), 0) for seed in range(30)} == set(RESULTS)


def test_placebo_bets_at_the_configured_books_price() -> None:
    pre = {**AVG_PRE, **quote("Max", PRE_CLOSING, (2.8, 3.6, 3.1))}

    prediction = Placebo(devig=_normalise, book="Max").predict(_context(pre, index=5))

    assert prediction is not None and prediction.bet is not None
    assert prediction.bet.book == "Max"
    maximum = dict(zip(RESULTS, (2.8, 3.6, 3.1), strict=True))
    assert prediction.bet.price == maximum[prediction.bet.outcome]


def test_placebo_predicts_nothing_without_a_complete_pre_closing_quote() -> None:
    pre = {**quote("Avg", CLOSING, (2.6, 3.3, 2.8)), **quote("Max", PRE_CLOSING, (2.7, 3.4, 2.9))}

    assert Placebo(devig=_normalise).predict(_context(pre)) is None


def test_placebo_predicts_nothing_when_devig_refuses_the_prices() -> None:
    assert Placebo(devig=_refusing).predict(_context(AVG_PRE)) is None


@pytest.mark.parametrize(
    "strategy",
    [MarketPre(devig=_normalise), EloPointInTime(), Placebo(devig=_normalise)],
    ids=["market_pre", "elo", "placebo"],
)
def test_every_strategy_replays_through_the_harness(strategy: Strategy) -> None:
    days = [date(2024, 8, 3) + timedelta(weeks=week) for week in range(3)]
    matches = tuple(
        hist_match(
            day=day,
            kickoff=datetime.combine(day, time(14), tzinfo=UTC),
            odds=AVG_PRE,
            line=index + 1,
        )
        for index, day in enumerate(days)
    )

    result = replay(matches, strategy)

    assert result.strategy == strategy.name
    assert len(result.predictions) == 3
    assert all(sum(prediction.probs) == pytest.approx(1.0) for prediction in result.predictions)
```

- [ ] **Step 10: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_strategies.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.backtest.strategies'`

- [ ] **Step 11: Stratejileri yaz**

Create `src/football_edge/backtest/strategies.py`:
```python
"""Faz 2'nin taban stratejileri (tasarım §7.3). Hepsi değişmez: `observe` yeni değer döner.

Vig temizleme ENJEKTE edilir (`Devig`): harness iskeleti vig modülüyle aynı dalgada yazıldı;
gerçek bağlantı bütünleşik harness'ta (`functools.partial(devig, method=...)`) kurulur.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from football_edge.backtest.harness import Bet, DecisionContext, Prediction, ResultRecord
from football_edge.elo import EloConfig, expected_home, updated
from football_edge.history.types import H2H, PRE_CLOSING, RESULTS, OddsKey

Devig = Callable[[Sequence[float]], tuple[float, ...]]

_FLOOR = 0.01
_CEILING = 0.98
# Maç başına tohum: bir maçın seçimi, başka maçların karar alıp almamasından bağımsızdır.
_SEED_STRIDE = 1_000_003


def _h2h_pre(context: DecisionContext, book: str) -> tuple[float, float, float] | None:
    """`book`un kapanış öncesi 1X2 fiyatları (H, D, A); biri eksikse None."""
    keys = [OddsKey(book=book, market=H2H, outcome=name, phase=PRE_CLOSING) for name in RESULTS]
    if not all(key in context.pre_prices for key in keys):
        return None
    home, draw, away = (context.pre_prices[key] for key in keys)
    return home, draw, away


def _fair(devig: Devig, prices: tuple[float, float, float]) -> tuple[float, float, float] | None:
    """Vig'i temizlenmiş olasılık; vig temizleyici fiyatı reddederse None (tahmin yok sayılır)."""
    try:
        probs = devig(prices)
    except ValueError:
        return None
    if len(probs) != len(RESULTS):
        raise ValueError(f"vig temizleyici {len(probs)} olasılık döndü, 1X2 üç ister")
    return probs[0], probs[1], probs[2]


def _clamp(value: float) -> float:
    return min(max(value, _FLOOR), _CEILING)


def _no_groups() -> Mapping[str, str]:
    return MappingProxyType({})


def _no_ratings() -> Mapping[tuple[str, str], float]:
    return MappingProxyType({})


@dataclass(frozen=True)
class MarketPre:
    """Piyasa taban çizgisi: `book`un kapanış öncesi fiyatının vig'i temizlenmiş olasılığı."""

    devig: Devig
    book: str = "Avg"

    @property
    def name(self) -> str:
        return "market_pre"

    def observe(self, result: ResultRecord) -> MarketPre:
        return self

    def predict(self, context: DecisionContext) -> Prediction | None:
        prices = _h2h_pre(context, self.book)
        probs = None if prices is None else _fair(self.devig, prices)
        if probs is None:
            return None
        return Prediction(match_index=context.match_index, strategy=self.name, probs=probs)


@dataclass(frozen=True)
class EloPointInTime:
    """Olay akışının Elo'su, iskele katsayılarla (Faz 3 fit eder).

    Reyting (grup, takım) anahtarlıdır (R94): ham takım adı ülkeler arasında kimlik değildir
    (sessiz birleştirme), lig kodu anahtarı ise terfi eden takımı sıfırlardı. Grup
    `groups.get(lig, lig)` — lig kodu → ülke; eşlenmemiş lig kendi grubudur. Görülmemiş
    (grup, takım) `config.initial`dan başlar.
    """

    config: EloConfig = EloConfig()
    draw_rate: float = 0.26
    groups: Mapping[str, str] = field(default_factory=_no_groups)
    ratings: Mapping[tuple[str, str], float] = field(default_factory=_no_ratings)

    @property
    def name(self) -> str:
        return "elo"

    def _key(self, league: str, team: str) -> tuple[str, str]:
        return self.groups.get(league, league), team

    def _rating(self, key: tuple[str, str]) -> float:
        return self.ratings.get(key, self.config.initial)

    def observe(self, result: ResultRecord) -> EloPointInTime:
        home_key = self._key(result.league, result.home)
        away_key = self._key(result.league, result.away)
        home, away = updated(
            self._rating(home_key),
            self._rating(away_key),
            result.home_goals,
            result.away_goals,
            self.config,
        )
        ratings = MappingProxyType({**self.ratings, home_key: home, away_key: away})
        return replace(self, ratings=ratings)

    def predict(self, context: DecisionContext) -> Prediction:
        expected = expected_home(
            self._rating(self._key(context.league, context.home)),
            self._rating(self._key(context.league, context.away)),
            self.config,
        )
        home = _clamp(expected - self.draw_rate / 2)
        away = _clamp(1.0 - home - self.draw_rate)
        total = home + self.draw_rate + away
        return Prediction(
            match_index=context.match_index,
            strategy=self.name,
            probs=(home / total, self.draw_rate / total, away / total),
        )


@dataclass(frozen=True)
class Placebo:
    """K4 negatif kontrolü: maç başına tohumlu rastgele sonuç, `book`un kapanış öncesi fiyatı."""

    devig: Devig
    seed: int = 20260922
    book: str = "Avg"

    @property
    def name(self) -> str:
        return "placebo"

    def observe(self, result: ResultRecord) -> Placebo:
        return self

    def predict(self, context: DecisionContext) -> Prediction | None:
        prices = _h2h_pre(context, self.book)
        probs = None if prices is None else _fair(self.devig, prices)
        if prices is None or probs is None:
            return None
        pick = random.Random(self.seed * _SEED_STRIDE + context.match_index).choice(RESULTS)
        bet = Bet(outcome=pick, price=prices[RESULTS.index(pick)], book=self.book)
        return Prediction(match_index=context.match_index, strategy=self.name, probs=probs, bet=bet)
```

- [ ] **Step 12: Yeşil olduğunu gör, statik denetim**
Run: `uv run pytest tests/test_strategies.py -q`
Expected: PASS (24 passed)
Run: `uv run pytest tests/test_timeline.py tests/test_events.py tests/test_harness.py tests/test_strategies.py -q`
Expected: PASS (74 passed)
Run: `uv run pytest tests/test_timeline.py tests/test_events.py tests/test_harness.py tests/test_strategies.py -q -m leakage`
Expected: `47 passed, 27 deselected`
Run: `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`
Expected: temiz (`Success: no issues found`)

- [ ] **Step 13: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır)

Her satır plan yazılırken ayrı bir kopyada uygulandı ve adı geçen test(ler) KIRMIZI ölçüldü (Task 0'ın
`types.py`si plan bölümünden birebir). Başlamadan dosyaların özetini al; her satırda değişikliği
yap → `PYTHONDONTWRITEBYTECODE=1 uv run pytest <testin dosyası> -q` → adı geçen test FAIL → değişikliği
elle geri al:
```bash
M=$(mktemp -d)
shasum -a 256 src/football_edge/backtest/timeline.py src/football_edge/backtest/events.py \
  src/football_edge/backtest/harness.py src/football_edge/backtest/strategies.py > "$M/once.sha"
```

| # | Mutasyon (dosya:ne değişir) | Kırmızı olması gereken test |
|---|---|---|
| 1 | `timeline.py:_decision_day` `back = …` → `back = (weekday - _FRIDAY) % 7` (salı–perşembe de cumaya) | `test_every_weekday_maps_to_friday_or_tuesday_noon_london_in_summer[wed]` |
| 2 | `timeline.py:decision_at` `instant >= _aware(kickoff)` → `instant > _aware(kickoff)` | `test_a_friday_match_has_a_decision_only_when_it_kicks_off_after_noon[equal]`, `test_a_tuesday_noon_kickoff_in_winter_has_no_decision` |
| 3 | `timeline.py:result_known_at` `match_date + timedelta(days=1)` → `match_date` | `test_without_a_kickoff_the_result_is_known_next_day_at_three_london` |
| 4 | `timeline.py:_london` `.astimezone(UTC)` silinir | `test_both_instants_come_back_in_utc` |
| 5 | `timeline.py:_aware` `if kickoff.utcoffset() is None:` → `if False:` | `test_a_naive_kickoff_is_refused[result]` |
| 6 | `events.py` `DECISION: int = 0` ↔ `RESULT: int = 1` değerleri yer değiştirir | `test_a_decision_sorts_before_a_result_at_the_same_instant`, `test_events_run_in_time_order_with_the_decision_first_on_a_tie`, `test_harness.py::test_a_result_known_exactly_at_a_decision_is_not_seen_by_that_decision` |
| 7 | `harness.py:_walk` `event.at <= latest` → `event.at < latest` | `test_the_walk_refuses_a_result_that_was_not_known_before_the_decision[same-instant]` |
| 8 | `harness.py:_walk` `latest = event.at if latest is None else max(latest, event.at)` → `latest = event.at` | `test_the_walk_remembers_the_latest_result_not_the_last_one_seen` |
| 9 | `harness.py:_context` `pre_prices=_phase_prices(match, PRE_CLOSING)` → `pre_prices=MappingProxyType(dict(match.odds))` | `test_a_decision_context_carries_only_pre_closing_prices` |
| 10 | `harness.py:_walk` `current = current.observe(…)` → `current.observe(…)` (dönen değer atılır) | `test_replay_threads_the_strategy_value_that_observe_returns`, `test_a_result_known_exactly_at_a_decision_is_not_seen_by_that_decision` |
| 11 | `harness.py:_walk` `predictions.append(prediction)` satırından önce `_outcome(event.match_index, match)` | `test_outcomes_are_built_only_after_every_prediction_is_frozen` |
| 12 | `harness.py:_walk` `if prediction.match_index != event.match_index:` → `if False:` | `test_a_prediction_for_another_match_is_refused` |
| 13 | `strategies.py:EloPointInTime.observe` `return replace(self, ratings=ratings)` → `return self` | `test_elo_ratings_at_a_decision_come_only_from_results_known_before_it`, `test_elo_observe_returns_a_new_value_and_leaves_the_old_one_untouched` |
| 14 | `strategies.py:EloPointInTime.predict` `away = _clamp(1.0 - home - self.draw_rate)` → `away = 1.0 - home - self.draw_rate` | `test_elo_clamps_extreme_expectations_and_renormalises[away-floor]` |
| 15 | `strategies.py` `_CEILING = 0.98` → `_CEILING = 1.0` | `test_elo_clamps_extreme_expectations_and_renormalises[home-ceiling]` |
| 16 | `strategies.py:Placebo.predict` `random.Random(self.seed * _SEED_STRIDE + context.match_index)` → `random.Random(self.seed)` | `test_placebo_picks_vary_across_matches` |
| 17 | `strategies.py:MarketPre.predict` `_h2h_pre(context, self.book)` → `_h2h_pre(context, "Avg")` | `test_market_pre_reads_the_configured_book` |
| 18 | `strategies.py:_fair` `except ValueError:` → `except KeyError:` | `test_market_pre_predicts_nothing_when_devig_refuses_the_prices`, `test_placebo_predicts_nothing_when_devig_refuses_the_prices` |
| 19 | `strategies.py:EloPointInTime._key` `return self.groups.get(league, league), team` → `return league, team` (grup yok sayılır) | `test_elo_carries_a_rating_across_leagues_of_the_same_group` |
| 20 | `strategies.py:EloPointInTime._key` → `return "", team` (ham ad kimlik olur) | `test_elo_keeps_same_named_teams_of_different_groups_apart`, `test_elo_groups_an_unmapped_league_by_its_own_code` |
| 21 | `strategies.py:EloPointInTime._key` `self.groups.get(league, league)` → `self.groups.get(league, "")` (eşlenmemiş ligler ortak grup) | `test_elo_groups_an_unmapped_league_by_its_own_code` |
| 22 | `strategies.py:EloPointInTime.predict` `self._rating(self._key(context.league, …))` → `self._rating((context.league, …))` (iki satır; tahmin gözlemden farklı anahtar okur) | `test_elo_carries_a_rating_across_leagues_of_the_same_group` |
| 23 | `harness.py:DecisionContext`a son alan olarak `results_before: tuple[ResultRecord, ...] = ()` (R98: bağlam durum görüntüsü taşımaz) | `test_the_context_type_has_no_field_for_closing_prices_or_the_result` |

Bitince geri yüklemeyi kanıtla:
Run: `shasum -a 256 -c "$M/once.sha" && uv run pytest tests/test_timeline.py tests/test_events.py tests/test_harness.py tests/test_strategies.py -q`
Expected: dört satır `OK`, `74 passed`

- [ ] **Step 14: Commit**
```bash
git add src/football_edge/backtest/timeline.py src/football_edge/backtest/events.py \
  src/football_edge/backtest/harness.py src/football_edge/backtest/strategies.py \
  tests/backtest_builders.py tests/test_timeline.py tests/test_events.py tests/test_harness.py \
  tests/test_strategies.py
git commit -m "feat: backtest harness iskeleti — zaman kuralları, olay akışı, bağlam/sonuç ayrımı, taban stratejiler (T2a)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 15: Kapının tamamı**
Run: `TMPDIR=$(mktemp -d) ./verify.sh` — log DOSYASINDAN oku.
Expected: 9 adım PASS + `SKIP: zincir (DATABASE_URL yok)`. (`sızıntı` adımı dalga sonunda Task 5'te
gelir; bu görevin 47 `leakage` testi o adımın alt sınırına sayılır.)

---

### Task 5: Dalga 1 birleştirmesi, migration 0007 ve kapının `sızıntı` adımı (controller)

**Kademe:** — (controller) · **Dalga:** 1 sonu · **Önkoşul:** Task 1–4'ün inceleme döngüleri kapandı
(her biri defterde `complete`).

**Files:**
- Modify: `verify.sh` (yeni `sızıntı` adımı), `.github/workflows/ci.yml` ("Geri kalan altı adım koşar" yorumuna
  `sızıntı`), `README.md` (§Kapı: "**On adım:**" → "**On bir adım:**", listeye `veri-sözleşmesi`nden sonra
  `sızıntı`; "On adımın hepsinin" → "On bir adımın hepsinin"; üç adımlık açıklama listesine `sızıntı` maddesi),
  `docs/HANDOFF.md` ("9 adım" geçen her yer → "10 adım"; `zincir` SKIP ayrıca sayılır)
- Canlı: `db/migrations/0007_holdout.sql` Supabase'e uygulanır

- [ ] **Step 1: Dört dalı sırayla birleştir** — dosya kümeleri ayrık, çakışma beklenmez.

```bash
git checkout main
for branch in feat/faz2-devig feat/faz2-lock feat/faz2-parser feat/faz2-harness; do
  git merge --no-ff "$branch" -m "merge: $branch (Faz 2 dalga 1)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" || break
  TMPDIR=$(mktemp -d) ./verify.sh || break
done
```
Expected: her birleştirmeden sonra `KAPI YEŞİL`. Bir birleştirme kırmızıysa döngü durur; kırmızı
adım o görevin implementer'ına bulgu olarak döner (controller düzeltmez).

- [ ] **Step 2: 0007'yi canlıya uygula** — Supabase `apply_migration`, ad `0007_holdout`, içerik
dosyanın kendisi. Doğrula:

```sql
select count(*) from holdout_access_log;                       -- 0
select tgname from pg_trigger where tgrelid = 'holdout_access_log'::regclass and not tgisinternal;
```
Expected: `0` ve append-only tetikleyicisi. Deneme satırı YAZILMAZ (append-only tabloya yazılan
satır silinemez — DEFERRED §2.3).

- [ ] **Step 3: `leakage` testlerini say**

Run: `uv run pytest tests/ -q -m leakage --collect-only 2>&1 | tail -1`
Expected: `N/M tests collected (… deselected)` — `N` bir sonraki adımdaki sabite yazılır.

- [ ] **Step 4: `verify.sh`e `sızıntı` adımını ekle** — `veri-sözleşmesi` adımının hemen ardına:

```bash
# Sızıntı (Faz 2 tasarımı §10): zaman semantiği, dönem ayrımı, kilit, bağlam/sonuç ayrımı.
# Veri-sözleşmesi adımının deseni: toplanan sayı --collect-only ile ölçülür ve alt sınırın
# altındaysa pytest hiç koşmadan kırmızı — bir `leakage` işareti sessizce düşerse kapı görür.
# Sabit yalnız ölçülerek büyütülür (Task 5, Task 12).
step "sızıntı" bash -c '
  EXPECTED_MIN_LEAKAGE=N

  collect_output=$(uv run pytest tests/ -q -m leakage --collect-only 2>&1)
  collect_code=$?
  if [ "$collect_code" -eq 5 ]; then
    collected=0
  else
    collected=$(printf "%s" "$collect_output" | grep -oE "^[0-9]+/" | head -1 | tr -d "/")
    collected=${collected:-0}
  fi

  if [ "$collected" -lt "$EXPECTED_MIN_LEAKAGE" ]; then
    printf "%s\n" "$collect_output"
    echo "HATA: leakage etiketli test sayısı ($collected) beklenen alt sınırın ($EXPECTED_MIN_LEAKAGE) altında"
    exit 1
  fi

  uv run pytest tests/ -q -m leakage
'
```
`N`, Step 3'te ölçülen sayıdır (yer tutucu değil: ölçmeden yazılmaz). Belge düzenlemeleri Files
listesindeki gibi: README "On bir adım" (listeye `sızıntı`, açıklamaya bir madde: "`sızıntı` — `leakage`
etiketli testleri koşar ve sayılarını ölçer (`EXPECTED_MIN_LEAKAGE`)"), HANDOFF "10 adım PASS + `zincir` SKIP".

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`)

| # | Mutasyon | Beklenen |
|---|---|---|
| 1 | `tests/`teki herhangi bir `@pytest.mark.leakage` satırı silinir | `FAIL: sızıntı` — "alt sınırın altında" |
| 2 | `EXPECTED_MIN_LEAKAGE` bir fazla | `FAIL: sızıntı` |
| 3 | bir `leakage` testinin iddiası tersine çevrilir | `FAIL: sızıntı` ve `FAIL: pytest` |

- [ ] **Step 6: Commit, taze klon kapısı, push**

```bash
git add verify.sh .github/workflows/ci.yml README.md docs/HANDOFF.md
git commit -m "ci: kapıya sızıntı adımı — leakage işaretli testler sayılarak koşar

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
Taze klon (`TMPDIR` klonun dışında) → `./verify.sh` → 10 adım PASS + `SKIP: zincir`. Sonra
`git fetch origin && git merge --no-ff origin/main` (bot çıpaları), `git push origin main`, CI yeşil.

---

### Task 6: Senkron, önbellek, CLI, migration 0006, history.yml ve kaynak kaydı (T1b)

**Kademe:** K2 · **Dalga:** 2 · **Worktree/dal:** `.worktrees/wt-sync` · `feat/faz2-sync`

**Files:**
- Create: `db/migrations/0006_history.sql` — `hist_files` (önbellek), `hist_fetches` (append-only)
- Create: `src/football_edge/history/store.py` — iki tablonun okuma/yazması
- Create: `src/football_edge/history/sync.py` — çekme → doğrulama → önbellek; `_load_all`, `load_matches`
- Create: `src/football_edge/history/__main__.py` — CLI: `sync [--all]`, `lock --write|--verify PATH`
- Create: `.github/workflows/history.yml` — tek job `history` (Task 10 bir ADIM ekler)
- Create: `config/robots/football-data.txt` — 2026-09-22 runner ölçümünün anlık görüntüsü
- Modify: `config/sources.yaml` — dosya sonuna `football-data` kaydı (`declared_paths` komutla üretilir)
- Create: `tests/fake_hist_db.py` — iki tablonun bellek içi taklidi
- Test: `tests/test_history_store.py`, `tests/test_history_sync.py`, `tests/test_history_registry.py`,
  `tests/test_history_cli.py`, `tests/test_history_workflow.py`

Dokunulmaz (ortak dosya, controller): `scripts/ops_alert.py`, `db/migrations/0008_*`,
`verify.sh`, `pyproject.toml`, `tests/workflow_helpers.py`, `tests/test_workflows.py`.

**Interfaces:**
- Consumes:
  - Task 1: `catalog.MAIN`, `EXTRA`, `HistoryLeague`, `Catalog`, `load_catalog(path: Path) ->
    Catalog`, `file_paths(league, *, current_season) -> tuple[str, ...]`,
    `declared_paths(catalog) -> tuple[str, ...]`, `season_of_path(path) -> str | None`;
    `football_data.parse_file(content, *, league, season) -> ParseResult`,
    `check_quality(result, *, path, league, season) -> None`; `tests/history_csv.py` (başlıklar,
    `E0`, `BRA`, `main_row`, `extra_row`, `csv_bytes`).
  - Task 3: `football_edge.history.lock`: `LockViolation`, `HistoryLock`, `build_lock(
    matches_by_league: Mapping[str, Sequence[HistMatch]], *, locked_at: date) -> HistoryLock`,
    `dump_lock(lock) -> str`, `load_lock(path: Path) -> HistoryLock` (R99: bozuk yapıda
    `LockViolation`), `verify_lock(lock, matches_by_league) -> None`, `HistoryLock.leagues:
    Mapping[str, Mapping[str, Digest]]`, `Digest.rows`; `football_edge.history.holdout`: `DEV`,
    `HOLDOUT`, `POST`, `HoldoutKey`, `HoldoutLocked`, `select_periods(matches, *, periods, key)`,
    `period_of` (test). Task 3'ün AST kuralı (`tests/test_holdout_access_rule.py`) `_load_all`
    anmasına yalnız `history/sync.py` ve `history/__main__.py`de izin verir (`tests/` taranmaz).
  - Task 0: `HistMatch`.
  - Mevcut kod: `collector._guarded_get(client, source, path, parser, *, timeout) ->
    httpx.Response`, `collector.ContractViolation`; `sources.Source`, `SourceBlocked`,
    `load_sources`, `enabled_sources`, `robots_for`, `audit_offline`; `collect.EXIT_SOURCE_FAILED`
    (7), `collect.SOURCES_PATH`, `collect.ROBOTS_DIR`, `collect.configure_logging`; `db.connect()`.
    Testler: `tests.fake_sources.fake_source`, `tests.workflow_helpers`, `tests.test_workflows`
    (alarm kuralı fonksiyonları), `tests.test_collect_workflows` (`_secret_expressions`,
    `_secret_paths`).
- Produces (sözleşme, birebir):
```python
# football_edge/history/store.py
@dataclass(frozen=True)
class CachedFile:
    path: str; sha256: str; fetched_at: datetime; content: bytes      # content açılmış (gzip değil)
def save_file(conn: psycopg.Connection[Any], *, path: str, content: bytes, fetched_at: datetime,
              last_modified: str | None, row_count: int) -> bool      # içerik değiştiyse True
def log_fetch(conn: psycopg.Connection[Any], *, path: str, fetched_at: datetime, sha256: str | None,
              http_status: int | None, rows_parsed: int, rows_rejected: int) -> None
def load_files(conn: psycopg.Connection[Any], paths: Sequence[str]) -> Mapping[str, CachedFile]

# football_edge/history/sync.py
SOURCE_ID: str = "football-data"
@dataclass(frozen=True)
class SyncReport:
    requested: int; changed: int; unchanged: int
    failed: tuple[tuple[str, str], ...]          # (yol, neden)
    rejected_rows: int
def mutable_paths(catalog: Catalog) -> tuple[str, ...]     # güncel sezon ana dosyaları + ek lig dosyaları
def sync(conn: psycopg.Connection[Any], client: httpx.Client, *, source: Source, parser: Protego,
         catalog: Catalog, paths: Sequence[str], now: Callable[[], datetime]) -> SyncReport
def load_matches(conn: psycopg.Connection[Any], catalog: Catalog, *, lock: HistoryLock | None = None,
                 key: HoldoutKey | None = None) -> Mapping[str, tuple[HistMatch, ...]]
    # R96: lig kodu → (date, kickoff, home) sırasıyla DEV + POST; HOLDOUT yalnız geçerli anahtarla.
    # lock verilirse ÖNCE bütün satırlar üzerinde verify_lock (LockViolation). Holdout history/'den anahtarsız çıkmaz.
# _load_all(conn, catalog): modüle özel, bütün dönemler — yalnız sync.py ve history/__main__.py (kilit komutu); AST kuralı korur

# CLI: python -m football_edge.history sync [--all] · lock --write PATH · lock --verify PATH
```
- Ek (sözleşme dışı): `store.sha256_hex(content: bytes) -> str`, `sync.TIMEOUT_SECONDS = 60.0`,
  `__main__.EXIT_LOCK_VIOLATION = 9`, `__main__.CATALOG_PATH`, `__main__.main(argv) -> int`;
  `tests/fake_hist_db.py` (`FakeHistDb`, `at`); `tests/test_history_sync.py` (`Site`, `FILES`,
  `PERIODS_FILES`, `OLD`, `CURRENT`, `EXTRA_FILE` — CLI testleri kullanır);
  `tests/test_history_workflow.py` (`DATABASE_STEPS` — Task 10 genişletir).

**Bu görevin kararları (hepsini testler sabitler):**
- İstek yolu YALNIZ `collector._guarded_get`: robots her yolda ve yönlendirmenin her sıçramasında
  sorulur, `crawl_delay_seconds` (3 sn) her istekten önce beklenir. `source.declared_paths`te
  olmayan yol hiç istenmez (`SourceBlocked`, R7: beyan = gerçek istek).
- Her yol kendi işlemindedir: çek → `parse_file` → `check_quality` → `save_file` → `log_fetch` →
  commit. Arızada: rollback, `LOGGER.exception`, günlüğe `sha256 NULL` satırı (HTTP hatasında durum
  kodu, yoksa NULL), `SyncReport.failed`e `(yol, "Tür: mesaj")` tek satır — döngü sürer. Sayaçlar
  commit'ten SONRA artar (G1). Sözleşmeyi geçmeyen dosya önbelleğe GİRMEZ; önceki iyi sürüm kalır.
- `hist_files.fetched_at`, o içeriğin İLK görüldüğü andır: aynı içerik yeniden yazılmaz
  (`save_file` False döner). Her çekmenin anı `hist_fetches`tedir. `sha256` ve `byte_size`
  açılmış baytlarındır; `content` `gzip.compress(…, mtime=0)`.
- `mutable_paths` = her ligin son dosyası (ana: güncel sezon; ek: tek dosya), sıralı.
- `_load_all` (modüle özel) bütün beyanlı yolları okur ve BÜTÜN dönemleri döner; önbellekte eksik
  dosya ya da bugünkü sözleşmeyi geçmeyen dosya `ContractViolation` verir (eksik veriyle kilit
  yazılmaz, doğrulama yeşil görünmez). Sıra `(date, kickoff ya da en küçük UTC an, home)` — saatsiz
  maç o günün saatlilerinden önce.
- `load_matches(conn, catalog, *, lock=None, key=None)` (R96) geliştirme + sonrası dönemlerini
  verir; HOLDOUT yalnız `open_holdout`un kurduğu anahtarla (`select_periods`; elle kurulan anahtar
  `HoldoutLocked`). `lock` verilirse doğrulama süzgeçten ÖNCE, bütün satırlar üzerinde koşar:
  değişen bir holdout satırı da `LockViolation` verir ama hiç dışarı çıkmaz. Analiz CLI'ları
  (Task 9, 10) ayrı `verify_lock` çağırmaz, `load_matches(..., lock=lock)` kullanır.
- CLI: çıktı `logging`le ve ilk iş `collect.configure_logging()` (kök handler redakte; DSN bir
  psycopg hatasında loga düşmesin). `sync` → 0 ya da `EXIT_SOURCE_FAILED` (7). `lock --write`
  `_load_all`dan kilit yazar (holdout ÖZETİ gerekir, satırları dışarı çıkmaz); `lock --verify`
  `load_matches(conn, catalog, lock=lock)` çağırır; veri farkı ya da bozuk kilit dosyası (R99:
  `load_lock` → `LockViolation`) → `EXIT_LOCK_VIOLATION` (9, `collect`in 2–8'i ve 0/1 dışında);
  kullanılamayan önbellek (`ContractViolation`) → 7 ve kilit dosyasına dokunulmaz. Kayıt yoksa ya
  da `enabled: false` ise çekme hiç başlamaz (`RuntimeError`). Yalnız toplu sayılar loglanır. CLI
  testleri iç fonksiyon yamalamaz: sentetik dosyalar `sync --all` ile sahte veritabanına girer.
- 0006: iki tabloda satır düzeyi güvenlik AÇIK ve politikasız — Supabase API rolleri (anon,
  authenticated) ham içeriği okuyamaz (D18); tabloların sahibi pipeline rolü RLS'e takılmaz.
  `hist_fetches` append-only (0001'in `forbid_ledger_mutation()`i, yeniden tanımlanmaz);
  `hist_files` değil (önbellek, güncellenir).
- `history.yml` TEK job (`history`), `collect-daily.yml` deseni: checkout (`persist-credentials:
  false`) → `Secret taraması` → setup-uv → `uv sync --frozen` → **`Senkron`** → `Alarm aç` →
  `Alarm kapat`. `all` girdisi `env` ile gelir, betiğe `${{ }}` ile gömülmez. **Task 10 `selftest`i
  ikinci job olarak DEĞİL, `Senkron` ile `Alarm aç` arasına bir ADIM olarak ekler**
  (`tests/workflow_helpers._steps` tek job varsayar; ikinci job `test_workflows.py`yi düşürür).
- Secret kuralı: "yalnız veritabanını kullanan adımlar secret alır ve yalnız DATABASE_URL" —
  izinli adım adları TEK sabitte, `tests/test_history_workflow.py::DATABASE_STEPS = ("Senkron",)`.
  Task 10 selftest adımına DATABASE_URL verip adını bu sabite ekler; testin gövdesi değişmez
  (plan yazılırken benzetildi: sabit genişletilmeden kırmızı, genişletilince yeşil).
- `history.yml`, controller'ın 0008'i onu `ops.dispatch_workflow` izinli listesine koyduğunda
  `tests/test_workflows.py`nin ALARMED testlerine (alarm adımları, izinler) kendiliğinden girer.
  O kurallar bugünden geçer: `test_history_already_obeys_the_alarm_rules_of_dispatched_workflows`
  aynı fonksiyonları bu dosyaya koşar. `persist-credentials` ve `odds-collect` kuralları zaten
  bütün workflow'lara uygulanıyor (`ALL_WORKFLOWS`).
- **Bu görevde YAPILMAZ (controller, Task 8):** 0006'yı Supabase'e uygulamak; izinli liste +
  pg_cron (0008) ve `scripts/ops_alert.py` `TRIGGERS`; ilk `sync --all`, `lock --write
  config/history_lock.yaml` ve commit'i; kilit dosyası var olunca `history.yml`e `lock --verify`
  adımı.

- [ ] **Step 1: Önbellek testlerini ve veritabanı taklidini yaz**

Create `tests/fake_hist_db.py`:
```python
"""`hist_files`/`hist_fetches` için bellek içi taklit (db/migrations/0006_history.sql).

Yük taşıyan kısıtları UYGULAR: NOT NULL sütunlar, `hist_files.path` birincil anahtarı (upsert) ve
`hist_fetches`in append-only oluşu (UPDATE/DELETE ifadesi tanınmaz). Commit/rollback gerçek bir
işlem gibi davranır: rollback commit'lenmemiş her yazmayı geri alır. `bytea` okunurken
`memoryview` döner — sürücünün ikili biçimde döndürdüğü tip; kod `bytes`a çevirmeyi unutursa
burada görünür.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

FILE_COLUMNS = (
    "path",
    "sha256",
    "fetched_at",
    "http_last_modified",
    "byte_size",
    "row_count",
    "content",
)
FETCH_COLUMNS = ("path", "fetched_at", "sha256", "http_status", "rows_parsed", "rows_rejected")
FILE_NULLABLE = frozenset({"http_last_modified"})
FETCH_NULLABLE = frozenset({"sha256", "http_status"})


class NotNullViolation(Exception):
    """Gerçek şemada NOT NULL olan sütuna None yazıldı."""


class CommitFailed(Exception):
    """COMMIT'in kendisi düştü, bağlantı ayakta (`tests/fake_db.py:CommitFailed` deseni)."""


@dataclass
class FakeHistDb:
    files: dict[str, dict[str, Any]] = field(default_factory=dict)
    fetches: list[dict[str, Any]] = field(default_factory=list)
    statements: list[str] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0
    commit_fails: Callable[[FakeHistDb], bool] | None = None

    def __post_init__(self) -> None:
        self._committed = copy.deepcopy((self.files, self.fetches))

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        if self.commit_fails is not None and self.commit_fails(self):
            raise CommitFailed("COMMIT düştü, bağlantı ayakta")
        self.commits += 1
        self._committed = copy.deepcopy((self.files, self.fetches))

    def rollback(self) -> None:
        self.rollbacks += 1
        self.files, self.fetches = copy.deepcopy(self._committed)

    def __enter__(self) -> FakeHistDb:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _row(
    columns: tuple[str, ...], params: tuple[Any, ...], nullable: frozenset[str]
) -> dict[str, Any]:
    row = dict(zip(columns, params, strict=True))
    empty = sorted(name for name, value in row.items() if value is None and name not in nullable)
    if empty:
        raise NotNullViolation(f"NOT NULL ihlali: {empty}")
    return row


class _Cursor:
    def __init__(self, db: FakeHistDb) -> None:
        self._db = db
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        text = " ".join(sql.split())
        self._db.statements = [*self._db.statements, text]
        self._result = []
        if text == "SELECT sha256 FROM hist_files WHERE path = %s":
            found = self._db.files.get(params[0])
            self._result = [] if found is None else [(found["sha256"],)]
        elif text.startswith("INSERT INTO hist_files") and "ON CONFLICT (path) DO UPDATE" in text:
            row = _row(FILE_COLUMNS, params, FILE_NULLABLE)
            self._db.files = {**self._db.files, row["path"]: row}
        elif text.startswith("INSERT INTO hist_fetches"):
            self._db.fetches = [*self._db.fetches, _row(FETCH_COLUMNS, params, FETCH_NULLABLE)]
        elif text.startswith("SELECT path, sha256, fetched_at, content FROM hist_files WHERE"):
            wanted = set(params[0])
            self._result = [
                (row["path"], row["sha256"], row["fetched_at"], memoryview(row["content"]))
                for path, row in self._db.files.items()
                if path in wanted
            ]
        else:
            raise AssertionError(f"taklit bu sorguyu tanımıyor: {text}")

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)


def at(minute: int) -> datetime:
    """Testlerin sabit saati: 2026-09-28 10:<minute> UTC."""
    return datetime(2026, 9, 28, 10, minute, tzinfo=UTC)
```

Create `tests/test_history_store.py`:
```python
"""`history/store.py` sahte bağlantıyla; `0006_history.sql` metin üzerinden (mevcut desen)."""

from __future__ import annotations

import gzip
import hashlib
import re
from pathlib import Path

import pytest

from football_edge.collector import ContractViolation
from football_edge.history import store
from football_edge.history.store import CachedFile, load_files, log_fetch, save_file
from tests.fake_hist_db import FakeHistDb, at

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/0006_history.sql"
PATH = "/mmz4281/2526/E0.csv"
CONTENT = b"Div,Date\r\nE0,16/08/2025\r\n"


def _save(db: FakeHistDb, content: bytes = CONTENT, minute: int = 0) -> bool:
    return save_file(
        db,
        path=PATH,
        content=content,
        fetched_at=at(minute),
        last_modified="Sun, 24 May 2026 20:00:00 GMT",
        row_count=380,
    )


def test_save_file_stores_gzip_content_with_the_sha_and_size_of_the_plain_bytes() -> None:
    db = FakeHistDb()

    assert _save(db) is True

    row = db.files[PATH]
    assert row["sha256"] == hashlib.sha256(CONTENT).hexdigest()
    assert row["byte_size"] == len(CONTENT)
    assert gzip.decompress(row["content"]) == CONTENT
    assert row["content"] != CONTENT, "içerik sıkıştırılmadan yazılmış"
    assert (row["row_count"], row["fetched_at"]) == (380, at(0))
    assert row["http_last_modified"] == "Sun, 24 May 2026 20:00:00 GMT"


def test_the_same_content_is_not_rewritten_and_keeps_its_first_seen_time() -> None:
    db = FakeHistDb()
    _save(db, minute=0)
    writes = sum("INSERT INTO hist_files" in text for text in db.statements)

    assert _save(db, minute=5) is False

    assert sum("INSERT INTO hist_files" in text for text in db.statements) == writes
    assert db.files[PATH]["fetched_at"] == at(0)


def test_changed_content_replaces_the_cached_version() -> None:
    db = FakeHistDb()
    _save(db, minute=0)
    newer = CONTENT + b"E0,23/08/2025\r\n"

    assert _save(db, newer, minute=5) is True

    assert db.files[PATH]["sha256"] == hashlib.sha256(newer).hexdigest()
    assert db.files[PATH]["fetched_at"] == at(5)
    assert len(db.files) == 1


def _log(db: FakeHistDb, *, sha256: str | None, status: int | None, minute: int = 0) -> None:
    log_fetch(
        db,
        path=PATH,
        fetched_at=at(minute),
        sha256=sha256,
        http_status=status,
        rows_parsed=380 if sha256 else 0,
        rows_rejected=1 if sha256 else 0,
    )


def test_every_attempt_is_logged_and_a_failed_one_has_no_sha() -> None:
    db = FakeHistDb()

    _log(db, sha256="ab" * 32, status=200, minute=0)
    _log(db, sha256=None, status=None, minute=1)

    assert [(row["sha256"], row["http_status"], row["rows_parsed"]) for row in db.fetches] == [
        ("ab" * 32, 200, 380),
        (None, None, 0),
    ]


def test_the_store_leaves_the_commit_to_its_caller() -> None:
    """Dosya yazıldı ama günlük satırı düştüyse ikisi birlikte geri alınabilmeli: commit sync'in."""
    db = FakeHistDb()
    _save(db)
    _log(db, sha256=None, status=None)

    assert db.commits == 0


def test_load_files_returns_plain_bytes_for_cached_paths_only() -> None:
    db = FakeHistDb()
    _save(db)

    loaded = load_files(db, [PATH, "/new/BRA.csv"])

    assert dict(loaded) == {
        PATH: CachedFile(
            path=PATH,
            sha256=hashlib.sha256(CONTENT).hexdigest(),
            fetched_at=at(0),
            content=CONTENT,
        )
    }
    assert type(loaded[PATH].content) is bytes


def test_load_files_refuses_content_that_does_not_match_its_sha() -> None:
    db = FakeHistDb()
    _save(db)
    db.files[PATH] = {**db.files[PATH], "content": gzip.compress(b"kurcalanmis", mtime=0)}

    with pytest.raises(ContractViolation, match="sha256"):
        load_files(db, [PATH])


# ── 0006_history.sql ────────────────────────────────────────────────────────


def _columns(table: str) -> dict[str, str]:
    """Tablonun sütun adı → tanımı (satır içi `--` yorumu atılmış, küçük harf)."""
    sql = MIGRATION.read_text(encoding="utf-8")
    body = re.search(rf"create table if not exists {table} \((.*?)\n\);", sql, flags=re.S)
    assert body is not None, f"{table} tablosu 0006'da yok"
    lines = (line.split("--")[0].strip().rstrip(",") for line in body.group(1).splitlines())
    return {line.split()[0]: " ".join(line.split()[1:]).lower() for line in lines if line}


def test_hist_files_is_a_cache_keyed_by_path_with_not_null_content() -> None:
    columns = _columns("hist_files")

    assert list(columns) == [
        "path",
        "sha256",
        "fetched_at",
        "http_last_modified",
        "byte_size",
        "row_count",
        "content",
    ]
    assert columns["path"] == "text primary key"
    assert columns["content"] == "bytea not null"
    assert columns["http_last_modified"] == "text"
    for name in ("sha256", "fetched_at", "byte_size", "row_count"):
        assert "not null" in columns[name], name


def test_hist_fetches_allows_a_null_sha_and_status_for_failed_attempts() -> None:
    columns = _columns("hist_fetches")

    assert list(columns) == [
        "id",
        "path",
        "fetched_at",
        "sha256",
        "http_status",
        "rows_parsed",
        "rows_rejected",
    ]
    assert columns["id"] == "bigserial primary key"
    assert (columns["sha256"], columns["http_status"]) == ("text", "int")
    for name in ("path", "fetched_at", "rows_parsed", "rows_rejected"):
        assert "not null" in columns[name], name


def test_the_fetch_log_is_append_only_and_the_cache_is_not() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    triggers = re.findall(
        r"create trigger \w+\s+before update or delete on (\w+)\s+for each row execute "
        r"function forbid_ledger_mutation\(\);",
        sql,
    )

    assert triggers == ["hist_fetches"]
    assert "create or replace function forbid_ledger_mutation" not in sql, (
        "0001'deki yeniden yazıldı"
    )


def test_raw_content_tables_hide_their_rows_from_api_roles() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    for table in ("hist_files", "hist_fetches"):
        assert f"alter table {table} enable row level security;" in sql, table
    assert "create policy" not in sql, "politika API rollerine satır açar"


def test_the_store_writes_exactly_the_columns_the_migration_creates() -> None:
    """Taklit store'un SQL'ini tanır, migration şemayı kurar: ikisini bağlayan tek yer burası."""

    def listed(statement: str) -> list[str]:
        found = re.search(r"\(([^)]*)\)\s*VALUES", statement)
        assert found is not None
        return [name.strip() for name in found.group(1).split(",")]

    assert listed(store._UPSERT_FILE) == list(_columns("hist_files"))
    assert listed(store._INSERT_FETCH) == list(_columns("hist_fetches"))[1:]
```

- [ ] **Step 2: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_history_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.history.store'`

- [ ] **Step 3: Migration'ı ve önbellek modülünü yaz**

Create `db/migrations/0006_history.sql`:
```sql
-- Faz 2: football-data.co.uk CSV önbelleği ve çekme günlüğü (tasarım §4.3, D6).
--
-- `hist_files` bir ÖNBELLEKTİR, kanıt değil: yol başına son sürüm, içerik değişince güncellenir.
-- Kanıt, append-only çekme günlüğü (`hist_fetches`) ile depodaki kilittir
-- (config/history_lock.yaml). Her sürümü saklamak yılda ~130 MB ederdi; son sürüm ~20 MB.
--
-- Ham üçüncü taraf içeriği YALNIZ bu özel tabloda durur (D18): satır düzeyi güvenlik açık ve
-- politikasız — API rolleri (anon, authenticated) hiçbir satır göremez; tabloların sahibi olan
-- pipeline rolü RLS'e takılmaz.

create table if not exists hist_files (
  path                text primary key,
  sha256              text not null,        -- AÇILMIŞ baytların özeti (gzip'in değil)
  fetched_at          timestamptz not null, -- bu sürümün ilk görüldüğü an
  http_last_modified  text,
  byte_size           int not null check (byte_size >= 0),   -- açılmış bayt sayısı
  row_count           int not null check (row_count >= 0),   -- ayrıştırılan maç
  content             bytea not null        -- gzip(dosya baytları)
);

create table if not exists hist_fetches (
  id             bigserial primary key,
  path           text not null,
  fetched_at     timestamptz not null,
  sha256         text,                      -- NULL: deneme başarısız, önbelleğe girmedi
  http_status    int,                       -- NULL: HTTP yanıtı yok (robots, ağ, doğrulama)
  rows_parsed    int not null check (rows_parsed >= 0),
  rows_rejected  int not null check (rows_rejected >= 0)
);

create index if not exists hist_fetches_path_idx on hist_fetches (path, fetched_at desc);

alter table hist_files enable row level security;
alter table hist_fetches enable row level security;

-- Append-only zorlaması. forbid_ledger_mutation() 0001'de tanımlandı; yeniden yazılmaz.
drop trigger if exists hist_fetches_append_only on hist_fetches;
create trigger hist_fetches_append_only
  before update or delete on hist_fetches
  for each row execute function forbid_ledger_mutation();
```

Create `src/football_edge/history/store.py`:
```python
"""`hist_files` (önbellek, yol başına son sürüm) ve `hist_fetches` (append-only çekme günlüğü).

`hist_files` kanıt DEĞİLDİR (tasarım D6): kanıt, çekme günlüğü ile depodaki kilittir. İçerik
gzip'le saklanır; `sha256` ve `byte_size` AÇILMIŞ baytlarındır. Ham üçüncü taraf içeriği yalnız bu
özel tabloda durur — bu modül onu loga yazmaz.
"""

from __future__ import annotations

import gzip
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

import psycopg

from football_edge.collector import ContractViolation

_CURRENT_SHA = "SELECT sha256 FROM hist_files WHERE path = %s"
_UPSERT_FILE = """
    INSERT INTO hist_files
      (path, sha256, fetched_at, http_last_modified, byte_size, row_count, content)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (path) DO UPDATE SET
      sha256 = excluded.sha256,
      fetched_at = excluded.fetched_at,
      http_last_modified = excluded.http_last_modified,
      byte_size = excluded.byte_size,
      row_count = excluded.row_count,
      content = excluded.content
"""
_INSERT_FETCH = """
    INSERT INTO hist_fetches
      (path, fetched_at, sha256, http_status, rows_parsed, rows_rejected)
    VALUES (%s, %s, %s, %s, %s, %s)
"""
_LOAD_FILES = "SELECT path, sha256, fetched_at, content FROM hist_files WHERE path = ANY(%s)"


@dataclass(frozen=True)
class CachedFile:
    path: str
    sha256: str
    fetched_at: datetime
    content: bytes  # açılmış (gzip değil)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_file(
    conn: psycopg.Connection[Any],
    *,
    path: str,
    content: bytes,
    fetched_at: datetime,
    last_modified: str | None,
    row_count: int,
) -> bool:
    """İçerik değiştiyse (ya da yol yeniyse) satırı yazar ve True döner.

    Aynı içerik yeniden YAZILMAZ: `fetched_at` o sürümün İLK görüldüğü anı taşır; her çekmenin
    anı `hist_fetches`tedir. Commit çağıranındır.
    """
    digest = sha256_hex(content)
    with conn.cursor() as cur:
        cur.execute(_CURRENT_SHA, (path,))
        found = cur.fetchone()
        if found is not None and found[0] == digest:
            return False
        cur.execute(
            _UPSERT_FILE,
            (
                path,
                digest,
                fetched_at,
                last_modified,
                len(content),
                row_count,
                gzip.compress(content, mtime=0),
            ),
        )
    return True


def log_fetch(
    conn: psycopg.Connection[Any],
    *,
    path: str,
    fetched_at: datetime,
    sha256: str | None,
    http_status: int | None,
    rows_parsed: int,
    rows_rejected: int,
) -> None:
    """Her çekme denemesi bir satır; `sha256` NULL ise dosya önbelleğe GİRMEDİ. Commit çağıranın."""
    with conn.cursor() as cur:
        cur.execute(
            _INSERT_FETCH, (path, fetched_at, sha256, http_status, rows_parsed, rows_rejected)
        )


def _cached(row: Sequence[Any]) -> CachedFile:
    path, digest, fetched_at, stored = row
    content = gzip.decompress(bytes(stored))
    if sha256_hex(content) != digest:
        raise ContractViolation(f"{path}: önbellekteki içerik kayıtlı sha256'yı üretmiyor")
    return CachedFile(path=path, sha256=digest, fetched_at=fetched_at, content=content)


def load_files(conn: psycopg.Connection[Any], paths: Sequence[str]) -> Mapping[str, CachedFile]:
    """İstenen yollardan önbellekte OLANLAR; eksik yolun kararı çağıranındır."""
    with conn.cursor() as cur:
        cur.execute(_LOAD_FILES, (list(paths),))
        rows = cur.fetchall()
    return MappingProxyType({row[0]: _cached(row) for row in rows})
```

- [ ] **Step 4: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_history_store.py -q`
Expected: PASS (12 passed)

- [ ] **Step 5: Senkron testlerini yaz**

Create `tests/test_history_sync.py`:
```python
"""`history/sync.py`: sahte veritabanı, `httpx.MockTransport`, sentetik CSV — ağ yok."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
from protego import Protego

from football_edge.collector import ContractViolation
from football_edge.history.catalog import Catalog, declared_paths, load_catalog
from football_edge.history.holdout import DEV, HOLDOUT, POST, HoldoutKey, HoldoutLocked, period_of
from football_edge.history.lock import LockViolation, build_lock
from football_edge.history.store import save_file
from football_edge.history.sync import SyncReport, _load_all, load_matches, mutable_paths, sync
from football_edge.history.types import HistMatch
from tests.fake_hist_db import FakeHistDb, at
from tests.fake_sources import fake_source
from tests.history_csv import (
    BRA,
    E0,
    EXTRA_NEW,
    MAIN_2526,
    MAIN_2627,
    csv_bytes,
    extra_row,
    main_row,
)

CATALOG = Catalog(current_season="2627", leagues=(E0, BRA))
OLD, CURRENT, EXTRA_FILE = "/mmz4281/2526/E0.csv", "/mmz4281/2627/E0.csv", "/new/BRA.csv"
FILES: Mapping[str, bytes] = {
    OLD: csv_bytes(MAIN_2526, [main_row(n) for n in range(3)]),
    CURRENT: csv_bytes(MAIN_2627, [main_row(n, {"Date": "22/08/2026"}) for n in range(2)]),
    EXTRA_FILE: csv_bytes(EXTRA_NEW, [extra_row(n) for n in range(2)]),
}
OPEN_ROBOTS = "User-agent: *\nDisallow:\n"
# Dönem karışık önbellek: E0'ın 2025/26 dosyası holdout, 2026/27 dosyası sonrası; ek lig dosyası
# bütün yılları taşır — geliştirme, holdout ve sonrası birer satır.
PERIODS_FILES: Mapping[str, bytes] = {
    **FILES,
    EXTRA_FILE: csv_bytes(
        EXTRA_NEW,
        [
            extra_row(0, {"Season": "2024", "Date": "20/10/2024"}),
            extra_row(1, {"Season": "2025", "Date": "16/08/2025"}),
            extra_row(2, {"Season": "2026", "Date": "20/08/2026"}),
        ],
    ),
}


class Site:
    """football-data taklidi: yol → yanıt; gelen her isteğin yolunu kaydeder."""

    def __init__(self, files: Mapping[str, bytes], status: Mapping[str, int] | None = None) -> None:
        self.files = dict(files)
        self.status = dict(status or {})
        self.requested: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requested = [*self.requested, request.url.path]
        code = self.status.get(request.url.path, 200)
        body = self.files.get(request.url.path, b"") if code == 200 else b""
        return httpx.Response(code, content=body, headers={"last-modified": "Mon, 21 Sep 2026"})


def ticking() -> Callable[[], datetime]:
    minutes = iter(range(60))
    return lambda: at(next(minutes))


def run(
    db: FakeHistDb,
    site: Site,
    paths: tuple[str, ...] = (OLD, CURRENT, EXTRA_FILE),
    *,
    robots: str = OPEN_ROBOTS,
    declared: tuple[str, ...] = (OLD, CURRENT, EXTRA_FILE),
) -> SyncReport:
    source = fake_source(
        id="football-data", base_url="https://football-data.co.uk", declared_paths=declared
    )
    with httpx.Client(transport=httpx.MockTransport(site)) as client:
        return sync(
            db,
            client,
            source=source,
            parser=Protego.parse(robots),
            catalog=CATALOG,
            paths=paths,
            now=ticking(),
        )


def test_mutable_paths_are_the_current_main_seasons_and_every_extra_file() -> None:
    assert mutable_paths(CATALOG) == (CURRENT, EXTRA_FILE)

    real = load_catalog(Path(__file__).resolve().parent.parent / "config/history_leagues.yaml")
    paths = mutable_paths(real)
    assert len(paths) == 22 + 16
    assert set(paths) <= set(declared_paths(real))
    assert all(path.startswith(("/mmz4281/2627/", "/new/")) for path in paths)


def test_sync_caches_every_file_and_logs_every_fetch() -> None:
    db, site = FakeHistDb(), Site(FILES)

    report = run(db, site)

    assert report == SyncReport(requested=3, changed=3, unchanged=0, failed=(), rejected_rows=0)
    assert site.requested == [OLD, CURRENT, EXTRA_FILE]
    assert set(db.files) == {OLD, CURRENT, EXTRA_FILE}
    assert [(row["path"], row["http_status"], row["rows_parsed"]) for row in db.fetches] == [
        (OLD, 200, 3),
        (CURRENT, 200, 2),
        (EXTRA_FILE, 200, 2),
    ]
    assert [row["fetched_at"] for row in db.fetches] == [at(0), at(1), at(2)]
    assert all(row["sha256"] for row in db.fetches)
    assert db.files[OLD]["http_last_modified"] == "Mon, 21 Sep 2026", "Last-Modified kayboldu"
    assert db.commits == 3, "her dosya kendi işleminde commit'lenmeli"


def test_an_unchanged_second_run_rewrites_nothing_but_still_logs_the_fetches() -> None:
    db, site = FakeHistDb(), Site(FILES)
    run(db, site)

    report = run(db, site)

    assert (report.changed, report.unchanged, report.failed) == (0, 3, ())
    assert len(db.fetches) == 6


def test_a_failing_file_is_named_and_the_others_still_sync() -> None:
    db, site = FakeHistDb(), Site(FILES, status={OLD: 404})

    report = run(db, site)

    ((path, reason),) = report.failed
    assert path == OLD and "404" in reason and "\n" not in reason
    assert (report.changed, report.unchanged) == (2, 0)
    assert set(db.files) == {CURRENT, EXTRA_FILE}
    assert (db.fetches[0]["sha256"], db.fetches[0]["http_status"]) == (None, 404)


def test_a_file_that_breaks_the_contract_never_replaces_the_cached_version() -> None:
    db = FakeHistDb()
    run(db, Site(FILES))
    good = db.files[EXTRA_FILE]["sha256"]
    broken = csv_bytes(tuple(n for n in EXTRA_NEW if n != "Res"), [extra_row(0)])

    report = run(db, Site({**FILES, EXTRA_FILE: broken}))

    ((path, reason),) = report.failed
    assert path == EXTRA_FILE and "ContractViolation" in reason and "zorunlu sütun" in reason
    assert db.files[EXTRA_FILE]["sha256"] == good
    assert (db.fetches[-1]["sha256"], db.fetches[-1]["http_status"]) == (None, None)


def test_rejected_rows_under_the_limit_are_counted_not_hidden() -> None:
    rows = [main_row(n) for n in range(199)] + [main_row(199, {"FTR": "A"})]
    db = FakeHistDb()

    report = run(db, Site({**FILES, OLD: csv_bytes(MAIN_2526, rows)}), (OLD,))

    assert (report.changed, report.rejected_rows) == (1, 1)
    assert (db.fetches[0]["rows_parsed"], db.fetches[0]["rows_rejected"]) == (199, 1)
    assert db.files[OLD]["row_count"] == 199


def test_an_undeclared_path_is_never_requested() -> None:
    db, site = FakeHistDb(), Site(FILES)

    report = run(db, site, declared=(OLD, CURRENT))

    assert [path for path, _ in report.failed] == [EXTRA_FILE]
    assert "SourceBlocked" in report.failed[0][1]
    assert EXTRA_FILE not in site.requested


def test_a_path_robots_forbids_is_never_requested() -> None:
    db, site = FakeHistDb(), Site(FILES)

    report = run(db, site, robots="User-agent: *\nDisallow: /new/\n")

    assert [path for path, _ in report.failed] == [EXTRA_FILE]
    assert EXTRA_FILE not in site.requested


def test_a_failed_commit_is_a_failure_not_a_change() -> None:
    """G1: commit düşerse satırlar geri alınır; sayaç onları yazılmış saymamalı."""
    first = iter([True])
    db = FakeHistDb(commit_fails=lambda _: next(first, False))

    report = run(db, Site(FILES))

    assert [path for path, _ in report.failed] == [OLD]
    assert "CommitFailed" in report.failed[0][1]
    assert report.changed == 2 and OLD not in db.files
    assert report.requested == report.changed + report.unchanged + len(report.failed)


# ── _load_all / load_matches ────────────────────────────────────────────────


def test_load_all_returns_every_cached_season_in_date_kickoff_home_order() -> None:
    rows_old = [
        main_row(0, {"Date": "23/08/2025"}),
        main_row(3, {"Date": "16/08/2025", "Time": "17:30"}),
        main_row(2, {"Date": "16/08/2025", "Time": "12:30"}),
        main_row(1, {"Date": "16/08/2025", "Time": "12:30"}),
        main_row(9, {"Date": "16/08/2025", "Time": ""}),
    ]
    db = FakeHistDb()
    run(db, Site({**FILES, OLD: csv_bytes(MAIN_2526, rows_old)}))

    loaded = _load_all(db, CATALOG)

    assert set(loaded) == {"E0", "BRA"}
    e0 = loaded["E0"]
    assert [(match.date, match.home) for match in e0] == [
        (date(2025, 8, 16), "Ev 9"),
        (date(2025, 8, 16), "Ev 1"),
        (date(2025, 8, 16), "Ev 2"),
        (date(2025, 8, 16), "Ev 3"),
        (date(2025, 8, 23), "Ev 0"),
        (date(2026, 8, 22), "Ev 0"),
        (date(2026, 8, 22), "Ev 1"),
    ]
    assert e0[0].kickoff is None and e0[1].kickoff == datetime(2025, 8, 16, 11, 30, tzinfo=UTC)
    assert {match.season for match in e0} == {"2526", "2627"}
    assert len(loaded["BRA"]) == 2


def test_load_matches_refuses_an_incomplete_cache() -> None:
    db = FakeHistDb()
    run(db, Site(FILES), (OLD, EXTRA_FILE))

    with pytest.raises(ContractViolation, match=f"1 dosya yok.*{CURRENT}"):
        load_matches(db, CATALOG)


def _periods(loaded: Mapping[str, tuple[HistMatch, ...]]) -> dict[str, list[str]]:
    return {code: sorted({period_of(m.date) for m in matches}) for code, matches in loaded.items()}


def _cached_periods() -> FakeHistDb:
    db = FakeHistDb()
    run(db, Site(PERIODS_FILES))
    return db


@pytest.mark.leakage
def test_load_matches_without_a_key_never_hands_out_a_holdout_row() -> None:
    """R96: holdout satırları `history/`den anahtarsız çıkmaz — `_load_all` onları taşır."""
    db = _cached_periods()

    everything, loaded = _load_all(db, CATALOG), load_matches(db, CATALOG)

    assert _periods(everything) == {"E0": [HOLDOUT, POST], "BRA": [DEV, HOLDOUT, POST]}
    assert _periods(loaded) == {"E0": [POST], "BRA": [DEV, POST]}
    assert [match.date for match in loaded["BRA"]] == [date(2024, 10, 20), date(2026, 8, 20)]


@pytest.mark.leakage
def test_a_hand_built_key_does_not_open_the_holdout() -> None:
    forged = HoldoutKey(opened_at=at(0), purpose="deneme", git_sha="0" * 40)

    with pytest.raises(HoldoutLocked):
        load_matches(_cached_periods(), CATALOG, key=forged)


@pytest.mark.leakage
def test_the_lock_is_checked_over_every_period_before_the_holdout_is_filtered_out() -> None:
    """Süzgeçten SONRA doğrulansaydı kilitteki holdout özeti eksik satırlarla tutmazdı."""
    db = _cached_periods()
    lock = build_lock(_load_all(db, CATALOG), locked_at=date(2026, 9, 28))

    loaded = load_matches(db, CATALOG, lock=lock)

    assert _periods(loaded) == {"E0": [POST], "BRA": [DEV, POST]}


@pytest.mark.leakage
def test_a_changed_holdout_row_breaks_the_lock_although_it_is_never_returned() -> None:
    db = _cached_periods()
    lock = build_lock(_load_all(db, CATALOG), locked_at=date(2026, 9, 28))
    rescored = [main_row(0, {"FTHG": "3"}), main_row(1), main_row(2)]
    run(db, Site({**PERIODS_FILES, OLD: csv_bytes(MAIN_2526, rescored)}))

    with pytest.raises(LockViolation):
        load_matches(db, CATALOG, lock=lock)


def test_load_matches_rechecks_the_contract_of_every_cached_file() -> None:
    """Önbelleğe bugünkü sözleşmeyi geçmeyen bir dosya girdiyse (eski kod, elle yazım) yükleme
    onu sessizce eksik satırla kullanmaz."""
    db = FakeHistDb()
    run(db, Site(FILES))
    broken = csv_bytes(tuple(n for n in MAIN_2627 if n != "FTAG"), [main_row(0)])
    save_file(db, path=CURRENT, content=broken, fetched_at=at(30), last_modified=None, row_count=0)

    with pytest.raises(ContractViolation, match="zorunlu sütun"):
        load_matches(db, CATALOG)
```

- [ ] **Step 6: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_history_sync.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.history.sync'`

- [ ] **Step 7: Senkronu yaz**

Create `src/football_edge/history/sync.py`:
```python
"""football-data senkronu: çekme → doğrulama → önbellek; önbellekten maç yükleme (tasarım §4.1).

İstek yolu YALNIZ `collector._guarded_get`tir: robots her yolda ve yönlendirmenin her
sıçramasında sorulur, istekler arası `crawl_delay_seconds` beklenir. Beyan edilmemiş bir yol
istenmez (R7): `declared_paths` gerçekten çekilen yollardır.

Bir dosyanın arızası ötekileri durdurmaz ama SESSİZ de geçmez: `SyncReport.failed` onu nedeniyle
taşır ve CLI turu kırmızıya çevirir (Ruling 6).

Holdout satırları bu paketten anahtarsız ÇIKMAZ (R96): `load_matches` geliştirme ve sonrası
dönemlerini verir, holdout'u yalnız `open_holdout`un kurduğu anahtarla. Bütün dönemleri dönen
`_load_all` modüle özeldir; onu yalnız kilit komutu (`history/__main__.py`) anar — Task 3'ün AST
kuralı (`tests/test_holdout_access_rule.py`) başka her anmayı kırmızıya çevirir.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import Any

import httpx
import psycopg
from protego import Protego

from football_edge.collector import ContractViolation, _guarded_get
from football_edge.history.catalog import (
    EXTRA,
    Catalog,
    HistoryLeague,
    declared_paths,
    file_paths,
    season_of_path,
)
from football_edge.history.football_data import check_quality, parse_file
from football_edge.history.holdout import DEV, HOLDOUT, POST, HoldoutKey, select_periods
from football_edge.history.lock import HistoryLock, verify_lock
from football_edge.history.store import load_files, log_fetch, save_file, sha256_hex
from football_edge.history.types import HistMatch
from football_edge.sources import Source, SourceBlocked

LOGGER = logging.getLogger("football_edge.history.sync")

SOURCE_ID: str = "football-data"
TIMEOUT_SECONDS = 60.0
# Saati olmayan maç (2019/20 öncesi ana ligler) aynı günün saatlilerinden önce sıralanır.
_NO_KICKOFF = datetime.min.replace(tzinfo=UTC)
# Anahtarsız okunabilen dönemler; HOLDOUT yalnız geçerli bir `HoldoutKey` ile eklenir.
_OPEN_PERIODS = frozenset({DEV, POST})


@dataclass(frozen=True)
class SyncReport:
    requested: int
    changed: int
    unchanged: int
    failed: tuple[tuple[str, str], ...]  # (yol, neden)
    rejected_rows: int


@dataclass(frozen=True)
class _Synced:
    changed: bool
    rejected: int


def mutable_paths(catalog: Catalog) -> tuple[str, ...]:
    """Hâlâ değişebilen dosyalar: güncel sezonun ana lig dosyaları ve bütün ek lig dosyaları."""
    return tuple(
        sorted(
            file_paths(league, current_season=catalog.current_season)[-1]
            for league in catalog.leagues
        )
    )


def _league_of(catalog: Catalog, path: str) -> HistoryLeague:
    for league in catalog.leagues:
        if path in file_paths(league, current_season=catalog.current_season):
            return league
    raise ContractViolation(f"{SOURCE_ID}: {path} katalogda yok")


def _season_for(league: HistoryLeague, path: str) -> str | None:
    return None if league.kind == EXTRA else season_of_path(path)


def _sync_one(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    *,
    source: Source,
    parser: Protego,
    catalog: Catalog,
    path: str,
    fetched_at: datetime,
) -> _Synced:
    if path not in source.declared_paths:
        raise SourceBlocked(f"{source.id}: {path} declared_paths'te yok — istek atılmadı")
    league = _league_of(catalog, path)
    season = _season_for(league, path)
    response = _guarded_get(client, source, path, parser, timeout=TIMEOUT_SECONDS)
    result = parse_file(response.content, league=league, season=season)
    check_quality(result, path=path, league=league, season=season)
    changed = save_file(
        conn,
        path=path,
        content=response.content,
        fetched_at=fetched_at,
        last_modified=response.headers.get("last-modified"),
        row_count=len(result.matches),
    )
    log_fetch(
        conn,
        path=path,
        fetched_at=fetched_at,
        sha256=sha256_hex(response.content),
        http_status=response.status_code,
        rows_parsed=len(result.matches),
        rows_rejected=len(result.rejected),
    )
    conn.commit()
    return _Synced(changed=changed, rejected=len(result.rejected))


def _reason(error: Exception) -> str:
    return " ".join(f"{type(error).__name__}: {error}".split())


def _record_failure(
    conn: psycopg.Connection[Any], *, path: str, fetched_at: datetime, error: Exception
) -> None:
    """Başarısız deneme de günlüğe girer — istek hiç atılmamış olsa bile (robots, beyan):
    sha256 NULL, yani önbelleğe girmedi; http_status yalnız HTTP hatasında dolu."""
    status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
    log_fetch(
        conn,
        path=path,
        fetched_at=fetched_at,
        sha256=None,
        http_status=status,
        rows_parsed=0,
        rows_rejected=0,
    )
    conn.commit()


def sync(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    *,
    source: Source,
    parser: Protego,
    catalog: Catalog,
    paths: Sequence[str],
    now: Callable[[], datetime],
) -> SyncReport:
    done: tuple[_Synced, ...] = ()
    failed: tuple[tuple[str, str], ...] = ()
    for path in paths:
        fetched_at = now()
        try:
            synced = _sync_one(
                conn,
                client,
                source=source,
                parser=parser,
                catalog=catalog,
                path=path,
                fetched_at=fetched_at,
            )
        except Exception as error:
            # Sayaçlar yalnız commit'ten SONRA artar: düşen commit "yazıldı" sayılmaz (G1).
            conn.rollback()
            LOGGER.exception("yol=%s senkronlanamadı, diğerlerine devam", path)
            _record_failure(conn, path=path, fetched_at=fetched_at, error=error)
            failed = (*failed, (path, _reason(error)))
            continue
        done = (*done, synced)
    changed = sum(1 for entry in done if entry.changed)
    return SyncReport(
        requested=len(paths),
        changed=changed,
        unchanged=len(done) - changed,
        failed=failed,
        rejected_rows=sum(entry.rejected for entry in done),
    )


def _order(match: HistMatch) -> tuple[date, datetime, str]:
    return (match.date, match.kickoff or _NO_KICKOFF, match.home)


def _parsed(path: str, content: bytes, league: HistoryLeague) -> tuple[HistMatch, ...]:
    season = _season_for(league, path)
    result = parse_file(content, league=league, season=season)
    check_quality(result, path=path, league=league, season=season)
    return result.matches


def _load_all(
    conn: psycopg.Connection[Any], catalog: Catalog
) -> Mapping[str, tuple[HistMatch, ...]]:
    """Lig kodu → bütün sezonların BÜTÜN dönemleri (holdout dahil), (tarih, başlama, ev) sırasıyla.

    Modüle özel (R96): yalnız `load_matches` ve kilit komutu anar. Önbellekte eksik dosya varsa ya
    da bir dosya bugünkü sözleşmeyi geçmiyorsa `ContractViolation`: eksik veriyle kurulan bir kilit
    ya da doğrulama başarı gibi görünürdü.
    """
    paths = declared_paths(catalog)
    files = load_files(conn, paths)
    missing = [path for path in paths if path not in files]
    if missing:
        raise ContractViolation(
            f"{SOURCE_ID}: önbellekte {len(missing)} dosya yok (ilki {missing[0]}) — "
            "önce `sync --all`"
        )
    return MappingProxyType(
        {
            league.code: tuple(
                sorted(
                    (
                        match
                        for path in file_paths(league, current_season=catalog.current_season)
                        for match in _parsed(path, files[path].content, league)
                    ),
                    key=_order,
                )
            )
            for league in catalog.leagues
        }
    )


def load_matches(
    conn: psycopg.Connection[Any],
    catalog: Catalog,
    *,
    lock: HistoryLock | None = None,
    key: HoldoutKey | None = None,
) -> Mapping[str, tuple[HistMatch, ...]]:
    """Lig kodu → geliştirme + sonrası dönemleri; holdout yalnız `open_holdout`un anahtarıyla (R96).

    `lock` verilirse doğrulama süzgeçten ÖNCE, bütün satırlar üzerinde koşar: değişen bir holdout
    satırı da `LockViolation` verir, oysa o satır hiç dışarı verilmez. Elle kurulan anahtar
    `select_periods`te `HoldoutLocked` verir.
    """
    everything = _load_all(conn, catalog)
    if lock is not None:
        verify_lock(lock, everything)
    periods = _OPEN_PERIODS if key is None else _OPEN_PERIODS | {HOLDOUT}
    return MappingProxyType(
        {
            code: select_periods(matches, periods=periods, key=key)
            for code, matches in everything.items()
        }
    )
```

- [ ] **Step 8: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_history_sync.py -q`
Expected: PASS (16 passed)
Run: `uv run pytest tests/test_history_sync.py -q -m leakage`
Expected: `4 passed, 12 deselected`

- [ ] **Step 9: Kaynak kaydı testlerini yaz**

Create `tests/test_history_registry.py`:
```python
"""`config/sources.yaml`daki `football-data` kaydı katalogdan türer (tasarım D20, R7, R59).

`declared_paths` gerçekten çekilen yollardır; `sync` beyan edilmemiş yolu istemez. Bu test iki
listenin EŞİT olduğunu zorlar: fetched ⊆ declared bağı yapıdan gelir, `sources.py` değişmez.
"""

from __future__ import annotations

from pathlib import Path

from football_edge.history.catalog import declared_paths, load_catalog
from football_edge.history.sync import SOURCE_ID
from football_edge.sources import Source, audit_offline, load_sources

REPO = Path(__file__).resolve().parent.parent
ROBOTS = REPO / "config/robots"


def _entry() -> Source:
    (entry,) = [s for s in load_sources(REPO / "config/sources.yaml") if s.id == SOURCE_ID]
    return entry


def test_declared_paths_are_exactly_the_catalog_expansion() -> None:
    declared = _entry().declared_paths
    expected = set(declared_paths(load_catalog(REPO / "config/history_leagues.yaml")))

    missing, extra = sorted(expected - set(declared)), sorted(set(declared) - expected)
    assert (missing, extra) == ([], []), (
        f"eksik {missing[:3]}…, fazla {extra[:3]}… — declared_paths'i katalogdan yeniden üret"
    )
    assert len(declared) == len(expected), "declared_paths'te yinelenen yol var"


def test_the_source_is_honest_polite_and_robots_based() -> None:
    entry = _entry()

    assert entry.base_url == "https://football-data.co.uk"
    assert entry.user_agent == "football-edge/0.1 (+https://github.com/popiliadam/football-edge)"
    assert entry.crawl_delay_seconds == 3.0
    assert (entry.enabled, entry.access_basis, entry.terms_url) == (True, "robots", "")


def test_the_committed_snapshot_is_the_measured_open_policy() -> None:
    text = (ROBOTS / f"{SOURCE_ID}.txt").read_text(encoding="utf-8")

    rules = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    assert rules == ["User-agent: *", "Disallow:"]


def test_every_declared_path_passes_the_offline_source_audit() -> None:
    entry = _entry()

    assert audit_offline((entry,), ROBOTS, entry.robots_verified_at) == ()
```

- [ ] **Step 10: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_history_registry.py -q`
Expected: FAIL (4 failed) — üçünde `ValueError: not enough values to unpack (expected 1, got 0)`
(kayıt yok), birinde `FileNotFoundError: …/config/robots/football-data.txt`

- [ ] **Step 11: robots anlık görüntüsünü ve kaynak kaydını ekle**

robots.txt 2026-09-22'de runner'dan ölçüldü (sunucu CRLF döndürür; `scripts/robots_drift.py`
satır sonlarını `\n`e indirip uçları kırparak karşılaştırır, LF güvenlidir). Tam bu komutla yaz:
```bash
printf '%s\n' '# Robots.txt file created by http://www.webtoolcentral.com' \
  '# For domain: http://www.football-data.co.uk' '' '# All robots will spider the domain' \
  'User-agent: *' 'Disallow:' > config/robots/football-data.txt
```
Beklenen dosya:
```text
# Robots.txt file created by http://www.webtoolcentral.com
# For domain: http://www.football-data.co.uk

# All robots will spider the domain
User-agent: *
Disallow:
```

`config/sources.yaml`in SONUNA (understat kaydından sonra, boş satırla ayrılmış) kaydın başını
ekle — `declared_paths` son anahtardır:
```bash
cat >> config/sources.yaml <<'EOF'

  - id: football-data
    base_url: https://football-data.co.uk
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 3.0
    robots_verified_at: 2026-09-22
    enabled: true
    access_basis: robots
    terms_url: ''
    note: >-
      Faz 2 tarihsel taban (tasarım D1, D7, D20). robots.txt `User-agent: *` + boş `Disallow:`
      (runner'dan ölçüldü 2026-09-22): her yol izinli, Crawl-delay yok; 3 sn kendi nezaket
      aralığımız. Kanonik adres kök alan adı (`www` 302 veriyor). Türkiye'den TLS reset: çekme
      yalnız runner'da (`history.yml`). declared_paths ELLE DÜZENLENMEZ, `config/
      history_leagues.yaml`dan üretilir (komut: planın Task 6'sı) — tests/test_history_registry.py
      iki listenin eşitliğini zorlar; yeni sezonda önce katalog, sonra bu liste. Veri lisansı açık
      (spec §10/2): ham satır yalnız özel veritabanında, depoya ve loga girmez.
    declared_paths:
EOF
```
Ardından listeyi katalogdan üret ve aynı dosyaya ekle (500 satır, `      - /mmz4281/0506/B1.csv`
… `      - /new/USA.csv`; ELLE yazılmaz):
```bash
uv run python -c 'from pathlib import Path; from football_edge.history.catalog import declared_paths, load_catalog; print("\n".join(f"      - {p}" for p in declared_paths(load_catalog(Path("config/history_leagues.yaml")))))' >> config/sources.yaml
```
Denetim: `tail -3 config/sources.yaml` → son satır `      - /new/USA.csv`;
`grep -c '^      - /mmz4281/\|^      - /new/' config/sources.yaml` → `500`.

- [ ] **Step 12: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_history_registry.py -q`
Expected: PASS (4 passed)
Run: `uv run python -m football_edge.collect sources-audit`
Expected: `kaynak politikası: TEMİZ`
Run: `uv run pytest tests/test_robots_refresh.py tests/test_sources.py -q`
Expected: PASS (gerçek kayıt defterini okuyan testler yeni kaydı da taşır)

- [ ] **Step 13: CLI testlerini yaz**

Create `tests/test_history_cli.py`:
```python
"""`python -m football_edge.history` sözleşmesi: yollar, çıkış kodları, kilit, log kurulumu.

Kilit komutları GERÇEK yoldan koşar: sentetik dosyalar önce `sync --all` ile sahte veritabanına
senkronlanır; `lock --write` bütün dönemleri (`_load_all`), `lock --verify` `load_matches(lock=)`
üzerinden okur (R96). Hiçbir iç fonksiyon yamalanmaz.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest

from football_edge import collect
from football_edge.history import __main__ as cli
from football_edge.history.holdout import DEV, HOLDOUT
from football_edge.history.lock import load_lock
from tests.fake_hist_db import FakeHistDb
from tests.history_csv import MAIN_2526, csv_bytes, main_row
from tests.test_history_sync import CURRENT, EXTRA_FILE, FILES, OLD, Site

# 2024/25 ana lig dosyası geliştirme dönemi; OLD (2025/26) holdout, CURRENT (2026/27) sonrası, ek
# lig dosyası (FILES) holdout.
DEV_FILE = "/mmz4281/2425/E0.csv"
DEV_DAY, HOLDOUT_DAY = "17/08/2024", "16/08/2025"
CLI_FILES = {
    **FILES,
    DEV_FILE: csv_bytes(MAIN_2526, [main_row(n, {"Date": DEV_DAY}) for n in range(2)]),
}

CATALOG_YAML = """
current_season: "2627"
leagues:
  - {code: E0, league_id: eng.1, name: "Premier League", country: England, tier: 1, kind: main,
     first_season: "2425", odds_api_key: "soccer_epl"}
  - {code: BRA, league_id: bra.1, name: "Serie A", country: Brazil, tier: 1, kind: extra,
     first_season: "", odds_api_key: ""}
"""
SOURCES_YAML = """
sources:
  - id: football-data
    base_url: https://football-data.co.uk
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-09-22
    declared_paths:
      - /mmz4281/2425/E0.csv
      - /mmz4281/2526/E0.csv
      - /mmz4281/2627/E0.csv
      - /new/BRA.csv
    enabled: true
    access_basis: robots
    terms_url: ''
    note: test
"""


def _patch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, site: Site, *, sources: str = SOURCES_YAML
) -> FakeHistDb:
    (tmp_path / "catalog.yaml").write_text(CATALOG_YAML, encoding="utf-8")
    (tmp_path / "sources.yaml").write_text(sources, encoding="utf-8")
    (tmp_path / "robots").mkdir()
    (tmp_path / "robots/football-data.txt").write_text(
        "User-agent: *\nDisallow:\n", encoding="utf-8"
    )
    monkeypatch.setattr(cli, "CATALOG_PATH", tmp_path / "catalog.yaml")
    monkeypatch.setattr(cli, "SOURCES_PATH", tmp_path / "sources.yaml")
    monkeypatch.setattr(cli, "ROBOTS_DIR", tmp_path / "robots")
    db = FakeHistDb()
    monkeypatch.setattr(cli, "connect", lambda: db)
    real_client = httpx.Client  # yama sonrası httpx.Client bu lambda olur
    monkeypatch.setattr(
        cli.httpx, "Client", lambda: real_client(transport=httpx.MockTransport(site))
    )
    return db


def test_sync_fetches_only_the_mutable_files_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    site = Site(CLI_FILES)
    _patch(monkeypatch, tmp_path, site)

    assert cli.main(["sync"]) == 0

    assert site.requested == [CURRENT, EXTRA_FILE]
    assert "2 yol istendi, 2 değişti, 0 aynı, 0 başarısız" in caplog.text


def test_sync_all_fetches_every_declared_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    site = Site(CLI_FILES)
    db = _patch(monkeypatch, tmp_path, site)

    assert cli.main(["sync", "--all"]) == 0

    assert site.requested == [DEV_FILE, OLD, CURRENT, EXTRA_FILE]
    assert set(db.files) == {DEV_FILE, OLD, CURRENT, EXTRA_FILE}


def test_a_failed_file_turns_the_run_red_with_the_source_code_and_its_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    _patch(monkeypatch, tmp_path, Site(CLI_FILES, status={CURRENT: 503}))

    assert cli.main(["sync"]) == collect.EXIT_SOURCE_FAILED

    assert f"başarısız: {CURRENT}" in caplog.text
    assert "1 başarısız" in caplog.text


def test_a_disabled_source_is_never_fetched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    site = Site(CLI_FILES)
    _patch(monkeypatch, tmp_path, site, sources=SOURCES_YAML.replace("true", "false"))

    with pytest.raises(RuntimeError, match="enabled=false"):
        cli.main(["sync"])
    assert site.requested == []


def test_the_redacting_log_setup_comes_before_anything_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bağlantı hatası DSN parolasını taşıyabilir: kök handler ondan ÖNCE sarılmış olmalı."""
    calls: list[str] = []

    def catalog(path: Path) -> None:
        calls.append("catalog")
        raise RuntimeError("dur")

    monkeypatch.setattr(cli, "configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(cli, "load_catalog", catalog)

    with pytest.raises(RuntimeError, match="dur"):
        cli.main(["sync"])
    assert calls == ["logging", "catalog"]


def test_the_lock_violation_code_is_its_own() -> None:
    taken = {value for name, value in vars(collect).items() if name.startswith("EXIT_")}

    assert cli.EXIT_LOCK_VIOLATION == 9
    assert cli.EXIT_LOCK_VIOLATION not in taken | {0, 1}


# ── lock ────────────────────────────────────────────────────────────────────


def _synced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Site, Path]:
    """Dört dosyayı senkronlar ve kilidi yazar; (site, kilit yolu) döner."""
    site = Site(CLI_FILES)
    _patch(monkeypatch, tmp_path, site)
    target = tmp_path / "history_lock.yaml"
    assert cli.main(["sync", "--all"]) == 0
    assert cli.main(["lock", "--write", str(target)]) == 0
    return site, target


def _rescored(path: str) -> bytes:
    """`path`in ilk maçının ev golü 2 → 3 (sonuç yine H): kilitli bir satır değişir."""
    day, count = {DEV_FILE: (DEV_DAY, 2), OLD: (HOLDOUT_DAY, 3)}[path]
    rows = [main_row(n, {"Date": day, "FTHG": "3" if n == 0 else "2"}) for n in range(count)]
    return csv_bytes(MAIN_2526, rows)


@pytest.mark.leakage
def test_lock_write_digests_every_period_and_verify_accepts_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`lock --write` holdout özetini de yazar (`_load_all`); `load_matches` holdout vermez."""
    _, target = _synced(monkeypatch, tmp_path)

    written = load_lock(target)

    assert (written.leagues["E0"][DEV].rows, written.leagues["E0"][HOLDOUT].rows) == (2, 3)
    assert (written.leagues["BRA"][DEV].rows, written.leagues["BRA"][HOLDOUT].rows) == (0, 2)
    assert cli.main(["lock", "--verify", str(target)]) == 0


@pytest.mark.leakage
@pytest.mark.parametrize("path", [DEV_FILE, OLD], ids=["gelistirme", "holdout"])
def test_lock_verify_exits_9_when_a_locked_row_changed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture, path: str
) -> None:
    """Holdout satırı dışarı hiç verilmez ama değişikliği yine kilide takılır (R96)."""
    site, target = _synced(monkeypatch, tmp_path)
    site.files = {**site.files, path: _rescored(path)}
    assert cli.main(["sync", "--all"]) == 0

    assert cli.main(["lock", "--verify", str(target)]) == cli.EXIT_LOCK_VIOLATION
    assert "KİLİT İHLALİ" in caplog.text


@pytest.mark.leakage
@pytest.mark.parametrize(
    "text", ["canonical_version: [\n", "canonical_version: 1\n"], ids=["bozuk-yaml", "eksik-alan"]
)
def test_a_broken_lock_file_exits_9_not_with_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture, text: str
) -> None:
    """R99: `load_lock` yapı hatasında LockViolation fırlatır; CLI onu da exit 9 ile karşılar."""
    _patch(monkeypatch, tmp_path, Site(CLI_FILES))
    target = tmp_path / "history_lock.yaml"
    target.write_text(text, encoding="utf-8")

    assert cli.main(["lock", "--verify", str(target)]) == cli.EXIT_LOCK_VIOLATION
    assert "KİLİT İHLALİ" in caplog.text


@pytest.mark.leakage
@pytest.mark.parametrize("flag", ["--write", "--verify"])
def test_lock_refuses_an_unusable_cache_with_the_source_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag: str
) -> None:
    _, target = _synced(monkeypatch, tmp_path)
    before = target.read_text(encoding="utf-8")
    monkeypatch.setattr(cli, "connect", lambda: FakeHistDb())  # önbellek boş

    assert cli.main(["lock", flag, str(target)]) == collect.EXIT_SOURCE_FAILED
    assert target.read_text(encoding="utf-8") == before, "eksik önbellekle kilit yazıldı"
```

- [ ] **Step 14: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_history_cli.py -q`
Expected: FAIL — `ImportError: cannot import name '__main__' from 'football_edge.history'`

- [ ] **Step 15: CLI'ı yaz**

Create `src/football_edge/history/__main__.py`:
```python
"""`python -m football_edge.history` — tarihsel taban CLI'ı (tasarım §4.1, §5.2).

    sync [--all]         değişken dosyalar (güncel sezon + ek ligler); --all: bütün beyanlı yollar
    lock --write PATH    önbellekten kilit dosyası üretir (geliştirme + holdout özetleri)
    lock --verify PATH   önbelleği kilide karşı doğrular; ihlal ya da bozuk kilit: exit 9

Kilit yazımı holdout satırlarının ÖZETİNE ihtiyaç duyar, satırlarına değil: bütün dönemleri dönen
`sync._load_all`ı anabilen tek modül budur (R96, Task 3'ün AST kuralı); özet dosyaya yalnız sayı ve
sha256 olarak çıkar. Doğrulama `load_matches(..., lock=)` üzerinden: holdout satırı dışarı çıkmaz.

Çıktı `logging` iledir; kök handler `collect.configure_logging` ile redakte edilir (DSN parolası
bir psycopg hatasında log'a düşmesin). Yalnız toplu sayılar yazılır, ham satır yazılmaz.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from football_edge.collect import (
    EXIT_SOURCE_FAILED,
    ROBOTS_DIR,
    SOURCES_PATH,
    configure_logging,
)
from football_edge.collector import ContractViolation
from football_edge.db import connect
from football_edge.history.catalog import Catalog, declared_paths, load_catalog
from football_edge.history.holdout import DEV, HOLDOUT
from football_edge.history.lock import LockViolation, build_lock, dump_lock, load_lock
from football_edge.history.sync import (
    SOURCE_ID,
    SyncReport,
    _load_all,
    load_matches,
    mutable_paths,
    sync,
)
from football_edge.sources import Source, enabled_sources, load_sources, robots_for

LOGGER = logging.getLogger("football_edge.history")

CATALOG_PATH = Path("config/history_leagues.yaml")
# Kilit ihlali: kilitli dönemin bir satırı değişti ya da kayboldu (tasarım §5.2). Karar insanındır;
# `collect`in EXIT_* kodlarından (2–8) ve 0/1'den ayrı.
EXIT_LOCK_VIOLATION = 9


def _source() -> Source:
    """`enabled: false` kapatma anahtarıdır: kayıt yoksa ya da kapalıysa çekme hiç başlamaz."""
    for entry in enabled_sources(load_sources(SOURCES_PATH)):
        if entry.id == SOURCE_ID:
            return entry
    raise RuntimeError(f"{SOURCE_ID}: kaynak kaydı yok ya da enabled=false ({SOURCES_PATH})")


def _report(report: SyncReport) -> int:
    LOGGER.info(
        "%s: %d yol istendi, %d değişti, %d aynı, %d başarısız, %d satır reddedildi",
        SOURCE_ID,
        report.requested,
        report.changed,
        report.unchanged,
        len(report.failed),
        report.rejected_rows,
    )
    for path, reason in report.failed:
        LOGGER.error("başarısız: %s — %s", path, reason)
    return EXIT_SOURCE_FAILED if report.failed else 0


def _sync_command(catalog: Catalog, *, all_paths: bool) -> int:
    source = _source()
    parser = robots_for(source, ROBOTS_DIR)
    paths = declared_paths(catalog) if all_paths else mutable_paths(catalog)
    with connect() as conn, httpx.Client() as client:
        report = sync(
            conn,
            client,
            source=source,
            parser=parser,
            catalog=catalog,
            paths=paths,
            now=lambda: datetime.now(UTC),
        )
    return _report(report)


def _write_lock(catalog: Catalog, target: Path) -> int:
    with connect() as conn:
        matches = _load_all(conn, catalog)
    lock = build_lock(matches, locked_at=datetime.now(UTC).date())
    target.write_text(dump_lock(lock), encoding="utf-8")
    for code, digests in lock.leagues.items():
        LOGGER.info("%s: dev %d, holdout %d satır", code, digests[DEV].rows, digests[HOLDOUT].rows)
    LOGGER.info("kilit yazıldı: %s (%d lig)", target, len(lock.leagues))
    return 0


def _verify_lock(catalog: Catalog, target: Path) -> int:
    """Bozuk kilit dosyası da (R99: `load_lock` → LockViolation) ve veri farkı da exit 9."""
    try:
        lock = load_lock(target)
        with connect() as conn:
            load_matches(conn, catalog, lock=lock)
    except LockViolation as violation:
        LOGGER.error("KİLİT İHLALİ: %s", violation)
        return EXIT_LOCK_VIOLATION
    LOGGER.info("kilit doğrulandı: %s (%d lig)", target, len(lock.leagues))
    return 0


def _lock_command(catalog: Catalog, *, write: Path | None, verify: Path | None) -> int:
    try:
        if write is not None:
            return _write_lock(catalog, write)
        if verify is not None:
            return _verify_lock(catalog, verify)
    except ContractViolation as violation:
        # Eksik ya da sözleşmeyi geçmeyen önbellekle kilit ne yazılır ne doğrulanır.
        LOGGER.error("önbellek kullanılamaz: %s", violation)
        return EXIT_SOURCE_FAILED
    raise ValueError("lock: --write ya da --verify gerekli")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.history")
    commands = parser.add_subparsers(dest="command", required=True)
    sync_parser = commands.add_parser("sync", help="football-data dosyalarını önbelleğe çek")
    sync_parser.add_argument(
        "--all", action="store_true", help="bütün beyanlı yollar (ilk tam yükleme)"
    )
    lock_parser = commands.add_parser("lock", help="kilit dosyasını yaz ya da doğrula")
    target = lock_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--write", type=Path, metavar="PATH")
    target.add_argument("--verify", type=Path, metavar="PATH")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    catalog = load_catalog(CATALOG_PATH)
    if args.command == "sync":
        return _sync_command(catalog, all_paths=args.all)
    return _lock_command(catalog, write=args.write, verify=args.verify)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 16: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_history_cli.py -q`
Expected: PASS (13 passed)
Run: `uv run pytest tests/test_history_cli.py -q -m leakage`
Expected: `7 passed, 6 deselected`

- [ ] **Step 17: Workflow testlerini yaz**

Create `tests/test_history_workflow.py`:
```python
"""`history.yml`: dispatch-only, tek job, secret yalnız veritabanı adımlarında, alarm kuralları.

İzinli listeye (0008, controller Task 8) girince `tests/test_workflows.py`nin ALARMED testleri bu
dosyayı kendiliğinden kapsar; o güne kadar aynı kurallar burada, aynı fonksiyonlarla koşulur.
Senkron adımının kabuk gövdesi `uv` yerine bir sahteyle koşulur; runner'da yeşil verdiği ölçülmez.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from football_edge import collect
from tests import test_collect_workflows as collect_rules
from tests import test_workflows as workflow_rules
from tests.workflow_helpers import REPO, _index_of, _steps, _triggers

HISTORY = REPO / ".github/workflows/history.yml"
SYNC = "football_edge.history sync"
# DATABASE_URL'i alan adımlar, adlarıyla. Task 10 `selftest` adımını buraya ekler; başka hiçbir
# adım (checkout, secret taraması, üçüncü taraf setup-uv, `uv sync`, alarm) secret görmez.
DATABASE_STEPS: tuple[str, ...] = ("Senkron",)


def _document() -> dict[str, Any]:
    return dict(yaml.safe_load(HISTORY.read_text(encoding="utf-8")))


def _sync_index() -> int:
    index = _index_of(_steps(HISTORY), SYNC)
    assert index is not None, "history.yml senkronu hiç koşmuyor"
    return index


def test_history_is_dispatched_only_with_an_optional_boolean_all_input() -> None:
    """pg_cron yalnız `ref` gönderir: zorunlu girdi o turu reddettirirdi."""
    triggers = _triggers(HISTORY)

    assert set(triggers) == {"workflow_dispatch"}, f"beklenmeyen tetik: {sorted(triggers)}"
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"all"}
    spec = inputs["all"]
    assert (spec["type"], spec["default"], spec.get("required", False)) == ("boolean", False, False)


def test_history_is_a_single_job_so_the_shared_workflow_rules_can_read_it() -> None:
    """`workflow_helpers._steps` tek job varsayar; Task 10 selftest'i ADIM olarak ekler."""
    assert list(_document()["jobs"]) == ["history"]


def test_history_queues_in_its_own_concurrency_group() -> None:
    assert _document()["concurrency"] == {"group": "history", "cancel-in-progress": False}


def test_secrets_are_scanned_after_checkout_and_before_the_sync() -> None:
    steps = _steps(HISTORY)
    checkout = _index_of(steps, "actions/checkout", key="uses")
    scan = _index_of(steps, "scripts/check_secrets.sh")

    assert checkout is not None and scan is not None
    assert checkout < scan < _sync_index()


def test_only_the_database_steps_get_a_secret_and_only_the_database_one() -> None:
    """Secret workflow ya da job `env`ine taşınırsa secret taramasına, `setup-uv` eylemine,
    `uv sync`e ve alarm adımlarına da açılır. İzinli adımlar DATABASE_STEPS'te; senkron biri."""
    text = HISTORY.read_text(encoding="utf-8")
    steps = _steps(HISTORY)
    allowed = [index for index, step in enumerate(steps) if step.get("name") in DATABASE_STEPS]

    assert len(allowed) == len(DATABASE_STEPS), f"adı bulunamayan adım: {DATABASE_STEPS}"
    assert _sync_index() in allowed, "senkron adımı DATABASE_STEPS'te değil"
    assert sorted(set(collect_rules._secret_expressions(text))) == ["secrets.DATABASE_URL"]
    assert collect_rules._secret_paths(yaml.safe_load(text)) == [
        ("jobs", "history", "steps", index, "env", "DATABASE_URL") for index in allowed
    ]


RULES: tuple[Callable[[Path], None], ...] = (
    workflow_rules.test_red_run_opens_the_alarm_and_green_run_closes_it,
    workflow_rules.test_only_the_closing_step_may_fail_without_turning_the_run_red,
    workflow_rules.test_alarm_jobs_may_write_issues_and_read_runs,
)


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule.__name__)
def test_history_already_obeys_the_alarm_rules_of_dispatched_workflows(
    rule: Callable[[Path], None],
) -> None:
    rule(HISTORY)


# `uv run python -m football_edge.history sync [--all]`un yerine geçer: argümanları kaydeder,
# `FAIL_CODE` ile döner.
FAKE_UV = """\
#!/usr/bin/env bash
echo "$*" >> "$CALLS"
exit "${FAIL_CODE:-0}"
"""


def _run_sync_step(tmp_path: Path, *, all_paths: str, code: int) -> tuple[int, list[str], str]:
    fake = tmp_path / "uv"
    fake.write_text(FAKE_UV, encoding="utf-8")
    fake.chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "CALLS": str(calls),
        "FAIL_CODE": str(code),
        "ALL_PATHS": all_paths,
    }
    body = str(_steps(HISTORY)[_sync_index()]["run"])
    # `shell:` verilmemiş `run` adımını GitHub `bash -e {0}` ile koşar.
    result = subprocess.run(
        ["bash", "-e", "-c", body], env=env, capture_output=True, text=True, timeout=30, check=False
    )
    return result.returncode, calls.read_text(encoding="utf-8").splitlines(), result.stdout


@pytest.mark.parametrize(
    ("all_paths", "expected"),
    [("false", f"run python -m {SYNC}"), ("true", f"run python -m {SYNC} --all")],
    ids=["haftalik", "tam-yukleme"],
)
def test_the_all_input_alone_decides_whether_every_path_is_fetched(
    tmp_path: Path, all_paths: str, expected: str
) -> None:
    code, calls, out = _run_sync_step(tmp_path, all_paths=all_paths, code=0)

    assert (code, calls) == (0, [expected])
    assert "::error::" not in out


@pytest.mark.parametrize(
    ("code", "named"),
    [(collect.EXIT_SOURCE_FAILED, "exit 7"), (1, "beklenmedik")],
    ids=["kaynak", "beklenmedik"],
)
def test_a_red_sync_turns_the_run_red_and_names_the_failure(
    tmp_path: Path, code: int, named: str
) -> None:
    returned, _, out = _run_sync_step(tmp_path, all_paths="false", code=code)

    assert returned == code, "senkronun kodu yutuldu: alarm adımı kırmızıyı görmez"
    assert any(line.startswith("::error::") and named in line for line in out.splitlines()), out
```

- [ ] **Step 18: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_history_workflow.py -q`
Expected: FAIL (12 failed) — `FileNotFoundError: …/.github/workflows/history.yml`

- [ ] **Step 19: Workflow'u yaz**

Create `.github/workflows/history.yml`:
```yaml
name: history

on:
  # Tek tetik `workflow_dispatch`: elle (ilk tam yükleme `all: true`) ve — controller'ın 0008
  # migration'ından sonra — haftalık pg_cron dispatch'i (yalnız `ref` gönderir, `all` false
  # kalır). GitHub `schedule`ı KASITLI olarak yok: seyrek ve gecikmeli koşar (0003).
  workflow_dispatch:
    inputs:
      all:
        description: "Bütün beyanlı yollar (ilk tam yükleme); kapalıysa yalnız değişken dosyalar"
        type: boolean
        default: false
        required: false

concurrency:
  # Kendi grubu: üst üste binen iki tur aynı kaynağa iki istemci gönderir ve 3 sn'lik aralık
  # ikiye bölünür. `odds-collect`e girmez — orada bekleyen bir mühür turunu iptal ettirebilirdi.
  group: history
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  # TEK job: tests/workflow_helpers.py `_steps()` tek job varsayar. Task 10'un `selftest`i ikinci
  # bir job değil, `Senkron` ile alarm adımları arasına girecek bir ADIMDIR.
  history:
    runs-on: ubuntu-latest
    # `--all`: 500 dosya × 3 sn nezaket aralığı ≈ 25 dk + indirme; haftalık tur ~40 dosya.
    timeout-minutes: 60
    permissions:
      # Job düzeyi üst düzeyi TAMAMEN ezer: checkout için `contents: read` burada da yazılı.
      contents: read
      # Alarm issue'su açar/kapatır (scripts/ops_alert.py).
      issues: write
      actions: read
    steps:
      - uses: actions/checkout@v4
        with:
          # Bu iş push'lamaz: job token'ı `.git/config`e yazılmaz, sonraki adımlar okuyamaz.
          persist-credentials: false
      - name: Secret taraması
        # Depo PUBLIC: izlenen bir dosyaya kaçmış secret varsa tur, veritabanı secret'ını hiçbir
        # adıma vermeden kırmızı düşer.
        run: ./scripts/check_secrets.sh
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.11"
      - run: uv sync --frozen
      - name: Senkron
        # Veritabanı secret'ını yalnız veritabanını kullanan adımlar alır (bugün bu; Task 10'dan
        # sonra selftest) — liste tests/test_history_workflow.py::DATABASE_STEPS. Girdi `env` ile
        # gelir, betiğe `${{ }}` ile gömülmez. Task 10'un selftest ADIMI bu adımla alarm
        # adımlarının arasına girer.
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          ALL_PATHS: ${{ inputs.all }}
        run: |
          set +e
          if [ "$ALL_PATHS" = "true" ]; then
            uv run python -m football_edge.history sync --all
          else
            uv run python -m football_edge.history sync
          fi
          code=$?
          set -e
          case "$code" in
            0) ;;
            7) echo "::error::history sync: en az bir dosya senkronlanamadı (exit 7) — ayrıntı yukarıdaki satırlarda" ;;
            *) echo "::error::history sync beklenmedik kodla düştü (exit $code)" ;;
          esac
          exit "$code"
      - name: Alarm aç
        # Önceki HERHANGİ bir adım kırmızıysa `ops-alert` issue'su açılır; açıksa yalnız gövdesi
        # güncellenir. `cancelled()`: zaman aşımı turu iptal eder ve `failure()` yanlış döner.
        if: ${{ failure() || cancelled() }}
        env:
          GITHUB_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: uv run python scripts/ops_alert.py fail --workflow history --run-url "$RUN_URL"
      - name: Alarm kapat
        # Kapatma düşerse (ör. GitHub 5xx) yeşil tur kırmızıya dönmez; açık alarm sonraki yeşil
        # turda kapanır.
        if: success()
        continue-on-error: true
        env:
          GITHUB_TOKEN: ${{ github.token }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: uv run python scripts/ops_alert.py ok --workflow history --run-url "$RUN_URL"
```

- [ ] **Step 20: Yeşil olduğunu gör, statik denetim**
Run: `uv run pytest tests/test_history_workflow.py -q`
Expected: PASS (12 passed)
Run: `uv run pytest tests/test_workflows.py tests/test_collect_workflows.py -q`
Expected: PASS — `test_only_a_pushing_workflow_keeps_the_checkout_token_on_disk[history.yml]` yeni
bir parametre olarak koşar
Run: `uv run pytest tests/test_history_store.py tests/test_history_sync.py tests/test_history_registry.py tests/test_history_cli.py tests/test_history_workflow.py -q`
Expected: PASS (57 passed)
Run: `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`
Expected: temiz

- [ ] **Step 21: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır)

Her satır plan yazılırken ayrı bir kopyada uygulandı ve adı geçen test KIRMIZI ölçüldü (Task 3
yerine sözleşmeye uyan bir kilit taslağıyla).

| # | Mutasyon (dosya:ne değişir) | Kırmızı olması gereken test |
|---|---|---|
| 1 | `store.py:save_file` aynı-içerik dalı → `if False:` (her turda yeniden yazar) | `test_history_sync.py::test_an_unchanged_second_run_rewrites_nothing_but_still_logs_the_fetches` |
| 2 | `store.py:save_file` `gzip.compress(content, mtime=0)` → `content` | `test_save_file_stores_gzip_content_with_the_sha_and_size_of_the_plain_bytes` |
| 3 | `store.py:_cached` sha karşılaştırması → `if False:` | `test_load_files_refuses_content_that_does_not_match_its_sha` |
| 4 | `sync.py:_sync_one` `if path not in source.declared_paths:` → `if False:` | `test_an_undeclared_path_is_never_requested` |
| 5 | `sync.py:_sync_one` `check_quality(...)` satırı silinir | `test_a_file_that_breaks_the_contract_never_replaces_the_cached_version` |
| 6 | `sync.py:_sync_one` `conn.commit()` silinir | `test_sync_caches_every_file_and_logs_every_fetch` |
| 7 | `sync.py:sync` `_record_failure(...)` satırı silinir | `test_a_failing_file_is_named_and_the_others_still_sync` |
| 8 | `sync.py:sync` `failed = (*failed, …)` satırı silinir (arıza yutulur) | `test_a_failing_file_is_named_and_the_others_still_sync` |
| 9 | `sync.py:sync` except'teki `conn.rollback()` silinir | `test_a_failed_commit_is_a_failure_not_a_change` |
| 10 | `sync.py:mutable_paths` `[-1]` → `[0]` | `test_mutable_paths_are_the_current_main_seasons_and_every_extra_file` |
| 11 | `sync.py:_load_all` eksik dosya koşulu → `if False:` | `test_load_matches_refuses_an_incomplete_cache` |
| 12 | `sync.py:_parsed` `check_quality(...)` satırı silinir | `test_load_matches_rechecks_the_contract_of_every_cached_file` |
| 13 | `sync.py:_order` → `(match.date, match.home, match.kickoff or _NO_KICKOFF)` | `test_load_all_returns_every_cached_season_in_date_kickoff_home_order` |
| 14 | `__main__.py:_sync_command` `declared_paths` ↔ `mutable_paths` yer değiştirir | `test_sync_fetches_only_the_mutable_files_by_default` |
| 15 | `__main__.py:_report` → `return 0` | `test_a_failed_file_turns_the_run_red_with_the_source_code_and_its_name` |
| 16 | `__main__.py:_verify_lock` `return EXIT_LOCK_VIOLATION` → `return EXIT_SOURCE_FAILED` | `test_lock_verify_exits_9_when_a_locked_row_changed` |
| 17 | `__main__.py:main` `configure_logging()` `load_catalog`dan sonraya | `test_the_redacting_log_setup_comes_before_anything_else` |
| 18 | `__main__.py:_lock_command` `except ContractViolation` → `except KeyError` | `test_lock_refuses_an_unusable_cache_with_the_source_code` |
| 19 | `history.yml` `sync --all` → `sync` | `test_the_all_input_alone_decides_whether_every_path_is_fetched[tam-yukleme]` |
| 20 | `history.yml` `exit "$code"` → `exit 0` | `test_a_red_sync_turns_the_run_red_and_names_the_failure` |
| 21 | `history.yml` alarm aç koşulu `failure() \|\| cancelled()` → `failure()` | `test_history_already_obeys_the_alarm_rules_of_dispatched_workflows[test_red_run_opens_the_alarm_and_green_run_closes_it]` |
| 22 | `history.yml` job düzeyine `env: DATABASE_URL: ${{ secrets.DATABASE_URL }}` | `test_only_the_database_steps_get_a_secret_and_only_the_database_one` |
| 22b | `history.yml` `Alarm aç` adımının `env`ine `DATABASE_URL` eklenir | `test_only_the_database_steps_get_a_secret_and_only_the_database_one` |
| 22c | `history.yml` `- name: Senkron` → `- name: Senkronla` (izinli ad bulunamaz) | `test_only_the_database_steps_get_a_secret_and_only_the_database_one` |
| 23 | `history.yml` `persist-credentials: false` silinir | `test_workflows.py::test_only_a_pushing_workflow_keeps_the_checkout_token_on_disk[history.yml]` |
| 24 | `0006_history.sql` tetikleyici `on hist_fetches` → `on hist_files` | `test_the_fetch_log_is_append_only_and_the_cache_is_not` |
| 25 | `0006_history.sql` `alter table hist_files enable row level security;` silinir | `test_raw_content_tables_hide_their_rows_from_api_roles` |
| 26 | `store.py:_UPSERT_FILE` `http_last_modified` → `last_modified` | `test_the_store_writes_exactly_the_columns_the_migration_creates` |
| 27 | `sources.yaml` `      - /new/USA.csv` satırı silinir | `test_declared_paths_are_exactly_the_catalog_expansion` |
| 28 | `sources.yaml` football-data `crawl_delay_seconds: 3.0` → `0.0` | `test_the_source_is_honest_polite_and_robots_based` |
| 29 | `robots/football-data.txt` `Disallow:` → `Disallow: /` | `test_every_declared_path_passes_the_offline_source_audit` |
| 30 | `sync.py:load_matches` süzgeç kalkar: `code: select_periods(matches, periods=periods, key=key)` → `code: matches` | `test_load_matches_without_a_key_never_hands_out_a_holdout_row` |
| 31 | `sync.py:load_matches` doğrulama süzgeçten SONRAYA: `verify_lock(lock, selected)` süzülmüş sonuç üzerinde | `test_the_lock_is_checked_over_every_period_before_the_holdout_is_filtered_out` |
| 32 | `sync.py:load_matches` anahtar yok sayılır: `periods = _OPEN_PERIODS` | `test_a_hand_built_key_does_not_open_the_holdout` |
| 33 | `sync.py:load_matches` `if lock is not None:` → `if False:` (kilit doğrulanmaz) | `test_a_changed_holdout_row_breaks_the_lock_although_it_is_never_returned`, `test_history_cli.py::test_lock_verify_exits_9_when_a_locked_row_changed[holdout]` |
| 34 | `__main__.py:_write_lock` `_load_all(conn, catalog)` → `load_matches(conn, catalog)` (holdout özeti 0 satır) | `test_lock_write_digests_every_period_and_verify_accepts_it` |
| 35 | `__main__.py:_verify_lock` `lock = load_lock(target)` `try`ın dışına (bozuk kilit traceback + exit 1) | `test_a_broken_lock_file_exits_9_not_with_a_traceback` |
| 36 | `sync.py:_sync_one` `last_modified=response.headers.get("last-modified")` → `last_modified=None` | `test_sync_caches_every_file_and_logs_every_fetch` |

- [ ] **Step 22: Commit**
```bash
git add db/migrations/0006_history.sql src/football_edge/history/store.py \
  src/football_edge/history/sync.py src/football_edge/history/__main__.py \
  .github/workflows/history.yml config/robots/football-data.txt config/sources.yaml \
  tests/fake_hist_db.py tests/test_history_store.py tests/test_history_sync.py \
  tests/test_history_registry.py tests/test_history_cli.py tests/test_history_workflow.py
git commit -m "feat: football-data senkronu, önbellek (0006), CLI, history.yml ve kaynak kaydı (T1b)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 23: Kapının tamamı**
Run: `TMPDIR=$(mktemp -d) ./verify.sh` — log DOSYASINDAN oku.
Expected: 10 adım PASS (Task 5'in `sızıntı` adımı dahil; bu görev 11 yeni `leakage` testi ekler) +
`SKIP: zincir (DATABASE_URL yok)`. `kaynak-politikası` adımı `football-data`nın 500 yolunu da sorar.

---

### Task 7: Tarihsel ↔ canlı kapanış köprüsü (T7)

**Kademe:** K2 · **Dalga:** 2 · **Worktree/dal:** `.worktrees/wt-bridge` · `feat/faz2-bridge`

**Files:**
- Create: `src/football_edge/market/bridge.py`
- Create: `config/history_aliases.yaml` (boş başlar; controller Task 8 Step 12'de gerçek adlarla doldurur)
- Test: `tests/test_bridge.py`

**Interfaces:**
- Consumes:
  - Task 0: `CLOSING`, `H2H`, `HistMatch`.
  - Task 2: `devig(prices: Sequence[float], method: str) -> tuple[float, ...]`, `InvalidPrices`,
    `match_probs(match, *, book, market, phase, method) -> tuple[float, ...] | None`,
    `MULTIPLICATIVE`, `SHIN`; `Interval`,
    `bootstrap_mean(values, *, resamples=2000, seed=20260922, level=0.95) -> Interval`;
    test yardımcısı `tests.market_factory.hist_match`.
  - Task 3: `POST`, `select_periods(matches, *, periods: frozenset[str], key=None) -> tuple[HistMatch, ...]`.
  - Task 4: `football_edge.backtest.timeline.LONDON: ZoneInfo` (saat dilimi kuralı tek yerde).
  - Mevcut: `naming.normalise_team(name: str) -> str`; mühür turu (`rounds.run_seal` →
    `odds_api.fetch_odds(markets="h2h")`) satırları `market='h2h'`, `is_closing=true`, sonuç adı ev
    ya da deplasman takımının adı veya `"Draw"` olarak yazar; `tests/fake_db.utc`.
- Produces:
```python
# football_edge/market/bridge.py
@dataclass(frozen=True)
class LiveClosing:
    match_id: str; league_id: str; kickoff: datetime; home: str; away: str
    prices: tuple[float, float, float]     # kitapların kapanış fiyatlarının aritmetik ortalaması (H, D, A)
    books: int
@dataclass(frozen=True)
class Pairing:
    pairs: tuple[tuple[LiveClosing, HistMatch], ...]
    unmatched_live: tuple[LiveClosing, ...]
@dataclass(frozen=True)
class BridgeReport:
    n: int; method: str
    mean_diff: tuple[Interval, Interval, Interval]    # p_bizim − p_AvgC (H, D, A)
    rms: float; unmatched: int      # unmatched = eşlenemeyen + AvgC'si eksik/çözülemeyen çift
def load_aliases(path: Path) -> Mapping[str, str]
def load_live_closings(conn: psycopg.Connection[Any], *, since: datetime) -> tuple[LiveClosing, ...]
    # aynı (maç, kitap, sonuç) iki mühür turunda yazıldıysa SON gözlem; üç sonucu tam kitaplar
def pair(live: Sequence[LiveClosing], hist: Sequence[HistMatch], *, aliases: Mapping[str, str],
         codes_by_league_id: Mapping[str, str]) -> Pairing
    # yalnız POST dönemi tarihsel satırlar dizinlenir (holdout anahtarsız okunmaz)
def compare(pairing: Pairing, *, method: str) -> BridgeReport
    # karşılaştırılabilir çift yoksa ValueError (n = 0'ın aralığı tanımsız)
def render_bridge_report(report: BridgeReport, *, generated_at: datetime, since: date) -> str   # R91
    # markdown, yalnız toplu sayı: n, karşılaştırılamayan, sonuç başına ortalama fark + aralık, RMS,
    # yöntem ve "aralık N küçükken geniştir" satırı; maç/takım satırı YOK
LIVE_MARKET = "h2h"; LIVE_DRAW = "Draw"; REFERENCE_BOOK = "Avg"
```

- [ ] **Step 1: Başarısız testleri yaz**
`tests/test_bridge.py` — tam içerik:
```python
"""Tarihsel ↔ canlı köprü: mühürlü kapanışın okunması, eşleme ve karşılaştırma (tasarım §9)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge.history.types import CLOSING, H2H, HistMatch
from football_edge.market.bridge import (
    LiveClosing,
    Pairing,
    compare,
    load_aliases,
    load_live_closings,
    pair,
    render_bridge_report,
)
from football_edge.market.devig import MULTIPLICATIVE, SHIN, devig
from tests.fake_db import utc
from tests.market_factory import hist_match

REPO = Path(__file__).resolve().parent.parent
SINCE = datetime(2026, 7, 1, tzinfo=UTC)
HOME, AWAY = "Alpha Rovers", "Beta Athletic"
CODES = MappingProxyType({"eng.1": "E0"})
NO_ALIASES: MappingProxyType[str, str] = MappingProxyType({})


@dataclass
class _FakeClosingDb:
    """`load_live_closings`in tek sorgusu; psycopg'nin tiplerini (datetime, Decimal) verir."""

    rows: list[tuple[Any, ...]]
    executed: list[tuple[str, Any]] = field(default_factory=list)

    def cursor(self) -> _Cursor:
        return _Cursor(self)


class _Cursor:
    def __init__(self, db: _FakeClosingDb) -> None:
        self._db = db

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        self._db.executed = [*self._db.executed, (" ".join(sql.split()), params)]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._db.rows)


def _row(
    match_id: str,
    book: str,
    outcome: str,
    price: float,
    *,
    observed: str = "2026-09-19T13:50:00Z",
    kickoff: str = "2026-09-19T14:00:00Z",
) -> tuple[Any, ...]:
    return (
        match_id,
        "eng.1",
        utc(kickoff),
        HOME,
        AWAY,
        book,
        outcome,
        Decimal(str(price)),
        utc(observed),
    )


def _book(match_id: str, book: str, prices: tuple[float, float, float]) -> list[tuple[Any, ...]]:
    names = (HOME, "Draw", AWAY)
    return [_row(match_id, book, name, price) for name, price in zip(names, prices, strict=True)]


def test_consensus_is_the_mean_over_books_that_carry_all_three_outcomes() -> None:
    rows = [
        *_book("m1", "book_a", (2.0, 3.4, 4.0)),
        *_book("m1", "book_b", (2.2, 3.6, 3.8)),
        _row("m1", "book_c", HOME, 2.1),  # beraberliği yok: ortalamaya girmez
        _row("m1", "book_c", AWAY, 3.9),
    ]
    (closing,) = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert closing.prices == pytest.approx((2.1, 3.5, 3.9))
    assert closing.books == 2
    assert all(type(price) is float for price in closing.prices)
    assert (closing.match_id, closing.league_id, closing.home, closing.away) == (
        "m1",
        "eng.1",
        HOME,
        AWAY,
    )
    assert closing.kickoff == datetime(2026, 9, 19, 14, 0, tzinfo=UTC)


def test_outcomes_are_mapped_by_team_name_not_by_row_order() -> None:
    rows = [
        _row("m1", "book_a", AWAY, 5.0),
        _row("m1", "book_a", "Draw", 3.8),
        _row("m1", "book_a", HOME, 1.7),
    ]
    (closing,) = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert closing.prices == (1.7, 3.8, 5.0)


def test_the_latest_closing_snapshot_of_a_book_wins() -> None:
    # Pencere iki mühür turunu kapsayabilir: başlamaya en yakın gözlem kapanıştır.
    rows = [
        _row("m1", "book_a", HOME, 2.0, observed="2026-09-19T13:55:00Z"),
        _row("m1", "book_a", HOME, 2.5, observed="2026-09-19T13:40:00Z"),
        _row("m1", "book_a", "Draw", 3.4),
        _row("m1", "book_a", AWAY, 4.0),
    ]
    (closing,) = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert closing.prices == (2.0, 3.4, 4.0)


def test_query_reads_only_h2h_closing_rows_of_matches_since_the_given_time() -> None:
    db = _FakeClosingDb([])
    assert load_live_closings(db, since=SINCE) == ()  # type: ignore[arg-type]
    ((sql, params),) = db.executed
    assert "JOIN odds_snapshots s ON s.match_id = m.id" in sql
    assert "s.is_closing" in sql
    assert "s.market = %s" in sql
    assert "m.commence_time >= %s" in sql
    assert params == ("h2h", SINCE)


def test_a_match_without_a_complete_book_is_skipped_and_named(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rows = [*_book("m1", "book_a", (2.0, 3.4, 4.0)), _row("m2", "book_a", HOME, 2.0)]
    with caplog.at_level(logging.WARNING, logger="football_edge.market.bridge"):
        closings = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert [closing.match_id for closing in closings] == ["m1"]
    assert "maç=m2" in caplog.text


def test_closings_come_back_in_kickoff_order() -> None:
    late = [
        _row("m9", "book_a", name, price, kickoff="2026-09-20T18:00:00Z")
        for name, price in zip((HOME, "Draw", AWAY), (2.0, 3.4, 4.0), strict=True)
    ]
    rows = [*late, *_book("m1", "book_a", (2.0, 3.4, 4.0))]
    closings = load_live_closings(_FakeClosingDb(rows), since=SINCE)  # type: ignore[arg-type]
    assert [closing.match_id for closing in closings] == ["m1", "m9"]


def _live(
    match_id: str = "m1",
    *,
    league_id: str = "eng.1",
    kickoff: datetime = datetime(2026, 9, 19, 14, 0, tzinfo=UTC),
    home: str = HOME,
    away: str = AWAY,
    prices: tuple[float, float, float] = (2.0, 4.0, 4.0),
) -> LiveClosing:
    return LiveClosing(match_id, league_id, kickoff, home, away, prices, 2)


def _hist(
    day: date,
    *,
    league: str = "E0",
    home: str = HOME,
    away: str = AWAY,
    avgc: tuple[float, float, float] | None = (2.0, 4.0, 4.0),
) -> HistMatch:
    prices = {} if avgc is None else {("Avg", H2H, CLOSING): avgc}
    return hist_match(league=league, season="2627", day=day, home=home, away=away, prices=prices)


def test_pairs_on_league_code_date_and_team_names() -> None:
    live = _live()
    target = _hist(date(2026, 9, 19))
    result = pair([live], [target], aliases=NO_ALIASES, codes_by_league_id=CODES)
    assert result == Pairing(pairs=((live, target),), unmatched_live=())


@pytest.mark.parametrize(
    ("kickoff", "london_day"),
    (
        (datetime(2026, 9, 19, 23, 30, tzinfo=UTC), date(2026, 9, 20)),  # BST: 00:30 ertesi gün
        (datetime(2026, 11, 7, 23, 30, tzinfo=UTC), date(2026, 11, 7)),  # GMT: 23:30 aynı gün
    ),
)
def test_pairing_uses_the_london_date_of_the_kickoff(kickoff: datetime, london_day: date) -> None:
    hist = [_hist(london_day + timedelta(days=shift)) for shift in (-1, 0, 1)]
    result = pair([_live(kickoff=kickoff)], hist, aliases=NO_ALIASES, codes_by_league_id=CODES)
    ((_, found),) = result.pairs
    assert found.date == london_day


@pytest.mark.parametrize("side", ("home", "away"))
def test_alias_maps_the_odds_api_name_to_the_football_data_name(side: str) -> None:
    # Takma ad ev ve deplasman adına AYRI AYRI uygulanır (m4: yalnız ev sınanıyordu).
    live = _live(**{side: "Delta Rovers United"})
    hist = [_hist(date(2026, 9, 19), **{side: "Delta Rov."})]
    aliases = MappingProxyType({"Delta Rovers United": "Delta Rov"})
    assert pair([live], hist, aliases=aliases, codes_by_league_id=CODES).pairs
    unaliased = pair([live], hist, aliases=NO_ALIASES, codes_by_league_id=CODES)
    assert unaliased.unmatched_live == (live,)


def test_names_are_compared_after_normalisation() -> None:
    live = _live(away="Beta Athletic F.C.")
    hist = [_hist(date(2026, 9, 19), away="BETA ATHLETIC")]
    assert pair([live], hist, aliases=NO_ALIASES, codes_by_league_id=CODES).pairs


def test_unmatched_live_matches_are_returned_in_order_not_dropped() -> None:
    unknown_league = _live("m1", league_id="xyz.9")
    no_counterpart = _live("m2", home="Gamma United")
    paired = _live("m3")
    hist = [_hist(date(2026, 9, 19)), _hist(date(2026, 9, 19), league="SP1", home="Gamma United")]
    result = pair(
        [unknown_league, no_counterpart, paired], hist, aliases=NO_ALIASES, codes_by_league_id=CODES
    )
    assert result.unmatched_live == (unknown_league, no_counterpart)
    assert [live.match_id for live, _ in result.pairs] == ["m3"]


@pytest.mark.leakage
def test_the_bridge_never_pairs_a_holdout_dated_match() -> None:
    # Holdout [2025-07-01, 2026-07-01) anahtarsız okunmaz: köprü yalnız "sonrası"na bakar.
    live = _live(kickoff=datetime(2026, 3, 14, 15, 0, tzinfo=UTC))
    hist = [_hist(date(2026, 3, 14), avgc=(2.0, 4.0, 4.0))]
    result = pair([live], hist, aliases=NO_ALIASES, codes_by_league_id=CODES)
    assert result.pairs == ()
    assert result.unmatched_live == (live,)


def test_compare_reports_ours_minus_avgc_per_outcome_and_the_rms() -> None:
    # Çift 1: bizim (2, 4, 4) → (0.5, 0.25, 0.25); AvgC (2.5, 10/3, 10/3) → (0.4, 0.3, 0.3)
    #   fark (0.1, −0.05, −0.05). Çift 2: iki taraf aynı → fark 0.
    #   ortalama (0.05, −0.025, −0.025) · RMS = √((0.01 + 0.0025 + 0.0025) / 6) = 0.05
    first = (_live("m1"), _hist(date(2026, 9, 19), avgc=(2.5, 10 / 3, 10 / 3)))
    second = (_live("m2", home="Gamma United"), _hist(date(2026, 9, 19), home="Gamma United"))
    pairing = Pairing(pairs=(first, second), unmatched_live=(_live("m3"),))
    report = compare(pairing, method=MULTIPLICATIVE)
    assert (report.n, report.method, report.unmatched) == (2, MULTIPLICATIVE, 1)
    estimates = tuple(interval.estimate for interval in report.mean_diff)
    assert estimates == pytest.approx((0.05, -0.025, -0.025), abs=1e-12)
    assert report.rms == pytest.approx(0.05, abs=1e-12)
    home = report.mean_diff[0]
    assert home.low <= home.estimate <= home.high


def test_compare_devigs_both_sides_with_the_same_method() -> None:
    ours, theirs = (1.8, 3.6, 4.6), (1.9, 3.5, 4.2)
    pairing = Pairing(
        pairs=((_live(prices=ours), _hist(date(2026, 9, 19), avgc=theirs)),), unmatched_live=()
    )
    report = compare(pairing, method=SHIN)
    expected = tuple(a - b for a, b in zip(devig(ours, SHIN), devig(theirs, SHIN), strict=True))
    estimates = tuple(interval.estimate for interval in report.mean_diff)
    assert estimates == pytest.approx(expected, abs=1e-12)


def test_pairs_without_a_closing_avgc_are_counted_as_unmatched() -> None:
    usable = (_live("m1"), _hist(date(2026, 9, 19)))
    bare = (
        _live("m2", home="Gamma United"),
        _hist(date(2026, 9, 19), home="Gamma United", avgc=None),
    )
    report = compare(Pairing(pairs=(usable, bare), unmatched_live=()), method=SHIN)
    assert (report.n, report.unmatched) == (1, 1)


def test_compare_without_comparable_pairs_is_an_error() -> None:
    with pytest.raises(ValueError, match="karşılaştırılabilir"):
        compare(Pairing(pairs=(), unmatched_live=(_live(),)), method=SHIN)


def test_bridge_report_carries_only_aggregates() -> None:
    first = (_live("m1"), _hist(date(2026, 9, 19), avgc=(2.5, 10 / 3, 10 / 3)))
    second = (_live("m2", home="Gamma United"), _hist(date(2026, 9, 19), home="Gamma United"))
    pairing = Pairing(pairs=(first, second), unmatched_live=(_live("m3"),))
    report = compare(pairing, method=MULTIPLICATIVE)
    generated = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
    text = render_bridge_report(report, generated_at=generated, since=date(2026, 7, 1))
    assert "Karşılaştırılan maç (N): 2" in text
    assert "Karşılaştırılamayan canlı maç: 1" in text
    assert "Yöntem: multiplicative" in text
    assert "2026-07-01 ve sonrasında" in text
    home = report.mean_diff[0]
    assert f"| H | +0.0500 | [{home.low:+.4f}, {home.high:+.4f}] |" in text
    assert "| D | -0.0250 |" in text
    assert "| A | -0.0250 |" in text
    assert "RMS (bütün sonuç farkları): 0.0500" in text
    assert "Aralık N küçükken geniştir (N = 2)" in text
    for name in (HOME, AWAY, "Gamma United"):
        assert name not in text  # takım adı (ham satır) rapora giremez
    assert text.endswith("\n")


def test_load_aliases_reads_an_immutable_string_mapping(tmp_path: Path) -> None:
    path = tmp_path / "aliases.yaml"
    path.write_text("aliases:\n  Alpha Rovers United: Alpha Rov\n", encoding="utf-8")
    aliases = load_aliases(path)
    assert dict(aliases) == {"Alpha Rovers United": "Alpha Rov"}
    with pytest.raises(TypeError):
        aliases["x"] = "y"  # type: ignore[index]


@pytest.mark.parametrize(
    "text",
    ("", "aliases: [a, b]\n", "other: {}\n", "aliases:\n  Alpha: 3\n", "aliases:\n  Alpha: ''\n"),
    ids=("bos", "liste", "anahtar-yok", "sayi", "bos-hedef"),
)
def test_load_aliases_rejects_a_malformed_file(tmp_path: Path, text: str) -> None:
    path = tmp_path / "aliases.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="aliases|takma ad"):
        load_aliases(path)


def test_repository_alias_file_loads() -> None:
    aliases = load_aliases(REPO / "config/history_aliases.yaml")
    assert all(isinstance(key, str) and isinstance(value, str) for key, value in aliases.items())
```

- [ ] **Step 2: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_bridge.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.market.bridge'`

- [ ] **Step 3: En küçük uygulamayı yaz**

Mühür penceresi (20 dk) cron aralığından (15 dk) uzun: aynı ligde mühürsüz başka bir maç varsa
önceki turda mühürlenmiş maç ikinci kez `is_closing` satırı alır (`rounds._seal_row_filter` yalnız
zamana bakar). Bu yüzden kitap-sonuç başına SON gözlem alınır. Tarih Londra'ya çevrilir:
football-data'nın `Date`'i İngiltere tarihidir (gece yarısı sonrası başlayan maç UTC'de önceki güne
düşer). `render_bridge_report` (R91) ilk gerçek köprü raporunun üreticisidir; onu Task 9'un
`python -m football_edge.market bridge` alt komutu çağırır.
`src/football_edge/market/bridge.py` — tam içerik:
```python
"""Tarihsel ↔ canlı kapanış köprüsü: kendi mühürlediğimiz kapanış ile football-data'nın `AvgC`'si.

Aynı maç `(lig, İngiltere tarihi, ev, deplasman)` ile eşlenir; iki taraf aynı yöntemle vig'den
arındırılıp sonuç başına karşılaştırılır (tasarım §9). Eşlenemeyen canlı maç düşürülmez, sayılır.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import psycopg
import yaml

from football_edge.backtest.timeline import LONDON
from football_edge.history.holdout import POST, select_periods
from football_edge.history.types import CLOSING, H2H, HistMatch
from football_edge.market.devig import InvalidPrices, devig, match_probs
from football_edge.market.metrics import Interval, bootstrap_mean
from football_edge.naming import normalise_team

LOGGER = logging.getLogger("football_edge.market.bridge")

# The Odds API'nin 1X2 market anahtarı ve beraberlik sonucunun adı: mühür turu
# (`rounds.run_seal` → `odds_api.fetch_odds(markets="h2h")`) satırları bu adlarla yazar.
LIVE_MARKET = "h2h"
LIVE_DRAW = "Draw"
REFERENCE_BOOK = "Avg"  # (Avg, CLOSING) = football-data'nın AvgC'si — referans kapanış (D3)

_CLOSINGS = """
    SELECT m.id, m.league_id, m.commence_time, m.home_team, m.away_team,
           s.bookmaker, s.outcome, s.price, s.observed_at
    FROM matches m
    JOIN odds_snapshots s ON s.match_id = m.id
    WHERE s.is_closing AND s.market = %s AND m.commence_time >= %s
    ORDER BY m.commence_time, m.id
"""

_OUTCOMES = ("H", "D", "A")
Books = Mapping[str, Mapping[str, float]]  # kitap → {sonuç adı: fiyat}
Key = tuple[str, date, str, str]


@dataclass(frozen=True)
class LiveClosing:
    match_id: str
    league_id: str
    kickoff: datetime
    home: str
    away: str
    prices: tuple[float, float, float]  # kitapların kapanış fiyatlarının aritmetik ortalaması
    books: int


@dataclass(frozen=True)
class Pairing:
    pairs: tuple[tuple[LiveClosing, HistMatch], ...]
    unmatched_live: tuple[LiveClosing, ...]


@dataclass(frozen=True)
class BridgeReport:
    n: int
    method: str
    mean_diff: tuple[Interval, Interval, Interval]  # p_bizim − p_AvgC (H, D, A)
    rms: float
    unmatched: int  # karşılaştırılamayan canlı maç: eşlenemeyen + AvgC'si eksik/çözülemeyen


def load_aliases(path: Path) -> Mapping[str, str]:
    """The Odds API takım adı → football-data takım adı."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("aliases"), dict):
        raise ValueError(f"{path}: kökte 'aliases' eşlemesi yok")
    aliases: dict[Any, Any] = raw["aliases"]
    for name, target in aliases.items():
        if not isinstance(name, str) or not isinstance(target, str) or not target:
            raise ValueError(f"{path}: takma ad metinden metne olmalı: {name!r} → {target!r}")
    return MappingProxyType(dict(aliases))


def _grouped(records: Sequence[tuple[Any, ...]]) -> dict[str, dict[str, dict[str, float]]]:
    """maç → kitap → sonuç → fiyat; aynı kitap-sonuç birden çok turda yazıldıysa SON gözlem."""
    grouped: dict[str, dict[str, dict[str, float]]] = {}
    for record in sorted(records, key=lambda row: row[8]):  # observed_at: artan
        match_id, book, outcome = str(record[0]), str(record[5]), str(record[6])
        grouped.setdefault(match_id, {}).setdefault(book, {})[outcome] = float(record[7])
    return grouped


def _consensus(books: Books, home: str, away: str) -> tuple[tuple[float, float, float], int] | None:
    """Üç sonucu da taşıyan kitapların sonuç başına ortalama fiyatı ve kitap sayısı."""
    names = (home, LIVE_DRAW, away)
    full = [book for book in books.values() if all(name in book for name in names)]
    if not full:
        return None
    count = len(full)
    home_price, draw_price, away_price = (
        math.fsum(book[name] for book in full) / count for name in names
    )
    return (home_price, draw_price, away_price), count


def load_live_closings(
    conn: psycopg.Connection[Any], *, since: datetime
) -> tuple[LiveClosing, ...]:
    """`since`ten sonra başlayan maçların mühürlü 1X2 kapanışları, kitaplar üzerinden ortalama."""
    with conn.cursor() as cur:
        cur.execute(_CLOSINGS, (LIVE_MARKET, since))
        records = cur.fetchall()
    heads = {str(row[0]): (str(row[1]), row[2], str(row[3]), str(row[4])) for row in records}
    grouped = _grouped(records)
    found: list[LiveClosing] = []
    for match_id, (league_id, kickoff, home, away) in heads.items():
        consensus = _consensus(grouped[match_id], home, away)
        if consensus is None:
            LOGGER.warning("maç=%s kapanışında üç sonucu tam kitap yok — köprüye girmedi", match_id)
            continue
        prices, books = consensus
        found.append(LiveClosing(match_id, league_id, kickoff, home, away, prices, books))
    return tuple(sorted(found, key=lambda closing: (closing.kickoff, closing.match_id)))


def _key(closing: LiveClosing, aliases: Mapping[str, str], codes: Mapping[str, str]) -> Key | None:
    code = codes.get(closing.league_id)
    if code is None:
        return None
    return (
        code,
        closing.kickoff.astimezone(LONDON).date(),  # football-data'nın Date'i İngiltere tarihidir
        normalise_team(aliases.get(closing.home, closing.home)),
        normalise_team(aliases.get(closing.away, closing.away)),
    )


def pair(
    live: Sequence[LiveClosing],
    hist: Sequence[HistMatch],
    *,
    aliases: Mapping[str, str],
    codes_by_league_id: Mapping[str, str],
) -> Pairing:
    # Köprü yalnız "sonrası" dönemine bakar: holdout anahtarsız okunmaz ve burada istenmez.
    index = {
        (match.league, match.date, normalise_team(match.home), normalise_team(match.away)): match
        for match in select_periods(hist, periods=frozenset({POST}))
    }
    pairs: list[tuple[LiveClosing, HistMatch]] = []
    unmatched: list[LiveClosing] = []
    for closing in live:
        key = _key(closing, aliases, codes_by_league_id)
        found = None if key is None else index.get(key)
        if found is None:
            unmatched.append(closing)
        else:
            pairs.append((closing, found))
    return Pairing(pairs=tuple(pairs), unmatched_live=tuple(unmatched))


def _live_probs(closing: LiveClosing, method: str) -> tuple[float, ...] | None:
    try:
        return devig(closing.prices, method)
    except InvalidPrices:
        return None


def compare(pairing: Pairing, *, method: str) -> BridgeReport:
    """Sonuç başına p_bizim − p_AvgC (ikisi de `method` ile); ortalama aralığı ve RMS."""
    diffs: list[tuple[float, ...]] = []
    skipped = 0
    for closing, match in pairing.pairs:
        theirs = match_probs(match, book=REFERENCE_BOOK, market=H2H, phase=CLOSING, method=method)
        ours = _live_probs(closing, method)
        if theirs is None or ours is None:
            skipped += 1
            continue
        diffs.append(tuple(mine - reference for mine, reference in zip(ours, theirs, strict=True)))
    if not diffs:
        raise ValueError(
            "karşılaştırılabilir eşleşme yok: "
            f"eşlenemeyen {len(pairing.unmatched_live)}, AvgC'si eksik/çözülemeyen {skipped}"
        )
    flat = [value for row in diffs for value in row]
    home, draw, away = (bootstrap_mean([row[index] for row in diffs]) for index in range(3))
    return BridgeReport(
        n=len(diffs),
        method=method,
        mean_diff=(home, draw, away),
        rms=math.sqrt(math.fsum(value * value for value in flat) / len(flat)),
        unmatched=len(pairing.unmatched_live) + skipped,
    )


def render_bridge_report(report: BridgeReport, *, generated_at: datetime, since: date) -> str:
    """Markdown rapor: yalnız toplu sayılar; maç, takım, maç tarihi satırı YOK (spec §3.2/4)."""
    rows = [
        f"| {name} | {interval.estimate:+.4f} | [{interval.low:+.4f}, {interval.high:+.4f}] |"
        for name, interval in zip(_OUTCOMES, report.mean_diff, strict=True)
    ]
    lines = [
        "# Tarihsel ↔ canlı kapanış köprüsü",
        "",
        f"Üretildi: {generated_at.isoformat()} · Canlı mühürler: {since.isoformat()} ve sonrasında "
        f"başlayan maçlar · Yöntem: {report.method} (iki tarafta da)",
        "",
        f"Karşılaştırılan maç (N): {report.n} · Karşılaştırılamayan canlı maç: {report.unmatched} "
        "(eşlenemeyen ya da AvgC'si eksik/çözülemeyen)",
        "",
        "| Sonuç | Ortalama fark (bizim − AvgC) | %95 aralık |",
        "|---|---|---|",
        *rows,
        "",
        f"RMS (bütün sonuç farkları): {report.rms:.4f}",
        "",
        f"Aralık N küçükken geniştir (N = {report.n}): rapor her hafta yeniden üretilir, canlı "
        "altı lig haftada ~60 maç ekler (tasarım §9, §13/13). Anlamlı bir sistematik fark doğrusal "
        "bir düzeltme ÖNERİSİ doğurur, uygulanmaz.",
    ]
    return "\n".join(lines) + "\n"
```

`config/history_aliases.yaml` — tam içerik:
```yaml
# The Odds API takım adı → football-data takım adı (tarihsel ↔ canlı köprü, tasarım §9).
# Yalnız normalize edilmiş ad eşitliğinin (naming.normalise_team) tutmadığı çiftler girer.
# Boş başlar: controller dalga 2 sonunda gerçek eşleşmeyen adlardan doldurur.
aliases: {}
```

- [ ] **Step 4: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_bridge.py -q`
Expected: PASS (26 passed)
Run: `uv run pytest tests/test_bridge.py -q -m leakage`
Expected: `1 passed, 25 deselected`
Run: `uv run mypy src scripts && uv run ruff check src tests && uv run ruff format --check src tests`
Expected: `Success: no issues found …` · `All checks passed!` · `… files already formatted`

- [ ] **Step 5: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır)
| # | Mutasyon (dosya:ne değişir) | Kırmızı olması gereken test |
|---|---|---|
| 1 | `bridge.py:_grouped` — `sorted(records, key=…row[8])` → `…, reverse=True` (en ERKEN gözlem kazanır) | `test_the_latest_closing_snapshot_of_a_book_wins` |
| 2 | `bridge.py:_consensus` — `all(name in book …)` → `any(…)` (eksik kitap ortalamaya girer) | `test_consensus_is_the_mean_over_books_that_carry_all_three_outcomes` |
| 3 | `bridge.py:_consensus` — ortalama yerine `full[0][name]` (ilk kitap) | `test_consensus_is_the_mean_over_books_that_carry_all_three_outcomes` |
| 4 | `bridge.py:_consensus` — `names = (home, LIVE_DRAW, away)` → `(away, LIVE_DRAW, home)` | `test_outcomes_are_mapped_by_team_name_not_by_row_order` |
| 5 | `bridge.py:load_live_closings` — sorgu parametresi `(LIVE_MARKET, since)` → `("totals", since)` | `test_query_reads_only_h2h_closing_rows_of_matches_since_the_given_time` |
| 6 | `bridge.py:load_live_closings` — eksik kitaplı maç uyarısı (`LOGGER.warning`) silinir | `test_a_match_without_a_complete_book_is_skipped_and_named` |
| 7 | `bridge.py:load_live_closings` — `sorted(found, …)` yerine `tuple(found)` | `test_closings_come_back_in_kickoff_order` |
| 8 | `bridge.py:_key` — `kickoff.astimezone(LONDON).date()` → `kickoff.date()` (UTC tarihi) | `test_pairing_uses_the_london_date_of_the_kickoff` |
| 9 | `bridge.py:_key` — `aliases.get(closing.home, closing.home)` → `closing.home` | `test_alias_maps_the_odds_api_name_to_the_football_data_name[home]` |
| 10 | `bridge.py:_key` — `aliases.get(closing.away, closing.away)` → `closing.away` (m4) | `test_alias_maps_the_odds_api_name_to_the_football_data_name[away]` |
| 11 | `bridge.py:_key` — lig kodu denetimi yerine `code = "E0"` | `test_unmatched_live_matches_are_returned_in_order_not_dropped` |
| 12 | `bridge.py:pair` — dizinde `normalise_team(match.home/away)` yerine ham ad | `test_names_are_compared_after_normalisation` |
| 13 | `bridge.py:pair` — `unmatched.append(closing)` → `pass` | `test_unmatched_live_matches_are_returned_in_order_not_dropped` |
| 14 | `bridge.py:pair` — `select_periods(hist, periods=frozenset({POST}))` → `hist` | `test_the_bridge_never_pairs_a_holdout_dated_match` |
| 15 | `bridge.py:compare` — `mine - reference` → `reference - mine` | `test_compare_reports_ours_minus_avgc_per_outcome_and_the_rms` |
| 16 | `bridge.py:compare` — AvgC tarafında `method=method` → `method="multiplicative"` | `test_compare_devigs_both_sides_with_the_same_method` |
| 17 | `bridge.py:compare` — `unmatched=len(…) + skipped` → `unmatched=len(…)` | `test_pairs_without_a_closing_avgc_are_counted_as_unmatched` |
| 18 | `bridge.py` — `_OUTCOMES = ("H", "D", "A")` → `("A", "D", "H")` (rapor satırları ters) | `test_bridge_report_carries_only_aggregates` |
| 19 | `bridge.py:render_bridge_report` — "Aralık N küçükken geniştir (N = …)" satırı silinir | `test_bridge_report_carries_only_aggregates` |
| 20 | `bridge.py:render_bridge_report` — karşılaştırılamayan sayısı yerine `report.n` | `test_bridge_report_carries_only_aggregates` |
| 21 | `bridge.py:render_bridge_report` — fark `:+.4f` → `:.4f` (işaretsiz) | `test_bridge_report_carries_only_aggregates` |

- [ ] **Step 6: Commit**
```bash
git add src/football_edge/market/bridge.py config/history_aliases.yaml tests/test_bridge.py
git commit -m "feat: tarihsel ↔ canlı kapanış köprüsü — mühürlü kapanış ile AvgC eşlemesi ve rapor (T7)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Kapının tamamı**
Run: `TMPDIR=$(mktemp -d) ./verify.sh` — log DOSYASINDAN oku.
Expected: 10 adım PASS (Task 5'in `sızıntı` adımı dahil; bu görev ona 1 `leakage` testi ekler —
alt sınır birleştirmede controller'ca yeniden ölçülür) + `SKIP: zincir (DATABASE_URL yok)`.

---

### Task 8: Dalga 2 birleştirmesi, haftalık tetik, ilk tam yükleme ve kilit (controller)

**Kademe:** — (controller) · **Dalga:** 2 sonu · **Önkoşul:** Task 6 ve 7 `complete`.

**Files:**
- Create: `db/migrations/0008_history_dispatch.sql`, `tests/test_history_dispatch.py`
- Modify: `scripts/ops_alert.py` (`TRIGGERS`), `tests/test_ops_alert.py` (`FRESH` + sınır testi),
  `docs/RUNBOOK.md` (yeni §3.10),
  `config/history_aliases.yaml` (gerçek adlarla), `config/history_lock.yaml` (yeni, üretilir)

- [ ] **Step 1: Birleştir** — `feat/faz2-sync`, sonra `feat/faz2-bridge`; her birinden sonra kapı
(Task 5 Step 1 deseni).

- [ ] **Step 1b: `sızıntı` alt sınırını yeniden ölç** — dalga 2 yeni `leakage` testleri getirdi:
`uv run pytest tests/ -q -m leakage --collect-only 2>&1 | tail -1` → `verify.sh`teki
`EXPECTED_MIN_LEAKAGE` ölçülen sayıya çıkarılır (yalnız ölçülerek; Task 5 deseni), kapı, commit
`ci: sızıntı alt sınırı dalga 2 sonrası ölçüldü`.

- [ ] **Step 2: 0006'yı canlıya uygula** (`apply_migration`, ad `0006_history`). Doğrula:

```sql
select count(*) from hist_files;    -- 0
select count(*) from hist_fetches;  -- 0
select tgname from pg_trigger where tgrelid = 'hist_fetches'::regclass and not tgisinternal;
```

- [ ] **Step 3: Başarısız testi yaz**

```python
# tests/test_history_dispatch.py
from __future__ import annotations

import re

from tests.workflow_helpers import REPO, _allow_list, _cron_jobs, _functions, _triggers

HISTORY = REPO / ".github/workflows/history.yml"


def test_history_is_triggered_by_pg_cron_alone() -> None:
    """Taban haftalık tazelenir; GitHub'ın `schedule`ı güvenilmez (0003): tek tetik pg_cron."""
    _, command = _cron_jobs().get("history-dispatch", ("", ""))

    assert command == "select ops.dispatch_history()", "history.yml hiç tetiklenmiyor"
    assert "ops.dispatch_workflow('history.yml')" in _functions().get("dispatch_history", "")
    assert "history.yml" in _allow_list(), "izinli listede yok: her dispatch reddedilir"
    assert "schedule" not in _triggers(HISTORY), "history.yml GitHub'dan da tetikleniyor"


def test_history_dispatch_runs_weekly_outside_time_critical_minutes() -> None:
    """Haftada bir, salı: football-data ana ligleri pazartesi akşamı, ek ligleri salı sabahı
    günceller (Last-Modified, 2026-09-22 ölçümü). Dakika mühür ve snapshot dakikalarından ayrı:
    zaman-kritik tetik dakikasını paylaşmaz."""
    jobs = _cron_jobs()
    seal_period = re.fullmatch(r"\*/(\d+)", jobs["seal-dispatch"][0].split()[0])
    assert seal_period is not None, f"seal zamanlaması okunamadı: {jobs['seal-dispatch'][0]!r}"
    taken = {
        *range(0, 60, int(seal_period.group(1))),
        int(jobs["snapshot-dispatch"][0].split()[0]),
    }
    minute, hour, day, month, weekday = jobs["history-dispatch"][0].split()

    assert re.fullmatch(r"\d+", minute) and int(minute) not in taken, (minute, sorted(taken))
    assert re.fullmatch(r"\d+", hour), hour
    assert (day, month, weekday) == ("*", "*", "2"), "haftada bir, salı değil"
```

Run: `uv run pytest tests/test_history_dispatch.py -q`
Expected: FAIL — `KeyError`/`AssertionError`: `history-dispatch` işi yok.

- [ ] **Step 4: Migration'ı yaz**

```sql
-- db/migrations/0008_history_dispatch.sql
-- Faz 2 tarihsel tabanını (history.yml) pg_cron'dan haftalık tetikle.
--
-- NEDEN: football-data güncel sezon dosyalarını haftada iki kez günceller, ek lig dosyaları her
-- hafta büyür; tazelenmeyen taban T7 köprüsünü ve "sonrası" dönemini bayatlatır. GitHub'ın
-- `schedule`ı güvenilir değil (bkz. 0003).
--
-- NE: `ops.dispatch_workflow`un izinli listesine `history.yml` eklenir. `create or replace` listeyi
-- BAŞTAN yazar: 0005'in dört adı da burada durmalı, listeden düşen bir workflow'un cron işi her turda
-- hata verir.

create or replace function ops.dispatch_workflow(p_workflow text) returns bigint
language plpgsql
set search_path = ''
as $$
declare
  token text;
begin
  if p_workflow is null or not (p_workflow = any (array[
    'seal.yml', 'snapshot.yml', 'collect-daily.yml', 'collect-news.yml', 'history.yml'
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

create or replace function ops.dispatch_history() returns bigint
language plpgsql
set search_path = ''
as $$
begin
  return ops.dispatch_workflow('history.yml');
end;
$$;

-- Hiçbir API rolü çağıramaz: çağırabilseydi dışarıdan herkes Actions dakikası yakardı.
revoke all on function ops.dispatch_workflow(text) from public, anon, authenticated;
revoke all on function ops.dispatch_history() from public, anon, authenticated;

-- Salı 09:50 UTC: ana lig dosyaları pazartesi akşamı, ek lig dosyaları salı sabahı güncelleniyor
-- (Last-Modified 2026-09-21 17:50 ve 2026-09-22 08:10 GMT). Dakika mühür (:00/:15/:30/:45) ve
-- snapshot (:22) dakikalarının dışında. Aynı adla yeniden çalıştırmak işi GÜNCELLER.
select cron.schedule('history-dispatch', '50 9 * * 2', 'select ops.dispatch_history()');
```

- [ ] **Step 5: Bekçiye tetiği ekle** — `scripts/ops_alert.py` `TRIGGERS` demetinin sonuna:

```python
    # Tarihsel taban haftalık (0008, salı 09:50): eşik bir hafta + pay.
    Trigger(
        workflow="history.yml",
        event=None,
        max_age=timedelta(days=8),
        hint="pg_cron history-dispatch durmuş olabilir — RUNBOOK §3.3",
    ),
```

Yeni tetik bekçinin sorduğu turlara `history.yml`i ekler; `tests/test_ops_alert.py`nin sahte GitHub'ı
onu tanımıyorsa bekçi onu bayat sayar ve on test (kredi teşhisi dahil) alarm yazdığı için kırmızıya
döner (ölçüldü). Fixture ve sınır testi aynı adımda güncellenir — `FRESH` sözlüğüne:

```python
    "history.yml": [_workflow_run("workflow_dispatch", timedelta(days=7, hours=23))],
```

ve dosyanın sonuna:

```python
def test_a_stale_history_trigger_is_named_in_the_watchdog_alarm() -> None:
    """Tarihsel tabanın tek tetiği pg_cron'dur (0008, haftada bir): durursa geriye bu alarm kalır.
    FRESH onu eşiğin hemen içinde tutar (7 gün 23 sa); bir saat sonrası bayattır."""
    stale = [_workflow_run("workflow_dispatch", timedelta(days=8, hours=1))]
    fake = FakeGitHub(runs={**FRESH, "history.yml": stale})

    assert _watchdog(fake) == 0

    (alarm,) = fake.issues
    assert alarm["title"] == WATCHDOG_ALARM
    for needle in ("history.yml: ", "history-dispatch"):
        assert needle in alarm["body"], f"gövdede teşhis eksik: {needle!r}"
```

- [ ] **Step 6: Yeşil olduğunu gör**

Run: `uv run pytest tests/test_history_dispatch.py tests/test_workflows.py tests/test_ops_alert.py tests/test_collect_workflows.py -q`
Expected: PASS — `history.yml` artık izinli listede, dolayısıyla `ALARMED` testleri de ona uygulanır
(Task 6 alarm adımlarını buna göre yazdı).

- [ ] **Step 7: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`)

| # | Mutasyon | Kırmızı olması gereken test |
|---|---|---|
| 1 | izinli listeden `'history.yml'` çıkarılır | `test_history_is_triggered_by_pg_cron_alone`, `test_every_dispatch_wrapper_targets_the_allow_list_in_force` |
| 2 | izinli listeden `'collect-news.yml'` düşer | `test_every_dispatch_wrapper_targets_the_allow_list_in_force` |
| 3 | zamanlama `'45 9 * * 2'` (mühür dakikası) | `test_history_dispatch_runs_weekly_outside_time_critical_minutes` |
| 4 | zamanlama `'50 9 * * *'` (her gün) | `test_history_dispatch_runs_weekly_outside_time_critical_minutes` |
| 5 | `revoke … dispatch_history()` satırı silinir | `test_no_api_role_may_call_a_dispatch_function` |
| 6 | `TRIGGERS`teki `history.yml` girdisi silinir | `test_a_stale_history_trigger_is_named_in_the_watchdog_alarm` |
| 7 | `max_age` `timedelta(days=9)` | `test_a_stale_history_trigger_is_named_in_the_watchdog_alarm` |

- [ ] **Step 8: RUNBOOK §3.10** — "Tarihsel taban (`history.yml`)": ne yapar (haftalık güncel sezon +
ek ligler; `--all` ilk yükleme), elle tetikleme (`gh workflow run history.yml -f all=true`), kırmızının
iki anlamı (kaynak hatası → `failed` listesi; kalite → reddedilen satır/fiyat payı), kilit ihlali
(`lock --verify` exit 9): önce farkı incele, kilidi güncellemek gerekçeli bir commit'tir. Yıllık
sezon ilerletme: football-data yeni sezonun ilk dosyasını yayımlayınca `config/history_leagues.yaml`
`current_season` ilerletilir ve `sources.yaml`ın `football-data` `declared_paths`i Task 6'nın üretici
komutuyla yenilenir (eşitlik testi eksik satırı adıyla söyler); dosya yayımlanmadan ilerletmek turu
404 ile kırmızı yapar.

- [ ] **Step 9: Commit, kapı, push, 0008'i canlıya uygula**

```bash
git add db/migrations/0008_history_dispatch.sql tests/test_history_dispatch.py \
  scripts/ops_alert.py tests/test_ops_alert.py docs/RUNBOOK.md
git commit -m "ops: tarihsel taban haftalık pg_cron tetiği ve bekçi izlemesi (0008)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
Kapının tamamı → push → `apply_migration` (`0008_history_dispatch`) → doğrula:
`select jobname, schedule, active from cron.job where jobname = 'history-dispatch';` → `50 9 * * 2`, `t`.

- [ ] **Step 10: İlk tam yükleme** — `gh workflow run history.yml -f all=true`; turu izle, logu oku.
Expected: `SyncReport` — `failed` boş; istenen yol sayısı `declared_paths` uzunluğuna eşit; reddedilen
satırlar dosya başına adıyla. Bir yol 404 verirse (o lig o sezon yok) katalogdaki `first_season`
düzeltmesi Task 6'nın implementer'ına bulgu olarak döner; kapı gevşetilmez.

- [ ] **Step 11: robots doğrulaması** — `gh workflow run sources-audit.yml`; logda `football-data:
sapma yok`. Sapma varsa anlık görüntü canlı dosyaya göre düzeltilir (içerik farkı değil yalnız biçim
farkı olmalı; içerik farkıysa robots yeniden okunur).

- [ ] **Step 12: Takım adı eşlemesi (T7)** — canlı altı ligde eşlenemeyen adları listele:

```bash
uv run --env-file .env python - <<'EOF'
from datetime import UTC, datetime, timedelta
from pathlib import Path

from football_edge.db import connect
from football_edge.history.catalog import load_catalog
from football_edge.history.sync import load_matches
from football_edge.market.bridge import load_aliases, load_live_closings, pair

catalog = load_catalog(Path("config/history_leagues.yaml"))
codes = {league.league_id: league.code for league in catalog.leagues}
with connect() as conn:
    live = load_live_closings(conn, since=datetime.now(UTC) - timedelta(days=60))
    matches = load_matches(conn, catalog)
hist = [match for rows in matches.values() for match in rows]
pairing = pair(live, hist, aliases=load_aliases(Path("config/history_aliases.yaml")),
               codes_by_league_id=codes)
for closing in pairing.unmatched_live:
    print(closing.league_id, closing.kickoff.date(), closing.home, "|", closing.away)
EOF
```
Her eşlenemeyen canlı ad için football-data'daki karşılığı (aynı tarih, aynı lig dosyası) bulunur ve
`config/history_aliases.yaml`a yazılır; betik boş liste basana kadar tekrarlanır. Yalnız ADLAR yazılır
(takım adı içerik değil, kimliktir).

- [ ] **Step 13: Kilidi üret ve incele**

Run: `/usr/bin/time -l uv run --env-file .env python -m football_edge.history lock --write config/history_lock.yaml`
(`-l` macOS'ta en yüksek bellek kullanımını da basar: bütün taban ~240 bin maç belleğe yüklenir; ölçülmedi.
Tepe 2 GB'ı aşarsa Faz 3'ten önce bir bellek görevi açılır.)
İncele: holdout satır toplamı 22 ana ligde **7.647**, 16 ek ligde **4.446** (ölçüm belgesi §2.4 — farklıysa
commit'lenmez, fark bulunur). `avgc_complete / rows` holdout'ta ana liglerde 1.0, RUS'ta ~0.67.
Run: `uv run --env-file .env python -m football_edge.history lock --verify config/history_lock.yaml`
Expected: exit 0.

- [ ] **Step 14: Commit, kapı, push**

```bash
git add config/history_aliases.yaml config/history_lock.yaml
git commit -m "data: tarihsel taban kilidi (dev + holdout satır özetleri) ve takım adı eşlemesi

İlk tam yükleme: <tur kimliği>. Holdout 7.647 + 4.446 satır; özetler içerik taşımaz.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
`<tur kimliği>` Step 10'un Actions tur numarasıdır.

---

### Task 9: Piyasa verimliliği ölçümü ve raporu (T4)

**Kademe:** K1 · **Dalga:** 3 · **Worktree/dal:** `.worktrees/wt-efficiency` · `feat/faz2-efficiency`

**Files:**
- Create: `src/football_edge/market/efficiency.py`
- Create: `src/football_edge/market/__main__.py`
- Create: `tests/efficiency_samples.py` (iki test dosyasının paylaştığı sentetik örnekler)
- Test: `tests/test_efficiency.py`, `tests/test_market_cli.py`
- Gerçek rapor (`docs/reports/<tarih>-piyasa-verimliligi.md`) bu görevde ÜRETİLMEZ: `DATABASE_URL`
  ve Task 8'in commit'lediği kilidi ister; controller Task 12 Step 1'de bu CLI ile üretir.

**Interfaces:**
- Consumes:
  - Task 0: `CLOSING`, `PRE_CLOSING`, `H2H`, `TOTALS_25`, `HistMatch`.
  - Task 1: `MAIN`, `EXTRA`, `HistoryLeague(code, league_id, name, country, tier, kind,
    first_season, odds_api_key)`, `Catalog(current_season, leagues)`, `load_catalog(path: Path) -> Catalog`.
  - Task 2: `DEFAULT_METHOD`, `METHODS`, `MULTIPLICATIVE`, `SHIN`, `match_probs(…)`,
    `overround(prices: Sequence[float]) -> float`; `Interval`, `Calibration`, `bootstrap_mean`,
    `brier`, `calibration`, `log_loss`, `outcome_index`, `per_match_log_loss`, `rps`;
    `tests/market_factory.py` (`Prices`, `hist_match`, `with_prices`).
  - Task 3: `DEV`, `POST`, `HOLDOUT`, `DEV_END`, `HOLDOUT_END`, `Window`, `MAIN_WINDOW`,
    `EXTRA_WINDOW` (R89: holdout'a uzanan pencere kurulamaz), `in_window(match: HistMatch, window:
    Window) -> bool`, `HoldoutKey`, `select_periods(matches, *, periods, key=None)`; `Digest(rows,
    sha256, avgc_complete)`, `HistoryLock(canonical_version, locked_at, dev_end, holdout_end,
    leagues)`, `LockViolation(*differences)`, `build_lock(matches_by_league, *, locked_at)`,
    `dump_lock(lock) -> str`, `load_lock(path: Path) -> HistoryLock` (R99: bozuk dosya →
    `LockViolation`), `verify_lock(lock, matches_by_league) -> None` (yalnız testin sahtesinde).
  - Task 6 (R96): `load_matches(conn, catalog, *, lock: HistoryLock | None = None, key: HoldoutKey |
    None = None) -> Mapping[str, tuple[HistMatch, ...]]` — DEV + POST; `lock` verilirse ÖNCE bütün
    satırlar üzerinde `verify_lock` (`LockViolation`); önbellek eksik ya da sözleşme dışıysa
    `collector.ContractViolation`.
  - Task 7 (R91): `LiveClosing`, `load_aliases(path) -> Mapping[str, str]`,
    `load_live_closings(conn, *, since: datetime) -> tuple[LiveClosing, ...]`, `pair(live, hist, *,
    aliases, codes_by_league_id) -> Pairing`, `compare(pairing, *, method) -> BridgeReport` (n = 0 →
    `ValueError`), `render_bridge_report(report, *, generated_at, since) -> str`; Task 3'ten ayrıca
    `HOLDOUT_END` (köprünün varsayılan `--since`i: sonrası döneminin başı).
  - Mevcut: `collect.configure_logging`, `collect.EXIT_SOURCE_FAILED` (7), `collector.ContractViolation`,
    `db.connect`.
- Produces (sözleşme birebir; `# EK` işaretliler controller'ın kabul ettiği eklerdir, `# R91`/`# R92` kararları):
```python
# football_edge/market/efficiency.py  (pencereler Task 3'ün holdout.py'sinden: Window, MAIN_WINDOW, EXTRA_WINDOW)
@dataclass(frozen=True)
class LeagueEfficiency:
    code: str; league_id: str; kind: str; n: int
    margin: Interval; log_loss: Interval; brier: float; rps: float
    calibration: Calibration; slope: Interval
    late_info: Interval | None; value_rate: Interval | None; sharp_gap: Interval | None
    ou25_margin: Interval | None      # R92: AvgC>2.5/<2.5 kapanış marjı (bootstrap); ek ligde / tam satır yoksa None
    ou25_log_loss: Interval | None; ou25_calibration: Calibration | None
    exchange_gap: Interval | None     # R97: LL(AvgC) − LL(BFEC), ikisi ≥ %90 dolu lig-sezonlarda (D3)
class NoClosingPrices(ValueError): ...   # EK (m9): pencerede AvgC 1X2'si tam maç yok — CLI ligi "—" ile yazar
@dataclass(frozen=True)
class Ranking:
    late_info: tuple[str, ...]; miscalibration: tuple[str, ...]; tiers: Mapping[str, str]
def method_scores(matches: Sequence[HistMatch]) -> Mapping[str, float]   # yöntem → havuzlanmış AvgC LL
    # yalnız DEV; her yöntemin çözebildiği ORTAK maçlar (Shin'in çözemediği maç hiçbirine girmez)
def league_efficiency(league: HistoryLeague, matches: Sequence[HistMatch], *, method: str,
                      resamples: int = RESAMPLES) -> LeagueEfficiency     # EK: resamples (CLI --resamples)
def rank(rows: Sequence[LeagueEfficiency]) -> Ranking
def candidates(rows: Sequence[LeagueEfficiency], ranking: Ranking, *, lock: HistoryLock,
               leagues: Sequence[HistoryLeague]) -> tuple[str, ...]      # tasarım §8.4; (kademe, kod) sırası
def render_report(rows: Sequence[LeagueEfficiency], ranking: Ranking, *, scores: Mapping[str, float],
                  candidates: Sequence[str], generated_at: datetime,
                  unmeasured: Sequence[HistoryLeague] = ()) -> str       # EK (m9): ölçülemeyen ligler "—"
def best_method(scores: Mapping[str, float]) -> str                      # EK: en düşük LL, eşitlikte ad
RESAMPLES = 2000; MIN_MATCHES = 1000; MIN_HOLDOUT_COVERAGE = 0.95; SHARP_COVERAGE = 0.90   # EK
AVERAGE = "Avg"; BEST = "Max"; SHARP = "PS"; EXCHANGE = "BFE"            # EK: OddsKey.book önekleri

# football_edge/market/__main__.py
# python -m football_edge.market efficiency --out PATH [--lock config/history_lock.yaml]
#        [--catalog config/history_leagues.yaml] [--resamples 2000]
# python -m football_edge.market bridge --out PATH [--since 2026-07-01] [--catalog …]      # R91
#        [--aliases config/history_aliases.yaml] [--method shin]
EXIT_LOCK_VIOLATION = 9     # history CLI'ıyla aynı kod — bozuk kilit dosyası da (R99); önbellek → 7
EXIT_NO_PAIRS = 10          # EK: köprüde karşılaştırılabilir eşleşme yok (N = 0) — rapor yazılmaz
def main(argv: Sequence[str] | None = None) -> int
```

- [ ] **Step 1: Başarısız testleri yaz — örnekler ve ölçütler**
`tests/efficiency_samples.py` — tam içerik:
```python
"""Verimlilik testlerinin SENTETİK örnekleri — gerçek maç, takım ya da oran satırı değil."""

from __future__ import annotations

from datetime import date, timedelta

from football_edge.history.catalog import EXTRA, MAIN, HistoryLeague
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch
from tests.market_factory import Prices, hist_match, with_prices

MAIN_LEAGUE = HistoryLeague("M1", "m.1", "Ana Lig", "Xland", 1, MAIN, "0506", "soccer_m1")
EXTRA_LEAGUE = HistoryLeague("X1", "x.1", "Ek Lig", "Yland", 1, EXTRA, "", "")
# Dört AvgC kümesi (ilki adil: Σ 1/o = 1) ve yedi skor. 4 ile 7 aralarında asal: her fiyat
# kümesi her sonucu görür, kalibrasyon fiti hiçbir yeniden örneklemde ayrışmaz.
CLOSE_SETS = ((2.0, 4.0, 4.0), (1.6, 4.2, 6.0), (2.6, 3.3, 2.9), (3.4, 3.5, 2.2))
SCORES = ((2, 0), (1, 1), (0, 1), (3, 1), (0, 0), (1, 2), (2, 1))
TOTAL_SETS = ((1.8, 2.1), (2.2, 1.7), (1.95, 1.95))


def synthetic(
    count: int,
    *,
    start: date = date(2023, 8, 5),
    league: str = "M1",
    season: str = "2324",
    first: int = 0,
) -> tuple[HistMatch, ...]:
    """Haftada sekiz maç, sentetik takım adları, yalnız AvgC 1X2 fiyatı."""
    return tuple(
        hist_match(
            league=league,
            season=season,
            day=start + timedelta(days=7 * (index // 8)),
            home=f"Team {2 * (first + index):03d}",
            away=f"Team {2 * (first + index) + 1:03d}",
            goals=SCORES[index % 7],
            prices={("Avg", H2H, CLOSING): CLOSE_SETS[index % 4]},
            line=first + index + 1,
        )
        for index in range(count)
    )


def added(matches: tuple[HistMatch, ...], prices: Prices) -> tuple[HistMatch, ...]:
    return tuple(with_prices(match, prices) for match in matches)


def rich(matches: tuple[HistMatch, ...]) -> tuple[HistMatch, ...]:
    """Her ölçütün girdisi dolu: kapanış öncesi Avg/Max, PSC, BFEC, Ü/A 2.5 kapanışı."""
    return tuple(
        with_prices(
            match,
            {
                ("Avg", H2H, PRE_CLOSING): (3.0, 3.0, 3.0),
                ("Max", H2H, PRE_CLOSING): CLOSE_SETS[(index + 1) % 4],
                ("PS", H2H, CLOSING): CLOSE_SETS[(index + 2) % 4],
                ("BFE", H2H, CLOSING): CLOSE_SETS[(index + 3) % 4],
                ("Avg", TOTALS_25, CLOSING): TOTAL_SETS[index % 3],
            },
        )
        for index, match in enumerate(matches)
    )


BASE = synthetic(56)
```

`tests/test_efficiency.py` — tam içerik:
```python
"""Piyasa verimliliği: ölçüt tanımları, dönem ayrımı, sıralama, adaylar, rapor (tasarım §8)."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, date, datetime
from types import MappingProxyType

import pytest

from football_edge.history.catalog import EXTRA, MAIN, HistoryLeague
from football_edge.history.holdout import DEV, DEV_END, HOLDOUT, HOLDOUT_END
from football_edge.history.lock import Digest, HistoryLock
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch
from football_edge.market import efficiency
from football_edge.market.devig import METHODS, MULTIPLICATIVE, SHIN, match_probs, overround
from football_edge.market.efficiency import (
    LeagueEfficiency,
    NoClosingPrices,
    Ranking,
    best_method,
    candidates,
    league_efficiency,
    method_scores,
    rank,
    render_report,
)
from football_edge.market.metrics import (
    Calibration,
    Interval,
    brier,
    calibration,
    log_loss,
    outcome_index,
    per_match_log_loss,
    rps,
)
from tests.efficiency_samples import (
    BASE,
    CLOSE_SETS,
    EXTRA_LEAGUE,
    MAIN_LEAGUE,
    TOTAL_SETS,
    added,
    rich,
    synthetic,
)
from tests.market_factory import with_prices

FAST = 40  # testlerde bootstrap tekrarı; üretim varsayılanı 2000


def _closing_probs(
    matches: tuple[HistMatch, ...], method: str, book: str = "Avg"
) -> list[tuple[float, ...] | None]:
    return [match_probs(m, book=book, market=H2H, phase=CLOSING, method=method) for m in matches]


def _results(matches: tuple[HistMatch, ...]) -> list[int]:
    return [outcome_index(match, H2H) for match in matches]


def test_n_counts_only_matches_with_a_complete_closing_1x2() -> None:
    bare = tuple(replace(match, odds=MappingProxyType({})) for match in synthetic(4, first=100))
    result = league_efficiency(MAIN_LEAGUE, (*BASE, *bare), method=SHIN, resamples=FAST)
    assert (result.code, result.league_id, result.kind, result.n) == ("M1", "m.1", MAIN, 56)


def test_margin_and_closing_accuracy_use_avgc_devigged_with_the_method() -> None:
    result = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    probs, outcomes = _closing_probs(BASE, SHIN), _results(BASE)
    margins = [overround(CLOSE_SETS[index % 4]) for index in range(56)]
    assert result.margin.estimate == pytest.approx(math.fsum(margins) / 56)
    assert result.log_loss.estimate == pytest.approx(log_loss(probs, outcomes))
    assert result.brier == pytest.approx(brier(probs, outcomes))
    assert result.rps == pytest.approx(rps(probs, outcomes))
    assert result.calibration == calibration(probs, outcomes)
    plain = league_efficiency(MAIN_LEAGUE, BASE, method=MULTIPLICATIVE, resamples=FAST)
    assert plain.log_loss.estimate != pytest.approx(result.log_loss.estimate)


def test_slope_interval_refits_the_calibration_on_resampled_matches() -> None:
    result = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    assert result.slope.estimate == result.calibration.slope
    assert result.slope.low < result.slope.estimate < result.slope.high
    fewer = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=10)
    assert (fewer.slope.low, fewer.slope.high) != (result.slope.low, result.slope.high)


def test_late_info_is_pre_closing_minus_closing_log_loss_per_match() -> None:
    # Kapanış öncesi (3, 3, 3) → (1/3, 1/3, 1/3): LL_öncesi her maçta ln 3. Yalnız ilk 40 maçta
    # kapanış öncesi fiyat var; ΔLL o 40 maçın ortalamasıdır.
    early = (*added(BASE[:40], {("Avg", H2H, PRE_CLOSING): (3.0, 3.0, 3.0)}), *BASE[40:])
    result = league_efficiency(MAIN_LEAGUE, early, method=MULTIPLICATIVE, resamples=FAST)
    closing = log_loss(_closing_probs(BASE[:40], MULTIPLICATIVE), _results(BASE[:40]))
    assert result.late_info is not None
    assert result.late_info.estimate == pytest.approx(math.log(3) - closing)


def test_extra_leagues_have_no_late_info_value_rate_or_totals() -> None:
    extra = rich(synthetic(56, league="X1", season="2023"))
    result = league_efficiency(EXTRA_LEAGUE, extra, method=SHIN, resamples=FAST)
    assert result.n == 56
    assert (result.late_info, result.value_rate) == (None, None)
    assert (result.ou25_margin, result.ou25_log_loss, result.ou25_calibration) == (None, None, None)


def test_value_rate_counts_matches_where_a_best_price_beats_the_fair_closing_probability() -> None:
    # Çarpımsal yöntemde Max_i · p_i = (Max_i / AvgC_i) / B. Değer YALNIZ ev sonucunda: i % 3 == 0
    # ise Max_H = AvgC_H × 1.2 (1.2 / B > 1), öteki sonuçlar × 1.0 (1/B ≤ 1). "Herhangi bir sonuç"
    # tanımı (tasarım §8.2) bu maçları sayar; "her sonuç" (min) hiçbirini saymazdı.
    # Adil kümede (B = 1) Max = AvgC çarpımı TAM 1'dir ve değer SAYILMAZ (> 1, ≥ değil).
    # Son altı maçta Max yok: paydaya girmezler. Değer: i < 50 ve i % 3 == 0 → 17/50.
    best = tuple(
        with_prices(
            match,
            {
                ("Max", H2H, PRE_CLOSING): tuple(
                    price * (1.2 if index % 3 == 0 and outcome == 0 else 1.0)
                    for outcome, price in enumerate(CLOSE_SETS[index % 4])
                )
            },
        )
        for index, match in enumerate(BASE[:50])
    )
    result = league_efficiency(
        MAIN_LEAGUE, (*best, *BASE[50:]), method=MULTIPLICATIVE, resamples=FAST
    )
    assert result.value_rate is not None
    assert result.value_rate.estimate == pytest.approx(17 / 50)


def test_sharp_gap_uses_only_seasons_where_avgc_and_psc_are_ninety_percent_complete() -> None:
    full = synthetic(20, start=date(2020, 8, 1), season="2021")
    edge = synthetic(20, start=date(2021, 8, 7), season="2122", first=20)  # 18/20 = %90: girer
    thin = synthetic(20, start=date(2022, 8, 6), season="2223", first=40)  # 17/20 = %85: girmez
    sharp = {("PS", H2H, CLOSING): (1.9, 3.8, 3.8)}
    seasons = (*added(full, sharp), *added(edge[:18], sharp), *edge[18:])
    matches = (*seasons, *added(thin[:17], sharp), *thin[17:])
    result = league_efficiency(MAIN_LEAGUE, matches, method=SHIN, resamples=FAST)
    used = (*added(full, sharp), *added(edge[:18], sharp))
    average = per_match_log_loss(_closing_probs(used, SHIN), _results(used))
    keen = per_match_log_loss(_closing_probs(used, SHIN, book="PS"), _results(used))
    assert result.sharp_gap is not None
    expected = math.fsum(a - s for a, s in zip(average, keen, strict=True)) / len(used)
    assert result.sharp_gap.estimate == pytest.approx(expected)


def test_sharp_and_exchange_gaps_are_none_when_no_season_qualifies() -> None:
    result = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    assert (result.sharp_gap, result.exchange_gap) == (None, None)


def test_exchange_gap_uses_only_seasons_where_avgc_and_bfec_are_ninety_percent_complete() -> None:
    # R97 (D3 "BFEC varsa raporlanır"): keskinlik farkıyla aynı kural, kitap BFE (Betfair borsası).
    # PSC hiç yok: iki fark birbirinden bağımsız hesaplanır.
    full = synthetic(20, start=date(2023, 8, 5), season="2324", first=600)  # 20/20: girer
    thin = synthetic(20, start=date(2024, 8, 3), season="2425", first=620)  # 17/20: girmez
    exchange = {("BFE", H2H, CLOSING): (1.8, 4.0, 4.4)}
    matches = (*added(full, exchange), *added(thin[:17], exchange), *thin[17:])
    result = league_efficiency(MAIN_LEAGUE, matches, method=SHIN, resamples=FAST)
    used = added(full, exchange)
    average = per_match_log_loss(_closing_probs(used, SHIN), _results(used))
    betfair = per_match_log_loss(_closing_probs(used, SHIN, book="BFE"), _results(used))
    assert result.sharp_gap is None
    assert result.exchange_gap is not None
    expected = math.fsum(a - b for a, b in zip(average, betfair, strict=True)) / len(used)
    assert result.exchange_gap.estimate == pytest.approx(expected)


def test_totals_metrics_use_the_closing_over_under_on_main_leagues() -> None:
    totals = tuple(
        with_prices(match, {("Avg", TOTALS_25, CLOSING): TOTAL_SETS[index % 3]})
        for index, match in enumerate(BASE)
    )
    result = league_efficiency(MAIN_LEAGUE, totals, method=SHIN, resamples=FAST)
    probs = [
        match_probs(match, book="Avg", market=TOTALS_25, phase=CLOSING, method=SHIN)
        for match in totals
    ]
    outcomes = [outcome_index(match, TOTALS_25) for match in totals]
    margins = [overround(TOTAL_SETS[index % 3]) for index in range(56)]
    assert result.ou25_margin is not None
    assert result.ou25_margin.estimate == pytest.approx(math.fsum(margins) / 56)
    assert result.ou25_log_loss is not None
    assert result.ou25_log_loss.estimate == pytest.approx(log_loss(probs, outcomes))
    assert result.ou25_calibration == calibration(probs, outcomes)
    bare = league_efficiency(MAIN_LEAGUE, BASE, method=SHIN, resamples=FAST)
    assert (bare.ou25_margin, bare.ou25_log_loss, bare.ou25_calibration) == (None, None, None)


def test_a_league_without_closing_prices_is_a_named_error() -> None:
    bare = tuple(replace(match, odds=MappingProxyType({})) for match in BASE)
    with pytest.raises(NoClosingPrices, match="M1"):
        league_efficiency(MAIN_LEAGUE, bare, method=SHIN, resamples=FAST)


def _later() -> tuple[HistMatch, ...]:
    """Holdout ve sonrası tarihli, ölçütleri belirgin biçimde değiştirecek maçlar."""
    holdout = synthetic(56, start=date(2025, 8, 2), season="2526", first=200)
    post = synthetic(16, start=date(2026, 8, 1), season="2627", first=300)
    lopsided = {("Avg", H2H, CLOSING): (1.3, 5.5, 11.0)}
    return rich(added((*holdout, *post), lopsided))


@pytest.mark.leakage
def test_holdout_and_post_matches_never_reach_any_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pencere bilerek devre dışı bırakılır (R89: holdout'a uzanan pencere kurulamaz): holdout'u
    # yalnız dönem süzgeci durdurur. Koruma: pencerenin normalde düşürdüğü 2018/19 maçı geçmeli.
    monkeypatch.setattr(efficiency, "in_window", lambda match, window: True)
    early = synthetic(4, start=date(2018, 8, 4), season="1819", first=700)
    assert efficiency._development_rows(MAIN_LEAGUE, early) == early, "yama etkisiz: test kör kalır"
    development = rich(BASE)
    mixed = league_efficiency(MAIN_LEAGUE, (*development, *_later()), method=SHIN, resamples=FAST)
    assert mixed == league_efficiency(MAIN_LEAGUE, development, method=SHIN, resamples=FAST)


@pytest.mark.leakage
def test_method_scores_ignore_matches_outside_the_development_period() -> None:
    assert method_scores((*BASE, *_later())) == method_scores(BASE)


def test_main_window_drops_development_matches_before_2019_20_but_extra_keeps_them() -> None:
    early = synthetic(20, start=date(2018, 8, 4), season="1819", first=400)
    assert league_efficiency(MAIN_LEAGUE, (*BASE, *early), method=SHIN, resamples=FAST).n == 56
    extra = synthetic(56, league="X1", season="2023")
    extra_early = synthetic(20, start=date(2014, 3, 1), league="X1", season="2014", first=500)
    result = league_efficiency(EXTRA_LEAGUE, (*extra, *extra_early), method=SHIN, resamples=FAST)
    assert result.n == 76


def test_method_scores_compare_every_method_on_the_same_matches() -> None:
    # Σ 1/o < 1: Shin çözemez → bu maç HİÇBİR yöntemin puanına girmez (ortak küme).
    under = with_prices(synthetic(1, first=900)[0], {("Avg", H2H, CLOSING): (2.2, 4.4, 4.4)})
    scores = method_scores((*BASE, under))
    assert tuple(scores) == METHODS
    for method in METHODS:
        assert scores[method] == pytest.approx(
            log_loss(_closing_probs(BASE, method), _results(BASE))
        )


def test_best_method_picks_the_lowest_log_loss_and_breaks_ties_by_name() -> None:
    assert best_method({"multiplicative": 0.99, "power": 0.97, "shin": 0.98}) == "power"
    assert best_method({"multiplicative": 0.97, "power": 0.98, "shin": 0.97}) == "multiplicative"


def _row(
    code: str,
    *,
    kind: str = MAIN,
    n: int = 1500,
    late: tuple[float, float, float] | None = None,
    slope: tuple[float, float, float] = (1.0, 0.95, 1.05),
    ece: float = 0.01,
) -> LeagueEfficiency:
    """Sıralama/aday testleri için elle kurulan satır; yalnız ilgili alanlar anlamlı."""
    return LeagueEfficiency(
        code=code,
        league_id=code.lower(),
        kind=kind,
        n=n,
        margin=Interval(0.05, 0.04, 0.06),
        log_loss=Interval(0.97, 0.96, 0.98),
        brier=0.57,
        rps=0.19,
        calibration=Calibration(slope=slope[0], intercept=0.0, ece=ece, n=3 * n),
        slope=Interval(*slope),
        late_info=None if late is None else Interval(*late),
        value_rate=None,
        sharp_gap=None,
        ou25_margin=None,
        ou25_log_loss=None,
        ou25_calibration=None,
        exchange_gap=None,
    )


def test_rank_orders_late_info_descending_over_main_leagues_only() -> None:
    rows = (
        _row("M1", late=(0.02, 0.01, 0.03)),
        _row("M2", late=(0.05, 0.04, 0.06)),
        _row("M3", late=(0.03, 0.02, 0.04)),
        _row("X1", kind=EXTRA),
    )
    assert rank(rows).late_info == ("M2", "M3", "M1")


def test_rank_orders_miscalibration_by_slope_distance_then_ece() -> None:
    rows = (
        _row("L1", kind=EXTRA, slope=(0.5, 0.45, 0.55)),  # |b − 1| = 0.5
        _row("L2", kind=EXTRA, slope=(1.25, 1.2, 1.3), ece=0.01),  # 0.25, ECE küçük
        _row("L3", kind=EXTRA, slope=(0.75, 0.7, 0.8), ece=0.03),  # 0.25, ECE büyük
        _row("L4", kind=EXTRA, slope=(1.0, 0.95, 1.05)),  # 0
    )
    assert rank(rows).miscalibration == ("L1", "L3", "L2", "L4")


def test_tiers_compare_interval_ends_with_the_median_estimate() -> None:
    # Altı ek lig kalibrasyon medyanını 0.3'e çeker: ana liglerin kalibrasyon kademesi C olur ve
    # görünen kademe yalnız geç bilgininkidir. Geç bilgi medyanı 0.02.
    main = (
        _row("M1", late=(0.05, 0.04, 0.06)),  # alt uç > medyan → A
        _row("M2", late=(0.03, 0.02, 0.04)),  # alt uç = medyan → A DEĞİL, B
        _row("M3", late=(0.02, 0.01, 0.03)),  # medyanı içerir → B
        _row("M4", late=(0.01, 0.0, 0.015)),  # üst uç < medyan → C
        _row("M5", late=(0.015, 0.005, 0.02)),  # üst uç = medyan → C DEĞİL, B
    )
    tight = tuple(replace(row, slope=Interval(1.01, 1.005, 1.015)) for row in main)
    padding = tuple(_row(f"E{i}", kind=EXTRA, slope=(1.3, 1.29, 1.31)) for i in range(6))
    tiers = rank((*tight, *padding)).tiers
    assert {code: tiers[code] for code in ("M1", "M2", "M3", "M4", "M5")} == {
        "M1": "A",
        "M2": "B",
        "M3": "B",
        "M4": "C",
        "M5": "B",
    }
    assert {tiers[f"E{i}"] for i in range(6)} == {"B"}


def test_a_league_takes_the_better_of_its_two_tiers() -> None:
    rows = (
        _row("P1", late=(0.05, 0.045, 0.055), slope=(1.0, 0.99, 1.01)),  # geç A · kalibrasyon B
        _row("P2", late=(0.03, 0.025, 0.035), slope=(1.0, 0.99, 1.01)),  # geç B · kalibrasyon B
        _row("P3", late=(0.01, 0.005, 0.015), slope=(1.5, 1.45, 1.55)),  # geç C · kalibrasyon A
    )
    assert dict(rank(rows).tiers) == {"P1": "A", "P2": "B", "P3": "A"}


def test_miscalibration_tier_uses_the_distance_interval_of_the_slope() -> None:
    # Q1 (0.5, 0.7) → |b−1| ∈ [0.3, 0.5] · Q2 (0.7, 1.45) 1'i içerir → [0, 0.45] · Q3 → [0.15, 0.25]
    # Medyan 0.2: Q1 A; Q2'nin alt ucu 0 → B (uçların mutlak değeri [0.3, 0.45] A derdi); Q3 B.
    rows = (
        _row("Q1", kind=EXTRA, slope=(0.6, 0.5, 0.7)),
        _row("Q2", kind=EXTRA, slope=(1.0, 0.7, 1.45)),
        _row("Q3", kind=EXTRA, slope=(1.2, 1.15, 1.25)),
    )
    assert dict(rank(rows).tiers) == {"Q1": "A", "Q2": "B", "Q3": "B"}


def _lock(coverage: dict[str, tuple[int, int]]) -> HistoryLock:
    """Lig → (holdout AvgC tam satır, holdout satır); holdout SATIRI yok, yalnız özet."""
    return HistoryLock(
        canonical_version=1,
        locked_at=date(2026, 9, 29),
        dev_end=DEV_END,
        holdout_end=HOLDOUT_END,
        leagues=MappingProxyType(
            {
                code: MappingProxyType(
                    {
                        DEV: Digest(rows=5000, sha256="0" * 64, avgc_complete=5000),
                        HOLDOUT: Digest(rows=rows, sha256="1" * 64, avgc_complete=complete),
                    }
                )
                for code, (complete, rows) in coverage.items()
            }
        ),
    )


def _catalog_entry(code: str, key: str) -> HistoryLeague:
    return HistoryLeague(code, code.lower(), code, "Xland", 1, MAIN, "0506", key)


def _chosen(
    *, n: int = 1000, holdout: tuple[int, int] = (95, 100), key: str = "soccer_c1", tier: str = "B"
) -> tuple[str, ...]:
    ranking = Ranking(late_info=(), miscalibration=("C1",), tiers=MappingProxyType({"C1": tier}))
    return candidates(
        (_row("C1", n=n),),
        ranking,
        lock=_lock({"C1": holdout}),
        leagues=(_catalog_entry("C1", key),),
    )


def test_a_league_at_every_boundary_is_a_candidate() -> None:
    assert _chosen() == ("C1",)  # N = 1000, holdout 95/100 = %95, anahtar var, kademe B


@pytest.mark.parametrize(
    "change",
    ({"n": 999}, {"key": ""}, {"tier": "C"}),
    ids=("n-999", "anahtar-yok", "kademe-c"),
)
def test_candidates_need_enough_matches_an_api_key_and_tier_a_or_b(
    change: dict[str, object],
) -> None:
    assert _chosen(**change) == ()  # type: ignore[arg-type]


@pytest.mark.leakage
@pytest.mark.parametrize("holdout", ((94, 100), (0, 0)), ids=("yuzde-94", "holdout-bos"))
def test_holdout_coverage_comes_from_the_lock_digest(holdout: tuple[int, int]) -> None:
    assert _chosen(holdout=holdout) == ()


def test_candidates_are_ordered_by_tier_then_code() -> None:
    ranking = Ranking(
        late_info=(), miscalibration=("C1", "C2"), tiers=MappingProxyType({"C1": "B", "C2": "A"})
    )
    chosen = candidates(
        (_row("C1"), _row("C2")),
        ranking,
        lock=_lock({"C1": (100, 100), "C2": (100, 100)}),
        leagues=(_catalog_entry("C1", "k1"), _catalog_entry("C2", "k2")),
    )
    assert chosen == ("C2", "C1")


def test_candidates_refuse_a_league_missing_from_the_lock_or_the_catalog() -> None:
    ranking = Ranking(late_info=(), miscalibration=("C1",), tiers=MappingProxyType({"C1": "A"}))
    with pytest.raises(ValueError, match="kilitte"):
        candidates((_row("C1"),), ranking, lock=_lock({}), leagues=(_catalog_entry("C1", "k"),))
    with pytest.raises(ValueError, match="kataloğunda"):
        candidates((_row("C1"),), ranking, lock=_lock({"C1": (100, 100)}), leagues=())


UNMEASURED = HistoryLeague("X9", "x.9", "Boş Lig", "Zland", 1, EXTRA, "", "")


def _report(scores: dict[str, float], chosen: tuple[str, ...] = ("M1",)) -> str:
    main = league_efficiency(MAIN_LEAGUE, rich(BASE), method=SHIN, resamples=FAST)
    extra = league_efficiency(
        EXTRA_LEAGUE, synthetic(56, league="X1", season="2023"), method=SHIN, resamples=FAST
    )
    return render_report(
        (main, extra),
        rank((main, extra)),
        scores=scores,
        candidates=chosen,
        generated_at=datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
        unmeasured=(UNMEASURED,),
    )


SHIN_BEST = {"multiplicative": 0.99, "power": 0.98, "shin": 0.97}


def test_report_has_every_section_and_only_aggregates() -> None:
    text = _report(SHIN_BEST)
    for heading in (
        "# Piyasa verimliliği — geliştirme dönemi",
        "## Vig yöntemleri (K2)",
        "## Lig başına ölçütler",
        "## Sıralamalar",
        "### R1 — geç bilgi",
        "### R2 — kapanış kalibrasyon hatası",
        "## Aday ligler",
        "## Raporun ölçmedikleri",
    ):
        assert heading in text, heading
    assert "| Keskinlik farkı (PSC) | Borsa farkı (BFEC) | Ü/A 2.5 marj |" in text
    assert "| M1 | m.1 | main | 56 |" in text
    assert "| X1 | x.1 | extra | 56 |" in text
    assert "GERİYE DÖNÜK ÜST SINIRDIR" in text
    assert "- M1" in text
    for item in (
        "2019/20 öncesi ana lig satırlarında saat yok",
        "kitap kümesi zamanla değişiyor",
        "Holdout'ta `PSC` kullanılamaz",
        "Bootstrap maçları bağımsız sayar",
    ):
        assert item in text, item
    assert "Team 0" not in text  # takım adı (ham satır) rapora giremez
    assert text.endswith("\n")


def test_report_prints_a_dash_for_metrics_a_league_does_not_have() -> None:
    extra_line = next(line for line in _report(SHIN_BEST).splitlines() if line.startswith("| X1"))
    # Ek ligde geç bilgi, değer sıklığı ve Ü/A üçlüsü (marj, LL, eğim) yok; PSC ve BFEC'siz
    # keskinlik ve borsa farkı da yok.
    assert extra_line.count("—") == 7


def test_a_league_that_could_not_be_measured_keeps_a_dash_row() -> None:
    # m9: ölçülemeyen lig rapordan DÜŞMEZ — N = 0 ve on dört ölçüt sütununun hepsi "—".
    lines = _report(SHIN_BEST).splitlines()
    (row,) = [line for line in lines if line.startswith("| X9 ")]
    assert row == "| X9 | x.9 | extra | 0 | " + " | ".join(["—"] * 14) + " |"
    header = next(line for line in lines if line.startswith("| Lig |"))
    assert row.count("|") == header.count("|")


def test_report_names_the_selected_method_and_flags_a_default_it_did_not_choose() -> None:
    assert "Seçilen yöntem: **shin**" in _report(SHIN_BEST)
    assert "UYARI" not in _report(SHIN_BEST)
    power_best = {"multiplicative": 0.99, "power": 0.96, "shin": 0.97}
    text = _report(power_best)
    assert "Seçilen yöntem: **power**" in text
    assert "UYARI" in text


def test_report_says_when_there_is_no_candidate() -> None:
    assert "Aday lig yok." in _report(SHIN_BEST, chosen=())
```

- [ ] **Step 2: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_efficiency.py -q`
Expected: FAIL — `ImportError: cannot import name 'efficiency' from 'football_edge.market'`

- [ ] **Step 3: En küçük uygulamayı yaz — `efficiency.py`**

Savunma iki katmanlıdır ve katmanlar bilerek ayrı: önce `select_periods` yalnız DEV'i bırakır, sonra
pencere. Sızıntı testi `efficiency.in_window`u yamalayıp pencereyi devre dışı bırakır (R89 holdout'a
uzanan bir pencere kurdurmaz) ve holdout'u yalnız dönem süzgecinin durdurduğunu kanıtlar — bu yüzden
`in_window` bu modülün adıyla çağrılır (koruma satırı: pencerenin normalde düşürdüğü 2018/19 maçı
yamadan sonra geçer). Holdout doluluğu yalnız kilidin `Digest`inden gelir. Ü/A 2.5 marjı (R92) log
loss ile AYNI tam satırlardan; PSC ve BFEC farkı (R97) tek `_book_gap` kuralıyla. AvgC'si tam maçı
olmayan lig `NoClosingPrices` fırlatır (m9). Dosya ~500 satır (hedef 400'ü aşar, 800 sınırının
altında): rapor yazımı sözleşmede aynı modülde.
`src/football_edge/market/efficiency.py` — tam içerik:
```python
"""Lig başına piyasa verimliliği — yalnız geliştirme dönemi (tasarım §8, D12).

Holdout'a dokunmaz: önce `select_periods` yalnız DEV satırlarını bırakır, sonra pencere uygulanır.
İki katman bilerek ayrı: pencere bir gün yanlış yazılsa da holdout içeri giremez. Holdout
doluluğu (aday kuralı) satırlardan değil, kilitteki özetten okunur.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from types import MappingProxyType

import numpy as np

from football_edge.history.catalog import MAIN, HistoryLeague
from football_edge.history.holdout import (
    DEV,
    EXTRA_WINDOW,
    HOLDOUT,
    MAIN_WINDOW,
    Window,
    in_window,
    select_periods,
)
from football_edge.history.lock import HistoryLock
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, TOTALS_25, HistMatch
from football_edge.market.devig import DEFAULT_METHOD, METHODS, match_probs, overround
from football_edge.market.metrics import (
    Calibration,
    Interval,
    bootstrap_mean,
    brier,
    calibration,
    log_loss,
    outcome_index,
    per_match_log_loss,
    rps,
)

AVERAGE = "Avg"  # (Avg, CLOSING) = AvgC, referans kapanış (D3); (Avg, PRE_CLOSING) = Avg
BEST = "Max"  # (Max, PRE_CLOSING): kapanış öncesi en iyi fiyat
SHARP = "PS"  # (PS, CLOSING) = PSC: keskin kitabın kapanışı
EXCHANGE = "BFE"  # (BFE, CLOSING) = BFEC: Betfair borsası kapanışı (D3 "varsa raporlanır", R97)
SHARP_COVERAGE = 0.90  # PSC/BFEC farkı: AvgC ile birlikte lig-sezonda doluluk alt sınırı
MIN_MATCHES = 1000  # aday: geliştirme N alt sınırı (tasarım §8.4)
MIN_HOLDOUT_COVERAGE = 0.95  # aday: kilitteki holdout AvgC doluluğu alt sınırı
RESAMPLES = 2000
SEED = 20260922
LEVEL = 0.95


@dataclass(frozen=True)
class LeagueEfficiency:
    code: str
    league_id: str
    kind: str
    n: int
    margin: Interval
    log_loss: Interval
    brier: float
    rps: float
    calibration: Calibration
    slope: Interval
    late_info: Interval | None
    value_rate: Interval | None
    sharp_gap: Interval | None
    ou25_margin: Interval | None
    ou25_log_loss: Interval | None
    ou25_calibration: Calibration | None
    exchange_gap: Interval | None


@dataclass(frozen=True)
class Ranking:
    late_info: tuple[str, ...]
    miscalibration: tuple[str, ...]
    tiers: Mapping[str, str]


class NoClosingPrices(ValueError):
    """Ligin geliştirme penceresinde AvgC 1X2'si tam tek maç yok: ölçülemez, rapor onu "—" yazar."""


@dataclass(frozen=True)
class _Sample:
    """Aynı sırada hizalanmış maçlar, fiyatlar, adil olasılıklar ve gerçekleşen sonuç sıraları."""

    matches: tuple[HistMatch, ...]
    prices: tuple[tuple[float, ...], ...]
    probs: tuple[tuple[float, ...], ...]
    outcomes: tuple[int, ...]


def _window(league: HistoryLeague) -> Window:
    return MAIN_WINDOW if league.kind == MAIN else EXTRA_WINDOW


def _development_rows(league: HistoryLeague, matches: Sequence[HistMatch]) -> tuple[HistMatch, ...]:
    development = select_periods(matches, periods=frozenset({DEV}))
    window = _window(league)
    # `in_window` bu modülün adıyla çağrılır: sızıntı testi onu yamalayıp (R89 holdout'a uzanan
    # pencereyi yasaklar) holdout'u yalnız dönem süzgecinin durdurduğunu kanıtlar.
    return tuple(match for match in development if in_window(match, window))


def _closing(match: HistMatch, book: str, method: str) -> tuple[float, ...] | None:
    return match_probs(match, book=book, market=H2H, phase=CLOSING, method=method)


def _sample(
    matches: Sequence[HistMatch], *, book: str, market: str, phase: str, method: str
) -> _Sample:
    rows = [
        (match, prices, probs, outcome_index(match, market))
        for match in matches
        if (prices := match.prices(book, market, phase)) is not None
        and (probs := match_probs(match, book=book, market=market, phase=phase, method=method))
        is not None
    ]
    return _Sample(
        matches=tuple(row[0] for row in rows),
        prices=tuple(row[1] for row in rows),
        probs=tuple(row[2] for row in rows),
        outcomes=tuple(row[3] for row in rows),
    )


def _slope_interval(close: _Sample, estimate: float, *, resamples: int) -> Interval:
    """Eğimin yüzdelik aralığı: maçlar yeniden örneklenir, fit her örnekte YENİDEN kurulur."""
    rng = np.random.default_rng(SEED)
    size = len(close.matches)
    slopes = []
    for _ in range(resamples):
        picked = rng.integers(0, size, size=size)
        probs = [close.probs[index] for index in picked]
        slopes.append(calibration(probs, [close.outcomes[index] for index in picked]).slope)
    tail = (1.0 - LEVEL) / 2.0 * 100.0
    low, high = np.percentile(slopes, [tail, 100.0 - tail])
    return Interval(estimate=estimate, low=float(low), high=float(high))


def _late_info(close: _Sample, *, method: str, resamples: int) -> Interval | None:
    """Maç başına LL(kapanış öncesi Avg) − LL(AvgC): büyükse bilgi kapanıştan önce gelmiyor."""
    rows = [
        (early, late, outcome)
        for match, late, outcome in zip(close.matches, close.probs, close.outcomes, strict=True)
        if (early := match_probs(match, book=AVERAGE, market=H2H, phase=PRE_CLOSING, method=method))
        is not None
    ]
    if not rows:
        return None
    outcomes = [row[2] for row in rows]
    early_loss = per_match_log_loss([row[0] for row in rows], outcomes)
    late_loss = per_match_log_loss([row[1] for row in rows], outcomes)
    gaps = [early - late for early, late in zip(early_loss, late_loss, strict=True)]
    return bootstrap_mean(gaps, resamples=resamples)


def _value_rate(close: _Sample, *, resamples: int) -> Interval | None:
    """max_i(Max_i · p_kapanış_i) > 1 olan maçların payı — geriye dönük üst sınır."""
    hits = [
        1.0 if max(price * fair for price, fair in zip(best, probs, strict=True)) > 1.0 else 0.0
        for match, probs in zip(close.matches, close.probs, strict=True)
        if (best := match.prices(BEST, H2H, PRE_CLOSING)) is not None
    ]
    return bootstrap_mean(hits, resamples=resamples) if hits else None


def _book_gap(
    rows: Sequence[HistMatch], *, book: str, method: str, resamples: int
) -> Interval | None:
    """LL(AvgC) − LL(`book` kapanışı), yalnız ikisinin birlikte ≥ %90 dolu olduğu lig-sezonlarda."""
    gaps: list[float] = []
    for season in sorted({match.season for match in rows}):
        members = [match for match in rows if match.season == season]
        both = [
            (average, other, outcome_index(match, H2H))
            for match in members
            if (average := _closing(match, AVERAGE, method)) is not None
            and (other := _closing(match, book, method)) is not None
        ]
        if len(both) / len(members) < SHARP_COVERAGE:
            continue
        outcomes = [row[2] for row in both]
        average_loss = per_match_log_loss([row[0] for row in both], outcomes)
        other_loss = per_match_log_loss([row[1] for row in both], outcomes)
        gaps.extend(a - o for a, o in zip(average_loss, other_loss, strict=True))
    return bootstrap_mean(gaps, resamples=resamples) if gaps else None


def _totals(
    rows: Sequence[HistMatch], *, method: str, resamples: int
) -> tuple[Interval | None, Interval | None, Calibration | None]:
    """Ü/A 2.5 kapanışı (AvgC>2.5, AvgC<2.5): marj, log loss, kalibrasyon — tam satır yoksa None."""
    sample = _sample(rows, book=AVERAGE, market=TOTALS_25, phase=CLOSING, method=method)
    if not sample.matches:
        return None, None, None
    margin = bootstrap_mean([overround(prices) for prices in sample.prices], resamples=resamples)
    loss = bootstrap_mean(per_match_log_loss(sample.probs, sample.outcomes), resamples=resamples)
    return margin, loss, calibration(sample.probs, sample.outcomes)


def league_efficiency(
    league: HistoryLeague, matches: Sequence[HistMatch], *, method: str, resamples: int = RESAMPLES
) -> LeagueEfficiency:
    """Tasarım §8.2'nin ölçütleri; N = geliştirme penceresinde AvgC 1X2'si tam maçlar."""
    rows = _development_rows(league, matches)
    close = _sample(rows, book=AVERAGE, market=H2H, phase=CLOSING, method=method)
    if not close.matches:
        raise NoClosingPrices(f"{league.code}: geliştirme penceresinde AvgC 1X2'si tam maç yok")
    main = league.kind == MAIN
    fit = calibration(close.probs, close.outcomes)
    margin = bootstrap_mean([overround(prices) for prices in close.prices], resamples=resamples)
    ou25_margin, ou25_loss, ou25_fit = (
        _totals(rows, method=method, resamples=resamples) if main else (None, None, None)
    )
    return LeagueEfficiency(
        code=league.code,
        league_id=league.league_id,
        kind=league.kind,
        n=len(close.matches),
        margin=margin,
        log_loss=bootstrap_mean(
            per_match_log_loss(close.probs, close.outcomes), resamples=resamples
        ),
        brier=brier(close.probs, close.outcomes),
        rps=rps(close.probs, close.outcomes),
        calibration=fit,
        slope=_slope_interval(close, fit.slope, resamples=resamples),
        late_info=_late_info(close, method=method, resamples=resamples) if main else None,
        value_rate=_value_rate(close, resamples=resamples) if main else None,
        sharp_gap=_book_gap(rows, book=SHARP, method=method, resamples=resamples),
        ou25_margin=ou25_margin,
        ou25_log_loss=ou25_loss,
        ou25_calibration=ou25_fit,
        exchange_gap=_book_gap(rows, book=EXCHANGE, method=method, resamples=resamples),
    )


def _every_method(match: HistMatch) -> tuple[tuple[float, ...], ...] | None:
    found: list[tuple[float, ...]] = []
    for method in METHODS:
        probs = _closing(match, AVERAGE, method)
        if probs is None:
            return None
        found.append(probs)
    return tuple(found)


def method_scores(matches: Sequence[HistMatch]) -> Mapping[str, float]:
    """Yöntem → havuzlanmış AvgC log loss'u; her yöntemin çözdüğü ORTAK geliştirme maçlarında."""
    table = [
        (probs, outcome_index(match, H2H))
        for match in select_periods(matches, periods=frozenset({DEV}))
        if (probs := _every_method(match)) is not None
    ]
    if not table:
        raise ValueError("geliştirme döneminde her yöntemin çözebildiği AvgC maçı yok")
    outcomes = [outcome for _, outcome in table]
    scores = {
        method: log_loss([probs[index] for probs, _ in table], outcomes)
        for index, method in enumerate(METHODS)
    }
    return MappingProxyType(scores)


def best_method(scores: Mapping[str, float]) -> str:
    """En düşük havuzlanmış log loss'lu yöntem; eşitlikte ada göre (tasarım §6)."""
    return min(scores, key=lambda method: (scores[method], method))


def _distance(slope: Interval) -> Interval:
    """|b − 1| ve aralığı: eğim aralığı 1'i içeriyorsa uzaklığın alt ucu 0'dır."""
    estimate = abs(slope.estimate - 1.0)
    if slope.low > 1.0:
        return Interval(estimate, slope.low - 1.0, slope.high - 1.0)
    if slope.high < 1.0:
        return Interval(estimate, 1.0 - slope.high, 1.0 - slope.low)
    return Interval(estimate, 0.0, max(1.0 - slope.low, slope.high - 1.0))


def _tiers(intervals: Mapping[str, Interval]) -> dict[str, str]:
    """Aralık medyanın açıkça üstündeyse A, açıkça altındaysa C, medyanı içeriyorsa B."""
    if not intervals:
        return {}
    middle = median(interval.estimate for interval in intervals.values())
    return {
        code: "A" if interval.low > middle else ("C" if interval.high < middle else "B")
        for code, interval in intervals.items()
    }


def rank(rows: Sequence[LeagueEfficiency]) -> Ranking:
    """R1 geç bilgi (ana ligler) ve R2 kalibrasyon hatası; bileşik puan YOK (tasarım §8.3)."""
    late = {row.code: row.late_info for row in rows if row.late_info is not None}
    distance = {row.code: _distance(row.slope) for row in rows}
    ece = {row.code: row.calibration.ece for row in rows}
    late_order = sorted(late, key=lambda code: (-late[code].estimate, code))
    miss_order = sorted(distance, key=lambda code: (-distance[code].estimate, -ece[code], code))
    late_tiers, miss_tiers = _tiers(late), _tiers(distance)
    # Ligin kademesi iki sıralamadaki İYİSİDİR: "A" < "B" < "C".
    tiers = {code: min(tier, late_tiers.get(code, "C")) for code, tier in miss_tiers.items()}
    return Ranking(tuple(late_order), tuple(miss_order), MappingProxyType(tiers))


def _holdout_coverage(lock: HistoryLock, code: str) -> float:
    """Holdout satırı OKUNMAZ: doluluk kilitteki özetten gelir (avgc_complete / rows)."""
    periods = lock.leagues.get(code)
    if periods is None or HOLDOUT not in periods:
        raise ValueError(f"{code}: kilitte holdout özeti yok")
    digest = periods[HOLDOUT]
    return digest.avgc_complete / digest.rows if digest.rows else 0.0


def _odds_api_key(leagues: Sequence[HistoryLeague], code: str) -> str:
    for league in leagues:
        if league.code == code:
            return league.odds_api_key
    raise ValueError(f"{code}: lig kataloğunda yok")


def candidates(
    rows: Sequence[LeagueEfficiency],
    ranking: Ranking,
    *,
    lock: HistoryLock,
    leagues: Sequence[HistoryLeague],
) -> tuple[str, ...]:
    """Tasarım §8.4: N ≥ 1000 · holdout AvgC ≥ %95 · Odds API anahtarı · R1/R2'de A ya da B."""
    chosen = [
        row.code
        for row in rows
        if row.n >= MIN_MATCHES
        and _holdout_coverage(lock, row.code) >= MIN_HOLDOUT_COVERAGE
        and _odds_api_key(leagues, row.code) != ""
        and ranking.tiers.get(row.code) in ("A", "B")
    ]
    return tuple(sorted(chosen, key=lambda code: (ranking.tiers[code], code)))


# ── Rapor: yalnız toplu sayılar; ham satır, takım adı, tarih YOK (spec §3.2/4) ──────────────

_HEADER = (
    "| Lig | Kimlik | Tür | N | Marj | Log loss | Brier | RPS | Eğim b | Kesişim a | ECE "
    "| Geç bilgi ΔLL | Değer sıklığı* | Keskinlik farkı (PSC) | Borsa farkı (BFEC) "
    "| Ü/A 2.5 marj | Ü/A 2.5 LL | Ü/A 2.5 eğim |"
)
_VALUE_NOTE = (
    "\\* Değer sıklığı GERİYE DÖNÜK ÜST SINIRDIR, ulaşılabilir değildir: adil kapanış olasılığı "
    "ancak maç başlarken bilinir (tasarım §8.2)."
)
# Tasarım §13'ün 3, 4, 5 ve 9. maddeleri — bu raporun ölçmedikleri.
_NOT_MEASURED = (
    "- **2019/20 öncesi ana lig satırlarında saat yok**: gün içi sıralama o dönemde yaklaşık "
    "(tutucu kural).",
    "- **`AvgC`'nin kitap kümesi zamanla değişiyor** ve satır başına yayımlanmıyor: referans "
    "sezonlar arası sabit bir büyüklük değildir.",
    "- **Holdout'ta `PSC` kullanılamaz** (%23–55, bayat); `BFEC` yalnız 2024/25'ten.",
    "- **Bootstrap maçları bağımsız sayar**; aynı haftanın maçları arasındaki ortak şoklar "
    "aralıkları olduğundan dar gösterebilir.",
)


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def _interval(interval: Interval | None) -> str:
    if interval is None:
        return "—"
    return f"{interval.estimate:.4f} [{interval.low:.4f}, {interval.high:.4f}]"


def _window_text(window: Window) -> str:
    start = "—" if window.start is None else window.start.isoformat()
    return f"[{start}, {window.end.isoformat()})"


def _score_lines(scores: Mapping[str, float]) -> list[str]:
    chosen = best_method(scores)
    lines = [
        "## Vig yöntemleri (K2)",
        "",
        "Havuzlanmış kapanış (`AvgC`) log loss'u, her yöntemin çözebildiği ortak maçlarda.",
        "",
        "| Yöntem | Log loss |",
        "|---|---|",
        *(f"| {method} | {score:.5f} |" for method, score in scores.items()),
        "",
        f"Seçilen yöntem: **{chosen}** (lig tablosu bununla) · `DEFAULT_METHOD`: {DEFAULT_METHOD}",
    ]
    if chosen != DEFAULT_METHOD:
        lines.append(f"UYARI: ölçüm `{chosen}` seçti; `DEFAULT_METHOD` Task 12'de güncellenmeli.")
    return [*lines, ""]


def _league_line(row: LeagueEfficiency) -> str:
    ou25_slope = None if row.ou25_calibration is None else row.ou25_calibration.slope
    cells = (
        row.code,
        row.league_id,
        row.kind,
        str(row.n),
        _interval(row.margin),
        _interval(row.log_loss),
        _number(row.brier),
        _number(row.rps),
        _interval(row.slope),
        _number(row.calibration.intercept),
        _number(row.calibration.ece),
        _interval(row.late_info),
        _interval(row.value_rate),
        _interval(row.sharp_gap),
        _interval(row.exchange_gap),
        _interval(row.ou25_margin),
        _interval(row.ou25_log_loss),
        _number(ou25_slope),
    )
    return "| " + " | ".join(cells) + " |"


def _unmeasured_line(league: HistoryLeague) -> str:
    # Ölçülemeyen lig tablodan DÜŞMEZ: N = 0 ve her ölçüt "—" (kısmî kayıp sessiz geçmez).
    metrics = _HEADER.count("|") - 1 - 4
    return (
        "| "
        + " | ".join((league.code, league.league_id, league.kind, "0", *("—",) * metrics))
        + " |"
    )


def _ranking_lines(ranking: Ranking) -> list[str]:
    def listed(codes: tuple[str, ...]) -> list[str]:
        numbered = [
            f"{place}. {code} — kademe {ranking.tiers[code]}" for place, code in enumerate(codes, 1)
        ]
        return numbered or ["(lig yok)"]

    return [
        "## Sıralamalar",
        "",
        "Bileşik puan yok (tasarım §8.3). Kademe: aralığın alt ucu medyanın üstündeyse A, üst ucu "
        "altındaysa C, yoksa B; ligin kademesi iki sıralamadaki iyisidir.",
        "",
        "### R1 — geç bilgi (ΔLL, ana ligler, büyükten küçüğe)",
        "",
        *listed(ranking.late_info),
        "",
        "### R2 — kapanış kalibrasyon hatası (|b − 1|, eşitlikte ECE)",
        "",
        *listed(ranking.miscalibration),
        "",
    ]


def render_report(
    rows: Sequence[LeagueEfficiency],
    ranking: Ranking,
    *,
    scores: Mapping[str, float],
    candidates: Sequence[str],
    generated_at: datetime,
    unmeasured: Sequence[HistoryLeague] = (),
) -> str:
    """Markdown rapor: yöntem puanları, lig tablosu, iki sıralama, adaylar, ölçülmeyenler.

    `unmeasured`: AvgC 1X2'si tam maçı olmayan ligler (`NoClosingPrices`) — satırları "—" ile.
    """
    lines = [
        "# Piyasa verimliliği — geliştirme dönemi",
        "",
        f"Üretildi: {generated_at.isoformat()} · Pencere: ana ligler {_window_text(MAIN_WINDOW)}, "
        f"ek ligler {_window_text(EXTRA_WINDOW)} · holdout satırı okunmadı (doluluk kilitten).",
        "",
        "Aralıklar %95 yüzdelik bootstrap (maç düzeyinde, sabit tohum). Yalnız toplu sayılar.",
        "",
        *_score_lines(scores),
        "## Lig başına ölçütler",
        "",
        _HEADER,
        "|" + "---|" * (_HEADER.count("|") - 1),
        *(_league_line(row) for row in rows),
        *(_unmeasured_line(league) for league in unmeasured),
        "",
        _VALUE_NOTE,
        "",
        *_ranking_lines(ranking),
        "## Aday ligler",
        "",
        "Ölçüt (tasarım §8.4): geliştirme N ≥ 1000 · holdout `AvgC` doluluğu ≥ %95 (kilitten) · "
        "The Odds API anahtarı var · R1 ya da R2'de A veya B kademesi.",
        "",
        *([f"- {code}" for code in candidates] or ["Aday lig yok."]),
        "",
        "## Raporun ölçmedikleri",
        "",
        *_NOT_MEASURED,
    ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_efficiency.py -q`
Expected: PASS (34 passed)

- [ ] **Step 5: Başarısız testleri yaz — CLI**
`tests/test_market_cli.py` — tam içerik:
```python
"""`python -m football_edge.market`: `efficiency` (önce kilit, sonra ölçüm) ve `bridge` (§8, §9)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge import collect
from football_edge.collect import EXIT_SOURCE_FAILED
from football_edge.collector import ContractViolation
from football_edge.history.catalog import Catalog
from football_edge.history.holdout import DEV, POST, HoldoutKey, select_periods
from football_edge.history.lock import HistoryLock, build_lock, dump_lock, load_lock, verify_lock
from football_edge.history.types import CLOSING, H2H, HistMatch
from football_edge.market import __main__ as market_main
from football_edge.market import efficiency
from football_edge.market.bridge import LiveClosing
from tests.efficiency_samples import BASE, EXTRA_LEAGUE, MAIN_LEAGUE, rich, synthetic
from tests.market_factory import hist_match

CATALOG = Catalog(current_season="2627", leagues=(MAIN_LEAGUE, EXTRA_LEAGUE))
History = Mapping[str, tuple[HistMatch, ...]]


class _Connection:
    """`with connect() as conn:` için en küçük bağlantı: CLI onu yalnız `load_matches`e verir."""

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _history() -> History:
    # Önbellekteki bütün dönemler: holdout satırları kilidin özetine girer, ölçüme hiç girmez.
    holdout = synthetic(8, start=date(2025, 8, 2), season="2526", first=200)
    extra = synthetic(56, league="X1", season="2023")
    return {"M1": (*rich(BASE), *rich(holdout)), "X1": extra}


def _wire(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, history: History, locked: History
) -> tuple[Path, list[Any]]:
    """Veritabanı, katalog ve günlük kurulumu sahte; kilit GERÇEK kilit koduyla dosyaya yazılır.

    Sahte `load_matches` Task 6'nın sözleşmesini (R96) izler: `lock` verilirse önce BÜTÜN satırlar
    üzerinde GERÇEK `verify_lock`, sonra yalnız DEV + POST döner (holdout anahtarsız çıkmaz).
    """
    calls: list[Any] = []
    connection = _Connection()

    def load(
        conn: object,
        catalog: Catalog,
        *,
        lock: HistoryLock | None = None,
        key: HoldoutKey | None = None,
    ) -> History:
        assert conn is connection and catalog is CATALOG and key is None
        calls.append(("load_matches", lock))
        if lock is not None:
            verify_lock(lock, history)
        periods = frozenset({DEV, POST})
        return {code: select_periods(rows, periods=periods) for code, rows in history.items()}

    monkeypatch.setattr(market_main, "configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(market_main, "connect", lambda: connection)
    monkeypatch.setattr(market_main, "load_catalog", lambda path: calls.append(path) or CATALOG)
    monkeypatch.setattr(market_main, "load_matches", load)
    lock_path = tmp_path / "history_lock.yaml"
    lock = build_lock(locked, locked_at=date(2026, 9, 29))
    lock_path.write_text(dump_lock(lock), encoding="utf-8")
    return lock_path, calls


def test_efficiency_writes_the_report_and_logs_a_one_line_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    history = _history()
    lock_path, calls = _wire(monkeypatch, tmp_path, history, history)
    seen: list[int] = []
    real = efficiency.league_efficiency

    def spy(league: Any, matches: Any, *, method: str, resamples: int) -> Any:
        seen.append(resamples)
        return real(league, matches, method=method, resamples=resamples)

    monkeypatch.setattr(market_main, "league_efficiency", spy)
    out = tmp_path / "reports" / "piyasa-verimliligi.md"
    caplog.set_level(logging.INFO, logger="football_edge.market")

    code = market_main.main(
        ["efficiency", "--out", str(out), "--lock", str(lock_path), "--catalog", "katalog.yaml"]
        + ["--resamples", "25"]
    )

    assert code == 0
    # kilit ayrı bir verify_lock çağrısıyla değil load_matches'in içinde doğrulanır (R96)
    assert calls == ["logging", Path("katalog.yaml"), ("load_matches", load_lock(lock_path))]
    assert seen == [25, 25]
    text = out.read_text(encoding="utf-8")
    assert "| M1 | m.1 | main | 56 |" in text  # sekiz holdout satırı N'ye girmedi
    assert "## Raporun ölçmedikleri" in text
    summary = [
        record.getMessage() for record in caplog.records if record.name == "football_edge.market"
    ]
    assert len(summary) == 1
    assert summary[0].startswith("verimlilik: 2 lig · yöntem=")
    assert str(out) in summary[0]


@pytest.mark.leakage
def test_efficiency_verifies_the_lock_before_computing_anything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    history = _history()
    stale = {**history, "M1": history["M1"][1:]}  # kilit bir satır eksik veriyle kurulmuş
    lock_path, _ = _wire(monkeypatch, tmp_path, history, stale)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("kilit doğrulanmadan ölçüm yapıldı")

    monkeypatch.setattr(market_main, "method_scores", forbidden)
    monkeypatch.setattr(market_main, "league_efficiency", forbidden)
    out = tmp_path / "rapor.md"

    code = market_main.main(["efficiency", "--out", str(out), "--lock", str(lock_path)])

    assert code == market_main.EXIT_LOCK_VIOLATION == 9
    assert not out.exists()
    assert "kilit doğrulanamadı" in caplog.text


@pytest.mark.leakage
@pytest.mark.parametrize("damage", ("yaml", "version"), ids=("bozuk-yaml", "surum-uyusmazligi"))
def test_a_corrupted_lock_file_exits_nine_before_the_cache_is_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, damage: str
) -> None:
    # R99: load_lock YAMALANMAZ — diske gerçekten bozuk bir kilit yazılır, gerçek okuyucu reddeder.
    history = _history()
    lock_path, calls = _wire(monkeypatch, tmp_path, history, history)
    if damage == "yaml":
        lock_path.write_text("canonical_version: 1\nleagues: [\n", encoding="utf-8")
    else:
        stale = replace(build_lock(history, locked_at=date(2026, 9, 29)), canonical_version=2)
        lock_path.write_text(dump_lock(stale), encoding="utf-8")
    out = tmp_path / "rapor.md"

    code = market_main.main(["efficiency", "--out", str(out), "--lock", str(lock_path)])

    assert code == market_main.EXIT_LOCK_VIOLATION
    assert not out.exists()
    assert [call for call in calls if isinstance(call, tuple)] == []  # önbellek hiç okunmadı


def test_efficiency_names_and_keeps_a_league_it_cannot_measure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # m9: AvgC 1X2'si tam maçı olmayan tek lig raporu düşürmez; satırı "—", logda adıyla anılır.
    bare = synthetic(56, league="X1", season="2023")
    history = {**_history(), "X1": tuple(replace(m, odds=MappingProxyType({})) for m in bare)}
    lock_path, _ = _wire(monkeypatch, tmp_path, history, history)
    out = tmp_path / "rapor.md"
    arguments = ["efficiency", "--out", str(out), "--lock", str(lock_path), "--resamples", "20"]

    code = market_main.main(arguments)

    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "| M1 | m.1 | main | 56 |" in text
    assert "| X1 | x.1 | extra | 0 | — |" in text
    assert "lig=X1 ölçülemedi" in caplog.text


def test_efficiency_stops_when_the_cache_breaks_its_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    history = _history()
    lock_path, _ = _wire(monkeypatch, tmp_path, history, history)

    def broken(conn: object, catalog: Catalog, **options: object) -> History:
        raise ContractViolation("football-data: önbellekte 3 dosya yok")

    monkeypatch.setattr(market_main, "load_matches", broken)
    out = tmp_path / "rapor.md"

    code = market_main.main(["efficiency", "--out", str(out), "--lock", str(lock_path)])

    assert code == EXIT_SOURCE_FAILED
    assert not out.exists()
    assert "önbellekte 3 dosya yok" in caplog.text


def test_efficiency_defaults_point_at_the_repository_config() -> None:
    args = market_main._parser().parse_args(["efficiency", "--out", "rapor.md"])
    assert args.lock == Path("config/history_lock.yaml")
    assert args.catalog == Path("config/history_leagues.yaml")
    assert args.resamples == 2000


def test_efficiency_requires_an_output_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(market_main, "configure_logging", lambda: None)
    with pytest.raises(SystemExit) as caught:
        market_main.main(["efficiency"])
    assert caught.value.code == 2


def test_market_exit_codes_do_not_collide_with_collect() -> None:
    taken = {value for name, value in vars(collect).items() if name.startswith("EXIT_")}
    ours = {market_main.EXIT_LOCK_VIOLATION, market_main.EXIT_NO_PAIRS}
    assert (market_main.EXIT_LOCK_VIOLATION, market_main.EXIT_NO_PAIRS) == (9, 10)
    assert not ours & (taken | {0, 1})


# ── bridge ───────────────────────────────────────────────────────────────────────────────────


def _live(match_id: str, home: str) -> LiveClosing:
    kickoff = datetime(2026, 9, 19, 14, 0, tzinfo=UTC)
    return LiveClosing(match_id, "m.1", kickoff, home, "Beta City", (2.0, 4.0, 4.0), 3)


def _post(home: str) -> HistMatch:
    """Sonrası dönemi (≥ 2026-07-01) tarihli sentetik football-data satırı."""
    avgc = {("Avg", H2H, CLOSING): (2.5, 10 / 3, 10 / 3)}
    return hist_match(league="M1", season="2627", day=date(2026, 9, 19), home=home, prices=avgc)


def _wire_bridge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, live: tuple[LiveClosing, ...]
) -> tuple[Path, list[Any]]:
    """Veritabanı sahte; takma ad dosyası gerçek: 'Delta Rovers United' → 'Delta Rov'.

    Dönen liste `load_catalog`un yolunu ve `load_live_closings`in `since`ini sırayla tutar.
    """
    connection = _Connection()
    seen: list[Any] = []

    def closings(conn: object, *, since: datetime) -> tuple[LiveClosing, ...]:
        assert conn is connection
        seen.append(since)
        return live

    history = {"M1": (_post("Alpha Town"), _post("Delta Rov")), "X1": ()}
    monkeypatch.setattr(market_main, "configure_logging", lambda: None)
    monkeypatch.setattr(market_main, "connect", lambda: connection)
    monkeypatch.setattr(market_main, "load_catalog", lambda path: seen.append(path) or CATALOG)
    monkeypatch.setattr(market_main, "load_matches", lambda conn, catalog: history)
    monkeypatch.setattr(market_main, "load_live_closings", closings)
    aliases = tmp_path / "history_aliases.yaml"
    aliases.write_text("aliases:\n  Delta Rovers United: Delta Rov\n", encoding="utf-8")
    return aliases, seen


def test_bridge_writes_the_report_with_the_days_n(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    live = (_live("m1", "Alpha Town"), _live("m2", "Delta Rovers United"), _live("m3", "Nobody"))
    aliases, seen = _wire_bridge(monkeypatch, tmp_path, live)
    out = tmp_path / "reports" / "kopru.md"
    caplog.set_level(logging.INFO, logger="football_edge.market")

    code = market_main.main(["bridge", "--out", str(out), "--aliases", str(aliases)])

    assert code == 0
    # varsayılanlar: depo kataloğu ve sonrası döneminin başı
    assert seen == [Path("config/history_leagues.yaml"), datetime(2026, 7, 1, tzinfo=UTC)]
    text = out.read_text(encoding="utf-8")
    assert "Karşılaştırılan maç (N): 2" in text  # takma adla eşlenen dahil
    assert "Karşılaştırılamayan canlı maç: 1" in text
    assert "Yöntem: shin" in text
    assert "Alpha Town" not in text
    summary = [
        record.getMessage() for record in caplog.records if record.name == "football_edge.market"
    ]
    assert summary == [f"köprü: n=2 · karşılaştırılamayan=1 · yöntem=shin · rapor={out}"]


def test_bridge_honours_catalog_since_and_method(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    aliases, seen = _wire_bridge(monkeypatch, tmp_path, (_live("m1", "Alpha Town"),))
    out = tmp_path / "kopru.md"
    arguments = ["bridge", "--out", str(out), "--aliases", str(aliases), "--catalog", "k.yaml"]

    code = market_main.main([*arguments, "--since", "2026-09-01", "--method", "multiplicative"])

    assert code == 0
    assert seen == [Path("k.yaml"), datetime(2026, 9, 1, tzinfo=UTC)]
    text = out.read_text(encoding="utf-8")
    assert "Yöntem: multiplicative" in text
    assert "2026-09-01 ve sonrasında" in text


def test_bridge_stops_when_the_cache_breaks_its_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    aliases, _ = _wire_bridge(monkeypatch, tmp_path, (_live("m1", "Alpha Town"),))

    def broken(conn: object, catalog: Catalog, **options: object) -> History:
        raise ContractViolation("football-data: önbellekte 3 dosya yok")

    monkeypatch.setattr(market_main, "load_matches", broken)
    out = tmp_path / "kopru.md"

    code = market_main.main(["bridge", "--out", str(out), "--aliases", str(aliases)])

    assert code == EXIT_SOURCE_FAILED
    assert not out.exists()


def test_bridge_without_comparable_pairs_writes_nothing_and_says_why(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    aliases, _ = _wire_bridge(monkeypatch, tmp_path, (_live("m3", "Nobody"),))
    out = tmp_path / "kopru.md"

    code = market_main.main(["bridge", "--out", str(out), "--aliases", str(aliases)])

    assert code == market_main.EXIT_NO_PAIRS
    assert not out.exists()
    assert "karşılaştırılabilir eşleşme yok" in caplog.text


def test_bridge_defaults_point_at_the_repository_config() -> None:
    args = market_main._parser().parse_args(["bridge", "--out", "kopru.md"])
    assert args.since == date(2026, 7, 1)
    assert args.catalog == Path("config/history_leagues.yaml")
    assert args.aliases == Path("config/history_aliases.yaml")
    assert args.method == "shin"
```

- [ ] **Step 6: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_market_cli.py -q`
Expected: FAIL — `ImportError: cannot import name '__main__' from 'football_edge.market'`

- [ ] **Step 7: En küçük uygulamayı yaz — `__main__.py`**

`efficiency`de kilit `load_matches(..., lock=lock)` içinde HER ölçümden önce doğrulanır (R96; ayrı
`verify_lock` çağrısı yok); bozuk kilit dosyasının `LockViolation`ı (R99) da aynı `try`da yakalanır.
Çıkış kodları `history` CLI'ıyla aynıdır (kilit 9, kullanılamaz önbellek 7). Tek lig ölçülemezse
(m9) rapor düşmez: lig adıyla loglanır, tabloda satırı "—" ile kalır. Ölçüm yöntemi `method_scores`un en düşüğüdür (tasarım §6:
"varsayılan yöntem ölçümle seçilir"); rapor `DEFAULT_METHOD`la uyuşmazlığı yazar, sabiti Task 12
değiştirir. `bridge` (R91) kilide bakmaz — yalnız kilitsiz "sonrası" dönemini okur; `--since`
UTC gece yarısıdır; N = 0 iken aralık tanımsızdır, rapor yazılmaz ve çıkış 10 olur (çoğu kez eksik
takma ad — Task 8 Step 12).
`src/football_edge/market/__main__.py` — tam içerik:
```python
"""Piyasa CLI'ı: `efficiency` (tasarım §8) ve `bridge` (tasarım §9) raporları.

`efficiency`de kilit HER ölçümden önce doğrulanır (`load_matches(..., lock=lock)`, R96): kilit
dosyası bozuksa ya da satırlar kilitli özetlere uymuyorsa tek bir ölçüt hesaplanmaz, rapor yazılmaz.
`bridge` yalnız kilitsiz "sonrası" dönemine bakar (`load_matches` DEV + POST, `pair` POST süzer).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time
from pathlib import Path

from football_edge.collect import EXIT_SOURCE_FAILED, configure_logging
from football_edge.collector import ContractViolation
from football_edge.db import connect
from football_edge.history.catalog import Catalog, HistoryLeague, load_catalog
from football_edge.history.holdout import HOLDOUT_END
from football_edge.history.lock import LockViolation, load_lock
from football_edge.history.sync import load_matches
from football_edge.history.types import HistMatch
from football_edge.market.bridge import (
    compare,
    load_aliases,
    load_live_closings,
    pair,
    render_bridge_report,
)
from football_edge.market.devig import DEFAULT_METHOD, METHODS
from football_edge.market.efficiency import (
    RESAMPLES,
    LeagueEfficiency,
    NoClosingPrices,
    best_method,
    candidates,
    league_efficiency,
    method_scores,
    rank,
    render_report,
)

LOGGER = logging.getLogger("football_edge.market")
LOCK_PATH = Path("config/history_lock.yaml")
CATALOG_PATH = Path("config/history_leagues.yaml")
ALIASES_PATH = Path("config/history_aliases.yaml")
# Kilitli dönemin bir satırı değişti ya da kayboldu: `history` CLI'ıyla aynı kod; `collect`in 2–8'i
# ve 0/1 dışında.
EXIT_LOCK_VIOLATION = 9
# Köprü: karşılaştırılabilir tek eşleşme yok (N = 0 → aralık tanımsız). Rapor yazılmaz; çoğu kez
# takma ad eksiktir (Task 8 Step 12).
EXIT_NO_PAIRS = 10


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.market")
    commands = parser.add_subparsers(dest="command", required=True)
    efficiency = commands.add_parser("efficiency", help="piyasa verimliliği raporu (geliştirme)")
    efficiency.add_argument("--out", type=Path, required=True, help="yazılacak markdown rapor")
    efficiency.add_argument("--lock", type=Path, default=LOCK_PATH)
    efficiency.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    efficiency.add_argument("--resamples", type=int, default=RESAMPLES)
    bridge = commands.add_parser("bridge", help="tarihsel ↔ canlı kapanış köprüsü raporu")
    bridge.add_argument("--out", type=Path, required=True, help="yazılacak markdown rapor")
    bridge.add_argument(
        "--since",
        type=date.fromisoformat,
        default=HOLDOUT_END,
        help="bu tarihten (UTC gece yarısı) sonra başlayan canlı maçlar; varsayılan: sonrası",
    )
    bridge.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    bridge.add_argument("--aliases", type=Path, default=ALIASES_PATH)
    bridge.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
    return parser


def _measure(
    catalog: Catalog,
    matches_by_league: Mapping[str, tuple[HistMatch, ...]],
    *,
    method: str,
    resamples: int,
) -> tuple[tuple[LeagueEfficiency, ...], tuple[HistoryLeague, ...]]:
    """Ölçülen satırlar ve ölçülemeyen ligler; biri raporun tamamını düşürmez (adıyla anılır)."""
    rows: list[LeagueEfficiency] = []
    unmeasured: list[HistoryLeague] = []
    for league in catalog.leagues:
        try:
            rows.append(
                league_efficiency(
                    league,
                    matches_by_league.get(league.code, ()),
                    method=method,
                    resamples=resamples,
                )
            )
        except NoClosingPrices as missing:
            LOGGER.warning("lig=%s ölçülemedi — %s", league.code, missing)
            unmeasured.append(league)
    return tuple(rows), tuple(unmeasured)


def _efficiency(args: argparse.Namespace, now: datetime) -> int:
    catalog = load_catalog(args.catalog)
    try:
        lock = load_lock(args.lock)
        with connect() as conn:
            matches_by_league = load_matches(conn, catalog, lock=lock)
    except LockViolation as violation:
        LOGGER.error("kilit doğrulanamadı — hiçbir ölçüt hesaplanmadı: %s", violation)
        return EXIT_LOCK_VIOLATION
    except ContractViolation as violation:
        # Eksik ya da sözleşmeyi geçmeyen önbellekle ölçülmez (history CLI'ıyla aynı kod).
        LOGGER.error("önbellek kullanılamaz — rapor üretilmedi: %s", violation)
        return EXIT_SOURCE_FAILED
    pooled = [match for matches in matches_by_league.values() for match in matches]
    scores = method_scores(pooled)
    method = best_method(scores)
    rows, unmeasured = _measure(catalog, matches_by_league, method=method, resamples=args.resamples)
    ranking = rank(rows)
    chosen = candidates(rows, ranking, lock=lock, leagues=catalog.leagues)
    report = render_report(
        rows, ranking, scores=scores, candidates=chosen, generated_at=now, unmeasured=unmeasured
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    LOGGER.info(
        "verimlilik: %d lig · yöntem=%s · aday=%s · ölçülemeyen=%s · rapor=%s",
        len(rows),
        method,
        ",".join(chosen) or "yok",
        ",".join(league.code for league in unmeasured) or "yok",
        args.out,
    )
    return 0


def _bridge(args: argparse.Namespace, now: datetime) -> int:
    catalog = load_catalog(args.catalog)
    aliases = load_aliases(args.aliases)
    since = datetime.combine(args.since, time.min, tzinfo=UTC)
    try:
        with connect() as conn:
            matches_by_league = load_matches(conn, catalog)
            live = load_live_closings(conn, since=since)
    except ContractViolation as violation:
        LOGGER.error("önbellek kullanılamaz — köprü raporu üretilmedi: %s", violation)
        return EXIT_SOURCE_FAILED
    codes = {league.league_id: league.code for league in catalog.leagues}
    hist = [match for matches in matches_by_league.values() for match in matches]
    pairing = pair(live, hist, aliases=aliases, codes_by_league_id=codes)
    try:
        report = compare(pairing, method=args.method)
    except ValueError as empty:
        LOGGER.error("köprü: %s — %d canlı kapanış, rapor yazılmadı", empty, len(live))
        return EXIT_NO_PAIRS
    text = render_bridge_report(report, generated_at=now, since=args.since)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    LOGGER.info(
        "köprü: n=%d · karşılaştırılamayan=%d · yöntem=%s · rapor=%s",
        report.n,
        report.unmatched,
        report.method,
        args.out,
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    args = _parser().parse_args(argv)
    now = datetime.now(UTC)
    if args.command == "bridge":
        return _bridge(args, now)
    return _efficiency(args, now)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_market_cli.py -q`
Expected: PASS (14 passed)
Run: `uv run pytest tests/test_efficiency.py tests/test_market_cli.py -q -m leakage`
Expected: `7 passed, 41 deselected`
Run: `uv run mypy src scripts && uv run ruff check src tests && uv run ruff format --check src tests`
Expected: `Success: no issues found …` · `All checks passed!` · `… files already formatted`

- [ ] **Step 9: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır)
| # | Mutasyon (dosya:ne değişir) | Kırmızı olması gereken test |
|---|---|---|
| 1 | `efficiency.py:_development_rows` — `select_periods(…DEV…)` → `tuple(matches)` (yalnız pencere kalır) | `test_holdout_and_post_matches_never_reach_any_metric` |
| 2 | `efficiency.py:_development_rows` — `in_window` modülün adıyla değil `holdout`tan çağrılır (yama etkisiz; I1) | `test_holdout_and_post_matches_never_reach_any_metric` (koruma satırı) |
| 3 | `efficiency.py:_development_rows` — pencere uygulanmaz (`return tuple(development)`) | `test_main_window_drops_development_matches_before_2019_20_but_extra_keeps_them` |
| 4 | `efficiency.py:_window` — ek lig de `MAIN_WINDOW` alır | `test_main_window_drops_development_matches_before_2019_20_but_extra_keeps_them` |
| 5 | `efficiency.py:league_efficiency` — `n=len(close.matches)` → `n=len(rows)` | `test_n_counts_only_matches_with_a_complete_closing_1x2` |
| 6 | `efficiency.py:league_efficiency` — `main = league.kind == MAIN` → `main = True` | `test_extra_leagues_have_no_late_info_value_rate_or_totals` |
| 7 | `efficiency.py:_slope_interval` — yeniden fit yerine `slopes.append(estimate)` | `test_slope_interval_refits_the_calibration_on_resampled_matches` |
| 8 | `efficiency.py:league_efficiency` — eğim aralığına `resamples=RESAMPLES` | `test_slope_interval_refits_the_calibration_on_resampled_matches` |
| 9 | `efficiency.py:_late_info` — `early - late` → `late - early` | `test_late_info_is_pre_closing_minus_closing_log_loss_per_match` |
| 10 | `efficiency.py:_value_rate` — `> 1.0` → `>= 1.0` | `test_value_rate_counts_matches_where_a_best_price_beats_the_fair_closing_probability` |
| 11 | `efficiency.py:_value_rate` — `max(…) > 1.0` → `min(…) > 1.0` ("her sonuç"; I3) | `test_value_rate_counts_matches_where_a_best_price_beats_the_fair_closing_probability` |
| 12 | `efficiency.py:_sharp_gap` — `< SHARP_COVERAGE` → `<= SHARP_COVERAGE` | `test_sharp_gap_uses_only_seasons_where_avgc_and_psc_are_ninety_percent_complete` |
| 13 | `efficiency.py:_sharp_gap` — doluluk süzgeci yerine `if not both:` | `test_sharp_gap_uses_only_seasons_where_avgc_and_psc_are_ninety_percent_complete` |
| 14 | `efficiency.py:method_scores` — `select_periods(…DEV…)` yerine `matches` | `test_method_scores_ignore_matches_outside_the_development_period` |
| 15 | `efficiency.py:method_scores` — her yöntem kendi çözebildiği maçlarda (ortak küme yok) | `test_method_scores_compare_every_method_on_the_same_matches` |
| 16 | `efficiency.py:_tiers` — `interval.low > middle` → `>=` | `test_tiers_compare_interval_ends_with_the_median_estimate` |
| 17 | `efficiency.py:_tiers` — `interval.high < middle` → `<=` | `test_tiers_compare_interval_ends_with_the_median_estimate` |
| 18 | `efficiency.py:rank` — `min(tier, late_tiers.get(code, "C"))` → `max(tier, …get(code, "A"))` | `test_a_league_takes_the_better_of_its_two_tiers` |
| 19 | `efficiency.py:_distance` — 1'i içeren aralıkta uçların mutlak değerleri (alt uç 0 değil) | `test_miscalibration_tier_uses_the_distance_interval_of_the_slope` |
| 20 | `efficiency.py:_distance` — `slope.high < 1` dalında `(slope.low - 1, slope.high - 1)` | `test_miscalibration_tier_uses_the_distance_interval_of_the_slope` |
| 21 | `efficiency.py:rank` — ECE eşitlik bozucusu `-ece[code]` → `ece[code]` | `test_rank_orders_miscalibration_by_slope_distance_then_ece` |
| 22 | `efficiency.py:candidates` — `row.n >= MIN_MATCHES` → `>` | `test_a_league_at_every_boundary_is_a_candidate` |
| 23 | `efficiency.py:candidates` — holdout doluluğu `>= MIN_HOLDOUT_COVERAGE` → `>` | `test_a_league_at_every_boundary_is_a_candidate` |
| 24 | `efficiency.py:candidates` — kademe `in ("A", "B", "C")` | `test_candidates_need_enough_matches_an_api_key_and_tier_a_or_b[kademe-c]` |
| 25 | `efficiency.py:_holdout_coverage` — `periods[HOLDOUT]` → `periods[DEV]` | `test_holdout_coverage_comes_from_the_lock_digest[yuzde-94]` |
| 26 | `efficiency.py:render_report` — `*_NOT_MEASURED,` satırı silinir | `test_report_has_every_section_and_only_aggregates` |
| 27 | `efficiency.py:render_report` — `_VALUE_NOTE,` satırı silinir | `test_report_has_every_section_and_only_aggregates` |
| 28 | `efficiency.py:_score_lines` — `if chosen != DEFAULT_METHOD:` → `if False:` | `test_report_names_the_selected_method_and_flags_a_default_it_did_not_choose` |
| 29 | `__main__.py:_efficiency` — `load_matches(conn, catalog, lock=lock)` → `load_matches(conn, catalog)` (R96) | `test_efficiency_verifies_the_lock_before_computing_anything` |
| 30 | `__main__.py:_efficiency` — `load_lock(args.lock)` `try` dışına alınır (bozuk kilit exit 1 olur; R99) | `test_a_corrupted_lock_file_exits_nine_before_the_cache_is_read` |
| 31 | `__main__.py` — `EXIT_LOCK_VIOLATION = 9` → `1` | `test_efficiency_verifies_the_lock_before_computing_anything` |
| 32 | `__main__.py:_efficiency` — `except ContractViolation` yerine `except KeyError` | `test_efficiency_stops_when_the_cache_breaks_its_contract` |
| 33 | `__main__.py:_efficiency` — `resamples=args.resamples` → `resamples=RESAMPLES` | `test_efficiency_writes_the_report_and_logs_a_one_line_summary` |
| 34 | `__main__.py:main` — `configure_logging()` silinir | `test_efficiency_writes_the_report_and_logs_a_one_line_summary` |
| 35 | `__main__.py:_efficiency` — `load_catalog(args.catalog)` → `load_catalog(CATALOG_PATH)` | `test_efficiency_writes_the_report_and_logs_a_one_line_summary` |
| 36 | `__main__.py:_efficiency` — `load_lock(args.lock)` → `load_lock(LOCK_PATH)` | `test_efficiency_writes_the_report_and_logs_a_one_line_summary` |
| 37 | `efficiency.py:league_efficiency` — `ou25_margin=ou25_margin` → `ou25_margin=margin` (1X2 marjı; R92) | `test_totals_metrics_use_the_closing_over_under_on_main_leagues` |
| 38 | `efficiency.py:_totals` — marj `overround(prices)` yerine `overround(probs)` (olasılıktan; R92) | `test_totals_metrics_use_the_closing_over_under_on_main_leagues` |
| 39 | `efficiency.py:league_efficiency` — `exchange_gap`te `book=EXCHANGE` → `book=SHARP` (R97) | `test_exchange_gap_uses_only_seasons_where_avgc_and_bfec_are_ninety_percent_complete` |
| 40 | `efficiency.py:league_efficiency` — `exchange_gap=None` (R97) | `test_exchange_gap_uses_only_seasons_where_avgc_and_bfec_are_ninety_percent_complete` |
| 41 | `efficiency.py:league_efficiency` — `NoClosingPrices` yerine düz `ValueError` (m9) | `test_a_league_without_closing_prices_is_a_named_error` |
| 42 | `__main__.py:_measure` — `except NoClosingPrices` → `except KeyError` (tek lig raporu düşürür; m9) | `test_efficiency_names_and_keeps_a_league_it_cannot_measure` |
| 43 | `efficiency.py:render_report` — `*(_unmeasured_line(…) for …)` satırı silinir (m9) | `test_a_league_that_could_not_be_measured_keeps_a_dash_row` |
| 44 | `efficiency.py:_unmeasured_line` — ölçüt sütunu sayısı `- 4` → `- 5` (m9) | `test_a_league_that_could_not_be_measured_keeps_a_dash_row` |
| 45 | `__main__.py:_bridge` — `datetime.combine(args.since, …)` → `datetime.combine(HOLDOUT_END, …)` | `test_bridge_honours_catalog_since_and_method` |
| 46 | `__main__.py:_bridge` — `load_catalog(args.catalog)` → `load_catalog(CATALOG_PATH)` | `test_bridge_honours_catalog_since_and_method` |
| 47 | `__main__.py:_bridge` — `compare(pairing, method=args.method)` → `method=DEFAULT_METHOD` | `test_bridge_honours_catalog_since_and_method` |
| 48 | `__main__.py:_bridge` — `pair(…, aliases=aliases, …)` → `aliases={}` | `test_bridge_writes_the_report_with_the_days_n` |
| 49 | `__main__.py:_bridge` — `codes = {league.league_id: league.code …}` ters (`code → league_id`) | `test_bridge_writes_the_report_with_the_days_n` |
| 50 | `__main__.py:main` — `if args.command == "bridge": return _bridge(…)` silinir | `test_bridge_writes_the_report_with_the_days_n` |
| 51 | `__main__.py:_bridge` — `except ContractViolation` yerine `except KeyError` | `test_bridge_stops_when_the_cache_breaks_its_contract` |
| 52 | `__main__.py:_bridge` — `except ValueError as empty:` yerine `except KeyError as empty:` | `test_bridge_without_comparable_pairs_writes_nothing_and_says_why` |
| 53 | `__main__.py` — `EXIT_NO_PAIRS = 10` → `9` | `test_market_exit_codes_do_not_collide_with_collect` |

- [ ] **Step 10: Commit**
```bash
git add src/football_edge/market/efficiency.py src/football_edge/market/__main__.py \
  tests/efficiency_samples.py tests/test_efficiency.py tests/test_market_cli.py
git commit -m "feat: lig başına piyasa verimliliği, iki sıralama, aday ligler; efficiency ve bridge CLI'ı (T4)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 11: Kapının tamamı**
Run: `TMPDIR=$(mktemp -d) ./verify.sh` — log DOSYASINDAN oku.
Expected: 10 adım PASS (Task 5'in `sızıntı` adımı dahil; bu görev ona 7 `leakage` testi ekler —
alt sınır birleştirmede controller'ca yeniden ölçülür) + `SKIP: zincir (DATABASE_URL yok)`.

---

### Task 10: Bütünleşik harness — değerlendirme, bilinen sonuçlar K1–K4 ve history.yml selftest adımı (T2b)

**Kademe:** K1 · **Dalga:** 3 · **Worktree/dal:** `.worktrees/wt-selftest` · `feat/faz2-selftest`

**Files:**
- Create: `src/football_edge/backtest/evaluate.py` — `Evaluation`, `evaluate`
- Create: `src/football_edge/backtest/selftest.py` — `Check`, K1–K4 ve K2/D1 raporları, `run_selftest`
- Create: `src/football_edge/backtest/__main__.py` — CLI `selftest`
- Modify: `.github/workflows/history.yml` — `Senkron` ile `Alarm aç` arasına `Bilinen sonuçlar` ADIMI
  (ikinci job DEĞİL); iki yorum güncellenir
- Modify: `tests/test_history_workflow.py` (Task 6) — bir import, `DATABASE_STEPS`e selftest adımının
  adı, dosya sonuna selftest bloğu
- Test: `tests/test_evaluate.py`, `tests/test_selftest.py`, `tests/test_backtest_cli.py`

Dokunulmaz: `tests/workflow_helpers.py` ve `tests/test_workflows.py` (tek-iş kuralı olduğu gibi kalır:
`_steps()` tek job varsayar), `history/*`, `market/*`, Task 4'ün `backtest/*` modülleri ve
`tests/backtest_builders.py` (yalnız kullanılır), ortak dosyalar.

**Interfaces:**
- Consumes:
  - Task 0 — `football_edge.history.types`: `HistMatch`, `OddsKey`, `PRE_CLOSING`, `CLOSING`, `H2H`,
    `RESULTS`.
  - Task 1 — `football_edge.history.catalog`: `MAIN`, `EXTRA`, `HistoryLeague(code, league_id, name,
    country, tier, kind, first_season, odds_api_key)`, `Catalog(current_season, leagues)`,
    `load_catalog(path: Path) -> Catalog`.
  - Task 2 — `football_edge.market.devig`: `devig(prices: Sequence[float], method: str) ->
    tuple[float, ...]`, `InvalidPrices(ValueError)`, `match_probs(match: HistMatch, *, book: str,
    market: str, phase: str, method: str) -> tuple[float, ...] | None`, `METHODS`, `MULTIPLICATIVE`,
    `POWER`, `SHIN`, `DEFAULT_METHOD`; `football_edge.market.metrics`: `Interval(estimate, low, high)`,
    `Calibration`, `per_match_log_loss(probs, outcomes) -> tuple[float, ...]`, `log_loss(probs,
    outcomes) -> float`, `brier`, `rps`, `calibration(probs, outcomes, *, bins=10) -> Calibration`,
    `clv(price: float, fair_probability: float) -> float`, `bootstrap_mean(values, *, resamples=2000,
    seed=20260922, level=0.95) -> Interval`, `outcome_index(match: HistMatch, market: str) -> int`.
  - Task 3 — `football_edge.history.holdout`: `DEV`, `MAIN_WINDOW`, `EXTRA_WINDOW`, `in_window(match,
    window) -> bool`, `select_periods(matches, *, periods: frozenset[str], key: HoldoutKey | None =
    None) -> tuple[HistMatch, ...]`, `HoldoutKey` (testte tip); `football_edge.history.lock`:
    `LockViolation(*differences)` (`.differences: tuple[str, ...]`), `HistoryLock`, `load_lock(path:
    Path) -> HistoryLock` (R99: bozuk YAML, eksik alan, sürüm uyuşmazlığı, 64-hex olmayan özet →
    `LockViolation`); testlerde gerçek kilit dosyası için `build_lock(matches_by_league, *,
    locked_at)` ve `dump_lock(lock) -> str`. `verify_lock`u bu görev ÇAĞIRMAZ (R96).
  - Task 4 — `harness.Bet`, `Outcome`, `Prediction`, `ReplayResult`, `ResultRecord`, `replay`;
    `strategies.Placebo(devig, seed=20260922, book="Avg")`; `strategies.EloPointInTime(config,
    draw_rate, groups, ratings)` (R94: `ratings` `(groups.get(lig, lig), takım)` anahtarlı);
    `timeline.decision_at`, `timeline.LONDON`; `tests/backtest_builders.py`: `hist_match`, `quote`.
  - Task 6 — `football_edge.history.sync.load_matches(conn, catalog, *, lock: HistoryLock | None =
    None, key: HoldoutKey | None = None) -> Mapping[str, tuple[HistMatch, ...]]` (R96: DEV + POST;
    `lock` verilirse ÖNCE bütün satırlarda `verify_lock` → `LockViolation`; HOLDOUT yalnız
    anahtarla); `football_edge.history.__main__.EXIT_LOCK_VIOLATION` (9);
    `.github/workflows/history.yml` (tek job `history`: checkout → `Secret taraması` → setup-uv →
    `uv sync --frozen` → `Senkron` → `Alarm aç` → `Alarm kapat`; `timeout-minutes: 60`);
    `tests/test_history_workflow.py`: `HISTORY`, `SYNC`, `FAKE_UV` (`$*`ı `$CALLS`a yazar,
    `${FAIL_CODE:-0}` ile döner), `_sync_index()`, `DATABASE_STEPS: tuple[str, ...] = ("Senkron",)`
    ve onu okuyan `test_only_the_database_steps_get_a_secret_and_only_the_database_one` (gövdesi
    değişmez: secret yalnız bu adlardaki adımlara, yalnız `DATABASE_URL`).
  - Task 8 — 0008 `history.yml`i `ops.dispatch_workflow` izinli listesine koydu: `tests/test_workflows.py`nin
    ALARMED testleri `[history.yml]` parametresiyle koşar (alarm son iki adım, yalnız kapatan adım
    `continue-on-error`).
  - Mevcut kod — `collect.configure_logging()`, `collect.EXIT_*` (2–8), `db.connect()`.
- Produces (sözleşme, birebir — plan başıyla aynı):
```python
# football_edge/backtest/evaluate.py
@dataclass(frozen=True)
class Evaluation:
    strategy: str; n: int; log_loss: Interval; brier: float; rps: float
    calibration: Calibration; clv: Interval | None; bets: int
def evaluate(result: ReplayResult, *, method: str, resamples: int = 2000) -> Evaluation
def clv_values(result: ReplayResult, *, method: str) -> tuple[float, ...]   # K4 bunu kullanır

# football_edge/backtest/selftest.py
@dataclass(frozen=True)
class Check:
    id: str; gate: bool; passed: bool; detail: str
def run_selftest(matches_by_league: Mapping[str, Sequence[HistMatch]], *, method: str,
                 main_codes: frozenset[str], resamples: int = 2000) -> tuple[Check, ...]
    # main_codes: katalogdaki MAIN liglerin kodları (K1'in 18/22 eşiği ve pencere seçimi için)
```
- Ek (sözleşme dışı): `__main__.rating_groups(catalog: Catalog) -> Mapping[str, str]` (R94: lig kodu →
  ülke, `MappingProxyType`), `evaluate.DEFAULT_RESAMPLES = 2000`, `evaluate.REFERENCE_BOOK = "Avg"`;
  `selftest.K1_MIN_POSITIVE = 18`, `K3_MIN_COVERAGE = 0.9`, `DRIFT_BUCKETS`; `__main__.EXIT_GATE_FAILED
  = 1`, `__main__.EXIT_LOCK_VIOLATION = 9`, `LOCK_PATH`, `CATALOG_PATH`, `main(argv: list[str] | None
  = None) -> int`.

**Bu görevin kararları (hepsini testler sabitler):**
- Her lig önce `select_periods(…, periods=frozenset({DEV}))`, sonra penceresi: ana lig `MAIN_WINDOW`,
  ek lig `EXTRA_WINDOW`. Holdout, sonrası ve pencere dışı satırlar hiçbir denetimi DEĞİŞTİRMEZ.
- **K1 (kapı):** ana ligler; kapanış öncesi `Avg` ve kapanış `AvgC` 1X2'si ikisi de tam (ve seçilen
  yöntem kabul ediyor) → maç başına LL(öncesi) − LL(kapanış). Havuzlanmış bootstrap `low > 0` VE
  ortalaması pozitif ana lig ≥ 18. Payda katalogdaki ana lig sayısı; verisi olmayan ana lig pozitif
  sayılmaz.
- **K2 (rapor):** bütün ligler kendi penceresinde, üç yöntemin de kabul ettiği `AvgC` 1X2 maçları;
  `passed = min(shin, power) < multiplicative`. `gate=False`.
- **K3 (kapı):** lig-sezon (ana `MAIN_WINDOW`, ek `EXTRA_WINDOW`) içinde `AvgC` ve `PSC` 1X2'nin
  birlikte tam olduğu satırların payı ≥ 0,9 (eşitlik dahil) olanlar; LL(AvgC) − LL(PSC) bootstrap
  `low > 0`.
- **K4 (kapı):** ana ligler penceresinde, lig koduna göre sıralı TEK havuz; `replay(havuz,
  Placebo(devig=partial(devig, method=method)))` → `clv_values` → `bootstrap_mean` → aralığın ÜST ucu
  < 0. Ortalama negatif ama aralık sıfıra değiyorsa KIRMIZI. Kapanışı eksik bahis CLV dışıdır ve
  sayısı yazılır. K4 `evaluate`i ÇAĞIRMAZ: kalibrasyon fiti ayrışan bir örneği haklı olarak reddeder
  (Task 2) ve CLV'yi ölçülemez kılardı — plan yazılırken sentetik veride tam olarak bu oldu.
- K4 ve D1 YALNIZ ana ligleri okur (`main`): kapanış öncesi `Avg` taşıyan bir ek lig bile K4'ün
  havuzuna ve D1'in kovalarına girmez (m7; ek liglerde kapanış öncesi fiyat yoktur — K1 gibi).
- **D1 (rapor):** karar → başlama süresi kovaları `[0,12) [12,36) [36,60) [60,96)` saat; kovada kapanış
  öncesi `Avg` ile kapanış `AvgC` adil olasılıkları arasındaki toplam değişim mesafesinin ortalaması;
  dolu kovalar boyunca azalmıyorsa geçer. `gate=False`.
- Ölçülemeyen denetim GEÇMEZ; detayı "`<id>` ölçülemedi: …" der. Boş bir tarih kapıyı yeşil yapamaz.
- Her `Check.detail` tek Türkçe satır: tahmin, %95 aralık, sayılar.
- `evaluate`: tahmin, KENDİ `match_index`inin sonucuyla eşlenir. CLV kapanış `AvgC`yi
  `Outcome.closing`ten okur (`match_probs` `HistMatch` ister, `ReplayResult` onu taşımaz — kural aynı:
  eksik ya da `InvalidPrices` → CLV dışı): bahsin fiyatı × bahsin SEÇTİĞİ sonucun adil kapanış
  olasılığı − 1 (maçın sonucu CLV'ye girmez).
- R94: Elo'nun reyting grupları katalogdan gelir — `rating_groups(catalog)` = `{lig kodu: ülke}`;
  Elo'yu kuran her yol `EloPointInTime(groups=rating_groups(catalog))` kullanır. Bu görevde Elo
  kuran yol YOK (selftest K1–K4'ü fiyatla ve Placebo'yla ölçer); CLI testi eşlemeyi ve Elo'ya
  verildiğinde aynı ülkenin liglerinin reytingi paylaştığını sınar.
- CLI: ilk iş `configure_logging()` (DSN içeren bir bağlantı hatası redakte loga düşsün); katalog →
  `load_lock` (R99: bozuk dosya `LockViolation`) → bağlan, `load_matches(conn, catalog, lock=lock)`
  (R96: kilidi bütün satırlarda doğrular, DEV + POST döner; CLI ayrıca `verify_lock` çağırmaz, anahtar
  vermez), bağlantıyı KAPAT → `run_selftest` (DEV'i kendisi seçer; POST düşer). Her `LockViolation`
  → 9, farklar tek log satırında (`"; ".join(error.differences)`), hiçbir denetim koşmaz. Kapı
  denetimi kırmızıysa 1; rapor denetimi çıkış kodunu etkilemez.
- `history.yml`: selftest bir ADIMDIR (`name: Bilinen sonuçlar`), `Senkron`dan sonra ve iki alarm
  adımından önce; `if:` taşımaz (örtük `success()`: kırmızı senkronun yarım bıraktığı önbellek
  ölçülmez); `DATABASE_URL` alır ve adı `DATABASE_STEPS`e girer; 0/1/9/diğer kodları `::error::`
  satırıyla adlandırır ve kodu yutmaz. `timeout-minutes: 60` değişmez (selftest'in süresi ÖLÇÜLMEDİ —
  ilk gerçek turun süresi HANDOFF'a yazılır). Selftest kilidi kendisi doğrular (exit 9): ayrı bir
  `lock --verify` adımı gerekmez.

- [ ] **Step 1: Değerlendirme testlerini yaz**

Create `tests/test_evaluate.py`:
```python
"""Değerlendirme: her tahmin kendi sonucuyla; CLV yalnız kapanışı tam bahislerde, AvgC'ye karşı."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from types import MappingProxyType

import pytest

from football_edge.backtest.evaluate import evaluate
from football_edge.backtest.harness import Bet, Outcome, Prediction, ReplayResult, replay
from football_edge.backtest.strategies import Placebo
from football_edge.history.types import CLOSING, PRE_CLOSING, RESULTS, OddsKey
from football_edge.market.devig import MULTIPLICATIVE, SHIN, devig
from football_edge.market.metrics import (
    bootstrap_mean,
    brier,
    calibration,
    per_match_log_loss,
    rps,
)
from tests.backtest_builders import hist_match, quote

SCORES = {"H": (1, 0), "D": (1, 1), "A": (0, 1)}
AVG_CLOSE = quote("Avg", CLOSING, (2.0, 3.4, 4.2))
FAVOURITE = (0.6, 0.25, 0.15)
OUTSIDER = (0.2, 0.3, 0.5)
OPEN = (0.45, 0.35, 0.2)
ROWS: tuple[tuple[tuple[float, float, float], str], ...] = (
    (FAVOURITE, "H"),
    (FAVOURITE, "H"),
    (FAVOURITE, "D"),
    (FAVOURITE, "H"),
    (OUTSIDER, "A"),
    (OUTSIDER, "D"),
    (OUTSIDER, "A"),
    (OUTSIDER, "H"),
    (OPEN, "D"),
    (OPEN, "H"),
    (OPEN, "D"),
    (OPEN, "A"),
)


def _replay(
    bets: Mapping[int, Bet] | None = None,
    closings: Mapping[int, Mapping[OddsKey, float]] | None = None,
) -> ReplayResult:
    """Harness'sız sonuç: maç sırası tahmin sırası değil, sonuçlar ters sırayla eklenir."""
    bets = bets or {}
    closings = closings or {}
    indices = [10 + 3 * position for position in range(len(ROWS))]
    predictions = tuple(
        Prediction(index, "test", probs, bets.get(position))
        for position, (index, (probs, _)) in enumerate(zip(indices, ROWS, strict=True))
    )
    outcomes = {
        index: Outcome(
            match_index=index,
            result=result,
            home_goals=SCORES[result][0],
            away_goals=SCORES[result][1],
            closing=MappingProxyType(dict(closings.get(position, AVG_CLOSE))),
        )
        for position, (index, (_, result)) in reversed(
            list(enumerate(zip(indices, ROWS, strict=True)))
        )
    }
    return ReplayResult(
        strategy="test",
        predictions=predictions,
        outcomes=MappingProxyType(outcomes),
        no_decision=0,
        no_prediction=0,
    )


def test_evaluate_scores_each_prediction_against_its_own_outcome() -> None:
    evaluation = evaluate(_replay(), method=MULTIPLICATIVE, resamples=500)

    probs = [probs for probs, _ in ROWS]
    outcomes = [RESULTS.index(result) for _, result in ROWS]
    losses = [-math.log(p[o]) for p, o in zip(probs, outcomes, strict=True)]
    assert (evaluation.strategy, evaluation.n) == ("test", 12)
    assert evaluation.log_loss == bootstrap_mean(per_match_log_loss(probs, outcomes), resamples=500)
    assert evaluation.log_loss.low <= sum(losses) / len(losses) <= evaluation.log_loss.high
    assert evaluation.brier == pytest.approx(brier(probs, outcomes))
    assert evaluation.rps == pytest.approx(rps(probs, outcomes))
    assert evaluation.calibration == calibration(probs, outcomes)
    assert (evaluation.clv, evaluation.bets) == (None, 0)


def test_clv_prices_the_bet_against_the_devigged_avg_closing_of_the_bet_outcome() -> None:
    closing = {**AVG_CLOSE, **quote("PS", CLOSING, (1.8, 3.9, 4.8))}

    evaluation = evaluate(
        _replay(bets={0: Bet("D", 3.6, "Avg")}, closings={0: closing}),
        method=MULTIPLICATIVE,
        resamples=500,
    )

    fair_draw = (1 / 3.4) / (1 / 2.0 + 1 / 3.4 + 1 / 4.2)
    assert evaluation.bets == 1
    assert evaluation.clv is not None
    assert evaluation.clv.estimate == pytest.approx(3.6 * fair_draw - 1)


def test_clv_follows_the_requested_devig_method() -> None:
    result = _replay(bets={0: Bet("D", 3.6, "Avg")})

    shin = evaluate(result, method=SHIN, resamples=500)
    multiplicative = evaluate(result, method=MULTIPLICATIVE, resamples=500)

    assert shin.clv is not None and multiplicative.clv is not None
    assert shin.clv.estimate == pytest.approx(3.6 * devig((2.0, 3.4, 4.2), SHIN)[1] - 1)
    assert shin.clv.estimate != pytest.approx(multiplicative.clv.estimate)


def test_bets_without_a_complete_avg_closing_stay_out_of_clv() -> None:
    no_draw = {key: price for key, price in AVG_CLOSE.items() if key.outcome != "D"}
    result = _replay(
        bets={0: Bet("H", 2.2, "Avg"), 1: Bet("H", 2.2, "Avg"), 2: Bet("A", 4.4, "Avg")},
        closings={1: {**no_draw, **quote("PS", CLOSING, (1.9, 3.5, 4.4))}, 2: {}},
    )

    evaluation = evaluate(result, method=MULTIPLICATIVE, resamples=500)

    fair_home = (1 / 2.0) / (1 / 2.0 + 1 / 3.4 + 1 / 4.2)
    assert (evaluation.n, evaluation.bets) == (12, 1)
    assert evaluation.clv is not None
    assert evaluation.clv.estimate == pytest.approx(2.2 * fair_home - 1)


@pytest.mark.parametrize(
    ("method", "bets"),
    [(SHIN, 0), (MULTIPLICATIVE, 1)],
    ids=["shin-refuses", "multiplicative-accepts"],
)
def test_closing_prices_the_method_refuses_stay_out_of_clv(method: str, bets: int) -> None:
    thin = quote("Avg", CLOSING, (2.5, 3.6, 3.6))  # Σ 1/o < 1: Shin için geçersiz

    evaluation = evaluate(
        _replay(bets={0: Bet("H", 2.6, "Avg")}, closings={0: thin}), method=method, resamples=500
    )

    assert evaluation.bets == bets
    assert (evaluation.clv is None) is (bets == 0)


def test_an_empty_replay_cannot_be_evaluated() -> None:
    empty = ReplayResult(
        strategy="test",
        predictions=(),
        outcomes=MappingProxyType({}),
        no_decision=0,
        no_prediction=0,
    )

    with pytest.raises(ValueError, match="tahmin yok"):
        evaluate(empty, method=MULTIPLICATIVE)


def test_evaluate_reads_a_placebo_replay_end_to_end() -> None:
    days = [date(2023, 8, 5) + timedelta(weeks=week) for week in range(9)]
    prices: Sequence[float] = (2.6, 3.3, 2.8)
    matches = tuple(
        hist_match(
            day=day,
            kickoff=datetime.combine(day, time(14), tzinfo=UTC),
            goals=SCORES[RESULTS[week % 3]],
            odds={
                **quote("Avg", PRE_CLOSING, prices),
                **({} if week == 4 else quote("Avg", CLOSING, prices)),
            },
            line=week + 1,
        )
        for week, day in enumerate(days)
    )

    result = replay(matches, Placebo(devig=partial(devig, method=MULTIPLICATIVE)))
    evaluation = evaluate(result, method=MULTIPLICATIVE, resamples=500)

    assert (evaluation.n, evaluation.bets) == (9, 8)
    assert evaluation.clv is not None
    assert evaluation.clv.estimate == pytest.approx(1 / sum(1 / price for price in prices) - 1)
```

- [ ] **Step 2: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_evaluate.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.backtest.evaluate'`

- [ ] **Step 3: Değerlendirmeyi yaz**

Create `src/football_edge/backtest/evaluate.py`:
```python
"""Yeniden oynatmanın değerlendirmesi (tasarım §7.5): isabet, kalibrasyon, CLV.

Kapanış YALNIZ burada, bütün tahminler dondurulduktan sonra `ReplayResult.outcomes`tan okunur.
CLV'nin referansı vig'i temizlenmiş kapanış `AvgC`'dir (D3); kapanışı tam olmayan bahis CLV'ye
girmez, sayısı `bets` ile bahisli tahmin sayısının farkıdır.
"""

from __future__ import annotations

from dataclasses import dataclass

from football_edge.backtest.harness import Outcome, ReplayResult
from football_edge.history.types import CLOSING, H2H, RESULTS, OddsKey
from football_edge.market.devig import InvalidPrices, devig
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

REFERENCE_BOOK = "Avg"
DEFAULT_RESAMPLES = 2000


@dataclass(frozen=True)
class Evaluation:
    strategy: str
    n: int
    log_loss: Interval
    brier: float
    rps: float
    calibration: Calibration
    clv: Interval | None
    bets: int


def _closing_probs(outcome: Outcome, method: str) -> tuple[float, ...] | None:
    """Kapanış `AvgC` 1X2'sinin adil olasılığı; eksik ya da reddedilen fiyatta None."""
    keys = [
        OddsKey(book=REFERENCE_BOOK, market=H2H, outcome=name, phase=CLOSING) for name in RESULTS
    ]
    if not all(key in outcome.closing for key in keys):
        return None
    try:
        return devig([outcome.closing[key] for key in keys], method)
    except InvalidPrices:
        return None


def clv_values(result: ReplayResult, *, method: str) -> tuple[float, ...]:
    """Bahisli ve kapanışı tam tahminlerin CLV'si, tahmin sırasıyla (K4 de bunu kullanır)."""
    values: list[float] = []
    for prediction in result.predictions:
        if prediction.bet is None:
            continue
        fair = _closing_probs(result.outcomes[prediction.match_index], method)
        if fair is not None:
            values.append(clv(prediction.bet.price, fair[RESULTS.index(prediction.bet.outcome)]))
    return tuple(values)


def evaluate(
    result: ReplayResult, *, method: str, resamples: int = DEFAULT_RESAMPLES
) -> Evaluation:
    """Her tahmini KENDİ maçının sonucuyla ölçer; bahislerin CLV'si kapanışı tam olanlarda."""
    if not result.predictions:
        raise ValueError(f"{result.strategy}: değerlendirilecek tahmin yok")
    probs = [prediction.probs for prediction in result.predictions]
    outcomes = [
        RESULTS.index(result.outcomes[prediction.match_index].result)
        for prediction in result.predictions
    ]
    values = clv_values(result, method=method)
    return Evaluation(
        strategy=result.strategy,
        n=len(probs),
        log_loss=bootstrap_mean(per_match_log_loss(probs, outcomes), resamples=resamples),
        brier=brier(probs, outcomes),
        rps=rps(probs, outcomes),
        calibration=calibration(probs, outcomes),
        clv=bootstrap_mean(values, resamples=resamples) if values else None,
        bets=len(values),
    )
```

- [ ] **Step 4: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_evaluate.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: Bilinen sonuç testlerini yaz**

Veri elle kurulur (gerçek takım/oran yok). Kapanış sonuca doğru kısalırsa (`TOWARD`) K1 geçer, kapanış
öncesiyle yer değiştirirse düşer; `PSC` daha keskin kısalırsa (`SHARPER`) K3 geçer; Placebo'nun
seçeceği taraf kapanışa doğru kısalırsa — gelecek fiyat sızıntısının ta kendisi — K4 düşer. Placebo'nun
seçimi Task 4'ün formülüyle testte yeniden hesaplanır (`_placebo_pick`).

Create `tests/test_selftest.py`:
```python
"""Bilinen sonuçlar K1–K4 (+ K2, D1 rapor): her denetim sentetik veride geçer ve kırmızı verebilir.

Veri elle kurulur: kapanış sonuca doğru kısalırsa K1 geçer, fiyatlar yer değiştirirse düşer;
Placebo'nun seçtiği tarafın fiyatı kapanışa doğru kısalırsa (gelecek fiyat sızıntısı) K4 düşer.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from functools import partial

import pytest

from football_edge.backtest import selftest
from football_edge.backtest.selftest import Check, run_selftest
from football_edge.backtest.strategies import Placebo
from football_edge.backtest.timeline import LONDON
from football_edge.history.holdout import DEV, HoldoutKey
from football_edge.history.types import CLOSING, PRE_CLOSING, RESULTS, HistMatch, OddsKey
from football_edge.market.devig import METHODS, MULTIPLICATIVE, devig
from tests.backtest_builders import hist_match, quote

RESAMPLES = 500
MAIN_LEAGUES = (
    "B1", "D1", "D2", "E0", "E1", "E2", "E3", "EC", "F1", "F2", "G1",
    "I1", "I2", "N1", "P1", "SC0", "SC1", "SC2", "SC3", "SP1", "SP2", "T1",
)  # fmt: skip
MAIN_CODES = frozenset(MAIN_LEAGUES)
Prices = tuple[float, float, float]
PRE: Prices = (2.6, 3.3, 2.8)
# Kapanış sonuca doğru kısalır (bilgi kapanışa kadar geldi) — ve keskin kitapta daha çok.
TOWARD: Mapping[str, Prices] = {"H": (1.9, 3.6, 4.2), "D": (3.2, 2.6, 3.2), "A": (4.2, 3.6, 1.9)}
SHARPER: Mapping[str, Prices] = {"H": (1.6, 4.3, 6.0), "D": (3.6, 2.1, 3.6), "A": (6.0, 4.3, 1.6)}
SLIGHT: Mapping[str, Prices] = {
    "H": (2.5, 3.3, 2.9),
    "D": (2.65, 3.2, 2.85),
    "A": (2.7, 3.3, 2.7),
}
WRONG = {"H": "A", "D": "H", "A": "D"}
SCORES = {"H": (1, 0), "D": (1, 1), "A": (0, 1)}
FAVOURITE_CLOSE: Prices = (1.5, 4.2, 6.5)
DRIFT: tuple[Prices, ...] = ((2.55, 3.3, 2.85), (2.4, 3.4, 3.0), (2.2, 3.5, 3.3), (1.9, 3.7, 4.0))
DRIFT_HOURS = {8: 0, 12: 1, 27: 1, 36: 2, 52: 2, 60: 3, 80: 3}  # karar→başlama saati: kova
PLACEBO_SEED = Placebo(devig=partial(devig, method=MULTIPLICATIVE)).seed


def _results(count: int) -> tuple[str, ...]:
    return tuple(RESULTS[index % 3] for index in range(count))


def _saturdays(count: int, first: date) -> tuple[datetime, ...]:
    """Ardışık cumartesiler 14:00 UTC: kararı cuma 12:00 Londra olan hafta sonu maçları."""
    return tuple(
        datetime.combine(first + timedelta(weeks=week), time(14), tzinfo=UTC)
        for week in range(count)
    )


def _match(
    league: str,
    kickoff: datetime,
    result: str,
    *,
    pre: Prices | None = None,
    close: Prices | None = None,
    sharp: Prices | None = None,
    season: str = "2324",
    line: int = 1,
) -> HistMatch:
    odds: dict[OddsKey, float] = {}
    if pre is not None:
        odds |= quote("Avg", PRE_CLOSING, pre)
    if close is not None:
        odds |= quote("Avg", CLOSING, close)
    if sharp is not None:
        odds |= quote("PS", CLOSING, sharp)
    return hist_match(
        day=kickoff.astimezone(LONDON).date(),
        kickoff=kickoff,
        league=league,
        season=season,
        home=f"{league} ev",
        away=f"{league} konuk",
        goals=SCORES[result],
        odds=odds,
        line=line,
    )


def _run(history: Mapping[str, Sequence[HistMatch]]) -> dict[str, Check]:
    checks = run_selftest(
        history, method=MULTIPLICATIVE, main_codes=MAIN_CODES, resamples=RESAMPLES
    )
    return {check.id: check for check in checks}


def _k1_league(
    code: str,
    *,
    swapped: bool = False,
    count: int = 6,
    first: date = date(2023, 8, 5),
    close_to: Mapping[str, Prices] = TOWARD,
) -> tuple[HistMatch, ...]:
    """Kapanış sonuca doğru kısalır; `swapped` iken kapanış öncesiyle yer değiştirir."""
    return tuple(
        _match(
            code,
            kickoff,
            result,
            pre=close_to[result] if swapped else PRE,
            close=PRE if swapped else close_to[result],
            line=index + 1,
        )
        for index, (kickoff, result) in enumerate(
            zip(_saturdays(count, first), _results(count), strict=True)
        )
    )


def _k1_history(good: int = len(MAIN_LEAGUES)) -> dict[str, tuple[HistMatch, ...]]:
    return {
        code: _k1_league(code, swapped=index >= good) for index, code in enumerate(MAIN_LEAGUES)
    }


def test_k1_passes_when_the_closing_beats_the_pre_closing_price_in_every_main_league() -> None:
    k1 = _run(_k1_history())["K1"]

    assert (k1.gate, k1.passed) == (True, True)
    assert "n=132" in k1.detail and "22/22" in k1.detail
    assert "\n" not in k1.detail


def test_k1_fails_when_the_pre_closing_and_closing_prices_are_swapped() -> None:
    k1 = _run(_k1_history(good=0))["K1"]

    assert (k1.gate, k1.passed) == (True, False)
    assert "0/22" in k1.detail


@pytest.mark.parametrize(("good", "passed"), [(18, True), (17, False)], ids=["18", "17"])
def test_k1_needs_eighteen_main_leagues_with_a_positive_gap(good: int, passed: bool) -> None:
    k1 = _run(_k1_history(good=good))["K1"]

    assert k1.passed is passed
    assert f"{good}/22" in k1.detail


def test_k1_fails_when_the_pooled_gap_is_not_above_zero_despite_eighteen_positive_leagues() -> None:
    history = {code: _k1_league(code, close_to=SLIGHT) for code in MAIN_LEAGUES[:18]}
    history |= {code: _k1_league(code, swapped=True, count=30) for code in MAIN_LEAGUES[18:]}

    k1 = _run(history)["K1"]

    assert "18/22" in k1.detail
    assert k1.passed is False


def test_k1_counts_every_main_league_of_the_catalog_even_without_data() -> None:
    k1 = _run({code: _k1_league(code) for code in MAIN_LEAGUES[:18]})["K1"]

    assert k1.passed is True
    assert "18/22" in k1.detail


def test_an_empty_history_turns_every_gate_check_red_without_crashing() -> None:
    checks = run_selftest({}, method=MULTIPLICATIVE, main_codes=MAIN_CODES, resamples=RESAMPLES)

    assert [(check.id, check.gate) for check in checks] == [
        ("K1", True),
        ("K2", False),
        ("K3", True),
        ("K4", True),
        ("D1", False),
    ]
    assert all(not check.passed and "ölçülemedi" in check.detail for check in checks)


@pytest.mark.leakage
def test_selftest_asks_select_periods_for_the_development_period_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[frozenset[str], HoldoutKey | None]] = []
    real = selftest.select_periods

    def spy(
        matches: Sequence[HistMatch], *, periods: frozenset[str], key: HoldoutKey | None = None
    ) -> tuple[HistMatch, ...]:
        asked.append((periods, key))
        return real(matches, periods=periods, key=key)

    monkeypatch.setattr(selftest, "select_periods", spy)

    _run(_k1_history())

    assert asked == [(frozenset({DEV}), None)] * len(MAIN_LEAGUES)


@pytest.mark.leakage
def test_holdout_and_later_rows_cannot_move_any_check() -> None:
    clean = _k1_history()
    later = {
        code: matches
        + _k1_league(code, swapped=True, count=12, first=date(2025, 8, 2))
        + _k1_league(code, swapped=True, count=6, first=date(2026, 8, 1))
        for code, matches in clean.items()
    }

    assert _run(later) == _run(clean)


@pytest.mark.leakage
def test_main_leagues_are_measured_only_inside_the_main_window() -> None:
    clean = _k1_history()
    early = {
        code: _k1_league(code, swapped=True, count=12, first=date(2018, 8, 4)) + matches
        for code, matches in clean.items()
    }

    assert _run(early) == _run(clean)


def _k2_history(results: str) -> dict[str, tuple[HistMatch, ...]]:
    """Ek lig (pencere EXTRA_WINDOW); kapanış belirgin bir favori gösterir."""
    kickoffs = _saturdays(len(results), date(2023, 4, 15))
    return {
        "BRA": tuple(
            _match("BRA", kickoff, result, close=FAVOURITE_CLOSE, season="2023", line=index + 1)
            for index, (kickoff, result) in enumerate(zip(kickoffs, results, strict=True))
        )
    }


def test_k2_prefers_shin_or_power_when_favourites_win_more_than_multiplicative_implies() -> None:
    k2 = _run(_k2_history("HHHHHHHHDA"))["K2"]

    assert (k2.gate, k2.passed) == (False, True)
    assert "n=10" in k2.detail
    assert all(method in k2.detail for method in METHODS)


def test_k2_is_reported_not_gated_when_multiplicative_wins() -> None:
    k2 = _run(_k2_history("HHDDDAAAAA"))["K2"]

    assert (k2.gate, k2.passed) == (False, False)


def _k3_rows(
    code: str,
    season: str,
    first: date,
    *,
    count: int = 10,
    with_sharp: int = 10,
    swapped: bool = False,
    sharp_to: Mapping[str, str] | None = None,
) -> tuple[HistMatch, ...]:
    """AvgC sonuca doğru, PSC daha keskin kısalır (`swapped`: tersi). İlk `with_sharp` satırda PSC
    var; `sharp_to` PSC'yi yanlış sonuca yöneltir."""
    rows = []
    for index, (kickoff, result) in enumerate(
        zip(_saturdays(count, first), _results(count), strict=True)
    ):
        average, sharp = TOWARD[result], SHARPER[result if sharp_to is None else sharp_to[result]]
        if swapped:
            average, sharp = sharp, average
        rows.append(
            _match(
                code,
                kickoff,
                result,
                close=average,
                sharp=sharp if index < with_sharp else None,
                season=season,
                line=index + 1,
            )
        )
    return tuple(rows)


def test_k3_passes_when_the_sharp_closing_beats_the_average_closing() -> None:
    history = {
        "E0": _k3_rows("E0", "2324", date(2023, 8, 5)),
        "BRA": _k3_rows("BRA", "2023", date(2023, 4, 15)),
    }

    k3 = _run(history)["K3"]

    assert (k3.gate, k3.passed) == (True, True)
    assert "lig-sezon 2/2" in k3.detail and "n=20" in k3.detail


def test_k3_fails_when_the_average_closing_is_sharper_than_the_sharp_book() -> None:
    k3 = _run({"E0": _k3_rows("E0", "2324", date(2023, 8, 5), swapped=True)})["K3"]

    assert (k3.gate, k3.passed) == (True, False)


@pytest.mark.parametrize(
    ("with_sharp", "passed"), [(9, False), (8, True)], ids=["ninety-kept", "eighty-dropped"]
)
def test_k3_keeps_only_league_seasons_where_both_closings_cover_ninety_percent(
    with_sharp: int, passed: bool
) -> None:
    history = {
        "E0": _k3_rows("E0", "2223", date(2022, 8, 6), with_sharp=with_sharp, sharp_to=WRONG)
        + _k3_rows("E0", "2324", date(2023, 8, 5))
    }

    k3 = _run(history)["K3"]

    assert k3.passed is passed
    assert f"lig-sezon {1 if passed else 2}/2" in k3.detail


@pytest.mark.leakage
def test_k3_measures_main_leagues_only_inside_the_main_window() -> None:
    history = {
        "E0": _k3_rows("E0", "1819", date(2018, 8, 4), count=30, swapped=True)
        + _k3_rows("E0", "2324", date(2023, 8, 5))
    }

    k3 = _run(history)["K3"]

    assert k3.passed is True
    assert "lig-sezon 1/1" in k3.detail


def _placebo_pick(index: int) -> str:
    """Placebo'nun havuzdaki `index`. maç için seçeceği sonuç (Task 4: maç başına tohum)."""
    return random.Random(PLACEBO_SEED * 1_000_003 + index).choice(RESULTS)


def _close_for(pick: str, target: float) -> Prices:
    """Çarpımsal vig temizliğinde `pick`in adil kapanış olasılığı (1 + target) / o_pre olur."""
    fair = (1.0 + target) / PRE[RESULTS.index(pick)]
    rest = (1.0 - fair) / 2
    home, draw, away = (1.0 / ((fair if name == pick else rest) * 1.05) for name in RESULTS)
    return home, draw, away


def _k4_history(
    close_of: Callable[[int, str], Prices | None], count: int = 30
) -> dict[str, tuple[HistMatch, ...]]:
    """Tek ana lig: havuzdaki sıra = listedeki sıra, `close_of(sıra, Placebo'nun seçimi)`."""
    kickoffs = _saturdays(count, date(2023, 8, 5))
    return {
        "E0": tuple(
            _match(
                "E0",
                kickoff,
                result,
                pre=PRE,
                close=close_of(index, _placebo_pick(index)),
                line=index + 1,
            )
            for index, (kickoff, result) in enumerate(zip(kickoffs, _results(count), strict=True))
        )
    }


@pytest.mark.leakage
def test_k4_passes_when_the_placebo_bets_into_prices_that_never_move() -> None:
    k4 = _run(_k4_history(lambda index, pick: PRE))["K4"]

    assert (k4.gate, k4.passed) == (True, True)
    assert "bahis=30" in k4.detail and "kapanışı eksik 0" in k4.detail


@pytest.mark.leakage
def test_k4_fails_when_the_placebo_always_picks_the_side_whose_price_shortened() -> None:
    k4 = _run(_k4_history(lambda index, pick: TOWARD[pick]))["K4"]

    assert (k4.gate, k4.passed) == (True, False)


@pytest.mark.leakage
def test_k4_fails_when_the_clv_interval_reaches_zero_despite_a_negative_mean() -> None:
    history = _k4_history(lambda index, pick: _close_for(pick, 0.2 if index % 2 == 0 else -0.25))

    k4 = _run(history)["K4"]

    found = re.search(r"CLV \(AvgC kapanışına karşı\) (\S+) \[%95 (\S+), (\S+)\]", k4.detail)
    assert found is not None, k4.detail
    estimate, _, high = (float(number) for number in found.groups())
    assert estimate < 0 < high, k4.detail
    assert k4.passed is False


def test_k4_leaves_bets_without_a_complete_closing_out_and_counts_them() -> None:
    k4 = _run(_k4_history(lambda index, pick: None if index < 3 else PRE))["K4"]

    assert k4.passed is True
    assert "bahis=27" in k4.detail and "kapanışı eksik 3" in k4.detail


def test_k4_is_red_when_the_placebo_cannot_bet() -> None:
    kickoffs = _saturdays(6, date(2023, 8, 5))
    k4 = _run({"E0": tuple(_match("E0", kickoff, "H", close=PRE) for kickoff in kickoffs)})["K4"]

    assert k4.passed is False
    assert "ölçülemedi" in k4.detail


def _d1_history(drift: Sequence[Prices], league: str = "E0") -> dict[str, tuple[HistMatch, ...]]:
    """Beş hafta; her hafta cuma 12:00 BST kararından 8–80 saat sonra başlayan yedi maç."""
    friday = datetime(2023, 8, 4, 11, tzinfo=UTC)
    slots = [(week, hours) for week in range(5) for hours in DRIFT_HOURS]
    return {
        league: tuple(
            _match(
                league,
                friday + timedelta(weeks=week, hours=hours),
                result,
                pre=PRE,
                close=drift[DRIFT_HOURS[hours]],
                line=index + 1,
            )
            for index, ((week, hours), result) in enumerate(
                zip(slots, _results(len(slots)), strict=True)
            )
        )
    }


@pytest.mark.leakage
def test_d1_passes_when_price_drift_grows_with_the_time_from_decision_to_kickoff() -> None:
    d1 = _run(_d1_history(DRIFT))["D1"]

    assert (d1.gate, d1.passed) == (False, True)
    assert re.search(r"\[0,12\) sa [0-9.]+ \(n=5\)", d1.detail), d1.detail
    for label in ("12,36", "36,60", "60,96"):
        assert re.search(rf"\[{label}\) sa [0-9.]+ \(n=10\)", d1.detail), d1.detail


@pytest.mark.leakage
def test_d1_fails_when_price_drift_shrinks_with_the_time_to_kickoff() -> None:
    d1 = _run(_d1_history(tuple(reversed(DRIFT))))["D1"]

    assert (d1.gate, d1.passed) == (False, False)


def test_k4_and_d1_measure_only_the_main_leagues() -> None:
    """Kapanış öncesi `Avg` fiyatı taşıyan bir EK lig K4'ün havuzuna ve D1'in kovalarına girmez."""
    main = _d1_history(DRIFT)
    extra = _d1_history(tuple(reversed(DRIFT)), league="BRA")

    clean, mixed = _run(main), _run({**main, **extra})

    assert "bahis=35" in mixed["K4"].detail
    assert (mixed["K4"], mixed["D1"]) == (clean["K4"], clean["D1"])
```

- [ ] **Step 6: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_selftest.py -q`
Expected: FAIL — `ImportError: cannot import name 'selftest' from 'football_edge.backtest'`

- [ ] **Step 7: Bilinen sonuçları yaz**

Create `src/football_edge/backtest/selftest.py`:
```python
"""Bilinen sonuçlar (tasarım §11, D13): harness ve vig hattı literatürün yönsel sonuçlarını üretir.

Yalnız geliştirme dönemi okunur: önce `select_periods` (DEV), sonra lig türünün penceresi (ana:
`MAIN_WINDOW`, ek: `EXTRA_WINDOW`). Kapı: K1, K3, K4. Rapor: K2 (vig yöntemi seçimi) ve D1 (karar
anı kuralının dolaylı sınaması, tasarım §4.5). Ölçülemeyen denetim GEÇMEZ — "ölçülemedi" yazar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from itertools import pairwise

from football_edge.backtest.evaluate import DEFAULT_RESAMPLES, clv_values
from football_edge.backtest.harness import replay
from football_edge.backtest.strategies import Placebo
from football_edge.backtest.timeline import decision_at
from football_edge.history.holdout import DEV, EXTRA_WINDOW, MAIN_WINDOW, in_window, select_periods
from football_edge.history.types import CLOSING, H2H, PRE_CLOSING, HistMatch
from football_edge.market.devig import METHODS, MULTIPLICATIVE, POWER, SHIN, devig, match_probs
from football_edge.market.metrics import (
    Interval,
    bootstrap_mean,
    log_loss,
    outcome_index,
    per_match_log_loss,
)

K1_MIN_POSITIVE = 18
K3_MIN_COVERAGE = 0.9
DRIFT_BUCKETS: tuple[tuple[float, float], ...] = ((0, 12), (12, 36), (36, 60), (60, 96))
REFERENCE_BOOK = "Avg"
SHARP_BOOK = "PS"

Quote = tuple[str, str]  # (kitap, evre)
Leagues = Mapping[str, Sequence[HistMatch]]
PRE_AVG: Quote = (REFERENCE_BOOK, PRE_CLOSING)
CLOSE_AVG: Quote = (REFERENCE_BOOK, CLOSING)
CLOSE_SHARP: Quote = (SHARP_BOOK, CLOSING)


@dataclass(frozen=True)
class Check:
    id: str
    gate: bool
    passed: bool
    detail: str


def _unmeasured(check_id: str, *, gate: bool, reason: str) -> Check:
    return Check(id=check_id, gate=gate, passed=False, detail=f"{check_id} ölçülemedi: {reason}")


def _interval(interval: Interval) -> str:
    return f"{interval.estimate:.4f} [%95 {interval.low:.4f}, {interval.high:.4f}]"


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _all(leagues: Leagues) -> tuple[HistMatch, ...]:
    return tuple(match for code in sorted(leagues) for match in leagues[code])


def _probs(match: HistMatch, quote: Quote, method: str) -> tuple[float, ...] | None:
    book, phase = quote
    return match_probs(match, book=book, market=H2H, phase=phase, method=method)


def _gaps(
    matches: Sequence[HistMatch], first: Quote, second: Quote, method: str
) -> tuple[float, ...]:
    """İki fiyat kümesi de tam olan maçlarda maç başına LL(first) − LL(second)."""
    firsts: list[tuple[float, ...]] = []
    seconds: list[tuple[float, ...]] = []
    outcomes: list[int] = []
    for match in matches:
        a, b = _probs(match, first, method), _probs(match, second, method)
        if a is None or b is None:
            continue
        firsts.append(a)
        seconds.append(b)
        outcomes.append(outcome_index(match, H2H))
    if not outcomes:
        return ()
    first_ll = per_match_log_loss(firsts, outcomes)
    second_ll = per_match_log_loss(seconds, outcomes)
    return tuple(x - y for x, y in zip(first_ll, second_ll, strict=True))


def _k1(main: Leagues, *, method: str, main_codes: frozenset[str], resamples: int) -> Check:
    gaps = {code: _gaps(main.get(code, ()), PRE_AVG, CLOSE_AVG, method) for code in main_codes}
    pooled = [gap for code in sorted(gaps) for gap in gaps[code]]
    if not pooled:
        return _unmeasured(
            "K1", gate=True, reason="kapanış öncesi Avg ve kapanış AvgC 1X2'si birlikte tam maç yok"
        )
    interval = bootstrap_mean(pooled, resamples=resamples)
    positive = sum(1 for values in gaps.values() if values and _mean(values) > 0)
    detail = (
        f"ΔLL = LL(kapanış öncesi Avg) − LL(kapanış AvgC) {_interval(interval)} n={len(pooled)}; "
        f"ΔLL > 0 olan ana lig {positive}/{len(main_codes)} (eşik {K1_MIN_POSITIVE})"
    )
    passed = interval.low > 0 and positive >= K1_MIN_POSITIVE
    return Check(id="K1", gate=True, passed=passed, detail=detail)


def _all_methods(match: HistMatch) -> dict[str, tuple[float, ...]] | None:
    probs = {method: _probs(match, CLOSE_AVG, method) for method in METHODS}
    complete = {method: value for method, value in probs.items() if value is not None}
    return complete if len(complete) == len(METHODS) else None


def _k2(windowed: Leagues) -> Check:
    by_method: dict[str, list[tuple[float, ...]]] = {method: [] for method in METHODS}
    outcomes: list[int] = []
    for match in _all(windowed):
        probs = _all_methods(match)
        if probs is None:
            continue
        outcomes.append(outcome_index(match, H2H))
        for method in METHODS:
            by_method[method].append(probs[method])
    if not outcomes:
        return _unmeasured("K2", gate=False, reason="kapanış AvgC 1X2'si tam maç yok")
    scores = {method: log_loss(by_method[method], outcomes) for method in METHODS}
    listed = " · ".join(f"{method} {scores[method]:.5f}" for method in METHODS)
    passed = min(scores[SHIN], scores[POWER]) < scores[MULTIPLICATIVE]
    detail = f"kapanış AvgC havuzlanmış log loss n={len(outcomes)}: {listed}"
    return Check(id="K2", gate=False, passed=passed, detail=detail)


def _both_closings(match: HistMatch) -> bool:
    return all(
        match.prices(book, H2H, CLOSING) is not None for book in (REFERENCE_BOOK, SHARP_BOOK)
    )


def _league_seasons(windowed: Leagues) -> dict[tuple[str, str], list[HistMatch]]:
    groups: dict[tuple[str, str], list[HistMatch]] = {}
    for code in sorted(windowed):
        for match in windowed[code]:
            groups.setdefault((code, match.season), []).append(match)
    return groups


def _k3(windowed: Leagues, *, method: str, resamples: int) -> Check:
    seasons = _league_seasons(windowed)
    kept = [
        matches
        for matches in seasons.values()
        if sum(map(_both_closings, matches)) / len(matches) >= K3_MIN_COVERAGE
    ]
    gaps = [gap for matches in kept for gap in _gaps(matches, CLOSE_AVG, CLOSE_SHARP, method)]
    if not gaps:
        return _unmeasured(
            "K3", gate=True, reason="AvgC ve PSC 1X2'sinin birlikte %90 dolu olduğu lig-sezon yok"
        )
    interval = bootstrap_mean(gaps, resamples=resamples)
    detail = (
        f"ΔLL = LL(AvgC) − LL(PSC) {_interval(interval)} n={len(gaps)}; lig-sezon "
        f"{len(kept)}/{len(seasons)} (AvgC ve PSC birlikte ≥ %90 dolu)"
    )
    return Check(id="K3", gate=True, passed=interval.low > 0, detail=detail)


def _k4(main: Leagues, *, method: str, resamples: int) -> Check:
    # Yalnız CLV: kalibrasyon fiti (evaluate) ayrışan küçük örnekte haklı olarak reddeder ve K4'ü
    # ölçemez kılardı; K4'ün sorusu bahsin kapanışa göre değeridir.
    result = replay(_all(main), Placebo(devig=partial(devig, method=method)))
    counts = f"karar yok {result.no_decision}, tahmin yok {result.no_prediction}"
    bets = sum(1 for prediction in result.predictions if prediction.bet is not None)
    values = clv_values(result, method=method)
    if not values:
        return _unmeasured(
            "K4", gate=True, reason=f"kapanışı tam bahis yok ({bets} bahis; {counts})"
        )
    interval = bootstrap_mean(values, resamples=resamples)
    detail = (
        f"Placebo CLV (AvgC kapanışına karşı) {_interval(interval)} bahis={len(values)}; "
        f"kapanışı eksik {bets - len(values)}; {counts}"
    )
    return Check(id="K4", gate=True, passed=interval.high < 0, detail=detail)


def _drift(match: HistMatch, method: str) -> tuple[float, float] | None:
    """(karar → başlama saati, kapanış öncesi ile kapanış olasılıkları arasındaki TV mesafesi)."""
    if match.kickoff is None:
        return None
    decided = decision_at(match.date, match.kickoff)
    pre, close = _probs(match, PRE_AVG, method), _probs(match, CLOSE_AVG, method)
    if decided is None or pre is None or close is None:
        return None
    hours = (match.kickoff - decided).total_seconds() / 3600
    return hours, 0.5 * sum(abs(a - b) for a, b in zip(pre, close, strict=True))


def _d1(main: Leagues, *, method: str) -> Check:
    drifts = [drift for drift in (_drift(match, method) for match in _all(main)) if drift]
    parts: list[str] = []
    means: list[float] = []
    for low, high in DRIFT_BUCKETS:
        values = [distance for hours, distance in drifts if low <= hours < high]
        label = f"[{low},{high}) sa"
        if not values:
            parts.append(f"{label} —")
            continue
        means.append(_mean(values))
        parts.append(f"{label} {means[-1]:.4f} (n={len(values)})")
    if len(means) < 2:
        return _unmeasured("D1", gate=False, reason="en az iki süre kovasında maç yok")
    rising = all(a <= b for a, b in pairwise(means))
    detail = (
        "karar→başlama süresine göre ortalama TV(kapanış öncesi Avg, kapanış AvgC): "
        + " · ".join(parts)
        + f"; tekdüze artan: {'evet' if rising else 'hayır'}"
    )
    return Check(id="D1", gate=False, passed=rising, detail=detail)


def run_selftest(
    matches_by_league: Leagues,
    *,
    method: str,
    main_codes: frozenset[str],
    resamples: int = DEFAULT_RESAMPLES,
) -> tuple[Check, ...]:
    """K1, K2, K3, K4, D1 — bu sırayla. Holdout ve sonrası satırlar hiçbir denetime girmez."""
    dev = {
        code: select_periods(matches, periods=frozenset({DEV}))
        for code, matches in matches_by_league.items()
    }
    windowed = {
        code: tuple(
            match
            for match in matches
            if in_window(match, MAIN_WINDOW if code in main_codes else EXTRA_WINDOW)
        )
        for code, matches in dev.items()
    }
    main = {code: matches for code, matches in windowed.items() if code in main_codes}
    return (
        _k1(main, method=method, main_codes=main_codes, resamples=resamples),
        _k2(windowed),
        _k3(windowed, method=method, resamples=resamples),
        _k4(main, method=method, resamples=resamples),
        _d1(main, method=method),
    )
```

- [ ] **Step 8: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_selftest.py -q`
Expected: PASS (25 passed)
Run: `uv run pytest tests/test_selftest.py -q -m leakage`
Expected: `9 passed, 16 deselected`

- [ ] **Step 9: CLI testlerini yaz**

Create `tests/test_backtest_cli.py`:
```python
"""`python -m football_edge.backtest selftest`: önce kilit, sonra denetimler; çıkış kodları.

Veritabanı yok: bağlantı, `load_matches` ve denetimler sahte; sınanan, CLI'nin tutkalıdır. Kilit
dosyası GERÇEKTİR (R99): geçerlisi `dump_lock` ile yazılır, bozuğu diske bozuk yazılır —
`load_lock` hiçbir testte yamalanmaz.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from football_edge import collect
from football_edge.backtest import __main__ as cli
from football_edge.backtest.harness import ResultRecord
from football_edge.backtest.selftest import Check
from football_edge.backtest.strategies import EloPointInTime
from football_edge.history import __main__ as history_cli
from football_edge.history.catalog import EXTRA, MAIN, Catalog, HistoryLeague
from football_edge.history.holdout import HoldoutKey
from football_edge.history.lock import HistoryLock, LockViolation, build_lock, dump_lock, load_lock
from football_edge.history.types import HistMatch
from football_edge.market.devig import DEFAULT_METHOD

CATALOG = Catalog(
    current_season="2627",
    leagues=(
        HistoryLeague(
            code="E0",
            league_id="test.1",
            name="Test Ana",
            country="Ülke A",
            tier=1,
            kind=MAIN,
            first_season="0506",
            odds_api_key="",
        ),
        HistoryLeague(
            code="E1",
            league_id="test.2",
            name="Test Ana 2",
            country="Ülke A",
            tier=2,
            kind=MAIN,
            first_season="0506",
            odds_api_key="",
        ),
        HistoryLeague(
            code="BRA",
            league_id="test.3",
            name="Test Ek",
            country="Ülke B",
            tier=1,
            kind=EXTRA,
            first_season="",
            odds_api_key="",
        ),
    ),
)
GREEN = (Check("K1", True, True, "k1 ayrıntı"), Check("K2", False, False, "k2 ayrıntı"))
# Diske gerçekten bozuk yazılan kilitler (R99: bozuk YAML, sürüm uyuşmazlığı → LockViolation).
CORRUPTIONS: Mapping[str, Callable[[str], str]] = {
    "broken-yaml": lambda valid: "canonical_version: [1\n",
    "wrong-version": lambda valid: valid.replace("canonical_version: 1", "canonical_version: 99"),
}


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        self.closed = True


@dataclass
class Calls:
    connection: FakeConnection = field(default_factory=FakeConnection)
    matches: Mapping[str, Sequence[HistMatch]] = field(default_factory=lambda: {"E0": ()})
    catalog_paths: list[Path] = field(default_factory=list)
    loaded_with: list[tuple[object, object, object, object]] = field(default_factory=list)
    selftest: list[dict[str, Any]] = field(default_factory=list)


def _lock_file(tmp_path: Path) -> Path:
    """Gerçek, geçerli bir kilit dosyası (lig yok): `load_lock` onu gerçekten okur."""
    path = tmp_path / "history_lock.yaml"
    path.write_text(dump_lock(build_lock({}, locked_at=date(2026, 9, 22))), encoding="utf-8")
    return path


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    checks: Sequence[Check] = GREEN,
    mismatch: bool = False,
) -> Calls:
    calls = Calls()

    def load_catalog(path: Path) -> Catalog:
        calls.catalog_paths.append(path)
        return CATALOG

    def load_matches(
        conn: object,
        catalog: Catalog,
        *,
        lock: HistoryLock | None = None,
        key: HoldoutKey | None = None,
    ) -> Mapping[str, Sequence[HistMatch]]:
        calls.loaded_with.append((conn, catalog, lock, key))
        if mismatch:
            raise LockViolation("E0/dev: beklenen 10 satır, gerçek 9")
        return calls.matches

    def run_selftest(
        matches: object, *, method: str, main_codes: frozenset[str], resamples: int
    ) -> tuple[Check, ...]:
        calls.selftest.append(
            {
                "matches": matches,
                "method": method,
                "main_codes": main_codes,
                "resamples": resamples,
                "connection_closed": calls.connection.closed,
            }
        )
        return tuple(checks)

    monkeypatch.setattr(cli, "connect", lambda: calls.connection)
    monkeypatch.setattr(cli, "load_catalog", load_catalog)
    monkeypatch.setattr(cli, "load_matches", load_matches)
    monkeypatch.setattr(cli, "run_selftest", run_selftest)
    return calls


def test_green_gate_checks_exit_zero_even_when_a_report_check_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _patch(monkeypatch)
    caplog.set_level(logging.INFO)

    assert cli.main(["selftest", "--lock", str(_lock_file(tmp_path))]) == 0
    assert "K1 (kapı) GEÇTİ — k1 ayrıntı" in caplog.messages
    assert "K2 (rapor) KALDI — k2 ayrıntı" in caplog.messages


def test_a_red_gate_check_exits_one_and_is_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _patch(monkeypatch, checks=(*GREEN, Check("K4", True, False, "k4 ayrıntı")))
    caplog.set_level(logging.INFO)

    assert cli.main(["selftest", "--lock", str(_lock_file(tmp_path))]) == cli.EXIT_GATE_FAILED == 1
    assert "K4 (kapı) KALDI — k4 ayrıntı" in caplog.messages
    assert "kırmızı kapı denetimi: K4" in caplog.messages


@pytest.mark.leakage
@pytest.mark.parametrize("corruption", sorted(CORRUPTIONS))
def test_a_corrupted_lock_file_exits_nine_before_the_database_is_touched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    corruption: str,
) -> None:
    calls = _patch(monkeypatch)
    lock = _lock_file(tmp_path)
    lock.write_text(CORRUPTIONS[corruption](lock.read_text(encoding="utf-8")), encoding="utf-8")

    assert cli.main(["selftest", "--lock", str(lock)]) == cli.EXIT_LOCK_VIOLATION == 9
    assert (calls.loaded_with, calls.selftest) == ([], [])
    assert any(message.startswith("kilit ihlali") for message in caplog.messages)


@pytest.mark.leakage
def test_a_lock_mismatch_found_by_load_matches_exits_nine_before_any_check_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    calls = _patch(monkeypatch, mismatch=True)

    assert cli.main(["selftest", "--lock", str(_lock_file(tmp_path))]) == 9
    assert calls.selftest == []
    assert any(
        message.startswith("kilit ihlali") and "E0/dev: beklenen 10 satır" in message
        for message in caplog.messages
    )


@pytest.mark.leakage
def test_load_matches_gets_the_loaded_lock_and_no_holdout_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R96: kilidi `load_matches` bütün satırlarda doğrular; CLI ayrıca doğrulamaz, anahtar da
    vermez (holdout açılmaz)."""
    calls = _patch(monkeypatch)
    lock = _lock_file(tmp_path)

    cli.main(["selftest", "--lock", str(lock)])

    assert calls.loaded_with == [(calls.connection, CATALOG, load_lock(lock), None)]
    assert calls.selftest[0]["matches"] is calls.matches


def test_main_leagues_method_and_resamples_reach_the_selftest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _patch(monkeypatch)

    cli.main(
        ["selftest", "--lock", str(_lock_file(tmp_path)), "--method", "power", "--resamples", "300"]
    )

    (call,) = calls.selftest
    assert (call["method"], call["resamples"]) == ("power", 300)
    assert call["main_codes"] == frozenset({"E0", "E1"})


def test_defaults_are_the_committed_lock_the_catalog_and_the_default_method() -> None:
    args = cli._parser().parse_args(["selftest"])

    assert (args.lock, args.catalog) == (
        Path("config/history_lock.yaml"),
        Path("config/history_leagues.yaml"),
    )
    assert (args.method, args.resamples) == (DEFAULT_METHOD, 2000)


def test_the_database_connection_is_closed_before_the_checks_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _patch(monkeypatch)

    cli.main(["selftest", "--lock", str(_lock_file(tmp_path))])

    assert calls.selftest[0]["connection_closed"] is True


def test_an_unknown_devig_method_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch(monkeypatch)

    with pytest.raises(SystemExit) as refused:
        cli.main(["selftest", "--method", "tahmin"])

    assert refused.value.code == 2
    assert calls.selftest == []


def test_the_redacting_log_setup_comes_before_anything_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bağlantı hatası DSN parolasını taşıyabilir: kök handler ondan ÖNCE sarılmış olmalı."""
    calls: list[str] = []

    def catalog(path: Path) -> Catalog:
        calls.append("catalog")
        raise RuntimeError("dur")

    monkeypatch.setattr(cli, "configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(cli, "load_catalog", catalog)

    with pytest.raises(RuntimeError, match="dur"):
        cli.main(["selftest"])
    assert calls == ["logging", "catalog"]


def test_rating_groups_are_the_catalog_countries() -> None:
    """R94: aynı ülkenin ligleri reytingi paylaşır (terfi); başka ülkenin aynı adlı kulübü değil."""
    groups = cli.rating_groups(CATALOG)

    assert dict(groups) == {"E0": "Ülke A", "E1": "Ülke A", "BRA": "Ülke B"}
    assert isinstance(groups, MappingProxyType)
    elo = EloPointInTime(groups=groups).observe(
        ResultRecord(
            league="E1",
            date=date(2024, 8, 3),
            home="Alfa",
            away="Beta",
            home_goals=2,
            away_goals=0,
            known_at=datetime(2024, 8, 3, 17, tzinfo=UTC),
        )
    )
    assert set(elo.ratings) == {("Ülke A", "Alfa"), ("Ülke A", "Beta")}


def test_a_lock_violation_has_the_same_code_as_in_the_history_cli() -> None:
    collectors = {
        value
        for name, value in vars(collect).items()
        if name.startswith("EXIT_") and isinstance(value, int)
    }

    assert cli.EXIT_LOCK_VIOLATION == history_cli.EXIT_LOCK_VIOLATION == 9
    assert cli.EXIT_LOCK_VIOLATION not in collectors | {0, 1}
    assert cli.EXIT_GATE_FAILED == 1
```

- [ ] **Step 10: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_backtest_cli.py -q`
Expected: FAIL — `ImportError: cannot import name '__main__' from 'football_edge.backtest'`

- [ ] **Step 11: CLI'yi yaz**

Create `src/football_edge/backtest/__main__.py`:
```python
"""`python -m football_edge.backtest selftest` — kilitli geliştirme verisinde bilinen sonuçlar.

Önce kilit: kilit dosyası bozuksa ya da önbellek kilitli dönemlerin özetinden farklıysa hiçbir
ölçüm koşmaz (exit 9). Sonra her denetim adıyla loglanır; kapı denetimlerinden biri kırmızıysa
exit 1 (history.yml adlandırır).
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from football_edge.backtest.evaluate import DEFAULT_RESAMPLES
from football_edge.backtest.selftest import Check, run_selftest
from football_edge.collect import configure_logging
from football_edge.db import connect
from football_edge.history.catalog import MAIN, Catalog, load_catalog
from football_edge.history.lock import LockViolation, load_lock
from football_edge.history.sync import load_matches
from football_edge.market.devig import DEFAULT_METHOD, METHODS

LOGGER = logging.getLogger("football_edge.backtest")
LOCK_PATH = Path("config/history_lock.yaml")
CATALOG_PATH = Path("config/history_leagues.yaml")
# 1: bir kapı denetimi kırmızı. Python'ın beklenmedik arızası da 1 verir; ayrım logdadır.
EXIT_GATE_FAILED = 1
# collect.EXIT_* (2–8) ile çakışmaz; history.yml'deki selftest adımı bu kodu adıyla karşılar.
EXIT_LOCK_VIOLATION = 9


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m football_edge.backtest")
    commands = parser.add_subparsers(dest="command", required=True)
    selftest = commands.add_parser("selftest", help="bilinen sonuçlar K1–K4 (+ K2, D1 rapor)")
    selftest.add_argument("--lock", type=Path, default=LOCK_PATH)
    selftest.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    selftest.add_argument("--method", choices=METHODS, default=DEFAULT_METHOD)
    selftest.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    return parser


def rating_groups(catalog: Catalog) -> Mapping[str, str]:
    """Elo'nun reyting grubu (R94): lig kodu → ülke. Elo'yu kuran her yol grupları buradan alır;
    selftest Elo kurmaz (K1–K4 fiyat ve Placebo ile ölçülür)."""
    return MappingProxyType({league.code: league.country for league in catalog.leagues})


def _log(check: Check) -> None:
    kind = "kapı" if check.gate else "rapor"
    verdict = "GEÇTİ" if check.passed else "KALDI"
    LOGGER.info("%s (%s) %s — %s", check.id, kind, verdict, check.detail)


def _selftest(args: argparse.Namespace) -> int:
    catalog = load_catalog(args.catalog)
    try:
        lock = load_lock(args.lock)
        with connect() as conn:
            # Kilit, holdout dahil BÜTÜN satırlarda load_matches'in içinde doğrulanır (R96); dönen
            # yalnız geliştirme ve sonrası dönemidir — holdout history/'den anahtarsız çıkmaz.
            matches = load_matches(conn, catalog, lock=lock)
    except LockViolation as error:
        LOGGER.error("kilit ihlali — bilinen sonuçlar koşulmadı: %s", "; ".join(error.differences))
        return EXIT_LOCK_VIOLATION
    main_codes = frozenset(league.code for league in catalog.leagues if league.kind == MAIN)
    checks = run_selftest(
        matches, method=args.method, main_codes=main_codes, resamples=args.resamples
    )
    for check in checks:
        _log(check)
    failed = [check.id for check in checks if check.gate and not check.passed]
    if failed:
        LOGGER.error("kırmızı kapı denetimi: %s", ", ".join(failed))
        return EXIT_GATE_FAILED
    LOGGER.info("bilinen sonuçlar: kapı denetimlerinin hepsi geçti")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    return _selftest(_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 12: Yeşil olduğunu gör**
Run: `uv run pytest tests/test_backtest_cli.py -q`
Expected: PASS (13 passed)

- [ ] **Step 13: Workflow testlerini güncelle** (`tests/test_history_workflow.py`, Task 6'nın dosyası)

Önce dosyanın Task 6 planındaki adları taşıdığını doğrula:
Run: `grep -nE '^HISTORY = |^SYNC = |^FAKE_UV = |^DATABASE_STEPS: |^def _sync_index|^def test_only_the_database_steps_get_a_secret_and_only_the_database_one' tests/test_history_workflow.py`
Expected: altı eşleşme. Eksik varsa DUR: Task 6'nın birleşen dosyası planından sapmış — controller'a sor.

(a) Import bloğunda `from football_edge import collect` satırının hemen altına:
```python
from football_edge.backtest import __main__ as backtest_cli
```

(b) `DATABASE_STEPS` — secret'ı alan adım adlarına selftest adımı girer; Task 6'nın
`test_only_the_database_steps_get_a_secret_and_only_the_database_one` testinin GÖVDESİ DEĞİŞMEZ. Eski:
```python
# DATABASE_URL'i alan adımlar, adlarıyla. Task 10 `selftest` adımını buraya ekler; başka hiçbir
# adım (checkout, secret taraması, üçüncü taraf setup-uv, `uv sync`, alarm) secret görmez.
DATABASE_STEPS: tuple[str, ...] = ("Senkron",)
```
Yeni:
```python
# DATABASE_URL'i alan adımlar, adlarıyla: senkron ve bilinen sonuçlar. Başka hiçbir adım
# (checkout, secret taraması, üçüncü taraf setup-uv, `uv sync`, alarm) secret görmez.
DATABASE_STEPS: tuple[str, ...] = ("Senkron", "Bilinen sonuçlar")
```

(c) Dosyanın SONUNA, iki boş satırdan sonra (Task 6'nın `FAKE_UV`, `HISTORY`, `_sync_index`i yeniden
kullanılır):
```python
# ── Bilinen sonuçlar adımı (Task 10) ─────────────────────────────────────────────────────────
# Tek job, tek alarm: selftest senkrondan SONRA, alarm adımlarından ÖNCE koşar. Kırmızı senkron
# selftest'i hiç koşturmaz (örtük `success()`); kırmızı selftest turu kırmızıya çevirir.

SELFTEST = "football_edge.backtest selftest"


def _selftest_index() -> int:
    index = _index_of(_steps(HISTORY), SELFTEST)
    assert index is not None, "history.yml bilinen sonuçları (selftest) hiç koşmuyor"
    return index


def test_selftest_runs_after_the_sync_and_before_the_alarm_steps() -> None:
    steps = _steps(HISTORY)
    opens = _index_of(steps, "scripts/ops_alert.py fail --workflow history ")
    closes = _index_of(steps, "scripts/ops_alert.py ok --workflow history ")

    assert opens is not None and closes is not None
    assert _sync_index() < _selftest_index() < opens < closes
    assert (opens, closes) == (len(steps) - 2, len(steps) - 1), "alarm son iki adım değil"


def test_selftest_reads_the_database_only_after_a_green_sync() -> None:
    step = _steps(HISTORY)[_selftest_index()]

    assert step.get("env") == {"DATABASE_URL": "${{ secrets.DATABASE_URL }}"}
    assert "if" not in step, "selftest kırmızı senkrondan sonra da koşar: yarım önbellek ölçülür"
    assert not step.get("continue-on-error"), "kırmızı selftest turu yeşil bırakır"


def _run_selftest_step(tmp_path: Path, *, code: int) -> tuple[int, list[str], str]:
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
    body = str(_steps(HISTORY)[_selftest_index()]["run"])
    result = subprocess.run(
        ["bash", "-e", "-c", body], env=env, capture_output=True, text=True, timeout=30, check=False
    )
    return result.returncode, calls.read_text(encoding="utf-8").splitlines(), result.stdout


@pytest.mark.parametrize(
    ("code", "named"),
    [
        (0, ""),
        (backtest_cli.EXIT_GATE_FAILED, "kapı"),
        (backtest_cli.EXIT_LOCK_VIOLATION, "kilit"),
        (3, "beklenmedik"),
    ],
    ids=["yesil", "kapi", "kilit", "beklenmedik"],
)
def test_selftest_names_every_exit_code_and_keeps_the_run_red(
    tmp_path: Path, code: int, named: str
) -> None:
    returned, calls, out = _run_selftest_step(tmp_path, code=code)

    errors = [line for line in out.splitlines() if line.startswith("::error::")]
    assert calls == [f"run python -m {SELFTEST}"]
    assert returned == code, "selftest'in kodu yutuldu: alarm adımı kırmızıyı görmez"
    if code == 0:
        assert errors == []
    else:
        assert len(errors) == 1 and named in errors[0] and f"exit {code}" in errors[0], errors
```

Run: `uv run ruff format tests/test_history_workflow.py && uv run ruff check tests/test_history_workflow.py`
Expected: `1 file left unchanged` (ya da yalnız boş satır düzeltmesi) ve `All checks passed!`

- [ ] **Step 14: Kırmızı olduğunu gör**
Run: `uv run pytest tests/test_history_workflow.py -q`
Expected: FAIL (7 failed, 11 passed) — altı `test_selftest_*` testi `AssertionError: history.yml bilinen
sonuçları (selftest) hiç koşmuyor`; `test_only_the_database_steps_get_a_secret_and_only_the_database_one`
`AssertionError: adı bulunamayan adım: ('Senkron', 'Bilinen sonuçlar')`. Task 6'nın kalan 11 testi yeşil.

- [ ] **Step 15: `history.yml`e selftest ADIMINI ekle**

Önce: `grep -c '      - name: Alarm aç' .github/workflows/history.yml` → `1`.

(a) Job yorumu:
```yaml
  # TEK job: tests/workflow_helpers.py `_steps()` tek job varsayar. Task 10'un `selftest`i ikinci
  # bir job değil, `Senkron` ile alarm adımları arasına girecek bir ADIMDIR.
```
yerine:
```yaml
  # TEK job: tests/workflow_helpers.py `_steps()` tek job varsayar. Bilinen sonuçlar (`selftest`)
  # bu yüzden ikinci bir job değil, `Senkron` ile alarm adımları arasında bir ADIMDIR.
```

(b) `Senkron` adımının yorumu:
```yaml
        # Veritabanı secret'ını yalnız veritabanını kullanan adımlar alır (bugün bu; Task 10'dan
        # sonra selftest) — liste tests/test_history_workflow.py::DATABASE_STEPS. Girdi `env` ile
        # gelir, betiğe `${{ }}` ile gömülmez. Task 10'un selftest ADIMI bu adımla alarm
        # adımlarının arasına girer.
```
yerine:
```yaml
        # Veritabanı secret'ını yalnız veritabanını kullanan adımlar alır (bu ve selftest) — liste
        # tests/test_history_workflow.py::DATABASE_STEPS. Girdi `env` ile gelir, betiğe `${{ }}`
        # ile gömülmez.
```

(c) `      - name: Alarm aç` satırının HEMEN ÖNCESİNE (yani `Senkron`un `exit "$code"` satırından sonra).
Adım adı `DATABASE_STEPS`teki adla BİREBİR aynıdır (`Bilinen sonuçlar`):
```yaml
      - name: Bilinen sonuçlar
        # Örtük `success()`: kırmızı senkronun yarım bıraktığı önbellek ölçülmez, alarmı zaten açılır.
        # Önce kilit (exit 9: kilitli dönemler değişti, hiçbir ölçüm koşmadı), sonra K1–K4 (exit 1).
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          set +e
          uv run python -m football_edge.backtest selftest
          code=$?
          set -e
          case "$code" in
            0) ;;
            1) echo "::error::selftest: bilinen sonuç kapısı kırmızı ya da beklenmedik arıza (exit 1) — hangi K olduğu yukarıdaki satırlarda" ;;
            9) echo "::error::selftest: kilit ihlali (exit 9) — önbellek kilitli dönemlerden farklı, K1–K4 koşulmadı" ;;
            *) echo "::error::selftest beklenmedik kodla düştü (exit $code)" ;;
          esac
          exit "$code"
```

`timeout-minutes: 60` değişmez.

- [ ] **Step 16: Yeşil olduğunu gör, statik denetim**
Run: `uv run pytest tests/test_history_workflow.py -q`
Expected: PASS (18 passed)
Run: `uv run pytest tests/test_workflows.py tests/test_collect_workflows.py -q`
Expected: PASS — `[history.yml]` parametreleri (alarm son iki adım, yalnız kapatan adım
`continue-on-error`, checkout token'ı diskte değil) selftest adımıyla da yeşil
Run: `uv run pytest tests/test_evaluate.py tests/test_selftest.py tests/test_backtest_cli.py tests/test_history_workflow.py -q`
Expected: PASS (64 passed)
Run: `uv run pytest tests/test_evaluate.py tests/test_selftest.py tests/test_backtest_cli.py tests/test_history_workflow.py -q -m leakage`
Expected: `13 passed, 51 deselected`
Run: `uv run pytest -q`
Expected: PASS (0 failed)
Run: `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src scripts`
Expected: temiz (`Success: no issues found`)

- [ ] **Step 17: Mutasyon kanıtı** (`PYTHONDONTWRITEBYTECODE=1`, her biri geri alınır)

Her satır plan yazılırken ayrı bir kopyada uygulandı ve adı geçen test(ler) KIRMIZI ölçüldü: Task 0,
1, 2, 3 ve 6'nın modülleri, `history.yml` ve `tests/test_history_workflow.py` o görevlerin plan
bölümlerinden BİREBİR alındı (numpy'lı `metrics.py` dahil); düzeltme turunun R96 `load_matches`i ve
R99 `load_lock`u sözleşmeye göre benzetildi, 0008 sözleşmeye uyan bir taslaktı.
Başlamadan:
```bash
M=$(mktemp -d)
shasum -a 256 src/football_edge/backtest/evaluate.py src/football_edge/backtest/selftest.py \
  src/football_edge/backtest/__main__.py .github/workflows/history.yml > "$M/once.sha"
```
Her satırda: değişikliği yap → `PYTHONDONTWRITEBYTECODE=1 uv run pytest <testin dosyası> -q` → adı geçen
test FAIL → değişikliği elle geri al.

| # | Mutasyon (dosya:ne değişir) | Kırmızı olması gereken test |
|---|---|---|
| 1 | `selftest.py:_k1` `positive >= K1_MIN_POSITIVE` → `positive > K1_MIN_POSITIVE` | `test_k1_needs_eighteen_main_leagues_with_a_positive_gap[18]` |
| 2 | `selftest.py:_k1` `passed = interval.low > 0 and positive >= …` → `passed = positive >= K1_MIN_POSITIVE` | `test_k1_fails_when_the_pooled_gap_is_not_above_zero_despite_eighteen_positive_leagues` |
| 3 | `selftest.py:_k1` `PRE_AVG, CLOSE_AVG` → `CLOSE_AVG, PRE_AVG` | `test_k1_passes_when_the_closing_beats_the_pre_closing_price_in_every_main_league` |
| 4 | `selftest.py:run_selftest` `MAIN_WINDOW if code in main_codes else EXTRA_WINDOW` → `EXTRA_WINDOW` | `test_main_leagues_are_measured_only_inside_the_main_window`, `test_k3_measures_main_leagues_only_inside_the_main_window` |
| 5 | `selftest.py:run_selftest` `select_periods(matches, periods=frozenset({DEV}))` → `tuple(matches)` | `test_selftest_asks_select_periods_for_the_development_period_only` |
| 6 | `selftest.py:_k3` `>= K3_MIN_COVERAGE` → `> K3_MIN_COVERAGE` | `test_k3_keeps_only_league_seasons_where_both_closings_cover_ninety_percent[ninety-kept]` |
| 7 | `selftest.py:_k4` `passed=interval.high < 0` → `passed=interval.estimate < 0` | `test_k4_fails_when_the_clv_interval_reaches_zero_despite_a_negative_mean` |
| 8 | `selftest.py:_k2` `min(scores[SHIN], scores[POWER]) < scores[MULTIPLICATIVE]` → `>` | `test_k2_prefers_shin_or_power_when_favourites_win_more_than_multiplicative_implies`, `test_k2_is_reported_not_gated_when_multiplicative_wins` |
| 9 | `selftest.py:_d1` `all(a <= b …)` → `all(a >= b …)` | `test_d1_passes_when_price_drift_grows_with_the_time_from_decision_to_kickoff`, `test_d1_fails_when_price_drift_shrinks_with_the_time_to_kickoff` |
| 10 | `selftest.py:_d1` `low <= hours < high` → `low < hours <= high` (12 sa ve 36 sa kova değiştirir) | `test_d1_passes_when_price_drift_grows_with_the_time_from_decision_to_kickoff` |
| 11 | `selftest.py:run_selftest` `_k2(windowed)` → `_k2(main)` (ek ligler düşer) | `test_k2_prefers_shin_or_power_when_favourites_win_more_than_multiplicative_implies` |
| 12 | `selftest.py:_k4` CLV yeniden `evaluate(result, method=method)` üzerinden (import edilerek) | `test_k1_fails_when_the_pre_closing_and_closing_prices_are_swapped` (`ValueError: kalibrasyon fiti yakınsamadı`) |
| 13 | `evaluate.py:clv_values` `fair[RESULTS.index(prediction.bet.outcome)]` → `fair[RESULTS.index(result.outcomes[prediction.match_index].result)]` | `test_clv_prices_the_bet_against_the_devigged_avg_closing_of_the_bet_outcome` |
| 14 | `evaluate.py:evaluate` `outcomes = [… for prediction in result.predictions]` → `[RESULTS.index(outcome.result) for outcome in result.outcomes.values()]` | `test_evaluate_scores_each_prediction_against_its_own_outcome` |
| 15 | `evaluate.py:_closing_probs` `except InvalidPrices:` → `except KeyError:` | `test_closing_prices_the_method_refuses_stay_out_of_clv[shin-refuses]` |
| 16 | `evaluate.py` `REFERENCE_BOOK = "Avg"` → `"PS"` | `test_clv_prices_the_bet_against_the_devigged_avg_closing_of_the_bet_outcome`, `test_bets_without_a_complete_avg_closing_stay_out_of_clv` |
| 17 | `__main__.py:_selftest` `load_matches(conn, catalog, lock=lock)` → `load_matches(conn, catalog)` (kilit doğrulanmaz, R96) | `test_load_matches_gets_the_loaded_lock_and_no_holdout_key` |
| 18 | `__main__.py:_selftest` `check.gate and not check.passed` → `not check.passed` | `test_green_gate_checks_exit_zero_even_when_a_report_check_fails` |
| 19 | `__main__.py:_selftest` ` if league.kind == MAIN` silinir (ek ligler de "ana") | `test_main_leagues_method_and_resamples_reach_the_selftest` |
| 20 | `__main__.py:main` `configure_logging()` satırı silinir | `test_the_redacting_log_setup_comes_before_anything_else` |
| 21 | `history.yml` selftest adımında `9) echo` → `99) echo` | `test_selftest_names_every_exit_code_and_keeps_the_run_red[kilit]` |
| 22 | `history.yml` selftest adımına `continue-on-error: true` | `test_selftest_reads_the_database_only_after_a_green_sync`, `test_workflows.py::test_only_the_closing_step_may_fail_without_turning_the_run_red[history.yml]` |
| 23 | `history.yml` selftest adımının `exit "$code"` satırı (`Alarm aç`tan hemen önceki; `Senkron`unki DEĞİL) → `exit 0` | `test_selftest_names_every_exit_code_and_keeps_the_run_red[kapi]`, `…[kilit]` |
| 24 | `history.yml` selftest adımına `if: always()` | `test_selftest_reads_the_database_only_after_a_green_sync` |
| 25 | `history.yml` job düzeyine `env: DATABASE_URL: ${{ secrets.DATABASE_URL }}` | `test_only_the_database_steps_get_a_secret_and_only_the_database_one` |
| 26 | `history.yml` `Senkron`dan ÖNCEYE ikinci bir selftest adımı (`uv run python -m football_edge.backtest selftest`) | `test_selftest_runs_after_the_sync_and_before_the_alarm_steps` |
| 27 | `history.yml` selftest adımının `env:` bloğu silinir | `test_selftest_reads_the_database_only_after_a_green_sync`, `test_only_the_database_steps_get_a_secret_and_only_the_database_one` |
| 28 | `history.yml` `name: Bilinen sonuçlar` → `name: Selftest` (`DATABASE_STEPS`le bağ kopar) | `test_only_the_database_steps_get_a_secret_and_only_the_database_one` |
| 29 | `__main__.py:rating_groups` `league.country` → `league.league_id` (grup ülke olmaktan çıkar) | `test_rating_groups_are_the_catalog_countries` |
| 30 | `__main__.py:_selftest` `lock = load_lock(args.lock)` `try:`un DIŞINA (bozuk kilit istisnası yükselir, R99) | `test_a_corrupted_lock_file_exits_nine_before_the_database_is_touched[broken-yaml]`, `…[wrong-version]` |
| 31 | `selftest.py:run_selftest` `_k4(main, …)` → `_k4(windowed, …)` (m7) | `test_k4_and_d1_measure_only_the_main_leagues` |
| 32 | `selftest.py:run_selftest` `_d1(main, …)` → `_d1(windowed, …)` (m7) | `test_k4_and_d1_measure_only_the_main_leagues` |
| 33 | `__main__.py:_selftest` `"; ".join(error.differences)` → `"kilit"` (farklar loglanmaz) | `test_a_lock_mismatch_found_by_load_matches_exits_nine_before_any_check_runs` |

Bitince geri yüklemeyi kanıtla:
Run: `shasum -a 256 -c "$M/once.sha" && uv run pytest tests/test_evaluate.py tests/test_selftest.py tests/test_backtest_cli.py tests/test_history_workflow.py -q`
Expected: dört satır `OK`, `64 passed`

- [ ] **Step 18: Commit**
```bash
git add src/football_edge/backtest/evaluate.py src/football_edge/backtest/selftest.py \
  src/football_edge/backtest/__main__.py .github/workflows/history.yml tests/test_evaluate.py \
  tests/test_selftest.py tests/test_backtest_cli.py tests/test_history_workflow.py
git commit -m "feat: bütünleşik harness — değerlendirme, bilinen sonuçlar K1–K4 ve history.yml selftest adımı (T2b)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 19: Kapının tamamı**
Run: `TMPDIR=$(mktemp -d) ./verify.sh` — log DOSYASINDAN oku.
Expected: 10 adım PASS (Task 5'in `sızıntı` adımı dahil; bu görev 12 yeni `leakage` testi ekler) +
`SKIP: zincir (DATABASE_URL yok)`. Kapı K1–K4'ü GERÇEK veride ÖLÇMEZ (veritabanı yok): gerçek sonuç
ilk `history.yml` turunun logundadır — Task 12 onu okur.

---

### Task 11: Kırmızı takım sızıntı denetimi (T6)

**Kademe:** K1 · **Dalga:** 4 · **Önkoşul:** Task 9 ve 10 birleşti, kilit commit'li.

Bu görev kod yazmaz; bağımsız bir inceleme ajanı (fable, kabuklu `general-purpose`) harness'ta
ileriye bakma hatası arar. Bulgular normal düzeltme döngüsüne girer.

- [ ] **Step 1: Denetim brief'i** (`.superpowers/sdd/<plan>/task-11-brief.md`) — ajana verilecekler:
tasarım §4.5, §5, §7, §10, bu planın Global Constraints'i ve şu modüller: `history/football_data.py`,
`history/holdout.py`, `history/lock.py`, `history/sync.py`, `backtest/*.py`, `market/efficiency.py`,
`market/metrics.py`, `market/devig.py`. Görev: "bu backtest'te ileriye bakma hatasını bul". Bakılacak
yerler (tasarım §10): sezon düzeyi normalizasyonlar, terfi eden takımın başlangıç reytingi, çift maç
satırı, saat dilimi ve yaz saati, karar anı kuralı ve kenar günleri, erteleme, eşzamanlı olayların
sırası, `load_matches` sıralaması, verimlilik ve selftest yollarında holdout filtresi, kilidin
kullanılan oran sütunlarını kapsaması, hiperparametre seçimi yoluyla holdout sızıntısı. Ajan her
şüpheyi ÇALIŞTIRARAK sınar (izole `git archive` kopyası, `PYTHONDONTWRITEBYTECODE=1`): sızan bir
strateji ya da özellik yazmayı dener ve harness'ın onu reddedip reddetmediğini görür.

- [ ] **Step 2: Dispatch** — `general-purpose`, model `fable`, arka planda; rapor dosyası
`task-11-report.md`: bulgu başına önem (Critical/Important/Minor), yeniden üretim komutu, önerilen
düzeltme.

- [ ] **Step 3: Bulguları döngüye sok** — her Critical/Important ilgili görevin sahibine (defterdeki
implementer; yoksa taze bir implementer) düzeltme turu olarak; kapsamlı yeniden inceleme; Minor'lar
defterde `deferred`.

- [ ] **Step 4: Rapor** — `docs/reports/<tarih>-sizinti-denetimi.md`: yöntem, denenen saldırılar,
bulgular ve kapanışları, açık kalanlar (Task 12'nin "ölçmedikleri" listesine). Yalnız kod ve sonuç
anlatır, veri satırı içermez.

```bash
git add docs/reports/<tarih>-sizinti-denetimi.md
git commit -m "docs: Faz 2 kırmızı takım sızıntı denetimi raporu

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 12: Faz 2 kapısı, lig önerisi ve HANDOFF (controller)

**Kademe:** — (controller) · **Dalga:** 4 · **Önkoşul:** Task 0–11 `complete`, açık Critical/Important
yok.

- [ ] **Step 1: Verimlilik raporu**

Run: `uv run --env-file .env python -m football_edge.market efficiency --out docs/reports/<tarih>-piyasa-verimliligi.md`
Expected: exit 0; rapor yalnız toplu sayı taşır (ham satır aranarak kontrol edilir: takım adı + tarih
birlikte geçmemeli).

- [ ] **Step 1b: İlk gerçek köprü raporu (T7, R91)**

Run: `uv run --env-file .env python -m football_edge.market bridge --out docs/reports/<tarih>-kapanis-koprusu.md --since 2026-09-19`
Expected: exit 0; `n` o güne kadar mühürlenip football-data'da da görünen maç sayısı, `unmatched` 0 (Task 8
Step 12'nin takma adlarıyla). Aralık geniş olabilir — tasarım §9 bunu kabul eder, rapor adıyla yazar.
Rapor yalnız toplu sayı taşır; commit Step 1'in raporuyla birlikte.

- [ ] **Step 2: Bilinen sonuçlar**

Run: `uv run --env-file .env python -m football_edge.backtest selftest`
Expected: exit 0 — K1, K3, K4 `passed=True`; K2 ve D1 raporlanır. Bir kapı kontrolü düşerse faz
geçmez: kırmızı kontrolün sahibi olan göreve bulgu olarak döner.

- [ ] **Step 3: Varsayılan vig yöntemi** — K2'nin en düşük log loss'u veren yöntemi `SHIN` değilse
`market/devig.py` `DEFAULT_METHOD` değişir: küçük bir K1 görevi (test sabitlemesiyle) → kapsamlı
inceleme → birleştirme. `SHIN` ise değişiklik yok, karar defterde.

- [ ] **Step 4: Lig önerisi → kullanıcı** — raporun aday listesi (tasarım §8.4) kullanıcıya
`AskUserQuestion` ile sunulur. Onaylanan ligler `config/leagues.yaml`a ayrı bir görevle girer — not:
`League` bugün `footystats_path`i zorunlu tutuyor; footystats sayfası olmayan bir aday bu alanın
isteğe bağlı olmasını gerektirir (o görevin kapsamı).

- [ ] **Step 5: Holdout açılış sayısı**

```sql
select count(*) from holdout_access_log;   -- Faz 2 sonunda 0 olmalı
```
Sıfır değilse faz geçmez (tasarım §5.3).

- [ ] **Step 6: Faz 2 HANDOFF** — `docs/phases/02-tarihsel-taban/HANDOFF.md`: ne bitti; kapı ne
ölçtü (adım adım, log dosyasından; `sızıntı` alt sınırı son kez ölçülüp güncellenir); **kapının ölçmedikleri** (tasarım §13 + yürütmede eklenenler + T6'nın
açık kalanları); verilen kararlar (defterdeki bütün `Ruling:` satırları); ertelenenler
(`docs/DEFERRED.md` yeni bölüm — defterdeki 0a Minor'ları ve plan yazımında ertelenenler dahil); tasarım
belgesinin §5.2 "kaynak metni" cümlesi R86'ya göre (ayrıştırılmış değerler) ve §7.2'nin "durumun o anki
görüntüsü" cümlesi R98'e göre (durum stratejide, `observe` ile; Faz 3 eşitlik testi bağlamı VE `observe`
akışını karşılaştırır) düzeltilir; Faz 3'ün ön koşulları (walk-forward doğrulama, canlı bağlam kurucusu
ve eşitlik testi, Elo fiti, scipy dalga 0'ı). `docs/HANDOFF.md` §0 güncellenir.

- [ ] **Step 7: Son kapı ve push** — taze klon, `TMPDIR` klonun dışında, `./verify.sh` log dosyasından;
`git fetch origin && git merge --no-ff origin/main`; `git push origin main`; CI yeşil.

---

## Faz 2 kapısının ÖLÇMEYECEKLERİ — Task 12'nin başlangıç listesi

Tasarım §13'ün on dört maddesi aynen geçerlidir. Plan yazılırken eklenenler:

15. **Karar anı kuralının doğrulaması dolaylıdır** (Task 10, D1): fiyat kayması–süre tekdüzeliği
    kuralı çürütebilir, kanıtlayamaz.
16. **`load_matches`in belleği gerçek veride ölçülmedi** (~240 bin maç). Plan incelemesinin deneyi: maç başına
    ~4,4 KB kalıcı → ~1,1 GB (runner 7 GB+); Task 8 Step 13 gerçek tepeyi ölçer. Ucuz iyileştirme ertelendi:
    `HistMatch.odds` sözlüğü yerine `ODDS_COLUMNS` sırasına hizalı bir demet.
17. **`first_season: "0506"` lig lig ölçülmedi**: eksik sezon dosyası ilk `--all` turunda 404 olarak
    görünür (Task 8 Step 10).
18. **`current_season` elle ilerletilir**; unutulursa yeni sezon hiç çekilmez — kapı bunu görmez, yalnız
    T7 raporu `n`in büyümediğini gösterir (RUNBOOK §3.10).
19. **R77 kural testinin bilinen boşlukları** (DEFERRED; defterdeki 0a Minor'ları): ek taşıyan dizeler
    (`"camoufox==0.4"`, `"pip install …"`), elle yazılmış proxy döndürme, Scrapling'in `spiders`/`core.ai`/
    `core.shell`/`cli` yolları (bugün kilit ve çalışma zamanı `ImportError` yakalıyor).
20. **Eski append-only tablolarda TRUNCATE ve RLS koruması yok** (0001–0005); 0006 ve 0007'de var (R90).
21. **`open_holdout` bağlantıdaki bekleyen başka yazımları da commit'ler** (docstring'de yazılı);
    yalnız `final_eval` çağırır (Faz 3).
22. **Köprü `n = 0` iken rapor yazmaz** (`EXIT_NO_PAIRS = 10`, R93): o durumda HANDOFF "N=0" yazar.
23. **Kilit kanonik satırı ayrıştırılmış değerlerden kurulur** (R86): kaynağın biçim değişikliği
    ("2.10" → "2.1") görünmez; değer değişikliği görünür.
24. **Plan yeniden incelemesinin kalan gözlemleri** (uygulama incelemelerinde kapanır): `_measure`in yakalama
    genişliği testsiz (`except NoClosingPrices` → `except ValueError` mutantı sağ kalıyor); `load_matches`in
    GERÇEK anahtarla holdout döndüren pozitif yolu testsiz (Faz 2 anahtar açmaz; `final_eval` Faz 3'te sınar);
    EKSİK kilit dosyası exit 9 değil exit 1 + traceback (R99 yalnız bozuk dosyayı kapsıyor).

## Self-review — plan tasarıma karşı (controller, yazıldığı gün)

- **Kapsam:** tasarım §4.1 → Task 6 · §4.2 → Task 1 · §4.3 → Task 6 (0006) · §4.4 → Task 1 · §4.5 → Task 4
  (kural) + Task 10 (D1 doğrulaması) · §4.6 → Task 1 (önbellekte, kullanılmaz) · §5 → Task 3, kilit commit'i
  Task 8, açılış sayısı Task 12 · §6 → Task 2 (+ yöntem seçimi Task 9/12) · §7 → Task 4 + Task 10 · §7.4 →
  arayüz (kanıt Faz 3) · §8 → Task 9 (rapor Task 12) · §9 → Task 7 (+ CLI Task 9, rapor Task 12) · §10 →
  Task 3/4 yapısal testleri + Task 11 · §11 → Task 5 (`sızıntı`), Task 8 (bekçi, pg_cron), Task 10 (K1–K4)
  · §12 → dalgalar · §13 → yukarıdaki liste · §14 → spec güncellemesi `5b3addd` (R86'nın tasarım metni Task 12).
- **Yer tutucu taraması:** "TBD/TODO/benzer şekilde/uygun hata" yok; `<tarih>`, `<tur kimliği>`, `<plan>` ve
  Task 5'in ölçülen `N`i çalışma zamanı değerleridir (aşağıda tanımlı).
- **Tip tutarlılığı:** bütün Python blokları AST ile ayrıştırıldı; görevler arası 152 anahtarlı çağrının
  hiçbiri tanımın parametreleriyle çelişmiyor (işaretlenenler aynı adlı, dosyaya özel test yardımcılarıydı).
  Bilinen tekrar: `hist_match` iki ayrı test yardımcısında (`tests/market_factory.py`, Task 2 ·
  `tests/backtest_builders.py`, Task 4) — dalga 1'de paralel yazıldıkları için; birleştirme ertelendi.
- **Kodun kendisi:** her görev bölümünün kodu yazarınca izole bir kopyada koşuldu (ruff, mypy strict,
  pytest, listelenen mutasyonların hepsi kırmızı); Task 0 ve Task 8'in controller kodu kopyada kapının
  tamamından geçti.
- **Bağımsız plan incelemesi (fable, iki tur):** planın kodu plan METNİNDEN tek ağaca dalga dalga kuruldu.
  Tur 1: W0–W2 ve Task 8 yeşil, W3 kırmızı (Task 9 ↔ R89); 1 Critical (lig önerisi yapısal boş), 3 Important
  (Task 9 ↔ R89, holdout'un `load_matches`ten anahtarsız çıkması, `value_rate` testi), 10 Minor. Düzeltme turu
  (R95–R100). Tur 2: her dalga ilk denemede yeşil — son durum 10 adım PASS + `zincir` SKIP, 1382 passed /
  2 skipped, leakage 220; revize "Expected" sayılarının hepsi tuttu; eski sağ kalan 6 mutantın 6'sı ve yeni
  kuralların 16 mutantının 15'i kırmızı; yeni kırılma yok. Kalan gözlemler madde 24'te.

## Yürütme

- **Yöntem:** `superpowers:subagent-driven-development`, bu projenin kurallarıyla: görev başına taze
  implementer (izole worktree, dal adı görevin başlığındaki), controller'ın ürettiği inceleme paketiyle
  bağımsız inceleme (kabuklu `general-purpose`; K1 görevlerde model `fable`), düzeltme turu (K2: bulgular
  tek turda toplu), kapsamlı yeniden inceleme, controller mutasyon kanıtı (`git archive` kopyası,
  `PYTHONDONTWRITEBYTECODE=1`), her commit'ten sonra `verify.sh`'ın tamamı, `main`e `--no-ff`, taze
  klon kapısı, push (önce `git fetch` + `git merge --no-ff origin/main`; rebase/force YOK).
- **Dalgalar:** 0 → 1 (Task 1–4 paralel) → 5 → 2 (Task 6, 7 paralel) → 8 → 3 (Task 9, 10 paralel) → 4
  (Task 11) → 12. Aynı anda en çok 4 implementer. Her dalgadan önce tek-yazar taraması (yukarıdaki
  paralellik tablosu) defterde yeniden yapılır.
- **Scratchpad:** paralel ajanlar oturumun scratchpad'ini paylaşır — her ajana kendi alt dizini verilir,
  başkasının dizinine yazmaz, hiçbir şeyi onaysız silmez (plan yazımında iki kez yaşandı).
- **Model:** varsayılan opus; K1 incelemeleri, Task 11 ve bütün-dal incelemesi fable; haiku hiçbir yerde.
- **Çalışma zamanı değerleri:** `<tarih>` komutun koşulduğu gün (`YYYY-MM-DD`), `<tur kimliği>` o adımın
  Actions tur numarası, `<plan>` bu planın defter dizini — hepsi koşulurken bilinir, önceden yazılamaz.
- **Onay kapıları:** bu plan kullanıcı onayından önce uygulanmaz; Task 12 Step 4 (lig önerisi) ayrıca
  kullanıcı onayı ister.
