# Top 150: coverage, final-period ownership and qualification

Review branch: `top150-improvements`, based on codex/main `43ea72e387c185a76f35d5bf6ab1b77a014b1679`. No merge or production deployment is included. Daily player-data activation remains disabled.

## Why Nic Claxton looked like he had not played

The leaderboard reads the **NBA-wide** `playerGameLogs.csv → playerSeasonStats.csv → generate_top150.py → top150/{year}.json` chain. It contains every participating athlete in verified final regular-season fixtures, including unrostered players; it is not restricted to fantasy starters.

Player profiles instead read `playerDailyData.csv` through `generate_players.game_log`, which includes saved positive-minute NBA appearances regardless of fantasy starter, bench or IR status. Career/FP-per-start and fantasy matchup calculations still use their separate scoring-eligibility rules.

The comprehensive archive's last successful refresh covers 125 current-season NBA games through November 6 (108,051 appearances across all five seasons). Its subsequent GitHub trial hit the 200-request cold-cache budget; collection is still gated off. Canonical fantasy-roster updates continued independently. This is a stale source archive, not a stale Vite asset or an intentional starter-only ranking restriction.

Nic Claxton (`4278067`) has no current-season appearance in that archive. The saved daily source has his **November 8 game: 18 minutes, 23 FPTS, slot IR**. That game correctly appears on his player profile but is newer than the NBA-wide ranking cutoff. Newer saved roster observations affect **137** leaderboard players; Claxton is the only currently rostered zero-archive-game placeholder with such a newer observation.

The cached canonical NBA schedule identifies **at least 21 finalized games** absent from the archive, on November 6–8: 146 final fixture IDs versus 125 collected IDs. Roster data extends through November 9, so a fresh independent fixture check may reveal additional missing games. These counts are from existing saved files, not a new NBA polling run.

### Safe fix and remaining data limitation

The exporter now publishes newer-roster coverage diagnostics and a per-season content version. The UI names the NBA cutoff separately from ownership freshness, says a full archive refresh is pending, and shows Claxton's newer game date with a working profile link. Opening an archive log also explains newer roster-game availability. These diagnostics update automatically through the existing export/build pipeline when canonical data changes, even if the NBA archive timestamp stays unchanged.

**The NBA-wide statistics remain through November 6.** No roster-only FPTS were added to rankings: doing so would favor fantasy-rostered players while omitting free agents' newer games. No synthetic NBA appearances, fantasy starts, scoring totals or historical records were created. Zero archive GP means no appearance in the validated archive at its displayed cutoff, not a claim that the player has never played since.

The safest follow-up, requiring separate approval, is a **current-season-only, non-persisting continuation of the existing collector**, reusing validated response checkpoints wherever their branch scope allows. Then validate complete fixture/participant coverage, compare historical rows, and commit a successful candidate only after review. At least 21 missing box scores plus fixture discovery and bounded bulk fantasy pages must be checked; a cold bootstrap can exceed 200 requests, while warm checkpoints avoid repeating completed requests. Establish checkpoint availability and a bounded budget before that trial. No new provider, per-player career collection, recurring workflow or large historical game-log backfill is needed. Do not enable the daily gate merely to repair this snapshot.

## Historical ownership: one consistent final fantasy period

Eight bounded, read-only ESPN requests were used: one default archived `mTeam+mRoster` view and one explicit final-scoring-period view per completed season. They transferred 11,185,840 bytes total, with no retries or per-player requests. Existing credential loading and the timeout/retry-limited client were reused. Credentials, private membership/owner records and raw responses are not saved.

Default archived rosters are not a safe season-end definition: the 2023/2024 defaults include June acquisitions. Explicit `scoringPeriodId` queries return different roster snapshots. We use the **league-wide final fantasy scoring period**, not each eliminated team's last matchup and not a later archived/offseason roster.

| Fantasy season | Final period | Verified roster entries | Different player ownership states versus default archive |
| --- | ---: | ---: | ---: |
| 2023 | 175 | 159 | 18 |
| 2024 | 167 | 167 | 3 |
| 2025 | 167 | 164 | 5 |
| 2026 | 167 | 161 | 0 |

`data/seasonEndRosters.json` is a new public-only normalized source snapshot: league/season/period identifiers, verification timestamp, team IDs/names and roster player IDs/names/slots. All ten teams must be present, roster entries must be nonempty, player ownership must be unique, the returned season/period must match canonical final-period metadata, and the source league/schema must match. Invalid coverage stops export. Missing snapshots stay **unknown** rather than implying free agency.

Ownership includes bench and IR. In a verified complete snapshot, an absent player is a free agent at that final period. Late adds/drops/trades are represented by that snapshot, not inferred from an earlier game or an incomplete transaction ledger. Team IDs and the selected season's canonical historical names/logos are used, so current naming changes do not rewrite past identities. Historical rostered players with no NBA appearances remain visible without fabricated statistics.

The table and fantasy-team filters now work for all four historical seasons. The UI explicitly labels “Season-end ownership” with its final fantasy scoring period; active-season ownership still uses the latest saved current roster. These are end-of-season affiliations, not ownership on each game's date. The historical snapshots are static reviewed facts, not an automatically polling historical collector. The Pages input path list includes the new ownership source; all export logic remains in the existing exporter.

## FPTS/game ranking behavior

Minimum GP is unchanged: `max(1, ceil(0.25 × maximum NBA team games))` (currently 3; completed 82-game seasons require 21).

- Sort all valid averages together by FPTS/game descending, total FPTS descending, then numeric ESPN player ID.
- Assign numerical ordinal ranks only to qualifiers. Ineligible players have a dash and a subdued `Ineligible · GP/minimum GP` label, with their actual average still shown.
- With at least 150 qualifiers, retain exactly ranks 1–150 and insert every ineligible player that sorts before the 150th eligible boundary using the same deterministic tie-breaks. They do not consume a rank or appear again in the rostered-outside section.
- With fewer qualifiers, keep every qualifier and include only ineligible players among the top 150 valid averages. With no qualifiers, show at most the best 150 valid averages, all unranked. This bounds short-field low-sample additions without losing qualifiers.
- No-game/undefined-average players never precede real averages. Owned no-game players remain in the rostered-outside section; others remain searchable. Total-FPTS ranking semantics and existing filters/overall ranks are unchanged.

The saved data reproduces the requested example exactly: **Jamal Murray rank 14, 46.4286; Paolo Banchero unranked, 45.0 over 2 games; Ty Jerome rank 15, 43.4286**. Current per-game view shows 150 eligible ranks plus six inserted ineligible players.

## UI and validation

Removed the extra Basketball Brawl eyebrow inside Top 150, retaining the primary masthead/navigation and the Players page branding. Embedded heading uses h2; the dedicated route uses h1. Search-to-leaderboard spacing is 32px and heading-to-controls spacing is 18px at desktop/mobile sizes. Narrow-screen sticky-name width is adjusted at 320px so the rightmost FPTS/game value remains readable during horizontal scrolling. Other pages are not restyled.

Validation covers stale IR-game evidence, version invalidation, final-period versus default rosters, missing teams/duplicate owners/wrong seasons, unknown versus free-agent status, trade/drop snapshot behavior, historical identities, no fabricated statistics, ineligible boundaries/ties/short fields and the actual Paolo/Claxton examples.

- 259 backend tests; 178 exporter tests; 110 frontend tests; actionlint; production Vite build.
- Real-HTTP built-preview Chrome at **320, 390 and 1280px**: both ranking entry points, 150 eligible ranks plus six inserts, correct Murray/Banchero/Jerome order, free-agent/search filters, all 163 active roster entries and all four historical roster totals, game logs and Claxton's profile game (23 FPTS/18 MIN).
- No duplicate Top 150 brand eyebrow, measured search/header/control spacing, no page overflow, readable rightmost values with sticky columns. Home, Standings, Team Overview, Historical H2H, Record Book and Scoreboard smoke checks remain passing. Separate missing-file, invalid JSON/schema, incomplete coverage and empty-season checks pass.
- Existing tracked canonical data, player archive/report/summaries/static shards remain unchanged. Only the new reviewed historical-ownership snapshot is added under data. No updater, live publisher, schedule, activation variable or production setting changes are made.

Full current NBA statistics require the separately approved collector continuation described above. This feature branch can be reviewed without activating collection or deploying it.
