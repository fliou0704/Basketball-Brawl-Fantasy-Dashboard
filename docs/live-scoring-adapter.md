# Lightweight live scoring adapter — Stage 1

Implemented on `codex`, starting from `fb74469`, October 31, 2026. This is an
**unpublished, one-shot adapter**. It does not run the canonical updater, write
CSVs/season metadata, call historical exporters, modify React, schedule jobs,
serve endpoints, deploy Pages, or change main. Existing local edits are preserved.

## Run locally

Use the existing project environment/dependencies and shared
`dataUpdateSafety.require_espn_credentials()` (`ESPN_S2` / `SWID`, including the
existing dotenv loader). No new authentication flow or credential files exist.

```bash
python liveScoringAdapter.py --season 2027 \
  --metadata /path/to/read-only/main-data/seasonMetadata.json \
  --output /tmp/brawl-live/snapshot.json
```

Both `--season` and `--output` are explicit. The output must resolve **outside the
repository**, preventing accidental canonical/Pages publication. Metadata is read
only; use the latest normal updater snapshot from main. The default metadata path
is `data/seasonMetadata.json`, but a stale codex data checkout is not necessarily
the latest production reference. No data synchronization is performed by this
command. There is no loop, sleep-based poller, default output, or new workflow.

Missing credentials report only variable names. Exit status 0 means a validated
check (including no-op); exit 1 means invalid input, failed check, or another
execution already owns this output. The CLI prints only metrics or sanitized
errors, never raw SDK/request exceptions.

## Two bounded requests

1. The existing `EspnFantasyRequests` class supplies the league endpoint/cookie
   structure, without constructing a League or triggering its player/draft/history
   requests. A shared Session transport reads
   `.../fba/seasons/{season}/segments/0/leagues/{id}` with
   `view=mMatchupScore&mScoreboard&mSettings`. No scoring-period override means
   ESPN selects its current period. The normalizer checks top-level scoringPeriodId
   against status.latestScoringPeriod and retains **only current-week matchups and
   current-period player statistics**. ESPN incidentally includes other schedule
   assignments; those are discarded, not exported or queried individually.
2. An anonymous public NBA scoreboard read for the verified fantasy scoring date:
   `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
   with `dates=YYYYMMDD&limit=100`. It supplies actual game states/clock/teams.
   Public and authenticated traffic use separate Sessions in normal operation.

No prior season, per-player card/profile, seven-day reconciliation, projection
history, transaction history, full NBA fixture list, or calendar-discovery HTTP
request is made. The read-only verified fantasy calendar supplies
period → week/date mapping, including extended weeks/playoffs. Its configuration
must agree with the live league settings. It never uses wall-clock seven-day
windows to infer a fantasy week. NBA timestamps are normalized with the existing
New York timezone utility; after-midnight UTC games keep their New York date.

## Snapshot schema (version 1)

The primary JSON is a full replacement snapshot, suitable for later React state
updates without a remount. It is **not** an incremental points ledger.

| Field | Meaning |
|---|---|
| schemaVersion | 1 |
| leagueId / season / week / scoringPeriod / date | Stable ESPN context and verified New York scoring date |
| calendarContextHash | Identity of the verified calendar configuration |
| revision | SHA-256 of normalized content, excluding update time/change hints |
| updatedAt | UTC time of the last meaningful content change; not a freshness heartbeat |
| matchups[] | Stable matchupId, ordered teamIds, officialScores, source winner indicator |
| teams[] | Stable teamId/name; officialScore and its source field; officialPeriodScores and officialDailyScore; rosterDailyScore; playerCreditedSum; diagnostic differences; current players |
| teams[].players[] | Stable playerId/teamId; current proTeamId and optional current-period statProTeamId; lineup slot ID/name; eligibleSlotIds; scoringEligible; fantasyPoints, creditedPoints, statPoints; actual-stat/played evidence; raw actual stat values; injuryStatus; gameIds/coverage |
| games[] | Stable NBA gameId, UTC start/New York date, home/away NBA IDs, actual state/name, period/clock and time-TBD flag |
| changes | baseRevision plus changed/removed team, matchup, player and game IDs |
| scoreAuthority / gameAssociation | Explicit descriptions of score authority and NBA affiliation joins |

A score change identifies the relevant matchup through its officialScores. Injury
changes identify the player/team; game/clock transitions identify the game, which
players reference by ID. Consumers must apply the full snapshot if their revision
is not changes.baseRevision. They must also key context by season/period and reject
older versions; a revision is a content hash, not a chronological counter.

### Official scores, eligibility and appearances

- `totalPointsLive` is authoritative when supplied; `totalPoints` is a clearly
  labeled official fallback, not relabeled as a proven live total. The response's
  pointsByScoringPeriod remain available independently. Scores are never replaced
  with recomputed player sums.
- Player fantasyPoints retain ESPN playerPoolEntry.appliedStatTotal. Daily actual
  stat objects use **statSourceId=0, statSplitTypeId=5**, matching season and period;
  projections, season aggregates and other days are excluded. statPoints retains
  appliedTotal separately. The adapter does not calculate a fantasy scoring formula.
- Actual selected slots are classified using the league's enabled lineup slots
  and the SDK POSITION_MAP. Starting-slot points contribute to creditedPoints;
  bench/IR retain their game points but contribute zero. This is current scoring
  eligibility, not a start/sit recommendation or future optimizer.
- Missing actual statistics do not manufacture appearances: played/statPoints
  are null when evidence is absent. A roster scalar of zero remains a reported
  zero, not proof of a DNP. Nothing is appended to playerDailyData.csv.
- `dailyDifference` is officialDailyScore minus eligible player points;
  `periodSumDifference` is official matchup total minus reported current-week
  daily totals. Nonzero differences are preserved, not spread across players/days.
- NBA game IDs use the stat's NBA team for an observed current-period performance
  when supplied, otherwise the player's current NBA affiliation. A fixture is not
  proof that the player appeared. Missing events have explicit no-event-observed
  coverage; they do not invent final/DNP statuses. Free agents remain distinct.

## Persistence, freshness and failure behavior

Three local files accompany each explicit destination:

- `snapshot.json`: validated allowlisted snapshot only. Atomic replacement with
  flush/fsync; no rewrite or mtime change when normalized content is unchanged,
  including unchanged 200 responses and 304 responses.
- `snapshot.json.state.json`: **internal cache/status**, not a browser payload.
  Holds normalized components, ETags/hashes, context/revision, successful
  verifiedAt, lastAttemptAt, sanitized error, and computed freshness. There are no
  raw authenticated bodies, cookies, owner data, request headers or secret values.
- `snapshot.json.lock`: persistent lock-file inode with a nonblocking OS flock.
  A competing process exits before network or snapshot writes. It does not delete
  another process's lock file; OS ownership releases after exit/crash. Supported
  execution environments are macOS/Linux, not Windows.

The primary snapshot is promoted only after **both** endpoint components and the
join validate. Partial responses, missing current teams/rosters/scores, duplicated
identities, invalid numbers, unknown slots, mismatched calendar/season, conflicting
NBA events, or omitted known current-date fixtures fail closed. An empty NBA
response can be accepted only with a valid response envelope and no missing known
fixtures; absent player events remain explicitly unconfirmed.

ETags are persisted per endpoint and sent with If-None-Match. A 304 requires a
validated normalized cache. A changed date drops the NBA ETag; league/season/cache
version changes invalidate caches. Calendar compatibility is rechecked on 304.
Snapshot/component hashes detect local corruption; a crash between the two atomic
file replacements invalidates component reuse on the next run. Bump CACHE_VERSION
when changing normalized cached semantics; change schemaVersion for incompatible
consumer contracts. This is a local cache, not a multi-file database transaction.

Each request has 10-second connect / 35-second read timeouts, no redirect following,
a 20 MB decoded-response acceptance limit, and at most three attempts. Transient
network/429/5xx responses use bounded 1/2-second backoff, honoring a numeric
Retry-After up to ten seconds. Longer/date-form retry instructions defer the run;
they are not bypassed. Invalid JSON/response shapes and 401/403 are not retried.
Thus two successful requests is the normal count; six is the retry ceiling.
The response limit rejects oversized decoded content after receipt, not a streaming
wire-byte quota. Read timeouts are requests' inactivity limits, not a whole-process
deadline; Stage 2 should also impose a job/service deadline.

Failure retains the last primary snapshot and successful verifiedAt, records a
separate failed attempt/error, and exits nonzero. `freshness(state, now)` marks a
snapshot stale after ten minutes (or immediately without a valid success time /
with a future clock). A recent failure still has an error even if its last good
snapshot is under ten minutes old. Recompute age at read time; a saved freshness
flag alone does not age itself. No-op checks refresh only the internal state.
A future public freshness manifest must expose a small allowlisted subset, **not
serve the internal cache file**. Missing/stale data must stay visible as such.

## Controlled real-ESPN validation

October 31 at approximately **5:35 a.m. ET**, using disposable main metadata and
external temporary outputs. Current context: **2027 Week 2, period 12, October 31**.

| Measurement | Cold | Persisted warm check |
|---|---:|---:|
| Requests | 2 | 2 |
| Elapsed adapter time | 0.626 s | 0.663 s |
| Decoded response bytes | 568,539 | 141,349 |
| 304 responses | 0 | 1 (league) |
| Primary snapshot bytes | 64,865 | 64,865 |
| Primary rewritten | Yes | **No** |

These are single samples measured inside run(), after Python/module import; they
exclude process startup and are not a latency SLA. Byte counts include decoded
responses, not compressed wire transfer. The public NBA response did not provide
an ETag in this sample, so it still transferred its body on the warm check.

The limited comparison used the **same response** through the production SDK's
H2HPointsBoxScore, the full updater's `_record_for_player`, and existing scoreboard
`project` with the exact official daily fields retained by current_calendar. It
avoided running a full historical updater/export. Results:

- All **five matchups / ten official team scores** matched the current scoreboard
  exporter. Examples: matchup 6 **583–994**, matchup 7 **648–1,447**, matchup 10
  **1,059–780**. Current daily player sums and official daily totals agreed.
- **162 current players** matched SDK identities, fantasy points and selected
  slots, with no differences. At this pregame snapshot there were no current-day
  observed player-performance rows; seven NBA games were scheduled.
- One bounded completed-period control (period 11, October 30) matched **162
  roster entries**, including **83 recorded performance rows**, with no points or
  slot differences. There were 101 actual-stat objects, including objects without
  a recorded performance; all 101 were recognized with the verified daily split
  discriminator. One public prior-date control confirmed **10 completed games**.
- The comparison itself took 3 HTTP reads / 1,158,558 decoded bytes / 0.843 seconds.
  No past-season fetch or canonical write was performed. Diagnostic setup checks
  were bounded; no recurring polling or production workflow was dispatched.

### Existing historical discrepancies

The earlier standings audit already establishes seven daily source discrepancies
and an additional weekly discrepancy: for example **2026 Week 18, team 1: official
1,467 versus eligible player 1,471**. See `docs/standings-franchise-data-audit.md`.
This stage did not refetch old seasons or try to resolve their still-unknown ESPN
cause. A regression uses these values to ensure official and player totals remain
independent. Those old discrepancies are not evidence that today's roster adapter
is missing a player. Current-day equality in the sample is not an assumption that
all future or historical snapshots must reconcile.

## Tests and remaining gaps

Focused offline tests cover live score authority/fallback, known discrepancy
values, bench/IR, actual-vs-projected stat splits, missing appearance evidence,
identity/coverage failures, calendar and period/week boundaries, NBA affiliation
changes, New York late-night dates, actual final/in-progress/postponed/canceled
states, Cup championship exclusion, conditional/no-op persistence, stale/error
retention, bounded retries/authentication, atomic write failure, locks, changes
including score decreases/injury-only updates, and corrupt caches.

Validation passed **26 focused adapter tests and all 194 backend tests**.
`git diff --check` passed. No frontend build/test run was needed because no frontend
files, exporters, dependencies or build configuration changed.

A current in-progress NBA game was **not available at the validation time**;
in-progress/clock transitions are tested offline, while actual completed and
pregame source states were checked live. Real event-to-API lag, sustained provider
quotas, Fastcast delivery, game-night concurrent NBA/fantasy roster transactions,
and production CDN/publication behavior are not established here. The adapter
supports the existing H2H points league and requires an available verified calendar;
other scoring formats fail closed. It does not estimate injuries, predictions,
lineup locks beyond the supplied actual slots, or historical roster changes.

## Recommended Stage 2

Keep the three-hour canonical writer and historical exporter unchanged. Next add
an independently published **live snapshot plus small freshness/version manifest**
with controllable caching, using a single writer and five-minute fixture-aware
gating. Stage 1 alone has no cadence or hosting activation. Add a thin live exporter within the frontend data-export pipeline, runnable
independently of historical generation. A small external service/store is preferable to full Pages deployment for every score change;
GitHub Pages can keep serving the main application.

React should validate season/period/revision, apply only newer compatible snapshots
in place, retain previous data on errors, and display freshness. Official team
scores replace the live scoring view; they are never added on top of a canonical
current-period total. Use stable player/team/game IDs for partial rendering and a
canonical baseline/context guard before overlaying detail contributions. When full
reconciliation catches up, discard the corresponding overlay. Shadow comparisons,
a game-night trial, a service deadline/backoff budget, and failure monitoring should
precede any public rollout. No hosting, frontend integration, schedule or deployment
changes are authorized or implemented by this stage.
