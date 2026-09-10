# Basketball Brawl — Stage 1

An isolated React + Vite prototype. No Dash server, ESPN requests, credentials,
browser-side standings calculations, charts, or production writes are involved.

## Local preview

Requires Python 3.10+ and Node 22.12+ (Node 22 LTS recommended).
From the repository root:

```sh
python3 frontend/scripts/generate_standings.py
cd frontend
npm ci
npm run build
npm run preview
```

Open http://localhost:4173/Basketball-Brawl-Fantasy-Dashboard/.
For development, use `npm run dev` instead of build/preview and follow its URL.
Regenerate JSON after the source CSV changes; `npm run build` consumes the existing
snapshot, while CI always regenerates it before building.

## Data contract

`public/data/standings.json` is a generated, deterministic snapshot:

- `schemaVersion`: 1
- `season`: 2026
- `statsThroughWeek`, `ranksThroughWeek`: source week numbers
- `teamCount`, `statsScope`, `source`: snapshot metadata
- `teams`: rank-ordered objects with `rank`, `teamId`, `teamName`, `abbreviation`,
  `wins`, `losses`, `record`, `pointsFor`, `pointsAgainst`, `pointsForDisplay`,
  `pointsAgainstDisplay`, and `logo`

The exporter uses the latest 2026 regular-season cumulative totals and the latest
2026 ranks, matching the Dash home page's convention. Teams are joined by stable
team ID. It never combines playoff points with regular-season totals. Existing
cumulative values are already precomputed by Python; selection, ordering, record
creation and number formatting happen in the exporter. React only renders them.
The checked-in data currently covers 10 teams through Week 16, not a live season
feed. No owner names or authenticated URLs are exported.

Logo paths are relative to the Vite base. The exporter safely reads the literal
logo mapping in `dataStore.py` without importing it, then copies the ten needed
local images from `assets/logos/` into `public/logos/`.

## Technology

React and React DOM are the only runtime dependencies. Vite builds JSX directly.
The lockfile pins the installed dependency graph. Styling uses plain CSS, system
fonts, responsive semantic tables, and no external font or image requests.
Loading, failure/retry and no-JavaScript messages are included.

## GitHub Pages (not enabled yet)

`../.github/workflows/frontend-pages.yml` runs only on a push to `codex` affecting
the frontend, source CSV, logo mapping/images, or the workflow itself. It checks
out the repository, sets up Node 22 and Python 3.11, runs `npm ci`, generates data,
runs exporter tests, builds, uploads only `frontend/dist`, and deploys the Pages
artifact in a separate job. Only deployment receives Pages and OIDC permissions.
It never commits generated files, calls the updaters, or deploys Render.

Vite's base is `/Basketball-Brawl-Fantasy-Dashboard/`; fetches and logos use that
same base. The eventual URL is:
https://fliou0704.github.io/Basketball-Brawl-Fantasy-Dashboard/

Before the first authorized push/deployment, manually select **Settings → Pages
→ Build and deployment → Source: GitHub Actions**. Ensure Actions are allowed and
the `github-pages` environment's deployment branch rules permit `codex` (if the
environment restricts deployments). The workflow does not enable Pages itself.
There is deliberately no manual-dispatch trigger: GitHub requires a dispatch
workflow on the default branch, and Stage 1 must remain exclusively on `codex`.

## Validation

From the repository root:

```sh
python3 -m unittest discover -s frontend/scripts -p 'test_*.py' -v
python3 -m unittest discover -s tests -v
```

The existing suite requires the root Python dependencies. The exporter itself
uses only Python's standard library. Exporter tests compare cumulative fields
against independently summed weekly CSV values and check playoff snapshot
semantics and invalid input. During Stage 1 validation, all 56 existing tests and
3 exporter tests passed. The Vite production build passed, and browser inspection
confirmed desktop plus 390px and 320px layouts with no horizontal overflow and all
10 logos loaded. This is local validation; hosted/mobile-network performance
remains to be measured after an authorized deployment.

## Created files

```text
.github/workflows/frontend-pages.yml
frontend/
  .gitignore
  README.md
  index.html
  package.json
  package-lock.json
  vite.config.js
  scripts/
    generate_standings.py
    test_generate_standings.py
  src/
    main.jsx
    styles.css
  public/
    data/standings.json
    logos/
      ForAllthebullDawgs.png
      IWatchBasketbal.png
      NYCChoppCheese.png
      NewJerseyEren.png
      PaulieGees.png
      PoohShaisty.png
      TeamChigga.png
      TheBronxOrthodoxChurch.png
      WhoInvitedThisKid.png
      wembarassing.png
```

Local `frontend/node_modules/`, `frontend/dist/`, and Python `__pycache__/`
directories are generated and ignored. All original production files and
pre-existing workspace edits are left unchanged.
