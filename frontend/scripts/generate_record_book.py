"""Precompute the current Dash Record Book without importing the Dash app."""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def frame_records(frame, columns):
    return [{column: (None if pd.isna(value) else value.item() if hasattr(value, 'item') else value)
             for column, value in row.items()}
            for row in frame[columns].to_dict('records')]


def all_time(league, weekly, daily, activity, logos):
    top_team = league.sort_values('Points For', ascending=False).iloc[0]
    top_player = weekly.sort_values('FPTS', ascending=False).iloc[0]
    top_daily = daily.sort_values('FPTS', ascending=False).iloc[0]

    hundred = daily[daily['FPTS'] >= 100].copy()
    hundred.sort_values('Date', ascending=False, inplace=True)
    hundred = hundred[['Date', 'Player Name', 'Team Name', 'FPTS']]
    hundred['Date'] = pd.to_datetime(hundred['Date']).dt.strftime('%m/%d/%Y')
    hundred_counts = hundred['Player Name'].value_counts().rename('Count').reset_index()

    dated_daily = daily.copy()
    dated_daily['Date'] = pd.to_datetime(dated_daily['Date'])
    negative = dated_daily[(dated_daily['FPTS'] < 0) & (~dated_daily['Player Slot'].isin(['BE', 'IR']))].copy()
    negative.sort_values('Date', ascending=False, inplace=True)
    latest_names = negative.drop_duplicates('Team ID')[['Team ID', 'Team Name']]
    name_by_id = dict(zip(latest_names['Team ID'], latest_names['Team Name']))
    negative_counts = negative.groupby('Team ID').size().reset_index(name='Count')
    negative_counts['Team Name'] = negative_counts['Team ID'].map(name_by_id)
    negative_counts['Logo Path'] = negative_counts['Team Name'].map(logos)
    negative_counts = negative_counts[['Logo Path', 'Count']].dropna().sort_values('Count', ascending=False)

    transactions = activity[activity['Action'].isin(['WAIVER ADDED', 'DROPPED', 'DRAFTED', 'TRADED'])]
    transactions = (transactions.groupby('Asset')['Action'].count().reset_index(name='Transaction Count')
                    .sort_values('Transaction Count', ascending=False).head(10))

    negative_table = negative[['Date', 'Player Name', 'Team Name', 'FPTS']].copy()
    negative_table['Date'] = negative_table['Date'].dt.strftime('%m/%d/%Y')
    return {
        'records': [
            {'label': 'Most Points in a Single Matchup (Team)',
             'value': f"{top_team['Team Name']} scored {top_team['Points For']} points in Week {top_team['Week']} of {top_team['Year']}"},
            {'label': 'Most Points in a Single Matchup (Player)',
             'value': f"{top_player['Player Name']} scored {top_player['FPTS']} points in Week {top_player['Week']} of {top_player['Year']} for {top_player['Team Name']}"},
            {'label': 'Most Points in a Single Day (Player)',
             'value': f"{top_daily['Player Name']} scored {top_daily['FPTS']} points on {top_daily['Date']} for {top_daily['Team Name']}"},
        ],
        'transactionLeaders': frame_records(transactions, ['Asset', 'Transaction Count']),
        'hundredPointDays': frame_records(hundred, ['Date', 'Player Name', 'Team Name', 'FPTS']),
        'hundredPointCounts': frame_records(hundred_counts, ['Player Name', 'Count']),
        'negativePointDays': frame_records(negative_table, ['Date', 'Player Name', 'Team Name', 'FPTS']),
        'negativeTeamCounts': [
            {'logo': 'logos/' + Path(row['Logo Path']).name, 'count': int(row['Count'])}
            for _, row in negative_counts.iterrows()
        ],
    }


def all_nba_teams(year_df):
    position_rows = []
    for player, group in year_df.groupby('Player Name'):
        total = group['FPTS'].sum()
        positions = (set(group['Position'].dropna().unique()) |
                     set(group['Position2'].dropna().unique()) |
                     set(group['Position3'].dropna().unique()))
        for position in positions:
            position_rows.append({'Player Name': player, 'Position': position, 'FPTS': total})
    positions = pd.DataFrame(position_rows).sort_values('FPTS', ascending=False)

    def select(used):
        team = []
        for slot in ['G', 'G', 'F', 'F', 'C']:
            eligible_positions = ['PG', 'SG'] if slot == 'G' else ['SF', 'PF'] if slot == 'F' else ['C']
            eligible = positions[positions['Position'].isin(eligible_positions) &
                                 (~positions['Player Name'].isin(used))]
            if not eligible.empty:
                player_row = eligible.iloc[0]
                name = player_row['Player Name']
                latest = year_df[year_df['Player Name'] == name].sort_values('Week', ascending=False).iloc[0]
                team.append({'Position': slot, 'Player': name, 'Team Name': latest['Team Name'],
                             'FPTS': player_row['FPTS'].item() if hasattr(player_row['FPTS'], 'item') else player_row['FPTS']})
                used.add(name)
        return team

    used = set()
    return [select(used), select(used), select(used)]


def season_awards(weekly, activity, year):
    year_df = weekly[weekly['Year'] == year]
    mvp = year_df.groupby('Player Name')['FPTS'].sum().reset_index().sort_values('FPTS', ascending=False).iloc[0]
    teams = all_nba_teams(year_df)

    activity_year = activity[activity['Year'] == year]
    unique = activity_year.groupby('Asset')['Team ID'].nunique().reset_index()
    unique.columns = ['Player Name', 'Unique Teams']
    most_unique = unique[unique['Unique Teams'] == unique['Unique Teams'].max()]

    waiver = activity_year[activity_year['Action'] == 'WAIVER ADDED'].copy()
    waiver.rename(columns={'Asset': 'Player Name'}, inplace=True)
    waiver = waiver.drop_duplicates(subset=['Player Name', 'Team Name'])
    totals = year_df.groupby(['Player Name', 'Team Name'])['FPTS'].sum().reset_index()
    best = waiver.merge(totals, on=['Player Name', 'Team Name'], how='left').sort_values('FPTS', ascending=False).reset_index().iloc[0]

    return {
        'title': f'{year} Awards',
        'mvp': {'label': '🏆 MVP', 'value': f"{mvp['Player Name']} with {mvp['FPTS']} fantasy points"},
        'allNba': [{'label': f"All-NBA {label} Team", 'players': team}
                   for label, team in zip(('1st', '2nd', '3rd'), teams)],
        'bestWaiverAdd': {'label': 'Best Waiver Add',
                          'value': f"{best['Player Name']} on {best['Team Name']} scored {best['FPTS']} points"},
        'mostUniqueTeams': {
            'label': 'League Slut (Most Unique Teams in a Season)',
            'players': frame_records(most_unique, ['Player Name', 'Unique Teams']),
        },
    }


def build(source, output):
    from build_homepage import logo_config, write_json
    league, weekly, daily, activity = [pd.read_csv(source / name) for name in
        ('basketballBrawlLeagueData.csv', 'playerMatchupData.csv', 'playerDailyData.csv', 'activityData.csv')]
    years = sorted((int(year) for year in weekly['Year'].unique()), reverse=True)
    payload = {'schemaVersion': 1, 'defaultYear': years[0], 'years': years,
               'allTime': all_time(league, weekly, daily, activity, logo_config()['team_logo_paths']),
               'seasons': {str(year): season_awards(weekly, activity, year) for year in years}}
    write_json(output / 'record-book.json', payload)
    print(f'Record Book: all-time plus {len(years)} season award sets')
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'frontend/public/data')
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
