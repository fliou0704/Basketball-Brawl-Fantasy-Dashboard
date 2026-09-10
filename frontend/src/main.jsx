import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const base = import.meta.env.BASE_URL;

function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${base}data/standings.json`, { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error('Standings unavailable'); return response.json(); })
      .then(payload => { if (payload.schemaVersion !== 1 || !payload.teams?.length) throw new Error('Invalid standings'); setData(payload); })
      .catch(err => { if (err.name !== 'AbortError') setError(true); });
    return () => controller.abort();
  }, []);

  return <>
    <a className="skip" href="#standings">Skip to standings</a>
    <header className="masthead"><div className="brand"><span className="ball" aria-hidden="true">✳</span> Basketball Brawl</div><span className="prototype">STAGE 01 <span> / PROTOTYPE</span></span></header>
    <main id="standings">
      <section className="hero" aria-labelledby="page-title">
        <div className="eyebrow">THE LEAGUE, AT A GLANCE</div>
        <h1 id="page-title">2026 <span>Standings</span><i>.</i></h1>
        <p>Every matchup matters. Every point counts.</p>
        <div className="season-tag"><span aria-hidden="true" />{data ? `${data.statsScope} · Through Week ${data.statsThroughWeek}` : '2026 season'}</div>
        <div className="court" aria-hidden="true"><div /></div>
      </section>
      {error ? <section className="message" role="alert"><h2>Standings couldn’t load</h2><p>Please try again in a moment.</p><button onClick={() => window.location.reload()}>Try again</button></section> : !data ? <p className="message" role="status">Loading the league…</p> : <>
        <div className="section-heading"><h2>League standings</h2><span>{data.teamCount} TEAMS</span></div>
        <div className="standings-card">
          <table><caption className="sr-only">2026 standings. Regular-season records and points through Week {data.statsThroughWeek}; ranks through Week {data.ranksThroughWeek}.</caption>
            <thead><tr><th scope="col">Rank</th><th scope="col">Team</th><th scope="col" className="record">W–L</th><th scope="col" className="desktop numeric">Points for</th><th scope="col" className="desktop numeric">Points against</th></tr></thead>
            <tbody>{data.teams.map(team => <tr key={team.teamId} className={team.rank === 1 ? 'leader' : ''}>
              <td className="rank"><span>{team.rank}</span></td>
              <th scope="row"><div className="team"><img src={`${base}${team.logo}`} width="44" height="44" alt="" onError={event => { event.currentTarget.style.visibility = 'hidden'; }} /><div><span className="team-name">{team.teamName}</span><span className="team-detail desktop">{team.abbreviation}{team.rank === 1 && ' · LEAGUE LEADER'}</span><span className="mobile-points">{team.pointsForDisplay} <abbr title="Points for">PF</abbr></span></div></div></th>
              <td className="record"><span>{team.record}</span></td><td className="desktop numeric points-for">{team.pointsForDisplay}</td><td className="desktop numeric">{team.pointsAgainstDisplay}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <p className="data-note">Regular-season records & points through Week {data.statsThroughWeek}. {data.ranksThroughWeek !== data.statsThroughWeek && `Ranks through Week ${data.ranksThroughWeek}. `}PF = points for. PA = points against.</p>
      </>}
      <footer><span>BB <span className="footer-divider">/</span> BASKETBALL BRAWL</span><span>2026 SEASON</span></footer>
    </main>
  </>;
}

createRoot(document.getElementById('root')).render(<App />);
