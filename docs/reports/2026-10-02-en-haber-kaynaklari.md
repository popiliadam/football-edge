# EN futbol haber kaynakları — robots / RSS / koşul taraması (2026-10-02)

**Durum:** karar girdisi · **Yöntem:** salt okuma taraması (araştırma ajanı, dürüst kimlik
`football-edge/0.1 (+https://github.com/popiliadam/football-edge)`) · **Karar kullanıcınındır.**
Önceki raporlar: `docs/reports/2026-09-23-kaynak-kosullari.md`, `docs/reports/2026-09-23-ek-kaynaklar.md` —
oradaki koşul okumaları burada tekrarlanmadı, yalnız atıf yapıldı; çelişkiler §5'te işaretli.

## 0. Kapsam, yöntem, uyarılar

- **Hukuk tavsiyesi değildir.** Koşul özetleri kendi cümlelerimle; alıntılar ≤15 sözcük.
- **`Content-Signal: ai-input=yes` tek taraflı bir sinyaldir, lisans değildir.** TR'de kullandığımız yöntem
  (ai-input=yes + RSS + koşullarda yasak yok) bu raporda aynen uygulandı.
- **Kapsam:** istenen ~45 kaynak + "gerekirse ekle" ile 40 ek alan adı (Content-Signal aramak için). Toplam
  84 alan adının robots.txt'i okundu; RSS ve koşullar yalnız anlamlı adaylarda okundu.
- **Ölçüm:** robots.txt `curl` ile ham metin; RSS ve koşul sayfaları scratchpad'deki salt okuma betiğiyle
  (projenin `.venv`'indeki `httpx` + `protego`; her istekten önce robots `protego` ile soruldu, bizim UA'mız
  için). İstekler sıralı, aralarında ≥2 sn; Reach siteleri için robots'taki `Crawl-delay: 10` uygulandı.
  Toplam ~220 istek. Cloudflare/403/bağlantı sıfırlama görülen yerde tekrar denenmedi, "okunamadı" yazıldı.
  Banner/form/doğrulamaya dokunulmadı; parmak izi/tarayıcı taklidi, proxy, adı verilmiş bot kimliği yok.
- **Kazara istekler:** koşul bağlantısını anasayfadan bulan sezgisel arama birkaç makale sayfasını da çekti
  (Marca, Flashscore, SPORTbible, Football Faithful birer makale, policies.google.com) — hepsi robots izinli,
  dürüst UA; içerikleri kullanılmadı.
- **"6'lı" AI bot sayımı:** önceki raporla aynı yöntem — GPTBot, ClaudeBot, CCBot, Google-Extended,
  PerplexityBot, anthropic-ai'dan kaçının `/news/2026/09/22/example-football-article` yolunda engelli olduğu
  (`protego`). Bunlar bizim UA'mız değil; yalnız yayıncının niyetini gösterir.
- **Sınıflar:** KULLANILABİLİR (ai-input=yes VE RSS VE koşullarda yasak yok) · KOŞULLU (sinyal yok ama
  robots/koşullar otomatik erişimi ya da AI kullanımını yasaklamıyor; RSS var) · YASAK (robots ya da
  koşullar otomatik erişimi / AI kullanımını yasaklıyor) · OKUNAMADI. Görevdeki dört sınıfa bir ek:
  **RSS YOK** — robots/koşul sorun çıkarmasa da RSS bulunamadığı için aday olmayan siteler (resmî lig ve
  kulüp siteleri).
- **Ticari kısıt ayrı bir eksen:** KOŞULLU bulunan EN sitelerin neredeyse hepsi kullanımı "kişisel / ticari
  olmayan" ile sınırlıyor ya da çoğaltma/saklamayı izne bağlıyor. Bu madde otomatik erişim yasağı değil;
  ama ticari lansmanda yazılı izin gerektirir (football-data duruşuyla aynı, spec §10/2).

## 1. Özet

**Ana bulgu: EN'de KULLANILABİLİR kaynak 0.** 84 robots.txt'in **hiçbiri** `ai-input=yes` taşımıyor. Content-Signal
satırı olan tek site soccernews.com (`search=yes,ai-train=no`, ai-input belirtilmemiş). TR'deki yöntem EN'e
taşınamıyor: büyük İngiliz yayıncılar Cloudflare sinyali yerine robots yorumlarında ve koşullarda açık yasak
kullanıyor (BBC, NYT, Daily Mail, Valnet, Reuters robots yorumları; Rocket'ın `tdl:` sözleşmesi).

**KULLANILABİLİR:** yok.

**KOŞULLU (13):** Sports Mole, The Independent, Evening Standard, Get French Football News, Football Oranje,
Inside Futbol, 101 Great Goals, The Football Faithful, Soccer News, World Soccer Talk, The Analyst (Opta),
Marca English, Breaking The Lines (RSS bayat). Ayrıca GDELT'in kendisi izinli (atıf şartı).
Hepsinde ortak risk: kişisel/ticari olmayan kullanım sınırı ya da izinsiz çoğaltma/saklama yasağı.

**YASAK (27):** BBC Sport, Sky Sports, ESPN, The Athletic/NYT, Goal, 90min, Football365, TEAMtalk, Planet
Football, FourFourTwo, Telegraph, Daily Mail, The Sun, Mirror, Express, Liverpool Echo, MEN, football.london,
Football Italia, Football España, Bundesliga.com, Eredivisie, FotMob, Football Fancast, GiveMeSport, Tribal
Football, SPORTbible (+ önceki rapordan Guardian, Times, Reuters).

**OKUNAMADI:** talkSPORT, OneFootball, Squawka, This Is Anfield (koşullar), Football Insider (koşullar),
AS English (EN sürümü bulunamadı), Serie A ve Pro League (koşul sayfası bulunamadı; RSS de yok).

**RSS YOK:** LaLiga, Serie A, Ligue 1, Pro League ve altı Premier League kulübünün resmî sitesi (Arsenal,
Chelsea, Liverpool, Man City, Man Utd, Tottenham — hiçbirinde RSS bağlantısı yok; Arsenal `/rss-feeds` 404).

**En iyi 5 öneri (hepsi KOŞULLU; açmak kullanıcı kararı):**
1. **Sports Mole** — futbol RSS'i 117 öğe, hepsi özetli, güncel; robots 0/6; çok ligli maç önizlemeleri (takım
   haberi içeriyor). Koşullar: kişisel/ticari olmayan; içeriğin her türlü kullanımı yazılı izne bağlı.
2. **The Independent** — futbol RSS'i 18 öğe, özetli; robots 0/6. Koşullar başlık + URL ile bağlantı vermeye
   açıkça izin veriyor; izinsiz indirme/saklama/arşivleme ve ticari kullanım yok.
3. **Evening Standard** — Independent ile aynı koşul metni; RSS 32 öğe; Londra kulüpleri ağırlıklı.
4. **Get French Football News** — Ligue 1; RSS 10 öğe, özetli; robots kısıtsız; koşul sayfası yok.
5. **Football Oranje** — Hollanda futbolu (Eredivisie/milli takım); RSS 10 öğe; robots kısıtsız; koşul
   sayfası yok.

Yedek: Inside Futbol (transfer ağırlıklı), 101 Great Goals (tahmini kadrolu önizlemeler; bahis ortaklığı sitesi),
Soccer News. Breaking The Lines AI kullanımına **açıkça davet eden tek** yayıncı (robots yorumu + llms.txt), ama
RSS'i eski WordPress alt alan adına gidiyor ve son öğesi 2026-06-12 — canlı akış yok.

**Kulüp/lig kapsamı (sitelerin odağına göre; lig başına isabet ÖLÇÜLMEDİ):**

| Lig | KOŞULLU kaynaklar |
|---|---|
| E0 Premier League | Independent, Standard (Londra), Sports Mole, Inside Futbol, 101 Great Goals, Soccer News, Football Faithful, WST |
| SP1 La Liga | Sports Mole, 101 Great Goals, Marca English (genel akış ABD sporlarıyla karışık; futbol akışı bayat) |
| I1 Serie A | Sports Mole, 101 Great Goals |
| D1 Bundesliga | Sports Mole, 101 Great Goals |
| F1 Ligue 1 | **GFFN** (tek odaklı), Sports Mole, 101 Great Goals |
| N1 Eredivisie | **Football Oranje** (milli takım ağırlıklı) |
| B1 Pro League | yok |
| T1 Süper Lig | yok (EN'de; TR kaynakları ayrı) |

## 2. Tablo (hepsi 2026-10-02'de okundu)

Kısaltmalar: "robots" = bizim UA'mız için RSS yolu izinli mi + `*` grubunun özeti; "CS" = Content-Signal;
"6'lı" = §0'daki sayım; "(önceki)" = koşul özeti 2026-09-23 raporlarından, bugün yeniden okunmadı.

| Kaynak | robots durumu | CS | AI bot engelleri | RSS URL (durum, öğe/özetli) | Koşul özeti | Sınıf | Okuma |
|---|---|---|---|---|---|---|---|
| BBC Sport | 200; RSS host (feeds.bbci.co.uk) izinli | yok | 6/6 (+14 adlı bot daha) | https://feeds.bbci.co.uk/sport/football/rss.xml (200, 81/81) | robots yorumu: kazıma, AI eğitimi, TDM ve "No retrieval-augmented generation (RAG), AI-powered search, agentic AI or grounding" | YASAK | 2026-10-02 |
| Sky Sports | 200; izinli | yok | 2/6 (GPTBot, CCBot) | https://www.skysports.com/rss/12040 (200, 20/18; at yarışı karışık) | (önceki) sky.com T&C: bot/kazıma/birleştirme yok, AI eğitimi yok | YASAK | 2026-10-02 |
| ESPN FC | 200; izinli | yok | 4/6 | https://www.espn.com/espn/rss/soccer/news (200, 19/19) | (önceki) Disney ToU: içeriği AI'ya prompt/eğitim için vermek yasak | YASAK | 2026-10-02 |
| The Athletic / NYT | 200; izinli (rss.nytimes.com robots 404) | yok | 6/6 (+19) | https://www.nytimes.com/athletic/rss/football/ (200, 100/100); https://rss.nytimes.com/services/xml/rss/nyt/Soccer.xml (200, 20) | robots yorumu: otomatik veri madenciliği yazılı izinsiz yasak; AI/ML geliştirme yasak; (önceki) ToS RAG/grounding | YASAK | 2026-10-02 |
| Goal.com | 200; `Allow: /` | yok | 0/6 | bulunamadı (`/feeds/en/news` 404; sayfada alternate yok) | (önceki) TDM ve kazıma yok, DSM Md. 4(3) hakkı saklı | YASAK | 2026-10-02 |
| 90min | 200; izinli | yok | 0/6 | https://www.90min.com/posts.rss (200, 90/90) | (önceki) Minute Media T&C: bot/crawler yasak | YASAK | 2026-10-02 |
| Football365 | 200; izinli; Google-Extended açıkça Allow | yok | 0/6 | https://www.football365.com/rss (200, 41/41) | (önceki) içeriği AI'ya vermek/beslemek yasak | YASAK | 2026-10-02 |
| TEAMtalk | 200; izinli (F365 ile aynı) | yok | 0/6 | https://www.teamtalk.com/rss (200, 35/35) | (önceki) F365 ile aynı metin | YASAK | 2026-10-02 |
| Planet Football | 200; izinli (aynı ağ) | yok | 0/6 | https://www.planetfootball.com/feed (200, 10/10) | /terms-conditions-2: bot, kazıyıcı, AI ile indeksleme/eğitim/analiz yasak; md. 6 otomatik erişim yasağı | YASAK | 2026-10-02 |
| FourFourTwo | 200; izinli | yok | 0/6 (13 başka AI botu kapalı) | https://www.fourfourtwo.com/feeds.xml (200, 50/49) | (önceki) Future plc: TDM ve kazıma her amaçla yasak | YASAK | 2026-10-02 |
| talkSPORT | okunamadı (TCP bağlantısı sıfırlandı) | — | — | denenmedi | (önceki) okunamadı | OKUNAMADI | 2026-10-02 |
| Evening Standard | 200; izinli | yok | 0/6 | https://www.standard.co.uk/sport/football/rss (200, 32/32) | /service/terms-of-use-6902768.html: yalnız kişisel/ticari olmayan; izinsiz indirme, saklama, arşivleme, ticari kullanım yok; AI/otomasyon maddesi yok | KOŞULLU | 2026-10-02 |
| The Independent | 200; izinli | yok | 0/6 | https://www.independent.co.uk/sport/football/rss (200, 18/18) | /service/user-policies-a6184151.html: Standard ile aynı; ek olarak üçüncü taraflar URL + başlık + kaynak adıyla bağlantı verebilir; derin bağlantı/çerçeve yok | KOŞULLU | 2026-10-02 |
| The Telegraph | 200; izinli | yok | 5/6 (+25; Google-Extended açık) | https://www.telegraph.co.uk/football/rss.xml (200, 120/120) | (önceki) robotla veri çıkarma yasak; AI eğitimi kapsam dışı | YASAK | 2026-10-02 |
| Daily Mail | 200 (.co.uk ve .com); izinli | yok | 6/6 (+27) | https://www.dailymail.co.uk/sport/football/index.rss → dailymail.com (200, 150/150) | robots yorumu (23.09.2026): otomatik veri madenciliği yazılı izinsiz yasak; AI/ML geliştirme yasak | YASAK | 2026-10-02 |
| The Sun | 200; **`User-agent: *` → `Disallow: /`** (bizim UA kapalı) | yok | 5/6 | istenmedi (robots kapalı) | robots yorumu: lisanssız LLM kullanımına izin yok | YASAK | 2026-10-02 |
| Mirror | 200; izinli; `Crawl-delay: 10` | yok | 5/6 (+6) | https://www.mirror.co.uk/sport/football/?service=rss (200, 25/25) | (önceki) Reach: içerikle AI eğitmek/geliştirmek yasak | YASAK | 2026-10-02 |
| Express | 200; izinli | yok | 5/6 | https://www.express.co.uk/posts/rss/78/football (200, 10/10; öğeler futbol dışı görünüyor) | (önceki) Reach metni | YASAK | 2026-10-02 |
| Liverpool Echo | 200; izinli; CD 10 | yok | 5/6 | https://www.liverpoolecho.co.uk/all-about/liverpool-fc?service=rss (200, 25/25) | (önceki) Reach metni varsayıldı, tek tek okunmadı | YASAK | 2026-10-02 |
| Manchester Evening News | 200; izinli; CD 10 | yok | 5/6 | https://www.manchestereveningnews.co.uk/sport/football/?service=rss (200, 25/25) | (önceki) Reach metni varsayıldı | YASAK | 2026-10-02 |
| football.london | 200; izinli; CD 10 | yok | 5/6 | https://www.football.london/?service=rss (200, 25/25) | (önceki) Reach | YASAK | 2026-10-02 |
| Football Italia | 200; izinli; **`tdl: https://m4ow.uk/socw/2.txt`** | yok | 0/6 | https://football-italia.net/feed/ (200, 20/20) | /terms-of-service/ md. 2: otomatik/programatik erişimi Rocket'ın "Search Only Terms Contract"ı yönetir (yalnız arama dizini; önceki rapor: AI zenginleştirme yasak) | YASAK | 2026-10-02 |
| Marca English | www.marca.com 200; RSS host e00-marca.uecdn.es izinli | yok | 5/6 (feed host 4/6) | https://e00-marca.uecdn.es/rss/en/index.xml (200, 31/30; ABD sporlarıyla karışık); `/rss/en/football.xml` 200 ama son öğe 2026-05-30 | /en/corporate/terms-of-service.shtml md. 5: içerik son kullanıcı için; izinsiz ticari kullanım/yeniden satış yok; çoğaltma izne bağlı; AI/otomasyon maddesi yok | KOŞULLU (zayıf) | 2026-10-02 |
| AS English | en.as.com robots 200; anasayfa as.com'a (İspanyolca) yönleniyor | yok | 3/6 (+9) | EN akışı bulunamadı | okunmadı | OKUNAMADI | 2026-10-02 |
| Get French Football News | 200; `*` grubu yok (yalnız bingbot/AmazonAdBot) → kısıtsız | yok | 0/6 | https://www.getfootballnewsfrance.com/feed/ (200, 10/10) | koşul sayfası yok (altbilgi: About/Contact/Privacy; `/terms-and-conditions/` 404) | KOŞULLU | 2026-10-02 |
| Bundesliga.com | 200 | yok | 0/6 (adlı botlar listeli, tam kapalı değil) | aranmadı | robots yasal uyarısı (DE/EN): TDM için kullanılamaz; bot ve benzeri programlarla erişim/analiz/indirme yasak; AI eğitimi özellikle | YASAK | 2026-10-02 |
| LaLiga | 200; `Crawl-delay: 30` | yok | 0/6 | bulunamadı | /en-GB/legal/legal-web: kişisel/ticari olmayan lisans; ticari amaçla çoğaltma/iletim yasak | RSS YOK | 2026-10-02 |
| Serie A | 200 (www ve en.); izinli | yok | 0/6 | bulunamadı (`/en` → en.legaseriea.it 307) | koşul sayfası bulunamadı | RSS YOK / OKUNAMADI | 2026-10-02 |
| Ligue1.com | 200; izinli | yok | 0/6 | bulunamadı | /en/legal/legal-notice: yalnız özel/kişisel kullanım; /en/legal/cgu: LFP yazılı izni olmadan yeniden kullanım yok | RSS YOK | 2026-10-02 |
| Eredivisie | 200; izinli | yok | 0/6 | bulunamadı (`/en/` 500) | /algemene-voorwaarden/: yalnız kişisel; ticari yasak; data mining/robot/spider/scraper yasak | YASAK | 2026-10-02 |
| Pro League | 200; izinli | yok | 0/6 | bulunamadı (`/en` 404) | koşul sayfası bulunamadı (`/disclaimer` 404) | RSS YOK / OKUNAMADI | 2026-10-02 |
| OneFootball | okunamadı (TCP sıfırlandı) | — | — | — | — | OKUNAMADI | 2026-10-02 |
| FotMob | 200; izinli (`/api/*` kapalı) | yok | 0/6 | https://www.fotmob.com/topnews/feed?format=rss (200, 20/20) | /tos.txt (12.09.2023): robot/spider/indeksleme ve sistematik toplu veri alımı açıkça yasak | YASAK | 2026-10-02 |
| Sports Mole | 200; izinli | yok | 0/6 | https://www.sportsmole.co.uk/football/rss.xml (200, 117/117) | terms-and-conditions_467 (12.05.2026): yalnız kişisel/özel/ticari olmayan; içeriğin her türlü kullanımı yazılı izne bağlı; rakip kullanım yok; AI/otomasyon maddesi yok | KOŞULLU | 2026-10-02 |
| Football Fancast | 200; izinli | yok | 4/6 (+9) | https://www.footballfancast.com/feed/ (200, 10/10) | Valnet robots yorumu: otomatik toplama yazılı izinsiz yasak; AI (eğitim, embedding, RAG) yasak | YASAK | 2026-10-02 |
| GiveMeSport | 200; izinli | yok | 4/6 | denenmedi | Valnet robots yorumu (Fancast ile aynı) | YASAK | 2026-10-02 |
| Squawka | 200; izinli | yok | 0/6 | `/en/feed/` 403; anasayfa 403 | okunamadı | OKUNAMADI | 2026-10-02 |
| The Analyst (Opta) | 200; izinli | yok | 5/6 (30+ adlı AI botu `Disallow: /`) | https://theanalyst.com/feed (200, 70/70) | statsperform.com/terms-and-conditions: yalnız kişisel/ticari olmayan; başka ağ ortamında kullanım izne bağlı; AI/otomasyon maddesi yok | KOŞULLU (zayıf) | 2026-10-02 |
| Tribal Football | 200; izinli; CD 1 | yok | 0/6 | bulunamadı (`/feed`, `/rss.xml` 404) | /terms-of-use (Livesport): otomatik istekle yük yok; izinsiz birleştirme/kazıma yok; ticari kullanım yok | YASAK | 2026-10-02 |
| World Soccer Talk | 200; izinli | yok | 0/6 | https://worldsoccertalk.com/feed/ → /rss/feed/ (200, 100/99) | /terms-and-conditions/ (Better Collective şablonu): içerik kullanımı yetkisi yalnız ücretsiz erişim kadar; AI/otomasyon maddesi yok — belirsiz | KOŞULLU (belirsiz) | 2026-10-02 |
| Arsenal | 200; izinli | yok | 0/6 | yok (`/rss-feeds` 404; alternate yok) | okunmadı | RSS YOK | 2026-10-02 |
| Chelsea | 200; `Allow: /` | yok | 0/6 | yok | okunmadı | RSS YOK | 2026-10-02 |
| Liverpool | 200; `Allow: /` | yok | 0/6 | yok | okunmadı | RSS YOK | 2026-10-02 |
| Man City | 200; izinli | yok | 0/6 | yok | okunmadı | RSS YOK | 2026-10-02 |
| Man Utd | 200; izinli | yok | 0/6 | yok | okunmadı | RSS YOK | 2026-10-02 |
| Tottenham | 200; GPTBot, ClaudeBot, PerplexityBot, Google-Extended **açıkça Allow** | yok | 0/6 | yok | okunmadı | RSS YOK | 2026-10-02 |
| **Ek alan adları** | | | | | | | |
| Breaking The Lines | 200; izinli; yorum: AI/LLM tarayıcıları "train on, cite, and surface" için davetli | yok | 0/6 (14 AI botu açıkça Allow) | https://breakingthelines.com/feed → old.breakingthelines.com/feed/ (200, 10/10; son öğe 2026-06-12, **bayat**) | /terms (07.04.2026): otomatik erişim robots'un izin verdiği kadar serbest; içerik yaratıcılara ait; platformdan çoğaltma izne bağlı. /llms.txt indeksleme, eğitim ve atfı hoş karşılıyor | KOŞULLU (RSS bayat) | 2026-10-02 |
| Football Oranje | 200; `Disallow:` boş | yok | 0/6 | https://www.football-oranje.com/feed/ (200, 10/10) | koşul sayfası bulunamadı | KOŞULLU | 2026-10-02 |
| Inside Futbol | 200; `*` grubu yok → kısıtsız | yok | 0/6 | https://insidefutbol.com/feed/ (200, 10/10) | /terms-of-use/ md. 7.2: kopyalama, indirme, iletme, çoğaltma, ticari kullanım yok; AI/otomasyon maddesi yok | KOŞULLU | 2026-10-02 |
| 101 Great Goals | 200; izinli | yok | 0/6 | https://www.101greatgoals.com/feed/ (200, 16/16) | /terms-and-conditions/ (Acroud Media, Nisan 2026): yazılı izinsiz dağıtım/kopyalama/çoğaltma/yayım yok; AI/otomasyon maddesi yok | KOŞULLU | 2026-10-02 |
| The Football Faithful | 200; izinli | yok | 0/6 | https://thefootballfaithful.com/feed/ (200, 10/10) | /terms-conditions/: çoğaltma, dağıtım, ticari kullanım yazılı izne bağlı; kişisel geçici kopya serbest | KOŞULLU | 2026-10-02 |
| Soccer News | 200; izinli | **`search=yes,ai-train=no`** (ai-input yok) | 3/6 | https://www.soccernews.com/feed/ (200, 10/10) | /terms-and-conditions/ md. 2.1: yalnız kişisel/ticari olmayan; ticari kullanım kesinlikle yasak | KOŞULLU (zayıf) | 2026-10-02 |
| This Is Anfield | 200; `Allow: /` | yok | 0/6 | https://www.thisisanfield.com/feed/ (200, 16/16) | anasayfa 403 → koşullar okunamadı | OKUNAMADI | 2026-10-02 |
| Football Insider | 200; izinli | yok | 3/6 | /feed/ → https://www.footballinsider247.com/stories.rss (200, 6/5) | koşul bağlantısı bulunamadı | OKUNAMADI | 2026-10-02 |
| SPORTbible | 200; izinli | yok | 0/6 | https://www.sportbible.com/football.rss (200) | ladbiblegroup.com/terms: robot/spider/kazıyıcı ile otomatik toplama yazılı izinsiz yasak | YASAK | 2026-10-02 |
| Football España | 200; `tdl:` Rocket sözleşmesi | yok | 0/6 | denenmedi | Football Italia ile aynı (Rocket) | YASAK | 2026-10-02 |
| GDELT (kaynak) | gdeltproject.org 200: yalnız `/data/` kapalı; api.* robots 404 (önceki) | yok | 0/6 | — (DOC API) | /about.html: veri setleri her kullanım için ücretsiz ve kısıtsız; her kullanımda GDELT atfı + bağlantı | izinli (atıf) | 2026-10-02 |

**Yalnız robots okunan ek alan adları** (RSS/koşul okunmadı; sınıflanmadı): theguardian.com 4/6 (yorum: LLM/ML/AI
kullanımı izne bağlı — önceki rapor YASAK), thetimes.com (`*` → `Disallow: /`), reuters.com (yorum: otomatik
toplama yazılı izinsiz yasak; makale yolu bizim UA'ya kapalı), sportskeeda 5/6, vavel 4/6, cbssports 1/6,
soccerway/flashscore 1/6, footballtransfers, besoccer, beinsports, football.co.uk, footballcritic,
totalfootballanalysis (`/feed` anasayfaya yönleniyor — RSS yok), ibtimes.co.uk, transfermarkt, foxsports,
eurosport (→ tntsports.co.uk) — hepsinde Content-Signal yok. Bağlantı kurulamadı: si.com, nbcsports.com,
footballwhispers.com, bundesligafanatic.com, dutchsoccersite.com, get{italian,german,spanish}footballnews.com.

## 3. GDELT izin listesine aday alan adları

**KULLANILABİLİR alan adı yok → katı kriterle izin listesine eklenecek EN alan adı yok.**

Kullanıcı kriteri "AI/otomasyon maddesi yok" düzeyine gevşetirse (KOŞULLU kabul) aday alan adları:
`sportsmole.co.uk`, `independent.co.uk`, `standard.co.uk`, `getfootballnewsfrance.com`, `football-oranje.com`,
`insidefutbol.com`, `101greatgoals.com`, `thefootballfaithful.com`, `soccernews.com`, `worldsoccertalk.com`,
`breakingthelines.com`. Uyarı: önceki rapor GDELT EN örnekleminde independent/standard/sportsmole için **0
isabet** ölçtü; diğerlerinin GDELT'teki payı ölçülmedi. GDELT yolunda siteye istek gitmez; yalnız koşullardaki
saklama/ticari kayıtlar (Independent/Standard "izinsiz saklama yok") anlamlı kalır.

## 4. `config/sources.yaml` kayıt taslakları

**KULLANILABİLİR kaynak yok → bu bölüm görev tanımı gereği boş.** Aşağıdaki taslaklar §1'in en iyi 5 KOŞULLU
önerisi içindir; hepsi `enabled: false`. Açmadan önce: (a) kullanıcı kararı, (b) kapının istediği robots anlık
görüntüsü `config/robots/<id>.txt` (bu taramada yazılmadı — tek dosya kuralı), (c) toplayıcı kodu yok.

```yaml
  - id: sportsmole
    base_url: https://www.sportsmole.co.uk
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-02
    declared_paths: ['/football/rss.xml']
    enabled: false
    access_basis: robots
    terms_url: https://www.sportsmole.co.uk/about/information/terms-and-conditions_467.html
    note: >-
      KOŞULLU (docs/reports/2026-10-02-en-haber-kaynaklari.md). Content-Signal YOK; robots `*` bu yolu
      izinli, 6'lı AI bot sayımı 0/6. RSS 200, 117 öğe, hepsi özetli. Koşullar (12.05.2026): yalnız
      kişisel/özel/ticari olmayan kullanım; içeriğin her türlü kullanımı yazılı izne bağlı; AI/otomasyon
      maddesi yok. Ticari lansmandan önce yazılı izin.

  - id: independent
    base_url: https://www.independent.co.uk
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-02
    declared_paths: ['/sport/football/rss']
    enabled: false
    access_basis: robots
    terms_url: https://www.independent.co.uk/service/user-policies-a6184151.html
    note: >-
      KOŞULLU. Content-Signal YOK; 0/6. RSS 200, 18 öğe, özetli. Koşullar: kişisel/ticari olmayan;
      izinsiz indirme/saklama/arşivleme yok — başlık+URL ile bağlantı açıkça serbest. Saklama maddesi
      nedeniyle yalnız URL + başlık tutulmalı mı: açık soru (§5/3).

  - id: standard
    base_url: https://www.standard.co.uk
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-02
    declared_paths: ['/sport/football/rss']
    enabled: false
    access_basis: robots
    terms_url: https://www.standard.co.uk/service/terms-of-use-6902768.html
    note: >-
      KOŞULLU. Independent ile aynı koşul metni. Content-Signal YOK; 0/6. RSS 200, 32 öğe, özetli.

  - id: gffn
    base_url: https://www.getfootballnewsfrance.com
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-02
    declared_paths: ['/feed/']
    enabled: false
    access_basis: robots
    terms_url: ''
    note: >-
      KOŞULLU. robots.txt'te `User-agent: *` grubu yok (yalnız bingbot/AmazonAdBot) → kısıtsız.
      Content-Signal YOK. RSS 200, 10 öğe, özetli; Ligue 1. Koşul sayfası YOK (altbilgide yalnız
      About/Contact/Privacy) — koşul yokluğu hak verilmesi demek değil.

  - id: football-oranje
    base_url: https://www.football-oranje.com
    user_agent: football-edge/0.1 (+https://github.com/popiliadam/football-edge)
    crawl_delay_seconds: 2.0
    robots_verified_at: 2026-10-02
    declared_paths: ['/feed/']
    enabled: false
    access_basis: robots
    terms_url: ''
    note: >-
      KOŞULLU. robots `*` için `Disallow:` boş; Content-Signal YOK; 0/6. RSS 200, 10 öğe, özetli;
      Hollanda futbolu (milli takım ağırlıklı, Eredivisie). Koşul sayfası bulunamadı.
```

## 5. Açık sorular

1. **Kriter kararı:** EN'de `ai-input=yes` veren yayıncı bulunamadı (84 robots). TR yöntemi EN'e taşınamıyor.
   KOŞULLU sınıf (AI/otomasyon yasağı yok, ama kişisel/ticari olmayan kısıtı var) EN haber sinyali için kabul
   edilecek mi, yoksa EN'de haber sinyali GDELT + yapılandırılmış veri (SportMonks, önceki rapor) ile mi sınırlı kalacak?
2. **Ticari olmayan kısıtı:** Jev'e başlık/özet girdi olarak vermek ürünün ticari olup olmamasına göre bu
   maddelere girer mi? Avukat sorusu. Ticari lansmandan önce yayıncıdan yazılı izin (dış iletişim — kullanıcı onayı).
3. **Saklama maddeleri:** Independent/Standard izinsiz indirme/saklama/arşivlemeyi, Inside Futbol indirmeyi
   yasaklıyor. Başlıkları DB'de tutmak yerine yalnız URL + geçici bellek içi işleme yeterli mi?
4. **Önceki raporla çelişki — "sessiz" tanımı:** 2026-09-23 kaynak-koşulları raporu independent.co.uk ve
   standard.co.uk'u "sessiz" saydı; aynı raporun sonraki bölümü "sessiz"i "saklama/veritabanı maddesi yok"
   diye tanımladı. Bugün okunan iki metin izinsiz **saklama ve arşivlemeyi** yasaklıyor → o tanıma göre
   "sessiz" değil, Newsquest'e yakın sınıf. Sports Mole (aynı 12.05.2026 sürümü) da yalnız "kişisel/ticari
   olmayan" değil, içeriğin **her türlü** kullanımını yazılı izne bağlıyor ve rakip kullanımı yasaklıyor.
   Bu raporda üçü de KOŞULLU; önceki "sessiz" etiketinin düzeltilmesi kullanıcı kararı.
5. **Önceki raporla uyumlu bulgular:** Goal/90min/F365/FourFourTwo robots'ta 6'lı engel yok ama koşullarda yasak
   (robots yine ToS göstergesi değil). Sky 2/6, ESPN 4/6, Telegraph 5/6, Daily Mail ve NYT 6/6, Reach 5/6 —
   2026-09-23 sayımlarıyla aynı. BBC için yeni ve daha güçlü kanıt: robots yorumu RAG/grounding/agentic AI'yı
   açıkça yasaklıyor (Jev kullanımı çıkarım/grounding sayılabilir).
6. **Breaking The Lines:** AI'ya açıkça izin veren tek EN yayıncı, ama RSS bayat (eski alt alan adı, son öğe
   2026-06-12). Yeni sitede canlı akış ya da haber sitemap'i var mı? İçerik yaratıcılara ait — BTL'nin daveti
   yaratıcı içeriğini kapsar mı? Analiz/yorum ağırlıklı; takım haberi sinyali zayıf olabilir.
7. **Güvenilmeyen girdi:** BTL'nin `/llms.txt`'i AI ajanlarına yönelik tanıtım talebi içeriyor (veri olarak
   okundu, sınıflamayı etkilemedi). RSS başlık/özetleri Jev'e verilecekse aynı türden metin girebilir — girdi
   sınırı/temizleme kararı gerekli.
8. **Okunamayanlar:** talkSPORT ve OneFootball (TCP sıfırlandı), Squawka (403), This Is Anfield koşulları (403),
   Football Insider koşulları (bağlantı yok), AS English (EN sürümü bulunamadı), Serie A ve Pro League koşul
   sayfaları, si.com, nbcsports — izin listesinde varsayılan dışarıda.
9. **Kapsam boşluğu:** B1 ve T1 için EN KOŞULLU kaynak yok; N1 yalnız Football Oranje (milli takım ağırlıklı).
   Lig başına isabet sayısı ölçülmedi — açılmadan önce RSS öğeleri lig takım adlarıyla eşlenip sayılmalı.
10. **Reach kulüp siteleri** (Liverpool Echo, MEN) hâlâ tek tek okunmadı (önceki rapor açık soru 6); robots'ları
    football.london/Mirror ile aynı yapıda, 5/6 engel ve `Crawl-delay: 10`.
