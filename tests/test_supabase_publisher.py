"""Credential-free contract/API tests. Actual SQL/RLS assertions live in supabase/tests."""
from copy import deepcopy
from datetime import timedelta
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

import requests
import supabasePublisher as pub
from liveScoringAdapter import assemble,normalize_league,normalize_games,changed_entities,digest
from tests.test_live_scoring_adapter import raw,nba,metadata,NOW

STATUS={'version':1,'rls_enabled':True,'anonymous_read_only':True,'authenticated_read_only':True,'writer_restricted':True,'select_policies_only':True}
UUID='11111111-1111-4111-8111-111111111111'


def snapshot(league=123):
    r=raw();r['id']=league
    s=assemble(normalize_league(r,2027,league,metadata()),normalize_games(nba(),'2026-10-31',2027),metadata())
    s.update(revision=digest(s),updatedAt=NOW.isoformat(),changes=changed_entities(None,s))
    return s


def response(data,status=200):
    return Mock(status_code=status,content=b'{}',headers={},json=Mock(return_value=data))


class ContractTests(unittest.TestCase):
    def test_existing_adapter_compatibility_and_exact_json_roundtrip(self):
        s=snapshot();summary=pub.validate(json.loads(json.dumps(s)),123,NOW.isoformat(),NOW)
        self.assertEqual(summary['players'],4);self.assertEqual(summary['revision'],s['revision'])

    def test_multi_league_and_schema_identity_rejected(self):
        for league,s in ((124,snapshot()),(123,dict(snapshot(),schemaVersion=2))):
            with self.assertRaises(pub.PublisherError):pub.validate(s,league,NOW.isoformat(),NOW)
        self.assertEqual(pub.validate(snapshot(124),124,NOW.isoformat(),NOW)['season'],2027)

    def test_unknown_sensitive_and_cache_fields_blocked(self):
        for field in ('cookies','owners','headers','cache','SWID','SUPABASE_SECRET_KEY'):
            s=snapshot();s['teams'][0][field]='must-not-escape'
            with self.subTest(field=field),self.assertRaises(pub.PublisherError):pub.validate(s,123,NOW.isoformat(),NOW)
        s=snapshot();s['changes']['players']=[{'email':'hidden@example.test'}]
        with self.assertRaises(pub.PublisherError):pub.validate(s,123,NOW.isoformat(),NOW)

    def test_secret_values_never_pass_inside_text(self):
        for secret in ('sb_secret_never_publish_this','opaque-secret-value-long'):
            s=snapshot();s['teams'][0]['name']=secret
            with patch.dict(os.environ,{'ESPN_S2':secret}),self.assertRaises(pub.PublisherError) as e:
                pub.validate(s,123,NOW.isoformat(),NOW)
            self.assertNotIn(secret,str(e.exception))

    def test_hash_finite_types_and_partial_coverage(self):
        for mutate in (lambda s:s['teams'][0].update(officialScore=999),lambda s:s.update(teams=[]),
                       lambda s:s['teams'][0]['players'][0].update(fantasyPoints=float('nan'))):
            s=snapshot();mutate(s)
            with self.assertRaises(pub.PublisherError):pub.validate(s,123,NOW.isoformat(),NOW)

    def test_stale_future_and_unverified_timestamps(self):
        for checked in ((NOW-timedelta(minutes=11)).isoformat(),(NOW+timedelta(minutes=6)).isoformat(),'2026-10-31T18:00:00'):
            with self.assertRaises(pub.PublisherError):pub.validate(snapshot(),123,checked,NOW)

    def test_state_error_or_revision_mismatch_is_not_publishable(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'snapshot.json';s=snapshot();p.write_text(json.dumps(s));state=p.with_suffix('.json.state.json')
            state.write_text(json.dumps({'revision':s['revision'],'leagueId':123,'season':2027,'verifiedAt':NOW.isoformat(),'error':None}))
            self.assertEqual(pub.load_snapshot(p)[0],s)
            state.write_text(json.dumps({'error':'source unavailable'}))
            with self.assertRaises(pub.PublisherError):pub.load_snapshot(p)

    def test_configuration_missing_names_and_no_actual_env_edit(self):
        with patch.dict(os.environ,{},clear=True),self.assertRaises(pub.PublisherError) as e:pub.Config.environment(True)
        self.assertIn('SUPABASE_URL',str(e.exception));self.assertIn('SUPABASE_SECRET_KEY',str(e.exception))
        for url in ('http://example.test','https://user:password@example.supabase.co','https://example.supabase.co/rest/v1'):
            with self.assertRaises(pub.PublisherError):pub.Config(url,'sb_secret_test')

    def test_dry_run_requires_no_supabase_or_espn_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'snapshot.json';s=snapshot();p.write_text(json.dumps(s))
            p.with_suffix('.json.state.json').write_text(json.dumps({'revision':s['revision'],'leagueId':123,'season':2027,'verifiedAt':NOW.isoformat(),'error':None}))
            with patch.dict(os.environ,{},clear=True),patch('supabasePublisher.validate',return_value={'season':2027}),patch('sys.argv',['publisher','--snapshot',str(p),'--league-id','123','--dry-run']),patch('sys.stdout',new_callable=io.StringIO) as out,patch('requests.Session.request') as network:
                self.assertEqual(pub.main(),0);network.assert_not_called();self.assertIn('dryRun',out.getvalue())


class APITests(unittest.TestCase):
    def setUp(self):
        self.config=pub.Config('https://example.supabase.co','sb_secret_fake_backend_only','sb_publishable_fake_public_only')
        self.session=Mock();self.publisher=pub.Publisher(self.config,self.session,sleep=lambda _:None);self.s=snapshot()
        self.row={'league_id':UUID,'season':2027,'snapshot':self.s,'revision':self.s['revision'],'verified_at':NOW.isoformat()}
    def publish(self):return self.publisher.publish(self.s,NOW.isoformat(),'nba',123,'Test league',True,NOW)
    def answers(self,action='inserted'):
        self.session.request.side_effect=[response(STATUS),response({'action':action,'league_id':UUID,'revision':self.s['revision']}),response([self.row])]

    def test_idempotent_upsert_and_unchanged_acknowledgement(self):
        for action in ('inserted','updated','unchanged','refreshed'):
            self.publisher._ready=False;self.answers(action)
            result=self.publish();self.assertEqual(result['action'],action);self.assertTrue(result['roundTripVerified'])
        for call in self.session.request.call_args_list:
            self.assertEqual(call.kwargs['timeout'],(10,30));self.assertFalse(call.kwargs['allow_redirects'])
            self.assertNotIn('Authorization',call.kwargs['headers'])

    def test_stale_remote_rejected_without_read_or_overwrite_retry(self):
        self.publisher._ready=True;self.session.request.return_value=response({'action':'stale'})
        with self.assertRaisesRegex(pub.PublisherError,'newer remote'):self.publish()
        self.assertEqual(self.session.request.call_count,1)

    def test_readback_is_scoped_by_league_and_season(self):
        self.answers();self.publish();call=self.session.request.call_args
        self.assertEqual(call.kwargs['params']['league_id'],'eq.'+UUID)
        self.assertEqual(call.kwargs['params']['season'],'eq.2027')

    def test_wrong_readback_does_not_claim_success(self):
        self.answers();self.row['snapshot']={'wrong':True}
        with self.assertRaisesRegex(pub.PublisherError,'mismatch'):self.publish()

    def test_wrong_league_or_missing_row_shape_rejected(self):
        for row in (None,dict(self.row,league_id='22222222-2222-4222-8222-222222222222'),dict(self.row,season=2026)):
            self.session.request.side_effect=None;self.session.request.return_value=response([row])
            with self.assertRaises(pub.PublisherError):self.publisher.read(UUID,2027)

    def test_missing_remote_freshness_is_sanitized(self):
        self.answers();self.row.pop('verified_at')
        with self.assertRaises(pub.PublisherError):self.publish()

    def test_readiness_blocks_insecure_schema(self):
        for key in STATUS:
            status=dict(STATUS);status[key]=False;self.session.request.side_effect=None;self.session.request.return_value=response(status)
            with self.assertRaises(pub.PublisherError):self.publisher.ready()

    def test_absent_migration_and_http_error_messages_are_sanitized(self):
        for status,body in ((404,{'code':'PGRST202'}),(403,{'message':self.config.secret}),(400,{'message':'authenticated private data'})):
            self.session.request.return_value=response(body,status)
            with self.assertRaises(pub.PublisherError) as e:self.publisher.ready()
            self.assertNotIn(self.config.secret,str(e.exception));self.assertNotIn('private data',str(e.exception))

    def test_connection_retries_are_bounded_and_rpc_retry_safe(self):
        self.session.request.side_effect=[requests.Timeout('secret header detail')]*2
        with self.assertRaises(pub.PublisherError) as e:self.publisher.ready()
        self.assertEqual(self.session.request.call_count,2);self.assertNotIn('secret header',str(e.exception))

    def test_anon_reads_use_only_publishable_key_and_mutations_are_denied(self):
        result={'leagueId':UUID,'verifiedAt':NOW.isoformat()}
        self.session.request.side_effect=[response([self.row]),response([{'is_public':True}])]+[response({'code':'42501'},403)]*7
        outcome=self.publisher.verify_anonymous(result,self.s,'nba',123,'Test league',True)
        self.assertEqual(outcome['anonymousMutationDenials'],7)
        for call in self.session.request.call_args_list:self.assertEqual(call.kwargs['headers']['apikey'],self.config.publishable)

    def test_anon_write_success_is_failure_and_does_not_target_real_rows(self):
        self.session.request.side_effect=[response([self.row]),response([{'is_public':True}]),response({},201)]
        with self.assertRaises(pub.PublisherError):self.publisher.verify_anonymous({'leagueId':UUID,'verifiedAt':NOW.isoformat()},self.s,'nba',123,'Test league',True)
        self.assertEqual(self.session.request.call_args.kwargs['json'],{'sport':'invalid'})


if __name__=='__main__':unittest.main()
