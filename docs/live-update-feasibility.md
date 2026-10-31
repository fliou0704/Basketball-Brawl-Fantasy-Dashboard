# Live update feasibility

Research only, October 30, 2026 (America/New_York). No updater, workflow,
credentials, deployment, or recurring polling configuration was changed.

## Recommendation

Prefer **B: a small live snapshot alongside the existing three-hour canonical
reconciliation**, eventually served from an endpoint with controllable caching.
Keep GitHub Pages for the application and historical exports. Start with a
five-minute upstream cadence and 30–60-second visible-browser checks. Treat this
as a freshness target, not a guaranteed maximum latency. Do not start at one
second or integrate ESPN's internal push protocol.

The smallest useful next implementation is an **unpublished, current-period-only
snapshot adapter and comparison test**, using the already verified ESPN bulk
box-score view. It should fetch one league response plus today's NBA scoreboard,
normalize allowed live fields, and compare player/lineup/scoring identities with
the canonical exporter. Do not change cron first. Publication should follow only
after the adapter and cache/merge behavior pass those comparisons.

## 1. Scope and measurement method

- Synchronized `codex` without disturbing pre-existing local changes; starting
  commit `b4efc6c7decef72115c745b5035e42f9196e1901` matched `origin/codex`.
  Canonical data was read from `origin/main` (`d28782a` at fetch).
- Inspected ingestion and dependencies, export/build/publication workflows, and
  browser refresh clients; no general application review.
- Read the 12 most recent update run summaries (all successful), exact step
  timestamps for three runs, and available completed logs. This does not rule out
  failures outside that sample.
- Ran **one updater preview** against a disposable `git archive` of main's data.
  Instrumented `requests.Session.send` in the temporary process; recorded only
  host/path/view/period, counts, duration, response size/status and allowlisted
  cache headers. No secrets, cookies, authenticated headers or raw authenticated
  bodies were saved. An 80-request ceiling and diagnostic-only connection/read
  timeouts bounded the preview. Production writes were disabled.
- Used a bounded 60-second pair of current-period reads, a smaller-view check and
  one conditional read; also checked ESPN's public page/application bundles,
  observed one anonymous page for 66 seconds, and read two deployed JSON headers.
  An initial four-read probe omitted the period selector and was discarded for
  live-stat conclusions; the corrected four-read probe used published period 11.
  These experiments ended; there is no running poller. Local files under
  `/private/tmp/brawl-live-audit` are diagnostic scratch, not production inputs.
- HTTP byte counts below are **decoded response bytes**, not compressed transfer
  sizes. Single samples are observations, not throughput benchmarks or rate-limit
  guarantees. Prices and platform documentation were checked on the research date.

## 2. Current architecture and measured performance

```text
main workflow (default branch; :17 every 3 hours Oct–Jun, daily Jul–Sep)
  checkout main canonical data + codex ingestion/export/frontend code
  install dependencies → backend safety tests
  nearLiveUpdater.py: ESPN → staged candidates → validation → canonical inputs
  generate_all.py: CSVs + currentLeague/seasonMetadata → all frontend JSON
  exporter tests + Node tests → compare deployed export fingerprint
  if changed: Vite build → commit canonical inputs on main → upload Pages artifact
  deploy Pages → browser's independent refresh/check
```

The canonical commit is after export/test/build validation. Main retains Dash;
codex supplies the React application and updater code. A normal relevant codex
push also builds Pages from main's canonical data. Both workflows share
`basketball-brawl-pages` with `cancel-in-progress: false`. The default pending
queue still coalesces/replaces older pending runs; it is not an unlimited FIFO.
See [GitHub concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

### One instrumented preview

At approximately 10:10 p.m. ET, the preview took **15.818 seconds**, made **32
HTTP requests**, spent **6.91 seconds inside HTTP sends**, and received **20.14 MB**
of decoded responses. All returned 200; there were no retries or 429s. Both daily
NBA/calendar caches were due, adding two calls. A comparable warm-cache run would
make **30 requests**, conditional on the same reconciliation window and no new or
stale profiles, seasonal fallbacks, rollover or failures.

`F` below means `https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons`.
`L(Y)` means `F/Y/segments/0/leagues/609694684`.

| Endpoint/view and purpose | Calls | HTTP seconds | Decoded MB |
|---|---:|---:|---:|
| L(2027), initial team/roster/matchup/settings/standings | 1 | 0.478 | 2.093 |
| L(2026), prior-season integrity/terminal checks, same views | 1 | 0.338 | 1.693 |
| F/Y/players, `players_wl`, current/prior bulk player identities | 2 | 0.320 | 0.508 |
| L(Y), `mDraftDetail`, construction and completion checks | 4 | 0.684 | 0.149 |
| L(2027), `mMatchupScore` + `mScoreboard`, seven recent daily periods plus previous matchup summary | 8 | 1.878 | 3.025 |
| L(2027), `mMatchup`, aggregate results | 1 | 0.181 | 0.391 |
| L(2027), settings/matchup score/team/roster, calendar/current snapshot | 1 | 0.384 | 1.981 |
| L(2027), `mTransactions2`, periods 0, 1 and recent seven | 9 | 1.565 | 0.399 |
| L(2027), bulk `kona_playercard`, projection history for rostered players | 1 | 0.485 | 8.835 |
| Public NBA scoreboard, yesterday/today status | 2 | 0.284 | 0.224 |
| F/2027, `proTeamSchedules_wl`, daily fixture refresh | 1 | 0.178 | 0.423 |
| Public fantasy scoreboard HTML, daily fantasy-calendar refresh | 1 | 0.136 | 0.415 |
| **Total** | **32** | **6.91** | **20.14** |

No per-player athlete-profile HTTP request was needed: all 367 cached profiles
were present/fresh. That updater refreshes profiles after seven days, may fetch
team references once per run, and may add requests for newcomers. Historical
three-point-attempt enrichment and short projection-history fallbacks can also
add season-wide bulk calls. Thus 30 is a measured-case warm estimate, not a fixed
upper bound. No synthetic player appearances or production data writes occurred.

### Production step timings

Actions API timestamps have one-second granularity. Zero below means below that
resolution, not literally free. Durations exclude scheduler delay unless stated.

| Stage | [Latest, 22:20 UTC](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41137446604) | [Manual, 20:37 UTC](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41124726130) | [Earlier, 18:00 UTC](https://github.com/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/runs/41103062835) |
|---|---:|---:|---:|
| Dependency installation | 15 s | 15 s | 10 s |
| Backend safety tests | 6 s | 6 s | 3 s |
| ESPN ingestion + candidate validation | 11 s | 21 s | 7 s |
| All frontend exports | 67 s | 66 s | 27 s |
| Exporter + frontend tests | 39 s | 39 s | 17 s |
| Fingerprint comparison | 1 s | <1 s | <1 s |
| Vite build | 1 s | <1 s | 1 s |
| Pages deployment action | 17 s | 29 s | 18 s |
| Run creation → completed | 3m10s | 7m36s | 8m24s |

The manual run waited approximately **4m13s before its update job started**. The
earlier run had approximately **4m41s between update-job completion and deploy-job
start**. Recent two runs spend about 106 seconds exporting/testing, versus 11–21
seconds ingesting. **Vite compilation is not the bottleneck.** Earlier run timings
also reflect earlier codex code, so these are not controlled equal-code trials.
The latest compressed Pages artifact was **7,328,234 bytes**.

Ten sampled scheduled runs from October 28–30 were created **11.5–163.1 minutes
after the nearest preceding configured `:17` three-hour slot**, with consecutive
scheduled-run creation gaps of **4.34–9.02 hours**. These offsets cannot identify
which missed slot an event belongs to or distinguish every scheduler cause;
creation time also excludes later job queues. They demonstrate that this repo's
observed delivery is substantially less regular than its cron expression.

[GitHub documents](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
a five-minute minimum schedule interval, default-branch execution, and possible
schedule delays/dropped jobs under load. A five-minute cron is not a latency SLA.

### Repetition and live changes

- Seven-day player/stat and transaction reconciliation deliberately revisits past
  periods for corrections. Keep this in the full pipeline; do not repeat it every
  five minutes merely to obtain today's scores.
- Three current-season draft reads and prior-season League construction repeat
  stable information. Preserve completion/terminal protections while considering
  reuse of already verified responses in a future optimization.
- The daily-period-6 response and previous-matchup summary use the same endpoint
  and period through different wrapper arguments. A raw-response cache could
  share network work while retaining different parsing semantics; reusing the
  parsed box object blindly would be incorrect.
- Bulk projection history is about **44% of decoded preview traffic**. It should
  not be fetched at live-score frequency. Profile enrichment and both calendars
  likewise belong on slower clocks. SDK requests mostly create separate HTTP
  sessions; connection reuse is another possible optimization.
- Every run regenerates historical/team/player/record-book exports and reruns
  broad exporter tests. Historical detail content hashes prevent unnecessary
  changes to finished payloads, but do not eliminate all regeneration work.
- During games, current daily player stats/credited contributions, matchup daily
  scores, game state/clock, current lineup/roster, and injury designations can
  change. Closed historical weeks/record books usually do not. A lineup change is
  not a historical scoring change; provisional live data must remain separate.
- Fingerprinting currently happens **after** all exports/tests. It avoids an
  unchanged build/deploy, not that earlier work. Whole-tree hashes include
  schedule/status/projection freshness timestamps; those can change even when
  scoring does not. A future live hash should separate meaningful payload
  changes from check/freshness times without hiding stale-data evidence.

### Browser detection and Pages JSON

Home and Scoreboard check every **300 seconds while visible** and on focus or
visibility restoration after roughly 60 seconds without a check. Home fetches a
97-byte `home-version.json` with `no-store`, then revisioned payloads; Scoreboard
revalidates its approximately **858 KB** manifest with `no-cache`, retains equal
snapshots, and retries details when appropriate. Matchup detail has a stable
season/week/match key, version-dependent fetches and React state updates: new data
does not require remounting or a browser reload. Version mismatches fail closed;
failed checks retain earlier data. Other older page loaders cache for the session;
this is not universal live refresh across every React page.

Observed deployed Home marker and scoreboard headers were `Cache-Control:
max-age=600`, ETag and Last-Modified. Existing browser directives request fresh
validation; these headers **do not prove every deployment incurs ten extra
minutes**, since CDN invalidation/revalidation may update earlier. However CDN
propagation/cache behavior is an unmeasured latency risk, and Pages offers no
application handler here to set a short custom JSON TTL.

JSON is fetched at runtime, so **changing data does not intrinsically require
recompiling React**. Today's workflows nevertheless copy all public assets into a
whole-site Pages artifact and redeploy. Pages has no configured independent
per-file JSON publishing API. Reusing built assets can remove compilation but
still requires a whole artifact deployment. External live JSON/API hosting is the
practical way to publish data without a Pages deployment. Do not expose ESPN
cookies to browsers or use frequent Git commits as a live message bus.

## 3. ESPN live capabilities and limitations

### Bounded observed HTTP capabilities

Using verified current scoring period **11**, at **10:13:44–10:14:44 p.m. ET**:

| Read | Result |
|---|---|
| `mMatchupScore` + `mScoreboard`, current period and matchup filter | 200, 440,277 bytes, 0.339 s; 162 roster entries, actual period stats, lineup slots and ACTIVE/DAY_TO_DAY/OUT injury labels |
| `mMatchupScore` only, same filter | 200, 158,486 bytes, 0.117 s; scores/current stats present, injury labels absent in this response |
| Combined view 60 seconds later | 200, 440,198 bytes, 0.146 s; player-stat digest and six teams' daily totals changed |
| Immediate conditional read with the new ETag | **304**, zero body, 0.102 s |

For example, one daily team total changed **148 → 150**, another **258 → 265**;
others decreased. Live data can be corrected, not just incremented. These samples
show changes within a minute; they do **not** establish a one-second source cadence
or measure event-on-court → ESPN API delay. `totalPoints` alone can represent
settled totals; a live adapter must verify current-period/roster applied totals
and reconcile period sums, rather than relabel a stale field as live.

ESPN's own common bundle also exposes `mMatchupScoreLite`. One read returned 200,
**15,320 bytes in 0.197 s**, with schedule/team IDs, period scores and totalPoints,
but no full rosters/injuries. Its live/settled-total semantics need a controlled
same-instant comparison before selecting it as the scoring authority. It is a
promising scoreboard-only optimization, not yet a verified replacement adapter.

The SDK's `box_scores(scoring_period=...)` already gets all fantasy teams in one
request. The `x-fantasy-filter` can restrict matchup periods; player-card filters
accept batches of stable IDs. No verified changed-since cursor or delta-player
feed was found. A batch for just selected players is not evidence that ESPN tells
us which players changed. Raw views can avoid heavy League construction.

Public NBA scoreboard supplies game states/clock/participants and was observed
with `max-age=8`. Bulk `players_wl` and full fixture responses had `max-age=300`;
fantasy league scoring responses had `must-revalidate` plus weak ETags. Current
code does not retain or send those ETags. The successful 304 probe supports a
future conditional cache, not guaranteed support on every view. Honor origin
cache lifetimes; no cache-busting query spam or attempts to bypass throttling.

### ESPN website transport

The published [basketball scoreboard bundle](https://cdn1.espn.net/kona/49f1381346a2-1.522/_next/1904a5b5-6da5-4c47-86b8-1c4b4638d358/page/basketball/league/scoreboard.js)
contains the actual scoreboard `getProGames`/`fastcastCB` path, a Fastcast
subscription client, WebSocket support/default mode, discovery configuration and
an HTTP long-poll fallback (client default polling interval 5 seconds). The
callback consumes game/player-stat updates. The initial league snapshot uses
HTTP views including mMatchupScore/mScoreboard. Thus there is source evidence of
**HTTP initialization plus Fastcast push**, not just speculative WebSocket strings
from analytics. No EventSource use was found in the two inspected bundles.

The bounded anonymous browser observation rendered an empty app body and saw only
geo/game-state HTTP requests, with no socket. It therefore did **not** confirm an
active authenticated subscription, effective message cadence, or fallback timing.
The client default is not a measured payload frequency. No Fastcast discovery,
tokens or topics were accessed. This internal protocol is not a supported public
API; adopting it would require separate permission/compatibility research,
reconnect/checkpoint/delta tests and a substantial maintenance commitment.

### Failure behavior and unknowns

The installed SDK is espn-api 0.41.0; its normal HTTP helpers have **no timeout**.
The preview imposed timeouts only inside its temporary instrumentation. The
updater retries selected connection/timeouts/unknown SDK and HTTP transient
failures three times with 1/2-second backoff. SDK non-200 statuses map to
ESPNUnknownError, so SDK retries do not provide precise HTTP-specific throttling
behavior. Some transaction retries repeat their whole bounded batch. NBA/calendar
clients have bounded timeouts/two attempts and persistent daily failure cooldowns;
athlete profiles have their own retries/seven-day cache. League/box caches are
process-local; NBA/calendar/projection history caches persist through main data.

No tested response returned 429, and no official quota, latency SLA or supported
third-party fantasy push API was found. The wrapper is community-maintained
[source](https://github.com/cwendt94/espn-api), not ESPN documentation. Treat these
JSON views and Fastcast as unofficial interfaces, even when used by ESPN itself.
Future implementation needs explicit timeouts, Retry-After when supplied,
exponential backoff/jitter, a circuit breaker, request/byte budgets, and stale
last-good snapshots. A successful small experiment does not establish safe
sustained 1–15-second polling.

## 4. Architectures, request budgets and latency

Estimates below assume one league, warm caches, no retries, two live upstream
reads per tick (combined fantasy snapshot + NBA status), and retained full updates.
They exclude optional profile/history discovery spikes. ESPN's own publication
lag is unknown and adds to every latency estimate.

| | A: full Actions pipeline every 5 min in game windows | B: full every 3h + lightweight 5-min snapshot | C: shared backend, ESPN every 1–15 s |
|---|---|---|---|
| ESPN requests/live hour | ~360 warm; naive 32×12 = 384 with due-refresh extras | **24–36 live + ~10 full = 34–46** (2–3 live reads/tick) | **480/h at 15 s**, 1,440/h at 5 s, **7,200/h at 1 s**, plus full reconciliation |
| Source bytes | ~230 MB decoded/h at measured warm response sizes | ~0.44 MB fantasy payload/tick + public scoreboard, before conditional savings | Highly cadence-dependent; central caching essential |
| Update-to-visible estimate without scheduler/CDN lag | ~3–13 min: 0–5 tick wait + ~3 processing + 0–5 browser check | External JSON: ~0–6 min plus short processing/cache, if browser checks ≤60 s; Pages-only still adds artifact deployment/queues | Target seconds to tens of seconds, plus ESPN lag; not proven |
| Runtime/hosting | Existing standard Actions + Pages | Actions pilot can remain best-effort; dependable cadence needs a small scheduled service and shared JSON store/API | Always-on process or appropriate durable scheduler; cache/state store, monitoring and API fan-out |
| Main weakness | Expensive repeated history work; queues can exceed interval | Correct live/canonical reconciliation and controlled publication | Unsupported upstream cadence/protocol, credentials, state/reconnect/rate-limit operations |
| Repository changes if later authorized | Schedule gate; workflow tests/caches; unchanged-export improvements; shorter browser cadence | Live adapter/schema/exporter, selective tests, data client and live-source fallback; keep full updater intact | B plus service lifecycle, subscriptions or API, per-client state/backpressure and monitoring |
| Complexity | Small code delta, poor freshness guarantees | Moderate; recommended balance | Highest; defer until demonstrated need |

The latency ranges are design estimates, not measured service guarantees. A/B
using GitHub cron can be much later, as this repo's actual timings demonstrate.
C's upstream budget must be shared across **all** viewers; never multiply ESPN
polls by number of browsers. Browser SSE/WebSockets could distribute server-side
snapshots without implying an ESPN push integration.

### Pages and Actions limits/costs

- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits):
  published site ≤1 GB, deployment timeout 10 minutes, soft bandwidth 100 GB/month.
  The soft 10-builds/hour limit **does not apply to custom Actions builds**, which
  this project uses. Twelve deployments/hour are not automatically forbidden,
  but remain inefficient and subject to rate limits/queues.
- This repository is public. [Standard public-repo hosted runners are free](https://docs.github.com/en/billing/concepts/product-billing/github-actions);
  larger runners and artifact/cache storage are separate considerations. Free
  compute does not make frequent whole-site builds operationally cheap.
- At six live hours/day and 30 days/month, A adds **2,160 full runs**. At about
  three job-minutes/run that is ~6,480 runner-minutes, plus deployment jobs and
  off-hours updates; ~15.8 GB compressed Pages artifact uploads at the measured
  7.33 MB each. This is upload traffic, not claimed concurrent artifact storage
  or Pages visitor bandwidth. History/commit churn and deployment failures add
  maintenance cost. A private repo would require a separate plan-specific bill.
- B: an experimental cache-controlled endpoint may fit a free service tier. A
  conservative small deployment budget is **$5–15/month**, including possible
  state/storage; this is an estimate, not a quote. [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
  provides a concrete $5 paid base, 10M included requests/month and CPU-based
  overages; the free tier has 100k requests/day and 10ms CPU/invocation. A thin
  adapter may fit; running this full pandas updater there is not the proposal.
- C needs a continuously scheduled collector or durable timer, not a function
  sleeping for hours. At 15-second upstream cadence for six hours/day, the assumed
  two-call collector makes ~86,400 ESPN requests/month; at one second ~1.30M.
  One hundred continuously visible browsers checking every 15 seconds for those
  hours make ~4.32M backend reads/month, versus ~64,800 at five-minute checks.
  CPU/state/stream duration/egress can dominate; validate the selected platform's
  billing before claiming a free tier. [Workers Cron](https://developers.cloudflare.com/workers/configuration/cron-triggers/) alone is minute-granularity,
  so subminute work needs a different scheduler/process, not extra cron lines.

## 5. Schedule-aware windows and safe publication

Use canonical `nbaSchedules[season]` stable IDs and UTC timestamps, with the
verified fantasy calendar for scoring-period joins. Evaluate the union of NBA
game windows, not an assumed evening or fixed fantasy seven-day week.

| State | Proposed upstream cadence |
|---|---|
| Off-hours/no imminent games | Full reconciliation every 3 hours; daily full schedule discovery |
| Pregame, first tipoff 30–120 minutes away | Live roster/injury/status snapshot every 15 minutes |
| Final 30 minutes before first confirmed tipoff | Every 5 minutes |
| Any game in progress, suspended/uncertain start, or pending final confirmation | Every 5 minutes |
| After all games final | Every 5 minutes for an initial 30-minute stabilization window; then 15 minutes for up to two hours; full updater continues catching later corrections |

Stability means unchanged meaningful game/player/fantasy totals for several
checks **and** all expected games finalized, not a clock-based assumption.
Thirty minutes/two hours are proposed initial operational settings, not guarantees
about ESPN finality. Overtime continues the live state. Delayed games remain
watched; re-evaluate actual status instead of ending at tipoff + fixed duration.
Use both league-local date and preceding date near midnight; do not stop a late
West Coast game at midnight ET. Early/weekend/international games use their
published timestamp. Recompute next wake-up when fixtures change.

Cup TBD obligations have no invented date. In a stale/unknown schedule, poll a
small public status view conservatively (e.g. every 15 minutes), retain full
calendar discovery and escalate to five minutes on discovered activity. An
empty/failed response cannot establish no games. Current 24-hour fixture discovery
can miss same-day changes; a later implementation should permit a bounded
pregame/status reconciliation on actual schedule contradictions, not refetch the
entire schedule every tick. Unlocalized uncertainty must not silently disable
updates. Include a broad status-discovery fallback so unknown early games are
not missed just because the cache has no fixture window.

With Actions, a lightweight five-minute gate must run before dependency installs,
full ingestion and exports; it reads persisted due/window state and exits when
not due. It is still subject to cron delay. Do not keep many sleeping runners or
build a chain of self-dispatching workflows to imitate a real-time service.

Keep a single writer per dataset. Preserve the existing full canonical writer
and serialization; use a separate live snapshot namespace/writer and ordered
version publication so full and live pipelines cannot overwrite each other.
Compute deterministic content hashes, skip unchanged publication, and publish a
small freshness marker separately. Never cancel a publishing transaction halfway
through; drop/coalesce stale pending live work. If retaining whole Pages artifacts,
serialize them with all normal Pages deployments and reject stale snapshots.

A live envelope should include schema version, season, matchup/scoring period,
source-observed/checked/published times, roster revision, canonical baseline
version and stable player/team/game IDs. Publish immutable data then an atomic
version pointer. Validate before promotion; retain last good data on failure.
Use a short controlled TTL/conditional validation and explicit stale state. The
browser applies newer compatible live fields in place, never double-adds a
current period already present in canonical totals, and discards an overlay when
the canonical reconciliation incorporates it. No historical CSV mutation on the
fast path. Contract tests must cover corrections that decrease totals, drops and
trades, locked bench/IR slots, rollover, version skew and upstream failures.

## 6. Staged plan and unresolved decisions

1. **Next, smallest practical step:** implement the unpublished adapter/comparison
   test described above, using at most two bulk reads and no new schedule. Verify
   the scoring-period selector, actual contribution/slot rules, injury provenance
   and a deterministic live hash. Treat mMatchupScoreLite as optional research
   until its live semantics agree with the verified combined view.
2. Create a separate shared live JSON contract/export, retain all existing
   safeguards, and test browser merge/fallback without remounting. Add explicit
   timeouts/conditional reads and record request counts/age/error metrics. Keep
   fixture/calendar/profile/history refresh on their slower clocks.
3. Choose publication: a Pages-only pilot is lower infrastructure effort but
   explicitly best-effort. For a meaningful five-minute freshness target, approve
   a small cache-controlled external data service; Pages still hosts the UI.
   Implement the fixture-aware gate and monitor lateness, 304/429/error rates and
   no-change ratio during a limited game-night trial before broad activation.
4. Only after demonstrated source freshness and demand, evaluate a 15–30-second
   collector/shared fan-out. One-second upstream requests and internal Fastcast
   are deferred. Test cold starts, repeated corrections, reconnects and source
   throttling before setting a near-real-time target.

Still unknown: ESPN event-to-API latency and sustainable request quota; effective
Fastcast authenticated delivery cadence; whether Lite supplies exactly the same
live totals; production CDN invalidation duration; future chosen hosting tier and
actual viewer concurrency. None is assumed solved by this document. No workflow
run was dispatched and no production service or schedule was changed for this
investigation. Only this research document is intended for commit/push to codex.
