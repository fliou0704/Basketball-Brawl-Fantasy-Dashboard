"""Contracts for daily eligibility, matchup mapping, and weekly parity."""

import unittest

import pandas as pd

from dataUpdateSafety import DataValidationError, PLAYER_DAILY_KEY
from playerDailyAggregation import (
    DAILY_STATS,
    POSITION_COLUMNS,
    aggregate_daily_to_weekly,
    build_scoring_period_map,
    eligible_position_fields,
    eligible_position_values,
    load_scoring_period_map,
    load_season_metadata,
    validate_scoring_period_map,
)


class PlayerDailyEligibilityTests(unittest.TestCase):
    def test_only_real_nba_positions_are_retained_in_espn_order(self):
        slots = ["PG", "SG", "G", "SG/SF", "G/F", "UT", "BE", "IR"]
        self.assertEqual(eligible_position_values(slots), ["PG", "SG"])
        self.assertEqual(
            eligible_position_fields(slots),
            {"Position": "PG", "Position2": "SG", "Position3": None},
        )

    def test_more_than_three_real_positions_is_rejected_not_truncated(self):
        with self.assertRaisesRegex(DataValidationError, "supports only three"):
            eligible_position_values(["PG", "SG", "SF", "PF"])

    def test_backfilled_positions_exactly_match_existing_weekly_semantics(self):
        daily = pd.read_csv("data/playerDailyData.csv")
        weekly = pd.read_csv("data/playerMatchupData.csv")
        expected = weekly.drop_duplicates(["Year", "Player ID"])[
            ["Year", "Player ID", *POSITION_COLUMNS]
        ]
        actual = daily.drop_duplicates(["Year", "Player ID"])[
            ["Year", "Player ID", *POSITION_COLUMNS]
        ]
        compared = expected.merge(actual, on=["Year", "Player ID"], suffixes=("_weekly", "_daily"))
        for column in POSITION_COLUMNS:
            self.assertTrue(
                compared[f"{column}_weekly"].fillna("").equals(compared[f"{column}_daily"].fillna(""))
            )
        self.assertEqual(actual[list(POSITION_COLUMNS)].notna().sum(axis=1).max(), 3)
        self.assertFalse(actual[list(POSITION_COLUMNS)].isna().all(axis=1).any())


class ScoringPeriodMapTests(unittest.TestCase):
    def test_generated_reference_matches_committed_reference(self):
        generated = build_scoring_period_map(load_season_metadata())
        stored = load_scoring_period_map()
        pd.testing.assert_frame_equal(generated, stored)
        self.assertEqual(stored.duplicated(["Year", "Scoring Period"]).sum(), 0)

    def test_every_historical_daily_period_maps_exactly_once(self):
        daily = pd.read_csv("data/playerDailyData.csv")
        mapping = load_scoring_period_map()
        validate_scoring_period_map(mapping, daily)
        coverage = daily[["Year", "Scoring Period"]].drop_duplicates().merge(
            mapping, on=["Year", "Scoring Period"], validate="one_to_one"
        )
        self.assertEqual(len(coverage), len(daily[["Year", "Scoring Period"]].drop_duplicates()))

    def test_representative_regular_and_playoff_periods(self):
        mapping = load_scoring_period_map().set_index(["Year", "Scoring Period"])["Week"]
        self.assertEqual(mapping.loc[(2025, 1)], 1)
        self.assertEqual(mapping.loc[(2025, 140)], 20)
        self.assertEqual(mapping.loc[(2023, 175)], 24)


class DailyWeeklyParityTests(unittest.TestCase):
    def test_daily_keys_remain_unique(self):
        daily = pd.read_csv("data/playerDailyData.csv")
        self.assertEqual(daily.duplicated(PLAYER_DAILY_KEY).sum(), 0)
        self.assertEqual(len(daily), 39832)

    def test_finalized_2023_through_2025_exactly_reproduce_weekly_performance(self):
        daily = pd.read_csv("data/playerDailyData.csv")
        matchup = pd.read_csv("data/playerMatchupData.csv")
        derived = aggregate_daily_to_weekly(
            daily,
            load_scoring_period_map(),
            load_season_metadata(),
            active_only=True,
        )
        years = [2023, 2024, 2025]
        derived = derived[derived["Year"].isin(years)]
        matchup = matchup[matchup["Year"].isin(years)]
        key = ["Year", "Week", "Team ID", "Player ID"]
        self.assertEqual(len(derived), 9481)
        self.assertEqual(set(map(tuple, derived[key].to_numpy())), set(map(tuple, matchup[key].to_numpy())))
        compared = matchup.merge(derived, on=key, suffixes=("_weekly", "_daily"), validate="one_to_one")
        for stat in DAILY_STATS:
            pd.testing.assert_series_equal(
                compared[f"{stat}_weekly"], compared[f"{stat}_daily"], check_names=False
            )

    def test_all_played_variant_retains_bench_and_ir_rows(self):
        daily = pd.read_csv("data/playerDailyData.csv")
        active = aggregate_daily_to_weekly(
            daily, load_scoring_period_map(), load_season_metadata(), active_only=True
        )
        all_played = aggregate_daily_to_weekly(
            daily, load_scoring_period_map(), load_season_metadata(), active_only=False
        )
        self.assertGreater(len(all_played), len(active))
        self.assertTrue((all_played["GP"] >= all_played["Fantasy Starts"]).all())


if __name__ == "__main__":
    unittest.main()
