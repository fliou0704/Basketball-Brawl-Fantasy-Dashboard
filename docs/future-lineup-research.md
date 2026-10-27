# Future fantasy lineup research — October 27, 2026 ET

Research only: no future-lineup ingestion, data files, updater changes or future-lineup UI were added. Read-only experiments used the existing credential helper, league 609694684 / season 2027 and espn-api 0.41.0. Current status was Week 2, scoring period 8.

## Verified availability

**ESPN returns date-specific future assignments.** This direct read returned full rosters for all ten teams:

```python
league.espn_request.league_get(params={
    'view': ['mRoster'], 'scoringPeriodId': target
})
```

Periods 8, 9, 11, 15, 38 and 167 (the final league period) were tested. The response root echoed the requested period while status.latestScoringPeriod remained 8. More significantly, the **same fantasy team's** player-to-slot assignments differed between periods 8, 9 and 11. Nine of its 15 players changed slot between today and tomorrow. Across the league, five of ten teams had at least one changed assignment.

That sampled team's assignments were identical at periods 15, 38 and 167. Responses are therefore accessible through the final period, but distant responses may carry forward defaults. This experiment does not establish that a manager explicitly planned every future date.

Observed structure, with identities anonymized (real IDs are integers):

```json
{
  "scoringPeriodId": 9,
  "status": {"latestScoringPeriod": 8},
  "teams": [{
    "id": "TEAM_A",
    "roster": {"entries": [{
      "playerId": "PLAYER_A",
      "lineupSlotId": 11,
      "status": "NORMAL"
    }]}
  }]
}
```

Actual anonymized examples changed slot 4→11 (C→UT), 11→4 (UT→C), and 3→12 (PF→BE). These are assigned slots, separate from position eligibility. Entry keys also included acquisitionDate, acquisitionType, injuryStatus, pendingTransactionIds and playerPoolEntry. All 159 league entries had status NORMAL in both sampled periods. The inspected fields do not establish who selected a slot or whether it was manually set versus inherited.

## Existing wrapper and exporter

Raw mMatchupScore/mScoreboard reads also honored scoringPeriodId 9: rosterForCurrentScoringPeriod for the **same team** matched tomorrow's mRoster assignments and differed from today's. Despite its name, that property was date-sensitive. rosterForMatchupPeriod and rosterForMatchupPeriodDelayed were aggregate contribution views, containing only three entries on the sampled side; they are not full daily lineups.

`League.box_scores(scoring_period=future)` alone does **not** select a future period: its branch only accepts periods at or before the current one. Passing both matchup_period and scoring_period accepts explicit IDs; matchup_total=False selects rosterForCurrentScoringPeriod. It also fetches NBA schedules. A direct mRoster read is the smaller future integration: one request per date for the whole league.

The current exporter requests mRoster without future period IDs and exports current membership, eligibility and current slots. It neither requests nor retains per-date future lineups. NBA player schedules do not establish fantasy lineup selections.

## Limitations and recommended approach

These are ESPN-returned assignments, not project-generated lineups. Manual intent remains unverified; compare a known manager-selected date with ESPN's UI before calling all future entries “manager planned.” No lineups were edited during research.

Verified league settings are INDIVIDUAL_GAME lineup locks and FIRSTGAME_SCORINGPERIOD roster locks. Future assignments remain mutable; transactions, injuries and manager edits can change them. A selected starter is not a guaranteed played start. Post-lock mutation and transaction propagation were not measured.

For a future task, collect a small rolling window of verified dates via mRoster. Retain complete entries even without game stats, keyed by season, scoring period, calendar date, team/player ID and lineupSlotId, with fetchedAt. Label them **“ESPN lineup as of [time]”**, with manual/default provenance unknown. Cache bounded requests, refresh near locks, validate roster/slot coverage, and use the existing backend credential helper and static export pipeline. Never replace unavailable assignments with today's roster, matchup aggregates or an optimized lineup. This integration is **not implemented** here.
