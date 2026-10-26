"""Stage, validate, and publish bounded ESPN updates. No full-history rebuilds."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import traceback
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from espn_api.basketball import League
from espn_api.basketball.constant import POSITION_MAP, STATS_MAP
from espn_api.requests.espn_requests import ESPNInvalidLeague, ESPNUnknownError

from activityDataUpdater import build_activity_candidate, validate_activity, draft_is_complete
from dataUpdateSafety import (DataValidationError, PLAYER_DAILY_KEY, LEAGUE_KEY,
    PLAYER_MATCHUP_KEY, atomic_write_csv, require_espn_credentials,
    validate_league_data, validate_player_daily_data, validate_player_matchup_data)
from leagueDataUpdater import update_league_data
from playerMatchupDataUpdater import update_playerMatchup_data
from playerDailyDataUpdater import available_scoring_period, fetch_daily_rows, with_raw_three_point_attempts
from playerDailyAggregation import build_scoring_period_map, validate_scoring_period_map
from playerMetadataUpdater import update_player_metadata
from scoreboardCalendar import scheduled_weeks, dated_snapshot
from nearLiveSafety import refresh_start, replace_partitions, changes, change_details

ROOT = Path(__file__).resolve().parent
KEYS = {'basketballBrawlLeagueData.csv': LEAGUE_KEY, 'playerMatchupData.csv': PLAYER_MATCHUP_KEY,
        'playerDailyData.csv': PLAYER_DAILY_KEY,
        'activityData.csv': ['Year', 'Date', 'Time', 'Team ID', 'Player ID', 'Action']}


def retry(call):
    for attempt in range(3):
        try:
            return call()
        except (requests.ConnectionError, requests.Timeout, ESPNUnknownError):
            if attempt == 2:
                raise RuntimeError('ESPN connection failed after three attempts') from None
            time.sleep(2 ** attempt)
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else None
            if status not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f'ESPN HTTP {status}') from None
            time.sleep(2 ** attempt)


class LeagueCache:
    """Reuse league construction, scoreboards, and daily boxes during one run."""
    def __init__(self):
        self.leagues = {}

    def __call__(self, league_id, year, **kwargs):
        year = int(year)
        if year not in self.leagues:
            league = retry(lambda: League(league_id=league_id, year=year, **kwargs))
            for name in ('box_scores', 'scoreboard'):
                method = getattr(league, name)
                cache = {}
                def cached(*args, _method=method, _cache=cache, **kw):
                    key = (args, tuple(sorted(kw.items())))
                    if key not in _cache:
                        _cache[key] = retry(lambda: _method(*args, **kw))
                    return _cache[key]
                setattr(league, name, cached)
            self.leagues[year] = league
        return self.leagues[year]


def atomic_json(payload, path):
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return False
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(text)
    os.replace(temporary, path)
    return True


def current_calendar(league, daily, previous, refresh_from=None):
    """Store allowlisted settings and observed boundaries, never invent future weeks."""
    raw = retry(lambda: league.espn_request.league_get(params={'view': ['mSettings', 'mMatchupScore', 'mTeam']}))
    league._brawl_raw = raw
    year = int(league.year)
    old = next((s for s in previous['seasons'] if int(s['season']) == year), None)
    rows = daily[daily['Year'] == year]
    anchors = {datetime.fromisoformat(str(r['Date'])).date() - timedelta(days=int(r['Scoring Period']))
               for r in rows.to_dict('records')}
    if not anchors and old:
        anchors = {datetime.fromisoformat(old['dateAnchor']).date()}
    if not anchors:
        schedule = retry(league.espn_request.get_pro_schedule)
        observed = [datetime.fromtimestamp(g['date'] / 1000, ZoneInfo('America/New_York')).date()
                    - timedelta(days=int(period))
                    for team in schedule['settings']['proTeams']
                    for period, games in team.get('proGamesByScoringPeriod', {}).items()
                    for g in games if 1 <= int(period) <= int(league.finalScoringPeriod)]
        if not observed:
            raise DataValidationError('ESPN has not published a usable season date anchor')
        anchors = {Counter(observed).most_common(1)[0][0]}
    if len(anchors) != 1:
        raise DataValidationError('inconsistent scoring-period date anchors')
    anchor = anchors.pop()
    periods = {}
    for week in (old or {}).get('weeks', []):
        periods.setdefault(int(week['week']), set()).update(range(week['firstPeriod'], week['lastPeriod'] + 1))
    matches = []
    for match in raw['schedule']:
        week = int(match['matchupPeriodId'])
        sides = []
        for side in ('home', 'away'):
            item = match.get(side, {})
            if not item.get('teamId'):
                continue
            points = {str(int(k)): float(v) for k, v in item.get('pointsByScoringPeriod', {}).items()
                      if int(k) <= int(league.finalScoringPeriod)}
            if old and refresh_from is not None:
                old_match = next((m for m in old['matchups'] if m['id'] == match['id']), None)
                old_side = next((s for s in (old_match or {}).get('sides', []) if s['teamId'] == item['teamId']), None)
                points = {k: v for k, v in points.items() if int(k) >= refresh_from}
                points.update({k: v for k, v in (old_side or {}).get('pointsByPeriod', {}).items() if int(k) < refresh_from})
            periods.setdefault(week, set()).update(map(int, points))
            sides.append({'teamId': item['teamId'], 'pointsByPeriod': points})
        matches.append({'id': match['id'], 'week': week, 'sides': sides})
    # Status authoritatively maps today's period even before its first game.
    periods.setdefault(int(league.currentMatchupPeriod), set()).add(available_scoring_period(league))
    weeks = [{'week': w, 'firstPeriod': min(p), 'lastPeriod': max(p),
              'start': (anchor + timedelta(days=min(p))).isoformat(),
              'end': (anchor + timedelta(days=max(p))).isoformat()} for w, p in sorted(periods.items()) if p]
    settings = raw['settings']
    counts = settings['rosterSettings']['lineupSlotCounts']
    slots = [POSITION_MAP[int(k)] for k, v in counts.items()
             if POSITION_MAP.get(int(k)) not in ('BE', 'IR', '') for _ in range(v)]
    result = {'season': year, 'firstPeriod': int(raw['status']['firstScoringPeriod']),
        'finalPeriod': int(league.finalScoringPeriod), 'regularWeeks': settings['scheduleSettings']['matchupPeriodCount'],
        'playoffTeamCount': settings['scheduleSettings']['playoffTeamCount'], 'dateAnchor': anchor.isoformat(),
        'weeks': weeks, 'lineupSlots': slots, 'benchSlots': sum(v for k, v in counts.items() if POSITION_MAP.get(int(k)) == 'BE'),
        'scoringWeights': {STATS_MAP.get(str(i['statId']), str(i['statId'])): i['points']
                          for i in settings['scoringSettings']['scoringItems']}, 'matchups': matches,
        'teams': [{'Team ID': t.team_id, 'Team Name': t.team_name, 'Team Abbreviation': t.team_abbrev,
                   'Team Owner': t.owners[0]['firstName']} for t in league.teams]}
    result['scheduledWeeks'] = scheduled_weeks(settings['scheduleSettings'], anchor.isoformat(),
                                              result['firstPeriod'], result['finalPeriod'])
    if available_scoring_period(league) < int(league.finalScoringPeriod):
        result['calendarThrough'] = (anchor + timedelta(days=available_scoring_period(league))).isoformat()
    return result


def live_rosters(league):
    """Current membership is a separate snapshot; never assigned to historical rows."""
    records = {int(t['id']): t['record']['overall'] for t in league._brawl_raw['teams']}
    return {'schemaVersion': 1, 'season': int(league.year), 'week': int(league.currentMatchupPeriod),
        'scoringPeriod': available_scoring_period(league),
        'teams': [{'teamId': int(t.team_id), 'teamName': t.team_name, 'abbreviation': t.team_abbrev,
            'owner': t.owners[0]['firstName'], 'wins': int(t.wins), 'losses': int(t.losses),
            'pointsFor': float(records[t.team_id]['pointsFor']), 'pointsAgainst': float(records[t.team_id]['pointsAgainst']),
            'rank': int(t.standing), 'roster': [{'playerId': int(p.playerId), 'name': p.name,
                'eligibility': list(p.eligibleSlots)} for p in t.roster]} for t in league.teams]}


def run(data_dir=ROOT / 'data', write=False):
    started = time.monotonic()
    swid, s2 = require_espn_credentials()
    factory = LeagueCache()
    def get(year):
        return factory(609694684, year, espn_s2=s2, swid=swid)
    now = datetime.now(ZoneInfo('America/New_York'))
    year = now.year + (now.month >= 7)
    try:
        active = get(year)
    except ESPNInvalidLeague:
        active = get(year - 1)
    year = int(active.year)
    complete, _ = retry(lambda: draft_is_complete(active))
    if not complete:
        print(f'ESPN {year} draft is incomplete; saved canonical snapshots retained.')
        return []
    data_dir = Path(data_dir).resolve()
    metadata_path = data_dir / 'seasonMetadata.json'
    metadata = json.loads((metadata_path if metadata_path.exists() else ROOT / 'frontend/source/season-metadata.json').read_text())
    before = {name: pd.read_csv(data_dir / name) for name in KEYS}
    before['playerDailyData.csv'] = with_raw_three_point_attempts(before['playerDailyData.csv'])
    validate_player_daily_data(before['playerDailyData.csv'], source='existing canonical')
    print(f"Daily dates: existing canonical, {len(before['playerDailyData.csv'])} rows, no conflicts", flush=True)
    # A temporary directory holds every candidate. A later failure never promotes
    # a partially updated set of CSVs into the caller's canonical directory.
    with tempfile.TemporaryDirectory(prefix='brawl-update-') as temporary:
        stage = Path(temporary)
        for path in data_dir.glob('*.csv'):
            shutil.copy2(path, stage / path.name)
        daily = before['playerDailyData.csv']
        max_year = int(daily['Year'].max())
        years = list(range(max_year, year + 1))
        partitions, frames, refresh_weeks, starts = set(), [], {}, {}
        for season in years:
            league = get(season)
            available = available_scoring_period(league)
            stored_rows = daily[daily['Year'] == season]
            stored = int(stored_rows['Scoring Period'].max()) if not stored_rows.empty else 0
            old_calendar = next((s for s in metadata['seasons'] if int(s['season']) == season), None)
            # A season already present beside a newer daily season is frozen.
            # During rollover, explicitly reconcile its last seven days once.
            first = refresh_start(stored, available)
            if old_calendar and season == year and stored >= available:
                final_date = datetime.fromisoformat(old_calendar['dateAnchor']).date() + timedelta(days=int(league.finalScoringPeriod))
                if now.date() > final_date + timedelta(days=7):
                    continue
            fetched = fetch_daily_rows(league, season, first, available, daily.columns.tolist())
            validate_player_daily_data(fetched, source=f'fresh ESPN season {season}')
            print(f'Daily dates: fresh ESPN season {season}, periods {first}-{available}, {len(fetched)} rows, no conflicts', flush=True)
            missing = set(stored_rows.loc[stored_rows['Scoring Period'].between(first, available), 'Scoring Period']) - set(fetched['Scoring Period'])
            if missing:
                schedule = retry(league._get_all_pro_schedule)
                for period in missing:
                    if any(games.get(str(int(period))) for games in schedule.values()):
                        raise DataValidationError(f'ESPN omitted all saved player rows for scheduled games in {season} period {int(period)}')
            starts[season] = first
            partitions.update((season, p) for p in range(first, available + 1))
            frames.append(fetched)
            touched = [int(w) for w, periods in league.matchup_ids.items()
                       if any(first <= int(p) <= available for p in periods) and int(w) < int(league.currentMatchupPeriod)]
            if int(league.scoringPeriodId) > int(league.finalScoringPeriod):
                touched += [int(w) for w in league.matchup_ids if int(w) == int(league.currentMatchupPeriod)]
            if touched:
                refresh_weeks[season] = min(touched)
        fetched = pd.concat(frames, ignore_index=True) if frames else daily.iloc[0:0].copy()
        candidate = replace_partitions(daily, fetched, partitions, 'Scoring Period', PLAYER_DAILY_KEY,
                                       lambda rows: validate_player_daily_data(rows, source='merged candidate'))
        # Check terminal completion before adding any later season.
        terminals = {s: int(get(s).finalScoringPeriod) for s in years if s < year}
        validate_player_daily_data(candidate, terminals, source='merged candidate')
        atomic_write_csv(candidate, stage / 'playerDailyData.csv')
        print('Daily authorized partitions:', sorted(partitions))
        print('Daily changes:', changes(daily, candidate, PLAYER_DAILY_KEY))
        update_league_data(stage / 'basketballBrawlLeagueData.csv', year, factory, refresh_weeks)
        update_playerMatchup_data(stage / 'playerMatchupData.csv', year, factory, refresh_weeks)
        # Fetching the current season's transaction partitions preserves delayed
        # events and the explicit manual-trade supplement. Prior seasons freeze.
        for season in years:
            if season != year and season in starts:
                prior = current_calendar(get(season), candidate, metadata, starts[season])
                metadata['seasons'] = [s for s in metadata['seasons'] if int(s['season']) != season] + [prior]
        calendar = current_calendar(active, candidate, metadata, starts.get(year, int(active.finalScoringPeriod) + 1))
        has_activity = bool((before['activityData.csv']['Year'] == year).any())
        activity, _, report = retry(lambda: build_activity_candidate(before['activityData.csv'], active, year,
            pd.read_csv(stage / 'activityTradeSupplement.csv'),
            recent_start=max(1, int(active.scoringPeriodId) - 6) if has_activity else None,
            date_anchor=calendar['dateAnchor']))
        validate_activity(activity)
        atomic_write_csv(activity, stage / 'activityData.csv')
        print('Activity reconciliation:', {k: v for k, v in report.items() if k != 'counts'})
        snapshot = live_rosters(active)
        atomic_json(snapshot, stage / 'currentLeague.json')
        metadata['seasons'] = [s for s in metadata['seasons'] if int(s['season']) != year] + [calendar]
        metadata['seasons'].sort(key=lambda s: int(s['season']))
        atomic_json(metadata, stage / 'seasonMetadata.json')
        mapping = build_scoring_period_map(metadata)
        validate_scoring_period_map(mapping, candidate)
        atomic_write_csv(mapping, stage / 'scoringPeriodMatchupMap.csv')
        # Also discover roster-only newcomers before their first game/action.
        roster_ids = {p['playerId'] for t in snapshot['teams'] for p in t['roster']}
        update_player_metadata(stage, stage / 'playerMetadata.csv', additional_ids=roster_ids)
        validate_league_data(pd.read_csv(stage / 'basketballBrawlLeagueData.csv'))
        validate_player_matchup_data(pd.read_csv(stage / 'playerMatchupData.csv'))
        for name, key in KEYS.items():
            after = pd.read_csv(stage / name)
            print(name, changes(before[name], after, key))
            details = change_details(before[name], after, key)
            if details['corrected'] or details['removedKeys']:
                print('Correction details:', details)
        # Only a fully validated candidate can acquire a data-update timestamp.
        old_snapshot_path = data_dir / 'currentLeague.json'
        old_snapshot = json.loads(old_snapshot_path.read_text()) if old_snapshot_path.exists() else None
        old_calendar = next((s for s in json.loads(metadata_path.read_text())['seasons']
                             if int(s['season']) == year), None) if metadata_path.exists() else None
        snapshot = dated_snapshot(snapshot, calendar, old_snapshot, old_calendar,
                                  datetime.now(timezone.utc).isoformat())
        atomic_json(snapshot, stage / 'currentLeague.json')
        changed = []
        for name in [*KEYS, 'playerMetadata.csv', 'scoringPeriodMatchupMap.csv', 'seasonMetadata.json', 'currentLeague.json']:
            target, source = data_dir / name, stage / name
            if source.suffix == '.csv' and target.exists():
                same = pd.read_csv(target).equals(pd.read_csv(source))
            else:
                same = target.exists() and target.read_bytes() == source.read_bytes()
            if not same:
                changed.append(name)
                if write:
                    if source.suffix == '.csv':
                        atomic_write_csv(pd.read_csv(source), target)
                    else:
                        atomic_json(json.loads(source.read_text()), target)
        print(('UPDATED' if write else 'PREVIEW'), changed, f'in {time.monotonic() - started:.1f}s')
        return changed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    try:
        run(args.data_dir, args.write)
    except Exception as error:
        # Never dump authenticated library exceptions or request details.
        print(f'Update failed: {type(error).__name__}', file=sys.stderr)
        if isinstance(error, DataValidationError):
            # Stack locations only: never expose library/request locals or headers.
            for frame in traceback.extract_tb(error.__traceback__):
                print(f"  {Path(frame.filename).name}:{frame.lineno} in {frame.name}", file=sys.stderr)
        if isinstance(error, DataValidationError) or (isinstance(error, RuntimeError) and str(error).startswith('Missing ESPN credentials')):
            print(str(error), file=sys.stderr)
        sys.exit(1)
