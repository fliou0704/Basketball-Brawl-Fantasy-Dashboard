import csv
import unittest
from generate_standings import ROOT, build_standings


class StandingsTests(unittest.TestCase):
    def setUp(self):
        with (ROOT / 'data/basketballBrawlLeagueData.csv').open(newline='') as source:
            self.rows = list(csv.DictReader(source))

    def test_real_snapshot_matches_weekly_totals(self):
        snapshot = build_standings(self.rows)
        for team in snapshot['teams']:
            weeks = [r for r in self.rows if r['Year'] == '2026' and r['Type'] == 'Regular'
                     and int(r['Team ID']) == team['teamId']]
            for output, column in [('wins', 'Win'), ('losses', 'Loss'),
                                   ('pointsFor', 'Points For'), ('pointsAgainst', 'Points Against')]:
                self.assertEqual(team[output], sum(float(r[column]) for r in weeks))
        self.assertEqual(snapshot['teamCount'], 10)

    def test_playoff_ranks_keep_regular_season_totals(self):
        regular = [r for r in self.rows if r['Year'] == '2026' and r['Week'] == '16']
        playoff = [dict(r, Week='17', Type='Playoff', Rank=str(11-int(r['Rank'])),
                        **{'Cumulative Wins': '99'}) for r in regular]
        result = build_standings(self.rows + playoff)
        self.assertEqual(result['ranksThroughWeek'], 17)
        self.assertEqual(result['statsThroughWeek'], 16)
        self.assertTrue(all(t['wins'] < 99 for t in result['teams']))
        self.assertEqual(result['teams'][0]['teamName'], 'I Watch Basketbal')

    def test_duplicate_or_missing_season_rejected(self):
        with self.assertRaises(ValueError):
            build_standings(self.rows, season=2000)
        row = next(r for r in self.rows if r['Year'] == '2026' and r['Week'] == '16')
        with self.assertRaises(ValueError):
            build_standings(self.rows + [row])


if __name__ == '__main__':
    unittest.main()
