import React, { useEffect, useState } from 'react';
import { Header, getData } from './App';
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
  return <>
    <div className="record-highlights"><Record record={data.mvp}/></div>
    {data.allNba.map(team=><section className="home-section" key={team.label}><div className="section-title"><h2>{team.label}</h2></div><ResponsiveTable rows={team.players} fields={columns.allNba} label={team.label}/></section>)}
    <div className="record-highlights"><Record record={data.bestWaiverAdd}/></div>
    <section className="home-section"><div className="section-title"><h2>{data.mostUniqueTeams.label}</h2></div><ResponsiveTable rows={data.mostUniqueTeams.players} fields={columns.unique} label={data.mostUniqueTeams.label}/></section>
  </>;
}

export default function RecordBook() {
  const [data,setData] = useState(null);
  const [year,setYear] = useState('');
  const [error,setError] = useState(false);
  useEffect(()=>{let active=true;getData('record-book.json').then(payload=>{if(active){setData(payload);setYear(String(payload.defaultYear));}}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  return <><a className="skip" href="#record-book">Skip to content</a><Header active="record-book"/>
    <main id="record-book" className="homepage record-book-page"><div className="home-heading"><h1>Record Book</h1></div>
      {data && <label className="record-year">Select Year:<select value={year} onChange={event=>setYear(event.target.value)}><option value="All-Time">All-Time</option>{data.years.map(value=><option key={value} value={value}>{value}</option>)}</select></label>}
      {error?<p role="alert">Record Book unavailable. Please reload to try again.</p>:!data||!year?<p role="status">Loading…</p>:year==='All-Time'?<AllTime data={data.allTime}/>:<><h2 className="award-title">{data.seasons[year].title}</h2><Season data={data.seasons[year]}/></>}
    </main></>;
}
