# Stage 3: Historical H2H

Only Historical H2H is migrated in this step. The Dash application, production
CSVs, updater behavior, Team Stats, Record Book, and Power Rankings are unchanged.

## Dash parity

`basketballBrawlHistoricalH2H.py` remains the source of truth. The offline
exporter preserves these behaviors:

- Team IDs are stable franchise identities. Selector labels use the latest name
  selected by the Dash options callback, in the same order.
- Selecting one team removes it from the other selector.
- Overall Record includes every meeting, including consolation. Regular Season
  and Playoffs use their corresponding `Type` values.
- Matchup History excludes consolation, sorts year and week descending, and
  retains Year, Week, historical Team Name, Type, Result, integer Score,
  historical Opponent Team Name, and Opponent Owner.
- A row counts as a win only when `Win == 1`; every other row counts as a loss,
  including a tied fixture. This matches the existing callback.
- Playoff history rows remain bold. Wins and losses retain green/red emphasis.
- Opening a score shows both historical rosters for that year/week/team-name
  combination, sorted by FPTS descending and formatted to two decimals.
- Reversing the selectors loads the opposite perspective, reversing the record,
  score, result, team names, and owner fields supplied by the source rows.

Historical matchup names are intentionally not rewritten to current names. For
example, a current Wembarrassingggg versus Jalen Jalen and Jaylen pairing contains
older Keegan It Real versus Jalen Inc. rows and player-detail headings. This
matches Dash while keeping the franchise pairing keyed by Team ID.

## JSON and route

`public/data/historical-h2h.json` contains `schemaVersion`, ordered current
`teams`, the eight displayed `columns`, and an ordered-pair-to-file lookup.

`public/data/historical-h2h/{lowerTeamId}-{higherTeamId}.json` contains both
perspectives for one unique franchise pair. Each perspective contains the two
IDs, current display title, three formatted records, optional never-played
message, and ordered history. Each history row contains its displayed fields,
playoff flag, and precomputed player details. React only selects and renders it.

The page route is `#/historical-h2h`. Home, Team Stats, and Historical H2H are
working shared-header destinations; later migrations remain disabled.

## Validation

Six offline parity tests execute the actual Dash callback functions from their
AST with inert UI components. They validate all 45 unique pairs in both
perspectives, all 850 displayed perspective rows and their player details,
selector ordering/exclusion, playoff flags, historical names, reversed records
and scores, plus explicit tied, consolation, and never-played cases.

The Pages workflow generates H2H data from its existing read-only main data
checkout, runs the complete frontend test suite, builds Vite, and deploys only
the static artifact. It does not import or run Dash and does not modify source
data.

Files added: `scripts/generate_historical_h2h.py`,
`scripts/test_historical_h2h.py`, `src/HistoricalH2H.jsx`,
`src/historical-h2h.css`, this document, the manifest, and 45 pair files.
Files changed: shared navigation/routing, README, and the dedicated Pages
workflow.
