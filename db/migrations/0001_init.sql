-- Faz 0 şeması: append-only oran defteri.

create table if not exists leagues (
  id            text primary key,
  odds_api_key  text not null unique,
  name          text not null,
  country       text not null,
  lang          text not null,
  gl            text not null,
  active        boolean not null default true
);

create table if not exists matches (
  id             text primary key,          -- The Odds API event id
  league_id      text not null references leagues(id),
  commence_time  timestamptz not null,
  home_team      text not null,
  away_team      text not null,
  first_seen_at  timestamptz not null default now(),
  sealed_at      timestamptz
);

create index if not exists matches_commence_idx on matches (commence_time);
create index if not exists matches_league_idx on matches (league_id);

create table if not exists odds_snapshots (
  id                     bigserial primary key,
  match_id               text not null references matches(id),
  observed_at            timestamptz not null,
  bookmaker              text not null,
  market                 text not null,
  outcome                text not null,
  point                  numeric,
  price                  numeric not null check (price > 1.0),
  bookmaker_last_update  timestamptz,
  is_closing             boolean not null default false,
  prev_hash              text not null,
  row_hash               text not null unique
);

create index if not exists odds_match_idx on odds_snapshots (match_id, observed_at);
create index if not exists odds_closing_idx on odds_snapshots (is_closing) where is_closing;

-- Append-only zorlaması: UPDATE ve DELETE veritabanı seviyesinde reddedilir.
create or replace function forbid_ledger_mutation() returns trigger as $$
begin
  raise exception 'odds_snapshots append-only bir defterdir; % reddedildi', tg_op;
end;
$$ language plpgsql;

drop trigger if exists odds_snapshots_append_only on odds_snapshots;
create trigger odds_snapshots_append_only
  before update or delete on odds_snapshots
  for each row execute function forbid_ledger_mutation();
