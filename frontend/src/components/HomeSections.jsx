import React from 'react';
import { CurrentWeek, CurrentWeekPerformances, Daily, Weekly } from './Recaps';
import Playoffs from './Playoffs';
import Standings from './Standings';

// Keep unknown score coverage distinct from a verified zero-point new week.
export default function HomeSections({ snapshot, live, publishedAt, daily, weekly, bracket, standings, allPlay }) {
  const zero = snapshot.scoringStatus === 'zero';
  const scoreboard = <CurrentWeek snapshot={snapshot} live={live} publishedAt={publishedAt} showPerformances={false}/>;
  return <>
    {zero ? <><Weekly recap={weekly}/><Daily recap={daily}/>{scoreboard}</> : <>
      {scoreboard}<CurrentWeekPerformances snapshot={snapshot}/><Daily recap={daily}/><Weekly recap={weekly}/>
    </>}
    {snapshot.state.phase === 'playoffs' && <Playoffs bracket={bracket}/>}
    <Standings data={standings} allPlay={allPlay} linkTeams final={snapshot.state.phase === 'playoffs'}/>
  </>;
}
