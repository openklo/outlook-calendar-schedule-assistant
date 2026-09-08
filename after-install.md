# calendar-overview — first-time setup

This plugin reuses the **bundled** `scripts/msgraph_auth.py` auth core
(drift-guarded, byte-identical to morning-digest / `~/.hermes/scripts`).
Calendar read (`Calendars.Read`) is **already a delegated scope for the
morning-digest app — no new app registration needed**: the same Entra
application + the same delegated scope set (which includes `Calendars.Read`)
serves this plugin. Just point this plugin at that same `MSFT_CLIENT_ID`.

## Step 1 — set `MSFT_CLIENT_ID`

Add the application (client) ID of your existing Microsoft Entra app to your
`.env` (template at `.env.example`):

    MSFT_CLIENT_ID=<your-client-id>

If it is missing you'll be told in two places:
- **At install**, `hermes plugins install` prompts for it (`requires_env` in `plugin.yaml`).
- **At runtime**, the next `fetch_calendar_overview` / `find_free_slot` with no
  client id reports the exact two-step fix and the setup location (the `needs_auth`
  contract).

## Step 2 — the 2-step delegated login

Auth is delegated (per-user) against the `organizations` authority via
**Authorization Code + PKCE (S256)** — no client secret. Run the bundled core in
two steps:

     1) python3 ~/.hermes/plugins/calendar-overview/scripts/msgraph_auth.py login
        -> prints the authorize URL. Open it in your browser and sign in to your
           work/school account.
     2) copy the full URL your browser lands on (the unreachability page) and:
        python3 ~/.hermes/plugins/calendar-overview/scripts/msgraph_auth.py consume "<PASTED_URL>"
        -> exchanges the code, stores the access/refresh tokens in the profile .env.

`login`/`consume` write `MSFT_ACCESS_TOKEN` / `MSFT_REFRESH_TOKEN` /
`MSFT_TOKEN_EXPIRES_AT` into your `.env` — **do not commit those real values.**
`MSFT_CLIENT_ID` is a public identifier and is safe in `.env.example`.

## Onboarding summary

    MSFT_CLIENT_ID (already exists from morning-digest; no new app registration)
      -> scripts/msgraph_auth.py login  -> open URL, sign in
      -> paste the callback URL
      -> scripts/msgraph_auth.py consume "<PASTED_URL>"
      -> first `fetch_calendar_overview` / `find_free_slot` works.

Full Entra registration walkthrough (only needed if you register a brand-new app):
see `docs/entra-registration-guide.md`, which points at the morning-digest guide.
No `MSFT_GRAPH_SECRET`, `MSFT_TENANT_ID`, `MSFT_AUTHORITY`, or `MSFT_UPN` are
required — they are optional overrides.
