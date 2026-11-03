import React, { useState } from 'react';
import { Section, TableCard } from './Layout';
const base = import.meta.env.BASE_URL;
export function TeamLogo({ team, size = 36 }) {
  const fallback = `${base}logos/Default.png`;
  return <img src={team.logo ? `${base}${team.logo}` : fallback} width={size} height={size} alt="" onError={event=>{event.currentTarget.onerror=null;event.currentTarget.src=fallback;}}/>;
}
export function Team({ team, link = false }) {
  const content=<><TeamLogo team={team}/><span className="team-name">{team.teamName}</span></>;
  return link?<a className="team team-link" href={`${base}#/teams/${team.teamId}`}>{content}</a>:<span className="team">{content}</span>;
}
export function allPlayRecord(team) {
  if(!team)return '—';
  return `${team.wins}-${team.losses}${team.ties?`-${team.ties}`:''}`;
}
export default function Standings({ data, allPlay, final = false, linkTeams = false }) {
  const [sort,setSort]=useState(null);
  if (!data?.teams?.length) return null;
  const lookup=new Map((allPlay?.teams||[]).map(team=>[Number(team.teamId),team]));
  const rows=[...data.teams];
  if(sort)rows.sort((a,b)=>sort==='desc'?(lookup.get(Number(a.teamId))?.rank??Infinity)-(lookup.get(Number(b.teamId))?.rank??Infinity):(lookup.get(Number(b.teamId))?.rank??-Infinity)-(lookup.get(Number(a.teamId))?.rank??-Infinity));
  const toggle=()=>setSort(sort==='desc'?'asc':'desc');
  const sortButton=<button type="button" className="all-play-sort" onClick={toggle}>All-Play W-L{sort==='desc'?' ↓':sort==='asc'?' ↑':''}</button>;
  return <Section className={allPlay?'combined-standings':''} title={final ? 'Final Standings' : 'Standings'} meta={`Regular season · through Week ${data.statsThroughWeek}`}>
    {allPlay&&<div className="mobile-standings">{sortButton}</div>}
    <TableCard>
    <ol className="mobile-standings" aria-label="Standings">
      {rows.map(team => <li key={team.teamId}>
        <div className="mobile-team-heading"><span className="mobile-rank">{team.rank}</span><Team team={team} link={linkTeams}/><div className="mobile-record"><span className="stat-label">W–L</span><strong>{team.record}</strong></div></div>
        <dl className="mobile-stats">{allPlay&&<div><dt>All-Play W-L</dt><dd>{allPlayRecord(lookup.get(Number(team.teamId)))}</dd></div>}<div><dt>PF</dt><dd>{team.pointsForDisplay}</dd></div><div><dt>PA</dt><dd>{team.pointsAgainstDisplay}</dd></div></dl>
      </li>)}
    </ol>
    <table className="desktop-standings"><caption className="sr-only">Regular-season standings through Week {data.statsThroughWeek}</caption>
      <thead><tr><th className="rank" scope="col">#</th><th scope="col">Team</th><th scope="col" className="record">W–L</th>{allPlay&&<th scope="col" className="numeric" aria-sort={sort==='desc'?'descending':sort==='asc'?'ascending':'none'}>{sortButton}</th>}<th scope="col" className="numeric">Points For</th><th scope="col" className="numeric">Points Against</th></tr></thead>
      <tbody>{rows.map(team => <tr key={team.teamId}><td className="rank">{team.rank}</td><th scope="row"><Team team={team} link={linkTeams}/></th><td className="record">{team.record}</td>{allPlay&&<td className="numeric">{allPlayRecord(lookup.get(Number(team.teamId)))}</td>}<td className="numeric">{team.pointsForDisplay}</td><td className="numeric">{team.pointsAgainstDisplay}</td></tr>)}</tbody>
    </table></TableCard>
  </Section>;
}
