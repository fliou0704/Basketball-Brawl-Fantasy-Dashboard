import React, { useEffect, useState } from 'react';
import { getData, Header } from './App';
import { PageShell, Section, TableCard } from './components/Layout';
import PlayerSearch from './components/PlayerSearch';
import { TeamLogo } from './components/Standings';
import { ageOnDate, defaultPlayerTab, formatHeight, formatPlayerGameDate, latestPlayerGameSeason, PLAYER_GAME_STATS, recentPlayerGames, selectPlayerTab } from './player-data';
import './players.css';

const base=import.meta.env.BASE_URL;
const stats=['starts','FPTS','fpPerStart','mpg','fppm','PTS','REB','AST','STL','BLK','3PM','TO','FGM','FGA','FTM','FTA'];
const rateStats=new Set(['fpPerStart','mpg','fppm']);
const labels={starts:'GP',FPTS:'FPTS',fpPerStart:'FP/Start',mpg:'MPG',fppm:'FPPM',PTS:'PTS',REB:'REB',AST:'AST',STL:'STL',BLK:'BLK','3PM':'3PM',TO:'TO',FGM:'FGM',FGA:'FGA',FTM:'FTM',FTA:'FTA'};
const statTitles={starts:'Credited fantasy starts',fpPerStart:'Fantasy points per credited start',mpg:'Minutes per credited game',fppm:'Fantasy points per minute'};
const tabLabels={career:'Career','game-log':'Game Log',transactions:'Transactions'};
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

function PlayerTabs({active,onChange}) {
  return <nav className="player-tabs" aria-label="Player sections" role="tablist">{Object.entries(tabLabels).map(([tab,label])=><button key={tab} type="button" role="tab" aria-selected={active===tab} aria-controls={`player-tab-${tab}`} onClick={()=>onChange(selectPlayerTab(tab))}>{label}</button>)}</nav>;
}

function transactionDate(value) { return new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date(`${value}T12:00:00Z`)); }
function gameValue(game,stat) { const value=game[stat]; return value==null?'—':Number(value).toLocaleString(undefined,{maximumFractionDigits:2}); }
function GameTable({games,label,emptyMessage='No games played.'}) {
  if(!games.length) return <div className="player-tab-empty">{emptyMessage}</div>;
  return <TableCard className="game-log-card"><div className="game-log-scroll"><table className="game-log-table"><caption className="sr-only">{label}</caption><thead><tr><th>Date</th>{PLAYER_GAME_STATS.map(stat=><th className="numeric" key={stat}>{stat}</th>)}</tr></thead><tbody>{games.map(game=><tr key={`${game.date}-${game.scoringPeriod}`}><th scope="row">{formatPlayerGameDate(game.date)}</th>{PLAYER_GAME_STATS.map(stat=><td className={`numeric ${stat==='FPTS'?'game-fpts':''}`} key={stat}>{gameValue(game,stat)}</td>)}</tr>)}</tbody></table></div></TableCard>;
}

function GameLogTab({career}) {
  const latest=latestPlayerGameSeason(career.gameSeasons||[]);
  const [season,setSeason]=useState(latest==null?'':String(latest));
  const games=career.gameLog||[];
  const selected=games.filter(game=>String(game.season)===season);
  return <div id="player-tab-game-log" role="tabpanel" className="player-tab-panel">
    <Section title="Recent Games" meta="Latest 5 played games"><GameTable games={recentPlayerGames(games)} label="Recent games"/></Section>
    <Section title="Complete Game Log" className="complete-game-log"><label className="player-season-selector">Season<select aria-label="Game Log season" value={season} onChange={event=>setSeason(event.target.value)}>{(career.gameSeasons||[]).map(year=><option key={year} value={year}>{year}</option>)}</select></label><GameTable games={selected} label={`${season} complete game log`} emptyMessage={`No games played in ${season}.`}/></Section>
  </div>;
}

function TransactionTeam({team}) { return <span className="transaction-team"><TeamLogo team={team} size={34}/><span>{team.teamName}</span></span>; }
function TransactionTeams({transaction}) {
  if(!transaction.counterpartTeam) return <TransactionTeam team={transaction.team}/>;
  const from=transaction.type==='TRADED'?transaction.team:transaction.counterpartTeam;
  const to=transaction.type==='TRADED'?transaction.counterpartTeam:transaction.team;
  return <span className="transaction-trade"><TransactionTeam team={from}/><span aria-hidden="true">→</span><TransactionTeam team={to}/></span>;
}
function TransactionsTab({transactions}) {
  return <div id="player-tab-transactions" role="tabpanel" className="player-tab-panel"><Section title="Basketball Brawl Transactions" meta="Most recent first">{transactions.length?<ol className="transaction-list">{transactions.map((transaction,index)=><li key={`${transaction.date}-${transaction.time}-${transaction.type}-${index}`}><time dateTime={transaction.date}>{transactionDate(transaction.date)}</time><div><strong>{transaction.type}</strong><span>{transaction.season} season</span></div><TransactionTeams transaction={transaction}/></li>)}</ol>:<div className="player-tab-empty">No Basketball Brawl transactions recorded for this player.</div>}</Section></div>;
}

export function PlayerPage({playerId}) {
  const {players,error:searchError}=usePlayers();
  const [state,setState]=useState({metadata:null,career:null,error:false});
  const [activeTab,setActiveTab]=useState(defaultPlayerTab());
  useEffect(()=>setActiveTab(defaultPlayerTab()),[playerId]);
  useEffect(()=>{let live=true;setState({metadata:null,career:null,error:false});Promise.all([getData('player-metadata.json'),getData(`players/${playerId}.json`)]).then(([metadata,career])=>{if(live)setState({metadata:metadata.players[playerId]||null,career,error:!metadata.players[playerId]});}).catch(()=>live&&setState({metadata:null,career:null,error:true}));return()=>{live=false;};},[playerId]);
  const {metadata:player,career,error}=state;
  const teamLabel=player?.Active?'NBA Team':'Last NBA Team';
  const eligibility=career?.fantasyEligibility?.join(' / ');
  return <><a className="skip" href="#player">Skip to content</a><Header active="players"/><PageShell id="player" className="players-page player-detail">
    {!searchError&&players&&<PlayerSearch players={players} compact/>}
    {error?<div className="message" role="alert"><h2>Player not found</h2><p>The ESPN Player ID {playerId} is not in Basketball Brawl history.</p><a href={`${base}#/players`}>Search players</a></div>:!player?<p role="status">Loading player…</p>:<>
      <section className="player-profile"><div className="player-headshot-wrap">{player['Headshot URL']?<img src={player['Headshot URL']} alt={`${player['Full Name']} headshot`}/>:<span aria-hidden="true"/>}</div><div className="player-profile-main"><p className="page-eyebrow">Basketball Brawl Player</p><h1>{player['Full Name']}</h1><p className="player-nba-line">{[eligibility,clean(player['Jersey Number'])?`#${player['Jersey Number']}`:null].filter(clean).join(' · ')}</p><div className="current-fantasy-team"><span>Fantasy Team</span>{career.fantasyTeam?<strong><img src={`${base}${career.fantasyTeam.logo}`} alt=""/>{career.fantasyTeam.teamName}</strong>:<strong>Fantasy Free Agent</strong>}</div><dl className="player-bio"><BioItem label="Age" value={ageOnDate(player['Birth Date'])} featured/><BioItem label="Height" value={formatHeight(player['Height Inches'])}/><BioItem label="Weight" value={clean(player['Weight Pounds'])?`${player['Weight Pounds']} lb`:null}/><BioItem label={teamLabel} value={player['NBA Team Name']}/><BioItem label="NBA position" value={player['NBA Position Name']||player['NBA Position Abbreviation']}/><BioItem label="Born" value={dateLabel(player['Birth Date'])}/><BioItem label="Birthplace" value={birthplace(player)}/><BioItem label="Draft" value={draftLabel(player)}/><BioItem label="NBA experience" value={clean(player['NBA Experience Years'])?`${player['NBA Experience Years']} years`:null}/><BioItem label="Status" value={player.Active?'Active':'Inactive'}/></dl></div></section>
      <PlayerTabs active={activeTab} onChange={setActiveTab}/>
      {activeTab==='career'&&<div id="player-tab-career" role="tabpanel" className="player-tab-panel"><Section title="Basketball Brawl Career"><p className="career-definition">Totals include played NBA games only when the player occupied an active fantasy lineup slot.</p><CareerTable rows={career.careerRows} career={career.career}/></Section></div>}
      {activeTab==='game-log'&&<GameLogTab career={career}/>}
      {activeTab==='transactions'&&<TransactionsTab transactions={career.transactions||[]}/>}
    </>}
  </PageShell></>;
}
