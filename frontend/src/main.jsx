import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import App from './App';
import TeamStats from './TeamStats';
import H2HPage from './HistoricalH2H';
import RecordBook from './RecordBook';
import StandingsPage from './StandingsPage';
import { PlayerPage, PlayersLanding } from './Players';
import { h2hRoute, playerRoute, teamIdFromRoute } from './site-data';

function Site() {
  const [route,setRoute] = useState(window.location.hash);
  useEffect(()=>{const update=()=>setRoute(window.location.hash);window.addEventListener('hashchange',update);return()=>window.removeEventListener('hashchange',update);},[]);
  const h2h=h2hRoute(route);
  if(h2h) return <H2HPage key={h2h.key} mode={h2h.mode}/>;
  if(route==='#/record-book' || route==='#record-book') return <RecordBook/>;
  if(route==='#/standings' || route==='#standings') return <StandingsPage/>;
  const player=playerRoute(route);
  if(player) return player.playerId?<PlayerPage playerId={player.playerId}/>:<PlayersLanding/>;
  const teamId=teamIdFromRoute(route);
  if(teamId) return <TeamStats teamId={teamId}/>;
  return <App/>;
}

createRoot(document.getElementById('root')).render(<Site />);
