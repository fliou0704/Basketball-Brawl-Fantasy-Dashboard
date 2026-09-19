import React, { useEffect, useState } from 'react';
import { Header, getData } from './App';
import { Card, PageHeader, PageShell, Section, TableCard } from './components/Layout';
import { nextExpandedId } from './site-data';
import './historical-h2h.css';

const base = import.meta.env.BASE_URL;
function TeamMark({ team, size = 48 }) {
  return team ? <img src={`${base}${team.logo}`} width={size} height={size} alt={`${team.teamName} logo`}/> : <span className="h2h-logo-placeholder" aria-hidden="true"/>;
}

function MatchupSelector({ teams, first, second, setFirst, setSecond }) {
  const selected = [teams.find(t=>String(t.teamId)===first), teams.find(t=>String(t.teamId)===second)];
  return <Card className="matchup-selector">{[{label:'Team A',value:first,other:second,set:setFirst,team:selected[0]},{label:'Team B',value:second,other:first,set:setSecond,team:selected[1]}].map((side,index)=><React.Fragment key={side.label}>
    {index===1&&<div className="versus" aria-hidden="true"><span>VS</span></div>}
    <div className="matchup-side" style={{'--side-color':side.team?.color||'var(--color-border-strong)'}}><TeamMark team={side.team} size={76}/><div className="matchup-side-copy"><strong>{side.team?.teamName||side.label}</strong><label htmlFor={`h2h-team-${index}`}>{side.label}</label><select id={`h2h-team-${index}`} value={side.value} onChange={e=>side.set(e.target.value)}><option value="">Choose a team</option>{teams.filter(t=>String(t.teamId)!==side.other).map(t=><option key={t.teamId} value={t.teamId}>{t.teamName}</option>)}</select></div></div>
  </React.Fragment>)}</Card>;
}

function PlayerSide({ team, players }) {
  return <div className="player-side" style={{'--side-color':team.color}}><header><TeamMark team={team}/><div><span>{team.teamName}</span><strong>{Math.round(players.reduce((sum,p)=>sum+(p.fpts||0),0))} FPTS</strong></div></header><div className="player-list">{players.map((p,index)=><div className="player-row" key={`${p.name}-${index}`}><strong>{p.name}</strong><span>{p.fpts==null?'—':Math.round(p.fpts)} FPTS</span></div>)}</div></div>;
}

function MatchupDetails({ details, teams }) {
  const sides=details.teamIds.map((id,index)=>({team:teams.find(t=>t.teamId===id)||{teamId:id,teamName:details.teams[index],color:'#666',logo:'logos/defaultLogo.png'},players:details.players[index]}));
  return <div className="matchup-details" aria-label={`Player breakdown for ${details.year}, week ${details.week}`}><div className="details-heading"><strong>Player breakdown</strong><span>{details.year} · Week {details.week}</span></div><div className="player-sides">{sides.map(side=><PlayerSide key={side.team.teamId} {...side}/>)}</div></div>;
}

function ResultRecord({ mode, view, teams, record }) {
  const a=teams.find(t=>String(t.teamId)===String(view.team1Id)); const b=teams.find(t=>String(t.teamId)===String(view.team2Id));
  if(mode==='theoretical') return <Section title="Theoretical H2H Record" meta={`${record.weeks} comparable weeks`}><Card className="record-hero"><TeamMark team={a}/><div><strong>{record.value}</strong><span>{record.ties?'Wins – Losses – Ties':'Wins – Losses'}</span></div><TeamMark team={b}/></Card></Section>;
  return <Section title="All-Time H2H Record" meta={`${view.history.length} matchups`}><Card className="record-hero"><TeamMark team={a}/><div><strong>{view.records[0].value}</strong><span>Wins – Losses</span></div><TeamMark team={b}/></Card><dl className="record-splits">{view.records.slice(1).map(r=><div key={r.label}><dt>{r.label} record</dt><dd>{r.value}</dd></div>)}</dl></Section>;
}

function MatchupHistory({ view, manifest, expandedId, setExpandedId, mode }) {
  const teamById=Object.fromEntries(manifest.teams.map(t=>[t.teamId,t]));
  const teamA=teamById[view.team1Id];const teamB=teamById[view.team2Id];
  return <Section title={mode==='theoretical'?'Week-by-Week Results':'Matchup History'} meta="Select a row for player details"><TableCard className="h2h-table-card"><div className="h2h-history" role="list">{view.history.map(row=>{const winner=teamById[row.winnerTeamId];const open=expandedId===row.id;const [scoreA,scoreB]=String(row.fields.Score).split(' - ').map(value=>Number(value).toLocaleString());const type=mode==='theoretical'?'Regular':row.fields.Type;const toggle=()=>setExpandedId(nextExpandedId(expandedId,row.id));return <div className="matchup-entry" key={row.id}><button type="button" className="result-row" style={{'--winner-color':winner?.color||'var(--color-border)'}} onClick={toggle} aria-expanded={open}><span className={`row-team-mark ${winner?.teamId===teamA?.teamId?'winner':''}`}><TeamMark team={teamA} size={42}/></span><span className="row-result"><strong>{scoreA} - {scoreB}</strong><small>{row.fields.Year} Week {row.fields.Week}, {type}</small></span><span className={`row-team-mark row-team-mark-b ${winner?.teamId===teamB?.teamId?'winner':''}`}><TeamMark team={teamB} size={42}/></span></button>{open&&<MatchupDetails details={row.details} teams={manifest.teams}/>}</div>})}</div></TableCard></Section>;
}

export default function H2HPage({ mode }) {
  const [manifest,setManifest]=useState(null);const [first,setFirst]=useState('');const [second,setSecond]=useState('');const [view,setView]=useState(null);const [season,setSeason]=useState('Summary');const [expandedId,setExpandedId]=useState(null);const [error,setError]=useState(false);
  useEffect(()=>{let active=true;getData('historical-h2h.json').then(d=>{if(active)setManifest(d);}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  useEffect(()=>{let active=true;setView(null);setSeason('Summary');setExpandedId(null);if(manifest&&first&&second){setError(false);const pair=manifest.pairs[`${first}-${second}`];getData(`historical-h2h/${pair}.json`).then(d=>{if(active)setView(d[mode][first]);}).catch(()=>{if(active)setError(true);});}return()=>{active=false;};},[manifest,first,second,mode]);
  const theoretical=mode==='theoretical';
  const filteredView=view&&theoretical?{...view,history:season==='Summary'?view.history:view.history.filter(row=>String(row.fields.Year)===season)}:view;
  const record=view&&theoretical?view.records[season]:null;
  return <><a className="skip" href="#h2h-page">Skip to content</a><Header active="h2h"/><PageShell id="h2h-page" className="h2h-page"><PageHeader title={theoretical?'Theoretical H2H':'Historical H2H'} meta={theoretical?'Regular-season comparison':'Actual matchups'}/>{theoretical&&<p className="h2h-intro">What if these two teams played each other every single week? Compare their finalized regular-season performances from the same actual week.</p>}{manifest&&<MatchupSelector teams={manifest.teams} first={first} second={second} setFirst={setFirst} setSecond={setSecond}/>} {error?<section className="message" role="alert"><h2>H2H unavailable</h2><p>Please reload to try again.</p></section>:!manifest?<p role="status">Loading…</p>:!first||!second?<p className="selection-prompt">Choose two teams to begin.</p>:!view?<p role="status">Loading…</p>:view.message?<p className="selection-prompt">{view.message}</p>:<>{theoretical&&<label className="season-selector h2h-season">Season<select value={season} onChange={event=>{setSeason(event.target.value);setExpandedId(null);}}><option>Summary</option>{view.seasons.map(year=><option key={year} value={year}>{year}</option>)}</select></label>}<ResultRecord mode={mode} view={filteredView} record={record} teams={manifest.teams}/><MatchupHistory mode={mode} view={filteredView} manifest={manifest} expandedId={expandedId} setExpandedId={setExpandedId}/></>}</PageShell></>;
}
