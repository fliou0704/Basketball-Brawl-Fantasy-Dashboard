"""Small per-week matchup payloads, built solely from canonical exports.

Unknown days remain null. Historical membership is keyed by team/player/day,
independent of current roster membership. No scoring formula is recalculated.
"""
from collections import defaultdict
from datetime import date, timedelta
import hashlib
import json
from build_homepage import number, raw_stats, write_json


def stable_key(teams):
    return '-'.join(str(t['teamId']) for t in sorted(teams, key=lambda t: t['teamId']))


from fantasyOpportunities import potential_starts, remaining as calculate_remaining


def remaining_opportunities(current, calendar, week, team_id):
    if week['state']=='final':
        return {'games':0,'potentialStarts':0,'days':[],'players':[],'reason':'Matchup complete.'}
    return calculate_remaining(current, calendar, week, team_id, current.get('nbaSchedule'))


def matchup_detail(match, week, calendar, current, mapping, rows):
    ids = [t['teamId'] for t in match['teams']]
    periods = sorted(p for p, w in mapping.items() if w == week['week'] and (calendar['season'] != current['season'] or p <= current['scoringPeriod'])) if week['state'] != 'future' else []
    source_match = next((m for m in calendar['matchups'] if str(m['id']) == str(match['id'])), {})
    explicit = {s['teamId']: s['pointsByPeriod'] for s in source_match.get('sides', [])}
    groups = defaultdict(list)
    seen = set()
    for r in rows:
        key = (int(r['Scoring Period']), int(r['Team ID']), int(r['Player ID']))
        if key in seen:
            raise ValueError('Duplicate canonical daily player key')
        seen.add(key)
        if key[0] in periods and key[1] in ids and r['Player Slot'] in calendar['lineupSlots']:
            groups[(key[0], key[1])].append(r)
    days, players, totals, valid = [], {}, [0.0] * len(ids), [True] * len(ids)
    starts = [0] * len(ids)
    daily_consistent = True
    for period in periods:
        points, contributors = [], []
        for i, team in enumerate(ids):
            records = groups[(period, team)]
            value = sum(number(r['FPTS']) for r in records) if records else explicit.get(team, {}).get(str(period))
            reference = explicit.get(team, {}).get(str(period))
            if reference is not None and value is not None and abs(reference-value) >= .01:
                daily_consistent = False
            points.append(value)
            valid[i] = valid[i] and value is not None
            totals[i] += value or 0
            for r in records:
                played = number(r['MIN']) > 0
                starts[i] += int(played)
                if not played and not number(r['FPTS']):
                    continue
                pid = int(r['Player ID'])
                player = players.setdefault((team, pid), {'teamId': team, 'playerId': pid, 'name': r['Player Name'], 'points': 0, 'starts': 0, 'daily': []})
                player['points'] += number(r['FPTS'])
                player['starts'] += int(played)
                game = {'period': period, 'points': number(r['FPTS']), 'stats': raw_stats(r, calendar['scoringWeights']), 'played': played}
                player['daily'].append(game)
                if played or number(r['FPTS']):
                    contributors.append(dict(game, teamId=team, playerId=pid, name=r['Player Name']))
        days.append({'period': period, 'date': calendar.get('scheduledDates', {}).get(period) or (date.fromisoformat(calendar['dateAnchor']) + timedelta(days=period)).isoformat(),
                     'partial': week['state'] == 'current' and period == current['scoringPeriod'], 'points': points, 'cumulative': [round(totals[i], 4) if valid[i] else None for i in range(len(ids))], 'contributors': contributors})
    scores = match['actualScores']
    reconciled = bool(days and daily_consistent and periods == list(range(periods[0], periods[-1]+1)) and scores is not None and all(valid) and all(abs(a-b) < .01 for a,b in zip(totals,scores)))
    insight = None
    # Today's live snapshot is not a scoring-period-end lead observation.
    completed_days = [d for d in days if not (week['state'] == 'current' and calendar['season'] == current['season'] and d['period'] == current['scoringPeriod'])]
    if reconciled and len(ids) == 2 and completed_days:
        previous, changes, deficits, comebacks = 0, 0, [0, 0], [0, 0]
        for d in completed_days:
            diff = d['cumulative'][0] - d['cumulative'][1]
            sign = (diff > 0) - (diff < 0)
            if sign:
                changes += int(previous != 0 and previous != sign)
                previous = sign
            for i, margin in enumerate((diff, -diff)):
                if margin >= 0:
                    comebacks[i] = max(comebacks[i], deficits[i])
                deficits[i] = max(deficits[i], -margin)
        net = max(completed_days, key=lambda d: abs(d['points'][0]-d['points'][1]))
        best_day = max(((d['points'][i], i, d['period']) for d in completed_days for i in range(2)), default=None)
        performances = [p for d in completed_days for p in d['contributors']]
        insight = {'leadChanges': changes, 'comebacks': comebacks, 'largestDailyAdvantage': {'period': net['period'], 'margin': abs(net['points'][0]-net['points'][1]), 'teamId': ids[0 if net['points'][0] >= net['points'][1] else 1]},
                   'highestDay': {'points': best_day[0], 'teamId': ids[best_day[1]], 'period': best_day[2]},
                   'bestPerformance': max(performances, key=lambda p: p['points'], default=None)}
    for p in players.values():
        roster = next((t['roster'] for t in current['teams'] if t['teamId'] == p['teamId']), [])
        p['currentRoster'] = any(r['playerId'] == p['playerId'] for r in roster) if calendar['season'] == current['season'] and week['state'] == 'current' else None
        p['perStart'] = p['points']/p['starts'] if p['starts'] else None
    return {'key': stable_key(match['teams']), 'days': days, 'players': sorted(players.values(), key=lambda p: -p['points']),
            'completedStarts': starts, 'reconciled': reconciled, 'insights': insight,
            'coverage': 'Daily totals reconcile to the scoreboard snapshot.' if reconciled else 'Daily history is incomplete or differs from the scoreboard snapshot. Cumulative totals may be partial; insights are withheld.',
            'remaining': [remaining_opportunities(current, calendar, week, t) for t in ids]}


def build_details(payload, calendars, current, mapping, daily, output):
    by_season = defaultdict(list)
    for row in daily:
        by_season[int(row['Year'])].append(row)
    for season in payload['seasons']:
        year = season['season']
        calendar = next(c for c in calendars if int(c['season']) == year)
        period_map = {int(r['Scoring Period']): int(r['Week']) for r in mapping if int(r['Year']) == year}
        by_week = defaultdict(list)
        for row in by_season[year]:
            by_week[period_map.get(int(row['Scoring Period']))].append(row)
        for week in season['weeks']:
            path = f"matchups/{year}/{week['week']}.json"
            week['detailPath'] = path
            matches = [matchup_detail(m, week, calendar, current, period_map, by_week[week['week']]) for m in week['matchups']]
            result = {'schemaVersion': 1, 'season': year, 'week': week['week'], 'updatedAt': payload['updatedAt'], 'matchups': matches}
            if week['state']=='final':
                # Finished data has its own content identity. A new roster/NBA
                # checkpoint must not rewrite every historical detail artifact.
                result['updatedAt'] = None
                result['detailVersion'] = hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
                week['detailVersion'] = result['detailVersion']
            if year==current['season'] and week['state']!='final':
                result['opportunitiesPath'] = 'matchup-opportunities.json'
                for detail, match in zip(matches, week['matchups']):
                    detail['teamIds'] = [t['teamId'] for t in match['teams']]
            target = output / path
            if not target.exists() or json.loads(target.read_text())!=result:
                write_json(target, result)
