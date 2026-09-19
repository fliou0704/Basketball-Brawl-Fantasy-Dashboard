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
  return <div className="player-side" style={{'--side-color':team.color}}><header><TeamMark team={team}/><div><span>{team.teamName}</span><strong>{players.reduce((sum,p)=>sum+(p.fpts||0),0).toFixed(0)} FPTS</strong></div></header><div className="player-list">{players.map((p,index)=><div className="player-row" key={`${p.name}-${index}`}><strong>{p.name}</strong><span>{p.fpts?.toFixed(1)??'—'} FPTS</span><small>Scoring components · PTS {p.pts??0} · REB {p.reb??0} · AST {p.ast??0} · STL {p.stl??0} · BLK {p.blk??0} · 3PM {p['3pm']??0}</small></div>)}</div></div>;
}

function MatchupDetails({ details, teams }) {
  const sides=details.teamIds.map((id,index)=>({team:teams.find(t=>t.teamId===id)||{teamId:id,teamName:details.teams[index],color:'#666',logo:'logos/defaultLogo.png'},players:details.players[index]}));
  return <div className="matchup-details" aria-label={`Player breakdown for ${details.year}, week ${details.week}`}><div className="details-heading"><strong>Player breakdown</strong><span>{details.year} · Week {details.week}</span></div><div className="player-sides">{sides.map(side=><PlayerSide key={side.team.teamId} {...side}/>)}</div></div>;
}

function ResultRecord({ mode, view, teams }) {
  const a=teams.find(t=>String(t.teamId)===String(view.team1Id)); const b=teams.find(t=>String(t.teamId)===String(view.team2Id));
  if(mode==='theoretical') return <Section title="Theoretical H2H Record" meta={`${view.history.length} comparable weeks`}><Card className="record-hero"><TeamMark team={a}/><div><strong>{view.record.value}</strong><span>{view.record.ties?'Wins – Losses – Ties':'Wins – Losses'}</span></div><TeamMark team={b}/></Card></Section>;
  return <Section title="All-Time H2H Record" meta={`${view.history.length} matchups`}><Card className="record-hero"><TeamMark team={a}/><div><strong>{view.records[0].value}</strong><span>Wins – Losses</span></div><TeamMark team={b}/></Card><dl className="record-splits">{view.records.slice(1).map(r=><div key={r.label}><dt>{r.label} record</dt><dd>{r.value}</dd></div>)}</dl></Section>;
}

function MatchupHistory({ view, manifest, expandedId, setExpandedId, mode }) {
  const teamById=Object.fromEntries(manifest.teams.map(t=>[t.teamId,t]));
  return <Section title={mode==='theoretical'?'Week-by-Week Results':'Matchup History'} meta="Select a row for player details"><TableCard className="h2h-table-card"><table className="h2h-history"><caption className="sr-only">Head-to-head results</caption><thead><tr><th>Winner</th>{manifest.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{view.history.map(row=>{const winner=teamById[row.winnerTeamId];const open=expandedId===row.id;const toggle=()=>setExpandedId(nextExpandedId(expandedId,row.id));return <React.Fragment key={row.id}><tr className={`${row.playoff?'h2h-playoff ':''}result-row`} style={{'--winner-color':winner?.color||'var(--color-border)'}} onClick={toggle} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();toggle();}}} tabIndex="0" aria-expanded={open}><td data-label="Winner" className="winner-cell">{winner?<TeamMark team={winner} size={34}/>:<strong>Tie</strong>}</td>{manifest.columns.map(c=><td key={c} data-label={c}>{row.fields[c]}</td>)}</tr>{open&&<tr className="details-row"><td colSpan={manifest.columns.length+1}><MatchupDetails details={row.details} teams={manifest.teams}/></td></tr>}</React.Fragment>})}</tbody></table></TableCard></Section>;
}

export default function H2HPage({ mode }) {
  const [manifest,setManifest]=useState(null);const [first,setFirst]=useState('');const [second,setSecond]=useState('');const [view,setView]=useState(null);const [expandedId,setExpandedId]=useState(null);const [error,setError]=useState(false);
  useEffect(()=>{let active=true;getData('historical-h2h.json').then(d=>{if(active)setManifest(d);}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  useEffect(()=>{let active=true;setView(null);setExpandedId(null);if(manifest&&first&&second){setError(false);const pair=manifest.pairs[`${first}-${second}`];getData(`historical-h2h/${pair}.json`).then(d=>{if(active)setView(d[mode][first]);}).catch(()=>{if(active)setError(true);});}return()=>{active=false;};},[manifest,first,second,mode]);
  const theoretical=mode==='theoretical';
  return <><a className="skip" href="#h2h-page">Skip to content</a><Header active="h2h"/><PageShell id="h2h-page" className="h2h-page"><PageHeader title={theoretical?'Theoretical H2H':'Historical H2H'} meta={theoretical?'Same-week comparison':'Actual matchups'}/><nav className="h2h-tabs" aria-label="H2H views"><a href={`${base}#/h2h/historical`} aria-current={!theoretical?'page':undefined}>Historical</a><a href={`${base}#/h2h/theoretical`} aria-current={theoretical?'page':undefined}>Theoretical</a></nav>{theoretical&&<p className="h2h-intro">What if these two teams played each other every single week? Compare their finalized performances from the same actual week.</p>}{manifest&&<MatchupSelector teams={manifest.teams} first={first} second={second} setFirst={setFirst} setSecond={setSecond}/>} {error?<section className="message" role="alert"><h2>H2H unavailable</h2><p>Please reload to try again.</p></section>:!manifest?<p role="status">Loading…</p>:!first||!second?<p className="selection-prompt">Choose two teams to begin.</p>:!view?<p role="status">Loading…</p>:view.message?<p className="selection-prompt">{view.message}</p>:<><ResultRecord mode={mode} view={view} teams={manifest.teams}/><MatchupHistory mode={mode} view={view} manifest={manifest} expandedId={expandedId} setExpandedId={setExpandedId}/></>}</PageShell></>;
}
