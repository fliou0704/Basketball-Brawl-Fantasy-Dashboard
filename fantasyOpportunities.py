"""Current-roster future opportunities; never historical player appearances."""
from collections import defaultdict
from datetime import timedelta
from nbaSchedule import instant, uncertainty, NY


def potential_starts(players, slots):
    """Maximum bipartite matching, one player-game per eligible daily slot."""
    assigned = {}
    def place(index, seen):
        for slot, name in enumerate(slots):
            if name not in players[index].get('eligibility', []) or slot in seen:
                continue
            seen.add(slot)
            if slot not in assigned or place(assigned[slot], seen):
                assigned[slot] = index
                return True
        return False
    for index, player in enumerate(players):
        if player.get('slot') not in ('IR', 'IR+', 'IL'):
            place(index, set())
    return len(assigned)


def prepare(schedule):
    """Index stable IDs once for all current/future fantasy team/week joins."""
    by_team = defaultdict(list)
    seen = {}
    for game in (schedule or {}).get('fixtures', []):
        if game['id'] in seen:
            if seen[game['id']] != game:
                return None
            continue
        seen[game['id']] = game
        for tid in (game['home'], game['away']):
            by_team[tid].append(game)
    return by_team


def remaining(current, calendar, week, team_id, schedule, index=None, locked=()):
    result = {'games':None, 'potentialStarts':None, 'days':[], 'players':[],
              'inProgress':0, 'startedUnconfirmed':0, 'uncertain':False, 'confirmedOnly':True,
              'reason':'Verified fantasy dates and a current NBA schedule are required.'}
    if week['state']=='final':
        return dict(result, games=0, potentialStarts=0, reason='Matchup complete.')
    team = next((t for t in current.get('teams', []) if t['teamId']==team_id), None)
    if not team or 'roster' not in team:
        return dict(result, reason='Current fantasy roster is unavailable.')
    roster = team['roster']
    if len({p['playerId']for p in roster})!=len(roster) or team.get('rosterConflict'):
        return dict(result, reason='Conflicting fantasy roster assignments; counts are unavailable.')
    result['players'] = [dict(playerId=p['playerId'], name=p['name'], slot=p.get('slot'),
                              injuryStatus=p.get('injuryStatus'), gameIds=None) for p in roster]
    if week.get('dateRangeKind')!='scheduled' or not schedule or schedule.get('publishedComplete') is not True:
        return result
    try:
        snapshot = instant(current['updatedAt'])
        age = snapshot - instant(schedule['verifiedAt'])
    except (KeyError, ValueError, TypeError):
        return result
    if schedule.get('season') != calendar['season'] or age > timedelta(hours=30) or schedule.get('lastError'):
        return dict(result, reason='NBA schedule verification is stale or failed; counts are unavailable.')
    index = prepare(schedule) if index is None else index
    if index is None:
        return dict(result, reason='Conflicting NBA fixture identities; counts are unavailable.')
    known_teams = {t['id'] for t in schedule.get('teams', [])}
    days = [d for d in calendar.get('scheduledDays', []) if d['week']==week['week']]
    if not days or len(days)!=week['lastPeriod']-week['firstPeriod']+1:
        return result
    day_map = {d['date']: d for d in days}
    slots_template = calendar.get('lineupSlots') or []
    uncertainties = uncertainty(schedule)
    candidates, active_locks, underway, unconfirmed = defaultdict(list), defaultdict(dict), defaultdict(set), defaultdict(set)
    today = snapshot.astimezone(NY).date().isoformat()
    unknown, tbd, not_started_unknown = [], False, False
    timing_unknown = False
    uncertain_dates = set()
    players = []
    # Actual starts use the historical team/slot recorded that day, including
    # players subsequently dropped or traded by the fantasy manager.
    for played in locked:
        if played['date']==today:
            active_locks[today][played['playerId']] = played['slot']
    for p in roster:
        tid = p.get('proTeamId')
        if tid is None or (tid != 0 and tid not in known_teams):
            unknown.append(p['playerId'])
            players.append(dict(playerId=p['playerId'],name=p['name'],slot=p.get('slot'),injuryStatus=p.get('injuryStatus'),gameIds=None))
            continue
        info = uncertainties.get(str(tid), {})
        window = info.get('cupWindow')
        affected = bool(info.get('unassigned')) and (not window or week['start']<=window[1] and week['end']>=window[0])
        affected = affected or bool(info.get('undated'))
        if affected:
            uncertain_dates.update(d for d in day_map if info.get('undated') or not window or window[0]<=d<=window[1])
        tbd = tbd or affected
        game_ids = []
        player_timing_unknown = False
        for g in index.get(tid, []):
            if not g['regularSeason']:
                continue
            if g['date'] not in day_map:
                continue
            day = g['date']
            start = instant(g['start'])
            try:
                known_before = instant(p['nbaTeamSince'])<=start and instant(p['rosterSince'])<=start
            except (KeyError, ValueError, TypeError):
                known_before = False
            if g['status']=='in-progress' and known_before:
                underway[day].add(p['playerId'])
            started = g['status'] in ('completed','in-progress') or (g['status'] in ('scheduled','unknown') and start<=snapshot and not g.get('timeTBD'))
            if started and known_before and g['status'] not in ('completed','in-progress'):
                unconfirmed[day].add(p['playerId'])
            if day==today and started and known_before and p.get('slot') in slots_template:
                active_locks[day].setdefault(p['playerId'], p['slot'])
            if g['status'] in ('completed','in-progress','canceled') or started:
                continue
            if g.get('hasStarted'):
                not_started_unknown = True  # resumed games are not new starts
                continue
            recently_pre = (g['status']=='scheduled' and g.get('statusVerifiedAt')
                            and instant(g['statusVerifiedAt'])>=snapshot-timedelta(minutes=5))
            if day==today and (schedule.get('statusError') or g.get('timeTBD') and not recently_pre):
                timing_unknown = True
                player_timing_unknown = True
                not_started_unknown = True
                continue
            if g['status'] not in ('scheduled','tbd'):
                not_started_unknown = True
                continue
            if day < today:
                continue
            candidates[day].append(p)
            game_ids.append(g['id'])
        players.append(dict(playerId=p['playerId'], name=p['name'], slot=p.get('slot'),
                            injuryStatus=p.get('injuryStatus'), proTeamId=tid,
                            gameIds=game_ids, additionalTBD=affected or player_timing_unknown))
    constraints = current.get('lineupConstraints', {})
    supported = (bool(slots_template) and constraints.get('daily') is True and not constraints.get('slotStatLimits')
                 and constraints.get('moveLimit') in (None,-1)
                 and constraints.get('lineupLock','INDIVIDUAL_GAME')=='INDIVIDUAL_GAME'
                 and constraints.get('rosterLock') in ('FIRSTGAME_SCORINGPERIOD','INDIVIDUAL_GAME'))
    daily = []
    for d in days:
        if d['date']<today:
            continue
        slots = list(slots_template)
        for name in active_locks[d['date']].values():
            if name in slots:
                slots.remove(name)
            else:
                supported = False  # inconsistent locked-slot evidence
        pool = list({p['playerId']:p for p in candidates[d['date']]}.values())
        if len(pool)!=len(candidates[d['date']]):
            supported = False  # multiple same-day games require a different slot model
        pool = [p for p in pool if p['playerId'] not in active_locks[d['date']]]
        if any(p.get('slot') not in ('IR','IR+','IL') and (not isinstance(p.get('eligibility'),list)
               or not p['eligibility'] or not all(isinstance(v,str)for v in p['eligibility'])) for p in pool):
            supported = False
        daily.append({'period':d['period'], 'date':d['date'], 'games':len(candidates[d['date']]),
                      'potentialStarts':potential_starts(pool,slots) if supported else None,
                      'inProgress':len(underway[d['date']]), 'lockedSlots':len(active_locks[d['date']]),
                      'availableSlots':slots if supported else None, 'lockedPlayerIds':sorted(active_locks[d['date']]),
                      'additionalTBD':d['date'] in uncertain_dates})
    result.update(days=daily, players=players, inProgress=sum(len(v)for v in underway.values()),
                  startedUnconfirmed=sum(len(v)for v in unconfirmed.values()),
                  uncertain=tbd or not_started_unknown, unknownPlayerIds=unknown)
    if unknown:
        for d in daily:
            d.update(games=None,potentialStarts=None)
        return dict(result, reason='An NBA affiliation is unknown; complete team counts are unavailable.')
    result['games'] = None if timing_unknown else sum(d['games']for d in daily)
    if supported and not tbd and not not_started_unknown:
        result['potentialStarts'] = sum(d['potentialStarts']for d in daily)
    else:
        for d in daily:
            if not supported or d['additionalTBD'] or not_started_unknown:
                d['potentialStarts'] = None
    reason = 'Confirmed future games for the current roster; potential starts are an upper bound, excluding IR and verified occupied daily slots. Other locks, injuries, DNPs and future roster decisions may reduce appearances.'
    if tbd:
        reason += ' Additional NBA Cup or postponed games are TBD; exact potential starts are unavailable.'
    if not_started_unknown:
        reason += ' Some game times or statuses are unconfirmed.'
    if not supported:
        reason += ' Player eligibility or lineup/game-limit rules are incomplete or unsupported; potential starts are unavailable.'
    if not supported:
        for d in daily:
            d['availableSlots'] = None
    result['reason'] = reason
    return result
