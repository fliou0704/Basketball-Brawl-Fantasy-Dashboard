# Modern dashboard production migration — review checkpoint

Prepared November 10, 2026. **Not merged or activated.** No Pages, Render, Actions, secret, variable, or branch-protection settings were changed. No live ESPN collection or production data writes were performed.

## Baselines and preserved history

| Ref | Audited commit | Role |
| --- | --- | --- |
| `main` | `c056c8be7e3479a6c247db8303e9c066df3b0018` | Existing production data/workflows and legacy app |
| `codex` | `bd430b4184ba8c4520ae890af2104543c194b7dc` | Deployed modern app, collectors, exporters and player archive |
| `archive/pre-modern-dashboard` | `c056c8be7e3479a6c247db8303e9c066df3b0018` | Permanent pushed backup of complete pre-migration main |
| Merge base | `c042396a64a5a0b2f52255450bc9337edf66642f` | Original shared history |

The baselines had 93 commits unique to main and 86 unique to codex. `modern-main-migration` starts at production main and performs a real merge of codex, with explicit conflict resolution and migration changes in the merge result. Both histories remain ancestors; no reset, force push, rebase or whole-tree replacement is used. Use a **merge commit**, not squash/rebase, when approving the migration PR so this ancestry is preserved.

The requested default `codex/…` feature prefix cannot coexist with an actual branch named `codex` in Git's ref namespace. The temporary branch is therefore `modern-main-migration`.

## Reconciliation decisions

### Canonical production inputs win byte-for-byte

All eight newer main inputs are retained verbatim, including prior historical corrections:

| Input | Rows at audit |
| --- | ---: |
| `data/basketballBrawlLeagueData.csv` | 960 |
| `data/playerMatchupData.csv` | 12,646 |
| `data/playerDailyData.csv` | 41,207 |
| `data/activityData.csv` | 2,417 |
| `data/playerMetadata.csv` | 367 |
| `data/scoringPeriodMatchupMap.csv` | 692 |
| `data/seasonMetadata.json` | Complete main document, including fantasy calendar and NBA schedule metadata |
| `data/currentLeague.json` | November 10, 14:53:31 UTC ownership snapshot; 163 roster entries |

[Provenance](modern-main-migration-provenance.json) records exact refs, hashes and sizes. Canonical hashes were checked before and after frontend regeneration. No historical or current canonical rows were discarded or recalculated. The comprehensive player archive/report, 2,714 season summaries and normalized static shards are retained from codex: 108,051 appearances, with current archive statistics through November 6. Their older statistical date is an existing limitation, not evidence that main's newer fantasy CSVs were replaced.

### Modern code and safeguards

The codex React app, all pages including Top 150, backend utilities, calendar/schedule integration, live adapter/publisher, tests and exporters are retained. Overlapping shared safety/updater code resolves to codex's developed versions, which include the earlier main date fix plus schema checks, raw 3PA handling, lineup-response completeness, metadata refresh and credited-start rules. Existing main push-recovery helper and production workflow behavior are retained and adapted to one checkout. The full backend suite verifies compatibility with main's current inputs.

All frontend exports were regenerated from the reconciled main inputs. Current fantasy ownership is November 10, while NBA-wide ranking statistics retain their separately labeled November 6 cutoff. All 163 roster entries remain represented; historical ownership is not inferred from today's roster.

The newer production CSV includes verified raw three-point attempts. An old Sprint test assumed attempts were always missing because it read codex's older CSV. Its assertion now compares to the actual source: preserve known attempts and preserve missing values as unknown. Scoring/export calculations were not modified to satisfy that test.

### Legacy Render retirement

The root Dash entry point (`basketballBrawlApp.py`), Home and Power Rankings modules, Dash/Plotly/Gunicorn dependencies and tracked OS/bytecode artifacts are removed from the proposed production tree. No Render blueprint, Dockerfile or Procfile was found; the visible legacy deployment direction was the root Dash app, requirements and README's Render URL. External Render service settings are not exposed by this repository audit.

Three original callback modules move to `tests/fixtures/legacy_dash/`, with parity tests updated to read them there. They are parsed as source with inert components; they are not imported or served as an app. Keeping these oracles preserves independent historical calculation checks. Shared backend/data utilities remain. The complete runnable old implementation and original requirements stay available on the permanent archive branch.

## Proposed workflow behavior after approval

| Workflow | Source / writes | Trigger and deployment boundary |
| --- | --- | --- |
| `update-league-data.yml` | One writable main checkout; same safeguarded updater and exact canonical allowlist | Original three-hour cadence (daily in summer), main-only manual dispatch; export/tests/build, bounded push recovery, deploy only changed payloads |
| `frontend-pages.yml` | Immutable triggering main SHA; regenerate from its own main data | Main frontend/data pushes or manual main dispatch only; main guard on both build and deploy; no codex production deployment |
| `player-game-logs.yml` | Main collector, main canonical reference, main-only approved outputs | Daily 11:43 UTC remains configured but gate is **disabled**; manual dispatch now targets main and defaults to `persist=false` |
| `live-scoring.yml` | Reviewed immutable backend `473b669a806fdec6a589d95e7f0bd0d642a8a377`, plus current main season metadata | Cloudflare continues dispatching main with `publish=true`, `force=false`; explicit main guard; no native cron, data commits or Pages deployment |

The live backend pin is valid and becomes part of retained main ancestry through the history-preserving merge. It is deliberately not changed to moving codex or moving main. Cloudflare code, deployment, authentication, game windows, cache and Supabase policies are unchanged. Existing public Vite variable names/values and backend secrets are unchanged.

Canonical, player-data and Pages workflows share `basketball-brawl-pages`, cancellation disabled. This serializes production data writers and deployments. A concurrent human main commit can still cause a safe push rejection; there is no automatic rebase or forced overwrite. The existing push helper retries only transient failures, detects ambiguous successful pushes and refuses stale writes. Both Pages deployment paths allow the same deployment twenty minutes.

Player-data commits retain `[skip pages]` and write only archive/report/season summaries/static shards. GitHub-token pushes do not create recursive push workflows; the explicit marker also avoids unnecessary frontend builds if another authorized token is used. The next canonical run detects changed ranking exports and deploys them. Canonical updates perform their own deployment, rather than relying on a token-generated push event. Live publication remains independent and creates no Git commits.

The obsolete cron diagnostic is removed from the proposed tree; real canonical/player schedules and external live scheduling remain. No recurring job is enabled by this preparation.

## Current repository settings, inspected read-only

- Default branch: main; Actions enabled; all actions allowed.
- Pages build type: `workflow` (GitHub Actions). The API's source field is main `/`; the effective frontend selector today is the workflows' codex checkout/trigger, which this PR replaces. No Pages UI switch is required to select main code once the new workflows are approved.
- `github-pages` environment currently allows both main and codex. No required reviewer rule was reported. At the approved switch, restrict this policy to main before resuming development pushes. A push uses the workflow version on its own branch: the old codex workflow can still request a deployment until codex is synchronized. Main-only environment policy closes that transition gap. This settings change is deliberately left for owner approval.
- Main and codex are currently unprotected. Consider reviewed-PR requirements with explicitly designed automation permissions; do not enable rules blindly that would prevent the existing data bot from persisting validated data. Protect the archive against deletion/force updates as appropriate.
- `PLAYER_GAME_LOGS_ENABLED` is absent/disabled; it remains so. Public live scoring configuration is already enabled and validated; no secret/service-role key was used for a frontend build.

## Validation

- Canonical production files: eight exact byte/hash comparisons, unchanged after exports.
- Player archive: exact comparisons to the audited modern commit; no collection/write attempt.
- 253 backend tests plus six production/CI-boundary tests.
- 171 exporter tests, 105 frontend tests, five push-recovery tests and 19 Cloudflare scheduler tests.
- All workflow YAML parses; every workflow Bash step passes syntax validation. Boundary tests reject codex checkouts/pushes and non-main production guards, preserve the player activation gate and immutable live pin, and enforce writer/deployment serialization.
- Production Vite builds with live scoring disabled and with actual public production configuration enabled.
- Built-preview Chrome checks at 375px and 1280px: both ranking entry points, 150 rows in both metrics, all 163 owners, filters, seasons, historical ownership isolation and on-demand game logs. Real local HTTP requests return the expected JSON under the Pages base path. Separate HTTP/schema/coverage/empty-state regressions pass.
- Home, Standings, Team Overview, Historical H2H, Record Book and Scoreboard smoke checks pass. Home and Scoreboard make successful anonymous Supabase reads; historical season selection does not reload the document. Existing frontend tests cover safe live overlays, stale/mismatched fallback, projections and selection preservation. No new fresh in-game publication is claimed from this daytime read-only verification.

These are local migration validation results. New workflow paths cannot be proven by a production run before merge, and no workflow was dispatched from this branch. Review and verify actual main deployments after approval.

## Approval checklist and remaining risks

See [the final switch checklist and modern recovery runbook](modern-main-switch-checklist.md) for exact-commit remote CI, environment policy verification, Render owner actions, and recovery to deployed modern commit `bd430b4184ba8c4520ae890af2104543c194b7dc` with current data.

1. **Before merging:** disable Render auto-deploy or pin the legacy service to `archive/pre-modern-dashboard` in the Render account. Removing its root entry point otherwise risks a failing legacy Render auto-deploy. This preparation has not changed that account or retired the live service externally.
2. Fetch main again immediately before approval. If canonical updates advanced, merge latest main into this migration branch, retain the newest main canonical inputs, regenerate exports and re-run affected checks. The provenance file describes the audited snapshot, not a freeze on production updates.
3. Keep the player activation gate disabled. The previous codex dry run hit the 200-request cold-cache budget. GitHub caches are branch-scoped: a future main trial must not assume it can restore codex's saved cache. Resume/initialize through bounded non-persisting trials on main only after separate approval; validate artifacts before persistence or activation. This migration neither solves nor conceals that outstanding bootstrap work.
4. At the approved switch, restrict the Pages environment deployment branch policy to main and keep codex frozen until synchronization. Main workflow edits alone cannot disable an older workflow file still present on codex. Then approve and merge this PR using a merge commit. Its main push will run the production Pages workflow. Verify the exact main SHA, every page, canonical ownership and live-read fallback publicly. Confirm the canonical job's next scheduled run and the continuing Cloudflare dispatches. Keep native scheduler timing limitations in mind; a registered cron is not proof of an executed scheduled run.
5. Synchronize codex as described below before resuming development. Confirm the Pages environment remains restricted to main. Do not manually dispatch the old codex workflow version during transition: old branch versions can still contain their prior dispatch behavior. No codex pointer has been changed during preparation.

The archive's main snapshot, the production main pointer, the current codex pointer, the Pages environment policy, existing repository variables and live/public site remain unchanged by this draft preparation. Only archive/migration refs are pushed. Until approval and synchronization, the existing production workflows still publish codex as before: avoid merging new development into codex during the review window if it must remain undeployed.

## Synchronize codex after the switch

Do this only after the migration is approved and main's production deployment is verified, using a clean checkout. Preserve any local work first. Do not reset or force push.

```sh
git fetch origin
git switch codex
git pull --ff-only origin codex
git merge --ff-only origin/main
git push origin codex
```

Fast-forward is possible if codex has not advanced beyond the audited modern parent. If it has new development commits, create a temporary synchronization branch from latest codex, merge main normally, review conflicts (especially workflows) and open a PR into codex. Preserve main's production-only workflow boundaries. No feature work needs to be discarded.

Thereafter, features start from synchronized codex and return there through review; promote reviewed releases to main with merge commits, then merge main back into codex after each release and before long-running feature work. Avoid repeated cherry-picks or squashes between these long-lived branches, which would duplicate development history and resurrect conflicts.

All automatic raw-data writes go to **main only**. Do not mirror bot commits to codex, run a second data writer there, or commit regenerated frontend JSON on every update. Develop against saved data or a read-only main source checkout, and let deployment regenerate JSON. Main will still accumulate intentional data commits under the existing Git architecture; merging shares their existing identities instead of creating a second divergent stream. Eliminating those main commits entirely would require a separately reviewed data-storage architecture change and is outside this migration.

## Rollback

The permanent archive is the pre-switch legacy recovery reference. If a future approved switch fails, stop the affected production workflow, restore the last known-good Pages artifact/configuration through a reviewed correction, and preserve current canonical and player archives. Do not reset main to the archive or blindly revert data-bearing commits after new updates. Backend live rollback remains independent via the existing workflow/Cloudflare controls and frontend feature flag. No rollback, environment-policy change, Render change or workflow activation has been performed here.
