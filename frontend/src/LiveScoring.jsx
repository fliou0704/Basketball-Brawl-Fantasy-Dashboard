import React,{createContext,useContext,useEffect,useMemo,useSyncExternalStore} from 'react';
import {createLiveStore,liveConfig,validLive} from './live-data';
const Context=createContext(null);
export function LiveProvider({children}) {
  const store=useMemo(()=>createLiveStore(liveConfig(import.meta.env),{base:import.meta.env.BASE_URL}),[]);
  useEffect(()=>{store.start();return()=>store.destroy();},[store]);
  return <Context.Provider value={store}>{children}</Context.Provider>;
}
export function useLiveScoring(context) {
  const store=useContext(Context),key=JSON.stringify(context);
  useEffect(()=>{store?.setContext(context);},[store,key]);
  useEffect(()=>()=>store?.setContext(null),[store]);
  const empty=useMemo(()=>({row:null,error:false,loading:false,now:Date.now()}),[]);
  const state=useSyncExternalStore(store?.subscribe||(()=>()=>{}),store?.getSnapshot||(()=>empty));
  return {...state,config:store?.config||{enabled:false},context};
}
export function LiveFreshness({live}) {
  if(!live?.config.enabled||!live.context?.active||!live.windowActive)return null;
  const good=validLive(live.row,live.context,live.config,live.now);
  const minutes=good?Math.max(0,Math.floor((live.now-Date.parse(live.row.verified_at))/60000)):null;
  return <p className="source-note live-freshness" role="status">{good?`${live.error?'Scores may be delayed · ':''}Updated ${minutes<1?'less than a minute':`${minutes} minute${minutes===1?'':'s'}`} ago`:live.loading?'Updating…':'Scores may be delayed · showing canonical scores'}</p>;
}
