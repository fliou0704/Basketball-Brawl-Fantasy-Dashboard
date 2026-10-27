// Presentation only. Keep every positional score/opportunity aligned with its team ID.
export function orientMatchup(match, detail) {
  const away=detail?.awayTeamId ?? match.awayTeamId;
  const home=detail?.homeTeamId ?? match.homeTeamId;
  const ids=away!=null&&home!=null?[away,home]:match.teams.map(t=>t.teamId);
  const order=ids.map(id=>match.teams.findIndex(t=>t.teamId===id));
  const reorder=values=>values==null?values:order.map(i=>values[i]);
  return {match:{...match,teams:reorder(match.teams),actualScores:reorder(match.actualScores),scoreDisplay:reorder(match.scoreDisplay)},
    detail:detail?{...detail,completedStarts:reorder(detail.completedStarts),remaining:reorder(detail.remaining),
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
  const position=p=>p.slots?.join(' / ') || p.slot || 'Unknown slot';
  const rank=p=>{const slot=p.slots?.[0] || p.slot;const index=slots.indexOf(slot);return index<0?slots.length:index;};
  const labels=[...new Set(rows.sort((a,b)=>rank(a)-rank(b)||position(a).localeCompare(position(b))).map(position))];
  return labels.flatMap(label=>{
    const sides=teams.map(t=>rows.filter(p=>p.teamId===t.teamId&&position(p)===label).sort((a,b)=>b.points-a.points||a.playerId-b.playerId));
    return Array.from({length:Math.max(...sides.map(s=>s.length))},(_,i)=>({label,players:sides.map(s=>s[i] || null)}));
  });
}
