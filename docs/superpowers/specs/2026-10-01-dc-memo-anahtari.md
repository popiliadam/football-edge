# Dixon-Coles memo anahtarı — tasarım notu (DEFERRED 16g)

**Tarih:** 2026-10-01 · **Durum:** TASARIM NOTU, kod değişikliği yok. Uygulama Faz 4'ün `model/strategies.py`ye
dokunan ilk değişikliğiyle (§7).
**Girdi:** DEFERRED 16g · kırmızı takım `docs/reports/2026-09-23-faz3-sizinti-denetimi.md` B1 / şüphe 4 ·
`docs/phases/03-baz-model/HANDOFF.md` §1, §3.3/9 · kod `30bf3bc` (`integ/s10`).
**Ölçüm:** yalnız SENTETİK veri (`tests/model_builders.py`, `tests/backtest_builders.py`); holdout, DB, ağ yok.
Betikler depo dışında, oturum çalışma alanında (`.superpowers/sdd/2026-10-01-oturum10-kucuk-borclar/t6/`, gitignored):
`t6-b1-olcum.py` (B1 + prototipler + ölçek), `t6-e2-bos-olcum.py` ve `t6-e2-fark.py` (yan bulgu §6),
`t6-c-iska.py` ve `t6-pytest-bekcili.py` (düzeltme turu 1: (c)'nin ıska yolu, §3/(c)). Prototipler
`DixonColesStrategy`nin alt sınıflarıdır ya da `params`ı süreç içinde değiştirir; depo kodu değişmedi.
**Düzeltme turu 1 (2026-10-01):** bağımsız inceleme I1 — ilk sürüm (c)'nin bekçisini yalnız isabette okuyordu;
ıskada `memo.latest` başka soydan sıcak başlangıç verebiliyordu. Bekçi ıska denetimiyle genişletildi (§3, §3.1, §5,
§7); §6 HANDOFF okuması ve E1 notu düzeltildi; (a) için test planı olmadığı açıkça yazıldı (§5).
**Düzeltme turu 2 (2026-10-01, bütün-dal son incelemesi F2):** bu not T7'den (`5306837`) önce yazıldı; T7 E2'yi iki
ayakta taze nesneyle kurdu. §5/3, §6 ve §7'deki E2 cümleleri buna göre güncellendi. Ayrıca §3 (c)'de `params`ın
üçüncü kaynağı (soğuk fit) sayıldı, §3.1'de iki komşu satırın ölçek farkı yazıldı.

## 1. Bugünkü mekanizma

| Yer | Ne yapar |
|---|---|
| `src/football_edge/model/strategies.py:35-40` | `_FitMemo`: `fits[(grup, fit günü)] → DCParams \| None` ve `latest[grup] → DCParams` (sıcak başlangıç). Değişebilir, bilinçli istisna |
| `strategies.py:70` | `memo` alanı `compare=False`; `observe` (`:85-91`) `replace(self, history=…)` ile yeni nesne kurar — **memo nesnesi aynen taşınır**: bir kök nesneden türeyen bütün durumlar tek memo'yu paylaşır |
| `strategies.py:93-103` | `params(grup, at)`: anahtar yalnız `(grup, at)`. İsabetsizlikte geçmiş düzleştirilir, `fit(records, at=…, start=latest)`; `latest` yalnız `fitted_on < at` ise başlangıç olur (`:96-97`) ve yalnız daha yeni günle güncellenir (`:101-102`) |
| `strategies.py:109` | `predict` fit gününü `fit_day(karar günü, cadence_days)` ile seçer |
| `src/football_edge/model/dixon_coles.py:77-80` | `_used`: yalnız `day < at` ve pencere içindeki maçlar fit'e girer → memo geleceği taşıyamaz |
| `dixon_coles.py:148-161` | `_start`: önceki fit'in parametreleri L-BFGS-B'nin başlangıç noktası olur — sonuç başlangıca **bit düzeyinde** bağlıdır (yakınsama toleransı kadar) |

Yapım yerleri (üçü de oynatma/slot başına TAZE nesne; B1 üretimde tetiklenmez):
`backtest/wf_run.py:54-71` (`model_strategies`; 1X2 ve Ü/A aynı memo'yu `:69`da bilerek paylaşır — aynı maçlar,
aynı fit) → `wf_run.py:86`, `model_selftest.py:63`, `final_eval.py:180` · `backtest/selection.py:164` (`dc_loss`,
grup başına) · `live/shadow.py:84` (`_states`, slot başına).

**Neden bugün aynı `(grup, at)` bir oynatmada hep aynı veriyi görür:** karar anı karar gününün 12:00 Londra'sıdır
(`backtest/timeline.py:41`, salı/cuma); sonuç başlama + 3 saatte, saatsizse ertesi gün 03:00 Londra'da bilinir
(`timeline.py:49-52`). `day < at` olan her maçın sonucu, fit günü `at` olan ilk karardan önce gözlenmiş olur;
aynı andaki olaylarda karar sonuçtan önce gelir (`events.py`). Kadans 7'de salı ve cuma kararı aynı pazartesiye
düşer; arada gözlenen çarşamba sonuçları `day ≥ at` olduğundan fit'e girmez. Bu, (a)/(b)'nin bayt eşliği
iddiasının dayanağıdır (§4) — gerçek veride ölçülmedi (§5/6).

## 2. B1 — sentetik yeniden üretim

**Senaryo:** aynı kök nesne önce tam kümeye (`main_history(2019, 2023)`, 5 sezon × 56 maç), sonra 2022/23'ü
çıkarılmış kümeye oynatılır; 2023/24'ün 56 tahmini karşılaştırılır. **B1'** (kırmızı takımda yoktu): aynı küme,
2022/23'ün golleri ev↔deplasman çevrilmiş — gözlem SAYISI aynı, İÇERİK farklı.

```bash
# worktree kökünden
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. uv run python \
  .superpowers/sdd/2026-10-01-oturum10-kucuk-borclar/t6/t6-b1-olcum.py
```

| Varyant | B1: tam kümeyle özdeş (yeniden kullanılan / taze) | B1: max \|yeniden − taze\| | B1': tam kümeyle özdeş | B1': max \|yeniden − taze\| |
|---|---|---|---|---|
| mevcut `(grup, at)` | **56/56** / 0 | 1,74e-01 | **56/56** | 6,49e-01 |
| düz sayı (toplam gözlem) | 0 / 0 | 2,18e-05 | **56/56** | 6,49e-01 |
| (a) `at`ten önceki gözlem sayısı | 0 / 0 | 2,18e-05 | **56/56** | 6,49e-01 |
| (b) `at`ten önceki gözlemlerin özeti | 0 / 0 | 2,18e-05 | 0 | 3,22e-05 |
| (c) anahtar aynen + soy bekçisi | `MemoReuseError` (`2023-08-04`, 2022/23 sonrası ilk isabet) | — | `MemoReuseError` (`2022-08-12`, ilk çevrilmiş turdan sonraki ilk isabet) | — |

Okuma:
- **B1 yeniden üretildi:** mevcut kodda yeniden kullanılan nesne 2023/24'ün 56/56 tahminini tam kümeninkiyle
  BİREBİR döndürür (kırmızı takımın 56/56'sı); taze nesne 0/56.
- **İkinci kanal — sıcak başlangıç:** (a)/(b) yanlış fit'i taşımayı keser, ama yeniden kullanılan nesne taze nesneyle
  hâlâ bayt eşit DEĞİL (0/56, fark 2e-05 mertebesi). Neden: `memo.latest` ilk oynatmanın SON fit'ini tutar
  (`fitted_on` = 2024); ikinci oynatmada `latest.fitted_on < at` tutmaz → fit'ler soğuk başlar, taze nesneninkiler
  önceki günden sıcak. Bilgi sızmaz (başlangıç noktası, veri değil), ama yeniden üretilebilirlik bozulur.
- **(a) içerik değişimini görmez:** sayı aynı kalınca (B1') memo isabeti sürer — veri düzeltmesi (gol düzeltilen
  satır) tam bu biçimdedir.

## 3. Seçenekler

**(a) `at`ten önceki gözlem sayısı.** Anahtar `(grup, at, n_before)`. Ucuz hesap için parça başına en büyük gün
özeti gerekir ("sıralı parça yapısı": `Chunks` yanında parça başına `max(day)`; dolu parçalar `observe` boyunca aynı
demet nesnesi olduğundan özet bir kez hesaplanır). Gözlemler gün sırasıyla gelmese de doğru: `max_day < at` olan
parça bütün sayılır, sınır parçası taranır.

**(b) Maç kümesinin kimliği (özet).** Anahtar `(grup, at, özet)`, özet = `day < at` gözlemlerin içerik özeti; dolu
parça başına özet bir kez, sınır parçası süzülerek. **Tuzak (ölçüldü):** özet parça SINIRINA bağlı olmamalı. İlk
prototip boş süzülmüş parçayı da özete katıyordu; kadans 7'de salı ile cuma arasında bir parça mühürlenince özet
değişti → 2 fazla fit, soğuk başlangıç (`latest.fitted_on == at`), **bayt farkı**. Boş parça atlanınca düzeldi.

**(c) Her oynatmada yeni nesne, bekçiyle.** Anahtar ve fit AYNEN kalır. Memo her girdiye bir mühür ekler: fit
anındaki toplam gözlem sayısı `k` ve ilk `k` gözlemin (gözlem SIRASIYLA) özeti. Bekçi `params`ın İKİ yolunda da
okur:
- **isabette:** `(grup, at)` girdisinin mührü şimdiki akışın öneki değilse `MemoReuseError`;
- **ıskada:** `memo.latest[grup]` varsa onun mührü (`(grup, latest.fitted_on)` girdisininki) şimdiki akışın öneki
  değilse `MemoReuseError` — fit başka soyun parametresinden sıcak başlamaz.

`params`ın çıktısı üç kaynaktan gelir: memo girdisi, `start = latest` ile fit, ya da `latest` yokken veya
`latest.fitted_on ≥ at` iken soğuk fit. İlk ikisi mühürlü; soğuk fit yalnız şimdiki akışı kullanır, yabancı soy
taşıyamaz.
Aynı soyda akış yalnız uzar → bekçi hiç tetiklenmez; 1X2/Ü-A paylaşımı aynı maçları aynı sırada gözler → geçer;
başka küme → ilk isabette ya da ilk ıskada adıyla düşer (sessiz değil). Ek yapı yok: ıska denetimi aynı mühür
makinesini kullanır. Statik ek (isteğe bağlı): yapım yerlerini sabitleyen AST testi — 16h'deki kaçışları görmez,
yalnız kazara girişi durdurur.

**Neden ıska denetimi gerekir (ölçüldü, `t6-c-iska.py`; inceleyicinin sondasıyla aynı sonuç):** aynı nesne önce tam
kümeye, sonra AYNI maçlar +3 gün kaydırılmış kümeye (cumartesi → salı; kadans 1'de fit günleri ayrık, memo hiç
isabet almaz) oynatıldı:

| İkinci küme | mevcut | (c) yalnız isabet | (c) isabet + ıska |
|---|---|---|---|
| ayrık anahtar (+3 gün) | hata yok · 4/224 taze ile bayt eşit · max fark 4,41e-05 | **aynı: hata yok · 4/224 · 4,41e-05** | `MemoReuseError` (ıska, `2020-08-04`; `latest` = `2023-11-03`) |
| B1 (2022/23 çıkarıldı) | hata yok · 112/168 | `MemoReuseError` (isabet, `2023-08-04`) | `MemoReuseError` (isabet, `2023-08-04`) |
| B1' (2022/23 golleri çevrildi) | hata yok · 116/224 | `MemoReuseError` (isabet, `2022-08-12`) | `MemoReuseError` (isabet, `2022-08-12`) |

Yalnız isabette okuyan bekçi ayrık anahtarlı yeniden kullanımda mevcut kodla birebir aynı davranır: hata yok,
yabancı soydan (ya da `latest.fitted_on ≥ at` olduğu için soğuk) başlayan fit'ler, taze nesneyle bayt farkı.
Yanlış pozitif yok: isabet + ıska bekçisi dört taze senaryoda (§4) bayt eşit, fit sayısı 56/56/112/56 (= mevcut);
`DixonColesStrategy.params`a süreç içinde takılıp tam pytest koşuldu (`t6-pytest-bekcili.py`): `3086 passed,
50 skipped`, `MemoReuseError` 0.

### 3.1 Karşılaştırma

| | (a) sayı | (b) özet | (c) bekçi (isabet + ıska) |
|---|---|---|---|
| B1 (sayı farklı) | düzeltir | düzeltir | **reddeder** (hata) |
| B1' (sayı aynı, içerik farklı) | **görmez** (56/56 taşır) | düzeltir | reddeder |
| Ayrık anahtarlı yeniden kullanım (+3 gün; memo isabeti yok) | hata yok · 4/224 taze ile bayt eşit · 4,41e-05 (anahtar zaten ayrık; sıcak başlangıç kanalı) | aynı (4/224 · 4,41e-05) | reddeder (ıska denetimi); yalnız isabet okuyan bekçi GÖRMEZ (4/224 bayt eşit, 4,41e-05) |
| Sıcak başlangıç kanalı (yeniden kullanım ≠ taze) | kalır (2e-05) | kalır (2–3e-05) | ıska denetimiyle kapanır: `start` yalnız mühürü şimdiki akışın öneki olan `latest`ten gelir; değilse hata |
| Taze oynatmada bayt eşliği (sentetik, §4) | eşit | eşit (sınır tuzağı düzeltilince) | eşit — anahtar, fit ve `start` değişmez; bekçi aynı soyda tetiklenemez |
| Fit sayısı, kadans 7 haftada iki tur | 56 (= mevcut) | 56 (= mevcut) | 56 (= mevcut) |
| Anahtar maliyeti, 45 bin gözlem / 176 parça (sıcak) | 0,066 ms/çağrı | 0,090 ms/çağrı | 0,064 ms/isabet; ıskada bir önek denetimi daha (fit'in yanında ihmal edilebilir) |
| Yapı değişikliği | parça özeti | parça özeti + parça özeti hash'i | parça özeti hash'i + girdi başına mühür; `Chunks` aynen |
| Memo semantiği (strategies.py docstring) | genişler: "aynı gün, farklı geçmiş → farklı fit" | genişler | aynı kalır; kötüye kullanım hata olur |

İki komşu satırın ölçeği farklıdır. "Ayrık anahtarlı yeniden kullanım" satırının 4,41e-05'i ikinci kümenin bütün 224
tahminidir (`t6-c-iska.py`). "Sıcak başlangıç kanalı" satırının 2e-05 / 2–3e-05'i yalnız 2023/24'ün 56 tahminidir
(§2: B1 2,18e-05, B1' (b) 3,22e-05). Bütün kümede (b) için ölçülen fark B1'de 2,18e-05 (168 tahmin), B1''de 4,22e-05
(224), ayrık anahtarda 4,41e-05 (224). Kanal bu yüzden 2–4e-05 mertebesindedir.

Ölçek satırının bağlamı (`t6-b1-olcum.py` §4, 45 bin rastgele gözlem, 92 takım): mevcut isabetsizlikte geçmişi
düzleştirmek 0,57 ms, pencerede 5.400 maçlı bir soğuk fit 13 ms (rastgele veri hızlı yakınsar; gerçek fit daha
pahalıdır, ölçülmedi). Anahtar `predict` başına hesaplanır; aynı karar anındaki tahminler aynı `Chunks` nesnesini
gördüğünden `(grup, at, id(chunks))` ile karar anı başına bire indirilebilir. Soğuk parça özeti tek seferlik 8 ms.

**Düz "gözlem sayısı" (16g'nin ilk önerisi) elendi — ölçüldü:** haftada iki turlu veride kadans 7'de fit sayısı
56 → 112 ve **bayt eşliği bozulur**: cuma yeniden fit'i `latest.fitted_on == at` yüzünden soğuk başlar. Mühürlü
kadans 1'de eşit kalır; yani Faz 3'ü bozmaz ama Faz 4'te kadans değişirse tuzaktır.

## 4. Mühürlü Faz 3 çıktılarının bayt eşliği

Mühürlü yapılandırma `cadence_days: 1` (`config/model_faz3.yaml`, dokunulmadı). Etkilenebilecek çıktılar: E raporu
ve haftalık W1–W3 (`walkforward` / `model-selftest`, kilitli E verisi — HANDOFF §3.3/6 "aynı kilit ve
yapılandırmayla aynı sayı"), gölge satırları (`live/shadow.py`). Seçim (`model_faz3.yaml`) yeniden koşulmaz;
holdout satırları yeniden hesaplanamaz ve AÇILMAZ.

Sentetik ölçüm (`t6-b1-olcum.py` §3): her varyant taze nesneyle, `wf_run` gibi 1X2 + Ü/A ortak memo'lu oynatıldı,
olasılık demetleri `==` ile mevcut kodla kıyaslandı:

(c) sütunu isabet + ıska bekçisi için `t6-c-iska.py` §2'de yeniden ölçüldü; dört satırda da aynı sonuç.

| Veri / kadans | mevcut fit | (a) | (b) | (c) | düz sayı |
|---|---|---|---|---|---|
| main (cumartesi), kadans 1 | 56 | eşit · 56 | eşit · 56 | eşit · 56 | eşit · 56 |
| main, kadans 7 | 56 | eşit · 56 | eşit · 56 | eşit · 56 | eşit · 56 |
| haftada iki tur, kadans 1 | 112 | eşit · 112 | eşit · 112 | eşit · 112 | eşit · 112 |
| haftada iki tur, kadans 7 | 56 | eşit · 56 | eşit · 56 | eşit · 56 | **farklı · 112** |

- **(c):** anahtar, fit sırası ve `start` değişmez → bayt eşliği koddan okunur; bekçi yalnız okur (isabette
  girdinin, ıskada `latest`in mührünü), aynı soyda akış yalnız uzadığı için tetiklenemez.
- **(a)/(b):** eşlik, "`(grup, at)` bir oynatmada tek bir `n_before`/özet görür" varsayımına bağlıdır (§1 son
  paragraf). Varsayım zaman kuralından çıkar; gerçek veride tutarsız satır (tarih ↔ başlama UTC'si bir günden fazla
  kayık) olursa (a)/(b) bugünkü bayat fit yerine yeniden fit eder → o grupta sayı değişir. **Ölçülmedi** (DB ister).

## 5. Test planı (önerilen (c) için; (b) seçilirse 5. madde eklenir)

**(a) için test planı yok, gerekmez:** (a) elendi, çünkü sayı aynı içerik farklı yeniden kullanımı (B1') görmez
(§2: 56/56 taşır) ve sıcak başlangıç kanalını açık bırakır. Onu öldüren test 2. maddedir.

Her test mutasyonla kırmızıya düşürülür (`PYTHONDONTWRITEBYTECODE=1`, geri alınca `git diff` temiz).

1. **B1:** aynı kök nesne tam kümeye, sonra sezonu çıkarılmış kümeye → `MemoReuseError`. Mutasyon: bekçi
   kaldırılır → oynatma hatasız biter, test kırmızı.
   - **1b — ayrık anahtarlı yeniden kullanım (ıska yolu):** aynı kök nesne tam kümeye, sonra aynı maçlar +3 gün
     kaydırılmış kümeye (memo hiç isabet almaz) → `MemoReuseError`. Mutasyon: ıska denetimi kaldırılır → oynatma
     hatasız biter, test kırmızı (`t6-c-iska.py`: yalnız isabet okuyan bekçide hata yok, 4/224 bayt eşit).
2. **B1':** sayı aynı, goller çevrilmiş → `MemoReuseError`. Mutasyon: mühür yalnız sayıyı denetler → kırmızı (zayıf
   bekçiyi, yani (a)'yı öldüren test).
3. **Paylaşım bozulmaz:** 1X2 + Ü/A ortak memo aynı küme → hata yok, `test_the_fit_runs_once_per_group_and_fit_day`
   (`tests/test_model_strategies.py:63-80`) aynen yeşil. Mutasyon: mühür akış yerine nesne kimliğine bağlanır →
   kırmızı. Ayrıca tam pytest `MemoReuseError`sız kalır (`t6-pytest-bekcili.py`: 3086 passed, 0 hata; ölçüm T7
   öncesi, E2 o sırada aynı nesneyle kuruluydu ve geçti). T7 (`5306837`) sonrası E2
   (`tests/test_context_parity.py:182-205`) iki ayakta taze nesne kurar, bekçiyi hiç tetikleyemez.
4. **Bayt eşliği altını:** haftada iki turlu sentetik geçmişte, kadans 1 ve 7, olasılık demetlerinin sha256'sı
   değişiklikten ÖNCE kaydedilir; sonra eşit olmalı. Mutasyon: anahtara toplam sayı eklenir → kadans 7 kırmızı.
5. ((b) için) **Parça sınırı:** `CHUNK` küçük yamalanır, salı–cuma arasında parça mühürlenir → fit sayısı ve
   olasılıklar değişmez. Mutasyon: boş süzülmüş parça özete katılır → kırmızı (§3'teki ölçülmüş tuzak).
6. **Gerçek veri (DB ister — controller/kullanıcı):** kilitli E verisinde `walkforward` ve `model-selftest`
   değişiklikten önce ve sonra; W1–W3 satırları ve satır özeti birebir. Yalnız DEV/E — holdout açılmaz.

## 6. Yan bulgu — E2 paritesi DC ayağında boş

**T7 sonrası durum:** T7 (`5306837`) E2'yi taze nesneyle kurdu (`tests/test_context_parity.py:182-205`). Her ayak
kendi nesnesini kurar; `active_from=` hedef günü replay'de hedeften önce fit bırakmaz, iki ayak da soğuk başlar ve
`==` ile bayt eşittir. Bu bölümün geri kalanı T7 ÖNCESİNİ anlatır (satır numaraları `30bf3bc`'ye göre); tablo ve
ölçümler o kodun bulgusudur.

`tests/test_context_parity.py:181-191` (E2, `leakage`) DC'yi önce `replay`e verir, sonra AYNI kök nesneyle canlı
akışı gözleyip tahmin eder → canlı tahmin memo isabetidir, canlı kurucunun fit'ini sınamaz. Ölçüm
(`t6-e2-bos-olcum.py`, akışın ilk yarısında goller çevrildi):

| | mevcut | (a) | (b) | (c) |
|---|---|---|---|---|
| aynı nesne, doğru akış | geçer | geçer | geçer | geçer |
| aynı nesne, BOZUK akış | **geçer** | **geçer** | düşer | `MemoReuseError` |
| taze nesne, doğru akış | **düşer** | düşer | düşer | düşer |

Taze nesnenin doğru akışta düşmesinin nedeni (`t6-e2-fark.py`): replay sıcak başlangıç zinciriyle, taze canlı
nesne soğuk fit eder; fark max 3,19e-06 (mutlak), `pytest.approx` varsayılanı (göreli 1e-6) bunu aşar. Replay'de
sıcak başlangıç kapatılınca replay ile taze canlı **bit düzeyinde eşit** (fark 0,0).

HANDOFF §3.3/9 bir **kural** eşliği söyler (DC aynı Londra gününün sonuçlarını `day < at` ile dışarıda bırakır, bu
kural canlıda ve tarihte aynı) — sayısal eşlik iddia etmez ve bu bulgu onu çürütmez. Kural eşliği korunur; sayısal
eşlik sıcak/soğuk başlangıç yüzünden ~3e-6 (sentetik, ölçüldü): gölge satırı (slot başına taze, soğuk fit) ile
walk-forward (sıcak zincir) arasında bu mertebede fark beklenir. Gerçek veride ölçülmedi.

**Ağırlık:** akış eşliği zaten sınanıyor — E1 (`tests/test_context_parity.py:166-177`) canlı kurucunun
`decision.results`ini `historical.streams[index]`e ve bağlamı birebir doğrular; canlı akışı bozmak E1'de yakalanır.
E2'nin DC ayağında gerçekte sınanmayan özellik "taze canlı DC fit'i ≈ replay"dır, ve o `approx` 1e-6'da düşer.
16g'nin kapsamı dışı; ayrı satır önerisi rapordadır. T7 sonrası E2 taze canlı DC fit'ini replay'le `==` ile
karşılaştırır ve aynı-nesne biçimi kalmadı; ama iki ayak `active_from=` ile soğuk başlar, yani sıcak zincir ↔ soğuk
canlı farkı (~3e-6) tolerans büyütülmeden testin dışında bırakıldı (E2 docstring'i) ve hâlâ sınanmaz.

## 7. Öneri ve zamanlama

**Öneri: (c) — anahtar aynen, soy bekçisi isabette VE ıskada (`MemoReuseError`).**
- Mühürlü Faz 3 çıktılarına dokunmaz: bayt eşliği ölçüme değil koda dayanır (§4).
- B1 ve B1'in ikisini de kapatır; (a) B1''yi görmez. Sıcak başlangıç kanalını ancak **ıska denetimiyle** kapatır:
  yalnız isabette okuyan bekçi, memo'ya hiç isabet etmeyen yeniden kullanımı (+3 gün sondası) mevcut kod gibi
  sessiz geçirir (4/224 bayt eşit, 4,41e-05). İki yol da denetlenince `params`ın her çıktısı ya şimdiki soydan gelir
  ya hata olur; (a)/(b) bu kanalı açık bırakır. Ölçülen kapsam: üç yeniden kullanım senaryosu hata verdi, dört taze
  senaryo bayt eşit — genel ispat değil, §5/1, 1b, 2 testleriyle sabitlenir.
- Projenin "sessiz değil, adıyla" çizgisine uyar. Üretim yolları zaten taze nesne kurduğu için davranış değişmez
  (tam pytest bekçi takılıyken `MemoReuseError` 0). Testlerde aynı nesnenin ikinci bir akışa yeniden verildiği
  kullanım bugün yok (`replay` çağıranları `5b97221`de tarandı): T6 anında tek örnek E2'ydi, T7 (`5306837`)
  onu taze nesneye çevirdi (§6). Ortak memo'lu 1X2 + Ü/A paylaşımı aynı kümeyi oynatır (§5/3).
- Bekçi maliyeti isabet başına ~0,06 ms (45 bin gözlem), ıskada bir önek denetimi daha; karar anı başına bire
  indirilebilir.

**(b)'ye ne zaman geçilir:** Faz 4 bir nesneyi bilerek birden çok kümede yeniden kullanmak isterse (örneğin boşluk
cezası gibi ne-olurdu koşularında fit paylaşımı). O zaman da parça sınırı testi (§5/5) ve sıcak başlangıcın soy
bağı birlikte tasarlanır.

**Ne zaman:** Faz 4'ün `model/strategies.py`ye dokunan ilk değişikliğiyle, aynı commit dizisinde: önce §5/4 altın
kaydı, sonra bekçi (isabet + ıska) + §5/1, 1b, 2, 3, en son §5/6 gerçek veri eşliği (DB'li adım controller'da). Ayrı bir oturum açmayı
gerektirmez; Faz 4 strategies.py'ye dokunmazsa 16g gizil kalır (üretim tetiklemiyor).

## 8. Ölçmediklerimiz

- Gerçek veride bayt eşliği (§4) ve §1'deki "bir `(grup, at)` tek `n_before`" varsayımı — DB ister.
- Gerçek veride DC fit süresi; anahtar/bekçi maliyetinin fit'e oranı yalnız sentetik ölçekte (§3.1).
- Bekçinin hash çakışması: prototip Python `hash()` kullandı (64 bit, süreç içi). Uygulamada kesin karşılaştırma
  ya da `hashlib` seçimi uygulama anında ölçülerek yapılır.
- E2'nin canlı ↔ tarih farkının gerçek veri büyüklüğü (§6).
