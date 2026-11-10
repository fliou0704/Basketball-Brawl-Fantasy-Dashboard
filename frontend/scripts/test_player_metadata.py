import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from generate_player_metadata import build


class PlayerMetadataExportTests(unittest.TestCase):
    def test_exports_espn_id_keyed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "data", root / "public"
            source.mkdir()
            pd.DataFrame([{
                "ESPN Player ID": 1966,
                "Full Name": "LeBron James",
                "Jersey Number": "23",
                "Birth City": None,
            }]).to_csv(source / "playerMetadata.csv", index=False)
            payload = build(source, output)
            self.assertEqual(payload["players"]["1966"]["Full Name"], "LeBron James")
            self.assertEqual(payload["players"]["1966"]["Jersey Number"], "23")
            self.assertIsNone(payload["players"]["1966"]["Birth City"])
            self.assertEqual(json.loads((output / "player-metadata.json").read_text()), payload)


if __name__ == "__main__":
    unittest.main()
