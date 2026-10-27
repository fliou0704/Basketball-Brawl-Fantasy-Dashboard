import unittest
import pandas as pd
from generate_team_stats import ROOT
from teamPerformance import team_performance, combine_performance


class TeamPerformanceTests(unittest.TestCase):
    def calculate(self, missing=False):
        rows = []
        for year in (2025, 2026):
            for period, points in ((1, 20), (2, 40)):
                for player, slot, minutes, score in ((1, 'PG', 30, points), (2, 'BE', 30, 999), (3, 'PG', 0, 0)):
                    rows.append({'Year':year,'Scoring Period':period,'Team ID':7,'Player ID':player,
                                 'Player Slot':slot,'MIN':minutes,'FPTS':score})
        if missing:
            rows = rows[1:]
        mapping = pd.DataFrame([{'Year':year,'Scoring Period':period,'Week':period}
                                for year in (2025,2026) for period in (1,2)])
        league = pd.DataFrame([{'Year':year,'Week':week,'Team ID':7,'Points For':points}
                               for year in (2025,2026) for week,points in ((1,20),(2,40))])
        metadata = {'seasons':[{'season':year,'lineupSlots':['PG']} for year in (2025,2026)]}
        return team_performance(pd.DataFrame(rows), mapping, metadata, league)

    def test_bench_and_unplayed_games_excluded_week_season_and_franchise(self):
        result = self.calculate()
        self.assertEqual(result[(2025,7)]['weeks']['1']['fpPerStart'],20)
        self.assertEqual(result[(2025,7)]['season']['starts'],2)
        self.assertEqual(result[(2025,7)]['season']['fpPerStart'],30)
        career = combine_performance(item['season'] for item in result.values())
        self.assertEqual((career['fpts'],career['starts'],career['fpPerStart']),(120,4,30))

    def test_missing_history_invalidates_broader_denominators(self):
        result = self.calculate(missing=True)
        self.assertIsNone(result[(2025,7)]['season']['fpPerStart'])
        self.assertIsNone(combine_performance(item['season'] for item in result.values())['starts'])

    def test_zero_starts_safe_and_aggregate_before_divide(self):
        self.assertIsNone(combine_performance([])['fpPerStart'])
        self.assertEqual(combine_performance([{'available':True,'fpts':20,'starts':1},
                                              {'available':True,'fpts':90,'starts':3}])['fpPerStart'],27.5)
