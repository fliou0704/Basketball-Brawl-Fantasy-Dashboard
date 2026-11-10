from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_cloudflare_preview as preview


class PreviewBuildTests(unittest.TestCase):
    def fixture(self, root):
        source = root / 'main'; source.mkdir()
        for name in preview.REQUIRED:
            p = source / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('approved')
        branch = root / 'branch'; (branch / 'data').mkdir(parents=True)
        (branch / 'data/playerDailyData.csv').write_text('stale')
        (branch / 'data/seasonEndRosters.json').write_text('new feature source')
        return source, branch

    def test_approved_data_wins_and_only_new_feature_input_can_be_added(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);main,branch=self.fixture(root)
            added=preview.prepare_data(branch,main,root/'out')
            self.assertEqual((root/'out/playerDailyData.csv').read_text(),'approved')
            self.assertEqual(added,['seasonEndRosters.json'])
            (main/'seasonEndRosters.json').write_text('approved ownership')
            self.assertEqual(preview.prepare_data(branch,main,root/'again'),[])
            self.assertEqual((root/'again/seasonEndRosters.json').read_text(),'approved ownership')

    def test_incomplete_main_fails_without_stale_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);main,branch=self.fixture(root);(main/'playerDailyData.csv').unlink()
            with self.assertRaises(ValueError):preview.prepare_data(branch,main,root/'out')

    def test_backend_credentials_and_nonpublishable_keys_are_rejected(self):
        for key in ['ESPN_S2','SWID','SUPABASE_SECRET_KEY','SUPABASE_SERVICE_ROLE_KEY','VITE_SECRET']:
            with self.subTest(key=key),self.assertRaises(ValueError):preview.validate_environment({key:'fixture-only'})
        with self.assertRaises(ValueError):preview.validate_environment({'VITE_SUPABASE_PUBLISHABLE_KEY':'service-role-fixture'})
        preview.validate_environment({'VITE_SUPABASE_PUBLISHABLE_KEY':'sb_publishable_fixture'})

    def test_code_copy_excludes_branch_data_generated_json_and_env_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);repo=root/'repo';repo.mkdir()
            for name in ['frontend/src/App.jsx','data/playerDailyData.csv','frontend/public/data/homepage.json','.env','frontend/.env.local']:
                p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
            names=b'frontend/src/App.jsx\0data/playerDailyData.csv\0frontend/public/data/homepage.json\0.env\0frontend/.env.local\0'
            with patch.object(preview.subprocess,'check_output',return_value=names):preview.copy_code(repo,root/'out')
            self.assertEqual([str(p.relative_to(root/'out'))for p in (root/'out').rglob('*')if p.is_file()],['frontend/src/App.jsx'])

    def test_source_hash_check_detects_changed_or_added_data(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'a').write_text('approved');before=preview.hashes(root)
            (root/'a').write_text('changed');self.assertNotEqual(before,preview.hashes(root))
