"""Allowlisted ESPN schedule dates and scoreboard snapshot provenance."""
def scheduled_weeks(schedule_settings, anchor, first_period, final_period):
    """No verified daily boundaries are exposed by the inspected ESPN views.

    Basketball periodTypeId=2 matchupPeriods groups base *weekly* periods
    into league matchup periods. For example {"1": [1]} coexists with daily
    pointsByScoringPeriod keys 1 through 6 in Week 1. It must never be decoded
    as daily scoring-period IDs, even if values happen to look plausible.
    Keep this fail-closed hook separate from observed metadata until ESPN
    supplies a verified daily-to-matchup calendar. No seven-day extrapolation.
    """
    return []


def dated_snapshot(snapshot, calendar, previous_snapshot, previous_calendar, updated_at):
    """Date a successfully validated data change, retaining provenance if unchanged.

    Export/deployment time and the visitor clock are never used. Call only after
    all candidate validation succeeds. Unchanged refreshes remain deterministic.
    """
    previous_snapshot = previous_snapshot or {}
    previous_data = {k: v for k, v in previous_snapshot.items() if k != 'updatedAt'}
    unchanged = previous_data == snapshot and previous_calendar == calendar
    return dict(snapshot, updatedAt=previous_snapshot['updatedAt']
                if unchanged and previous_snapshot.get('updatedAt') else updated_at)
