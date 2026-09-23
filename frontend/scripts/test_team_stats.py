"""Parity oracle executes the actual Dash callback with inert HTML components."""
import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
import warnings

import pandas as pd

from generate_team_stats import (ROOT, build, physical_metrics, player_percentiles, prepare_players,
                                 point_rank_captions, roster_mpg, season_reference_date, season_roster,
                                 stat_values, weekly_performance)
from playerDailyAggregation import aggregate_daily_to_weekly, load_scoring_period_map, load_season_metadata


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
        cls.daily_weekly = aggregate_daily_to_weekly(
            cls.daily, load_scoring_period_map(), load_season_metadata(), active_only=True
        )
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
        self.assertEqual([t['owner'] for t in self.manifest['teams']], list(expected['Team Owner']))

    def test_season_snapshots_match_final_regular_season_source(self):
        for tid, payload in self.payloads.items():
            for year in self.manifest['years']:
                season = payload['seasons'][str(year)]
                if season is None:
                    continue
                regular = self.league[(self.league['Year'] == year) &
                                      (self.league['Type'] == 'Regular') &
                                      (self.league['Team ID'] == tid)]
                source = regular.loc[regular['Week'].idxmax()]
                final_week = regular['Week'].max()
                rank = self.league[(self.league['Year'] == year) &
                                   (self.league['Week'] == final_week) &
                                   (self.league['Team ID'] == tid)].iloc[0]['Rank']
                snapshot = season['snapshot']
                self.assertEqual(snapshot['rank'], int(rank))
                self.assertEqual(snapshot['record'], f"{int(source['Cumulative Wins'])}–{int(source['Cumulative Losses'])}")
                self.assertEqual(snapshot['pointsFor'], source['Cumulative Points For'])
                self.assertEqual(snapshot['pointsAgainst'], source['Cumulative Points Against'])

    def test_points_for_and_against_rank_captions_follow_direction_and_ties(self):
        teams = [
            {'teamId': 1, 'pointsFor': 120, 'pointsAgainst': 80},
            {'teamId': 2, 'pointsFor': 110, 'pointsAgainst': 90},
            {'teamId': 3, 'pointsFor': 100, 'pointsAgainst': 100},
            {'teamId': 4, 'pointsFor': 100, 'pointsAgainst': 100},
        ]
        result = point_rank_captions(teams)
        self.assertEqual(result[1]['pointsForRankCaption'], '1st')
        self.assertEqual(result[4]['pointsForRankCaption'], 'T-3rd')
        self.assertEqual(result[1]['pointsAgainstRankCaption'], '1st')
        self.assertEqual(result[4]['pointsAgainstRankCaption'], 'T-3rd')

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
                    actual = [{key: stat[key] for key in ('label','rank','value')} for stat in season['rankings']]
                    self.assertEqual(actual, [{'label': l, 'rank': r, 'value': v} for l,r,v in zip(labels,ranks,values)])

    def test_category_relative_bars_map_first_to_full_and_last_to_empty(self):
        year = self.manifest['years'][0]
        by_label = {}
        for payload in self.payloads.values():
            season = payload['seasons'][str(year)]
            if season:
                for stat in season['rankings']:
                    by_label.setdefault(stat['label'], []).append(stat)
        for label, stats in by_label.items():
            available = [stat for stat in stats if stat['rank'] is not None]
            self.assertTrue(all(0 <= stat['relativePercent'] <= 100 for stat in available))
            self.assertTrue(all(stat['rankImage'].startswith('placements/') for stat in available))
            self.assertTrue(all(stat['relativePercent'] == 100 for stat in available if stat['rank'] == 1))
            last_rank = max(stat['rank'] for stat in available)
            for stat in available:
                expected = (last_rank - stat['rank']) / (last_rank - 1) * 100
                self.assertAlmostEqual(stat['relativePercent'], expected, delta=.11, msg=label)
            self.assertTrue(all(stat['relativePercent'] == 0 for stat in available if stat['rank'] == last_rank))

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

    def test_roster_exports_box_score_totals_games_and_status(self):
        payload = self.payloads[16]
        year = self.manifest['years'][0]
        roster = payload['seasons'][str(year)]['roster']
        self.assertTrue(roster)
        required = {'games','points','rebounds','assists','steals','blocks','turnovers',
                    'threePointers','fieldGoalPct','freeThrowPct','current',
                    'fptsPercentile','fppmPercentile'}
        self.assertTrue(all(required.issubset(row) for row in roster))
        source = prepare_players(self.weekly)
        for player in roster[:3]:
            rows = source[(source['Year'] == year) & (source['Team ID'] == 16) &
                          (source['Player ID'] == player['playerId'])]
            self.assertEqual(player['points'], str(int(rows['PTS'].sum())))
            self.assertEqual(player['rebounds'], str(int(rows['REB'].sum())))
            appearances = self.daily[(self.daily['Year'] == year) & (self.daily['Team ID'] == 16) &
                                     (self.daily['Player ID'] == player['playerId']) & (self.daily['MIN'] > 0)]['Date'].nunique()
            self.assertEqual(player['games'], appearances)
        self.assertTrue(any(row['current'] for row in roster))
        self.assertTrue(any(not row['current'] for row in roster))
        self.assertTrue(all(row['current'] == (row['action'] not in ('DROPPED','TRADED','NOT KEPT')) for row in roster))
        for row in roster:
            for key in ('fptsPercentile', 'fppmPercentile'):
                self.assertTrue(row[key] is None or 0 <= row[key] <= 100)

    def test_player_percentiles_are_league_relative_for_fpts_and_fppm(self):
        weekly = pd.DataFrame([
            {'Year': 2026, 'Week': 1, 'Player ID': 1, 'FPTS': 100},
            {'Year': 2026, 'Week': 1, 'Player ID': 2, 'FPTS': 50},
            {'Year': 2026, 'Week': 1, 'Player ID': 3, 'FPTS': 10},
        ])
        daily = pd.DataFrame([
            {'Year': 2026, 'Player ID': 1, 'FPTS': 20, 'MIN': 40},
            {'Year': 2026, 'Player ID': 2, 'FPTS': 30, 'MIN': 30},
            {'Year': 2026, 'Player ID': 3, 'FPTS': 10, 'MIN': 40},
        ])
        result = player_percentiles(weekly, daily, 2026)
        self.assertEqual([result[pid]['fptsPercentile'] for pid in (1, 2, 3)], [100, 50, 0])
        self.assertEqual([result[pid]['fppmPercentile'] for pid in (2, 1, 3)], [100, 50, 0])

    def test_weekly_performance_sums_team_fpts_and_exports_chart_geometry(self):
        rows = pd.DataFrame([
            {'Year': 2026, 'Week': 1, 'Team ID': 7, 'FPTS': 100, 'MIN': 50, 'Fantasy Starts': 2},
            {'Year': 2026, 'Week': 1, 'Team ID': 7, 'FPTS': 50, 'MIN': 50, 'Fantasy Starts': 1},
            {'Year': 2026, 'Week': 2, 'Team ID': 7, 'FPTS': 225, 'MIN': 150, 'Fantasy Starts': 4},
            {'Year': 2026, 'Week': 1, 'Team ID': 8, 'FPTS': 900, 'MIN': 10, 'Fantasy Starts': 1},
            {'Year': 2025, 'Week': 1, 'Team ID': 7, 'FPTS': 800, 'MIN': 10, 'Fantasy Starts': 1},
        ])
        result = weekly_performance(rows, 7, 2026)
        metric, fppm, starts = [result['metrics'][key] for key in ('fpts', 'fppm', 'starts')]
        self.assertEqual(result['weeks'], [1, 2])
        self.assertEqual([point['value'] for point in metric['points']], [150, 225])
        self.assertEqual([point['display'] for point in metric['points']], ['150', '225'])
        self.assertEqual([point['value'] for point in fppm['points']], [1.5, 1.5])
        self.assertEqual([point['display'] for point in fppm['points']], ['1.5', '1.5'])
        self.assertEqual([point['value'] for point in starts['points']], [3, 4])
        self.assertEqual(metric['points'][0]['x'], 54)
        self.assertEqual(metric['points'][-1]['x'], 770)
        self.assertEqual([point['week'] for point in metric['points']], result['weeks'])
        self.assertTrue(all('showLabel' not in point for point in metric['points']))
        self.assertEqual(len(metric['yTicks']), 5)
        self.assertTrue(metric['path'])

    def test_weekly_fppm_and_starts_use_only_canonical_active_performances(self):
        daily = pd.DataFrame([
            {'Year': 2026, 'Scoring Period': 1, 'Team ID': 7, 'Player ID': 1,
             'Team Name': 'Seven', 'Player Name': 'Active', 'Player Slot': 'PG', 'FPTS': 20, 'MIN': 10},
            {'Year': 2026, 'Scoring Period': 2, 'Team ID': 7, 'Player ID': 1,
             'Team Name': 'Seven', 'Player Name': 'Active', 'Player Slot': 'UT', 'FPTS': 10, 'MIN': 20},
            {'Year': 2026, 'Scoring Period': 1, 'Team ID': 7, 'Player ID': 2,
             'Team Name': 'Seven', 'Player Name': 'Bench', 'Player Slot': 'BE', 'FPTS': 100, 'MIN': 20},
        ])
        mapping = pd.DataFrame([{'Year': 2026, 'Scoring Period': period, 'Week': 1} for period in (1, 2)])
        metadata = {'seasons': [{'season': 2026, 'lineupSlots': ['PG', 'UT']}]}
        canonical = aggregate_daily_to_weekly(daily, mapping, metadata, active_only=True)
        result = weekly_performance(canonical, 7, 2026)['metrics']
        self.assertEqual(result['fpts']['points'][0]['value'], 30)
        self.assertEqual(result['fppm']['points'][0]['value'], 1)
        self.assertEqual(result['starts']['points'][0]['value'], 2)

    def test_roster_mpg_aggregates_active_minutes_before_dividing_by_starts(self):
        active = pd.DataFrame([
            {'Year': 2026, 'Week': 1, 'Team ID': 7, 'Player ID': 10, 'MIN': 20, 'Fantasy Starts': 2},
            {'Year': 2026, 'Week': 2, 'Team ID': 7, 'Player ID': 10, 'MIN': 30, 'Fantasy Starts': 1},
            {'Year': 2026, 'Week': 1, 'Team ID': 7, 'Player ID': 11, 'MIN': 40, 'Fantasy Starts': 0},
        ])
        result = roster_mpg(active, 7, 2026)
        self.assertAlmostEqual(result[10], 50 / 3)
        self.assertTrue(pd.isna(result[11]))

    def test_known_team_week_matches_canonical_daily_aggregation(self):
        expected = self.daily_weekly[(self.daily_weekly['Year'] == 2025) &
                                     (self.daily_weekly['Team ID'] == 16) &
                                     (self.daily_weekly['Week'] == 1)]
        totals = expected[['FPTS', 'MIN', 'Fantasy Starts']].sum()
        exported = self.payloads[16]['seasons']['2025']['weeklyPerformance']['metrics']
        self.assertEqual(exported['fpts']['points'][0]['value'], totals['FPTS'])
        self.assertAlmostEqual(exported['fppm']['points'][0]['value'], totals['FPTS'] / totals['MIN'], places=3)
        self.assertEqual(exported['starts']['points'][0]['value'], totals['Fantasy Starts'])

    def test_physicals_use_current_roster_and_metric_specific_denominators(self):
        rosters = {
            1: [{'playerId': 1, 'current': True}, {'playerId': 2, 'current': False},
                {'playerId': 3, 'current': True}],
            2: [{'playerId': 4, 'current': True}],
        }
        metadata = pd.DataFrame([
            {'ESPN Player ID': 1, 'Birth Date': '2000-10-22', 'Height Inches': 72, 'Weight Pounds': 180},
            {'ESPN Player ID': 2, 'Birth Date': '1980-01-01', 'Height Inches': 90, 'Weight Pounds': 300},
            {'ESPN Player ID': 3, 'Birth Date': '2001-10-23', 'Height Inches': None, 'Weight Pounds': 210},
            {'ESPN Player ID': 4, 'Birth Date': '1999-01-01', 'Height Inches': 78, 'Weight Pounds': 220},
        ])
        seasons = {'seasons': [{'season': 2025, 'weeks': [{'start': '2024-10-22'}]}]}
        result = physical_metrics(rosters, metadata, seasons, 2025)
        team = {metric['key']: metric for metric in result[1]}
        self.assertEqual(team['age']['rawValue'], 23)
        self.assertEqual(team['age']['sampleSize'], 2)
        self.assertEqual(team['height']['rawValue'], 72)
        self.assertEqual(team['height']['value'], '6\'0"')
        self.assertEqual(team['height']['sampleSize'], 1)
        self.assertAlmostEqual(team['bmi']['rawValue'], 703 * 180 / 72 ** 2, places=4)
        self.assertEqual(team['bmi']['sampleSize'], 1)
        self.assertEqual(team['height']['rank'], 2)
        self.assertEqual(team['height']['caption'], '2nd Tallest')

    def test_historical_age_uses_first_matchup_date(self):
        seasons = {'seasons': [{'season': 2025, 'weeks': [{'start': '2024-10-22'}]}]}
        self.assertEqual(season_reference_date(seasons, 2025), pd.Timestamp('2024-10-22'))
        metadata = pd.DataFrame([
            {'ESPN Player ID': 1, 'Birth Date': '2000-10-22', 'Height Inches': 72, 'Weight Pounds': 180},
            {'ESPN Player ID': 2, 'Birth Date': '2000-10-23', 'Height Inches': 72, 'Weight Pounds': 180},
        ])
        result = physical_metrics({1: [{'playerId': 1, 'current': True},
                                       {'playerId': 2, 'current': True}]}, metadata, seasons, 2025)
        age = next(metric for metric in result[1] if metric['key'] == 'age')
        self.assertEqual(age['rawValue'], 23.5)

    def test_physical_rank_labels_and_ties_follow_min_rank(self):
        rosters = {team_id: [{'playerId': team_id, 'current': True}] for team_id in range(1, 5)}
        metadata = pd.DataFrame([
            {'ESPN Player ID': 1, 'Birth Date': '2004-01-01', 'Height Inches': 80, 'Weight Pounds': 240},
            {'ESPN Player ID': 2, 'Birth Date': '2003-01-01', 'Height Inches': 80, 'Weight Pounds': 220},
            {'ESPN Player ID': 3, 'Birth Date': '2002-01-01', 'Height Inches': 76, 'Weight Pounds': 210},
            {'ESPN Player ID': 4, 'Birth Date': '2001-01-01', 'Height Inches': 74, 'Weight Pounds': 180},
        ])
        seasons = {'seasons': [{'season': 2025, 'weeks': [{'start': '2024-10-22'}]}]}
        result = physical_metrics(rosters, metadata, seasons, 2025)
        by_team = {team_id: {metric['key']: metric for metric in rows} for team_id, rows in result.items()}
        self.assertEqual([by_team[team]['age']['caption'] for team in range(1, 5)],
                         ['Youngest', '2nd Youngest', '2nd Oldest', 'Oldest'])
        self.assertEqual([by_team[team]['height']['rank'] for team in (1, 2)], [1, 1])
        self.assertEqual(by_team[1]['height']['caption'], '1st Tallest')
        self.assertEqual(by_team[1]['bmi']['caption'], '1st in League')

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
        self.assertEqual({key: stats[1][-1][key] for key in ('label','rank','value')},
                         {'label':'PPM','rank':None,'value':'N/A'})
        self.assertIsNone(stats[1][-1]['relativePercent'])
        self.assertIsNone(stats[1][-1]['rankImage'])

    def test_missing_team_season_returns_no_roster(self):
        self.assertIsNone(season_roster(prepare_players(self.weekly), self.daily, self.activity, -1, 2026))


if __name__ == '__main__':
    unittest.main()
