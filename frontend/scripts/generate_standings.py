"""Export the Dash standings snapshot using only local CSVs and the stdlib."""
import ast
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'frontend/public'


def all_play(rows, teams, completed_weeks):
    """Official full-field regular weeks only; ties contribute half a win."""
    ids = set(teams)
    grouped = defaultdict(list)
    for row in rows:
        grouped[int(row['Week'])].append(row)
    totals = {tid: dict(teams[tid], wins=0, losses=0, ties=0, points=0.0) for tid in ids}
    included = []
    for week in sorted(set(completed_weeks)):
        field = grouped[week]
        if len(field) != len(ids) or {int(r['Team ID']) for r in field} != ids or any(r['Type'] != 'Regular' for r in field):
            continue
        try:
            scores = {int(r['Team ID']): float(r['Points For']) for r in field}
            if not all(math.isfinite(v) for v in scores.values()):
                continue
        except (ValueError, TypeError, KeyError):
            continue
        included.append(week)
        for tid, score in scores.items():
            team = totals[tid]
            team['points'] += score
            for other, value in scores.items():
                if other != tid:
                    team['wins' if score > value else 'losses' if score < value else 'ties'] += 1
    for team in totals.values():
        games = team['wins'] + team['losses'] + team['ties']
        team['winPct'] = (team['wins'] + team['ties'] / 2) / games if games else None
        team['record'] = f"{team['wins']}–{team['losses']}–{team['ties']}"
    ordered = sorted(totals.values(), key=lambda t: (-(t['winPct'] or 0), -t['wins'], -t['points'], t['teamId']))
    return {'weeks': included, 'teams': [dict(t, rank=i+1) for i, t in enumerate(ordered)] if included else []}


def build_standings(rows, season=2026):
    rows = [row for row in rows if int(row['Year']) == season]
    regular = [row for row in rows if row['Type'] == 'Regular']
    if not regular:
        raise ValueError(f'No regular-season data for {season}')
    rank_week = max(int(row['Week']) for row in rows)
    stats_week = max(int(row['Week']) for row in regular)
    latest = [row for row in rows if int(row['Week']) == rank_week]
    stats = [row for row in regular if int(row['Week']) == stats_week]
    ranks = {int(row['Team ID']): int(row['Rank']) for row in latest}
    ids = [int(row['Team ID']) for row in stats]
    if len(set(ids)) != len(ids) or len(ranks) != len(latest) or set(ids) != set(ranks):
        raise ValueError('Duplicate teams or incomplete latest snapshot')
    if sorted(ranks.values()) != list(range(1, len(ids) + 1)):
        raise ValueError('Ranks must be a complete standings order')
    teams = []
    for row in stats:
        wins, losses = int(row['Cumulative Wins']), int(row['Cumulative Losses'])
        pf, pa = float(row['Cumulative Points For']), float(row['Cumulative Points Against'])
        teams.append(dict(rank=ranks[int(row['Team ID'])], teamId=int(row['Team ID']),
                          teamName=row['Team Name'], abbreviation=row['Team Abbreviation'],
                          wins=wins, losses=losses, record=f'{wins}–{losses}',
                          pointsFor=pf, pointsAgainst=pa,
                          pointsForDisplay=f'{pf:,.0f}', pointsAgainstDisplay=f'{pa:,.0f}'))
    return dict(schemaVersion=1, season=season, currentWeek=rank_week, statsThroughWeek=stats_week,
                ranksThroughWeek=rank_week, teamCount=len(teams),
                statsScope='Regular season', source='basketballBrawlLeagueData.csv',
                teams=sorted(teams, key=lambda team: team['rank']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'data/basketballBrawlLeagueData.csv',
                        help='League CSV to read; CI supplies a read-only checkout of current production data.')
    args = parser.parse_args()
    with args.source.open(newline='') as source:
        payload = build_standings(list(csv.DictReader(source)))
    # Read only literal logo configuration; never import Dash or load its datasets.
    config = {}
    for node in ast.parse((ROOT / 'dataStore.py').read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('team_logo_paths', 'default_logo_path'):
                    config[target.id] = ast.literal_eval(node.value)
    (PUBLIC / 'logos').mkdir(parents=True, exist_ok=True)
    for team in payload['teams']:
        relative = config['team_logo_paths'].get(team['teamName'], config['default_logo_path'])
        logo = (ROOT / relative).resolve()
        if not logo.is_relative_to((ROOT / 'assets/logos').resolve()) or not logo.is_file():
            raise ValueError(f'Invalid local logo for team {team["teamId"]}')
        shutil.copyfile(logo, PUBLIC / 'logos' / logo.name)
        team['logo'] = f'logos/{logo.name}'
    (PUBLIC / 'data').mkdir(parents=True, exist_ok=True)
    (PUBLIC / 'data/standings.json').write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    print(f'Generated {payload["season"]}: {payload["teamCount"]} teams, standings Week {payload["currentWeek"]}, regular-season stats through Week {payload["statsThroughWeek"]}')


if __name__ == '__main__':
    main()
