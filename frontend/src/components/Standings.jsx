import React from 'react';
import { Section, TableCard } from './Layout';
const base = import.meta.env.BASE_URL;
export function TeamLogo({ team, size = 36 }) {
  return <img src={`${base}${team.logo}`} width={size} height={size} alt="" />;
}
export function Team({ team }) {
  return <span className="team"><TeamLogo team={team}/><span className="team-name">{team.teamName}</span></span>;
}
export default function Standings({ data, final = false }) {
  if (!data?.teams?.length) return null;
  return <Section title={final ? 'Final Standings' : 'Standings'} meta={`Regular season · through Week ${data.statsThroughWeek}`}>
    <TableCard>
    <ol className="mobile-standings" aria-label="Standings">
      {data.teams.map(team => <li key={team.teamId}>
        <div className="mobile-team-heading"><span className="mobile-rank">{team.rank}</span><Team team={team} /><div className="mobile-record"><span className="stat-label">W–L</span><strong>{team.record}</strong></div></div>
        <dl className="mobile-stats"><div><dt>PF</dt><dd>{team.pointsForDisplay}</dd></div><div><dt>PA</dt><dd>{team.pointsAgainstDisplay}</dd></div></dl>
      </li>)}
    </ol>
    <table className="desktop-standings"><caption className="sr-only">Regular-season standings through Week {data.statsThroughWeek}</caption>
      <thead><tr><th className="rank" scope="col">#</th><th scope="col">Team</th><th scope="col" className="record">W–L</th><th scope="col" className="numeric">Points For</th><th scope="col" className="numeric">Points Against</th></tr></thead>
      <tbody>{data.teams.map(team => <tr key={team.teamId}><td className="rank">{team.rank}</td><th scope="row"><Team team={team} /></th><td className="record">{team.record}</td><td className="numeric">{team.pointsForDisplay}</td><td className="numeric">{team.pointsAgainstDisplay}</td></tr>)}</tbody>
    </table></TableCard>
  </Section>;
}
