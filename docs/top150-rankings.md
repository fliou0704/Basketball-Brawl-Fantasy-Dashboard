# Top 150 — review implementation

Implemented on `top150-rankings-review`, based on codex `6a2ad74`. This review branch deliberately prevents the existing canonical Pages builder (which checks out codex) from publishing an unapproved frontend. No merge, deployment, gate activation, ESPN writes or live-scoring change was performed.

## Workflow readiness

Draft [PR #10](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/pull/10) adds only the reviewed `player-game-logs.yml` to main. It is byte-identical to the existing codex workflow. Its collector/exporter/tests/dependencies already exist on codex, which the workflow checks out. Existing canonical/live workflows are untouched. Hold this PR for approval.

GitHub's attempted manual dispatch returned 404 because the workflow is absent on default main. Therefore remote manual validation and actual scheduled execution remain unverified. Registration does not block this UI review. `PLAYER_GAME_LOGS_ENABLED` remains disabled/absent. After approval: merge only PR #10, manually dispatch ref codex with `persist=false`, review coverage/artifacts and unchanged-output behavior, then separately approve persistence and setting `PLAYER_GAME_LOGS_ENABLED=true`. Verify actual scheduled run records; native GitHub cron delivery has been unreliable in this repository. See player-ranking-data.md for cadence, retries, bounded checkpoints and rollback. No new credentials are required.

## Data and rankings

The existing guarded `generate_top150.py` now consumes validated comprehensive season summaries and collector coverage instead of requiring the old optional nbaPlayerPool.json scaffold. The legacy validator remains available. Summary identity/count/appearance totals and archive versions must match the collector report before `completePool` is asserted. NBA ownership and scores are not inferred from fantasy-contribution CSVs.

`top-150.json` is an approximately 799-byte season index. `top150/{year}.json` contains one season's full population and roster overlay (current season approximately 81 KB). No whole historical archive is downloaded by the page. Historical and current metadata supply actual maximum NBA team-game counts.

- Total mode ranks all recorded NBA appearances by summed FPTS descending, FPTS/Game descending, then numeric ESPN ID ascending.
- Per-game mode uses FPTS divided by actual GP and requires `ceil(0.25 * maximum NBA team games)`, at least one GP. Current snapshot: maximum 10 team games → minimum 3 GP. Completed seasons: 82 → minimum 21 GP.
- The first section contains the leading 150 qualifying players. Filtering/search preserves these original overall ranks, rather than re-ranking the filtered subset.
- The second section contains only rostered players outside that section, preserving true qualifying ranks and omitting intervening free agents. Nonqualifying/no-game roster players have no fabricated rank and receive an explicit label. A current snapshot has 163 actual roster entries including reserves/IR, not an assumed 150. Total mode accounts for 115 inside + 48 outside; per-game mode accounts for 123 inside + 40 outside. Six rostered players have no recorded NBA appearances; twelve are unqualified in the current per-game view.
- Search additionally exposes other matching players outside the main sections, including unqualified free agents. Their statistics/game logs remain accessible without filling intervening ranks in the default tables.

Current ownership comes from main's `currentLeague.json` through the normal exporter source directory. The preview uses the saved main snapshot at 2026-11-06T16:46:55.921146+00:00, with 163 players. Roster IDs are unique and every roster entry is represented, including zero-game players. Free-agent overlays use team ID 0 and slot FA with the displayed name Free Agent, without modifying the underlying archive. Ownership timestamp is displayed separately from statistics. Historical ownership is explicitly unavailable, team filters are disabled, and current rosters are never projected backward.

NBA affiliation is the latest **observed game team**, not a verified current affiliation after a trade without a subsequent appearance. Fantasy positions use available ESPN eligibility IDs. Unknown fields are dashes; missing scores remain distinct from genuine zero. Historical eligibility and unknown fantasy-pool participants retain the limitations documented in player-ranking-data.md.

## UI and static access

`#/top-150` reuses PageShell, PageHeader, Section, TableCard, PlayerIdentity and Team logos. It adds a navigation link while leaving existing page calculations/routing intact. Metric buttons, season, name search, fantasy-team/free-agent filter and position filter are local React state. Rank and player columns remain sticky in semantic horizontally scrolling tables; there is no conversion to stacked mobile cards. The table container scrolls without page-level overflow. Headshots are lazy-loaded through an optional prop; existing PlayerIdentity consumers retain eager behavior.

Clicking a player opens a lightweight game-log panel and loads only `player-static/games/{year}/{playerId % 32 padded to two digits}.json`. Rows are filtered by exact player ID and shown newest first, including opponent, minutes, fantasy/counting points and shooting. Zero-game roster players show no recorded appearances without an unnecessary request. There is one cached promise per data URL, failed loads can retry, and abandoned season/player requests cannot overwrite current selection.

The index is refreshed on page entry, and season/shard URLs are versioned by content/ownership timestamps to avoid reusing an old cached response after a new dataset. Switching modes/filters requires no page reload. Shards remain on-demand; no Supabase or free-agent live polling is introduced.

`generate_all.py` already invoked the scaffold exporter, so existing Pages workflows automatically include this feature's data after an approved merge into codex. It copies the committed static shards and derives roster-aware summaries using fresh main canonical ownership. Daily player-data commits can retain their existing [skip pages] marker; the next successful canonical export detects changed ranking payloads and deploys through the normal fingerprint/build path. No separate frontend deployment logic was added.

## Validation and review

Backend tests: 253 passed. Frontend tests: 104 passed. Exporter tests: 171 passed with a consistent freshly generated temporary output. The first exporter run against the existing working tree found four stale generated-output mismatches; those unrelated files were preserved. No tests were weakened to ignore those failures; the suite passed when outputs matched their inputs. The old scaffold's real-data assertion was updated to expect the now-available complete archive rather than incorrectly asserting that the entire pool is unavailable.

Real browser checks at 375, 430, 768 and 1280 pixels passed: 150 rows, mode/qualification changes, historical seasons, search, filters, on-demand game logs, sticky horizontal scrolling and no page-level overflow. Home, Standings, Team Stats, Historical H2H, Record Book and Scoreboard loaded without alerts/page errors against consistent generated data. Existing live-scoring hooks/provider logic were unchanged; no new ESPN/Supabase operation was performed for UI validation. Production Vite build passed.

Screenshots were captured locally at `/private/tmp/top150-review-375.png` and `/private/tmp/top150-review-1280.png`. The current season initially loads only its approximately 81 KB season payload plus the tiny index (and existing navigation data/images); no game shard is requested until opening a player. Individual shards average about 126 KB, maximum about 296 KB. Timing/latency depends on hosting; no production user-facing latency measurement is claimed for this undeployed branch.

Changed feature files: generate_top150.py, its archive tests and updated scaffold assertion; Top150.jsx/top150.css; top150-data.js/tests; main.jsx/App.jsx routing/navigation; optional PlayerIdentity lazy-loading prop; generated top-150 index, season payloads and player-static assets; this document. No canonical CSV, existing live workflow, Cloudflare code or production flag was modified.

## Approval/deployment sequence

1. Review the UI branch and screenshot/preview. Approve merging `top150-rankings-review` into codex only when ready to deploy. A normal approved codex frontend push triggers Pages; the canonical builder can also deploy codex during a later data update, which is why review remains on a separate branch.
2. Approve the independent minimal workflow-registration PR #10 and its manual trial. Keep the publishing gate off until successful validation, then approve enabling daily scheduling. Do not merge the whole codex branch into main.
3. Verify the real public Top 150 and daily dataset cadence after deployment. Neither is claimed as deployed/active here.

Rollback after a future deployment: revert only the reviewed UI commit and rebuild through existing Pages. Stop daily player maintenance separately with PLAYER_GAME_LOGS_ENABLED=false. Historical CSVs and live scoring need no reset or deletion. Current roster ownership is a dated canonical snapshot, not live transaction streaming; historical ownership remains unavailable; latest observed NBA team is not necessarily a newly traded player's current team; player positions can be unknown; datasets update daily rather than every five minutes.
