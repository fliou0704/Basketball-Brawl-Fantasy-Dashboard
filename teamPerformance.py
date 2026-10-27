"""Reusable team FP/Start, reconciled against recorded fantasy matchup scores."""
import math

from playerDailyAggregation import DAILY_KEY, attach_matchup_weeks, credited_daily_rows


def combine_performance(metrics):
    metrics = list(metrics)
    available = bool(metrics) and all(item['available'] for item in metrics)
    points = sum(item['fpts'] for item in metrics)
    starts = sum(item['starts'] for item in metrics) if available else None
    return {'fpts': points, 'starts': starts, 'available': available,
            'fpPerStart': round(points / starts, 2) if starts else None,
            'reason': None if available else 'Credited player-game coverage does not reconcile with matchup scores.'}


def team_performance(daily, mapping, metadata, league):
    """Key by (season, team ID); only scored matchup rows define the scope.

    Reconcile every week's active played-game FPTS to its authoritative team
    score. Any missing/ambiguous rows invalidate that denominator and all broader
    scopes containing it. No partial-history rate is presented as a full rate.
    """
    rows = attach_matchup_weeks(daily, mapping)
    duplicate_keys = rows[rows.duplicated(list(DAILY_KEY), keep=False)]
    rows = credited_daily_rows(rows.drop_duplicates(list(DAILY_KEY)), metadata)
    output = {}
    for (year, team_id), matches in league.groupby(['Year', 'Team ID']):
        weeks = {}
        for week, scores in matches.groupby('Week'):
            games = rows[(rows['Year'] == year) & (rows['Team ID'] == team_id) & (rows['Week'] == week)]
            duplicates = duplicate_keys[(duplicate_keys['Year'] == year) & (duplicate_keys['Team ID'] == team_id) & (duplicate_keys['Week'] == week)]
            points = float(scores['Points For'].sum())
            available = (len(scores) == 1 and duplicates.empty and not games.empty
                         and games['FPTS'].notna().all()
                         and math.isclose(float(games['FPTS'].sum()), points, abs_tol=.01, rel_tol=0))
            starts = len(games) if available else None
            weeks[str(int(week))] = {'fpts': points, 'starts': starts, 'available': available,
                                    'fpPerStart': round(points / starts, 2) if starts else None}
        output[(int(year), int(team_id))] = {'weeks': weeks, 'season': combine_performance(weeks.values())}
    return output
