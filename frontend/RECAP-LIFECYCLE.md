# Home and Scoreboard recap lifecycle

Home uses the published `currentLeague.json` season, matchup week, and ESPN
scoring period. `generate_home_current.py` exports the sorted canonical
`scoringPeriodMatchupMap.csv` sequence for that week as `state.weekScoringPeriods`.
`showHomeRecap` admits only the first two entries of that sequence. It never uses
the visitor's date, a 48-hour timer, observed player-game dates, Monday boundaries,
or a fixed week length. A stale snapshot retains its published period until a
newer deployment is detected by the existing five-minute version check.

Only week N−1 is eligible in week N. It must appear in the existing Home
exporter's completed weeks and have valid weekly recap data (matching week,
end date, leaders, matchups, and the shared component's expected arrays).
Week 1, an unavailable current period, a missing recap, or an incomplete previous
week produces no Home recap. Older completed weeks never substitute. No current
player-game rows are required. The canonical mapping is used as published;
missing future entries or calendar boundaries are never extrapolated.

This replaces the former `verifiedWeekStart: null` gate, which prevented every
production Home recap from appearing. Verified calendar boundaries are no longer
needed for this scoring-period-based rule. Scoreboard remains the permanent
home for completed recaps: it embeds existing seasonal exports only for final
weeks with at least one final matchup. Its exporter and route are unchanged.

## Current-week scoring and Home order

`scoringStatus` uses only finite ESPN matchup contributions whose periods map to
the current week and do not exceed the published period. A known nonzero value
means `started`, including partial updates. `zero` requires all current league
teams exactly once and explicit zero values for every published mapped period
of the current week. Missing assignments, absent values, or invalid values yield
`unavailable`, unless a known nonzero contribution already establishes scoring.
Previous-week points and player rows never establish this signal. Available
score totals retain the existing calculation; absent totals display an em dash.

- **Confirmed zero:** eligible previous weekly recap → available daily recap →
  current scoreboard → standings. Current-week performances are suppressed.
- **Started:** current scoreboard → available current-week performances → daily
  recap → eligible previous weekly recap → standings.
- **Unavailable:** scoreboard-first order, displaying available performances
  only; unknown coverage is never presented as a confirmed zero week.

Playoffs retain their bracket after the recap/scoreboard content and before
standings. Empty sections render nothing. Offseason content and historical
snapshot selection retain their existing behavior. The shared daily heading
formats the recap's date as `October 25, 2026 Recap`, using New York and a
date-only value anchored at noon UTC. The current scoreboard heading is
`2027 Week 2 Scoreboard`, with the existing publication timestamp retained.
Scores, weekly recap calculations, 3PA/stat breakdowns, player identities, and
all ingestion/persistence code are unchanged.

## Validation

Use the same production source selection as the existing Pages workflow. Export
into a temporary directory when local public data contains unrelated edits.

- `python frontend/scripts/generate_all.py --source-dir SOURCE --output-dir OUTPUT`
- `python -m unittest discover -s frontend/scripts -p 'test_*.py' -v`
- `npm --prefix frontend test`
- `npm --prefix frontend run build`
- With Vite running: `python frontend/tests/recap_browser.py`

Exporter tests use `FRONTEND_TEST_OUTPUT`, `BRAWL_REFERENCE_DIR`, and the existing
`*_TEST_SOURCE` variables to select temporary exports and their canonical source.
The optional browser check accepts `BRAWL_URL`, `BRAWL_DATA_DIR`, and
`CHROMIUM_PATH`; it requires Playwright. It checks deterministic period windows,
both score-based orders, stale clocks, the permanent Scoreboard recap, and
desktop/390px/320px overflow. No updater or deployment workflow changes are
required.
