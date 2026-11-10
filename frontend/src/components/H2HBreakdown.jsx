import React from 'react';
import PlayerIdentity from './PlayerIdentity';
import './h2h-breakdown.css';

const base=import.meta.env.BASE_URL;
export function TeamMark({team,size=48}) {
  return team?<img src={`${base}${team.logo}`} width={size} height={size} alt={`${team.teamName} logo`}/>:<span className="h2h-logo-placeholder" aria-hidden="true"/>;
}
export function PlayerSide({team,players}) {
  return <div className="player-side" style={{'--side-color':team.color}}><header><TeamMark team={team}/><div><span>{team.teamName}</span><strong>{Math.round(players.reduce((sum,p)=>sum+(p.fpts||0),0))} FPTS</strong></div></header><div className="player-list">{players.map((p,index)=><div className="player-row" key={`${p.name}-${index}`}><strong><PlayerIdentity playerId={p.playerId} name={p.name}/></strong><span>{p.fpts==null?'—':Math.round(p.fpts)} FPTS</span></div>)}</div></div>;
}
export function PlayerSides({children,className=''}) {
  return <div className={`player-sides ${className}`.trim()}>{children}</div>;
}
