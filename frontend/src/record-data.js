// Date is the saved NBA performance date, never a fantasy matchup boundary.
export function highlightsUrl(row) {
  let date='';
  const match=String(row.Date||'').match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  const iso=match?`${match[3]}-${match[1]}-${match[2]}`:String(row.Date||'');
  if(/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const parsed=new Date(`${iso}T12:00:00Z`);
    if(!Number.isNaN(parsed.valueOf())&&parsed.toISOString().slice(0,10)===iso)
      date=new Intl.DateTimeFormat('en-US',{month:'long',day:'numeric',year:'numeric',timeZone:'UTC'}).format(parsed).replace(',','');
  }
  const query=[row['Player Name'],date,row.nbaOpponent?`vs ${row.nbaOpponent}`:null,'highlights'].filter(Boolean).join(' ');
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
}
