"""Guard the production/development boundary without network or credentials."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github/workflows'


class ProductionWorkflowBoundaries(unittest.TestCase):
    def workflow(self, name):
        return (WORKFLOWS / name).read_text()

    def test_production_workflows_never_checkout_or_push_codex(self):
        for path in WORKFLOWS.glob('*.yml'):
            source = path.read_text()
            with self.subTest(workflow=path.name):
                self.assertNotRegex(source, r'ref:\s*codex\b|HEAD:codex|refs/heads/codex')

    def test_pages_requires_main_at_build_and_deploy(self):
        source = self.workflow('frontend-pages.yml')
        self.assertRegex(source, r'branches:\s*\[main\]')
        self.assertGreaterEqual(source.count("if: github.ref == 'refs/heads/main'"), 2)
        self.assertIn('ref: ${{ github.sha }}', source)
        self.assertNotIn('pull_request_target:', source)

    def test_data_writers_share_deployment_lock_and_refuse_dev_dispatches(self):
        for name in ['update-league-data.yml', 'player-game-logs.yml']:
            source = self.workflow(name)
            with self.subTest(workflow=name):
                self.assertIn('group: basketball-brawl-pages', source)
                self.assertIn('cancel-in-progress: false', source)
                self.assertIn("if: github.ref == 'refs/heads/main'", source)
                self.assertIn('bash .github/scripts/push-validated-data.sh main', source)
                self.assertNotIn('git push --force', source)

    def test_player_collection_keeps_explicit_activation_and_manual_dry_run(self):
        source = self.workflow('player-game-logs.yml')
        self.assertIn("vars.PLAYER_GAME_LOGS_ENABLED == 'true'", source)
        persist = source.split('      persist:', 1)[1].split('permissions:', 1)[0]
        self.assertIn('default: false', persist)
        self.assertIn('if: inputs.persist ||', source)
        self.assertIn('budget=200', source)
        self.assertIn('--canonical data/playerDailyData.csv', source)
        self.assertNotIn('npm run build', source)
        self.assertNotIn('deploy-pages@', source)

    def test_live_preserves_reviewed_backend_and_never_deploys_or_commits(self):
        source = self.workflow('live-scoring.yml')
        self.assertIn('ref: 473b669a806fdec6a589d95e7f0bd0d642a8a377', source)
        self.assertIn("if: github.ref == 'refs/heads/main'", source)
        self.assertNotIn('git commit', source)
        self.assertNotIn('deploy-pages@', source)
        self.assertNotRegex(source, re.compile(r'^  schedule:', re.MULTILINE))


if __name__ == '__main__':
    unittest.main()
