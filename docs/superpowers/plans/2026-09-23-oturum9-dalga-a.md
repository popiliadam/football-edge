# Oturum 9 — Dalga A (kullanıcı girdisi gerekmeyen işler) — uygulama planı

**Kaynak:** `docs/HANDOFF.md` §0.6 Dalga A (1–4). **Spec:** `docs/superpowers/specs/2026-09-19-football-edge-design.md`
§3.2 ve §3.2.1 (R77b, 2026-09-23 kullanıcı kararı) · §5.4 (dil kalibrasyonu) · Faz 4 spec
`docs/superpowers/specs/2026-09-23-faz4-jev-sinyal-design.md`. **Risk:** K2 (T2/T3 kapı değişikliği ve toplayıcı
olduğu için tam inceleme + mutasyon).

## Global Constraints
- Kapı: `TMPDIR=$(mktemp -d) ./verify.sh > <log> 2>&1`; sonuç LOG DOSYASINDAN okunur. 10 PASS + `SKIP: zincir`
  adıyla (DB bağlıyken 11/11). Her commit'ten sonra tam kapı.
- Mutasyon kanıtları `PYTHONDONTWRITEBYTECODE=1` ile; her yeni test/kural en az bir mutasyonla kırmızı kanıtlanır,
  mutasyon geri alınır ve ağaç temiz bırakılır.
- HİÇBİR ŞEY SİLME (dosya, dal, satır). `git add -A` yok — yalnız açık yollar. Holdout AÇILMAZ. Append-only
  tablolara yazılmaz; DB yalnız okuma (`set transaction read only`).
- Commit biçimi `<type>: <açıklama>` + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Yorum/doküman dili Türkçe, çevredeki kodun yoğunluğu ve deyimiyle.
- Anahtar adları testlerde parçalardan kurulur (kapının secrets adımı testleri de tarar).

## Task 1: EN alan adı sıralaması → kaynak koşulları raporu
**Ölçüm yapıldı (controller, 2026-09-23, yerel ağ — ham GKG sunucusu yerelde açık; 429 veren DOC API'ydi):**
`step6_gdelt_en.py` + `doms.most_common(40)`; 28 GKG dosyası (son 7 günden 6 saatte bir, 672'nin 1/24'ü),
27.658 kayıt, başlığında lig takımı geçen 198, 93 alan adı (64'ü tek isabet), ilk 10 alan adı isabetlerin %45'i.
Raporun kontrol ettiği 25 alan adından yalnız `manchestereveningnews.co.uk` (1 isabet, "yasaklıyor"); 3 sessiz alan
adı (independent/standard/sportsmole) **0 isabet**. Ham çıktı: controller'ın verdiği `run.log` ve `doms.json`.

**Yapılacak:** (a) raporun "Açık sorular 1"ini kapatan yeni bölüm `## Alan adı sıralaması (2026-09-23 ölçümü)`:
yöntem, komut, sayılar, ilk 40 tablo, örneklem sınırı (1/24 örneklem → alan adı başına sayılar gürültülü; yalnız
başlığında takım adı geçenler; `AMBIG` listesi dışarıda). (b) İsabet sırasına göre ilk 15 alan adının koşul
sayfalarını raporun yöntemiyle oku (önce robots'a sor; robots kapalıysa okuma; dürüst UA; banner/form/Cloudflare
doğrulamasına dokunma; WebSearch yalnız sayfa bulmak için) ve raporun yayıncı tablosu biçiminde sınıfla
(yasaklıyor / sessiz / okunamadı + kanıt + "Çıkarım?"). (c) Özet §2'ye tek paragraf: izin listesi önerisinin
GDELT'teki gerçek kapsama etkisi (sessiz bulunan alan adlarının isabet payı). Karar kullanıcınındır — öneri dili
"karar girdisi". **Dosya:** yalnız `docs/reports/2026-09-23-kaynak-kosullari.md`.

## Task 2: Erişim yöntemi kapısını R77b'ye göre yeniden yaz (AYRI commit, adaptörden ÖNCE)
`tests/test_access_method_rule.py` (R80: Scrapling fetcher'ları ve parmak izi araçları bütünüyle yasak) R77b'ye
göre yeniden yazılır. Kapı gevşetmesi değil, kullanıcının politika kararı; ama eski kural yeni sınırlar olmadan
kalkmaz — **aynı commit** şunları taşır:
1. **Serbest kalanlar (R77b):** Scrapling `Fetcher`/`DynamicFetcher`/`StealthyFetcher` ve oturumları,
   `scrapling.fetchers`/`scrapling.engines`, `scrapling[fetchers]` ekstrası, `curl_cffi`, `tls-client`,
   `browserforge`, `camoufox`, `patchright`, `undetected-chromedriver`/`nodriver`/`zendriver`,
   `undetected-playwright`, `playwright-stealth`, `selenium-stealth`, `apify-fingerprint-datapoints` (parmak izi /
   tarayıcı taklidi).
2. **Yasak KALANLAR (R77b'nin değişmeyen sınırları; tabloda neden metniyle):** CAPTCHA/doğrulama çözücüler
   (`2captcha-python`, `anticaptchaofficial`, `capsolver`), Cloudflare atlatıcıları (`cloudscraper`, `cfscrape`),
   bot tespiti aşma çatısı `botasaurus`, IP döndürme (`requests-ip-rotator`), kimlik döndürme (`fake-useragent`).
   Mevcut A/B/C eksenleri (AST, kilit/pyproject, kurulum betikleri) bunlar için aynen sürer.
3. **Yeni kırmızı kurallar (her biri mutasyonla kırmızı kanıtlı):**
   - (a) `ProxyRotator` import/ad kullanımı ve herhangi bir çağrıda `proxy=`/`proxies=` anahtar argümanı yasak
     (`src/`, `scripts/`).
   - (b) `solve_cloudflare` anahtar argümanı ya da adı hiçbir değerle geçmez; kurulu Scrapling sürümünün
     fetcher imzalarında doğrulama/CAPTCHA çözmeye yönelik başka seçenek varsa (imzalardan ölçülür, raporda
     listelenir) aynı listeye girer.
   - (c) User-Agent'ta adı verilmiş bot yok: `useragent=`/`user_agent=` argümanları, `"User-Agent"` başlık
     sözlüğü anahtarları (büyük/küçük harf duyarsız) ve `config/sources.yaml`daki `user_agent` alanı
     `Googlebot`, `bingbot`, `ClaudeBot`, `GPTBot`, `CCBot`, `anthropic-ai`, `PerplexityBot`, `Google-Extended`,
     `Applebot`, `YandexBot`, `DuckDuckBot`, `Baiduspider` (büyük/küçük harf duyarsız) içeremez.
   - (d) **Tek geçit:** Scrapling fetcher/engine importu yalnız adaptör modülünde serbest
     (`src/football_edge/scrape.py`, Task 3 yazar); başka her `src/`/`scripts/` dosyasında kırmızı. Böylece
     "yalnız `sources.yaml` kaynağı", robots, crawl-delay, `Retry-After` ve 403/429 kuralları adaptörün davranış
     testlerinde tek yerde zorlanır.
4. Modül docstring'i R77b'ye göre yeniden yazılır (serbest/yasak/bilinen sınırlar).
5. Aynı commit belge notları: `docs/superpowers/specs/2026-09-22-faz2-olcumler-ve-kararlar.md` R79/R80 kaydına ve
   Faz 2 D17 "Scrapling benimsenmez" satırına "R77b ile değişti (2026-09-23)" notu (silme yok, not eklenir);
   `docs/DEFERRED.md` 11c satırına aynı not.
**Dosyalar:** `tests/test_access_method_rule.py`, o iki belge. `pyproject.toml`/`uv.lock` bu task'ta DEĞİŞMEZ.

## Task 3: Scrapling toplayıcı adaptörü + ilk hedef (TFF PFDK kararları, `enabled: false`)
Task 2'nin üstüne, aynı worktree'de.
1. Bağımlılık: `scrapling[fetchers]` (`uv add`), `uv.lock` güncellenir. Tarayıcı ikilileri (`scrapling install`,
   `playwright install`) CI'da KURULMAZ; testler ağsız ve tarayıcısız koşar (sahte fetcher / kayıtlı fixture).
2. `src/football_edge/scrape.py` — tek geçit. Sözleşme:
   - Girdi bir `sources.Source` (yalnız `config/sources.yaml`dan yüklenmiş; `access_basis: robots`); hedef URL'nin
     şeması+host'u `base_url` ile aynı olmalı, yol `declared_paths`ta olmalı (R7) — değilse istek ATILMADAN hata.
   - Her istekten önce robots: canlı robots.txt (projenin mevcut yolu, `collector._guarded_get`/`sources.allows`
     deseni) hem kaynağın `user_agent` belirtecine hem gönderilen gerçek User-Agent'a (tarayıcı kimliği → `*` grubu)
     göre sorulur; ikisinden biri kapalıysa istek atılmaz.
   - crawl-delay (kaynağın `crawl_delay_seconds` ve robots `Crawl-delay`inin büyüğü) ardışık istekler arasında
     uygulanır; `Retry-After` varsa uyulur; 403/429'da kaynak için tur DURUR — kimlik, başlık, yol ya da fetcher
     değiştirerek yeniden deneme YOK.
   - Yönlendirmeler otomatik izlenmez: her sıçrama aynı host + robots denetiminden geçer (mevcut `_guarded_get`
     davranışının karşılığı); başka host'a sıçrama hata.
   - Varsayılan fetcher `Fetcher` (curl_cffi, R77b varsayılanları açık: `impersonate`, `stealthy_headers`);
     `DynamicFetcher`/`StealthyFetcher` açık parametreyle seçilir; `solve_cloudflare` ve proxy hiç geçilmez
     (Task 2 kuralları bunu zorlar). Scrapling'in `Selector`ı ayrıştırmada kullanılabilir.
   - Davranış testleri (ağsız): sources.yaml dışı kaynak/host/yol reddi, robots reddi (iki UA ekseni ayrı),
     crawl-delay ve `Retry-After` beklemesi (saat enjekte edilir), 403 ve 429'da durma ve ikinci isteğin
     atılmaması, farklı host'a yönlendirme reddi. Her biri mutasyonla kırmızı kanıtlı.
3. İlk hedef — TFF PFDK kararları: `config/sources.yaml`da yeni kaynak `enabled: false` (ya da mevcut `tff`
   kaynağına yeni declared path — hangisinin doğru olduğu robots ve mevcut sözleşmeye göre ölçülüp raporda
   gerekçelenir), `config/robots/` anlık görüntüsü ve `robots_verified_at` kapının `kaynak-politikası` adımını
   geçmeli. Canlı sayfadan (adaptör üzerinden, robots izinliyse) bir fixture kaydedilir; windows-1254 çözümü ve
   ayrıştırıcı (karar tarihi, kulüp, kişi/rol, ceza türü/süresi — sayfada gerçekten olan alanlar ÖLÇÜLÜR) `contract`
   etiketli testle sabitlenir. Toplayıcı veritabanına YAZMAZ ve zamanlanmaz (yalnız ayrıştırma + fixture);
   yazma/zamanlama Plan 2'ye.
   - TFF koşulları otomatik erişimi yasaklıyorsa ya da robots kapalıysa hedef UYGULANMAZ: rapora kanıtla yazılır,
     task adaptörle biter (DONE_WITH_CONCERNS).
4. Ajansspor gövdesi, Fotomaç/A Spor, kulüp sayfaları bu task'ta YOK (17l ve §0.7/4 kullanıcı kararına bağlı).
**Dosyalar:** `pyproject.toml`, `uv.lock`, `src/football_edge/scrape.py`, yeni `src/football_edge/collectors/pfdk.py`
(ya da raporda gerekçelenen ad), `config/sources.yaml`, `config/robots/<id>.txt`, `tests/test_scrape*.py`,
`tests/test_pfdk*.py`, `tests/fixtures/...`, gerekirse `verify.sh`teki `EXPECTED_MIN_CONTRACT`.

## Task 4: Küçük borçlar (K2)
1. **DEFERRED 17n** — boş tur bekçisi (`collect.py` `EXIT_EMPTY_ROUND = 19`) test boşlukları: olay tam ufukta
   (`<=` sınırı), eksik alanlı ve liste olmayan `/events` yükü (KeyError/TypeError dalı) testle sabitlenir; gölge
   logunda `config.method` yerine sabit yöntem mutantının yaşaması kapatılır (fikstür yöntemi POWER dışı bir
   değerle çalıştırılıp logda o değer beklenir).
2. **DEFERRED 17h (17a bekçisi kaçışları, son inceleme M-4/M-5)** — `tests/test_jev_item_answers_readers.py`:
   tablo adı sabitiyle kurulan f-string (`f"… FROM {TABLE}"`), `%`/`.format`, `+` birleştirme ve büyük harf tablo
   adı yakalanır; `gates_from`a veren okuyucular için ayrı `GATES_READERS` kümesi. `psycopg.sql.Identifier`,
   `db/migrations` VIEW/fonksiyon ve `scripts/` taraması kapsam dışı kalırsa docstring'de "bilinen sınır" olarak
   yazılır.
3. **DEFERRED 16k-b** — `EloModelConfig.draw` `ordered` biçimde isteğe bağlı: bir sonraki model dosyası `draw`sız
   yazılabilir; mühürlü `config/model_faz3.yaml` (`ordered` + `draw: 0.26`) aynen okunmaya devam eder (test).
   `quadratic` biçimde davranış değişmez.
4. DEFERRED 17n, 17h, 16k satırlarına kapanış notu (tarih + commit).
**Dosyalar:** `tests/test_jev_item_answers_readers.py`, `collect.py` bekçisinin ve gölge logunun test dosyaları,
`src/football_edge/model/elo_model.py` ve testi, `docs/DEFERRED.md` (yalnız 16k/17h/17n satırları). Üretim
davranışı değişirse yalnız 16k-b için.

## Task 5: Dil kalibrasyonu ön-etiketleri — TR (Plan 2 T3 hazırlığı)
**Ölçüldü (controller, salt okuma):** `news_items` = 1.275 satır, hepsi `tr`/`ajansspor`. **EN haber YOK** →
EN ön-etiketi bu dalgada yapılamaz; EN kaynağı §0.7/4 kullanıcı kararına bağlı (Task 1 bulgusu: izin listesi
GDELT'te bugün 0 isabet).
1. `news_items`tan tohumlu (tohum yazılır) karıştırma; sırayla gidilir, başlığı bir kulübü (lig takımı) adıyla
   anmayanlar atlanır (sayısı yazılır) — 100 TR maddeye ulaşılır. Salt okuma bağlantısı.
2. Her madde: `data/calibration/README.md` biçimi `{"title","url","language":"tr","team","relevant"}` +
   `id` (news_items.id) + `rationale` (tek cümle) + `borderline` (bool). `team` kanonik ad (projenin takım adları
   yapılandırmasından). `relevant` tanımı README ve `calibration._INSTRUCTIONS` ile birebir.
3. Bağımsız ikinci etiket: ayrı bir ajan aynı 100 maddeyi ilk etiketleri GÖRMEDEN etiketler; uyuşmazlıklar ayrı
   listelenir (kullanıcının önce bakacağı yer).
4. Çıktı gitignored dizinde: `.superpowers/sdd/2026-09-23-oturum9-dalga-a/calibration/` →
   `tr.prelabel.jsonl`, `tr.second.jsonl`, `tr.review.md` (kullanıcının onaylayacağı tek dosya: tablo, uyuşmazlıklar
   önce, yöntem, tohum, atlanan sayısı). Ham metin depoya (izlenen dosyalara) GİRMEZ; Jev ÇAĞRILMAZ;
   `data/calibration/` değişmez.
**Dosyalar:** yalnız gitignored çıktı dizini.
