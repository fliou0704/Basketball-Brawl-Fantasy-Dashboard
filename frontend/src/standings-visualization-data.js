export const rankTeamOpacity=(teamId,selectedTeamId)=>selectedTeamId==null || Number(teamId)===Number(selectedTeamId) ? 1 : .16;

export function selectedRankLabel(ranks,selectedTeamId) {
  return selectedTeamId==null ? 'All teams' : ranks.find(team=>Number(team.teamId)===Number(selectedTeamId))?.teamName || 'All teams';
}
