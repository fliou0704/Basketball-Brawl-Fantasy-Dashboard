// Presentation only. Keep every positional score/opportunity aligned with its team ID.
export function orientMatchup(match, detail) {
  const away=detail?.awayTeamId ?? match.awayTeamId;
  const home=detail?.homeTeamId ?? match.homeTeamId;
  const ids=away!=null&&home!=null?[away,home]:match.teams.map(t=>t.teamId);
  const order=ids.map(id=>match.teams.findIndex(t=>t.teamId===id));
  const reorder=values=>values==null?values:order.map(i=>values[i]);
  return {match:{...match,teams:reorder(match.teams),actualScores:reorder(match.actualScores),scoreDisplay:reorder(match.scoreDisplay)},
    detail:detail?{...detail,completedStarts:reorder(detail.completedStarts),remaining:reorder(detail.remaining),potential:reorder(detail.potential),
      days:detail.days.map(d=>({...d,points:reorder(d.points),cumulative:reorder(d.cumulative)}))}:null,
    rolesVerified:away!=null&&home!=null};
}
export function comparisonDays(detail) {
  const recorded=new Map(detail.days.map(d=>[d.period,d]));
  return (detail.calendarDays || detail.days).map(d=>({...d,...recorded.get(d.period),future:Boolean(d.future)}));
}
export function dailyAdvantage(day) {
  if(day.future || !day.points || day.points.length!==2 || day.points.some(p=>p==null))return null;
  const difference=day.points[0]-day.points[1];
  return {winner:difference===0?null:difference>0?0:1,margin:Math.abs(difference)};
}
export function lineupPairs(players, teams, slots, reserves=false) {
  const rows=players.filter(p=>Boolean(p.eligible)!==reserves);
  const position=p=>p.slot || 'Unknown slot';
  const ordered=[...new Set([...(slots.length?slots:['PG','SG','SF','PF','C','G','F','UT']), 'BE', 'IR'])];
  const rank=p=>{const index=ordered.indexOf(p.slot==='UTIL'?'UT':p.slot);return index<0?ordered.length:index;};
  const labels=[...new Set(rows.sort((a,b)=>rank(a)-rank(b)||position(a).localeCompare(position(b))).map(position))];
  return labels.flatMap(label=>{
    const sides=teams.map(t=>rows.filter(p=>p.teamId===t.teamId&&position(p)===label).sort((a,b)=>a.playerId-b.playerId));
    return Array.from({length:Math.max(...sides.map(s=>s.length))},(_,i)=>({label,players:sides.map(s=>s[i] || null)}));
  });
}

// Summary is a pair of independently ranked lists, never a fantasy-slot lineup.
export function summaryPairs(players, teams, reserves=false) {
  const sides=teams.map(t=>players.filter(p=>p.teamId===t.teamId && Boolean(p.eligible)!==reserves)
    .sort((a,b)=>b.points-a.points || a.playerId-b.playerId));
  return Array.from({length:Math.max(0,...sides.map(s=>s.length))},(_,i)=>({label:String(i),players:sides.map(s=>s[i] || null)}));
}

export function projectedFinal(match,detail,index) {
  const actual=match.status==='future'?0:match.actualScores?.[index];
  const remaining=detail?.remaining?.[index]?.projection?.remaining;
  return match.status==='final'||actual==null||remaining==null?null:actual+remaining;
}
export function projectionDay(detail,date,index) {
  return detail?.remaining?.[index]?.projection?.days?.find(d=>d.date===date) ?? null;
}
export function projectedAdvantage(detail,date) {
  const days=[projectionDay(detail,date,0),projectionDay(detail,date,1)];
  if(days.some(d=>d?.points==null))return null;
  const difference=days[0].points-days[1].points;
  return {winner:difference===0?null:difference>0?0:1,margin:Math.abs(difference)};
}
export function projectedPlayers(detail,date,teams,selected=true) {
  const sides=teams.map((team,i)=>{
    const members=new Map((detail.remaining[i]?.players || []).map(p=>[p.playerId,p]));
    return (projectionDay(detail,date,i)?.players || []).filter(p=>(p.selected===true)===selected)
      .map(p=>({...members.get(p.playerId),...p,teamId:team.teamId,projected:true}))
      .sort((a,b)=>(b.points ?? -Infinity)-(a.points ?? -Infinity)||a.playerId-b.playerId);
  });
  return Array.from({length:Math.max(0,...sides.map(s=>s.length))},(_,i)=>({label:String(i),players:sides.map(s=>s[i] || null)}));
}
