# football-edge — Oturum Devri (Handoff)

**Son güncelleme:** 2026-09-19 · **Durum:** **Faz 0 TAMAM ve main'e merge edildi**
**main:** `2978fca` · 40 commit · **98 test geçiyor** · kapı 7 adım yeşil

> Giriş sırası: `README.md` → bu dosya → `docs/DEFERRED.md`.
> Faz 0'ın detaylı "ölçülmeyenler" listesi: `docs/phases/00-kayit-altyapisi/HANDOFF.md` §3.
> Arıza prosedürleri: `docs/RUNBOOK.md`.

---

## 1. Senin yapman gereken TEK şey

```bash
cd ~/dev/football-edge && git push origin main && git push origin faz-0-kayit-altyapisi
```

`outward_action_gate` asistanın push etmesini engelliyor; **21 commit yerelde bekliyor.**

**Bu push üç workflow'u da ilk kez gerçekten test eder** — üçü de bugüne kadar hiç koşmadı:
`ci.yml` (push/PR'da kapı) · `snapshot.yml` (günde 1, 06:17 UTC) · `seal.yml` (15 dakikada bir).

GitHub `schedule`'ı **yalnız varsayılan dalda** onurlandırır. Yani `main` push edilene kadar
hiçbir cron çalışmaz ve **her gecikme günü geri gelmeyecek kapanış oranı demektir** — Faz 0'ın
var olma sebebiyle tam olarak aynı zarar.

Push sonrası ilk kontrol: Actions'ta üç workflow da yeşil mi, ve ilk `seal` turundan sonra
`ledger/` altına yeni bir çıpa commit'i düştü mü.

---

## 2. Canlı ve doğrulanmış durum

| Şey | Değer | Nasıl doğrulandı |
|---|---|---|
| Supabase | `football-edge` · `aaxadphezxavohkhqdrf` · eu-central-1 | ACTIVE_HEALTHY |
| Bağlantı | `aws-0-eu-central-1.pooler.supabase.com:5432` (**session** pooler) | canlı bağlanıldı, `TimeZone=UTC` |
| **Defter** | **3.717 satır · 51 maç · 25 bookmaker** | canlı snapshot, exit 0 |
| Zincir | **SAĞLAM**, baş `4768f367…` | `verify-chain`, 3717 satır tarandı |
| Çıpa | `ledger/head-2026-09-19.txt` (`rows=3717 last_id=3718`) | `publish-head` |
| **Append-only** | UPDATE ve DELETE **reddedildi** | 2 test, gerçek Postgres, 3717 satır üstünde |
| Kapı | 7 adım, hepsi PASS | `DATABASE_URL` bağlı koşuldu, merge sonrası tekrar |
| Secret taraması | kırmızı-sonra-yeşil **kanıtlı** | sahte secret → exit 1, kaldırıldı → exit 0 |
| Odds API | **494/500 kredi** | lig başına tam 1 harcandı |
| GitHub | `popiliadam/football-edge` (public) | secrets ayarlı |

`.env` (gitignored, izin 600): `ODDS_API_KEY`, `DATABASE_URL`. Repoda hiçbir yerde geçmiyor.

---

## 3. Faz 0 ne üretti

8 görev · 4 düzeltme turu · **6 Critical + ~20 Important bulgu, hepsi kapatıldı** · 1 → 98 test.

Her görev ayrı bir inceleme ajanından geçti; her düzeltme turu kendi re-review'ünü aldı; final
whole-branch inceleme (Opus) **YES WITH CONDITIONS** verdi ve altı koşulun altısı da karşılandı.

**Öğretici olan:** ilk üç düzeltme turunun her biri, bir öncekinin düzeltmesinde yeni bir kusur
buldu — üçü de aynı kavram karmaşasının farklı derinlikleri: *"başarısız değil" ≠ "kalıcı olarak
yazıldı"*. Doğru ölçüt en baştan şuydu: **bu maç için bir satır commit'lendi mi.**

---

## 4. Verilen kararlar (Ruling listesi)

Tam gerekçeler `.superpowers/sdd/2026-09-19-faz0-kayit-altyapisi/progress.md` içinde — **o dizin
gitignored, yani merge etmez ve yalnız bu makinede durur.** Kalıcı olması gerekenler
`docs/DEFERRED.md` ve `docs/RUNBOOK.md`'ye taşındı.

1. **Supabase pooler, doğrudan bağlantı değil** — doğrudan host yalnız IPv6, Actions IPv4. *Ölçüldü.*
2. **Push anomalisi anomali değildi** — kullanıcı kendi attı, öncesinde onay vermişti.
3. **Public repo + canlı anahtar → kapıya secret taraması**, ve kırmızı verdiği kanıtlandı.
4. **Plan kod blokları format-temiz değil** → `ruff format` beklenen adım, sapma değil.
5. **Kurulu-paket import kontrolü kapıya** — testler `pythonpath=["src"]`, CI kurulu paketi çağırıyor.
6. **Lig döngüsüne arıza izolasyonu + exit 3** — bozuk yanıt tüm turu düşürüyordu.
7. **`git add -A` yasak** (implementer koşarken) — bir kez yaptım, commit sınırını bozdum, ayırdım.
8. **Kuyruktan silme kodda değil mimaride kapatıldı** — trigger + dış çıpa + çıpa karşılaştırması.
9. **Kanonik zaman damgası load-bearing** — iki taraf tek fonksiyonu paylaşır, yoksa her satır "KIRIK".
10. **Migrasyonu controller uyguladı** — subagent'ın MCP erişimi belirsizdi.
11. **Mühür maç bazında, lig bazında değil** — ve liste **commit'ten sonra** birikir.
12. **Çıpa hash'i yeniden hesaplanır** — saklı sütuna güvenmek, herkese açık bir değeri kopyalamaya açıktı.
13. **Kilitlenmeye bypass bayrağı YOK** — kapalı-arızalanmak doğru; kurtarma yazılı prosedürle.
14. **Ayna arızasında erken çıkış** — kredi yakmamak için; bedeli o turun mührü, yazılı.
15. **Merge `--no-ff`** — squash/rebase gitleaks parmak izlerini geçersiz kılar.

---

## 5. Kapının ÖLÇMEDİĞİ şeyler

Tam liste: `docs/phases/00-kayit-altyapisi/HANDOFF.md` §3. Başlıcaları:

1. **Hiçbir workflow hiç koşmadı.** Push edilmedi; `schedule` yalnız varsayılan dalda çalışır.
2. **Defterin İÇİ bir daha hash'lenmiyor.** Çıpa sonrası yalnız kuyruk taranıyor; 2..3718 arası
   satırlar hiçbir zamanlanmış koşuda yeniden doğrulanmayacak. `--full` seçeneği yok.
3. **Tetikleyici, ürünün adını koyduğu aktöre karşı savunma değil.** Toplayıcı tablo **sahibi**
   olarak bağlanıyor; o rol `DISABLE TRIGGER` ve `TRUNCATE` yapabilir. En az yetkili rol yok.
4. **Çıpa silmek, bozmaktan daha sessiz** — ve meşru arşivleme prosedüründen ayırt edilemiyor.
5. **Eşzamanlı yazar güvenliği** yalnız sahte bağlantıyla, ifade sırası üzerinden kanıtlandı;
   iki gerçek Postgres oturumu hiç ölçülmedi.
6. **Ertelenen maçlar** kapanış oranını kaybeder ve 24 saat sonra rapordan düşer.
7. **`matches` tablosuna hiç girmemiş maç**, kaçan-mühür raporunda görünmez.
8. **Yazma yolu yavaş**: satır başına bir INSERT, ~3700 gidiş-dönüş, tur ~4 dakika.
9. **Jev hiç kullanılmadı** (Faz 4) ve **çok dilli doğruluğu ölçülmedi** (Faz 1'in şartı).

---

## 6. Faz 1 — nereden başlanır

**Yol haritası:** `docs/superpowers/plans/2026-09-19-faz-1-7-yol-haritasi.md` (Faz 1 bölümü)
**Devralınan borç:** `docs/DEFERRED.md`

Faz 1 = toplayıcılar + varlık eşleme + **dil kalibrasyonu**. Task 2–8 (Understat, FootyStats,
FBref, ClubElo, Google News çok dilli, TFF, Open-Meteo/Wikidata) birbirinden **bağımsız** →
**izole git worktree'lerde paralel** koşturulmalı. Ortak çalışma ağacında paralel implementer
çalıştırma: bu oturumda bedeli görüldü.

**Faz 1'in ilk işi Faz 0'ın borcu olmalı:** batch insert (yazma yolu) ve zincir iç taraması
(`--full`). İkisi de Faz 1'in getireceği hacimde acil hâle gelir.

Faz 1 henüz **tam TDD planı almadı** — fresh session'ın ilk işi o planı yazmak olabilir
(Faz 0'ın planı `docs/superpowers/plans/2026-09-19-faz0-kayit-altyapisi.md` örnek alınabilir).

---

## 7. Çalışma disiplini (bu projede öğrenilenler)

- Kapı çıktısı **dosyadan** okunur. `SKIP` geçmek değildir, adıyla raporlanır.
- Implementer koşarken **`git add -A` yok** — yalnız açık yollar.
- Append-only tabloya test satırı yazma: silinemez. Sondayı **transaction içinde** koş, geri al.
- Her görev: implementer → rapor → inceleme paketi → inceleme ajanı → defter. Atlanmaz.
- Bir test, konusunu **yeniden yazıyorsa** yalnız aynı kodu iki kez yazabildiğinizi kanıtlar.
- Bir düzeltme komşu bir varsayımı geçersiz kılabilir — her turda "bu tur neyi bozdu" sorulur.
- Model: varsayılan **opus**, çok karmaşık işlerde **fable**, **haiku asla**.
