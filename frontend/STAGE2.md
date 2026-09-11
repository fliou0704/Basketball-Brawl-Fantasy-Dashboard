# Stage 2: homepage

## Scope and commands

Everything lives under `frontend/` except the dedicated Pages workflow. Dash,
Render, production CSVs, and updater behavior are untouched. The Stage 1 exporter
is retained for compatibility; the homepage uses the new orchestration command.

From the repository root, with a directory containing current copies of the three
production CSVs (the CI checkout is `frontend/.league-source/data`):

```sh
python3 frontend/scripts/build_homepage.py --source-dir /tmp/brawl-stage2-data
HOMEPAGE_TEST_SOURCE=/tmp/brawl-stage2-data STANDINGS_TEST_SOURCE=/tmp/brawl-stage2-data/basketballBrawlLeagueData.csv python3 -m unittest discover -s frontend/scripts -p 'test_*.py' -v
python3 -m unittest discover -s tests -v
cd frontend
npm ci
npm run build
npm run preview
```

Without `--source-dir`, the build uses the local root CSVs, which may be older than
production on `main`. It is entirely offline and uses only the Python standard
library. The normal preview uses the checked-in generated JSON.

## JSON contract

- `public/data/homepage.json`: schema version, timezone, season calendars, dated
  state lookup, and offseason transitions.
- `public/data/{2023,2024,2025,2026}/standings.json`: regular-season snapshots by week.
- Each season also has `daily-recap.json`, `weekly-recap.json`, `playoffs.json`,
  `season-leaders.json`, and `history.json`. Each has version, season, and `data`.
- `public/data/standings.json`: retained top-level standings contract, now final
  regular-season rankings and stats together (rather than mixed playoff ranks).
- `public/data/data-quality.json`: daily active-roster reconciliation audit.
- `source/season-metadata.json`: allowlisted, non-secret ESPN build input; never a
  raw response. Contains scoring-period totals, matchup calendars, roster slots,
  and scoring weights for each archived season. Not copied to the public directory.

React loads only the section datasets needed for the selected season/state. All
statistics, lineup optimization, sorting, bracket winners, rank chart geometry,
and date state decisions are precomputed by Python. The frontend only chooses a
precomputed date/state and renders it. There are no new runtime dependencies.

## Season states and date preview

`homepage_state.select_state(date, seasons)` is the centralized pure selector.
It consumes the build's normalized calendars and available completed-day/week
lists. A fantasy season's year denotes its ending year (e.g. 2026 starts in 2025).
The browser defaults to today's date in America/New_York, updating the selection
when that calendar date changes. No visible debug controls are included.

Append `?date=YYYY-MM-DD` to the homepage URL, for example:

| Scenario | Date |
| --- | --- |
| Preseason / previous completed season | 2025-09-10 |
| First scoring day; previous-season recap | 2025-10-21 |
| Early daily recap, no prior weekly recap | 2025-10-22 |
| First day of week 2; weekly recap first | 2025-10-27 |
| Normal midseason day; daily recap first | 2026-01-15 |
| First playoff round | 2026-03-16 |
| Semifinals | 2026-03-23 |
| Championship week | 2026-03-30 |
| Final scoring day | 2026-04-05 |
| Immediately after championship | 2026-04-06 |

Only scoring days strictly before the requested date are eligible for recaps.
An NBA off-day reuses the most recent completed scoring day. Weekly recaps require
a completed week in the current season. Day one falls back to the most recently
completed season, with no empty recap cards. A season is complete only when its
terminal ESPN scoring day and final league week are present in the source data.

Calendar dates come from ESPN matchup scoring-period membership and the verified
CSV date-to-period anchor. ESPN omits some no-game period keys. For these gaps,
the calendar infers the normal week-start weekday from the season's observed
starts, retaining the real season opener and ESPN terminal date. No fixed Monday,
season dates, week counts, or playoff start dates are used by the selector.
This inference is tested with a Wednesday-start calendar too. A nonstandard
midseason change to the league's weekly cadence would need additional metadata.

Historical previews hide future playoff results and opponent assignments, but
are presentations of the final archive, not replay of intraday roster changes or
what an earlier data ingest actually knew. Historical team names/logos reflect
the season archive's available identities.

## Scoring investigation and limits

The daily CSV includes `Player Slot`. `BE` and `IR` must not count toward team
scores; active slots come from each season's ESPN roster settings. Comparing
active-player sums with ESPN's `pointsByScoringPeriod` found 5 mismatched team-days
in 2023, 1 in 2024, none in 2025, and 1 in 2026 (6,177 comparisons total). Therefore,
daily team winners use ESPN's authoritative per-scoring-period scores. Partial
team slates do not produce a team winner. Tied leaders are all included.

Individual daily leaders use rostered player FPTS, including bench/inactive
players, with duplicate player-day rows resolved deterministically by highest
recorded performance. The existing CSV's basketball-stat columns are applied
fantasy scoring contributions. They are converted back using ESPN's season
scoring weights: e.g. AST / 2, TO / -2, FGM / 2, FGA / -1 for the current rules.
The raw counts are precomputed in JSON, never calculated by React.

**3PA is missing.** The updater saves scoring breakdown fields, and 3PA has no
scoring weight or CSV column. Library inspection showed how raw stat blocks could
be accessed; a bounded daily endpoint check did not return usable daily roster
entries. No unsupported historical 3PA values or zero placeholders were invented.
The UI shows `3PM/—` and explains the missing field. A future isolated raw-stat
backfill would be needed for a complete shooting line. No production schema was
changed in this stage.

**The scoreboard is not live.** ESPN exposes reliable scoring-period team totals;
we show the active fantasy week's cumulative scores **through the previous
completed archived day**, explicitly dated. On the first day of a new week, an
old-week scoreboard is not shown as current. Intraday totals and completion status
would require scheduled authenticated refreshes; GitHub Pages alone is not a
live data feed. A historical date cannot reconstruct intraday scores.

Refresh the allowlisted input explicitly when league data advances:

```sh
python3 frontend/scripts/refresh_season_metadata.py --source-dir /tmp/brawl-stage2-data
```

This optional live command needs the root Python dependencies and existing
`require_espn_credentials()` helper. It never saves raw responses or credentials.
Normal builds/tests do not call ESPN. New seasons absent from metadata fail the
build clearly, rather than inventing dates. Until a future season's metadata and
CSV data are added, the public homepage remains the latest completed-season recap.
Pages is redeployed on relevant `codex` pushes, not automatically when `main`
changes. No new scheduler or external service was introduced.

## Weekly lineup and playoff logic

Team of the Week maximizes total weekly player FPTS across the actual ESPN slots:
PG, SG, SF, PF, C, G, F, and three UT slots. A slot-mask dynamic program prevents
reusing players. Eligibility comes from `Position`, `Position2`, and `Position3`
in the existing weekly CSV; G accepts PG/SG, F accepts SF/PF, UT accepts any base
position. This is deterministic given available position data, which may omit
some historical alternate ESPN eligibility. Weekly points include a player's
rostered bench production, so this is a best-performance lineup, not a score
actually achieved by a manager. The highest scoring selected player gets MVP gold.

Playoff matchups use Team IDs and actual `Type == Playoffs` rows, reciprocal rows
are deduplicated, and `Bye` rows advance to the semifinals. Consolation matches
are excluded. Previous completed rounds show final scores and advancing teams;
active rounds hide final scores; future rounds hide opponents/results. Completed
championship winners get a restrained gold treatment. Tied scores are displayed
without guessing an advance/tiebreaker. Playoff Team of the Week includes only
players whose teams actually played championship-bracket games that week;
first-round byes and consolation teams are excluded.

Offseason order is bracket → final regular-season standings → top ten players →
historical charts. Season player totals cover rostered weekly performances during
the fantasy season, not every NBA player or the entire NBA schedule. Duplicate
player-week records are counted once (highest recorded total, then lowest Team ID),
and transferred players list the owning teams found in the archive.

Around the League uses reliable completed regular-week data: biggest rank rise,
highest-scoring losing team, and longest win streak. It follows the main recaps
and standings. Activity data was inspected, but waiver impact / injury claims
were not implemented because reliable performance attribution is not available.

Charts are plain SVG/CSS without Plotly, chart libraries, zoom/pan handlers, or
wheel/touch interception. Rank paths and bar widths are prepared in Python. The
header menu implements Home only; future destinations are disabled text, with no
broken links or migrated Dash routes.

## Files and validation

Created: `scripts/homepage_state.py`, `scripts/build_homepage.py`,
`scripts/refresh_season_metadata.py`, `scripts/test_homepage.py`,
`source/season-metadata.json`, `src/App.jsx`, `src/homepage.css`,
`src/components/{Standings,Recaps,Playoffs,SeasonHistory}.jsx`, the JSON files above,
and this document. Additional local logos are copied for historical team names.
Changed: `src/main.jsx`, `index.html`, `README.md`, generated top-level standings,
and `.github/workflows/frontend-pages.yml`. Existing Stage 1 scripts/styles remain.

Validation includes the 56 existing Python tests and 29 frontend Python tests
(24 new homepage tests + 5 existing exporter tests), Vite production build, and
browser inspection at desktop, 390px and 320px. Tests cover all ten requested date
scenarios, no-game boundaries, missing recaps, future-result hiding, ties,
lineup eligibility/uniqueness, playoff participation, authoritative team scores,
and every generated state's JSON references.
