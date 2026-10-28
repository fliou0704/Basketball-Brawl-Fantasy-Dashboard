import React, { useState } from 'react';
import { Card, Section, TableCard } from './Layout';
import { TeamLogo } from './Standings';

export const FRANCHISE_TABS=[['performance','Performance'],['achievements','Achievements'],['roster','All-Time Roster']];
const number=value=>value==null?'Unavailable':Number(value).toLocaleString(undefined,{maximumFractionDigits:2});
const ordinal=value=>value==null?'—':`${value}${value%100>=11&&value%100<=13?'th':value%10===1?'st':value%10===2?'nd':value%10===3?'rd':'th'}`;

function Trend({ data, note }) {
  const [hover,setHover]=useState(null);
  if(!data)return null;
  return <Card as="figure" className="franchise-trend"><h3>{data.label}</h3><div className="franchise-chart-scroll"><svg className="weekly-performance-chart franchise-chart" viewBox={data.viewBox.join(' ')} role="img" aria-label={data.label}>
    {data.ticks.map(tick=><g key={tick.value}><line x1="54" x2="770" y1={tick.y} y2={tick.y}/><text x="46" y={tick.y+4} textAnchor="end">{tick.display}</text></g>)}
    {data.points.map((point,index)=>{const previous=data.points[index-1];return <g key={point.year}>
      {previous?.y!=null&&point.y!=null&&<line className="franchise-trend-line" x1={previous.x} y1={previous.y} x2={point.x} y2={point.y} strokeDasharray={point.partial?'5 4':undefined}/>}
      {point.y!=null&&<circle cx={point.x} cy={point.y} r="5" className={point.partial?'franchise-partial':''} tabIndex="0" aria-label={`${point.year}: ${point.display}${point.partial?' · Partial season':''}`} onClick={()=>setHover(point)} onMouseEnter={()=>setHover(point)} onFocus={()=>setHover(point)} onMouseLeave={()=>setHover(null)} onBlur={()=>setHover(null)}><title>{`${point.year}: ${point.display}${point.partial?' · Partial season':''}`}</title></circle>}
      <text x={point.x} y="233" textAnchor="middle">{point.year}{point.partial?'*':''}</text>{point.y==null&&<text x={point.x} y="218" textAnchor="middle">N/A</text>}
    </g>;})}<text x="412" y="254" textAnchor="middle">Season</text>
  </svg></div><figcaption><span className="franchise-hover" aria-live="polite">{hover?`${hover.year}: ${hover.display}${hover.partial?' · Partial season':''}`:'Hover or focus a point for details.'}</span>{note}</figcaption></Card>;
}

function History({ rows, onSeason }) {
  return <Section title="Season-by-Season History" meta="Select a season to explore"><TableCard className="franchise-history-scroll"><table className="team-roster franchise-history"><thead><tr>{['Season','Team / Owner','Record','Regular PF','FP/Start','Regular Rank','Final Rank','Playoff Finish'].map(label=><th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.year} onClick={()=>onSeason(String(row.year))}>
    <th scope="row"><button className="franchise-season-link" onClick={event=>{event.stopPropagation();onSeason(String(row.year));}}>{row.year}</button>{!row.complete&&<small>In progress</small>}</th>
    <td><div className="franchise-historical-team" style={{'--historical-color':row.team.color}}><TeamLogo team={row.team} size={34}/><div><strong>{row.team.teamName}</strong><small>{row.owners.join(' / ')}</small></div></div></td><td>{row.record}<small>{row.regularWeeks} / {row.scheduledRegularWeeks??'—'} weeks</small></td><td>{number(row.regularFpts)}</td><td>{number(row.fpPerStart)}</td><td>{ordinal(row.regularRank)}{!row.complete?'*':''}</td><td>{ordinal(row.finalRank)}</td><td className={row.champion?'franchise-champion':''}>{row.playoffFinish}</td>
  </tr>)}</tbody></table></TableCard><p className="source-note">Record, PF and regular rank match the season Team overview. * Current position, not a final finish. Historical identities follow the same franchise ID.</p></Section>;
}

export default function FranchiseProfile({ profile, records, roster, onSeason }) {
  const [tab,setTab]=useState('performance');
  if(!profile)return <><Section title="All-Time Record"><Card><dl className="team-records">{records.map(record=><div key={record.label}><dt>{record.label}</dt><dd>{record.value}</dd></div>)}</dl></Card></Section>{roster}</>;
  const totals=profile.totals;
  return <div className="franchise-profile">
    <Section title="Franchise Career" meta={`${totals.completedSeasons} completed seasons`}><Card><dl className="franchise-career">{[
      ['Seasons played',totals.seasons],['Championships',totals.championships],['Finals appearances',totals.championshipAppearances],['Playoff appearances',totals.playoffAppearances],
      ['Regular-season record',`${totals.wins}–${totals.losses}`],['Winning percentage',totals.winPct==null?'—':`${(totals.winPct*100).toFixed(1)}%`],['All-time FPTS',number(totals.fpts)],['FP/Start',number(totals.fpPerStart)],
    ].map(([label,value])=><div key={label} className={label==='Championships'?'franchise-title-stat':''}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></Card><p className="source-note">Performance includes all recorded seasons, including the current partial season. FPTS includes all recorded matchup types; appearances and titles count completed seasons only. FP/Start uses eligible player FPTS, excludes byes, and can differ from frozen scoreboard totals. It is unavailable when player-game coverage cannot be verified.</p></Section>
    <nav className="team-tabs" role="tablist" aria-label="Franchise sections">{FRANCHISE_TABS.map(([key,label])=><button id={`franchise-tab-${key}`} key={key} role="tab" aria-selected={tab===key} aria-controls={`franchise-panel-${key}`} onClick={()=>setTab(key)}>{label}</button>)}</nav>
    <div id={`franchise-panel-${tab}`} role="tabpanel" aria-labelledby={`franchise-tab-${tab}`}>
      {tab==='performance'&&<><Section title="All-Time Record"><Card><dl className="team-records">{records.map(record=><div key={record.label}><dt>{record.label}</dt><dd>{record.value}</dd></div>)}</dl></Card></Section><History rows={profile.history} onSeason={onSeason}/><Section title="Franchise Trends"><div className="franchise-trends"><Trend data={profile.trends.fpts} note="Total FPTS across all recorded matchups. * Partial season; totals vary with season length."/><Trend data={profile.trends.regularRank} note="Regular-season position; 1st is at the top. * In-progress standing. Final finishes are listed in the history table."/><Trend data={profile.trends.fpPerStart} note="Eligible player FPTS ÷ credited starts; bye weeks excluded. Gaps indicate unverified history; * partial season."/></div></Section></>}
      {tab==='achievements'&&<><Section title="Season Highs & Lows"><Card><dl className="team-records"><div><dt>Best completed season</dt><dd>{profile.bestSeason??'Not yet available'}</dd></div><div><dt>Worst completed season</dt><dd>{profile.worstSeason??'Not yet available'}</dd></div></dl><p className="source-note">By regular-season winning percentage, then regular rank and PF. Unfinished seasons are excluded.</p></Card></Section><Section title="Franchise Records"><Card><ul className="franchise-achievements">{profile.records.map(record=><li key={record.label}><div><h3>{record.label}</h3><p>{record.team.teamName} · {record.year}, Week {record.week}</p></div><strong>{record.value}</strong></li>)}</ul></Card></Section><Section title="Notable Achievements" meta="Completed seasons"><Card><ul className="franchise-achievements">{profile.achievements.map(item=><li key={`${item.year}-${item.title}`}><TeamLogo team={item.team} size={44}/><div><h3 className={item.title==='League champion'?'franchise-champion':''}>{item.year} · {item.title}</h3><p>{item.team.teamName} · {item.detail}</p></div></li>)}</ul>{!profile.achievements.length&&<p>No completed-season titles, finals appearances or regular-season first-place finishes recorded.</p>}</Card></Section></>}
      {tab==='roster'&&roster}
    </div>
  </div>;
}
