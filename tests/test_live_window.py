from copy import deepcopy
from datetime import datetime,timedelta,timezone
import unittest
from liveWindow import precheck,check
from tests.test_nba_schedule import full_schedule
from nbaSchedule import normalize
from tests.test_live_scoring_adapter import metadata,nba

class LiveWindowTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,31,22,tzinfo=timezone.utc);self.m=metadata()
        s=normalize(full_schedule(),2027);s.update(verifiedAt=(self.now-timedelta(hours=4)).isoformat())
        s['fixtures']=[{'id':456,'home':1,'away':2,'hasStarted':False,'date':'2026-10-31','start':'2026-10-31T23:00:00Z','regularSeason':True,'status':'scheduled'}]
        s['teams']=[{'id':1},{'id':2}];s['rules']={'expectedTeamGames':1};self.m['nbaSchedules']={'2027':s}
    def test_no_frequent_requests_off_hours_and_no_game_date(self):
        self.assertFalse(precheck(self.m,self.now-timedelta(hours=2))['due'])
        m=deepcopy(self.m);m['nbaSchedules']['2027']['fixtures']=[]
        m['nbaSchedules']['2027']['teams']=[]
        self.assertFalse(precheck(m,self.now)['due'])
    def test_pregame_live_overtime_and_postgame_cache(self):
        self.assertTrue(precheck(self.m,self.now)['due'])
        result,state=check(self.m,self.now,fetch=lambda *_:nba());self.assertTrue(result['due'])
        late=self.now+timedelta(hours=6)
        result,state=check(self.m,late,state,fetch=lambda *_:nba());self.assertTrue(result['due'])
        final=lambda *_:nba(name='STATUS_FINAL',state='post')
        result,state=check(self.m,late,state,fetch=final);self.assertTrue(result['due'])
        self.assertFalse(precheck(self.m,late+timedelta(minutes=31),state)['due'])
    def test_late_game_crosses_midnight_new_york(self):
        self.m['nbaSchedules']['2027']['fixtures'][0]['start']='2026-11-01T02:00:00Z'
        self.assertTrue(precheck(self.m,datetime(2026,11,1,5,30,tzinfo=timezone.utc))['due'])
    def test_cup_missing_schedule_and_failure_dont_imply_zero(self):
        m=deepcopy(self.m);m['nbaSchedules']={}
        self.assertTrue(precheck(m,self.now+timedelta(minutes=2))['due'])
        self.assertFalse(precheck(m,self.now+timedelta(minutes=7))['due'])
        with self.assertRaises(ValueError):check(self.m,self.now,fetch=lambda *_:{'leagues':[1],'events':[]})
    def test_new_schedule_invalidates_closed_window(self):
        _,state=check(self.m,self.now,fetch=lambda *_:nba(name='STATUS_FINAL',state='post'))
        now=self.now+timedelta(minutes=40)
        self.assertFalse(precheck(self.m,now,state)['due'])
        self.m['nbaSchedules']['2027']['fixtures'][0]['start']='2026-10-31T23:30:00Z'
        self.assertTrue(precheck(self.m,now,state)['due'])
    def test_postponed_game_falls_back_to_quarter_hour_discovery(self):
        _,state=check(self.m,self.now,fetch=lambda *_:nba(name='STATUS_POSTPONED',state='pre'))
        self.assertFalse(precheck(self.m,self.now+timedelta(minutes=5),state)['due'])
        self.assertTrue(precheck(self.m,self.now+timedelta(minutes=15),state)['due'])
    def test_manual_force_and_fantasy_offseason(self):
        now=datetime(2026,7,1,12,tzinfo=timezone.utc)
        self.assertFalse(precheck(self.m,now)['due'])
        self.assertTrue(precheck(self.m,now,force=True)['due'])
    def test_workflow_is_activation_gated_read_only_and_has_no_deploy(self):
        from pathlib import Path
        text=(Path(__file__).parents[1]/'.github/workflows/live-scoring.yml').read_text()
        self.assertIn("vars.LIVE_SCORING_AUTOPUBLISH == 'true'",text)
        self.assertIn('contents: read',text)
        for forbidden in ('git commit','git push','deploy-pages','pages: write','npm run build'):
            self.assertNotIn(forbidden,text)
        self.assertIn('default: false',text)

if __name__=='__main__':unittest.main()
