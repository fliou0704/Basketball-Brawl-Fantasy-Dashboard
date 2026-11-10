"""Validated, public-only final-period rosters; never infer ownership from scoring."""
import csv
import json
from build_homepage import team_info


def validate_snapshot(snapshot, year, expected_teams, final_period):
    if (snapshot.get('season') != int(year) or snapshot.get('scoringPeriod') != final_period
            or snapshot.get('finalScoringPeriod') != final_period):
        raise ValueError('Historical ownership is not the selected final fantasy scoring period')
    teams = snapshot.get('teams', [])
    ids = [t['teamId'] for t in teams]
    if len(ids) != len(set(ids)) or set(ids) != set(expected_teams):
        raise ValueError('Historical ownership is missing fantasy teams')
    players = set()
    for team in teams:
        if team.get('rosterPresent') is not True or not team.get('entries'):
            raise ValueError('Historical roster coverage cannot be certified')
        for entry in team['entries']:
            pid = entry.get('playerId')
            if type(pid) is not int or pid <= 0 or pid in players or not entry.get('name'):
                raise ValueError('Historical roster has duplicate or invalid player identity')
            players.add(pid)
    return snapshot


def load_historical_ownership(source, year, config):
    path = source / 'seasonEndRosters.json'
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    if payload.get('schemaVersion') != 1 or payload.get('leagueId') != 609694684:
        raise ValueError('Historical ownership schema or league mismatch')
    snapshot = payload.get('seasons', {}).get(str(year))
    if snapshot is None:
        return None
    metadata = json.loads((source / 'seasonMetadata.json').read_text())
    info = next(s for s in metadata['seasons'] if s['season'] == int(year))
    # Preserve each season's canonical team names, not current franchise aliases.
    with (source / 'basketballBrawlLeagueData.csv').open() as handle:
        rows = [r for r in csv.DictReader(handle) if int(r['Year']) == int(year)]
    names = {int(r['Team ID']): r['Team Name'] for r in sorted(rows, key=lambda r: int(r['Week']))}
    validate_snapshot(snapshot, year, names, info['finalPeriod'])
    owners, player_names, slots = {}, {}, {}
    for team in snapshot['teams']:
        identity = team_info({'Team ID': team['teamId'], 'Team Name': names[team['teamId']]}, config)
        for entry in team['entries']:
            pid = entry['playerId']
            owners[pid] = identity
            player_names[pid] = entry['name']
            slots[pid] = entry.get('slotId')
    return {'owners': owners, 'names': player_names, 'slots': slots,
            'verifiedAt': payload['verifiedAt'], 'scoringPeriod': snapshot['scoringPeriod']}
