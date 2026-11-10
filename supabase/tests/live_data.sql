-- Optional SQL Editor verification after migration. ALL test rows roll back.
begin;
create function pg_temp.live_fixture(espn_id bigint, rev text, points integer, source_at timestamptz)
returns jsonb language sql as $$
  select jsonb_build_object('leagueId',espn_id,'season',2027,'week',2,'scoringPeriod',12,
    'date','2026-10-31','schemaVersion',1,'revision',rev,'updatedAt',source_at,
    'teams',jsonb_build_array(jsonb_build_object('officialScore',points)),
    'matchups','[]'::jsonb,'games','[]'::jsonb);
$$;

do $$
declare
  fixture jsonb := pg_temp.live_fixture(90000000000001,repeat('a',64),10,now()-interval '1 minute');
  checked timestamptz := now()-interval '30 seconds';
  result jsonb;
  lid uuid;
  first_publication timestamptz;
begin
  if exists (select 1 from public.leagues where espn_league_id between 90000000000001 and 90000000000002) then
    raise exception 'Reserved SQL test identities already exist; no changes made';
  end if;
  if not (public.live_schema_status()->>'rls_enabled')::boolean
     or not (public.live_schema_status()->>'writer_restricted')::boolean
     or not (public.live_schema_status()->>'anonymous_read_only')::boolean then
    raise exception 'Security readiness failed';
  end if;
  result := public.publish_live_snapshot('nba',90000000000001,'SQL test NBA',true,fixture,checked);
  if result->>'action' <> 'inserted' then raise exception 'First insert failed'; end if;
  lid := (result->>'league_id')::uuid;
  select published_at into first_publication from public.live_snapshots where league_id=lid;
  result := public.publish_live_snapshot('nba',90000000000001,'SQL test NBA',true,fixture,checked);
  if result->>'action' <> 'unchanged' then raise exception 'Idempotence failed'; end if;
  result := public.publish_live_snapshot('nba',90000000000001,'SQL test NBA',true,fixture,now()-interval '20 seconds');
  if result->>'action' <> 'refreshed' or (select published_at from public.live_snapshots where league_id=lid) <> first_publication then
    raise exception 'Freshness-only check changed publication time';
  end if;
  result := public.publish_live_snapshot('nba',90000000000001,'SQL test NBA',true,
    pg_temp.live_fixture(90000000000001,repeat('b',64),20,now()-interval '15 seconds'),now()-interval '10 seconds');
  if result->>'action' <> 'updated' then raise exception 'Newer snapshot update failed'; end if;
  result := public.publish_live_snapshot('nba',90000000000001,'Must not change',false,fixture,now());
  if result->>'action' <> 'stale' or (select display_name from public.leagues where id=lid) <> 'SQL test NBA'
    or not (select is_public from public.leagues where id=lid) then raise exception 'Stale snapshot changed data/visibility'; end if;
  if (select count(*) from public.live_snapshots where league_id=lid) <> 1 then raise exception 'Unnecessary history rows'; end if;
  -- Same ESPN ID across sports is a different league, not a collision.
  perform public.publish_live_snapshot('nfl',90000000000001,'SQL test NFL',true,fixture,checked);
  perform public.publish_live_snapshot('nba',90000000000002,'SQL test private',false,
    pg_temp.live_fixture(90000000000002,repeat('c',64),30,now()-interval '1 minute'),checked);
  if (select count(*) from public.leagues where espn_league_id=90000000000001) <> 2 then raise exception 'Sport isolation failed'; end if;
  begin
    perform public.publish_live_snapshot('nba',90000000000001,'Bad identity',true,
      pg_temp.live_fixture(90000000000002,repeat('d',64),30,now()),now());
    raise exception 'Identity mismatch was accepted';
  exception when invalid_parameter_value then null;
  end;
end;
$$;

set local role anon;
do $$
begin
  if (select count(*) from public.leagues where espn_league_id between 90000000000001 and 90000000000002) <> 2 then
    raise exception 'Anonymous public/private league visibility failed';
  end if;
  if (select count(*) from public.live_snapshots s join public.leagues l on s.league_id=l.id
      where l.espn_league_id between 90000000000001 and 90000000000002) <> 2 then
    raise exception 'Anonymous public/private snapshot visibility failed';
  end if;
  begin
    insert into public.leagues(sport,espn_league_id,display_name) values('nba',90000000000003,'Must fail');
    raise exception 'Anonymous INSERT succeeded';
  exception when insufficient_privilege then null; end;
  begin
    update public.leagues set display_name='Must fail' where espn_league_id=90000000000001;
    raise exception 'Anonymous UPDATE succeeded';
  exception when insufficient_privilege then null; end;
  begin
    delete from public.leagues where espn_league_id=90000000000001;
    raise exception 'Anonymous DELETE succeeded';
  exception when insufficient_privilege then null; end;
  begin
    update public.live_snapshots set schema_version=1;
    raise exception 'Anonymous snapshot UPDATE succeeded';
  exception when insufficient_privilege then null; end;
end;
$$;
reset role;
rollback;
