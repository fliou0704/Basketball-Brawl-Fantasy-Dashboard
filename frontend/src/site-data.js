export function teamIdFromRoute(route) {
  return route.match(/^#\/?teams\/(\d+)$/)?.[1] || null;
}

export function latestTeamSeason(data) {
  return Object.keys(data?.seasons || {}).filter(year=>data.seasons[year]).map(Number).sort((a,b)=>b-a)[0]?.toString() || 'Summary';
}

export function selectSeasonView(manifest, season, standings, playoffs, requestedDate) {
  const calendar=manifest.calendars.find(item=>item.season===Number(season));
  const finalWeek=Math.max(...Object.keys(standings).map(Number));
  let playoffKey=null;
  if(calendar?.complete && playoffs.final) playoffKey='final';
  else {
    const state=manifest.states[requestedDate];
    if(state?.season===Number(season) && state.phase==='playoffs' && state.playoffKey && playoffs[state.playoffKey]) playoffKey=state.playoffKey;
  }
  return {standings:standings[String(finalWeek)], bracket:playoffKey?playoffs[playoffKey]:null, complete:calendar?.complete};
}
