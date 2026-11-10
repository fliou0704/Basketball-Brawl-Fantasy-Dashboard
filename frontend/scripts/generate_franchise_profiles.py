"""Team-only franchise profiles, joined by stable ESPN fantasy team ID."""
import json

import pandas as pd

from build_homepage import logo_config, team_info, write_json
from generate_record_book import completed_season_years, champion_for, season_teams
from generate_team_stats import ordinal
from playerDailyAggregation import load_season_metadata, attach_matchup_weeks, credited_daily_rows, load_scoring_period_map


def trend_chart(history, key, label, rank=False, granular=False):
    rows = sorted(history, key=lambda row: (row['year'], row.get('order', 0)))
    values = [row[key] for row in rows if row[key] is not None]
    maximum = max(max(values, default=1), 1)
    floor = min(min(values, default=0), 0) if not rank else 0
    ceiling = max((row['teamCount'] for row in rows), default=10) if rank else maximum * 1.08
    points = []
    for index, row in enumerate(rows):
        value = row[key]
        x = round(54 + index * 716 / max(1, len(rows) - 1), 2)
        y = None if value is None else round(24 + (value - 1) * 182 / max(1, ceiling - 1), 2) if rank else round(206 - (value-floor) / (ceiling-floor) * 182, 2)
        points.append({'id': row.get('id', str(row['year'])), 'label': row.get('label', str(row['year'])),
                       'tick': row.get('tick', str(row['year'])), 'boundary': index == 0 or row['year'] != rows[index-1]['year'],
                       'year': row['year'], 'value': value, 'x': x, 'y': y,
                       'partial': not row['complete'], 'color': row['team']['color'],
                       'display': 'Unavailable' if value is None else ordinal(value) if rank else f'{value:,.2f}' if key == 'fpPerStart' else f'{value:,.0f}'})
    ticks = ([{'value': value, 'display': ordinal(value), 'y': round(24 + (value - 1) * 182 / max(1, ceiling - 1), 2)}
              for value in range(1, int(ceiling) + 1)] if rank else
             [{'value': floor+(ceiling-floor)*part, 'display': f'{floor+(ceiling-floor)*part:,.1f}' if key == 'fpPerStart' else f'{floor+(ceiling-floor)*part:,.0f}',
               'y': round(206 - part * 182, 2)} for part in (0, .25, .5, .75, 1)])
    return {'label': label, 'granular': granular, 'points': points, 'ticks': ticks, 'viewBox': [0, 0, 800, 260]}


def franchise_profile(payload, league, completed, metadata, config):
    team_id = int(payload['team']['teamId'])
    franchise = league[league['Team ID'] == team_id].sort_values(['Year', 'Week'])
    history = []
    for year_text, season in payload['seasons'].items():
        if season is None:
            continue
        year = int(year_text)
        rows = franchise[franchise['Year'] == year]
        regular = rows[rows['Type'] == 'Regular']
        snapshot = season.get('snapshot') or {}
        settings = next((item for item in metadata['seasons'] if int(item['season']) == year), {})
        complete = year in completed
        identity = dict(team_info(rows.iloc[-1], config), owner=str(rows.iloc[-1]['Team Owner'])) if not rows.empty else payload['team']
        wins, losses = int(snapshot.get('wins', regular['Win'].sum())), int(snapshot.get('losses', regular['Loss'].sum()))
        rank = snapshot.get('rank')
        final_rank = int(rows.iloc[-1]['Rank']) if complete and not rows.empty else None
        playoff = complete and rows['Type'].isin(['Playoffs', 'Bye']).any()
        playoff_rows = league[(league['Year'] == year) & (league['Type'] == 'Playoffs')]
        finalists = playoff_rows[playoff_rows['Week'] == playoff_rows['Week'].max()] if not playoff_rows.empty else playoff_rows
        appearance = complete and team_id in set(finalists['Team ID'])
        champion = champion_for(league, year, season_teams(league, year, config)) if complete else None
        won = bool(champion and champion['teamId'] == team_id)
        performance = season.get('performance', {}).get('season', {})
        total_fpts = float(rows['Points For'].sum()) if not rows.empty else float(snapshot.get('pointsFor', 0))
        history.append({'year': year, 'team': identity, 'complete': complete,
                        'owners': list(dict.fromkeys(str(owner) for owner in rows['Team Owner'].dropna())) if not rows.empty else [identity.get('owner', '')],
                        'wins': wins, 'losses': losses, 'record': f'{wins}–{losses}',
                        'winPct': wins / (wins + losses) if wins + losses else None,
                        'regularFpts': float(snapshot.get('pointsFor', regular['Points For'].sum())),
                        'fpts': total_fpts, 'regularRank': rank,
                        'finalRank': final_rank, 'teamCount': int(league[league['Year'] == year]['Team ID'].nunique()) or 10,
                        'regularWeeks': int(regular['Week'].nunique()), 'scheduledRegularWeeks': settings.get('regularWeeks'),
                        'fpPerStart': performance.get('fpPerStart'), 'champion': won,
                        'championshipAppearance': bool(appearance), 'playoffAppearance': bool(playoff),
                        'playoffFinish': 'In progress' if not complete else 'Champion' if won else 'Runner-up' if appearance else f'{ordinal(final_rank)} overall' if playoff else 'Did not qualify'})
    history.sort(key=lambda row: row['year'], reverse=True)
    finished = [row for row in history if row['complete']]
    # Compare finished seasons by regular-season win percentage, then rank and PF.
    ordered = sorted(finished, key=lambda row: (row['winPct'] or 0, -(row['regularRank'] or 999), row['regularFpts']))
    wins, losses = sum(row['wins'] for row in history), sum(row['losses'] for row in history)
    achievements = []
    for row in finished:
        if row['champion'] or row['championshipAppearance'] or row['regularRank'] == 1:
            achievements.append({'year': row['year'], 'team': row['team'],
                                 'title': 'League champion' if row['champion'] else 'Championship finalist' if row['championshipAppearance'] else 'Regular-season leader',
                                 'detail': f"{row['record']} regular season · {ordinal(row['finalRank'])} final finish"})
    records = []
    if not franchise.empty:
        for label, column in (('Highest-scoring matchup', 'Points For'),):
            top = franchise.loc[franchise[column].idxmax()]
            records.append({'label': label, 'value': f"{top[column]:,.0f} FPTS", 'year': int(top['Year']), 'week': int(top['Week']), 'team': team_info(top, config)})
        games = franchise[franchise['Type'].isin(['Regular', 'Playoffs'])].copy()
        if not games.empty:
            games['Margin'] = games['Points For'] - games['Points Against']
            top = games.loc[games['Margin'].idxmax()]
            if top['Margin'] > 0:
                records.append({'label': 'Largest matchup win', 'value': f"+{top['Margin']:,.0f} FPTS", 'year': int(top['Year']), 'week': int(top['Week']), 'team': team_info(top, config)})
    return {'history': history, 'totals': {'seasons': len(history), 'completedSeasons': len(finished),
             'championships': sum(row['champion'] for row in history),
             'championshipAppearances': sum(row['championshipAppearance'] for row in history),
             'playoffAppearances': sum(row['playoffAppearance'] for row in history),
             'wins': wins, 'losses': losses, 'winPct': round(wins / (wins + losses), 4) if wins + losses else None,
             'fpts': sum(row['fpts'] for row in history),
             'fpPerStart': payload.get('summary', {}).get('performance', {}).get('fpPerStart')},
            'bestSeason': ordered[-1]['year'] if ordered else None, 'worstSeason': ordered[0]['year'] if ordered else None,
            'achievements': achievements, 'records': records,
            'trends': {key: trend_chart(history, key, label, rank) for key, label, rank in (
                ('fpts', 'Season Fantasy Points', False), ('regularRank', 'Regular-season position', True),
                ('fpPerStart', 'Fantasy Points per Start', False))}}


def granular_trends(payload, profile, league, daily, mapping, metadata):
    """Chronological actuals; verified denominators and canonical rank snapshots."""
    tid = payload['team']['teamId']
    history = {r['year']: r for r in profile['history']}
    rows = league[league['Team ID'] == tid].sort_values(['Year', 'Week'])
    weekly, ranks, dates, differences = [], [], [], []
    for _, row in rows.iterrows():
        year, week = int(row['Year']), int(row['Week'])
        if year not in history:
            continue
        base = dict(history[year], order=week, id=f'{year}-w{week}', label=f'{year} · Week {week}', tick=f'W{week}')
        metric = payload['seasons'][str(year)]['performance']['weeks'].get(str(week), {})
        if metric.get('available') and metric.get('coverage')=='verified' and metric.get('scoreDelta'):
            differences.append({'year':year,'week':week,'official':metric['recordedFpts'],'eligible':metric['fpts']})
        weekly.append(dict(base, fpts=float(row['Points For']), fpPerStart=metric.get('fpPerStart')))
        field = league[(league['Year']==year) & (league['Week']==week)]
        expected = set(league[league['Year']==year]['Team ID'])
        # Do not chart a rank from a partial league field or playoff placement.
        if len(field)==len(expected) and set(field['Team ID'])==expected and field['Type'].eq('Regular').all():
            ranks.append(dict(base, regularRank=int(row['Rank'])))
    if {'Year', 'Team ID', 'Date', 'Player Slot', 'MIN', 'FPTS'}.issubset(daily.columns):
        credited = credited_daily_rows(attach_matchup_weeks(daily, mapping), metadata)
        credited = credited[credited['Team ID']==tid]
        for (year, week), games in credited.groupby(['Year', 'Week']):
            season = payload['seasons'].get(str(int(year)))
            metric = (season or {}).get('performance', {}).get('weeks', {}).get(str(int(week)), {})
            if not metric.get('available') or metric.get('coverage')=='bye-excluded' or abs(games['FPTS'].sum()-metric['fpts'])>.01:
                continue
            for day, group in games.groupby('Date'):
                dates.append(dict(history[int(year)], order=day, id=day, label=f'{day} · {int(year)} Week {int(week)} · eligible player FPTS',
                                  tick=day[5:], fpts=float(group['FPTS'].sum())))
    profile['scoreDifferences'] = differences
    profile['trendViews'] = {
        'fpts': {'week': trend_chart(weekly,'fpts','Weekly Fantasy Points',granular=True),
                 'day': trend_chart(dates,'fpts','Daily eligible player Fantasy Points',granular=True)},
        'regularRank': {'week': trend_chart(ranks,'regularRank','Weekly regular-season position',rank=True,granular=True)},
        'fpPerStart': {'week': trend_chart(weekly,'fpPerStart','Weekly Fantasy Points per Start',granular=True)}}


def build(source, output):
    league = pd.read_csv(source / 'basketballBrawlLeagueData.csv')
    daily = pd.read_csv(source / 'playerDailyData.csv')
    metadata, config = load_season_metadata(), logo_config()
    completed = set(completed_season_years(league, daily, metadata))
    for path in sorted((output / 'team-stats').glob('*.json')):
        payload = json.loads(path.read_text())
        payload['franchise'] = franchise_profile(payload, league, completed, metadata, config)
        if all('weeks' in (v or {}).get('performance', {}) for v in payload['seasons'].values() if v):
            granular_trends(payload, payload['franchise'], league, daily, load_scoring_period_map(), metadata)
        write_json(path, payload)
