import React, { useEffect, useState } from 'react';
import { Header } from './App';
import { PageShell, PageHeader, Section, Card } from './components/Layout';
import { Match, Weekly } from './components/Recaps';
import { adjacentWeek, loadScoreboard, matchupStatus, scoreboardLink, selectScoreboard } from './scoreboard-data';
import { formatPublicationTime, HOME_REFRESH_MS, leagueDate } from './home-data';
import MatchupDetail from './MatchupDetail';
import { matchupKey, matchupLink } from './scoreboard-data';
import './scoreboard.css';
import { formatCalendarDate, formatCalendarRange } from './fantasy-calendar';

const base = import.meta.env.BASE_URL;
export function ScoreboardContext({selected, current, updatedAt}) {
  const timestamp=formatPublicationTime(updatedAt);
  return (
    <div className="scoreboard-context">
          {selected.start && selected.end ? <p>{selected.dateRangeKind==='observed'?'Observed dates: ':''}{formatCalendarRange(selected.start,selected.end)}</p> : <p>Schedule dates unavailable.</p>}
          {selected.state==='current' && <p>ESPN snapshot through {formatCalendarDate(current.asOfDate,'year')}.{current.asOfDate < leagueDate()?' A newer daily snapshot is not yet available.':''}</p>}
          {selected.matchups.some(match=>match.status==='current') && timestamp && <p>Last updated: <time dateTime={updatedAt}>{timestamp} ET</time></p>}
    </div>
  );
}

export default function ScoreboardPage({requested}) {
  const [snapshot,setSnapshot] = useState(null);
  const [failed,setFailed] = useState(false);
  useEffect(()=>{
    let alive=true;
    const update=()=>loadScoreboard(base).then(value=>{if(alive){setSnapshot(value);setFailed(false);}}).catch(()=>{if(alive)setFailed(true);});
    update();
    const timer=setInterval(update,HOME_REFRESH_MS);
    window.addEventListener('focus',update);
    return()=>{alive=false;clearInterval(timer);window.removeEventListener('focus',update);};
  },[]);
  const data=snapshot?.data;
  const view=data && selectScoreboard(data,requested);
  const go=(season,week)=>{window.location.hash=scoreboardLink(season,week);};
  const previous=view && adjacentWeek(data,view.season.season,view.selected.week,-1);
  const next=view && adjacentWeek(data,view.season.season,view.selected.week,1);
  const selected=view?.selected;
  return <><a className="skip" href="#scoreboard" onClick={event=>{event.preventDefault();const main=document.getElementById('scoreboard');main.setAttribute('tabindex','-1');main.focus();}}>Skip to content</a><Header active="scoreboard"/><PageShell id="scoreboard" className="scoreboard-page">
    <PageHeader title="Scoreboard" meta={view && `${view.season.season} · Week ${selected.week}`}/>
    {!data ? <p role={failed?'alert':'status'}>{failed?'Scoreboard unavailable. Please reload to try again.':'Loading scoreboard…'}</p> : <>
      <div className="scoreboard-controls" aria-label="Scoreboard selection">
        <label>Season<select aria-label="Season" value={view?.season.season ?? ''} onChange={event=>{const season=Number(event.target.value);const target=selectScoreboard(data,{season});if(target)go(season,target.selected.week);}}><option value="" disabled>Select season</option>{[...data.seasons].reverse().map(s=><option key={s.season} value={s.season}>{s.season}</option>)}</select></label>
        <label>Week<select aria-label="Week" value={selected?.week ?? ''} disabled={!view} onChange={event=>go(view.season.season,Number(event.target.value))}><option value="" disabled>Select week</option>{view?.season.weeks.map(w=><option key={w.week} value={w.week}>Week {w.week}{w.phase==='playoffs'?' · Playoffs':''}{w.start&&w.end?` · ${formatCalendarRange(w.start,w.end)}`:''}</option>)}</select></label>
        <div className="scoreboard-arrows"><button aria-label="Previous week" disabled={!previous} onClick={()=>go(previous.season,previous.week)}>←</button><button aria-label="Next week" disabled={!next} onClick={()=>go(next.season,next.week)}>→</button></div>
        <button onClick={()=>go(data.current.season,data.current.week)}>Current week</button>
      </div>
      {failed && <p role="status">Refresh failed. Showing the last loaded snapshot.</p>}
      {!view ? <Card><p role="status">This season or week is unavailable. Choose a season or return to the current week.</p></Card> : <>{requested.match ? <MatchupDetail key={`${view.season.season}-${selected.week}-${requested.match}`} season={view.season.season} week={selected} match={selected.matchups.find(m=>matchupKey(m)===requested.match)} updatedAt={data.updatedAt}/> : <><Section title={`Week ${selected.week}${selected.phase==='playoffs'?' · Playoffs':''}`} meta={`${view.season.season} · ${matchupStatus[selected.state]}`}>
        <ScoreboardContext selected={selected} current={data.current} updatedAt={data.updatedAt}/>
        <Card><div className="scoreboard-list" aria-live="polite">{selected.matchups.map(match=><a key={match.id} className="scoreboard-match matchup-link" href={matchupLink(view.season.season,selected.week,match)} aria-label={`Open matchup: ${match.teams.map(t=>t.teamName).join(' versus ')}`}><p className={`match-status ${match.status}`}>{matchupStatus[match.status]}</p><Match match={match} completed={match.status==='final'}/></a>)}</div>
          {!selected.matchups.length && <p role="status">Matchup assignments are unavailable or have not been published for this week.</p>}
        </Card>
        {view.season.unpublishedPlayoffs && <p className="source-note">Playoff assignments have not been published. They will appear when verified ESPN matchups become available.</p>}
      </Section><Weekly recap={selected.state === 'final' ? selected.recap : null}/></>}</>}
    </>}
  </PageShell></>;
}
