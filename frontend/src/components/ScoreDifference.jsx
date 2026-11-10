import React from 'react';
const fmt=n=>Number(n).toLocaleString('en-US',{maximumFractionDigits:2});

export default function ScoreDifference({official,eligible,label}) {
  if(official==null||eligible==null||Math.abs(official-eligible)<.01)return null;
  return <p className="source-note score-difference">{label&&`${label} · `}Official matchup score: {fmt(official)} FPTS. Eligible player points: {fmt(eligible)} FPTS. Difference reflects historical ESPN scoring records. Official results and player-based FP/Start are preserved.</p>;
}
