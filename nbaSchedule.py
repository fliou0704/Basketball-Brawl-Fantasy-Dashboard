"""Canonical NBA fixtures, separate from observed fantasy player performances.

Persist the dataset in seasonMetadata.nbaSchedules through the existing atomic
updater commit. Full fantasy schedules are fetched daily; recent public NBA
scoreboards supply status changes without reloading the season every three hours.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')
DAY = timedelta(hours=24)
FANTASY_URL = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{season}'
SCOREBOARD_URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
# Published NBA season rules, not dates assigned to unannounced games. Unknown
# future seasons retain global uncertainty rather than copying this Cup window.
SEASON_RULES = {2027: {'expectedTeamGames': 82, 'publishedMinimum': 80,
    'regularStart': '2026-10-20', 'regularEnd': '2027-04-11',
    'cupWindow': ['2026-12-04', '2026-12-10'],
    'source': 'https://pr.nba.com/2026-27-nba-regular-season-schedule/'}}


class ScheduleError(ValueError):
    pass


def instant(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ScheduleError('NBA timestamps require an explicit timezone')
    return result.astimezone(timezone.utc)


def request_json(url, params):
    import requests
    import time
    for attempt in range(2):
        try:
            response = requests.get(url, params=params, timeout=(10, 35))
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            if attempt:
                raise ScheduleError('ESPN NBA request failed') from None
            time.sleep(1)


def fetch_schedule(season):
    return request_json(FANTASY_URL.format(season=season), {'view': 'proTeamSchedules_wl'})


def normalize(raw, season, previous=None, parser_only=False, now=None):
    try:
        teams = [{'id': int(t['id']), 'abbrev': t['abbrev']}
                 for t in raw['settings']['proTeams'] if int(t['id']) != 0]
        if len(teams) != 30 or len({t['id'] for t in teams}) != 30:
            raise ScheduleError('NBA team coverage is incomplete')
        ids = {t['id'] for t in teams}
        rules = SEASON_RULES.get(season, {'expectedTeamGames': 82, 'publishedMinimum': 80})
        known_ids = {g['id']for g in (previous or {}).get('fixtures', []) if g['regularSeason']}
        records, appearances = {}, Counter()
        for team in raw['settings']['proTeams']:
            tid = int(team['id'])
            if not tid:
                continue
            for period, games in team['proGamesByScoringPeriod'].items():
                if int(period) < 1:
                    continue
                for game in games:
                    if any(k in game and not isinstance(game[k],bool) for k in ('statsOfficial','startTimeTBD','validForLocking')):
                        raise ScheduleError('invalid NBA fixture state flags')
                    gid = int(game['id'])
                    if gid<=0:
                        raise ScheduleError('invalid NBA game identity')
                    home, away = int(game['homeProTeamId']), int(game['awayProTeamId'])
                    if home not in ids or away not in ids or home == away or tid not in (home, away):
                        raise ScheduleError('invalid NBA fixture participants')
                    start = datetime.fromtimestamp(game['date']/1000, timezone.utc)
                    day = start.astimezone(NY).date().isoformat()
                    if start.astimezone(NY).year not in (season-1,season):
                        raise ScheduleError('NBA fixture dates do not match requested season')
                    if 'regularStart' in rules and not rules['regularStart'] <= day <= rules['regularEnd'] and gid not in known_ids:
                        continue
                    # Fantasy's regular-season pro schedule excludes the Cup
                    # championship (independently checked against competition 39).
                    row = {'id': gid, 'season': season, 'start': start.isoformat(), 'date': day,
                           'home': home, 'away': away, 'period': int(period),
                           'timeTBD': game.get('startTimeTBD') is True,
                           'status': 'completed' if game.get('statsOfficial') else 'tbd' if game.get('startTimeTBD') else 'scheduled' if game.get('validForLocking') else 'unknown',
                           'regularSeason': True, 'statsOfficial': bool(game.get('statsOfficial')),
                           'hasStarted': bool(game.get('statsOfficial')),
                           'validForLocking': game.get('validForLocking', False)}
                    if gid in records and records[gid] != row:
                        raise ScheduleError('conflicting duplicate NBA game ID')
                    records[gid] = row
                    appearances[(gid, tid)] += 1
        if any(appearances[(g['id'], tid)] != 1 for g in records.values() for tid in (g['home'], g['away'])):
            raise ScheduleError('NBA fixtures must occur exactly once for each participating team')
        old = {g['id']: g for g in (previous or {}).get('fixtures', [])}
        added = set(records)-set(old)
        for gid in set(old)-set(records):
            prior = old[gid]
            tombstone = deepcopy(prior)
            if prior['status'] not in ('canceled','replaced'):
                replacements = [n for n in added if all(records[n][k]==prior[k] for k in ('start','home','away'))]
                if (len(replacements)!=1 or prior['status'] in ('completed','in-progress')
                        or instant(prior['start'])<=(now or datetime.now(timezone.utc))):
                    raise ScheduleError('ESPN omitted previously verified NBA game IDs; replacement is unconfirmed')
                replacement = replacements[0]
                added.remove(replacement)
                tombstone.update(status='replaced',regularSeason=False,replacedBy=replacement)
            records[gid] = tombstone
        counts = Counter(t for g in records.values() if g['regularSeason'] for t in (g['home'], g['away']))
        active_counts = Counter(t for g in records.values() if g['regularSeason'] and g['status']!='canceled' for t in (g['home'],g['away']))
        if not records or any(counts[t]<1 for t in ids):
            raise ScheduleError('empty NBA schedule is not verified coverage')
        if not parser_only and any(counts[t]<rules['publishedMinimum'] or active_counts[t]>rules['expectedTeamGames'] for t in ids):
            raise ScheduleError('published NBA schedule is partial or contains extra nonregular games')
        for gid, g in records.items():
            prior = old.get(gid)
            if prior and prior.get('hasStarted'):
                g['hasStarted'] = True
                if prior.get('originalStart') or prior['start']!=g['start']:
                    g['originalStart'] = prior.get('originalStart',prior['start'])
            if prior and prior['status'] in ('completed', 'in-progress'):
                if any(g[k] != prior[k] for k in ('home', 'away', 'date')):
                    raise ScheduleError('NBA refresh contradicts a started historical fixture')
            # Preserve the richer public status until a new start time clearly
            # resolves a postponement. Never downgrade a completed game.
            if prior and g['status']!='completed' and prior['start'] == g['start'] and prior['status'] in ('completed', 'in-progress', 'postponed', 'canceled'):
                g['status'] = prior['status']
                g['regularSeason'] = prior['regularSeason']
        return {'schemaVersion': 2, 'season': season, 'teams': sorted(teams, key=lambda t:t['id']),
                'fixtures': sorted(records.values(), key=lambda g:(g['date'], g['id'])),
                'rules': rules, 'publishedComplete': not parser_only, 'parserOnly':parser_only,
                'source': 'ESPN proTeamSchedules_wl + NBA scoreboards'}
    except (KeyError, TypeError, ValueError, OverflowError, OSError) as error:
        if isinstance(error, ScheduleError):
            raise
        raise ScheduleError('malformed ESPN NBA fixture response') from None


def refresh(previous, season, now, force=False, fetch=fetch_schedule, log=print, parser_only=False):
    if now.tzinfo is None:
        raise ScheduleError('NBA refresh clock requires an explicit timezone')
    old = previous if previous and previous.get('season') == season else {}
    value = deepcopy(old)
    if parser_only and old.get('fixtures') and not force:
        log('NBA schedule: using frozen historical parser cache; no historical opportunities estimated.')
        return value
    if not force:
        for key in ('lastAttemptAt', 'verifiedAt'):
            try:
                if now - instant(value[key]) < DAY:
                    log('NBA schedule: using persisted daily cache/cooldown.')
                    return value
            except (KeyError, ValueError, TypeError):
                pass
    moment = now.astimezone(timezone.utc).isoformat()
    value['lastAttemptAt'] = moment
    try:
        candidate = normalize(fetch(season), season, old, parser_only=parser_only, now=now)
        before = {g['id']:g for g in old.get('fixtures', [])}
        changed = [g['id'] for g in candidate['fixtures'] if before.get(g['id']) != g]
        log(f'NBA schedule: accepted {len(candidate["fixtures"])} fixtures / 30 teams; {len(changed)} new or changed IDs; sample {changed[:12]}.')
        if before and changed:
            log('NBA fixture changes: ' + json.dumps([{'id':g['id'],'before':{k:before.get(g['id'],{}).get(k) for k in ('start','home','away','status')},
                'after':{k:g.get(k)for k in ('start','home','away','status')}} for g in candidate['fixtures'] if g['id'] in changed][:6],sort_keys=True))
        return dict(candidate, verifiedAt=moment, lastAttemptAt=moment)
    except ScheduleError as error:
        value['lastError'] = str(error)
        log(f'NBA schedule: {error}; previous fixtures retained.')
        return value


def wrapper_schedule(schedule):
    """Reconstitute only the fields espn_api needs, sharing the daily cache."""
    if not schedule.get('fixtures'):
        raise ScheduleError('no usable NBA schedule for ESPN player-date parsing')
    teams = {t['id']:dict(t, proGamesByScoringPeriod={}) for t in schedule['teams']}
    teams[0] = {'id':0, 'abbrev':'FA', 'proGamesByScoringPeriod':{}}
    for g in schedule['fixtures']:
        if not g['regularSeason'] or g['status'] == 'canceled':
            continue
        row = {'id':g['id'], 'date':int(instant(g['start']).timestamp()*1000),
               'homeProTeamId':g['home'], 'awayProTeamId':g['away'],
               'scoringPeriodId':g['period'], 'statsOfficial':g['statsOfficial'],
               'startTimeTBD':g['timeTBD'], 'validForLocking':g['validForLocking']}
        for tid in (g['home'], g['away']):
            teams[tid]['proGamesByScoringPeriod'].setdefault(str(g['period']), []).append(row)
    return {'settings':{'proTeams':list(teams.values())}}


def recent_status(schedule, now, calendar=None, fetch=request_json, log=print):
    """Two small day reads each update; absence never means canceled/completed."""
    value = deepcopy(schedule)
    if not value.get('fixtures'):
        return value
    games = {g['id']:g for g in value['fixtures']}
    dates = {d['date']: d['period'] for d in (calendar or {}).get('days', [])}
    try:
        for offset in (-1, 0):
            day = now.astimezone(NY).date() + timedelta(days=offset)
            raw = fetch(SCOREBOARD_URL, {'dates':day.strftime('%Y%m%d'), 'limit':100})
            if not isinstance(raw,dict) or not isinstance(raw.get('events'), list) or not raw.get('leagues'):
                raise ScheduleError('invalid recent NBA scoreboard')
            expected = {g['id'] for g in games.values() if g['date']==day.isoformat() and g['regularSeason']
                        and g['status'] not in ('completed','canceled','replaced')}
            received = {int(e['id']) for e in raw['events'] if int(e.get('season',{}).get('year',0))==value['season']}
            if expected-received:
                raise ScheduleError('recent NBA scoreboard omitted known fixtures')
            for event in raw['events']:
                if int(event.get('season', {}).get('year', 0)) != value['season']:
                    continue
                gid = int(event['id'])
                if gid not in games:
                    continue  # An NBA event alone does not establish fantasy eligibility.
                comp = event['competitions'][0]
                g = games[gid]
                participants = {int(t['id']) for t in comp['competitors']}
                if participants != {g['home'], g['away']}:
                    raise ScheduleError('NBA scoreboard participants conflict with fixture')
                if int(event['season']['type']) != 2 or str(comp['type']['id']) == '39':
                    g['regularSeason'] = False
                    continue
                status = event['status']['type']
                name = status['name']
                state = ('postponed' if 'POSTPON' in name or 'SUSPEND' in name else
                         'canceled' if 'CANCEL' in name else 'completed' if status.get('completed') else
                         'in-progress' if status['state']=='in' else 'scheduled' if status['state']=='pre' else 'unknown')
                start = instant(event['date'])
                date_string = start.astimezone(NY).date().isoformat()
                if g['status'] == 'completed' and (date_string != g['date'] or state != 'completed'):
                    raise ScheduleError('NBA status refresh would rewrite a completed fixture')
                g.update(status=state, start=start.isoformat(), date=date_string,
                         timeTBD=comp.get('timeValid') is not True,
                         statusVerifiedAt=now.astimezone(timezone.utc).isoformat())
                g['hasStarted'] = g.get('hasStarted',False) or state in ('in-progress','completed') or 'SUSPEND' in name
                if date_string in dates:
                    g['period'] = dates[date_string]
        value['statusAt'] = now.astimezone(timezone.utc).isoformat()
        value.pop('statusError', None)
        return value
    except (ScheduleError, KeyError, TypeError, ValueError):
        result = deepcopy(schedule)
        result['statusError'] = 'Recent NBA status unavailable; started games remain excluded conservatively.'
        log(result['statusError'])
        return result


def uncertainty(schedule):
    counts = Counter(t for g in schedule.get('fixtures', []) if g['regularSeason'] and g['status']!='canceled' for t in (g['home'],g['away']))
    canceled = {t for g in schedule.get('fixtures', []) if g['status']=='canceled' and g['regularSeason'] for t in (g['home'],g['away'])}
    target = schedule.get('rules', {}).get('expectedTeamGames')
    return {str(t['id']): {'unassigned':max(0,target-counts[t['id']]) if target else None,
                          'cupWindow':None if t['id'] in canceled else schedule.get('rules', {}).get('cupWindow'),
                          'undated':sum(g['status']=='postponed' or g.get('hasStarted',False) and g['status']not in('completed','in-progress','canceled') for g in schedule.get('fixtures', []) if t['id'] in (g['home'],g['away']) and g['regularSeason'])}
            for t in schedule.get('teams', [])}


def valid_cache(value):
    try:
        if value['schemaVersion']!=2 or value['publishedComplete'] is not True:
            return False
        instant(value['verifiedAt'])
        teams = {t['id'] for t in value['teams']}
        if len(teams)!=30 or len(value['teams'])!=30 or len({g['id']for g in value['fixtures']})!=len(value['fixtures']):
            return False
        counts, active = Counter(), Counter()
        for g in value['fixtures']:
            if g['home'] not in teams or g['away'] not in teams or g['home']==g['away'] or g['season']!=value['season']:
                return False
            if instant(g['start']).astimezone(NY).date().isoformat()!=g['date']:
                return False
            if g['status'] not in ('scheduled','tbd','unknown','completed','in-progress','postponed','canceled','replaced'):
                return False
            if g['regularSeason']:
                counts.update([g['home'],g['away']])
                if g['status']!='canceled':
                    active.update([g['home'],g['away']])
        return all(counts[t]>=value['rules']['publishedMinimum'] and active[t]<=value['rules']['expectedTeamGames'] for t in teams)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def join_calendar(fixtures, days):
    """NBA date -> verified fantasy day/week; outside-league dates stay null."""
    lookup = {d['date']:d for d in days}
    return [dict(g, fantasyPeriod=lookup.get(g['date'],{}).get('period'),
                 fantasyWeek=lookup.get(g['date'],{}).get('week')) for g in fixtures]
