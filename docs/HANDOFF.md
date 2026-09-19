# football-edge — Oturum Devri (Handoff)

**Son güncelleme:** 2026-09-19 · **Durum:** **Faz 1 TAMAM — `faz-1-toplayicilar` merge'e HAZIR**
**Dal:** `faz-1-toplayicilar` · **45 commit** (main'den itibaren) · **349 test** (+18 contract)
· kapı **9 adım yeşil + `zincir` adıyla SKIP** · **push edilmedi, CI hiç koşmadı**

> Giriş sırası: `README.md` → bu dosya → `docs/DEFERRED.md`.
> Faz 1'in detaylı "ölçülmeyenler" listesi: `docs/phases/01-toplayicilar/HANDOFF.md` **§3**.
> Faz 0'ınki: `docs/phases/00-kayit-altyapisi/HANDOFF.md` §3.
> Arıza prosedürleri: `docs/RUNBOOK.md`.

---

## 1. Senin yapacağın şeyler

**1. Dalı push et.** `outward_action_gate` asistanın push'unu kapatıyor; push senin
terminalinden gelir.

```bash
git push -u origin faz-1-toplayicilar
```

**Merge `--no-ff` OLMALI.** `squash`/`rebase` gitleaks parmak izlerini geçersiz kılar
(Faz 0 Ruling 15) — ve bu dalda Task 8'in `--amend`'le geçmişten çıkardığı bir fixture var.

**2. Push'tan sonra CI'ı izle.** Faz 1'in dört yeni kapı adımı (`kaynak-politikası`,
`veri-sözleşmesi`, `dil-kalibrasyonu`, genişletilmiş `scripts/` kapsamı) ve iki yeni
workflow (`sources-audit.yml`, `full-scan.yml`) **bir runner'da hiç koşmadı.**

```bash
gh run list --repo popiliadam/football-edge --limit 10
```

Kırmızı gelirse ilk bakılacak yer runner'da `uv sync --frozen`: bu dal üç yeni bağımlılık
getirdi (`protego`, `beautifulsoup4`, `typesafe-sdk`).

**3. Faz 0'ın cron'larını da kontrol et.** `snapshot.yml` ve `seal.yml` Faz 0'dan beri
varsayılan dalda koşuyor olmalı; `ledger/` altına düzenli çıpa commit'i düşüyor mu bak.

**4. Bunu bil: ~2026-10-19'da kapı KENDİLİĞİNDEN kırmızı verecek.** `config/sources.yaml`
içindeki yedi kaynağın `robots_verified_at`i `2026-09-19` ve `kaynak-politikası` adımı
**30 günlük** tazelik istiyor. Bu tasarım, arıza değil: robots anlık görüntüleri yeniden
çekilir ve tarihler güncellenir. **Kapı gevşetilerek yeşil alınmaz.**

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
| Kapı | 9 adım PASS + `zincir` SKIP | `bce4aa8` ağacında, log dosyasından okundu |
| Odds API | **494/500 kredi** | Faz 1 bir kredi bile harcamadı |

`.env` (gitignored, izin 600): `ODDS_API_KEY`, `DATABASE_URL`. **`TYPESAFE_API_KEY` YOK.**
Repoda hiçbir yerde geçmiyor.

---

## 3. Faz 1 ne üretti

13 görev · 5 paralel worktree · **0 Critical** bulgu · **~45 Important**, hepsi kapatıldı ·
98 → **349 test** (+18 `contract` etiketli).

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
gitignored, yani merge etmez ve yalnız bu makinede durur.** 53 ruling'in Faz 2'yi bağlayan
22'si `docs/phases/01-toplayicilar/HANDOFF.md` **§4**'te; ertelenen 48 minor bulgu
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
   *"başarısız değil" ≠ "kalıcı olarak yazıldı."*
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

**Tam liste: `docs/phases/01-toplayicilar/HANDOFF.md` §3 — 22 madde, hepsi adıyla.**
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

---

## 6. Faz 2 — nereden başlanır

**Yol haritası:** `docs/superpowers/plans/2026-09-19-faz-1-7-yol-haritasi.md` (Faz 2 bölümü)
**Ön koşullar:** `docs/phases/01-toplayicilar/HANDOFF.md` §5
**Devralınan borç:** `docs/DEFERRED.md` (§9 Faz 1'indir)

Faz 2 = tarihsel taban · backtest harness · piyasa verimliliği · sızıntı denetimi.

**Faz 2'nin ilk işi Faz 1'in borcu olmalı:** beş `fetch-*` komutunu bir zamanlamaya bağlamak.
Backtest harness'ının besleneceği canlı özellik akışı bugün YOK, ve kaçırılan bir gözlem —
tıpkı kapanış oranı gibi — sonradan üretilemez.

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
