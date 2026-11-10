import copy,csv,io,json,tempfile,unittest
from pathlib import Path
from playerGameLogs import appearances,assemble,fantasy_games,parse_stats,reconcile,CollectionError,STATS,Client

class GameLogTests(unittest.TestCase):
 def row(self):return {'Year':2027,'Game ID':1,'Player ID':5,'Player Name':'Player','Date':'2026-10-20','Scoring Period':1,'NBA Team ID':1,'Opponent ID':2,**{s:0.0 for s in STATS},'GP':1.0}
 def fantasy(self,year=2027):return {'players':[{'player':{'id':5,'eligibleSlots':[0,1],'stats':[{'seasonId':year,'statSourceId':0,'statSplitTypeId':5,'scoringPeriodId':1,'externalId':'1','appliedTotal':0,'stats':{'42':1}}]}}]}
 def test_season_specific(self):self.assertEqual(fantasy_games(self.fantasy(2026),2027)[0],{})
 def test_zero_point_zero_minutes_included(self):self.assertEqual(len(assemble([self.row()],{}, {},{})[0]),1)
 def test_scoring_negative_fractional(self):
  r=self.row();r['TO']=2;r['PTS']=1.5
  self.assertEqual(assemble([r],{}, {},{'11':-2,'0':1})[0][0]['FPTS'],-2.5)
 def test_period_conflict(self):
  with self.assertRaises(CollectionError):assemble([self.row()],{(1,5):{'period':2,'points':0}}, {},{})
 def test_duplicate_rejected(self):
  with self.assertRaises(CollectionError):assemble([self.row(),self.row()],{}, {},{})
 def test_multiple_games_same_period(self):
  r=self.row();other=dict(r,**{'Game ID':2});self.assertEqual(len(assemble([r,other],{}, {},{})[0]),2)
 def test_mismatch_quarantined(self):
  with self.assertRaises(CollectionError):assemble([self.row()],{(1,5):{'period':1,'points':3}}, {},{})
 def test_debut_missing_fantasy_pool_fallback(self):
  rows,fallback=assemble([self.row()],{}, {},{});self.assertEqual(fallback,[[1,5]])
 def test_stable_output(self):
  r=self.row();other=dict(r,**{'Game ID':2});self.assertEqual(assemble([r,other],{}, {},{}),assemble([other,r],{}, {},{}))
 def test_reconciliation_correction_does_not_mutate(self):
  r=self.row();r['FPTS']=2;old={'Year':'2027','Player ID':'5','Scoring Period':'1','Date':'2026-10-20','MIN':'0','FPTS':'1'};before=dict(old)
  self.assertEqual(len(reconcile([r],[old])['differences']),1);self.assertEqual(old,before)
 def test_cache_resume_without_network(self):
  import hashlib
  with tempfile.TemporaryDirectory()as d:
   key=hashlib.sha256(json.dumps(['url',None,None],sort_keys=True).encode()).hexdigest();Path(d,key+'.json').write_text('{"ok":true}')
   c=Client.__new__(Client);c.cache=Path(d);self.assertEqual(c.get('url'),{'ok':True})
 def test_missing_fixture_period_uses_explicit_fantasy_game(self):
  r=self.row();r['Scoring Period']=None
  rows,_=assemble([r],{(1,5):{'period':4,'points':0}}, {},{})
  self.assertEqual(rows[0]['Scoring Period'],4)
 def test_unmapped_period_remains_unresolved(self):
  r=self.row();r['Scoring Period']=None
  self.assertIsNone(assemble([r],{}, {},{})[0][0]['Scoring Period'])
 def test_interrupted_collection_preserves_last_good_csv(self):
  from playerGameLogs import collect
  class Broken:
   def league(self,*args,**kwargs):raise CollectionError('source unavailable')
  with tempfile.TemporaryDirectory()as d:
   target=Path(d,'playerGameLogs.csv');target.write_bytes(b'last-good')
   with self.assertRaises(CollectionError):collect(2027,Broken(),str(target))
   self.assertEqual(target.read_bytes(),b'last-good')
 def test_actual_fantasy_stats_are_rescored_before_acceptance(self):
  r=self.row();stats={sid:0 for sid in STATS.values()};stats['42']=1;stats['0']=4
  game={'period':1,'points':4,'stats':stats};audit=[]
  rows,_=assemble([r],{(1,5):game},{5:[0,1]},{'0':1},audit)
  self.assertEqual(rows[0]['FPTS'],4);self.assertEqual(rows[0]['PTS'],4);self.assertEqual(len(audit),1)
  game['points']=9
  with self.assertRaises(CollectionError):assemble([r],{(1,5):game},{},{'0':1},[])
 def test_dropped_players_do_not_require_ownership(self):
  rows,_=assemble([self.row()],{}, {},{})
  self.assertNotIn('Team ID',rows[0]);self.assertEqual(rows[0]['Player ID'],5)
 def test_protected_legacy_output_rejected_before_requests(self):
  from playerGameLogs import collect
  with self.assertRaises(CollectionError):collect(2027,None,'data/playerDailyData.csv')
  with self.assertRaises(CollectionError):collect(2027,None,'.env')
 def test_checkpoint_drops_unrelated_private_envelope(self):
  from playerGameLogs import cache_value,BASE
  raw={'settings':{'scoringSettings':{'scoringItems':[]}},'members':[{'id':'private-profile'}]}
  self.assertNotIn('private-profile',json.dumps(cache_value(BASE+'2027',{'view':'mSettings'},raw)))
  self.assertEqual(cache_value(BASE+'2027',{'view':'kona_playercard'},{'players':[],'members':['private-profile']}),{'players':[]})
 def test_raw_gp_id_and_minute_precision(self):
  self.assertEqual(STATS['GP'],'42');self.assertEqual(STATS['MIN'],'40')
 def test_fantasy_duplicate_conflict(self):
  f=self.fantasy();g=copy.deepcopy(f['players'][0]['player']['stats'][0]);g['appliedTotal']=1;f['players'][0]['player']['stats'].append(g)
  with self.assertRaises(CollectionError):fantasy_games(f,2027)
 def test_box_dnp_and_official_zero_minutes(self):
  labels=['MIN','PTS','REB','AST','STL','BLK','FG','FT','3PT','TO']
  def athlete(pid,dnp=False):return {'didNotPlay':dnp,'athlete':{'id':pid,'displayName':'Player'},'stats':['0','0','0','0','0','0','0-0','0-0','0-0','0']}
  raw={'header':{'id':'1','season':{'type':2},'competitions':[{'status':{'type':{'completed':True}}}]},'boxscore':{'players':[{'team':{'id':1},'statistics':[{'labels':labels,'athletes':[athlete(5),athlete(6,True)]}]},{'team':{'id':2},'statistics':[{'labels':labels,'athletes':[athlete(8)]}]}]}}
  inactive=athlete(7);inactive.update(active=False);inactive['stats'][0]='--';raw['boxscore']['players'][0]['statistics'][0]['athletes'].append(inactive)
  rows=appearances(raw,{'id':1,'home':1,'away':2,'date':'2026-10-20','period':1},2027);self.assertEqual([r['Player ID']for r in rows],[5,8])
  raw['header']['competitions'][0]['type']={'id':'39'};self.assertEqual(appearances(raw,{'id':1},2027),[])
if __name__=='__main__':unittest.main()
