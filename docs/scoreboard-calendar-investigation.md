# Scoreboard calendar investigation — 2026-10-25

Authenticated read-only checks used the existing credential helper, league
609694684, seasons 2027 and 2026, espn-api 0.41.0. No credentials, headers,
cookies, team identities, or full private response dumps are retained here.

## Findings

The 2027 league response (`mSettings`, `mSchedule`, `mMatchupScore`, `mStatus`)
reports currentMatchupPeriod=1, root scoringPeriodId=6, latestScoringPeriod=6,
firstScoringPeriod=1 and finalScoringPeriod=167. `status.scoringPeriodId` is absent;
the daily scoring-period ID is at the response root.

scheduleSettings has periodTypeId=2, matchupPeriodLength=1,
playoffMatchupPeriodLength=1, matchupPeriodCount=20 and matchupPeriods
{"1":[1], "2":[2], …, "23":[23]}. These arrays group base weekly periods
into league matchups; they are not daily scoring-period boundaries. The decisive
counterexample is Week 1: schedule[].matchupPeriodId=1 has
pointsByScoringPeriod keys 1–6. The same singleton mapping accompanies 2026
Week 17's fourteen daily periods. The observed league settings verify the
one-week grouping case; multi-week league configurations were not investigated.

`espn_api.basketball.League._map_matchup_ids` derives membership from schedule
home/away pointsByScoringPeriod keys, not from a future calendar. Its future
mapping cannot be treated as scheduled boundaries.

Game-level kona_game_state/kona_game_settings exposes currentScoringPeriod.id=6,
but no daily-to-week mapping. Game-level mSettings/mSchedule returned empty
objects. The segment game-state resource returned not found. League queries
for scoringPeriodId 7, 14 and 100 echo that root parameter while retaining the
actual currentMatchupPeriod=1; they do not predict future membership.

proTeamSchedules_wl exposes settings.proTeams[].proGamesByScoringPeriod,
with game timestamps and scoringPeriodId, but no fantasy matchup membership.
All inspected 2027 games in periods 1–167 agree with the retained 2026-10-19
anchor after America/New_York conversion. Only 150 daily periods have games:
game absence does not establish a fantasy week boundary.

No complete future daily-to-fantasy-matchup mapping was found in these responses.
Missing information is the first and last *daily* scoring period of each future
base weekly period, including extensions, off days, and playoff boundaries.
Neither a date anchor nor the league's weekly grouping fills that gap.

## Implemented behavior

Reject scheduleSettings.matchupPeriods as a daily calendar, including plausible
arrays. Ignore legacy scheduledWeeks exports based on that interpretation.
For completed weeks, retain both historical metadata endpoints only when they
agree with canonical observed period membership, season limits and the stored
date anchor. Do not fill missing endpoints. Current/future observations never
become scheduled dates. The payload identifies observed/unavailable range kind,
source and period IDs; the UI labels historical dates as observed.

All 93 prior historical ranges are restored from unchanged metadata. Archived
metadata, canonical daily records, scores, season detection, request count,
timezone conversion, legacy Dash and the three-hourly updater are unchanged.
No authoritative scheduled range is currently exported.

| Season/week | Daily periods | Dates | Evidence and classification |
|---|---|---|---|
| 2027/1 | 1–6 observed so far | Oct 20–25, 2026 observed so far | Live points membership; full range unavailable, dates withheld |
| 2027/2 | unavailable | unavailable | Assignment exists, no verified daily boundaries |
| 2027/10 | unavailable | unavailable | Assignment exists, no verified daily boundaries |
| 2026/1 | 1–6 | Oct 21–26, 2025 | Metadata + canonical map + live points membership; observed |
| 2026/17 | 112–125 | Feb 9–22, 2026 | Same sources; observed extended week |
| 2026/21 | 147–153 | Mar 16–22, 2026 | Same sources; observed playoffs |
| 2026/11 | 70–76 | Dec 29, 2025–Jan 4, 2026 | Same sources; observed cross-year |

The retained anchors for 2023–2027 remain metadata inputs, never production
constants. The safe fallback applies to the saved snapshot without refreshing
player records to today's live period.

## Projection implications

Past observed ranges support historical evaluation, but cannot certify game
counts over complete future matchups. A projection engine must distinguish
known daily game schedules from verified fantasy-week boundaries. Until a
validated calendar is available, complete matchup projections should remain
unavailable rather than assuming seven days or truncating at the latest game.

## Validation

98 backend tests pass, including existing UTC/league-timezone regressions.
99 exporter tests pass after full generation; the first run exposed a stale
checked-in player manifest (2026 versus current snapshot 2027), resolved by the
normal generate_all step. Unrelated generated artifacts are excluded from this
calendar-only commit. React tests and Vite production build pass. Chromium
checks pass at 1280, 720, 390 and 320 pixels; restored cross-year, extended and
playoff dates are checked at desktop and mobile widths with no horizontal overflow.

GitHub API access and the Pages host returned Forbidden from this environment.
Deployment verification must therefore be reported separately from local success;
a push triggers the existing codex Pages workflow, but is not proof of deployment.
