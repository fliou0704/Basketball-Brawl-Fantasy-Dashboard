import json
import os
from pathlib import Path
import tempfile
import unittest

from export_fingerprint import fingerprint, differs
from build_homepage import ROOT


class ExportFingerprintTests(unittest.TestCase):
    def test_unchanged_exports_skip_and_correction_deploys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'players.json'
            path.write_text(json.dumps({'points': 10}))
            first = fingerprint(root)
            self.assertFalse(differs(first, {'fingerprint': first}))
            (root / 'pipeline.json').write_text('ignored marker')
            self.assertEqual(first, fingerprint(root))
            path.write_text(json.dumps({'points': 11}))
            self.assertTrue(differs(fingerprint(root), {'fingerprint': first}))
            self.assertTrue(differs(fingerprint(root), {}))

    def test_current_snapshot_rosters_and_played_game_logs_reach_exports(self):
        source = Path(os.environ.get('TEAM_STATS_TEST_SOURCE', ROOT / 'data'))
        current = source / 'currentLeague.json'
        if not current.exists():
            self.skipTest('legacy source has no current-season snapshot')
        output = Path(os.environ.get('FRONTEND_TEST_OUTPUT', ROOT / 'frontend/public/data'))
        snapshot = json.loads(current.read_text())
        manifest = json.loads((output / 'team-stats.json').read_text())
        self.assertEqual(manifest['years'][0], snapshot['season'])
        for team in snapshot['teams']:
            payload = json.loads((output / 'team-stats' / f"{team['teamId']}.json").read_text())
            roster = payload['seasons'][str(snapshot['season'])]['roster']
            self.assertEqual({p['playerId'] for p in roster if p['current']},
                             {p['playerId'] for p in team['roster']})
        import pandas as pd
        daily = pd.read_csv(source / 'playerDailyData.csv')
        recent = daily[(daily['Year'] == snapshot['season']) & (daily['MIN'] > 0)]
        for _, row in recent.iterrows():
            player = json.loads((output / 'players' / f"{int(row['Player ID'])}.json").read_text())
            game = next(g for g in player['gameLog'] if g['date'] == row['Date'])
            self.assertEqual(game['FPTS'], row['FPTS'])
