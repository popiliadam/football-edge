# Faz 1 — Toplayıcılar, Varlık Eşleme, Dil Kalibrasyonu — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modelin ihtiyaç duyduğu veri türlerini — yalnız izinli kaynaklardan, robots.txt'i
*kodla zorlayarak*, `observed_at` damgalı ve append-only biçimde — toplayan bir katman kurmak;
takım adlarını kaynaklar arası eşlemek; ve Jev'in çok dilli doğruluğunu ölçmek.

**Architecture:** Faz 0'ın defteri üstüne ikinci bir depo katmanı gelir: `source_observations`
(append-only, `observed_at` damgalı, kaynak başına şema + tazelik sözleşmesi). Tüm toplayıcılar
tek bir `collector.py` iskeletine oturur: `izin kontrolü → fetch → doğrula → yaz`. **İzin kontrolü
kodun içindedir** — `config/robots/<kaynak>.txt` altında commit'lenmiş robots.txt anlık
görüntüsüne karşı `urllib.robotparser` ile sorulur, ve disallow edilen bir yolu isteyen toplayıcı
testte patlar. Varlık eşleme Jev'in `Choice` primitifiyle yapılır ve **eşleşme eşiğin altındaysa
satır yazılmaz** (sessiz join hatası bu projenin 1 numaralı ölüm sebebi, spec §5.3).

**Tech Stack:** Python 3.11+, uv, httpx, psycopg3 (`executemany` + `unnest` toplu yazma),
PyYAML, beautifulsoup4, `urllib.robotparser` (stdlib), typesafe-sdk (Jev), pytest, ruff, mypy,
Supabase Postgres, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-19-football-edge-design.md`
**Yol haritası:** `docs/superpowers/plans/2026-09-19-faz-1-7-yol-haritasi.md` (Faz 1 bölümü)
**Devralınan borç:** `docs/DEFERRED.md`
**Faz 0 devri:** `docs/HANDOFF.md`, `docs/phases/00-kayit-altyapisi/HANDOFF.md`

---

## 0. Bu plan yazılırken ÖLÇÜLEN kaynak erişim denetimi (2026-09-19)

Spec §10/3 ve yol haritası "robots.txt Faz 1'de doğrulanacak" diyordu. **Doğrulandı — ve yol
haritasının yedi toplayıcısından üçü projenin KENDİ politikasıyla kapalı çıktı.** Ölçüm bu makineden
(TR) yapıldı; kanıtlar aşağıda. Bu tablo Task 3'te `config/sources.yaml` + `config/robots/*.txt`
olarak **makine tarafından kontrol edilebilir** hâle getirilir; bir daha ezbere güvenilmez.

| Yol haritası | Kaynak | Ölçülen | Karar |
|---|---|---|---|
| Task 2 | **Understat** | `robots.txt` = `User-agent: *` / `Disallow: /` — 26 bayt, `Last-Modified: 2020-07-13`, tarayıcı UA'sıyla da aynı | **KAPALI** — spec §3.2/1. Ağdan bağımsız, kesin. |
| Task 3 | **FootyStats** | 200; `User-agent: ClaudeBot` → `Crawl-delay: 1`; `/turkey/super-lig/xg` 388 KB, sunucu-render tablo | **İZİNLİ** ✅ |
| Task 4 | **FBref** | İçerik sayfası **ve** `/robots.txt` → **403 Cloudflare**. Politikayı okumak bile bot korumasını aşmayı gerektiriyor | **KAPALI** — spec §3.2/2; SofaScore'u eleyen kuralın aynısı |
| Task 5 | **ClubElo** | `api.clubelo.com/Fixtures` → 200 `text/csv`: `Fixtures API deactivated`. Tarih ve kulüp uçları → ısrarlı 502 | **KULLANILAMAZ** |
| Task 6 | **Google News RSS** | 200, 105 item, `hl`/`gl`/`ceid` çalışıyor. Feed'in kendi `<copyright>`'ı: *"solely for ... personal, non-commercial use. Any other use of the feed is expressly prohibited."* | **Teknik olarak açık, LİSANS ÇATIŞMASI** |
| Task 7 | **TFF** `pageID=600` | 200, 406 KB, `Content-Type: text/html; charset=windows-1254` — **yalnız HTTP başlığında, gövdede meta yok**. `robots.txt` → 404 (yok) | **İZİNLİ** ✅ |
| Task 8 | **Open-Meteo** | 200; yanıt `elevation` alanını **doğrudan** veriyor (İstanbul için 77.0 m) | **İZİNLİ** ✅ |
| Task 8 | **Wikidata** | SPARQL ucu yerel `outward_action_gate` tarafından `net_post` olarak engellendi | **REST ile çözülür** (aşağıda) |
| (yeni) | **Ajansspor** | `robots.txt`: `Content-Signal: ai-train=no, search=yes, **ai-input=yes**`; ama `/lineup/*`, `/mac/`, `/oyuncu/`, `/lig/`, `*rsc=*` **Disallow** | **KISMEN izinli** — haber yolları açık, yapısal sayfalar kapalı |

### 0.1 Ruling A — kapalı kaynaklar izinliyle değiştirilir, boşluk ADIYLA yazılır

| Kaybedilen | Yerine | Neden savunulabilir |
|---|---|---|
| Understat xG (6 lig) | **FootyStats xG** (Task 5) | FootyStats zaten bu 6 ligi de kapsıyor ve ClaudeBot'a açık. Tek xG yolu olmaktan çıkıp **tek xG yolu** olarak kalıyor — kaynak sayısı azalıyor, kapsam azalmıyor. |
| ClubElo reytingi | **Kendi Elo motorumuz** (Task 10), sonuçlardan hesaplanır (Task 9) | Elo deterministik bir özyinelemedir: saf fonksiyon, dış bağımlılık yok, TDD'ye birebir uygun, ve **train/serve sapması imkânsız** (backtest ile canlı aynı fonksiyonu çağırır — spec §6.3). Faz 2'nin MIT veri seti zaten ClubElo sütunu taşıyor; tohumlama oradan yapılır. |
| FBref hakem + seyirci (40+ ülke) | **Kapatılmadı — boşluk** | TR için TFF karşılıyor (Task 6). Global hakem/seyirci Faz 1'de YOK; `docs/DEFERRED.md`'ye yazılır ve Faz 3'ün baz modeli hakem özelliği olmadan kurulur. **Bunu "zaten vardı" sanarak üstüne inşa etmek yasak.** |

### 0.2 Ruling B — haber katmanı kaynak-bağımsız adaptör, Google News **varsayılan KAPALI**

Haber katmanı tek bir sağlayıcıya değil, `NewsAdapter` arayüzüne yazılır (Task 8). İlk ve
varsayılan adaptör **Ajansspor** (yalnız robots'un izin verdiği haber yolları). **Google News
adaptörü de yazılır** ama `config/sources.yaml` içinde `enabled: false` ile gelir ve feed'in
copyright metni kodun yanında birebir kayıtlıdır. Mimari korunur; ticari karar konfigürasyondadır.

Spec §3.1 Google News'i "lisanslı yüzey" diye sınıflıyordu. **Feed'in kendisi aksini söylüyor.**
Bu satır Task 13'te `docs/DEFERRED.md` §7'ye, MIT CSV lisans zinciriyle aynı muameleyle
("ticari lansman öncesi avukat") taşınır.

### 0.3 Ruling C — bu denetimin kendisi bir daha ezberlenmez

Yukarıdaki tablo **bugünün ölçümüdür**; yarın değişebilir. Task 3 onu ikiye böler:
- **Kapı (çevrimdışı, ağsız):** her etkin kaynağın `config/robots/<id>.txt` anlık görüntüsü var mı,
  `robots_verified_at` 30 günden eski mi, ve toplayıcının **beyan ettiği her yol** o anlık görüntüde
  `can_fetch` mi. Ağ gerektirmez, her push'ta koşar.
- **Zamanlanmış (canlı):** `sources-audit.yml` günde bir robots.txt'leri yeniden çeker ve
  commit'lenmiş anlık görüntüyle **diff**'ler. Upstream politikası değişince kırmızı verir.

Bu ayrım `snapshot`/`seal` ayrımının aynısıdır: sözleşme kapıda, sapma zamanlanmış işte.

### 0.4 Ölçüm sınırı — dürüstçe

Sondalar **Türkiye'den** koşuldu. Spec §7 runner konumunun *erişim* sorununu çözdüğünü söylüyor.
Güven düzeyleri ayrışır:

- **Understat:** politika dosyası, ağdan bağımsız → kesin.
- **Google News copyright:** feed'in kendi gövdesinden alıntı → kesin.
- **ClubElo `/Fixtures`:** uygulama seviyesinde 200 + `text/csv` mesajı → o uç için kesin.
  Tarih/kulüp uçlarının 502'si ağ/coğrafya kaynaklı **olabilir**.
- **FBref 403:** TR'den ölçüldü. Cloudflare bot koruması coğrafyadan bağımsız davranır ve spec
  zaten "Cloudflare korumalı, `soccerdata` CAPTCHA çözücü istiyor" diyor — ama **runner'dan
  yeniden ölçülmedi.** Task 3'ün `sources-audit.yml`'i bunu her gün runner'dan ölçer; FBref
  açılırsa iş kırmızı verir ve haber verir. Kapanan kaynak gibi **açılan kaynak da** olaydır.

---

## Global Constraints

Faz 0'ın kısıtlarının **hepsi geçerlidir** (`docs/superpowers/plans/2026-09-19-faz0-kayit-altyapisi.md`
§Global Constraints). Faz 1'in eklediği:

- **Python ≥ 3.11.** Tür ipuçları zorunlu; `from __future__ import annotations` her modülde.
- **Mutasyon yok.** `frozen=True` dataclass veya tuple; mevcut nesne değiştirilmez, yenisi üretilir.
- **Dosya boyutu:** 200-400 satır normal, 800 mutlak üst sınır. Fonksiyon < 50 satır. 4+ seviye iç içe yok.
- **`print` yok** kütüphane kodunda; `logging`. CLI giriş noktası hariç.
- **Hardcoded secret yok.** Faz 1'in eklediği env: `TYPESAFE_API_KEY`. Yoksa açık hata.
- **Her toplanan satırda `observed_at`.** Özellik yalnız `observed_at < kickoff` veriden hesaplanır (spec §6.3).
- **`source_observations` append-only.** UPDATE/DELETE veritabanı seviyesinde reddedilir.
  **Hash zinciri YOKTUR** — bilinçli: zincir, ürünün kurcalanmazlık iddiasını taşıyan *oran*
  defteri içindir. Bu karar Task 13'te handoff'a "kapının ölçmediği" olarak yazılır.
- **Kaynak politikası KODLA zorlanır:** `fetch_text` robots'a sormadan istek atmaz (Task 3).
  Spec §3.2 artık prose değil, testi olan bir kural.
- **Crawl-delay'e uyulur.** Kaynak başına `config/sources.yaml`'dan okunur; FootyStats için 1.0 sn.
- **Ham içerik yeniden yayınlanmaz** (spec §3.2/4). `source_observations.payload` yalnız
  **türetilmiş sayısal alan** taşır; tam HTML/metin gövdesi saklanmaz.
- **Backtest ve canlı aynı özellik kodunu çağırır** (spec §6.3). Toplayıcı ile okuyucu arasında
  ikinci bir dönüştürme yolu yazılmaz.
- **Jev cevabı elle katsayıya çevrilmez** (spec §5.2). Faz 1 yalnız *toplar ve ölçer*.
- **Kapı (`./verify.sh`):** Faz 0'ın 7 adımı + `kaynak-politikası` + `veri-sözleşmesi`.
  Hepsi yeşil değilse faz bitmemiştir. **`SKIP` geçmek değildir, adıyla raporlanır.**
- **Biçimlendirme:** bu dokümandaki kod blokları elle yazıldı; `line-length = 100` ayarındaki
  `ruff format` ile birebir aynı olmayabilir. Aktarımdan sonra `uv run ruff format` çalıştır;
  **yalnız boşluk/satır kırma** değişikliği beklenir. İsim/değer/mantık değişiyorsa aktarım hatalıdır.
- **Paket gerçekten kurulu olmalı:** `uv sync --reinstall-package football-edge` bozulursa.

---

## Yol haritası ↔ plan task eşlemesi

| Yol haritası | Bu plan | Durum |
|---|---|---|
| — (HANDOFF §6: "Faz 1'in ilk işi Faz 0'ın borcu") | Task 1, Task 2 | eklendi |
| Task 1 — toplayıcı çatısı | Task 3 (kaynak politikası) + Task 4 (çatı) | ikiye bölündü |
| Task 2 — Understat | — | **KAPALI** (Ruling A) → kapsamı Task 5 devraldı |
| Task 3 — FootyStats | Task 5 (**referans uygulama**) | genişledi: tüm ligler |
| Task 4 — FBref | — | **KAPALI** (Ruling A) → boşluk DEFERRED'a |
| Task 5 — ClubElo | Task 9 (sonuç toplayıcı) + Task 10 (Elo motoru) | değiştirildi |
| Task 6 — Google News | Task 8 (haber adaptörü, varsayılan kapalı) | Ruling B |
| Task 7 — TFF | Task 6 | aynı |
| Task 8 — Open-Meteo + Wikidata | Task 7 | aynı |
| Task 9 — varlık eşleme (Jev) | Task 11 | aynı |
| Task 10 — dil kalibrasyonu | Task 12 | aynı |
| (faz geçiş kuralı) | Task 13 | eklendi |

---

## Dosya Yapısı

| Dosya | Sorumluluk |
|---|---|
| `config/sources.yaml` | Kaynak kayıt defteri: robots durumu, crawl-delay, UA, lisans notu, etkinlik |
| `config/robots/<id>.txt` | Ölçülmüş robots.txt anlık görüntüleri (kapının çevrimdışı dayanağı) |
| `config/leagues.yaml` | **Mevcut** — Faz 1'de kaynak anahtarları eklenir (`footystats_slug`, `tff_league_id`) |
| `src/football_edge/sources.py` | `Source` kaydı, robots yükleme/sorgulama, crawl-delay kapısı |
| `src/football_edge/collector.py` | Ortak `izin → fetch → doğrula → yaz` iskeleti, tazelik/şema iddiası, devre kesici |
| `src/football_edge/observations.py` | `source_observations` yazma/okuma (append-only) |
| `src/football_edge/collectors/footystats.py` | xG/xGA tablosu (referans uygulama) |
| `src/football_edge/collectors/tff.py` | Hakem ataması + PFDK, **windows-1254** |
| `src/football_edge/collectors/venues.py` | Wikidata REST + OSM: stadyum koordinatı/rakım |
| `src/football_edge/collectors/weather.py` | Open-Meteo: maç saati hava + rakım |
| `src/football_edge/collectors/news.py` | `NewsAdapter` arayüzü + Ajansspor + Google News (kapalı) |
| `src/football_edge/collectors/results.py` | The Odds API `/scores` → `match_results` |
| `src/football_edge/elo.py` | Saf Elo motoru (dış bağımlılık yok) |
| `src/football_edge/jev.py` | TypeSafe istemci sarmalayıcı: `Choice`/`Noul`, eşik, hata yolu |
| `src/football_edge/mapping.py` | Varlık eşleme: aday üretimi + Jev seçimi + eşik + sözlük |
| `src/football_edge/collect.py` | **Mevcut** — yeni alt komutlar eklenir |
| `src/football_edge/db.py` | **Mevcut** — toplu yazma (Task 1) |
| `db/migrations/0002_sources.sql` | `source_observations`, `match_results`, `entity_aliases` + append-only tetikleyiciler |
| `.github/workflows/sources-audit.yml` | Günlük canlı robots/erişim sapma denetimi |
| `tests/` | Her modül için birim testler; `tests/fixtures/` altında kaydedilmiş kaynak yanıtları |

---

## Paralellik ve worktree protokolü

**Sıralı zincir:** Task 1 → 2 → 3 → 4 → 5 birleşmeden Task 6-10 BAŞLAMAZ.
Task 5 (FootyStats) çatının **gerçek bir kaynağa karşı kanıtıdır**: Faz 0'ın `fake_db.py`
docstring'inde yazılı ders — *kısıt uygulamayan bir taklit, temiz veritabanında patlayan kodu
yeşil gösterir*. Çatıyı yalnız test ikizine karşı doğrulayıp beş ajanı izole worktree'ye salmak,
çatı hatalıysa beş worktree'yi birden yanlış yapar.

**Paralel küme (izole worktree, her biri kendi dalı + kendi venv'i):**

| Worktree | Task | Dokunduğu dosyalar (ÖRTÜŞME YOK) |
|---|---|---|
| `wt-tff` | Task 6 | `collectors/tff.py`, `tests/test_tff.py`, `tests/fixtures/tff/` |
| `wt-venue` | Task 7 | `collectors/venues.py`, `collectors/weather.py`, `tests/test_venues.py`, `tests/test_weather.py`, `tests/fixtures/venue/` |
| `wt-news` | Task 8 | `collectors/news.py`, `tests/test_news.py`, `tests/fixtures/news/` |
| `wt-results` | Task 9 | `collectors/results.py`, `tests/test_results.py`, `tests/fixtures/results/` |
| `wt-elo` | Task 10 | `elo.py`, `tests/test_elo.py` |

**Tek yazar kuralı.** Hiçbir paralel task `config/sources.yaml`, `config/leagues.yaml`,
`collector.py`, `sources.py`, `db/migrations/*` veya `verify.sh` dosyasını **değiştirmez** —
hepsini yalnız okur. İhtiyaç duyulan her kayıt Task 3/4'te önceden yazılır (aşağıdaki
`config/sources.yaml` tüm kaynakları baştan içerir). Bir paralel task bu dosyalardan birini
değiştirmek zorunda kalıyorsa **dur ve bildir**: bu, çatının eksik olduğunun işaretidir.

**`src/football_edge/collect.py` de salt okunurdur (Ruling R1).** Paralel task'lar CLI alt
komutu EKLEMEZ — yalnız `collect_*()` kütüphane fonksiyonunu ve testini teslim eder. İki
worktree aynı `main()` dalına yazarsa birleştirme çakışması kesindir ve çakışmayı çözen kişi
iki ayrı ajanın niyetini tahmin etmek zorunda kalır. CLI kaydı, beş dal birleştikten sonra
**tek sıralı adımda** yapılır (aşağıda, "Birleştirme adımı: CLI kaydı").

Worktree kurulumu için `superpowers:using-git-worktrees` skill'ini kullan. Her worktree'de:

```bash
uv sync --frozen && uv run pytest -q
```

Birleştirme **`--no-ff`** ile yapılır (Faz 0 Ruling 15: squash/rebase gitleaks parmak izlerini
geçersizleştirir). Beşi birleştikten sonra **tek bir kapı koşusu** ve ardından Task 11 başlar.

---

### Task 1: Faz 0 borcu — toplu yazma ve `commence_time` tazeleme

Faz 0'ın ilk canlı turu 3 717 satırı **~4 dakikada** yazdı: `insert_snapshots` satır başına bir
`cur.execute` atıyor (`docs/DEFERRED.md` §4.1). Faz 1 kaynak sayısını artırıyor; `snapshot` ve
`seal` **aynı `odds-collect` concurrency grubunda** ve `cancel-in-progress: false`, yani uzun
snapshot turu mühür turlarını kuyruğa diziyor — **kaçan mühür geri gelmez.** Bu yüzden Faz 1'in
ilk işi budur.

Aynı task `docs/DEFERRED.md` §3.1'i de kapatır: `upsert_matches` `ON CONFLICT (id) DO NOTHING`
kullandığı için **ertelenen maç eski saatini taşımaya devam ediyor** ve eski saatinden 24 saat
sonra mühür penceresinden *sessizce* düşüyor. İki değişiklik de `db.py`'dedir ve ikisi de yazma
yolunun doğruluğudur.

**Files:**
- Modify: `src/football_edge/db.py` (`upsert_matches`, `insert_snapshots`)
- Modify: `tests/fake_db.py` (yeni SQL şekillerini tanısın)
- Modify: `tests/test_db.py`

**Interfaces:**
- Consumes: `football_edge.ledger.chain`, `football_edge.odds_api.PriceRow` (değişmedi)
- Produces: imzalar **değişmez** —
  - `insert_snapshots(conn, rows, observed_at, *, is_closing) -> tuple[str, ...]`
  - `upsert_matches(conn, rows, league_id) -> int`
  - Davranış değişikliği: tek INSERT ifadesi; `commence_time` her turda tazelenir.

- [ ] **Step 1: Write the failing tests**

`tests/test_db.py` dosyasının SONUNA ekle:

```python
def test_insert_snapshots_uses_a_single_statement() -> None:
    """3 717 satır = 3 717 gidiş-dönüş demek değildir. Sayı yük taşır: mühür penceresi 20 dakika."""
    db = FakeLedgerDb(leagues={"eng.1": ()})
    rows = tuple(
        PriceRow(
            event_id="evt1",
            sport_key="soccer_epl",
            commence_time="2026-09-19T18:00:00Z",
            home_team="A",
            away_team="B",
            bookmaker=f"book{index}",
            bookmaker_last_update="2026-09-19T10:00:00Z",
            market="h2h",
            outcome="A",
            point=None,
            price=1.90 + index / 100,
        )
        for index in range(25)
    )
    upsert_matches(db, rows, "eng.1")
    written = insert_snapshots(db, rows, utc("2026-09-19T12:00:00Z"), is_closing=False)

    assert len(written) == 25
    inserts = [s for s in db.statements if s.startswith("INSERT INTO odds_snapshots")]
    assert len(inserts) == 1, f"25 satır için {len(inserts)} ifade atıldı"


def test_insert_snapshots_preserves_chain_order() -> None:
    """Zincir `ORDER BY id` ile geri okunuyor. Toplu yazma sırayı bozarsa defter KIRIK der."""
    db = FakeLedgerDb(leagues={"eng.1": ()})
    rows = tuple(
        PriceRow(
            event_id="evt1",
            sport_key="soccer_epl",
            commence_time="2026-09-19T18:00:00Z",
            home_team="A",
            away_team="B",
            bookmaker=f"book{index}",
            bookmaker_last_update="2026-09-19T10:00:00Z",
            market="h2h",
            outcome="A",
            point=None,
            price=1.90 + index / 100,
        )
        for index in range(5)
    )
    upsert_matches(db, rows, "eng.1")
    insert_snapshots(db, rows, utc("2026-09-19T12:00:00Z"), is_closing=False)

    stored = sorted(db.snapshots, key=lambda row: int(row["id"]))
    for earlier, later in zip(stored, stored[1:], strict=False):
        assert later["prev_hash"] == earlier["row_hash"]


def test_lock_is_still_taken_before_the_head_is_read() -> None:
    """Toplu yazma, kilidin baş okumasından ÖNCE gelmesini bozmamalı (db.LEDGER_LOCK_KEY)."""
    db = FakeLedgerDb(leagues={"eng.1": ()})
    rows = (
        PriceRow(
            event_id="evt1",
            sport_key="soccer_epl",
            commence_time="2026-09-19T18:00:00Z",
            home_team="A",
            away_team="B",
            bookmaker="pinnacle",
            bookmaker_last_update="2026-09-19T10:00:00Z",
            market="h2h",
            outcome="A",
            point=None,
            price=1.95,
        ),
    )
    upsert_matches(db, rows, "eng.1")
    insert_snapshots(db, rows, utc("2026-09-19T12:00:00Z"), is_closing=False)

    lock_index = next(i for i, s in enumerate(db.statements) if s.startswith("SELECT pg_advisory"))
    head_index = next(i for i, s in enumerate(db.statements) if "ORDER BY id DESC" in s)
    assert lock_index < head_index


def test_upsert_matches_refreshes_a_postponed_kickoff() -> None:
    """Ertelenen maç: DO NOTHING eski saati taşıyordu ve maç mühür penceresinden sessizce düşüyordu."""
    db = FakeLedgerDb(leagues={"eng.1": ()})
    original = PriceRow(
        event_id="evt1",
        sport_key="soccer_epl",
        commence_time="2026-09-19T18:00:00Z",
        home_team="A",
        away_team="B",
        bookmaker="pinnacle",
        bookmaker_last_update="2026-09-19T10:00:00Z",
        market="h2h",
        outcome="A",
        point=None,
        price=1.95,
    )
    upsert_matches(db, (original,), "eng.1")
    postponed = replace(original, commence_time="2026-09-26T18:00:00Z")
    upsert_matches(db, (postponed,), "eng.1")

    assert db.matches["evt1"]["commence_time"] == utc("2026-09-26T18:00:00Z")
```

`tests/test_db.py`'nin import bloğunu tamamla (eksikse ekle):

```python
from dataclasses import replace

from football_edge.db import insert_snapshots, upsert_matches
from football_edge.odds_api import PriceRow
from tests.fake_db import FakeLedgerDb, utc
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_db.py -v -k "single_statement or chain_order or postponed"`
Expected: FAIL — `test_insert_snapshots_uses_a_single_statement` 25 ifade görür,
`test_upsert_matches_refreshes_a_postponed_kickoff` eski saati görür.
`taklit veritabanı bu sorguyu tanımıyor` hatası **bu adımda beklenmez** (henüz eski SQL koşuyor).

- [ ] **Step 3: Teach the fake the batched statements**

`tests/fake_db.py` içinde `_LedgerCursor.execute`'a, `INSERT INTO odds_snapshots` dalını
**değiştirerek** toplu biçimi tanıt. Mevcut `elif text.startswith("INSERT INTO odds_snapshots")`
satırını şununla değiştir:

```python
        elif text.startswith("INSERT INTO odds_snapshots"):
            self.rowcount, self._result = self._db.put_snapshots(params)
```

Ve `FakeLedgerDb` içine `put_snapshot`'ın **yanına** ekle (eskisini silme — tekil yol başka
testlerde kullanılıyor değilse de, davranış tek yerde kalsın diye yenisi eskisini çağırır):

```python
    def put_snapshots(self, params: dict[str, Any]) -> tuple[int, list[tuple[Any, ...]]]:
        """Kolon-dizisi (unnest) biçimindeki toplu insert'i satırlara açar.

        Gerçek ifade tek `INSERT ... SELECT * FROM unnest(...) ... RETURNING match_id`.
        Taklit de tek çağrıda tüm satırları görmeli: aksi hâlde "kaç ifade atıldı" testi
        taklidin şekline bakar, kodun şekline değil.
        """
        columns = tuple(LEDGER_COLUMNS)
        count = len(params["row_hash"])
        written: list[tuple[Any, ...]] = []
        inserted = 0
        for index in range(count):
            row = {name: params[name][index] for name in columns}
            if self.put_snapshot(row):
                inserted += 1
                written.append((row["match_id"],))
        return inserted, written
```

`_LedgerCursor.execute`'un başındaki `self.rowcount, self._result = 0, []` satırı olduğu gibi kalır.

- [ ] **Step 4: Write the batched implementation**

`src/football_edge/db.py` içinde `upsert_matches` ve `insert_snapshots`'ı **değiştir**.
Modülün üstüne, `LEDGER_LOCK_KEY` tanımının altına ekle:

```python
# Toplu yazmanın kolon sırası. `_SNAPSHOT_COLUMNS` hem SQL metnini hem parametre sözlüğünü
# üretir: iki listeyi elle eşlemek, sessizce kayan bir sütun eşlemesine davetiyedir.
_SNAPSHOT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("match_id", "text"),
    ("observed_at", "timestamptz"),
    ("bookmaker", "text"),
    ("market", "text"),
    ("outcome", "text"),
    ("point", "numeric"),
    ("price", "numeric"),
    ("bookmaker_last_update", "timestamptz"),
    ("is_closing", "boolean"),
    ("prev_hash", "text"),
    ("row_hash", "text"),
)

_NAMES = ", ".join(name for name, _ in _SNAPSHOT_COLUMNS)
_ARRAYS = ", ".join(f"%({name})s::{kind}[]" for name, kind in _SNAPSHOT_COLUMNS)

# `WITH ORDINALITY ... ORDER BY ord` LOAD-BEARING'DİR: defter `ORDER BY id` ile geri okunur
# ve `verify_chain` her satırın `prev_hash`ini bir öncekinin `row_hash`i sanar. Satırlar dizi
# sırasından FARKLI bir sırayla eklenirse bigserial sırası zinciri çapraz keser ve KURCALANMAMIŞ
# bir defter "KIRIK" der. Append-only olduğu için o satırlar silinemez.
INSERT_SNAPSHOTS = f"""
    INSERT INTO odds_snapshots ({_NAMES})
    SELECT {_NAMES}
    FROM unnest({_ARRAYS}) WITH ORDINALITY AS t({_NAMES}, ord)
    ORDER BY ord
    ON CONFLICT (row_hash) DO NOTHING
    RETURNING match_id
"""
```

`upsert_matches`'ı şununla değiştir:

```python
def upsert_matches(
    conn: psycopg.Connection[Any], rows: tuple[PriceRow, ...], league_id: str
) -> int:
    """Maçları tazeler. `commence_time` HER TURDA güncellenir.

    `DO NOTHING` ertelenen maçın ESKİ saatini taşımaya devam ediyordu: satır filtresi API'nin
    güncel saatine, mühür adaylığı veritabanının bayat saatine bakıyor ve maç eski saatinden
    24 saat sonra `_seal_candidates` penceresinden SESSİZCE düşüyordu — ne mühürlenir ne de
    kaçan mühür olarak raporlanır. Kapanış fiyatı kaybolur ve kimse görmez (DEFERRED §3.1).

    Dönen sayı "yeni maç" değil "GÖRÜLEN maç"tır: `DO UPDATE` her satır için 1 bildirir.
    Çağıran bu değeri karar için kullanmaz.
    """
    seen: dict[str, PriceRow] = {}
    for row in rows:
        seen.setdefault(row.event_id, row)
    if not seen:
        return 0
    params = [
        (event_id, league_id, row.commence_time, row.home_team, row.away_team)
        for event_id, row in seen.items()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO matches (id, league_id, commence_time, home_team, away_team)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET commence_time = excluded.commence_time
            """,
            params,
        )
        return max(cur.rowcount, 0)
```

`insert_snapshots`'ın gövdesini (docstring'i AYNEN koru) şununla değiştir:

```python
    lock_ledger(conn)
    payloads = tuple(snapshot_payload(row, observed_at, is_closing=is_closing) for row in rows)
    linked = chain(payloads, prev_hash=chain_head(conn))
    if not linked:
        return ()
    columns = {
        name: [entry[name] for entry in linked] for name, _ in _SNAPSHOT_COLUMNS
    }
    with conn.cursor() as cur:
        cur.execute(INSERT_SNAPSHOTS, columns)
        return tuple(str(record[0]) for record in cur.fetchall())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py tests/test_collect.py tests/test_collect_seal.py -q`
Expected: hepsi PASS. Kırmızı kalan varsa **taklidi değil kodu** düzelt: `put_snapshots`
kolon-dizisi bekliyor, `INSERT_SNAPSHOTS` kolon-dizisi gönderiyor.

- [ ] **Step 6: Run the gate**

Run: `./verify.sh`
Expected: `KAPI YEŞİL`. `SKIP: zincir (DATABASE_URL yok)` satırı beklenir ve **geçmek değildir** —
canlı doğrulama Step 7'de.

- [ ] **Step 7: Verify against real Postgres — inside a transaction, rolled back**

Append-only tabloya yazılan test satırı **silinemez**. Sondayı işlem içinde koş ve geri al:

```bash
DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d= -f2-)" uv run python - <<'PY'
from datetime import UTC, datetime
from football_edge.db import connect, insert_snapshots, upsert_matches
from football_edge.odds_api import PriceRow

rows = tuple(
    PriceRow("probe-evt", "soccer_epl", "2036-01-01T18:00:00Z", "A", "B",
             f"book{i}", "2036-01-01T10:00:00Z", "h2h", "A", None, 1.90 + i / 100)
    for i in range(200)
)
with connect() as conn:
    upsert_matches(conn, rows, "eng.1")
    written = insert_snapshots(conn, rows, datetime.now(UTC), is_closing=False)
    print("yazıldı:", len(written))
    conn.rollback()          # GERİ AL — defter append-only, kalıcı olur
    print("geri alındı")
PY
```

Expected: `yazıldı: 200` ve `geri alındı`. Yazım hatası, tip uyumsuzluğu veya `unnest` cast
hatası **yalnız burada** patlar (DEFERRED §5/6: yeni SQL şekilleri gerçek Postgres'e karşı hiç
koşmadı). `eng.1` ligi tabloda yoksa önce `uv run python -m football_edge.collect snapshot`
ile aynayı tazele ya da sondayı mevcut bir `league_id` ile koş.

- [ ] **Step 8: Commit**

```bash
git add src/football_edge/db.py tests/fake_db.py tests/test_db.py
git commit -m "perf: oran defterine toplu yazma; ertelenen maçın saati tazelenir

Faz 0'ın ilk canlı turu 3717 satırı ~4 dakikada yazdı (satır başına bir INSERT).
Mühür penceresi 20 dakika ve snapshot ile seal aynı concurrency grubunda; kaçan
mühür geri gelmez. Tek ifade + unnest WITH ORDINALITY ile zincir sırası korunur.

upsert_matches artık commence_time'ı tazeliyor: DO NOTHING ertelenen maçı eski
saatiyle bırakıyor ve maç mühür penceresinden sessizce düşüyordu (DEFERRED §3.1).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Faz 0 borcu — `verify-chain --full` ve çıpa kapsaması

`docs/DEFERRED.md` §1.1–§1.3'ün üçü de aynı boşluğun yüzleri: **bir çıpa varken defterin İÇİ bir
daha hash'lenmiyor.** `_verify_chain_command` yalnız (i) çıpanın gösterdiği tek satırı ve (ii) en
yeni çıpadan sonraki kuyruğu ölçer. 2..3718 arası satırlar hiçbir zamanlanmış koşuda
doğrulanmaz — ve çıpalar hep ileri gittiği için hiç doğrulanmayacak.

Üstelik **silinen çıpa hiçbir şey bastırmıyor**: `_scan_anchors` yalnız var olan dosyaları görür.
"Dün üç çıpa vardı" bilgisi hiçbir yerde tutulmuyor, ve silme meşru arşivleme prosedüründen
(RUNBOOK §1.4) ayırt edilemiyor. Bunun **dışarıda tutulan** karşılığı zaten var: git geçmişi.

**Files:**
- Modify: `src/football_edge/collect.py`
- Modify: `tests/test_verify_chain.py`

**Interfaces:**
- Consumes: `football_edge.ledger.verify_chain`, `payload_of`, `row_hash` (değişmedi)
- Produces:
  - `_verify_chain_command(conn, *, anchor_dir=ANCHOR_DIR, full=False) -> int`
  - `expected_anchor_names(directory: Path) -> tuple[str, ...] | None` — git geçmişinden
    eklenen çıpa dosyası adları; git yoksa `None`
  - `missing_anchors(directory: Path) -> tuple[str, ...]` — geçmişte var, diskte yok
  - CLI: `python -m football_edge.collect verify-chain --full`

- [ ] **Step 1: Write the failing test**

`tests/test_verify_chain.py` dosyasının SONUNA ekle:

```python
def test_full_scan_rehashes_rows_before_the_anchor(tmp_path: Path) -> None:
    """Varsayılan mod çıpanın ÖNCESİNİ hiç okumuyor; --full okumak zorunda."""
    rows = list(chained_rows(6))
    anchor = tmp_path / "head-2026-09-19.txt"
    anchor.write_text(
        f"2026-09-19T00:00:00+00:00\nrows=6\nlast_id=6\nhead={rows[-1]['row_hash']}\n",
        encoding="utf-8",
    )
    rows[2] = {**rows[2], "price": Decimal("9.99")}  # çıpanın ÖNÜNDEKİ bir satır kurcalandı
    db = FakeChainDb(rows=tuple(rows))

    assert _verify_chain_command(db, anchor_dir=tmp_path) == 0, "varsayılan mod bunu göremez"
    assert _verify_chain_command(db, anchor_dir=tmp_path, full=True) == 1


def test_full_scan_asks_every_anchor_not_just_first_and_last(tmp_path: Path) -> None:
    """asked = (anchors[0], anchors[-1]) — 30 günde 28 çıpa hiç sorulmuyordu."""
    rows = chained_rows(9)
    for index, count in ((0, 3), (1, 6), (2, 9)):
        day = 17 + index
        (tmp_path / f"head-2026-09-{day}.txt").write_text(
            f"2026-09-{day}T00:00:00+00:00\nrows={count}\nlast_id={count}\n"
            f"head={rows[count - 1]['row_hash']}\n",
            encoding="utf-8",
        )
    # ORTADAKİ çıpayı yalancı yap: ne ilk ne son.
    (tmp_path / "head-2026-09-18.txt").write_text(
        "2026-09-18T00:00:00+00:00\nrows=6\nlast_id=6\nhead=" + "b" * 64 + "\n",
        encoding="utf-8",
    )
    db = FakeChainDb(rows=rows)

    assert _verify_chain_command(db, anchor_dir=tmp_path) == 0, "orta çıpa sorulmuyordu"
    assert _verify_chain_command(db, anchor_dir=tmp_path, full=True) == 1


def test_missing_anchor_is_reported_by_name(tmp_path: Path, capsys: Any) -> None:
    """Silinen çıpa bozulandan SESSİZDİR: _scan_anchors yalnız var olanı görür."""
    (tmp_path / "head-2026-09-19.txt").write_text("x\nrows=0\nlast_id=0\nhead=z\n", encoding="utf-8")
    recorded = ("head-2026-09-18.txt", "head-2026-09-19.txt")

    assert missing_anchors(tmp_path, recorded=recorded) == ("head-2026-09-18.txt",)


def test_missing_anchor_check_is_named_when_git_is_absent(tmp_path: Path) -> None:
    """Atlanan kontrol geçmek değildir; git yoksa None döner ve çağıran adıyla yazar."""
    assert expected_anchor_names(tmp_path) is None


def test_shallow_clone_skips_by_name_rather_than_passing_vacuously(tmp_path: Path) -> None:
    """Sığ klonda `git log` BAŞARILI olup boş döner — kontrol sessizce geçerdi.

    `actions/checkout` varsayılanı `fetch-depth: 1`. Boş liste dönmek, "hiç çıpa yok" ile
    "geçmişi göremiyorum"u aynı şeye indirger. İkincisi bir ATLAMADIR ve adıyla yazılır.
    """
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "ledger").mkdir()
    # Sığ olmayan taze depo: geçmiş var (boş), None DEĞİL boş demet beklenir.
    assert expected_anchor_names(tmp_path / "ledger") == ()
```

`tests/test_verify_chain.py`'nin import bloğuna ekle:

```python
from decimal import Decimal
from typing import Any

from football_edge.collect import (
    _verify_chain_command,
    expected_anchor_names,
    missing_anchors,
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_verify_chain.py -v -k "full_scan or missing_anchor or git_is_absent"`
Expected: FAIL — `ImportError: cannot import name 'expected_anchor_names'` ve
`_verify_chain_command() got an unexpected keyword argument 'full'`.

- [ ] **Step 3: Implement the full scan and anchor coverage**

`src/football_edge/collect.py`'ye ekle (`_first_anchor_break`'in hemen altına):

```python
def expected_anchor_names(directory: Path = ANCHOR_DIR) -> tuple[str, ...] | None:
    """Git geçmişine EKLENMİŞ çıpa dosyalarının adları; git yoksa None.

    Silinen çıpa, bozulan çıpadan sessizdir: `_scan_anchors` yalnız diskte duranı görür ve
    silme, RUNBOOK §1.4'teki meşru arşivlemeden ayırt edilemez (DEFERRED §1.3). Beklenen kümeyi
    DIŞARIDA tutmak gerekir; dışarısı zaten var — defterin dış kanıtı olan aynı git geçmişi.
    """
    try:
        # SIĞ KLON SESSİZ BİR GEÇİŞTİR: `actions/checkout` varsayılanı `fetch-depth: 1` ve
        # sığ bir depoda `git log` BAŞARILI olup boş liste döner. Boş liste "hiç çıpa
        # yayınlanmamış" ile "geçmişi göremiyorum"u aynı şeye indirger ve kontrol hiçbir
        # şey ölçmeden yeşil verir. Atlanan kontrol geçmek değildir — adıyla atlanır.
        shallow = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        if shallow.stdout.strip() == "true":
            return None
        found = subprocess.run(
            ["git", "log", "--diff-filter=A", "--name-only", "--format=", "--", str(directory)],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    names = tuple(
        Path(line).name
        for line in found.stdout.splitlines()
        if line.strip() and Path(line).name.startswith("head-")
    )
    return tuple(sorted(set(names)))


def missing_anchors(
    directory: Path = ANCHOR_DIR, *, recorded: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    """Geçmişte yayınlanmış ama diskte OLMAYAN çıpalar."""
    expected = expected_anchor_names(directory) if recorded is None else recorded
    if expected is None:
        return ()
    present = {target.name for target in directory.glob("head-*.txt")}
    return tuple(name for name in expected if name not in present)
```

Modülün import bloğuna `import subprocess` ekle (alfabetik: `import sys`'in üstüne).

`_verify_chain_command`'ı şununla değiştir:

```python
def _verify_chain_command(
    conn: psycopg.Connection[Any], *, anchor_dir: Path = ANCHOR_DIR, full: bool = False
) -> int:
    scan = _scan_anchors(anchor_dir)
    anchors = scan.readable
    if scan.downgraded is not None and anchors:
        sys.stdout.write(
            f"en yeni çıpa okunamadı ({scan.downgraded.name}) — kuyruk kesme kontrolü "
            "bir önceki çıpaya düşürüldü, EN YENİ ÇIPA ATLANDI\n"
        )
    if expected_anchor_names(anchor_dir) is None:
        # Atlanan kontrol geçmek değildir: sessiz kalınmaz, adıyla yazılır.
        sys.stdout.write("git geçmişi okunamadı — ÇIPA EKSİKLİĞİ KONTROLÜ ATLANDI\n")
    else:
        gone = missing_anchors(anchor_dir)
        if gone:
            sys.stdout.write("ÇIPA EKSİK (git geçmişinde var, diskte yok): " + ", ".join(gone) + "\n")
            return 1
    if not anchors:
        sys.stdout.write("çıpa yok ya da okunamadı — kuyruk kesme kontrolü ATLANDI\n")
        return _report_chain(verify_chain(_ledger_rows(conn, None)))
    # --full: HER çıpa sorulur ve defter GENESIS'ten yeniden hash'lenir. Varsayılan mod
    # yalnız (en eski, en yeni) çifti sorar ve yalnız kuyruğu tarar — aradaki satırlar hiç
    # yeniden hash'lenmez (DEFERRED §1.1, §1.2).
    asked = anchors if (full or len(anchors) == 1) else (anchors[0], anchors[-1])
    breakage = _first_anchor_break(conn, asked)
    if breakage is not None:
        sys.stdout.write(f"ÇIPA UYUŞMAZLIĞI: {breakage}\n")
        return 1
    newest = anchors[-1]
    if full:
        sys.stdout.write(f"tam tarama: {len(asked)} çıpa soruldu, defter GENESIS'ten taranıyor\n")
        return _report_chain(verify_chain(_ledger_rows(conn, None)))
    if newest.last_id <= 0:
        return _report_chain(verify_chain(_ledger_rows(conn, None)))
    return _report_chain(verify_chain(_ledger_rows(conn, newest.last_id), start_hash=newest.head))
```

`main()` içinde argüman ayrıştırmasını genişlet:

```python
    parser.add_argument("command", choices=("snapshot", "seal", "verify-chain", "publish-head"))
    parser.add_argument(
        "--full",
        action="store_true",
        help="verify-chain: defteri GENESIS'ten yeniden hash'le ve HER çıpayı sor",
    )
```

ve `verify-chain` dalını:

```python
        if args.command == "verify-chain":
            return _verify_chain_command(conn, full=args.full)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_verify_chain.py -v`
Expected: hepsi PASS.

- [ ] **Step 5: Add the weekly full scan to CI**

`.github/workflows/seal.yml` bir `verify-chain` adımı taşıyor; **ona dokunma** (her 15 dakikada
tam tarama, defter büyüdükçe pahalı hâle gelir). Bunun yerine yeni dosya
`.github/workflows/full-scan.yml`:

```yaml
name: full-scan

# Defterin İÇİ hiçbir zamanlanmış koşuda yeniden hash'lenmiyordu: `seal.yml` yalnız en yeni
# çıpadan SONRAKİ kuyruğu tarar ve çıpalar hep ileri gider (DEFERRED §1.1). Haftada bir tam
# tarama, o boşluğu kapatan tek şeydir. Maliyeti gerçek ve büyüyor — 3 717 satır bugün ucuz,
# 12 ayda değil; pahalılaştığında AYLIK yapılır, kapı gevşetilmez.
on:
  schedule:
    - cron: "23 4 * * 0"   # Pazar 04:23 UTC — mühür turlarının en seyrek olduğu saat
  workflow_dispatch:

concurrency:
  # Deftere YAZMAZ ama okuması uzun sürer; mühür turuyla yarıştırmaya gerek yok.
  group: odds-collect
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  full-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          # Çıpa eksikliği kontrolü `git log` okur; sığ klon geçmişi görmez ve kontrol
          # SESSİZCE atlanır. Atlanan kontrol geçmek değildir — bu yüzden tam geçmiş.
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.11"
      - run: uv sync --frozen
      - name: Tam zincir taraması
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: uv run python -m football_edge.collect verify-chain --full
```

`tests/test_workflows.py` workflow'lar hakkında yapısal iddialar kuruyor; yeni dosyayı oraya
tanıt (o testin mevcut deseni neyse onu izle — `full-scan.yml`'in `schedule` taşıdığını ve
`contents: read` olduğunu iddia eden bir vaka ekle).

- [ ] **Step 6: Run the gate and commit**

```bash
./verify.sh
git add src/football_edge/collect.py tests/test_verify_chain.py tests/test_workflows.py .github/workflows/full-scan.yml
git commit -m "feat: verify-chain --full ve çıpa eksikliği kontrolü

Çıpa varken defterin içi bir daha hash'lenmiyordu; çıpalar hep ileri gittiği için
2..N arası satırlar hiç doğrulanmayacaktı (DEFERRED §1.1). --full defteri
GENESIS'ten tarar ve HER çıpayı sorar (§1.2).

Silinen çıpa bozulandan sessizdi ve meşru arşivlemeden ayırt edilemiyordu (§1.3);
beklenen küme artık git geçmişinden türetiliyor. Git yoksa kontrol ADIYLA atlanır.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---
### Task 3: Kaynak kayıt defteri ve robots.txt'in KODLA zorlanması

Spec §3.2 bugüne kadar **prose**'du: "robots.txt'i otomatik erişime kapalı kaynak taranmaz."
Hiçbir şey bunu zorlamıyordu. `~/.claude/rules/qa-loop.md`'nin ayırdığı iki sütun tam olarak bu:
*garanti* ile *rica*. Bu task kuralı garanti sütununa taşır — disallow edilen bir yolu isteyen
toplayıcı **testte patlar**, üretimde değil.

Kayıt defteri §0'daki ölçümü de kalıcılaştırır: bir daha "Understat kapalıydı galiba" denmez.

**Files:**
- Create: `config/sources.yaml`, `config/robots/` (7 dosya), `src/football_edge/sources.py`,
  `tests/test_sources.py`, `scripts/robots_drift.py`, `.github/workflows/sources-audit.yml`
- Modify: `verify.sh` (yeni adım), `src/football_edge/collect.py` (yeni alt komut)
- **Bağımlılık eklenmez** — `pyproject.toml` Task 4'ün işi.

**Interfaces:**
- Consumes: yok
- Produces:
  - `Source` frozen dataclass: `id, base_url, user_agent, crawl_delay_seconds, robots_verified_at: date, declared_paths: tuple[str, ...], enabled: bool, note: str`
  - `SourceBlocked(RuntimeError)`
  - `load_sources(path: Path) -> tuple[Source, ...]`
  - `enabled_sources(sources: tuple[Source, ...]) -> tuple[Source, ...]`
  - `robots_for(source: Source, robots_dir: Path) -> RobotFileParser`
  - `allows(parser: RobotFileParser, source: Source, path: str) -> bool`
  - `guard_path(parser: RobotFileParser, source: Source, path: str) -> None` — izin yoksa `SourceBlocked`
  - `audit_offline(sources, robots_dir, today, *, max_age_days=30) -> tuple[str, ...]` — ihlal metinleri
  - CLI: `python -m football_edge.collect sources-audit`

- [ ] **Step 1: Write the failing test**

`tests/test_sources.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from football_edge.sources import (
    Source,
    SourceBlocked,
    allows,
    audit_offline,
    enabled_sources,
    guard_path,
    load_sources,
    robots_for,
)

UNDERSTAT_ROBOTS = "User-agent: *\nDisallow: /\n"
FOOTYSTATS_ROBOTS = (
    "User-agent: ClaudeBot\nCrawl-delay: 1\n\n"
    "User-agent: *\nDisallow: /api/club*\nDisallow: /*.php\nDisallow: /matches?*\n"
)
AJANSSPOR_ROBOTS = (
    "User-agent: *\n"
    "Content-Signal: ai-train=no, search=yes, ai-input=yes\n"
    "Disallow: /lineup/\nDisallow: /mac/\nDisallow: /oyuncu/\nDisallow: /lig/\n"
)


def source(**overrides: object) -> Source:
    base = {
        "id": "footystats",
        "base_url": "https://footystats.org",
        "user_agent": "ClaudeBot/1.0 (+https://anthropic.com/claudebot)",
        "crawl_delay_seconds": 1.0,
        "robots_verified_at": date(2026, 9, 19),
        "declared_paths": ("/turkey/super-lig/xg",),
        "enabled": True,
        "note": "",
    }
    return Source(**{**base, **overrides})  # type: ignore[arg-type]


def write_robots(directory: Path, source_id: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{source_id}.txt"
    target.write_text(body, encoding="utf-8")
    return target


def test_site_wide_disallow_blocks_every_path(tmp_path: Path) -> None:
    """Understat: `User-agent: * / Disallow: /`. Spec §3.2/1 — taranmaz."""
    write_robots(tmp_path, "understat", UNDERSTAT_ROBOTS)
    understat = source(id="understat", base_url="https://understat.com")
    parser = robots_for(understat, tmp_path)

    assert allows(parser, understat, "/league/EPL") is False
    assert allows(parser, understat, "/") is False


def test_allowed_path_passes_and_disallowed_path_raises(tmp_path: Path) -> None:
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    footystats = source()
    parser = robots_for(footystats, tmp_path)

    guard_path(parser, footystats, "/turkey/super-lig/xg")  # patlamamalı
    with pytest.raises(SourceBlocked, match="footystats"):
        guard_path(parser, footystats, "/c-dl.php")


def test_ajansspor_structural_paths_are_closed_but_news_is_open(tmp_path: Path) -> None:
    """robots `/lineup/`, `/mac/`, `/oyuncu/`, `/lig/` kapatıyor — muhtemel 11 ALINMAZ."""
    write_robots(tmp_path, "ajansspor", AJANSSPOR_ROBOTS)
    ajansspor = source(id="ajansspor", base_url="https://ajansspor.com", crawl_delay_seconds=1.0)
    parser = robots_for(ajansspor, tmp_path)

    assert allows(parser, ajansspor, "/lineup/galatasaray") is False
    assert allows(parser, ajansspor, "/mac/12345") is False
    assert allows(parser, ajansspor, "/futbol/galatasaray-haberleri") is True


def test_empty_robots_file_allows_everything(tmp_path: Path) -> None:
    """TFF'de robots.txt YOK (404) ve ClubElo'nunki boş. Boş politika = kısıt yok.

    `RobotFileParser.can_fetch` HİÇ parse edilmemişken False döner; boş gövdeyle parse
    edilince True. İkisini karıştırmak, izinli kaynağı sessizce kapatır.
    """
    write_robots(tmp_path, "tff", "")
    tff = source(id="tff", base_url="https://www.tff.org")
    parser = robots_for(tff, tmp_path)

    assert allows(parser, tff, "/Default.aspx?pageID=600") is True


def test_missing_snapshot_is_a_violation_not_a_pass(tmp_path: Path) -> None:
    """Anlık görüntü yoksa kapı YEŞİL VERMEZ. Ölçülmemiş politika, izin değildir."""
    violations = audit_offline((source(),), tmp_path, date(2026, 9, 19))
    assert any("anlık görüntü yok" in text for text in violations)


def test_declared_path_that_robots_forbids_is_a_violation(tmp_path: Path) -> None:
    """Toplayıcının beyan ettiği yol robots'a uymuyorsa, kod yazılmadan kapı kırmızı verir."""
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    violations = audit_offline(
        (source(declared_paths=("/turkey/super-lig/xg", "/c-dl.php")),),
        tmp_path,
        date(2026, 9, 19),
    )
    assert any("/c-dl.php" in text for text in violations)


def test_stale_verification_is_a_violation(tmp_path: Path) -> None:
    """robots 30 günden eski ölçüldüyse 'izinli' bir iddia değil, bir hatıradır."""
    write_robots(tmp_path, "footystats", FOOTYSTATS_ROBOTS)
    violations = audit_offline((source(),), tmp_path, date(2026, 11, 1))
    assert any("30 günden eski" in text for text in violations)


def test_disabled_sources_are_not_audited(tmp_path: Path) -> None:
    """Kapalı kaynak taranmıyor; anlık görüntüsü eksik diye kapı kırmızı vermez."""
    assert audit_offline((source(enabled=False),), tmp_path, date(2026, 9, 19)) == ()


def test_registry_loads_and_filters(tmp_path: Path) -> None:
    target = tmp_path / "sources.yaml"
    target.write_text(
        "sources:\n"
        "  - id: footystats\n"
        "    base_url: https://footystats.org\n"
        "    user_agent: ClaudeBot/1.0\n"
        "    crawl_delay_seconds: 1.0\n"
        "    robots_verified_at: 2026-09-19\n"
        "    declared_paths: ['/turkey/super-lig/xg']\n"
        "    enabled: true\n"
        "    note: ''\n"
        "  - id: understat\n"
        "    base_url: https://understat.com\n"
        "    user_agent: ClaudeBot/1.0\n"
        "    crawl_delay_seconds: 1.0\n"
        "    robots_verified_at: 2026-09-19\n"
        "    declared_paths: []\n"
        "    enabled: false\n"
        "    note: 'robots.txt Disallow: / — spec §3.2/1'\n",
        encoding="utf-8",
    )
    loaded = load_sources(target)

    assert len(loaded) == 2
    assert tuple(entry.id for entry in enabled_sources(loaded)) == ("footystats",)
    assert loaded[0].robots_verified_at == date(2026, 9, 19)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.sources'`

- [ ] **Step 3: Write the implementation**

`src/football_edge/sources.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

import yaml


class SourceBlocked(RuntimeError):
    """Kaynak politikası bu yolu kapatıyor. İstek ATILMAZ.

    Spec §3.2/1-2: robots.txt'i otomatik erişime kapalı kaynak taranmaz, erişim kontrolü
    aşılmaz. Bu istisna o kuralın KODDAKİ karşılığıdır; yakalanıp yutulursa kural yine
    prose'a döner.
    """


@dataclass(frozen=True)
class Source:
    id: str
    base_url: str
    user_agent: str
    crawl_delay_seconds: float
    robots_verified_at: date
    declared_paths: tuple[str, ...]
    enabled: bool
    note: str


REQUIRED_FIELDS = frozenset(
    {
        "id",
        "base_url",
        "user_agent",
        "crawl_delay_seconds",
        "robots_verified_at",
        "declared_paths",
        "enabled",
        "note",
    }
)


def _validate(entry: dict[str, Any], seen: frozenset[str]) -> None:
    keys = frozenset(entry)
    missing = REQUIRED_FIELDS - keys
    if missing:
        raise ValueError(f"kaynak kaydında eksik alan: {sorted(missing)} ({entry.get('id', '?')})")
    unknown = keys - REQUIRED_FIELDS
    if unknown:
        raise ValueError(f"kaynak kaydında bilinmeyen alan: {sorted(unknown)} ({entry['id']})")
    if entry["id"] in seen:
        raise ValueError(f"yinelenen kaynak id: {entry['id']}")


def load_sources(path: Path) -> tuple[Source, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "sources" not in raw:
        raise ValueError(f"{path}: kökte 'sources' anahtarı yok")
    sources: tuple[Source, ...] = ()
    seen: frozenset[str] = frozenset()
    for entry in raw["sources"]:
        _validate(entry, seen)
        sources = (
            *sources,
            Source(**{**entry, "declared_paths": tuple(entry["declared_paths"])}),
        )
        seen = seen | {entry["id"]}
    return sources


def enabled_sources(sources: tuple[Source, ...]) -> tuple[Source, ...]:
    return tuple(entry for entry in sources if entry.enabled)


def robots_snapshot(source: Source, robots_dir: Path) -> Path:
    return robots_dir / f"{source.id}.txt"


def robots_for(source: Source, robots_dir: Path) -> RobotFileParser:
    """Commit'lenmiş robots.txt anlık görüntüsünü ayrıştırır.

    `parse()` ÇAĞRILMAZSA `can_fetch` her yola False der (CPython: "until the robots.txt file
    has been read ... we must assume that no url is allowable"). Boş gövdeyle parse edilince
    ise True döner. İkisi farklıdır: biri "bilmiyoruz", diğeri "kısıt yok". Boş dosya, ölçülmüş
    ve boş çıkmış bir politikadır (TFF'de robots.txt 404, ClubElo'nunki boş) — ve parse edilir.
    """
    parser = RobotFileParser()
    parser.parse(robots_snapshot(source, robots_dir).read_text(encoding="utf-8").splitlines())
    return parser


def allows(parser: RobotFileParser, source: Source, path: str) -> bool:
    return bool(parser.can_fetch(source.user_agent, f"{source.base_url}{path}"))


def guard_path(parser: RobotFileParser, source: Source, path: str) -> None:
    if not allows(parser, source, path):
        raise SourceBlocked(f"{source.id}: robots.txt '{path}' yolunu kapatıyor — istek atılmadı")


def audit_offline(
    sources: tuple[Source, ...],
    robots_dir: Path,
    today: date,
    *,
    max_age_days: int = 30,
) -> tuple[str, ...]:
    """Ağ GEREKTİRMEYEN kaynak politikası denetimi; ihlal metinlerini döner.

    Kapının bu adımı her push'ta koşar, secret istemez ve ağa çıkmaz. Canlı sapmayı
    `sources-audit.yml` günde bir ölçer. Sözleşme kapıda, sapma zamanlanmış işte —
    `snapshot`/`seal` ayrımının aynısı.
    """
    violations: tuple[str, ...] = ()
    for source in enabled_sources(sources):
        snapshot = robots_snapshot(source, robots_dir)
        if not snapshot.is_file():
            violations = (*violations, f"{source.id}: robots anlık görüntü yok ({snapshot})")
            continue
        if today - source.robots_verified_at > timedelta(days=max_age_days):
            violations = (
                *violations,
                f"{source.id}: robots doğrulaması {max_age_days} günden eski "
                f"({source.robots_verified_at})",
            )
        parser = robots_for(source, robots_dir)
        for path in source.declared_paths:
            if not allows(parser, source, path):
                violations = (*violations, f"{source.id}: beyan edilen yol robots'a aykırı: {path}")
    return violations
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sources.py -v`
Expected: 9 PASS

- [ ] **Step 5: Capture the robots snapshots**

Ölçümü **kaydet**; ezberleme. Her dosya, §0'daki tablonun makine tarafından okunabilir hâlidir.

```bash
mkdir -p config/robots
# R9: KENDI kimligimizle tanitiriz. FootyStats'in robots'u ClaudeBot'a kendi grubunu
# (Crawl-delay 1, hic Disallow yok) veriyor; o izin Anthropic'in tarayicisina verilmis,
# bize degil. Baskasinin kimligini almak user-agent sahteciligidir.
UA='football-edge/0.1 (+https://github.com/popiliadam/football-edge)'
for pair in "footystats:https://footystats.org" "tff:https://www.tff.org" \
            "ajansspor:https://ajansspor.com" "openmeteo:https://api.open-meteo.com" \
            "wikidata:https://www.wikidata.org" "googlenews:https://news.google.com" \
            "understat:https://understat.com"; do
  id="${pair%%:*}"; base="${pair#*:}"
  code=$(curl -sS -m 25 -A "$UA" -o "config/robots/$id.txt" -w '%{http_code}' "$base/robots.txt" || echo 000)
  # 404/000 = politika dosyası YOK. Boş dosya "kısıt yok" demektir ve parse edilir;
  # eksik dosya kapıyı kırmızıya düşürür. İkisini karıştırma.
  if [ "$code" != "200" ]; then : > "config/robots/$id.txt"; fi
  printf '%-12s HTTP %s  %s bayt\n' "$id" "$code" "$(wc -c < "config/robots/$id.txt" | tr -d ' ')"
done
```

Expected (2026-09-19 ölçümü):
`footystats` 200 · `tff` 404→boş · `ajansspor` 200 · `openmeteo` 200 ya da 404 ·
`wikidata` 200 · `googlenews` 200 · `understat` 200 (26 bayt, `Disallow: /`).

**Doğrula:** `cat config/robots/understat.txt` → `User-agent: *` ve `Disallow: /` görmeli.
Görmüyorsan ölçüm yanlış; §0.1'in dayanağı odur, düzeltmeden devam etme.

- [ ] **Step 6: Write the registry**

`config/sources.yaml`:

```yaml
# Kaynak kayıt defteri. `declared_paths`, toplayıcının GERÇEKTEN istediği yollardır ve kapı
# her push'ta bunları config/robots/<id>.txt'ye karşı sorar. Yeni bir yol eklemeden önce
# robots'a bak; kapı zaten bakacak.
#
# Ölçüm tarihi 2026-09-19. `robots_verified_at` 30 günden eskiyse kapı kırmızı verir —
# tazelemek için Task 3 Step 5'teki komutu yeniden koş ve tarihleri güncelle.
sources:
  - id: footystats
    base_url: https://footystats.org
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 5.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/turkey/super-lig/xg']
    enabled: true
    note: >-
      R9: ClaudeBot grubunun Crawl-delay 1 izni Anthropic'in tarayıcısınadır, bizim değil —
      o kimliği almak sahteciliktir. `*` grubu altındayız ve altı /xg yolunun altısı da
      orada izinli. `*` Crawl-delay bildirmiyor; 5.0 sitenin adlandırılmış bir üçüncü
      taraf tarayıcıya verdiği en hızlı değerdir (R13).

  - id: tff
    base_url: https://www.tff.org
    user_agent: football-edge/0.1
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/Default.aspx?pageID=600', '/Default.aspx?pageID=246']
    enabled: true
    note: 'robots.txt YOK (404). Gövde windows-1254; charset YALNIZ HTTP başlığında.'

  - id: ajansspor
    base_url: https://ajansspor.com
    user_agent: football-edge/0.1
    crawl_delay_seconds: 1.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/sitemap.xml']
    enabled: true
    note: >-
      Content-Signal: ai-train=no, search=yes, ai-input=yes. /lineup/, /mac/, /oyuncu/,
      /lig/ ve *rsc=* DISALLOW — muhtemel 11 ve yapısal sayfalar ALINMAZ, yalnız haber yolları.

  - id: openmeteo
    base_url: https://api.open-meteo.com
    user_agent: football-edge/0.1
    crawl_delay_seconds: 0.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/v1/forecast']
    enabled: true
    note: 'Anahtarsız, ücretsiz. Yanıt `elevation` alanını doğrudan veriyor.'

  - id: wikidata
    base_url: https://www.wikidata.org
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 1.0
    robots_verified_at: 2026-09-19
    declared_paths: ['/wiki/Special:EntityData']
    enabled: true
    note: >-
      SPARQL ucu DEĞİL REST kullanılır: Special:EntityData/<QID>.json düz bir GET'tir.
      SPARQL, yerel outward_action_gate tarafından net_post olarak engelleniyor.

  - id: googlenews
    base_url: https://news.google.com
    user_agent: football-edge/0.1
    crawl_delay_seconds: 1.0
    robots_verified_at: 2026-09-19
    declared_paths: []
    enabled: false
    note: >-
      KAPALI (Ruling B). Feed 200 dönüyor ve hl/gl/ceid çalışıyor, ama feed'in kendi
      <copyright> metni: "solely for the purpose of rendering Google News results within a
      personal feed reader for personal, non-commercial use. Any other use of the feed is
      expressly prohibited." Adaptör yazıldı, varsayılan kapalı; ticari karar operatörde.

  - id: understat
    base_url: https://understat.com
    user_agent: football-edge/0.1
    crawl_delay_seconds: 1.0
    robots_verified_at: 2026-09-19
    declared_paths: []
    enabled: false
    note: >-
      KAPALI (Ruling A). robots.txt = "User-agent: * / Disallow: /" (26 bayt,
      Last-Modified 2020-07-13). Spec §3.2/1 gereği taranmaz. xG kapsamını footystats devraldı.
```

**Not:** FBref ve ClubElo kayıt defterinde **yoktur** — `declared_paths` boş bir kapalı kayıt,
denetimin hiçbir şey ölçmediği bir satırdır. İkisi de `docs/DEFERRED.md`'ye yazılır (Task 13).

- [ ] **Step 7: Add the gate step and the CLI command**

`src/football_edge/collect.py`'ye ekle:

```python
SOURCES_PATH = Path("config/sources.yaml")
ROBOTS_DIR = Path("config/robots")
EXIT_SOURCE_POLICY = 6


def _sources_audit_command(*, today: date) -> int:
    violations = audit_offline(load_sources(SOURCES_PATH), ROBOTS_DIR, today)
    if not violations:
        sys.stdout.write("kaynak politikası: TEMİZ\n")
        return 0
    for text in violations:
        sys.stdout.write(f"KAYNAK POLİTİKASI İHLALİ: {text}\n")
    return EXIT_SOURCE_POLICY
```

Import bloğuna `from datetime import date` ve `from football_edge.sources import audit_offline, load_sources` ekle.
`main()`'in `choices` demetine `"sources-audit"` ekle ve `connect()` **açılmadan önce** — bu komut
veritabanına dokunmaz — şu dalı koy:

```python
    if args.command == "sources-audit":
        return _sources_audit_command(today=now.date())
```

`verify.sh` içinde `step "secrets"` satırının **üstüne** ekle:

```bash
# Kaynak politikası ÇEVRİMDIŞI sorulur: ağ yok, secret yok, her push'ta koşar. Canlı sapmayı
# sources-audit.yml günde bir ölçer. Robots'u ölçmeden "izinli" demek, spec §3.2'yi prose'a
# geri çevirir; bu adım onu kuralda tutar.
step "kaynak-politikası" env PYTHONPATH= uv run python -m football_edge.collect sources-audit
```

`EXIT_SOURCE_POLICY = 6` için `collect.py`'deki çıkış kodu yorum bloğuna bir satır ekle
(her kodun workflow'da adlandırılmış bir `case` arm'ı olmalı — `tests/test_workflows.py` bu bağı tutar).

- [ ] **Step 8: Add the live drift workflow**

`.github/workflows/sources-audit.yml`:

```yaml
name: sources-audit

# Kapanan kaynak kadar AÇILAN kaynak da olaydır: FBref'in 403'ü ve ClubElo'nun 502'si bu
# makineden (TR) ölçüldü; runner ABD/AB'de. Bu iş her gün runner'dan ölçer ve commit'lenmiş
# anlık görüntüyle diff'ler. Politika değişirse kırmızı verir — iki yönde de.
on:
  schedule:
    - cron: "41 5 * * *"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  audit:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.11"
      - run: uv sync --frozen
      - name: Çevrimdışı sözleşme
        run: uv run python -m football_edge.collect sources-audit
      - name: Canlı robots.txt sapması
        run: uv run python scripts/robots_drift.py
      - name: FBref ve ClubElo yeniden ölçümü
        # Bilgilendirme: bu iki kaynak TR'den kapalı ölçüldü ve plan onları kapsam dışı
        # bıraktı (Ruling A). Runner'dan AÇIK çıkarlarsa bu adım bunu görünür kılar; kararı
        # değiştirmez, kararın dayanağını tazeler. `|| true`: bu adım işi düşürmez.
        run: |
          curl -sS -m 25 -o /dev/null -w 'fbref robots HTTP %{http_code}\n' \
            https://fbref.com/robots.txt || true
          curl -sS -m 25 -w '\nclubelo /Fixtures ^\n' http://api.clubelo.com/Fixtures || true
```

`scripts/robots_drift.py`:

```python
#!/usr/bin/env python3
"""Canlı robots.txt'leri commit'lenmiş anlık görüntülerle karşılaştırır.

KAPALI kaynaklar da taranır: kapanan kaynak kadar AÇILAN kaynak da olaydır. Understat
bir gün robots'unu gevşetirse bunu görmek isteriz; görmek, kararı değiştirmek zorunda
değildir ama kararın dayanağını tazeler.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

import httpx

from football_edge.sources import load_sources, robots_snapshot

SOURCES = Path("config/sources.yaml")
ROBOTS = Path("config/robots")


def live_robots(client: httpx.Client, base_url: str, user_agent: str) -> str:
    """Canlı robots.txt gövdesi. 404 = politika dosyası YOK ve bu BOŞ metne denktir.

    Eksik dosya ile boş dosya farklıdır (bkz. `sources.robots_for`): biri "bilmiyoruz",
    diğeri "kısıt yok". Burada 404, kayıtlı boş anlık görüntüyle eşleşmelidir.
    """
    response = client.get(
        f"{base_url}/robots.txt",
        headers={"user-agent": user_agent},
        timeout=25.0,
        follow_redirects=True,
    )
    return response.text if response.status_code == 200 else ""


def main() -> int:
    drifted = 0
    with httpx.Client() as client:
        for source in load_sources(SOURCES):
            snapshot = robots_snapshot(source, ROBOTS)
            if not snapshot.is_file():
                continue
            recorded = snapshot.read_text(encoding="utf-8")
            try:
                current = live_robots(client, source.base_url, source.user_agent)
            except httpx.HTTPError as error:
                # ÖLÇÜLEMEYEN kaynak geçmek değildir: adıyla yazılır ve iş kırmızı verir.
                sys.stdout.write(f"ÖLÇÜLEMEDİ: {source.id} — {error}\n")
                drifted = 1
                continue
            if current.strip() == recorded.strip():
                sys.stdout.write(f"sapma yok: {source.id}\n")
                continue
            drifted = 1
            sys.stdout.write(f"ROBOTS SAPMASI: {source.id}\n")
            sys.stdout.writelines(
                difflib.unified_diff(
                    recorded.splitlines(keepends=True),
                    current.splitlines(keepends=True),
                    fromfile=f"{source.id} (kayıtlı)",
                    tofile=f"{source.id} (canlı)",
                )
            )
    return drifted


if __name__ == "__main__":
    raise SystemExit(main())
```

Çalıştığını **yerelde doğrula** — kırmızı verdiği kanıtlanmamış bir denetim, denetim değildir:

```bash
uv run python scripts/robots_drift.py; echo "temizken: $?"     # 0 beklenir
printf '\nDisallow: /uydurma\n' >> config/robots/footystats.txt
uv run python scripts/robots_drift.py; echo "kırıkken: $?"     # 1 + diff beklenir
git checkout -- config/robots/footystats.txt
```

- [ ] **Step 9: Run the gate and commit**

```bash
./verify.sh
git add config/sources.yaml config/robots src/football_edge/sources.py tests/test_sources.py scripts/robots_drift.py verify.sh src/football_edge/collect.py .github/workflows/sources-audit.yml
git commit -m "feat: kaynak kayıt defteri ve robots.txt'in kodla zorlanması

Spec §3.2 bugüne kadar prose'du. Artık: disallow edilen yolu isteyen toplayıcı
SourceBlocked ile patlar, kapı her push'ta beyan edilen yolları commit'lenmiş
robots anlık görüntüsüne karşı sorar, sources-audit.yml günde bir canlı sapmayı
ölçer.

Ölçüldü 2026-09-19: understat Disallow: / (kapalı), footystats ClaudeBot
Crawl-delay 1 (izinli), tff robots yok (izinli), ajansspor /lineup /mac /oyuncu
/lig kapalı — muhtemel 11 alınmaz.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Toplayıcı çatısı ve gözlem deposu

Her toplayıcı aynı iskelete oturur: **izin → fetch → doğrula → yaz**. "Doğrula" iki iddiadır ve
ikisi de spec §8'in "sessiz kaynak arızası" panzehiridir: **tazelik** (veri ne kadar eski) ve
**şema** (beklenen alanlar makul aralıkta mı). Kırılan bir ayrıştırıcının ürettiği **boş liste**,
şema iddiası olmadan başarılı bir turdan ayırt edilemez.

**Files:**
- Create: `src/football_edge/naming.py`, `src/football_edge/collector.py`,
  `src/football_edge/observations.py`, `db/migrations/0002_sources.sql`,
  `tests/test_collector.py`, `tests/test_observations.py`, `tests/fake_sources.py`
- Modify: `verify.sh`, `pyproject.toml`

**Interfaces:**
- Consumes: `football_edge.sources.{Source, guard_path, robots_for, SourceBlocked}`
- Produces:
  - `Observation` frozen dataclass: `source_id: str, entity_kind: str, entity_key: str, observed_at: datetime, payload: dict[str, Any]` (+ `content_hash` özelliği)
  - `ContractViolation(RuntimeError)`
  - `fetch_text(client, source, path, parser, *, expect: str, encoding: str | None = None) -> str`
  - `assert_fresh(observations, now, *, max_age: timedelta, source_id: str) -> None`
  - `assert_schema(observations, *, source_id, required: frozenset[str], minimum_rows: int) -> None`
  - `Breaker` frozen dataclass: `failures: int, opened_at: datetime | None`; `record(breaker, now, *, ok: bool, threshold: int = 3, cooldown: timedelta) -> Breaker`; `is_open(breaker, now, *, cooldown) -> bool`
  - `write_observations(conn, observations) -> int`
  - `latest_observations(conn, source_id, entity_kind) -> tuple[Observation, ...]`
  - **`naming.normalise_team(name: str) -> str`** — paylaşılan ad normalleştirici.
    Task 6 (TFF) ve Task 11 (varlık eşleme) İKİSİ de bunu import eder. Genel amaçlı bir
    normalleştirici tek bir toplayıcının iç detayı olamaz; paralel bir task'ın içine
    gömülü bir sembole sıralı bir task'ın bağlanması cross-worktree kırılganlığıdır.

- [ ] **Step 1: Write the failing test**

`tests/test_collector.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from football_edge.collector import (
    Breaker,
    ContractViolation,
    Observation,
    assert_fresh,
    assert_schema,
    fetch_text,
    is_open,
    record,
)
from football_edge.sources import SourceBlocked, robots_for
from tests.fake_sources import fake_source, write_robots

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def observation(key: str, **payload: object) -> Observation:
    return Observation(
        source_id="footystats",
        entity_kind="team",
        entity_key=key,
        observed_at=NOW,
        payload={"xg": 1.5, "xga": 1.1, **payload},
    )


def test_fetch_refuses_a_disallowed_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """İstek ATILMAZ: robots kontrolü fetch'in İLK işidir, yanıtı filtrelemek değil."""
    write_robots(tmp_path, "blocked", "User-agent: *\nDisallow: /\n")
    source = fake_source(id="blocked")
    parser = robots_for(source, tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text="gelmemeliydi")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceBlocked):
            fetch_text(client, source, "/anything", parser, expect="text/html")

    assert calls == [], "robots kapalıyken HTTP isteği atıldı"


def test_fetch_rejects_a_wrong_content_type(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Spec §7: bazı uçlar 200 dönüp YANLIŞ içerik verir. 200 doğruluk değildir."""
    write_robots(tmp_path, "ok", "")
    source = fake_source(id="ok")
    parser = robots_for(source, tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>hata sayfası</html>", headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ContractViolation, match="content-type"):
            fetch_text(client, source, "/feed", parser, expect="application/xml")


def test_fetch_decodes_with_the_declared_encoding(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """TFF windows-1254: charset YALNIZ HTTP başlığında. httpx'in tahminine bırakılmaz."""
    write_robots(tmp_path, "tff", "")
    source = fake_source(id="tff")
    parser = robots_for(source, tmp_path)
    body = "Süper Lig hakem ataması".encode("windows-1254")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        text = fetch_text(client, source, "/x", parser, expect="text/html", encoding="windows-1254")

    assert "Süper Lig" in text


def test_empty_result_fails_the_schema_assertion() -> None:
    """Kırılan ayrıştırıcı BOŞ LİSTE üretir ve sessizce başarılı görünür — asıl arıza budur."""
    with pytest.raises(ContractViolation, match="en az 1 satır"):
        assert_schema((), source_id="footystats", required=frozenset({"xg"}), minimum_rows=1)


def test_missing_field_fails_the_schema_assertion() -> None:
    with pytest.raises(ContractViolation, match="xga"):
        assert_schema(
            (Observation("footystats", "team", "gs", NOW, {"xg": 1.5}),),
            source_id="footystats",
            required=frozenset({"xg", "xga"}),
            minimum_rows=1,
        )


def test_stale_data_fails_the_freshness_assertion() -> None:
    old = Observation("footystats", "team", "gs", NOW - timedelta(days=9), {"xg": 1.5})
    with pytest.raises(ContractViolation, match="tazelik"):
        assert_fresh((old,), NOW, max_age=timedelta(days=7), source_id="footystats")


def test_fresh_data_passes() -> None:
    assert_fresh((observation("gs"),), NOW, max_age=timedelta(days=7), source_id="footystats")


def test_content_hash_is_stable_and_content_sensitive() -> None:
    """Aynı içerik yeniden gözlenirse yeni satır yazılmaz; depo idempotent olmalı."""
    assert observation("gs").content_hash == observation("gs").content_hash
    assert observation("gs").content_hash != observation("gs", xg=1.6).content_hash


def test_breaker_opens_after_the_threshold_and_closes_after_cooldown() -> None:
    """Kaynak başına devre kesici (spec §8): kırılgan kaynak turu her seferinde düşürmesin."""
    cooldown = timedelta(hours=1)
    breaker = Breaker(failures=0, opened_at=None)
    for _ in range(3):
        breaker = record(breaker, NOW, ok=False, threshold=3, cooldown=cooldown)

    assert is_open(breaker, NOW, cooldown=cooldown) is True
    assert is_open(breaker, NOW + timedelta(hours=2), cooldown=cooldown) is False
    assert record(breaker, NOW, ok=True, threshold=3, cooldown=cooldown).failures == 0
```

`tests/fake_sources.py`:

```python
"""Testler için kaynak kaydı kurgusu."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from football_edge.sources import Source


def fake_source(**overrides: object) -> Source:
    base = {
        "id": "footystats",
        "base_url": "https://example.test",
        "user_agent": "football-edge-test/0.1",
        "crawl_delay_seconds": 0.0,
        "robots_verified_at": date(2026, 9, 19),
        "declared_paths": (),
        "enabled": True,
        "note": "",
    }
    return Source(**{**base, **overrides})  # type: ignore[arg-type]


def write_robots(directory: Path, source_id: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{source_id}.txt"
    target.write_text(body, encoding="utf-8")
    return target
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.collector'`

- [ ] **Step 3: Write the shared name normaliser, then the framework**

`src/football_edge/naming.py`:

```python
from __future__ import annotations

import re
import unicodedata

# Hukuki/kurumsal ekler: eşleşme anahtarına katkısı yok, gürültüsü çok.
_SUFFIXES = re.compile(r"\b(a\.?ş\.?|spor kul(ü|u)b(ü|u)|futbol|sk|as|fk|fc|cf)\b")
_NON_WORD = re.compile(r"[^a-z0-9ğüşıöç ]+")


def normalise_team(name: str) -> str:
    """Kaynaklar arası eşleşme anahtarı: küçük harf, aksan korunur, ek ve noktalama atılır.

    TÜRKÇE'YE ÖZEL VE LOAD-BEARING: Python'da `"I".lower()` `"i"` verir, oysa Türkçe'de
    `I`nın küçüğü `ı`, `İ`nin küçüğü `i`dir. `casefold()` da bunu bilmez. Açık eşleme
    yapılmazsa aynı takım iki kaynakta FARKLI anahtar üretir ve join sessizce boş kalır —
    bu projenin 1 numaralı ölüm sebebi (spec §5.3).

    Task 6 (TFF) ve Task 11 (varlık eşleme) bu TEK fonksiyonu paylaşır. İki kopya tutulursa
    biri diğerinden sessizce ayrışır ve eşleşme anahtarı iki farklı şey olur.
    """
    folded = name.replace("İ", "i").replace("I", "ı").strip().lower()
    folded = unicodedata.normalize("NFC", folded)
    folded = _SUFFIXES.sub(" ", folded)
    folded = _NON_WORD.sub(" ", folded)
    return " ".join(folded.split())
```

Testlerini `tests/test_collector.py`'nin sonuna ekle:

```python
def test_normalise_team_strips_legal_suffixes_and_punctuation() -> None:
    from football_edge.naming import normalise_team

    assert normalise_team("  Galatasaray A.Ş. ") == normalise_team("GALATASARAY AŞ")
    assert normalise_team("Gaziantep F.K.") == normalise_team("gaziantep fk")


def test_normalise_team_uses_turkish_case_rules() -> None:
    """`"I".lower()` Python'da `"i"` verir; Türkçe'de `ı` olmalı. Karıştıran join boş kalır."""
    from football_edge.naming import normalise_team

    assert normalise_team("FENERBAHÇE") == normalise_team("Fenerbahçe")
    assert normalise_team("ISTANBULSPOR") == normalise_team("Istanbulspor")
```

`src/football_edge/collector.py`:

```python
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.robotparser import RobotFileParser

import httpx

from football_edge.sources import Source, guard_path

LOGGER = logging.getLogger("football_edge.collector")


class ContractViolation(RuntimeError):
    """Veri sözleşmesi bozuldu: tazelik, şema ya da içerik türü.

    Yutulursa kaynak arızası SESSİZ olur — spec §8'in panzehiri tam olarak bunun
    gürültülü olmasıdır. Kırılan bir ayrıştırıcı boş liste üretir ve boş liste,
    iddiasız bir turda başarıdan ayırt edilemez.
    """


@dataclass(frozen=True)
class Observation:
    source_id: str
    entity_kind: str
    entity_key: str
    observed_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """İçeriğin kanonik özeti; aynı gözlem iki kez yazılmasın diye.

        `observed_at` HARİÇTİR: aynı xG tablosunu iki saat arayla görmek yeni bir olgu
        değildir. Zaman dâhil edilseydi depo her turda büyür ve tazelik iddiası
        kendi ürettiği gürültüyle her zaman yeşil olurdu.
        """
        canonical = json.dumps(
            {"k": self.entity_kind, "e": self.entity_key, "p": self.payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(f"{self.source_id}{canonical}".encode()).hexdigest()


@dataclass(frozen=True)
class Breaker:
    failures: int
    opened_at: datetime | None


def record(
    breaker: Breaker, now: datetime, *, ok: bool, threshold: int, cooldown: timedelta
) -> Breaker:
    if ok:
        return Breaker(failures=0, opened_at=None)
    failures = breaker.failures + 1
    return Breaker(failures=failures, opened_at=now if failures >= threshold else breaker.opened_at)


def is_open(breaker: Breaker, now: datetime, *, cooldown: timedelta) -> bool:
    if breaker.opened_at is None:
        return False
    return now - breaker.opened_at < cooldown


def fetch_text(
    client: httpx.Client,
    source: Source,
    path: str,
    parser: RobotFileParser,
    *,
    expect: str,
    encoding: str | None = None,
    timeout: float = 30.0,
) -> str:
    """İzin → istek → içerik doğrulaması. Bu SIRA yük taşır.

    İzin kontrolü İLK iştir: yanıtı aldıktan sonra filtrelemek, isteği zaten atmış olmak
    demektir ve spec §3.2 "taranmaz" diyor, "okunmaz" değil.

    `expect` zorunludur çünkü bazı uçlar 200 dönüp yanlış içerik verir (spec §7): 200,
    doğru veriyi aldığımızın kanıtı değildir.

    `encoding` verilirse httpx'in tahmini EZİLİR. TFF'de charset yalnız HTTP başlığındadır
    ve gövdede meta yoktur; tahmine bırakılırsa Türkçe karakterler sessizce bozulur ve
    takım adları hiçbir eşleşmeye uymaz.
    """
    guard_path(parser, source, path)
    if source.crawl_delay_seconds > 0:
        time.sleep(source.crawl_delay_seconds)
    response = client.get(
        f"{source.base_url}{path}",
        headers={"user-agent": source.user_agent},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    received = response.headers.get("content-type", "")
    if expect not in received:
        raise ContractViolation(
            f"{source.id}: beklenen content-type '{expect}', gelen '{received}' ({path})"
        )
    if encoding is None:
        return response.text
    return response.content.decode(encoding, errors="strict")


def assert_schema(
    observations: tuple[Observation, ...],
    *,
    source_id: str,
    required: frozenset[str],
    minimum_rows: int,
) -> None:
    if len(observations) < minimum_rows:
        raise ContractViolation(
            f"{source_id}: şema iddiası — en az {minimum_rows} satır beklendi, "
            f"{len(observations)} geldi"
        )
    for entry in observations:
        missing = required - frozenset(entry.payload)
        if missing:
            raise ContractViolation(
                f"{source_id}: şema iddiası — eksik alan {sorted(missing)} ({entry.entity_key})"
            )


def assert_fresh(
    observations: tuple[Observation, ...],
    now: datetime,
    *,
    max_age: timedelta,
    source_id: str,
) -> None:
    if not observations:
        raise ContractViolation(f"{source_id}: tazelik iddiası — hiç gözlem yok")
    newest = max(entry.observed_at for entry in observations)
    if now - newest > max_age:
        raise ContractViolation(
            f"{source_id}: tazelik iddiası — en yeni gözlem {newest.isoformat()}, "
            f"sınır {max_age}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collector.py -v`
Expected: 9 PASS

- [ ] **Step 5: Write the migration**

`db/migrations/0002_sources.sql`:

```sql
-- Faz 1 şeması: kaynak gözlemleri, maç sonuçları, varlık takma adları.
--
-- HASH ZİNCİRİ YOKTUR ve bu bilinçlidir. Zincir, ürünün "bu kayıt kurcalanmadı" iddiasını
-- taşıyan ORAN defteri içindir. Kaynak gözlemleri özellik girdisidir: append-only ve
-- observed_at damgalı olmaları yeniden üretilebilirlik için yeter. Bu ödünleşme faz
-- handoff'unda "kapının ölçmediği" olarak yazılır — sessizce varsayılmaz.

create table if not exists source_observations (
  id            bigserial primary key,
  source_id     text not null,
  entity_kind   text not null,
  entity_key    text not null,
  observed_at   timestamptz not null,
  payload       jsonb not null,
  content_hash  text not null,
  unique (source_id, entity_kind, entity_key, content_hash)
);

create index if not exists obs_lookup_idx
  on source_observations (source_id, entity_kind, entity_key, observed_at desc);
create index if not exists obs_observed_idx on source_observations (observed_at);

-- Sonuçlar da bir GÖZLEMDİR: skor düzeltilebilir ve düzeltmenin kendisi kayıtta kalmalı.
-- (match_id, observed_at) anahtarı düzeltme geçmişini taşır; okuyan en yenisini alır.
create table if not exists match_results (
  match_id      text not null references matches(id),
  observed_at   timestamptz not null,
  home_score    int not null check (home_score >= 0),
  away_score    int not null check (away_score >= 0),
  completed     boolean not null,
  primary key (match_id, observed_at)
);

create index if not exists results_completed_idx on match_results (completed) where completed;

-- Varlık eşleme sözlüğü. `confidence` SAKLANIR: eşiği sonradan yükseltmek, eşleşmeleri
-- yeniden çıkarmayı gerektirmesin (spec §5.2, "ham cevaplar saklandığı sürece").
create table if not exists entity_aliases (
  source_id     text not null,
  entity_kind   text not null,
  alias         text not null,
  canonical_id  text not null,
  confidence    numeric not null check (confidence >= 0 and confidence <= 1),
  decided_at    timestamptz not null,
  primary key (source_id, entity_kind, alias)
);

-- Append-only zorlaması. forbid_ledger_mutation() 0001'de tanımlandı; yeniden yazılmaz.
drop trigger if exists source_observations_append_only on source_observations;
create trigger source_observations_append_only
  before update or delete on source_observations
  for each row execute function forbid_ledger_mutation();

drop trigger if exists match_results_append_only on match_results;
create trigger match_results_append_only
  before update or delete on match_results
  for each row execute function forbid_ledger_mutation();
```

**Migrasyonu CONTROLLER uygular, subagent değil** (Faz 0 Ruling 10). Uygulama:

```bash
DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d= -f2-)" \
  uv run python -c "
from pathlib import Path
from football_edge.db import connect
with connect() as conn:
    conn.execute(Path('db/migrations/0002_sources.sql').read_text(encoding='utf-8'))
    conn.commit()
print('0002 uygulandı')
"
```

- [ ] **Step 6: Write the observation store**

`tests/test_observations.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from football_edge.collector import Observation
from football_edge.observations import write_observations
from tests.fake_obs_db import FakeObservationDb

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def obs(key: str, xg: float) -> Observation:
    return Observation("footystats", "team", key, NOW, {"xg": xg})


def test_writes_every_new_observation() -> None:
    db = FakeObservationDb()
    assert write_observations(db, (obs("gs", 1.5), obs("fb", 1.2))) == 2


def test_identical_content_is_not_written_twice() -> None:
    """Aynı tablo her turda yeniden gözlenir; depo idempotent olmalı, yoksa sınırsız büyür."""
    db = FakeObservationDb()
    write_observations(db, (obs("gs", 1.5),))
    assert write_observations(db, (obs("gs", 1.5),)) == 0
    assert write_observations(db, (obs("gs", 1.6),)) == 1


def test_writes_use_a_single_statement() -> None:
    db = FakeObservationDb()
    write_observations(db, tuple(obs(f"t{i}", 1.0 + i / 10) for i in range(40)))
    inserts = [s for s in db.statements if s.startswith("INSERT INTO source_observations")]
    assert len(inserts) == 1
```

`tests/fake_obs_db.py`:

```python
"""`source_observations` için bellek içi taklit; UNIQUE kısıtını GERÇEKTEN uygular."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OBS_COLUMNS = ("source_id", "entity_kind", "entity_key", "observed_at", "payload", "content_hash")


@dataclass
class FakeObservationDb:
    rows: list[dict[str, Any]] = field(default_factory=list)
    statements: list[str] = field(default_factory=list)

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        return None

    def __enter__(self) -> FakeObservationDb:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _Cursor:
    def __init__(self, db: FakeObservationDb) -> None:
        self._db = db
        self.rowcount = -1
        self._result: list[tuple[Any, ...]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        text = " ".join(sql.split())
        self._db.statements = [*self._db.statements, text]
        self.rowcount, self._result = 0, []
        if not text.startswith("INSERT INTO source_observations"):
            raise AssertionError(f"taklit bu sorguyu tanımıyor: {text}")
        keys = {(row["source_id"], row["entity_kind"], row["entity_key"], row["content_hash"])
                for row in self._db.rows}
        for index in range(len(params["content_hash"])):
            row = {name: params[name][index] for name in OBS_COLUMNS}
            key = (row["source_id"], row["entity_kind"], row["entity_key"], row["content_hash"])
            if key in keys:
                continue
            keys = keys | {key}
            self._db.rows = [*self._db.rows, row]
            self._result.append((row["entity_key"],))
        self.rowcount = len(self._result)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._result)
```

`src/football_edge/observations.py`:

```python
from __future__ import annotations

import json
from typing import Any

import psycopg

from football_edge.collector import Observation
from football_edge.ledger import canonical_timestamp

_OBS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_id", "text"),
    ("entity_kind", "text"),
    ("entity_key", "text"),
    ("observed_at", "timestamptz"),
    ("payload", "jsonb"),
    ("content_hash", "text"),
)

_OBS_NAMES = ", ".join(name for name, _ in _OBS_COLUMNS)
_OBS_ARRAYS = ", ".join(f"%({name})s::{kind}[]" for name, kind in _OBS_COLUMNS)

# Task 1'deki oran yazımıyla AYNI desen: tek ifade, kolon dizileri, RETURNING.
# `ON CONFLICT DO NOTHING` idempotentliği verir — aynı xG tablosu her turda yeniden
# gözlenir ve ikinci kez yazılmaz.
INSERT_OBSERVATIONS = f"""
    INSERT INTO source_observations ({_OBS_NAMES})
    SELECT {_OBS_NAMES}
    FROM unnest({_OBS_ARRAYS}) AS t({_OBS_NAMES})
    ON CONFLICT (source_id, entity_kind, entity_key, content_hash) DO NOTHING
    RETURNING entity_key
"""


def write_observations(
    conn: psycopg.Connection[Any], observations: tuple[Observation, ...]
) -> int:
    """YENİ yazılan gözlem sayısını döner (yinelenenler sayılmaz)."""
    if not observations:
        return 0
    columns: dict[str, list[Any]] = {
        "source_id": [entry.source_id for entry in observations],
        "entity_kind": [entry.entity_kind for entry in observations],
        "entity_key": [entry.entity_key for entry in observations],
        "observed_at": [canonical_timestamp(entry.observed_at) for entry in observations],
        "payload": [json.dumps(entry.payload, sort_keys=True, ensure_ascii=False)
                    for entry in observations],
        "content_hash": [entry.content_hash for entry in observations],
    }
    with conn.cursor() as cur:
        cur.execute(INSERT_OBSERVATIONS, columns)
        return len(cur.fetchall())
```

- [ ] **Step 7: Add the data-contract gate step**

`verify.sh`'e, `step "kaynak-politikası"` satırının **altına** ekle:

```bash
# Veri sözleşmesi: toplayıcıların KAYDEDİLMİŞ fixture'ları üzerinde tazelik/şema iddiaları.
# Ağa çıkmaz — fixture'lar repoda. Canlı tazeliği snapshot turu ölçer; burada ölçülen,
# AYRIŞTIRICININ hâlâ beklenen şekli ürettiğidir.
step "veri-sözleşmesi" uv run pytest tests/ -q -m contract
```

`pyproject.toml`'da `[tool.pytest.ini_options]` altına ekle:

```toml
markers = ["contract: kaydedilmiş fixture üzerinde tazelik/şema sözleşmesi"]
```

Ve bağımlılıkları güncelle:

```toml
dependencies = [
    "httpx>=0.27",
    "psycopg[binary]>=3.2",
    "pyyaml>=6.0",
    "beautifulsoup4>=4.12",
    "defusedxml>=0.7",
    "typesafe-sdk>=0.1",
]

[dependency-groups]
dev = [
    "pytest>=8.0", "ruff>=0.6", "mypy>=1.11",
    "types-PyYAML", "types-beautifulsoup4", "types-defusedxml",
]
```

**`defusedxml` neden bağımlılık:** Task 8 DIŞ kaynaklardan gelen XML ayrıştırıyor (RSS,
sitemap). Stdlib `xml.etree.ElementTree` "billion laughs" ve quadratic-blowup varlık
genişlemesine **açıktır** (defusedxml'in kendi uyumluluk tablosu). Beslediğimiz XML'i biz
yazmıyoruz — ayrıştırıcı sertleştirilmiş olanı olmalı. Girdi doğrulaması, ayrıştırıcı
seçiminde başlar.

Run: `uv lock && uv sync`
Expected: `uv.lock` güncellenir; repoya girer, `.gitignore`'a EKLENMEZ.

- [ ] **Step 8: Run the gate and commit**

```bash
./verify.sh
git add src/football_edge/naming.py src/football_edge/collector.py src/football_edge/observations.py db/migrations/0002_sources.sql tests/test_collector.py tests/test_observations.py tests/fake_sources.py tests/fake_obs_db.py verify.sh pyproject.toml uv.lock
git commit -m "feat: toplayıcı çatısı, gözlem deposu ve veri sözleşmesi adımı

izin -> fetch -> doğrula -> yaz. İzin kontrolü fetch'in İLK işi: disallow edilen
yolda HTTP isteği hiç atılmaz. content-type zorunlu (200 doğruluk değildir), encoding
açıkça verilebilir (TFF windows-1254 yalnız başlıkta).

Tazelik ve şema iddiaları ContractViolation fırlatır: kırılan ayrıştırıcının ürettiği
boş liste, iddiasız bir turda başarıdan ayırt edilemiyordu.

source_observations append-only ama hash zincirsiz — bilinçli, handoff'a yazılacak.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---
### Task 5: FootyStats toplayıcı — çatının REFERANS uygulaması

Bu task iki iş yapar: xG kapsamını sağlar (Understat'ın devri, Ruling A) **ve** Task 4'ün
çatısını gerçek bir kaynağa karşı kanıtlar. Faz 0'ın `tests/fake_db.py` docstring'inde yazılı
ders: *kısıt uygulamayan bir taklit, temiz veritabanında patlayan kodu yeşil gösterir.* Çatıyı
yalnız test ikizine karşı doğrulayıp beş ajanı izole worktree'ye salmak, çatı hatalıysa **beş
worktree'yi birden** yanlış yapar. Bu yüzden Task 5 paralel kümenin İÇİNDE değil, ÖNÜNDEDİR.

**Ölçüldü (2026-09-19):** `/turkey/super-lig/xg` → 200, 388 KB, sunucu-render.
`<table class='full-league-table table-sort xg-all mobify-table'>`; `thead` sütunları
`# · (arma) · Team · MP · xG · xGA · xGD · GF · GA · xG vs Actual`; takım hücresi
`<a href='/clubs/galatasaray-187'>Galatasaray…` — **kararlı sayısal takım kimliği**, varlık
eşleme için bedava çıpa.

**Files:**
- Create: `src/football_edge/collectors/__init__.py`, `src/football_edge/collectors/footystats.py`,
  `tests/test_footystats.py`, `tests/fixtures/footystats/turkey-super-lig-xg.html`
- Modify: `config/sources.yaml` (6 lig yolu), `config/leagues.yaml`, `src/football_edge/leagues.py`,
  `src/football_edge/collect.py`, **`tests/test_leagues.py`** (Faz 0'ın fixture'ları yeni
  zorunlu alanı taşımıyor ve `_validate` bilinmeyen/eksik alanda patlıyor — güncellenmezse kırılır)

**Interfaces:**
- Consumes: `collector.{Observation, ContractViolation, fetch_text, assert_schema, assert_fresh}`,
  `sources.{load_sources, robots_for}`, `observations.write_observations`
- Produces:
  - `parse_xg_table(html_text: str, *, league_id: str, observed_at: datetime) -> tuple[Observation, ...]`
    — `entity_kind="team"`, `entity_key=f"{league_id}:{footystats_id}"`,
    payload: `{"team_name": str, "footystats_id": int, "matches_played": int, "xg": float, "xga": float}`
  - `collect_footystats(conn, client, leagues, sources_path, robots_dir, now) -> int`
  - CLI: `python -m football_edge.collect fetch-footystats`
  - `League` alanı **eklenir**: `footystats_path: str`

- [ ] **Step 1: Capture the fixture**

Ayrıştırıcı **kaydedilmiş** bir sayfaya karşı test edilir; testler ağa çıkmaz. Tam sayfa 388 KB —
yalnız ilgili tabloyu sakla:

```bash
mkdir -p tests/fixtures/footystats
curl -sS -m 30 -A 'football-edge/0.1 (+https://github.com/popiliadam/football-edge)' \
  https://footystats.org/turkey/super-lig/xg -o /tmp/fs-xg.html
uv run python - <<'PY'
from pathlib import Path
from bs4 import BeautifulSoup
soup = BeautifulSoup(Path("/tmp/fs-xg.html").read_text(encoding="utf-8"), "html.parser")
table = soup.find("table", class_="xg-all")
assert table is not None, "'xg-all' tablosu yok — sayfa şekli değişmiş, ayrıştırıcıyı yazmadan bak"
Path("tests/fixtures/footystats/turkey-super-lig-xg.html").write_text(str(table), encoding="utf-8")
print("fixture bayt:", len(str(table)))
PY
```

Expected: `fixture bayt:` ~30 000–80 000. Assert patlarsa **dur**: ölçüm bayatlamış demektir,
ayrıştırıcıyı hayale göre yazma.

- [ ] **Step 2: Write the failing test**

`tests/test_footystats.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.footystats import parse_xg_table

FIXTURE = Path("tests/fixtures/footystats/turkey-super-lig-xg.html")
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.mark.contract
def test_parses_every_team_in_the_league() -> None:
    parsed = parse_xg_table(fixture_html(), league_id="tur.1", observed_at=NOW)
    assert len(parsed) >= 18, f"Süper Lig 18+ takım; {len(parsed)} ayrıştırıldı"


@pytest.mark.contract
def test_payload_carries_the_required_fields_in_plausible_ranges() -> None:
    parsed = parse_xg_table(fixture_html(), league_id="tur.1", observed_at=NOW)
    for entry in parsed:
        assert entry.payload["team_name"]
        assert entry.payload["footystats_id"] > 0
        assert entry.payload["matches_played"] >= 0
        # Sezon toplamı xG: 0 ile 4 gol/maç arası makul. Aralık iddiası, ayrıştırıcının
        # yanlış SÜTUNU okuduğunu yakalar — eksik sütunu değil.
        assert 0.0 <= entry.payload["xg"] <= entry.payload["matches_played"] * 4 + 4
        assert 0.0 <= entry.payload["xga"] <= entry.payload["matches_played"] * 4 + 4


@pytest.mark.contract
def test_entity_key_is_league_scoped_and_stable() -> None:
    parsed = parse_xg_table(fixture_html(), league_id="tur.1", observed_at=NOW)
    keys = tuple(entry.entity_key for entry in parsed)
    assert len(set(keys)) == len(keys), "yinelenen entity_key — join sessizce çoğaltır"
    assert all(key.startswith("tur.1:") for key in keys)


def test_missing_table_raises_rather_than_returning_empty() -> None:
    """Kırılan ayrıştırıcı BOŞ LİSTE döndürmemeli: boş liste sessizce başarı gibi görünür."""
    with pytest.raises(ContractViolation, match="xg-all"):
        parse_xg_table("<html><body>hiçbir şey</body></html>", league_id="tur.1", observed_at=NOW)


def test_renamed_column_raises() -> None:
    """Sütun adı değişirse indeksle okumak YANLIŞ SAYIYI sessizce alır. Ad kontrol edilir."""
    broken = "<table class='xg-all'><thead><tr><th>#</th><th>Team</th><th>MP</th>" \
             "<th>ExpG</th><th>ExpGA</th></tr></thead><tbody></tbody></table>"
    with pytest.raises(ContractViolation, match="xG"):
        parse_xg_table(broken, league_id="tur.1", observed_at=NOW)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_footystats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.collectors'`

- [ ] **Step 4: Write the parser**

`src/football_edge/collectors/__init__.py`: (boş dosya)

`src/football_edge/collectors/footystats.py`:

```python
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from football_edge.collector import ContractViolation, Observation

SOURCE_ID = "footystats"

# `<a href='/clubs/galatasaray-187'>` — sondaki sayı kararlı FootyStats takım kimliğidir.
# Ada göre eşleşmeye göre çok daha sağlam: ad değişir, kimlik değişmez.
_CLUB_HREF = re.compile(r"/clubs/[a-z0-9-]+-(?P<club_id>\d+)/?$")

_REQUIRED_COLUMNS = ("Team", "MP", "xG", "xGA")


def _text(node: Any) -> str:
    """Bir düğümün görünür metnini tek yoldan alır (bs4 tipleri tek yerde daraltılır)."""
    return "" if node is None else str(node.get_text(" ", strip=True))


def _first_string(node: Tag) -> str:
    """`<a>Galatasaray<div class='hover-modal'>…</div></a>` — yalnız İLK metin düğümü.

    `get_text()` gömülü hover-modal'ın tamamını da getirir ve takım adı bir paragrafa
    dönüşür; o ad hiçbir eşleşmeye uymaz ve join SESSİZCE boş kalır.
    """
    for child in node.children:
        if isinstance(child, str) and child.strip():
            return child.strip()
    return _text(node)


def _number(cell: Tag, column: str, team: str) -> float:
    raw = _text(cell).replace(",", "")
    try:
        return float(raw)
    except ValueError as error:
        raise ContractViolation(
            f"{SOURCE_ID}: '{column}' sayı değil ({team}): {raw!r}"
        ) from error


def _columns(table: Tag) -> dict[str, int]:
    headers = tuple(_text(cell) for cell in table.select("thead th"))
    index = {name: position for position, name in enumerate(headers) if name}
    missing = tuple(name for name in _REQUIRED_COLUMNS if name not in index)
    if missing:
        raise ContractViolation(
            f"{SOURCE_ID}: beklenen sütun(lar) yok {missing} — bulunanlar: {headers}"
        )
    return index


def parse_xg_table(
    html_text: str, *, league_id: str, observed_at: datetime
) -> tuple[Observation, ...]:
    """FootyStats lig xG tablosunu gözlemlere çevirir.

    Sütunlar İSİMLE bulunur, konumla değil: FootyStats sütun ekleyince konumla okuyan bir
    ayrıştırıcı komşu sütunu okur ve HATA VERMEZ — xG yerine xGD yazar. Sessiz yanlış veri,
    eksik veriden kötüdür; model onu doğru sanıp fit eder.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", class_="xg-all")
    if not isinstance(table, Tag):
        raise ContractViolation(f"{SOURCE_ID}: 'xg-all' tablosu bulunamadı — sayfa şekli değişti")
    index = _columns(table)
    parsed: tuple[Observation, ...] = ()
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) <= max(index.values()):
            continue  # ara başlık / reklam satırı
        team_cell = cells[index["Team"]]
        link = team_cell.find("a", href=_CLUB_HREF)
        if not isinstance(link, Tag):
            continue
        found = _CLUB_HREF.search(str(link.get("href", "")))
        if found is None:
            continue
        name = _first_string(link)
        club_id = int(found.group("club_id"))
        parsed = (
            *parsed,
            Observation(
                source_id=SOURCE_ID,
                entity_kind="team",
                entity_key=f"{league_id}:{club_id}",
                observed_at=observed_at,
                payload={
                    "team_name": name,
                    "footystats_id": club_id,
                    "matches_played": int(_number(cells[index["MP"]], "MP", name)),
                    "xg": _number(cells[index["xG"]], "xG", name),
                    "xga": _number(cells[index["xGA"]], "xGA", name),
                },
            ),
        )
    return parsed
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_footystats.py -v`
Expected: 5 PASS. `test_parses_every_team_in_the_league` düşerse fixture'a bak — ayrıştırıcı
değil, **beklenti** yanlış olabilir (lig 18 değil 19 takımlı olabilir).

- [ ] **Step 6: Wire the league config and the collector entry point**

`src/football_edge/leagues.py` içinde `League`'e alan ekle ve `REQUIRED_FIELDS`'e yaz:

```python
@dataclass(frozen=True)
class League:
    id: str
    odds_api_key: str
    name: str
    country: str
    lang: str
    gl: str
    active: bool
    footystats_path: str


REQUIRED_FIELDS = frozenset(
    {"id", "odds_api_key", "name", "country", "lang", "gl", "active", "footystats_path"}
)
```

Aynı dosyada, `load_leagues` içindeki `raw["leagues"]` satırını değiştir — çıplak `KeyError`
operatöre ne olduğunu söylemiyordu (DEFERRED §6/T2):

```python
    if not isinstance(raw, dict) or "leagues" not in raw:
        raise ValueError(f"{path}: kökte 'leagues' anahtarı yok")
    entries = raw["leagues"]
```

`config/leagues.yaml`'daki **altı ligin her birine** satır ekle:

```yaml
    footystats_path: /england/premier-league/xg      # eng.1
    footystats_path: /spain/la-liga/xg               # esp.1
    footystats_path: /italy/serie-a/xg               # ita.1
    footystats_path: /germany/bundesliga/xg          # ger.1
    footystats_path: /france/ligue-1/xg              # fra.1
    footystats_path: /turkey/super-lig/xg            # tur.1
```

**Her yolu doğrula** — uydurma slug kapıyı değil, turu sessizce boşaltır:

```bash
for p in /england/premier-league/xg /spain/la-liga/xg /italy/serie-a/xg \
         /germany/bundesliga/xg /france/ligue-1/xg /turkey/super-lig/xg; do
  printf '%-32s ' "$p"
  curl -sS -m 25 -o /dev/null -w 'HTTP %{http_code}\n' \
    -A 'football-edge/0.1 (+https://github.com/popiliadam/football-edge)' "https://footystats.org$p"
  sleep 1   # Crawl-delay: 1
done
```

Expected: altısı da `HTTP 200`. 404 dönen varsa doğru slug'ı FootyStats'ın lig menüsünden bul.

`config/sources.yaml`'da `footystats` kaydının `declared_paths` listesini **altı yolun hepsiyle**
değiştir. Kapı bunları robots'a karşı soracak.

`src/football_edge/collectors/footystats.py`'ye ekle:

```python
def collect_footystats(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    leagues: tuple[League, ...],
    *,
    sources_path: Path,
    robots_dir: Path,
    now: datetime,
) -> int:
    """Etkin liglerin xG tablolarını toplar; YAZILAN yeni gözlem sayısını döner.

    Lig başına arıza izolasyonu Faz 0'daki `_collect` ile aynı gerekçeyle: tek ligin
    kırılması diğerlerini düşürmemeli.
    """
    source = next(entry for entry in load_sources(sources_path) if entry.id == SOURCE_ID)
    parser = robots_for(source, robots_dir)
    written = 0
    for league in leagues:
        try:
            body = fetch_text(
                client, source, league.footystats_path, parser, expect="text/html"
            )
            parsed = parse_xg_table(body, league_id=league.id, observed_at=now)
            assert_schema(
                parsed,
                source_id=SOURCE_ID,
                required=frozenset({"team_name", "footystats_id", "xg", "xga"}),
                minimum_rows=10,
            )
            written += write_observations(conn, parsed)
            conn.commit()
        except Exception:
            conn.rollback()
            LOGGER.exception("lig=%s footystats toplanamadı, diğerlerine devam", league.id)
    return written
```

Gerekli import'ları dosyanın üstüne ekle (`logging`, `Path`, `httpx`, `psycopg`,
`fetch_text`, `assert_schema`, `load_sources`, `robots_for`, `write_observations`,
`League`) ve `LOGGER = logging.getLogger("football_edge.collectors.footystats")` tanımla.

`collect.py`'de `choices` demetine `"fetch-footystats"` ekle ve dalı yaz:

```python
        if args.command == "fetch-footystats":
            with httpx.Client() as client:
                written = collect_footystats(
                    conn,
                    client,
                    active_leagues(load_leagues(LEAGUES_PATH)),
                    sources_path=SOURCES_PATH,
                    robots_dir=ROBOTS_DIR,
                    now=now,
                )
            sys.stdout.write(f"footystats: {written} yeni gözlem\n")
            return 0
```

- [ ] **Step 7: Run the gate, then one live round**

```bash
./verify.sh
DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d= -f2-)" \
  uv run python -m football_edge.collect fetch-footystats
```

Expected: `footystats: N yeni gözlem`, N ≥ 100 (6 lig × ~20 takım). **İkinci kez koş:**
`footystats: 0 yeni gözlem` beklenir — `content_hash` idempotentliği burada kanıtlanır.
Sıfır değilse `content_hash`'e `observed_at` sızmıştır.

- [ ] **Step 8: Commit**

```bash
git add src/football_edge/collectors tests/test_footystats.py tests/fixtures/footystats config/sources.yaml config/leagues.yaml src/football_edge/leagues.py tests/test_leagues.py src/football_edge/collect.py
git commit -m "feat: FootyStats xG toplayıcı — çatının referans uygulaması

Understat robots.txt ile kapalı (Disallow: /); xG kapsamını FootyStats devraldı
ve altı ligin hepsini veriyor. Sütunlar İSİMLE bulunuyor: konumla okuyan bir
ayrıştırıcı, sütun eklenince komşu sütunu sessizce okur.

Takım kimliği /clubs/<slug>-<id> href'inden alınıyor — ada göre eşleşmeden çok
daha sağlam ve Task 11'in varlık eşlemesine bedava çıpa.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## PARALEL KÜME — Task 6-10

**BURADAN İTİBAREN Task 1-5 birleşmiş olmalı.** Beş task izole worktree'de eşzamanlı koşar.
Her ajan **yalnız kendi tablosundaki dosyalara yazar**; `config/*`, `collector.py`, `sources.py`,
`db/migrations/*`, `verify.sh` **salt okunur**. Worktree kurulumu:
`superpowers:using-git-worktrees`. Birleştirme `--no-ff`.

---

### Task 6: TFF toplayıcı — hakem ataması ve PFDK (windows-1254)

> **GERİ ALINDI (2026-09-19, Task 6 uygulaması + inceleme).** Bu bölüm aşağıda bir zamanlar
> spec'i "düzeltiyordu": hakem atamasını `pageID=600`'den `pageID=433`'e taşıyordu. **O düzeltme
> YANLIŞTI ve spec BAŞTAN BERİ DOĞRUYDU.** Ölçüm iki kez, birbirinden bağımsız biçimde yeniden
> üretildi: `pageID=433`'ün varsayılan GET'i **BOŞ** — gönderilmemiş, üç katmanlı bir arama formu
> döner ve engellenmiş bir POST olmadan asla hakem satırı vermez. `pageID=600` ise veriyi
> taşıyor: **7 lig bloğu / 63 maç satırı, `<table>` değil `<div>` bloklarında** (420 KB'lık
> sayfada yalnız 3 `<table>` var — `find_all("table")` hiçbir şey bulmuyor).
>
> **Yanlış sonucun sebebi yöntemdeydi, veride değil:** `pageID=600`'de "Hakem" 181 kez geçiyordu;
> bir bağlam regex'i (`.{130}Hakem.{170}`) yalnız 1 eşleşme verdi, çünkü `finditer` ÖRTÜŞEN
> eşleşmeleri yutar — 300 karakterlik pencere içindeki ardışık geçişler tek eşleşmeye düştü.
> Üstüne veri `<table>` sanılarak arandı. **Ders:** doğrulanmamış bir ölçüm yönteminden çıkan
> sonucu kural hâline getirmek, hiç ölçmemekten daha tehlikelidir — sonuç "ölçüldü" etiketiyle
> dolaşır ve doğru olan kaydı devirir.
>
> Kodda geçerli olan `src/football_edge/collectors/tff.py` → `REFEREE_PATH =
> "/Default.aspx?pageID=600"` ve `config/sources.yaml` → `tff.declared_paths`. Aşağıdaki
> Step 1/Step 4 blokları TARİHSEL plan metnidir; `433` geçen her satır **yanlıştır**, düzeltilmiş
> hâli için koda ve `docs/phases/01-toplayicilar/HANDOFF.md` §4'e bakın.

**İki sınır, baştan yazılı:**
1. `__VIEWSTATE` + RadComboBox ⇒ **yalnız varsayılan (bu hafta) görünüm GET ile adreslenebilir.**
   Başka hafta/lig postback ister; postback POST'tur ve `outward_action_gate` onu `net_post`
   olarak engeller. Toplayıcı haftalık koşar ve bu haftayı alır — ihtiyaç duyduğu tam budur.
2. ~~Sayfada **`VAR` dizesi hiç geçmiyor** (ölçüldü).~~ **BU DA YANLIŞTI.** VAR/AVAR atamaları
   sayfada VAR — ama düz "VAR" kelimesiyle değil, **rol işaretiyle: `(V)` ve `(A)`** (ölçüldü:
   tek turda V=11, A=11). "VAR dizesini ara" ölçümü bu yüzden yanıltıcıydı. Toplanmıyor —
   sözleşme tek bir `referee` alanı istiyor — ama **var olmadığı için değil, kapsam dışı
   bırakıldığı için.** DEFERRED §9.7.

**Files:**
- Create: `src/football_edge/collectors/tff.py`, `tests/test_tff.py`, `tests/fixtures/tff/`
- **Salt okunur:** `config/sources.yaml` (`tff` kaydı ve `declared_paths` hazır),
  `src/football_edge/collect.py` (Ruling R1 — CLI dalı EKLEME)

**Interfaces:**
- Consumes: `collector.{Observation, ContractViolation, fetch_text, assert_schema}`,
  `sources.{load_sources, robots_for}`, `observations.write_observations`
- Produces:
  - `parse_referees(html_text: str, *, observed_at: datetime) -> tuple[Observation, ...]`
    — `entity_kind="fixture_official"`, `entity_key=f"{home}|{away}"` (normalize edilmiş),
    payload: `{"home_team": str, "away_team": str, "referee": str, "league": str}`
  - `collect_tff(conn, client, *, sources_path, robots_dir, now) -> int`
  - CLI: **bu task'ta YOK** (Ruling R1) — `fetch-tff` dalı birleştirme adımında eklenir.

- [ ] **Step 1: Capture the fixture with the correct encoding**

> **DÜZELTİLDİ:** aşağıdaki blok bir zamanlar `pageID=433` çekiyordu; o sayfa boş form döner.
> Gerçekte çekilen ve teslim edilen fixture `haftanin-maclari-600.html`'dir. `hakem-433.html`
> de repoda durur ama **negatif bulgu olarak sabitlenmiştir** (R37): ayrıştırıcının o sayfaya
> karşı satır UYDURMADIĞINI, `ContractViolation` fırlattığını kanıtlayan bir test taşır.

```bash
mkdir -p tests/fixtures/tff
curl -sS -m 30 -A 'football-edge/0.1' \
  'https://www.tff.org/Default.aspx?pageID=600' -o /tmp/tff600.html
uv run python - <<'PY'
from pathlib import Path
raw = Path("/tmp/tff600.html").read_bytes()
text = raw.decode("windows-1254")          # charset YALNIZ HTTP başlığında; meta yok
assert "Hakem" in text, "sayfa şekli değişti — ayrıştırıcıyı yazmadan bak"
# Fixture UTF-8 saklanır: repo tek kodlama taşır, kod yolu ise windows-1254'ü fetch'te çözer.
Path("tests/fixtures/tff/haftanin-maclari-600.html").write_text(text, encoding="utf-8")
print("bayt:", len(text), "| 'Hakem':", text.count("Hakem"))
PY
```

- [ ] **Step 2: Inspect the fixture and name the real table**

Ayrıştırıcıyı yazmadan **bak** — bu adım atlanamaz, çünkü tablo şeklini kimse ezbere bilmiyor:

```bash
uv run python - <<'PY'
from pathlib import Path
from bs4 import BeautifulSoup
soup = BeautifulSoup(Path("tests/fixtures/tff/hakem-433.html").read_text(encoding="utf-8"), "html.parser")
for position, table in enumerate(soup.find_all("table")):
    rows = table.find_all("tr")
    head = [c.get_text(" ", strip=True) for c in rows[0].find_all(["td", "th"])] if rows else []
    print(f"[{position}] class={table.get('class')} satır={len(rows)} ilk={head[:8]}")
PY
```

Hakem sütunu taşıyan tablonun **indeksini ve `class`'ını** not al; Step 4'teki
`_REFEREE_TABLE_HINT` sabitini onunla doldur. Hiçbir tabloda hakem adı yoksa **dur ve bildir**:
sayfa yapısı değişmiştir ve bu, uydurulacak bir şey değildir.

- [ ] **Step 3: Write the failing test**

`tests/test_tff.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.tff import parse_referees
from football_edge.naming import normalise_team

FIXTURE = Path("tests/fixtures/tff/hakem-433.html")
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


@pytest.mark.contract
def test_parses_this_weeks_fixtures() -> None:
    parsed = parse_referees(FIXTURE.read_text(encoding="utf-8"), observed_at=NOW)
    assert len(parsed) >= 5, f"haftalık program en az 5 maç taşımalı; {len(parsed)} bulundu"


@pytest.mark.contract
def test_turkish_characters_survive() -> None:
    """windows-1254 yanlış çözülürse 'Ü' ve 'ı' bozulur ve HİÇBİR eşleşme tutmaz."""
    text = FIXTURE.read_text(encoding="utf-8")
    parsed = parse_referees(text, observed_at=NOW)
    joined = " ".join(
        f"{entry.payload['home_team']} {entry.payload['away_team']} {entry.payload['referee']}"
        for entry in parsed
    )
    assert "�" not in joined, "değiştirme karakteri var — kodlama yanlış çözüldü"
    assert any(letter in joined for letter in "çğıöşüÇĞİÖŞÜ"), "hiç Türkçe karakter yok"


@pytest.mark.contract
def test_every_row_has_a_referee() -> None:
    parsed = parse_referees(FIXTURE.read_text(encoding="utf-8"), observed_at=NOW)
    assert all(entry.payload["referee"].strip() for entry in parsed)


def test_empty_page_raises_rather_than_returning_empty() -> None:
    with pytest.raises(ContractViolation):
        parse_referees("<html><body></body></html>", observed_at=NOW)


def test_team_normalisation_is_case_and_space_insensitive() -> None:
    """Eşleşme anahtarı normalize edilir; 'Galatasaray A.Ş.' ile 'GALATASARAY' aynı olmalı."""
    assert normalise_team("  Galatasaray A.Ş. ") == normalise_team("GALATASARAY AŞ")
```

- [ ] **Step 4: Run test to verify it fails, then implement**

Run: `uv run pytest tests/test_tff.py -v` → `ModuleNotFoundError`

`src/football_edge/collectors/tff.py`:

```python
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg
from bs4 import BeautifulSoup, Tag

from football_edge.collector import ContractViolation, Observation, assert_schema, fetch_text
from football_edge.naming import normalise_team
from football_edge.observations import write_observations
from football_edge.sources import load_sources, robots_for

LOGGER = logging.getLogger("football_edge.collectors.tff")
SOURCE_ID = "tff"
REFEREE_PATH = "/Default.aspx?pageID=600"   # DÜZELTİLDİ: plan bir ara 433 diyordu, yanlıştı

# Step 2'de ÖLÇÜLEN tablo işareti. Boş bırakılırsa tüm tablolar taranır; ölçüldüyse
# doldurulur ve ayrıştırıcı yanlış tabloyu okumaz.
# NOT (uygulamada geçersiz kaldı): sayfada veri `<table>` DEĞİL `<div>` bloklarında —
# 420 KB içinde yalnız 3 `<table>` var. Teslim edilen ayrıştırıcı div gezinir.
_REFEREE_TABLE_HINT = ""

# TFF gövdesi windows-1254. Kodlama fetch tarafında AÇIKÇA verilir; httpx'in tahminine
# bırakılırsa Türkçe adlar sessizce bozulur ve varlık eşleme hiçbir şey bulamaz.
ENCODING = "windows-1254"


def _cells(row: Tag) -> tuple[str, ...]:
    return tuple(cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"]))


def parse_referees(html_text: str, *, observed_at: datetime) -> tuple[Observation, ...]:
    """Haftanın hakem atamalarını gözlemlere çevirir.

    Satır şekli TFF tarafından değiştirilebilir; bu yüzden sütun sayısı ve içerik
    DOĞRULANIR. Tanınmayan satır sessizce atlanır, ama HİÇ satır tanınmazsa
    ContractViolation fırlatılır: boş sonuç başarıdan ayırt edilemez.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    tables = (
        soup.find_all("table", class_=_REFEREE_TABLE_HINT)
        if _REFEREE_TABLE_HINT
        else soup.find_all("table")
    )
    parsed: tuple[Observation, ...] = ()
    for table in tables:
        for row in table.find_all("tr"):
            values = _cells(row)
            if len(values) < 4:
                continue
            home, away, referee = values[1].strip(), values[2].strip(), values[3].strip()
            if not (home and away and referee) or home.lower() in {"ev sahibi", "takım"}:
                continue
            parsed = (
                *parsed,
                Observation(
                    source_id=SOURCE_ID,
                    entity_kind="fixture_official",
                    entity_key=f"{normalise_team(home)}|{normalise_team(away)}",
                    observed_at=observed_at,
                    payload={
                        "home_team": home,
                        "away_team": away,
                        "referee": referee,
                        "league": values[0].strip(),
                    },
                ),
            )
    if not parsed:
        raise ContractViolation(f"{SOURCE_ID}: hiç hakem satırı tanınmadı — sayfa şekli değişti")
    return parsed


def collect_tff(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    *,
    sources_path: Path,
    robots_dir: Path,
    now: datetime,
) -> int:
    source = next(entry for entry in load_sources(sources_path) if entry.id == SOURCE_ID)
    parser = robots_for(source, robots_dir)
    body = fetch_text(
        client, source, REFEREE_PATH, parser, expect="text/html", encoding=ENCODING
    )
    parsed = parse_referees(body, observed_at=now)
    assert_schema(
        parsed,
        source_id=SOURCE_ID,
        required=frozenset({"home_team", "away_team", "referee"}),
        minimum_rows=5,
    )
    written = write_observations(conn, parsed)
    conn.commit()
    return written
```

**Step 2'de ölçtüğün sütun sırası `[lig, ev, deplasman, hakem]` DEĞİLSE**, `parse_referees`
içindeki indeksleri ölçtüğün sıraya göre düzelt ve `_REFEREE_TABLE_HINT`'i doldur. Testler
gerçek fixture'a karşı koşuyor; yanlış indeks orada kırmızı verir.

- [ ] **Step 5: Run tests, gate, live round, commit**

```bash
uv run pytest tests/test_tff.py -v && ./verify.sh
# CLI dalı henüz YOK (Ruling R1): toplayıcı doğrudan çağrılır.
DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d= -f2-)" uv run python -c "
from datetime import UTC, datetime
from pathlib import Path
import httpx
from football_edge.db import connect
from football_edge.collectors.tff import collect_tff
with connect() as conn, httpx.Client() as client:
    n = collect_tff(conn, client, sources_path=Path('config/sources.yaml'),
                    robots_dir=Path('config/robots'), now=datetime.now(UTC))
    print('tff yeni gozlem:', n)
"
git add src/football_edge/collectors/tff.py tests/test_tff.py tests/fixtures/tff
git commit -m "feat: TFF hakem ataması toplayıcı (windows-1254)

Spec pageID=600 diyordu ve DOĞRUYDU. Planın 'düzeltmesi' (433) yanlıştı: 433'ün
varsayılan GET'i gönderilmemiş bir arama formu döndürüyor. 600 veriyi taşıyor —
7 lig bloğu / 63 maç satırı, <table> değil <div> içinde.

charset yalnız HTTP başlığında; kodlama fetch'te açıkça veriliyor. Tahmine
bırakılırsa Türkçe adlar bozulur ve varlık eşleme hiçbir şey bulamaz.

Bilinen sınır: __VIEWSTATE postback'i gerektiği için yalnız BU HAFTA GET ile
alınabiliyor. VAR/AVAR atamaları sayfada VAR — (V)/(A) rol işaretiyle — ama
sözleşme tek `referee` alanı istediği için toplanmıyor.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Stadyum coğrafyası ve maç saati havası

Rakım gerçek bir gol etkisidir (yol haritası Task 8). **Ölçüldü:** Open-Meteo yanıtı
`elevation` alanını **doğrudan** veriyor (İstanbul için 77.0 m) — rakım için ayrı bir kaynağa
gerek yok, yalnız **koordinat** gerekiyor. Koordinat Wikidata'dan **REST ile** alınır:
`Special:EntityData/<QID>.json` düz bir GET'tir; SPARQL ucu yerel `outward_action_gate`
tarafından `net_post` olarak engelleniyor (ölçüldü) ve zaten gereksiz.

**Files:**
- Create: `src/football_edge/collectors/venues.py`, `src/football_edge/collectors/weather.py`,
  `tests/test_venues.py`, `tests/test_weather.py`, `tests/fixtures/venue/`
- **Salt okunur:** `config/sources.yaml` (`wikidata`, `openmeteo` kayıtları hazır)

**Interfaces:**
- Consumes: `collector.{Observation, ContractViolation, fetch_text, assert_schema}`
- Produces:
  - `parse_entity_coordinates(payload: dict[str, Any], qid: str) -> tuple[float, float]` — (lat, lon)
  - `parse_forecast(payload: dict[str, Any], kickoff: datetime) -> dict[str, float]` —
    `{"temperature_c", "precipitation_mm", "wind_kmh", "elevation_m"}`
  - `venue_observation(qid, lat, lon, *, observed_at) -> Observation` (`entity_kind="venue"`)
  - `weather_observation(match_id, values, *, observed_at) -> Observation` (`entity_kind="match_weather"`)

- [ ] **Step 1: Capture fixtures**

```bash
mkdir -p tests/fixtures/venue
# Q170980 = Türk Telekom Stadyumu (koordinat taşıyan bir stadyum QID'si)
curl -sS -m 25 -A 'football-edge/0.1' \
  'https://www.wikidata.org/wiki/Special:EntityData/Q170980.json' \
  -o tests/fixtures/venue/wikidata-Q170980.json
curl -sS -m 25 \
  'https://api.open-meteo.com/v1/forecast?latitude=41.04&longitude=28.99&hourly=temperature_2m,precipitation,wind_speed_10m&forecast_days=2' \
  -o tests/fixtures/venue/open-meteo.json
uv run python - <<'PY'
import json
from pathlib import Path
wd = json.loads(Path("tests/fixtures/venue/wikidata-Q170980.json").read_text(encoding="utf-8"))
claims = wd["entities"]["Q170980"]["claims"]
assert "P625" in claims, "P625 (koordinat) yok — başka bir stadyum QID'si seç"
om = json.loads(Path("tests/fixtures/venue/open-meteo.json").read_text(encoding="utf-8"))
assert "elevation" in om and "hourly" in om
print("koordinat:", claims["P625"][0]["mainsnak"]["datavalue"]["value"])
print("rakım:", om["elevation"])
PY
```

- [ ] **Step 2: Write the failing tests**

`tests/test_venues.py`:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.venues import parse_entity_coordinates, venue_observation

FIXTURE = Path("tests/fixtures/venue/wikidata-Q170980.json")
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


@pytest.mark.contract
def test_reads_coordinates_from_the_rest_payload() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    latitude, longitude = parse_entity_coordinates(payload, "Q170980")
    assert 35.0 < latitude < 43.0, "Türkiye enlem aralığı dışında"
    assert 25.0 < longitude < 45.0


def test_missing_coordinate_claim_raises() -> None:
    payload = {"entities": {"Q1": {"claims": {}}}}
    with pytest.raises(ContractViolation, match="P625"):
        parse_entity_coordinates(payload, "Q1")


def test_swapped_latitude_longitude_is_caught() -> None:
    """Wikidata `value` sözlüğünde lat/lon ADLIDIR; konuma göre okumak ikisini takas eder."""
    payload = {
        "entities": {
            "Q1": {
                "claims": {
                    "P625": [
                        {"mainsnak": {"datavalue": {"value": {"latitude": 41.1, "longitude": 29.0}}}}
                    ]
                }
            }
        }
    }
    assert parse_entity_coordinates(payload, "Q1") == (41.1, 29.0)


def test_observation_is_venue_kinded() -> None:
    entry = venue_observation("Q170980", 41.1, 29.0, observed_at=NOW)
    assert entry.entity_kind == "venue"
    assert entry.entity_key == "Q170980"
```

`tests/test_weather.py`:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.weather import parse_forecast

FIXTURE = Path("tests/fixtures/venue/open-meteo.json")


def payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.contract
def test_picks_the_hour_nearest_to_kickoff() -> None:
    body = payload()
    first_hour = str(body["hourly"]["time"][0])  # type: ignore[index]
    kickoff = datetime.fromisoformat(first_hour).replace(tzinfo=UTC)
    values = parse_forecast(body, kickoff)
    assert values["temperature_c"] == float(body["hourly"]["temperature_2m"][0])  # type: ignore[index]


@pytest.mark.contract
def test_elevation_comes_straight_from_the_response() -> None:
    """Rakım için ayrı kaynak yok: Open-Meteo zaten veriyor."""
    values = parse_forecast(payload(), datetime(2026, 9, 19, 0, 0, tzinfo=UTC))
    assert values["elevation_m"] == float(payload()["elevation"])  # type: ignore[index]


def test_kickoff_outside_the_forecast_window_raises() -> None:
    """Tahmin penceresi dışındaki saat için EN YAKIN saati vermek sessiz yanlış veridir."""
    with pytest.raises(ContractViolation, match="pencere"):
        parse_forecast(payload(), datetime(2030, 1, 1, 12, 0, tzinfo=UTC))
```

- [ ] **Step 3: Run tests to verify they fail, then implement**

`src/football_edge/collectors/venues.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from football_edge.collector import ContractViolation, Observation

SOURCE_ID = "wikidata"
ENTITY_PATH = "/wiki/Special:EntityData/{qid}.json"


def parse_entity_coordinates(payload: dict[str, Any], qid: str) -> tuple[float, float]:
    """P625 (koordinat konumu) talebinden (enlem, boylam).

    SPARQL DEĞİL REST: `Special:EntityData/<QID>.json` düz bir GET'tir. SPARQL ucu yerel
    `outward_action_gate` tarafından `net_post` olarak engelleniyor (ölçüldü 2026-09-19) ve
    tek bir varlık için zaten gereksiz.
    """
    claims = payload.get("entities", {}).get(qid, {}).get("claims", {})
    statements = claims.get("P625")
    if not statements:
        raise ContractViolation(f"{SOURCE_ID}: {qid} için P625 (koordinat) yok")
    value = statements[0]["mainsnak"]["datavalue"]["value"]
    # Alanlar ADLA okunur: konumla okumak enlem/boylamı takas eder ve hava tahmini
    # başka bir kıtadan gelir — hata vermeden.
    return float(value["latitude"]), float(value["longitude"])


def venue_observation(
    qid: str, latitude: float, longitude: float, *, observed_at: datetime
) -> Observation:
    return Observation(
        source_id=SOURCE_ID,
        entity_kind="venue",
        entity_key=qid,
        observed_at=observed_at,
        payload={"latitude": latitude, "longitude": longitude},
    )
```

`src/football_edge/collectors/weather.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from football_edge.collector import ContractViolation, Observation

SOURCE_ID = "openmeteo"
FORECAST_PATH = "/v1/forecast"
_MAX_GAP = timedelta(hours=1)


def parse_forecast(payload: dict[str, Any], kickoff: datetime) -> dict[str, float]:
    """Maç saatine EN YAKIN saatlik tahmini seçer; pencere dışındaysa patlar.

    Pencere dışı bir saat için "en yakın"ı vermek sessiz yanlış veridir: model onu maç
    saatinin havası sanar. Sızıntı değil ama aynı kadar zararlı — ölçülmemiş bir sayıyı
    ölçülmüş gibi kullanmak.
    """
    hourly = payload.get("hourly", {})
    stamps = hourly.get("time", [])
    if not stamps:
        raise ContractViolation(f"{SOURCE_ID}: saatlik tahmin yok")
    target = kickoff.replace(tzinfo=None)
    parsed = [datetime.fromisoformat(str(stamp)) for stamp in stamps]
    position = min(range(len(parsed)), key=lambda index: abs(parsed[index] - target))
    if abs(parsed[position] - target) > _MAX_GAP:
        raise ContractViolation(
            f"{SOURCE_ID}: maç saati {kickoff.isoformat()} tahmin penceresinin dışında"
        )
    return {
        "temperature_c": float(hourly["temperature_2m"][position]),
        "precipitation_mm": float(hourly["precipitation"][position]),
        "wind_kmh": float(hourly["wind_speed_10m"][position]),
        "elevation_m": float(payload["elevation"]),
    }


def weather_observation(
    match_id: str, values: dict[str, float], *, observed_at: datetime
) -> Observation:
    return Observation(
        source_id=SOURCE_ID,
        entity_kind="match_weather",
        entity_key=match_id,
        observed_at=observed_at,
        payload=dict(values),
    )
```

- [ ] **Step 4: Run tests, gate, commit**

```bash
uv run pytest tests/test_venues.py tests/test_weather.py -v && ./verify.sh
git add src/football_edge/collectors/venues.py src/football_edge/collectors/weather.py tests/test_venues.py tests/test_weather.py tests/fixtures/venue
git commit -m "feat: stadyum koordinatı (Wikidata REST) ve maç saati havası (Open-Meteo)

Rakım için ayrı kaynak gerekmedi: Open-Meteo yanıtı elevation'ı doğrudan veriyor.
Wikidata SPARQL yerine Special:EntityData REST — SPARQL yerel gate'te net_post
olarak engelleniyor ve tek varlık için gereksiz.

Koordinat alanları ADLA okunuyor; konumla okumak enlem/boylamı hata vermeden
takas eder ve hava başka kıtadan gelir.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---
### Task 8: Haber adaptör katmanı (Ajansspor birincil, Google News bayrakla KAPALI)

Ruling B: haber katmanı tek sağlayıcıya değil, bir **arayüze** yazılır. Google News feed'inin
kendi copyright metni ticari kullanımı açıkça yasaklıyor; adaptörü yazılır ama
`config/sources.yaml`'da `enabled: false` gelir ve lisans metni kodun yanında birebir durur.

**Ölçülen (2026-09-19) — Ajansspor robots.txt spec'in varsaydığından dar:**
`Content-Signal: ai-train=no, search=yes, **ai-input=yes**` (AI girdi kullanımı açıkça izinli,
eğitim değil) — ama `/lineup/*`, `/mac/*`, `/oyuncu/*`, `/lig/*` ve `*rsc=*` **Disallow**.
Spec §3.1 Ajansspor'dan "muhtemel 11 + sakat/cezalı" bekliyordu: **muhtemel 11 alınmaz.**
Yalnız haber yolları açıktır.

**`declared_paths` neden yalnız `/sitemap.xml`:** haber makalesi URL'leri dinamiktir,
listelenemez. Kapı **statik** beyanları sorar; çalışma anında `fetch_text`'in içindeki
`guard_path` **her makale URL'sini tek tek** sorar. İkisi birbirinin yerine geçmez.

**Files:**
- Create: `src/football_edge/collectors/news.py`, `tests/test_news.py`, `tests/fixtures/news/`
- **Salt okunur:** `config/sources.yaml`

**Interfaces:**
- Consumes: `collector.{Observation, ContractViolation, fetch_text}`, `sources.{load_sources, robots_for, SourceBlocked}`
- Produces:
  - `NewsItem` frozen dataclass: `title: str, url: str, published_at: datetime, source_id: str`
  - `NewsAdapter` Protocol: `source_id: str`; `parse(body: str, *, now: datetime) -> tuple[NewsItem, ...]`
  - `AjansporAdapter`, `GoogleNewsAdapter`
  - `news_observation(item: NewsItem) -> Observation` (`entity_kind="news"`, `entity_key=url`)
  - `enabled_adapters(sources) -> tuple[NewsAdapter, ...]`

- [ ] **Step 1: Capture fixtures**

```bash
mkdir -p tests/fixtures/news
curl -sS -m 30 -A 'football-edge/0.1' https://ajansspor.com/sitemap.xml \
  -o tests/fixtures/news/ajansspor-sitemap.xml
curl -sS -m 30 -A 'football-edge/0.1' \
  'https://news.google.com/rss/search?q=Galatasaray&hl=tr&gl=TR&ceid=TR:tr' \
  -o tests/fixtures/news/googlenews-tr.xml
head -c 400 tests/fixtures/news/ajansspor-sitemap.xml; echo
grep -c '<item>' tests/fixtures/news/googlenews-tr.xml
```

Expected: Google News fixture'ında ≥ 50 `<item>`. Ajansspor `sitemap.xml` bir **sitemap index**
döndürebilir (`<sitemapindex>`); o hâlde içindeki haber sitemap'ini de indir ve fixture'a ekle.

- [ ] **Step 2: Write the failing test**

`tests/test_news.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.news import (
    AjansporAdapter,
    GoogleNewsAdapter,
    enabled_adapters,
    news_observation,
)
from football_edge.sources import SourceBlocked, load_sources, robots_for
from football_edge.collector import fetch_text
from tests.fake_sources import fake_source, write_robots

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
GOOGLE_FIXTURE = Path("tests/fixtures/news/googlenews-tr.xml")


@pytest.mark.contract
def test_google_adapter_parses_the_feed() -> None:
    items = GoogleNewsAdapter().parse(GOOGLE_FIXTURE.read_text(encoding="utf-8"), now=NOW)
    assert len(items) >= 20
    assert all(item.title and item.url for item in items)


def test_google_news_is_disabled_in_the_registry() -> None:
    """Ruling B: feed'in kendi copyright'ı ticari kullanımı yasaklıyor. Varsayılan KAPALI."""
    registry = load_sources(Path("config/sources.yaml"))
    google = next(entry for entry in registry if entry.id == "googlenews")
    assert google.enabled is False
    assert "non-commercial" in google.note


def test_enabled_adapters_excludes_disabled_sources() -> None:
    registry = load_sources(Path("config/sources.yaml"))
    assert "googlenews" not in tuple(a.source_id for a in enabled_adapters(registry))


def test_article_url_is_checked_against_robots_at_fetch_time(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """`declared_paths` statik yolları kapıda sorar; DİNAMİK makale URL'si burada sorulur.

    Ajansspor `/mac/` ve `/lineup/` kapatıyor. Sitemap'ten böyle bir URL gelirse istek
    ATILMAMALI — robots'a uymak, listeyi kimin ürettiğine bağlı olamaz.
    """
    write_robots(tmp_path, "ajansspor", "User-agent: *\nDisallow: /mac/\nDisallow: /lineup/\n")
    source = fake_source(id="ajansspor")
    parser = robots_for(source, tmp_path)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text="<html/>", headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceBlocked):
            fetch_text(client, source, "/mac/12345", parser, expect="text/html")
        fetch_text(client, source, "/futbol/haber-1", parser, expect="text/html")

    assert calls == ["https://example.test/futbol/haber-1"]


def test_observation_key_is_the_article_url() -> None:
    items = GoogleNewsAdapter().parse(GOOGLE_FIXTURE.read_text(encoding="utf-8"), now=NOW)
    entry = news_observation(items[0])
    assert entry.entity_kind == "news"
    assert entry.entity_key == items[0].url
    # Ham içerik YENİDEN YAYINLANMAZ (spec §3.2/4): yalnız başlık ve bağlantı saklanır.
    assert set(entry.payload) == {"title", "url", "published_at", "source_id"}


def test_empty_feed_raises() -> None:
    with pytest.raises(ContractViolation):
        GoogleNewsAdapter().parse("<rss><channel></channel></rss>", now=NOW)


def test_entity_expansion_attack_is_refused_not_expanded() -> None:
    """Besleme gövdesini biz yazmıyoruz. Stdlib ElementTree bunu genişletmeye ÇALIŞIR.

    `defusedxml` varlık tanımını reddeder ve ContractViolation'a dönüşür; sertleştirilmemiş
    bir ayrıştırıcı burada belleği tüketir ve toplayıcı turu hiç bitmez.
    """
    bomb = (
        "<?xml version='1.0'?><!DOCTYPE rss ["
        "<!ENTITY a 'aaaaaaaaaa'>"
        "<!ENTITY b '&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;'>"
        "<!ENTITY c '&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;'>"
        "]><rss><channel><item><title>&c;</title><link>x</link></item></channel></rss>"
    )
    with pytest.raises(ContractViolation):
        GoogleNewsAdapter().parse(bomb, now=NOW)
```

- [ ] **Step 3: Run test to verify it fails, then implement**

`src/football_edge/collectors/news.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Protocol
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from football_edge.collector import ContractViolation, Observation
from football_edge.sources import Source, enabled_sources

# Google News RSS feed'inin KENDİ <copyright> metni (alıntı, 2026-09-19 ölçümü):
#   "This XML feed is made available solely for the purpose of rendering Google News results
#    within a personal feed reader for personal, non-commercial use. Any other use of the
#    feed is expressly prohibited."
# Spec §3.1 bu kaynağı "lisanslı yüzey" diye sınıflıyordu; feed aksini söylüyor. Adaptör
# yazıldı ama `config/sources.yaml`'da `enabled: false`. Ticari karar operatörde;
# `docs/DEFERRED.md` §7'de "ticari lansman öncesi avukat" maddesiyle duruyor.
GOOGLE_NEWS_LICENCE = "personal, non-commercial use only — see config/sources.yaml"


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    published_at: datetime
    source_id: str


class NewsAdapter(Protocol):
    source_id: str

    def parse(self, body: str, *, now: datetime) -> tuple[NewsItem, ...]: ...


def _rss_items(body: str, source_id: str, now: datetime) -> tuple[NewsItem, ...]:
    # `defusedxml`: besleme DIŞARIDAN geliyor ve stdlib ElementTree varlık genişlemesine
    # (billion laughs / quadratic blowup) açıktır. Bir haber beslemesi, gövdesini bizim
    # yazmadığımız her girdi gibi düşmanca kabul edilir.
    try:
        root = fromstring(body)
    except (ParseError, DefusedXmlException) as error:
        raise ContractViolation(
            f"{source_id}: RSS ayrıştırılamadı ({type(error).__name__})"
        ) from error
    items: tuple[NewsItem, ...] = ()
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not title or not link:
            continue
        raw_date = node.findtext("pubDate")
        published = now
        if raw_date:
            try:
                published = parsedate_to_datetime(raw_date)
            except (TypeError, ValueError):
                published = now
        items = (*items, NewsItem(title=title, url=link, published_at=published, source_id=source_id))
    if not items:
        raise ContractViolation(f"{source_id}: feed'de hiç item yok")
    return items


@dataclass(frozen=True)
class GoogleNewsAdapter:
    source_id: str = "googlenews"

    def parse(self, body: str, *, now: datetime) -> tuple[NewsItem, ...]:
        return _rss_items(body, self.source_id, now)


@dataclass(frozen=True)
class AjansporAdapter:
    """Yalnız robots'un izin verdiği haber yolları.

    `/lineup/`, `/mac/`, `/oyuncu/`, `/lig/` DISALLOW (ölçüldü 2026-09-19). Spec §3.1
    Ajansspor'dan "muhtemel 11" bekliyordu; o yol kapalıdır ve alınmaz. Filtre burada
    KOLAYLIK içindir — asıl zorlama `fetch_text` içindeki `guard_path`tedir.
    """

    source_id: str = "ajansspor"

    def parse(self, body: str, *, now: datetime) -> tuple[NewsItem, ...]:
        try:
            root = fromstring(body)
        except (ParseError, DefusedXmlException) as error:
            raise ContractViolation(
                f"{self.source_id}: sitemap ayrıştırılamadı ({type(error).__name__})"
            ) from error
        items: tuple[NewsItem, ...] = ()
        for node in root.iter():
            if not node.tag.endswith("}loc") and node.tag != "loc":
                continue
            url = (node.text or "").strip()
            if not url:
                continue
            items = (
                *items,
                NewsItem(title=url.rsplit("/", 1)[-1], url=url, published_at=now,
                         source_id=self.source_id),
            )
        if not items:
            raise ContractViolation(f"{self.source_id}: sitemap'te hiç <loc> yok")
        return items


def news_observation(item: NewsItem) -> Observation:
    """Haber gözlemi: YALNIZ başlık ve bağlantı.

    Ham içerik yeniden yayınlanmaz (spec §3.2/4) ve gövde saklanmaz: Faz 4'te Jev makaleyi
    okuduğunda ondan yalnız SAYISAL özellik türetilir.
    """
    return Observation(
        source_id=item.source_id,
        entity_kind="news",
        entity_key=item.url,
        observed_at=item.published_at,
        payload={
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at.isoformat(),
            "source_id": item.source_id,
        },
    )


_ADAPTERS: dict[str, NewsAdapter] = {
    "ajansspor": AjansporAdapter(),
    "googlenews": GoogleNewsAdapter(),
}


def enabled_adapters(sources: tuple[Source, ...]) -> tuple[NewsAdapter, ...]:
    return tuple(
        _ADAPTERS[entry.id] for entry in enabled_sources(sources) if entry.id in _ADAPTERS
    )
```

- [ ] **Step 4: Run tests, gate, commit**

```bash
uv run pytest tests/test_news.py -v && ./verify.sh
git add src/football_edge/collectors/news.py tests/test_news.py tests/fixtures/news
git commit -m "feat: kaynak-bağımsız haber adaptörü; Google News varsayılan KAPALI

Feed'in kendi copyright metni ticari kullanımı açıkça yasaklıyor ('personal,
non-commercial use ... any other use expressly prohibited'). Adaptör yazıldı,
sources.yaml'da enabled: false, lisans metni kodun yanında.

Ajansspor robots'u spec'in varsaydığından dar: /lineup/, /mac/, /oyuncu/, /lig/
kapalı — muhtemel 11 ALINMAZ. Dinamik makale URL'leri fetch anında guard_path ile
tek tek sorulur; declared_paths statik beyanı kapıda sorar, ikisi birbirinin yerine
geçmez.

XML defusedxml ile ayrıştırılıyor: besleme gövdesini biz yazmıyoruz ve stdlib
ElementTree varlık genişlemesine açık.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: Maç sonucu toplayıcı (The Odds API `/scores`)

ClubElo kullanılamaz durumda (Ruling A). Elo'yu kendimiz hesaplayacağız ve bunun için **sonuç**
gerekiyor — Faz 0'ın `matches` tablosunda skor **yok**.

**Neden The Odds API `/scores`:** sonuçları **zaten `matches` tablosunda duran aynı `event_id`
ile** veriyor. Yani sonuç yolu **hiç varlık eşlemesi gerektirmez** — ve "sessiz join hatası bu
projenin 1 numaralı ölüm sebebi" (spec §5.3). Bir eşleme adımını hiç var etmemek, onu doğru
yapmaktan iyidir.

**Doğrulanan API sözleşmesi (the-odds-api.com/liveapi/guides/v4/):**
`GET /v4/sports/{sport}/scores/?apiKey=…&daysFrom=…&dateFormat=iso`; `daysFrom` **1–3**;
yanıt `{id, sport_key, commence_time, completed, home_team, away_team, scores: [{name, score}], last_update}`.
**Kredi maliyeti:** *"The usage quota cost is 2 if the `daysFrom` parameter is specified
(returning completed events), otherwise the usage quota cost is 1."*

**Kredi disiplini:** lig başına 2 kredi × 6 lig = 12 kredi/tur. Aylık 500 kredi ve snapshot/seal
zaten harcıyor → **günde bir** koşar, `guard_quota` eşiği `min_remaining=40` ile.

**Files:**
- Create: `src/football_edge/collectors/results.py`, `tests/test_results.py`, `tests/fixtures/results/`
- **Salt okunur:** `config/leagues.yaml`, `src/football_edge/odds_api.py`,
  `src/football_edge/collect.py` (Ruling R1 — CLI dalı EKLEME)

**Interfaces:**
- Consumes: `odds_api.{read_quota, guard_quota, Quota, QuotaExhausted}`, `leagues.League`
- Produces:
  - `MatchOutcome` frozen dataclass: `match_id: str, home_goals: int, away_goals: int, completed: bool, observed_at: datetime`
  - `parse_scores(payload: list[dict[str, Any]], observed_at: datetime) -> tuple[MatchOutcome, ...]`
  - `fetch_scores(client, api_key, sport_key, *, days_from=3) -> tuple[tuple[MatchOutcome, ...], Quota]`
  - `write_results(conn, outcomes) -> int`
  - CLI: **bu task'ta YOK** (Ruling R1) — `fetch-results` dalı birleştirme adımında eklenir.
  - **Task 10 bu tipi import ETMEZ** — Elo motoru düz demet alır (paralel bağımsızlık).

- [ ] **Step 1: Write the failing test**

`tests/test_results.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from football_edge.collector import ContractViolation
from football_edge.collectors.results import parse_scores

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def event(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "evt1",
        "sport_key": "soccer_turkey_super_league",
        "commence_time": "2026-09-18T18:00:00Z",
        "completed": True,
        "home_team": "Galatasaray",
        "away_team": "Fenerbahce",
        "scores": [
            {"name": "Galatasaray", "score": "2"},
            {"name": "Fenerbahce", "score": "1"},
        ],
        "last_update": "2026-09-18T20:00:00Z",
    }
    return {**base, **overrides}


def test_maps_scores_to_home_and_away_by_name() -> None:
    """`scores` dizisinin SIRASI garanti değildir; ada göre eşlenir, konuma göre değil."""
    reversed_order = event(
        scores=[{"name": "Fenerbahce", "score": "1"}, {"name": "Galatasaray", "score": "2"}]
    )
    (outcome,) = parse_scores([reversed_order], NOW)
    assert (outcome.home_goals, outcome.away_goals) == (2, 1)


def test_skips_events_that_have_not_completed() -> None:
    assert parse_scores([event(completed=False, scores=None)], NOW) == ()


def test_unknown_team_name_in_scores_raises() -> None:
    """Skor adı takım adlarından biriyle eşleşmiyorsa SESSİZCE 0-0 yazmak felakettir."""
    with pytest.raises(ContractViolation, match="eşleşmedi"):
        parse_scores(
            [event(scores=[{"name": "Besiktas", "score": "2"}, {"name": "Fenerbahce", "score": "1"}])],
            NOW,
        )


def test_non_numeric_score_raises() -> None:
    with pytest.raises(ContractViolation, match="sayı"):
        parse_scores([event(scores=[{"name": "Galatasaray", "score": "-"},
                                    {"name": "Fenerbahce", "score": "1"}])], NOW)


def test_match_id_is_the_odds_api_event_id() -> None:
    """Sonuç yolu varlık eşlemesi GEREKTİRMEZ: aynı event_id zaten matches tablosunda."""
    (outcome,) = parse_scores([event()], NOW)
    assert outcome.match_id == "evt1"
```

- [ ] **Step 2: Run test to verify it fails, then implement**

`src/football_edge/collectors/results.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
import psycopg

from football_edge.collector import ContractViolation
from football_edge.ledger import canonical_timestamp
from football_edge.odds_api import BASE_URL, Quota, read_quota

SOURCE_ID = "oddsapi_scores"


@dataclass(frozen=True)
class MatchOutcome:
    match_id: str
    home_goals: int
    away_goals: int
    completed: bool
    observed_at: datetime


def _goals(scores: list[dict[str, Any]], team: str, event_id: str) -> int:
    for entry in scores:
        if str(entry.get("name", "")) == team:
            raw = str(entry.get("score", ""))
            if not raw.lstrip("-").isdigit():
                raise ContractViolation(f"{SOURCE_ID}: skor sayı değil ({event_id}, {team}): {raw!r}")
            return int(raw)
    raise ContractViolation(f"{SOURCE_ID}: '{team}' skor listesiyle eşleşmedi ({event_id})")


def parse_scores(
    payload: list[dict[str, Any]], observed_at: datetime
) -> tuple[MatchOutcome, ...]:
    """Tamamlanmış maçları sonuca çevirir; tamamlanmamışlar ATLANIR.

    `scores` dizisinin SIRASI belgelenmemiştir; ev/deplasman ADA göre eşlenir. Konuma göre
    okumak, skorları sessizce ters çevirir — ve ters bir sonuç, eksik bir sonuçtan çok daha
    zararlıdır: Elo onu doğru sanıp iki takımı da yanlış yöne iter.
    """
    outcomes: tuple[MatchOutcome, ...] = ()
    for event in payload:
        if not event.get("completed"):
            continue
        scores = event.get("scores")
        if not scores:
            continue
        event_id = str(event["id"])
        outcomes = (
            *outcomes,
            MatchOutcome(
                match_id=event_id,
                home_goals=_goals(scores, str(event["home_team"]), event_id),
                away_goals=_goals(scores, str(event["away_team"]), event_id),
                completed=True,
                observed_at=observed_at,
            ),
        )
    return outcomes


def fetch_scores(
    client: httpx.Client,
    api_key: str,
    sport_key: str,
    observed_at: datetime,
    *,
    days_from: int = 3,
) -> tuple[tuple[MatchOutcome, ...], Quota]:
    """`daysFrom` BELİRTİLİNCE maliyet 2 kredidir (1 değil) — belgelenmiş davranış.

    Geçerli aralık 1-3; dışına çıkmak API hatası verir. Günde bir koşulduğu için 3 seçilir:
    bir turun kaçması sonucu kaybettirmesin.
    """
    if not 1 <= days_from <= 3:
        raise ValueError(f"daysFrom 1-3 arasında olmalı, {days_from} verildi")
    response = client.get(
        f"{BASE_URL}/sports/{sport_key}/scores/",
        params={"apiKey": api_key, "daysFrom": str(days_from), "dateFormat": "iso"},
        timeout=30.0,
    )
    response.raise_for_status()
    return parse_scores(response.json(), observed_at), read_quota(response.headers)


def write_results(conn: psycopg.Connection[Any], outcomes: tuple[MatchOutcome, ...]) -> int:
    """Sonuçları yazar. `matches` tablosunda OLMAYAN maç sessizce düşer (yabancı anahtar).

    Bu bilinçlidir: `/scores` bizim topladığımızdan daha geniş bir maç kümesi döndürebilir
    ve Faz 0'ın defteri yalnız kendi gördüğü maçlar hakkında iddia taşır.
    """
    if not outcomes:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO match_results (match_id, observed_at, home_score, away_score, completed)
            SELECT %s::text, %s::timestamptz, %s::int, %s::int, %s::boolean
            WHERE EXISTS (SELECT 1 FROM matches WHERE id = %s)
            ON CONFLICT (match_id, observed_at) DO NOTHING
            """,
            [
                (
                    entry.match_id,
                    canonical_timestamp(entry.observed_at),
                    entry.home_goals,
                    entry.away_goals,
                    entry.completed,
                    entry.match_id,
                )
                for entry in outcomes
            ],
        )
        return max(cur.rowcount, 0)
```

- [ ] **Step 3: Run tests, gate, commit**

```bash
uv run pytest tests/test_results.py -v && ./verify.sh
git add src/football_edge/collectors/results.py tests/test_results.py
git commit -m "feat: maç sonucu toplayıcı (The Odds API /scores)

ClubElo API deaktif; Elo'yu kendimiz hesaplayacağız ve sonuç gerekiyordu.
/scores sonuçları matches tablosundaki AYNI event_id ile veriyor — sonuç yolu
hiç varlık eşlemesi gerektirmiyor, ve sessiz join hatası bu projenin 1 numaralı
ölüm sebebi.

Skorlar ADA göre eşleniyor: dizinin sırası belgelenmemiş ve konuma göre okumak
skoru sessizce ters çevirir. daysFrom belirtilince maliyet 2 kredi (belgelenmiş).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 10: Elo motoru (saf hesap, dış bağımlılık yok)

ClubElo'nun yerini alır. **Saf bir özyinelemedir**: aynı girdi → aynı çıktı, ağ yok, tarih yok.
Bu onu TDD için ideal ve **train/serve sapmasına karşı bağışık** yapar (spec §8): backtest de
canlı da bu tek fonksiyonu çağırır, ikinci bir yol yazılmaz.

**Bu task hiçbir toplayıcıya bağlı değildir.** Girdisi düz demettir
(`(home_key, away_key, home_goals, away_goals)`), Task 9'un tipini import etmez —
paralel bağımsızlık bunu gerektirir.

**Files:**
- Create: `src/football_edge/elo.py`, `tests/test_elo.py`

**Interfaces:**
- Consumes: yok
- Produces:
  - `EloConfig` frozen dataclass: `k: float = 20.0, home_advantage: float = 65.0, initial: float = 1500.0, goal_scaling: bool = True`
  - `expected_home(home_rating: float, away_rating: float, config: EloConfig) -> float`
  - `updated(home_rating, away_rating, home_goals, away_goals, config) -> tuple[float, float]`
  - `run(results: tuple[tuple[str, str, int, int], ...], config: EloConfig, *, seed: dict[str, float] | None = None) -> dict[str, float]`

- [ ] **Step 1: Write the failing test**

`tests/test_elo.py`:

```python
from __future__ import annotations

import pytest

from football_edge.elo import EloConfig, expected_home, run, updated

CONFIG = EloConfig()
FLAT = EloConfig(home_advantage=0.0, goal_scaling=False)


def test_equal_ratings_with_no_home_advantage_expect_half() -> None:
    assert expected_home(1500.0, 1500.0, FLAT) == pytest.approx(0.5)


def test_home_advantage_raises_the_expectation() -> None:
    assert expected_home(1500.0, 1500.0, CONFIG) > 0.5


def test_stronger_team_expects_more() -> None:
    assert expected_home(1700.0, 1500.0, FLAT) > expected_home(1500.0, 1700.0, FLAT)


def test_rating_change_is_zero_sum() -> None:
    """Elo kapalı bir sistemdir: biri ne kazanırsa diğeri onu kaybeder.

    Sıfır toplam bozulursa lig ortalaması sürüklenir ve ligler arası ortak ölçek
    (Faz 3, task 3) anlamını yitirir.
    """
    home, away = updated(1500.0, 1500.0, 2, 1, FLAT)
    assert (home - 1500.0) == pytest.approx(-(away - 1500.0))


def test_draw_between_equals_changes_nothing() -> None:
    assert updated(1500.0, 1500.0, 1, 1, FLAT) == pytest.approx((1500.0, 1500.0))


def test_beating_a_stronger_team_gains_more_than_beating_a_weaker_one() -> None:
    underdog, _ = updated(1400.0, 1700.0, 1, 0, FLAT)
    favourite, _ = updated(1700.0, 1400.0, 1, 0, FLAT)
    assert (underdog - 1400.0) > (favourite - 1700.0)


def test_bigger_margin_moves_the_rating_more_when_goal_scaling_is_on() -> None:
    narrow, _ = updated(1500.0, 1500.0, 1, 0, CONFIG)
    wide, _ = updated(1500.0, 1500.0, 4, 0, CONFIG)
    assert wide > narrow


def test_margin_is_ignored_when_goal_scaling_is_off() -> None:
    narrow, _ = updated(1500.0, 1500.0, 1, 0, FLAT)
    wide, _ = updated(1500.0, 1500.0, 4, 0, FLAT)
    assert narrow == pytest.approx(wide)


def test_run_is_deterministic_and_order_sensitive() -> None:
    """Sıra ÖNEMLİDİR: Elo yol bağımlıdır. Testin bunu bilmesi, backtest'in de bilmesini sağlar."""
    forward = (("a", "b", 2, 0), ("b", "c", 1, 0))
    backward = (("b", "c", 1, 0), ("a", "b", 2, 0))
    assert run(forward, FLAT) == run(forward, FLAT)
    assert run(forward, FLAT) != run(backward, FLAT)


def test_run_seeds_unknown_teams_at_the_initial_rating() -> None:
    ratings = run((("a", "b", 1, 0),), FLAT)
    assert set(ratings) == {"a", "b"}
    assert sum(ratings.values()) == pytest.approx(2 * FLAT.initial)


def test_run_accepts_a_seed_and_does_not_mutate_it() -> None:
    """Faz 2'nin MIT veri setindeki ClubElo sütunu tohum olarak geçirilecek."""
    seed = {"a": 1800.0}
    ratings = run((("a", "b", 1, 0),), FLAT, seed=seed)
    assert seed == {"a": 1800.0}, "tohum sözlüğü mutasyona uğradı"
    assert ratings["a"] > 1800.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_elo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'football_edge.elo'`

- [ ] **Step 3: Write the implementation**

`src/football_edge/elo.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

_SCALE = 400.0


@dataclass(frozen=True)
class EloConfig:
    """Elo parametreleri.

    Değerler BAŞLANGIÇ değeridir, gerçek değil: `k` ve `home_advantage` Faz 2'de tarihsel
    veri üzerinde FIT EDİLİR. Spec §4/3'ün kuralı burada da geçerli — uydurulmuş katsayı
    modelin yanlış olduğunu gizler. Bu sayılar yalnız fit edilene kadar duran iskelelerdir.
    """

    k: float = 20.0
    home_advantage: float = 65.0
    initial: float = 1500.0
    goal_scaling: bool = True


def expected_home(home_rating: float, away_rating: float, config: EloConfig) -> float:
    difference = (home_rating + config.home_advantage) - away_rating
    return 1.0 / (1.0 + 10.0 ** (-difference / _SCALE))


def _outcome(home_goals: int, away_goals: int) -> float:
    if home_goals > away_goals:
        return 1.0
    return 0.0 if home_goals < away_goals else 0.5


def _margin_multiplier(home_goals: int, away_goals: int, config: EloConfig) -> float:
    """Gol farkı çarpanı. Kapalıyken 1.0 — sıfır toplam her iki hâlde de korunur."""
    if not config.goal_scaling:
        return 1.0
    margin = abs(home_goals - away_goals)
    return 1.0 if margin <= 1 else (1.0 + (margin - 1) * 0.5)


def updated(
    home_rating: float,
    away_rating: float,
    home_goals: int,
    away_goals: int,
    config: EloConfig,
) -> tuple[float, float]:
    """Tek maçın ardından yeni reytingler. Değişim SIFIR TOPLAMDIR.

    Tek bir `change` hesaplanıp birine eklenip diğerinden çıkarılır; iki ayrı beklenti
    hesaplamak kayan nokta hatasıyla sızıntı yaratır ve lig ortalaması yıllar içinde
    sürüklenir.
    """
    expected = expected_home(home_rating, away_rating, config)
    actual = _outcome(home_goals, away_goals)
    change = config.k * _margin_multiplier(home_goals, away_goals, config) * (actual - expected)
    return home_rating + change, away_rating - change


def run(
    results: tuple[tuple[str, str, int, int], ...],
    config: EloConfig,
    *,
    seed: dict[str, float] | None = None,
) -> dict[str, float]:
    """Maçları SIRAYLA işler ve nihai reytingleri döner.

    SIRA yük taşır: Elo yol bağımlıdır. Çağıran maçları `commence_time`e göre sıralamak
    zorundadır — sıralanmamış bir dizi sessizce başka bir sayı üretir ve hiçbir şey
    kırmızı vermez.

    `seed` MUTASYONA UĞRAMAZ; kopyalanır (Faz 2'nin MIT ClubElo sütunu buraya geçirilecek).
    """
    ratings = dict(seed or {})
    for home, away, home_goals, away_goals in results:
        home_rating = ratings.get(home, config.initial)
        away_rating = ratings.get(away, config.initial)
        new_home, new_away = updated(home_rating, away_rating, home_goals, away_goals, config)
        ratings = {**ratings, home: new_home, away: new_away}
    return ratings
```

- [ ] **Step 4: Run tests, gate, commit**

```bash
uv run pytest tests/test_elo.py -v && ./verify.sh
git add src/football_edge/elo.py tests/test_elo.py
git commit -m "feat: saf Elo motoru — ClubElo API'sinin yerine

api.clubelo.com/Fixtures 'Fixtures API deactivated' dönüyor, tarih/kulüp uçları
ısrarlı 502. Elo deterministik bir özyineleme: ağ yok, dış bağımlılık yok, ve
backtest ile canlı TEK fonksiyonu çağırdığı için train/serve sapmasına bağışık.

Değişim sıfır toplam (tek `change` hesaplanıp eklenip çıkarılıyor); k ve
home_advantage Faz 2'de fit edilecek iskele değerlerdir, gerçek değil.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Paralel kümeyi birleştirme

Beş worktree yeşil olduğunda, **tek tek** ve `--no-ff` ile birleştir; her birleştirmeden sonra
kapıyı koş. Hepsi bittikten sonra:

```bash
./verify.sh
uv run pytest -q          # çakışan fixture/işaret yok mu
git log --oneline --graph -12
```

### Birleştirme adımı: CLI kaydı (Ruling R1)

Paralel task'ların hiçbiri `collect.py`'a dokunmadı. Beş dal birleştikten sonra, **tek sıralı
commit'te** dört alt komut eklenir: `fetch-tff`, `fetch-venues`, `fetch-news`, `fetch-results`.
Her biri kendi `collect_*()` fonksiyonunu çağırır; imzalar ilgili task'ların Interfaces
bloklarında yazılıdır. `choices` demetine dördü de eklenir ve **eklenen her yeni çıkış kodunun
`.github/workflows/*.yml` içinde adlandırılmış bir `case` arm'ı olur** —
`tests/test_workflows.py` bu bağı kapıda tutuyor.

```bash
uv run pytest tests/test_workflows.py -v && ./verify.sh
git add src/football_edge/collect.py .github/workflows
git commit -m "feat: paralel toplayicilarin CLI kaydi

R1: paralel task'lar collect.py'a dokunmadi; dort alt komut tek sirali commit'te.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**Birleştirme sonrası tek bir soru sorulur ve cevabı yazılır:** *bu tur neyi bozdu?* Faz 0'ın
dördüncü düzeltme turuna kadar süren ders buydu — bir düzeltme komşu bir varsayımı geçersiz
kılabilir. Beş bağımsız dalın hepsi `collector.py`'nin aynı sözleşmesine dayanıyor; biri onu
farklı anladıysa çakışma derleme hatası olarak değil, **sessiz davranış farkı** olarak gelir.

---
### Task 11: Varlık eşleme (Jev `Choice`) — sessiz join hatasına karşı

*"Sessiz join hatası bu projenin bir numaralı ölüm sebebi"* (spec §5.3). FootyStats "Galatasaray",
TFF "Galatasaray A.Ş.", The Odds API "Galatasaray" diyor — ve biri "Gaziantep FK" ile "Gaziantep
Basketbol"u karıştırdığında **hiçbir şey kırmızı vermez**; model yanlış takımın xG'siyle fit olur.

**Kanonik ad uzayı The Odds API'dir** — çünkü `matches.id` zaten oradan geliyor ve defterin
tamamı o kimliğe bağlı. Diğer her kaynak ona eşlenir.

**Mimari (spec §5.3):** *kod aday çıkarır, Jev seçer.* Kod, normalize edilmiş ad benzerliğiyle
lig kapsamındaki adayları daraltır; Jev `Choice` ile doğrusunu seçer; **eşik altındaki eşleşme
YAZILMAZ** ve çözülmemiş olarak raporlanır. Bir eşleşmeyi atlamak, yanlış eşlemekten iyidir.

**Files:**
- Create: `src/football_edge/jev.py`, `src/football_edge/mapping.py`, `tests/test_jev.py`,
  `tests/test_mapping.py`, `tests/fake_jev.py`
- Modify: `src/football_edge/collect.py`, `.env.example`

**Interfaces:**
- Consumes: `collector.Observation`, `entity_aliases` tablosu (0002)
- Produces:
  - `JevClient` Protocol: `ask_choice(state: dict[str, Any], instructions: str, criteria: dict[str, str]) -> ChoiceAnswer`
  - `ChoiceAnswer` frozen dataclass: `choice: str, confidence: float, probabilities: dict[str, float]`
  - `TypeSafeJev` — gerçek istemci (`typesafe_sdk.TypeSafeClient`)
  - `NO_MATCH = "none of the above"`
  - `candidates(alias: str, canonical: tuple[str, ...], *, limit: int = 8) -> tuple[str, ...]`
  - `resolve(alias, canonical, client, *, league, threshold=0.75) -> Resolution`
  - `Resolution` frozen dataclass: `alias: str, canonical_id: str | None, confidence: float, reason: str`
  - `write_aliases(conn, source_id, entity_kind, resolutions, now) -> int`
  - CLI: `map-entities`

- [ ] **Step 1: Write the failing test**

`tests/fake_jev.py`:

```python
"""Jev taklidi: ağa çıkmaz, senaryoyu test yazar."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from football_edge.jev import ChoiceAnswer


@dataclass
class FakeJev:
    answer: ChoiceAnswer
    seen: list[dict[str, Any]] = field(default_factory=list)

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        self.seen = [*self.seen, {"state": state, "criteria": criteria}]
        return self.answer
```

`tests/test_mapping.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from football_edge.jev import NO_MATCH, ChoiceAnswer
from football_edge.mapping import candidates, resolve
from tests.fake_jev import FakeJev

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
CANONICAL = ("Galatasaray", "Fenerbahce", "Besiktas", "Gaziantep FK", "Trabzonspor")


def answer(choice: str, confidence: float) -> ChoiceAnswer:
    return ChoiceAnswer(choice=choice, confidence=confidence, probabilities={choice: confidence})


def test_candidates_are_narrowed_before_the_model_is_asked() -> None:
    """Kod aday çıkarır, Jev seçer (spec §5.3). Tüm listeyi sormak hem pahalı hem gürültülü."""
    narrowed = candidates("Galatasaray A.Ş.", CANONICAL, limit=3)
    assert "Galatasaray" in narrowed
    assert len(narrowed) <= 3


def test_candidates_never_omit_a_plausible_match() -> None:
    """Model, listeye KONULMAYAN bir değeri seçemez (TypeSafe Choice dokümanı)."""
    assert "Gaziantep FK" in candidates("Gaziantep Futbol Kulübü", CANONICAL)


def test_high_confidence_match_is_accepted() -> None:
    client = FakeJev(answer("Galatasaray", 0.97))
    found = resolve("Galatasaray A.Ş.", CANONICAL, client, league="tur.1")
    assert found.canonical_id == "Galatasaray"


def test_low_confidence_match_is_refused_and_named() -> None:
    """Eşik altı eşleşme YAZILMAZ. Bir eşleşmeyi atlamak, yanlış eşlemekten iyidir."""
    client = FakeJev(answer("Fenerbahce", 0.41))
    found = resolve("FB A.Ş.", CANONICAL, client, league="tur.1", threshold=0.75)
    assert found.canonical_id is None
    assert "eşik" in found.reason


def test_no_match_option_is_offered_and_honoured() -> None:
    """Liste her girdiyi kapsamayabilir; 'hiçbiri' seçeneği olmadan model UYDURMAK zorunda kalır."""
    client = FakeJev(answer(NO_MATCH, 0.99))
    found = resolve("Panathinaikos", CANONICAL, client, league="tur.1")
    assert found.canonical_id is None
    assert NO_MATCH in client.seen[0]["criteria"]


def test_league_context_reaches_the_model() -> None:
    """Aynı ad farklı liglerde farklı kulüp olabilir; lig bağlamsız soru eksik sorudur."""
    client = FakeJev(answer("Galatasaray", 0.9))
    resolve("Galatasaray A.Ş.", CANONICAL, client, league="tur.1")
    assert client.seen[0]["state"]["league"] == "tur.1"


def test_exact_normalised_match_skips_the_model_entirely() -> None:
    """Deterministik cevabı modele sormak hem para hem gürültüdür (spec §5.2 tasarım kuralı)."""
    client = FakeJev(answer("YANLIS", 1.0))
    found = resolve("  GALATASARAY  ", CANONICAL, client, league="tur.1")
    assert found.canonical_id == "Galatasaray"
    assert client.seen == [], "birebir eşleşmede model çağrıldı"
```

- [ ] **Step 2: Run test to verify it fails, then implement the client**

`src/football_edge/jev.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

NO_MATCH = "none of the above"


@dataclass(frozen=True)
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]


class JevClient(Protocol):
    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer: ...


class TypeSafeJev:
    """TypeSafe System One (Jev) sarmalayıcısı.

    `typesafe_sdk` yalnız BURADA import edilir: eşleme mantığı sağlayıcıyı tanımaz ve
    testler ağa çıkmadan `JevClient` protokolünü taklit eder.

    `confidence`, olasılık DAĞILIMININ ne kadar tepeli olduğunu özetler — işin doğru
    yapıldığının garantisi değil (TypeSafe confidence dokümanı). Eşik, sonucun
    bedeline göre seçilir; burada bedel sessiz bir join hatasıdır, o yüzden yüksektir.
    """

    def __init__(self, api_key: str | None = None) -> None:
        resolved = api_key or os.getenv("TYPESAFE_API_KEY")
        if not resolved:
            raise RuntimeError("TYPESAFE_API_KEY tanımlı değil")
        self._api_key = resolved

    def ask_choice(
        self, state: dict[str, Any], instructions: str, criteria: dict[str, str]
    ) -> ChoiceAnswer:
        from typesafe_sdk import Choice, TypeSafeClient

        with TypeSafeClient(api_key=self._api_key) as client:
            response = client.system_one(
                state=state,
                questions={"match": Choice(instructions=instructions, criteria=criteria)},
            )
        answer = response.choices["match"]
        return ChoiceAnswer(
            choice=str(answer.choice),
            confidence=float(answer.confidence),
            probabilities={str(k): float(v) for k, v in dict(answer.probabilities).items()},
        )
```

`src/football_edge/mapping.py`:

```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

import psycopg

from football_edge.naming import normalise_team
from football_edge.jev import NO_MATCH, ChoiceAnswer, JevClient

LOGGER = logging.getLogger("football_edge.mapping")

_INSTRUCTIONS = (
    "The alias below is a football club name taken from one data source. "
    "Select the club from the canonical list that refers to the SAME club. "
    "Clubs from the same city can be different clubs, and a club may field teams in other "
    "sports — only an exact same-club match counts. "
    f"If no option refers to the same club, select '{NO_MATCH}'."
)


@dataclass(frozen=True)
class Resolution:
    alias: str
    canonical_id: str | None
    confidence: float
    reason: str


def candidates(alias: str, canonical: tuple[str, ...], *, limit: int = 8) -> tuple[str, ...]:
    """Normalize edilmiş ad benzerliğine göre en olası adaylar.

    Model, listeye KONULMAYAN bir değeri seçemez (TypeSafe Choice dokümanı: "the model
    cannot choose an omitted value"), o yüzden `limit` cömert tutulur. Aday üretimi
    deterministiktir ve testi vardır — daraltmayı modele bırakmak, hatayı görünmez yapar.
    """
    target = normalise_team(alias)
    scored = sorted(
        canonical,
        key=lambda name: SequenceMatcher(None, target, normalise_team(name)).ratio(),
        reverse=True,
    )
    return tuple(scored[:limit])


def resolve(
    alias: str,
    canonical: tuple[str, ...],
    client: JevClient,
    *,
    league: str,
    threshold: float = 0.75,
) -> Resolution:
    """Takma adı kanonik ada eşler; EŞİK ALTINDAKİ eşleşme reddedilir.

    Reddetmek sessiz kalmak değildir: `Resolution.reason` sebebi taşır ve çağıran onu
    raporlar. Yanlış bir eşleşme hiçbir zaman kırmızı vermez; eksik bir eşleşme raporda
    görünür ve elle kapatılabilir.
    """
    normalised = normalise_team(alias)
    for name in canonical:
        if normalise_team(name) == normalised:
            # Deterministik cevabı modele sormak hem para hem gürültüdür (spec §5.2:
            # "bunun cevabı tabloda zaten var mı?").
            return Resolution(alias, name, 1.0, "birebir normalize eşleşme")

    options = candidates(alias, canonical)
    criteria = {name: f"The club known as {name}" for name in options}
    criteria[NO_MATCH] = "None of the listed clubs is the same club as the alias"
    answer: ChoiceAnswer = client.ask_choice(
        state={"alias": alias, "league": league, "source_naming": normalised},
        instructions=_INSTRUCTIONS,
        criteria=criteria,
    )
    if answer.choice == NO_MATCH:
        return Resolution(alias, None, answer.confidence, "model 'hiçbiri' dedi")
    if answer.confidence < threshold:
        return Resolution(
            alias,
            None,
            answer.confidence,
            f"güven {answer.confidence:.2f} < eşik {threshold:.2f} — yazılmadı",
        )
    return Resolution(alias, answer.choice, answer.confidence, "model seçti")


def write_aliases(
    conn: psycopg.Connection[Any],
    source_id: str,
    entity_kind: str,
    resolutions: tuple[Resolution, ...],
    now: datetime,
) -> int:
    """YALNIZ çözülmüş eşleşmeleri yazar. Çözülmeyenler çağıran tarafından raporlanır."""
    rows = [entry for entry in resolutions if entry.canonical_id is not None]
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO entity_aliases
              (source_id, entity_kind, alias, canonical_id, confidence, decided_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, entity_kind, alias) DO UPDATE SET
              canonical_id = excluded.canonical_id,
              confidence = excluded.confidence,
              decided_at = excluded.decided_at
            """,
            [
                (source_id, entity_kind, entry.alias, entry.canonical_id, entry.confidence, now)
                for entry in rows
            ],
        )
    conn.commit()
    return len(rows)
```

`.env.example`'a ekle: `TYPESAFE_API_KEY=`

- [ ] **Step 3: Run tests, gate, commit**

```bash
uv run pytest tests/test_mapping.py tests/test_jev.py -v && ./verify.sh
git add src/football_edge/jev.py src/football_edge/mapping.py tests/test_mapping.py tests/test_jev.py tests/fake_jev.py .env.example src/football_edge/collect.py
git commit -m "feat: varlık eşleme — kod aday çıkarır, Jev Choice ile seçer

Sessiz join hatası bu projenin 1 numaralı ölüm sebebi (spec §5.3). Eşik altındaki
eşleşme YAZILMAZ ve sebebiyle raporlanır: bir eşleşmeyi atlamak raporda görünür,
yanlış eşlemek hiçbir zaman kırmızı vermez.

Birebir normalize eşleşmede model HİÇ çağrılmaz; 'hiçbiri' seçeneği her zaman
listede, yoksa model uydurmak zorunda kalır.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 12: Dil kalibrasyon testi — ölçülmeden hiçbir dil üretime alınmaz

Spec §5.4 ve açık soru #4: **Jev'in Türkçe ve diğer dillerdeki doğruluğu ölçülmemiştir.** Yol
haritası bunu Faz 1'in şartı yapıyor: *"Kötü çıkarsa mimarinin en global parçası çöker — o
yüzden Faz 1'in sonunda değil, ölçüm biter bitmez karar verilir."*

**Bu task insan emeği gerektirir ve bunu gizlemek anlamsızdır:** dil başına ~100 haber başlığı
**elle etiketlenir**. Plan etiketleme biçimini, aracını ve eşiği verir; etiketleri veremez.
Etiketsiz bir kalibrasyon, kendi konusunu yeniden yazan bir testtir.

**Files:**
- Create: `config/languages.yaml`, `data/calibration/README.md`, `data/calibration/tr.jsonl`,
  `src/football_edge/calibration.py`, `tests/test_calibration.py`
- Modify: `verify.sh`, `src/football_edge/collect.py`

**Interfaces:**
- Consumes: `jev.{JevClient, ChoiceAnswer}`, `collectors.news.NewsItem`
- Produces:
  - `LabelledItem` frozen dataclass: `title: str, url: str, language: str, relevant: bool, team: str`
  - `load_labels(path: Path) -> tuple[LabelledItem, ...]`
  - `CalibrationReport` frozen dataclass: `language: str, n: int, accuracy: float, false_positive: int, false_negative: int, mean_confidence: float`
  - `score_language(items, client, *, language) -> CalibrationReport`
  - `production_ready(report, *, min_n=100, min_accuracy=0.85) -> tuple[bool, str]`
  - CLI: `calibrate --language tr` — Jev'i koşturur, `<lang>.report.json` yazar (PARA HARCAR)
  - CLI: `check-languages` — **ağa çıkmaz**; `config/languages.yaml`'daki her
    `production_enabled: true` için rapor dosyasının var olduğunu ve `production_ready()`'yi
    geçtiğini doğrular. Kapının `dil-kalibrasyonu` adımı bunu çağırır, `calibrate`'i değil:
    kapı ne para harcar ne ağa çıkar.

- [ ] **Step 1: Write the labelling format and the seed file**

`data/calibration/README.md`:

```markdown
# Dil kalibrasyon etiketleri

Dil başına ~100 haber başlığı, ELLE etiketlenmiş. Spec §5.4: ölçülmeden hiçbir dil
üretime alınmaz.

Biçim: satır başına bir JSON nesnesi (JSONL).

    {"title": "...", "url": "...", "language": "tr", "team": "Galatasaray", "relevant": true}

- `team` — haberin ilgili olduğu iddia edilen takımın KANONİK adı.
- `relevant` — bu haber GERÇEKTEN o takımın YAKLAŞAN maçını ilgilendiriyor mu?
  `true`: kadro, sakatlık, ceza, hoca, motivasyon, saha/hava.
  `false`: transfer dedikodusu, geçmiş maç özeti, başka takım, kulüp dışı haber.

Etiketleyen kişi bir insandır ve adı `data/calibration/<dil>.meta.json` içine yazılır.
Etiketleri modelin kendisine ürettirmek, ölçümü ölçülenin kopyası yapar — o rapor
hiçbir şey kanıtlamaz.

Başlıkları toplamak için:

    uv run python -m football_edge.collect harvest-labels --language tr --out data/calibration/tr.raw.jsonl

Sonra `relevant` alanlarını elle doldur ve `.jsonl` olarak kaydet.
```

`data/calibration/tr.jsonl` — **ilk 10 satırı elle yaz** (kalanı etiketleme turunda gelir).
En az bir açık `true`, bir açık `false` ve bir **sınırda** vaka içermeli; sınır vakası yoksa
ölçüm yalnız kolay soruları ölçer.

- [ ] **Step 2: Write the failing test**

`tests/test_calibration.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from football_edge.calibration import (
    LabelledItem,
    load_labels,
    production_ready,
    score_language,
)
from football_edge.jev import ChoiceAnswer
from tests.fake_jev import FakeJev


def item(relevant: bool, title: str = "Galatasaray'da sakatlık") -> LabelledItem:
    return LabelledItem(title=title, url=f"https://x/{title}", language="tr",
                        relevant=relevant, team="Galatasaray")


def answer(choice: str, confidence: float = 0.9) -> ChoiceAnswer:
    return ChoiceAnswer(choice=choice, confidence=confidence, probabilities={choice: confidence})


def test_perfect_agreement_scores_one() -> None:
    report = score_language((item(True), item(True)), FakeJev(answer("relevant")), language="tr")
    assert report.accuracy == pytest.approx(1.0)
    assert report.n == 2


def test_disagreement_is_split_into_false_positive_and_false_negative() -> None:
    """Tek bir 'doğruluk' sayısı yönü gizler. Hangi yönde yanıldığı KARAR değiştirir."""
    report = score_language(
        (item(False), item(False)), FakeJev(answer("relevant")), language="tr"
    )
    assert report.accuracy == pytest.approx(0.0)
    assert report.false_positive == 2
    assert report.false_negative == 0


def test_language_below_the_sample_floor_is_not_production_ready() -> None:
    """%100 doğruluk 12 örnekte hiçbir şey kanıtlamaz."""
    report = score_language((item(True),) * 12, FakeJev(answer("relevant")), language="tr")
    ready, reason = production_ready(report)
    assert ready is False
    assert "örnek" in reason


def test_language_below_the_accuracy_floor_is_not_production_ready() -> None:
    items = (item(True),) * 80 + (item(False),) * 40
    report = score_language(items, FakeJev(answer("relevant")), language="tr")
    ready, reason = production_ready(report)
    assert ready is False
    assert "doğruluk" in reason


def test_labels_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "tr.jsonl"
    target.write_text(
        '{"title":"a","url":"u","language":"tr","team":"Galatasaray","relevant":true}\n'
        '{"title":"b","url":"v","language":"tr","team":"Fenerbahce","relevant":false}\n',
        encoding="utf-8",
    )
    loaded = load_labels(target)
    assert len(loaded) == 2
    assert loaded[0].relevant is True and loaded[1].relevant is False
```

- [ ] **Step 3: Implement**

`src/football_edge/calibration.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from football_edge.jev import JevClient

RELEVANT = "relevant"
NOT_RELEVANT = "not relevant"

_INSTRUCTIONS = (
    "Does this news headline carry information that affects the named club's NEXT match? "
    "Relevant: squad availability, injuries, suspensions, manager change, motivation, "
    "venue or weather. Not relevant: transfer rumours, reports on past matches, other "
    "clubs, or non-football club news."
)


@dataclass(frozen=True)
class LabelledItem:
    title: str
    url: str
    language: str
    relevant: bool
    team: str


@dataclass(frozen=True)
class CalibrationReport:
    language: str
    n: int
    accuracy: float
    false_positive: int
    false_negative: int
    mean_confidence: float


def load_labels(path: Path) -> tuple[LabelledItem, ...]:
    items: tuple[LabelledItem, ...] = ()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        items = (*items, LabelledItem(**record))
    return items


def score_language(
    items: tuple[LabelledItem, ...], client: JevClient, *, language: str
) -> CalibrationReport:
    """Jev'in cevaplarını İNSAN etiketleriyle karşılaştırır.

    Yanılma YÖNÜ ayrı sayılır: yanlış pozitif (alakasız haberi alakalı sanmak) sinyali
    gürültüyle şişirir; yanlış negatif (alakalı haberi kaçırmak) sinyali kaybettirir.
    Tek bir doğruluk sayısı ikisini eşitler ve hangisinin olduğu KARARI değiştirir.
    """
    correct = 0
    false_positive = 0
    false_negative = 0
    confidences: list[float] = []
    for entry in items:
        answer = client.ask_choice(
            state={"headline": entry.title, "club": entry.team, "language": entry.language},
            instructions=_INSTRUCTIONS,
            criteria={
                RELEVANT: "The headline affects the club's next match",
                NOT_RELEVANT: "The headline does not affect the club's next match",
            },
        )
        predicted = answer.choice == RELEVANT
        confidences.append(answer.confidence)
        if predicted == entry.relevant:
            correct += 1
        elif predicted:
            false_positive += 1
        else:
            false_negative += 1
    total = len(items)
    return CalibrationReport(
        language=language,
        n=total,
        accuracy=correct / total if total else 0.0,
        false_positive=false_positive,
        false_negative=false_negative,
        mean_confidence=sum(confidences) / len(confidences) if confidences else 0.0,
    )


def production_ready(
    report: CalibrationReport, *, min_n: int = 100, min_accuracy: float = 0.85
) -> tuple[bool, str]:
    """Bir dilin üretime alınabilirliği. Eşikler ÖLÇÜLDÜKTEN sonra ayarlanır, önce değil.

    `min_n` neden var: %100 doğruluk 12 örnekte hiçbir şey kanıtlamaz. `min_accuracy`
    başlangıç değeridir ve ilk gerçek ölçümden sonra bu dosyada gerekçesiyle güncellenir.
    """
    if report.n < min_n:
        return False, f"{report.language}: {report.n} örnek < {min_n} — ölçüm yetersiz"
    if report.accuracy < min_accuracy:
        return (
            False,
            f"{report.language}: doğruluk {report.accuracy:.2f} < {min_accuracy:.2f} "
            f"(YP={report.false_positive}, YN={report.false_negative})",
        )
    return True, f"{report.language}: doğruluk {report.accuracy:.2f}, n={report.n}"
```

`config/languages.yaml`:

```yaml
# Bir dil, kalibrasyon raporu OLMADAN production_enabled olamaz. Kapı bunu zorlar:
# rapor dosyası yoksa ya da eşiği geçmiyorsa `dil-kalibrasyonu` adımı kırmızı verir.
languages:
  - code: tr
    production_enabled: false      # ölçülene kadar false
    calibration_report: data/calibration/tr.report.json
  - code: en
    production_enabled: false
    calibration_report: data/calibration/en.report.json
```

- [ ] **Step 4: Run the real calibration for Turkish**

Bu adım **gerçek Jev çağrısı yapar** ve para harcar (~$0.0004/soru × ~100 = ihmal edilebilir).

```bash
TYPESAFE_API_KEY="$(grep '^TYPESAFE_API_KEY=' .env | cut -d= -f2-)" \
  uv run python -m football_edge.collect calibrate --language tr
```

Expected: `data/calibration/tr.report.json` yazılır ve stdout'a rapor basılır.
**Sonucu ne çıkarsa çık, Task 13'te handoff'a yazılır.** Doğruluk eşiğin altındaysa
`config/languages.yaml` `production_enabled: false` kalır — bu bir başarısızlık değil,
Faz 1'in **ölçmek için var olduğu** şeyin cevabıdır. Yol haritası: *"ölçüm biter bitmez
karar verilir."*

- [ ] **Step 5: Add the gate step, run the gate, commit**

`verify.sh`'e `step "veri-sözleşmesi"` altına:

```bash
# Ölçülmemiş dil üretime alınamaz (spec §5.4). Bu adım ağa çıkmaz: yalnız
# config/languages.yaml'daki production_enabled bayraklarının bir kalibrasyon raporuyla
# desteklendiğini sorar. Rapor yoksa bayrak açık olamaz.
step "dil-kalibrasyonu" uv run python -m football_edge.collect check-languages
```

`check-languages` uygulaması (`collect.py`'ye ekle):

```python
def _check_languages_command(*, languages_path: Path = LANGUAGES_PATH) -> int:
    """Rapor OLMADAN production_enabled olan dil var mı? Ağa çıkmaz, para harcamaz."""
    raw = yaml.safe_load(languages_path.read_text(encoding="utf-8"))
    violations: tuple[str, ...] = ()
    for entry in raw["languages"]:
        if not entry["production_enabled"]:
            continue
        report_path = Path(entry["calibration_report"])
        if not report_path.is_file():
            violations = (*violations, f"{entry['code']}: production_enabled ama rapor yok")
            continue
        report = CalibrationReport(**json.loads(report_path.read_text(encoding="utf-8")))
        ready, reason = production_ready(report)
        if not ready:
            violations = (*violations, reason)
    for text in violations:
        sys.stdout.write(f"DİL KALİBRASYON İHLALİ: {text}\n")
    if violations:
        return EXIT_LANGUAGE_UNCALIBRATED
    sys.stdout.write("dil kalibrasyonu: TEMİZ\n")
    return 0
```

`collect.py`'ye `EXIT_LANGUAGE_UNCALIBRATED = 7`, `LANGUAGES_PATH = Path("config/languages.yaml")`
ve `import json` / `import yaml` ekle; `choices` demetine `"calibrate"` ve `"check-languages"`
ekle; `calibrate` için `--language` argümanı tanımla. İkisi de `connect()` AÇILMADAN önce
dallanır — hiçbiri veritabanına dokunmaz.

```bash
./verify.sh
git add config/languages.yaml data/calibration src/football_edge/calibration.py tests/test_calibration.py verify.sh src/football_edge/collect.py
git commit -m "feat: dil kalibrasyon ölçümü ve üretim kapısı

Spec §5.4 / açık soru #4: Jev'in çok dilli doğruluğu ölçülmemişti. Dil başına ~100
ELLE etiketlenmiş haber; etiketleri modele ürettirmek ölçümü ölçülenin kopyası yapar.

Yanılma yönü ayrı sayılıyor: yanlış pozitif sinyali şişirir, yanlış negatif
kaybettirir; tek doğruluk sayısı ikisini eşitler ve kararı değiştirir.

Kapı, kalibrasyon raporu olmayan bir dilin production_enabled olmasını engelliyor.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 13: Faz 1 kapısı, uçtan uca doğrulama ve handoff

Faz geçiş kuralı üç şey ister (yol haritası): tüm task'lar kapıdan geçti · critical/high bulgu
yok · **kapının neyi ÖLÇMEDİĞİ adıyla yazıldı.** Üçüncüsü en çok atlanandır ve en pahalıya
patlayandır: ölçülmediği yazılmamış bir boşluk, sonraki fazda *"zaten doğrulanmıştı"* sanılarak
üstüne inşa edilir.

**Files:**
- Create: `docs/phases/01-toplayicilar/HANDOFF.md`
- Modify: `docs/HANDOFF.md`, `docs/DEFERRED.md`, `README.md`

- [ ] **Step 1: Run the full gate and read the OUTPUT, not the summary**

```bash
DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d= -f2-)" ./verify.sh
echo "--- exit: $? ---"
cat "${TMPDIR:-/tmp}/football-edge-verify.log"
```

Beklenen **on adım**: `ruff-check` · `ruff-format` · `mypy` · `pytest` · `paket-kurulu` ·
`kaynak-politikası` · `veri-sözleşmesi` · `dil-kalibrasyonu` · `secrets` · `zincir`.
**`SKIP` gören her adımı adıyla not al** — geçmek değildir.

- [ ] **Step 2: Prove the gate actually goes red**

Yeşil bir kapı, kırmızı verdiği kanıtlanmadan bir kural değildir (Faz 0 Ruling 3'ün dersi).
Her yeni adımı **bilerek kır**, kırmızı gördüğünü doğrula, **geri al**:

```bash
# 1) kaynak-politikası: beyan edilmiş ama robots'a aykırı bir yol ekle
cp config/sources.yaml /tmp/sources.bak
uv run python -m football_edge.collect sources-audit; echo "önce: $?"   # 0 beklenir
sed -i '' "s#declared_paths: \['/turkey/super-lig/xg'#declared_paths: ['/c-dl.php', '/turkey/super-lig/xg'#" config/sources.yaml
uv run python -m football_edge.collect sources-audit; echo "kırıkken: $?"  # 6 beklenir
cp /tmp/sources.bak config/sources.yaml
uv run python -m football_edge.collect sources-audit; echo "sonra: $?"   # 0 beklenir

# 2) veri-sözleşmesi: bir fixture'ın sütun başlığını boz
cp tests/fixtures/footystats/turkey-super-lig-xg.html /tmp/fs.bak
sed -i '' 's/>xGA</>ExpGA</' tests/fixtures/footystats/turkey-super-lig-xg.html
uv run pytest tests/ -q -m contract; echo "kırıkken: $?"                 # 1 beklenir
cp /tmp/fs.bak tests/fixtures/footystats/turkey-super-lig-xg.html
uv run pytest tests/ -q -m contract; echo "sonra: $?"                    # 0 beklenir

git status --porcelain     # BOŞ olmalı: kırdıklarının hepsi geri alındı
```

Bir adım kırıkken **yeşil kaldıysa o bir bulgudur** — kapıyı düzelt, raporla, gevşetme.
Daha geniş bir tur için `/loop-kit:judge-selftest` (temiz çalışma ağacı ister).

- [ ] **Step 3: Write the phase handoff**

`docs/phases/01-toplayicilar/HANDOFF.md` — bölümleri:

1. **Ne bitti** — task başına bir satır, commit SHA'sıyla.
2. **Canlı ve doğrulanmış durum** — kaynak başına: son başarılı tur, yazılan gözlem sayısı,
   tazelik penceresi. Faz 0'ın §2 tablosunun biçimini izle: her satırın "nasıl doğrulandı"
   sütunu olsun.
3. **Kapının ÖLÇMEDİĞİ** — aşağıdaki liste **başlangıç noktasıdır**, tamamlanmış hâli değil.
   Uygulama sırasında bulunan her yeni boşluk buraya eklenir.
4. **Verilen kararlar** — Ruling A/B/C ve uygulama sırasında verilen her yeni karar.
5. **Faz 2'nin ön koşulları** — MIT CSV yükleyici neyi hazır bulacak: `match_results`
   (Elo tohumu), `source_observations` (xG), `entity_aliases` (join anahtarı).

- [ ] **Step 4: Update the inherited debt and the top-level handoff**

`docs/DEFERRED.md`'ye **yeni bölüm** ekle — Faz 1'in devrettiği borç:

| # | Konu | Not |
|---|---|---|
| F1-1 | **FBref kapalı** → global hakem ve seyirci verisi YOK | TR'de TFF karşılıyor. Faz 3'ün baz modeli hakem özelliği olmadan kurulur. "Zaten vardı" sanılmasın. |
| F1-2 | **ClubElo kullanılamaz** → Elo kendi motorumuzda | `k` ve `home_advantage` **fit edilmedi**, iskele değer. Faz 2'nin işi. |
| F1-3 | **Google News lisans çatışması** | Feed'in copyright'ı ticari kullanımı yasaklıyor. MIT CSV ile aynı muamele: ticari lansman öncesi avukat. |
| F1-4 | **Understat kapalı** | robots.txt `Disallow: /`. xG kapsamını FootyStats devraldı; **6 ligin xG'si artık tek kaynağa bağlı** — o kaynak düşerse yedek yok. |
| F1-5 | **`source_observations` hash zincirsiz** | Bilinçli: zincir oran defteri içindir. Özellik girdisi kurcalanırsa dış çıpa bunu göstermez. |
| F1-6 | **TFF yalnız BU HAFTA** | `__VIEWSTATE` postback'i gerekli; geçmiş hafta/lig alınamıyor. ~~VAR ataması sayfada hiç geçmiyor.~~ **DÜZELTİLDİ:** VAR/AVAR sayfada VAR, `(V)`/`(A)` rol işaretiyle — toplanmıyor, çünkü sözleşme tek `referee` alanı istiyor. |
| F1-7 | **Ajansspor yapısal sayfaları kapalı** | `/lineup/`, `/mac/`, `/oyuncu/`, `/lig/` Disallow — **muhtemel 11 ve sakat/cezalı listesi alınamıyor.** Spec §3.1 bunları bekliyordu. |
| F1-8 | **Dil kalibrasyonu: yalnız ölçülen dil(ler)** | Ölçülmeyen her dil `production_enabled: false` kalır. Kapı bunu zorlar. |

`docs/HANDOFF.md`'yi Faz 1 durumuna göre yeniden yaz (Faz 0'ın biçimini koru:
*senin yapman gereken tek şey* → *canlı durum* → *ne üretti* → *kararlar* →
*kapının ölçmediği* → *sonraki faz* → *çalışma disiplini*).

- [ ] **Step 5: Final gate and commit**

```bash
DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d= -f2-)" ./verify.sh
git add docs/
git commit -m "docs: Faz 1 devri — ne ölçüldü, ne ÖLÇÜLMEDİ, Faz 2'ye devreden borç

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**Push asistan tarafından YAPILMAZ** — `outward_action_gate` `git_push`'u kapatıyor.
Push operatörün terminalinden gelir.

---

## Faz 1 kapısının ÖLÇMEYECEĞİ — Task 13'ün başlangıç listesi

Bu liste **plan yazılırken** biliniyordu. Task 13 onu tamamlar, silmez.

1. **Canlı tazelik kapıda ölçülmez.** `veri-sözleşmesi` adımı **kaydedilmiş fixture'lara**
   karşı koşar: ölçtüğü şey *ayrıştırıcı hâlâ beklenen şekli üretiyor mu*, *kaynak hâlâ
   taze mi* değil. Canlı tazelik yalnız toplayıcı turunda ölçülür ve o tur kapıda değildir.
2. **Fixture bayatlar.** Kaynak HTML'ini değiştirdiğinde fixture eskisini taşımaya devam eder
   ve kapı **yeşil kalır** — ta ki canlı tur `ContractViolation` verene kadar. `sources-audit.yml`
   robots'u ölçer, **sayfa şeklini ölçmez.**
3. **`source_observations` hash zincirsiz** (F1-5). Oran defteri kurcalanırsa dış çıpa gösterir;
   özellik girdisi kurcalanırsa hiçbir şey göstermez.
4. **Varlık eşleme doğruluğu için insan doğrusu yok.** Eşik altı eşleşmeler reddediliyor, ama
   eşik ÜSTÜNDEKİ bir eşleşmenin doğru olduğunu ölçen bir şey yok. Jev güvenle yanılırsa
   sessiz join hatası geri gelir — yalnız daha az sıklıkta.
5. **Elo parametreleri fit edilmedi** (F1-2). `k=20`, `home_advantage=65` iskeledir.
   Testler *tutarlılığı* ölçüyor (sıfır toplam, monotonluk), **doğruluğu değil.**
6. **Hava tahmini vs gerçekleşen hava** hiç karşılaştırılmadı. Maç saati tahmini `observed_at`
   damgalı ve sızıntısız, ama tahmin hatasının büyüklüğü bilinmiyor.
7. **`match_results` kapsamı ölçülmedi.** `/scores` yalnız `daysFrom<=3` veriyor; bir tur
   kaçarsa o maçların sonucu **kalıcı olarak** gelmez ve bunu raporlayan bir şey yok
   (Faz 0'ın "kaçan mühür" raporunun sonuç tarafındaki karşılığı **yazılmadı**).
8. **Eşzamanlı toplayıcı turları** ölçülmedi. `source_observations` defter kilidini kullanmıyor
   (zinciri yok, gerek de yok) ama iki turun aynı anda koşması hiç denenmedi.
9. **Faz 0'ın devrettiği ve Faz 1'in kapatmadığı** her madde: en az yetkili veritabanı rolü
   yok (DEFERRED §2.1), çıpa silme tespiti artık var ama **git geçmişine güveniyor**,
   eşzamanlı yazar güvenliği hâlâ yalnız sahte bağlantıyla kanıtlı (§5.2), `shellcheck`/
   `actionlint`/`yamllint` hâlâ yok (§5.1), coverage hâlâ ölçülmüyor (§5.3).

---

## Self-review — plan spec'e karşı

**Spec kapsaması.** §3.1 kaynak envanteri → Task 3 kayıt defteri (kapalı olanlar adıyla).
§3.2 kaynak politikası → Task 3, **kodla zorlanıyor**. §3.4 `leagues.yaml` → Task 5.
§5.3 Jev boru hattı rolleri → Task 11 (varlık eşleme); *kendini onaran ayrıştırıcı*, *kaynak
çelişkisi hakemi*, *haber kümeleme* **Faz 4'tedir** ve yol haritası da öyle diyor.
§5.4 çok dillilik → Task 12. §6.2 kapı → Task 3/4/12 adımları. §6.3 sızıntıya karşı önlemler →
her gözlemde `observed_at`, append-only, tek özellik kodu (Elo).
**Kapsanmayan ve kasıtlı:** §4 model mimarisi (Faz 3), §6.1 CLV ölçümü (Faz 2-3),
§1.4 tarihsel vs canlı kapanış kalibrasyonu (Faz 2).

**Yer tutucu taraması.** Kod gerektiren her adımda çalışan kod var. İki yerde **ölçüm
adımı** var, yer tutucu değil: Task 6 Step 2 (TFF tablo indeksi ölçülür, çünkü sayfa şeklini
kimse ezbere bilemez ve uydurmak yasaktır) ve Task 12 Step 1 (insan etiketleri — modele
ürettirmek ölçümü geçersiz kılar). İkisi de **çıktısı tanımlı, komutu verilmiş** adımlardır.

**Tip tutarlılığı.** `Observation` Task 4'te tanımlandı; Task 5-8 aynı alanları kullanıyor.
`Source` Task 3'te; `fetch_text`/`guard_path` imzaları Task 4-8 arasında sabit.
`ChoiceAnswer` Task 11'de; Task 12 aynı `ask_choice` protokolünü çağırıyor.
`normalise_team` **Task 4'ün `naming.py`'sinde** tanımlı; Task 6 ve Task 11 ikisi de oradan
import eder (Ruling R2 — önceden Task 6'nın içindeydi ve bu cross-worktree kırılganlıktı).
`MatchOutcome` (Task 9) Task 10'a **sızmaz**: Elo düz demet alır, paralel bağımsızlık korunur.

---

## Yürütme

**Plan tamamlandı.** İki yürütme seçeneği:

**1. Subagent-Driven (önerilen)** — task başına taze subagent, aralarda inceleme, hızlı döngü.
Paralel küme (Task 6-10) için `superpowers:using-git-worktrees` + beş eşzamanlı ajan.

**2. Inline Execution** — bu oturumda `superpowers:executing-plans` ile, checkpoint'lerle.

**Sıra pazarlığa kapalı:** Task 1→2→3→4→5 sıralıdır ve 5 birleşmeden paralel küme başlamaz.
Task 11 paralel kümenin tamamı birleştikten sonra; Task 12 Task 11'den sonra; Task 13 en son.
