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
