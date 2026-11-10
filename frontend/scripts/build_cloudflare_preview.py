"""Read-only preview build: feature code + freshly fetched approved main data."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
APPROVED_REPOSITORY = 'https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard.git'
# PR #14 introduces this source. Never replace a file already approved on main.
NEW_FEATURE_INPUTS = ('seasonEndRosters.json',)
REQUIRED = ('basketballBrawlLeagueData.csv', 'playerMatchupData.csv', 'playerDailyData.csv',
            'activityData.csv', 'playerMetadata.csv', 'scoringPeriodMatchupMap.csv',
            'seasonMetadata.json', 'currentLeague.json', 'playerSeasonStats.csv',
            'playerGameLogs.csv', 'playerGameLogs.report.json', 'player-static/index.json')


def run(args, cwd, **kwargs):
    return subprocess.run(args, cwd=cwd, check=True, **kwargs)


def validate_environment(env):
    if any(env.get(k) for k in ('ESPN_S2', 'SWID', 'SUPABASE_SECRET_KEY', 'SUPABASE_SERVICE_ROLE_KEY')):
        raise ValueError('Preview builds must not receive backend credentials')
    for name, value in env.items():
        if value and name.startswith('VITE_') and any(s in name for s in ('SECRET', 'SERVICE_ROLE', 'ESPN_S2', 'SWID')):
            raise ValueError('Preview frontend configuration contains a forbidden credential field')
    key = env.get('VITE_SUPABASE_PUBLISHABLE_KEY', '')
    if key and not key.startswith('sb_publishable_'):
        raise ValueError('Preview Supabase key must be publishable')


def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file()}


def copy_code(repo, target):
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=repo).decode().split('\0')
    for name in filter(None, paths):
        rel = Path(name)
        if (rel.parts[0] == 'data' or name.startswith('frontend/public/data/')
                or rel.name == '.env' or rel.name.startswith('.env.')):
            continue
        src = repo / rel
        if src.is_symlink():
            raise ValueError('Preview inputs must not link outside the tracked checkout')
        if src.is_file():
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)


def prepare_data(repo, approved, target):
    for name in REQUIRED:
        if not (approved / name).is_file():
            raise ValueError('Approved main data is incomplete; refusing stale branch fallback')
    shutil.copytree(approved, target)
    additions = []
    for name in NEW_FEATURE_INPUTS:
        branch_input = repo / 'data' / name
        if not (target / name).exists() and branch_input.is_file():
            if branch_input.is_symlink():
                raise ValueError('Preview data must not use external links')
            shutil.copyfile(branch_input, target / name)
            additions.append(name)
    return additions


def build(repo=ROOT):
    validate_environment(os.environ)
    if sys.version_info < (3, 11):
        raise ValueError('Preview build requires Python 3.11 or newer')
    env = dict(os.environ, VITE_ENABLE_LIVE_SCORING=os.environ.get('VITE_ENABLE_LIVE_SCORING', 'false'))
    # Exporters must resolve metadata from the isolated approved data, not a host setting.
    for key in ('BRAWL_REFERENCE_DIR', 'PYTHONPATH'):
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix='brawl-preview-') as tmp:
        tmp = Path(tmp); approved = tmp / 'approved'; workspace = tmp / 'workspace'
        run(['git', 'clone', '--quiet', '--depth', '1', '--filter=blob:none', '--sparse',
             '--single-branch', '--branch', 'main', APPROVED_REPOSITORY, str(approved)], repo)
        run(['git', 'sparse-checkout', 'set', 'data'], approved)
        main_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=approved, text=True).strip()
        workspace.mkdir(); copy_code(repo, workspace)
        additions = prepare_data(repo, approved / 'data', workspace / 'data')
        before = hashes(workspace / 'data')
        run([sys.executable, '-m', 'venv', str(tmp / 'venv')], workspace)
        python = str(tmp / 'venv/bin/python')
        run([python, '-m', 'pip', 'install', '--disable-pip-version-check', '-r',
             'frontend/requirements-build.txt'], workspace, env=env)
        run(['npm', 'ci', '--prefix', 'frontend'], workspace, env=env)
        run([python, 'frontend/scripts/generate_all.py', '--source-dir', 'data'], workspace, env=env)
        if hashes(workspace / 'data') != before:
            raise ValueError('Preview exporter changed source data; build rejected')
        provenance = {'schemaVersion': 1, 'preview': True, 'canonicalCommit': main_sha,
                      'featureCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
                      'featureOnlyInputs': additions}
        (workspace / 'frontend/public/data/preview-build.json').write_text(json.dumps(provenance) + '\n')
        run(['npm', 'run', 'build', '--prefix', 'frontend', '--', '--mode', 'cloudflare-preview'], workspace, env=env)
        if hashes(workspace / 'data') != before:
            raise ValueError('Preview build changed source data; build rejected')
        output = repo / 'frontend/dist-cloudflare'
        if output.is_symlink():
            raise ValueError('Preview output must not be an external link')
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(workspace / 'frontend/dist', output)
        print('Preview built from approved main commit ' + main_sha)
        print('Feature-only new inputs: ' + (', '.join(additions) or 'none'))


if __name__ == '__main__':
    build()
