import React, { useEffect, useRef, useState } from 'react';
import Standings from './components/Standings';
import Playoffs from './components/Playoffs';
import { Daily, Weekly, Scoreboard, Around, CurrentWeek } from './components/Recaps';
import { SeasonLeaders, SeasonHistory } from './components/SeasonHistory';
import { PageHeader, PageShell } from './components/Layout';
import { createHomeClient, HOME_REFRESH_MS, leagueDate } from './home-data';
import './homepage.css';

const base = import.meta.env.BASE_URL;
const cache = new Map();
export function getData(path) {
  if (!cache.has(path)) cache.set(path, fetch(`${base}data/${path}`).then(r=>{
    if (!r.ok) throw new Error('Data unavailable');
    return r.json();
  }).then(d=>{if(d.schemaVersion!==1) throw new Error('Unsupported data'); return d;}).catch(e=>{cache.delete(path);throw e;}));
  return cache.get(path);
}
const homeClient = createHomeClient(base);
export function Header({ active = 'home' }) {
  const [open,setOpen] = useState(false);
  const [teamsOpen,setTeamsOpen] = useState(false);
  const [h2hOpen,setH2hOpen] = useState(false);
  const [teams,setTeams] = useState([]);
  useEffect(()=>{let active=true;getData('team-stats.json').then(data=>{if(active)setTeams(data.teams);}).catch(()=>{});return()=>{active=false;};},[]);
  useEffect(()=>{
    if(!teamsOpen && !h2hOpen) return;
    const close = event => { if(!event.target.closest('.teams-menu')) setTeamsOpen(false); if(!event.target.closest('.h2h-menu')) setH2hOpen(false); };
    const escape = event => { if(event.key==='Escape') { setTeamsOpen(false); setH2hOpen(false); } };
    document.addEventListener('click',close); document.addEventListener('keydown',escape);
    return()=>{document.removeEventListener('click',close);document.removeEventListener('keydown',escape);};
  },[teamsOpen,h2hOpen]);
  return <header className="masthead"><div className="header-inner"><a className="brand" href={base}><span className="brand-mark" aria-hidden="true"/><span>Basketball Brawl</span></a><button type="button" className="menu-button" aria-expanded={open} aria-controls="site-menu" aria-label={open?'Close menu':'Open menu'} onClick={()=>setOpen(!open)}><span className={open?'menu-icon open':'menu-icon'} aria-hidden="true"><span/><span/><span/></span></button>
    <nav id="site-menu" className={open?'site-menu open':'site-menu'} aria-label="Main navigation"><a href={base} aria-current={active==='home'?'page':undefined}>Home</a><a href={`${base}#/scoreboard`} aria-current={active==='scoreboard'?'page':undefined} onClick={()=>setOpen(false)}>Scoreboard</a><a href={`${base}#/standings`} aria-current={active==='standings'?'page':undefined} onClick={()=>setOpen(false)}>Standings</a><a href={`${base}#/players`} aria-current={active==='players'?'page':undefined} onClick={()=>setOpen(false)}>Players</a><div className={`teams-menu ${teamsOpen?'open':''}`}><button type="button" aria-expanded={teamsOpen} aria-controls="teams-submenu" aria-current={active==='teams'?'page':undefined} onClick={event=>{event.stopPropagation();setTeamsOpen(!teamsOpen);setH2hOpen(false);}}>Teams <span aria-hidden="true">▾</span></button><div id="teams-submenu" className="teams-submenu">{teams.map(team=><a key={team.teamId} href={`${base}#/teams/${team.teamId}`} onClick={()=>{setTeamsOpen(false);setOpen(false);}}>{team.teamName}</a>)}</div></div><div className={`teams-menu h2h-menu ${h2hOpen?'open':''}`}><button type="button" aria-expanded={h2hOpen} aria-controls="h2h-submenu" aria-current={active==='h2h'?'page':undefined} onClick={event=>{event.stopPropagation();setH2hOpen(!h2hOpen);setTeamsOpen(false);}}>H2H <span aria-hidden="true">▾</span></button><div id="h2h-submenu" className="teams-submenu"><a href={`${base}#/h2h/historical`} onClick={()=>{setH2hOpen(false);setOpen(false);}}>Historical</a><a href={`${base}#/h2h/theoretical`} onClick={()=>{setH2hOpen(false);setOpen(false);}}>Theoretical</a></div></div><a href={`${base}#/record-book`} aria-current={active==='record-book'?'page':undefined} onClick={()=>setOpen(false)}>Record Book</a><span aria-disabled="true">Power Rankings</span></nav>
  </div></header>;
}
export default function App() {
  const override = new URLSearchParams(window.location.search).get('date');
  const [realDate,setRealDate] = useState(leagueDate);
  const requested = override || realDate;
  const [page,setPage] = useState(null);
  const [error,setError] = useState(false);
  const [refreshFailed,setRefreshFailed] = useState(false);
  const hasPage = useRef(false);
  useEffect(()=>{const timer=setInterval(()=>setRealDate(leagueDate()),60000);return()=>clearInterval(timer);},[]);
  useEffect(()=>{
    let cancelled=false, loading=false, lastCheck=0;
    setError(false);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(requested) || Number.isNaN(Date.parse(`${requested}T12:00:00Z`)) || new Date(`${requested}T12:00:00Z`).toISOString().slice(0,10)!==requested) {setError(true);return;}
    async function update() {
      if (loading) return;
      loading=true; lastCheck=Date.now();
      try {
        const data=await homeClient.load(requested,{preview:Boolean(override)});
        if(!cancelled) {hasPage.current=true;setPage(data);setError(false);setRefreshFailed(false);}
      } catch {
        if(!cancelled) {setRefreshFailed(true);if(!hasPage.current)setError(true);}
      } finally {loading=false;}
    }
    const resume=()=>{if(document.visibilityState==='visible' && Date.now()-lastCheck>60000)update();};
    update();
    const timer=setInterval(()=>{if(document.visibilityState==='visible')update();},HOME_REFRESH_MS);
    window.addEventListener('focus',resume);document.addEventListener('visibilitychange',resume);
    return()=>{cancelled=true;clearInterval(timer);window.removeEventListener('focus',resume);document.removeEventListener('visibilitychange',resume);};
  },[requested,override]);
  const state=page?.state;
  const offseason=state?.phase==='offseason';
  const daily=page?.['daily-recap']?.[state?.dailyDate];
  const weekly=page?.['weekly-recap']?.[state?.weeklyWeek];
  const standings=page?.standings?.[state?.standingsWeek];
  const bracket=page?.playoffs?.[state?.playoffKey];
  return <><a className="skip" href="#home">Skip to content</a><Header/><PageShell id="home" className="homepage">
    <PageHeader title={state?.season ? `${state.season} ${offseason?'Season':state.phase==='playoffs'?'Playoffs':'Season'}`:'Basketball Brawl'} meta={state?.season && (offseason?'Season complete':`Week ${state.week}`)}/>
    {!error && page?.current && <CurrentWeek snapshot={page.current} publishedAt={page.publishedAt} stale={page.stale} refreshFailed={refreshFailed}/>}
    {error?<section className="message" role="alert"><h2>Homepage unavailable</h2><p>{override?'Check the date (YYYY-MM-DD) and try again.':'Please try again.'}</p><button onClick={()=>window.location.reload()}>Try again</button></section>:!page?<p role="status">Loading…</p>:!state.season?<p className="archive-note">No completed season is available for this date.</p>:offseason?<>
      <Playoffs bracket={bracket}/><Standings data={standings} final/>
      <SeasonLeaders players={page['season-leaders']}/><SeasonHistory data={page.history}/>
    </>:state.phase==='playoffs'?<>
      <Playoffs bracket={bracket}/><Weekly recap={weekly} playoffOnly/>
      {!page.current && <Scoreboard recap={daily} week={state.week}/>}<Standings data={standings} final/>
    </>:<>
      {state.weeklyFirst?<><Weekly recap={weekly}/><Daily recap={daily}/></>:<><Daily recap={daily}/><Weekly recap={weekly}/></>}
      {!page.current && <Scoreboard recap={daily} week={state.week}/>}<Standings data={standings}/><Around recap={weekly}/>
    </>}
  </PageShell></>;
}
