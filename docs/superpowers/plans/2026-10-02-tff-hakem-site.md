# TFF Baş Hakemi Maç Sayfasında — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Süper Lig (`tur.1`) maç sayfası, TFF'nin "Haftanın Maçları" sayfasında (`pageID=600`) maç başlamadan ÖNCE
açıklanmış baş hakemi "Hakem: X (TFF ataması)" / "Referee: X (TFF appointment)" satırıyla gösterir; atanmamış,
eşlenemeyen ya da yalnız başlamadan sonra görülmüş atamada satır HİÇ basılmaz; hiçbir kayıp sessiz değildir.

**Architecture:** Toplayıcı (`collectors/tff.py`) her TFF satırından İstanbul tarihini ve saatini okur, gözlemi
tarihli anahtarla yazar ve AYNI turun ayrıştırılmış sonucunu yeni `officials.link_officials`e verir. Bağlayıcı
`config/tff_teams.yaml` ile TFF adını The Odds API adına çevirir, `matches`te `tur.1` + ev + deplasman + İstanbul
takvim günüyle TEK maçı bulur ve hakem değiştiyse append-only `public.match_officials`e satır ekler. 0015'in
`site.match_officials` görünümü maç başına başlamadan önce görülen SON atamayı `site.matches` tabanıyla süzer;
dışa aktarım onu aynı REPEATABLE READ işleminde okur, anlık görüntünün her maçına zorunlu `referee` (metin|null)
girer, Next sayfası onu tek bir `RefereeLine` bileşeniyle basar.

**Tech Stack:** Python 3.11 (uv, pytest, mypy `--strict`, ruff 100 sütun), psycopg 3, PyYAML, BeautifulSoup 4,
`zoneinfo` (`Europe/Istanbul`); Postgres 17 (Supabase imajı `public.ecr.aws/supabase/postgres:17.6.1.143`, yalnız
`sitedb` kum havuzunda); Node 24.21.0, pnpm, Next.js 16 (statik dışa aktarım), React 19, TypeScript 5.9, Vitest 4,
Biome 2.

**Spec:** docs/superpowers/specs/2026-10-02-tff-hakem-site-design.md

## Global Constraints

Spec'ten (değerler aynen; her görevin gereksinimine örtük olarak dahildir):

- Kapsam: yalnız Süper Lig (`tur.1`) baş hakemi; yardımcı/dördüncü/VAR/AVAR, alt ligler, geriye dönük doldurma, modelde hakem özelliği ve JSON-LD'de hakem YOK (§1).
- Başarı: "atanmış ve eşlenmiş her `tur.1` maçında sayfa, `commence_time`dan ÖNCE görülen SON atamayı gösterir" (§1).
- "maç başladıktan sonra görülen atama, eşlenemeyen maç ve atanmamış maç için sayfada hakem satırı YOKTUR (yer tutucu, "yakında", tahmin yok)" (§1).
- "hiçbir sessiz kayıp yok: ayrıştırılamayan satır ve yapılandırmada olmayan takım adı kırmızıdır" (§1).
- Yük: `match_date` (ISO `YYYY-MM-DD`) ve `kickoff_local` (`HH:MM`, İstanbul); anahtar `ev|deplasman|YYYY-MM-DD`; eski anahtarlı satırlara dokunulmaz (§3.1).
- "tarih/saati okunamayan satır "sessizce atlandı" sayılır → `ContractViolation`" (§3.2).
- `collect_tff` gözlemleri yazdıktan sonra AYNI `now` ile `link_officials` çağırır; bağlama gözlem tablosundan OKUMAZ (§3.3).
- Lig süzgeci: `config/tff_teams.yaml` `league_label_contains: "Süper Lig"`; hedef lig `league_id: tur.1`; diğer bloklar sayılır, işlenmez (§4).
- Ad eşlemesi: YAML `teams:` anahtarı `normalise_team(TFF adı)`, değer API adı ya da `null`; YAML'da HİÇ olmayan TFF adı → `ContractViolation`; değeri `null` olan takım içeren maç → `awaiting_alias` sayacı (loglanır, hata değil) (§4 + plan düzeltmesi).
- Maç bulma: `matches.league_id='tur.1'`, `home_team`, `away_team` eşit ve `commence_time`ın **Europe/Istanbul takvim günü** = `match_date`; tek eşleşme → bağlanır; sıfır → "DB'de yok" sayacı; birden çok → `ContractViolation` (§4).
- Değişiklik kaydı: maçın SON kayıtlı hakemi bu turunkinden farklıysa (ya da hiç yoksa) `(match_id, referee, seen_at=now)` eklenir; aynıysa yazılmaz; X→Y→X üç satır (§4).
- Dönüş sayıları: `(bağlanan, yeni yazılan, DB'de yok, alias bekleyen, lig dışı)`; `collect-daily` logu basar (§4).
- Migration `db/migrations/0015_match_officials.sql`; **0014'e DOKUNULMAZ**; tablo ve görünüm DDL'i spec §5'teki metinle aynı; append-only (`forbid_ledger_mutation`), RLS açık + politikasız + FORCE yok, API rollerinden revoke (0013 kalıbı); görünüm `with (security_barrier)`, `grant select … to site_reader` (§5).
- H1a: yeni temel tablo yalnız `public.match_officials`; taban `site.matches` join'inden gelir (§5).
- Anlık görüntü: her maç öğesinde ZORUNLU `referee`, değer null ya da 1–80 karakter metin; `schema_version` 1 kalır (§6).
- Sözlük anahtarı `match.referee`: en "Referee: {name} (TFF appointment)", tr "Hakem: {name} (TFF ataması)"; null ise satır hiç basılmaz; `numbers.ts` `pageNames.match` hakem adını içerir (§6).
- Sıra: 0014 → 0015; `site_reader`a LOGIN veren migration **0016** olur (§5).
- Yayın: yerelde serbest; ilk yayından önce avukat (K/7/6, KVKK) (§8).

Proje süreci (HANDOFF/bellek; her görevde):

- **TAM KAPI** (her görevin SON adımı; sonuç LOG DOSYASINDAN okunur, özet değil):
  ```bash
  export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh > "$T/verify.log" 2>&1; grep -E "^(PASS|FAIL|SKIP)|KAPI" "$T/verify.log"
  ```
  Beklenen: hiç `FAIL:` yok; adıyla üç SKIP — `SKIP: site-db (SITE_TEST_DATABASE_URL yok)`, `SKIP: site-derleme/e2e (…)`,
  `SKIP: zincir (DATABASE_URL yok)`; son satır `KAPI YEŞİL`. Kırmızıysa `$T/verify.log`un ilgili `=== adım ===` bölümü
  okunur, kapı gevşetilmez, düzeltme yeni commit'tir.
- Python: `PYTHONDONTWRITEBYTECODE=1 uv run pytest …`, `uv run mypy src scripts`, `uv run ruff check src tests scripts`,
  `uv run ruff format src tests scripts` (commit'ten önce biçim).
- Web: `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; pnpm -C web exec vitest run <web'e göreli dosya>`;
  commit'ten önce değişen web dosyalarına `pnpm -C web exec biome check --write <web'e göreli dosyalar>`.
- **`sitedb` testleri** (`tests/test_site_*_db.py`) atılabilir yerel Postgres kabı ister (`tests/site_db.py`,
  `docs/RUNBOOK.md` §4). Değişken yoksa yerelde adıyla SKIP, `CI=true` iken FAIL (CI'da koşarlar). Yerelde koşturmak
  (Docker gerekir; ilk `up` ~1,7 GB imaj indirir — **controller onayıyla**; bu oturumun kendi önek ve portu):
  ```bash
  export FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620
  FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh up
  FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_views_db.py tests/test_site_officials_db.py tests/test_site_e2e_db.py
  ```
  `test` alt komutu `SITE_TEST_DATABASE_URL`i bu betiğin BOŞ kabına çevirir, `--tb=short` ve `PYTHONDONTWRITEBYTECODE=1`
  ile koşar; canlıya bağlanmaz, `.env` okumaz. Docker yoksa DB adımları ve DB mutasyon kanıtları adıyla "yerelde
  koşmadı (Docker yok)" diye rapora yazılır — atlanan kontrol geçmek değildir.
- **MUTASYON KALIBI** (her "Mutasyon kanıtı" adımı bu dört satırı koşar; F/OLD/NEW/test komutu adımda yazılıdır):
  yedekle → OLD'u (dosyada TAM BİR KEZ geçmeli) NEW'le değiştir → testi koş (beklenen `exit=1`, adı geçen test kırmızı) →
  yedeği geri koy → `cmp` sessizse geri konmuştur. `rm`, `git checkout -- <yol>`, `git restore` KULLANILMAZ.
- Immutability: paylaşılan/girdi objesi mutate edilmez (yerel liste/dict doldurmak serbest). Fonksiyonlar < 50 satır.
- `git add` dosya ADIYLA (`-A`/`.` yok). Commit: `<type>: <açıklama>` (type ∈ feat, fix, refactor, docs, test, chore, perf, ci),
  boş satır, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Push/merge, canlı DB'ye migration uygulama, Netlify, secret: bu planın işi DEĞİL (controller / HANDOFF Adım 12).
- Kapının secrets adımı testleri de tarar: test içinde `AD=değer` biçimli secret adı parçalardan kurulur
  (`"DATABASE" + "_URL"`).
- Güvenlik sınırı (yeni tablo + görünüm + yetki, spec §9/8): Görev 3 ve Görev 5'in incelemesi kabuk taşıyan
  (`general-purpose`) bağımsız bir inceleyiciye verilir — mutasyon koşturabilmeli (bellek: reviewer-needs-shell).

## Review Focus

Spec'in ima ettiği ama görev testlerinin kendiliğinden kapsamayacağı, kullanıcıyı en olası ısıracak beş girdi; her
birinin testi sahibi görevin adımındadır:

1. **Adında "Süper Lig" geçen başka bir TFF bloğu** (ör. "Turkcell Kadın Futbol Süper Ligi"): alt dize süzgecinden
   geçer, takım adları YAML'da yoktur → `ContractViolation` mesajı lig ETİKETİNİ ve TFF adını taşımalı ki düzeltme
   (YAML'a satır mı, süzgeç mi) ilk bakışta görülsün; sessiz bağlama yok (Görev 4, `test_review_focus_an_unknown_team_in_another_super_lig_block_is_red_with_its_label`).
2. **Aynı maç turda iki kez** (sayfa iki blokta ya da yinelenen satır): aynı hakemle tek bağlantı; farklı hakemle
   `ContractViolation` — hangi atamanın gerçek olduğu tahmin edilmez (Görev 4, iki `test_review_focus_the_same_match_*`).
3. **Yayımlanamayan hakem metni** (> 80 karakter, `<`, `>`, `http`): DB'nin `check`i ya da `verify-snapshot`in H2c'si
   ona ilk kez dışa aktarımda takılırsa BÜTÜN site dışa aktarımı durur; bağlayıcı bunu yazmadan önce adıyla kırmızı
   yapar (Görev 4, `test_review_focus_an_unpublishable_referee_text_is_red_before_the_db`).
4. **Ev/deplasman TFF ile API arasında ters**: tahminle bağlanmaz (yanlış hakemden kötü), "DB'de yok" sayılır, ama her
   hafta sessizce kaybolmasın diye adlarıyla UYARI loglanır (Görev 4, `test_review_focus_reversed_home_and_away_is_not_linked_but_warned`).
5. **`referee` anahtarı olmayan bayat anlık görüntü** (eski dışa aktarım, yeniden üretilmemiş fixture): sayfa hakem
   satırını sessizce düşürürdü; `parseSnapshot` adıyla reddeder (Görev 6, `snapshot.test.ts` "hakem anahtarı yok").

**Kapının ölçmedikleri (bu plan; Görev 7 faz HANDOFF'una yazar):** (a) YAML'daki API adlarının `tur.1`de gerçekten
görüldüğü (`test_every_mapped_api_name_was_seen_in_tur1`) yalnız veritabanı adresiyle koşar — kapıda ve CI'da adıyla
SKIP; (b) TFF tarih hücresinin şekli 2026-09-19 fixture'ından ölçüldü — TFF'nin YANLIŞ tarih basması ölçülmez;
(c) `league_label_contains` alt dizedir: başka bir "Süper Lig" bloğunda YAML'da OLAN bir adla (ör. kadın takımı
"GALATASARAY A.Ş.") aynı gün aynı rakiple oynanan maç yanlış maça bağlanabilir; (d) ters ev/deplasman yalnız uyarıdır,
`collect-daily` kırmızı olmaz; (e) check-out derlenmiş sayfada hakem satırının VARLIĞINI/YOKLUĞUNU ölçmez (bileşen
birim testi + ad listesi ölçer; satır `data-fe` taşımaz); (f) `verify-snapshot` hakemin yalnız `tur.1` maçında
durduğunu sınamaz (tek yazar `link_officials` yalnız `tur.1`e yazar); (g) canlıya uygulama ve advisors (HANDOFF Adım 12);
(h) DB mutasyon kanıtları yalnız yerel kum havuzunda (Docker) koşar, CI yalnız yeşili ölçer; (i) `seen_at` toplama
turunun `now`udur, TFF'nin atamayı yayımladığı an değil — tur maçtan sonra koşarsa atama görünmez (muhafazakâr yön);
(j) hakem adı TFF'nin büyük harfli yazımıyla basılır, yazım düzeltmesi yok.

---

## Controller düzeltmesi C1 (2026-10-02, plan incelemesi) — lig süzgeci daraltıldı

Taslaktaki `league_label_contains in label` alt dize karşılaştırması "Kadın Futbol Süper **Ligi**" bloğunu da
işlerdi (kadın takımı "GALATASARAY A.Ş." YAML'da OLAN bir adla aynı gün aynı rakiple oynarsa yanlış maça bağlanırdı).
Bu plan boyunca süzgeç `TeamMap.matches_league(label)`tir (yukarıdaki kod bloklarında uygulandı):
- ifade TAM eşleşir: `re.escape("süper lig") + r"(?!\w)"`, `casefold` üzerinde — "Süper Ligi" eşleşmez;
- `officials.py` modül sabiti `_EXCLUDED_LEAGUE_WORDS = ("kadın", "kadin", "u19", "u21", "gelişim", "gelisim")`
  içeren etiket işlenmez; `officials.py` başında `import re` gerekir.
- **Görev 1'e test eklenir** (`tests/test_officials.py`, `load_team_map(TEAMS_YAML)` ile):
  ```python
  @pytest.mark.parametrize(
      ("label", "expected"),
      [
          ("Trendyol Süper Lig Adnan Süvari Sezonu", True),
          ("Kadın Futbol Süper Ligi", False),
          ("KADIN FUTBOL SÜPER LİGİ", False),
          ("Süper Lig U19 Gelişim Ligi", False),
          ("Trendyol 1. Lig", False),
      ],
  )
  def test_only_the_mens_top_league_block_is_processed(label: str, expected: bool) -> None:
      assert load_team_map(TEAMS_YAML).matches_league(label) is expected
  ```
  Mutasyon: `(?!\w)` kaldırılırsa "Kadın Futbol Süper Ligi" satırı dışlama listesi yüzünden yine False kalır —
  bu yüzden İKİ ayrı mutasyon koşulur: (a) `_EXCLUDED_LEAGUE_WORDS = ()` → "Kadın…" satırları kırmızı;
  (b) hem dışlama boş hem `(?!\w)` yok → "Süper Lig U19…" dışında da kırmızı; (c) `(?!\w)` yok ve dışlama
  dolu → yeni bir parametre `("Süper Ligi Play-off", False)` kırmızı — bu parametreyi de listeye ekle.
- Görev 7'de DEFERRED 9.7b metni "alt dize" değil "C1 ile daraltıldı (tam ifade + kadın/genç dışlama); kalan risk:
  TFF dışlama sözcüğü taşımayan yeni bir 'Süper Lig' bloğu açarsa" olarak yazılır; Review Focus (c) aynı anlamda.

## Dosya yapısı

| Dosya | Durum | Sorumluluk |
|---|---|---|
| `docs/superpowers/specs/2026-10-02-tff-hakem-site-design.md` | Değişir (G1) | §4 `awaiting_alias` + dönüş sayıları; §6 `oneOf` → `type` listesi; §9/2 gün örneği |
| `config/tff_teams.yaml` | Yeni (G1) | TFF adı (normalise) → API adı | null; lig etiketi ve hedef lig |
| `src/football_edge/officials.py` | Yeni (G1), büyür (G4) | YAML yükleyici; saf eşleme (`plan_links`); DB okuma/yazma (`find_candidates`, `link_officials`) |
| `tests/test_officials.py` | Yeni (G1), büyür (G4) | YAML biçimi, fixture kapsamı, canlı ad testi (SKIP'li); eşleme birim testleri |
| `src/football_edge/collectors/tff.py` | Değişir (G2, G4) | Tarih/saat ayrıştırma, tarihli anahtar; `collect_tff` → `link_officials` |
| `tests/test_tff.py` | Değişir (G2, G4) | Tarih/saat ve kayıp testleri; toplama → bağlama testleri |
| `verify.sh` | Değişir (G2, G3, G4) | `EXPECTED_MIN_CONTRACT` 25→27; `EXPECTED_MIN_SITEDB` 28→37→40; `EXPECTED_MIN_SITEDB_LEAKAGE` 4→5 |
| `db/migrations/0015_match_officials.sql` | Yeni (G3) | Tablo, append-only, RLS, revoke, `site.match_officials`, grant |
| `tests/site_db.py` | Değişir (G3) | `TEMPLATE_MIGRATIONS`a 0015; belge satırları |
| `tests/test_site_officials_migration_text.py` | Yeni (G3) | 0015 metin testleri (DB'siz, her kapıda) |
| `tests/test_site_views_db.py` | Değişir (G3) | Kapanış/sahiplik/tip sabitleri; görünüm davranışı; append-only; idempotentlik |
| `docs/RUNBOOK.md` | Değişir (G3) | Şablon migration listesi |
| `tests/test_site_officials_db.py` | Yeni (G4) | `link_officials` gerçek Postgres'te: değişiklik kaydı, İstanbul günü aralığı |
| `scripts/sandbox_db.sh` | Değişir (G4) | `DEFAULT_TESTS`e yeni DB test dosyası |
| `src/football_edge/site/inputs.py` | Değişir (G5) | `MatchRow.referee`; döküm satırı 6 kolon |
| `src/football_edge/site/export.py` | Değişir (G5) | `site.match_officials` aynı işlemde okunur |
| `src/football_edge/site/derive.py` | Değişir (G5) | Maç nesnesine `referee` |
| `web/contract/snapshot.schema.json` | Değişir (G5) | Zorunlu `referee`, `$defs.person` |
| `web/src/lib/snapshot-types.ts` | Değişir (G5) | `Match.referee: string \| null` |
| `tests/site_web_fixtures.py` + `web/fixtures/snapshot.fixture.web-{full,empty}.json` | Değişir (G5) | Üretici + yeniden üretilmiş fixture'lar |
| `web/fixtures/snapshot.fixture.json`, `snapshot.fixture-record.json` | Değişir (G5) | B-1 fixture'larına `referee` + yeni hash |
| `tests/fake_site_db.py`, `tests/site_builders.py` | Değişir (G5) | Taklit görünüm ve döküm kurucusu |
| `tests/test_site_{derive,export,verify,contract,e2e_db}.py` | Değişir (G5) | Hakemli/hakemsiz türetim, dışa aktarım, şema kuralları, uçtan uca |
| `web/src/components/RefereeLine.tsx` (+ `.test.tsx`) | Yeni (G6) | Tek satır; null iken hiçbir şey |
| `web/src/app/[lang]/[league]/match/[pathId]/[slug]/page.tsx` | Değişir (G6) | Satırı başlama anının altına koyar |
| `web/src/i18n/{en,tr}.json`, `dict.test.ts` | Değişir (G6) | `match.referee` |
| `web/scripts/checkout/numbers.ts` (+ `referee.test.ts`) | Değişir/Yeni (G6) | Ad listesine hakem |
| `web/src/lib/snapshot.ts`, `snapshot.test.ts` | Değişir (G6) | `referee` biçim bekçisi |
| `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md` | Değişir (G7) | §1 kapsam dışı, B7, H1a, H2b, §7 içerik |
| `docs/DEFERRED.md`, `docs/HANDOFF.md`, `docs/phases/06-site/HANDOFF.md` | Değişir (G7) | I-5 notu, alias/etiket maddeleri, Adım 12/14, ölçülmeyenler, avukat satırı |

Görev sırası ve bağımlılık: G1 → G2 → G3 → G4 (G1+G2'nin yükünü ve G3'ün tablosunu tüketir) → G5 (G3'ün görünümünü
tüketir) → G6 (G5'in tipini tüketir) → G7. Önerilen sıradan sapma yok; tek ekleme: spec düzeltmeleri G1'de toplandı
(§4'e ek olarak §6 ve §9/2 — gerekçe ilgili adımda), çünkü sonraki her görev spec'i tek kaynak olarak okur.

---

### Task 1: Spec düzeltmesi, `config/tff_teams.yaml` ve yükleyicisi

**Files:**
- Modify: `docs/superpowers/specs/2026-10-02-tff-hakem-site-design.md:40-48` (§4), `:77-78` (§6), `:98-99` (§9/2)
- Create: `config/tff_teams.yaml`
- Create: `src/football_edge/officials.py`
- Test (Create): `tests/test_officials.py`

**Interfaces:**
- Consumes: `football_edge.naming.normalise_team(name: str) -> str`;
  `football_edge.collectors.tff.parse_referees(html_text: str, *, observed_at: datetime) -> tuple[Observation, ...]`;
  `football_edge.db.connect(dsn: str | None = None) -> psycopg.Connection[Any]`.
- Produces: `football_edge.officials.TFF_TEAMS_PATH: Path` (= `Path("config/tff_teams.yaml")`);
  `@dataclass(frozen=True) class TeamMap(league_label_contains: str, league_id: str, teams: Mapping[str, str | None])`;
  `load_team_map(path: Path = TFF_TEAMS_PATH) -> TeamMap` (biçim dışı → `ValueError`).

- [ ] **Step 1: Spec'i düzelt (üç yer)**

Gerekçe: (i) kullanıcı kararı — `null` değerli takım `awaiting_alias`; (ii) depodaki şema doğrulayıcısı
(`src/football_edge/site/schema.py` `SUPPORTED`) `oneOf` desteklemez, bilinmeyen anahtar kelime `SchemaError`dır —
aynı anlam `type: ["string", "null"]` ile kurulur (B-1'in `round`u `["object", "null"]` aynı deseni kullanır);
(iii) İstanbul UTC+3'tür: 23:30 İstanbul UTC'de gece yarısını GEÇMEZ (20:30 UTC); ayrışma 00:00–02:59 İstanbul
başlamalarındadır.

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
from pathlib import Path

path = Path("docs/superpowers/specs/2026-10-02-tff-hakem-site-design.md")
text = path.read_text(encoding="utf-8")
edits = [
    (
        "  (yapılandırma eksiği; sessiz geçmez; düzeltme: YAML'a satır).\n",
        "  (yapılandırma eksiği; sessiz geçmez; düzeltme: YAML'a satır).\n"
        "- **Henüz görülmemiş API yazımı (plan düzeltmesi, 2026-10-02):** YAML'da değeri `null` olan takım (API yazımı\n"
        "  canlı `matches`te henüz hiç görülmedi — uydurulmaz; bugün `kasimpaşa`, `tümosan konyaspor`) içeren maç ayrı\n"
        "  `awaiting_alias` sayacına girer (loglanır, hata değil). YAML'da HİÇ olmayan TFF adı `ContractViolation` kalır.\n",
    ),
    (
        "- Dönüş: `(bağlanan, yeni yazılan, DB'de yok, lig dışı)` sayıları;",
        "- Dönüş: `(bağlanan, yeni yazılan, DB'de yok, alias bekleyen, lig dışı)` sayıları;",
    ),
    (
        '`{"oneOf": [{"$ref": "#/$defs/person"},\n  {"type": "null"}]}`; `$defs.person` = 1–80 karakter metin.',
        '`{"$ref": "#/$defs/person"}`; `$defs.person` =\n'
        '  `{"type": ["string", "null"], "minLength": 1, "maxLength": 80}` (plan düzeltmesi: depodaki doğrulayıcı\n'
        "  `football_edge.site.schema` `oneOf` desteklemez; anlam aynı: null ya da 1–80 karakter metin).",
    ),
    (
        "(UTC'de\n   gece yarısını geçen 23:30 İstanbul maçı doğru güne düşer)",
        "(İstanbul\n   UTC+3: 01:00 İstanbul maçı = önceki UTC günü 22:00 → İstanbul gününe; 23:30 İstanbul maçı = aynı UTC günü\n"
        "   20:30 → kendi gününe; plan düzeltmesi 2026-10-02)",
    ),
]
for old, new in edits:
    assert text.count(old) == 1, old
    text = text.replace(old, new)
path.write_text(text, encoding="utf-8")
PY
git diff --stat -- docs/superpowers/specs/2026-10-02-tff-hakem-site-design.md
```
Expected: `1 file changed`; betik `AssertionError` vermez.

- [ ] **Step 2: YAML anahtarlarını hesaplat (uydurma ad yok)**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
from football_edge.naming import normalise_team

for name in (
    "AMED SPORTİF FAALİYETLER", "ARCA ÇORUM FK", "BEŞİKTAŞ A.Ş.", "ÇAYKUR RİZESPOR A.Ş.",
    "CORENDON ALANYASPOR", "ERZURUMSPOR FK", "EYÜPSPOR", "FENERBAHÇE A.Ş.", "GALATASARAY A.Ş.",
    "GAZİANTEP FUTBOL KULÜBÜ A.Ş.", "GENÇLERBİRLİĞİ", "GÖZTEPE A.Ş.", "İSTANBUL BAŞAKŞEHİR FK",
    "KOCAELİSPOR", "SAMSUNSPOR A.Ş.", "TRABZONSPOR A.Ş.", "KASIMPAŞA A.Ş.", "TÜMOSAN KONYASPOR",
):
    print(f"{normalise_team(name)!r:32} <- {name}")
PY
```
Expected (plan yazımında ölçüldü, 2026-10-02): `'amed sportif faaliyetler'`, `'arca çorum'`, `'beşiktaş'`,
`'çaykur rizespor'`, `'corendon alanyaspor'`, `'erzurumspor'`, `'eyüpspor'`, `'fenerbahçe'`, `'galatasaray'`,
`'gaziantep kulübü'`, `'gençlerbirliği'`, `'göztepe'`, `'istanbul başakşehir'`, `'kocaelispor'`, `'samsunspor'`,
`'trabzonspor'`, `'kasimpaşa'`, `'tümosan konyaspor'`. Çıktı farklıysa YAML anahtarları ÇIKTIDAN yazılır.

- [ ] **Step 3: Başarısız testleri yaz — `tests/test_officials.py`**

```python
"""TFF baş hakemi eşlemesi (spec 2026-10-02 §4): takım adı yapılandırması.

Canlı ad doğrulaması (`test_every_mapped_api_name_was_seen_in_tur1`) yalnız veritabanı adresi varken
koşar ve YALNIZ OKUR (işlem geri alınır); kapıda ve CI'da adıyla SKIP'tir.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from football_edge.collectors.tff import parse_referees
from football_edge.db import connect
from football_edge.naming import normalise_team
from football_edge.officials import load_team_map

REPO = Path(__file__).resolve().parent.parent
TEAMS_YAML = REPO / "config/tff_teams.yaml"
TFF_FIXTURE = REPO / "tests/fixtures/tff/haftanin-maclari-600.html"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
LIVE_VAR = "DATABASE" + "_URL"
needs_live = pytest.mark.skipif(
    not os.getenv(LIVE_VAR), reason=f"SKIP: canlı ad doğrulaması ({LIVE_VAR} yok)"
)


def test_the_committed_team_map_targets_tur1_with_eighteen_teams() -> None:
    team_map = load_team_map(TEAMS_YAML)

    assert (team_map.league_label_contains, team_map.league_id) == ("Süper Lig", "tur.1")
    assert len(team_map.teams) == 18


def test_every_key_is_its_own_normalise_team_output_and_values_are_null_or_text() -> None:
    raw = yaml.safe_load(TEAMS_YAML.read_text(encoding="utf-8"))

    assert [key for key in raw["teams"] if normalise_team(key) != key] == []
    assert all(
        value is None or (isinstance(value, str) and value.strip())
        for value in raw["teams"].values()
    )


def test_every_super_lig_name_in_the_tff_fixture_has_an_entry() -> None:
    """Ölçülen sayfanın (2026-09-19) 9 Süper Lig maçındaki 18 TFF adı YAML'da anahtar olarak var."""
    team_map = load_team_map(TEAMS_YAML)
    parsed = parse_referees(TFF_FIXTURE.read_text(encoding="utf-8"), observed_at=NOW)
    names = {
        normalise_team(entry.payload[side])
        for entry in parsed
        if team_map.matches_league(entry.payload["league"])
        for side in ("home_team", "away_team")
    }

    assert len(names) == 18
    assert names <= set(team_map.teams), sorted(names - set(team_map.teams))


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("league_id: tur.1\nteams: {galatasaray: Galatasaray}\n", "üst anahtarlar"),
        (
            'league_label_contains: ""\nleague_id: tur.1\nteams: {galatasaray: Galatasaray}\n',
            "boş olmayan metin olmalı",
        ),
        ('league_label_contains: "Süper Lig"\nleague_id: tur.1\nteams: {}\n', "teams boş olmayan"),
        (
            'league_label_contains: "Süper Lig"\nleague_id: tur.1\n'
            'teams: {"GALATASARAY A.Ş.": Galatasaray}\n',
            "normalise_team çıktısı değil",
        ),
        (
            'league_label_contains: "Süper Lig"\nleague_id: tur.1\nteams: {galatasaray: ""}\n',
            "null ya da boş olmayan metin",
        ),
    ],
)
def test_a_malformed_team_map_is_refused_by_name(tmp_path: Path, text: str, needle: str) -> None:
    path = tmp_path / "tff_teams.yaml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match=needle):
        load_team_map(path)


@needs_live
def test_every_mapped_api_name_was_seen_in_tur1() -> None:
    """Spec §4: her API adı `tur.1`de GERÇEKTEN görülmüş olmalı. Yalnız okur; işlem geri alınır."""
    team_map = load_team_map(TEAMS_YAML)
    names = sorted({name for name in team_map.teams.values() if name is not None})
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                "SELECT DISTINCT side.name FROM matches m "
                "CROSS JOIN LATERAL (VALUES (m.home_team), (m.away_team)) AS side(name) "
                "WHERE m.league_id = %s AND side.name = ANY(%s)",
                (team_map.league_id, names),
            )
            seen = {str(row[0]) for row in cur.fetchall()}
    finally:
        conn.rollback()
        conn.close()

    assert sorted(set(names) - seen) == []
```

- [ ] **Step 4: Koş — kırmızı**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_officials.py -q -rs`
Expected: toplama hatası `ModuleNotFoundError: No module named 'football_edge.officials'`.

- [ ] **Step 5: En küçük uygulama — `config/tff_teams.yaml`**

```yaml
# TFF "Haftanın Maçları" (pageID=600) takım adı → The Odds API yazımı (spec 2026-10-02-tff-hakem-site-design §4).
#
# Anahtar: normalise_team(TFF adı) — tests/test_officials.py anahtarın kendi çıktısı olduğunu sınar.
# Değer: bu sezon `matches`te (league_id = tur.1) GÖRÜLEN API adı. null = API yazımı henüz hiç görülmedi;
# UYDURULMAZ — o takımın maçı `awaiting_alias` sayılır (loglanır, hata değil). YAML'da HİÇ olmayan TFF adı
# `ContractViolation`dır: düzeltme bu dosyaya satır. Kaynak: canlı DB salt okuma, 2026-10-02.
# Eklenen her API adı `test_every_mapped_api_name_was_seen_in_tur1` ile (veritabanı adresiyle) doğrulanır.
league_label_contains: "Süper Lig"
league_id: tur.1
teams:
  "amed sportif faaliyetler": "Amed SK"  # AMED SPORTİF FAALİYETLER
  "arca çorum": "Çorum FK"  # ARCA ÇORUM FK
  "beşiktaş": "Besiktas JK"  # BEŞİKTAŞ A.Ş.
  "çaykur rizespor": "Çaykur Rizespor"  # ÇAYKUR RİZESPOR A.Ş.
  "corendon alanyaspor": "Alanyaspor"  # CORENDON ALANYASPOR
  "erzurumspor": "Erzurum BB"  # ERZURUMSPOR FK
  "eyüpspor": "Eyüpspor"  # EYÜPSPOR
  "fenerbahçe": "Fenerbahce"  # FENERBAHÇE A.Ş.
  "galatasaray": "Galatasaray"  # GALATASARAY A.Ş.
  "gaziantep kulübü": "Gazişehir Gaziantep"  # GAZİANTEP FUTBOL KULÜBÜ A.Ş.
  "gençlerbirliği": "Genclerbirligi SK"  # GENÇLERBİRLİĞİ
  "göztepe": "Goztepe"  # GÖZTEPE A.Ş.
  "istanbul başakşehir": "Basaksehir"  # İSTANBUL BAŞAKŞEHİR FK
  "kocaelispor": "Kocaelispor"  # KOCAELİSPOR
  "samsunspor": "Samsunspor"  # SAMSUNSPOR A.Ş.
  "trabzonspor": "Trabzonspor"  # TRABZONSPOR A.Ş.
  "kasimpaşa": null  # KASIMPAŞA A.Ş. — API yazımı henüz görülmedi (DEFERRED 9.7a)
  "tümosan konyaspor": null  # TÜMOSAN KONYASPOR — API yazımı henüz görülmedi (DEFERRED 9.7a)
```

- [ ] **Step 6: En küçük uygulama — `src/football_edge/officials.py`**

```python
"""TFF baş hakem atamasını `matches` satırına bağlama (spec 2026-10-02 §4).

Bu modülün ilk parçası takım adı eşlemesidir: `config/tff_teams.yaml`. Anahtar `normalise_team(TFF
adı)`, değer bu sezon `matches`te (`league_id = tur.1`) GÖRÜLEN The Odds API yazımı ya da `null`
(yazım henüz görülmedi — uydurulmaz; o takımın maçı `awaiting_alias` sayılır).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from football_edge.naming import normalise_team

TFF_TEAMS_PATH = Path("config/tff_teams.yaml")
_TOP_KEYS = frozenset({"league_label_contains", "league_id", "teams"})


@dataclass(frozen=True)
class TeamMap:
    league_label_contains: str  # bu metni İÇEREN TFF lig bloğu işlenir
    league_id: str  # `matches.league_id` hedefi
    teams: Mapping[str, str | None]  # normalise_team(TFF adı) → API adı | None

    def matches_league(self, label: str) -> bool:
        """Etiket `league_label_contains`ı TAM ifade olarak taşır ("Süper Ligi" eşleşmez) ve
        kadın/genç ligi bloğu değildir (controller düzeltmesi C1)."""
        folded = label.casefold()
        if any(word in folded for word in _EXCLUDED_LEAGUE_WORDS):
            return False
        phrase = re.escape(self.league_label_contains.casefold()) + r"(?!\w)"
        return re.search(phrase, folded) is not None


def load_team_map(path: Path = TFF_TEAMS_PATH) -> TeamMap:
    """Biçim dışı her dosya `ValueError`dır; mesaj yolu ve kuralı adlandırır."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != _TOP_KEYS:
        raise ValueError(f"{path}: üst anahtarlar {sorted(_TOP_KEYS)} olmalı")
    label, league_id, teams = raw["league_label_contains"], raw["league_id"], raw["teams"]
    if not (isinstance(label, str) and label and isinstance(league_id, str) and league_id):
        raise ValueError(f"{path}: league_label_contains ve league_id boş olmayan metin olmalı")
    if not isinstance(teams, dict) or not teams:
        raise ValueError(f"{path}: teams boş olmayan bir eşleme olmalı")
    return TeamMap(label, league_id, _checked_teams(path, teams))


def _checked_teams(path: Path, teams: Mapping[Any, Any]) -> dict[str, str | None]:
    for key, value in teams.items():
        if not isinstance(key, str) or normalise_team(key) != key:
            raise ValueError(f"{path}: anahtar normalise_team çıktısı değil: {key!r}")
        if value is not None and not (isinstance(value, str) and value.strip()):
            raise ValueError(f"{path}: {key!r} değeri null ya da boş olmayan metin olmalı")
    return {str(key): value for key, value in teams.items()}
```

- [ ] **Step 7: Koş — yeşil**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_officials.py -q -rs`
Expected: `8 passed, 1 skipped`; SKIP satırı `SKIP: canlı ad doğrulaması (DATABASE_URL yok)`.
Sonra: `uv run mypy src scripts` → `Success`; `uv run ruff check src tests scripts` → temiz.

- [ ] **Step 8: Mutasyon kanıtı (iki)**

(a) Anahtar kuralı:
```bash
F=src/football_edge/officials.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'if not isinstance(key, str) or normalise_team(key) != key:' 'if not isinstance(key, str):'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_officials.py -q -k malformed; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`, kırmızı `test_a_malformed_team_map_is_refused_by_name[...normalise_team çıktısı değil]`; `GERI-KONDU`.

(b) YAML kapsamı: `config/tff_teams.yaml`de `  "göztepe": "Goztepe"  # GÖZTEPE A.Ş.` satırını boşla değiştir:
```bash
F=config/tff_teams.yaml; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" '  "göztepe": "Goztepe"  # GÖZTEPE A.Ş.
' ''
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_officials.py -q -k "fixture or eighteen"; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`, iki test kırmızı (`eighteen` 17 ≠ 18; `fixture` `['göztepe']` eksik); `GERI-KONDU`.

- [ ] **Step 9: (İsteğe bağlı, controller — canlı salt okuma izni varsa) canlı ad testi**

Run: `set -a; . ./.env; set +a; PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_officials.py -q -rs -k seen_in_tur1 --tb=short`
Expected: `1 passed`. Koşulmadıysa rapora "canlı ad testi koşulmadı (adres yok)" yazılır. Değer ekrana basılmaz.

- [ ] **Step 10: Commit**

```bash
uv run ruff format src tests scripts
git add docs/superpowers/specs/2026-10-02-tff-hakem-site-design.md config/tff_teams.yaml src/football_edge/officials.py tests/test_officials.py
git commit -F - <<'EOF'
feat: TFF takım adı eşlemesi (config/tff_teams.yaml) ve yükleyicisi; spec awaiting_alias düzeltmesi

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 11: TAM KAPI**

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh > "$T/verify.log" 2>&1; grep -E "^(PASS|FAIL|SKIP)|KAPI" "$T/verify.log"
```
Expected: `FAIL:` yok; `SKIP: site-db (SITE_TEST_DATABASE_URL yok)`, `SKIP: site-derleme/e2e (…)`, `SKIP: zincir (DATABASE_URL yok)`; `KAPI YEŞİL`.

---

### Task 2: TFF satırından İstanbul tarihi ve saati; tarihli anahtar; sayım bekçisi

**Files:**
- Modify: `src/football_edge/collectors/tff.py:19-24` (import), `:53-58` (sınıf sabitlerine tarih), `:149-210` (`parse_referees` → `_kickoff`, `_row_observation`), `:247-252` (`assert_schema` zorunlu alanı)
- Modify: `verify.sh:93` (`EXPECTED_MIN_CONTRACT=25` → `27`)
- Test: `tests/test_tff.py` (yeni yardımcı + dört test; 225. satırdan sonra)

**Interfaces:**
- Consumes: mevcut `parse_referees`, `ContractViolation`, `Observation(source_id, entity_kind, entity_key, observed_at, payload)`.
- Produces: `parse_referees` aynı imza; HER gözlemin yükü `{"home_team", "away_team", "referee", "league", "match_date": "YYYY-MM-DD", "kickoff_local": "HH:MM"}`; `entity_key = f"{normalise_team(home)}|{normalise_team(away)}|{match_date}"`. Görev 4 `payload["match_date"]`i okur.

- [ ] **Step 1: Başarısız testleri yaz — `tests/test_tff.py` (225. satırdan, `test_all_officials_named_without_links_still_raises`ten sonra)**

```python
def _first_date_cell_replaced(html: str, old: str, new: str) -> str:
    """İlk maç satırının (KASIMPAŞA – TÜMOSAN KONYASPOR, atanmış) tarih hücresinde `old` → `new`."""
    soup = BeautifulSoup(html, "html.parser")
    cell = soup.find("div", class_="haftaninMaclariMaclarTarih")
    assert cell is not None
    target = cell.find(string=lambda text: text is not None and old in text)
    assert target is not None, old
    target.replace_with(target.replace(old, new))
    return str(soup)


@pytest.mark.contract
def test_every_row_carries_its_istanbul_date_and_kickoff() -> None:
    """Ölçüldü (2026-09-19): tarih hücresi "18.09.2026 Cuma 20:00" — gün.ay.yıl, gün adı, İstanbul saati."""
    parsed = parse_referees(fixture_html(), observed_at=NOW)
    match = next(entry for entry in parsed if entry.payload["home_team"] == "KASIMPAŞA A.Ş.")

    assert (match.payload["match_date"], match.payload["kickoff_local"]) == ("2026-09-18", "20:00")
    assert all(re.fullmatch(r"2026-09-(18|19|20)", e.payload["match_date"]) for e in parsed)
    assert all(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", e.payload["kickoff_local"]) for e in parsed)


@pytest.mark.contract
def test_the_entity_key_is_dated_so_next_season_cannot_overwrite_this_one() -> None:
    parsed = parse_referees(fixture_html(), observed_at=NOW)
    match = next(entry for entry in parsed if entry.payload["home_team"] == "KASIMPAŞA A.Ş.")

    assert match.entity_key == "kasimpaşa|tümosan konyaspor|2026-09-18"
    assert len({entry.entity_key for entry in parsed}) == len(parsed)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("18.09.2026", "18.09.26"),  # iki haneli yıl: tarih okunmaz
        ("18.09.2026", "31.02.2026"),  # takvimde olmayan gün
        ("20:00", "20.00"),  # saat biçimi değişti
        ("20:00", "25:00"),  # olmayan saat
    ],
)
def test_a_row_whose_date_or_kickoff_cannot_be_read_is_a_loss_not_a_skip(old: str, new: str) -> None:
    """Spec §3.2: tarih/saati okunamayan atanmış satır sayım bekçisine kayıp olarak düşer."""
    degraded = _first_date_cell_replaced(fixture_html(), old, new)

    with pytest.raises(ContractViolation, match="sessizce atlandı"):
        parse_referees(degraded, observed_at=NOW)
```

- [ ] **Step 2: Koş — kırmızı**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_tff.py -q -k "istanbul_date or dated or cannot_be_read"`
Expected: `KeyError: 'match_date'` (iki test) ve `DID NOT RAISE <class 'football_edge.collector.ContractViolation'>` (dört parametre).

- [ ] **Step 3: En küçük uygulama — `src/football_edge/collectors/tff.py`**

İmport bloğu (`:19-24`) şöyle olur:
```python
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
```

`_OFFICIALS_CLASS = "haftaninMaclariMaclarHakemler"` satırının (`:58`) hemen altına:
```python
_DATE_CLASS = "haftaninMaclariMaclarTarih"
# Tarih hücresi ÖLÇÜLDÜ (2026-09-19 fixture'ı, 63/63 satır): "18.09.2026 Cuma 20:00" — gün.ay.yıl,
# Türkçe gün adı, İstanbul saati (spec 2026-10-02 §3.1). Tam BİR tarih ve BİR saat okunmalı; aksi
# satır kayıptır ve `parse_referees`in sayım bekçisine düşer (§3.2).
_DATE = re.compile(r"(?<!\d)(\d{2})\.(\d{2})\.(\d{4})(?!\d)")
_KICKOFF = re.compile(r"(?<![\d:])([01]\d|2[0-3]):([0-5]\d)(?![\d:])")
```

`_league_blocks`ın (`:126-146`) altına, `parse_referees`ten önce iki fonksiyon:
```python
def _kickoff(row: Tag) -> tuple[date, str] | None:
    """Satırın İstanbul tarihi ve `HH:MM` saati; tam bir tarih ve bir saat okunamazsa None."""
    cell = row.find("div", class_=_DATE_CLASS)
    if not isinstance(cell, Tag):
        return None
    text = _text(cell)
    days, times = _DATE.findall(text), _KICKOFF.findall(text)
    if len(days) != 1 or len(times) != 1:
        return None
    day, month, year = (int(part) for part in days[0])
    try:
        when = date(year, month, day)
    except ValueError:
        return None
    hour, minute = times[0]
    return when, f"{hour}:{minute}"


def _row_observation(league: str, row: Tag, observed_at: datetime) -> Observation | None:
    """Tam satırın gözlemi; ev, deplasman, baş hakem, tarih ya da saatten biri yoksa None."""
    home, away = _team_name(row, _HOME_CLASS), _team_name(row, _AWAY_CLASS)
    referee, kickoff = _head_referee(row), _kickoff(row)
    if not (home and away and referee and kickoff):
        return None
    match_date, kickoff_local = kickoff
    day = match_date.isoformat()
    return Observation(
        source_id=SOURCE_ID,
        entity_kind="fixture_official",
        # Tarihli anahtar (spec §3.1): gelecek sezonun aynı eşleşmesi bu sezonu ezemez.
        entity_key=f"{normalise_team(home)}|{normalise_team(away)}|{day}",
        observed_at=observed_at,
        payload={
            "home_team": home,
            "away_team": away,
            "referee": referee,
            "league": league,
            "match_date": day,
            "kickoff_local": kickoff_local,
        },
    )
```

`parse_referees`in gövdesi (`:172-210`; docstring aynen kalır, sonuna bir paragraf eklenir: "Tarih ve saat
de satırın parçasıdır (spec 2026-10-02 §3.2): okunamayan tarih/saat taşıyan atanmış satır aynı bekçiye kayıp
olarak düşer.") şöyle olur:
```python
    soup = BeautifulSoup(html_text, "html.parser")
    parsed: tuple[Observation, ...] = ()
    total_rows = 0
    unassigned = 0
    for league_name, container in _league_blocks(soup):
        for row in container.find_all("div", class_=_MATCH_ROW_CLASS):
            total_rows += 1
            entry = _row_observation(league_name, row, observed_at)
            if entry is None:
                if _officials_cell_is_empty(row):
                    unassigned += 1
                continue
            parsed = (*parsed, entry)
    if total_rows == 0:
        raise ContractViolation(f"{SOURCE_ID}: hiç maç satırı tanınmadı — sayfa şekli değişti")
    if unassigned:
        LOGGER.info("%s: %d maç için hakem ataması henüz yayınlanmamış", SOURCE_ID, unassigned)
    if len(parsed) + unassigned < total_rows:
        raise ContractViolation(
            f"{SOURCE_ID}: {total_rows} satır bulundu, {len(parsed)} ayrıştırıldı, "
            f"{unassigned} görevlisiz; en az bir satır sessizce atlandı"
        )
    return parsed
```

`collect_tff` içindeki `assert_schema` çağrısında (`:247-252`) zorunlu küme:
```python
        required=frozenset({"home_team", "away_team", "referee", "match_date"}),
```

`verify.sh:93`: `  EXPECTED_MIN_CONTRACT=25` → `  EXPECTED_MIN_CONTRACT=27` (iki yeni `contract` testi).

- [ ] **Step 4: Koş — yeşil**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_tff.py tests/test_officials.py -q`
Expected: hepsi geçer (eski testler dahil: 62 gözlem, ikinci tur 0 yeni gözlem).
Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -m contract --collect-only 2>&1 | grep -oE '^[0-9]+/'`
Expected: `27/`.

- [ ] **Step 5: Mutasyon kanıtı (iki)**

(a) Tarihsiz satır kayıp sayılmazsa:
```bash
F=src/football_edge/collectors/tff.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'if not (home and away and referee and kickoff):' 'if not (home and away and referee):'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_tff.py -q -k cannot_be_read; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1` (dört parametre `TypeError: cannot unpack non-iterable NoneType`, `ContractViolation` değil); `GERI-KONDU`.

(b) Anahtar tarihsiz:
```bash
F=src/football_edge/collectors/tff.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'entity_key=f"{normalise_team(home)}|{normalise_team(away)}|{day}",' 'entity_key=f"{normalise_team(home)}|{normalise_team(away)}",'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_tff.py -q -k dated; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`; `GERI-KONDU`.

- [ ] **Step 6: Commit**

```bash
uv run ruff format src tests scripts
git add src/football_edge/collectors/tff.py tests/test_tff.py verify.sh
git commit -F - <<'EOF'
feat: TFF satırından İstanbul tarihi ve saati; tarihli gözlem anahtarı

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 7: TAM KAPI**

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh > "$T/verify.log" 2>&1; grep -E "^(PASS|FAIL|SKIP)|KAPI" "$T/verify.log"
```
Expected: `FAIL:` yok; `PASS: veri-sözleşmesi` dahil; üç adlı SKIP; `KAPI YEŞİL`.

---

### Task 3: 0015 — `public.match_officials` ve `site.match_officials`

**Files:**
- Create: `db/migrations/0015_match_officials.sql`
- Modify: `tests/site_db.py:3` (belge), `:42-47` (`TEMPLATE_MIGRATIONS`), `:203` (belge)
- Create (test): `tests/test_site_officials_migration_text.py`
- Modify (test): `tests/test_site_views_db.py:27-35` (sabitler), `:152-163` (kapanış testi adı/belgesi), `:187` (sahiplik sayısı), `:332-342` (`SITE_TYPES`), `:437-442` (altına 0015 idempotentlik), `:447-482` (`seeded`e hakem tohumu), `:529-537` (parametre), dosya sonuna yeni testler
- Modify: `verify.sh:161` (`EXPECTED_MIN_SITEDB=28` → `37`), `:164` (`EXPECTED_MIN_SITEDB_LEAKAGE=4` → `5`)
- Modify: `docs/RUNBOOK.md:584`

**Interfaces:**
- Consumes: 0001 `public.matches(id)`, `public.forbid_ledger_mutation()` (0013 gövdesi `tg_table_name`li); 0014 `site.matches`, `site_reader`.
- Produces: tablo `public.match_officials(id bigint identity, match_id text → matches.id, referee text 1–80, seen_at timestamptz)`; görünüm `site.match_officials(match_id text, referee text)` — maç başına `seen_at < commence_time` olan EN SON satır, yalnız `site.matches`teki maçlar; `site_reader` SELECT. Görev 4 tabloya `INSERT INTO match_officials (match_id, referee, seen_at)`; Görev 5 görünümden `SELECT match_id, referee FROM site.match_officials ORDER BY match_id` yapar.

- [ ] **Step 1: Başarısız metin testlerini yaz — `tests/test_site_officials_migration_text.py`**

```python
"""0015 METNİ (spec 2026-10-02 §5): her kapıda, DB'siz. Yorumlar ayıklanır, yorumdaki kelime sayılmaz."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.sql_text import statements
from tests.test_site_migration_text import _select_items

MIGRATION = Path(__file__).resolve().parent.parent / "db/migrations/0015_match_officials.sql"
_VIEW = re.compile(r"create or replace view site\.match_officials with \(security_barrier\) as (.*)")


def _statements() -> list[str]:
    return statements(MIGRATION.read_text(encoding="utf-8"))


def _view() -> str:
    (body,) = [found.group(1) for text in _statements() if (found := _VIEW.fullmatch(text))]
    return body


def test_0015_bounds_its_lock_wait_like_0014() -> None:
    assert (_statements()[0], _statements()[-1]) == ("set lock_timeout = '5s'", "reset lock_timeout")


def test_the_table_is_the_spec_table() -> None:
    assert (
        "create table if not exists public.match_officials ( "
        "id bigint generated always as identity primary key, "
        "match_id text not null references public.matches(id), "
        "referee text not null check (length(referee) between 1 and 80), "
        "seen_at timestamptz not null )"
    ) in _statements()
    assert (
        "create index if not exists match_officials_match_idx "
        "on public.match_officials (match_id, seen_at)"
    ) in _statements()


def test_the_table_is_append_only_and_truncate_guarded() -> None:
    text = _statements()

    assert (
        "create trigger match_officials_append_only before update or delete "
        "on public.match_officials for each row execute function public.forbid_ledger_mutation()"
    ) in text
    assert (
        "create trigger match_officials_no_truncate before truncate on public.match_officials "
        "for each statement execute function public.forbid_ledger_mutation()"
    ) in text


def test_rls_is_on_without_force_or_policy_and_the_api_roles_lose_everything() -> None:
    text = _statements()
    joined = " ".join(text)

    assert "alter table public.match_officials enable row level security" in text
    assert "force row level security" not in joined and "create policy" not in joined
    assert "revoke all on public.match_officials from anon, authenticated" in text
    assert "revoke all on sequence public.match_officials_id_seq from anon, authenticated" in text
    assert "revoke all on site.match_officials from anon, authenticated, service_role" in text


def test_the_view_reads_only_the_table_and_site_matches_and_is_not_invoker() -> None:
    sources = set(re.findall(r"\b(?:from|join) ([\w.]+)", _view()))

    assert sources == {"public.match_officials", "site.matches"}
    assert all("security_invoker" not in text for text in _statements())


@pytest.mark.leakage
def test_the_view_shows_the_last_assignment_seen_before_kickoff() -> None:
    body = _view()

    assert _select_items(body) == ("distinct on (o.match_id) o.match_id", "o.referee")
    assert "join site.matches m on m.id = o.match_id" in body
    assert "where o.seen_at < m.commence_time" in body
    assert body.endswith("order by o.match_id, o.seen_at desc, o.id desc")
    assert "public_floor" not in body, "taban site.matches join'inden gelir"


def test_the_only_grant_is_select_on_the_view_to_site_reader() -> None:
    grants = [text for text in _statements() if text.startswith("grant ")]
    joined = " ".join(_statements())

    assert grants == ["grant select on site.match_officials to site_reader"]
    assert re.search(r"\blogin\b", joined) is None and re.search(r"\bpassword\b", joined) is None
```

- [ ] **Step 2: Başarısız DB testlerini yaz — `tests/test_site_views_db.py`**

(i) Sabitler (`:27-35`):
```python
BASE_TABLES = {"public.leagues", "public.matches", "public.match_officials", "public.odds_snapshots"}
SITE_VIEWS = {
    "site.leagues",
    "site.matches",
    "site.match_officials",
    "site.ledger_head",
    "site.record",
    "site_input.h2h_quotes",
    "site_audit.ledger_rows",
}
```
(ii) Kapanış testi (`:152-163`): ad `test_the_views_depend_on_exactly_the_base_tables_and_the_floor`, gövde aynı,
belge iki satır:
```python
    """H1a: temel tablolar = {leagues, matches, match_officials, odds_snapshots} (match_officials
    2026-10-02'den beri, spec tff-hakem-site §5); fonksiyonlar ⊆ {public_floor}."""
```
(iii) `:187`: `assert len(owners) == 6 + 3` → `assert len(owners) == 7 + 4`.
(iv) `SITE_TYPES`e (`:332-342`) `"site.ledger_head"`tan önce:
```python
    "site.match_officials": [("match_id", "text"), ("referee", "text")],
```
(v) `test_applying_0014_twice_is_harmless`in (`:437-442`) altına:
```python
def test_applying_0015_twice_is_harmless(full_sequence: psycopg.Cursor[Any]) -> None:
    full_sequence.execute("SAVEPOINT again_0015")
    full_sequence.execute((REPO / "db/migrations/0015_match_officials.sql").read_text().encode())
    columns = _rows(
        full_sequence,
        "SELECT attname::text FROM pg_attribute WHERE attrelid = 'site.match_officials'::regclass "
        "AND attnum > 0 AND NOT attisdropped ORDER BY attnum",
    )
    full_sequence.execute("ROLLBACK TO SAVEPOINT again_0015")

    assert columns == [("match_id",), ("referee",)]


def test_the_officials_table_has_rls_without_policy_or_force_and_no_api_grant(
    full_sequence: psycopg.Cursor[Any],
) -> None:
    ((rls, force),) = _rows(
        full_sequence,
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE oid = 'public.match_officials'::regclass",
    )
    policies = _rows(
        full_sequence,
        "SELECT polname FROM pg_policy WHERE polrelid = 'public.match_officials'::regclass",
    )
    tables = _rows(
        full_sequence,
        "SELECT r FROM unnest(%s::text[]) r WHERE has_table_privilege(r, "
        "'public.match_officials', 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
        (["anon", "authenticated"],),
    )
    sequences = _rows(
        full_sequence,
        "SELECT r FROM unnest(%s::text[]) r "
        "WHERE has_sequence_privilege(r, 'public.match_officials_id_seq', 'USAGE,SELECT,UPDATE')",
        (["anon", "authenticated"],),
    )

    assert (rls, force) == (True, False)
    assert policies == [] and tables == [] and sequences == []
```
(vi) `seeded`e (`:447-482`) — sabitler `ASLEEP = …` satırının altına:
```python
# 0015 tohumları: tablo gözlemleri, görünüm başlama ANINDAN önceki SON satırı göstermeli.
OFFICIALS = (
    (HOLDOUT[0], "Holdout Hakem", "2026-01-14T12:00:00Z"),  # taban altı maç: görünmez
    (FLOOR[0], "Taban Hakem", "2026-07-01T12:00:00Z"),  # taban maçı, başlamadan önce: görünür
    (LIVE[0], "Önce Hakem", "2026-09-18T10:00:00Z"),
    (LIVE[0], "Son Hakem", "2026-09-19T10:00:00Z"),  # başlamadan önceki EN SON: görünür
    (LIVE[0], "Geç Hakem", LIVE[1]),  # tam başlama anı: görünmez (seen_at < commence_time)
    (ASLEEP[0], "Uyuyan Hakem", "2026-09-20T10:00:00Z"),  # pasif lig: görünmez
)
```
ve `seeded` içinde odds döngüsünden sonra, `conn.commit()`ten önce:
```python
        cur.executemany(
            "INSERT INTO match_officials (match_id, referee, seen_at) VALUES (%s, %s, %s)", OFFICIALS
        )
```
(vii) `test_site_reader_cannot_touch_a_table_or_write_through_a_view` parametre listesine (`:529-537`) ikinci satırdan sonra:
```python
        "SELECT 1 FROM public.match_officials LIMIT 1",
```
(viii) Dosya sonuna:
```python
@pytest.mark.leakage
def test_the_officials_view_hides_holdout_and_passive_league_matches(
    seeded: psycopg.Cursor[Any],
) -> None:
    with as_reader(seeded) as cur:
        shown = {row[0] for row in _rows(cur, "SELECT match_id FROM site.match_officials")}

    assert shown == {FLOOR[0], LIVE[0]}


def test_the_officials_view_shows_the_last_referee_seen_before_kickoff(
    seeded: psycopg.Cursor[Any],
) -> None:
    with as_reader(seeded) as cur:
        rows = dict(_rows(cur, "SELECT match_id, referee FROM site.match_officials"))

    assert rows == {FLOOR[0]: "Taban Hakem", LIVE[0]: "Son Hakem"}


@pytest.mark.parametrize(
    ("statement", "operation"),
    [
        ("UPDATE match_officials SET referee = 'x'", "UPDATE"),
        ("DELETE FROM match_officials", "DELETE"),
        ("TRUNCATE match_officials", "TRUNCATE"),
    ],
)
def test_match_officials_is_append_only_even_for_the_owner(
    seeded: psycopg.Cursor[Any], statement: str, operation: str
) -> None:
    seeded.execute("SAVEPOINT append_only")
    try:
        with pytest.raises(
            psycopg.errors.RaiseException,
            match=f"match_officials append-only bir defterdir; {operation}",
        ):
            seeded.execute(statement)
    finally:
        seeded.execute("ROLLBACK TO SAVEPOINT append_only")
```

- [ ] **Step 3: Koş — kırmızı**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_officials_migration_text.py tests/test_site_template_subset.py -q`
Expected: `FileNotFoundError: …/0015_match_officials.sql` (metin testleri). Kum havuzu varsa
(`FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_views_db.py`): `UndefinedTable: relation "match_officials" does not exist` ile kırmızı.

- [ ] **Step 4: En küçük uygulama — `db/migrations/0015_match_officials.sql`**

```sql
-- TFF baş hakemi (docs/superpowers/specs/2026-10-02-tff-hakem-site-design.md §5). YAZILIR, canlıya bu
-- görevde UYGULANMAZ: docs/HANDOFF.md §0.4 Adım 12'de 0014'ten SONRA, aynı kuralla (sessiz aralık, ROLLBACK
-- provası, bayt bayt metin + sha256 deftere, `postgres` rolü, advisors). 0014'e DOKUNMAZ; site şeması ve
-- `site_reader` 0014'te kurulur. `site_reader`a LOGIN veren migration 0016'dır.
--
-- `public.match_officials` değişiklik kaydıdır: maçın SON kayıtlı hakemi bu turunkinden farklıysa (ya da hiç
-- yoksa) bir satır (`football_edge.officials.link_officials`). Append-only (0001'in tetikleyici fonksiyonu,
-- 0013'ün TRUNCATE bekçisi deseni), RLS açık + politikasız + FORCE yok (0013 deseni: sahibin yazımı durmasın),
-- API rollerinin yetkisi yok. `site.match_officials`: maç başına `commence_time`dan ÖNCE görülen SON atama;
-- taban ve pasif lig süzgeci `site.matches` join'inden gelir (H1a: yeni temel tablo yalnız bu).

-- DEFERRED 18f'in biçimi (0014 ile aynı): `set … reset` her gönderim biçiminde bağlar.
set lock_timeout = '5s';

create table if not exists public.match_officials (
  id         bigint generated always as identity primary key,
  match_id   text not null references public.matches(id),
  referee    text not null check (length(referee) between 1 and 80),
  seen_at    timestamptz not null
);
create index if not exists match_officials_match_idx on public.match_officials (match_id, seen_at);

-- Append-only: UPDATE/DELETE satır tetikleyicisi, TRUNCATE ifade tetikleyicisi (sahip için de koşar;
-- `truncate matches cascade` da buradan geçer). Mesaj tablonun adını taşır (0013 gövdesi).
drop trigger if exists match_officials_append_only on public.match_officials;
create trigger match_officials_append_only
  before update or delete on public.match_officials
  for each row execute function public.forbid_ledger_mutation();

drop trigger if exists match_officials_no_truncate on public.match_officials;
create trigger match_officials_no_truncate
  before truncate on public.match_officials
  for each statement execute function public.forbid_ledger_mutation();

-- 0013 kalıbı: RLS politikasız; API rollerinden açıkça geri alınır (0013'ün varsayılan yetki kapanışına ek).
alter table public.match_officials enable row level security;
revoke all on public.match_officials from anon, authenticated;
revoke all on sequence public.match_officials_id_seq from anon, authenticated;

create or replace view site.match_officials with (security_barrier) as
  select distinct on (o.match_id) o.match_id, o.referee
  from public.match_officials o
  join site.matches m on m.id = o.match_id
  where o.seen_at < m.commence_time
  order by o.match_id, o.seen_at desc, o.id desc;

revoke all on site.match_officials from anon, authenticated, service_role;
grant select on site.match_officials to site_reader;

reset lock_timeout;
```

`tests/site_db.py`:
- `:3` `0001→0014 tek işlemde` → `0001→0015 tek işlemde`; `:203` `0001→0014 tek işlemde` → `0001→0015 tek işlemde`.
- `TEMPLATE_MIGRATIONS` (`:42-47`):
```python
TEMPLATE_MIGRATIONS = (
    "0001_init.sql",
    "0002_sources.sql",
    "0013_api_roles_lockdown.sql",
    "0014_site_read.sql",
    "0015_match_officials.sql",
)
```
`verify.sh:161` `    EXPECTED_MIN_SITEDB=28` → `    EXPECTED_MIN_SITEDB=37`; `:164` `    EXPECTED_MIN_SITEDB_LEAKAGE=4` → `    EXPECTED_MIN_SITEDB_LEAKAGE=5`.
`docs/RUNBOOK.md:584`: `0001→0014'ü tek işlemde` → `0001→0015'i tek işlemde`; `(0001, 0002, 0013, 0014)` → `(0001, 0002, 0013, 0014, 0015)`.

- [ ] **Step 5: Koş — yeşil**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_officials_migration_text.py tests/test_site_template_subset.py tests/test_site_migration_text.py tests/test_site_harness_rules.py -q`
Expected: hepsi geçer.
Run: `for m in sitedb "sitedb and leakage"; do PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -m "$m" --collect-only 2>&1 | grep -oE '^[0-9]+/'; done`
Expected: `37/` ve `5/` (28 + 9: iki görünüm, iki katalog, bir tip parametresi, bir okuyucu parametresi, üç append-only; leakage +1).
Kum havuzu (Global Constraints komutları): `FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_views_db.py tests/test_site_e2e_db.py`
Expected: hepsi geçer (e2e değişmeden: 0015 tohumsuz boş görünüm). Docker yoksa: "yerelde koşmadı (Docker yok)".

- [ ] **Step 6: Mutasyon kanıtı (metin; DB'si kum havuzunda)**

(a) As-of sınırı:
```bash
F=db/migrations/0015_match_officials.sql; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'where o.seen_at < m.commence_time' 'where o.seen_at <= m.commence_time'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_officials_migration_text.py -q; echo "exit=$?"
FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_views_db.py -k last_referee; echo "db-exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1` (`test_the_view_shows_the_last_assignment_seen_before_kickoff`); kum havuzunda `db-exit=1` (`LIVE` → `Geç Hakem`); `GERI-KONDU`.

(b) Taban kaçağı:
```bash
F=db/migrations/0015_match_officials.sql; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'join site.matches m on m.id = o.match_id' 'join public.matches m on m.id = o.match_id'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_officials_migration_text.py -q; echo "exit=$?"
FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_views_db.py -k "hides_holdout or base_tables"; echo "db-exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1` (iki metin testi); kum havuzunda `db-exit=1` (holdout ve pasif lig görünür); `GERI-KONDU`.

(c) RLS:
```bash
F=db/migrations/0015_match_officials.sql; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'alter table public.match_officials enable row level security;
' ''
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_officials_migration_text.py -q -k rls; echo "exit=$?"
FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_views_db.py -k rls_without_policy; echo "db-exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`; `db-exit=1`; `GERI-KONDU`.

(d) Append-only — DELETE bekçisi düşerse:
```bash
F=db/migrations/0015_match_officials.sql; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" '  before update or delete on public.match_officials' '  before update on public.match_officials'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_officials_migration_text.py -q -k append_only; echo "exit=$?"
FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_views_db.py -k append_only; echo "db-exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`; kum havuzunda `db-exit=1` (yalnız `DELETE` parametresi `DID NOT RAISE`); `GERI-KONDU`.

- [ ] **Step 7: Commit**

```bash
uv run ruff format src tests scripts
git add db/migrations/0015_match_officials.sql tests/site_db.py tests/test_site_officials_migration_text.py tests/test_site_views_db.py verify.sh docs/RUNBOOK.md
git commit -F - <<'EOF'
feat: 0015 match_officials — append-only tablo ve site.match_officials görünümü

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 8: TAM KAPI**

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh > "$T/verify.log" 2>&1; grep -E "^(PASS|FAIL|SKIP)|KAPI" "$T/verify.log"
```
Expected: `FAIL:` yok; üç adlı SKIP; `KAPI YEŞİL`. (İnceleme: kabuk taşıyan bağımsız inceleyici — güvenlik sınırı.)

---

### Task 4: `link_officials` — eşleme, değişiklik kaydı, `collect_tff`e bağlama

**Files:**
- Modify: `src/football_edge/officials.py` (Görev 1'in dosyası — aşağıdaki TAM içerikle değiştirilir)
- Modify: `src/football_edge/collectors/tff.py:30-33` (import), `:223-255` (`collect_tff`)
- Modify (test): `tests/test_officials.py` (import bloğu + dosya sonuna testler)
- Modify (test): `tests/test_tff.py:18-33` (import), `:254-347` (üç toplama testi `links` fixture'ı alır) + yeni test
- Create (test): `tests/test_site_officials_db.py`
- Modify: `verify.sh:161` (`EXPECTED_MIN_SITEDB=37` → `40`)
- Modify: `scripts/sandbox_db.sh` `DEFAULT_TESTS` (`tests/test_site_officials_db.py` eklenir)

**Interfaces:**
- Consumes: Görev 1 `TeamMap`, `load_team_map`, `TFF_TEAMS_PATH`; Görev 2 yükü (`payload["match_date"]` ISO); Görev 3 tablosu `match_officials(match_id, referee, seen_at)`; `ContractViolation`, `Observation`, `normalise_team`.
- Produces (hepsi `football_edge.officials`):
  - `ISTANBUL: ZoneInfo`, `REFEREE_MAX = 80`
  - `@dataclass(frozen=True) Assignment(league: str, home: str, away: str, referee: str, match_date: date)`
  - `@dataclass(frozen=True) Candidate(match_id: str, home: str, away: str, commence_time: datetime)`
  - `@dataclass(frozen=True) LinkPlan(links: tuple[tuple[str, str], ...], not_in_db: int, awaiting_alias: int, other_league: int)`
  - `@dataclass(frozen=True) LinkResult(linked: int, written: int, not_in_db: int, awaiting_alias: int, other_league: int)`
  - `istanbul_day(moment: datetime) -> date`; `assignment_of(entry: Observation) -> Assignment`
  - `plan_links(assignments: Sequence[Assignment], candidates: Sequence[Candidate], team_map: TeamMap) -> LinkPlan`
  - `pending_writes(links: Sequence[tuple[str, str]], latest: Mapping[str, str], now: datetime) -> tuple[tuple[str, str, datetime], ...]`
  - `find_candidates(conn: psycopg.Connection[Any], league_id: str, days: Sequence[date]) -> tuple[Candidate, ...]`
  - `link_officials(conn: psycopg.Connection[Any], observations: Sequence[Observation], *, team_map: TeamMap, now: datetime) -> LinkResult`
  - `collect_tff(conn, client, *, sources_path: Path, robots_dir: Path, now: datetime, teams_path: Path = TFF_TEAMS_PATH) -> int` (dönüş aynı: yeni gözlem sayısı)

- [ ] **Step 1: Başarısız birim testlerini yaz — `tests/test_officials.py`**

İmport bloğu şöyle olur:
```python
from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml

from football_edge.collector import ContractViolation
from football_edge.collectors.tff import parse_referees
from football_edge.db import connect
from football_edge.naming import normalise_team
from football_edge.officials import (
    Assignment,
    Candidate,
    TeamMap,
    assignment_of,
    load_team_map,
    pending_writes,
    plan_links,
)
```
Dosya sonuna:
```python
LABEL = "Trendyol Süper Lig Adnan Süvari Sezonu"
MAP = TeamMap(
    "Süper Lig",
    "tur.1",
    {
        "trabzonspor": "Trabzonspor",
        "galatasaray": "Galatasaray",
        "beşiktaş": "Besiktas JK",
        "kasimpaşa": None,
    },
)
TS_GS = ("TRABZONSPOR A.Ş.", "GALATASARAY A.Ş.")


def _assign(
    home: str, away: str, day: str, *, referee: str = "ALİ HAKEM", league: str = LABEL
) -> Assignment:
    return Assignment(league, home, away, referee, date.fromisoformat(day))


def _game(match_id: str, home: str, away: str, kickoff: str) -> Candidate:
    return Candidate(match_id, home, away, datetime.fromisoformat(kickoff))


def test_an_observation_becomes_an_assignment_with_its_istanbul_date() -> None:
    parsed = parse_referees(TFF_FIXTURE.read_text(encoding="utf-8"), observed_at=NOW)
    (entry,) = [e for e in parsed if e.payload["home_team"] == "KASIMPAŞA A.Ş."]

    assert assignment_of(entry) == Assignment(
        LABEL, "KASIMPAŞA A.Ş.", "TÜMOSAN KONYASPOR", "DAVUT DAKUL ÇELİK", date(2026, 9, 18)
    )


def test_a_tff_name_missing_from_the_yaml_is_red_by_name() -> None:
    with pytest.raises(ContractViolation, match="YENİ KULÜP A.Ş."):
        plan_links([_assign("YENİ KULÜP A.Ş.", "GALATASARAY A.Ş.", "2026-09-19")], [], MAP)


def test_a_block_outside_the_label_is_counted_not_processed() -> None:
    plan = plan_links(
        [_assign("YENİ KULÜP", "BAŞKA KULÜP", "2026-09-19", league="Trendyol 1. Lig")], [], MAP
    )

    assert (plan.links, plan.other_league) == ((), 1)


def test_a_null_alias_is_awaiting_not_red() -> None:
    games = [_game("m1", "Kasimpasa", "Besiktas JK", "2026-09-19T17:00:00+00:00")]
    plan = plan_links([_assign("KASIMPAŞA A.Ş.", "BEŞİKTAŞ A.Ş.", "2026-09-19")], games, MAP)

    assert (plan.links, plan.awaiting_alias, plan.not_in_db) == ((), 1, 0)


@pytest.mark.parametrize(
    ("day", "kickoff"),
    [
        ("2026-09-19", "2026-09-18T22:00:00+00:00"),  # 01:00 İstanbul: UTC'de önceki gün
        ("2026-09-18", "2026-09-18T20:30:00+00:00"),  # 23:30 İstanbul: UTC'de aynı gün
    ],
)
def test_the_match_day_is_the_istanbul_calendar_day(day: str, kickoff: str) -> None:
    games = [_game("m1", "Trabzonspor", "Galatasaray", kickoff)]

    assert plan_links([_assign(*TS_GS, day)], games, MAP).links == (("m1", "ALİ HAKEM"),)


def test_the_utc_day_is_not_the_match_day() -> None:
    games = [_game("m1", "Trabzonspor", "Galatasaray", "2026-09-18T22:00:00+00:00")]
    plan = plan_links([_assign(*TS_GS, "2026-09-18")], games, MAP)

    assert (plan.links, plan.not_in_db) == ((), 1)


def test_no_match_in_the_db_is_counted_not_red() -> None:
    plan = plan_links([_assign(*TS_GS, "2026-09-19")], [], MAP)

    assert (plan.links, plan.not_in_db) == ((), 1)


def test_two_db_matches_on_the_same_istanbul_day_are_red() -> None:
    games = [
        _game("m1", "Trabzonspor", "Galatasaray", "2026-09-19T12:00:00+00:00"),
        _game("m2", "Trabzonspor", "Galatasaray", "2026-09-19T17:00:00+00:00"),
    ]
    with pytest.raises(ContractViolation, match="2 maç"):
        plan_links([_assign(*TS_GS, "2026-09-19")], games, MAP)


def test_only_a_changed_or_first_referee_is_written() -> None:
    now = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)
    links = (("m1", "ALİ"), ("m2", "VELİ"), ("m3", "CAN"))

    assert pending_writes(links, {"m1": "ALİ", "m2": "ESKİ"}, now) == (
        ("m2", "VELİ", now),
        ("m3", "CAN", now),
    )


def test_the_fixture_round_with_the_committed_yaml_is_red_nowhere() -> None:
    """Ölçülen tur: 62 satır, 9'u Süper Lig; KASIMPAŞA–KONYASPOR alias bekler, 8'i DB'siz."""
    parsed = parse_referees(TFF_FIXTURE.read_text(encoding="utf-8"), observed_at=NOW)
    plan = plan_links([assignment_of(e) for e in parsed], [], load_team_map(TEAMS_YAML))

    assert (plan.links, plan.not_in_db, plan.awaiting_alias, plan.other_league) == ((), 8, 1, 53)


# ── Review Focus ──────────────────────────────────────────────────────────────────────────────


def test_review_focus_an_unknown_team_in_another_super_lig_block_is_red_with_its_label() -> None:
    women = "Turkcell Kadın Futbol Süper Ligi"

    with pytest.raises(ContractViolation, match=women):
        plan_links([_assign("ABB FOMGET GSK", "GALATASARAY A.Ş.", "2026-09-19", league=women)], [], MAP)


def test_review_focus_the_same_match_twice_with_one_referee_links_once() -> None:
    games = [_game("m1", "Trabzonspor", "Galatasaray", "2026-09-19T17:00:00+00:00")]
    rows = [_assign(*TS_GS, "2026-09-19"), _assign(*TS_GS, "2026-09-19")]

    assert plan_links(rows, games, MAP).links == (("m1", "ALİ HAKEM"),)


def test_review_focus_the_same_match_with_two_referees_is_red() -> None:
    games = [_game("m1", "Trabzonspor", "Galatasaray", "2026-09-19T17:00:00+00:00")]
    rows = [_assign(*TS_GS, "2026-09-19"), _assign(*TS_GS, "2026-09-19", referee="VELİ HAKEM")]

    with pytest.raises(ContractViolation, match="iki farklı hakem"):
        plan_links(rows, games, MAP)


@pytest.mark.parametrize("referee", ["", "A" * 81, "<b>ALİ</b>", "ALİ http://x.invalid"])
def test_review_focus_an_unpublishable_referee_text_is_red_before_the_db(referee: str) -> None:
    with pytest.raises(ContractViolation, match="hakem metni sözleşme dışı"):
        plan_links([_assign(*TS_GS, "2026-09-19", referee=referee)], [], MAP)


def test_review_focus_reversed_home_and_away_is_not_linked_but_warned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="football_edge.officials")
    games = [_game("m1", "Galatasaray", "Trabzonspor", "2026-09-19T17:00:00+00:00")]
    plan = plan_links([_assign(*TS_GS, "2026-09-19")], games, MAP)

    assert (plan.links, plan.not_in_db) == ((), 1)
    assert "ters ev/deplasman" in caplog.text
```

- [ ] **Step 2: Başarısız toplama testlerini yaz — `tests/test_tff.py`**

İmport bloğu (`:18-33`) şöyle olur:
```python
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from bs4 import BeautifulSoup

from football_edge.collector import ContractViolation
from football_edge.collectors import tff
from football_edge.collectors.tff import collect_tff, parse_referees
from football_edge.naming import normalise_team
from football_edge.officials import LinkResult, TeamMap
from tests.fake_obs_db import FakeObservationDb
from tests.fake_sources import write_robots
```
`_write_sources_yaml`dan (`:233`) önce fixture:
```python
@pytest.fixture
def links(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """`link_officials`in kaydedicisi: taklit DB `matches`/`match_officials` sorgularını tanımaz."""
    calls: list[dict[str, Any]] = []

    def record(conn: Any, observations: Any, *, team_map: TeamMap, now: datetime) -> LinkResult:
        calls.append({"observations": observations, "team_map": team_map, "now": now})
        return LinkResult(linked=9, written=3, not_in_db=1, awaiting_alias=1, other_league=53)

    monkeypatch.setattr(tff, "link_officials", record)
    return calls
```
Üç mevcut toplama testinin imzası `links` alır (gövdeler aynı):
`def test_collect_tff_writes_observations_and_commits(tmp_path: Path, links: list[dict[str, Any]]) -> None:`,
`def test_collect_tff_second_round_is_idempotent(tmp_path: Path, links: list[dict[str, Any]]) -> None:`,
`def test_collect_tff_week_with_no_assignments_writes_nothing_and_succeeds(tmp_path: Path, links: list[dict[str, Any]]) -> None:`
— sonuncusunun son satırı `assert db.rows == []`ın altına `assert links == [], "atanmamış haftada bağlama çağrılmaz"`.
Dosya sonuna:
```python
def test_collect_tff_links_this_rounds_parse_with_the_same_now(
    tmp_path: Path, links: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    """Spec §3.3: bağlama gözlem tablosundan OKUMAZ — turun ayrıştırılmış sonucu ve AYNI `now`."""
    caplog.set_level(logging.INFO, logger="football_edge.collectors.tff")
    sources_path = _write_sources_yaml(tmp_path)
    write_robots(tmp_path, "tff", "")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=fixture_html().encode("windows-1254"),
            headers={"content-type": "text/html; charset=windows-1254"},
        )

    collect_tff(
        FakeObservationDb(),  # type: ignore[arg-type]
        httpx.Client(transport=httpx.MockTransport(handler)),
        sources_path=sources_path,
        robots_dir=tmp_path,
        now=NOW,
    )

    (call,) = links
    assert call["now"] == NOW
    assert call["observations"] == parse_referees(fixture_html(), observed_at=NOW)
    assert call["team_map"].league_id == "tur.1"
    assert "bağlanan 9, yeni yazılan 3, DB'de yok 1, alias bekleyen 1, lig dışı 53" in caplog.text
```

- [ ] **Step 3: Başarısız DB testlerini yaz — `tests/test_site_officials_db.py`**

```python
"""`link_officials` gerçek Postgres'te (spec 2026-10-02 §4, §9/3): değişiklik kaydı ve İstanbul günü.

Yalnız atılabilir yerel kapta koşar (`tests/site_db.py`): `scripts/sandbox_db.sh test
tests/test_site_officials_db.py`. Değişken yoksa yerelde SKIP, CI'da FAIL. Her test şablonun kendi
kopyasında (`site_db_each`): append-only tablo temizlenmez, veritabanı atılır.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import psycopg
import pytest

from football_edge.collector import Observation
from football_edge.officials import LinkResult, TeamMap, find_candidates, link_officials
from tests.site_db import site_cluster, site_db_each

pytestmark = pytest.mark.sitedb

LABEL = "Trendyol Süper Lig Adnan Süvari Sezonu"
TEAMS = TeamMap("Süper Lig", "tur.1", {"trabzonspor": "Trabzonspor", "galatasaray": "Galatasaray"})
MATCH = "m-ts-gs"
# İstanbul günleri: MATCH 20:00 İst. 19 Eylül · m-gece 00:00 İst. 19 Eylül (UTC'de 18'i) ·
# m-ertesi 00:00 İst. 20 Eylül (UTC'de 19'u) · m-baska-lig aynı takımlar, başka lig.
MATCHES = (
    (MATCH, "tur.1", "2026-09-19T17:00:00+00:00", "Trabzonspor", "Galatasaray"),
    ("m-gece", "tur.1", "2026-09-18T21:00:00+00:00", "Goztepe", "Samsunspor"),
    ("m-ertesi", "tur.1", "2026-09-19T21:00:00+00:00", "Goztepe", "Samsunspor"),
    ("m-baska-lig", "tst.1", "2026-09-19T17:00:00+00:00", "Trabzonspor", "Galatasaray"),
)


def _seed(url: str) -> None:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO leagues VALUES "
            "('tur.1', 'k-tur', 'Süper Lig', 'Türkiye', 'tr', 'TR', true), "
            "('tst.1', 'k-tst', 'Deneme Ligi', 'Testland', 'tr', 'TR', true)"
        )
        cur.executemany(
            "INSERT INTO matches (id, league_id, commence_time, home_team, away_team) "
            "VALUES (%s, %s, %s, %s, %s)",
            MATCHES,
        )


def _round(referee: str) -> tuple[Observation, ...]:
    return (
        Observation(
            source_id="tff",
            entity_kind="fixture_official",
            entity_key="trabzonspor|galatasaray|2026-09-19",
            observed_at=datetime(2026, 9, 17, 9, 0, tzinfo=UTC),
            payload={
                "home_team": "TRABZONSPOR A.Ş.",
                "away_team": "GALATASARAY A.Ş.",
                "referee": referee,
                "league": LABEL,
                "match_date": "2026-09-19",
                "kickoff_local": "20:00",
            },
        ),
    )


def _at(hour: int) -> datetime:
    return datetime(2026, 9, 17, hour, 0, tzinfo=UTC)


def _link(url: str, referee: str, hour: int) -> LinkResult:
    with psycopg.connect(url) as conn:
        return link_officials(conn, _round(referee), team_map=TEAMS, now=_at(hour))


def _recorded(url: str) -> list[tuple[str, str, datetime]]:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT match_id, referee, seen_at FROM match_officials ORDER BY id")
        return [(str(a), str(b), c) for a, b, c in cur.fetchall()]


def test_the_same_referee_is_not_recorded_twice(site_db_each: str) -> None:
    _seed(site_db_each)
    first = _link(site_db_each, "ALİ HAKEM", 9)
    second = _link(site_db_each, "ALİ HAKEM", 10)

    assert (first.linked, first.written, second.linked, second.written) == (1, 1, 1, 0)
    assert _recorded(site_db_each) == [(MATCH, "ALİ HAKEM", _at(9))]


def test_x_then_y_then_x_is_three_rows(site_db_each: str) -> None:
    """I-5 burada oluşmaz: karşılaştırma maçın SON kayıtlı hakemiyledir, içerik hash'iyle değil."""
    _seed(site_db_each)
    for referee, hour in (("ALİ HAKEM", 9), ("VELİ HAKEM", 10), ("ALİ HAKEM", 11)):
        _link(site_db_each, referee, hour)

    assert _recorded(site_db_each) == [
        (MATCH, "ALİ HAKEM", _at(9)),
        (MATCH, "VELİ HAKEM", _at(10)),
        (MATCH, "ALİ HAKEM", _at(11)),
    ]


def test_candidates_are_the_istanbul_day_of_the_target_league(site_db_each: str) -> None:
    _seed(site_db_each)
    with psycopg.connect(site_db_each) as conn:
        found = find_candidates(conn, "tur.1", [date(2026, 9, 19)])

    assert sorted(candidate.match_id for candidate in found) == ["m-gece", MATCH]
```

- [ ] **Step 4: Koş — kırmızı**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_officials.py tests/test_tff.py -q`
Expected: toplama hatası `ImportError: cannot import name 'Assignment' from 'football_edge.officials'` (ve `LinkResult`).

- [ ] **Step 5: En küçük uygulama — `src/football_edge/officials.py` (TAM içerik)**

```python
"""TFF baş hakem atamasını `matches` satırına bağlar ve değişikliği kaydeder (spec 2026-10-02 §4).

Takım adı eşlemesi `config/tff_teams.yaml`dır: anahtar `normalise_team(TFF adı)`, değer bu sezon
`matches`te (`league_id = tur.1`) GÖRÜLEN The Odds API yazımı ya da `null` (yazım henüz görülmedi —
uydurulmaz; o takımın maçı `awaiting_alias` sayılır, hata değil). YAML'da HİÇ olmayan ad
`ContractViolation`dır (yapılandırma eksiği; düzeltme YAML'a satır).

Bağlama gözlem tablosunu OKUMAZ: `collect_tff`in o turda ayrıştırdığı gözlemlerden çalışır; bu
yüzden `latest_observations`in X→Y→X sınırlaması (DEFERRED 9.6e, I-5) burada oluşmaz. Maç, TFF
tarihinin Europe/Istanbul takvim günüyle bulunur; saat uyuşmazlığı eşlemeyi bozmaz.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
import yaml

from football_edge.collector import ContractViolation, Observation
from football_edge.naming import normalise_team

LOGGER = logging.getLogger("football_edge.officials")

TFF_TEAMS_PATH = Path("config/tff_teams.yaml")
ISTANBUL = ZoneInfo("Europe/Istanbul")
# 0015'in `check (length(referee) between 1 and 80)`ü ve şemanın `$defs.person`ı. `verify-snapshot`
# H2c işaretleri burada da reddedilir: bozuk bir ad ilk kez dışa aktarımda görülürse BÜTÜN site
# durur.
REFEREE_MAX = 80
_UNSAFE = ("http", "<", ">")
_TOP_KEYS = frozenset({"league_label_contains", "league_id", "teams"})

_CANDIDATES = (
    "SELECT id, home_team, away_team, commence_time FROM matches "
    "WHERE league_id = %s AND commence_time >= %s AND commence_time < %s"
)
_LATEST = (
    "SELECT DISTINCT ON (match_id) match_id, referee FROM match_officials "
    "WHERE match_id = ANY(%s) ORDER BY match_id, seen_at DESC, id DESC"
)
_INSERT = "INSERT INTO match_officials (match_id, referee, seen_at) VALUES (%s, %s, %s)"

_Key = tuple[str, str, date]  # (API ev adı, API deplasman adı, İstanbul günü)


@dataclass(frozen=True)
class TeamMap:
    league_label_contains: str  # bu metni İÇEREN TFF lig bloğu işlenir
    league_id: str  # `matches.league_id` hedefi
    teams: Mapping[str, str | None]  # normalise_team(TFF adı) → API adı | None

    def matches_league(self, label: str) -> bool:
        """Etiket `league_label_contains`ı TAM ifade olarak taşır ("Süper Ligi" eşleşmez) ve
        kadın/genç ligi bloğu değildir (controller düzeltmesi C1)."""
        folded = label.casefold()
        if any(word in folded for word in _EXCLUDED_LEAGUE_WORDS):
            return False
        phrase = re.escape(self.league_label_contains.casefold()) + r"(?!\w)"
        return re.search(phrase, folded) is not None


@dataclass(frozen=True)
class Assignment:
    league: str  # TFF lig bloğunun etiketi
    home: str  # TFF yazımı
    away: str
    referee: str
    match_date: date  # TFF'nin (İstanbul) tarihi


@dataclass(frozen=True)
class Candidate:
    match_id: str
    home: str  # API yazımı
    away: str
    commence_time: datetime


@dataclass(frozen=True)
class LinkPlan:
    links: tuple[tuple[str, str], ...]  # (match_id, referee), match_id sırasıyla
    not_in_db: int
    awaiting_alias: int
    other_league: int


@dataclass(frozen=True)
class LinkResult:
    linked: int
    written: int
    not_in_db: int
    awaiting_alias: int
    other_league: int


def load_team_map(path: Path = TFF_TEAMS_PATH) -> TeamMap:
    """Biçim dışı her dosya `ValueError`dır; mesaj yolu ve kuralı adlandırır."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != _TOP_KEYS:
        raise ValueError(f"{path}: üst anahtarlar {sorted(_TOP_KEYS)} olmalı")
    label, league_id, teams = raw["league_label_contains"], raw["league_id"], raw["teams"]
    if not (isinstance(label, str) and label and isinstance(league_id, str) and league_id):
        raise ValueError(f"{path}: league_label_contains ve league_id boş olmayan metin olmalı")
    if not isinstance(teams, dict) or not teams:
        raise ValueError(f"{path}: teams boş olmayan bir eşleme olmalı")
    return TeamMap(label, league_id, _checked_teams(path, teams))


def _checked_teams(path: Path, teams: Mapping[Any, Any]) -> dict[str, str | None]:
    for key, value in teams.items():
        if not isinstance(key, str) or normalise_team(key) != key:
            raise ValueError(f"{path}: anahtar normalise_team çıktısı değil: {key!r}")
        if value is not None and not (isinstance(value, str) and value.strip()):
            raise ValueError(f"{path}: {key!r} değeri null ya da boş olmayan metin olmalı")
    return {str(key): value for key, value in teams.items()}


def istanbul_day(moment: datetime) -> date:
    """`commence_time`ın Europe/Istanbul takvim günü; saat dilimsiz an reddedilir."""
    if moment.utcoffset() is None:
        raise ValueError("istanbul_day saat dilimi taşımayan datetime kabul etmez")
    return moment.astimezone(ISTANBUL).date()


def assignment_of(entry: Observation) -> Assignment:
    payload = entry.payload
    return Assignment(
        str(payload["league"]),
        str(payload["home_team"]),
        str(payload["away_team"]),
        str(payload["referee"]),
        date.fromisoformat(str(payload["match_date"])),
    )


def plan_links(
    assignments: Sequence[Assignment],
    candidates: Sequence[Candidate],
    team_map: TeamMap,
) -> LinkPlan:
    """Saf eşleme (spec §4): DB yok, saat yok. Kırmızı `ContractViolation`dır; sayaçlar loglanır."""
    index = _index(candidates)
    links: dict[str, str] = {}
    not_in_db = awaiting = other = 0
    for item in assignments:
        if not team_map.matches_league(item.league):
            other += 1
            continue
        _check_referee(item)
        home, away = _api_name(item.home, item, team_map), _api_name(item.away, item, team_map)
        if home is None or away is None:
            awaiting += 1
            continue
        found = index.get((home, away, item.match_date), ())
        if len(found) > 1:
            raise ContractViolation(
                f"tff: {item.home} – {item.away} ({item.match_date}) için {len(found)} maç "
                f"({', '.join(sorted(found))}) — aynı İstanbul gününde birden çok eşleşme"
            )
        if not found:
            not_in_db += 1
            _warn_if_reversed(index, (home, away), item)
            continue
        links = _with_link(links, found[0], item.referee)
    return LinkPlan(tuple(sorted(links.items())), not_in_db, awaiting, other)


def _check_referee(item: Assignment) -> None:
    text = item.referee
    if not 1 <= len(text) <= REFEREE_MAX or any(mark in text.lower() for mark in _UNSAFE):
        raise ContractViolation(
            f"tff: {item.home} – {item.away} hakem metni sözleşme dışı "
            f"(1–{REFEREE_MAX} karakter, bağlantı/işaretleme yok)"
        )


def _api_name(tff_name: str, item: Assignment, team_map: TeamMap) -> str | None:
    key = normalise_team(tff_name)
    if key not in team_map.teams:
        raise ContractViolation(
            f"tff: {tff_name!r} ({item.league}) {TFF_TEAMS_PATH} teams'te yok — yapılandırma "
            f"eksiği; düzeltme: YAML'a satır (anahtar {key!r})"
        )
    return team_map.teams[key]


def _index(candidates: Sequence[Candidate]) -> dict[_Key, tuple[str, ...]]:
    index: dict[_Key, tuple[str, ...]] = {}
    for candidate in candidates:
        key = (candidate.home, candidate.away, istanbul_day(candidate.commence_time))
        index[key] = (*index.get(key, ()), candidate.match_id)
    return index


def _warn_if_reversed(
    index: Mapping[_Key, tuple[str, ...]], names: tuple[str, str], item: Assignment
) -> None:
    """Ters sırayla var olan maç tahminle bağlanmaz, ama haftalarca sessizce kaybolmasın."""
    home, away = names
    if index.get((away, home, item.match_date)):
        LOGGER.warning(
            "tff: %s – %s (%s) DB'de ters ev/deplasman sırasıyla var — bağlanmadı",
            item.home,
            item.away,
            item.match_date.isoformat(),
        )


def _with_link(links: Mapping[str, str], match_id: str, referee: str) -> dict[str, str]:
    known = links.get(match_id)
    if known is not None and known != referee:
        raise ContractViolation(
            f"tff: aynı maç ({match_id}) bu turda iki farklı hakemle — {known!r} / {referee!r}"
        )
    return {**links, match_id: referee}


def pending_writes(
    links: Sequence[tuple[str, str]], latest: Mapping[str, str], now: datetime
) -> tuple[tuple[str, str, datetime], ...]:
    """Değişiklik kaydı: maçın SON kayıtlı hakemi farklıysa ya da hiç yoksa bir satır."""
    return tuple(
        (match_id, referee, now) for match_id, referee in links if latest.get(match_id) != referee
    )


def find_candidates(
    conn: psycopg.Connection[Any], league_id: str, days: Sequence[date]
) -> tuple[Candidate, ...]:
    """Verilen İstanbul günlerini kapsayan aralıktaki maçlar; sınırlar İstanbul gece yarısıdır."""
    if not days:
        return ()
    start = datetime.combine(min(days), time(0), tzinfo=ISTANBUL)
    end = datetime.combine(max(days) + timedelta(days=1), time(0), tzinfo=ISTANBUL)
    with conn.cursor() as cur:
        cur.execute(_CANDIDATES, (league_id, start, end))
        rows = cur.fetchall()
    return tuple(Candidate(str(row[0]), str(row[1]), str(row[2]), row[3]) for row in rows)


def _latest_referees(conn: psycopg.Connection[Any], match_ids: Sequence[str]) -> dict[str, str]:
    if not match_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(_LATEST, (list(match_ids),))
        return {str(row[0]): str(row[1]) for row in cur.fetchall()}


def link_officials(
    conn: psycopg.Connection[Any],
    observations: Sequence[Observation],
    *,
    team_map: TeamMap,
    now: datetime,
) -> LinkResult:
    """Turun ayrıştırılmış sonucunu bağlar ve değişeni `match_officials`e yazar; commit eder."""
    assignments = tuple(assignment_of(entry) for entry in observations)
    days = sorted(
        {item.match_date for item in assignments if team_map.matches_league(item.league)}
    )
    plan = plan_links(assignments, find_candidates(conn, team_map.league_id, days), team_map)
    latest = _latest_referees(conn, [match_id for match_id, _ in plan.links])
    rows = pending_writes(plan.links, latest, now)
    if rows:
        with conn.cursor() as cur:
            cur.executemany(_INSERT, rows)
    conn.commit()
    return LinkResult(
        len(plan.links), len(rows), plan.not_in_db, plan.awaiting_alias, plan.other_league
    )
```

`src/football_edge/collectors/tff.py` — import bloğuna (`:30-33`, `observations` satırından önce):
```python
from football_edge.officials import TFF_TEAMS_PATH, link_officials, load_team_map
```
`collect_tff` (`:223-255`) şöyle olur (docstring'in sonuna bir paragraf: "Gözlemler yazılıp commit edildikten
sonra AYNI `now` ile `link_officials` çağrılır (spec 2026-10-02 §3.3): bağlama turun ayrıştırılmış sonucundan
çalışır, gözlem tablosunu okumaz. Sayıları loglanır; yapılandırma ya da eşleme kırmızısı istisnadır."):
```python
def collect_tff(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    *,
    sources_path: Path,
    robots_dir: Path,
    now: datetime,
    teams_path: Path = TFF_TEAMS_PATH,
) -> int:
    source = _enabled_source(sources_path)
    parser = robots_for(source, robots_dir)
    body = fetch_text(client, source, REFEREE_PATH, parser, expect="text/html", encoding=ENCODING)
    parsed = parse_referees(body, observed_at=now)
    if not parsed:
        # `parse_referees` boş sonucu YALNIZ her satır meşru olarak görevlisizken döner
        # (sıfır satır ve açıklanamayan her satır fırlatır) ve sayıyı kendisi loglar.
        # `minimum_rows=5` burada uygulanırsa atanmamış hafta yeniden kırmızıya düşer.
        return 0
    assert_schema(
        parsed,
        source_id=SOURCE_ID,
        required=frozenset({"home_team", "away_team", "referee", "match_date"}),
        minimum_rows=5,
    )
    written = write_observations(conn, parsed)
    conn.commit()
    result = link_officials(conn, parsed, team_map=load_team_map(teams_path), now=now)
    LOGGER.info(
        "%s: hakem bağlama — bağlanan %d, yeni yazılan %d, DB'de yok %d, alias bekleyen %d, "
        "lig dışı %d",
        SOURCE_ID,
        result.linked,
        result.written,
        result.not_in_db,
        result.awaiting_alias,
        result.other_league,
    )
    return written
```
(Docstring mevcut metni + eklenen paragrafla `def`in hemen altında kalır.)

`verify.sh:161`: `    EXPECTED_MIN_SITEDB=37` → `    EXPECTED_MIN_SITEDB=40`.
`scripts/sandbox_db.sh` `DEFAULT_TESTS` ikinci satırı:
```bash
  tests/test_site_views_db.py tests/test_site_officials_db.py tests/test_site_e2e_db.py)
```

- [ ] **Step 6: Koş — yeşil**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_officials.py tests/test_tff.py tests/test_collect_fetch_commands.py tests/test_site_harness_rules.py -q -rs`
Expected: hepsi geçer + 1 adlı SKIP (canlı ad testi).
Run: `uv run mypy src scripts` → `Success`. `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -m sitedb --collect-only 2>&1 | grep -oE '^[0-9]+/'` → `40/`.
Kum havuzu: `FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_officials_db.py tests/test_site_views_db.py` → hepsi geçer (Docker yoksa adıyla yazılır).

- [ ] **Step 7: Mutasyon kanıtı (dört)**

(a) Gün UTC'ye kayarsa:
```bash
F=src/football_edge/officials.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'return moment.astimezone(ISTANBUL).date()' 'return moment.date()'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_officials.py -q -k "istanbul_calendar or utc_day"; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1` (01:00 parametresi ve `utc_day`); `GERI-KONDU`.

(b) Değişiklik kaydı her turda yazarsa:
```bash
F=src/football_edge/officials.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'if latest.get(match_id) != referee' 'if latest is not None'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_officials.py -q -k changed_or_first; echo "exit=$?"
FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_officials_db.py -k not_recorded_twice; echo "db-exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`; kum havuzunda `db-exit=1`; `GERI-KONDU`.

(c) SON kayıt yerine İLK kayıt (yalnız DB):
```bash
F=src/football_edge/officials.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'ORDER BY match_id, seen_at DESC, id DESC' 'ORDER BY match_id, seen_at ASC, id ASC'
FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_officials_db.py -k three_rows; echo "db-exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `db-exit=1` (üçüncü tur ilk kayıtla aynı sanılır → 2 satır); `GERI-KONDU`. Docker yoksa adıyla "koşmadı".

(d) Aday aralığı UTC gününe kayarsa (yalnız DB):
```bash
F=src/football_edge/officials.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'start = datetime.combine(min(days), time(0), tzinfo=ISTANBUL)' 'start = datetime.combine(min(days), time(0), tzinfo=ZoneInfo("UTC"))'
FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_officials_db.py -k istanbul_day; echo "db-exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `db-exit=1` (`m-gece` düşer); `GERI-KONDU`.

(e) Toplama aynı `now`u geçirmezse:
```bash
F=src/football_edge/collectors/tff.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'team_map=load_team_map(teams_path), now=now)' 'team_map=load_team_map(teams_path), now=now.replace(microsecond=1))'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_tff.py -q -k same_now; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`; `GERI-KONDU`.

- [ ] **Step 8: Commit**

```bash
uv run ruff format src tests scripts
git add src/football_edge/officials.py src/football_edge/collectors/tff.py tests/test_officials.py tests/test_tff.py tests/test_site_officials_db.py verify.sh scripts/sandbox_db.sh
git commit -F - <<'EOF'
feat: TFF baş hakemini maça bağla ve değişikliği kaydet (link_officials)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 9: TAM KAPI**

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh > "$T/verify.log" 2>&1; grep -E "^(PASS|FAIL|SKIP)|KAPI" "$T/verify.log"
```
Expected: `FAIL:` yok; üç adlı SKIP; `KAPI YEŞİL`.

---

### Task 5: Anlık görüntüye `referee` — dışa aktarım, döküm, türetim, şema, TS tipi, fixture'lar

Sözleşme değişikliği tek parçadır: şemada zorunlu alan, onu taşımayan her fixture'ı, TS tipini ve dışa aktarımı aynı
commit'te kırar — ayrı görevlere bölünemez.

**Files:**
- Modify: `src/football_edge/site/inputs.py:65-71` (`MatchRow`), `:199-201` (`_match`)
- Modify: `src/football_edge/site/export.py:72-80` (`_OFFICIALS`), `:332-358` (`_dump`)
- Modify: `src/football_edge/site/derive.py:210-211` (`_match_json`)
- Modify: `web/contract/snapshot.schema.json:85`, `:94`, `:172`
- Modify: `web/src/lib/snapshot-types.ts:61-75`
- Modify: `tests/site_web_fixtures.py:7-11`, `:66-84`, `:97-141` → yeniden üret `web/fixtures/snapshot.fixture.web-full.json`, `web/fixtures/snapshot.fixture.web-empty.json`
- Modify (betik): `web/fixtures/snapshot.fixture.json`, `web/fixtures/snapshot.fixture-record.json`
- Modify: `tests/fake_site_db.py:20-35`, `:48-53` (altına yöntem), `:124-129` (dal)
- Modify: `tests/site_builders.py:11-12` (import), `:144-166` (`export_dump`)
- Test: `tests/test_site_derive.py`, `tests/test_site_export.py`, `tests/test_site_verify.py` (dosya sonlarına), `tests/test_site_contract.py:58-75`, `tests/test_site_e2e_db.py:55-63`, `:99-197`, `:208-216`
- `verify.py`, `contract.py`, `__main__.py`, `schema.py`: değişmez (H2c her dizeyi zaten tarar — test aşağıda kanıtlar).

**Interfaces:**
- Consumes: Görev 3 `site.match_officials(match_id text, referee text)`.
- Produces: `MatchRow(id, league_id, commence_time, home, away, referee: str | None)`; döküm maç satırı 6 kolon `[id, league_id, commence_time, home, away, referee|null]` (`DUMP_VERSION` 1 kalır: döküm diske yazılmaz, iki türetim aynı commit'in kodudur); anlık görüntü maç nesnesi `"referee": str | null` (zorunlu); `$defs.person`; TS `Match.referee: string | null`; `FakeSiteDb.officials: Sequence[tuple[str, str, datetime, int]]` (match_id, referee, seen_at, id); `export_dump(..., referees: Mapping[str, str] | None = None)`.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_site_derive.py` sonuna:
```python
def test_a_match_carries_its_referee_or_null() -> None:
    """Spec 2026-10-02 §6: hakem dökümden aynen; hakemsiz maç `null` (yer tutucu yok)."""
    body = _body(ROUNDS, referees={mid(1): "Deneme Hakem"})

    assert _match(body, 1)["referee"] == "Deneme Hakem"
    assert _match(body, 2)["referee"] is None


def test_a_referee_that_is_not_text_in_the_dump_is_a_named_error() -> None:
    dump = export_dump(
        leagues=[LEAGUE], matches=MATCHES, rounds=ROUNDS, referees={mid(1): "Deneme Hakem"}
    )

    with pytest.raises(ValueError, match="hakem metin değil"):
        load_inputs(dump.replace('"Deneme Hakem"', "7"))
```
`tests/test_site_export.py` sonuna:
```python
def test_the_export_carries_the_last_referee_seen_before_kickoff(tmp_path: Path) -> None:
    """`site.match_officials` aynı işlemde okunur; başlama anındaki atama görünmez (taklit görünüm)."""
    db = _db(
        officials=[
            (M1, "Önce Hakem", at("2026-09-20T09:00:00Z"), 1),
            (M1, "Son Hakem", at("2026-09-21T09:00:00Z"), 2),
            (M2, "Geç Hakem", at("2026-09-23T15:00:00Z"), 3),
        ]
    )
    out = _export(db, tmp_path)
    snapshot = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))

    assert {match["id"]: match["referee"] for match in snapshot["matches"]} == {
        M1: "Son Hakem",
        M2: None,
    }
    assert any(q.startswith("SELECT match_id, referee FROM site.match_officials") for q in db.queries)
```
`tests/test_site_verify.py` sonuna:
```python
@pytest.mark.parametrize("text", ["http://x.invalid", "a<b", "a>b"])
def test_a_referee_carrying_a_link_or_markup_is_red(text: str) -> None:
    """H2c yeni alanı da tarar (verify.py değişmeden)."""
    errors = _broken(_set("matches.0.referee", text))

    assert any("$.matches[0].referee: bağlantı ya da işaretleme" in e for e in errors), errors


@pytest.mark.parametrize(
    ("value", "needle"),
    [
        ("", "1 karakterden kısa"),
        ("x" * 81, "80 karakterden uzun"),
        (7, "tip ['string', 'null'] bekleniyordu"),
    ],
)
def test_a_referee_outside_the_person_shape_is_red(value: object, needle: str) -> None:
    errors = _broken(_set("matches.0.referee", value))

    assert any(e.startswith("$.matches[0].referee: ") and needle in e for e in errors), errors


def test_a_match_without_the_referee_key_is_red() -> None:
    def drop(snapshot: dict[str, Any]) -> None:
        del snapshot["matches"][0]["referee"]

    errors = _broken(drop)

    assert "$.matches[0]: zorunlu 'referee' yok" in errors, errors
```
`tests/test_site_contract.py` — `test_the_fixtures_carry_every_variant_the_site_must_render` sonuna (`:75`'ten sonra):
```python
    assert any(match["referee"] is None for match in matches), "hakemsiz maç yok"
    assert any(isinstance(match["referee"], str) for match in matches), "hakemli maç yok"
```

- [ ] **Step 2: Koş — kırmızı**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_derive.py tests/test_site_export.py tests/test_site_verify.py tests/test_site_contract.py -q -k "referee or every_variant"`
Expected: `TypeError: export_dump() got an unexpected keyword argument 'referees'` (derive), `TypeError: … unexpected keyword argument 'officials'` (export), verify H2c/biçim testleri `AssertionError` (alan şemada yok: hata yolu `<bilinmeyen anahtar #…>`, iletiler `bilinmeyen anahtar`), `drop` testi ve contract varyant testi `KeyError: 'referee'`.

- [ ] **Step 3: En küçük uygulama — Python**

`src/football_edge/site/inputs.py` `MatchRow` (`:65-71`):
```python
@dataclass(frozen=True)
class MatchRow:
    id: str
    league_id: str
    commence_time: datetime
    home: str
    away: str
    referee: str | None  # TFF baş hakemi (`site.match_officials`, spec 2026-10-02); yoksa None
```
`_match` (`:199-201`):
```python
def _match(row: Sequence[Any]) -> MatchRow:
    match_id, league_id, commence_time, home, away, referee = row
    if referee is not None and not isinstance(referee, str):
        raise ValueError("dökümde hakem metin değil")
    return MatchRow(
        str(match_id), str(league_id), _time(commence_time), str(home), str(away), referee
    )
```
`src/football_edge/site/export.py` — `_RECORD` tanımının (`:77-80`) altına:
```python
# Spec 2026-10-02 §5–6: maç başına başlamadan önce görülen SON atama (görünüm süzer).
_OFFICIALS = "SELECT match_id, referee FROM site.match_officials ORDER BY match_id"
```
`_dump` (`:325-360`) şöyle olur:
```python
def _dump(
    conn: psycopg.Connection[Any],
    cut: LedgerCut,
    anchor: Anchor,
    method: str,
    league_slugs: Mapping[str, str],
) -> str:
    with conn.cursor() as cur:
        leagues = _all(cur, _LEAGUES)
        matches = _all(cur, _MATCHES)
        quotes = _all(cur, _QUOTES, (cut.last_id,))
        record = _all(cur, _RECORD)
        referees = {str(row[0]): str(row[1]) for row in _all(cur, _OFFICIALS)}
    quoted = {row[1] for row in quotes}
    shown = [row for row in matches if row[0] in quoted]
    if anchor.rows > 0 and not shown:
        raise ExportRefused(EXIT_SITE_CUT, "defterde satır var ama maç kümesi boş")
    if any(row[2] < PUBLIC_FLOOR for row in matches):
        raise ExportRefused(EXIT_SITE_CUT, "görünüm tabandan eski bir maç döndürdü (H1)")
    unslugged = sorted(str(row[0]) for row in leagues if row[0] not in league_slugs)
    if unslugged:
        raise ExportRefused(
            EXIT_SITE_CONFIG,
            "config/site_leagues.yaml'da slug'ı olmayan lig: " + ", ".join(unslugged),
        )
    return dump_text(
        config=DumpConfig(
            method, SITE_MIN_BOOKS, SITE_MIN_TEAM_MATCHES, MOVE_MIN_MATCHES, PATH_ID_LENGTH
        ),
        floor=PUBLIC_FLOOR,
        ledger=cut,
        anchor=AnchorValue(anchor.path.name, anchor.rows, anchor.last_id, anchor.head),
        leagues=[(*row, league_slugs[str(row[0])]) for row in leagues],
        matches=[(*row, referees.get(str(row[0]))) for row in matches],
        quotes=quotes,
        record=record,
    )
```
`src/football_edge/site/derive.py` `_match_json` — `"away": row.away,` satırının (`:211`) altına:
```python
        "referee": row.referee,
```
`tests/fake_site_db.py` — alanlar (`:25`ten sonra, `record` satırının altına):
```python
    # 0015 `public.match_officials` satırları: (match_id, referee, seen_at, id)
    officials: Sequence[tuple[str, str, datetime, int]] = ()
```
`h2h_quotes` yönteminden (`:55`) önce:
```python
    def site_match_officials(self) -> list[tuple[str, str]]:
        """0015 `site.match_officials`: tabandaki maçta başlamadan ÖNCE görülen SON hakem."""
        kickoffs = {row[0]: row[2] for row in self.site_matches()}
        latest: dict[str, tuple[datetime, int, str]] = {}
        for match_id, referee, seen_at, row_id in self.officials:
            kickoff = kickoffs.get(match_id)
            if kickoff is None or not seen_at < kickoff:
                continue
            if match_id not in latest or (seen_at, row_id) > latest[match_id][:2]:
                latest[match_id] = (seen_at, row_id, referee)
        return sorted((match_id, value[2]) for match_id, value in latest.items())
```
`_Cursor.execute`te `elif "FROM site_input.h2h_quotes" in text:` dalının (`:126`) önüne:
```python
        elif text.startswith("SELECT match_id, referee FROM site.match_officials"):
            self._result = list(db.site_match_officials())
```
`tests/site_builders.py` — import (`:11-12`): `from collections.abc import Mapping, Sequence`; `export_dump` (`:144-166`):
```python
def export_dump(
    *,
    leagues: Sequence[tuple[str, str, str, str]],  # id, ad, ülke, site slug'ı
    matches: Sequence[tuple[str, str, str, str, str]],
    rounds: Sequence[Round],
    record: Sequence[tuple[Any, ...]] = (),
    method: str = "power",
    referees: Mapping[str, str] | None = None,  # match_id → `site.match_officials` hakemi
) -> str:
    """Dışa aktarımın üreteceği döküm METNİ (`dump_text`), DB'siz."""
    quotes = quote_rows(rounds)
    last_id = len(quotes)
    named = referees or {}
    return dump_text(
        config=DumpConfig(
            method, SITE_MIN_BOOKS, SITE_MIN_TEAM_MATCHES, MOVE_MIN_MATCHES, PATH_ID_LENGTH
        ),
        floor=PUBLIC_FLOOR,
        ledger=LedgerCut(last_id, last_id, "c" * 64),
        anchor=AnchorValue("head-2026-09-21.txt", last_id, last_id, "c" * 64),
        leagues=leagues,
        matches=[
            (mid, league, at(when), home, away, named.get(mid))
            for mid, league, when, home, away in matches
        ],
        quotes=quotes,
        record=record,
    )
```

- [ ] **Step 4: En küçük uygulama — şema ve TS tipi**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
from pathlib import Path

path = Path("web/contract/snapshot.schema.json")
text = path.read_text(encoding="utf-8")
edits = [
    ('"home", "away", "sealed", "rounds"', '"home", "away", "referee", "sealed", "rounds"'),
    (
        '          "away": {"$ref": "#/$defs/label"},\n',
        '          "away": {"$ref": "#/$defs/label"},\n          "referee": {"$ref": "#/$defs/person"},\n',
    ),
    (
        '    "points": {',
        '    "person": {"description": "Süper Lig maçında TFF\'nin maç başlamadan önce açıkladığı baş hakem adı; '
        'yoksa null (H2b genişlemesi, docs/superpowers/specs/2026-10-02-tff-hakem-site-design.md §6).", '
        '"type": ["string", "null"], "minLength": 1, "maxLength": 80},\n    "points": {',
    ),
]
for old, new in edits:
    assert text.count(old) == 1, old
    text = text.replace(old, new)
path.write_text(text, encoding="utf-8")
PY
```
`web/src/lib/snapshot-types.ts` `Match` (`:61-75`) — `  away: string;` satırının altına:
```ts
  referee: string | null;
```

- [ ] **Step 5: En küçük uygulama — fixture'lar**

`tests/site_web_fixtures.py`:
- Belge (`:7-11`) "Kapsanan durumlar" cümlesinin sonuna: `· hakemli (iki maç) ve hakemsiz maç (spec 2026-10-02 §6)`.
- `_match` döndürdüğü sözlükte `"away": away_name,` satırının altına: `"referee": rest.get("referee"),`
- `_matches()`ta `_match(1, …` çağrısına `indexable=True,` satırından sonra `referee="Deniz Örnek",`; `_match(3, …`
  çağrısına `indexable=False,` satırından sonra `referee="Ayşe Yılmaz",`.

Yeniden üret ve B-1 fixture'larını güncelle:
```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -m tests.site_web_fixtures
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
import json
import re
from pathlib import Path

from football_edge.site.contract import content_sha256

for name in ("snapshot.fixture.json", "snapshot.fixture-record.json"):
    path = Path("web/fixtures") / name
    lines = path.read_text(encoding="utf-8").split("\n")
    out, first = [], True
    for line in lines:
        if re.search(r'"path_id": "[0-9a-z]{12}", "rounds": ', line):
            value = '"Deneme Hakem"' if first else "null"
            line = line.replace(', "rounds": ', f', "referee": {value}, "rounds": ', 1)
            first = False
        out.append(line)
    text = "\n".join(out)
    document = json.loads(text)
    old = re.search(r'"content_sha256": "([0-9a-f]{64})"', text).group(1)
    text = text.replace(old, content_sha256(document), 1)
    path.write_text(text, encoding="utf-8")
    print(name, sum("referee" in match for match in document["matches"]))
PY
```
Expected: `web/fixtures/snapshot.fixture.web-full.json`, `web/fixtures/snapshot.fixture.web-empty.json`, sonra
`snapshot.fixture.json 8`, `snapshot.fixture-record.json 8`.

- [ ] **Step 6: En küçük uygulama — uçtan uca test (`tests/test_site_e2e_db.py`)**

`MATCHES` listesinin (`:55-63`) altına:
```python
# 0015 tohumları (spec 2026-10-02): M1'in ataması başlamadan önce (görünür), M2'ninki başlama ANINDA
# (görünmez → null), holdout maçınınki taban altında (görünmez).
OFFICIALS = (
    (M1, "Deneme Hakem", "2026-09-21T09:00:00Z"),
    (M2, "Geç Hakem", "2026-09-23T15:00:00Z"),
    (HOLDOUT, "Eski Hakem", "2026-01-14T09:00:00Z"),
)
```
`_seed`te `cur.executemany(… MATCHES)` çağrısının altına:
```python
        cur.executemany(
            "INSERT INTO match_officials (match_id, referee, seen_at) VALUES (%s, %s, %s)", OFFICIALS
        )
```
`EXPECTED_MATCHES`a (`:99-197`) dört satır:
```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
from pathlib import Path

path = Path("tests/test_site_e2e_db.py")
text = path.read_text(encoding="utf-8")
for away, referee in (
    ('"away": "Taban B",\n', "None"),
    ('"away": "Beta FK",\n        "sealed": True,\n        "rounds": 3,', '"Deneme Hakem"'),
    ('"away": "Alfa Spor",\n', "None"),
    ('"away": "Beta FK",\n        "sealed": False,', "None"),
):
    assert text.count(away) == 1, away
    head = away.split("\n")[0] + "\n"
    text = text.replace(away, head + f'        "referee": {referee},\n' + away[len(head):], 1)
path.write_text(text, encoding="utf-8")
PY
```
(Dört eşleşme sırasıyla FLOOR, M1, M2, M3 sözlükleridir; betik her biri TEK eşleşmede durur.)

- [ ] **Step 7: Koş — yeşil**

Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -m "not sitedb" -k "site" --tb=short`
Expected: hepsi geçer (`test_site_web_contract.py` TS ↔ şema `referee: string | null` eşitliği ve üretici eşliği dahil).
Run: `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; pnpm -C web exec tsc --noEmit && pnpm -C web exec vitest run`
Expected: tip hatası yok; bütün vitest testleri geçer.
Kum havuzu: `FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_e2e_db.py` → geçer (Docker yoksa adıyla).

- [ ] **Step 8: Mutasyon kanıtı (üç)**

(a) Dışa aktarım hakemi düşürürse:
```bash
F=src/football_edge/site/export.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" 'matches=[(*row, referees.get(str(row[0]))) for row in matches],' 'matches=[(*row, None) for row in matches],'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_export.py -q -k referee; echo "exit=$?"
FE_SANDBOX_PREFIX=fe-tff-hakem FE_SANDBOX_PORT=55620 scripts/sandbox_db.sh test tests/test_site_e2e_db.py -k hand_computed; echo "db-exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`; kum havuzunda `db-exit=1`; `GERI-KONDU`.

(b) Türetim hakemi yazmazsa:
```bash
F=src/football_edge/site/derive.py; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" '"referee": row.referee,' '"referee": None,'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_derive.py -q -k referee; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`; `GERI-KONDU`.

(c) Şema alanı zorunlu olmazsa:
```bash
F=web/contract/snapshot.schema.json; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" '"away", "referee", "sealed"' '"away", "sealed"'
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_site_verify.py -q -k without_the_referee_key; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`; `GERI-KONDU`.

- [ ] **Step 9: Commit**

```bash
uv run ruff format src tests scripts
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; pnpm -C web exec biome check --write src/lib/snapshot-types.ts
git add src/football_edge/site/inputs.py src/football_edge/site/export.py src/football_edge/site/derive.py web/contract/snapshot.schema.json web/src/lib/snapshot-types.ts tests/site_web_fixtures.py web/fixtures/snapshot.fixture.web-full.json web/fixtures/snapshot.fixture.web-empty.json web/fixtures/snapshot.fixture.json web/fixtures/snapshot.fixture-record.json tests/fake_site_db.py tests/site_builders.py tests/test_site_derive.py tests/test_site_export.py tests/test_site_verify.py tests/test_site_contract.py tests/test_site_e2e_db.py
git commit -F - <<'EOF'
feat: anlık görüntüye maç hakemi (referee) — dışa aktarım, şema, TS tipi, fixture'lar

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 10: TAM KAPI**

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh > "$T/verify.log" 2>&1; grep -E "^(PASS|FAIL|SKIP)|KAPI" "$T/verify.log"
```
Expected: `FAIL:` yok (`site-tip`, `site-test`, `site-derleme`, `site-uyum` PASS — fixture derlemesi hakemli JSON'u okur); üç adlı SKIP; `KAPI YEŞİL`. (İnceleme: kabuk taşıyan bağımsız inceleyici.)

---

### Task 6: Maç sayfasında hakem satırı; sözlükler; check-out ad listesi; okuyucu bekçisi

**Files:**
- Create: `web/src/components/RefereeLine.tsx`, Test: `web/src/components/RefereeLine.test.tsx`
- Modify: `web/src/app/[lang]/[league]/match/[pathId]/[slug]/page.tsx:9` (import), `:67-70` (satır)
- Modify: `web/src/i18n/en.json:45`, `web/src/i18n/tr.json:45`, Test: `web/src/i18n/dict.test.ts:24` (altına)
- Modify: `web/scripts/checkout/numbers.ts:85-89`, Test (Create): `web/scripts/checkout/referee.test.ts`
- Modify: `web/src/lib/snapshot.ts:96-124`, Test: `web/src/lib/snapshot.test.ts:63` (listenin sonuna)

**Interfaces:**
- Consumes: Görev 5 `Match.referee: string | null`; `t(lang: Lang, key: DictKey): string`; `numberFindings(snapshot, page, html): string[]`; `expectedPages(snapshot): ExpectedPage[]`.
- Produces: `RefereeLine({ name, lang }: { name: string | null; lang: Lang })` — null → `null`; aksi → `<p>{t(lang, "match.referee") yuvası doldurulmuş}</p>`; sözlük anahtarı `match.referee`.

- [ ] **Step 1: Başarısız testleri yaz**

`web/src/components/RefereeLine.test.tsx`:
```tsx
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RefereeLine } from "./RefereeLine.tsx";

describe("RefereeLine (spec 2026-10-02 §6)", () => {
  it("dolu hakem: kaynağı adıyla tek satır, iki dilde", () => {
    expect(renderToString(<RefereeLine name="Deniz Örnek" lang="tr" />)).toBe(
      "<p>Hakem: Deniz Örnek (TFF ataması)</p>",
    );
    expect(renderToString(<RefereeLine name="Deniz Örnek" lang="en" />)).toBe(
      "<p>Referee: Deniz Örnek (TFF appointment)</p>",
    );
  });

  it("null: HİÇBİR şey çizilmez (yer tutucu, 'yakında' yok)", () => {
    expect(renderToString(<RefereeLine name={null} lang="tr" />)).toBe("");
  });

  it("adın içindeki $& değiştirme kalıbı yorumlanmaz, & kaçırılır", () => {
    expect(renderToString(<RefereeLine name="A $& B" lang="en" />)).toBe(
      "<p>Referee: A $&amp; B (TFF appointment)</p>",
    );
  });
});
```
`web/src/i18n/dict.test.ts` — `en boş sicil metni…` testinin (`:20-24`) altına:
```ts
  // spec 2026-10-02 §6: kaynak adıyla (TFF Kullanım Şartları kaynak gösterimi, §8); tek `{name}` yuvası.
  it("hakem satırı kaynağı adıyla taşır", () => {
    expect(en["match.referee"]).toBe("Referee: {name} (TFF appointment)");
    expect(tr["match.referee"]).toBe("Hakem: {name} (TFF ataması)");
  });
```
`web/scripts/checkout/referee.test.ts`:
```ts
// Check-out ad listesi hakemi taşır (spec 2026-10-02 §6): hakem adı veri metnidir, içindeki rakam bulgu değildir.
import { describe, expect, it } from "vitest";
import { fullFixture } from "../../src/lib/fixture.ts";
import { expectedPages } from "./expect.ts";
import { numberFindings } from "./numbers.ts";

const snapshot = fullFixture();
const match = snapshot.matches.find((each) => each.referee !== null);
if (!match) throw new Error("fixture hakemli maç taşımıyor");
const page = expectedPages(snapshot).find(
  (each) => each.id === `match:${match.id}` && each.lang === "en",
);
if (!page) throw new Error("hakemli maçın sayfası yok");

describe("check-out ad listesi hakemi taşır", () => {
  it("hakem adındaki rakam veri metnidir; yanına eklenen sayı kırmızı", () => {
    const named = {
      ...snapshot,
      matches: snapshot.matches.map((each) =>
        each.id === match.id ? { ...each, referee: "Ali 2 Veli" } : each,
      ),
    };
    expect(numberFindings(named, page, "<p>Referee: Ali 2 Veli (TFF appointment)</p>")).toEqual([]);
    expect(numberFindings(named, page, "<p>Referee: Ali 2 Veli (3)</p>")).toHaveLength(1);
  });
});
```
`web/src/lib/snapshot.test.ts` — ilk `it.each` listesinin sonuna (`["sicil girdisi nesne değil", …],` satırından sonra, `] as const)`tan önce):
```ts
    ["hakem anahtarı yok (bayat anlık görüntü)", ["matches", 0, "referee"], undefined],
    ["hakem boş metin", ["matches", 0, "referee"], ""],
    ["hakem sayı", ["matches", 0, "referee"], 7],
```

- [ ] **Step 2: Koş — kırmızı**

Run: `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; pnpm -C web exec vitest run src/components/RefereeLine.test.tsx src/i18n/dict.test.ts scripts/checkout/referee.test.ts src/lib/snapshot.test.ts`
Expected: `RefereeLine.tsx` çözülemiyor (Failed to resolve import); `dict.test.ts` `expected undefined to be 'Referee: …'`; `referee.test.ts` `data-fe dışında sayı "2"`; `snapshot.test.ts` üç yeni satır `expected [Function] to throw an error`.

- [ ] **Step 3: En küçük uygulama**

`web/src/components/RefereeLine.tsx`:
```tsx
// TFF'nin maç başlamadan önce açıkladığı baş hakem (spec 2026-10-02 §6; İz B H2b genişlemesi).
// `null` iken HİÇBİR şey çizilmez — yer tutucu, "yakında", tahmin yok (spec §1). Kaynak adıyla
// yazılır ("TFF ataması"): TFF Kullanım Şartları kaynak gösterimi ister (spec §8).
import type { Lang } from "../../site.config.ts";
import { t } from "../i18n/dict.ts";

export function RefereeLine({ name, lang }: { name: string | null; lang: Lang }) {
  if (name === null) return null;
  // Değiştirici FONKSİYON: ad `$&` gibi bir değiştirme kalıbı taşısa da harfiyen basılır.
  return <p>{t(lang, "match.referee").replace("{name}", () => name)}</p>;
}
```
`web/src/i18n/en.json` — `  "match.pending": "Pending",` satırının (`:45`) altına:
```json
  "match.referee": "Referee: {name} (TFF appointment)",
```
`web/src/i18n/tr.json` — `  "match.pending": "Bekleniyor",` satırının (`:45`) altına:
```json
  "match.referee": "Hakem: {name} (TFF ataması)",
```
`page.tsx` — import bloğunda `RoundsTable` satırının (`:8`) altına:
```tsx
import { RefereeLine } from "../../../../../../components/RefereeLine.tsx";
```
ve başlama anı paragrafının (`:67-70`) hemen altına (`<ValueBadge …/>`tan önce):
```tsx
      <RefereeLine name={match.referee} lang={lang} />
```
Dosyanın baş yorumunun (`:1-2`) sonuna: `// Süper Lig maçında TFF baş hakemi (spec 2026-10-02): yalnız ad ve kaynak; null ise satır yok.`
`web/scripts/checkout/numbers.ts` `match` dalı (`:85-89`):
```ts
    match: () => {
      const match = snapshot.matches.find((each) => each.id === id);
      const own = snapshot.leagues.find((each) => each.id === match?.league_id);
      // Hakem adı veri metnidir (spec 2026-10-02 §6): adındaki rakam bulgu değildir.
      const referee = match?.referee ? [match.referee] : [];
      return [...(own ? [own.name] : []), ...(match ? matchOf(match) : []), ...referee];
    },
```
`web/src/lib/snapshot.ts` — `label` fonksiyonunun (`:96-99`) altına:
```ts
// Hakem alanı ZORUNLUDUR: null ya da boş olmayan metin. Anahtarı taşımayan bayat bir anlık görüntü
// hakem satırını sessizce düşürürdü (spec 2026-10-02 §6, Review Focus 5).
function referee(row: Json, at: string): void {
  const value = row.referee;
  if (value !== null && (typeof value !== "string" || value === "")) {
    fail(`${at}.referee metin ya da null değil`);
  }
}
```
ve `checkShape`teki maç döngüsünde (`:121`) `label(...)` satırının altına:
```ts
    referee(match, `matches[${index}]`);
```

- [ ] **Step 4: Koş — yeşil**

Run: `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; pnpm -C web exec biome check --write src/components/RefereeLine.tsx src/components/RefereeLine.test.tsx "src/app/[lang]/[league]/match/[pathId]/[slug]/page.tsx" src/i18n/en.json src/i18n/tr.json src/i18n/dict.test.ts scripts/checkout/numbers.ts scripts/checkout/referee.test.ts src/lib/snapshot.ts src/lib/snapshot.test.ts && pnpm -C web exec tsc --noEmit && pnpm -C web exec vitest run`
Expected: biçim uygulanır; tip hatası yok; bütün vitest testleri geçer (`tr ve en aynı anahtar kümesini taşır` dahil).

- [ ] **Step 5: Mutasyon kanıtı (üç)**

(a) Değiştirme kalıbı:
```bash
F=web/src/components/RefereeLine.tsx; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" '.replace("{name}", () => name)' '.replace("{name}", name)'
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; pnpm -C web exec vitest run src/components/RefereeLine.test.tsx; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1` (`$&` testi); `GERI-KONDU`.

(b) Ad listesi:
```bash
F=web/scripts/checkout/numbers.ts; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" '...(match ? matchOf(match) : []), ...referee]' '...(match ? matchOf(match) : [])]'
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; pnpm -C web exec vitest run scripts/checkout/referee.test.ts; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1`; `GERI-KONDU`. (Biome sonrası satır sarılmışsa OLD, dosyadaki tek satırlık `return` metninden alınır.)

(c) Okuyucu bekçisi:
```bash
F=web/src/lib/snapshot.ts; B=$(mktemp -d); cp "$F" "$B/orig"
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'import pathlib,sys;p=pathlib.Path(sys.argv[1]);t=p.read_text(encoding="utf-8");assert t.count(sys.argv[2])==1,"OLD tekil değil";p.write_text(t.replace(sys.argv[2],sys.argv[3]),encoding="utf-8")' "$F" '    referee(match, `matches[${index}]`);
' ''
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; pnpm -C web exec vitest run src/lib/snapshot.test.ts; echo "exit=$?"
cp "$B/orig" "$F"; cmp "$B/orig" "$F" && echo GERI-KONDU
```
Expected: `exit=1` (üç hakem satırı); `GERI-KONDU`.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/RefereeLine.tsx web/src/components/RefereeLine.test.tsx "web/src/app/[lang]/[league]/match/[pathId]/[slug]/page.tsx" web/src/i18n/en.json web/src/i18n/tr.json web/src/i18n/dict.test.ts web/scripts/checkout/numbers.ts web/scripts/checkout/referee.test.ts web/src/lib/snapshot.ts web/src/lib/snapshot.test.ts
git commit -F - <<'EOF'
feat: maç sayfasında TFF baş hakemi satırı

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 7: TAM KAPI**

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh > "$T/verify.log" 2>&1; grep -E "^(PASS|FAIL|SKIP)|KAPI" "$T/verify.log"
```
Expected: `FAIL:` yok (`site-derleme` ve `site-uyum` hakemli fixture sayfalarını derler ve tarar); üç adlı SKIP; `KAPI YEŞİL`.

---

### Task 7: İz B spec değişikliği, DEFERRED, HANDOFF

**Files:**
- Modify: `docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md:34` (B7), `:64` (§1 kapsam dışı), `:90` (H1a), `:91` (H2b), `:507` (§7 içerik)
- Modify: `docs/DEFERRED.md:503` (9.6e notu), `:545` (9.7a, 9.7b)
- Modify: `docs/HANDOFF.md:253` (Adım 12 başlığı), `:262` (0015 maddesi), `:284` (0016)
- Modify: `docs/phases/06-site/HANDOFF.md:120` (Canlıya geçiş), `:248` (yeni "ölçmedikleri" bölümü), dosya sonu (C12)

**Interfaces:**
- Consumes: Görev 1–6'nın adları (`config/tff_teams.yaml`, `awaiting_alias`, `0015_match_officials.sql`, `tests/test_site_officials_db.py`, `test_every_mapped_api_name_was_seen_in_tur1`).
- Produces: doküman; kod arayüzü yok.

- [ ] **Step 1: Başarısız (bekçi) adımı — anchor'ların TEK olduğunu ölç**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
from pathlib import Path

checks = {
    "docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md": [
        "**Maç sayfası yalnız vig'i temizlenmiş piyasa konsensüs olasılığını gösterir** — kitap adı",
        "- Haber, sakatlık, kadro, hakem, hava, stadyum verisi — sitede HİÇBİR kaynak metni ya da oyuncu düzeyi bilgi yok",
        "= {`leagues`, `matches`, `odds_snapshots`} (ara `site.*` görünümleri",
        "serbest metin alanı yalnız takım adı, lig adı, ülke — tip ve uzunluk sınırlı",
        'mühür durumu ("kapanış kaydedildi" / "bekleniyor").',
    ],
    "docs/DEFERRED.md": [
        "Sınırlama `latest_observations` docstring'inde ve HANDOFF §3.9/31'de yazılı.\n",
        "toplayıcısı yeni bir iştir, sayfa şekli ölçülerek başlar. HANDOFF §3.9/30.\n",
    ],
    "docs/HANDOFF.md": [
        "**Adım 12 — 0014'ü canlıya uygula (K/3, 15 dk; asistan yapar, sen onaylarsın).**",
        "- Bitti: advisors'ta yeni ERROR/WARN yok; `site` şeması görünümleri canlıda; seal yeşil.\n",
        "(`0015_site_reader_login.sql`;",
    ],
    "docs/phases/06-site/HANDOFF.md": [
        "eklenmemiş, `security_invoker` uyarısı yok).\n",
        "## Hukuk incelemesi (HANDOFF §0.7/7'ye)\n",
    ],
}
for name, anchors in checks.items():
    text = Path(name).read_text(encoding="utf-8")
    for anchor in anchors:
        print(text.count(anchor), name, anchor[:60])
PY
```
Expected: her satır `1 …` ile başlar. (`0` ya da `2` görülürse belge başka bir oturumda değişmiştir — anchor dosyanın
GÜNCEL metninden yeniden alınır, değiştirme metni aynı kalır.)

- [ ] **Step 2: Belgeleri düzenle**

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
from pathlib import Path

SPEC = "docs/superpowers/specs/2026-10-02-tff-hakem-site-design.md"
edits = {
    "docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md": [
        (
            "**Maç sayfası yalnız vig'i temizlenmiş piyasa konsensüs olasılığını gösterir** — kitap adı",
            "**Maç sayfası yalnız vig'i temizlenmiş piyasa konsensüs olasılığını gösterir** (2026-10-02: ve "
            f"Süper Lig maçında TFF baş hakem adını — `{SPEC}`) — kitap adı",
        ),
        (
            "- Haber, sakatlık, kadro, hakem, hava, stadyum verisi — sitede HİÇBİR kaynak metni ya da oyuncu düzeyi bilgi yok",
            "- Haber, sakatlık, kadro, hava, stadyum verisi ve hakem (TEK istisna, kullanıcı kararı 2026-10-02: yalnız\n"
            "  Süper Lig maç sayfasında TFF'nin maç başlamadan önce açıkladığı baş hakem adı — "
            f"`{SPEC}`) — sitede HİÇBİR kaynak metni ya da oyuncu düzeyi bilgi yok",
        ),
        (
            "= {`leagues`, `matches`, `odds_snapshots`} (ara `site.*` görünümleri",
            "= {`leagues`, `matches`, `match_officials`, `odds_snapshots`} (`match_officials` 2026-10-02'den beri, yalnız "
            "`site.match_officials` üzerinden ve `site.matches` join'iyle tabanlı; ara `site.*` görünümleri",
        ),
        (
            "serbest metin alanı yalnız takım adı, lig adı, ülke — tip ve uzunluk sınırlı",
            "serbest metin alanı yalnız takım adı, lig adı, ülke ve Süper Lig TFF baş hakem adı (`$defs.person`, "
            "2026-10-02) — tip ve uzunluk sınırlı",
        ),
        (
            'mühür durumu ("kapanış kaydedildi" / "bekleniyor").',
            'mühür durumu ("kapanış kaydedildi" / "bekleniyor"), Süper Lig maçında TFF baş hakem adı ("Hakem: X (TFF\n'
            f"ataması)\"; atanmamış/eşlenmemiş/başlamadan sonra görülmüşse satır yok — `{SPEC}`).",
        ),
    ],
    "docs/DEFERRED.md": [
        (
            "Sınırlama `latest_observations` docstring'inde ve HANDOFF §3.9/31'de yazılı.\n",
            "Sınırlama `latest_observations` docstring'inde ve HANDOFF §3.9/31'de yazılı.\n"
            "**TFF hakem yolu bu sınırdan etkilenmez (2026-10-02):** `officials.link_officials` turun ayrıştırılmış\n"
            "sonucundan çalışır, gözlem tablosunu okumaz; `match_officials` değişiklik kaydı X→Y→X'i üç satır yazar\n"
            "(`tests/test_site_officials_db.py`). 9.6e'nin kendisi (`latest_observations`) açık kalır.\n",
        ),
        (
            "toplayıcısı yeni bir iştir, sayfa şekli ölçülerek başlar. HANDOFF §3.9/30.\n",
            "toplayıcısı yeni bir iştir, sayfa şekli ölçülerek başlar. HANDOFF §3.9/30.\n\n"
            "**9.7a — İki Süper Lig takımının API yazımı henüz görülmedi (2026-10-02).** `config/tff_teams.yaml`de\n"
            "`kasimpaşa` ve `tümosan konyaspor` `null`: The Odds API'nin bu sezon `tur.1`de onları hangi adla yazdığı\n"
            "canlı `matches`te hiç görülmedi; ad UYDURULMAZ. Bu iki takımın maçları `awaiting_alias` sayılır (hata değil)\n"
            "ve sayfada hakem satırı çıkmaz. Düzeltme: takımın ilk `tur.1` maçı `matches`e girince adı ölçerek YAML'a yaz,\n"
            "`test_every_mapped_api_name_was_seen_in_tur1`i veritabanı adresiyle koş. Ne zaman: `collect-daily` logunda\n"
            "`alias bekleyen` > 0 görüldüğünde.\n\n"
            "**9.7b — Lig süzgeci alt dizedir (2026-10-02).** `league_label_contains: \"Süper Lig\"` adında \"Süper Lig\"\n"
            "geçen BAŞKA bir bloğu da (ör. \"Turkcell Kadın Futbol Süper Ligi\") işler: YAML'da olmayan ad kırmızıdır\n"
            "(sessiz değil, `collect-daily` düşer), ama YAML'da OLAN bir adla aynı gün aynı rakiple oynanan maç yanlış\n"
            "maça bağlanabilir. Bugün ölçülen sayfada (2026-09-19) böyle blok yok. Ne zaman: `pageID=600`de ilk kez\n"
            "ikinci bir \"Süper Lig\" etiketi görüldüğünde (kırmızı mesaj etiketi adıyla taşır) — süzgeç tam etiket\n"
            "ya da dışlama listesiyle daraltılır (kullanıcı kararı).\n",
        ),
    ],
    "docs/HANDOFF.md": [
        (
            "**Adım 12 — 0014'ü canlıya uygula (K/3, 15 dk; asistan yapar, sen onaylarsın).**",
            "**Adım 12 — 0014'ü, ardından 0015'i canlıya uygula (K/3, 25 dk; asistan yapar, sen onaylarsın).**",
        ),
        (
            "- Bitti: advisors'ta yeni ERROR/WARN yok; `site` şeması görünümleri canlıda; seal yeşil.\n",
            "- Bitti: advisors'ta yeni ERROR/WARN yok; `site` şeması görünümleri canlıda; seal yeşil.\n"
            "- **0015 (TFF baş hakemi, `db/migrations/0015_match_officials.sql`; "
            f"`{SPEC}` §5):** 0014 bittikten SONRA\n"
            "  aynı kuralla — sessiz aralık, bayt bayt metin + sha256 deftere, `begin … rollback` provası, `apply_migration`\n"
            "  `postgres` rolüyle, katalog testleri salt okuma, advisors, sonraki seal turu yeşil. Söyleyeceği:\n"
            "  *\"0015'i uygula.\"* Bitti: `public.match_officials` (RLS açık, politikasız) ve `site.match_officials`\n"
            "  canlıda; sonraki `collect-daily` logunda `hakem bağlama` satırı.\n",
        ),
        (
            "(`0015_site_reader_login.sql`;",
            "(`0016_site_reader_login.sql` — 0015 TFF hakem tablosudur;",
        ),
    ],
    "docs/phases/06-site/HANDOFF.md": [
        (
            "eklenmemiş, `security_invoker` uyarısı yok).\n",
            "eklenmemiş, `security_invoker` uyarısı yok).\n"
            "   **0015 (TFF baş hakemi, 2026-10-02):** 0014'ten SONRA aynı kuralla; `site_reader`a `LOGIN` veren migration\n"
            "   **0016** olur (`docs/HANDOFF.md` §0.4 Adım 12/14).\n",
        ),
        (
            "## Hukuk incelemesi (HANDOFF §0.7/7'ye)\n",
            "## Kapının ÖLÇMEDİKLERİ (TFF baş hakemi, 2026-10-02)\n\n"
            "Plan: `docs/superpowers/plans/2026-10-02-tff-hakem-site.md`.\n\n"
            "1. YAML'daki API adlarının `tur.1`de görüldüğü (`test_every_mapped_api_name_was_seen_in_tur1`) yalnız\n"
            "   veritabanı adresiyle koşar — kapıda ve CI'da adıyla SKIP.\n"
            "2. TFF tarih hücresinin şekli 2026-09-19 fixture'ından ölçüldü; TFF'nin YANLIŞ tarih basması ölçülmez.\n"
            "3. `league_label_contains` alt dizedir (DEFERRED 9.7b).\n"
            "4. Ters ev/deplasman yalnız uyarıdır; `collect-daily` kırmızı olmaz.\n"
            "5. Check-out derlenmiş sayfada hakem satırının VARLIĞINI/YOKLUĞUNU ölçmez (bileşen testi + ad listesi ölçer;\n"
            "   satır `data-fe` taşımaz).\n"
            "6. `verify-snapshot` hakemin yalnız `tur.1` maçında durduğunu sınamaz (tek yazar `link_officials`).\n"
            "7. Canlıya uygulama ve advisors (HANDOFF Adım 12).\n"
            "8. DB mutasyon kanıtları yalnız yerel kum havuzunda (Docker); CI yalnız yeşili ölçer.\n"
            "9. `seen_at` toplama turunun `now`udur, TFF'nin yayımladığı an değil (muhafazakâr yön).\n"
            "10. Hakem adı TFF'nin büyük harfli yazımıyla basılır; yazım düzeltmesi yok.\n\n"
            "## Hukuk incelemesi (HANDOFF §0.7/7'ye)\n",
        ),
    ],
}
for name, pairs in edits.items():
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, (name, old[:60])
        text = text.replace(old, new)
    if name == "docs/phases/06-site/HANDOFF.md":
        text += (
            "| C12 | maç sayfası (Süper Lig) | TFF baş hakem adı | Hakem adı kişisel veridir (kamuya açıklanmış görev "
            "bilgisi); TFF Kullanım Şartları (pageID=179) ticari olmayan kullanım + kaynak gösterimi diyor ve sayfa "
            "\"(TFF ataması)\" yazıyor. Ticari bir sitede yayın KVKK ve TFF koşulları açısından uygun mu? Depodaki tam "
            "sayfa fixture'ları kırpılmadı (spec 2026-10-02 §8) |\n"
        )
    path.write_text(text, encoding="utf-8")
PY
git diff --stat
```
Expected: dört dosya değişti; betik `AssertionError` vermez.

- [ ] **Step 3: Doğrula**

Run: `grep -n "0016_site_reader_login\|0015'i canlıya\|9.7a\|9.7b\|C12" docs/HANDOFF.md docs/DEFERRED.md docs/phases/06-site/HANDOFF.md`
Expected: Adım 12 başlığı, 0016 satırı, 9.7a/9.7b, C12 satırı görünür.
Run: `PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/ -q -m "not sitedb" -k "runbook or handoff or deferred or docs" --tb=short`
Expected: geçer (doküman bekçisi testleri varsa yeşil; yoksa `deselected`).

- [ ] **Step 4: Mutasyon kanıtı**

Doküman görevi davranış taşımaz; bekçisi Step 1'in TEK-eşleşme ölçümü ve Step 2'nin `assert`leridir. Kanıt:
Step 2 betiği ikinci kez koşulduğunda `AssertionError` verir (anchor artık değişti → `count == 0`):
```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -c 'from pathlib import Path; t=Path("docs/HANDOFF.md").read_text(encoding="utf-8"); print(t.count("(`0015_site_reader_login.sql`;"), t.count("(`0016_site_reader_login.sql`"))'
```
Expected: `0 1`.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-09-23-faz6-iz-b-design.md docs/DEFERRED.md docs/HANDOFF.md docs/phases/06-site/HANDOFF.md
git commit -F - <<'EOF'
docs: İz B kapsamı, DEFERRED ve HANDOFF — TFF baş hakemi (0015), LOGIN 0016

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 6: TAM KAPI**

```bash
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; nvm use 24.21.0; T=$(mktemp -d); env -u DATABASE_URL -u ODDS_API_KEY -u TYPESAFE_API_KEY TMPDIR=$T ./verify.sh > "$T/verify.log" 2>&1; grep -E "^(PASS|FAIL|SKIP)|KAPI" "$T/verify.log"
```
Expected: `FAIL:` yok; üç adlı SKIP; `KAPI YEŞİL`.

---

## Spec kapsam haritası (öz-inceleme)

| Spec | Görev |
|---|---|
| §1 başarı ölçütleri (son ön-başlama ataması; satır yok; sessiz kayıp yok) | G3 (görünüm), G4 (eşleme kırmızıları), G5 (null), G6 (satır yok) |
| §3.1 tarih/saat, yük, tarihli anahtar | G2 |
| §3.2 sayım bekçisi | G2 |
| §3.3 aynı `now`, gözlem tablosundan okumaz | G4 |
| §4 lig süzgeci, ad eşlemesi, maç bulma, değişiklik kaydı, dönüş | G1 (YAML), G4 |
| §5 0015 (tablo, append-only, RLS, revoke, görünüm, grant), H1a, 0016 | G3, G7 |
| §6 dışa aktarım/döküm/türetim, şema, TS, fixture, sayfa, sözlük, check-out | G5, G6 |
| §7 İz B §1, H2b, B7/H1a | G7 |
| §8 hukuk (kaynak gösterimi, avukat) | G6 ("TFF ataması"), G7 (C12) |
| §9/1–8 testler, bağımsız inceleme | G2–G6; inceleme notu G3/G5 |
