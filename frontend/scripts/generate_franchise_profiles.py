"""Team-only franchise profiles, joined by stable ESPN fantasy team ID."""
import json

import pandas as pd

from build_homepage import logo_config, team_info, write_json
from generate_record_book import completed_season_years, champion_for, season_teams
from generate_team_stats import ordinal
from playerDailyAggregation import load_season_metadata


def trend_chart(history, key, label, rank=False):
    rows = sorted(history, key=lambda row: row['year'])
    values = [row[key] for row in rows if row[key] is not None]
    maximum = max(values, default=1) or 1
    ceiling = max(row['teamCount'] for row in rows) if rank else maximum * 1.08
    points = []
    for index, row in enumerate(rows):
        value = row[key]
        x = round(54 + index * 716 / max(1, len(rows) - 1), 2)
        y = None if value is None else round(24 + (value - 1) * 182 / max(1, ceiling - 1), 2) if rank else round(206 - value / ceiling * 182, 2)
        points.append({'year': row['year'], 'value': value, 'x': x, 'y': y,
                       'partial': not row['complete'], 'color': row['team']['color'],
                       'display': 'Unavailable' if value is None else ordinal(value) if rank else f'{value:,.2f}' if key == 'fpPerStart' else f'{value:,.0f}'})
    ticks = ([{'value': value, 'display': ordinal(value), 'y': round(24 + (value - 1) * 182 / max(1, ceiling - 1), 2)}
              for value in range(1, int(ceiling) + 1)] if rank else
             [{'value': ceiling * part, 'display': f'{ceiling * part:,.1f}' if key == 'fpPerStart' else f'{ceiling * part:,.0f}',
               'y': round(206 - part * 182, 2)} for part in (0, .25, .5, .75, 1)])
    return {'label': label, 'points': points, 'ticks': ticks, 'viewBox': [0, 0, 800, 260]}


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


def build(source, output):
    league = pd.read_csv(source / 'basketballBrawlLeagueData.csv')
    daily = pd.read_csv(source / 'playerDailyData.csv')
    metadata, config = load_season_metadata(), logo_config()
    completed = set(completed_season_years(league, daily, metadata))
    for path in sorted((output / 'team-stats').glob('*.json')):
        payload = json.loads(path.read_text())
        payload['franchise'] = franchise_profile(payload, league, completed, metadata, config)
        write_json(path, payload)
