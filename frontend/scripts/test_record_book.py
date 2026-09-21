"""Deterministic parity tests against the actual Dash Record Book callback."""
import ast
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_record_book import (ROOT, all_fantasy_team, all_time, build,
                                  player_totals, transaction_rankings)
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
        cls.config = logo_config()
        cls.logos = cls.config['team_logo_paths']
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
        for key, index in (('hundredPointDays', 1), ('negativePointDays', 2)):
            projected = [{column: row[column] for column in ('Date', 'Player Name', 'Team Name', 'FPTS')}
                         for row in exported[key]]
            self.assertEqual(projected, table_data(tables[index]))
            self.assertTrue(all(row['team']['teamId'] for row in exported[key]))
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

    def test_every_season_has_complete_unique_roster_and_ranked_awards(self):
        for year in self.payload['years']:
            with self.subTest(year=year):
                exported = self.payload['seasons'][str(year)]
                roster = exported['allFantasyTeam']
                self.assertEqual(len(roster), len(exported['roster']['activeSlots']) + exported['roster']['benchSlots'])
                self.assertEqual(len({row['playerId'] for row in roster}), len(roster))
                self.assertTrue(all(row['team']['teamId'] for row in roster))
                self.assertLessEqual(len(exported['bestWaiverAdds']), 10)
                self.assertLessEqual(len(exported['bestDraftPicks']), 10)
                self.assertEqual(exported['journeymen'][0]['rank'], 1)
                self.assertTrue(all(row['teamCount'] >= 3 for row in exported['journeymen']))
                self.assertTrue(all(len(row['teams']) == row['teamCount'] for row in exported['journeymen']))
                for player in exported['journeymen']:
                    history = self.activity[(self.activity['Year'] == year) &
                                            (self.activity['Player ID'] == player['playerId'])].copy()
                    history['_date'] = pd.to_datetime(history['Date'])
                    history['_time'] = history['Time'].fillna('')
                    history['_order'] = range(len(history))
                    history.sort_values(['_date', '_time', '_order'], inplace=True)
                    expected = list(dict.fromkeys(int(value) for value in history['Team ID'].dropna()))
                    self.assertEqual([team['teamId'] for team in player['teams']], expected)

    def test_championship_history_contains_each_completed_champion_once(self):
        champions = self.payload['allTime']['champions']
        completed = {int(year) for year in self.payload['years']
                     if self.payload['seasons'][str(year)]['champion']}
        self.assertEqual({row['year'] for row in champions}, completed)
        self.assertEqual(len({row['year'] for row in champions}), len(champions))

    def test_isolated_activity_edge_filters_and_best_waiver_deduplication(self):
        year = int(self.weekly['Year'].max())
        activity = self.activity[self.activity['Year'] == year].copy()
        first = activity.iloc[0].copy()
        excluded = []
        for action in ('KEEPER', 'NOT KEPT', 'RECEIVED', 'FA ADDED'):
            row = first.copy(); row['Action'] = action; row['Asset'] = f'Excluded {action}'
            excluded.append(row)
        changed = pd.concat([self.activity, pd.DataFrame(excluded)], ignore_index=True)
        result = all_time(self.league, self.weekly, self.daily, changed, self.config)
        names = {row['Asset'] for row in result['transactionLeaders']}
        self.assertFalse(names & {row['Asset'] for row in excluded})

    def test_latest_position_eligibility_controls_lineup(self):
        daily = pd.DataFrame([
            {'Year': 2026, 'Date': '2025-10-20', 'Scoring Period': 1, 'Player Slot': 'PG', 'Player ID': 1, 'Player Name': 'Changed', 'Team ID': 1, 'Position': 'PG', 'Position2': None, 'Position3': None, 'FPTS': 50},
            {'Year': 2026, 'Date': '2026-01-20', 'Scoring Period': 90, 'Player Slot': 'SF', 'Player ID': 1, 'Player Name': 'Changed', 'Team ID': 1, 'Position': 'SF', 'Position2': None, 'Position3': None, 'FPTS': 50},
            {'Year': 2026, 'Date': '2026-01-20', 'Scoring Period': 90, 'Player Slot': 'PG', 'Player ID': 2, 'Player Name': 'Guard', 'Team ID': 2, 'Position': 'PG', 'Position2': None, 'Position3': None, 'FPTS': 80},
        ])
        players = player_totals(daily, 2026, ['PG', 'SF'], {1: {'teamId': 1}, 2: {'teamId': 2}})
        lineup = all_fantasy_team(players, ['PG', 'SF'], 0)
        self.assertEqual([(row['slot'], row['name']) for row in lineup], [('PG', 'Guard'), ('SF', 'Changed')])

    def test_draft_pick_requires_drafted_to_be_latest_action(self):
        activity = pd.DataFrame([
            {'Year': 2024, 'Date': '2023-10-01', 'Time': '10:00', 'Player ID': 1, 'Asset': 'Older Pick', 'Team ID': 1, 'Action': 'DRAFTED'},
            {'Year': 2025, 'Date': '2024-10-20', 'Time': '10:00', 'Player ID': 1, 'Asset': 'Older Pick', 'Team ID': 1, 'Action': 'DROPPED'},
            {'Year': 2024, 'Date': '2023-10-01', 'Time': '10:00', 'Player ID': 2, 'Asset': 'Dropped Same Year', 'Team ID': 2, 'Action': 'DRAFTED'},
            {'Year': 2024, 'Date': '2024-01-20', 'Time': '10:00', 'Player ID': 2, 'Asset': 'Dropped Same Year', 'Team ID': 2, 'Action': 'DROPPED'},
        ])
        scores = pd.DataFrame([{'Player ID': 1, 'Team ID': 1, 'FPTS': 200},
                               {'Player ID': 2, 'Team ID': 2, 'FPTS': 100}])
        ranked = transaction_rankings(activity, scores, {1: {'teamId': 1}, 2: {'teamId': 2}},
                                      'DRAFTED', True, 2024)
        self.assertEqual([row['name'] for row in ranked], ['Older Pick'])


if __name__ == '__main__':
    unittest.main()
