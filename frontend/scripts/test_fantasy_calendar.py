"""Scheduled dates enrich payloads without activating projections or changing scores."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from espnFantasyCalendar import context, normalize, week_ranges
from generate_fantasy_calendar import attach
from generate_scoreboard import project
from generate_matchup_details import matchup_detail
from build_homepage import logo_config

ROOT = Path(__file__).resolve().parents[2]


class CalendarExportTests(unittest.TestCase):
    def setUp(self):
        f = json.loads((ROOT/'tests/fixtures/fantasy_calendar_2027.json').read_text())
        self.ctx = context(f['league'])
        self.calendar = dict(normalize(f['constants'],self.ctx), verifiedAt='2026-10-27T12:00:00Z')
        self.season = {'season':2027,'firstPeriod':1,'finalPeriod':167,'regularWeeks':20,
                       'dateAnchor':'2026-10-19','weeks':[],'teams':[],
                       'matchups':[{'id':2,'week':2,'sides':[{'teamId':1,'pointsByPeriod':{'7':12}}]}],
                       'lineupSlots':['PG'],'scoringWeights':{'PTS':1},
                       'fantasyCalendarContext':self.ctx,'fantasyCalendar':self.calendar}
        self.mapping = [{'Year':'2027','Scoring Period':'7','Week':'2'}]
        self.current = {'season':2027,'week':2,'scoringPeriod':7,'updatedAt':'2026-10-27T12:00:00Z',
                        'teams':[{'teamId':1,'teamName':'One','roster':[]}]}

    def test_static_export_navigation_and_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            scheduled=attach([self.season],[],self.mapping,out)
            saved=json.loads((out/'fantasy-calendar.json').read_text())
            self.assertEqual(len(saved['seasons'][0]['days']),167)
            result=project(self.current,[self.season],self.mapping,[],logo_config(),scheduled)
        weeks=result['seasons'][0]['weeks']
        self.assertEqual(len(weeks),23)
        self.assertEqual((weeks[1]['start'],weeks[1]['end']),('2026-10-26','2026-11-01'))
        self.assertEqual(weeks[20]['phase'],'playoffs')
        self.assertEqual(weeks[22]['matchups'],[])
        self.assertEqual(weeks[1]['matchups'][0]['actualScores'],None)  # single side stays unknown
        self.assertEqual(weeks[1]['dateRangeKind'],'scheduled')

    def test_inconsistent_cache_and_missing_cache_fall_back(self):
        for broken in [None,dict(self.calendar,days=[]),dict(self.calendar,context=dict(self.ctx,season=2026))]:
            season=dict(self.season,fantasyCalendar=broken)
            with tempfile.TemporaryDirectory() as directory:
                self.assertEqual(attach([season],[],self.mapping,Path(directory)),{})
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(attach([self.season],[{'Year':2027,'Scoring Period':7,'Date':'2026-10-27'}],self.mapping,Path(directory)),{})

    def test_scheduled_ranges_do_not_enable_remaining_totals(self):
        season=dict(self.season,scheduledDates={7:'2026-10-26'})
        match={'id':2,'teams':[{'teamId':1},{'teamId':2}],'actualScores':[12,0]}
        week=dict(week_ranges(self.calendar)[1],state='current',dateRangeKind='scheduled')
        result=matchup_detail(match,week,season,self.current,{7:2},[])
        self.assertEqual(result['days'][0]['date'],'2026-10-26')
        self.assertTrue(all(r['games'] is None and r['potentialStarts'] is None for r in result['remaining']))


if __name__=='__main__': unittest.main()
