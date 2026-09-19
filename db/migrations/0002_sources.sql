-- Faz 1 şeması: kaynak gözlemleri, maç sonuçları, varlık takma adları.
--
-- HASH ZİNCİRİ YOKTUR ve bu bilinçlidir. Zincir, ürünün "bu kayıt kurcalanmadı" iddiasını
-- taşıyan ORAN defteri içindir. Kaynak gözlemleri özellik girdisidir: append-only ve
-- observed_at damgalı olmaları yeniden üretilebilirlik için yeter. Bu ödünleşme faz
-- handoff'unda "kapının ölçmediği" olarak yazılır — sessizce varsayılmaz.

create table if not exists source_observations (
  id            bigserial primary key,
  source_id     text not null,
  entity_kind   text not null,
  entity_key    text not null,
  observed_at   timestamptz not null,
  payload       jsonb not null,
  content_hash  text not null,
  unique (source_id, entity_kind, entity_key, content_hash)
);

create index if not exists obs_lookup_idx
  on source_observations (source_id, entity_kind, entity_key, observed_at desc);
create index if not exists obs_observed_idx on source_observations (observed_at);

-- Sonuçlar da bir GÖZLEMDİR: skor düzeltilebilir ve düzeltmenin kendisi kayıtta kalmalı.
-- (match_id, observed_at) anahtarı düzeltme geçmişini taşır; okuyan en yenisini alır.
create table if not exists match_results (
  match_id      text not null references matches(id),
  observed_at   timestamptz not null,
  home_score    int not null check (home_score >= 0),
  away_score    int not null check (away_score >= 0),
  completed     boolean not null,
  primary key (match_id, observed_at)
);

create index if not exists results_completed_idx on match_results (completed) where completed;

-- Varlık eşleme sözlüğü. `confidence` SAKLANIR: eşiği sonradan yükseltmek, eşleşmeleri
-- yeniden çıkarmayı gerektirmesin (spec §5.2, "ham cevaplar saklandığı sürece").
create table if not exists entity_aliases (
  source_id     text not null,
  entity_kind   text not null,
  alias         text not null,
  canonical_id  text not null,
  confidence    numeric not null check (confidence >= 0 and confidence <= 1),
  decided_at    timestamptz not null,
  primary key (source_id, entity_kind, alias)
);

-- Append-only zorlaması. forbid_ledger_mutation() 0001'de tanımlandı; yeniden yazılmaz.
drop trigger if exists source_observations_append_only on source_observations;
create trigger source_observations_append_only
  before update or delete on source_observations
  for each row execute function forbid_ledger_mutation();

drop trigger if exists match_results_append_only on match_results;
create trigger match_results_append_only
  before update or delete on match_results
  for each row execute function forbid_ledger_mutation();
