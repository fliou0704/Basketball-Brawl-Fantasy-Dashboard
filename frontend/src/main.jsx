import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import App from './App';
import TeamStats from './TeamStats';

function Site() {
  const [route,setRoute] = useState(window.location.hash);
  useEffect(()=>{const update=()=>setRoute(window.location.hash);window.addEventListener('hashchange',update);return()=>window.removeEventListener('hashchange',update);},[]);
  return route==='#/team-stats' || route==='#team-stats' ? <TeamStats/> : <App/>;
}

createRoot(document.getElementById('root')).render(<Site />);
