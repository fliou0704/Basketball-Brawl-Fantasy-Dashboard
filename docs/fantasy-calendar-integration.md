# Automatic ESPN fantasy calendar

The updater now reads ESPN's public Fantasy Basketball Scoreboard bootstrap at
`https://fantasy.espn.com/basketball/league/scoreboard`. It joins
`constants.segments[segmentId].periodTypes[periodTypeId].periods` to the league's
`scheduleSettings.matchupPeriods`, then labels each daily period using its
`constants.scoringPeriods` New York end boundary minus one civil day. Period 1's
start timestamp includes the offseason and is deliberately not used as its date.
See [the source investigation](fantasy-calendar-research.md) for evidence.

## Persistent canonical dataset

`data/seasonMetadata.json` retains the existing observed `weeks` unchanged.
Each season can additionally contain:

```text
fantasyCalendarContext: season, segmentId, periodTypeId, firstPeriod, finalPeriod,
                        regularWeeks, matchupPeriods
fantasyCalendar:
  schemaVersion: 1
  context: the validated league configuration
  source, sourceUrl
  days: [{period, date: YYYY-MM-DD, week}, ...]
  verifiedAt: last successful verification, UTC ISO timestamp
  lastAttemptAt: last attempted verification, UTC ISO timestamp
  lastError: safe failure reason, only after an unsuccessful attempt
```

Matchup ranges are derived from the ordered daily rows instead of duplicated in
the canonical cache. `frontend/public/data/fantasy-calendar.json` exports verified
seasons with `days` and derived `weeks` (`firstPeriod`, `lastPeriod`, `start`,
`end`). Scoreboard and per-week detail exports consume those same validated rows.
`frontend/src/fantasy-calendar.js` provides reusable lookups and civil-date
formatting; the browser never requests ESPN.

## Refresh, failures and schedule revisions

The normal three-hour updater checks the active season's cache locally. A
successful verification is eligible for another check after 24 hours. An
unsuccessful attempt has its own 24-hour cooldown, including failed initial
discovery. Failure never advances `verifiedAt` or replaces the previous rows.
The public HTTP reader has a timeout and at most two attempts per refresh.
Malformed/contradictory responses also enter the cooldown.

The existing workflow already commits `seasonMetadata.json` on main after
validation, exports, tests and build; thus both clocks persist across runner
instances. Its shared `basketball-brawl-pages` concurrency group serializes the
updater and normal codex Pages builds. No workflow changes or additional writes
to main are required. Existing staging and atomic metadata writes are retained.
If unrelated validation prevents the entire pipeline from committing, no
candidate data or new verification clock is promoted.

A newly discovered season has its own empty cache and initializes regardless of
the previous season's timestamps. Previous-season caches are retained at rollover.
The reader also supports archived seasons by discovering ESPN's versioned public
calendar bundle from the current application's loader. It never evaluates remote
JavaScript. Normal operation refreshes only the active season, without an
automatic historical rebuild. Archived seasons without a cached scheduled
calendar continue to show their validated observed dates.

For an intentional manual override (preview unless `--write` is specified):

```bash
python nearLiveUpdater.py --data-dir /path/to/disposable/data --force-calendar-refresh
```

Only accept consecutive, unique daily IDs/dates, complete configured matchup
coverage, contiguous base-period groups and valid season bounds. Compare against
canonical observed dates and matchup membership, including today's status, and
freeze all previously verified periods through the current available period.
Log changed dates/memberships and affected matchup weeks before accepting future
adjustments. Ambiguous past changes are rejected. A changed league configuration
invalidates use of an older cache until matching verification succeeds; it does
not bypass the normal request limit. Stale but matching valid calendars remain
usable during outages. Export-time validation suppresses a cache that conflicts
with the exact published observations.

Calendar-only checks do not advance the score snapshot's `updatedAt`. The normal
export fingerprint includes calendar verification and rows. Existing canonical
CSV meanings, scoring, historical identities, eligibility and aggregation are
unchanged. Scoreboard can navigate configured future playoff dates before ESPN
publishes participants. Unknown opponents remain unknown.

## UI and limits

Scoreboard, matchup headers, daily chart labels/tooltips, day selectors, daily
cards, insights and player daily contributions display ordinary dates. Formatting
does not interpret a civil date through the visitor's local timezone. Missing
dates remain explicit; archived observations retain their observed designation.

Remaining-game totals, potential starts, projections and optimization remain
disabled for unfinished matchups, even when scheduled dates are verified. The
existing estimator's tests require an explicit test-only opt-in; production never
exports it.

ESPN's bootstrap/asset schema is undocumented and can change. Schema checks,
bounded requests, safe error reporting and last-known-good retention contain that
risk. Fantasy calendar coverage does not establish complete NBA fixture coverage.

## Validation

Validated 2027: 23 matchup weeks, 167 days; Week 2 October 26–November 1,
Week 18 February 15–28, playoffs March 15–April 4. Tests cover parsing, malformed
data, extended/multiple base periods, playoffs, DST and host zones, persistent
success/failure clocks, force refresh, new seasons, future revisions, historical
conflicts, static exports and disabled remaining totals.

Two live updater runs used a disposable copy of main. The first initialized the
calendar; the second ran with calendar HTTP explicitly blocked and reused the
persisted cache. All four canonical CSVs remained byte-identical. A stale-cache
experiment refreshed successfully; a simulated failure retained its prior rows
and success timestamp. Live archived 2026 discovery also succeeded. Desktop,
390px and 320px browser checks covered current/daily/player views, reload,
future/extended/playoff navigation, historical fallback and horizontal overflow.
