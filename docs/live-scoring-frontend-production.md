# Public live-scoring rollout

Activated October 31, 2026, New York time. All times below are EDT unless explicitly UTC.

Production: https://fliou0704.github.io/Basketball-Brawl-Fantasy-Dashboard/

## What was actually deployed

The public disabled bundle already contained the React integration from `473b669` via the canonical Pages builder. The last successful direct codex-push build alone was not a reliable indicator of the public code version. Before activation, the public bundle contained the Supabase transport and freshness text; anonymous reads and canonical league/period identifiers were independently checked.

`codex` already contained the reviewed shared `LiveProvider`, one metadata poller, safe official-score/player overlay, freshness indicators and canonical fallback. Its frontend differences since the older direct build were limited to that integration, exporter context fields, validation and tests. No React source transfer, unrelated development merge or historical-data rewrite was necessary.

| PR | Change | Merge commit |
|---|---|---|
| [#3](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/pull/3), into main | Five public build variables on the canonical workflow's Vite step; six added YAML lines only | `6e333ad2c6341c86d233e9cc721eeacadf9f3539` |
| [#7](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/pull/7), into codex | Add manual dispatch to existing frontend Pages workflow; two added lines only | `f847cd2d8fb11671027da67d378ea7f1b787d49d` |
| [#8](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/pull/8), into main | Register the exact reviewed codex Pages workflow on the default branch so GitHub discovers manual dispatch | `0552ddec0ed11dabb25b874ecfe1c9e2dceeaee3` |

PR #8 adds one workflow file, byte-identical to codex. Its push trigger targets only codex and its build job requires `refs/heads/codex`; a main push cannot deploy this workflow. Shared `basketball-brawl-pages` concurrency preserves serialization with canonical updates. Existing workflows, Dash, canonical CSVs and the pinned live backend were preserved. No entire codex-to-main merge occurred.

The #7 merge triggered the normal codex push path. [Pages run 41269196728](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41269196728) built and deployed `f847cd2`, completing at **11:29:15 p.m.** It regenerated JSON from main's canonical inputs and published the enabled Vite build. No ESPN updater or canonical CSV write ran in this frontend-only deployment. Unlike the canonical job's export-fingerprint optimization, the frontend-only job always builds/uploads/deploys once its codex job gate passes; configuration-only rebuilds do not require a CSV or JSON fingerprint change.

## Public build configuration

These repository Actions **variables**, not backend secrets, are now configured:

| Name expected by source | Configuration |
|---|---|
| `VITE_ENABLE_LIVE_SCORING` | `true` |
| `VITE_SUPABASE_URL` | Verified Supabase project root HTTPS URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Verified `sb_publishable_` key; value deliberately omitted here |
| `VITE_LIVE_LEAGUE_ID` | `aeab467a-499a-4684-91af-e18f4966f7fa` |
| `VITE_LIVE_ESPN_LEAGUE_ID` | `609694684` |

The code does not read `VITE_SUPABASE_LEAGUE_ID`. Both Pages builders now use the same five exact names. Values were passed through captured API input and verified in memory without logging keys. Existing ESPN/Supabase backend secrets and the user's `.env` were not changed. The enabled public asset (`index-D7O1HDjC.js`) was independently checked for the expected public configuration and absence of configured backend credential values or a secret-key marker.

No manual setup remains for this activation.

## Verification

- **91 frontend tests** passed locally and in the deployment; **165 exporter tests** passed in the deployment against main's canonical data. Enabled and disabled production Vite builds passed. Backend source was unchanged, so the full backend suite was not repeated for these YAML/configuration changes.
- Parsed YAML equivalence proved #3 changes only the Vite environment and #7 only adds dispatch. #8 matches codex byte-for-byte and retains its codex-only gate and shared concurrency. Main changed only the two frontend-related workflow paths during this rollout; Dash, canonical data and live-scoring workflow blobs matched the pre-rollout versions.
- Local enabled-build browser acceptance at **1280px, 390px and 320px** used the actual anonymous Supabase snapshot and production canonical JSON. Home, Scoreboard list and matchup detail displayed matching official scores. An unchanged revision downloaded metadata only. Controlled browser-only score changes updated without navigation, remounts, selection resets or scroll changes. Projection values stayed at the canonical baseline. Failed reads, stale snapshots and historical-season isolation passed.
- The same controlled-response acceptance passed against the **actual deployed public site** at all three widths. Test responses and the test clock were confined to those browser contexts; no Supabase rows, canonical files or public responses were modified.
- Separate **unmodified native browser** checks at **1280px and 390px** used no network mocks, injected timers or changed clocks. Real anonymous API reads returned the expected UUID, ESPN league 609694684, season 2027, week 2 and period 12. Home, list and detail official scores matched the snapshot. Freshness displayed “Updated 3 minutes ago” / “Updated 4 minutes ago.” Waiting through an actual 20-second poll produced a new metadata read without a document reload; lineup date, DOM control and scroll were retained. No page errors or horizontal overflow were observed.
- Scope, wrong-league/season, stale/missing/out-of-order data, official discrepancies, bench/IR credit, rollover and projection behavior remain covered by the focused frontend tests.

The real snapshot observed in the public checks was verified at **11:25:44.790257 p.m.** (`2026-11-01T03:25:44.790257+00:00`), with 10 teams and 162 players. The games were final. Actual native polling/freshness was observed; a naturally changing in-progress score after deployment was not available. Score-change behavior was verified using clearly separated browser-only controlled responses rather than fabricated ESPN or database writes.

## Backend and canonical independence

Cloudflare remains enabled and dispatches main with `publish=true`, `force=false`. Backend code remains pinned to `473b669a806fdec6a589d95e7f0bd0d642a8a377`; native live cron remains removed. Actual publication continued through [run 41269102226](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41269102226), created at **11:25:15 p.m.**

After frontend deployment and the main workflow-registration merge, [run 41269437580](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41269437580) started automatically at **11:30:16 p.m.** on main `0552dde` and succeeded. The game-window gate correctly skipped publication once the postgame window closed. This is a successful scheduler/gate check, **not** another publication. No forced ESPN request was used to manufacture a fresh live result.

The canonical updater's schedules, commands, Git data persistence, fingerprint deployment guard and concurrency were unchanged; only its public Vite build environment was added. Its most recent observed scheduled run [41255401270](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41255401270) succeeded independently before this rollout. It was not manually invoked for testing. The live workflow has read-only Git permissions and no Pages steps, so its polling cannot commit data or redeploy the site.

## Rollback and operations

Disable only the frontend overlay and rebuild, without stopping canonical reconciliation or Cloudflare:

```sh
gh variable set VITE_ENABLE_LIVE_SCORING --body false --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
gh workflow run frontend-pages.yml --ref codex --repo fliou0704/Basketball-Brawl-Fantasy-Dashboard
```

Wait for the resulting Pages deployment and verify the disabled public bundle. Changing a variable alone cannot change JavaScript already loaded by browsers. Existing open tabs retain their loaded build until reload; freshness validation still protects them. Immediate public-access withdrawal through the existing league `is_public` policy is separately documented in [rollout preparation](live-scoring-rollout.md); do not delete snapshots or historical data.

To stop backend publishing independently, disable the live GitHub workflow and then deploy the Cloudflare Worker with `SCHEDULER_ENABLED:false`, as documented in [external scheduler operations](external-live-scheduler.md). Neither rollback requires reverting or deleting canonical data.

To re-enable the frontend, restore the public feature flag to true and dispatch the same frontend workflow with ref codex. GitHub's workflow now exists on main for discovery, but execution must target codex. A normal reviewed codex frontend/workflow push also retains its existing deployment behavior. Do not trigger the full canonical updater merely to rebuild public configuration.

Monitor actual Cloudflare dispatches, correlated workflow publication versus intentional gate skips, Supabase `verified_at`, browser freshness and free-tier usage. The frontend polls metadata about every 20 seconds in relevant windows and at most every five minutes off-hours; body reads occur only on revision changes. Hidden tabs pause polling. Snapshots older than ten minutes, mismatched periods/leagues and snapshots older than canonical ingestion are rejected. Postgame/off-hours fallback is expected. GitHub runner queues, token expiry, provider outages, free-tier egress and canonical period-rollover lag remain operational limitations; no five-minute freshness SLA is claimed.
