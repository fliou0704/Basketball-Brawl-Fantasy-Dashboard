# Complete NBA player game logs: research and recommendation

Read-only investigation, November 6, 2026 (New York). Code baseline: codex `b960c41`; current canonical inputs inspected from origin/main `e337c7f`. Local tracked CSVs lag production, so numerical reconciliation used `git show origin/main:...`, never replaced local files. No updater, workflow, frontend, canonical CSV or deployed service was changed.

## Recommendation

Use ESPN's **league-scoped bulk fantasy requests**, retaining raw `kona_playercard` game records for initial backfill and paginated `kona_player_info` exact-period records for daily increments. Reuse the existing request construction, credentials helper, scoring/calendar metadata and atomic-validation patterns. Keep an independent **all-player NBA game-log CSV**, rather than inserting free agents into the fantasy-ownership CSV. No new provider or database is justified yet.

This is an experimentally supported design, not certification that the ESPN fantasy pool contains every NBA participant. Before production acceptance, reconcile against completed regular-season fixture box scores, including the end of the NBA season outside fantasy playoffs. Resolve missing athletes through the same ESPN NBA source. Do not advertise a complete Top 150 until coverage passes that check.

## Existing collection and consumers

`playerDailyDataBuilder.py` is the legacy full-season builder; it loops seasons/scoring periods and home/away fantasy lineups. Do not run it: it writes the canonical file wholesale and contains hardcoded credential literals. Any still-valid exposed credentials require separate rotation; values are deliberately omitted here.

`playerDailyDataUpdater.py` provides `fetch_daily_rows`, `_record_for_player`, validation and atomic merge/write. `nearLiveUpdater.py` orchestrates staged bounded refreshes, validates candidates and preserves historical partitions. Its `LeagueFactory` caches league construction and box-score reads. `box_scores` requests `mMatchupScore` + `mScoreboard`, filtered by matchup period/scoringPeriodId; only fantasy lineup players are collected, including bench/IR players with daily stats. It does not collect the entire NBA player universe.

The installed **espn-api 0.41.0** supplies `League`, `Player`, requests and stat mappings. League initialization also reads league settings/rosters/status, professional players and schedules. `get_pro_players` uses `players_wl` with active filtering: this is current metadata, not season-specific appearance evidence. `free_agents(size=50)` uses `kona_player_info`, FREEAGENT/WAIVERS status and ownership/draft sorts; default size and present ownership cannot establish historical coverage. `player_info(playerId=[...])` supports a list and calls `get_player_card`, then fetches/caches professional schedules. It is not inherently one request per player.

`Player.stats` reduces daily game records to scoring-period keys. Distinct games in one period can overwrite one another; schedule-derived dates also rely on current team affiliation and naive host timestamps. Preserve raw `externalId`, season and stats instead of making that normalized object the archive format. No multi-game period appeared in the sampled current-season pool, so the collision risk is source-code evidence, not an observed production duplicate.

Current flow: ESPN fantasy lineups → weighted daily contribution rows → validated canonical CSV → shared weekly/team aggregation → Python frontend exporters → static JSON → React. `generate_players.py` directly indexes fantasy teams by Team ID and builds ownership stints. `generate_record_book.py` ranks non-bench negative games and awards; shared slot aggregation and `teamPerformance.py` drive fantasy totals and starts. React consumes exported JSON, not CSV directly.

The live adapter has useful bounded requests, safe authentication errors, ETags, timestamps and atomic locking/writes; its current-period normalized roster snapshot cannot supply unrostered history. Reuse patterns in a separate daily collector without altering live polling. Its 20 MB response guard should remain: a measured all-pool card response exceeded it, making smaller batches necessary. The installed library's request helper lacks explicit timeouts and its authentication exception interpolates cookies; use a sanitized bounded wrapper, never raw exception logging.

## Measured source comparison

All requests were sequential, read-only and authenticated through `require_espn_credentials()` where required. Benchmarks used bounded connection/read timeouts and no retry loop. There were **24 total HTTP reads**, including five initial setup/filter probes and subsequent targeted reconciliation. Successful probes returned HTTP 200; no observed 429s or timeouts. These are single observations, not sustained rate-limit or percentile measurements. Sizes are **decoded JSON bytes**, not measured wire transfers. Fantasy Content-Length was absent; public NBA box scores were compressed.

| Request | Players returned | Raw game-split rows, all returned seasons | Decoded bytes | Seconds |
|---|---:|---:|---:|---:|
| Settings + current roster/status | 163 roster members | — | 1,775,403 | 0.454 |
| Player pool, first page, limit 1,000 | 1,000 | 0 | 5,289,783 | 0.381 |
| Player card, one ID | 1 | 90 | 61,840 | 0.076 |
| Player cards, 120 IDs | 120 | 10,366 | 6,722,047 | 0.624 |
| Player cards, 1,000 IDs | 1,000 | 72,512 | 31,001,135 | 2.186 |
| Player pool, offset 1,000 | 100 | 0 | 217,025 | 0.100 |
| Player pool, offset 1,100 | 0 | 0 | 14 | 0.115 |
| Cards for final 100 IDs | 100 | 5,255 | 1,229,089 | 0.197 |
| Historical 2023 cards, 12 requested IDs | 10 | 819 actual 2023 game rows | 524,264 | 0.176 |
| Exact current-season period 17, pool first page | 1,000 | 95 | 1,243,273 | 0.176 |
| Public NBA scoreboard, November 5 | — | — | 51,350 | 0.171 |
| One public NBA summary/box score | 25 athlete entries | participation must be filtered | 434,635 | 0.100 |

The first pool attempt failed HTTP 400: **a limit requires a sort** (`FILTER_LIMIT_MISSING_SORT`). Adding the library's `sortPercOwned` shape resolved it. Pagination returned 1,000, then 100, then zero entries. A page limit is a transport bound, never an eligibility/ranking threshold. Deduplicate IDs across pages and detect changing-sort pagination drift; a moving ownership sort is not a transactional snapshot.

Bulk cards use `/games/fba/seasons/{year}/segments/0/leagues/609694684?view=kona_playercard`, `players.filterIds.value`, and `filterStatsForTopScoringPeriodIds` with additional season-total tokens such as `002027`/`102027`. The 1,000-ID response included **2026 and 2027**, projections, DNP-like entries and game rows. Neither total response rows nor presence of stats proves season eligibility. Avoid the 31 MB request in production; measured 100–120-ID batches are a sensible initial ceiling, with response-byte validation and adaptive splitting.

Exact daily bulk retrieval was verified with `view=kona_player_info`, `scoringPeriodId=17`, and `players.filterStatsForScoringPeriodIds.value=[17]`, plus limit/offset/sort. All 95 actual game-split rows returned were explicitly season 2027/period 17; 49 had positive minutes. In contrast, “top scoring periods = 1” returned 904 game rows and was not validated as exact-day selection: do not substitute it for the exact filter. The second daily page was not benchmarked, so complete daily counts are unverified.

Public NBA `site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard` discovers event IDs; `/summary?event=...` returns all athlete box-score lines, including DNPs. This naturally preserves game identity and supports independent participation/coverage checks. It costs approximately one summary per game plus date scoreboards, requires raw-stat parsing/scoring and regular-season/Cup exclusions, and is less efficient than two-page fantasy daily reads. ESPN public and fantasy endpoints are unofficial integration surfaces with no verified availability/rate-limit contract. `stats.nba.com` is a potential independent season-log source, but was not benchmarked and would add identity mapping/provider dependencies; no recommendation to adopt it now.

## Eligibility, season and identity rules

Require actual `statSourceId=0`, game split `statSplitTypeId=5`, the requested `seasonId`, a stable `externalId`, and verified regular-season game classification. ESPN fantasy year **2027 means NBA 2026–27**, not calendar 2027. The date anchor for 2027 is 2026-10-19; use existing verified fantasy calendars/fixture joins and New York civil dates rather than fixed matchup-week arithmetic.

Stat ID **40 is MIN; 42 is GP; 28 is MPG**, as verified in the installed mapping. Prefer explicit positive game GP or confirmed box-score participation; positive minutes is corroboration, not the sole gate. Preserve an actual GP/participation record with zero displayed minutes or zero/negative FPTS; exclude `didNotPlay=true`, projections and inactive/DNP-only entries. No positive-GP/zero-minute example was found in the 161-player canonical sample, so that edge remains an acceptance fixture to validate. Some 444 positive-minute current-season player entries were found across the two card batches; this is an observed candidate count, not an independent NBA-completeness guarantee.

Use `(NBA/fantasy season, ESPN player ID, NBA game ID)` as the performance key. A player changing fantasy teams must not duplicate the performance. Keep the NBA team from that game's participant/box-score evidence, never retroactively apply today's proTeamId. Keep current fantasy ownership and historical fantasy contributions as separate joins. Dates/scoring periods alone cannot distinguish multiple games. Store the NBA game even if no fantasy matchup/week mapping exists beyond the fantasy season; do not silently truncate full NBA regular-season logs at `finalScoringPeriod`.

## Accuracy and canonical representation

Reconciled **1,091 current-season canonical rows for 161 players** against a separate 161-ID bulk card read (1.104 seconds, 8,871,130 bytes). All 1,091 fresh ESPN applied totals matched the league-weight recalculation. **1,090 matched canonical FPTS and weighted stats**; one correction is explained below. Dates sampled against the verified calendar included periods 12/14/16 → October 31/November 2/November 4.

The canonical file's scoring stat columns are **weighted contributions**, because `_record_for_player` inserts `points_breakdown`: raw FGM 1 becomes stored FGM 2; raw TO 1 becomes stored TO −2. MIN is raw; main now also has nullable raw 3PA. Comparing raw stats directly initially flags essentially every row—this is a representation difference, not thousands of corrupt box scores. Do not rescore canonical contribution columns as though they were raw counts.

| Sample | Verified observation |
|---|---|
| Currently rostered Tre Johnson, 5238230 | Period 16, 14 MIN, −3 FPTS; canonical FPTS matched |
| Free agent Gary Payton II, 3134903 | Period 17, 10 MIN, 15 FPTS; absent from current-season canonical rows; present in earlier fantasy history |
| Rostered then dropped Rui Hachimura, 4066648 | Absent from current ESPN rosters; one canonical current-season game versus six positive-GP season card rows |
| Low-minute Yang Hansen, 5217746 | Period 16, 2 MIN, −2 FPTS; retained as an appearance |
| Zero-FPTS Sergio de Larrea, 5279129 | Period 7, 6 MIN, 0 FPTS; must remain eligible |
| Correction: Jayson Tatum, 4065648 | Period 7/game 401909870: fresh 36 vs canonical 38 FPTS; raw TO now 4, weighted −8 vs canonical −6. Independent public NBA box score also reports 4 TO and 28 MIN, `didNotPlay=false` |

The scoring weights in saved season metadata are identical for 2023–2027 and match the live 2027 scoring settings: PTS/REB/3PM/FTM +1, AST/FGM +2, STL/BLK +4, FGA/FTA −1, TO −2. Historical league-scoped cards were readable for 2023, but only 10 of 12 current-player IDs returned records. This is not a full historical roster/discovery test or proof of availability before 2023. Retrieve and version historical settings explicitly before backfill; do not assume weights will never change. Preserve ESPN appliedTotal as the league-specific value and validate against raw-stat recalculation; quarantine mismatches, rather than silently accepting either result. No canonical correction was applied during research.

## Storage and integrity recommendation

Keep `playerDailyData.csv` unchanged as historical **fantasy ownership/contribution evidence**. Main contains 40,923 rows/25 columns, about 5.44 MB: seasonal unique players are 242, 232, 217, 207 and 161 for 2023–2027. Current season has 1,091 rows. Local tracked file is older, 39,840 rows/24 columns; this explains the user's pasted 24-column schema versus main's added raw 3PA.

Null Team ID fails numeric assumptions/direct `int()` lookups; a fake numeric free-agent team can leak into records, awards, stints and team aggregates. An invented `FA` slot is not a universal exclusion: some code excludes only BE/IR. Existing key `(Year, Scoring Period, Team ID, Player ID)` includes ownership and has no game ID. These are concrete reasons to prefer a separate dataset, rather than proliferating exclusions throughout consumers.

Proposed future `nbaPlayerGameLogs.csv`: season, gameId, playerId, game-date NY, actual NBA team ID, scoringPeriod (nullable if unmapped), raw counting stats including MIN/GP/3PA, ESPN applied fantasy points, scoring-rule/version reference and source. Keep current fantasy ownership in existing roster data; optional historical joins use existing contributor rows, never current rosters. Separate metadata records successful coverage, source verification and correction state so unchanged rows do not churn daily. No schema was added during this investigation.

Estimate 25,000–32,000 appearances/year at 150–250 CSV bytes/row: **3.75–8 MB/season**, roughly 15–32 MB for four completed seasons; these are planning estimates, not measured final coverage. Existing 5.44 MB fantasy CSV remains additional, not replaced. Git retains old revisions, so avoid per-row verification timestamp rewrites and full-file reorderings; only actual changes should produce diffs. Measure compressed Git-pack growth in a disposable backfill before approving multi-season retention.

## Daily maintenance and backfill plan

1. Start with 2027 in a disposable directory. Page the unrestricted season pool to exhaustion; no active-only, ownership, Top-N or FPTS filter. Collect season-specific participants and compare with all completed regular-season fixture participants. Discover new debuts through exact-day bulk reads plus fixture coverage; current free-agent status is not eligibility.
2. Backfill eligible players in bounded ~100-ID card batches, persisting successful partitions/checkpoints atomically. Retain raw season/game IDs; filter extra seasons/projections/DNPs; validate requested-versus-returned identities and actual GP. Empty/partial/error responses never authorize deletion. Returning fewer historical IDs needs explicit absent/unavailable classification.
3. Daily, refresh exact recent completed scoring periods (initially three days), page to exhaustion, upsert by game key and update participation discovery. Refresh postponed/rescheduled event IDs from the canonical schedule. A traded or dropped player needs no full-history refetch. Completed one-game players stay in the archive without repeated individual history reads.
4. Keep fixture/period coverage and content hashes, record incomplete partitions, retry bounded transient failures, stage the full candidate and atomically publish only validated data. Resume from checkpoints after interruption. A rolling window catches recent corrections but not all late revisions: perform a bounded weekly historical reconciliation/season-total check, then targeted card refreshes. Never claim old rows are immutable source truth.
5. Generate reusable all-player ranking and player-log JSON through the existing frontend exporter pipeline. Rankings use every actual NBA appearance, including unrostered/bench/zero-FPTS games, while fantasy team awards and actual-start calculations continue using the ownership dataset.
6. After current-season coverage/scoring/idempotence tests pass, repeat separately for 2026, then 2025–2023, using each season's own player pool, fixture IDs, historical endpoint and scoring settings. Do not discover retired 2023 participants from the 2027 active pool. Reuse canonical rows for identity and reconciliation, but their weighted stats, partial ownership coverage and missing game IDs prevent treating them as a complete raw archive. Availability before 2023 remains untested.

Estimated initial current-season backfill: three discovery reads plus roughly 5–12 card batches depending on eligibility-first filtering, plus missing-fixture audits. Historical full-season payloads can be larger than the measured early-season sample; adapt batch sizes. At observed latency the basic fetch phase is seconds to tens of seconds; budget **1–5 minutes** including parsing, validation, retries and writing, and measure before scheduling. Daily three-period refresh is approximately **6–9 paginated fantasy reads**, plus optional roster/settings reuse and bounded correction/box-score audits; no five-minute free-agent polling. This should fit existing eight/25-minute Actions budgets, but historical full-season end-to-end runtime is not measured.

Suggested implementation order, for a later approved stage: new isolated `nbaPlayerGameLogs.py` + focused tests; reuse read-only scoring/calendar helpers from `matchupProjections.py`, `historicalThreePointAttempts.py`, `nbaSchedule.py` and `dataUpdateSafety.py`; add a separate validated daily hook in `nearLiveUpdater.py` only after standalone acceptance; add an all-player exporter and optional data-input persistence to the canonical workflow; finally adapt player/ranking JSON consumers. Do not change the live adapter, Supabase schema, Cloudflare worker or fantasy contribution aggregations to collect free agents.

## Remaining validation and decisions

No user input is required to choose the safer architecture. Implementation approval is the next decision. Open technical checks: independent all-season NBA participant completeness; exact daily tail-page coverage; historical pool discovery/older-season availability; zero-minute actual GP and genuine multi-game-period fixtures; late-correction horizon and measured backfill Git growth. These are validation work, not reasons to invent missing data or ask for an arbitrary player cap.

Source references: [upstream request client](https://github.com/cwendt94/espn-api/blob/master/espn_api/requests/espn_requests.py), [basketball library API](https://github.com/cwendt94/espn-api/wiki/League-Class-Basketball), [maintainer discussion of daily player history](https://github.com/cwendt94/espn-api/discussions/611). Installed source and direct measured responses take precedence over assumptions based on upstream versions. No production implementation or deployment was performed.
