-- Sitenin salt okuma katmanı (Faz 6 İz B tasarımı §4, B3–B5). YAZILIR, canlıya bu görevde UYGULANMAZ
-- (HANDOFF §0.7: AK6 onayı + ROLLBACK'li prova + `apply_migration`).
--
-- Üç şema, bir rol: `site` (her kolonu anlık görüntüye BİREBİR girebilir = yayımlanabilir),
-- `site_input` (hesap girdisi, yayımlanmaz: kitap bazında fiyat), `site_audit` (yalnız zincir
-- doğrulaması, yayımlanmaz). `site_reader` yalnız bu üç şemanın görünümlerini okur; HİÇBİR tabloda
-- yetkisi yoktur. Görünümler sahibinin (`postgres` = tablo sahibi) yetkisiyle okunur: 0013'ün RLS'i
-- politikasızdır ve sahibi bağlamaz. Görünüm sahibi tablo sahibi değilse ya da `security_invoker`
-- taşırsa görünüm HATASIZ 0 satır döner — katalog testi ikisini de kırmızı yapar (§4.2).
-- Parola ve oturum açma hakkı burada YOKTUR: onaydan sonra kullanıcı istemci tarafında verir (AK18).

-- DEFERRED 18f'in biçimi: `set … reset` her gönderim biçiminde bağlar (`set local` yalnız işlem
-- açan biçimlerde). Görünüm kurmak referans verilen tablolarda hafif kilit alır; mühür turunun
-- arkasında sınırsız beklenmez.
set lock_timeout = '5s';

create schema if not exists site;
create schema if not exists site_input;
create schema if not exists site_audit;
revoke all on schema site, site_input, site_audit from public;

-- Rol küme düzeyindedir: şablon kopyaları ve önceki test oturumları aynı kümeyi paylaşır.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'site_reader') then
    create role site_reader nologin noinherit;
  end if;
end
$$;
-- Kaza önleyiciler, güvenlik sınırı DEĞİL (oturumda kapatılabilir). Sınır: yetki yok.
alter role site_reader set default_transaction_read_only = on;
alter role site_reader set statement_timeout = '30s';

-- B4: holdout tabanı TEK yerde. Gövde tablo okumaz; değer Python sabitine eşitliğiyle sınanır.
create or replace function site.public_floor() returns timestamptz
language sql
immutable
begin atomic
  select '2026-07-02 00:00:00+00'::timestamptz;
end;

-- Taban süzgeci yok: lig satırı tarih taşımaz. Pasif lig (ve onun maçları) düşer.
create or replace view site.leagues with (security_barrier) as
  select l.id, l.name, l.country
  from public.leagues l
  where l.active;

-- `sealed_at` alınmaz (UPDATE edilir); `commence_time` de değişkendir — tutarlılık dışa aktarımın
-- tek REPEATABLE READ işlemine dayanır (B12).
create or replace view site.matches with (security_barrier) as
  select m.id, m.league_id, m.commence_time, m.home_team, m.away_team
  from public.matches m
  join site.leagues l on l.id = m.league_id
  where m.commence_time >= site.public_floor();

-- Bütün defter; tarih kolonu taşımaz. `head` saklanan hücredir — dışa aktarım onu KULLANMAZ,
-- zinciri yeniden hesaplar.
create or replace view site.ledger_head with (security_barrier) as
  select count(*)::bigint as rows,
         coalesce(max(o.id), 0)::bigint as last_id,
         coalesce(
           (select o2.row_hash from public.odds_snapshots o2 order by o2.id desc limit 1),
           repeat('0', 64)
         ) as head
  from public.odds_snapshots o;

-- B5: yer tutucu sicil. Faz 5 `publications`a AYNI ad, tip ve sırayla bağlar; gövde o güne dek
-- `where false` kalır (metin testi) ve kolon listesi Python sabitine eşittir (katalog testi).
create or replace view site.record with (security_barrier) as
  select null::bigint as publication_id,
         null::text as match_id,
         null::text as market,
         null::text as outcome,
         null::timestamptz as published_at,
         null::numeric as published_price,
         null::bigint as publication_ledger_id,
         null::numeric as closing_fair_price,
         null::double precision as clv,
         null::text as publication_hash
  where false;

-- Hesap girdisi: kitap adı YOK; `book_key` tur içinde kitabın sırası. Taban `site.matches`ten gelir.
create or replace view site_input.h2h_quotes with (security_barrier) as
  select o.id as ledger_id,
         o.match_id,
         o.observed_at,
         o.is_closing,
         o.outcome,
         o.price,
         dense_rank() over (partition by o.match_id, o.observed_at order by o.bookmaker) as book_key
  from public.odds_snapshots o
  join site.matches m on m.id = o.match_id
  where o.market = 'h2h';

-- Yalnız zincir doğrulaması: bilinçli olarak TABANSIZDIR (zincir GENESIS'ten ancak bütün satırlarla
-- hash'lenir). Holdout tarihli satır (bugün yok) yalnız hash'lenir, türetime girmez.
create or replace view site_audit.ledger_rows with (security_barrier) as
  select o.id, o.match_id, o.observed_at, o.bookmaker, o.market, o.outcome, o.point, o.price,
         o.bookmaker_last_update, o.is_closing, o.prev_hash, o.row_hash
  from public.odds_snapshots o;

-- ── Yetkiler: yalnız site_reader ────────────────────────────────────────────────────────────
revoke all on all tables in schema site, site_input, site_audit from anon, authenticated, service_role;
revoke all on function site.public_floor() from public, anon, authenticated, service_role;
grant usage on schema site, site_input, site_audit to site_reader;
grant select on all tables in schema site to site_reader;
grant select on all tables in schema site_input to site_reader;
grant select on all tables in schema site_audit to site_reader;
-- Yük taşır: görünümdeki fonksiyon çağrısının EXECUTE'u SORGULAYANA göre denetlenir. Bu satır
-- olmadan taban süzen her görünüm site_reader için yetki hatası verir.
grant execute on function site.public_floor() to site_reader;

reset lock_timeout;
