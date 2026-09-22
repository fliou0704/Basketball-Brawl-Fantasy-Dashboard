"""Offline historical and same-week theoretical H2H export."""
import argparse
from itertools import combinations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_COLUMNS = ['Year', 'Week', 'Type', 'Score']
THEORETICAL_COLUMNS = ['Year', 'Week', 'Score']


def selector_teams(league, config):
    # This is the live options callback order, not the layout's initial ordering.
    latest = league.sort_values('Year').drop_duplicates('Team ID', keep='last')
    from build_homepage import team_info
    return [team_info(r, config) for _, r in latest.iterrows()]


def current_names(league):
    latest = league[league['Year'] == league['Year'].max()]
    latest = latest[latest['Week'] == latest['Week'].max()]
    return {int(r['Team ID']): r['Team Name'] for _, r in latest.iterrows()}


def matchup_details(players, year, week, team_ids, team_names):
    sides = []
    for team_id in team_ids:
        group = players[(players['Year'] == year) & (players['Week'] == week) & (players['Team ID'] == team_id)]
        group = group.sort_values('FPTS', ascending=False).reset_index(drop=True)
        sides.append([{'playerId': int(r['Player ID']), 'name': r['Player Name'], 'fpts': None if pd.isna(r['FPTS']) else round(float(r['FPTS']), 2)}
                      for _, r in group.iterrows()])
    return {'year': int(year), 'week': int(week), 'teamIds': list(map(int, team_ids)),
            'teams': list(team_names), 'players': sides}


def perspective(league, players, first, second):
    names = current_names(league)
    rows = league[(league['Team ID'] == first) & (league['Opponent Team ID'] == second)]
    result = {'team1Id': first, 'team2Id': second, 'title': f'{names[first]} vs. {names[second]}',
              'records': [], 'history': [], 'message': None}
    if rows.empty:
        result['message'] = 'These teams have never played before.'
        return result
    for label, subset in [('Overall Record', rows), ('Regular Season', rows[rows['Type']=='Regular']), ('Playoffs', rows[rows['Type']=='Playoffs'])]:
        wins = subset['Win'].sum()
        result['records'].append({'label': label, 'value': f'{int(wins)} - {int(len(subset)-wins)}'})
    history = rows[rows['Type'] != 'Consolation'].copy()
    history['Score'] = history['Points For'].astype(int).astype(str) + ' - ' + history['Points Against'].astype(int).astype(str)
    history = history[HISTORICAL_COLUMNS + ['Team Name', 'Opponent Team Name', 'Win', 'Loss']].sort_values(['Year','Week'], ascending=[False,False])
    for row in history.to_dict('records'):
        winner = first if row['Win'] == 1 else second if row['Loss'] == 1 else None
        result['history'].append({'id': f"historical-{int(row['Year'])}-{int(row['Week'])}",
                                  'fields': {key: row[key] if pd.notna(row[key]) else None for key in HISTORICAL_COLUMNS},
                                  'winnerTeamId': winner, 'playoff': row['Type']=='Playoffs',
                                  'details': matchup_details(players, row['Year'], row['Week'], (first, second),
                                                             (row['Team Name'], row['Opponent Team Name']))})
    return result


def theoretical(league, players, first, second):
    names = current_names(league)
    eligible = league[league['Type'] == 'Regular']
    left = eligible[eligible['Team ID'] == first][['Year', 'Week', 'Type', 'Team Name', 'Team Owner', 'Points For']]
    right = eligible[eligible['Team ID'] == second][['Year', 'Week', 'Type', 'Team Name', 'Team Owner', 'Points For']]
    rows = left.merge(right, on=['Year', 'Week'], suffixes=(' A', ' B')).sort_values(['Year', 'Week'], ascending=False)
    result = {'team1Id': first, 'team2Id': second, 'title': f'{names[first]} vs. {names[second]}',
              'seasons': [], 'records': {}, 'history': [], 'message': None}
    if rows.empty:
        result['message'] = 'These teams do not have any comparable weeks.'
        return result
    result['seasons'] = sorted(map(int, rows['Year'].unique()), reverse=True)
    for key, subset in [('Summary', rows)] + [(str(year), rows[rows['Year'] == year]) for year in result['seasons']]:
        wins = int((subset['Points For A'] > subset['Points For B']).sum())
        losses = int((subset['Points For A'] < subset['Points For B']).sum())
        ties = int(len(subset) - wins - losses)
        result['records'][key] = {'wins': wins, 'losses': losses, 'ties': ties, 'weeks': int(len(subset)),
                                  'value': f'{wins} - {losses}' + (f' - {ties}' if ties else '')}
    for row in rows.to_dict('records'):
        a, b = float(row['Points For A']), float(row['Points For B'])
        winner = first if a > b else second if b > a else None
        fields = {'Year': int(row['Year']), 'Week': int(row['Week']), 'Score': f'{int(a)} - {int(b)}'}
        result['history'].append({'id': f"theoretical-{int(row['Year'])}-{int(row['Week'])}", 'fields': fields,
                                  'winnerTeamId': winner, 'playoff': False,
                                  'details': matchup_details(players, row['Year'], row['Week'], (first, second),
                                                             (row['Team Name A'], row['Team Name B']))})
    return result


def build(source, output):
    from build_homepage import logo_config, write_json
    league = pd.read_csv(source / 'basketballBrawlLeagueData.csv')
    players = pd.read_csv(source / 'playerMatchupData.csv')
    teams = selector_teams(league, logo_config())
    pairs = {}
    for first, second in combinations(sorted(t['teamId'] for t in teams), 2):
        key = f'{first}-{second}'
        write_json(output / 'historical-h2h' / f'{key}.json', {'schemaVersion': 1,
                   'historical': {str(first): perspective(league, players, first, second),
                                  str(second): perspective(league, players, second, first)},
                   'theoretical': {str(first): theoretical(league, players, first, second),
                                   str(second): theoretical(league, players, second, first)}})
        pairs[f'{first}-{second}'] = key
        pairs[f'{second}-{first}'] = key
    write_json(output / 'historical-h2h.json', {'schemaVersion': 1, 'teams': teams,
               'historicalColumns': HISTORICAL_COLUMNS, 'theoreticalColumns': THEORETICAL_COLUMNS, 'pairs': pairs})
    print(f'Historical H2H: {len(teams)} franchises, {len(pairs)//2} unique pairs, both perspectives')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'frontend/public/data')
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
