// All lookups consume exported scheduled rows; no inferred ESPN week arithmetic.
export function calendarSeason(data, season) {
  return data?.seasons?.find(s=>s.season===Number(season) && s.verified===true) ?? null;
}
export function scoringDate(data, season, period) {
  return calendarSeason(data,season)?.days.find(d=>d.period===Number(period))?.date ?? null;
}
export function matchupForDate(data, season, date) {
  return calendarSeason(data,season)?.days.find(d=>d.date===date)?.week ?? null;
}
export function matchupRange(data, season, week) {
  return calendarSeason(data,season)?.weeks.find(w=>w.week===Number(week)) ?? null;
}
export function matchupDates(data, season, week) {
  return calendarSeason(data,season)?.days.filter(d=>d.week===Number(week)).map(d=>d.date) ?? [];
}
function civilDate(value) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(value ?? '')) return null;
  const parsed=new Date(`${value}T12:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0,10)===value ? parsed : null;
}
export function formatCalendarDate(value, style='short') {
  const parsed=civilDate(value);
  if(!parsed) return 'Date unavailable';
  return new Intl.DateTimeFormat('en-US',{timeZone:'UTC',month:style==='long'?'long':'short',day:'numeric',...(style==='long'?{weekday:'long'}:{}),...(style==='year'?{year:'numeric'}:{})}).format(parsed);
}
export function formatCalendarRange(start, end) {
  if(!civilDate(start) || !civilDate(end) || start>end) return 'Schedule dates unavailable';
  if(start===end) return formatCalendarDate(start,'year');
  return start.slice(0,4)===end.slice(0,4)
    ? `${formatCalendarDate(start)} – ${formatCalendarDate(end)}, ${end.slice(0,4)}`
    : `${formatCalendarDate(start,'year')} – ${formatCalendarDate(end,'year')}`;
}
