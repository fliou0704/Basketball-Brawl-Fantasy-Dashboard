import React from 'react';
import { Team } from './Standings';
import { Match } from './Recaps';
export default function Playoffs({ bracket }) {
  if (!bracket?.rounds?.length) return null;
  return <section className="home-section bracket-section"><div className="section-title"><h2>Playoff Bracket</h2>{bracket.champion && <span className="champion">♛ {bracket.champion.teamName}</span>}</div>
    <div className="bracket">{bracket.rounds.map((round,i)=><div className={`round ${round.status}`} key={round.week}>
      <h3>{round.title}<span>{round.status==='active'?'Active':round.status==='upcoming'?'Upcoming':`Week ${round.week} · Final`}</span></h3>
      {round.matches.map((match,j)=><div className={i===bracket.rounds.length-1 && bracket.champion?'championship-match':''} key={j}><Match match={match} completed={round.status==='completed'}/>{round.status==='completed' && match.winnerId && <p className="advances">{match.teams.find(t=>t.teamId===match.winnerId).teamName} {i===bracket.rounds.length-1?'wins the championship':'advances →'}</p>}</div>)}
      {round.byes.map(team=><div className="bye" key={team.teamId}><Team team={team}/><span>Bye to semifinals</span></div>)}
      {round.status==='upcoming' && <p className="pending-round">{i===1?'First-round':'Semifinal'} winners</p>}
    </div>)}</div>
  </section>;
}
