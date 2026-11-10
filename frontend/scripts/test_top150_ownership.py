import copy
import json
from pathlib import Path
import tempfile
import unittest
from top150_ownership import validate_snapshot, load_historical_ownership
from generate_top150 import build_archive
import test_top150_archive as archive_tests


def snapshot():
    return {'season':2027,'scoringPeriod':167,'finalScoringPeriod':167,'teams':[
        {'teamId':1,'teamName':'Later alias','rosterPresent':True,'entries':[{'playerId':11,'name':'Reserve','slotId':21}]},
        {'teamId':2,'teamName':'Other alias','rosterPresent':True,'entries':[{'playerId':10,'name':'Traded player','slotId':0}]}]}


def files(path, value=None):
    (path/'seasonMetadata.json').write_text(json.dumps({'seasons':[{'season':2027,'finalPeriod':167}]}))
    (path/'basketballBrawlLeagueData.csv').write_text('Year,Week,Team ID,Team Name\n2027,23,1,Historical One\n2027,23,2,Historical Two\n')
    (path/'seasonEndRosters.json').write_text(json.dumps({'schemaVersion':1,'leagueId':609694684,'verifiedAt':'2026-11-10T00:00:00Z','seasons':{'2027':value or snapshot()}}))


class OwnershipTests(unittest.TestCase):
    def test_final_global_period_includes_reserves_and_uses_historical_names(self):
        with tempfile.TemporaryDirectory()as d:
            p=Path(d);files(p);from build_homepage import logo_config
            result=load_historical_ownership(p,2027,logo_config())
            self.assertEqual(result['owners'][10]['teamId'],2)
            self.assertEqual(result['owners'][10]['teamName'],'Historical Two')
            self.assertIn(11,result['owners']);self.assertNotIn(12,result['owners'])

    def test_incomplete_duplicate_wrong_season_or_default_postseason_snapshot_rejected(self):
        good=snapshot();invalid=[{**good,'scoringPeriod':175},{**good,'season':2026},{**good,'teams':good['teams'][:1]}]
        duplicate=copy.deepcopy(good);duplicate['teams'][1]['entries'][0]['playerId']=11;invalid.append(duplicate)
        missing=copy.deepcopy(good);missing['teams'][0]['rosterPresent']=False;invalid.append(missing)
        for value in invalid:
            with self.subTest(value=value),self.assertRaises(ValueError):validate_snapshot(value,2027,{1,2},167)

    def test_missing_snapshot_is_unknown_not_free_agency(self):
        with tempfile.TemporaryDirectory()as d:
            self.assertIsNone(load_historical_ownership(Path(d),2023,{}))
            files(Path(d));self.assertIsNone(load_historical_ownership(Path(d),2023,{}))

    def test_archive_ownership_is_separate_from_games_and_never_reassigns_history(self):
        with tempfile.TemporaryDirectory()as d:
            p=Path(d);archive_tests.ArchiveRankingTests().fixture(p);files(p);original=(p/'playerSeasonStats.csv').read_bytes()
            build_archive(p,p/'out');s=json.loads((p/'out/top150/2027.json').read_text());by_id={x['playerId']:x for x in s['players']}
            self.assertEqual(by_id[10]['fantasyTeam']['teamId'],2);self.assertEqual(by_id[10]['gp'],1);self.assertEqual(by_id[10]['fpts'],-2)
            self.assertEqual(by_id[11]['gp'],0);self.assertIsNone(by_id[11]['fpts']);self.assertEqual(s['ownershipScoringPeriod'],167)
            self.assertEqual((p/'playerSeasonStats.csv').read_bytes(),original)

    def test_all_saved_historical_snapshots_have_exact_team_coverage_and_unique_ids(self):
        from build_homepage import ROOT,logo_config
        for year,count in [(2023,159),(2024,167),(2025,164),(2026,161)]:
            with self.subTest(year=year):
                result=load_historical_ownership(ROOT/'data',year,logo_config())
                self.assertEqual(len(result['owners']),count);self.assertEqual(len({t['teamId']for t in result['owners'].values()}),10)


class CoverageDiagnosticsTests(unittest.TestCase):
    def test_real_claxton_game_is_known_but_outside_the_nba_archive_cutoff(self):
        import csv
        from build_homepage import ROOT
        current=json.loads((ROOT/'frontend/public/data/top150/2027.json').read_text())
        player=next(p for p in current['players']if p['playerId']==4278067)
        with (ROOT/'data/playerDailyData.csv').open()as f:
            games=[r for r in csv.DictReader(f)if r['Year']=='2027'and r['Player ID']=='4278067'and float(r['MIN'])>0]
        november8=next(r for r in games if r['Date']=='2026-11-08')
        self.assertEqual(float(november8['FPTS']),23);self.assertEqual(float(november8['MIN']),18)
        self.assertEqual(november8['Player Slot'],'IR')
        self.assertEqual(player['newerRosterGames']['throughDate'],'2026-11-08')
        self.assertIsNone(player['fpts']);self.assertEqual(player['gp'],0)

    def test_newer_ir_game_is_reported_without_fabricating_full_pool_statistics(self):
        with tempfile.TemporaryDirectory()as d:
            p=Path(d);archive_tests.ArchiveRankingTests().fixture(p)
            (p/'currentLeague.json').write_text(json.dumps({'season':2027,'updatedAt':'2026-10-22','teams':[{'teamId':1,'teamName':'One','roster':[{'playerId':11,'name':'Reserve','slot':'IR'}]}]}))
            (p/'playerDailyData.csv').write_text('Year,Player ID,Date,MIN,Player Slot,FPTS\n2027,11,2026-10-21,18,IR,23\n2027,11,2026-10-21,18,IR,23\n2027,10,2026-10-22,0,BE,0\n')
            original=(p/'playerSeasonStats.csv').read_bytes();build_archive(p,p/'out')
            s=json.loads((p/'out/top150/2027.json').read_text());by_id={x['playerId']:x for x in s['players']}
            self.assertEqual(s['throughDate'],'2026-10-20');self.assertEqual(s['newerRosterThroughDate'],'2026-10-21')
            self.assertEqual(by_id[11]['newerRosterGames'],{'count':1,'throughDate':'2026-10-21'})
            self.assertEqual(by_id[11]['gp'],0);self.assertIsNone(by_id[11]['fpts']);self.assertEqual((p/'playerSeasonStats.csv').read_bytes(),original)
            first=s['dataVersion'];(p/'playerDailyData.csv').write_text((p/'playerDailyData.csv').read_text().replace('2026-10-21','2026-10-23'))
            build_archive(p,p/'out');changed=json.loads((p/'out/top150/2027.json').read_text());self.assertNotEqual(changed['dataVersion'],first)
