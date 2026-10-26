"""Completed-week box scores must describe the selected team's fantasy starts."""
import unittest
from build_homepage import choose_lineup, lineup_week_stats, team_info


class WeeklyLineupStatsTests(unittest.TestCase):
    def setUp(self):
        self.calendar = {'season': 2027, 'lineupSlots': ['PG', 'UT'], 'scoringWeights': {
            'PTS': 1, 'REB': 1, 'AST': 2, 'BLK': 4, 'STL': 4, 'TO': -2,
            'FGM': 2, 'FGA': -1, '3PM': 1}}
        self.mapping = [{'Year': '2027', 'Scoring Period': str(p), 'Week': str(w)}
                        for p, w in [(2, 1), (7, 2), (8, 2), (9, 3)]]

    def game(self, period, **changes):
        return {'Year': '2027', 'Scoring Period': str(period), 'Player ID': '1',
                'Team ID': '1', 'Player Slot': 'PG', 'MIN': '20', 'FPTS': '50',
                'PTS': '10', 'REB': '5', 'AST': '8', 'BLK': '4', 'STL': '8',
                'TO': '-6', 'FGM': '2', 'FGA': '-2', '3PM': '1', '3PA': '1', **changes}

    def test_actual_eligible_games_exact_week_and_team_with_weighted_totals(self):
        rows = [self.game(7), self.game(8, PTS='30', FGM='6', FGA='-18', **{'3PA': '9'}),
                self.game(2, PTS='999'), self.game(9, PTS='999'),
                self.game(7, **{'Player Slot': 'BE', 'Player ID': '2'}),
                self.game(8, **{'MIN': '0', 'Player ID': '3'}),
                self.game(7, **{'Team ID': '2', 'PTS': '999'})]
        rows.append(rows[0].copy())  # Repeated export records are not another NBA game.
        stats = lineup_week_stats(rows, self.mapping, self.calendar)
        result = stats[(2, 1, 1)]
        self.assertEqual(result['gamesPlayed'], 2)
        self.assertEqual(result['perGame'], {'PTS': 20, 'REB': 5, 'AST': 4, 'BLK': 1, 'STL': 2, 'TO': 3})
        self.assertEqual([result['totals'][k] for k in ('FGM', 'FGA', '3PM', '3PA')], [4, 20, 2, 10])
        self.assertEqual(result['shooting'], {'FG%': 20, '3P%': 20})
        self.assertNotIn((2, 1, 2), stats)
        self.assertNotIn((2, 1, 3), stats)

    def test_missing_stats_propagate_unknown_instead_of_partial_total_or_zero(self):
        rows = [self.game(7), self.game(8, **{'3PA': '', 'AST': ''})]
        result = lineup_week_stats(rows, self.mapping, self.calendar)[(2, 1, 1)]
        self.assertEqual(result['gamesPlayed'], 2)
        self.assertIsNone(result['totals']['3PA'])
        self.assertIsNone(result['shooting']['3P%'])
        self.assertIsNone(result['perGame']['AST'])
        self.assertEqual(result['totals']['3PM'], 2)

    def test_zero_attempts_and_no_games_are_safe(self):
        row = self.game(7, FGM='0', FGA='0', **{'3PM': '0', '3PA': '0'})
        result = lineup_week_stats([row], self.mapping, self.calendar)[(2, 1, 1)]
        self.assertEqual(result['shooting'], {'FG%': None, '3P%': None})
        self.assertEqual(result['gamesPlayed'], 1)
        self.assertEqual(lineup_week_stats([], self.mapping, self.calendar), {})

    def test_enrichment_never_changes_selected_lineup_or_weekly_fpts(self):
        team = {'teamId': 1, 'teamName': 'Historical name', 'logo': 'logos/Old.png'}
        rows = [{'Player ID': '1', 'Player Name': 'One', 'Team ID': '1', 'FPTS': '184.5', 'Position': 'PG'}]
        lineup = choose_lineup(rows, ['PG'], {1: team})
        before = lineup[0].copy()
        lineup[0]['weeklyStats'] = lineup_week_stats([self.game(7)], self.mapping, self.calendar)[(2, 1, 1)]
        self.assertEqual({k: v for k, v in lineup[0].items() if k != 'weeklyStats'}, before)
        self.assertEqual(lineup[0]['points'], 184.5)
        self.assertEqual(lineup[0]['team'], team)
        historical = team_info({'Team ID': '1', 'Team Name': 'Historical name'}, {
            'team_logo_paths': {'Historical name': 'assets/logos/Old.png'},
            'default_logo_path': 'assets/logos/Default.png', 'team_colors': {}})
        self.assertEqual(historical['logo'], 'logos/Old.png')
        self.assertEqual(team_info({'Team ID': '1', 'Team Name': 'Unknown'}, {
            'team_logo_paths': {}, 'default_logo_path': 'assets/logos/Default.png',
            'team_colors': {}})['logo'], 'logos/Default.png')


if __name__ == '__main__':
    unittest.main()
