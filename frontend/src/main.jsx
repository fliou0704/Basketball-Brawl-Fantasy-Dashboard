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
      .then(response => {
        if (!response.ok) throw new Error('Standings unavailable');
        return response.json();
      })
      .then(payload => {
        if (payload.schemaVersion !== 1 || !payload.teams?.length) throw new Error('Invalid standings');
        setData(payload);
      })
      .catch(err => { if (err.name !== 'AbortError') setError(true); });
    return () => controller.abort();
  }, []);

  return <>
    <a className="skip" href="#standings">Skip to standings</a>
    <header className="masthead"><div className="brand">Basketball Brawl</div></header>
    <main id="standings">
      <div className="page-heading">
        <h1>2026 Standings</h1>
      </div>
      {error ? <section className="message" role="alert">
        <h2>Standings couldn’t load</h2>
        <button onClick={() => window.location.reload()}>Try again</button>
      </section> : !data ? <p className="message" role="status">Loading standings…</p> : <>
        <div className="stats-scope">
          <p>Records & points: regular season through Week {data.statsThroughWeek}</p>
          {data.ranksThroughWeek !== data.statsThroughWeek &&
            <p>Rankings: through Week {data.ranksThroughWeek}</p>}
        </div>
        <ol className="mobile-standings" aria-label="2026 standings">
          {data.teams.map(team => <li key={team.teamId}>
            <div className="mobile-team-heading">
              <span className="mobile-rank"><span className="sr-only">Rank </span>{team.rank}</span>
              <div className="team">
                <img src={`${base}${team.logo}`} width="36" height="36" alt=""
                  onError={event => { event.currentTarget.style.visibility = 'hidden'; }} />
                <span className="team-name">{team.teamName}</span>
              </div>
              <div className="mobile-record"><span className="stat-label">W–L</span><strong>{team.record}</strong></div>
            </div>
            <dl className="mobile-stats">
              <div><dt><abbr title="Points for">PF</abbr></dt><dd>{team.pointsForDisplay}</dd></div>
              <div><dt><abbr title="Points against">PA</abbr></dt><dd>{team.pointsAgainstDisplay}</dd></div>
            </dl>
          </li>)}
        </ol>
        <table className="desktop-standings">
          <caption className="sr-only">2026 standings through Week {data.currentWeek}. Regular-season records and points through Week {data.statsThroughWeek}.</caption>
          <thead><tr>
            <th scope="col" className="rank" aria-label="Rank">#</th>
            <th scope="col">Team</th>
            <th scope="col" className="record">W–L</th>
            <th scope="col" className="desktop numeric">Points for</th>
            <th scope="col" className="desktop numeric">Points against</th>
          </tr></thead>
          <tbody>{data.teams.map(team => <tr key={team.teamId}>
            <td className="rank">{team.rank}</td>
            <th scope="row">
              <div className="team">
                <img src={`${base}${team.logo}`} width="40" height="40" alt=""
                  onError={event => { event.currentTarget.style.visibility = 'hidden'; }} />
                <div className="team-text">
                  <span className="team-name">{team.teamName}</span>
                </div>
              </div>
            </th>
            <td className="record">{team.record}</td>
            <td className="desktop numeric points-for">{team.pointsForDisplay}</td>
            <td className="desktop numeric">{team.pointsAgainstDisplay}</td>
          </tr>)}</tbody>
        </table>
      </>}
    </main>
  </>;
}

createRoot(document.getElementById('root')).render(<App />);
