# tests/test_tz_resolve.py
# Regression test for the tz pass-through defect in _structure_event
# (scripts/calendar_overview.py, lines ~66-67). Before the fix, start_dt /
# start_tz / end_dt / end_tz forwarded Microsoft Graph's raw dateTime +
# timeZone VERBATIM, so a consumer could NOT tell whether "09:00" meant 09:00
# UTC or 09:00 in the consumer's zone -> the worker "doubting tz" symptom.
#
# After the fix the four fields carry machine-LOCAL wall-time (start_dt /
# end_dt, offset-qualified ISO 8601) and the machine-LOCAL IANA name
# (start_tz / end_tz, e.g. "Europe/Berlin"), resolved via zoneinfo/TZ. The
# incoming Graph timeZone is NOT relabelled into the output.
#
# Token-free & OFFLINE: _structure_event is a pure transform on event dicts
# (no Graph call, no MSFT_* needed). Hermetic via a temp OBSIDIAN_VAULT_PATH.
import sys, os, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

# Target zone forced for this test so the assertions are deterministic.
os.environ["TZ"] = "Europe/Berlin"

# TWO different SOURCE zones describing the SAME instants, both of which must
# resolve to identical Berlin wall-time. 10:00 Berlin == CET (UTC+1) in Jan ==
# 04:00 US/Eastern EST (UTC-5); 11:00 Berlin == 05:00 EST. Different
# timeZone/offset, same instant -> identical output proves real resolution,
# not a relabeling.
EV_CET = {"id": "E-CET", "subject": "CET morning",
           "start": {"dateTime": "2026-01-06T10:00:00+01:00", "timeZone": "W. Europe Standard Time"},
           "end":    {"dateTime": "2026-01-06T11:00:00+01:00", "timeZone": "W. Europe Standard Time"},
           "attendees": [], "organizer": {"emailAddress": {"name": "J", "address": "j@x"}},
           "body": {"content": ""}}
EV_NY = {"id": "E-NY", "subject": "NY early",
          "start": {"dateTime": "2026-01-06T04:00:00-05:00", "timeZone": "Eastern Standard Time"},
          "end":    {"dateTime": "2026-01-06T05:00:00-05:00", "timeZone": "Eastern Standard Time"},
          "attendees": [], "organizer": {"emailAddress": {"name": "J", "address": "j@x"}},
          "body": {"content": ""}}

import calendar_overview as c

with tempfile.TemporaryDirectory() as td:
    os.environ["OBSIDIAN_VAULT_PATH"] = td         # make enrich_event hermetic
    a = c._structure_event(EV_CET, self_email="me@x.com")
    b = c._structure_event(EV_NY,  self_email="me@x.com")

# (1) start_tz / end_tz are the MACHINE-LOCAL IANA name, NOT the raw Graph name.
assert a["start_tz"] == "Europe/Berlin", a["start_tz"]
assert a["end_tz"]   == "Europe/Berlin", a["end_tz"]
assert b["start_tz"] == "Europe/Berlin", b["start_tz"]
assert "W. Europe" not in a["start_tz"], "raw Graph timeZone leaked into start_tz: " + a["start_tz"]
assert "Eastern"   not in b["start_tz"], "raw Graph timeZone leaked into start_tz: " + b["start_tz"]

# (2) start_dt / end_dt are local Berlin wall-time, offset-qualified ISO 8601.
assert a["start_dt"] == "2026-01-06T10:00:00+01:00", a["start_dt"]
assert a["end_dt"]   == "2026-01-06T11:00:00+01:00", a["end_dt"]

# (3) Different SOURCE zone, SAME instant -> identical local wall-time.
assert b["start_dt"] == a["start_dt"], (b["start_dt"], a["start_dt"])
assert b["end_dt"]   == a["end_dt"],   (b["end_dt"], a["end_dt"])

# (4) All four fields still present (schema shape unchanged).
for k in ("start_dt", "start_tz", "end_dt", "end_tz"):
    assert k in a, "missing field " + k

print("TZRESOLVE-OK")
