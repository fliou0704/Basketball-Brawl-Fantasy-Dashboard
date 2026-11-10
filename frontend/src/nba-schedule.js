// Shared published fixtures and current affiliations; no historical reassignment.
import {leagueDate} from './home-data.js';
export function fixturesByTeam(data, team) {
  return data?.fixtures?.filter(g=>g.regularSeason && [g.home,g.away].includes(Number(team))) ?? [];
}
export function fixturesByDate(data, date) {
  return data?.fixtures?.filter(g=>g.regularSeason && g.date===date) ?? [];
}
export function playerFutureGames(data, player, snapshot) {
  if(!data?.publishedComplete || data.lastError || !data.verifiedAt || new Date(snapshot)-new Date(data.verifiedAt)>30*60*60*1000) return null;
  const team=data?.playerAffiliations?.[String(player)];
  if(team==null) return null;
  return fixturesByTeam(data,team).filter(g=>!g.hasStarted && ['scheduled','tbd'].includes(g.status) && (g.timeTBD ? g.date>leagueDate(new Date(snapshot)) : new Date(g.start)>new Date(snapshot)));
}
export function gameTime(game) {
  if(game.timeTBD) return 'Time TBD';
  return `${new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'}).format(new Date(game.start))} ET`;
}

const shared=new Map();
export async function loadOpportunities(base, path, updatedAt, fetcher=fetch) {
  const key=`${base}:${path}:${updatedAt}`;
  if(!shared.has(key)) {
    const read=async path=>{
      const response=await fetcher(`${base}data/${path}`,{cache:'no-cache'});
      if(!response.ok) throw new Error('Schedule unavailable');
      const value=await response.json();
      if(value.updatedAt!==updatedAt) throw new Error('Schedule snapshot changed; refresh the scoreboard.');
      return value;
    };
    shared.set(key,Promise.all([read(path),read('nba-schedule.json')]).then(([opportunities,schedule])=>{
      if(opportunities.schemaVersion!==1 || schedule.schemaVersion!==2) throw new Error('Unsupported schedule');
      return {opportunities,schedule};
    }).catch(error=>{shared.delete(key);throw error;}));
    if(shared.size>2) shared.delete(shared.keys().next().value);
  }
  return shared.get(key);
}
