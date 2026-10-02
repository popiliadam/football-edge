# The Odds API koşulları — türetilmiş olasılık yayımı (AK17, 2026-10-02)

**Durum:** karar girdisi (spec 2026-09-23-faz6-iz-b-design §16 AK17; HANDOFF §0 adımı) · **Yöntem:** salt okuma
araştırması (araştırma ajanı) · **Hukuk tavsiyesi değildir; bir koşul okumasıdır.** Karar kullanıcınındır.

## Özet
1. **Türetilmiş olasılığı sitede göstermek (AK8 a) koşullarda açıkça izinli:** izin listesinde "türettiğin değerleri
   hesaplayıp göstermek" ve ticari kullanım dahil web sitesinde gösterim var; atıf zorunlu değil; plan ayrımı yok.
2. **Toplu indirilebilir döküm (AK21) koşulların tek açık yasağına en yakın nokta:** yasak, veriyi "bağımsız veri
   ürünü" olarak yeniden dağıtmak ve örnek olarak "downloadable files" sayıyor. Türetilmiş değerlerin dosyası buna
   girer mi — **BELİRSİZ — avukata/yazılı izne.** Spec önerisi (yalnız hash) koşullarla uyumlu kalır.
3. **`path_id` (AK20 b) için yasak bulunmadı**; olay kimliği hakkında koşullarda da belgelerde de madde yok
   (kalıcılığı belgelenmemiş — teknik risk, §17 ölçümü sürer). Kitap adı + fiyatı göstermek (AK8 c / AK9 b) The Odds
   API tarafında izinli görünüyor; asıl kısıt TR mevzuatı ve sorumlu oyun maddesi (spec §10.3).

## 0. Kapsam ve uyarı
- Okunan: the-odds-api.com'un kendi sayfaları (koşullar, SSS, belgeler, fiyat, widget). Bahisçilerin kendi koşulları,
  TR mevzuatı (7258, reklam), AB veritabanı hakkı **okunmadı** — kapsam dışı, §4'te soru olarak.
- Sayfalar WebFetch ile okundu; araç sayfayı bir özetleyici modelden geçirir. Aşağıdaki kısa alıntılar aracın
  "verbatim" isteğine döndürdüğü metindir; **karar vermeden önce kullanıcı alıntıları sayfada gözle doğrulamalı**
  (özellikle §2 Q2'nin dayanağı).
- **Ham metinle doğrulandı (2026-10-02, asistan, özetleyicisiz):** koşullar sayfası `curl` ile indirilip HTML'den arındırıldı; şu ifadeler sayfada birebir var: "Last updated: 31 August 2026" · Restrictions: "redistribute our data as a standalone data product" + örneklerde "downloadable files" · "provided our data is not the primary product" · "Calculating and displaying values you derive from our data" · "Attribution to The Odds API is not required". Q1, Q2 ve Q5'in dayanağı bu ölçümle sabit.
- Koşullar "yayımlandığında yürürlüğe girer", esaslı değişiklikte e-posta bildirimi var (Changes to These Terms).
  Bugünkü sürüm **31 August 2026** tarihli. Yayından önce yeniden okunmalı.
- Ayrı bir "Acceptable Use" sayfası yok; karşılığı koşulların içindeki *Appropriate Usage and Abuse* başlığı.

## 1. Okunan kaynaklar (okuma tarihi: 2026-10-02)

| URL | Başlık / bölüm | Not |
|---|---|---|
| https://the-odds-api.com/ | Ana sayfa: altbilgi bağlantıları, fiyat tablosu | Koşul bağlantısı altbilgiden bulundu |
| https://the-odds-api.com/terms-and-conditions.html | Terms and Conditions (son güncelleme 31 Aug 2026) | Başlıklar: Definitions · Market Data & Transparency · Liability · Force Majeure · **Restrictions** · API Key Responsibility · Cancellations & Refunds · Appropriate Usage and Abuse · **Responsible Gambling** · Changes to These Terms · Governing Law and Jurisdiction · Add-on Privacy |
| https://the-odds-api.com/manage/faqs.html | FAQ | 11 soru; hepsi faturalama/kredi/iletişim. Kullanım hakkı, ticari kullanım, atıf sorusu **yok** |
| https://the-odds-api.com/liveapi/guides/v4/ | API v4 belgeleri | Kullanım hakkı maddesi yok; olay `id`si yalnız uç noktalar arası eşleşme bağlamında anılıyor |
| https://the-odds-api.com/widget/ | Odds Widget | Ayrı ziyaret kotalı planlar; bahisçi affiliate bağlantısı destekleniyor |

WebSearch yalnız fiyat bilgisini çapraz kontrol için kullanıldı (üçüncü taraf blog; kanıt sayılmadı).

## 2. Bulgular

### Q1 — Türetilmiş/toplulaştırılmış olasılığı halka açık sitede yayımlamak · **SERBEST**
- *Restrictions* başlığındaki izinli kullanımlar listesi: verinin süresiz saklanması; arayüzde/web sitesinde/mobil
  uygulamada gösterimi, ticari kullanım dahil; araştırma ve analitik panolarda kullanımı; "Calculating and displaying
  values you derive from our data"; istatistik/ML modeli eğitimi.
- Ticari/ticari olmayan ayrımı: ayrım **yok**; ticari kullanım açıkça destekleniyor. Tek koşul, verinin satılan ya da
  dağıtılan **asıl ürün** olmaması ("provided our data is not the primary product", Restrictions).
- Sınır: sitemizin asıl ürünü konsensüs olasılığı listesi olursa "asıl ürün" koşulu tartışmaya açılır. Sicil, CLV ve
  analiz ile çerçevelenmiş bir site bu sınırın içinde görünüyor; ölçüt koşullarda tanımlı değil — "asıl ürün"ün
  nerede başladığı **BELİRSİZ** (§4/1).

### Q2 — Bütün maçların türetilmiş olasılıklarının indirilebilir JSON dökümü (`/data/snapshot.json`) · **BELİRSİZ — avukata/yazılı izne**
- *Restrictions*: "Do not resell, repackage, or redistribute our data as a standalone data product." Hemen ardından
  kapsam örneği: kendi API'n, veri akışı, **"downloadable files"** ya da başkalarına ham veri kaynağı olmaya yönelik
  herhangi bir biçim. Aynı başlıkta ana kaygı "rakip ürün" olarak ham veri akışı satmak diye açıklanıyor.
- Neden belirsiz: (i) izin listesi türetilmiş değerler için yalnız "hesaplamak ve **göstermek**"ten söz ediyor,
  dosya olarak dağıtmaktan değil; (ii) yasak "our data" diyor — vig'i çıkarılmış konsensüs olasılığının hâlâ "onların
  verisi" sayılıp sayılmadığı tanımlanmamış (Definitions'ta "Service" = API ve ilişkili piyasa verisi); (iii) dosyanın
  amacı doğrulama, ama makinece okunur, bütün maçları kapsayan, kalıcı URL'li bir dosya fiilen "başkalarına veri
  kaynağı" işlevi görebilir.
- Bedel ve risk: ihlal şüphesinde anahtar iptali ve erişim engeli (*Restrictions*, *Appropriate Usage and Abuse*:
  "terminate API access at any time without warning"). Proje defteri tek kaynağa bağlı; risk iş sürekliliği riski.

### Q3 — Olay kimliğinin türevini URL'de kamuya açık kimlik olarak kullanmak (`path_id`) · **SERBEST (dolaylı) — açık madde yok**
- Koşullarda olay kimliği, tanımlayıcı ya da URL hakkında madde **yok**. Kimlik API yanıtının bir alanı; gösterim
  izni (Q1) kapsamında okunabilir. Kimliğin öneki tek başına bir veri ürünü değil.
- Teknik not (hukuki değil): belgeler `id`nin kalıcılığı, ertelemede korunup korunmadığı ya da `commence_time`
  değişimi hakkında **hiçbir şey söylemiyor**; yalnız skor yanıtındaki `id`nin oran yanıtındakiyle eşleştiği yazılı.
  Spec §8.1/§17'deki "ertelemede korunduğu ölçülmedi" notu geçerli kalır.

### Q4 — Bahisçi adı + bahisçi fiyatı yayımlamak (kanıt satırı, AK9 b) · **The Odds API tarafında SERBEST (koşullu); TR mevzuatı ve marka tarafı BELİRSİZ — avukata**
- Ham veriyi web sitesinde göstermek izinli (Q1 listesi). Koşul aynı: bağımsız veri ürünü olarak dağıtmamak.
  Tahmin başına birkaç kanıt satırı bu sınırın içinde görünüyor; **tam defter dökümü (AK9 c)** ise bahisçi
  fiyatlarının toplu, indirilebilir bir dosyası olur ve Q2'deki "downloadable files" örneğine Q2'den daha yakındır →
  **İZNE BAĞLI** (yazılı izin olmadan yapılmamalı).
- Markalar: *Market Data & Transparency* üçüncü taraf markalarının sahiplerinde kaldığını söylüyor ve The Odds API'nin
  kendi kullanımını "yalnız tanımlama, betimleyici atıf, piyasaların olgusal karşılaştırması" ile sınırlıyor. Bize
  marka hakkı devretmiyor; bahisçi adını kullanmanın marka hukuku boyutu **BELİRSİZ** (§4/4).
- *Responsible Gambling*: veri bahisçileri/bahis hizmetlerini tanıtmak için kullanılırsa uygun sorumlu oyun mesajı
  gösterilmeli (örnek "Gamble Responsibly. 18+"); yerel mevzuata ve reklam standartlarına uyum **tamamen
  kullanıcının sorumluluğu**. Bahisçi adı + fiyatı göstermek TR'de bahis reklamı riskini (spec §10.3, 7258) doğrudan
  büyütür; The Odds API koşulları bu riski bize bırakıyor.
- Koşullar ayrıca The Odds API'nin hiçbir bahisçiyle bağlantılı olmadığını, verinin herkese açık kaynaklardan ve
  izinle erişilen üçüncü taraf akışlarından geldiğini söylüyor. Bahisçilerin kendi koşulları The Odds API'nin
  izniyle ortadan kalkmaz — bu okumanın kapsamı dışında (§4/3).

### Q5 — Atıf zorunluluğu · **SERBEST (zorunlu değil)**
- Koşullar: "Attribution to The Odds API is not required, but is always appreciated." Biçim şartı yok.
- Öneri: zorunlu olmasa da kaynak şeffaflığı için hakkında/şartlar sayfasında adıyla anmak bir maliyet taşımaz;
  ancak The Odds API'yi onaylayan/ortak gibi gösteren dil kullanılmamalı (koşulsuz bir yasak yok, ihtiyat).

### Q6 — Plan/abonelik türüne bağlı farklar · **SERBEST (kullanım hakkında plan ayrımı yok)**
- Koşullarda kullanım hakkını plana bağlayan madde **yok**; *Restrictions* bütün kullanıcılar için aynı.
- Planlar arası fark yalnız teknik/kota: ana sayfa fiyat tablosu Starter (ücretsiz) için "500 credits per month" ve
  "Most bookmakers", ücretli planlar için "All bookmakers" ve daha fazla kredi gösteriyor.
- Tutarsızlık (teknik, hukuki değil): fiyat tablosu metni Starter altında "Historical Odds" listeliyor; belgeler
  tarihsel uç noktalar için "only available on paid usage plans" diyor. Metin dönüşümü üstü çizili biçimi
  kaybetmiş olabilir — **BELİRSİZ**, plan seçerken sayfada gözle bakılmalı. DEFERRED 10m (kredi bütçesi) ile ilgili.
- Widget ayrı bir üründür (ziyaret kotalı ayrı planlar); bizim kullanımımızla ilgisi yok.

### Önceki belgelerle çelişki kontrolü
- `docs/reports/2026-09-23-kaynak-kosullari.md` The Odds API hakkında bir şey yazmıyor → çelişki yok.
- `docs/superpowers/specs/2026-09-19-football-edge-design.md` §kaynak tablosu: "Ticari hizmet; 'lisanslı' iddiası yok".
  Bugünkü metinle **uyumlu**: koşullar bahisçilerden lisans iddia etmiyor; kaynak olarak herkese açık sayfalar ve
  "express permission" ile erişilen üçüncü taraf akışlarını sayıyor. Ek bilgi: bağımsızlık beyanı ve NSW hukuku.
- Spec B7 / phases/06-site HANDOFF C9 "koşullar okunmadı" diyor → bu raporla kapanır (karar kullanıcıda).
- HANDOFF'taki "kabul edilebilir kullanım sayfası" ayrı sayfa olarak yok (§0).

## 3. Açık kararlar için sonuç ve öneri

| AK | Spec önerisi | Koşulların söylediği | Öneri |
|---|---|---|---|
| **AK8** | (a) yalnız vig'siz olasılık | (a) açıkça izinli ("derive + display", ticari dahil). (c) de The Odds API tarafında izinli, ama sorumlu oyun maddesi ve yerel mevzuat sorumluluğu bize kalıyor | **(a) değişmeden.** Koşullar (a)'yı engellemiyor; (c)'yi engelleyen The Odds API değil, TR mevzuatı (§10.3) — ayrı karar |
| **AK9** | Şimdi (a); (b)/(c) AK8(c)+AK17'ye bağlı | (a) etkilenmez. (b) birkaç kanıt satırı gösterimi: izinli görünüyor. (c) tam defter dökümü = bahisçi fiyatlarının indirilebilir toplu dosyası → "downloadable files" örneğine en yakın | **Şimdi (a).** (b) yalnız AK8(c) TR-mevzuat açısından onaylanırsa; (c) **yazılı izin olmadan hayır** |
| **AK20 (b)** | `path_id` = olay kimliği öneki | Kimlik/URL hakkında madde yok; yasak bulunmadı | **(b) sürer.** Hukuki engel yok; kimliğin ertelemede kalıcılığı belgelerde yok → §17 ölçümü ve 301 yönlendirme güvencesi aynen |
| **AK21** | Yalnız hash, AK17'ye kadar | Toplu indirilebilir dosya, yasağın kendi örneğine ("downloadable files") dokunuyor; türetilmiş değerin "our data" sayılıp sayılmadığı tanımsız | **Yalnız hash sürer.** Dosyayı açmak için yol: (i) §5'teki e-postayla yazılı izin, ya da (ii) avukat görüşü. Bedeli spec'te adıyla yazılı: hash doğrulama değil taahhüttür (§6.1) |

Kapsam notu: §8.1'in `/data/slugs.json`ı yalnız slug taşıyor, oran/olasılık taşımıyor → Q2 kapsamında değil.

## 4. Avukata sorulacaklar
1. "Primary product" / "standalone data product" ölçütü: konsensüs olasılığı gösteren, sicil/CLV ile çerçevelenmiş
   ücretsiz bir site bu sınırın neresinde? Site ileride gelir modeli (reklam/affiliate/abonelik) eklerse değişir mi?
2. Vig'i çıkarılmış, birden çok bahisçiden türetilmiş olasılık sözleşmedeki "our data" kapsamında mı? Türetilmiş
   değerlerin **indirilebilir** toplu dosyası (`snapshot.json`) "redistribute ... downloadable files" yasağına girer mi?
3. The Odds API verisini herkese açık bahisçi sayfalarından topluyor. Bahisçilerin kendi kullanım koşulları ya da AB
   veritabanı hakkı (96/9/EC sui generis) türetilmiş olasılığın ya da ham fiyatın yayımına karşı bize yöneltilebilir mi?
4. Bahisçi adını (marka) olgusal karşılaştırma için anmak TR ve hedef ülkelerde marka hukuku açısından serbest mi?
5. TR: bahisçi adı + fiyatı, ya da yalnız türetilmiş olasılık yayımlamak 7258 sayılı Kanun ve reklam mevzuatı
   açısından yasa dışı bahis reklamı/teşviki sayılır mı? (Spec §10.3 ile aynı soru; The Odds API koşulları bu
   sorumluluğu açıkça kullanıcıya bırakıyor.)
6. Sözleşme NSW (Avustralya) hukukuna tabi ve NSW mahkemeleri münhasır yetkili; tüketici olmayan bir TR kullanıcısı
   için pratik anlamı ve tek taraflı değişiklik maddesinin (yayımlandığı an yürürlük) geçerliliği.

## 5. Yazılı izin taslağı (GÖNDERİLMEDİ — kullanıcı onayı olmadan gönderilmez)

Alıcı (altbilgideki iletişim adresi): team@the-odds-api.com

> **Subject:** Permission question: publishing derived consensus probabilities and a verification file
>
> Hello The Odds API team,
>
> I am an API user building a small, free website about football betting markets [non-commercial today — confirm
> before sending; mention any planned revenue model]. I would like
> to confirm that the following uses fit your Terms and Conditions (version dated 31 August 2026):
>
> 1. Match pages show only a consensus probability per outcome (e.g. "home 47%") that we derive from several
>    bookmakers' prices with the margin removed. No bookmaker names, no raw prices, no links.
> 2. A downloadable JSON file (/data/snapshot.json) containing those derived probabilities for all listed matches,
>    published so that readers can verify that the pages match our records. It would contain no raw bookmaker
>    prices and no bookmaker names.
> 3. Using a short prefix of your event id as a stable identifier in our page URLs.
> 4. In future, for each published prediction only, showing a few "evidence" rows with the bookmaker name and the
>    price we recorded at that time.
>
> We do not offer an API, data feed or any paid data product. Could you confirm whether items 1-4 are permitted,
> and whether item 2 would count as redistribution under the Restrictions section? If any item needs a different
> plan or a separate agreement, please let us know.
>
> Thank you,
> [name]

## Yöntem
WebFetch ile 5 sayfa (koşullar sayfası birden çok soruyla 4 kez), WebSearch 1 kez (fiyat çapraz kontrolü, kanıt
sayılmadı). Form, hesap, banner, e-posta yok. Depoda salt okuma: spec §16 (AK8, AK9, AK17, AK20, AK21), §6.1, §6.3,
§8.1; `docs/reports/2026-09-23-kaynak-kosullari.md`; `docs/HANDOFF.md`, `docs/phases/06-site/HANDOFF.md` C9,
`docs/superpowers/specs/2026-09-19-football-edge-design.md` kaynak tablosu (çelişki taraması).
