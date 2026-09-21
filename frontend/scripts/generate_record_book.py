"""Precompute Record Book data without importing the Dash app."""
import argparse
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
POSITION_COLUMNS = ('Position', 'Position2', 'Position3')
FLEX = {'G': {'PG', 'SG'}, 'F': {'SF', 'PF'}, 'UT': {'PG', 'SG', 'SF', 'PF', 'C'}}


def scalar(value):
    return value.item() if hasattr(value, 'item') else value


def frame_records(frame, columns):
    return [{column: value if isinstance(value, dict) else None if pd.isna(value) else scalar(value)
             for column, value in row.items()}
            for row in frame[columns].to_dict('records')]


def all_time(league, weekly, daily, activity, config):
    """Intentionally retain the existing Summary / All-Time definitions."""
    top_team = league.sort_values('Points For', ascending=False).iloc[0]
    top_player = weekly.sort_values('FPTS', ascending=False).iloc[0]
    top_daily = daily.sort_values('FPTS', ascending=False).iloc[0]
    teams_by_season = {int(year): season_teams(league, int(year), config)
                       for year in league['Year'].unique()}
    team_for = lambda row: teams_by_season.get(int(row['Year']), {}).get(int(row['Team ID']))
    hundred = daily[daily['FPTS'] >= 100].copy().sort_values('Date', ascending=False)
    hundred = hundred[['Year', 'Date', 'Player Name', 'Team Name', 'Team ID', 'FPTS']]
    hundred['team'] = hundred.apply(team_for, axis=1)
    hundred['Date'] = pd.to_datetime(hundred['Date']).dt.strftime('%m/%d/%Y')
    hundred_counts = hundred['Player Name'].value_counts().rename('Count').reset_index()
    dated = daily.copy()
    dated['Date'] = pd.to_datetime(dated['Date'])
    negative = dated[(dated['FPTS'] < 0) & (~dated['Player Slot'].isin(['BE', 'IR']))].copy()
    negative.sort_values('Date', ascending=False, inplace=True)
    negative['team'] = negative.apply(team_for, axis=1)
    names = dict(zip(negative.drop_duplicates('Team ID')['Team ID'],
                     negative.drop_duplicates('Team ID')['Team Name']))
    counts = negative.groupby('Team ID').size().reset_index(name='Count')
    counts['Logo Path'] = counts['Team ID'].map(names).map(config['team_logo_paths'])
    counts = counts.dropna(subset=['Logo Path']).sort_values('Count', ascending=False)
    transactions = activity[activity['Action'].isin(['WAIVER ADDED', 'DROPPED', 'DRAFTED', 'TRADED'])]
    transactions = (transactions.groupby('Asset')['Action'].count().reset_index(name='Transaction Count')
                    .sort_values('Transaction Count', ascending=False).head(10))
    negative['Date'] = negative['Date'].dt.strftime('%m/%d/%Y')
    return {
        'champions': [{'year': year, 'team': champion_for(league, year, teams_by_season[year])}
                      for year in sorted(teams_by_season)
                      if champion_for(league, year, teams_by_season[year])],
        'records': [
            {'label': 'Most Points in a Single Matchup (Team)', 'value': f"{top_team['Team Name']} scored {top_team['Points For']} points in Week {top_team['Week']} of {top_team['Year']}", 'team': team_for(top_team)},
            {'label': 'Most Points in a Single Matchup (Player)', 'value': f"{top_player['Player Name']} scored {top_player['FPTS']} points in Week {top_player['Week']} of {top_player['Year']} for {top_player['Team Name']}", 'team': team_for(top_player)},
            {'label': 'Most Points in a Single Day (Player)', 'value': f"{top_daily['Player Name']} scored {top_daily['FPTS']} points on {top_daily['Date']} for {top_daily['Team Name']}", 'team': team_for(top_daily)},
        ],
        'transactionLeaders': frame_records(transactions, ['Asset', 'Transaction Count']),
        'hundredPointDays': frame_records(hundred, ['Date', 'Player Name', 'Team Name', 'FPTS', 'team']),
        'hundredPointCounts': frame_records(hundred_counts, ['Player Name', 'Count']),
        'negativePointDays': frame_records(negative, ['Date', 'Player Name', 'Team Name', 'FPTS', 'team']),
        'negativeTeamCounts': [{'logo': 'logos/' + Path(row['Logo Path']).name, 'count': int(row['Count'])}
                               for _, row in counts.iterrows()],
    }


def season_teams(league, year, config):
    from build_homepage import team_info
    rows = league[league['Year'] == year].sort_values('Week').drop_duplicates('Team ID', keep='last')
    return {int(row['Team ID']): team_info(row, config) for _, row in rows.iterrows()}


def player_totals(daily, year, active_slots, teams, eligibility_fallback=None):
    season = daily[daily['Year'] == year].copy()
    totals = season[season['Player Slot'].isin(active_slots)].groupby('Player ID', as_index=False)['FPTS'].sum()
    season['_date'] = pd.to_datetime(season['Date'])
    if set(POSITION_COLUMNS).issubset(season.columns):
        latest = season.sort_values(['_date', 'Scoring Period']).drop_duplicates('Player ID', keep='last')
    elif eligibility_fallback is not None:
        fallback = eligibility_fallback[eligibility_fallback['Year'] == year].copy()
        latest = fallback.sort_values('Week').drop_duplicates('Player ID', keep='last')
    else:
        raise ValueError(f'{year} daily player data is missing positional eligibility')
    result = totals.merge(latest[['Player ID', 'Player Name', 'Team ID', *POSITION_COLUMNS]], on='Player ID')
    result['positions'] = result.apply(lambda row: [row[c] for c in POSITION_COLUMNS if pd.notna(row[c])], axis=1)
    result['team'] = result['Team ID'].map(lambda value: teams.get(int(value)))
    return result.sort_values(['FPTS', 'Player ID'], ascending=[False, True]).reset_index(drop=True)


def player_record(row, slot=None):
    result = {'playerId': int(row['Player ID']), 'name': row['Player Name'],
              'points': scalar(row['FPTS']), 'positions': row['positions'], 'team': row['team']}
    if slot is not None:
        result['slot'] = slot
    return result


def all_fantasy_team(players, active_slots, bench_count):
    used, lineup = set(), []
    for slot in active_slots:
        positions = FLEX.get(slot, {slot})
        choice = next((row for _, row in players.iterrows()
                       if row['Player ID'] not in used and set(row['positions']) & positions), None)
        if choice is not None:
            used.add(choice['Player ID'])
            lineup.append(player_record(choice, slot))
    for _, row in players.iterrows():
        if len(lineup) >= len(active_slots) + bench_count:
            break
        if row['Player ID'] not in used:
            used.add(row['Player ID'])
            lineup.append(player_record(row, 'BE'))
    return lineup


def inferred_bench_count(daily, year):
    bench = daily[(daily['Year'] == year) & (daily['Player Slot'] == 'BE')]
    if bench.empty:
        return 0
    return int(bench.groupby(['Scoring Period', 'Team ID'])['Player ID'].nunique().max())


def ordered_events(activity_year):
    events = activity_year.copy()
    events['_date'] = pd.to_datetime(events['Date'])
    events['_time'] = events['Time'].fillna('')
    events['_order'] = range(len(events))
    return events.sort_values(['_date', '_time', '_order'])


def transaction_rankings(activity, team_scores, teams, action, latest_action=False, year=None):
    events = ordered_events(activity[activity['Year'] == year] if year is not None else activity)
    if latest_action:
        candidates = events.drop_duplicates('Player ID', keep='last')
        candidates = candidates[candidates['Action'] == action]
    else:
        candidates = events[events['Action'] == action].drop_duplicates(['Player ID', 'Team ID'])
    ranked = (candidates.merge(team_scores, on=['Player ID', 'Team ID'], how='left')
              .dropna(subset=['FPTS']).sort_values(['FPTS', 'Player ID'], ascending=[False, True])
              .drop_duplicates('Player ID').head(10))
    return [{'playerId': int(row['Player ID']), 'name': row['Asset'], 'points': scalar(row['FPTS']),
             'team': teams.get(int(row['Team ID']))} for _, row in ranked.iterrows()]


def champion_for(league, year, teams):
    playoffs = league[(league['Year'] == year) & (league['Type'] == 'Playoffs')]
    if playoffs.empty:
        return None
    final = playoffs[playoffs['Week'] == playoffs['Week'].max()]
    winner = final[final['Win'] == 1]
    return teams.get(int(winner.iloc[0]['Team ID'])) if not winner.empty else None


def season_awards(league, weekly, daily, activity, metadata, config, year):
    settings = next(item for item in metadata['seasons'] if int(item['season']) == year)
    slots = settings['lineupSlots']
    teams = season_teams(league, year, config)
    players = player_totals(daily, year, slots, teams, weekly)
    team_scores = (daily[(daily['Year'] == year) & daily['Player Slot'].isin(slots)]
                   .groupby(['Player ID', 'Team ID'], as_index=False)['FPTS'].sum())
    activity_year = activity[activity['Year'] == year]
    unique = (activity_year.groupby(['Player ID', 'Asset'], dropna=False)['Team ID'].nunique()
              .reset_index(name='teamCount').sort_values(['teamCount', 'Asset'], ascending=[False, True]))
    unique['rank'] = unique['teamCount'].rank(method='min', ascending=False).astype(int)
    journeymen = []
    for _, row in unique[unique['teamCount'] >= 3].iterrows():
        history = ordered_events(activity_year[activity_year['Player ID'] == row['Player ID']])
        team_ids = list(dict.fromkeys(int(value) for value in history['Team ID'].dropna()))
        journeymen.append({'playerId': None if pd.isna(row['Player ID']) else int(row['Player ID']),
                           'name': row['Asset'], 'teamCount': int(row['teamCount']),
                           'rank': int(row['rank']), 'teams': [teams[team_id] for team_id in team_ids if team_id in teams]})
    bench_count = int(settings.get('benchSlots', inferred_bench_count(daily, year)))
    return {
        'title': f'{year} Honors',
        'champion': champion_for(league, year, teams),
        'mvp': player_record(players.iloc[0]),
        'allFantasyTeam': all_fantasy_team(players, slots, bench_count),
        'bestWaiverAdds': transaction_rankings(activity_year, team_scores, teams, 'WAIVER ADDED'),
        'bestDraftPicks': transaction_rankings(activity, team_scores, teams, 'DRAFTED', True, year),
        'journeymen': journeymen,
        'roster': {'activeSlots': slots, 'benchSlots': bench_count},
    }


def build(source, output):
    from build_homepage import logo_config, write_json
    from playerDailyAggregation import load_season_metadata
    league, weekly, daily, activity = [pd.read_csv(source / name) for name in
        ('basketballBrawlLeagueData.csv', 'playerMatchupData.csv', 'playerDailyData.csv', 'activityData.csv')]
    metadata, config = load_season_metadata(), logo_config()
    years = sorted((int(year) for year in daily['Year'].unique()), reverse=True)
    payload = {'schemaVersion': 1, 'defaultYear': years[0], 'years': years,
               'allTime': all_time(league, weekly, daily, activity, config),
               'seasons': {str(year): season_awards(league, weekly, daily, activity, metadata, config, year)
                           for year in years}}
    write_json(output / 'record-book.json', payload)
    print(f'Record Book: all-time plus {len(years)} season honor sets')
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'frontend/public/data')
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
