# Live data and automation audit — October 20, 2026

## Findings and actual update

- `main` owns canonical production inputs and Dash/Render. `codex` owns React,
  exporters, and normal frontend push deployments. Branches are not identical.
- The last four scheduled updates failed before export/deployment. The October 14
  job log explicitly reports missing GitHub Secrets `ESPN_S2` and `SWID`. Local
  credentials work. No secret values or settings were inspected or changed.
- The deployed Pages manifest initially reported season 2026; its latest successful
  deployment before this task was September 23. A successful old scheduled job
  could deploy Pages, but it lacked metadata discovery, calendar rollover, bounded
  corrections, common concurrency, and export-based no-change detection.
- The `codex` league/matchup snapshots were behind canonical `main`: 70 league
  rows and 808 matchup-player rows were missing locally. These were restored from
  `main`, without recomputing them or merging application code.
- Live ESPN: fantasy season **2027** (2026–27), matchup week **1**, scoring period
  **1**, terminal fantasy period **167**. No official 2027 matchup is complete.
  Historical 2026 is complete through week 23 / scoring period 167. The maximum
  scoring period across all seasons (175) is not the 2026 or 2027 terminal period.
  There are no missing completed league weeks. Nine 2026 daily period IDs have no
  saved player rows; none has a nonzero saved official team-day score. These were
  not filled with synthetic rows or described as verified missing games.
- One completed staged update took **32.4 seconds**. It added eight 2027 daily
  rows (including bench records), 203 Activity rows, ten public athlete profiles,
  and refreshed 290 cached active profiles. All profile lookups succeeded.
- The 2026 final seven scoring periods and final matchup were checked against ESPN:
  no saved player stats, fantasy scores, or official outcomes required correction.
- Re-running legacy playoff ranking logic initially changed six 2026 week-23
  placement ranks despite identical official scores/outcomes. The new guard
  preserves those placements; none of those changes were accepted. Saved
  historical eligibility and team identity fields are likewise retained.
- The new snapshot exposes all ten current teams and 151 roster entries, including
  current eligibility, independently of historical daily ownership. Player careers
  and logs use saved lineup/played-game semantics. Current Team metrics derive
  from canonical daily contributions; standings/outcomes remain official ESPN data.
- Home retains its existing completed-day recap behavior, including the prior
  completed season on opening day. Historical H2H uses completed official matchups.

## Correction and transaction policy

`nearLiveUpdater.py` stages all candidates, validates them, then atomically replaces
each changed canonical file. A failure before promotion leaves the original inputs
unchanged. Workflow commits happen only after export/tests/build succeed.

- Refresh the current period plus the preceding six scoring periods, capped by
  ESPN `finalScoringPeriod`. Catch up missing periods after an outage.
- During rollover, also reconcile the prior season's final seven periods once,
  before a newer daily season is persisted. Older seasons then freeze. After a
  terminal period has been available for seven days, routine offseason polling
  does not keep rewriting its statistics.
- Refresh completed official league/player-matchup weeks touched by those daily
  partitions. Recalculate cumulative fields only through the explicitly refreshed
  tail, using ESPN official scores and winners, never outcomes inferred from daily
  totals. Preserve historical eligibility, identities, and unchanged playoff places.
- Allow validated inserts, changes, and deletions inside authorized partitions.
  Reject duplicate keys, schema changes, or out-of-partition records. No-change
  logical results preserve the original order and file.
- First Activity import fetches the current season only. Later runs fetch recent
  seven-period overlap plus draft anchors 0/1, keeping older activity and manual
  trade supplements. It includes post-final-period transactions. A season with an
  incomplete draft is skipped safely, rather than promoting a partial draft.
- Five finalized 2027 trade IDs lack supplemental player movements. Existing trade
  policy deliberately does not infer player trades from acceptance records. Their
  histories still require supplement review; current roster membership is accurate
  independently. This remains a manual limitation, not a silently repaired history.
- Public metadata discovers both canonical-record IDs and roster-only newcomers.
  New IDs are fetched immediately; cached active profiles refresh weekly. Failed
  public profiles retain existing values, report unresolved IDs, and retry later.
- Calendar metadata is canonical in `data/seasonMetadata.json`; period-to-week
  mappings use observed ESPN boundaries. Future matchup dates are not invented.

## Proposed cadence and cost

Prepared schedule: **minute 17 every three hours October–June**, and **13:17 UTC
daily July–September**. Runs may be delayed by GitHub. This is eight polls/day
during the season and reduced offseason polling; no external scheduler is needed.

The repository is public, so standard GitHub-hosted Actions runners do not consume
a private-repository minute allowance. Eight builds/day are far below Pages limits.
Routine requests are estimated at roughly **30–45 ESPN requests/run** (about
240–360/day), including seven daily boxes, bounded transactions, current settings,
and cached league setup. Missing-period catchup increases requests proportionally.
A weekly profile refresh adds roughly 300–330 public profile/team requests once,
not every run. These are implementation estimates, not an ESPN rate-limit guarantee.
The completed first update took 32.4s; allow roughly 1–3 minutes including offline
exports, tests, dependency setup, and build. No-change runs skip Vite/deployment.

References: [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
[Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits),
[scheduled Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Workflow ownership and activation

The proposed `main` change is **only `.github/workflows/update-league-data.yml`**
from this `codex` change. It explicitly checks out canonical `main` inputs and the
`codex` updater/exporter implementation in `site/`. Dash source/dependencies remain
on `main`; no frontend branch merge or updater-source transfer is necessary.

1. Restore/configure repository Actions Secrets `ESPN_S2` and `SWID` locally in
   GitHub settings. Values must never be supplied in chat or committed.
2. Approve transferring that one workflow file to `main` to activate the cadence.
   This task does not push or merge to `main`.
3. The workflow runs offline safety tests, staged live updates, exporters, export
   tests, and React contracts. It compares the resulting JSON fingerprint against
   the marker on the actual deployed site, builds only changed exports, commits
   validated source inputs to `main`, uploads the artifact, and deploys Pages.
4. Both Pages paths share `basketball-brawl-pages` concurrency with cancellation
   disabled. Workflow-token data commits cannot trigger a deployment loop. An
   unsuccessful deployment leaves the published fingerprint unchanged, so the
   next run can recover even when canonical inputs have no further changes.
5. Normal relevant `codex` pushes continue to build/deploy Pages. Until the new
   canonical metadata exists on `main`, that workflow uses the complete validated
   `codex` snapshot as a temporary bridge. Once activated, all sources come from
   `main`. Generated JSON is an artifact, not a second set of automated Git commits.

Remaining limitations: manual trade-supplement review; unknown ESPN corrections
older than the bounded window require an explicit audited repair; an already-open
browser tab needs a reload to fetch a new static snapshot. Historical source audit
warnings (five 2023, one 2024, one 2026 daily team-score mismatches, missing raw 3PA)
were retained and were not repaired by rewriting old data.

## Verification

84 backend/safety tests, 74 frontend exporter/freshness tests, and 15 React contract
tests passed across the final full suites and focused freshness check. Vite built
successfully. YAML parsed and `git diff --check` passed. The ESPN client version is
pinned to the locally validated 0.41.0 for reproducible scheduled runs. User changes
to Dash files and existing generated frontend snapshots were left unstaged.
