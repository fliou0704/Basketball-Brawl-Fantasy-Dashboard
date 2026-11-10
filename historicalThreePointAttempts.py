"""Bounded raw-stat enrichment; preserve every historical scoring/roster field."""
import math


def recover_attempts(daily, year, raw):
    """Only explicit raw 3PA, matched by player/period AND saved FPTS/minutes."""
    samples = {}
    conflicts = set()
    for item in raw.get('players', []):
        player = item.get('player', item)
        for game in player.get('stats', []):
            if game.get('seasonId') != year or game.get('statSourceId') != 0 or game.get('statSplitTypeId') != 5:
                continue
            stats = game.get('stats', {})
            value = stats.get('18')
            if value is None or not isinstance(value, (int,float)) or not math.isfinite(value) or value < 0 or value != int(value):
                continue
            key = (int(player['id']), int(game['scoringPeriodId']))
            sample = (float(game.get('appliedTotal', float('nan'))), float(stats.get('40', float('nan'))), int(value))
            if key in samples and samples[key] != sample:
                conflicts.add(key)
            samples[key] = sample
    result = daily.copy()
    if '3PA' not in result:
        result['3PA'] = float('nan')
    count = 0
    for index, row in result[(result['Year']==year) & result['3PA'].isna()].iterrows():
        key = (int(row['Player ID']), int(row['Scoring Period']))
        sample = samples.get(key)
        if key in conflicts or sample is None:
            continue
        fpts, minutes, attempts = sample
        if math.isclose(float(row['FPTS']),fpts,abs_tol=.01,rel_tol=0) and math.isclose(float(row['MIN']),minutes,abs_tol=.01,rel_tol=0):
            result.at[index,'3PA'] = attempts
            count += 1
    return result, count


def refresh_missing_attempts(daily, metadata, current_year, request, now):
    """At most one bulk request per old season, recorded to prevent repeat backfills."""
    report = metadata.setdefault('historical3PARecovery', {})
    for year in sorted(map(int,daily['Year'].unique())):
        if year >= current_year or str(year) in report:
            continue
        missing = daily[(daily['Year']==year) & daily['3PA'].isna()]
        if missing.empty:
            continue
        try:
            raw = request(year,sorted(map(int,missing['Player ID'].unique())))
            if not isinstance(raw.get('players'),list):
                raise ValueError('Missing bulk player stats')
            daily, count = recover_attempts(daily,year,raw)
            report[str(year)] = {'checkedAt':now.isoformat(),'recoveredRows':count,
                'source':'ESPN bulk actual game stats, raw stat 18; FPTS/MIN matched',
                'unavailableRows':int(daily.loc[daily['Year']==year,'3PA'].isna().sum())}
        except Exception:
            report[str(year)] = {'checkedAt':now.isoformat(),'error':'Historical raw 3PA unavailable; no stats inferred.'}
    return daily
