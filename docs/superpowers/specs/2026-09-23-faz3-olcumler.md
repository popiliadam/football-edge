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

## Task 9 (dalga 3 sonu) — 2026-09-23, yerel (macOS), dalga 3 birleşmiş `main`

| Ölçüm | Sonuç |
|---|---|
| `leakage` etiketli test | **287** → `EXPECTED_MIN_LEAKAGE=287` |
| `select --cadence-days 1` (yalnız S) | exit 0 · **200 sn** · tepe RSS ~608 MB · 19 aday (Elo 14, DC 5) |
| `walkforward --gap` | exit 0 · **205 sn** · tepe RSS ~1.108 MB |
| `walkforward` (`--gap`siz, belirlenimcilik için ikinci koşu) | exit 0; satır özeti iki koşuda aynı: `b346641b…e98a2` |
| Rapordaki takım adı | `[]` |

P17: `walkforward` 90 dk'nın çok altında → Task 12 başlayabilir.

**Seçilen yapılandırma** (`config/model_faz3.yaml`): Elo k = 10, ev avantajı 65, marj doğrusal, dönüş 0,2,
yeni takım farkı 75, beraberlik biçimi **ordered** (s = 1,0672, c = 0,5952); Dixon-Coles ξ = 0,003, sırt = 0,003,
pencere 1095 gün.

**Bulgu — ızgara ucu (plan Task 9 Step 2):** Elo `k = 10` (alt uç), DC `ξ = 0.003` (üst uç) ve DC
`sırt = 0.003` (alt uç) seçildi. Izgara bu fazda GENİŞLETİLMEDİ (genişletmek S'de ikinci bir aramadır, yeni bir
seçimdir); karar kullanıcıya bırakılır (Faz 3 HANDOFF).

**Seçimin izi** (yalnız parametreler ve S log loss'ları):

```
aday elo {'k': 20.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.0, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.030316
aday elo {'k': 10.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.0, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.026611
aday elo {'k': 15.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.0, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.027632
aday elo {'k': 25.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.0, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.033895
aday elo {'k': 30.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.0, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.038041
aday elo {'k': 10.0, 'home_advantage': 40.0, 'margin': 'linear', 'regress': 0.0, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.028091
aday elo {'k': 10.0, 'home_advantage': 90.0, 'margin': 'linear', 'regress': 0.0, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.031997
aday elo {'k': 10.0, 'home_advantage': 65.0, 'margin': 'none', 'regress': 0.0, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.028094
aday elo {'k': 10.0, 'home_advantage': 65.0, 'margin': 'log', 'regress': 0.0, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.026738
aday elo {'k': 10.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.2, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.026492
aday elo {'k': 10.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.4, 'newcomer_offset': 0.0, 'draw_form': 'quadratic'} → S log loss 1.029325
aday elo {'k': 10.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.2, 'newcomer_offset': 75.0, 'draw_form': 'quadratic'} → S log loss 1.025651
aday elo {'k': 10.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.2, 'newcomer_offset': 150.0, 'draw_form': 'quadratic'} → S log loss 1.029532
aday elo {'k': 10.0, 'home_advantage': 65.0, 'margin': 'linear', 'regress': 0.2, 'newcomer_offset': 75.0, 'draw_form': 'ordered'} → S log loss 1.025586
aday dixon_coles {'xi': 0.0019, 'ridge': 0.01} → S log loss 1.027380
aday dixon_coles {'xi': 0.001, 'ridge': 0.01} → S log loss 1.029152
aday dixon_coles {'xi': 0.003, 'ridge': 0.01} → S log loss 1.026342
aday dixon_coles {'xi': 0.003, 'ridge': 0.003} → S log loss 1.024430
aday dixon_coles {'xi': 0.003, 'ridge': 0.03} → S log loss 1.032715
```

**E raporunun okunması (Step 5):** W1'in ham hâli ΔLL(harman − piyasa) = 0,0002 [0,0000, 0,0005]; üst uç
δ = 0,001'in altında → revizyon yok, E örneklem dışı kalır. Diğer gözlemler (bulgu, kapı değil):
- Ü/A 2.5'te piyasa satırı **1 bahis**, CLV 0,7493 — kendi fiyatına karşı bahis yapmaması gereken bir strateji;
  tek bir satırda tutarsız (toplamı 1'in altında) Ü/A fiyatı olduğunu gösterir. Toplu sayı; maç satırı
  raporlanmaz. Veri kusuru olarak ölçmedikleri listesine.
- Dixon-Coles'un Ü/A kalibrasyonu zayıf: eğim b = 0,633, ECE 0,0247 (aşırı özgüvenli).
- Boşluk cezası (R128, DEV simülasyonu): Elo 0,0034 [0,0013, 0,0055], DC 0,0064 [0,0034, 0,0094] — bir sezon
  eksik girdinin maliyeti; holdout yılının canlı maliyeti için alt sınır tahmini.

## Dalga 4 sonu — 2026-09-23, canlı veritabanı

| Ölçüm | Sonuç |
|---|---|
| `leakage` etiketli test | **336** (plan 334 + Task 10 düzeltme turunun 2 testi) → `EXPECTED_MIN_LEAKAGE=336` |
| I6: `tests/test_holdout_phase_db.py` 0010 ÖNCESİ | **FAIL** — "ikinci faz99 açılışı kabul edildi" |
| 0009 · 0010 · 0011 (`apply_migration`) | uygulandı; `holdout_access_log` = 0; indeks `split_part(purpose, ':'::text, 1)`; `model_predictions` iki tetikleyici (`_append_only`, `_no_truncate`), RLS `true`; `shadow-dispatch` (`35 12 * * 2,5`), `history-dispatch` (`50 9 * * 2`), `history-dispatch-friday` (`50 9 * * 5`) active |
| I6: aynı test 0010 SONRASI | **1 passed**; ardından `holdout_access_log` = 0 |
| `DATABASE_URL` bağlı tam kapı | **11/11** |
| Anahtarsız `load_matches` (Task 10'un bütün dönemlerde yineleme reddiyle) | red yok, 38 lig — holdout'ta yineleme yok (C1 gerçek veride kapalı) |
| İlk gölge turu (`shadow.yml`, run 35835173227, çarşamba) | yeşil; `karar 0 · yazılan satır 0 · eşlenemeyen 27 · bayat durum 0 · fiyatsız 0` (karar günü değil) |
| E3 (`live parity`) takma adlardan ÖNCE | eşleşen 23 · eşlenemeyen 28 · sezon farkı 0 · başlama farkı 0 |
| E3 38 takma addan SONRA | **eşleşen 50 · eşlenemeyen 1 · sezon farkı 0 · başlama farkı 0**; kalan 1: tabanda henüz olmayan bir T1 maçı (2026-09-20) |

Takma adlar (`config/history_aliases.yaml`, 38 çift) TAHMİN edilmedi: her canlı ad, aynı gün ve aynı lig
dosyasında, aynı ev/deplasman konumundaki TEK football-data satırından okundu (öteki taraf zaten eşlenmiş ya da
günün eşlenmemiş tek satırı). ned.1 ve bel.1'in canlı maçı bu pencerede yoktu (milli ara) — onların `Date`
eşleşmesi ilk maç haftasından sonra ölçülür; AUT kapalı (§3/38 AUT için açık).
