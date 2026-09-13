"""Deterministic parity tests against the actual Dash Record Book callback."""
import ast
import json
import os
from pathlib import Path
import tempfile
import types
import unittest

import pandas as pd

from generate_record_book import ROOT, all_time, build, season_awards
from test_team_stats import Element, Html


class App:
    def __init__(self):
        self.callbacks = {}

    def callback(self, *args, **kwargs):
        def decorate(function):
            self.callbacks[function.__name__] = function
            return function
        return decorate


def dash_oracle(league, weekly, daily, activity, logos):
    tree = ast.parse((ROOT / 'basketballBrawlRecordBook.py').read_text())
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    table = lambda **props: Element('DataTable', **props)
    namespace = {
        'pd': pd, 'html': Html(), 'dcc': Html(),
        'dash_table': types.SimpleNamespace(DataTable=table),
        'Output': lambda *args: None, 'Input': lambda *args: None,
        'data': league.copy(), 'playerMatchup': weekly.copy(),
        'playerDaily': daily.copy(), 'activityData': activity.copy(),
        'team_logo_paths': logos,
    }
    exec(compile(tree, '<Dash Record Book parity oracle>', 'exec'), namespace)
    app = App()
    namespace['register_record_book_callbacks'](app)
    return namespace, app.callbacks['update_awards_display']


def table_data(element):
    return element.find('DataTable')[0].props['data']


class RecordBookParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ.get('RECORD_BOOK_TEST_SOURCE', ROOT / 'data'))
        cls.league, cls.weekly, cls.daily, cls.activity = [pd.read_csv(cls.source / name) for name in
            ('basketballBrawlLeagueData.csv', 'playerMatchupData.csv', 'playerDailyData.csv', 'activityData.csv')]
        from build_homepage import logo_config
        cls.logos = logo_config()['team_logo_paths']
        cls.namespace, callback = dash_oracle(cls.league, cls.weekly, cls.daily, cls.activity, cls.logos)
        cls.callback = staticmethod(callback)
        cls.temp = tempfile.TemporaryDirectory()
        output = Path(cls.temp.name)
        build(cls.source, output)
        cls.payload = json.loads((output / 'record-book.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_year_options_and_default_match_dash(self):
        self.assertEqual(self.payload['defaultYear'], int(self.namespace['playerMatchup']['Year'].max()))
        self.assertEqual(self.payload['years'], sorted((int(y) for y in self.namespace['playerMatchup']['Year'].unique()), reverse=True))
        self.assertEqual([o['value'] for o in self.namespace['dropdown_options']],
                         ['All-Time'] + [str(y) for y in self.payload['years']])

    def test_all_time_single_records_match_dash_text(self):
        reference = self.callback('All-Time')
        paragraphs = [node.children for node in reference.find('P')]
        # The final paragraph is the 100-point occurrence summary.
        self.assertEqual([record['value'] for record in self.payload['allTime']['records']], paragraphs[:3])

    def test_all_time_tables_order_values_and_activity_filters_match_dash(self):
        reference = self.callback('All-Time')
        tables = reference.find('DataTable')
        exported = self.payload['allTime']
        self.assertEqual(exported['transactionLeaders'], table_data(tables[0]))
        self.assertEqual(exported['hundredPointDays'], table_data(tables[1]))
        self.assertEqual(exported['negativePointDays'], table_data(tables[2]))
        allowed = self.activity[self.activity['Action'].isin(['WAIVER ADDED','DROPPED','DRAFTED','TRADED'])]
        self.assertEqual(sum(row['Transaction Count'] for row in exported['transactionLeaders']),
                         sum(allowed['Asset'].value_counts().head(10)))
        self.assertTrue(all(row['FPTS'] >= 100 for row in exported['hundredPointDays']))
        self.assertTrue(all(row['FPTS'] < 0 for row in exported['negativePointDays']))

    def test_hundred_point_counts_and_negative_team_logo_counts_match_dash(self):
        exported = self.payload['allTime']
        reference = self.callback('All-Time')
        count_text = reference.find('P')[3].children
        self.assertEqual(', '.join(f"{r['Player Name']}: {r['Count']}" for r in exported['hundredPointCounts']), count_text)
        expected = []
        for item in reference.children[-1].children:
            image = item.find('Img')[0]
            span = item.find('Span')[0]
            expected.append({'logo': 'logos/' + Path(image.props['src']).name,
                             'count': int(span.children.removeprefix(': '))})
        self.assertEqual(exported['negativeTeamCounts'], expected)

    def test_every_season_section_value_order_and_ties_match_dash(self):
        for year in self.payload['years']:
            with self.subTest(year=year):
                reference = self.callback(str(year))
                exported = self.payload['seasons'][str(year)]
                self.assertEqual(reference.find('H3')[0].children, exported['title'])
                self.assertEqual(reference.find('H4')[0].children, exported['mvp']['label'])
                self.assertEqual(reference.find('P')[0].children, exported['mvp']['value'])
                tables = reference.find('DataTable')
                for index, team in enumerate(exported['allNba']):
                    self.assertEqual(team['label'], reference.find('H4')[index + 1].children)
                    self.assertEqual(team['players'], table_data(tables[index]))
                    self.assertEqual(len({p['Player'] for p in team['players']}), len(team['players']))
                self.assertEqual(reference.find('P')[1].children, exported['bestWaiverAdd']['value'])
                self.assertEqual(exported['mostUniqueTeams']['players'], table_data(tables[3]))
                maximum = exported['mostUniqueTeams']['players'][0]['Unique Teams']
                self.assertTrue(all(row['Unique Teams'] == maximum for row in exported['mostUniqueTeams']['players']))

    def test_isolated_activity_edge_filters_and_best_waiver_deduplication(self):
        year = int(self.weekly['Year'].max())
        activity = self.activity[self.activity['Year'] == year].copy()
        first = activity.iloc[0].copy()
        excluded = []
        for action in ('KEEPER', 'NOT KEPT', 'RECEIVED', 'FA ADDED'):
            row = first.copy(); row['Action'] = action; row['Asset'] = f'Excluded {action}'
            excluded.append(row)
        changed = pd.concat([self.activity, pd.DataFrame(excluded)], ignore_index=True)
        result = all_time(self.league, self.weekly, self.daily, changed, self.logos)
        names = {row['Asset'] for row in result['transactionLeaders']}
        self.assertFalse(names & {row['Asset'] for row in excluded})

        waiver = activity[activity['Action'] == 'WAIVER ADDED'].iloc[0].copy()
        duplicate = pd.concat([self.activity, pd.DataFrame([waiver, waiver])], ignore_index=True)
        baseline = season_awards(self.weekly, self.activity, year)['bestWaiverAdd']
        self.assertEqual(season_awards(self.weekly, duplicate, year)['bestWaiverAdd'], baseline)


if __name__ == '__main__':
    unittest.main()
