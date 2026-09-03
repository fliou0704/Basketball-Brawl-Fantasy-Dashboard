# Testing

Run the data-validation suite from the project root:

```bash
python3 -m unittest discover -s tests -v
```

The suite runs without network access or ESPN credentials. It validates the
CSV files used by the dashboard, including required schemas, duplicate rows and
logical duplicate records, reciprocal league matchups, team references, numeric
score fields, and date formats.

When adding a data updater, run this command before committing its output.

## Incremental-update contract

`tests/test_incremental_data_updates.py` uses small synthetic records and no
live API calls. It documents the required behavior before updater code changes:
existing rows must remain byte-for-byte unchanged, only the new week may be
appended, corrupt candidates must fail before a write, historical seasons must
remain intact, and a prior season must be completed before a new season begins.

The logical uniqueness keys are:

- `basketballBrawlLeagueData.csv`: `Year`, `Week`, `Team ID`. Each row is that
  fantasy team's standings record for one week. Playoff byes must still have a
  row, so they do not need a special key.
- `playerMatchupData.csv`: `Year`, `Week`, `Team ID`, `Player ID`. A player can
  change fantasy teams over a season, but should occur only once for one team in
  one matchup week.
- `playerDailyData.csv`: `Year`, `Scoring Period`, `Team ID`, `Player ID`.
  Scoring period identifies the fantasy day, while team ID preserves the roster
  attribution if a player changes teams during a season.
