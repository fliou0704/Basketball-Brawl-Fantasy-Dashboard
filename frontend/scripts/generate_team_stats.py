"""Precompute the existing Dash Team Stats definitions without importing the app."""
import argparse
import math
from pathlib import Path
import shutil
import sys

import pandas as pd

from generate_standings import build_standings

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playerDailyAggregation import (aggregate_daily_to_weekly, load_scoring_period_map,
                                    load_season_metadata)

STAT_LABELS = ('FG%', 'FT%', '3PM', 'REB', 'AST/TO', 'STL', 'BLK', 'PTS', 'FPTS', 'PPM')
RANK_NAMES = ('first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth')
INACTIVE_ACTIONS = ('DROPPED', 'TRADED', 'NOT KEPT')


def ordinal(value):
    value = int(value)
    mod100 = value % 100
    suffix = 'th' if 11 <= mod100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th')
    return f'{value}{suffix}'


def point_rank_captions(teams):
    """Return tie-aware regular-season PF/PA rank captions by team ID."""
    captions = {}
    for field, ascending, output_key in (
        ('pointsFor', False, 'pointsForRankCaption'),
        ('pointsAgainst', True, 'pointsAgainstRankCaption'),
    ):
        values = pd.Series({int(team['teamId']): team[field] for team in teams})
        ranks = values.rank(ascending=ascending, method='min').astype(int)
        counts = values.value_counts()
        for team_id, value in values.items():
            prefix = 'T-' if counts[value] > 1 else ''
            captions.setdefault(int(team_id), {})[output_key] = f'{prefix}{ordinal(ranks[team_id])}'
    return captions


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


def weekly_performance(daily_weekly, team_id, year):
    """Build chart-ready weekly metrics from canonical active daily performances."""
    rows = daily_weekly[(daily_weekly['Year'] == year) & (daily_weekly['Team ID'] == team_id)]
    totals = rows.groupby('Week').agg({'FPTS': 'sum', 'MIN': 'sum', 'Fantasy Starts': 'sum'}).sort_index()
    if totals.empty:
        return None
    totals['FPPM'] = totals['FPTS'] / totals['MIN'].replace(0, pd.NA)
    weeks = [int(week) for week in totals.index]
    left, right, top, bottom = 54, 770, 20, 215

    def chart_metric(series, key, label):
        maximum = float(series.max())
        if key == 'fpts':
            ceiling = max(100, math.ceil(maximum / 500) * 500)
            display = lambda value: f'{value:,.0f}'
        elif key == 'fppm':
            ceiling = max(.1, math.ceil(maximum * 10) / 10)
            display = lambda value: f'{value:.2f}'.rstrip('0').rstrip('.')
        else:
            ceiling = max(20, math.ceil(maximum / 20) * 20)
            display = lambda value: f'{value:,.0f}'
        points = []
        for index, (week, value) in enumerate(series.items()):
            x = left if len(series) == 1 else left + index * (right - left) / (len(series) - 1)
            y = bottom - float(value) / ceiling * (bottom - top)
            points.append({'week': int(week), 'value': round(float(value), 3),
                           'display': display(float(value)), 'x': round(x, 2), 'y': round(y, 2)})
        ticks = [{'value': round(ceiling * part, 3), 'display': display(ceiling * part),
                  'y': round(bottom - part * (bottom - top), 2)} for part in (0, .25, .5, .75, 1)]
        return {'label': label, 'path': ' '.join(f"{point['x']},{point['y']}" for point in points),
                'points': points, 'yTicks': ticks}

    return {'metrics': {
                'fpts': chart_metric(totals['FPTS'], 'fpts', 'FPTS'),
                'fppm': chart_metric(totals['FPPM'], 'fppm', 'FPPM'),
                'starts': chart_metric(totals['Fantasy Starts'], 'starts', 'Starts'),
            }, 'weeks': weeks, 'viewBox': [0, 0, 800, 250]}


def roster_mpg(daily_weekly, team_id, year):
    """Aggregate credited active-lineup minutes per credited played-game start."""
    rows = daily_weekly[(daily_weekly['Year'] == year) & (daily_weekly['Team ID'] == team_id)]
    totals = rows.groupby('Player ID').agg({'MIN': 'sum', 'Fantasy Starts': 'sum'})
    return totals['MIN'] / totals['Fantasy Starts'].replace(0, pd.NA)


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


def season_roster(players, daily, activity, team_id, year, quality=None, daily_weekly=None):
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
    if daily_weekly is not None:
        mpg = roster_mpg(daily_weekly, team_id, year).rename('MPG')
        merged = merged.merge(mpg, left_on='Player ID', right_index=True, how='left')
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
             'mpg': f"{r['MPG']:.1f}" if 'MPG' in r and pd.notna(r['MPG']) else 'N/A',
             'date': r['Date'], 'contribution': f"{r['Contribution']:.2f}%"} for _, r in merged.iterrows()]


def season_reference_date(season_metadata, year):
    """Use the first saved matchup date as the season's demographic reference."""
    season = next(item for item in season_metadata['seasons'] if int(item['season']) == int(year))
    return pd.Timestamp(season['weeks'][0]['start'])


def physical_metrics(rosters, metadata, season_metadata, year):
    """Calculate and league-rank current-roster physicals for one fantasy season."""
    fields = metadata.copy()
    fields['ESPN Player ID'] = pd.to_numeric(fields['ESPN Player ID'], errors='coerce')
    fields = fields.dropna(subset=['ESPN Player ID']).drop_duplicates('ESPN Player ID')
    fields['ESPN Player ID'] = fields['ESPN Player ID'].astype(int)
    fields['Birth Date'] = pd.to_datetime(fields['Birth Date'], errors='coerce')
    fields['Height Inches'] = pd.to_numeric(fields['Height Inches'], errors='coerce')
    fields['Weight Pounds'] = pd.to_numeric(fields['Weight Pounds'], errors='coerce')
    fields = fields.set_index('ESPN Player ID')
    reference = season_reference_date(season_metadata, year)
    values = {}
    for team_id, roster in rosters.items():
        current_ids = [row['playerId'] for row in (roster or []) if row['current']]
        current = fields.reindex(current_ids)
        births = current['Birth Date'].dropna()
        ages = births.map(lambda birth: reference.year - birth.year -
                          ((reference.month, reference.day) < (birth.month, birth.day)))
        heights = current['Height Inches'].dropna()
        heights = heights[heights > 0]
        bmi_rows = current[['Height Inches', 'Weight Pounds']].dropna()
        bmi_rows = bmi_rows[(bmi_rows['Height Inches'] > 0) & (bmi_rows['Weight Pounds'] > 0)]
        bmis = 703 * bmi_rows['Weight Pounds'] / bmi_rows['Height Inches'].pow(2)
        values[int(team_id)] = {
            'age': (float(ages.mean()) if not ages.empty else None, int(ages.count())),
            'height': (float(heights.mean()) if not heights.empty else None, int(heights.count())),
            'bmi': (float(bmis.mean()) if not bmis.empty else None, int(bmis.count())),
        }

    ranks = {}
    for key, ascending in (('age', True), ('height', False), ('bmi', False)):
        series = pd.Series({team_id: metrics[key][0] for team_id, metrics in values.items()}).dropna()
        ranks[key] = series.rank(ascending=ascending, method='min').astype(int).to_dict()

    team_count = len(ranks['age'])
    output = {}
    for team_id, metrics in values.items():
        rows = []
        for key, label in (('age', 'Average Age'), ('height', 'Average Height'), ('bmi', 'Average BMI')):
            raw, sample_size = metrics[key]
            rank = ranks[key].get(team_id)
            if raw is None:
                display, caption = 'N/A', 'Not ranked'
            elif key == 'age':
                display = f'{raw:.1f}'
                oldest_rank = team_count - rank + 1
                if rank == 1:
                    caption = 'Youngest'
                elif oldest_rank == 1:
                    caption = 'Oldest'
                elif rank <= team_count / 2:
                    caption = f'{ordinal(rank)} Youngest'
                else:
                    caption = f'{ordinal(oldest_rank)} Oldest'
            elif key == 'height':
                rounded_inches = int(round(raw))
                display = f'{rounded_inches // 12}\'{rounded_inches % 12}"'
                caption = f'{ordinal(rank)} Tallest'
            else:
                display = f'{raw:.1f}'
                caption = f'{ordinal(rank)} in League'
            rows.append({'key': key, 'label': label, 'value': display,
                         'rawValue': round(raw, 4) if raw is not None else None,
                         'rank': rank, 'caption': caption, 'sampleSize': sample_size})
        output[team_id] = rows
    return output


def build(source, output):
    # Imported here to reuse safe logo configuration, not Dash's mutable dataStore.
    from build_homepage import logo_config, team_info, write_json
    league, weekly, daily, activity = [pd.read_csv(source / name) for name in
        ('basketballBrawlLeagueData.csv', 'playerMatchupData.csv', 'playerDailyData.csv', 'activityData.csv')]
    players = prepare_players(weekly)
    season_metadata = load_season_metadata()
    daily_weekly = aggregate_daily_to_weekly(
        daily, load_scoring_period_map(), season_metadata, active_only=True
    )
    metadata = pd.read_csv(source / 'playerMetadata.csv')
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
    rosters = {year: {team['teamId']: season_roster(players, daily, activity, team['teamId'], year, quality[year], daily_weekly)
                      for team in teams} for year in years}
    physicals = {year: physical_metrics(rosters[year], metadata, season_metadata, year) for year in years}
    # Match the site's regular-season standings snapshots; playoff placement is not
    # the Team page's standings rank.
    regular_rows = league[league['Type'] == 'Regular'].to_dict('records')
    standings = {year: build_standings(regular_rows, year) for year in years}
    point_ranks = {year: point_rank_captions(table['teams']) for year, table in standings.items()}
    for year, table in standings.items():
        season_rows = league[league['Year'] == year].sort_values('Week', ascending=False).drop_duplicates('Team ID')
        identities = {int(row['Team ID']): team_info(row, config) for _, row in season_rows.iterrows()}
        for row in table['teams']:
            row.update(identities[row['teamId']])
    for team in teams:
        tid = team['teamId']
        seasons = {}
        for year in years:
            roster = rosters[year][tid]
            standing = next((row for row in standings[year]['teams'] if row['teamId'] == tid), None)
            seasons[str(year)] = None if roster is None else {
                'rankings': rankings[year][tid], 'roster': roster,
                'physicals': physicals[year][tid],
                'weeklyPerformance': weekly_performance(daily_weekly, tid, year),
                'snapshot': None if standing is None else {
                    **{key: standing[key] for key in ('rank', 'record', 'wins', 'losses', 'pointsFor',
                                                       'pointsAgainst', 'pointsForDisplay', 'pointsAgainstDisplay')},
                    **point_ranks[year][tid],
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
