import React from 'react';
import {PlayerSides} from './H2HBreakdown';
import PlayerIdentity from './PlayerIdentity';
import {formatCalendarDate} from '../fantasy-calendar';
import {projectedFinal,projectionDay,projectedPlayers} from '../matchup-box-score';
const fmt=n=>n==null?'Unavailable':n.toLocaleString('en-US',{maximumFractionDigits:1});

export function ProjectionSummary({detail,match}) {
  if(!detail || ['final','bye','unavailable','opponent-unavailable'].includes(match.status))return null;
  return <div className="matchup-estimates"><p className="estimate-label">Optimal-lineup estimates</p><PlayerSides>{match.teams.map((team,i)=>{
    const projection=detail.remaining[i]?.projection;
    return <div key={team.teamId} className="estimate-team"><strong>{team.teamName}</strong><dl><div><dt>Projected remaining</dt><dd>{fmt(projection?.remaining)}</dd></div><div><dt>Projected final</dt><dd>{fmt(projectedFinal(match,detail,i))}</dd></div></dl>{projection?.remaining==null&&projection?.confirmedRemaining!=null&&<p className="source-note">Confirmed-game subtotal: {fmt(projection.confirmedRemaining)} FPTS</p>}{projection?.remaining==null&&<p className="source-note">{projection?.reason || 'Completed NBA samples and verified schedules are required.'}</p>}</div>;
  })}</PlayerSides><p className="source-note">Last 10 completed NBA regular-season games, with smaller samples labeled per player. Maximum 10 eligible starters per day. Estimates assume participation; they are not manager-selected lineups or guaranteed outcomes.</p></div>;
}
export function PotentialPoints({detail,teams}) {
  if(!detail?.potential?.some(p=>p.completedDays>0))return null;
  const dates=[...new Set(detail.potential.flatMap(p=>p.days.map(d=>d.date)))].sort();
  return <details className="potential-points"><summary>Potential Points · {detail.potential.every(p=>p.points==null)?'Unavailable (incomplete historical rosters)':'historical optimal lineup'}</summary><PlayerSides>{teams.map((team,i)=>{
    const p=detail.potential[i];return <div key={team.teamId}><strong>{team.teamName}</strong><dl><div><dt>Potential Points</dt><dd>{fmt(p.points)}</dd></div><div><dt>Points left on bench</dt><dd>{fmt(p.leftOnBench)}</dd></div><div><dt>Lineup efficiency</dt><dd>{p.efficiency==null?'Unavailable':`${(p.efficiency*100).toFixed(1)}%`}</dd></div></dl><p className="source-note">{p.coveredDays}/{p.completedDays} dates have complete evidence. {p.reason}</p></div>;
  })}</PlayerSides><div className="matchup-table-scroll"><table><caption>Daily potential points · incomplete historical evidence stays unavailable</caption><thead><tr><th>Date</th>{teams.map(t=><th key={t.teamId}>{t.teamName}</th>)}</tr></thead><tbody>{dates.map(date=><tr key={date}><th>{formatCalendarDate(date)}</th>{detail.potential.map((p,i)=><td key={i}>{fmt(p.days.find(d=>d.date===date)?.points)}</td>)}</tr>)}</tbody></table></div></details>;
}
export function ProjectedLineups({detail,teams,date}) {
  const days=teams.map((_,i)=>projectionDay(detail,date,i));
  if(!days.some(d=>d?.players?.length))return <p className="source-note">Projected player-games unavailable for this date.</p>;
  return <div className="projected-lineups"><h3>Optimal projected lineup · {formatCalendarDate(date)}</h3><p className="source-note">Current roster, verified future fixtures and trailing completed-game averages. Each scheduled player keeps an individual estimate, including projected bench and IR players.</p><PlayerSides>{teams.map((t,i)=><p key={t.teamId}><strong>{t.teamName}: {fmt(days[i]?.points)} FPTS</strong>{days[i]?.reason&&<small>{days[i].reason}</small>}{days[i]?.additionalTBD&&<small>Additional games TBD; confirmed games only.</small>}</p>)}</PlayerSides>
    {[['Optimal projected starters',true],['Other scheduled players · not counted in the optimal total',false]].map(([label,selected])=><div className="box-lineup-group" key={label}><h3>{label}</h3>{projectedPlayers(detail,date,teams,selected).map((pair,index)=><PlayerSides className="box-lineup-row" key={index}>{pair.players.map((p,i)=>!p?<div className="box-player box-empty" key={teams[i].teamId}>No scheduled player</div>:<div className={`box-player ${i===0?'away':'home'}`} key={teams[i].teamId} data-projected-player={p.playerId}><div className="box-player-copy"><PlayerIdentity playerId={p.playerId} name={p.name || String(p.playerId)} showHeadshot size={32}/><small>{p.selected==null?'Selection unavailable':p.selected?`Optimal starter · ${p.assignedSlot}`:['IR','IR+','IL'].includes(p.slot)?'IR · excluded':'Projected bench'}</small>{p.injuryStatus&&!['ACTIVE','NORMAL','HEALTHY'].includes(p.injuryStatus)&&<small>Status: {p.injuryStatus} · participation uncertain</small>}<small>{p.sampleSize} completed NBA games · regular season{p.firstDate?` · ${formatCalendarDate(p.firstDate,'year')} – ${formatCalendarDate(p.lastDate,'year')}`:''}</small>{p.sampleSize<10&&<small>Limited sample</small>}</div><strong className="box-player-points">{fmt(p.points)}<small>Est. FPTS</small></strong></div>)}</PlayerSides>)}</div>)}
  </div>;
}
