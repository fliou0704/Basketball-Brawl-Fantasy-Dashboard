# Historical Team FP/Start audit

Audited 2026-10-27 against production data at `a61012c847845dff70d52c5d284c2d338f6fa7ae`,
with the frontend starting at `19e3041`. No canonical CSVs were changed.

## Root cause and coverage

Daily records already cover every league season, 2023–2027, with stable fantasy
team/player IDs, scoring periods, historical lineup slots, minutes and applied
fantasy points. Weekly player exports and saved season metadata provide independent
score references. This is a calculation/availability bug, not a missing-season backfill.

| Season | Available team-seasons before | After | Verified team-weeks | Byes excluded | Verified zero-start weeks | Eligible starts |
|---|---:|---:|---:|---:|---:|---:|
| 2023 | 4/10 | 10/10 | 240/240 | 2 | 1 | 9,380 |
| 2024 | 8/10 | 10/10 | 230/230 | 2 | 0 | 8,914 |
| 2025 | 8/10 | 10/10 | 230/230 | 2 | 0 | 8,214 |
| 2026 | 6/10 | 10/10 | 230/230 | 2 | 0 | 7,861 |
| 2027 (partial, recorded Week 1) | 10/10 | 10/10 | 10/10 | 0 | 0 | 349 |

Verified team-week counts include explicit bye exclusions and the known zero-start
week. A zero-start week's own rate is unavailable (0/0); its zero totals can still
participate in a verified season/career denominator. All 10 career rates are now
available. No historical team-season remains unavailable in this source snapshot.

Three distinct problems caused the old guard to withhold entire season/career rates:

1. Eight bye team-weeks contain active-slot NBA performances but no fantasy matchup
   score. Those games must contribute neither FPTS nor starts.
2. Eight scored team-weeks differ by 1–4 points between player scoring and frozen
   scoreboard snapshots. Exact per-player weekly totals verify seven of these;
   saved ESPN daily scores verify the later 2026 Week 18 player-stat correction.
3. Team 1 benched every recorded game in 2023 Week 14. Its observed bench rows
   establish zero credited starts, rather than missing history.

## ESPN verification

Six bounded, read-only requests used the historical `mMatchupScore` / `mScoreboard`
endpoint and scoring-period-specific `rosterForCurrentScoringPeriod` entries,
the same endpoint used by installed `espn_api.basketball.League.box_scores`.
No `mRoster` current-roster membership was substituted for historical assignments.
No data backfill, recurring historical requests, or new lineup table was necessary.

One initial schema/roster check used 2023 period 148. Five targeted probes then
checked periods 2023/154, 2023/167, 2024/146, 2026/132 and 2026/160. All stored
active played-game `(team ID, player ID, slot, FPTS)` sets matched ESPN exactly
across all teams on those dates. The endpoint itself still exposes frozen daily
scoreboard differences alongside the matching player totals; its team adjustments
were zero. Examples:

| Season / period | Team ID | Actual active starts | Eligible player FPTS | Frozen daily scoreboard |
|---|---:|---:|---:|---:|
| 2023 / 154 | 2 | 6 | 228 | 229 |
| 2023 / 167 | 16 | 2 | 43 | 39 |
| 2024 / 146 | 17 | 6 | 229 | 228 |
| 2026 / 160 | 10 | 6 | 202 | 198 |

Saved scoreboard totals and applied player points are therefore separate facts.
FP/Start uses the latter; official matchup/Standings/Record Book totals stay intact.
The public `team-performance-audit.json` lists all eight score discrepancies and
their verification sources, and identifies any future unresolved weeks explicitly.

## Representative season and career reconciliation

Each eligible start is one stored played game (MIN > 0) in an active slot for that
season, mapped to its actual fantasy team and matchup week. BE, IR and byes are
excluded; zero and negative point games still count. Repeated games on separate
scoring periods are separate starts. FPTS is already applied using that season's
scoring configuration; the exporter does not recompute the scoring formula.

| Scope | Team ID | Eligible FPTS | Starts | FP/Start |
|---|---:|---:|---:|---:|
| 2023 (earliest) | 1 | 27,194 | 822 | 33.08 |
| 2025 (middle) | 16 | 33,469 | 940 | 35.61 |
| 2026 (latest complete) | 1 | 36,187 | 947 | 38.21 |
| Team 1 career through recorded 2027 Week 1 | 1 | 137,525 | 3,685 | 37.32 |

Career is the sum of eligible FPTS divided by the sum of eligible starts, never
an average of the season ratios. Source IDs preserve franchise renames/ownership.
Partial-season rates use only recorded matchup weeks, not scheduled opportunities.

## Reproducing the offline audit

`python frontend/scripts/audit_team_performance.py --source-dir <canonical-data-directory>`

The normal frontend export pipeline also publishes the same coverage audit and
all Team metric fields. Future missing rows, duplicate player-game keys, unknown
slots, missing minutes/points or unexplained score mismatches still cause an
unavailable rate. Matching independent weekly references requires per-player
agreement, not just an accidentally matching team sum. There is no tolerance
increase or invented denominator.
