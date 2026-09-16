import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import App from './App';
import TeamStats from './TeamStats';
import HistoricalH2H from './HistoricalH2H';
import RecordBook from './RecordBook';
import StandingsPage from './StandingsPage';
import { teamIdFromRoute } from './site-data';

function Site() {
  const [route,setRoute] = useState(window.location.hash);
  useEffect(()=>{const update=()=>setRoute(window.location.hash);window.addEventListener('hashchange',update);return()=>window.removeEventListener('hashchange',update);},[]);
  if(route==='#/historical-h2h' || route==='#historical-h2h') return <HistoricalH2H/>;
  if(route==='#/record-book' || route==='#record-book') return <RecordBook/>;
  if(route==='#/standings' || route==='#standings') return <StandingsPage/>;
  const teamId=teamIdFromRoute(route);
  if(teamId) return <TeamStats teamId={teamId}/>;
  return <App/>;
}

createRoot(document.getElementById('root')).render(<Site />);
