-- MVCAP AI voice receptionist schema
-- Apply via Supabase SQL editor or `supabase db push`

create extension if not exists pg_trgm;

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
do $$ begin
  create type keyword_action_type as enum (
    'say',
    'transfer_extension',
    'transfer_external',
    'refer_external',
    'ask_county',
    'flow',
    'alias_of'
  );
exception
  when duplicate_object then null;
end $$;

do $$ begin
  create type call_outcome as enum (
    'completed',
    'transferred',
    'referred',
    'abandoned',
    'after_hours',
    'error',
    'unknown'
  );
exception
  when duplicate_object then null;
end $$;

-- ---------------------------------------------------------------------------
-- staff
-- ---------------------------------------------------------------------------
create table if not exists staff (
  id uuid primary key default gen_random_uuid(),
  last_name text not null,
  first_legal text not null,
  first_preferred text,
  title text,
  extension text,
  external_number text,
  shareable boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists staff_last_name_idx on staff (lower(last_name));
create index if not exists staff_first_preferred_idx on staff (lower(first_preferred));
create index if not exists staff_first_legal_idx on staff (lower(first_legal));
create index if not exists staff_extension_idx on staff (extension);

-- ---------------------------------------------------------------------------
-- keyword_rules
-- ---------------------------------------------------------------------------
create table if not exists keyword_rules (
  id uuid primary key default gen_random_uuid(),
  keyword text not null,
  aliases text[] not null default '{}',
  action_type keyword_action_type not null,
  message text,
  target text,
  county_branches jsonb,
  followup_question text,
  flow_definition jsonb,
  active boolean not null default true,
  source_notes text,
  ambiguous boolean not null default false,
  ambiguity_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (keyword)
);

create index if not exists keyword_rules_keyword_idx on keyword_rules (lower(keyword));
create index if not exists keyword_rules_active_idx on keyword_rules (active);

-- ---------------------------------------------------------------------------
-- status_updates
-- ---------------------------------------------------------------------------
create table if not exists status_updates (
  id uuid primary key default gen_random_uuid(),
  effective_date date not null,
  message text not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists status_updates_active_idx on status_updates (active, effective_date desc);

-- ---------------------------------------------------------------------------
-- call_logs
-- ---------------------------------------------------------------------------
create table if not exists call_logs (
  id uuid primary key default gen_random_uuid(),
  call_sid text,
  room_name text,
  from_number text,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  transcript jsonb not null default '[]'::jsonb,
  matched_keywords text[] not null default '{}',
  tool_calls jsonb not null default '[]'::jsonb,
  transfer_target text,
  outcome call_outcome not null default 'unknown',
  latency_metrics jsonb not null default '{}'::jsonb,
  error text,
  created_at timestamptz not null default now()
);

create index if not exists call_logs_started_at_idx on call_logs (started_at desc);
create index if not exists call_logs_call_sid_idx on call_logs (call_sid);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists staff_set_updated_at on staff;
create trigger staff_set_updated_at
  before update on staff
  for each row execute function set_updated_at();

drop trigger if exists keyword_rules_set_updated_at on keyword_rules;
create trigger keyword_rules_set_updated_at
  before update on keyword_rules
  for each row execute function set_updated_at();

drop trigger if exists status_updates_set_updated_at on status_updates;
create trigger status_updates_set_updated_at
  before update on status_updates
  for each row execute function set_updated_at();
