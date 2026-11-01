> Historical Stage 2 preparation record. See [public frontend rollout](live-scoring-frontend-production.md) and [production activation](live-scoring-production.md)
> for the subsequent Stage 3 workflow, configuration, verification and rollback status.

# End-to-end live scoring — prepared, not activated

Starting codex commit `1fbdda5`. The three-hour canonical updater and historical
CSV semantics are unchanged. Live data is a separate temporary Supabase overlay.
No production live flag, automatic publisher, GitHub secret or main branch was
changed during implementation.

## Activation boundary

- Frontend: `VITE_ENABLE_LIVE_SCORING` defaults **false**. Disabled builds perform
  no Supabase requests and render no live indicators.
- Publisher: schedule jobs require repository variable
  `LIVE_SCORING_AUTOPUBLISH=true` **and** the default main branch. This variable is
  not set. The new workflow is prepared only on codex. Manual execution defaults
  to dry-run; publishing requires an explicit manual input.
- The preparation commit uses `[skip pages]`. The codex Pages workflow recognizes
  that marker and skips the direct build/deployment. Normal later pushes retain
  their deployment behavior. The existing canonical workflow may still publish
  ordinary scheduled data with the live feature disabled; it was not disabled.
- No new schema migration is required. The applied Stage 2A schema remains valid.

## Publisher and game windows

`.github/workflows/live-scoring.yml` has a five-minute UTC trigger, concurrency
`basketball-brawl-live-scoring`, an eight-minute deadline, read-only Git permissions,
no Git commits, no Pages permissions, no build/deploy actions, and no live files in
Git. It checks out codex code and main's read-only season metadata.

`liveWindow.py` first checks the verified fantasy calendar and cached NBA fixtures
without dependencies/network. Only candidate windows install existing Python
requirements and query public NBA status. It normally begins 60 minutes before a
confirmed tipoff, continues through live/delayed/overtime games, and observes a
30-minute post-final window. Yesterday's fixtures remain eligible across New York
midnight; tomorrow's confirmed near-midnight tipoffs can be included too. All
clocks are UTC and civil dates use America/New_York, including DST changes.

Canceled/postponed/TBD fixtures and missing/stale coverage are not interpreted as
zero. Unassigned Cup obligations trigger best-effort quarter-hour public status
discovery in the relevant Cup window (unlocalized uncertainty remains explicit).
Known fixtures omitted by a response fail closed rather than overwrite good data.
Postponed/unknown games fall back to quarter-hour discovery. Last observed active
status keeps exceptionally long games monitored. A changed schedule signature
reopens a previously closed window. After the postgame window, later corrections
remain the canonical updater's responsibility.

Small public gate state, plus the existing normalized adapter snapshot/ETag state,
are restored/saved using Actions cache, never committed. Cache entries contain no
credentials/raw authenticated responses. The OS lock file is harmless across
runners; the underlying lock is released by process exit. The cache is an
optimization: a cold gate conservatively starts its post-final observation clock
when it first sees finality. Cache misses can add a short extra observation period.

The gate typically adds **one public NBA request** to the adapter's two reads:
roughly **36 ESPN requests per live hour**. Midnight can require two date checks,
so budget up to **48/hour**, plus retries and the unchanged canonical pipeline
(roughly ten requests/hour amortized in the measured warm case). Fresh complete
no-game/off-hours windows make no ESPN requests. Uncertain discovery can still
make bounded public checks; it does not blindly run the fantasy adapter all day.

Actions scheduling is best effort. The cron is offset from the hour, but can be
late or coalesced; five-minute collection is a target, not a guarantee. A true
freshness SLA would need a more dependable scheduler in a later stage.

## Shared React data flow

One `LiveProvider` and store serve Home/Scoreboard. There is no per-component
Supabase polling. Relevant visible current pages check small scoped row metadata
every **20 seconds** in pregame/live/postgame windows. Outside those windows they
check at most every five minutes. Hidden tabs stop timers/abort requests; focus
resumes without duplicating an in-flight request. Historical/other pages do not
poll live data. Each request has an abort deadline; responses from a discarded
context cannot overwrite the current one.

Metadata reads exclude the JSONB body. The full snapshot is fetched only when
revision changes; unchanged payloads retain object identity. A newer successful
heartbeat can update freshness without downloading the body again. Scope/freshness
validation precedes application. No page key depends on live revision: scroll,
selected matchup/date, filters, expanded sections and header state survive updates.

Only public URL/publishable key/league UUID reach the bundle. Build validation
rejects secret keys and credential-named VITE variables, even if the feature is
disabled. `frontend/.env.example` contains blank public configuration names, not
actual values. No Supabase SDK or Realtime subscription was added.

### Merge rules

- Require matching configured league UUID + ESPN league ID, season, matchup week,
  scoring period and date; validate row/payload versions, identities and scores.
- Use successful `verified_at` for freshness and compare it with canonical
  ingestion `updatedAt`, not the Pages publication time. Reject stale (>10-minute),
  future, out-of-order or older-than-canonical observations. A content timestamp
  may be older when a newer genuine check reconfirms unchanged data.
- Home/Scoreboard replace **official scores**, never add them to existing totals.
  Current-day detail replaces its period's contributions, never appends a duplicate
  game. Earlier dates and historical contributor ownership remain intact.
- Bench/IR retain game points but contribute zero. Only observed participation
  establishes starts. Actual game statuses come from NBA data, not a tipoff-time
  heuristic. Current-day official/player discrepancies remain unadjusted.
- If today's canonical contributor disappeared from the live roster (a potentially
  locked drop/trade), official scores can update but player detail remains
  canonical with an explicit reconciliation note. Missing historical ownership
  is not invented from today's roster.
- Projections/opportunities retain their canonical baseline and timestamp. Projected
  final continues to use baseline actuals, **not newer live actuals plus potentially
  already-started projected games**. Existing values remain available and clearly
  labeled; this stage does not recompute projections on the fast path.
- Weekly Home individual-game rankings remain canonical, with a note. Current
  player/game-status updates appear in the detail lineup; no fabricated full-week
  top-five reranking is done from incomplete historical data.
- A transient failed/invalid read retains a compatible last-good overlay only while
  fresh, with a delay indicator; stale data falls back to canonical. An empty scoped
  result (private/withdrawn public row) clears the overlay on the next check.

A new live period waits for matching canonical context; it cannot be applied to
yesterday's or a historical matchup. In an unusual early game coinciding with
canonical rollover lag, live display can be delayed until the canonical updater
publishes that scope. This conservative limitation is preferable to mixing periods.

## Backend robustness found during integration

A cold adapter cache can reproduce identical hashed content with a different
updatedAt/change-hint envelope. The publisher now resolves that conflict by reading
the scoped stored row, proving identical meaningful content/revision, and reusing
only its existing envelope before the atomic RPC retry. Concurrent newer content
is rejected. SQL ordering/locking protections remain authoritative; no migration
or unsafe GET-then-PATCH was introduced.

Real read-back also exposed PostgreSQL's omission of trailing fractional timestamp
zeros, which Python 3.9's ISO parser rejected. The publisher now pads fractional
precision for database timestamps without dropping timezone information. The
snapshot had already committed correctly; retrying the exact input returned
`unchanged` and verified its JSON/freshness, without repeating ESPN reads.

## Configuration and manual tests

GitHub repository **Actions secrets** (names only) are:

| Secret | Purpose |
|---|---|
| ESPN_S2 / SWID | Existing authenticated ESPN adapter |
| SUPABASE_URL | Existing Supabase project root URL |
| SUPABASE_SECRET_KEY | Trusted backend-only publishing |

All four names were already configured when inspected. No values were read into
logs or changed. Publishable keys are not needed in the backend workflow.

After approval, add these **repository variables**, not backend keys:

| Variable | Value |
|---|---|
| VITE_ENABLE_LIVE_SCORING | `false` during preparation; `true` only for approved activation |
| VITE_SUPABASE_URL | Public project URL from your Supabase project |
| VITE_SUPABASE_PUBLISHABLE_KEY | Publishable key only, never the secret key |
| VITE_LIVE_LEAGUE_ID | UUID of Basketball Brawl in the `leagues` table |
| VITE_LIVE_ESPN_LEAGUE_ID | Optional; defaults to `609694684` |
| LIVE_SCORING_AUTOPUBLISH | Leave absent/false until approved; true activates schedule jobs |

Local preview configuration uses the same VITE names in ignored frontend local
environment files. Only public values belong there. Do not copy ESPN/secret keys
to any VITE variable. Both Pages build workflows have prepared public-variable
wiring on codex. The main canonical workflow still needs its small build-environment
diff applied under a later approval, so the next canonical deployment does not
silently build a different feature-flag state.

Manual test command (once GitHub recognizes the workflow):

```bash
gh workflow run live-scoring.yml --ref codex -f publish=false -f force=true
```

This is one forced adapter **dry-run**, no Supabase write and no activation flag
change. For one deliberately requested publication, use `publish=true`. Normal
window-gated manual runs use `force=false`. A successful local gate + publisher
manual equivalent is also possible with existing CLI commands; no scheduler is
needed for that validation.

GitHub may require a workflow to exist on the default branch before dispatching
it. If it returns 404/422, do not work around this by enabling recurring jobs or
merging the frontend branch. After approval, transfer **only** the new live
workflow and the existing canonical workflow's small public-build-environment diff
to main. No Dash code or full codex branch merge is necessary.

## Approval sequence and emergency disable

1. Review/approve the two minimal main workflow changes and public frontend
   configuration. Keep both activation flags false during that transfer.
2. Run one forced manual dry-run, then one explicit manual publish/read-back; check
   gate behavior and source freshness during a bounded game-night trial.
3. Approve frontend activation, set VITE_ENABLE_LIVE_SCORING=true, and deploy through
   the normal Pages workflow: push an approved commit touching frontend/** without
   the [skip pages] marker. Merely changing a repository variable does not rebuild
   already deployed JavaScript. Verify desktop/mobile and canonical fallback.
4. Only then approve LIVE_SCORING_AUTOPUBLISH=true. Monitor lateness/errors/usage.

To stop new automatic publications, set LIVE_SCORING_AUTOPUBLISH=false and cancel
any currently running live job if immediate cessation is required. This does not
stop canonical reconciliation. To withdraw the public overlay promptly, set the
league's `is_public` false in Table Editor (or SQL Editor); an open active page
clears it at its next ~20-second check (off-hours ≤5 minutes). No browser can be
revoked synchronously while offline. For a permanent frontend disable, set the
VITE flag false and redeploy both consistent builders. Do not delete snapshots or
historical data. Re-enabling public access/automatic updates requires approval.

Rollback can revert the integration commit on codex and deploy the prior frontend;
canonical files and historical results were never changed. Keeping the small
Supabase schema/row is harmless. Do not force older data into the newer snapshot.

## Expected free-tier usage

The [current Supabase free plan](https://supabase.com/pricing) lists unlimited API
requests, 500 MB database size and 5 GB egress (with a separate cached-egress
allowance). Do not assume REST reads consume the cached allowance. Inactive free
projects can pause; absence/failure falls back to canonical.

Illustration: six active hours/day, 30 days/month, ~70 KB changed payload every
five minutes and ~0.5 KB metadata every 20 seconds. Each continuously visible
viewer transfers about **150 MB/month of full snapshots + 16 MB metadata**, plus
small off-hour checks. Ten such viewers are roughly **1.7 GB/month**, plus about
0.15 GB backend read-back and protocol/other traffic. One hundred viewers could
exceed **16 GB/month**, above free egress; measure actual usage before expanding.
Metadata-only checks prevent the much larger cost of fetching 70 KB every 20
seconds. The database keeps one current row per league/season; monitor storage,
WAL/vacuum and usage in the dashboard. No paid service was added.

## Validation record

- **224 backend tests, 165 exporter tests and 91 frontend tests passed**, as did
  enabled and disabled Vite production builds. Workflow YAML parsed successfully.
- Desktop, 390px and 320px local browser checks used controlled Supabase responses:
  Home/list/detail updates, unchanged metadata-only checks, stable DOM/scroll/date
  selection/expanded details, baseline projections, stale/network fallback,
  historical isolation and disabled zero-Supabase-network behavior passed.
- One bounded real NBA gate check returned an active game window. One local
  workflow-equivalent adapter publication reached Supabase and matched its stored
  JSON/revision; after the timestamp parser correction, the exact idempotent retry
  passed. No further ESPN query was needed for the retry.
- Production flags remain off; no main changes, new schema, historical writes,
  automatic publication or direct Pages rollout was performed.

Exact final test counts, commit and attempted GitHub manual-dispatch status are
reported with the task result. Unknowns remain GitHub scheduling latency under
load, sustained provider quotas and real viewer traffic; this stage promises no
hard five-minute SLA.
