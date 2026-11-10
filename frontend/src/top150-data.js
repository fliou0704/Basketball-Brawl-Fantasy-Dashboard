// Ordinal ranks: selected metric descending, other metric descending, ESPN ID ascending.
// The complete-pool guard applies before any rank or waiver recommendation is shown.
export function rankTop150(season,mode='total',cutoff=150) {
  if(!season?.completePool||!Array.isArray(season.players)||season.players.length===0||season.players.some(p=>!p||typeof p!=='object')||!Number.isFinite(season.maxTeamGames)||season.maxTeamGames<0||new Set(season.players.map(p=>p.playerId)).size!==season.players.length||season.players.some(p=>!Number.isInteger(p.playerId)||typeof p.name!=='string'||(p.fpts!=null&&(!Number.isFinite(p.fpts)||!Number.isInteger(p.gp)||p.gp<1)))) return {available:false,top:[],below:[],minimumGP:null};
  const minimumGP=Math.max(1,Math.ceil(.25*season.maxTeamGames));
  const metric=mode==='perGame'?'fptsPerGame':'fpts';
  const other=mode==='perGame'?'fpts':'fptsPerGame';
  const order=(a,b)=>(b[metric]??0)-(a[metric]??0)||(b[other]??0)-(a[other]??0)||a.playerId-b.playerId;
  const rows=season.players.map(p=>({...p,fptsPerGame:p.gp>0&&p.fpts!=null?p.fpts/p.gp:null}));
  const valid=rows.filter(p=>p.fpts!=null).sort(order);
  const eligible=valid.filter(p=>mode!=='perGame'||p.gp>=minimumGP);
  const ranks=new Map(eligible.map((p,i)=>[p.playerId,i+1]));
  const ranked=valid.map(p=>({...p,rank:ranks.get(p.playerId)??null}));
  const noGames=rows.filter(p=>p.fpts==null).sort((a,b)=>a.playerId-b.playerId).map(p=>({...p,rank:null}));
  const all=[...ranked,...noGames];
  const eligibleTop=new Set(eligible.slice(0,cutoff).map(p=>p.playerId));
  // With fewer than cutoff qualifiers, bound low-sample entries to the top
  // cutoff valid averages, while keeping every qualifier. No-game rows stay out.
  const shortField=new Set(ranked.slice(0,cutoff).map(p=>p.playerId));
  const boundary=eligible[cutoff-1];
  const top=ranked.filter(p=>eligibleTop.has(p.playerId)||(mode==='perGame'&&p.rank==null&&
    (boundary?order(p,boundary)<=0:shortField.has(p.playerId))));
  const shown=new Set(top.map(p=>p.playerId));
  const below=season.ownershipAvailable?all.filter(p=>p.fantasyTeam&&!shown.has(p.playerId)):[];
  return {available:true,minimumGP,all,top,below,eligibleShown:top.filter(p=>p.rank!=null).length,
    ineligibleShown:top.filter(p=>p.rank==null).length};
}

export function filterRankings(rows,{search='',team='',position=''}={}){const q=search.toLocaleLowerCase();return rows.filter(p=>p.name.toLocaleLowerCase().includes(q)&&(!team||(team==='FA'?!p.fantasyTeam&&p.ownershipStatus!=='unknown':String(p.fantasyTeam?.teamId)===team))&&(!position||p.positions?.includes(Number(position))));}
