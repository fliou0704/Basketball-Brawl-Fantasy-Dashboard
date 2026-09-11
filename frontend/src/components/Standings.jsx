import React from 'react';
const base = import.meta.env.BASE_URL;
export function Team({ team }) {
  return <span className="team"><img src={`${base}${team.logo}`} width="36" height="36" alt="" /><span className="team-name">{team.teamName}</span></span>;
}
export default function Standings({ data, final = false }) {
  if (!data?.teams?.length) return null;
  return <section className="home-section">
    <div className="section-title"><h2>{final ? 'Final regular-season standings' : 'Regular-season standings'}</h2><span>Through Week {data.statsThroughWeek}</span></div>
    <ol className="mobile-standings" aria-label="Standings">
      {data.teams.map(team => <li key={team.teamId}>
        <div className="mobile-team-heading"><span className="mobile-rank">{team.rank}</span><Team team={team} /><div className="mobile-record"><span className="stat-label">W–L</span><strong>{team.record}</strong></div></div>
        <dl className="mobile-stats"><div><dt>PF</dt><dd>{team.pointsForDisplay}</dd></div><div><dt>PA</dt><dd>{team.pointsAgainstDisplay}</dd></div></dl>
      </li>)}
    </ol>
    <table className="desktop-standings"><caption className="sr-only">Regular-season standings through Week {data.statsThroughWeek}</caption>
      <thead><tr><th className="rank" scope="col">#</th><th scope="col">Team</th><th scope="col" className="record">W–L</th><th scope="col" className="numeric">Points for</th><th scope="col" className="numeric">Points against</th></tr></thead>
      <tbody>{data.teams.map(team => <tr key={team.teamId}><td className="rank">{team.rank}</td><th scope="row"><Team team={team} /></th><td className="record">{team.record}</td><td className="numeric">{team.pointsForDisplay}</td><td className="numeric">{team.pointsAgainstDisplay}</td></tr>)}</tbody>
    </table>
  </section>;
}
