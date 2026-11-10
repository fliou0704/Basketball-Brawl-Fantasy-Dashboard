# NBA schedule and remaining fantasy opportunities

Starting commit: `541db927385aa0c830127d63ca6bf16ba3a36df9` (`codex`, synchronized with origin).

## Sources and audit

The installed espn-api 0.41.0 already requests the full NBA fixture list:

```text
GET https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{season}
    ?view=proTeamSchedules_wl
settings.proTeams[].proGamesByScoringPeriod[period][]
```

The 2027 response contains 30 NBA franchises, 2,400 team/game entries and **1,200
unique games**, spanning October 20, 2026–April 11, 2027. Every franchise has 80
published fixtures. Fields include stable game ID, home/away IDs, epoch start,
scoringPeriodId, statsOfficial, validForLocking and startTimeTBD. The two copies
of each game must agree; they are normalized to one record per ID.

This is complete **published** coverage, not proof of 82 fully assigned games.
The [NBA's official release](https://pr.nba.com/2026-27-nba-regular-season-schedule/)
establishes two additional obligations per team, with pairings/dates assigned
after Cup group play, within December 4–10. No placeholder player-game rows or
arbitrary fixture dates are created for those obligations.

Fantasy's completion flag does not describe live/postponed/canceled states. The
updater therefore also reads two small public NBA scoreboards (yesterday/today
in New York), rather than reloading a full season each three-hour run:

```text
GET https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard
    ?dates=YYYYMMDD&limit=100
```

Inspecting actual responses established status.type.name/state/completed,
competitions[].timeValid, NBA participants and season.type. The Cup championship
is a special case: season.type may still be 2, but competition.type.id is **39**
(`CC`). The inspected December 16, 2025 championship (401809839) was absent from
the fantasy fixture source. Both checks prevent counting it as regular season.
The [NBA Cup FAQ](https://www.nba.com/news/nba-cup-frequently-asked-questions)
also distinguishes the championship from regular-season games.

Public team schedules for Boston (2), Golden State (9), and the Lakers (27),
requested with `season=2027&seasontype=2`, each matched all 80 fantasy-source IDs.
All 80 Boston start timestamps agreed as well. Range scoreboard requests returned
400 and a year query with an oversized limit silently truncated; neither is used
as season coverage evidence. No new provider, dependency, or per-player schedule
request was introduced.

The Python wrapper previously requested the pro schedule repeatedly during
League/team initialization and daily box-score parsing. `LeagueCache` now supplies
those calls from the same persistent cache, including constructor-time calls.
Public `players_wl`, already requested by the wrapper, supplies bulk current NBA
affiliations; the existing league request now includes mRoster to retain numeric
proTeamId and current fantasy ownership/slots directly.

## Canonical datasets and persistence

NBA fixtures are a separate logical dataset at:

```text
data/seasonMetadata.json
  nbaSchedules[ESPN NBA season year]
```

Using this existing persisted file avoids a new workflow or a main-branch code
change. The existing updater commits it after validation, exports, tests and build.

Each cache contains schemaVersion=2, season, source, teams, fixtures, season rules,
publishedComplete, parserOnly, verifiedAt, lastAttemptAt and optional lastError.
Status reads retain statusAt and optional statusError. UTC ISO timestamps are
separate from fixture identity. Each fixture includes:

| Field | Meaning |
|---|---|
| id | Stable ESPN NBA game ID, never team/date identity |
| season | 2027 denotes NBA 2026–27 |
| start / date | UTC start instant / America/New_York civil date |
| home / away | ESPN NBA franchise IDs, separate from fantasy team IDs |
| period | Original fantasy-source daily period; frontend week joins use verified dates |
| status | scheduled, tbd, unknown, in-progress, completed, postponed, canceled, replaced |
| regularSeason | Eligibility for regular-season opportunities |
| timeTBD | Known fixture date with uncertain tipoff; never fabricate a time |
| statsOfficial / validForLocking | Allowlisted original fantasy-source evidence |
| hasStarted | Sticky evidence preventing a resumed game from becoming a second new start |
| statusVerifiedAt | Latest public status observation, when available |
| originalStart / replacedBy | Retained resumption/replacement evidence when applicable |

No future records are inserted into `playerDailyData.csv`. Historical statistics,
team identities, eligibility, actual starts and FP/Start calculations are unchanged.

Old-season League objects can still be constructed by existing terminal-season
safety checks. Archived pro schedules include canceled/postponed records in excess
of played-game counts (2026 returned 1,234 IDs). Their unmodified parser inputs are
cached once with parserOnly=true and publishedComplete=false, then frozen. They
are never exported as current verified coverage or historical potential starts.

## Daily synchronization and reconciliation

`nearLiveUpdater.py` loads the registry before constructing League objects.
Each active NBA season has independent UTC success and attempt clocks. Under
24 hours, full-season HTTP is skipped. At/after 24 hours, one full fixture refresh
is attempted with connection/read timeouts and at most two attempts. Failure or
invalid data preserves the previous fixtures and successful timestamp, records
the failed attempt and enters a 24-hour retry cooldown. New seasons initialize
independently. Historical parser caches do not reload every three hours.

Manual override, preferably against disposable data:

```bash
python nearLiveUpdater.py --data-dir /path/to/disposable/data --force-nba-refresh
```

Without `--write`, the usual preview semantics apply. Force applies to the active
schedule, not every archived parser input. The normal three-hour process still
refreshes current rosters/affiliations and recent NBA status even with a cached
full schedule. Status absence is not evidence of cancellation or completion;
omitted known recent fixtures are treated as a failed status read.

Candidates require all 30 teams, unique coherent IDs, both team copies, valid
timestamps and plausible published season coverage. Empty/partial data cannot
erase a valid cache. Source omissions of previously verified IDs are rejected
unless a known canceled tombstone or an unambiguous unstarted replacement can be
retained. A replacement must have the exact original participants/start and one
new candidate ID; ambiguous replacements remain unavailable for review. Known
future IDs can move beyond the initially announced season window without being
mistaken for new postseason events. Preseason/postseason additions are excluded
from the verified 2027 regular-season window.

Future time/date/participant changes are compared by ID and logged. Completed or
in-progress historical date/participant contradictions are rejected. Canceled
records remain as tombstones, with active-game caps evaluated separately. Sticky
hasStarted prevents suspended/resumed games from being counted as new future
starts. These cases never rewrite observed player performances.

All changes use the existing staged candidate and atomic metadata writes. Existing
`basketball-brawl-pages` workflow concurrency serializes writers and deployments.
An unrelated validation failure promotes neither data nor new cache clocks.

## NBA Cup and other uncertainty

The cache distinguishes published fixtures, known unassigned obligations, unknown
statuses/times, and failed source coverage. A valid no-game date is different from
an unassigned Cup day. The 2027 verified Cup window localizes uncertainty to
fantasy weeks 7 and 8, without assigning either extra game to either week/day.
Confirmed counts remain labeled **confirmed**, while affected potential-start
totals are unavailable. New fixtures automatically reduce outstanding obligations
at the next daily refresh. Finalized 82-game coverage removes that uncertainty.

Unlocalized postponements, cancellations or resumptions are not assigned guessed
future dates. Their uncertainty can suppress potential-start estimates outside
the Cup window too. Unknown affiliations, failed/full stale coverage, conflicting
ownership and uncertain same-day start timing produce unavailable totals, not
zero. A confirmed pregame status can resolve a known-date, time-TBD game today;
future known-date/time-TBD fixtures retain their date and display `Time TBD`.

Full cache verification older than 30 hours or a failed full refresh suppresses
team counts until verification recovers. A failed recent status read suppresses
affected current-day counts; future dated fixtures remain available as confirmed
published opportunities. Statuses are never inferred to be completed just because
their scheduled time passed; those games are separately started/unconfirmed.

## Affiliations, fantasy ownership and lineup capacity

Weekly `playerMetadata.csv` athlete profiles are not trusted for live NBA team
assignment. `currentLeague.json` now retains numeric `nbaAffiliations` from the
existing bulk player request, with current-roster overrides, rosterVerifiedAt and
nbaAffiliationSince. Roster entries retain proTeamId, slot, eligibility, injury
status, rosterSince and nbaTeamSince. Stable player IDs are the join keys.

NBA trades change future fixture associations; fantasy adds/drops/trades change
the roster used for future counts. These refresh every three hours independently
of fixture discovery. Explicit NBA free agent ID 0 has no confirmed team games;
missing/unknown team assignment is unavailable. Two-way players use their ESPN NBA
assignment if known; unfamiliar/non-NBA IDs remain unknown. First-verified NBA and
fantasy ownership times reset on changes so a destination team's earlier game is
not retroactively treated as the player's locked start.

The reusable solver in `fantasyOpportunities.py`:

1. Selects verified scheduled days for the chosen fantasy week. No seven-day
   arithmetic; extended weeks, openings and playoffs use the same calendar.
2. Joins each current roster member to its NBA team's stable fixtures by NY date.
3. Counts distinct unstarted player/game pairs within the matchup. Completed,
   in-progress, canceled, already-started and resumed games are not future starts.
   Live and started/unconfirmed opportunities are reported separately, regardless
   of whether fantasy points have arrived in the scoring snapshot.
4. Reserves today's actual recorded active slots, even for contributors later
   dropped or traded. Verified pre-tipoff ownership and current selected starters
   can establish additional locked slots. New NBA affiliations never rewrite past
   player/team associations. Unknown locks can reduce the reported upper bound.
5. Uses maximum bipartite matching over each day's remaining PG/SG/SF/PF/C/G/F/UT
   slots and eligible players. IR is excluded from starts; bench players may be
   selected for future unstarted games. One player occupies at most one slot.

Scheduled Games count current-roster **player-game opportunities**, including IR
players' team fixtures, not guaranteed appearances or unique NBA events. Potential
Starts are an upper bound for that fixed roster and available lineup capacity;
they do not recommend a lineup. Injuries, DNPs, other locks and future transactions
can change the outcome. Unsupported locks, move limits, game-played limits,
multiple same-day fixtures for one player, and relevant unassigned games suppress
potential starts. No actual-start calculation or fantasy score is changed.

## Static exports and UI

* `nba-schedule.json`: one shared current NBA fixture list, teams, IDs indexed by
  date/team, current player affiliations, source/freshness/uncertainty, and explicit
  fantasyPeriod/fantasyWeek joins. Dates beyond this league's final week stay null.
* `matchup-opportunities.json`: active/future week → fantasy team → confirmed
  counts, potential starts, daily capacity, player game IDs and uncertainty. It
  does not embed fixture objects in every player/week.
* Active/future detail files reference the shared exports. The browser hydrates
  only the selected matchup and guards matching snapshot timestamps. Optional
  schedule read failure withholds opportunities while retaining actual scores.
* Finished detail files use a deterministic content identity, independent of the
  live roster clock. Unchanged historical artifacts are not rewritten by a fresh
  NBA/roster verification. Historical actual scoring/contributors remain intact;
  today's roster is never used to invent their potential starts.

The existing Overview, Daily and Players layout is retained. It now shows confirmed
remaining games, up-to potential starts, a dated opportunity table, player-level
game counts/opponents/times, Cup uncertainty and source/snapshot time. No projected
points, probabilities, injury predictions or start/sit recommendations are added.

## Verification

Disposable source snapshot: fetched main data. Initial update retrieved/persisted
all 1,200 fixtures. A second process, with full-season schedule HTTP prohibited,
reused the cache and refreshed roster/status inputs. Artificially aging only the
temporary active cache triggered a fresh active-season read while the historical
parser stayed frozen. Failure retention/cooldown, additions, replacements, trades,
conflicts, time zones, daily slot limits and uncertainty are exercised offline.
All four canonical CSVs remained byte-identical after the disposable updates. A separate actual updater run with a simulated full-schedule outage continued successfully, retained the prior fixtures/success time, persisted the failed-attempt clock, and skipped a subsequent retry within its cooldown.

Examples at the disposable snapshot `2026-10-27T18:48:16Z`:

| Week | Fantasy team | Confirmed remaining player-games | Potential starts |
|---|---|---:|---:|
| 2 | The Bronx Orthodox Church | 34 | Up to 33 |
| 2 | Big Wong | 42 | Up to 39 |
| 3 | I Watch Basketbal | 59 | Up to 43 |
| 3 | Jalen Jalen and Jaylen | 57 | Up to 44 |
| 7 | I Watch Basketbal | 34 | Unavailable — Cup dates unassigned |
| 7 | For All the bullDawgs | 30 | Unavailable — Cup dates unassigned |

These are snapshot-dependent opportunities, not predictions. Shared playoff week
counts are available per team, but playoff pairings remain unpublished until ESPN
provides them. UI verification covers current/future/Cup/extended/playoff and
historical routes at desktop, 390px and 320px, including unknown-data fallback.

## Maintenance limits

ESPN endpoints are undocumented. Requests and parsing are bounded and fail closed.
New seasons initialize automatically. A season without a verified published Cup
window treats unassigned obligations as unlocalized: confirmed games still show,
but precise potential starts wait for complete fixture publication. Standard
82-game/30-team coverage rules must be reviewed for NBA format changes or unusual
short seasons. Ambiguous started-game history/replacement conflicts are reported
rather than guessed. This is daily fixture discovery with three-hour roster and
recent-status snapshots, not real-time injury/participation tracking.

Validation completed: 146 backend tests, 140 exporter tests, 56 frontend tests, the Vite production build, and desktop/390px/320px browser checks. The optional-schedule outage browser check preserves actual scoring while withholding opportunity counts.
