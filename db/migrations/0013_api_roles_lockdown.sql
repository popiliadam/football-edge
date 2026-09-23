-- API rolleri kilidi: eski tablolarda RLS, `anon`/`authenticated` yetkilerinin geri alınması,
-- eski append-only tablolara TRUNCATE bekçisi (DEFERRED 12a, R90).
--
-- NEDEN: 0001/0002'nin altı tablosunda RLS kapalıydı ve Supabase'in varsayılan yetkileri API
-- rollerine (`anon`, `authenticated`) her tabloda SELECT/INSERT/UPDATE/DELETE/TRUNCATE vermişti:
-- yayımlanabilir anahtarı bilen herkes REST'ten defteri okuyabilir, `matches`e yazabilir, satır
-- tetikleyicisini görmeyen TRUNCATE ile `odds_snapshots`u boşaltabilirdi. RLS'li tablolarda
-- (0006–0012) politika olmadığı için satır açılmıyordu, ama yetki yine duruyordu.
--
-- Boru hattının bütünü (GitHub işleri, pg_cron'un 0003–0011 dispatch işleri) tablo sahibi
-- `postgres` olarak bağlanır: sahip RLS'yi atlar (Supabase'de `postgres` ayrıca BYPASSRLS taşır),
-- yetkileri sahip olmaktan gelir. FORCE kasıtlı olarak yok — sahibin yazımı durmasın.
-- `service_role`e DOKUNULMAZ: gizli anahtarın rolüdür, BYPASSRLS taşır; append-only tablolarda
-- onu da satır ve TRUNCATE tetikleyicileri durdurur.

-- ── Kilit bekleme sınırı ──────────────────────────────────────────────────────────────────────
-- `enable row level security` ve tetikleyici kurmak altı tabloda sert kilit ister. Bir mühür turu
-- `odds_snapshots`a yazarken migration kuyrukta beklerse, ARKASINA dizilen her okuma/yazma da bekler.
-- Beş saniyede kilit alınamazsa migration hatayla düşer (bütünüyle geri alınır) ve sakin bir
-- dakikada yeniden koşulur. `local`: yalnız bu işlem; migration işlem içinde uygulanır.
set local lock_timeout = '5s';

-- ── RLS: politikasız, FORCE değil (0006/0007 deseni) ───────────────────────────────────────────
alter table leagues enable row level security;
alter table matches enable row level security;
alter table odds_snapshots enable row level security;
alter table source_observations enable row level security;
alter table match_results enable row level security;
alter table entity_aliases enable row level security;

-- ── Var olan nesneler: API rollerinin bütün yetkileri ─────────────────────────────────────────
-- Tablolar (görünümler dâhil) ve bigserial dizileri. Dizi yetkisi tek başına satır açmaz, ama
-- `nextval` ile defterin id'lerini tüketmek dışarıdan mümkün olmasın.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;
-- `forbid_ledger_mutation` bir tetikleyici fonksiyonudur; doğrudan çağrılamaz ve tetiklenirken
-- EXECUTE denetlenmez. PUBLIC'in hazır EXECUTE'u yine de kapanır: `anon` onu PUBLIC'ten miras alır.
revoke execute on function public.forbid_ledger_mutation() from public;

-- ── Gelecekte oluşturulacak nesneler ──────────────────────────────────────────────────────────
-- Supabase'in varsayılan yetkileri iki `for role` altında durur: `postgres` ve `supabase_admin`
-- (kapta `pg_default_acl`den ölçüldü). Bu depo nesnelerini `postgres` olarak oluşturur; onun
-- girdisi kapanır. `supabase_admin`inkini `postgres` değiştiremez (yetki hatası) ve bu depo o
-- rolle nesne oluşturmaz — bilinen sınır.
alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on functions from anon, authenticated;
-- Fonksiyonların PUBLIC EXECUTE'u şemaya bağlı girdiden değil Postgres'in genel varsayılanından
-- gelir; şemaya bağlı bir REVOKE onu kaldırmaz (kapta ölçüldü). Genel girdi `postgres`in HER
-- şemadaki YENİ fonksiyonlarını etkiler; var olanlara ve eklentilerin (`supabase_admin` sahipli)
-- fonksiyonlarına dokunmaz. `public`te şemaya bağlı girdi `service_role`e EXECUTE vermeye devam eder;
-- `public` DIŞINDA (`ops`, `extensions`, yeni bir şema) `postgres`in yeni fonksiyonu yalnız
-- sahibine açıktır; `service_role` de EXECUTE alamaz. Oraya `service_role`/RPC için fonksiyon yazan
-- migration EXECUTE'u açıkça vermelidir. Bugün her çağıran `postgres`tir (pg_cron işleri dâhil).
alter default privileges for role postgres
  revoke execute on functions from public;

-- ── Tetikleyici fonksiyonu: sabit search_path, mesajda tablonun adı ───────────────────────────
-- 0001'in gövdesi her tabloda "odds_snapshots" diyordu. Gövde hiçbir nesneye adla başvurmaz;
-- `search_path = ''` onu şema kaydırmasına karşı kapatır (advisor function_search_path_mutable).
-- `create or replace` sahibi ve yetkileri korur; bağlı tetikleyiciler yeniden kurulmaz.
create or replace function public.forbid_ledger_mutation() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception '% append-only bir defterdir; % reddedildi', tg_table_name, tg_op;
end;
$$;

-- ── TRUNCATE bekçisi: eski append-only üçlü (R90) ─────────────────────────────────────────────
-- Satır tetikleyicisi (0001/0002) TRUNCATE'i görmez: defter tek komutla boşaltılamasın. İfade
-- tetikleyicisi sahip için de koşar; `truncate matches cascade` da buradan geçer.
drop trigger if exists odds_snapshots_no_truncate on odds_snapshots;
create trigger odds_snapshots_no_truncate
  before truncate on odds_snapshots
  for each statement execute function forbid_ledger_mutation();

drop trigger if exists source_observations_no_truncate on source_observations;
create trigger source_observations_no_truncate
  before truncate on source_observations
  for each statement execute function forbid_ledger_mutation();

drop trigger if exists match_results_no_truncate on match_results;
create trigger match_results_no_truncate
  before truncate on match_results
  for each statement execute function forbid_ledger_mutation();
