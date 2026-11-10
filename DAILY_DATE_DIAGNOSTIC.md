# Automated daily-date failure — October 24, 2026

Canonical `main` daily data passed the unchanged date invariant: 39,832 rows,
seasons 2023–2026, zero conflicting `(Year, Scoring Period)` mappings. No existing
dates require migration. The near-live rollout did not introduce invalid saved
dates; validation prevented its UTC-generated candidates from being committed.

## Reproduction before changing the transformation

The same read-only fetch was run under `TZ=UTC`, matching the Actions runner.
Every conflict below originated in **fresh ESPN rows** and then appeared unchanged
in the merged candidate. IDs are representative players for each date group.

| Season | Period | First date: count; player IDs | Second date: count; player IDs | Total |
|---|---:|---|---|---:|
| 2026 | 161 | 2026-03-30: 19; 2490149, 4701230, 4066261 | 2026-03-31: 38; 3908809, 4066457, 4433083 | 57 |
| 2026 | 162 | 2026-03-31: 15; 5061575, 4432816, 4432573 | 2026-04-01: 42; 3908809, 4066457, 3147657 | 57 |
| 2026 | 163 | 2026-04-01: 24; 2490149, 4701230, 4066261 | 2026-04-02: 39; 4576087, 4433083, 4431679 | 63 |
| 2026 | 164 | 2026-04-02: 19; 5061575, 5107199, 4397002 | 2026-04-03: 39; 3907497, 3908809, 4066457 | 58 |
| 2026 | 165 | 2026-04-03: 31; 2490149, 4701230, 5061575 | 2026-04-04: 35; 3917376, 4431679, 4433134 | 66 |
| 2026 | 167 | 2026-04-05: 55; 3908809, 3917376, 4222252 | 2026-04-06: 18; 4431679, 4709138, 4711272 | 73 |
| 2027 | 1 | 2026-10-20: 19; 3147657, 3136195, 3908845 | 2026-10-21: 11; 5104157, 4066259, 4395630 | 30 |
| 2027 | 2 | 2026-10-21: 44; 4711294, 2595516, 4433134 | 2026-10-22: 54; 4433136, 3155942, 4873138 | 98 |
| 2027 | 3 | 2026-10-22: 11; 4432158, 3992, 5124612 | 2026-10-23: 12; 3112335, 3936299, 3978 | 23 |
| 2027 | 4 | 2026-10-23: 53; 3147657, 4711294, 2595516 | 2026-10-24: 56; 5104157, 4433136, 3155942 | 109 |

2026 period 166 had no conflict. In all sampled periods, ESPN's authoritative
`proTeamSchedules_wl` schedule assigns the games to the reported scoring-period
ID, and their timestamps resolve to exactly one **America/New_York** calendar date:
the first date in each table row. The schedule does not supply a separate canonical
date-only field in the library path; it supplies a game timestamp and period ID.

## Exact cause and contract

The pinned `espn-api==0.41.0` builds `Player.schedule[period]['date']` with
`datetime.fromtimestamp(game['date'] / 1000.0)`, a naive datetime in the host's
timezone. That value becomes `player.stats[period]['date']`.
`playerDailyDataUpdater._record_for_player()` previously called `.date()` directly.
UTC runners therefore assigned next-day UTC dates to late NBA games. Local runs
on the New York machine happened to agree with saved historical dates.

For example, game 401810951 starts at `2026-03-31T01:00:00Z`, or March 30 at
21:00 New York time. ESPN assigns it to 2026 period 161. Game 401810947 starts at
`2026-03-30T23:30:00Z`, also March 30 in New York. The old transformation split
those games into March 30 and March 31. The new season reproduces the same older
timezone bug; it does not require a new data model.

The existing `Date` contract remains the league-local NBA game/scoring-day date,
as used by the Game Log and period-to-date anchors. We keep ESPN's scoring-period
ID unchanged and convert the datetime instant to `America/New_York` **before**
extracting its date. Naive library datetimes are interpreted in their originating
host timezone; aware datetimes work as well. We do not force UTC onto a naive
datetime or assign every row an arbitrary first date.

No sampled postponed/delayed game creates a legitimate second New York date for
one scoring period. If such a case appears later, the invariant still rejects it
with explicit source, year, period, dates, counts, and representative player IDs
for investigation; it is not silently normalized or dropped.

## Scope and verification

The source fix is in `playerDailyDataUpdater.py`. `dataUpdateSafety.py` retains the
validator and adds safe conflict details; `nearLiveUpdater.py` validates canonical
and fresh rows separately and labels those checks in workflow logs. Fixtures use
only public game timestamps and player IDs, without authenticated responses.

Regression tests reproduce the original two-date UTC failure and cover UTC,
New York, Los Angeles, aware timestamps, reused period numbers across seasons,
incorrect within-season mappings, immutable historical partitions, reconciliation,
and idempotence. No test calls ESPN. No workflow-file change is needed: the main
workflow already checks out updater code from `codex`.

The fixed full updater was executed under `TZ=UTC` against an isolated copy of
`main`: 398 refreshed 2026 rows and 260 new 2027 rows passed date validation. All
39,832 existing canonical daily records remained exactly unchanged. Season 2027
advanced to period 4; 211 Activity rows were added. Local validation passed 89
backend/safety tests, 82 exporter tests, 23 React tests, and the Vite production
build. Canonical data is published by the main workflow only after its complete
validation/build chain succeeds, rather than committed from this local preview.
