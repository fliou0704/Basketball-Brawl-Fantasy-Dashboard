import React, { useEffect, useRef, useState } from 'react';
import { Header, getData } from './App';
import './historical-h2h.css';

function Details({ details, onClose }) {
  const region = useRef(null);
  useEffect(()=>{region.current?.scrollIntoView({block:'start'});},[details]);
  return <section ref={region} className="home-section h2h-details" aria-labelledby="matchup-details-title">
    <div className="section-title"><h2 id="matchup-details-title">Matchup Details</h2><button onClick={onClose}>Close</button></div>
    <p>Year: {details.year} | Week: {details.week}</p>
    <div className="h2h-player-sides">{details.teams.map((team,side)=><table key={side}>
      <caption>{team}</caption><thead><tr><th scope="col">Player Name</th><th scope="col">FPTS</th></tr></thead>
      <tbody>{details.players[side].map((p,i)=><tr key={i}><td>{p.name}</td><td>{p.fpts}</td></tr>)}</tbody>
    </table>)}</div>
  </section>;
}

export default function HistoricalH2H() {
  const [manifest,setManifest] = useState(null);
  const [first,setFirst] = useState('');
  const [second,setSecond] = useState('');
  const [view,setView] = useState(null);
  const [details,setDetails] = useState(null);
  const [error,setError] = useState(false);
  useEffect(()=>{let active=true;getData('historical-h2h.json').then(d=>{if(active)setManifest(d);}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  useEffect(()=>{
    let active=true;setView(null);setDetails(null);
    if(manifest && first && second) {
      setError(false);
      const pair = manifest.pairs[`${first}-${second}`];
      getData(`historical-h2h/${pair}.json`).then(d=>{if(active)setView(d.perspectives[first]);}).catch(()=>{if(active)setError(true);});
    }
    return()=>{active=false;};
  },[manifest,first,second]);
  return <><a className="skip" href="#historical-h2h">Skip to content</a><Header active="historical-h2h"/>
    <main id="historical-h2h" className="homepage h2h-page"><div className="home-heading"><h1>Historical Head-to-Head Matchups</h1></div>
      {manifest && <div className="h2h-selectors">{[{id:'h2h-first',label:'Team 1:',value:first,other:second,set:setFirst},{id:'h2h-second',label:'Team 2:',value:second,other:first,set:setSecond}].map(s=><div key={s.id}><label htmlFor={s.id}>{s.label}</label><select id={s.id} value={s.value} onChange={e=>s.set(e.target.value)}><option value="">Select {s.label.slice(0,-1)}</option>{manifest.teams.filter(t=>String(t.teamId)!==s.other).map(t=><option key={t.teamId} value={t.teamId}>{t.teamName}</option>)}</select></div>)}</div>}
      {error?<p role="alert">Historical H2H unavailable. Please reload to try again.</p>:!manifest?<p role="status">Loading…</p>:!first||!second?<p>Select two teams!</p>:!view?<p role="status">Loading…</p>:view.message?<p>{view.message}</p>:<>
        <section className="home-section"><div className="section-title"><h2>{view.title}</h2></div><dl className="h2h-records">{view.records.map(r=><div key={r.label}><dt>{r.label}</dt><dd>{r.value}</dd></div>)}</dl></section>
        <section className="home-section"><div className="section-title"><h2>Matchup History</h2></div>
          <table className="h2h-history"><caption className="sr-only">Matchup History</caption><thead><tr>{manifest.columns.map(c=><th key={c} scope="col">{c}</th>)}</tr></thead>
            <tbody>{view.history.map((row,i)=><tr key={i} className={row.playoff?'h2h-playoff':''} onClick={()=>setDetails(row.details)}>{manifest.columns.map(c=><td key={c} data-label={c} className={c==='Result'?`h2h-result ${row.fields[c]==='W'?'win':'loss'}`:undefined}>{c==='Score'?<button className="h2h-score" aria-label={`Matchup Details: ${row.fields['Year']}, Week ${row.fields['Week']}, ${row.fields['Team Name']} vs. ${row.fields['Opponent Team Name']}`} onClick={()=>setDetails(row.details)}>{row.fields[c]}</button>:row.fields[c]}</td>)}</tr>)}</tbody>
          </table>
        </section>
        {details && <Details details={details} onClose={()=>setDetails(null)}/>}
      </>}
    </main></>;
}
