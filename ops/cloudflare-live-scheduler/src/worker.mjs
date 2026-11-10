import {DurableObject} from 'cloudflare:workers';
import {runTick} from './scheduler.mjs';

export class DispatchGuard extends DurableObject {
  async fetch(request) {
    if (request.method !== 'POST' || new URL(request.url).pathname !== '/tick')
      return new Response('Not found', {status: 404});
    const {scheduledTime} = await request.json();
    return Response.json(await runTick(this.ctx, this.env, scheduledTime));
  }
}

export default {
  // No public HTTP dispatch or management endpoint, even in local preview.
  fetch() { return new Response('Not found', {status: 404}); },
  async scheduled(event, env) {
    let result;
    try {
      if (env.SCHEDULER_ENABLED !== 'true') result = {status: 'skipped', code: 'disabled'};
      else {
        const id = env.DISPATCH_GUARD.idFromName('basketball-brawl-live-v1');
        const response = await env.DISPATCH_GUARD.get(id).fetch('https://guard/tick', {
          method: 'POST', body: JSON.stringify({scheduledTime: event.scheduledTime})
        });
        result = await response.json();
      }
    } catch { result = {status: 'error', code: 'guard_unavailable'}; }
    console.log(JSON.stringify({component: 'github-live-dispatch', scheduledTime: event.scheduledTime, ...result}));
    if (result.status === 'error') throw new Error(`Live scheduler failed: ${result.code}`);
  }
};
