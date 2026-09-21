import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from dataUpdateSafety import DataValidationError, player_metadata_by_id
from playerMetadataUpdater import (
    METADATA_COLUMNS,
    discover_player_ids,
    update_player_metadata,
    validate_metadata,
)


NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def profile(player_id, active=True, fetched_at=NOW, **overrides):
    row = {column: None for column in METADATA_COLUMNS}
    row.update({
        "ESPN Player ID": player_id,
        "Full Name": f"Player {player_id}",
        "First Name": "Player",
        "Last Name": str(player_id),
        "Headshot URL": f"https://example.test/{player_id}.png",
        "Height Inches": 78,
        "Weight Pounds": 210,
        "Birth Date": "2000-01-01",
        "Birth Country": "USA",
        "NBA Position Name": "Guard",
        "NBA Position Abbreviation": "G",
        "Active": active,
        "Status": "active" if active else "inactive",
        "Team Relationship": "current" if active else "last-known",
        "Profile Source": "espn-core-athlete",
        "Profile Fetched At": fetched_at.isoformat().replace("+00:00", "Z"),
    })
    row.update(overrides)
    return row


class PlayerMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        pd.DataFrame({"Player ID": [1966, 3989]}).to_csv(self.directory / "playerDailyData.csv", index=False)
        pd.DataFrame({"Player ID": [1966, 5104157]}).to_csv(self.directory / "playerMatchupData.csv", index=False)
        pd.DataFrame({"Player ID": [3989.0, None]}).to_csv(self.directory / "activityData.csv", index=False)
        self.output = self.directory / "playerMetadata.csv"

    def tearDown(self):
        self.temp.cleanup()

    def write(self, *rows):
        pd.DataFrame(rows, columns=METADATA_COLUMNS).to_csv(self.output, index=False)

    def test_discovers_historical_union(self):
        self.assertEqual(discover_player_ids(self.directory), {1966, 3989, 5104157})

    def test_uniqueness_and_integer_join_helper(self):
        frame = pd.DataFrame([profile(1966)], columns=METADATA_COLUMNS)
        self.assertEqual(player_metadata_by_id(frame)[1966]["Full Name"], "Player 1966")
        with self.assertRaisesRegex(DataValidationError, "duplicate"):
            validate_metadata(pd.concat([frame, frame], ignore_index=True))

    def test_new_players_are_fetched_while_fresh_existing_player_is_not(self):
        self.write(profile(1966))
        fetched = []
        def fetch(player_id, moment):
            fetched.append(player_id)
            return profile(player_id, fetched_at=moment)
        report = update_player_metadata(self.directory, self.output, fetch, NOW)
        self.assertEqual(fetched, [3989, 5104157])
        self.assertEqual(report.records, 3)

    def test_active_player_refreshes_when_due(self):
        self.write(profile(1966, fetched_at=NOW - timedelta(days=8)), profile(3989, active=False), profile(5104157))
        fetched = []
        update_player_metadata(self.directory, self.output, lambda pid, now: fetched.append(pid) or profile(pid, fetched_at=now), NOW)
        self.assertEqual(fetched, [1966])

    def test_inactive_historical_player_is_preserved(self):
        old = profile(3989, active=False, **{"NBA Team Name": "Boston Celtics"})
        self.write(profile(1966), old, profile(5104157))
        update_player_metadata(self.directory, self.output, lambda *_: self.fail("inactive player fetched"), NOW)
        saved = player_metadata_by_id(pd.read_csv(self.output))
        self.assertEqual(saved[3989]["NBA Team Name"], "Boston Celtics")
        self.assertEqual(saved[3989]["Team Relationship"], "last-known")

    def test_failed_refresh_preserves_cached_record(self):
        old = profile(1966, fetched_at=NOW - timedelta(days=8), **{"Headshot URL": "kept"})
        self.write(old, profile(3989, active=False), profile(5104157))
        report = update_player_metadata(self.directory, self.output, lambda *_: (_ for _ in ()).throw(RuntimeError("temporary")), NOW)
        saved = player_metadata_by_id(pd.read_csv(self.output))
        self.assertEqual(saved[1966]["Headshot URL"], "kept")
        self.assertIn(1966, report.unresolved)

    def test_null_refresh_does_not_erase_established_metadata(self):
        old = profile(1966, fetched_at=NOW - timedelta(days=8), **{"Birth City": "Akron"})
        self.write(old, profile(3989, active=False), profile(5104157))
        update_player_metadata(self.directory, self.output, lambda pid, now: profile(pid, fetched_at=now, **{"Birth City": None}), NOW)
        saved = player_metadata_by_id(pd.read_csv(self.output))
        self.assertEqual(saved[1966]["Birth City"], "Akron")


if __name__ == "__main__":
    unittest.main()
