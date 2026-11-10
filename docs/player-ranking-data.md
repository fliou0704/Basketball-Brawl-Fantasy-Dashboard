# Daily maintenance and ranking-data preparation

Implemented after 150d609 on codex. **Production scheduling is not active.** No main merge, deployment, frontend UI/calculation migration, live-scoring change, Cloudflare change or canonical updater change is included.

## Completed work

- Verified the collector, all five seasons and canonical preservation. A controlled three-day live incremental refresh added 42 appearances in two newly finalized 2027 games: 108,051 total rows, 931 distinct player IDs, 5,045 games. Historical rows remain unchanged. 2027 now has 452 players, 125 games and 2,823 appearances through November 6, 2026.
- Prepared a guarded once-daily workflow at **11:43 UTC** (06:43 EST / 07:43 EDT), with manual dispatch. The workflow is committed only on codex; default-branch registration and the explicit repository variable gate remain required. No settings were enabled.
- Added configurable `--correction-days`: routine updates use three days; Sunday's prepared job uses fourteen days. Daily request budget is 200; weekly budget is 400, because fourteen days of NBA box scores plus paginated fantasy records can exceed 200. Both are hard limits, with bounded per-request retries and persistent checkpoints. Existing live and canonical concurrency groups remain separate and untouched.
- Added full-season reconciliation using an independent checkpoint namespace. `--full-reconcile` re-fetches a season once into a fresh namespace, without refreshing that namespace again during budget-limited retries. A new operation needs a new reconciliation ID; retries must reuse the same ID. This prevents an expensive full-season reconciliation from restarting indefinitely.
- Added early maintenance status: one refreshed fixture read can return `no_recent_games` or `scheduled_not_final` without running collection. Recent finalized games still receive correction checks during rest days. Exceptions indicate actual failure; missing data never masquerades as a no-game result.
- Added a guard against disappearing previously verified appearances. Collector validation continues checking independent completed-event coverage, both NBA teams, required statistics, season/period identities, duplicate keys and scoring. Unusual losses stop publication; legitimate statistical corrections remain auditable in the existing report.
- Added summaries and opt-in static exports, with no ownership assignment or ranking cutoff.

## Season summary

`data/playerSeasonStats.csv`: **2,714 player-season rows, 401,044 bytes** at validation time.

Columns: `Year`, `Player ID`, `Player Name`, `Latest Observed NBA Team ID`, `NBA Team IDs`, `Eligible Slot IDs`, `Games Played`, `Total FPTS`, `FPTS/Game`, `Total MIN`, `Total PTS`, `Total REB`, `Total AST`, `Total STL`, `Total BLK`, `Total FGM`, `Total FGA`, `Total FTM`, `Total FTA`, `Total 3PM`, `Total 3PA`, `Total TO`.

Grouping uses season and ESPN player ID, not names. Games Played counts distinct accepted NBA appearances; FPTS/Game is exact summed FPTS divided by that count. Negative and zero performances remain included. Totals use raw archive statistics and preserve all supported seasons/players. Season totals and appearance counts were independently checked against the underlying archive. Deterministic ordering is year/player ID; the future frontend can sort by any metric and select 150 dynamically.

`NBA Team IDs` is the sorted set of actual teams represented during that season. `Latest Observed NBA Team ID` comes from the latest recorded appearance, **not a claim about the player's current affiliation after a trade/signing without another game**. Eligibility comes from the latest recorded eligibility metadata and may be unknown; it is not reconstructed historical eligibility. No fantasy roster owner is embedded. Future free-agent labels should join current roster snapshots separately.

## Static loading contract

`frontend/scripts/generate_player_rankings.py` is the opt-in exporter entry point, reusing `playerSeasonStats.py`. It is deliberately not called by `generate_all.py` yet, so the prepared assets do not automatically publish through the existing site.

```sh
python frontend/scripts/generate_player_rankings.py
```

Outputs are under `data/player-static/`, outside the currently deployed frontend tree:

- `index.json`: schema, archive SHA-256, seasons, counts, path patterns, shard rule and `updatedAt`.
- `seasons/{year}.json`: that season's full summary, encoded as a columns array plus row arrays.
- `games/{year}/{shard}.json`: individual-game records for players whose numeric ESPN ID modulo 32 equals the shard. Shard numbers are zero-padded (`00`–`31`); each payload supplies its columns and deterministically ordered rows. JSON uses native numbers and eligibility/team arrays, avoiding string-number or nested-JSON parsing in future clients.

A future ranking page downloads one small season summary. A player view computes ID modulo 32, fetches one shard for the requested season, and filters by Player ID. A career view can request one shard per season on demand. There are 160 game shards, five season files and one manifest, avoiding thousands of per-player files. Measured game shards averaged about **126 KB**, with a maximum about **296 KB**; all static outputs total about **20.6 MB**. Total output size is not the browser cost: a single player-season lookup fetches one shard, not the entire archive or all static files.

The exporter validates required finite statistics, duplicate identities and the collector's CSV/report digest before writing outputs. Summary totals reconcile with all game rows. Output files are individually atomic; the manifest is published last. Future Pages integration should deploy the whole output tree atomically using the existing Pages artifact mechanism, rather than serving a directory while it is being regenerated. `updatedAt` means **archive content last changed**, not a new successful check every day. It stays stable when data is unchanged, preventing timestamp-only commits. Source coverage dates live in the collector report; successful no-change checks remain visible in Actions logs. Open browser views must not mistake a content timestamp for last verification.

## Local operations

```sh
# Ordinary daily correction window (requires existing ESPN environment credentials)
python playerGameLogs.py --seasons 2027 --refresh --maintenance --correction-days 3

# Broader weekly reconciliation
python playerGameLogs.py --seasons 2027 --refresh --maintenance --correction-days 14 --max-requests 400

# Explicit full-season reconciliation; repeat same ID to resume request checkpoints
python playerGameLogs.py --seasons 2027 --full-reconcile --reconciliation-id audit-2026-11-06 --max-requests 200

python frontend/scripts/generate_player_rankings.py
```

A cold cache needs a bootstrap; request-budget exits preserve the last-good dataset and checkpoints. Retry the same full-reconciliation ID to resume. Use a different ID to deliberately start another full reconciliation. The normal routine cache is separate and is not invalidated by manual full reconciliation. Routine updates never need to redownload all historical seasons. Historical source disagreements/unknown eligibility remain documented in `playerGameLogs.report.json` and the prior integration guide.

## Exact production activation steps — approval still required

1. Review and transfer **only** `.github/workflows/player-game-logs.yml` to main through a narrow PR. It checks out codex, where collector/data/exporter dependencies already live; do not merge the entire development branch. Keep `PLAYER_GAME_LOGS_ENABLED` absent or false while registering it. ESPN_S2 and SWID remain existing Actions secrets; no new secrets or token values are required.
2. Once registered on default main, manually dispatch the **codex ref** with persistence disabled:
   `gh workflow run player-game-logs.yml --ref codex -f seasons=2027 -f persist=false`.
   Inspect collector coverage, report digest, summaries, artifacts and cache persistence. Warm a cold cache with bounded retries if needed. The attempted dispatch during this task returned **HTTP 404**, confirming default-branch registration is still missing; no successful Actions E2E is claimed.
3. After approval and manual validation, test an explicit `persist=true` dispatch on codex. It stages only the archive/report, summary CSV and dedicated static directory. It uses `[skip pages]`, never commits checkpoints, and never invokes a frontend build or live publisher. Existing canonical reconciliation is independent.
4. Only with approval, set repository Actions variable `PLAYER_GAME_LOGS_ENABLED=true`. Scheduled events must originate on main; manual dispatch must target codex. Scheduled persistence is explicitly enabled by the same gate. Verify actual `event=schedule` run records and resulting data before claiming automation works. This repository previously experienced native cron registration/delivery failures; no guarantee is inferred from correct YAML. If native scheduling still fails, a separately approved extension to the existing reliable scheduler can dispatch this workflow; the five-minute Cloudflare/live pipeline has not been modified here.
5. Before the Top 150 UI, approve hooking the opt-in exporter into the existing frontend export pipeline/public artifact and implement roster joins separately. Current React calculations/data-loading remain unchanged.

Disable automatic collection immediately by setting `PLAYER_GAME_LOGS_ENABLED=false`; cancel an identified running game-log job if necessary. Manual dispatch remains available. This does not disable live scoring or canonical updates. Reverting this task's commit is also possible without deleting historical CSVs; no forced history rewrite is necessary.

## Validation, performance and remaining concerns

- Full backend suite: **253 tests passed**, including aggregation, zero/negative FPTS, actual-game denominators, cross-season identity, duplicate/missing-stat rejection, deterministic static generation, unchanged-byte replay, archive/report corruption recovery, three- versus fourteen-day request selection, no-game/not-final maintenance gates and isolated full-reconciliation checkpoints.
- Real bounded incremental test: **42 requests, 14,282,904 decoded bytes, 15.546 seconds**. It added 42 appearances in two completed games. Existing historical rows and playerDailyData.csv were preserved. Repeating static generation produced identical bytes and timestamps. Historical seasons retain 1,230 games each; current validation checks metadata and summaries against the same digest.
- Public export storage: about 401 KB CSV summaries and 20.6 MB of static assets; no SDK, database, service or frontend dependency was added.
- Daily/full-season code is committed/prepared, but production registration, native schedule delivery and a remote manual Actions trial remain unverified until the approved main transfer. The local collector/exporter E2E passed. No production schedule, repository activation variable, credential or deployment was changed.
- Eligibility is unavailable for some NBA participants not represented in the fantasy pool. Latest observed NBA affiliation is not current team verification. Source differences are auditable; no silent rewrite of legacy historical fantasy data is performed. Late corrections outside fourteen days require explicit full reconciliation.
- Potentially valid credential literals remain in the legacy builder/history identified by the prior research. They were not reused or printed. The account owner should revoke/rotate any still-valid exposed ESPN credentials and update local/GitHub secret values; do not paste them into chat. Removing tracked literals/history is a separate approved cleanup, not a substitute for rotation. No automatic rotation or unrelated security refactor occurred.
