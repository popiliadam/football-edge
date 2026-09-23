# Kaynak koşulları — GDELT, EN yayıncılar, ajansspor, football-data (2026-09-23)

**Durum:** karar girdisi (HANDOFF §0.2/5, DEFERRED 17l) · **Yöntem:** salt okuma araştırması (oturum 8, araştırma
ajanı); hukuki görüş değildir · **Karar kullanıcınındır.**

## Özet
1. **GDELT:** kendi veri setleri akademik/ticari/resmî her kullanıma ücretsiz ve kısıtsız açık; tek şart GDELT'e
   atıf + gdeltproject.org bağlantısı. Başlıkların (yayıncı metni) hakları hakkında hüküm yok. DOC API sınırı 429
   gövdesinde yazılı: 5 sn'de bir istek. **Öneri:** GDELT'le devam; atıf `sources.yaml` notuna + README'ye; istek
   aralığı ≥ 6 sn, 429'da ısrar yok.
2. **EN yayıncılar:** 25 alan adından 19'u yapay zekâ kullanımını/TDM'yi/otomatik toplamayı açıkça yasaklıyor,
   3'ü sessiz (independent.co.uk, standard.co.uk, sportsmole.co.uk), 5'i okunamadı. "Yasaklayanı dışla" politikası
   büyük İngiliz futbol yayıncılarının neredeyse hepsini düşürür. **Öneri:** kara liste yerine **izin listesi**
   (okunmuş ve sessiz bulunmuş alan adları; bilinmeyen varsayılan dışarıda).

   **GDELT'teki gerçek kapsam (2026-09-23 ölçümü, §Alan adı sıralaması):** yukarıdaki 3 sessiz alan adı EN GKG
   örnekleminde **0 isabet** — bugünkü izin listesi lig takımı geçen başlıkların hiçbirini geçirmez. Sıralamanın
   ilk 15 alan adı okununca yalnız dailytrust.com ve el-balad.com sessiz çıktı: **6/198 (%3,0)**. punchng.com
   okunamadı (koşul sayfası bulunamadı; 3, %1,5). Kalan 12 alan adı (96 isabet, %48,5) yasaklıyor: 37'sinde
   (%18,7) yapay zekâ maddesi var; aol.co.uk ve thehardtackle.com (45, %22,7) otomatik toplamayı **ve** ticari
   yeniden kullanımı yasaklıyor; Newsquest'in 3 bölge sitesi (14, %7,1) yapay zekâ/otomasyon demiyor ama izinsiz
   saklamayı, veritabanı kurmayı ve ticari kullanımı yasaklıyor. İlk 15 dışındaki 92 isabet (%46,5) bilinmiyor
   (MEN'in 1 isabeti eski tabloda yasaklıyor), izin listesinde varsayılan dışarıda. "Sessiz", ticari kullanım izni
   demek değildir: el-balad.com da izinsiz ticari kullanımı yasaklıyor. **Karar girdisi:** okunmuş-sessiz izin
   listesi EN akışın ~%3'ünü tutar. Yapay zekâ maddesi olmayan ama otomatik toplama ve/veya ticari kullanım/
   veritabanı kısıtı taşıyan alan adlarını (aol, thehardtackle, Newsquest) ayrı sınıf sayıp listeye almak
   **65/198 (%32,8)** eder, Punch dahil değil (Punch ile 68/198, %34,3). Bu ayrım iki soruya bağlıdır:
   §Açık sorular 2 (ToS bizi bağlar mı; başlık/URL GDELT'ten gelir, siteye istek yok — bu yalnız otomatik erişim
   kaygısını kaldırır) ve başlıkların ticari bir üründe saklanıp kullanılmasının bu ticari/veritabanı kayıtlarına
   girip girmediği. Örneklem 1/24; alan adı başına sayılar gürültülü.
3. **ajansspor (17l):** tek sözleşme metni `/uyelik-sozlesmesi` robots'ta `Disallow` → okunmadı. Okunabilen yasal
   sayfalarda otomatik okuma/yapay zekâ maddesi yok. robots.txt `Content-Signal: ai-input=yes, ai-train=no`.
   **Öneri:** 17l'yi bu kanıtla kapat (Jev'e gövde göndermek girdi kullanımıdır, eğitim değil) ya da yayıncıya
   sor (dış iletişim — kullanıcı onayı).
4. **football-data:** `disclaimer.php`/`notes.txt` (2026-09-22 runner'dan okundu, Faz 2 ölçümleri §2.4) yalnız
   sorumluluk reddi; lisans/ticari/yapay zekâ maddesi yok. Yeni robots blokları yalnız adı verilmiş yapay zekâ
   botları. **Öneri:** duruş sürer; veri Jev'e verilmez; ticari lansmandan önce yazılı izin (spec §10/2).

## GDELT
| Konu | Bulgu | Kaynak |
|---|---|---|
| Ticari/yapay zekâ | Kendi veri setleri için kısıtsız; üçüncü taraf içeriği hakkında madde yok | gdeltproject.org/about.html |
| Atıf | Her kullanımda GDELT'e atıf + bağlantı | aynı |
| Hız | 429 gövdesi: 5 sn'de bir istek; yazılı kabul edilebilir kullanım metni yok | 429 yanıtı; blog.gdeltproject.org (DOC 2.0 duyurusu, 2024 kota yazısı) |
| robots | `api.gdeltproject.org/robots.txt` 404 | ölçüm |

GDELT'in izni kendi ürettiği alanları kapsar (`seendate`, alan adı, dil, URL); `title` yayıncının metnidir — GDELT
hak vermez, yasak da koymaz.

## Yayıncı tablosu (aday liste — frekans sıralaması ÖLÇÜLMEDİ)
Bu 25 alan adı sıralama ölçülmeden seçildi; GDELT örnekleminde isabeti olan yalnız manchestereveningnews.co.uk (1).
Sıralamaya göre ilk 15 alan adı: §Alan adı sıralaması.

"Çıkarım?": yasak içeriği bir yapay zekâya verip yanıt almayı (bizim Jev kullanımımız) da kapsıyor mu.
"robots": altı yapay zekâ botundan (GPTBot, ClaudeBot, CCBot, Google-Extended, PerplexityBot, anthropic-ai) kaçı
bir makale yolunda engelli (bilgi amaçlı; biz bu sitelere istek atmıyoruz, başlık/URL GDELT'ten gelir).

| Alan adı | Sınıf | Kanıt (koşul sayfası, okunduğu sürüm) | Çıkarım? | robots |
|---|---|---|---|---|
| theguardian.com | yasaklıyor | /help/terms-of-service: ML/yapay zekâ amaçları, TDM ve ticari kullanım | Evet | 4/6 |
| bbc.co.uk / bbc.com | yasaklıyor | /usingthebbc/terms/can-i-use-bbc-content/ (28.07.2025): yapay zekâ eğitimi ve bilgisayarla analiz izne tabi | Evet | 6/6 |
| espn.com | yasaklıyor | disneytermsofuse.com (24.05.2024): içeriği yapay zekâya prompt/ince ayar/eğitim için vermek | Evet | 4/6 |
| skysports.com | yasaklıyor | sky.com T&C (10.10.2025): bot/kazıma/birleştirme; yapay zekâ eğitimi | Kısmen | 2/6 |
| dailymail.co.uk | yasaklıyor | /terms (29.07.2025): ML/yapay zekâ eğitimi, TDM hakkı saklı | Evet | 6/6 |
| mirror / express / football.london (Reach) | yasaklıyor | /terms-conditions (27.11.2025): içerikle yapay zekâ eğitmek/geliştirmek | Kısmen | 5/6 |
| manchestereveningnews, liverpoolecho | yasaklıyor (çıkarım) | aynı Reach metni varsayıldı, tek tek okunmadı | Kısmen | 5/6 |
| thesun.co.uk | yasaklıyor | koşullar robots gereği okunmadı; robots yorumu lisanssız LLM kullanımına izin vermiyor | Belirsiz | izin listesi modeli |
| telegraph.co.uk | yasaklıyor | ticari olmayan kullanım yapay zekâ eğitimini kapsamaz; robotla veri çıkarma yasak | Kısmen | 5/6 |
| apnews.com | yasaklıyor | /termsofservice (21.01.2026): ML/yapay zekâyı eğitmek/bilgilendirmek; otomatik erişim | Evet | 5/6 |
| reuters.com | yasaklıyor | koşullar robots gereği okunmadı; robots bildirimi izinsiz otomatik toplamayı yasaklar | Belirsiz | izin listesi modeli |
| nytimes.com (The Athletic) | yasaklıyor | ToS (20.01.2026): eğitim, grounding, RAG; DSM Md. 4 TDM itirazı | Evet | 6/6 |
| goal.com | yasaklıyor | /en/legal/terms-conditions (Mayıs 2026): TDM ve kazıma yok, 2019/790 Md. 4(3) hakkı saklı | Evet | 0/6 |
| 90min.com | yasaklıyor (otomatik toplama) | minutegroup.com T&C (24.08.2026): bot/crawler; yapay zekâ maddesi yok | Hayır | 0/6 |
| football365 / teamtalk | yasaklıyor | /terms-conditions (29.05.2025): içeriği yapay zekâya vermek/beslemek/doğrulamak | Evet | 0/6 |
| irishtimes.com | yasaklıyor | lisanssız kazıma, otomatik özetleme, birleştirme | Evet | 1/6 |
| cbssports.com | yasaklıyor (otomatik toplama) | viacomcbs.legal ToS (27.05.2025): izinsiz kazıma/veri madenciliği | Hayır | 1/6 |
| foxsports.com | yasaklıyor | /terms-of-use (21.08.2025): yapay zekâ/LLM eğitimi | Kısmen | 0/6 |
| sports.yahoo.com | yasaklıyor (otomatik toplama) | legal.yahoo.com ToS (04.08.2026): robot/kazıyıcı | Hayır | 6/6 |
| **independent.co.uk** | **sessiz** | /service/user-policies-a6184151.html: yapay zekâ maddesi yok; URL + başlık alıntısıyla bağlantıya izin | — | 0/6 |
| **standard.co.uk** | **sessiz** | /service/terms-of-use-6902768.html: Independent ile aynı metin | — | 0/6 |
| **sportsmole.co.uk** | **sessiz** | terms-and-conditions_467 (12.05.2026): yapay zekâ maddesi yok; kişisel/ticari olmayan kullanım | — | 0/6 |
| independent.ie | okunamadı | Mediahuis 403 (Cloudflare doğrulaması aşılmadı) | — | 6/6 |
| talksport, si.com, nbcsports | okunamadı | bağlantı sıfırlandı | — | — |
| eurosport.com | okunamadı | koşullar yalnız PDF | — | 0/6 |

Robots'taki yapay zekâ blokları ToS'un iyi bir göstergesi değil: Goal, 90min, F365, Fox robots'ta engel koymuyor
ama ToS'ta yasaklıyor.

## Alan adı sıralaması (2026-09-23 ölçümü)
**Yöntem.** GDELT GKG 2.1 ana (İngilizce) akış; son 7 günden 6 saatte bir 15 dakikalık dosya — 28 dosya
(2026-09-16 00:00 → 2026-09-22 18:00 UTC), haftanın 672 dosyasının 1/24'ü. Kaynak `data.gdeltproject.org`
(robots canlı soruldu, 1 sn aralık; 429 veren DOC API'ydi, ham GKG sunucusu yerel ağdan açık). Her kaydın
`<PAGE_TITLE>`'ı bellekte normalize edilip 8 ligin takım adlarıyla eşlendi (takım adları için `Matches.csv`);
alan adı GKG'nin kaynak alanından sayıldı, yalnız sayılar yazıldı. Belirsiz adlar dışarıda: `AMBIG` = nice, lens,
como, inter, milan, brest, angers, genoa, roma, metz, leeds, nantes, venezia, twente.
**Komut** (controller koştu): `PYTHONPATH=.superpowers/sdd/2026-09-23-faz4-plan1-dalga0-1/t0c DOMS_OUT=… uv run
python step6_doms.py` (`step6_gdelt_en.py` + alan adı sayacı; `doms.most_common(40)` + tam sayım `doms.json`).
Ham çıktı: `.superpowers/sdd/2026-09-23-oturum9-dalga-a/a1/run.log`, `doms.json`.

**Sayılar.** 27.658 kayıt; başlığında lig takımı geçen **198**; **93 alan adı** (64'ü tek isabet). İlk 10 alan adı
isabetlerin %45'i (90/198), ilk 15'i %53'ü (105/198). Lig kırılımı (örneklem): E0 154, SP1 18, F1 13, D1 8, I1 3,
N1 3, B1 2, T1 1 (toplam 202: bir başlık birden fazla ligin takımını içerirse her lige sayılır, kayıt bir kez) —
EN akış neredeyse yalnız Premier League.

| Sıra | İsabet | Alan adları |
|---|---|---|
| 1 | 35 | aol.co.uk |
| 2 | 14 | caughtoffside.com |
| 3 | 10 | thehardtackle.com |
| 4 | 8 | fourfourtwo.com |
| 5 | 6 | bournemouthecho.co.uk |
| 6 | 5 | ipswichstar.co.uk |
| 7–16 | 3 | barcablaugranes.com, braidwoodtimes.com.au, chelmsfordcitynews.co.uk, dailytrust.com, el-balad.com, greatlakesadvocate.com.au, justarsenal.com, punchng.com, sbnation.com, toffeeweb.com |
| 17–29 | 2 | aawsat.com, arsenalnews.co.uk, batemansbaypost.com.au, blueprint.ng, brightonandhovenews.org, canberratimes.com.au, crookwellgazette.com.au, dailymail.com, foot01.com, gazette-news.co.uk, messengernewspapers.co.uk, nzcity.co.nz, promptnewsonline.com |
| 30–40 | 1 | superbike-news.co.uk, thenationonlineng.net, k923orlando.com, yorkpress.co.uk, london-now.co.uk, merimbulanewsweekly.com.au, northcountrypublicradio.org, theleader.com.au, townandcountrymag.com, denbighshirefreepress.co.uk, newcastleherald.com.au |

1–29'da eşitlikte sıra alfabetik. 30–40 bu kurala uymaz: 64 tek isabetli alan adından `most_common(40)`'ın ilk
görülme sırasıyla (deterministik, alfabetik değil) seçtiği 11'i; alfabetik olsaydı balls.ie, bignewsnetwork.com …
ile başlardı.

**Örneklem sınırı.** 1/24 örneklem: alan adı başına sayılar gürültülü (3 isabet ≈ haftada ~70 ± geniş aralık);
3'lü ve 2'li gruplar içindeki sıra anlamsız. Yalnız **başlığında** takım adı geçen kayıtlar sayıldı; `AMBIG`
adlarının (ör. Inter, Milan, Leeds) başlıkları ve takım adı geçmeyen futbol haberleri dışarıda. dailymail.com (2)
dailymail.co.uk'tan ayrı sayıldı; koşulları okunmadı (aynı şirket, büyük olasılıkla aynı metin).

### İlk 15 alan adının koşulları
Yöntem yukarıdaki tabloyla aynı: her sitede önce canlı robots.txt soruldu (dürüst UA; bir istek dışında hepsi
projenin `_guarded_get`i, bkz. §Yöntem);
banner/form/doğrulamaya dokunulmadı; WebSearch yalnız thehardtackle ve punchng koşul sayfasını aramak için. Aynı
sahipli siteler (footer'daki koşul bağlantısı aynı metne gidiyor) tek satırda. "robots": altı yapay zekâ botundan
kaçı `/news/2026/09/22/example-football-article` yolunda engelli.

| Alan adı (isabet) | Sınıf | Kanıt (koşul sayfası, okunduğu sürüm) | Çıkarım? | robots |
|---|---|---|---|---|
| aol.co.uk (35) | yasaklıyor (otomatik toplama, ticari yeniden kullanım) | legal.aol.com/terms (en-GB, 24.11.2025): robot/kazıyıcı/veri madenciliği "her amaçla" izinsiz yok; hizmetin "herhangi bir bölümünü" ticari amaçla yeniden kullanmak yok; içerikten rakip/ikame "birleştirilmiş veri kaynağı" kurmak yok; yapay zekâ maddesi yalnız AOL'un kendi özellikleri. Sahip **AOL Media LLC** (Yahoo değil) | Hayır | 6/6 |
| caughtoffside.com (14), justarsenal.com (3) | yasaklıyor | Rocket Sports ToS v1.0 (08.06.2026) + bağlı "Search Only Terms Contract" (m4ow.uk/socw/2.txt): yalnız arama dizini; md. 7.3 eğitim, embedding, veri seti, "yapay zekâ üretimini zenginleştirme" yasak; lisanssız erişime ürün başına £500 "erişim ücreti" | Evet | 0/6 |
| thehardtackle.com (10) | yasaklıyor (otomatik toplama, ticari kullanım) | /terms-of-service/ (30.11.2025): izinsiz kazıma/otomatik erişim ve bot yok; lisans yalnız kişisel, ticari olmayan kullanım ("Use content for commercial purposes without prior written consent" lisans dışı); md. 4.3 "No Commercial Use": yazılı izinsiz çoğaltma/dağıtım yok | Hayır | 0/6 |
| fourfourtwo.com (8) | yasaklıyor | futureplc.com/terms-and-conditions-uk/ (07.04.2025): TDM ve kazıma "her amaçla" yok, yapay zekâ eğitimi dahil; 2019/790 Md. 4(3) hakkı saklı; ticari kullanım lisansa bağlı | Evet | 0/6 |
| bournemouthecho.co.uk (6), ipswichstar.co.uk (5), chelmsfordcitynews.co.uk (3) | yasaklıyor (veritabanı/ticari) | newsquest.co.uk/legal/terms-conditions/ (15.12.2025, sürüm toa_2025.09.29; üç sitenin footer'ı /legal/'e gider): yapay zekâ/TDM/otomatik toplama maddesi yok, ama "Rights": yalnız özel amaç, "not for any advertising or other commercial purpose"; yazılı izinsiz "copy, store … create a database … from downloaded materials" yok; siteyi başka elektronik erişim sisteminde saklamak izne bağlı. /legal/ai-notice/ (17.12.2025) yalnız kendi yapay zekâ kullanımları | Hayır (yapay zekâ sözü yok; veritabanı/ticari kaydı geniş) | 5/6 |
| barcablaugranes.com (3), sbnation.com (3) | yasaklıyor | pmc.com/terms-of-use (21.08.2026; SB Nation Penske Media'ya bağlı): yapay zekâ araçları/bot ile erişim-kazıma; içeriği yapay zekâyı eğitmek **veya grounding** için kullanmak | Evet | 5/6 |
| braidwoodtimes.com.au (3), greatlakesadvocate.com.au (3) | yasaklıyor | /conditions-of-use/ (Kasım 2022): robot/spider, otomatik betik yok; robots.txt ACM beyanı (Nisan 2026): içerik **ve metaveri** her türlü ML/yapay zekâ amacıyla, işletim dahil, yasak | Evet | 6/6 |
| **dailytrust.com (3)** | **sessiz** | /terms-of-use (tarih görünmüyor): yalnız yorum/paylaşım kuralları; yeniden kullanım, otomatik erişim, yapay zekâ maddesi yok | — | 0/6 |
| **el-balad.com (3)** | **sessiz** | /terms (tarih görünmüyor): bağlantı paylaşmak ve atıfla referans izinli; izinsiz kopyalama/yeniden yayın ve **izinsiz ticari kullanım yok** (sessiz ≠ ticari kullanım izni) | — | 0/6 |
| punchng.com (3) | okunamadı (koşul sayfası bulunamadı) | /privacy-policy/ "the terms of use found on the site"a atıf yapıyor, ama altbilgide koşul bağlantısı yok, aramayla bulunamadı; /terms/ → 301 /terms-and-condition/ → 200, gövde boş. Bulunan tek metin makale altı ibare: yazılı izinsiz çoğaltma, yayın, "rewritten" ve yeniden dağıtım yok. /affiliate-disclaimer-guidelines/ yalnız bahis | Belirsiz | 0/6 |

"Sessiz" = yapay zekâ/TDM/otomatik toplama maddesi yok **ve saklama/veritabanı maddesi yok**; ticari kullanım izni
anlamına gelmez (el-balad, önceki tablodaki sportsmole ticari kullanımı izne bağlıyor). el-balad ile Newsquest'i
ayıran sınır bu saklama/veritabanı maddesidir (ikisi de izinsiz ticari kullanımı yasaklıyor); manşet sessiz payını
3 (yalnız dailytrust) yerine 6 yapan da o: el-balad Newsquest gibi sayılsaydı pay 3/198 (%1,5) olurdu.

Robots yine ToS'un göstergesi değil: Rocket ve Future robots'ta hiçbir yapay zekâ botunu engellemiyor ama ToS'ta
en sert metinler onların.

## ajansspor (17l)
- Sözleşme `/uyelik-sozlesmesi` ve `/kvkk` robots'ta kapalı → okunmadı; altbilgide kullanım koşulları bağlantısı yok.
- /gizlilik-politikasi, /kunye, /cerez-politikasi okundu (200, robots izinli): otomatik okuma/iktibas/yapay zekâ
  maddesi yok; genel "tüm hakları saklıdır" ibaresi.
- robots.txt `Content-Signal: ai-input=yes, ai-train=no` — elde olan en güçlü makinece okunur kanıt.

## football-data.co.uk
Bu ağdan bugün erişilemedi (TLS reset). 2026-09-22 runner okuması: yalnız sorumluluk reddi. robots kopyası
`config/robots/football-data.txt` (12 adlı yapay zekâ botu engelli, `*` açık; bizim UA onlara uymuyor — protego
500/500).

## Yöntem
Oturum 8: GDELT'e toplam 2 istek (robots 404; bir DOC sorgusu 429 → durdu; GKG o oturumda indirilmedi).
32 alan adının robots.txt'i dürüst UA ile okundu, protego ile değerlendirildi. Koşul sayfaları için önce robots'a
soruldu; Reuters ve Sun koşul sayfaları robots'ta kapalı olduğu için okunmadı.
Banner/form/Cloudflare doğrulamasına dokunulmadı. WebSearch yalnız sayfa bulmak için; kanıt birincil sayfalar.

Oturum 9 eki (2026-09-23): ilk 15 alan adı için robots.txt, ana sayfa (koşul bağlantısını bulmak için) ve koşul
sayfaları dürüst UA ile okundu; hepsi robots izinli. Bir istek dışında hepsi projenin `_guarded_get`i üzerinden
(robots + 2 sn aralık) gitti. İstisna: punchng.com `/terms/` yönlendirmesini görmek için yalın bir httpx isteği
(yönlendirme izlenmeden); robots bu yola izinliydi, UA dürüsttü, ama 2 sn aralık uygulanmadı — robots isteğinin
hemen ardından gitti. legal.aol.com robots.txt 403 → RFC 9309 gereği kısıtsız sayıldı. Sıralama için controller
28 GKG dosyasını data.gdeltproject.org'dan indirdi (robots canlı soruldu, 1 sn aralık). punchng.com için ek
okuma: /privacy-policy/ ve /terms/ yönlendirmesi. Not: Rocket sözleşmesi arama dizini dışındaki otomatik erişimi
"lisanssız" sayar; bu okuma caughtoffside.com ve justarsenal.com'a robots + ana sayfa + koşul sayfası isteği içerdi.

## Açık sorular
1. ~~Alan adı sıralaması ölçülmeli~~ **Kapandı (2026-09-23):** §Alan adı sıralaması. 3 sessiz alan adı yetmiyor
   (0 isabet); ilk 15'ten sessiz bulunanlar isabetlerin %3'ü. Açık kalan: ilk 15 dışı (92 isabet, %46,5; MEN
   hariç) okunmadı; punchng.com'un koşul sayfası bulunamadı (okunamadı); Newsquest'in saklama/veritabanı/ticari
   kaydı ile AOL ve thehardtackle'ın ticari yeniden kullanım kayıtlarının başlıkları saklayıp ticari üründe
   kullanmaya uzanıp uzanmadığı ve Rocket'ın ürün başına erişim ücreti iddiası 2. sorudaki avukat sorusuna eklenir.
2. **ToS'lar bizi bağlar mı?** Sitelere istek atmıyoruz (başlık/URL GDELT'ten). Avukat sorusu; temkinli yol dışlamak.
3. **Başlık telifi:** Birleşik Krallık NLA v Meltwater; AB TDM istisnası (2019/790 Md. 4) hak sahibinin itirazıyla
   kapanır — Goal, Daily Mail, NYT itirazı açık.
4. **ajansspor:** yayıncıya sormak (kullanıcı onayı) ya da `ai-input=yes`'i yeterli saymak.
5. **Okunamayanlar** (independent.ie, talksport, si, nbcsports, eurosport; Reuters, Sun koşulları;
   punchng.com) izin listesinde varsayılan dışarıda.
6. **Reach bölge siteleri** (MEN, Liverpool Echo) tek tek okunmadı.
7. **İlk 15 dışındaki olası Newsquest siteleri** (sahiplik doğrulanmadı): gazette-news.co.uk 2,
   messengernewspapers.co.uk 2, yorkpress.co.uk 1, cotswoldjournal.co.uk 1, denbighshirefreepress.co.uk 1, belki
   countypress.co.uk 1 — bilinmeyen 92 isabetin ~8'i; Newsquest sınıfı benimsenirse senaryo 65 → ≤73.
