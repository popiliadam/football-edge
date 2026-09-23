# Faz 3 — Baz model, walk-forward doğrulama, canlı bağlam ve tek holdout açılışı · Tasarım

**Tarih:** 2026-09-23 · **Durum:** **ONAYLANDI** (kullanıcı, 2026-09-23 — §14'ün on iki kararının hepsi önerildiği gibi; kararlar §14.1'de R128–R139). Sıradaki onay kapısı: TDD planı `../plans/2026-09-23-faz3-model-walkforward.md`; plan onaylanmadan ve İz A (`feat/leagues-n1-b1-aut`) `main`e birleşmeden Faz 3 kodu yazılmaz · **Spec:** `2026-09-19-football-edge-design.md` (§4, §6.2, §6.3, §9 Faz 3) · **Önceki faz:**
`2026-09-22-faz2-tarihsel-taban-design.md` (D1–D20), `docs/phases/02-tarihsel-taban/HANDOFF.md` (§3 ölçülmeyenler,
§4 R78–R121, §6 ön koşullar) · **Yol haritası:** `../plans/2026-09-21-yol-haritasi-v2-paralel-izler.md` (Faz 3
dalgaları) · **Ertelenenler:** `docs/DEFERRED.md` §12, §14

Bu belge taslak olarak yazıldı ve 2026-09-23'te onaylandı: kodla doğrulanan her olgu `dosya:satır` ile, ölçülmemiş her şey "ölçülmedi" diye
yazılıdır. Bu belge yazılırken veritabanına bağlanılmadı, kapı dışında hiçbir şey koşulmadı, holdout AÇILMADI.
Plan-zamanı ölçümleri (§11, dalga 0) ayrı bir ölçüm belgesine (`2026-09-23-faz3-olcumler.md`, plan aşamasında)
yazılır. Atıf biçimi: "§3/N" = Faz 2 HANDOFF §3'ün N. maddesi; "12x"/"14x" = DEFERRED §12/§14; "Rnn" = Faz 2
HANDOFF §4'teki karar.

## 0. Özet

Faz 3, Jev'siz baz modeli kurar ve **dürüstçe** ölçer. Faz 2 ölçme aracını kurdu; Faz 3 o araca ilk modeli
takar ve üç sözü tutar:

1. **Model ailesi** — fit edilmiş Elo (bugün iskele katsayılarla), zaman sönümlü Dixon-Coles ve piyasa ile
   log-doğrusal görüş havuzu (logistic opinion pooling). Hepsi Faz 2 harness'ının `Strategy` arayüzüne takılır.
2. **Walk-forward** — her hiperparametre ve her ağırlık yalnız geliştirme döneminde (`< 2025-07-01`), ileriye
   kayan pencerelerle seçilir. Faz 2'nin örneklem içi ölçümleri (HANDOFF §3/32) burada kapanır.
3. **Canlı bağlam kurucusu + eşitlik testi** — defter ve gözlem deposundan `DecisionContext` VE `observe`
   akışını kuran ikinci kurucu; iki kurucunun aynı maç için aynı şeyi ürettiği bir testle kanıtlanır (R98).
   Bu olmadan backtest'in canlıyı temsil ettiği iddia edilemez.
4. **Tek, kayıtlı holdout açılışı** — önceden yazılmış ve commit'lenmiş karşılaştırmalarla, yalnız
   `backtest/final_eval.py`de; işçilere anahtar değil SEÇİLMİŞ SATIR verilir (DEFERRED 12i).

Faz 3'ün kapısı bir kâr iddiası DEĞİLDİR: 1X2'de Elo + Dixon-Coles'un kapanışı yenmesi beklenmez (Faz 2 K1:
kapanış kapanış öncesinden bile isabetli). Kapı, ölçümün dürüst yapıldığını ve baz çizginin holdout'taki
değerinin **kaydedildiğini** ister (spec §9: "Holdout CLV baz çizgi"). Performans şartı §14/K3'te kullanıcıya
sorulur.

## 1. Kapsam

**Faz 3'ün görevleri** (yol haritası v2 §2 İz A tablosundaki numaralar): T1 Dixon-Coles (saf) · T3 Elo fiti ·
T5 kalibrasyon ölçümü · T4 görüş havuzu · T6 baz çizgi raporu. Faz 2 HANDOFF §6'nın ön koşulları ayrı görev
olarak eklenir: P1 walk-forward · P2 canlı bağlam kurucusu + eşitlik testi · P3 Elo fiti (= T3) · P4 scipy
dalga 0'ı · P5 `final_eval` (seçilmiş satır, tek açılış).

**Kapsam dışı (YAGNI):**
- **xG varyantı (yol haritası T2) — DÜŞER.** Tarihsel xG yok: `HxG`/`AxG` kaynağı belgesiz, yalnız 2026/27'den
  dolu ve maç sonrası büyüklük (Faz 2 D16); footystats yalnız altı canlı lig ve tarihçesiz. Fit edilemeyen bir
  özellik modele girmez (spec §4/3).
- **Hakem özelliği** — FBref kapalı, TR dışında kaynak yok (Faz 1 HANDOFF §5/6).
- Jev özellikleri (Faz 4), istifleme, Kelly, EV eşiği kapısı (Faz 5), yayın (Faz 6).
- **Asya handikabı** — çeyrek çizgiler (Faz 2 §13/6); Dixon-Coles'un skor matrisi ileride verir, Faz 3 ölçmez.
- Kupa/uluslararası maçlar — tarihsel tabanda yok.
- Canlı tahminlerin YAYINI. Faz 3 en fazla gölge (shadow) tahmin kaydeder (§10, §14/K7).

## 2. Girdiler (kodla ya da önceki ölçümle bağlı)

| Olgu | Değer | Kaynak |
|---|---|---|
| Dönemler | geliştirme `< 2025-07-01` · holdout `[2025-07-01, 2026-07-01)` · sonrası `≥ 2026-07-01` | `history/holdout.py:24-25`, `:82-87` |
| Anahtarsız yükleme | `load_matches` DEV + POST döner; HOLDOUT yalnız `open_holdout`un anahtarıyla | `history/sync.py:243-265` (R96) |
| Pencere tipi | `Window.end > DEV_END` → `ValueError`; holdout/sonrası için pencere yok | `history/holdout.py:53-68` (R89) |
| Kapanış öncesi fiyat | ana ligler: `BbAv*` 2005/06–2018/19, `Avg*` 2019/20'den; **ek ligler (AUT dahil): YOK** | ölçüm belgesi Faz 2 §2.4; `history/holdout.py:71-74` |
| Referans kapanış | `AvgC` ana liglerde 2019/20'den %100; ek liglerde dosya boyunca | Faz 2 D3; `football_data.py:59-61` |
| Başlama saati | ana liglerde 2019/20 öncesi yok (§3/3); 2019/20+ saatsiz satır sayısı ölçülmedi (§3/37) | Faz 2 HANDOFF §3 |
| Karar anı | cuma/salı 12:00 Europe/London; sonuç başlama + 3 sa | `backtest/timeline.py:41-53` |
| Harness | olay akışı, eşzamanlıda karar önce, `LeakageError` ikinci katman | `backtest/events.py:35-39`, `backtest/harness.py:133-162` |
| Bağlam | `DecisionContext` durum görüntüsü taşımaz; durum `observe` ile stratejide | `backtest/harness.py:35-49`, `:76-82` (R98) |
| Maç kimliği | `DecisionContext.match_index` = yeniden oynatmadaki SIRA; canlıda karşılığı yok | `backtest/harness.py:42`, `:110-120` |
| Elo | `k=20`, `home_advantage=65`, marj eğrisi doğrusal — üçü iskele; beraberlik sabit `draw_rate=0.26` | `elo.py:9-21`, `:37-49`; `backtest/strategies.py:80-131` |
| Elo reyting grubu | (ülke, takım) — R94 | `backtest/strategies.py:99-100` |
| Vig | `DEFAULT_METHOD = power` (R118) | `market/devig.py:108-141` |
| CLV | `o · p_kapanış − 1`, referans vig'i temizlenmiş `AvgC` | `market/metrics.py:152`, `backtest/evaluate.py:55-64` |
| Canlı fiyat | `odds_snapshots` (append-only, zincirli); günlük snapshot 06:22 UTC, mühür kapanışta | `db/migrations/0001_init.sql`, `.github/workflows/snapshot.yml` |
| Canlı sonuç | `match_results` (The Odds API skorları, `fetch-results` KREDİ yakar, elle — R45/R67); içerik tekilleştirmesi yok (9.6f) | `db/migrations/0002_sources.sql`, `collectors/results.py` |
| Canlı ↔ tarihsel eşleme | (lig, Londra tarihi, normalize ad) + `config/history_aliases.yaml` (6 ad) | `market/bridge.py:130-163` |
| Canlı ligler | 8 aktif: eng.1, esp.1, ita.1, ger.1, fra.1, tur.1, ned.1, bel.1; `aut.1` var ama `active: false` (kredi) — İz A `main`e birleşti (`dd038f7`, `a398c31`) | `config/leagues.yaml` (`a398c31`) |
| Holdout açılışı | 0 (`holdout_access_log`); izinli tek modül `backtest/final_eval.py` (henüz yok) | Faz 2 HANDOFF §2.3; `tests/test_holdout_access_rule.py` `GUARDED` |
| Bağımlılık | yalnız numpy (D15); scipy Faz 3 dalga 0'ı | `pyproject.toml` |

**İki olgu tasarımı en çok bağlar:**
- **AUT (ve bütün ek ligler) kapanış öncesi fiyat taşımaz.** Tarihte bir karar anı fiyatı olmadığı için orada
  ne CLV ne de piyasa harmanı ölçülebilir; kapanışı harman girdisi yapmak sızıntıdır (kapanış karar anından
  sonra bilinir). Ek liglerde yalnız modelin isabeti (LL, kalibrasyon) ölçülür (§6.5, §14/K10).
- **Holdout yılı hem kilitli test hem en yakın sezondur.** Anahtarsız her yol (canlı dahil) 2025/26'yı
  görmez; Elo holdout yılını atlayarak sonrası dönemine girer (§3/40). §5.4 bunu ele alır.

## 3. Mimari

```
                     geliştirme (DEV)                               sonrası (POST) + canlı
 load_matches(key=None) ─► per-country replay ─► predictions      ledger (odds_snapshots, matches)
        │                  (harness.replay, değişmez)   │          history POST (hist_files, haftalık)
        │                                                ▼                 │
        │   model/elo_fit.py ──┐           backtest/walkforward.py         ▼
        │   model/dixon_coles.py ├─ Strategy ─► (bölgeler, katlar,     live/context.py ── canonical
        │   model/pool.py ─────┘    arayüzü     ağırlık fiti, rapor)   (canlı kurucu)     MatchRecord
        │                                                ▲                 │                 │
        │           backtest/context.py ◄────────────────┴─────────────────┘  eşitlik testi ◄┘
        │           (TEK bağlam kurucusu: MatchRecord → DecisionContext, ResultRecord)
        │
 config/model_faz3.yaml (dondurulmuş hiperparametreler, commit)
 config/faz3_preregistration.yaml (holdout karşılaştırmaları, commit + sha)
        │
 backtest/final_eval.py ── open_holdout (TEK açılış, holdout_access_log) ── seçilmiş satırlar ─► rapor
                                                                          (anahtar dışarı çıkmaz)
```

| Bileşen | Dosya (yeni ya da değişen) | Ne |
|---|---|---|
| Ortak bağlam kurucusu | `backtest/context.py` (yeni); `harness.py`'nin `_context`/`_result_record`ı buraya taşınır (`harness.py:98-120`) | Kaynaktan bağımsız `MatchRecord` → `DecisionContext` ve `ResultRecord`. İki kurucunun ortak son adımı |
| Tarihsel kaynak bağdaştırıcısı | `backtest/context.py` | `HistMatch` → `MatchRecord` (bugünkü davranış, birebir) |
| Canlı kaynak bağdaştırıcısı | `live/context.py` (yeni paket) | defter + tarihsel POST önbelleği → `MatchRecord`; `observe` akışı; bayat durum koruması (§7.3) |
| Elo fiti | `model/elo_fit.py` (yeni); `elo.py` yalnız yeni alanlar alırsa | `k`, ev avantajı, marj biçimi, sezon başı ortalamaya dönüş, terfi eden takım başlangıcı, sıralı-lojit beraberlik |
| Dixon-Coles | `model/dixon_coles.py` (saf) + `model/strategies.py` | zaman sönümlü en çok olabilirlik (scipy L-BFGS-B), ρ düzeltmesi, sırt cezası; 1X2 ve Ü/A 2.5 |
| Görüş havuzu | `model/pool.py` (saf) | `log p ∝ Σ wᵢ log pᵢ`; lig başına ağırlık, walk-forward ile |
| Walk-forward | `backtest/walkforward.py` (yeni) | seçim/değerlendirme bölgeleri, bileşen tahminlerinin saklanması, ağırlık katları, rapor |
| Son değerlendirme | `backtest/final_eval.py` (yeni; AST kuralının izinli tek modülü) | tek açılış, ön kayıt doğrulaması, seçilmiş satır |
| CLI | `backtest/__main__.py` (`walkforward`, `final-eval`) | `collect.py`ye dokunmaz (Faz 2 §12) |
| Gölge tahmin (§14/K7 onaylanırsa) | `live/shadow.py`, `db/migrations/0009_model_predictions.sql`, workflow | append-only, RLS, TRUNCATE tetikleyicili |
| Tek açılış (DB) (§14/K8) | `db/migrations/0010_holdout_phase.sql` | faz başına en çok bir açılış, veritabanı düzeyinde |

## 4. Veri akışı ve zaman

- **Tarihsel:** `load_matches(conn, catalog, lock=load_lock(...))` (`sync.py:243`) → lig kodu → maçlar.
  Kilit doğrulaması her walk-forward koşusunda ZORUNLU (`lock` verilmeden koşu reddedilir): model fitinin
  gördüğü satırlar kilitli satırlardır.
- **Yeniden oynatma ülke grubu başına:** Elo reyting grubu ülkedir (R94) ve Dixon-Coles da ülke grubu başına
  fit edilir (§6.2, §14/K9); gruplar arasında durum etkileşimi yoktur. Grup başına `replay` bellek ve süreyi
  böler, sonuç tek akışla aynıdır (eşitliği bir test sabitler).
- **Zaman kuralları DEĞİŞMEZ** (`timeline.py`). Yeni modeller aynı karar anında, aynı `observe` akışıyla
  tahmin eder. Walk-forward, `replay`in bütün kararlarda ürettiği tahminleri tarihe göre bölgelere ayırır; fit
  ise yalnız `observe` ile gelen, karar anından önce bilinen sonuçlarla yapılır — harness'ın garantisi
  modellere de uzanır.
- **Durumun değişmezliği ve maliyet.** Stratejiler değişmezdir (`observe` yeni değer döner). Dixon-Coles
  geçmiş sonuçları taşımak zorunda: her `observe`da büyüyen bir demeti kopyalamak O(n²)'dir (~200 bin sonuç).
  Plan, kopyalamadan paylaşan kalıcı bir yapı (ör. hafta dilimli demetler) kullanır ve süre/RSS'i dalga 0'da
  ölçer (§11, §13/R2).

## 5. Walk-forward

### 5.1 Bölgeler (yalnız DEV; holdout ve sonrası HİÇBİR seçimde kullanılmaz)

| Bölge | Ana ligler | Ek ligler | Neye yarar |
|---|---|---|---|
| Isınma | 2005/06 → 2011/12 | dosyanın ilk yılı | Elo/DC durumu; tahmin ölçülmez |
| **S — seçim** | 2012/13 → 2018/19 | 2012 → 2018-06 | hiperparametre seçimi; ölçüt log loss (sonuca karşı). Piyasa girdisi `BbAv` (Avg değil); kapanış yok → CLV yok; saat yok (gün içi sıra yaklaşık, §3/3) |
| **E — değerlendirme** | 2019/20 → 2024/25 (`MAIN_WINDOW`) | 2018-07 → 2025-06 | raporlanan walk-forward sayıları; `Avg` kapanış öncesi + `AvgC` + saat birlikte → LL, kalibrasyon, CLV |

Bölge sınırları `Window` tipiyle kurulur (`holdout.py:53`); E'nin sonu `DEV_END`dir ve pencere holdout'a
uzanamaz (R89). Sonrası dönemi (≥ 2026-07-01) spec §6.2 gereği "dokunulmamış son ileri test"tir: Faz 3'te
yalnız `final_eval` ve canlı gölge okur, hiçbir seçim görmez.

### 5.2 Şema — seçenekler (§14/K2)

| | Tanım | Artı | Eksi |
|---|---|---|---|
| **A (öneri)** | Hiperparametreler S'de BİR kez seçilir ve dondurulur (`config/model_faz3.yaml`, commit). E boyunca model parametreleri (Elo reytingleri, DC güçleri) çevrimiçi güncellenir/yeniden fit edilir, hiperparametreler sabit. Havuz ağırlığı lig başına **genişleyen katlarla**: E'nin sezonu `s` için ağırlık, E'nin `s`'den önceki sezonlarının tahminleriyle fit edilir; E'nin ilk sezonu S'nin (`BbAv`) ağırlığını kullanır | Tek seçim, E sayıları temiz örneklem dışı; ucuz; S ile E'nin fiyat kaynağı farkı (BbAv/Avg) yalnız ilk katı etkiler | Hiperparametre kayması (2012 → 2024) yakalanmaz |
| B | İç içe kayan başlangıç: her E sezonu için hiperparametreler o sezondan önceki bütün veriyle yeniden seçilir | En dürüst, kaymayı izler | Altı kez tam arama; DC ile hesap süresi ölçülmedi — runner 60 dk'yı aşabilir |
| C | Tek bölme: 2012/13–2022/23 seçim, 2023/24–2024/25 test | En basit | E iki sezona iner; aralıklar genişler; seçim E'nin ilk yıllarını görür |

Reddedilen: hiperparametreyi E'de seçip E'de raporlamak (örneklem içi — Faz 2'nin `method_scores` kusuru, 14q).

### 5.3 Ne hesaplanır, ne saklanır

- Her strateji için E'deki her tahmin, **bileşen olasılıklarıyla** (piyasa, Elo, DC) saklanır; havuz ağırlık
  katları bu kayıt üzerinde çevrimdışı hesaplanır (yeniden oynatma gerekmez). Kayıt yalnız bellekte ya da
  gitignored geçici dosyada: ham satır depoya girmez (Faz 2 §4.3).
- Rapor (`docs/reports/<tarih>-faz3-walkforward.md`): lig başına ve havuzlanmış LL (bootstrap GA), Brier, RPS,
  kalibrasyon eğimi/ECE, CLV (§6.4 bahis kuralıyla), bahis sayısı, tahminsiz karar sayısı; yalnız toplu sayı.
- **Belirlenimcilik:** aynı kilit + aynı `model_faz3.yaml` + aynı git SHA → aynı tahminlerin sha256'sı. scipy
  sonuçları platformlar arası bit düzeyinde aynı değildir; özet, olasılıkların `1e-9`'a yuvarlanmışından alınır
  ve toleransı dalga 0'da ölçülür.

### 5.4 DEV + POST holdout boşluğu (Faz 2 §3/40) — seçenekler (§14/K1)

Sorun: anahtarsız her okuma 2025/26'yı atlar. Elo reytingleri ve DC güçleri 2025-06'dan doğrudan 2026-07'ye
atlar; 2025/26'da terfi eden takımlar görülmemiş sayılır. Bu SIZINTI değildir, bayat durumdur — ama canlı
tahminin kalitesini düşürür ve backtest'in "sürekli durum" varsayımıyla canlının farkını büyütür.

| | Tanım | Bedel |
|---|---|---|
| **H1 (öneri) — boşluk + ölçülen ceza** | Canlı ve anahtarsız her yol DEV + POST ile kurulur; boşluk modelin sezon başı kurallarıyla (Elo ortalamaya dönüş, terfi eden takım başlangıcı, DC zaman sönümü) karşılanır. **Boşluk cezası DEV'de ölçülür:** E'nin bir sezonunu atlayarak sonrakini tahmin eden simülasyon (ör. 2022/23 atlanır, 2023/24 tahmin edilir) ile atlanmadan tahmin arasındaki LL farkı raporlanır. `final_eval` tek açılışında POST'u TAM durumla (DEV + HOLDOUT + POST) da ölçer: canlı gölgenin (boşluklu) aynı maçlardaki sayısıyla fark doğrudan boşluk cezasıdır. Holdout, planlanan son açılıştan (Faz 5) sonra "durum verisi" olarak serbest kalır | Faz 3–5 canlı gölgesi bir sezon bayat durumla koşar; üç açılış hakkı korunur |
| H2 — Faz 3 açılışından sonra yalnız sonuçları serbest bırak | Tek açılıştan sonra holdout'un sonuç sütunları (skor; fiyat değil) anahtarsız okunur; canlı durum tam olur | Faz 4/5 holdout'ta LL ölçemez (sonuçlar artık açık) → onların kapısı POST'a taşınır; POST Faz 4'te birkaç bin maç, holdout 12.092 |
| H3 — "yalnız durum" açılışları | Canlı her koşuda holdout sonuçlarını kayda düşen ayrı bir amaçla açar | Açılış sayısı anlamını yitirir (günde bir); değerlendirmede kullanılmadığı yalnız disiplinle korunur — reddedilir |

## 6. Model ailesi

### 6.1 Elo fiti (T3, Faz 2 §6/3)

Bugünkü `EloPointInTime` (`strategies.py:80-131`) iskele katsayılarla ve sabit `draw_rate` ile koşar; bu
beraberlik olasılığını reyting farkından bağımsız kılar. Fit edilecekler (S bölgesinde log loss):

| Parametre | Seçenekler | Not |
|---|---|---|
| `k` | sürekli | `elo.py:18` |
| ev avantajı | sürekli, ülke grubu başına mı tek mi — tek (az parametre); lig başına fark raporlanır | `elo.py:19` |
| marj çarpanı | yok / doğrusal (bugün) / `log(1+marj)` | `elo.py:37-49`; biçim S'de karşılaştırılır |
| sezon başı ortalamaya dönüş `λ` | `r ← μ + (1−λ)(r − μ)` | yeni; boşluk (§5.4) buna yaslanır |
| terfi eden takım başlangıcı | grup ortalaması / o sezon düşen takımların ortalaması | yeni; `config.initial` (1500) bugün her yeni takıma veriliyor |
| 1X2 eşlemesi | sıralı lojit: `P(H) = σ(β·Δ − c₁)`, `P(A) = σ(−β·Δ − c₂)`, D kalan | `draw_rate`in yerine; lig başına kesişimler |

Arama: küçük ızgara + scipy Nelder–Mead; ızgara ve sonuç raporda. Elo tek geçişli (çevrimiçi) olduğundan her
aday bir `replay` ister; aday sayısı süre ölçümüne göre planda sınırlanır.

### 6.2 Dixon-Coles (T1)

- Gol süreci: `X ~ Poisson(α_ev · β_dep · γ)`, `Y ~ Poisson(α_dep · β_ev)`, düşük skorlarda `τ(ρ)` düzeltmesi
  (0-0, 1-0, 0-1, 1-1). Ağırlık `exp(−ξ · gün farkı)`; güçlere sırt (L2) cezası (yeni ve az maçlı takımlar
  için, kimlik kısıtını da sağlar).
- Fit: scipy L-BFGS-B, önceki fitten sıcak başlangıç. Yakınsamayan fit → o karar için tahmin YOK (sayılır,
  sessiz geçmez — Ruling 6 ruhu); son yakınsayan fitle tahmin etmek bayat parametreyi gizlerdi.
- **Grup:** ülke grubu başına, kademeler (E0–E3) birlikte — terfi/küme düşme takımları bağlar, R94 ile
  tutarlı. Seçenek lig başına fit (§14/K9).
- **Yeniden fit sıklığı:** `observe`, ISO haftası değişen ilk sonuçta grubu yeniden fit eder (karar anları
  salı ve cuma; fit o haftaya kadar bilinen sonuçları kullanır). Strateji protokolü DEĞİŞMEZ (`harness.py:76-82`).
- Hiperparametreler (S'de): `ξ`, sırt katsayısı, fit penceresi (sönümün kestiği geçmiş). γ ve ρ fit edilir.
- Çıktı: skor matrisi (0..10) → 1X2 ve Ü/A 2.5 olasılıkları.

### 6.3 Görüş havuzu (T4)

`p_harman ∝ exp(w_m · log p_piyasa + w_e · log p_elo + w_d · log p_dc)`, ağırlıklar ≥ 0, lig başına; normalize.
`p_piyasa` = karar anı kapanış öncesi `Avg`'nin power ile vig'i temizlenmiş olasılığı (E'de `Avg`, S'de
`BbAv`). Ağırlıklar §5.2/A'nın genişleyen katlarıyla fit edilir (her kat birkaç bin maç; lig başına üç
parametre). Beklenti: verimli liglerde `w_m` baskın (spec §4/2) — bunu veri söyler; ağırlık için ön bilgi
girilmez.

**Havuzun doğal bir akıl sağlığı sınaması var:** `w = (1, 0, 0)` havuzun içindedir, yani doğru fit edilmiş bir
harman E'de piyasadan anlamlı ölçüde KÖTÜ olamaz. Olursa fit ya da hat bozuktur (§9/G4).

### 6.4 CLV için bahis kuralı (Faz 5'in staking'i değil)

Walk-forward ve holdout'ta CLV ölçmek için sabit, önceden kayıtlı bir kural: maç başına en çok bir bahis,
1X2'de `p_harman · o_pre − 1` en büyük sonuç, eşik `τ`'yu aşıyorsa; birim bahis; fiyat karar anı `Avg`
kapanış öncesi fiyatı (ulaşılabilir; `Max` değil). Birincil `τ` ve duyarlılık kümesi §14/K12'de. CLV'nin
referansı değişmez (`evaluate.py:42-64`). CLV sonuç sızıntısını GÖRMEZ (Faz 2 §3/29): sonuç sızıntısının
ölçüsü LL ve Oracle kanaryasıdır.

### 6.5 Ek ligler (AUT dahil)

Kapanış öncesi fiyat yok → havuz ve CLV tarihte ölçülemez. Ek liglerde yalnız model (Elo, DC) ölçülür: LL,
kalibrasyon ve `LL(model) − LL(AvgC)` (kapanışa uzaklık — kapanış burada bir KIYAS, girdi değil). Canlıda
AUT'un kapanış öncesi fiyatı defterden gelir; AUT'ta harmanın ve CLV'nin ilk ölçümü canlı gölgedir (§14/K10).
AUT'un `Date` takvimi (Londra tarihi mi) ölçülmedi (§3/38): canlı eşleme için İz A'nın ilk mühürlerinden sonra
köprüyle ölçülür.

### 6.6 Ü/A 2.5

DC'nin skor matrisi Ü/A 2.5'i bedava verir; ana liglerde `Avg>2.5`/`Avg<2.5` kapanış öncesi ve `AvgC` var.
Spec §2/2 kenarın yan marketlerde olma olasılığını daha yüksek görür. Öneri: 1X2 birincil, Ü/A 2.5 ikincil
ön kayıtlı karşılaştırma (§14/K4). İki yollu kalibrasyonda kesişim simetriyle 0'dır (12j) — raporda yazılır.

## 7. Canlı bağlam kurucusu + eşitlik testi (P2, R98)

### 7.1 Tek son adım

Bugün bağlam `harness._context` (`harness.py:110-120`) ve sonuç kaydı `harness._result_record`
(`harness.py:98-107`) içinde, `HistMatch`e bağlı. Faz 3 bunları kaynaktan bağımsız bir ara kayda bağlar:

```
MatchRecord: key (lig kodu, Londra tarihi, ev, deplasman — kanonik ad), season, kickoff (UTC | None),
             pre_prices (OddsKey → fiyat, yalnız PRE_CLOSING), result (varsa: goller)
```

`context_of(record, decided)` ve `result_of(record, known_at)` iki kurucunun ORTAK son adımıdır; eşitlik testi
böylece "iki ayrı kod aynı şeyi mi yazdı"yı değil "iki kaynak aynı kaydı mı üretti"yi sınar. Karar anı ve sonuç
anı her iki kurucuda `timeline.decision_at` / `timeline.result_known_at`tan gelir — canlı kurucu gerçek varış
anını KULLANMAZ (§7.3).

### 7.2 Canlı kurucu (`live/context.py`)

- Maç: `matches` satırı → lig kodu (`history_leagues.yaml`'ın `league_id` eşlemesi), Londra tarihi
  (`bridge.py:130-139` ile aynı kural), ad → `history_aliases.yaml` + `normalise_team`. Eşlenemeyen ad
  maçı düşürmez: "eşlenemedi" sayılır, tahmin yok (R93 ruhu).
- Sezon kodu: tarihsel ayrıştırıcının kuralıyla (ana: `"2627"`; ek: dosyanın `Season` biçimi) — ayrı yazılmaz,
  ortak fonksiyon.
- `pre_prices`: gözlem anı `≤ decision_at` olan SON snapshot turunun 1X2'si (ve Ü/A 2.5'i), kitaplar üzerinde
  aritmetik ortalama → `OddsKey("Avg", "1x2", H/D/A, "pre")`. Bu, football-data'nın `Avg` tanımına (kitap
  ortalaması) yapısal olarak denktir; KİTAP KÜMESİ ve TOPLAMA SAATİ denk değildir (§12/5–6).
- Varsayılan zamanlama: bugünkü 06:22 UTC snapshot'ı; karar anında (11:00/12:00 UTC) ayrı bir snapshot kredi
  harcar (§14/K6).

### 7.3 `observe` akışı ve bayat durum koruması

Tarihsel kural sonucu başlama + 3 saatte "bilinir" sayar. Canlıda sonucun kaynağı §14/K5'in kararıdır;
öneri football-data sonrası dönemi (ücretsiz, tarihsel kaynakla AYNI satırlar — eşitlik yapıdan gelir).
football-data'nın yayın gecikmesi ÖLÇÜLMEDİ; salı 09:50 UTC senkronu hafta sonu sonuçlarını içermeyebilir.

**Bayat durum koruması:** canlı kurucu bir karar için, tarihsel kuralın "bilinir" saydığı (`known_at <
decision_at`) ve aynı gruptaki takımların oynadığı her maçın sonucunu arar; biri eksikse o maç için tahmin
YOK ("durum bayat", sayılır ve raporlanır). Böylece tahmin edilen her maçta canlı `observe` akışı tarihsel
akışla ÖZDEŞTİR; farkın bedeli tahmin sayısına yansır, sessizce modele değil. Eksik sonuç sayısı
football-data gecikmesinin ilk gerçek ölçüsüdür.

### 7.4 Eşitlik testi — üç katman

| # | Ne | Nerede | Nasıl kırmızı olur |
|---|---|---|---|
| E1 | Aynı maçı taşıyan sentetik kaynak çiftleri (`HistMatch` ↔ defter satırları + POST satırları): iki kurucunun `DecisionContext`'i (bütün alanlar) ve karar anına kadarki `ResultRecord` dizisi ÖZDEŞ. Üretilen fikstürler: yaz saati geçişi, salı/cuma, saatsiz maç, eşzamanlı sonuç, ad takma adı, terfi eden takım, eksik fiyat, karar anından SONRA gelen snapshot | `tests/test_context_parity.py` (`leakage` işaretli) | Mutasyonlar: canlı kurucu `≤` yerine `<`/ilk snapshot'ı alır; `observe`a gerçek varış anı verilir; takma ad atlanır; Londra yerine UTC tarihi; sezon kodu ayrı hesaplanır → her biri kırmızı |
| E2 | Aynı stratejiye iki kurucudan gelen bağlam ve akış → aynı `Prediction` (Elo, DC, harman) | aynı dosya | strateji bağlamda kaynağa özgü bir alana bakarsa |
| E3 | Gerçek veride: POST'ta hem defterde hem football-data'da olan maçlar için yapısal alanlar (lig, tarih, adlar, karar anı, sezon) BİREBİR; fiyat farkı ve bayat durum sayısı RAPOR | `python -m football_edge.live parity` (köprü deseni) | yapısal alan farkı → exit ≠ 0; fiyat farkı kapı değildir (kitap kümeleri farklı) |

### 7.5 Kimlik

`match_index` yeniden oynatmaya özgü bir sıradır (`harness.py:42`); canlıda karşılığı yoktur. Bağlama
kararlı bir `match_key` (lig, Londra tarihi, ev, deplasman) eklenir; eşitlik testi `match_index` dışındaki bütün
alanları karşılaştırır. Placebo'nun tohumu da `match_key`e bağlanır (DEFERRED 14l: bugün giriş SIRASINA bağlı,
`strategies.py:154`). Yinelenen anahtar (14g, 14r) bağlam kurulurken `ValueError`: iki karar + çift güncelleme
sessiz geçmez.

## 8. `final_eval` — tek, kayıtlı açılış (P5)

### 8.1 Ön kayıt

`config/faz3_preregistration.yaml` açılıştan ÖNCE commit'lenir: dondurulmuş `model_faz3.yaml`'ın sha256'sı,
kilit dosyasının sha256'sı, strateji listesi, karşılaştırmalar, bahis kuralı (`τ`), bootstrap tohumu ve tekrar
sayısı, "geçer/kalır" ölçütleri (§14/K3). Önerilen karşılaştırmalar (holdout, ana ligler; ek ligler ayrı tablo):

| # | Karşılaştırma | Ölçü |
|---|---|---|
| C1 | harman vs piyasa (kapanış öncesi `Avg`) | eşleştirilmiş ΔLL, bootstrap GA |
| C2 | DC, fit Elo, iskele Elo vs piyasa | ΔLL |
| C3 | harman bahisleri (§6.4) | ortalama CLV ve GA; Placebo ile yan yana |
| C4 | harman kalibrasyonu | eğim `b`, ECE |
| C5 | Ü/A 2.5 (DC, harman) | ΔLL, CLV (ikincil) |
| C6 | POST, tam durum (DEV + HOLDOUT + POST) | C1–C3'ün sonrası dönem karşılığı; canlı gölgeyle fark = boşluk cezası (§5.4) |

`final_eval`, ön kayıt dosyasının commit'lenmiş sürümüyle çalışma ağacındakinin aynı olduğunu, çalışma
ağacının temiz olduğunu ve `model_faz3.yaml`/kilit özetlerinin kayıttakiyle eşleştiğini açılıştan ÖNCE sınar;
biri tutmazsa açmadan çıkar. Açılışın `purpose` alanı `faz3:<ön kayıt sha256>` taşır.

### 8.2 Seçilmiş satır, anahtar değil (12i)

```
final_eval:  kayıt ve temizlik denetimleri → conn (TAZE, bekleyen yazım yok — §3/21)
             → open_holdout(conn, purpose=…) → load_matches(conn, catalog, lock=…, key=key)
             → satırlar (tuple[HistMatch, ...], ön kaydın istediği dönem/lig) → key bırakılır
             → walkforward.final_run(rows, config) (anahtar GÖRMEZ) → rapor
```

- `HoldoutKey` adının anıldığı yerler bir AST testiyle sınırlanır: `history/holdout.py`, `history/sync.py`,
  `backtest/final_eval.py`. Anahtar bir fonksiyona argüman olarak yalnız `load_matches`e verilir; dönüş
  değerinde, öznitelikte ya da modül düzeyinde saklanamaz.
- Burada `load_matches`in gerçek anahtarlı pozitif yolu ilk kez sınanır (14j): fake bağlantıyla birim testi
  ve açılıştaki gerçek sayım (`holdout` satır sayısı kilitteki 7.646 + 4.446 ile eşit olmalı, değilse rapor
  yazılmaz, kırmızı).
- 14h sertleştirmesi (ayrıştırıcının `_`-önekli yardımcılarına `history/` dışından erişim yasağı) açılıştan
  ÖNCE kapıya girer (§14/K11).

### 8.3 Tek açılış nasıl zorlanır (§14/K8)

- Uygulama: `final_eval`, `holdout_access_log`da `purpose LIKE 'faz3:%'` sayısı 0 değilse açmaz.
- Öneri ek olarak veritabanı: `0010_holdout_phase.sql` — `phase` sütunu (`faz3`, `faz4`, `faz5`) ve `phase`
  üzerinde tekil indeks; ikinci Faz 3 açılışı INSERT'te düşer. Append-only tetikleyici satır UPDATE/DELETE'i
  durdurur, sütun eklemeyi değil (mevcut 0 satır).
- **Prova:** gerçek açılıştan önce aynı kod yolu anahtarsız bir "sahte holdout" üzerinde koşar (E'nin son
  sezonu 2024/25, ön kayıttaki aynı karşılaştırmalar) — aynı makinede/runner'da, süre ve RSS ölçülür. Prova
  yeşil olmadan açılış yapılmaz.
- **Açılıştan sonra çöküş:** açılış sayılmıştır. Öneri: rapor ÜRETİLMEDİYSE ve git SHA'sı değişmediyse tek
  bir yeniden koşu, `faz3-rerun:<neden>` amacıyla ikinci bir kayıt olarak ve HANDOFF'ta ADIYLA sayılarak; kod
  değiştiyse holdout Faz 3 için harcanmış sayılır.
- Çıktı: `docs/reports/<tarih>-faz3-holdout.md` — yalnız toplu sayı; tahminlerin sha256'sı (tekrarlanabilirlik),
  ham satır yok. Faz 3 HANDOFF açılış sayısını `select count(*) from holdout_access_log` ile yazar.

## 9. Kapıya eklenenler ve her birinin nasıl kırmızı verdiği

Her satırın kırmızı verebildiği plan aşamasında MUTASYONLA kanıtlanır (Faz 1 §6.2; controller, `git archive`
kopyası, `PYTHONDONTWRITEBYTECODE=1`).

| # | Ne | Nerede | Kırmızı ne zaman |
|---|---|---|---|
| G1 | `sızıntı` alt sınırı yükselir (E1/E2, walk-forward bölge testleri, fit'in yalnız `observe` verisini gördüğü testler) | `verify.sh` `EXPECTED_MIN_LEAKAGE` (dalga sonunda ölçülür) | işaret silinir / test sayısı düşer |
| G2 | **Gelecek-fit kanaryası:** bir fitçiye gelecekteki bir sonucu enjekte eden sızdırılmış `observe` → DC/Elo/havuz tahmininde Oracle benzeri LL düşüşü; dürüst hatta kanarya 0 kazanç | `tests/test_model_leakage.py` (`leakage`) | fit penceresi `known_at < decision_at` yerine `≤` ya da tarih süzmesiz olursa |
| G3 | **Katlar arası sızıntı:** havuz ağırlığı sezon `s` için `s`'nin ya da sonrasının tahminini görürse | `tests/test_walkforward.py` (`leakage`) | kat sınırı bir sezon kaydırılırsa |
| G4 | **Bilinen sonuçlar (model)**, haftalık `history.yml` adımı: W1 harman LL ≤ piyasa LL + δ (E, havuzlanmış); W2 fit Elo LL < iskele Elo LL; W3 DC LL < "ev/beraberlik/deplasman oranı" taban çizgisi; W4 havuzlanmış kalibrasyon eğimi GA'sı 1'i içerir ya da raporlanır (kapı değil) | `backtest/selftest.py` genişler | fit bozulur, ağırlık yanlış yöne gider, DC yakınsamaz — W1'in doğal alt sınırı §6.3 |
| G5 | Holdout erişim kuralı genişler: `HoldoutKey` yalnız üç modülde; anahtar yalnız `load_matches`e argüman (12i); 14h | `tests/test_holdout_access_rule.py` | izinsiz modülde anma; anahtarın döndürülmesi/saklanması |
| G6 | Tek açılış: `final_eval` ön kayıt/temizlik/sayım denetimleri (fake bağlantı) + 0010 tekil indeks (DB bağlıyken) | `tests/test_final_eval.py`; `zincir` gibi DB bağlıyken koşan test | ikinci açılış, kirli ağaç, sha uyuşmazlığı |
| G7 | Belirlenimcilik: sentetik veride walk-forward tahmin özeti sabit | `tests/test_walkforward.py` | sıraya ya da küme yinelemesine bağlı sonuç |
| G8 | `paket-kurulu` scipy'ı da ister | `verify.sh` (dalga 0) | scipy import edilemez |

G4'ün sınırı: haftalık iş DB ister ve CI'da koşmaz (Faz 2 `Bilinen sonuçlar` ile aynı). Runner süresi 60 dk
(R84); DC ile süre dalga 0'da ölçülür, aşarsa W3 lig alt kümesine iner ve bu ADIYLA yazılır.

## 10. Canlı gölge (§14/K7 onaylanırsa)

- `live/shadow.py`: aktif her lig için salı ve cuma karar anından sonra (pg_cron → `workflow_dispatch`, RUNBOOK
  §3 deseni) canlı kurucu → strateji → `model_predictions` (append-only, RLS, TRUNCATE tetikleyicili; satır:
  maç kimliği, `match_key`, strateji, olasılıklar, bahis, `model_faz3.yaml` sha, git SHA, `decided_at`,
  `recorded_at` DB saati). Yayın YOK.
- CLV, mühürlenen kapanışla (`is_closing`) ve köprünün düzeltme önerisiyle birlikte haftalık rapora girer.
  Canlı gölge kredi HARCAMAZ (mevcut snapshot'ları okur); K6'nın ek snapshot'ı harcar.
- Gölge sayıları hiçbir hiperparametre seçimine GİRMEZ (sonrası dönemi spec §6.2'nin son ileri testidir).

## 11. Görevler ve dalgalar (plan bunları ayrıntılandırır)

| Dalga | Görev | Başlıca dosyalar | Kademe |
|---|---|---|---|
| 0 | scipy (tek controller commit'i) · ölçümler: DC fit süresi/RSS (ülke grubu başına), Elo `replay` süresi, 2019/20+ saatsiz satır sayısı (§3/37), 14g yinelenen sayımı, scipy tolerans | `pyproject.toml`, `uv.lock`, ölçüm belgesi | — |
| 1 | T1 DC (saf) | `model/dixon_coles.py` | K1 |
| 1 | T3 Elo fiti (saf + strateji) | `model/elo_fit.py` | K1 |
| 1 | T5/T4 havuz (saf) | `model/pool.py` | K1 |
| 1 | P2a ortak bağlam kurucusu + `match_key` + 14l | `backtest/context.py`, `harness.py`, `strategies.py` | K1 |
| 2 | P1 walk-forward + S'de seçim + `model_faz3.yaml` | `backtest/walkforward.py`, `model/strategies.py`, config | K1 |
| 2 | P2b canlı kurucu + E1–E3 | `live/context.py`, testler | K1 |
| 3 | G4 selftest genişlemesi · gölge (K7) · 0010 (K8) · 14h, 14j | `selftest.py`, `live/shadow.py`, migration'lar | K1/K2 |
| 4 | T6 walk-forward raporu → ön kayıt commit'i → prova → **tek açılış** → holdout raporu → kırmızı takım (fable) → Faz 3 HANDOFF | `final_eval.py`, raporlar | K1 |

Kurallar Faz 2 §12 ile aynı: tek-yazar taraması, en çok 4 paralel implementer, izole worktree, ortak dosyalar
(`verify.sh`, `pyproject.toml`, `ops_alert.py`) yalnız dalga 0/dalga sonunda, her commit'ten sonra tam kapı.
**Kırmızı takım açılıştan ÖNCE** koşar (holdout'un hiperparametre seçimi yoluyla sızması, bölge sınırları,
bayat durum koruması, ön kaydın değiştirilebilirliği); açılıştan sonra bulunan bir hata holdout'u geri getirmez.

## 12. Kapının ÖLÇMEYECEKLERİ (şimdiden)

1. **Canlı ↔ tarihsel eşitliği fiyat DEĞERİNDE kanıtlanmaz:** E1 aynı kaynağı taklit eden fikstürlerde
   özdeşliği, E3 gerçek veride yalnız yapısal alanları sınar. Kitap kümesi farkı (The Odds API ~28 kitap vs
   football-data'nın `Avg` kümesi) ölçülür, düzeltilmez.
2. **football-data'nın yayın gecikmesi ölçülmedi**; bayat durum koruması onu tahmin kaybına çevirir, ölçmez.
   Koruma yalnız grubun takımlarını arar; başka ülkedeki bir sonuç (grup dışı) zaten duruma girmez.
3. **Seçim bölgesi S'nin piyasa girdisi `BbAv`, E'ninki `Avg`:** havuz ağırlığının ilk katı farklı bir
   toplayıcıyla fit edilir.
4. **S'de başlama saati yok:** gün içi sıralama yaklaşık (§3/3); S'nin LL'si E'ninkiyle birebir kıyaslanmaz.
5. **Canlı `pre` fiyatı karar anından saatler önce toplanır** (06:22 UTC snapshot'ı, K6 onaylanmazsa);
   football-data'nınki öğleden sonra. Canlı CLV'nin tarihsel CLV'den farkının bir kısmı budur.
6. **AUT ve ek liglerde harman ve CLV tarihte ölçülmez** (§6.5).
7. **Boşluk cezası DEV simülasyonuyla ve `final_eval`in C6'sıyla ölçülür**; canlı gölgenin kendisi boşluklu
   durumla koşar (H1).
8. **Erteleme (§3/36), saatsiz 2019/20+ satırlar (§3/37), `Date` varsayımı (§3/38), katalog kilitte değil
   (§3/39)** Faz 3'te de açık; katalog sha256'sı `model_faz3.yaml`a yazılır (değişirse walk-forward reddeder),
   ama kilide girmez.
9. **Bootstrap maçları bağımsız sayar** (§3/9); havuz ağırlığı gibi katlar arası parametrelerin belirsizliği
   aralıklara girmez.
10. **Tek açılış bir kez harcanır:** açılıştan sonra bulunan bir kusur o açılışı geri getirmez; prova ve
    kırmızı takım bunu azaltır, ölçmez.
11. **Elo reyting grubu ülke varsayımı** (R94; "aynı ülkede aynı adlı iki kulüp yok") ölçülmedi.
12. **AST kuralları kazara girişi durdurur, kasıtlı kaçışı değil** (§3/27; 12h) — "stratejiler düşmanca kod
    değildir" varsayımı sürer.
13. **Kapı kâr ölçmez:** walk-forward ve holdout CLV'si bir baz çizgi kaydıdır; Faz 5'in staking'i ve EV
    eşiği burada yoktur.

## 13. Riskler

| # | Risk | Panzehir |
|---|---|---|
| R1 | Hiperparametrenin holdout'tan dolaylı sızması (açılış sonrası "bir ayar daha") | ön kayıt sha'sı `purpose`ta; tek açılış DB'de; açılış sonrası kod değişikliği Faz 3 sayılarını değiştirmez |
| R2 | DC hesap süresi/bellek (değişmez durum + haftalık fit × 20 yıl × 38 lig) | ülke grubu başına replay; kalıcı yapı; dalga 0 ölçümü; aşarsa fit sıklığı aylık ya da E yalnız canlı ligler — ADIYLA |
| R3 | scipy'nin platformlar arası kayan nokta farkı → belirlenimcilik testi titrer | yuvarlanmış özet, tolerans dalga 0'da ölçülür |
| R4 | Havuz ağırlığının aşırı uyumu (az maçlı lig) | ağırlık ≥ 0, lig N'i küçükse havuzlanmış ağırlık; ölçüt raporda |
| R5 | Canlı gölgenin bayat durum yüzünden az tahmin üretmesi | sayılır; K5'in ek senkronu; K1 |
| R6 | Açılışta çöküş (OOM, bağlantı) | prova aynı kaynakla; çöküş kuralı §8.3 |
| R7 | İz A'nın lig kümesi ya da kredi hesabı değişir | canlı kapsam girdi; kurucu ve gölge `leagues.yaml`dan okur, lig sayısına bağlı değil |
| R8 | Kredi bütçesi (500/ay) | Faz 3 kendi başına kredi harcamaz; K5/K6'nın kredili seçenekleri ayrı onay |

## 14. Onay bekleyen kararlar

Her birinde asistanın önerisi **kalın**. Faz 2'deki gibi "önerine bırakıyorum" da bir cevaptır; K1 ve K3
holdout ve spec §9'un kapısına dokunduğu için AYRICA onay ister.

| # | Karar | Seçenekler | Öneri ve gerekçe |
|---|---|---|---|
| **K1** | Holdout boşluğu ve canlı durum (§5.4) | H1 boşluk + ölçülen ceza, holdout Faz 5'ten sonra serbest · H2 Faz 3 açılışından sonra sonuçları serbest bırak, Faz 4/5 kapısı POST'a · H3 yalnız-durum açılışları | **H1** — üç açılış hakkını korur; ceza iki yoldan ölçülür; canlı Faz 3'te zaten gölge |
| **K2** | Walk-forward şeması (§5.2) | A S'de dondurulmuş hiperparametre + genişleyen ağırlık katları · B iç içe kayan başlangıç · C tek bölme | **A** — E sayıları temiz örneklem dışı ve ucuz; B'nin süresi ölçülmeden seçilmez (dalga 0 ölçümü B'yi mümkün gösterirse duyarlılık olarak eklenir) |
| **K3** | Faz 3 kapısının geçme ölçütü | P süreç + akıl sağlığı (ön kayıt, tek açılış, eşitlik, W1: harman piyasadan anlamlı kötü değil); holdout sayıları KAYDEDİLİR, kenar şartı yok · Q holdout CLV > 0 şart · R yönsel beklentiler ön kayıtta geç/kal olarak yazılır ama faz geçişini bağlamaz | **P** — 1X2'de Elo+DC'nin kapanışı yenmesi beklenmez; Q Faz 3'ü tasarım gereği düşürür ve Faz 4'ün kıyas tabanını geciktirir |
| **K4** | Model ailesi | fit Elo + DC + log havuz, 1X2 birincil + Ü/A 2.5 ikincil · yalnız 1X2 · havuzsuz (yalnız modeller) | **fit Elo + DC + havuz, Ü/A ikincil** — Ü/A DC'den bedava, spec §2/2 |
| **K5** | Canlı `observe` akışının sonuç kaynağı | football-data POST + bayat durum koruması + ücretsiz cuma senkronu · The Odds API skorları (kredi) · ikisi | **football-data + koruma + cuma 09:50 UTC ek senkronu** — kredi yok, satırlar tarihsel kaynakla aynı; gecikme ilk kez ölçülür |
| **K6** | Canlı karar anı fiyatı | mevcut 06:22 UTC snapshot · salı/cuma karar anında ek snapshot (≈ aktif lig × ~9 kredi/ay; İz A'nın kredi hesabına bağlı) | **mevcut snapshot** Faz 3'te; ek snapshot İz A'nın kredi ölçümünden sonra ayrı onayla |
| **K7** | Faz 3'ün canlı kapsamı | bütün aktif liglerde gölge tahmin (append-only tablo, yayın yok) · canlı tahmin yok (yalnız kurucu + eşitlik) · yalnız A kademesi (T1, N1, B1, AUT) | **bütün aktif liglerde gölge** — kredi harcamaz, canlı CLV örneği şimdi birikmeye başlar |
| **K8** | Tek açılışın zorlanması ve çöküş kuralı | uygulama denetimi · + DB `phase` tekil indeksi (0010) · çöküşte: rapor yoksa ve SHA aynıysa tek, kayıtlı yeniden koşu / hiç yeniden koşu yok | **uygulama + DB + prova; tek kayıtlı yeniden koşu** |
| **K9** | Dixon-Coles grubu | ülke grubu (kademeler birlikte, R94) · lig başına | **ülke grubu** — terfi/küme düşme takımları bağlanır; süre dalga 0'da ölçülür, aşarsa lig başına |
| **K10** | AUT ve ek ligler | yalnız model (LL, kalibrasyon) tarihte; canlıda gölge harman · Faz 3'ün dışında | **yalnız model + canlı gölge** — tarihte ölçülemeyen şey iddia edilmez |
| **K11** | Açılıştan önce kapatılacak ertelenenler | 14h (özel yardımcı erişim kuralı), 14j (anahtarlı pozitif yol), 14l (Placebo tohumu), 14k (kanarya iki yuva) | **14h, 14j, 14l zorunlu; 14k isteğe bağlı** (ucuz, aynı dosya) |
| **K12** | CLV bahis kuralının eşiği `τ` | birincil `τ` ve duyarlılık kümesi | **birincil `τ = 0.02`, duyarlılık {0, 0.05}**, önceden kayıtlı; `τ` E'de seçilmez (seçilirse holdout karşılaştırması örneklem içi olur) |

### 14.1 Kullanıcının kararları (2026-09-23) — Ruling

Kullanıcı on iki kararın hepsinde önerilen seçeneği onayladı; K1 ve K3 ayrıca açıkça onaylandı. Biçim: karar —
*yanlışsa bedeli*.

| Ruling | Karar | Seçilen | Yanlışsa bedeli |
|---|---|---|---|
| **R128** | K1 holdout boşluğu | **H1**: canlı ve anahtarsız her yol DEV + POST; boşluk cezası DEV simülasyonu ve `final_eval` C6 ile ölçülür; holdout canlı duruma ancak Faz 5 açılışından SONRA serbest kalır | Faz 3–5 canlı gölgesi bir sezon bayat durumla koşar |
| **R129** | K2 walk-forward şeması | **A**: hiperparametreler S'de (2012/13–2018/19) bir kez seçilip `config/model_faz3.yaml`da dondurulur; E'de (2019/20–2024/25) raporlanır; havuz ağırlığı genişleyen sezon katlarıyla | hiperparametre kayması yakalanmaz |
| **R130** | K3 kapı ölçütü | **P**: süreç + akıl sağlığı (ön kayıt, tek açılış, eşitlik testi, W1); holdout sayıları kaydedilir, kenar şartı YOK | kötü bir baz çizgi de fazı geçer — Faz 4 onu kıyas tabanı olarak alır |
| **R131** | K4 model ailesi | fit Elo + Dixon-Coles + log-doğrusal havuz; 1X2 birincil, Ü/A 2.5 ikincil | Ü/A kodu ve raporu ek iş |
| **R132** | K5 canlı sonuç kaynağı | football-data POST + bayat durum koruması + cuma 09:50 UTC ek senkronu; kredi yok | gecikmeli sonuçlar tahmin kaybına döner |
| **R133** | K6 canlı karar anı fiyatı | mevcut 06:22 UTC snapshot; ek snapshot İz A'nın kredi ölçümünden sonra ayrı onayla | canlı `pre` fiyatı tarihsel olandan saatler erken |
| **R134** | K7 canlı kapsam | bütün aktif liglerde gölge tahmin (append-only `model_predictions`, yayın yok) | bir migration, bir iş akışı |
| **R135** | K8 tek açılış | uygulama denetimi + `0010_holdout_phase.sql` (faz başına tekil) + 2024/25 üzerinde tam prova; çöküşte YALNIZ rapor üretilmediyse ve git SHA aynıysa tek, kayıtlı yeniden koşu | ikinci kayıt HANDOFF'ta adıyla sayılır |
| **R136** | K9 DC grubu | ülke grubu (kademeler birlikte); süre dalga 0'da ölçülür, aşarsa lig başına ve ADIYLA | ince bağlantılı grupta güçler zayıf tanımlı |
| **R137** | K10 ek ligler | tarihte yalnız model (LL, kalibrasyon, kapanışa uzaklık); harman ve CLV canlı gölgede | AUT'ta harman iddiası canlı veri birikene dek yok |
| **R138** | K11 açılış öncesi ertelenenler | 14h, 14j, 14l zorunlu; 14k isteğe bağlı (plan dahil ediyor, aynı dosya) | küçük üç görev |
| **R139** | K12 CLV eşiği | birincil `τ = 0.02`, duyarlılık {0, 0.05}, ön kayıtta sabit, E'de seçilmez | τ optimum olmayabilir; bu bilinçli |

### 14.2 Plan yazımında netleşenler (2026-09-23)

**Ruling numaraları:** K1–K12 önce R122–R133 diye yazılmıştı; İz A'nın defteri R122–R127'yi kullandığı için
R128–R139'a kaydırıldı (R122→R128 … R133→R139). **Taban:** plan İz A birleşmiş `main`e (`a398c31`) karşı
yeniden doğrulandı; 8 aktif lig, `aut.1` kapalı — AUT canlıda (gölge, E3) görünmez, K10/R137'nin "canlıda gölge
harman" kısmı AUT açılana (kredi onayı) dek ölçülmez.

TDD planı (`../plans/2026-09-23-faz3-model-walkforward.md`) yazılırken kod bir kopyada koşuldu; tasarımdan sapan
ya da onu netleştiren kararlar planda P1–P25'tir. Tasarım metnini değiştirenler:

- **P1** — §7.1–7.4: bağlam yalnız `Avg` 1X2 kapanış öncesi fiyatını taşır; canlı defter yalnız 1X2 toplar, başka
  kitap/market bağlamda kalsaydı E1 eşitliği sözde kalırdı. Faz 2'nin bir testi buna göre güncellenir.
- **P7** — §5.1: ek liglerde S `2013-01-01`den başlar (2012 ısınma).
- **P8, P9** — §6.3, §9 G4: lig kendi eğitim satırı < 1.000 ise havuzlanmış ağırlık; W1 = ortalama ΔLL ≤ δ = 0.001.
- **P11** — §6.1: Elo'nun 1X2 eşlemesi sıralı lojit değil `P(D) = δ·4E(1−E)` (tek parametre, kapalı biçim fit).
- **P20** — §11: görev numaraları — gölge Task 11, modelin bilinen sonuçları Task 12.
- **R141** (controller, plan incelemesi I1) — §7.3: bayat durum koruması modelin BÜTÜN grup liglerine genişler;
  defterde fikstürü olmayan ligler (E1–E3, D2, I2, SP2, F2 …) için football-data'nın kendi tarihlerinden
  (sezgisel: olağan maç günü aralığının %95'liği + 1 gün).
- **Plan incelemesi C1** — §8.3: yinelenen maç denetimi `history/` içinde, BÜTÜN dönemlerde (holdout dahil) ve
  anahtar yokken koşar; holdout'taki bir yineleme açılışı harcamaz (exit 12). I4: açılış sonrası her arıza exit 14.
- **P25** — §10: haftalık gölge CLV raporu Faz 3'te yazılmaz (Faz 4'ün ilk görevi); R128'nin boşluk cezası bu fazda
  DEV simülasyonu (`walkforward --gap`) ve `final_eval` C6 ile ölçülür, canlı ayağı o rapora kadar ölçülmez.

### 14.3 Controller kararları (2026-09-23) — kullanıcı P1/P9/P11/P25'i controller'a bıraktı

| Ruling | Konu | Karar | Yanlışsa bedeli |
|---|---|---|---|
| **R142** | P11 · §6.1 Elo beraberliği | `δ·4E(1−E)` ve sıralı lojit (M5) İKİSİ de S seçiminin ızgarasında tek kategorik hiperparametre (`draw_form`); yalnız seçilen biçim ve S'de fit edilen parametreleri donar ve açılışa girer | seçim ızgarası bir boyut büyür |
| **R143** | P9 · §9 G4 W1 | W1 daha kötü olmama sınaması: maç başına LL(harman) − LL(piyasa) ortalamasının %95 bootstrap aralığının ÜST ucu ≤ 0.001; bootstrap Faz 2'nin (`market.metrics.bootstrap_mean`, maç düzeyi, tohum 20260922, düzey 0.95, B = 2.000 — `market/efficiency.py` RESAMPLES/SEED/LEVEL) | nokta tahmininden sıkı: gerçek veride W1 daha kolay kırmızı |
| **R144** | P1 · §7.1–7.4 | bağlam yalnız `Avg` 1X2 kapanış öncesi fiyatını taşır — yazıldığı gibi kabul | başka kitap/market okuyan strateji bağlamdan alamaz |
| **R145** | P25 · §10, §5.4 | haftalık gölge CLV raporu Faz 4'ün ilk görevi; R128'in canlı ayağı o zamana dek ölçülmez — yazıldığı gibi kabul | ilk haftaların gölge sayıları okunmaz |

Plan yazımında R142'nin uygulanması: **R146** sıralı lojit küresel ve simetrik (tek `s`, tek `c`; M5'teki lig başına
kesişimler yok) · **R147** Elo adayları S'de `quadratic` biçimle oynatılır, E geri okunur, adayın biçimi o E'de
fit edilir (reyting yolu biçimden bağımsız). R141 düzeltildiği için P26 yoktur.

## 15. Karar kaydı

| # | Karar | Bölüm |
|---|---|---|
| M1 | xG varyantı ve hakem özelliği Faz 3'ten düşer | §1 |
| M2 | Bölgeler: ısınma / S 2012/13–2018/19 / E 2019/20–2024/25 (ek ligler tarihle) | §5.1 |
| M3 | Walk-forward şeması (K2) | §5.2 |
| M4 | Holdout boşluğu (K1) | §5.4 |
| M5 | Elo: sıralı-lojit 1X2, ortalamaya dönüş, terfi başlangıcı; fit S'de | §6.1 |
| M6 | DC: zaman sönümlü, ρ, sırt cezası, haftalık fit, yakınsamayan fit tahmin vermez; grup (K9) | §6.2 |
| M7 | Log-doğrusal havuz, lig başına, ağırlık ≥ 0 | §6.3 |
| M8 | CLV bahis kuralı sabit ve ön kayıtlı (K12) | §6.4 |
| M9 | Ortak `MatchRecord` son adımı; `match_key`; Placebo tohumu anahtardan | §7.1, §7.5 |
| M10 | Canlı kurucu: son snapshot ≤ karar anı, kitap ortalaması; sonuç kaynağı (K5) ve bayat durum koruması | §7.2–7.3 |
| M11 | Eşitlik testi E1–E3 | §7.4 |
| M12 | `final_eval`: ön kayıt, seçilmiş satır, tek açılış (K8), prova | §8 |
| M13 | Kapı eklemeleri G1–G8 | §9 |
| M14 | Canlı gölge (K7) | §10 |
| M15 | Bağımlılık: scipy (dalga 0); pandas/statsmodels yine yok | §11 |
