# Faz 2 — kırmızı takım sızıntı denetimi (Task 11, T6)

**Tarih:** 2026-09-22 · **Denetlenen:** `main` `aec668f` · **Denetçi:** bağımsız ajan (fable), kabuklu
`general-purpose` · **Düzeltmeler:** `b345b06` (merge `6be8201`). Rapor yalnız kod ve sonuç anlatır;
bütün saldırılar sentetik veriyle, izole bir `git archive` kopyasında, ağ ve veritabanı olmadan koşuldu.

## Yöntem

Görev: "bu backtest'te ileriye bakma hatasını bul". Denetçi tasarım §4.5, §5, §7, §10'u, planın
kısıtlarını ve `history/`, `backtest/`, `market/` modüllerini okudu; her şüpheyi ÇALIŞTIRARAK sınadı:
sızan bir strateji ya da kural ihlali yazıp harness'ın ve kapının onu reddedip reddetmediğini ölçtü.

## Denenen saldırılar

| # | Saldırı | Hedef | Sonuç |
|---|---|---|---|
| S1 | 2019-07-01 → 2026-06-30 her gün × her 15 dk başlama (iki yaz saati yorumu) + saatsiz maç | karar/sonuç anı kuralı (D4, D5), kenar günleri, gece yarısı | 245.472 çift, **0 ihlal** |
| S2a | Dürüst "kaydedici" strateji, 3 lig × 700 gün, karışık giriş sırası, gece başlamaları | olay akışı, eşzamanlı olaylar, `observe` | karardan sonra bilinen sonuç **0** |
| S2b | Bağlamda `pre` dışı fiyat evresi | `DecisionContext` tip ayrımı | **0** |
| S2c | Bağımsız point-in-time Elo ≟ harness Elo'su | terfi eden takım, sıralama | **0 / 2.245 fark** |
| S2e | Ters sıralı olaylar | savunma katmanı (§10/3) | `LeakageError` |
| S3 | 16 kilit mutasyonu (fiyat sütunları, başlama, tarih, gol, sezon, dönem satırları) | kilidin kapsamı (§5.2) | Faz 2'nin kullandığı her sütun `LockViolation` |
| S4 | `load_files` + `parse_file` ile anahtarsız holdout; AST kuralı | holdout erişimi (§5.3) | **sızdı → F1** |
| S5 | Aynı maç iki sezon dosyasında (pencereler Haz–Tem çakışır) | çift satır | iki karar → F3 |
| S6 | `pre == close` verisi | K1/K4 duyarlılığı | K1 yakalar, K4 kör → F2 |
| S7 | Holdout ve sonrası satırları verimlilik, yöntem seçimi ve selftest'e | holdout süzgeci | çıktılar **birebir eşit** |
| S8 | Harness kasten sızdırıldı (bütün sonuçlar önce) + sonuç kullanan Oracle | K4'ün harness sızıntısına duyarlılığı | Oracle log loss 0,105; **K4 yine geçti → F2** |
| S9 | Placebo seçimi giriş sırasına bağlı mı | tohum | 775 / 1.200 seçim değişti → F5 |
| S10 | Sezon düzeyi normalizasyon araması | §10 listesi | strateji tarafında yok |

Harness'ın olay akışında, zaman kuralında ve tip ayrımında çalıştırılarak sınanan **hiçbir ileriye
bakma bulunmadı**; bulgular çevre korumalardadır.

## Bulgular ve kapanışları

| # | Önem | Bulgu | Kapanış |
|---|---|---|---|
| F1 | Important | `load_files` + `parse_file` açık API'si holdout satırlarını anahtarsız kuruyordu; AST kuralı yalnız `open_holdout`, `_HOLDOUT_SEAL`, `_load_all`ı koruyordu | **Kapandı (R119):** kural `load_files`, `parse_file`, `sync._parsed`ı korur; izin yalnız `history/sync.py` ve `history/__main__.py`. Yeniden inceleme `import *`, `importlib`, izinli modül üzerinden erişim, yeniden ihraç, `getattr`/`attrgetter` biçimlerinin yakalandığını doğruladı |
| F2 | Important | K4 (Placebo CLV) harness sızıntısını ölçmez: Placebo sonucu yok sayar, CLV sonuçtan bağımsızdır | **Kapandı (R120):** `leakage` işaretli Oracle kanaryası (`tests/test_harness.py`) — dürüst harness'ta 252 maçta 0 sonuç-bilgili tahmin, sızdırılan harness'ta kırmızı; K4'ün açıklaması "fiyat sütunu negatif kontrolü; harness sızıntısını ölçmez" |
| F3 | Minor | Sezonlar arası yinelenen satır iki karar ve çift Elo güncellemesi üretir | Ertelendi (R121): gerçek veride yinelenen (lig, tarih, ev, deplasman) satırı **0** (38 lig, dev + sonrası) |
| F4 | Minor | Mühür hesaplanmış adla (`vars()` + `endswith`) taklit edilebilir | Kabul: bilinen sınır (DEFERRED 12h, 12i) — "stratejiler düşmanca kod değildir" varsayımı |
| F5 | Minor | Placebo tohumu maç kimliğine değil giriş pozisyonuna bağlı | Ertelendi (R121): K4 sonucu havuz düzeyinde; sıra sabit (lig koduyla sıralı) |

## Açık kalanlar (Faz 2 kapısının ölçmediklerine)

- Ayrıştırıcının özel yardımcıları (`_decode` → `_records` → `_context` → `_row`) başka bir modülden dört özel
  adla çağrılırsa holdout satırı kurar; AST kuralı görmez — hesaplanmış adla aynı sınıf, kasıtlı yeniden kurma.
- Önbelleğe ham SQL ile erişim (`hist_files`) yalnız bayt verir; satıra çevirmek korunan `parse_file`ı ya da
  yukarıdaki özel yolu ister.
- Oracle kanaryası sonuçların **≥ 10 saat** erken sızmasında kırmızıdır; 1–9 saatlik sızıntıyı mevcut tam-an
  testleri (`test_harness.py`, `test_events.py`) yakalar.
- Yansıma yoluyla `HistMatch`e ulaşma (DEFERRED 12h).
