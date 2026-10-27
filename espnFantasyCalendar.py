"""Public ESPN calendar discovery and a repository-persisted daily cache.

No authenticated responses or remote JavaScript execution. Observations remain
separate; callers publish this optional cache with their staged metadata writes.
"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import re
import time
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

PAGE = 'https://fantasy.espn.com/basketball/league/scoreboard'
SOURCE = 'ESPN public fantasy constants + league matchupPeriods'
NY = ZoneInfo('America/New_York')
INTERVAL = timedelta(hours=24)


class CalendarError(ValueError):
    """Safe messages contain schema/period diagnostics, never HTTP details."""


def integer(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CalendarError('invalid calendar identifier')
    return value


def context(raw):
    settings = raw['settings']['scheduleSettings']
    return {'season': int(raw['seasonId']), 'segmentId': int(raw['segmentId']),
            'periodTypeId': int(settings['periodTypeId']),
            'firstPeriod': int(raw['status']['firstScoringPeriod']),
            'finalPeriod': int(raw['status']['finalScoringPeriod']),
            'regularWeeks': int(settings['matchupPeriodCount']),
            'matchupPeriods': settings['matchupPeriods']}


def validate(calendar, expected=None, daily=(), mapping=(), through=0, previous=None):
    """Validate normalized rows, league coverage, observations, and frozen past."""
    try:
        if calendar['schemaVersion'] != 1 or calendar['source'] != SOURCE:
            raise CalendarError('unsupported calendar schema or source')
        ctx = calendar['context']
        if expected is not None and ctx != expected:
            raise CalendarError('calendar league configuration changed')
        year = integer(ctx['season'])
        first, last = integer(ctx['firstPeriod']), integer(ctx['finalPeriod'])
        if not 1 <= first <= last <= 500:
            raise CalendarError('invalid calendar season limits')
        rows = calendar['days']
        if [integer(r['period']) for r in rows] != list(range(first, last + 1)):
            raise CalendarError('calendar periods missing, duplicated, or unordered')
        dates = [date.fromisoformat(r['date']) for r in rows]
        if dates[0].year not in (year - 1, year) or dates[-1].year not in (year - 1, year):
            raise CalendarError('calendar dates fall outside fantasy season')
        if any(d.isoformat() != r['date'] for d, r in zip(dates, rows)) or any(
                b != a + timedelta(days=1) for a, b in zip(dates, dates[1:])):
            raise CalendarError('calendar dates are not consecutive civil days')
        weeks = [integer(r['week']) for r in rows]
        configured = sorted(int(w) for w in ctx['matchupPeriods'])
        if sorted(set(weeks)) != configured or weeks != sorted(weeks) or configured != list(range(1, max(configured) + 1)):
            raise CalendarError('calendar matchup coverage or ordering invalid')
        if not 1 <= integer(ctx['regularWeeks']) <= len(configured):
            raise CalendarError('invalid regular-season matchup count')
        lookup = {r['period']: r for r in rows}
        for r in daily:
            if int(r['Year']) == year and (int(r['Scoring Period']) not in lookup or
                    lookup[int(r['Scoring Period'])]['date'] != str(r['Date'])):
                raise CalendarError(f'calendar conflicts with observed date in season {year}')
        for r in mapping:
            if int(r['Year']) == year and (int(r['Scoring Period']) not in lookup or
                    lookup[int(r['Scoring Period'])]['week'] != int(r['Week'])):
                raise CalendarError(f'calendar conflicts with observed matchup in season {year}')
        if previous:
            for r in previous.get('days', []):
                if r['period'] <= through and lookup.get(r['period']) != r:
                    raise CalendarError(f'calendar would change verified history at period {r["period"]}')
        return calendar
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, CalendarError):
            raise
        raise CalendarError('malformed calendar schema or date') from None


def normalize(constants, ctx):
    try:
        if constants['seasonConfig'] != ctx['season']:
            raise CalendarError('wrong ESPN calendar season')
        segment = next(s for s in constants['segments'] if s['id'] == ctx['segmentId'])
        kind = next(t for t in segment['periodTypes'] if t['id'] == ctx['periodTypeId'])
        bases = kind['periods']
        if len({integer(b['id']) for b in bases}) != len(bases):
            raise CalendarError('duplicate base period')
        base = {b['id']: b for b in bases}
        daily = constants['scoringPeriods']
        if len({integer(d['id']) for d in daily}) != len(daily):
            raise CalendarError('duplicate daily period')
        days = {}
        for d in daily:
            if not ctx['firstPeriod'] <= d['id'] <= ctx['finalPeriod']:
                continue
            if d['preSeason'] is not False or d['postSeason'] is not False:
                raise CalendarError('non-daily sentinel inside league calendar')
            start, end = d['startDate'], d['endDate']
            if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or not 0 < start < end:
                raise CalendarError('invalid calendar timestamp')
            # Rollover timestamps are not tipoff times. Period 1 starts in the
            # offseason; end boundary minus one NY civil day is its date label.
            days[d['id']] = (datetime.fromtimestamp(end / 1000, NY).date() - timedelta(days=1)).isoformat()
        rows = []
        for w, ids in sorted(ctx['matchupPeriods'].items(), key=lambda p: int(p[0])):
            if not ids or len(set(ids)) != len(ids):
                raise CalendarError('empty or duplicate matchup base periods')
            periods = []
            for b in ids:
                definition = base[integer(b)]
                a, z = integer(definition['scoringPeriodStart']), integer(definition['scoringPeriodEnd'])
                if not 1 <= a <= z <= 500:
                    raise CalendarError('invalid matchup boundaries')
                periods.extend(range(max(a, ctx['firstPeriod']), min(z, ctx['finalPeriod']) + 1))
            if not periods or periods != list(range(min(periods), max(periods) + 1)):
                raise CalendarError('noncontiguous or overlapping matchup boundaries')
            rows.extend({'period': p, 'date': days[p], 'week': int(w)} for p in periods)
        return validate({'schemaVersion': 1, 'context': deepcopy(ctx), 'source': SOURCE, 'days': rows})
    except (KeyError, TypeError, ValueError, StopIteration, OverflowError, OSError):
        raise CalendarError('invalid ESPN calendar constants or league grouping') from None


def _literal(text, start):
    """Read JSON-like literal arrays from archived bundles; never eval code."""
    stack, quoted, escaped = [], None, False
    for j in range(start, len(text)):
        c = text[j]
        if quoted:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == quoted:
                quoted = None
        elif c in ('"', "'"):
            quoted = c
        elif c in '[{':
            stack.append(c)
        elif c in ']}':
            stack.pop()
            if not stack:
                return json.loads(re.sub(r'([{,])([A-Za-z_$][\w$]*):', r'\1"\2":', text[start:j+1]))
    raise CalendarError('unterminated ESPN literal')


def _get(url):
    import requests  # Existing updater dependency; offline exporters need only stdlib.
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('fantasy.espn.com', 'cdn1.espn.net'):
        raise CalendarError('unexpected ESPN asset origin')
    for attempt in range(2):
        try:
            response = requests.get(url, timeout=(10, 30))
            if response.status_code != 200:
                raise CalendarError(f'public calendar HTTP {response.status_code}')
            if len(response.content) > 16_000_000:
                raise CalendarError('oversized ESPN calendar response')
            return response.text
        except (requests.RequestException, CalendarError):
            if attempt:
                raise CalendarError('public calendar request failed') from None
            time.sleep(1)


def discover(season):
    """Current: one public HTML GET. Archives: bounded loader + one chunk."""
    try:
        html = _get(PAGE)
        marker = re.search(r'__NEXT_DATA__\s*=\s*', html)
        if not marker:
            raise CalendarError('ESPN bootstrap missing')
        bootstrap, _ = json.JSONDecoder().raw_decode(html[marker.end():])
        config = bootstrap['props']['pageProps']['page']['config']
        constants = config['constants']
        if constants['seasonConfig'] == season:
            return constants, PAGE
        # ESPN's loader names historical modules by season and version. Discover
        # paths from the current loader instead of pinning expiring asset hashes.
        scripts = re.findall(r'<script[^>]+src=["\x27]([^"\x27]+)', html)
        url = next(urljoin(PAGE, s) for s in scripts if '/commons/main-' in s)
        main = _get(url)
        match = re.search(r'(\d+):"(chunks/modules_api_lm_seasons_fba_' + str(int(season)) + r'_[0-9a-f]+)"', main)
        if not match:
            raise CalendarError('ESPN historical season not published')
        digest = re.search(r'\b' + match[1] + r':"([0-9a-f]{20})"', main)
        if not digest:
            raise CalendarError('ESPN historical loader changed')
        asset = url.split('/_next/')[0] + '/_next/webpack/' + match[2] + '-' + digest[1] + '.js'
        chunk = _get(asset)
        result = {'seasonConfig': season}
        for m in re.finditer(r'\w\.exports=(\[\{(?:endDate|id):)', chunk):
            value = _literal(chunk, m.start(1))
            if value and 'preSeason' in value[0]:
                result['scoringPeriods'] = value
            if value and 'periodTypes' in value[0]:
                result['segments'] = value
        return result, asset
    except (KeyError, ValueError, TypeError, StopIteration, IndexError):
        raise CalendarError('ESPN public calendar schema changed') from None


def stamp(value):
    if not isinstance(value, str):
        raise CalendarError('invalid calendar verification time')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise CalendarError('calendar verification time must include timezone')
    return parsed.astimezone(timezone.utc)


def refresh(previous, ctx, daily=(), mapping=(), through=0, now=None, force=False, fetch=discover, log=print):
    """Return a candidate only. Its metadata commit persists both cooldowns.

    Failures never advance verifiedAt or replace days. A separate lastAttemptAt
    throttles failed initialization as well as failures with an existing cache.
    """
    import requests
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise CalendarError('refresh clock must include timezone')
    if not isinstance(previous, dict):
        previous = None
    if previous and isinstance(previous.get('context'), dict) and previous['context']['season'] != ctx['season']:
        previous = None
    result = deepcopy(previous or {})
    if not force:
        for key in ('lastAttemptAt', 'verifiedAt'):
            try:
                if now - stamp(result[key]) < INTERVAL:
                    log('Fantasy calendar: cached; next check after 24-hour cooldown.')
                    return result
            except (KeyError, TypeError, ValueError):
                pass
    attempted = now.astimezone(timezone.utc).isoformat()
    result['lastAttemptAt'] = attempted
    try:
        constants, url = fetch(ctx['season'])
        candidate = normalize(constants, ctx)
        validate(candidate, ctx, daily, mapping, through, previous)
        old = {r['period']: r for r in (previous or {}).get('days', [])}
        new = {r['period']: r for r in candidate['days']}
        differences = [{'period': p, 'before': old.get(p), 'after': new.get(p)}
                       for p in sorted(set(old) | set(new)) if old.get(p) != new.get(p)]
        changed_weeks = sorted({r[key]['week'] for r in differences
                                for key in ('before', 'after') if r[key]})
        log(f'Fantasy calendar: accepted {len(candidate["days"])} days; {len(differences)} changed dates/memberships; affected weeks {changed_weeks}.')
        if differences and old:
            log('Fantasy calendar changes: ' + json.dumps(differences[:12], sort_keys=True))
        return dict(candidate, sourceUrl=url, verifiedAt=attempted, lastAttemptAt=attempted)
    except (CalendarError, requests.RequestException) as error:
        # Only our safe validation messages may enter logs or persisted state.
        reason = str(error) if isinstance(error, CalendarError) else 'public calendar network failure'
        result['lastError'] = reason
        log(f'Fantasy calendar: refresh rejected ({reason}); last known-good calendar retained.')
        return result


def verified(season):
    """Validated, configuration-matching cache or None; usable while stale."""
    value = season.get('fantasyCalendar')
    if not isinstance(value, dict) or not value.get('verifiedAt'):
        return None
    try:
        stamp(value['verifiedAt'])
        validate(value, season.get('fantasyCalendarContext'))
        if value['context']['season'] != season['season']:
            return None
        return value
    except (CalendarError, ValueError, TypeError):
        return None


def week_ranges(calendar):
    result = []
    for r in calendar['days']:
        if not result or result[-1]['week'] != r['week']:
            result.append({'week': r['week'], 'firstPeriod': r['period'],
                           'lastPeriod': r['period'], 'start': r['date'], 'end': r['date']})
        else:
            result[-1].update(lastPeriod=r['period'], end=r['date'])
    return result
