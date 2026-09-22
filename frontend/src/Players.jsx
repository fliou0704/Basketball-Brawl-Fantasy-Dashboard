import React, { useEffect, useState } from 'react';
import { getData, Header } from './App';
import { PageShell, Section, TableCard } from './components/Layout';
import PlayerSearch from './components/PlayerSearch';
import { ageOnDate, formatHeight } from './player-data';
import './players.css';

const base=import.meta.env.BASE_URL;
const stats=['starts','FPTS','fpPerStart','mpg','fppm','PTS','REB','AST','STL','BLK','3PM','TO','FGM','FGA','FTM','FTA'];
const rateStats=new Set(['fpPerStart','mpg','fppm']);
const labels={starts:'GP',FPTS:'FPTS',fpPerStart:'FP/Start',mpg:'MPG',fppm:'FPPM',PTS:'PTS',REB:'REB',AST:'AST',STL:'STL',BLK:'BLK','3PM':'3PM',TO:'TO',FGM:'FGM',FGA:'FGA',FTM:'FTM',FTA:'FTA'};
const statTitles={starts:'Credited fantasy starts',fpPerStart:'Fantasy points per credited start',mpg:'Minutes per credited game',fppm:'Fantasy points per minute'};
const clean=value=>value!==null&&value!==undefined&&value!=='';

function usePlayers() {
  const [state,setState]=useState({players:null,error:false});
  useEffect(()=>{let live=true;getData('players.json').then(data=>live&&setState({players:data.players,error:false})).catch(()=>live&&setState({players:null,error:true}));return()=>{live=false;};},[]);
  return state;
}

export function PlayersLanding() {
  const {players,error}=usePlayers();
  return <><a className="skip" href="#players">Skip to content</a><Header active="players"/><PageShell id="players" className="players-page"><header className="page-header"><div><p className="page-eyebrow">Basketball Brawl</p><h1>Players</h1></div></header>
    {error?<div className="message" role="alert">Player search is unavailable.</div>:players?<PlayerSearch players={players}/>:<p role="status">Loading players…</p>}
  </PageShell></>;
}

function BioItem({label,value,featured=false}) { return clean(value)&&<div className={featured?'bio-item bio-featured':'bio-item'}><dt>{label}</dt><dd>{value}</dd></div>; }
function dateLabel(value) { if(!value)return null; return new Intl.DateTimeFormat('en-US',{year:'numeric',month:'long',day:'numeric',timeZone:'UTC'}).format(new Date(`${value}T12:00:00Z`)); }
function draftLabel(player) { return clean(player['Draft Year'])?[player['Draft Year'],clean(player['Draft Round'])?`Round ${player['Draft Round']}`:null,clean(player['Draft Pick'])?`Pick ${player['Draft Pick']}`:null].filter(Boolean).join(' · '):null; }
function birthplace(player) { return [player['Birth City'],player['Birth State Region'],player['Birth Country']].filter(clean).join(', ')||null; }
function statDisplay(row,stat) { const value=row[stat]; return value==null?'—':rateStats.has(stat)?Number(value).toFixed(2):value.toLocaleString(); }

function CareerTable({rows,career}) {
  if(!rows.length) return <div className="career-empty"><h3>No credited starts</h3><p>This player has appeared in Basketball Brawl history but has no played games from an active fantasy lineup slot.</p></div>;
  return <TableCard className="career-table-card"><div className="career-scroll"><table className="career-table"><thead><tr><th>Season</th><th className="career-team">Fantasy team</th>{stats.map(stat=><th key={stat} className="numeric">{statTitles[stat]?<abbr title={statTitles[stat]}>{labels[stat]}</abbr>:labels[stat]}</th>)}</tr></thead><tbody>
    {rows.map((row,index)=>row.rowType==='seasonTotal'?<tr className="season-total" key={`${row.season}-total`}><td/><th scope="row">{row.season} Total</th>{stats.map(stat=><td key={stat} className={`numeric ${stat==='FPTS'?'career-fpts':''}`}>{statDisplay(row,stat)}</td>)}</tr>:<tr key={`${row.season}-${row.team.teamId}-${row.firstDate}-${index}`}><td>{row.season}</td><th scope="row"><span className="career-team-cell"><img src={`${base}${row.team.logo}`} alt=""/><span>{row.team.teamName}</span></span></th>{stats.map(stat=><td key={stat} className={`numeric ${stat==='FPTS'?'career-fpts':''}`}>{statDisplay(row,stat)}</td>)}</tr>)}
    <tr className="career-total"><th scope="row">Career</th><td>All teams</td>{stats.map(stat=><td key={stat} className={`numeric ${stat==='FPTS'?'career-fpts':''}`}>{statDisplay(career,stat)}</td>)}</tr>
  </tbody></table></div></TableCard>;
}

export function PlayerPage({playerId}) {
  const {players,error:searchError}=usePlayers();
  const [state,setState]=useState({metadata:null,career:null,error:false});
  useEffect(()=>{let live=true;setState({metadata:null,career:null,error:false});Promise.all([getData('player-metadata.json'),getData(`players/${playerId}.json`)]).then(([metadata,career])=>{if(live)setState({metadata:metadata.players[playerId]||null,career,error:!metadata.players[playerId]});}).catch(()=>live&&setState({metadata:null,career:null,error:true}));return()=>{live=false;};},[playerId]);
  const {metadata:player,career,error}=state;
  const teamLabel=player?.Active?'NBA Team':'Last NBA Team';
  const eligibility=career?.fantasyEligibility?.join(' / ');
  return <><a className="skip" href="#player">Skip to content</a><Header active="players"/><PageShell id="player" className="players-page player-detail">
    {!searchError&&players&&<PlayerSearch players={players} compact/>}
    {error?<div className="message" role="alert"><h2>Player not found</h2><p>The ESPN Player ID {playerId} is not in Basketball Brawl history.</p><a href={`${base}#/players`}>Search players</a></div>:!player?<p role="status">Loading player…</p>:<>
      <section className="player-profile"><div className="player-headshot-wrap">{player['Headshot URL']?<img src={player['Headshot URL']} alt={`${player['Full Name']} headshot`}/>:<span aria-hidden="true"/>}</div><div className="player-profile-main"><p className="page-eyebrow">Basketball Brawl Player</p><h1>{player['Full Name']}</h1><p className="player-nba-line">{[eligibility,clean(player['Jersey Number'])?`#${player['Jersey Number']}`:null].filter(clean).join(' · ')}</p><div className="current-fantasy-team"><span>Fantasy Team</span>{career.fantasyTeam?<strong><img src={`${base}${career.fantasyTeam.logo}`} alt=""/>{career.fantasyTeam.teamName}</strong>:<strong>Fantasy Free Agent</strong>}</div><dl className="player-bio"><BioItem label="Age" value={ageOnDate(player['Birth Date'])} featured/><BioItem label="Height" value={formatHeight(player['Height Inches'])}/><BioItem label="Weight" value={clean(player['Weight Pounds'])?`${player['Weight Pounds']} lb`:null}/><BioItem label={teamLabel} value={player['NBA Team Name']}/><BioItem label="NBA position" value={player['NBA Position Name']||player['NBA Position Abbreviation']}/><BioItem label="Born" value={dateLabel(player['Birth Date'])}/><BioItem label="Birthplace" value={birthplace(player)}/><BioItem label="Draft" value={draftLabel(player)}/><BioItem label="NBA experience" value={clean(player['NBA Experience Years'])?`${player['NBA Experience Years']} years`:null}/><BioItem label="Status" value={player.Active?'Active':'Inactive'}/></dl></div></section>
      <Section title="Basketball Brawl Career"><p className="career-definition">Totals include played NBA games only when the player occupied an active fantasy lineup slot.</p><CareerTable rows={career.careerRows} career={career.career}/></Section>
    </>}
  </PageShell></>;
}
