"""Team FP/Start from credited games, independently checked against saved exports.

ESPN's frozen scoreboard points can differ from its corrected player stats.
They remain an audit reference, never a replacement player-scoring numerator.
Bye-week roster games do not count toward a fantasy matchup.
"""
import math

from playerDailyAggregation import DAILY_KEY, attach_matchup_weeks, credited_daily_rows


def combine_performance(metrics):
    metrics = list(metrics)
    available = bool(metrics) and all(item['available'] for item in metrics)
    points = sum(item['fpts'] for item in metrics)
    starts = sum(item['starts'] for item in metrics) if available else None
    return {'fpts': points, 'starts': starts, 'available': available,
            'fpPerStart': round(points / starts, 2) if starts else None,
            'reason': None if available else 'Credited player-game coverage could not be verified.'}


def team_performance(daily, mapping, metadata, league, player_weekly=None):
    """Key by (season, team ID); only scored matchup rows define the scope.

    Reconcile credited FPTS to an independent saved weekly-player or ESPN daily
    score reference, or to the scoreboard. Keep exact comparisons; do not widen
    tolerance to paper over missing games. Any missing/ambiguous coverage
    invalidates broader scopes. A verified 0/0 week has no rate but can be summed.
    """
    observed = attach_matchup_weeks(daily, mapping)
    rows = observed
    duplicate_keys = rows[rows.duplicated(list(DAILY_KEY), keep=False)]
    rows = credited_daily_rows(rows.drop_duplicates(list(DAILY_KEY)), metadata)
    references = {}
    for season in metadata.get('seasons', []):
        for match in season.get('matchups', []):
            for side in match.get('sides', []):
                values = side.get('pointsByPeriod', {})
                if values:
                    references[(int(season['season']), int(match['week']), int(side['teamId']))] = sum(float(value) for value in values.values())
    weekly_refs = {}
    if player_weekly is not None:
        for key, group in player_weekly.groupby(['Year', 'Week', 'Team ID']):
            if not group.duplicated(['Player ID']).any() and group['FPTS'].notna().all():
                weekly_refs[tuple(map(int, key))] = group.set_index('Player ID')['FPTS']
    output = {}
    for (year, team_id), matches in league.groupby(['Year', 'Team ID']):
        weeks = {}
        for week, scores in matches.groupby('Week'):
            games = rows[(rows['Year'] == year) & (rows['Team ID'] == team_id) & (rows['Week'] == week)]
            duplicates = duplicate_keys[(duplicate_keys['Year'] == year) & (duplicate_keys['Team ID'] == team_id) & (duplicate_keys['Week'] == week)]
            recorded = float(scores['Points For'].sum())
            key = (int(year), int(week), int(team_id))
            team_rows = observed[(observed['Year'] == year) & (observed['Team ID'] == team_id) & (observed['Week'] == week)]
            bye = len(scores) == 1 and 'Type' in scores and scores.iloc[0]['Type'] == 'Bye'
            observed_points = float(games['FPTS'].sum())
            observed_starts = len(games)
            points = 0.0 if bye else float(games['FPTS'].sum())
            weekly_reference = weekly_refs.get(key)
            # A matching team sum alone must not hide offsetting missing or
            # misattributed players in the independent weekly-player reference.
            weekly_points = None
            if weekly_reference is not None:
                actual = games.groupby('Player ID')['FPTS'].sum()
                actual, expected = actual.align(weekly_reference, fill_value=0)
                if all(math.isclose(float(a), float(b), abs_tol=.01, rel_tol=0) for a, b in zip(actual, expected)):
                    weekly_points = float(weekly_reference.sum())
            evidence = [('scoreboard', recorded), ('weekly-player-stats', weekly_points),
                        ('saved-espn-daily-scores', references.get(key))]
            verified_by = next((name for name, value in evidence if value is not None and
                                math.isclose(points, value, abs_tol=.01, rel_tol=0)), None)
            known_slots = set(next((s['lineupSlots'] for s in metadata['seasons'] if int(s['season']) == int(year)), [])) | {'BE', 'IR'}
            valid_rows = (not team_rows.empty and team_rows['Player Slot'].isin(known_slots).all()
                          and team_rows[['MIN', 'FPTS']].notna().all().all())
            available = bool(bye or (len(scores) == 1 and duplicates.empty and valid_rows and verified_by))
            if bye:
                games = games.iloc[:0]
                verified_by = 'bye-excluded'
            starts = len(games) if available else None
            weeks[str(int(week))] = {'fpts': points, 'starts': starts, 'available': available,
                                    'fpPerStart': round(points / starts, 2) if starts else None,
                                    'recordedFpts': recorded, 'scoreDelta': round(points - recorded, 4),
                                    'observedFpts': observed_points, 'observedStarts': observed_starts,
                                    'previouslyAvailable': bool(len(scores) == 1 and duplicates.empty and not games.empty
                                        and math.isclose(observed_points, recorded, abs_tol=.01, rel_tol=0)),
                                    'verifiedBy': verified_by if available else None,
                                    'coverage': 'bye-excluded' if bye else 'verified-zero-starts' if available and not starts else 'verified' if available else 'unverified'}
        output[(int(year), int(team_id))] = {'weeks': weeks, 'season': combine_performance(weeks.values())}
    return output


def performance_audit(performance):
    """Season coverage and exact unresolved weeks, without changing source data."""
    seasons = []
    for year in sorted({key[0] for key in performance}):
        teams = [(team, data) for (season, team), data in performance.items() if season == year]
        weeks = [(team, int(week), metric) for team, data in teams for week, metric in data['weeks'].items()]
        seasons.append({'season': year, 'teams': len(teams),
            'availableTeams': sum(data['season']['available'] for _, data in teams),
            'previouslyAvailableTeams': sum(all(metric['previouslyAvailable'] for metric in data['weeks'].values()) for _, data in teams),
            'recordedTeamWeeks': len(weeks),
            'previouslyAvailableTeamWeeks': sum(metric['previouslyAvailable'] for _, _, metric in weeks),
            'verifiedTeamWeeks': sum(metric['available'] for _, _, metric in weeks),
            'byeWeeksExcluded': sum(metric['coverage'] == 'bye-excluded' for _, _, metric in weeks),
            'verifiedZeroStartWeeks': sum(metric['coverage'] == 'verified-zero-starts' for _, _, metric in weeks),
            'eligibleFpts': sum(metric['fpts'] for _, _, metric in weeks),
            'starts': sum(metric['starts'] or 0 for _, _, metric in weeks),
            'scoreDifferences': [{'teamId': team, 'week': week, 'recordedFpts': metric['recordedFpts'],
                                 'eligibleFpts': metric['fpts'], 'delta': metric['scoreDelta'], 'verifiedBy': metric['verifiedBy']}
                                for team, week, metric in weeks if metric['scoreDelta']],
            'unavailableWeeks': [{'teamId': team, 'week': week} for team, week, metric in weeks if not metric['available']]})
    return {'schemaVersion': 1, 'scope': 'Recorded fantasy matchup weeks; bye player-games excluded', 'seasons': seasons}
