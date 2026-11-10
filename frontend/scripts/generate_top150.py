"""Export guarded NBA-wide rankings; never infer a full pool from roster-only CSVs.

Optional input nbaPlayerPool.json is a complete season-total snapshot. Its contract
is documented in frontend/SPRINT.md. This exporter does not perform API requests.
"""
import json
import math
from pathlib import Path
from build_homepage import write_json, logo_config, team_info


def validate_pool(pool, weights):
    if pool.get('complete') is not True or not pool.get('source') or pool.get('scope') != 'NBA regular season':
        raise ValueError('Unverified or incomplete NBA player pool')
    if pool.get('scoringWeights') != weights:
        raise ValueError('Player pool scoring rules do not match the selected fantasy season')
    players = pool['players']
    ids = [p['playerId'] for p in players]
    if len(ids) != len(set(ids)) or len(ids) < 150:
        raise ValueError('Duplicate players or incomplete NBA player population')
    for p in players:
        if not isinstance(p['playerId'], int) or p['playerId'] <= 0 or not p.get('name'):
            raise ValueError('Invalid player identity')
        for key in ('gp', 'fpts'):
            if not isinstance(p[key], (int, float)) or not math.isfinite(p[key]):
                raise ValueError('Missing/nonfinite season statistics')
        if p['gp'] < 0 or p['gp'] != int(p['gp']) or (p['gp'] == 0 and p['fpts'] != 0):
            raise ValueError('Invalid games played')
    maximum = pool.get('maxTeamGames')
    if maximum is not None and (not isinstance(maximum, int) or maximum < max(p['gp'] for p in players)):
        raise ValueError('Invalid maximum team games')
    return players


def build(source: Path, output: Path):
    archive=build_archive(source,output)
    if archive is not None:return archive
    metadata = json.loads((source / 'seasonMetadata.json').read_text())
    path = source / 'nbaPlayerPool.json'
    pools = json.loads(path.read_text()).get('seasons', {}) if path.exists() else {}
    current_path = source / 'currentLeague.json'
    current = json.loads(current_path.read_text()) if current_path.exists() else {}
    config = logo_config()
    owners = {}
    names = {}
    for team in current.get('teams', []):
        identity = team_info({'Team ID': team['teamId'], 'Team Name': team['teamName']}, config)
        for player in team['roster']:
            pid = player['playerId']
            if pid in owners:
                raise ValueError('Conflicting roster ownership')
            owners[pid] = identity
            names[pid] = player['name']
    seasons = {}
    for season in metadata['seasons']:
        year = str(season['season'])
        result = {'completePool': False, 'limitation': 'NBA-wide season totals are unavailable: the saved daily dataset covers fantasy-rostered players only.'}
        pool = pools.get(year)
        if pool:
            try:
                players = validate_pool(pool, season['scoringWeights'])
                ownership = current.get('season') == int(year)
                exported = [{**p, 'fantasyTeam': owners.get(p['playerId']) if ownership else None} for p in players]
                if ownership:
                    ids = {p['playerId'] for p in players}
                    exported.extend({'playerId': pid, 'name': names[pid], 'gp': None, 'fpts': None, 'fantasyTeam': team}
                                    for pid, team in owners.items() if pid not in ids)
                maximum = pool.get('maxTeamGames')
                result = {'completePool': True, 'players': exported, 'maxTeamGames': maximum if maximum is not None else max(p['gp'] for p in players),
                          'gamesBasis': 'Based on maximum NBA team games played.' if maximum is not None else 'Fallback: maximum player GP in the complete pool; team schedule counts unavailable.',
                          'ownershipAvailable': ownership,
                          'ownershipNote': 'Ownership: saved active-season roster snapshot.' if ownership else 'Historical roster reconstruction unavailable; ownership comparisons disabled.',
                          'source': pool['source']}
            except (ValueError, KeyError, TypeError) as error:
                result['limitation'] = f'NBA-wide rankings unavailable: {error}.'
        seasons[year] = result
    payload = {'schemaVersion': 1, 'years': sorted(map(int, seasons), reverse=True), 'seasons': seasons}
    write_json(output / 'top-150.json', payload)
    return payload


def newer_roster_games(source, year, through_date):
    """Coverage diagnostics only: never turn roster-only rows into NBA rankings."""
    import csv
    path = source / 'playerDailyData.csv'
    if not path.exists():
        return {}
    dates = {}
    with path.open() as handle:
        for row in csv.DictReader(handle):
            if int(row['Year']) == int(year) and row['Date'] > through_date and float(row['MIN'] or 0) > 0:
                dates.setdefault(int(row['Player ID']), set()).add(row['Date'])
    return {pid: {'count': len(days), 'throughDate': max(days)} for pid, days in dates.items()}


def build_archive(source,output):
    import csv,shutil,hashlib
    root=Path(__file__).resolve().parents[2]/'data'
    data=source if (source/'playerSeasonStats.csv').exists() else root
    if not (data/'playerSeasonStats.csv').exists():return None
    meta=json.loads((data/'playerGameLogs.report.json').read_text());static=data/'player-static';manifest=json.loads((static/'index.json').read_text())
    if manifest['archiveSHA256']!=meta['csvSHA256']:raise ValueError('Ranking/archive versions differ')
    current=json.loads((source/'currentLeague.json').read_text())if(source/'currentLeague.json').exists()else {}
    owners={};names={};slots={};config=logo_config()
    for t in current.get('teams',[]):
        identity=team_info({'Team ID':t['teamId'],'Team Name':t['teamName']},config)
        for p in t['roster']:
            if p['playerId']in owners:raise ValueError('Conflicting roster ownership')
            owners[p['playerId']]=identity;names[p['playerId']]=p['name'];slots[p['playerId']]=p.get('slot')
    seasons={}
    from top150_ownership import load_historical_ownership
    contexts={}
    if current.get('season'):
        contexts[str(current['season'])]={'owners':owners,'names':names,'slots':slots,'verifiedAt':current.get('updatedAt'),'kind':'current','scoringPeriod':None}
    with (data/'playerSeasonStats.csv').open()as handle:summary_rows=list(csv.DictReader(handle))
    for y in {r['Year'] for r in summary_rows}:
        if y not in contexts:
            historical=load_historical_ownership(source,y,config)
            if historical:contexts[y]={**historical,'kind':'seasonEnd'}
    for r in summary_rows:
        y=r['Year'];pid=int(r['Player ID']);context=contexts.get(y)
        season_owners=context['owners'] if context else {}
        seasons.setdefault(y,{'players':[]})['players'].append({'playerId':pid,'name':r['Player Name'],'gp':int(r['Games Played']),'fpts':float(r['Total FPTS']),'nbaTeamId':int(r['Latest Observed NBA Team ID']),'positions':[x for x in json.loads(r['Eligible Slot IDs'])if x in range(5)],'fantasyTeam':season_owners.get(pid),'teamId':season_owners[pid]['teamId']if pid in season_owners else 0 if context else None,'playerSlot':context['slots'].get(pid,'FA')if context else None,'ownershipStatus':'owned'if pid in season_owners else 'freeAgent'if context else 'unknown'})
    for y,season in seasons.items():
        players=season['players'];coverage=meta['seasonReports'][y]
        if len({p['playerId']for p in players})!=len(players) or len(players)!=coverage['players'] or sum(p['gp']for p in players)!=coverage['rows']:raise ValueError('Ranking summary coverage mismatch')
        if any(p['gp']<=0 or not math.isfinite(p['fpts'])for p in players):raise ValueError('Invalid season summary')
        context=contexts.get(y)
        if context:
            ids={p['playerId']for p in players}
            players += [{'playerId':pid,'name':context['names'][pid],'gp':0,'fpts':None,'positions':[],'nbaTeamId':None,'fantasyTeam':team,'teamId':team['teamId'],'playerSlot':context['slots'][pid],'ownershipStatus':'owned'}for pid,team in context['owners'].items()if pid not in ids]
        newer=newer_roster_games(source,y,coverage['throughDate'])
        for player in players:
            if player['playerId'] in newer:player['newerRosterGames']=newer[player['playerId']]
        season['newerRosterThroughDate']=max((v['throughDate']for v in newer.values()),default=None)
        season.update(completePool=True,maxTeamGames=max(coverage['teamGames'].values()),ownershipAvailable=bool(context),ownershipUpdatedAt=context['verifiedAt']if context else None,ownershipKind=context['kind']if context else 'unknown',ownershipScoringPeriod=context['scoringPeriod']if context else None,throughDate=coverage['throughDate'])
    output.mkdir(parents=True,exist_ok=True);shutil.copytree(static,output/'player-static',dirs_exist_ok=True)
    for y,value in seasons.items():
        value['dataVersion']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        write_json(output/'top150'/(y+'.json'),{'schemaVersion':1,**value})
    payload={'schemaVersion':1,'years':sorted(map(int,seasons),reverse=True),'currentSeason':max(map(int,seasons)),'updatedAt':manifest['updatedAt'],'seasons':{y:{k:v for k,v in value.items()if k!='players'}for y,value in seasons.items()}}
    write_json(output/'top-150.json',payload);return payload
