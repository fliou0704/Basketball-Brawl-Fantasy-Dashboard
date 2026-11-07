import unittest,tempfile,json,csv
from pathlib import Path
from generate_top150 import build_archive
class ArchiveRankingTests(unittest.TestCase):
 def fixture(self,path):
  fields=['Year','Player ID','Player Name','Games Played','Total FPTS','Latest Observed NBA Team ID','Eligible Slot IDs']
  with (path/'playerSeasonStats.csv').open('w')as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow(dict(zip(fields,[2027,10,'Player',1,-2,1,'[0,1]'])))
  (path/'playerGameLogs.report.json').write_text(json.dumps({'csvSHA256':'a','seasonReports':{'2027':{'players':1,'rows':1,'teamGames':{'1':1},'throughDate':'2026-10-20'}}}))
  (path/'player-static').mkdir();(path/'player-static/index.json').write_text(json.dumps({'archiveSHA256':'a','updatedAt':'2026-10-21T00:00:00Z'}))
 def test_archive_context_free_agent_and_no_games_owner(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);self.fixture(p);(p/'currentLeague.json').write_text(json.dumps({'season':2027,'teams':[{'teamId':1,'teamName':'One','roster':[{'playerId':11,'name':'No games','slot':'IR'}]}]}))
   build_archive(p,p/'out');season=json.loads((p/'out/top150/2027.json').read_text());players=season['players']
   self.assertEqual(players[0]['teamId'],0);self.assertEqual(players[0]['playerSlot'],'FA');self.assertEqual(players[0]['fpts'],-2)
   self.assertIsNone(players[1]['fpts']);self.assertEqual(players[1]['gp'],0);self.assertEqual(players[1]['playerSlot'],'IR')
 def test_stale_or_incomplete_summary_rejected(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);self.fixture(p)
   report=json.loads((p/'playerGameLogs.report.json').read_text());report['seasonReports']['2027']['rows']=2;(p/'playerGameLogs.report.json').write_text(json.dumps(report))
   with self.assertRaises(ValueError):build_archive(p,p/'out')
