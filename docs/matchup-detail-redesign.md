# Matchup box-score redesign

Started from synchronized codex/origin/codex commit 81556230d40353a14bede7a0deba6ead2b6af695. Existing local changes remain separate.

The detail page has four sections: facing scorecard, daily score comparison, head-to-head scoring breakdown, and remaining opportunities. The list view retains its existing controls and presentation. Details hide those controls and link back to the exact selected season/week. Routes and the hashchange navigation mechanism are unchanged.

## Reuse and orientation

H2H's TeamMark, PlayerSide, PlayerSides, and their original breakdown CSS are extracted into shared components. The existing H2H rendering uses those same components with its original player totals and markup. Scoreboard uses PlayerSides, the shared PlayerIdentity/headshots, TeamLogo, layout tokens, date formatters, canonical scoring totals and existing opportunity loader.

The retained seasonMetadata matchups use the updater's explicit home-then-away side order. Every two-sided archived assignment with canonical results was checked against the league CSV Home/Away field: 461 pairings agree, with no inversions. Archive-only fallback exports use the CSV Home/Away values directly. New explicit role IDs permit away-left/home-right presentation without sorting by score. Positional daily scores, official totals, recorded starts and opportunity arrays follow the same team-ID permutation. Unknown single-sided/byes do not invent an away/home role.

## Historical daily lineup support

The daily CSV retains original fantasy team ID, player ID, actual Player Slot, position eligibility, game FPTS and minutes. The updater skips a player when ESPN has no game-stat record. Consequently the dataset cannot verify a complete roster, all idle starters, or every bench/IR occupant on any given day.

The small exporter adjustment retains **all existing daily records**, including bench/IR and zero-minute entries, alongside the existing active-slot scoring aggregation. Specific dates show recorded slot assignments and explicitly state that the complete daily lineup is unavailable. No roster is inferred from weekly totals or substituted from today's roster. Future dates have placeholders only.

Summary groups the same canonical active-slot contributions by historical team/player, with actual slots used across the matchup. Bench/IR game FPTS appear separately with zero credited fantasy points. A player who moved between starter and reserve slots can appear in both groups, with only the active contributions counted. NBA team names come from the existing player metadata and are explicitly labeled current profile; historical game-day NBA affiliation is unavailable. No new ESPN requests or ingestion were introduced.

Daily columns use the existing verified scheduled calendar, or retained observed historical dates when a full scheduled calendar is unavailable. Future scores remain dashes, distinct from recorded zeroes. Official totals are displayed without distributing corrections across days. Existing reconciliation warnings remain visible when daily rows and canonical totals differ.

## Remaining Opportunities regression

The existing opportunity calculations, loaders, timestamp/completeness protections, NBA Cup/TBD warnings, per-day breakdown and player-level game details are retained. Only presentation order and always-accessible player disclosure controls change. No changes were made to the main updater, fantasyOpportunities.py, NBA schedule ingestion, fantasy scoring calculations, or calendar validation.

A before/after exporter comparison over 21 current, historical, extended-week and playoff pairings verifies identical remaining opportunities, completed starts, players, insights, reconciliation flags, daily points, cumulative totals and original contributors.

## Verification

- 146 offline backend tests, 142 exporter tests against fresh disposable exports, and 62 frontend tests pass. Vite production build passes.
- Fresh exports were generated separately from the untouched local canonical data and an archived copy of origin/main. No updater or live ESPN ingestion was run for this frontend task.
- Chromium checks at 1280px, 390px and 320px cover current 2027 Week 2, historical 2026 Week 1, extended 14-day Week 17, playoff Week 21 and future 2027 Week 3; away/home order, Summary/date selection, bench exclusion, four-section structure, hidden detail selectors, player opportunities, direct URL, refresh, back/forward, and existing H2H expansion pass.
- The daily table scrolls inside its own card with readable sticky team identities; the page itself has no horizontal overflow. Player names wrap instead of truncating. Desktop and mobile screenshots were visually inspected.
