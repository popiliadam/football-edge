# Yol Haritası v2 — paralel izler ve riske göre süreç

**Tarih:** 2026-09-21 · **Önceki:** `2026-09-19-faz-1-7-yol-haritasi.md` (görev listeleri
orada; bu belge yalnız SIRAYI ve SÜRECİ değiştirir) · **Spec:** değişmedi.

Değişmeyenler: spec §3.2 kaynak politikası, §6.2 kapı, sızıntı önlemleri, faz geçiş kuralı,
"kapının ölçmediği" yazılır. Değişen: işler bağımlılık izin verdiği ölçüde **aynı anda** yürür
ve inceleme yükü **riske göre** ayarlanır.

## 1. Neden yavaştı (ölçülmüş)

- **Sıralı yürütme.** Faz 1'in 13 görevinden yalnız 5'i (Task 6–10) paralel koştu — sıfır
  çakışmayla. Kalanlar ortak dosyalara (`collect.py`, `verify.sh`) dokunduğu için sıralıydı.
- **Her risk seviyesine aynı ağırlıkta inceleme.** Görev incelemesi + düzeltme turları + bütün-dal
  incelemesi + kontrol incelemesi + artık tur. Kritik kodda gerçek hatalar yakaladı (yönlendirme
  bypass'ı, UTC kayması, commit'ten önce sayım); son turun 7 artığının 5'i ise doküman sayısı ve
  yorum tarihçesiydi.
- **Kod yorumlarına yazılan tarihçe** bayatladı ve kendi düzeltme turlarını doğurdu.
- **İşletme izlenmedi.** Mühür iki gün kırmızıydı (DEFERRED §10) — kodun değil işletmenin açığı.

## 2. Üç iz

```
İz A (veri → model, sıralı çekirdek):  Faz 2 ──► Faz 3 ──► Faz 4 ──► Faz 5
İz B (ürün yüzeyi, veri sözleşmesine karşı):  Faz 6 iskeleti ─────────► Faz 6 kalanı ► Faz 7
İz C (işletme / otonomi, hemen):  C1–C5
```

A'nın fazları birbirinin çıktısını tükettiği için sıralı kalır; **faz İÇİNDE** bağımsız
görevler dalgalar hâlinde paralel koşar. B, A'nın model çıktısına değil bir **okuma
sözleşmesine** (maç, oran anlık görüntüsü, kapanış mührü, tahmin yer tutucusu) bağlanır; bu
yüzden bugün başlayabilir. C, "manuel süreç kalmasın" hedefinin kendisidir.

### İz A — faz içi dalgalar (görev numaraları eski yol haritasındaki)

| Faz | Dalga 1 (paralel) | Dalga 2 (paralel) | Dalga 3 |
|---|---|---|---|
| 2 | T1 MIT yükleyici · T3 vig temizleme (saf) · T5 holdout tanımı · T2 harness iskeleti (sahte veriyle) | T4 piyasa verimliliği · T7 tarihsel/canlı kapanış · T2 bütünleşik | T6 Opus sızıntı denetimi |
| 3 | T1 Dixon-Coles (saf) · T3 Elo fit · T5 kalibrasyon ölçümü (saf) | T2 xG varyantı · T4 opinion pooling | T6 baz çizgi raporu |
| 4 | T1 Jev istemcisi · T7 özellik deposu | T2 · T3 · T4 · T5 soru bataryaları · T6 boru hattı rolleri | T8 budama · T9 eşdoğrusallık |
| 5 | T2 Kelly + simülasyon · T3 EV eşiği · T6 kayıp otopsisi | T1 istifleme | T4 CLV kapısı · T5 judge-selftest |

**Faz 4 ön koşulu (insan):** dil kalibrasyonu — `TYPESAFE_API_KEY` ve dil başına ~100 elle
etiketli haber (spec §5.4). Etiket yükünü azaltmak için Opus ön-etiketler, insan yalnız onaylar;
ölçüm yine insan etiketine karşıdır.

### İz B — Faz 6'nın modelden bağımsız kısmı şimdi

Hemen: T1 Next.js iskeleti + okuma katmanı · T3 sicil sayfasının defter/zincir başı doğrulama
kısmı · T4 pSEO yapısı · T5 schema.org · T6 18+/KVKK · T7 deploy. T2 maç sayfası "value" rozeti
Faz 5'e kadar yer tutucuyla. Faz 7'nin T1–T2'si (katmanlama kararı, Sonnet hattı ve maliyet
tavanı) Faz 6 iskeletiyle; T3 doğrulama geçidi Faz 4'ün Jev istemcisini bekler.
**İnsan gereken tek yer:** Netlify hesabı/site ve alan adı kararı.

### İz C — işletme ve otonomi (hemen, birbirinden bağımsız)

| # | İş | Neyi kaldırır |
|---|---|---|
| C1 | Mühür tetiği canlı + doğrulandı (pg_cron → `workflow_dispatch`, RUNBOOK §3) | 2 günlük sessiz kayıp |
| C2 | Mühür/kapı kırmızısı için bildirim (DEFERRED 10a) | "Kimse bakmadı" |
| C3 | Faz 1 toplayıcılarını zamanla — aynı pg_cron → dispatch deseni (HANDOFF §3.1/1: hiçbiri zamanlanmış değil) | Elle `fetch-*` |
| C4 | robots 30 günlük yeniden doğrulamayı otomatikleştir: canlı = anlık görüntü ise tarih bot commit'iyle ilerler, farklıysa kırmızı | ~2026-10-19'daki elle yenileme |
| C5 | Odds API kredi izleme + "yalnız YENİ kaçan mühür" raporu (DEFERRED 10b, 10d) | Gürültü ve ay sonu sürprizi |

## 3. Riske göre süreç

| Kademe | Kapsam | Süreç |
|---|---|---|
| **K1** | Para ve veri bütünlüğü: defter, mühür, model, staking, CLV kapısı | TDD + görev incelemesi + bütün-dal incelemesi (bugünkü süreç) |
| **K2** | Toplayıcı, özellik, boru hattı, işletme | TDD + tek görev incelemesi; bulgular tek turda toplu düzeltilir |
| **K3** | Doküman, site görünümü, içerik şablonu | Controller doğrulaması; inceleme turu açılmaz |

Kurallar:
- Kod yorumu kısa bir "neden" taşır; tarihçe commit mesajında ve faz HANDOFF'unda durur.
- Belgelerde donmuş sayı tutulmaz; gerekiyorsa ölçen komut yazılır.
- Yalnız doküman sayısı / atıf bulgusu bir inceleme turu AÇMAZ; bir sonraki doküman commit'ine
  toplanır.

## 4. Paralellik kuralları

- Her dalgadan önce tek-yazar taraması (Faz 1 R1/R2): aynı dosyaya iki paralel görev yazmaz;
  ortak dosyalar (`collect.py` CLI kaydı, `verify.sh`) yalnız dalga sonu birleştirme adımında
  değişir.
- Paralel görevler izole worktree'lerde; birleştirme `--no-ff`.
- Aynı anda en çok **4** implementer: daha fazlası haftalık API limitine çarpar (Faz 1'de bir kez
  oldu) ve inceleme darboğazını büyütür.
- Model: varsayılan opus; mimari ve bütün-dal incelemesi fable; haiku hiçbir yerde.

## 5. İnsan gereken kararlar (otomatikleştirilemeyen)

1. Mühür tokenı + Vault + migration 0003 (RUNBOOK §3.2) — C1 için.
2. Bildirim kanalı (C2): GitHub e-postası yeterli mi, yoksa webhook (Telegram/Slack) mı.
3. Netlify hesabı ve alan adı (İz B).
4. `TYPESAFE_API_KEY` + dil kalibrasyon etiketleri (Faz 4 ön koşulu).
5. Odds API planı: güvenilir mühürle kredi ilk kez gerçekten tükenecek (DEFERRED 10d).
