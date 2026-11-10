# Final production switch gates and modern Pages recovery

PR #13 remains draft. This document and the read-only CI are preparation, not approval to switch. No deployment, production setting, secret, Render service, daily-player gate or production branch was modified.

## Exact-commit remote CI

`.github/workflows/migration-ci.yml` runs on pushes to `modern-main-migration`. Its check tests the pushed commit itself: checkout uses `github.sha` and verifies `git rev-parse HEAD == GITHUB_SHA`. It does not test a synthetic PR merge or a moving branch tip.

The token has only `contents: read`; credentials are not persisted. There is no environment, deployment job, secrets access, live collector, publisher, commit, push, or data-persistence step. Test fixtures and generated frontend JSON are written only inside the disposable runner workspace; `data/` must remain clean. Existing public Vite variables are used only for the enabled build.

It verifies all workflow files plus the documentation-only recovery workflow with checksum-verified actionlint 1.7.12, backend/boundary tests, offline push-recovery tests, scheduler unit tests, all exports and exporter tests, frontend tests, and disabled/enabled production builds. PR #13's current head and its matching successful check/run are the review evidence. Do not accept an older green run if the migration head subsequently changes.

## Production freshness and synchronization proof

The original production baseline is `c056c8be7e3479a6c247db8303e9c066df3b0018`. The permanent legacy archive remains at that exact commit. The modern parent is `bd430b4184ba8c4520ae890af2104543c194b7dc`. The first migration commit is `2f36047876a0dec9cc2be35b29be430ca2b8273a`, with both of those commits as parents; follow-up validation/docs commits retain that ancestry.

At each review checkpoint fetch origin and compare actual main to `docs/modern-main-migration-provenance.json`'s `productionBase`. Check the canonical paths against current main, not merely the original backup. If main advances, merge it normally into the migration branch, preserve its newest canonical inputs, regenerate, update the provenance, and let exact-commit CI run again. Do not reset/force a production branch or overwrite the permanent archive.

With no new development, the codex synchronization is a **true fast-forward**, not a content approximation: codex's `bd430b4` is an ancestor of the migration head. A merge-commit merge of PR #13 makes that head an ancestor of new main, so codex can advance directly to it. Verify before the future push:

```sh
git fetch origin
git merge-base --is-ancestor origin/codex origin/main
# Exit 0 is required. In a clean codex checkout:
git switch codex
git pull --ff-only origin codex
git merge --ff-only origin/main
git push origin codex
```

These synchronization commands are **not run during preparation**. Use a merge commit for PR #13; squash/rebase merging would remove this ancestry guarantee. If codex has advanced, stop the fast-forward path and reconcile through a normal reviewed synchronization merge. All automated canonical/player writes then target main only; share those existing commits by merges rather than creating/cherry-picking a second automated data stream.

## Required Pages environment restriction

Current read-only API inspection reports:

- Environment: `github-pages`.
- `deployment_branch_policy`: `protected_branches=false`, `custom_branch_policies=true`.
- Branch rules: `main` (ID `59645385`) and `codex` (ID `59647482`).

At the approved switch, GitHub repository **Settings → Environments → github-pages → Deployment branches and tags** must use **Selected branches and tags**, with **one Branch rule exactly `main`**. Remove `codex` and any other branch/tag wildcard rule. Do not choose “Protected branches only”: main is currently unprotected. Do not broaden to “No restriction.” Preserve the environment and its other settings.

Perform this after freezing development/settling existing Pages runs, before merging PR #13 or resuming codex pushes. This policy checks the workflow run's branch, not the code checked out in a step. It blocks the older codex workflow's deployment job during the transition; the main recovery workflow can still check out the pinned known-good code. Workflow files alone cannot constrain old branch copies.

**Owner approval required; not executed.** The owner can change it in the UI, or authorize this agent to remove only the codex rule. The currently identified equivalent mutation is:

```sh
# FUTURE APPROVED MUTATION ONLY: re-read policy IDs first.
gh api --method DELETE repos/fliou0704/Basketball-Brawl-Fantasy-Dashboard/environments/github-pages/deployment-branch-policies/59647482
```

Immediately verify using read-only calls:

```sh
gh api repos/fliou0704/Basketball-Brawl-Fantasy-Dashboard/environments/github-pages --jq '.deployment_branch_policy'
gh api repos/fliou0704/Basketball-Brawl-Fantasy-Dashboard/environments/github-pages/deployment-branch-policies --jq '[.branch_policies[] | {name,type}]'
```

Required results: custom policies true, protected-only false; exactly `[{"name":"main","type":"branch"}]`. These two positive assertions plus the workflow main guards are the non-deploying verification. After the separately approved merge, verify a real successful deployment from main. Do not deliberately launch a forbidden codex deployment as a test. See [GitHub's environment documentation](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

## Render shutdown: owner dashboard action

This repository does not expose an authorized Render connection/service identifier, and no Render account settings were inspected or changed. **The owner needs to complete and confirm this in Render, or explicitly provide an authorized service connection.**

In Render Dashboard, open the legacy Basketball Brawl web service, then **Settings → Build & Deploy → Auto-Deploy → Off**, and save. Confirm Off remains after refresh, the connected repository/branch, and that no deploy is building or queued. Let a healthy in-flight deploy finish or cancel the specifically identified unwanted deploy. Check any separately configured CI/deploy-hook integration, because turning off commit-triggered deploys does not disable an external manual hook.

Leave the last healthy service running during the switch; turning off auto-deploy is sufficient to prevent the main merge from launching the removed Dash entry point. Do not delete the service or change its secrets. If retaining a runnable archival service is desired later, separately approve selecting `archive/pre-modern-dashboard` as its source branch while auto-deploy stays off. Suspension/deletion is a separate post-switch decision, not required here. See [Render's deployment controls](https://render.com/docs/deploys).

## Concrete recovery to the last known-good modern site

### Verified recovery identity

- **Modern recovery source commit:** `bd430b4184ba8c4520ae890af2104543c194b7dc` (Top 150 already integrated).
- [Successful Pages run 42852828968](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/42852828968), push on codex.
- Deployment `7687558056`, confirmed `success` at `2026-11-10T16:18:15Z`.
- Original artifact `github-pages`, ID `13781821092`, 10,252,865 bytes, expires `2026-11-11T16:17:52Z`.

The expiring original artifact is evidence, not the durable recovery dependency. Its frozen data would be older, and re-running its old codex deployment after main-only restriction would be blocked. **Do not reset main to this commit, revert canonical updates, re-enable codex production deployment, or substitute the legacy Render archive.**

### Prepared deployment recipe (not installed or executed)

[modern-pages-recovery.yml.example](modern-pages-recovery.yml.example) is a complete, linted one-shot workflow template under `docs/`, not `.github/workflows/`. It cannot dispatch or deploy in its current location. It:

1. Runs only via manual dispatch on main under the existing Pages concurrency/environment policy.
2. Checks out current main read-only into `current/` and the exact known-good modern commit into `recovery/`.
3. Regenerates the old modern code's exports from **current main's complete `data/`**, including newer canonical CSV/calendar/rosters and current comprehensive player archives. The known-good exporter supports that source override. Data is never restored from the old commit into main.
4. Validates exports/frontend tests, builds with the existing public Vite configuration, and uploads/deploys the Pages artifact. A failed build/validation blocks deployment.
5. Records the current source SHA in the run summary and asserts that `current/data/` is unchanged. It has no write token, commit, push, ESPN collection or Supabase publication step. Only the deployment job has the necessary Pages/OIDC permissions.

The known-good source commit and deployment record are verified. The example passes actionlint. The migration CI does **not** run this recovery workflow or claim a recovery deployment was tested. Future data/schema incompatibility must fail validation, not bypass safeguards.

### Future authorized rollback steps

If the approved production switch later fails:

1. Obtain rollback approval. Freeze development and pause the two Pages producers (`frontend-pages.yml`, `update-league-data.yml`) so they cannot overwrite the recovery deployment. Settle/wait for identified in-flight production writes/deployments before dispatching recovery; inspect specific run IDs instead of canceling all workflows. Keep the player gate disabled. Keep Cloudflare live publication and Supabase unchanged unless the incident specifically concerns them. Keep the main-only Pages policy.
2. In a clean checkout, prepare a workflow-only recovery PR:

   ```sh
   git fetch origin
   git switch -c modern-pages-recovery origin/main
   cp docs/modern-pages-recovery.yml.example .github/workflows/modern-pages-recovery.yml
   git add .github/workflows/modern-pages-recovery.yml
   git commit -m "Prepare pinned modern Pages recovery without reverting data"
   git push -u origin modern-pages-recovery
   gh pr create --base main --head modern-pages-recovery --title "Recover known-good modern Pages with current data" --body "Manual-only recovery; source bd430b4184ba8c4520ae890af2104543c194b7dc, data from current main, no canonical writes."
   ```

3. Review that the PR changes only the workflow template. Approve/merge normally, then dispatch **on main**:

   ```sh
   gh workflow run modern-pages-recovery.yml --ref main
   ```

   This does not require permission for codex deployments or a Pages branch-setting change. Watch the actual run, generated tests, recorded main source SHA and deployment result. Stop on failure; do not skip validation or force-push.
4. Verify public Home, Scoreboard, standings/history, Top 150, current ownership, game logs and live fallback. The artifact uses latest main inputs as of checkout, rather than the old deployment's frozen snapshot. Confirm canonical/player data have no rollback commit or diff.
5. Keep the regular Pages producers paused until the migration/workflow defect has a reviewed fix; otherwise they could overwrite the recovered site. Resume the independent canonical cadence only after verifying that fix. Remove the one-shot recovery workflow through a reviewed follow-up. Data and histories are preserved throughout.

This is a forward, workflow-only recovery change built from a pinned modern source with current data. It is not a destructive repository rollback. No recovery PR, pause command, dispatch or production change has been performed.

## Go/no-go gate

Production remains **NO-GO until** the current exact migration head has successful read-only CI, main freshness is reconfirmed, the owner confirms Render auto-deploy Off, the owner approves/applies and verifies main-only Pages policy, and the owner explicitly approves the migration merge/deployment. Player-data activation is excluded. After those gates, merge normally and verify main deployment before the true fast-forward codex synchronization.
