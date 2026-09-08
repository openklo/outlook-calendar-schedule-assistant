# calendar-overview - Microsoft Graph calendar overview + free-slot finder

One-line: a multi-day Outlook schedule overview (today + N days ahead) with
transport flagging and local memory-search pointers for agenda- / @-tagged
meetings, plus an on-demand "find me the nearest free slot for an N-hour
meeting" that pads a +-30 min transport buffer around physical meetings - all
over delegated Microsoft Graph (PKCE, multi-tenant work/school accounts).

## Capabilities (two tools)

1. `fetch_calendar_overview` - multi-day schedule overview. Default: today +
   3 days ahead. Returns sorted events, each classified and enriched.
2. `find_free_slot` - find the earliest free slot (>= duration minutes)
   starting from now over a 7-day horizon within the 09:00-18:00 local work
   window, via Graph `findMeetingTimes`. For a physical meeting a transport
   buffer of +-30 min is verified free around the chosen slot
   ([start-30, end+30]); a virtual meeting gets no buffer.

## CLI invocation

Both scripts are thin CLIs; the tool handlers (`tools.py`) just subprocess
into them and surface the JSON.

    # overview (today + 3 days by default)
    python3 scripts/calendar_overview.py --start-date YYYY-MM-DD --days-ahead 3

    # free slot (60 min virtual by default)
    python3 scripts/calendar_availability.py --duration 60 --meeting-type in-person

Flags: `fetch_calendar_overview` takes `start_date` (YYYY-MM-DD, default
today) and `days_ahead` (int, default 3). `find_free_slot` takes
`duration_minutes` (default 60) and `meeting_type` (virtual|in-person,
default virtual). Both emit JSON on stdout.

## Per-event schema

`fetch_calendar_overview` returns a JSON array; each event carries the
15-field structure (`_structure_event`) plus the embedded `memory_search`
block:

    id, subject, start_dt, start_tz, end_dt, end_tz, is_all_day, location,
    meeting_type, requires_transport, attendees, organizer, body_text,
    context_summary, categories, + memory_search

- `meeting_type` in {virtual, in-person, unknown} and `requires_transport`
  (bool) come from `_classify_meeting` (URL / provider keyword / room-name
  heuristics). `requires_transport` is True for in-person events.
- `context_summary` = {has_agenda, action_items} parsed from the body.
- `memory_search` = the preparation block from `memory_search.enrich_event`
  ({keywords, enrichment_queries, vault_results, mentioned_me}): it scans the
  Obsidian vault for prior notes and surfaces them as pointers. `mentioned_me`
  is a heuristic - body keyword scan for the user's UPN (`MSFT_UPN`) or the
  literal tokens `@me`/`mentions`.
- All-day/multi-day events: only an all-day the user has ACCEPTED
  (attendee `response.status == accepted`) blocks the full work day;
  tentative/declined do not.

## Auth: needs_auth contract

Delegated OAuth 2.0 Authorization Code + PKCE (S256) against the
`organizations` authority via the **bundled** `scripts/msgraph_auth.py`
(drift-guarded, byte-identical to morning-digest / `~/.hermes/scripts`).
Calendar read uses the `Calendars.Read` delegated scope, which is already
granted to the morning-digest app - no new app registration needed.

The only required env var is `MSFT_CLIENT_ID` (set in `~/.hermes/.env`;
template at `.env.example`). If auth is missing, a tool call returns the
`needs_auth` JSON contract instead of failing:

    {"needs_auth": true, "step_1": "python3 .../msgraph_auth.py login",
     "step_2": "paste FULL callback URL back",
     "finish": "python3 .../msgraph_auth.py consume \"<URL>\" then retry"}

Two-step login:

    1) python3 scripts/msgraph_auth.py login      -> open the authorize URL,
                                                     sign in to your account
    2) python3 scripts/msgraph_auth.py consume "<PASTED_CALLBACK_URL>"
                                                 -> stores the access/refresh
                                                     tokens in the profile .env

The token values written to `.env` must never be committed. Full first-time
setup: see `after-install.md`; a fresh Entra registration walkthrough:
`docs/entra-registration-guide.md`.

## Invariants

- Auth core is reused, not re-implemented (DRY). The `msgraph_auth.py`
  copies stay in sync via `scripts/verify-auth.sh` (3-copy drift guard).
- No sends or side effects: the plugin only reads the calendar and
  reports; it never mutates mail or calendar.

## Scenarios & how to trigger

**Current status (2026-09-08): installed but NOT enabled.** `hermes plugins
list` shows `calendar-overview | not enabled | 0.1.0 | user`, and
`~/.hermes/config.yaml` `plugins.enabled` lists only `morning-digest` +
`obsidian-index`. Until enabled, the two tools are NOT live in a Hermes
session. Auth is fine: `MSFT_CLIENT_ID`/`MSFT_ACCESS_TOKEN`/
`MSFT_REFRESH_TOKEN` are already set in `~/.hermes/.env`, so the scripts run
live as-is.

### STEP 0 (one-time, the actual blocker): enable the plugin

    hermes plugins enable calendar-overview --no-allow-tool-override

It registers 2 new tools and does not override any built-in, so
`--no-allow-tool-override` skips the confirmation prompt. Verify with
`hermes plugins list` (status -> `enabled`) or
`hermes plugins capabilities calendar-overview` (declared vs granted).
The enable writes into `plugins.enabled` + a `plugins.entries`
`allow_tool_override: false` in `~/.hermes/config.yaml`. This step was
intentionally NOT auto-run: docs only, config left untouched.

### STEP 1 (one-time, if a run ever reports `needs_auth`)

`MSFT_CLIENT_ID` is required; the delegated token comes from the bundled
core. If a tool returns the `needs_auth` contract, run (no new app
registration - reuses morning-digest's `Calendars.Read` scope + same client id):

    1) python3 scripts/msgraph_auth.py login       -> open the URL, sign in
    2) python3 scripts/msgraph_auth.py consume "<FULL_CALLBACK_URL>"

### Scenario 1 - Multi-day overview (`fetch_calendar_overview` / calendar_overview.py)

- In session: "show my calendar for the next 3 days" / "today through Friday"
- CLI: `python3 scripts/calendar_overview.py --start-date YYYY-MM-DD --days-ahead N`
  (defaults: today, 3 days)
- Output root: `date_scope / days / event_count / in_person_count /
  virtual_count / events[]`. Each `event` auto-enriches:
  - `meeting_type` in {virtual,in-person,unknown} + `requires_transport` -
    URL/provider keyword (zoom/teams/meet/gcal/webex/skype) => virtual;
    subject containing "in-person" or a plain (non-URL, non-provider) room
    name in `location.displayName` => in-person.
  - `context_summary` = {has_agenda, action_items} parsed from the body
    (agenda/objective/goals/topics-to-cover; action verbs prepare/review/
    bring/submit/read/deadline).
  - `memory_search` = {keywords (top-8, >=3 chars, stopword-dropped,
    subject + action-item boosted), enrichment_queries (1-3 natural-language
    queries for obsidian_search), vault_results (OFFLINE grep of
    $OBSIDIAN_VAULT_PATH, default `~/Documents/Obsidian Vault`, top-3
    {filename,path,matches,snippet,score}), mentioned_me (body contains
    `@me`, your `MSFT_UPN`, or "mention(s)")}.
  - All-day events block the full work day [09:00-18:00] ONLY when your
    attendee `response.status == accepted`; tentative/declined do not.

### Scenario 2 - Free-slot finder (`find_free_slot` / calendar_availability.py)

- In session: "find a free 60-minute in-person slot"
- CLI: `python3 scripts/calendar_availability.py --duration M --meeting-type {virtual,in-person}`
  flags: `--start-date D` (default today), `--horizon-days N` (default 7),
  `--work-start 09:00`, `--work-end 18:00`, `--buffer 30` (defaults 60 /
  virtual / today / 7d / 09:00-18:00 / 30).
- Output: `{found, start, end, meeting_type, transport_buffer_min,
  busy_count}` or `{found:false, reason}`. in-person verifies
  `[start-30, end+30]` free (transport buffer); virtual gets no buffer.
- NOTE flag-forwarding gap: the TOOL schema (`find_free_slot`) forwards only
  `duration_minutes` + `meeting_type`; `--start-date`/`--horizon-days`/
  `--work-start`/`--work-end`/`--buffer` are CLI-only, not exposed by the tool.

### Scenario 3 - Offline memory search (NO token, NO network)

`memory_search.py` is the engine Scenario 1 embeds, and a standalone CLI:

- CLI: `python3 scripts/memory_search.py --event-json '{...event...}'
  [--emit-queries] [--self-email <MSFT_UPN>] [--top-n N]`
  (`--event-json` required; `--emit-queries` prints one NL query per line
  for obsidian_search). Pure stdlib, offline - useful for scripting without
  a live token.

### Scenario 4 - `needs_auth` fallback

If `MSFT_CLIENT_ID` or the token is missing, ANY of the two tools returns
the `needs_auth` JSON contract (see "Auth" above) instead of failing:
run STEP 1, then retry the same call. Pre-login the scripts exit 3
(`NotAuthenticatedError`); via the tool handlers that surfaces as the
`needs_auth` payload.

## Install from scratch (new machine)

Distributed as a Git repository: `git@github.com:openklo/outlook-calendar-schedule-assistant.git`.

**Option A — let Hermes install from the remote** (recommended):

    hermes plugins install openklo/outlook-calendar-schedule-assistant --no-enable
    hermes plugins enable calendar-overview --no-allow-tool-override
    hermes calendar-setup status         # then follow the rendered checklist

**Option B — clone + mirror locally** (offline, or per-profile; same consumer
pattern as the morning-digest dist repo at `~/code/hermes-morning-digest`):

    git clone git@github.com:openklo/outlook-calendar-schedule-assistant ~/code/hermes-calendar-overview
    bash ~/code/hermes-calendar-overview/scripts/update-locally.sh default

After either install, the setup wizard (or the rendered `after-install.md`
checklist) walks you through the one delegated sign-in:

    hermes calendar-setup status                     # what is set, what is missing
    hermes calendar-setup login                      # prints the authorize URL
    hermes calendar-setup consume --url "http://127.0.0.1:8765/callback?code=..."
    hermes calendar-setup verify                     # live 1-day round-trip
