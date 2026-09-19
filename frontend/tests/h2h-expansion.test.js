import test from 'node:test';
import assert from 'node:assert/strict';
import { nextExpandedId } from '../src/site-data.js';

test('matchup rows keep only one player breakdown open', () => {
  let open=nextExpandedId(null,'matchup-1');
  assert.equal(open,'matchup-1');
  open=nextExpandedId(open,'matchup-2');
  assert.equal(open,'matchup-2');
  open=nextExpandedId(open,'matchup-2');
  assert.equal(open,null);
});
