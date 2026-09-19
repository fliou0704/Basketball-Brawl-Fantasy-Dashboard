"""Precompute the existing Dash Team Stats definitions without importing the app."""
import argparse
import math
from pathlib import Path
import shutil

import pandas as pd

from generate_standings import build_standings

ROOT = Path(__file__).resolve().parents[2]
STAT_LABELS = ('FG%', 'FT%', '3PM', 'REB', 'AST/TO', 'STL', 'BLK', 'PTS', 'FPTS', 'PPM')
RANK_NAMES = ('first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth')
INACTIVE_ACTIONS = ('DROPPED', 'TRADED', 'NOT KEPT')


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
        last_rank = int(ranks.max()) if not ranks.empty else None
        for tid, value in values.items():
            digits = 3 if label == 'PPM' else 2 if label in ('FG%', 'FT%', 'AST/TO') else 0
            rank = int(ranks[tid]) if tid in ranks else None
            relative = (last_rank - rank) / (last_rank - 1) * 100 if rank and last_rank > 1 else 100 if rank == 1 else None
            result[int(tid)].append({'label': label, 'rank': rank,
                                     'rankImage': f'placements/{RANK_NAMES[rank - 1]}.png' if rank else None,
                                     'relativePercent': round(relative, 1) if relative is not None else None,
                                     'value': f'{value:.{digits}f}' if pd.notna(value) else 'N/A'})
    return result


def player_percentiles(players, daily, year):
    """League-relative season percentiles for fantasy-relevant players."""
    weekly = players[players['Year'] == year].sort_values('FPTS', ascending=False)
    weekly = weekly.drop_duplicates(['Week', 'Player ID'])
    fpts = weekly.groupby('Player ID')['FPTS'].sum()
    daily_rows = daily[(daily['Year'] == year) & (daily['MIN'] > 0)]
    efficiency = daily_rows.groupby('Player ID').agg({'FPTS': 'sum', 'MIN': 'sum'})
    fppm = efficiency['FPTS'] / efficiency['MIN'].replace(0, pd.NA)

    def percentile(series):
        series = series[(series > 0) & series.notna()]
        ranks = series.rank(ascending=False, method='min')
        count = len(series)
        return {int(pid): round((count - rank) / (count - 1) * 100, 1) if count > 1 else 100
                for pid, rank in ranks.items()}

    fpts_pct, fppm_pct = percentile(fpts), percentile(fppm)
    return {int(pid): {'fptsPercentile': fpts_pct.get(int(pid)), 'fppmPercentile': fppm_pct.get(int(pid))}
            for pid in set(fpts_pct) | set(fppm_pct)}


def weekly_performance(players, team_id, year):
    rows = players[(players['Year'] == year) & (players['Team ID'] == team_id)]
    totals = rows.groupby('Week')['FPTS'].sum().sort_index()
    if totals.empty:
        return None
    weeks = [int(week) for week in totals.index]
    maximum = float(totals.max())
    ceiling = max(100, math.ceil(maximum / 500) * 500)
    left, right, top, bottom = 54, 770, 20, 215
    points = []
    for index, (week, value) in enumerate(totals.items()):
        x = left if len(totals) == 1 else left + index * (right - left) / (len(totals) - 1)
        y = bottom - float(value) / ceiling * (bottom - top)
        points.append({'week': int(week), 'value': round(float(value), 1),
                       'display': f'{float(value):,.0f}', 'x': round(x, 2), 'y': round(y, 2)})
    ticks = [{'value': round(ceiling * part), 'display': f'{ceiling * part:,.0f}',
              'y': round(bottom - part * (bottom - top), 2)} for part in (0, .25, .5, .75, 1)]
    return {'metrics': {'fpts': {'label': 'FPTS', 'path': ' '.join(f"{p['x']},{p['y']}" for p in points),
                                  'points': points, 'yTicks': ticks}},
            'weeks': weeks, 'viewBox': [0, 0, 800, 250]}


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


def season_roster(players, daily, activity, team_id, year, quality=None):
    rows = players[(players['Year'] == year) & (players['Team ID'] == team_id)]
    if rows.empty:
        return None
    stat_columns = ['FPTS', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', '3PM', 'FGM', 'FGA', 'FTM', 'FTA']
    roster = rows.groupby(['Player Name', 'Player ID'])[stat_columns].sum().reset_index().sort_values('FPTS', ascending=False)
    daily_rows = daily[(daily['Year'] == year) & (daily['Team ID'] == team_id)]
    ppm = daily_rows.groupby(['Player Name', 'Player ID']).agg({'FPTS': 'sum', 'MIN': 'sum'}).reset_index()
    ppm['PPM'] = (ppm['FPTS'] / ppm['MIN']).round(3)
    games = daily_rows[daily_rows['MIN'] > 0].groupby('Player ID')['Date'].nunique().rename('Games')
    actions = activity[(activity['Team ID'] == team_id) & (activity['Year'] == year)].copy()
    actions['Datetime'] = pd.to_datetime(actions['Date'] + ' ' + actions['Time'])
    actions = actions.sort_values('Datetime', ascending=False)
    merged = roster.merge(actions, how='left', on='Player ID')
    merged = merged.sort_values('Datetime', ascending=False).drop_duplicates('Player ID')
    # Preserve Dash's name-based PPM join and latest-action ordering, including ties.
    merged = merged.merge(ppm[['Player Name', 'PPM']], on='Player Name', how='left')
    merged = merged.merge(games, on='Player ID', how='left')
    merged['Action'] = merged['Action'].fillna('KEEPER')
    merged['Date'] = merged['Date'].fillna('—')
    merged['Games'] = merged['Games'].fillna(0).astype(int)
    merged['Contribution'] = (merged['FPTS'] / roster['FPTS'].sum() * 100).round(2)
    merged = merged.sort_values('FPTS', ascending=False)
    quality = quality or {}
    return [{'playerId': int(r['Player ID']), 'name': r['Player Name'], 'fpts': str(int(r['FPTS'])), 'games': int(r['Games']),
             'points': str(int(r['PTS'])), 'rebounds': str(int(r['REB'])), 'assists': str(int(r['AST'])),
             'steals': str(int(r['STL'])), 'blocks': str(int(r['BLK'])), 'turnovers': str(int(r['TO'])),
             'threePointers': str(int(r['3PM'])),
             'fieldGoalPct': f"{r['FGM'] / r['FGA'] * 100:.1f}%" if r['FGA'] else 'N/A',
             'freeThrowPct': f"{r['FTM'] / r['FTA'] * 100:.1f}%" if r['FTA'] else 'N/A',
             **quality.get(int(r['Player ID']), {'fptsPercentile': None, 'fppmPercentile': None}),
             'current': r['Action'] not in INACTIVE_ACTIONS,
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
    config = logo_config()
    placements = output.parent / 'placements'
    placements.mkdir(parents=True, exist_ok=True)
    for name in RANK_NAMES:
        shutil.copyfile(ROOT / 'assets' / 'placements' / f'{name}.png', placements / f'{name}.png')
    teams = [dict(team_info(row, config), owner=row['Team Owner']) for _, row in latest.iterrows()]
    rankings = {year: stat_values(players, daily, year) for year in years}
    quality = {year: player_percentiles(players, daily, year) for year in years}
    # Match the site's regular-season standings snapshots; playoff placement is not
    # the Team page's standings rank.
    regular_rows = league[league['Type'] == 'Regular'].to_dict('records')
    standings = {year: build_standings(regular_rows, year) for year in years}
    for year, table in standings.items():
        season_rows = league[league['Year'] == year].sort_values('Week', ascending=False).drop_duplicates('Team ID')
        identities = {int(row['Team ID']): team_info(row, config) for _, row in season_rows.iterrows()}
        for row in table['teams']:
            row.update(identities[row['teamId']])
    for team in teams:
        tid = team['teamId']
        seasons = {}
        for year in years:
            roster = season_roster(players, daily, activity, tid, year, quality[year])
            standing = next((row for row in standings[year]['teams'] if row['teamId'] == tid), None)
            seasons[str(year)] = None if roster is None else {
                'rankings': rankings[year][tid], 'roster': roster,
                'weeklyPerformance': weekly_performance(players, tid, year),
                'snapshot': None if standing is None else {
                    key: standing[key] for key in ('rank', 'record', 'wins', 'losses', 'pointsFor',
                                                   'pointsAgainst', 'pointsForDisplay', 'pointsAgainstDisplay')
                }
            }
        write_json(output / 'team-stats' / f'{tid}.json', {'schemaVersion': 1, 'team': team,
                   'summary': summary(players, league, activity, tid), 'seasons': seasons})
    write_json(output / 'team-stats.json', {'schemaVersion': 1, 'years': years, 'teams': teams,
                                             'standings': {str(year): standings[year] for year in years}})
    print(f'Team Stats: {len(teams)} teams, {len(years)} seasons, all-time summaries')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'frontend/public/data')
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
