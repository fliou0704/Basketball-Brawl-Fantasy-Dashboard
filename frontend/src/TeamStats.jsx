import React, { useEffect, useState } from 'react';
import { Header, getData } from './App';
import { TeamLogo } from './components/Standings';
import { Card, PageShell, Section, TableCard } from './components/Layout';
import { latestTeamSeason } from './site-data';
import './team-stats.css';

function Roster({ rows, summary }) {
  const columns = summary
    ? [['name','Player Name'],['fpts','Total FPTS'],['action','Last Action'],['date','Last Action Date']]
    : [['name','Player'],['fpts','FPTS'],['games','GP'],['points','PTS'],['rebounds','REB'],['assists','AST'],['steals','STL'],['blocks','BLK'],['turnovers','TO'],['threePointers','3PM'],['fieldGoalPct','FG%'],['freeThrowPct','FT%']];
  return <table className={`team-roster ${summary?'summary-roster':'season-roster'}`}><caption className="sr-only">{summary?'All-Time Roster':'Roster'}</caption>
    <thead><tr>{columns.map(([key,label])=><th key={key} scope="col">{label}</th>)}</tr></thead>
    <tbody>{rows.map((row,index)=><tr key={`${row.playerId}-${index}`} className={summary?(row.inactive?'roster-inactive':'roster-active'):''}>
      {columns.map(([key,label])=>key==='name'?<th key={key} scope="row">{row[key]}</th>:<td key={key} data-label={label}>{row[key]}</td>)}
    </tr>)}</tbody>
  </table>;
}

function SeasonRoster({ rows }) {
  const current=rows.filter(row=>row.current);
  const former=rows.filter(row=>!row.current);
  return <div className="roster-groups">
    <div><h3 className="roster-heading">Current Roster <span>{current.length} players</span></h3><TableCard className="roster-card"><Roster rows={current}/></TableCard></div>
    {former.length>0&&<div><h3 className="roster-heading">Former Players <span>{former.length} players</span></h3><TableCard className="roster-card"><Roster rows={former}/></TableCard></div>}
  </div>;
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
  useEffect(()=>{let active=true;getData('team-stats.json').then(d=>{if(active)setManifest(d);}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  useEffect(()=>{
    let active=true;setData(null);setError(false);setYear('');
    if(teamId)getData(`team-stats/${teamId}.json`).then(d=>{if(active){setData(d);setYear(latestTeamSeason(d));}}).catch(()=>{if(active)setError(true);});
    return()=>{active=false;};
  },[teamId]);
  const isSummary = year==='Summary';
  const season = data?.seasons[year];
  const validTeam = manifest?.teams.some(team=>String(team.teamId)===String(teamId));
  return <><a className="skip" href="#team-page">Skip to content</a><Header active="teams"/>
    <PageShell id="team-page" className="homepage team-stats-page">
      {error || (manifest && !validTeam)?<section className="message" role="alert"><h1>Team unavailable</h1><p>Choose a team from the Teams menu.</p></section>:!manifest || !data || !year?<p role="status">Loading…</p>:<>
        <header className="team-identity" style={{'--team-color':data.team.color}}>
          <TeamLogo team={data.team} size={84}/><div className="team-identity-copy"><p className="page-eyebrow">Franchise</p><h1>{data.team.teamName}</h1>{data.team.owner&&<p className="team-owner">Owner · {data.team.owner}</p>}</div>
          <label className="season-selector">Season<select aria-label="Season" value={year} onChange={event=>setYear(event.target.value)}><option value="Summary">Summary</option>{Object.keys(data.seasons).filter(y=>data.seasons[y]).sort((a,b)=>b-a).map(y=><option key={y} value={y}>{y}</option>)}</select></label>
        </header>
        {isSummary?<><Section title="All-Time Record"><Card><dl className="team-records">{data.summary.records.map(r=><div key={r.label}><dt>{r.label}</dt><dd>{r.value}</dd></div>)}</dl></Card></Section>
          <Section title="All-Time Roster"><TableCard><Roster rows={data.summary.roster} summary/></TableCard></Section></>
          :!season?<p>No data for {data.team.teamName} in {year}</p>:<>
            <Section title="Season Snapshot" meta={year}><Card><dl className="season-snapshot"><div><dt>Record</dt><dd>{season.snapshot.record}</dd></div><div><dt>Standing</dt><dd>{ordinal(season.snapshot.rank)}</dd></div><div><dt>Points For</dt><dd>{season.snapshot.pointsForDisplay}</dd></div><div><dt>Points Against</dt><dd>{season.snapshot.pointsAgainstDisplay}</dd></div></dl></Card></Section>
            <Section title="Category Rankings"><Card><dl className="team-rankings">{season.rankings.map(stat=><div className="ranking-row" key={stat.label}><dt>{stat.label}</dt><dd><div className="ranking-result">{stat.rankImage?<img className="rank-image" src={`${import.meta.env.BASE_URL}${stat.rankImage}`} alt={ordinal(stat.rank)}/>:<span className="rank-unavailable">N/A</span>}<strong>{stat.value}</strong></div><div className="relative-track" role="img" aria-label={`${stat.label}: ${stat.relativePercent ?? 0}% of the category leader`}><span style={{width:`${stat.relativePercent ?? 0}%`}}/></div></dd></div>)}</dl></Card></Section>
            <Section title="Roster"><SeasonRoster rows={season.roster}/></Section>
          </>}
      </>}
    </PageShell></>;
}
