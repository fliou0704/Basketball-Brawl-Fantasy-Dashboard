import React, { useId, useMemo, useState } from 'react';
import { clearPlayerSearch, searchPlayers } from '../player-data';

const base=import.meta.env.BASE_URL;

export default function PlayerSearch({players, compact=false}) {
  const [query,setQuery]=useState('');
  const inputId=useId();
  const matches=useMemo(()=>searchPlayers(players,query),[players,query]);
  const active=query.trim().length>0;
  return <div className={`player-search ${compact?'player-search-compact':''}`}>
    <label htmlFor={inputId}>{compact?'Search for another player':'Find a player'}</label>
    <div className="player-search-input-wrap"><span aria-hidden="true">⌕</span><input id={inputId} type="search" value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search Basketball Brawl players..." autoComplete="off"/></div>
    {active&&<div className="player-search-results" role="region" aria-live="polite" aria-label="Player search results">
      {matches.length?matches.map(player=><a key={player.playerId} className="player-search-result" href={`${base}#/players/${player.playerId}`} onClick={()=>setQuery(clearPlayerSearch())}>
        {player.headshot?<img src={player.headshot} alt=""/>:<span className="player-search-fallback" aria-hidden="true"/>}
        <span><strong>{player.name}</strong><small>{[player.fantasyEligibility?.join(' / ')||player.position,player.fantasyTeam?.teamName||'Fantasy Free Agent'].filter(Boolean).join(' · ')}</small></span>
      </a>):<p className="player-search-empty">No Basketball Brawl players found.</p>}
    </div>}
  </div>;
}
