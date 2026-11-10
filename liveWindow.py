"""Schedule-aware gate; no ESPN fantasy requests, commits or deployment actions."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

from nbaSchedule import NY,instant,uncertainty,SCOREBOARD_URL


def precheck(metadata,now,state=None,force=False):
    season=now.year+(now.month>=7)
    result={'due':False,'season':season,'dates':[],'reason':'Outside verified fantasy/game windows'}
    if force:return dict(result,due=True,reason='Manual force')
    calendar=next((s.get('fantasyCalendar',{})for s in metadata.get('seasons',[])if s['season']==season),{})
    valid={d['date']for d in calendar.get('days',[])}
    today=now.astimezone(NY).date();schedule=metadata.get('nbaSchedules',{}).get(str(season),{})
    state=state or {};entries=state.get('dates',{})
    fresh=bool(schedule.get('publishedComplete') and not schedule.get('lastError'))
    try:fresh=fresh and timedelta(0)<=now-instant(schedule['verifiedAt'])<=timedelta(hours=30)
    except (KeyError,ValueError,TypeError):fresh=False
    unknown=uncertainty(schedule) if schedule else {}
    discovery=now.minute%15<5 # Best effort under a five-minute Actions trigger.
    for offset in (-1,0,1):
        day=(today+timedelta(days=offset)).isoformat()
        if day not in valid:continue
        games=[g for g in schedule.get('fixtures',[])if g['date']==day and g['regularSeason'] and g['status']not in('canceled','replaced')]
        signature=hashlib.sha256(json.dumps([(g['id'],g['start'])for g in games],sort_keys=True).encode()).hexdigest()
        old=entries.get(day,{})
        cup=any(v.get('unassigned') and (not v.get('cupWindow') or v['cupWindow'][0]<=day<=v['cupWindow'][1])for v in unknown.values())
        unsure=not fresh or cup or any(g['status'] in ('tbd','postponed','unknown') or g.get('timeTBD') for g in games)
        closed=False
        if old.get('signature')==signature and old.get('firstFinalAt'):
            closed=now-instant(old['firstFinalAt'])>=timedelta(minutes=30)
        near=any(g['status'] not in ('postponed','unknown') and instant(g['start'])-timedelta(minutes=60)<=now<=instant(g['start'])+timedelta(hours=12) for g in games)
        underway=old.get('active') or any(g['status']=='in-progress'for g in games)
        if old.get('pending') and not discovery:near=False;underway=False
        if ((near or underway) and not closed) or (unsure and discovery and (offset==0 or offset==-1 and now.astimezone(NY).hour<8)):
            result['dates'].append({'date':day,'signature':signature,'expected':[g['id']for g in games]})
    result['due']=bool(result['dates']);
    if result['due']:result['reason']='Candidate game/discovery window'
    return result


def check(metadata,now,state=None,force=False,fetch=None):
    state=state or {'version':1,'dates':{}}
    value=precheck(metadata,now,state,force)
    if force:return value,state
    if not value['due']:return value,state
    from liveScoringAdapter import normalize_games
    from nbaSchedule import request_json
    fetch=fetch or request_json;publish=False
    for item in value['dates']:
        raw=fetch(SCOREBOARD_URL,{'dates':item['date'].replace('-',''),'limit':100})
        games=normalize_games(raw,item['date'],value['season'])['games']
        if set(item['expected'])-{g['gameId']for g in games}:raise ValueError('NBA status omitted known fixtures; retained last snapshot')
        old=state.get('dates',{}).get(item['date'],{})
        if old.get('signature')!=item['signature']:old={}
        active=any(g['status']=='in-progress' or g['status']=='scheduled' and instant(g['start'])<=now+timedelta(minutes=60) for g in games)
        pending=any(g['status'] in ('unknown','postponed')for g in games)
        terminal=bool(games) and all(g['status'] in ('completed','canceled')for g in games)
        final=old.get('firstFinalAt') if terminal else None
        if terminal and not final:final=now.isoformat()
        publish|=active or pending and now.minute%15<5 or terminal and now-instant(final)<timedelta(minutes=30)
        state.setdefault('dates',{})[item['date']]={'signature':item['signature'],'firstFinalAt':final,'active':active,'pending':pending,'checkedAt':now.isoformat()}
    state['dates']={k:v for k,v in state.get('dates',{}).items()if now-instant(v['checkedAt'])<timedelta(days=3)}
    value.update(due=bool(publish),reason='Game window active' if publish else 'No active games; postgame window ended')
    return value,state


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--metadata',type=Path,required=True);p.add_argument('--state',type=Path,required=True)
    p.add_argument('--precheck',action='store_true');p.add_argument('--force',action='store_true');args=p.parse_args()
    try:
        metadata=json.loads(args.metadata.read_text());state=json.loads(args.state.read_text())if args.state.exists()else {'version':1,'dates':{}}
        if state.get('version')!=1:state={'version':1,'dates':{}}
        now=datetime.now(timezone.utc)
        if args.precheck:result=precheck(metadata,now,state,args.force)
        else:
            result,state=check(metadata,now,state,args.force)
            args.state.parent.mkdir(parents=True,exist_ok=True)
            fd,path=tempfile.mkstemp(dir=args.state.parent)
            try:
                with os.fdopen(fd,'w')as f:json.dump(state,f)
                os.replace(path,args.state)
            finally:
                if os.path.exists(path):os.unlink(path)
        print('due='+str(result['due']).lower());print('season='+str(result['season']));print('reason='+result['reason']);return 0
    except (ValueError,KeyError,TypeError,OSError):
        print('Live window check failed; no publication authorized',file=__import__('sys').stderr);return 1


if __name__=='__main__':raise SystemExit(main())
