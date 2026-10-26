export const HOME_REFRESH_MS = 5 * 60 * 1000;

export function formatPublicationTime(value) {
  if (!value || Number.isNaN(Date.parse(value))) return null;
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone:'America/New_York', month:'2-digit', day:'2-digit', year:'2-digit',
    hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:true
  }).formatToParts(new Date(value)).map(part => [part.type, part.value]));
  return `${parts.month}/${parts.day}/${parts.year} ${parts.hour}:${parts.minute}:${parts.second} ${parts.dayPeriod}`;
}

export function leagueDate(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York', year:'numeric', month:'2-digit', day:'2-digit'}).format(now);
}

export function selectHomeState(manifest, current, requested, {preview = false, publishedAt = null, now = new Date()} = {}) {
  // A historical preview must never use a later snapshot's scores or opponents.
  if (current?.active && (!preview || requested === current.asOfDate)
      && requested >= current.asOfDate && requested >= current.seasonStart && requested <= current.seasonEnd) {
    const stale = requested > current.asOfDate || (publishedAt && now - new Date(publishedAt) > 6 * 60 * 60 * 1000);
    return {state: current.state, current, stale: Boolean(stale), publishedAt};
  }
  const state = manifest.states[requested] ?? manifest.offseasons.filter(s => s.after < requested).at(-1)?.state
    ?? {phase:'offseason', season:null};
  return {state, current:null, stale:false, publishedAt};
}

export function createHomeClient(base, fetcher = (...args) => fetch(...args)) {
  let version = null;
  const cache = new Map();
  async function json(path, revision) {
    const key = `${revision}/${path}`;
    if (!cache.has(key)) cache.set(key, fetcher(`${base}data/${path}?v=${encodeURIComponent(revision)}`, {cache:'no-cache'})
      .then(async response => {
        if (!response.ok) throw new Error('Home data unavailable');
        const value = await response.json();
        if (value.schemaVersion !== 1) throw new Error('Unsupported Home data');
        return value;
      }).catch(error => {cache.delete(key); throw error;}));
    return cache.get(key);
  }
  return {
    async load(requested, options = {}) {
      const response = await fetcher(`${base}data/home-version.json`, {cache:'no-store'});
      if (!response.ok) throw new Error('Home version unavailable');
      const marker = await response.json();
      if (marker.schemaVersion !== 1 || !marker.version) throw new Error('Unsupported Home version');
      if (version !== marker.version) {cache.clear(); version = marker.version;}
      const revision = marker.version;
      const publishedAt = response.headers?.get('last-modified') || null;
      const [manifest, current] = await Promise.all([json('homepage.json', revision), json('home-current.json', revision)]);
      const selected = selectHomeState(manifest, current, requested, {...options, publishedAt});
      const {state} = selected;
      if (!state.season) return selected;
      let names;
      if (selected.current) {
        names = ['standings', ...(state.dailyDate ? ['daily-recap'] : []), ...(state.weeklyWeek ? ['weekly-recap'] : [])];
      } else {
        names = state.phase === 'offseason' ? ['standings','playoffs','season-leaders','history']
          : state.phase === 'playoffs' ? ['standings','daily-recap','weekly-recap','playoffs']
          : ['standings','daily-recap','weekly-recap'];
      }
      const entries = await Promise.all(names.map(async name => [name, (await json(`${state.season}/${name}.json`, revision)).data]));
      const page = {...selected, ...Object.fromEntries(entries)};
      if (selected.current?.bracket) page.playoffs = {[state.playoffKey]: selected.current.bracket};
      return page;
    }
  };
}

// Visibility follows the published ESPN period, even if the visitor's clock
// advances while no newer snapshot is available. The exporter verifies the recap.
export function showHomeRecap(state) {
  if (!state || !['regular', 'playoffs'].includes(state.phase)
      || state.week <= 1 || state.weeklyWeek !== state.week - 1
      || !Number.isInteger(state.scoringPeriod)
      || !Array.isArray(state.weekScoringPeriods)) return false;
  const periods = [...new Set(state.weekScoringPeriods)].filter(Number.isInteger).sort((a,b)=>a-b);
  return periods.slice(0,2).includes(state.scoringPeriod);
}
