# Supabase live-data foundation — Stage 2A

Starting codex commit: `46a844c`. This adds a one-shot publisher, a reproducible
PostgreSQL migration and tests. The ESPN normalizer, canonical updater, CSVs,
frontend, GitHub workflows and production deployment are unchanged.

## Current project: already verified

On October 31, 2026, you applied the migration through SQL Editor. The configured
project passed the schema/security check. One fresh Basketball Brawl snapshot was
published successfully:

- NBA ESPN league **609694684**, season **2027**, ten teams / 162 players.
- **69,371-byte** normalized JSON; the first database action was `inserted`.
- Secret-key read-back matched the original JSON and revision exactly.
- Publishable-key read-back matched too; public league metadata was readable.
- All **seven anonymous mutation probes** were denied: INSERT/UPDATE/DELETE on
  each of the two tables, plus the publisher RPC.
- The probes cannot delete/change the real published row: PATCH/DELETE target a
  nonexistent UUID; inserts have invalid mandatory data as an additional safeguard.
- No recurring updates, website integration or new deployment was activated.

**Nothing else needs activation for this stage.** To inspect the result, open
Table Editor → `leagues` → find Basketball Brawl. Then open `live_snapshots`,
filter season 2027, and expand the `snapshot` JSONB cell. The table holds the
latest manual snapshot, not an automatically refreshed live feed. Its freshness
will age until an explicitly requested check/publication is performed.

## New-project setup, step by step

These instructions are for a future project or machine; do not reapply an already
successful migration or republish just to follow the checklist.

1. Open the [Supabase dashboard](https://supabase.com/dashboard), choose New project,
   choose the free plan, a project name, region and a strong database password.
   Keep the password private. This integration does not require Docker, an
   always-on server, a database password in Python, or paid resources.
2. In the project's Connect dialog / Settings, find the project URL and **API Keys**.
   Use a current **publishable** key for public reads and a **secret** key for the
   trusted backend. See [Supabase's key guidance](https://supabase.com/docs/guides/getting-started/api-keys).
   Do not put a secret key in Vite/React, browser code, GitHub files or screenshots.
3. You alone populate your local `.env`. Keep the existing ESPN variables and add
   `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SECRET_KEY`. The tracked
   `.env.example` shows blank names only. The URL is the HTTPS project root, ending
   in `.supabase.co`, without `/rest/v1`. Existing environment variables take
   precedence over dotenv. Never paste actual values into this document or a chat.
4. From the repository, `git check-ignore .env .env.local` must show ignored paths.
   `.env.*` variants are ignored; only the blank `.env.example` is tracked. This
   stage expands that template with the requested Supabase names; it does not edit
   your actual `.env` or GitHub Secrets.
5. In Supabase → **SQL Editor → New query**, paste the entire contents of
   `supabase/migrations/202610310001_live_data.sql`, then click **Run once**.
   It creates two tables, their RLS policies, and two restricted functions in one
   transaction. It does not delete data or touch unrelated tables. It intentionally
   fails if these objects already exist rather than replacing unknown schemas.
6. Check readiness from the repository:

   ```bash
   python supabasePublisher.py --check-schema
   ```

   Expected: `Supabase schema and security checks passed`. This check is read-only;
   it verifies RLS, read-only role grants, SELECT policies and restricted RPC access.
   The Data API must be enabled for the `public` schema (the normal project setup).

### First generation / publication

Use a read-only copy of the latest normal updater metadata from main. This avoids
mistaking older codex data for the current verified calendar. Nothing is merged
into main or written to canonical data:

```bash
mkdir -p /tmp/brawl-supabase
# Fetch only if the origin/main reference needs refreshing.
git fetch origin
git show origin/main:data/seasonMetadata.json > /tmp/brawl-supabase/seasonMetadata.json
python supabasePublisher.py --generate --season 2027 \
  --metadata /tmp/brawl-supabase/seasonMetadata.json \
  --output /tmp/brawl-supabase/snapshot.json \
  --sport nba --league-id 609694684 --display-name 'Basketball Brawl' \
  --visibility public --verify-anonymous
```

This preflights Supabase **before** requesting ESPN, invokes the existing adapter
once (normally two ESPN reads), publishes, reads back and checks integrity. The
publisher uses current `apikey` headers, not secret keys as Bearer JWTs. HTTP logs,
response bodies and key values are never printed. The summary reports counts,
content revision, non-secret league UUID, action and verification booleans.

Visibility is explicit. Use `--visibility private` for leagues that should not be
public, without `--verify-anonymous`. A public league's full normalized snapshot
is readable by anyone with the publishable key; ESPN authentication itself does
not mean league data should be public. Only publish with the league's authorization.

To publish an **already generated and freshly verified** snapshot, without another
ESPN request:

```bash
python supabasePublisher.py --snapshot /tmp/brawl-supabase/snapshot.json \
  --sport nba --league-id 609694684 --display-name 'Basketball Brawl' \
  --visibility public --verify-anonymous
```

The matching adapter `.state.json` must exist with a successful verification and
matching revision/league/season. It is read locally; it is never uploaded. Failed
or older-than-ten-minute verification is rejected. Do not forge a fresh timestamp
on an old file; generate a genuinely fresh adapter check if needed.

### Dry-run without Supabase credentials

```bash
python supabasePublisher.py --snapshot /tmp/brawl-supabase/snapshot.json --dry-run
```

This validates contract, identities, content hash, approved fields and timestamps,
then prints a compact summary. It makes **no network requests** and needs no
Supabase or ESPN credentials when using an existing successful snapshot/state.
Alternatively `--generate ... --dry-run` needs ESPN credentials and performs only
the adapter's bounded reads, with no Supabase connection or write. Use one mode,
not repeated ESPN generation during troubleshooting.

## Storage design and security

| Object | Purpose |
|---|---|
| `leagues` | Stable generated UUID, sport (`nba`/`nfl`), ESPN ID, display name, explicit `is_public` (default false), created/updated times |
| `live_snapshots` | FK to league, season, matchup period, scoring period/date, JSONB snapshot, schema version/revision, source/verification/publication timestamps |
| `publish_live_snapshot` | Service-role-only transactional register/upsert with row locking and stale/conflict protection |
| `live_schema_status` | Service-role-only, read-only readiness check |

The unique league identity is **(sport, ESPN league ID)**. Identical ESPN IDs in
NBA and NFL remain different leagues. The snapshot primary key is **(league UUID,
season)**: the current period replaces the previous period in that row. There is
no row added every five minutes or every date. A new season can have its own row.
Primary-key/natural-key indexes support these lookups without redundant indexes.
The schema/publisher can store either sport; `--generate` currently supports only
the existing NBA adapter. An NFL producer must supply the same validated contract
or introduce an explicit new supported schema version; this stage adds no NFL feed.

RLS and grants work together. `anon` and `authenticated` have SELECT only, and
policies show only explicitly public leagues and their snapshots. Neither can
INSERT, UPDATE, DELETE, TRUNCATE, or execute either backend RPC. The functions use
**security invoker** with an empty search path and qualified tables; they are not
public SECURITY DEFINER bypasses. Only the trusted service role can publish.
The secret key bypasses RLS by design; keep it exclusively on trusted machines.
See [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security) and
[function security](https://supabase.com/docs/guides/database/functions).

The Python publisher is separate from the adapter: publishing existing JSON does
not call ESPN or re-normalize scores. It validates the exact Stage 1 allowlist,
nested fields, scope and content hash, rejects private/cache/credential fields and
key markers, and checks for configured credential values inside text. Official
scores and known discrepancies are preserved exactly. No raw authenticated ESPN
response, cookies, owners, internal adapter cache or Supabase key is sent as data.

### Ordering, no-op and freshness rules

The RPC locks the league row, including first-insert and rollover races. It
rejects a lower scoring/matchup period, older content timestamp or older successful
verification before modifying the existing snapshot or league visibility/name.
Changed content with an ambiguous equal timestamp is rejected too. Protection is
in PostgreSQL, not a vulnerable client GET-then-PATCH sequence.

- Same revision and payload / same verification time: `unchanged`, no row rewrite.
- Same content with a later genuine successful check: `refreshed`, updates only
  verified_at; original published_at and JSON stay unchanged.
- Newer valid content: `updated`, replaces JSON and publication time.
- First snapshot: `inserted`.
- Older/conflicting snapshot: `stale`; Python reports rejection and does not force
  an overwrite. A reused revision with different JSON is rejected as a conflict.

Freshness is a necessary heartbeat, distinct from unnecessary content writes.
The database also bounds verification age and future clocks. Source time comes
from snapshot.updatedAt, verification time from the successful adapter state, and
publication time from the database. Network failures have bounded retries and
sanitized errors. A timed-out RPC might have committed; retry the **same** snapshot
safely rather than deleting rows. A newer concurrent publisher may legitimately
cause a read-back mismatch; never overwrite it to force a comparison to pass.

## Verification, tests and troubleshooting

```bash
python -m unittest tests.test_supabase_publisher -v
python -m unittest discover -s tests -v
```

Validation passed **20 focused publisher tests and all 214 backend tests**. An
embedded PostgreSQL runtime in a temporary directory executed the actual migration
and `supabase/tests/live_data.sql`: atomic/idempotent/freshness/stale behaviors,
multi-sport isolation, public/private RLS visibility and denied anonymous mutations
passed. No runtime package was added to production dependencies. For optional
manual SQL verification, paste that test file into SQL Editor after migration;
its transaction **rolls all test rows back**. Do not remove the rollback.

Additional read-only SQL Editor checks:

```sql
select public.live_schema_status();
select schemaname, tablename, policyname, roles, cmd, qual
from pg_policies
where schemaname = 'public' and tablename in ('leagues', 'live_snapshots');
select sport, espn_league_id, display_name, is_public from public.leagues;
select league_id, season, matchup_period, scoring_period, revision,
       source_updated_at, verified_at, published_at from public.live_snapshots;
```

Common issues:

- **Missing variables:** configure only the reported names locally; never send
  their values in a message. Current keys begin `sb_publishable_` / `sb_secret_`.
- **Migration not found / PGRST202 / PGRST205:** apply the SQL file in the correct
  project, ensure Data API is enabled, and wait briefly for schema-cache reload.
- **Objects already exist:** stop; do not drop tables. A successfully applied
  migration need not be applied twice. Inspect/readiness-check the existing schema.
- **Security/readiness fails:** do not publish or broaden grants. Compare the
  applied policies/grants to the migration before proceeding.
- **Anonymous read empty:** private leagues are intentionally invisible. Confirm
  the intended visibility using the secret-key/SQL Editor view, not by disabling RLS.
- **Stale snapshot/state mismatch:** run a fresh adapter check with matching metadata;
  do not copy its internal state into JSON or manually update freshness timestamps.
- **HTTP/network failure:** no request headers/body/keys appear in diagnostics.
  Check project availability and configured names; do not post raw error responses.
- **Snapshot has new fields/version:** review the producer contract and security
  allowlist before adding support. Never accept arbitrary adapter cache/raw JSON.

Tables store related rows; JSONB stores structured JSON that Table Editor can
expand/query. A primary key uniquely identifies a row. An upsert inserts or
replaces its matching row; this RPC adds freshness/order checks. RLS is PostgreSQL's
row-level filter for public access, separate from the grant permitting an operation.

## Next stage

This is a manually exercised storage foundation. Remaining work is a deliberately
separate live frontend export/client contract, a small public version/freshness
manifest, visible stale-data/fallback behavior and a controlled game-night shadow
trial. Any scheduled five-minute publisher or production React integration needs
a later authorized stage. Nothing here enables recurring updates, realtime
subscriptions, historical migration, paid hosting or automatic deployment.
