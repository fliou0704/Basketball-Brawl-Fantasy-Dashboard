import React from 'react';
import { Card, Section, TableCard } from './Layout';
export function SeasonLeaders({ players }) {
  if (!players?.length) return null;
  return <Section title="Season Leaders" meta="Rostered players"><TableCard><ol className="season-leaders">{players.map(p=><li key={p.playerId}><span className="leader-rank">{p.rank}</span><div><h3>{p.name}</h3><p>{p.teams.map(t=>t.teamName).join(' / ')}</p></div><strong>{p.pointsDisplay}<small>FPTS</small></strong></li>)}</ol></TableCard></Section>;
}
export function SeasonHistory({ data }) {
  if (!data) return null;
  return <Section title="Regular Season"><div className="history-grid">
    <Card as="figure" title="Rank Progression"><svg className="rank-chart" viewBox="0 0 320 230" role="img" aria-label="Weekly regular-season team rank progression. Rank one is at the top.">
      {data.rankTicks.map(t=><g key={t.rank}><line x1="25" x2="300" y1={t.y} y2={t.y} stroke="#e0e4da"/><text x="8" y={t.y+4}>{t.rank}</text></g>)}
      {data.ranks.map(t=><polyline key={t.teamId} points={t.path} fill="none" stroke={t.color} strokeWidth="2"><title>{t.teamName}</title></polyline>)}
      <text x="25" y="225">Week 1</text><text x="250" y="225">Week {data.weeks[data.weeks.length-1]}</text>
    </svg><ul className="chart-legend">{data.ranks.map(t=><li key={t.teamId}><span style={{background:t.color}}/>{t.teamName}</li>)}</ul></Card>
    <Card as="figure" title="Weekly Scoring Leaders"><ol className="weekly-highs">{data.highWeeks.map(t=><li key={t.week}><span className="week-number">{t.week}</span><div><div className="bar-label"><span>{t.teamName}</span><strong>{t.pointsDisplay}</strong></div><div className="bar" style={{width:t.width,background:t.color}}/></div></li>)}</ol></Card>
  </div></Section>;
}
