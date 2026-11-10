"""Pure date-to-homepage selection. All dates are league-local (America/New_York)."""
from datetime import date


def select_state(requested_date, seasons):
    day = date.fromisoformat(requested_date) if isinstance(requested_date, str) else requested_date
    completed = [s for s in seasons if s['complete'] and date.fromisoformat(s['end']) < day]
    previous = max(completed, key=lambda s: s['season'], default=None)
    active = next((s for s in seasons if s['start'] <= day.isoformat() <= s['end']), None)
    if active:
        prior_days = [d for d in active['completedDays'] if d < day.isoformat()]
        week = next((w for w in active['weeks'] if w['start'] <= day.isoformat() <= w['end']), None)
        if prior_days and week:
            previous_weeks = [w for w in active['weeks'] if w['end'] < day.isoformat() and w['week'] in active['completedWeeks']]
            prior_week = max(previous_weeks, key=lambda w: w['week'], default=None)
            phase = 'playoffs' if week['week'] > active['regularWeeks'] else 'regular'
            return {'phase': phase, 'season': active['season'], 'week': week['week'],
                    'dailyDate': max(prior_days), 'weeklyWeek': prior_week['week'] if prior_week else None,
                    'weeklyFirst': bool(prior_week and day.isoformat() == week['start']),
                    'standingsWeek': max([w['week'] for w in previous_weeks if w['week'] <= active['regularWeeks']], default=None),
                    'playoffKey': str(week['week']) if phase == 'playoffs' else None}
    return {'phase': 'offseason', 'season': previous['season'] if previous else None,
            'week': None, 'dailyDate': None, 'weeklyWeek': None, 'weeklyFirst': False,
            'standingsWeek': previous['regularWeeks'] if previous else None,
            'playoffKey': 'final' if previous else None}


def normalize_calendar(weeks, end):
    """Recover no-game boundary days from the observed weekly cadence.

    ESPN pointsByScoringPeriod omits team-days with no scoring. Infer the normal
    boundary weekday from the season's observed starts, never a fixed Monday.
    Keep the actual first season day and ESPN's terminal period date.
    """
    from collections import Counter
    from datetime import timedelta
    if len(weeks) < 2:
        return weeks
    weekday = Counter(date.fromisoformat(w['start']).weekday() for w in weeks[1:]).most_common(1)[0][0]
    result = [dict(w) for w in weeks]
    for i, week in enumerate(result):
        if i:
            start = date.fromisoformat(week['start'])
            offset = (start.weekday()-weekday) % 7
            week['start'] = (start-timedelta(days=offset)).isoformat()
            week['firstPeriod'] -= offset
    for i, week in enumerate(result):
        next_start = date.fromisoformat(result[i+1]['start']) if i+1<len(result) else date.fromisoformat(end)+timedelta(days=1)
        last = next_start-timedelta(days=1)
        original_end = date.fromisoformat(week['end'])
        week['lastPeriod'] += (last-original_end).days
        week['end'] = last.isoformat()
    return result
