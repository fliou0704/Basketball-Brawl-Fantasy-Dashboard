export function teamIdFromRoute(route) {
  return route.match(/^#\/?teams\/(\d+)$/)?.[1] || null;
}

export function playerRoute(route) {
  if (route==='#/players' || route==='#players') return {playerId:null};
  const match=route.match(/^#\/?players\/(\d+)$/);
  return match ? {playerId:match[1]} : null;
}

export function nextExpandedId(current, clicked) {
  return current === clicked ? null : clicked;
}

export function h2hRoute(route) {
  if (route==='#/historical-h2h' || route==='#historical-h2h' || route==='#/h2h/historical') return {mode:'historical',key:'h2h-historical'};
  if (route==='#/h2h/theoretical') return {mode:'theoretical',key:'h2h-theoretical'};
  return null;
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
