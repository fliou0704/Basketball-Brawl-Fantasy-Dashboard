# Standings, injury availability, franchise trends and historical audit

Started from synchronized `codex` d92df76 on October 30, 2026. Existing uncommitted work is preserved. All generation and live updater validation used a disposable copy of canonical `origin/main` data, not the workspace datasets.

## Features and calculation scope

- Standings adds All-Play from official frozen weekly FPTS. Each full-field completed regular week awards one result against each other team; ties contribute half a win to percentage. Missing fields, duplicate teams, nonfinite scores, playoffs, byes and unfinished weeks are excluded. Sort: percentage, wins, included-week FPTS, stable franchise ID. Historical team identities are retained. Existing standings and W–L results are unchanged.
- Weekly Scoring Leaders uses the entire verified regular-season week range for geometry and labels. Future weeks have positions without bars. Completed scores and team colors are unchanged.
- Teams Summary adds Season/Week/Day for FPTS, Season/Week for regular rank and FP/Start. Week FPTS uses official matchup scores; daily FPTS uses credited eligible player performances in verified recorded matchup weeks, excluding byes. Missing/unsupported data is unavailable, never interpolated as zero. Daily dates without credited games are omitted. All recorded franchise seasons are chronological, with season boundaries and partial-season treatment. Hover/focus preserves full dates, weeks and seasons; labels thin automatically. Lines connect actual observations without smoothing.
- Weekly ranks reuse canonical regular-season rank snapshots and require a complete field. Rank 1 remains at the top. Playoff placement is excluded. Weekly FP/Start uses verified eligible player FPTS / credited starts, including legitimate zero/negative performances; zero or unverified denominators remain unavailable. Season/career rates sum numerators and denominators before dividing.
- Verified official-versus-player score differences appear contextually on Scoreboard, Teams season views and a compact franchise disclosure. Official scores, results and corrected player numerators are preserved independently.

## Injury source, freshness and limits

The already-requested ESPN `mRoster`/Player wrapper supplies `injuryStatus`. This is regularly refreshed by the established three-hour updater; profile metadata is not used as a game-specific injury feed. The roster snapshot now records `injuryVerifiedAt` and source alongside the status, with no additional injury API requests.

ESPN OUT and SSPD/SUSPENDED exclude projected starts **only on the same New York date as the fresh observation and projected game**, at most six hours old relative to the snapshot. Started/completed games never enter the future pool. IR lineup slots remain excluded under existing rules. QUESTIONABLE, DOUBTFUL and DAY_TO_DAY do not exclude players. The trailing-game ability estimate remains visible for every scheduled game, including excluded players, and the lineup re-optimizes with eligible bench replacements.

Later dates assume participation and explicitly retain uncertainty: current OUT is not proof that a player will miss the entire remaining week. Missing, stale, unknown or unsupported statuses never declare a player healthy or excluded. This implements same-day verified status cases only; no return dates, injury interpretation or future game-specific absences are invented. Snapshot age remains visible through existing publication metadata and freshness checks.

## Raw 3PA: verified and recovered

Historical daily CSVs genuinely lacked raw 3PA. ESPN stat ID 18 maps to `3PA`; its scoring weight is absent/zero, so historical applied fantasy-stat exports did not preserve attempts. Recent ingestion already reads raw `stats.total['3PA']`; the exporter correctly marked old coverage incomplete.

Four bulk historical player-card reads, one per season, recovered every retained 2023–2026 daily row. Each raw actual-game sample must match season/player/scoring-period, saved applied FPTS and minutes; conflicting samples, missing attempts or mismatched records remain unavailable. Explicit zeros are retained. No attempts are inferred from makes, and no scoring formula is changed.

| Season | Historical daily rows | Raw 3PA recovered | Missing after recovery |
| --- | ---: | ---: | ---: |
| 2023 | 10,412 | 10,412 | 0 |
| 2024 | 10,338 | 10,338 | 0 |
| 2025 | 9,801 | 9,801 | 0 |
| 2026 | 9,281 | 9,281 | 0 |

The updater records the attempt and coverage in `seasonMetadata.historical3PARecovery`, preventing repeat historical requests. A failed historical attempt is recorded and leaves values null for deliberate later review. Scheduled generation remains automatic. The disposable integration update changed only 3PA among daily columns: all 40,472 rows and every other column matched the source exactly. Weekly player records and official league records were unchanged. This is bounded stat enrichment, not a roster or historical-scoring rebuild.

## The seven reported daily discrepancies

The 5 / 1 / 0 / 1 counts still exist. Four current season-score requests confirmed that saved ESPN daily aggregates are unchanged. Bulk actual player-game FPTS/MIN also match canonical individual performances. Verified independent saved weekly-player totals reconcile the affected player scopes. These findings are score-source disagreements, not evidence of absent roster rows or a proven lineup-lock ingestion bug. The exact ESPN cause remains unresolved; preserve both sources.

| Season | Date | Team ID / historical name | ESPN daily aggregate | Eligible player FPTS | Player minus ESPN |
| --- | --- | --- | ---: | ---: | ---: |
| 2023 | 2023-03-19 | 2 · New Jersey Eren | 229 | 228 | −1 |
| 2023 | 2023-03-19 | 13 · The Bronx Orthodox Church | 265 | 266 | +1 |
| 2023 | 2023-04-01 | 12 · Pooh Shaisty | 51 | 47 | −4 |
| 2023 | 2023-04-01 | 16 · Fordham Rams | 39 | 43 | +4 |
| 2023 | 2023-04-01 | 13 · The Bronx Orthodox Church | 50 | 52 | +2 |
| 2024 | 2024-03-17 | 17 · I Watch Basketbal | 228 | 229 | +1 |
| 2026 | 2026-03-29 | 10 · For All the bullDawgs | 198 | 202 | +4 |

`data-quality.json` now includes exact teams, dates, periods, weeks and both totals, plus an explicit definition explaining that the legacy `activeRosterMismatches` counter compares scores, not roster completeness.

An additional existing weekly discrepancy is 2026 Week 18, team 1: official 1,467 versus eligible 1,471. Saved ESPN daily scores agree with the eligible total, so it is absent from the daily mismatch counter. Weekly difference coverage is therefore 5 / 1 / 0 / 2 across 2023–2026. Contextual explanations include all eight affected team-weeks, rather than only the seven daily differences.

## Historical FP/Start verification

All 40 historical team-seasons are available: 240/240 team-weeks in 2023, 230/230 in each of 2024–2026 (including correctly excluded bye scopes). No FP/Start backfill was restarted. Existing independent weekly-player and saved ESPN daily-score reconciliation remains in use, retaining corrected player FPTS even when frozen scoreboard results differ. Fresh generated team profiles and franchise totals are checked against summed FPTS/starts; weekly chart values use those same verified metrics.

## Validation and deployment

Focused tests cover all-play ties and incomplete fields, full-season bar geometry, same-day injury exclusions and replacements, uncertain/stale/later availability, untouched player averages, bounded raw-stat recovery, chart ordering/gaps/rank direction, and contextual score reconciliation. Full backend/exporter/frontend tests and production build are run against fresh disposable exports. Browser checks cover all five seasons, every franchise granularity control, historical/current FP/Start, scoreboard differences and overflow at 1280px, 390px and 320px, plus existing matchup refresh checks.

The established Pages workflow regenerates every browser-facing payload from canonical data and uses `codex` for site/updater code. The established League Data and Pages workflow publishes only validated canonical data to main; no code merge into main is used.
