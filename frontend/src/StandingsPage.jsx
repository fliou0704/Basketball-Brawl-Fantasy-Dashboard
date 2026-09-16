import React, { useEffect, useState } from 'react';
import { Header, getData } from './App';
import Playoffs from './components/Playoffs';
import Standings from './components/Standings';
import { PageHeader, PageShell } from './components/Layout';
import { selectSeasonView } from './site-data';
import './homepage.css';

export default function StandingsPage() {
  const [manifest,setManifest]=useState(null);
  const [season,setSeason]=useState('');
  const [view,setView]=useState(null);
  const [error,setError]=useState(false);
  useEffect(()=>{let active=true;Promise.all([getData('homepage.json'),getData('team-stats.json')]).then(([home,teams])=>{if(active){setManifest({...home,teamData:teams});setSeason(String(teams.years[0]));}}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  useEffect(()=>{if(!manifest||!season)return;let active=true;setView(null);setError(false);getData(`${season}/playoffs.json`).then(p=>{if(active)setView(selectSeasonView(manifest,season,{0:manifest.teamData.standings[season]},p.data,new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York'}).format(new Date())));}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[manifest,season]);
  return <><a className="skip" href="#standings-page">Skip to content</a><Header active="standings"/><PageShell id="standings-page" className="homepage standings-page">
    <PageHeader title="Standings" meta={manifest&&<label className="season-selector">Season<select aria-label="Season" value={season} onChange={event=>setSeason(event.target.value)}>{manifest.teamData.years.map(year=><option key={year}>{year}</option>)}</select></label>}/>
    {error?<section className="message" role="alert"><h2>Standings unavailable</h2><p>Please reload to try again.</p></section>:!view?<p role="status">Loading…</p>:<><Standings data={view.standings} final={view.complete} linkTeams/><Playoffs bracket={view.bracket}/></>}
  </PageShell></>;
}
