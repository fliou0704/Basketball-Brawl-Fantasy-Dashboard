"""Export the validated scheduled calendar; never request ESPN during a build."""
from espnFantasyCalendar import verified, week_ranges, validate
from build_homepage import write_json


def attach(calendars, daily, mapping, output):
    seasons = []
    for season in calendars:
        calendar = verified(season)
        if not calendar:
            continue
        # A cached calendar must still agree with the exact exported snapshot.
        # If a new observation disagrees, suppress only this optional calendar.
        try:
            validate(calendar, season.get('fantasyCalendarContext'), daily, mapping)
        except ValueError:
            continue
        seasons.append({'season': season['season'], 'verified': True,
                        'source': calendar['source'], 'verifiedAt': calendar['verifiedAt'],
                        'days': calendar['days'], 'weeks': week_ranges(calendar)})
    payload = {'schemaVersion': 1, 'seasons': seasons}
    write_json(output / 'fantasy-calendar.json', payload)
    return {s['season']: s for s in seasons}
