# TFF baş hakemi maç sayfasında — tasarım (2026-10-02)

**Durum:** kullanıcı onaylı tasarım (kullanıcı oturumu Adım 6; yaklaşım A ve tasarım "en iyi senaryo / öneri" ile
onaylandı) · **Üst belge:** `2026-09-23-faz6-iz-b-design.md` (İz B) — bu belge onun §1 kapsam dışı listesini ve H2b'yi
DEĞİŞTİRİR (§7) · **Yayın:** yerelde serbest; **ilk yayından önce avukat** (K/7/6 TFF koşulları + hakem adı/KVKK).

## 1. Amaç ve başarı ölçütü
Süper Lig (`tur.1`) maç sayfası, TFF'nin "Haftanın Maçları" sayfasında (`pageID=600`) **maç başlamadan önce**
açıklanmış baş hakemi gösterir: "Hakem: X (TFF ataması)" / "Referee: X (TFF appointment)". Başarı:
- atanmış ve eşlenmiş her `tur.1` maçında sayfa, `commence_time`dan ÖNCE görülen SON atamayı gösterir;
- maç başladıktan sonra görülen atama, eşlenemeyen maç ve atanmamış maç için sayfada hakem satırı YOKTUR (yer tutucu,
  "yakında", tahmin yok);
- hiçbir sessiz kayıp yok: ayrıştırılamayan satır ve yapılandırmada olmayan takım adı kırmızıdır.

**Kapsam dışı (YAGNI):** yardımcı/dördüncü/VAR/AVAR hakemleri; alt ligler; geriye dönük doldurma (eski gözlemlerde tarih
yok); modelde hakem özelliği (Faz 3 kararı aynen); JSON-LD'de hakem (schema.org'da standart alan yok).

## 2. Bugünkü durum (keşif, 2026-10-02)
- `collectors/tff.py` `parse_referees`: `entity_kind="fixture_official"`, anahtar `ev|deplasman` (tarih/lig yok),
  yük `{home_team, away_team, referee, league}`; satırdaki tarih (`haftaninMaclariMaclarTarih`: `18.09.2026` + saat
  `20:00`, İstanbul) OKUNMUYOR. Bütün ligler yazılıyor (fixture: Süper Lig 9, 1. Lig 10, 2. Lig 17, 3. Lig 26).
- TFF maçı `matches` satırına BAĞLI DEĞİL: `matches.id` The Odds API olay kimliği, adlar API yazımı; TFF adları
  sponsorlu/aksanlı ("tümosan konyaspor", "çaykur rizespor"); `entity_aliases` yalnız footystats.
- `source_observations` `content_hash` ile tekilleşir → X→Y→X'te ikinci X yazılmaz; `latest_observations` Y'yi döner
  (bilinen I-5, DEFERRED §9.6e). As-of (`observed_at < commence_time`) kuralı yok.
- Site yalnız `site` şemasını okur (AK1-A); 0014 (`site.leagues/matches/ledger_head/record`, `site_input`, `site_audit`)
  depoda, canlıda değil. Spec İz B §1 hakemi açıkça dışarıda tutuyor; H2b serbest metni takım/lig/ülke adıyla sınırlıyor.

## 3. Toplama (`src/football_edge/collectors/tff.py`)
1. Her maç satırından **tarih** (`dd.mm.yyyy`) ve **saat** (`HH:MM`) okunur; yüke `match_date` (ISO `YYYY-MM-DD`) ve
   `kickoff_local` (`HH:MM`) girer. Anahtar `ev|deplasman|YYYY-MM-DD` olur (gelecek sezonun aynı eşleşmesi bu sezonu
   ezemez). Eski anahtarlı satırlar olduğu gibi kalır (append-only); okuyan kod yok (§2).
2. Sayım bekçisi aynen: tarih/saati okunamayan satır "sessizce atlandı" sayılır → `ContractViolation`.
3. `collect_tff` gözlemleri bugünkü gibi yazdıktan sonra AYNI `now` ile `link_officials` çağırır (§4). Bağlama
   gözlem tablosundan okumaz — o turun ayrıştırılmış sonucundan çalışır (I-5'ten bağımsız).

## 4. Eşleme ve kayıt (`src/football_edge/officials.py`, `config/tff_teams.yaml`)
- **Lig süzgeci:** lig etiketi `config/tff_teams.yaml` `league_label_contains` ("Süper Lig") ifadesini TAM
  ifade olarak taşıyan bloklar (plan düzeltmesi, controller düzeltmesi C1, 2026-10-02): etiket
  `label.replace("İ", "i").casefold()` ile katlanır (büyük harfli "SÜPER LİG" de eşleşir); ifadeden sonra
  harf/rakam gelmez (`(?!\w)` — "Süper Ligi" eşleşmez); `kadın`, `kadin`, `u19`, `u21`, `gelişim`, `gelisim`
  sözcüklerinden birini taşıyan etiket (kadın/genç ligi) işlenmez. Hedef lig `tur.1`. Diğer bloklar sayılır,
  işlenmez.
- **Ad eşlemesi:** YAML `teams:` — `normalise_team(TFF adı) → API adı` (18 takım, canlı `matches`ten salt okuma ile
  kurulur; her API adı `tur.1`de gerçekten görülmüş olmalı — test). YAML'da olmayan TFF adı → `ContractViolation`
  (yapılandırma eksiği; sessiz geçmez; düzeltme: YAML'a satır).
- **Henüz görülmemiş API yazımı (plan düzeltmesi, 2026-10-02):** YAML'da değeri `null` olan takım (API yazımı
  canlı `matches`te henüz hiç görülmedi — uydurulmaz; bugün `kasimpaşa`, `tümosan konyaspor`) içeren maç ayrı
  `awaiting_alias` sayacına girer (loglanır, hata değil). YAML'da HİÇ olmayan TFF adı `ContractViolation` kalır.
- **Maç bulma:** `matches` içinde `league_id='tur.1'`, `home_team`, `away_team` eşit ve `commence_time`ın
  **Europe/Istanbul takvim günü** = `match_date`. Tam bir eşleşme → bağlanır; sıfır → "henüz DB'de yok" sayacı (oranlar
  ufka girmemiş olabilir; hata değil, loglanır); birden çok → `ContractViolation`.
- **Değişiklik kaydı:** tablo `match_officials`a, maçın SON kayıtlı hakemi bu turunkinden farklıysa (ya da hiç yoksa)
  `(match_id, referee, seen_at=now)` eklenir. Aynıysa yazılmaz. X→Y→X üç satır olur (I-5 burada oluşmaz).
- Dönüş: `(bağlanan, yeni yazılan, DB'de yok, alias bekleyen, lig dışı)` sayıları; `collect-daily` logu bunları basar.

## 5. Veritabanı (`db/migrations/0015_match_officials.sql`; 0014'e DOKUNULMAZ)
```sql
create table if not exists public.match_officials (
  id         bigint generated always as identity primary key,
  match_id   text not null references public.matches(id),
  referee    text not null check (length(referee) between 1 and 80),
  seen_at    timestamptz not null
);
create index if not exists match_officials_match_idx on public.match_officials (match_id, seen_at);
-- append-only (0001 forbid_ledger_mutation), RLS açık + politikasız, API rollerinden revoke (0013 kalıbı)

create or replace view site.match_officials with (security_barrier) as
  select distinct on (o.match_id) o.match_id, o.referee
  from public.match_officials o
  join site.matches m on m.id = o.match_id
  where o.seen_at < m.commence_time
  order by o.match_id, o.seen_at desc, o.id desc;
-- revoke API rolleri; grant select to site_reader
```
- Taban (holdout) süzgeci `site.matches` join'inden gelir (H1a kapanışı: yeni temel tablo yalnız `match_officials`).
- Sıra: 0014 → 0015 (site şeması ve `site_reader` 0014'te). Adım 14'ün LOGIN migration'ı **0016** olur.
- Canlıya uygulama: 0014 ile aynı kural (sessiz aralık, ROLLBACK provası, bayt bayt metin + sha256 deftere,
  `postgres` rolü, advisors, sonraki mühür turu yeşil).

## 6. Site (dışa aktarım → anlık görüntü → sayfa)
- `export.py`: `site.match_officials` aynı REPEATABLE READ işleminde okunur; `inputs.py` döküm/`MatchRow`a
  `referee: str | None`; `derive._match_json` maç nesnesine `"referee": <ad> | null`.
- `web/contract/snapshot.schema.json`: maç öğesine zorunlu `referee` — `{"$ref": "#/$defs/person"}`; `$defs.person` =
  `{"type": ["string", "null"], "minLength": 1, "maxLength": 80}` (plan düzeltmesi: depodaki doğrulayıcı
  `football_edge.site.schema` `oneOf` desteklemez; anlam aynı: null ya da 1–80 karakter metin). `schema_version` 1 kalır (hiç yayın yok; tek tüketici
  bizim derlememiz). TS tipleri, `web/fixtures/*.json` ve `tests/site_web_fixtures.py` üreticisi aynı anda.
- Maç sayfası: `referee` doluysa sözlük anahtarı `match.referee` ("Referee: {name} (TFF appointment)" / "Hakem:
  {name} (TFF ataması)"); null ise satır hiç basılmaz. `check-out` ad listesi (`numbers.ts` `pageNames.match`)
  hakem adını içerir.

## 7. İz B spec'inde değişen kurallar (kullanıcı kararı, 2026-10-02)
- §1 kapsam dışı listesinden "hakem" çıkar; yerine: "yalnız Süper Lig maç sayfasında TFF'nin maç başlamadan önce
  açıkladığı baş hakem adı (bu belge)".
- H2b: serbest metin "takım, lig, ülke adı **ve Süper Lig TFF baş hakem adı**".
- B7/H1a: `site_reader` kapanışına `public.match_officials` girer (yalnız `site.match_officials` üzerinden, tabanlı).

## 8. Hukuk
- TFF Kullanım Şartları (pageID=179): ticari olmayan kullanım + kaynak gösterimi → sayfa "(TFF ataması)" ile kaynağı
  adıyla gösterir. Ticari olmayan yerel kullanım bugün; **yayından önce avukat** (K/7/6).
- Hakem adı kişisel veridir (kamuya açıklanmış görev bilgisi). KVKK açısından yayımı avukat sorusu (Adım 16 paketi).
- Depodaki tam sayfa fixture'ları kullanıcı kararıyla kırpılmadı (Adım 6) — avukat paketine not.

## 9. Testler (her biri mutasyon kanıtlı; tam kapı)
1. Ayrıştırıcı: fixture'dan tarih/saat; anahtar tarihli; tarihi bozulmuş satır → `ContractViolation`.
2. Eşleme (birim): YAML'da olmayan ad → kırmızı; lig dışı blok işlenmez; gün eşlemesi İstanbul saatine göre (İstanbul
   UTC+3: 01:00 İstanbul maçı = önceki UTC günü 22:00 → İstanbul gününe; 23:30 İstanbul maçı = aynı UTC günü
   20:30 → kendi gününe; plan düzeltmesi 2026-10-02); sıfır maç → sayaç; iki maç → kırmızı.
3. Değişiklik kaydı (DB): aynı hakem tekrar yazılmaz; X→Y→X üç satır.
4. Görünüm (site-db): `seen_at >= commence_time` satırı görünmez; aynı maçta en son ön-başlama satırı döner;
   tabandan eski maç sızmaz; `site_reader` yalnız görünümü okur, tabloyu okuyamaz; API rolleri hiçbirini okuyamaz;
   append-only. Kapanış testleri (`BASE_TABLES`, sahiplik sayısı, `SITE_TYPES`) yeni nesneyle güncellenir.
5. Şablon/alt küme: `tests/site_db.py` `TEMPLATE_MIGRATIONS`a 0015; `verify.sh` site-db alt sınırları.
6. Dışa aktarım/türetim: hakemli ve hakemsiz maç; şema ve TS sözleşme testleri; fixture üretici eşliği.
7. Web: hakem doluysa satır var, null ise yok; sözlük en/tr anahtar eşliği; check-out ad kuralı.
8. Bağımsız inceleme ajanı (güvenlik sınırı: yeni tablo + görünüm + yetki).

## 10. Öz-inceleme
- Yer tutucu yok; açık uygulama ayrıntısı: YAML'ın 18 satırı (canlı salt okuma ile plan sırasında doldurulur).
- Tutarlılık: 0014 değişmez; 0015 0014'ten sonra; LOGIN 0016 (HANDOFF Adım 14 güncellenir).
- Kapsam tek plana sığar (toplayıcı + eşleme + migration + dışa aktarım + sayfa).
- Belirsizlik: "İstanbul takvim günü" eşlemesi bilinçli seçim (TFF tarihi yerel); saat uyuşmazlığı eşlemeyi bozmaz,
  yalnız günlük çakışma (aynı gün aynı iki takım iki kez) kırmızıdır.
