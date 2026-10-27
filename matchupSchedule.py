"""Allowlisted NBA schedule snapshot; never infer fantasy-week boundaries."""
from datetime import datetime, timezone


def schedule_snapshot(raw, now):
    teams = raw.get('settings', {}).get('proTeams', [])
    names = {int(t['id']): t['abbrev'] for t in teams}
    games, seen = [], set()
    missing = False
    for team in teams:
        if int(team['id']) == 0:
            continue
        missing = missing or 'proGamesByScoringPeriod' not in team
        for period, entries in team.get('proGamesByScoringPeriod', {}).items():
            for game in entries:
                key = (int(team['id']), int(game['id']))
                if key in seen:
                    continue
                seen.add(key)
                start = datetime.fromtimestamp(game['date']/1000, timezone.utc)
                opponent = game['awayProTeamId'] if game['homeProTeamId'] == team['id'] else game['homeProTeamId']
                games.append({'id': int(game['id']), 'proTeamId': int(team['id']), 'opponent': names.get(opponent),
                              'period': int(period), 'start': start.isoformat(),
                              'state': 'completed' if game.get('statsOfficial') else 'scheduled' if start > now else 'started-unconfirmed'})
    # Publication of all teams is evidence of NBA coverage, never fantasy-week coverage.
    return {'complete': len(names) >= 30 and not missing, 'source': 'ESPN proTeamSchedules_wl', 'games': games}


def enrich_roster_snapshot(league, snapshot, raw, now):
    nba = league.espn_request.get_pro_schedule()
    pro_ids = {t['abbrev']: int(t['id']) for t in nba.get('settings', {}).get('proTeams', [])}
    players = {int(p.playerId): p for t in league.teams for p in t.roster}
    for team in snapshot['teams']:
        for rostered in team['roster']:
            player = players[rostered['playerId']]
            rostered.update(proTeamId=pro_ids.get(player.proTeam), slot=player.lineupSlot,
                            injuryStatus=player.injuryStatus)
    settings = raw['settings']
    roster = settings['rosterSettings']
    snapshot['lineupConstraints'] = {'daily': roster.get('lineupLocktimeType') == 'INDIVIDUAL_GAME',
        'lineupLock': roster.get('lineupLocktimeType'), 'rosterLock': roster.get('rosterLocktimeType'),
        'slotStatLimits': roster.get('lineupSlotStatLimits', {}),
        'matchupAcquisitionLimit': settings.get('acquisitionSettings', {}).get('matchupAcquisitionLimit')}
    snapshot['nbaSchedule'] = schedule_snapshot(nba, now)
    return snapshot
