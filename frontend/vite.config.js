import { defineConfig,loadEnv } from 'vite';

export function checkPublicLiveEnv(env) {
  for(const [name,value]of Object.entries(env))if(name.startsWith('VITE_')&&value&&/SECRET|ESPN_S2|SWID/i.test(name))throw Error('Backend credentials must never use a VITE_ variable');
  if(env.VITE_SUPABASE_PUBLISHABLE_KEY&&!env.VITE_SUPABASE_PUBLISHABLE_KEY.startsWith('sb_publishable_'))throw Error('Frontend Supabase key must be publishable');
  if(env.VITE_ENABLE_LIVE_SCORING==='true'&&(!/^https:\/\/[a-z0-9-]+\.supabase\.co\/?$/.test(env.VITE_SUPABASE_URL||'')||!env.VITE_SUPABASE_PUBLISHABLE_KEY||!/^[a-f0-9-]{36}$/.test(env.VITE_LIVE_LEAGUE_ID||'')))throw Error('Live scoring requires explicit public URL, publishable key and league UUID');
}
export default defineConfig(({mode})=>{
  checkPublicLiveEnv({...loadEnv(mode,process.cwd(),'VITE_'),...process.env});
  return {base:mode==='cloudflare-preview'?'/':'/Basketball-Brawl-Fantasy-Dashboard/'};
});
