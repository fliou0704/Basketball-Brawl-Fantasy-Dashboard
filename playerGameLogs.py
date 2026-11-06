"""Independent NBA appearances archive. Explicit CLI only; no live updater imports.

Checkpoints contain ESPN basketball responses, never cookies or request headers.
No existing dataset is a write target. Published CSV is replaced only after coverage
and scoring validation; failed requests retain both checkpoints and last-good CSV.
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import time

from dataUpdateSafety import require_espn_credentials
from liveScoringAdapter import atomic, locked
from nbaSchedule import normalize, instant, NY

STATS = {'MIN':'40','PTS':'0','REB':'6','AST':'3','STL':'2','BLK':'1','FGM':'13','FGA':'14','FTM':'15','FTA':'16','3PM':'17','3PA':'18','TO':'11','GP':'42'}
COLUMNS = ['Year','Game ID','Player ID','Player Name','Date','Scoring Period','NBA Team ID','Opponent ID','Eligible Slot IDs','FPTS',*STATS,'Source']
BASE='https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/'
PUBLIC='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'

class CollectionError(ValueError): pass

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);atomic(path,value)

def number(v):
    if isinstance(v,bool):raise CollectionError('Boolean statistic is not numeric data')
    v=float(v)
    if not math.isfinite(v):raise CollectionError('Nonfinite statistic')
    return v

def parse_stats(labels, values):
    result={}
    for label,value in zip(labels,values):
        if label in ('FG','FT','3PT'):
            made,attempted=value.split('-');prefix={'FG':'FG','FT':'FT','3PT':'3P'}[label]
            result[prefix+'M']=number(made);result[prefix+'A']=number(attempted)
        elif label=='MIN' and ':' in value:
            minute,second=value.split(':');result['MIN']=number(minute)+number(second)/60
        elif label in STATS:result[label]=number(value)
        elif label=='MIN':result['MIN']=number(value)
    if not set(STATS)-{'GP'}<=result.keys():raise CollectionError('Incomplete box-score statistics')
    result['GP']=1.0
    return result

def appearances(raw,fixture,year):
    header=raw['header'];competition=header['competitions'][0]
    if str(competition.get('type',{}).get('id'))=='39':return []
    if str(header['id'])!=str(fixture['id']):raise CollectionError('Wrong NBA game')
    if competition.get('date') and instant(competition['date']).astimezone(NY).date().isoformat()!=fixture['date']:raise CollectionError('NBA game date differs from fixture; refresh source before retry')
    if header.get('season',{}).get('type')!=2:return []
    if not competition.get('status',{}).get('type',{}).get('completed'):raise CollectionError('NBA game not final')
    if any(str(x.get('id'))=='39' for x in competition.get('groups',[])):return []
    # Championship exclusion: explicit title as an additional guard, never all Cup games.
    if any('championship' in str(n.get('headline','')).lower() and 'cup' in str(n.get('headline','')).lower() for n in competition.get('notes',[])):return []
    teams=raw['boxscore']['players'];ids={int(t['team']['id'])for t in teams}
    if ids!={fixture['home'],fixture['away']}:raise CollectionError('NBA team coverage mismatch')
    rows=[]
    for team in teams:
        tid=int(team['team']['id']);opponent=next(x for x in ids if x!=tid)
        groups=team['statistics']
        if len(groups)!=1:raise CollectionError('Unexpected box-score groups')
        for athlete in groups[0]['athletes']:
            if athlete.get('didNotPlay') is True:continue
            if (athlete.get('reason') or athlete.get('active') is False) and athlete.get('stats',[None])[0]=='--':continue
            if athlete.get('didNotPlay') is not False:raise CollectionError('Unknown participation')
            uncertain=athlete['stats'][0]=='--'
            values=list(athlete['stats'])
            if uncertain:values[0]='0'
            stats=parse_stats(groups[0]['labels'],values)
            rows.append({'Year':year,'Game ID':int(fixture['id']),'Player ID':int(athlete['athlete']['id']),
                'Player Name':athlete['athlete']['displayName'],'Date':fixture['date'],'Scoring Period':fixture['period'],
                'NBA Team ID':tid,'Opponent ID':opponent,'_needsGP':uncertain,**stats})
    if not rows or {r['NBA Team ID']for r in rows}!=ids or len({r['Player ID']for r in rows})!=len(rows):raise CollectionError('Empty or duplicate NBA appearances')
    return rows

def fantasy_games(raw, year):
    games={};eligibility={}
    for item in raw.get('players',[]):
        p=item.get('player',item);pid=int(p['id']);eligibility[pid]=sorted(set(map(int,p.get('eligibleSlots',[]))))
        for g in p.get('stats',[]):
            if g.get('seasonId')!=year or g.get('statSourceId')!=0 or g.get('statSplitTypeId')!=5:continue
            if not g.get('externalId'):continue
            key=(int(g['externalId']),pid)
            record={'period':int(g['scoringPeriodId']),'points':number(g['appliedTotal']), 'stats':g.get('stats',{})}
            if key in games and games[key]!=record:raise CollectionError('Conflicting fantasy game identity')
            games[key]=record
    return games,eligibility

def assemble(rows,games,eligibility,weights,discrepancies=None):
    result=[];fallback=[];seen=set()
    for row in rows:
        row=dict(row);key=(row['Game ID'],row['Player ID'])
        if key in seen:raise CollectionError('Duplicate performance')
        seen.add(key)
        points=sum(row.get(name,0)*weights.get(sid,0)for name,sid in STATS.items())
        game=games.get(key);use_fantasy_stats=False
        if row.pop('_needsGP',False):
            gp=game.get('stats',{}).get('42') if game else None
            if gp==0:continue
            if gp!=1:raise CollectionError('Ambiguous NBA participation requires fantasy GP confirmation')
        if game:
            if row['Scoring Period'] is None:row['Scoring Period']=game['period']
            if game['period']!=row['Scoring Period']:raise CollectionError('Fantasy scoring-period mismatch')
            if 'stats' in game and set(STATS.values())<=game['stats'].keys() and number(game['stats']['42'])>0:
                if number(game['stats']['42'])!=1:raise CollectionError('Game-level fantasy GP is not one')
                use_fantasy_stats=True
                fresh={name:number(game['stats'][sid])for name,sid in STATS.items()}
                recomputed=sum(fresh[name]*weights.get(sid,0)for name,sid in STATS.items())
                if abs(recomputed-game['points'])>.001:raise CollectionError('Fantasy raw statistics do not reproduce official points')
                differences={k:{'boxScore':row[k],'fantasy':fresh[k]}for k in STATS if row[k]!=fresh[k]}
                if differences and discrepancies is not None:discrepancies.append({'gameId':key[0],'playerId':key[1],'stats':differences})
                row.update(fresh);points=game['points']
            elif abs(game['points']-points)>.001:raise CollectionError('Box-score versus fantasy scoring mismatch')
        if not use_fantasy_stats:fallback.append(list(key))
        row.update(FPTS=points,Source='ESPN fantasy game + NBA participation' if use_fantasy_stats else 'ESPN NBA box score + league scoring',**{'Eligible Slot IDs':json.dumps(eligibility.get(row['Player ID'],[]),separators=(',',':'))})
        result.append(row)
    return sorted(result,key=lambda r:(r['Year'],r['Date'],r['Game ID'],r['Player ID'])),sorted(fallback)

def reconcile(rows,canonical,weights=None):
    index={}
    for r in rows:index.setdefault((r['Year'],r['Player ID'],r['Scoring Period']),[]).append(r)
    years={r['Year']for r in rows}
    result={'checked':0,'matched':0,'missing':0,'ambiguous':0,'differences':[],'statDifferences':[]}
    for old in canonical:
        key=tuple(int(float(old[k]))for k in ('Year','Player ID','Scoring Period'))
        if key[0]not in years:continue
        result['checked']+=1;found=index.get(key,[])
        if not found:result['missing']+=1;continue
        if len(found)!=1:result['ambiguous']+=1;continue
        result['matched']+=1;r=found[0]
        if weights is not None:
            diffs={name:{'canonical':float(old[name]),'expectedContribution':r[name]*(1 if name in ('MIN','3PA') else weights.get(sid,1))}for name,sid in STATS.items()if name in old and old[name] not in ('','nan') and name!='GP' and abs(float(old[name])-r[name]*(1 if name in ('MIN','3PA') else weights.get(sid,1)))>.001}
            if diffs:result['statDifferences'].append({'playerId':r['Player ID'],'gameId':r['Game ID'],'stats':diffs})
        if old['Date']!=r['Date']or abs(float(old['FPTS'])-r['FPTS'])>.001 or abs(float(old['MIN'])-r['MIN'])>.001:
            result['differences'].append({'playerId':r['Player ID'],'gameId':r['Game ID'],'canonicalFPTS':float(old['FPTS']),'newFPTS':r['FPTS'],'dateMatches':old['Date']==r['Date'],'minutesMatch':abs(float(old['MIN'])-r['MIN'])<=.001})
    return result

def cache_value(url,params,value):
    # Retain only the basketball fields consumed here, not league member/owner
    # profiles or unrelated response envelopes. Never persist request context.
    view=(params or {}).get('view')
    if url.startswith(BASE) and view=='mSettings':
        return {'settings':{'scoringSettings':{'scoringItems':value['settings']['scoringSettings']['scoringItems']}}}
    if url.startswith(BASE) and view in ('kona_playercard','kona_player_info'):
        return {'players':value['players']}
    return value

class Client:
    def __init__(self, cache, budget=200):
        import requests
        self.session=requests.Session();swid,s2=require_espn_credentials()
        self.cookies={'SWID':swid,'espn_s2':s2};self.cache=Path(cache);self.budget=budget
        self.metrics={'requests':0,'bytes':0,'seconds':0.0}
    def get(self,url,params=None,filters=None,refresh=False):
        key=hashlib.sha256(json.dumps([url,params,filters],sort_keys=True).encode()).hexdigest()
        path=self.cache/(key+'.json')
        if path.exists() and not refresh:
            old=json.loads(path.read_text());value=cache_value(url,params,old)
            if value!=old:write_json(path,value)
            return value
        for attempt in range(2):
            if self.metrics['requests']>=self.budget:raise CollectionError('Request budget reached; rerun to resume checkpoints')
            self.metrics['requests']+=1;t=time.monotonic()
            try:
                r=self.session.get(url,params=params,headers={'x-fantasy-filter':json.dumps(filters)}if filters else {},cookies=self.cookies if url.startswith(BASE) else {},timeout=(10,40),allow_redirects=False)
                self.metrics['seconds']+=time.monotonic()-t;self.metrics['bytes']+=len(r.content)
                if r.status_code in (429,500,502,503,504) and attempt==0:time.sleep(2);continue
                if r.status_code!=200:raise CollectionError('ESPN request rejected; checkpoint retained')
                if len(r.content)>20_000_000:raise CollectionError('Response exceeds size bound; reduce batch size')
                value=cache_value(url,params,r.json());write_json(path,value);time.sleep(.1);return value
            except CollectionError:raise
            except Exception:
                if attempt:raise CollectionError('ESPN transport/JSON failure; checkpoint retained')from None
                time.sleep(1)

    def league(self,year,view,filters=None,period=None,refresh=False):
        params={'view':view}
        if period is not None:params['scoringPeriodId']=period
        return self.get(BASE+str(year)+'/segments/0/leagues/609694684',params,filters,refresh)

def collect(year,client,output,refresh=False,canonical="data/playerDailyData.csv"):
    protected={'playerDailyData.csv','basketballBrawlLeagueData.csv','playerMatchupData.csv','activityData.csv','playerMetadata.csv','scoringPeriodMatchupMap.csv'}
    if Path(output).suffix!='.csv' or Path(output).name in protected:raise CollectionError('Output must be a separate game-log CSV')
    start=time.monotonic();now=datetime.now(timezone.utc)
    settings=client.league(year,'mSettings',refresh=refresh)['settings']
    weights={str(s['statId']):number(s['points'])for s in settings['scoringSettings']['scoringItems']}
    if set(weights)-set(STATS.values()):raise CollectionError('Scoring rules use unsupported raw statistics')
    raw=client.get(BASE+str(year),{'view':'proTeamSchedules_wl'},refresh=refresh)
    schedule=normalize(raw,year,parser_only=True)
    fixtures=schedule['fixtures'];nba_teams={t['id']for t in schedule['teams']}
    completed=[g for g in fixtures if g['regularSeason'] and g['statsOfficial'] and instant(g['start'])<now]
    if not completed:raise CollectionError('No verified completed fixtures')
    # Independent discovery: day-bounded public NBA events, not the fantasy pool.
    from datetime import date
    cursor=date(year-1,10,1);end=min(now.date(),date(year,6,30));public_ids=set();public_games={}
    while cursor<=end:
        last=cursor
        board=client.get(PUBLIC+'scoreboard',{'dates':cursor.strftime('%Y%m%d'),'limit':1000},refresh=refresh and last>=now.date()-timedelta(days=3))
        events=board.get('events')
        if not isinstance(events,list)or len(events)>=1000:raise CollectionError('Incomplete NBA event discovery')
        for event in events:
            comp=event['competitions'][0]
            if event['season']['type']==2 and str(comp.get('type',{}).get('id'))!='39' and event['status']['type']['completed'] and {int(t['team']['id'])for t in comp['competitors']}<=nba_teams:
                public_ids.add(int(event['id']));public_games[int(event['id'])]=event
        cursor=last+timedelta(days=1)
    fixture_ids={g['id']for g in completed}
    if fixture_ids-public_ids:raise CollectionError('Fantasy fixtures absent from independent NBA events')
    missing_fixture_ids=sorted(public_ids-fixture_ids)
    for gid in missing_fixture_ids:
        event=public_games[gid];sides={t['homeAway']:int(t['team']['id'])for t in event['competitions'][0]['competitors']}
        completed.append({'id':gid,'date':instant(event['date']).astimezone(NY).date().isoformat(),'period':None,**sides})
    allrows=[];included=[]
    for fixture in completed:
        recent=fixture['date']>=(now-timedelta(days=3)).date().isoformat()
        box=client.get(PUBLIC+'summary',{'event':fixture['id']},refresh=refresh and recent)
        rows=appearances(box,fixture,year)
        if rows:included.append(fixture['id']);allrows+=rows
    ids=sorted({r['Player ID']for r in allrows});games={};eligibility={}
    # Initial resumable bulk cards; incremental exact-period reads replace only
    # observed keys. Cache avoids re-downloading careers on subsequent runs.
    checkpoint=client.cache/('season-'+str(year)+'-index.json')
    if checkpoint.exists():
        saved=json.loads(checkpoint.read_text())
        eligibility={int(k):v for k,v in saved['eligibility'].items()}
        games={(int(gid),int(pid)):value for gid,pid,value in saved['games']}
    attempted=set(saved.get('attemptedIds',[])) if checkpoint.exists() else set()
    unknown=[pid for pid in ids if pid not in attempted]
    for pos in range(0,len(unknown),80):
        chunk=unknown[pos:pos+80]
        raw=client.league(year,'kona_playercard',{'players':{'filterIds':{'value':chunk},'filterStatsForTopScoringPeriodIds':{'value':220,'additionalValue':['00'+str(year)]}}})
        g,e=fantasy_games(raw,year);games.update(g);eligibility.update(e)
    write_json(checkpoint,{'attemptedIds':sorted(attempted|set(ids)),'eligibility':eligibility,'games':[[gid,pid,value]for (gid,pid),value in sorted(games.items())]})
    if refresh:
        periods=sorted({r['Scoring Period']for r in allrows if r['Date']>=(now-timedelta(days=3)).date().isoformat()})
        for period in periods:
            offset=0
            while True:
                raw=client.league(year,'kona_player_info',{'players':{'limit':200,'offset':offset,'sortPercOwned':{'sortPriority':1,'sortAsc':False},'filterStatsForScoringPeriodIds':{'value':[period]}}},period,True)
                if not isinstance(raw.get('players'),list):raise CollectionError('Missing fantasy page')
                g,e=fantasy_games(raw,year);games.update(g);eligibility.update(e)
                if len(raw['players'])<200:break
                offset+=200
                if offset>4000:raise CollectionError('Unbounded player pagination')
    write_json(checkpoint,{'attemptedIds':sorted(attempted|set(ids)),'eligibility':eligibility,'games':[[gid,pid,value]for (gid,pid),value in sorted(games.items())]})
    if not included or set(included)!=public_ids:raise CollectionError('Final NBA participant coverage incomplete')
    discrepancies=[]
    rows,fallback=assemble(allrows,games,eligibility,weights,discrepancies)
    if {r['Game ID']for r in rows}!=public_ids:raise CollectionError('Validated participation missing an NBA game')
    expected_pairs={(g['id'],tid)for g in completed for tid in (g['home'],g['away'])}
    actual_pairs={(r['Game ID'],r['NBA Team ID'])for r in rows}
    if expected_pairs!=actual_pairs:raise CollectionError('NBA team-game participant coverage incomplete')
    team_games={str(tid):sum(t==tid for _,t in actual_pairs)for tid in sorted(nba_teams)}
    if year in (2023,2024,2025,2026) and now.date()>date(year,6,30) and any(n!=82 for n in team_games.values()):raise CollectionError('Completed season does not cover 82 games per NBA franchise')
    row_keys={(r['Game ID'],r['Player ID'])for r in rows}
    fantasy_only=[key for key,g in games.items()if key[0]in public_ids and number(g['stats'].get('42',0))>0 and key not in row_keys]
    if fantasy_only:raise CollectionError('Positive fantasy GP is absent from NBA participant coverage')
    ids=sorted({r['Player ID']for r in rows})
    destination=Path(output);prior=[]
    if destination.exists():prior=list(csv.DictReader(destination.open()))
    old_by_key={(int(r['Year']),int(r['Game ID']),int(r['Player ID'])):r for r in prior}
    corrections=[]
    for r in rows:
        old=old_by_key.get((year,r['Game ID'],r['Player ID']))
        if old:
            stat_changes={k:{'old':float(old[k]),'new':r[k]}for k in ['FPTS',*STATS]if abs(float(old[k])-r[k])>.001}
            if stat_changes or old['Date']!=r['Date'] or old['Scoring Period']!=str(r['Scoring Period'] or ''):corrections.append({'season':year,'gameId':r['Game ID'],'playerId':r['Player ID'],'stats':stat_changes,'oldDate':old['Date'],'newDate':r['Date'],'oldPeriod':old['Scoring Period'],'newPeriod':r['Scoring Period']})
    retained=[r for r in prior if int(r['Year'])!=year]
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=COLUMNS,lineterminator='\n');writer.writeheader();writer.writerows(sorted(retained+rows,key=lambda r:(int(r['Year']),r['Date'],int(r['Game ID']),int(r['Player ID']))))
    content=out.getvalue();destination.parent.mkdir(parents=True,exist_ok=True)
    import os,tempfile
    if not destination.exists() or destination.read_bytes()!=content.encode('utf-8'):
        fd,tmp=tempfile.mkstemp(dir=destination.parent,prefix='.game-logs-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='')as f:f.write(content);f.flush();os.fsync(f.fileno())
            os.replace(tmp,destination)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    canonical=Path(canonical)
    report={'schemaVersion':1,'leagueId':609694684,'scoringWeights':weights,'season':year,'players':len(ids),'throughDate':max(r['Date']for r in rows),'games':len(included),'rows':len(rows),'coverage':'all participating athletes in verified final regular-season fixtures','fixtureCount':len(completed),'fallbackFixtureIds':missing_fixture_ids,'unresolvedScoringPeriods':[[r['Game ID'],r['Player ID']]for r in rows if r['Scoring Period'] is None],'independentPublicGameCount':len(public_ids),'unmatchedFantasyGP':fantasy_only,'nbaTeamCount':len({r['NBA Team ID']for r in rows}),'teamGames':team_games,'sourceStatDiscrepancies':discrepancies,'fallbackGamePlayers':fallback,'unresolvedEligibilityPlayers':[pid for pid in ids if not eligibility.get(pid)],'metrics':client.metrics,'elapsedSeconds':round(time.monotonic()-start,3),'corrections':corrections,'csvSHA256':hashlib.sha256(content.encode()).hexdigest(),'reconciliation':reconcile(rows,list(csv.DictReader(canonical.open())),weights)if canonical.exists()else None}
    report_path=destination.with_suffix('.report.json')
    previous_report=json.loads(report_path.read_text()) if report_path.exists() else {}
    season_reports=previous_report.get('seasonReports',{})
    season_reports[str(year)]={k:v for k,v in report.items()if k not in ('metrics','elapsedSeconds','csvSHA256','corrections')}
    report['seasonReports']=season_reports
    report['archive']={str(y):{'rows':sum(int(r['Year'])==y for r in retained+rows),'players':len({int(r['Player ID'])for r in retained+rows if int(r['Year'])==y}),'games':len({int(r['Game ID'])for r in retained+rows if int(r['Year'])==y})}for y in sorted({int(r['Year'])for r in retained+rows})}
    # Runtime measurements go to stdout, not Git churn for unchanged datasets.
    comparable=lambda value:{k:v for k,v in value.items()if k not in ('metrics','elapsedSeconds','corrections')}
    if comparable(previous_report)!=comparable(report):write_json(report_path,report)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seasons',type=int,nargs='+',required=True);p.add_argument('--output',default='data/playerGameLogs.csv');p.add_argument('--cache',default='.player-game-log-cache');p.add_argument('--canonical',default='data/playerDailyData.csv');p.add_argument('--max-requests',type=int,default=200);p.add_argument('--refresh',action='store_true');a=p.parse_args()
    try:
        with locked(Path(a.output)):
            client=Client(a.cache,a.max_requests)
            for year in a.seasons:
                result=collect(year,client,a.output,a.refresh,a.canonical)
                print(json.dumps({k:result[k]for k in ('season','players','games','rows','metrics','elapsedSeconds')}))
    except (CollectionError,KeyError,ValueError,TypeError)as error:
        print(json.dumps({'error':'Collection failed safely; inspect validated source/checkpoints and retry','type':type(error).__name__,'reason':str(error) if isinstance(error,CollectionError) else 'Invalid source data'}));raise SystemExit(1)from None
if __name__=='__main__':main()
