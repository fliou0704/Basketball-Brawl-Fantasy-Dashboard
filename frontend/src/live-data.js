// Public read-only transport and temporary overlays. No scoring formula lives here.
export const LIVE_STALE_MS=10*60*1000;
const fmt=n=>n.toLocaleString('en-US',{maximumFractionDigits:1});
const finite=n=>typeof n==='number'&&Number.isFinite(n);
export function liveConfig(env={}) {
  const enabled=env.VITE_ENABLE_LIVE_SCORING==='true';
  const url=env.VITE_SUPABASE_URL||'',key=env.VITE_SUPABASE_PUBLISHABLE_KEY||'',league=env.VITE_LIVE_LEAGUE_ID||'';
  const valid=/^https:\/\/[a-z0-9-]+\.supabase\.co\/?$/.test(url)&&key.startsWith('sb_publishable_')&&/^[a-f0-9-]{36}$/.test(league);
  return {enabled,valid,url:url.replace(/\/$/,''),key,league,espnLeagueId:Number(env.VITE_LIVE_ESPN_LEAGUE_ID||609694684)};
}
export function canonicalContext(value,updatedAt,active=true) {
  return value?{leagueId:value.leagueId,season:value.season,week:value.week,scoringPeriod:value.scoringPeriod,
    date:value.asOfDate||value.date,updatedAt:updatedAt||value.updatedAt,active}:null;
}
export function validLive(row,ctx,config,now=Date.now()) {
  try {
    const s=row.snapshot,checked=Date.parse(row.verified_at),source=Date.parse(s.updatedAt),canonical=Date.parse(ctx.updatedAt);
    if(!config.enabled||!config.valid||!ctx.active||ctx.leagueId!==config.espnLeagueId||row.league_id!==config.league||s.schemaVersion!==1||row.schema_version!==1)return false;
    if(s.leagueId!==ctx.leagueId||s.season!==ctx.season||s.week!==ctx.week||s.scoringPeriod!==ctx.scoringPeriod||s.date!==ctx.date)return false;
    if(row.season!==s.season||row.matchup_period!==s.week||row.scoring_period!==s.scoringPeriod||row.scoring_date!==s.date||row.revision!==s.revision)return false;
    if(!/^[a-f0-9]{64}$/.test(s.revision)||!finite(checked)||!finite(source)||!finite(canonical)||checked<canonical||checked>now+5*60000||now-checked>LIVE_STALE_MS||source>checked||Date.parse(row.source_updated_at)!==source)return false;
    if(!Array.isArray(s.teams)||!s.teams.length||!Array.isArray(s.matchups)||!Array.isArray(s.games))return false;
    const teams=new Set(),players=new Set(),matched=new Set(),games=new Set();
    for(const g of s.games){if(!Number.isInteger(g.gameId)||games.has(g.gameId)||typeof g.status!=='string'||!finite(Date.parse(g.start)))return false;games.add(g.gameId);}
    for(const t of s.teams) {
      if(!Number.isInteger(t.teamId)||teams.has(t.teamId)||!finite(t.officialScore)||!finite(t.officialDailyScore)||!Array.isArray(t.players))return false;
      teams.add(t.teamId);
      for(const p of t.players) {
        if(players.has(p.playerId)||!Number.isInteger(p.playerId)||p.teamId!==t.teamId||!finite(p.fantasyPoints)||!finite(p.creditedPoints)||typeof p.scoringEligible!=='boolean'||p.creditedPoints!==(p.scoringEligible?p.fantasyPoints:0)||!Array.isArray(p.gameIds))return false;
        if(typeof p.name!=='string'||typeof p.slot!=='string'||typeof p.injuryStatus!=='string'||typeof p.gameCoverage!=='string'||!p.stats||typeof p.stats!=='object'||Object.values(p.stats).some(v=>!finite(v))||p.gameIds.some(id=>!games.has(id)))return false;
        players.add(p.playerId);
      }
    }
    for(const m of s.matchups) {
      if(!Array.isArray(m.teamIds)||!m.teamIds.length||m.teamIds.length!==m.officialScores.length)return false;
      for(let i=0;i<m.teamIds.length;i++) {
        const id=m.teamIds[i];if(!teams.has(id)||matched.has(id)||m.officialScores[i]!==s.teams.find(t=>t.teamId===id).officialScore)return false;
        matched.add(id);
      }
    }
    return matched.size===teams.size;
  } catch {return false;}
}
export function overlayMatch(match,row,ctx,config,now=Date.now()) {
  if(!match||!['current','unavailable',undefined].includes(match.status)||!validLive(row,ctx,config,now))return match;
  const ids=match.teams.map(t=>t.teamId),source=row.snapshot.matchups.find(m=>m.teamIds.length===ids.length&&m.teamIds.every(id=>ids.includes(id)));
  if(!source)return match;
  const scores=ids.map(id=>row.snapshot.teams.find(t=>t.teamId===id).officialScore);
  return {...match,status:match.status==='unavailable'?'current':match.status,actualScores:scores,scoreDisplay:scores.map(fmt),liveVerifiedAt:row.verified_at};
}
export function overlayHome(home,row,ctx,config,now=Date.now()) {
  if(!home?.active||!validLive(row,ctx,config,now))return home;
  const matches=home.matchups.map(m=>overlayMatch(m,row,ctx,config,now));
  if(matches.some((m,i)=>m===home.matchups[i]))return home;
  return {...home,matchups:matches,liveVerifiedAt:row.verified_at};
}
export function overlayDetail(detail,match,row,ctx,config,now=Date.now()) {
  if(!detail||overlayMatch(match,row,ctx,config,now)===match)return detail;
  const s=row.snapshot,ids=match.teams.map(t=>t.teamId),date=detail.calendarDays?.find(d=>d.period===s.scoringPeriod);
  if(!date||date.date!==s.date)return detail;
  const teams=ids.map(id=>s.teams.find(t=>t.teamId===id));
  const old=detail.days.find(d=>d.period===s.scoringPeriod);
  const present=new Set(teams.flatMap(t=>t.players.map(p=>`${t.teamId}:${p.playerId}`)));
  const marker={verifiedAt:row.verified_at,canonicalUpdatedAt:ctx.updatedAt,baselineScores:match.actualScores,date:s.date};
  // A dropped/traded contributor cannot be silently removed from today's history.
  if(old?.lineup?.some(p=>!present.has(`${p.teamId}:${p.playerId}`)))return {...detail,liveOverlay:marker,liveDetailUnavailable:true};
  const gameMap=new Map(s.games.map(g=>[g.gameId,g]));
  const lineup=teams.flatMap(t=>t.players.map(p=>({teamId:t.teamId,playerId:p.playerId,name:p.name,slot:p.slot,positions:[],
    eligible:p.scoringEligible,points:p.creditedPoints,gamePoints:p.fantasyPoints,played:p.played===true,stats:p.stats,
    nbaTeam:null,liveStatus:p.gameIds.map(id=>gameMap.get(id)?.status||'unknown').join(', ')||p.gameCoverage,injuryStatus:p.injuryStatus})));
  const day={...(old||{}),period:s.scoringPeriod,date:s.date,partial:true,lineupCoverage:'complete-current-roster',lineup,
    points:teams.map(t=>t.officialDailyScore),cumulative:[null,null],contributors:lineup.filter(p=>p.eligible&&(p.played||p.points))};
  const days=[...detail.days.filter(d=>d.period!==s.scoringPeriod),day].sort((a,b)=>a.period-b.period);
  const summary=new Map();
  for(const d of days)for(const p of d.lineup||[]) {
    const key=`${p.teamId}:${p.playerId}:${p.eligible}`;
    const entry=summary.get(key)||{...p,points:0,gamePoints:0,starts:0,slots:[]};
    entry.points+=p.points;entry.gamePoints+=p.gamePoints;entry.starts+=Number(p.eligible&&p.played);if(!entry.slots.includes(p.slot))entry.slots.push(p.slot);
    if(p.liveStatus){entry.liveStatus=p.liveStatus;entry.injuryStatus=p.injuryStatus;}
    summary.set(key,entry);
  }
  return {...detail,days,summaryLineup:[...summary.values()],liveOverlay:marker,reconciled:false,insights:null,
    completedStarts:ids.map(id=>days.reduce((n,d)=>n+(d.lineup||[]).filter(p=>p.teamId===id&&p.eligible&&p.played).length,0))};
}
export function pollDelay(schedule,row,now=Date.now()) {
  const games=row?.snapshot?.games||schedule?.fixtures||[];
  if(games.some(g=>g.regularSeason!==false&&!['completed','canceled','replaced'].includes(g.status)&&Date.parse(g.start)-60*60000<=now&&now-Date.parse(g.start)<12*3600000))return 20000;
  if(games.some(g=>g.status==='in-progress')&&now-Date.parse(row?.verified_at||schedule?.statusAt)<30*60000)return 20000;
  if(games.length&&games.every(g=>['completed','canceled','replaced'].includes(g.status))&&now-Date.parse(row?.source_updated_at)<30*60000)return 20000;
  return 5*60000;
}
const META='league_id,season,matchup_period,scoring_period,scoring_date,schema_version,revision,source_updated_at,verified_at,published_at';
export function createLiveStore(config,{fetcher=fetch,clock=Date.now,timers=globalThis,doc=globalThis.document,win=globalThis.window,base='/'}={}) {
  let state={row:null,error:false,loading:false,now:clock()},ctx=null,schedule=null,timer=null,controller=null,running=false,generation=0,lastSchedule=0,started=false,lastCheck=0;
  const listeners=new Set();
  const emit=patch=>{const next={...state,...patch};next.windowActive=pollDelay(schedule,next.row,next.now)===20000;if(next.windowActive===state.windowActive&&next.row===state.row&&next.error===state.error&&next.loading===state.loading&&Math.floor(next.now/60000)===Math.floor(state.now/60000)&&Boolean(state.row&&next.now-Date.parse(state.row.verified_at)>LIVE_STALE_MS)===Boolean(state.row&&state.now-Date.parse(state.row.verified_at)>LIVE_STALE_MS))return;state=next;listeners.forEach(fn=>fn());};
  const stop=()=>{generation++;if(timer!=null)timers.clearTimeout(timer);timer=null;controller?.abort();controller=null;running=false;};
  const relevant=()=>config.enabled&&config.valid&&ctx?.active&&ctx.leagueId===config.espnLeagueId;
  const plan=()=>{if(started&&relevant()&&doc?.visibilityState!=='hidden')timer=timers.setTimeout(check,pollDelay(schedule,state.row,clock()));};
  async function check() {
    if(running||!started||!relevant()||doc?.visibilityState==='hidden')return;
    if(timer!=null)timers.clearTimeout(timer);timer=null;running=true;lastCheck=clock();const id=generation;
    const ownController=new AbortController();controller=ownController;const signal=ownController.signal,deadline=timers.setTimeout(()=>ownController.abort(),15000);
    if(!state.row)emit({loading:true});
    try {
      if(!schedule||clock()-lastSchedule>=5*60000) {
        try {const r=await fetcher(`${base}data/nba-schedule.json`,{cache:'no-cache',signal});if(r.ok){const value=await r.json();if(value.season===ctx.season)schedule=value;}lastSchedule=clock();}catch(e){if(signal.aborted)throw e;}
      }
      if(signal.aborted||id!==generation)return;
      const url=new URL(config.url+'/rest/v1/live_snapshots');url.search=new URLSearchParams({league_id:'eq.'+config.league,season:'eq.'+ctx.season,select:META,limit:'1'});
      const read=async u=>{const r=await fetcher(u,{headers:{apikey:config.key},cache:'no-store',signal});if(!r.ok)throw Error('Live data unavailable');const rows=await r.json();if(Array.isArray(rows)&&rows.length===0){const error=Error('Live data withdrawn');error.withdrawn=true;throw error;}if(!Array.isArray(rows)||rows.length!==1)throw Error('Live data unavailable');return rows[0];};
      const meta=await read(url.href);let row;
      if(signal.aborted||id!==generation)return;
      if(meta.league_id!==config.league||meta.season!==ctx.season||meta.matchup_period!==ctx.week||meta.scoring_period!==ctx.scoringPeriod||meta.scoring_date!==ctx.date)throw Error('Live period differs from canonical');
      if(state.row?.revision===meta.revision)row={...state.row,...meta};
      else {url.searchParams.set('select',META+',snapshot');row=await read(url.href);}
      if(!validLive(row,ctx,config,clock()))throw Error('Incompatible live snapshot');
      if(state.row&&(Date.parse(row.verified_at)<Date.parse(state.row.verified_at)||Date.parse(row.source_updated_at)<Date.parse(state.row.source_updated_at)))throw Error('Older live snapshot');
      if(id===generation)emit({row:state.row&&JSON.stringify(row)===JSON.stringify(state.row)?state.row:row,error:false,now:clock()});
    } catch(error) {if(id===generation)emit({error:true,row:error.withdrawn?null:state.row,now:clock()});}
    finally {timers.clearTimeout(deadline);if(id===generation){running=false;controller=null;emit({loading:false,now:clock()});plan();}}
  }
  const resume=()=>{if(doc?.visibilityState==='hidden'){stop();return;}if(!running&&clock()-lastCheck>=15000)check();else if(!running&&timer==null)plan();};
  return {
    config,getSnapshot:()=>state,
    subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},
    setContext(value){const scope=c=>JSON.stringify(c&&[c.leagueId,c.season,c.week,c.scoringPeriod,c.date,c.active]);const changed=scope(ctx)!==scope(value);ctx=value;if(changed){stop();schedule=null;lastSchedule=0;emit({row:null,error:false,loading:false,now:clock()});if(started)check();}},
    start(){if(started)return;started=true;doc?.addEventListener('visibilitychange',resume);win?.addEventListener('focus',resume);check();},
    destroy(){started=false;stop();doc?.removeEventListener('visibilitychange',resume);win?.removeEventListener('focus',resume);},
    refresh:check
  };
}
