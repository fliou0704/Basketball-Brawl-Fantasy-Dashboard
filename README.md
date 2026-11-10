# Basketball Brawl

The modern React dashboard presents ESPN fantasy basketball data, historical league records, live scores, and NBA-wide Top 150 rankings.

[Public dashboard](https://fliou0704.github.io/Basketball-Brawl-Fantasy-Dashboard/) · [Migration review and rollout](docs/modern-main-migration.md)

## Branches

- `main`: stable modern production code and the only automated data-write branch after the migration is approved.
- `codex`: feature integration and development; its commits do not deploy production after migration.
- Feature branches: temporary review branches into `codex`; promote reviewed releases from `codex` to `main` with a merge commit.
- `archive/pre-modern-dashboard`: permanent pre-migration legacy Dash/Render snapshot. Do not rewrite or delete it.

This branch prepares that production switch; the migration PR must be reviewed and merged before these workflow rules take effect.

## Local development

Use Python 3.11 and Node 22.12 or newer. No credentials are needed to export or browse the saved datasets.

```sh
pip install -r requirements.txt -r frontend/requirements-build.txt
npm ci --prefix frontend
python frontend/scripts/generate_all.py
npm run dev --prefix frontend
```

Open the URL printed by Vite, including `/Basketball-Brawl-Fantasy-Dashboard/`. Generate exports again when source data or exporters change. Production validation uses `npm run build --prefix frontend` and `npm run preview --prefix frontend`.

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s frontend/scripts -p 'test_*.py' -v
npm test --prefix frontend
```

## Production data and deployment

The existing canonical job retains its cadence and safeguarded ESPN writes, regenerates all frontend JSON, validates/builds it, commits changed canonical inputs on `main`, and deploys changed Pages output. A separate Pages workflow deploys approved `main` frontend changes or a manual `main` dispatch. Shared concurrency serializes production data writes and deployments. No automatic job commits generated browser JSON.

Cloudflare still dispatches the existing pinned live-scoring backend on `main`; Supabase supplies a stale-safe browser overlay. Live snapshots are never committed and never trigger Pages. Public Vite configuration is documented in [the live-scoring rollout](docs/live-scoring-rollout.md). Backend credentials belong only in the existing environment/GitHub Secrets; never use a `VITE_` prefix for them.

The comprehensive player-data workflow remains gated off after its 200-request cold-cache trial stopped safely. Do not enable it as part of migration. See [player-ranking-data.md](docs/player-ranking-data.md) for bounded checkpoint resumption and future activation. Once separately validated, it will persist only its archive/report/summaries/static shards on `main`; the next canonical build publishes updated rankings.

## Legacy application

The Dash/Render entry point and dependencies are retired in this proposed tree. The complete old implementation remains on the archival branch. Three callback source files remain under `tests/fixtures/legacy_dash/` solely as independent regression oracles. External Render auto-deploy must be disabled or pinned to the archive before approving the production switch; repository changes do not change Render account settings.
