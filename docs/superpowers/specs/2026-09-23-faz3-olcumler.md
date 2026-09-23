# Faz 3 — Gerçek veri ölçümleri

Plan: `docs/superpowers/plans/2026-09-23-faz3-model-walkforward.md`. Her ölçüm komutuyla yazılır; holdout
anahtarsız okunamaz (`load_matches` yalnız DEV + sonrası döner). Ham üçüncü taraf içeriği yok, yalnız sayı.

## Task 0 (dalga 0) — 2026-09-23, yerel (macOS), `main` `5580a7e` + dalga 0 yaması

| Ölçüm | Sonuç |
|---|---|
| §3/37 saatsiz 2019/20+ ana lig satırı (DEV) | **0** |
| 14g yinelenen `(lig, tarih, ev, deplasman)`, DEV + sonrası | **0** |
| Yükleme süresi / tepe RSS | 10,1 sn · ~735 MB |

Sonuç: yineleme 0 → Task 4'ün `DuplicateMatch`i gerçek veride oynatmayı düşürmez; dalga 1 başlar. §3/37
kapanır: 2019/20 ve sonrasında ana liglerde saatsiz satır yok (saatsiz satırlar yalnız ≤ 2018/19 sezonlarında,
ana liglerde toplam 108.885 — sezon biçimi `"1920"`, dizge karşılaştırması bu yüzden doğru).

Komut (plan Task 0 Step 5, aynen; `/usr/bin/time -l` ile):

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

Kapı: `verify.sh` 10 PASS + `SKIP: zincir (DATABASE_URL yok)`; pytest 1.553 passed / 2 skipped (taban değişmedi).
Mutasyon: `"scipy>=1.14",` çıkarılıp `uv sync` → `FAIL: paket-kurulu`, `KAPI KIRMIZI`; geri alındı. (`mypy`
bu anda kırmızı olmaz: `src`de henüz scipy içe alan modül yok.) `uv.lock`: scipy 1.17.1 (Python 3.11) ve
1.18.1 (daha yeni Python işaretleri için).

## Task 5 (dalga 1 sonu) — 2026-09-23, yerel (macOS), dalga 1 birleşmiş `main`

| Ölçüm | Sonuç |
|---|---|
| `leakage` etiketli test | **269** (265 + Task 1 · 2 · 4'ün 1 + 1 + 2'si) → `EXPECTED_MIN_LEAKAGE=269` |
| İngiltere grubu (en büyük), DEV maç sayısı | 51.138 |
| Elo replay (İngiltere, DEV, varsayılan yapılandırma) | 1,4 sn |
| Dixon-Coles fiti (1095 gün pencere, 4 karar günü ortalaması) | **0,02 sn/fit**; dördü de yakınsadı (124–126 takım, ev 0,25–0,30, ρ −0,025…−0,003) |
| Tepe RSS | ~719 MB (yükleme baskın) |
| Derecelendirme grubu | 27 |

**Kadans kararı (P18, plan Task 5 Step 3 kuralı):** üst sınır kestirimi — 27 grubun hepsi İngiltere kadar büyük
sayılırsa, S + E ≈ 13 sezon × 52 hafta × 2 karar günü ≈ 1.350 fit/grup × 0,02 sn × 27 ≈ **12 dk** (H2H ve Ü/A
aynı memo'yu paylaşır). 45 dk'nın altında → **`cadence_days = 1`**. Seçimin ızgarası (DC ξ × sırt) bu süreyi aday
başına yineler; gerçek süre Task 9'da ölçülür (P17 eşiği 90 dk).

Mutasyon: `tests/test_dixon_coles.py`den bir `@pytest.mark.leakage` çıkarıldı → `FAIL: sızıntı`, `KAPI KIRMIZI`;
geri alındı.

Komut (plan Task 5 Step 3, aynen), ayrıca yakınsama denetimi için aynı dört günde `fit(...)` dönüşünün takım
sayısı, ev ve ρ değerleri yazdırıldı.
