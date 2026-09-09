"""Offline safety and normalization tests for the hybrid Activity updater."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from activityDataUpdater import (
    SCHEMA, TRADE_COLUMNS, build_automated_rows, build_draft_rows,
    build_manual_trade_rows, build_not_kept_rows, fetch_transactions,
    prepare_activity_update, write_activity_update,
)
from dataUpdateSafety import DataValidationError

TEAMS = {1: "One", 2: "Two"}
PLAYERS = {value: f"Player {value}" for value in (101, 202, 303, 404, 505, 606, 707, 808)}


def tx(identifier, kind, status="EXECUTED", execution="PROCESS", pending=False, items=None, stamp=1730433600000):
    return {"id": identifier, "type": kind, "status": status, "executionType": execution,
            "isPending": pending, "processDate": stamp, "proposedDate": stamp,
            "items": items or []}


def add(player=101, team=1): return {"type": "ADD", "playerId": player, "toTeamId": team}
def drop(player=202, team=1): return {"type": "DROP", "playerId": player, "fromTeamId": team}


def activity_row(index, year, action="DRAFTED", player=101, team=1, date="2024-10-01", time="12:00"):
    return {"Unnamed: 0": index, "Year": year, "Date": date, "Time": time,
            "Team Name": TEAMS[team], "Asset": PLAYERS[player], "Action": action,
            "Team ID": team, "Player ID": player}


class Response:
    def __init__(self, transactions): self.transactions = transactions
    def raise_for_status(self): pass
    def json(self): return {"transactions": self.transactions}


class ActivityUpdaterTests(unittest.TestCase):
    def test_executed_waiver_add_and_associated_drop(self):
        rows = build_automated_rows(2026, [tx("w", "WAIVER", items=[add(), drop()])], TEAMS, PLAYERS)
        self.assertEqual(rows.Action.tolist(), ["WAIVER ADDED", "DROPPED"])
        self.assertEqual(set(rows["Team ID"]), {1})

    def test_failed_canceled_and_pending_waivers_are_excluded(self):
        transactions = [
            tx("failed", "WAIVER", "FAILED_ROSTERLIMIT", items=[add()]),
            tx("canceled", "WAIVER", "CANCELED", "CANCEL", items=[add()]),
            tx("pending", "WAIVER", "PENDING", "EXECUTE", True, [add()]),
            tx("odd", "WAIVER", "EXECUTED", "PROCESS", True, [add()]),
            tx("wrong-execution", "WAIVER", "EXECUTED", "EXECUTE", False, [add()]),
        ]
        self.assertTrue(build_automated_rows(2026, transactions, TEAMS, PLAYERS).empty)

    def test_free_agent_add_and_drop(self):
        rows = build_automated_rows(2026, [tx("fa", "FREEAGENT", execution="EXECUTE", items=[add(), drop()])], TEAMS, PLAYERS)
        self.assertEqual(rows.Action.tolist(), ["FA ADDED", "DROPPED"])

    def test_fetch_includes_period_zero_and_post_final_periods(self):
        league = SimpleNamespace(scoringPeriodId=4, finalScoringPeriod=2,
            espn_request=SimpleNamespace(LEAGUE_ENDPOINT="endpoint", cookies={}))
        seen = []
        def requester(url, params, cookies, timeout):
            period = params["scoringPeriodId"]; seen.append(period)
            rows = [tx(f"t{period}", "WAIVER", items=[add()])] if period in {0, 4} else []
            return Response(rows)
        transactions, _ = fetch_transactions(league, requester)
        self.assertEqual(seen, [0, 1, 2, 3, 4])
        self.assertEqual({item["id"] for item in transactions}, {"t0", "t4"})

    def test_draft_and_keeper_generation(self):
        picks = [
            SimpleNamespace(playerId=101, playerName="Alpha", team=SimpleNamespace(team_id=1), keeper_status=True),
            SimpleNamespace(playerId=202, playerName="Bravo", team=SimpleNamespace(team_id=2), keeper_status=False),
        ]
        league = SimpleNamespace(draft=picks)
        rows = build_draft_rows(2026, league, [tx("draft", "DRAFT")], TEAMS, PLAYERS)
        self.assertEqual(rows.Action.tolist(), ["KEEPER", "DRAFTED"])

    def test_manual_trade_generates_paired_rows(self):
        manual = pd.DataFrame([[2026, "2025-11-01", "19:30", 101, 1, 2, "trade-1"]], columns=TRADE_COLUMNS)
        rows = build_manual_trade_rows(2026, manual, TEAMS, PLAYERS)
        self.assertEqual(rows.Action.tolist(), ["TRADED", "RECEIVED"])
        self.assertEqual(rows["Team ID"].tolist(), [1, 2])

    def test_unresolved_espn_trade_never_creates_activity(self):
        trade = tx("trade", "TRADE_ACCEPT", execution="EXECUTE", items=[])
        self.assertTrue(build_automated_rows(2026, [trade], TEAMS, PLAYERS).empty)

    def test_executed_trade_automates_drop_but_not_player_movements(self):
        trade = tx("trade", "TRADE_ACCEPT", execution="PROCESS", items=[
            {"type": "TRADE", "playerId": 101, "fromTeamId": 1, "toTeamId": 2},
            drop(202, 1),
        ])
        rows = build_automated_rows(2026, [trade], TEAMS, PLAYERS)
        self.assertEqual(rows.Action.tolist(), ["DROPPED"])
        self.assertEqual(rows["Player ID"].tolist(), [202])

    def test_not_kept_is_deterministic(self):
        existing = pd.DataFrame([activity_row(0, 2025, "DRAFTED", 101, 1)])
        draft = pd.DataFrame([
            {k: v for k, v in activity_row(1, 2026, "KEEPER", 202, 2, "2025-10-15", "19:00").items() if k != "Unnamed: 0"}
        ])
        first = build_not_kept_rows(existing, 2026, draft)
        second = build_not_kept_rows(existing, 2026, draft)
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(first.iloc[0]["Action"], "NOT KEPT")

    def test_every_owned_latest_action_can_generate_not_kept(self):
        owned_actions = ["DRAFTED", "KEEPER", "WAIVER ADDED", "FA ADDED", "RECEIVED"]
        for offset, action in enumerate(owned_actions):
            with self.subTest(action=action):
                player = (101, 202, 303, 404, 505)[offset]
                existing = pd.DataFrame([activity_row(0, 2025, action, player, 1)])
                draft = pd.DataFrame([{k: v for k, v in activity_row(
                    1, 2026, "KEEPER", 808, 2, "2025-10-15", "19:00"
                ).items() if k != "Unnamed: 0"}])
                rows = build_not_kept_rows(existing, 2026, draft)
                self.assertEqual(rows["Player ID"].tolist(), [player])

    def test_unowned_latest_actions_do_not_generate_not_kept(self):
        for action in ("DROPPED", "TRADED", "NOT KEPT"):
            with self.subTest(action=action):
                existing = pd.DataFrame([activity_row(0, 2025, action, 101, 1)])
                draft = pd.DataFrame([{k: v for k, v in activity_row(
                    1, 2026, "KEEPER", 808, 2, "2025-10-15", "19:00"
                ).items() if k != "Unnamed: 0"}])
                self.assertTrue(build_not_kept_rows(existing, 2026, draft).empty)

    def test_player_kept_by_same_team_does_not_generate_not_kept(self):
        existing = pd.DataFrame([activity_row(0, 2025, "WAIVER ADDED", 101, 1)])
        draft = pd.DataFrame([{k: v for k, v in activity_row(
            1, 2026, "KEEPER", 101, 1, "2025-10-15", "19:00"
        ).items() if k != "Unnamed: 0"}])
        self.assertTrue(build_not_kept_rows(existing, 2026, draft).empty)

    def test_trade_changes_end_of_season_owner_for_not_kept(self):
        existing = pd.DataFrame([
            activity_row(0, 2025, "DRAFTED", 101, 1, time="10:00"),
            activity_row(1, 2025, "TRADED", 101, 1, time="11:00"),
            activity_row(2, 2025, "RECEIVED", 101, 2, time="11:00"),
        ])
        draft = pd.DataFrame([{k: v for k, v in activity_row(
            3, 2026, "KEEPER", 808, 1, "2025-10-15", "19:00"
        ).items() if k != "Unnamed: 0"}])
        rows = build_not_kept_rows(existing, 2026, draft)
        self.assertEqual(rows[["Team ID", "Player ID"]].values.tolist(), [[2, 101]])

    def test_current_partition_replacement_preserves_history_and_is_idempotent(self):
        history = pd.DataFrame([activity_row(0, 2025)])
        current = pd.DataFrame([{k: v for k, v in activity_row(1, 2026, "WAIVER ADDED", 202, 2).items() if k != "Unnamed: 0"}])
        candidate = prepare_activity_update(history, current, 2026)
        pd.testing.assert_frame_equal(candidate.iloc[:1].reset_index(drop=True), history)
        rerun = prepare_activity_update(candidate, current, 2026)
        pd.testing.assert_frame_equal(candidate, rerun)

    def test_validation_failure_leaves_csv_byte_for_byte_unchanged(self):
        existing = pd.DataFrame([activity_row(0, 2025)])
        duplicate = {k: v for k, v in activity_row(1, 2026).items() if k != "Unnamed: 0"}
        current = pd.DataFrame([duplicate, duplicate])
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "activity.csv"
            backup = Path(directory) / "backup.csv"
            existing.to_csv(destination, index=False)
            original = destination.read_bytes()
            with self.assertRaises(DataValidationError):
                write_activity_update(existing, current, 2026, destination, backup)
            self.assertEqual(destination.read_bytes(), original)
            self.assertFalse(backup.exists())


if __name__ == "__main__":
    unittest.main()
