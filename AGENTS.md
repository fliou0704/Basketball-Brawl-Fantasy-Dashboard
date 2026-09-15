# ESPN diagnostics and credentials

# Frontend design system

- Before changing frontend layout, styling, navigation, or reusable UI, read and follow `frontend/DESIGN_SYSTEM.md`.
- Treat the Home page as the reference implementation. Reuse its design tokens and shared primitives rather than introducing page-specific equivalents.
- Keep orange for Basketball Brawl brand/interaction states and gold for achievements, winners, champions, and MVP treatment.
- Do not comprehensively restyle migrated pages unless the task explicitly includes them.

- Live ESPN diagnostics and updater previews are authorized to run autonomously when live data is needed to validate behavior. Do not ask for credentials on each run.
- Credentials are available through the `ESPN_S2` and `SWID` environment variables. `dataUpdateSafety.py` centrally loads the root `.env` using python-dotenv without overriding existing environment variables. Use the existing `require_espn_credentials()` helper.
- The user alone creates and populates the local `.env`. Never inspect its contents or create or populate actual credential values. If credentials are missing, report only the missing variable names and ask the user to configure them locally.
- Never print, log, commit, copy into source, or add secret values to fixtures. Do not dump environment variables, cookies, request headers, or authenticated request details. Keep diagnostic output free of secrets.
- Keep `.env` and local `.env.*` variants ignored by Git. `.env.example` must contain only `ESPN_S2=` and `SWID=` with blank values.
- GitHub Actions continues to use GitHub Secrets through environment variables; do not replace or override them with local configuration.
- Prefer offline unit tests normally: `python -m unittest discover -s tests -v`. Live ESPN API calls are allowed for validation that requires live data. Use previews when checking updater behavior to avoid unintended writes to production datasets.
