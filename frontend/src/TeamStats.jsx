import React, { useEffect, useState } from 'react';
import { Header, getData } from './App';
import { TeamLogo } from './components/Standings';
import { Card, PageShell, Section, TableCard } from './components/Layout';
import PlayerIdentity from './components/PlayerIdentity';
import { latestTeamSeason } from './site-data';
import { defaultTeamTab, TEAM_TABS, selectTeamTab } from './team-tabs';
import './team-stats.css';

function Roster({ rows, summary, qualityMetric = 'fpts' }) {
  const columns = summary
    ? [['name','Player Name'],['fpts','Total FPTS'],['action','Last Action'],['date','Last Action Date']]
    : [['name','Player'],['quality','League %ile'],['fpts','FPTS'],['ppm','FPPM'],['mpg','MPG'],['games','GP'],['points','PTS'],['rebounds','REB'],['assists','AST'],['steals','STL'],['blocks','BLK'],['turnovers','TO'],['threePointers','3PM'],['fieldGoalPct','FG%'],['freeThrowPct','FT%']];
  return <table className={`team-roster ${summary?'summary-roster':'season-roster'}`}><caption className="sr-only">{summary?'All-Time Roster':'Roster'}</caption>
    <thead><tr>{columns.map(([key,label])=><th key={key} scope="col">{label}</th>)}</tr></thead>
    <tbody>{rows.map((row,index)=><tr key={`${row.playerId}-${index}`} className={summary?(row.inactive?'roster-inactive':'roster-active'):''}>
      {columns.map(([key,label])=>key==='name'?<th key={key} scope="row" title={row[key]}><PlayerIdentity playerId={row.playerId} name={row[key]} showHeadshot/></th>:key==='quality'?<td key={key} data-label={label}><PlayerQuality row={row} metric={qualityMetric}/></td>:<td key={key} data-label={label}>{row[key]}</td>)}
    </tr>)}</tbody>
  </table>;
}

function PlayerQuality({ row, metric }) {
  const value=row[metric==='fppm'?'fppmPercentile':'fptsPercentile'];
  if(value==null) return <span className="quality-na">N/A</span>;
  return <div className={`player-quality ${value>=75?'quality-high':value<50?'quality-low':''}`} aria-label={`${ordinal(Math.round(value))} percentile by ${metric.toUpperCase()}`}><span>{ordinal(Math.round(value))}</span><div><i style={{width:`${value}%`}}/></div></div>;
}

function SeasonRoster({ rows }) {
  const [qualityMetric,setQualityMetric]=useState('fpts');
  const current=rows.filter(row=>row.current);
  const former=rows.filter(row=>!row.current);
  return <div className="roster-groups">
    <div className="quality-controls"><p>League percentile compares each player with all fantasy-relevant players that season.</p><div className="metric-toggle" aria-label="Player percentile basis">{[['fpts','FPTS'],['fppm','FPPM']].map(([key,label])=><button key={key} type="button" aria-pressed={qualityMetric===key} onClick={()=>setQualityMetric(key)}>{label}</button>)}</div></div>
    <div><h3 className="roster-heading">Current Roster <span>{current.length} players</span></h3><TableCard className="roster-card"><Roster rows={current} qualityMetric={qualityMetric}/></TableCard></div>
    {former.length>0&&<div><h3 className="roster-heading">Former Players <span>{former.length} players</span></h3><TableCard className="roster-card"><Roster rows={former} qualityMetric={qualityMetric}/></TableCard></div>}
  </div>;
}

function WeeklyPerformance({ data }) {
  const [metricKey,setMetricKey]=useState('fpts');
  const metric=data?.metrics?.[metricKey];
  if(!metric?.points?.length) return null;
  const toggle=<span className="metric-toggle weekly-metric-toggle" aria-label="Weekly performance metric">{[['fpts','FPTS'],['fppm','FPPM'],['starts','Starts']].map(([key,label])=><button key={key} type="button" aria-pressed={metricKey===key} onClick={()=>setMetricKey(key)}>{label}</button>)}</span>;
  return <Section title="Weekly Performance" meta={toggle}><Card as="figure" className="weekly-performance-card"><svg className="weekly-performance-chart" viewBox={data.viewBox.join(' ')} role="img" aria-label={`Weekly team ${metric.label}`}>
    {metric.yTicks.map(tick=><g key={tick.value}><line x1="54" x2="770" y1={tick.y} y2={tick.y}/><text x="46" y={tick.y+4} textAnchor="end">{tick.display}</text></g>)}
    <polyline points={metric.path}/>
    {metric.points.map(point=><g className="weekly-point" key={point.week}><circle cx={point.x} cy={point.y} r="4"><title>{`Week ${point.week}: ${point.display} ${metric.label}`}</title></circle><text x={point.x} y="239" textAnchor="middle">{point.week}</text></g>)}
    <text className="axis-label" x="412" y="249" textAnchor="middle">Week</text>
  </svg></Card></Section>;
}

function Physicals({ metrics }) {
  if(!metrics?.length) return null;
  return <Section title="Physicals"><Card><dl className="team-physicals">{metrics.map(metric=><div key={metric.key}><dt>{metric.label}</dt><dd>{metric.value}</dd><dd className="physical-rank">{metric.caption}</dd></div>)}</dl></Card></Section>;
}

function TeamTabs({ active, onChange }) {
  return <nav className="team-tabs" aria-label="Team sections" role="tablist">{TEAM_TABS.map(({key,label})=><button key={key} type="button" role="tab" aria-selected={active===key} aria-controls={`team-tab-${key}`} onClick={()=>onChange(selectTeamTab(key))}>{label}</button>)}</nav>;
}

function ordinal(rank) {
  if(rank == null) return 'N/A';
  const mod100=rank%100;
  return `${rank}${mod100>=11&&mod100<=13?'th':rank%10===1?'st':rank%10===2?'nd':rank%10===3?'rd':'th'}`;
}

export default function TeamStats({ teamId }) {
  const [manifest,setManifest] = useState(null);
  const [year,setYear] = useState('');
  const [data,setData] = useState(null);
  const [error,setError] = useState(false);
  const [activeTab,setActiveTab] = useState(defaultTeamTab());
  useEffect(()=>{let active=true;getData('team-stats.json').then(d=>{if(active)setManifest(d);}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  useEffect(()=>{
    let active=true;setData(null);setError(false);setYear('');setActiveTab(defaultTeamTab());
    if(teamId)getData(`team-stats/${teamId}.json`).then(d=>{if(active){setData(d);setYear(latestTeamSeason(d));}}).catch(()=>{if(active)setError(true);});
    return()=>{active=false;};
  },[teamId]);
  const isSummary = year==='Summary';
  const season = data?.seasons[year];
  const validTeam = manifest?.teams.some(team=>String(team.teamId)===String(teamId));
  return <><a className="skip" href="#team-page">Skip to content</a><Header active="teams"/>
    <PageShell id="team-page" className="homepage team-stats-page">
      {error || (manifest && !validTeam)?<section className="message" role="alert"><h1>Team unavailable</h1><p>Choose a team from the Teams menu.</p></section>:!manifest || !data || !year?<p role="status">Loading…</p>:<div className={`team-theme ${isSummary?'':'season-view'}`} style={{'--team-color':data.team.color}}>
        <header className="team-identity">
          <TeamLogo team={data.team} size={84}/><div className="team-identity-copy"><p className="page-eyebrow">Franchise</p><h1>{data.team.teamName}</h1>{data.team.owner&&<p className="team-owner">Owner · {data.team.owner}</p>}</div>
          <label className="season-selector">Season<select aria-label="Season" value={year} onChange={event=>setYear(event.target.value)}><option value="Summary">Summary</option>{Object.keys(data.seasons).filter(y=>data.seasons[y]).sort((a,b)=>b-a).map(y=><option key={y} value={y}>{y}</option>)}</select></label>
        </header>
        {isSummary?<><Section title="All-Time Record"><Card><dl className="team-records">{data.summary.records.map(r=><div key={r.label}><dt>{r.label}</dt><dd>{r.value}</dd></div>)}</dl></Card></Section>
          <Section title="All-Time Roster"><TableCard><Roster rows={data.summary.roster} summary/></TableCard></Section></>
          :!season?<p>No data for {data.team.teamName} in {year}</p>:<>
            <Section title="Overview" meta={year}><Card><dl className="season-snapshot"><div><dt>Record</dt><dd>{season.snapshot.record}</dd></div><div><dt>Standing</dt><dd>{ordinal(season.snapshot.rank)}</dd></div><div><dt>Points For</dt><dd>{season.snapshot.pointsForDisplay}</dd><dd className="snapshot-rank">{season.snapshot.pointsForRankCaption}</dd></div><div><dt>Points Against</dt><dd>{season.snapshot.pointsAgainstDisplay}</dd><dd className="snapshot-rank">{season.snapshot.pointsAgainstRankCaption}</dd></div></dl></Card></Section>
            <TeamTabs active={activeTab} onChange={setActiveTab}/>
            {activeTab==='roster'&&<div id="team-tab-roster" role="tabpanel"><Section title="Roster"><SeasonRoster rows={season.roster}/></Section></div>}
            {activeTab==='rankings'&&<div id="team-tab-rankings" role="tabpanel"><Section title="Category Rankings"><Card><dl className="team-rankings">{season.rankings.map(stat=><div className="ranking-item" key={stat.label}>{stat.rankImage?<img className="rank-image" src={`${import.meta.env.BASE_URL}${stat.rankImage}`} alt={ordinal(stat.rank)}/>:<span className="rank-unavailable">N/A</span>}<div className="ranking-copy"><dt>{stat.label}</dt><dd><strong>{stat.value}</strong></dd></div><div className="relative-track" role="img" aria-label={`${stat.label}: rank position ${stat.relativePercent ?? 0}%`}><span style={{width:`${stat.relativePercent ?? 0}%`}}/></div></div>)}</dl></Card></Section></div>}
            {activeTab==='weekly'&&<div id="team-tab-weekly" role="tabpanel"><WeeklyPerformance data={season.weeklyPerformance}/></div>}
            {activeTab==='physicals'&&<div id="team-tab-physicals" role="tabpanel"><Physicals metrics={season.physicals}/></div>}
          </>}
      </div>}
    </PageShell></>;
}
