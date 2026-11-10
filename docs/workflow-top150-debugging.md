# Workflow failures and empty Top 150 investigation

Investigated November 10, 2026. Starting review commit: `407260e80b58545d98a0905cbd187c95e3e36d3e`.
Production refs inspected: `main` at `14d18b6`, `codex` at `6a2ad74`.
No production dispatch, deployment, merge, credential changes, or player-data activation was performed.

## Workflow evidence

### November 10: Pages synchronization timeout

[Run 42838587270](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/42838587270):
`update-data` succeeded (14:52:54–14:55:17 UTC), including export/build and canonical commit/push `14d18b6`.
Only `deploy` failed (14:55:24–15:05:33). The deployment stayed queued until 14:57:09, then `syncing_files` until the action canceled it at its default ten-minute deadline.

The artifact was **7,454,990 bytes**, versus **7,455,114 bytes** for successful [run 42750337825](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/42750337825), whose deployment took 12 seconds. No concurrent Pages workflow run appeared in the 14:45–15:15 API history. Both canonical and frontend workflows already use `basketball-brawl-pages`, with cancellation disabled. Live dispatches do not deploy Pages.

Evidence supports a GitHub Pages synchronization delay, not an oversized Top 150 deployment, failed build, or deployment overlap. GitHub's internal cause is not exposed. Canonical inputs persisted; that build did not publish. Public `pipeline.json` still reported fingerprint `4c3ea22818609d22bb67e26ffe51792c3b4714d8b1e3120543e4fd129c70ea12` at inspection. A later successful canonical deployment is needed to publish the delayed static data; no claim is made that this failed deployment recovered automatically.

### November 6: GitHub push rejection

[Run 42309823493](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/42309823493) created local commit `a2fe553` at 23:09:51 UTC (two files; 3,447 insertions/deletions). At 23:09:52 GitHub returned `Internal Server Error` and remotely rejected `HEAD -> main`. Validation and local commit succeeded; push failed, preventing deployment.

The next successful canonical [run 42344917009](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/42344917009), November 7 at 05:58 UTC, recomputed the inputs and pushed `a2c9412`. Subsequent successful updates continued, through `ea4b8d7` and `14d18b6`. The failed commit itself was not preserved remotely, so byte-for-byte recovery of that intermediate snapshot cannot be proven; the ongoing canonical state was refreshed rather than permanently stopping at the failed push.

### November 9: live runs failed before jobs existed

Runs [42671626453](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/42671626453), [42672406832](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/42672406832), and [42673141775](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/42673141775) were accepted `workflow_dispatch` events at 18:10, 18:15 and 18:20 UTC. Each has zero API jobs, zero check runs, and an empty log ZIP. There is no evidence that checkout, game-window logic, dependency installation, collector, or publisher ran. Cloudflare dispatch itself created the records successfully.

GitHub reported an [Actions/Checks incident](https://www.githubstatus.com/incidents/tp8cghg7tlc4) beginning at 18:12 UTC, mitigated at 18:43 and resolved at 18:59. Combined with the pre-job failures and later recovery, infrastructure failure is the strongest explanation; the first failed dispatch precedes the public incident announcement by two minutes. Per-run infrastructure errors are not exposed, so exact internal attribution remains unavailable.

The live workflow blob is identical at failed-run ref `e4d2072` and current `main` (`33eebd655b4377a7c6e4a977fed2617c3c1caf7b`). Runtime deprecation warnings cannot explain a run that never started a job. No adapter/cache/concurrency changes are justified. Later Cloudflare dispatches succeeded, including 42839002751 and 42839848406; their publication steps correctly skipped outside game windows. Anonymous Supabase read returned HTTP 200 with latest verification `2026-11-10T05:50:37.743243+00:00`, season 2027, matchup 4, scoring period 21. This daytime readback is not evidence of a new publication or uninterrupted publication during the incident. Last-known-good data remains present; any missed live intervals are not reconstructed by this investigation.

### Narrow recovery changes, not yet installed in production

Draft [PR #12](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/pull/12), branch `workflow-transient-recovery`, commit `7d201ed`:

- Retry only allowlisted transport/server push errors, at most three attempts with 5/10-second waits. Verify the remote after an ambiguous failure; an already accepted commit succeeds. Refuse to overwrite a remote that advanced. No reset, force push, rebase, or repeated ESPN collection.
- Allow the existing Pages deployment twenty minutes; do not create competing deployment retries. Persistent failures remain fatal.
- Five offline regression cases cover recovery, deterministic rejection, accepted-but-error response, concurrent updates and exhaustion. Bash syntax and YAML structural comparison pass; only the push invocation and deploy timeout change in the YAML.

These changes mitigate transient failures; they cannot guarantee availability during GitHub outages. They have not run remotely because production merge is pending approval.

## Top 150 root cause and environment comparison

There were **two components**. The dedicated `#/top-150` route used `src/Top150.jsx`, which fetches the metadata index and then a full season file. The Players landing (`#/players`) still used `src/components/Top150.jsx`, expecting players embedded in the index. The current index intentionally contains metadata only. Its season entry has no `players`, so the complete-pool guard correctly rejected it. This is a loader/schema mismatch, not missing NBA logs or an overly strict guard.

A disposable baseline production build restored the pre-fix Players component and reproduced “A verified complete NBA player pool is unavailable for this season” using real project files and HTTP. The dedicated route already worked. Local development uses the same route/component distinction; stale dev servers or built output can additionally serve older code and must be restarted/rebuilt after checkout changes.

The public Pages site is built from `codex`, not draft PR #11. Its `/data/top-150.json` returns HTTP 200 with the older incomplete fantasy-only payload. The per-season `/data/top150/2027.json` initially returned 404 (one subsequent inspection returned transient HTTP 503). The actual reviewed Top 150 frontend and its assets remain undeployed. Updating this review branch alone intentionally does not change the public website.

### Fix and data checks

The Players entry now delegates to the same season loader/table, in embedded mode without a second site header or nested `main`. HTTP failure, invalid JSON/schema, coverage failure, genuinely empty season, loading, and unmatched filters have distinct messages; developer diagnostics identify index versus season loading. Failed promises are evicted so later retries are possible. Coverage checks remain enabled; malformed and empty player arrays fail closed.

The existing chain is unchanged:
`playerGameLogs.csv → playerSeasonStats.csv → generate_all.py / generate_top150.py → top-150.json + top150/{year}.json → shared loader → validation → ordinal rankings`.
The exporter verifies the archive hash and season row/player coverage. It joins only saved current-season ownership and preserves unavailable historical ownership. No new updater or production CSV semantics were introduced.

Regenerating from the existing archive plus the consistent saved ownership snapshot produced the same 2027 payload: **458 players** (452 with games plus six rostered without games), **163 roster entries**, max team games 10 and minimum per-game qualification 3. Archive totals remain 108,051 game logs and 2,714 player-season summaries. Generated ranking assets did not need changing.

### Built-preview verification

Chrome tested the actual Vite production build under `/Basketball-Brawl-Fantasy-Dashboard/`, widths **375 and 1280**. Both `#/players` and `#/top-150` rendered **150 top rows**. Both metrics accounted for all 163 owners across Top 150 and the rostered-outside section. Free-agent/search filters, historical season switching, ownership unavailability, and player game-log drilldowns passed. Real HTTP returned 200 for:

- `/Basketball-Brawl-Fantasy-Dashboard/data/top-150.json`
- `/Basketball-Brawl-Fantasy-Dashboard/data/top150/2027.json` (with version query)
- `/Basketball-Brawl-Fantasy-Dashboard/data/top150/2023.json`
- The selected player's `/data/player-static/games/{year}/{shard}.json`.

Separate fault-injection checks passed for missing files, HTML instead of JSON, unsupported schema, empty seasons and incomplete coverage. Home, Standings, Team, Historical H2H, Record Book and Scoreboard smoke checks passed against consistent disposable exports served over HTTP. Unrelated dirty tracked exports were preserved; the disposable build output used consistent exports rather than overwriting those files.

Validation: **253 backend tests, 171 exporter tests, 105 frontend tests, five push tests, production Vite build, and the browser checks passed**. No live ESPN writes were needed.

Reproduce the browser regression after `npm run build --prefix frontend` and serving `npm run preview --prefix frontend -- --host 127.0.0.1 --port 4174`:

```sh
PLAYWRIGHT_CORE_PATH=/path/to/playwright-core node frontend/scripts/check_top150_browser.cjs
```

`TOP150_PREVIEW_URL` overrides the default preview URL; `CHROME_PATH` overrides Chrome. Optional `TOP150_BASELINE_URL` points at a separately built pre-fix preview to assert the original failure. Use consistent regenerated exports in disposable output if unrelated local export edits exist.

## Approval boundary

PR #11 remains draft into `codex`; PR #10 remains draft. `PLAYER_GAME_LOGS_ENABLED` is absent, so its explicit true gate remains disabled. PR #12 is separately reviewable into `main`. Neither production branch was modified and no deployment or workflow activation occurred. Public Top 150 requires explicit approval to merge/deploy; production recovery changes require their own approval. Unrelated local application, generated-data, diagnostic and editor changes remain uncommitted and untouched.
