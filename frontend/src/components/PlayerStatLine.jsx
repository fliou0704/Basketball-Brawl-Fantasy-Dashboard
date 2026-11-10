import React from 'react';

export default function PlayerStatLine({ stats = {} }) {
  const value = key => stats[key] ?? '—';
  return <dl className="stat-line">
    {['PTS','REB','AST','BLK','STL','TO'].map(key=><div key={key}><dt>{key}</dt><dd>{value(key)}</dd></div>)}
    <div><dt>FGM/A</dt><dd>{value('FGM')}/{value('FGA')}</dd></div>
    <div><dt>3PM/A</dt><dd>{value('3PM')}/{value('3PA')}</dd></div>
  </dl>;
}
