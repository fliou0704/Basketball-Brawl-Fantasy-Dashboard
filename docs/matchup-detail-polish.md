# Matchup sorting and refresh diagnosis

Starting codex commit: 33462ad4f85bc8d31284df57af14890d6aa63b82. Unrelated local changes were preserved.

## Reproduced cause

Production-page browser instrumentation counted one document request and zero hash changes. With a selected date and scrollY=600, dispatching a focus event fetched scoreboard.json and matchups/2027/2.json, removed the selected dropdown's ancestor once, reset the date to Summary, and left scrollY=0. Invoking the registered 300,000ms polling callback caused the same reset. It was React subtree removal, not a full browser reload, route change or GitHub Pages cache action.

The manifest refresh always replaced state with a fresh object. MatchupDetail depended on that object and immediately cleared its detail state, unmounting ScoringBreakdown. Its local selection then reinitialized on every detail response. Focus events were unthrottled, so switching windows could reproduce the problem much more often than the five-minute poll.

## Focused fix

- Summary independently sorts each team's scoring contributors by descending credited matchup FPTS, with player ID as the stable tie-breaker. Bench/IR remains a separate excluded group. Rows are paired by rank, not by position.
- Date mode uses only the actual recorded slot, ordered by the exported league slot order, with BE/IR afterward. Duplicate-slot players use stable player-ID order; position eligibility never substitutes for assignment.
- Unchanged manifests retain their object identity. Manifest requests cannot overlap, rapid focus events are throttled to one check per minute, hidden-tab polls are skipped, and returning to a visible tab checks freshness. The existing five-minute live-score cadence remains.
- Detail loading uses a stable content/version key. An unchanged historical detail version does not refetch just because the global live timestamp changed. Background loads retain the complete previous score/detail pair until the replacement succeeds. The breakdown stays mounted, preserving its selection and DOM.
- A subsequent manifest check retries failed detail loads even when manifest content is unchanged. Failed manifest/detail checks preserve loaded data; error notices are placed below existing detail content so they do not insert rows above the current viewport.

## Verification

66 frontend tests and 146 offline backend tests pass; Vite production build passes. Browser tests against the production build at 1280px, 390px and 320px verify independent Summary ranking, recorded daily positions, current/historical/extended/playoff/future views, direct links and existing H2H behavior. Controlled idle, focus bursts, normal polls, delayed score changes, failed manifest/details and recovery preserve the exact dropdown DOM, chosen date, scroll position and single document navigation, while real score updates appear. No historical backfill, updater changes, scoring changes or future-lineup ingestion were added.

Future-lineup findings are recorded separately in [future-lineup-research.md](future-lineup-research.md).
