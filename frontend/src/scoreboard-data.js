import {loadOpportunities} from './nba-schedule.js';
export const matchupStatus = {final:'Final', current:'In progress', future:'Not started', bye:'Bye', 'opponent-unavailable':'Opponent unavailable', unavailable:'Final score unavailable'};
export function scoreboardRoute(route) {
  const match = route.match(/^#\/?scoreboard(?:\?(.*))?$/);
  if (!match) return null;
  const query = new URLSearchParams(match[1] || '');
  return {season:query.get('season'), week:query.get('week'), ...(query.has('match') ? {match:query.get('match')} : {})};
}
export function scoreboardLink(season, week) {
  return `#/scoreboard?season=${season}&week=${week}`;
}
export function selectScoreboard(data, requested = {}) {
  const year = requested.season == null ? data.current.season : Number(requested.season);
  const season = data.seasons.find(s=>s.season === year);
  if (!season) return null;
  const week = requested.week == null ? (year === data.current.season ? data.current.week : season.weeks.at(-1)?.week) : Number(requested.week);
  const selected = season.weeks.find(w=>w.week === week);
  return selected ? {season, selected} : null;
}
export function adjacentWeek(data, season, week, step) {
  const choices = data.seasons.flatMap(s=>s.weeks.map(w=>({season:s.season, week:w.week})));
  const index = choices.findIndex(c=>c.season === season && c.week === week);
  return index < 0 ? null : choices[index+step] || null;
}
export async function loadScoreboard(base, fetcher = fetch) {
  const response = await fetcher(`${base}data/scoreboard.json`, {cache:'no-cache'});
  if (!response.ok) throw new Error('Scoreboard unavailable');
  const data = await response.json();
  if (data.schemaVersion !== 1) throw new Error('Unsupported scoreboard');
  return {data};
}

export function matchupKey(match) { return match.teams.map(t=>t.teamId).sort((a,b)=>a-b).join('-'); }
export function matchupLink(season, week, match) { return `${scoreboardLink(season,week)}&match=${matchupKey(match)}`; }
export async function loadMatchupWeek(base, path, updatedAt, fetcher=fetch, detailVersion=null) {
  const response=await fetcher(`${base}data/${path}`,{cache:'no-cache'});
  if(!response.ok) throw new Error('Matchup details unavailable');
  const data=await response.json();
  if(data.schemaVersion!==1 || (detailVersion ? data.detailVersion!==detailVersion : data.updatedAt!==updatedAt)) throw new Error('Matchup snapshot changed; refresh the scoreboard.');
  if(data.opportunitiesPath) {
    try {
    const {opportunities,schedule}=await loadOpportunities(base,data.opportunitiesPath,updatedAt,fetcher);
    const games=new Map(schedule.fixtures.map(g=>[g.id,g]));
    const names=new Map(schedule.teams.map(t=>[t.id,t.abbrev]));
    for(const match of data.matchups) {
      match.scheduleVerifiedAt=opportunities.verifiedAt;
      match.opportunitiesUpdatedAt=opportunities.updatedAt;
      match.remaining=match.teamIds.map(id=>{
        const result=opportunities.weeks[String(data.week)]?.[String(id)];
        if(!result) throw new Error('Matchup opportunities unavailable');
        return {...result,players:result.players.map(p=>({...p,games:p.gameIds==null?null:p.gameIds.map(gid=>{
          const g=games.get(gid);if(!g) throw new Error('Schedule snapshot changed');
          return {...g,opponent:names.get(g.home===p.proTeamId?g.away:g.home)};
        })}))};
      });
    }
    } catch {
      // Optional schedule failures must not hide canonical actual scores.
      for(const match of data.matchups) {
        match.scheduleError='Remaining schedule unavailable. Reload to try the latest schedule.';
        match.remaining=match.remaining.map(r=>({...r,projection:null,games:null,potentialStarts:null,days:[],players:[],reason:match.scheduleError}));
      }
    }
  }
  return data;
}

// Unchanged static exports should not trigger another detail fetch/render cycle.
export function retainSnapshot(previous, next) {
  return previous && JSON.stringify(previous)===JSON.stringify(next) ? previous : next;
}
