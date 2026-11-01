# Live-scoring scheduler investigation — 2026-11-01 UTC

## Conclusion

No concrete repository configuration defect was identified. The observed failure is **absence of GitHub-created schedule runs**, before any job or Python game-window check. GitHub scheduler delivery delay and an internal workflow schedule-registration/discovery issue cannot be distinguished through the public APIs. Do not label either a proven root cause. Automatic publishing is configured/enabled but not yet demonstrated operational.

PR #3 remains draft/unmerged. All frontend VITE repository variables remain absent, so production live scoring stays disabled. No Pages build/deployment or backend source change was made for this investigation.

## Evidence

- Default branch is main; public repository, not a fork, archived or disabled. Actions permissions: `enabled=true`, `allowed_actions=all`, `sha_pinning_required=false`.
- Workflow ID `403162553`, path `.github/workflows/live-scoring.yml`, state **active** before investigation. Initial `updated_at` still reflected initial installation; that timestamp alone does not prove missing schedule registration.
- The Contents API (`ref=main`) exactly matches fetched origin/main `808ca4953deb6f35ec6d84307c3f4db45b0d6d9b`. Workflow blob: `094224b455e36b2994f10e439235bf7f7165436d`.
- Cron `2-59/5 * * * *` is valid five-field POSIX syntax: minutes 02, 07, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57 UTC, including five-minute hour rollover. No timezone option is configured; New York/DST logic is internal to the existing gate, not this UTC cron.
- Both `schedule` and `workflow_dispatch` triggers are present. The scheduled job explicitly allows schedule + refs/heads/main + repository variable `LIVE_SCORING_AUTOPUBLISH=true`. Scheduled `PUBLISH` evaluates true; manual publishing still requires its explicit boolean input.
- Scheduler and manual work serialize in the existing concurrency group; runtime remains pinned to reviewed `473b669a806fdec6a589d95e7f0bd0d642a8a377`. No Git commit or Pages deployment action is present.
- The cron-change merge author is repository owner `fliou0704` (normal User account, admin permission), with recent repository activity. No evidence of the documented 60-day inactivity disable or deprovisioned enterprise actor case.
- Direct `runs?event=schedule` returned total_count=0 before the enable diagnostic. The API initially listed only the earlier successful manual run `41255742308`.
- Canonical workflow ID `225436151` has scheduled history, most recently `41255401270`, created **00:08:13 UTC**. That precedes live schedule installation at **00:36:26 UTC**. Repository-wide schedule query after that installation also returned zero. The older canonical successes do **not** establish a simultaneous positive control or prove this is isolated to the live workflow. The next nominal winter canonical tick is 03:17 UTC; its cron and code were not changed.
- Repository Events API is not an Actions schedule-event log; the workflow-runs API is the relevant evidence. It showed recent PR activity but cannot expose internal scheduler queue state or dropped events.

A run skipped at the job-level condition would still have a run record. A Python window no-op would have a successful job with skipped downstream publication. Neither can account for zero schedule run records. Changing the game-window conditions would therefore address the wrong layer and weaken safeguards.

## Minimal diagnostic and manual validation

At **01:13:09 UTC**, sent one idempotent `PUT /actions/workflows/403162553/enable`; the request succeeded and state remained active with updated_at 01:13:09 UTC. No disable/enable pair, cron edit, new workflow or secret change was performed. GitHub documents this endpoint as setting active state; it does **not** document it as rebuilding scheduler registration. This is a diagnostic attempt, not a claimed fix or evidence that reactivation was necessary.

Dispatched exactly one manual run on main with `publish=true`, **force=false**:

https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41260149710

- Created 01:13:11 UTC; job completed 01:13:43 UTC (**32 seconds**).
- Both existing game-window checks passed without a forced bypass. Publication step ran, returned action=updated, and roundTripVerified=true.
- Fresh anonymous Supabase readback passed full schema/content-hash validation and backend security preflight: league 609694684, Supabase UUID aeab467a-499a-4684-91af-e18f4966f7fa, season 2027, week 2, scoring period 12, date 2026-10-31, 10 teams, 162 players, 7 NBA games, **93,678 bytes**.
- Verified at 01:13:39.998465 UTC; 27 seconds old at independent readback. Revision advanced to `ba771b1d85174509475a2ff9f6bd12b00fa317922170848d85343ede162ed104` from the earlier manual-trial revision.
- This proves current main execution, window logic and publication work. It remains **workflow_dispatch**, never schedule evidence. No second manual test was used to manufacture cadence.

Final scheduled-run observation at **2026-11-01 01:17:15 UTC**: **zero scheduled runs**, 40.8 minutes after the cron-change merge. The enable diagnostic has not demonstrated recovery. Automatic publishing remains unverified/non-operational in the observed history; configured active state is not proof of unattended operation.

## What GitHub documents

[Schedule event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) requires the default branch and supports a minimum five-minute interval. It warns that scheduler load can delay or drop jobs; it states no registration-time or five-minute delivery guarantee. Public workflows may be disabled after 60 inactive days. The current workflow is active and recently changed, so no documented automatic reactivation requirement applies.

[Workflow troubleshooting](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows#scheduled-workflow-stopped-running) also describes enabled/manual-working workflows with a suspended/deleted actor and a cron-changing commit as recovery. No evidence supports that case here. An arbitrary cron rewrite or renamed duplicate would change production without an identified defect; neither was performed.

[Enable workflow API](https://docs.github.com/en/rest/actions/workflows#enable-a-workflow) describes only setting state active. Public API evidence does not establish whether an internal scheduler registration is healthy. Persistent absence warrants a GitHub Support case with repository, workflow ID/path, main commit/blob, cron, UTC expected ticks, enable-request time, run-count queries and successful manual run URL. Do not include credential values.

## Alternatives if absence persists

1. **Smallest independent scheduler:** a [Cloudflare Worker Cron Trigger](https://developers.cloudflare.com/workers/configuration/cron-triggers/) on its [Free plan](https://developers.cloudflare.com/workers/platform/pricing/) can call this existing workflow_dispatch endpoint with publish=true and force=false. At five-minute intervals this is 288 dispatch attempts/day before schedule-aware filtering; verify current limits before implementation. Store a narrowly scoped repository Actions-write credential in the scheduler's secret storage; keep ESPN/Supabase server credentials in GitHub. Respect the existing stop switch explicitly in the external scheduler: manual dispatch deliberately bypasses the scheduled-job activation flag, so disabling native cron alone would not stop external dispatch. Do not pass credentials in URLs. GitHub runner queue delays remain, and the free scheduler is not a hard freshness SLA. No Worker/account/token/infrastructure was created here.
2. **Existing always-on host:** use its monitored OS scheduler to run the pinned one-shot publisher, with the same gate, lock and server-only credentials. This bypasses both GitHub schedule delivery and runner startup, but requires a genuinely always-on machine, operational ownership and secure secret provisioning. A sleeping laptop is not a reliable production scheduler. No host was provisioned or modified.
3. **Escalate before redesign:** GitHub Support can investigate scheduler registration/queue state unavailable to repository APIs. Replacing the Python backend or adding another native Actions cron would not isolate the observed failure.

Do not enable frontend scoring until actual unattended publications and fresh readback pass. Keep the approved native schedule enabled for observation unless rollback is requested; stop it with the existing LIVE_SCORING_AUTOPUBLISH=false flag. No paid infrastructure was introduced.
