import React, { useEffect, useState } from 'react';
import { playerHref } from '../player-data';

const base=import.meta.env.BASE_URL;
let metadataPromise;

function loadMetadata() {
  if(!metadataPromise) metadataPromise=fetch(`${base}data/player-metadata.json`).then(response=>response.ok?response.json():Promise.reject(new Error('Player metadata unavailable')));
  return metadataPromise;
}

export default function PlayerIdentity({playerId,name,headshotUrl=null,showHeadshot=false,size=30,subtitle=null,className='',onClick}) {
  const href=playerHref(playerId,base);
  const [headshot,setHeadshot]=useState(headshotUrl);
  useEffect(()=>{
    if(headshotUrl) { setHeadshot(headshotUrl); return; }
    if(!showHeadshot||!href) { setHeadshot(null); return; }
    let active=true;
    loadMetadata().then(data=>{if(active)setHeadshot(data.players?.[String(playerId)]?.['Headshot URL']||null);}).catch(()=>{});
    return()=>{active=false;};
  },[headshotUrl,href,playerId,showHeadshot]);
  const content=<>{showHeadshot&&headshot&&<span className="compact-player-headshot" style={{width:size,height:size}}><img src={headshot} alt=""/></span>}<span className="player-link-copy"><span className="player-link-name">{name}</span>{subtitle&&<small>{subtitle}</small>}</span></>;
  return href?<a className={`player-link ${showHeadshot?'player-link-identity':''} ${className}`.trim()} href={href} onClick={onClick}>{content}</a>:<span className={`player-link-fallback ${className}`.trim()}>{content}</span>;
}
