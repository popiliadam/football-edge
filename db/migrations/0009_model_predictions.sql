-- Faz 3: canlı gölge tahminleri (Faz 3 tasarımı §10, R134). YAYIN YOK.
--
-- Salı ve cuma karar anından sonra `live shadow` aktif liglerin kararı verilmiş maçları için
-- bileşen olasılıklarını (piyasa, fit Elo, Dixon-Coles) ve karar anındaki kapanış öncesi fiyatı
-- yazar. Harman ve bahis bu satırlardan, dondurulmuş ağırlıkla haftalık raporda hesaplanır: bütün
-- girdiler karar anının bilgisidir. Satır append-only: bir tahmin sonradan değiştirilemez, silinemez,
-- tablo boşaltılamaz — gölge sicil ancak böyle kanıt olur.

create table if not exists model_predictions (
  id                   bigserial primary key,
  match_id             text not null references matches(id),
  match_key            text not null,
  strategy             text not null,
  p_home               double precision not null check (p_home >= 0 and p_home <= 1),
  p_draw               double precision not null check (p_draw >= 0 and p_draw <= 1),
  p_away               double precision not null check (p_away >= 0 and p_away <= 1),
  pre_home             numeric not null check (pre_home > 1.0),
  pre_draw             numeric not null check (pre_draw > 1.0),
  pre_away             numeric not null check (pre_away > 1.0),
  decided_at           timestamptz not null,
  model_config_sha256  text not null check (model_config_sha256 ~ '^[0-9a-f]{64}$'),
  git_sha              text not null check (git_sha ~ '^[0-9a-f]{40}$'),
  recorded_at          timestamptz not null default now(),
  unique (match_id, strategy, model_config_sha256)
);

create index if not exists model_predictions_decided_idx on model_predictions (decided_at);

-- API rolleri tabloya erişemez (R90 deseni): RLS açık, politika yok.
alter table model_predictions enable row level security;

drop trigger if exists model_predictions_append_only on model_predictions;
create trigger model_predictions_append_only
  before update or delete on model_predictions
  for each row execute function forbid_ledger_mutation();

drop trigger if exists model_predictions_no_truncate on model_predictions;
create trigger model_predictions_no_truncate
  before truncate on model_predictions
  for each statement execute function forbid_ledger_mutation();
