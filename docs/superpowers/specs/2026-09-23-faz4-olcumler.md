# Faz 4 — Ölçümler

Spec: `2026-09-23-faz4-jev-sinyal-design.md`. Plan 1: `docs/superpowers/plans/2026-09-23-faz4-plan1-dalga0-1.md`.
Her sayı altında yazan komutla ölçüldü; ölçülmeyen şey "ÖLÇÜLMEDİ" diye, nedeniyle yazılıdır. Plan 2 ve maliyet
ölçümü bu belgeye eklenir. Ham üçüncü taraf içeriği (başlık, gövde, sayfa metni) YOK — yalnız toplu sayı ve
≤ 1 cümlelik koşul alıntısı.

## T0c — arşiv ve kaynak spike'ı (2026-09-23, yerel macOS, Türkiye ağı, `feat/faz4-c` @ `858418b`)

**Ortak yöntem.** Ölçüm betikleri tek kullanımlıktır (oturum scratch dizininde, depoya girmedi); aşağıdaki
komutlar onları adıyla çağırır ve her birinin yaptığı iş satır içinde anlatılır. Her HTTP isteği projenin
`football_edge.collector._guarded_get`inden geçti: canlı `robots.txt` `protego` ile ayrıştırılıp
`football_edge.sources.allows` ile soruldu, crawl-delay uygulandı, yönlendirmenin her sıçraması ayrıca soruldu
(orijin dışı sıçrama `SourceBlocked`). Kimlik: `football-edge/0.1 (+https://github.com/popiliadam/football-edge)`.
Ad hoc kaynaklar `football_edge.sources.Source` ile kuruldu (`lib.py`: `adhoc`, `live_robots`, `ask`, `get`).
429'da yalnız bekleme (aynı kimlik, aynı yol); kimlik/IP/yol değiştirilmedi, hiçbir engel aşılmadı.

Girdiler (depoya girmedi):
- `ajansspor.csv` — controller'ın salt okuma dışa aktarımı (`source_observations`, `source_id='ajansspor'`,
  `entity_kind='news'`): **1.251 satır, 1.251 tekil URL, yayıncı iddiası 2026-09-04T11:58Z → 2026-09-23T06:46Z**
  (sha256 öneki `e02f59ffe1d14374`). Başlıklar yalnız bellekte eşleme için kullanıldı.
- `Matches.csv` — `xgabora/Club-Football-Match-Data` commit `25882a58a736daf7ece3781940eac17ae1117a66`
  (Faz 2 §2.1 ile aynı sürüm), ham GitHub'dan (45.370.018 B, sha256 `ef224cf2c252f07a…`). YALNIZ `Division`,
  `MatchDate`, `HomeTeam`, `AwayTeam` okunur; sonuç ve oran sütunları okunmaz (holdout sızıntısı yok).

```bash
# her komut worktree kökünden; S = oturum scratch dizini (…/scratchpad/t0c)
PYTHONPATH=$S PYTHONDONTWRITEBYTECODE=1 uv run python $S/<betik>.py [argümanlar]
```

### T0c/1 GDELT

| Ölçüm | Sonuç |
|---|---|
| Koşullar | `https://gdeltproject.org/about.html` (okundu 2026-09-23; `www.` kökene 301 — `_guarded_get` orijin dışı sıçramayı reddetti, kök doğrudan okundu): "all datasets released by the GDELT Project are available for unlimited and unrestricted use for any academic, commercial, or governmental use of any kind without fee." Atıf zorunlu (GDELT'e atıf + bağlantı). |
| robots — `api.gdeltproject.org` | **404** (robots yok → RFC 9309: her yol izinli). DOC API belgelenmiş, anahtarsız bir API → `access_basis: api_terms` (R8, Open-Meteo emsali) |
| robots — `gdeltproject.org` | 200, 33 B: `User-agent: *` / `Disallow: /data/` (bu host'un `/data/` yolu; ham dosyalar AYRI host'ta) |
| robots — `data.gdeltproject.org` | **404** → her yol izinli (`/gdeltv2/lastupdate.txt`, `masterfilelist.txt`, 15 dk'lık dosyalar) |
| TR / EN kapsamı | EN ana akış; TR "translation" akışında (GKG `TranslationInfo` = `srclc:tur`). Örnek: 2026-09-10'dan üç 15 dk'lık translation GKG dosyasında 8.467 kayıt, **483 Türkçe**, 40 Türkçe alan adı; `ajansspor.com` **0** |
| DOC 2.0 API arama derinliği | Belge: 2017 "rolling window of the last 3 months"; 2018-01-08 güncellemesi "up to the past year of coverage". **Ölçüldü: belgeden derin** — `"Fenerbahce" "Galatasaray" (sourcelang:turkish OR sourcelang:english)`, `2019-12-15 → 2019-12-22`: 200, **250 kayıt (tavan)**, hepsi Turkish, `seendate` 2019-12-15T04:00Z → 2019-12-21T22:45Z. E bölgesinin başı aranabilir |
| DOC 2.0 API erişimi (yerel ağ) | **429** — "Please limit requests to one every 5 seconds…". 14:59–15:53 arası **2 başarılı / 19 istek** (10 sn, 90 sn aralık ve 20 dk sessizlik sonrası tek istek dahil; başarılar 15:00:59 ve 15:51:03). `Retry-After` yok. Engel aşılmadı. Bu hızla (~1 yanıt / 25 dk) örneklem koşulamaz |
| Ham dosya erişimi | `data.gdeltproject.org` sorunsuz (200). Güncel 15 dk'lık boyutlar: export 85 KB, mentions 135 KB, GKG 5,2 MB; translation GKG 13,9 MB |

Komutlar: `step1_2_robots.py` (yedi host'un canlı robots'u + `allows`; T0c/2 de aynı çıktıdan), koşul sayfaları
WebFetch ile okundu;
`gkg_domains.py 20260910090000 20260910180000 20260910200000`; DOC API: `gdelt.py` (`artlist`, 10 sn aralık, 429'da
90 sn × 3), `probe_depth.py` (20 dk bekle, 30 sn aralık), `probe_sparse.py` (90 sn aralık, 8 deneme; 7.'si 200 verdi).

### T0c/2 CC-NEWS (Common Crawl) ve öbür açık arşivler

| Ölçüm | Sonuç |
|---|---|
| Koşullar | `https://commoncrawl.org/terms-of-use` (LAST UPDATED 2024-03-07, okundu 2026-09-23): lisans "limited, non-assignable, non-transferable, non-sublicensable, non-exclusive"; ticari kullanım açıkça izinli DEĞİL — "CC strongly recommends that you obtain the advice of legal counsel before making any use, including commercial use" |
| Erişim yolu | `s3://commoncrawl/crawl-data/CC-NEWS/yyyy/mm/warc.paths.gz` ya da `https://data.commoncrawl.org/crawl-data/CC-NEWS/yyyy/mm/warc.paths.gz`; WARC'lar ~1 GB; **CC-NEWS için URL/anahtar kelime dizini YOK** (CDX yalnız CC-MAIN) |
| robots — `data.commoncrawl.org` | 200, 25 B: `User-Agent: *` / `Disallow: /` → `allows()` **False** (CC-NEWS yolları dahil) |
| robots — `index.commoncrawl.org` | 200, 181 B: `Disallow: /` + yalnız `/$`, `/index.html$`, `/collinfo.json$` … izinli → CDX sorgu uçları (`/CC-MAIN-…-index`) **False** |
| Sonuç | **ELENDİ**: robots kodla soruldu ve kapattı; `api_terms` sayılsa bile ToS ticari kullanım için temiz değil. Kapsam ve damga ÖLÇÜLMEDİ (istek atılmadı) |
| Internet Archive (Wayback) | `web.archive.org/robots.txt` 404; koşullar `archive.org/about/terms.php` (sayfa JS ile çiziliyor, metni arama sonucundan doğrulandı): erişim "for scholarship and research purposes only" → **ELENDİ** (ticari değil) |
| Google News RSS | **ELENDİ** — `config/sources.yaml` `googlenews` notu: feed'in kendi `<copyright>`ı "personal, non-commercial use" |

### T0c/3 Kapsam — lig × sezon

**ÖLÇÜLEMEDİ.** Tek temiz arşiv GDELT; lig-sezon başına 50 maçlık örneklemi (tohum `20260923`) koşacak DOC API
2019'a iniyor (T0c/1) ama yerel ağdan ~1 yanıt / 25 dk veriyor: 2.800 sorgu (holdout yalnız: 400) bu ağda
koşulamaz. DOC API'siz tek yol ham GKG dosyalarıdır: maç başına −7..0 penceresi 768 dosya × ~5 MB (EN) + 768 ×
~14 MB (TR) ≈ 14 GB; bütçe dışı (BigQuery ücretli + hesap gerektirir, yasak). Runner'da tek kullanımlık dalla
koşulabilir (6 sn aralıkla ~4,7 saat) — bu görevde push yok, ADIYLA: ölçülmedi.

Hazırlanan (koşulamayan) örneklem: `step3_coverage.py 50 50` — 8 lig (`E0 SP1 I1 D1 F1 T1 N1 B1`) × 7 sezon ×
50 maç, `random.Random(20260923)`, pencere `[gün−7 00:00Z, gün 12:00Z)`, sorgu `"<ev>" "<dep>" (sourcelang:turkish
OR sourcelang:english)`, iki ölçü (≥ 1 kayıt; başlıkta takım adı). Evren (maç sayısı, `Matches.csv`): holdout 2025
E0 380 · SP1 380 · I1 380 · D1 306 · F1 306 · T1 306 · N1 306 · B1 311.

Dolaylı işaret (kapsam ölçümü DEĞİL): GDELT'in güncel Türkçe hacmi düşük — üç translation GKG örneğinde 15 dk
başına ~161 Türkçe kayıt, `ajansspor.com` 0; ajansspor'un mentions akışında 19 günde bulunan URL sayısı T0c/4'te.

### T0c/4 Yayın zamanı — arşiv damgası ↔ yayıncı iddiası (spec §3/2a, R172)

Yol: DOC API `domain:ajansspor.com` 429 (T0c/1) → ham GDELT 2.0 **mentions** dosyaları (ana + translation, 15
dk, 2026-09-03 → 2026-09-23, gün başına 2 × 96 dosya). Dosyalar bellekte açıldı, diske yazılmadı; yalnız
`MentionSourceName` `ajansspor.com` olan satırların (URL, `MentionTimeDate`) çifti tutuldu. Eşleme URL ile
(şema/`www.`/sorgu/sondaki `/` atılmış); fark = ilk `MentionTimeDate` − `publisher_claim`.

| Ölçüm | Sonuç |
|---|---|
| Taranan | 3.951 dosya (20 gün × 192 + 2026-09-23'ün henüz yayımlanmamış 81 dilimi eksik), 313,6 MB, 404 dışında hata yok |
| ajansspor satırı / tekil URL | 26 mention satırı (hepsi translation akışı) / **16 tekil URL** — 19 günde; 2'si CSV penceresi dışında |
| Yayıncı iddiası (CSV) | 1.251 |
| **Eşleşen** | **14** (hepsi URL ile; başlık eşlemesine gerek kalmadı) |
| **Eşleşmeyen pay** | **%98,9** |
| Fark (arşiv − iddia), saat | min 3,85 · **medyan 6,31** · **p95 7,24** · **p99 7,41** (n=14'te p99 = en büyük) |
| Negatif fark payı | **0** (arşiv hiçbir zaman iddiadan önce değil) |
| Eşik \|fark\| p99 ≤ 24 sa | tutuyor — ama n=14 (%1,1) ile; fark sistematik olarak +4…+7 saat (translation akışı gecikmesi) |

Komut: `step4_mentions.py <YYYYMMDD> 1 mentions_all.jsonl` (her gün için), sonra `S=$S python3 step4_stats.py`.
Sınır: mentions yalnız CAMEO olayı çıkarılan makaleleri taşır; GKG (tüm makaleler) ~14 MB/15 dk olduğu için 19
gün taranmadı — üç GKG örneğinde de ajansspor 0 (T0c/1).

### T0c/5 Haber gövdesi (ajansspor)

| Ölçüm | Sonuç |
|---|---|
| Canlı robots | 200, 1.411 B; `config/robots/ajansspor.txt` anlık görüntüsüyle **birebir aynı** |
| Makale yolları | CSV'deki 1.251 URL'nin hepsi `/haber/…`; `allows()` **1.251 / 1.251 izinli** |
| Content-Signal | `ai-train=no, search=yes, ai-input=yes` — Jev'e girdi olarak vermek `ai-input`; eğitim yok |
| Örnek sayfa (tohum 20260923, 1 istek) | 200, `text/html; charset=utf-8`, 126 KB; `<h1>` 1, `<article>` 1; JSON-LD `NewsArticle` var, `articleBody` alanı var (örnekte 1.414 karakter), `datePublished` ve `dateModified` var; meta robots `index, follow, max-snippet:-1`; `X-Robots-Tag` yok |
| Seçici | başlık: `h1` ya da JSON-LD `headline`; gövde: JSON-LD `NewsArticle.articleBody` (düz metin, sınıf adları Tailwind üretimi — kırılgan, kullanılmaz) |
| ToS | `/uyelik-sozlesmesi` ve `/kvkk` robots'ta `Disallow` — okunmadı (istek atılmadı); ÖLÇÜLMEDİ |

Komut: `step5_body.py` (canlı robots + 1.251 yolun `allows` sonucu + tohumlu tek sayfanın yapı sayımları; içerik
basılmadı ve yazılmadı).

### T0c/6 EN canlı kaynak adayları

| Aday | Biçim | robots (`allows`) | ToS (okundu 2026-09-23, ≤ 1 cümle) | Son 7 gün, lig başına başlık (E0/SP1/I1/D1/F1/T1/N1/B1) | Karar |
|---|---|---|---|---|---|
| BBC Sport | RSS (`feeds.bbci.co.uk/sport/football/…/rss.xml`, 3 feed, `pubDate` %100) | izinli | `bbc.co.uk/usingthebbc/terms-of-use/` §15: "You're not allowed to pluck metadata from our content or RSS feeds." (§8: yapay zekâ / bilgisayarla analiz izne tabi) | 31/0/0/0/0/0/0/0 | **ELENDİ** (ToS) |
| The Guardian | RSS (`/football/…/rss`, 7 feed; TR ve BE feed'i 404) + Open Platform API (anahtar ister, hesap açılmadı) | RSS izinli; API host robots 401 | OP şartları §(g) ve site ToS: makine öğrenmesi/yapay zekâ ve "text and data aggregation, analysis or mining" amaçlı kullanım yasak; site kullanımı yalnız kişisel ve ticari olmayan | 18/7/1/2/2/0/0/0 | **ELENDİ** (ToS) |
| ESPN | RSS (`/espn/rss/soccer/news`, 20 öğe) | izinli | `disneytermsofuse.com/english/` x.: "robot, spider, script, or other automated means", AI Tool ve veri madenciliği dahil, yasak | 4/3/0/2/0/0/0/0 | **ELENDİ** (ToS) |
| Sky Sports | RSS (`/rss/12040`, `/rss/11095`) | izinli | koşullar `sky.com/help/articles/skycom-terms-and-conditions`e yönleniyor, sayfa JS ile çiziliyor → OKUNAMADI; temiz sayılamaz | 9/0/0/2/0/0/0/0 | **ELENDİ** (ToS doğrulanamadı) |
| **GDELT DOC 2.0 API** (+ ham 15 dk dosyalar) | JSON API (`mode=artlist`: url, title, `seendate`, domain, language) ve GKG | API 404 → izinli (`api_terms`); data host izinli | T0c/1: ticari dahil sınırsız, atıf zorunlu | GKG örneği ×24 ≈ 3.696/432/72/192/312/24/72/48 | **SEÇİLDİ** (tek temiz ToS) — koşullu, aşağıda |

EN kapsam komutları: `step6_leagues.py` (dört RSS adayı, son 7 gün, takım adı eşleşmesi — 2025-07-01 sonrası
`Matches.csv` takımları, `names.py` arama adları); `step6_gdelt_en.py` (son 7 günden 6 saatte bir 1 GKG dosyası =
28/672, `<PAGE_TITLE>` 2026-07-01 sonrası `Matches.csv` takımlarının adıyla eşlenir, ×24 ile haftalığa ölçeklenir; belirsiz tek kelimelik adlar — Nice,
Lens, Como, Brest, Angers, Genoa, Roma, Metz, Leeds, Nantes, Venezia, Twente — dışarıda; şehir adıyla eşleşen
takımlar yüzünden E0 üst sınırdır). 28 dosyada 27.658 kayıt, 198'i başlıkta bir lig takımı taşıyor, 93 alan adı.

GDELT'in koşulları: (1) DOC API yerel ağdan 429 → canlı toplayıcı runner'da koşmalı ve runner'dan erişim
ÖLÇÜLMEDİ; (2) GDELT başlıkları üçüncü taraf yayıncılara ait — ToS'u yapay zekâ kullanımını açıkça yasaklayan alan
adları (bu ölçümde: `theguardian.com`, `bbc.co.uk`/`bbc.com`, `espn.com`) toplayıcıda dışlanmalı (kullanıcı kararı).

### T0c ölçülmeyenler

- Lig × sezon kapsam payı (T0c/3) — DOC API yerel ağdan 429 (~1 yanıt / 25 dk); ham GKG bütçe dışı.
- GDELT DOC API'nin runner'dan erişimi — bu görevde push yok; runner'da geçici dalla ölçülebilir. (Derinlik ölçüldü: 2019-12 aranabiliyor.)
- GKG (tüm makaleler) üzerinden ajansspor eşleşmesi (19 gün × ~1,3 GB/gün).
- ajansspor ToS (robots'ta `Disallow`, okunmadı).
- Sky Sports ToS metni.
- §3/2b (yayıncı iddiası ↔ `first_seen_at`) — Plan 2'de, Task 9'dan ≥ 2 hafta sonra.
