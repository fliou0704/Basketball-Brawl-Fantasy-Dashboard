-- Stage 2A: apply once in Supabase SQL Editor. No existing data is deleted.
begin;

create table public.leagues (
  id uuid primary key default gen_random_uuid(),
  sport text not null check (sport in ('nba', 'nfl')),
  espn_league_id bigint not null check (espn_league_id > 0),
  display_name text not null check (length(display_name) between 1 and 160),
  is_public boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (sport, espn_league_id)
);

-- One current row per league/season. A period rollover replaces that row.
create table public.live_snapshots (
  league_id uuid not null references public.leagues(id) on delete restrict,
  season integer not null check (season between 2000 and 2200),
  matchup_period integer not null check (matchup_period > 0),
  scoring_period integer not null check (scoring_period > 0),
  scoring_date date not null,
  schema_version integer not null check (schema_version = 1),
  revision text not null check (revision ~ '^[a-f0-9]{64}$'),
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'),
  source_updated_at timestamptz not null,
  verified_at timestamptz not null,
  published_at timestamptz not null default now(),
  primary key (league_id, season),
  check (source_updated_at <= verified_at),
  check ((snapshot->>'leagueId')::bigint > 0),
  check ((snapshot->>'schemaVersion')::integer = schema_version),
  check ((snapshot->>'season')::integer = season),
  check ((snapshot->>'week')::integer = matchup_period),
  check ((snapshot->>'scoringPeriod')::integer = scoring_period),
  check ((snapshot->>'date')::date = scoring_date),
  check (snapshot->>'revision' = revision)
);
-- The PK and natural-key UNIQUE constraints provide the needed lookup indexes.

alter table public.leagues enable row level security;
alter table public.live_snapshots enable row level security;
revoke all on public.leagues, public.live_snapshots from public, anon, authenticated;
grant usage on schema public to anon, authenticated, service_role;
grant select on public.leagues, public.live_snapshots to anon, authenticated;
grant select, insert, update on public.leagues, public.live_snapshots to service_role;

create policy public_leagues_read on public.leagues for select
  to anon, authenticated using (is_public);
create policy public_snapshots_read on public.live_snapshots for select
  to anon, authenticated using (
    exists (select 1 from public.leagues l
            where l.id = live_snapshots.league_id and l.is_public)
  );

create function public.publish_live_snapshot(
  p_sport text, p_espn_league_id bigint, p_display_name text,
  p_is_public boolean, p_snapshot jsonb, p_verified_at timestamptz
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
  v_league uuid;
  v_season integer;
  v_period integer;
  v_week integer;
  v_source timestamptz;
  v_old public.live_snapshots%rowtype;
  v_action text;
begin
  if p_sport not in ('nba','nfl') or p_espn_league_id <= 0
     or p_is_public is null or p_display_name is null
     or length(p_display_name) not between 1 and 160
     or p_snapshot is null or jsonb_typeof(p_snapshot) <> 'object'
     or not (p_snapshot ?& array['leagueId','season','week','scoringPeriod','date',
                                'schemaVersion','revision','updatedAt','teams','matchups','games'])
     or (p_snapshot->>'leagueId')::bigint is distinct from p_espn_league_id
     or (p_snapshot->>'schemaVersion')::integer is distinct from 1
     or coalesce(p_snapshot->>'revision','') !~ '^[a-f0-9]{64}$'
     or p_snapshot ?| array['cookies','credentials','headers','cache','espn_s2','SWID']
     or p_verified_at is null or p_verified_at > now() + interval '5 minutes'
     or p_verified_at < now() - interval '10 minutes' then
    raise exception 'Invalid or stale live snapshot' using errcode = '22023';
  end if;
  v_season := (p_snapshot->>'season')::integer;
  v_period := (p_snapshot->>'scoringPeriod')::integer;
  v_week := (p_snapshot->>'week')::integer;
  v_source := (p_snapshot->>'updatedAt')::timestamptz;
  if v_source is null or v_source > p_verified_at then
    raise exception 'Invalid snapshot provenance' using errcode = '22023';
  end if;

  insert into public.leagues (sport,espn_league_id,display_name,is_public)
    values (p_sport,p_espn_league_id,p_display_name,p_is_public)
    on conflict (sport,espn_league_id) do nothing;
  -- Serialize all publishers for this league, including first insert and rollover.
  select id into strict v_league from public.leagues
    where sport=p_sport and espn_league_id=p_espn_league_id for update;
  select * into v_old from public.live_snapshots
    where league_id=v_league and season=v_season for update;

  if found then
    if v_period < v_old.scoring_period or v_week < v_old.matchup_period
       or v_source < v_old.source_updated_at or p_verified_at < v_old.verified_at then
      return jsonb_build_object('action','stale','league_id',v_league,'revision',v_old.revision);
    end if;
    if v_old.revision = p_snapshot->>'revision' then
      if v_old.snapshot <> p_snapshot then
        raise exception 'Snapshot revision conflict' using errcode = '22023';
      end if;
      v_action := 'unchanged';
      -- This is a necessary freshness heartbeat, not a new content publication.
      if p_verified_at > v_old.verified_at then
        update public.live_snapshots set verified_at=p_verified_at
          where league_id=v_league and season=v_season;
        v_action := 'refreshed';
      end if;
    else
      if p_verified_at <= v_old.verified_at or v_source <= v_old.source_updated_at then
        return jsonb_build_object('action','stale','league_id',v_league,'revision',v_old.revision);
      end if;
      update public.live_snapshots set
        matchup_period=v_week, scoring_period=v_period, scoring_date=(p_snapshot->>'date')::date,
        schema_version=1, revision=p_snapshot->>'revision',snapshot=p_snapshot,
        source_updated_at=v_source,verified_at=p_verified_at,published_at=now()
        where league_id=v_league and season=v_season;
      v_action := 'updated';
    end if;
  else
    insert into public.live_snapshots
      (league_id,season,matchup_period,scoring_period,scoring_date,schema_version,
       revision,snapshot,source_updated_at,verified_at)
      values (v_league,v_season,v_week,v_period,(p_snapshot->>'date')::date,1,
              p_snapshot->>'revision',p_snapshot,v_source,p_verified_at);
    v_action := 'inserted';
  end if;
  update public.leagues set display_name=p_display_name,is_public=p_is_public,updated_at=now()
    where id=v_league and (display_name,is_public) is distinct from (p_display_name,p_is_public);
  return jsonb_build_object('action',v_action,'league_id',v_league,'revision',p_snapshot->>'revision');
end;
$$;
revoke all on function public.publish_live_snapshot(text,bigint,text,boolean,jsonb,timestamptz)
  from public, anon, authenticated;
grant execute on function public.publish_live_snapshot(text,bigint,text,boolean,jsonb,timestamptz)
  to service_role;

-- Read-only readiness check. Does not reveal keys or existing data.
create function public.live_schema_status() returns jsonb language sql
  security invoker set search_path = '' as $$
  select jsonb_build_object(
    'version',1,
    'rls_enabled',(select bool_and(relrowsecurity) and count(*)=2 from pg_catalog.pg_class
      where oid in ('public.leagues'::regclass,'public.live_snapshots'::regclass)),
    'anonymous_read_only',
      has_table_privilege('anon','public.leagues','SELECT') and
      has_table_privilege('anon','public.live_snapshots','SELECT') and
      not has_table_privilege('anon','public.leagues','INSERT,UPDATE,DELETE,TRUNCATE') and
      not has_table_privilege('anon','public.live_snapshots','INSERT,UPDATE,DELETE,TRUNCATE'),
    'authenticated_read_only',
      not has_table_privilege('authenticated','public.leagues','INSERT,UPDATE,DELETE,TRUNCATE') and
      not has_table_privilege('authenticated','public.live_snapshots','INSERT,UPDATE,DELETE,TRUNCATE'),
    'writer_restricted',
      not has_function_privilege('anon','public.publish_live_snapshot(text,bigint,text,boolean,jsonb,timestamptz)','EXECUTE') and
      not has_function_privilege('authenticated','public.publish_live_snapshot(text,bigint,text,boolean,jsonb,timestamptz)','EXECUTE'),
    'select_policies_only',(select count(*)=2 and bool_and(cmd='SELECT') from pg_catalog.pg_policies
      where schemaname='public' and tablename in ('leagues','live_snapshots'))
  );
$$;
revoke all on function public.live_schema_status() from public,anon,authenticated;
grant execute on function public.live_schema_status() to service_role;
notify pgrst, 'reload schema';
commit;
