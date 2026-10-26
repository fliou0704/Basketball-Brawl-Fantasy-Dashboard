These fixtures derive from the failed October 26, 2026 updater run:

- Canonical input: main `477dd10f42ab7aa57e9f6b8df350ba6a7bb3c66f`.
- Implementation: codex `e4c6c379be5cb9f1cf3800c82cc487f94f758bc3`.
- `daily_before.csv`: all 388 persisted 2027 daily records.
- `daily_incoming.csv`: authenticated ESPN periods 1–7 refetch, also 388 records;
  period 7 has complete lineups but no played games, and therefore no daily rows.
- `league_week1.csv` and `players_week1.csv`: first completed matchup from the
  verified disposable update, in canonical column order.

Names, abbreviations, and owners are replaced with deterministic fixture labels.
Player/team IDs and statistical values are retained to reproduce the eight real
corrections. No cookies, headers, credentials, or request objects are included.
Daily statistical breakdown fields contain fantasy point contributions, rather
than raw box-score counts (for example, one steal contributes four points).
