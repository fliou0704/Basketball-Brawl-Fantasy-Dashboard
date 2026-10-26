"""Actual Oct 26 failure, with names/owners replaced and credentials excluded."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import pandas as pd

from dataUpdateSafety import (DataValidationError, LEAGUE_KEY, PLAYER_DAILY_KEY,
    order_generated_csv_columns, require_csv_schema, validate_league_data,
    validate_player_daily_data)
from leagueDataUpdater import update_league_data, prepare_league_update
from nearLiveSafety import replace_partitions, changes
from nearLiveUpdater import current_calendar, live_rosters

FIXTURES = Path(__file__).parent / 'fixtures/updater_2026_10_26'


def fixture(name):
    return pd.read_csv(FIXTURES / (name + '.csv'))


class October26RegressionTests(unittest.TestCase):
    def test_exact_first_week_order_failure_and_explicit_producer_order(self):
        incoming = fixture('league_week1')
        old = incoming.assign(Year=2026)
        columns = list(incoming)
        columns[7:12] = ['Win', 'Loss', 'Home/Away', 'Points For', 'Points Against']
        wrong = incoming[columns]
        with self.assertRaisesRegex(DataValidationError, 'order differences=.*Home/Away'):
            prepare_league_update(old, wrong)
        generated = order_generated_csv_columns(old, wrong, 'league builder')
        result = prepare_league_update(old, generated)
        pd.testing.assert_frame_equal(result.iloc[:len(old)], old)
        pd.testing.assert_frame_equal(result.iloc[len(old):].reset_index(drop=True), incoming)

    def test_missing_extra_and_duplicate_columns_are_never_dropped(self):
        old = fixture('league_week1')
        for wrong in [old.drop(columns='Win'), old.assign(Unrecognized=1),
                      pd.concat([old, old[['Win']]], axis=1)]:
            with self.subTest(columns=list(wrong)):
                with self.assertRaisesRegex(DataValidationError, 'columns='):
                    order_generated_csv_columns(old, wrong, 'league builder')
                with self.assertRaises(DataValidationError):
                    require_csv_schema(old, wrong, 'persist')

    def test_identical_schema_and_nulls_are_preserved(self):
        old = fixture('daily_before')
        require_csv_schema(old, old.copy(), 'daily')
        result = order_generated_csv_columns(old, old, 'daily')
        pd.testing.assert_frame_equal(old, result)
        self.assertTrue(result.Position2.isna().any())

    def test_real_periods_1_through_7_corrections_empty_day_and_idempotence(self):
        old, incoming = fixture('daily_before'), fixture('daily_incoming')
        historical = old.assign(Year=2026, Date=old.Date.str.replace('2026', '2025'))
        existing = pd.concat([historical, old], ignore_index=True)
        authorized = {(2027, p) for p in range(1, 8)}
        self.assertEqual(len(incoming), 388)
        self.assertEqual(set(incoming['Scoring Period']), set(range(1, 7)))
        result = replace_partitions(existing, incoming, authorized, 'Scoring Period',
                                    PLAYER_DAILY_KEY, validate_player_daily_data)
        self.assertEqual(changes(existing, result, PLAYER_DAILY_KEY),
                         dict(inserted=0, removed=0, corrected=8))
        pd.testing.assert_frame_equal(result.iloc[:len(historical)], historical)
        repeated = replace_partitions(result, incoming, authorized, 'Scoring Period',
                                       PLAYER_DAILY_KEY, validate_player_daily_data)
        pd.testing.assert_frame_equal(result, repeated)
        expected = {(2, 2, 4066320): {'FPTS', 'STL'}, (4, 17, 4432639): {'FPTS', 'STL'},
            (5, 7, 4591725): {'FPTS', 'AST'}, (5, 13, 4066383): {'FPTS', 'STL'},
            (5, 13, 4437244): {'FPTS', 'STL'}, (5, 17, 4433287): {'FPTS', 'REB', 'TO'},
            (5, 17, 4066328): {'BLK', 'STL'}, (5, 8, 3064514): {'FPTS', 'TO', 'FGA'}}
        before, after = old.set_index(PLAYER_DAILY_KEY), incoming.set_index(PLAYER_DAILY_KEY)
        equal = before.eq(after) | (before.isna() & after.isna())
        actual = {k[1:]: set(equal.columns[~equal.loc[k]]) for k in equal.index[~equal.all(axis=1)]}
        self.assertEqual(actual, expected)
        with self.assertRaises(DataValidationError):
            replace_partitions(existing, incoming.assign(Year=2026), authorized,
                               'Scoring Period', PLAYER_DAILY_KEY, validate_player_daily_data)

    def test_actual_first_completed_week_through_production_builder(self):
        expected = fixture('league_week1')
        # A completed prior season, no rows for 2027: the failing production path.
        historical = expected.assign(Year=2026)
        teams = {int(r['Team ID']): NS(team_id=int(r['Team ID']), team_name=r['Team Name'],
            team_abbrev=r['Team Abbreviation'], owners=[{'firstName': r['Team Owner']}])
            for r in expected.to_dict('records')}
        boxes = [NS(home_team=teams[int(r['Team ID'])], away_team=teams[int(r['Opponent Team ID'])],
            home_final_score=r['Points For'], away_final_score=r['Points Against'],
            winner='HOME' if r['Win'] else 'AWAY') for r in expected.to_dict('records') if r['Home/Away']=='Home']
        league = NS(currentMatchupPeriod=2, settings=NS(matchup_periods={w: [] for w in range(1, 24)}, reg_season_count=20),
                    scoreboard=lambda week: boxes)
        factory = lambda **kwargs: (league if kwargs["year"] == 2027 else
            NS(settings=NS(matchup_periods={1: []})))
        with tempfile.TemporaryDirectory() as tmp, patch('leagueDataUpdater.require_espn_credentials', return_value=('', '')):
            path = Path(tmp) / 'league.csv'
            historical.to_csv(path, index=False)
            self.assertTrue(update_league_data(path, 2027, factory))
            result = pd.read_csv(path)
            pd.testing.assert_frame_equal(result.iloc[:len(historical)], historical, check_dtype=False)
            pd.testing.assert_frame_equal(result[result.Year==2027].reset_index(drop=True), expected, check_dtype=False)
            saved = path.read_bytes()
            self.assertFalse(update_league_data(path, 2027, factory, {2027: 1}))
            self.assertEqual(path.read_bytes(), saved)

    def test_current_week_comes_from_status_before_first_player_game(self):
        daily = fixture('daily_before')
        teams = [NS(team_id=1, team_name='One', team_abbrev='ONE', owners=[{'firstName':'Owner'}])]
        raw = {'schedule': [{'id': 1, 'matchupPeriodId': 1,
                'home': {'teamId': 1, 'pointsByScoringPeriod': {'6': 10}}}],
            'settings': {'rosterSettings': {'lineupSlotCounts': {'0': 1}},
                'scheduleSettings': {'matchupPeriodCount': 20, 'playoffTeamCount': 6},
                'scoringSettings': {'scoringItems': []}}, 'status': {'firstScoringPeriod': 1}}
        league = NS(year=2027, currentMatchupPeriod=2, scoringPeriodId=7,
            finalScoringPeriod=170, teams=teams, espn_request=NS(league_get=lambda **kw: raw))
        calendar = current_calendar(league, daily, {'seasons': []})
        self.assertEqual([(w['week'],w['firstPeriod'],w['lastPeriod']) for w in calendar['weeks']],
                         [(1, 6, 6), (2, 7, 7)])
        self.assertFalse((daily['Scoring Period']==7).any())

    def test_player_first_week_builder_checks_and_orders_every_stat_field(self):
        from playerMatchupDataUpdater import update_playerMatchup_data
        expected = fixture('players_week1')
        old = expected.assign(Year=2026)
        stat_cols = list(expected.columns[10:])
        team_ids = list(expected['Team ID'].unique())
        def lineup(team_id):
            return [NS(name=r['Player Name'], playerId=r['Player ID'], points=r['FPTS'],
                eligibleSlots=[r[c] for c in ('Position','Position2','Position3') if pd.notna(r[c])] + ['UT'],
                points_breakdown={c:r[c] for c in reversed(stat_cols)})
                for r in expected[expected['Team ID']==team_id].to_dict('records')]
        boxes = [NS(home_team=NS(team_id=a,team_name=f'Fixture Team Name {a}'),
                    away_team=NS(team_id=b,team_name=f'Fixture Team Name {b}'),
                    home_lineup=lineup(a),away_lineup=lineup(b))
                 for a,b in zip(team_ids[::2],team_ids[1::2])]
        league = NS(currentMatchupPeriod=2,
            settings=NS(matchup_periods={w:[] for w in range(1,24)},reg_season_count=20),
            box_scores=lambda week: boxes)
        factory = lambda **kw: league if kw['year']==2027 else NS(settings=NS(matchup_periods={1:[]}))
        with tempfile.TemporaryDirectory() as tmp, patch('playerMatchupDataUpdater.require_espn_credentials',return_value=('', '')):
            path=Path(tmp)/'players.csv';old.to_csv(path,index=False)
            self.assertTrue(update_playerMatchup_data(path,2027,factory))
            result=pd.read_csv(path)
            self.assertEqual(list(result),list(old))
            pd.testing.assert_frame_equal(result[result.Year==2027].sort_values('Player ID').reset_index(drop=True),
                expected.sort_values('Player ID').reset_index(drop=True),check_dtype=False)
            saved=path.read_bytes()
            self.assertFalse(update_playerMatchup_data(path,2027,factory,{2027:1}))
            self.assertEqual(path.read_bytes(),saved)

    def test_reconciliation_window_spans_matchups_without_seven_day_week_assumption(self):
        old, incoming = fixture('daily_before'), fixture('daily_incoming')
        # Period 8 belongs to week 2; the correction window also covers week 1.
        first_game = incoming.iloc[:1].assign(**{'Scoring Period':8, 'Date':'2026-10-27'})
        fresh = pd.concat([incoming[incoming['Scoring Period']>=2], first_game],ignore_index=True)
        authorized = {(2027,p) for p in range(2,9)}
        result = replace_partitions(old,fresh,authorized,'Scoring Period',PLAYER_DAILY_KEY,validate_player_daily_data)
        self.assertEqual(changes(old,result,PLAYER_DAILY_KEY),dict(inserted=1,removed=0,corrected=8))
        pd.testing.assert_frame_equal(result[result['Scoring Period']==1].reset_index(drop=True),
                                     old[old['Scoring Period']==1].reset_index(drop=True))
