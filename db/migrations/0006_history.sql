-- Faz 2: football-data.co.uk CSV önbelleği ve çekme günlüğü (tasarım §4.3, D6).
--
-- `hist_files` bir ÖNBELLEKTİR, kanıt değil: yol başına son sürüm, içerik değişince güncellenir.
-- Kanıt, append-only çekme günlüğü (`hist_fetches`) ile depodaki kilittir
-- (config/history_lock.yaml). Her sürümü saklamak yılda ~130 MB ederdi; son sürüm ~20 MB.
--
-- Ham üçüncü taraf içeriği YALNIZ bu özel tabloda durur (D18): satır düzeyi güvenlik açık ve
-- politikasız — API rolleri (anon, authenticated) hiçbir satır göremez; tabloların sahibi olan
-- pipeline rolü RLS'e takılmaz.

create table if not exists hist_files (
  path                text primary key,
  sha256              text not null,        -- AÇILMIŞ baytların özeti (gzip'in değil)
  fetched_at          timestamptz not null, -- bu sürümün ilk görüldüğü an
  http_last_modified  text,
  byte_size           int not null check (byte_size >= 0),   -- açılmış bayt sayısı
  row_count           int not null check (row_count >= 0),   -- ayrıştırılan maç
  content             bytea not null        -- gzip(dosya baytları)
);

create table if not exists hist_fetches (
  id             bigserial primary key,
  path           text not null,
  fetched_at     timestamptz not null,
  sha256         text,                      -- NULL: deneme başarısız, önbelleğe girmedi
  http_status    int,                       -- NULL: HTTP yanıtı yok (robots, ağ, doğrulama)
  rows_parsed    int not null check (rows_parsed >= 0),
  rows_rejected  int not null check (rows_rejected >= 0)
);

create index if not exists hist_fetches_path_idx on hist_fetches (path, fetched_at desc);

alter table hist_files enable row level security;
alter table hist_fetches enable row level security;

-- Append-only zorlaması. forbid_ledger_mutation() 0001'de tanımlandı; yeniden yazılmaz.
drop trigger if exists hist_fetches_append_only on hist_fetches;
create trigger hist_fetches_append_only
  before update or delete on hist_fetches
  for each row execute function forbid_ledger_mutation();
