-- Faz 2: holdout açılış kaydı (tasarım §5.3, D8).
--
-- Holdout (maç tarihi 2025-07-01 ile 2026-07-01 arası) yalnız `open_holdout` ile açılır ve her
-- açılış buraya bir satır yazar: an, git SHA'sı, amaç. Faz kapıları açılış sayısını bu tablodan
-- okur (Faz 2 sonunda sıfır). Kayıt append-only'dir: bir açılış silinemez, değiştirilemez, tablo
-- boşaltılamaz — sayım ancak böyle kanıt olur. Kısıtlar kodun doğrulamasının ikinci katmanıdır.

create table if not exists holdout_access_log (
  id         bigserial primary key,
  opened_at  timestamptz not null,
  git_sha    text not null check (git_sha ~ '^[0-9a-f]{40}$'),
  purpose    text not null check (length(purpose) > 0)
);

-- API rolleri (anon, authenticated) tabloya hiç erişemez: RLS açık, politika YOK (R90). Hat
-- tablonun sahibi olarak bağlanır ve sahip RLS'yi atlar; FORCE kasıtlı olarak yok — açılış
-- yazımı durmasın.
alter table holdout_access_log enable row level security;

-- Append-only zorlaması. forbid_ledger_mutation() 0001'de tanımlandı; yeniden yazılmaz.
drop trigger if exists holdout_access_log_append_only on holdout_access_log;
create trigger holdout_access_log_append_only
  before update or delete on holdout_access_log
  for each row execute function forbid_ledger_mutation();

-- Satır tetikleyicisi TRUNCATE'i görmez: açılış sayısı tek komutla silinemesin (R90).
drop trigger if exists holdout_access_log_no_truncate on holdout_access_log;
create trigger holdout_access_log_no_truncate
  before truncate on holdout_access_log
  for each statement execute function forbid_ledger_mutation();
