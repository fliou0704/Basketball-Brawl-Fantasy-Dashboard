// Fixed destination: this Worker cannot dispatch an arbitrary repository/workflow.
export const REPO = 'fliou0704/Basketball-Brawl-Fantasy-Dashboard';
export const WORKFLOW = 'live-scoring.yml';
const ROOT = `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}`;
const SLOT = 300_000, COOLDOWN = 240_000, MAX_BODY = 512_000;
class SafeError extends Error {
  constructor(code, httpStatus) { super(code); this.code = code; this.httpStatus = httpStatus; }
}

export async function runTick(ctx, env, scheduledTime, io = {}) {
  const now = io.now || Date.now, fetcher = io.fetch || fetch;
  const sleep = io.sleep || (ms => new Promise(resolve => setTimeout(resolve, ms)));
  const started = now(), deadline = started + 45_000;
  if (env.SCHEDULER_ENABLED !== 'true') return {status: 'skipped', code: 'disabled'};
  if (!/^github_pat_[A-Za-z0-9_]+$/.test(env.GITHUB_TOKEN || ''))
    return {status: 'error', code: 'fine_grained_token_required'};
  if (!Number.isSafeInteger(scheduledTime) || started - scheduledTime > COOLDOWN || scheduledTime > started + 60_000)
    return {status: 'skipped', code: 'stale_or_invalid_tick'};
  const slot = Math.floor(scheduledTime / SLOT);
  let claimed = false, phase = 'claim';

  async function request(url, method = 'GET', body) {
    // GETs are idempotent; POST dispatch has no idempotency key. Never replay an
    // ambiguous POST, including a timeout/5xx: it might already have created a run.
    for (let attempt = 0; attempt < (method === 'GET' ? 2 : 1); attempt++) {
      if (now() >= deadline) throw new SafeError('deadline_exceeded');
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), Math.min(8_000, deadline - now()));
      try {
        const r = await fetcher(url, {
          method, redirect: 'manual', signal: controller.signal,
          headers: {Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2026-03-10', 'User-Agent': 'basketball-brawl-live-scheduler',
            'Content-Type': 'application/json'},
          ...(body ? {body: JSON.stringify(body)} : {})
        });
        if (method === 'GET' && attempt === 0 && [429, 500, 502, 503, 504].includes(r.status)) {
          const delay = Number(r.headers.get('retry-after') || '1');
          await r.body?.cancel();
          if (!Number.isFinite(delay) || delay < 0 || delay > 1)
            throw new SafeError('retry_deferred', r.status);
          await sleep(Math.max(250, delay * 1000));
          continue;
        }
        if (!r.ok) {
          await r.body?.cancel();
          throw new SafeError(method === 'POST' && r.status >= 500 ? 'dispatch_ambiguous' :
            [401, 403].includes(r.status) ? 'github_auth_or_permission_failed' : 'github_http_error', r.status);
        }
        if (Number(r.headers.get('content-length')) > MAX_BODY) {
          await r.body?.cancel();
          throw new SafeError('oversized_response');
        }
        const text = await r.text();
        if (text.length > MAX_BODY) throw new SafeError('oversized_response');
        let data = null;
        try { if (text) data = JSON.parse(text); }
        catch { if (method === 'GET') throw new SafeError('invalid_github_json'); }
        return {status: r.status, data};
      } catch (error) {
        if (error instanceof SafeError) throw error;
        if (method === 'POST') throw new SafeError('dispatch_ambiguous');
        if (attempt === 1) throw new SafeError('github_network_or_timeout');
        await sleep(250);
      } finally { clearTimeout(timer); }
    }
  }

  try {
    const skip = await ctx.blockConcurrencyWhile(async () => {
      const old = await ctx.storage.get('guard');
      if (old && (old.version !== 1 || !Number.isSafeInteger(old.lastSlot) || !Number.isFinite(old.leaseUntil) || !Number.isFinite(old.lastPostAt)))
        throw new SafeError('invalid_guard_state');
      if (old && slot <= old.lastSlot) return 'duplicate_or_old_tick';
      if (old?.leaseUntil > started) return 'dispatch_in_flight';
      await ctx.storage.put('guard', {version: 1, lastSlot: slot, leaseUntil: started + 90_000, lastPostAt: old?.lastPostAt || 0});
      claimed = true;
      return old?.lastPostAt && started - old.lastPostAt < COOLDOWN ? 'dispatch_cooldown' : null;
    });
    if (skip) return {status: 'skipped', code: skip};

    phase = 'workflow';
    const {data: workflow} = await request(ROOT);
    if (workflow?.path !== `.github/workflows/${WORKFLOW}` || !Number.isSafeInteger(workflow?.id))
      throw new SafeError('workflow_identity_mismatch');
    if (workflow.state !== 'active') return {status: 'skipped', code: 'workflow_disabled'};

    phase = 'runs';
    const {data} = await request(`${ROOT}/runs?branch=main&per_page=20`);
    if (!Array.isArray(data?.workflow_runs)) throw new SafeError('invalid_run_list');
    for (const run of data.workflow_runs) {
      if (run.workflow_id !== workflow.id || run.head_branch !== 'main' || !Number.isSafeInteger(run.id) || !Number.isFinite(Date.parse(run.created_at)))
        throw new SafeError('invalid_run_identity');
      if (run.status !== 'completed') return {status: 'skipped', code: 'workflow_busy', runId: run.id};
      if (Date.parse(run.created_at) > now() + 60_000) throw new SafeError('invalid_run_timestamp');
      if (now() - Date.parse(run.created_at) < COOLDOWN)
        return {status: 'skipped', code: 'recent_run', runId: run.id};
    }

    phase = 'dispatch';
    await ctx.blockConcurrencyWhile(async () => {
      const state = await ctx.storage.get('guard');
      if (state?.lastSlot !== slot || now() >= deadline) throw new SafeError('dispatch_lease_lost');
      await ctx.storage.put('guard', {...state, lastPostAt: now()});
    });
    const result = await request(`${ROOT}/dispatches`, 'POST', {ref: 'main', inputs: {publish: true, force: false}});
    if (![200, 204].includes(result.status)) throw new SafeError('unexpected_dispatch_status', result.status);
    const id = result.data?.workflow_run_id;
    return {status: 'accepted', code: 'dispatch_accepted', httpStatus: result.status,
      ...(Number.isSafeInteger(id) && id > 0 ? {runId: id, runUrl: `https://github.com/${REPO}/actions/runs/${id}`} : {})};
  } catch (error) {
    // Never log request headers, tokens, raw GitHub bodies, or exception messages.
    return {status: 'error', code: error instanceof SafeError ? error.code : 'state_or_internal_error', phase,
      ...(error instanceof SafeError && error.httpStatus ? {httpStatus: error.httpStatus} : {})};
  } finally {
    if (claimed) {
      try {
        await ctx.blockConcurrencyWhile(async () => {
          const state = await ctx.storage.get('guard');
          if (state?.lastSlot === slot) await ctx.storage.put('guard', {...state, leaseUntil: 0});
        });
      } catch { /* A persisted claim still prevents replay; the lease expires after 90s. */ }
    }
  }
}
