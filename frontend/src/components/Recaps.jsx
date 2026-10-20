import React from 'react';
import { Team } from './Standings';
import { Card, Section } from './Layout';
import PlayerIdentity from './PlayerIdentity';
export const dateLabel = value => new Intl.DateTimeFormat('en-US', {month:'short',day:'numeric',timeZone:'UTC'}).format(new Date(`${value}T12:00:00Z`));
export function Match({ match, completed = true }) {
  return <div className="match">{match.teams.map((team,i) => <div key={team.teamId} className={`match-team ${completed && match.winnerId === team.teamId ? 'winner' : ''} ${completed && match.winnerId && match.winnerId !== team.teamId ? 'eliminated' : ''}`}><Team team={team} /><strong>{match.scoreDisplay?.[i] ?? '—'}</strong></div>)}</div>;
}
function Lineup({ players, playoffs }) {
  if (!players?.length) return null;
  return <Card className="lineup-section" title={playoffs ? 'Playoff Team of the Week' : 'Team of the Week'}><div className="lineup">{players.map((p,i)=><article key={`${p.playerId}-${i}`} className={p.mvp?'lineup-player mvp':'lineup-player'}>
    <span className="slot">{p.slot}</span><div><h4><PlayerIdentity playerId={p.playerId} name={p.name} showHeadshot/>{p.mvp && <span className="mvp-label"> · MVP</span>}</h4><p>{p.team.teamName}</p></div><strong>{p.pointsDisplay}<small>FPTS</small></strong>
  </article>)}</div></Card>;
}
export function Weekly({ recap, playoffOnly = false }) {
  if (!recap || (playoffOnly && !recap.playoffs)) return null;
  return <Section className="weekly-recap" title={recap.playoffs ? 'Playoff Recap' : 'Weekly Recap'} meta={`Week ${recap.week} · ${dateLabel(recap.end)}`}>
    <div className="recap-highlights"><Card title={`Top Team${recap.leaders.length>1?'s':''}`}>{recap.leaders.map(t=><div className="team-highlight" key={t.teamId}><Team team={t} /><strong>{t.pointsDisplay}<small>FPTS</small></strong></div>)}</Card>
    {!!recap.closest.length && <Card title={`Closest Matchup · ${recap.closest[0].marginDisplay} point margin`}>{recap.closest.map((m,i)=><Match key={i} match={m}/>)}</Card>}</div>
    {recap.playoffs && <Card className="playoff-results" title="Round Results">{recap.matches.map((m,i)=><Match key={i} match={m}/>)}</Card>}
    <Lineup players={recap.lineup} playoffs={recap.playoffs}/>
  </Section>;
}
const stat = (p, name) => p.stats[name] ?? '—';
export function Daily({ recap }) {
  if (!recap?.players?.length) return null;
  return <Section className="daily-recap" title="Daily Recap" meta={dateLabel(recap.date)}>
    <div className="daily-grid">{!!recap.leaders.length && <Card className="daily-winner" title={`Top Team${recap.leaders.length>1?'s':''}`}>{recap.leaders.map(t=><div className="team-highlight" key={t.teamId}><Team team={t}/><strong>{t.pointsDisplay}<small>FPTS</small></strong></div>)}</Card>}
    <Card className="performances-card" title="Top Performances"><div className="performances">{recap.players.map((p,index)=><article className="performance" key={`${p.playerId}-${p.team.teamId}`}>
      <span className="performance-rank">{index+1}</span><div className="performance-body"><div className="performance-heading"><div><h4><PlayerIdentity playerId={p.playerId} name={p.name} showHeadshot/></h4><p>{p.team.teamName}{p.bench?' · Bench / IR':''}</p></div><strong>{p.pointsDisplay}<small>FPTS</small></strong></div>
      <dl className="stat-line">{['PTS','REB','AST','BLK','STL','TO'].map(k=><div key={k}><dt>{k}</dt><dd>{stat(p,k)}</dd></div>)}<div><dt>FGM/A</dt><dd>{stat(p,'FGM')}/{stat(p,'FGA')}</dd></div><div><dt>3PM/A</dt><dd>{stat(p,'3PM')}/{stat(p,'3PA')}</dd></div></dl>
    </div></article>)}</div><p className="source-note">3PA unavailable. Bench performances included.</p></Card></div>
  </Section>;
}
export function Scoreboard({ recap, week }) {
  if (!recap?.scoreboard?.length || recap.week !== week) return null;
  return <Section title="Current Matchups" meta={`Week ${week} · through ${dateLabel(recap.date)}`}><Card><div className="scoreboard">{recap.scoreboard.map((m,i)=><Match key={i} match={m} completed={false}/>)}</div></Card></Section>;
}
export function CurrentWeek({ snapshot, publishedAt, stale, refreshFailed }) {
  const timestamp = publishedAt && !Number.isNaN(Date.parse(publishedAt))
    ? new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(publishedAt)) : null;
  return <>
    <Section title="Current Fantasy Scoreboard" meta={`${snapshot.season} · Week ${snapshot.week} · Week in Progress${stale?' · Older snapshot':''}`}>
      <Card><p className="current-week-context">Latest available · {dateLabel(snapshot.asOfDate)} · Scoring Period {snapshot.scoringPeriod}{timestamp && <> · Published <time dateTime={new Date(publishedAt).toISOString()}>{timestamp}</time></>}</p>
        {(stale || refreshFailed) && <p className="source-note" role="status">{refreshFailed?'Unable to check for newer data. ':''}Showing the latest available snapshot. {stale?'The scoring period or week may have advanced since this update.':''}</p>}
        <div className="scoreboard">{snapshot.matchups.map((match,index)=><Match key={index} match={match} completed={false}/>)}</div>
        {!snapshot.matchups.length && <p className="source-note">Matchup assignments are not available in the latest snapshot.</p>}
      </Card>
    </Section>
    <Section title="Best Player Performances" meta={`Week ${snapshot.week} · Individual games`}>
      <Card>{snapshot.players.length ? <div className="performances">{snapshot.players.map((player,index)=><article className="performance" key={`${player.playerId}-${player.scoringPeriod}`}>
        <span className="performance-rank">{index+1}</span><div className="performance-body"><div className="performance-heading"><div><h4><PlayerIdentity playerId={player.playerId} name={player.name} showHeadshot/></h4><p>{player.team.teamName} · <time dateTime={player.date}>{dateLabel(player.date)}</time></p></div><strong>{player.pointsDisplay}<small>FPTS</small></strong></div></div>
      </article>)}</div> : <p className="current-week-empty">No player performances are available for this week yet.</p>}
        <p className="source-note">Latest available individual-game scores; performances may still be in progress.</p>
      </Card>
    </Section>
  </>;
}
export function Around({ recap }) {
  if (!recap?.insights?.length) return null;
  return <Section title="Around the League" meta={`Through Week ${recap.week}`}><Card><div className="insights">{recap.insights.map(card=><article key={card.title}><h3>{card.title}</h3><Team team={card.team}/><p>{card.value}</p></article>)}</div></Card></Section>;
}
