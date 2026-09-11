import csv
from datetime import date, timedelta
import json
import os
from pathlib import Path
import unittest

from build_homepage import ROOT, choose_lineup, raw_stats, matchup_rows, bracket_view, team_info, logo_config
from homepage_state import select_state, normalize_calendar

META = json.loads((ROOT / 'frontend/source/season-metadata.json').read_text())['seasons']


def seasons():
    result = []
    for meta in META:
        end = (date.fromisoformat(meta['dateAnchor'])+timedelta(days=meta['finalPeriod'])).isoformat()
        weeks = normalize_calendar(meta['weeks'], end)
        days = [(date.fromisoformat(weeks[0]['start'])+timedelta(days=i)).isoformat()
                for i in range((date.fromisoformat(end)-date.fromisoformat(weeks[0]['start'])).days+1)]
        result.append(dict(meta, start=weeks[0]['start'],end=end,weeks=weeks,complete=True,
                           completedDays=days,completedWeeks=[w['week'] for w in weeks]))
    return result


class SeasonStateTests(unittest.TestCase):
    def setUp(self):
        self.seasons = seasons()
        self.current = self.seasons[-1]

    def state(self, day): return select_state(day, self.seasons)

    def test_preseason_uses_previous_completed_season(self):
        self.assertEqual(self.state('2025-09-10')['season'], 2025)
        self.assertEqual(self.state('2025-09-10')['phase'], 'offseason')

    def test_day_one_uses_previous_season_without_empty_recaps(self):
        s = self.state(self.current['start'])
        self.assertEqual((s['phase'],s['season']),('offseason',2025))
        self.assertIsNone(s['dailyDate']); self.assertIsNone(s['weeklyWeek'])

    def test_second_day_selects_current_season_and_previous_day(self):
        s = self.state('2025-10-22')
        self.assertEqual(s['phase'],'regular'); self.assertEqual(s['dailyDate'],'2025-10-21')
        self.assertEqual(s['season'],2026)

    def test_week_one_never_borrows_prior_season_week(self):
        self.assertIsNone(self.state('2025-10-24')['weeklyWeek'])

    def test_midseason_daily_first(self):
        s = self.state('2026-01-15')
        self.assertEqual(s['phase'],'regular'); self.assertFalse(s['weeklyFirst'])
        self.assertEqual(s['dailyDate'],'2026-01-14')

    def test_new_week_automatically_weekly_first(self):
        week = self.current['weeks'][5]
        s = self.state(week['start'])
        self.assertTrue(s['weeklyFirst']); self.assertEqual(s['weeklyWeek'],week['week']-1)

    def test_first_playoff_week(self):
        w = self.current['weeks'][self.current['regularWeeks']]
        s = self.state(w['start'])
        self.assertEqual(s['phase'],'playoffs'); self.assertEqual(s['playoffKey'],str(w['week']))

    def test_middle_playoff_week(self):
        w = self.current['weeks'][-2]
        s = self.state(w['start'])
        self.assertEqual(s['phase'],'playoffs'); self.assertEqual(s['weeklyWeek'],w['week']-1)

    def test_final_week_is_still_playoffs(self):
        self.assertEqual(self.state(self.current['end'])['phase'],'playoffs')

    def test_day_after_final_is_offseason_current_completed_season(self):
        day = date.fromisoformat(self.current['end'])+timedelta(days=1)
        s = self.state(day)
        self.assertEqual((s['phase'],s['season'],s['playoffKey']),('offseason',2026,'final'))

    def test_missing_previous_day_uses_last_completed_scoring_day(self):
        self.current['completedDays'].remove('2026-01-14')
        self.assertEqual(self.state('2026-01-15')['dailyDate'],'2026-01-13')

    def test_no_future_daily_or_weekly_results(self):
        for s in self.seasons:
            for week in s['weeks']:
                state=self.state(week['start'])
                if state['phase']!='offseason':
                    self.assertLess(state['dailyDate'],week['start'])
                    if state['weeklyWeek']: self.assertLess(state['weeklyWeek'],week['week'])

    def test_no_game_boundary_is_inferred_not_hardcoded(self):
        weeks=[dict(week=1,start='2026-01-07',end='2026-01-13',firstPeriod=1,lastPeriod=7),
               dict(week=2,start='2026-01-14',end='2026-01-20',firstPeriod=8,lastPeriod=14),
               dict(week=3,start='2026-01-22',end='2026-01-27',firstPeriod=16,lastPeriod=21),
               dict(week=4,start='2026-01-28',end='2026-02-03',firstPeriod=22,lastPeriod=28)]
        result=normalize_calendar(weeks,'2026-02-03')
        self.assertEqual(result[2]['start'],'2026-01-21') # Wednesday cadence, not Monday

    def test_incomplete_season_never_claims_champion(self):
        self.current['complete']=False
        self.assertEqual(self.state('2026-04-06')['season'],2025)


class HomepageMetricTests(unittest.TestCase):
    def test_scoring_contributions_convert_to_actual_stats(self):
        stats=raw_stats({'AST':'20','TO':'-8','FGM':'24','FGA':'-20','3PM':'3'}, {'AST':2,'TO':-2,'FGM':2,'FGA':-1,'3PM':1})
        self.assertEqual(stats['AST'],10);self.assertEqual(stats['TO'],4)
        self.assertEqual(stats['FGM'],12);self.assertEqual(stats['FGA'],20)
        self.assertIsNone(stats['3PA'])

    def test_lineup_optimizes_eligibility_without_reusing_players(self):
        def row(pid, points, pos, pos2=''):
            return {'Player ID':str(pid),'Player Name':str(pid),'Team ID':'1','FPTS':str(points),'Position':pos,'Position2':pos2}
        lineup=choose_lineup([row(1,100,'PG','C'),row(2,99,'PG'),row(3,1,'C')],['PG','C'],{1:{'teamId':1}})
        self.assertEqual(sum(p['points'] for p in lineup),199)
        self.assertEqual(len({p['playerId'] for p in lineup}),2)
        self.assertEqual(next(p['playerId'] for p in lineup if p['slot']=='C'),1)

    def test_matchup_ties_and_reciprocals(self):
        rows=[{'Team ID':'1','Opponent Team ID':'2','Points For':'100','Points Against':'100','Type':'Regular'},
              {'Team ID':'2','Opponent Team ID':'1','Points For':'100','Points Against':'100','Type':'Regular'}]
        matches=matchup_rows(rows,{1:{'teamId':1},2:{'teamId':2}})
        self.assertEqual(len(matches),1);self.assertIsNone(matches[0]['winnerId']);self.assertEqual(matches[0]['margin'],0)

    def test_real_bracket_excludes_consolation_and_hides_future_results(self):
        source=Path(os.environ.get('HOMEPAGE_TEST_SOURCE', ROOT / 'data'))
        with (source/'basketballBrawlLeagueData.csv').open() as handle:
            rows=[r for r in csv.DictReader(handle) if r['Year']=='2025']
        meta=next(m for m in META if m['season']==2025)
        teams={int(r['Team ID']):team_info(r,logo_config()) for r in rows}
        active=bracket_view(rows,meta,teams,meta['regularWeeks']+1)
        self.assertTrue(all(m['scores'] is None for m in active['rounds'][0]['matches']))
        self.assertEqual(active['rounds'][1]['matches'],[])
        self.assertIsNone(active['champion'])
        complete=bracket_view(rows,meta,teams)
        self.assertEqual([len(r['matches']) for r in complete['rounds']],[2,2,1])
        self.assertIsNotNone(complete['champion'])

    def test_live_metadata_has_authoritative_team_day_totals(self):
        meta=META[-1]
        self.assertTrue(any(side['pointsByPeriod'] for m in meta['matchups'] for side in m['sides']))
        self.assertNotIn('BE',meta['lineupSlots']);self.assertNotIn('IR',meta['lineupSlots'])
        self.assertEqual(meta['lineupSlots'].count('UT'),3)


class GeneratedHomepageTests(unittest.TestCase):
    def setUp(self):
        self.output=ROOT/'frontend/public/data'

    def load(self, name):
        return json.loads((self.output/name).read_text())

    def test_generated_day_one_has_previous_season_recap(self):
        state=self.load('homepage.json')['states']['2025-10-21']
        self.assertEqual(state['season'],2025)
        self.assertEqual(state['phase'],'offseason')

    def test_generated_weekly_playoff_lineup_only_actual_participants(self):
        recaps=self.load('2026/weekly-recap.json')['data']
        for week in ('21','22','23'):
            recap=recaps[week]
            ids={t['teamId'] for m in recap['matches'] for t in m['teams']}
            self.assertTrue(all(p['team']['teamId'] in ids for p in recap['lineup']))
            self.assertEqual(len({p['playerId'] for p in recap['lineup']}),len(recap['lineup']))

    def test_generated_regular_standings_do_not_use_playoff_ranks(self):
        standings=self.load('2026/standings.json')['data']['20']
        self.assertEqual(standings['currentWeek'],20)
        source=Path(os.environ.get('HOMEPAGE_TEST_SOURCE', ROOT / 'data'))
        with (source/'basketballBrawlLeagueData.csv').open() as handle:
            rows=[r for r in csv.DictReader(handle) if r['Year']=='2025' and r['Week']=='20']
        historical=self.load('2025/standings.json')['data']['20']
        ranks={int(r['Team ID']):int(r['Rank']) for r in rows}
        self.assertEqual({t['teamId']:t['rank'] for t in historical['teams']},ranks)

    def test_daily_team_leader_is_authoritative_espn_score(self):
        daily=self.load('2026/daily-recap.json')['data']
        meta=META[-1]
        for day,recap in daily.items():
            period=(date.fromisoformat(day)-date.fromisoformat(meta['dateAnchor'])).days
            totals={side['teamId']:side['pointsByPeriod'][str(period)]
                    for matchup in meta['matchups'] for side in matchup['sides']
                    if str(period) in side['pointsByPeriod']}
            for leader in recap['leaders']:
                self.assertEqual(leader['points'],max(totals.values()))

    def test_every_dated_state_reference_exists_without_empty_recap(self):
        manifest=self.load('homepage.json')
        seasonal={str(year):{name:self.load(f'{year}/{name}.json')['data']
                            for name in ('daily-recap','weekly-recap','standings','playoffs')}
                  for year in (2023,2024,2025,2026)}
        for day,state in manifest['states'].items():
            if state['season'] is None: continue
            data=seasonal[str(state['season'])]
            for field,name in [('dailyDate','daily-recap'),('weeklyWeek','weekly-recap'),
                               ('standingsWeek','standings'),('playoffKey','playoffs')]:
                key=state.get(field)
                if key is not None:
                    self.assertIn(str(key),data[name],(day,field))
            if state['dailyDate']:
                self.assertTrue(data['daily-recap'][state['dailyDate']]['players'])


if __name__=='__main__': unittest.main()
