# Multi-feature sprint

The sprint changes frontend components and read-only exporters. No canonical CSV,
updater, scheduler, live scoring, Supabase, deployment workflow, or credentials were
changed. Pre-existing local edits to generated snapshots were preserved.

## Preview without overwriting local snapshots

From the repository root (use the Python environment with pandas installed):

```sh
npm --prefix frontend ci
npm --prefix frontend run build -- --outDir /private/tmp/brawl-sprint-preview
python frontend/scripts/generate_all.py --output-dir /private/tmp/brawl-sprint-preview/data
npm --prefix frontend run preview -- --outDir /private/tmp/brawl-sprint-preview --host 127.0.0.1 --port 4176
```

Open http://127.0.0.1:4176/Basketball-Brawl-Fantasy-Dashboard/ .
Check Home, #/standings, #/record-book (Year: All-Time), and #/players.
Nothing is deployed by these commands. The regular `generate_all.py` pipeline
also generates all new fields automatically for future authorized deployments.

## Data limitations

100+ FPTS records use the existing saved NBA game Date and FPTS unchanged.
PTS, REB, AST, STL, BLK, FGM, FGA, 3PM and TO are recovered from that same row
using that season's scoring weights, via the existing `raw_stats` helper.
3PA is absent from the current source CSV. It is shown as —, including in 3PM/—;
if an optional raw 3PA column becomes available the exporter consumes it.
NBA opponents are not saved; YouTube queries omit them rather than substituting
fantasy opponents. No YouTube API or game lookup request is used.

The daily CSV includes fantasy-rostered players and omits their unrostered games.
Player metadata is also fantasy-history scoped. Neither establishes NBA-wide
season totals. Top 150 therefore displays a clear unavailable state for these
snapshots. The interface, ranking engine and exporter contract are implemented;
automatic collection of a verified complete NBA player pool remains blocked on
a new data-source decision. No misleading roster-only ranking is presented.
Current roster membership is taken only from currentLeague.json for its own season.
Historical comparison is disabled; absent ownership is never labeled Free Agent.

## Optional complete-pool input contract

`generate_top150.py` accepts `data/nbaPlayerPool.json` if a future data collection
step supplies it. It never makes external requests or edits the source. Format:

```json
{"seasons":{"2027":{
  "complete":true,
  "scope":"NBA regular season",
  "source":"source identification and snapshot timestamp",
  "scoringWeights":{"PTS":1},
  "maxTeamGames":20,
  "players":[{"playerId":1,"name":"Example","nbaTeam":"NBA team","gp":10,"fpts":250}]
}}}
```

This abbreviated example is not a valid population: at least 150 unique player
IDs and **all eligible NBA players** must be supplied. `scoringWeights` must equal
the complete selected season configuration, not the abbreviated example above.
FPTS must cover every actual regular-season NBA game using those scoring rules,
including games played while a fantasy free agent or bench player. The producer
must attest completeness; the exporter checks that attestation, scope, scoring,
unique identities, finite totals and valid GP. It cannot independently prove that
a producer did not omit NBA players. `maxTeamGames` must be the maximum completed
NBA team game count for that snapshot; if unavailable, the explicitly labeled
fallback is maximum player GP in the complete pool. Headshot URLs are optional.

Total FPTS is the default. Rankings use selected metric descending, other metric
descending, then numeric ESPN ID ascending (ordinal ranks). Per-game eligibility
is max(1, ceil(0.25 × maximum team GP)). All rostered below-cutoff players remain
in the same table; unqualified/no-stat players receive NQ, not an invented rank.

## Changed components

- `Standings`, `HomeSections`, `App`, `StandingsPage`, `home-data`: same seasonal
  snapshots and shared table; All-Play data on Home, including date-scoped exports.
- `StandingsVisualizations`, `standings-visualization-data`, `build_homepage`:
  observed completed playoff weeks, all week ticks, logo legend, static labeled
  scoring bars with logos and rounded y-axis references.
- `RecordBook`, `record-data`, `PlayerIdentity`, `generate_record_book`:
  shared headshots/fallbacks, safe encoded highlight searches, actual stat lines.
- `Top150`, `top150-data`, `generate_top150`, `Players`, `generate_all`:
  guarded season rankings, ownership and qualification behavior.
- `styles.css`, `homepage.css`, `record-book.css`, `players.css`: shared table
  scroll regions and compact styles. These affected tables preserve rows/columns
  at every width, overriding the prior design-system mobile-card option.

Browser regression: `frontend/tests/sprint-browser.cjs` uses Playwright Core and
local Chrome against the preview. It tests 375, 430, 768 and 1280px, with screenshots
in `/private/tmp/brawl-*.png`. The populated Top 150 UI uses a labeled synthetic
fixture; real data remains guarded. No runtime dependency was added.

## Validation and completion

- Complete: shared Home/Standings columns, data, logos, formatting and All-Play
  sorting; date-scoped All-Play records prevent future results in Home previews.
- Complete: rank chart includes completed playoff weeks, every observed week
  tick, compact logo selector and no point-click selection/instruction.
- Complete: scoring bars have logos, static FPTS labels, rounded reference ticks
  and gridlines; no hover-dependent content or native title tooltips.
- Complete: Standings and every expandable All-Time table preserve semantic rows
  and columns in internal scroll regions; all three player tables have headshots.
- Complete: safe dynamically encoded YouTube searches using saved NBA game dates.
- Partial: 100+ stat lines; all requested fields except unavailable raw 3PA are
  recovered. NBA opponents remain omitted from searches when unavailable.
- Partial: Top 150 UI/logic/export contract implemented and fixture-tested;
  real rankings blocked by missing complete NBA player-pool data.

Validation on the final implementation:

- `npm --prefix frontend test`: 98 passed.
- `python -m unittest discover -s tests -v`: 224 passed.
- `FRONTEND_TEST_OUTPUT=/private/tmp/brawl-sprint-data python -m unittest discover -s frontend/scripts -p 'test_*.py' -v`: 168 passed against a completed full export.
- Final Record Book parity rerun after passing metadata into enrichment: 11 passed.
- Full export and Vite production build succeeded.
- Browser regression passed at 375, 430, 768 and 1280px: every season selector,
  aligned table display, no document overflow, expanded/collapsed records,
  sorting, chart logos/ticks/filter interactions, Home parity, image fallback,
  and guarded plus populated-fixture Top 150 behavior. Screenshots reviewed.
- `git diff --check`: passed. Original local dirty snapshots and app changes
  were not staged. No push, merge, or public deployment was performed.
