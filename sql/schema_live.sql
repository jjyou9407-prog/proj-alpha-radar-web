-- Alpha Radar AI live schema
-- Supabase SQL 편집기에 통째로 붙여넣고 Run 실행

create table if not exists rankings (
  id bigserial primary key,
  symbol text not null,
  name text not null,
  market text not null check (market in ('US','KR')),
  score int not null,
  price numeric not null,
  entry_price numeric not null,
  stop_price numeric not null,
  target_price numeric not null,
  change_text text,
  reason text,
  beginner_note text,
  created_at timestamptz default now()
);

create table if not exists alerts (
  id bigserial primary key,
  symbol text not null,
  title text not null,
  message text not null,
  level text default 'info',
  created_at timestamptz default now()
);

create table if not exists watchlists (
  id bigserial primary key,
  symbol text not null,
  name text,
  market text,
  created_at timestamptz default now()
);

create table if not exists portfolio (
  id bigserial primary key,
  symbol text not null,
  name text,
  market text,
  avg_price numeric,
  quantity numeric,
  current_price numeric,
  profit_percent numeric,
  created_at timestamptz default now()
);

alter table rankings enable row level security;
alter table alerts enable row level security;
alter table watchlists enable row level security;
alter table portfolio enable row level security;

drop policy if exists "rankings public read" on rankings;
drop policy if exists "alerts public read" on alerts;
drop policy if exists "watchlists public read" on watchlists;
drop policy if exists "portfolio public read" on portfolio;

create policy "rankings public read" on rankings for select using (true);
create policy "alerts public read" on alerts for select using (true);
create policy "watchlists public read" on watchlists for select using (true);
create policy "portfolio public read" on portfolio for select using (true);

-- v1 hot news sidebar/feed
-- 무료 RSS/뉴스 기반 핫뉴스를 화면 오른쪽 고정 사이드바에 표시하기 위한 테이블입니다.
create table if not exists hot_news (
  id bigserial primary key,
  symbol text not null,
  name text,
  market text,
  title text not null,
  summary text,
  url text,
  source text,
  published_at timestamptz,
  sentiment text default 'neutral',
  hot_score int default 0,
  matched_keywords text,
  related_symbols text,
  created_at timestamptz default now()
);

alter table hot_news enable row level security;

drop policy if exists "hot_news public read" on hot_news;
create policy "hot_news public read" on hot_news for select using (true);

create index if not exists hot_news_score_idx on hot_news (hot_score desc, published_at desc);
create index if not exists hot_news_symbol_idx on hot_news (symbol);

insert into watchlists (symbol, name, market)
select 'NVDA', '엔비디아', 'US'
where not exists (select 1 from watchlists where symbol='NVDA');

insert into watchlists (symbol, name, market)
select 'TSLA', '테슬라', 'US'
where not exists (select 1 from watchlists where symbol='TSLA');

insert into watchlists (symbol, name, market)
select '000660', 'SK하이닉스', 'KR'
where not exists (select 1 from watchlists where symbol='000660');
