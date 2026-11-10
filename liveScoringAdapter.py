"""Unpublished, one-shot current-period ESPN snapshot. Never writes canonical data."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time

import requests
from espn_api.requests.espn_requests import EspnFantasyRequests
from espn_api.basketball.constant import POSITION_MAP, STATS_MAP
from dataUpdateSafety import require_espn_credentials
from espnFantasyCalendar import verified, context as calendar_context
from nbaSchedule import NY, SCOREBOARD_URL, instant

ROOT = Path(__file__).resolve().parent
VIEWS = ['mMatchupScore', 'mScoreboard', 'mSettings']
STALE_AFTER = timedelta(minutes=10)
CACHE_VERSION = 1  # Bump when normalized cached component semantics change.


class AdapterError(ValueError):
    """Messages are fixed/allowlisted: never include authenticated API exceptions."""


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n').encode()


def number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise AdapterError('Missing or invalid numeric scoring data')
    return round(value, 4)


def identity(value, zero=False):
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if zero else 1):
        raise AdapterError('Missing or invalid stable identity')
    return value


def normalize_player(entry, season, period, tid, slots, counts):
    pool=entry['playerPoolEntry'];p=pool['player'];pid=identity(p['id'])
    if entry['playerId']!=pid or pool['onTeamId']!=tid:
        raise AdapterError('Conflicting current player ownership')
    slot=entry['lineupSlotId']
    if slot not in POSITION_MAP or slot not in {int(k) for k,v in counts.items() if v}:
        raise AdapterError('Unknown fantasy lineup slot')
    stats=[s for s in p.get('stats',[]) if s.get('statSourceId')==0 and s.get('statSplitTypeId')==5 and s.get('scoringPeriodId')==period and s.get('seasonId')==season]
    if len(stats)>1:
        raise AdapterError('Conflicting current player statistics')
    actual=stats[0] if stats else None
    points=number(pool['appliedStatTotal'])
    # Keep the official roster scalar and raw actual stat evidence distinct.
    raw_stats={STATS_MAP.get(str(k),str(k)):number(v) for k,v in (actual or {}).get('stats',{}).items()}
    eligibility=sorted({identity(i,zero=True) for i in p['eligibleSlots']})
    return {'playerId':pid,'teamId':tid,'name':str(p['fullName']),
        'proTeamId':identity(p['proTeamId'],zero=True),'slotId':slot,'slot':POSITION_MAP[slot],
        'eligibleSlotIds':eligibility,'scoringEligible':slot in slots,
        'fantasyPoints':points,'creditedPoints':points if slot in slots else 0,
        'statPoints':number(actual['appliedTotal']) if actual and 'appliedTotal' in actual else None,
        'hasActualStats':actual is not None,'played':raw_stats['MIN']>0 if 'MIN' in raw_stats else None,
        'statProTeamId':identity(actual['proTeamId'],zero=True) if actual and 'proTeamId' in actual else None,
        'stats':raw_stats,'injuryStatus':p.get('injuryStatus') if p.get('injuryStatus') in ('ACTIVE','DAY_TO_DAY','OUT','PROBABLE','QUESTIONABLE','DOUBTFUL') else 'UNKNOWN'}


def normalize_league(raw, season, league_id, metadata):
    """Allowlist only current lineups/stats; no owners, historical logs or projections."""
    try:
        if raw['seasonId'] != season or raw['id'] != league_id:
            raise AdapterError('League response identity mismatch')
        period = identity(raw['scoringPeriodId'])
        week = identity(raw['status']['currentMatchupPeriod'])
        if period!=raw['status']['latestScoringPeriod']:
            raise AdapterError('Response is not the current fantasy scoring period')
        if not raw['status']['firstScoringPeriod'] <= period <= raw['status']['finalScoringPeriod']:
            raise AdapterError('No active fantasy scoring period')
        saved = next(s for s in metadata['seasons'] if s['season']==season)
        calendar = verified(saved)
        day = next(d for d in (calendar or {}).get('days', []) if d['period']==period)
        if calendar['context']!=calendar_context(raw):
            raise AdapterError('Verified calendar configuration no longer matches ESPN')
        if day['week'] != week:
            raise AdapterError('Verified fantasy calendar disagrees with ESPN period')
        settings = raw['settings']
        if settings['scoringSettings']['scoringType'] != 'H2H_POINTS':
            raise AdapterError('Only verified H2H points scoring is supported')
        counts = settings['rosterSettings']['lineupSlotCounts']
        slots = {int(k) for k,v in counts.items() if v and POSITION_MAP.get(int(k)) not in ('BE','IR','')}
        if not slots or any(s not in POSITION_MAP for s in slots):
            raise AdapterError('Unsupported active lineup slots')
        names = {identity(t['id']):str(t['name']) for t in raw['teams']}
        if len(names)!=settings['size'] or len(raw['teams'])!=len(names):
            raise AdapterError('Incomplete fantasy team coverage')
        teams, matches, seen_players = {}, [], set()
        for match in sorted(raw['schedule'],key=lambda m:m['id']):
            if match['matchupPeriodId'] != week:
                continue
            sides=[]
            for side in ('home','away'):
                if not match.get(side,{}).get('teamId'):
                    continue
                source=match[side];tid=identity(source['teamId'])
                if tid not in names or tid in teams:
                    raise AdapterError('Conflicting fantasy matchup ownership')
                roster=source['rosterForCurrentScoringPeriod']
                entries=roster['entries']
                if not isinstance(entries,list) or not entries:
                    raise AdapterError('Missing current fantasy roster')
                players=[]
                for entry in entries:
                    player=normalize_player(entry,season,period,tid,slots,counts)
                    if player['playerId'] in seen_players:raise AdapterError('Conflicting current player ownership')
                    seen_players.add(player['playerId']);players.append(player)
                period_scores={str(identity(int(k))):number(v) for k,v in source['pointsByScoringPeriod'].items() if any(d['period']==int(k) and d['week']==week for d in calendar['days']) and int(k)<=period}
                if str(period) not in period_scores:
                    raise AdapterError('Missing official current-period score')
                score_field='totalPointsLive' if source.get('totalPointsLive') is not None else 'totalPoints'
                official=number(source[score_field]);daily=number(roster['appliedStatTotal'])
                credited=round(sum(p['creditedPoints'] for p in players),4)
                teams[tid]={'teamId':tid,'name':names[tid],'officialScore':official,'officialScoreField':score_field,
                    'officialPeriodScores':period_scores,'officialDailyScore':period_scores[str(period)],
                    'rosterDailyScore':daily,'playerCreditedSum':credited,
                    'dailyDifference':round(period_scores[str(period)]-credited,4),
                    'periodSumDifference':round(official-sum(period_scores.values()),4),
                    'players':sorted(players,key=lambda p:p['playerId'])}
                sides.append(tid)
            if not sides:
                raise AdapterError('Empty current fantasy matchup')
            matches.append({'matchupId':identity(match['id']),'teamIds':sides,
                            'officialScores':[teams[t]['officialScore'] for t in sides],
                            'winner':match.get('winner') if match.get('winner') in ('HOME','AWAY','TIE','UNDECIDED') else 'UNKNOWN'})
        if set(teams)!=set(names):
            raise AdapterError('Incomplete current matchup/roster coverage')
        return {'leagueId':league_id,'season':season,'week':week,'scoringPeriod':period,'date':day['date'],
                'teams':list(teams.values()),'matchups':matches,'calendarContextHash':digest(calendar['context']),
                'lineupSlotCounts':{POSITION_MAP[int(k)]:v for k,v in counts.items() if v},
                'scoreAuthority':'ESPN official matchup totals; player sums are diagnostic only'}
    except AdapterError:
        raise
    except (KeyError,TypeError,ValueError,StopIteration,AttributeError,IndexError):
        raise AdapterError('Incomplete or incompatible current league response/calendar') from None


def normalize_games(raw, day, season):
    """Actual public status, never the SDK's tipoff-plus-three-hours estimate."""
    try:
        if not isinstance(raw.get('events'),list) or not raw.get('leagues'):
            raise AdapterError('Incomplete NBA scoreboard')
        games=[];seen=set()
        for event in raw['events']:
            if event['season']['year']!=season:
                raise AdapterError('NBA scoreboard season mismatch')
            comp=event['competitions'][0];start=instant(event['date'])
            if start.astimezone(NY).date().isoformat()!=day:
                continue
            if event['season']['type']!=2 or str(comp['type']['id'])=='39':
                continue
            gid=identity(int(event['id']));state=event['status']['type'];name=state['name']
            status=('postponed' if 'POSTPON' in name or 'SUSPEND' in name else 'canceled' if 'CANCEL' in name else
                    'completed' if state.get('completed') is True else 'in-progress' if state['state']=='in' else 'scheduled' if state['state']=='pre' else 'unknown')
            opponents={c['homeAway']:identity(int(c['id'])) for c in comp['competitors']}
            if gid in seen or set(opponents)!= {'home','away'} or opponents['home']==opponents['away']:
                raise AdapterError('Conflicting NBA game identity')
            seen.add(gid)
            games.append({'gameId':gid,'date':day,'start':start.isoformat(),'homeTeamId':opponents['home'],
                'awayTeamId':opponents['away'],'status':status,'statusName':name,
                'clock':str(event['status'].get('displayClock','')),'period':event['status'].get('period'),
                'timeTBD':comp.get('timeValid') is not True})
        return {'date':day,'games':sorted(games,key=lambda g:g['gameId'])}
    except AdapterError:
        raise
    except (KeyError,ValueError,TypeError,IndexError,AttributeError):
        raise AdapterError('Incomplete or incompatible NBA scoreboard') from None


def assemble(league, nba, metadata):
    try:
        saved=next(s for s in metadata['seasons'] if s['season']==league['season'])
        calendar=verified(saved)
        day=next(d for d in (calendar or {}).get('days',[]) if d['period']==league['scoringPeriod'])
        if digest(calendar['context'])!=league['calendarContextHash'] or (day['date'],day['week'])!=(league['date'],league['week']):
            raise AdapterError('Cached snapshot calendar mismatch')
    except (KeyError,TypeError,StopIteration):
        raise AdapterError('Verified calendar is unavailable for cached snapshot') from None
    value=deepcopy(league);value['games']=nba['games'];value['schemaVersion']=1
    value['gameAssociation']='Current-period stat NBA team when provided; otherwise current NBA affiliation. Fixtures are not appearance evidence.'
    schedule=metadata.get('nbaSchedules',{}).get(str(value['season']),{})
    expected={g['id'] for g in schedule.get('fixtures',[]) if g['date']==value['date'] and g['regularSeason'] and g['status'] not in ('canceled','replaced')}
    received={g['gameId'] for g in value['games']}
    if expected-received:
        raise AdapterError('NBA scoreboard omitted known current-date fixtures')
    by_team={}
    for g in value['games']:
        for tid in (g['homeTeamId'],g['awayTeamId']):by_team.setdefault(tid,[]).append(g['gameId'])
    for t in value['teams']:
        for p in t['players']:
            p['gameIds']=by_team.get(p['statProTeamId'] or p['proTeamId'],[])
            # No event means unknown/no published game, never an invented final or DNP.
            p['gameCoverage']='confirmed' if p['gameIds'] else 'free-agent' if p['proTeamId']==0 else 'no-event-observed'
    return value


def freshness(state, now):
    try:
        age=(now-instant(state['verifiedAt'])).total_seconds()
        return {'stale':age<0 or age>STALE_AFTER.total_seconds(),'ageSeconds':max(0,round(age))}
    except (KeyError,ValueError,TypeError):
        return {'stale':True,'ageSeconds':None}


class Client:
    def __init__(self, session=None, sleep=time.sleep):
        self.session=session or requests.Session();self.public_session=session or requests.Session();self.sleep=sleep
        self.metrics={'requests':0,'responseBytes':0,'notModified':0}

    def read(self, url, params, cookies, old, normalize):
        headers={'If-None-Match':old['etag']} if old and old.get('etag') else {}
        for attempt in range(3):
            self.metrics['requests']+=1
            try:
                r=(self.session if cookies else self.public_session).get(url,params=params,cookies=cookies,headers=headers,timeout=(10,35),allow_redirects=False)
                self.metrics['responseBytes']+=len(r.content)
                if len(r.content)>20_000_000:raise AdapterError('Oversized ESPN response; last good snapshot retained')
                if r.status_code in (401,403):raise AdapterError('ESPN authentication/access denied; check configured credentials')
                if r.status_code==304:
                    if not old or 'data' not in old:raise AdapterError('304 without a validated cached snapshot')
                    self.metrics['notModified']+=1
                    return deepcopy(old)
                if r.status_code in (429,500,502,503,504):
                    if attempt==2:raise AdapterError('ESPN transient failure; retry budget exhausted')
                    delay=2**attempt
                    retry=r.headers.get('Retry-After')
                    if retry:
                        try:delay=max(delay,float(retry))
                        except ValueError:raise AdapterError('ESPN requested a deferred retry') from None
                        if delay>10:raise AdapterError('ESPN requested a deferred retry')
                    self.sleep(delay);continue
                if r.status_code!=200:raise AdapterError('Unexpected ESPN response; last good snapshot retained')
                data=normalize(r.json())
                return {'etag':r.headers.get('ETag'),'data':data}
            except (requests.RequestException,ValueError) as error:
                if isinstance(error,AdapterError):raise
                if not isinstance(error,requests.RequestException):raise AdapterError('Invalid ESPN JSON; last good snapshot retained') from None
                if attempt==2:raise AdapterError('ESPN connection failed; retry budget exhausted') from None
                self.sleep(2**attempt)


def atomic(path, value):
    content=encoded(value)
    if path.exists() and path.read_bytes()==content:return False
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
    return True


@contextmanager
def locked(output):
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.with_suffix(output.suffix+'.lock').open('a') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise AdapterError('Another live adapter execution owns this output') from None
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


def safe_output(output):
    output=Path(output).resolve()
    # An explicit external destination prevents accidental Pages/canonical publication.
    if output==ROOT or ROOT in output.parents:
        raise AdapterError('Live output must be outside the repository')
    return output


def changed_entities(previous, value):
    result={'baseRevision':(previous or {}).get('revision')}
    for key,ident in (('teams','teamId'),('matchups','matchupId'),('games','gameId')):
        before={r[ident]:r for r in (previous or {}).get(key,[])};after={r[ident]:r for r in value[key]}
        result[key]=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
    before={p['playerId']:p for t in (previous or {}).get('teams',[])for p in t['players']}
    after={p['playerId']:p for t in value['teams']for p in t['players']}
    result['players']=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
    return result


def run(output, metadata, season, league_id=609694684, client=None, now=None, credentials=None):
    started=time.monotonic();now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise AdapterError('Adapter clock must include timezone')
    output=safe_output(output);state_path=output.with_suffix(output.suffix+'.state.json')
    with locked(output):
        try:
            previous=json.loads(output.read_text()) if output.exists() else None
            state=json.loads(state_path.read_text()) if state_path.exists() else {}
            if not isinstance(state,dict):raise AdapterError('Invalid local live cache; existing files retained')
            if state and (state.get('schemaVersion')!=1 or state.get('adapterVersion')!=CACHE_VERSION or state.get('leagueId')!=league_id or state.get('season')!=season):state={}
            if not isinstance(state,dict) or previous is not None and not isinstance(previous,dict):
                raise AdapterError('Invalid local live cache; existing files retained')
            if previous and (previous.get('schemaVersion')!=1 or previous.get('revision')!=digest({k:v for k,v in previous.items() if k not in ('revision','updatedAt','changes')})):
                raise AdapterError('Invalid local snapshot revision; existing files retained')
            cache=state.get('cache',{})
            # Never reuse a partially published cache after a crash or manual corruption.
            if previous and state.get('revision')!=previous.get('revision'):cache={}
        except (OSError,ValueError,TypeError):
            raise AdapterError('Invalid local live cache; existing files retained') from None
        client=client or Client();stamp=now.astimezone(timezone.utc).isoformat()
        try:
            swid,s2=credentials if credentials is not None else require_espn_credentials()
            api=EspnFantasyRequests('nba',season,league_id,cookies={'espn_s2':s2,'SWID':swid})
            old=cache.get('league')
            if old and digest(old.get('data'))!=old.get('hash'):old=None
            league=client.read(api.LEAGUE_ENDPOINT,{'view':VIEWS},api.cookies,old,
                               lambda raw:normalize_league(raw,season,league_id,metadata))
            if league['data']['season']!=season or league['data']['leagueId']!=league_id:raise AdapterError('Cached league identity mismatch')
            old_nba=cache.get('nba')
            if old_nba and (old_nba.get('data',{}).get('date')!=league['data']['date'] or digest(old_nba.get('data'))!=old_nba.get('hash')):old_nba=None
            nba=client.read(SCOREBOARD_URL,{'dates':league['data']['date'].replace('-',''),'limit':100},None,old_nba,
                           lambda raw:normalize_games(raw,league['data']['date'],season))
            candidate=assemble(league['data'],nba['data'],metadata)
            if previous and (previous['season'],previous['scoringPeriod'])>(season,candidate['scoringPeriod']):raise AdapterError('ESPN response would regress current scoring period')
            revision=digest(candidate)
            changed=not previous or previous['revision']!=revision
            if changed:
                candidate.update(revision=revision,updatedAt=stamp,changes=changed_entities(previous,candidate))
                atomic(output,candidate)
            for component in (league,nba):component['hash']=digest(component['data'])
            state={'schemaVersion':1,'adapterVersion':CACHE_VERSION,'leagueId':league_id,'season':season,'revision':revision,
                   'lastAttemptAt':stamp,'verifiedAt':stamp,'error':None,'cache':{'league':league,'nba':nba}}
            state['freshness']=freshness(state,now)
            atomic(state_path,state)
            return {'changed':changed,'revision':revision,'snapshotBytes':output.stat().st_size,
                    **client.metrics,'seconds':round(time.monotonic()-started,3),'freshness':state['freshness']}
        except (AdapterError,RuntimeError,KeyError,TypeError,IndexError,AttributeError) as error:
            # Only our fixed AdapterError messages or missing-variable names escape.
            message=str(error) if isinstance(error,AdapterError) or str(error).startswith('Missing ESPN credentials.') else 'Live adapter failed; last good snapshot retained'
            state.update(schemaVersion=1,adapterVersion=CACHE_VERSION,leagueId=league_id,season=season,lastAttemptAt=stamp,error=message)
            state['freshness']=freshness(state,now);atomic(state_path,state)
            raise AdapterError(message) from None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True,help='Explicit local JSON path outside the repository')
    p.add_argument('--metadata',type=Path,default=ROOT/'data/seasonMetadata.json',help='Read-only verified fantasy calendar/fixture metadata')
    p.add_argument('--season',type=int,required=True)
    p.add_argument('--league-id',type=int,default=609694684)
    args=p.parse_args()
    try:
        metadata=json.loads(args.metadata.read_text())
        print(json.dumps(run(args.output,metadata,args.season,args.league_id),sort_keys=True))
    except (AdapterError,OSError,ValueError):
        # Never stringify unexpected library exceptions (the SDK can include cookies).
        import sys
        error=sys.exc_info()[1]
        print(str(error) if isinstance(error,AdapterError) else 'Invalid adapter input or local file access',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
