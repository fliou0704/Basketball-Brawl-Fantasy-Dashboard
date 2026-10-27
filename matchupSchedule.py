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


def enrich_roster_snapshot(league, snapshot, raw, now, schedule=None, previous=None):
    nba = league.espn_request.get_pro_schedule() if schedule is None else {'settings':{'proTeams':schedule.get('teams', [])}}
    pro_ids = {t['abbrev']: int(t['id']) for t in nba.get('settings', {}).get('proTeams', [])}
    players = {int(p.playerId): p for t in league.teams for p in t.roster}
    # The wrapper discards numeric NBA affiliations. The already-requested
    # mRoster response supplies current proTeamId without per-player calls.
    affiliations = {int(e['playerPoolEntry']['player']['id']):e['playerPoolEntry']['player'].get('proTeamId')
                    for t in raw.get('teams', []) for e in t.get('roster', {}).get('entries', [])}
    snapshot['nbaAffiliations'] = dict(getattr(league, '_brawl_affiliations', {}))
    snapshot['nbaAffiliations'].update({str(k):v for k,v in affiliations.items()})
    previous = previous or {}
    old_rosters = {(t['teamId'],p['playerId']):p for t in previous.get('teams', []) for p in t.get('roster', [])}
    old_affiliations = previous.get('nbaAffiliations', {})
    old_since = previous.get('nbaAffiliationSince', {})
    snapshot['nbaAffiliationSince'] = {pid:old_since.get(pid,previous.get('rosterVerifiedAt',previous.get('updatedAt',now.isoformat())))
        if tid==old_affiliations.get(pid) else now.isoformat() for pid,tid in snapshot['nbaAffiliations'].items()}
    for team in snapshot['teams']:
        for rostered in team['roster']:
            player = players[rostered['playerId']]
            rostered.update(proTeamId=affiliations.get(rostered['playerId'], pro_ids.get(player.proTeam)), slot=player.lineupSlot,
                            injuryStatus=player.injuryStatus, affiliationVerifiedAt=now.isoformat(),
                            affiliationSource='ESPN current roster')
            old = old_rosters.get((team['teamId'],rostered['playerId']), {})
            rostered['rosterSince'] = old.get('rosterSince',previous.get('rosterVerifiedAt',previous.get('updatedAt',now.isoformat()))) if old else now.isoformat()
            rostered['nbaTeamSince'] = snapshot['nbaAffiliationSince'].get(str(rostered['playerId']), now.isoformat())
    settings = raw['settings']
    roster = settings['rosterSettings']
    snapshot['lineupConstraints'] = {'daily': roster.get('lineupLocktimeType') == 'INDIVIDUAL_GAME',
        'lineupLock': roster.get('lineupLocktimeType'), 'rosterLock': roster.get('rosterLocktimeType'),
        'slotStatLimits': roster.get('lineupSlotStatLimits', {}),
        'moveLimit': roster.get('moveLimit'),
        'matchupAcquisitionLimit': settings.get('acquisitionSettings', {}).get('matchupAcquisitionLimit')}
    snapshot['rosterVerifiedAt'] = now.isoformat()
    if schedule is None:
        snapshot['nbaSchedule'] = schedule_snapshot(nba, now)
    else:
        snapshot['nbaSchedule'] = {'season':schedule.get('season'), 'verifiedAt':schedule.get('verifiedAt'),
                                   'statusAt':schedule.get('statusAt'), 'source':'seasonMetadata.nbaSchedules'}
    return snapshot
