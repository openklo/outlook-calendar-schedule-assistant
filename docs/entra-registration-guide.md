# Microsoft Entra Application Registration Guide (calendar-overview)

This plugin reads your calendar via Microsoft Graph **delegated** permissions
(Authorization Code + PKCE, multi-tenant `organizations`, work/school accounts
only). It needs **no new app registration**: `Calendars.Read` is already a
delegated scope for the morning-digest Entra app, so calendar-overview reuses
the same `MSFT_CLIENT_ID` and the same delegated scope set.

## Scopes delegated for this app (already requested)

- `offline_access` — refresh tokens (long-lived sessions).
- `User.Read` — basic user profile.
- `Mail.Read` — morning-digest mail digest.
- `Calendars.Read` — **calendar-overview** calendarView / findMeetingTimes.
- `Mail.ReadWrite` — optional draft-reply (never auto-sent).

Because `Calendars.Read` is already among them, you do **not** have to register
a new app or add new scopes — point calendar-overview at the existing
`MSFT_CLIENT_ID` and run the 2-step `login`/`consume` flow in
`../after-install.md` against the bundled `scripts/msgraph_auth.py`.

## Thin pointer — full walkthrough

For the end-to-end registration flow (public client app, delegated vs
application permissions, `offline_access`, consent, multi-tenant
`organizations` authority), reuse the morning-digest guide by reference:

    ~/.hermes/plugins/morning-digest/docs/entra-registration-guide.md

The only difference for this plugin is the `Calendars.Read` scope above, which is
already covered because it is part of the same delegated scope set.
