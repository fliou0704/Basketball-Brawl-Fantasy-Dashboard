import unittest
from datetime import datetime, timezone
from matchupSchedule import schedule_snapshot
from matchupSchedule import enrich_roster_snapshot
from types import SimpleNamespace
from copy import deepcopy

class ScheduleTests(unittest.TestCase):
    def test_normalizes_deduplicates_and_keeps_game_state_explicit(self):
        games=[{'id':1,'date':1000,'homeProTeamId':1,'awayProTeamId':2,'statsOfficial':True},
               {'id':2,'date':2000,'homeProTeamId':1,'awayProTeamId':2},
               {'id':3,'date':9000,'homeProTeamId':1,'awayProTeamId':2}]
        raw={'settings':{'proTeams':[{'id':1,'abbrev':'ONE','proGamesByScoringPeriod':{'1':games+games}}, {'id':2,'abbrev':'TWO','proGamesByScoringPeriod':{}}]}}
        result=schedule_snapshot(raw,datetime.fromtimestamp(5,timezone.utc))
        self.assertFalse(result['complete'])
        self.assertEqual([g['state'] for g in result['games']],['completed','started-unconfirmed','scheduled'])
        self.assertEqual(len(result['games']),3)
        self.assertEqual(result['games'][0]['opponent'],'TWO')
        self.assertEqual(result['games'][0]['start'],'1970-01-01T00:00:01+00:00')

    def test_missing_coverage_is_not_empty_schedule(self):
        self.assertFalse(schedule_snapshot({},datetime.now(timezone.utc))['complete'])

    def test_roster_bulk_affiliation_overrides_stale_profile_and_tracks_trade_time(self):
        now=datetime(2026,10,27,16,tzinfo=timezone.utc)
        previous={'updatedAt':'2026-10-27T12:00:00Z','nbaAffiliations':{'1':1},'nbaAffiliationSince':{'1':'2026-10-20T00:00:00Z'},
                  'teams':[{'teamId':10,'roster':[{'playerId':1,'proTeamId':1,'rosterSince':'2026-10-20T00:00:00Z'}]}]}
        before=deepcopy(previous)
        league=SimpleNamespace(teams=[SimpleNamespace(roster=[SimpleNamespace(playerId=1,proTeam='ONE',lineupSlot='PG',injuryStatus='ACTIVE')])],_brawl_affiliations={'1':2})
        raw={'teams':[{'roster':{'entries':[{'playerPoolEntry':{'player':{'id':1,'proTeamId':2}}}]}}],
             'settings':{'rosterSettings':{'lineupLocktimeType':'INDIVIDUAL_GAME','rosterLocktimeType':'FIRSTGAME_SCORINGPERIOD'},'acquisitionSettings':{}}}
        snapshot={'teams':[{'teamId':10,'roster':[{'playerId':1}]}]}
        schedule={'teams':[{'id':1,'abbrev':'ONE'},{'id':2,'abbrev':'TWO'}],'season':2027}
        result=enrich_roster_snapshot(league,snapshot,raw,now,schedule,previous)
        p=result['teams'][0]['roster'][0]
        self.assertEqual(p['proTeamId'],2);self.assertEqual(p['nbaTeamSince'],now.isoformat())
        self.assertEqual(p['rosterSince'],'2026-10-20T00:00:00Z');self.assertEqual(previous,before)
