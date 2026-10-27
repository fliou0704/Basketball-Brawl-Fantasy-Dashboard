import React, { useEffect, useState } from 'react';
import { Card, Section, TableCard } from './components/Layout';
import { Team, TeamLogo } from './components/Standings';
import { PlayerSides } from './components/H2HBreakdown';
import PlayerIdentity from './components/PlayerIdentity';
import { formatPublicationTime } from './home-data';
import { loadMatchupWeek, matchupKey, scoreboardLink } from './scoreboard-data';
import { formatCalendarDate, formatCalendarRange } from './fantasy-calendar';
import { gameTime } from './nba-schedule';
import { orientMatchup, comparisonDays, dailyAdvantage, lineupPairs, summaryPairs } from './matchup-box-score';

const base=import.meta.env.BASE_URL;
const fmt=n=>n==null?'—':n.toLocaleString('en-US',{maximumFractionDigits:1});
const availability=n=>n==null?'Unavailable':fmt(n);

export function Scorecard({match,week,season,updatedAt,rolesVerified}) {
  const status={current:'Live',final:'Final',future:'Upcoming',bye:'Bye','opponent-unavailable':'Opponent unavailable',unavailable:'Score unavailable'}[match.status];
  return <Section title={`${season} Week ${week.week}`} meta={status} className="matchup-scorecard-section"><Card className="matchup-scorecard">
    <p className="box-score-dates">{week.start&&week.end?`${week.dateRangeKind==='observed'?'Observed dates: ':''}${formatCalendarRange(week.start,week.end)}`:'Verified matchup dates unavailable'}</p>
    <div className="facing-scoreboard">{match.teams.map((team,i)=><React.Fragment key={team.teamId}>{i===1&&<span className="score-separator" aria-hidden="true">:</span>}<div className={`facing-team ${i===0?'away':'home'}`} style={{'--side-color':team.color}} data-team-id={team.teamId}>
      <div className="facing-identity"><TeamLogo team={team} size={64}/><div><span className="box-role">{rolesVerified?(i===0?'Away':'Home'):match.bye?'Bye':'Team'}</span><h2>{team.teamName}</h2></div></div><strong className="facing-points" aria-label={`${team.teamName} fantasy points`}>{fmt(match.actualScores?.[i])}<small>FPTS</small></strong>
    </div></React.Fragment>)}</div>
    {match.status==='current'&&updatedAt&&<p className="source-note">Snapshot: <time dateTime={updatedAt}>{formatPublicationTime(updatedAt)} ET</time></p>}
  </Card></Section>;
}
export function DailyComparison({detail,match}) {
  const days=comparisonDays(detail);
  return <Section title="Daily scoring comparison"><TableCard className="daily-box-card"><div className="daily-box-scroll" role="region" aria-label="Daily fantasy points" tabIndex="0">
    <table className="daily-box-table"><caption className="sr-only">Daily fantasy points by team, with official matchup totals</caption><thead><tr><th scope="col">Team</th>{days.map(d=><th key={d.period} scope="col" className={d.future?'future-day':''}><time dateTime={d.date}>{formatCalendarDate(d.date)}</time><small>{d.future?'Upcoming':d.partial?'Live':d.points?'Recorded':'Unavailable'}</small></th>)}<th scope="col" className="box-total">Total</th></tr></thead>
      <tbody>{match.teams.map((team,i)=><tr key={team.teamId}><th scope="row"><span className="daily-team-name"><TeamLogo team={team} size={24}/>{team.teamName}</span></th>{days.map(d=>{const advantage=dailyAdvantage(d);const winner=advantage?.winner===i;return <td key={d.period} className={`${winner?'daily-winner':''} ${d.future?'future-day':''}`} style={{'--daily-color':team.color}}>{d.future?'—':fmt(d.points?.[i])}{winner&&<small className="daily-margin">+{fmt(advantage.margin)}</small>}</td>;})}<td className="box-total">{fmt(match.actualScores?.[i])}</td></tr>)}</tbody>
    </table></div>{!days.length&&<p className="source-note">Verified daily dates are unavailable.</p>}<p className="source-note">{detail.reconciled?'Daily totals reconcile to the scoreboard snapshot.':match.status==='future'?'Scores will appear after play begins.':'Recorded daily scores are incomplete or differ from the official total. Official totals are shown without adjusting daily contributions.'} Dashes indicate unavailable or upcoming scores; a recorded zero is shown as 0.</p>
  </TableCard></Section>;
}
function LineupPlayer({player,home,summary}) {
  if(!player)return <div className="box-player box-empty">No recorded player</div>;
  return <div className={`box-player ${home?'home':'away'}`} data-player-id={player.playerId} data-slot={summary?player.slots.join('/'):player.slot}>
    <div className="box-player-copy"><PlayerIdentity playerId={player.playerId} name={player.name} showHeadshot size={32}/><small>{summary?`Slots: ${player.slots.join(' / ')}`:`Slot: ${player.slot}`}{player.positions?.length?` · ${player.positions.join('/')}`:''}</small><small>{player.nbaTeam?`${player.nbaTeam} · current profile`:'NBA team at game date unavailable'}</small>{!player.eligible&&<small>Bench / IR · {fmt(player.gamePoints)} game FPTS excluded</small>}</div>
    <strong className="box-player-points">{fmt(player.points)}<small>FPTS</small></strong>
  </div>;
}
export function ScoringBreakdown({detail,teams}) {
  const [selected,setSelected]=useState('summary');
  const dates=comparisonDays(detail),day=dates.find(d=>d.date===selected),summary=selected==='summary';
  const players=summary?detail.summaryLineup || []:day?.lineup || [];
  const starters=summary?summaryPairs(players,teams):lineupPairs(players,teams,detail.lineupSlots || []);
  const reserves=summary?summaryPairs(players,teams,true):lineupPairs(players,teams,detail.lineupSlots || [],true);
  return <Section title="Head-to-head scoring breakdown"><Card className="box-breakdown">
    <label className="box-lineup-select">Lineup view<select aria-label="Lineup view" value={selected} onChange={e=>setSelected(e.target.value)}><option value="summary">Summary</option>{dates.map(d=><option key={d.date} value={d.date}>{formatCalendarDate(d.date,'long')}{d.future?' · Upcoming':''}</option>)}</select></label>
    <PlayerSides className="box-lineup-headings">{teams.map((team,i)=><div className={`player-side ${i===1?'home':''}`} style={{'--side-color':team.color}} key={team.teamId}><header><TeamLogo team={team} size={36}/><div><span>{team.teamName}</span><strong>{players.some(p=>p.teamId===team.teamId)?`${fmt(players.filter(p=>p.teamId===team.teamId).reduce((n,p)=>n+p.points,0))} recorded FPTS`:'Recorded points unavailable'}</strong></div></header></div>)}</PlayerSides>
    <p className="source-note">{summary?'Summary ranks each team independently by contributed FPTS. Slots list the positions actually used; this is not a single historical lineup.':day?.future?'Future lineup unavailable. No planned lineup is assumed.':'Complete daily lineup unavailable. These are verified slot assignments for players with recorded stats; players without stat records may be missing.'} NBA affiliations are from the current player profile; historical NBA teams are unavailable.</p>
    {[['Scoring starters',starters],['Bench / IR · excluded from fantasy totals',reserves]].map(([label,pairs])=><div className="box-lineup-group" key={label}><h3>{label}</h3>{pairs.length?pairs.map((pair,index)=><PlayerSides className="box-lineup-row" key={`${pair.label}-${index}`}>{pair.players.map((p,i)=><LineupPlayer key={teams[i].teamId} player={p} home={i===1} summary={summary}/>)}</PlayerSides>):<p className="source-note">{day?.future?'Lineup not available yet.':'No recorded players available.'}</p>}</div>)}
  </Card></Section>;
}
function Opportunities({detail,teams}) {
  const periods=[...new Set(detail.remaining.flatMap(r=>r.days.map(d=>d.period)))].sort((a,b)=>a-b);
  return <Section title="Remaining opportunities"><Card>{teams.map((team,i)=><div className="opportunity-team" key={team.teamId}><h3><Team team={team}/></h3><p>Recorded played starts: <strong>{detail.completedStarts[i]}</strong> · Confirmed scheduled games: <strong>{availability(detail.remaining[i].games)}</strong> · Potential starts: <strong>{detail.remaining[i].potentialStarts==null?'Unavailable':`Up to ${fmt(detail.remaining[i].potentialStarts)}`}</strong></p><p className="source-note">{detail.remaining[i].reason}</p>{(detail.remaining[i].inProgress>0||detail.remaining[i].startedUnconfirmed>0)&&<p className="source-note">{detail.remaining[i].inProgress || 0} player-games in progress · {detail.remaining[i].startedUnconfirmed || 0} started/unconfirmed; excluded from future counts.</p>}</div>)}{detail.scheduleVerifiedAt&&<p className="source-note">Current roster and game snapshot: {formatPublicationTime(detail.opportunitiesUpdatedAt)} ET. NBA schedule verified: {formatPublicationTime(detail.scheduleVerifiedAt)} ET. Counts are player-game opportunities for the current roster.</p>}</Card>{!!periods.length && <TableCard><div className="matchup-table-scroll"><table><caption>Daily schedule · games / potential starts · in-progress games excluded</caption><thead><tr><th>Day</th>{teams.map(t=><th key={t.teamId}>{t.teamName}</th>)}</tr></thead><tbody>{periods.map(p=><tr key={p}><th>{formatCalendarDate(detail.remaining.flatMap(r=>r.days).find(d=>d.period===p)?.date)}</th>{detail.remaining.map((r,i)=>{const d=r.days.find(d=>d.period===p);return <td key={i}>{availability(d?.games)} / {availability(d?.potentialStarts)}{d?.additionalTBD?' · Additional games TBD':''}{d?.inProgress?` · ${d.inProgress} started/unconfirmed`:''}</td>;})}</tr>)}</tbody></table></div></TableCard>}<PlayerOpportunities detail={detail} teams={teams}/></Section>;
}
function PlayerOpportunities({detail,teams}) {
  return <div className="opportunity-player-details">{detail.remaining.map((r,i)=>!!r.players.length&&<details key={teams[i].teamId}><summary>{teams[i].teamName} · Player opportunities</summary>{r.players.map(p=><div className="opportunity-player" key={p.playerId}><PlayerIdentity playerId={p.playerId} name={p.name} showHeadshot/><p>{p.games==null?'Remaining schedule unavailable':`${p.games.length} confirmed scheduled games`}{p.slot?` · ${p.slot}`:''}{p.injuryStatus?` · ${p.injuryStatus}`:''}</p>{p.additionalTBD&&<p className="source-note">Additional NBA Cup or postponed games: TBD.</p>}{p.games?.map(g=><p key={g.id}>{formatCalendarDate(g.date)} · {gameTime(g)} · vs {g.opponent ?? 'Opponent unavailable'}</p>)}</div>)}</details>)}</div>;
}
export default function MatchupDetail({season,week,match,updatedAt,refreshCount=0}) {
  const [snapshot,setSnapshot]=useState(null),[error,setError]=useState(false);
  const matchVersion=JSON.stringify(match);
  const detailPath=week.detailPath,detailVersion=week.detailVersion;
  const checkpoint=detailVersion?null:updatedAt;
  const requestVersion=JSON.stringify([detailPath,detailVersion,matchVersion,checkpoint]);
  // A successful manifest check retries a failed detail, but leaves loaded versions alone.
  useEffect(()=>{
    if(snapshot?.version===requestVersion && !error)return;
    let alive=true;
    setError(false);
    if(match&&detailPath)loadMatchupWeek(base,detailPath,checkpoint,fetch,detailVersion).then(data=>{
      if(!alive)return;
      const found=data.matchups.find(m=>m.key===matchupKey(match));
      if(found)setSnapshot({detail:found,match,updatedAt,version:requestVersion});
      setError(!found);
    }).catch(()=>{if(alive)setError(true);});
    else setError(true);
    return()=>{alive=false;};
  },[requestVersion,refreshCount]);
  const detail=snapshot?.detail;
  const oriented=match?orientMatchup(snapshot?.match || match,detail):null;
  return <div className="matchup-box-score"><h1 className="sr-only">{season} Week {week.week} matchup</h1><a className="matchup-back" href={scoreboardLink(season,week.week)}>← {season} Week {week.week} Matchups</a>
    {!match?<Card><p role="status">This matchup is unavailable. Return to the scoreboard to choose a matchup.</p></Card>:<>
      <Scorecard match={oriented.match} rolesVerified={oriented.rolesVerified} season={season} week={week} updatedAt={snapshot?.updatedAt ?? updatedAt}/>
      {!detail?<Card><p role={error?'alert':'status'}>{error?'Matchup details unavailable. Reload to retrieve the latest snapshot.':'Loading matchup details…'}</p></Card>:<>
        <DailyComparison detail={oriented.detail} match={oriented.match}/>
        <ScoringBreakdown detail={oriented.detail} teams={oriented.match.teams}/>
        <Opportunities detail={oriented.detail} teams={oriented.match.teams}/>
        {error&&<p className="source-note" role="status">Refresh failed. Showing the last complete matchup snapshot; updates will retry automatically.</p>}
      </>}
    </>}
  </div>;
}
