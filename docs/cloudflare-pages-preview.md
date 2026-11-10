# Cloudflare Pages developer previews

Preparation only: no Cloudflare project, deployment, merge, credential/configuration change, or daily collection activation was performed. GitHub Pages from main remains production. This is a separate static developer site, not the existing Cloudflare live-scheduler Worker.

## Dashboard configuration after approval

Create a **Pages Git integration** project (not a Workers build). A suggested project name is `basketball-brawl-preview`, subject to availability. Connect the existing GitHub account/repository without adding a PAT to build variables.

| Setting | Exact value |
| --- | --- |
| Repository | `fliou0704/Basketball-Brawl-Fantasy-Dashboard` |
| Framework preset | None / custom |
| Production branch | `codex` **after this setup PR is approved and merged into codex** |
| Root directory | Leave blank: repository root |
| Build command | `python frontend/scripts/build_cloudflare_preview.py` |
| Build output directory | `frontend/dist-cloudflare` |
| Preview deployments | Custom branches |
| Include preview branches | `*` |
| Exclude preview branches | `main`, `archive/*` |
| Automatic production-branch builds | Enabled for codex; this means the developer site's stable URL only |

Cloudflare calls its primary branch “Production,” but this project's primary URL is still development-only. Do not change GitHub Pages settings, the main-only `github-pages` environment policy, production domains, Render, or the live scheduler. Cloudflare's [branch controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/) support the explicit include/exclude rules above.

Configure these **in both Cloudflare Production and Preview environments**, using the current build image:

| Variable | Value |
| --- | --- |
| `NODE_VERSION` | `22` |
| `PYTHON_VERSION` | `3.11.18` |
| `SKIP_DEPENDENCY_INSTALL` | `1` |
| `VITE_ENABLE_LIVE_SCORING` | `false` (recommended; also the script's default) |

The script explicitly installs only the existing frontend Python requirements in an isolated virtual environment and runs `npm ci` against the selected branch's frontend lockfile. Automatic root dependency installation is skipped; no ESPN/backend dependency install or updater is needed. Cloudflare documents [runtime selection and the skip-install flag](https://developers.cloudflare.com/pages/configuration/build-image/).

To preview read-only live overlays, optionally set `VITE_ENABLE_LIVE_SCORING=true` and copy these **public** values from existing production configuration into both Cloudflare environments:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY` (must begin `sb_publishable_`)
- `VITE_LIVE_LEAGUE_ID` (the actual league UUID; not `VITE_SUPABASE_LEAGUE_ID`)
- `VITE_LIVE_ESPN_LEAGUE_ID=609694684`

No Supabase configuration is required with live scoring disabled. Never add ESPN credentials, Supabase secret/service-role keys, GitHub tokens or Cloudflare deployment tokens to this build. The script rejects known backend credentials and non-publishable Supabase keys. The existing Vite public-variable validation remains in force. Supabase's anonymous read-only policies are unchanged.

## What each preview builds

The branch being built supplies React, Vite, Python exporters, shared calculations and static assets. A temporary sparse clone of the fixed public repository's **latest main** supplies all canonical data, season/calendar/schedule metadata, player archive/report/summaries and static game shards. The builder fails if required main inputs are missing; it never substitutes a stale feature CSV.

It copies only Git-tracked code/assets, excluding branch data, generated frontend JSON and all `.env` files. It then copies approved main data into the temporary code workspace and calls the existing `generate_all.py`. This also keeps exporters that reference their repository ROOT pointed at fresh approved data. Hash checks reject data changes during export/build. The only result copied back is ignored `frontend/dist-cloudflare`; canonical checkout files are never modified or committed.

One explicitly allowed **new** feature source is `data/seasonEndRosters.json` from PR #14. It is copied from the branch only when main has no version of that file. Once main has an approved version, main always wins. No other branch data is overlaid. This lets the unmerged historical-ownership feature be previewed without replacing existing canonical statistics with old branch snapshots. `/data/preview-build.json` records the approved main SHA, feature SHA, and any such feature-only source addition.

Vite's dedicated `cloudflare-preview` mode uses `/` and shows a small “Development preview” label inside the existing masthead. The normal `npm run build --prefix frontend` still uses `/Basketball-Brawl-Fantasy-Dashboard/` and contains no preview indicator. Existing hash routes (`/#/scoreboard`, `/#/players`, etc.), versioned JSON fetches, logos and images use BASE_URL. No SPA routing rewrite or Pages Function is required for those hash routes; Cloudflare also has [default SPA serving behavior](https://developers.cloudflare.com/pages/configuration/serving-pages/).

This build performs no ESPN collection, Supabase publication, Git push, canonical write, or GitHub Pages deployment. There is no Wrangler call, new GitHub workflow or recurring job. Existing public JSON/browser reads and optional Supabase reads are unchanged. The developer site refreshes approved main data **when a build occurs**, not continuously: push a development commit or retry the desired Cloudflare build to refresh it. Disabling daily NBA archive collection still means that archive may be older; previews do not invent or collect missing games.

## Bootstrap and PR #14

Cloudflare executes each selected branch's own build command/source. Merely creating the project will not add this setup to codex or PR #14.

1. Review this setup PR independently of PR #14. Recommended permanent setup: after its approved merge into codex, use codex as the Cloudflare production branch and the rules above.
2. If testing the infrastructure before that merge is desired, with separate project/deployment approval select **`cloudflare-pages-preview`** as the initial Cloudflare production branch. After the approved codex merge, change it to codex. No project has been created here.
3. **PR #14 does not appear automatically.** Its branch is `top150-improvements`, still unmerged and unchanged. Before selecting that branch for a Cloudflare preview, bring the approved preview setup into it by merging synchronized codex, or use a temporary integration branch containing both reviewed branches. Selecting the old PR #14 branch without the setup script will fail the build.
4. Select that combined branch's Cloudflare preview deployment/branch alias to inspect PR #14; the stable codex developer URL will not contain unmerged PR #14 code. A detached local integration of the two branches is used for verification without modifying or merging PR #14 itself.

Because a branch named codex already exists, Git cannot create `codex/feature-name` refs. Existing flat feature names and other feature prefixes are supported by the `*` include rule. Archive/main exclusions avoid unneeded production/archival builds.

## Local checks and cleanup

Use Python 3.11+ and Node 22.12+. Build tracked/staged source files (add new source files to Git before a local preview build), without any backend credential environment variables:

```sh
python3.11 frontend/scripts/build_cloudflare_preview.py
npm ci --prefix frontend
npm run preview --prefix frontend -- --base / --outDir dist-cloudflare --host 127.0.0.1 --port 4178
```

The script installs its dependencies in disposable directories, fetches main read-only, and never runs deployment commands. Temporary inputs/dependencies are removed afterward. `frontend/dist-cloudflare/` is ignored and can be removed/rebuilt as a generated artifact.

Test the normal GitHub Pages build separately with `npm ci --prefix frontend`, `npm run build --prefix frontend`, and `npm run preview --prefix frontend`. Do not set Cloudflare preview mode in GitHub Actions. All existing production workflows and PR #14 remain independent.

## Verification performed before review

- Local end-to-end execution with Python 3.11.18 and Node: fresh public main clone, isolated Python/npm dependency install, all exports, root-mode Vite build, and provenance matching approved main `43ea72e387c185a76f35d5bf6ab1b77a014b1679`.
- A detached checkout of PR #14 with this setup patch applied cleanly also built successfully. It used the same main data, added only the missing feature-owned historical roster source, and preserved PR #14's published branch/ref. This is local compatibility evidence, not a deployed Cloudflare preview.
- 259 backend tests, 176 exporter tests (including five new preview isolation/security tests), 107 frontend tests (including base-path/public-config regressions), and the normal GitHub Pages build passed.
- Browser checks with real HTTP at 320/390/1280px: production subpath and root preview, eight major routes, navigation, loaded JS/CSS/logos/JSON, read-only GET/HEAD requests, and preview-only indicator. The existing Team Overview has a 4px page overflow at 320px in both builds; preview does not worsen it. Other tested pages/sizes fit. No unrelated layout fix was introduced.
- Additional PR #14 root-preview browser checks verify its qualification, historical ownership and game-log behavior. Generated preview output has 783 files, maximum single-file size 4,128,741 bytes, and no canonical CSV files. Existing source data and tracked generated files remain unchanged.

No Cloudflare-hosted URL has been issued or tested: project creation and first deployment require owner approval and dashboard setup. No main/codex/PR #14 merge, production deployment, GitHub Pages setting change, collection, or Supabase publication was performed.
