# Cloudflare live-scoring scheduler

## Status and scope

Cloudflare backend enabled on October 31, 2026 (New York), Worker version `a8cc254d-c110-41c3-a522-1a75079994e7`. A real Cloudflare Cron Trigger dispatched and published successfully; independent anonymous Supabase readback matched. Automatic runs recurred at five-minute intervals, each publishing successfully. PR #6 removed only native live cron from main (`be488e8e9c3703e1700399cf40e00c50b885c4c2`); workflow_dispatch remains available. The later [public frontend rollout](live-scoring-frontend-production.md) enabled React after its separate acceptance gates; PR #3 is now merged. The committed Worker flag remains false by design; production was explicitly deployed with SCHEDULER_ENABLED:true.

The Worker dispatches only `fliou0704/Basketball-Brawl-Fantasy-Dashboard`, `live-scoring.yml`, with `ref=main`, `publish=true`, `force=false`. Existing pinned backend, NBA window checks, updater cache, publisher, Supabase safety, canonical reconciliation and Pages are reused unchanged. External runs appear as **workflow_dispatch**, not schedule, in GitHub; Cloudflare's real Cron Trigger logs establish their origin.

Source: `ops/cloudflare-live-scheduler/`. No public HTTP route, preview URL, checkout, ESPN credentials or Supabase credentials are present in the Worker. Compatibility date 2026-07-30 is pinned to the tested local runtime; it does not change current account limits.

## Verified free-tier fit (checked October 31, 2026, New York)

[Workers limits](https://developers.cloudflare.com/workers/platform/limits/) list **5 cron triggers/account**, **100,000 requests/day**, **10 ms CPU per free invocation**, and **50 subrequests/invocation**. Network waiting is not CPU time. [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) includes a Free plan; no paid subscription is needed for this design.

[Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/) permits SQLite-backed objects on Free: 100,000 requests/day, 13,000 GB-seconds/day compute, 5 million rows read/day, 100,000 rows written/day and 5 GB storage. Exceeding a free limit fails operations rather than automatically buying a paid plan. The migration explicitly selects SQLite; do not substitute a paid-only legacy KV-backed object.

One five-minute timer means **288 invocations/day**, about 8,640 per 30-day month. Enabled ticks use one object call and normally **two GitHub GETs plus one POST** (864 GitHub calls/day, 36/hour); busy/disabled cases use fewer. At most two attempts per GET and one POST: five GitHub HTTP calls/tick. Fixed state is one small overwritten record, at most four small storage writes/tick including claim, POST marker and lease release—well below free daily storage limits even allowing index overhead. A 45-second maximum network budget uses approximately 1,620 GB-seconds/day at 128 MB in the pessimistic all-ticks-full-duration case, below the object allowance. Confirm measured CPU, latency and account-wide usage after deployment; local tests cannot establish production CPU consumption or an uptime SLA.

The free plan's five-trigger allowance is shared across the account. Check existing usage first. Do not upgrade, enable a paid plan, or add a payment method for this task. Cron configuration changes may take up to 15 minutes to propagate ([Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)). Cloudflare delivery and GitHub runner latency still require monitoring; this is not a guaranteed five-minute freshness SLA.

## Safeguards

- `SCHEDULER_ENABLED` must equal `true`; checked before any GitHub request. The committed default is false. Ordinary deployments without an explicit override return to disabled mode.
- A single SQLite-backed Durable Object atomically claims each five-minute timestamp bucket before network I/O. Claims survive eviction/redeployment. Old/repeated ticks are skipped; a 90-second lease prevents concurrent dispatch operations. State does not grow with tick count. Keep Worker name, class, binding and object identity stable.
- Stale ticks (>4 minutes late) and implausible future ticks are skipped rather than replayed in bursts. A four-minute POST cooldown covers adjacent-slot redeliveries.
- The Worker checks workflow identity/enabled state and the latest 20 main-branch runs; non-completed runs or runs created within four minutes suppress dispatch. The workflow's existing concurrency group is authoritative for serialization, including native/manual races. GitHub list visibility is eventually consistent: this is not a cross-provider exactly-once guarantee. Remove native cron after proof to close the transitional duplicate source.
- GET requests have an eight-second timeout and at most one retry, respecting short Retry-After values; longer deferrals fail closed for the next tick. Total I/O deadline is 45 seconds. HTTP redirects are rejected without forwarding credentials.
- **POST is never retried automatically.** A timeout, network error or server 5xx may follow an accepted dispatch. Its durable claim prevents replay; inspect GitHub before manually retrying. Recovery is the next tick, not a blind repeat. The existing publisher remains stale-safe/idempotent.
- Logs contain tick timestamp, fixed outcome/error codes, phase, HTTP status and a validated run ID/constructed URL when GitHub returns one. They never include tokens, headers, raw bodies, exception messages or player data. `dispatch_accepted` means GitHub accepted the request, **not** that ESPN collection or Supabase publication succeeded.

## Manual account/token setup

These setup steps have been completed for the production Worker. Use them for recovery or token renewal. Never paste either provider's credentials into chat or source files.

1. Create/sign into a Cloudflare account and confirm **Workers Free**, SQLite Durable Objects availability, and a free cron slot. No domain is required.
2. On GitHub, open **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**. Resource owner: `fliou0704`. Repository access: **Only select repositories → Basketball-Brawl-Fantasy-Dashboard**. Repository permission: **Actions: Read and write**; leave everything else unselected (Metadata read is automatic). Choose a short expiry (for example 30 days), name it for this scheduler, and record a renewal reminder. Do not reuse the broad CLI token. See [GitHub dispatch permissions](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event).
3. In your own terminal, from the repository:

   ```sh
   cd "ops/cloudflare-live-scheduler"
   npm ci
   npx wrangler login
   npm run deploy
   npx wrangler secret put GITHUB_TOKEN
   ```

   Complete Cloudflare login yourself. The first deployment is **disabled** and creates the named Worker and SQLite binding. Paste the fine-grained GitHub token only into Wrangler's secret prompt; it is stored as a Cloudflare encrypted secret, not a local environment file. If your login has multiple accounts, set `CLOUDFLARE_ACCOUNT_ID` to the intended non-secret account ID for these commands. Do not select a different/paid account to bypass an error. [Secret documentation](https://developers.cloudflare.com/workers/configuration/secrets/).

4. Verify only expected-binding presence and unexpected-binding **counts**, never raw secret names: names can themselves contain accidentally pasted credentials. The expected inventory is exactly one GITHUB_TOKEN binding. If extra bindings exist, stop; inspect/remove them in the Cloudflare dashboard without copying their names into commands or logs. If any name was a token, revoke/replace that token before continuing. Do not read or print secret values. Confirm SCHEDULER_ENABLED=false. Then activate explicitly:

   ```sh
   npm run deploy -- --var SCHEDULER_ENABLED:true
   npm run tail -- --format json
   ```

   Wrangler preserves secrets across normal deployments. Leave the credential out of command arguments, shell history and configuration. There is no HTTP endpoint that can trigger the publisher. To let Codex finish the account-dependent steps, report only that login/secret setup succeeded—never send the token.

## Real end-to-end acceptance gate

Do not disable native cron or report success merely because local tests or manual dispatch succeed.

1. Allow propagation, then observe a **real Cloudflare scheduled event** during an NBA game window. Record the UTC tick/Cloudflare event, `dispatch_accepted`, returned run ID/URL and outcome. If GitHub's successful response has no run ID (older 204 response), correlate the unique new main-branch run with the Cloudflare dispatch time and token owner; do not count unrelated manual runs.
2. Open that exact GitHub run. It must be `event=workflow_dispatch`, branch main, successful, and have the publication step actually run. A valid game-window no-op is expected off-hours, but does not complete the publication test. Do not use force=true to manufacture an NBA window.
3. Check the publisher's JSON summary: `roundTripVerified=true`, action updated/unchanged, expected league UUID, season and player/team counts. In Wrangler logs, accepted dispatch alone is insufficient. In GitHub:

   ```sh
   gh run view RUN_ID --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
   gh run view RUN_ID --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard --log
   ```

   Logs should show the existing safe summary; do not dump request headers or environment variables.
4. Independently read Supabase using the existing local helper and configured local environment. From the repository root, this is read-only and makes no ESPN request:

   ```sh
   python - <<'PY'
   import json
   from supabasePublisher import Config, Publisher, validate, database_instant
   p = Publisher(Config.environment(anonymous=True))
   p.ready()
   r = p.read('aeab467a-499a-4684-91af-e18f4966f7fa', 2027, anonymous=True)
   s = r['snapshot']
   result = validate(s, 609694684, database_instant(r['verified_at']).isoformat())
   print(json.dumps({**result, 'week': s['week'], 'scoringPeriod': s['scoringPeriod'], 'date': s['date']}))
   PY
   ```

   For later seasons use the actual season reported by the run, not permanently 2027. Compare revision and verifiedAt with that run's publisher summary and execution interval. Validation rejects stale data. A newer row from another run cannot prove this selected run's readback; verify the latest correlated run instead. Existing .env stays ignored and is loaded only by the established helper.
5. Observe another real five-minute tick; confirm no simultaneous runs, appropriate busy/no-op behavior, advancing verification time, and unchanged canonical/Pages behavior. Record actual observed cadence; do not infer success from a configured timer.
6. **Only after real publication/readback succeeds**, prepare a narrow main PR removing just the live workflow's `on.schedule` block. Preserve workflow_dispatch, job logic, secrets, concurrency and the `473b669` backend pin. Leave the canonical updater's schedule untouched. Merge that reviewed one-file diff, then verify later external ticks still work. The log-only cron diagnostic can be retired separately; it is not a publication duplicate. Native cron has intentionally not been removed in this preparation stage.

## Immediate stop, monitoring and rollback

The GitHub variable `LIVE_SCORING_AUTOPUBLISH=false` stops native schedule jobs only. **It does not stop external manual dispatch.** Use the Worker flag and GitHub workflow state instead.

Fast server-side emergency stop (does not affect canonical reconciliation or Pages):

```sh
gh workflow disable live-scoring.yml --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
```

GitHub then rejects further dispatch; the Worker also sees the disabled state. This does not cancel a run already accepted. If needed, list and cancel that specific live run, never the canonical updater:

```sh
gh run list --workflow live-scoring.yml --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
gh run cancel RUN_ID --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
```

Stop the Cloudflare producer and its checks:

```sh
cd ops/cloudflare-live-scheduler
npm run deploy -- --var SCHEDULER_ENABLED:false
```

Removing a Cron Trigger alone can take up to 15 minutes to propagate. Revoking the dedicated GitHub token is another immediate credential-level stop. Do not change ESPN/Supabase secrets or delete data. To resume, restore a valid dedicated secret if revoked, enable the GitHub workflow with `gh workflow enable live-scoring.yml --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard`, and explicitly deploy SCHEDULER_ENABLED:true. If native cron still exists, re-enabling the workflow also re-enables that trigger; review the cutover state first.

Monitor Cloudflare Workers **Observability → Logs/Metrics**, Cron Trigger invocations, outcome/error codes, CPU and free usage; monitor GitHub's correlated run status and Supabase verified_at. Authentication/permission failures usually require token expiry/scope/account checks, not additional retries. Disabled/busy/recent_run codes are intentional no-ops. `dispatch_ambiguous` requires checking GitHub before manual intervention. Preserve a record of Cloudflare event IDs and GitHub run IDs for actual cadence measurements.

Rollback to native scheduling: first disable the Worker, then revert only the eventual native-cron-removal PR (if it was merged), restore the existing native activation flag, and re-enable the live workflow if disabled. Native delivery was previously unreliable; this restores the prior configuration, not a reliability guarantee. React remains off throughout. No historical rows or live snapshot need deletion.

## Local validation (not a real deployment)

```sh
cd ops/cloudflare-live-scheduler
npm test
npm run check
```

Tests cover exact payload, default off, scoped token format, timestamps, durable concurrent/replayed ticks, restart persistence, cooldown, active/recent runs, disabled workflow, malformed responses, bounded GET retries, ambiguous non-replayed POSTs, sanitized failures and redirects. Miniflare runs the actual scheduled handler and SQLite-backed Durable Object against **mocked GitHub with external network disabled**, including runtime recreation. These tests do not prove Cloudflare production scheduling, production CPU use, ESPN publication, or Supabase freshness. The account/token and real acceptance gate above remain required.

Validation record: **20 tests passed**, including the actual local Workers runtime/SQLite restart test. Wrangler dry-run bundled **8.32 KiB (2.92 KiB gzip)** with the expected SQLite binding and disabled flag. At preparation time the CLI was unauthenticated. No production event or publication was performed by these local tests; production verification is recorded separately below.

## Production trial record — October 31, 2026 (New York)

Configuration checks emitted only authenticated/expected-present booleans and an unexpected-binding count of zero. The enabled production version was inspected to verify its flag, token binding, Durable Object binding and scheduled handler without printing arbitrary provider names or credential values.

| Cloudflare cron event (EDT) | GitHub run | Result | Publication/readback |
|---|---|---|---|
| 11:00:13.079 p.m. | [41267400197](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41267400197) | Created 11:00:16, completed 11:00:42; 26 seconds | updated; roundTripVerified; anonymous revision/timestamp match |
| Following automatic tick | [41267736030](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41267736030) | Created 11:05:15 p.m.; success | refreshed; roundTripVerified; verified 11:05:42.463447 p.m. |
| Following automatic tick | [41268075610](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41268075610) | Created 11:10:16 p.m.; success | refreshed; roundTripVerified; independent anonymous revision/timestamp match at 11:10:43.902195 p.m. |
| Post-cutover automatic tick | [41268423699](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41268423699) | Created 11:15:16 p.m., completed 11:15:47; main `be488e8` | refreshed; roundTripVerified; independent anonymous revision/timestamp match at 11:15:43.545688 p.m. |

First row: verified at 11:00:38.663066 p.m. EDT; revision `6cbf5e52a1e9dd9b5a99cd15216d5d87c22ddf7dd0eb1be55c49efcdb040157a`; 93,840 bytes; season 2027, matchup week 2, scoring period 12, scoring date October 31, 10 teams, 162 players, 5 matchups. The seven NBA games were final; the existing postgame window permitted publication without force. Official matchup scores and starter/bench/IR credit rules passed. Anonymous readback was 58 seconds old when independently validated.

Real tail evidence marked cloudflareCronEvent=true, outcome=ok, dispatch_accepted, HTTP 200 and the exact returned GitHub run ID. These are actual remote scheduled events, not the local runtime fixtures or manually triggered GitHub trials. Native cron removal was merged only after all three publications passed. Main changed by one file/three deleted lines; parsed YAML comparison confirms everything except on.schedule is identical. Canonical workflow and Dash application blobs are unchanged. Observed dispatch creation intervals were 299, 301 and 300 seconds. The fourth run used the post-cutover main commit and passed schema/hash/freshness, league/season/period, official-score consistency and player lineup-credit validation on independent anonymous readback. Scores stayed unchanged after final games; verified_at advanced, rather than inventing score changes. No Pages deployment or React activation was performed during this backend trial; the subsequent frontend rollout is recorded separately.

Activation validation: all 20 scheduler tests passed again. The first restricted-environment runtime attempt aborted inside Node; rerunning with the required local runtime permissions passed the actual SQLite/Workers test. No scheduler source changes were needed. Workflow comparison, git diff checks, enabled deployed flag, expected credential-binding presence/zero unexpected bindings, PR #3 draft state and disabled frontend flag were verified. No arbitrary secret names or values were printed.
