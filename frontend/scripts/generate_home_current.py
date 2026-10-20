"""Project the current ESPN snapshot into Home without requiring completed games."""
import hashlib
import json
from datetime import date, timedelta

from build_homepage import (bracket_view, display, logo_config, number, player_info,
                            read_csv, team_info, write_json)


def project(current, calendar, mapping, daily, manifest, seasonal, league, config):
    year, period, week = (int(current[k]) for k in ('season', 'scoringPeriod', 'week'))
    periods = {int(r['Scoring Period']): int(r['Week']) for r in mapping if int(r['Year']) == year}
    anchor = date.fromisoformat(calendar['dateAnchor'])
    as_of = (anchor + timedelta(days=period)).isoformat()
    active = (calendar['firstPeriod'] <= period <= calendar['finalPeriod']
              and periods.get(period) == week and week > 0)
    result = {'schemaVersion': 1, 'active': active, 'season': year, 'week': week,
              'scoringPeriod': period, 'asOfDate': as_of,
              'seasonStart': (anchor + timedelta(days=calendar['firstPeriod'])).isoformat(),
              'seasonEnd': (anchor + timedelta(days=calendar['finalPeriod'])).isoformat(),
              'matchups': [], 'players': []}
    if not active:
        return result
    teams = {int(t['teamId']): team_info({'Team ID': t['teamId'], 'Team Name': t['teamName']}, config)
             for t in current['teams']}
    for match in calendar['matchups']:
        if int(match['week']) != week or len(match['sides']) != 2:
            continue
        scores = [sum(number(v) for p, v in side['pointsByPeriod'].items()
                      if int(p) <= period and periods.get(int(p)) == week) for side in match['sides']]
        result['matchups'].append({'teams': [teams[int(side['teamId'])] for side in match['sides']],
                                   'scoreDisplay': list(map(display, scores))})
    # Rank individual player-games, not weekly player totals. MIN > 0 establishes
    # participation, but does not establish that the NBA game is final.
    rows = [r for r in daily if int(r['Year']) == year and int(r['Scoring Period']) <= period
            and periods.get(int(r['Scoring Period'])) == week and number(r.get('MIN')) > 0]
    unique = {}
    for row in sorted(rows, key=lambda r: (-number(r['FPTS']), -int(r['Scoring Period']),
                                           int(r['Player ID']), int(r['Team ID']))):
        unique.setdefault((int(row['Player ID']), int(row['Scoring Period'])), row)
    result['players'] = [dict(player_info(r, teams), date=r['Date'], scoringPeriod=int(r['Scoring Period']))
                         for r in list(unique.values())[:5]]
    descriptor = next((s for s in manifest['calendars'] if s['season'] == year), {})
    prior = [w for w in descriptor.get('completedWeeks', []) if w < week]
    daily_date = max((d for d in seasonal.get('daily-recap', {}) if d < as_of), default=None)
    standings_week = max((int(w) for w in seasonal.get('standings', {}) if int(w) < week), default=0)
    playoff = week > calendar['regularWeeks']
    result['state'] = {'season': year, 'week': week, 'phase': 'playoffs' if playoff else 'regular',
                       'dailyDate': daily_date, 'weeklyWeek': max(prior, default=None),
                       'standingsWeek': standings_week,
                       'weeklyFirst': bool(prior and period == min(p for p, w in periods.items() if w == week)),
                       'playoffKey': str(week) if playoff else None}
    if playoff:
        result['bracket'] = seasonal.get('playoffs', {}).get(str(week)) or bracket_view(
            [r for r in league if int(r['Year']) == year], calendar, teams, week)
    return result


def build(source, output):
    current_path = source / 'currentLeague.json'
    current = None
    if current_path.exists() and (source / 'seasonMetadata.json').exists():
        snapshot = json.loads(current_path.read_text())
        calendar = next(s for s in json.loads((source / 'seasonMetadata.json').read_text())['seasons']
                        if s['season'] == snapshot['season'])
        seasonal = {}
        for name in ('daily-recap', 'weekly-recap', 'standings', 'playoffs'):
            path = output / str(snapshot['season']) / f'{name}.json'
            seasonal[name] = json.loads(path.read_text())['data'] if path.exists() else {}
        current = project(snapshot, calendar, read_csv(source / 'scoringPeriodMatchupMap.csv'),
                          read_csv(source / 'playerDailyData.csv'),
                          json.loads((output / 'homepage.json').read_text()), seasonal,
                          read_csv(source / 'basketballBrawlLeagueData.csv'), logo_config())
    write_json(output / 'home-current.json', current or {'schemaVersion': 1, 'active': False})
    # Content-derived and deterministic: unchanged refreshes must not trigger a
    # deployment just because an exporter ran again. Publication time is supplied
    # by the HTTP Last-Modified header, not an invented ingestion timestamp.
    digest = hashlib.sha256()
    paths = [output / 'homepage.json', output / 'home-current.json']
    paths += [p for p in output.glob('[0-9]*/*.json') if p.parent.name.isdigit()]
    for path in sorted(paths):
        digest.update(str(path.relative_to(output)).encode())
        digest.update(path.read_bytes())
    write_json(output / 'home-version.json', {'schemaVersion': 1, 'version': digest.hexdigest()})
