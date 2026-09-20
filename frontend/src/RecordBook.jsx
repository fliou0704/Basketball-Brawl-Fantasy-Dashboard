import React, { useEffect, useState } from 'react';
import { Header, getData } from './App';
import { Card, PageHeader, PageShell, Section } from './components/Layout';
import { TeamLogo } from './components/Standings';
import './record-book.css';

const columns = {
  transactions: [['Asset','Player Name'],['Transaction Count','Transaction Count']],
  days: [['Date','Date'],['Player Name','Player Name'],['Team Name','Team Name'],['FPTS','FPTS']],
  allNba: [['Position','Position'],['Player','Player'],['Team Name','Team Name'],['FPTS','FPTS']],
  unique: [['Player Name','Player Name'],['Unique Teams','Unique Teams']],
};

function ResponsiveTable({ rows, fields, label }) {
  return <table className="record-table"><caption className="sr-only">{label}</caption>
    <thead><tr>{fields.map(([key,name])=><th key={key} scope="col">{name}</th>)}</tr></thead>
    <tbody>{rows.map((row,index)=><tr key={index}>{fields.map(([key,name],cell)=>cell===0
      ? <th key={key} scope="row" data-label={name}>{row[key]}</th>
      : <td key={key} data-label={name}>{row[key]}</td>)}</tr>)}</tbody>
  </table>;
}

function Record({ record }) {
  return <section className="record-item"><h3>{record.label}</h3><p>{record.value}</p></section>;
}

function AllTime({ data }) {
  return <>
    <div className="record-highlights">{data.records.map(record=><Record key={record.label} record={record}/>)}</div>
    <section className="home-section"><div className="section-title"><h2>Top 10 Most Active Players (Total Transactions)</h2></div><ResponsiveTable rows={data.transactionLeaders} fields={columns.transactions} label="Top 10 Most Active Players"/></section>
    <section className="home-section"><div className="section-title"><h2>Players with 100+ Point Days</h2></div><ResponsiveTable rows={data.hundredPointDays} fields={columns.days} label="Players with 100+ Point Days"/><p className="record-counts">{data.hundredPointCounts.map(row=>`${row['Player Name']}: ${row.Count}`).join(', ')}</p></section>
    <section className="home-section"><div className="section-title"><h2>Players with Negative Point Days</h2></div><ResponsiveTable rows={data.negativePointDays} fields={columns.days} label="Players with Negative Point Days"/><div className="negative-team-counts">{data.negativeTeamCounts.map((row,index)=><span key={`${row.logo}-${index}`}><img src={`${import.meta.env.BASE_URL}${row.logo}`} alt=""/>: {row.count}</span>)}</div></section>
  </>;
}

function Season({ data }) {
  const firstJourneymen=data.journeymen.filter(player=>player.rank===1);
  return <div className="season-honors">
    <section className="premier-awards" aria-label="Premier season awards">
      <Card className="premier-award champion-card"><p className="award-kicker">Champion</p>{data.champion?<TeamIdentity team={data.champion}/>:<p className="award-pending">Season in progress</p>}</Card>
      <Card className="premier-award mvp-card"><p className="award-kicker">Most Valuable Player</p><PlayerIdentity player={data.mvp} featured/><p className="award-points">{formatPoints(data.mvp.points)} fantasy points</p></Card>
    </section>
    <Section title="All-Fantasy Team" meta={`${data.roster.activeSlots.length} starters · ${data.roster.benchSlots} bench`} className="all-fantasy-section">
      <Card className="fantasy-roster"><ol>{data.allFantasyTeam.map((player,index)=><li key={player.playerId}><span className={`roster-slot ${player.slot==='BE'?'bench':''}`}>{player.slot==='BE'?`BE ${index-data.roster.activeSlots.length+1}`:player.slot}</span><PlayerIdentity player={player}/><strong>{formatPoints(player.points)}</strong></li>)}</ol></Card>
    </Section>
    <ExpandableAward title="Best Waiver Add" players={data.bestWaiverAdds}/>
    <ExpandableAward title="Best Draft Pick" players={data.bestDraftPicks}/>
    <ExpandableAward title="Journeyman" players={data.journeymen} leaders={firstJourneymen} journeyman/>
  </div>;
}

const formatPoints=value=>Number(value).toLocaleString(undefined,{maximumFractionDigits:1});

function TeamIdentity({ team }) {
  return <div className="award-identity"><TeamLogo team={team} size={64}/><div><strong>{team.teamName}</strong><span>League champion</span></div></div>;
}

function PlayerIdentity({ player, featured=false }) {
  return <div className={`player-identity ${featured?'featured':''}`}>{player.team&&<TeamLogo team={player.team} size={featured?52:34}/>}<div><strong>{player.name}</strong>{player.team&&<span>{player.team.teamName}</span>}</div></div>;
}

function AwardLeaders({ players, journeyman=false }) {
  return <div className="award-leaders">{players.map(player=><div className="award-leader" key={player.playerId??player.name}>{journeyman?<div><strong>{player.name}</strong><span>{player.teamCount} fantasy teams</span></div>:<><PlayerIdentity player={player}/><strong className="award-result">{formatPoints(player.points)}</strong></>}</div>)}</div>;
}

function ExpandableAward({ title, players, leaders=players.slice(0,1), journeyman=false }) {
  return <Section title={title} className="compact-award-section"><Card className="expandable-award"><AwardLeaders players={leaders} journeyman={journeyman}/>{players.length>leaders.length&&<details><summary><span>View Top 10</span><span className="award-caret" aria-hidden="true">⌄</span></summary><ol className="award-ranking">{players.map(player=><li key={player.playerId??player.name}><span className="award-rank">{journeyman?player.rank:players.indexOf(player)+1}</span>{journeyman?<div><strong>{player.name}</strong><span>{player.teamCount} fantasy teams</span></div>:<PlayerIdentity player={player}/>} {!journeyman&&<strong className="award-result">{formatPoints(player.points)}</strong>}</li>)}</ol></details>}</Card></Section>;
}

export default function RecordBook() {
  const [data,setData] = useState(null);
  const [year,setYear] = useState('');
  const [error,setError] = useState(false);
  useEffect(()=>{let active=true;getData('record-book.json').then(payload=>{if(active){setData(payload);setYear(String(payload.defaultYear));}}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  return <><a className="skip" href="#record-book">Skip to content</a><Header active="record-book"/>
    <PageShell id="record-book" className="record-book-page"><PageHeader title="Record Book"/>
      {data && <label className="record-year">Select Year:<select value={year} onChange={event=>setYear(event.target.value)}><option value="All-Time">All-Time</option>{data.years.map(value=><option key={value} value={value}>{value}</option>)}</select></label>}
      {error?<p role="alert">Record Book unavailable. Please reload to try again.</p>:!data||!year?<p role="status">Loading…</p>:year==='All-Time'?<AllTime data={data.allTime}/>:<><h2 className="award-title">{data.seasons[year].title}</h2><Season data={data.seasons[year]}/></>}
    </PageShell></>;
}
