# football-edge — Oturum Devri (Handoff)

**Son güncelleme:** 2026-10-02 (oturum 10b kapanışı) · **Sıradaki oturum: KULLANICI OTURUMU (§0)** — kullanıcının
bütün işleri (§0.önceki/0.K) asistan rehberliğinde adım adım, tek oturumda · **Durum:** asistanın kullanıcısız işi yok;
`main` = `dcf8648`, CI yeşil · **0013 CANLIDA**, **0014 yalnız depoda**, deploy BAĞLI DEĞİL · ilk kulüp maçları
**2026-10-09/10** · Plan 2 en erken **2026-10-07** · holdout açılmadı

> Giriş sırası: `README.md` → bu dosya → `docs/DEFERRED.md`.
> **Faz 3'ün devir belgesi ve "ölçülmeyenler" listesi: `docs/phases/03-baz-model/HANDOFF.md` §3.**
> Faz 2'nin devir belgesi ve "ölçülmeyenler" listesi: `docs/phases/02-tarihsel-taban/HANDOFF.md` §3.**
> Faz 1'inki: `docs/phases/01-toplayicilar/HANDOFF.md` §3. Faz 0'ınki: `docs/phases/00-kayit-altyapisi/HANDOFF.md` §3.
> Arıza prosedürleri: `docs/RUNBOOK.md`.

---

## 0. KULLANICI OTURUMU — BURADAN BAŞLA (yazıldı 2026-10-02, oturum 10b kapanışı)

Bu oturumun amacı: **kullanıcının yapması gereken her şeyi (§0.K) tek oturumda, asistan adım adım yönlendirerek
bitirmek.** Asistanın kullanıcısız işi kalmadı (oturum 10/10b hepsini kapattı — §0.önceki/0.2a–0.2b). Aşağıdaki
yol haritası sıralıdır; her adım bir öncekinin çıktısına dayanabilir. Ayrıntılı gerekçeler §0.önceki/0.K'dedir
(K/n numaraları aynı). Tahmini toplam süre: **3–4 saat** (hukuk görüşmesi hariç — o oturum dışında).

### 0.0 Başlatma istemi (taze oturuma yapıştır)
> "`docs/HANDOFF.md` §0 KULLANICI OTURUMU'ndan başla. Önce §0.3 açılış kontrollerini yap (salt okuma, bana 5 satır
> özet). Sonra §0.4 yol haritasını Adım 1'den başlayarak yürüt: her adımda bana ne yapacağımı tıklama tıklama anlat,
> benim 'tamam'ımı bekle, sonra kendi kısmını yap ve doğrula, ilerlemeyi deftere yaz, bir sonraki adıma geç.
> Kararlarda önerini söyle; secret'ları asla sohbete yazdırma."

### 0.1 Durum (ölçüldü 2026-10-02, salt okuma)
- **Dal:** `main` = `origin/main` = `dcf8648`; yerelde yalnız `main`, worktree yok (K/S temizliği yapıldı).
- **CI ve zamanlanmış işler yeşil** (son 40 koşuda kırmızı yok). Yeni kodla `seal` (`09052d4`) yeşil.
- **Kapı:** 16 PASS + adıyla 3 SKIP (`site-db`, `site-derleme/e2e`, `zincir`); komut §0.önceki/0.1. pytest ~3750.
- **Canlı DB:** 0013 canlıda, **0014 YALNIZ depoda**. Supabase advisors yalnız INFO. `site_reader` rolü yok (0014 kurar).
- **Site:** `web/site.config.ts`: `SITE_NAME = "Goool"` (2026-10-02, Adım 5); yer tutucular `SITE_URL = "https://example.invalid"`,
  `LEDGER_HISTORY_URL = "https://example.invalid/ledger"`. `site.yml` hiç koşmadı (yalnız elle tetiklenir).
  `environment: production` hem `build` hem `deploy` işinde (Adım 3, `af34af2`); ortamda dal kuralı `main` +
  Required reviewers `popiliadam` (API ölçüldü 2026-10-02).
- **Holdout:** açılmadı. Maçlar: ilk kulüp maçları 10-09/10; fikstürler ~10-02/03'te `snapshot` ufkuna girer.
- **Araç:** `psql` PATH'te değil; kurulu: `/opt/homebrew/opt/libpq/bin/psql` (Adım 14'te bu yol kullanılır).

### 0.2 Asistan için oturum kuralları (bu oturuma özel — §0.önceki/0.D da geçerli)
1. **Tek adım, tek seferde.** Her adımda: (a) neden şimdi, (b) kullanıcının yapacakları numaralı tıklama listesi, (c)
   kullanıcının bana söyleyeceği tam cümle, (d) "bitti" ölçütü. Kullanıcı "tamam" demeden asistan kendi kısmına geçmez.
2. **Secret'lar sohbete girmez:** token, parola, bağlantı dizesi kullanıcı tarafından doğrudan GitHub/Supabase
   arayüzüne ya da kullanıcının KENDİ terminaline yazılır. Asistan terminal panelini (`read_terminal`) parola girilen
   adımlarda OKUMAZ. Kullanıcı yanlışlıkla yapıştırırsa: hemen "o değeri döndür (rotate)" de, adımı tekrarlat.
3. **Kararlarda öneri ver** (bellek `user-delegates-to-recommendation`): seçenekleri kısa yaz, önerini ilk sıraya koy.
   "En iyi senaryo / senin önerin" cevabı = öneriyle devam; ama para, hukuk, dış iletişim ve geri alınamaz adımlar
   için kullanıcının AÇIK "evet"i şart.
4. **İlerleme defteri:** `.superpowers/sdd/_kalici/kullanici-oturumu/ilerleme.md` (gitignored, kalıcı). Her adım
   bitince bir satır: `Adım N: bitti — <karar/çıktı> — <commit varsa>`. Bağlam sıkışırsa defter + `git log` esastır.
5. **Kod değişiklikleri:** her biri test + mutasyon kanıtı + tam kapı + commit + `git fetch && git merge --no-ff
   origin/main` + `grep -q "KAPI YEŞİL" <log> && git push`; CI koşarken yeni push yapma. Kod değişikliği küçükse
   asistan kendisi yapar; 50 satırı aşan ya da güvenlik sınırına dokunan değişiklik için bir bağımsız inceleme ajanı
   (general-purpose, sahte ikililer kuralı — bellek `probes-fake-binaries`).
6. **Canlı DB yazımı:** §0.önceki/0.D "Canlı DB'ye yazım" kuralı aynen (sessiz aralık, ROLLBACK provası, metin bayt
   bayt, sha256 deftere, sonra salt okuma doğrulaması + advisors + sonraki mühür turunun yeşili).
7. **Ücret açan commit'i asistan yapamaz** (bellek `credit-activation-commit-blocked`): kullanıcıya tek satır verilir.
8. **Bağlam %95'e gelirse** (bellek `handoff-before-compaction`): koşan adımı bitir, defteri ve bu §0'ı güncelle,
   commit/push, yeni oturumda kaldığı adımdan devam.

### 0.3 Açılış kontrolleri (asistan, ~5 dk, salt okuma — kullanıcıya 5 satır özet)
1. `git fetch && git status -sb && git log --oneline -3` — `main` temiz mi, bot commit'leri dışında yeni bir şey var mı.
2. `gh run list --limit 30` — kırmızı koşu var mı (varsa önce o; RUNBOOK).
3. **§0.İ/1 (10-02/03 `snapshot`):** son `snapshot` logunda `yazılan satır` > 0 mı, lig başına `ufuktaki fikstür`.
   Exit 19 tek seferse beklenen (RUNBOOK §3.11); 10-04'ten sonra hâlâ 0 ise arıza.
4. Supabase advisors (`get_advisors security`) — yalnız INFO beklenir.
5. İlerleme defteri varsa oku, kaldığı adımdan devam; yoksa oluştur (ilk satır: tarih + `main` SHA'sı).

### 0.4 Yol haritası — adım adım

Sıra mantığı: önce **ücretsiz ve geri alınabilir** işler (temizlik, güvenlik ayarı, kararlar), sonra **para ve
hesaplar**, sonra **canlı veritabanı**, en son **ilk derleme** ve **hukuk paketi**. Hukuk onayı gelmeden site
YAYIMLANMAZ (K/7: "yayından ÖNCE avukat") — bu oturumun son hâli "yayına hazır, avukat bekleniyor"dur.

> **SIRA DEĞİŞİKLİĞİ (kullanıcı kararı, 2026-10-02, Adım 5'te):** önce **yerelde tam test**, alan adı ve Netlify
> sonra. Marka adı **Goool** (AK3, koda girdi); alan adı adayı **goool.ai** (whois 2026-10-02 boş; Netlify .ai
> satmıyor → kayıt yeri önerisi Porkbun + Netlify DNS nameserver) — **satın alınmadı**, `SITE_URL` bilerek yer
> tutucu kalır. Geçerli sıra: 1–9 aynen → **10–11 ERTELENDİ** (yayın aşamasına) → 12–14 aynen, tek farkla:
> `SITE_DATABASE_URL` şimdilik GitHub'a değil depodaki gitignored **`.env`**'e (değer ekrana basılmaz; GitHub
> secret'ı yayın aşamasında) → **15 YEREL prova** (gerçek veriyle `site export` + `verify-snapshot` + `pnpm -C web
> run build` + `check-out` + yerel statik sunucuda tarayıcı panelinde gezinti; `site_publish.py slugs/live`
> yer tutucuyla bilerek kırmızı — beklenen) → 16 avukat paketi (ekran görüntüleri yerel provadan) → 17 kapanış.
> **Yayın aşaması (sonra):** goool.ai alımı → ayrı Netlify hesabı → secret'lar → `SITE_URL` → CI `site.yml` provası
> → avukat onayıyla ilk yayın.

---

#### FAZ 1 — Temizlik ve güvenlik ayarları (~20 dk, ücretsiz)

**Adım 1 — Kalan silmeler (K/S kalanı, 2 dk).**
- Kullanıcı: yalnız onay. Söyleyeceği: *"t6-rls ve rev kaplarını ve uzak faz-0 dalını sil."* (İstemezse: "dokunma".)
- Asistan: `docker ps -a` ile `t6-rls-pre`, `t6-rls-sandbox`, `t6-rls-pg`, `rev8-pg`, `rev9-pg` adlarını ve
  durumlarını (Exited) gösterir, tek tek `docker rm <ad>`; uzak dal için `git merge-base --is-ancestor
  origin/faz-0-kayit-altyapisi main` (birleşmiş olmalı) sonra `git push origin --delete faz-0-kayit-altyapisi`
  (outward işlem — onay kapısı soracak, kullanıcı onaylar). Tag `archive/measure-r104-width`e DOKUNMA.
- Bitti: `docker ps -a | grep -E '^(t6-rls|rev[89])'` boş; `git ls-remote origin` yalnız `main` + tag.

**Adım 2 — Supabase "Exposed schemas" kontrolü (K/13 birinci yarı, 5 dk).**
- Neden: pg_net'in `net` şeması API'ye açıksa anon anahtarla dışarıdan GitHub tokenlı kuyruk okunabilir.
- Kullanıcı:
  1. https://supabase.com/dashboard → giriş → proje **`aaxadphezxavohkhqdrf`**.
  2. Sol alt **Project Settings** (dişli) → **Data API** (eski arayüzde "API").
  3. **"Exposed schemas"** alanına bak. Olması gereken: `public`, `graphql_public`. **`net` varsa** yanındaki ×'e bas
     → **Save**. (`site`, `site_input`, `site_audit` da OLMAMALI.)
  4. Aynı sayfada "Extra search path" alanını da oku (değiştirme).
- Söyleyeceği: *"Exposed schemas: <gördüğün liste>. Extra search path: <liste>. net yoktu / vardı, kaldırdım."*
- Asistan: deftere yazar. `net` vardıysa olay olarak §0.R'ye not düşer (ne zamandır açıktı bilinmez — GitHub
  tokenının döndürülmesini önerir: Adım 2b).
- **Adım 2b (yalnız `net` açıktıysa):** pg_cron dispatch'lerinin kullandığı GitHub tokenını döndür — asistan
  RUNBOOK'tan tokenın adını/yerini bulur ve kullanıcıya GitHub → Settings → Developer settings → tokens yolunu tarif eder.

**Adım 3 — GitHub `production` ortamı (K/14 birinci yarı, 5 dk).**
- Neden: site secret'ları yalnız `main` dalından ve ortam kapsamlı okunmalı; ayrıca "Required reviewers" ile her
  yayından önce senin onayın istenir — avukat gelmeden yanlışlıkla yayın olmaz.
- Kullanıcı:
  1. https://github.com/popiliadam/football-edge → **Settings** → sol menü **Environments**.
  2. `production` varsa tıkla; yoksa **New environment** → ad: `production` → **Configure environment**.
  3. **Deployment branches and tags** → **Selected branches and tags** → **Add deployment branch or tag rule** →
     `main` → **Add rule**.
  4. **Required reviewers** kutusunu işaretle → kendini (`popiliadam`) ekle → **Save protection rules**.
     (Öneri: işaretle. Etki: `site.yml`in her işi senin "Approve" tıklamanı bekler.)
  5. Henüz secret EKLEME (Adım 11 ve 14'te).
- Söyleyeceği: *"production ortamı hazır: dal kuralı main, required reviewer ben."*
- Asistan: `site.yml` `build` işine `environment: production` ekler (bugün yok; yoksa ortam secret'ı build'e görünmez
  → exit 20). `tests/test_site_workflow.py`ye "build ve deploy aynı ortamı kullanır" testi + mutasyon (satırı sil →
  kırmızı); tam kapı; commit `ci: site build işi production ortamında`; push; CI yeşil.
- Bitti: CI yeşil; testte iki iş de `environment: production`.

---

#### FAZ 2 — Kararlar (~60–90 dk, yalnız konuşma; para yok)

**Adım 4 — İz B onayları (K/10, 10 dk).**
- Asistan önce spec `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md` §16 tablosunu 22 satırlık kısa liste
  olarak gösterir (her satır: soru · öneri · etkisi). Öneriler: AK1 A · AK2 spec onayı (sicil boş metni §6.2) ·
  AK5 en+tr · AK6 §4.3 listesi · AK8 (a) vig'siz olasılık · AK9 (a) · AK10 skor yok · AK11 hayır · AK12 analitik
  yok · AK14 AK3/AK4/AK13'ten sonra · AK15 günlük + saatlik mühür sonrası · AK16 CLI · AK19/AK20 uygulandı ·
  AK21 yalnız hash · AK22 tabandan beri hepsi.
- Kullanıcı söyleyeceği: *"Önerilerle onay"* ya da farklı istediği satırlar. **AK17 için:** *"AK17 araştırmasını yap."*
- Asistan:
  - Onayı deftere ve spec §16'ya "Onaylandı 2026-10-xx (kullanıcı)" olarak işler (commit `docs:`).
  - AK2 ile bağlı metin düzeltmelerini uygular: DEFERRED 20b (en `record.emptyExplain` sabitlenir), 20g ("to be
    registered in advance"), 20e (yerel saat diliminin adı) — her biri test + kapı.
  - **AK17:** The Odds API Terms of Service + kabul edilebilir kullanım sayfasını salt okuma okur (WebFetch;
    yalnız okuma, form yok), "türetilmiş olasılığı halka açık sitede yayımlamak" açısından özet raporu
    `docs/reports/2026-10-xx-odds-api-kosullari.md`ye yazar, 3 satır sonuç söyler. Yasak çıkarsa AK8/AK9/AK21
    yeniden kullanıcıya sorulur (öneri: kaynak adı gösterilmeden yalnız toplulaştırılmış olasılık, ya da yazılı izin).
- Bitti: spec onay satırı commit'li; AK17 raporu commit'li ve kararı deftere yazılı.

**Adım 5 — Marka adı (K/1, 10 dk).**
- Kullanıcı: sitenin adını seçer. Asistan isterse 5 öneri sunar (kısa, .com alınabilirliği Adım 10'da denetlenir;
  "bahis/bet/iddaa" sözcüğü İÇERMEMELİ — TR riski K/7/2).
- Söyleyeceği: *"Marka adı: <Ad>."* (Alan adı farklı olacaksa onu da.)
- Asistan: `web/site.config.ts` `SITE_NAME`; yasal taslaklardaki `[site-name]` yer tutucuları
  (`.superpowers/sdd/_kalici/hukuk-taslak-metin/` + `web/content/` altındaki karşılıkları — `grep -rn "\[site-name\]"`);
  `Organization` JSON-LD; sayfa başlıkları. Testler + `check-out` + tam kapı; commit `feat: marka adı`.
- Bitti: `grep -rn "\[site-name\]" web/ docs/` → 0 (taslak dizini hariç değil: o da güncellenir).

**Adım 6 — TFF koşulları (K/12, 5 dk).**
- Seçenekler: (a) `tff` kaynağını kapat · (b) ticari lansmana kadar sürdür, lansmandan önce TFF'den izin iste ·
  **(c) avukata sor, o zamana kadar yalnız iç kullanım (sitede gösterilmez) — ÖNERİ**. Ayrıca
  `tests/fixtures/tff/` tam sayfa kopyalarının kırpılması: **öneri evet**.
- Söyleyeceği: *"TFF: (c). Fixture'ları kırp."*
- Asistan: kararı `sources.yaml` yorumuna/kaynak politikası notuna yazar; fixture kırpma (hakem adları dahil gerçek
  kişi adları takma adla; testler aynı davranışı ölçmeli) — test + kapı + commit. Avukat sorusu Adım 16 paketine.

**Adım 7 — Haber kaynağı politikası (K/4, 15 dk).** Girdi: `docs/reports/2026-09-23-kaynak-kosullari.md`,
`docs/reports/2026-09-23-ek-kaynaklar.md` — asistan her alt soru için 3 satırlık özet verir.
- (a) EN — GDELT ayağı: **öneri: şimdilik HAYIR** (izin listesi GDELT'te fiilen boş: sessiz pay %3,0; en sık 15 alan
  adının 12'si yasaklıyor). EN kaynağı (c)'deki ücretli/resmî yoldan gelir.
- (b) CaughtOffside/JustArsenal (Rocket Sports, £500/makale "Search Only"): **öneri: kesin dışarıda**
  (`sources.yaml`a `enabled: false` + gerekçe; erişim kapısı bu alan adlarını reddeder).
- (c) Ücretli: SportMonks Starter (€29/ay; 14 gün deneme = hesap açmak SENDE) · X API (~$60/ay).
  **Öneri:** önce SportMonks 14 günlük deneme (yapılandırılmış sakat/cezalı — sağlık verisi sorusu K/7/1 avukata);
  X API şimdilik hayır. Hesap açılırsa API anahtarı GitHub secret'ına SEN eklersin (ad asistan söyler).
- (d) TR: ajansspor (zaten) + Fotomaç/A Spor RSS + TFF PFDK (Adım 6'ya bağlı) + Galatasaray RSS — **öneri: ajansspor +
  Fotomaç RSS + A Spor RSS**; kulüp RSS'leri ve PFDK avukat sonrası.
- (e) ajansspor 17l: **öneri: robots `Content-Signal: ai-input=yes, ai-train=no` yeterli say** (Jev'e başlık vermek
  "input"tur, eğitim değil); yayıncıya yazmak dış iletişim — istersen metni asistan hazırlar, SEN gönderirsin.
- Söyleyeceği: *"K/4: a hayır, b dışarıda, c SportMonks denemesi (hesabı ben açarım) / hayır, d <seçim>, e yeterli."*
- Asistan: `sources.yaml`a seçilen kaynakları `enabled: true` + robots anlık görüntüsü + koşul kanıtı ile ekler (R77b
  erişim kapısı, `scrape.py` tek geçit), toplayıcıları yazar — bu bir **kod dalgası**dır: oturum içinde vakit varsa
  yapılır (inceleme ajanıyla), yoksa deftere "Plan 2 kademe 2'ye" yazılır. Karar her durumda deftere + §0.K/4'e işlenir.

**Adım 8 — Dil kalibrasyonu etiket onayı (K/5, 45–60 dk — oturumun en uzun adımı).**
Dosya: `.superpowers/sdd/_kalici/kalibrasyon-onay/tr.review.md` (174 satır, 100 madde). Asistan dosyayı kullanıcıyla
birlikte yürür; kullanıcı dosyayı düzenlemez, kararları SÖYLER, asistan yazar.
1. **Açık soru (§0 dosyada):** "yaklaşan maç" (A) yayın anına göre — **öneri (A)** — ya da (B) bugüne göre.
   Söyleyeceği: *"A."*
2. **`team` yazımı:** asistan önce üretimde Jev'e giden `club` dizesinin kaynağını kodda gösterir (hangi yazım
   üretimde kullanılıyorsa kalibrasyon da onu kullanmalı — öneri bu). Söyleyeceği: *"Üretimdeki yazımı kullan."*
3. **6 uyuşmazlık:** asistan her birini tek tek gösterir (başlık · iki öneri · gerekçe). Kullanıcı her biri için
   *"true"* / *"false"* der.
4. **29 sınırda madde:** 5'erli gruplar hâlinde; her grup için kullanıcı *"hepsine katılıyorum"* ya da *"N numara
   false olsun"* der.
5. **65 net madde:** asistan tek tabloda gösterir; kullanıcı *"hepsine katılıyorum"* ya da itirazlarını söyler.
6. **Etiketleyen adı:** kullanıcı adını söyler (README: `data/calibration/tr.meta.json`a girer).
7. **Başlık telifi:** K/7/5 avukatta çözülene kadar **öneri: depoya yalnız `id` + etiket + kulüp + dil**; başlık
   metni gitignored `_kalici`de kalır (ölçüm yerelde başlıkla koşar).
- Asistan: `data/calibration/tr.jsonl`i (bugün BİÇİM ÖRNEĞİ, 10 satır — README §"BUGÜNKÜ içeriği") onaylı 100
  etiketle değiştirir, `tr.meta.json` yazar, README'yi günceller, `calibration.load_labels` + testler + kapı; commit.
  Sınıf dağılımını (true/false sayısı) ve (A)/(B) seçimini meta'ya yazar.
- Bitti: `load_labels` 100 satır okur; meta'da ad + tarih + seçimler.

**Adım 9 — Ücretli Jev (K/6, 5 dk karar).**
- Bugün ölçümü koşturan CLI YOK (`calibration.run_calibration` var, komut satırı yok — Plan 2 T3 işi). Bu yüzden:
  **bu oturumda yalnız karar alınır**, ücret açan commit Plan 2 T3'te (≥ 10-07) yapılır.
- Asistan söyler: tahmini maliyet (100 madde × fiyat — `jev_budget` ve TypeSafe fiyatından hesaplar), tavan
  `MONTHLY_CAP_USD = 25.0`.
- Söyleyeceği: *"Jev ücretli ölçümünü onaylıyorum, aylık tavan 25 $ (ya da: <tutar>)."*
- Asistan: deftere ve §0.K/6'ya "onaylı, commit Plan 2 T3'te kullanıcıya tek satır verilecek" yazar.

---

#### FAZ 3 — Para ve hesaplar (~40 dk)

**Adım 10 — Alan adı + ayrı Netlify hesabı (K/2, 25 dk; ödeme SENDE).**
- Neden ayrı hesap: Netlify kişisel erişim tokenı site başına kısıtlanamaz; hesabın bütün sitelerine yetkilidir (AK18).
- Kullanıcı:
  1. **Yeni Netlify hesabı:** https://app.netlify.com/signup — bu siteye özel bir e-posta (ör. `+site` takma adı)
     ile kaydol. (Mevcut Netlify hesabına yeni ekip açmak da olur ama token yine hesabın her şeyine yetkili — ayrı
     hesap öneri.)
  2. **Boş site oluştur:** **Add new project → Deploy manually** → masaüstünde içinde tek `index.html` ("yakında")
     olan bir klasör sürükle. (Asistan bu dosyayı `noindex` meta'lı hazırlar ve yolunu söyler.)
  3. **Site ID:** Project configuration → General → Project details → **Project ID** — kopyala (gizli değil ama
     yine de doğrudan GitHub'a yapıştır).
  4. **Token:** sağ üst avatar → **User settings → Applications → Personal access tokens → New access token** →
     açıklama `football-edge GitHub Actions`, son kullanma 90 gün (takvime yenileme notu) → kopyala (bir kez görünür).
  5. **Alan adı:** öneri Netlify içinden satın al (DNS otomatik): Domain management → **Add a domain → Register a new
     domain** → Adım 5'teki ad → WHOIS gizliliği AÇIK → öde. (Başka kayıtçıdan alırsan: Namecheap — sonra Netlify
     DNS'e nameserver yönlendirmesini asistan tarif eder. Cloudflare Registrar Cloudflare DNS'i zorunlu kılar; o
     yolda Netlify'a CNAME kayıtları gerekir.)
  6. HTTPS: Domain management → HTTPS → "Verify DNS / Provision certificate" (otomatik; birkaç dk–saat sürebilir).
- Söyleyeceği: *"Netlify hazır. Alan adı: <alan>. Token ve Site ID elimde (sohbete yazmıyorum)."*

**Adım 11 — Netlify secret'larını GitHub'a ekle (K/14 ikinci yarı, 5 dk).**
- Kullanıcı: GitHub → Settings → **Environments → production → Environment secrets → Add environment secret**:
  1. Ad `NETLIFY_AUTH_TOKEN`, değer: Adım 10/4'teki token.
  2. Ad `NETLIFY_SITE_ID`, değer: Adım 10/3'teki ID.
  (Repository secrets'a DEĞİL, ortam secret'ına.)
- Söyleyeceği: *"İki Netlify secret'ı production ortamına eklendi."*
- Asistan: `gh api repos/popiliadam/football-edge/environments/production/secrets` ile yalnız ADLARI doğrular;
  `web/site.config.ts` `SITE_URL` ve `LEDGER_HISTORY_URL` → `https://<alan>` (ve `…/ledger`); site haritası/hreflang/
  canonical testleri + `site_publish.py` yayın bekçileri (yer tutucuda kasıtlı kırmızıydı — artık gerçek alanla)
  + tam kapı; commit `feat: gerçek alan adı`; push.
- Bitti: secret adları listede; `grep -rn example.invalid web/ scripts/` → 0.

---

#### FAZ 4 — Canlı veritabanı: okuma katmanı (~40 dk)

**Adım 12 — 0014'ü canlıya uygula (K/3, 15 dk; asistan yapar, sen onaylarsın).**
- Söyleyeceği: *"AK6 = §4.3 listesi, 0014'ü uygula."*
- Asistan (`docs/phases/06-site/HANDOFF.md` "Canlıya geçiş" adım 2): sessiz aralık (:00/:15/:30/:45 dışı,
  `gh run list --status in_progress` boş) → `db/migrations/0014_site_read.sql` metni bayt bayt, sha256 deftere →
  aynı SQL `begin … rollback` kuru koşusu (sonuç `raise exception` JSON'unda) → `apply_migration` **`postgres` rolüyle**
  (görünüm sahibi = tablo sahibi; aksi hâlde RLS'li tablolar görünümden hatasız 0 satır döner) → katalog testleri canlıya
  salt okuma (`tests/test_site_views_db.py` vb. RUNBOOK §2.5 komutuyla, `--tb=short`) → `get_advisors security` +
  `performance` → bir sonraki `seal` turu yeşil.
- Bitti: advisors'ta yeni ERROR/WARN yok; `site` şeması görünümleri canlıda; seal yeşil.

**Adım 13 — `site_reader` artık riskini kabul (K/13 ikinci yarı, 5 dk; açık karar).**
- Asistan: canlıda `site_reader` etkin yetkilerini salt okuma sorgusuyla ölçer (`net` şeması dahil) ve
  `tests/test_site_views_db.py` `PG_NET_RELATIONS`/`PG_NET_FUNCTIONS` kabul listesiyle karşılaştırır; liste dışı
  yetki varsa DURUR. Sonra riski düz dille anlatır: LOGIN'li `site_reader` `net.http_post` ile DB sunucusundan dışa
  istek atabilir ve `net.http_request_queue`yu (pg_cron'un GitHub tokenını taşır) okuyup yazabilir; bunu `postgres`
  geri alamaz (Supabase'in `supabase_admin` yetkisi); parola yalnız GitHub `production` ortam secret'ında durur.
- Söyleyeceği (kabul ediyorsa): *"site_reader için pg_net artık riskini bilerek kabul ediyorum."* Kabul etmiyorsa:
  *"Kabul etmiyorum"* → site adımları burada durur; asistan alternatifi (dışa aktarımı `postgres` yerine
  Actions'ta geçici rolle yapmak vb.) DEFERRED'a yazar.

**Adım 14 — `site_reader` parolası ve `SITE_DATABASE_URL` (K/15, 15 dk).**
- Kullanıcı (KENDİ terminalinde — Claude uygulamasının Terminal paneli olur; asistan bu sırada paneli OKUMAZ):
  1. Parola üret (URL kodlaması gerektirmesin diye yalnız hex): `openssl rand -hex 24` → çıktıyı bir yere not et
     (parola yöneticisi).
  2. `postgres` olarak bağlan — en kolayı depodaki `.env`in `DATABASE_URL`si (zaten session pooler, `postgres`):
     `cd ~/dev/football-edge && /opt/homebrew/opt/libpq/bin/psql "$(grep '^DATABASE_URL=' .env | cut -d= -f2- | tr -d '"')"`
     (Değer ekrana basılmaz. Veritabanı parolasını SIFIRLAMA — `DATABASE_URL` secret'ı ve bütün zamanlanmış işler kırılır.)
  3. Bağlandığını gör: istem `postgres=>` olmalı.
  4. psql içinde: `\password site_reader` → parolayı iki kez yapıştır (ekranda görünmez) → `\q`.
     (`ALTER ROLE … PASSWORD` KULLANMA — DDL loglanırsa düz metin kalır.)
  5. Söyleyeceği: *"site_reader parolası ayarlandı."*
- Asistan: `site_reader`a `LOGIN` veren küçük migration (`0015_site_reader_login.sql`; test + kum havuzu + Adım 12'deki
  canlı yazım kuralı) → uygular → doğrular (`rolcanlogin = true`, diğer yetkiler değişmedi).
- Kullanıcı (devam):
  6. `SITE_DATABASE_URL`yi kur: `postgresql://site_reader.aaxadphezxavohkhqdrf:<hex-parola>@<pooler host>:5432/postgres?sslmode=require`
     — pooler host'unu (gizli değil) asistan `.env`deki `DATABASE_URL`den yalnız host adını ayıklayarak söyler.
  7. GitHub → Settings → Environments → **production** → Add environment secret → ad `SITE_DATABASE_URL`, değer bu dize.
  8. Doğrulama (KENDİ terminalinde, çıktı secret içermez):
     `/opt/homebrew/opt/libpq/bin/psql "<SITE_DATABASE_URL>" -c "select current_user; show default_transaction_read_only; show statement_timeout;"`
     → çıktıyı sohbete yapıştır (yalnız bu üç satır).
- Asistan: çıktıda `site_reader` · `on` · beklenen zaman aşımı görmeli (rol GUC'leri pooler üzerinden uygulanıyor —
  faz HANDOFF adım 5); secret adlarını `gh api` ile doğrular; deftere yazar. RUNBOOK'a parola döndürme prosedürünü ekler.
- Bitti: üç secret production ortamında; psql çıktısı beklenen; `rolcanlogin` doğru.

---

#### FAZ 5 — İlk derleme (yayınsız) ve hukuk paketi (~40 dk)

**Adım 15 — `site.yml` ilk derleme provası (yayın YOK).**
- Neden: gerçek veriyle dışa aktarım + derleme + bekçiler ilk kez koşar; `deploy` işi Required reviewers yüzünden
  onay bekler — reddedilir (avukat gelmeden yayın yok).
- Asistan: `gh workflow run site.yml -f first_publish=true` (canlı site yok → önceki `slugs.json` yok) → kullanıcıya
  "Actions sekmesinde `build` onay bekliyor" der.
- Kullanıcı: GitHub → **Actions → site → koşu → Review deployments → production → Approve** (yalnız `build` için).
  `deploy` onay istediğinde: **Reject** (ya da hiçbir şey yapma; süre dolunca düşer).
  Söyleyeceği: *"build'i onayladım, deploy'u reddettim."*
- Asistan: `build` logunu okur (dışa aktarım satırı: maç/lig/takım/satır sayıları, `content_sha256`), artifact'ı
  indirir (`gh run download`), yerelde `check-out` ve yayın bekçilerini koşar, 5 örnek sayfayı tarayıcıda (yerel
  statik sunucu) kullanıcıya gösterir.
- Bitti: build yeşil; check-out 0 bulgu; deploy reddedildi; sayfalar gerçek veriyle görüldü.
- **Karar noktası (kullanıcı):** avukat beklenmeden `noindex`li yayın istenirse açıkça söylemeli — **öneri: HAYIR,
  avukat onayından sonra** (TR bahis içeriği riski K/7/2).

**Adım 16 — Avukat paketi (K/7, 20 dk hazırlık; görüşme oturum dışında).**
- Asistan: tek bir belge hazırlar (`docs/reports/2026-10-xx-avukat-paketi.md` + istenirse .docx/PDF): proje bir
  paragrafta; soru listesi öncelik sırasıyla (K/7/1–7: sağlık verisi/KVKK md. 6, TR bahis içeriği riski, KVKK aydınlatma
  öğeleri + `localStorage` 18+ onayı + Netlify log davranışı, football-data yazılı izin, başlık telifi + Rocket Sports
  £500 sözleşmesi, TFF koşulları (Adım 6), B-2 C1–C11); ekler: 8 taslak metin (`_kalici/hukuk-taslak-metin/`), site
  ekran görüntüleri (Adım 15'ten), veri akışı şeması (archify ile tek sayfa).
- Kullanıcı: avukatı seçer, paketi SEN gönderirsin (asistan e-posta göndermez).
  Söyleyeceği: *"Paket tamam, avukata ben gönderiyorum."*
- Ayrıca **football-data.co.uk yazılı izin e-postası** (K/7/4): asistan kısa İngilizce taslak hazırlar, SEN gönderirsin.

**Adım 17 — Oturum kapanışı (asistan, 10 dk).**
- Bu §0'ı "kullanıcı oturumu sonucu" ile günceller: biten adımlar, alınan kararlar, kalanlar (avukat yanıtı → TASLAK
  kaldırma + indeksleme AK14 + ilk gerçek yayın; Plan 2 ≥ 10-07; K/8 holdout 2. açılışı çok sonra; K/9 Odds API planı
  10-09 sonrası ilk hafta kredi ölçümüyle). Defteri kapatır, commit/push, CI yeşil.

### 0.5 Bu oturumda YAPILMAYACAKLAR (bilerek)
- **İlk gerçek yayın ve indekslemeye açma** — avukat onayı (K/7, AK13/AK14) gelmeden.
- **K/8 holdout 2. açılışı** — Plan 2 T11, ön kayıt + kırmızı takımdan sonra.
- **K/9 Odds API plan yükseltme** — 10-09'dan sonra ilk haftanın kredi tüketimi ölçülünce (§0.önceki/0.İ/6).
- **Ücret açan Jev commit'i** — Plan 2 T3'te (Adım 9 kararıyla).
- **Plan 2** — en erken 2026-10-07 (§0.önceki/0.A/1).

### 0.6 Adım adım hızlı tablo
| # | Ne | Kim | Süre | Para | Bloklar |
|---|---|---|---|---|---|
| 1 | Kalan silmeler | sen onay · asistan | 2 dk | — | — |
| 2 | Supabase Exposed schemas | sen | 5 dk | — | 13 |
| 3 | GitHub production ortamı | sen · asistan site.yml | 10 dk | — | 11, 14, 15 |
| 4 | İz B onayları + AK17 araştırması | sen karar · asistan | 10 dk | — | 15 |
| 5 | Marka adı | sen | 10 dk | — | 10 |
| 6 | TFF kararı | sen | 5 dk | — | 16 |
| 7 | Haber kaynakları | sen | 15 dk | SportMonks denemesi (isteğe bağlı) | Plan 2 |
| 8 | Kalibrasyon etiketleri | sen + asistan | 45–60 dk | — | 9, Plan 2 T3 |
| 9 | Ücretli Jev kararı | sen | 5 dk | karar (commit sonra) | Plan 2 T3 |
| 10 | Alan adı + ayrı Netlify | sen | 25 dk | alan adı | 11 |
| 11 | Netlify secret'ları | sen · asistan SITE_URL | 10 dk | — | 15 |
| 12 | 0014 canlıya | asistan (sen "uygula") | 15 dk | — | 13, 14 |
| 13 | pg_net artık riski kabulü | sen | 5 dk | — | 14 |
| 14 | site_reader parolası + SITE_DATABASE_URL | sen · asistan LOGIN | 15 dk | — | 15 |
| 15 | İlk derleme provası (yayınsız) | asistan · sen onay/red | 20 dk | — | yayın |
| 16 | Avukat paketi + football-data izni | asistan hazırlar · sen gönderirsin | 20 dk | avukat ücreti | yayın, indeksleme |
| 17 | Kapanış | asistan | 10 dk | — | — |

---

## 0.önceki — Oturum 9–10b durumu ve referans bölümleri (0.İ izlenecekler, 0.A, 0.D disiplin, 0.K ayrıntılı liste)

> Aşağıdaki alt bölümler (0.1–0.R) oturum 9–10b'nin durum kaydıdır. **0.İ izlenecekler, 0.D disiplin ve 0.K ayrıntılı
> liste geçerlidir**; başlatma istemi ve yol haritası yukarıdaki KULLANICI OTURUMU'dur.

Bu bölüm kendi başına yeterlidir; altındaki "0.eski*" bölümleri tarihçedir. Kullanıcının yapacakları **§0.K**'de
(tek yer, tam liste). Asistanın kullanıcısız yapacakları **§0.A**'da. Disiplin **§0.D**'de.

### 0.0 (eski — KULLANMA; geçerli istem en üstteki §0.0) Başlatma istemi
> "`docs/HANDOFF.md` §0'dan devam et. Önce §0.İ izlenecekleri tarihine göre kontrol et (salt okuma). Sonra §0.A'daki
> kullanıcısız işleri dalga dalga yürüt — ayrık dosya kümeli işler paralel ajanlarla, her ajan kendi scratch alt
> dizininde, her dalga bağımsız inceleme ve tam kapıdan geçer. §0.K'deki kullanıcı işlerini SORMA; kullanıcı onları
> en sonda toplu yapacak. 2026-10-07 veya sonrasıysa §0.A/1 (Plan 2 başlangıç kontrol listesi) de yürütülür."

### 0.1 Durum (ölçüldü 2026-10-01, salt okuma)
- **Dal:** `main` = `origin/main` = `aa73c0c` (son insan commit'i `3df5599`; sonrası bot zincir başı/robots commit'leri).
  Açık worktree'ler ve birleşmiş yerel dallar duruyor (silme §0.K/S).
- **CI:** son push (`3df5599`) yeşil — 17 PASS + `SKIP: zincir`, ~3,3 dk; `site-db` (Postgres kabı) ve 6 site adımı CI'da koşuyor.
- **Zamanlanmış işler (son 7 gün hepsi yeşil):** `seal` 15 dk'da bir, `snapshot` 06:22, `collect-news` 2 saatte bir,
  `collect-daily` 07:10, `sources-audit` günlük (robots yeniden doğrulandı 10-01), `shadow` (09-25, 09-29), `history`
  (09-25, 09-29; selftest K1–K4 GEÇTİ). 0013'ten sonra hiçbir işte yetki hatası yok.
- **Gölge:** 09-25 ve 09-29 `karar 0 · yazılan 0 · eşlenemeyen 0` — milli ara, beklenen.
- **Veri:** `news_items` 1.679 (hepsi TR/ajansspor; ilk 09-23 canlı, geri doldurma 09-04'ten); `odds_snapshots` 5.763
  satır, son satır 09-20 (milli ara — arıza değil); `matches`te ileri tarihli maç yok (fikstürler ~10-02'de 7 günlük
  ufka girer); `model_predictions` 0; `jev_spend` 0 (Jev hiç çağrılmadı).
- **Canlı veritabanı:** 0013 (API rolleri kilidi) **CANLIDA** (2026-09-23 21:36 UTC). **0014 (site okuma katmanı)
  YALNIZ depoda** — canlıya uygulanmadı (§0.K/3). Supabase advisors: ERROR/WARN yok (INFO "RLS açık politika yok" kasıtlı).
- **Kapı:** yerelde 16 PASS + adıyla 3 SKIP (`site-db`, `site-derleme/e2e`, `zincir`); DB bağlıyken `zincir` de PASS.
  Komut: `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); TMPDIR=$T ./verify.sh > "$T/verify.log" 2>&1`
  — sonuç LOG'dan; kurulum `uv sync --frozen --extra scrape`. Node 22 ile `site-kurulum` adıyla FAIL (kasıtlı).
  Secret'lı kabukta koşma: `env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY …` (yalnız `zincir` için DB gerekir).
- **Holdout:** açılmadı. Plan 2 en erken 2026-10-07.

### 0.2b Oturum 10b'de biten (2026-10-02) — aynı disiplin (görev + bütün-dal incelemesi + tek düzeltme dalgası + tam kapı)
- Plan `docs/superpowers/plans/2026-10-01-oturum10b-kalan-borclar.md` (defter `.superpowers/sdd/2026-10-01-oturum10b-kalan-borclar/progress.md`).
- **K/S temizliği yapıldı** (kullanıcı onayıyla; ayrıntı §0.K/S).
- **16g UYGULANDI:** DC memo soy bekçisi (`model/strategies.py`, `MemoReuseError`) — yalnız yükseltir, olasılık değişmez;
  bütün zamanlanmış/CLI giriş noktalarından ulaşılamaz (izlendi, sentetik koşuldu). **19b KAPANDI:** seal `Bekçi` ve
  sources-audit push adımı tarama başarısına bağlı (yeşil turda davranış aynı — 5.800 simüle tur). **21a–21e, 21j, 21k
  kapandı** (workflow bekçileri, sıcak başlangıç ve harman testleri, `_headers` ayrıştırıcıları, 404'te iç import yok).
  Yeni ertelenenler 21l–21n.
- **Push sonrası (`09052d4`):** CI ve ilk `seal` yeşil; kilitli E verisinde eski/yeni kod `model-selftest` ve
  `walkforward` çıktıları birebir (yalnız zaman damgası farklı).
- **Güvenlik olayı (zararsız):** bir inceleyici sondasında gerçek `git -C site push` 4 kez çalıştı, chdir'de düştü;
  origin'de yeni ref yok (doğrulandı). Kural belleğe ve inceleyici talimatına girdi: sondalar sahte ikililerle.

### 0.2a Oturum 10'da biten (2026-10-01) — görev incelemesi + bütün-dal incelemesi + tek düzeltme dalgası + tam kapı
- Plan `docs/superpowers/plans/2026-10-01-oturum10-kucuk-borclar.md` (defter `.superpowers/sdd/2026-10-01-oturum10-kucuk-borclar/progress.md`,
  gitignored). Yedi görev paralel worktree'lerde (`.worktrees/wt-s10-t1…t7`, `wt-s10-fix`), `integ/s10` üzerinden `main`e.
- **Kapanan DEFERRED:** 11a, 11h (N7 eşdeğer DEĞİLMİŞ — test eklendi), 17h, **18g(b)** (`db.connect` iki katmanlı DSN hijyeni:
  `src/football_edge/dsn_hygiene.py` — bağlanmadan önce biçim + bağlanırken maske; 4 düzeltme turunda 6 yeni sızıntı biçimi
  bulundu ve kapandı, 18 libpq seçeneği), 19a (yapılandırma hatası exit 20, beklenmeyen 22), 19c, 20a, 20d, 20f (404 `lang`,
  nav adları), 20k, 20l, 20m. **Kısmen:** 19b (iki workflow'a tarama + özellik/sıra bekçileri; kırmızı taramadan sonra
  `!cancelled()` adımları hâlâ koşar). **Tasarım:** 16g (`docs/superpowers/specs/2026-10-01-dc-memo-anahtari.md`, öneri (c)
  soy bekçisi; uygulama Faz 4 model değişikliğiyle). **Yan bulgu kapandı:** E2 parite testinin DC ayağı hiçbir şey ölçmüyordu
  (memo isabeti) — T7. Yeni ertelenenler **DEFERRED §21** (21a–21k).
- **Canlı/zamanlanmış işlere etkisi:** `db.connect` her zamanlanmış işin yolunda. Yerel `.env` `DATABASE_URL` yeni biçim
  denetiminden geçiyor (yalnız bool ölçüldü); GitHub secret'ı push sonrası ilk `seal` turuyla doğrulanır (§0.İ/0).

### 0.2 Oturum 9'da biten (2026-09-23/24) — hepsi bağımsız inceleme + bütün-dal incelemesi + CI'dan geçti
- **Dalga A** (plan `docs/superpowers/plans/2026-09-23-oturum9-dalga-a.md`, defter
  `.superpowers/sdd/2026-09-23-oturum9-dalga-a/progress.md`): T1 EN alan adı koşulları raporu · T2 erişim kapısı
  R77b'ye göre (fetcher'lar yalnız `src/football_edge/scrape.py` tek geçidinde; doğrulama çözme/proxy/adı verilmiş
  bot/Scrapling CLI bayrakları kırmızı) · T3 Scrapling adaptörü + TFF PFDK ayrıştırıcısı (`tff-pfdk` kapalı;
  fixture'lar kırpılmış ve takma adlı) · T4 17n/17h/16k-b · T5 100 TR haber ön-etiketi (onay §0.K/5) · **T6 0013**.
- **İz B** (spec `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md`; planlar
  `docs/superpowers/plans/2026-09-24-faz6-iz-b-{1-okuma-katmani,2-web-yuzeyi}.md`; **faz belgesi
  `docs/phases/06-site/HANDOFF.md`** — canlıya geçiş listesi, kapının ÖLÇMEDİKLERİ B-1 1–19 + B-2, hukuk C1–C11):
  B-1 okuma katmanı (0014, dışa aktarıcı, `verify-snapshot`, `site.yml` build/deploy/live — yalnız elle tetiklenir,
  CI `site-db`) · B-2 web yüzeyi (`web/` Next.js 16 statik, value önerisi YOK, varsayılan noindex, TASLAK hukuk,
  CSP hash'leri, `check-out` çıktı denetleyicisi, `site_gate.sh`, yayın bekçileri).
- **Oturumda bulunup kapatılan gerçek sorunlar:** 6 eski tabloda RLS yoktu ve `anon` yazabiliyordu (0013) · canlıda 51
  maç içi oran satırı türetime girebilirdi · ger.1/aut.1 aynı adlı lig → kalıcı `site_slug` · secret taraması bulduğu
  değeri public CI loguna basıyordu (mevcut tarama dahil) → yalnız `dosya:satır` · kapı pytest'i bağlantı hatasında
  parola basabiliyordu → `--tb=short` bekçisi · deploy secret'ı npm koduyla aynı job'daydı → ayrı `deploy` job'ı.
- **Asistanın oturumdaki hataları (tekrarlanmasın):** paralel ajanlara ayrı scratch dizini verilmedi → kanıtlar ezildi
  (yeniden koşuldu); bir belge push'u yerel kapı kırmızıyken gitti (`;` zincir; neden yerel ekstra eksikliği, CI
  yeşildi) → push artık `grep -q "KAPI YEŞİL" … && git push`.

### 0.İ İzlenecekler (tarih sırasıyla — taze oturum her açılışta bakar)
0. **Oturum 10 push'undan hemen sonra:** ilk `seal` turu yeşil olmalı (yeni `dsn_hygiene` biçim denetimi GitHub
   `DATABASE_URL` secret'ını reddederse exit ≠ 0 — o zaman birleştirme commit'i geri alınır, secret biçimi ölçülür);
   ilk `ci.yml` pytest adımı yeşil olmalı (DEFERRED 21i: runner libpq sürümü ölçülmedi).
   **→ YAPILDI 2026-10-01:** `833fe48` CI yeşil, 18:15 UTC `seal` yeşil (yeni biçim denetimi canlı secret'ı kabul etti);
   yerelden salt okuma `verify-chain` yeni `connect` yolundan `SAĞLAM`.
1. **~2026-10-02/03 06:22 UTC `snapshot`:** fikstürler 7 günlük ufka girer, `odds_snapshots`a satır yazılmaya başlar.
   **Olası tek yanlış exit 19** (oranı geç açılan bir lig, ötekiler boşken; RUNBOOK §3.11) — sonraki yeşil tur kapatır.
   **10-04'ten sonra hâlâ 19 ya da 0 satır → gerçek arıza**, RUNBOOK §3.11. `matches`te ileri tarihli maç görünmeli.
2. **2026-10-07 (salı):** Plan 2 başlangıç kontrol listesi açılır (§0.A/1). `lag_b_p99` ölçülebilir (sync-news ≥ 2 hafta).
3. **2026-10-09 (perşembe) / 10-10 (cuma):** ilk kulüp maçları (La Liga, Süper Lig 10-09; EPL 10-10). **İlk karar günlü
   gölge turu 10-09 cuma 12:35 UTC** (`shadow.yml`): `gölge: karar N · yazılan M · eşlenemeyen U · bayat B`; **U > 0
   ise** adlar aynı gün/lig/konum kuralıyla `config/history_aliases.yaml`a (TAHMİN EDİLMEZ). İlk mühür (`is_closing`)
   satırları başlamadan ≤ 20 dk önce.
4. **10-10/11 hafta sonu sonrası:** `live parity --since 2026-10-01` (salt okuma) — ned.1/bel.1'in ilk canlı maçları ve
   yeni takma adlar.
5. **İlk dolu salı gölge raporu en erken 2026-10-13** (gerçekçi 10-20; sonuç football-data haftalık senkronuna bağlı).
6. **Odds API kredi tüketimi:** maçlar başlayınca ilk hafta ölçülür (§0.K/9 kararının girdisi).
7. **Supabase advisors** ara sıra okunur (`get_advisors security`); 0013 sonrası beklenen yalnız INFO.

### 0.A Asistanın kullanıcısız işleri (öncelik sırasıyla)
1. **Plan 2 başlangıç kontrol listesi (≥ 2026-10-07)** — Faz 4 Plan 2 (Jev sinyali) yazılmadan önce:
   - (a) **Arşiv kapsamı ölçümü (DEFERRED 17k):** GDELT DOC API yerel ağdan 429 → runner'da tek kullanımlık dal +
     `workflow_dispatch`, T0c `step3_coverage.py 50 50` (~2.800 sorgu, ≥ 6 sn aralık, ~4,7 saat; betikler
     `.superpowers/sdd/2026-09-23-faz4-plan1-dalga0-1/t0c/`). **DİKKAT:** `Matches.csv` holdout SONUÇLARI taşır —
     dala YALNIZ sonuç sütunları çıkarılmış kopya (tarih/lig/takım) itilir; ham dosya public depoya ASLA girmez. ≥ %30
     ise arşiv ayağı açılır; değilse spec §7.3 yalnız-canlı yolu. Uzak geçici dalın silinmesi kullanıcı onayı (§0.K/S).
   - (b) `lag_b_p99`: yayıncı iddiası ↔ `first_seen_at` (sync-news ≥ 2 hafta, 10-07'den itibaren).
   - (c) Gölge raporunun ilk dolu turları (§0.İ/3–5) → canlı ΔLL SD'si → güç yeniden hesabı (spec §7.3).
   - (d) Plan 2 brief'lerine taşınacaklar: 17c–17e (T10), 17h kırmızı takım, 17n; `tier1` zamanlanırken exit 7 = "Jev
     kesintisi" adıyla; Plan metni Task 9 Step 8'de `min(boolean)` değil `bool_and`.
   - Plan 2'nin kullanıcıya bağlı kapıları: §0.K/4 (EN kaynağı), §0.K/5 (kalibrasyon onayı), §0.K/6 (ücretli Jev).
2. ~~İsteğe bağlı küçük işler~~ **Oturum 10 ve 10b'de bitti (§0.2a–§0.2b).** Kalan kullanıcısız küçükler DEFERRED 21f,
   21g, 21h, 21l–21n (hepsi tetikli, acil değil). 16g'nin gerçek veri eşliği de ölçüldü (2026-10-02: eski/yeni kodla
   `model-selftest` birebir, `walkforward` satır özeti sha256 aynı).
3. **İz B'de kullanıcısız kalan yok** — 0014'ün canlıya uygulanması, deploy, alan adı, hukuk hepsi §0.K'ye bağlı.
   Kullanıcı §0.K'yi tamamlayınca asistan `docs/phases/06-site/HANDOFF.md` "Canlıya geçiş" listesini 1→6 yürütür.

### 0.D Çalışma disiplini (oturum 9'un kanıtladıkları — öncekiler §0.eski bölümlerinde aynen geçerli)
- Alt ajanlar Opus 5.5 high (`~/.claude/settings.json`); `model` parametresi verilmez. Haiku yok.
- **Her dispatch:** "HİÇBİR ŞEY SİLME" · **kendine ait scratch alt dizini, görev önekli dosya adları** (paylaşılan
  scratchpad/`/tmp` YASAK) · rapor dosyası + kısa son mesaj · holdout AÇMA · canlı DB'ye bağlanma/.env okuma yok
  (gerekmedikçe) · kendi kap öneki (`scripts/sandbox_db.sh`; başkasının kabına dokunma).
- **İnceleme kalıbı:** inceleyici plana bayt eşliğini betikle doğrular, `git archive` kopyasında BAĞIMSIZ mutasyon
  koşar (`PYTHONDONTWRITEBYTECODE=1`), kendi saldırgan sondalarını dener. Her düzeltme turu kapsamlı yeniden
  inceleme; görev başına ≤ 5 tur; her iz için bütün-dal incelemesi + TEK düzeltme dalgası + tek yeniden inceleme.
  Minor'lar deftere; "MERGE ÖNCESİ" işaretliler bütün-dal düzeltmesine.
- **Kapı:** her commit'ten sonra tam kapı (`T=$(mktemp -d)`, TMPDIR depo DIŞINDA — içindeyse iki B-1 testi kırmızı,
  DEFERRED 20l); push `grep -q "KAPI YEŞİL" <log> && git fetch && git merge --no-ff origin/main … && git push`
  zinciriyle; `main`e `--no-ff`; taze klon kapısı; CI yeşil. **CI `cancel-in-progress`:** koşan CI'ı izlerken yeni
  push yapma (iptal eder).
- **Canlı DB'ye yazım:** önce aynı SQL `begin … rollback` kuru koşusu (sonuç `raise exception` JSON'unda), sessiz
  aralıkta (mühür :00/:15/:30/:45 dışı, `gh run list --status in_progress` boş), sonra `apply_migration` (metin bayt
  bayt aynı, sha256 deftere), sonra salt okuma doğrulaması + advisors + bir sonraki mühür turunun yeşili.
- **Ücret/harcama açan commit'i asistan yapamaz** (bellek `credit-activation-commit-blocked`): değişiklik hazırlanır,
  kapı koşulur, kullanıcıya tek satırlık `git commit` verilir; birleştirme/push asistanda.
- **İzin sınıflandırıcısı reddederse** (ör. Supabase REST'e publishable anahtarla GET) ısrar edilmez, kullanıcıya
  §0.K'ye yazılır.
- SDD defterleri gitignored: `.superpowers/sdd/<plan>/progress.md` — her kararın ("Ruling:") gerekçesi ve "yanlışsa
  maliyeti" orada. Kalıcı tutulan kullanıcı dosyaları: `.superpowers/sdd/_kalici/` (kalibrasyon onayı, hukuk taslakları).

### 0.K KULLANICININ YAPACAKLARI — ayrıntılı referans (KULLANICI OTURUMU'nda en üstteki §0.4 sırasıyla yürütülür)
Her madde: **Ne** · **Neden** · **Nerede** · **Nasıl** · **Sonra asistan** · **Bloklar**. Sıra önerisi: önce K/S
(temizlik, 10 dk) ve K/13–14 (güvenlik ayarları, 10 dk); sonra kararlar; en son hukuk ve para.

**K/1 — Marka adı.** Ne: sitenin adı (çalışma adı `football-edge`). Neden: alan adı, `Organization` JSON-LD, hukuk
metinleri, sayfa başlıkları ondan türer; şu an yer tutucu `[site-name]`. Nasıl: adı yaz. Sonra asistan: yer
tutucuları tek yerden (web yapılandırması) değiştirir, kapı + `check-out`. Bloklar: AK3, deploy, indeksleme.

**K/2 — Alan adı + Netlify hesabı.** Ne: alan adını satın al (ödeme sende; kayıt yeri Cloudflare Registrar /
Namecheap / Netlify — Netlify DNS'e bağlanabilen herhangi biri); **yalnız bu siteyi barındıracak ayrı bir Netlify
hesabı/ekibi** aç (neden: Netlify kişisel erişim tokenı site başına kısıtlanamaz, hesabın bütün sitelerine yetkilidir —
AK18). Nasıl: Netlify'da boş site oluştur; Site ID'yi ve bir kişisel erişim tokenını K/14'teki secret'lara sen ekle
(asistan token görmez). Sonra asistan: `SITE_URL` yer tutucusunu (`https://example.invalid`) gerçek alan adıyla
değiştirir, DNS/site ayarlarını Netlify araçlarıyla kurar (sen giriş yaptıktan sonra), yayın bekçileri (`site_publish.py`)
bunu bekler — yer tutucu adresle kasıtlı olarak kırmızı. Bloklar: AK4, ilk yayın, site haritası/hreflang mutlak adresleri.

**K/3 — 0014'ün canlıya uygulanması (halka açık okuma katmanı, AK6).** Ne: siteye açılacak görünümleri onayla:
öneri spec §4.3 listesi (`site` şeması yayımlanabilir; `site_input` ve `site_audit` YAYIMLANMAZ). Neden: 0014 canlıya
ancak onayla uygulanır. Nerede: `db/migrations/0014_site_read.sql`, spec §4. Nasıl: "AK6 = §4.3 listesi, uygula" de.
Sonra asistan: `docs/phases/06-site/HANDOFF.md` "Canlıya geçiş" 2. adım (ROLLBACK provası → `apply_migration` `postgres`
rolüyle → katalog testleri canlıya salt okuma → advisors). Bloklar: ilk gerçek dışa aktarım.

**K/4 — Haber kaynağı politikası.** Girdi belgeleri: `docs/reports/2026-09-23-kaynak-kosullari.md` (oturum 9'da
genişletildi) ve `docs/reports/2026-09-23-ek-kaynaklar.md`. Karar verilecekler:
- (a) **EN — GDELT ayağı hangi politikayla, ya da hiç?** Ölçüm: önerilen izin listesi GDELT'in İngilizce futbol
  başlıklarında fiilen boş (sessiz pay %3,0: yalnız dailytrust, el-balad); en sık 15 alan adının 12'si yasaklıyor (AOL,
  thehardtackle ticari yeniden kullanım; Newsquest veritabanı/ticari). Raporun 3 "sessiz" yayıncısı (independent,
  standard, sportsmole) GDELT örnekleminde **0 isabet**.
- (b) **CaughtOffside/JustArsenal (Rocket Sports)** arama dışı her otomatik erişimi lisanssız sayıp makale başına
  **£500** talep eden bir "Search Only" sözleşmesi yayımlıyor. Koşul okuması bu iki siteye robots izinli **3 istek**
  attı (rapor yöntem bölümünde). Avukat sorusu (K/7'ye eklendi). Karar: bu alan adları kesin dışarıda mı?
- (c) **Ücretli kaynaklar:** SportMonks Starter (€29/ay, yapılandırılmış sakat/cezalı; 14 günlük deneme = hesap
  açmak, SENDE) · X API resmî kulüp hesapları için (~$60/ay tahmin). Hangileri?
- (d) **TR:** ajansspor (zaten toplanıyor) + Fotomaç/A Spor RSS + TFF PFDK (K/12'ye bağlı) + Galatasaray RSS — hangileri?
- (e) **ajansspor 17l:** sözleşme sayfası robots'ta kapalı (okunamadı); robots `Content-Signal: ai-input=yes,
  ai-train=no`. Seçenek: bunu yeterli say (öneri: Jev'e gövde vermek "input"tur, eğitim değil) ya da yayıncıya sor
  (dış iletişim — sen yaparsın ya da asistana açık onay verirsin).
- Sonra asistan: seçilen kaynakları `sources.yaml`a `enabled: true` ile, robots anlık görüntüsü + koşul kanıtıyla
  açar; Scrapling adaptörü üzerinden toplayıcı yazar. Bloklar: EN dil kalibrasyonu (K/5b), Plan 2 kademe 2.

**K/5 — Dil kalibrasyonu etiket onayı (Plan 2 T3 bunu bekler).**
- Dosya: **`.superpowers/sdd/_kalici/kalibrasyon-onay/tr.review.md`** (gitignored; kopyası SDD dizininde de var).
  100 madde: önce **6 uyuşmazlık**, sonra **29 sınırda**, sonra 65 net madde. Her satırda `[ ]` onay kutusu.
- Önce **dosyanın başındaki açık soru:** "yaklaşan maç" **(A) haberin yayımlandığı ana göre mi** (öneri — Jev'e tarih
  gitmez, üretimde haber yayın anında kullanılır, ölçüm tekrarlanabilir kalır) **(B) bugüne göre mi**. (B) seçilirse
  oynanmış maça bağlı `true` satırlar (1065, 422, 902, 187, 145, 572, 227, 791, 950, 1193) `false` olur.
- **`team` yazımı:** dosyada Odds API yazımı ("Fenerbahce", "Besiktas JK"); `data/calibration/README.md` örnekleri
  "Fenerbahçe". Jev'e `club` olarak bu dize gider — hangisi?
- Nasıl: kutuları işaretle, değiştirdiğin `relevant` değerlerini yaz, adını yaz (README: etiketleyenin adı
  `data/calibration/tr.meta.json`a girer). Sonra asistan: onaylı etiketleri `data/calibration/tr.jsonl`a (ham başlık
  telifi sorusu K/7'de — gerekirse yalnız id+etiket) aktarır, T3 ölçümünü (ücretli Jev, K/6) hazırlar.
- Sınırlar (dosyada yazılı): 71/100 dört büyük kulüp; kulüp adı geçmeyen ama ilgili başlıklar atlandı; sınıflar
  dengesiz (27 true/73 false); haber gövdeleri boş (yalnız başlık).
- **K/5b — EN etiketleri yok:** `news_items`ta İngilizce haber yok; K/4 (EN kaynağı) kararından sonra hazırlanır.

**K/6 — Ücretli Jev harcamasını açan commit + Plan 2 maliyet ölçümü onayı.** Ne: Jev (TypeSafe) ilk ücretli çağrısı.
Neden: auto-mode harcama açan commit'i asistana yaptırmaz (bellek `credit-activation-commit-blocked`). Nasıl: asistan
değişikliği hazırlar ve kapıyı koşar, sana **tek satırlık `git commit` komutu** verir; sen çalıştırırsın. Tavan:
`MONTHLY_CAP_USD = 25.0` (`src/football_edge/jev_budget.py`), aşılırsa kesinti. `TYPESAFE_API_KEY` zaten secret ve
`.env`te (2026-09-23). Bloklar: K/5 ölçümü, Plan 2 kademe 1–2.

**K/7 — Hukuk (yayından ÖNCE, avukatla).** Avukata götürülecek paket:
- Taslak metinler: **`.superpowers/sdd/_kalici/hukuk-taslak-metin/`** (8 dosya: en/tr × terms, privacy, cookies,
  responsible-gambling; düz metin). Sitede "TASLAK — avukat onayı bekler" işaretli, noindex, site haritası dışında.
- Sorular (öncelik sırası):
  1. **Sakatlık bilgisi = sağlık verisi (KVKK md. 6 / GDPR md. 9)** — kaynaktan bağımsız, bütün projeyi ilgilendirir;
     takım düzeyinde toplulaştırma yeterli mi? Haber hattı (`news_items`, 0012) başlık ve gövde saklıyor.
  2. Türkiye'de bahisle ilgili içerik/yönlendirme riski (site value önerisi yayımlamıyor; yalnız piyasa olasılıkları
     ve kapanış sicili).
  3. KVKK aydınlatma metni öğeleri (veri sorumlusu, amaç, haklar — taslakta yok), "kesinlikle gerekli yerel depolama"
     sınıflaması (18+ onayı `localStorage`da `fe-age-18`), barındırıcının (Netlify) çerez/IP log davranışı.
  4. football-data.co.uk'tan **yazılı izin** (spec §10/2; ticari lansmandan önce).
  5. Başlık telifi (NLA v Meltwater; AB TDM istisnası itirazla kapanır) ve yayıncı ToS'larının aracı (GDELT/Google
     News) üzerinden bizi bağlayıp bağlamadığı; **Rocket Sports £500/makale "Search Only" sözleşmesi** (K/4b).
  6. TFF koşulları (K/12).
  7. B-2 incelemesinin **C1–C11** soruları: `docs/phases/06-site/HANDOFF.md` "Hukuk incelemesi" (sorumlu bahis dili,
     yardım hattı ad/numaraları — doğrulanacak, "yardım ülkende mevcut" ifadesi vb.).
- Sonra asistan: avukatın düzeltmelerini metinlere işler, TASLAK işaretini kaldırır (kapı bekçisi var), AK13'ü kapatır.
  Bloklar: indekslemeye açma (AK14), TR dili yayını.

**K/8 — Holdout 2. açılışı için açık "evet"** (Plan 2 T11 — çok sonra; ön kayıt ve kırmızı takımdan sonra sorulur.
Şimdi bir şey gerekmez).

**K/9 — İsteğe bağlı: Odds API planı.** Maçlar 10-09'da başlayınca ilk haftanın kredi tüketimi ölçülür (§0.İ/6);
aylık kredi yetmezse plan yükseltme (ödeme sende).

**K/10 — İz B onayları (spec + AK'lar).** Spec `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md` §16 tablosu;
her satırda öneri yazılı. "Önerilerle onay" demen yeterli; farklı istediklerini yaz:
AK1 mimari A (Actions'ta salt okuma rolüyle statik üretim) · **AK2 spec onayı (sicil boş durum metni §6.2 dahil)** ·
AK3 = K/1 · AK4 = K/2 · AK5 diller en+tr · AK6 = K/3 · AK7 kapandı (0013) · AK8 maç sayfası yalnız vig'siz olasılık ·
AK9 kamu doğrulaması şimdi (a) çıpalar+baş+hash · AK10 skor yok · AK11 gölge seri sitede yok · AK12 analitik yok ·
AK13 = K/7 · AK14 indeksleme AK3/AK4/AK13'ten sonra · AK15 yeniden derleme günlük + saatlik mühür sonrası (yeni
migration gerekir) · AK16 Netlify CLI · **AK17 The Odds API koşulları türetilmiş olasılık yayımı açısından okunmadı**
(asistan salt okuma araştırması yapabilir — "yap" demen yeter; AK8/AK9/AK20/AK21'i etkiler) · AK18 = K/14 · AK19 CSP
hash'leri (uygulandı; `_headers` ~176 + 379 × sayfa bayt) · AK20 slug kalıcılığı (b) (uygulandı) · AK21 toplu indirme
yok, yalnız hash · AK22 tabandan beri her maç. Ayrıca planların yürütüldüğünü onayla (yöntem: subagent-driven —
yapıldı). Bekleyen metin düzeltmeleri AK2 ile: DEFERRED 20g (en boş sicil "to be registered in advance"), 20i.

**K/12 — TFF koşulları** (`https://www.tff.org/Default.aspx?pageID=179`): "ticari amaçlarla kullanılamaz", kaynak
gösterilmeden kopyalanamaz. Etkiler: **açık `tff` kaynağı** (hakem atamaları, günlük toplanıyor) ve kapalı `tff-pfdk`.
Karar: (a) `tff`yi kapat · (b) ticari lansmana kadar sürdür, lansmandan önce izin iste · (c) avukata sor (K/7/6).
Ayrıca `tests/fixtures/tff/` tam sayfa kopyaları (hakem adları, public repo) — kırpılsın mı (asistan yapar, öneri: evet).

**K/13 — Supabase panelinde pg_net kontrolü (güvenlik, 5 dk).** Ölçüm (2026-09-24, canlı, salt okuma):
`anon`/`authenticated`/`service_role` rollerinin `net` şemasında USAGE, `net.http_request_queue` SELECT/INSERT,
`net._http_response` SELECT ve `net.http_post` EXECUTE yetkisi var (veren `supabase_admin`; `postgres` geri alamaz —
kapta ölçüldü). Kuyruk pg_cron dispatch'lerinin Bearer GitHub token'ını taşır. Dışarıdan erişim **yalnız PostgREST
`net` şemasını açarsa** mümkün. Nasıl: Supabase Dashboard → proje `aaxadphezxavohkhqdrf` → **Project Settings → Data API (eski arayüzde "API") →
"Exposed schemas"**: listede yalnız `public` (ve `graphql_public`) olmalı; **`net` OLMAMALI** (varsa çıkar).
(Asistanın bunu REST'ten yoklaması izin sınıflandırıcısınca reddedildi.) Ayrıca `site_reader`a LOGIN vermeden önce
bu artık riski açıkça kabul et (faz HANDOFF "Canlıya geçiş" adım 3). Sonra asistan: canlıda `site_reader` yetkilerini
yeniden ölçer.

**K/14 — GitHub depo ayarları (site yayını, AK18; 10 dk).** Depo `popiliadam/football-edge` → Settings:
1. **Environments → `production` oluştur → Deployment branches: yalnız `main`.**
2. Bu ortamın secret'ları (repo düzeyinde DEĞİL): `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID` (K/2'den),
   `SITE_DATABASE_URL` (K/15'ten). Neden ortam kapsamlı: depo düzeyi secret'ı her dalın workflow'u okuyabilir.
3. Asistan bundan sonra `site.yml`in `build` işine `environment: production` ekler (bugün yok; ortam secret'ı aksi
   hâlde `build`e görünmez → exit 20) ve testle sabitler.
`site.yml` YALNIZ elle tetiklenir; **K/2, K/3, K/13, K/14, K/15 bitmeden tetikleme.**

**K/15 — `site_reader` parolası (0014 canlıya uygulandıktan sonra).** Nasıl: Supabase SQL düzenleyicisinde DEĞİL,
istemci tarafı SCRAM ile: `psql "<postgres bağlantı dizesi>"` → `\password site_reader` (parola sunucu loguna düz
metin düşmez; `ALTER ROLE … PASSWORD '…'` KULLANMA — DDL loglanırsa düz metin kalır). Sonra `site_reader`a `LOGIN`
(asistan migration ile; parolayı görmez). Bağlantı dizesi Supavisor biçiminde (`site_reader.aaxadphezxavohkhqdrf`,
session pooler 5432) → `SITE_DATABASE_URL` ortam secret'ı (K/14). Asistan: pooler üzerinden rol GUC'lerinin
uygulandığını ölçer (faz HANDOFF adım 5).

**K/S — Silme onayları (temizlik; asistan senin "sil" onayınla yapar ya da komutları sen çalıştırırsın).**
> **YAPILDI 2026-10-01 (kullanıcı onayıyla):** 1–5 ve 7 — 19 worktree, 23 yerel dal (`feat/s9-scrapling` dahil), ~41 GB SDD
> scratch (defterler + inceleme/rapor dosyaları `.superpowers/sdd/_kalici/defterler/` altında), 46 kap, `/tmp/b2fake`.
> Dokunulmayanlar: `t6-rls-{pre,sandbox,pg}`, `rev8-pg`, `rev9-pg` kapları (listede ve defterde yok — büyük olasılıkla
> oturum 8/9 kum havuzu; onay verirsen silinir) ve uzak dal `origin/faz-0-kayit-altyapisi` (birleşmiş; uzak silme ayrı onay).
Hepsi `main`de birleşmiş ya da yeniden üretilebilir; **kalıcı tutulanlar `.superpowers/sdd/_kalici/` (silinmez).**
1. **Worktree'ler + dalları (hepsi `main`de):** `.worktrees/wt-izb-{b1,b1-t4,b1-t8,b2}`,
   `.worktrees/wt-s9-{a1,borc,integ,izb,rls,scrapling-clean}` ve dallar `feat/izb-b1`, `feat/izb-b1-t4`,
   `feat/izb-b1-t8`, `feat/izb-b2`, `docs/s9-en-alan-adlari`, `docs/s9-iz-b-tasarim`, `feat/s9-borc`,
   `feat/s9-rls`, `feat/s9-scrapling-clean`, `integ/s9-dalga-a`. Eski: `faz-0-kayit-altyapisi`, `faz-1-toplayicilar`
   (ikisi de `main`de birleşmiş).
2. **`feat/s9-scrapling` dalı + `.worktrees/wt-s9-scrapling` — ÖNCELİKLİ:** `922a445` gerçek kişi adlı PFDK
   fixture'larını taşıyor; hiç push edilmedi, `main`de yok. Silinmesi önerilir (`git branch -D` gerekir — birleşmemiş görünür).
3. **SDD scratch'leri (~34 GB):** `.superpowers/sdd/2026-09-23-oturum9-dalga-a/` (7,3 GB),
   `.superpowers/sdd/2026-09-24-faz6-iz-b-1-okuma-katmani/` (13 GB), `.superpowers/sdd/2026-09-24-faz6-iz-b-2-web-yuzeyi/`
   (14 GB). İçlerindeki `progress.md` defterleri kararların tam kaydıdır — silmeden önce istersen yalnız
   `progress.md` + `*-review.md` + `*-report.md` dosyalarını `_kalici/defterler/` altına taşıtabilirsin (öneri).
4. **Durdurulmuş Docker kapları (47):** `docker ps -a` → adları `izb-`, `b1r-`, `b1rr-`, `t6r1-` ile başlayanlar
   (oturum 9 kum havuzları). `football-edge-sandbox-{applied,empty}` `scripts/sandbox_db.sh`in varsayılan kaplarıdır —
   silinebilir, betik yeniden kurar. Komut (kendi kapların için): `docker rm $(docker ps -aq --filter name=^izb-)` vb.
5. **`/tmp/b2fake`** (B-2 plan yazarının atığı).
7. **Oturum 10 (hepsi `main`de):** worktree'ler `.worktrees/wt-s10-{t1,t2,t3,t4,t5,t6,t7,fix}` ve dallar `feat/s10-t1…t7`,
   `feat/s10-fix`, `integ/s10`; SDD çalışma alanı `.superpowers/sdd/2026-10-01-oturum10-kucuk-borclar/` (defter + inceleme
   raporları + sondalar; istersen `progress.md`, `*-review*.md`, `*-report.md`, `final-review.md` → `_kalici/defterler/`).
6. Faz 4 T0c runner ölçümü yapılırsa (§0.A/1a) **uzak geçici dal** silinmesi.

### 0.R Senin adına verilen kararlar — gözden geçir (tam liste ve "yanlışsa maliyeti" defterlerde)
- 0013'ü canlıya uyguladım (yalnız yetki geri alır; tek satır `grant` ile geri döner).
- İz B'yi spec onayını beklemeden yerelde yaptım (deploy yok, 0014 canlıda yok).
- Dalga A/1 ölçümünü runner yerine yerelde koştum (holdout sonuçlu `Matches.csv` public depoya itilmesin diye).
- T2 erişim kapısı: R77b'nin değişmeyen sınırları (CAPTCHA çözücüler, Cloudflare atlatıcıları, IP/UA döndürme) yasak
  kaldı; Scrapling fetcher'ları yalnız `scrape.py` tek geçidinde.
- Scrapling tarayıcı taşıyıcıları (dynamic/stealthy) gerçek tarayıcıyla ölçülene kadar kapalı (DEFERRED 11g).
- `scrape` ekstrası yalnız CI'da kurulur (zamanlanmış işler hafif).
- Gerçek adlı PFDK commit'i `main`e hiç sokulmadı (dal yeniden kuruldu).
- Deploy ayrı job'da; `slugs` bekçisi build'de, `live` bekçisi üçüncü job'da.
- `check-out`a Türkçe bahis tavsiyesi sözcükleri (değer bahsi/valör/banko/tavsiye/kupon/iddaa) — sorumluluk reddi
  cümleleri tam cümle izinli.
- Site Node adımları `env -i` izin listesiyle (yerel secret'lar `next build`e geçmez).
- Tabandan önce gözlenmiş oran (canlıda 0 satır) dışa aktarımı düşürür — kod değişmedi, "ölçülmeyenler"de.
- Defterler: `.superpowers/sdd/2026-09-23-oturum9-dalga-a/progress.md`,
  `…/2026-09-24-faz6-iz-b-1-okuma-katmani/progress.md`, `…/2026-09-24-faz6-iz-b-2-web-yuzeyi/progress.md`
  (`grep '^Ruling'`).

> **Numara eşlemesi:** eski §0.7 maddeleri (aşağıdaki tarihçe ve `docs/phases/06-site/HANDOFF.md` "§0.7" atıfları)
> burada aynı numarayla K/1–K/15'tir (K/11 silme listesi → K/S). Yeni madde yok sayılmadı; eskiler güncellendi.

## 0.eski2 Oturum 9 ve Faz 4 Plan 1 (2026-09-23/24 — tarihçe; güncel liste yukarıda §0.K)

**Faz 4 Plan 1 bitti.** Tasarım `docs/superpowers/specs/2026-09-23-faz4-jev-sinyal-design.md` (R157–R172), plan
`docs/superpowers/plans/2026-09-23-faz4-plan1-dalga0-1.md`, T0c raporu `docs/reports/2026-09-23-faz4-arsiv-spike.md`,
ölçümler `docs/superpowers/specs/2026-09-23-faz4-olcumler.md`, ertelenenler **DEFERRED §17**. SDD defteri (gitignored,
bütün kararlar ve kanıtlar) `.superpowers/sdd/2026-09-23-faz4-plan1-dalga0-1/progress.md`.

### 0.0 Taze oturum — başlatma

**Başlatma istemi (yeni oturuma yapıştır):**
> "`docs/HANDOFF.md` §0'dan devam et. Önce §0.3 izlenecekleri kontrol et. Sonra §0.6'daki iş listesini (kullanıcı
> girdisi GEREKMEYEN işler) dalga dalga yürüt — ayrık dosya kümeli işler paralel ajanlarla, her dalga bağımsız
> inceleme ve tam kapıdan geçer. §0.7'deki kullanıcı taleplerini SORMA; kullanıcı onları toplu olarak verecek.
> 2026-10-07 veya sonrasıysa §0.2 kontrol listesini de yürüt."

### 0.0a Oturum 9 (2026-09-23/24) — ne bitti, nerede duruyor
SDD defteri (gitignored, bütün kararlar/incelemeler): `.superpowers/sdd/2026-09-23-oturum9-dalga-a/progress.md`.
Plan `docs/superpowers/plans/2026-09-23-oturum9-dalga-a.md` (T1–T6). Her görev bağımsız incelemeden (mutasyonlu,
`git archive` kopyasında) + bütün-dal incelemesinden geçti; taze klon kapısı ve CI yeşil.
- **T1** EN alan adı sıralaması (GDELT GKG, yerelde — ham dosya sunucusu açık; runner yolu holdout sonuçlu
  `Matches.csv`'yi public repoya itmeyi gerektirirdi): 198 isabet / 93 alan adı; önerilen izin listesinin 3 sessiz
  alanı **0 isabet**; ilk 15 alan adı okundu → sessiz pay **%3,0**. Rapor `docs/reports/2026-09-23-kaynak-kosullari.md`.
- **T2** erişim kapısı R77b'ye göre yeniden yazıldı (fetcher'lar yalnız `scrape.py` tek geçidinde; doğrulama çözme,
  proxy, adı verilmiş bot, Scrapling CLI bayrakları kırmızı). **T3** Scrapling adaptörü (`src/football_edge/scrape.py`,
  `scrape` ekstrası yalnız `ci.yml`de) + TFF PFDK ayrıştırıcısı (`tff-pfdk`, `enabled: false`; fixture'lar kırpılmış
  ve takma adlı). Tarayıcı taşıyıcıları gerçek tarayıcıyla ölçülene kadar kapalı (DEFERRED 11g).
- **T4** 17n, 17h (17a bekçisi kaçışları), 16k-b kapandı. **T5** 100 TR haber ön-etiketi + bağımsız ikinci etiket
  (uyum %94, κ 0,86) → onay dosyası §0.7/5. EN yok (`news_items`ta EN haber yok).
- **T6 (eklendi, K1):** 6 eski tabloda RLS yoktu ve `anon`/`authenticated` tam yetkiliydi (advisor ERROR ×6). `0013`
  yazıldı, kapta test edildi (`scripts/sandbox_db.sh`, RUNBOOK §4), ROLLBACK kuru koşusundan sonra **canlıya
  uygulandı**; ilk mühür turu yeşil; advisors ERROR/WARN yok. DEFERRED 12a kapandı, §18 açıldı.
- **İz B (Dalga B) — YAPILDI, `main`de:** spec `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md` (4 düzeltme
  turu → "Planlanabilir"; mimari A; açık kararlar AK1–AK22 spec §16) · planlar
  `docs/superpowers/plans/2026-09-24-faz6-iz-b-{1-okuma-katmani,2-web-yuzeyi}.md` (her biri 2 tur bağımsız plan
  incelemesi, planın kodu tek ağaçta kurulup koşuldu) · yürütme SDD: B-1 T0–T9 (K1), B-2 T0–T10; her görev bağımsız
  inceleme (mutasyonlu, `git archive` kopyası) + düzeltme turları + her iz için bütün-dal incelemesi ve tek düzeltme
  dalgası. **Faz belgesi (canlıya geçiş kontrol listesi, kapının ÖLÇMEDİKLERİ B-1 1–19 ve B-2, hukuk soruları
  C1–C11): `docs/phases/06-site/HANDOFF.md`.** SDD defterleri (gitignored): `.superpowers/sdd/2026-09-24-faz6-iz-b-{1,2}-…/progress.md`.
  - **B-1:** 0014 (`site_reader`, `site`/`site_input`/`site_audit`) yalnız depoda ve kapta test edildi; dışa aktarıcı
    (REPEATABLE READ, zincir GENESIS'ten, her çıpa, ikinci türetim alt süreçte, atomik yazım, çıkış 20–24),
    `verify-snapshot`, `config/site_leagues.yaml`, `site.yml` (build/deploy/live üç iş; YALNIZ elle tetiklenir;
    tetiklenmesi §0.7/14'e bağlı), CI `site-db` adımı (kap; 28 test; ilk CI 2 dk 24 sn).
  - **B-2:** `web/` Next.js 16 statik site (value önerisi YOK, varsayılan noindex, yer tutucu marka/alan adı,
    TASLAK hukuk metinleri, CSP hash'leri `unsafe-inline`sız), `check-out` çıktı denetleyicisi (yasak kelime/bahis
    şirketi/lisans/iç bağlantı/`data-fe` dışı sayı/CSP/görünür TASLAK), `site_gate.sh` (Node çağrıları `env -i`
    izin listesiyle), yayın bekçileri (`site_publish.py slugs|live`).
  - **Oturumda bulunup kapatılanlar:** canlıda 51 maç içi oran satırı → türetimde başlama öncesi süzgeci; aynı adlı iki
    lig (ger.1/aut.1) → kalıcı `site_slug`; secret taramasının bulduğu değeri herkese açık CI loguna basması (mevcut
    tarama dahil) → yalnız `dosya:satır`; kapı pytest'inin bağlantı hatasında parola basması → `--tb=short` bekçisi.
- **Açık worktree'ler** (`.worktrees/wt-s9-*`, `wt-izb-*`) ve yerel dallar birleşti ama silinmedi (silme onayı §0.7/11).

**Kullanıcı kararı (2026-09-23):** §0.2'deki ön koşullar acil değil — Plan 2'nin başlangıç kontrol listesidir. Haber
senkronu ve gölge raporu kendiliğinden birikir; arşiv kapsam ölçümü Plan 2 yazılırken (en erken 2026-10-07) yapılır.
Kullanıcı ayrıca "en iyi senaryo, asistanın önerisi" diye yetki verdi (bellek: `user-delegates-to-recommendation`).

### 0.1 Ne yapıldı (hepsi görev incelemesi + bütün-dal incelemesinden geçti)
- **Dalga 0:** T1 `live freeze-weights` + `config/blend_weights_faz3.yaml` (19 lig; çoğunda model ağırlığı 0 — Faz 3
  bulgusuyla tutarlı) · T2 haftalık gölge CLV raporu (`shadow.yml` salı adımı, yalnız baz stratejileri — mühür testli;
  sonuç football-data'dan `match_key` ile, çünkü `match_results` boş) · T3–T5 açılış öncesi düzeltmeler 16a–16d, 16i,
  16l, 16p (`final-eval --phase` zorunlu) · T6 spike · T7 Jev batarya + $25/ay tavan (`jev_spend`) · T8 `0012`.
- **Dalga 1:** T9 `news_items` + `sync-news` (R172: `available_at = greatest(now(), iddia)`) · T10 karar anı filtresi,
  logit kaydırma, import kuralı · T11 34 soruluk `config/jev_questions.yaml`, kademe 1 koşucusu (`features tier1`, sahte
  istemciyle; gerçek Jev çağrısı YOK).
- **Son inceleme düzeltmeleri:** bütçesiz Jev yolları kapandı (`map-entities`, `calibrate` artık `BudgetedJev`), havuz
  fiti yakınsamazsa `freeze-weights` exit 18, kademe 1 haber başına 3 deneme tavanı (`t1_failed:<n>` işaretleri),
  `CalibrationUnfit`.
- **Gerçek veritabanı işlemleri:** `0012` uygulandı ve okuma sorgularıyla doğrulandı · `sync-news --since 2026-09-04`
  geri doldurması 1.259 haber (önce ROLLBACK'li kuru koşu) · 16i ölçümü: 1X2/pre red 0, W1–W4 GEÇTİ.

### 0.2 Plan 2'nin başlangıç kontrol listesi (acil değil — en erken 2026-10-07; Plan 2 bunlar olmadan yazılmaz)
1. **Arşiv kapsamı runner'da (DEFERRED 17k)** — asistan yapar: geçici dal + `workflow_dispatch`, T0c betiği
   (`step3_coverage.py 50 50`, ~2.800 sorgu, ~4,7 saat). **Betikler ve girdileri** (oturum 8'de `/private/tmp`ten
   kurtarıldı — yeniden başlatmada silinirdi): `.superpowers/sdd/2026-09-23-faz4-plan1-dalga0-1/t0c/` (gitignored;
   `Matches.csv` holdout sonuçları taşır, betik sonuç sütunlarını OKUMAZ). ≥ %30 ise
   arşiv ayağı yeniden açılır; değilse spec §7.3 yalnız-canlı yolu (seçim dilimi ≥ 900 haberli maç, kapı dilimi ≥ 1.800,
   2027-06-30). **Şu anki karar: KAPALI** (koşul ölçülmediği için).
2. ~~`TYPESAFE_API_KEY`~~ — **2026-09-23 eklendi** (secret + `.env`). Ücretli harcamayı açan commit'i asistan yapamaz —
   tek satırlık komutu kullanıcıya verir.
3. **`lag_b_p99`**: `sync-news` en az 2 hafta koşmuş olmalı (en erken **2026-10-07**) — yayıncı iddiası ↔ `first_seen_at`.
4. **Gölge raporunun ilk DOLU turları:** milli ara yüzünden 09-26 ve 09-29 boş geçer; ilk karar günü **2026-10-09
   cuma 12:35 UTC**, ilk dolu salı raporu en erken **2026-10-13** (sonuç football-data haftalık senkronuna bağlı;
   gerçekçi 10-20). Canlı ΔLL SD'si → güç yeniden hesabı (spec §7.3) ancak ondan sonra.
5. **EN kaynağı — KULLANICI KARARI GEREKİYOR:** `docs/reports/2026-09-23-kaynak-kosullari.md`. GDELT kendi verisi için
   kısıtsız (atıf şartı, ≤ 1 istek/5 sn). Kontrol edilen 25 EN yayıncıdan 19'u yapay zekâ kullanımını/TDM'yi açıkça
   yasaklıyor, 3'ü sessiz (independent, standard, sportsmole) → "yasaklayanı dışla" büyük İngiliz yayıncılarının
   hepsini düşürür; öneri **izin listesi** (okunmuş-sessiz alan adları, bilinmeyen dışarıda). Önce runner'da gerçek
   alan adı sıralaması ölçülmeli (`step6_gdelt_en.py` → `doms.most_common(40)`, T0c betik dizininde). **17l
   ajansspor:** sözleşme robots'ta kapalı; robots `Content-Signal: ai-input=yes, ai-train=no` — kapatmak ya da
   yayıncıya sormak (dış iletişim, kullanıcı onayı) kullanıcıda.

**Plan 2'ye taşınacaklar (brief'lere):** 17c–17e açılış öncesi (T10), 17h kırmızı takım (oturum 8'de 17a bekçisinin
kaçışları eklendi), 17n bekçi test boşlukları. **`tier1` zamanlanırken:** workflow adımı exit 7'yi "Jev kesintisi"
diye adlandırır (17b). 17a/17b oturum 8'de kapandı. Plan metnindeki Task 9 Step 8 kuru koşusunda `min(boolean)` yok —
`bool_and`.

### 0.2b Oturum 8'de (2026-09-23) biten — hepsi bağımsız bütün-dal incelemesinden geçti, `main`de
- football-data robots sapması (#3) kapandı (§0.3/6).
- Küçük borç temizliği (`3205f32`) + küçükleri (`50b677f`): DEFERRED 16j/17i kapalı; 16k-c ve 17m'nin iki doğrulama
  açığı kapalı. Plan `docs/superpowers/plans/2026-09-23-kucuk-borc-temizligi.md`.
- **Takma ad hijyeni (16e, `6ca8547`):** 51 canlı maçta tek eşlenmeyen `Erzurum BB` → `Erzurumspor`; `live parity`
  eşleşen 51 · eşlenemeyen 0 · sezon farkı 0 · başlama farkı 0.
- **17a** okuyucu mühürü (süzgeç yönü dahil) · **17b** kesinti = art arda 3 Jev hatası, koşu durur (≤ 3 çağrı) ·
  **17g** reddedilen karar fiyatı gölgede ve raporda adıyla · **boş tur bekçisi:** her lig boşken ücretsiz `/events`
  ufukta fikstür görürse `collect snapshot` exit 19 (RUNBOOK §3.11) — `f640fa1`. İnceleme: 50 mutasyon; I-1 (süzgeç
  yönü), I-2 (kesinti tavanı delmesi), M-1 düzeltildi, kalanlar 17h/17n.
- **Kaynak koşulları raporu** (§0.2/5). **T0c betikleri** `/private/tmp`ten kalıcı dizine kurtarıldı (§0.2/1).
- **Kalan iş:** §0.6 (kullanıcısız iş listesi) ve §0.7 (toplu kullanıcı talepleri).

### 0.3 İzlenecekler
**Milli ara (ölçüldü 2026-09-23, The Odds API ücretsiz `/events`, 0 kredi):** sonraki kulüp maçları EPL 2026-10-10,
La Liga ve Süper Lig 2026-10-09. `odds_snapshots`ta 09-20'den beri satır yok — arıza DEĞİL, fikstür yok.
1. **2026-09-26 cuma 12:35 UTC** gölge turu: `karar 0` beklenir (arıza değil). İlk dolu karar günü **2026-10-09**.
2. **2026-09-29 salı** haftalık rapor: yeni karar yok; yalnız 09-19/20 maçları. İlk dolu rapor en erken 10-13.
3. **~2026-10-02/03 06:22 UTC snapshot:** fikstürler 7 günlük ufka girer, satır yazılmaya başlamalı. **Olası tek
   yanlış exit 19** (oranı geç açılan bir lig ve öteki ligler hâlâ boşsa; RUNBOOK §3.11) — sonraki yeşil tur alarmı
   kapatır. 10-04'ten sonra hâlâ 19 ya da 0 satır → gerçek arıza, RUNBOOK §3.11.
4. **10-10/11 hafta sonundan sonra:** `live parity --since 2026-10-01` (salt okuma) — ned.1/bel.1'in ilk canlı
   maçları ve yeni takma adlar (aynı gün/lig/konum kuralı; teşhis betiği tarifi 16e satırında).
5. `collect-news` her turda "Haber deposunu güncelle"; `history.yml` model W1–W4 runner'da ilk tur 09-26/29.
6. **2026-09-23 football-data robots sapması (#3, oturum 8'de kapatıldı):** site AI eğitim botlarını ve kazıyıcıları
   adıyla kapattı (GPTBot, ClaudeBot, CCBot… 12 grup); `*` açık kaldı. RUNBOOK §3.7 uygulandı: bizim UA ile protego
   500/500 yol izinli (ClaudeBot 0/500) → anlık görüntü (runner diff'inden birebir kuruldu, hunk sayıları doğrulandı)
   ve `robots_verified_at` güncellendi; test yeni kural listesini birebir sabitler. **Sınır:** football-data verisi
   Jev'e/AI'a verilmiyor — Plan 2'de verilecekse bu kaynak yeniden değerlendirilir (sitenin niyeti açık).
7. **0013 sonrası (oturum 9):** bütün zamanlanmış işler `postgres` ile bağlanır ve etkilenmemeli — 21:45 mühür turu
   yeşil ölçüldü. İlk `collect-news`, `snapshot` (06:22), `collect-daily`, `shadow`, `history` turlarında bir yetki
   hatası (`permission denied`) görülürse RUNBOOK §4 ve DEFERRED 18; geri dönüş tek satır `grant`tir.

### 0.4 Plan 2'ye kadar ara iş
Yerini §0.6 (kullanıcı girdisi gerekmeyen iş listesi) ve §0.7 (toplu kullanıcı talepleri) aldı. Oturum 8'de
yapılanlar §0.2b'de.

### 0.6 Taze oturum iş listesi — kullanıcı girdisi GEREKMEYEN işler (oturum 9 için)
**Oturum 9 durumu:** Dalga A 1–4 ve Dalga B 5–6 BİTTİ, hepsi `main`de (§0.0a). Kullanıcı girdisi gerekmeyen iş
listesi tükendi; İz B'nin kalanı (0014'ün canlıya uygulanması, deploy, alan adı, hukuk) §0.7 kararlarına bağlı.
İsteğe bağlı 7 (DEFERRED 16g DC memo anahtarı) ve 8 (arşiv kapsamı runner ölçümü, 17k) yapılmadı — sonraki oturum
bunlarla ya da 2026-10-07'den sonra §0.2 (Plan 2) ile başlar.
Kullanıcı kararı (2026-09-23): Netlify'a kadar yapılabilecek her şey taze oturumda bitirilir; kullanıcıdan
istenenler (§0.7) sonra toplu verilir. Alt ajanlar Opus 5.5 high (`~/.claude/settings.json`, bellek
`subagents-opus-high`). Her dalga: ayrık dosya kümesi → worktree başına bir ajan → entegrasyon dalı → bağımsız
bütün-dal incelemesi (mutasyonlu) → düzeltme turu → DB bağlı 11/11 → `main` → CI.

**Dalga A (paralel, dosya kümeleri ayrık):**
1. **EN alan adı sıralaması (ops, ~dakikalar):** tek kullanımlık dal + `workflow_dispatch` ile runner'da T0c
   `step6_gdelt_en.py`'yi `doms.most_common(40)` basacak biçimde koş (betik `.superpowers/sdd/2026-09-23-faz4-plan1-dalga0-1/t0c/`;
   GDELT ücretsiz, ≥ 6 sn aralık, 429'da dur). Çıktı kaynak koşulları raporuna (§0.2/5) eklenir: izin listesiyle
   kaç başlık kaybedilir. Kullanıcının EN kararı (§0.7/4) bu veriyle verilir. Dal sonra silinir (uzak dal: onay).
2. **Scrapling toplayıcı adaptörü (K2, kullanıcı isteği; kural R77b, spec §3.2.1):** Scrapling TAM kullanılır —
   `Fetcher`/`DynamicFetcher`/`StealthyFetcher` ve varsayılanları (tarayıcı parmak izi taklidi, gerçekçi başlıklar);
   "dürüst kimlik" şartı kalktı. Adaptör projenin `guard_path` (robots), crawl-delay, `Retry-After` ve yönlendirme
   denetiminin ARKASINDA çalışır. **Kodla zorlanan sınırlar (AST/test bekçisi):** `solve_cloudflare` ve benzeri
   doğrulama çözme seçenekleri kapalı, proxy parametresi yok, User-Agent'ta adı verilmiş bot (`Googlebot`,
   `ClaudeBot`…) yok, 403/429'da kimlik/yol değiştirip yeniden deneme yok, yalnız `sources.yaml`da politikadan
   geçmiş kaynak. ToS'u yasaklayan kaynaklar (kaynak koşulları raporundaki 19 yayıncı, Transfermarkt, FPL, UEFA…)
   kullanılmaz — asistan bunları uygulamaz. Yeni kaynaklar `enabled: false` girer; açmak §0.7/4'e bağlı. İlk
   hedefler: TFF PFDK kararları (windows-1254, uyarlanabilir seçiciler), ajansspor gövdesi, Fotomaç/A Spor, RSS'siz
   kulüp sayfaları (koşulları okunup uygun bulunursa).
   **ÖNCE KAPI DEĞİŞİKLİĞİ (bilinçli, ayrı commit):** `tests/test_access_method_rule.py` (R80 — Scrapling
   fetcher'ları, `curl_cffi`, `camoufox`, stealth eklentileri BÜTÜNÜYLE yasak) R77b'ye göre yeniden yazılır: bu
   araçların importu serbest bırakılır, AYNI committe yeni kırmızı testler eklenir — `ProxyRotator`/proxy parametresi,
   `solve_cloudflare` ve benzeri doğrulama çözme seçenekleri, User-Agent'ta adı verilmiş bot, `sources.yaml` dışı
   hedef. Her yeni kural mutasyonla kırmızı kanıtlanır (`/loop-kit:judge-selftest` ruhu). R79/R80 kaydı
   (`docs/superpowers/specs/2026-09-22-faz2-olcumler-ve-kararlar.md`, Faz 2 D17 "Scrapling benimsenmez") ve
   DEFERRED 11c bu committe "R77b ile değişti" notu alır. Bu kapı gevşetmesi DEĞİL, kullanıcının politika kararıdır
   (2026-09-23); yine de "kapı gevşetilerek yeşil alınmaz" kuralı gereği yeni sınırlar olmadan eskisi kaldırılmaz.
3. **Küçük borçlar (K2):** DEFERRED 17n (bekçi test boşlukları), 17h'ye eklenen 17a bekçisi kaçışları (tablo adı
   sabitiyle f-string, büyük harf tablo adı, `GATES_READERS` kümesi — son inceleme M-4/M-5), 16k-b (`draw` alanı
   `ordered` biçimde isteğe bağlı; mühürlü `model_faz3.yaml` okunmaya devam eder).
4. **Dil kalibrasyonu ön-etiketleri (Plan 2 T3 hazırlığı, ücretsiz):** `news_items`tan tohumlu 100 TR + 100 EN
   haber; Opus ön-etiketler (spec §5.4: insan yalnız onaylar); kullanıcının onaylayacağı tek dosya (§0.7/5). Jev
   ÇAĞRILMAZ; ham metin depoya girmez (gitignored dizin).

**Dalga B (A'dan sonra; İz B — Netlify/alan adı/marka OLMADAN yapılabilen kısım):**
5. **İz B tasarımı:** `superpowers:brainstorming` → `docs/superpowers/specs/<tarih>-faz6-iz-b-design.md`. Marka,
   alan adı, diller, halka açık tablolar YER TUTUCU; her açık karar §0.7'ye satır olarak eklenir. Sonra
   `writing-plans` + bağımsız plan incelemesi.
6. **İz B yapımı (yerelde, deploy YOK):** T1 Next.js iskeleti + okuma katmanı (salt okuma görünümleri/rol ve RLS
   migration'ı YAZILIR ama canlıya UYGULANMAZ — §0.7/3 onayı bekler; yerel Postgres kabında test), T3 sicil sayfası
   (defterden türetilir, kapı defterle birebir uyuşmayı ölçer), T4 pSEO yapısı + `hreflang`, T5 schema.org, T6
   18+/sorumlu bahis/KVKK/çerez metin TASLAKLARI (hukuk incelemesi §0.7/7), T7 `netlify.toml` + Actions deploy
   adımı hazır ama bağlanmamış. T2 "value" rozeti Faz 5'e kadar yer tutucu; sitede value önerisi YOK (Faz 3 sonucu).

**İsteğe bağlı (vakit kalırsa):** 7. DEFERRED 16g DC memo anahtarı tasarımı (`at`ten önceki gözlem sayısı, ucuz
hesap). 8. Arşiv kapsamı runner ölçümü (17k, `step3_coverage.py 50 50`, ~4,7 saat, arka planda) — sonuç Plan 2'ye
hazır olur.

### 0.7 Kullanıcıdan TOPLU istenecekler (oturumda sorulmaz; kullanıcı hazır olunca birlikte)
1. **Marka adı** (alan adı ondan türer; `football-edge` çalışma adı).
2. **Alan adı satın alma** (ödeme kullanıcıda; kayıt yeri seçenekleri Cloudflare Registrar / Namecheap / Netlify)
   ve **Netlify hesabı** (kullanıcı açar/giriş yapar; site, deploy, DNS'i asistan kurar — Netlify araçları bağlı).
3. **Halka açık okuma katmanı:** siteye hangi tablolar/görünümler açılır (sicil, maç, kapanış…) — migration
   uygulanmadan önce onay.
4. **Haber kaynağı politikası:** EN izin listesi (`docs/reports/2026-09-23-kaynak-kosullari.md` + Dalga A/1
   ölçümü) ve ek kaynaklar (`docs/reports/2026-09-23-ek-kaynaklar.md`): önerilen kombinasyon EN = GDELT izin listesi
   + SportMonks Starter (€29/ay, yapılandırılmış sakat/cezalı) + resmî hesaplar için X API (~$60/ay tahmini) +
   Wikidata; TR = ajansspor + Fotomaç/A Spor RSS + TFF PFDK + Galatasaray RSS. Kararlar: hangileri, ücretli olanlar
   (SportMonks 14 günlük deneme = hesap açma, kullanıcı), **ajansspor 17l** (`ai-input=yes` yeterli mi, sorulsun mu).
5. **Dil kalibrasyonu etiket onayı** (200 haber; Dalga A/4 dosyası) — Plan 2 T3 bunu bekler.
6. **Ücretli Jev harcamasını açan commit** (tek satırlık komut kullanıcıya verilir; auto-mode bu commit'i yapmaz)
   ve Plan 2 maliyet ölçümü onayı.
7. **Hukuk (yayından önce, avukatla):** **sakatlık bilgisi = sağlık verisi (KVKK md. 6 / GDPR md. 9) — kaynaktan
   bağımsız, bütün projeyi ilgilendirir; takım düzeyinde toplulaştırma yeterli mi?** · Türkiye'de bahisle ilgili
   içerik/yönlendirme riski, KVKK metinleri,
   football-data'dan yazılı izin (spec §10/2), başlık telifi ve yayıncı ToS'larının aracı (GDELT/Google News)
   üzerinden bizi bağlayıp bağlamadığı (kaynak koşulları raporu §Açık sorular 2–3).
8. **Holdout 2. açılışı için açık "evet"** (Plan 2 T11 — çok sonra, ön kayıt ve kırmızı takımdan sonra).
9. İsteğe bağlı: Odds API planı (kredi; maçlar 10-09'da başlayınca tüketim ölçülür).

**Oturum 9'un eklediği kullanıcı kararları (2026-09-24):**
4b. **EN kaynağı — yeni ölçüm (T1):** izin listesi önerisi GDELT'te fiilen boş (sessiz pay %3,0: dailytrust, el-balad);
   ilk 15 alan adının 12'si yasaklıyor (AOL, thehardtackle ticari yeniden kullanım; Newsquest veritabanı/ticari).
   **CaughtOffside/JustArsenal sahibi (Rocket Sports)** arama dışı her otomatik erişimi lisanssız sayıp makale başına
   £500 talep eden bir "Search Only" sözleşmesi yayımlıyor; koşul okuması bu iki siteye robots izinli 3 istek attı
   (rapor yöntem bölümünde) — avukat sorusuna eklendi. Karar: GDELT EN ayağı hangi politikayla (ya da hiç)?
5b. **Dil kalibrasyonu onay dosyası:** `.superpowers/sdd/2026-09-23-oturum9-dalga-a/calibration/tr.review.md`
   (100 madde; önce 6 uyuşmazlık, sonra 29 sınırda). Dosyanın başındaki **açık soru:** "yaklaşan maç" haberin
   yayımlandığı ana göre mi (öneri) bugüne göre mi. Ayrıca `team` yazımı (Odds API "Fenerbahce" ↔ README "Fenerbahçe").
10. **İz B spec onayı ve AK1–AK22** (spec §16; öneriler yazılı) + planların onayı ve yürütme yöntemi (öneri: subagent
   driven; B-1 K1). Onaysız da yerel yürütme sürer (deploy yok, 0014 canlıya uygulanmaz).
11. **Silme onayları:** birleşmiş worktree'ler `.worktrees/wt-s9-{a1,borc,rls,scrapling,scrapling-clean,integ}` ve
   dalları; **yerel `feat/s9-scrapling` dalı gerçek adlı PFDK fixture'larını taşıyor** (`922a445`; hiç push
   edilmedi, `main`de yok) — silinmesi önerilir; `.superpowers/sdd/…/t3-scratch` (~1,5 GB ölçüm artığı); B-2 plan
   yazarının `/tmp`ye bıraktığı atıklar (`b2fake/`, `b2fe.bak`, `b2-tsconfig-before.json`, `b2build.log`, `x`).
   Ayrıca: `.worktrees/wt-izb-{b1,b1-t4,b1-t8,b2}` ve dalları (hepsi `main`de); SDD scratch'lerinde büyük derleme
   kopyaları (B-2 `t1-scratch/b2t1_pre-biome` ~435 MB, `t9-scratch/b2t9_mut` ~353 MB, `t9-review-scratch` ~653 MB);
   durdurulmuş ama silinmemiş kum havuzu kapları (`izb-*`, `izb-b1t*`, `izb-b2*`, `t6r-*` önekli — `docker ps -a`).
12. **TFF koşulları** (`pageID=179`): bilgi "ticari amaçlarla kullanılamaz", kaynak gösterilmeden kopyalanamaz.
   Açık `tff` kaynağını (hakem atamaları, günlük) ve kapalı `tff-pfdk`yi etkiler. Ayrıca `tests/fixtures/tff/` tam
   sayfa kopyaları (hakem adları) public repoda — kırpılsın mı?
13. **pg_net (canlıda ölçüldü, 2026-09-24):** `anon`/`authenticated`/`service_role` `net` şemasında USAGE, kuyrukta
   SELECT/INSERT ve `net.http_post` EXECUTE taşıyor (yetkiyi `supabase_admin` vermiş; `postgres` geri alamaz — kapta
   ölçüldü). Dışarıdan erişim yalnız PostgREST `net`i açarsa mümkün: **Supabase panelinde "Exposed schemas" listesinde
   `net` OLMADIĞINI doğrula** (asistanın REST yoklaması izin sınıflandırıcısınca reddedildi). `site_reader`'a LOGIN
   verilmeden önce bu artık risk kabul edilmeli (`docs/phases/06-site/HANDOFF.md` canlıya geçiş adım 3).
14. **Site yayını için GitHub ayarları (AK18):** `production` ortamını `main` dalına sınırla; `NETLIFY_AUTH_TOKEN`,
   `NETLIFY_SITE_ID` ve `SITE_DATABASE_URL` ortam kapsamlı secret olsun (`build` işi için de ortam gerekir). Bunlar,
   alan adı (AK4) ve 0014'ün canlıya uygulanması onaylanmadan `site.yml` TETİKLENMEZ.
15. **Hukuk soruları C1–C11** (B-2 T7 incelemesi): `docs/phases/06-site/HANDOFF.md` "Hukuk incelemesi" — §0.7/7'nin
   parçası (KVKK aydınlatma metni öğeleri, "kesinlikle gerekli yerel depolama" sınıflaması, sorumlu bahis dili,
   yardım hattı adları/numaraları, barındırıcının çerez/log davranışı).
### 0.5 Çalışma disiplini (Faz 3 §0.5 aynen geçerli; bu oturumun ekledikleri)
- **Model (2026-09-23, kullanıcı):** bütün alt ajanlar Opus 5.5 high — `~/.claude/settings.json`
  `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=claude-opus-5-5` + `effortLevel: high`. Aşağıdaki ve eski bölümlerdeki "K1 incelemeleri /
  kırmızı takım `fable`" notları bununla geçersiz. Ajana `model` parametresi verilmez.
- SDD betikleri ANA depo kökünden, BASE/HEAD açık SHA ile (`review-package`); worktree'ler `.worktrees/wt-faz4-*`.
- Plan yazımı: sözleşmeli paralel yazar ajanlar + tek-ağaç bağımsız plan incelemesi (iki tur) — dört görevler arası
  kırılmayı yürütmeden önce yakaladı.
- Gerçek DB'ye ilk yazım öncesi aynı SQL ROLLBACK içinde koşulur; K1 inceleyicileri yerel Postgres kabında (supabase
  17.6 imajı) migration ve INSERT'i gerçekten koşabilir.
- Temizlik: `.worktrees/wt-faz4-{a,b,c,d,e,f,fix}` ve dalları `feat/faz4-{a..f}`, `fix/faz4-plan1-final` 2026-09-23'te
  silindi (kullanıcı onayı; hepsi birleşmişti, uzakta dal yoktu). SDD defteri korunur.
- `TYPESAFE_API_KEY` 2026-09-23'te GitHub secret'ına ve `.env`e eklendi (kullanıcı; değer okunmadı). Anahtar henüz hiç
  çağrılmadı — ilk ücretli çağrı Plan 2'nin maliyet ölçümünde, kullanıcı onayıyla.

## 0.eski Önceki oturum (2026-09-23, Faz 3 kapanışında yazıldı — tarihçe)

**Faz 3 bitti.** 14 görevin hepsi `main`de; ayrıntı, kapının ne ölçtüğü ve ÖLÇMEDİKLERİ, R149–R156 ve Faz 4 ön
koşulları: **`docs/phases/03-baz-model/HANDOFF.md`**. Kısaca:
- Kapı: 1790 passed / 3 skipped (üçü `DATABASE_URL yok`) · `leakage` 336 · migration 0009/0010/0011 canlı.
- **Holdout — tek açılış** (kullanıcı onaylı): C1 ΔLL harman − piyasa 0,0001 [−0,0005, 0,0007]; harman bahis CLV
  −0,0497 (54 bahis), Placebo −0,0868; C6 0,0002 [−0,0013, 0,0018]. Jev'siz baz model piyasayı yenmiyor — Faz 4'ün
  baz çizgisi. Rapor `docs/reports/2026-09-23-faz3-holdout.md`.
- Ertelenenler DEFERRED §16 (16a–16c **bir sonraki açılıştan ÖNCE**). Defter (gitignored)
  `.superpowers/sdd/2026-09-23-faz3-model-walkforward/`.

### 0.1 Sıradaki oturum — FAZ 4 TASARIMI (taze oturum)

**Başlatma istemi (yeni oturuma yapıştır):**
> "`docs/HANDOFF.md` §0'dan devam et. Faz 4 tasarımını `superpowers:brainstorming` ile benimle başlat;
> §0.3'teki açık kararları bana sor. Kod yazma; tasarım onayından sonra `superpowers:writing-plans`."

**Okuma sırası (bu sırayla, başka bir şey okumadan):**
1. Bu bölüm (§0.1–§0.5).
2. `docs/phases/03-baz-model/HANDOFF.md` — Faz 3'ün sonucu, §3 ölçülmeyenler (özellikle §3.3), §6 Faz 4 ön koşulları.
3. `docs/DEFERRED.md` §16 (Faz 3), §15 (İz A), §14 (Faz 2).
4. Ana tasarım `docs/superpowers/specs/2026-09-19-football-edge-design.md` §4 (model), **§5 (Jev / soru bataryası /
   boru hattı rolleri / çok dillilik)**, §6.2 (holdout politikası), §9 (fazlar: Faz 4 = "Jev sinyal katmanı + özellik
   deposu + budama", kapı "baz çizgiye karşı marjinal CLV").
5. Yol haritası `docs/superpowers/plans/2026-09-21-yol-haritasi-v2-paralel-izler.md` §2 (Faz 4 dalgaları: T1 Jev
   istemcisi · T7 özellik deposu → T2–T5 soru bataryaları · T6 boru hattı rolleri → T8 budama · T9 eşdoğrusallık),
   §3 (K1/K2/K3 kademeleri), §4 (paralellik), §5 (insan kararları).
6. Faz 3 tasarımı `docs/superpowers/specs/2026-09-23-faz3-model-walkforward-design.md` — yalnız Faz 4'ün tüketeceği
   arayüzler: §5 (walk-forward bölgeleri S/E), §7 (canlı bağlam, E1–E3), §8 (ön kayıt ve tek açılış), §10 (gölge).

**Faz 3'ün Faz 4'e bıraktığı baz çizgi (karşılaştırılacak sayılar):**
- Holdout (2025/26, tek açılış): C1 ΔLL harman − piyasa 0,0001 [−0,0005, 0,0007]; LL piyasa 1,0026 · DC 1,0241 ·
  fit Elo 1,0254; harman bahis CLV −0,0497 (54 bahis); Placebo CLV −0,0868. E bölgesi (2019/20–2024/25): ΔLL 0,0002
  [0,0000, 0,0005]. **Sonuç: dil sinyali olmayan model piyasayı yenmiyor; model payı piyasadan ~0,022 LL geride.**
- Donmuş model `config/model_faz3.yaml` (sha256 `26b81642…`); harman ağırlıkları `backtest/wf_eval.frozen_weights`.

### 0.2 Faz 4'ün önündeki gerçek (2026-09-23 ölçüldü — tasarımın ilk sorusu)

1. **Dil sinyalinin tarihi YOK.** Walk-forward'un gücü 13 sezonluk fiyat tarihinden geliyordu; haber için böyle bir
   arşiv yok. `source_observations`: haber yalnız `ajansspor` (TR), **1.243 kayıt, 2026-09-04'ten beri**; başka dil
   yok. Faz 4'ün kapısı "baz çizgiye karşı marjinal CLV" ise örneklem yalnız CANLI birikimden gelir (gölge sicili +
   haber). Tasarım bunu çözmek zorunda: (a) geriye dönük haber arşivi kaynağı (lisans + robots, spec §3.2) var mı;
   (b) yoksa ölçüm yalnız ileriye dönük gölge üzerinde mi — o zaman ne kadar hafta gerekir (güç hesabı);
   (c) holdout politikası (§6.2) canlı-yalnız bir sinyal için nasıl uygulanır.
2. **Jev hiç çağrılmadı.** `.env`de `TYPESAFE_API_KEY` yok. `src/football_edge/jev.py` bir `JevClient` protokolü ve
   `TypeSafeJev` sarmalayıcısı taşır (Faz 1, varlık eşlemesi için; testler protokolü taklit eder). `typesafe-sdk`
   bağımlılığı `pyproject.toml`da. **Ön koşul (insan): API anahtarı.**
3. **Dil kalibrasyonu yapılmadı.** `config/languages.yaml`: `tr` ve `en` `production_enabled: false`;
   `data/calibration/tr.jsonl` yalnız 10 BİÇİM örneği (gerçek etiket değil). Spec §5.4: dil başına ~100 insan etiketli
   haber; ölçülmeden hiçbir dil üretime alınmaz (kapının `dil-kalibrasyonu` adımı zorlar). Yol haritası önerisi:
   Opus ön-etiketler, insan onaylar, ölçüm insan etiketine karşı.
4. **Gölge sicili yeni başladı:** `model_predictions` boş; ilk karar günlü tur 2026-09-26 cuma 12:35 UTC. Faz 3
   HANDOFF §3.3/8: eşlenemeyen tek canlı ad o ülke grubunu 10 gün bayat yapar (takma ad hijyeni şart).
5. **Maliyet tavanı:** Odds API bütçesi 500/ay (8 aktif lig, beklenen ≈455/ay, İz A R125); Jev ~$0,0004/maç (spec §5.1,
   ölçülmedi); ~35 soru × maç × lig. Haber toplama ücretsiz kaynaklarla (spec §3.2).

### 0.3 Kullanıcıya sorulacak açık kararlar (brainstorming'de)

1. Faz 4'ün değerlendirme stratejisi: geriye dönük haber arşivi mi aranacak, yoksa yalnız ileriye dönük gölge
   birikimi mi (kaç hafta, hangi güçte)? Bu karar fazın takvimini belirler.
2. `TYPESAFE_API_KEY` ne zaman verilecek; aylık Jev harcama tavanı.
3. Dil kalibrasyonu: hangi diller (TR + EN? 8 aktif ligin dilleri: EN, ES, IT, DE, FR, TR, NL)? Etiket yükü
   (dil başına ~100) kimde; Opus ön-etiket + insan onayı kabul mü?
4. Faz 4'ün ilk görevi gölge CLV raporu mu (P25, DEFERRED 16o), yoksa Faz 4'ten önce ayrı bir iş olarak mı?
5. Izgara ucu (DEFERRED 16n): Faz 4'te baz model yeniden seçilecekse ızgara genişletilsin mi?
6. Bir sonraki holdout: Faz 3 holdout'u (2025/26) harcandı; R128'e göre Faz 5 açılışından sonra durum verisi olur.
   Faz 4'ün kendi holdout'u ne (2026/27'nin bir dilimi mi)? Ön kayıt DEFERRED 16c'ye göre raporun bastığını birebir
   listelemeli.
7. Paralel iz: İz B (Netlify + alan adı — kullanıcıdan hâlâ bekleniyor) Faz 4'le paralel başlasın mı?

### 0.4 Bir sonraki holdout açılışından ÖNCE düzeltilecekler (Faz 4 planına girmeli)

DEFERRED **16a** (açılış sonrası arıza yolları: `--out` yoklaması, `fit_weights` yakınsamama), **16b** (ön kayıt
kanonik yol), **16c** (ön kayıt ↔ rapor: eşleştirilmiş ΔLL + `incomplete`/`fallback`), **16d** (faz parametresi).
Bunlar plansız kalırsa bir sonraki tek açılış riske girer.

### 0.5 Çalışma disiplini (bu projede kanıtlanmış; taze oturum bunları bilmez)

- **Süreç:** tasarım → kullanıcı onayı → plan (`writing-plans`; planın kodu plan metninden tek ağaca kurulup kapıdan
  geçirilir) → bağımsız plan incelemesi → `subagent-driven-development`. Faz 3 bu düzende 1 günde bitti.
- **Kapı:** önkoşul Node 24 — önce `source ~/.nvm/nvm.sh && nvm use 24.21.0` (Faz 6 B-2 T10'dan beri; PATH'teki
  Node 22 ile `FAIL: site-kurulum` — `HATA: Node 22, .nvmrc 24 istiyor`), sonra `TMPDIR=$(mktemp -d) ./verify.sh >
  <log> 2>&1`, sonuç LOG DOSYASINDAN. Yerelde DB'siz 16 PASS + `SKIP: site-db`, `SKIP: site-derleme/e2e`,
  `SKIP: zincir`; kum havuzu kabıyla (`SITE_TEST_DATABASE_URL`) 17 PASS + `SKIP: zincir`; `zincir` yalnız
  `DATABASE_URL` bağlıyken koşar (kipler: `docs/phases/06-site/HANDOFF.md` "B-2 T10"). Her commit'ten sonra tam kapı; `main`e `--no-ff`; push öncesi `git fetch && git merge --no-ff
  origin/main`; taze klon kapısı; CI yeşil. Force/rebase yok (bot çıpaları).
- **Worktree:** `git worktree add .worktrees/wt-<görev> -b feat/<faz>-<görev> main` (Agent'ın `isolation: worktree`ü
  bu makinede çalışmıyor). Dalga başına ≤ 4 paralel implementer, ayrık dosya kümeleri.
- **SDD betikleri** (`review-package`, `task-brief`) ANA depo kökünden koşulur (worktree'den koşulursa paketi
  worktree'nin `.superpowers/`una yazar).
- **Her dispatch'e:** "HİÇBİR ŞEY SİLME", ayrı scratch alt dizini, rapor dosyası + kısa son mesaj, holdout'u AÇMA,
  DB/.env yok (gerekmedikçe). Model parametresi verilmez (opus miras); K1 incelemeleri ve kırmızı takım `fable`.
- **İnceleme kalıbı:** inceleyici görev kodunun planla bayt eşliğini mekanik doğrular ve mutasyon tablosunu `git archive`
  kopyasında BAĞIMSIZ koşar; kendi mutasyonlarını da dener — Faz 3'te üç Important (R153–R155) böyle bulundu.
- **Ölçüm önce:** gerçek veri kararları (kadans, süre, yineleme) ölçülür, ölçüm belgesine komutuyla yazılır.
- **Takma adlar TAHMİN edilmez:** aynı gün, aynı lig, aynı ev/deplasman konumundaki tek satırdan okunur.
- **Migration'lar** Supabase `apply_migration` (proje `aaxadphezxavohkhqdrf`), doğrulama yalnız okuma sorgusuyla;
  append-only tablolara deneme satırı yazılmaz.
- **Temizlik:** Faz 3'ün worktree ve dalları 2026-09-23'te silindi (kullanıcı onayı); SDD defterleri
  (`.superpowers/sdd/*`, gitignored) korunur — kararların tam kaydı oradadır.

### 0.6 İzlenecekler (Faz 3'ün ekledikleri)
1. **2026-09-26 cuma 12:35 UTC** ilk karar günlü gölge turu: `gölge: karar N · yazılan satır M · eşlenemeyen U ·
   bayat durum B`; `U > 0` ise adlar aynı gün/lig/konum kuralıyla `config/history_aliases.yaml`a (yoksa grup 10 gün
   bayat). ned.1/bel.1'in ilk canlı maçlarından sonra `live parity` (E3) yeniden.
2. **2026-09-26 cuma 09:50 UTC** ilk `history-dispatch-friday`; **2026-09-29 salı 09:50** haftalık `history.yml`
   (selftest + model W1–W4, ~7,5 dk).
3. `history_leagues.yaml`/`history_lock.yaml` değişirse gölge ve model adımı exit 11 — `model_faz3.yaml` yeniden
   üretilmeli (Faz 3 HANDOFF §3.3/7).

**Geçmiş: oturum 6'nın açılış öncesi durağı (2026-09-23 ~09:00 UTC; kullanıcı "evet" dedi, açılış yapıldı):**
- Task 0–12 `main`de (son `bf5a06d`, CI yeşil); defter `.superpowers/sdd/2026-09-23-faz3-model-walkforward/progress.md`
  (R149–R156). Migration 0009/0010/0011 canlı; I6 kanıtı (0010 önce kırmızı, sonra yeşil); DB bağlı kapı 11/11.
- Seçim (S) `config/model_faz3.yaml`: Elo k=10, ha=65, linear, regress 0,2, newcomer 75, **ordered**; DC ξ=0,003,
  sırt=0,003. **Izgara ucu bulgusu** (k, ξ, sırt) — genişletme kararı kullanıcıda.
- E raporu `docs/reports/2026-09-23-faz3-walkforward.md`: W1 ham ΔLL 0,0002 [0,0000, 0,0005]; runner'da W1–W3 GEÇTİ.
- Ön kayıt `config/faz3_preregistration.yaml` (`c129cc3`), prova yeşil (holdout AÇILMADI), kırmızı takım temiz
  (5 Minor, R156 ile ertelendi). `holdout_access_log` = 0.
- **Sıradaki adım: Task 13 Step 7 — kullanıcının açık "evet"i, sonra Step 8 TEK açılış** (plan Task 13).

**Önceki plan notu — FAZ 3 UYGULAMASI:** "`docs/HANDOFF.md` §0'dan devam et" → planı `superpowers:subagent-driven-development`
ile yürüt; yeni worktree (`git worktree add`), dalga 0 (Task 0: scipy controller commit'i + iki gerçek veri ölçümü).
Durma noktaları: Task 13 holdout açılışı ÖNCESİ kullanıcının açık "evet"i (P14). Plan, ölçülmeyenler listesini ve
yürütme defterini kendisi taşır.

**Geçmiş: oturum 5'in başlatma tablosu (izler bitti)**

**Sıradaki oturum — PARALEL İZLER (kullanıcı kararı 2026-09-22: izler birbirini kırmadan paralel yürür)**

Yeni oturumda: "`docs/HANDOFF.md` §0'dan devam et" → bu tabloyu oku → `git worktree list` ile başla. İzler
ayrı worktree'de, ayrı dalda, AYRIK dosya kümeleriyle yürür; her iz kendi SDD defterini tutar
(`.superpowers/sdd/<plan-adı>/`). Bir izin dosyasına öteki YAZMAZ (tek-yazar kuralı).

| İz | İş | Dal · worktree | Yazdığı dosyalar (YALNIZ bunlar) | Dokunmaz |
|---|---|---|---|---|
| **A** | Lig ekleme: N1, B1, AUT (Faz 2 HANDOFF §5) | `feat/leagues-n1-b1-aut` · `.worktrees/wt-leagues` | `config/leagues.yaml`, `src/football_edge/leagues.py` (`footystats_path` isteğe bağlı), `src/football_edge/collectors/*` ve `odds_api.py` kayıtları, bunların testleri; kapı sabitleri (`verify.sh` `EXPECTED_MIN_*`) GEREKİRSE yalnız bu iz | `docs/superpowers/**`, `history/`, `backtest/`, `market/` |
| **B** | Faz 3 tasarımı ve TDD planı (model + walk-forward) | `docs/faz3-plan` · `.worktrees/wt-faz3` | yalnız `docs/superpowers/specs/2026-*-faz3-*.md`, `docs/superpowers/plans/2026-*-faz3-*.md` (+ ölçüm belgesi) — KOD YOK | `src/`, `tests/`, `config/`, `verify.sh` |
| **C** | İzleme + temizlik (ana oturum, controller) | `main` | `docs/HANDOFF.md`, `docs/RUNBOOK.md` (gerekirse) | izlerin dosyaları |

- **A — adımlar:** (1) footystats sayfası var mı ölç (yalnız `collector._guarded_get`, robots; football-data ölçümü
  gerekirse runner'da — yerel ağ ulaşamıyor); (2) `footystats_path` isteğe bağlı, altı canlı ligin davranışı sabit
  (TDD); (3) The Odds API anahtarları (ölçüm belgesi §2.5) ve **günlük kredi maliyeti hesaplanıp kullanıcıya
  sorulur — kredi harcayan etkinleştirme onaysız YOK** (bütçe 500/ay); (4) toplayıcı başına uygunluk (tff yalnız
  Türkiye); (5) `config/history_aliases.yaml` ilk canlı kapanışlardan sonra — ad TAHMİN edilmez.
- **B — adımlar:** `superpowers:brainstorming` → tasarım (kullanıcı onayı) → `superpowers:writing-plans` →
  bağımsız plan incelemesi (Faz 2 deseni: planın kodu plan metninden tek ağaca kurulur). Girdi: Faz 2 HANDOFF §3
  (ölçülmeyenler, 43 madde) ve §6 (ön koşullar: walk-forward, canlı bağlam kurucusu + eşitlik testi — bağlam VE
  `observe` akışı, Elo fiti, scipy dalga 0'ı, `final_eval` işçilere anahtar değil SEÇİLMİŞ satır verir — 12i),
  DEFERRED §12, §14. Holdout Faz 3'e dek AÇILMAZ; tasarım açılışı tek sefer ve kayıtlı yapar. Uygulama, plan
  onaylandıktan SONRA ve A birleştikten sonra başlar (A'nın lig kümesi Faz 3'ün canlı kapsamını belirler).
- **C — adımlar:** (1) 2026-09-23 sabahı ilk cron'lu `collect-daily` + footystats; (2) **2026-09-29 09:50 UTC**
  `history.yml` — selftest adımının runner'daki ilk turu (yerelde 25 sn); kırmızıysa logu oku, kapıyı gevşetme;
  (3) temizlik YALNIZ kullanıcı onayıyla: `.worktrees/wt-{parser,devig,lock,harness,sync,bridge,efficiency,selftest,
  r111,method,t11fix,measure}`, dalları `feat/faz2-*`, yerel + uzak `measure/r104-width` (hepsi birleşti ya da
  ölçüm artığı) ve Faz 2 SDD defter dizinleri.
- **Birleştirme kuralı (her iz):** kendi dalında her commit'ten sonra tam `verify.sh` (log dosyasından, SKIP adıyla);
  `main`e `--no-ff` merge ÖNCESİ `git fetch origin && git merge origin/main` + kapı; push, CI yeşil. Force/rebase yok.
  İki iz aynı anda merge ediyorsa sırayla: önce biri push'lar, öteki yeniden fetch + merge + kapı.
- **Başlatma istemi (yeni oturuma yapıştır):** "`docs/HANDOFF.md` §0'dan devam et. İz A ve İz B'yi paralel
  başlat (ayrı worktree, SDD, her dispatch'e 'hiçbir şey silme'); İz C'yi ana oturumda izle. Durma noktaları:
  A'da kredi harcayan etkinleştirme, B'de tasarım onayı."

**Oturum 4'ün kararları** (gerekçe ve bedel defterde; tam liste Faz 2 HANDOFF §4): R106 — `ci.yml` yorumu ·
R107/R113 — dalga implementer'ları ayrı worktree'lerde paralel · R108 — fikstür için ayrıştırıcı gevşetilmez ·
R109 — DEFERRED 12e T6'ya eklenmez · R110 — 0006'ya TRUNCATE tetikleyicisi · R111 — boş fazla kuyruk kırpılır ·
R112 — kilit 7.646 ile · R114–R116 — verimlilik raporu tek lig yüzünden düşmez, yakalama dar · R117 — denetçi fable ·
R118 — `DEFAULT_METHOD = power` · R119 — AST kuralı `load_files`/`parse_file`/`_parsed`ı korur · R120 — Oracle
kanaryası; K4 fiyat sütunu kontrolü · R121 — F3/F5 ertelendi, F4 kabul.

**Oturum düzeni (öğrenilenler)**
- Bağlam ~%95'e yaklaşınca devir: koşan görev bitince defter + bu bölüm + commit/push, sonra yeni oturum —
  otomatik sıkıştırmaya güvenme.
- `Agent`'ın `isolation: "worktree"`ü bu makinede çalışmıyor (WorktreeCreate hook yol döndürmüyor) → worktree'yi
  `git worktree add` ile elle aç.
- Alt ajanlar izinsiz `rm -rf` yaptı (kendi scratch dizinleri) → her dispatch'e "hiçbir şey silme" yaz; paralel
  ajanlara scratchpad'de AYRI alt dizin ver. Bazı implementer'lar rapor dosyasını yazamıyor → raporu son mesajda
  iste, controller kaydeder.
- Yerel ağ football-data.co.uk'a ULAŞAMIYOR (bağlantı sıfırlanıyor) — kaynak ölçümleri runner'da, geçici dalda.
- Scratchpad'den `gh` çağrısı → `-R popiliadam/football-edge`.

**İzlenecekler (kendiliğinden olmalı; olmazsa RUNBOOK §3)**
1. **2026-09-29 09:50 UTC `history.yml`** — selftest adımının runner'daki ilk turu (yukarıda, adım 3).
2. 2026-09-23 07:10 UTC ilk cron'lu `collect-daily` ve 10:40 yerel ilk zamanlanmış footystats turu:
   ikisi de yeşil, `açık alarm yok`. TFF atanmamış günlerde `tff: 0 yeni gözlem` normaldir (R72).
3. Bekçinin yeni kodla ilk turu (seal'in seyrek `schedule` turu): `🔴 bekçi kırmızı` açılmamalı.
4. 2026-09-26'dan itibaren `sources-audit` (05:41 UTC) robots tarihini ilk kez kendisi ilerletir.
5. CI'da bir kez `astral-sh/setup-uv` 10 dk takıldı (2026-09-22, rerun yeşil); tekrarlarsa adım düzeyi timeout
   (DEFERRED 14u).
6. **İz A sonrası:** ~~06:22 snapshot 8 anahtar~~ (09-23 yeşil); N1/B1 maçlı ilk mühür turu yeşil ve maçı mühürlüyor
   (milli ara sonrası ilk hafta); 10:40 yerel footystats turu 8 lig ok (bel.1 satır sayısı — DEFERRED 15d).

**Kullanıcıdan beklenenler** (2026-09-23 güncel)
1. Depoyu GitHub'da **Watch** etmek (alarm e-postaları) — ölçülemedi (`gh` token'ında `notifications` yok).
2. DEFERRED 10t kararı (yerel işi yetkisiz ayrı macOS kullanıcısında koşturmak) — şimdilik kabul.
3. İz B için Netlify sitesi ve alan adı.
4. **Faz 4 için `TYPESAFE_API_KEY`** ve dil kalibrasyon etiketleri (dil başına ~100; §0.3/2–3).
5. ~~Faz 2 Task 12'de lig önerisi~~ — verildi (N1, B1, AUT). ~~Worktree/dal silme onayları~~ — Faz 2 ve Faz 3 için yapıldı.
6. ~~Faz 3 holdout açılışı~~ — **2026-09-23 onaylandı ve yapıldı** (tek açılış).

---

## 1. Senin yapacağın şeyler

> **Tarihçe (Faz 1 dönemi).** Güncel ve tam kullanıcı listesi: **§0.K**.

**1. Tetikler canlı — yapman gereken bir şey yok.** `seal` (15 dakikada bir) ve `snapshot`
(06:22 UTC) Supabase pg_cron'dan `workflow_dispatch` ile tetikleniyor (0003/0004, RUNBOOK §3);
token Vault'ta `github_seal_dispatch` adıyla, süresiz. Kırmızı bir tur `ops-alert` etiketli bir
issue açar, yeşil tur kapatır; tetikler durursa bekçi `🔴 bekçi kırmızı` açar. Toplayıcılar da aynı
yolla koşar: `collect-daily` (tff, venues; 07:10 UTC) ve `collect-news` (2 saatte bir); footystats
senin Mac'inde launchd ile koşar (RUNBOOK §3.9 — Mac'in gün içinde bir kez açık olması yeter);
`fetch-results` kredi harcadığı için elle (R67). Bekçi kalan Odds API kredisini de izler. Haber
almak için depoyu GitHub'da **Watch** etmen yeterli. (GitHub'ın `schedule`ı 51 saatte ~203 mühür turunun
16'sını koşturmuş, 47 maçın kapanış fiyatı kalıcı kaçmıştı — DEFERRED §10.)

**2. Push, merge ve migration'ları asistan yapar.** Bu projede SEO eklentisi (ve onun push kapısı)
`.claude/settings.local.json` ile kapalı; Supabase migration araçlarına izin verildi.
**Asla `--force`:** `seal.yml`in bot commit'leri zincir çıpalarıdır, force push onları siler.
Push reddedilirse önce `git pull --no-rebase origin main`.

**3. robots.txt doğrulaması otomatik.** `kaynak-politikası` adımı `robots_verified_at` için
**30 günlük** tazelik ister; `sources-audit.yml` canlı robots.txt anlık görüntüyle aynıysa tarihi
kendisi ilerletir (RUNBOOK §3.7). Bir robots.txt değişirse tarih ilerlemez, tur kırmızı olur ve
`🔴 sources-audit kırmızı` açılır: o zaman robots'u elle incele. **Kapı gevşetilerek yeşil alınmaz.**

---

## 2. Canlı ve doğrulanmış durum

| Şey | Değer | Nasıl doğrulandı |
|---|---|---|
| Supabase | `football-edge` · `aaxadphezxavohkhqdrf` · eu-central-1 | ACTIVE_HEALTHY |
| Bağlantı | `aws-0-eu-central-1.pooler.supabase.com:5432` (**session** pooler) | canlı bağlanıldı, `TimeZone=UTC` |
| **Oran defteri** | **3.717 satır · 51 maç · 25 bookmaker** | Faz 0 canlı snapshot, exit 0 |
| Zincir | **SAĞLAM**, `--full` ile GENESIS'ten tarandı | Task 2: canlı `verify-chain --full` → `kontrol=3717` |
| Çıpa | `ledger/head-2026-09-19.txt` | `publish-head` |
| Append-only (oran) | UPDATE ve DELETE **reddedildi** | Faz 0: 2 test, gerçek Postgres |
| **Yeni şema** | `source_observations` · `match_results` · `entity_aliases` | Task 4: canlı migrasyon, tablo listesi doğrulandı |
| Append-only (gözlem) | UPDATE ve DELETE **reddedildi** | Task 4: gerçek veritabanında, **tam yetkili rolle** denendi |
| Toplu yazma | 200 satır yazıldı → zincir bağı geri okundu → geri alındı | Task 1: canlı Postgres sondası |
| FootyStats | 6 lig 200; tur 1 **114 gözlem**, tur 2 **0** · 09-22: runner'dan 6/6 **403**, Mac'ten 200 → iş Mac'te (R73) | Task 5: canlı ×2 · 09-22: run 35710579845 + yerel tanı |
| TFF | `pageID=600`: 7 lig / **63 satır**; tur 1 **62 gözlem**, tur 2 **0** · 09-22: 63/63 hücre boş (hakemler açıklanmamış) → 0 gözlem, hata değil (R72) | Task 6 + bağımsız inceleme · 09-22: yerel tanı, sayfa şekli sağlam |
| Ajansspor haber | **1000 yeni gözlem**, exit 0 · runner: **193** (09-22 09:28, elle) + **3** (10:07, cron) | Task M: `fetch-news` canlı · 09-22: `collect-news` turları |
| Stadyum koordinatı | **1 yeni** (Rams Park, `Q81492`) | Task M: `fetch-venues` canlı |
| **Hava yolu** | **HİÇ ÇALIŞMADI** | veritabanında uygun maç yok (R46) — olmuş gibi sayılmadı |
| **`fetch-results`** | **HİÇ KOŞMADI** | bilinçli (R45): API kredisi yakar |
| **Dil kalibrasyonu** | **HİÇBİR DİL ÖLÇÜLMEDİ** | `TYPESAFE_API_KEY` yok, insan etiketi yok |
| Kapı | 10 adım PASS + `zincir` SKIP · `main` (Task 11 kapanışı, `7ff6457` sonrası): **1530 passed, 2 skipped** · contract 18 · **leakage 265** · `a647f36`'da DATABASE_URL bağlı: 11/11, 1380 passed, zincir SAĞLAM | `main`: yerel, `TMPDIR` depo dışında, log dosyasından okundu; CI yeşil · dalga 0 (`e521ed5`) taze klonda aynı sayı |
| **Mühür (`seal.yml`)** | 09-19 14:39 → 09-21 14:15: **16 tur** (~203 beklenirdi), 15'i `exit 5`; **47 maç kalıcı kayıp** | `gh run list` + tur loglarındaki "kaçan mühür" listelerinin birleşimi |
| Tetikler (pg_cron → `workflow_dispatch`) | `seal-dispatch` (her 15 dk) ve `snapshot-dispatch` (06:22 UTC) **canlı**; 0004 09-22 06:06 UTC uygulandı; `snapshot.yml`in `schedule`ı kalktı | seal 05:45/06:00/06:15 ve snapshot 06:22 → cron `succeeded` + `204` → turlar success (controller, 09-22) |
| Toplayıcı tetikleri | `collect-daily-dispatch` (07:10 UTC), `collect-news-dispatch` (2 saatte bir) — 0005 09-22 09:27 UTC uygulandı | elle 09:28 → `204`/`204`; cron 10:07 → `succeeded` + `204` → `collect-news` yeşil |
| Alarm ve bekçi | `ops-alert` issue'ları; bekçi tetikleri, Odds API kredisini ve Mac'in kalp atışını (72 sa) izler | #1 `🔴 collect-daily kırmızı` 09:29 açıldı (github-actions, etiketli) — 10:57:58'de yeşil `collect-daily` turuyla (run 35718803834) "yeşile döndü" yorumuyla kapandı; bekçi yeni kodla henüz koşmadı |
| robots doğrulaması | otomatik (`sources-audit.yml`, RUNBOOK §3.7) | elle tur 09-22 (35715215485): 7/7 kaynak sapma yok, runner footystats robots'unu okuyor; ilk otomatik ilerletme 09-26'dan itibaren |
| Loglarda sır | Odds/TypeSafe anahtarı, `DATABASE_URL` ve parolası redakte; yakalanmayan istisna da (C7) | uçtan uca bozuk DSN → parola parçası 0; runner turlarında (daily/news/seal) sır sayımı 0/0/0 — maskeleme sınanmadı (10n) |
| Çıpa push'u | yalnız commit varsa, merge ile en çok 3 deneme, checkout güncel uç (C6) | 09:30 turu `zincir başı değişmedi — commit ve push yok`: gürültü durdu; ret→merge yolu henüz koşmadı |
| Kırmızı tur alarmı | `ops-alert` issue + dispatch bekçisi (`scripts/ops_alert.py`, RUNBOOK §3.6) | runner'da ve gerçek GitHub'da koştu: #1 açıldı, 10:57:58'de yeşil `collect-daily` turuyla (run 35718803834) "yeşile döndü" yorumuyla kapandı |
| footystats yerel işi (Mac) | launchd, 4 dilim + oturum açılışı, UTC günü başına bir tur; rapor `footystats-local.yml`; kalp atışı 72 sa, kendi alarmı (R73–R76) | Kuruldu 2026-09-22 10:57 UTC: ilk tur `main` `6dccfa8` ile **114 yeni gözlem**, exit 0; rapor → `footystats-local.yml` yeşil (`açık alarm yok`) |
| Odds API | **494/500 kredi** | Faz 1 bir kredi bile harcamadı |

`.env` (gitignored, izin 600): `ODDS_API_KEY`, `DATABASE_URL`. **`TYPESAFE_API_KEY` `.env`de ve
repoda YOK** — ama kullanıcının kabuk ortamında tanımlı (09-22 ölçüldü, değer okunmadı). Dil
kalibrasyonu (`calibrate`, PARA HARCAR) bununla koşulabilir; karar kullanıcıda.

---

## 3. Faz 1 ne üretti

13 görev · 5 paralel worktree · **0 Critical** bulgu · **40'tan fazla Important**, hepsi
kapatıldı · 98 → **365 test** (+18 `contract` etiketli).

Her görev ayrı bir inceleme ajanından geçti; her düzeltme turu kendi re-review'ünü aldı.
İncelemeciler rapora güvenmedi: mutasyonları izole klonlarda (`git archive`) canlı uygulayıp
RED gördüler, sonra geri aldılar.

**Ne kuruldu:** kaynak kayıt defteri ve robots.txt'in **kodla zorlanması** · toplayıcı çatısı
(`fetch → doğrula → yaz`) · append-only gözlem deposu · beş toplayıcı (FootyStats xG, TFF
hakem, Ajansspor haber, stadyum/hava, maç sonucu) · saf Elo motoru · varlık eşleme (Jev) ·
dil kalibrasyon harness'ı ve üretim kapısı. Ayrıca Faz 0'ın iki borcu kapandı: oran defterine
**toplu yazma** ve `verify-chain --full` + haftalık tam tarama.

**Öğretici olan üç şey** — ayrıntı `docs/phases/01-toplayicilar/HANDOFF.md` §6:

1. **Doğrulanmamış bir ölçüm YÖNTEMİ, hiç ölçmemekten tehlikelidir.** Bir regex'in örtüşen
   eşleşmeleri yutması, doğru olan spec'i "düzelttirdi" ve toplayıcıyı boş bir sayfaya
   yönlendirecekti. Yanlış sonuç "ölçüldü" etiketiyle dolaşır.
2. **Kırmızı veremeyen bir test, planın KENDİ verdiği kodda en az dört kez çıktı.** Kuralı
   yazan taraf, kendi ürettiği testlerde çiğnedi. Artık her testin kırmızı verebildiği
   mutasyonla kanıtlanıyor.
3. **Tipli bir arayüz cevabın ŞEKLİNİ garanti eder, DOĞRULUĞUNU asla.** Model, sunulan
   seçenekler kümesinin dışından bir cevap döndürebiliyordu ve o değer veritabanına
   yazılıyordu. Üyelik artık BİZİM tarafımızda kontrol ediliyor.

---

## 4. Verilen kararlar (Ruling listesi)

Tam gerekçeler `.superpowers/sdd/2026-09-19-faz1-toplayicilar/progress.md` içinde — **o dizin
gitignored, yani merge etmez ve yalnız bu makinede durur.** Faz 2'yi bağlayan ruling'ler
`docs/phases/01-toplayicilar/HANDOFF.md` **§4**'te; ertelenen minor bulgular
`docs/DEFERRED.md` **§9**'da. Başlıcaları:

1. **`declared_paths` GERÇEKTEN ÇEKİLEBİLİR URL olmalı, temsilî önek değil.** Önek, kapının
   hiç istenmeyen bir yolu ölçmesine yol açar — izinli kaynağı kapatır ya da izinsizi geçirir.
2. **User-agent sahteciliği YOK.** Plan `ClaudeBot` kimliğini kullanıyordu; ClaudeBot
   Anthropic'in tarayıcısıdır, biz değiliz. *Ölçüldü: dürüst kimliğin bedeli sıfır.*
   **2026-09-22 (R77):** erişim yöntemi kuralı olarak genişletildi — izinli (dürüst kimlikli
   headless tarayıcı, adaptive seçiciler, resmî API, izin istemek, meşru ortam) ve yasak
   (kimlik/parmak izi taklidi, bot kontrolü ya da CAPTCHA aşma, IP/proxy döndürme, 403/429'u
   yok sayma) listeleri spec §3.2.1'de.
3. **RFC 9309 uyumlu ayrıştırıcı zorunlu** (`protego`). stdlib iki YÖNDE birden yanlıştı.
4. **Ham üçüncü taraf içeriği depoya girmez** — public depoda commit etmek yayınlamaktır.
5. **`access_basis: robots | api_terms`** — API host'u ile web sitesi ayrımı koda geçti,
   `api_terms` kaynaklar `terms_url` taşımak zorunda ve kapı denetliyor.
6. **Kısmî kayıp sessiz geçemez** — bulunandan az yazan bir tur "başarı" raporlayamaz.
7. **`written` COMMIT'TEN SONRA sayılır.** Faz 0'ın dört düzeltme turuna mal olan hata:
   *"başarısız değil" ≠ "kalıcı olarak yazıldı."* R48 venues/news/results'ta düzeltti;
   footystats ancak son bütün-dal incelemesinde düzeldi (I-1,
   `test_collect_does_not_count_a_league_whose_commit_fails`). tff sayıyı yalnız commit
   başarılıysa döndürür.
8. **Saat dilimi iki tarafta da zorlanır** — istek tarafında UTC guard, yanıt tarafında
   `timezone=GMT`. *200, doğru veriyi aldığımızın kanıtı değildir.*
9. **`assert_fresh` yalnız KAYNAĞIN verdiği `observed_at` üzerinde çağrılır** — toplayıcı
   kendi `now`unu basıyorsa iddia her zaman doğrudur, yani hiçbir şey ölçmez.
10. **Zamanlama Faz 1 kapsamı değil** — ama "hiç koşmayan toplayıcı hiçbir şey toplamaz"
    gerçeği adıyla yazıldı, sessizce varsayılmadı.
11. **Kalibrasyon harness'ı yazılır, ölçüm ertelenir.** Spec §5.4'ün şartını **karşılamıyor
    ve karşıladığını iddia etmiyoruz.**
12. **`collect.py` 800 satır sınırında teslim edilmez** — üç kez bölündü (`anchors.py`,
    `fetch.py`, `rounds.py`), 515'e indi.

---

## 5. Kapının ÖLÇMEDİĞİ şeyler

**Tam liste: `docs/phases/01-toplayicilar/HANDOFF.md` §3 — hepsi adıyla.**
Bir sonraki fazın üstüne inşa etmemesi gerekenler:

1. ~~**TOPLAYICILAR HİÇBİR YERDE KOŞMUYOR.**~~ **09-22'den beri koşuyor:** `collect-daily`
   (tff, venues) ve `collect-news` pg_cron'dan, footystats Mac'te launchd ile (R73). Kapsam hâlâ
   dar: TFF yalnız bu haftayı, venues tek stadyumu veriyor (madde 9, 10).
2. **DİL KALİBRASYONU HİÇBİR ŞEY ÖLÇMEDİ** ve spec §5.4'ün Faz 1 şartı **KARŞILANMADI.**
   Kapı yeşil, çünkü ölçtüğü soru "ölçülmemiş bir dil açık mı" ve cevap "hayır". **Yeşil
   kapı, ölçümün yapıldığı anlamına gelmiyor.**
3. **`fetch-results` hiç koşmadı** (bilinçli, kredi); **`fetch-venues`in hava/UTC yolu hiç
   koşmadı** (veritabanında uygun maç yok).
4. **`source_observations`ın HASH ZİNCİRİ YOK** — özellik girdisi kurcalanırsa dış çıpa
   bunu göstermez.
5. **Varlık eşlemenin insan gerçek-referansı YOK.** Eşiğin altı reddediliyor, ama eşiğin
   ÜSTÜNDEKİ bir eşleşmenin DOĞRU olduğunu hiçbir şey doğrulamıyor. `map-entities` bugün
   yalnız `footystats`ı eşliyor ve **`entity_aliases`ı üretimde hiçbir şey okumuyor.**
6. **Elo'nun `k`, `home_advantage` ve marj eğrisi FİT EDİLMEMİŞ iskeledir.**
7. **FBref kapalı → GLOBAL HAKEM VE SEYİRCİ VERİSİ YOK.** Faz 3'ün baz modeli hakem
   özelliği **olmadan** kurulmalı. Understat kapalı → altı ligin xG'si **tek kaynakta**,
   yedek yok. ClubElo kullanılamaz.
8. **Google News hem robots ile kapalı hem lisansı amaçlanan kullanımı yasaklıyor** —
   adaptör `enabled: false` teslim edildi; spec §3.2/1'in kaçış yolu fiilen kapalı.
9. **TFF yalnız bu haftayı veriyor**; VAR/AVAR sayfada `(V)`/`(A)` olarak **var ama
   toplanmıyor.** **Ajansspor'un yapısal yolları kapalı → muhtemel 11 ve sakat/cezalı
   listesi ALINAMIYOR** (spec §3.1 bunları bekliyordu).
10. **`fetch-venues` tam olarak BİR stadyum kapsıyor** — "hava özelliği var" varsayımı
    bugün yanlıştır.
11. **`source_observations`ta iki kalıcı sonda satırı var** ve kaldırılamaz (kaldırmanın tek
    yolu `DISABLE TRIGGER`, RUNBOOK §2.3 yasaklıyor). Korumanın çalıştığının da kanıtı.
12. **`seal.yml` sığ checkout yapıyor** → çıpa silme tespiti 15 dakikalık turda değil,
    haftalık `full-scan.yml`de: gecikme **en fazla 7 gün**.
13. **`cur.rowcount`un `executemany` sonrası davranışı canlı Postgres'e karşı doğrulanmadı**
    — etkilenen raporlanan SAYI, yazılan satırlar değil.
14. ~~**Faz 1'in beş workflow'unun hiçbiri bir runner'da koşmadı**~~ 09-22'de `collect-daily`,
    `collect-news` ve `sources-audit` koştu (canlı robots sapması: 7/7 kaynak yok). `full-scan`
    henüz koşmadı; `collect-daily`nin ilk turu footystats 403'ü ve TFF'nin atanmamış haftasını
    buldu (R72, R73).
15. Faz 0'dan devreden ve kapanmayan: en az yetkili rol yok · `shellcheck`/`actionlint` yok ·
    `mypy` `tests/`i görmüyor · coverage yok · secret taraması git geçmişini taramıyor.
16. **`latest_observations` güncel durumu DEĞİL, içerik başına İLK görüleni döner.** Bir değer
    geri dönerse (X → Y → X) "en yeni" **Y** çıkar, hatasız. Faz 2 gözlem deposunun "en
    yeni"sini güncel durum sanmamalı; düzeltme migrasyon ister —
    `docs/phases/01-toplayicilar/HANDOFF.md` §3.9/31.

---

## 6. Faz 2 — nereden başlanır

**Yol haritası:** `docs/superpowers/plans/2026-09-19-faz-1-7-yol-haritasi.md` (Faz 2 bölümü)
**Ön koşullar:** `docs/phases/01-toplayicilar/HANDOFF.md` §5
**Devralınan borç:** `docs/DEFERRED.md` (§9 Faz 1'indir)

Faz 2 = tarihsel taban · backtest harness · piyasa verimliliği · sızıntı denetimi. **Tamamlandı (2026-09-22) —
devir belgesi `docs/phases/02-tarihsel-taban/HANDOFF.md`**; bu bölüm yalnız başlangıç bağlamıdır.

**Birincil girdi football-data.co.uk'tur** (Faz 2 tasarımı D1; `xgabora/Club-Football-Match-Data` bırakıldı:
kapanış oranı yok, ek ligler 2024-12'de bitiyor — ölçüm belgesi
`docs/superpowers/specs/2026-09-22-faz2-olcumler-ve-kararlar.md`). Lisans sorusu artık doğrudan football-data
içindir (ana spec §10/2): özel depolama, yalnız türetilmiş sayısal özellik, ham satır yayımlanmaz; ticari
lansmandan önce avukat ve site sahibinden yazılı izin.

**Faz 1'in zamanlama borcu İz C'de ödendi:** dört `fetch-*` komutu `collect-daily` / `collect-news` ile
pg_cron'dan tetikleniyor (0005 uygulandı — §2); `fetch-results` kredi harcadığı için elle (R67).

---

## 7. Çalışma disiplini (bu projede öğrenilenler)

- Kapı çıktısı **dosyadan** okunur. `SKIP` geçmek değildir, adıyla raporlanır.
- **Bir ölçüm YÖNTEMİ doğrulanmadan sonucu kural yapılmaz.** Yanlış sonuç "ölçüldü"
  etiketiyle dolaşır ve doğru olan kaydı devirir.
- Bir test, konusunu **yeniden yazıyorsa** yalnız aynı kodu iki kez yazabildiğinizi
  kanıtlar. Her testin **kırmızı verebildiği mutasyonla kanıtlanır.**
- **Planın yazarlığı kendi işini notlandıramaz.** Plan-mandated bir bulgu da bulgudur.
- **Tipli bir arayüz cevabın şeklini garanti eder, doğruluğunu asla.**
- Implementer koşarken **`git add -A` yok** — yalnız açık yollar.
- Append-only tabloya test satırı yazma: silinemez. Sondayı **transaction içinde** koş,
  geri al. (Bu kural Faz 1'de ihlal edildi ve bedeli iki kalıcı satır oldu.)
- Paralel implementer **yalnız izole worktree'de**, ve **tek-yazar** sınırı dispatch'ten
  ÖNCE taranır. Faz 1'de beş dal sıfır çakışmayla birleşti.
- Her görev: implementer → rapor → inceleme paketi → inceleme ajanı → defter. Atlanmaz.
- Model: varsayılan **opus**, çok karmaşık işlerde **fable**, **haiku asla**.
- Mutasyon kanıtı `PYTHONDONTWRITEBYTECODE=1` ile koşulur: aynı boyutlu, aynı saniyede geri alınan
  düzenleme bayat `.pyc` bırakır ve geri yüklenen kaynak mutant bytecode'u çalıştırır.
- Son doğrulama taze bir klonda ve `TMPDIR` klonun DIŞINDA: bir test `tmp_path`in git deposu
  dışında olduğunu varsayıyor (R63).
- GitHub `schedule`ı güvenilmez (51 saatte ~203 turun 16'sı): kaçırılamaz işler pg_cron →
  `workflow_dispatch` ile tetiklenir.
- `main`e bot yazıyor: push'tan önce fetch + merge, asla rebase ya da force.
- Loglar public: yeni bir kimlik bilgisi `_log_secrets`e de eklenir (RUNBOOK §3.8, DEFERRED 10o).
- Risk kademeleri ve paralel dalga kuralları yol haritası v2 §3–§4'te: K1 (defter, mühür, model,
  güvenlik) tam inceleme; en çok 4 paralel implementer; her dalgadan önce tek-yazar taraması.

---

## 8. 2026-09-21/22 oturumunda verilen görevler

Her ajan işi aynı yoldan geçti: brief → implementer (izole worktree) → bağımsız inceleme (opus) →
düzeltme turu → controller mutasyon doğrulaması → `main`e `--no-ff` → taze klon kapısı.

### 8.1 Ajanlara verilen görevler
1. **Faz 1 son inceleme düzeltme turu (Task F)** — limite takılıp yarım kalan dalga tamamlandı:
   `4158f81` (kod), `370caae` (belgeler); kontrol incelemesi 12/12 ADDRESSED; yedi artık (R62):
   `28cbd4f`, `1f6a9b6`.
2. **Faz 1'in `main`e alınması** (controller): `e9acd0f` (origin çıpaları, merge), `668ec61`.
3. **C1 — mühür tetiği** (controller): migration 0003 + testler + RUNBOOK §3 (`e4a3dae`, `1975e5c`,
   `940caef`); yol haritası v2 (`ee65f52`).
4. **Task A — çıpa gürültüsü:** `b2658d7` + düzeltme `10b7e11` → `ee07601`. İnceleme: tek-alan testi
   eksikti (Important), UTF-8 olmayan çıpa (Minor) — ikisi de düzeltildi.
5. **Task B — snapshot pg_cron + `ops-alert` + bekçi:** `8d7ab72`, `1df6d83` + `f4c2d57`, `a75c302`
   → `3b00066`; 0004 uygulandı ve canlıda doğrulandı. İnceleme: bekçi alarmı kendini geri
   çekiyordu → kendi issue'su (R66).
6. **Task C3 — toplayıcı zamanlaması:** `151620f` + `6c12d0d` → `36fc89c` (0005 uygulanmadı — §0).
7. **Task C5 — kredi bekçisi + toplayıcı tetik izleme:** `9c687af`, `d6e46c6` + `49fa13a` → `6fdf093`.
8. **Task C4 — robots otomatik yeniden doğrulama:** `4383c6a`, `b27c062`, `368a189` + `07b2af9`,
   `6c82e11`, `9de9875` → `1f89c17` (controller'ın bulduğu `os.replace` kör noktası kapatıldı).
9. **Entegrasyon** (controller): bekçinin izlediği her workflow var + push'lamayan her checkout
   token'ı diske yazmaz (`d0e37c7`), belgeler (`a02158c`), E501 (`8a5456c`).
10. **Task C7 — loglarda sır (K1):** `1a605a0`, `5c6c407` + `f46ac76` → `596b025`, yorum `8465077`.
    İnceleme: yakalanmayan istisna parolayı public loga basıyordu, DSN parolası libpq ile
    uyuşmuyordu — düzeltildi, uçtan uca doğrulandı.
11. **Task C6 — çıpa push'u + checkout güncel uç + test bölme:** `ace2abc`, `731fc4d`, `d38fa9d` →
    `3009c5b` (`tests/test_workflows.py` 1030 → 610 satır; saf taşıma).
12. **Belgeler:** `40dc723`, `6973cde`, `d086d4f`, `f86bb03` ve bu devir.

### 8.2 Kullanıcıya verilen görevler
1. `git push origin main` (iki kez) — **yapıldı** (`4b6a143..668ec61`, `dd963ce..b1eea7c`).
2. `git pull --no-rebase origin main` — **yapıldı** (gerek kalmamıştı).
3. Migration 0003'ü SQL editöründe çalıştırmak — **yapıldı**.
4. Fine-grained GitHub token (hazır form: yalnız bu depo, Actions: Read and write, süresiz) — **yapıldı**.
5. Token'ı Vault'a `github_seal_dispatch` adıyla koymak — **yapıldı**.
6. `.claude/settings.local.json` (SEO eklentisi kapalı + Supabase migration izni) — **yapıldı**,
   yeni oturumda etkin.
7. Depoyu GitHub'da **Watch** etmek — **açık** (alarm e-postaları için).
8. `/pseo-approve` — **kullanılmamalı**: onay ilgisiz `bigcat-tr` defterine düşer.

### 8.3 Bu oturumun kararları (R55–R71; gerekçe ve bedel defterde)
R55 yarım dalganın diff'i korundu (mutasyonla doğrulandı) · R56 #M10 gerçekten kapatıldı · R57 PFDK
uygulanmadı, kayda geçti · R58 yeni §3 maddeleri §3.9'da, eski numaralar sabit · R59 #M28 tek yönlü
bağ (fetched ⊆ declared) · R60 secret adı elle eklendi, türetme testi ertelendi · R61 donmuş sayılar
kaldırıldı · R62 yedi artık tek turda · R63 `TMPDIR` test varsayımı park edildi · R64 origin/main
rebase değil merge · R65 A'nın iki bulgusu düzeltildi · R66 bekçinin kendi alarmı · R67
`fetch-results` zamanlanmadı (kredi) · R68 C3 Minor'ları + `persist-credentials` · R69 C4 Minor'ları;
seal push'u ayrı iş (C6) · R70 C7: excepthook + libpq + bütün kök handler'lar · R71 seal checkout
güncel uç + test dosyası bölme.

### 8.4 2026-09-22 oturum 2 (HANDOFF §0'dan devam)
**Operasyon (controller):** 13 bot çıpa commit'i `--no-ff` birleşti (`646e4d8`), taze klon kapısı,
push; 0005 uygulandı; toplayıcılar elle ve cron'la tetiklendi; ilk `collect-daily` turunun iki
kırmızısı teşhis edildi (yerel tanı, kaynak başına tek istek, veritabanına yazmadan).

**Ajanlara verilen görevler**
1. **T1 — TFF atanmamış hafta (K2):** controller TDD + 5/5 mutasyon → `063e0b6`; inceleme
   (feature-dev:code-reviewer) APPROVED + 1 Important (ayırt edilemeyen durum adıyla, `76739f2`)
   → `c715e01`. Not: bu ajan tipinin kabuğu yok, mutasyonları elle izledi.
2. **T2 — footystats yerel işi (K2):** `c5489b1` (collect-daily'den çıkar) + `cce76f7` (launchd
   işi, 16/16 mutasyon); inceleme (general-purpose, kabuklu) CHANGES REQUESTED: 4 Important,
   20 mutasyonun 12'si kaçtı. Düzeltme turu `e1e3054` (R74, R75; 35/35 mutasyon) → yeniden
   inceleme CHANGES REQUESTED: **Critical** — test dosyasının sahte `.env` satırları kapının
   `secrets` adımını düşürüyordu (birleşseydi mühür turları ilk adımda düşerdi; dalda
   `verify.sh`'ın tamamı koşulmamıştı) + 2 Important → `19a921c` (R76; taze klonda kapı yeşil,
   12/12 mutasyon) → son kontrol APPROVED.

**Kullanıcıya verilen görev:** FootyStats kararı (AskUserQuestion) — **"Mac'te günlük iş"** seçildi.

**Kararlar (gerekçe ve bedel defterde):** R72 TFF: sıfır maç satırı fırlatır, hepsi meşru
görevlisizse boş sonuç; "boş hücre" = `<a>` yok VE metin yok · R73 footystats GitHub-hosted
runner'da koşmaz (test sabitliyor), Mac'te launchd · R74 sonuç `footystats-local.yml`e raporlanır:
alarmı github-actions açar (kendi token'ınla açılan issue bildirim üretmez), raporlar bekçinin kalp
atışı (72 sa) · R75 dört dilim + oturum açılışı + UTC-gün damgası, fetch yeniden denemesi, klon
yoksa yeniden klon, betik `main`den kendini günceller, kurucu atomik yazar ve `bootstrap`ı yeniden
dener · R76 Mac'in kalp atışı bekçi alarmını paylaşmaz (`footystats-local` başlığı, bekçi yalnız
açar); bir deponun kendi `scripts/` kopyası kendini güncellemez.
