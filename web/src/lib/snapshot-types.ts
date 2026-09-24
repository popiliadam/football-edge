// Anlık görüntü v1'in TS karşılığı (spec §5.2). Sözleşmenin sahibi
// `web/contract/snapshot.schema.json`dur; bu dosya onu ELLE taşır.
// BİÇİM KURALI (tests/test_site_web_contract.py bu biçimi ayrıştırır):
// her tip `export type Ad = {` ile açılır, `};` ile kapanır, her satırda tek anahtar.

export type Triple = {
  home: number;
  draw: number;
  away: number;
};

export type Round = {
  observed_at: string;
  books: number;
  p: Triple;
};

export type H2h = {
  opening: Round | null;
  latest: Round | null;
  closing: Round | null;
};

export type Anchor = {
  file: string;
  rows: number;
  last_id: number;
  head: string;
};

export type Ledger = {
  rows: number;
  last_id: number;
  head: string;
  anchor: Anchor;
};

export type MoveDistribution = {
  p10: number;
  p50: number;
  p90: number;
};

export type League = {
  id: string;
  slug: string;
  name: string;
  country: string;
  matches: number;
  move_distribution: MoveDistribution | null;
};

export type Team = {
  league_id: string;
  slug: string;
  name: string;
  matches: number;
  indexable: boolean;
};

export type Match = {
  id: string;
  league_id: string;
  path_id: string;
  slug: string;
  date: string;
  commence_time: string;
  home: string;
  away: string;
  sealed: boolean;
  rounds: number;
  h2h: H2h;
  move: Triple | null;
  indexable: boolean;
};

export type RecordEntry = {
  publication_id: number;
  match_id: string;
  market: string;
  outcome: "home" | "draw" | "away";
  published_at: string;
  published_price: number;
  publication_ledger_id: number;
  closing_fair_price: number;
  clv: number;
  publication_hash: string;
};

export type RecordSummary = {
  mean_clv: number;
  ci_low: number;
  ci_high: number;
  n: number;
};

export type TrackRecord = {
  published: number;
  entries: RecordEntry[];
  summary: RecordSummary | null;
};

export type Snapshot = {
  schema_version: 1;
  generated_at: string;
  git_sha: string;
  content_sha256: string;
  ledger: Ledger;
  floor: string;
  leagues: League[];
  teams: Team[];
  matches: Match[];
  record: TrackRecord;
  value_badge: null;
  analysis: null;
};
