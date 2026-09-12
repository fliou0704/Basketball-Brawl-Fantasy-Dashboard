"""Precompute the existing Dash Team Stats definitions without importing the app."""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STAT_LABELS = ('FG%', 'FT%', '3PM', 'REB', 'AST/TO', 'STL', 'BLK', 'PTS', 'FPTS', 'PPM')


def prepare_players(weekly):
    players = weekly.copy()
    for stat, divisor in {'FGM': 2, 'FGA': -1, 'FTA': -1, 'AST': 2, 'STL': 4, 'BLK': 4, 'TO': -2}.items():
        players[stat] = players[stat] / divisor
    return players


def stat_values(players, daily, year):
    rows = players[players['Year'] == year]
    totals = daily[daily['Year'] == year].groupby('Team ID').agg({'FPTS': 'sum', 'MIN': 'sum'})
    ppm = (totals['FPTS'] / totals['MIN'].replace(0, pd.NA)).to_dict()
    functions = {
        'FG%': lambda df: df['FGM'].sum() / df['FGA'].replace(0, pd.NA).sum() * 100,
        'FT%': lambda df: df['FTM'].sum() / df['FTA'].replace(0, pd.NA).sum() * 100,
        '3PM': lambda df: df['3PM'].sum(), 'REB': lambda df: df['REB'].sum(),
        'AST/TO': lambda df: df['AST'].sum() / df['TO'].replace(0, pd.NA).sum(),
        'STL': lambda df: df['STL'].sum(), 'BLK': lambda df: df['BLK'].sum(),
        'PTS': lambda df: df['PTS'].sum(), 'FPTS': lambda df: df['FPTS'].sum(),
        'PPM': lambda df: ppm.get(df['Team ID'].iloc[0]),
    }
    result = {int(t): [] for t in rows['Team ID'].unique()}
    for label, func in functions.items():
        values = pd.Series({tid: func(group) for tid, group in rows.groupby('Team ID')})
        ranks = values.dropna().rank(ascending=False, method='min')
        for tid, value in values.items():
            digits = 3 if label == 'PPM' else 2 if label in ('FG%', 'FT%', 'AST/TO') else 0
            result[int(tid)].append({'label': label, 'rank': int(ranks[tid]) if tid in ranks else None,
                                     'value': f'{value:.{digits}f}' if pd.notna(value) else 'N/A'})
    return result


def summary(players, league, activity, team_id):
    rows = players[players['Team ID'] == team_id]
    roster = rows.groupby('Player ID')['FPTS'].sum().reset_index().sort_values('FPTS', ascending=False)
    names = rows.sort_values('Year', ascending=False).drop_duplicates('Player ID')[['Player ID', 'Player Name']]
    roster = roster.merge(names, on='Player ID', how='left')
    actions = activity[activity['Team ID'] == team_id].copy()
    actions['Datetime'] = pd.to_datetime(actions['Date'] + ' ' + actions['Time'])
    actions = actions.sort_values('Datetime', ascending=False)
    history = []
    for pid in roster['Player ID'].unique():
        matches = actions[actions['Player ID'] == pid]
        nonkeepers = matches[matches['Action'] != 'KEEPER']
        action, day = ('—', '—') if matches.empty else ('KEEPER', None)
        if not nonkeepers.empty:
            action, day = nonkeepers.iloc[0][['Action', 'Date']]
        history.append({'Player ID': pid, 'Action': action, 'Date': day})
    roster = roster.merge(pd.DataFrame(history, columns=['Player ID', 'Action', 'Date']), on='Player ID', how='left').sort_values('FPTS', ascending=False)
    output = [{'playerId': int(r['Player ID']), 'name': r['Player Name'], 'fpts': str(int(r['FPTS'])),
               'action': r['Action'] if pd.notna(r['Action']) else '—',
               'date': r['Date'] if pd.notna(r['Date']) else '—',
               'inactive': r['Action'] in ('DROPPED', 'TRADED', 'NOT KEPT')} for _, r in roster.iterrows()]
    records = league[(league['Team ID'] == team_id) & (league['Type'] != 'Consolation')]
    record_output = []
    for label, subset in [('Overall Record', records), ('Regular Season', records[records['Type'] == 'Regular']), ('Playoffs', records[records['Type'] == 'Playoffs'])]:
        wins, losses = subset['Win'].sum(), subset['Loss'].sum()
        pct = f'({wins / (wins + losses):.3f})' if wins + losses > 0 else ''
        record_output.append({'label': label, 'value': f'{wins} - {losses} {pct}'.strip()})
    return {'records': record_output, 'roster': output}


def season_roster(players, daily, activity, team_id, year):
    rows = players[(players['Year'] == year) & (players['Team ID'] == team_id)]
    if rows.empty:
        return None
    roster = rows.groupby(['Player Name', 'Player ID'])['FPTS'].sum().reset_index().sort_values('FPTS', ascending=False)
    ppm = daily[(daily['Year'] == year) & (daily['Team ID'] == team_id)].groupby(['Player Name', 'Player ID']).agg({'FPTS': 'sum', 'MIN': 'sum'}).reset_index()
    ppm['PPM'] = (ppm['FPTS'] / ppm['MIN']).round(3)
    actions = activity[(activity['Team ID'] == team_id) & (activity['Year'] == year)].copy()
    actions['Datetime'] = pd.to_datetime(actions['Date'] + ' ' + actions['Time'])
    actions = actions.sort_values('Datetime', ascending=False)
    merged = roster.merge(actions, how='left', on='Player ID')
    merged = merged.sort_values('Datetime', ascending=False).drop_duplicates('Player ID')
    # Preserve Dash's name-based PPM join and latest-action ordering, including ties.
    merged = merged.merge(ppm[['Player Name', 'PPM']], on='Player Name', how='left')
    merged['Action'] = merged['Action'].fillna('KEEPER')
    merged['Date'] = merged['Date'].fillna('—')
    merged['Contribution'] = (merged['FPTS'] / roster['FPTS'].sum() * 100).round(2)
    merged = merged.sort_values('FPTS', ascending=False)
    return [{'playerId': int(r['Player ID']), 'name': r['Player Name'], 'fpts': str(int(r['FPTS'])),
             'ppm': f"{r['PPM']:.3f}" if pd.notna(r['PPM']) else 'N/A', 'action': r['Action'],
             'date': r['Date'], 'contribution': f"{r['Contribution']:.2f}%"} for _, r in merged.iterrows()]


def build(source, output):
    # Imported here to reuse safe logo configuration, not Dash's mutable dataStore.
    from build_homepage import logo_config, team_info, write_json
    league, weekly, daily, activity = [pd.read_csv(source / name) for name in
        ('basketballBrawlLeagueData.csv', 'playerMatchupData.csv', 'playerDailyData.csv', 'activityData.csv')]
    players = prepare_players(weekly)
    years = sorted(map(int, players['Year'].unique()), reverse=True)
    latest = league.sort_values('Year', ascending=False).drop_duplicates('Team ID')
    teams = [team_info(row, logo_config()) for _, row in latest.iterrows()]
    rankings = {year: stat_values(players, daily, year) for year in years}
    for team in teams:
        tid = team['teamId']
        seasons = {}
        for year in years:
            roster = season_roster(players, daily, activity, tid, year)
            seasons[str(year)] = None if roster is None else {'rankings': rankings[year][tid], 'roster': roster}
        write_json(output / 'team-stats' / f'{tid}.json', {'schemaVersion': 1, 'team': team,
                   'summary': summary(players, league, activity, tid), 'seasons': seasons})
    write_json(output / 'team-stats.json', {'schemaVersion': 1, 'years': years, 'teams': teams})
    print(f'Team Stats: {len(teams)} teams, {len(years)} seasons, all-time summaries')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'frontend/public/data')
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
