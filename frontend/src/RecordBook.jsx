import React, { useEffect, useState } from 'react';
import { Header, getData } from './App';
import { Card, PageHeader, PageShell, Section } from './components/Layout';
import { TeamLogo } from './components/Standings';
import './record-book.css';

const columns = {
  transactions: [['Asset','Player Name'],['Transaction Count','Transaction Count']],
  days: [['Date','Date'],['Player Name','Player Name'],['Team Name','Team Name'],['FPTS','FPTS']],
};

function ResponsiveTable({ rows, fields, label }) {
  return <table className="record-table"><caption className="sr-only">{label}</caption>
    <thead><tr>{fields.map(([key,name])=><th key={key} scope="col">{name}</th>)}</tr></thead>
    <tbody>{rows.map((row,index)=><tr key={index}>{fields.map(([key,name],cell)=>cell===0
      ? <th key={key} scope="row" data-label={name}>{row[key]}</th>
      : <td key={key} data-label={name}>{key==='Team Name'&&row.team?<span className="table-team"><TeamLogo team={row.team} size={26}/>{row[key]}</span>:row[key]}</td>)}</tr>)}</tbody>
  </table>;
}

function Record({ record }) {
  return <Card className="all-time-record"><p className="award-kicker">{record.label}</p><div>{record.team&&<TeamLogo team={record.team} size={52}/>}<p>{record.value}</p></div></Card>;
}

function AllTime({ data }) {
  return <div className="all-time-record-book">
    <Section title="Championship History"><Card className="championship-timeline"><ol>{data.champions.map(champion=><li key={champion.year}><span className="timeline-year">{champion.year}</span><span className="timeline-crown" aria-hidden="true">♛</span><TeamLogo team={champion.team} size={48}/><strong>{champion.team.teamName}</strong></li>)}</ol></Card></Section>
    <Section title="Most Points"><div className="all-time-records">{data.records.map(record=><Record key={record.label} record={record}/>)}</div></Section>
    <ExpandableTable title="Players with 100+ Point Days" rows={data.hundredPointDays} fields={columns.days}><p className="record-counts">{data.hundredPointCounts.map(row=>`${row['Player Name']}: ${row.Count}`).join(', ')}</p></ExpandableTable>
    <ExpandableTable title="Players with Negative Point Days" rows={data.negativePointDays} fields={columns.days}><div className="negative-team-counts">{data.negativeTeamCounts.map((row,index)=><span key={`${row.logo}-${index}`}><img src={`${import.meta.env.BASE_URL}${row.logo}`} alt=""/>: {row.count}</span>)}</div></ExpandableTable>
    <ExpandableTable title="Top 10 Most Active Players (Total Transactions)" rows={data.transactionLeaders} fields={columns.transactions}/>
  </div>;
}

function ExpandableTable({ title, rows, fields, children }) {
  return <section className="all-time-expandable"><details><summary><span>{title}</span><span className="summary-meta">{rows.length} records <span className="award-caret" aria-hidden="true">⌄</span></span></summary><div className="expandable-table-body"><ResponsiveTable rows={rows} fields={fields} label={title}/>{children}</div></details></section>;
}

function Season({ data }) {
  const firstJourneymen=data.journeymen.filter(player=>player.rank===1);
  return <div className="season-honors">
    <section className="premier-awards" aria-label="Premier season awards">
      <Card className="premier-award champion-card"><p className="award-kicker">Champion</p>{data.champion?<TeamIdentity team={data.champion}/>:<p className="award-pending">Season in progress</p>}</Card>
      <Card className="premier-award mvp-card"><p className="award-kicker">Most Valuable Player</p><PlayerIdentity player={data.mvp} featured/><p className="award-points">{formatPoints(data.mvp.points)} FPTS</p></Card>
    </section>
    <Section title="All-Fantasy Team" meta={`${data.roster.activeSlots.length} starters · ${data.roster.benchSlots} bench`} className="all-fantasy-section">
      <Card className="fantasy-roster"><div className="roster-columns" aria-hidden="true"><span>Slot</span><span>Player</span><span>FPTS</span></div><ol>{data.allFantasyTeam.map((player,index)=><li key={player.playerId}><span className={`roster-slot ${player.slot==='BE'?'bench':''}`}>{player.slot==='BE'?`BE ${index-data.roster.activeSlots.length+1}`:player.slot}</span><PlayerIdentity player={player}/><strong>{formatPoints(player.points)} <small>FPTS</small></strong></li>)}</ol></Card>
    </Section>
    <ExpandableAward title="Best Waiver Add" players={data.bestWaiverAdds}/>
    <ExpandableAward title="Best Draft Pick" players={data.bestDraftPicks}/>
    <ExpandableAward title="Journeyman" players={data.journeymen} leaders={firstJourneymen} journeyman expandLabel="View Other Popular Players"/>
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
  return <div className="award-leaders">{players.map(player=><div className="award-leader" key={player.playerId??player.name}>{journeyman?<JourneymanIdentity player={player}/>:<><PlayerIdentity player={player}/><strong className="award-result">{formatPoints(player.points)} <small>FPTS</small></strong></>}</div>)}</div>;
}

function JourneymanIdentity({ player }) {
  return <div className="journeyman-identity"><div><strong>{player.name}</strong><span>{player.teamCount} fantasy teams</span></div><div className="journeyman-logos" aria-label={`${player.name} fantasy teams`}>{player.teams.map(team=><TeamLogo key={team.teamId} team={team} size={24}/>)}</div></div>;
}

function ExpandableAward({ title, players, leaders=players.slice(0,1), journeyman=false, expandLabel='View Top 10' }) {
  const expandedPlayers=journeyman?players.filter(player=>player.rank!==1):players;
  return <Section title={title} className="compact-award-section"><Card className="expandable-award"><AwardLeaders players={leaders} journeyman={journeyman}/>{expandedPlayers.length>0&&<details><summary><span>{expandLabel}</span><span className="award-caret" aria-hidden="true">⌄</span></summary><ol className="award-ranking">{expandedPlayers.map(player=><li key={player.playerId??player.name}><span className="award-rank">{journeyman?player.rank:players.indexOf(player)+1}</span>{journeyman?<JourneymanIdentity player={player}/>:<PlayerIdentity player={player}/>} {!journeyman&&<strong className="award-result">{formatPoints(player.points)} <small>FPTS</small></strong>}</li>)}</ol></details>}</Card></Section>;
}

export default function RecordBook() {
  const [data,setData] = useState(null);
  const [year,setYear] = useState('');
  const [error,setError] = useState(false);
  useEffect(()=>{let active=true;getData('record-book.json').then(payload=>{if(active){setData(payload);setYear(String(payload.defaultYear));}}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  return <><a className="skip" href="#record-book">Skip to content</a><Header active="record-book"/>
    <PageShell id="record-book" className="record-book-page"><PageHeader title="Record Book" meta={data&&<label className="season-selector">Year<select aria-label="Year" value={year} onChange={event=>setYear(event.target.value)}><option value="All-Time">All-Time</option>{data.years.map(value=><option key={value} value={value}>{value}</option>)}</select></label>}/>
      {error?<p role="alert">Record Book unavailable. Please reload to try again.</p>:!data||!year?<p role="status">Loading…</p>:year==='All-Time'?<AllTime data={data.allTime}/>:<><h2 className="award-title">{data.seasons[year].title}</h2><Season data={data.seasons[year]}/></>}
    </PageShell></>;
}
