# Faz 0 — Kayıt Altyapısı Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Her gün oran çekip değiştirilemez bir deftere yazan ve maç başlarken kapanış oranını mühürleyen, ücretsiz bulutta koşan bir kayıt sistemi kurmak.

**Architecture:** Python toplayıcı → The Odds API → hash-zincirli append-only Postgres defteri (Supabase). İki zamanlanmış iş: `snapshot` (maç öncesi periyodik) ve `seal` (başlama saatinde kapanış mührü). Zincir başı her gün public repoya yazılarak dış çıpa oluşturulur.

**Tech Stack:** Python 3.11+, uv, httpx, psycopg3, PyYAML, pytest, ruff, mypy, Supabase Postgres, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-19-football-edge-design.md`

## Global Constraints

- **Python ≥ 3.11.** Tür ipuçları zorunlu; `from __future__ import annotations` her modülde.
- **Mutasyon yok.** Veri yapıları `frozen=True` dataclass veya tuple; mevcut nesne değiştirilmez, yenisi üretilir.
- **Dosya boyutu:** 200-400 satır normal, 800 mutlak üst sınır. Fonksiyon < 50 satır. 4+ seviye iç içe yok.
- **`print` yok** kütüphane kodunda; `logging` kullanılır. CLI giriş noktası hariç.
- **Hardcoded secret yok.** Env değişkenleri: `ODDS_API_KEY`, `DATABASE_URL`. Yoksa açık hata fırlatılır.
- **Defter append-only.** `odds_snapshots` üzerinde UPDATE/DELETE veritabanı seviyesinde reddedilir.
- **Kaynak politikası (spec §3.2):** robots.txt'i otomatik erişime kapalı kaynak taranmaz; erişim kontrolü aşılmaz.
- **Kredi disiplini:** The Odds API maliyeti = `market sayısı × region sayısı`. `/v4/sports` ve `/v4/sports/{sport}/events` ücretsizdir. Her çağrıdan sonra `x-requests-remaining` okunur ve eşiğin altına inince iş durur.
- **Kapı (`./verify.sh`):** `ruff check` + `ruff format --check` + `mypy src` + `pytest` + zincir doğrulama. Hepsi yeşil değilse faz bitmemiştir.

---

## Dosya Yapısı

| Dosya | Sorumluluk |
|---|---|
| `pyproject.toml` | Bağımlılıklar, ruff/mypy/pytest konfigürasyonu |
| `verify.sh` | Kapı — tek komut, tüm kontroller |
| `config/leagues.yaml` | Lig kayıtları (id, odds_api_key, dil, aktiflik) |
| `src/football_edge/leagues.py` | `leagues.yaml` yükleme ve doğrulama |
| `src/football_edge/odds_api.py` | The Odds API istemcisi + yanıt düzleştirme + kota okuma |
| `src/football_edge/ledger.py` | Hash zinciri hesaplama ve doğrulama (saf fonksiyonlar) |
| `src/football_edge/db.py` | Postgres bağlantısı, insert, sorgu |
| `src/football_edge/collect.py` | CLI: `snapshot`, `seal`, `verify-chain`, `publish-head` |
| `db/migrations/0001_init.sql` | Şema + append-only tetikleyici |
| `.github/workflows/snapshot.yml` | Periyodik maç öncesi tarama |
| `.github/workflows/seal.yml` | Başlama saati kapanış mührü |
| `ledger/` | Günlük zincir başı dosyaları (dış çıpa) |
| `tests/` | Her modül için birim testler |

---

### Task 1: Proje iskeleti ve kapı

**Files:**
- Create: `pyproject.toml`, `uv.lock`, `verify.sh`, `src/football_edge/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`
- Zaten var, DOKUNMA: `.gitignore` (`.env` girdisiyle birlikte commit'li)

**Interfaces:**
- Consumes: yok
- Produces: `football_edge` paketi import edilebilir; `./verify.sh` çalışır ve exit 0 döner.

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:
```python
from __future__ import annotations

import football_edge


def test_package_exposes_version() -> None:
    assert isinstance(football_edge.__version__, str)
    assert football_edge.__version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge'`

- [ ] **Step 3: Create pyproject.toml**

`pyproject.toml`:
```toml
[project]
name = "football-edge"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "psycopg[binary]>=3.2",
    "pyyaml>=6.0",
]

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.6", "mypy>=1.11", "types-PyYAML"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/football_edge"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "T20"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src"]
```

- [ ] **Step 4: Create the package**

`src/football_edge/__init__.py`:
```python
from __future__ import annotations

__version__ = "0.1.0"
```

`tests/__init__.py`: (boş dosya)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 6: Create the gate**

`verify.sh`:
```bash
#!/usr/bin/env bash
# football-edge kapısı. Çıktı dosyaya yazılır; özet değil çıktı okunur.
set -uo pipefail

LOG="${TMPDIR:-/tmp}/football-edge-verify.log"
: > "$LOG"
FAILED=0

step() {
  local name="$1"; shift
  echo "=== $name ===" | tee -a "$LOG"
  if "$@" >>"$LOG" 2>&1; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    FAILED=1
  fi
}

step "ruff-check"  uv run ruff check src tests
step "ruff-format" uv run ruff format --check src tests
step "mypy"        uv run mypy src
step "pytest"      uv run pytest -q

echo
echo "Tam çıktı: $LOG"
if [ "$FAILED" -ne 0 ]; then
  echo "KAPI KIRMIZI"
  exit 1
fi
echo "KAPI YEŞİL"
```

`.gitignore` **zaten var ve commit'li** — yeniden yazma, üzerine yazma, dokunma.
İçeriği `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`,
`.ruff_cache/`, `.env`, `.env.*`, `!.env.example` satırlarını içeriyor.
`uv.lock` ignore EDİLMEMELİ; listede yok, öyle kalmalı.

- [ ] **Step 7: Generate the lockfile**

CI `uv sync --frozen` ile koşar ve bu, commit'lenmiş bir `uv.lock` olmadan hata verir.

Run: `uv lock`
Expected: `uv.lock` oluşur. `.gitignore`'a EKLENMEZ — repoya girmesi gerekir.

- [ ] **Step 8: Run the gate**

Run: `chmod +x verify.sh && ./verify.sh`
Expected: `KAPI YEŞİL`, exit 0. Kırmızıysa log dosyasını oku ve düzelt.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock verify.sh src tests
git commit -m "chore: proje iskeleti, lockfile ve kapı (ruff+mypy+pytest)"
```

**Not:** `.gitignore` zaten mevcut ve commit'li — yeniden oluşturma, sadece doğrula
(`git check-ignore -v .env` `.env` satırını göstermeli).

---

### Task 2: Lig konfigürasyonu

**Files:**
- Create: `config/leagues.yaml`, `src/football_edge/leagues.py`, `tests/test_leagues.py`

**Interfaces:**
- Consumes: yok
- Produces:
  - `League` frozen dataclass: `id: str, odds_api_key: str, name: str, country: str, lang: str, gl: str, active: bool`
  - `load_leagues(path: Path) -> tuple[League, ...]`
  - `active_leagues(leagues: tuple[League, ...]) -> tuple[League, ...]`

- [ ] **Step 1: Write the failing test**

`tests/test_leagues.py`:
```python
from __future__ import annotations

from pathlib import Path

import pytest

from football_edge.leagues import League, active_leagues, load_leagues

VALID = """
leagues:
  - id: eng.1
    odds_api_key: soccer_epl
    name: Premier League
    country: England
    lang: en
    gl: GB
    active: true
  - id: tur.1
    odds_api_key: soccer_turkey_super_league
    name: Super Lig
    country: Turkey
    lang: tr
    gl: TR
    active: false
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "leagues.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_all_leagues(tmp_path: Path) -> None:
    leagues = load_leagues(write(tmp_path, VALID))
    assert len(leagues) == 2
    assert leagues[0] == League(
        id="eng.1",
        odds_api_key="soccer_epl",
        name="Premier League",
        country="England",
        lang="en",
        gl="GB",
        active=True,
    )


def test_active_leagues_filters(tmp_path: Path) -> None:
    leagues = load_leagues(write(tmp_path, VALID))
    assert tuple(lg.id for lg in active_leagues(leagues)) == ("eng.1",)


def test_missing_field_raises(tmp_path: Path) -> None:
    text = VALID.replace("    country: England\n", "")
    with pytest.raises(ValueError, match="eksik alan"):
        load_leagues(write(tmp_path, text))


def test_unknown_field_raises(tmp_path: Path) -> None:
    text = VALID.replace("    gl: GB\n", "    gl: GB\n    tier: 1\n")
    with pytest.raises(ValueError, match="bilinmeyen alan"):
        load_leagues(write(tmp_path, text))


def test_duplicate_id_raises(tmp_path: Path) -> None:
    text = VALID.replace("id: tur.1", "id: eng.1")
    with pytest.raises(ValueError, match="yinelenen"):
        load_leagues(write(tmp_path, text))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_leagues.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.leagues'`

- [ ] **Step 3: Write minimal implementation**

`src/football_edge/leagues.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class League:
    id: str
    odds_api_key: str
    name: str
    country: str
    lang: str
    gl: str
    active: bool


REQUIRED_FIELDS = frozenset(
    {"id", "odds_api_key", "name", "country", "lang", "gl", "active"}
)


def _validate(entry: dict[str, Any], seen: frozenset[str]) -> None:
    keys = frozenset(entry)
    missing = REQUIRED_FIELDS - keys
    if missing:
        raise ValueError(f"lig kaydında eksik alan: {sorted(missing)} ({entry.get('id', '?')})")
    unknown = keys - REQUIRED_FIELDS
    if unknown:
        raise ValueError(f"lig kaydında bilinmeyen alan: {sorted(unknown)} ({entry['id']})")
    if entry["id"] in seen:
        raise ValueError(f"yinelenen lig id: {entry['id']}")


def load_leagues(path: Path) -> tuple[League, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = raw["leagues"]
    leagues: tuple[League, ...] = ()
    seen: frozenset[str] = frozenset()
    for entry in entries:
        _validate(entry, seen)
        leagues = (*leagues, League(**entry))
        seen = seen | {entry["id"]}
    return leagues


def active_leagues(leagues: tuple[League, ...]) -> tuple[League, ...]:
    return tuple(league for league in leagues if league.active)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_leagues.py -v`
Expected: 5 PASS

- [ ] **Step 5: Create the real league file**

`config/leagues.yaml` — Faz 1'de genişletilecek, Faz 2'de ölçümle budanacak. Başlangıç seti ücretsiz katmanda kredi yakmamak için dar tutulur:
```yaml
# Faz 0 başlangıç seti. Faz 1'de genişler, Faz 2'de piyasa verimliliği
# ölçümüne göre budanır. odds_api_key değerleri /v4/sports çıktısından doğrulanmalı.
leagues:
  - id: eng.1
    odds_api_key: soccer_epl
    name: Premier League
    country: England
    lang: en
    gl: GB
    active: true
  - id: esp.1
    odds_api_key: soccer_spain_la_liga
    name: La Liga
    country: Spain
    lang: es
    gl: ES
    active: true
  - id: ita.1
    odds_api_key: soccer_italy_serie_a
    name: Serie A
    country: Italy
    lang: it
    gl: IT
    active: true
  - id: ger.1
    odds_api_key: soccer_germany_bundesliga
    name: Bundesliga
    country: Germany
    lang: de
    gl: DE
    active: true
  - id: fra.1
    odds_api_key: soccer_france_ligue_one
    name: Ligue 1
    country: France
    lang: fr
    gl: FR
    active: true
  - id: tur.1
    odds_api_key: soccer_turkey_super_league
    name: Super Lig
    country: Turkey
    lang: tr
    gl: TR
    active: true
```

- [ ] **Step 6: Verify the real file loads**

Run: `uv run python -c "from pathlib import Path; from football_edge.leagues import load_leagues; print(len(load_leagues(Path('config/leagues.yaml'))))"`
Expected: `6`

- [ ] **Step 7: Run the gate and commit**

```bash
./verify.sh
git add config/leagues.yaml src/football_edge/leagues.py tests/test_leagues.py
git commit -m "feat: lig konfigürasyonu yükleyici ve doğrulayıcı"
```

---

### Task 3: The Odds API istemcisi

**Files:**
- Create: `src/football_edge/odds_api.py`, `tests/test_odds_api.py`

**Interfaces:**
- Consumes: yok
- Produces:
  - `PriceRow` frozen dataclass: `event_id, sport_key, commence_time, home_team, away_team, bookmaker, bookmaker_last_update, market, outcome, point: float | None, price: float`
  - `Quota` frozen dataclass: `remaining: int, used: int, last_cost: int`
  - `flatten_odds(payload: list[dict]) -> tuple[PriceRow, ...]`
  - `read_quota(headers: Mapping[str, str]) -> Quota`
  - `fetch_odds(client, api_key, sport_key, *, regions="eu", markets="h2h", commence_time_to=None) -> tuple[tuple[PriceRow, ...], Quota]`
  - `QuotaExhausted(RuntimeError)`
  - `guard_quota(quota: Quota, min_remaining: int) -> None`

- [ ] **Step 1: Write the failing test**

`tests/test_odds_api.py`:
```python
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from football_edge.odds_api import (
    Quota,
    QuotaExhausted,
    fetch_odds,
    flatten_odds,
    guard_quota,
    read_quota,
)

PAYLOAD = [
    {
        "id": "abc123",
        "sport_key": "soccer_epl",
        "sport_title": "EPL",
        "commence_time": "2026-09-20T14:00:00Z",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": "2026-09-19T10:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.95},
                            {"name": "Chelsea", "price": 4.10},
                            {"name": "Draw", "price": 3.60},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.90, "point": 2.5},
                            {"name": "Under", "price": 1.95, "point": 2.5},
                        ],
                    },
                ],
            }
        ],
    }
]


def test_flatten_produces_one_row_per_outcome() -> None:
    rows = flatten_odds(PAYLOAD)
    assert len(rows) == 5


def test_flatten_carries_event_and_market_fields() -> None:
    rows = flatten_odds(PAYLOAD)
    first = rows[0]
    assert first.event_id == "abc123"
    assert first.home_team == "Arsenal"
    assert first.bookmaker == "pinnacle"
    assert first.market == "h2h"
    assert first.outcome == "Arsenal"
    assert first.price == 1.95
    assert first.point is None


def test_flatten_keeps_totals_point() -> None:
    rows = flatten_odds(PAYLOAD)
    over = next(r for r in rows if r.outcome == "Over")
    assert over.point == 2.5
    assert over.market == "totals"


def test_flatten_handles_event_with_no_bookmakers() -> None:
    assert flatten_odds([{**PAYLOAD[0], "bookmakers": []}]) == ()


def test_read_quota_parses_headers() -> None:
    quota = read_quota(
        {"x-requests-remaining": "487", "x-requests-used": "13", "x-requests-last": "1"}
    )
    assert quota == Quota(remaining=487, used=13, last_cost=1)


def test_guard_quota_raises_below_threshold() -> None:
    with pytest.raises(QuotaExhausted, match="kalan kredi"):
        guard_quota(Quota(remaining=5, used=495, last_cost=1), min_remaining=10)


def test_guard_quota_passes_above_threshold() -> None:
    guard_quota(Quota(remaining=50, used=450, last_cost=1), min_remaining=10)


def test_fetch_odds_builds_request_and_returns_rows() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json=PAYLOAD,
            headers={
                "x-requests-remaining": "499",
                "x-requests-used": "1",
                "x-requests-last": "1",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rows, quota = fetch_odds(client, "KEY", "soccer_epl", commence_time_to="2026-09-26T00:00:00Z")

    assert len(rows) == 5
    assert quota.remaining == 499

    parsed = urlparse(str(captured["url"]))
    assert parsed.path == "/v4/sports/soccer_epl/odds"
    # Ham dizede yüzde-kodlamaya bakma: onu httpx belirler, biz değil.
    params = parse_qs(parsed.query)
    assert params["apiKey"] == ["KEY"]
    assert params["regions"] == ["eu"]
    assert params["markets"] == ["h2h"]
    assert params["oddsFormat"] == ["decimal"]
    assert params["dateFormat"] == ["iso"]
    assert params["commenceTimeTo"] == ["2026-09-26T00:00:00Z"]


def test_fetch_odds_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "invalid key"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_odds(client, "BAD", "soccer_epl")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_odds_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.odds_api'`

- [ ] **Step 3: Write minimal implementation**

`src/football_edge/odds_api.py`:
```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

BASE_URL = "https://api.the-odds-api.com/v4"


class QuotaExhausted(RuntimeError):
    """Kalan kredi güvenli eşiğin altına indi."""


@dataclass(frozen=True)
class Quota:
    remaining: int
    used: int
    last_cost: int


@dataclass(frozen=True)
class PriceRow:
    event_id: str
    sport_key: str
    commence_time: str
    home_team: str
    away_team: str
    bookmaker: str
    bookmaker_last_update: str
    market: str
    outcome: str
    point: float | None
    price: float


def _rows_for_event(event: dict[str, Any]) -> tuple[PriceRow, ...]:
    rows: tuple[PriceRow, ...] = ()
    for bookmaker in event.get("bookmakers", ()):
        for market in bookmaker.get("markets", ()):
            for outcome in market.get("outcomes", ()):
                point = outcome.get("point")
                rows = (
                    *rows,
                    PriceRow(
                        event_id=event["id"],
                        sport_key=event["sport_key"],
                        commence_time=event["commence_time"],
                        home_team=event["home_team"],
                        away_team=event["away_team"],
                        bookmaker=bookmaker["key"],
                        bookmaker_last_update=bookmaker["last_update"],
                        market=market["key"],
                        outcome=outcome["name"],
                        point=None if point is None else float(point),
                        price=float(outcome["price"]),
                    ),
                )
    return rows


def flatten_odds(payload: list[dict[str, Any]]) -> tuple[PriceRow, ...]:
    rows: tuple[PriceRow, ...] = ()
    for event in payload:
        rows = (*rows, *_rows_for_event(event))
    return rows


def read_quota(headers: Mapping[str, str]) -> Quota:
    return Quota(
        remaining=int(headers["x-requests-remaining"]),
        used=int(headers["x-requests-used"]),
        last_cost=int(headers["x-requests-last"]),
    )


def guard_quota(quota: Quota, min_remaining: int) -> None:
    if quota.remaining < min_remaining:
        raise QuotaExhausted(f"kalan kredi {quota.remaining} < eşik {min_remaining}")


def fetch_odds(
    client: httpx.Client,
    api_key: str,
    sport_key: str,
    *,
    regions: str = "eu",
    markets: str = "h2h",
    commence_time_to: str | None = None,
) -> tuple[tuple[PriceRow, ...], Quota]:
    params: dict[str, str] = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }
    if commence_time_to is not None:
        params["commenceTimeTo"] = commence_time_to

    response = client.get(f"{BASE_URL}/sports/{sport_key}/odds", params=params, timeout=30.0)
    response.raise_for_status()
    return flatten_odds(response.json()), read_quota(response.headers)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_odds_api.py -v`
Expected: 9 PASS

- [ ] **Step 5: Run the gate and commit**

```bash
./verify.sh
git add src/football_edge/odds_api.py tests/test_odds_api.py
git commit -m "feat: The Odds API istemcisi, düzleştirme ve kota koruması"
```

---

### Task 4: Hash zinciri

**Files:**
- Create: `src/football_edge/ledger.py`, `tests/test_ledger.py`

**Interfaces:**
- Consumes: yok
- Produces:
  - `GENESIS: str` (64 karakter sıfır)
  - `row_hash(prev_hash: str, payload: dict[str, Any]) -> str`
  - `chain(payloads: tuple[dict, ...], prev_hash: str = GENESIS) -> tuple[dict, ...]` — her sözlüğe `prev_hash` ve `row_hash` ekler
  - `verify_chain(rows: tuple[dict, ...], start_hash: str = GENESIS) -> ChainResult`
  - `ChainResult` frozen dataclass: `ok: bool, checked: int, head: str, error: str | None, failed_index: int | None`

- [ ] **Step 1: Write the failing test**

`tests/test_ledger.py`:
```python
from __future__ import annotations

from typing import Any

from football_edge.ledger import GENESIS, chain, row_hash, verify_chain

PAYLOADS: tuple[dict[str, Any], ...] = (
    {"event_id": "a", "bookmaker": "pinnacle", "price": 1.95},
    {"event_id": "a", "bookmaker": "betfair_ex_eu", "price": 1.97},
    {"event_id": "b", "bookmaker": "pinnacle", "price": 2.40},
)


def test_row_hash_is_deterministic() -> None:
    assert row_hash(GENESIS, PAYLOADS[0]) == row_hash(GENESIS, PAYLOADS[0])


def test_row_hash_ignores_key_order() -> None:
    reordered = {"price": 1.95, "bookmaker": "pinnacle", "event_id": "a"}
    assert row_hash(GENESIS, PAYLOADS[0]) == row_hash(GENESIS, reordered)


def test_row_hash_changes_with_content() -> None:
    altered = {**PAYLOADS[0], "price": 1.96}
    assert row_hash(GENESIS, PAYLOADS[0]) != row_hash(GENESIS, altered)


def test_row_hash_changes_with_prev_hash() -> None:
    assert row_hash(GENESIS, PAYLOADS[0]) != row_hash("f" * 64, PAYLOADS[0])


def test_chain_links_rows() -> None:
    rows = chain(PAYLOADS)
    assert rows[0]["prev_hash"] == GENESIS
    assert rows[1]["prev_hash"] == rows[0]["row_hash"]
    assert rows[2]["prev_hash"] == rows[1]["row_hash"]


def test_chain_does_not_mutate_input() -> None:
    original = {**PAYLOADS[0]}
    chain(PAYLOADS)
    assert PAYLOADS[0] == original
    assert "row_hash" not in PAYLOADS[0]


def test_verify_accepts_intact_chain() -> None:
    result = verify_chain(chain(PAYLOADS))
    assert result.ok is True
    assert result.checked == 3
    assert result.error is None


def test_verify_detects_edited_value() -> None:
    rows = list(chain(PAYLOADS))
    rows[1] = {**rows[1], "price": 9.99}
    result = verify_chain(tuple(rows))
    assert result.ok is False
    assert result.failed_index == 1
    assert "içerik" in (result.error or "")


def test_verify_detects_deleted_row() -> None:
    rows = chain(PAYLOADS)
    result = verify_chain((rows[0], rows[2]))
    assert result.ok is False
    assert result.failed_index == 1


def test_verify_resumes_from_known_head() -> None:
    first = chain(PAYLOADS[:2])
    head = first[-1]["row_hash"]
    second = chain(PAYLOADS[2:], prev_hash=head)
    assert verify_chain(second, start_hash=head).ok is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ledger.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.ledger'`

- [ ] **Step 3: Write minimal implementation**

`src/football_edge/ledger.py`:
```python
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

GENESIS = "0" * 64
_CHAIN_KEYS = frozenset({"prev_hash", "row_hash", "id"})


@dataclass(frozen=True)
class ChainResult:
    ok: bool
    checked: int
    head: str
    error: str | None = None
    failed_index: int | None = None


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def row_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(payload)).encode("utf-8")).hexdigest()


def chain(
    payloads: tuple[dict[str, Any], ...], prev_hash: str = GENESIS
) -> tuple[dict[str, Any], ...]:
    rows: tuple[dict[str, Any], ...] = ()
    current = prev_hash
    for payload in payloads:
        digest = row_hash(current, payload)
        rows = (*rows, {**payload, "prev_hash": current, "row_hash": digest})
        current = digest
    return rows


def verify_chain(rows: tuple[dict[str, Any], ...], start_hash: str = GENESIS) -> ChainResult:
    current = start_hash
    for index, row in enumerate(rows):
        payload = {key: value for key, value in row.items() if key not in _CHAIN_KEYS}
        if row["prev_hash"] != current:
            return ChainResult(False, index, current, "prev_hash zincire uymuyor", index)
        expected = row_hash(current, payload)
        if row["row_hash"] != expected:
            return ChainResult(False, index, current, "row_hash içerikle uyuşmuyor", index)
        current = row["row_hash"]
    return ChainResult(True, len(rows), current)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ledger.py -v`
Expected: 10 PASS

- [ ] **Step 5: Run the gate and commit**

```bash
./verify.sh
git add src/football_edge/ledger.py tests/test_ledger.py
git commit -m "feat: hash zinciri hesaplama ve kurcalama tespiti"
```

---

### Task 5: Veritabanı şeması ve append-only zorlaması

**Files:**
- Create: `db/migrations/0001_init.sql`, `src/football_edge/db.py`, `tests/test_db.py`

**Interfaces:**
- Consumes: `PriceRow` (Task 3), `chain`/`GENESIS` (Task 4)
- Produces:
  - `connect(dsn: str | None = None) -> psycopg.Connection`
  - `snapshot_payload(row: PriceRow, observed_at: datetime, *, is_closing: bool) -> dict[str, Any]`
  - `chain_head(conn) -> str`
  - `upsert_matches(conn, rows: tuple[PriceRow, ...], league_id: str) -> int`
  - `insert_snapshots(conn, rows: tuple[PriceRow, ...], observed_at: datetime, *, is_closing: bool) -> int`

**Not:** Supabase projesi **zaten oluşturuldu** — `football-edge`, ref `aaxadphezxavohkhqdrf`,
bölge `eu-central-1`, durum `ACTIVE_HEALTHY`. Yeniden oluşturma.

**Bağlantı tuzağı — bunu baştan doğru yap:**
- Supabase'in **doğrudan** bağlantısı (`db.<ref>.supabase.co:5432`) yalnız **IPv6** üzerinden
  erişilebilir. GitHub Actions runner'ları IPv4'tür → doğrudan bağlantı CI'da çalışmaz.
- Bu yüzden `DATABASE_URL` **pooler** ana makinesini kullanmalı:
  `aws-0-eu-central-1.pooler.supabase.com`. Kullanıcı adı `postgres.<ref>` biçimindedir.
- **Session pooler (port 5432)** tercih edilir: hazırlanmış ifadelerle (prepared statements)
  sorun çıkarmaz. **Transaction pooler (port 6543)** kullanılacaksa psycopg3'ün hazırlanmış
  ifadeleri kapatılmalıdır (`prepare_threshold=None`), aksi hâlde birkaç çağrıdan sonra
  beklenmedik hatalar başlar.
- Bağlantı dizesi Supabase panelinden alınır (Project Settings → Database → Connection string);
  parola MCP üzerinden okunamaz.

- [ ] **Step 1: Write the failing test**

`tests/test_db.py` — saf yardımcıları DB'siz test eder; şema testleri `DATABASE_URL` varsa koşar:
```python
from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from football_edge.db import snapshot_payload
from football_edge.odds_api import PriceRow

ROW = PriceRow(
    event_id="abc123",
    sport_key="soccer_epl",
    commence_time="2026-09-20T14:00:00Z",
    home_team="Arsenal",
    away_team="Chelsea",
    bookmaker="pinnacle",
    bookmaker_last_update="2026-09-19T10:00:00Z",
    market="h2h",
    outcome="Arsenal",
    point=None,
    price=1.95,
)
OBSERVED = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def test_snapshot_payload_has_stable_keys() -> None:
    payload = snapshot_payload(ROW, OBSERVED, is_closing=False)
    assert set(payload) == {
        "match_id",
        "observed_at",
        "bookmaker",
        "market",
        "outcome",
        "point",
        "price",
        "bookmaker_last_update",
        "is_closing",
    }


def test_snapshot_payload_serialises_time_as_iso() -> None:
    payload = snapshot_payload(ROW, OBSERVED, is_closing=True)
    assert payload["observed_at"] == "2026-09-19T12:00:00+00:00"
    assert payload["is_closing"] is True
    assert payload["match_id"] == "abc123"


def test_snapshot_payload_excludes_chain_fields() -> None:
    payload = snapshot_payload(ROW, OBSERVED, is_closing=False)
    assert "row_hash" not in payload
    assert "prev_hash" not in payload


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL yok")
def test_append_only_trigger_blocks_update() -> None:
    import psycopg

    from football_edge.db import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM odds_snapshots LIMIT 1")
        found = cur.fetchone()
        if found is None:
            pytest.skip("defter boş")
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            cur.execute("UPDATE odds_snapshots SET price = 9.99 WHERE id = %s", (found[0],))


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL yok")
def test_append_only_trigger_blocks_delete() -> None:
    import psycopg

    from football_edge.db import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM odds_snapshots LIMIT 1")
        found = cur.fetchone()
        if found is None:
            pytest.skip("defter boş")
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            cur.execute("DELETE FROM odds_snapshots WHERE id = %s", (found[0],))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.db'` (DB testleri skip)

- [ ] **Step 3: Write the migration**

`db/migrations/0001_init.sql`:
```sql
-- Faz 0 şeması: append-only oran defteri.

create table if not exists leagues (
  id            text primary key,
  odds_api_key  text not null unique,
  name          text not null,
  country       text not null,
  lang          text not null,
  gl            text not null,
  active        boolean not null default true
);

create table if not exists matches (
  id             text primary key,          -- The Odds API event id
  league_id      text not null references leagues(id),
  commence_time  timestamptz not null,
  home_team      text not null,
  away_team      text not null,
  first_seen_at  timestamptz not null default now(),
  sealed_at      timestamptz
);

create index if not exists matches_commence_idx on matches (commence_time);
create index if not exists matches_league_idx on matches (league_id);

create table if not exists odds_snapshots (
  id                     bigserial primary key,
  match_id               text not null references matches(id),
  observed_at            timestamptz not null,
  bookmaker              text not null,
  market                 text not null,
  outcome                text not null,
  point                  numeric,
  price                  numeric not null check (price > 1.0),
  bookmaker_last_update  timestamptz,
  is_closing             boolean not null default false,
  prev_hash              text not null,
  row_hash               text not null unique
);

create index if not exists odds_match_idx on odds_snapshots (match_id, observed_at);
create index if not exists odds_closing_idx on odds_snapshots (is_closing) where is_closing;

-- Append-only zorlaması: UPDATE ve DELETE veritabanı seviyesinde reddedilir.
create or replace function forbid_ledger_mutation() returns trigger as $$
begin
  raise exception 'odds_snapshots append-only bir defterdir; % reddedildi', tg_op;
end;
$$ language plpgsql;

drop trigger if exists odds_snapshots_append_only on odds_snapshots;
create trigger odds_snapshots_append_only
  before update or delete on odds_snapshots
  for each row execute function forbid_ledger_mutation();
```

- [ ] **Step 4: Create the Supabase project and apply the migration**

Kullanıcıya doğrula: **yeni Supabase projesi $0/ay** (org `rkwkgvljyppbldscylwf`). Onay alındıktan sonra:
1. Supabase MCP `create_project` ile proje oluştur (ad: `football-edge`, bölge: `eu-central-1`).
2. `db/migrations/0001_init.sql` içeriğini `apply_migration` ile uygula.
3. Bağlantı dizesini yerel `.env` dosyasına `DATABASE_URL=` olarak yaz (`.gitignore`'da, repoya girmez).
4. `config/leagues.yaml` satırlarını `leagues` tablosuna yükle.

- [ ] **Step 5: Write the db module**

`src/football_edge/db.py`:
```python
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import psycopg

from football_edge.ledger import GENESIS, chain
from football_edge.odds_api import PriceRow


def connect(dsn: str | None = None) -> psycopg.Connection[Any]:
    resolved = dsn or os.getenv("DATABASE_URL")
    if not resolved:
        raise RuntimeError("DATABASE_URL tanımlı değil")
    # Oturum saat dilimi UTC'ye sabitlenir: zincir hash'i zaman damgasının
    # metin hâlini kapsıyor, oturum TZ'si değişirse geri okumada zincir kırılır.
    return psycopg.connect(resolved, options="-c timezone=UTC")


def snapshot_payload(row: PriceRow, observed_at: datetime, *, is_closing: bool) -> dict[str, Any]:
    return {
        "match_id": row.event_id,
        "observed_at": observed_at.isoformat(),
        "bookmaker": row.bookmaker,
        "market": row.market,
        "outcome": row.outcome,
        "point": row.point,
        "price": row.price,
        "bookmaker_last_update": row.bookmaker_last_update,
        "is_closing": is_closing,
    }


def chain_head(conn: psycopg.Connection[Any]) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT row_hash FROM odds_snapshots ORDER BY id DESC LIMIT 1")
        found = cur.fetchone()
    return GENESIS if found is None else str(found[0])


def upsert_matches(conn: psycopg.Connection[Any], rows: tuple[PriceRow, ...], league_id: str) -> int:
    seen: dict[str, PriceRow] = {}
    for row in rows:
        seen.setdefault(row.event_id, row)
    with conn.cursor() as cur:
        for event_id, row in seen.items():
            cur.execute(
                """
                INSERT INTO matches (id, league_id, commence_time, home_team, away_team)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (event_id, league_id, row.commence_time, row.home_team, row.away_team),
            )
    return len(seen)


def insert_snapshots(
    conn: psycopg.Connection[Any],
    rows: tuple[PriceRow, ...],
    observed_at: datetime,
    *,
    is_closing: bool,
) -> int:
    payloads = tuple(snapshot_payload(row, observed_at, is_closing=is_closing) for row in rows)
    linked = chain(payloads, prev_hash=chain_head(conn))
    with conn.cursor() as cur:
        for entry in linked:
            cur.execute(
                """
                INSERT INTO odds_snapshots
                  (match_id, observed_at, bookmaker, market, outcome, point, price,
                   bookmaker_last_update, is_closing, prev_hash, row_hash)
                VALUES (%(match_id)s, %(observed_at)s, %(bookmaker)s, %(market)s, %(outcome)s,
                        %(point)s, %(price)s, %(bookmaker_last_update)s, %(is_closing)s,
                        %(prev_hash)s, %(row_hash)s)
                ON CONFLICT (row_hash) DO NOTHING
                """,
                entry,
            )
    return len(linked)
```

- [ ] **Step 6: Run tests and the append-only proof**

Run: `uv run pytest tests/test_db.py -v`
Expected: `DATABASE_URL` yoksa 3 PASS + 2 SKIP. Ayarlıysa ve defterde en az bir satır varsa 5 PASS.

**UPDATE ve DELETE'in gerçekten reddedildiğini gözünle gör** — bu Faz 0'ın asıl iddiası ve SKIP geçmek değildir.

- [ ] **Step 7: Run the gate and commit**

```bash
./verify.sh
git add db/migrations/0001_init.sql src/football_edge/db.py tests/test_db.py
git commit -m "feat: append-only defter şeması ve hash-zincirli yazma"
```

---

### Task 6: `snapshot` ve `seal` komutları

**Files:**
- Create: `src/football_edge/collect.py`, `tests/test_collect.py`

**Interfaces:**
- Consumes: `load_leagues`/`active_leagues` (Task 2), `fetch_odds`/`guard_quota`/`QuotaExhausted` (Task 3), `verify_chain` (Task 4), `connect`/`chain_head`/`upsert_matches`/`insert_snapshots` (Task 5)
- Produces:
  - `horizon_iso(now: datetime, days: int) -> str`
  - `seal_window(commence_time: datetime, now: datetime, minutes: int) -> bool`
  - `run_snapshot(conn, client, api_key, leagues, now, *, horizon_days=7, min_remaining=10) -> tuple[int, Quota | None]`
  - `run_seal(conn, client, api_key, leagues, now, *, window_minutes=20, min_remaining=5) -> tuple[int, Quota | None]`
  - CLI: `python -m football_edge.collect snapshot|seal|verify-chain|publish-head`

- [ ] **Step 1: Write the failing test**

`tests/test_collect.py`:
```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from football_edge.collect import horizon_iso, seal_window

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def test_seal_window_true_just_before_kickoff() -> None:
    assert seal_window(NOW + timedelta(minutes=10), NOW, minutes=20) is True


def test_seal_window_false_when_far_away() -> None:
    assert seal_window(NOW + timedelta(hours=5), NOW, minutes=20) is False


def test_seal_window_false_after_kickoff() -> None:
    assert seal_window(NOW - timedelta(minutes=1), NOW, minutes=20) is False


def test_seal_window_true_at_exact_boundary() -> None:
    assert seal_window(NOW + timedelta(minutes=20), NOW, minutes=20) is True


def test_horizon_iso_formats_utc_with_z() -> None:
    assert horizon_iso(NOW, days=7) == "2026-09-26T12:00:00Z"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.collect'`

- [ ] **Step 3: Write minimal implementation**

`src/football_edge/collect.py`:
```python
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import psycopg

from football_edge.db import chain_head, connect, insert_snapshots, upsert_matches
from football_edge.leagues import League, active_leagues, load_leagues
from football_edge.ledger import verify_chain
from football_edge.odds_api import Quota, QuotaExhausted, fetch_odds, guard_quota

LOGGER = logging.getLogger("football_edge.collect")
LEAGUES_PATH = Path("config/leagues.yaml")


def horizon_iso(now: datetime, days: int) -> str:
    return (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def seal_window(commence_time: datetime, now: datetime, minutes: int) -> bool:
    delta = commence_time - now
    return timedelta(0) <= delta <= timedelta(minutes=minutes)


def _collect(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    commence_time_to: str,
    is_closing: bool,
    min_remaining: int,
) -> tuple[int, Quota | None]:
    written = 0
    quota: Quota | None = None
    for league in leagues:
        if quota is not None:
            guard_quota(quota, min_remaining)
        rows, quota = fetch_odds(
            client, api_key, league.odds_api_key, commence_time_to=commence_time_to
        )
        if not rows:
            LOGGER.info("lig=%s maç yok", league.id)
            continue
        upsert_matches(conn, rows, league.id)
        written += insert_snapshots(conn, rows, now, is_closing=is_closing)
        conn.commit()
        LOGGER.info("lig=%s satır=%d kalan_kredi=%d", league.id, len(rows), quota.remaining)
    return written, quota


def run_snapshot(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    horizon_days: int = 7,
    min_remaining: int = 10,
) -> tuple[int, Quota | None]:
    return _collect(
        conn,
        client,
        api_key,
        leagues,
        now,
        commence_time_to=horizon_iso(now, horizon_days),
        is_closing=False,
        min_remaining=min_remaining,
    )


def _leagues_due_for_seal(
    conn: psycopg.Connection[Any], leagues: tuple[League, ...], now: datetime, window_minutes: int
) -> tuple[League, ...]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT league_id, commence_time FROM matches
            WHERE sealed_at IS NULL AND commence_time > %s - interval '1 day'
            """,
            (now,),
        )
        candidates = tuple((str(record[0]), record[1]) for record in cur.fetchall())
    due = {
        league_id
        for league_id, commence_time in candidates
        if seal_window(commence_time, now, window_minutes)
    }
    return tuple(league for league in leagues if league.id in due)


def run_seal(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    api_key: str,
    leagues: tuple[League, ...],
    now: datetime,
    *,
    window_minutes: int = 20,
    min_remaining: int = 5,
) -> tuple[int, Quota | None]:
    due = _leagues_due_for_seal(conn, leagues, now, window_minutes)
    if not due:
        LOGGER.info("mühürlenecek maç yok")
        return 0, None
    written, quota = _collect(
        conn,
        client,
        api_key,
        due,
        now,
        commence_time_to=horizon_iso(now, 1),
        is_closing=True,
        min_remaining=min_remaining,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE matches SET sealed_at = %s
            WHERE sealed_at IS NULL AND commence_time BETWEEN %s AND %s
            """,
            (now, now, now + timedelta(minutes=window_minutes)),
        )
    conn.commit()
    return written, quota


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} tanımlı değil")
    return value


def _verify_chain_command(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT match_id, observed_at, bookmaker, market, outcome, point, price,
                   bookmaker_last_update, is_closing, prev_hash, row_hash
            FROM odds_snapshots ORDER BY id
            """
        )
        columns = [desc[0] for desc in cur.description or ()]
        records = tuple(dict(zip(columns, record, strict=True)) for record in cur.fetchall())

    normalised = tuple(
        {
            **record,
            "observed_at": record["observed_at"].isoformat(),
            "bookmaker_last_update": (
                record["bookmaker_last_update"].strftime("%Y-%m-%dT%H:%M:%SZ")
                if record["bookmaker_last_update"] is not None
                else None
            ),
            "point": None if record["point"] is None else float(record["point"]),
            "price": float(record["price"]),
        }
        for record in records
    )
    result = verify_chain(normalised)
    sys.stdout.write(
        f"zincir: {'SAĞLAM' if result.ok else 'KIRIK'} "
        f"kontrol={result.checked} baş={result.head[:16]} hata={result.error}\n"
    )
    return 0 if result.ok else 1


def _publish_head_command(conn: psycopg.Connection[Any], now: datetime) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM odds_snapshots")
        count = int((cur.fetchone() or (0,))[0])
    head = chain_head(conn)
    target = Path("ledger") / f"head-{now:%Y-%m-%d}.txt"
    target.parent.mkdir(exist_ok=True)
    target.write_text(f"{now.isoformat()}\nrows={count}\nhead={head}\n", encoding="utf-8")
    sys.stdout.write(f"zincir başı yazıldı: {target}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="football-edge")
    parser.add_argument("command", choices=("snapshot", "seal", "verify-chain", "publish-head"))
    args = parser.parse_args(argv)

    now = datetime.now(UTC)

    with connect() as conn:
        if args.command == "verify-chain":
            return _verify_chain_command(conn)
        if args.command == "publish-head":
            return _publish_head_command(conn, now)

        leagues = active_leagues(load_leagues(LEAGUES_PATH))
        api_key = _require_env("ODDS_API_KEY")
        with httpx.Client() as client:
            try:
                # Ayrı if/else: run_snapshot ve run_seal farklı keyword argümanlara
                # sahip, tek değişkene atanınca mypy --strict uyumsuzluk bildirir.
                if args.command == "snapshot":
                    written, quota = run_snapshot(conn, client, api_key, leagues, now)
                else:
                    written, quota = run_seal(conn, client, api_key, leagues, now)
            except QuotaExhausted:
                LOGGER.exception("kredi tükendi, iş durduruldu")
                return 2
        remaining = "bilinmiyor" if quota is None else str(quota.remaining)
        sys.stdout.write(f"yazılan satır: {written}, kalan kredi: {remaining}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collect.py -v`
Expected: 5 PASS

- [ ] **Step 5: Run the gate and commit**

```bash
./verify.sh
git add src/football_edge/collect.py tests/test_collect.py
git commit -m "feat: snapshot, seal, verify-chain ve publish-head komutları"
```

---

### Task 7: GitHub Actions ve dış çıpa

**Files:**
- Create: `.github/workflows/snapshot.yml`, `.github/workflows/seal.yml`, `ledger/.gitkeep`

**Interfaces:**
- Consumes: `python -m football_edge.collect` CLI (Task 6)
- Produces: iki zamanlanmış iş; `ledger/head-YYYY-MM-DD.txt` public repoya yazılır.

**DİKKAT:** Bu görev bir GitHub deposu ve uzak repoya yazma gerektirir. `outward_action_gate` bunu engeller — **kullanıcıdan açık onay alınmadan uzak repoya yazma.** Gerekli repository secret'ları: `ODDS_API_KEY`, `DATABASE_URL`.

- [ ] **Step 1: Write the snapshot workflow**

`.github/workflows/snapshot.yml`:
```yaml
name: snapshot

on:
  schedule:
    # 03:00, 09:00, 15:00, 21:00 UTC — maç öncesi periyodik tarama
    - cron: "0 3,9,15,21 * * *"
  workflow_dispatch:

concurrency:
  group: odds-collect
  cancel-in-progress: false

jobs:
  snapshot:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.11"
      - run: uv sync --frozen
      - name: Oranları çek
        env:
          ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: uv run python -m football_edge.collect snapshot
```

- [ ] **Step 2: Write the seal workflow**

`.github/workflows/seal.yml` — mühürleme, zincir doğrulama ve dış çıpa yayını:
```yaml
name: seal

on:
  schedule:
    # Her 15 dakikada bir: başlamak üzere olan maçların kapanış oranını mühürle.
    - cron: "*/15 * * * *"
  workflow_dispatch:

concurrency:
  group: odds-collect
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  seal:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.11"
      - run: uv sync --frozen
      - name: Kapanışı mühürle
        env:
          ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: uv run python -m football_edge.collect seal
      - name: Zinciri doğrula
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: uv run python -m football_edge.collect verify-chain
      - name: Zincir başını yayınla
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: uv run python -m football_edge.collect publish-head
      - name: Dış çıpayı commit'le
        run: |
          git config user.name "football-edge-bot"
          git config user.email "bot@users.noreply.github.com"
          git add ledger/
          git diff --cached --quiet || git commit -m "chore: zincir başı $(date -u +%F)"
          git -c http.version=HTTP/1.1 push origin HEAD
```

- [ ] **Step 3: Verify the workflows are syntactically valid**

Run: `uv run python -c "import yaml,pathlib; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('yaml gecerli')"`
Expected: `yaml gecerli`

- [ ] **Step 4: Create the ledger directory**

```bash
mkdir -p ledger && touch ledger/.gitkeep
```

- [ ] **Step 5: Commit yerelde — uzak repoya YAZMA**

```bash
git add .github ledger
git commit -m "ci: snapshot ve seal zamanlanmış işleri, dış çıpa yayını"
```

**DUR.** GitHub deposu oluşturma, uzak repoya yazma ve secret ekleme kullanıcı onayı gerektirir.
Bu adımları kullanıcıya anlat ve onay iste; kendi başına yapma.

---

### Task 8: Uçtan uca doğrulama ve handoff

**Files:**
- Create: `docs/phases/00-kayit-altyapisi/HANDOFF.md`
- Modify: `verify.sh` (zincir doğrulamayı kapıya ekle)

**Interfaces:**
- Consumes: hepsi
- Produces: Faz 0'ın bittiğini kanıtlayan çıktı + Faz 1 için handoff.

- [ ] **Step 1: Add chain verification to the gate**

`verify.sh` içinde `step "pytest" ...` satırından sonra ekle:
```bash
if [ -n "${DATABASE_URL:-}" ]; then
  step "zincir" uv run python -m football_edge.collect verify-chain
else
  echo "SKIP: zincir (DATABASE_URL yok)" | tee -a "$LOG"
fi
```

**Not:** `SKIP` geçmek değildir. Handoff'ta hangi kontrolün atlandığı adıyla yazılır.

- [ ] **Step 2: Run a real snapshot against the free tier**

```bash
export ODDS_API_KEY=... DATABASE_URL=...
uv run python -m football_edge.collect snapshot
```
Beklenen: `yazılan satır: N, kalan kredi: M` — N > 0 ve M, başlangıçtaki krediden `aktif lig sayısı` kadar az olmalı (her lig 1 kredi: `markets=h2h` × `regions=eu`).

- [ ] **Step 3: Prove the ledger is append-only**

```bash
uv run pytest tests/test_db.py -v -k "append_only"
```
Beklenen: 2 PASS. **Bu Faz 0'ın merkezi iddiası — SKIP kabul edilmez.**

- [ ] **Step 4: Prove the chain is intact**

```bash
uv run python -m football_edge.collect verify-chain
```
Beklenen: `zincir: SAĞLAM`

- [ ] **Step 5: Run the full gate**

```bash
./verify.sh
```
Beklenen: `KAPI YEŞİL`. Log dosyasını aç ve her adımın gerçekten koştuğunu gör — özet yeterli değil.

- [ ] **Step 6: Write the handoff**

`docs/phases/00-kayit-altyapisi/HANDOFF.md` şunları içermeli:
- **Ne bitti:** şema, toplayıcı, mühürleme, zincir, kapı, workflow'lar.
- **Kapı ne ölçtü:** ruff, ruff-format, mypy, pytest (N test), zincir doğrulama, append-only tetikleyici.
- **Kapının ÖLÇMEDİĞİ:** (a) GitHub Actions gerçekten koştu mu — uzak repo onayı beklemedeyse ölçülmedi; (b) kapanış mührünün gerçek maç saatiyle hizası canlı maçta doğrulanmadı; (c) `odds_api_key` değerleri `/v4/sports` çıktısına karşı doğrulanmadı; (d) kredi tüketiminin aylık bütçeye oturduğu tam bir ay boyunca gözlenmedi.
- **Faz 1 ön koşulları:** çalışan `DATABASE_URL`, en az 7 günlük anlık görüntü birikimi, doğrulanmış lig anahtarları.
- **Açık sorular:** spec §10'dan devredilenler.

- [ ] **Step 7: Commit**

```bash
git add verify.sh docs/phases
git commit -m "chore: zincir doğrulama kapıya eklendi, Faz 0 handoff"
```
