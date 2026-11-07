// Ordinal ranks: selected metric descending, other metric descending, ESPN ID ascending.
// The complete-pool guard applies before any rank or waiver recommendation is shown.
export function rankTop150(season,mode='total',cutoff=150) {
  if(!season?.completePool||!Array.isArray(season.players)||!Number.isFinite(season.maxTeamGames)||season.maxTeamGames<0||new Set(season.players.map(p=>p.playerId)).size!==season.players.length||season.players.some(p=>!Number.isInteger(p.playerId)||typeof p.name!=='string'||(p.fpts!=null&&(!Number.isFinite(p.fpts)||!Number.isInteger(p.gp)||p.gp<1)))) return {available:false,top:[],below:[],minimumGP:null};
  const minimumGP=Math.max(1,Math.ceil(.25*season.maxTeamGames));
  const metric=mode==='perGame'?'fptsPerGame':'fpts';
  const other=mode==='perGame'?'fpts':'fptsPerGame';
  const rows=season.players.map(p=>({...p,fptsPerGame:p.gp>0&&p.fpts!=null?p.fpts/p.gp:null}));
  const eligible=rows.filter(p=>p.fpts!=null&&(mode!=='perGame'||p.gp>=minimumGP));
  eligible.sort((a,b)=>(b[metric]??0)-(a[metric]??0)||(b[other]??0)-(a[other]??0)||Number(a.playerId)-Number(b.playerId));
  const ranked=eligible.map((p,i)=>({...p,rank:i+1}));
  const rankedIds=new Set(ranked.map(p=>p.playerId));
  const ownership=season.ownershipAvailable;
  return {available:true,minimumGP,all:[...ranked,...rows.filter(p=>!rankedIds.has(p.playerId)).map(p=>({...p,rank:null}))],top:ranked.slice(0,cutoff),below:ownership?[
    ...ranked.slice(cutoff).filter(p=>p.fantasyTeam),
    ...rows.filter(p=>p.fantasyTeam&&!rankedIds.has(p.playerId)).sort((a,b)=>a.playerId-b.playerId).map(p=>({...p,rank:null})),
  ]:[]};
}

export function filterRankings(rows,{search='',team='',position=''}={}){const q=search.toLocaleLowerCase();return rows.filter(p=>p.name.toLocaleLowerCase().includes(q)&&(!team||(team==='FA'?!p.fantasyTeam:String(p.fantasyTeam?.teamId)===team))&&(!position||p.positions?.includes(Number(position))));}
