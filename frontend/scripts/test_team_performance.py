import unittest
import pandas as pd
from generate_team_stats import ROOT
from teamPerformance import team_performance, combine_performance, performance_audit


class TeamPerformanceTests(unittest.TestCase):
    def calculate(self, missing=False):
        rows = []
        for year in (2025, 2026):
            for period, points in ((1, 20), (2, 40)):
                for player, slot, minutes, score in ((1, 'PG', 30, points), (2, 'BE', 30, 999), (3, 'PG', 0, 0)):
                    rows.append({'Year':year,'Scoring Period':period,'Team ID':7,'Player ID':player,
                                 'Player Slot':slot,'MIN':minutes,'FPTS':score})
        if missing:
            rows = rows[1:]
        mapping = pd.DataFrame([{'Year':year,'Scoring Period':period,'Week':period}
                                for year in (2025,2026) for period in (1,2)])
        league = pd.DataFrame([{'Year':year,'Week':week,'Team ID':7,'Points For':points}
                               for year in (2025,2026) for week,points in ((1,20),(2,40))])
        metadata = {'seasons':[{'season':year,'lineupSlots':['PG']} for year in (2025,2026)]}
        return team_performance(pd.DataFrame(rows), mapping, metadata, league)

    def test_bench_and_unplayed_games_excluded_week_season_and_franchise(self):
        result = self.calculate()
        self.assertEqual(result[(2025,7)]['weeks']['1']['fpPerStart'],20)
        self.assertEqual(result[(2025,7)]['season']['starts'],2)
        self.assertEqual(result[(2025,7)]['season']['fpPerStart'],30)
        career = combine_performance(item['season'] for item in result.values())
        self.assertEqual((career['fpts'],career['starts'],career['fpPerStart']),(120,4,30))

    def test_missing_history_invalidates_broader_denominators(self):
        result = self.calculate(missing=True)
        self.assertIsNone(result[(2025,7)]['season']['fpPerStart'])
        self.assertIsNone(combine_performance(item['season'] for item in result.values())['starts'])

    def test_zero_starts_safe_and_aggregate_before_divide(self):
        self.assertIsNone(combine_performance([])['fpPerStart'])
        self.assertEqual(combine_performance([{'available':True,'fpts':20,'starts':1},
                                              {'available':True,'fpts':90,'starts':3}])['fpPerStart'],27.5)

    def test_zero_scoring_played_start_still_counts(self):
        rows = pd.DataFrame([{'Year':2026,'Scoring Period':1,'Team ID':7,'Player ID':1,
                              'Player Slot':'PG','MIN':10,'FPTS':0}])
        mapping = pd.DataFrame([{'Year':2026,'Scoring Period':1,'Week':1}])
        metadata = {'seasons':[{'season':2026,'lineupSlots':['PG']}]}
        league = pd.DataFrame([{'Year':2026,'Week':1,'Team ID':7,'Points For':0}])
        metric = team_performance(rows,mapping,metadata,league)[(2026,7)]['season']
        self.assertEqual((metric['starts'],metric['fpPerStart']),(1,0))
        duplicated = team_performance(pd.concat([rows,rows]),mapping,metadata,league)
        self.assertFalse(duplicated[(2026,7)]['season']['available'])

    def fixture(self):
        daily=pd.DataFrame([
            {'Year':2023,'Scoring Period':period,'Team ID':7,'Player ID':player,
             'Player Slot':slot,'MIN':minutes,'FPTS':points}
            for period,player,slot,minutes,points in (
                (1,1,'PG',30,20),(1,2,'BE',30,100),(1,3,'IR',20,100),
                (2,1,'PG',20,0),(2,4,'PG',10,-3),(2,5,'PG',0,0),
                (3,1,'PG',30,80))])
        mapping=pd.DataFrame([{'Year':2023,'Scoring Period':period,'Week':period} for period in (1,2,3)])
        metadata={'seasons':[{'season':2023,'lineupSlots':['PG'],'matchups':[]}]}
        league=pd.DataFrame([{'Year':2023,'Week':week,'Team ID':7,'Type':kind,'Points For':points}
                             for week,kind,points in ((1,'Regular',20),(2,'Regular',-3),(3,'Bye',0))])
        weekly=pd.DataFrame([{'Year':2023,'Week':week,'Team ID':7,'Player ID':player,'FPTS':points}
                             for week,player,points in ((1,1,20),(2,1,0),(2,4,-3),(3,1,80))])
        return daily,mapping,metadata,league,weekly

    def test_byes_exclude_all_roster_games_from_numerator_and_denominator(self):
        result=team_performance(*self.fixture())[(2023,7)]
        bye=result['weeks']['3']
        self.assertEqual((bye['fpts'],bye['starts'],bye['coverage']),(0,0,'bye-excluded'))
        self.assertTrue(result['season']['available'])
        self.assertEqual((result['season']['fpts'],result['season']['starts']),(17,3))
        self.assertEqual(result['season']['fpPerStart'],5.67)

    def test_corrected_player_scores_do_not_require_frozen_scoreboard_to_change(self):
        daily,mapping,metadata,league,weekly=self.fixture()
        league.loc[league.Week==1,'Points For']=19
        result=team_performance(daily,mapping,metadata,league,weekly)[(2023,7)]
        metric=result['weeks']['1']
        self.assertEqual((metric['recordedFpts'],metric['fpts'],metric['scoreDelta']),(19,20,1))
        self.assertEqual(metric['verifiedBy'],'weekly-player-stats')
        self.assertTrue(result['season']['available'])
        self.assertEqual(league.loc[league.Week==1,'Points For'].iloc[0],19)

    def test_saved_espn_daily_scores_can_verify_a_later_stat_correction(self):
        daily,mapping,metadata,league,weekly=self.fixture()
        daily.loc[(daily['Scoring Period']==1)&(daily['Player ID']==1),'FPTS']=24
        metadata['seasons'][0]['matchups']=[{'week':1,'sides':[{'teamId':7,'pointsByPeriod':{'1':24}}]}]
        metric=team_performance(daily,mapping,metadata,league,weekly)[(2023,7)]['weeks']['1']
        self.assertTrue(metric['available'])
        self.assertEqual((metric['fpts'],metric['verifiedBy']),(24,'saved-espn-daily-scores'))

    def test_weekly_player_reference_must_match_each_player_not_only_the_team_sum(self):
        daily,mapping,metadata,league,weekly=self.fixture()
        daily.loc[(daily['Scoring Period']==1)&(daily['Player ID']==1),'FPTS']=15
        daily.loc[len(daily)]=[2023,1,7,6,'PG',30,5]
        league.loc[league.Week==1,'Points For']=19
        metric=team_performance(daily,mapping,metadata,league,weekly)[(2023,7)]['weeks']['1']
        self.assertFalse(metric['available'])

    def test_unexplained_missing_data_invalidates_season_and_career(self):
        daily,mapping,metadata,league,weekly=self.fixture()
        daily=daily[~((daily['Scoring Period']==1)&(daily['Player ID']==1))]
        result=team_performance(daily,mapping,metadata,league,weekly)[(2023,7)]
        self.assertFalse(result['season']['available'])
        self.assertIsNone(combine_performance([result['season']])['fpPerStart'])

    def test_all_benched_week_is_verified_zero_starts_not_missing(self):
        daily,mapping,metadata,league,weekly=self.fixture()
        daily.loc[daily['Scoring Period']==1,'Player Slot']='BE'
        league.loc[league.Week==1,'Points For']=0
        metric=team_performance(daily,mapping,metadata,league,weekly)[(2023,7)]['weeks']['1']
        self.assertEqual((metric['fpts'],metric['starts'],metric['coverage']),(0,0,'verified-zero-starts'))
        self.assertTrue(metric['available'])
        self.assertIsNone(metric['fpPerStart'])

    def test_historical_slot_rules_team_ownership_and_repeated_dates(self):
        daily,mapping,metadata,league,weekly=self.fixture()
        # Same player's games on different dates count separately, staying with
        # the historical team ID rather than a current roster/name lookup.
        daily.loc[daily['Scoring Period']==2,'Team ID']=8
        league.loc[league.Week==2,'Team ID']=8
        weekly.loc[weekly.Week==2,'Team ID']=8
        result=team_performance(daily,mapping,metadata,league,weekly)
        self.assertEqual(result[(2023,7)]['season']['starts'],1)
        self.assertEqual(result[(2023,8)]['season']['starts'],2)
        self.assertEqual(result[(2023,8)]['season']['fpts'],-3)
        metadata['seasons'][0]['lineupSlots']=['C']
        self.assertFalse(team_performance(daily,mapping,metadata,league,weekly)[(2023,7)]['season']['available'])

    def test_audit_distinguishes_byes_score_corrections_and_unknown_weeks(self):
        data=self.fixture()
        report=performance_audit(team_performance(*data))['seasons'][0]
        self.assertEqual(report['byeWeeksExcluded'],1)
        self.assertEqual(report['verifiedTeamWeeks'],3)
        self.assertEqual(report['unavailableWeeks'],[])

    def test_each_played_date_counts_once_and_future_unmatched_rows_do_not_count(self):
        daily,mapping,metadata,league,weekly=self.fixture()
        daily=daily[daily['Player ID']==1].copy().reset_index(drop=True)
        daily.loc[daily['Scoring Period']==2,'FPTS']=5
        mapping.loc[mapping['Scoring Period']==2,'Week']=1
        league=league[league.Week!=2].copy()
        league.loc[league.Week==1,'Points For']=25
        weekly=weekly[(weekly['Week']==1)&(weekly['Player ID']==1)].copy()
        weekly.loc[:,'FPTS']=25
        # The same historical player played two dates in one matchup week.
        result=team_performance(daily,mapping,metadata,league,weekly)[(2023,7)]
        self.assertEqual((result['weeks']['1']['starts'],result['weeks']['1']['fpts']),(2,25))
        # A future scheduled row has no recorded matchup result and is ignored.
        daily.loc[len(daily)]=[2023,4,7,99,'PG',0,0]
        mapping.loc[len(mapping)]=[2023,4,4]
        later=team_performance(daily,mapping,metadata,league,weekly)[(2023,7)]
        self.assertEqual(result['season'],later['season'])
