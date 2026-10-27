import React from 'react';
import { Team } from './Standings';
import { Card, Section } from './Layout';
import PlayerIdentity from './PlayerIdentity';
import PlayerStatLine from './PlayerStatLine';
import { formatPublicationTime } from '../home-data';
export const dateLabel = value => new Intl.DateTimeFormat('en-US', {month:'short',day:'numeric',timeZone:'UTC'}).format(new Date(`${value}T12:00:00Z`));
export function Match({ match, completed = true }) {
  return <div className="match">{match.teams.map((team,i) => <div key={team.teamId} className={`match-team ${completed && match.winnerId === team.teamId ? 'winner' : ''} ${completed && match.winnerId && match.winnerId !== team.teamId ? 'eliminated' : ''}`}><Team team={team} /><strong>{match.scoreDisplay?.[i] ?? '—'}</strong></div>)}</div>;
}
function Lineup({ players, playoffs }) {
  if (!players?.length) return null;
  return <Card className="lineup-section" title={playoffs ? 'Playoff Team of the Week' : 'Team of the Week'}><div className="lineup">{players.map((p,i)=><article key={`${p.playerId}-${i}`} className={p.mvp?'lineup-player mvp':'lineup-player'}>
    <span className="slot">{p.slot}</span><div className="lineup-identity"><h4><PlayerIdentity playerId={p.playerId} name={p.name} showHeadshot/>{p.mvp && <span className="mvp-label"> · MVP</span>}</h4><p className="lineup-fantasy-team"><Team team={p.team}/></p></div><strong>{p.pointsDisplay}<small>FPTS</small></strong>
    <WeeklyPlayerStats stats={p.weeklyStats}/>
  </article>)}</div><p className="source-note">Statistics reflect played fantasy starts for this team and week.</p></Card>;
}
export function WeeklyPlayerStats({ stats }) {
  const value = n => n == null ? '—' : String(n);
  const average = n => n == null ? '—' : n.toFixed(1);
  const shooting = (made, attempted, pct) => `${value(made)}/${value(attempted)} (${pct == null ? '—' : `${pct.toFixed(1)}%`})`;
  return <dl className="weekly-player-stats">
    <div><dt>GP</dt><dd>{value(stats?.gamesPlayed)}</dd></div>
    {['PTS','REB','AST','BLK','STL','TO'].map(key=><div key={key}><dt>{key}/G</dt><dd>{average(stats?.perGame?.[key])}</dd></div>)}
    <div><dt>FG</dt><dd>{shooting(stats?.totals?.FGM,stats?.totals?.FGA,stats?.shooting?.['FG%'])}</dd></div>
    <div><dt>3PT</dt><dd>{shooting(stats?.totals?.['3PM'],stats?.totals?.['3PA'],stats?.shooting?.['3P%'])}</dd></div></dl>;
}
export function Weekly({ recap, playoffOnly = false }) {
  if (!recap || (playoffOnly && !recap.playoffs)) return null;
  return <Section className="weekly-recap" title={`Week ${recap.week} Recap`} meta={`Week ${recap.week} · ${dateLabel(recap.end)}`}>
    <div className="recap-highlights"><Card title={`Top Team${recap.leaders.length>1?'s':''}`}>{recap.leaders.map(t=><div className="team-highlight" key={t.teamId}><Team team={t} /><strong>{t.pointsDisplay}<small>FPTS</small></strong></div>)}</Card>
    {!!recap.closest.length && <Card title={`Closest Matchup · ${recap.closest[0].marginDisplay} point margin`}>{recap.closest.map((m,i)=><Match key={i} match={m}/>)}</Card>}</div>
    {recap.playoffs && <Card className="playoff-results" title="Round Results">{recap.matches.map((m,i)=><Match key={i} match={m}/>)}</Card>}
    <Lineup players={recap.lineup} playoffs={recap.playoffs}/>
  </Section>;
}
export function Daily({ recap }) {
  if (!recap?.players?.length) return null;
  const title = new Intl.DateTimeFormat('en-US', {month:'long',day:'numeric',year:'numeric',timeZone:'America/New_York'}).format(new Date(`${recap.date}T12:00:00Z`));
  return <Section className="daily-recap" title={`${title} Recap`}>
    <div className="daily-grid">{!!recap.leaders.length && <Card className="daily-winner" title={`Top Team${recap.leaders.length>1?'s':''}`}>{recap.leaders.map(t=><div className="team-highlight" key={t.teamId}><Team team={t}/><strong>{t.pointsDisplay}<small>FPTS</small></strong></div>)}</Card>}
    <Card className="performances-card" title="Top Performances"><div className="performances">{recap.players.map((p,index)=><article className="performance" key={`${p.playerId}-${p.team.teamId}`}>
      <span className="performance-rank">{index+1}</span><div className="performance-body"><div className="performance-heading"><div><h4><PlayerIdentity playerId={p.playerId} name={p.name} showHeadshot/></h4><p>{p.team.teamName}{p.bench?' · Bench / IR':''}</p></div><strong>{p.pointsDisplay}<small>FPTS</small></strong></div>
      <PlayerStatLine stats={p.stats}/>
    </div></article>)}</div><p className="source-note">Bench performances included.</p></Card></div>
  </Section>;
}
export function Scoreboard({ recap, week }) {
  if (!recap?.scoreboard?.length || recap.week !== week) return null;
  return <Section title="Current Matchups" meta={`Week ${week} · through ${dateLabel(recap.date)}`}><Card><div className="scoreboard">{recap.scoreboard.map((m,i)=><Match key={i} match={m} completed={false}/>)}</div></Card></Section>;
}
export function CurrentWeek({ snapshot, publishedAt, showPerformances = true }) {
  const timestamp = formatPublicationTime(publishedAt);
  return <>
    <Section title={`${snapshot.season} Week ${snapshot.week} Scoreboard`}>
      <Card>{timestamp && <p className="current-week-context">Last updated: <time dateTime={new Date(publishedAt).toISOString()}>{timestamp}</time></p>}
        <div className="scoreboard">{snapshot.matchups.map((match,index)=><Match key={index} match={match} completed={false}/>)}</div>
        {!snapshot.matchups.length && <p className="source-note">Matchup assignments are not available in the latest snapshot.</p>}
      </Card>
    </Section>
    {showPerformances && <CurrentWeekPerformances snapshot={snapshot}/>}
  </>;
}
export function CurrentWeekPerformances({ snapshot }) {
  if (!snapshot.players.length) return null;
  return <Section title={`Best Week ${snapshot.week} Performances`} meta="Individual games">
      <Card><div className="performances">{snapshot.players.map((player,index)=><article className="performance" key={`${player.playerId}-${player.scoringPeriod}`}>
        <span className="performance-rank">{index+1}</span><div className="performance-body"><div className="performance-heading"><div><h4><PlayerIdentity playerId={player.playerId} name={player.name} showHeadshot/></h4><p>{player.team.teamName} · <time dateTime={player.date}>{dateLabel(player.date)}</time></p></div><strong>{player.pointsDisplay}<small>FPTS</small></strong></div><PlayerStatLine stats={player.stats}/></div>
      </article>)}</div>
      </Card>
    </Section>;
}
