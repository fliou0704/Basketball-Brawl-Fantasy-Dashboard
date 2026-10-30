import unittest
from datetime import datetime, timezone
import pandas as pd
from historicalThreePointAttempts import recover_attempts, refresh_missing_attempts


class RecoveryTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame([{'Year':2023,'Player ID':1,'Scoring Period':2,'Team ID':3,'FPTS':-2,'MIN':20,'3PA':float('nan')}])
    def raw(self, **changes):
        game={'seasonId':2023,'statSourceId':0,'statSplitTypeId':5,'scoringPeriodId':2,'appliedTotal':-2,'stats':{'40':20,'18':0}}
        game.update(changes)
        return {'players':[{'id':1,'stats':[game]}]}
    def test_explicit_zero_attempts_preserve_all_other_columns(self):
        old=self.frame();result,n=recover_attempts(old,2023,self.raw())
        self.assertEqual(n,1);self.assertEqual(result['3PA'].iloc[0],0)
        pd.testing.assert_frame_equal(old.drop(columns='3PA'),result.drop(columns='3PA'))
    def test_missing_conflicting_or_changed_scoring_is_unavailable(self):
        for raw in [self.raw(stats={'40':20}),self.raw(appliedTotal=3),self.raw(stats={'40':19,'18':2}),self.raw(statSourceId=1)]:
            self.assertEqual(recover_attempts(self.frame(),2023,raw)[1],0)
        raw=self.raw();raw['players'][0]['stats'].append({**raw['players'][0]['stats'][0],'stats':{'40':20,'18':5}})
        self.assertEqual(recover_attempts(self.frame(),2023,raw)[1],0)
    def test_cache_prevents_repeated_requests_and_errors_do_not_infer(self):
        calls=[];meta={};now=datetime.now(timezone.utc)
        def request(year,ids):calls.append((year,ids));return self.raw()
        refresh_missing_attempts(self.frame(),meta,2027,request,now)
        refresh_missing_attempts(self.frame(),meta,2027,request,now)
        self.assertEqual(calls,[(2023,[1])])
        def failure(*args):raise ValueError('unavailable')
        result=refresh_missing_attempts(self.frame(),{},2027,failure,now)
        self.assertTrue(result['3PA'].isna().all())
