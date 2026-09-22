export function normalizePlayerSearch(value) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/gi,' ').trim().toLowerCase();
}

export function searchPlayers(players, query, limit=8) {
  const term=normalizePlayerSearch(query);
  if(!term) return [];
  return players.filter(player=>normalizePlayerSearch(player.name).includes(term)).slice(0,limit);
}

export function clearPlayerSearch() { return ''; }

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
