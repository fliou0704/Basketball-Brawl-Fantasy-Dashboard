import React, { useEffect, useState } from 'react';
import { Header, getData } from './App';
import { Team } from './components/Standings';
import './team-stats.css';

function Roster({ rows, summary }) {
  const columns = summary
    ? [['name','Player Name'],['fpts','Total FPTS'],['action','Last Action'],['date','Last Action Date']]
    : [['name','Player Name'],['fpts','FPTS'],['ppm','PPM'],['action','Action'],['date','Date'],['contribution','Contribution']];
  return <table className="team-roster"><caption className="sr-only">{summary?'All-Time Roster':'Roster'}</caption>
    <thead><tr>{columns.map(([key,label])=><th key={key} scope="col">{label}</th>)}</tr></thead>
    <tbody>{rows.map((row,index)=><tr key={`${row.playerId}-${index}`} className={summary?(row.inactive?'roster-inactive':'roster-active'):''}>
      {columns.map(([key,label])=>key==='name'?<th key={key} scope="row">{row[key]}</th>:<td key={key} data-label={label}>{row[key]}</td>)}
    </tr>)}</tbody>
  </table>;
}

export default function TeamStats() {
  const [manifest,setManifest] = useState(null);
  const [teamId,setTeamId] = useState('');
  const [year,setYear] = useState('Summary');
  const [data,setData] = useState(null);
  const [error,setError] = useState(false);
  useEffect(()=>{let active=true;getData('team-stats.json').then(d=>{if(active)setManifest(d);}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  useEffect(()=>{
    let active=true;setData(null);setError(false);
    if(teamId)getData(`team-stats/${teamId}.json`).then(d=>{if(active)setData(d);}).catch(()=>{if(active)setError(true);});
    return()=>{active=false;};
  },[teamId]);
  const isSummary = year==='Summary';
  const season = data?.seasons[year];
  return <><a className="skip" href="#team-stats">Skip to content</a><Header active="team-stats"/>
    <main id="team-stats" className="homepage team-stats-page"><div className="home-heading"><h1>Team Stats</h1></div>
      {manifest && <div className="team-stats-selectors"><label>Team<select value={teamId} onChange={e=>setTeamId(e.target.value)}><option value="">Select a team</option>{manifest.teams.map(t=><option key={t.teamId} value={t.teamId}>{t.teamName}</option>)}</select></label>
        {teamId && <label>Season<select value={year} onChange={e=>setYear(e.target.value)}><option value="Summary">Summary</option>{manifest.years.map(y=><option key={y} value={y}>{y}</option>)}</select></label>}
      </div>}
      {error?<p role="alert">Team Stats unavailable. Please reload to try again.</p>:!manifest || (teamId&&!data)?<p role="status">Loading…</p>:!teamId?<p>Please select a team</p>:data && <>
        <div className="selected-team"><h2><Team team={data.team}/></h2><span>{year}</span></div>
        {isSummary?<><section className="home-section"><div className="section-title"><h2>All-Time Record</h2></div><dl className="team-records">{data.summary.records.map(r=><div key={r.label}><dt>{r.label}</dt><dd>{r.value}</dd></div>)}</dl></section>
          <section className="home-section"><div className="section-title"><h2>All-Time Roster</h2></div><Roster rows={data.summary.roster} summary/></section></>
          :!season?<p>No data for {data.team.teamName} in {year}</p>:<>
            <section className="home-section"><div className="section-title"><h2>Stat Rankings</h2></div><dl className="team-rankings">{season.rankings.map(stat=><div key={stat.label}><dt>{stat.label}</dt><dd><span className="stat-rank">{stat.rank===null?'Rank N/A':`Rank ${stat.rank}`}</span><strong>{stat.value}</strong></dd></div>)}</dl></section>
            <section className="home-section"><div className="section-title"><h2>Roster</h2></div><Roster rows={season.roster}/></section>
          </>}
      </>}
    </main></>;
}
