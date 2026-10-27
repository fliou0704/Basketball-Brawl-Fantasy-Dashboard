"""Overlay current official standings and roster membership on static exports."""
import json
import pandas as pd

from build_homepage import logo_config, team_info, write_json
from teamPerformance import combine_performance


def build(source, output):
    path = source / 'currentLeague.json'
    if not path.exists():
        return
    current = json.loads(path.read_text())
    manifest = json.loads((output / 'team-stats.json').read_text())
    config = logo_config()
    year = str(current['season'])
    from playerDailyAggregation import aggregate_daily_to_weekly, load_season_metadata, load_scoring_period_map
    from generate_team_stats import (prepare_players, stat_values, player_percentiles, season_roster,
                                     weekly_performance, physical_metrics, summary)
    daily = pd.read_csv(source / 'playerDailyData.csv')
    activity = pd.read_csv(source / 'activityData.csv')
    season_metadata = load_season_metadata()
    daily_weekly = aggregate_daily_to_weekly(daily, load_scoring_period_map(), season_metadata, active_only=True)
    live_daily = daily_weekly[daily_weekly['Year'] == int(year)]
    live_players = prepare_players(live_daily) if not live_daily.empty else None
    rankings = stat_values(live_players, daily, int(year)) if live_players is not None else {}
    quality = player_percentiles(live_players, daily, int(year)) if live_players is not None else {}
    historical_weekly = pd.read_csv(source / 'playerMatchupData.csv')
    summary_players = prepare_players(historical_weekly[historical_weekly['Year'] != int(year)])
    if live_players is not None:
        summary_players = pd.concat([summary_players, live_players], ignore_index=True)
    league = pd.read_csv(source / 'basketballBrawlLeagueData.csv')
    teams, standings = [], []
    for row in sorted(current['teams'], key=lambda t: (t['rank'], t['teamId'])):
        identity = dict(team_info({'Team ID': row['teamId'], 'Team Name': row['teamName']}, config), owner=row['owner'])
        teams.append(identity)
        standings.append({**identity, **{key: row[key] for key in ('rank', 'wins', 'losses', 'pointsFor', 'pointsAgainst')},
            'record': f"{row['wins']}–{row['losses']}", 'pointsForDisplay': f"{row['pointsFor']:,.0f}",
            'pointsAgainstDisplay': f"{row['pointsAgainst']:,.0f}", 'abbreviation': row['abbreviation']})
    table = {'schemaVersion': 1, 'season': int(year), 'currentWeek': current['week'],
        'statsThroughWeek': max(0, current['week'] - 1), 'ranksThroughWeek': max(0, current['week'] - 1),
        'teamCount': len(teams), 'statsScope': 'Official ESPN standings', 'source': 'currentLeague.json', 'teams': standings}
    manifest['teams'] = teams
    manifest['years'] = sorted(set(manifest['years']) | {int(year)}, reverse=True)
    manifest['standings'][year] = table
    for identity, live in zip(teams, sorted(current['teams'], key=lambda t: (t['rank'], t['teamId']))):
        path = output / 'team-stats' / f"{identity['teamId']}.json"
        payload = json.loads(path.read_text())
        payload['team'] = identity
        payload['summary'] = summary(summary_players, league, activity, identity['teamId'])
        season = payload['seasons'].get(year)
        roster = (season_roster(live_players, daily, activity, identity['teamId'], int(year), quality, daily_weekly)
                  if live_players is not None else None) or list((season or {}).get('roster', []))
        current_ids = {p['playerId'] for p in live['roster']}
        for row in payload['summary']['roster']:
            row['inactive'] = row['playerId'] not in current_ids
        for row in roster:
            row['current'] = row['playerId'] in current_ids
        represented = {p['playerId'] for p in roster}
        for player in live['roster']:
            if player['playerId'] not in represented:
                roster.append({'playerId': player['playerId'], 'name': player['name'], 'current': True,
                    **{k: '0' for k in ('fpts', 'games', 'points', 'rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'threePointers')},
                    'ppm': 'N/A', 'mpg': 'N/A', 'fieldGoalPct': 'N/A', 'freeThrowPct': 'N/A',
                    'fptsPercentile': None, 'fppmPercentile': None})
        standing = next(r for r in standings if r['teamId'] == identity['teamId'])
        snapshot = {k: standing[k] for k in ('rank', 'record', 'wins', 'losses', 'pointsFor', 'pointsAgainst', 'pointsForDisplay', 'pointsAgainstDisplay')}
        if season is None:
            from generate_team_stats import STAT_LABELS
            season = {'rankings': [{'label': k, 'rank': None, 'rankImage': None, 'relativePercent': None, 'value': 'N/A'} for k in STAT_LABELS],
                      'weeklyPerformance': None, 'physicals': []}
        payload['seasons'][year] = dict(season, roster=roster, snapshot=snapshot)
        payload['summary']['performance'] = combine_performance(
            item.get('performance', {}).get('season', {
                'available': False, 'starts': None,
                'fpts': item.get('snapshot', {}).get('pointsFor', 0),
            }) for item in payload['seasons'].values() if item is not None
        )
        if identity['teamId'] in rankings:
            payload['seasons'][year]['rankings'] = rankings[identity['teamId']]
            payload['seasons'][year]['weeklyPerformance'] = weekly_performance(daily_weekly, identity['teamId'], int(year))
        write_json(path, payload)
    rosters = {team['teamId']: json.loads((output / 'team-stats' / f"{team['teamId']}.json").read_text())['seasons'][year]['roster'] for team in teams}
    physicals = physical_metrics(rosters, pd.read_csv(source / 'playerMetadata.csv'), season_metadata, int(year))
    for team in teams:
        path = output / 'team-stats' / f"{team['teamId']}.json"
        payload = json.loads(path.read_text())
        payload['seasons'][year]['physicals'] = physicals[team['teamId']]
        write_json(path, payload)
    write_json(output / 'team-stats.json', manifest)
    write_json(output / 'standings.json', table)
    homepage = json.loads((output / 'homepage.json').read_text())
    for state in homepage['states'].values():
        if state['season'] == int(year) and state.get('standingsWeek') is None:
            state['standingsWeek'] = 0
    write_json(output / 'homepage.json', homepage)
    seasonal_path = output / year / 'standings.json'
    seasonal = json.loads(seasonal_path.read_text()) if seasonal_path.exists() else {'schemaVersion': 1, 'season': int(year), 'data': {}}
    seasonal['data']['0'] = table
    write_json(seasonal_path, seasonal)
    # The first week has no completed recap yet. Existing Home behavior shows
    # the prior completed season; Standings and Team selectors still expose it.
    playoff_path = output / year / 'playoffs.json'
    if not playoff_path.exists():
        write_json(playoff_path, {'schemaVersion': 1, 'season': int(year), 'data': {}})
    write_json(output / 'current-league.json', current)
