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
