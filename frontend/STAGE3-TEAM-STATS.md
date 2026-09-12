# Stage 3: Team Stats

Only Team Stats is migrated. Dash, Render, updater behavior, and production CSVs
are unchanged. Other menu destinations retain their existing disabled state.

## Source of truth and parity

`basketballBrawlTeamStats.py` supplies the definitions. The exporter runs on copies
of four CSV inputs, without importing Dash or its mutable `dataStore` module:
league, weekly player, daily player, and activity data.

Preserved behavior:

- Team selection order and display names use the latest league season; season
  options are Summary followed by descending years. No team is initially selected.
- Rankings retain FG%, FT%, 3PM, REB, AST/TO, STL, BLK, PTS, FPTS, PPM in that order.
  The same weekly scoring-contribution conversions are applied. All recorded weeks
  count, including postseason; the old page's regular-season-only TODO is not implemented.
- Ranks are descending with `method='min'` for ties. Values retain Dash's precision:
  PPM three decimals; FG%, FT%, AST/TO two; other totals zero.
- Team PPM is daily FPTS divided by daily minutes, with the same missing-value rule.
- Season rosters preserve the grouped weekly FPTS order, name-based daily PPM join,
  most recent season activity by player ID, KEEPER fallback, original date strings,
  and contribution percentage. No browser calculations or user sorting were added.
- Summary records exclude consolation and retain separate overall, regular-season,
  and playoff records and winning percentages. Summary roster FPTS spans all years;
  the latest non-KEEPER action is used exactly as in Dash (even when it is a drop).
  DROPPED, TRADED, and NOT KEPT rows retain the inactive color distinction.
- Dash placement images are rendered as numeric ranks; compact mobile roster rows
  show every column with its label. These are presentation changes only.

No statistical behavior is intentionally changed. Existing quirks, including
name-based PPM matching and treating an unrecognized/missing summary action as
active, remain. The data is a build-time snapshot, not a live callback query.

## JSON and routing

`public/data/team-stats.json` has `schemaVersion`, descending `years`, and ordered
`teams` (teamId, teamName, local logo, color).

`public/data/team-stats/{teamId}.json` has `schemaVersion`, `team`, `summary`, and
`seasons` keyed by year. Summary contains formatted `records` and an ordered
`roster` with playerId, name, fpts, action, date, inactive. Each season contains
ordered `rankings` (label, nullable rank, formatted value) and ordered roster rows
(playerId, name, fpts, ppm, action, date, contribution). A missing team season is
null, rendered with the same no-data message as Dash. All output is strict JSON.
Only the selected team's file is fetched.

The route is `#/team-stats`, relative to the existing Vite project base. It works
on direct visits and reloads without a GitHub Pages rewrite or new router package.
The shared header links Home and Team Stats; the remaining destinations are unchanged.

## Build and validation

Requires Python 3.11+ for the pinned build dependencies. From the repository root:

```sh
python -m pip install -r frontend/requirements-build.txt
python frontend/scripts/generate_team_stats.py --source-dir /path/to/current/data
TEAM_STATS_TEST_SOURCE=/path/to/current/data HOMEPAGE_TEST_SOURCE=/path/to/current/data STANDINGS_TEST_SOURCE=/path/to/current/data/basketballBrawlLeagueData.csv python -m unittest discover -s frontend/scripts -p 'test_*.py' -v
python -m unittest discover -s tests -v
cd frontend
npm run build
npm run preview
```

The normal frontend preview uses committed JSON. The dedicated Pages workflow
reads activity data alongside its existing temporary main CSV checkout, installs
pinned pandas/NumPy build dependencies, generates homepage and Team Stats JSON,
runs the frontend tests, and builds/deploys codex. No updater is invoked.

Six new tests execute the actual Dash callback AST with inert HTML components,
using fresh, isolated source data. They compare all ten teams in all four seasons
(2023–2026): every ranking label/value/rank, every roster value and row order, all
summary records/rosters/status colors, and selector ordering. Additional edge checks
cover tied ranks, missing PPM, and missing team seasons. These tests are offline;
Dash does not need to be installed. Existing homepage tests remain in the suite.

Validation: 35 frontend tests (29 existing + 6 new), 56 production Python tests,
Vite build, desktop/390px/320px browser inspection, season/team switching, Summary,
and header navigation. Browser values were checked against the parity-tested JSON.

Files added: `scripts/generate_team_stats.py`, `scripts/test_team_stats.py`,
`requirements-build.txt`, `src/TeamStats.jsx`, `src/team-stats.css`, this document,
and the Team Stats JSON manifest plus ten team files.
Files changed: `src/App.jsx`, `src/main.jsx`, `README.md`, and the dedicated Pages workflow.
