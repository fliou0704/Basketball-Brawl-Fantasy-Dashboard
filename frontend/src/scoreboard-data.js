export const matchupStatus = {final:'Final', current:'In progress', future:'Not started', bye:'Bye', 'opponent-unavailable':'Opponent unavailable', unavailable:'Final score unavailable'};
export function scoreboardRoute(route) {
  const match = route.match(/^#\/?scoreboard(?:\?(.*))?$/);
  if (!match) return null;
  const query = new URLSearchParams(match[1] || '');
  return {season:query.get('season'), week:query.get('week')};
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
  return {data, publishedAt:response.headers.get('last-modified')};
}
