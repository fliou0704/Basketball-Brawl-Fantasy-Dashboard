import React from 'react';
import { Section, TableCard } from './Layout';
import { Team } from './Standings';

export default function AllPlay({data}) {
  if(!data?.teams?.length)return null;
  const pct=t=>`${(t.winPct*100).toFixed(1)}%`;
  return <Section title="All-Play Standings" meta={`${data.weeks.length} completed regular-season weeks`}>
    <TableCard><ol className="mobile-standings" aria-label="All-Play Standings">{data.teams.map(t=><li key={t.teamId}><div className="mobile-team-heading"><span className="mobile-rank">{t.rank}</span><Team team={t} link/><div className="mobile-record"><span className="stat-label">W–L–T</span><strong>{t.record}</strong></div></div><dl className="mobile-stats"><div><dt>Win %</dt><dd>{pct(t)}</dd></div></dl></li>)}</ol>
    <table className="desktop-standings"><caption className="sr-only">All-Play Standings</caption><thead><tr><th>#</th><th>Team</th><th className="numeric">W–L–T</th><th className="numeric">Win %</th></tr></thead><tbody>{data.teams.map(t=><tr key={t.teamId}><td>{t.rank}</td><th><Team team={t} link/></th><td className="numeric">{t.record}</td><td className="numeric">{pct(t)}</td></tr>)}</tbody></table></TableCard>
    <p className="source-note">Official weekly FPTS against every other team. Ties count as half a win. Only complete regular-season fields count; byes and playoffs are excluded. Tiebreakers: wins, included-week FPTS, then franchise ID.</p>
  </Section>;
}
