import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from generate_home_current import build, project
from build_homepage import raw_stats


class CurrentHomeTests(unittest.TestCase):
    def setUp(self):
        self.current = {'season': 2027, 'week': 1, 'scoringPeriod': 1,
                        'teams': [{'teamId': i, 'teamName': f'Team {i}'} for i in range(1, 11)]}
        self.calendar = {'season': 2027, 'firstPeriod': 1, 'finalPeriod': 167,
                         'dateAnchor': '2026-10-19', 'regularWeeks': 20,
                         'weeks': [{'week': 1, 'firstPeriod': 1, 'lastPeriod': 1,
                                    'start': '2026-10-20', 'end': '2026-10-20'}],
                         'matchups': [{'week': 1, 'sides': [{'teamId': i, 'pointsByPeriod': {'1': 0}},
                                                           {'teamId': i+1, 'pointsByPeriod': {'1': 0}}]}
                                      for i in range(1, 11, 2)]}
        self.mapping = [{'Year': '2027', 'Scoring Period': '1', 'Week': '1'}]
        self.config = {'team_logo_paths': {}, 'default_logo_path': 'assets/logos/Default.png', 'team_colors': {}}
        self.daily = []
        self.manifest = {'calendars': []}
        self.seasonal = {}

    def render(self):
        return project(self.current, self.calendar, self.mapping, self.daily,
                       self.manifest, self.seasonal, [], self.config)

    def player(self, pid, period, points, minutes=10):
        return {'Year': '2027', 'Scoring Period': str(period), 'Date': f'2026-10-{19+period:02}',
                'Team ID': '1', 'Player ID': str(pid), 'Player Name': f'Player {pid}',
                'FPTS': str(points), 'MIN': str(minutes)}

    def test_opening_day_without_completed_games_has_all_zero_score_matchups(self):
        view = self.render()
        self.assertTrue(view['active'])
        self.assertEqual((view['season'], view['week'], view['scoringPeriod']), (2027, 1, 1))
        self.assertEqual(len(view['matchups']), 5)
        self.assertTrue(all(m['scoreDisplay'] == ['0', '0'] for m in view['matchups']))
        self.assertEqual(view['players'], [])
        self.assertIsNone(view['state']['dailyDate'])
        self.assertEqual(view['scoringStatus'], 'zero')
        self.assertIsNone(view['state']['weeklyWeek'])

    def test_partial_scores_are_authoritative_and_never_marked_final(self):
        self.calendar['matchups'][0]['sides'][1]['pointsByPeriod']['1'] = 12.5
        self.daily = [self.player(1, 1, 99)]
        view = self.render()
        self.assertEqual(view['matchups'][0]['scoreDisplay'], ['0', '12.5'])
        self.assertNotIn('winnerId', view['matchups'][0])
        self.assertNotIn('final', view['players'][0])
        self.assertEqual(view['scoringStatus'], 'started')

    def test_first_day_of_next_week_uses_period_mapping_not_calendar_or_previous_games(self):
        self.current.update(week=2, scoringPeriod=8)
        self.mapping.append({'Year': '2027', 'Scoring Period': '8', 'Week': '2'})
        for matchup in self.calendar['matchups']:
            matchup['week'] = 2
        self.daily = [self.player(1, 1, 200)]
        view = self.render()
        self.assertTrue(view['active'])
        self.assertEqual(view['state']['week'], 2)
        self.assertEqual(view['players'], [])

    def test_first_valid_record_reveals_new_week_even_with_zero_points(self):
        self.current.update(week=2, scoringPeriod=8)
        self.mapping.append({'Year': '2027', 'Scoring Period': '8', 'Week': '2'})
        self.daily = [self.player(1, 1, 999), self.player(2, 8, 0, 1)]
        players = self.render()['players']
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0]['playerId'], 2)
        self.assertEqual(players[0]['scoringPeriod'], 8)
        self.assertEqual(players[0]['points'], 0)
        self.assertEqual(self.render()['state']['scoringPeriod'], 8)

    def recap_fixture(self, week, period):
        # A short opening week and an extended next week; no seven-day cadence.
        sequence = {1: [1, 2, 3], 2: list(range(4, 15)), 3: [15, 16, 17, 18]}
        self.mapping = [{'Year': '2027', 'Scoring Period': str(p), 'Week': str(w)}
                        for w, periods in sequence.items() for p in periods]
        self.current.update(week=week, scoringPeriod=period)
        self.manifest = {'calendars': [{'season': 2027, 'completedWeeks': list(range(1, week))}]}
        self.seasonal = {'weekly-recap': {str(w): {'week': w, 'end': '2026-10-25',
            'leaders': [{'teamId': 1}], 'matches': [{'teams': []}], 'closest': [], 'lineup': []}
            for w in range(1, week)}}
        for match in self.calendar['matchups']:
            match['week'] = week
            for side in match['sides']:
                side['pointsByPeriod'] = {str(p): 0 for p in sequence[week] if p <= period}

    def test_first_two_actual_periods_of_each_week_with_no_player_rows(self):
        for week, period, visible in [(1, 1, False), (2, 4, True), (2, 5, True),
                                      (2, 6, False), (2, 14, False),
                                      (3, 15, True), (3, 16, True), (3, 17, False)]:
            with self.subTest(week=week, period=period):
                self.recap_fixture(week, period)
                view = self.render()
                self.assertEqual(view['state']['weeklyFirst'], visible)
                self.assertEqual(view['state']['weeklyWeek'], week - 1 if week > 1 else None)
                self.assertEqual(view['players'], [])
                self.assertEqual(view['scoringStatus'], 'zero')

    def test_missing_incomplete_or_uncompleted_recap_never_uses_an_older_week(self):
        for invalid in (None, {}, {'week': 2}, {'week': 1},
                        {'week': 2, 'end': '2026-10-25', 'leaders': [], 'matches': []}):
            self.recap_fixture(3, 15)
            self.seasonal['weekly-recap']['2'] = invalid
            self.assertIsNone(self.render()['state']['weeklyWeek'])
        self.recap_fixture(3, 15)
        self.manifest['calendars'][0]['completedWeeks'] = [1]
        self.assertIsNone(self.render()['state']['weeklyWeek'])

    def test_missing_scoring_period_is_safe(self):
        self.current.pop('scoringPeriod')
        self.assertFalse(self.render()['active'])

    def test_missing_scores_are_unknown_and_prior_week_scores_do_not_start_current_week(self):
        self.recap_fixture(2, 4)
        self.calendar['matchups'][0]['sides'][0]['pointsByPeriod'] = {'3': 999}
        view = self.render()
        self.assertEqual(view['scoringStatus'], 'unavailable')
        self.assertEqual(view['matchups'][0]['scoreDisplay'][0], '—')
        self.calendar['matchups'][0]['sides'][1]['pointsByPeriod']['4'] = 5
        self.assertEqual(self.render()['scoringStatus'], 'started')

    def test_invalid_scores_and_missing_matchups_are_not_zero(self):
        for value in ('', None, 'nan', 'inf'):
            self.calendar['matchups'][0]['sides'][0]['pointsByPeriod']['1'] = value
            self.assertEqual(self.render()['scoringStatus'], 'unavailable')
        self.calendar['matchups'] = []
        self.assertEqual(self.render()['scoringStatus'], 'unavailable')

    def test_nonzero_periods_that_net_to_zero_still_establish_scoring(self):
        self.recap_fixture(2, 5)
        self.calendar['matchups'][0]['sides'][0]['pointsByPeriod'] = {'4': 10, '5': -10}
        self.assertEqual(self.render()['scoringStatus'], 'started')

    def test_current_week_games_filter_sort_deduplicate_and_keep_dates(self):
        self.current.update(week=2, scoringPeriod=9)
        self.mapping += [{'Year':'2027','Scoring Period':str(p),'Week':'2'} for p in (8, 9, 10)]
        self.daily = [self.player(1,1,200), self.player(2,8,60), self.player(2,8,60),
                      self.player(3,9,70), self.player(3,8,55), self.player(4,10,999), self.player(5,9,0,0)]
        players = self.render()['players']
        self.assertEqual([p['points'] for p in players], [70,60,55])
        self.assertEqual([p['date'] for p in players], ['2026-10-28','2026-10-27','2026-10-27'])

    def test_playoffs_select_active_bracket_without_any_completed_day(self):
        self.current['week'] = 21
        self.mapping[0]['Week'] = '21'
        self.calendar['weeks'][0]['week'] = 21
        self.calendar['matchups'][0]['week'] = 21
        view = self.render()
        self.assertEqual(view['state']['phase'], 'playoffs')
        self.assertEqual(view['bracket']['rounds'][0]['status'], 'active')
        self.assertIsNone(view['bracket']['champion'])

    def test_outside_espn_season_or_unmapped_period_is_not_active(self):
        self.current['scoringPeriod'] = 168
        self.assertFalse(self.render()['active'])
        self.current['scoringPeriod'] = 2
        self.assertFalse(self.render()['active'])

    def test_no_games_day_does_not_require_performance_rows(self):
        self.current['scoringPeriod'] = 2
        self.mapping.append({'Year':'2027','Scoring Period':'2','Week':'1'})
        self.assertTrue(self.render()['active'])
        self.assertEqual(len(self.render()['matchups']), 5)

    def test_weekly_individual_games_export_the_same_raw_stats_as_daily(self):
        self.calendar['scoringWeights']={'PTS':1,'AST':2,'FGM':2,'FGA':-1,'3PM':1}
        row=self.player(1,1,60)
        row.update({'PTS':'25','AST':'14','FGM':'16','FGA':'-20','3PM':'4','3PA':'11'})
        self.daily=[row]
        player=self.render()['players'][0]
        self.assertEqual(player['stats'],raw_stats(row,self.calendar['scoringWeights']))
        self.assertEqual((player['stats']['3PA'],player['stats']['AST'],player['points']),(11,7,60))
        self.assertIsNone(raw_stats({'3PM':'4'}, {'3PM':1})['3PA'])
        self.assertEqual(raw_stats({'3PA':'0'}, {})['3PA'],0)
        self.assertNotIn('gameStatus',player)

    def test_version_is_stable_and_changes_with_scores_or_recaps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'source'; output = root/'out'
            source.mkdir(); output.mkdir()
            (source/'currentLeague.json').write_text(json.dumps(self.current))
            (source/'seasonMetadata.json').write_text(json.dumps({'seasons':[self.calendar]}))
            (output/'homepage.json').write_text(json.dumps({'calendars':[]}))
            (output/'2027').mkdir()
            def csv_rows(path):
                return self.mapping if path.name == 'scoringPeriodMatchupMap.csv' else []
            with patch('generate_home_current.read_csv', side_effect=csv_rows), patch('generate_home_current.logo_config', return_value=self.config):
                build(source, output)
                version = (output/'home-version.json').read_text()
                build(source, output)
                self.assertEqual(version, (output/'home-version.json').read_text())
                self.calendar['matchups'][0]['sides'][0]['pointsByPeriod']['1'] = 12
                (source/'seasonMetadata.json').write_text(json.dumps({'seasons':[self.calendar]}))
                build(source, output)
                self.assertNotEqual(version, (output/'home-version.json').read_text())
                version = (output/'home-version.json').read_text()
                (output/'2027/daily-recap.json').write_text(json.dumps({'data':{'2026-10-19':{'players':[]}}}))
                build(source, output)
                self.assertNotEqual(version, (output/'home-version.json').read_text())


if __name__ == '__main__':
    unittest.main()
