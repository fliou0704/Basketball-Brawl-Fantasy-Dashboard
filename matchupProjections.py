"""Auditable trailing-game estimates and maximum-weight fantasy-slot assignments.

Bulk ESPN game samples supplement canonical logs that omit unrostered games.
No fantasy actual scores or historical lineup records are rewritten.
"""
from collections import defaultdict
from datetime import date, timedelta
import math
from nbaSchedule import instant, NY

IR_SLOTS = ('IR', 'IR+', 'IL')


def participation(member, game, snapshot):
    """Current ESPN OUT applies only on the observed NY date, never a return forecast."""
    status = member.get('injuryStatus')
    stamp = member.get('injuryVerifiedAt')
    result = {'availabilityStatus': status or 'UNKNOWN', 'excluded': False,
              'availabilityReason': 'Availability unverified; participation assumed.'}
    try:
        verified = instant(stamp)
        now = instant(snapshot)
        fresh = timedelta(0) <= now-verified <= timedelta(hours=6)
        source = member.get('injurySource') == 'ESPN current roster'
        if fresh and source:
            result['availabilityReason'] = 'Current ESPN status; future participation uncertain.'
            if game['date'] == now.astimezone(NY).date().isoformat() == verified.astimezone(NY).date().isoformat() and status in ('OUT', 'SSPD', 'SUSPENDED'):
                result.update(excluded=True, availabilityReason=f'ESPN {status} on this date; excluded from projected starts.')
        elif stamp:
            result['availabilityReason'] = 'Availability status is stale or unverified; participation assumed.'
    except (ValueError, TypeError, KeyError):
        pass
    return result


def optimal_lineup(players, slots, value='points', limit=10):
    """Slot-mask DP; optional empty slots, one appearance per player, deterministic ties."""
    if len(slots)>16 or any(not isinstance(s,str) for s in slots):
        raise ValueError('Unsupported lineup slot template')
    seen=set()
    dp={0:(0.0,())}
    for p in sorted(players,key=lambda p:p['playerId']):
        pid=p['playerId']
        if pid in seen:
            raise ValueError('Duplicate player in daily lineup pool')
        seen.add(pid)
        if p.get('slot') in IR_SLOTS:
            continue
        score=p.get(value)
        if score is None or not math.isfinite(float(score)):
            raise ValueError('Missing player value')
        if not isinstance(p.get('eligibility'),list) or not p['eligibility']:
            raise ValueError('Missing positional eligibility')
        allowed=[i for i,s in enumerate(slots) if s in p['eligibility']]
        for mask,(total,picks) in list(dp.items()):
            if bin(mask).count('1')>=limit:
                continue
            for i in allowed:
                if mask&(1<<i):
                    continue
                new=mask|(1<<i);candidate=(total+score,picks+((pid,i),))
                old=dp.get(new)
                if old is None or candidate[0]>old[0] or candidate[0]==old[0] and candidate[1]<old[1]:
                    dp[new]=candidate
    mask=min(dp,key=lambda m:(-dp[m][0],-bin(m).count('1'),dp[m][1]))
    total,picks=dp[mask]
    return {'points':total,'assignments':{pid:slots[i] for pid,i in picks}}


def trailing_average(games, before, as_of):
    """Use actual completions known at the snapshot, strictly before the target civil date."""
    invalid={'points':None,'sampleSize':0,'reason':'Conflicting or invalid game sample.'}
    try:
        snapshot=instant(as_of)
        unique={}
        for g in games:
            if g.get('completed') is not True or g['date']>=before or instant(g['knownAt'])>snapshot:
                continue
            if isinstance(g.get('points'),bool) or not isinstance(g.get('points'),(int,float)) or not math.isfinite(g['points']):
                return invalid
            key=g.get('gameId') or (g['season'],g['date'])
            if key in unique and unique[key]['points']!=g['points']:
                return invalid
            unique[key]=g
    except (ValueError,KeyError,TypeError):
        return invalid
    sample=sorted(unique.values(),key=lambda g:(g['date'],g.get('gameId',0)),reverse=True)[:10]
    return {'points':sum(g['points'] for g in sample)/len(sample) if sample else None,
            'sampleSize':len(sample),'firstDate':min((g['date'] for g in sample),default=None),
            'lastDate':max((g['date'] for g in sample),default=None)}


def normalize_history(raw, ids, calendars, schedules, now, scoring_year=None):
    anchors={int(c['season']):date.fromisoformat(c['dateAnchor']) for c in calendars}
    current=max(anchors)
    weights={int(c['season']):c.get('scoringWeights') for c in calendars}
    scoring_year=scoring_year or current
    fixtures={int(g['id']):g for s in schedules.values() for g in s.get('fixtures',[])}
    result={}
    for item in raw.get('players',[]):
        p=item.get('player',item);pid=int(p['id'])
        if pid not in ids:
            continue
        games={};conflict=False
        for r in p.get('stats',[]):
            if r.get('statSourceId')!=0 or r.get('statSplitTypeId')!=5 or float(r.get('stats',{}).get('40',0) or 0)<=0:
                continue
            season=int(r['seasonId']);period=int(r['scoringPeriodId'])
            if period<1 or season not in anchors:
                continue
            if weights.get(season)!=weights.get(scoring_year):
                conflict=True;continue  # do not silently rescore historical performances
            gid=int(r['externalId']);fixture=fixtures.get(gid)
            if fixture:
                if not (fixture.get('statsOfficial') is True or fixture.get('status')=='completed') or instant(fixture['start'])>now:
                    continue
                day=fixture['date']
                if int(fixture['season'])!=season or fixture.get('period')!=period:
                    conflict=True;continue
            elif season<current and season in anchors:
                # Past-season actual NBA game rows use the verified civil scoring-day anchor.
                day=(anchors[season]+timedelta(days=period)).isoformat()
            else:
                conflict=True
                continue  # unknown current games cannot silently vanish from the trailing sample
            value=r.get('appliedTotal')
            if value is None or not math.isfinite(float(value)) or day>now.astimezone(NY).date().isoformat():
                conflict=True;continue
            game={'gameId':gid,'season':season,'date':day,'points':float(value),'completed':True,'knownAt':now.isoformat()}
            if gid in games and games[gid]['points']!=game['points']:
                conflict=True
            games[gid]=game
        result[str(pid)]={'games':sorted(games.values(),key=lambda g:(g['date'],g['gameId']),reverse=True)[:20],
                          'error':'Conflicting NBA game evidence.' if conflict else None}
    return result


def refresh_history(league, calendars, schedules, now, previous=None, request_factory=None):
    """One roster-wide current request, with cached seasonal bulk fallbacks for short samples."""
    ids={int(p.playerId) for t in league.teams for p in t.roster}
    year=int(league.year)
    raw=league.espn_request.get_player_card(sorted(ids), max(200,int(league.finalScoringPeriod)),
        additional_filters=[f'00{year-1}'])
    if not isinstance(raw.get('players'),list):
        raise ValueError('Missing bulk NBA player response')
    result=normalize_history(raw,ids,calendars,schedules,now)
    prior=(previous or {}).get('players',{}) if (previous or {}).get('season')==year else {}
    for pid in ids:
        key=str(pid);entry=result.setdefault(key,{'games':[],'error':None});old=prior.get(key,{})
        cached=[] if old.get('error') else [g for g in old.get('games',[]) if g['season']<year-1]
        games={g['gameId']:g for g in cached};games.update({g['gameId']:g for g in entry['games']})
        entry['games']=sorted(games.values(),key=lambda g:(g['date'],g['gameId']),reverse=True)[:20]
        entry['checkedSeasons']=sorted(set(old.get('checkedSeasons',[]))|{year,year-1})
    if request_factory is None:
        from espn_api.requests.espn_requests import EspnFantasyRequests
        request_factory=lambda season:EspnFantasyRequests('nba',season,league.league_id,cookies=league.espn_request.cookies)
    # Filters on the current endpoint do not reliably return seasons older than
    # its previous year. Ask the historical endpoint explicitly, in bulk.
    for season in sorted((int(c['season']) for c in calendars if int(c['season'])<year-1),reverse=True):
        short={pid for pid in ids if len(result[str(pid)]['games'])<10 and season not in result[str(pid)]['checkedSeasons']}
        if not short:
            continue
        try:
            extra=request_factory(season).get_player_card(sorted(short),200)
            if not isinstance(extra.get('players'),list):
                raise ValueError('Missing historical bulk player response')
            more=normalize_history(extra,short,calendars,schedules,now,scoring_year=season)
        except Exception:
            for pid in short:
                result[str(pid)]['error']='Historical NBA game coverage unavailable.'
            continue
        for pid in short:
            key=str(pid);entry=result[key];added=more.get(key,{'games':[]})
            merged={g['gameId']:g for g in entry['games']};merged.update({g['gameId']:g for g in added['games']})
            entry['games']=sorted(merged.values(),key=lambda g:(g['date'],g['gameId']),reverse=True)[:20]
            entry['error']=entry.get('error') or added.get('error')
            entry['checkedSeasons']=sorted(set(entry['checkedSeasons'])|{season})
    return {'season':year,'gameScope':'regular-season','verifiedAt':now.isoformat(),'source':'ESPN bulk kona_playercard actual regular-season games',
            'players':result,'lastError':None}


def project_team(current, calendar, week, team, opportunities, fixtures):
    result={'remaining':None,'confirmedRemaining':None,'days':[],
            'reason':'Completed NBA game samples and verified remaining opportunities are required.'}
    history=current.get('projectionHistory') or {}
    if history.get('lastError') or not history.get('verifiedAt') or not current.get('updatedAt'):
        return result
    try:
        age=instant(current['updatedAt'])-instant(history['verifiedAt'])
        if age<timedelta(0) or age>timedelta(hours=30):
            return dict(result,reason='Player game samples are stale.')
    except (ValueError,TypeError):
        return result
    roster={p['playerId']:p for p in team['roster']}
    daily=defaultdict(list)
    unknown=False
    for p in opportunities['players']:
        if p.get('gameIds') is None:
            unknown=True;continue
        entry=history.get('players',{}).get(str(p['playerId']),{})
        for gid in p['gameIds']:
            game=fixtures.get(gid)
            if not game:
                unknown=True;continue
            average=trailing_average(entry.get('games',[]),game['date'],current['updatedAt'])
            if entry.get('error'):
                average={'points':None,'sampleSize':0}
            daily[game['date']].append({'playerId':p['playerId'],'gameId':gid,**average,
                **participation(roster[p['playerId']],game,current['updatedAt']), 'assignedSlot':None,'selected':None})
    for day in opportunities['days']:
        players=daily[day['date']]
        slots=day.get('availableSlots')
        pool=[];reason=None
        if slots is None:
            reason='Lineup locks, eligibility or league limits are not fully supported.'
        for p in players:
            member=roster[p['playerId']]
            if p['excluded'] or member.get('slot') in IR_SLOTS or p['playerId'] in day.get('lockedPlayerIds',[]):
                p['selected']=False;continue
            if p['points'] is None:
                reason='A scheduled player has no reliable completed-game sample.'
            pool.append(dict(member,points=p['points']))
        optimum=None
        if reason is None:
            try:
                optimum=optimal_lineup(pool,slots)
                for p in players:
                    p['assignedSlot']=optimum['assignments'].get(p['playerId'])
                    p['selected']=p['assignedSlot'] is not None
            except ValueError:
                reason='Daily player/position evidence is incomplete or conflicting.'
        result['days'].append({'date':day['date'],'period':day['period'],'points':optimum['points'] if optimum and not day.get('additionalTBD') else None,
                               'confirmedPoints':optimum['points'] if optimum else None, 'players':players,'additionalTBD':day.get('additionalTBD',False),'reason':reason})
    known=bool(opportunities['days']) and not unknown and all(d['confirmedPoints'] is not None for d in result['days'])
    if known:
        result['confirmedRemaining']=sum(d['confirmedPoints'] for d in result['days'])
        if not opportunities.get('uncertain') and not opportunities.get('inProgress') and not opportunities.get('startedUnconfirmed') and opportunities.get('games') is not None:
            result['remaining']=result['confirmedRemaining']
    result['reason']='Optimal-lineup estimate using the current roster and last 10 completed NBA games. Fresh ESPN OUT/suspension statuses exclude starts only on the observed date. Later availability, DNPs and future roster changes are unknown.'
    if opportunities.get('uncertain'):
        result['reason']+=' Additional NBA Cup dates or game statuses are unresolved; a complete projected final score is unavailable.'
    if opportunities.get('inProgress') or opportunities.get('startedUnconfirmed'):
        result['reason']+=' Started games are not projected again; their unfinished scoring makes a full projected final unavailable.'
    if not known:
        result['reason']+=' Some player projections or lineup constraints are unavailable.'
    return result


def historical_potential(records, slots, actual, *, complete=False, locks_verified=False):
    """Never upgrade partial game rows to a complete historical roster certificate."""
    unavailable={'points':None,'leftOnBench':None,'efficiency':None,
                 'reason':'Complete historical roster, game and eligibility evidence is unavailable.'}
    if not complete or not locks_verified or actual is None:
        return unavailable
    pool=[]
    for p in records:
        if p.get('slot') in IR_SLOTS or p.get('played') is False or p.get('rosterMember') is False:
            continue
        if not p.get('gameComplete') or p.get('rosterMember') is not True:
            return unavailable
        pool.append(p)
    try:
        optimum=optimal_lineup(pool,slots)
    except ValueError:
        return unavailable
    value=optimum['points']
    if value<actual-0.01:
        return dict(unavailable,reason='Historical optimal points do not reconcile with actual scoring.')
    return {'points':value,'leftOnBench':value-actual,'efficiency':actual/value if value>0 and actual>=0 else None,
            'assignments':optimum['assignments'],'reason':None}
