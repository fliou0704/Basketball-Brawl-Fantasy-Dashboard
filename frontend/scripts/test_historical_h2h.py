"""Direct offline parity against the actual Historical H2H callbacks."""
import ast
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
import warnings

import pandas as pd

from generate_historical_h2h import ROOT, build, perspective
from test_team_stats import Html, Element


def callbacks(league, players):
    tree = ast.parse((ROOT / 'basketballBrawlHistoricalH2H.py').read_text())
    register = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='register_h2h_callbacks')
    functions = [n for n in register.body if isinstance(n, ast.FunctionDef)]
    for node in functions:
        node.decorator_list = []
    namespace = {'data': league.copy(), 'playerMatchup': players.copy(), 'html': Html(), 'dcc': Html(), 'pd': pd,
                 'DataTable': lambda **props: Element('DataTable', **props),
                 'dash': types.SimpleNamespace(callback_context=types.SimpleNamespace(triggered=[{'prop_id':'selected-matchup.data'}]))}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<Dash H2H oracle>', 'exec'), namespace)
    return namespace


class HistoricalH2HParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('H2H_TEST_SOURCE', ROOT / 'data'))
        cls.league = pd.read_csv(source / 'basketballBrawlLeagueData.csv')
        cls.players = pd.read_csv(source / 'playerMatchupData.csv')
        cls.oracle = callbacks(cls.league, cls.players)
        cls.temp = tempfile.TemporaryDirectory()
        output = Path(cls.temp.name)
        build(source, output)
        cls.manifest = json.loads((output / 'historical-h2h.json').read_text())
        cls.payloads = [json.loads(p.read_text()) for p in sorted((output/'historical-h2h').glob('*.json'))]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_45_pairs_both_perspectives_records_history_and_bolding(self):
        self.assertEqual(len(self.payloads), 45)
        self.assertEqual(len(self.manifest['pairs']), 90)
        playoff_pairs, regular_only = 0, 0
        for pair in self.payloads:
            for view in pair['perspectives'].values():
                with self.subTest(first=view['team1Id'], second=view['team2Id']), warnings.catch_warnings():
                    warnings.simplefilter('ignore', pd.errors.SettingWithCopyWarning)
                    reference = self.oracle['update_h2h'](view['team1Id'], view['team2Id'])
                    if view['message']:
                        self.assertEqual(reference.children, view['message'])
                        continue
                    self.assertEqual(reference.find('H3')[0].children, view['title'])
                    self.assertEqual([p.children for p in reference.find('P')], [f"{r['label']}: {r['value']}" for r in view['records']])
                    table = reference.find('DataTable')[0]
                    self.assertEqual(table.props['data'], [r['fields'] for r in view['history']])
                    self.assertEqual([c['id'] for c in table.props['columns']], self.manifest['columns'])
                    self.assertEqual([r['playoff'] for r in view['history']], [r['Type']=='Playoffs' for r in table.props['data']])
                    playoff_pairs += any(r['playoff'] for r in view['history'])
                    regular_only += not any(r['playoff'] for r in view['history'])
        self.assertGreater(playoff_pairs, 0)
        self.assertGreater(regular_only, 0)

    def test_every_matchup_player_detail_matches_actual_callback(self):
        for pair in self.payloads:
            for view in pair['perspectives'].values():
                for row in view['history']:
                    details = row['details']
                    selected = {'Year':details['year'], 'Week':details['week'], 'Team1':details['teams'][0], 'Team2':details['teams'][1]}
                    with self.subTest(pair=view['title'], year=details['year'], week=details['week']), warnings.catch_warnings():
                        warnings.simplefilter('ignore', FutureWarning)
                        _, reference = self.oracle['toggle_modal'](selected,view['team1Id'],view['team2Id'],0)
                        expected = [[c.children for c in r.find('Td')] for r in reference.find('Tbody')[0].find('Tr')]
                        actual = [[a['name'],a['fpts'],'',b['fpts'],b['name']] for a,b in zip(*details['players'])]
                        self.assertEqual(actual, expected)

    def test_selector_names_order_and_exclusion_match_dash(self):
        for first in [None]+[t['teamId'] for t in self.manifest['teams']]:
            for second in [None]+[t['teamId'] for t in self.manifest['teams']]:
                expected = self.oracle['update_dropdown_options'](first,second)
                actual = tuple([{'label':t['teamName'],'value':t['teamId']} for t in self.manifest['teams'] if t['teamId']!=excluded] for excluded in (second,first))
                self.assertEqual(actual, expected)

    def test_historical_names_are_not_replaced_by_current_names(self):
        changed = 0
        for pair in self.payloads:
            for view in pair['perspectives'].values():
                for row in view['history']:
                    f = row['fields']
                    self.assertEqual(row['details']['teams'], [f['Team Name'],f['Opponent Team Name']])
                    current = next(t['teamName'] for t in self.manifest['teams'] if t['teamId']==view['team1Id'])
                    changed += f['Team Name'] != current
        self.assertGreater(changed, 0)

    def test_reversed_results_and_scores_follow_each_team_perspective(self):
        for pair in self.payloads:
            first, second = pair['perspectives'].values()
            other = {(r['fields']['Year'],r['fields']['Week']):r['fields'] for r in second['history']}
            for row in first['history']:
                r = row['fields']; reverse = other[(r['Year'],r['Week'])]
                self.assertEqual(r['Score'].split(' - '), list(reversed(reverse['Score'].split(' - '))))
                self.assertEqual(r['Team Name'], reverse['Opponent Team Name'])
                if len(set(r['Score'].split(' - ')))>1:
                    self.assertNotEqual(r['Result'], reverse['Result'])

    def test_ties_consolation_and_never_played_match_dash(self):
        league = self.league.copy()
        latest = league[league['Year']==league['Year'].max()]
        latest = latest[latest['Week']==latest['Week'].max()].copy()
        first, second = latest['Team ID'].iloc[:2].tolist()
        base = latest.iloc[0].copy()
        base['Team ID'], base['Opponent Team ID'] = first, second
        base['Win'], base['Loss'], base['Points For'], base['Points Against'] = 0, 0, 100, 100
        base['Type'] = 'Regular'
        consolation = base.copy(); consolation['Type'], consolation['Win'], consolation['Week'] = 'Consolation', 1, 1
        latest['Opponent Team ID'] = -1
        fixture = pd.concat([latest, pd.DataFrame([base,consolation])], ignore_index=True)
        value = perspective(fixture,self.players,int(first),int(second))
        reference = callbacks(fixture,self.players)['update_h2h'](first,second)
        self.assertEqual(value['records'][0]['value'], '1 - 1')
        self.assertEqual(value['history'][0]['fields']['Result'], 'L')
        self.assertEqual(len(value['history']), 1)
        self.assertEqual([p.children for p in reference.find('P')], [f"{r['label']}: {r['value']}" for r in value['records']])
        reverse = perspective(fixture,self.players,int(second),int(first))
        self.assertEqual(reverse['message'],'These teams have never played before.')


if __name__ == '__main__':
    unittest.main()
