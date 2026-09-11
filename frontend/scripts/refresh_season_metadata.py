"""Explicit live refresh of allowlisted ESPN calendar/settings/score data.

Uses the existing credential helper. Never saves the raw ESPN response.
The normal homepage build and tests are offline.
"""
import argparse
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def refresh(source, output):
    import requests
    from dataUpdateSafety import require_espn_credentials
    from espn_api.basketball.constant import STATS_MAP, POSITION_MAP
    swid, s2 = require_espn_credentials()
    with (source / 'playerDailyData.csv').open() as handle:
        daily = list(csv.DictReader(handle))
    seasons = []
    for year in sorted({int(row['Year']) for row in daily}):
        response = requests.get(
            f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{year}/segments/0/leagues/609694684',
            params={'view': ['mSettings', 'mMatchupScore']},
            cookies={'SWID': swid, 'espn_s2': s2}, timeout=45)
        if response.status_code != 200:
            raise RuntimeError(f'ESPN metadata unavailable for {year}: HTTP {response.status_code}')
        data = response.json()
        settings = data['settings']
        rows = [row for row in daily if int(row['Year']) == year]
        anchors = {date.fromisoformat(row['Date']) - timedelta(days=int(row['Scoring Period'])) for row in rows}
        if len(anchors) != 1:
            raise ValueError(f'Inconsistent scoring-period date anchors for {year}')
        anchor = anchors.pop()
        weeks, matchups = {}, []
        for match in data['schedule']:
            week = int(match['matchupPeriodId'])
            sides = []
            for side in ('home', 'away'):
                entry = match.get(side, {})
                if not entry.get('teamId'):
                    continue
                points = {str(int(k)): float(v) for k, v in entry.get('pointsByScoringPeriod', {}).items()}
                weeks.setdefault(week, set()).update(map(int, points))
                sides.append({'teamId': entry['teamId'], 'pointsByPeriod': points})
            matchups.append({'id': match['id'], 'week': week, 'sides': sides})
        calendar = []
        for week, periods in sorted(weeks.items()):
            if not periods:
                continue
            calendar.append({'week': week, 'firstPeriod': min(periods), 'lastPeriod': max(periods),
                             'start': (anchor + timedelta(days=min(periods))).isoformat(),
                             'end': (anchor + timedelta(days=max(periods))).isoformat()})
        slots = [POSITION_MAP[int(slot)] for slot, count in settings['rosterSettings']['lineupSlotCounts'].items()
                 if POSITION_MAP.get(int(slot)) not in ('BE', 'IR', '') for _ in range(count)]
        season = {'season': year, 'firstPeriod': data['status']['firstScoringPeriod'],
                  'finalPeriod': data['status']['finalScoringPeriod'],
                  'regularWeeks': settings['scheduleSettings']['matchupPeriodCount'],
                  'playoffTeamCount': settings['scheduleSettings']['playoffTeamCount'],
                  'dateAnchor': anchor.isoformat(), 'weeks': calendar, 'lineupSlots': slots,
                  'scoringWeights': {STATS_MAP.get(str(item['statId']), str(item['statId'])): item['points']
                                     for item in settings['scoringSettings']['scoringItems']},
                  'matchups': matchups}
        seasons.append(season)
        print(f'{year}: {len(calendar)} weeks; {len(matchups)} matchup records; {len(slots)} active roster slots')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'schemaVersion': 1, 'source': 'ESPN mSettings + mMatchupScore; CSV date anchors',
                                  'seasons': seasons}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'frontend/source/season-metadata.json')
    args = parser.parse_args()
    try:
        refresh(args.source_dir, args.output)
    except Exception as exc:
        # Exception strings from HTTP libraries can include request details.
        print(f'Metadata refresh failed ({type(exc).__name__}); no raw response saved.', file=sys.stderr)
        raise SystemExit(1)
