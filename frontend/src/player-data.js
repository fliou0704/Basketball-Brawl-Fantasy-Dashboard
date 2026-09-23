export function normalizePlayerSearch(value) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/gi,' ').trim().toLowerCase();
}

export function searchPlayers(players, query, limit=8) {
  const term=normalizePlayerSearch(query);
  if(!term) return [];
  return players.filter(player=>normalizePlayerSearch(player.name).includes(term)).slice(0,limit);
}

export function clearPlayerSearch() { return ''; }

export const PLAYER_TABS=['career','game-log','transactions'];
export const PLAYER_GAME_STATS=['FPTS','MIN','PTS','REB','AST','STL','BLK','3PM','TO','FGM','FGA','FTM','FTA'];
export function defaultPlayerTab() { return PLAYER_TABS[0]; }
export function selectPlayerTab(tab) { return PLAYER_TABS.includes(tab)?tab:defaultPlayerTab(); }
export function recentPlayerGames(games,limit=5) { return [...games].sort((a,b)=>b.date.localeCompare(a.date)).slice(0,limit); }
export function latestPlayerGameSeason(seasons) { return [...seasons].map(Number).sort((a,b)=>b-a)[0]??null; }
export function formatPlayerGameDate(value) { const [year,month,day]=String(value).split('-'); return `${month}/${day}/${year.slice(-2)}`; }

export function playerHref(playerId, base='/') {
  const value=String(playerId??'');
  return /^\d+$/.test(value)&&Number(value)>0 ? `${base}#/players/${value}` : null;
}

export function ageOnDate(birthDate, now=new Date()) {
  const [year,month,day]=String(birthDate||'').split('-').map(Number);
  if(!year || !month || !day) return null;
  let age=now.getFullYear()-year;
  if(now.getMonth()+1<month || (now.getMonth()+1===month && now.getDate()<day)) age--;
  return age;
}

export function formatHeight(inches) {
  if(inches==null || inches==='') return null;
  const value=Number(inches);
  return `${Math.floor(value/12)}′ ${value%12}″`;
}
