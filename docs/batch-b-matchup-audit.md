# Batch B: matchup data audit and implementation

Starting commit: d535e28b2877eda68b3171b3ea8b6df39dad3548 (local HEAD matched origin/codex after fetch and fast-forward pull).

## Available sources before UI work

| Information | Canonical source | Treatment |
|---|---|---|
| Season, matchup week, team IDs and opponents | seasonMetadata.json matchups; basketballBrawlLeagueData.csv fallback | Route uses season/week/sorted numeric team IDs, independent of display names and ESPN schedule record IDs |
| Names, logos, colors | existing team_info exporter / dataStore configuration | Same identity utilities as Scoreboard and Home |
| Historical final FPTS | basketballBrawlLeagueData.csv | Preserve canonical totals and winner logic |
| Current scores | seasonMetadata.json pointsByPeriod plus canonical period map | Preserve existing Scoreboard accumulation |
| Weekly contributors | playerDailyData.csv joined to scoringPeriodMatchupMap.csv | Active-slot points; played starts require MIN > 0; original team ID retained per day, including trades |
| Daily raw stats | weighted CSV fields plus season scoringWeights | Reuse raw_stats; missing stats remain unknown |
| Daily team totals | active-slot daily CSV records, explicit ESPN pointsByPeriod when no records | Never repeat weekly totals as daily values; absent evidence stays null |
| Historical dates and extended/playoff periods | retained seasonMetadata.weeks plus validated period map | Existing observed_dates validation retained, including cross-year and 14-day weeks |
| Current roster and positional eligibility | currentLeague.json | Membership separated from historical contributions |
| Active/bench slots | seasonMetadata.lineupSlots / benchSlots | Existing authoritative roster settings |
| NBA games, opponents, game completion | ESPN proTeamSchedules_wl | New allowlisted snapshot, one extra request per update, independent from fantasy schedule |
| IR membership, NBA team identity, injuries, locks and limits | live league roster objects / rosterSettings / acquisitionSettings | New allowlisted fields in currentLeague.json; no browser authentication |
| Complete future fantasy-week daily boundaries | **Unavailable in inspected ESPN views** | No extrapolation or seven-day assumption; counts remain unavailable |

## Live read-only validation, October 26, 2026 ET

ESPN league 609694684 / 2027 reports currentMatchupPeriod 2 and scoringPeriodId 7.
Roster settings provide PG, SG, SF, PF, C, G, F and three UT slots (10 active),
five BE, two IR, INDIVIDUAL_GAME lineup locks and FIRSTGAME_SCORINGPERIOD roster
locks. No lineupSlotStatLimits are set; matchup acquisition limit is 1. Future
acquisitions are intentionally excluded from the current-roster upper bound.

The current mSettings/mMatchupScore/mTeam request confirms periodTypeId=2 and
matchupPeriods {1:[1], 2:[2], …, 23:[23]}. As previously established in
[the calendar investigation](scoreboard-calendar-investigation.md), those are
base **weekly** IDs. They cannot map Week 2 to daily IDs, or establish its end.
The earlier investigation also checked game state/settings, future-period
queries and pro-team schedules. Those sources do not supply the missing daily
to weekly calendar. Current live metadata does not overturn that finding.

proTeamSchedules_wl supplies date, scoringPeriodId, home/away pro-team IDs,
game ID and statsOfficial. It does not supply a reliable live game-state flag.
Official stats establish completed games. A nonofficial game whose timestamp
has passed is reported as started/unconfirmed and excluded from future counts;
it is never silently classified as completed or fully remaining.

## New browser exports and routes

`#/scoreboard?season=2027&week=2&match=1-17` is the stable route form. The actual
participating IDs determine the final key. The existing hashchange router handles
refresh, back and forward. Each Scoreboard card is a native keyboard-accessible
anchor. Details have Overview, Daily and Players views, with a selectable daily
or cumulative chart and per-day player stats.

`scoreboard.json` contains a detailPath per week. Only a selected week's
`matchups/{season}/{week}.json` is fetched. It includes per-match daily team
points, cumulative snapshots, recorded played starts, original contributors,
current membership flags, decoded stats, reconciliation state and remaining
opportunity availability. Snapshot timestamps must match the Scoreboard; mixed
deployments fail closed. No full historical rebuild is added to the updater.
The exporter follows the existing scheduled generate_all path.

Insights require complete daily snapshots that reconcile with canonical scores.
Ties preserve the previous non-tied leader; a change is counted when the next
non-tied scoring-period-end leader differs. Largest comeback means a recorded
deficit later recovered to at least a tie. It does not imply intragame tracking.
Corrections are not spread across dates to force reconciliation.

## Remaining opportunities contract and blocker

A completed matchup has zero remaining opportunities. An unfinished matchup
requires an explicitly verified scheduled range, complete NBA coverage and a
dated snapshot before counts are published. Observed current endpoints cannot
satisfy this requirement. With current inputs, unfinished totals are unavailable.
There is deliberately no fabricated scheduled range producer or manual override.

The tested calculation accepts future verified period ranges, counts distinct
player/game pairs inside those bounds, excludes official completed games and
all games whose start has passed, checks NBA dates against the New York fantasy
calendar, and retains zero-game days. Potential starts use maximum bipartite
matching between each day's current players and the actual eligible active
slots, excluding IR membership. One player cannot occupy multiple slots. These
are upper bounds: health, future decisions, already locked players, roster moves
and any season game limits can reduce starts. Unsupported lineup locks suppress
the starts estimate. Unknown schedule coverage or player NBA team identity
suppresses complete totals.

Next prerequisite for projections: obtain and independently validate an
authoritative daily-to-fantasy-week calendar, including off days, extensions and
playoff grouping. Reconcile player contributions against daily team totals
before using future expected player production. No scores, probabilities,
injury predictions or roster recommendations are projected in this batch.

## Verification results

- 108 offline backend tests pass; 134 exporter tests pass against fresh disposable exports; 49 frontend tests pass; Vite production build passes.
- Disposable updater verification used a copy of origin/main data and retained bounded periods 1–7 for season 2027. It inserted 27 daily rows and corrected 49 existing rows without deleting rows. Canonical weekly league/player totals did not change. The exported NBA schedule has complete team coverage and 2,400 team/game records.
- Five of five live 2027 Week 2 timelines reconcile. At the validation snapshot, I Watch Basketbal has 221 FPTS / 7 recorded starts, versus Wembarrassingggg at 180 / 7. These are live partial scoring-period totals, not final results.
- All five historical Week 1 and extended Week 17 (2026) timelines reconcile. Week 21 playoff pairings reconcile; byes retain their distinct status. Future 2027 Week 3 has assignments and no fabricated scores or dates.
- Chromium desktop (1280px), mobile (390px), and compact mobile (320px) pass matchup navigation, direct URLs, reload, back/forward, all three views, unknown matchups, historical/extended/playoff/future cases and page overflow checks. Home and standings smoke checks pass. Team page loads, but its existing tabs/roster overflow at 320px remains outside this change.
- A first exporter suite run against existing local generated files exposed stale standings, recaps and player manifest artifacts. The same suite passes against complete fresh disposable exports. Existing user changes to those generated files remain untouched.
- Checked-in matchup detail files were generated from the workspace's existing canonical snapshot. Pages builds continue to regenerate from current main inputs through the existing workflow; live validation used disposable updated main inputs.
