import copy
import json
from pathlib import Path
import tempfile
import unittest
from tests.test_nba_schedule import full_schedule
from nbaSchedule import normalize
from espnFantasyCalendar import normalize as normalize_calendar, context, week_ranges
from generate_nba_schedule import build

ROOT=Path(__file__).resolve().parents[2]


class SharedScheduleExportTests(unittest.TestCase):
    def test_single_shared_fixture_dataset_current_and_future_opportunities(self):
        f=json.loads((ROOT/'tests/fixtures/fantasy_calendar_2027.json').read_text())
        days=normalize_calendar(f['constants'],context(f['league']))['days']
        nba=dict(normalize(full_schedule(),2027),verifiedAt='2026-10-27T12:00:00Z')
        metadata={'nbaSchedules':{'2027':nba}}
        current={'season':2027,'updatedAt':'2026-10-27T16:00:00Z','nbaAffiliations':{'1':1},
                 'lineupConstraints':{'daily':True,'rosterLock':'FIRSTGAME_SCORINGPERIOD','slotStatLimits':{}},
                 'teams':[{'teamId':1,'roster':[{'playerId':1,'name':'One','proTeamId':1,'slot':'BE','eligibility':['PG']}]}]}
        calendar={'season':2027,'lineupSlots':['PG'],'scheduledDays':days}
        ranges=week_ranges({'days':days})
        scoreboard={'seasons':[{'season':2027,'weeks':[dict(w,state='final'if w['week']<2 else'current'if w['week']==2 else'future',dateRangeKind='scheduled')for w in ranges]}]}
        before=copy.deepcopy(metadata)
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);build(metadata,current,[calendar],scoreboard,[],out)
            fixtures=json.loads((out/'nba-schedule.json').read_text());opps=json.loads((out/'matchup-opportunities.json').read_text())
        self.assertEqual(len(fixtures['fixtures']),1200)
        self.assertTrue(all(g['fantasyWeek'] is not None for g in fixtures['fixtures']))
        self.assertEqual(opps['weeks']['2']['1']['games'],3)
        self.assertEqual(opps['weeks']['2']['1']['potentialStarts'],3)
        self.assertEqual(opps['weeks']['3']['1']['games'],3)
        self.assertNotIn('1',opps['weeks'])
        self.assertEqual(metadata,before)
        self.assertTrue(all('start' not in p for week in opps['weeks'].values()for r in week.values()for p in r['players']))

    def test_conflicting_player_identity_fails_closed(self):
        # Cross-manager duplicate ownership is detected before any future joins.
        from fantasyOpportunities import remaining
        value=remaining({'teams':[{'teamId':1,'rosterConflict':True,'roster':[]}]},{},{'state':'future'},1,None)
        self.assertIsNone(value['games'])


if __name__=='__main__':unittest.main()
