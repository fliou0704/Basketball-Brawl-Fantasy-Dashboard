import csv
import os
from pathlib import Path
import unittest
from generate_standings import ROOT, build_standings


def fixture(week, kind='Regular', reverse=False):
    """Two-team snapshot independent of the real dataset's current week."""
    return [dict(Year='2026', Week=str(week), Type=kind,
                 **{'Team ID': str(team), 'Team Name': f'Team {team}',
                    'Team Abbreviation': str(team), 'Rank': str(3-team if reverse else team),
                    'Cumulative Wins': str(week-team), 'Cumulative Losses': str(team),
                    'Cumulative Points For': str(week*100+team),
                    'Cumulative Points Against': str(week*90+team)}) for team in (1, 2)]


class StandingsTests(unittest.TestCase):
    def test_next_regular_week_advances_all_fields(self):
        rows = fixture(16) + fixture(17, reverse=True)
        result = build_standings(list(reversed(rows)))
        self.assertEqual(result['currentWeek'], 17)
        self.assertEqual(result['statsThroughWeek'], 17)
        self.assertEqual(result['teams'][0]['teamId'], 2)
        self.assertEqual(result['teams'][0]['pointsFor'], 1702)

    def test_playoffs_byes_and_consolation_advance_ranks_only(self):
        for kind in ('Playoffs', 'Bye', 'Consolation'):
            with self.subTest(kind=kind):
                rows = fixture(20) + fixture(21, kind) + fixture(23, kind, reverse=True)
                result = build_standings(rows)
                self.assertEqual(result['currentWeek'], 23)
                self.assertEqual(result['ranksThroughWeek'], 23)
                self.assertEqual(result['statsThroughWeek'], 20)
                self.assertEqual(result['teams'][0]['teamId'], 2)
                self.assertEqual(result['teams'][0]['wins'], 18)
                self.assertEqual(result['teams'][0]['pointsFor'], 2002)

    def test_other_season_does_not_advance_current_week(self):
        result = build_standings(fixture(18) + [dict(r, Year='2025') for r in fixture(24)])
        self.assertEqual(result['currentWeek'], 18)

    def test_duplicate_missing_team_or_missing_season_rejected(self):
        rows = fixture(20)
        for bad_rows in ([], rows + [rows[0]], rows + fixture(21, 'Playoffs')[:1]):
            with self.subTest(rows=bad_rows), self.assertRaises(ValueError):
                build_standings(bad_rows)

    def test_current_source_matches_dash_selection_and_weekly_totals(self):
        source = Path(os.environ.get('STANDINGS_TEST_SOURCE', ROOT / 'data/basketballBrawlLeagueData.csv'))
        with source.open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        season = [r for r in rows if int(r['Year']) == 2026]
        latest_week = max(int(r['Week']) for r in season)
        regular = [r for r in season if r['Type'] == 'Regular']
        stats_week = max(int(r['Week']) for r in regular)
        ranks = {r['Team Name']: int(r['Rank']) for r in season if int(r['Week']) == latest_week}
        stats = {r['Team Name']: r for r in regular if int(r['Week']) == stats_week}
        snapshot = build_standings(rows)
        self.assertEqual(snapshot['currentWeek'], latest_week)
        self.assertEqual(snapshot['statsThroughWeek'], stats_week)
        self.assertEqual(snapshot['teamCount'], len(stats))
        for team in snapshot['teams']:
            # Independent equivalent of Dash's latest-name/rank merge.
            self.assertEqual(team['rank'], ranks[team['teamName']])
            for output, cumulative, weekly in [
                ('wins', 'Cumulative Wins', 'Win'), ('losses', 'Cumulative Losses', 'Loss'),
                ('pointsFor', 'Cumulative Points For', 'Points For'),
                ('pointsAgainst', 'Cumulative Points Against', 'Points Against')
            ]:
                self.assertEqual(team[output], float(stats[team['teamName']][cumulative]))
                self.assertEqual(team[output], sum(float(r[weekly]) for r in regular
                                                 if int(r['Team ID']) == team['teamId']))


if __name__ == '__main__':
    unittest.main()
