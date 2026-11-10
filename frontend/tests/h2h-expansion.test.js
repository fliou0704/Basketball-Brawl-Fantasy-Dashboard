import test from 'node:test';
import assert from 'node:assert/strict';
import { h2hRoute, nextExpandedId } from '../src/site-data.js';

test('matchup rows keep only one player breakdown open', () => {
  let open=nextExpandedId(null,'matchup-1');
  assert.equal(open,'matchup-1');
  open=nextExpandedId(open,'matchup-2');
  assert.equal(open,'matchup-2');
  open=nextExpandedId(open,'matchup-2');
  assert.equal(open,null);
});

test('cross-route H2H navigation remounts each mode instead of retaining incompatible selected-team state',()=>{
  const historical=h2hRoute('#/h2h/historical');
  const theoretical=h2hRoute('#/h2h/theoretical');
  assert.deepEqual(historical,{mode:'historical',key:'h2h-historical'});
  assert.deepEqual(theoretical,{mode:'theoretical',key:'h2h-theoretical'});
  assert.notEqual(historical.key,theoretical.key);
  assert.equal(h2hRoute('#/standings'),null);
});
