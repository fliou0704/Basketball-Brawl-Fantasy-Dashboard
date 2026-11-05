import React, {useEffect,useState} from 'react';
import {getData} from '../App';
import {Section,TableCard} from './Layout';
import PlayerIdentity from './PlayerIdentity';
import {TeamLogo} from './Standings';
import {rankTop150} from '../top150-data';
const display=value=>value==null?'—':Number(value).toLocaleString(undefined,{maximumFractionDigits:1});

export default function Top150() {
  const [data,setData]=useState(null),[year,setYear]=useState(''),[mode,setMode]=useState('total'),[error,setError]=useState(false);
  useEffect(()=>{let active=true;getData('top-150.json').then(payload=>{if(active){setData(payload);setYear(String(payload.years[0]));}}).catch(()=>{if(active)setError(true);});return()=>{active=false;};},[]);
  const season=data?.seasons[year],ranking=rankTop150(season,mode);
  const row=p=><tr key={p.playerId} className={season.ownershipAvailable&&!p.fantasyTeam?'top150-free-agent':''}><td className="numeric">{p.rank??'NQ'}</td><th scope="row"><PlayerIdentity playerId={p.playerId} name={p.name} headshotUrl={p.headshot} showHeadshot size={30}/>{p.fpts==null&&<small>No recorded statistics</small>}</th><td>{p.nbaTeam||'—'}</td><td>{!season.ownershipAvailable?'Unknown':p.fantasyTeam?<span className="table-team"><TeamLogo team={p.fantasyTeam} size={24}/>{p.fantasyTeam.teamName}</span>:<span className="free-agent-label">FA</span>}</td><td className="numeric">{p.gp??'—'}</td><td className="numeric">{display(p.fpts)}</td><td className="numeric">{display(p.fptsPerGame)}</td></tr>;
  return <Section title="Top 150" meta="NBA-wide season rankings">
    {error?<p role="status">NBA-wide ranking data is unavailable. The saved fantasy roster data cannot establish the Top 150.</p>:!data?<p role="status">Loading rankings…</p>:<>
      <div className="top150-controls"><label className="season-selector">Season<select aria-label="Top 150 season" value={year} onChange={e=>setYear(e.target.value)}>{data.years.map(y=><option key={y}>{y}</option>)}</select></label><div className="player-tabs" role="group" aria-label="Ranking metric">{[['total','Total FPTS'],['perGame','FPTS/Game']].map(([value,label])=><button key={value} type="button" aria-pressed={mode===value} onClick={()=>setMode(value)}>{label}</button>)}</div></div>
      {!ranking.available?<div className="message"><p>{season?.limitation||'A verified complete NBA player pool is unavailable for this season.'}</p><p>Rankings and free-agent recommendations will appear when a complete season player pool is exported. Saved fantasy starts alone omit unrostered games and players.</p></div>:<>
        <p>Minimum {ranking.minimumGP} GP to qualify for per-game rankings. {season.gamesBasis}</p><p>{season.ownershipNote} Ties: selected metric, other metric, then ESPN player ID.</p>
        <TableCard><div className="table-scroll" role="region" aria-label="Top 150 players" tabIndex="0"><table className="data-table top150-table"><thead><tr>{['Rank','Player','NBA Team','Fantasy Team / Status','GP','Total FPTS','FPTS/Game'].map(label=><th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{ranking.top.map(row)}{ranking.below.length>0&&<tr className="top150-divider"><th colSpan="7" scope="rowgroup">Below Top 150 · rostered players (NQ = unqualified or no statistics)</th></tr>}{ranking.below.map(row)}</tbody></table></div></TableCard>
      </>}
    </>}
  </Section>;
}
