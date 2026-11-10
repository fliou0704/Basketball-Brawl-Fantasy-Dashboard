> Current maintenance/export preparation: [player ranking data](player-ranking-data.md). The original manual-only implementation below is historical; the newer schedule is prepared on codex behind an inactive gate and is not registered/active on main.

# Comprehensive NBA player game logs

Implemented on codex, beginning from research commit ca6c614. No frontend, live-scoring, Supabase, Cloudflare or existing canonical updater was changed. The new manual-only workflow is a separate daily-capable process; no production schedule is activated.

## Data model and source authority

`data/playerGameLogs.csv` has one row per `(Year, Player ID, Game ID)`, independent of fantasy ownership. `Year` is the fantasy ending year: 2027 means NBA 2026–27. There are no synthetic fantasy teams or FA slots in this core archive.

Columns:

- `Year`, `Game ID`, `Player ID`, `Player Name`: season, stable ESPN event/player identities and game participant name.
- `Date`: actual New York civil game date from verified fixtures/public event timestamps.
- `Scoring Period`: explicit fantasy fixture/game-stat period. Public-discovered games missing from fantasy fixtures use the raw fantasy game period when available; otherwise this remains empty and is reported, never inferred from seven-day weeks.
- `NBA Team ID`, `Opponent ID`: actual box-score teams for that game, preserving trades.
- `Eligible Slot IDs`: JSON array of ESPN fantasy eligibility/lineup-slot IDs from the season-scoped response, preserving all available positions without truncation. An empty array means unknown, not ineligible. Historical point-in-time eligibility changes cannot be reconstructed from current card metadata.
- `FPTS`: league-specific applied total where verified against raw fantasy stats and season scoring settings, otherwise final NBA raw stats scored with those settings.
- `MIN`, `PTS`, `REB`, `AST`, `STL`, `BLK`, `FGM`, `FGA`, `FTM`, `FTA`, `3PM`, `3PA`, `TO`, `GP`: **raw statistics**, unlike weighted contribution columns in playerDailyData.csv. MIN supports fractional minutes; GP is one per actual appearance, including a rounded zero-minute appearance.
- `Source`: explicit fantasy-stat/NBA-participation or NBA-box-score/scoring fallback provenance.

The collector starts from all independently discovered completed NBA regular-season events and final fantasy fixtures, not a ranked fantasy pool. NBA team membership excludes All-Star/exhibition teams even where ESPN labels an exhibition season type 2; Cup championship competition 39 is excluded. Public events missing from fantasy schedules are discovered and retained. Every final eligible event must have successfully parsed participant coverage before publication. Missing/empty/partial responses or conflicting event/team identities fail safely.

DNPs use explicit participation, reason and statistics evidence. ESPN can report `didNotPlay=false` for a coach's-decision DNP with `--` minutes; that contradictory placeholder is excluded. Actual zero-minute/zero-FPTS participants remain included. NBA performance keys do not depend on fantasy roster changes, and more than one game can share a scoring period.

Fantasy cards and public NBA box scores sometimes disagree. Complete positive-GP fantasy game stats are accepted only if their weighted total reproduces the official league appliedTotal; their differences from NBA box scores are recorded in `sourceStatDiscrepancies`. Incomplete/unavailable fantasy rows use verified NBA stats and season weights, listed in `fallbackGamePlayers`. Unverifiable appliedTotal or explicit period disagreement aborts publication. Disagreements are not silently called confirmed NBA corrections: source choice and raw differences remain auditable. Existing historical fantasy CSVs are never rewritten.

## Commands and incremental process

Run from repository root, using existing local environment loading/ESPN credentials:

```sh
# First season or interrupted backfill: repeated runs reuse request checkpoints.
python playerGameLogs.py --seasons 2027 --max-requests 200

# Normal daily maintenance: new completed games and three-day correction window.
python playerGameLogs.py --seasons 2027 --refresh --max-requests 200

# Historical seasons, explicitly selected; each invocation is request-bounded.
python playerGameLogs.py --seasons 2026 --max-requests 200
python playerGameLogs.py --seasons 2025 2024 2023 --max-requests 200
```

A request-budget exit intentionally stops the operation and retains the last-good CSV plus successful request checkpoints. Re-run to resume; do not use `--refresh` while repeatedly resuming an initial historical backfill, because it deliberately refetches recent inputs. JSON responses in ignored `.player-game-log-cache/` are internal checkpoints, not public exports. They never contain request cookies/headers. Use the existing credentials helper; do not run the legacy builder with embedded credential literals.

Each invocation verifies season-specific scoring settings, discovers NBA games by bounded **single-date** public scoreboard requests, and reads each final game's participants. ESPN rejected range-date scoreboard probes, so no unsupported date-range assumption remains. Completed historical inputs are cached. Refresh revisits recent games and exact fantasy periods, pages the entire unrestricted pool to exhaustion with a required sort, updates newly appearing players and retains older games. Initial cards use at most 80 IDs per request; only newly discovered IDs need additional card backfills, including attempted-but-missing IDs tracked to avoid repeated useless history fetches. Current and historical source data are never mixed by season.

There is no universal guarantee that late corrections happen within three days. For older corrections, run an explicit backfill in a fresh separately named `--cache` directory; this is intentionally more expensive, and must be budgeted/resumed. The current incremental mode does not automatically perform a weekly full-history sweep. Historical seasons do not need daily polling after completion.

Normalization, identity, full game/participant coverage and scoring checks finish before atomic CSV replacement. Other collected seasons are retained. A report contains the CSV digest, coverage, unresolved mappings/eligibility, source differences, changed FPTS and legacy reconciliation. CSV and report are individually atomic, not a multi-file transaction: consumers should verify `csvSHA256` and retry on a mismatch after an interrupted report write. Output locking prevents overlapping writers to the same destination. Identical replay leaves CSV and report bytes unchanged; new runtime metrics are returned on stdout instead of forcing Git changes.

## Workflow and activation boundary

`.github/workflows/player-game-logs.yml` is **workflow_dispatch only**, codex-only, separate concurrency, and no pip caching. It restores/saves checkpoints (including failed bounded backfills), tests the collector, refreshes selected seasons using existing ESPN Secrets, and uploads validated outputs. `persist` defaults false; when explicitly true it stages only the new CSV/report and pushes codex with `[skip pages]`. No frontend build or live publication occurs.

GitHub requires this workflow to be registered on the default branch before UI/API manual dispatch can be relied on. This task does not merge it into main or activate a schedule. Local CLI is operational now. Later approval can register the manual workflow and add a single daily trigger or approved invocation from canonical reconciliation. The existing three-hour updater has not been made dependent on this new archive, so a game-log source outage cannot disrupt current standings or live scores.

## Validation and known limits

Focused mocked tests cover season filtering, debut fallback, DNP/zero-minute/zero-FPTS appearances, fractional/negative scoring, mismatched totals, explicit/unresolved periods, two games in a period, duplicates, ownership independence, deterministic ordering, correction reporting, interrupted publication and cache resume. Full backend tests also ran. Production and local legacy files were not overwritten.

Real integration results and historical coverage are recorded in the accompanying game-log report. The current-season sample passed independent game discovery and all participating player records; repeated cached replay made zero network requests and preserved byte-identical CSV/report output. A real daily refresh made **34 HTTP requests / 11,481,908 decoded bytes in 9.755 seconds**, including source verification, recent box scores and exact-period pages. An initial successful validation pass reused earlier resumable checkpoints; it is not a cold-backfill timing measurement. A full historical year requires roughly 270 daily event reads plus about 1,230 box scores and several card batches, so it is deliberately processed in bounded chunks, not added to five-minute polling.

Known limits: positional eligibility can be unknown for athletes absent from the fantasy player pool; late corrections need an explicit broader backfill; independent sources can disagree and their raw differences must be reviewed; source rate limits/availability are unofficial; JSON response size is bounded but historical parsing/storage still needs monitoring. The legacy builder's hardcoded credential exposure requires manual rotation of any still-valid values; this implementation does not rotate or copy them.

No Top 150 UI, Free Agent Explorer, ranking changes or existing fantasy aggregation migration was implemented. Future rankings should sum raw archive FPTS and count unique game IDs, then join current roster ownership separately. Before frontend work, review source-discrepancy and eligibility reports and approve the desired daily activation/retention policy.

## Completed backfill and release validation (November 6, 2026)

| Fantasy year | NBA season | Players | Completed regular-season games | Appearance rows | Legacy rows matched |
|---|---|---:|---:|---:|---:|
| 2023 | 2022–23 | 539 | 1,230 | 25,894 | 10,412 |
| 2024 | 2023–24 | 572 | 1,230 | 26,401 | 10,338 |
| 2025 | 2024–25 | 569 | 1,230 | 26,306 | 9,801 |
| 2026 | 2025–26 | 582 | 1,230 | 26,627 | 9,281 |
| 2027 | 2026–27, through November 5 | 452 | 123 | 2,781 | 1,091 |

Combined archive: **108,009 appearances, 931 distinct player IDs, 5,043 season/game identities**, 19,522,107 CSV bytes before any later source changes. All rows have GP=1 and unique season/player/game keys. Completed historical seasons passed independent public NBA event discovery and exactly 82 games per franchise across all 30 NBA teams. Current-season coverage is all final games found through the verified snapshot, not a promise about unplayed fixtures.

All **40,923 canonical records** matched a unique appearance by season/player/period, with date checked. There were no missing or ambiguous matches, and no unresolved scoring periods. Historical seasons had zero FPTS, minutes, date or weighted-stat discrepancies. The sole current-season difference is Tatum game 401909870: canonical 38 versus verified 36 FPTS, caused by TO changing from three to four (−6 versus −8 contribution). Existing records remain unchanged.

Source disagreement details are retained rather than erased: 127 player-game stat comparisons differ between NBA box scores and complete league-scoped fantasy records across the archive. A total of 1,097 appearances use NBA-box-score/scoring fallback. Fantasy eligibility is unavailable for 37, 37, 22, 26 and 8 season/player combinations respectively; these are reported and represented by empty eligibility arrays, not excluded. Every accepted positive-GP fantasy record for the verified games was reverse-checked against the final appearance keys, with zero unmatched records. A missing 2026 fantasy fixture (401810087) was recovered via public NBA events and its explicit fantasy game period.

Historical collection was run sequentially in checkpointed batches capped at 200 HTTP requests each. Typical measured 200-game-heavy batches transferred roughly 75–80 MB of decoded JSON, spending about 15–23 seconds in HTTP calls plus throttling, parsing and disk work. Full-year source discovery/backfill needs approximately 1,500 GETs; these are planning counts, not a clean cold-run benchmark. Historical cached validation/reconciliation replays measured about 21–24 seconds with zero HTTP requests. The implementation was debugged and resumed in place, so no misleading single cold-runtime figure is claimed. Daily refresh remains the much smaller measured 34-request path described above.

The final full backend suite passed **245 tests**, including 21 collector tests. Live backfills, a real incremental refresh, request-budget stop/resume, protected-output rejection, whole-archive uniqueness/GP/digest checks and byte-stable zero-network replay were validated. Checkpoints now retain only needed settings/player envelopes, excluding unrelated private league-member fields. No secret values, raw response checkpoints, credentials or lock files are committed.

The prepared workflow was parsed and checked to contain only workflow_dispatch. Its inputs are validated before command execution, and persistence remains opt-in. Registering it on main and enabling a daily schedule/persistence gate require a later approved workflow change; simply adding a cron without reviewing the manual persist condition is not an activation procedure. No main merge, frontend deployment or recurring collection was performed in this implementation.
