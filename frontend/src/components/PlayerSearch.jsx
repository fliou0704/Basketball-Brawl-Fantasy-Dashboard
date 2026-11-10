import React, { useId, useMemo, useState } from 'react';
import { clearPlayerSearch, searchPlayers } from '../player-data';
import PlayerIdentity from './PlayerIdentity';

export default function PlayerSearch({players, compact=false}) {
  const [query,setQuery]=useState('');
  const inputId=useId();
  const matches=useMemo(()=>searchPlayers(players,query),[players,query]);
  const active=query.trim().length>0;
  return <div className={`player-search ${compact?'player-search-compact':''}`}>
    <label htmlFor={inputId}>{compact?'Search for another player':'Find a player'}</label>
    <div className="player-search-input-wrap"><span aria-hidden="true">⌕</span><input id={inputId} type="search" value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search Basketball Brawl players..." autoComplete="off"/></div>
    {active&&<div className="player-search-results" role="region" aria-live="polite" aria-label="Player search results">
      {matches.length?matches.map(player=><PlayerIdentity key={player.playerId} className="player-search-result" playerId={player.playerId} name={player.name} headshotUrl={player.headshot} showHeadshot size={50} subtitle={[player.fantasyEligibility?.join(' / ')||player.position,player.fantasyTeam?.teamName||'Fantasy Free Agent'].filter(Boolean).join(' · ')} onClick={()=>setQuery(clearPlayerSearch())}/>):<p className="player-search-empty">No Basketball Brawl players found.</p>}
    </div>}
  </div>;
}
