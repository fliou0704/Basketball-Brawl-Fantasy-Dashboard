# Stage 3: Record Book

Only Record Book is migrated in this step. Dash, production CSVs, updater
behavior, Team Stats, Historical H2H, and Power Rankings are unchanged.

## Dash parity

`basketballBrawlRecordBook.py` remains the source of truth. The offline exporter
preserves its default latest-season selection plus the All-Time option.

All-Time contains:

- Most Points in a Single Matchup (Team)
- Most Points in a Single Matchup (Player)
- Most Points in a Single Day (Player)
- Top 10 Most Active Players (Total Transactions)
- Players with 100+ Point Days, including the occurrence-count line
- Players with Negative Point Days, including team-logo occurrence counts

Each season contains the year Awards heading, MVP, All-NBA 1st/2nd/3rd Teams,
Best Waiver Add, and League Slut (Most Unique Teams in a Season).

The implementation intentionally retains these Dash definitions:

- The three single-game records use the first row after descending sort.
- Most Active Players counts only `WAIVER ADDED`, `DROPPED`, `DRAFTED`, and
  `TRADED`, groups by activity `Asset`, sorts descending, and takes ten.
- 100+ days include every daily FPTS row at or above 100, newest date first.
  Player occurrence counts retain pandas `value_counts` ordering.
- Negative days include only FPTS below zero and exclude `BE` and `IR`. Their
  table is newest first. Team counts use Team ID but display the latest name
  found among negative rows, then map that name to the existing logo mapping.
- Season MVP totals weekly FPTS by Player Name across every recorded week.
- All-NBA teams expand all three saved position fields, rank by total season
  FPTS, fill G/G/F/F/C, prevent reuse across all three teams, and display the
  player's latest team name for the season.
- Best Waiver Add includes only `WAIVER ADDED`, removes repeated player/team
  additions for the year, joins Player Name and Team Name to weekly FPTS totals,
  and takes the first descending result.
- Most Unique Teams counts distinct Team IDs for every activity action and shows
  every player tied for the maximum.

No definitions, filters, labels, metrics, or tie behavior are changed.

## JSON and route

`public/data/record-book.json` contains `schemaVersion`, `defaultYear`, descending
`years`, `allTime`, and `seasons` keyed by year. All displayed strings, ordered
records, tables, counts, All-NBA selections, and awards are precomputed. React
only selects All-Time or a year and renders the supplied values.

The route is `#/record-book`. The shared header now links Home, Team Stats,
Historical H2H, and Record Book. Later destinations remain disabled.

## Validation

Six deterministic tests execute the actual Dash Record Book callback from its
AST using isolated CSV copies and inert UI components. They compare every
All-Time record and table plus every section for all four seasons. Separate
assertions cover year ordering/defaults, transaction action exclusions, 100+
and negative thresholds, bench/IR exclusion through direct table parity, logo
counts, tied maximum unique-team rows, unique All-NBA selection, and repeated
waiver-add deduplication.

The Pages workflow generates the JSON from its existing read-only main data
checkout, runs the complete frontend tests, builds Vite, and deploys the static
artifact. It does not import Dash, run an updater, or write production data.

Files added: `scripts/generate_record_book.py`, `scripts/test_record_book.py`,
`src/RecordBook.jsx`, `src/record-book.css`, this document, and
`public/data/record-book.json`. Files changed: shared navigation/routing, README,
and the dedicated Pages workflow.
