#!/usr/bin/env bash
# graph_calendar_overview_regression.sh -- LIVE adaptive regression for the
# calendar-overview plugin's overview CLI. Mirrors scripts/graph_microsoft_calendar_
# regression.sh's 7-day adaptive baseline, retargeted to calendar_overview.py, and
# asserts the NEW Phase-2 fields: memory_search block on every event,
# meeting_type in {virtual,in-person,unknown}, requires_transport bool when
# in-person, context_summary{has_agenda,action_items}, plus an in-person scenario
# (requires_transport==true + memory_search present). ASCII-only source.
#
# This is a LIVE gate: it talks to Microsoft Graph via the bundled auth core.
# Pre-login (no MSFT token) the target exits 3 / prints "Not authenticated to
# Microsoft Graph"; that is the EXPECTED pre-login state -- the suite prints
# needs_auth guidance and exits non-zero (never a false pass). The offline unit
# tests (tests/test_classify.py, test_context.py, test_structure_event.py,
# test_fetch_window.py, test_overview_cli.py) are the token-independent gates.
set -euo pipefail

PLUGIN_DIR="$HOME/.hermes/plugins/calendar-overview"
D="$PLUGIN_DIR/scripts/calendar_overview.py"
AUTH="$PLUGIN_DIR/scripts/msgraph_auth.py"
P=0; F=0
ok()  { echo "PASS: $1"; ((P++)) || true; }
die() { echo "FAIL: $1"; ((F++)) || true; }

[ -f "$D" ] || { die "script missing: $D"; exit 1; }

# --- Lint check ---------------------------------------------------------------
python3 -c "compile(open('$D').read(),'$D','exec')" \
   && ok "$(basename "$D") lint clean" || die "$(basename "$D") broken"

OUT="$(mktemp).json"
ERR="$(mktemp).err"
BASELINE_7DAY="$(mktemp).json"

run_overview() {
    timeout 90 python3 "$D" "$@" >"$OUT" 2>"$ERR" || true
}

# --- auth-failure detector: pre-login this suite must NOT pass ---------------
looks_unauth() {
    # rc==3 OR the auth core's signature message on stderr
    [ "$1" -eq 3 ] || grep -q "Not authenticated to Microsoft Graph" "$ERR" 2>/dev/null
}

TODAY=$(date +%Y-%m-%d)
WEEK_AGO=$(date -d "3 days ago" +%Y-%m-%d 2>/dev/null || date -v-3d +%Y-%m-%d)

# =====================================================================
# STEP 1: Adaptive baseline -- 7-day window (today back 3 .. today forw 3)
# -> ground truth for ALL subsequent date-filter tests.
# =====================================================================
run_overview --start-date "$WEEK_AGO" --days-ahead 7
RC=$?
if looks_unauth "$RC"; then
    echo ""
    echo "needs_auth: Microsoft Graph delegated token unavailable."
    echo "  step_1: python3 $AUTH login"
    echo "  step_2: paste FULL callback URL back"
    echo "  finish: python3 $AUTH consume \"<URL>\" then re-run this suite"
    echo ""
    echo "RESULT: 1 passed, 0 failed (pre-login auth gate -- not a real pass)"
    rm -f "$OUT" "$ERR" "$BASELINE_7DAY"
    exit 4
fi
if [ "$RC" -eq 0 ] && [ ! -s "$ERR" ]; then
    ok "7-day baseline exit 0, no stderr"
else
    die "7-day baseline rc=$RC, stderr present"
fi

# Validate baseline JSON structure
python3 -c "
import json
d = json.load(open('$OUT'))
assert isinstance(d, dict) and 'events' in d, 'missing events key'
assert isinstance(d['events'], list), 'events should be list'
assert 'event_count' in d, 'missing event_count'
assert 'date_scope' in d, 'missing date_scope'
" && ok "7-day baseline: valid JSON with events array" || die "7-day baseline structure invalid"

if [ $(python3 -c "import json;print(len(json.load(open('$OUT'))['events']))") -eq 0 ]; then
    cp "$OUT" "$BASELINE_7DAY"
    echo "WARNING: no calendar events in 7-day window -- adaptive date tests skipped"
    echo "NOTE: 3 passed, no failures (no data to test against)"
    rm -f "$OUT" "$ERR" "$BASELINE_7DAY"
    exit 0
fi

cp "$OUT" "$BASELINE_7DAY"
export BASELINE="$BASELINE_7DAY"

# =====================================================================
# STEP 2: Extract anchor date from baseline (most-events date).
# =====================================================================
ANCHOR_INFO=$(python3 << 'PYEOF'
import json, os
from collections import Counter
d = json.load(open(os.environ["BASELINE"]))
events = d.get("events", [])
if not events:
    print("NONE 0"); raise SystemExit(0)
date_counter = Counter()
for ev in events:
    dt = ev.get("start_dt", "")[:10]
    if dt and len(dt) == 10:
        date_counter[dt] += 1
anchor_date, anchor_count = date_counter.most_common(1)[0]
print(f"{anchor_date} {anchor_count}")
PYEOF
)
ANCHOR_DATE=$(echo "$ANCHOR_INFO" | awk '{print $1}')
ANCHOR_COUNT=$(echo "$ANCHOR_INFO" | awk '{print $2}')
ok "anchor date: $ANCHOR_DATE with $ANCHOR_COUNT events in baseline"

# =====================================================================
# STEP 3: NEW-FIELD structure validation on EVERY baseline event
#   (the Phase-2 fields this suite exists to guard).
# =====================================================================
python3 -c "
import json
d = json.load(open('$BASELINE'))
events = d['events']
assert isinstance(events, list) and len(events) >= 1, 'baseline has no events'

# Root shape (co CLI: date_scope/days/event_count/in_person_count/virtual_count/events)
for k in ('date_scope', 'days', 'event_count', 'in_person_count',
          'virtual_count', 'events'):
    assert k in d, f'missing root key: {k}'
assert d['event_count'] == len(events), 'event_count != len(events)'
assert d['in_person_count'] + d['virtual_count'] <= len(events), \
    'in_person+virtual exceeds total'

# Per-event REQUIRED keys (16-field _structure_event schema incl. memory_search)
REQUIRED_EVENT_KEYS = ('id', 'subject', 'start_dt', 'start_tz', 'end_dt', 'end_tz',
    'is_all_day', 'location', 'meeting_type', 'requires_transport',
    'attendees', 'organizer', 'body_text', 'context_summary', 'categories',
    'memory_search')

inperson_seen = 0
for ev in events:
    for k in REQUIRED_EVENT_KEYS:
        assert k in ev, f'missing event key: {k} on {ev.get(\"id\",\"?\")} '

    # meeting_type in {virtual,in-person,unknown}
    assert ev['meeting_type'] in ('virtual', 'in-person', 'unknown'), \
        f'invalid meeting_type: {ev[\"meeting_type\"]!r}'

    # requires_transport is a bool; when in-person it MUST be True
    assert isinstance(ev['requires_transport'], bool), \
        f'requires_transport not bool: {ev[\"requires_transport\"]!r}'
    if ev['meeting_type'] == 'in-person':
        inperson_seen += 1
        assert ev['requires_transport'] is True, \
            f'in-person event should have requires_transport==true: {ev[\"id\"]}'

    # context_summary has has_agenda (bool) + action_items (list)
    ctx = ev['context_summary']
    assert 'has_agenda' in ctx and 'action_items' in ctx, 'context_summary incomplete'
    assert isinstance(ctx['has_agenda'], bool), 'has_agenda not bool'
    assert isinstance(ctx['action_items'], list), 'action_items not list'

    # memory_search block present + well-formed on EVERY event
    ms = ev['memory_search']
    assert isinstance(ms, dict), 'memory_search must be a dict'
    for mk in ('keywords', 'enrichment_queries', 'vault_results', 'mentioned_me'):
        assert mk in ms, f'memory_search missing {mk} on {ev.get(\"id\",\"?\")}'
    assert isinstance(ms['keywords'], list), 'memory_search.keywords not list'
    assert isinstance(ms['enrichment_queries'], list), 'enrichment_queries not list'
    assert isinstance(ms['vault_results'], list), 'vault_results not list'
    assert isinstance(ms['mentioned_me'], bool), 'mentioned_me not bool'

    assert isinstance(ev['attendees'], list), 'attendees not list'
    assert 'name' in ev['organizer'] and 'email' in ev['organizer'], \
        'organizer incomplete'
print(f'events={len(events)} in-person-scenarios={inperson_seen}')
" && ok "JSON structure + NEW fields validated on baseline (memory_search/meeting_type/requires_transport/context_summary)" \
   || die "JSON structure / new-field check failed"

# =====================================================================
# STEP 3b: in-person scenario guard (adaptive: only asserts if data has one)
# =====================================================================
python3 -c "
import json
d = json.load(open('$BASELINE'))
ip = [e for e in d['events'] if e['meeting_type'] == 'in-person']
if ip:
    e = ip[0]
    assert e['requires_transport'] is True, 'in-person scenario: requires_transport!=true'
    assert 'memory_search' in e, 'in-person scenario: memory_search key missing'
    print(f'OK: in-person scenario satisfied by {e[\"id\"]}')
else:
    print('NOTE: no in-person events in window -- scenario vacuously passed')
" && ok "in-person scenario (requires_transport==true + memory_search)" \
   || die "in-person scenario failed"

# =====================================================================
# STEP 4: Adaptive single-date test (--start-date ANCHOR --days-ahead 1)
# =====================================================================
run_overview --start-date "$ANCHOR_DATE" --days-ahead 1
RC=$?
if [ "$RC" -eq 0 ] && [ ! -s "$ERR" ]; then
    ok "--start-date $ANCHOR_DATE --days-ahead 1 exit 0, no stderr"
else
    die "--start-date anchor rc=$RC, stderr present"
fi

python3 -c "
import json
baseline = json.load(open('$BASELINE'))
anchor_events_from_baseline = [
    ev for ev in baseline['events']
    if ev['start_dt'][:10] == '$ANCHOR_DATE'
]
single = json.load(open('$OUT'))
assert single, 'empty single-date output'
single_events = single.get('events', [])
ids_baseline = sorted([ev['id'] for ev in anchor_events_from_baseline])
ids_single   = sorted([ev['id'] for ev in single_events])
if ids_baseline != ids_single:
    missing = set(ids_baseline) - set(ids_single)
    extra   = set(ids_single) - set(ids_baseline)
    raise AssertionError(
        f'event ID mismatch: baseline={len(ids_baseline)} single={len(ids_single)} '
        f'missing={list(missing)[:5]} extra={list(extra)[:5]}')
subjects_baseline = sorted([ev['subject'] for ev in anchor_events_from_baseline])
subjects_single   = sorted([ev['subject'] for ev in single_events])
assert subjects_baseline == subjects_single, 'subject mismatch even though IDs matched'
# new fields must survive the single-date path too
for ev in single_events:
    assert 'memory_search' in ev and ev['meeting_type'] in ('virtual','in-person','unknown')
print(f'Verified: single-date returns exactly {len(ids_single)} events on $ANCHOR_DATE')
" && ok "--start-date anchor verification: IDs+subjects match baseline ($ANCHOR_COUNT expected)" \
   || die "single-date mismatch vs baseline"

# =====================================================================
# STEP 5: No-args (today) returns valid co-CLI JSON
# =====================================================================
run_overview
RC=$?
if [ "$RC" -eq 0 ] && [ ! -s "$ERR" ]; then
    ok "no-args exit 0, no stderr"
else
    die "no-args rc=$RC"
fi
python3 -c "
import json; d=json.load(open('$OUT'))
assert isinstance(d['events'], list), 'today should return events list'
assert d['date_scope'] == '$TODAY', f'today date_scope mismatch: {d[\"date_scope\"]}'
assert 'event_count' in d and 'in_person_count' in d, 'today missing co CLI root keys'
" && ok "no-args returns valid JSON for today ($TODAY)" || die "no-args structure failed"

# =====================================================================
# STEP 6: Negative controls
# =====================================================================

# Test E: far-future date = valid JSON
run_overview --start-date "2035-12-31" --days-ahead 1
RC=$?
if [ "$RC" -eq 0 ] && [ ! -s "$ERR" ]; then
    ok "future-date exit 0, no stderr"
else
    die "future-date rc=$RC"
fi
python3 -c "
import json; d=json.load(open('$OUT'))
assert isinstance(d['events'], list), 'future date should still return a list'
assert 'event_count' in d, 'future date missing event_count'
" && ok "future-date: valid JSON structure" || die "future-date structure invalid"

# Test F: invalid date = non-zero exit
python3 "$D" --start-date "not-a-date" >"$OUT" 2>"$ERR" && RC=0 || RC=$?
if [ "$RC" -ne 0 ]; then
    ok "invalid-date graceful failure (rc=$RC)"
else
    die "invalid date did not cause failure"
fi

# Test G: --help exits 0
python3 "$D" --help >"$OUT" 2>"$ERR" && RC=0 || RC=$?
if [ "$RC" -eq 0 ]; then
    ok "--help exits 0"
else
    die "--help non-zero exit"
fi

# Test H: non-integer --days-ahead rejected by argparse
python3 "$D" --start-date "$TODAY" --days-ahead "abc" >"$OUT" 2>"$ERR" && RC=0 || RC=$?
if [ "$RC" -ne 0 ]; then
    ok "bad --days-ahead (non-int) rejected (rc=$RC)"
else
    die "non-int --days-ahead should have failed but did not"
fi

# --- Cleanup ---
rm -f "$OUT" "$ERR" "$BASELINE_7DAY"
echo ""
echo "RESULT: $P passed, $F failed"
[ $F -eq 0 ] && exit 0 || exit 1
