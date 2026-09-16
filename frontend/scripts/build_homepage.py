"""Offline orchestration for the Basketball Brawl homepage and date previews."""
import argparse
import ast
from collections import defaultdict
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import shutil

from generate_standings import build_standings
from homepage_state import select_state, normalize_calendar

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'frontend/public'
VERSION = 1


def number(value):
    return float(value or 0)


def display(value):
    return f'{value:,.0f}' if value == int(value) else f'{value:,.1f}'


def read_csv(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')


def logo_config():
    result = {}
    for node in ast.parse((ROOT / 'dataStore.py').read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('team_logo_paths', 'default_logo_path', 'team_colors'):
                    result[target.id] = ast.literal_eval(node.value)
    return result


def team_info(row, config):
    return {'teamId': int(row['Team ID']), 'teamName': row['Team Name'],
            'logo': 'logos/' + Path(config['team_logo_paths'].get(row['Team Name'], config['default_logo_path'])).name,
            'color': config['team_colors'].get(int(row['Team ID']), '#52654c')}


def raw_stats(row, weights):
    # Legacy CSV fields are appliedStats (scoring contributions), not box-score counts.
    result = {}
    for field in ('PTS', 'REB', 'AST', 'FGM', 'FGA', '3PM', '3PA', 'BLK', 'STL', 'TO'):
        weight = weights.get(field)
        value = row.get(field)
        result[field] = round(number(value) / weight) if value not in (None, '') and weight else None
    return result


def player_info(row, teams, weights=None):
    result = {'playerId': int(row['Player ID']), 'name': row['Player Name'],
              'team': teams[int(row['Team ID'])], 'points': number(row['FPTS']),
              'pointsDisplay': display(number(row['FPTS']))}
    if weights:
        result['stats'] = raw_stats(row, weights)
        result['bench'] = row.get('Player Slot') in ('BE', 'IR')
    return result


def choose_lineup(rows, slots, teams):
    """Maximum-total assignment by slot-mask DP; each player can appear only once.

    Eligibility uses the three position fields already saved in the weekly CSV.
    Duplicate player/team rows from trades use highest recorded weekly performance.
    """
    eligible = {'G': {'PG', 'SG'}, 'F': {'SF', 'PF'}, 'UT': {'PG', 'SG', 'SF', 'PF', 'C'}}
    dedup = {}
    for row in sorted(rows, key=lambda r: (-number(r['FPTS']), int(r['Player ID']), int(r['Team ID']))):
        dedup.setdefault(int(row['Player ID']), row)
    # At most N candidates per eligibility class can be needed for N slots.
    candidates_by_id = {}
    for slot in set(slots):
        eligible_positions = eligible.get(slot, {slot})
        options = [r for r in dedup.values() if {r.get(k) for k in ('Position','Position2','Position3')} & eligible_positions]
        for row in options[:len(slots)]: candidates_by_id[int(row['Player ID'])] = row
    candidates = sorted(candidates_by_id.values(), key=lambda r: (-number(r['FPTS']), int(r['Player ID'])))
    dp = {0: (0.0, [])}
    for row in candidates:
        positions = {row.get(field) for field in ('Position', 'Position2', 'Position3')}
        allowed = [i for i, slot in enumerate(slots) if positions & eligible.get(slot, {slot})]
        # Copy prevents reusing this player for multiple slots.
        for mask, (total, picks) in list(dp.items()):
            for i in allowed:
                if mask & (1 << i):
                    continue
                new_mask = mask | (1 << i)
                score = total + number(row['FPTS'])
                if new_mask not in dp or score > dp[new_mask][0]:
                    dp[new_mask] = (score, picks + [(i, row)])
    best_mask = max(dp, key=lambda mask: (bin(mask).count('1'), dp[mask][0]))
    picks = sorted(dp[best_mask][1])
    mvp = max((row for _, row in picks), key=lambda r: (number(r['FPTS']), -int(r['Player ID'])), default=None)
    return [dict(player_info(row, teams), slot=slots[i], mvp=row is mvp) for i, row in picks]


def matchup_rows(rows, teams, championship_only=False):
    seen, matches = set(), []
    for row in rows:
        if championship_only and row['Type'] != 'Playoffs':
            continue
        if not row['Opponent Team ID']:
            continue
        a, b = int(row['Team ID']), int(float(row['Opponent Team ID']))
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        scores = [number(row['Points For']), number(row['Points Against'])]
        winner = a if scores[0] > scores[1] else b if scores[1] > scores[0] else None
        matches.append({'teams': [teams[a], teams[b]], 'scores': scores,
                        'scoreDisplay': list(map(display, scores)), 'winnerId': winner,
                        'margin': abs(scores[0] - scores[1]), 'marginDisplay': display(abs(scores[0] - scores[1]))})
    return matches


def bracket_view(league, calendar, teams, active_week=None):
    rounds = []
    playoff_weeks = [w for w in calendar['weeks'] if w['week'] > calendar['regularWeeks']]
    for i, week in enumerate(playoff_weeks):
        state = 'completed' if active_week is None or week['week'] < active_week else 'active' if week['week'] == active_week else 'upcoming'
        title = 'Championship' if i == len(playoff_weeks)-1 else 'Semifinals' if i == len(playoff_weeks)-2 else 'First round'
        # Future opponent assignments are not disclosed before the preceding round ends.
        if state == 'upcoming':
            rounds.append({'week': week['week'], 'title': title, 'status': state, 'matches': [], 'byes': []})
            continue
        rows = [r for r in league if int(r['Week']) == week['week']]
        matches = matchup_rows(rows, teams, True)
        if state != 'completed':
            matches = [dict(m, scores=None, scoreDisplay=None, winnerId=None, margin=None, marginDisplay=None) for m in matches]
        rounds.append({'week': week['week'], 'title': title, 'status': state, 'matches': matches,
                       'byes': [teams[int(r['Team ID'])] for r in rows if r['Type'] == 'Bye']})
    champion = None
    if active_week is None and rounds and rounds[-1]['matches']:
        champion_id = rounds[-1]['matches'][0]['winnerId']
        champion = teams.get(champion_id)
    return {'rounds': rounds, 'champion': champion}


def build_season(year, league, daily, weekly, calendar, config, output):
    teams = {int(r['Team ID']): team_info(r, config) for r in league}
    by_week, by_day, players_by_week = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in league: by_week[int(row['Week'])].append(row)
    for row in daily: by_day[row['Date']].append(row)
    for row in weekly: players_by_week[int(row['Week'])].append(row)
    end = (date.fromisoformat(calendar['dateAnchor']) + timedelta(days=calendar['finalPeriod'])).isoformat()
    weeks = normalize_calendar(calendar['weeks'], end)
    calendar = dict(calendar, weeks=weeks)
    if not weeks or max(by_week) > max(w['week'] for w in weeks):
        raise ValueError(f'{year} needs refreshed ESPN season metadata')
    # Complete seasons require the terminal day and the terminal league week.
    end = (date.fromisoformat(calendar['dateAnchor']) + timedelta(days=calendar['finalPeriod'])).isoformat()
    complete = max(by_day) >= end and max(by_week) >= weeks[-1]['week']
    available_end = min(max(by_day), end)
    completed_weeks = [w['week'] for w in weeks if w['end'] <= available_end and w['week'] in by_week]
    descriptor = {'season': year, 'start': weeks[0]['start'], 'end': end, 'complete': complete,
                  'regularWeeks': calendar['regularWeeks'], 'weeks': weeks,
                  'completedDays': sorted(d for d in by_day if d <= available_end), 'completedWeeks': completed_weeks}
    standings = {}
    for w in completed_weeks:
        if w <= calendar['regularWeeks']:
            # Stage 2 explicitly shows regular-season ranks with regular-season stats.
            snap = build_standings([r for r in league if int(r['Week']) <= w and r['Type'] == 'Regular'], year)
            for team in snap['teams']: team.update(teams[team['teamId']])
            standings[str(w)] = snap
    authoritative = defaultdict(dict)
    for match in calendar['matchups']:
        for side in match['sides']:
            for period, points in side['pointsByPeriod'].items():
                authoritative[int(period)][side['teamId']] = points
    daily_recaps = {}
    audit = {'comparedTeamDays': 0, 'activeRosterMismatches': 0, 'missing3PA': True}
    for day, rows in sorted(by_day.items()):
        period = int(rows[0]['Scoring Period'])
        week = next((w for w in weeks if w['firstPeriod'] <= period <= w['lastPeriod']), None)
        if not week: continue
        totals = authoritative.get(period, {})
        active_sums = defaultdict(float)
        for row in rows:
            if row['Player Slot'] in calendar['lineupSlots']: active_sums[int(row['Team ID'])] += number(row['FPTS'])
        for team, total in active_sums.items():
            if team in totals:
                audit['comparedTeamDays'] += 1
                audit['activeRosterMismatches'] += abs(total - totals[team]) > .01
        # Require all league teams to avoid crowning a winner from a partial slate.
        leaders = []
        if set(totals) == set(teams):
            highest = max(totals.values())
            leaders = [dict(teams[t], points=p, pointsDisplay=display(p)) for t, p in totals.items() if p == highest]
        unique_performances = {}
        for row in sorted(rows, key=lambda r: (-number(r['FPTS']), int(r['Player ID']), int(r['Team ID']))):
            unique_performances.setdefault(int(row['Player ID']), row)
        performances = list(unique_performances.values())[:5]
        scoreboard = []
        for match in calendar['matchups']:
            if match['week'] != week['week'] or len(match['sides']) != 2: continue
            sides = match['sides']
            scores = [sum(v for sp, v in side['pointsByPeriod'].items() if int(sp) <= period) for side in sides]
            scoreboard.append({'teams': [teams[side['teamId']] for side in sides], 'scoreDisplay': list(map(display, scores))})
        daily_recaps[day] = {'date': day, 'week': week['week'], 'leaders': leaders,
                             'players': [player_info(r, teams, calendar['scoringWeights']) for r in performances],
                             'scoreboard': scoreboard, 'scoreboardLabel': f'Week {week["week"]} · through {day}'}
    weekly_recaps = {}
    for w in completed_weeks:
        rows = by_week[w]
        championship = {int(r['Team ID']) for r in rows if r['Type'] == 'Playoffs'}
        pool = players_by_week[w]
        playoff = w > calendar['regularWeeks']
        if playoff: pool = [r for r in pool if int(r['Team ID']) in championship]
        matches = matchup_rows(rows, teams, playoff)
        best = max((number(r['Points For']) for r in rows if not playoff or int(r['Team ID']) in championship), default=0)
        leaders = [dict(teams[int(r['Team ID'])], pointsDisplay=display(best)) for r in rows
                   if number(r['Points For']) == best and (not playoff or int(r['Team ID']) in championship)]
        smallest = min((m['margin'] for m in matches), default=None)
        closest = [m for m in matches if m['margin'] == smallest]
        insights = []
        if not playoff:
            prior_ranks = {int(r['Team ID']): int(r['Rank']) for r in by_week.get(w-1, [])}
            movers = [(prior_ranks.get(int(r['Team ID']), int(r['Rank']))-int(r['Rank']), r) for r in rows]
            rise, riser = max(movers, key=lambda item: item[0])
            if rise > 0: insights.append({'title': 'Biggest riser', 'team': teams[int(riser['Team ID'])], 'value': f'Up {rise} places'})
            losing = [r for r in rows if number(r['Points For']) < number(r['Points Against'])]
            if losing:
                tough = max(losing,key=lambda r: number(r['Points For']))
                insights.append({'title': 'Toughest loss', 'team': teams[int(tough['Team ID'])], 'value': display(number(tough['Points For'])) + ' points'})
            streaks = []
            for tid in teams:
                streak = 0
                for prior in range(w,0,-1):
                    row = next((r for r in by_week[prior] if int(r['Team ID'])==tid), None)
                    if not row or int(row['Win']) != 1: break
                    streak += 1
                streaks.append((streak,tid))
            streak, tid = max(streaks)
            if streak >= 2: insights.append({'title': 'Longest win streak', 'team': teams[tid], 'value': f'{streak} straight wins'})
        weekly_recaps[str(w)] = {'week': w, 'end': next(x['end'] for x in weeks if x['week'] == w),
                                 'playoffs': playoff, 'leaders': leaders, 'closest': closest,
                                 'matches': matches, 'insights': insights, 'lineup': choose_lineup(pool, calendar['lineupSlots'], teams)}
    # Season player totals use weekly FPTS, avoiding daily-row double counting.
    # A transferred player's points are attributed to each owning team by week.
    player_totals = {}
    unique_week_players = {}
    for row in sorted(weekly, key=lambda r: (-number(r['FPTS']), int(r['Team ID']))):
        unique_week_players.setdefault((int(row['Week']), int(row['Player ID'])), row)
    for row in unique_week_players.values():
        if int(row['Week']) not in completed_weeks: continue
        pid = int(row['Player ID'])
        p = player_totals.setdefault(pid, {'playerId': pid, 'name': row['Player Name'], 'points': 0, 'teamIds': []})
        p['points'] += number(row['FPTS'])
        tid = int(row['Team ID'])
        if tid not in p['teamIds']: p['teamIds'].append(tid)
    leaders = [dict(p, rank=i+1, pointsDisplay=display(p['points']), teams=[teams[t] for t in p['teamIds']])
               for i, p in enumerate(sorted(player_totals.values(), key=lambda p: (-p['points'], p['playerId']))[:10])]
    playoffs = {str(w['week']): bracket_view(league, calendar, teams, w['week']) for w in weeks if w['week'] > calendar['regularWeeks']}
    if complete: playoffs['final'] = bracket_view(league, calendar, teams)
    regular_weeks = [w for w in completed_weeks if w <= calendar['regularWeeks']]
    # SVG geometry is precomputed in Python. React only paints supplied points.
    rank_series = []
    for tid, team in teams.items():
        points = []
        for w in regular_weeks:
            row = next(r for r in by_week[w] if int(r['Team ID']) == tid)
            points.append([round(25 + (w-1)*275/max(1,len(regular_weeks)-1),2), round(20+(int(row['Rank'])-1)*180/max(1,len(teams)-1),2)])
        rank_series.append(dict(team, path=' '.join(f'{x},{y}' for x,y in points)))
    high_weeks = []
    max_score = max((number(r['Points For']) for r in league if r['Type']=='Regular'), default=1)
    for w in regular_weeks:
        top = max(by_week[w], key=lambda r: number(r['Points For']))
        high_weeks.append(dict(teams[int(top['Team ID'])], week=w, pointsDisplay=display(number(top['Points For'])),
                               width=f'{number(top["Points For"])/max_score*100:.2f}%'))
    charts = {'ranks': rank_series, 'weeks': regular_weeks, 'highWeeks': high_weeks,
              'rankTicks': [{'rank': i, 'y': 20+(i-1)*180/max(1,len(teams)-1)} for i in range(1,len(teams)+1)]}
    for name, content in [('standings',standings), ('daily-recap',daily_recaps), ('weekly-recap',weekly_recaps),
                          ('playoffs',playoffs), ('season-leaders',leaders), ('history',charts)]:
        write_json(output / str(year) / f'{name}.json', {'schemaVersion': VERSION, 'season': year, 'data': content})
    return descriptor, audit


def build(source, output=PUBLIC / 'data', metadata=ROOT / 'frontend/source/season-metadata.json'):
    config = logo_config()
    league, daily, weekly = [read_csv(source / name) for name in ('basketballBrawlLeagueData.csv','playerDailyData.csv','playerMatchupData.csv')]
    calendars = json.loads(metadata.read_text())['seasons']
    years = sorted({int(r['Year']) for r in league})
    if not set(years).issubset({s['season'] for s in calendars}):
        raise ValueError('New season detected: refresh season metadata before building')
    descriptors, audits = [], {}
    for year in years:
        selected = [[r for r in rows if int(r['Year']) == year] for rows in (league,daily,weekly)]
        descriptor, audit = build_season(year, *selected, next(s for s in calendars if s['season']==year), config, output)
        descriptors.append(descriptor); audits[str(year)] = audit
    # A dated lookup keeps statistical/state logic out of React.
    states = {}
    for season in descriptors:
        start = date.fromisoformat(season['start'])
        end = date.fromisoformat(season['end'])
        day = start
        while day <= end:
            states[day.isoformat()] = select_state(day, descriptors)
            day += timedelta(days=1)
    completed = [{'after': s['end'], 'state': select_state(date.fromisoformat(s['end'])+timedelta(days=1),descriptors)}
                 for s in descriptors if s['complete']]
    write_json(output / 'homepage.json', {'schemaVersion': VERSION, 'timezone': 'America/New_York',
               'states': states, 'offseasons': completed, 'earliestDate': descriptors[0]['start'],
               'latestSeason': descriptors[-1]['season'], 'calendars': descriptors,
               'limitations': {'raw3PA': 'Not recorded in the source CSV.', 'scoreboard': 'Completed-day snapshots only; not live.'}})
    write_json(output / 'data-quality.json', {'schemaVersion': VERSION, 'seasons': audits})
    # Keep the Stage 1 data contract, now with consistent final regular-season ranks.
    latest = descriptors[-1]
    snap = json.loads((output / str(latest['season']) / 'standings.json').read_text())['data']
    write_json(output / 'standings.json', snap[str(max(map(int,snap)))])
    (PUBLIC / 'logos').mkdir(exist_ok=True)
    for relative in set(config['team_logo_paths'].values()) | {config['default_logo_path']}:
        logo = ROOT / relative
        shutil.copyfile(logo, PUBLIC / 'logos' / logo.name)
    print(f'Built {len(descriptors)} seasons, {len(states)} dated states; latest season {latest["season"]}')
    print('Daily score audit:', audits)
    return descriptors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--output-dir', type=Path, default=PUBLIC / 'data')
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
