> Follow-up: see [scheduler investigation](live-scoring-scheduler-investigation.md) for the active-state API check, non-forced manual publication and current scheduled-run evidence.

# Live scoring production activation

Stage 3B starts from codex `473b669` and main `af25cd9`. The completed React integration already exists on codex; activation requires public build configuration and a normal Pages build, not a merge of React into main. Unrelated working-tree changes are excluded.

## Backend

PR #2: https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/pull/2
Main merge: `808ca4953deb6f35ec6d84307c3f4db45b0d6d9b`.

Only `.github/workflows/live-scoring.yml` changed. Cron `2-59/5 * * * *` is UTC; job conditions require schedule + main + `LIVE_SCORING_AUTOPUBLISH=true`. Manual execution defaults to dry-run. Scheduled execution publishes only after the existing precheck and live NBA status gate permit it. Backend remains pinned to `473b669a806fdec6a589d95e7f0bd0d642a8a377`.

Main's current canonical season metadata supplies the verified calendar/fixtures. Pregame, live/overtime, 30-minute postgame, New York midnight and schedule uncertainty behavior is unchanged. Five-minute scheduling is best effort: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

No generated live data is committed; the job has read-only Git permissions and no build/deploy steps. Concurrent runs serialize; cache loss does not weaken stale/atomic Supabase publication. Backend credentials remain in the existing four Actions secrets.

Observed from merge at **2026-11-01 00:36:26 UTC** through **01:06:41 UTC** (30 minutes 15 seconds): **zero scheduled runs**, despite current canonical metadata opening the game window. The direct workflow API returned `total_count=0` for `event=schedule`. Workflow state is active, main is the default branch, Actions is enabled, and `LIVE_SCORING_AUTOPUBLISH=true`. GitHub public status reported Actions operational. No scheduled publication or five-minute cadence is claimed. Backend schedule remains enabled for subsequent observation; Phase B is blocked until multiple real scheduled publications pass.

The prior Stage 3A manual run `41255742308` succeeded in 30 seconds, but does not count as scheduled evidence. Its stored snapshot remained verified at `2026-11-01T00:13:11.647749Z`, revision `7a9f63ca2adfe38a450306f68de59cf4690e70b7a07f4af1f9716381b4b90315`, season 2027, week 2, scoring period 12, 10 teams, 162 players, 7 games and 87,350 bytes. Anonymous readback, official matchup score agreement and bench/IR credit rules passed. The real snapshot passes frontend validation when checked at its collection time and is correctly rejected now as stale; canonical Home is retained. No fresh Stage 3B publication was fabricated or manually substituted.

## Frontend configuration

Draft, unmerged PR #3 (public build environment only; commit `f48c06958417879313b634e55061044235259ad1`): https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/pull/3

After multiple successful scheduled publishing runs and verified Supabase freshness, merge PR #3 and configure both Pages builders using these repository variables:

- `VITE_SUPABASE_URL`: public project URL.
- `VITE_SUPABASE_PUBLISHABLE_KEY`: publishable key only.
- `VITE_LIVE_LEAGUE_ID`: `aeab467a-499a-4684-91af-e18f4966f7fa` (Supabase league UUID).
- `VITE_LIVE_ESPN_LEAGUE_ID`: `609694684`.
- `VITE_ENABLE_LIVE_SCORING`: `true` only after the backend gate passes.

`VITE_SUPABASE_LEAGUE_ID` is not used by the code. No secret/service-role key belongs in VITE configuration. When Phase B resumes, pass public configuration directly to GitHub variables without printing values or changing local .env. Then push a reviewed frontend-path change through the existing codex Pages workflow (without `[skip pages]`) and verify real Home/list/detail updates, selection/scroll preservation and canonical fallback before declaring activation complete.

Production URL: https://fliou0704.github.io/Basketball-Brawl-Fantasy-Dashboard/
Frontend activation/deployment **withheld**. All public VITE repository variables remain unset, so the live flag defaults false. The production site was inspected and continues displaying canonical scores. No new Pages deployment was triggered by this stage; open-site live updates and fresh scheduled-score changes cannot yet be verified.

The canonical updater's proposed (unmerged) frontend preparation change is its public build env block; its commands, schedule, source data and Git persistence are unchanged. Dash is untouched. The shared React store polls scoped metadata, downloads changed revisions and rejects stale/mismatched/out-of-order snapshots, preserving canonical data and projections. No page reload is part of polling.

## Validation

- 224 backend tests passed, including window/rollover/atomic publisher safety.
- Additional offline checks passed across both repeated 01:30 New York hours at the November DST transition and the 30-minute UTC postgame expiry.
- Scheduled/manual/ref/activation matrix and pinned/no-commit/no-deploy workflow checks passed.
- 91 frontend tests passed, including stale/error/identity/period fallback, official scores, bench/IR, projection preservation and polling cleanup.
- Enabled and disabled production builds passed; configured ESPN/Supabase secret values and secret-key markers were absent from the enabled bundle.
- Real stored-snapshot/public-readback correctness and stale fallback passed; fresh scheduled publication and enabled public-site checks remain blocked.
- Main/codex branch heads did not advance from live-data activity. The main diff from Stage 3A contains only the live workflow; the canonical workflow and Dash application are unchanged. Latest canonical run `41255401270` succeeded independently at 00:08 UTC, before activation.
- Required backend secret names are present and unchanged. No manual secret setup is missing. Public frontend variables are intentionally not configured before the backend gate passes.

## Independent rollback

Stop subsequent scheduled backend publications (manual dispatch remains explicit):

```sh
gh variable set LIVE_SCORING_AUTOPUBLISH --body false --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
```

For an immediate in-flight stop, find the running live job and cancel that ID only:

```sh
gh run list --workflow live-scoring.yml --status in_progress --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
gh run cancel RUN_ID --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
```

Disable the browser overlay independently:

```sh
gh variable set VITE_ENABLE_LIVE_SCORING --body false --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
```

Then rerun the most recent successful `Frontend prototype Pages` workflow run from codex with `gh run rerun RUN_ID --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard` (without `--failed`), and verify the disabled build. Reruns read current repository variables. A variable change alone does not rewrite deployed JavaScript. The next changed canonical Pages deployment also uses the same disabled flag. No historical data or snapshots need deletion.

A browser already holding an enabled bundle keeps it until reload; expired live data automatically falls back after ten minutes. If immediate withdrawal of public data is needed, the existing league visibility control can revoke public reads; do not delete canonical history.

## Usage

Typical game-window collection is one public status request plus two adapter requests per run (~36 ESPN requests/hour at the target cadence), with extra bounded checks near midnight/retries. Fresh complete off-hours/no-game windows use the cheap no-network gate. The Actions runner still starts for each cron tick; actual execution delay/cadence and duration must be measured. Supabase stores one current row per league/season; each changed ~85 KB snapshot is read back after publication. Browser metadata polling is shared every ~20 seconds while active and slows off-hours; full bodies download only on revision changes. Monitor Actions minutes/cache and Supabase egress in their dashboards; no new paid service is introduced.
