"""Allowlisted ESPN schedule dates and scoreboard snapshot provenance."""
from datetime import date, timedelta


def scheduled_weeks(schedule_settings, anchor, first_period, final_period):
    """Use explicit ESPN matchupPeriods, never point/performance observations.

    dateAnchor is the validated league-local date for scoring period zero.
    Missing, malformed or overlapping schedules are unavailable, not extrapolated.
    This field stays separate from the canonical observed scoring-period map.
    """
    periods = schedule_settings.get('matchupPeriods')
    if not isinstance(periods, dict) or not periods:
        return []
    try:
        origin = date.fromisoformat(anchor)
        weeks, seen = [], set()
        for key, values in periods.items():
            week = int(key)
            if week < 1 or not isinstance(values, list) or not values:
                return []
            if any(isinstance(p, bool) or str(int(p)) != str(p) for p in values):
                return []
            days = sorted(map(int, values))
            if days[0] < first_period or days[-1] > final_period or len(set(days)) != len(days) or seen.intersection(days):
                return []
            seen.update(days)
            weeks.append({'week': week, 'firstPeriod': days[0], 'lastPeriod': days[-1],
                          'start': (origin + timedelta(days=days[0])).isoformat(),
                          'end': (origin + timedelta(days=days[-1])).isoformat()})
        if len({w['week'] for w in weeks}) != len(weeks):
            return []
        return sorted(weeks, key=lambda w: w['week'])
    except (ValueError, TypeError, OverflowError):
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
