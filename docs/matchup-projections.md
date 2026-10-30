# Matchup projections and historical Potential Points

Starting point: synchronized codex/origin/codex 5b3bd331798ec65f93da73ec032af2f2b0cb4a5d. Existing uncommitted work is preserved.

## Data audit and sources

Existing canonical daily records include active, bench and IR game performances, original fantasy team/player IDs, minutes and recorded position eligibility. They support historical contribution displays, but omit players without game stats and performances while unrostered. Fantasy seasons can also end before the NBA season. Therefore those records alone cannot certify a player's last ten NBA games or a complete historical roster.

The existing NBA fixture cache, verified fantasy calendar, current roster affiliations/eligibility, roster-since evidence and lineup-lock calculations already support Remaining Opportunities. Those calculations and actual fantasy scoring remain intact. The opportunity export now also retains the exact unoccupied slot template and locked player IDs, permitting weighted optimization against the same evidence.

One bulk `kona_playercard` read requests all current-roster IDs, including current and previous-season actual game stats. Only statSourceId=0, statSplitTypeId=5, positive-minute rows are accepted. NBA game ID identifies and deduplicates appearances. Current games require a completed/official fixture, with start at or before the snapshot; in-progress games are excluded. Past fixture dates are reused where available, otherwise past actual scoring-day IDs use the retained, verified season anchor. AppliedTotal is already ESPN's custom league FPTS; no fantasy scoring formula is recalculated. Unsupported historical scoring-rule differences fail closed.

Older filters on the current-season endpoint do not reliably retrieve seasons before its previous season. Short samples use explicit historical-season bulk endpoints. Historical samples and checked seasons are cached, so future runs fetch only current/previous-year samples and any genuinely new short-history players. No per-player request loop, full-history rebuild, browser authentication, or new credentials are introduced. Persist only up to twenty completed games per current-roster player in the allowlisted currentLeague.projectionHistory snapshot. Optional sample failures withhold forecasts without interrupting validated canonical scoring updates.

A disposable update retrieved all 162 current-roster players: 153 have at least ten completed games and nine have shorter available samples. Four veterans with season-long absences required a 2025 endpoint; they are not incorrectly treated as four-game samples. All 2,530 sampled games overlapping the canonical daily data have identical FPTS. All retained seasons use the same scoring weights in the inspected dataset.

## Calculation

The user confirmed **regular-season fantasy game logs** as the sample scope. NBA postseason games are not included.

For each confirmed future player-game:

1. Select actual, completed games known at the data snapshot and strictly earlier than the projected game's New York calendar date.
2. Deduplicate NBA game IDs, sort chronologically, take the latest ten, and use the arithmetic mean. Keep legitimate zero and negative performances. Fewer available games remain explicitly labeled with sample count and date span. No future or recursively projected performances enter the mean.
3. Keep an individual estimate for every scheduled game, including IR and players omitted from the optimum.

For each fantasy team/date, slot-mask dynamic programming maximizes the sum of projected FPTS. A player can fill at most one eligible position; no more than ten scoring slots may be used. Empty slots are allowed, so negative projections need not be started. Deterministic player-ID tie-breaking keeps assignments stable. Bench players can start if eligible; IR membership excludes selection. Verified occupied slots and locked players are removed using the same context as Remaining Opportunities. Missing eligibility, unsupported limits/locks or a missing relevant player estimate withhold the exact team optimum rather than treating unknowns as zero.

Projected remaining FPTS sums daily optima. Projected final equals canonical actual FPTS plus that remaining value; upcoming matches use a zero *projection baseline* while actual scores stay unscored dashes. Completed matchups show actual finals only. Future roster membership is the current snapshot, with changes, health and DNPs explicitly uncertain. These are optimal-lineup estimates, never manager-selected lineups or participation guarantees.

NBA Cup/TBD uncertainty produces a confirmed-game subtotal, not a complete final forecast. Affected daily totals remain unavailable instead of displaying a false zero. In-progress or started/unconfirmed games are not projected again: their unresolved remaining scoring also withholds a full projected final, while later confirmed player-game estimates remain inspectable. Unknown/stale schedules and samples follow existing fail-closed behavior.

## Historical Potential Points

The same weighted optimizer can compute an actual daily maximum only with certified complete roster/game/eligibility evidence and supported historical locks. IR is excluded; acquired-after/departed players cannot be counted. Potential Points sum complete daily optima; Points Left on Bench is potential minus actual for the same completed dates; efficiency is actual/potential only for a positive denominator and nonnegative actual. Inconsistent results are withheld.

**Current exact historical coverage is zero.** Retained daily lineup coverage is recorded-games-only; it is never upgraded to a complete roster certificate. Neither today's roster nor weekly totals fill missing slots. The UI exposes unavailable metrics, covered/completed-date counts, and an expandable daily audit. No historical backfill or fabricated maximum was added. The next prerequisite is complete date-specific roster and eligibility evidence retained with game/lock provenance.

## Integration, examples and verification

Forecasts extend the existing shared matchup-opportunities export, keyed by season/week/team/date and NBA game ID; full game logs and fixtures are not duplicated into each matchup detail. At the validation snapshot the entire combined opportunities/forecast payload compresses to about 223 KB. Historical detail content hashes remain independent of live sample refreshes.

Example verified 2027 Week 2 snapshot (October 30, before today's games): Big Wong has 673 actual + 715.8 optimal remaining = **1,388.8 projected final**; The Bronx Orthodox Church has 378 + 528.8 = **906.8**. These numbers will change with completed games, rosters and fixtures; they are not guaranteed outcomes.

The existing four-section page is retained. The scorecard adds estimates below actuals; daily cells label estimated remaining/upcoming points separately from actuals; selected dates list projected starters and every other scheduled player, with sample sizes. Potential Points is a compact disclosure, and Remaining Opportunities is retained. No probabilities, simulations, injury predictions or add/drop advice are implemented.

Validation: 164 offline backend tests, 156 exporter tests against fresh disposable exports, and 73 frontend tests pass, as does the Vite production build. The cold-start disposable updater passed bounded canonical reconciliation and populated the cache without touching workspace datasets. Production-build browser checks at 1280px, 390px and 320px pass actual-plus-remaining totals, per-game estimates for starters and bench, the ten-player cap, future/Cup uncertainty, historical unavailability, existing H2H/navigation/opportunities, and stable idle/focus/poll/error-recovery behavior. Selected dates, dropdown DOM and scroll positions remain intact. Desktop/mobile screenshots were reviewed. Raw sample history is excluded from the browser's current-league export; only shared derived forecasts are published.
