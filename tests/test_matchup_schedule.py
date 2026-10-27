import unittest
from datetime import datetime, timezone
from matchupSchedule import schedule_snapshot

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
