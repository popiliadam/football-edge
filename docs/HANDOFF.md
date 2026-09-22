# football-edge — Oturum Devri (Handoff)

**Son güncelleme:** 2026-09-22 · **Durum:** **Faz 1 `main`'de; İz C (işletme) C1–C5 tamam** — mühür, snapshot ve toplayıcılar
pg_cron'dan tetikleniyor, kırmızı tur `ops-alert` issue'su açıyor, robots doğrulaması otomatik
(RUNBOOK §3); loglarda sır yok; çıpa push'u yarışa dayanıklı · **Dal:** `main` · kapı **9 adım
yeşil + `zincir` adıyla SKIP** (ölçüm §2)

> Giriş sırası: `README.md` → bu dosya → `docs/DEFERRED.md`.
> Faz 1'in detaylı "ölçülmeyenler" listesi: `docs/phases/01-toplayicilar/HANDOFF.md` **§3**.
> Faz 0'ınki: `docs/phases/00-kayit-altyapisi/HANDOFF.md` §3.
> Arıza prosedürleri: `docs/RUNBOOK.md`.

---

## 0. Sonraki oturum — buradan başla (2026-09-22'de yazıldı)

**Neden yeni oturum:** bu oturumda SEO eklentisinin `outward_action_gate` hook'u oturum başında
yüklendiği için push engellendi. Eklenti bu projede `.claude/settings.local.json` ile kapatıldı;
yeni oturumda yüklenmez ve push'u asistan yapar. (Aynı dosya Supabase `apply_migration` /
`execute_sql` araçlarına izin verir.)

**Başlangıç durumu**
- Yerel `main` `origin/main`in ~40 commit önünde ve push'lanmadı; `origin/main`de ise
  `seal.yml` botunun çıpa commit'leri birikiyor (her 15 dakikada bir, push gidene kadar).
- Son kapı: `d086d4f` taze klon — 9 adım PASS, 542 passed / 2 skipped, contract 18,
  `SKIP: zincir` (DATABASE_URL yok; zincir yalnız `seal.yml`de koşar).
- Veritabanında canlı: migration 0003 + 0004 — `seal` her 15 dakikada, `snapshot` 06:22 UTC,
  ikisi de 2026-09-22'de `204` + success ile doğrulandı. **0005 UYGULANMADI.**
- Açık worktree yok. SDD defterleri (gitignored, yalnız bu makinede):
  `.superpowers/sdd/2026-09-19-faz1-toplayicilar/`, `.superpowers/sdd/2026-09-22-isletme/`.

**Sırayla yapılacaklar**
1. `git fetch origin` → `git merge --no-ff origin/main` (**asla rebase, asla force**: bot
   commit'leri zincir çıpalarıdır) → `git push origin main`. Reddedilirse fetch + merge'i tekrarla.
2. Push'tan SONRA `db/migrations/0005_collect_dispatch.sql`i Supabase aracıyla uygula. Sıra
   önemli: GitHub `main`de olmayan bir workflow'u tetiklemez (404).
3. `select ops.dispatch_collect_daily();` ve `select ops.dispatch_collect_news();` bir kez →
   `net._http_response` `204` → `gh run list --workflow collect-daily.yml` / `collect-news.yml`.
   Bu toplayıcılar hiçbir runner'da koşmadı: ilk turlar kırmızı olabilir; `🔴 collect-* kırmızı`
   issue'sundaki tur loguna bak, kök nedeni düzelt.
4. Doğrula: RUNBOOK §3.3 sorgusu (bütün `*-dispatch` işleri `succeeded` + `204`); zaman damgası
   çıpa commit'leri durdu mu (`git log origin/main` — artık yalnız baş değişince ya da yeni günde);
   bekçinin "hiç tur yok" alarmı toplayıcılar koşunca kapanmalı.
5. İzle: 2026-09-27 05:41 UTC `sources-audit` turu — ilk otomatik robots tarihi ilerletmesi ve bot
   push'u; ilk canlı `ops-alert` kırmızı→yeşil döngüsü (DEFERRED 10a).
6. Hafızadaki `pending-push-deadline` notunu sil.
7. Sonra yol haritası v2 (`docs/superpowers/plans/2026-09-21-yol-haritasi-v2-paralel-izler.md`):
   İz A — Faz 2'nin tam TDD planı (dalga 1: MIT yükleyici ∥ vig temizleme ∥ holdout ∥ harness
   iskeleti) ve İz B — Faz 6 iskeleti, paralel. İz B için Netlify hesabı ve alan adı kullanıcı kararı.

**Son tarih: 2026-10-02.** 0004 canlı ve eski `snapshot.yml` (GitHub `schedule`lı) origin'de
durdukça snapshot günde iki kez koşabilir; milli maç arasında bedeli 0, maçlar 7 günlük pencereye
girince (~10-02) Odds API kredisi iki kat harcanır.

**Kullanıcıdan beklenen tek şey:** depoyu GitHub'da **Watch** etmek (alarm e-postaları için).

---

## 1. Senin yapacağın şeyler

**1. Tetikler canlı — yapman gereken bir şey yok.** `seal` (15 dakikada bir) ve `snapshot`
(06:22 UTC) Supabase pg_cron'dan `workflow_dispatch` ile tetikleniyor (0003/0004, RUNBOOK §3);
token Vault'ta `github_seal_dispatch` adıyla, süresiz. Kırmızı bir tur `ops-alert` etiketli bir
issue açar, yeşil tur kapatır; tetikler durursa bekçi `🔴 bekçi kırmızı` açar. Toplayıcılar da aynı
yolla koşar: `collect-daily` (footystats, tff, venues; 07:10 UTC) ve `collect-news` (2 saatte bir);
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
| FootyStats | 6 lig 200; tur 1 **114 gözlem**, tur 2 **0** | Task 5: canlı ×2, CLI + doğrudan DB sorgusu |
| TFF | `pageID=600`: 7 lig / **63 satır**; tur 1 **62 gözlem**, tur 2 **0** | Task 6 + bağımsız inceleme, canlı site + canlı DB |
| Ajansspor haber | **1000 yeni gözlem**, exit 0 | Task M: `fetch-news` canlı |
| Stadyum koordinatı | **1 yeni** (Rams Park, `Q81492`) | Task M: `fetch-venues` canlı |
| **Hava yolu** | **HİÇ ÇALIŞMADI** | veritabanında uygun maç yok (R46) — olmuş gibi sayılmadı |
| **`fetch-results`** | **HİÇ KOŞMADI** | bilinçli (R45): API kredisi yakar |
| **Dil kalibrasyonu** | **HİÇBİR DİL ÖLÇÜLMEDİ** | `TYPESAFE_API_KEY` yok, insan etiketi yok |
| Kapı | 9 adım PASS + `zincir` SKIP · 542 passed, 2 skipped | `d086d4f` ağacı, taze klon, secret'sız, log dosyasından okundu (09-22) |
| **Mühür (`seal.yml`)** | 09-19 14:39 → 09-21 14:15: **16 tur** (~203 beklenirdi), 15'i `exit 5`; **47 maç kalıcı kayıp** | `gh run list` + tur loglarındaki "kaçan mühür" listelerinin birleşimi |
| Tetikler (pg_cron → `workflow_dispatch`) | `seal-dispatch` (her 15 dk) ve `snapshot-dispatch` (06:22 UTC) **canlı**; 0004 09-22 06:06 UTC uygulandı; `snapshot.yml`in `schedule`ı kalktı | seal 05:45/06:00/06:15 ve snapshot 06:22 → cron `succeeded` + `204` → turlar success (controller, 09-22) |
| Toplayıcı tetikleri | `collect-daily-dispatch` (07:10 UTC), `collect-news-dispatch` (2 saatte bir) — 0005 **veritabanına UYGULANMADI** | `collect-*.yml` `main`e push'lanınca uygulanacak (GitHub `main`de olmayan workflow'u tetiklemez) |
| Alarm ve bekçi | `ops-alert` issue'ları; bekçi tetikleri ve Odds API kredisini izler | kod `main`de, testli; hiçbir runner'da henüz koşmadı |
| robots doğrulaması | otomatik (`sources-audit.yml`, RUNBOOK §3.7) | ilk otomatik ilerletme 2026-09-27 05:41 UTC turunda bekleniyor |
| Loglarda sır | Odds/TypeSafe anahtarı, `DATABASE_URL` ve parolası redakte; yakalanmayan istisna da (C7) | uçtan uca bozuk DSN `verify-chain` → parola parçası stdout/stderr'de 0 (controller, 09-22) |
| Çıpa push'u | yalnız commit varsa, merge ile en çok 3 deneme, checkout güncel uç (C6) | gerçek git sığ klon senaryoları; runner'da henüz koşmadı |
| Kırmızı tur alarmı | `ops-alert` issue + dispatch bekçisi (`scripts/ops_alert.py`, RUNBOOK §3.6) | Yalnız MockTransport testleri — runner'da ve gerçek GitHub'da **henüz koşmadı** |
| Odds API | **494/500 kredi** | Faz 1 bir kredi bile harcamadı |

`.env` (gitignored, izin 600): `ODDS_API_KEY`, `DATABASE_URL`. **`TYPESAFE_API_KEY` YOK.**
Repoda hiçbir yerde geçmiyor.

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

1. **TOPLAYICILAR HİÇBİR YERDE KOŞMUYOR.** Zamanlama yok, cron yok, workflow yok.
   Kütüphane + CLI olarak teslim edildiler. **Hiç koşmayan toplayıcı hiçbir şey toplamaz.**
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
14. **Faz 1'in beş workflow'unun hiçbiri bir runner'da koşmadı**; canlı robots sapması bir
    kez bile ölçülmedi.
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

Faz 2 = tarihsel taban · backtest harness · piyasa verimliliği · sızıntı denetimi.

**Faz 1'in zamanlama borcu İz C'de ödendi:** dört `fetch-*` komutu `collect-daily` /
`collect-news` ile pg_cron'dan tetikleniyor (0005 push'tan sonra uygulanacak — §0); `fetch-results`
kredi harcadığı için elle (R67). Sıra ve paralellik: yol haritası v2 (§0/7).

**Faz 2'nin birincil girdisi `xgabora/Club-Football-Match-Data`dır ve lisans zinciri hâlâ
açık bir sorudur** (MIT ilan ediyor, verisi football-data.co.uk'tan türemiş, o kaynağın
lisansı ticari türevleri dışlıyor). Eğitim verisi olarak kullanılır, ham satır yayınlanmaz.

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
