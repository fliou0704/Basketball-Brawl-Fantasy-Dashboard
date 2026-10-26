# Home and Scoreboard recap lifecycle

Scoreboard embeds the existing seasonal weekly recap exports only for completed
weeks with at least one final matchup. It renders the shared `Weekly` component
below matchups using the selected season/week. Missing historical recaps stay
absent; future and unplayed weeks never acquire a recap. Export ordering in
`generate_all.py` already generates seasonal recaps before Scoreboard.

Home uses authoritative `currentLeague.json` season/week through the existing
current snapshot exporter. The current leaderboard still uses canonical daily
records mapped to that fantasy matchup week with MIN > 0, including partial
and zero-FPTS games. An empty player list now suppresses the whole leaderboard.
No previous-week fallback or scoring change was added.

## Calendar limitation and conservative fallback

`scoreboardCalendar.scheduled_weeks` and
`docs/scoreboard-calendar-investigation.md` document that inspected ESPN views do
not supply verified daily matchup boundaries. `seasonMetadata.weeks` and the
canonical period map retain observed scoring, which may omit no-game days.
`matchupPeriods` groups weekly base periods; those IDs are not daily periods.
Neither a last player game, inferred weekly cadence, nor an observed first game
is a valid scheduled boundary. No extra ESPN requests were added.

Accordingly the current exporter explicitly emits `verifiedWeekStart: null`.
**Production Home hides its temporary recap while that boundary is unknown.**
This is the requested conservative fallback; Scoreboard remains the permanent
home for Week 1 and historical recaps. A verified scheduled date source must be
established before production can open the two-day Home window. No currently
available observed or legacy `scheduledWeeks` value is promoted to that field.

`showHomeRecap` requires an active season, a completed earlier week, and that
verified start. It compares the requested New York calendar date with the start
and the following calendar date, excluding day 3. It does not assume a matchup
length. Home already refreshes its New York date every minute, independently of
new games or publication versions. Deterministic fixtures exercise the verified
window, playoffs, extended periods, missing dates, season start, and clock aging.

During the active season, Home order is: current scoreboard, current-week player
performances if present, playoff bracket when applicable, daily/temporary weekly
recaps, archive current matchups when applicable, standings last. Around the
League is removed, including its component, and Toughest Loss is no longer
exported. Closest Matchup and Team of the Week remain in the shared recap.

## Validation

Use the same source selection as the existing Pages workflow (production main
CSV/metadata copied into `frontend/.league-source/data`). Run the exporter before
its tests, with the workflow's source environment variables:

- `python frontend/scripts/generate_all.py --source-dir frontend/.league-source/data`
- `python -m unittest discover -s tests -v`
- `python -m unittest discover -s frontend/scripts -p 'test_*.py' -v`
- `npm --prefix frontend test`
- `npm --prefix frontend run build`
- With Vite running: `python frontend/tests/recap_browser.py`

The browser check uses deterministic dates and tests desktop, 390px, and 320px,
recap selection, missing-date fallback, first scoring, zero-FPTS participation,
standings order, and automatic clock expiration without new player games.
No updater, deployment workflow, canonical scoring, main branch, or Dash code
was changed.
