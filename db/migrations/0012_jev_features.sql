-- Faz 4: haber ve Jev özellik deposu (Faz 4 tasarımı §4, R164, R166).
--
-- Tek zaman alanı `available_at`: canlıda max(ilk görüş anımız, yayıncı iddiası), arşivde iddia edilen
-- yayın anı + ölçülmüş güvenlik payı. `first_seen_at` veritabanı saatidir (R172): ajansspor'un
-- `source_observations.observed_at`i yayıncının iddiasıdır, bizim toplama saatimiz değil. Özellik kodu yalnız bu alana bakar; canlı ve arşiv aynı yoldan geçer. Kademe 1
-- haber başına T1 kapı sorularını, kademe 2 karar anında maç başına bataryayı saklar. Bütün
-- tablolar append-only: bir cevap sonradan değiştirilemez, silinemez, tablo boşaltılamaz — özellik
-- kümesi ancak böyle yeniden üretilebilir. `jev_spend` harcama tavanının (R159) defteridir.
--
-- Maliyet sütunlarında `< 'Infinity'` bilinçlidir: numeric'te NaN her sayıdan büyük sayılır ve
-- `>= 0`ı geçer; bir NaN ay toplamını NaN yapar ve tavan karşılaştırması hep yanlış döner.

create table if not exists news_items (
  id                    bigserial primary key,
  source_id             text not null,
  lang                  text not null check (length(lang) > 0),
  title                 text not null,
  body                  text,
  url                   text not null,
  published_at_claimed  timestamptz,
  first_seen_at         timestamptz not null default now(),
  available_at          timestamptz not null,
  availability_basis    text not null check (availability_basis in ('observed', 'archive_claimed')),
  content_hash          text not null check (content_hash ~ '^[0-9a-f]{64}$'),
  recorded_at           timestamptz not null default now(),
  unique (source_id, content_hash),
  -- Canlı haber bizim görmediğimiz bir anda "mevcut" sayılamaz; yayıncı iddiasından önce de sayılamaz.
  check (
    availability_basis <> 'observed'
    or (
      available_at >= first_seen_at
      and (published_at_claimed is null or available_at >= published_at_claimed)
    )
  ),
  -- Arşiv haberinin zamanı iddiadan türetilir: iddia yoksa ya da pay negatifse satır yanlıştır.
  check (
    availability_basis <> 'archive_claimed'
    or (published_at_claimed is not null and available_at >= published_at_claimed)
  )
);

create index if not exists news_items_available_idx on news_items (available_at);

create table if not exists jev_item_answers (
  id              bigserial primary key,
  item_id         bigint not null references news_items(id),
  prompt_version  text not null check (prompt_version ~ '^[0-9a-f]{64}$'),
  question_id     text not null check (length(question_id) > 0),
  choice          text not null,
  probabilities   jsonb not null check (jsonb_typeof(probabilities) = 'object'),
  confidence      double precision not null check (confidence >= 0 and confidence <= 1),
  match_id        text references matches(id),
  side            text check (side in ('home', 'away', 'both')),
  cluster_id      text,
  jev_model       text not null,
  asked_at        timestamptz not null,
  cost_usd        numeric not null check (cost_usd >= 0 and cost_usd < 'Infinity'),
  recorded_at     timestamptz not null default now(),
  unique (item_id, prompt_version, question_id)
);

create index if not exists jev_item_answers_match_idx on jev_item_answers (match_id);

create table if not exists jev_match_answers (
  id              bigserial primary key,
  match_id        text not null references matches(id),
  decided_at      timestamptz not null,
  prompt_version  text not null check (prompt_version ~ '^[0-9a-f]{64}$'),
  question_id     text not null check (length(question_id) > 0),
  variant         text not null check (variant in ('real', 'blank', 'shuffled')),
  item_set_hash   text not null check (item_set_hash ~ '^[0-9a-f]{64}$'),
  choice          text not null,
  probabilities   jsonb not null check (jsonb_typeof(probabilities) = 'object'),
  confidence      double precision not null check (confidence >= 0 and confidence <= 1),
  jev_model       text not null,
  asked_at        timestamptz not null,
  cost_usd        numeric not null check (cost_usd >= 0 and cost_usd < 'Infinity'),
  recorded_at     timestamptz not null default now(),
  unique (match_id, decided_at, prompt_version, question_id, variant)
);

create index if not exists jev_match_answers_decided_idx on jev_match_answers (decided_at);

-- `cost_basis`: SDK maliyet bildirmezse tahmin yazılır ve adıyla işaretlenir (plan Task 7).
-- Token sayıları ilk 100 çağrının maliyet ölçümü içindir (Plan 2).
create table if not exists jev_spend (
  id             bigserial primary key,
  spent_at       timestamptz not null,
  kind           text not null check (length(kind) > 0),
  cost_usd       numeric not null check (cost_usd >= 0 and cost_usd < 'Infinity'),
  cost_basis     text not null check (cost_basis in ('reported', 'estimated')),
  input_tokens   integer check (input_tokens >= 0),
  output_tokens  integer check (output_tokens >= 0),
  recorded_at    timestamptz not null default now()
);

create index if not exists jev_spend_spent_idx on jev_spend (spent_at);

-- API rolleri tablolara erişemez (R90 deseni): RLS açık, politika yok.
alter table news_items enable row level security;
alter table jev_item_answers enable row level security;
alter table jev_match_answers enable row level security;
alter table jev_spend enable row level security;

-- Append-only zorlaması. forbid_ledger_mutation() 0001'de tanımlandı; yeniden yazılmaz.
-- Satır tetikleyicisi TRUNCATE'i görmez: her tabloya ayrı ifade tetikleyicisi.
drop trigger if exists news_items_append_only on news_items;
create trigger news_items_append_only
  before update or delete on news_items
  for each row execute function forbid_ledger_mutation();

drop trigger if exists news_items_no_truncate on news_items;
create trigger news_items_no_truncate
  before truncate on news_items
  for each statement execute function forbid_ledger_mutation();

drop trigger if exists jev_item_answers_append_only on jev_item_answers;
create trigger jev_item_answers_append_only
  before update or delete on jev_item_answers
  for each row execute function forbid_ledger_mutation();

drop trigger if exists jev_item_answers_no_truncate on jev_item_answers;
create trigger jev_item_answers_no_truncate
  before truncate on jev_item_answers
  for each statement execute function forbid_ledger_mutation();

drop trigger if exists jev_match_answers_append_only on jev_match_answers;
create trigger jev_match_answers_append_only
  before update or delete on jev_match_answers
  for each row execute function forbid_ledger_mutation();

drop trigger if exists jev_match_answers_no_truncate on jev_match_answers;
create trigger jev_match_answers_no_truncate
  before truncate on jev_match_answers
  for each statement execute function forbid_ledger_mutation();

drop trigger if exists jev_spend_append_only on jev_spend;
create trigger jev_spend_append_only
  before update or delete on jev_spend
  for each row execute function forbid_ledger_mutation();

drop trigger if exists jev_spend_no_truncate on jev_spend;
create trigger jev_spend_no_truncate
  before truncate on jev_spend
  for each statement execute function forbid_ledger_mutation();
