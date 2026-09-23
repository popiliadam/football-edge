# Faz 3 sızıntı denetimi — kırmızı takım (2026-09-23)

## Kapsam ve yöntem

- **Commit:** `c129cc3` (main). Kod `git archive` ile izole kopyaya çıkarıldı; `uv sync`; her koşu
  `PYTHONDONTWRITEBYTECODE=1`.
- **Yasaklar (uyuldu):** `open_holdout` çağrılmadı; `final-eval` yalnız kodu okunarak incelendi, `--rehearse`siz
  koşulmadı; `run_final` gerçek bağlantıya verilmedi; DB/`.env`/ağ yok; depo değiştirilmedi.
- **Yöntem:** her şüphe için sentetik veriyle (`tests/model_builders.py`, `tests/backtest_builders.py`) bir deney
  yazıldı ve **koşuldu**: kopyada `tests/test_redteam.py` (33 deney, 33 geçti, 11 sn; depoya girmedi). Her deney
  "sızıntı yok" demeden önce **pozitif kontrol** taşır (aynı deney, sızıntının olması GEREKEN yerde fark görüyor
  mu). Projenin `leakage` süiti kopyada koşuldu: **336 passed** (`verify.sh` alt sınırı 336). `preflight`in git
  davranışı tek kullanımlık bir git deposunda ölçüldü.
- Denetçi: kabuklu `general-purpose` ajan, model fable (plan Task 13 Step 4).

## Özet tablo

| # | Şüphe | Deney | Sonuç | Şiddet |
|---|---|---|---|---|
| 1 | Hiperparametre seçimi E/holdout görüyor mu | `select()` iki kez: E dönemi (≥ 2019-07-01) golleri + sonuçları çevrilmiş vs ham → `(elo, dc, trials)` birebir aynı. Pozitif kontrol: S'nin ikinci yarısı çevrilince `trials` değişiyor | SIZINTI YOK | — |
| 2 | Ağırlık katları (`_training`): sezon `s` kendi/sonraki satırı görüyor mu | G3 testi ve ilk kat S kuralı kopyada yeşil; `row.season < season` dize karşılaştırması 4 haneli ana lig kodlarında (`1213` … `2425`) doğru sıralı; `fold_weights` yalnız `MAIN` | SIZINTI YOK | — |
| 3 | `frozen_weights` holdout/POST görüyor mu; `final_zone` bölgeleme | `evaluate_selected` casusla iki kez (holdout + POST sonuçları çevrilmiş vs ham): satırlar `holdout`/`post` bölgesi taşıyor, dönen ağırlıklar **aynı**; holdout Brier'i değişiyor (pozitif kontrol). `rehearsal_zone`: yalnız 2024/25 `holdout`, E'den düşüyor | SIZINTI YOK | — |
| 4 | DC memo `(grup, fit günü)`: başka maç kümesine sızar mı | Aynı **nesne** önce tam kümeye, sonra 2022/23'ü çıkarılmış kümeye oynatıldı: 2023/24'ün 56/56 tahmini tam kümeninkiyle özdeş (memo isabeti); taze nesne farklı. Üretimde `DixonColesStrategy(` 3 yerde ve hepsi oynatma/slot başına taze (AST taraması; `gap_penalty` ≠ 0) | BULGU (gizil; üretimde tetiklenmiyor) | Minor |
| 5 | Elo/DC `observe` sırası, aynı-an eşitliği | Sonucu **tam** karar anında bilinen maç gözlenmiyor; 1 sn önce → gözleniyor; 1 sn sonra → değil. `observe_stream` aynı üçlüyü veriyor (`<`) | SIZINTI YOK | — |
| 6 | Canlı kurucu: karar sonrası snapshot, `now` > karar, bayat koruma | `build_batch` now = karar + 1 gün: karar sonrası snapshot bağlama girmiyor. Ancak `is_stale` karara göre 10 gün geriye bakarken `_shadow` defteri `now − 10 gün`den yüklüyor → aradaki pencerede biten, tabanda olmayan maç görünmüyor | BULGU (bakış açısı; ileri bilgi değil) | Minor |
| 7 | Ön kayıt değişebilirliği, özet/temiz ağaç | Temiz → geçti; izlenmeyen dosya → RED; commit'li **başka** bir ön kayıt dosyası (`--prereg config/alt.yaml`, resamples = 5) → geçti. Kanonik yol zorlanmıyor | BULGU | Minor |
| 8 | `final_eval` AST kuralı (12i/14h) kaçış yolları | `key_misuses`: walrus, `AnnAssign`, demet hedef, `IfExp`, öznitelik hedef, doğrudan `return open_holdout(…)`, dict, `for` hedefi, closure, `evil.load_matches(key=key)` → 10/10 görülmedi. `private_accesses`: `getattr`/`__dict__`/`importlib` → 3/3 görülmedi. Gerçek `final_eval.py` kurala uyuyor | BULGU (kural sınırı) | Minor |
| 9 | 0010 indeks atlatma | Python öykünmesi: kanonik `faz3:…`/`faz3-rerun:…:…` indekste; `faz3 :`, `FAZ3:`, ` faz3:`, U+FF1A girmiyor — ama bu amaçları yalnız `purpose_for` üretir (AST kuralı başka yazar bırakmaz). Python katmanı (`LIKE 'faz3%'`) `faz30:`u da sayar (güvenli yön). Postgres'te koşulmadı | SIZINTI YOK (Python öykünmesi) | — |
| 10 | Placebo tohumu kimliğe bağlı mı | E0'a E1 eklenince ortak maçların seçimleri aynı | SIZINTI YOK | — |
| 11a | `HistMatch.result` gollerle çelişirse | Ayrıştırıcı `result != _winner(goals)` satırını reddediyor (`football_data.py:334`) | SIZINTI YOK | — |
| 11b | Harness `LeakageError` ikinci katmanı | Olaylar `(an, tür, sıra)` sıralı; karar (0) sonuçtan (1) önce; `event.at <= latest` tutarlı | SIZINTI YOK | — |
| 11c | Rapora ham satır sızması | `render_final` yalnız toplu; açılış sonrası istisna metinleri indeks/zaman taşıyor; `DuplicateMatch` anahtarsız `_refuse_duplicates` ile açılıştan ÖNCE yakalanır | SIZINTI YOK | — |

**Sonuç:** Look-ahead ya da holdout sızıntısı **kanıtlanamadı**; beş Minor bulgu var, hiçbiri holdout açılışını
ertelemeyi gerektirmiyor.

## Bulgular

### B1 · DC memo'su nesne paylaşımında sızar (gizil) — Minor
- **Yer:** `src/football_edge/model/strategies.py:93-103` (`params`), `:70` (`memo … compare=False`, `replace` ile taşınır).
- **Kanıt:** yeniden kullanılan DC nesnesi, sezonu çıkarılmış küme oynatılınca 2023/24'ün 56/56 tahminini tam
  kümeninkiyle aynen döndürüyor; taze nesne 56'dan azını.
- **Neden üretimde tetiklenmiyor:** `wf_run.model_strategies` (grup başına), `selection.dc_loss` (grup başına),
  `live/shadow._states` (slot başına) — üç yapım yeri de taze; AST taramasıyla doğrulandı.
- **Asgari düzeltme:** memo anahtarına gruptaki gözlem sayısını eklemek (aynı gün, farklı geçmiş → farklı fit).

### B2 · Bayat durum koruması karara göre bakıyor, defter `now`a göre yükleniyor — Minor
- **Yer:** `src/football_edge/live/context.py:173-175` ile `src/football_edge/live/__main__.py:100`
  (`load_live_matches(since=now - LOOKBACK)`).
- **Etki:** ileri bilgi değil; R141/R153 korumasının kör noktası (karar ile koşu arasındaki gün sayısı kadar).
  Salı/cuma 12:35 UTC koşusunda karar ile koşu aynı gündür (fark < 1 gün).
- **Asgari düzeltme:** `since = now - LOOKBACK - <en uzun karar→koşu aralığı>`.

### B3 · Ön kayıt kanonik yola bağlı değil — Minor
- **Yer:** `src/football_edge/backtest/__main__.py:111-114` (`--prereg/--config/--lock/--catalog` serbest),
  `preregistration.py:99-115`.
- **Kanıt:** commit'li başka bir ön kayıt dosyasıyla `preflight` geçti; açılışın `purpose`u o dosyanın sha256'sını
  taşır — denetlenebilir, ama "ön kayıt = `config/faz3_preregistration.yaml`" sözü kodla zorlanmıyor.
- **Asgari düzeltme:** açılışta (prova değil) yollar kanonik değilse `EXIT_PREFLIGHT`.

### B4 · 12i anahtar akışı kuralı yalnız `key = open_holdout(...)` ve `ast.Name` yüklerini görür — Minor
- **Yer:** `tests/test_holdout_access_rule.py:319-355`. 10 kaçış biçiminin 10'u görülmedi. Gerçek dosya uyumlu.
  (Plan "ölçmedikleri" 26 ile aynı sınır; burada ölçüldü.)
- **Asgari düzeltme:** her `open_holdout` çağrısının ebeveyni tek ad hedefli `ast.Assign` değilse ihlal; `NamedExpr`/
  `AnnAssign` hedefleri; `load_matches` çağrısı yalnız ad olarak.

### B5 · 14h özel yardımcı kuralı dinamik erişimi görmez — Minor
- **Yer:** `tests/test_holdout_access_rule.py:362-391`. `getattr(…, "_records")`, `__dict__["_records"]`,
  `importlib.import_module(...)._records` → 3/3 görülmedi.
- **Asgari düzeltme:** korunan modül takma adlarına `getattr`/`__dict__`/`vars` ile `_` önekli dize erişimini ihlal
  saymak; `importlib.import_module("<korunan>")`i takma ad olarak kaydetmek.

## Ölçmediklerimiz

- **Gerçek Postgres:** 0010 ifade indeksi ve 0007 tetikleyicileri Python öykünmesiyle değerlendirildi (0010'un
  gerçek DB'de reddettiği ayrıca dalga 4 sonunda kanıtlandı — ölçüm belgesi).
- **Gerçek veri:** E3, football-data yayın gecikmesi, kilit doğrulaması, holdout satır sayımı — DB ister.
- **Açılış yolu uçtan uca:** `run_final` yalnız okundu; `OpenedButFailed`/`__exit__` (R154) yolları projenin sahte
  bağlantı testlerine bırakıldı.
- **`history/__main__.py` kilit komutu:** holdout satırlarının yalnız özet/sayım olarak çıktığı okunarak varsayıldı.
- **Canlı zamanlama** ve football-data'nın sezon içi satır düzeltmeleri ölçülmedi.
- **Süreç dışı arıza (OOM/137)** ve aynı anda iki `final-eval` süreci (yarış) denenmedi.
- `EXPECTED_MIN_LEAKAGE=336` bugünkü sayıya eşit: yeni etiketler eklendikçe güncellenmezse sınır gevşer (gözlem).
