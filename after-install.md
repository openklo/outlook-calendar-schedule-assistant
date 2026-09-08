# calendar-overview — first-time setup (setup wizard)

Two tools are ready as soon as one delegated sign-in completes:
`fetch_calendar_overview` (multi-day schedule overview) and `find_free_slot`
(nearest free slot, +-30 min transport padding for physical meetings).
Auth is delegated Microsoft Graph (Authorization Code + PKCE) over the **bundled**
`scripts/msgraph_auth.py` core. Calendar read uses the `Calendars.Read` scope your
existing work/school Entra app already grants — **no new app registration needed**:
this plugin reuses the same `MSFT_CLIENT_ID` as your current Graph plugin.

## The 4-step wizard

    hermes calendar-setup status      # 1. see what is set vs missing
    hermes calendar-setup login       # 2. prints the authorize URL — open it, sign in
    hermes calendar-setup consume    # 3. exchange the callback URL for tokens
          --url "http://127.0.0.1:8765/callback?code=..."
    hermes calendar-setup verify      # 4. live round-trip over 1 day of calendar

`status` output contract (never prints secret values):
    {"client_id_set": bool, "token_present": bool, "ready": bool, "next_step": str|null}

## Step-by-step (manual equivalent, if you prefer plain commands)

1. **Set `MSFT_CLIENT_ID`** (Application/client ID of your existing Entra app)
   in your profile `.env` (`~/.hermes/.env`; template: `.env.example`).
   If missing, `hermes plugins install` prompts for it and `status` points you here.
2. **Login:** `python3 scripts/msgraph_auth.py login` — open the printed URL,
   sign in to your work/school account. The browser lands on a "can't reach this
   page" URL — that is expected (loopback).
3. **Consume:** paste that FULL callback URL back:
   `python3 scripts/msgraph_auth.py consume "http://127.0.0.1:8765/callback?code=..."`
   Tokens are stored in the profile `.env` — `MSFT_ACCESS_TOKEN` /
   `MSFT_REFRESH_TOKEN` are per-user secrets and must never be committed.
   `MSFT_CLIENT_ID` is a public identifier and is safe in `.env.example`.
4. **Verify:** `python3 scripts/calendar_overview.py --days-ahead 1`
   (or `hermes calendar-setup verify`) → JSON with `event_count` = working.

## If a tool returns the `needs_auth` contract instead of data

That is the plugin telling you step 2–3 are incomplete. Run:
    hermes calendar-setup login
    hermes calendar-setup consume --url "<FULL_CALLBACK_URL>"
then retry the tool call. No calendar data is mutated; this plugin only READS.

## Optional overrides (only if you know why)

`MSFT_AUTHORITY` (default `organizations`), `MSFT_REDIRECT_URI` (default loopback),
`MSFT_UPN` (used for @me detection). Full registration walkthrough for a
brand-new app: `docs/entra-registration-guide.md`.
