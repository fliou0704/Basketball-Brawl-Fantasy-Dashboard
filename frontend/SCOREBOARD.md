# Scoreboard Stage 1

Route: `#/scoreboard?season=2027&week=1`. The unqualified route follows the latest exported ESPN current season/matchup period, including day one with no played games. Hash changes preserve refresh, back and forward, and GitHub Pages compatibility. Arrows traverse known weeks across seasons; selecting an archived season opens its last known week. Unknown links show an unavailable state.

`generate_scoreboard.py` runs inside `generate_all.py`, so both existing Pages workflows and the automated three-hour refresh include it without workflow changes. It reads currentLeague.json, seasonMetadata.json, scoringPeriodMatchupMap.csv and canonical league results. No new ESPN calls or scoring changes. `actualScores` are numeric or null; future scores are always null. No projections are exported. Existing Match, Team/TeamLogo, page, section and card components supply presentation.

## Availability and freshness

The repository snapshot supports 2023–2026 finals, including confirmed playoff byes, plus 2027 Weeks 1–20 assignments. Current season/week is 2027/1 at scoring period 1, observed October 20, 2026. It is not advanced by counting performance records or assuming the wall clock implies a newer ESPN period. Current scores accumulate only mapped periods through that snapshot. The page calls out an older scoring-period snapshot, retries every five minutes and on focus, and retains the last successful load if refresh fails. Data-update time is recorded by the validated updater, as described below.

## Scheduled dates and update provenance

The original `weeks` boundaries and scoringPeriodMatchupMap.csv were assembled from observed `pointsByScoringPeriod` keys (plus today's status period). They were not a full season schedule: a current week stopped at the latest observation, and future assignments had no date bounds. They must not be presented as complete calendar ranges, even for archived seasons whose no-game boundary dates may be missing.

The existing bounded updater already fetches `mSettings` together with `mMatchupScore` and `mTeam`. It now allowlists `settings.scheduleSettings.matchupPeriods` into a separate `scheduledWeeks` field: explicit scoring-period lists map through the validated league-local `dateAnchor`. No extra ESPN requests, seven-day assumptions, last-performance endpoints, or changes to canonical scoring/map semantics. `refresh_season_metadata.py` also retains these settings on its existing explicit refresh. Extended/All-Star and playoff periods, including dates across calendar years, follow the exact returned lists. Missing, malformed or overlapping schedules are unavailable; future schedule dates do not imply published opponents.

The Scoreboard exporter reads only these scheduled boundaries for full ranges. Existing local inputs do not yet contain `scheduledWeeks`; those seasons show **Schedule dates unavailable** until an authoritative settings refresh supplies them. The scheduled updater automatically populates the current season using its existing GitHub Secrets. Archived seasons require their existing explicit metadata refresh; observed historical dates are not silently promoted to scheduled dates. Local ESPN credentials were unavailable during this change, so live response coverage could not be confirmed.

`currentLeague.updatedAt` records the UTC time when a changed scoreboard snapshot passes all existing candidate validation. It is retained when roster/calendar/score content is unchanged, keeping no-change refreshes deterministic. The exporter preserves that timestamp and never substitutes export time, HTTP Last-Modified, or visitor time. **Last updated** appears only when the selected week contains in-progress matchups and a valid stored timestamp exists. Legacy inputs without it hide the timestamp until a successful data refresh. The bottom fantasy-points disclaimer has been removed.

## Projection data audit (repository + installed espn-api 0.41.0)

This is a static audit of stored schemas, updater code, and installed SDK implementations, not a live verification of future ESPN responses. No projection data collection was added.

| Input | Classification | Evidence and limits |
| --- | --- | --- |
| Future NBA schedule per scoring period | Available through existing integration, not stored | `League._get_all_pro_schedule()` / `espn_request.get_pro_schedule()` exposes `settings.proTeams[].proGamesByScoringPeriod`; nearLiveUpdater already uses it for anchor and omission validation. Store all games, not `Player.schedule`'s first game per period, when Stage 2 is authorized. Future fantasy period mappings still need verified coverage. |
| Player fantasy points / rolling 10 games | Already stored, with coverage limits | playerDailyData.csv has Player ID, Date, Scoring Period, MIN and FPTS, including bench/IR games; playerMatchupData.csv has weekly totals. Deduplicate player-games, filter played games, and use canonical FPTS rather than redoing scoring. Current historical universe is fantasy rostered players, so unrostered stretches and newly acquired players may lack ten games. SDK Player.stats can expose additional splits, but coverage needs validation. |
| Fantasy roster membership | Already stored | currentLeague.json teams[].roster is current membership; daily rows preserve historical Team ID. Do not apply current ownership retrospectively. Future roster changes cannot be known. |
| Positional eligibility | Already stored | currentLeague.json roster[].eligibility, populated by live_rosters from Player.eligibleSlots; season metadata supplies active lineup slot counts. Historical daily Position columns are less complete than current eligibility. |
| Actual daily starting lineups | Historical assignments stored; current accessible; future reliability unverified | playerDailyData.csv Player Slot comes from box-score home/away lineups. SDK BoxPlayer reads lineupSlotId, Player exposes lineupSlot. `League.box_scores(scoring_period=future)` **alone does not select a future period** in this SDK: its branch accepts only periods <= current; both matchup_period and scoring_period can set a future request. That is a request capability, not proof ESPN returns future owner-set assignments. No stored future daily snapshots or documented owner-intent provenance exist. |
| Injury / availability | Available through integration, not reliably stored | SDK Player.injuryStatus and injured expose current flags; currentLeague's allowlist omits them. playerMetadata.csv Active/Status is an athlete profile refreshed weekly, not a timely fantasy injury feed. Future availability remains uncertain. |

**Future lineup provenance:** Neither the current stored schemas nor SDK lineupSlotId/lineupSlot establishes whether a manager explicitly chose an assignment, accepted a default, or let an old lineup carry over. No reliable explicit-versus-default signal was identified. Future assignments and their provenance must be validated against the actual ESPN response and UI before being described as owner-set. Do not infer active management from a valid starting slot.

## Stage 2 recommendation

First validate date-specific future lineup retrieval and provenance for this league, then design a separately timestamped projection export beside actualScores. Primary projections should use ESPN's actual date-specific assignments where reliable, preserving inactive-manager choices. Label carried/unknown assignments and insufficient coverage. Add a clearly labeled optimized comparison or fallback only as a separate mode; never silently replace actual lineups. Join verified NBA schedules, observed roster membership, eligibility and fresh injury flags to deduplicated rolling played-game FPTS. Backtest against frozen snapshots without changing canonical historical scores. Publish coverage and assumptions before implementing prediction outputs.

## Verification

Focused Python exporter tests and Node React/data tests cover day-one zero scores, accumulation, canonical finals, future null scores, missing assignments, byes, unknown opponents, season boundaries and deep links. Run normal repository checks:

```
python -m unittest discover -s tests -v
python frontend/scripts/generate_all.py
python -m unittest discover -s frontend/scripts -p 'test_*.py' -v
npm test --prefix frontend
npm run build --prefix frontend
```

Optional real-browser checks require Python Playwright and Chromium, then a running Vite dev server: `python frontend/tests/scoreboard_browser.py`. They exercise desktop/tablet/390px/320px, refresh, back/forward, future and historical navigation, playoff byes, missing assignments and horizontal overflow.
