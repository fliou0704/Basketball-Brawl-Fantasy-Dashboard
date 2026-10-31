"""One-shot Supabase publication of the existing allowlisted live snapshot."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import requests
from liveScoringAdapter import digest, encoded, identity, number, freshness, run as generate
from nbaSchedule import instant, NY

ROOT = Path(__file__).resolve().parent
MIGRATION = 'supabase/migrations/202610310001_live_data.sql'
TOP = set('schemaVersion leagueId season week scoringPeriod date calendarContextHash teams matchups lineupSlotCounts scoreAuthority gameAssociation games revision updatedAt changes'.split())
TEAM = set('teamId name officialScore officialScoreField officialPeriodScores officialDailyScore rosterDailyScore playerCreditedSum dailyDifference periodSumDifference players'.split())
PLAYER = set('playerId teamId name proTeamId slotId slot eligibleSlotIds scoringEligible fantasyPoints creditedPoints statPoints hasActualStats played statProTeamId stats injuryStatus gameIds gameCoverage'.split())
GAME = set('gameId date start homeTeamId awayTeamId status statusName clock period timeTBD'.split())
MATCH = set('matchupId teamIds officialScores winner'.split())
CHANGES = set('baseRevision teams matchups games players'.split())
FORBIDDEN = set('espns2 swid cookies cookie credentials authorization headers password token accesstoken refreshtoken secret secretkey supabasesecretkey cache owners owner'.split())


class PublisherError(ValueError):
    """Only fixed, non-sensitive messages are reported by the CLI."""


def shape(value, fields):
    if not isinstance(value,dict) or set(value)!=fields:
        raise PublisherError('Snapshot contains missing or unapproved fields')


def scan(value):
    if isinstance(value,dict):
        for k,v in value.items():
            if re.sub('[^a-z0-9]','',k.lower()) in FORBIDDEN:
                raise PublisherError('Snapshot contains a forbidden sensitive field')
            scan(v)
    elif isinstance(value,list):
        for v in value:scan(v)
    elif value is not None and not isinstance(value,(str,int,float,bool)):
        raise PublisherError('Snapshot is not JSON data')
    elif isinstance(value,str):
        if 'sb_secret_' in value or 'sb_publishable_' in value:
            raise PublisherError('Snapshot contains an API key marker')
        # Defense in depth for accidental actual credential values inside text.
        for name in ('ESPN_S2','SWID','SUPABASE_SECRET_KEY','SUPABASE_PUBLISHABLE_KEY'):
            secret=os.environ.get(name,'')
            if len(secret)>=12 and secret in value:
                raise PublisherError('Snapshot contains configured credentials')


def text(value, maximum=200):
    if not isinstance(value,str) or not 1<=len(value)<=maximum:
        raise PublisherError('Invalid snapshot text field')


def boolean(value):
    if not isinstance(value,bool):raise PublisherError('Invalid snapshot boolean field')


def validate(snapshot, league_id, verified_at, now=None):
    """Validate the Stage 1 contract; never re-normalize or recalculate scoring."""
    try:
        scan(snapshot);shape(snapshot,TOP)
        if identity(snapshot['schemaVersion'])!=1:
            raise PublisherError('Unsupported snapshot schema version')
        if identity(snapshot['leagueId'])!=identity(league_id):raise PublisherError('Snapshot league identity mismatch')
        if not 2000<=identity(snapshot['season'])<=2200:raise PublisherError('Invalid fantasy season')
        identity(snapshot['week']);identity(snapshot['scoringPeriod']);date.fromisoformat(snapshot['date'])
        if not re.fullmatch('[a-f0-9]{64}',snapshot['calendarContextHash']):raise PublisherError('Invalid calendar provenance')
        if snapshot['revision']!=digest({k:v for k,v in snapshot.items()if k not in ('revision','updatedAt','changes')}):
            raise PublisherError('Snapshot content hash mismatch')
        checked=instant(verified_at);source=instant(snapshot['updatedAt']);now=now or datetime.now(timezone.utc)
        if source>checked or checked>now+timedelta(minutes=5) or freshness({'verifiedAt':verified_at},now)['stale']:
            raise PublisherError('Snapshot verification is stale or has invalid timestamps')
        if not snapshot['teams'] or not snapshot['matchups']:raise PublisherError('Empty live snapshot')
        text(snapshot['scoreAuthority'],500);text(snapshot['gameAssociation'],500)
        teams=set();players=set();game_ids=set();matched=set();matches=set()
        for g in snapshot['games']:
            shape(g,GAME);gid=identity(g['gameId'])
            if gid in game_ids:raise PublisherError('Duplicate NBA game identity')
            game_ids.add(gid);identity(g['homeTeamId']);identity(g['awayTeamId']);start=instant(g['start'])
            boolean(g['timeTBD']);text(g['statusName'],64)
            if not isinstance(g['clock'],str) or len(g['clock'])>32:raise PublisherError('Invalid game clock')
            if g['period'] is not None:identity(g['period'],zero=True)
            if g['status'] not in ('scheduled','in-progress','completed','postponed','canceled','unknown') or start.astimezone(NY).date().isoformat()!=g['date']:raise PublisherError('Invalid game status/date')
            if g['date']!=snapshot['date'] or g['homeTeamId']==g['awayTeamId']:raise PublisherError('Invalid game date or teams')
        for t in snapshot['teams']:
            shape(t,TEAM);tid=identity(t['teamId'])
            if tid in teams:raise PublisherError('Duplicate fantasy team identity')
            teams.add(tid);text(t['name'])
            for k in ('officialScore','officialDailyScore','rosterDailyScore','playerCreditedSum','dailyDifference','periodSumDifference'):number(t[k])
            for period,points in t['officialPeriodScores'].items():identity(int(period));number(points)
            if t['officialScoreField'] not in ('totalPoints','totalPointsLive'):raise PublisherError('Unknown official score source')
            if not t['players']:raise PublisherError('Missing current roster')
            for p in t['players']:
                shape(p,PLAYER);pid=identity(p['playerId'])
                if pid in players or p['teamId']!=tid:raise PublisherError('Conflicting player ownership')
                players.add(pid);identity(p['proTeamId'],zero=True);identity(p['slotId'],zero=True);text(p['name']);text(p['slot'],16)
                boolean(p['scoringEligible']);boolean(p['hasActualStats'])
                if p['played'] is not None:boolean(p['played'])
                if p['statProTeamId'] is not None:identity(p['statProTeamId'],zero=True)
                for sid in p['eligibleSlotIds']:identity(sid,zero=True)
                for gid in p['gameIds']:identity(gid)
                if p['injuryStatus'] not in ('ACTIVE','DAY_TO_DAY','OUT','PROBABLE','QUESTIONABLE','DOUBTFUL','UNKNOWN') or p['gameCoverage'] not in ('confirmed','free-agent','no-event-observed'):raise PublisherError('Unapproved player status')
                for key in ('fantasyPoints','creditedPoints'):number(p[key])
                if p['statPoints'] is not None:number(p['statPoints'])
                for key,value in p['stats'].items():
                    if not re.fullmatch('[A-Za-z0-9%_+/.\-]{1,32}',key):raise PublisherError('Unapproved stat field')
                    number(value)
                if not set(p['gameIds'])<=game_ids:raise PublisherError('Unresolved player game identity')
        for m in snapshot['matchups']:
            shape(m,MATCH);mid=identity(m['matchupId'])
            if mid in matches or m['winner'] not in ('HOME','AWAY','TIE','UNDECIDED','UNKNOWN'):raise PublisherError('Conflicting matchup identity/status')
            matches.add(mid)
            if not 1<=len(m['teamIds'])<=2 or len(m['teamIds'])!=len(m['officialScores']):raise PublisherError('Invalid matchup sides')
            for tid,score in zip(m['teamIds'],m['officialScores']):
                if tid not in teams or tid in matched:raise PublisherError('Invalid matchup team assignment')
                matched.add(tid);number(score)
                if next(t['officialScore']for t in snapshot['teams']if t['teamId']==tid)!=score:raise PublisherError('Conflicting official matchup score')
        if matched!=teams:raise PublisherError('Incomplete matchup coverage')
        shape(snapshot['changes'],CHANGES)
        if snapshot['changes']['baseRevision'] is not None and not re.fullmatch('[a-f0-9]{64}',snapshot['changes']['baseRevision']):raise PublisherError('Invalid change provenance')
        for key in ('teams','players','games','matchups'):
            for item in snapshot['changes'][key]:identity(item)
        for k,v in snapshot['lineupSlotCounts'].items():
            if not re.fullmatch('[A-Za-z0-9_/-]{1,16}',k):raise PublisherError('Unapproved lineup field')
            identity(v,zero=True)
        if len(encoded(snapshot))>2_000_000:raise PublisherError('Live snapshot exceeds size budget')
        return {'season':snapshot['season'],'revision':snapshot['revision'],'snapshotBytes':len(encoded(snapshot)),
                'teams':len(teams),'players':len(players),'verifiedAt':checked.isoformat()}
    except PublisherError:raise
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError):
        raise PublisherError('Invalid live snapshot contract') from None


class Config:
    def __init__(self, url, secret, publishable=None):
        u=urlsplit(url)
        if u.scheme!='https' or not re.fullmatch('[a-z0-9-]+\.supabase\.co',u.hostname or '') or u.username or u.port or u.query or u.fragment or u.path not in ('','/'):
            raise PublisherError('SUPABASE_URL must be the HTTPS Supabase project root URL')
        if not secret.startswith('sb_secret_') or publishable and not publishable.startswith('sb_publishable_'):
            raise PublisherError('Use current Supabase secret/publishable keys in the named environment variables')
        self.url=url.rstrip('/')+'/rest/v1';self.secret=secret;self.publishable=publishable

    @classmethod
    def environment(cls, anonymous=False):
        # Reuse the existing dotenv behavior without inspecting or rewriting .env.
        names=['SUPABASE_URL','SUPABASE_SECRET_KEY']+(['SUPABASE_PUBLISHABLE_KEY']if anonymous else [])
        missing=[n for n in names if not os.environ.get(n)]
        if missing:raise PublisherError('Missing environment variables: '+', '.join(missing))
        return cls(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SECRET_KEY'],os.environ.get('SUPABASE_PUBLISHABLE_KEY'))


class Publisher:
    def __init__(self, config, session=None, sleep=time.sleep):
        self.config=config;self.session=session or requests.Session();self.sleep=sleep;self._ready=False

    def request(self,method,path,body=None,params=None,anonymous=False,denied=False):
        key=self.config.publishable if anonymous else self.config.secret
        if not key:raise PublisherError('Missing environment variables: SUPABASE_PUBLISHABLE_KEY')
        for attempt in range(2):
            try:
                r=self.session.request(method,self.config.url+'/'+path,headers={'apikey':key,'Content-Type':'application/json'},json=body,params=params,timeout=(10,30),allow_redirects=False)
                if denied:
                    if r.status_code in (401,403) and r.json().get('code')=='42501':return True
                    raise PublisherError('Anonymous write access was not safely denied')
                if r.status_code in (429,500,502,503,504) and attempt==0:
                    retry=r.headers.get('Retry-After','1')
                    try:delay=float(retry)
                    except ValueError:raise PublisherError('Supabase requested a deferred retry') from None
                    if not 0<=delay<=5:raise PublisherError('Supabase requested a deferred retry')
                    self.sleep(max(1,delay));continue
                if not 200<=r.status_code<300:
                    try:code=r.json().get('code')
                    except (ValueError,AttributeError):code=None
                    if code in ('PGRST202','PGRST205','42P01'):raise PublisherError('Apply '+MIGRATION+' in the Supabase SQL Editor first')
                    raise PublisherError('Supabase API request failed (HTTP '+str(r.status_code)+'); no response details logged')
                if len(r.content)>3_000_000:raise PublisherError('Oversized Supabase response')
                return r.json()
            except requests.RequestException:
                if attempt==1:raise PublisherError('Supabase connection failed; remote state may be committed, retry the same snapshot safely') from None
                self.sleep(1)
            except (ValueError,AttributeError) as error:
                if isinstance(error,PublisherError):raise
                raise PublisherError('Invalid Supabase API response') from None

    def ready(self):
        status=self.request('POST','rpc/live_schema_status',{})
        if not isinstance(status,dict) or status.get('version')!=1 or any(status.get(k) is not True for k in ('rls_enabled','anonymous_read_only','authenticated_read_only','writer_restricted','select_policies_only')):
            raise PublisherError('Supabase security/readiness checks did not pass; do not publish')
        self._ready=True
        return status

    def read(self,league_uuid,season,anonymous=False):
        rows=self.request('GET','live_snapshots',params={'league_id':'eq.'+league_uuid,'season':'eq.'+str(season),'select':'*','limit':'2'},anonymous=anonymous)
        if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):raise PublisherError('Expected exactly one accessible snapshot for this league/season')
        if rows[0].get('league_id')!=league_uuid or rows[0].get('season')!=season:raise PublisherError('Read-back league/season identity mismatch')
        return rows[0]

    def publish(self,snapshot,verified_at,sport,league_id,name,public,now=None):
        summary=validate(snapshot,league_id,verified_at,now)
        if sport not in ('nba','nfl') or not isinstance(public,bool) or not isinstance(name,str) or not 1<=len(name)<=160:
            raise PublisherError('Invalid sport, display name or explicit visibility')
        if not self._ready:self.ready()
        args={'p_sport':sport,'p_espn_league_id':league_id,'p_display_name':name,'p_is_public':public,
              'p_snapshot':snapshot,'p_verified_at':summary['verifiedAt']}
        result=self.request('POST','rpc/publish_live_snapshot',args)
        if not isinstance(result,dict) or result.get('action') not in ('inserted','updated','refreshed','unchanged','stale'):
            raise PublisherError('Invalid publication acknowledgement')
        if result['action']=='stale':raise PublisherError('Older or conflicting snapshot rejected; newer remote data retained')
        uuid=result.get('league_id')
        if not isinstance(uuid,str) or not re.fullmatch('[a-f0-9-]{36}',uuid) or result.get('revision')!=snapshot['revision']:
            raise PublisherError('Publication identity mismatch')
        row=self.read(uuid,summary['season'])
        try:
            if row.get('snapshot')!=snapshot or row.get('revision')!=snapshot['revision'] or instant(row['verified_at'])<instant(verified_at):
                raise PublisherError('Read-back content or freshness mismatch')
        except (ValueError,TypeError,KeyError):
            raise PublisherError('Read-back content or freshness mismatch') from None
        return {**summary,'action':result['action'],'leagueId':uuid,'roundTripVerified':True}

    def verify_anonymous(self,result,snapshot,sport,league_id,name,public):
        if not public:raise PublisherError('Anonymous round-trip test requires an explicitly public league')
        row=self.read(result['leagueId'],snapshot['season'],anonymous=True)
        if row.get('snapshot')!=snapshot:raise PublisherError('Anonymous read-back mismatch')
        leagues=self.request('GET','leagues',params={'id':'eq.'+result['leagueId'],'select':'id,sport,espn_league_id,is_public'},anonymous=True)
        if not isinstance(leagues,list) or len(leagues)!=1 or not isinstance(leagues[0],dict) or leagues[0].get('is_public') is not True:raise PublisherError('Public league metadata is not readable')
        # Invalid insert can never add a row even if grants are misconfigured.
        # UPDATE/DELETE target a nonexistent UUID, never the real league/snapshot.
        missing='00000000-0000-0000-0000-000000000000'
        for table,column in (('leagues','id'),('live_snapshots','league_id')):
            for method,body in (('POST',{'league_id':missing} if table=='live_snapshots' else {'sport':'invalid'}),
                                ('PATCH',{'schema_version':1} if table=='live_snapshots' else {'display_name':name}),('DELETE',None)):
                self.request(method,table,body,params=None if method=='POST' else {column:'eq.'+missing},anonymous=True,denied=True)
        self.request('POST','rpc/publish_live_snapshot',{'p_sport':sport,'p_espn_league_id':league_id,'p_display_name':name,
            'p_is_public':public,'p_snapshot':snapshot,'p_verified_at':result['verifiedAt']},anonymous=True,denied=True)
        return {'anonymousReadVerified':True,'anonymousMutationDenials':7}


def load_snapshot(path):
    try:
        snapshot=json.loads(path.read_text());state=json.loads(path.with_suffix(path.suffix+'.state.json').read_text())
        if state.get('error') or state.get('revision')!=snapshot['revision'] or state.get('leagueId')!=snapshot['leagueId'] or state.get('season')!=snapshot['season']:
            raise PublisherError('Adapter verification state is failed or incompatible')
        return snapshot,state['verifiedAt']
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as error:
        if isinstance(error,PublisherError):raise
        raise PublisherError('Read a valid adapter snapshot and its matching successful state file') from None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument('--snapshot',type=Path);modes.add_argument('--generate',action='store_true');modes.add_argument('--check-schema',action='store_true')
    p.add_argument('--dry-run',action='store_true');p.add_argument('--verify-anonymous',action='store_true')
    p.add_argument('--sport',choices=['nba','nfl'],default='nba');p.add_argument('--league-id',type=int,default=609694684)
    p.add_argument('--display-name',default='Basketball Brawl');p.add_argument('--visibility',choices=['public','private'])
    p.add_argument('--season',type=int);p.add_argument('--metadata',type=Path,default=ROOT/'data/seasonMetadata.json');p.add_argument('--output',type=Path)
    args=p.parse_args()
    try:
        publisher=None
        if not args.dry_run:
            publisher=Publisher(Config.environment(args.verify_anonymous));publisher.ready()
        if args.check_schema:
            if args.dry_run:raise PublisherError('Schema check requires Supabase configuration')
            print('Supabase schema and security checks passed');return 0
        if args.verify_anonymous and args.visibility!='public':raise PublisherError('Anonymous verification requires explicit --visibility public')
        if not args.dry_run and args.visibility is None:raise PublisherError('Choose explicit --visibility public or private')
        if args.generate:
            if args.sport!='nba' or args.season is None or args.output is None:raise PublisherError('NBA generation requires --season and external --output; NFL adapter is a future stage')
            generate(args.output,json.loads(args.metadata.read_text()),args.season,args.league_id)
            path=args.output
        else:path=args.snapshot
        snapshot,verified_at=load_snapshot(path);summary=validate(snapshot,args.league_id,verified_at)
        if args.dry_run:print(json.dumps({'dryRun':True,**summary},sort_keys=True));return 0
        result=publisher.publish(snapshot,verified_at,args.sport,args.league_id,args.display_name,args.visibility=='public')
        if args.verify_anonymous:result.update(publisher.verify_anonymous(result,snapshot,args.sport,args.league_id,args.display_name,args.visibility=='public'))
        print(json.dumps(result,sort_keys=True));return 0
    except (PublisherError,OSError,ValueError,TypeError,KeyError):
        import sys
        error=sys.exc_info()[1]
        print(str(error) if isinstance(error,PublisherError) else 'Invalid publication input or remote response',file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
