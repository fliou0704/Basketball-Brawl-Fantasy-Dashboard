"""Parity oracle executes the actual Dash callback with inert HTML components."""
import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
import warnings

import pandas as pd

from generate_team_stats import build, prepare_players, stat_values, season_roster, ROOT


class Element:
    def __init__(self, tag, children=None, **props):
        self.tag, self.children, self.props = tag, children, props

    def find(self, tag):
        result = [self] if self.tag == tag else []
        for child in self.children if isinstance(self.children, list) else [self.children]:
            if isinstance(child, Element):
                result.extend(child.find(tag))
        return result


class Html:
    def __getattr__(self, tag):
        return lambda children=None, **props: Element(tag, children, **props)


def dash_callback(league, weekly, daily, activity):
    tree = ast.parse((ROOT / 'basketballBrawlTeamStats.py').read_text())
    register = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'register_team_callbacks')
    callback = next(n for n in register.body if isinstance(n, ast.FunctionDef) and n.name == 'update_team_stats')
    callback.decorator_list = []
    # Execute the original module's exact scoring conversions on an isolated copy.
    conversions = [n for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Subscript)
                   and isinstance(n.targets[0].value, ast.Name) and n.targets[0].value.id == 'players']
    namespace = {'pd': pd, 'html': Html(), 'players': weekly.copy(), 'league_data': league.copy(),
                 'playerDaily': daily.copy(), 'activityData': activity.copy()}
    exec(compile(ast.Module(body=conversions + [callback], type_ignores=[]), '<Dash Team Stats parity oracle>', 'exec'), namespace)
    return namespace['update_team_stats']


class TeamStatsParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ.get('TEAM_STATS_TEST_SOURCE', ROOT / 'data'))
        cls.league, cls.weekly, cls.daily, cls.activity = [pd.read_csv(cls.source / name) for name in
            ('basketballBrawlLeagueData.csv', 'playerMatchupData.csv', 'playerDailyData.csv', 'activityData.csv')]
        cls.reference = staticmethod(dash_callback(cls.league, cls.weekly, cls.daily, cls.activity))
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        build(cls.source, cls.output)
        cls.manifest = json.loads((cls.output / 'team-stats.json').read_text())
        cls.payloads = {t['teamId']: json.loads((cls.output / 'team-stats' / f"{t['teamId']}.json").read_text()) for t in cls.manifest['teams']}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_team_and_season_selector_order_matches_dash(self):
        expected = self.league.sort_values('Year', ascending=False).drop_duplicates('Team ID')
        self.assertEqual([(t['teamId'], t['teamName']) for t in self.manifest['teams']],
                         list(expected[['Team ID', 'Team Name']].itertuples(index=False, name=None)))
        self.assertEqual(self.manifest['years'], sorted(self.weekly['Year'].unique(), reverse=True))

    def test_every_season_stat_value_and_rank_matches_dash(self):
        placements = ['first','second','third','fourth','fifth','sixth','seventh','eighth','ninth','tenth']
        self.assertIn(2026, self.manifest['years'])
        self.assertIn(2025, self.manifest['years'])
        for tid, payload in self.payloads.items():
            for year in self.manifest['years']:
                with self.subTest(team=tid, year=year), warnings.catch_warnings():
                    warnings.simplefilter('ignore', DeprecationWarning)
                    reference = self.reference(tid, year)
                    season = payload['seasons'][str(year)]
                    if season is None:
                        self.assertIn('No data', reference.children)
                        continue
                    rows = reference.find('Table')[0].find('Tr')
                    labels = [c.children for c in rows[0].find('Td')]
                    ranks = [placements.index(Path(c.children.props['src']).stem)+1 if isinstance(c.children, Element) else None for c in rows[1].find('Td')]
                    values = [c.children for c in rows[2].find('Td')]
                    self.assertEqual(season['rankings'], [{'label': l, 'rank': r, 'value': v} for l,r,v in zip(labels,ranks,values)])

    def test_every_season_roster_value_and_order_matches_dash(self):
        for tid, payload in self.payloads.items():
            for year in self.manifest['years']:
                with self.subTest(team=tid, year=year), warnings.catch_warnings():
                    warnings.simplefilter('ignore', DeprecationWarning)
                    season = payload['seasons'][str(year)]
                    if season is None:
                        continue
                    reference = self.reference(tid, year).find('Table')[1].find('Tbody')[0]
                    expected = [[c.children for c in row.find('Td')] for row in reference.find('Tr')]
                    actual = [[r[k] for k in ('name','fpts','ppm','action','date','contribution')] for r in season['roster']]
                    self.assertEqual(actual, expected)

    def test_all_time_records_roster_and_status_match_dash(self):
        for tid, payload in self.payloads.items():
            with self.subTest(team=tid):
                reference = self.reference(tid, 'Summary')
                actual = payload['summary']
                self.assertEqual([f"{r['label']}: {r['value']}" for r in actual['records']], [e.children.strip() for e in reference.find('P')])
                rows = reference.find('Tbody')[0].find('Tr')
                self.assertEqual([[r[k] for k in ('name','fpts','action','date')] for r in actual['roster']], [[c.children for c in row.find('Td')] for row in rows])
                self.assertEqual([r['inactive'] for r in actual['roster']], [r.props['style']['background-color']=='#f8d7da' for r in rows])

    def test_rank_ties_use_min_rank_and_missing_ppm_is_unranked(self):
        rows = []
        for tid, pts in [(1, 100),(2,100),(3,50)]:
            row = self.weekly.iloc[0].copy()
            row['Team ID'], row['Year'], row['PTS'] = tid, 2026, pts
            rows.append(row)
        weekly = prepare_players(pd.DataFrame(rows))
        daily = self.daily.iloc[:0].copy()
        stats = stat_values(weekly, daily, 2026)
        self.assertEqual([stats[t][7]['rank'] for t in (1,2,3)], [1,1,3])
        self.assertEqual(stats[1][-1], {'label':'PPM','rank':None,'value':'N/A'})

    def test_missing_team_season_returns_no_roster(self):
        self.assertIsNone(season_roster(prepare_players(self.weekly), self.daily, self.activity, -1, 2026))


if __name__ == '__main__':
    unittest.main()
