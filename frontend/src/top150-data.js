// Ordinal ranks: selected metric descending, other metric descending, ESPN ID ascending.
// The complete-pool guard applies before any rank or waiver recommendation is shown.
export function rankTop150(season,mode='total',cutoff=150) {
  if(!season?.completePool) return {available:false,top:[],below:[],minimumGP:null};
  const minimumGP=Math.max(1,Math.ceil(.25*season.maxTeamGames));
  const metric=mode==='perGame'?'fptsPerGame':'fpts';
  const other=mode==='perGame'?'fpts':'fptsPerGame';
  const rows=season.players.map(p=>({...p,fptsPerGame:p.gp>0&&p.fpts!=null?p.fpts/p.gp:null}));
  const eligible=rows.filter(p=>p.fpts!=null&&(mode!=='perGame'||p.gp>=minimumGP));
  eligible.sort((a,b)=>(b[metric]??0)-(a[metric]??0)||(b[other]??0)-(a[other]??0)||Number(a.playerId)-Number(b.playerId));
  const ranked=eligible.map((p,i)=>({...p,rank:i+1}));
  const rankedIds=new Set(ranked.map(p=>p.playerId));
  const ownership=season.ownershipAvailable;
  return {available:true,minimumGP,top:ranked.slice(0,cutoff),below:ownership?[
    ...ranked.slice(cutoff).filter(p=>p.fantasyTeam),
    ...rows.filter(p=>p.fantasyTeam&&!rankedIds.has(p.playerId)).sort((a,b)=>a.playerId-b.playerId).map(p=>({...p,rank:null})),
  ]:[]};
}
