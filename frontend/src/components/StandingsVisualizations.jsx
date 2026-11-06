import React, { useState } from 'react';
import { Card, Section } from './Layout';
import { TeamLogo } from './Standings';
import { scoringScale } from '../standings-visualization-data';
import { rankTeamOpacity, selectedRankLabel } from '../standings-visualization-data';

const ordinal=value=>`${value}${value%100>=11&&value%100<=13?'th':value%10===1?'st':value%10===2?'nd':value%10===3?'rd':'th'}`;

export default function StandingsVisualizations({ data }) {
  const [teamId,setTeamId]=useState(null);
  if(!data?.weeks?.length&&!data?.scoringWeekTicks?.length) return null;
  const scale=scoringScale(data.highWeeks);
  const rankWeeks=data.rankWeekTicks || data.weeks.map((week,index)=>({week,x:data.ranks[0]?.points[index]?.x}));
  const chartWidth=Math.max(800,Math.max(rankWeeks.length,data.scoringWeekTicks?.length||0)*42);
  const selected=teamId==null ? null : Number(teamId);
  const rankLabel=selectedRankLabel(data.ranks,selected);
  return <Section className="standings-visualizations" title="Season Visualizations" meta="Completed matchup weeks">
    <div className="standings-graphs">
      <Card as="figure" title="Weekly Scoring Leaders"><div className="standings-chart-scroll"><svg className="standings-chart scoring-leaders-chart" style={{minWidth:chartWidth}} viewBox={data.viewBox.join(' ')} role="img" aria-label="Highest-scoring fantasy team by completed matchup week">
        <line x1="54" x2="770" y1="215" y2="215" className="chart-axis"/>
        {scale.ticks.map(tick=><g key={tick.value}><line x1="54" x2="770" y1={tick.y} y2={tick.y}/></g>)}
        {data.highWeeks.map(bar=>{const y=scale.y(bar.points);return <g key={bar.week} aria-label={`Week ${bar.week}: ${bar.teamName}, ${bar.pointsDisplay} FPTS`}><rect x={bar.x} y={y} width={bar.width} height={215-y} rx="3" fill={bar.color}/><image href={`${import.meta.env.BASE_URL}${bar.logo||'logos/Default.png'}`} x={bar.x+bar.width/2-10} y={y-25} width="20" height="20" onError={event=>{event.currentTarget.onerror=null;event.currentTarget.setAttribute('href',`${import.meta.env.BASE_URL}logos/Default.png`);}}/><text x={bar.x+bar.width/2} y={Math.max(12,y-29)} textAnchor="middle">{bar.pointsDisplay}</text></g>;})}
        {(data.scoringWeekTicks || data.highWeeks.map(b=>({week:b.week,x:b.x+b.width/2}))).map(t=><text key={t.week} x={t.x} y="233" textAnchor="middle">{t.week}</text>)}<text x="412" y="254" textAnchor="middle" className="chart-axis-label">Matchup Week</text><text x="13" y="25" className="chart-axis-label">FPTS</text>
      </svg></div></Card>
      <Card as="figure" title="League Rank Progression"><div className="rank-chart-controls" aria-label="Rank progression team filter"><button type="button" aria-pressed={selected==null} onClick={()=>setTeamId(null)}>All teams</button>{data.ranks.map(team=><button key={team.teamId} type="button" aria-pressed={selected===team.teamId} onClick={()=>setTeamId(team.teamId)}><i style={{background:team.color}}/><TeamLogo team={team} size={20}/>{team.teamName}</button>)}</div><div className="standings-chart-scroll"><svg className="standings-chart rank-progression-chart" style={{minWidth:chartWidth}} viewBox={data.viewBox.join(' ')} role="img" aria-label={`Weekly league rank progression for ${rankLabel}. Rank one is at the top.`}>
        {data.rankTicks.map(tick=><g key={tick.rank}><line x1="54" x2="770" y1={tick.y} y2={tick.y}/><text x="45" y={tick.y+4} textAnchor="end">{ordinal(tick.rank)}</text></g>)}
        {data.ranks.map(team=><g key={team.teamId} style={{opacity:rankTeamOpacity(team.teamId,selected)}}><polyline points={team.path} fill="none" stroke={team.color} strokeWidth="3"><title>{team.teamName}</title></polyline>{team.points.map(point=><circle key={point.week} cx={point.x} cy={point.y} r="4" fill={team.color} tabIndex="0"><title>{`${team.teamName} — Week ${point.week}: ${ordinal(point.rank)}`}</title></circle>)}</g>)}
        {rankWeeks.map(({week,x})=><text key={week} x={x} y="233" textAnchor="middle">{week}</text>)}<text x="412" y="254" textAnchor="middle" className="chart-axis-label">Matchup Week</text>
      </svg></div></Card>
    </div>
  </Section>;
}
