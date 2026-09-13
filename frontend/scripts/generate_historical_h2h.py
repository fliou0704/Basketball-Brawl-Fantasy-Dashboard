"""Offline Historical H2H export preserving the Dash callback's definitions."""
import argparse
from itertools import combinations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = ['Year', 'Week', 'Team Name', 'Type', 'Result', 'Score', 'Opponent Team Name', 'Opponent Owner']


def selector_teams(league):
    # This is the live options callback order, not the layout's initial ordering.
    latest = league.sort_values('Year').drop_duplicates('Team ID', keep='last')
    return [{'teamId': int(r['Team ID']), 'teamName': r['Team Name']} for _, r in latest.iterrows()]


def current_names(league):
    latest = league[league['Year'] == league['Year'].max()]
    latest = latest[latest['Week'] == latest['Week'].max()]
    return {int(r['Team ID']): r['Team Name'] for _, r in latest.iterrows()}


def matchup_details(players, row):
    sides = []
    for name in (row['Team Name'], row['Opponent Team Name']):
        group = players[(players['Year'] == row['Year']) & (players['Week'] == row['Week']) & (players['Team Name'] == name)]
        group = group[['Player Name', 'FPTS']].sort_values('FPTS', ascending=False).reset_index(drop=True)
        sides.append([{'name': r['Player Name'], 'fpts': f"{r['FPTS']:.2f}" if pd.notna(r['FPTS']) else ''} for _, r in group.iterrows()])
    size = max(map(len, sides))
    for side in sides:
        side.extend({'name': '', 'fpts': ''} for _ in range(size-len(side)))
    return {'year': int(row['Year']), 'week': int(row['Week']),
            'teams': [row['Team Name'], row['Opponent Team Name']], 'players': sides}


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
    history['Result'] = history['Win'].apply(lambda w: 'W' if w==1 else 'L')
    history['Score'] = history['Points For'].astype(int).astype(str) + ' - ' + history['Points Against'].astype(int).astype(str)
    history = history[COLUMNS].sort_values(['Year','Week'], ascending=[False,False])
    for row in history.to_dict('records'):
        result['history'].append({'fields': {key: value if pd.notna(value) else None for key,value in row.items()},
                                  'playoff': row['Type']=='Playoffs', 'details': matchup_details(players, row)})
    return result


def build(source, output):
    from build_homepage import write_json
    league = pd.read_csv(source / 'basketballBrawlLeagueData.csv')
    players = pd.read_csv(source / 'playerMatchupData.csv')
    teams = selector_teams(league)
    pairs = {}
    for first, second in combinations(sorted(t['teamId'] for t in teams), 2):
        key = f'{first}-{second}'
        write_json(output / 'historical-h2h' / f'{key}.json', {'schemaVersion': 1,
                   'perspectives': {str(first): perspective(league, players, first, second),
                                    str(second): perspective(league, players, second, first)}})
        pairs[f'{first}-{second}'] = key
        pairs[f'{second}-{first}'] = key
    write_json(output / 'historical-h2h.json', {'schemaVersion': 1, 'teams': teams, 'columns': COLUMNS, 'pairs': pairs})
    print(f'Historical H2H: {len(teams)} franchises, {len(pairs)//2} unique pairs, both perspectives')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'frontend/public/data')
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
