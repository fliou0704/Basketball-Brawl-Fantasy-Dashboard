import json
import tempfile
import unittest
from pathlib import Path
from generate_scoreboard import attach_recaps


class RecapLifecycleTests(unittest.TestCase):
    def test_selected_season_week_recaps_only_for_played_completed_matchups(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = {'seasons': []}
            for year in (2023, 2027, 2028):
                season = {'season': year, 'weeks': []}
                payload['seasons'].append(season)
                for week, state, matches in [(1, 'final', [{'status': 'final'}]),
                                              (2, 'current', [{'status': 'current'}]),
                                              (3, 'future', [{'status': 'future'}]),
                                              (4, 'final', [])]:
                    season['weeks'].append({'week': week, 'state': state, 'matchups': matches})
                if year != 2028:
                    (root / str(year)).mkdir()
                    (root / str(year) / 'weekly-recap.json').write_text(json.dumps(
                        {'data': {str(w): {'week': w, 'season': year} for w in range(1, 5)}}))
            attach_recaps(payload, root)
            for season in payload['seasons']:
                weeks = season['weeks']
                self.assertEqual(weeks[0]['recap'], None if season['season'] == 2028 else
                                 {'week': 1, 'season': season['season']})
                self.assertTrue(all(w['recap'] is None for w in weeks[1:]))
