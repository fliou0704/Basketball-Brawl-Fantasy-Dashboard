export const rankTeamOpacity=(teamId,selectedTeamId)=>selectedTeamId==null || Number(teamId)===Number(selectedTeamId) ? 1 : .16;

export function selectedRankLabel(ranks,selectedTeamId) {
  return selectedTeamId==null ? 'All teams' : ranks.find(team=>Number(team.teamId)===Number(selectedTeamId))?.teamName || 'All teams';
}

export function scoringScale(bars) {
  const max=Math.max(1,...bars.map(bar=>Number(bar.points)||0));
  const magnitude=10**Math.floor(Math.log10(max/4));
  const step=[1,2,5,10].map(n=>n*magnitude).find(n=>n>=max/4);
  const upper=Math.ceil(max/step)*step;
  // Leave space above the tallest bar for its logo and point total.
  const y=value=>215-value/upper*150;
  return {y,ticks:Array.from({length:Math.round(upper/step)+1},(_,i)=>({value:i*step,y:y(i*step)}))};
}

export function standingsAllPlay(history,throughWeek) {
  const scoped=history?.allPlayByWeek?.[throughWeek];
  if(scoped) return scoped;
  const all=history?.allPlay;
  return all?.weeks?.every(week=>week<=Number(throughWeek))?all:null;
}
