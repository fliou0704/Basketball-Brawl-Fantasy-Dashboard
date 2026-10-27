"""Export browseable ESPN assignments and actual scores; no projection inputs."""
import json
from datetime import date, timedelta
from pathlib import Path

from build_homepage import display, logo_config, read_csv, team_info, write_json


def observed_dates(calendar, selected, period_map):
    """Validate retained observations without completing missing endpoints."""
    saved = next((w for w in calendar.get('weeks', []) if int(w['week']) == selected), {})
    try:
        first, last = int(saved['firstPeriod']), int(saved['lastPeriod'])
        origin = date.fromisoformat(calendar['dateAnchor'])
        known = {p for p, week in period_map.items() if week == selected}
        if (not known or first != min(known) or last != max(known)
                or first < calendar.get('firstPeriod', 1) or last > calendar['finalPeriod']
                or any(period_map.get(p, selected) != selected for p in range(first, last + 1))
                or saved['start'] != (origin + timedelta(days=first)).isoformat()
                or saved['end'] != (origin + timedelta(days=last)).isoformat()):
            return {}
        return {k: saved[k] for k in ('firstPeriod', 'lastPeriod', 'start', 'end')}
    except (KeyError, ValueError, TypeError, OverflowError):
        return {}


def project(current, calendars, mapping, league, config, scheduled=None):
    scheduled = scheduled or {}
    year, period = int(current['season']), int(current['scoringPeriod'])
    mapped = {int(r['Scoring Period']): int(r['Week']) for r in mapping if int(r['Year']) == year}
    # ESPN status remains authoritative on day one, before any performance rows.
    week = mapped.get(period, int(current['week']))
    if period in mapped and week != int(current['week']):
        raise ValueError('ESPN status and scoring-period mapping disagree')
    payload = {'schemaVersion': 1, 'current': {'season': year, 'week': week, 'scoringPeriod': period}, 'updatedAt': current.get('updatedAt'), 'seasons': []}
    for calendar in sorted(calendars, key=lambda c: c['season']):
        season = int(calendar['season'])
        rows = [r for r in league if int(r['Year']) == season]
        identities = {int(r['Team ID']): team_info(r, config) for r in rows}
        identities.update({int(r['Team ID']): team_info(r, config) for r in calendar.get('teams', [])})
        if season == year:
            identities.update({int(t['teamId']): team_info({'Team ID': t['teamId'], 'Team Name': t['teamName']}, config) for t in current['teams']})
            payload['current']['asOfDate'] = (date.fromisoformat(calendar['dateAnchor']) + timedelta(days=period)).isoformat()
        # Ignore legacy scheduledWeeks: db225a0 misread weekly IDs as daily IDs.
        # Completed observations are useful history, never future boundaries.
        assignments = calendar['matchups']
        verified_calendar = scheduled.get(season, {})
        scheduled_ranges = {w['week']: w for w in verified_calendar.get('weeks', [])}
        numbers = sorted(set(scheduled_ranges) | ({week} if season == year else set()) | {int(w['week']) for w in calendar['weeks']} | {int(m['week']) for m in assignments} | {int(r['Week']) for r in rows})
        exported = []
        for selected in numbers:
            state = 'final' if season < year or (season == year and selected < week) else 'current' if season == year and selected == week else 'future'
            period_map = {int(r['Scoring Period']): int(r['Week']) for r in mapping if int(r['Year']) == season}
            results = {int(r['Team ID']): r for r in rows if int(r['Week']) == selected}
            # The existing updater writes the terminal week's canonical results
            # only once ESPN has completed the season; status can retain that week.
            if state == 'current' and period >= calendar['finalPeriod'] and results:
                state = 'final'
            dates = scheduled_ranges.get(selected) or (observed_dates(calendar, selected, period_map) if state == 'final' else {})
            matches = []
            for match in assignments:
                if int(match['week']) != selected:
                    continue
                sides = match['sides']
                if not sides or len(sides) > 2 or any(int(s['teamId']) not in identities for s in sides):
                    continue
                ids = [int(s['teamId']) for s in sides]
                single = len(sides) == 1
                bye = single and results.get(ids[0], {}).get('Type') == 'Bye'
                scores = None
                if not single and state == 'final':
                    # Canonical historical totals, without recalculating scoring.
                    if all(t in results and results[t]['Points For'] != '' for t in ids) and all(int(float(results[t].get('Opponent Team ID') or -1)) == ids[1-i] for i,t in enumerate(ids)):
                        scores = [float(results[t]['Points For']) for t in ids]
                elif not single and state == 'current':
                    scores = [sum(float(v) for p,v in side['pointsByPeriod'].items() if int(p) <= period and period_map.get(int(p)) == selected) for side in sides]
                winner = ids[scores.index(max(scores))] if state == 'final' and scores and scores[0] != scores[1] else None
                matches.append({'id': match['id'], 'teams': [identities[t] for t in ids], 'bye': bye,
                                'status': 'bye' if bye else 'opponent-unavailable' if single else state if scores is not None or state == 'future' else 'unavailable',
                                'actualScores': scores, 'scoreDisplay': list(map(display, scores)) if scores is not None else None,
                                'winnerId': winner})
            # Old exports may have canonical results but no retained ESPN schedule.
            if not matches and state == 'final':
                seen = set()
                for t,r in results.items():
                    opponent = int(float(r['Opponent Team ID'])) if r['Opponent Team ID'] else None
                    if t in seen or t not in identities or (opponent and opponent not in identities):
                        continue
                    ids = [t,opponent] if opponent else [t]
                    if opponent and opponent not in results:
                        continue
                    seen.update(ids)
                    bye = r['Type'] == 'Bye'
                    if not opponent and not bye:
                        continue
                    scores = [float(results[i]['Points For']) for i in ids] if not bye else None
                    matches.append({'id': f'archive-{t}', 'teams': [identities[i] for i in ids], 'bye': bye,
                                    'status': 'bye' if bye else 'final', 'actualScores': scores,
                                    'scoreDisplay': list(map(display,scores)) if scores else None,
                                    'winnerId': ids[scores.index(max(scores))] if scores and scores[0] != scores[1] else None})
            exported.append({'week': selected, 'phase': 'playoffs' if selected > calendar['regularWeeks'] else 'regular',
                             'state': state, 'start': dates.get('start'), 'end': dates.get('end'),
                             'firstPeriod': dates.get('firstPeriod'), 'lastPeriod': dates.get('lastPeriod'),
                             'dateRangeKind': 'scheduled' if selected in scheduled_ranges else 'observed' if dates else 'unavailable',
                             'dateRangeSource': verified_calendar.get('source') if selected in scheduled_ranges else 'seasonMetadata.weeks+canonical-period-map' if dates else None,
                             'calendarPartial': selected not in scheduled_ranges, 'matchups': matches})
        payload['seasons'].append({'season': season, 'weeks': exported, 'unpublishedPlayoffs': not any(w['phase'] == 'playoffs' and w['matchups'] for w in exported)})
    return payload


def attach_recaps(payload, output):
    # Reuse the Home exporter; retain recaps only for played, completed weeks.
    for season in payload['seasons']:
        path = output / str(season['season']) / 'weekly-recap.json'
        recaps = json.loads(path.read_text())['data'] if path.exists() else {}
        for week in season['weeks']:
            week['recap'] = recaps.get(str(week['week'])) if (
                week['state'] == 'final' and any(m['status'] == 'final' for m in week['matchups'])) else None


def build(source, output):
    current = json.loads((source / 'currentLeague.json').read_text())
    calendars = json.loads((source / 'seasonMetadata.json').read_text())['seasons']
    mapping = read_csv(source / 'scoringPeriodMatchupMap.csv')
    from generate_fantasy_calendar import attach
    daily = read_csv(source / 'playerDailyData.csv')
    scheduled = attach(calendars, daily, mapping, output)
    payload = project(current, calendars, mapping, read_csv(source / 'basketballBrawlLeagueData.csv'), logo_config(), scheduled)
    # Enrich daily labels only; observed period membership and scores stay intact.
    calendars = [dict(c, scheduledDates={d['period']: d['date'] for d in scheduled.get(c['season'], {}).get('days', [])}) for c in calendars]
    from generate_matchup_details import build_details
    build_details(payload, calendars, current, mapping, daily, output)
    attach_recaps(payload, output)
    write_json(output / 'scoreboard.json', payload)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    build(root / 'data', root / 'frontend/public/data')
