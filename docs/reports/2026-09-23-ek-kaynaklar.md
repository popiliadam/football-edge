# Ek futbol haber kaynakları — koşul araştırması (2026-09-23)

**Durum:** karar girdisi (HANDOFF §0.7/4) · **Yöntem:** salt okuma araştırması (oturum 8, araştırma ajanı, dürüst
kimlik `football-edge-research/0.1`); hukuki görüş değildir · **Karar kullanıcınındır.** Önceki rapor:
`docs/reports/2026-09-23-kaynak-kosullari.md` (25 EN yayıncıdan 19'u yapay zekâ kullanımını/TDM'yi yasaklıyor).

## Özet
Hiçbir kaynak sorunu tek başına çözmüyor. **Haber API'leri** (GNews, NewsData.io, Event Registry, NewsAPI.org,
Mediastack) yayıncı hakkı vermiyor — yalnız aktarıyor; risk ve tazminat kullanıcıda. **Resmî lig/federasyon
siteleri** (Premier League, FPL, UEFA) otomatik toplamayı ve/veya yapay zekâ kullanımını açıkça yasaklıyor.
Kullanılabilir yollar: yapılandırılmış veri satan sağlayıcı, ücretli resmî sosyal API, `ai-input=yes` sinyalli
birkaç Türk yayıncı.

**EN — en iyi seçenekler**
1. GDELT + izin listesi (mevcut) — `izinli` (GDELT atfı); başlık hakları yayıncıda.
2. **SportMonks** — `koşullu` (ücretli plan, yeniden satış yok): yapılandırılmış sakat/cezalı (`sidelined`);
   koşullarda yapay zekâ maddesi yok; ticari ücretli planda açık. Starter €29/ay 5 lig; haber eklentisi +€99/ay.
3. **X API** (kullandıkça öde, $0.005/gönderi) — `koşullu`: yalnız model eğitimi yasak; ANCAK bir kullanıcının
   sağlık bilgisini türetme/çıkarsama yasağı var — kulüp hesabının duyurduğu oyuncu sakatlığı buna dokunabilir.
4. **Wikidata** (CC0, mevcut) — `izinli`: teknik direktör değişiklikleri (P286).
5. **Bluesky Jetstream** — `koşullu` (gönderi telifi kullanıcıda; ücretsiz; kulüp kapsamı ölçülmedi).

**TR — en iyi seçenekler**
1. ajansspor (mevcut) — `koşullu`: robots `ai-input=yes`, sözleşme okunamadı.
2. **Fotomaç / A Spor RSS** (Turkuvaz) — `koşullu`: robots `Content-Signal: ai-input=yes, ai-train=no`; Süper Lig
   ve Premier Lig için ayrı RSS (50 haber, özetli); koşul sayfası bulunamadı.
3. **TFF PFDK kararları** — `koşullu`: cezaların resmî kaynağı; TFF telif notu kişisel/ticari olmayan kullanıma
   izin verir, ticari kullanım izin + atıf ister.
4. **Galatasaray resmî RSS** (`/xml/gs.rss`) — `koşullu` (koşullar sessiz). FB/BJK/TS sitelerinde RSS yok.
5. SportMonks — Süper Lig, Starter'ın 5 lig kotasından biri olabilir.

**Önerilen kombinasyon (karar kullanıcıda):** EN: GDELT izin listesi + SportMonks Starter + resmî kulüp/lig
hesapları için X API + Wikidata. TR: ajansspor + Fotomaç/A Spor RSS + TFF PFDK + Galatasaray RSS + SportMonks.
Tahmini maliyet €29/ay + X ≈ $60/ay (40 hesap × 10 gönderi/gün varsayımı — ölçülmedi).

## Tablo (hepsi 2026-09-23'te okundu)
| Kaynak | Dil | Ne verir | Yöntem | Otomatik toplama | Yapay zekâ girdisi | Ticari | Maliyet/limit | Karar |
|---|---|---|---|---|---|---|---|---|
| SportMonks | EN/TR | Sakat/cezalı, kadro, maç öncesi haber (eklenti) | API | İzinli | Madde yok | Ücretli planda; yeniden satış yok | €29/ay 5 lig; haber +€99 | koşullu |
| API-Football | EN/TR | Sakatlık | API | ? | ? | ? | Ücretsiz 100/gün (ikincil) | okunamadı (Cloudflare, aşılmadı) |
| SportsDataIO | EN | Sakatlık, haber | Lisans | Sözleşme | "AI Content Automation" pazarlıyor | Sözleşme | Talep üzerine | koşullu (lisans) |
| X API | EN/TR | Resmî kulüp/lig gönderileri | API | İzinli | Eğitim yasak; sağlık çıkarsama yasak | Kapsama kadar | $0.005/gönderi | koşullu |
| Bluesky | EN | Gönderiler | Jetstream | İzinli | Madde yok | Madde yok | Ücretsiz | koşullu |
| Reddit Data API | EN | Gönderiler | API | Yalnız uygulamada gösterim | Eğitim yasak | Ayrı sözleşme | — | yasak (sözleşmesiz) |
| Guardian Open Platform | EN | Tam metin | API | Bot yasak | Yasak | Ticari olmayan | — | yasak |
| NYT API | EN | Başlık/özet | API | — | Yapay zekâ geliştirme yasak | Yasak (kumar anılıyor) | — | yasak |
| NewsAPI.org | EN/TR | Başlık/özet/URL | API | — | Madde yok | Yalnız ücretli | $449/ay | koşullu (yayıncı riski bizde) |
| GNews | EN/TR | Başlık; ücretlide metin | API | — | Madde yok | Ücretlide | €49.99/ay | koşullu (yayıncı riski bizde) |
| NewsData.io | EN/TR | Başlık; ücretlide metin | API | — | Madde yok | Evet, yayıncı adına izin veremez | $199.99/ay | koşullu (risk + tazminat bizde) |
| Event Registry | EN/TR | Metin + üst veri | API | — | Madde yok | Ücretlide | Ücretsiz yalnız değerlendirme | koşullu (yayıncı riski bizde) |
| Mediastack | EN | Başlık | API | — | Madde yok | Ücretsiz ticari değil | $24.99/ay | koşullu |
| Bing News API | — | — | — | — | — | — | 2025-08-11'de kapandı | yok |
| Wikinews | — | — | — | — | — | — | 2026-05-04'ten beri salt okunur | yok |
| Wikipedia / Wikidata | EN/TR | Koç, kadro | API/döküm | İzinli (UA politikası) | Lisans engellemiyor | CC BY-SA / CC0 | Enterprise ücretsiz 50k/ay | izinli |
| FPL API | EN | Sakatlık bayrağı | Belgelenmemiş JSON | Yasak | — | Yasak | — | yasak |
| premierleague.com | EN | Haber | Web | Veritabanı kurmak yasak | — | Yasak | — | yasak |
| UEFA | EN | Haber, kadro | Web | Yasak | Yasak | — | — | yasak |
| Transfermarkt | EN/TR | Sakatlık listesi | Web | Bot yasak | Yasak; TDM saklı | — | — | yasak |
| TheSportsDB | EN | Temel veri | API | robots izinli | robots `ai-input=no` | — | — | yasak |
| Fotomaç / A Spor | TR | Başlık + özet | RSS | robots izinli | robots `ai-input=yes` | Sayfa yok | Ücretsiz | koşullu |
| Sporx | TR | Haber | Web | robots izinli | Madde yok | Kaynak gösterme (FSEK 36) | Ücretsiz | koşullu (atıf) |
| TFF (PFDK, pageID=600) | TR | Ceza, hakem ataması | Web | Madde yok | Madde yok | Ticari izne bağlı | Ücretsiz | koşullu |
| Galatasaray | TR | Kulüp haberleri | RSS | — | Madde yok | Sayfa yok | Ücretsiz | koşullu |
| Anadolu Ajansı | TR | Haber | RSS | — | — | Abone olmayan kullanamaz | Abonelik | yasak (abonelikle koşullu) |
| TRT Haber | TR | Haber | Web | Yasak | — | Geniş yasak | — | yasak |
| NTV Spor | TR | Haber | Web | robots yapay zekâ botlarını kapatıyor | ? | ? | — | okunamadı |
| PA / Reuters / AP / AFP | EN | Akış | Lisans | Sözleşme | Sözleşme | Sözleşme | Kamuya açık değil | koşullu (lisans) |

## Scrapling notu
> **Güncelleme (aynı gün, R77b):** kullanıcı kararıyla parmak izi/tarayıcı taklidi ve varsayılanlar
> artık İZİNLİ (spec §3.2.1 R77b). Aşağıdaki "aykırı" notu R77 içindi; değişmeyen sınırlar: doğrulama çözme/atlatma
> yok (`solve_cloudflare` kapalı), robots/ToS'a uyum, adı verilmiş bot taklidi yok, proxy yok.

- **Varsayılanlar R77'ye aykırı:** `get` Chrome parmak izini taklit eder (`impersonate="chrome"`,
  `stealthy_headers=true`); `fetch` üretilmiş gerçek tarayıcı kimliği ve Google yönlendirme başlığı kullanır
  (`google_search=true`). Kullanımda taklit KAPATILIR, kimlik açıkça `football-edge/0.1 (+github)`, `google_search=false`.
- **Değer kattığı yer:** TFF PFDK (windows-1254, kırılgan `<div>` düzeni — uyarlanabilir seçiciler), RSS'i olmayan kulüp
  sayfaları (yalnız koşulları uygun bulunursa), JavaScript'le çizilen koşul sayfalarını okumak.
- **Gerekmediği yer:** RSS (Fotomaç, A Spor, Galatasaray), API'ler (SportMonks, X, Wikidata, GDELT), ajansspor sitemap.
- Cloudflare doğrulaması (ör. api-football.com) Scrapling'le de aşılmaz.

## Açık sorular
1. **KVKK/GDPR — BÜTÜN PROJE:** sakatlık bilgisi kimliği belli kişilerin sağlık verisidir (KVKK md. 6, GDPR md. 9,
   özel nitelikli). Kaynaktan bağımsız. Özelliklerin takım düzeyinde toplulaştırılması riski azaltır mı? Avukat.
2. X'in sağlık çıkarsama maddesi kulüp duyurularından oyuncu sakatlığı türetmeyi kapsıyor mu?
3. SportMonks maç öncesi haber metni kendi içeriği mi, lisanslı mı; yapay zekâ girdisi açıkça serbest mi? (Sormak
   dış iletişim — kullanıcı onayı.)
4. SportMonks'un Süper Lig sakatlık kapsamı ajansspor'a göre? (14 günlük deneme hesap açmayı gerektirir — kullanıcı.)
5. TFF'den ticari lansman öncesi yazılı izin? (dış iletişim — kullanıcı.)
6. `ai-input=yes` bir lisans değil, tek taraflı sinyal — ajansspor, Fotomaç, A Spor bu tek kanıta dayanıyor.

**Okunamayanlar:** API-Football koşulları, NTV Spor koşulları, Mastodon, Event Registry fiyatları, tek tek kulüp
koşulları (Arsenal, Man Utd — 404).
