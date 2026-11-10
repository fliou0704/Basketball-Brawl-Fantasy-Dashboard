import test from 'node:test';
import assert from 'node:assert/strict';
import config,{checkPublicLiveEnv} from '../vite.config.js';
test('only the isolated Cloudflare mode changes the production base path',()=>{
 assert.equal(config({mode:'cloudflare-preview'}).base,'/');
 for(const mode of ['production','development','preview'])assert.equal(config({mode}).base,'/Basketball-Brawl-Fantasy-Dashboard/');
});
test('preview public configuration retains backend credential rejection',()=>{
 assert.throws(()=>checkPublicLiveEnv({VITE_SUPABASE_PUBLISHABLE_KEY:'sb_secret_fixture'}));
 assert.throws(()=>checkPublicLiveEnv({VITE_ESPN_S2:'fixture'}));
});
