"""Shared NBA fixtures/opportunities; never copy a season into matchup payloads."""
from collections import defaultdict
from copy import deepcopy
from nbaSchedule import valid_cache, uncertainty, join_calendar
from fantasyOpportunities import prepare, remaining
from build_homepage import write_json


def build(metadata, current, calendars, scoreboard, daily, output):
    current = deepcopy(current)
    owners = defaultdict(set)
    for t in current['teams']:
        for p in t['roster']:
            owners[p['playerId']].add(t['teamId'])
    for t in current['teams']:
        if any(len(owners[p['playerId']])>1 for p in t['roster']):
            t['rosterConflict'] = True
    season = int(current['season'])
    schedule = metadata.get('nbaSchedules', {}).get(str(season))
    if not schedule or not valid_cache(schedule):
        schedule = None
    calendar = next(c for c in calendars if c['season']==season)
    by_date, by_team = defaultdict(list), defaultdict(list)
    for g in (schedule or {}).get('fixtures', []):
        by_date[g['date']].append(g['id'])
        for t in (g['home'],g['away']):
            by_team[str(t)].append(g['id'])
    shared = dict(schedule or {}, schemaVersion=2, season=season, updatedAt=current.get('updatedAt'),
                  fixtures=join_calendar((schedule or {}).get('fixtures', []),calendar.get('scheduledDays', [])), teams=(schedule or {}).get('teams', []),
                  byDate=dict(by_date), byTeam=dict(by_team), uncertainty=uncertainty(schedule or {}),
                  playerAffiliations=current.get('nbaAffiliations', {}),
                  affiliationSince=current.get('nbaAffiliationSince', {}),
                  affiliationsVerifiedAt=current.get('rosterVerifiedAt'))
    write_json(output/'nba-schedule.json', shared)
    weeks = next(s['weeks']for s in scoreboard['seasons']if s['season']==season)
    index = prepare(schedule)
    occupied = defaultdict(list)
    # Preserve actual lineup evidence even if the contributor was later dropped.
    for r in daily:
        if int(r['Year'])==season and r['Player Slot'] in calendar['lineupSlots'] and float(r['MIN'] or 0)>0:
            occupied[int(r['Team ID'])].append({'playerId':int(r['Player ID']), 'date':r['Date'], 'slot':r['Player Slot']})
    values = {str(w['week']): {str(t['teamId']):remaining(current,calendar,w,t['teamId'],schedule,index,occupied[t['teamId']])
                             for t in current['teams']} for w in weeks if w['state']!='final'}
    from matchupProjections import project_team
    fixtures={g['id']:g for g in (schedule or {}).get('fixtures',[])}
    for week in weeks:
        if week['state']=='final':
            continue
        for team in current['teams']:
            opportunity=values[str(week['week'])][str(team['teamId'])]
            opportunity['projection']=project_team(current,calendar,week,team,opportunity,fixtures)
    write_json(output/'matchup-opportunities.json', {'schemaVersion':1,'season':season,
        'updatedAt':current.get('updatedAt'),'verifiedAt':(schedule or {}).get('verifiedAt'),
        'statusAt':(schedule or {}).get('statusAt'),'weeks':values})
