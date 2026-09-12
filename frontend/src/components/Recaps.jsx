import React from 'react';
import { Team } from './Standings';
export const dateLabel = value => new Intl.DateTimeFormat('en-US', {month:'short',day:'numeric',timeZone:'UTC'}).format(new Date(`${value}T12:00:00Z`));
export function Match({ match, completed = true }) {
  return <div className="match">{match.teams.map((team,i) => <div key={team.teamId} className={`match-team ${completed && match.winnerId === team.teamId ? 'winner' : ''} ${completed && match.winnerId && match.winnerId !== team.teamId ? 'eliminated' : ''}`}><Team team={team} /><strong>{match.scoreDisplay?.[i] ?? '—'}</strong></div>)}</div>;
}
function Lineup({ players, playoffs }) {
  if (!players?.length) return null;
  return <div className="lineup-section"><h3>{playoffs ? 'Playoff Team of the Week' : 'Team of the Week'}</h3><div className="lineup">{players.map((p,i)=><article key={`${p.playerId}-${i}`} className={p.mvp?'lineup-player mvp':'lineup-player'}>
    <span className="slot">{p.slot}</span><div><h4>{p.name}{p.mvp && <span className="mvp-label"> · MVP</span>}</h4><p>{p.team.teamName}</p></div><strong>{p.pointsDisplay}<small>FPTS</small></strong>
  </article>)}</div></div>;
}
export function Weekly({ recap, playoffOnly = false }) {
  if (!recap || (playoffOnly && !recap.playoffs)) return null;
  return <section className="home-section weekly-recap"><div className="section-title"><h2>{recap.playoffs ? 'Playoff Recap' : 'Weekly Recap'}</h2><span>Week {recap.week} · {dateLabel(recap.end)}</span></div>
    <div className="recap-highlights"><div><h3>Top Team{recap.leaders.length>1?'s':''}</h3>{recap.leaders.map(t=><div className="team-highlight" key={t.teamId}><Team team={t} /><strong>{t.pointsDisplay}<small>FPTS</small></strong></div>)}</div>
    {!!recap.closest.length && <div><h3>Closest Matchup <span className="subtle">· {recap.closest[0].marginDisplay} point margin</span></h3>{recap.closest.map((m,i)=><Match key={i} match={m}/>)}</div>}</div>
    {recap.playoffs && <div className="playoff-results"><h3>Round Results</h3>{recap.matches.map((m,i)=><Match key={i} match={m}/>)}</div>}
    <Lineup players={recap.lineup} playoffs={recap.playoffs}/>
  </section>;
}
const stat = (p, name) => p.stats[name] ?? '—';
export function Daily({ recap }) {
  if (!recap?.players?.length) return null;
  return <section className="home-section daily-recap"><div className="section-title"><h2>Daily Recap</h2><span>{dateLabel(recap.date)}</span></div>
    {!!recap.leaders.length && <div className="daily-winner"><h3>Top Team{recap.leaders.length>1?'s':''}</h3>{recap.leaders.map(t=><div className="team-highlight" key={t.teamId}><Team team={t}/><strong>{t.pointsDisplay}<small>FPTS</small></strong></div>)}</div>}
    <h3 className="performances-title">Top Performances</h3><div className="performances">{recap.players.map(p=><article className="performance" key={`${p.playerId}-${p.team.teamId}`}>
      <div className="performance-heading"><div><h4>{p.name}</h4><p>{p.team.teamName}{p.bench?' · Bench / IR':''}</p></div><strong>{p.pointsDisplay}<small>FPTS</small></strong></div>
      <dl className="stat-line">{['PTS','REB','AST','BLK','STL','TO'].map(k=><div key={k}><dt>{k}</dt><dd>{stat(p,k)}</dd></div>)}<div><dt>FGM/A</dt><dd>{stat(p,'FGM')}/{stat(p,'FGA')}</dd></div><div><dt>3PM/A</dt><dd>{stat(p,'3PM')}/{stat(p,'3PA')}</dd></div></dl>
    </article>)}</div><p className="source-note">3PA unavailable. Bench performances included.</p>
  </section>;
}
export function Scoreboard({ recap, week }) {
  if (!recap?.scoreboard?.length || recap.week !== week) return null;
  return <section className="home-section"><div className="section-title"><h2>Current Matchups</h2><span>Week {week} · through {dateLabel(recap.date)}</span></div><div className="scoreboard">{recap.scoreboard.map((m,i)=><Match key={i} match={m} completed={false}/>)}</div></section>;
}
export function Around({ recap }) {
  if (!recap?.insights?.length) return null;
  return <section className="home-section"><div className="section-title"><h2>Around the League</h2><span>Through Week {recap.week}</span></div><div className="insights">{recap.insights.map(card=><article key={card.title}><h3>{card.title}</h3><Team team={card.team}/><p>{card.value}</p></article>)}</div></section>;
}
