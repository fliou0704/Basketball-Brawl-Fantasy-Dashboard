import React from 'react';
import { CurrentWeek, CurrentWeekPerformances, Daily, Weekly } from './Recaps';
import Playoffs from './Playoffs';
import Standings from './Standings';

// Keep unknown score coverage distinct from a verified zero-point new week.
export default function HomeSections({ snapshot, publishedAt, daily, weekly, bracket, standings }) {
  const zero = snapshot.scoringStatus === 'zero';
  const scoreboard = <CurrentWeek snapshot={snapshot} publishedAt={publishedAt} showPerformances={false}/>;
  return <>
    {zero ? <><Weekly recap={weekly}/><Daily recap={daily}/>{scoreboard}</> : <>
      {scoreboard}<CurrentWeekPerformances snapshot={snapshot}/><Daily recap={daily}/><Weekly recap={weekly}/>
    </>}
    {snapshot.state.phase === 'playoffs' && <Playoffs bracket={bracket}/>}
    <Standings data={standings} final={snapshot.state.phase === 'playoffs'}/>
  </>;
}
