import React from 'react';
import { Team } from './Standings';
import { Match } from './Recaps';
export default function Playoffs({ bracket, completed }) {
  if (!bracket?.rounds?.length) return null;
  return <section className="home-section bracket-section"><div className="section-title"><h2>{completed?'Championship bracket':'Playoffs'}</h2>{bracket.champion && <span className="champion">♛ {bracket.champion.teamName}</span>}</div>
    <div className="bracket">{bracket.rounds.map((round,i)=><div className={`round ${round.status}`} key={round.week}>
      <h3>{round.title}<span>{round.status==='active'?'Current round':round.status==='upcoming'?'Upcoming':`Week ${round.week} · Final`}</span></h3>
      {round.matches.map((match,j)=><div className={i===bracket.rounds.length-1 && bracket.champion?'championship-match':''} key={j}><Match match={match} completed={round.status==='completed'}/>{round.status==='completed' && match.winnerId && <p className="advances">{match.teams.find(t=>t.teamId===match.winnerId).teamName} {i===bracket.rounds.length-1?'wins the championship':'advances →'}</p>}</div>)}
      {round.byes.map(team=><div className="bye" key={team.teamId}><Team team={team}/><span>First-round bye → Semifinals</span></div>)}
      {round.status==='upcoming' && <p className="pending-round">Winners advance from the {i===1?'first round':'semifinals'}.</p>}
    </div>)}</div>
  </section>;
}
