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
   (okunmuş ve sessiz bulunmuş alan adları; bilinmeyen varsayılan dışarıda). Kapsam kaybı ölçülmedi (§6/1).
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
GDELT'e toplam 2 istek (robots 404; bir DOC sorgusu 429 → durdu; GKG indirilmedi). 32 alan adının robots.txt'i
dürüst UA ile okundu, protego ile değerlendirildi. Koşul sayfaları için önce robots'a soruldu; Reuters ve Sun
koşul sayfaları robots'ta kapalı olduğu için okunmadı. Banner/form/Cloudflare doğrulamasına dokunulmadı.
WebSearch yalnız sayfa bulmak için; kanıt birincil sayfalar.

## Açık sorular
1. **Alan adı sıralaması runner'da ölçülmeli:** `step6_gdelt_en.py` (`.superpowers/sdd/2026-09-23-faz4-plan1-dalga0-1/t0c/`)
   içinde `doms.most_common(40)` — izin listesiyle kaç başlık kaybedildiğini ve 3 sessiz alan adının yetip
   yetmediğini gösterir.
2. **ToS'lar bizi bağlar mı?** Sitelere istek atmıyoruz (başlık/URL GDELT'ten). Avukat sorusu; temkinli yol dışlamak.
3. **Başlık telifi:** Birleşik Krallık NLA v Meltwater; AB TDM istisnası (2019/790 Md. 4) hak sahibinin itirazıyla
   kapanır — Goal, Daily Mail, NYT itirazı açık.
4. **ajansspor:** yayıncıya sormak (kullanıcı onayı) ya da `ai-input=yes`'i yeterli saymak.
5. **Okunamayanlar** (independent.ie, talksport, si, nbcsports, eurosport; Reuters, Sun koşulları) izin listesinde
   varsayılan dışarıda.
6. **Reach bölge siteleri** (MEN, Liverpool Echo) tek tek okunmadı.
