import unittest,tempfile,csv,json
from pathlib import Path
from playerGameLogs import STATS,COLUMNS,CollectionError
from playerSeasonStats import summaries,export
class SeasonStatsTests(unittest.TestCase):
 def row(self,gid=1,year=2027,points=0):return {'Year':str(year),'Game ID':str(gid),'Player ID':'5','Player Name':'Player','Date':'2026-10-20','Scoring Period':'1','NBA Team ID':'1','Opponent ID':'2','Eligible Slot IDs':'[0,1]','Source':'test','FPTS':str(points),**{s:str(1 if s=='GP' else 0)for s in STATS}}
 def test_actual_games_negative_zero_and_season_identity(self):
  rows=[self.row(1,points=0),self.row(2,points=-4),self.row(3,2026,9)];s=summaries(rows)
  self.assertEqual(s[1]['Games Played'],2);self.assertEqual(s[1]['Total FPTS'],-4);self.assertEqual(s[1]['FPTS/Game'],-2)
  self.assertEqual(len(s),2)
 def test_duplicate_and_missing_stat(self):
  with self.assertRaises(CollectionError):summaries([self.row(),self.row()])
  r=self.row();r['PTS']='nan'
  with self.assertRaises(CollectionError):summaries([r])
 def test_deterministic_input_order(self):self.assertEqual(summaries([self.row(2),self.row(1)]),summaries([self.row(1),self.row(2)]))
 def test_static_shard_and_noop(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d,'logs.csv');out=Path(d,'static');summary=Path(d,'summary.csv')
   with p.open('w')as f:
    w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerow(self.row())
   export(p,summary,out);before={str(x):x.read_bytes()for x in out.rglob('*.json')}
   export(p,summary,out);self.assertEqual(before,{str(x):x.read_bytes()for x in out.rglob('*.json')})
   shard=json.loads((out/'games/2027/05.json').read_text());self.assertEqual(len(shard['rows']),1)
 def test_corrupt_archive_marker_preserves_outputs(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d,'logs.csv');summary=Path(d,'summary.csv');summary.write_text('last-good')
   with p.open('w')as f:
    w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerow(self.row())
   p.with_suffix('.report.json').write_text('{"csvSHA256":"wrong"}')
   with self.assertRaises(CollectionError):export(p,summary,Path(d,'static'))
   self.assertEqual(summary.read_text(),'last-good')

class MaintenanceTests(unittest.TestCase):
 def test_weekly_window_refreshes_older_days(self):
  from unittest.mock import patch
  from datetime import datetime,timezone
  import playerGameLogs as p
  class Clock(datetime):
   @classmethod
   def now(cls,tz=None):return datetime(2026,11,6,tzinfo=timezone.utc)
  class Fake:
   def __init__(self):self.days={}
   def league(self,*a,**kw):return {'settings':{'scoringSettings':{'scoringItems':[]}}}
   def get(self,url,params=None,refresh=False):
    if params and 'dates'in params:self.days[params['dates']]=refresh
    return {'events':[]}
  fixture={'id':1,'regularSeason':True,'statsOfficial':True,'start':'2026-11-05T20:00:00+00:00'}
  for days,expected in [(3,False),(14,True)]:
   client=Fake()
   with patch.object(p,'datetime',Clock),patch.object(p,'normalize',return_value={'teams':[{'id':1}],'fixtures':[fixture]}):
    with self.assertRaises(CollectionError):p.collect(2027,client,'/tmp/test-archive.csv',True,correction_days=days)
   self.assertEqual(client.days['20261028'],expected)
 def test_no_game_maintenance_skips_collection(self):
  import playerGameLogs as p
  from unittest.mock import patch,Mock
  import contextlib,io
  with tempfile.TemporaryDirectory()as d:
   for fixtures,status in [([],'no_recent_games'),([{'date':p.datetime.now(p.timezone.utc).astimezone(p.NY).date().isoformat(),'statsOfficial':False}],'scheduled_not_final')]:
    output=io.StringIO();client=Mock();client.metrics={}
    with patch('sys.argv',['playerGameLogs.py','--seasons','2027','--maintenance','--output',d+'/logs.csv']),patch.object(p,'Client',return_value=client),patch.object(p,'normalize',return_value={'fixtures':fixtures}),patch.object(p,'collect')as collect,contextlib.redirect_stdout(output):p.main()
    collect.assert_not_called();self.assertEqual(json.loads(output.getvalue())['status'],status)

 def test_full_reconciliation_uses_independent_resumable_cache(self):
  import playerGameLogs as p
  from unittest.mock import patch,Mock
  import contextlib,io
  with tempfile.TemporaryDirectory()as d:
   result={'season':2027,'players':1,'games':1,'rows':1,'metrics':{},'elapsedSeconds':0}
   with patch('sys.argv',['playerGameLogs.py','--seasons','2027','--output',d+'/logs.csv','--cache',d+'/cache','--refresh','--full-reconcile','--reconciliation-id','audit-1']),patch.object(p,'Client')as client,patch.object(p,'collect',return_value=result)as collect,contextlib.redirect_stdout(io.StringIO()):p.main()
   self.assertEqual(client.call_args.args[0],Path(d+'/cache/full-audit-1'));self.assertFalse(collect.call_args.args[3])
